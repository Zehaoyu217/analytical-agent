# backend/app/harness/skill_tools.py
from __future__ import annotations

import dataclasses
from typing import Any

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore
from app.harness.dispatcher import ToolDispatcher
from app.harness.sandbox import SandboxExecutor
from app.skills.correlation import correlate
from app.skills.data_profiler import profile
from app.skills.distribution_fit import fit as dist_fit
from app.skills.group_compare import compare
from app.skills.registry import SkillRegistry
from app.skills.stat_validate import validate
from app.skills.time_series import (
    characterize,
    decompose,
    find_anomalies,
    find_changepoints,
    lag_correlate,
)
from app.wiki.engine import WikiEngine
from app.wiki.schema import Finding


def _lookup_frame(args: dict[str, Any]):
    # Hook for DuckDB-backed frame lookup by name/id — wired up in the
    # agent API layer. Placeholder here keeps the registration self-contained.
    raise NotImplementedError(
        "frame lookup: pass 'data' inline or wire DuckDB lookup in higher layer"
    )


def register_core_tools(
    dispatcher: ToolDispatcher,
    artifact_store: ArtifactStore,
    wiki: WikiEngine,
    sandbox: SandboxExecutor,
    session_id: str,
    registry: SkillRegistry | None = None,
) -> None:
    def _load_skill_body(args: dict[str, Any]) -> dict:
        name = args.get("name")
        if not name:
            raise ValueError("skill: 'name' required")
        if registry is None:
            raise RuntimeError("skill registry not wired")
        body = registry.get_instructions(name)
        if body is None:
            raise KeyError(f"skill: '{name}' not found")
        return {"name": name, "body": body}

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
        wiki.write_working(str(args.get("content", "")))
        return {"ok": True}

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

    from app.skills.report_builder.pkg import build as _report_build  # local import to keep harness import graph flat

    dispatcher.register("report.build", lambda **kw: _report_build(**kw))

    from app.skills.analysis_plan.pkg.plan import plan as _analysis_plan
    from app.skills.dashboard_builder.pkg.build import build as _dashboard_build

    dispatcher.register("analysis_plan.plan", lambda **kw: _analysis_plan(**kw))
    dispatcher.register("dashboard.build", lambda **kw: _dashboard_build(**kw))
