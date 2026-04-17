from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from backend.app.integrity.plugins.graph_lint.wrappers.vulture import (
    VultureFinding,
    parse_vulture_output,
    run_vulture,
)

SAMPLE_OUTPUT = """\
backend/app/x.py:10: unused function 'old_helper' (90% confidence)
backend/app/y.py:42: unused variable '_unused' (60% confidence)
"""


def test_parse_extracts_findings():
    findings = parse_vulture_output(SAMPLE_OUTPUT)
    assert len(findings) == 2
    assert findings[0] == VultureFinding(
        path="backend/app/x.py", line=10, kind="function", name="old_helper", confidence=90
    )
    assert findings[1].confidence == 60


def test_parse_skips_garbage_lines():
    out = "Hello there\nbackend/app/x.py:10: unused function 'old' (90% confidence)\n"
    findings = parse_vulture_output(out)
    assert len(findings) == 1


def test_run_vulture_handles_missing_binary(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    result = run_vulture(tmp_path / "app", min_confidence=80, vulture_bin="definitely_not_a_binary")
    assert result.findings == []
    assert "definitely_not_a_binary" in result.failure_message


def test_run_vulture_executes_real_binary(tmp_path: Path):
    # Write a tiny module with one obvious unused
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def used():\n    return 1\n\n"
        "def _unused_priv():\n    return 2\n\n"
        "used()\n"
    )
    try:
        subprocess.run(["vulture", "--version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("vulture not installed")
    result = run_vulture(pkg, min_confidence=60)
    assert result.failure_message == ""
    names = {f.name for f in result.findings}
    assert "_unused_priv" in names or any("unused" in f.name for f in result.findings)
