---
title: Integrity Plugin D (hooks_check) — gate ε
status: design-approved
created: 2026-04-17
last_revised: 2026-04-17
owner: jay
parent_spec: 2026-04-16-integrity-system-design.md
gate: ε
depends_on:
  - 2026-04-17-integrity-plugin-e-design.md   # gate δ — shipped (consumes config/manifest.yaml inventory)
  - 2026-04-17-integrity-plugin-b-design.md   # gate β — shipped (engine + report aggregator)
---

# Plugin D — `hooks_check`

> Sub-spec for gate ε of the integrity system. Parent: `2026-04-16-integrity-system-design.md` §5.5. Single source of truth for Plugin D scope, design, and acceptance criteria. Edit in place; bump `last_revised`.

## 1. Goal

Codify, verify, and dry-run the project's `.claude/settings.json` hook contract:

`config/hooks_coverage.yaml` — committed declaration of "when files matching X change, a hook matching Y must run." Plugin D ingests this, parses `.claude/settings.json`, and emits three rules:

- `hooks.missing` (WARN) — coverage rule has no matching hook.
- `hooks.broken` (WARN) — configured hook exits non-zero in a sandboxed dry-run.
- `hooks.unused` (INFO) — configured hook is not justified by any coverage rule (and not on the `tolerated` allowlist).

The acceptance gate ε requires **five coverage rules** for the highest-churn paths (selected from a 30-day `git log --name-only` analysis), every rule satisfied by an existing hook, every hook dry-run green.

All execution builds on the engine, snapshots, and aggregator shipped at gates β/γ/δ. Plugin D shares Plugin E's plugin/builder/rule layering verbatim.

## 2. Non-goals

- **Hook authoring assistance.** Plugin D verifies the contract; it does not generate hook commands. Authoring is a human task.
- **Frontend/IDE hook coverage.** Only `.claude/settings.json` is in scope. VS Code `tasks.json`, husky, lint-staged, and pre-commit are out of scope.
- **End-to-end mutation tests.** Dry-run verifies exit code only; semantic correctness of the hook's effect (did it actually fix the lint?) is not asserted.
- **Cross-repo settings.** Single repository only. The plugin reads `<repo_root>/.claude/settings.json` and nothing else.
- **Auto-fix.** Drift is reported; gate ζ (Plugin F) handles fixes if any class is added there. None planned for MVP.
- **Path-glob enforcement at hook level.** Claude Code matches hooks by *tool name* (`Write|Edit`, etc.), not file path. Whether the hook command itself filters by path is the hook author's responsibility; we cannot verify that statically.

## 3. Decisions locked from brainstorm

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Coverage format | YAML, committed at `config/hooks_coverage.yaml`, deterministically sorted | Diffable; co-located with `config/integrity.yaml`; matches Plugin E pattern |
| Schema validator | Per-type module in `plugins/hooks_check/schemas/coverage.py` | Mirrors Plugin E `schemas/` layering; no new dep |
| Settings parser | Strict — raise on JSON errors or shape violations | `.claude/settings.json` is small + author-controlled; silent failure hides real bugs |
| Hook normalization | Flatten nested `hooks` blocks into `(event, matcher, command, source_index)` records | Single record shape is trivially indexable for matching + reporting |
| Coverage matching | event match + matcher overlap (regex-ish union) + `command_substring in command` | Hook authors compose tool matchers as `Write\|Edit\|MultiEdit`; substring is the cheap, robust match |
| Matcher overlap algorithm | Split on `\|`, treat each side as a literal token, intersection non-empty → overlap | Claude Code matchers are pipe-joined literal tool names; full regex parsing is unnecessary |
| Dry-run sandbox | Per-rule canonical fixture file in `plugins/hooks_check/fixtures/`; tempdir copy; `cwd=tempdir` | Hook can mutate the temp file freely; never touches the repo |
| Dry-run stdin payload | JSON shape Claude Code emits: `{"tool_name": "Write", "tool_input": {"file_path": "<temp>", "content": "<sample>"}}` | Mirrors actual hook invocation; commands that read stdin Just Work |
| Dry-run timeout | 10s default per hook; `subprocess.TimeoutExpired` → `hooks.broken` WARN with `"timed out after 10s"` | Bounds blast radius if a hook hangs |
| Dry-run env | Inherits `os.environ` minus secret-suspicious vars (`*_TOKEN`, `*_KEY`, `*_SECRET`); `PATH` preserved | Lets hooks find `uv`, `pnpm`, etc. without leaking creds |
| Concurrency | Hooks run sequentially | Keeps stderr capture clean; per-hook 10s × N hooks is fine for ≤20 hooks |
| `hooks.unused` policy | INFO only; require explicit allowlist via `tolerated:` to suppress | Hook authors add formatters everyone wants without trip-wiring |
| Plugin depends_on | `("config_registry",)` — soft dep; degrades if manifest absent | Honours upstream order; standalone-runnable via `--plugin hooks_check` |
| Plugin output artifact | `integrity-out/{date}/hooks_check.json` | Mirrors Plugin B/C/E pattern |
| Makefile target | `integrity-hooks` | Naming consistent with `integrity-doc`, `integrity-config` |
| `config/integrity.yaml` block | `hooks_check: { enabled: true, coverage_path, settings_path, dry_run_timeout_seconds, tolerated, disabled_rules }` | All knobs explicit; matches Plugin E config style |
| Settings.json multiple locations | MVP scans `<repo_root>/.claude/settings.json` only; `.claude/settings.local.json` and `~/.claude/settings.json` excluded with `INFO` note in the report | Predictable, repo-scoped; user-level / local overrides are out of scope |

## 4. Architecture

### 4.1 File layout

```
backend/app/integrity/plugins/hooks_check/
  __init__.py
  plugin.py                          # HooksCheckPlugin (mirrors ConfigRegistryPlugin shape)
  coverage.py                        # CoverageRule / CoverageDoc dataclasses + load/parse helpers
  settings_parser.py                 # parse `.claude/settings.json` → list[HookRecord]
  matching.py                        # rule↔hook overlap predicate (event + matcher + command_substring)
  dry_run.py                         # sandboxed hook invocation (subprocess + timeout + tempdir + stdin payload)
  fixtures/                          # canonical samples used by dry_run
    sample.py
    sample.tsx
    sample.md
    SKILL.md
    sample_skill.yaml
    sample_script.sh
  rules/
    __init__.py
    missing.py                       # hooks.missing (WARN)
    broken.py                        # hooks.broken (WARN)
    unused.py                        # hooks.unused (INFO)
  schemas/
    __init__.py
    coverage.py                      # CoverageSchemaValidator — shape-checks hooks_coverage.yaml
  tests/
    __init__.py
    conftest.py                      # tiny_repo fixture (with .claude/settings.json + hooks_coverage.yaml)
    test_coverage_load.py            # parsing + schema-violations
    test_settings_parser.py          # nested hooks → flat list; strict on JSON errors
    test_matching.py                 # event match + matcher overlap + substring; full edge-case grid
    test_dry_run.py                  # green hook → exit 0; broken hook → captured stderr; timeout → "timed out"
    test_dry_run_safety.py           # fixture sample is in tempdir, not repo; PATH preserved; secrets stripped
    test_rule_missing.py             # +/− fixture pair
    test_rule_broken.py              # +/− fixture pair (real subprocess, time-boxed)
    test_rule_unused.py              # +/− fixture pair; tolerated allowlist suppresses
    test_schemas_coverage.py         # one (+) and one (−) schema fixture
    test_plugin_integration.py       # full scan against tiny_repo with exact issue counts
    test_acceptance_gate.py          # 5-rule fixture mirroring real config — every rule satisfied, every hook green
```

### 4.2 Plugin shape

```python
@dataclass
class HooksCheckPlugin:
    name: str = "hooks_check"
    version: str = "1.0.0"
    depends_on: tuple[str, ...] = ("config_registry",)
    paths: tuple[str, ...] = (
        ".claude/settings.json",
        "config/hooks_coverage.yaml",
    )
    config: dict[str, Any] = field(default_factory=dict)
    today: date = field(default_factory=date.today)
    rules: dict[str, Rule] | None = None

    def scan(self, ctx: ScanContext) -> ScanResult:
        # 1. Load coverage doc (hooks_coverage.yaml). Schema-validate. Parse failures → ERROR-severity issue + early return.
        # 2. Parse settings.json into list[HookRecord]. Parse failures → ERROR-severity issue + early return.
        # 3. Run each enabled rule (missing / broken / unused) per-rule try/except.
        # 4. Emit IntegrityIssue list + write integrity-out/{date}/hooks_check.json.
```

`config` keys (read from `config/integrity.yaml::plugins.hooks_check`):

| Key | Default | Purpose |
|-----|---------|---------|
| `coverage_path` | `"config/hooks_coverage.yaml"` | Where the coverage doc lives |
| `settings_path` | `".claude/settings.json"` | Where the settings doc lives |
| `dry_run_timeout_seconds` | `10` | Per-hook wall-clock cap |
| `tolerated` | `[]` | Substrings allow-listed against `hooks.unused` (e.g., `["prettier", "black"]`) |
| `disabled_rules` | `[]` | Rule ids to skip |

### 4.3 Coverage doc schema

`config/hooks_coverage.yaml`:

```yaml
# Top-level keys: rules, tolerated. Generated/edited by hand.
rules:
  - id: docs_changed_runs_doc_audit
    description: "Markdown edits trigger doc_audit drift detection."
    when:
      paths: ["docs/**/*.md", "knowledge/**/*.md", "*.md"]
    requires_hook:
      event: PostToolUse
      matcher: "Write|Edit|MultiEdit"
      command_substring: "doc_audit"

  - id: backend_python_changed_runs_typecheck
    description: "Python edits trigger ruff + mypy."
    when:
      paths: ["backend/app/**/*.py", "backend/scripts/**/*.py"]
    requires_hook:
      event: PostToolUse
      matcher: "Write|Edit|MultiEdit"
      command_substring: "ruff"

  - id: frontend_changed_runs_lint
    description: "TS/TSX edits trigger eslint."
    when:
      paths: ["frontend/src/**/*.ts", "frontend/src/**/*.tsx"]
    requires_hook:
      event: PostToolUse
      matcher: "Write|Edit|MultiEdit"
      command_substring: "eslint"

  - id: skill_md_changed_runs_skill_check
    description: "SKILL.md edits run dependency manifest check."
    when:
      paths: ["backend/app/skills/**/SKILL.md", "backend/app/skills/**/skill.yaml"]
    requires_hook:
      event: PostToolUse
      matcher: "Write|Edit|MultiEdit"
      command_substring: "skill-check"

  - id: manifest_inputs_changed_runs_integrity_config
    description: "Edits to scripts, skill yaml, or top-level configs verify the manifest is in sync."
    when:
      paths:
        - "scripts/**"
        - "backend/app/skills/**/skill.yaml"
        - "pyproject.toml"
        - "package.json"
        - "Makefile"
        - ".claude/settings.json"
    requires_hook:
      event: PostToolUse
      matcher: "Write|Edit|MultiEdit"
      command_substring: "integrity --plugin config_registry"

# Hook commands matching any tolerated substring are exempt from hooks.unused.
tolerated:
  - "sb inject"          # superbrain context injection (UserPromptSubmit)
  - "sb reindex"         # superbrain reindex on ingest
```

### 4.4 Settings parser

```python
@dataclass(frozen=True)
class HookRecord:
    event: str          # "PreToolUse" | "PostToolUse" | "Stop" | "UserPromptSubmit" | ...
    matcher: str        # raw matcher string ("Write|Edit"); "" if absent
    command: str        # raw command string
    source_index: tuple[int, int, int]   # (event_block_idx, hook_block_idx, hook_idx) for traceability
```

Strict parsing (raises `ValueError` with path-prefixed messages):
- Top-level must be `{"hooks": {...}}` (or empty `{}` → empty list).
- Each event key maps to a `list[dict]`. Each dict has optional `matcher: str` and required `hooks: list[dict]`.
- Each inner hook is `{"type": "command", "command": str}`. Other types ignored with `INFO` note.

### 4.5 Matching predicate

```python
def matches(rule: CoverageRule, hook: HookRecord) -> bool:
    if hook.event != rule.requires_hook.event:
        return False
    rule_tokens = set(filter(None, rule.requires_hook.matcher.split("|")))
    hook_tokens = set(filter(None, hook.matcher.split("|"))) or {"*"}
    if rule_tokens and hook_tokens != {"*"} and rule_tokens.isdisjoint(hook_tokens):
        return False
    return rule.requires_hook.command_substring in hook.command
```

Empty hook matcher → universal (`*`); satisfies any rule. Empty rule matcher (no token constraint) → only event + substring need to match.

### 4.6 Dry-run sandbox

```python
@dataclass(frozen=True)
class DryRunResult:
    rule_id: str
    hook_command: str
    exit_code: int | None     # None on timeout
    stdout: str               # truncated to 4 KB
    stderr: str               # truncated to 4 KB
    duration_ms: int
    timed_out: bool
```

Per hook + per matched rule:
1. Pick the rule's first `when.paths` entry; map its extension to a fixture (`.py` → `sample.py`, `.tsx` → `sample.tsx`, `SKILL.md` → `SKILL.md`, etc.). Fall back to `sample.md`.
2. `mkdtemp()`; copy fixture into a path that mirrors the glob (e.g., `<temp>/backend/app/skills/foo/SKILL.md`).
3. Compose stdin JSON: `{"tool_name": tool, "tool_input": {"file_path": "<temp_path>", "content": "<fixture_text>"}}` where `tool` is `sorted(hook.matcher.split("|"))[0]` if the matcher is non-empty, else `"Write"`. Sorted to keep dry-runs deterministic across runs.
4. `subprocess.run([shell, "-c", hook.command], input=stdin, cwd=<temp>, env=<sanitized>, capture_output=True, timeout=N, text=True)`. Default shell `/bin/sh` (override via `SHELL` env if set).
5. Truncate stdout/stderr at 4 KB. Tempdir is unconditionally cleaned up.

Sanitized env strips keys matching `re.compile(r"_(TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL)$", re.I)` while preserving `PATH`, `HOME`, `LANG`, `LC_*`, `TMPDIR`, `SHELL`, `USER`, `LOGNAME`.

### 4.7 Rule signatures

```python
Rule = Callable[
    [ScanContext, dict[str, Any], date],   # ctx, plugin_cfg, today
    list[IntegrityIssue],
]
```

`plugin_cfg` carries:
- `_coverage`: `CoverageDoc`
- `_hooks`: `list[HookRecord]`
- `_tolerated`: `list[str]`
- `_dry_run_timeout`: `int`
- `_repo_root`: `Path`

Each rule operates independently against the parsed coverage doc + flat hook list. Only `hooks.broken` invokes `dry_run.run_for(...)`; the cost of re-parsing settings + coverage on every rule is zero (we did it once at plugin entry).

### 4.7.1 `hooks.missing`

For each rule in coverage doc, check if any `HookRecord` matches per §4.5. If not → emit:

```python
IntegrityIssue(
    rule="hooks.missing",
    severity="WARN",
    node_id=rule.id,
    location=rule.id,
    message=f"No hook matches coverage rule '{rule.id}': "
            f"need event={rule.requires_hook.event}, matcher overlapping "
            f"{rule.requires_hook.matcher!r}, command containing "
            f"{rule.requires_hook.command_substring!r}",
    evidence={
        "rule_paths": rule.when.paths,
        "required_event": rule.requires_hook.event,
        "required_matcher": rule.requires_hook.matcher,
        "required_substring": rule.requires_hook.command_substring,
    },
    fix_class=None,
)
```

### 4.7.2 `hooks.broken`

For each rule satisfied by ≥1 hook, dry-run the first matching hook (`§4.6`). If exit ≠ 0 or timeout → emit:

```python
IntegrityIssue(
    rule="hooks.broken",
    severity="WARN",
    node_id=rule.id,
    location=f"{rule.id}@.claude/settings.json#{hook.source_index}",
    message=(f"Hook for rule '{rule.id}' exited {result.exit_code}"
             if not result.timed_out
             else f"Hook for rule '{rule.id}' timed out after {timeout}s"),
    evidence={
        "command": hook.command,
        "exit_code": result.exit_code,
        "stderr_tail": result.stderr[-1024:],
        "duration_ms": result.duration_ms,
    },
    fix_class=None,
)
```

### 4.7.3 `hooks.unused`

For each `HookRecord`, check (a) command matches no rule's `command_substring`, AND (b) no entry in `tolerated` is a substring of the command. If both → emit INFO:

```python
IntegrityIssue(
    rule="hooks.unused",
    severity="INFO",
    node_id=f"hook:{hook.source_index}",
    location=f".claude/settings.json#{hook.source_index}",
    message=f"Hook is not justified by any coverage rule: {hook.command[:80]!r}",
    evidence={"event": hook.event, "matcher": hook.matcher, "command": hook.command},
    fix_class=None,
)
```

### 4.8 Failure modes

| Failure | Behavior |
|---------|----------|
| `config/hooks_coverage.yaml` missing | Plugin emits one ERROR issue (`hooks.coverage_missing`), zero rules run, exit clean |
| `hooks_coverage.yaml` schema invalid | One ERROR issue per failure (path-prefixed), early return |
| `.claude/settings.json` missing | All hooks treated as empty list → all coverage rules report `hooks.missing`; INFO note in report |
| `.claude/settings.json` JSON error | One ERROR issue (`hooks.settings_parse`) + early return on rules that need parsed hooks |
| Single rule raises | Caught at plugin level → one ERROR issue per rule; siblings continue (Plugin E pattern) |
| Single dry-run subprocess raises (e.g., shell missing) | Caught inside `dry_run.run_for` → emits broken-style WARN with `exception_type` evidence; doesn't crash the rule |

### 4.9 Output artifact shape

`integrity-out/{date}/hooks_check.json`:

```json
{
  "plugin": "hooks_check",
  "version": "1.0.0",
  "date": "2026-04-17",
  "rules_run": ["hooks.missing", "hooks.broken", "hooks.unused"],
  "failures": [],
  "coverage_summary": {
    "rules_total": 5,
    "rules_satisfied": 5,
    "hooks_total": 7,
    "hooks_dry_run_green": 7
  },
  "issues": [...]
}
```

`coverage_summary` is the headline number for the Health dashboard. `rules_satisfied / rules_total` is the gate-ε status indicator.

## 5. Five MVP coverage rules (chosen from 30-day churn)

`git log --since='30 days ago' --name-only` bucketed:

| Rank | Path bucket | 30d churn | Coverage rule |
|------|-------------|-----------|---------------|
| 1 | `backend/app/**/*.py` | 903 | `backend_python_changed_runs_typecheck` (ruff) |
| 2 | `frontend/src/**/*.{ts,tsx}` | 262 | `frontend_changed_runs_lint` (eslint) |
| 3 | `docs/**/*.md` | 131 | `docs_changed_runs_doc_audit` (doc_audit) |
| 4 | `backend/app/skills/**/SKILL.md` | 50 | `skill_md_changed_runs_skill_check` (skill-check) |
| 5 | `scripts/**` + `pyproject.toml` + `Makefile` etc. | 26 (combined) | `manifest_inputs_changed_runs_integrity_config` (integrity --plugin config_registry) |

### 5.1 Hook commands shipped to satisfy the gate

The plugin only verifies. Real `.claude/settings.json` hooks satisfying the rules ship in the same PR (so gate ε passes on first run):

```jsonc
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command",
            "command": "uv run ruff check --fix --quiet \"$CLAUDE_FILE_PATH\" 2>/dev/null || true" }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command",
            "command": "case \"$CLAUDE_FILE_PATH\" in *.ts|*.tsx) cd frontend && pnpm exec eslint --quiet \"../$CLAUDE_FILE_PATH\" 2>/dev/null || true ;; esac" }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command",
            "command": "case \"$CLAUDE_FILE_PATH\" in docs/*.md|knowledge/*.md|*.md) uv run python -m backend.app.integrity --plugin doc_audit --no-augment 2>/dev/null || true ;; esac" }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command",
            "command": "case \"$CLAUDE_FILE_PATH\" in *SKILL.md|*skill.yaml) make skill-check 2>/dev/null || true ;; esac" }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command",
            "command": "case \"$CLAUDE_FILE_PATH\" in scripts/*|*pyproject.toml|*Makefile|.claude/settings.json|*skill.yaml) uv run python -m backend.app.integrity --plugin config_registry --no-augment --check 2>/dev/null || true ;; esac" }
        ]
      }
    ]
  }
}
```

Trailing `|| true` keeps Claude Code's tool-use unblocked even if the lint command fails (lint warnings ≠ tool-use errors). The integrity dashboard remains the source of truth for whether the lint actually ran clean — `hooks.broken` is asserted via Plugin D dry-run, not by Claude Code's runtime.

The existing `sb inject` (UserPromptSubmit) and `sb reindex` (PostToolUse `sb_ingest|sb_promote_claim`) hooks are preserved verbatim; both go on the `tolerated` allowlist so `hooks.unused` doesn't flag them.

## 6. CLI / Make integration

Add to `Makefile`:

```makefile
integrity-hooks: ## Run only Plugin D (hooks_check) — gate ε
	uv run python -m backend.app.integrity --plugin hooks_check --no-augment
```

Add `hooks_check` to `KNOWN_PLUGINS` in `backend/app/integrity/__main__.py` and wire registration mirroring `config_registry`. Honor `--plugin hooks_check` standalone via the existing `depends_on=()` rewrite when upstream is skipped.

`config/integrity.yaml` block:

```yaml
  hooks_check:
    enabled: true
    coverage_path: "config/hooks_coverage.yaml"
    settings_path: ".claude/settings.json"
    dry_run_timeout_seconds: 10
    tolerated:
      - "sb inject"
      - "sb reindex"
    disabled_rules: []
```

## 7. Acceptance gate ε

All four conditions must hold on the real repository:

1. **Five rules defined**: `config/hooks_coverage.yaml` lists the five rules from §5 (verified by `test_acceptance_gate.py`).
2. **Every rule satisfied**: `make integrity-hooks` on the real repo emits zero `hooks.missing` issues.
3. **Every hook dry-runs green**: `make integrity-hooks` emits zero `hooks.broken` issues.
4. **Exit zero**: `make integrity-hooks` returns 0 on a clean checkout (no WARN/ERROR-severity gate failures from this plugin).

`hooks.unused` may emit INFO; it does not gate ε. The intent is to surface tolerated formatters or new sb-style hooks without blocking the gate.

## 8. Testing

| Layer | Coverage |
|-------|----------|
| Coverage parser | Schema-valid load; missing required keys raise; duplicate ids raise; empty `rules:` raises |
| Settings parser | Nested → flat normalization; events with no matcher → `matcher=""`; `type != "command"` skipped with INFO; JSON parse error raises with byte offset |
| Matching predicate | Event mismatch → false; matcher disjoint → false; substring absent → false; universal hook (matcher="") satisfies any tool; pipe-token overlap covers `Write\|Edit` ⊇ `Write\|Edit\|MultiEdit` |
| Dry-run | Green hook (echo 0) → exit 0; broken hook (`false`) → exit 1 captured; timeout (`sleep 30`) → `timed_out=True`; missing shell raises caught + reported |
| Dry-run safety | Tempdir created and cleaned; secrets stripped from env; PATH preserved; sample fixture not modified in repo |
| `hooks.missing` | +/− pair (rule with no hook → 1 issue; rule with matching hook → 0 issues) |
| `hooks.broken` | +/− pair (real subprocess) |
| `hooks.unused` | +/− pair; `tolerated:` substring suppresses |
| Schema validator | One valid + one invalid coverage doc fixture |
| Plugin integration | Full scan of tiny_repo; assert exact issue counts and ordering |
| Acceptance gate | Synthetic 5-rule fixture mirroring §5; every rule satisfied; every hook green; assert `coverage_summary.rules_satisfied == 5` |

`tests/conftest.py::tiny_repo` extends Plugin E's fixture with:
- `.claude/settings.json` with 3 hooks (1 satisfies a rule, 1 broken, 1 unused)
- `config/hooks_coverage.yaml` with 3 rules (1 satisfied, 1 missing, 1 satisfied-but-broken)
- `config/integrity.yaml` extended with `hooks_check.enabled: true`
- `tolerated: ["sb"]` so the third hook (sb-style) is tolerated and not flagged unused

## 9. Sequencing

| Step | Output | Gate |
|------|--------|------|
| 1 | Write coverage doc + schema validator | `test_coverage_load.py`, `test_schemas_coverage.py` green |
| 2 | Write settings parser | `test_settings_parser.py` green |
| 3 | Write matching predicate | `test_matching.py` green |
| 4 | Write dry-run sandbox + canonical fixtures | `test_dry_run.py`, `test_dry_run_safety.py` green |
| 5 | Implement three rules | per-rule +/− tests green |
| 6 | Wire `HooksCheckPlugin` orchestration | `test_plugin_integration.py` green |
| 7 | Wire CLI/Make + `config/integrity.yaml` | `make integrity-hooks` exits 0 against real repo |
| 8 | Add 5 hooks to `.claude/settings.json` + 5 rules to `config/hooks_coverage.yaml` | `test_acceptance_gate.py` green; gate ε passes |
| 9 | `docs/log.md` entry under `[Unreleased]` | Changelog reflects the user-visible new check + new files |

## 10. Migration & rollback

- Adding the plugin is purely additive; no existing behavior changes.
- `config/integrity.yaml::plugins.hooks_check.enabled: false` disables the plugin without removing files (mirrors Plugin E rollback).
- Removing the plugin in the future: delete the directory, remove the `KNOWN_PLUGINS` entry, drop the `integrity.yaml` block, drop the Makefile target. `config/hooks_coverage.yaml` may be left in place (harmless) or deleted.

## 11. Open questions (deferred to future sub-spec)

- **Hook coverage for non-Claude tools** (husky, pre-commit). Add `provider:` field to `requires_hook` in v2.
- **Path-glob enforcement.** Only feasible if hook commands declare which paths they handle (perhaps via a `# integrity-handles: <glob>` comment convention). Out of MVP.
- **Hook coverage telemetry.** Could integrate with the Health dashboard to show which rules trigger most often. Defer to autofix (Plugin F) or post-ε.

## 12. References

- Parent: `docs/superpowers/specs/2026-04-16-integrity-system-design.md` §5.5
- Plugin E (the layering template): `docs/superpowers/specs/2026-04-17-integrity-plugin-e-design.md`
- Engine + topo sort: `backend/app/integrity/engine.py`
- Plugin protocol: `backend/app/integrity/protocol.py`
- Existing settings: `.claude/settings.json`
- Existing make targets: `Makefile` lines 120-140
