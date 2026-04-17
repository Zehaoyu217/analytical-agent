from backend.app.integrity.plugins.doc_audit.parser.code_refs import (
    CodeRef,
    extract_code_refs,
)


def test_extracts_path_line_pattern():
    text = "See `backend/app/foo.py:42` for the function."
    refs = extract_code_refs(text)
    matching = [r for r in refs if r.kind == "path_line"]
    assert any(r.path == "backend/app/foo.py" and r.line == 42 for r in matching)


def test_extracts_path_pattern_with_slash_required():
    text = "Open `backend/app/foo.py` and edit it. Also see `bar.py` (no slash, ignored)."
    refs = extract_code_refs(text)
    paths = {r.path for r in refs if r.kind == "path"}
    assert "backend/app/foo.py" in paths
    # bare `bar.py` lacks `/` → not captured as path
    assert "bar.py" not in paths


def test_extracts_qualified_symbol():
    text = "Calls `Module.do_thing` and `pkg.sub.func`."
    refs = extract_code_refs(text)
    syms = {r.symbol for r in refs if r.kind == "symbol"}
    assert "Module.do_thing" in syms
    assert "pkg.sub.func" in syms


def test_skips_fenced_code_blocks():
    text = (
        "Above the fence: `path/foo.py`.\n\n"
        "```python\n"
        "# `path/inside_fence.py` should be skipped\n"
        "```\n\n"
        "Below the fence: `path/bar.py`.\n"
    )
    refs = extract_code_refs(text)
    paths = {r.path for r in refs if r.kind == "path"}
    assert "path/foo.py" in paths
    assert "path/bar.py" in paths
    assert "path/inside_fence.py" not in paths


def test_skips_inline_indented_code_blocks():
    text = "Normal `path/a.py`\n\n    `path/indented.py` is in indented code\n\nAnd `path/b.py`.\n"
    refs = extract_code_refs(text)
    paths = {r.path for r in refs if r.kind == "path"}
    assert "path/a.py" in paths
    assert "path/b.py" in paths
    assert "path/indented.py" not in paths


def test_does_not_match_bare_unqualified_word():
    text = "The word `config` should not match as a symbol candidate."
    refs = extract_code_refs(text)
    syms = {r.symbol for r in refs if r.kind == "symbol"}
    # `config` lacks `.`, so not extracted as a qualified symbol candidate
    assert "config" not in syms


def test_source_line_recorded():
    text = "first line\nsecond `path/x.py:7` line\nthird line\n"
    refs = extract_code_refs(text)
    pl = [r for r in refs if r.kind == "path_line"][0]
    assert pl.source_line == 2
