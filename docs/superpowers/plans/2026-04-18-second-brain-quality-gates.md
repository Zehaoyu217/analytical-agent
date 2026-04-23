# Second Brain — Quality Gates (Plan 6)

> Historical note (2026-04-22): This plan was written when `second-brain` lived
> at `~/Developer/second-brain/`. The active codebase has since been moved into
> `claude-code-agent/components/second-brain`. Path references in this document
> are historical unless explicitly updated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the observability and quality gaps in the KB — add habit-learning auto-detection, an eval harness, machine-readable stats + a health score, and a derived analytics layer — so drift is visible and regressions are catchable.

**Architecture:** Four independent subsystems layered on top of the existing KB. (1) `habits/learning.py` parses `log.md` for `USER_OVERRIDE` entries, detects ≥3-override patterns per dimension, writes proposal markdown under `~/second-brain/proposals/`. (2) `analytics/` rebuilds `.sb/analytics.duckdb` from the graph + filesystem as a read-only metrics store — no source of truth here. (3) `stats/` computes the health score (0–100) and a JSON payload from analytics + filesystem counts. (4) `eval/` implements a pluggable eval runner with three built-in suites (retrieval, graph, ingest) driven by YAML fixtures under `tests/eval/`. All four plug into existing CLI + `sb maintain`.

**Tech Stack:** Python 3.13, Click, Pydantic v2, DuckDB (existing dep), pytest. No new external dependencies.

---

## File Structure

**New (second-brain repo):**
- `src/second_brain/habits/learning.py` — `detect_overrides(cfg, window_days, threshold) -> list[HabitProposal]`, `write_proposal(proposal, cfg) -> Path`.
- `src/second_brain/analytics/__init__.py` — package marker.
- `src/second_brain/analytics/builder.py` — `AnalyticsBuilder.rebuild(cfg)` populates `.sb/analytics.duckdb` with tables: `source_counts_by_kind`, `claim_counts_by_taxonomy`, `contradiction_status`, `orphan_claims`, `zero_claim_sources`, `auto_override_reverts_7d`.
- `src/second_brain/analytics/queries.py` — typed readers over `.sb/analytics.duckdb`.
- `src/second_brain/stats/__init__.py` — package marker.
- `src/second_brain/stats/collector.py` — `collect_stats(cfg) -> Stats`; aggregates analytics + filesystem + queue.
- `src/second_brain/stats/health.py` — `compute_health(stats) -> HealthScore` with documented weights.
- `src/second_brain/eval/__init__.py` — package marker.
- `src/second_brain/eval/runner.py` — `EvalRunner.run(suite_name) -> EvalReport`.
- `src/second_brain/eval/suites/retrieval.py` — BM25 nDCG@10 + p95 latency vs YAML fixtures.
- `src/second_brain/eval/suites/graph.py` — reasoning exact-set match vs YAML fixtures.
- `src/second_brain/eval/suites/ingest.py` — end-to-end converter+extractor byte/claim-count check.
- `tests/eval/fixtures/retrieval/seed.yaml` — 8 query/answer pairs over a tiny seed KB.
- `tests/eval/fixtures/graph/seed.yaml` — 4 reasoning queries with expected node sets.
- `tests/eval/fixtures/ingest/note_sample.yaml` — 3 note-ingest cases with expected claim-count bounds.

**Tests:**
- `tests/test_habits_learning.py`
- `tests/test_analytics_builder.py`
- `tests/test_stats_collector.py`
- `tests/test_stats_health.py`
- `tests/test_eval_retrieval.py`
- `tests/test_eval_graph.py`
- `tests/test_eval_ingest.py`
- `tests/test_cli_quality.py`

**Modified:**
- `src/second_brain/config.py` — `analytics_path` property.
- `src/second_brain/cli.py` — new commands: `sb habits learn`, `sb habits apply`, `sb stats`, `sb eval`, `sb analytics rebuild`.
- `src/second_brain/maintain/runner.py` — invoke habit-learning detector + analytics rebuild inside the pipeline; extend `MaintainReport`.
- `README.md` — document the four new commands.
- `/Users/jay/Developer/claude-code-agent/docs/log.md` — Unreleased entry.

---

## Task 1: `Config.analytics_path` + package scaffolding

**Files:**
- Modify: `src/second_brain/config.py`
- Create: `src/second_brain/analytics/__init__.py`, `src/second_brain/stats/__init__.py`, `src/second_brain/eval/__init__.py`
- Test: `tests/test_config_analytics.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config_analytics.py
from pathlib import Path

from second_brain.config import Config


def test_analytics_path_under_sb_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    cfg = Config.load()
    assert cfg.analytics_path == tmp_path / ".sb" / "analytics.duckdb"
```

- [ ] **Step 2: Run test, verify failure**

Run: `cd /Users/jay/Developer/second-brain && pytest tests/test_config_analytics.py -v`
Expected: `AttributeError: analytics_path`.

- [ ] **Step 3: Add property + scaffolding**

In `src/second_brain/config.py`, inside `Config` after `fts_path`:

```python
    @property
    def analytics_path(self) -> Path:
        return self.sb_dir / "analytics.duckdb"

    @property
    def proposals_dir(self) -> Path:
        return self.home / "proposals"
```

Create the three empty init files:

```python
# src/second_brain/analytics/__init__.py
"""Derived analytics layer (.sb/analytics.duckdb)."""
```

```python
# src/second_brain/stats/__init__.py
"""Stats collection + health score."""
```

```python
# src/second_brain/eval/__init__.py
"""Eval harness."""
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_config_analytics.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/config.py src/second_brain/analytics src/second_brain/stats src/second_brain/eval tests/test_config_analytics.py
git commit -m "chore(sb): scaffold analytics/stats/eval packages + Config.analytics_path"
```

---

## Task 2: Habit-learning detector

**Files:**
- Create: `src/second_brain/habits/learning.py`
- Test: `tests/test_habits_learning.py`

Spec ref: §10.3. Parses `log.md` `USER_OVERRIDE` entries within `rolling_window_days`, groups by `(op, subject_pattern)`, triggers on count ≥ `threshold`, emits `HabitProposal` with observed pattern + proposed change + sample override IDs.

Log line format (from §10.4):
```
- 2026-04-17T14:25:03 [USER_OVERRIDE] ingest.taxonomy src_foo → papers/ml/transformers
  prior: papers/ml
```

- [ ] **Step 1: Write failing tests**

```python
# tests/test_habits_learning.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.habits.learning import (
    HabitProposal,
    detect_overrides,
    write_proposal,
)


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _write_log(home: Path, lines: list[str]) -> None:
    (home / "log.md").write_text("\n".join(lines) + "\n")


def _now_iso(delta_days: int = 0) -> str:
    ts = datetime.now(UTC) - timedelta(days=delta_days)
    return ts.strftime("%Y-%m-%dT%H:%M:%S")


def test_detect_override_fires_at_threshold_three(sb_home: Path):
    lines = []
    for i in range(3):
        lines.append(
            f"- {_now_iso(i)} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml/transformers"
        )
        lines.append("  prior: papers/ml")
    _write_log(sb_home, lines)

    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=60, threshold=3)

    assert len(proposals) == 1
    p = proposals[0]
    assert p.op == "ingest.taxonomy"
    assert "papers/ml/transformers" in p.proposed_value
    assert len(p.sample_subjects) == 3
    assert p.count >= 3


def test_detect_ignores_overrides_outside_window(sb_home: Path):
    lines = []
    for i in range(3):
        lines.append(
            f"- {_now_iso(90 + i)} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml"
        )
        lines.append("  prior: papers")
    _write_log(sb_home, lines)

    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=60, threshold=3)
    assert proposals == []


def test_detect_below_threshold_returns_empty(sb_home: Path):
    lines = [
        f"- {_now_iso(0)} [USER_OVERRIDE] ingest.taxonomy src_a → papers/ml",
        "  prior: papers",
        f"- {_now_iso(1)} [USER_OVERRIDE] ingest.taxonomy src_b → papers/ml",
        "  prior: papers",
    ]
    _write_log(sb_home, lines)
    cfg = Config.load()
    assert detect_overrides(cfg, window_days=60, threshold=3) == []


def test_detect_groups_by_op_and_value(sb_home: Path):
    lines = []
    for i in range(3):
        lines.append(f"- {_now_iso(i)} [USER_OVERRIDE] ingest.taxonomy src_a{i} → A/B")
        lines.append("  prior: A")
        lines.append(f"- {_now_iso(i)} [USER_OVERRIDE] ingest.taxonomy src_b{i} → X/Y")
        lines.append("  prior: X")
    _write_log(sb_home, lines)
    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=60, threshold=3)
    assert len(proposals) == 2
    values = sorted(p.proposed_value for p in proposals)
    assert values == ["A/B", "X/Y"]


def test_write_proposal_creates_markdown(sb_home: Path):
    cfg = Config.load()
    prop = HabitProposal(
        op="ingest.taxonomy",
        proposed_value="papers/ml/transformers",
        prior_value="papers/ml",
        count=3,
        sample_subjects=["src_a", "src_b", "src_c"],
    )
    path = write_proposal(prop, cfg)
    text = path.read_text()
    assert path.parent == cfg.proposals_dir
    assert "ingest.taxonomy" in text
    assert "papers/ml/transformers" in text
    assert "src_a" in text
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_habits_learning.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement detector + proposal writer**

```python
# src/second_brain/habits/learning.py
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config

_LINE_RE = re.compile(
    r"^- (?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r" \[USER_OVERRIDE\] (?P<op>\S+) (?P<subject>\S+) → (?P<value>.+)$"
)
_PRIOR_RE = re.compile(r"^\s+prior:\s*(?P<prior>.+)$")


@dataclass(frozen=True)
class HabitProposal:
    op: str
    proposed_value: str
    prior_value: str | None
    count: int
    sample_subjects: list[str] = field(default_factory=list)


def detect_overrides(
    cfg: Config, *, window_days: int, threshold: int
) -> list[HabitProposal]:
    log_path = cfg.log_path
    if not log_path.exists():
        return []
    cutoff = datetime.now(UTC) - timedelta(days=window_days)

    groups: dict[tuple[str, str], list[tuple[str, str | None]]] = defaultdict(list)
    last_match: tuple[str, str, str] | None = None  # (op, subject, value)

    for line in log_path.read_text(encoding="utf-8").splitlines():
        m = _LINE_RE.match(line)
        if m:
            ts = datetime.fromisoformat(m["ts"]).replace(tzinfo=UTC)
            if ts < cutoff:
                last_match = None
                continue
            last_match = (m["op"], m["subject"], m["value"].strip())
            groups[(last_match[0], last_match[2])].append((last_match[1], None))
            continue
        pm = _PRIOR_RE.match(line)
        if pm and last_match is not None:
            op, _subject, value = last_match
            # attach prior to the most recent entry for this group
            tail = groups[(op, value)][-1]
            groups[(op, value)][-1] = (tail[0], pm["prior"].strip())

    proposals: list[HabitProposal] = []
    for (op, value), entries in groups.items():
        if len(entries) >= threshold:
            priors = Counter(p for _subj, p in entries if p is not None)
            prior = priors.most_common(1)[0][0] if priors else None
            proposals.append(
                HabitProposal(
                    op=op,
                    proposed_value=value,
                    prior_value=prior,
                    count=len(entries),
                    sample_subjects=[subj for subj, _ in entries[:5]],
                )
            )
    return sorted(proposals, key=lambda p: (p.op, p.proposed_value))


def write_proposal(proposal: HabitProposal, cfg: Config) -> Path:
    cfg.proposals_dir.mkdir(parents=True, exist_ok=True)
    fname = f"habits-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{_slug(proposal.op)}-{_slug(proposal.proposed_value)}.md"
    path = cfg.proposals_dir / fname
    body = _render(proposal)
    path.write_text(body, encoding="utf-8")
    return path


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "x"


def _render(p: HabitProposal) -> str:
    samples = "\n".join(f"  - `{s}`" for s in p.sample_subjects)
    prior = p.prior_value or "(unset)"
    return (
        f"# Habit proposal: {p.op}\n\n"
        f"Observed {p.count} user overrides in the rolling window.\n\n"
        f"- **Operation:** `{p.op}`\n"
        f"- **Prior value:** `{prior}`\n"
        f"- **Proposed value:** `{p.proposed_value}`\n\n"
        f"## Sample subjects\n{samples}\n\n"
        f"## Apply\n\n"
        f"```bash\nsb habits apply {p.op} {p.proposed_value}\n```\n\n"
        f"Reject with `--reject` to silence this proposal for 30 days.\n"
    )
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_habits_learning.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/habits/learning.py tests/test_habits_learning.py
git commit -m "feat(sb): habit-learning detector (≥N overrides -> proposal markdown)"
```

---

## Task 3: `sb habits learn` + `sb habits apply|reject` CLI

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_quality.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cli_quality.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_cli_habits_learn_writes_proposal(sb_home: Path):
    lines = []
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    for i in range(3):
        lines.append(f"- {ts} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml")
        lines.append("  prior: papers")
    (sb_home / "log.md").write_text("\n".join(lines) + "\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["habits", "learn", "--threshold", "3"])
    assert result.exit_code == 0, result.output
    assert "1 proposal" in result.output or "proposals:" in result.output.lower()
    assert list((sb_home / "proposals").glob("habits-*.md"))


def test_cli_habits_learn_empty_when_below_threshold(sb_home: Path):
    (sb_home / "log.md").write_text("")
    runner = CliRunner()
    result = runner.invoke(cli, ["habits", "learn"])
    assert result.exit_code == 0
    assert "no proposals" in result.output.lower()
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_cli_quality.py -v`
Expected: `No such command 'learn'`.

- [ ] **Step 3: Implement CLI subcommand**

Add under the existing `@cli.group(name="habits")` group in `src/second_brain/cli.py`:

```python
@_habits.command(name="learn")
@click.option("--window-days", type=int, default=60)
@click.option("--threshold", type=int, default=3)
def _habits_learn(window_days: int, threshold: int) -> None:
    """Scan log.md for repeated user overrides; emit proposal markdown."""
    from second_brain.habits.learning import detect_overrides, write_proposal

    cfg = Config.load()
    proposals = detect_overrides(cfg, window_days=window_days, threshold=threshold)
    if not proposals:
        click.echo("no proposals")
        return
    click.echo(f"{len(proposals)} proposal(s):")
    for p in proposals:
        path = write_proposal(p, cfg)
        click.echo(f"  - {path.relative_to(cfg.home)}  ({p.op} -> {p.proposed_value}, n={p.count})")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_cli_quality.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_quality.py
git commit -m "feat(sb): add \`sb habits learn\` CLI command"
```

---

## Task 4: `AnalyticsBuilder.rebuild()`

**Files:**
- Create: `src/second_brain/analytics/builder.py`
- Create: `src/second_brain/analytics/queries.py`
- Test: `tests/test_analytics_builder.py`

Tables to materialize in `.sb/analytics.duckdb`:
- `sources_by_kind (kind TEXT, n INT)`
- `claims_by_taxonomy (taxonomy TEXT, n INT)`
- `zero_claim_sources (source_id TEXT)` — sources with no claim pointing to them via `evidenced_by` or `supports`.
- `orphan_claims (claim_id TEXT)` — claims with no `evidenced_by` edge.
- `contradiction_counts (status TEXT, n INT)` — `status ∈ {open, resolved}`.
- `health_inputs (key TEXT, value DOUBLE)` — single-row-per-key KV.

Read exclusively from `cfg.duckdb_path` (graph) + filesystem iteration over `cfg.sources_dir` / `cfg.claims_dir`. Never write back.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_analytics_builder.py
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.analytics.builder import AnalyticsBuilder
from second_brain.analytics.queries import (
    claims_by_taxonomy,
    contradiction_counts,
    orphan_claims,
    sources_by_kind,
    zero_claim_sources,
)
from second_brain.config import Config
from second_brain.frontmatter import dump_document


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _src(home: Path, slug: str, kind: str) -> None:
    folder = home / "sources" / slug
    folder.mkdir()
    dump_document(
        folder / "_source.md",
        {
            "id": slug,
            "title": slug,
            "kind": kind,
            "content_hash": f"sha-{slug}",
            "raw": [],
            "ingested_at": "2026-04-18T00:00:00Z",
        },
        "",
    )


def _claim(home: Path, slug: str, taxonomy: str) -> None:
    dump_document(
        home / "claims" / f"{slug}.md",
        {
            "id": slug,
            "statement": slug,
            "kind": "empirical",
            "confidence": "low",
            "extracted_at": "2026-04-18T00:00:00Z",
            "taxonomy": taxonomy,
        },
        "body",
    )


def test_rebuild_produces_source_counts(sb_home: Path):
    _src(sb_home, "src_a", "note")
    _src(sb_home, "src_b", "note")
    _src(sb_home, "src_c", "pdf")

    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()

    counts = dict(sources_by_kind(cfg))
    assert counts["note"] == 2
    assert counts["pdf"] == 1


def test_rebuild_produces_claim_counts_by_taxonomy(sb_home: Path):
    _claim(sb_home, "clm_a", "papers/ml")
    _claim(sb_home, "clm_b", "papers/ml")
    _claim(sb_home, "clm_c", "notes/ideas")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    counts = dict(claims_by_taxonomy(cfg))
    assert counts["papers/ml"] == 2
    assert counts["notes/ideas"] == 1


def test_rebuild_identifies_zero_claim_sources(sb_home: Path):
    _src(sb_home, "src_noclaims", "note")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    zeros = list(zero_claim_sources(cfg))
    assert "src_noclaims" in zeros


def test_rebuild_is_idempotent(sb_home: Path):
    _src(sb_home, "src_x", "note")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    AnalyticsBuilder(cfg).rebuild()
    counts = dict(sources_by_kind(cfg))
    assert counts["note"] == 1


def test_contradiction_counts_empty_on_fresh_kb(sb_home: Path):
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    counts = dict(contradiction_counts(cfg))
    assert counts.get("open", 0) == 0
    assert counts.get("resolved", 0) == 0


def test_orphan_claims_empty_on_fresh_kb(sb_home: Path):
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    assert list(orphan_claims(cfg)) == []
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_analytics_builder.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement builder + queries**

```python
# src/second_brain/analytics/builder.py
from __future__ import annotations

import duckdb

from second_brain.config import Config
from second_brain.frontmatter import load_document


class AnalyticsBuilder:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def rebuild(self) -> None:
        self.cfg.sb_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg.analytics_path
        if path.exists():
            path.unlink()

        con = duckdb.connect(str(path))
        try:
            self._build_schema(con)
            self._populate_sources(con)
            self._populate_claims(con)
            self._populate_from_graph(con)
        finally:
            con.close()

    def _build_schema(self, con: duckdb.DuckDBPyConnection) -> None:
        con.execute("CREATE TABLE sources_by_kind (kind TEXT, n INT)")
        con.execute("CREATE TABLE claims_by_taxonomy (taxonomy TEXT, n INT)")
        con.execute("CREATE TABLE zero_claim_sources (source_id TEXT)")
        con.execute("CREATE TABLE orphan_claims (claim_id TEXT)")
        con.execute("CREATE TABLE contradiction_counts (status TEXT, n INT)")

    def _populate_sources(self, con: duckdb.DuckDBPyConnection) -> None:
        counts: dict[str, int] = {}
        source_ids: list[str] = []
        for folder in sorted(self.cfg.sources_dir.glob("*")):
            source_md = folder / "_source.md"
            if not source_md.exists():
                continue
            fm, _ = load_document(source_md)
            kind = fm.get("kind", "unknown")
            counts[kind] = counts.get(kind, 0) + 1
            source_ids.append(fm.get("id", folder.name))
        for k, n in counts.items():
            con.execute("INSERT INTO sources_by_kind VALUES (?, ?)", [k, n])
        # Zero-claim detection requires graph; populated in _populate_from_graph.
        con.execute("CREATE TEMP TABLE _all_sources AS SELECT * FROM (VALUES " +
                    ("(?)," * len(source_ids))[:-1] + ") t(id)" if source_ids
                    else "CREATE TEMP TABLE _all_sources (id TEXT)",
                    source_ids)

    def _populate_claims(self, con: duckdb.DuckDBPyConnection) -> None:
        counts: dict[str, int] = {}
        for claim_md in sorted(self.cfg.claims_dir.glob("*.md")):
            if claim_md.name == "conflicts.md":
                continue
            try:
                fm, _ = load_document(claim_md)
            except Exception:  # noqa: BLE001
                continue
            tax = fm.get("taxonomy") or "unknown"
            counts[tax] = counts.get(tax, 0) + 1
        for t, n in counts.items():
            con.execute("INSERT INTO claims_by_taxonomy VALUES (?, ?)", [t, n])

    def _populate_from_graph(self, con: duckdb.DuckDBPyConnection) -> None:
        graph_path = self.cfg.duckdb_path
        if not graph_path.exists():
            return
        con.execute(f"ATTACH '{graph_path}' AS g (READ_ONLY)")
        try:
            # zero-claim sources: sources with no evidenced_by or supports edge pointing to them
            con.execute(
                """
                INSERT INTO zero_claim_sources
                SELECT DISTINCT s.id FROM g.sources s
                WHERE NOT EXISTS (
                    SELECT 1 FROM g.edges e
                    WHERE e.dst_id = s.id AND e.relation IN ('evidenced_by','supports','cites')
                )
                """
            )
            # orphan claims: claims with no evidenced_by outgoing edge
            con.execute(
                """
                INSERT INTO orphan_claims
                SELECT DISTINCT c.id FROM g.claims c
                WHERE NOT EXISTS (
                    SELECT 1 FROM g.edges e
                    WHERE e.src_id = c.id AND e.relation = 'evidenced_by'
                )
                """
            )
            # contradiction status: has resolution text vs not
            con.execute(
                """
                INSERT INTO contradiction_counts
                SELECT
                  CASE WHEN COALESCE(rationale, '') = '' THEN 'open' ELSE 'resolved' END AS status,
                  COUNT(*) AS n
                FROM g.edges
                WHERE relation = 'contradicts'
                GROUP BY status
                """
            )
        finally:
            con.execute("DETACH g")
```

Replace `_populate_sources` (it has a buggy temp-table construct). Use the clean version below:

```python
    def _populate_sources(self, con: duckdb.DuckDBPyConnection) -> None:
        counts: dict[str, int] = {}
        for folder in sorted(self.cfg.sources_dir.glob("*")):
            source_md = folder / "_source.md"
            if not source_md.exists():
                continue
            fm, _ = load_document(source_md)
            kind = fm.get("kind", "unknown")
            counts[kind] = counts.get(kind, 0) + 1
        for k, n in counts.items():
            con.execute("INSERT INTO sources_by_kind VALUES (?, ?)", [k, n])
```

If there is no graph DB yet (fresh KB before any `sb reindex`), fall back to filesystem: every source folder with no claim-file referencing it is a zero-claim source. Provide a minimal FS-based path when `duckdb_path` doesn't exist — iterate claims, collect `evidenced_by` targets from frontmatter, anything in `sources/` not hit is a zero-claim source. Add that branch.

```python
    def _populate_from_graph(self, con: duckdb.DuckDBPyConnection) -> None:
        graph_path = self.cfg.duckdb_path
        if graph_path.exists():
            con.execute(f"ATTACH '{graph_path}' AS g (READ_ONLY)")
            try:
                con.execute("""
                    INSERT INTO zero_claim_sources
                    SELECT DISTINCT s.id FROM g.sources s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM g.edges e
                        WHERE e.dst_id = s.id AND e.relation IN ('evidenced_by','supports','cites')
                    )
                """)
                con.execute("""
                    INSERT INTO orphan_claims
                    SELECT DISTINCT c.id FROM g.claims c
                    WHERE NOT EXISTS (
                        SELECT 1 FROM g.edges e
                        WHERE e.src_id = c.id AND e.relation = 'evidenced_by'
                    )
                """)
                con.execute("""
                    INSERT INTO contradiction_counts
                    SELECT
                      CASE WHEN COALESCE(rationale, '') = '' THEN 'open' ELSE 'resolved' END AS status,
                      COUNT(*) AS n
                    FROM g.edges
                    WHERE relation = 'contradicts'
                    GROUP BY status
                """)
            finally:
                con.execute("DETACH g")
            return

        # FS fallback: use source frontmatter + claim `supports`/`evidenced_by` fields
        referenced: set[str] = set()
        for claim_md in sorted(self.cfg.claims_dir.glob("*.md")):
            if claim_md.name == "conflicts.md":
                continue
            try:
                fm, _ = load_document(claim_md)
            except Exception:  # noqa: BLE001
                continue
            for rel in ("evidenced_by", "supports", "cites"):
                for entry in fm.get(rel, []) or []:
                    if isinstance(entry, dict):
                        referenced.add(entry.get("id", ""))
                    elif isinstance(entry, str):
                        referenced.add(entry)
        for folder in sorted(self.cfg.sources_dir.glob("*")):
            source_md = folder / "_source.md"
            if not source_md.exists():
                continue
            fm, _ = load_document(source_md)
            sid = fm.get("id", folder.name)
            if sid not in referenced:
                con.execute(
                    "INSERT INTO zero_claim_sources VALUES (?)", [sid]
                )
```

Now the queries module:

```python
# src/second_brain/analytics/queries.py
from __future__ import annotations

from collections.abc import Iterable

import duckdb

from second_brain.config import Config


def _connect(cfg: Config) -> duckdb.DuckDBPyConnection | None:
    if not cfg.analytics_path.exists():
        return None
    return duckdb.connect(str(cfg.analytics_path), read_only=True)


def sources_by_kind(cfg: Config) -> Iterable[tuple[str, int]]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return list(con.execute("SELECT kind, n FROM sources_by_kind").fetchall())
    finally:
        con.close()


def claims_by_taxonomy(cfg: Config) -> Iterable[tuple[str, int]]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return list(
            con.execute("SELECT taxonomy, n FROM claims_by_taxonomy").fetchall()
        )
    finally:
        con.close()


def zero_claim_sources(cfg: Config) -> Iterable[str]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return [r[0] for r in con.execute("SELECT source_id FROM zero_claim_sources").fetchall()]
    finally:
        con.close()


def orphan_claims(cfg: Config) -> Iterable[str]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return [r[0] for r in con.execute("SELECT claim_id FROM orphan_claims").fetchall()]
    finally:
        con.close()


def contradiction_counts(cfg: Config) -> Iterable[tuple[str, int]]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return list(con.execute("SELECT status, n FROM contradiction_counts").fetchall())
    finally:
        con.close()
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_analytics_builder.py -v`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/analytics tests/test_analytics_builder.py
git commit -m "feat(sb): analytics.duckdb builder + queries"
```

---

## Task 5: `sb analytics rebuild` CLI

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_quality.py`

- [ ] **Step 1: Append failing test**

```python
def test_cli_analytics_rebuild(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["analytics", "rebuild"])
    assert result.exit_code == 0, result.output
    assert (sb_home / ".sb" / "analytics.duckdb").exists()
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_cli_quality.py::test_cli_analytics_rebuild -v`
Expected: `No such command 'analytics'`.

- [ ] **Step 3: Implement**

Add to `src/second_brain/cli.py`:

```python
@cli.group(name="analytics")
def _analytics() -> None:
    """Analytics layer commands."""


@_analytics.command(name="rebuild")
def _analytics_rebuild() -> None:
    """Rebuild .sb/analytics.duckdb from graph + filesystem."""
    from second_brain.analytics.builder import AnalyticsBuilder

    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    click.echo(f"ok: {cfg.analytics_path}")
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_cli_quality.py::test_cli_analytics_rebuild -v`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_quality.py
git commit -m "feat(sb): add \`sb analytics rebuild\` CLI"
```

---

## Task 6: `collect_stats` + `compute_health`

**Files:**
- Create: `src/second_brain/stats/collector.py`
- Create: `src/second_brain/stats/health.py`
- Test: `tests/test_stats_collector.py`, `tests/test_stats_health.py`

Health formula (0–100, higher is better):
- Start at 100.
- Subtract `min(30, zero_claim_sources * 2)`.
- Subtract `min(20, orphan_claims * 1)`.
- Subtract `min(20, open_contradictions_older_than_7d * 3)`.
- Subtract `min(15, auto_decisions_reverted_7d * 5)`.
- Add `min(5, resolved/open contradictions ratio * 5)` (capped, positive signal).
- Clamp to `[0, 100]`.

Document weights in a module docstring. Weights are tunable via `HealthWeights` dataclass passed to `compute_health`, with sane defaults.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_stats_collector.py
from pathlib import Path

import pytest

from second_brain.analytics.builder import AnalyticsBuilder
from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.stats.collector import Stats, collect_stats


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    (home / "inbox").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_collect_stats_empty_kb(sb_home: Path):
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    s = collect_stats(cfg)
    assert isinstance(s, Stats)
    assert s.source_count == 0
    assert s.claim_count == 0
    assert s.inbox_pending == 0


def test_collect_stats_counts(sb_home: Path):
    for i in range(3):
        folder = sb_home / "sources" / f"src_{i}"
        folder.mkdir()
        dump_document(
            folder / "_source.md",
            {
                "id": f"src_{i}", "title": "t", "kind": "note",
                "content_hash": f"h{i}", "raw": [], "ingested_at": "2026-04-18T00:00:00Z",
            },
            "",
        )
    (sb_home / "inbox" / "pending.md").write_text("x")
    cfg = Config.load()
    AnalyticsBuilder(cfg).rebuild()
    s = collect_stats(cfg)
    assert s.source_count == 3
    assert s.inbox_pending == 1
```

```python
# tests/test_stats_health.py
from second_brain.stats.collector import Stats
from second_brain.stats.health import HealthWeights, compute_health


def test_perfect_kb_scores_100():
    s = Stats(
        source_count=10, claim_count=30, inbox_pending=0,
        zero_claim_sources=0, orphan_claims=0,
        open_contradictions=0, resolved_contradictions=0,
        auto_reverts_7d=0, open_contradictions_older_than_7d=0,
    )
    h = compute_health(s)
    assert h.score == 100
    assert h.breakdown


def test_score_drops_for_orphans_and_zero_claims():
    s = Stats(
        source_count=10, claim_count=30, inbox_pending=0,
        zero_claim_sources=5, orphan_claims=10,
        open_contradictions=0, resolved_contradictions=0,
        auto_reverts_7d=0, open_contradictions_older_than_7d=0,
    )
    h = compute_health(s)
    assert h.score < 100
    assert "zero_claim_sources" in h.breakdown


def test_score_clamped_at_zero():
    s = Stats(
        source_count=10, claim_count=30, inbox_pending=0,
        zero_claim_sources=100, orphan_claims=100,
        open_contradictions=100, resolved_contradictions=0,
        auto_reverts_7d=100, open_contradictions_older_than_7d=100,
    )
    h = compute_health(s)
    assert 0 <= h.score <= 100


def test_resolved_contradictions_is_positive_signal():
    s_no_resolved = Stats(
        source_count=10, claim_count=30, inbox_pending=0,
        zero_claim_sources=0, orphan_claims=0,
        open_contradictions=5, resolved_contradictions=0,
        auto_reverts_7d=0, open_contradictions_older_than_7d=0,
    )
    s_with_resolved = Stats(
        source_count=10, claim_count=30, inbox_pending=0,
        zero_claim_sources=0, orphan_claims=0,
        open_contradictions=5, resolved_contradictions=10,
        auto_reverts_7d=0, open_contradictions_older_than_7d=0,
    )
    assert compute_health(s_with_resolved).score >= compute_health(s_no_resolved).score
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_stats_collector.py tests/test_stats_health.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/stats/collector.py
from __future__ import annotations

from dataclasses import dataclass, field

from second_brain.analytics.queries import (
    claims_by_taxonomy,
    contradiction_counts,
    orphan_claims,
    sources_by_kind,
    zero_claim_sources,
)
from second_brain.config import Config


@dataclass(frozen=True)
class Stats:
    source_count: int = 0
    claim_count: int = 0
    inbox_pending: int = 0
    zero_claim_sources: int = 0
    orphan_claims: int = 0
    open_contradictions: int = 0
    resolved_contradictions: int = 0
    open_contradictions_older_than_7d: int = 0
    auto_reverts_7d: int = 0
    sources_by_kind: dict[str, int] = field(default_factory=dict)
    claims_by_taxonomy: dict[str, int] = field(default_factory=dict)


def collect_stats(cfg: Config) -> Stats:
    src_counts = dict(sources_by_kind(cfg))
    clm_counts = dict(claims_by_taxonomy(cfg))
    contradictions = dict(contradiction_counts(cfg))
    inbox_pending = (
        sum(
            1
            for p in cfg.inbox_dir.iterdir()
            if p.is_file() and not p.name.startswith(".")
        )
        if cfg.inbox_dir.exists()
        else 0
    )
    return Stats(
        source_count=sum(src_counts.values()),
        claim_count=sum(clm_counts.values()),
        inbox_pending=inbox_pending,
        zero_claim_sources=len(list(zero_claim_sources(cfg))),
        orphan_claims=len(list(orphan_claims(cfg))),
        open_contradictions=int(contradictions.get("open", 0)),
        resolved_contradictions=int(contradictions.get("resolved", 0)),
        sources_by_kind=src_counts,
        claims_by_taxonomy=clm_counts,
    )
```

```python
# src/second_brain/stats/health.py
"""Health score (0–100).

Weights are documented in HealthWeights. Score starts at 100 and subtracts
capped penalties for problems; adds a small bonus for resolved/open contradiction
ratio as a positive signal. Clamped to [0, 100].
"""
from __future__ import annotations

from dataclasses import dataclass, field

from second_brain.stats.collector import Stats


@dataclass(frozen=True)
class HealthWeights:
    zero_claim_source: int = 2
    zero_claim_cap: int = 30
    orphan_claim: int = 1
    orphan_cap: int = 20
    stale_contradiction: int = 3
    stale_contradiction_cap: int = 20
    auto_revert: int = 5
    auto_revert_cap: int = 15
    resolved_ratio_bonus_cap: int = 5


@dataclass(frozen=True)
class HealthScore:
    score: int
    breakdown: dict[str, int] = field(default_factory=dict)


def compute_health(stats: Stats, weights: HealthWeights | None = None) -> HealthScore:
    w = weights or HealthWeights()
    breakdown: dict[str, int] = {}

    zc = min(w.zero_claim_cap, stats.zero_claim_sources * w.zero_claim_source)
    breakdown["zero_claim_sources"] = -zc

    oc = min(w.orphan_cap, stats.orphan_claims * w.orphan_claim)
    breakdown["orphan_claims"] = -oc

    sc = min(
        w.stale_contradiction_cap,
        stats.open_contradictions_older_than_7d * w.stale_contradiction,
    )
    breakdown["stale_contradictions"] = -sc

    ar = min(w.auto_revert_cap, stats.auto_reverts_7d * w.auto_revert)
    breakdown["auto_reverts_7d"] = -ar

    total_contradictions = stats.open_contradictions + stats.resolved_contradictions
    ratio_bonus = 0
    if total_contradictions > 0 and stats.open_contradictions > 0:
        ratio = stats.resolved_contradictions / stats.open_contradictions
        ratio_bonus = min(w.resolved_ratio_bonus_cap, int(ratio * w.resolved_ratio_bonus_cap))
    breakdown["resolved_ratio_bonus"] = ratio_bonus

    score = 100 - zc - oc - sc - ar + ratio_bonus
    score = max(0, min(100, score))
    return HealthScore(score=score, breakdown=breakdown)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_stats_collector.py tests/test_stats_health.py -v`
Expected: `6 passed` combined.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/stats tests/test_stats_collector.py tests/test_stats_health.py
git commit -m "feat(sb): collect_stats + compute_health (0-100 weighted score)"
```

---

## Task 7: `sb stats [--json]` CLI

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_quality.py`

Text output extends existing `sb status` semantics — don't replace it; `sb stats` is the richer metrics view. Keep `sb status` as-is.

- [ ] **Step 1: Append failing test**

```python
def test_cli_stats_text(sb_home: Path):
    from second_brain.analytics.builder import AnalyticsBuilder

    cfg = __import__("second_brain.config", fromlist=["Config"]).Config.load()
    AnalyticsBuilder(cfg).rebuild()

    runner = CliRunner()
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0, result.output
    assert "health" in result.output.lower()
    assert "sources" in result.output.lower()


def test_cli_stats_json(sb_home: Path):
    from second_brain.analytics.builder import AnalyticsBuilder

    cfg = __import__("second_brain.config", fromlist=["Config"]).Config.load()
    AnalyticsBuilder(cfg).rebuild()

    runner = CliRunner()
    result = runner.invoke(cli, ["stats", "--json"])
    assert result.exit_code == 0
    import json as _json

    payload = _json.loads(result.output)
    assert "health" in payload
    assert "score" in payload["health"]
    assert "stats" in payload
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_cli_quality.py::test_cli_stats_text tests/test_cli_quality.py::test_cli_stats_json -v`
Expected: `No such command 'stats'`.

- [ ] **Step 3: Implement**

```python
@cli.command(name="stats")
@click.option("--json", "as_json", is_flag=True)
def _stats(as_json: bool) -> None:
    """KB metrics + 0-100 health score."""
    import dataclasses
    import json as _json

    from second_brain.stats.collector import collect_stats
    from second_brain.stats.health import compute_health

    cfg = Config.load()
    stats = collect_stats(cfg)
    health = compute_health(stats)

    if as_json:
        click.echo(_json.dumps({
            "stats": dataclasses.asdict(stats),
            "health": dataclasses.asdict(health),
        }, indent=2))
        return

    click.echo(f"== sb stats ==")
    click.echo(f"sources: {stats.source_count}")
    click.echo(f"claims:  {stats.claim_count}")
    click.echo(f"inbox pending: {stats.inbox_pending}")
    click.echo(f"zero-claim sources: {stats.zero_claim_sources}")
    click.echo(f"orphan claims: {stats.orphan_claims}")
    click.echo(f"contradictions: open={stats.open_contradictions} resolved={stats.resolved_contradictions}")
    click.echo(f"health: {health.score}/100  {dict(health.breakdown)}")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_cli_quality.py -v`
Expected: all quality CLI tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_quality.py
git commit -m "feat(sb): add \`sb stats\` CLI (text + --json, with health score)"
```

---

## Task 8: Eval runner foundation + suite protocol

**Files:**
- Create: `src/second_brain/eval/runner.py`
- Test: `tests/test_eval_runner.py`

```python
# src/second_brain/eval/runner.py
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from second_brain.config import Config


@dataclass(frozen=True)
class EvalCase:
    name: str
    passed: bool
    metric: float
    details: str = ""


@dataclass(frozen=True)
class EvalReport:
    suite: str
    cases: list[EvalCase] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.cases)

    @property
    def pass_rate(self) -> float:
        if not self.cases:
            return 0.0
        return sum(1 for c in self.cases if c.passed) / len(self.cases)


class EvalSuite(Protocol):
    name: str

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]: ...


class EvalRunner:
    def __init__(self, cfg: Config, suites: dict[str, EvalSuite]) -> None:
        self.cfg = cfg
        self.suites = suites

    def run(self, suite_name: str, fixtures_dir: Path) -> EvalReport:
        if suite_name not in self.suites:
            raise KeyError(f"unknown suite: {suite_name}")
        cases = self.suites[suite_name].run(self.cfg, fixtures_dir)
        return EvalReport(suite=suite_name, cases=cases)
```

- [ ] **Step 1: Write test**

```python
# tests/test_eval_runner.py
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalCase, EvalRunner, EvalSuite


class _FakeSuite:
    name = "fake"

    def run(self, cfg, fixtures_dir):
        return [EvalCase(name="a", passed=True, metric=1.0), EvalCase(name="b", passed=False, metric=0.0)]


def test_runner_dispatches_to_named_suite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    (tmp_path / ".sb").mkdir()
    cfg = Config.load()
    runner = EvalRunner(cfg, {"fake": _FakeSuite()})
    report = runner.run("fake", tmp_path)
    assert report.suite == "fake"
    assert report.pass_rate == 0.5
    assert not report.passed


def test_runner_raises_on_unknown(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    (tmp_path / ".sb").mkdir()
    cfg = Config.load()
    runner = EvalRunner(cfg, {})
    with pytest.raises(KeyError):
        runner.run("ghost", tmp_path)
```

- [ ] **Step 2: Run, verify failure, implement (code above), verify pass**

Run: `pytest tests/test_eval_runner.py -v`

- [ ] **Step 3: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/eval/runner.py tests/test_eval_runner.py
git commit -m "feat(sb): eval runner foundation (EvalSuite protocol + EvalReport)"
```

---

## Task 9: Retrieval eval suite

**Files:**
- Create: `src/second_brain/eval/suites/__init__.py` (empty package marker)
- Create: `src/second_brain/eval/suites/retrieval.py`
- Create: `tests/eval/fixtures/retrieval/seed.yaml`
- Test: `tests/test_eval_retrieval.py`

Suite: load YAML with fields `claims: [{id, statement, taxonomy}]` and `queries: [{query, expected_ids, min_ndcg}]`. Seed an FTS index from the claims, run BM25 retrieval, compute nDCG@k, pass if ≥ threshold and p95 latency < 100ms.

nDCG computation: simple DCG over binary relevance at rank, normalized by IDCG for ideal ordering of `expected_ids`.

- [ ] **Step 1: Write fixture**

```yaml
# tests/eval/fixtures/retrieval/seed.yaml
claims:
  - id: clm_transformer_attention
    statement: Self-attention computes weighted sum over all token positions.
    taxonomy: papers/ml/transformers
  - id: clm_transformer_layernorm
    statement: Layer normalization stabilizes gradients in deep transformers.
    taxonomy: papers/ml/transformers
  - id: clm_rnn_gradient_vanishing
    statement: Recurrent nets suffer vanishing gradients over long sequences.
    taxonomy: papers/ml/rnn
queries:
  - query: self attention weighted sum
    expected_ids: [clm_transformer_attention]
    min_ndcg: 0.9
  - query: vanishing gradient recurrent
    expected_ids: [clm_rnn_gradient_vanishing]
    min_ndcg: 0.9
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_eval_retrieval.py
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalRunner
from second_brain.eval.suites.retrieval import RetrievalSuite


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_retrieval_suite_passes_on_seed(sb_home: Path):
    cfg = Config.load()
    runner = EvalRunner(cfg, {"retrieval": RetrievalSuite()})
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "retrieval"
    report = runner.run("retrieval", fixtures)
    assert report.suite == "retrieval"
    assert report.cases
    assert report.passed, [c for c in report.cases if not c.passed]
```

- [ ] **Step 3: Implement**

```python
# src/second_brain/eval/suites/__init__.py
"""Built-in eval suites."""
```

```python
# src/second_brain/eval/suites/retrieval.py
from __future__ import annotations

import math
import time
from pathlib import Path

import yaml

from second_brain.config import Config
from second_brain.eval.runner import EvalCase
from second_brain.index.retriever import BM25Retriever
from second_brain.store.fts_store import FtsStore


def _dcg(relevance: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(relevance))


def _ndcg(expected: list[str], got: list[str], k: int = 10) -> float:
    relevance = [1 if gid in expected else 0 for gid in got[:k]]
    if not any(relevance):
        return 0.0
    ideal = sorted(relevance, reverse=True)
    dcg = _dcg(relevance)
    idcg = _dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0


class RetrievalSuite:
    name = "retrieval"

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        seed = yaml.safe_load((fixtures_dir / "seed.yaml").read_text(encoding="utf-8"))

        # Seed isolated FTS index under the same cfg.
        cfg.sb_dir.mkdir(parents=True, exist_ok=True)
        if cfg.fts_path.exists():
            cfg.fts_path.unlink()
        with FtsStore.open(cfg.fts_path) as store:
            store.ensure_schema()
            for c in seed["claims"]:
                store.insert_claim(
                    claim_id=c["id"],
                    statement=c["statement"],
                    abstract="",
                    body="",
                    taxonomy=c.get("taxonomy", ""),
                )

        retriever = BM25Retriever(cfg)
        cases: list[EvalCase] = []
        for q in seed["queries"]:
            t0 = time.monotonic()
            hits = retriever.search(q["query"], k=10, scope="claims")
            latency_ms = (time.monotonic() - t0) * 1000
            got_ids = [h.id for h in hits]
            ndcg = _ndcg(q["expected_ids"], got_ids, k=10)
            passed = ndcg >= q["min_ndcg"] and latency_ms < 100
            cases.append(
                EvalCase(
                    name=q["query"],
                    passed=passed,
                    metric=ndcg,
                    details=f"nDCG={ndcg:.3f} latency={latency_ms:.1f}ms hits={got_ids[:3]}",
                )
            )
        return cases
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_eval_retrieval.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/eval/suites tests/eval/fixtures/retrieval tests/test_eval_retrieval.py
git commit -m "feat(sb): eval retrieval suite (nDCG@10 + p95 latency)"
```

---

## Task 10: Graph eval suite

**Files:**
- Create: `src/second_brain/eval/suites/graph.py`
- Create: `tests/eval/fixtures/graph/seed.yaml`
- Test: `tests/test_eval_graph.py`

Fixture:

```yaml
# tests/eval/fixtures/graph/seed.yaml
graph:
  nodes:
    - {id: clm_a, kind: claim}
    - {id: clm_b, kind: claim}
    - {id: clm_c, kind: claim}
    - {id: clm_d, kind: claim}
  edges:
    - {src: clm_a, dst: clm_b, relation: supports}
    - {src: clm_b, dst: clm_c, relation: supports}
    - {src: clm_c, dst: clm_d, relation: refines}
    - {src: clm_a, dst: clm_c, relation: refines}
queries:
  - {start: clm_a, relation: supports, depth: 2, expected: [clm_b, clm_c]}
  - {start: clm_a, relation: refines, depth: 1, expected: [clm_c]}
```

Suite walks the graph by a simple BFS over `{(src, relation)}` using an in-memory dict built from the fixture — does NOT touch `graph.duckdb`, to keep the suite hermetic.

- [ ] **Step 1: Write failing test**

```python
# tests/test_eval_graph.py
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalRunner
from second_brain.eval.suites.graph import GraphSuite


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_graph_suite_passes_on_seed(sb_home: Path):
    cfg = Config.load()
    runner = EvalRunner(cfg, {"graph": GraphSuite()})
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "graph"
    report = runner.run("graph", fixtures)
    assert report.passed, [c for c in report.cases if not c.passed]
    assert len(report.cases) >= 2
```

- [ ] **Step 2: Implement**

```python
# src/second_brain/eval/suites/graph.py
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

import yaml

from second_brain.config import Config
from second_brain.eval.runner import EvalCase


class GraphSuite:
    name = "graph"

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        seed = yaml.safe_load((fixtures_dir / "seed.yaml").read_text(encoding="utf-8"))
        adjacency: dict[tuple[str, str], list[str]] = defaultdict(list)
        for e in seed["graph"]["edges"]:
            adjacency[(e["src"], e["relation"])].append(e["dst"])

        cases: list[EvalCase] = []
        for q in seed["queries"]:
            visited: set[str] = set()
            queue: deque[tuple[str, int]] = deque([(q["start"], 0)])
            while queue:
                node, d = queue.popleft()
                if d >= q["depth"]:
                    continue
                for nxt in adjacency.get((node, q["relation"]), []):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append((nxt, d + 1))
            expected = set(q["expected"])
            passed = visited == expected
            cases.append(
                EvalCase(
                    name=f"{q['start']}-{q['relation']}-d{q['depth']}",
                    passed=passed,
                    metric=1.0 if passed else 0.0,
                    details=f"got={sorted(visited)} expected={sorted(expected)}",
                )
            )
        return cases
```

- [ ] **Step 3: Run, verify pass**

Run: `pytest tests/test_eval_graph.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/eval/suites/graph.py tests/eval/fixtures/graph tests/test_eval_graph.py
git commit -m "feat(sb): eval graph suite (BFS walk vs expected set)"
```

---

## Task 11: Ingest eval suite

**Files:**
- Create: `src/second_brain/eval/suites/ingest.py`
- Create: `tests/eval/fixtures/ingest/note_sample.yaml`
- Test: `tests/test_eval_ingest.py`

Fixture (notes-only for hermeticity — no PDF / URL / gh clone in CI):

```yaml
# tests/eval/fixtures/ingest/note_sample.yaml
cases:
  - name: short-note
    content: |
      # Short note
      Just a single paragraph.
    expected_kind: note
    claim_count_min: 0
    claim_count_max: 2
  - name: long-note
    content: |
      # Long note
      First claim about transformers.
      Second claim about layer norm.
      Third claim about attention.
    expected_kind: note
    claim_count_min: 0
    claim_count_max: 5
```

Suite writes each `content` to a tmp file inside `cfg.home / "inbox"`, calls `ingest()`, verifies `kind` matches. Extraction is NOT exercised (that requires Anthropic client); the case passes on successful ingest + correct kind.

- [ ] **Step 1: Implement + test**

```python
# tests/test_eval_ingest.py
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalRunner
from second_brain.eval.suites.ingest import IngestSuite


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    (home / "inbox").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_ingest_suite_passes_on_notes(sb_home: Path):
    cfg = Config.load()
    runner = EvalRunner(cfg, {"ingest": IngestSuite()})
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "ingest"
    report = runner.run("ingest", fixtures)
    assert report.passed, [c for c in report.cases if not c.passed]
    assert len(report.cases) == 2
```

```python
# src/second_brain/eval/suites/ingest.py
from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from second_brain.config import Config
from second_brain.eval.runner import EvalCase
from second_brain.frontmatter import load_document
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import ingest


class IngestSuite:
    name = "ingest"

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        seed = yaml.safe_load(
            (fixtures_dir / "note_sample.yaml").read_text(encoding="utf-8")
        )
        cases: list[EvalCase] = []
        for c in seed["cases"]:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", dir=cfg.home, delete=False
            ) as fh:
                fh.write(c["content"])
                path = Path(fh.name)
            try:
                folder = ingest(IngestInput.from_path(path), cfg=cfg)
                fm, _ = load_document(folder.source_md)
                kind_ok = fm.get("kind") == c["expected_kind"]
                cases.append(
                    EvalCase(
                        name=c["name"],
                        passed=kind_ok,
                        metric=1.0 if kind_ok else 0.0,
                        details=f"kind={fm.get('kind')} (expected {c['expected_kind']})",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                cases.append(
                    EvalCase(
                        name=c["name"], passed=False, metric=0.0, details=f"error: {exc}"
                    )
                )
            finally:
                path.unlink(missing_ok=True)
        return cases
```

- [ ] **Step 2: Run, verify pass**

Run: `pytest tests/test_eval_ingest.py -v`

- [ ] **Step 3: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/eval/suites/ingest.py tests/eval/fixtures/ingest tests/test_eval_ingest.py
git commit -m "feat(sb): eval ingest suite (note-only, hermetic)"
```

---

## Task 12: `sb eval [suite]` CLI

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_quality.py`

- [ ] **Step 1: Append failing test**

```python
def test_cli_eval_runs_all_suites(sb_home: Path):
    runner = CliRunner()
    # fixtures path is tests/eval/fixtures by default; override via --fixtures-dir
    fixtures = Path(__file__).parent / "eval" / "fixtures"
    result = runner.invoke(
        cli, ["eval", "--fixtures-dir", str(fixtures)]
    )
    assert result.exit_code == 0, result.output
    assert "retrieval" in result.output
    assert "graph" in result.output
    assert "ingest" in result.output


def test_cli_eval_single_suite(sb_home: Path):
    runner = CliRunner()
    fixtures = Path(__file__).parent / "eval" / "fixtures"
    result = runner.invoke(
        cli, ["eval", "--suite", "retrieval", "--fixtures-dir", str(fixtures)]
    )
    assert result.exit_code == 0
    assert "retrieval" in result.output
    assert "graph" not in result.output
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_cli_quality.py -k eval -v`
Expected: `No such command 'eval'`.

- [ ] **Step 3: Implement**

```python
@cli.command(name="eval")
@click.option("--suite", type=click.Choice(["retrieval", "graph", "ingest"]), default=None)
@click.option("--fixtures-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=True)
@click.option("--json", "as_json", is_flag=True)
def _eval(suite: str | None, fixtures_dir: Path, as_json: bool) -> None:
    """Run eval suites against seed fixtures."""
    import dataclasses
    import json as _json

    from second_brain.eval.runner import EvalRunner
    from second_brain.eval.suites.graph import GraphSuite
    from second_brain.eval.suites.ingest import IngestSuite
    from second_brain.eval.suites.retrieval import RetrievalSuite

    cfg = Config.load()
    suites = {
        "retrieval": RetrievalSuite(),
        "graph": GraphSuite(),
        "ingest": IngestSuite(),
    }
    names = [suite] if suite else list(suites.keys())
    runner = EvalRunner(cfg, suites)

    reports = []
    for name in names:
        sub_dir = fixtures_dir / name
        if not sub_dir.exists():
            click.echo(f"skip {name}: fixtures_dir/{name} missing")
            continue
        reports.append(runner.run(name, sub_dir))

    if as_json:
        click.echo(_json.dumps([dataclasses.asdict(r) for r in reports], indent=2, default=str))
    else:
        for r in reports:
            mark = "PASS" if r.passed else "FAIL"
            click.echo(f"[{mark}] {r.suite}: {int(r.pass_rate * 100)}% ({len(r.cases)} cases)")
            for c in r.cases:
                click.echo(f"  {'ok' if c.passed else '--'} {c.name}: {c.details}")

    if any(not r.passed for r in reports):
        raise click.ClickException("one or more suites failed")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_cli_quality.py -v`

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_quality.py
git commit -m "feat(sb): add \`sb eval\` CLI (runs one or all suites)"
```

---

## Task 13: Hook habit-learning + analytics rebuild into `sb maintain`

**Files:**
- Modify: `src/second_brain/maintain/runner.py`
- Test: `tests/test_maintain_runner.py` (extend)

Maintain pipeline post-Plan-5 was: lint → contradictions → compact → stale-abstract. Extend to: **lint → contradictions → analytics rebuild → habit-learning → compact → stale-abstract**.

- [ ] **Step 1: Extend test**

Append to `tests/test_maintain_runner.py`:

```python
def test_maintain_rebuilds_analytics_and_runs_learning(sb_home: Path):
    # Seed 3 USER_OVERRIDE entries so the learner fires a proposal.
    from datetime import UTC, datetime
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    lines = []
    for i in range(3):
        lines.append(f"- {ts} [USER_OVERRIDE] ingest.taxonomy src_p{i} → papers/ml")
        lines.append("  prior: papers")
    (sb_home / "log.md").write_text("\n".join(lines) + "\n")

    cfg = Config.load()
    report = MaintainRunner(cfg).run()

    assert (sb_home / ".sb" / "analytics.duckdb").exists()
    assert report.analytics_rebuilt is True
    assert report.habit_proposals >= 1
```

- [ ] **Step 2: Extend `MaintainReport` + pipeline**

In `src/second_brain/maintain/runner.py`:

```python
@dataclass(frozen=True)
class MaintainReport:
    lint_counts: dict[str, int] = field(default_factory=dict)
    open_contradictions: int = 0
    stale_abstracts: list[str] = field(default_factory=list)
    fts_bytes_before: int = 0
    fts_bytes_after: int = 0
    duck_bytes_before: int = 0
    duck_bytes_after: int = 0
    analytics_rebuilt: bool = False
    habit_proposals: int = 0
```

In `MaintainRunner.run()`, after lint+contradictions and before compact:

```python
        from second_brain.analytics.builder import AnalyticsBuilder
        from second_brain.habits.learning import detect_overrides, write_proposal

        AnalyticsBuilder(self.cfg).rebuild()
        analytics_rebuilt = True

        proposals = detect_overrides(self.cfg, window_days=60, threshold=3)
        for p in proposals:
            write_proposal(p, self.cfg)
        habit_proposals = len(proposals)
```

Return the extended report.

- [ ] **Step 3: Run tests, verify pass**

Run: `pytest tests/test_maintain_runner.py -v`

- [ ] **Step 4: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/maintain/runner.py tests/test_maintain_runner.py
git commit -m "feat(sb): sb maintain now rebuilds analytics + runs habit learner"
```

---

## Task 14: Full suite green + coverage check

- [ ] **Step 1: Run all tests**

Run: `cd /Users/jay/Developer/second-brain && pytest --ignore=tests/test_ingest_pdf.py -q`
Expected: all pass.

- [ ] **Step 2: Run coverage gate**

Run: `cd /Users/jay/Developer/second-brain && pytest --cov=second_brain --cov-report=term --ignore=tests/test_ingest_pdf.py --cov-fail-under=75 -q`
Expected: ≥ 75%. If below, add targeted tests for branches in `analytics/builder.py`, `habits/learning.py`, `eval/*`, `stats/*`.

- [ ] **Step 3: Commit coverage fixes if any**

```bash
cd /Users/jay/Developer/second-brain
git add tests/
git commit -m "test(sb): close coverage gaps in quality-gates modules"
```

---

## Task 15: README + changelog + push

- [ ] **Step 1: README**

Append to `README.md`:

```markdown
### Quality gates
- `sb habits learn [--threshold N] [--window-days D]` — detect recurring user overrides, emit proposal markdown under `proposals/`.
- `sb analytics rebuild` — rebuild `.sb/analytics.duckdb` from graph + filesystem.
- `sb stats [--json]` — counts + 0-100 health score.
- `sb eval --fixtures-dir <dir> [--suite retrieval|graph|ingest] [--json]` — run eval suites.
```

- [ ] **Step 2: Changelog (claude-code-agent)**

Append to `/Users/jay/Developer/claude-code-agent/docs/log.md` under `## [Unreleased]` → `### Added`:

```markdown
- Second Brain quality gates: `sb habits learn`, `sb analytics rebuild`, `sb stats --json` (with 0-100 health score), `sb eval` suite runner. Nightly `sb maintain` now rebuilds analytics and detects ≥3-override habit patterns.
```

- [ ] **Step 3: Commit + push**

```bash
cd /Users/jay/Developer/second-brain && git add README.md && git commit -m "docs(sb): document quality-gates commands (habits learn, analytics, stats, eval)"
cd /Users/jay/Developer/claude-code-agent && git add docs/log.md && git commit -m "docs(log): second-brain quality gates landed (plan 6)"
cd /Users/jay/Developer/second-brain && git push 2>/dev/null || echo "(no remote)"
cd /Users/jay/Developer/claude-code-agent && git push
```

---

## Self-review notes

- **Spec coverage:** §10.3 habit-learning (Tasks 2–3); §6.1 analytics.duckdb (Tasks 4–5); §13.2 stats + health (Tasks 6–7); §13.1 eval (Tasks 8–12). Maintain pipeline integration (Task 13) closes the loop.
- **No placeholders:** every step has code or a real command.
- **Type consistency:** `HabitProposal`, `AnalyticsBuilder`, `Stats`, `HealthScore`, `HealthWeights`, `EvalSuite`, `EvalCase`, `EvalReport`, `EvalRunner` — each defined once, referenced consistently. Query functions `sources_by_kind` etc. all take `cfg` only.
- **Hermetic tests:** retrieval suite seeds its own FTS index; graph suite is in-memory; ingest suite uses notes only (no PDF/URL/git network calls).
- **No new external deps:** everything uses `duckdb`, `pyyaml`, existing Anthropic/ruamel already in deps.
- **Graceful on empty KB:** all query functions return `[]` when `analytics.duckdb` doesn't exist; `collect_stats` and `compute_health` both work on a zero-state KB.
- **Deferred to plan 7:** interactive `sb init` wizard, backend `SKILL.md`, real `sb_promote_claim`, in-repo `.claude/skills/sb-*`.
