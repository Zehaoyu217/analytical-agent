# Progressive Skill Exposure — Design Spec

**Date:** 2026-04-15
**Status:** Approved

---

## Problem

The current skill system loads all skills into the system prompt every turn — a flat list of
~18 entries with descriptions. This has two compounding problems:

1. **Token waste:** Every turn pays the full cost of every skill description, even for skills
   irrelevant to the current task.
2. **No hierarchy:** Skills that are logically related (e.g., correlation, distribution fit,
   group compare) are presented as equals to skills at a completely different level of
   abstraction. The agent gets no guidance on how to navigate the space.

The design goal is **progressive context exposure**: the agent sees only what it needs at each
step, and loads deeper content on demand.

---

## Mental Model

Skills are organized in a tree. The agent always sees the top of the tree (Level 1). Loading a
skill reveals its children. Loading a child reveals its children. The agent traverses the tree
as deeply as the task requires — no more.

```
System prompt (every turn):
  charting             [4 sub-skills]
  statistical_analysis [5 sub-skills]
  reporting            [3 sub-skills]
  data_profiler
  sql_builder
  analysis_plan

Agent loads statistical_analysis → sees body + sub-skill catalog:
  correlation
  distribution_fit
  group_compare
  stat_validate
  time_series

Agent loads correlation → sees body + sub-skill catalog:
  correlation_methodology  [Reference] — load only for algorithmic depth
```

Three levels are enough for current skills. The structure supports arbitrary depth if needed.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hierarchy representation | Nested directories | Filesystem IS the hierarchy — no metadata drift possible |
| Sub-skill catalog generation | System-driven (auto-appended) | Authors don't maintain child lists; registry generates from tree |
| Direct access to sub-skills by name | Permissive | Discovery is progressive; access is not gated. Power-user can name a sub-skill directly. |
| Level 3 (deep docs) format | Uniform SKILL.md | Same tool, same format at every depth. `references/` directory removed. |
| Hub rule | 2+ children required | A hub with one child is just indirection. Collapse to standalone Level 1. |
| Bootstrap import generation | Dynamic, from registry | Hard-coded import strings break on nesting. Registry generates correct paths at startup. |

---

## File System Structure

The directory nesting is the parent-child declaration. No metadata field needed.

```
backend/app/skills/
  charting/                        ← Level 1 hub
    SKILL.md
    bar_chart/                     ← Level 2
      SKILL.md
      pkg/
    altair_charts/                 ← Level 2
      SKILL.md
      pkg/
      altair_reference/            ← Level 3 reference
        SKILL.md

  statistical_analysis/            ← Level 1 hub
    SKILL.md
    correlation/                   ← Level 2
      SKILL.md
      pkg/
      correlation_methodology/     ← Level 3 reference
        SKILL.md
    distribution_fit/              ← Level 2
      SKILL.md
    group_compare/                 ← Level 2
      SKILL.md
    stat_validate/                 ← Level 2
      SKILL.md
    time_series/                   ← Level 2
      SKILL.md
      pkg/
      time_series_methodology/     ← Level 3 reference
        SKILL.md

  reporting/                       ← Level 1 hub
    SKILL.md
    report_builder/                ← Level 2
      SKILL.md
    dashboard_builder/             ← Level 2
      SKILL.md
    html_tables/                   ← Level 2
      SKILL.md

  data_profiler/                   ← Level 1 standalone (single child → no hub)
    SKILL.md
    pkg/

  sql_builder/                     ← Level 1 standalone
    SKILL.md
    pkg/

  analysis_plan/                   ← Level 1 standalone
    SKILL.md
    pkg/
```

**Rules:**
- A directory containing a `SKILL.md` is a skill.
- Sub-directories with their own `SKILL.md` are children.
- `pkg/` and `tests/` are never treated as child skills.
- Any skill directory that has children must have `__init__.py` so Python can traverse the
  module path to reach nested `pkg/` packages. This applies at every depth — not just Level 1
  hubs. A Level 2 skill that later gains children requires `__init__.py` added at that point.
- `references/` is removed entirely — all reference material becomes Level 3 SKILL.md files.

---

## Registry & Data Model

### SkillNode

Replaces the current `LoadedSkill` dataclass:

```python
@dataclass
class SkillNode:
    metadata: SkillMetadata      # name, version, description (no `level` field)
    instructions: str            # SKILL.md body, frontmatter stripped
    package_path: Path | None    # skill/pkg/ if it exists
    depth: int                   # 1 = Level 1, 2 = Level 2, etc. Computed, not stored.
    parent: SkillNode | None     # None for Level 1 skills
    children: list[SkillNode]    # empty for leaf skills
```

### SkillRegistry API

```python
class SkillRegistry:
    _roots: list[SkillNode]       # Level 1 skills only (ordered)
    _index: dict[str, SkillNode]  # flat lookup, all levels, by name

    def discover(self, root: Path) -> None
        # Recursively walks directories, builds tree + flat index

    def list_top_level(self) -> list[SkillNode]
        # Level 1 only — used by PreTurnInjector

    def get_skill(self, name: str) -> SkillNode | None
        # Flat lookup, any depth — permissive direct access

    def get_children(self, name: str) -> list[SkillNode]
        # Direct children — used to build sub-skill catalog in tool response

    def get_breadcrumb(self, name: str) -> list[str]
        # ["statistical_analysis", "correlation"] — shown in tool response header

    def generate_bootstrap_imports(self) -> list[str]
        # Auto-generates import strings from all pkg/ directories in the tree
        # Replaces hand-maintained sandbox_bootstrap.py import list
```

### Discovery Algorithm

```python
def _discover_recursive(self, dir: Path, parent: SkillNode | None, depth: int):
    skill_md = dir / "SKILL.md"
    if not skill_md.exists():
        return

    node = self._parse_skill(skill_md, dir, parent, depth)
    self._index[node.metadata.name] = node

    if parent is None:
        self._roots.append(node)
    else:
        parent.children.append(node)

    for subdir in sorted(dir.iterdir()):
        if subdir.is_dir() and subdir.name not in ("pkg", "tests", "evals"):
            self._discover_recursive(subdir, node, depth + 1)
```

### Frontmatter Schema

`level` field removed. Depth is computed from directory position, never authored.

**Operational skill:**
```yaml
---
name: correlation
description: Selects and runs the right correlation method based on data type and distribution.
version: 0.1
---
```

**Reference skill (Level 3):**
```yaml
---
name: correlation_methodology
description: "[Reference] Mathematical assumptions, edge cases, and numeric limits of
  Pearson/Spearman/Kendall. Load only when debugging unexpected results or needing
  algorithmic depth."
version: 0.1
---
```

`[Reference]` is authored in the `description` field — no new frontmatter field. The signal
appears wherever the description appears (sub-skill catalog, any tool response).

`skill.yaml` loses `references_path` tracking. `requires`, `packages`, and `errors` unchanged.

---

## Skill Tool Response Format

`skill("name")` returns three parts: breadcrumb (if nested), SKILL.md body, sub-skill catalog
(if children exist). Catalog is always system-generated — never authored.

**Hub skill (`skill("statistical_analysis")`):**
```
# statistical_analysis

[SKILL.md body]

---
## Sub-skills

- `correlation` — Selects and runs the right correlation method based on data type and distribution.
- `distribution_fit` — Fits parametric distributions; returns best-fit params and goodness-of-fit.
- `group_compare` — Compares means/medians across groups with the appropriate statistical test.
- `stat_validate` — Validates statistical assumptions before analysis runs.
- `time_series` — Decomposes and forecasts time-series; detects seasonality and trends.
```

**Nested skill with reference child (`skill("correlation")`):**
```
# statistical_analysis › correlation

[SKILL.md body]

---
## Sub-skills

- `correlation_methodology` — [Reference] Mathematical assumptions, edge cases, and numeric
  limits of each method. Load only if debugging unexpected results or needing algorithmic depth.
```

**Leaf skill, no children (`skill("sql_builder")`):**
```
# sql_builder

[SKILL.md body]
```

No trailing section. Clean.

**Rules:**
- Breadcrumb shown for any skill below Level 1.
- `## Sub-skills` section only rendered when children exist.
- One-line descriptions only in the catalog — agent is choosing, not reading.
- `[Reference]` prefix in description is authored; the system renders it as-is.

---

## System Prompt Injection

`PreTurnInjector._skill_menu()` renders Level 1 only.

```
## Skills

Use the `skill` tool to load any skill before using it. Hub skills expand into sub-skills
when loaded — read the sub-skill catalog before deciding which to use.

- `charting` — Visualization: bar, line, scatter, heatmap and more. [4 sub-skills]
- `statistical_analysis` — Tests and analysis: correlation, distribution fitting,
  group comparison, time-series. [5 sub-skills]
- `reporting` — Build HTML reports, dashboards, and formatted tables. [3 sub-skills]
- `data_profiler` — Full-dataset profile: schema, types, nulls, distributions, quality flags.
- `sql_builder` — Write and execute SQL queries against loaded datasets.
- `analysis_plan` — Generate a structured analysis plan before diving into data.
```

**Rules:**
- `[N sub-skills]` annotation on hub skills only. Standalone skills have no annotation.
- Two-sentence preamble explains the progressive model to the agent.
- No category grouping — list is short enough (<12 entries) that grouping adds noise.
- Estimated token reduction: **60-70% per turn** vs. current flat catalog.

---

## Dynamic Bootstrap Generation

`sandbox_bootstrap.py` is no longer hand-maintained. `SkillRegistry.generate_bootstrap_imports()`
walks the full tree, finds every skill with a `pkg/`, and produces the correct import path
based on actual directory depth:

```python
# Before nesting (depth=1):
"from app.skills.correlation.pkg import correlate"

# After nesting (depth=2):
"from app.skills.statistical_analysis.correlation.pkg import correlate"
```

The sandbox wiring calls `registry.generate_bootstrap_imports()` at startup. The file gets a
header comment: `# Auto-generated by SkillRegistry.generate_bootstrap_imports(). Do not edit.`

---

## Tooling

### make skill-new

```bash
make skill-new name=X                          # Level 1 standalone
make skill-new name=X parent=Y                 # Sub-skill under Y
make skill-new name=X parent=Y type=reference  # Reference skill — no pkg/, [Reference] template
```

`parent=Y` variant automatically:
- Creates `skills/Y/X/SKILL.md`
- Creates `skills/Y/X/pkg/__init__.py` (operational) or omits it (reference)
- Ensures `skills/Y/__init__.py` exists

### make skill-check additions

- All skills reachable from a Level 1 root (no orphaned directories)
- All hub directories have `__init__.py`
- No `level` field in any frontmatter
- All reference skills have `[Reference]` in description

---

## Migration Plan

### Phase 1 — Registry goes recursive (non-breaking)
Update `discover()` to walk recursively. Both flat and nested structures recognized simultaneously.
Add `generate_bootstrap_imports()` to registry. Sandbox not yet using it. Existing flat skills
continue working unchanged.

### Phase 2 — Create Level 1 hub SKILL.md files
Write `statistical_analysis/SKILL.md`, `charting/SKILL.md`, `reporting/SKILL.md`.
These are guidance docs — "here's when to use which sub-skill and why." No `pkg/` unless shared
utility code is needed.

### Phase 3 — Move existing skills into hierarchy
Use `git mv` to preserve history. Move each skill directory into its hub. Add `__init__.py`
at hub level. Switch sandbox to dynamic bootstrap generation.

### Phase 4 — Convert references/ to Level 3 SKILL.md files
Each `references/*.md` file becomes its own `skill_name_ref/SKILL.md` with `[Reference]`
description. Delete all `references/` directories.

### Phase 5 — Strip `level` field from all frontmatter
Automated pass. `make skill-check` validates none remain.

### Phase 6 — Update all documentation
Full doc sweep (see Documentation section below).

---

## Documentation Changes

| File | Change |
|------|--------|
| `docs/skill-creation.md` | Full rewrite: hub vs. standalone decision rule, reference skills, `make skill-new` options, `__init__.py` requirement for hubs, hub SKILL.md content guidelines |
| `docs/progressive-skill-exposure.md` | **New.** Mental model, catalog→load→sub-catalog flow, token impact, worked examples |
| `prompts/data_scientist.md` | Update skill section: progressive model, hub vs. leaf, what `[N sub-skills]` means |
| `CLAUDE.md` | Update architecture section: skill hierarchy, registry tree, dynamic bootstrap |
| `backend/app/harness/sandbox_bootstrap.py` | Add "do not edit" header; generation moved to registry |

---

## What Does Not Change

- `skill.yaml` structure (except removal of `references_path`)
- `requires`, `packages`, `error_templates` semantics
- Permissive direct access: `skill("any_name")` works regardless of depth
- `pkg/` directory convention inside skills
- `tests/` directory convention
- The `skill` tool name and call signature from the agent's perspective
- Frontend skill API endpoints (`/api/skills/manifest`, `/api/skills/{name}/detail`) —
  will need minor updates to expose tree structure, but not a blocker
