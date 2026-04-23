from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder

log = logging.getLogger(__name__)

# Common Homebrew / system locations to try if `java` isn't already on PATH.
# opendataloader_pdf invokes the bundled JAR via subprocess and relies on the
# `java` executable being discoverable, so we proactively prepend any known
# JDK directory before running.
_JAVA_PATH_CANDIDATES = (
    "/opt/homebrew/opt/openjdk/bin",
    "/opt/homebrew/opt/openjdk@21/bin",
    "/opt/homebrew/opt/openjdk@17/bin",
    "/usr/local/opt/openjdk/bin",
    "/usr/lib/jvm/default-java/bin",
)

_MARKDOWN_PAGE_SEPARATOR = "<!-- page: %page-number% -->"
_PAGE_MARKER_RE = re.compile(r"^<!--\s*page[: ]+\d+\s*-->$", re.IGNORECASE)


def _java_works(java_bin: str = "java") -> bool:
    """Return True if `java -version` exits cleanly.

    On macOS, /usr/bin/java is a stub that exits non-zero with a "please
    install Java" prompt — `shutil.which` finds it, but it isn't usable.
    Probe with a real invocation instead.
    """
    try:
        proc = subprocess.run(
            [java_bin, "-version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ensure_java_on_path() -> None:
    if shutil.which("java") and _java_works():
        return
    for candidate in _JAVA_PATH_CANDIDATES:
        java_bin = Path(candidate, "java")
        if java_bin.exists() and _java_works(str(java_bin)):
            os.environ["PATH"] = candidate + os.pathsep + os.environ.get("PATH", "")
            return


class PdfConverter(Converter):
    kind: ClassVar[str] = "pdf"

    def matches(self, source: IngestInput) -> bool:
        return source.suffix == ".pdf"

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        raw_write = target.write_raw(
            rel_path="raw/original.pdf",
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
        """Convert PDF bytes to Markdown via opendataloader_pdf.

        opendataloader_pdf wraps a Java JAR (PDFBox-based) that produces
        substantially better Markdown — preserving tables, headings, and
        reading order — than markitdown's pdfminer pipeline.

        The library only accepts file paths, so we stage the bytes into a
        temp directory, run the converter, and read the resulting `.md`
        sibling back. Failures fall through to a placeholder so ingest
        still succeeds and `sb lint` can flag the source for retry.
        """
        _ensure_java_on_path()
        try:
            import opendataloader_pdf  # type: ignore[import-not-found]
        except ImportError as exc:
            return f"[opendataloader_pdf unavailable: {exc}]\n"

        stem = Path(source.origin).stem or "document"
        with tempfile.TemporaryDirectory(prefix="odl_pdf_") as tmpdir:
            tmp = Path(tmpdir)
            pdf_path = tmp / f"{stem}.pdf"
            pdf_path.write_bytes(source.content)
            try:
                opendataloader_pdf.convert(
                    input_path=str(pdf_path),
                    output_dir=str(tmp),
                    format="markdown",
                    markdown_page_separator=_MARKDOWN_PAGE_SEPARATOR,
                    quiet=True,
                )
            except Exception as exc:
                log.warning("opendataloader_pdf failed for %s: %s", source.origin, exc)
                return f"[opendataloader_pdf failed: {exc}]\n"

            md_path = tmp / f"{stem}.md"
            if not md_path.exists():
                # opendataloader sometimes nests output one level deep when
                # the input is a directory; fall back to a recursive scan.
                candidates = sorted(tmp.rglob("*.md"))
                if not candidates:
                    return "[opendataloader_pdf produced no markdown]\n"
                md_path = candidates[0]

            text = md_path.read_text(encoding="utf-8", errors="ignore").strip()
            return text + "\n" if text else "\n"

    @staticmethod
    def _guess_title(body: str, source: IngestInput) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped and not _is_non_content_line(stripped):
                return stripped[:120]
        return Path(source.origin).stem


def _is_non_content_line(line: str) -> bool:
    return line.startswith("[opendataloader_pdf") or bool(_PAGE_MARKER_RE.match(line))
