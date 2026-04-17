from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_LINE_RE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):\s*unused\s+(?P<kind>\w+)\s+'(?P<name>[^']+)'\s+\((?P<conf>\d+)%\s+confidence\)"
)


@dataclass(frozen=True)
class VultureFinding:
    path: str
    line: int
    kind: str
    name: str
    confidence: int


@dataclass(frozen=True)
class VultureResult:
    findings: list[VultureFinding] = field(default_factory=list)
    failure_message: str = ""


def parse_vulture_output(text: str) -> list[VultureFinding]:
    out: list[VultureFinding] = []
    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        out.append(
            VultureFinding(
                path=m.group("path"),
                line=int(m.group("line")),
                kind=m.group("kind"),
                name=m.group("name"),
                confidence=int(m.group("conf")),
            )
        )
    return out


def run_vulture(
    target: Path, *, min_confidence: int, vulture_bin: str = "vulture"
) -> VultureResult:
    cmd = [vulture_bin, str(target), "--min-confidence", str(min_confidence)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    except FileNotFoundError as exc:
        return VultureResult(failure_message=f"vulture binary not found: {vulture_bin} ({exc})")
    except subprocess.TimeoutExpired:
        return VultureResult(failure_message="vulture timed out after 120s")

    # vulture exits 0 if no findings, 3 if findings present. Other codes = error.
    if proc.returncode not in (0, 3):
        stderr = proc.stderr.strip()
        return VultureResult(failure_message=f"vulture exited {proc.returncode}: {stderr}")

    return VultureResult(findings=parse_vulture_output(proc.stdout))
