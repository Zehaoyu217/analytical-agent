from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from .issue import IntegrityIssue
from .schema import GraphSnapshot


@dataclass(frozen=True)
class ScanContext:
    repo_root: Path
    graph: GraphSnapshot


@dataclass(frozen=True)
class ScanResult:
    plugin_name: str
    plugin_version: str
    issues: list[IntegrityIssue] = field(default_factory=list)
    artifacts: list[Path] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@runtime_checkable
class IntegrityPlugin(Protocol):
    name: str
    version: str
    depends_on: tuple[str, ...]
    paths: tuple[str, ...]

    def scan(self, ctx: ScanContext) -> ScanResult: ...
