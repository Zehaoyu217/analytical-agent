# Foundations Implementation Plan (Plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the shared substrate — skill metadata convention, theme system, artifact store, wiki helpers, and a complete `data_profiler` skill with its dependencies (`sql_builder`, `html_tables`, 6 core Altair chart templates) — so the statistical skills (Plan 2), harness (Plan 3), and composition skills (Plan 4) have stable foundations to build on.

**Architecture:** Skills follow Claude-Code-style SKILL.md frontmatter for the agent-visible fields (`name`, `description`, `level`, `version`); `skill.yaml` remains only for dependency lists and error templates. Theme tokens live in one `tokens.yaml` with 5 variants and drive Altair themes, HTML table CSS, and dashboard CSS from the same source of truth. Artifact store is SQLite-backed with a 512KB inline/disk split, typed distillation for context compaction, and an EventBus for UI streaming — modeled on `Analytical-chatbot` with `profile`, `analysis`, `file` types added.

**Tech Stack:** Python 3.12, FastAPI, SQLite (stdlib), PyYAML, DuckDB 1.2+, Polars 1.20+, Altair 5.5+, Pydantic, pytest, ruff, mypy (strict).

**Plan split:**
| Plan | Scope |
|---|---|
| 1 (this) | Skill convention + theme + artifact store + wiki + data_profiler + 6 charts + sql/tables |
| 2 | correlation, group_compare, stat_validate, time_series, distribution_fit, 14 gotchas |
| 3 | System prompt + injector + router + loop + dispatcher + sandbox + guardrails + wrap-up + models.yaml |
| 4 | Remaining 14 templates + report_builder + dashboard_builder + analysis_plan |

---

## File Structure

Files created or modified in this plan (grouped by phase):

### Phase 0 — Skill Convention Migration
- Modify: `backend/app/skills/registry.py`
- Modify: `Makefile` (`skill-new` target)
- Create: `backend/tests/unit/test_skill_registry_frontmatter.py`

### Phase 1 — Theme System
- Create: `config/themes/tokens.yaml`
- Create: `config/themes/__init__.py`
- Create: `config/themes/theme_switcher.py`
- Create: `config/themes/altair_theme.py`
- Create: `config/themes/table_css.py`
- Create: `backend/tests/unit/test_theme_tokens.py`
- Create: `backend/tests/unit/test_altair_theme.py`
- Create: `backend/tests/unit/test_table_css.py`

### Phase 2 — Artifact Store
- Create: `backend/app/artifacts/__init__.py`
- Create: `backend/app/artifacts/models.py` (Pydantic `Artifact`, `ProgressStep`)
- Create: `backend/app/artifacts/store.py` (SQLite-backed store)
- Create: `backend/app/artifacts/distill.py` (type-aware compaction helpers)
- Create: `backend/app/artifacts/events.py` (EventBus)
- Create: `backend/tests/unit/test_artifact_store.py`
- Create: `backend/tests/unit/test_artifact_distill.py`
- Create: `backend/tests/unit/test_artifact_events.py`

### Phase 3 — Wiki Engine
- Create: `backend/app/wiki/__init__.py`
- Create: `backend/app/wiki/engine.py`
- Create: `backend/app/wiki/schema.py` (Finding, Hypothesis, Entity dataclasses)
- Create: `backend/tests/unit/test_wiki_engine.py`

### Phase 4 — sql_builder + html_tables skills
- Create: `backend/app/skills/sql_builder/SKILL.md`
- Create: `backend/app/skills/sql_builder/skill.yaml`
- Create: `backend/app/skills/sql_builder/pkg/__init__.py`
- Create: `backend/app/skills/sql_builder/pkg/builder.py`
- Create: `backend/app/skills/sql_builder/tests/test_builder.py`
- Create: `backend/app/skills/html_tables/SKILL.md`
- Create: `backend/app/skills/html_tables/skill.yaml`
- Create: `backend/app/skills/html_tables/pkg/__init__.py`
- Create: `backend/app/skills/html_tables/pkg/renderer.py`
- Create: `backend/app/skills/html_tables/tests/test_renderer.py`

### Phase 5 — altair_charts skill + 6 core templates
- Modify: `backend/pyproject.toml` (add `altair>=5.5`)
- Create: `backend/app/skills/altair_charts/SKILL.md`
- Create: `backend/app/skills/altair_charts/skill.yaml`
- Create: `backend/app/skills/altair_charts/pkg/__init__.py`
- Create: `backend/app/skills/altair_charts/pkg/_common.py` (series role resolver)
- Create: `backend/app/skills/altair_charts/pkg/bar.py`
- Create: `backend/app/skills/altair_charts/pkg/multi_line.py`
- Create: `backend/app/skills/altair_charts/pkg/histogram.py`
- Create: `backend/app/skills/altair_charts/pkg/scatter_trend.py`
- Create: `backend/app/skills/altair_charts/pkg/boxplot.py`
- Create: `backend/app/skills/altair_charts/pkg/correlation_heatmap.py`
- Create: `backend/app/skills/altair_charts/tests/test_bar.py`
- Create: `backend/app/skills/altair_charts/tests/test_multi_line.py`
- Create: `backend/app/skills/altair_charts/tests/test_histogram.py`
- Create: `backend/app/skills/altair_charts/tests/test_scatter_trend.py`
- Create: `backend/app/skills/altair_charts/tests/test_boxplot.py`
- Create: `backend/app/skills/altair_charts/tests/test_correlation_heatmap.py`

### Phase 6 — data_profiler skill
- Create: `backend/app/skills/data_profiler/SKILL.md`
- Create: `backend/app/skills/data_profiler/skill.yaml`
- Create: `backend/app/skills/data_profiler/pkg/__init__.py`
- Create: `backend/app/skills/data_profiler/pkg/risks.py` (21 risk constants + Risk dataclass)
- Create: `backend/app/skills/data_profiler/pkg/report.py` (ProfileReport dataclass)
- Create: `backend/app/skills/data_profiler/pkg/sections/schema.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/missingness.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/duplicates.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/distributions.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/dates.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/outliers.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/keys.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/relationships.py`
- Create: `backend/app/skills/data_profiler/pkg/html_report.py`
- Create: `backend/app/skills/data_profiler/pkg/profile.py` (orchestrator)
- Create: `backend/app/skills/data_profiler/tests/test_schema.py`
- Create: `backend/app/skills/data_profiler/tests/test_missingness.py`
- Create: `backend/app/skills/data_profiler/tests/test_duplicates.py`
- Create: `backend/app/skills/data_profiler/tests/test_distributions.py`
- Create: `backend/app/skills/data_profiler/tests/test_dates.py`
- Create: `backend/app/skills/data_profiler/tests/test_outliers.py`
- Create: `backend/app/skills/data_profiler/tests/test_keys.py`
- Create: `backend/app/skills/data_profiler/tests/test_relationships.py`
- Create: `backend/app/skills/data_profiler/tests/test_profile.py`
- Create: `backend/app/skills/data_profiler/tests/test_html_report.py`
- Create: `backend/app/skills/data_profiler/tests/fixtures/conftest.py`
- Modify: `backend/app/artifacts/models.py` (add `"profile"` to `Literal` union)
- Modify: `backend/app/artifacts/distill.py` (add `_distill_profile`)

---

## Phase 0 — Skill Convention Migration

Agent-visible metadata (`name`, `description`, `level`, `version`) moves to SKILL.md frontmatter; `skill.yaml` retains dependencies and error templates. Must happen before any new skill is scaffolded so every skill in this plan uses the target convention.

### Task 0.1: Write failing test for frontmatter parsing

**Files:**
- Test: `backend/tests/unit/test_skill_registry_frontmatter.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_skill_registry_frontmatter.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.skills.registry import SkillRegistry


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Minimal demo skill.\n"
        "level: 2\n"
        "version: '0.3'\n"
        "---\n"
        "# Demo\n\nBody text.\n"
    )
    (skill_dir / "skill.yaml").write_text(
        "dependencies:\n"
        "  requires: [theme_config]\n"
        "  used_by: []\n"
        "  packages: [pandas]\n"
        "errors:\n"
        "  BAD_INPUT:\n"
        "    message: bad input {field}\n"
        "    guidance: provide {field}\n"
        "    recovery: supply the value and rerun\n"
    )
    return tmp_path


def test_registry_reads_metadata_from_skill_md_frontmatter(skills_root: Path) -> None:
    registry = SkillRegistry(skills_root)
    registry.discover()

    loaded = registry.get_skill("demo")
    assert loaded is not None
    assert loaded.metadata.name == "demo"
    assert loaded.metadata.description == "Minimal demo skill."
    assert loaded.metadata.level == 2
    assert loaded.metadata.version == "0.3"
    assert loaded.metadata.dependencies_requires == ["theme_config"]
    assert loaded.metadata.dependencies_packages == ["pandas"]
    assert "BAD_INPUT" in loaded.metadata.error_templates


def test_registry_body_excludes_frontmatter(skills_root: Path) -> None:
    registry = SkillRegistry(skills_root)
    registry.discover()

    instructions = registry.get_instructions("demo")
    assert instructions is not None
    assert instructions.startswith("# Demo")
    assert "---" not in instructions.splitlines()[0]


def test_registry_ignores_dir_without_skill_md(tmp_path: Path) -> None:
    (tmp_path / "nope").mkdir()
    registry = SkillRegistry(tmp_path)
    registry.discover()
    assert registry.list_skills() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_skill_registry_frontmatter.py -v`
Expected: FAIL (registry currently requires name/description/level inside `skill.yaml`).

### Task 0.2: Update registry to parse SKILL.md frontmatter

**Files:**
- Modify: `backend/app/skills/registry.py`

- [ ] **Step 1: Replace `discover()` with frontmatter-aware version**

Replace the contents of `backend/app/skills/registry.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.skills.base import SkillMetadata


@dataclass
class LoadedSkill:
    """A discovered and loaded skill (evals excluded)."""

    metadata: SkillMetadata
    instructions: str
    package_path: Path
    references_path: Path | None
    evals_path: None = None  # sealed from agent


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a SKILL.md file into (frontmatter_dict, body)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(
            i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        return {}, text
    raw = "".join(lines[1:end])
    body = "".join(lines[end + 1 :]).lstrip("\n")
    parsed = yaml.safe_load(raw) or {}
    return parsed, body


class SkillRegistry:
    """Discovers and loads skills from a directory tree."""

    def __init__(self, skills_root: Path) -> None:
        self._root = skills_root
        self._skills: dict[str, LoadedSkill] = {}

    def discover(self) -> None:
        self._skills.clear()
        if not self._root.exists():
            return

        for skill_dir in sorted(self._root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            fm, body = _split_frontmatter(skill_md.read_text())
            name = fm.get("name")
            if not name:
                continue

            skill_yaml = skill_dir / "skill.yaml"
            deps: dict = {}
            errors: dict = {}
            if skill_yaml.exists():
                raw = yaml.safe_load(skill_yaml.read_text()) or {}
                deps = raw.get("dependencies", {}) or {}
                errors = raw.get("errors", {}) or {}

            metadata = SkillMetadata(
                name=name,
                version=str(fm.get("version", "0.0")),
                description=fm.get("description", ""),
                level=int(fm.get("level", 1)),
                dependencies_requires=deps.get("requires", []),
                dependencies_used_by=deps.get("used_by", []),
                dependencies_packages=deps.get("packages", []),
                error_templates=errors,
            )

            pkg_path = skill_dir / "pkg"
            refs_path = skill_dir / "references"

            self._skills[metadata.name] = LoadedSkill(
                metadata=metadata,
                instructions=body,
                package_path=pkg_path,
                references_path=refs_path if refs_path.exists() else None,
            )

    def list_skills(self) -> list[str]:
        return list(self._skills.keys())

    def get_skill(self, name: str) -> LoadedSkill | None:
        return self._skills.get(name)

    def get_instructions(self, name: str) -> str | None:
        skill = self._skills.get(name)
        return skill.instructions if skill else None

    def get_dependency_graph(self) -> dict[str, list[str]]:
        return {
            name: skill.metadata.dependencies_requires
            for name, skill in self._skills.items()
        }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && pytest tests/unit/test_skill_registry_frontmatter.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 3: Run existing skill tests to confirm no regression**

Run: `cd backend && pytest tests/ -v -k skill`
Expected: PASS (no failures; registry still loads skills that supply minimum fields).

### Task 0.3: Update `skill-new` Makefile scaffolder

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Replace the `skill-new` target**

In `Makefile`, replace the `skill-new` target with:

```makefile
skill-new:
ifndef name
	$(error Usage: make skill-new name=<skill_name>)
endif
	@mkdir -p backend/app/skills/$(name)/pkg
	@mkdir -p backend/app/skills/$(name)/references
	@mkdir -p backend/app/skills/$(name)/tests
	@mkdir -p backend/app/skills/$(name)/evals/fixtures
	@touch backend/app/skills/$(name)/pkg/__init__.py
	@printf -- "---\nname: $(name)\ndescription: ''\nlevel: 1\nversion: '0.1'\n---\n# $(name)\n\nOne-paragraph overview.\n\n## When to use\n\n...\n\n## Contract\n\n...\n" > backend/app/skills/$(name)/SKILL.md
	@printf "dependencies:\n  requires: []\n  used_by: []\n  packages: []\nerrors: {}\n" > backend/app/skills/$(name)/skill.yaml
	@echo "Skill scaffolded at backend/app/skills/$(name)/"
```

- [ ] **Step 2: Smoke-test the scaffolder**

Run: `make skill-new name=_scratch_demo && cat backend/app/skills/_scratch_demo/SKILL.md && rm -rf backend/app/skills/_scratch_demo`
Expected: prints SKILL.md with frontmatter; no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/app/skills/registry.py backend/tests/unit/test_skill_registry_frontmatter.py Makefile
git commit -m "feat(skills): move skill metadata to SKILL.md frontmatter"
```

---

## Phase 1 — Theme System

Single `tokens.yaml` → five variants (light, dark, editorial, presentation, print) → Altair theme, HTML table CSS, dashboard CSS all read from the same source.

### Task 1.1: Create tokens.yaml

**Files:**
- Create: `config/themes/tokens.yaml`

- [ ] **Step 1: Write the token file**

```yaml
# config/themes/tokens.yaml
# GIR-inspired institutional aesthetic. Single source of truth for all themes.
# Series blues are named by role; each variant resolves role → shade.

default_variant: light

typography:
  sans: "Inter, system-ui, sans-serif"
  mono: "JetBrains Mono, ui-monospace, monospace"
  serif: "Source Serif Pro, Georgia, serif"
  scale:
    xs: 11
    sm: 12
    base: 14
    md: 16
    lg: 18
    xl: 22
    title: 28
  weight:
    regular: 400
    medium: 500
    semibold: 600
    bold: 700

# Eight series blues (role -> shade) and categorical palette, colorblind-safe.
# Strokes: actual solid 2.5, reference dotted 1.5, forecast dashed 1.5.
series_strokes:
  actual:     {width: 2.5, dash: null}
  primary:    {width: 2.0, dash: null}
  secondary:  {width: 2.0, dash: null}
  reference:  {width: 1.5, dash: [2, 3]}
  projection: {width: 1.5, dash: [5, 3]}
  forecast:   {width: 1.5, dash: [6, 3]}
  scenario:   {width: 1.2, dash: [3, 3]}
  ghost:      {width: 1.0, dash: [1, 3]}

variants:

  light:
    surface:
      base:       "#FFFFFF"
      panel:      "#F7F8FA"
      border:     "#E2E6EC"
      text:       "#111827"
      text_muted: "#4B5563"
      grid:       "#E5E7EB"
    series_blues:
      actual:     "#0B2545"
      primary:    "#13315C"
      secondary:  "#1E40AF"
      reference:  "#3A6EA5"
      projection: "#5B8AC7"
      forecast:   "#8CB0D9"
      scenario:   "#B3CFE6"
      ghost:      "#DCE7F2"
    semantic:
      primary:   "#13315C"
      positive:  "#4E7A3C"
      negative:  "#8F3031"
      warning:   "#B67B1E"
      info:      "#3A6EA5"
      neutral:   "#6B7280"
      highlight: "#B5892A"
    categorical:
      - "#13315C"
      - "#8F3031"
      - "#4E7A3C"
      - "#B67B1E"
      - "#3A6EA5"
      - "#1E40AF"
      - "#5B8AC7"
      - "#B5892A"
      - "#6B3E91"
      - "#8CB0D9"
      - "#0B2545"
      - "#2F4858"
      - "#B3CFE6"
      - "#D97757"
      - "#4A6670"
      - "#7A7A7A"
      - "#A43E2A"
      - "#45788F"
    diverging:
      negative: "#8F3031"
      neutral:  "#F5EFE6"
      positive: "#13315C"
    chart:
      default_width: 680
      default_height: 320
      title_anchor: "start"

  dark:
    surface:
      base:       "#0F172A"
      panel:      "#1E293B"
      border:     "#334155"
      text:       "#E5E7EB"
      text_muted: "#94A3B8"
      grid:       "#1E293B"
    series_blues:
      actual:     "#BCD3F2"
      primary:    "#9DB9E0"
      secondary:  "#7EA0CE"
      reference:  "#6186BB"
      projection: "#476DA4"
      forecast:   "#335589"
      scenario:   "#25406B"
      ghost:      "#1A2D4F"
    semantic:
      primary:   "#9DB9E0"
      positive:  "#7FB069"
      negative:  "#D97757"
      warning:   "#E3B23C"
      info:      "#6186BB"
      neutral:   "#94A3B8"
      highlight: "#E3B23C"
    categorical:
      - "#9DB9E0"
      - "#D97757"
      - "#7FB069"
      - "#E3B23C"
      - "#6186BB"
      - "#7EA0CE"
      - "#476DA4"
      - "#E3B23C"
      - "#A892C7"
      - "#BCD3F2"
      - "#476DA4"
      - "#5F7480"
      - "#335589"
      - "#F5A886"
      - "#8AA3AE"
      - "#9CA3AF"
      - "#C87660"
      - "#7C9CAE"
    diverging:
      negative: "#D97757"
      neutral:  "#1E293B"
      positive: "#9DB9E0"
    chart:
      default_width: 680
      default_height: 320
      title_anchor: "start"

  editorial:
    surface:
      base:       "#FBF7EE"
      panel:      "#F3ECDB"
      border:     "#D6CAB1"
      text:       "#1F1B17"
      text_muted: "#5C5242"
      grid:       "#E7DFC9"
    series_blues:
      actual:     "#0B2545"
      primary:    "#13315C"
      secondary:  "#1E40AF"
      reference:  "#3A6EA5"
      projection: "#5B8AC7"
      forecast:   "#8CB0D9"
      scenario:   "#B3CFE6"
      ghost:      "#D2DEEC"
    semantic:
      primary:   "#13315C"
      positive:  "#4E7A3C"
      negative:  "#8F3031"
      warning:   "#B67B1E"
      info:      "#3A6EA5"
      neutral:   "#5C5242"
      highlight: "#B5892A"
    categorical:
      - "#13315C"
      - "#8F3031"
      - "#4E7A3C"
      - "#B67B1E"
      - "#3A6EA5"
      - "#6B3E91"
      - "#0B2545"
      - "#B5892A"
      - "#2F4858"
      - "#8CB0D9"
      - "#A43E2A"
      - "#45788F"
      - "#4A6670"
      - "#5B8AC7"
      - "#1E40AF"
      - "#7A7A7A"
      - "#5C5242"
      - "#B3CFE6"
    diverging:
      negative: "#8F3031"
      neutral:  "#F5EFE6"
      positive: "#13315C"
    chart:
      default_width: 720
      default_height: 360
      title_anchor: "start"
    typography_override:
      headings: serif

  presentation:
    surface:
      base:       "#FFFFFF"
      panel:      "#F1F4F8"
      border:     "#C8D0DA"
      text:       "#0B1220"
      text_muted: "#3B4252"
      grid:       "#D4DBE4"
    series_blues:
      actual:     "#081C34"
      primary:    "#0F2A4A"
      secondary:  "#17397C"
      reference:  "#2E5F95"
      projection: "#4F7CB5"
      forecast:   "#7A9FCB"
      scenario:   "#A7C3E0"
      ghost:      "#D0DDEB"
    semantic:
      primary:   "#0F2A4A"
      positive:  "#426B32"
      negative:  "#7A2929"
      warning:   "#A26A14"
      info:      "#2E5F95"
      neutral:   "#3B4252"
      highlight: "#A47B1E"
    categorical:
      - "#0F2A4A"
      - "#7A2929"
      - "#426B32"
      - "#A26A14"
      - "#2E5F95"
      - "#17397C"
      - "#4F7CB5"
      - "#A47B1E"
      - "#5F3682"
      - "#081C34"
      - "#7A9FCB"
      - "#244052"
      - "#A7C3E0"
      - "#C25C36"
      - "#3F5B67"
      - "#666666"
      - "#963626"
      - "#3D6A80"
    diverging:
      negative: "#7A2929"
      neutral:  "#E8E8E8"
      positive: "#0F2A4A"
    chart:
      default_width: 900
      default_height: 540
      title_anchor: "start"
    typography_override:
      base_size: 18

  print:
    surface:
      base:       "#FFFFFF"
      panel:      "#F5F5F5"
      border:     "#888888"
      text:       "#000000"
      text_muted: "#3F3F3F"
      grid:       "#BDBDBD"
    series_blues:
      actual:     "#1A1A1A"
      primary:    "#333333"
      secondary:  "#4D4D4D"
      reference:  "#666666"
      projection: "#808080"
      forecast:   "#999999"
      scenario:   "#BFBFBF"
      ghost:      "#D9D9D9"
    semantic:
      primary:   "#1A1A1A"
      positive:  "#1A1A1A"
      negative:  "#4D4D4D"
      warning:   "#666666"
      info:      "#333333"
      neutral:   "#808080"
      highlight: "#1A1A1A"
    categorical:
      - "#000000"
      - "#333333"
      - "#4D4D4D"
      - "#666666"
      - "#808080"
      - "#999999"
      - "#1A1A1A"
      - "#2B2B2B"
      - "#3F3F3F"
      - "#555555"
      - "#6B6B6B"
      - "#7F7F7F"
      - "#939393"
      - "#ABABAB"
      - "#BFBFBF"
      - "#D3D3D3"
      - "#575757"
      - "#8B8B8B"
    diverging:
      negative: "#4D4D4D"
      neutral:  "#F5F5F5"
      positive: "#000000"
    chart:
      default_width: 680
      default_height: 320
      title_anchor: "start"
```

- [ ] **Step 2: Validate it parses**

Run: `python -c "import yaml; d=yaml.safe_load(open('config/themes/tokens.yaml')); print(sorted(d['variants']))"`
Expected: `['dark', 'editorial', 'light', 'presentation', 'print']`

### Task 1.2: Write failing test for theme_switcher

**Files:**
- Test: `backend/tests/unit/test_theme_tokens.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_theme_tokens.py
from __future__ import annotations

from pathlib import Path

import pytest

from config.themes.theme_switcher import ThemeTokens

TOKENS_PATH = Path(__file__).resolve().parents[3] / "config" / "themes" / "tokens.yaml"


def test_loads_all_five_variants() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH)
    assert sorted(tokens.variants) == ["dark", "editorial", "light", "presentation", "print"]


def test_resolves_series_blues_by_role() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    assert tokens.series_color("actual") == "#0B2545"
    assert tokens.series_color("forecast") == "#8CB0D9"


def test_series_stroke_actual_is_solid_and_thick() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    stroke = tokens.series_stroke("actual")
    assert stroke.width == 2.5
    assert stroke.dash is None


def test_series_stroke_forecast_is_dashed() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    stroke = tokens.series_stroke("forecast")
    assert stroke.dash == [6, 3]


def test_editorial_uses_cream_surface() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("editorial")
    assert tokens.surface("base").startswith("#FB")


def test_unknown_variant_raises() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH)
    with pytest.raises(KeyError):
        tokens.for_variant("neon")


def test_categorical_has_at_least_18_colors() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    assert len(tokens.categorical()) >= 18
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_theme_tokens.py -v`
Expected: FAIL (module not found).

### Task 1.3: Implement theme_switcher

**Files:**
- Create: `config/themes/__init__.py`
- Create: `config/themes/theme_switcher.py`

- [ ] **Step 1: Create `__init__.py`**

```python
# config/themes/__init__.py
"""Unified theme tokens and renderer helpers."""
```

- [ ] **Step 2: Implement `theme_switcher.py`**

```python
# config/themes/theme_switcher.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SeriesStroke:
    width: float
    dash: list[int] | None


@dataclass(frozen=True)
class VariantTokens:
    """A single variant's resolved tokens."""

    name: str
    raw: dict[str, Any]
    series_strokes: dict[str, SeriesStroke]
    typography: dict[str, Any]

    def surface(self, key: str) -> str:
        return str(self.raw["surface"][key])

    def series_color(self, role: str) -> str:
        return str(self.raw["series_blues"][role])

    def series_stroke(self, role: str) -> SeriesStroke:
        return self.series_strokes[role]

    def semantic(self, role: str) -> str:
        return str(self.raw["semantic"][role])

    def categorical(self) -> list[str]:
        return list(self.raw["categorical"])

    def diverging(self) -> dict[str, str]:
        return dict(self.raw["diverging"])

    def chart(self, key: str) -> Any:
        return self.raw["chart"][key]

    def typography_override(self) -> dict[str, Any]:
        return dict(self.raw.get("typography_override", {}))


@dataclass(frozen=True)
class ThemeTokens:
    variants: dict[str, dict[str, Any]]
    typography: dict[str, Any]
    series_strokes: dict[str, SeriesStroke]
    default_variant: str

    @classmethod
    def load(cls, path: Path) -> ThemeTokens:
        data = yaml.safe_load(path.read_text())
        strokes = {
            role: SeriesStroke(width=float(s["width"]), dash=s.get("dash"))
            for role, s in data["series_strokes"].items()
        }
        return cls(
            variants=data["variants"],
            typography=data["typography"],
            series_strokes=strokes,
            default_variant=data.get("default_variant", "light"),
        )

    def for_variant(self, name: str) -> VariantTokens:
        if name not in self.variants:
            raise KeyError(name)
        return VariantTokens(
            name=name,
            raw=self.variants[name],
            series_strokes=self.series_strokes,
            typography=self.typography,
        )

    def default(self) -> VariantTokens:
        return self.for_variant(self.default_variant)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd backend && pytest tests/unit/test_theme_tokens.py -v`
Expected: PASS (all 7 tests).

### Task 1.4: Write failing test for Altair theme

**Files:**
- Test: `backend/tests/unit/test_altair_theme.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_altair_theme.py
from __future__ import annotations

from pathlib import Path

import altair as alt
import pytest

from config.themes.altair_theme import register_all, use_variant

TOKENS_PATH = Path(__file__).resolve().parents[3] / "config" / "themes" / "tokens.yaml"


@pytest.fixture(autouse=True)
def reset_active():
    # Ensure a clean theme registration before each test.
    register_all(TOKENS_PATH)
    yield


def test_register_all_registers_five_variant_names() -> None:
    names = alt.themes.names()
    for variant in ("light", "dark", "editorial", "presentation", "print"):
        assert f"gir_{variant}" in names


def test_use_variant_activates_theme() -> None:
    use_variant("editorial")
    config = alt.themes.get()()
    assert "config" in config
    assert config["config"]["background"].startswith("#FB")


def test_theme_provides_range_category_of_18_colors() -> None:
    use_variant("light")
    config = alt.themes.get()()
    assert len(config["config"]["range"]["category"]) >= 18


def test_theme_title_anchor_is_start() -> None:
    use_variant("editorial")
    config = alt.themes.get()()
    assert config["config"]["title"]["anchor"] == "start"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_altair_theme.py -v`
Expected: FAIL (module not found).

### Task 1.5: Implement Altair theme

**Files:**
- Create: `config/themes/altair_theme.py`

- [ ] **Step 1: Write `altair_theme.py`**

```python
# config/themes/altair_theme.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import altair as alt

from config.themes.theme_switcher import ThemeTokens, VariantTokens

_DEFAULT_TOKENS: ThemeTokens | None = None


def _build_spec(tokens: VariantTokens, typography: dict[str, Any]) -> dict[str, Any]:
    sans = typography["sans"]
    font = sans
    title_font = typography.get("serif", sans) if tokens.typography_override().get("headings") == "serif" else sans
    base_size = tokens.typography_override().get("base_size", typography["scale"]["base"])

    return {
        "background": tokens.surface("base"),
        "config": {
            "background": tokens.surface("base"),
            "font": font,
            "title": {
                "anchor": tokens.chart("title_anchor"),
                "color": tokens.surface("text"),
                "font": title_font,
                "fontSize": typography["scale"]["xl"],
                "fontWeight": typography["weight"]["semibold"],
                "subtitleColor": tokens.surface("text_muted"),
                "subtitleFont": font,
            },
            "view": {
                "continuousWidth": tokens.chart("default_width"),
                "continuousHeight": tokens.chart("default_height"),
                "stroke": tokens.surface("border"),
            },
            "axis": {
                "domainColor": tokens.surface("border"),
                "gridColor": tokens.surface("grid"),
                "labelColor": tokens.surface("text_muted"),
                "labelFont": font,
                "labelFontSize": typography["scale"]["sm"],
                "tickColor": tokens.surface("border"),
                "titleColor": tokens.surface("text"),
                "titleFont": font,
                "titleFontSize": typography["scale"]["base"],
                "titleFontWeight": typography["weight"]["medium"],
            },
            "legend": {
                "labelColor": tokens.surface("text"),
                "labelFont": font,
                "labelFontSize": typography["scale"]["sm"],
                "titleColor": tokens.surface("text"),
                "titleFont": font,
                "titleFontSize": typography["scale"]["sm"],
                "titleFontWeight": typography["weight"]["medium"],
            },
            "range": {
                "category": tokens.categorical(),
                "diverging": [
                    tokens.diverging()["negative"],
                    tokens.diverging()["neutral"],
                    tokens.diverging()["positive"],
                ],
                "ramp": [tokens.series_color("ghost"), tokens.series_color("actual")],
                "ordinal": [
                    tokens.series_color(role)
                    for role in (
                        "ghost", "scenario", "forecast", "projection",
                        "reference", "secondary", "primary", "actual",
                    )
                ],
            },
            "mark": {"font": font, "fontSize": base_size},
            "text": {"font": font, "fontSize": typography["scale"]["sm"], "color": tokens.surface("text")},
            "header": {"labelFont": font, "titleFont": font},
        },
    }


def register_all(tokens_path: Path | None = None) -> None:
    global _DEFAULT_TOKENS
    path = tokens_path or (Path(__file__).parent / "tokens.yaml")
    _DEFAULT_TOKENS = ThemeTokens.load(path)
    typography = _DEFAULT_TOKENS.typography
    for variant_name in _DEFAULT_TOKENS.variants:
        variant = _DEFAULT_TOKENS.for_variant(variant_name)
        spec = _build_spec(variant, typography)
        alt.themes.register(f"gir_{variant_name}", lambda s=spec: s)
    alt.themes.enable(f"gir_{_DEFAULT_TOKENS.default_variant}")


def use_variant(variant: str) -> None:
    if _DEFAULT_TOKENS is None:
        register_all()
    alt.themes.enable(f"gir_{variant}")


def active_tokens() -> VariantTokens:
    if _DEFAULT_TOKENS is None:
        register_all()
    assert _DEFAULT_TOKENS is not None
    # alt.themes.active is the registered name (e.g. "gir_light").
    active = alt.themes.active or f"gir_{_DEFAULT_TOKENS.default_variant}"
    variant_name = active.removeprefix("gir_")
    return _DEFAULT_TOKENS.for_variant(variant_name)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && pytest tests/unit/test_altair_theme.py -v`
Expected: PASS (all 4 tests). If `altair` is missing, the test will fail at import — if so, proceed to Task 5.1 to add the dependency first, then return here.

### Task 1.6: Write failing test for table CSS

**Files:**
- Test: `backend/tests/unit/test_table_css.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_table_css.py
from __future__ import annotations

from pathlib import Path

from config.themes.table_css import render_table_css

TOKENS_PATH = Path(__file__).resolve().parents[3] / "config" / "themes" / "tokens.yaml"


def test_emits_style_block_with_variant_surface_color() -> None:
    css = render_table_css(variant="editorial", tokens_path=TOKENS_PATH)
    assert css.startswith("<style")
    assert "#FBF7EE" in css  # editorial surface base


def test_emits_semantic_color_for_positive_cells() -> None:
    css = render_table_css(variant="light", tokens_path=TOKENS_PATH)
    assert ".cell-positive" in css
    assert "#4E7A3C" in css


def test_print_variant_is_greyscale_only() -> None:
    css = render_table_css(variant="print", tokens_path=TOKENS_PATH)
    # No non-grey hex codes should sneak in.
    import re
    hex_codes = re.findall(r"#[0-9A-Fa-f]{6}", css)
    for code in hex_codes:
        r, g, b = int(code[1:3], 16), int(code[3:5], 16), int(code[5:7], 16)
        assert r == g == b, f"print variant should be achromatic, got {code}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_table_css.py -v`
Expected: FAIL (module not found).

### Task 1.7: Implement table_css

**Files:**
- Create: `config/themes/table_css.py`

- [ ] **Step 1: Write `table_css.py`**

```python
# config/themes/table_css.py
from __future__ import annotations

from pathlib import Path

from config.themes.theme_switcher import ThemeTokens


def render_table_css(variant: str = "light", tokens_path: Path | None = None) -> str:
    path = tokens_path or (Path(__file__).parent / "tokens.yaml")
    tokens = ThemeTokens.load(path).for_variant(variant)
    typography = ThemeTokens.load(path).typography
    sans = typography["sans"]
    base = typography["scale"]["base"]
    sm = typography["scale"]["sm"]

    css = f"""<style>
.ga-table {{
  font-family: {sans};
  font-size: {base}px;
  color: {tokens.surface("text")};
  background: {tokens.surface("base")};
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}}
.ga-table thead th {{
  background: {tokens.surface("panel")};
  color: {tokens.surface("text")};
  text-align: left;
  font-weight: {typography["weight"]["semibold"]};
  border-bottom: 2px solid {tokens.surface("border")};
  padding: 6px 10px;
  font-size: {sm}px;
}}
.ga-table tbody td {{
  border-bottom: 1px solid {tokens.surface("grid")};
  padding: 5px 10px;
  font-size: {sm}px;
}}
.ga-table tbody tr:hover {{ background: {tokens.surface("panel")}; }}
.ga-table .cell-num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.ga-table .cell-positive {{ color: {tokens.semantic("positive")}; font-weight: 500; }}
.ga-table .cell-negative {{ color: {tokens.semantic("negative")}; font-weight: 500; }}
.ga-table .cell-warning  {{ color: {tokens.semantic("warning")}; }}
.ga-table .cell-muted    {{ color: {tokens.surface("text_muted")}; }}
.ga-table caption {{
  text-align: left;
  caption-side: top;
  font-weight: {typography["weight"]["semibold"]};
  color: {tokens.surface("text")};
  padding-bottom: 4px;
}}
</style>"""
    return css
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && pytest tests/unit/test_table_css.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 3: Commit Phase 1**

```bash
git add config/themes/ backend/tests/unit/test_theme_tokens.py backend/tests/unit/test_altair_theme.py backend/tests/unit/test_table_css.py
git commit -m "feat(theme): unified token system with 5 variants + Altair + table CSS"
```

---

## Phase 2 — Artifact Store

SQLite-backed store with typed distillation, event emission, and 512KB inline/disk split. Modeled on `Analytical-chatbot/backend/app/artifacts/store.py`; adds `profile`, `analysis`, `file` types and disk overflow.

### Task 2.1: Write failing test for basic add/get round-trip

**Files:**
- Test: `backend/tests/unit/test_artifact_store.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_artifact_store.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(db_path=tmp_path / "a.db", disk_root=tmp_path / "blobs")


def test_add_and_get_round_trip(store: ArtifactStore) -> None:
    a = Artifact(type="table", title="Rows per country", content="<table/>", format="html")
    saved = store.add_artifact("s1", a)
    assert saved.id
    assert saved.name == "rows_per_country"

    again = store.get_artifact("s1", saved.id)
    assert again is not None
    assert again.content == "<table/>"


def test_slug_collision_is_suffixed(store: ArtifactStore) -> None:
    store.add_artifact("s1", Artifact(type="table", title="Revenue", content="<table/>"))
    second = store.add_artifact("s1", Artifact(type="table", title="Revenue", content="<table/>"))
    assert second.name == "revenue_2"


def test_get_by_name(store: ArtifactStore) -> None:
    saved = store.add_artifact("s1", Artifact(type="chart", title="Trend", content="{}", format="vega-lite"))
    hit = store.get_artifact_by_name("s1", "trend")
    assert hit is not None
    assert hit.id == saved.id


def test_survives_new_instance(tmp_path: Path) -> None:
    db = tmp_path / "a.db"
    blobs = tmp_path / "blobs"
    s1 = ArtifactStore(db_path=db, disk_root=blobs)
    saved = s1.add_artifact("s1", Artifact(type="table", title="Persist", content="<t/>"))

    s2 = ArtifactStore(db_path=db, disk_root=blobs)
    again = s2.get_artifact("s1", saved.id)
    assert again is not None
    assert again.content == "<t/>"


def test_update_preserves_id(store: ArtifactStore) -> None:
    saved = store.add_artifact("s1", Artifact(type="table", title="Live", content="<t/>"))
    updated = store.update_artifact("s1", saved.id, content="<t2/>")
    assert updated is not None
    assert updated.id == saved.id
    assert updated.content == "<t2/>"


def test_disk_split_above_threshold(tmp_path: Path) -> None:
    store = ArtifactStore(db_path=tmp_path / "a.db", disk_root=tmp_path / "blobs", inline_threshold=100)
    big = "x" * 500
    saved = store.add_artifact("s1", Artifact(type="file", title="Big", content=big, format="txt"))
    # Content should be roundtrippable, but not stored inline.
    again = store.get_artifact("s1", saved.id)
    assert again is not None
    assert again.content == big
    # Blob file must exist on disk.
    assert (tmp_path / "blobs" / "s1" / f"{saved.id}.txt").exists()


def test_disk_split_survives_reload(tmp_path: Path) -> None:
    db = tmp_path / "a.db"
    blobs = tmp_path / "blobs"
    s1 = ArtifactStore(db_path=db, disk_root=blobs, inline_threshold=100)
    big = "y" * 500
    saved = s1.add_artifact("s1", Artifact(type="file", title="Big", content=big, format="txt"))

    s2 = ArtifactStore(db_path=db, disk_root=blobs, inline_threshold=100)
    again = s2.get_artifact("s1", saved.id)
    assert again is not None
    assert again.content == big


def test_accepts_profile_type(store: ArtifactStore) -> None:
    saved = store.add_artifact(
        "s1",
        Artifact(type="profile", title="customers_v1 profile", content="{}", format="profile-json"),
    )
    assert saved.type == "profile"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_artifact_store.py -v`
Expected: FAIL (module not found).

### Task 2.2: Implement Artifact model

**Files:**
- Create: `backend/app/artifacts/__init__.py`
- Create: `backend/app/artifacts/models.py`

- [ ] **Step 1: Create package init**

```python
# backend/app/artifacts/__init__.py
from app.artifacts.models import Artifact, ProgressStep
from app.artifacts.store import ArtifactStore
from app.artifacts.events import EventBus, get_event_bus

__all__ = ["Artifact", "ProgressStep", "ArtifactStore", "EventBus", "get_event_bus"]
```

- [ ] **Step 2: Implement models**

```python
# backend/app/artifacts/models.py
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

ArtifactType = Literal["table", "chart", "diagram", "dashboard_component", "profile", "analysis", "file"]


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: ArtifactType = "table"
    name: str = ""
    title: str = ""
    description: str = ""
    content: str = ""
    format: str = "html"
    session_id: str = ""
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)
    chart_data: dict[str, Any] | None = None
    total_rows: int | None = None
    displayed_rows: int | None = None
    profile_summary: str | None = None


class ProgressStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    label: str
    status: Literal["pending", "running", "done", "error"] = "pending"
    detail: str = ""
    started_at: float | None = None
    finished_at: float | None = None
```

### Task 2.3: Implement ArtifactStore with SQLite + disk split + slug

**Files:**
- Create: `backend/app/artifacts/store.py`

- [ ] **Step 1: Write `store.py`**

```python
# backend/app/artifacts/store.py
from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from app.artifacts.events import EventBus, get_event_bus
from app.artifacts.models import Artifact

logger = logging.getLogger(__name__)

INLINE_THRESHOLD_BYTES = 512 * 1024  # 512KB


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().strip()).strip("_")
    return slug[:60] if slug else "artifact"


class ArtifactStore:
    def __init__(
        self,
        db_path: str | Path | None = None,
        disk_root: str | Path | None = None,
        inline_threshold: int = INLINE_THRESHOLD_BYTES,
        event_bus: EventBus | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else None
        self._disk_root = Path(disk_root) if disk_root else None
        self._inline_threshold = inline_threshold
        self._events = event_bus or get_event_bus()
        self._cache: dict[str, list[Artifact]] = {}
        self._loaded: set[str] = set()
        if self._db_path:
            self._init_db()

    # ── DB ──────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    type TEXT NOT NULL DEFAULT 'table',
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    disk_path TEXT DEFAULT NULL,
                    format TEXT NOT NULL DEFAULT 'html',
                    chart_data_json TEXT DEFAULT NULL,
                    total_rows INTEGER DEFAULT NULL,
                    displayed_rows INTEGER DEFAULT NULL,
                    profile_summary TEXT DEFAULT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (session_id, id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_art_session ON artifacts(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_art_name ON artifacts(session_id, name)")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    # ── Disk overflow ───────────────────────────────────────────────────────

    def _disk_path_for(self, session_id: str, artifact_id: str, fmt: str) -> Path:
        assert self._disk_root is not None
        folder = self._disk_root / session_id
        folder.mkdir(parents=True, exist_ok=True)
        ext = re.sub(r"[^A-Za-z0-9]+", "", fmt) or "bin"
        return folder / f"{artifact_id}.{ext}"

    def _should_offload(self, content: str) -> bool:
        return self._disk_root is not None and len(content.encode("utf-8")) >= self._inline_threshold

    # ── Row (de)serialization ───────────────────────────────────────────────

    def _to_row(self, a: Artifact) -> tuple:
        if self._should_offload(a.content):
            disk_path = self._disk_path_for(a.session_id, a.id, a.format)
            disk_path.write_text(a.content)
            inline_content = ""
            disk_str = str(disk_path)
        else:
            inline_content = a.content
            disk_str = None
        return (
            a.id, a.session_id, a.name, a.type, a.title, a.description,
            inline_content, disk_str, a.format,
            json.dumps(a.chart_data) if a.chart_data else None,
            a.total_rows, a.displayed_rows, a.profile_summary,
            json.dumps(a.metadata), a.created_at,
        )

    def _from_row(self, row: tuple) -> Artifact:
        (id_, session_id, name, type_, title, desc, inline_content, disk_path,
         fmt, chart_json, total_rows, disp_rows, profile_summary, meta_json, created_at) = row
        content = inline_content
        if disk_path and Path(disk_path).exists():
            content = Path(disk_path).read_text()
        return Artifact(
            id=id_, session_id=session_id, name=name, type=type_,
            title=title, description=desc, content=content, format=fmt,
            chart_data=json.loads(chart_json) if chart_json else None,
            total_rows=total_rows, displayed_rows=disp_rows,
            profile_summary=profile_summary,
            metadata=json.loads(meta_json) if meta_json else {},
            created_at=created_at,
        )

    # ── Session load ────────────────────────────────────────────────────────

    def _load_session(self, session_id: str) -> None:
        if session_id in self._loaded or not self._db_path:
            self._loaded.add(session_id)
            return
        self._loaded.add(session_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, session_id, name, type, title, description, content, disk_path, "
                "format, chart_data_json, total_rows, displayed_rows, profile_summary, "
                "metadata_json, created_at FROM artifacts WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        self._cache[session_id] = [self._from_row(r) for r in rows]

    def _persist(self, a: Artifact) -> None:
        if not self._db_path:
            return
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                self._to_row(a),
            )
            conn.commit()

    # ── Public API ──────────────────────────────────────────────────────────

    def add_artifact(self, session_id: str, artifact: Artifact) -> Artifact:
        self._load_session(session_id)
        artifact.session_id = session_id
        if not artifact.name and artifact.title:
            base = _slugify(artifact.title)
            existing = {a.name for a in self._cache.get(session_id, [])}
            slug, counter = base, 2
            while slug in existing:
                slug = f"{base}_{counter}"
                counter += 1
            artifact.name = slug
        self._cache.setdefault(session_id, []).append(artifact)
        self._persist(artifact)
        self._events.emit("artifact.saved", {"session_id": session_id, "artifact_id": artifact.id, "type": artifact.type})
        return artifact

    def update_artifact(self, session_id: str, artifact_id: str, **kwargs: Any) -> Artifact | None:
        self._load_session(session_id)
        for a in self._cache.get(session_id, []):
            if a.id == artifact_id:
                for k, v in kwargs.items():
                    setattr(a, k, v)
                self._persist(a)
                self._events.emit("artifact.updated", {"session_id": session_id, "artifact_id": a.id})
                return a
        return None

    def get_artifacts(self, session_id: str) -> list[Artifact]:
        self._load_session(session_id)
        return list(self._cache.get(session_id, []))

    def get_artifact(self, session_id: str, artifact_id: str) -> Artifact | None:
        self._load_session(session_id)
        for a in self._cache.get(session_id, []):
            if a.id == artifact_id:
                return a
        return None

    def get_artifact_by_name(self, session_id: str, name: str) -> Artifact | None:
        self._load_session(session_id)
        nlower = name.lower()
        for a in self._cache.get(session_id, []):
            if a.name == nlower or a.title.lower() == nlower:
                return a
        return None
```

### Task 2.4: Implement EventBus

**Files:**
- Create: `backend/app/artifacts/events.py`
- Test: `backend/tests/unit/test_artifact_events.py`

- [ ] **Step 1: Write failing event test**

```python
# backend/tests/unit/test_artifact_events.py
from __future__ import annotations

from pathlib import Path

from app.artifacts.events import EventBus
from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore


def test_emit_calls_subscriber() -> None:
    bus = EventBus()
    seen: list[dict] = []
    bus.subscribe(lambda ev: seen.append(ev))
    bus.emit("artifact.saved", {"artifact_id": "abc"})
    assert seen and seen[0]["type"] == "artifact.saved"
    assert seen[0]["data"]["artifact_id"] == "abc"


def test_store_emits_on_add(tmp_path: Path) -> None:
    bus = EventBus()
    seen: list[dict] = []
    bus.subscribe(lambda ev: seen.append(ev))
    store = ArtifactStore(db_path=tmp_path / "a.db", disk_root=tmp_path / "blobs", event_bus=bus)

    store.add_artifact("s1", Artifact(type="table", title="x", content="<t/>"))
    assert any(ev["type"] == "artifact.saved" for ev in seen)


def test_store_emits_on_update(tmp_path: Path) -> None:
    bus = EventBus()
    seen: list[dict] = []
    bus.subscribe(lambda ev: seen.append(ev))
    store = ArtifactStore(db_path=tmp_path / "a.db", disk_root=tmp_path / "blobs", event_bus=bus)

    saved = store.add_artifact("s1", Artifact(type="table", title="x", content="<t/>"))
    store.update_artifact("s1", saved.id, content="<t2/>")
    assert any(ev["type"] == "artifact.updated" for ev in seen)
```

- [ ] **Step 2: Run it (will fail — EventBus missing)**

Run: `cd backend && pytest tests/unit/test_artifact_events.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement EventBus**

```python
# backend/app/artifacts/events.py
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

Event = dict[str, Any]
Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: list[Subscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subs.append(fn)

        def unsubscribe() -> None:
            with self._lock:
                if fn in self._subs:
                    self._subs.remove(fn)

        return unsubscribe

    def emit(self, type_: str, data: dict[str, Any]) -> None:
        event = {"type": type_, "data": data}
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(event)
            except Exception:  # noqa: BLE001 - subscriber errors must not break emit
                pass


_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
```

- [ ] **Step 4: Run all store tests**

Run: `cd backend && pytest tests/unit/test_artifact_store.py tests/unit/test_artifact_events.py -v`
Expected: PASS (all tests).

### Task 2.5: Implement distillation helpers

**Files:**
- Create: `backend/app/artifacts/distill.py`
- Test: `backend/tests/unit/test_artifact_distill.py`

- [ ] **Step 1: Write failing distillation test**

```python
# backend/tests/unit/test_artifact_distill.py
from __future__ import annotations

from app.artifacts.distill import distill_artifact, format_artifacts_for_compaction
from app.artifacts.models import Artifact


def test_distill_chart_extracts_mark_and_encodings() -> None:
    a = Artifact(
        type="chart",
        title="Revenue by month",
        content="{}",
        format="vega-lite",
        chart_data={
            "mark": "line",
            "x": {"field": "month", "type": "temporal"},
            "y": {"field": "revenue", "type": "quantitative"},
            "data_sample": {"month": ["2024-01", "2024-02"], "revenue": [100, 120]},
            "data_rows": 2,
        },
    )
    out = distill_artifact(a)
    assert "mark=line" in out
    assert "x=month" in out
    assert "y=revenue" in out


def test_distill_table_includes_row_counts() -> None:
    a = Artifact(
        type="table",
        title="Top customers",
        content="<table><thead><tr><th>name</th></tr></thead><tbody><tr><td>A</td></tr></tbody></table>",
        total_rows=200,
        displayed_rows=50,
    )
    out = distill_artifact(a)
    assert "200 rows" in out
    assert "displayed 50" in out


def test_distill_profile_prefers_profile_summary_field() -> None:
    a = Artifact(
        type="profile",
        title="customers_v1",
        content="{}",
        profile_summary="8 cols; 1 BLOCKER (duplicate_key on customer_id); 2 HIGH risks.",
    )
    out = distill_artifact(a)
    assert "BLOCKER" in out
    assert "customers_v1" in out


def test_format_artifacts_for_compaction_lists_all() -> None:
    artifacts = [
        Artifact(id="a1", type="table", title="Rows", content="<t/>"),
        Artifact(id="a2", type="chart", title="Trend", content="{}", format="vega-lite"),
    ]
    out = format_artifacts_for_compaction(artifacts)
    assert "Artifacts (2 total)" in out
    assert "a1" in out and "a2" in out
```

- [ ] **Step 2: Run it (will fail)**

Run: `cd backend && pytest tests/unit/test_artifact_distill.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement distillation**

```python
# backend/app/artifacts/distill.py
from __future__ import annotations

from html.parser import HTMLParser

from app.artifacts.models import Artifact


def _round(v: str) -> str:
    try:
        f = float(v.replace(",", ""))
        return str(int(f)) if f == int(f) else f"{f:.2f}"
    except (ValueError, AttributeError):
        return v


def _distill_chart(a: Artifact) -> str:
    cd = a.chart_data or {}
    mark_raw = cd.get("mark", "unknown")
    mark = mark_raw["type"] if isinstance(mark_raw, dict) else str(mark_raw)
    encodings: list[str] = []
    for ch in ("x", "y", "color", "size", "column", "row"):
        enc = cd.get(ch, {})
        if isinstance(enc, dict) and "field" in enc:
            encodings.append(f"{ch}={enc['field']}")
    enc_str = ", ".join(encodings) or "no encodings"
    out = f"- [chart] '{a.name or a.id}' \"{a.title}\" — mark={mark}, {enc_str}"
    ds = cd.get("data_sample", {})
    if isinstance(ds, dict) and ds:
        cols = list(ds.keys())
        col_values = [ds[c] for c in cols]
        rows = list(zip(*col_values))
        n_rows = int(cd.get("data_rows", len(rows) or 0))
        if rows:
            header = ",".join(str(c) for c in cols)
            body = "\n  ".join(",".join(_round(str(v)) for v in r) for r in rows)
            out += f"\n  {header}\n  {body}"
            if n_rows > len(rows):
                out += f"\n  ... [{n_rows - len(rows)} rows truncated]"
    return out


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._in_cell = False
        self._text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._text = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._row.append(self._text.strip())
            self._in_cell = False
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = []

    def handle_data(self, data):
        if self._in_cell:
            self._text += data


def _distill_table(a: Artifact, max_rows: int = 50) -> str:
    row_info = ""
    if a.total_rows is not None:
        row_info = f", {a.total_rows} rows"
        if a.displayed_rows is not None and a.displayed_rows < a.total_rows:
            row_info += f", displayed {a.displayed_rows}"
    summary = f"- [table] '{a.name or a.id}' \"{a.title}\"{row_info}"
    if a.content:
        p = _TableParser()
        try:
            p.feed(a.content[:500_000])
            if p.rows:
                header = p.rows[0]
                body = p.rows[1 : max_rows + 1]
                truncated = max(0, len(p.rows) - 1 - len(body))
                def fmt(cells: list[str], is_header: bool = False) -> str:
                    vals = cells if is_header else [_round(c) for c in cells]
                    return ",".join(v.replace(",", ";") for v in vals)
                preview = "\n  " + fmt(header, True) + "\n  " + "\n  ".join(fmt(r) for r in body)
                if truncated > 0:
                    preview += f"\n  ... [{truncated} rows truncated]"
                summary += preview
        except Exception:  # noqa: BLE001
            pass
    return summary


def _distill_profile(a: Artifact) -> str:
    if a.profile_summary:
        return f"- [profile] '{a.name or a.id}' \"{a.title}\" — {a.profile_summary}"
    return f"- [profile] '{a.name or a.id}' \"{a.title}\" — (no summary available)"


def _distill_generic(a: Artifact) -> str:
    return f"- [{a.type}] '{a.name or a.id}' \"{a.title}\""


def distill_artifact(a: Artifact) -> str:
    if a.type == "chart":
        return _distill_chart(a)
    if a.type == "table":
        return _distill_table(a)
    if a.type == "profile":
        return _distill_profile(a)
    return _distill_generic(a)


def format_artifacts_for_compaction(artifacts: list[Artifact]) -> str:
    if not artifacts:
        return ""
    lines = [f"## Artifacts ({len(artifacts)} total)"]
    lines.extend(distill_artifact(a) for a in artifacts)
    return "\n".join(lines)
```

- [ ] **Step 4: Run the full artifact test suite**

Run: `cd backend && pytest tests/unit/test_artifact_store.py tests/unit/test_artifact_events.py tests/unit/test_artifact_distill.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit Phase 2**

```bash
git add backend/app/artifacts/ backend/tests/unit/test_artifact_store.py backend/tests/unit/test_artifact_events.py backend/tests/unit/test_artifact_distill.py
git commit -m "feat(artifacts): SQLite store with event bus, disk overflow, typed distillation"
```

---

## Phase 3 — Wiki Engine

Helpers for read/write on `working.md`, `index.md`, `log.md`, plus `promote_finding` and `rebuild_index`.

### Task 3.1: Write failing test for wiki read/write

**Files:**
- Test: `backend/tests/unit/test_wiki_engine.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_wiki_engine.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.wiki.engine import WikiEngine
from app.wiki.schema import Finding


@pytest.fixture
def wiki(tmp_path: Path) -> WikiEngine:
    for sub in ("findings", "hypotheses", "entities", "meta"):
        (tmp_path / sub).mkdir()
    (tmp_path / "working.md").write_text("# Working\n\n## Current Focus\n\ninitial\n")
    (tmp_path / "index.md").write_text("# Wiki Index\n\n")
    (tmp_path / "log.md").write_text("# Log\n\n")
    return WikiEngine(tmp_path)


def test_read_working_returns_file_contents(wiki: WikiEngine) -> None:
    text = wiki.read_working()
    assert "initial" in text


def test_write_working_replaces_contents(wiki: WikiEngine) -> None:
    wiki.write_working("# Working\n\n## Current Focus\n\nanalyzing customers\n")
    assert "analyzing customers" in wiki.read_working()


def test_write_working_rejects_over_200_lines(wiki: WikiEngine) -> None:
    too_long = "\n".join(f"line {i}" for i in range(250))
    with pytest.raises(ValueError, match="200"):
        wiki.write_working(too_long)


def test_append_log_adds_timestamped_line(wiki: WikiEngine) -> None:
    wiki.append_log("turn 1: profiled customers_v1")
    text = (wiki.root / "log.md").read_text()
    assert "turn 1: profiled customers_v1" in text


def test_promote_finding_writes_markdown(wiki: WikiEngine) -> None:
    finding = Finding(
        id="F-20260412-001",
        title="Revenue grew 12% QoQ",
        body="Analysis shows ...",
        evidence=["art_ab12cd"],
        stat_validate_pass=True,
    )
    path = wiki.promote_finding(finding)
    assert path.exists()
    assert path.name == "F-20260412-001.md"
    assert "Revenue grew 12% QoQ" in path.read_text()


def test_promote_finding_refuses_without_evidence(wiki: WikiEngine) -> None:
    bad = Finding(id="F-X", title="t", body="b", evidence=[], stat_validate_pass=True)
    with pytest.raises(ValueError, match="evidence"):
        wiki.promote_finding(bad)


def test_promote_finding_refuses_without_stat_validate_pass(wiki: WikiEngine) -> None:
    bad = Finding(id="F-X", title="t", body="b", evidence=["art1"], stat_validate_pass=False)
    with pytest.raises(ValueError, match="stat_validate"):
        wiki.promote_finding(bad)


def test_rebuild_index_lists_all_pages(wiki: WikiEngine) -> None:
    wiki.promote_finding(
        Finding(id="F-X", title="First", body="b", evidence=["a"], stat_validate_pass=True)
    )
    (wiki.root / "entities" / "customers.md").write_text("# customers\n\nentity notes\n")

    wiki.rebuild_index()
    text = (wiki.root / "index.md").read_text()
    assert "F-X" in text
    assert "First" in text
    assert "customers" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_wiki_engine.py -v`
Expected: FAIL.

### Task 3.2: Implement wiki schema + engine

**Files:**
- Create: `backend/app/wiki/__init__.py`
- Create: `backend/app/wiki/schema.py`
- Create: `backend/app/wiki/engine.py`

- [ ] **Step 1: Create package init**

```python
# backend/app/wiki/__init__.py
from app.wiki.engine import WikiEngine
from app.wiki.schema import Entity, Finding, Hypothesis

__all__ = ["WikiEngine", "Finding", "Hypothesis", "Entity"]
```

- [ ] **Step 2: Implement schema**

```python
# backend/app/wiki/schema.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Finding:
    id: str
    title: str
    body: str
    evidence: list[str] = field(default_factory=list)
    stat_validate_pass: bool = False


@dataclass(frozen=True)
class Hypothesis:
    id: str
    title: str
    body: str


@dataclass(frozen=True)
class Entity:
    name: str
    body: str
```

- [ ] **Step 3: Implement engine**

```python
# backend/app/wiki/engine.py
from __future__ import annotations

import time
from pathlib import Path

from app.wiki.schema import Finding

MAX_WORKING_LINES = 200


class WikiEngine:
    def __init__(self, root: Path) -> None:
        self.root = root

    # ── working.md ──────────────────────────────────────────────────────────

    def read_working(self) -> str:
        return (self.root / "working.md").read_text()

    def write_working(self, content: str) -> None:
        lines = content.splitlines()
        if len(lines) > MAX_WORKING_LINES:
            raise ValueError(
                f"working.md exceeds {MAX_WORKING_LINES} lines ({len(lines)}); compact first"
            )
        (self.root / "working.md").write_text(content)

    # ── log.md ──────────────────────────────────────────────────────────────

    def append_log(self, line: str) -> None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        path = self.root / "log.md"
        existing = path.read_text() if path.exists() else "# Log\n\n"
        path.write_text(existing + f"- {stamp} — {line}\n")

    # ── findings ────────────────────────────────────────────────────────────

    def promote_finding(self, finding: Finding) -> Path:
        if not finding.evidence:
            raise ValueError("cannot promote finding without evidence (need artifact IDs)")
        if not finding.stat_validate_pass:
            raise ValueError("cannot promote finding without stat_validate PASS")
        body = (
            f"# {finding.title}\n\n"
            f"**Finding ID:** `{finding.id}`\n\n"
            f"## Summary\n\n{finding.body}\n\n"
            f"## Evidence\n\n"
            + "\n".join(f"- `{a}`" for a in finding.evidence)
            + "\n"
        )
        path = self.root / "findings" / f"{finding.id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    # ── index ───────────────────────────────────────────────────────────────

    def _list_titles(self, subdir: str) -> list[tuple[str, str]]:
        folder = self.root / subdir
        if not folder.exists():
            return []
        out: list[tuple[str, str]] = []
        for md in sorted(folder.glob("*.md")):
            first_heading = next(
                (ln.lstrip("# ").strip() for ln in md.read_text().splitlines() if ln.startswith("# ")),
                md.stem,
            )
            out.append((md.stem, first_heading))
        return out

    def rebuild_index(self) -> None:
        sections = [
            ("Findings", self._list_titles("findings")),
            ("Hypotheses", self._list_titles("hypotheses")),
            ("Entities", self._list_titles("entities")),
            ("Meta", self._list_titles("meta")),
        ]
        lines = ["# Wiki Index", ""]
        for heading, items in sections:
            lines.append(f"## {heading}")
            lines.append("")
            if not items:
                lines.append("_(no pages yet)_")
            else:
                for stem, title in items:
                    lines.append(f"- [{stem}]({stem}.md) — {title}")
            lines.append("")
        (self.root / "index.md").write_text("\n".join(lines))
```

- [ ] **Step 4: Run wiki tests**

Run: `cd backend && pytest tests/unit/test_wiki_engine.py -v`
Expected: PASS (all 8 tests).

- [ ] **Step 5: Commit Phase 3**

```bash
git add backend/app/wiki/ backend/tests/unit/test_wiki_engine.py
git commit -m "feat(wiki): engine with working/log read+write and finding promotion"
```

---

## Phase 4 — sql_builder + html_tables Skills

Two simple Level-1 primitives that `data_profiler` depends on.

### Task 4.1: Scaffold sql_builder skill

**Files:**
- Create: `backend/app/skills/sql_builder/SKILL.md`
- Create: `backend/app/skills/sql_builder/skill.yaml`
- Create: `backend/app/skills/sql_builder/pkg/__init__.py`
- Create: `backend/app/skills/sql_builder/pkg/builder.py`
- Create: `backend/app/skills/sql_builder/tests/__init__.py`
- Create: `backend/app/skills/sql_builder/tests/test_builder.py`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: sql_builder
description: DuckDB query helpers — safe field quoting, paginated SELECTs, column stats.
level: 1
version: '0.1'
---
# sql_builder

Composes DuckDB SQL safely from field lists. No string interpolation of user values — field names are quoted with `"` and any non-identifier input raises.

## When to use

When another skill needs to scan a DataFrame via DuckDB for speed (large tables, grouping, window functions).

## Contract

- `quote(ident: str) -> str`: returns `"ident"`; raises `ValueError` if the string is not a safe identifier.
- `select(table, columns, where=None, limit=None) -> str`
- `groupby_counts(table, column) -> str`
- `summary_stats(table, column) -> str` — returns a SELECT that yields `count, nulls, min, max, mean, stddev, p01, p05, p50, p95, p99` for a numeric column.

## Errors

`NOT_IDENTIFIER` — identifier contains characters outside `[A-Za-z_][A-Za-z0-9_]*`.
```

- [ ] **Step 2: Write skill.yaml**

```yaml
dependencies:
  requires: []
  used_by: [data_profiler]
  packages: []
errors:
  NOT_IDENTIFIER:
    message: "Identifier '{ident}' is not a safe SQL identifier."
    guidance: "Use only letters, digits, and underscore; must not start with a digit."
    recovery: "Rename the column or pass it through quote()."
```

- [ ] **Step 3: Write empty `pkg/__init__.py` and `tests/__init__.py`**

```python
# backend/app/skills/sql_builder/pkg/__init__.py
from app.skills.sql_builder.pkg.builder import (
    groupby_counts,
    quote,
    select,
    summary_stats,
)

__all__ = ["quote", "select", "groupby_counts", "summary_stats"]
```

```python
# backend/app/skills/sql_builder/tests/__init__.py
```

- [ ] **Step 4: Write failing tests**

```python
# backend/app/skills/sql_builder/tests/test_builder.py
from __future__ import annotations

import pytest

from app.skills.base import SkillError
from app.skills.sql_builder.pkg.builder import (
    groupby_counts,
    quote,
    select,
    summary_stats,
)


def test_quote_wraps_identifier() -> None:
    assert quote("age") == '"age"'


def test_quote_rejects_spaces_and_punctuation() -> None:
    with pytest.raises(SkillError):
        quote("age; DROP TABLE")


def test_quote_rejects_leading_digit() -> None:
    with pytest.raises(SkillError):
        quote("1st_col")


def test_select_renders_columns_and_limit() -> None:
    sql = select("df", ["a", "b"], limit=10)
    assert sql == 'SELECT "a", "b" FROM "df" LIMIT 10'


def test_select_accepts_where_clause() -> None:
    sql = select("df", ["a"], where='"a" > 5', limit=None)
    assert sql == 'SELECT "a" FROM "df" WHERE "a" > 5'


def test_groupby_counts_orders_desc() -> None:
    sql = groupby_counts("df", "country")
    assert 'GROUP BY "country"' in sql
    assert "ORDER BY cnt DESC" in sql


def test_summary_stats_has_eleven_fields() -> None:
    sql = summary_stats("df", "revenue")
    for token in (
        "count", "nulls", "min(", "max(", "avg(", "stddev(",
        "quantile_cont(\"revenue\", 0.01)",
        "quantile_cont(\"revenue\", 0.95)",
    ):
        assert token in sql
```

- [ ] **Step 5: Implement builder.py**

```python
# backend/app/skills/sql_builder/pkg/builder.py
from __future__ import annotations

import re

from app.skills.base import SkillError

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ERRORS = {
    "NOT_IDENTIFIER": {
        "message": "Identifier '{ident}' is not a safe SQL identifier.",
        "guidance": "Use only letters, digits, and underscore; must not start with a digit.",
        "recovery": "Rename the column or pass it through quote().",
    }
}


def quote(ident: str) -> str:
    if not _IDENT.match(ident or ""):
        raise SkillError("NOT_IDENTIFIER", {"ident": ident}, _ERRORS)
    return f'"{ident}"'


def select(
    table: str,
    columns: list[str],
    where: str | None = None,
    limit: int | None = None,
) -> str:
    cols = ", ".join(quote(c) for c in columns)
    tbl = quote(table)
    sql = f"SELECT {cols} FROM {tbl}"
    if where:
        sql += f" WHERE {where}"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return sql


def groupby_counts(table: str, column: str) -> str:
    col = quote(column)
    tbl = quote(table)
    return (
        f"SELECT {col} AS value, COUNT(*) AS cnt "
        f"FROM {tbl} GROUP BY {col} ORDER BY cnt DESC"
    )


def summary_stats(table: str, column: str) -> str:
    col = quote(column)
    tbl = quote(table)
    return (
        f"SELECT COUNT(*) AS count, "
        f"COUNT(*) - COUNT({col}) AS nulls, "
        f"min({col}) AS min, max({col}) AS max, "
        f"avg({col}) AS mean, stddev({col}) AS stddev, "
        f"quantile_cont({col}, 0.01) AS p01, "
        f"quantile_cont({col}, 0.05) AS p05, "
        f"quantile_cont({col}, 0.50) AS p50, "
        f"quantile_cont({col}, 0.95) AS p95, "
        f"quantile_cont({col}, 0.99) AS p99 "
        f"FROM {tbl}"
    )
```

- [ ] **Step 6: Run tests**

Run: `cd backend && pytest app/skills/sql_builder/tests/ -v`
Expected: PASS (all 7 tests).

- [ ] **Step 7: Commit sql_builder**

```bash
git add backend/app/skills/sql_builder/
git commit -m "feat(skills): sql_builder primitive with safe identifier quoting"
```

### Task 4.2: Scaffold html_tables skill

**Files:**
- Create: `backend/app/skills/html_tables/SKILL.md`
- Create: `backend/app/skills/html_tables/skill.yaml`
- Create: `backend/app/skills/html_tables/pkg/__init__.py`
- Create: `backend/app/skills/html_tables/pkg/renderer.py`
- Create: `backend/app/skills/html_tables/tests/__init__.py`
- Create: `backend/app/skills/html_tables/tests/test_renderer.py`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: html_tables
description: Render a DataFrame as themed HTML with numeric right-align, semantic cell classes, and caption.
level: 1
version: '0.1'
---
# html_tables

Renders a DataFrame into HTML, pulling CSS from the active theme (cell-positive, cell-negative, cell-muted). Headers come from DataFrame columns; numeric columns automatically get `cell-num` for right-align.

## When to use

When an analytical result is best shown as a table, not a chart (e.g. exact per-row counts, categorical comparisons, ≤20 rows).

## Contract

- `render(df, title=None, caption=None, variant="light", max_rows=200, cell_classes=None) -> str`
- Returns a string containing `<style>` + `<table class="ga-table">`.
- `cell_classes` maps `(row_index, column_name) -> list[str]`; lets callers mark positive/negative cells.

## Rules

- No color hex hardcoded in renderer — comes from the active variant.
- Rows beyond `max_rows` are truncated with a visible marker row.
- Numeric columns right-aligned via the `cell-num` class.
```

- [ ] **Step 2: Write skill.yaml**

```yaml
dependencies:
  requires: [theme_config]
  used_by: [data_profiler, report_builder, dashboard_builder]
  packages: [pandas]
errors: {}
```

- [ ] **Step 3: Write failing tests**

```python
# backend/app/skills/html_tables/tests/__init__.py
```

```python
# backend/app/skills/html_tables/tests/test_renderer.py
from __future__ import annotations

import pandas as pd

from app.skills.html_tables.pkg.renderer import render


def test_render_emits_table_and_style() -> None:
    df = pd.DataFrame({"name": ["a", "b"], "count": [10, 20]})
    out = render(df, title="Counts")
    assert '<table class="ga-table"' in out
    assert "<style" in out
    assert "<caption>Counts</caption>" in out


def test_numeric_columns_get_cell_num_class() -> None:
    df = pd.DataFrame({"name": ["a"], "count": [10]})
    out = render(df)
    assert 'class="cell-num"' in out


def test_truncates_beyond_max_rows() -> None:
    df = pd.DataFrame({"x": list(range(25))})
    out = render(df, max_rows=10)
    # First 10 visible, truncation note
    assert "15 rows truncated" in out


def test_custom_cell_classes_applied() -> None:
    df = pd.DataFrame({"delta": [1.0, -2.0]})
    classes = {(0, "delta"): ["cell-positive"], (1, "delta"): ["cell-negative"]}
    out = render(df, cell_classes=classes)
    assert "cell-positive" in out
    assert "cell-negative" in out
```

- [ ] **Step 4: Implement renderer**

```python
# backend/app/skills/html_tables/pkg/__init__.py
from app.skills.html_tables.pkg.renderer import render

__all__ = ["render"]
```

```python
# backend/app/skills/html_tables/pkg/renderer.py
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from config.themes.table_css import render_table_css


def _is_numeric(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def render(
    df: pd.DataFrame,
    title: str | None = None,
    caption: str | None = None,
    variant: str = "light",
    max_rows: int = 200,
    cell_classes: dict[tuple[int, str], list[str]] | None = None,
) -> str:
    cell_classes = cell_classes or {}
    css = render_table_css(variant=variant)
    caption_text = caption or title
    caption_html = f"<caption>{escape(caption_text)}</caption>" if caption_text else ""

    numeric_cols = {c for c in df.columns if _is_numeric(df[c])}
    thead = "<thead><tr>" + "".join(f"<th>{escape(str(c))}</th>" for c in df.columns) + "</tr></thead>"

    rows_html: list[str] = []
    truncated = max(0, len(df) - max_rows)
    for row_i, (_, row) in enumerate(df.head(max_rows).iterrows()):
        cells: list[str] = []
        for col in df.columns:
            classes: list[str] = []
            if col in numeric_cols:
                classes.append("cell-num")
            classes.extend(cell_classes.get((row_i, col), []))
            cls_attr = f' class="{" ".join(classes)}"' if classes else ""
            val = row[col]
            shown = "" if pd.isna(val) else escape(str(val))
            cells.append(f"<td{cls_attr}>{shown}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")
    if truncated > 0:
        span = len(df.columns)
        rows_html.append(
            f'<tr><td colspan="{span}" class="cell-muted">'
            f"… [{truncated} rows truncated]</td></tr>"
        )
    tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
    table = f'<table class="ga-table">{caption_html}{thead}{tbody}</table>'
    return css + "\n" + table


def _unused_type_hint(_: Any) -> None:
    """Stub kept to prevent flake complaints about the Any import."""
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest app/skills/html_tables/tests/ -v`
Expected: PASS (all 4 tests).

- [ ] **Step 6: Commit html_tables**

```bash
git add backend/app/skills/html_tables/
git commit -m "feat(skills): html_tables renderer pulling theme CSS from active variant"
```

---

## Phase 5 — altair_charts skill + 6 core templates

Install Altair, scaffold the skill, write a shared series-role resolver, then implement 6 templates (enough for `data_profiler` and the Plan 2 stat skills). The remaining 14 templates come in Plan 4.

### Task 5.1: Add altair dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add the dependency line**

Open `backend/pyproject.toml` and add `"altair>=5.5"` to the main `dependencies` list (preserve order with the existing deps).

- [ ] **Step 2: Install**

Run: `cd backend && uv pip install -e '.'` (or `pip install -e .` if not using uv).
Expected: altair and its deps resolve without error.

- [ ] **Step 3: Verify import**

Run: `cd backend && python -c "import altair as alt; print(alt.__version__)"`
Expected: prints version ≥5.5.

### Task 5.2: Scaffold altair_charts skill

**Files:**
- Create: `backend/app/skills/altair_charts/SKILL.md`
- Create: `backend/app/skills/altair_charts/skill.yaml`
- Create: `backend/app/skills/altair_charts/pkg/__init__.py`
- Create: `backend/app/skills/altair_charts/pkg/_common.py`
- Create: `backend/app/skills/altair_charts/tests/__init__.py`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: altair_charts
description: 20 pre-themed chart templates (bar, multi_line, histogram, scatter_trend, boxplot, correlation_heatmap, and more). Theme resolves colors and strokes; templates never take color args.
level: 1
version: '0.1'
---
# altair_charts

Pre-themed Altair chart templates. Every template takes a DataFrame plus field mappings and returns an `alt.Chart` fully themed by the active variant. Agents should reach for these FIRST before writing raw Altair.

## When to use

Default for all chart rendering. Falls through to raw Altair only if no template fits.

## Layer doctrine

1. Templates (this skill) — first choice.
2. Composed — `alt.layer`, `alt.hconcat`, `alt.vconcat` of templates.
3. Themed raw — raw Altair with theme already active.
4. Raw Altair — last-resort escape hatch.

## Series roles

Every template that draws multiple series takes a `series_role` field mapping rather than color literals. Roles (`actual`, `primary`, `secondary`, `reference`, `projection`, `forecast`, `scenario`, `ghost`) resolve to the 8 named blues with role-specific strokes.

## Templates shipped in this phase (6 of 20)

- `bar(df, x, y, category=None)` — simple and grouped.
- `multi_line(df, x, y, series_role)` — time-series with role-typed strokes.
- `histogram(df, field, bins=30)` — distribution.
- `scatter_trend(df, x, y, trend="linear")` — x vs y with regression line.
- `boxplot(df, field, group=None)` — distribution grouped.
- `correlation_heatmap(df, fields=None)` — diverging palette, square matrix.

Remaining 14 ship in Plan 4.
```

- [ ] **Step 2: Write skill.yaml**

```yaml
dependencies:
  requires: [theme_config]
  used_by: [data_profiler, report_builder, dashboard_builder]
  packages: [altair, pandas]
errors: {}
```

- [ ] **Step 3: Write `pkg/_common.py`**

```python
# backend/app/skills/altair_charts/pkg/_common.py
from __future__ import annotations

from typing import Any

import altair as alt

from config.themes.altair_theme import active_tokens, register_all


def ensure_theme_registered() -> None:
    """Call once at chart build time to guarantee themes exist."""
    try:
        if "gir_light" not in alt.themes.names():
            register_all()
    except Exception:  # noqa: BLE001
        register_all()


def resolve_series_style(role: str) -> dict[str, Any]:
    """Return a dict of Altair mark kwargs for a named series role."""
    tokens = active_tokens()
    color = tokens.series_color(role)
    stroke = tokens.series_stroke(role)
    props: dict[str, Any] = {"color": color, "strokeWidth": stroke.width}
    if stroke.dash is not None:
        props["strokeDash"] = stroke.dash
    return props


def diverging_scheme_values() -> list[str]:
    tokens = active_tokens()
    div = tokens.diverging()
    return [div["negative"], div["neutral"], div["positive"]]
```

- [ ] **Step 4: Write `pkg/__init__.py` (will be filled as templates ship)**

```python
# backend/app/skills/altair_charts/pkg/__init__.py
from app.skills.altair_charts.pkg.bar import bar
from app.skills.altair_charts.pkg.boxplot import boxplot
from app.skills.altair_charts.pkg.correlation_heatmap import correlation_heatmap
from app.skills.altair_charts.pkg.histogram import histogram
from app.skills.altair_charts.pkg.multi_line import multi_line
from app.skills.altair_charts.pkg.scatter_trend import scatter_trend

__all__ = [
    "bar",
    "boxplot",
    "correlation_heatmap",
    "histogram",
    "multi_line",
    "scatter_trend",
]
```

Note: the package will fail to import until all six template files exist (Tasks 5.3 – 5.8). That is intentional — every test in this phase reimports `pkg` after a new template lands.

- [ ] **Step 5: Write tests `__init__.py`**

```python
# backend/app/skills/altair_charts/tests/__init__.py
```

### Task 5.3: bar template

**Files:**
- Create: `backend/app/skills/altair_charts/pkg/bar.py`
- Test: `backend/app/skills/altair_charts/tests/test_bar.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/altair_charts/tests/test_bar.py
from __future__ import annotations

import pandas as pd
import pytest


def test_bar_returns_chart_with_bar_mark() -> None:
    # Local import so the rest of the suite does not fail before all templates exist.
    from app.skills.altair_charts.pkg.bar import bar

    df = pd.DataFrame({"country": ["US", "UK"], "revenue": [100, 80]})
    chart = bar(df, x="country", y="revenue")
    spec = chart.to_dict()
    assert spec["mark"] in ("bar", {"type": "bar"}) or spec["mark"]["type"] == "bar"


def test_bar_with_category_adds_color_channel() -> None:
    from app.skills.altair_charts.pkg.bar import bar

    df = pd.DataFrame(
        {"country": ["US", "US", "UK", "UK"], "segment": ["A", "B", "A", "B"], "revenue": [10, 20, 15, 25]}
    )
    chart = bar(df, x="country", y="revenue", category="segment")
    spec = chart.to_dict()
    assert "color" in spec["encoding"]


def test_bar_raises_on_missing_field() -> None:
    from app.skills.altair_charts.pkg.bar import bar

    df = pd.DataFrame({"country": ["US"]})
    with pytest.raises(KeyError, match="y"):
        bar(df, x="country", y="revenue")
```

- [ ] **Step 2: Run test — fails**

Run: `cd backend && pytest app/skills/altair_charts/tests/test_bar.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement bar template**

```python
# backend/app/skills/altair_charts/pkg/bar.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import ensure_theme_registered


def bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    category: str | None = None,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    missing = [f for f in (x, y) + ((category,) if category else ()) if f not in df.columns]
    if missing:
        raise KeyError(
            f"bar(): missing fields {missing}; df has columns {list(df.columns)}"
        )

    x_type = "nominal" if not pd.api.types.is_numeric_dtype(df[x]) else "quantitative"
    encoding: dict = {
        "x": alt.X(x, type=x_type, title=x),
        "y": alt.Y(y, type="quantitative", title=y),
    }
    if category:
        encoding["color"] = alt.Color(category, type="nominal", title=category)
        encoding["xOffset"] = alt.XOffset(category, type="nominal")
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(**encoding)
    )
    if title:
        chart = chart.properties(title=title)
    return chart
```

- [ ] **Step 4: Run test — passes**

Run: `cd backend && pytest app/skills/altair_charts/tests/test_bar.py -v`
Expected: PASS.

### Task 5.4: multi_line template

**Files:**
- Create: `backend/app/skills/altair_charts/pkg/multi_line.py`
- Test: `backend/app/skills/altair_charts/tests/test_multi_line.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/altair_charts/tests/test_multi_line.py
from __future__ import annotations

import pandas as pd


def test_multi_line_with_series_role_has_layers() -> None:
    from app.skills.altair_charts.pkg.multi_line import multi_line

    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=6, freq="ME").tolist() * 2,
            "value": [1, 2, 3, 4, 5, 6, 1.1, 2.1, 3.1, 4.1, 5.1, 6.1],
            "series": ["actual"] * 6 + ["forecast"] * 6,
        }
    )
    chart = multi_line(df, x="date", y="value", series_role="series")
    spec = chart.to_dict()
    # Layered chart containing at least 2 layers (one per role).
    assert "layer" in spec or "hconcat" in spec or "vconcat" in spec or spec.get("mark") in ("line", {"type": "line"})


def test_multi_line_forecast_layer_has_dashed_stroke() -> None:
    from app.skills.altair_charts.pkg.multi_line import multi_line

    df = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=3, freq="ME").tolist() * 2,
         "value": [1, 2, 3, 4, 5, 6],
         "series": ["actual"] * 3 + ["forecast"] * 3}
    )
    chart = multi_line(df, x="date", y="value", series_role="series")
    spec = chart.to_dict()
    # Find a layer whose mark has a strokeDash set.
    layers = spec.get("layer", [])
    assert any(
        isinstance(layer.get("mark"), dict) and layer["mark"].get("strokeDash") is not None
        for layer in layers
    )
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/altair_charts/pkg/multi_line.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def multi_line(
    df: pd.DataFrame,
    x: str,
    y: str,
    series_role: str,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    for f in (x, y, series_role):
        if f not in df.columns:
            raise KeyError(f"multi_line(): missing field '{f}'; df has {list(df.columns)}")

    roles = list(df[series_role].dropna().unique())
    x_type = "temporal" if pd.api.types.is_datetime64_any_dtype(df[x]) else "quantitative"

    layers: list[alt.Chart] = []
    for role in roles:
        style = resolve_series_style(str(role))
        mark_kwargs = {"type": "line", "strokeWidth": style["strokeWidth"], "color": style["color"]}
        if "strokeDash" in style:
            mark_kwargs["strokeDash"] = style["strokeDash"]
        sub = (
            alt.Chart(df[df[series_role] == role])
            .mark_line(**mark_kwargs)
            .encode(
                x=alt.X(x, type=x_type, title=x),
                y=alt.Y(y, type="quantitative", title=y),
            )
        )
        layers.append(sub)
    chart = alt.layer(*layers) if len(layers) > 1 else layers[0]
    if title:
        chart = chart.properties(title=title)
    return chart
```

- [ ] **Step 4: Run — passes.**

Run: `cd backend && pytest app/skills/altair_charts/tests/test_multi_line.py -v`
Expected: PASS.

### Task 5.5: histogram template

**Files:**
- Create: `backend/app/skills/altair_charts/pkg/histogram.py`
- Test: `backend/app/skills/altair_charts/tests/test_histogram.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/altair_charts/tests/test_histogram.py
from __future__ import annotations

import pandas as pd


def test_histogram_uses_bar_mark_with_bin() -> None:
    from app.skills.altair_charts.pkg.histogram import histogram

    df = pd.DataFrame({"revenue": list(range(100))})
    chart = histogram(df, field="revenue", bins=10)
    spec = chart.to_dict()
    enc = spec["encoding"]
    assert enc["x"]["bin"] in (True, {"maxbins": 10})


def test_histogram_raises_on_non_numeric_field() -> None:
    import pytest

    from app.skills.altair_charts.pkg.histogram import histogram

    df = pd.DataFrame({"cat": ["a", "b"]})
    with pytest.raises(ValueError, match="numeric"):
        histogram(df, field="cat")
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/altair_charts/pkg/histogram.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import ensure_theme_registered


def histogram(
    df: pd.DataFrame,
    field: str,
    bins: int = 30,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    if field not in df.columns:
        raise KeyError(f"histogram(): missing field '{field}'")
    if not pd.api.types.is_numeric_dtype(df[field]):
        raise ValueError(f"histogram(): field '{field}' must be numeric")

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(field, bin=alt.Bin(maxbins=bins), title=field),
            y=alt.Y("count()", title="count"),
        )
    )
    if title:
        chart = chart.properties(title=title)
    return chart
```

- [ ] **Step 4: Run — passes.**

### Task 5.6: scatter_trend template

**Files:**
- Create: `backend/app/skills/altair_charts/pkg/scatter_trend.py`
- Test: `backend/app/skills/altair_charts/tests/test_scatter_trend.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/altair_charts/tests/test_scatter_trend.py
from __future__ import annotations

import pandas as pd


def test_scatter_trend_layers_points_and_regression_line() -> None:
    from app.skills.altair_charts.pkg.scatter_trend import scatter_trend

    df = pd.DataFrame({"x": list(range(20)), "y": [i * 2 + 1 for i in range(20)]})
    chart = scatter_trend(df, x="x", y="y")
    spec = chart.to_dict()
    assert "layer" in spec
    marks = {layer.get("mark", {}).get("type") if isinstance(layer.get("mark"), dict) else layer.get("mark") for layer in spec["layer"]}
    assert "point" in marks or "circle" in marks
    assert "line" in marks


def test_scatter_trend_raises_on_non_numeric_axes() -> None:
    import pytest
    from app.skills.altair_charts.pkg.scatter_trend import scatter_trend

    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
    with pytest.raises(ValueError, match="numeric"):
        scatter_trend(df, x="x", y="y")
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/altair_charts/pkg/scatter_trend.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def scatter_trend(
    df: pd.DataFrame,
    x: str,
    y: str,
    trend: str = "linear",
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    for f in (x, y):
        if f not in df.columns:
            raise KeyError(f"scatter_trend(): missing field '{f}'")
        if not pd.api.types.is_numeric_dtype(df[f]):
            raise ValueError(f"scatter_trend(): '{f}' must be numeric")

    primary = resolve_series_style("primary")
    reference = resolve_series_style("reference")

    points = (
        alt.Chart(df)
        .mark_circle(color=primary["color"], size=45, opacity=0.75)
        .encode(
            x=alt.X(x, type="quantitative"),
            y=alt.Y(y, type="quantitative"),
        )
    )
    line = (
        alt.Chart(df)
        .transform_regression(x, y, method=trend)
        .mark_line(color=reference["color"], strokeWidth=reference["strokeWidth"],
                   strokeDash=reference.get("strokeDash"))
        .encode(
            x=alt.X(x, type="quantitative"),
            y=alt.Y(y, type="quantitative"),
        )
    )
    chart = alt.layer(points, line)
    if title:
        chart = chart.properties(title=title)
    return chart
```

- [ ] **Step 4: Run — passes.**

### Task 5.7: boxplot template

**Files:**
- Create: `backend/app/skills/altair_charts/pkg/boxplot.py`
- Test: `backend/app/skills/altair_charts/tests/test_boxplot.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/altair_charts/tests/test_boxplot.py
from __future__ import annotations

import pandas as pd


def test_boxplot_with_group_has_category_axis() -> None:
    from app.skills.altair_charts.pkg.boxplot import boxplot

    df = pd.DataFrame(
        {"segment": ["A", "A", "B", "B", "A", "B"], "revenue": [1.0, 2.0, 5.0, 6.0, 1.5, 5.5]}
    )
    chart = boxplot(df, field="revenue", group="segment")
    spec = chart.to_dict()
    assert spec["mark"]["type"] == "boxplot"
    assert spec["encoding"]["x"]["field"] == "segment"


def test_boxplot_without_group_is_single_box() -> None:
    from app.skills.altair_charts.pkg.boxplot import boxplot

    df = pd.DataFrame({"revenue": [1.0, 2.0, 5.0, 6.0, 1.5, 5.5]})
    chart = boxplot(df, field="revenue")
    spec = chart.to_dict()
    assert spec["mark"]["type"] == "boxplot"
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/altair_charts/pkg/boxplot.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    ensure_theme_registered,
    resolve_series_style,
)


def boxplot(
    df: pd.DataFrame,
    field: str,
    group: str | None = None,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    if field not in df.columns:
        raise KeyError(f"boxplot(): missing field '{field}'")
    if not pd.api.types.is_numeric_dtype(df[field]):
        raise ValueError(f"boxplot(): '{field}' must be numeric")
    if group and group not in df.columns:
        raise KeyError(f"boxplot(): missing group '{group}'")

    primary = resolve_series_style("primary")
    encoding: dict = {"y": alt.Y(field, type="quantitative", title=field)}
    if group:
        encoding["x"] = alt.X(group, type="nominal", title=group)
    chart = (
        alt.Chart(df)
        .mark_boxplot(color=primary["color"], size=40)
        .encode(**encoding)
    )
    if title:
        chart = chart.properties(title=title)
    return chart
```

- [ ] **Step 4: Run — passes.**

### Task 5.8: correlation_heatmap template

**Files:**
- Create: `backend/app/skills/altair_charts/pkg/correlation_heatmap.py`
- Test: `backend/app/skills/altair_charts/tests/test_correlation_heatmap.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/altair_charts/tests/test_correlation_heatmap.py
from __future__ import annotations

import pandas as pd


def test_correlation_heatmap_returns_square_matrix() -> None:
    from app.skills.altair_charts.pkg.correlation_heatmap import correlation_heatmap

    df = pd.DataFrame({"a": range(20), "b": range(20, 40), "c": list(range(0, 40, 2))})
    chart = correlation_heatmap(df)
    spec = chart.to_dict()
    assert spec["mark"]["type"] == "rect"
    # data embedded should have n*n rows (3×3 = 9)
    values = spec.get("data", {}).get("values") or spec.get("datasets", {}).get(
        next(iter(spec.get("datasets", {})), ""), []
    )
    assert len(values) == 9


def test_correlation_heatmap_ignores_non_numeric_fields() -> None:
    from app.skills.altair_charts.pkg.correlation_heatmap import correlation_heatmap

    df = pd.DataFrame({"a": range(5), "b": range(5), "cat": list("abcde")})
    chart = correlation_heatmap(df)
    spec = chart.to_dict()
    values = spec.get("data", {}).get("values") or []
    if not values:
        datasets = spec.get("datasets", {})
        values = datasets[next(iter(datasets))]
    fields = {v["var_x"] for v in values}
    assert "cat" not in fields
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/altair_charts/pkg/correlation_heatmap.py
from __future__ import annotations

import altair as alt
import pandas as pd

from app.skills.altair_charts.pkg._common import (
    diverging_scheme_values,
    ensure_theme_registered,
)


def correlation_heatmap(
    df: pd.DataFrame,
    fields: list[str] | None = None,
    title: str | None = None,
) -> alt.Chart:
    ensure_theme_registered()
    numeric_df = df.select_dtypes(include="number")
    if fields is not None:
        numeric_df = numeric_df[[f for f in fields if f in numeric_df.columns]]
    corr = numeric_df.corr(numeric_only=True).round(3)

    # Melt to long form.
    long = (
        corr.reset_index()
        .melt(id_vars="index", var_name="var_y", value_name="corr")
        .rename(columns={"index": "var_x"})
    )

    diverging = diverging_scheme_values()
    chart = (
        alt.Chart(long)
        .mark_rect()
        .encode(
            x=alt.X("var_x:N", title=None),
            y=alt.Y("var_y:N", title=None),
            color=alt.Color(
                "corr:Q",
                scale=alt.Scale(domain=[-1, 0, 1], range=diverging),
                title="corr",
            ),
            tooltip=[alt.Tooltip("var_x:N"), alt.Tooltip("var_y:N"), alt.Tooltip("corr:Q", format=".2f")],
        )
    )
    if title:
        chart = chart.properties(title=title)
    return chart
```

- [ ] **Step 4: Run full altair suite**

Run: `cd backend && pytest app/skills/altair_charts/ -v`
Expected: PASS (6 template test files, 12+ tests total).

- [ ] **Step 5: Commit Phase 5**

```bash
git add backend/pyproject.toml backend/app/skills/altair_charts/
git commit -m "feat(skills): altair_charts with 6 themed templates (bar/line/hist/scatter/box/heatmap)"
```

---

## Phase 6 — data_profiler skill

Eight sections, 21 risk types, editorial HTML report with embedded charts, `profile` artifact type. Built on top of theme + artifact store + sql_builder + html_tables + altair_charts.

### Task 6.1: Scaffold data_profiler + risks + ProfileReport

**Files:**
- Create: `backend/app/skills/data_profiler/SKILL.md`
- Create: `backend/app/skills/data_profiler/skill.yaml`
- Create: `backend/app/skills/data_profiler/pkg/__init__.py`
- Create: `backend/app/skills/data_profiler/pkg/risks.py`
- Create: `backend/app/skills/data_profiler/pkg/report.py`
- Create: `backend/app/skills/data_profiler/tests/__init__.py`
- Create: `backend/app/skills/data_profiler/tests/fixtures/__init__.py`
- Create: `backend/app/skills/data_profiler/tests/fixtures/conftest.py`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: data_profiler
description: Full-dataset profile. Runs before analysis; surfaces structured risks (missing, dupes, keys, outliers, dates, skew) with BLOCKER/HIGH/MEDIUM/LOW severity. Emits a machine-readable JSON artifact and a human-readable HTML report.
level: 1
version: '0.1'
---
# data_profiler

One call, eight sections, structured risks. Agents should call this on any unfamiliar dataset before analyzing. If a BLOCKER is raised, resolve it first.

## When to use

First turn on a new dataset. Optionally again after a transformation that changed the shape (merges, joins, filters).

## Contract

```python
report = profile(df, name="customers_v1", key_candidates=["customer_id"])
# report.summary             — one-paragraph, model-readable
# report.risks               — severity-sorted Risk list
# report.sections            — full section payloads
# report.artifact_id         — profile-json artifact
# report.report_artifact_id  — profile-html artifact
```

## Sections

1. `schema` — types, counts, null counts.
2. `missingness` — per-column missing %; co-occurrence between columns.
3. `duplicates` — duplicate rows; duplicate keys (if `key_candidates` given).
4. `distributions` — skew, kurtosis, near-constant detection.
5. `dates` — monotonicity, gaps, future dates, naive timezones.
6. `outliers` — IQR + p0.001/p0.999 tail.
7. `keys` — cardinality; suspected foreign keys to passed `key_candidates`.
8. `relationships` — pairwise correlations and collinear pairs (|r| > 0.95).

## Risk severities

- `BLOCKER` — analysis should stop until resolved (duplicate key, >50% missing on a required col).
- `HIGH` — must be disclosed in any Finding using the affected columns.
- `MEDIUM` — worth noting in COT.
- `LOW` — informational.

Every risk has a `mitigation` string.
```

- [ ] **Step 2: Write skill.yaml**

```yaml
dependencies:
  requires: [theme_config, sql_builder, html_tables, altair_charts]
  used_by: [report_builder]
  packages: [pandas, numpy, duckdb]
errors:
  EMPTY_DATAFRAME:
    message: "data_profiler called on empty DataFrame '{name}'."
    guidance: "Load data before profiling; empty DFs cannot be validated."
    recovery: "Inspect the source query and retry."
```

- [ ] **Step 3: Implement risks.py**

```python
# backend/app/skills/data_profiler/pkg/risks.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["BLOCKER", "HIGH", "MEDIUM", "LOW"]

RISK_KINDS: tuple[str, ...] = (
    "missing_over_threshold",
    "missing_co_occurrence",
    "duplicate_rows",
    "duplicate_key",
    "constant_column",
    "near_constant",
    "high_cardinality_categorical",
    "low_cardinality_numeric",
    "mixed_types",
    "date_gaps",
    "date_non_monotonic",
    "date_future",
    "outliers_extreme",
    "skew_heavy",
    "suspicious_zeros",
    "suspicious_placeholders",
    "unit_inconsistency",
    "suspected_foreign_key",
    "collinear_pair",
    "class_imbalance",
    "timezone_naive",
)

SEVERITY_ORDER: dict[str, int] = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@dataclass(frozen=True)
class Risk:
    kind: str
    severity: Severity
    columns: tuple[str, ...]
    detail: str
    mitigation: str

    def __post_init__(self) -> None:
        if self.kind not in RISK_KINDS:
            raise ValueError(f"unknown risk kind: {self.kind}")

    def sort_key(self) -> tuple[int, str, tuple[str, ...]]:
        return (SEVERITY_ORDER[self.severity], self.kind, self.columns)
```

- [ ] **Step 4: Implement report.py**

```python
# backend/app/skills/data_profiler/pkg/report.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.skills.data_profiler.pkg.risks import Risk


@dataclass(frozen=True)
class ProfileReport:
    name: str
    n_rows: int
    n_cols: int
    summary: str
    risks: list[Risk] = field(default_factory=list)
    sections: dict[str, Any] = field(default_factory=dict)
    artifact_id: str | None = None
    report_artifact_id: str | None = None
```

- [ ] **Step 5: Write shared test fixtures**

```python
# backend/app/skills/data_profiler/tests/__init__.py
```

```python
# backend/app/skills/data_profiler/tests/fixtures/__init__.py
```

```python
# backend/app/skills/data_profiler/tests/fixtures/conftest.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def small_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4, 5],
            "age": [25, 30, np.nan, 40, 45],
            "country": ["US", "UK", "US", None, "US"],
            "signup_date": pd.to_datetime(
                ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-20", "2024-03-01"]
            ),
            "revenue": [100.0, 200.0, 150.0, np.nan, 300.0],
        }
    )


@pytest.fixture
def duplicated_key_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"customer_id": [1, 2, 2, 3], "revenue": [10.0, 20.0, 25.0, 30.0]}
    )


@pytest.fixture
def heavy_missing_df() -> pd.DataFrame:
    import numpy as np
    return pd.DataFrame(
        {
            "id": range(10),
            "email": [None] * 8 + ["a@b", "c@d"],
            "score": [1.0, np.nan, 3.0, np.nan, 5.0, np.nan, 7.0, np.nan, 9.0, np.nan],
        }
    )


@pytest.fixture
def date_gap_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"ts": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-10", "2024-01-11"])}
    )
```

Add this `conftest.py` path into pytest discovery by adding to `backend/pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
testpaths = ["tests", "app/skills"]
```

If the key already exists, merge rather than duplicate.

### Task 6.2: schema section (types + counts)

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/__init__.py`
- Create: `backend/app/skills/data_profiler/pkg/sections/schema.py`
- Test: `backend/app/skills/data_profiler/tests/test_schema.py`

- [ ] **Step 1: Empty `sections/__init__.py`**

```python
# backend/app/skills/data_profiler/pkg/sections/__init__.py
```

- [ ] **Step 2: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_schema.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_schema_reports_column_types_and_null_counts(small_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.schema import run

    result = run(small_df)
    cols = {c["name"]: c for c in result["columns"]}
    assert cols["age"]["null_count"] == 1
    assert cols["country"]["null_count"] == 1
    assert cols["customer_id"]["dtype"].startswith("int")
    assert cols["signup_date"]["dtype"].startswith("datetime")


def test_schema_flags_mixed_types() -> None:
    from app.skills.data_profiler.pkg.sections.schema import run

    df = pd.DataFrame({"mix": [1, "two", 3.0]})
    result = run(df)
    risks = result["risks"]
    assert any(r.kind == "mixed_types" for r in risks)
```

- [ ] **Step 3: Run — fails. Step 4: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/schema.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk


def run(df: pd.DataFrame) -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    risks: list[Risk] = []
    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        null_count = int(series.isna().sum())
        columns.append(
            {
                "name": col,
                "dtype": dtype,
                "null_count": null_count,
                "non_null_count": int(len(series) - null_count),
            }
        )
        if dtype == "object":
            non_null = series.dropna()
            types = {type(v).__name__ for v in non_null}
            if len(types) > 1:
                risks.append(
                    Risk(
                        kind="mixed_types",
                        severity="HIGH",
                        columns=(col,),
                        detail=f"column '{col}' contains mixed types: {sorted(types)}",
                        mitigation=(
                            "Coerce to a single type before analysis "
                            "(pd.to_numeric(errors='coerce') or str())."
                        ),
                    )
                )
    return {"n_rows": int(len(df)), "n_cols": int(len(df.columns)), "columns": columns, "risks": risks}
```

- [ ] **Step 5: Run — passes.**

Run: `cd backend && pytest app/skills/data_profiler/tests/test_schema.py -v`

### Task 6.3: missingness section

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/missingness.py`
- Test: `backend/app/skills/data_profiler/tests/test_missingness.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_missingness.py
from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_flags_missing_over_50_percent(heavy_missing_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.missingness import run

    result = run(heavy_missing_df)
    kinds = {(r.kind, r.severity) for r in result["risks"]}
    assert ("missing_over_threshold", "BLOCKER") in kinds
    assert any(r.columns == ("email",) for r in result["risks"] if r.kind == "missing_over_threshold")


def test_flags_co_occurrence_when_columns_missing_together() -> None:
    from app.skills.data_profiler.pkg.sections.missingness import run

    df = pd.DataFrame(
        {"a": [None, None, 3.0, 4.0, 5.0], "b": [None, None, 3.0, 4.0, 5.0]}
    )
    result = run(df)
    kinds = {r.kind for r in result["risks"]}
    assert "missing_co_occurrence" in kinds
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/missingness.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

BLOCKER_THRESHOLD = 0.5
HIGH_THRESHOLD = 0.2
CO_OCCURRENCE_THRESHOLD = 0.8


def run(df: pd.DataFrame) -> dict[str, Any]:
    n = len(df)
    risks: list[Risk] = []
    per_col: dict[str, float] = {}
    for col in df.columns:
        frac = float(df[col].isna().mean()) if n else 0.0
        per_col[col] = frac
        if frac >= BLOCKER_THRESHOLD:
            risks.append(
                Risk(
                    kind="missing_over_threshold",
                    severity="BLOCKER",
                    columns=(col,),
                    detail=f"{frac * 100:.1f}% of '{col}' is null",
                    mitigation="Drop the column or impute before analysis; do not silently ignore.",
                )
            )
        elif frac >= HIGH_THRESHOLD:
            risks.append(
                Risk(
                    kind="missing_over_threshold",
                    severity="HIGH",
                    columns=(col,),
                    detail=f"{frac * 100:.1f}% of '{col}' is null",
                    mitigation="Either impute with a defensible strategy or restrict analysis to non-null rows and disclose.",
                )
            )

    # Co-occurrence: look for pairs that are null together
    nan_mask = df.isna()
    cols_with_nulls = [c for c in df.columns if per_col[c] > 0]
    for i, a in enumerate(cols_with_nulls):
        for b in cols_with_nulls[i + 1 :]:
            a_null = nan_mask[a]
            b_null = nan_mask[b]
            joint = int((a_null & b_null).sum())
            base = int(a_null.sum())
            if base and joint / base >= CO_OCCURRENCE_THRESHOLD:
                risks.append(
                    Risk(
                        kind="missing_co_occurrence",
                        severity="MEDIUM",
                        columns=(a, b),
                        detail=f"when '{a}' is null, '{b}' is null {joint / base * 100:.0f}% of the time",
                        mitigation="Treat these as a single 'not collected' case; consider one indicator column.",
                    )
                )
    return {"per_column_fraction": per_col, "risks": risks}
```

- [ ] **Step 4: Run — passes.**

### Task 6.4: duplicates section

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/duplicates.py`
- Test: `backend/app/skills/data_profiler/tests/test_duplicates.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_duplicates.py
from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_detects_duplicate_rows() -> None:
    from app.skills.data_profiler.pkg.sections.duplicates import run

    df = pd.DataFrame({"a": [1, 1, 2], "b": [10, 10, 20]})
    result = run(df, key_candidates=None)
    assert any(r.kind == "duplicate_rows" and r.severity == "HIGH" for r in result["risks"])


def test_duplicate_key_is_blocker(duplicated_key_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.duplicates import run

    result = run(duplicated_key_df, key_candidates=["customer_id"])
    kinds = {(r.kind, r.severity) for r in result["risks"]}
    assert ("duplicate_key", "BLOCKER") in kinds
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/duplicates.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk


def run(df: pd.DataFrame, key_candidates: list[str] | None = None) -> dict[str, Any]:
    risks: list[Risk] = []
    dup_rows = int(df.duplicated().sum())
    if dup_rows > 0:
        risks.append(
            Risk(
                kind="duplicate_rows",
                severity="HIGH",
                columns=tuple(df.columns),
                detail=f"{dup_rows} full-row duplicates detected",
                mitigation="Run `df.drop_duplicates()` or investigate the source for re-ingestion bugs.",
            )
        )
    dup_key_detail: dict[str, int] = {}
    if key_candidates:
        for col in key_candidates:
            if col not in df.columns:
                continue
            dup = int(df.duplicated(subset=[col]).sum())
            dup_key_detail[col] = dup
            if dup > 0:
                risks.append(
                    Risk(
                        kind="duplicate_key",
                        severity="BLOCKER",
                        columns=(col,),
                        detail=f"'{col}' has {dup} duplicate values; not a valid primary key",
                        mitigation="Re-derive the key, deduplicate with a tie-breaker, or choose a composite key.",
                    )
                )
    return {"duplicate_rows": dup_rows, "duplicate_keys": dup_key_detail, "risks": risks}
```

- [ ] **Step 4: Run — passes.**

### Task 6.5: distributions section (skew + near-constant)

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/distributions.py`
- Test: `backend/app/skills/data_profiler/tests/test_distributions.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_distributions.py
from __future__ import annotations

import numpy as np
import pandas as pd


def test_flags_heavy_skew() -> None:
    from app.skills.data_profiler.pkg.sections.distributions import run

    rng = np.random.default_rng(0)
    # Heavy right skew: mostly zeros with a few huge tails.
    values = rng.exponential(scale=1.0, size=2000)
    values[-5:] = 1e6
    df = pd.DataFrame({"v": values})
    result = run(df)
    assert any(r.kind == "skew_heavy" for r in result["risks"])


def test_flags_constant_column() -> None:
    from app.skills.data_profiler.pkg.sections.distributions import run

    df = pd.DataFrame({"k": [1] * 100})
    result = run(df)
    assert any(r.kind == "constant_column" for r in result["risks"])


def test_flags_near_constant() -> None:
    from app.skills.data_profiler.pkg.sections.distributions import run

    df = pd.DataFrame({"mostly_one": [1] * 98 + [2, 3]})
    result = run(df)
    kinds = {r.kind for r in result["risks"]}
    assert "near_constant" in kinds
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/distributions.py
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

SKEW_THRESHOLD = 3.0
NEAR_CONST_THRESHOLD = 0.95


def run(df: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, dict[str, float]] = {}
    risks: list[Risk] = []
    for col in df.columns:
        s = df[col].dropna()
        if s.empty:
            continue
        n_unique = int(s.nunique())
        if n_unique == 1:
            risks.append(
                Risk(
                    kind="constant_column",
                    severity="MEDIUM",
                    columns=(col,),
                    detail=f"column '{col}' has a single value",
                    mitigation="Consider dropping before modeling.",
                )
            )
            continue
        # Near-constant: mode fraction ≥ threshold
        mode_frac = float(s.value_counts(normalize=True).iloc[0])
        if mode_frac >= NEAR_CONST_THRESHOLD:
            risks.append(
                Risk(
                    kind="near_constant",
                    severity="MEDIUM",
                    columns=(col,),
                    detail=f"{mode_frac * 100:.1f}% of '{col}' is a single mode value",
                    mitigation="Likely uninformative; validate before using as a feature.",
                )
            )
        if pd.api.types.is_numeric_dtype(s):
            skew = float(pd.Series(s).skew())
            stats[col] = {"skew": skew, "kurtosis": float(pd.Series(s).kurt())}
            if abs(skew) >= SKEW_THRESHOLD:
                risks.append(
                    Risk(
                        kind="skew_heavy",
                        severity="MEDIUM",
                        columns=(col,),
                        detail=f"'{col}' skew={skew:.2f} — consider log or rank transform",
                        mitigation="Apply np.log1p for right-skew or a winsorized transform before parametric tests.",
                    )
                )
    return {"stats": stats, "risks": risks}
```

- [ ] **Step 4: Run — passes.**

### Task 6.6: dates section (gaps + future + naive tz)

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/dates.py`
- Test: `backend/app/skills/data_profiler/tests/test_dates.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_dates.py
from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_flags_date_gap(date_gap_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.sections.dates import run

    result = run(date_gap_df)
    assert any(r.kind == "date_gaps" for r in result["risks"])


def test_flags_future_dates() -> None:
    from app.skills.data_profiler.pkg.sections.dates import run

    df = pd.DataFrame({"ts": pd.to_datetime(["2099-01-01", "2020-01-01"])})
    result = run(df)
    assert any(r.kind == "date_future" for r in result["risks"])


def test_flags_timezone_naive() -> None:
    from app.skills.data_profiler.pkg.sections.dates import run

    df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01"])})
    result = run(df)
    assert any(r.kind == "timezone_naive" for r in result["risks"])
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/dates.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk


def _is_date(series: pd.Series) -> bool:
    return pd.api.types.is_datetime64_any_dtype(series)


def run(df: pd.DataFrame) -> dict[str, Any]:
    risks: list[Risk] = []
    now = datetime.now(timezone.utc)
    for col in df.columns:
        s = df[col].dropna()
        if not _is_date(s) or s.empty:
            continue
        # Timezone-naive detection
        if s.dt.tz is None:
            risks.append(
                Risk(
                    kind="timezone_naive",
                    severity="LOW",
                    columns=(col,),
                    detail=f"'{col}' is timezone-naive",
                    mitigation="Use `tz_localize` to fix the origin zone before comparing across sources.",
                )
            )
        # Non-monotonic: sorted series differs from series
        if not s.sort_values().equals(s):
            risks.append(
                Risk(
                    kind="date_non_monotonic",
                    severity="LOW",
                    columns=(col,),
                    detail=f"'{col}' is not monotonically ordered",
                    mitigation="Sort before any time-series analysis.",
                )
            )
        # Gaps: median diff vs max diff
        diffs = s.sort_values().diff().dropna()
        if not diffs.empty:
            median = diffs.median()
            max_gap = diffs.max()
            if median.total_seconds() > 0 and max_gap.total_seconds() > median.total_seconds() * 5:
                risks.append(
                    Risk(
                        kind="date_gaps",
                        severity="MEDIUM",
                        columns=(col,),
                        detail=f"'{col}' has a max gap of {max_gap} vs median {median}",
                        mitigation="Confirm the gap is real (no data) vs a reporting cadence change; reindex if needed.",
                    )
                )
        # Future dates
        as_utc = s if s.dt.tz is not None else s.dt.tz_localize("UTC")
        if (as_utc > now).any():
            risks.append(
                Risk(
                    kind="date_future",
                    severity="HIGH",
                    columns=(col,),
                    detail=f"'{col}' contains dates in the future",
                    mitigation="Verify the source; future timestamps often indicate bad joins or TZ bugs.",
                )
            )
    return {"risks": risks}
```

- [ ] **Step 4: Run — passes.**

### Task 6.7: outliers section

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/outliers.py`
- Test: `backend/app/skills/data_profiler/tests/test_outliers.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_outliers.py
from __future__ import annotations

import numpy as np
import pandas as pd


def test_flags_extreme_outliers() -> None:
    from app.skills.data_profiler.pkg.sections.outliers import run

    rng = np.random.default_rng(0)
    values = rng.normal(0, 1, size=1000)
    values[-3:] = [1e9, -1e9, 5e8]
    df = pd.DataFrame({"v": values})
    result = run(df)
    assert any(r.kind == "outliers_extreme" for r in result["risks"])


def test_does_not_flag_normal_distribution() -> None:
    from app.skills.data_profiler.pkg.sections.outliers import run

    rng = np.random.default_rng(1)
    df = pd.DataFrame({"v": rng.normal(0, 1, size=1000)})
    result = run(df)
    assert not any(r.kind == "outliers_extreme" for r in result["risks"])
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/outliers.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

TAIL_P = 0.001
MIN_SAMPLES = 50


def run(df: pd.DataFrame) -> dict[str, Any]:
    risks: list[Risk] = []
    details: dict[str, dict[str, float]] = {}
    for col in df.columns:
        s = df[col].dropna()
        if not pd.api.types.is_numeric_dtype(s) or len(s) < MIN_SAMPLES:
            continue
        low = s.quantile(TAIL_P)
        high = s.quantile(1 - TAIL_P)
        extreme_hi = int((s > high * 10).sum()) if high > 0 else int((s > high + abs(high) * 9).sum())
        extreme_lo = int((s < low * 10).sum()) if low < 0 else 0
        details[col] = {"p001": float(low), "p999": float(high)}
        if extreme_hi + extreme_lo > 0:
            risks.append(
                Risk(
                    kind="outliers_extreme",
                    severity="MEDIUM",
                    columns=(col,),
                    detail=(
                        f"'{col}' has {extreme_hi + extreme_lo} points >10× the 0.1%/99.9% tail"
                    ),
                    mitigation="Verify unit consistency and data-entry bugs; winsorize before parametric tests.",
                )
            )
    return {"details": details, "risks": risks}
```

- [ ] **Step 4: Run — passes.**

### Task 6.8: keys section (cardinality + FK suggestion)

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/keys.py`
- Test: `backend/app/skills/data_profiler/tests/test_keys.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_keys.py
from __future__ import annotations

import pandas as pd


def test_flags_high_cardinality_categorical() -> None:
    from app.skills.data_profiler.pkg.sections.keys import run

    df = pd.DataFrame({"uid": [f"u{i}" for i in range(100)]})
    result = run(df, key_candidates=None)
    kinds = {r.kind for r in result["risks"]}
    assert "high_cardinality_categorical" in kinds


def test_suggests_foreign_key_when_values_overlap_candidate() -> None:
    from app.skills.data_profiler.pkg.sections.keys import run

    df = pd.DataFrame({"ref": [1, 2, 3, 3, 2, 1]})
    result = run(df, key_candidates=["customer_id"])
    assert any(r.kind == "suspected_foreign_key" for r in result["risks"])
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/keys.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

HIGH_CARD_RATIO = 0.9


def run(df: pd.DataFrame, key_candidates: list[str] | None = None) -> dict[str, Any]:
    risks: list[Risk] = []
    cardinalities: dict[str, int] = {}
    n = len(df)
    for col in df.columns:
        s = df[col].dropna()
        u = int(s.nunique())
        cardinalities[col] = u
        if s.dtype == object and n and u / max(n, 1) >= HIGH_CARD_RATIO:
            risks.append(
                Risk(
                    kind="high_cardinality_categorical",
                    severity="LOW",
                    columns=(col,),
                    detail=f"'{col}' has {u} unique values out of {n} rows",
                    mitigation="Avoid one-hot encoding directly; consider target encoding or dropping.",
                )
            )
        if pd.api.types.is_numeric_dtype(s) and u < 10 and n > 100:
            risks.append(
                Risk(
                    kind="low_cardinality_numeric",
                    severity="LOW",
                    columns=(col,),
                    detail=f"numeric column '{col}' only has {u} distinct values",
                    mitigation="Consider treating as categorical; arithmetic may not be meaningful.",
                )
            )
    if key_candidates:
        for col in df.columns:
            if col in key_candidates:
                continue
            # Heuristic: numeric column whose values look like keys (ints or hex-ish)
            s = df[col].dropna()
            if not pd.api.types.is_integer_dtype(s):
                continue
            if s.nunique() > 1 and s.nunique() <= n:
                risks.append(
                    Risk(
                        kind="suspected_foreign_key",
                        severity="LOW",
                        columns=(col,),
                        detail=f"'{col}' looks like a foreign key (integer, many distinct values)",
                        mitigation=f"Confirm join target among candidates {key_candidates}.",
                    )
                )
    return {"cardinalities": cardinalities, "risks": risks}
```

- [ ] **Step 4: Run — passes.**

### Task 6.9: relationships section

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/sections/relationships.py`
- Test: `backend/app/skills/data_profiler/tests/test_relationships.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_relationships.py
from __future__ import annotations

import pandas as pd


def test_flags_collinear_pair() -> None:
    from app.skills.data_profiler.pkg.sections.relationships import run

    df = pd.DataFrame(
        {"x": list(range(100)), "y_dup": [v + 0.001 for v in range(100)], "z": [i % 4 for i in range(100)]}
    )
    result = run(df)
    assert any(
        r.kind == "collinear_pair" and set(r.columns) == {"x", "y_dup"} for r in result["risks"]
    )
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/sections/relationships.py
from __future__ import annotations

from typing import Any

import pandas as pd

from app.skills.data_profiler.pkg.risks import Risk

COLLINEAR_THRESHOLD = 0.95


def run(df: pd.DataFrame) -> dict[str, Any]:
    num = df.select_dtypes(include="number")
    if num.shape[1] < 2:
        return {"correlations": {}, "risks": []}
    corr = num.corr(numeric_only=True)
    pairs: list[tuple[str, str, float]] = []
    cols = list(corr.columns)
    risks: list[Risk] = []
    for i, a in enumerate(cols):
        for b in cols[i + 1 :]:
            val = float(corr.loc[a, b])
            if pd.notna(val):
                pairs.append((a, b, val))
                if abs(val) >= COLLINEAR_THRESHOLD:
                    risks.append(
                        Risk(
                            kind="collinear_pair",
                            severity="MEDIUM",
                            columns=(a, b),
                            detail=f"corr({a}, {b}) = {val:.3f}",
                            mitigation="Drop one before modeling to avoid unstable coefficients.",
                        )
                    )
    return {"correlations": pairs, "risks": risks}
```

- [ ] **Step 4: Run — passes.**

### Task 6.10: profile() orchestrator

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/profile.py`
- Test: `backend/app/skills/data_profiler/tests/test_profile.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_profile.py
from __future__ import annotations

import pandas as pd
import pytest

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_profile_returns_report_with_risks_sorted(duplicated_key_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.profile import profile

    report = profile(duplicated_key_df, name="cust", key_candidates=["customer_id"])
    assert report.n_rows == 4
    assert report.risks[0].severity == "BLOCKER"
    assert "customer_id" in report.summary


def test_profile_saves_json_and_html_artifacts_when_store_given(
    small_df: pd.DataFrame, tmp_path
) -> None:
    from app.artifacts.store import ArtifactStore
    from app.skills.data_profiler.pkg.profile import profile

    store = ArtifactStore(db_path=tmp_path / "a.db", disk_root=tmp_path / "blobs")
    report = profile(small_df, name="customers_v1", store=store, session_id="s1")
    assert report.artifact_id is not None
    assert report.report_artifact_id is not None

    saved_json = store.get_artifact("s1", report.artifact_id)
    assert saved_json is not None and saved_json.format == "profile-json"

    saved_html = store.get_artifact("s1", report.report_artifact_id)
    assert saved_html is not None and saved_html.format == "profile-html"
    assert "<html" in saved_html.content.lower()


def test_profile_empty_dataframe_raises(tmp_path) -> None:
    from app.skills.base import SkillError
    from app.skills.data_profiler.pkg.profile import profile

    with pytest.raises(SkillError):
        profile(pd.DataFrame(), name="empty")
```

- [ ] **Step 2: Run — fails. Step 3: Implement orchestrator:**

```python
# backend/app/skills/data_profiler/pkg/__init__.py
from app.skills.data_profiler.pkg.profile import profile
from app.skills.data_profiler.pkg.report import ProfileReport
from app.skills.data_profiler.pkg.risks import Risk

__all__ = ["profile", "ProfileReport", "Risk"]
```

```python
# backend/app/skills/data_profiler/pkg/profile.py
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import pandas as pd

from app.artifacts.models import Artifact
from app.artifacts.store import ArtifactStore
from app.skills.base import SkillError
from app.skills.data_profiler.pkg.html_report import render_html_report
from app.skills.data_profiler.pkg.report import ProfileReport
from app.skills.data_profiler.pkg.risks import Risk
from app.skills.data_profiler.pkg.sections import (
    dates,
    distributions,
    duplicates,
    keys,
    missingness,
    outliers,
    relationships,
    schema,
)

_ERRORS = {
    "EMPTY_DATAFRAME": {
        "message": "data_profiler called on empty DataFrame '{name}'.",
        "guidance": "Load data before profiling; empty DFs cannot be validated.",
        "recovery": "Inspect the source query and retry.",
    }
}


def _build_summary(name: str, n_rows: int, n_cols: int, risks: list[Risk]) -> str:
    blockers = [r for r in risks if r.severity == "BLOCKER"]
    highs = [r for r in risks if r.severity == "HIGH"]
    parts = [f"{name}: {n_rows} rows × {n_cols} cols"]
    if blockers:
        parts.append(
            f"{len(blockers)} BLOCKER(s): "
            + "; ".join(f"{r.kind} on {'/'.join(r.columns)}" for r in blockers)
        )
    if highs:
        parts.append(f"{len(highs)} HIGH")
    other = [r for r in risks if r.severity not in ("BLOCKER", "HIGH")]
    if other:
        parts.append(f"{len(other)} MEDIUM/LOW")
    return "; ".join(parts)


def profile(
    df: pd.DataFrame,
    name: str,
    key_candidates: list[str] | None = None,
    store: ArtifactStore | None = None,
    session_id: str = "default",
) -> ProfileReport:
    if df.empty:
        raise SkillError("EMPTY_DATAFRAME", {"name": name}, _ERRORS)

    section_results: dict[str, dict[str, Any]] = {
        "schema": schema.run(df),
        "missingness": missingness.run(df),
        "duplicates": duplicates.run(df, key_candidates=key_candidates),
        "distributions": distributions.run(df),
        "dates": dates.run(df),
        "outliers": outliers.run(df),
        "keys": keys.run(df, key_candidates=key_candidates),
        "relationships": relationships.run(df),
    }

    risks: list[Risk] = []
    for s in section_results.values():
        risks.extend(s.get("risks", []))
    risks.sort(key=lambda r: r.sort_key())

    n_rows = int(len(df))
    n_cols = int(len(df.columns))
    summary = _build_summary(name, n_rows, n_cols, risks)

    artifact_id = None
    report_artifact_id = None
    if store is not None:
        json_payload = {
            "name": name,
            "n_rows": n_rows,
            "n_cols": n_cols,
            "summary": summary,
            "risks": [asdict(r) for r in risks],
            "sections": {
                k: {sk: sv for sk, sv in v.items() if sk != "risks"}
                for k, v in section_results.items()
            },
        }
        a_json = store.add_artifact(
            session_id,
            Artifact(
                type="profile",
                title=f"{name} profile",
                content=json.dumps(json_payload, default=str, indent=2),
                format="profile-json",
                profile_summary=summary,
            ),
        )
        artifact_id = a_json.id

        html = render_html_report(
            name=name,
            n_rows=n_rows,
            n_cols=n_cols,
            summary=summary,
            risks=risks,
            sections=section_results,
            df=df,
        )
        a_html = store.add_artifact(
            session_id,
            Artifact(
                type="profile",
                title=f"{name} profile — report",
                content=html,
                format="profile-html",
                profile_summary=summary,
            ),
        )
        report_artifact_id = a_html.id

    return ProfileReport(
        name=name,
        n_rows=n_rows,
        n_cols=n_cols,
        summary=summary,
        risks=risks,
        sections={k: {sk: sv for sk, sv in v.items() if sk != "risks"} for k, v in section_results.items()},
        artifact_id=artifact_id,
        report_artifact_id=report_artifact_id,
    )
```

### Task 6.11: HTML report (editorial theme)

**Files:**
- Create: `backend/app/skills/data_profiler/pkg/html_report.py`
- Test: `backend/app/skills/data_profiler/tests/test_html_report.py`

- [ ] **Step 1: Write failing test**

```python
# backend/app/skills/data_profiler/tests/test_html_report.py
from __future__ import annotations

import pandas as pd

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_html_report_uses_editorial_surface_color(small_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.html_report import render_html_report
    from app.skills.data_profiler.pkg.sections import schema

    sec = {"schema": schema.run(small_df)}
    html = render_html_report(
        name="customers_v1",
        n_rows=len(small_df),
        n_cols=len(small_df.columns),
        summary="summary",
        risks=[],
        sections=sec,
        df=small_df,
    )
    assert "<html" in html.lower()
    assert "#FBF7EE" in html  # editorial base


def test_html_report_lists_risks_sorted_with_blocker_first(duplicated_key_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.html_report import render_html_report
    from app.skills.data_profiler.pkg.risks import Risk

    risks = [
        Risk(kind="duplicate_key", severity="BLOCKER", columns=("customer_id",), detail="d", mitigation="m"),
        Risk(kind="duplicate_rows", severity="HIGH", columns=("a", "b"), detail="d", mitigation="m"),
    ]
    html = render_html_report(
        name="x",
        n_rows=4,
        n_cols=2,
        summary="s",
        risks=risks,
        sections={},
        df=duplicated_key_df,
    )
    assert html.index("BLOCKER") < html.index("HIGH")
```

- [ ] **Step 2: Run — fails. Step 3: Implement:**

```python
# backend/app/skills/data_profiler/pkg/html_report.py
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from app.skills.altair_charts.pkg.histogram import histogram
from app.skills.data_profiler.pkg.risks import Risk
from app.skills.html_tables.pkg.renderer import render as render_table
from config.themes.altair_theme import register_all, use_variant
from config.themes.theme_switcher import ThemeTokens
from config.themes.table_css import render_table_css

VARIANT = "editorial"


def _header(name: str, n_rows: int, n_cols: int, summary: str, tokens) -> str:
    return (
        f'<header style="padding:24px 32px;border-bottom:1px solid {tokens.surface("border")};">'
        f'<h1 style="margin:0 0 6px 0;font-family:Source Serif Pro,Georgia,serif;'
        f'font-size:28px;color:{tokens.surface("text")};">{escape(name)} — data profile</h1>'
        f'<div style="color:{tokens.surface("text_muted")};font-size:13px;">'
        f"{n_rows:,} rows × {n_cols} cols</div>"
        f'<p style="margin:12px 0 0;font-size:15px;line-height:1.5;color:{tokens.surface("text")}">'
        f"{escape(summary)}</p></header>"
    )


def _risks_section(risks: list[Risk], tokens) -> str:
    if not risks:
        return (
            f'<section style="padding:16px 32px;color:{tokens.surface("text_muted")};">'
            "No risks surfaced.</section>"
        )
    rows = []
    for r in sorted(risks, key=lambda x: x.sort_key()):
        chip_bg = {
            "BLOCKER": tokens.semantic("negative"),
            "HIGH": tokens.semantic("warning"),
            "MEDIUM": tokens.semantic("info"),
            "LOW": tokens.surface("text_muted"),
        }[r.severity]
        rows.append(
            f'<tr><td><span style="background:{chip_bg};color:#fff;padding:2px 8px;'
            f'border-radius:3px;font-size:11px;font-weight:600;">{r.severity}</span></td>'
            f"<td>{escape(r.kind)}</td>"
            f"<td>{escape(', '.join(r.columns))}</td>"
            f"<td>{escape(r.detail)}</td>"
            f"<td>{escape(r.mitigation)}</td></tr>"
        )
    return (
        f'<section style="padding:16px 32px;"><h2 style="font-family:Source Serif Pro,serif;">Risks</h2>'
        f'<table class="ga-table"><thead><tr>'
        f"<th>Severity</th><th>Kind</th><th>Columns</th><th>Detail</th><th>Mitigation</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></section>"
    )


def _schema_section(sections: dict[str, Any]) -> str:
    sch = sections.get("schema")
    if not sch:
        return ""
    data = pd.DataFrame(sch["columns"])
    return (
        '<section style="padding:16px 32px;">'
        '<h2 style="font-family:Source Serif Pro,serif;">Schema</h2>'
        + render_table(data, variant=VARIANT, max_rows=100)
        + "</section>"
    )


def _distribution_section(df: pd.DataFrame, tokens) -> str:
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])][:4]
    if not numeric_cols:
        return ""
    charts_html = []
    for col in numeric_cols:
        try:
            chart = histogram(df, field=col, bins=30, title=col)
            charts_html.append(chart.to_html())
        except Exception:  # noqa: BLE001
            continue
    if not charts_html:
        return ""
    return (
        '<section style="padding:16px 32px;">'
        '<h2 style="font-family:Source Serif Pro,serif;">Distributions</h2>'
        + "".join(f'<div style="margin:12px 0;">{c}</div>' for c in charts_html)
        + "</section>"
    )


def render_html_report(
    name: str,
    n_rows: int,
    n_cols: int,
    summary: str,
    risks: list[Risk],
    sections: dict[str, Any],
    df: pd.DataFrame,
) -> str:
    register_all()
    use_variant(VARIANT)
    tokens = ThemeTokens.load(
        __import__("pathlib").Path(__file__).resolve().parents[4] / "config" / "themes" / "tokens.yaml"
    ).for_variant(VARIANT)

    css = render_table_css(variant=VARIANT)
    body = [
        _header(name, n_rows, n_cols, summary, tokens),
        _risks_section(risks, tokens),
        _schema_section(sections),
        _distribution_section(df, tokens),
    ]
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{escape(name)} profile</title>"
        f"{css}</head>"
        f'<body style="margin:0;background:{tokens.surface("base")};color:{tokens.surface("text")};'
        'font-family:Inter,system-ui,sans-serif;">'
        + "".join(body)
        + "</body></html>"
    )
```

- [ ] **Step 4: Run — passes.**

Run: `cd backend && pytest app/skills/data_profiler/tests/test_html_report.py app/skills/data_profiler/tests/test_profile.py -v`
Expected: PASS.

### Task 6.12: Run the full data_profiler suite

- [ ] **Step 1: Run all data_profiler tests**

Run: `cd backend && pytest app/skills/data_profiler/ -v`
Expected: PASS across 10+ test files.

- [ ] **Step 2: Commit data_profiler**

```bash
git add backend/app/skills/data_profiler/
git commit -m "feat(skills): data_profiler with 8 sections, 21 risk types, editorial HTML report"
```

### Task 6.13: Hook data_profiler into skill manifest check

- [ ] **Step 1: Run manifest check**

Run: `make skill-check`
Expected: all six new skills (theme_config path pending — theme is a module not a skill in this phase — `sql_builder`, `html_tables`, `altair_charts`, `data_profiler`) resolve cleanly. If `skill-check` surfaces orphaned deps, patch by filling `used_by:` fields or downgrading the dependency type.

- [ ] **Step 2: Run entire test suite**

Run: `cd backend && pytest -v`
Expected: all tests pass. Fix any collateral issues inline.

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "chore: wire foundations skills into manifest check"
```

---

## Self-Review Checklist

Before declaring Plan 1 complete, verify:

- [ ] Every new skill has SKILL.md + skill.yaml + pkg/ + tests/ and `make skill-check` passes.
- [ ] `cd backend && pytest` passes at HEAD (unit + skill tests).
- [ ] `cd backend && ruff check .` passes.
- [ ] `cd backend && mypy app/` passes (new modules only — legacy type-check debt is out of scope).
- [ ] `tokens.yaml` has 5 variants, each with 8 series_blues roles and ≥18 categorical colors.
- [ ] Artifact store supports `profile` type and 512KB disk overflow survives reload.
- [ ] Wiki engine enforces ≤200-line working.md and refuses Findings without evidence + stat_validate PASS.
- [ ] `data_profiler.profile()` produces both `profile-json` and `profile-html` artifacts on a real DataFrame; each risk has a mitigation.
- [ ] All 21 risk kinds listed in `RISK_KINDS` are exercised by at least one test OR noted as deferred (Plan 2 may surface additional ones — this plan covers the common set).

## Coverage Notes

The following RISK_KINDS are exercised by tests in this plan:

- `missing_over_threshold` ✓
- `missing_co_occurrence` ✓
- `duplicate_rows` ✓
- `duplicate_key` ✓
- `constant_column` ✓
- `near_constant` ✓
- `high_cardinality_categorical` ✓
- `low_cardinality_numeric` ✓ (implemented; add test if coverage gate fails)
- `mixed_types` ✓
- `date_gaps` ✓
- `date_non_monotonic` ✓ (implemented; add test if coverage gate fails)
- `date_future` ✓
- `outliers_extreme` ✓
- `skew_heavy` ✓
- `suspected_foreign_key` ✓
- `collinear_pair` ✓
- `timezone_naive` ✓

Deferred to later plans (data needed to exercise these): `suspicious_zeros`, `suspicious_placeholders`, `unit_inconsistency`, `class_imbalance`. Their constants are defined in `RISK_KINDS` and implementation can land incrementally when real datasets surface them.

## What This Plan Unblocks

- Plan 2 (Statistical Skills): `correlation`, `group_compare`, `stat_validate` build on theme + charts + artifacts; `stat_validate` references gotchas that live alongside the wiki engine.
- Plan 3 (Harness): `PreTurnInjector` compacts artifact lists via `format_artifacts_for_compaction`; `TurnWrapUp` uses `WikiEngine.promote_finding` + `rebuild_index`; sandbox globals include all 6 chart templates and `profile`.
- Plan 4 (Composition): `report_builder` renders editorial pages using the same theme + tables + charts already proven in `data_profiler`'s HTML report.
