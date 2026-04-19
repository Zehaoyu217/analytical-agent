"""Tests for dead_directive_cleanup fixer."""
from __future__ import annotations

from pathlib import Path

from app.integrity.plugins.autofix.fixers.dead_directive_cleanup import propose
from app.integrity.plugins.autofix.loader import SiblingArtifacts


def _artifacts(directives: list[dict]) -> SiblingArtifacts:
    issues = [
        {"rule": "lint.dead_directive",
         "evidence": d, "severity": "INFO",
         "node_id": f"{d['path']}:{d['line']}",
         "location": d["path"], "message": "dead",
         "fix_class": None, "first_seen": ""}
        for d in directives
    ]
    return SiblingArtifacts(
        doc_audit={}, config_registry={},
        graph_lint={"plugin": "graph_lint", "issues": issues},
        aggregate={}, failures={},
    )


def test_no_dead_directives_returns_empty(tmp_path: Path) -> None:
    artifacts = _artifacts([])
    assert propose(artifacts, tmp_path, {}) == []


def test_strips_python_noqa_when_directive_only(tmp_path: Path) -> None:
    f = tmp_path / "src" / "x.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("import os  # noqa: F401\nprint('hi')\n")

    artifacts = _artifacts([
        {"path": "src/x.py", "line": 1, "language": "python",
         "rule_code": "F401", "directive_kind": "noqa"},
    ])
    diffs = propose(artifacts, tmp_path, {})
    assert len(diffs) == 1
    assert diffs[0].new_content == "import os\nprint('hi')\n"


def test_strips_eslint_disable_next_line(tmp_path: Path) -> None:
    f = tmp_path / "src" / "x.ts"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "// eslint-disable-next-line react/no-unused-vars\n"
        "const x = 1;\n"
    )
    artifacts = _artifacts([
        {"path": "src/x.ts", "line": 1, "language": "typescript",
         "rule_code": "react/no-unused-vars", "directive_kind": "eslint-disable-next-line"},
    ])
    diffs = propose(artifacts, tmp_path, {})
    assert len(diffs) == 1
    assert "eslint-disable" not in diffs[0].new_content
    assert diffs[0].new_content == "const x = 1;\n"


def test_skips_unknown_rule_code(tmp_path: Path) -> None:
    f = tmp_path / "src" / "x.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x = 1  # noqa: WEIRD123\n")

    artifacts = _artifacts([
        {"path": "src/x.py", "line": 1, "language": "python",
         "rule_code": "WEIRD123", "directive_kind": "noqa"},
    ])
    diffs = propose(artifacts, tmp_path, {"known_codes": ["F401", "E501"]})
    assert diffs == []


def test_groups_multiple_directives_per_file(tmp_path: Path) -> None:
    f = tmp_path / "src" / "x.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "import a  # noqa: F401\n"
        "import b  # noqa: F401\n"
    )
    artifacts = _artifacts([
        {"path": "src/x.py", "line": 1, "language": "python",
         "rule_code": "F401", "directive_kind": "noqa"},
        {"path": "src/x.py", "line": 2, "language": "python",
         "rule_code": "F401", "directive_kind": "noqa"},
    ])
    diffs = propose(artifacts, tmp_path, {})
    assert len(diffs) == 1
    assert diffs[0].new_content == "import a\nimport b\n"
