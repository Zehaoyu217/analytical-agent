# Second Brain — Polish & Bridge Completion (Plan 7) Implementation Plan

> Historical note (2026-04-22): This plan was written when `second-brain` lived
> at `~/Developer/second-brain/`. The active codebase has since been moved into
> `claude-code-agent/components/second-brain`. Path references in this document
> are historical unless explicitly updated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the v1 second-brain → claude-code-agent bridge by shipping an interactive `sb init` wizard, a backend `second_brain` skill package (with sub-skills), a real `sb_promote_claim` tool handler, and user-facing skills under `.claude/skills/sb-*` inside the second-brain repo.

**Architecture:** Two repos. Wizard + user-facing skills land in `~/Developer/second-brain/`. Backend skill + real `sb_promote_claim` land in `~/Developer/claude-code-agent/`. All changes are additive and preserve graceful-degradation (no-op when `SECOND_BRAIN_ENABLED` is false). The promote-claim tool writes a new `claims/<slug>.md` directly into the KB filesystem and relies on the existing `sb reindex` PostToolUse hook to refresh derived indexes.

**Tech Stack:** Python 3.13, Click, Pydantic v2, ruamel.yaml, pytest + pytest-cov, Markdown-as-truth filesystem, FastAPI (tool dispatch on the CC-agent side).

---

## File Structure

### second-brain/ (the tool)

```
src/second_brain/
├── cli.py                       # extended: new `sb init` top-level command
└── init_wizard/                 # NEW
    ├── __init__.py
    ├── scaffold.py              # creates ~/second-brain/ tree + starter README
    ├── interview.py             # prompts → Habits overrides
    └── wiring.py                # prints CC-agent hook-wiring instructions

.claude/skills/                  # NEW (user-facing, discoverable by Claude Code)
├── sb-daily/SKILL.md
├── sb-research/SKILL.md
└── sb-claim-review/SKILL.md

tests/test_init_wizard.py        # NEW — wizard interview + scaffold tests
tests/test_cli_init.py           # NEW — `sb init` CLI smoke tests
```

### claude-code-agent/ (the consumer)

```
backend/app/skills/second_brain/
├── SKILL.md                     # NEW — Level-1 Reference skill, <200 lines
├── schema.md                    # NEW — sub-skill: schema fields + ids
└── reasoning-patterns.md        # NEW — sub-skill: walk/load/search idioms

backend/app/tools/sb_tools.py    # MODIFIED — replace stub sb_promote_claim
backend/tests/tools/test_sb_tools.py  # MODIFIED — real promote-claim tests
```

Each unit has one responsibility:
- `init_wizard/scaffold.py` owns directory creation — nothing else.
- `init_wizard/interview.py` owns prompt → habits-dict transformation — no I/O beyond `click.prompt`.
- `init_wizard/wiring.py` owns printing CC-agent integration hints.
- `sb_tools.sb_promote_claim` owns serialising a claim record and writing the file. Reindex is out-of-band (PostToolUse).

---

## Task 1: Config.readme_path + wizard scaffolding skeleton

**Files:**
- Modify: `second-brain/src/second_brain/config.py`
- Create: `second-brain/src/second_brain/init_wizard/__init__.py`
- Test: `second-brain/tests/test_init_wizard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_init_wizard.py
from __future__ import annotations

from pathlib import Path

from second_brain.config import Config


def test_config_exposes_readme_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path / "sb"))
    cfg = Config.load()
    assert cfg.readme_path == Path(str(tmp_path / "sb")) / "README.md"


def test_init_wizard_package_importable():
    from second_brain import init_wizard  # noqa: F401
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /Users/jay/Developer/second-brain && .venv/bin/pytest tests/test_init_wizard.py -x
```

Expected: ImportError on `init_wizard` + AttributeError on `readme_path`.

- [ ] **Step 3: Implement**

Append to `src/second_brain/config.py`:

```python
    @property
    def readme_path(self) -> Path:
        return self.home / "README.md"
```

Create `src/second_brain/init_wizard/__init__.py`:

```python
"""Interactive `sb init` wizard: scaffold layout + capture habits."""
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_init_wizard.py -x
```

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/config.py src/second_brain/init_wizard tests/test_init_wizard.py
git commit -m "chore(sb): add readme_path + init_wizard package scaffolding"
```

---

## Task 2: Scaffold module — create_tree()

**Files:**
- Create: `second-brain/src/second_brain/init_wizard/scaffold.py`
- Test: `second-brain/tests/test_init_wizard_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_init_wizard_scaffold.py
from __future__ import annotations

from second_brain.config import Config
from second_brain.init_wizard.scaffold import ScaffoldResult, create_tree


def test_create_tree_creates_all_expected_dirs(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()

    result = create_tree(cfg)

    assert isinstance(result, ScaffoldResult)
    assert cfg.sources_dir.is_dir()
    assert cfg.claims_dir.is_dir()
    assert cfg.inbox_dir.is_dir()
    assert cfg.sb_dir.is_dir()
    assert cfg.proposals_dir.is_dir()
    assert cfg.log_path.is_file()
    assert cfg.readme_path.is_file()
    assert "second-brain" in cfg.readme_path.read_text().lower()
    assert result.created_dirs >= 5
    assert result.created_files >= 2


def test_create_tree_is_idempotent(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    # Seed with a non-default readme; re-running must preserve it.
    create_tree(cfg)
    cfg.readme_path.write_text("custom user readme", encoding="utf-8")

    result = create_tree(cfg)
    assert cfg.readme_path.read_text() == "custom user readme"
    # Second call should report zero new files because everything already exists.
    assert result.created_files == 0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/pytest tests/test_init_wizard_scaffold.py -x
```

- [ ] **Step 3: Implement**

Create `src/second_brain/init_wizard/scaffold.py`:

```python
"""Create the `~/second-brain/` tree. Idempotent: never overwrites user content."""
from __future__ import annotations

from dataclasses import dataclass

from second_brain.config import Config

_README_TEMPLATE = """# Second Brain

Personal knowledge base. Markdown is source of truth.

```
~/second-brain/
  .sb/               # derived indexes (gitignored)
  sources/           # one folder per ingested artefact
  claims/            # atomic claims (*.md)
  inbox/             # drop files for `sb ingest`
  proposals/         # habit-learning proposals
  log.md             # append-only activity log
```

Run `sb --help` for commands. See the second-brain repo README for the full guide.
"""

_LOG_HEADER = "# Second Brain — activity log\n\n"


@dataclass(frozen=True)
class ScaffoldResult:
    created_dirs: int
    created_files: int


def create_tree(cfg: Config) -> ScaffoldResult:
    """Create directories and starter files. Existing content is preserved."""
    dirs = [
        cfg.home,
        cfg.sb_dir,
        cfg.sources_dir,
        cfg.claims_dir,
        cfg.inbox_dir,
        cfg.proposals_dir,
    ]
    created_dirs = 0
    for d in dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=False)
            created_dirs += 1
        elif not d.is_dir():
            raise RuntimeError(f"{d} exists but is not a directory")

    created_files = 0
    if not cfg.readme_path.exists():
        cfg.readme_path.write_text(_README_TEMPLATE, encoding="utf-8")
        created_files += 1
    if not cfg.log_path.exists():
        cfg.log_path.write_text(_LOG_HEADER, encoding="utf-8")
        created_files += 1

    return ScaffoldResult(created_dirs=created_dirs, created_files=created_files)
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_init_wizard_scaffold.py -x
```

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/init_wizard/scaffold.py tests/test_init_wizard_scaffold.py
git commit -m "feat(sb): init wizard scaffold module — idempotent tree creation"
```

---

## Task 3: Interview module — non-interactive defaults path

**Files:**
- Create: `second-brain/src/second_brain/init_wizard/interview.py`
- Test: `second-brain/tests/test_init_wizard_interview.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_init_wizard_interview.py
from __future__ import annotations

from second_brain.habits import Habits
from second_brain.init_wizard.interview import InterviewAnswers, run_interview


def test_run_interview_non_interactive_yields_defaults():
    answers = run_interview(interactive=False)
    assert isinstance(answers, InterviewAnswers)
    assert answers.to_habits() == Habits.default()


def test_interview_answers_apply_density_override():
    answers = InterviewAnswers(default_density="dense")
    habits = answers.to_habits()
    assert habits.extraction.default_density == "dense"


def test_interview_answers_apply_retrieval_prefer():
    answers = InterviewAnswers(retrieval_prefer="sources")
    habits = answers.to_habits()
    assert habits.retrieval.prefer == "sources"


def test_interview_answers_apply_taxonomy_roots():
    answers = InterviewAnswers(taxonomy_roots=["papers/ml", "notes/personal"])
    habits = answers.to_habits()
    assert habits.taxonomy.roots == ["papers/ml", "notes/personal"]
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/pytest tests/test_init_wizard_interview.py -x
```

- [ ] **Step 3: Implement**

Create `src/second_brain/init_wizard/interview.py`:

```python
"""Turn interactive prompts into `Habits` overrides. Interactive logic is kept
thin — prompts live here; the scaffold + CLI layers stay decoupled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import click

from second_brain.habits import Habits
from second_brain.habits.schema import Density, RetrievalPref


@dataclass(frozen=True)
class InterviewAnswers:
    taxonomy_roots: list[str] | None = None
    default_density: Density | None = None
    retrieval_prefer: RetrievalPref | None = None
    injection_scope: Literal["claims", "sources", "both"] | None = None
    autonomy_extract: Literal["auto", "hitl"] | None = None

    def to_habits(self) -> Habits:
        base = Habits.default()
        patch: dict = {}

        if self.taxonomy_roots is not None:
            patch["taxonomy"] = base.taxonomy.model_copy(update={"roots": list(self.taxonomy_roots)})
        if self.default_density is not None:
            patch["extraction"] = base.extraction.model_copy(update={"default_density": self.default_density})
        if self.retrieval_prefer is not None:
            patch["retrieval"] = base.retrieval.model_copy(update={"prefer": self.retrieval_prefer})
        if self.injection_scope is not None:
            patch["injection"] = base.injection.model_copy(update={"scope": self.injection_scope})
        if self.autonomy_extract is not None:
            patch["autonomy"] = base.autonomy.model_copy(update={"extract": self.autonomy_extract})

        return base.model_copy(update=patch) if patch else base


def run_interview(interactive: bool = True) -> InterviewAnswers:
    """Run the wizard interview. Defaults-only when `interactive=False`."""
    if not interactive:
        return InterviewAnswers()

    click.echo("Second Brain setup — answer a few questions (press Enter for defaults).\n")

    taxonomy_input = click.prompt(
        "Taxonomy roots (comma-separated, blank = defaults)",
        default="",
        show_default=False,
    ).strip()
    taxonomy_roots = (
        [r.strip() for r in taxonomy_input.split(",") if r.strip()]
        if taxonomy_input
        else None
    )

    density = click.prompt(
        "Default claim-extraction density",
        type=click.Choice(["sparse", "moderate", "dense"]),
        default="moderate",
    )

    prefer = click.prompt(
        "Retrieval preference",
        type=click.Choice(["claims", "sources", "balanced"]),
        default="claims",
    )

    scope = click.prompt(
        "Prompt-injection scope",
        type=click.Choice(["claims", "sources", "both"]),
        default="claims",
    )

    autonomy = click.prompt(
        "Claim extraction autonomy",
        type=click.Choice(["auto", "hitl"]),
        default="auto",
    )

    return InterviewAnswers(
        taxonomy_roots=taxonomy_roots,
        default_density=density,
        retrieval_prefer=prefer,
        injection_scope=scope,
        autonomy_extract=autonomy,
    )
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_init_wizard_interview.py -x
```

Note: if `Habits.default().injection` doesn't have a `scope` field, the plan's `injection_scope` is still valid because Pydantic's `model_copy(update={"scope": ...})` only applies when the field exists. Inspect `InjectionHabits` in `habits/schema.py` and adjust the `patch` key to the actual field name (e.g., `retrieval_scope`). This is the one explicitly-allowed deviation for this task.

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/init_wizard/interview.py tests/test_init_wizard_interview.py
git commit -m "feat(sb): init wizard interview — prompts to Habits overrides"
```

---

## Task 4: Wiring module — prints CC-agent hook instructions

**Files:**
- Create: `second-brain/src/second_brain/init_wizard/wiring.py`
- Test: `second-brain/tests/test_init_wizard_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_init_wizard_wiring.py
from __future__ import annotations

from second_brain.init_wizard.wiring import render_wiring_instructions


def test_render_wiring_instructions_mentions_cc_agent_hook_keys():
    text = render_wiring_instructions(home="/Users/jay/second-brain")

    assert "UserPromptSubmit" in text
    assert "PostToolUse" in text
    assert "sb inject" in text
    assert "sb reindex" in text
    assert "SECOND_BRAIN_HOME" in text
    assert "/Users/jay/second-brain" in text


def test_render_wiring_instructions_works_without_home():
    text = render_wiring_instructions()
    assert "SECOND_BRAIN_HOME" in text
    assert "UserPromptSubmit" in text
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/pytest tests/test_init_wizard_wiring.py -x
```

- [ ] **Step 3: Implement**

Create `src/second_brain/init_wizard/wiring.py`:

```python
"""Render claude-code-agent wiring instructions for a newly-initialised KB."""
from __future__ import annotations

_TEMPLATE = """\
claude-code-agent integration
-----------------------------

1. Export the data home in your shell so backend + hooks agree:

     export SECOND_BRAIN_HOME={home}

2. Symlink the `sb` CLI onto your PATH (if not already):

     ln -s "$(pwd)/.venv/bin/sb" ~/.local/bin/sb

3. Ensure the following hooks are present in
   `~/Developer/claude-code-agent/.claude/settings.json`:

     "UserPromptSubmit": [
       {{"command": "sb inject --k 5 --scope claims --max-tokens 800 --prompt-stdin"}}
     ],
     "PostToolUse": [
       {{"matcher": "sb_ingest|sb_promote_claim",
         "command": "sb reindex"}}
     ]

4. Restart the claude-code-agent backend so `SECOND_BRAIN_ENABLED` picks
   up the now-present `.sb/` directory.
"""


def render_wiring_instructions(home: str | None = None) -> str:
    home_txt = home or "$HOME/second-brain"
    return _TEMPLATE.format(home=home_txt)
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_init_wizard_wiring.py -x
```

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/init_wizard/wiring.py tests/test_init_wizard_wiring.py
git commit -m "feat(sb): init wizard wiring — CC-agent hook instructions"
```

---

## Task 5: `sb init` top-level CLI command

**Files:**
- Modify: `second-brain/src/second_brain/cli.py`
- Test: `second-brain/tests/test_cli_init.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_init.py
from __future__ import annotations

from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.habits.loader import habits_path, load_habits


def test_sb_init_defaults_scaffolds_tree_and_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))

    res = CliRunner().invoke(cli, ["init", "--defaults"])
    assert res.exit_code == 0, res.output

    cfg = Config.load()
    assert cfg.sources_dir.is_dir()
    assert cfg.claims_dir.is_dir()
    assert cfg.sb_dir.is_dir()
    assert habits_path(cfg).is_file()
    assert load_habits(cfg) is not None
    assert "UserPromptSubmit" in res.output
    assert "SECOND_BRAIN_HOME" in res.output


def test_sb_init_refuses_to_clobber_existing_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    runner = CliRunner()

    first = runner.invoke(cli, ["init", "--defaults"])
    assert first.exit_code == 0

    second = runner.invoke(cli, ["init", "--defaults"])
    # Scaffolding is idempotent, but habits.yaml must not be silently overwritten.
    assert second.exit_code != 0
    assert "habits.yaml already exists" in (second.output + (second.stderr or ""))


def test_sb_init_reconfigure_rewrites_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    runner = CliRunner()

    runner.invoke(cli, ["init", "--defaults"])
    res = runner.invoke(cli, ["init", "--reconfigure", "--defaults"])

    assert res.exit_code == 0
    assert habits_path(Config.load()).is_file()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
.venv/bin/pytest tests/test_cli_init.py -x
```

- [ ] **Step 3: Implement**

Append to `src/second_brain/cli.py`, after the existing imports:

```python
@cli.command(name="init")
@click.option("--defaults", "non_interactive", is_flag=True, default=False,
              help="Skip the interactive interview; accept every default.")
@click.option("--reconfigure", is_flag=True, default=False,
              help="Regenerate habits.yaml only (preserves existing directories).")
def _init(non_interactive: bool, reconfigure: bool) -> None:
    """Interactive setup: scaffold layout + capture habits + print wiring."""
    from second_brain.init_wizard.interview import run_interview
    from second_brain.init_wizard.scaffold import create_tree
    from second_brain.init_wizard.wiring import render_wiring_instructions

    cfg = Config.load()
    create_tree(cfg)

    hpath = habits_path(cfg)
    if hpath.exists() and not reconfigure:
        raise click.ClickException(
            f"habits.yaml already exists at {hpath}. "
            "Re-run with --reconfigure to rewrite it."
        )

    answers = run_interview(interactive=not non_interactive)
    save_habits(cfg, answers.to_habits())
    click.echo(f"wrote {hpath}")

    click.echo("")
    click.echo(render_wiring_instructions(home=str(cfg.home)))
```

- [ ] **Step 4: Run — expect PASS**

```bash
.venv/bin/pytest tests/test_cli_init.py -x
```

- [ ] **Step 5: Commit**

```bash
git add src/second_brain/cli.py tests/test_cli_init.py
git commit -m "feat(sb): add top-level \`sb init\` wizard command"
```

---

## Task 6: User-facing `.claude/skills/sb-daily/SKILL.md`

**Files:**
- Create: `second-brain/.claude/skills/sb-daily/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: sb-daily
description: Use when the user asks Claude to review today's ingested sources, triage the inbox, run `sb maintain`, or summarise recent claim activity in the second-brain KB.
---

# Second Brain — Daily Review

Use this skill when the user says things like "run my daily second-brain review", "triage today's inbox", or "what did I capture recently?".

## Workflow

1. Run `sb status` and `sb process-inbox` in parallel via the Bash tool. Report counts (ok/failed/quarantined).
2. Run `sb maintain --json` and surface:
   - Lint error/warning counts
   - Open contradictions (highlight any ≥ 5)
   - Stale abstract count
   - Whether analytics was rebuilt and any habit proposals
3. Run `sb stats --json`. Report the health score and its top two deductions.
4. If any proposals exist under `~/second-brain/proposals/`, list them and ask the user whether to apply (do NOT apply automatically).

## Do not

- Do not auto-answer habit proposals. Let the user confirm.
- Do not run `sb eval` in the daily flow — it's for CI / explicit requests.
- Do not push the git repo under `~/second-brain/` unless the user asks.

## See also

- `sb-research` — for targeted retrieval / reasoning flows.
- `sb-claim-review` — for promoting findings into claims.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/sb-daily/SKILL.md
git commit -m "docs(sb): add sb-daily skill for daily review workflow"
```

---

## Task 7: User-facing `.claude/skills/sb-research/SKILL.md`

**Files:**
- Create: `second-brain/.claude/skills/sb-research/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: sb-research
description: Use when the user wants Claude to answer a question grounded in the second-brain KB — retrieve claims, walk supports/contradicts chains, and cite source ids before proposing an answer.
---

# Second Brain — Research

Use this skill when the user asks a factual question and wants KB-grounded answers rather than general knowledge.

## Retrieval-first contract

1. Call `sb_search` (or run `sb search <query> --k 10`) first. Prefer `scope=claims`.
2. For each promising hit, call `sb_load` (or `sb load <id> --depth 1`) to pull in neighbours.
3. When a claim has `contradicts:` edges, always fetch both sides before asserting either.
4. Use `sb_reason` (or `sb reason <id> supports --depth 3`) to follow support chains when asked "why".
5. Cite every non-trivial claim by its `clm_*` id. Name the source id when quoting.

## Never

- Never answer from memory when the KB has hits — the KB represents the user's curated truth.
- Never silently pick one side of a contradiction. Surface both, then offer a recommendation.

## See also

- `sb-claim-review` — when research turns up a new atomic claim worth persisting.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/sb-research/SKILL.md
git commit -m "docs(sb): add sb-research skill for KB-grounded Q&A"
```

---

## Task 8: User-facing `.claude/skills/sb-claim-review/SKILL.md`

**Files:**
- Create: `second-brain/.claude/skills/sb-claim-review/SKILL.md`

- [ ] **Step 1: Write the skill**

```markdown
---
name: sb-claim-review
description: Use when the user asks Claude to promote a finding, research result, or wiki insight into a second-brain atomic claim (`claims/*.md`) — covers drafting, edge-binding, and calling `sb_promote_claim`.
---

# Second Brain — Claim Review & Promotion

Use this skill when a conversation produces an insight the user wants to persist as a durable claim.

## Workflow

1. Restate the finding as a single **atomic, falsifiable** sentence. If you can't, stop — it is not a claim.
2. Classify the claim:
   - `kind`: one of `empirical`, `theoretical`, `definitional`, `opinion`, `prediction`.
   - `confidence`: `low` | `medium` | `high` (match the evidence, not the user's tone).
3. Identify related claims in the KB via `sb_search` and choose `supports`, `contradicts`, or `refines` edges. Empty lists are fine.
4. Call `sb_promote_claim` with:
   - `statement` (the atomic sentence)
   - `abstract` (≤ 2 sentences, why this claim matters)
   - `kind`, `confidence`
   - `supports` / `contradicts` / `refines` (list of `clm_*` ids; omit if empty)
   - `taxonomy` (e.g. `notes/personal`, `papers/ml`)
   - optional `source_ids` — list of `src_*` anchors for provenance.
5. Confirm the written path back to the user.

## Do not

- Do not write claims directly with `Write`. Always go through `sb_promote_claim` so reindexing and logging happen correctly.
- Do not invent `clm_*` ids when specifying edges — only reference ids that `sb_search` returned.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/sb-claim-review/SKILL.md
git commit -m "docs(sb): add sb-claim-review skill for claim promotion"
```

---

## Task 9 (switch repos): Backend `second_brain/SKILL.md` (Level-1 Reference)

**Files:**
- Create: `claude-code-agent/backend/app/skills/second_brain/SKILL.md`

**Note:** This task modifies the `claude-code-agent` repo (not `second-brain`). `cd /Users/jay/Developer/claude-code-agent` before running commands.

- [ ] **Step 1: Write the skill**

Create `backend/app/skills/second_brain/SKILL.md` (<200 lines):

```markdown
---
name: second_brain
description: "[Reference] Second Brain KB — markdown-as-truth, graph-backed, BM25-indexed knowledge base. Use when the agent needs to retrieve grounded claims, walk typed edges, or write atomic findings into the KB via sb_search / sb_load / sb_reason / sb_ingest / sb_promote_claim."
---

# Second Brain skill — Level-1 reference

This is a **reference skill**. Load it when you need authoritative context about
the Second Brain KB (filesystem shape, tool contracts, edge semantics).

## The KB in one paragraph

Files on disk at `$SECOND_BRAIN_HOME` (default `~/second-brain/`). Sources live
in `sources/<slug>/_source.md` with `raw/*` attachments. Claims live in
`claims/<slug>.md` — one atomic statement per file. Edges (typed relations with
confidence) are derived from claim frontmatter and written to
`.sb/graph.duckdb`. A BM25 index lives at `.sb/kb.sqlite`. Contradictions are
first-class edges with `rationale:` notes, not merge conflicts.

## When to use tools vs shell

Inside claude-code-agent you have five JSON tools; prefer them over spawning
`sb` subprocesses during a conversation.

| Tool | Use for |
|---|---|
| `sb_search` | BM25 retrieval (natural prompt OK; OR-tokenised) |
| `sb_load` | Fetch a node + its 1-hop neighbourhood |
| `sb_reason` | Typed walk over `supports` / `refines` / `contradicts` |
| `sb_ingest` | Push a local file into the KB mid-conversation |
| `sb_promote_claim` | Persist a new atomic claim (writes `claims/<slug>.md`) |

All five return `{"ok": false, "error": "second_brain_disabled", ...}` when
`SECOND_BRAIN_ENABLED` is false. Don't treat that as failure — it means the user
hasn't initialised a KB.

## Grounding contract

1. When the user asks a factual question, always call `sb_search` first.
2. Cite claim ids (`clm_...`) when stating KB-derived facts.
3. Surface contradictions explicitly. Never silently pick one side.
4. Promote a finding into a claim only when it is atomic, falsifiable, and new.

## Sub-skills

- `schema.md` — full frontmatter schemas + id prefixes.
- `reasoning-patterns.md` — walk templates and anti-patterns.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/jay/Developer/claude-code-agent
git add backend/app/skills/second_brain/SKILL.md
git commit -m "docs(sb): add backend second_brain Level-1 reference skill"
```

---

## Task 10: Backend `second_brain/schema.md` sub-skill

**Files:**
- Create: `claude-code-agent/backend/app/skills/second_brain/schema.md`

- [ ] **Step 1: Write the sub-skill**

```markdown
---
name: second_brain_schema
description: "[Reference] Second Brain schemas — source + claim frontmatter, edge relations, id prefixes. Loaded only after parent `second_brain` skill."
---

# Schema reference

## ID prefixes

| Prefix | Kind |
|---|---|
| `src_` | Source (paper, blog, repo, note, url) |
| `clm_` | Claim (atomic statement) |

IDs are deterministic slugs of title + disambiguator; see the `slugs` module.

## Source frontmatter (`sources/<slug>/_source.md`)

```yaml
id: src_...
slug: "..."
title: "..."
kind: paper | blog | url | repo | note | other
ingested_at: <iso ts>
origin: { uri: "...", kind: "file" | "url" | "gh" }
content_hash: sha256-...
taxonomy: "papers/ml"   # optional
abstract: "..."         # optional
```

## Claim frontmatter (`claims/<slug>.md`)

```yaml
id: clm_...
statement: "..."                  # atomic, falsifiable
kind: empirical | theoretical | definitional | opinion | prediction
confidence: low | medium | high
scope: ""                          # optional: narrows applicability
supports: [clm_..., ...]           # outbound edges
contradicts: [clm_..., ...]
refines: [clm_..., ...]
extracted_at: <iso ts>
status: active | superseded | retracted | disputed
resolution: "..."                  # set when a contradiction is resolved
abstract: "..."
```

## Edge relations

| Relation | Semantics |
|---|---|
| `cites` | Claim cites a source (implicit via body markdown link) |
| `supports` | A supports B (strengthens) |
| `refines` | A refines B (narrows or improves precision) |
| `contradicts` | A contradicts B (open until `rationale`/`resolution` set) |

A contradiction is **resolved** when either side's claim has `resolution:` set
OR the corresponding edge row carries a non-empty `rationale`.
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/skills/second_brain/schema.md
git commit -m "docs(sb): add second_brain/schema sub-skill"
```

---

## Task 11: Backend `second_brain/reasoning-patterns.md` sub-skill

**Files:**
- Create: `claude-code-agent/backend/app/skills/second_brain/reasoning-patterns.md`

- [ ] **Step 1: Write the sub-skill**

```markdown
---
name: second_brain_reasoning_patterns
description: "[Reference] Walking the Second Brain graph — query templates, contradiction handling, depth heuristics."
---

# Reasoning patterns

## Pattern 1 — grounded answer

```
sb_search(query=<user question>, k=10, scope="claims")
→ for each top-3 hit:
    sb_load(node_id=hit.id, depth=1)
→ draft answer, cite clm_ ids
```

## Pattern 2 — "why" / causal chain

```
sb_search(query=<topic>, scope="claims") → pick root
sb_reason(start_id=<root>, walk="supports", direction="inbound", max_depth=3)
→ explain chain top-down
```

## Pattern 3 — contradiction audit

```
sb_search(query=<topic>) → pick seed
sb_reason(start_id=<seed>, walk="contradicts", max_depth=2)
→ list open contradictions (rationale empty)
→ surface to user; don't pick a winner unilaterally
```

## Depth heuristics

- `depth=0`: fact lookup, minimal context.
- `depth=1`: normal research question.
- `depth=2+`: "explain the chain", "audit the topic". Expensive — justify.

## Anti-patterns

- **Don't** answer from memory when `sb_search` returned hits. The KB is the
  user's curated truth; your memory is the fallback.
- **Don't** call `sb_ingest` on arbitrary URLs during conversation — it mutates
  disk. Ask the user first, unless explicitly told to scrape.
- **Don't** use `sb_promote_claim` to store conversational summaries. Claims
  must be atomic + falsifiable.
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/skills/second_brain/reasoning-patterns.md
git commit -m "docs(sb): add second_brain/reasoning-patterns sub-skill"
```

---

## Task 12: Real `sb_promote_claim` — write the tests

**Files:**
- Modify: `claude-code-agent/backend/tests/tools/test_sb_tools.py`

- [ ] **Step 1: Append failing tests**

Add to `backend/tests/tools/test_sb_tools.py`:

```python
def test_sb_promote_claim_no_op_when_disabled(monkeypatch, tmp_path):
    from app import config as app_config
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False)
    from app.tools import sb_tools

    res = sb_tools.sb_promote_claim({"statement": "x", "kind": "empirical", "confidence": "low"})
    assert res["ok"] is False
    assert res["error"] == "second_brain_disabled"


def test_sb_promote_claim_writes_claim_markdown(monkeypatch, tmp_path):
    from app import config as app_config
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True)
    monkeypatch.setattr(app_config, "SECOND_BRAIN_HOME", home)

    from app.tools import sb_tools

    res = sb_tools.sb_promote_claim({
        "statement": "Attention is all you need for sequence modelling.",
        "abstract": "Transformer beats RNN baselines on translation.",
        "kind": "empirical",
        "confidence": "high",
        "taxonomy": "papers/ml",
    })

    assert res["ok"] is True, res
    assert res["claim_id"].startswith("clm_")
    written = home / "claims" / res["filename"]
    assert written.is_file()
    body = written.read_text(encoding="utf-8")
    assert "Attention is all you need" in body
    assert "kind: empirical" in body
    assert "confidence: high" in body


def test_sb_promote_claim_rejects_missing_statement(monkeypatch, tmp_path):
    from app import config as app_config
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True)
    monkeypatch.setattr(app_config, "SECOND_BRAIN_HOME", home)

    from app.tools import sb_tools

    res = sb_tools.sb_promote_claim({"kind": "empirical", "confidence": "low"})
    assert res["ok"] is False
    assert "statement" in res["error"]


def test_sb_promote_claim_refuses_overwrite(monkeypatch, tmp_path):
    from app import config as app_config
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True)
    monkeypatch.setattr(app_config, "SECOND_BRAIN_HOME", home)

    from app.tools import sb_tools

    args = {
        "statement": "Gravity pulls mass toward mass.",
        "kind": "theoretical",
        "confidence": "high",
    }
    first = sb_tools.sb_promote_claim(args)
    second = sb_tools.sb_promote_claim(args)

    assert first["ok"] is True
    # Same statement → same slug → second call must fail explicitly.
    assert second["ok"] is False
    assert "exists" in second["error"].lower()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
cd /Users/jay/Developer/claude-code-agent
pytest backend/tests/tools/test_sb_tools.py::test_sb_promote_claim_writes_claim_markdown -x
```

---

## Task 13: Real `sb_promote_claim` — implementation

**Files:**
- Modify: `claude-code-agent/backend/app/tools/sb_tools.py`

- [ ] **Step 1: Replace the stub**

Replace the `sb_promote_claim` function in `backend/app/tools/sb_tools.py`:

```python
def sb_promote_claim(args: dict[str, Any]) -> dict[str, Any]:
    if not config.SECOND_BRAIN_ENABLED:
        return _disabled()

    from datetime import datetime, timezone
    from io import StringIO

    from ruamel.yaml import YAML
    from second_brain.schema.claim import ClaimConfidence, ClaimFrontmatter, ClaimKind

    statement = str(args.get("statement", "")).strip()
    if not statement:
        return {"ok": False, "error": "missing statement"}

    kind_raw = str(args.get("kind", "empirical"))
    conf_raw = str(args.get("confidence", "low"))
    try:
        kind = ClaimKind(kind_raw)
    except ValueError:
        return {"ok": False, "error": f"invalid kind: {kind_raw}"}
    try:
        confidence = ClaimConfidence(conf_raw)
    except ValueError:
        return {"ok": False, "error": f"invalid confidence: {conf_raw}"}

    supports = [str(x) for x in (args.get("supports") or [])]
    contradicts = [str(x) for x in (args.get("contradicts") or [])]
    refines = [str(x) for x in (args.get("refines") or [])]
    abstract = str(args.get("abstract", ""))
    taxonomy = str(args.get("taxonomy", ""))

    cfg = _cfg()
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify_claim(statement)
    claim_id = f"clm_{slug}"
    path = cfg.claims_dir / f"{slug}.md"
    if path.exists():
        return {"ok": False, "error": f"claim file exists: {path.name}"}

    fm = ClaimFrontmatter(
        id=claim_id,
        statement=statement,
        kind=kind,
        confidence=confidence,
        supports=supports,
        contradicts=contradicts,
        refines=refines,
        extracted_at=datetime.now(timezone.utc),
        abstract=abstract,
    )

    yaml = YAML()
    yaml.default_flow_style = False
    buf = StringIO()
    yaml.dump(fm.to_frontmatter_dict(), buf)
    fm_text = buf.getvalue().rstrip()

    body_lines = ["---", fm_text, "---", "", f"# {statement}", ""]
    if abstract:
        body_lines.extend([abstract, ""])
    if taxonomy:
        body_lines.extend([f"> taxonomy: `{taxonomy}`", ""])
    path.write_text("\n".join(body_lines), encoding="utf-8")

    return {
        "ok": True,
        "claim_id": claim_id,
        "filename": path.name,
        "path": str(path),
    }


def _slugify_claim(text: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        slug = "claim"
    return slug[:60].rstrip("-")
```

- [ ] **Step 2: Run — expect PASS**

```bash
pytest backend/tests/tools/test_sb_tools.py -x
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/tools/sb_tools.py backend/tests/tools/test_sb_tools.py
git commit -m "feat(sb): implement real sb_promote_claim tool handler"
```

---

## Task 14: Coverage & regression gate

- [ ] **Step 1: Run second-brain suite**

```bash
cd /Users/jay/Developer/second-brain
.venv/bin/pytest --cov=second_brain --cov-fail-under=75 --ignore=tests/test_ingest_pdf.py
```

Expected: PASS (≥75% coverage).

- [ ] **Step 2: Run claude-code-agent backend suite (scoped)**

```bash
cd /Users/jay/Developer/claude-code-agent
python -m pytest backend/tests/tools/test_sb_tools.py backend/tests/api/test_chat_api_sb_tools.py -x
```

Expected: PASS.

- [ ] **Step 3: If coverage drops below 75% in second-brain, add focused tests**

No commit if no changes needed.

---

## Task 15: Changelog + README bumps

**Files:**
- Modify: `second-brain/README.md`
- Modify: `claude-code-agent/docs/log.md`

- [ ] **Step 1: Bump second-brain README**

In `second-brain/README.md`:
- Change the status line from `v0.5` to `v0.6` (or whatever the current `vX.Y` says).
- Add a `sb init` command entry at the top of the Commands section:

```
### Setup
- `sb init [--defaults] [--reconfigure]` — interactive wizard: scaffold `~/second-brain/` + capture habits.
```

Commit:

```bash
cd /Users/jay/Developer/second-brain
git add README.md
git commit -m "docs(sb): document \`sb init\` wizard in README"
```

- [ ] **Step 2: Bump claude-code-agent changelog**

Append an entry to `claude-code-agent/docs/log.md` under `[Unreleased]` (create the section if it's not there):

```
- **second-brain bridge** — shipped real `sb_promote_claim` tool handler (claims now persist to `~/second-brain/claims/<slug>.md`), and added backend `second_brain/` Level-1 reference skill with `schema` + `reasoning-patterns` sub-skills.
```

Commit:

```bash
cd /Users/jay/Developer/claude-code-agent
git add docs/log.md
git commit -m "docs(sb): changelog — promote_claim + backend SKILL.md"
```

- [ ] **Step 3: DO NOT push**

The parent will push after all batches finish.

---

## Self-review notes (filled in before handoff)

- **Spec coverage:** Tasks 1–5 cover spec §11 (Wizard). Tasks 6–8 cover the "SB-facing skills" deliverable. Tasks 9–11 cover spec §12.1.1 (backend skill package). Tasks 12–13 cover spec §12.1.2 (real `sb_promote_claim`). Tasks 14–15 cover testing + changelog.
- **Placeholder scan:** All code blocks contain complete implementations. No TBD / TODO.
- **Type consistency:** `ClaimKind`, `ClaimConfidence`, `ClaimFrontmatter` all verified against `second-brain/src/second_brain/schema/claim.py`. `sb_promote_claim` uses `cfg.claims_dir` which already exists on `Config`.

## Execution handoff

Plan complete. Execute task-by-task, TDD, commit after each task with the exact messages given.
