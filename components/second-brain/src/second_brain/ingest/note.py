from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder

_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class NoteConverter(Converter):
    kind: ClassVar[str] = "note"
    _SUFFIXES = frozenset({".md", ".txt"})

    def matches(self, source: IngestInput) -> bool:
        return source.suffix in self._SUFFIXES

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        body = source.content.decode("utf-8", errors="replace")
        raw_write = target.write_raw(
            rel_path=f"raw/original{source.suffix}",
            content=source.content,
            kind="original",
        )
        match = _H1.search(body)
        if match:
            title = match.group(1).strip()
        else:
            title = Path(source.origin).stem
        return SourceArtifacts(
            processed_body=body if body.endswith("\n") else body + "\n",
            raw=[raw_write],
            title_hint=title,
        )
