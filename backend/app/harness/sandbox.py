from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 60


@dataclass(frozen=True, slots=True)
class SandboxResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int
    duration_sec: float


class SandboxExecutor:
    def __init__(
        self,
        python_executable: str | None = None,
        timeout_sec: int = DEFAULT_TIMEOUT,
        extra_globals_script: str = "",
        cwd: str | Path | None = None,
    ) -> None:
        self._python = python_executable or sys.executable
        self._timeout = timeout_sec
        self._extra = extra_globals_script
        self._cwd = Path(cwd) if cwd else None

    def _wrap(self, user_code: str) -> str:
        header = self._extra.rstrip() + "\n" if self._extra else ""
        return header + textwrap.dedent(user_code)

    def run(self, code: str) -> SandboxResult:
        wrapped = self._wrap(code)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(wrapped)
            f.flush()
            path = f.name
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [self._python, path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(self._cwd) if self._cwd else None,
                check=False,
            )
            duration = time.monotonic() - start
            return SandboxResult(
                ok=(proc.returncode == 0),
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                duration_sec=duration,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start
            return SandboxResult(
                ok=False,
                stdout=e.stdout or "",
                stderr=f"timeout after {self._timeout}s\n{e.stderr or ''}",
                returncode=-1,
                duration_sec=duration,
            )
        finally:
            Path(path).unlink(missing_ok=True)
