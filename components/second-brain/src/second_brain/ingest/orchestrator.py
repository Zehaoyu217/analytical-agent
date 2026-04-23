from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.ingest.base import Converter, IngestInput, SourceFolder
from second_brain.ingest.docx import DocxConverter
from second_brain.ingest.epub import EpubConverter
from second_brain.ingest.note import NoteConverter
from second_brain.ingest.pdf import PdfConverter
from second_brain.ingest.repo import RepoConverter
from second_brain.ingest.url import UrlConverter
from second_brain.log import EventKind, append_event
from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind
from second_brain.slugs import propose_source_slug


class IngestError(RuntimeError):
    pass


DEFAULT_CONVERTERS: list[Converter] = [
    NoteConverter(),
    PdfConverter(),
    DocxConverter(),
    EpubConverter(),
    UrlConverter(),
    RepoConverter(),
]


def ingest(
    source: IngestInput,
    *,
    cfg: Config,
    converters: list[Converter] | None = None,
) -> SourceFolder:
    cfg.sources_dir.mkdir(parents=True, exist_ok=True)
    registered = converters or DEFAULT_CONVERTERS

    _check_duplicate(cfg, source.sha256)

    converter = _pick_converter(source, registered)
    kind = SourceKind(converter.kind)

    # Speculative slug (may need bump after real title lands).
    taken = _taken_slugs(cfg)
    title_guess = _fallback_title(source)
    slug = propose_source_slug(kind=kind, title=title_guess, taken=taken)
    folder = SourceFolder.create(cfg.sources_dir / slug)

    try:
        artifacts = converter.convert(source, folder)
    except Exception:
        folder.destroy()
        raise

    title = (artifacts.title_hint or title_guess).strip() or title_guess
    # If the real title would produce a different slug, rename folder (once).
    desired = propose_source_slug(kind=kind, title=title, year=artifacts.year_hint, taken=taken)
    if desired != slug:
        new_root = cfg.sources_dir / desired
        folder.root.rename(new_root)
        folder = SourceFolder(root=new_root)
        slug = desired

    folder.write_manifest(artifacts.raw)

    frontmatter = SourceFrontmatter(
        id=slug,
        title=title,
        kind=kind,
        authors=artifacts.authors_hint,
        year=artifacts.year_hint,
        source_url=None,
        tags=[],
        ingested_at=datetime.now(UTC),
        content_hash=source.sha256,
        habit_taxonomy=None,
        raw=[
            RawArtifact(path=r.path, kind=r.kind, sha256=r.sha256) for r in artifacts.raw
        ],
        cites=[],
        related=[],
        supersedes=[],
        abstract="",
    )
    dump_document(folder.source_md, frontmatter.to_frontmatter_dict(), artifacts.processed_body)
    append_event(
        kind=EventKind.INGEST,
        op=f"ingest.{kind.value}",
        subject=slug,
        value=source.origin,
        home=cfg.home,
    )
    return folder


def _pick_converter(source: IngestInput, registered: list[Converter]) -> Converter:
    for c in registered:
        if c.matches(source):
            return c
    raise IngestError(f"no converter matched suffix={source.suffix!r}")


def _taken_slugs(cfg: Config) -> set[str]:
    if not cfg.sources_dir.exists():
        return set()
    return {p.name for p in cfg.sources_dir.iterdir() if p.is_dir()}


def _check_duplicate(cfg: Config, content_hash: str) -> None:
    for folder in cfg.sources_dir.glob("*/_source.md"):
        from second_brain.frontmatter import load_document
        meta, _ = load_document(folder)
        if meta.get("content_hash") == content_hash:
            raise IngestError(f"duplicate content_hash → existing: {folder.parent.name}")


def _fallback_title(source: IngestInput) -> str:
    from pathlib import Path
    return Path(source.origin).stem or "untitled"
