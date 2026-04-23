from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.harness.research.modules.web import WebModule, _extract_title, _strip_html


def test_strip_html_removes_tags():
    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    result = _strip_html(html)
    assert "Hello world" in result
    assert "<" not in result


def test_strip_html_removes_script_and_style():
    html = (
        "<html><head><style>body{color:red}</style></head>"
        "<body><script>alert(1)</script><p>content</p></body></html>"
    )
    result = _strip_html(html)
    assert "color:red" not in result
    assert "alert" not in result
    assert "content" in result


def test_extract_title():
    html = "<html><head><title>My Page</title></head><body></body></html>"
    assert _extract_title(html) == "My Page"


def test_extract_title_missing():
    assert _extract_title("<html><body>no title</body></html>") == ""


def test_run_skips_on_tiny_budget():
    module = WebModule()
    result = module.run(["https://example.com"], budget_tokens=10)
    assert result.pages == ()


def test_run_fetches_and_strips():
    module = WebModule()
    fake_html = (
        "<html><head><title>Test Page</title></head>"
        "<body><p>Important content here.</p></body></html>"
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_resp):
        result = module.run(["https://example.com/test"], budget_tokens=20_000)

    assert len(result.pages) == 1
    assert result.pages[0].title == "Test Page"
    assert "Important content" in result.pages[0].summary


def test_run_skips_failed_fetch():
    module = WebModule()
    with patch("httpx.get", side_effect=Exception("timeout")):
        result = module.run(["https://example.com"], budget_tokens=20_000)
    assert result.pages == ()


def test_result_is_tuple():
    module = WebModule()
    mock_resp = MagicMock()
    mock_resp.text = "<html><head><title>T</title></head><body>body</body></html>"
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.get", return_value=mock_resp):
        result = module.run(["https://x.com"], budget_tokens=20_000)
    assert isinstance(result.pages, tuple)
