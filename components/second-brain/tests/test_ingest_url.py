from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.url import UrlConverter


_SAMPLE_HTML = b"""<!doctype html>
<html>
  <head><title>Ignore Me \xe2\x80\x94 Site Title</title></head>
  <body>
    <nav>nav junk</nav>
    <article>
      <h1>A Clear Article Title</h1>
      <p>This is the first paragraph of the real article body.</p>
      <p>Second paragraph with more detail.</p>
    </article>
    <footer>footer junk</footer>
  </body>
</html>
"""


def _transport(body: bytes = _SAMPLE_HTML, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status,
            content=body,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    return httpx.MockTransport(handler)


def test_matches_http_origin() -> None:
    c = UrlConverter()
    ok = IngestInput.from_bytes(origin="https://example.com/a", suffix="", content=b"")
    bad = IngestInput.from_bytes(origin="/tmp/a.pdf", suffix=".pdf", content=b"")
    assert c.matches(ok)
    assert not c.matches(bad)


def test_convert_writes_raw_html_and_body(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="https://example.com/a", suffix="", content=b"")
    c = UrlConverter(client=httpx.Client(transport=_transport()))
    artifacts = c.convert(inp, folder)
    assert (folder.raw_dir / "page.html").exists()
    assert (folder.raw_dir / "page.html").read_bytes() == _SAMPLE_HTML
    assert "A Clear Article Title" in artifacts.title_hint
    assert "first paragraph of the real article body" in artifacts.processed_body
    assert artifacts.raw[0].path == "raw/page.html"
    assert artifacts.raw[0].kind == "original"


def test_convert_http_error_raises(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    inp = IngestInput.from_bytes(origin="https://example.com/missing", suffix="", content=b"")
    c = UrlConverter(client=httpx.Client(transport=_transport(status=404)))
    with pytest.raises(RuntimeError, match="status=404"):
        c.convert(inp, folder)
