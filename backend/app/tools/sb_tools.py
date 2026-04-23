"""Second-Brain tool handlers. Each function returns a JSON-serializable dict.

When the Second-Brain KB is disabled (directory missing), every handler
returns a structured error rather than raising, so the agent loop keeps
working without the KB.
"""
from __future__ import annotations

from datetime import UTC
from typing import Any

from app import config


def _disabled(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": "second_brain_disabled"}
    if extra:
        out.update(extra)
    return out


def _cfg() -> Any:
    from second_brain.config import Config
    return Config.load()


def sb_search(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled({"hits": []})
    from second_brain.research.broker import broker_search

    query = str(args.get("query", ""))
    if not query:
        return {"ok": False, "error": "missing query", "hits": []}
    k = int(args.get("k", 5))
    scope = str(args.get("scope", "both"))
    with_neighbors = bool(args.get("with_neighbors", False))

    cfg = _cfg()
    if not cfg.fts_path.exists():
        return {"ok": False, "error": "no_index", "hits": []}

    result = broker_search(
        cfg,
        query=query,
        k=k,
        scope=scope,
        with_neighbors=with_neighbors,
    )
    return {
        "ok": True,
        "hits": [
            {
                "id": h.id,
                "kind": h.kind,
                "title": h.title,
                "score": h.score,
                "matched_field": h.matched_field,
                "summary": h.summary,
                "project_ids": h.project_ids,
                "source_ids": h.source_ids,
                "claim_ids": h.claim_ids,
                "section_title": h.section_title,
                "page_start": h.page_start,
                "page_end": h.page_end,
                "evidence": [
                    {
                        "id": ev.id,
                        "kind": ev.kind,
                        "score": ev.score,
                        "matched_field": ev.matched_field,
                        "snippet": ev.snippet,
                        "neighbors": ev.neighbors,
                        "source_id": ev.source_id,
                        "chunk_id": ev.chunk_id,
                        "section_title": ev.section_title,
                        "source_title": ev.source_title,
                        "page_start": ev.page_start,
                        "page_end": ev.page_end,
                    }
                    for ev in h.evidence
                ],
            }
            for h in result.hits
        ],
    }


def sb_load(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    from second_brain.load import LoadError, load_node

    node_id = str(args.get("node_id", ""))
    if not node_id:
        return {"ok": False, "error": "missing node_id"}
    depth = int(args.get("depth", 0))
    relations = args.get("relations") or None
    if isinstance(relations, str):
        relations = [r.strip() for r in relations.split(",") if r.strip()]

    cfg = _cfg()
    try:
        result = load_node(cfg, node_id, depth=depth, relations=relations)
    except LoadError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — KB may be uninitialised; surface as structured error
        return {"ok": False, "error": f"load_failed: {exc}"}
    return {
        "ok": True,
        "root": result.root,
        "neighbors": result.neighbors,
        "edges": result.edges,
    }


def sb_reason(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled({"paths": []})
    from second_brain.reason import GraphPattern
    from second_brain.reason import sb_reason as _run

    start_id = str(args.get("start_id", ""))
    walk = str(args.get("walk", ""))
    if not start_id or not walk:
        return {"ok": False, "error": "start_id and walk required", "paths": []}
    direction = str(args.get("direction", "outbound"))
    max_depth = int(args.get("max_depth", 3))
    terminator = args.get("terminator")

    cfg = _cfg()
    paths = _run(
        cfg,
        start_id=start_id,
        pattern=GraphPattern(
            walk=walk,
            direction=direction,  # type: ignore[arg-type]
            max_depth=max_depth,
            terminator=terminator,
        ),
    )
    return {"ok": True, "paths": paths}


def sb_ingest(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    from pathlib import Path as _Path

    from second_brain.ingest.base import IngestInput
    from second_brain.ingest.orchestrator import IngestError, ingest
    from second_brain.reindex import reindex
    from second_brain.research.compiler import compile_center

    path_or_url = str(args.get("path", ""))
    if not path_or_url:
        return {"ok": False, "error": "missing path"}

    cfg = _cfg()
    try:
        if path_or_url.startswith(("http://", "https://", "gh:", "file://")):
            inp = IngestInput.from_bytes(
                origin=path_or_url,
                suffix=_Path(path_or_url).suffix,
                content=b"",
            )
        else:
            inp = IngestInput.from_path(_Path(path_or_url))
        folder = ingest(inp, cfg=cfg)
        compile_center(cfg)
        reindex(cfg)
    except IngestError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"ingest_failed: {exc}"}
    return {"ok": True, "source_id": folder.root.name, "folder": str(folder.root)}


def sb_promote_claim(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()

    from datetime import datetime
    from io import StringIO

    from ruamel.yaml import YAML
    from second_brain.reindex import reindex
    from second_brain.research.compiler import compile_center
    from second_brain.schema.claim import ClaimConfidence, ClaimFrontmatter, ClaimKind

    statement = str(args.get("statement", "")).strip()
    if not statement:
        return {"ok": False, "error": "missing statement"}

    kind_raw = str(args.get("kind", "empirical"))
    conf_raw = str(args.get("confidence", "low"))
    try:
        kind = ClaimKind(kind_raw)
    except ValueError:
        return {"ok": False, "error": f"invalid kind: {kind_raw}"}
    try:
        confidence = ClaimConfidence(conf_raw)
    except ValueError:
        return {"ok": False, "error": f"invalid confidence: {conf_raw}"}

    supports = [str(x) for x in (args.get("supports") or [])]
    contradicts = [str(x) for x in (args.get("contradicts") or [])]
    refines = [str(x) for x in (args.get("refines") or [])]
    abstract = str(args.get("abstract", ""))
    taxonomy = str(args.get("taxonomy", ""))

    cfg = _cfg()
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify_claim(statement)
    claim_id = f"clm_{slug}"
    path = cfg.claims_dir / f"{slug}.md"
    if path.exists():
        return {"ok": False, "error": f"claim file exists: {path.name}"}

    fm = ClaimFrontmatter(
        id=claim_id,
        statement=statement,
        kind=kind,
        confidence=confidence,
        supports=supports,
        contradicts=contradicts,
        refines=refines,
        extracted_at=datetime.now(UTC),
        abstract=abstract,
    )

    yaml = YAML()
    yaml.default_flow_style = False
    buf = StringIO()
    yaml.dump(fm.to_frontmatter_dict(), buf)
    fm_text = buf.getvalue().rstrip()

    body_lines = ["---", fm_text, "---", "", f"# {statement}", ""]
    if abstract:
        body_lines.extend([abstract, ""])
    if taxonomy:
        body_lines.extend([f"> taxonomy: `{taxonomy}`", ""])
    path.write_text("\n".join(body_lines), encoding="utf-8")
    compile_center(cfg)
    reindex(cfg)

    return {
        "ok": True,
        "claim_id": claim_id,
        "filename": path.name,
        "path": str(path),
    }


def _slugify_claim(text: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        slug = "claim"
    return slug[:60].rstrip("-")
