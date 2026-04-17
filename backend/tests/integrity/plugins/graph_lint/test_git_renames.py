

from backend.app.integrity.plugins.graph_lint.git_renames import (
    parse_renames,
    recent_renames,
)

SAMPLE = """\
R100\told/path.py\tnew/path.py
R092\tfrontend/src/old.tsx\tfrontend/src/renamed.tsx
"""


def test_parse_extracts_old_to_new():
    renames = parse_renames(SAMPLE)
    assert renames == {
        "old/path.py": "new/path.py",
        "frontend/src/old.tsx": "frontend/src/renamed.tsx",
    }


def test_parse_handles_empty_input():
    assert parse_renames("") == {}


def test_recent_renames_swallows_subprocess_error(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    out = recent_renames(tmp_path, since="1.day.ago", git_bin="definitely_not_git")
    assert out == {}
