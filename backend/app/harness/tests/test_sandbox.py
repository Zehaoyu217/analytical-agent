from __future__ import annotations

from app.harness.sandbox import SandboxExecutor, SandboxResult


def test_sandbox_runs_simple_expression() -> None:
    sb = SandboxExecutor()
    out = sb.run("x = 2 + 3\nprint(x)")
    assert isinstance(out, SandboxResult)
    assert out.ok is True
    assert "5" in out.stdout
    assert out.stderr == ""
    assert out.returncode == 0


def test_sandbox_reports_error_without_raising() -> None:
    sb = SandboxExecutor()
    out = sb.run("raise ValueError('nope')")
    assert out.ok is False
    assert "ValueError" in out.stderr
    assert "nope" in out.stderr


def test_sandbox_respects_timeout() -> None:
    sb = SandboxExecutor(timeout_sec=1)
    out = sb.run("import time\ntime.sleep(5)\nprint('done')")
    assert out.ok is False
    assert "timeout" in out.stderr.lower() or "killed" in out.stderr.lower()


def test_sandbox_preinjected_globals_available(tmp_path) -> None:
    sb = SandboxExecutor(extra_globals_script="import numpy as np\nimport pandas as pd\n")
    code = "arr = np.array([1,2,3])\nprint('sum', arr.sum())"
    out = sb.run(code)
    assert out.ok is True
    assert "sum 6" in out.stdout
