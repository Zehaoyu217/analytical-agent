"""Eval runner foundation: suite Protocol, cases, reports, dispatcher.

Suites implement the :class:`EvalSuite` protocol: a ``name`` attribute plus a
``run(cfg, fixtures_dir)`` method returning a list of :class:`EvalCase`. The
runner wraps them into a report the CLI can pretty-print or emit as JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from second_brain.config import Config


@dataclass(frozen=True)
class EvalCase:
    """Outcome of a single eval case."""

    name: str
    passed: bool
    metric: float
    details: str = ""


@dataclass(frozen=True)
class EvalReport:
    """Aggregate outcome of running one suite."""

    suite: str
    cases: list[EvalCase] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if every case passed (vacuously true for empty reports)."""
        return all(c.passed for c in self.cases)

    @property
    def pass_rate(self) -> float:
        """Fraction of cases that passed; 0.0 when the suite produced no cases."""
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.passed) / len(self.cases)


@runtime_checkable
class EvalSuite(Protocol):
    """Contract every suite implementation must satisfy."""

    name: str

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]: ...


class EvalRunner:
    """Dispatches a suite name to the matching :class:`EvalSuite` instance."""

    def __init__(self, cfg: Config, suites: dict[str, EvalSuite]) -> None:
        self.cfg = cfg
        self.suites = suites

    def run(self, suite_name: str, fixtures_dir: Path) -> EvalReport:
        if suite_name not in self.suites:
            raise KeyError(f"unknown suite: {suite_name}")
        cases = self.suites[suite_name].run(self.cfg, fixtures_dir)
        return EvalReport(suite=suite_name, cases=cases)
