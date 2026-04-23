# Second Brain — habits + inject + reconcile + claude-code-agent bridge

> Historical note (2026-04-22): This plan was written when `second-brain` lived
> at `~/Developer/second-brain/`. The active codebase has since been moved into
> `claude-code-agent/components/second-brain`. Path references in this document
> are historical unless explicitly updated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the second-brain KB usable from inside claude-code-agent by landing the habits layer, the `sb inject` prompt-prefix hook, the `sb reconcile` contradiction resolver, and the three-artifact bridge (skill + tool registrations + settings hook) described in design spec §8.4, §10, §7.4, and §12.

**Architecture:** Three subsystems layered in dependency order. (1) `habits` is the config substrate that the other two read from. (2) `sb inject` and `sb reconcile` are two CLI commands that each consume habits and talk to the existing retriever / lint stack. (3) The claude-code-agent bridge installs `second-brain` as a local editable dep, adds `sb_search` / `sb_load` / `sb_reason` / `sb_ingest` / `sb_promote_claim` tool schemas with handlers that wrap direct Python calls into `second_brain`, and writes the `UserPromptSubmit` + `PostToolUse` hook entries in `.claude/settings.json`. Graceful degradation: if `~/second-brain/.sb/` does not exist, all tools and the hook silently no-op so the agent stays usable.

**Tech Stack:** Python 3.12+, Click, Pydantic v2, ruamel.yaml, Anthropic SDK tool-use, pytest, httpx.MockTransport; claude-code-agent backend (FastAPI, pydantic, `ToolSchema` + `ToolDispatcher`).

**Scope gates:**
- In-scope: habits.yaml schema + loader + CLI, density resolution, `sb inject`, reconciler client + pipeline + `sb reconcile` CLI, editable-install of second-brain into claude-code-agent, new tool schemas + dispatcher wiring, `.claude/settings.json` hook entries.
- Out-of-scope (later plans): wizard (`sb init`), habit-learning detector, `sb watch` / `sb maintain`, eval harness, MCP `sb serve`.

---

## File structure

### Created in `~/Developer/second-brain/`

| File | Responsibility |
|---|---|
| `src/second_brain/habits/__init__.py` | Public surface: `Habits`, `load_habits`, `save_habits`, `Autonomy`, `InjectionHabits`, `ExtractionHabits`. |
| `src/second_brain/habits/schema.py` | Pydantic v2 models for every habits.yaml section. |
| `src/second_brain/habits/loader.py` | `load_habits(cfg)` / `save_habits(cfg, h)` / `validate_habits_file(path)`. |
| `src/second_brain/habits/density.py` | `resolve_density(kind, taxonomy, habits, explicit) -> Density` prefix-match resolver. |
| `src/second_brain/inject/__init__.py` | Public: `InjectionResult`, `render_injection_block`, `build_injection`. |
| `src/second_brain/inject/renderer.py` | `render_injection_block(hits, cfg) -> str` producing the human/SDK-friendly prefix. |
| `src/second_brain/inject/runner.py` | `build_injection(cfg, habits, prompt) -> InjectionResult` orchestrating skip-pattern, scoring, BM25 call, rendering. |
| `src/second_brain/reconcile/__init__.py` | Public: `OpenDebate`, `ReconcilerClient`, `FakeReconcilerClient`, `AnthropicReconcilerClient`, `reconcile_pair`, `run_reconcile`. |
| `src/second_brain/reconcile/schema.py` | Tool-use `input_schema` for Claude reconciliation; `validate_resolution_record`. |
| `src/second_brain/reconcile/client.py` | Client protocol, fake, Anthropic-backed impl. |
| `src/second_brain/reconcile/finder.py` | `find_open_debates(cfg, habits) -> list[OpenDebate]` — pulls unresolved `contradicts` edges older than grace window. |
| `src/second_brain/reconcile/writer.py` | Writes `claims/resolutions/<slug>.md`, updates claim frontmatter `resolution:` pointer. |
| `src/second_brain/reconcile/worker.py` | `run_reconcile(cfg, client, *, limit, autonomy) -> ReconcileReport`. |
| `tests/habits/test_schema.py`, `test_loader.py`, `test_density.py` | |
| `tests/inject/test_renderer.py`, `test_runner.py`, `test_cli.py` | |
| `tests/reconcile/test_finder.py`, `test_writer.py`, `test_worker.py`, `test_cli.py` | |

### Modified in `~/Developer/second-brain/`

| File | Change |
|---|---|
| `src/second_brain/cli.py` | Add `sb habits show|validate|init`, `sb inject`, `sb reconcile`. Have `sb extract` resolve density from habits when `--density` omitted. |
| `src/second_brain/extract/worker.py` | Accept explicit density; if `None`, caller resolves from habits. |
| `pyproject.toml` | Ensure `ruamel.yaml` dep is present (already there); add `rapidfuzz` is **not** needed. |

### Created in `~/Developer/claude-code-agent/`

| File | Responsibility |
|---|---|
| `backend/app/tools/__init__.py` | New `tools` package (empty). |
| `backend/app/tools/sb_tools.py` | Five thin handlers: `sb_search`, `sb_load`, `sb_reason`, `sb_ingest`, `sb_promote_claim`. Each imports `second_brain` lazily, no-ops on disabled KB, returns JSON-serializable dict. |
| `backend/tests/tools/test_sb_tools.py` | Unit tests for each handler, including the `SECOND_BRAIN_ENABLED = False` path. |

### Modified in `~/Developer/claude-code-agent/`

| File | Change |
|---|---|
| `backend/app/api/chat_api.py` | Add five `ToolSchema` constants, append to `_CHAT_TOOLS`, register handlers in `_build_dispatcher` (or after, like `get_context_status`). |
| `backend/pyproject.toml` | Add `second-brain` as an editable path dep (`second-brain = {path = "../../second-brain", develop = true}` — or the Poetry equivalent). If the project uses `requirements.txt`, add a `-e ../../second-brain` line. |
| `.claude/settings.json` | Add `UserPromptSubmit` hook (`sb inject …`) and `PostToolUse` matcher for `sb_ingest|sb_promote_claim`. |
| `backend/app/config.py` | Add `SECOND_BRAIN_HOME` + `SECOND_BRAIN_ENABLED` constants. |

---

## Execution ordering

Batches chosen to keep second-brain green at every boundary and to keep claude-code-agent changes in one contiguous block at the end.

- **Batch A — Habits (Tasks 1–4).** Habits schema, loader+CLI, density resolution, density wired into `sb extract`.
- **Batch B — Inject (Tasks 5–7).** Renderer, runner, `sb inject` CLI.
- **Batch C — Reconcile (Tasks 8–11).** Schema/client, finder, writer, worker+CLI.
- **Batch D — Bridge (Tasks 12–15).** Editable install + config flag, `sb_tools.py` handlers, ToolSchema + dispatcher wiring, hook entries in `.claude/settings.json`.

---

## Task 1: Habits schema

**Files:**
- Create: `src/second_brain/habits/__init__.py`
- Create: `src/second_brain/habits/schema.py`
- Create: `tests/habits/__init__.py`
- Create: `tests/habits/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/habits/test_schema.py
from second_brain.habits import Habits


def test_default_habits_are_valid_and_stable():
    h = Habits.default()
    assert h.injection.enabled is True
    assert h.injection.k == 5
    assert h.injection.max_tokens == 800
    assert h.injection.min_score == 0.2
    assert h.extraction.default_density == "moderate"
    assert h.extraction.by_taxonomy["papers/*"] == "dense"
    assert h.conflicts.grace_period_days == 14
    assert h.conflicts.cluster_threshold == 3
    assert h.autonomy.default == "hitl"
    assert h.autonomy.overrides["reconciliation.resolution"] == "hitl"
    assert h.autonomy.overrides["ingest.slug"] == "auto"


def test_habits_round_trip_through_dict_preserves_fields():
    h = Habits.default()
    raw = h.model_dump(mode="python")
    assert raw["injection"]["k"] == 5
    h2 = Habits.model_validate(raw)
    assert h2 == h


def test_habits_rejects_unknown_autonomy_mode():
    import pytest
    from pydantic import ValidationError
    raw = Habits.default().model_dump()
    raw["autonomy"]["default"] = "yolo"
    with pytest.raises(ValidationError):
        Habits.model_validate(raw)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/habits/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.habits'`.

- [ ] **Step 3: Implement the minimum to pass**

```python
# src/second_brain/habits/__init__.py
from second_brain.habits.schema import (
    Autonomy,
    ConflictsHabits,
    ExtractionHabits,
    Habits,
    InjectionHabits,
    LearningHabits,
    MaintenanceHabits,
    NamingConvention,
    RepoCaptureHabits,
    RetrievalHabits,
    TaxonomyHabits,
)

__all__ = [
    "Autonomy",
    "ConflictsHabits",
    "ExtractionHabits",
    "Habits",
    "InjectionHabits",
    "LearningHabits",
    "MaintenanceHabits",
    "NamingConvention",
    "RepoCaptureHabits",
    "RetrievalHabits",
    "TaxonomyHabits",
]
```

```python
# src/second_brain/habits/schema.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AutonomyMode = Literal["auto", "hitl"]
Density = Literal["sparse", "moderate", "dense"]
RetrievalPref = Literal["claims", "sources", "balanced"]
RetrievalScope = Literal["claims", "sources", "both"]


class NamingConvention(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_slug: str = "{kind-prefix}_{year?}_{title-kebab}"
    claim_slug: str = "{verb}-{subject-kebab}"
    max_slug_length: int = 80


class TaxonomyHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    roots: list[str] = Field(
        default_factory=lambda: [
            "papers/ml", "papers/systems", "blog", "news",
            "notes/personal", "notes/work", "repos/ml", "repos/infra",
        ]
    )
    enforce: Literal["soft", "strict"] = "soft"


class ExtractionConfidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    require_quote_for_extracted: bool = True
    max_inferred_per_source: int = 20


class ExtractionHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    default_density: Density = "moderate"
    by_taxonomy: dict[str, Density] = Field(
        default_factory=lambda: {
            "papers/*": "dense",
            "blog/*": "sparse",
            "news/*": "sparse",
            "notes/*": "moderate",
            "repos/*": "sparse",
        }
    )
    by_kind: dict[str, Density] = Field(default_factory=lambda: {"url": "sparse"})
    claim_rubric: str = (
        "A claim is an atomic, falsifiable assertion. Skip rhetoric, background.\n"
        "Prefer author's exact phrasing. Tag `kind: opinion` when scope is limited."
    )
    confidence_policy: ExtractionConfidencePolicy = Field(default_factory=ExtractionConfidencePolicy)


class RetrievalHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prefer: RetrievalPref = "claims"
    default_k: int = 10
    default_scope: RetrievalScope = "both"
    max_depth_content: int = 1


class InjectionHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    k: int = 5
    max_tokens: int = 800
    min_score: float = 0.2
    skip_patterns: list[str] = Field(
        default_factory=lambda: [
            r"^/",
            r"^(git|gh|npm|pip|make)\b",
            r"\b(ssh|curl|docker)\b",
        ]
    )


class ConflictsHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    grace_period_days: int = 14
    cluster_threshold: int = 3


class RepoCaptureHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    globs: list[str] = Field(
        default_factory=lambda: [
            "README*", "docs/**/*.md", "pyproject.toml", "package.json", "Cargo.toml",
        ]
    )
    exclude_globs: list[str] = Field(
        default_factory=lambda: ["node_modules/**", "target/**", ".git/**"]
    )


class Autonomy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    default: AutonomyMode = "hitl"
    overrides: dict[str, AutonomyMode] = Field(
        default_factory=lambda: {
            "ingest.slug": "auto",
            "ingest.taxonomy": "hitl",
            "extraction.density_adjust": "auto",
            "reconciliation.resolution": "hitl",
            "reconciliation.reject_edge": "auto",
            "habit_learning.apply": "hitl",
        }
    )

    def for_op(self, op: str) -> AutonomyMode:
        return self.overrides.get(op, self.default)


class LearningHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    threshold_overrides: int = 3
    rolling_window_days: int = 90
    dimensions: list[str] = Field(
        default_factory=lambda: [
            "naming.source_slug",
            "naming.claim_slug",
            "taxonomy.roots",
            "extraction.by_taxonomy",
            "extraction.by_kind",
            "injection.skip_patterns",
        ]
    )


class MaintenanceNightly(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = True
    time: str = "03:30"
    tasks: list[str] = Field(
        default_factory=lambda: [
            "lint",
            "regen_abstracts_for_changed",
            "rebuild_conflicts_md",
            "prune_failed_ingests_older_than_30d",
            "habit_learning_detector",
        ]
    )


class MaintenanceHabits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    nightly: MaintenanceNightly = Field(default_factory=MaintenanceNightly)


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = ""
    primary_language: str = "en"


class Habits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: Identity = Field(default_factory=Identity)
    taxonomy: TaxonomyHabits = Field(default_factory=TaxonomyHabits)
    naming_convention: NamingConvention = Field(default_factory=NamingConvention)
    extraction: ExtractionHabits = Field(default_factory=ExtractionHabits)
    retrieval: RetrievalHabits = Field(default_factory=RetrievalHabits)
    injection: InjectionHabits = Field(default_factory=InjectionHabits)
    conflicts: ConflictsHabits = Field(default_factory=ConflictsHabits)
    repo_capture: RepoCaptureHabits = Field(default_factory=RepoCaptureHabits)
    autonomy: Autonomy = Field(default_factory=Autonomy)
    learning: LearningHabits = Field(default_factory=LearningHabits)
    maintenance: MaintenanceHabits = Field(default_factory=MaintenanceHabits)

    @classmethod
    def default(cls) -> "Habits":
        return cls()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/habits/test_schema.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/habits/__init__.py src/second_brain/habits/schema.py \
        tests/habits/__init__.py tests/habits/test_schema.py
git commit -m "feat(habits): Habits pydantic schema with defaults for every section"
```

---

## Task 2: Habits loader + `sb habits` CLI

**Files:**
- Create: `src/second_brain/habits/loader.py`
- Modify: `src/second_brain/cli.py`
- Create: `tests/habits/test_loader.py`
- Create: `tests/habits/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/habits/test_loader.py
from pathlib import Path

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.habits.loader import (
    habits_path,
    load_habits,
    save_habits,
    validate_habits_file,
)


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    home.mkdir()
    (home / ".sb").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def test_load_returns_defaults_when_file_missing(tmp_path):
    cfg = _cfg(tmp_path)
    assert load_habits(cfg) == Habits.default()


def test_save_then_load_round_trip(tmp_path):
    cfg = _cfg(tmp_path)
    h = Habits.default().model_copy(update={})
    save_habits(cfg, h)
    assert habits_path(cfg).exists()
    assert load_habits(cfg) == h


def test_partial_yaml_fills_in_defaults(tmp_path):
    cfg = _cfg(tmp_path)
    habits_path(cfg).write_text(
        "injection:\n  k: 9\n  max_tokens: 1200\n",
        encoding="utf-8",
    )
    h = load_habits(cfg)
    assert h.injection.k == 9
    assert h.injection.max_tokens == 1200
    # Untouched fields fall back to defaults.
    assert h.injection.enabled is True
    assert h.conflicts.grace_period_days == 14


def test_validate_habits_file_reports_errors(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("autonomy:\n  default: yolo\n", encoding="utf-8")
    errs = validate_habits_file(p)
    assert errs, "expected at least one validation error"
    assert any("default" in e for e in errs)
```

```python
# tests/habits/test_cli.py
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.habits.loader import habits_path


def _init_home(tmp_path: Path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_sb_habits_init_writes_default_file(tmp_path, monkeypatch):
    home = _init_home(tmp_path, monkeypatch)
    res = CliRunner().invoke(cli, ["habits", "init"])
    assert res.exit_code == 0, res.output
    assert (home / ".sb" / "habits.yaml").exists()


def test_sb_habits_show_prints_injection_k(tmp_path, monkeypatch):
    _init_home(tmp_path, monkeypatch)
    res = CliRunner().invoke(cli, ["habits", "show"])
    assert res.exit_code == 0
    assert "injection" in res.output
    assert "k: 5" in res.output


def test_sb_habits_validate_reports_invalid(tmp_path, monkeypatch):
    home = _init_home(tmp_path, monkeypatch)
    habits_path_ = home / ".sb" / "habits.yaml"
    habits_path_.write_text("autonomy:\n  default: yolo\n", encoding="utf-8")
    res = CliRunner().invoke(cli, ["habits", "validate"])
    assert res.exit_code != 0
    assert "default" in res.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/habits/test_loader.py tests/habits/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'second_brain.habits.loader'`.

- [ ] **Step 3: Implement loader + CLI wiring**

```python
# src/second_brain/habits/loader.py
from __future__ import annotations

from io import StringIO
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.habits.schema import Habits

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False


def habits_path(cfg: Config) -> Path:
    return cfg.sb_dir / "habits.yaml"


def load_habits(cfg: Config) -> Habits:
    path = habits_path(cfg)
    if not path.exists():
        return Habits.default()
    raw = _yaml.load(path.read_text(encoding="utf-8")) or {}
    return Habits.model_validate(raw)


def save_habits(cfg: Config, habits: Habits) -> None:
    path = habits_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = StringIO()
    _yaml.dump(habits.model_dump(mode="python"), buf)
    path.write_text(buf.getvalue(), encoding="utf-8")


def validate_habits_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        raw = _yaml.load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return [f"yaml parse error: {exc}"]
    try:
        Habits.model_validate(raw)
    except ValidationError as exc:
        return [str(e) for e in exc.errors()]
    return []
```

Then append the following command group to `src/second_brain/cli.py` (keep existing commands untouched):

```python
# Add near the existing imports at the top of cli.py:
from second_brain.habits.loader import habits_path, load_habits, save_habits, validate_habits_file
from second_brain.habits import Habits

# Append near the bottom of cli.py, before any `if __name__ == "__main__":`:
@cli.group(name="habits")
def _habits() -> None:
    """Inspect and manage habits.yaml."""


@_habits.command(name="init")
@click.option("--force", is_flag=True, default=False,
              help="Overwrite an existing habits.yaml.")
def _habits_init(force: bool) -> None:
    cfg = Config.load()
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    path = habits_path(cfg)
    if path.exists() and not force:
        raise click.ClickException(f"{path} already exists; use --force to overwrite")
    save_habits(cfg, Habits.default())
    click.echo(f"wrote {path}")


@_habits.command(name="show")
def _habits_show() -> None:
    cfg = Config.load()
    from io import StringIO
    from ruamel.yaml import YAML
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    buf = StringIO()
    yaml.dump(load_habits(cfg).model_dump(mode="python"), buf)
    click.echo(buf.getvalue())


@_habits.command(name="validate")
def _habits_validate() -> None:
    cfg = Config.load()
    errs = validate_habits_file(habits_path(cfg))
    if not errs:
        click.echo("ok")
        return
    for e in errs:
        click.echo(e, err=True)
    raise click.ClickException("habits.yaml invalid")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/habits/ -v`
Expected: 7 passed total.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/habits/loader.py src/second_brain/cli.py \
        tests/habits/test_loader.py tests/habits/test_cli.py
git commit -m "feat(habits): loader + sb habits init/show/validate CLI"
```

---

## Task 3: Density resolution from habits

**Files:**
- Create: `src/second_brain/habits/density.py`
- Create: `tests/habits/test_density.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/habits/test_density.py
from second_brain.habits import Habits
from second_brain.habits.density import resolve_density


def test_explicit_density_wins():
    h = Habits.default()
    assert resolve_density(kind="url", taxonomy="papers/ml", habits=h, explicit="dense") == "dense"


def test_by_kind_beats_by_taxonomy_and_default():
    h = Habits.default()
    # url kind forces sparse even though papers/ml taxonomy prefers dense.
    assert resolve_density(kind="url", taxonomy="papers/ml", habits=h, explicit=None) == "sparse"


def test_by_taxonomy_prefix_match():
    h = Habits.default()
    assert resolve_density(kind="pdf", taxonomy="papers/ml", habits=h, explicit=None) == "dense"
    assert resolve_density(kind="pdf", taxonomy="blog/personal", habits=h, explicit=None) == "sparse"


def test_most_specific_taxonomy_prefix_wins():
    h = Habits.default().model_copy(update={
        "extraction": Habits.default().extraction.model_copy(update={
            "by_taxonomy": {"papers/*": "dense", "papers/ml/thesis/*": "moderate"},
        }),
    })
    assert resolve_density(kind="pdf", taxonomy="papers/ml/thesis/2021",
                           habits=h, explicit=None) == "moderate"


def test_default_density_when_no_match():
    h = Habits.default()
    assert resolve_density(kind="note", taxonomy=None, habits=h, explicit=None) == "moderate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/habits/test_density.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'second_brain.habits.density'`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/habits/density.py
from __future__ import annotations

from typing import Literal

from second_brain.habits.schema import Density, Habits


def _prefix_match(pattern: str, taxonomy: str) -> bool:
    # Pattern is a glob-like prefix ending in /* — we match on path segments,
    # not raw substrings, so "blog/*" does NOT match "blog-archive/x".
    if pattern.endswith("/*"):
        base = pattern[:-2]
        return taxonomy == base or taxonomy.startswith(base + "/")
    return taxonomy == pattern


def resolve_density(
    *,
    kind: str,
    taxonomy: str | None,
    habits: Habits,
    explicit: Density | None,
) -> Density:
    if explicit is not None:
        return explicit

    by_kind = habits.extraction.by_kind.get(kind)
    if by_kind is not None:
        return by_kind

    if taxonomy:
        candidates = [
            (pattern, density)
            for pattern, density in habits.extraction.by_taxonomy.items()
            if _prefix_match(pattern, taxonomy)
        ]
        if candidates:
            # Most-specific = longest base (without the trailing /*).
            candidates.sort(key=lambda p: len(p[0].rstrip("*").rstrip("/")), reverse=True)
            return candidates[0][1]

    return habits.extraction.default_density
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/habits/test_density.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/habits/density.py tests/habits/test_density.py
git commit -m "feat(habits): density resolver (explicit > by_kind > taxonomy-longest-prefix > default)"
```

---

## Task 4: `sb extract` consults habits for density

**Files:**
- Modify: `src/second_brain/cli.py` (the `_extract` command)
- Create: `tests/habits/test_extract_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/habits/test_extract_integration.py
import json
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _seed_source(home: Path, slug: str, taxonomy: str, kind: str = "pdf") -> None:
    src_dir = home / "sources" / slug
    src_dir.mkdir(parents=True)
    (src_dir / "raw").mkdir()
    fm = "\n".join([
        "---",
        f"id: {slug}",
        f"title: '{slug}'",
        f"kind: {kind}",
        "authors: []",
        "year: 2024",
        "source_url: null",
        "tags: []",
        "ingested_at: 2024-01-01T00:00:00Z",
        "content_hash: sha256:abc",
        f"habit_taxonomy: {taxonomy}",
        "raw: []",
        "cites: []",
        "related: []",
        "supersedes: []",
        "abstract: ''",
        "---",
    ])
    (src_dir / "_source.md").write_text(fm + "\n\nbody\n", encoding="utf-8")


def test_sb_extract_uses_habits_density_when_not_supplied(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setenv("SB_FAKE_CLAIMS", "[]")  # fake empty extraction, keeps run green
    monkeypatch.setenv("SB_DENSITY_PROBE", "1")  # see cli change below
    _seed_source(home, "src_paper", taxonomy="papers/ml")
    _seed_source(home, "src_blogpost", taxonomy="blog/web")
    runner = CliRunner()

    res_paper = runner.invoke(cli, ["extract", "src_paper"])
    res_blog = runner.invoke(cli, ["extract", "src_blogpost"])
    assert res_paper.exit_code == 0, res_paper.output
    assert res_blog.exit_code == 0, res_blog.output
    # The probe prints the resolved density so we can assert without touching extractor internals.
    assert "density=dense" in res_paper.output
    assert "density=sparse" in res_blog.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/habits/test_extract_integration.py -v`
Expected: FAIL — either the probe env var is ignored and the current extract always uses the CLI default, or `density=dense` does not appear.

- [ ] **Step 3: Modify `_extract`**

Replace the body of the existing `_extract` click command in `src/second_brain/cli.py`. Keep imports at the top of the function local to keep the module-level import graph unchanged.

```python
# src/second_brain/cli.py — replace the existing _extract body with:

@cli.command(name="extract")
@click.argument("source_id")
@click.option("--density", type=click.Choice(["sparse", "moderate", "dense"]),
              default=None,
              help="Override habits-derived density for this run.")
@click.option("--rubric", default=None,
              help="Override habits.extraction.claim_rubric for this run.")
@click.option("--live/--fake", default=None,
              help="Force real Anthropic call (--live) or fake client (--fake). "
                   "Default: fake if ANTHROPIC_API_KEY unset or SB_FAKE_CLAIMS set.")
def _extract(source_id: str, density: str | None, rubric: str | None,
             live: bool | None) -> None:
    """Extract claims from an ingested source."""
    import json as _json
    import os

    from second_brain.extract.client import AnthropicClient, FakeExtractorClient
    from second_brain.extract.worker import extract_source
    from second_brain.frontmatter import load_document
    from second_brain.habits.density import resolve_density
    from second_brain.habits.loader import load_habits

    cfg = Config.load()
    habits = load_habits(cfg)

    # Read the source frontmatter so we can pass kind + taxonomy into the resolver.
    src_path = cfg.sources_dir / source_id / "_source.md"
    if not src_path.exists():
        raise click.ClickException(f"source not found: {source_id}")
    meta, _ = load_document(src_path)
    resolved_density = resolve_density(
        kind=str(meta.get("kind") or ""),
        taxonomy=meta.get("habit_taxonomy") or None,
        habits=habits,
        explicit=density,  # type: ignore[arg-type]
    )
    resolved_rubric = rubric if rubric is not None else habits.extraction.claim_rubric

    if os.environ.get("SB_DENSITY_PROBE"):
        click.echo(f"density={resolved_density}")

    fake_payload = os.environ.get("SB_FAKE_CLAIMS")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if live is True and not api_key:
        raise click.ClickException("ANTHROPIC_API_KEY not set; cannot run --live")
    use_fake = (live is False) or fake_payload or not api_key
    if use_fake:
        canned = _json.loads(fake_payload) if fake_payload else []
        client = FakeExtractorClient(canned=canned)
    else:
        client = AnthropicClient()

    claims = extract_source(cfg, source_id=source_id, client=client,
                             density=resolved_density, rubric=resolved_rubric)
    click.echo(f"extracted {len(claims)} claim(s) for {source_id}")
    for c in claims:
        click.echo(f"  - {c.id}: {c.statement}")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/habits/test_extract_integration.py -v` — 1 passed.
Run: `pytest -m "not integration" -q` — full fast suite still green (verify no existing `sb extract` test regressed — the existing CLI surface is a strict superset).

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/cli.py tests/habits/test_extract_integration.py
git commit -m "feat(habits): sb extract resolves density from habits when --density omitted"
```

---

## Task 5: Injection renderer

**Files:**
- Create: `src/second_brain/inject/__init__.py`
- Create: `src/second_brain/inject/renderer.py`
- Create: `tests/inject/__init__.py`
- Create: `tests/inject/test_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/inject/test_renderer.py
from second_brain.index.retriever import RetrievalHit
from second_brain.inject.renderer import render_injection_block


def _hit(i: int, kind: str = "claim", score: float = 0.87,
         neighbors: list[str] | None = None) -> RetrievalHit:
    return RetrievalHit(
        id=f"clm_demo-{i}",
        kind=kind,  # type: ignore[arg-type]
        score=score,
        matched_field="statement",
        snippet=f"Self-attention is sufficient for seq transduction #{i}.",
        neighbors=neighbors or [],
    )


def test_renders_header_numbered_list_and_footer():
    out = render_injection_block([_hit(1, neighbors=["src_a", "clm_b"])])
    assert out.startswith("### Second Brain — top matches for this prompt")
    assert "1. [clm_demo-1] (score 0.87)" in out
    assert "Self-attention is sufficient for seq transduction #1." in out
    assert "◇ neighbor: src_a" in out
    assert "◇ neighbor: clm_b" in out
    assert "Use sb_load(<id>, depth=1) to expand any of these." in out


def test_returns_empty_string_when_no_hits():
    assert render_injection_block([]) == ""


def test_budget_truncation_drops_tail_items_but_keeps_header():
    hits = [_hit(i) for i in range(1, 21)]
    out = render_injection_block(hits, max_tokens=80)  # tiny budget
    # Header always present, tail items dropped, explicit truncation note.
    assert out.startswith("### Second Brain — top matches for this prompt")
    assert "truncated" in out.lower()
    # At least one hit must have survived.
    assert "1. [clm_demo-1]" in out
```

- [ ] **Step 2: Run test**

Run: `pytest tests/inject/test_renderer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'second_brain.inject'`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/inject/__init__.py
from second_brain.inject.renderer import render_injection_block
from second_brain.inject.runner import InjectionResult, build_injection

__all__ = ["InjectionResult", "build_injection", "render_injection_block"]
```

```python
# src/second_brain/inject/renderer.py
from __future__ import annotations

from second_brain.index.retriever import RetrievalHit

_HEADER = "### Second Brain — top matches for this prompt"
_FOOTER = "Use sb_load(<id>, depth=1) to expand any of these."


def _approx_tokens(text: str) -> int:
    # A rough 4-char-per-token heuristic is fine for the budget cap.
    return max(1, len(text) // 4)


def _render_hit(idx: int, hit: RetrievalHit) -> str:
    lines = [f"{idx}. [{hit.id}] (score {hit.score:.2f})"]
    if hit.snippet:
        lines.append(f"   {hit.snippet.strip()}")
    for n in hit.neighbors:
        lines.append(f"   ◇ neighbor: {n}")
    return "\n".join(lines)


def render_injection_block(
    hits: list[RetrievalHit],
    *,
    max_tokens: int | None = None,
) -> str:
    if not hits:
        return ""

    rendered: list[str] = [_HEADER, ""]
    truncated = False
    running = _approx_tokens(_HEADER) + _approx_tokens(_FOOTER)

    for i, h in enumerate(hits, 1):
        block = _render_hit(i, h)
        cost = _approx_tokens(block)
        if max_tokens is not None and running + cost > max_tokens and i > 1:
            truncated = True
            break
        rendered.append(block)
        running += cost

    rendered.append("")
    if truncated:
        rendered.append("(truncated by injection budget)")
    rendered.append(_FOOTER)
    return "\n".join(rendered)
```

Leave `runner.py` as a placeholder for now so `from second_brain.inject import …` doesn't break:

```python
# src/second_brain/inject/runner.py (placeholder until Task 6)
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionResult:
    block: str
    hit_ids: list[str]
    skipped_reason: str | None = None


def build_injection(*args, **kwargs):  # type: ignore[no-untyped-def]
    raise NotImplementedError("implemented in Task 6")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/inject/test_renderer.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/inject/__init__.py src/second_brain/inject/renderer.py \
        src/second_brain/inject/runner.py \
        tests/inject/__init__.py tests/inject/test_renderer.py
git commit -m "feat(inject): renderer for top-k matches with budget truncation"
```

---

## Task 6: Injection runner

**Files:**
- Modify: `src/second_brain/inject/runner.py`
- Create: `tests/inject/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/inject/test_runner.py
from dataclasses import dataclass, field
from pathlib import Path

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.index.retriever import RetrievalHit
from second_brain.inject.runner import build_injection


@dataclass
class _StubRetriever:
    hits: list[RetrievalHit] = field(default_factory=list)
    calls: list[tuple[str, int, str]] = field(default_factory=list)

    def search(self, query, k=10, scope="both", taxonomy=None,
               with_neighbors=False):
        self.calls.append((query, k, scope))
        return list(self.hits[:k])


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    return Config(home=home, sb_dir=home / ".sb")


def test_skipped_when_disabled(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default().model_copy(update={
        "injection": Habits.default().injection.model_copy(update={"enabled": False}),
    })
    retriever = _StubRetriever()
    res = build_injection(cfg, habits, prompt="anything", retriever=retriever)
    assert res.block == ""
    assert res.skipped_reason == "disabled"
    assert retriever.calls == []


def test_skipped_on_skip_pattern_match(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default()  # default skip_patterns include "^/"
    retriever = _StubRetriever(hits=[RetrievalHit(
        id="clm_x", kind="claim", score=1.0, matched_field="statement", snippet="x")])
    res = build_injection(cfg, habits, prompt="/help", retriever=retriever)
    assert res.block == ""
    assert res.skipped_reason == "skip_pattern"
    assert retriever.calls == []


def test_skipped_when_top_score_below_min(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default()
    retriever = _StubRetriever(hits=[
        RetrievalHit(id="clm_x", kind="claim", score=0.1,
                     matched_field="statement", snippet="weak"),
    ])
    res = build_injection(cfg, habits, prompt="explain transformers", retriever=retriever)
    assert res.block == ""
    assert res.skipped_reason == "below_min_score"


def test_happy_path_returns_block_and_hit_ids(tmp_path):
    cfg = _cfg(tmp_path)
    habits = Habits.default()
    hits = [
        RetrievalHit(id="clm_a", kind="claim", score=0.9,
                     matched_field="statement", snippet="A"),
        RetrievalHit(id="clm_b", kind="claim", score=0.7,
                     matched_field="statement", snippet="B"),
    ]
    retriever = _StubRetriever(hits=hits)
    res = build_injection(cfg, habits, prompt="explain transformers",
                          retriever=retriever)
    assert res.skipped_reason is None
    assert "clm_a" in res.block
    assert res.hit_ids == ["clm_a", "clm_b"]
    # k from habits is 5 by default.
    assert retriever.calls == [("explain transformers", 5, "claims")]
```

- [ ] **Step 2: Run**

Run: `pytest tests/inject/test_runner.py -v`
Expected: FAIL — `NotImplementedError` from runner placeholder.

- [ ] **Step 3: Implement the runner**

```python
# src/second_brain/inject/runner.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.index.retriever import RetrievalHit
from second_brain.inject.renderer import render_injection_block


class _RetrieverProto(Protocol):
    def search(self, query: str, k: int = 10, scope: str = "both",
               taxonomy: str | None = None,
               with_neighbors: bool = False) -> list[RetrievalHit]: ...


@dataclass(frozen=True)
class InjectionResult:
    block: str
    hit_ids: list[str]
    skipped_reason: str | None = None


def _matches_any(prompt: str, patterns: list[str]) -> bool:
    for pat in patterns:
        try:
            if re.search(pat, prompt):
                return True
        except re.error:
            # A malformed habit regex should never block the agent — treat as no-match.
            continue
    return False


def _default_retriever(cfg: Config) -> _RetrieverProto:
    from second_brain.index.retriever import BM25Retriever
    return BM25Retriever(cfg)


def build_injection(
    cfg: Config,
    habits: Habits,
    prompt: str,
    *,
    retriever: _RetrieverProto | None = None,
) -> InjectionResult:
    inj = habits.injection
    if not inj.enabled:
        return InjectionResult(block="", hit_ids=[], skipped_reason="disabled")

    if _matches_any(prompt, inj.skip_patterns):
        return InjectionResult(block="", hit_ids=[], skipped_reason="skip_pattern")

    if retriever is None:
        retriever = _default_retriever(cfg)

    hits = retriever.search(prompt, k=inj.k, scope="claims")
    if not hits:
        return InjectionResult(block="", hit_ids=[], skipped_reason="no_hits")

    if hits[0].score < inj.min_score:
        return InjectionResult(block="", hit_ids=[], skipped_reason="below_min_score")

    block = render_injection_block(hits, max_tokens=inj.max_tokens)
    return InjectionResult(block=block, hit_ids=[h.id for h in hits])
```

- [ ] **Step 4: Run**

Run: `pytest tests/inject/test_runner.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/inject/runner.py tests/inject/test_runner.py
git commit -m "feat(inject): build_injection with skip/min-score/budget handling"
```

---

## Task 7: `sb inject` CLI

**Files:**
- Modify: `src/second_brain/cli.py`
- Create: `tests/inject/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/inject/test_cli.py
import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _init_kb_with_claim(home: Path) -> None:
    (home / ".sb").mkdir(parents=True, exist_ok=True)
    # Build a minimal FTS5 index directly so we don't need a full ingest+extract cycle.
    db = sqlite3.connect(home / ".sb" / "kb.sqlite")
    db.executescript(
        """
        CREATE VIRTUAL TABLE claim_fts USING fts5(
            claim_id UNINDEXED, statement, abstract, body, taxonomy,
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE VIRTUAL TABLE source_fts USING fts5(
            source_id UNINDEXED, title, abstract, processed_body, taxonomy,
            tokenize='unicode61 remove_diacritics 2'
        );
        INSERT INTO claim_fts(claim_id, statement, abstract, body, taxonomy)
        VALUES ('clm_attention-replaces-recurrence',
                'Self-attention alone is sufficient for seq transduction',
                'Self-attention is sufficient', 'body', 'papers/ml');
        """
    )
    db.commit()
    db.close()


def test_sb_inject_prints_block_for_matching_prompt(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(cli, ["inject", "--prompt", "attention transduction"])
    assert res.exit_code == 0, res.output
    assert "Second Brain" in res.output
    assert "clm_attention-replaces-recurrence" in res.output


def test_sb_inject_silent_on_skip_pattern(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(cli, ["inject", "--prompt", "/help"])
    assert res.exit_code == 0
    assert res.output.strip() == ""


def test_sb_inject_json_flag_returns_metadata(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(
        cli, ["inject", "--prompt", "attention transduction", "--json"]
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["hit_ids"] == ["clm_attention-replaces-recurrence"]
    assert payload["skipped_reason"] is None
    assert "clm_attention-replaces-recurrence" in payload["block"]


def test_sb_inject_disabled_via_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    (home / ".sb" / "habits.yaml").write_text(
        "injection:\n  enabled: false\n", encoding="utf-8"
    )
    res = CliRunner().invoke(cli, ["inject", "--prompt", "anything"])
    assert res.exit_code == 0
    assert res.output.strip() == ""


def test_sb_inject_stdin(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    _init_kb_with_claim(home)
    res = CliRunner().invoke(
        cli, ["inject", "--prompt-stdin"], input="attention transduction\n"
    )
    assert res.exit_code == 0
    assert "clm_attention-replaces-recurrence" in res.output
```

- [ ] **Step 2: Run**

Run: `pytest tests/inject/test_cli.py -v`
Expected: FAIL — `Error: No such command 'inject'`.

- [ ] **Step 3: Wire the CLI command**

Append to `src/second_brain/cli.py`:

```python
@cli.command(name="inject")
@click.option("--prompt", default=None, help="Prompt text.")
@click.option("--prompt-stdin", "prompt_stdin", is_flag=True, default=False,
              help="Read the prompt from stdin (preferred for hook usage).")
@click.option("--k", default=None, type=int,
              help="Override habits.injection.k for this call.")
@click.option("--max-tokens", default=None, type=int,
              help="Override habits.injection.max_tokens for this call.")
@click.option("--scope", default=None,
              type=click.Choice(["claims", "sources", "both"]),
              help="Override retrieval scope (default: claims).")
@click.option("--json", "as_json", is_flag=True, default=False)
def _inject(prompt: str | None, prompt_stdin: bool,
            k: int | None, max_tokens: int | None,
            scope: str | None, as_json: bool) -> None:
    """Emit a BM25 prefix block for the prompt (UserPromptSubmit hook payload)."""
    import json as _json
    import sys

    from second_brain.habits.loader import load_habits
    from second_brain.inject.runner import build_injection

    if prompt_stdin:
        prompt_value = sys.stdin.read()
    elif prompt is not None:
        prompt_value = prompt
    else:
        raise click.ClickException("either --prompt or --prompt-stdin is required")

    cfg = Config.load()
    if not cfg.fts_path.exists():
        # Graceful: no index yet → no injection, exit 0.
        if as_json:
            click.echo(_json.dumps({"block": "", "hit_ids": [], "skipped_reason": "no_index"}))
        return

    habits = load_habits(cfg)
    # Per-call overrides land as an Habits patch so skip_patterns / enabled still apply.
    patches: dict[str, object] = {}
    if k is not None or max_tokens is not None:
        inj = habits.injection
        inj_patch: dict[str, object] = {}
        if k is not None:
            inj_patch["k"] = k
        if max_tokens is not None:
            inj_patch["max_tokens"] = max_tokens
        patches["injection"] = inj.model_copy(update=inj_patch)
    if patches:
        habits = habits.model_copy(update=patches)

    result = build_injection(cfg, habits, prompt_value.strip())

    if as_json:
        click.echo(_json.dumps({
            "block": result.block,
            "hit_ids": result.hit_ids,
            "skipped_reason": result.skipped_reason,
        }))
        return

    if result.block:
        click.echo(result.block)
```

- [ ] **Step 4: Run**

Run: `pytest tests/inject/ -v` — all inject tests pass.
Run: `pytest -m "not integration" -q` — full fast suite green.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/cli.py tests/inject/test_cli.py
git commit -m "feat(inject): sb inject CLI (prompt/stdin/json, habits-aware)"
```

---

## Task 8: Reconciler schema + client

**Files:**
- Create: `src/second_brain/reconcile/__init__.py`
- Create: `src/second_brain/reconcile/schema.py`
- Create: `src/second_brain/reconcile/client.py`
- Create: `tests/reconcile/__init__.py`
- Create: `tests/reconcile/test_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/reconcile/test_client.py
from second_brain.reconcile.client import (
    FakeReconcilerClient,
    ReconcileRequest,
    ReconcileResponse,
)
from second_brain.reconcile.schema import RECORD_RESOLUTION_TOOL, validate_resolution_record


def test_tool_schema_shape():
    assert RECORD_RESOLUTION_TOOL["name"] == "record_resolution"
    props = RECORD_RESOLUTION_TOOL["input_schema"]["properties"]
    assert set(props.keys()) >= {"resolution_md", "applies_where", "primary_claim_id"}


def test_validate_resolution_record_accepts_minimum():
    validate_resolution_record({
        "resolution_md": "Scope differs: paper A covers X; paper B covers Y.",
        "applies_where": "scope",
        "primary_claim_id": "clm_x",
    })


def test_validate_resolution_record_rejects_unknown_applies_where():
    import pytest
    with pytest.raises(ValueError):
        validate_resolution_record({
            "resolution_md": "...",
            "applies_where": "vibes",
            "primary_claim_id": "clm_x",
        })


def test_fake_client_returns_canned_payload():
    client = FakeReconcilerClient(canned={
        "resolution_md": "scope diff",
        "applies_where": "scope",
        "primary_claim_id": "clm_a",
    })
    res = client.reconcile(ReconcileRequest(
        claim_a_id="clm_a", claim_a_body="A",
        claim_b_id="clm_b", claim_b_body="B",
        supports_a="src_x body", supports_b="src_y body",
    ))
    assert isinstance(res, ReconcileResponse)
    assert res.primary_claim_id == "clm_a"
    assert res.applies_where == "scope"
    assert "scope diff" in res.resolution_md
```

- [ ] **Step 2: Run**

Run: `pytest tests/reconcile/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'second_brain.reconcile'`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/reconcile/__init__.py
from second_brain.reconcile.client import (
    AnthropicReconcilerClient,
    FakeReconcilerClient,
    ReconcileRequest,
    ReconcileResponse,
    ReconcilerClient,
)

__all__ = [
    "AnthropicReconcilerClient",
    "FakeReconcilerClient",
    "ReconcileRequest",
    "ReconcileResponse",
    "ReconcilerClient",
]
```

```python
# src/second_brain/reconcile/schema.py
from __future__ import annotations

from typing import Any

APPLIES_WHERE = ["scope", "methodology", "era", "definition", "interpretation", "reject"]

RECORD_RESOLUTION_TOOL: dict[str, Any] = {
    "name": "record_resolution",
    "description": (
        "Record a resolution for a pair of contradicting claims. Explain why they "
        "disagree, pick which claim is primary in the current context, and name "
        "the dimension along which they differ (scope, methodology, era, etc.)."
    ),
    "input_schema": {
        "type": "object",
        "required": ["resolution_md", "applies_where", "primary_claim_id"],
        "properties": {
            "resolution_md": {
                "type": "string",
                "description": "Markdown body for claims/resolutions/<slug>.md.",
            },
            "applies_where": {"type": "string", "enum": APPLIES_WHERE},
            "primary_claim_id": {"type": "string"},
            "rationale": {"type": "string", "default": ""},
        },
    },
}


def validate_resolution_record(rec: dict[str, Any]) -> None:
    required = {"resolution_md", "applies_where", "primary_claim_id"}
    missing = required - rec.keys()
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if rec["applies_where"] not in APPLIES_WHERE:
        raise ValueError(f"applies_where must be one of {APPLIES_WHERE}")
    for key in ("resolution_md", "primary_claim_id"):
        if not isinstance(rec[key], str) or not rec[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
```

```python
# src/second_brain/reconcile/client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from second_brain.reconcile.schema import RECORD_RESOLUTION_TOOL, validate_resolution_record


@dataclass(frozen=True)
class ReconcileRequest:
    claim_a_id: str
    claim_a_body: str
    claim_b_id: str
    claim_b_body: str
    supports_a: str
    supports_b: str


@dataclass(frozen=True)
class ReconcileResponse:
    resolution_md: str
    applies_where: str
    primary_claim_id: str
    rationale: str = ""


class ReconcilerClient(Protocol):
    def reconcile(self, req: ReconcileRequest) -> ReconcileResponse: ...


class FakeReconcilerClient:
    def __init__(self, *, canned: dict[str, Any]) -> None:
        validate_resolution_record(canned)
        self._canned = dict(canned)

    def reconcile(self, req: ReconcileRequest) -> ReconcileResponse:
        rec = dict(self._canned)
        return ReconcileResponse(
            resolution_md=rec["resolution_md"],
            applies_where=rec["applies_where"],
            primary_claim_id=rec["primary_claim_id"],
            rationale=rec.get("rationale", ""),
        )


_SYSTEM_PROMPT = (
    "You reconcile pairs of contradicting claims. Always call record_resolution. "
    "Produce a short markdown note explaining the dimension of disagreement "
    "(scope, methodology, era, definition, interpretation, or reject if one side is wrong). "
    "Pick a primary claim that wins in the current context."
)


class AnthropicReconcilerClient:
    """Opus 4.7 via Anthropic SDK tool-use for schema-constrained reconciliation."""

    def __init__(self, *, model: str = "claude-opus-4-7", max_tokens: int = 2048) -> None:
        self.model = model
        self.max_tokens = max_tokens
        from anthropic import Anthropic  # type: ignore[import-not-found]
        self._sdk = Anthropic()

    def reconcile(self, req: ReconcileRequest) -> ReconcileResponse:
        user_prompt = (
            f"# Claim A ({req.claim_a_id})\n{req.claim_a_body}\n\n"
            f"## Support for A\n{req.supports_a}\n\n"
            f"# Claim B ({req.claim_b_id})\n{req.claim_b_body}\n\n"
            f"## Support for B\n{req.supports_b}\n"
        )
        resp = self._sdk.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=_SYSTEM_PROMPT,
            tools=[RECORD_RESOLUTION_TOOL],
            tool_choice={"type": "tool", "name": "record_resolution"},
            messages=[{"role": "user", "content": user_prompt}],
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "record_resolution":
                rec = block.input  # type: ignore[attr-defined]
                validate_resolution_record(rec)
                return ReconcileResponse(
                    resolution_md=rec["resolution_md"],
                    applies_where=rec["applies_where"],
                    primary_claim_id=rec["primary_claim_id"],
                    rationale=rec.get("rationale", ""),
                )
        raise RuntimeError("Anthropic response contained no record_resolution tool_use")
```

- [ ] **Step 4: Run**

Run: `pytest tests/reconcile/test_client.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/reconcile/__init__.py src/second_brain/reconcile/schema.py \
        src/second_brain/reconcile/client.py \
        tests/reconcile/__init__.py tests/reconcile/test_client.py
git commit -m "feat(reconcile): tool-use schema + ReconcilerClient (fake + Anthropic)"
```

---

## Task 9: Open-debates finder

**Files:**
- Create: `src/second_brain/reconcile/finder.py`
- Create: `tests/reconcile/test_finder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/reconcile/test_finder.py
from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.reconcile.finder import find_open_debates


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def _write_claim(cfg: Config, slug: str, *, contradicts: list[str],
                 resolution: str | None, extracted_at: datetime) -> None:
    body = "\n".join([
        "---",
        f"id: {slug}",
        f"statement: 'stmt for {slug}'",
        "kind: empirical",
        "confidence: high",
        "scope: ''",
        f"contradicts: {contradicts}",
        "supports: []",
        "refines: []",
        f"extracted_at: {extracted_at.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "status: active",
        f"resolution: {resolution if resolution else 'null'}",
        "abstract: ''",
        "---",
        "",
    ])
    (cfg.claims_dir / f"{slug}.md").write_text(body, encoding="utf-8")


def test_find_open_debates_returns_unresolved_past_grace(tmp_path):
    cfg = _cfg(tmp_path)
    old = datetime.now(UTC) - timedelta(days=30)
    fresh = datetime.now(UTC) - timedelta(days=2)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], resolution=None, extracted_at=old)
    _write_claim(cfg, "clm_b", contradicts=[], resolution=None, extracted_at=old)
    _write_claim(cfg, "clm_c", contradicts=["clm_d"], resolution=None, extracted_at=fresh)
    _write_claim(cfg, "clm_d", contradicts=[], resolution=None, extracted_at=fresh)

    debates = find_open_debates(cfg, Habits.default())
    pair_ids = {(d.left_id, d.right_id) for d in debates}
    assert ("clm_a", "clm_b") in pair_ids
    assert ("clm_c", "clm_d") not in pair_ids  # within grace window


def test_find_open_debates_skips_resolved(tmp_path):
    cfg = _cfg(tmp_path)
    old = datetime.now(UTC) - timedelta(days=30)
    _write_claim(cfg, "clm_x", contradicts=["clm_y"],
                 resolution="claims/resolutions/x-y.md", extracted_at=old)
    _write_claim(cfg, "clm_y", contradicts=[], resolution=None, extracted_at=old)
    debates = find_open_debates(cfg, Habits.default())
    assert not debates
```

- [ ] **Step 2: Run**

Run: `pytest tests/reconcile/test_finder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'second_brain.reconcile.finder'`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/reconcile/finder.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.habits import Habits


@dataclass(frozen=True)
class OpenDebate:
    left_id: str
    right_id: str
    left_path: str
    right_path: str


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            # Accept the Z suffix shorthand.
            s = value.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def find_open_debates(cfg: Config, habits: Habits) -> list[OpenDebate]:
    if not cfg.claims_dir.exists():
        return []
    grace = timedelta(days=habits.conflicts.grace_period_days)
    cutoff = datetime.now(UTC) - grace

    # Map id → (path, meta).
    claims: dict[str, tuple[str, dict]] = {}
    for p in cfg.claims_dir.glob("*.md"):
        if p.parent.name == "resolutions":
            continue
        meta, _ = load_document(p)
        cid = str(meta.get("id") or "")
        if cid:
            claims[cid] = (str(p), meta)

    debates: list[OpenDebate] = []
    seen: set[tuple[str, str]] = set()

    for cid, (path, meta) in claims.items():
        if meta.get("resolution"):
            continue
        extracted = _parse_dt(meta.get("extracted_at"))
        if extracted is None or extracted > cutoff:
            continue
        for other_id in meta.get("contradicts") or []:
            other = claims.get(other_id)
            if other is None:
                continue
            # Canonicalize the pair by sorted id so we don't emit duplicates.
            left, right = sorted((cid, other_id))
            if (left, right) in seen:
                continue
            seen.add((left, right))
            left_path, _ = claims[left]
            right_path, _ = claims[right]
            debates.append(OpenDebate(
                left_id=left, right_id=right,
                left_path=left_path, right_path=right_path,
            ))
    return debates
```

- [ ] **Step 4: Run**

Run: `pytest tests/reconcile/test_finder.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/reconcile/finder.py tests/reconcile/test_finder.py
git commit -m "feat(reconcile): find_open_debates (unresolved contradictions past grace)"
```

---

## Task 10: Resolution writer

**Files:**
- Create: `src/second_brain/reconcile/writer.py`
- Create: `tests/reconcile/test_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/reconcile/test_writer.py
from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.reconcile.client import ReconcileResponse
from second_brain.reconcile.finder import OpenDebate
from second_brain.reconcile.writer import write_resolution


def _init_cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def _seed_claim(cfg: Config, slug: str, *, contradicts: list[str]) -> None:
    body = "\n".join([
        "---",
        f"id: {slug}",
        f"statement: 'stmt for {slug}'",
        "kind: empirical",
        "confidence: high",
        "scope: ''",
        f"contradicts: {contradicts}",
        "supports: []",
        "refines: []",
        "extracted_at: 2024-01-01T00:00:00Z",
        "status: active",
        "resolution: null",
        "abstract: ''",
        "---",
        "",
    ])
    (cfg.claims_dir / f"{slug}.md").write_text(body, encoding="utf-8")


def test_write_resolution_persists_note_and_updates_primary(tmp_path):
    cfg = _init_cfg(tmp_path)
    _seed_claim(cfg, "clm_a", contradicts=["clm_b"])
    _seed_claim(cfg, "clm_b", contradicts=["clm_a"])

    debate = OpenDebate(
        left_id="clm_a", right_id="clm_b",
        left_path=str(cfg.claims_dir / "clm_a.md"),
        right_path=str(cfg.claims_dir / "clm_b.md"),
    )
    resp = ReconcileResponse(
        resolution_md="The two claims differ in scope.",
        applies_where="scope",
        primary_claim_id="clm_a",
    )
    rel = write_resolution(cfg, debate, resp)

    # Resolution note exists at the expected relative path.
    assert rel.startswith("claims/resolutions/")
    assert (cfg.home / rel).exists()
    # Primary claim's frontmatter now points at the note.
    primary_meta, _ = load_document(cfg.claims_dir / "clm_a.md")
    assert primary_meta["resolution"] == rel
    # Other side left untouched.
    other_meta, _ = load_document(cfg.claims_dir / "clm_b.md")
    assert other_meta.get("resolution") in (None, "null", "")
```

- [ ] **Step 2: Run**

Run: `pytest tests/reconcile/test_writer.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/reconcile/writer.py
from __future__ import annotations

from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.reconcile.client import ReconcileResponse
from second_brain.reconcile.finder import OpenDebate


def _resolution_slug(debate: OpenDebate) -> str:
    left = debate.left_id.removeprefix("clm_")
    right = debate.right_id.removeprefix("clm_")
    return f"{left}__vs__{right}"


def write_resolution(cfg: Config, debate: OpenDebate, resp: ReconcileResponse) -> str:
    """Write resolutions/<slug>.md and update the primary claim's frontmatter.

    Returns the resolution path relative to cfg.home (suitable for claim.resolution).
    """
    resolutions_dir = cfg.claims_dir / "resolutions"
    resolutions_dir.mkdir(parents=True, exist_ok=True)

    slug = _resolution_slug(debate)
    note_path = resolutions_dir / f"{slug}.md"
    body = (
        f"# {debate.left_id} vs {debate.right_id}\n\n"
        f"- applies_where: {resp.applies_where}\n"
        f"- primary: {resp.primary_claim_id}\n\n"
        f"{resp.resolution_md.strip()}\n"
    )
    if resp.rationale:
        body += f"\n## Rationale\n\n{resp.rationale.strip()}\n"
    note_path.write_text(body, encoding="utf-8")

    rel = str(note_path.relative_to(cfg.home))

    primary_path = Path(debate.left_path if debate.left_id == resp.primary_claim_id
                        else debate.right_path)
    meta, md_body = load_document(primary_path)
    meta["resolution"] = rel
    dump_document(primary_path, meta, md_body)
    return rel
```

- [ ] **Step 4: Run**

Run: `pytest tests/reconcile/test_writer.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/reconcile/writer.py tests/reconcile/test_writer.py
git commit -m "feat(reconcile): write_resolution writes note + updates primary frontmatter"
```

---

## Task 11: Reconcile worker + `sb reconcile` CLI

**Files:**
- Create: `src/second_brain/reconcile/worker.py`
- Modify: `src/second_brain/cli.py`
- Create: `tests/reconcile/test_worker.py`
- Create: `tests/reconcile/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/reconcile/test_worker.py
from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.habits import Habits
from second_brain.reconcile.client import FakeReconcilerClient
from second_brain.reconcile.worker import run_reconcile


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def _seed_pair(cfg: Config) -> None:
    old = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for slug, other in [("clm_a", "clm_b"), ("clm_b", "clm_a")]:
        (cfg.claims_dir / f"{slug}.md").write_text(
            "\n".join([
                "---",
                f"id: {slug}",
                f"statement: '{slug}'",
                "kind: empirical",
                "confidence: high",
                "scope: ''",
                f"contradicts: [{other}]",
                "supports: []",
                "refines: []",
                f"extracted_at: {old}",
                "status: active",
                "resolution: null",
                "abstract: ''",
                "---",
                "",
            ]),
            encoding="utf-8",
        )


def test_run_reconcile_writes_resolutions_for_each_debate(tmp_path):
    cfg = _cfg(tmp_path)
    _seed_pair(cfg)
    client = FakeReconcilerClient(canned={
        "resolution_md": "scope diff",
        "applies_where": "scope",
        "primary_claim_id": "clm_a",
    })
    report = run_reconcile(cfg, Habits.default(), client=client, limit=10)
    assert report.resolved == 1
    assert report.skipped == 0
    primary_meta, _ = load_document(cfg.claims_dir / "clm_a.md")
    assert primary_meta["resolution"].startswith("claims/resolutions/")


def test_run_reconcile_respects_limit(tmp_path):
    cfg = _cfg(tmp_path)
    _seed_pair(cfg)
    client = FakeReconcilerClient(canned={
        "resolution_md": "x", "applies_where": "scope", "primary_claim_id": "clm_a",
    })
    report = run_reconcile(cfg, Habits.default(), client=client, limit=0)
    assert report.resolved == 0


def test_run_reconcile_dry_run_does_not_mutate(tmp_path):
    cfg = _cfg(tmp_path)
    _seed_pair(cfg)
    client = FakeReconcilerClient(canned={
        "resolution_md": "x", "applies_where": "scope", "primary_claim_id": "clm_a",
    })
    report = run_reconcile(cfg, Habits.default(), client=client, limit=10, dry_run=True)
    assert report.resolved == 0
    assert report.proposed == 1
    primary_meta, _ = load_document(cfg.claims_dir / "clm_a.md")
    assert primary_meta.get("resolution") in (None, "null", "")
```

```python
# tests/reconcile/test_cli.py
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _init_sb_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _seed_pair(home: Path) -> None:
    old = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for slug, other in [("clm_a", "clm_b"), ("clm_b", "clm_a")]:
        (home / "claims" / f"{slug}.md").write_text(
            "\n".join([
                "---", f"id: {slug}", f"statement: '{slug}'",
                "kind: empirical", "confidence: high", "scope: ''",
                f"contradicts: [{other}]", "supports: []", "refines: []",
                f"extracted_at: {old}", "status: active", "resolution: null",
                "abstract: ''", "---", "",
            ]),
            encoding="utf-8",
        )


def test_sb_reconcile_fake_writes_resolution(tmp_path, monkeypatch):
    home = _init_sb_home(tmp_path, monkeypatch)
    _seed_pair(home)
    monkeypatch.setenv("SB_FAKE_RESOLUTION", json.dumps({
        "resolution_md": "scope diff",
        "applies_where": "scope",
        "primary_claim_id": "clm_a",
    }))
    res = CliRunner().invoke(cli, ["reconcile", "--fake", "--limit", "10"])
    assert res.exit_code == 0, res.output
    assert (home / "claims" / "resolutions").exists()
    assert any((home / "claims" / "resolutions").iterdir())


def test_sb_reconcile_dry_run_reports_without_writing(tmp_path, monkeypatch):
    home = _init_sb_home(tmp_path, monkeypatch)
    _seed_pair(home)
    monkeypatch.setenv("SB_FAKE_RESOLUTION", json.dumps({
        "resolution_md": "x", "applies_where": "scope", "primary_claim_id": "clm_a",
    }))
    res = CliRunner().invoke(
        cli, ["reconcile", "--fake", "--dry-run", "--limit", "10"]
    )
    assert res.exit_code == 0, res.output
    assert "proposed=1" in res.output
    assert not (home / "claims" / "resolutions").exists()
```

- [ ] **Step 2: Run**

Run: `pytest tests/reconcile/test_worker.py tests/reconcile/test_cli.py -v`
Expected: FAIL (worker module missing, reconcile command not registered).

- [ ] **Step 3: Implement worker + CLI**

```python
# src/second_brain/reconcile/worker.py
from __future__ import annotations

from dataclasses import dataclass

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.habits import Habits
from second_brain.log import EventKind, append_event
from second_brain.reconcile.client import ReconcileRequest, ReconcilerClient
from second_brain.reconcile.finder import find_open_debates
from second_brain.reconcile.writer import write_resolution


@dataclass(frozen=True)
class ReconcileReport:
    resolved: int
    proposed: int
    skipped: int


def _claim_body(path: str) -> str:
    _meta, body = load_document(path)
    return body


def run_reconcile(
    cfg: Config,
    habits: Habits,
    *,
    client: ReconcilerClient,
    limit: int,
    dry_run: bool = False,
) -> ReconcileReport:
    debates = find_open_debates(cfg, habits)
    if limit <= 0:
        return ReconcileReport(resolved=0, proposed=0, skipped=len(debates))

    resolved = 0
    proposed = 0
    skipped = 0
    for debate in debates[:limit]:
        try:
            req = ReconcileRequest(
                claim_a_id=debate.left_id,
                claim_b_id=debate.right_id,
                claim_a_body=_claim_body(debate.left_path),
                claim_b_body=_claim_body(debate.right_path),
                supports_a="",  # v1: supports bodies deferred; see spec §16.
                supports_b="",
            )
            resp = client.reconcile(req)
        except Exception as exc:  # noqa: BLE001
            skipped += 1
            append_event(
                kind=EventKind.ERROR, op="reconcile.call_failed",
                subject=f"{debate.left_id}__vs__{debate.right_id}",
                value=str(exc), home=cfg.home,
            )
            continue

        if dry_run:
            proposed += 1
            append_event(
                kind=EventKind.SUGGEST, op="reconcile.proposed",
                subject=f"{debate.left_id}__vs__{debate.right_id}",
                value=resp.primary_claim_id,
                reason={"applies_where": resp.applies_where},
                home=cfg.home,
            )
            continue

        rel = write_resolution(cfg, debate, resp)
        resolved += 1
        append_event(
            kind=EventKind.AUTO if habits.autonomy.for_op("reconciliation.resolution") == "auto"
            else EventKind.USER_OVERRIDE,
            op="reconcile.resolved",
            subject=f"{debate.left_id}__vs__{debate.right_id}",
            value=rel,
            reason={"applies_where": resp.applies_where, "primary": resp.primary_claim_id},
            home=cfg.home,
        )

    return ReconcileReport(resolved=resolved, proposed=proposed, skipped=skipped)
```

Append to `src/second_brain/cli.py`:

```python
@cli.command(name="reconcile")
@click.option("--limit", default=10, type=int,
              help="Max debates to process this run.")
@click.option("--dry-run", is_flag=True, default=False,
              help="Propose without writing resolutions.")
@click.option("--live/--fake", default=None,
              help="Force real Anthropic call (--live) or fake client (--fake). "
                   "Default: fake if ANTHROPIC_API_KEY unset or SB_FAKE_RESOLUTION set.")
def _reconcile(limit: int, dry_run: bool, live: bool | None) -> None:
    """Resolve open contradictions with Claude (or the fake client)."""
    import json as _json
    import os

    from second_brain.habits.loader import load_habits
    from second_brain.reconcile.client import (
        AnthropicReconcilerClient, FakeReconcilerClient,
    )
    from second_brain.reconcile.worker import run_reconcile

    cfg = Config.load()
    habits = load_habits(cfg)

    fake_payload = os.environ.get("SB_FAKE_RESOLUTION")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if live is True and not api_key:
        raise click.ClickException("ANTHROPIC_API_KEY not set; cannot run --live")
    use_fake = (live is False) or fake_payload or not api_key
    if use_fake:
        canned = _json.loads(fake_payload) if fake_payload else {
            "resolution_md": "(fake-canned) scope difference",
            "applies_where": "scope",
            "primary_claim_id": "clm_unknown",
        }
        client = FakeReconcilerClient(canned=canned)
    else:
        client = AnthropicReconcilerClient()

    report = run_reconcile(cfg, habits, client=client, limit=limit, dry_run=dry_run)
    click.echo(
        f"resolved={report.resolved} proposed={report.proposed} skipped={report.skipped}"
    )
```

- [ ] **Step 4: Run**

Run: `pytest tests/reconcile/ -v` — 8 passed.
Run: `pytest -m "not integration" -q` — full fast suite green; coverage ≥75%.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/reconcile/worker.py src/second_brain/cli.py \
        tests/reconcile/test_worker.py tests/reconcile/test_cli.py
git commit -m "feat(reconcile): run_reconcile worker + sb reconcile CLI (fake/live, dry-run)"
```

---

## Task 12: claude-code-agent — config flag + editable install

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/pyproject.toml` (or `requirements.txt`, whichever is authoritative)
- Create: `backend/tests/test_config_second_brain.py`

This task lands in the **claude-code-agent** repo (`~/Developer/claude-code-agent/`).

- [ ] **Step 1: Inspect the current config module**

Run: `rg -n "^(class Config|SECOND_BRAIN|settings =)" backend/app/config.py` to see the shape. Preserve the existing pattern (module-level constants or a settings object).

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_config_second_brain.py
import importlib
import os
from pathlib import Path


def test_second_brain_disabled_when_home_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path / "nonexistent"))
    from app import config
    importlib.reload(config)
    assert config.SECOND_BRAIN_ENABLED is False


def test_second_brain_enabled_when_sb_dir_present(monkeypatch, tmp_path):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    from app import config
    importlib.reload(config)
    assert config.SECOND_BRAIN_HOME == home
    assert config.SECOND_BRAIN_ENABLED is True
```

- [ ] **Step 3: Run the test**

Run: `cd backend && pytest tests/test_config_second_brain.py -v`
Expected: FAIL (`AttributeError: module 'app.config' has no attribute 'SECOND_BRAIN_ENABLED'`).

- [ ] **Step 4: Add config constants**

Append to `backend/app/config.py` (end of file, keep existing exports intact):

```python
# ── Second Brain integration ────────────────────────────────────────────────
import os as _os
from pathlib import Path as _Path


def _resolve_sb_home() -> _Path:
    raw = _os.environ.get("SECOND_BRAIN_HOME")
    return _Path(raw).expanduser() if raw else _Path.home() / "second-brain"


SECOND_BRAIN_HOME: _Path = _resolve_sb_home()
SECOND_BRAIN_ENABLED: bool = (
    SECOND_BRAIN_HOME.exists() and (SECOND_BRAIN_HOME / ".sb").exists()
)
```

- [ ] **Step 5: Add `second-brain` as a local editable dep**

Pick whichever of the following matches the project's build system.

**If `backend/pyproject.toml` uses Poetry:** add under `[tool.poetry.dependencies]`:

```toml
second-brain = {path = "../../second-brain", develop = true}
```

**If it uses PEP 621 (setuptools/hatch) with `[project.optional-dependencies]`:** add:

```toml
[project.optional-dependencies]
second-brain = ["second-brain @ file:///../../second-brain"]
```

and install with `pip install -e '.[second-brain]'`.

**If the project uses `requirements.txt`:** add a line:

```
-e ../../second-brain
```

Run the project's install command once to pick up the link. Example:

```bash
cd backend && pip install -e ../../second-brain
```

- [ ] **Step 6: Re-run the test**

Run: `cd backend && pytest tests/test_config_second_brain.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit (claude-code-agent repo)**

```bash
git add backend/app/config.py backend/pyproject.toml backend/tests/test_config_second_brain.py
git commit -m "feat(second-brain): config flag + editable install of second_brain package"
```

(Include `backend/requirements.txt` in `git add` instead if that's what the project uses.)

---

## Task 13: `sb_tools.py` handlers with graceful degradation

**Files:**
- Create: `backend/app/tools/__init__.py`
- Create: `backend/app/tools/sb_tools.py`
- Create: `backend/tests/tools/__init__.py`
- Create: `backend/tests/tools/test_sb_tools.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/tools/test_sb_tools.py
import importlib
from pathlib import Path


def _point_at_home(monkeypatch, home: Path, enabled: bool) -> None:
    if enabled:
        (home / ".sb").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    from app import config
    importlib.reload(config)


def test_sb_search_no_op_when_disabled(monkeypatch, tmp_path):
    _point_at_home(monkeypatch, tmp_path / "sb", enabled=False)
    from app.tools import sb_tools
    importlib.reload(sb_tools)
    res = sb_tools.sb_search({"query": "x"})
    assert res == {"ok": False, "error": "second_brain_disabled", "hits": []}


def test_sb_search_returns_hits_when_enabled(monkeypatch, tmp_path):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    # Minimal FTS5 index so BM25Retriever can respond.
    import sqlite3
    db = sqlite3.connect(home / ".sb" / "kb.sqlite")
    db.executescript(
        """
        CREATE VIRTUAL TABLE claim_fts USING fts5(
            claim_id UNINDEXED, statement, abstract, body, taxonomy,
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE VIRTUAL TABLE source_fts USING fts5(
            source_id UNINDEXED, title, abstract, processed_body, taxonomy,
            tokenize='unicode61 remove_diacritics 2'
        );
        INSERT INTO claim_fts(claim_id, statement, abstract, body, taxonomy)
        VALUES ('clm_x', 'attention alone suffices', 'attention', 'body', 'papers/ml');
        """
    )
    db.commit()
    db.close()
    _point_at_home(monkeypatch, home, enabled=True)

    from app.tools import sb_tools
    importlib.reload(sb_tools)
    res = sb_tools.sb_search({"query": "attention", "k": 3, "scope": "claims"})
    assert res["ok"] is True
    assert any(h["id"] == "clm_x" for h in res["hits"])


def test_sb_load_unknown_id_returns_error(monkeypatch, tmp_path):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    _point_at_home(monkeypatch, home, enabled=True)
    from app.tools import sb_tools
    importlib.reload(sb_tools)
    res = sb_tools.sb_load({"node_id": "clm_doesnt_exist"})
    assert res["ok"] is False


def test_sb_ingest_rejects_path_when_disabled(monkeypatch, tmp_path):
    _point_at_home(monkeypatch, tmp_path / "sb", enabled=False)
    from app.tools import sb_tools
    importlib.reload(sb_tools)
    res = sb_tools.sb_ingest({"path": str(tmp_path / "doc.md")})
    assert res == {"ok": False, "error": "second_brain_disabled"}
```

- [ ] **Step 2: Run**

Run: `cd backend && pytest tests/tools/test_sb_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.tools.sb_tools'`.

- [ ] **Step 3: Implement the handlers**

```python
# backend/app/tools/__init__.py
```

```python
# backend/app/tools/sb_tools.py
"""Second-Brain tool handlers. Each function returns a JSON-serializable dict.

When the Second-Brain KB is disabled (directory missing), every handler
returns a structured error rather than raising, so the agent loop keeps
working without the KB.
"""
from __future__ import annotations

from typing import Any

from app import config


def _disabled(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "error": "second_brain_disabled"}
    if extra:
        out.update(extra)
    return out


def _cfg():  # noqa: ANN202
    from second_brain.config import Config
    return Config.load()


def sb_search(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled({"hits": []})
    from second_brain.index.retriever import BM25Retriever

    query = str(args.get("query", ""))
    if not query:
        return {"ok": False, "error": "missing query", "hits": []}
    k = int(args.get("k", 5))
    scope = str(args.get("scope", "both"))
    taxonomy = args.get("taxonomy")
    with_neighbors = bool(args.get("with_neighbors", False))

    cfg = _cfg()
    if not cfg.fts_path.exists():
        return {"ok": False, "error": "no_index", "hits": []}

    retriever = BM25Retriever(cfg)
    hits = retriever.search(
        query, k=k, scope=scope,  # type: ignore[arg-type]
        taxonomy=taxonomy, with_neighbors=with_neighbors,
    )
    return {"ok": True, "hits": [
        {"id": h.id, "kind": h.kind, "score": h.score,
         "matched_field": h.matched_field, "snippet": h.snippet,
         "neighbors": h.neighbors}
        for h in hits
    ]}


def sb_load(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    from second_brain.load import LoadError, load_node

    node_id = str(args.get("node_id", ""))
    if not node_id:
        return {"ok": False, "error": "missing node_id"}
    depth = int(args.get("depth", 0))
    relations = args.get("relations") or None
    if isinstance(relations, str):
        relations = [r.strip() for r in relations.split(",") if r.strip()]

    cfg = _cfg()
    try:
        result = load_node(cfg, node_id, depth=depth, relations=relations)
    except LoadError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "root": result.root, "neighbors": result.neighbors,
            "edges": result.edges}


def sb_reason(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled({"paths": []})
    from second_brain.reason import GraphPattern, sb_reason as _run

    start_id = str(args.get("start_id", ""))
    walk = str(args.get("walk", ""))
    if not start_id or not walk:
        return {"ok": False, "error": "start_id and walk required", "paths": []}
    direction = str(args.get("direction", "outbound"))
    max_depth = int(args.get("max_depth", 3))
    terminator = args.get("terminator")

    cfg = _cfg()
    paths = _run(cfg, start_id=start_id,
                 pattern=GraphPattern(walk=walk, direction=direction,  # type: ignore[arg-type]
                                       max_depth=max_depth, terminator=terminator))
    return {"ok": True, "paths": paths}


def sb_ingest(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    from pathlib import Path as _Path

    from second_brain.ingest.base import IngestInput
    from second_brain.ingest.orchestrator import IngestError, ingest

    path_or_url = str(args.get("path", ""))
    if not path_or_url:
        return {"ok": False, "error": "missing path"}

    cfg = _cfg()
    try:
        if path_or_url.startswith(("http://", "https://", "gh:", "file://")):
            # URL and repo converters accept origin strings via IngestInput.from_origin;
            # fall back to a path if the URL/repo shorthand isn't supported here.
            inp = IngestInput.from_path(_Path(path_or_url)) \
                if _Path(path_or_url).exists() else None
            if inp is None:
                # Future: add IngestInput.from_origin for URLs/repos.
                return {"ok": False, "error": "url/repo ingest via tool not yet supported"}
        else:
            inp = IngestInput.from_path(_Path(path_or_url))
        folder = ingest(inp, cfg=cfg)
    except IngestError as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "source_id": folder.root.name, "folder": str(folder.root)}


def sb_promote_claim(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()
    # v1: claude-code-agent wiki findings don't yet carry ids that second-brain
    # can resolve. Return a structured not-implemented so the agent can continue.
    return {"ok": False, "error": "sb_promote_claim not wired in v1 bridge"}
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/tools/test_sb_tools.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools/__init__.py backend/app/tools/sb_tools.py \
        backend/tests/tools/__init__.py backend/tests/tools/test_sb_tools.py
git commit -m "feat(second-brain): sb_* tool handlers with disabled/no-index guards"
```

---

## Task 14: Register ToolSchemas + dispatcher handlers

**Files:**
- Modify: `backend/app/api/chat_api.py`
- Create: `backend/tests/api/test_chat_api_sb_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_chat_api_sb_tools.py
from app.api.chat_api import _CHAT_TOOLS


def test_sb_tool_schemas_present():
    names = {t.name for t in _CHAT_TOOLS}
    assert {"sb_search", "sb_load", "sb_reason", "sb_ingest", "sb_promote_claim"} <= names


def test_sb_search_schema_requires_query():
    schema = next(t for t in _CHAT_TOOLS if t.name == "sb_search").input_schema
    assert "query" in schema["required"]


def test_sb_load_schema_has_node_id_and_depth():
    schema = next(t for t in _CHAT_TOOLS if t.name == "sb_load").input_schema
    assert "node_id" in schema["required"]
    assert "depth" in schema["properties"]
```

- [ ] **Step 2: Run**

Run: `cd backend && pytest tests/api/test_chat_api_sb_tools.py -v`
Expected: FAIL — assertions fail because the new schemas are not yet in `_CHAT_TOOLS`.

- [ ] **Step 3: Add ToolSchemas**

Add these five schema constants in `backend/app/api/chat_api.py` near the existing tool-schema block (right after `_SEARCH_TEXT`):

```python
_SB_SEARCH = ToolSchema(
    name="sb_search",
    description=(
        "BM25 search against the Second Brain knowledge base. "
        "Returns top-k claims and/or sources ranked by relevance. "
        "Use to find prior extracted claims or source material before answering."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language query."},
            "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 50},
            "scope": {"type": "string", "enum": ["claims", "sources", "both"], "default": "both"},
            "taxonomy": {"type": ["string", "null"], "description": "Optional taxonomy prefix filter."},
            "with_neighbors": {"type": "boolean", "default": False},
        },
        "required": ["query"],
    },
)

_SB_LOAD = ToolSchema(
    name="sb_load",
    description=(
        "Load a Second Brain node (claim or source) by id, optionally expanding "
        "its graph neighborhood. Use after sb_search identifies an interesting id."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "node_id": {"type": "string"},
            "depth": {"type": "integer", "default": 0, "minimum": 0, "maximum": 3},
            "relations": {"type": ["string", "null"], "description":
                "Comma-separated edge types to follow (supports, contradicts, cites, refines, …)."},
        },
        "required": ["node_id"],
    },
)

_SB_REASON = ToolSchema(
    name="sb_reason",
    description=(
        "Walk the Second Brain graph from start_id along a typed relation. "
        "Use for 'what does X support?' or 'what contradicts Y?' style traversals."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "start_id": {"type": "string"},
            "walk": {"type": "string", "description":
                "Edge relation to walk, e.g. 'supports' or 'refines'."},
            "direction": {"type": "string", "enum": ["outbound", "inbound", "both"], "default": "outbound"},
            "max_depth": {"type": "integer", "default": 3, "minimum": 1, "maximum": 6},
            "terminator": {"type": ["string", "null"], "description":
                "Optional relation to stop on (e.g. 'supersedes')."},
        },
        "required": ["start_id", "walk"],
    },
)

_SB_INGEST = ToolSchema(
    name="sb_ingest",
    description=(
        "Ingest a local file (PDF, markdown, DOCX, EPUB) into the Second Brain "
        "knowledge base. URL/repo ingest via tool is not yet supported — drop those "
        "into ~/second-brain/inbox/ and run `sb process-inbox`."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file to ingest."},
        },
        "required": ["path"],
    },
)

_SB_PROMOTE_CLAIM = ToolSchema(
    name="sb_promote_claim",
    description=(
        "Promote a validated wiki finding into a Second Brain claim node. "
        "Not yet wired in v1 — returns a structured not-implemented."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "finding_id": {"type": "string"},
        },
        "required": ["finding_id"],
    },
)
```

Then extend `_CHAT_TOOLS`:

```python
_CHAT_TOOLS: tuple[ToolSchema, ...] = (
    _EXECUTE_PYTHON,
    _WRITE_WORKING,
    _LOAD_SKILL,
    _SAVE_ARTIFACT,
    _PROMOTE_FINDING,
    _DELEGATE_SUBAGENT,
    _TODO_WRITE,
    _GET_CONTEXT_STATUS,
    _READ_FILE,
    _GLOB_FILES,
    _SEARCH_TEXT,
    _SB_SEARCH,
    _SB_LOAD,
    _SB_REASON,
    _SB_INGEST,
    _SB_PROMOTE_CLAIM,
)
```

And register handlers in the same spot where `get_context_status` is registered (right before `loop = AgentLoop(...)`):

```python
            # ── Second Brain tools (no-op when disabled) ─────────────────
            from app.tools import sb_tools as _sb
            dispatcher.register("sb_search", _sb.sb_search)
            dispatcher.register("sb_load", _sb.sb_load)
            dispatcher.register("sb_reason", _sb.sb_reason)
            dispatcher.register("sb_ingest", _sb.sb_ingest)
            dispatcher.register("sb_promote_claim", _sb.sb_promote_claim)
```

- [ ] **Step 4: Run**

Run: `cd backend && pytest tests/api/test_chat_api_sb_tools.py tests/tools/ -v`
Expected: 7 passed.
Run: `cd backend && pytest -q` — full backend suite still green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat_api.py backend/tests/api/test_chat_api_sb_tools.py
git commit -m "feat(second-brain): register sb_search/load/reason/ingest/promote_claim tools"
```

---

## Task 15: Hook wiring in `.claude/settings.json`

**Files:**
- Modify: `.claude/settings.json`
- Create: `tests/settings/test_claude_settings.py` (at repo root, or under `backend/tests/` if that's the testing home)

- [ ] **Step 1: Inspect current settings**

Run: `cat .claude/settings.json | head -40` so you know the existing structure. Do not clobber unrelated keys.

- [ ] **Step 2: Write the failing test**

```python
# tests/settings/test_claude_settings.py
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / ".claude" / "settings.json"


def test_settings_file_exists():
    assert SETTINGS.exists(), f"{SETTINGS} missing"


def test_user_prompt_submit_has_sb_inject_hook():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    ups = data.get("hooks", {}).get("UserPromptSubmit", [])
    cmds = [h.get("command", "") for h in ups]
    assert any("sb inject" in c and "--prompt-stdin" in c for c in cmds), \
        f"no sb inject hook in UserPromptSubmit: {cmds}"


def test_post_tool_use_has_sb_reindex_matcher():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    ptu = data.get("hooks", {}).get("PostToolUse", [])
    hits = [h for h in ptu
            if "sb_ingest" in (h.get("matcher") or "")
            or "sb_promote_claim" in (h.get("matcher") or "")]
    assert hits, f"no sb reindex hook in PostToolUse: {ptu}"
    assert any("sb reindex" in h.get("command", "") for h in hits)
```

- [ ] **Step 3: Run**

Run: `pytest tests/settings/test_claude_settings.py -v`
Expected: FAIL (no hook entries yet).

- [ ] **Step 4: Add the hook entries**

Open `.claude/settings.json` and merge in (preserving existing hooks):

```jsonc
{
  "hooks": {
    "UserPromptSubmit": [
      { "command": "sb inject --k 5 --scope claims --max-tokens 800 --prompt-stdin" }
    ],
    "PostToolUse": [
      {
        "matcher": "sb_ingest|sb_promote_claim",
        "command": "sb reindex"
      }
    ]
  }
}
```

If the file already defines `hooks.UserPromptSubmit` / `hooks.PostToolUse` arrays, append the new entries; do not overwrite existing ones.

- [ ] **Step 5: Run the tests**

Run: `pytest tests/settings/test_claude_settings.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add .claude/settings.json tests/settings/test_claude_settings.py
git commit -m "feat(second-brain): UserPromptSubmit + PostToolUse hook wiring"
```

---

## Self-review

**Spec coverage:**

| Spec §/requirement | Covered by |
|---|---|
| §10 `habits.yaml` schema complete | Task 1 |
| §10 habits load / save / validate | Task 2 |
| §5.5 "Adaptive density resolution: by_kind → by_taxonomy → default_density" | Tasks 3, 4 |
| §8.4 `sb inject` hook + block format | Tasks 5, 6, 7 |
| §8.4 skip_patterns / min_score gates | Task 6 |
| §7.4 `sb reconcile` reads debates → proposes resolution → writes note + updates primary | Tasks 9, 10, 11 |
| §10.2 autonomy `reconciliation.resolution` hitl vs auto | Task 11 (`dry_run`, `habits.autonomy.for_op`) |
| §12.1 skill + tools + hook artifacts in claude-code-agent | Tasks 13, 14, 15 |
| §12.2 `SECOND_BRAIN_ENABLED` graceful degradation | Task 12, `_disabled()` branches |
| §12.3 MCP upgrade path | Not required in v1; out of scope (explicitly noted in plan header) |
| §8.5 hybrid retrieval extension point | Not in v1 plan; preserved via `BM25Retriever` behind the `Retriever` protocol |

**Explicit deferrals to later plans:**
- Wizard (`sb init`) and per-op autonomy elaboration — plan 5.
- Habit-learning detector + `proposals/` dir + auto-apply with revert — plan 5.
- `sb watch` daemon + `sb maintain` cron + health score — plan 6.
- Eval harness (`sb eval` + nDCG / recall@k fixtures) — plan 6.
- URL/repo ingest via the `sb_ingest` agent tool — deferred because it requires `IngestInput.from_origin` plumbing; tracked via structured error response from Task 13 handler.
- `sb_promote_claim` wiring to wiki findings — deferred; handler returns structured not-implemented.

**Placeholder scan:** No "TBD" / "implement later" steps survive. Every code block is either complete or an explicit placeholder whose full impl is a later step in the same plan (Task 5's `runner.py` placeholder is replaced in Task 6).

**Type consistency:**
- `Density` is `Literal["sparse", "moderate", "dense"]` in `habits/schema.py` and reused in `habits/density.py` and the modified `_extract`.
- `ReconcileRequest` / `ReconcileResponse` dataclasses introduced in Task 8 are the exact shapes consumed in Tasks 10 and 11.
- `OpenDebate` introduced in Task 9 is used verbatim in Tasks 10, 11.
- `InjectionResult` introduced in Task 5's placeholder matches the Task 6 implementation.

**Execution handoff:** Subagent-driven. Four batches:
- **Batch A (~/Developer/second-brain):** Tasks 1–4 — one subagent.
- **Batch B (~/Developer/second-brain):** Tasks 5–7 — one subagent.
- **Batch C (~/Developer/second-brain):** Tasks 8–11 — one subagent.
- **Batch D (~/Developer/claude-code-agent):** Tasks 12–15 — one subagent.

Each batch: TDD discipline, verbatim commit messages, stay inside its working directory, do NOT dispatch further subagents, do NOT modify the other repo, keep test suites green + coverage gates honored.
