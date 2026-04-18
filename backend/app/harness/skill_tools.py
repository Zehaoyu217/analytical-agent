# backend/app/harness/skill_tools.py
from __future__ import annotations

import dataclasses
import difflib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _closest_skill_names(target: str, available: list[str], *, n: int = 5) -> list[str]:
    """Return up to ``n`` closest matches from ``available`` to ``target``.

    Uses difflib ratio so "correl" → "correlation", "timeseries" →
    "time_series".  Empty list when nothing is close enough.
    """
    if not target or not available:
        return []
    return difflib.get_close_matches(target, available, n=n, cutoff=0.4)

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore
from app.harness.dispatcher import ToolDispatcher
from app.harness.fs_tools import FsTools
from app.harness.sandbox import SandboxExecutor
from app.skills.data_profiler import profile
from app.skills.registry import SkillRegistry
from app.skills.statistical_analysis.correlation import correlate
from app.skills.statistical_analysis.distribution_fit import fit as dist_fit
from app.skills.statistical_analysis.group_compare import compare
from app.skills.statistical_analysis.stat_validate import validate
from app.skills.statistical_analysis.time_series import (
    characterize,
    decompose,
    find_anomalies,
    find_changepoints,
    lag_correlate,
)
from app.storage.session_db import SessionDB
from app.wiki.engine import WikiEngine
from app.wiki.schema import Finding


def register_core_tools(
    dispatcher: ToolDispatcher,
    artifact_store: ArtifactStore,
    wiki: WikiEngine,
    sandbox: SandboxExecutor,
    session_id: str,
    registry: SkillRegistry | None = None,
    session_db: SessionDB | None = None,
) -> None:
    def _lookup_frame(args: dict[str, Any]) -> pd.DataFrame:
        """Resolve a named or ID-referenced artifact into a pandas DataFrame.

        Lookup order:
          1. ``artifact_id`` key — direct ID lookup.
          2. ``name`` / ``dataset_name`` / ``frame_name`` key — name lookup
             (case-insensitive match against artifact name or title).

        Raises ``ValueError`` with the list of available artifact names when
        nothing is found so the model can self-correct.
        """
        import json as _json  # noqa: PLC0415

        import pandas as pd  # noqa: PLC0415

        artifact = None

        if "artifact_id" in args:
            artifact = artifact_store.get_artifact(session_id, str(args["artifact_id"]))

        if artifact is None:
            frame_name = (
                args.get("name")
                or args.get("dataset_name")
                or args.get("frame_name")
            )
            if frame_name:
                artifact = artifact_store.get_artifact_by_name(session_id, str(frame_name))

        if artifact is None:
            available = [
                a.name or a.title
                for a in artifact_store.get_artifacts(session_id)
            ]
            raise ValueError(
                "frame not found — pass 'data' inline, or provide 'artifact_id' / 'name'. "
                f"Available artifacts in this session: {available}"
            )

        try:
            records = _json.loads(artifact.content)
            return pd.DataFrame(records)
        except Exception as exc:
            raise ValueError(
                f"artifact '{artifact.name or artifact.id}' content could not be parsed "
                f"as tabular data: {exc}"
            ) from exc

    def _emit_skill_event(
        *,
        name: str,
        started: float,
        outcome: str,
        detail: dict[str, Any],
    ) -> None:
        """Best-effort skill-load telemetry — never raises."""
        from app.telemetry.skills_log import append_skill_event  # noqa: PLC0415

        record = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "actor": f"skill:{name}",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "outcome": outcome,
            "detail": detail,
        }
        append_skill_event(record)

    def _load_skill_body(args: dict[str, Any]) -> dict:
        """Return the SKILL.md body with breadcrumb header and sub-skill catalog.

        Progressive exposure: loading a skill automatically appends the catalog
        of its direct children (system-generated from the registry tree).
        The agent calls skill() on any child name to go deeper.
        """
        started = time.monotonic()
        name = args.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("skill: 'name' (string) required")
        if registry is None:
            raise RuntimeError("skill registry not wired")

        node = registry.get_skill(name)
        if node is None:
            available = registry.list_skills()
            suggestions = _closest_skill_names(name, available)
            _emit_skill_event(
                name=name,
                started=started,
                outcome="error",
                detail={"action": "load", "reason": "not_found"},
            )
            raise KeyError(
                f"skill: '{name}' not found. "
                f"{len(available)} skills available. "
                f"Suggestions: {suggestions}"
            )

        meta = node.metadata
        breadcrumb = registry.get_breadcrumb(name)
        children = registry.get_children(name)

        # Build the body: optional breadcrumb header + instructions + optional sub-skill catalog
        parts: list[str] = []

        # Breadcrumb header (only for skills below Level 1)
        if node.depth > 1:
            crumb = " › ".join(breadcrumb)
            parts.append(f"# {crumb}\n")
        else:
            parts.append(f"# {name}\n")

        parts.append(node.instructions)

        # Auto-appended sub-skill catalog (system-generated, never authored)
        if children:
            catalog_lines = ["---", "## Sub-skills", ""]
            for child in children:
                child_desc = child.metadata.description.strip()
                catalog_lines.append(f"- `{child.metadata.name}` — {child_desc}")
            parts.append("\n".join(catalog_lines))

        full_body = "\n\n".join(p.strip() for p in parts if p.strip())

        has_package = (
            node.package_path is not None
            and node.package_path.exists()
            and any(node.package_path.iterdir())
        )

        _emit_skill_event(
            name=name,
            started=started,
            outcome="ok",
            detail={
                "action": "load",
                "depth": node.depth,
                "has_package": bool(has_package),
            },
        )

        return {
            "name": meta.name,
            "body": full_body,
            "metadata": {
                "name": meta.name,
                "version": meta.version,
                "description": meta.description,
                "requires": list(meta.dependencies_requires),
                "used_by": list(meta.dependencies_used_by),
                "packages": list(meta.dependencies_packages),
                "error_templates": dict(meta.error_templates),
            },
            "has_python_package": has_package,
            "depth": node.depth,
            "breadcrumb": breadcrumb,
            "child_count": len(children),
        }

    def _run_sandbox(args: dict[str, Any]) -> dict:
        code = str(args.get("code", ""))
        result = sandbox.run(code)
        return {
            "ok": result.ok,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "duration_sec": result.duration_sec,
        }

    def _save(args: dict[str, Any]) -> dict:
        content = args["content"]
        if not isinstance(content, str):
            content = str(content)
        art = Artifact(
            type=args.get("type", "table"),
            title=args.get("title", ""),
            description=args.get("summary", args.get("description", "")),
            content=content,
            format=args.get("format", args.get("mime_type", "html")),
        )
        saved = artifact_store.add_artifact(session_id, art)
        return {"artifact_id": saved.id}

    def _update(args: dict[str, Any]) -> dict:
        updates = {
            k: v
            for k, v in args.items()
            if k != "artifact_id" and v is not None
        }
        artifact_store.update_artifact(session_id, args["artifact_id"], **updates)
        return {"ok": True, "artifact_id": args["artifact_id"]}

    def _get(args: dict[str, Any]) -> dict:
        art = artifact_store.get_artifact(session_id, args["artifact_id"])
        if art is None:
            return {"ok": False, "error": "not_found"}
        return {
            "artifact_id": art.id,
            "type": art.type,
            "title": art.title,
            "description": art.description,
            "format": art.format,
        }

    def _write_working(args: dict[str, Any]) -> dict:
        content = str(args.get("content", ""))
        wiki.write_working(content)
        return {"ok": True, "content": content}

    def _promote(args: dict[str, Any]) -> dict:
        finding = Finding(
            id=str(args["finding_id"]),
            title=str(args.get("title", args["finding_id"])),
            body=str(args["body"]),
            evidence=list(args.get("evidence_ids", [])),
            stat_validate_pass=bool(args.get("validated", True)),
        )
        path = wiki.promote_finding(finding)
        return {"ok": True, "finding_id": finding.id, "path": str(path)}

    def _correlate(args: dict[str, Any]) -> dict:
        import pandas as pd
        df = pd.DataFrame(args["data"]) if "data" in args else _lookup_frame(args)
        result = correlate(
            df=df,
            x=args["x"],
            y=args["y"],
            method=args.get("method", "auto"),
            partial_on=args.get("partial_on"),
            detrend=args.get("detrend"),
            bootstrap_n=int(args.get("bootstrap_n", 1000)),
            store=artifact_store,
            session_id=session_id,
        )
        return result.to_dict()

    def _compare(args: dict[str, Any]) -> dict:
        import pandas as pd
        df = pd.DataFrame(args["data"]) if "data" in args else _lookup_frame(args)
        result = compare(
            df=df,
            value=args["value"],
            group=args["group"],
            paired=bool(args.get("paired", False)),
            paired_id=args.get("paired_id"),
            method=args.get("method", "auto"),
            bootstrap_n=int(args.get("bootstrap_n", 1000)),
            store=artifact_store,
            session_id=session_id,
        )
        return result.to_dict()

    def _validate(args: dict[str, Any]) -> dict:
        import pandas as pd
        frame = None
        if "frame_data" in args:
            frame = pd.DataFrame(args["frame_data"])
        verdict = validate(
            claim_kind=args["claim_kind"],
            payload=args["payload"],
            turn_trace=args.get("turn_trace", []),
            frame=frame,
            stratify_candidates=tuple(args.get("stratify_candidates", ())),
            claim_text=str(args.get("claim_text", "")),
        )
        return verdict.to_dict()

    def _characterize(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        return characterize(s).to_dict()

    def _decompose(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        d = decompose(s, period=args.get("period"))
        return {
            "period": d.period,
            "trend": d.trend.tolist(),
            "seasonal": d.seasonal.tolist(),
            "residual": d.residual.tolist(),
        }

    def _anomalies(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        a = find_anomalies(s, method=args.get("method", "auto"))
        return {
            "indices": list(a.indices),
            "values": list(a.values),
            "method_used": a.method_used,
            "threshold": a.threshold,
        }

    def _changepoints(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        c = find_changepoints(s, penalty=float(args.get("penalty", 10.0)))
        return {
            "indices": list(c.indices),
            "segments": [list(seg) for seg in c.segments],
        }

    def _lag_correlate(args: dict[str, Any]) -> dict:
        import pandas as pd
        x = pd.Series(args["x"])
        y = pd.Series(args["y"])
        result = lag_correlate(
            x,
            y,
            max_lag=int(args.get("max_lag", 30)),
            accept_non_stationary=bool(args.get("accept_non_stationary", False)),
        )
        return {
            "lags": result.lags.tolist(),
            "coefficients": result.coefficients.tolist(),
            "significant_lags": list(result.significant_lags),
        }

    def _fit(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        return dist_fit(
            s,
            candidates=args.get("candidates", "auto"),
            store=artifact_store,
            session_id=session_id,
        ).to_dict()

    def _profile(args: dict[str, Any]) -> dict:
        import pandas as pd
        df = pd.DataFrame(args["data"]) if "data" in args else _lookup_frame(args)
        report = profile(
            df=df,
            name=str(args.get("name", "dataset")),
            key_candidates=list(args.get("key_candidates", [])),
            store=artifact_store,
            session_id=session_id,
        )
        return {
            "summary": report.summary,
            "artifact_id": report.artifact_id,
            "report_artifact_id": report.report_artifact_id,
            "risks": [dataclasses.asdict(risk) for risk in report.risks],
        }

    dispatcher.register("skill", _load_skill_body)
    dispatcher.register("sandbox.run", _run_sandbox)
    dispatcher.register("save_artifact", _save)
    dispatcher.register("update_artifact", _update)
    dispatcher.register("get_artifact", _get)
    dispatcher.register("write_working", _write_working)
    dispatcher.register("promote_finding", _promote)
    dispatcher.register("correlation.correlate", _correlate)
    dispatcher.register("group_compare.compare", _compare)
    dispatcher.register("stat_validate.validate", _validate)
    dispatcher.register("time_series.characterize", _characterize)
    dispatcher.register("time_series.decompose", _decompose)
    dispatcher.register("time_series.find_anomalies", _anomalies)
    dispatcher.register("time_series.find_changepoints", _changepoints)
    dispatcher.register("time_series.lag_correlate", _lag_correlate)
    dispatcher.register("distribution_fit.fit", _fit)
    dispatcher.register("data_profiler.profile", _profile)

    from app.skills.reporting.report_builder.pkg.build import (
        build as _report_build,  # local import to keep harness import graph flat
    )

    dispatcher.register("report.build", lambda args: _report_build(**args))

    from app.skills.analysis_plan.pkg.plan import plan as _analysis_plan
    from app.skills.reporting.dashboard_builder.pkg.build import build as _dashboard_build

    dispatcher.register("analysis_plan.plan", lambda args: _analysis_plan(**args))
    dispatcher.register("dashboard.build", lambda args: _dashboard_build(**args))

    # ── Filesystem tools (P25) ────────────────────────────────────────────────
    _repo_root = Path(__file__).resolve().parents[3]
    fs = FsTools(project_root=_repo_root)
    dispatcher.register("read_file", fs.read_file)
    dispatcher.register("glob_files", fs.glob_files)
    dispatcher.register("search_text", fs.search_text)

    # ── Session search (H2) ───────────────────────────────────────────────────
    _sdb = session_db

    def _session_search(args: dict[str, Any]) -> dict[str, Any]:
        if _sdb is None:
            return {"results": [], "error": "session_db not available"}
        query = str(args.get("query", "")).strip()
        if not query:
            return {"results": [], "error": "query is required"}
        limit = min(int(args.get("limit", 5)), 20)
        results = _sdb.search(query=query, limit=limit)
        return {
            "results": [
                {
                    "session_id": r.session_id,
                    "message_id": r.message_id,
                    "snippet": r.snippet,
                    "role": r.role,
                    "timestamp": r.timestamp,
                }
                for r in results
            ]
        }

    dispatcher.register("session_search", _session_search)
