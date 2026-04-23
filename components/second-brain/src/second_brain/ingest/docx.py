from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder


class DocxConverter(Converter):
    kind: ClassVar[str] = "docx"

    def matches(self, source: IngestInput) -> bool:
        return source.suffix == ".docx"

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        raw_write = target.write_raw(
            rel_path="raw/original.docx",
            content=source.content,
            kind="original",
        )
        body = self._extract_text(source)
        title = self._guess_title(body, source)
        return SourceArtifacts(
            processed_body=body,
            raw=[raw_write],
            title_hint=title,
        )

    @staticmethod
    def _extract_text(source: IngestInput) -> str:
        try:
            from markitdown import MarkItDown  # type: ignore[import-not-found]

            md = MarkItDown()
            with source.open_stream() as stream:
                result = md.convert_stream(stream, file_extension=".docx")
            text = (result.text_content or "").strip()
            return text + "\n" if text else "\n"
        except Exception as exc:  # noqa: BLE001
            return f"[markitdown failed: {exc}]\n"

    @staticmethod
    def _guess_title(body: str, source: IngestInput) -> str:
        stripped_body = body.strip()
        if stripped_body.startswith("[markitdown failed"):
            # Fallback placeholder spans one or more lines; skip straight to stem.
            return Path(source.origin).stem
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped and not stripped.startswith("[markitdown"):
                return stripped[:120]
        return Path(source.origin).stem
