from __future__ import annotations

from typing import ClassVar

import httpx

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder


class UrlConverter(Converter):
    kind: ClassVar[str] = "url"

    def __init__(self, client: httpx.Client | None = None, *, timeout: float = 30.0) -> None:
        self._client = client
        self._timeout = timeout

    def matches(self, source: IngestInput) -> bool:
        origin = source.origin or ""
        return origin.startswith("http://") or origin.startswith("https://")

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        html = self._fetch(source.origin)
        raw_write = target.write_raw(
            rel_path="raw/page.html",
            content=html,
            kind="original",
        )
        title, body_md = self._extract_article(html)
        return SourceArtifacts(
            processed_body=body_md if body_md.endswith("\n") else body_md + "\n",
            raw=[raw_write],
            title_hint=title,
        )

    def _fetch(self, url: str) -> bytes:
        client = self._client or httpx.Client(timeout=self._timeout, follow_redirects=True)
        try:
            resp = client.get(url)
        finally:
            if self._client is None:
                client.close()
        if resp.status_code >= 400:
            raise RuntimeError(f"url fetch failed: status={resp.status_code} url={url}")
        return resp.content

    @staticmethod
    def _extract_article(html: bytes) -> tuple[str, str]:
        try:
            from readability import Document  # type: ignore[import-not-found]

            doc = Document(html.decode("utf-8", errors="replace"))
            summary_html = doc.summary(html_partial=True)
            body = _html_to_text(summary_html)
            title = _extract_h1(summary_html) or (doc.short_title() or doc.title() or "").strip()
            return title or "untitled", body
        except Exception as exc:  # noqa: BLE001
            return "untitled", f"[readability failed: {exc}]\n"


def _extract_h1(fragment: str) -> str | None:
    try:
        from lxml import html as lxml_html  # type: ignore[import-not-found]

        root = lxml_html.fromstring(fragment)
        for el in root.iter("h1"):
            text = (el.text_content() or "").strip()
            if text:
                return text
        return None
    except Exception:  # noqa: BLE001
        return None


def _html_to_text(fragment: str) -> str:
    # Tiny fallback: strip tags by collapsing with lxml if available, else regex.
    try:
        from lxml import html as lxml_html  # type: ignore[import-not-found]

        root = lxml_html.fromstring(fragment)
        parts: list[str] = []
        for el in root.iter():
            text = (el.text or "").strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts).strip() + "\n"
    except Exception:  # noqa: BLE001
        import re

        stripped = re.sub(r"<[^>]+>", " ", fragment)
        return " ".join(stripped.split()).strip() + "\n"
