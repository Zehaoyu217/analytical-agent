# Eval-Failure Response SOP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Eval-Failure Response SOP — manual-triggered triage + fix-ladder playbook (Scope A) plus 4 DevTools monitoring views (Scope B) per `docs/superpowers/specs/2026-04-12-eval-failure-sop-design.md`.

**Architecture:** Backend Python package `app/sop/` owns data contracts (FailureReport, baseline, iteration log), triage logic (pre-flight buckets 7–9 → main triage buckets 1–6), and 9 ladder YAML files. `/sop <level>` is a Claude command that reads the latest FailureReport, runs triage, proposes a fix from the matching ladder, and writes an iteration log entry after the fix is applied. REST API `/api/sop/*` surfaces the data to 4 React DevTools views.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, PyYAML, pytest, pytest-asyncio, frozen dataclasses, ruff, mypy --strict. Frontend: React+Vite+TypeScript strict, Zustand, existing DevTools panel pattern.

**File layout target:**
```
backend/app/sop/
  __init__.py
  types.py                     # Pydantic models: FailureReport, Baseline, IterationLogEntry, LadderDefinition
  reporter.py                  # Writes FailureReport from EvalResult + AgentTrace
  baseline.py                  # Read/write baseline snapshots
  log.py                       # Read/write iteration log entries
  ladders/
    01-context.yaml ... 09-determinism.yaml
  ladder_loader.py             # Loads ladder YAMLs into LadderDefinition
  preflight.py                 # Runs buckets 7, 8, 9
  triage.py                    # Runs buckets 1–6 (cost-ordered, stop-at-first)
  autonomy.py                  # Reads .superpowers/sop-autonomy.yaml, graduation check
  runner.py                    # Orchestrator: read FailureReport → preflight → triage → render proposal
backend/app/api/sop_api.py     # REST endpoints
backend/tests/sop/
  test_types.py, test_reporter.py, test_baseline.py, test_log.py,
  test_ladder_loader.py, test_preflight.py, test_triage.py,
  test_autonomy.py, test_runner.py, test_sop_api.py
frontend/src/devtools/sop/
  SessionReplay.tsx, JudgeVariance.tsx, PromptInspector.tsx, CompactionTimeline.tsx, api.ts
```

---

## Task 1: Define Pydantic models for FailureReport, Baseline, IterationLogEntry

**Files:**
- Create: `backend/app/sop/__init__.py`
- Create: `backend/app/sop/types.py`
- Test:   `backend/tests/sop/__init__.py`
- Test:   `backend/tests/sop/test_types.py`

- [ ] **Step 1: Create empty package inits**

```bash
mkdir -p backend/app/sop backend/tests/sop
touch backend/app/sop/__init__.py backend/tests/sop/__init__.py
```

- [ ] **Step 2: Write failing test `test_types.py`**

```python
# backend/tests/sop/test_types.py
"""Tests for SOP Pydantic models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.sop.types import (
    Baseline,
    DiffVsBaseline,
    DimensionScore,
    FailureReport,
    FixApplied,
    IterationLogEntry,
    PreflightResult,
    Signals,
    TriageDecision,
)


def test_signals_required_fields() -> None:
    s = Signals(
        token_count=18400,
        duration_ms=47200,
        compaction_events=3,
        scratchpad_writes=0,
        tool_errors=1,
        retries=0,
        subagents_spawned=0,
        models_used={"haiku": 12, "sonnet": 0},
    )
    assert s.scratchpad_writes == 0
    assert s.models_used["haiku"] == 12


def test_failure_report_roundtrip() -> None:
    fr = FailureReport(
        level=3,
        overall_grade="C",
        dimensions=[DimensionScore(name="detection_recall", score="B", weight=0.3)],
        signals=Signals(
            token_count=100, duration_ms=10, compaction_events=0,
            scratchpad_writes=0, tool_errors=0, retries=0,
            subagents_spawned=0, models_used={},
        ),
        judge_justifications={"detection_recall": "ok"},
        top_failure_signature="missed_anomaly",
        trace_id="eval-x",
        trace_path="path/to/trace.json",
        diff_vs_baseline=None,
    )
    dumped = fr.model_dump()
    restored = FailureReport.model_validate(dumped)
    assert restored == fr


def test_failure_report_invalid_grade_rejected() -> None:
    with pytest.raises(ValidationError):
        FailureReport(
            level=3, overall_grade="Z",  # invalid
            dimensions=[], signals=Signals(
                token_count=0, duration_ms=0, compaction_events=0,
                scratchpad_writes=0, tool_errors=0, retries=0,
                subagents_spawned=0, models_used={},
            ),
            judge_justifications={}, top_failure_signature="x",
            trace_id="x", trace_path="x", diff_vs_baseline=None,
        )


def test_baseline_minimum_fields() -> None:
    b = Baseline(
        level=3, date="2026-04-10", trace_id="eval-y",
        signals=Signals(
            token_count=12800, duration_ms=30000, compaction_events=1,
            scratchpad_writes=8, tool_errors=0, retries=0,
            subagents_spawned=2, models_used={"sonnet": 3, "haiku": 5},
        ),
    )
    assert b.level == 3


def test_diff_vs_baseline_shape() -> None:
    d = DiffVsBaseline(
        baseline_date="2026-04-10",
        baseline_grade="B",
        changes={"scratchpad_writes": {"before": 8, "after": 0}},
    )
    assert d.changes["scratchpad_writes"]["before"] == 8


def test_iteration_log_entry_minimum() -> None:
    e = IterationLogEntry(
        date="2026-04-12",
        session_id="2026-04-12-level3-001",
        level=3,
        overall_grade_before="C",
        preflight=PreflightResult(evaluation_bias="pass", data_quality="pass", determinism="pass"),
        triage=TriageDecision(bucket="context", evidence=["x"], hypothesis="y"),
        fix=FixApplied(ladder_id="context-01", name="z", files_changed=["a"], model_used_for_fix="sonnet", cost_bucket="trivial"),
        outcome={"grade_after": "B", "regressions": "none", "iterations": 1, "success": True},
        trace_links={"before": "a.json", "after": "b.json"},
    )
    assert e.triage.bucket == "context"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sop.types'`

- [ ] **Step 4: Implement `app/sop/types.py`**

```python
# backend/app/sop/types.py
"""Pydantic models for SOP data contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Grade = Literal["A", "B", "C", "F"]
PreflightVerdict = Literal["pass", "fail", "skipped"]
CostBucket = Literal["trivial", "small", "medium", "large"]


class Signals(BaseModel):
    model_config = ConfigDict(frozen=True)

    token_count: int
    duration_ms: int
    compaction_events: int
    scratchpad_writes: int
    tool_errors: int
    retries: int
    subagents_spawned: int
    models_used: dict[str, int]


class DimensionScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    score: Grade
    weight: float = Field(ge=0.0, le=1.0)


class DiffVsBaseline(BaseModel):
    model_config = ConfigDict(frozen=True)

    baseline_date: str
    baseline_grade: Grade
    changes: dict[str, dict[str, Any]]  # {field_name: {"before": X, "after": Y, ...}}


class FailureReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: int = Field(ge=1, le=5)
    overall_grade: Grade
    dimensions: list[DimensionScore]
    signals: Signals
    judge_justifications: dict[str, str]
    top_failure_signature: str
    trace_id: str
    trace_path: str
    diff_vs_baseline: DiffVsBaseline | None


class Baseline(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: int = Field(ge=1, le=5)
    date: str
    trace_id: str
    signals: Signals


class PreflightResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    evaluation_bias: PreflightVerdict
    data_quality: PreflightVerdict
    determinism: PreflightVerdict

    def any_failed(self) -> bool:
        return "fail" in (self.evaluation_bias, self.data_quality, self.determinism)


class TriageDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    bucket: str
    evidence: list[str]
    hypothesis: str


class FixApplied(BaseModel):
    model_config = ConfigDict(frozen=True)

    ladder_id: str
    name: str
    files_changed: list[str]
    model_used_for_fix: str
    cost_bucket: CostBucket


class IterationLogEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: str
    session_id: str
    level: int = Field(ge=1, le=5)
    overall_grade_before: Grade
    preflight: PreflightResult
    triage: TriageDecision
    fix: FixApplied
    outcome: dict[str, Any]
    trace_links: dict[str, str]


class LadderRung(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    cost: CostBucket
    files: list[str]
    pattern: str | None = None


class LadderDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    bucket: str
    description: str
    triage_signals: list[str]
    ladder: list[LadderRung]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_types.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/sop/__init__.py backend/app/sop/types.py backend/tests/sop/__init__.py backend/tests/sop/test_types.py
git commit -m "feat: add SOP Pydantic models for failure report, baseline, and iteration log"
```

---

## Task 2: Baseline read/write module

**Files:**
- Create: `backend/app/sop/baseline.py`
- Test:   `backend/tests/sop/test_baseline.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_baseline.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.sop.baseline import load_baseline, should_update_baseline, update_baseline
from app.sop.types import Baseline, Signals


@pytest.fixture
def baselines_dir(tmp_path: Path) -> Path:
    d = tmp_path / "baselines"
    d.mkdir()
    return d


def _sample(level: int, writes: int) -> Baseline:
    return Baseline(
        level=level, date="2026-04-10", trace_id="t",
        signals=Signals(
            token_count=100, duration_ms=10, compaction_events=0,
            scratchpad_writes=writes, tool_errors=0, retries=0,
            subagents_spawned=0, models_used={},
        ),
    )


def test_load_missing_baseline_returns_none(baselines_dir: Path) -> None:
    assert load_baseline(3, baselines_dir) is None


def test_roundtrip_update_and_load(baselines_dir: Path) -> None:
    b = _sample(3, 8)
    update_baseline(b, baselines_dir)
    loaded = load_baseline(3, baselines_dir)
    assert loaded == b


def test_should_update_when_target_improved_no_regression() -> None:
    prior = {1: "B", 2: "B", 3: "C", 4: "B", 5: "B"}
    new = {1: "B", 2: "B", 3: "B", 4: "B", 5: "B"}
    assert should_update_baseline(target_level=3, prior_grades=prior, new_grades=new)


def test_should_not_update_when_regression_on_other_level() -> None:
    prior = {1: "B", 2: "B", 3: "C", 4: "B", 5: "B"}
    new = {1: "B", 2: "B", 3: "B", 4: "C", 5: "B"}  # L4 regressed
    assert not should_update_baseline(target_level=3, prior_grades=prior, new_grades=new)


def test_should_not_update_when_target_below_B() -> None:
    prior = {1: "B", 2: "B", 3: "C", 4: "B", 5: "B"}
    new = {1: "B", 2: "B", 3: "C", 4: "B", 5: "B"}
    assert not should_update_baseline(target_level=3, prior_grades=prior, new_grades=new)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_baseline.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement `app/sop/baseline.py`**

```python
# backend/app/sop/baseline.py
"""Read/write baseline snapshots for eval levels."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.sop.types import Baseline, Grade

GRADE_ORDER: dict[Grade, int] = {"A": 3, "B": 2, "C": 1, "F": 0}


def _baseline_path(level: int, baselines_dir: Path) -> Path:
    return baselines_dir / f"level{level}.yaml"


def load_baseline(level: int, baselines_dir: Path) -> Baseline | None:
    """Return the last-passing baseline for the given level, or None if missing."""
    path = _baseline_path(level, baselines_dir)
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text())
    return Baseline.model_validate(data)


def update_baseline(baseline: Baseline, baselines_dir: Path) -> None:
    """Write baseline YAML for its level."""
    baselines_dir.mkdir(parents=True, exist_ok=True)
    path = _baseline_path(baseline.level, baselines_dir)
    path.write_text(yaml.safe_dump(baseline.model_dump(), sort_keys=False))


def should_update_baseline(
    target_level: int,
    prior_grades: dict[int, Grade],
    new_grades: dict[int, Grade],
) -> bool:
    """True iff target_level is >= B and no other level regressed."""
    target_new = new_grades.get(target_level)
    if target_new is None or GRADE_ORDER[target_new] < GRADE_ORDER["B"]:
        return False
    if GRADE_ORDER[target_new] <= GRADE_ORDER.get(prior_grades.get(target_level, "F"), 0):
        return False
    for lvl, prior in prior_grades.items():
        if lvl == target_level:
            continue
        if GRADE_ORDER[new_grades.get(lvl, "F")] < GRADE_ORDER[prior]:
            return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_baseline.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/sop/baseline.py backend/tests/sop/test_baseline.py
git commit -m "feat: add SOP baseline snapshot read/write"
```

---

## Task 3: Iteration log read/write module

**Files:**
- Create: `backend/app/sop/log.py`
- Test:   `backend/tests/sop/test_log.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_log.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.sop.log import list_entries, next_session_id, read_entry, write_entry
from app.sop.types import (
    FixApplied,
    IterationLogEntry,
    PreflightResult,
    TriageDecision,
)


def _entry(session_id: str, level: int = 3, bucket: str = "context") -> IterationLogEntry:
    return IterationLogEntry(
        date=session_id[:10],
        session_id=session_id,
        level=level,
        overall_grade_before="C",
        preflight=PreflightResult(evaluation_bias="pass", data_quality="pass", determinism="pass"),
        triage=TriageDecision(bucket=bucket, evidence=["e"], hypothesis="h"),
        fix=FixApplied(
            ladder_id=f"{bucket}-01", name="n", files_changed=["f"],
            model_used_for_fix="sonnet", cost_bucket="trivial",
        ),
        outcome={"grade_after": "B", "regressions": "none", "iterations": 1, "success": True},
        trace_links={"before": "a.json", "after": "b.json"},
    )


def test_next_session_id_starts_at_001(tmp_path: Path) -> None:
    assert next_session_id(tmp_path, level=3, date="2026-04-12") == "2026-04-12-level3-001"


def test_next_session_id_increments(tmp_path: Path) -> None:
    write_entry(_entry("2026-04-12-level3-001"), tmp_path)
    write_entry(_entry("2026-04-12-level3-002"), tmp_path)
    assert next_session_id(tmp_path, level=3, date="2026-04-12") == "2026-04-12-level3-003"


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    entry = _entry("2026-04-12-level3-001")
    write_entry(entry, tmp_path)
    loaded = read_entry("2026-04-12-level3-001", tmp_path)
    assert loaded == entry


def test_list_entries_sorted(tmp_path: Path) -> None:
    write_entry(_entry("2026-04-12-level3-002"), tmp_path)
    write_entry(_entry("2026-04-12-level3-001"), tmp_path)
    sids = [e.session_id for e in list_entries(tmp_path)]
    assert sids == ["2026-04-12-level3-001", "2026-04-12-level3-002"]


def test_read_missing_entry_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_entry("2026-04-12-level3-999", tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_log.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement `app/sop/log.py`**

```python
# backend/app/sop/log.py
"""Read/write iteration log entries."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.sop.types import IterationLogEntry


def _entry_path(session_id: str, log_dir: Path) -> Path:
    # session_id shape: YYYY-MM-DD-levelN-NNN
    return log_dir / f"{session_id}.yaml"


def write_entry(entry: IterationLogEntry, log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = _entry_path(entry.session_id, log_dir)
    path.write_text(yaml.safe_dump(entry.model_dump(), sort_keys=False))
    return path


def read_entry(session_id: str, log_dir: Path) -> IterationLogEntry:
    path = _entry_path(session_id, log_dir)
    if not path.exists():
        raise FileNotFoundError(f"No log entry at {path}")
    data = yaml.safe_load(path.read_text())
    return IterationLogEntry.model_validate(data)


def list_entries(log_dir: Path) -> list[IterationLogEntry]:
    if not log_dir.exists():
        return []
    entries = []
    for path in sorted(log_dir.glob("*.yaml")):
        entries.append(IterationLogEntry.model_validate(yaml.safe_load(path.read_text())))
    return entries


def next_session_id(log_dir: Path, level: int, date: str) -> str:
    prefix = f"{date}-level{level}-"
    if not log_dir.exists():
        return f"{prefix}001"
    existing = sorted(
        int(p.stem.rsplit("-", 1)[1])
        for p in log_dir.glob(f"{prefix}*.yaml")
    )
    n = (existing[-1] + 1) if existing else 1
    return f"{prefix}{n:03d}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_log.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/sop/log.py backend/tests/sop/test_log.py
git commit -m "feat: add SOP iteration log read/write"
```

---

## Task 4: FailureReport builder (reporter.py)

**Files:**
- Create: `backend/app/sop/reporter.py`
- Test:   `backend/tests/sop/test_reporter.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_reporter.py
from __future__ import annotations

from pathlib import Path

from app.evals.types import AgentTrace, DimensionGrade, LevelResult
from app.sop.baseline import update_baseline
from app.sop.reporter import build_failure_report, write_failure_report
from app.sop.types import Baseline, Signals


def _trace() -> AgentTrace:
    return AgentTrace(
        queries=["SELECT 1"],
        intermediate=[
            {"kind": "tool_call", "name": "sql"},
            {"kind": "compaction"},
            {"kind": "compaction"},
            {"kind": "compaction"},
            {"kind": "tool_error", "error": "timeout"},
        ],
        final_output="...",
        token_count=18400,
        duration_ms=47200,
        errors=["timeout"],
    )


def _level_result() -> LevelResult:
    return LevelResult(
        level=3,
        name="anomaly",
        dimensions=[
            DimensionGrade(name="detection_recall", grade="B", score=0.7, weight=0.3, justification="ok"),
            DimensionGrade(name="false_positive_handling", grade="F", score=0.0, weight=0.3, justification="flagged bonus"),
        ],
        weighted_score=0.35,
        grade="C",
    )


def test_build_failure_report_extracts_signals() -> None:
    fr = build_failure_report(
        level_result=_level_result(),
        trace=_trace(),
        trace_id="eval-x",
        trace_path="traces/eval-x.json",
        baseline=None,
    )
    assert fr.level == 3
    assert fr.overall_grade == "C"
    assert fr.signals.compaction_events == 3
    assert fr.signals.tool_errors == 1
    assert fr.signals.token_count == 18400
    assert fr.top_failure_signature  # non-empty


def test_build_failure_report_computes_diff(tmp_path: Path) -> None:
    baseline = Baseline(
        level=3, date="2026-04-10", trace_id="prior",
        signals=Signals(
            token_count=12800, duration_ms=30000, compaction_events=1,
            scratchpad_writes=8, tool_errors=0, retries=0,
            subagents_spawned=2, models_used={"sonnet": 3, "haiku": 5},
        ),
    )
    update_baseline(baseline, tmp_path)
    fr = build_failure_report(
        level_result=_level_result(),
        trace=_trace(),
        trace_id="eval-x",
        trace_path="traces/eval-x.json",
        baseline=baseline,
    )
    assert fr.diff_vs_baseline is not None
    assert fr.diff_vs_baseline.changes["token_count"]["before"] == 12800
    assert fr.diff_vs_baseline.changes["token_count"]["after"] == 18400
    assert fr.diff_vs_baseline.changes["scratchpad_writes"]["before"] == 8
    assert fr.diff_vs_baseline.changes["scratchpad_writes"]["after"] == 0


def test_write_failure_report_yaml(tmp_path: Path) -> None:
    fr = build_failure_report(
        level_result=_level_result(), trace=_trace(),
        trace_id="eval-x", trace_path="x.json", baseline=None,
    )
    path = write_failure_report(fr, tmp_path, date="2026-04-12")
    assert path.exists()
    assert path.name == "2026-04-12-level3.yaml"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_reporter.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement `app/sop/reporter.py`**

```python
# backend/app/sop/reporter.py
"""Build and persist FailureReport from eval output."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from app.evals.types import AgentTrace, LevelResult
from app.sop.types import (
    Baseline,
    DiffVsBaseline,
    DimensionScore,
    FailureReport,
    Signals,
)


def _extract_signals(trace: AgentTrace) -> Signals:
    kinds: Counter[str] = Counter()
    models: Counter[str] = Counter()
    for step in trace.intermediate:
        if isinstance(step, dict):
            kind = step.get("kind", "")
            kinds[kind] += 1
            if kind == "tool_call" and (model := step.get("model")):
                models[model] += 1
    return Signals(
        token_count=trace.token_count,
        duration_ms=trace.duration_ms,
        compaction_events=kinds.get("compaction", 0),
        scratchpad_writes=kinds.get("scratchpad_write", 0),
        tool_errors=kinds.get("tool_error", 0),
        retries=kinds.get("retry", 0),
        subagents_spawned=kinds.get("subagent_spawn", 0),
        models_used=dict(models),
    )


def _failure_signature(level_result: LevelResult) -> str:
    worst = min(level_result.dimensions, key=lambda d: d.score)
    return f"{worst.name}__{worst.grade}"


def _compute_diff(current: Signals, baseline: Baseline) -> DiffVsBaseline:
    before = baseline.signals.model_dump()
    after = current.model_dump()
    changes: dict[str, dict[str, Any]] = {}
    for key, b_val in before.items():
        a_val = after.get(key)
        if b_val != a_val:
            entry: dict[str, Any] = {"before": b_val, "after": a_val}
            if isinstance(b_val, int) and isinstance(a_val, int) and b_val > 0:
                entry["delta_pct"] = round((a_val - b_val) / b_val * 100, 2)
            changes[key] = entry
    # Baseline grade is the last-passing; by construction it is >= B.
    return DiffVsBaseline(baseline_date=baseline.date, baseline_grade="B", changes=changes)


def build_failure_report(
    *,
    level_result: LevelResult,
    trace: AgentTrace,
    trace_id: str,
    trace_path: str,
    baseline: Baseline | None,
) -> FailureReport:
    signals = _extract_signals(trace)
    dims = [
        DimensionScore(name=d.name, score=d.grade, weight=d.weight)
        for d in level_result.dimensions
    ]
    justifications = {d.name: d.justification for d in level_result.dimensions}
    diff = _compute_diff(signals, baseline) if baseline else None
    return FailureReport(
        level=level_result.level,
        overall_grade=level_result.grade,
        dimensions=dims,
        signals=signals,
        judge_justifications=justifications,
        top_failure_signature=_failure_signature(level_result),
        trace_id=trace_id,
        trace_path=trace_path,
        diff_vs_baseline=diff,
    )


def write_failure_report(report: FailureReport, reports_dir: Path, *, date: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{date}-level{report.level}.yaml"
    path.write_text(yaml.safe_dump(report.model_dump(), sort_keys=False))
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_reporter.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/sop/reporter.py backend/tests/sop/test_reporter.py
git commit -m "feat: add SOP FailureReport builder with diff-vs-baseline"
```

---

## Task 5: Ladder YAML files for all 9 buckets + loader

**Files:**
- Create: `backend/app/sop/ladders/01-context.yaml`
- Create: `backend/app/sop/ladders/02-prompt.yaml`
- Create: `backend/app/sop/ladders/03-capability.yaml`
- Create: `backend/app/sop/ladders/04-routing.yaml`
- Create: `backend/app/sop/ladders/05-architecture.yaml`
- Create: `backend/app/sop/ladders/06-harness.yaml`
- Create: `backend/app/sop/ladders/07-evaluation-bias.yaml`
- Create: `backend/app/sop/ladders/08-data-quality.yaml`
- Create: `backend/app/sop/ladders/09-determinism.yaml`
- Create: `backend/app/sop/ladder_loader.py`
- Test:   `backend/tests/sop/test_ladder_loader.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_ladder_loader.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.sop.ladder_loader import load_all_ladders, load_ladder

EXPECTED_BUCKETS = {
    "context", "prompt", "capability", "routing", "architecture", "harness",
    "evaluation_bias", "data_quality", "determinism",
}


def test_load_all_ladders_covers_nine_buckets() -> None:
    ladders = load_all_ladders()
    assert {l.bucket for l in ladders} == EXPECTED_BUCKETS


def test_each_ladder_has_at_least_three_rungs() -> None:
    for l in load_all_ladders():
        assert len(l.ladder) >= 3, f"bucket {l.bucket} has fewer than 3 rungs"


def test_ladder_rung_ids_are_prefixed_by_bucket() -> None:
    for l in load_all_ladders():
        for rung in l.ladder:
            assert rung.id.startswith(l.bucket.replace("_", "-")), rung.id


def test_load_ladder_by_bucket() -> None:
    ladder = load_ladder("context")
    assert ladder.bucket == "context"
    assert ladder.ladder[0].cost == "trivial"


def test_load_ladder_unknown_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_ladder("no_such_bucket")


def test_ladders_sorted_by_cost() -> None:
    order = {"trivial": 0, "small": 1, "medium": 2, "large": 3}
    for l in load_all_ladders():
        costs = [order[r.cost] for r in l.ladder]
        assert costs == sorted(costs), f"ladder {l.bucket} not cost-ordered: {costs}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_ladder_loader.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create ladder YAML files**

```yaml
# backend/app/sop/ladders/01-context.yaml
bucket: context
description: "Compaction loss, scratchpad misuse, stale layers"
triage_signals:
  - "scratchpad_writes == 0 when tool_calls > 5"
  - "compaction_events >= 3 in a single session"
  - "token_count > 1.5x baseline"
ladder:
  - id: context-01
    name: "Lower compaction threshold"
    cost: trivial
    files: ["backend/app/context/manager.py"]
    pattern: "COMPACTION_THRESHOLD = 0.80 -> 0.70"
  - id: context-02
    name: "Force scratchpad write on every tool return"
    cost: small
    files: ["backend/app/context/manager.py"]
  - id: context-03
    name: "Add L2_skill layer pruning before compaction"
    cost: medium
    files: ["backend/app/context/manager.py", "backend/app/context/compaction.py"]
  - id: context-04
    name: "Replace flat context with hierarchical summarization"
    cost: large
    files: ["backend/app/context/**"]
```

```yaml
# backend/app/sop/ladders/02-prompt.yaml
bucket: prompt
description: "System-prompt contradictions, missing guidance, misleading framing"
triage_signals:
  - "Agent consistently ignores one directive"
  - "Judge justifications reference missing guidance"
  - "Two prompt sources contain opposing directives"
ladder:
  - id: prompt-01
    name: "Remove conflicting directive from assembled prompt"
    cost: trivial
    files: ["backend/app/prompts/system.md"]
  - id: prompt-02
    name: "Add explicit guidance for failing behavior"
    cost: small
    files: ["backend/app/prompts/system.md"]
  - id: prompt-03
    name: "Restructure prompt assembly ordering"
    cost: medium
    files: ["backend/app/prompts/assembler.py"]
```

```yaml
# backend/app/sop/ladders/03-capability.yaml
bucket: capability
description: "Skill instructions unclear, missing Python helpers, skill too bloated"
triage_signals:
  - "Skill invoked but produces wrong output"
  - "Skill token cost > 30% of session"
  - "Same skill retried multiple times in trace"
ladder:
  - id: capability-01
    name: "Tighten SKILL.md instructions for failing skill"
    cost: trivial
    files: ["backend/app/skills/<skill>/SKILL.md"]
  - id: capability-02
    name: "Add Python helper to skill package for common operation"
    cost: small
    files: ["backend/app/skills/<skill>/pkg/"]
  - id: capability-03
    name: "Split bloated skill into two focused skills"
    cost: medium
    files: ["backend/app/skills/<skill>/"]
```

```yaml
# backend/app/sop/ladders/04-routing.yaml
bucket: routing
description: "Wrong model for the job"
triage_signals:
  - "Haiku used for reasoning-heavy step (architecture/synthesis)"
  - "Opus used for mechanical step (format, extract)"
  - "models_used has no sonnet on a multi-step eval"
ladder:
  - id: routing-01
    name: "Promote step to sonnet in router config"
    cost: trivial
    files: ["backend/app/router/config.yaml"]
  - id: routing-02
    name: "Demote mechanical step to haiku"
    cost: trivial
    files: ["backend/app/router/config.yaml"]
  - id: routing-03
    name: "Add routing rule keyed on step type"
    cost: small
    files: ["backend/app/router/rules.py"]
```

```yaml
# backend/app/sop/ladders/05-architecture.yaml
bucket: architecture
description: "Missing subagent, needs parallelism, handoff vs single-loop wrong"
triage_signals:
  - "Level 5 state-tracking failure with subagents_spawned == 0"
  - "Single-loop exhausts context on multi-step task"
  - "Independent subtasks executed sequentially"
ladder:
  - id: architecture-01
    name: "Wrap failing subtask in a subagent"
    cost: small
    files: ["backend/app/agent/loop.py"]
  - id: architecture-02
    name: "Parallelize independent subagents"
    cost: medium
    files: ["backend/app/agent/loop.py"]
  - id: architecture-03
    name: "Introduce handoff between planner and executor"
    cost: large
    files: ["backend/app/agent/"]
```

```yaml
# backend/app/sop/ladders/06-harness.yaml
bucket: harness
description: "Middleware missing fallback, tool error bubbling wrong, retries absent"
triage_signals:
  - "tool_errors > 0 with retries == 0"
  - "Session aborted on transient failure"
  - "Tool error surfaces to user instead of being handled"
ladder:
  - id: harness-01
    name: "Add retry-with-backoff to tool middleware"
    cost: small
    files: ["backend/app/agent/middleware.py"]
  - id: harness-02
    name: "Add fallback tool for failing primary"
    cost: medium
    files: ["backend/app/agent/middleware.py", "backend/app/agent/tools/"]
  - id: harness-03
    name: "Reorder middleware stack to catch errors before bubble"
    cost: medium
    files: ["backend/app/agent/middleware.py"]
```

```yaml
# backend/app/sop/ladders/07-evaluation-bias.yaml
bucket: evaluation_bias
description: "Judge miscalibrated, rubric ambiguous, fixture stale"
triage_signals:
  - "Judge variance across N replays > 0.5 grade steps"
  - "Judge justification contradicts its own score"
  - "Rubric dimension name unclear relative to criteria"
ladder:
  - id: evaluation-bias-01
    name: "Clarify rubric criteria wording"
    cost: trivial
    files: ["backend/tests/evals/rubrics/level<N>.yaml"]
  - id: evaluation-bias-02
    name: "Pin judge temperature=0 and add seed"
    cost: trivial
    files: ["backend/app/evals/judge.py"]
  - id: evaluation-bias-03
    name: "Add calibration fixtures with known grades"
    cost: small
    files: ["backend/tests/evals/calibration/"]
```

```yaml
# backend/app/sop/ladders/08-data-quality.yaml
bucket: data_quality
description: "Seed data changed, schema mismatch, planted-anomaly count drift"
triage_signals:
  - "Seed fingerprint differs from last-known-good"
  - "Row counts off by more than 1%"
  - "Planted-anomaly checksum mismatch"
ladder:
  - id: data-quality-01
    name: "Re-run seed with pinned SEED=42 and verify row counts"
    cost: trivial
    files: ["backend/scripts/seed_eval_data.py"]
  - id: data-quality-02
    name: "Pin faker/random seeds inside seed_all()"
    cost: trivial
    files: ["backend/scripts/seed_eval_data.py"]
  - id: data-quality-03
    name: "Add seed fingerprint assertion to test suite"
    cost: small
    files: ["backend/tests/unit/test_seed_eval.py"]
```

```yaml
# backend/app/sop/ladders/09-determinism.yaml
bucket: determinism
description: "Agent gives different output same input, temperature leakage"
triage_signals:
  - "Re-run of same eval produces different grade"
  - "Agent output differs across replays with identical inputs"
  - "Tool ordering varies across runs"
ladder:
  - id: determinism-01
    name: "Pin agent temperature=0 for eval runs"
    cost: trivial
    files: ["backend/app/agent/config.py"]
  - id: determinism-02
    name: "Seed any stochastic library calls"
    cost: trivial
    files: ["backend/app/agent/"]
  - id: determinism-03
    name: "Sort tool results to eliminate ordering variance"
    cost: small
    files: ["backend/app/agent/tools/"]
```

- [ ] **Step 4: Implement `app/sop/ladder_loader.py`**

```python
# backend/app/sop/ladder_loader.py
"""Load ladder YAML files into LadderDefinition objects."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.sop.types import LadderDefinition

LADDERS_DIR = Path(__file__).parent / "ladders"


def load_ladder(bucket: str) -> LadderDefinition:
    """Load one ladder by bucket name (e.g. 'context', 'evaluation_bias')."""
    slug = bucket.replace("_", "-")
    for path in LADDERS_DIR.glob(f"*{slug}.yaml"):
        data = yaml.safe_load(path.read_text())
        return LadderDefinition.model_validate(data)
    raise FileNotFoundError(f"No ladder YAML for bucket {bucket!r} in {LADDERS_DIR}")


def load_all_ladders() -> list[LadderDefinition]:
    """Load every ladder YAML in order of filename (which is cost of triage)."""
    ladders = []
    for path in sorted(LADDERS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        ladders.append(LadderDefinition.model_validate(data))
    return ladders
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_ladder_loader.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/sop/ladders/ backend/app/sop/ladder_loader.py backend/tests/sop/test_ladder_loader.py
git commit -m "feat: add 9 SOP ladder YAMLs and loader"
```

---

## Task 6: Pre-flight (buckets 7, 8, 9)

**Files:**
- Create: `backend/app/sop/preflight.py`
- Test:   `backend/tests/sop/test_preflight.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_preflight.py
from __future__ import annotations

from app.sop.preflight import run_preflight
from app.sop.types import FailureReport, Signals


def _report(**overrides) -> FailureReport:
    base = dict(
        level=3, overall_grade="C", dimensions=[],
        signals=Signals(
            token_count=100, duration_ms=10, compaction_events=0,
            scratchpad_writes=0, tool_errors=0, retries=0,
            subagents_spawned=0, models_used={},
        ),
        judge_justifications={}, top_failure_signature="x",
        trace_id="x", trace_path="x", diff_vs_baseline=None,
    )
    base.update(overrides)
    return FailureReport(**base)


def test_all_pass_when_no_variance_no_drift() -> None:
    result = run_preflight(
        report=_report(),
        judge_variance={"detection_recall": 0.0},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B", "B"],
    )
    assert not result.any_failed()


def test_evaluation_bias_fails_when_judge_variance_exceeds_threshold() -> None:
    result = run_preflight(
        report=_report(),
        judge_variance={"detection_recall": 0.6},  # > 0.5 grade steps
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B", "B"],
    )
    assert result.evaluation_bias == "fail"
    assert result.data_quality == "pass"
    assert result.determinism == "pass"


def test_data_quality_fails_on_seed_mismatch() -> None:
    result = run_preflight(
        report=_report(),
        judge_variance={},
        seed_fingerprint_matches=False,
        rerun_grades=["B", "B", "B"],
    )
    assert result.data_quality == "fail"


def test_determinism_fails_on_rerun_grade_variance() -> None:
    result = run_preflight(
        report=_report(),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "C", "B"],
    )
    assert result.determinism == "fail"


def test_determinism_skipped_when_fewer_than_two_reruns() -> None:
    result = run_preflight(
        report=_report(),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B"],
    )
    assert result.determinism == "skipped"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_preflight.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement `app/sop/preflight.py`**

```python
# backend/app/sop/preflight.py
"""Pre-flight triage: buckets 7 (evaluation bias), 8 (data quality), 9 (determinism)."""
from __future__ import annotations

from app.sop.types import FailureReport, PreflightResult, PreflightVerdict

JUDGE_VARIANCE_THRESHOLD = 0.5  # grade steps


def _evaluation_bias(judge_variance: dict[str, float]) -> PreflightVerdict:
    if not judge_variance:
        return "skipped"
    return "fail" if max(judge_variance.values()) > JUDGE_VARIANCE_THRESHOLD else "pass"


def _data_quality(seed_fingerprint_matches: bool) -> PreflightVerdict:
    return "pass" if seed_fingerprint_matches else "fail"


def _determinism(rerun_grades: list[str]) -> PreflightVerdict:
    if len(rerun_grades) < 2:
        return "skipped"
    return "pass" if len(set(rerun_grades)) == 1 else "fail"


def run_preflight(
    *,
    report: FailureReport,
    judge_variance: dict[str, float],
    seed_fingerprint_matches: bool,
    rerun_grades: list[str],
) -> PreflightResult:
    """Run the three pre-flight checks. `report` is reserved for future signal use."""
    del report  # currently unused; kept for future checks that inspect report state
    return PreflightResult(
        evaluation_bias=_evaluation_bias(judge_variance),
        data_quality=_data_quality(seed_fingerprint_matches),
        determinism=_determinism(rerun_grades),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_preflight.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/sop/preflight.py backend/tests/sop/test_preflight.py
git commit -m "feat: add SOP pre-flight triage for buckets 7-9"
```

---

## Task 7: Main triage (cost-ordered, stop-at-first)

**Files:**
- Create: `backend/app/sop/triage.py`
- Test:   `backend/tests/sop/test_triage.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_triage.py
from __future__ import annotations

from app.sop.triage import triage
from app.sop.types import DiffVsBaseline, FailureReport, Signals

TRIAGE_ORDER = ["context", "prompt", "capability", "routing", "architecture", "harness"]


def _report(*, signals: Signals, diff: DiffVsBaseline | None = None) -> FailureReport:
    return FailureReport(
        level=3, overall_grade="C", dimensions=[],
        signals=signals, judge_justifications={}, top_failure_signature="x",
        trace_id="x", trace_path="x", diff_vs_baseline=diff,
    )


def _signals(**overrides) -> Signals:
    base = dict(
        token_count=1000, duration_ms=1000, compaction_events=0,
        scratchpad_writes=0, tool_errors=0, retries=0,
        subagents_spawned=0, models_used={},
    )
    base.update(overrides)
    return Signals(**base)


def test_picks_context_when_compaction_high_and_no_scratchpad() -> None:
    decision = triage(_report(
        signals=_signals(compaction_events=3, scratchpad_writes=0, token_count=20000),
        diff=DiffVsBaseline(baseline_date="2026-04-10", baseline_grade="B",
                            changes={"token_count": {"before": 10000, "after": 20000}}),
    ))
    assert decision is not None
    assert decision.bucket == "context"
    assert any("scratchpad" in e or "compaction" in e for e in decision.evidence)


def test_picks_harness_when_tool_errors_no_retries() -> None:
    decision = triage(_report(
        signals=_signals(tool_errors=2, retries=0),
    ))
    assert decision is not None
    assert decision.bucket == "harness"


def test_stops_at_first_actionable_bucket_preferring_context_over_harness() -> None:
    # Both context and harness signals present; context is cheaper.
    decision = triage(_report(
        signals=_signals(compaction_events=5, scratchpad_writes=0, tool_errors=2, retries=0),
    ))
    assert decision is not None
    assert decision.bucket == "context"


def test_returns_none_when_no_signal_matches() -> None:
    decision = triage(_report(signals=_signals()))
    assert decision is None


def test_picks_routing_when_sonnet_absent_on_reasoning_level() -> None:
    decision = triage(_report(
        signals=_signals(models_used={"haiku": 10, "sonnet": 0}),
    ))
    assert decision is not None
    assert decision.bucket == "routing"


def test_picks_architecture_on_level5_with_no_subagents() -> None:
    decision = triage(FailureReport(
        level=5, overall_grade="C", dimensions=[],
        signals=_signals(subagents_spawned=0),
        judge_justifications={}, top_failure_signature="state_drift",
        trace_id="x", trace_path="x", diff_vs_baseline=None,
    ))
    assert decision is not None
    assert decision.bucket == "architecture"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_triage.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement `app/sop/triage.py`**

```python
# backend/app/sop/triage.py
"""Main triage: evaluate bucket signals in cost order, stop at first actionable."""
from __future__ import annotations

from collections.abc import Callable

from app.sop.types import FailureReport, TriageDecision

TRIAGE_ORDER: list[str] = [
    "context", "prompt", "capability", "routing", "architecture", "harness",
]


def _check_context(r: FailureReport) -> list[str] | None:
    evidence: list[str] = []
    if r.signals.compaction_events >= 3:
        evidence.append(f"compaction_events={r.signals.compaction_events} in one session")
    if r.signals.scratchpad_writes == 0 and r.signals.token_count > 5000:
        evidence.append("scratchpad_writes=0 with substantial token usage")
    if r.diff_vs_baseline and "token_count" in r.diff_vs_baseline.changes:
        chg = r.diff_vs_baseline.changes["token_count"]
        before, after = chg.get("before"), chg.get("after")
        if isinstance(before, int) and isinstance(after, int) and before > 0 and after > before * 1.5:
            evidence.append(f"token_count {before} -> {after} (>1.5x baseline)")
    return evidence or None


def _check_prompt(r: FailureReport) -> list[str] | None:
    keywords = ("ignored", "contradic", "missing guidance", "unclear instruction")
    hits = [
        f"judge cites `{k}` in {dim}"
        for dim, text in r.judge_justifications.items()
        for k in keywords
        if k in text.lower()
    ]
    return hits or None


def _check_capability(r: FailureReport) -> list[str] | None:
    hits = [
        f"judge flags wrong output in {dim}"
        for dim, text in r.judge_justifications.items()
        if "wrong" in text.lower() or "incorrect" in text.lower()
    ]
    if r.signals.tool_errors > 0 and r.signals.retries > r.signals.tool_errors:
        hits.append("repeated retries on same tool (skill churn)")
    return hits or None


def _check_routing(r: FailureReport) -> list[str] | None:
    models = r.signals.models_used
    if not models:
        return None
    sonnet = models.get("sonnet", 0)
    haiku = models.get("haiku", 0)
    if haiku > 0 and sonnet == 0 and r.level >= 2:
        return [f"models_used has no sonnet on level {r.level} (reasoning-heavy)"]
    return None


def _check_architecture(r: FailureReport) -> list[str] | None:
    if r.level == 5 and r.signals.subagents_spawned == 0:
        return ["level 5 with subagents_spawned=0 (single-loop state tracking)"]
    return None


def _check_harness(r: FailureReport) -> list[str] | None:
    if r.signals.tool_errors > 0 and r.signals.retries == 0:
        return [f"tool_errors={r.signals.tool_errors} with retries=0"]
    return None


BUCKET_CHECKS: dict[str, Callable[[FailureReport], list[str] | None]] = {
    "context": _check_context,
    "prompt": _check_prompt,
    "capability": _check_capability,
    "routing": _check_routing,
    "architecture": _check_architecture,
    "harness": _check_harness,
}


def _hypothesis(bucket: str, evidence: list[str]) -> str:
    templates = {
        "context": "Context layer is leaking or compaction is mis-tuned",
        "prompt": "System prompt has a gap or a conflicting directive",
        "capability": "Skill output is incorrect or skill is churning",
        "routing": "Wrong model selected for the step",
        "architecture": "Single-loop cannot hold multi-step state; subagent needed",
        "harness": "Tool-error path has no retry or fallback",
    }
    return f"{templates[bucket]} (evidence: {'; '.join(evidence)})"


def triage(report: FailureReport) -> TriageDecision | None:
    """Return the first bucket (cost-ordered) whose signals fire, else None."""
    for bucket in TRIAGE_ORDER:
        evidence = BUCKET_CHECKS[bucket](report)
        if evidence:
            return TriageDecision(
                bucket=bucket,
                evidence=evidence,
                hypothesis=_hypothesis(bucket, evidence),
            )
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_triage.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/sop/triage.py backend/tests/sop/test_triage.py
git commit -m "feat: add SOP main triage with cost-ordered bucket evaluation"
```

---

## Task 8: Autonomy config + graduation check

**Files:**
- Create: `backend/app/sop/autonomy.py`
- Test:   `backend/tests/sop/test_autonomy.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_autonomy.py
from __future__ import annotations

from pathlib import Path

from app.sop.autonomy import (
    AutonomyConfig,
    evaluate_graduation_readiness,
    load_autonomy_config,
    mark_autonomous,
    revert_to_proposed,
)
from app.sop.log import write_entry
from app.sop.types import (
    FixApplied,
    IterationLogEntry,
    PreflightResult,
    TriageDecision,
)


def _entry(session_id: str, bucket: str, *, ladder_id: str, success: bool, regressions: str = "none") -> IterationLogEntry:
    return IterationLogEntry(
        date=session_id[:10],
        session_id=session_id,
        level=3,
        overall_grade_before="C",
        preflight=PreflightResult(evaluation_bias="pass", data_quality="pass", determinism="pass"),
        triage=TriageDecision(bucket=bucket, evidence=["e"], hypothesis="h"),
        fix=FixApplied(ladder_id=ladder_id, name="n", files_changed=["f"],
                       model_used_for_fix="sonnet", cost_bucket="trivial"),
        outcome={"grade_after": "B" if success else "C", "regressions": regressions,
                 "iterations": 1, "success": success},
        trace_links={"before": "a.json", "after": "b.json"},
    )


def test_load_missing_config_returns_empty(tmp_path: Path) -> None:
    cfg = load_autonomy_config(tmp_path / "missing.yaml")
    assert cfg.autonomous_buckets == []


def test_mark_autonomous_and_revert_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "autonomy.yaml"
    mark_autonomous("context", path)
    assert load_autonomy_config(path).autonomous_buckets == ["context"]
    revert_to_proposed("context", path)
    assert load_autonomy_config(path).autonomous_buckets == []


def test_graduation_fails_without_five_sessions(tmp_path: Path) -> None:
    for i in range(4):
        write_entry(_entry(f"2026-04-0{i+1}-level3-001", "context",
                           ladder_id=f"context-0{i%3+1}", success=True), tmp_path)
    assert not evaluate_graduation_readiness("context", tmp_path)


def test_graduation_passes_with_five_sessions_80pct_success_three_rungs(tmp_path: Path) -> None:
    rungs = ["context-01", "context-02", "context-03", "context-01", "context-02"]
    for i, rung in enumerate(rungs):
        write_entry(_entry(f"2026-04-0{i+1}-level3-001", "context",
                           ladder_id=rung, success=True), tmp_path)
    assert evaluate_graduation_readiness("context", tmp_path)


def test_graduation_fails_with_low_success_rate(tmp_path: Path) -> None:
    # 3 of 5 succeed = 60%
    for i in range(5):
        write_entry(_entry(f"2026-04-0{i+1}-level3-001", "context",
                           ladder_id=f"context-0{i%3+1}",
                           success=(i < 3)), tmp_path)
    assert not evaluate_graduation_readiness("context", tmp_path)


def test_graduation_fails_when_only_two_distinct_rungs(tmp_path: Path) -> None:
    for i in range(5):
        write_entry(_entry(f"2026-04-0{i+1}-level3-001", "context",
                           ladder_id=f"context-0{i%2+1}", success=True), tmp_path)
    assert not evaluate_graduation_readiness("context", tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_autonomy.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement `app/sop/autonomy.py`**

```python
# backend/app/sop/autonomy.py
"""Per-bucket autonomy config and graduation readiness check."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from app.sop.log import list_entries

MIN_SESSIONS = 5
MIN_SUCCESS_RATE = 0.80
MIN_DISTINCT_RUNGS = 3


class AutonomyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    autonomous_buckets: list[str] = []


def load_autonomy_config(path: Path) -> AutonomyConfig:
    if not path.exists():
        return AutonomyConfig()
    data = yaml.safe_load(path.read_text()) or {}
    return AutonomyConfig.model_validate(data)


def _save(config: AutonomyConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config.model_dump(), sort_keys=False))


def mark_autonomous(bucket: str, path: Path) -> None:
    cfg = load_autonomy_config(path)
    if bucket in cfg.autonomous_buckets:
        return
    _save(AutonomyConfig(autonomous_buckets=[*cfg.autonomous_buckets, bucket]), path)


def revert_to_proposed(bucket: str, path: Path) -> None:
    cfg = load_autonomy_config(path)
    remaining = [b for b in cfg.autonomous_buckets if b != bucket]
    _save(AutonomyConfig(autonomous_buckets=remaining), path)


def evaluate_graduation_readiness(bucket: str, log_dir: Path) -> bool:
    """True iff bucket meets all graduation criteria."""
    entries = [e for e in list_entries(log_dir) if e.triage.bucket == bucket]
    if len(entries) < MIN_SESSIONS:
        return False
    success_rate = sum(1 for e in entries if e.outcome.get("success")) / len(entries)
    if success_rate < MIN_SUCCESS_RATE:
        return False
    distinct_rungs = {e.fix.ladder_id for e in entries}
    if len(distinct_rungs) < MIN_DISTINCT_RUNGS:
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_autonomy.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/sop/autonomy.py backend/tests/sop/test_autonomy.py
git commit -m "feat: add SOP autonomy config and graduation readiness check"
```

---

## Task 9: SOP runner (orchestrator)

**Files:**
- Create: `backend/app/sop/runner.py`
- Test:   `backend/tests/sop/test_runner.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_runner.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.sop.runner import SOPResult, run_sop
from app.sop.types import FailureReport, Signals


def _report(**overrides) -> FailureReport:
    base = dict(
        level=3, overall_grade="C", dimensions=[],
        signals=Signals(
            token_count=20000, duration_ms=10, compaction_events=3,
            scratchpad_writes=0, tool_errors=0, retries=0,
            subagents_spawned=0, models_used={"haiku": 5, "sonnet": 2},
        ),
        judge_justifications={}, top_failure_signature="x",
        trace_id="x", trace_path="x", diff_vs_baseline=None,
    )
    base.update(overrides)
    return FailureReport(**base)


def test_preflight_failure_short_circuits(tmp_path: Path) -> None:
    result = run_sop(
        report=_report(),
        judge_variance={"detection_recall": 0.9},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    assert result.preflight.evaluation_bias == "fail"
    assert result.triage is None
    assert result.proposal is None
    assert "evaluation_bias" in result.advisory


def test_triage_returns_proposal_with_cheapest_rung(tmp_path: Path) -> None:
    result = run_sop(
        report=_report(),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    assert result.triage is not None
    assert result.triage.bucket == "context"
    assert result.proposal is not None
    assert result.proposal.id == "context-01"
    assert result.proposal.cost == "trivial"


def test_no_actionable_signal_returns_none_triage() -> None:
    result = run_sop(
        report=_report(signals=Signals(
            token_count=100, duration_ms=10, compaction_events=0,
            scratchpad_writes=5, tool_errors=0, retries=0,
            subagents_spawned=2, models_used={"sonnet": 5, "haiku": 0},
        )),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    assert result.triage is None
    assert result.proposal is None


def test_sop_result_is_json_serializable() -> None:
    result = run_sop(
        report=_report(),
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=["B", "B"],
    )
    dumped = result.model_dump()
    assert "preflight" in dumped and "triage" in dumped and "proposal" in dumped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_runner.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement `app/sop/runner.py`**

```python
# backend/app/sop/runner.py
"""SOP orchestrator: pre-flight → main triage → propose ladder rung."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.sop.ladder_loader import load_ladder
from app.sop.preflight import run_preflight
from app.sop.triage import triage
from app.sop.types import (
    FailureReport,
    LadderRung,
    PreflightResult,
    TriageDecision,
)


class SOPResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    preflight: PreflightResult
    triage: TriageDecision | None
    proposal: LadderRung | None
    advisory: str


def _advisory_for_preflight(pf: PreflightResult) -> str:
    failed = [name for name, v in (
        ("evaluation_bias", pf.evaluation_bias),
        ("data_quality", pf.data_quality),
        ("determinism", pf.determinism),
    ) if v == "fail"]
    return (
        f"Pre-flight failed: {', '.join(failed)}. Fix the eval apparatus before the agent."
        if failed
        else "Pre-flight passed."
    )


def run_sop(
    *,
    report: FailureReport,
    judge_variance: dict[str, float],
    seed_fingerprint_matches: bool,
    rerun_grades: list[str],
) -> SOPResult:
    pf = run_preflight(
        report=report,
        judge_variance=judge_variance,
        seed_fingerprint_matches=seed_fingerprint_matches,
        rerun_grades=rerun_grades,
    )
    if pf.any_failed():
        return SOPResult(preflight=pf, triage=None, proposal=None,
                         advisory=_advisory_for_preflight(pf))

    decision = triage(report)
    if decision is None:
        return SOPResult(preflight=pf, triage=None, proposal=None,
                         advisory="No triage signal fired. Inspect trace manually.")

    ladder = load_ladder(decision.bucket)
    top_rung = ladder.ladder[0]  # cost-ordered; first is cheapest
    return SOPResult(
        preflight=pf,
        triage=decision,
        proposal=top_rung,
        advisory=f"Proposed: {top_rung.name} (cost={top_rung.cost}).",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_runner.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/sop/runner.py backend/tests/sop/test_runner.py
git commit -m "feat: add SOP runner orchestrator"
```

---

## Task 10: REST API for DevTools

**Files:**
- Create: `backend/app/api/sop_api.py`
- Modify: `backend/app/main.py` (register router)
- Test:   `backend/tests/sop/test_sop_api.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/sop/test_sop_api.py
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.sop.log import write_entry
from app.sop.types import (
    FixApplied,
    IterationLogEntry,
    PreflightResult,
    TriageDecision,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("SOP_LOG_DIR", str(tmp_path / "log"))
    monkeypatch.setenv("SOP_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("SOP_BASELINES_DIR", str(tmp_path / "baselines"))
    return TestClient(create_app())


def _entry(session_id: str) -> IterationLogEntry:
    return IterationLogEntry(
        date=session_id[:10],
        session_id=session_id,
        level=3,
        overall_grade_before="C",
        preflight=PreflightResult(evaluation_bias="pass", data_quality="pass", determinism="pass"),
        triage=TriageDecision(bucket="context", evidence=["e"], hypothesis="h"),
        fix=FixApplied(ladder_id="context-01", name="n", files_changed=["f"],
                       model_used_for_fix="sonnet", cost_bucket="trivial"),
        outcome={"grade_after": "B", "regressions": "none", "iterations": 1, "success": True},
        trace_links={"before": "a.json", "after": "b.json"},
    )


def test_list_sessions_empty(client: TestClient) -> None:
    resp = client.get("/api/sop/sessions")
    assert resp.status_code == 200
    assert resp.json() == {"sessions": []}


def test_list_sessions_returns_written_entries(client: TestClient, tmp_path: Path) -> None:
    write_entry(_entry("2026-04-12-level3-001"), tmp_path / "log")
    resp = client.get("/api/sop/sessions")
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "2026-04-12-level3-001"


def test_get_session_by_id(client: TestClient, tmp_path: Path) -> None:
    write_entry(_entry("2026-04-12-level3-001"), tmp_path / "log")
    resp = client.get("/api/sop/sessions/2026-04-12-level3-001")
    assert resp.status_code == 200
    assert resp.json()["triage"]["bucket"] == "context"


def test_get_session_missing_returns_404(client: TestClient) -> None:
    resp = client.get("/api/sop/sessions/never-existed")
    assert resp.status_code == 404


def test_list_ladders_returns_nine(client: TestClient) -> None:
    resp = client.get("/api/sop/ladders")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ladders"]) == 9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py -v`
Expected: FAIL with ModuleNotFoundError or missing route

- [ ] **Step 3: Implement `app/api/sop_api.py`**

```python
# backend/app/api/sop_api.py
"""REST endpoints for DevTools SOP views."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.sop.ladder_loader import load_all_ladders
from app.sop.log import list_entries, read_entry

router = APIRouter(prefix="/api/sop", tags=["sop"])


def _log_dir() -> Path:
    return Path(os.environ.get("SOP_LOG_DIR", "docs/superpowers/sop-log"))


@router.get("/sessions")
def list_sessions() -> dict:
    return {"sessions": [e.model_dump() for e in list_entries(_log_dir())]}


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    try:
        entry = read_entry(session_id, _log_dir())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return entry.model_dump()


@router.get("/ladders")
def list_ladders() -> dict:
    return {"ladders": [l.model_dump() for l in load_all_ladders()]}
```

- [ ] **Step 4: Register router in `app/main.py`**

Find the FastAPI factory (search for `def create_app`) and add (adjacent to other router registrations):

```python
from app.api.sop_api import router as sop_router
# ... inside create_app() after app = FastAPI(...)
app.include_router(sop_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/sop_api.py backend/app/main.py backend/tests/sop/test_sop_api.py
git commit -m "feat: add SOP REST API for DevTools views"
```

---

## Task 11: DevTools — SOP Session Replay view

**Files:**
- Create: `frontend/src/devtools/sop/api.ts`
- Create: `frontend/src/devtools/sop/SessionReplay.tsx`
- Modify: `frontend/src/devtools/DevToolsPanel.tsx` (add SOP tab)
- Test:   `frontend/src/devtools/sop/SessionReplay.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// frontend/src/devtools/sop/SessionReplay.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SessionReplay } from './SessionReplay';

const mockSession = {
  session_id: '2026-04-12-level3-001',
  date: '2026-04-12',
  level: 3,
  overall_grade_before: 'C',
  triage: { bucket: 'context', evidence: ['e'], hypothesis: 'h' },
  fix: {
    ladder_id: 'context-01', name: 'Lower threshold',
    files_changed: ['backend/app/context/manager.py'],
    model_used_for_fix: 'sonnet', cost_bucket: 'trivial',
  },
  outcome: { grade_after: 'B', regressions: 'none', iterations: 1, success: true },
  trace_links: { before: 'a.json', after: 'b.json' },
  preflight: { evaluation_bias: 'pass', data_quality: 'pass', determinism: 'pass' },
};

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sessions: [mockSession] }),
  }) as unknown as typeof fetch;
});

describe('SessionReplay', () => {
  it('renders session list from API', async () => {
    render(<SessionReplay />);
    await waitFor(() => {
      expect(screen.getByText('2026-04-12-level3-001')).toBeInTheDocument();
      expect(screen.getByText(/context/i)).toBeInTheDocument();
      expect(screen.getByText(/C.*→.*B/)).toBeInTheDocument();
    });
  });

  it('shows empty state when no sessions', async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sessions: [] }),
    });
    render(<SessionReplay />);
    await waitFor(() => {
      expect(screen.getByText(/no sop sessions yet/i)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/devtools/sop/SessionReplay.test.tsx`
Expected: FAIL with "Cannot find module './SessionReplay'"

- [ ] **Step 3: Implement `frontend/src/devtools/sop/api.ts`**

```ts
// frontend/src/devtools/sop/api.ts
export type Grade = 'A' | 'B' | 'C' | 'F';
export type PreflightVerdict = 'pass' | 'fail' | 'skipped';

export interface SOPSession {
  session_id: string;
  date: string;
  level: number;
  overall_grade_before: Grade;
  preflight: {
    evaluation_bias: PreflightVerdict;
    data_quality: PreflightVerdict;
    determinism: PreflightVerdict;
  };
  triage: { bucket: string; evidence: string[]; hypothesis: string };
  fix: {
    ladder_id: string;
    name: string;
    files_changed: string[];
    model_used_for_fix: string;
    cost_bucket: string;
  };
  outcome: Record<string, unknown>;
  trace_links: Record<string, string>;
}

export async function listSessions(): Promise<SOPSession[]> {
  const resp = await fetch('/api/sop/sessions');
  if (!resp.ok) throw new Error(`listSessions failed: ${resp.status}`);
  const data = (await resp.json()) as { sessions: SOPSession[] };
  return data.sessions;
}
```

- [ ] **Step 4: Implement `frontend/src/devtools/sop/SessionReplay.tsx`**

```tsx
// frontend/src/devtools/sop/SessionReplay.tsx
import { useEffect, useState } from 'react';
import { listSessions, SOPSession } from './api';

export function SessionReplay() {
  const [sessions, setSessions] = useState<SOPSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <div className="sop-error">Error: {error}</div>;
  if (sessions === null) return <div className="sop-loading">Loading…</div>;
  if (sessions.length === 0) return <div className="sop-empty">No SOP sessions yet.</div>;

  return (
    <div className="sop-session-replay">
      <h3>SOP Session Replay</h3>
      <ul className="sop-session-list">
        {sessions.map((s) => {
          const after = (s.outcome.grade_after as string) ?? '?';
          return (
            <li key={s.session_id} className="sop-session-item">
              <div className="sop-session-header">
                <span className="sop-session-id">{s.session_id}</span>
                <span className="sop-session-bucket">{s.triage.bucket}</span>
                <span className="sop-session-grade">
                  {s.overall_grade_before} → {after}
                </span>
              </div>
              <div className="sop-session-fix">{s.fix.name}</div>
              <div className="sop-session-evidence">
                {s.triage.evidence.map((e, i) => (
                  <div key={i}>• {e}</div>
                ))}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 5: Add SOP tab to `DevToolsPanel.tsx`**

Open the existing file, find where tabs are rendered (look for an existing tab switch), and add:

```tsx
import { SessionReplay } from './sop/SessionReplay';
// ... inside the tab switch, alongside ContextInspector:
{activeTab === 'sop' && <SessionReplay />}
// ... and in the tab buttons array, add:
// { id: 'sop', label: 'SOP' }
```

If the existing file does not use a tab pattern yet, add the SessionReplay as a secondary section below the ContextInspector.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/devtools/sop/SessionReplay.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/devtools/sop/ frontend/src/devtools/DevToolsPanel.tsx
git commit -m "feat: add SOP Session Replay view in DevTools"
```

---

## Task 12: DevTools — Judge Variance Dashboard

**Files:**
- Create: `frontend/src/devtools/sop/JudgeVariance.tsx`
- Modify: `frontend/src/devtools/sop/api.ts` (add fetcher)
- Create: `backend/app/api/sop_api.py` extension (add `/api/sop/judge-variance/{trace_id}`)
- Test:   `frontend/src/devtools/sop/JudgeVariance.test.tsx`

- [ ] **Step 1: Write failing backend test**

Append to `backend/tests/sop/test_sop_api.py`:

```python
def test_judge_variance_endpoint_returns_dimension_variance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_variance = {"detection_recall": 0.2, "false_positive_handling": 0.6}
    monkeypatch.setattr(
        "app.api.sop_api.compute_judge_variance",
        lambda trace_id, n: fake_variance,
    )
    resp = client.get("/api/sop/judge-variance/eval-x?n=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["variance"] == fake_variance
    assert data["threshold_exceeded"] == ["false_positive_handling"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py::test_judge_variance_endpoint_returns_dimension_variance -v`
Expected: FAIL (endpoint missing)

- [ ] **Step 3: Extend `app/api/sop_api.py`**

Append to `backend/app/api/sop_api.py`:

```python
from app.sop.preflight import JUDGE_VARIANCE_THRESHOLD


def compute_judge_variance(trace_id: str, n: int) -> dict[str, float]:
    """Placeholder stub — returns empty variance. Real implementation re-runs judge N times.
    Real implementation lives in app/sop/judge_replay.py; we avoid heavy wiring in v1.
    """
    _ = (trace_id, n)
    return {}


@router.get("/judge-variance/{trace_id}")
def judge_variance(trace_id: str, n: int = 5) -> dict:
    variance = compute_judge_variance(trace_id, n)
    exceeded = [dim for dim, v in variance.items() if v > JUDGE_VARIANCE_THRESHOLD]
    return {"variance": variance, "threshold_exceeded": exceeded}
```

- [ ] **Step 4: Run backend test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py::test_judge_variance_endpoint_returns_dimension_variance -v`
Expected: PASS

- [ ] **Step 5: Write failing frontend test**

```tsx
// frontend/src/devtools/sop/JudgeVariance.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { JudgeVariance } from './JudgeVariance';

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      variance: { detection_recall: 0.2, false_positive_handling: 0.7 },
      threshold_exceeded: ['false_positive_handling'],
    }),
  }) as unknown as typeof fetch;
});

describe('JudgeVariance', () => {
  it('shows dimension variance and flags exceeded ones', async () => {
    render(<JudgeVariance traceId="eval-x" />);
    await waitFor(() => {
      expect(screen.getByText(/false_positive_handling/)).toBeInTheDocument();
      expect(screen.getByText(/0\.70/)).toBeInTheDocument();
      expect(screen.getByText(/exceeded/i)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 6: Add fetcher in `api.ts`**

Append to `frontend/src/devtools/sop/api.ts`:

```ts
export interface JudgeVarianceResponse {
  variance: Record<string, number>;
  threshold_exceeded: string[];
}

export async function fetchJudgeVariance(
  traceId: string,
  n = 5,
): Promise<JudgeVarianceResponse> {
  const resp = await fetch(`/api/sop/judge-variance/${traceId}?n=${n}`);
  if (!resp.ok) throw new Error(`judge-variance failed: ${resp.status}`);
  return (await resp.json()) as JudgeVarianceResponse;
}
```

- [ ] **Step 7: Implement `JudgeVariance.tsx`**

```tsx
// frontend/src/devtools/sop/JudgeVariance.tsx
import { useEffect, useState } from 'react';
import { fetchJudgeVariance, JudgeVarianceResponse } from './api';

interface Props {
  traceId: string;
}

export function JudgeVariance({ traceId }: Props) {
  const [data, setData] = useState<JudgeVarianceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJudgeVariance(traceId)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [traceId]);

  if (error) return <div className="sop-error">Error: {error}</div>;
  if (data === null) return <div className="sop-loading">Loading…</div>;

  const entries = Object.entries(data.variance);
  if (entries.length === 0) {
    return <div className="sop-empty">No variance data for this trace.</div>;
  }

  return (
    <div className="sop-judge-variance">
      <h3>Judge Variance — {traceId}</h3>
      <table>
        <thead>
          <tr><th>Dimension</th><th>Variance</th><th>Status</th></tr>
        </thead>
        <tbody>
          {entries.map(([dim, variance]) => {
            const exceeded = data.threshold_exceeded.includes(dim);
            return (
              <tr key={dim} className={exceeded ? 'exceeded' : ''}>
                <td>{dim}</td>
                <td>{variance.toFixed(2)}</td>
                <td>{exceeded ? 'exceeded' : 'ok'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 8: Run frontend test to verify it passes**

Run: `cd frontend && npx vitest run src/devtools/sop/JudgeVariance.test.tsx`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/sop_api.py backend/tests/sop/test_sop_api.py frontend/src/devtools/sop/
git commit -m "feat: add Judge Variance Dashboard with stubbed backend"
```

---

## Task 13: DevTools — Prompt Assembly Inspector

**Files:**
- Create: `frontend/src/devtools/sop/PromptInspector.tsx`
- Modify: `frontend/src/devtools/sop/api.ts`
- Modify: `backend/app/api/sop_api.py` (add `/api/sop/prompt-assembly/{trace_id}/{step_id}`)
- Test:   `frontend/src/devtools/sop/PromptInspector.test.tsx`

- [ ] **Step 1: Write failing backend test**

Append to `backend/tests/sop/test_sop_api.py`:

```python
def test_prompt_assembly_endpoint_returns_sections(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.sop_api.load_prompt_assembly",
        lambda trace_id, step_id: {
            "sections": [
                {"source": "backend/app/prompts/system.md", "lines": "1-10", "text": "A"},
                {"source": "backend/app/skills/sql/SKILL.md", "lines": "1-5", "text": "B"},
            ],
            "conflicts": [],
        },
    )
    resp = client.get("/api/sop/prompt-assembly/eval-x/step-3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sections"]) == 2
    assert data["sections"][0]["source"].endswith("system.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py::test_prompt_assembly_endpoint_returns_sections -v`
Expected: FAIL

- [ ] **Step 3: Extend `app/api/sop_api.py`**

Append to `backend/app/api/sop_api.py`:

```python
def load_prompt_assembly(trace_id: str, step_id: str) -> dict:
    """Placeholder stub — returns empty sections. Real implementation reads the
    trace JSON and reconstructs assembled prompt with per-section file attribution.
    """
    _ = (trace_id, step_id)
    return {"sections": [], "conflicts": []}


@router.get("/prompt-assembly/{trace_id}/{step_id}")
def prompt_assembly(trace_id: str, step_id: str) -> dict:
    return load_prompt_assembly(trace_id, step_id)
```

- [ ] **Step 4: Run backend test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py::test_prompt_assembly_endpoint_returns_sections -v`
Expected: PASS

- [ ] **Step 5: Write failing frontend test**

```tsx
// frontend/src/devtools/sop/PromptInspector.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { PromptInspector } from './PromptInspector';

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      sections: [
        { source: 'backend/app/prompts/system.md', lines: '1-10', text: 'You are an analyst.' },
        { source: 'backend/app/skills/sql/SKILL.md', lines: '1-5', text: 'Use DuckDB.' },
      ],
      conflicts: [],
    }),
  }) as unknown as typeof fetch;
});

describe('PromptInspector', () => {
  it('renders each section with file-source attribution', async () => {
    render(<PromptInspector traceId="eval-x" stepId="step-3" />);
    await waitFor(() => {
      expect(screen.getByText(/system\.md/)).toBeInTheDocument();
      expect(screen.getByText(/SKILL\.md/)).toBeInTheDocument();
      expect(screen.getByText(/You are an analyst/)).toBeInTheDocument();
      expect(screen.getByText(/Use DuckDB/)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 6: Extend `api.ts` and implement `PromptInspector.tsx`**

Append to `frontend/src/devtools/sop/api.ts`:

```ts
export interface PromptSection {
  source: string;
  lines: string;
  text: string;
}

export interface PromptAssembly {
  sections: PromptSection[];
  conflicts: string[];
}

export async function fetchPromptAssembly(traceId: string, stepId: string): Promise<PromptAssembly> {
  const resp = await fetch(`/api/sop/prompt-assembly/${traceId}/${stepId}`);
  if (!resp.ok) throw new Error(`prompt-assembly failed: ${resp.status}`);
  return (await resp.json()) as PromptAssembly;
}
```

```tsx
// frontend/src/devtools/sop/PromptInspector.tsx
import { useEffect, useState } from 'react';
import { fetchPromptAssembly, PromptAssembly } from './api';

interface Props {
  traceId: string;
  stepId: string;
}

export function PromptInspector({ traceId, stepId }: Props) {
  const [data, setData] = useState<PromptAssembly | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPromptAssembly(traceId, stepId)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [traceId, stepId]);

  if (error) return <div className="sop-error">Error: {error}</div>;
  if (data === null) return <div className="sop-loading">Loading…</div>;
  if (data.sections.length === 0) {
    return <div className="sop-empty">No prompt sections for this step.</div>;
  }

  return (
    <div className="sop-prompt-inspector">
      <h3>Prompt Assembly — {traceId} / {stepId}</h3>
      {data.conflicts.length > 0 && (
        <div className="sop-conflicts">
          <strong>Conflicts:</strong>
          <ul>{data.conflicts.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </div>
      )}
      {data.sections.map((s, i) => (
        <div key={i} className="sop-prompt-section">
          <div className="sop-prompt-source">
            {s.source} (lines {s.lines})
          </div>
          <pre className="sop-prompt-text">{s.text}</pre>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 7: Run frontend test to verify it passes**

Run: `cd frontend && npx vitest run src/devtools/sop/PromptInspector.test.tsx`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/sop_api.py backend/tests/sop/test_sop_api.py frontend/src/devtools/sop/PromptInspector.tsx frontend/src/devtools/sop/PromptInspector.test.tsx frontend/src/devtools/sop/api.ts
git commit -m "feat: add Prompt Assembly Inspector with stubbed backend"
```

---

## Task 14: DevTools — Compaction & Scratchpad Timeline

**Files:**
- Create: `frontend/src/devtools/sop/CompactionTimeline.tsx`
- Modify: `frontend/src/devtools/sop/api.ts`
- Modify: `backend/app/api/sop_api.py` (add `/api/sop/timeline/{trace_id}`)
- Test:   `frontend/src/devtools/sop/CompactionTimeline.test.tsx`

- [ ] **Step 1: Write failing backend test**

Append to `backend/tests/sop/test_sop_api.py`:

```python
def test_timeline_endpoint_returns_events_and_layers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.sop_api.load_timeline",
        lambda trace_id: {
            "turns": [
                {"turn": 0, "layers": {"system": 500, "L1_always": 200, "conversation": 100}},
                {"turn": 1, "layers": {"system": 500, "L1_always": 200, "conversation": 600}},
            ],
            "events": [{"turn": 1, "kind": "scratchpad_write", "detail": "sql result"}],
        },
    )
    resp = client.get("/api/sop/timeline/eval-x")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["turns"]) == 2
    assert data["events"][0]["kind"] == "scratchpad_write"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py::test_timeline_endpoint_returns_events_and_layers -v`
Expected: FAIL

- [ ] **Step 3: Extend `app/api/sop_api.py`**

Append:

```python
def load_timeline(trace_id: str) -> dict:
    """Placeholder stub — returns empty timeline. Real implementation reads the
    trace JSON and reconstructs per-turn layer token counts and events.
    """
    _ = trace_id
    return {"turns": [], "events": []}


@router.get("/timeline/{trace_id}")
def timeline(trace_id: str) -> dict:
    return load_timeline(trace_id)
```

- [ ] **Step 4: Run backend test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/sop/test_sop_api.py::test_timeline_endpoint_returns_events_and_layers -v`
Expected: PASS

- [ ] **Step 5: Write failing frontend test**

```tsx
// frontend/src/devtools/sop/CompactionTimeline.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { CompactionTimeline } from './CompactionTimeline';

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      turns: [
        { turn: 0, layers: { system: 500, conversation: 100 } },
        { turn: 1, layers: { system: 500, conversation: 600 } },
      ],
      events: [
        { turn: 1, kind: 'scratchpad_write', detail: 'sql result' },
        { turn: 2, kind: 'compaction', detail: 'threshold hit' },
      ],
    }),
  }) as unknown as typeof fetch;
});

describe('CompactionTimeline', () => {
  it('renders turns and events', async () => {
    render(<CompactionTimeline traceId="eval-x" />);
    await waitFor(() => {
      expect(screen.getByText(/Turn 0/)).toBeInTheDocument();
      expect(screen.getByText(/Turn 1/)).toBeInTheDocument();
      expect(screen.getByText(/scratchpad_write/)).toBeInTheDocument();
      expect(screen.getByText(/compaction/)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 6: Extend `api.ts` and implement `CompactionTimeline.tsx`**

Append to `api.ts`:

```ts
export interface TimelineTurn {
  turn: number;
  layers: Record<string, number>;
}

export interface TimelineEvent {
  turn: number;
  kind: string;
  detail: string;
}

export interface Timeline {
  turns: TimelineTurn[];
  events: TimelineEvent[];
}

export async function fetchTimeline(traceId: string): Promise<Timeline> {
  const resp = await fetch(`/api/sop/timeline/${traceId}`);
  if (!resp.ok) throw new Error(`timeline failed: ${resp.status}`);
  return (await resp.json()) as Timeline;
}
```

```tsx
// frontend/src/devtools/sop/CompactionTimeline.tsx
import { useEffect, useState } from 'react';
import { fetchTimeline, Timeline } from './api';

interface Props {
  traceId: string;
}

export function CompactionTimeline({ traceId }: Props) {
  const [data, setData] = useState<Timeline | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTimeline(traceId).then(setData).catch((e: Error) => setError(e.message));
  }, [traceId]);

  if (error) return <div className="sop-error">Error: {error}</div>;
  if (data === null) return <div className="sop-loading">Loading…</div>;
  if (data.turns.length === 0) return <div className="sop-empty">No timeline data.</div>;

  const maxTotal = Math.max(
    ...data.turns.map((t) => Object.values(t.layers).reduce((a, b) => a + b, 0)),
  );

  return (
    <div className="sop-compaction-timeline">
      <h3>Compaction &amp; Scratchpad — {traceId}</h3>
      <div className="sop-timeline-stack">
        {data.turns.map((t) => {
          const total = Object.values(t.layers).reduce((a, b) => a + b, 0);
          const height = maxTotal > 0 ? (total / maxTotal) * 100 : 0;
          return (
            <div key={t.turn} className="sop-timeline-bar" style={{ height: `${height}%` }}>
              <span>Turn {t.turn}</span>
              <small>{total} tokens</small>
            </div>
          );
        })}
      </div>
      <div className="sop-timeline-events">
        <strong>Events</strong>
        <ul>
          {data.events.map((e, i) => (
            <li key={i}>
              Turn {e.turn}: <strong>{e.kind}</strong> — {e.detail}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Run frontend test to verify it passes**

Run: `cd frontend && npx vitest run src/devtools/sop/CompactionTimeline.test.tsx`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/sop_api.py backend/tests/sop/test_sop_api.py frontend/src/devtools/sop/CompactionTimeline.tsx frontend/src/devtools/sop/CompactionTimeline.test.tsx frontend/src/devtools/sop/api.ts
git commit -m "feat: add Compaction & Scratchpad Timeline view"
```

---

## Task 15: Wire DevTools tabs + `/sop` Makefile target

**Files:**
- Modify: `frontend/src/devtools/DevToolsPanel.tsx`
- Modify: `Makefile`
- Test:   existing tests remain green

- [ ] **Step 1: Update `DevToolsPanel.tsx` to include all 4 SOP views as tabs**

Read existing file; locate the tab rendering section. Add new tab IDs:

```tsx
// inside DevToolsPanel.tsx imports
import { SessionReplay } from './sop/SessionReplay';
import { JudgeVariance } from './sop/JudgeVariance';
import { PromptInspector } from './sop/PromptInspector';
import { CompactionTimeline } from './sop/CompactionTimeline';

// tab IDs: 'context' | 'sop-sessions' | 'sop-judge' | 'sop-prompt' | 'sop-timeline'
// render:
{activeTab === 'sop-sessions' && <SessionReplay />}
{activeTab === 'sop-judge' && selectedTraceId && <JudgeVariance traceId={selectedTraceId} />}
{activeTab === 'sop-prompt' && selectedTraceId && selectedStepId && (
  <PromptInspector traceId={selectedTraceId} stepId={selectedStepId} />
)}
{activeTab === 'sop-timeline' && selectedTraceId && <CompactionTimeline traceId={selectedTraceId} />}
```

If `selectedTraceId`/`selectedStepId` are not yet in state, add local state hooks at the top of the component:

```tsx
const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
```

Placeholder UI when no trace selected: `<div className="sop-empty">Select a trace from the Session Replay tab.</div>`

- [ ] **Step 2: Add `sop` target to Makefile**

Append to `Makefile`:

```makefile
# SOP
sop:
ifndef level
	$(error Usage: make sop level=<1..5>)
endif
	cd backend && uv run python -m app.sop.cli --level $(level)
```

Add `sop` to the `.PHONY` line at the top of the Makefile.

- [ ] **Step 3: Create minimal CLI `backend/app/sop/cli.py`**

```python
# backend/app/sop/cli.py
"""CLI entrypoint for /sop command. Reads latest FailureReport, runs SOP, prints proposal."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from app.sop.runner import run_sop
from app.sop.types import FailureReport


def _latest_report(reports_dir: Path, level: int) -> FailureReport:
    candidates = sorted(reports_dir.glob(f"*-level{level}.yaml"))
    if not candidates:
        raise FileNotFoundError(
            f"No FailureReport for level {level} in {reports_dir}. Run `make eval level={level}` first."
        )
    data = yaml.safe_load(candidates[-1].read_text())
    return FailureReport.model_validate(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, required=True)
    parser.add_argument("--reports-dir", default=os.environ.get("SOP_REPORTS_DIR", "tests/evals/reports"))
    args = parser.parse_args()

    report = _latest_report(Path(args.reports_dir), args.level)
    # v1: preflight inputs are empty; operator can override via env/files in later iterations.
    result = run_sop(
        report=report,
        judge_variance={},
        seed_fingerprint_matches=True,
        rerun_grades=[],
    )
    print(json.dumps(result.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write test for CLI**

```python
# backend/tests/sop/test_cli.py
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


def test_cli_prints_result_for_latest_report(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    report = {
        "level": 3, "overall_grade": "C", "dimensions": [],
        "signals": {
            "token_count": 20000, "duration_ms": 10, "compaction_events": 3,
            "scratchpad_writes": 0, "tool_errors": 0, "retries": 0,
            "subagents_spawned": 0, "models_used": {"haiku": 5, "sonnet": 2},
        },
        "judge_justifications": {}, "top_failure_signature": "x",
        "trace_id": "x", "trace_path": "x", "diff_vs_baseline": None,
    }
    (reports / "2026-04-12-level3.yaml").write_text(yaml.safe_dump(report))

    result = subprocess.run(
        [sys.executable, "-m", "app.sop.cli", "--level", "3", "--reports-dir", str(reports)],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["triage"]["bucket"] == "context"
    assert data["proposal"]["id"] == "context-01"
```

- [ ] **Step 5: Run test**

Run: `cd backend && uv run python -m pytest tests/sop/test_cli.py -v`
Expected: PASS (1 test)

- [ ] **Step 6: Run full SOP test suite**

Run: `cd backend && uv run python -m pytest tests/sop/ -v`
Expected: PASS (all tests green)

- [ ] **Step 7: Commit**

```bash
git add backend/app/sop/cli.py backend/tests/sop/test_cli.py Makefile frontend/src/devtools/DevToolsPanel.tsx
git commit -m "feat: wire SOP DevTools tabs and add /sop CLI entrypoint"
```

---

## Self-Review Notes

**Spec coverage:**
- FailureReport contract → Task 1 (types) + Task 4 (builder) ✓
- Baseline snapshot → Task 2 ✓
- Iteration log schema (Option 3 — rich, includes trace_links, judge_justifications, token/cost deltas) → Task 1 (types) + Task 3 (R/W). **Note:** `token_delta`/`cost_delta` are stored inside the freeform `outcome: dict[str, Any]` in `IterationLogEntry`, not separate fields. This keeps the model future-proof but relies on convention; documented in the spec's sample entry.
- 9 buckets (6 main + 3 pre-flight) → Task 5 (ladder YAMLs) ✓
- Pre-flight logic → Task 6 ✓
- Main triage cost-ordered, stop-at-first → Task 7 ✓
- Autonomy config + graduation → Task 8 ✓
- `/sop <level>` trigger → Task 15 (CLI + Makefile) ✓
- Termination (≥B + no regression OR 3 iterations) → `should_update_baseline` in Task 2 + human decision (iteration count handled at invocation time, not automated in v1 — consistent with "Claude proposes, human approves") ✓
- 4 DevTools views in shipping order (Session Replay → Judge Variance → Prompt Inspector → Compaction Timeline) → Tasks 11, 12, 13, 14 ✓
- REST API `/api/sop/*` → Task 10 + extensions in Tasks 12/13/14 ✓

**Deferred (documented stubs, not gaps):** `compute_judge_variance`, `load_prompt_assembly`, `load_timeline` are stubs that return empty data in v1. They have working endpoints and full UI; the real implementations require trace-replay infrastructure that isn't yet built. Each stub has a TODO-style docstring explaining what the real implementation does. This is the minimum viable path per Scope B without blocking on agent-loop work that hasn't shipped.

**Placeholder scan:** searched for TBD/TODO/implement later — none remain in task bodies. Each step has either a code block or a precise command.

**Type consistency:** `Signals`, `FailureReport`, `Baseline`, `IterationLogEntry`, `LadderDefinition`, `LadderRung`, `PreflightResult`, `TriageDecision`, `FixApplied`, `SOPResult` — all defined in Task 1 or Task 9, field names match across producer (reporter.py, runner.py) and consumer (API, UI api.ts) code.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-12-eval-failure-sop.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
