from __future__ import annotations

import hashlib
import io
import json
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, ClassVar, Protocol, runtime_checkable


@dataclass(frozen=True)
class IngestInput:
    origin: str
    suffix: str
    content: bytes

    @classmethod
    def from_path(cls, path: Path) -> IngestInput:
        return cls(
            origin=str(path),
            suffix=path.suffix.lower(),
            content=path.read_bytes(),
        )

    @classmethod
    def from_bytes(cls, *, origin: str, suffix: str, content: bytes) -> IngestInput:
        return cls(origin=origin, suffix=suffix, content=content)

    @contextmanager
    def open_stream(self) -> Iterator[IO[bytes]]:
        buf = io.BytesIO(self.content)
        try:
            yield buf
        finally:
            buf.close()

    @property
    def sha256(self) -> str:
        return "sha256:" + hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class RawWrite:
    path: str  # relative to folder root, e.g. "raw/paper.pdf"
    kind: str  # "original" | "screenshot" | "extracted-text" | ...
    sha256: str


@dataclass(frozen=True)
class SourceArtifacts:
    processed_body: str
    raw: list[RawWrite] = field(default_factory=list)
    title_hint: str | None = None
    year_hint: int | None = None
    authors_hint: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceFolder:
    root: Path

    KIND: ClassVar[str] = "folder"

    @classmethod
    def create(cls, root: Path) -> SourceFolder:
        if root.exists():
            raise FileExistsError(f"{root} already exists")
        root.mkdir(parents=True)
        (root / "raw").mkdir()
        return cls(root=root)

    @property
    def source_md(self) -> Path:
        return self.root / "_source.md"

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def raw_manifest(self) -> Path:
        return self.root / "raw_manifest.json"

    @property
    def chunk_manifest(self) -> Path:
        return self.root / "chunk_manifest.json"

    def write_raw(self, *, rel_path: str, content: bytes, kind: str) -> RawWrite:
        if not rel_path.startswith("raw/"):
            raise ValueError("rel_path must live under raw/")
        target = self.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        return RawWrite(path=rel_path, kind=kind, sha256=digest)

    def write_manifest(self, raws: list[RawWrite]) -> None:
        data = [{"path": r.path, "kind": r.kind, "sha256": r.sha256} for r in raws]
        self.raw_manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def destroy(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


@runtime_checkable
class Converter(Protocol):
    kind: ClassVar[str]

    def matches(self, source: IngestInput) -> bool: ...

    def convert(
        self, source: IngestInput, target: SourceFolder
    ) -> SourceArtifacts: ...
