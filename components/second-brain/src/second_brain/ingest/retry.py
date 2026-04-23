from __future__ import annotations

from datetime import UTC, datetime

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.orchestrator import DEFAULT_CONVERTERS, _pick_converter
from second_brain.log import EventKind, append_event
from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind


class RetryError(RuntimeError):
    pass


def retry_source(slug: str, *, cfg: Config) -> None:
    folder_path = cfg.sources_dir / slug
    if not folder_path.exists():
        raise RetryError(f"source not found: {slug}")
    fm, _body = load_document(folder_path / "_source.md")
    raw_entries = fm.get("raw") or []
    if not raw_entries:
        raise RetryError(f"no raw artifacts to replay for {slug}")
    first = raw_entries[0]
    raw_path = folder_path / first["path"]
    if not raw_path.exists():
        raise RetryError(f"raw file missing: {raw_path}")

    source = IngestInput.from_path(raw_path)
    converter = _pick_converter(source, DEFAULT_CONVERTERS)
    folder = SourceFolder(root=folder_path)
    artifacts = converter.convert(source, folder)  # may raise; propagate

    kind = SourceKind(converter.kind)
    title = (artifacts.title_hint or fm.get("title") or slug).strip()
    folder.write_manifest(artifacts.raw)

    ingested_at_raw = fm.get("ingested_at")
    if isinstance(ingested_at_raw, datetime):
        ingested_at = ingested_at_raw
    elif isinstance(ingested_at_raw, str):
        try:
            ingested_at = datetime.fromisoformat(ingested_at_raw.replace("Z", "+00:00"))
        except ValueError:
            ingested_at = datetime.now(UTC)
    else:
        ingested_at = datetime.now(UTC)

    new_fm = SourceFrontmatter(
        id=slug,
        title=title,
        kind=kind,
        authors=artifacts.authors_hint,
        year=artifacts.year_hint,
        source_url=fm.get("source_url"),
        tags=fm.get("tags", []) or [],
        ingested_at=ingested_at,
        content_hash=source.sha256,
        habit_taxonomy=fm.get("habit_taxonomy"),
        raw=[RawArtifact(path=r.path, kind=r.kind, sha256=r.sha256) for r in artifacts.raw],
        cites=fm.get("cites", []) or [],
        related=fm.get("related", []) or [],
        supersedes=fm.get("supersedes", []) or [],
        abstract=fm.get("abstract", "") or "",
    )
    dump_document(
        folder.source_md, new_fm.to_frontmatter_dict(), artifacts.processed_body
    )
    append_event(
        kind=EventKind.RETRY,
        op=f"retry.{kind.value}",
        subject=slug,
        value=source.origin,
        home=cfg.home,
    )
