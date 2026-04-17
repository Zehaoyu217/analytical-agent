# Second Brain — Automation (Plan 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unattended operation to second-brain — batch inbox processing, ingest retry, filesystem watcher, and a nightly maintenance job — so the KB can absorb drops and self-heal without a human in the loop.

**Architecture:** Four additive commands on top of the existing `sb` CLI. `sb process-inbox` iterates `~/second-brain/inbox/` with a resumable manifest and per-file error isolation. `sb ingest --retry <slug>` reuses the original converter against preserved `raw/*` bytes for sources previously marked `kind: failed`. `sb watch` uses `watchdog` in a single-worker serial queue that debounces rapid drops and calls the same orchestrator. `sb maintain` is a one-shot pipeline invokable by launchd/cron that composes existing subsystems (lint → reconcile summary → index compact → stale abstract regen → habit-learning detector stub). No cross-coupling between the four — each is independently testable and shippable.

**Tech Stack:** Python 3.13, Click, `watchdog` (new dependency), existing `second_brain.ingest.orchestrator.ingest()`, existing `FtsStore` + `DuckStore`, pytest + fake-clock patterns already used in the repo.

---

## File Structure

**New files (second-brain repo):**
- `src/second_brain/inbox/__init__.py` — package marker.
- `src/second_brain/inbox/runner.py` — `InboxRunner` class: discover candidates, call `ingest()` per file, write `.sb/inbox_manifest.json` with per-file outcomes.
- `src/second_brain/ingest/retry.py` — `retry_source(slug, cfg)` function: load preserved `raw/*`, replay converter, overwrite `_source.md`.
- `src/second_brain/watch/__init__.py` — package marker.
- `src/second_brain/watch/queue.py` — `SerialQueue` with debounce window + dedupe key; synchronous drain for tests.
- `src/second_brain/watch/daemon.py` — `Watcher` that wires `watchdog.observers.Observer` to `SerialQueue` and a worker callback.
- `src/second_brain/maintain/__init__.py` — package marker.
- `src/second_brain/maintain/runner.py` — `MaintainRunner.run()` composing lint, conflict report, index compact (`VACUUM`/`CHECKPOINT`), stale-abstract scan, habit-learning stub hook.
- `src/second_brain/maintain/compact.py` — DuckDB/SQLite maintenance ops (`VACUUM`, `ANALYZE`, `CHECKPOINT`).

**Tests (all under `tests/`):**
- `tests/test_inbox_runner.py`
- `tests/test_ingest_retry.py`
- `tests/test_watch_queue.py`
- `tests/test_watch_daemon.py`
- `tests/test_maintain_runner.py`
- `tests/test_maintain_compact.py`
- `tests/test_cli_automation.py` — covers all four CLI surfaces end-to-end against tmp `SECOND_BRAIN_HOME`.

**Modified files:**
- `src/second_brain/cli.py` — four new commands (`process-inbox`, `ingest --retry`, `watch`, `maintain`).
- `src/second_brain/ingest/orchestrator.py` — factor out `_persist_failed_source()` so the retry path can recognize and replace it; add `resume=True` flag to `ingest()` for retry reuse.
- `src/second_brain/log.py` — add `EventKind.MAINTAIN`, `EventKind.WATCH`, `EventKind.RETRY`.
- `pyproject.toml` — add `watchdog>=4.0` to `[project.dependencies]`.
- `README.md` — document the four new commands + sample launchd/cron snippet.
- `docs/log.md` (claude-code-agent) — `[Unreleased]` entry under **Added**.

---

## Task 1: Add `watchdog` dependency + scaffolding packages

**Files:**
- Modify: `pyproject.toml`
- Create: `src/second_brain/inbox/__init__.py`
- Create: `src/second_brain/watch/__init__.py`
- Create: `src/second_brain/maintain/__init__.py`

- [ ] **Step 1: Add watchdog to dependencies**

Edit `pyproject.toml`, add `"watchdog>=4.0"` to the `dependencies` list (alphabetical).

- [ ] **Step 2: Create empty package markers**

```python
# src/second_brain/inbox/__init__.py
"""Inbox batch runner."""
```

```python
# src/second_brain/watch/__init__.py
"""Filesystem watcher daemon."""
```

```python
# src/second_brain/maintain/__init__.py
"""Nightly maintenance pipeline."""
```

- [ ] **Step 3: Sync + verify import**

Run: `cd /Users/jay/Developer/second-brain && uv sync --extra dev && python -c "import watchdog; from second_brain import inbox, watch, maintain; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add pyproject.toml uv.lock src/second_brain/inbox src/second_brain/watch src/second_brain/maintain
git commit -m "chore(sb): scaffold inbox/watch/maintain packages + watchdog dep"
```

---

## Task 2: Extend `EventKind` with automation verbs

**Files:**
- Modify: `src/second_brain/log.py`
- Test: `tests/test_log_eventkinds.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_log_eventkinds.py
from second_brain.log import EventKind


def test_automation_event_kinds_exist():
    assert EventKind.RETRY == "RETRY"
    assert EventKind.WATCH == "WATCH"
    assert EventKind.MAINTAIN == "MAINTAIN"
```

- [ ] **Step 2: Run test, verify failure**

Run: `cd /Users/jay/Developer/second-brain && pytest tests/test_log_eventkinds.py -v`
Expected: `AttributeError: RETRY` (or equivalent).

- [ ] **Step 3: Add enum members**

In `src/second_brain/log.py`, extend `EventKind`:

```python
class EventKind(StrEnum):
    AUTO = "AUTO"
    USER_OVERRIDE = "USER_OVERRIDE"
    SUGGEST = "SUGGEST"
    INGEST = "INGEST"
    REINDEX = "REINDEX"
    ERROR = "ERROR"
    RETRY = "RETRY"
    WATCH = "WATCH"
    MAINTAIN = "MAINTAIN"
```

- [ ] **Step 4: Run test, verify pass**

Run: `cd /Users/jay/Developer/second-brain && pytest tests/test_log_eventkinds.py -v`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/log.py tests/test_log_eventkinds.py
git commit -m "feat(sb): log.EventKind gains RETRY/WATCH/MAINTAIN"
```

---

## Task 3: `InboxRunner` — iterate + manifest

**Files:**
- Create: `src/second_brain/inbox/runner.py`
- Test: `tests/test_inbox_runner.py`

Behavior requirements:
- Scans `cfg.inbox_dir` non-recursively (one level — nested dirs ignored, user is expected to drop files; recursion can be added later).
- Skips dotfiles and files in an `ignore` set (empty by default).
- Per-file: build `IngestInput.from_path()`, call `ingest()`, capture success (slug) or error (message).
- On success: move file from `inbox/` to `inbox/.processed/<date>/<originalname>` (atomic rename, keeps inbox tidy but preserves artifact).
- On failure: leave file in `inbox/`, append to manifest as `failed`, increment retry-count in manifest (capped at 3).
- Manifest persisted at `cfg.sb_dir / "inbox_manifest.json"` with shape:
  ```json
  {
    "version": 1,
    "runs": [
      {"started_at": "...", "items": [{"path": "...", "status": "ok", "slug": "..."}, {"path": "...", "status": "failed", "error": "...", "attempts": 1}]}
    ]
  }
  ```
- Returns `InboxRunResult(ok: list[str], failed: list[InboxFailure])`.

- [ ] **Step 1: Write failing test — success path**

```python
# tests/test_inbox_runner.py
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.inbox.runner import InboxRunner


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "inbox").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_inbox_runner_ingests_note_and_moves_to_processed(sb_home: Path):
    note = sb_home / "inbox" / "idea.md"
    note.write_text("# Idea\n\nA test note.\n", encoding="utf-8")

    cfg = Config.load()
    result = InboxRunner(cfg).run()

    assert len(result.ok) == 1
    assert result.failed == []
    # Original moved under .processed/<date>/idea.md
    assert not note.exists()
    processed = list((sb_home / "inbox" / ".processed").rglob("idea.md"))
    assert len(processed) == 1
    # Source folder exists
    assert any((sb_home / "sources").iterdir())
    # Manifest written
    manifest = (sb_home / ".sb" / "inbox_manifest.json")
    assert manifest.exists()


def test_inbox_runner_failed_item_stays_in_inbox_and_records_error(sb_home: Path, monkeypatch: pytest.MonkeyPatch):
    bad = sb_home / "inbox" / "bad.xyz"
    bad.write_bytes(b"not ingestable")

    cfg = Config.load()
    result = InboxRunner(cfg).run()

    assert result.ok == []
    assert len(result.failed) == 1
    assert bad.exists(), "failed file must stay in inbox for manual triage"
    manifest = (sb_home / ".sb" / "inbox_manifest.json").read_text()
    assert "bad.xyz" in manifest
    assert "failed" in manifest


def test_inbox_runner_skips_dotfiles(sb_home: Path):
    (sb_home / "inbox" / ".DS_Store").write_text("noise")
    cfg = Config.load()
    result = InboxRunner(cfg).run()
    assert result.ok == []
    assert result.failed == []


def test_inbox_runner_caps_retry_attempts_at_3(sb_home: Path):
    """After 3 failed attempts across separate runs, item is marked quarantined."""
    bad = sb_home / "inbox" / "bad.xyz"
    bad.write_bytes(b"not ingestable")
    cfg = Config.load()
    for _ in range(4):
        InboxRunner(cfg).run()
    manifest = (sb_home / ".sb" / "inbox_manifest.json").read_text()
    # Last run should record quarantined=True once attempts>=3
    assert "quarantined" in manifest
```

- [ ] **Step 2: Run tests, verify failure**

Run: `cd /Users/jay/Developer/second-brain && pytest tests/test_inbox_runner.py -v`
Expected: `ModuleNotFoundError: second_brain.inbox.runner`

- [ ] **Step 3: Implement `InboxRunner`**

```python
# src/second_brain/inbox/runner.py
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from second_brain.config import Config
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest
from second_brain.log import EventKind, append_event

_MANIFEST_VERSION = 1
_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class InboxFailure:
    path: str
    error: str
    attempts: int
    quarantined: bool


@dataclass(frozen=True)
class InboxRunResult:
    ok: list[str] = field(default_factory=list)
    failed: list[InboxFailure] = field(default_factory=list)


class InboxRunner:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def run(self) -> InboxRunResult:
        self.cfg.inbox_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._load_manifest()
        items: list[dict] = []
        ok: list[str] = []
        failed: list[InboxFailure] = []

        for path in sorted(self._candidates()):
            prior = self._prior_attempts(manifest, path)
            try:
                source = IngestInput.from_path(path)
                folder = ingest(source, cfg=self.cfg)
            except (IngestError, Exception) as exc:  # noqa: BLE001 — converter can raise anything
                attempts = prior + 1
                quarantined = attempts >= _MAX_ATTEMPTS
                failure = InboxFailure(
                    path=str(path), error=str(exc), attempts=attempts, quarantined=quarantined
                )
                failed.append(failure)
                items.append(
                    {
                        "path": str(path),
                        "status": "failed",
                        "error": str(exc),
                        "attempts": attempts,
                        "quarantined": quarantined,
                    }
                )
                continue
            slug = folder.root.name
            ok.append(slug)
            self._move_to_processed(path)
            items.append({"path": str(path), "status": "ok", "slug": slug})

        manifest["runs"].append(
            {"started_at": datetime.now(UTC).isoformat(), "items": items}
        )
        self._save_manifest(manifest)
        return InboxRunResult(ok=ok, failed=failed)

    def _candidates(self) -> list[Path]:
        if not self.cfg.inbox_dir.exists():
            return []
        return [
            p
            for p in self.cfg.inbox_dir.iterdir()
            if p.is_file() and not p.name.startswith(".")
        ]

    def _move_to_processed(self, path: Path) -> None:
        date_dir = self.cfg.inbox_dir / ".processed" / datetime.now(UTC).strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(date_dir / path.name))

    def _manifest_path(self) -> Path:
        return self.cfg.sb_dir / "inbox_manifest.json"

    def _load_manifest(self) -> dict:
        p = self._manifest_path()
        if not p.exists():
            return {"version": _MANIFEST_VERSION, "runs": []}
        return json.loads(p.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest: dict) -> None:
        self.cfg.sb_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path().write_text(
            json.dumps(manifest, indent=2, sort_keys=False), encoding="utf-8"
        )

    def _prior_attempts(self, manifest: dict, path: Path) -> int:
        total = 0
        target = str(path)
        for run in manifest.get("runs", []):
            for item in run.get("items", []):
                if item.get("path") == target and item.get("status") == "failed":
                    total += 1
        return total
```

- [ ] **Step 4: Run tests, verify pass**

Run: `cd /Users/jay/Developer/second-brain && pytest tests/test_inbox_runner.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/inbox/runner.py tests/test_inbox_runner.py
git commit -m "feat(sb): InboxRunner with manifest + quarantine after 3 failures"
```

---

## Task 4: `sb process-inbox` CLI command

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_automation.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cli_automation.py
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "inbox").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_cli_process_inbox_reports_ok_and_failures(sb_home: Path):
    (sb_home / "inbox" / "idea.md").write_text("# Idea\n\nnote.\n")
    (sb_home / "inbox" / "bad.xyz").write_bytes(b"junk")

    runner = CliRunner()
    result = runner.invoke(cli, ["process-inbox"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "FAILED" in result.output
    assert "bad.xyz" in result.output


def test_cli_process_inbox_exits_0_on_empty_inbox(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["process-inbox"])
    assert result.exit_code == 0
    assert "empty" in result.output.lower()
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_cli_automation.py::test_cli_process_inbox_reports_ok_and_failures -v`
Expected: `Error: No such command 'process-inbox'` or non-zero exit.

- [ ] **Step 3: Implement the command**

Add to `src/second_brain/cli.py` after the `ingest` command:

```python
@cli.command(name="process-inbox")
def _process_inbox() -> None:
    """Ingest every file in ~/second-brain/inbox/ (non-recursive)."""
    from second_brain.inbox.runner import InboxRunner

    cfg = Config.load()
    result = InboxRunner(cfg).run()

    if not result.ok and not result.failed:
        click.echo("inbox empty")
        return
    click.echo(f"OK: {len(result.ok)}")
    for slug in result.ok:
        click.echo(f"  + {slug}")
    if result.failed:
        click.echo(f"FAILED: {len(result.failed)}")
        for fail in result.failed:
            tag = " [quarantined]" if fail.quarantined else ""
            click.echo(f"  x {fail.path} (attempts={fail.attempts}){tag} — {fail.error}")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_cli_automation.py::test_cli_process_inbox_reports_ok_and_failures tests/test_cli_automation.py::test_cli_process_inbox_exits_0_on_empty_inbox -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_automation.py
git commit -m "feat(sb): add \`sb process-inbox\` CLI command"
```

---

## Task 5: `retry_source(slug)` — replay converter against preserved raw/*

**Files:**
- Create: `src/second_brain/ingest/retry.py`
- Test: `tests/test_ingest_retry.py`

Design notes:
- `_source.md` for a failed ingest has `kind: failed` and `raw:` entries pointing at preserved bytes. Retry loads the first raw artifact, rebuilds an `IngestInput`, re-picks a converter, and re-runs. If successful, the old `_source.md` is overwritten with the new frontmatter + body. If still failing, we leave it and append a log entry.
- Slug is preserved across retry — never re-slug on retry, since callers/indexes may reference the old one.
- After success, emit `EventKind.RETRY` log entry.

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest_retry.py
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.ingest.base import SourceFolder
from second_brain.ingest.retry import RetryError, retry_source


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _make_failed_source(home: Path, slug: str, raw_filename: str, body: bytes) -> Path:
    folder = home / "sources" / slug
    (folder / "raw").mkdir(parents=True)
    raw_path = folder / "raw" / raw_filename
    raw_path.write_bytes(body)
    fm = {
        "id": slug,
        "title": slug,
        "kind": "failed",
        "content_hash": "sha256-placeholder",
        "raw": [{"path": f"raw/{raw_filename}", "kind": "note", "sha256": "x"}],
        "ingested_at": "2026-04-18T00:00:00Z",
    }
    dump_document(folder / "_source.md", fm, "retry me")
    return folder


def test_retry_source_succeeds_and_flips_kind(sb_home: Path):
    folder_path = _make_failed_source(
        sb_home, "note-sample-1", "note.md", b"# Good\n\nretryable content.\n"
    )
    cfg = Config.load()
    retry_source("note-sample-1", cfg=cfg)

    fm, body = load_document(folder_path / "_source.md")
    assert fm["kind"] == "note"
    assert "retryable content" in body


def test_retry_source_raises_when_slug_missing(sb_home: Path):
    cfg = Config.load()
    with pytest.raises(RetryError, match="not found"):
        retry_source("nope", cfg=cfg)


def test_retry_source_raises_when_raw_missing(sb_home: Path):
    folder = sb_home / "sources" / "broken"
    folder.mkdir()
    dump_document(
        folder / "_source.md",
        {"id": "broken", "title": "broken", "kind": "failed", "raw": []},
        "",
    )
    cfg = Config.load()
    with pytest.raises(RetryError, match="no raw"):
        retry_source("broken", cfg=cfg)
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_ingest_retry.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement retry**

```python
# src/second_brain/ingest/retry.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.orchestrator import DEFAULT_CONVERTERS, _pick_converter
from second_brain.log import EventKind, append_event
from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind


class RetryError(RuntimeError):
    pass


def retry_source(slug: str, *, cfg: Config) -> None:
    folder_path = cfg.sources_dir / slug
    if not folder_path.exists():
        raise RetryError(f"source not found: {slug}")
    fm, _body = load_document(folder_path / "_source.md")
    raw_entries = fm.get("raw") or []
    if not raw_entries:
        raise RetryError(f"no raw artifacts to replay for {slug}")
    first = raw_entries[0]
    raw_path = folder_path / first["path"]
    if not raw_path.exists():
        raise RetryError(f"raw file missing: {raw_path}")

    source = IngestInput.from_path(raw_path)
    converter = _pick_converter(source, DEFAULT_CONVERTERS)
    folder = SourceFolder(root=folder_path)
    artifacts = converter.convert(source, folder)  # may raise; propagate

    kind = SourceKind(converter.kind)
    title = (artifacts.title_hint or fm.get("title") or slug).strip()
    folder.write_manifest(artifacts.raw)

    new_fm = SourceFrontmatter(
        id=slug,
        title=title,
        kind=kind,
        authors=artifacts.authors_hint,
        year=artifacts.year_hint,
        source_url=fm.get("source_url"),
        tags=fm.get("tags", []) or [],
        ingested_at=datetime.now(UTC),
        content_hash=source.sha256,
        habit_taxonomy=fm.get("habit_taxonomy"),
        raw=[RawArtifact(path=r.path, kind=r.kind, sha256=r.sha256) for r in artifacts.raw],
        cites=fm.get("cites", []) or [],
        related=fm.get("related", []) or [],
        supersedes=fm.get("supersedes", []) or [],
        abstract=fm.get("abstract", "") or "",
    )
    dump_document(
        folder.source_md, new_fm.to_frontmatter_dict(), artifacts.processed_body
    )
    append_event(
        kind=EventKind.RETRY, op=f"retry.{kind.value}", subject=slug, value=source.origin, home=cfg.home
    )
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_ingest_retry.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/ingest/retry.py tests/test_ingest_retry.py
git commit -m "feat(sb): add retry_source() to replay converter on preserved raw/*"
```

---

## Task 6: `sb ingest --retry <slug>` CLI option

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_automation.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_cli_automation.py`:

```python
from second_brain.frontmatter import dump_document


def test_cli_ingest_retry_rehydrates_failed_source(sb_home: Path):
    folder = sb_home / "sources" / "note-sample-1"
    (folder / "raw").mkdir(parents=True)
    (folder / "raw" / "note.md").write_text("# Good\n\nbody.\n")
    dump_document(
        folder / "_source.md",
        {
            "id": "note-sample-1",
            "title": "note-sample-1",
            "kind": "failed",
            "content_hash": "sha256-x",
            "raw": [{"path": "raw/note.md", "kind": "note", "sha256": "x"}],
        },
        "placeholder",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", "--retry", "note-sample-1"])
    assert result.exit_code == 0, result.output
    assert "retry ok" in result.output.lower()
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_cli_automation.py::test_cli_ingest_retry_rehydrates_failed_source -v`
Expected: `Error: Got unexpected extra argument` or similar.

- [ ] **Step 3: Implement retry flag**

Edit the existing `_ingest` command in `src/second_brain/cli.py`. Replace its signature + body:

```python
@cli.command(name="ingest")
@click.argument("path_or_slug", required=False)
@click.option("--retry", "retry_flag", is_flag=True, help="Retry a previously-failed source by slug.")
def _ingest(path_or_slug: str | None, retry_flag: bool) -> None:
    """Ingest a file/URL, or retry a failed source (`--retry <slug>`)."""
    cfg = Config.load()
    if retry_flag:
        if not path_or_slug:
            raise click.UsageError("--retry requires a source slug")
        from second_brain.ingest.retry import retry_source

        retry_source(path_or_slug, cfg=cfg)
        click.echo(f"retry ok: {path_or_slug}")
        return

    if not path_or_slug:
        raise click.UsageError("PATH_OR_SLUG required")

    from second_brain.ingest.base import IngestInput
    from second_brain.ingest.orchestrator import ingest as _ingest_fn

    source = IngestInput.from_path(Path(path_or_slug))
    folder = _ingest_fn(source, cfg=cfg)
    click.echo(f"ok: {folder.root.name}")
```

(The original `_ingest` took just `path: Path`. Check existing behavior in `src/second_brain/cli.py` around line 23 and preserve any output conventions.)

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_cli_automation.py -v`
Expected: all new process-inbox + ingest-retry tests pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_automation.py
git commit -m "feat(sb): add --retry flag to \`sb ingest\`"
```

---

## Task 7: `SerialQueue` — debounce + dedupe

**Files:**
- Create: `src/second_brain/watch/queue.py`
- Test: `tests/test_watch_queue.py`

Requirements:
- FIFO serial queue protected by a lock.
- Each job has a `key` (dedupe) and a `ready_at` timestamp (debounce).
- `enqueue(key, fn, debounce=1.0)` — if key already queued, bump its `ready_at`.
- `drain_until_empty(clock=time.monotonic)` — synchronously drain ready jobs for tests.
- Worker loop is a separate concern (daemon thread) in Task 8.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_watch_queue.py
from __future__ import annotations

from second_brain.watch.queue import SerialQueue


def test_queue_runs_fn_after_debounce(monkeypatch):
    clock = iter([0.0, 0.5, 1.2])  # enqueue t=0, drain t=0.5 (not ready), drain t=1.2 (ready)
    q = SerialQueue()
    called: list[str] = []

    q.enqueue("a", lambda: called.append("a"), debounce=1.0, now=0.0)
    q.drain_until_empty(now=0.5)
    assert called == []  # debounce window
    q.drain_until_empty(now=1.2)
    assert called == ["a"]


def test_queue_dedupes_repeated_key_and_bumps_ready_at():
    q = SerialQueue()
    called: list[float] = []

    q.enqueue("same", lambda: called.append(0.0), debounce=1.0, now=0.0)
    q.enqueue("same", lambda: called.append(1.0), debounce=1.0, now=0.8)  # bumps to 1.8

    q.drain_until_empty(now=1.5)
    assert called == []  # not yet ready — debounce reset on second enqueue

    q.drain_until_empty(now=2.0)
    assert called == [1.0]  # only most recent fn executed, once


def test_queue_runs_fifo_for_distinct_keys():
    q = SerialQueue()
    called: list[str] = []
    q.enqueue("a", lambda: called.append("a"), debounce=0.0, now=0.0)
    q.enqueue("b", lambda: called.append("b"), debounce=0.0, now=0.0)
    q.drain_until_empty(now=0.0)
    assert called == ["a", "b"]


def test_queue_swallows_fn_exceptions_and_continues():
    q = SerialQueue()
    called: list[str] = []

    def boom() -> None:
        raise RuntimeError("x")

    q.enqueue("a", boom, debounce=0.0, now=0.0)
    q.enqueue("b", lambda: called.append("b"), debounce=0.0, now=0.0)
    q.drain_until_empty(now=0.0)
    assert called == ["b"]
    assert q.last_errors and "x" in q.last_errors[0]
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_watch_queue.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `SerialQueue`**

```python
# src/second_brain/watch/queue.py
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class _Job:
    key: str
    fn: Callable[[], None]
    ready_at: float


class SerialQueue:
    """FIFO queue with per-key dedupe + debounce. Not thread-safe drain."""

    def __init__(self) -> None:
        self._jobs: list[_Job] = []
        self._lock = threading.Lock()
        self.last_errors: list[str] = []

    def enqueue(
        self, key: str, fn: Callable[[], None], *, debounce: float, now: float
    ) -> None:
        ready_at = now + debounce
        with self._lock:
            for job in self._jobs:
                if job.key == key:
                    job.fn = fn
                    job.ready_at = ready_at
                    return
            self._jobs.append(_Job(key=key, fn=fn, ready_at=ready_at))

    def drain_until_empty(self, *, now: float) -> int:
        """Run all jobs whose ready_at <= now. Returns count executed."""
        executed = 0
        while True:
            job = self._pop_ready(now)
            if job is None:
                break
            try:
                job.fn()
            except Exception as exc:  # noqa: BLE001 — logging, not silencing
                self.last_errors.append(f"{job.key}: {exc!r}")
            executed += 1
        return executed

    def _pop_ready(self, now: float) -> _Job | None:
        with self._lock:
            for i, job in enumerate(self._jobs):
                if job.ready_at <= now:
                    return self._jobs.pop(i)
        return None

    def pending(self) -> int:
        with self._lock:
            return len(self._jobs)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_watch_queue.py -v`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/watch/queue.py tests/test_watch_queue.py
git commit -m "feat(sb): SerialQueue with dedupe + debounce for watcher daemon"
```

---

## Task 8: `Watcher` daemon wiring

**Files:**
- Create: `src/second_brain/watch/daemon.py`
- Test: `tests/test_watch_daemon.py`

Design:
- `Watcher(cfg, queue=None, worker=None)` — defaults to `SerialQueue()` and the production worker (calls `ingest()`).
- Uses `watchdog.events.FileSystemEventHandler` subclass `_InboxHandler` that enqueues on_created / on_moved events.
- Ignores dotfiles, `.processed/`, and events on directories.
- `start()` spins up `Observer` + a worker thread that polls `queue.drain_until_empty(now=time.monotonic())` every 250ms.
- `stop()` joins both.
- Tests inject fake queue/clock and drive handler directly — no real observer thread in unit tests.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_watch_daemon.py
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from second_brain.config import Config
from second_brain.watch.daemon import Watcher
from second_brain.watch.queue import SerialQueue


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "inbox").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_handler_enqueues_on_created_event(sb_home: Path):
    calls: list[Path] = []
    q = SerialQueue()
    w = Watcher(Config.load(), queue=q, worker=lambda path: calls.append(path), clock=lambda: 0.0)

    # Simulate a watchdog on_created event on a .md file in inbox
    new_file = sb_home / "inbox" / "drop.md"
    new_file.write_text("# x")
    w._handle_event(str(new_file))

    assert q.pending() == 1
    # Drain past debounce
    q.drain_until_empty(now=10.0)
    assert calls == [new_file]


def test_handler_skips_dotfiles_and_directories(sb_home: Path):
    q = SerialQueue()
    w = Watcher(Config.load(), queue=q, worker=lambda p: None, clock=lambda: 0.0)

    dot = sb_home / "inbox" / ".DS_Store"
    dot.write_text("x")
    w._handle_event(str(dot))
    assert q.pending() == 0

    sub = sb_home / "inbox" / ".processed"
    sub.mkdir()
    w._handle_event(str(sub))
    assert q.pending() == 0


def test_handler_dedupes_rapid_events_for_same_path(sb_home: Path):
    calls: list[Path] = []
    q = SerialQueue()
    w = Watcher(Config.load(), queue=q, worker=lambda p: calls.append(p), clock=lambda: 0.0)

    f = sb_home / "inbox" / "thrash.md"
    f.write_text("x")
    for _ in range(5):
        w._handle_event(str(f))

    assert q.pending() == 1
    q.drain_until_empty(now=10.0)
    assert calls == [f]  # exactly once
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_watch_daemon.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `Watcher`**

```python
# src/second_brain/watch/daemon.py
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from second_brain.config import Config
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest
from second_brain.log import EventKind, append_event
from second_brain.watch.queue import SerialQueue

if TYPE_CHECKING:
    from watchdog.observers import Observer


Worker = Callable[[Path], None]
Clock = Callable[[], float]

_DEBOUNCE_SECONDS = 1.5
_POLL_INTERVAL = 0.25


def _default_worker(cfg: Config) -> Worker:
    def run(path: Path) -> None:
        try:
            source = IngestInput.from_path(path)
            folder = ingest(source, cfg=cfg)
            append_event(
                kind=EventKind.WATCH,
                op="watch.ingest.ok",
                subject=folder.root.name,
                value=str(path),
                home=cfg.home,
            )
        except (IngestError, Exception) as exc:  # noqa: BLE001
            append_event(
                kind=EventKind.ERROR,
                op="watch.ingest.failed",
                subject=str(path),
                value=str(exc),
                home=cfg.home,
            )

    return run


class Watcher:
    def __init__(
        self,
        cfg: Config,
        *,
        queue: SerialQueue | None = None,
        worker: Worker | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.cfg = cfg
        self.queue = queue or SerialQueue()
        self._worker = worker or _default_worker(cfg)
        self._clock = clock or time.monotonic
        self._observer: Observer | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def _handle_event(self, src_path: str) -> None:
        path = Path(src_path)
        if not path.exists() or path.is_dir():
            return
        if path.name.startswith("."):
            return
        if ".processed" in path.parts:
            return
        self.queue.enqueue(
            key=str(path),
            fn=lambda p=path: self._worker(p),
            debounce=_DEBOUNCE_SECONDS,
            now=self._clock(),
        )

    def start(self) -> None:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        handler = _InboxHandler(self)
        observer = Observer()
        observer.schedule(handler, str(self.cfg.inbox_dir), recursive=False)
        observer.start()
        self._observer = observer

        self._stop.clear()
        self._thread = threading.Thread(target=self._worker_loop, name="sb-watch", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=timeout)
            self._observer = None
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            self.queue.drain_until_empty(now=self._clock())
            time.sleep(_POLL_INTERVAL)


try:
    from watchdog.events import FileSystemEventHandler as _BaseHandler
except ImportError:  # watchdog optional at import time; start() will re-import
    _BaseHandler = object  # type: ignore[assignment,misc]


class _InboxHandler(_BaseHandler):  # type: ignore[misc]
    def __init__(self, watcher: Watcher) -> None:
        super().__init__()
        self._watcher = watcher

    def on_created(self, event) -> None:  # type: ignore[no-untyped-def]
        self._watcher._handle_event(event.src_path)

    def on_moved(self, event) -> None:  # type: ignore[no-untyped-def]
        self._watcher._handle_event(event.dest_path)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_watch_daemon.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/watch/daemon.py tests/test_watch_daemon.py
git commit -m "feat(sb): Watcher daemon with serial queue + event deduping"
```

---

## Task 9: `sb watch` CLI command

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_automation.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_cli_automation.py`:

```python
def test_cli_watch_once_drains_then_exits(sb_home: Path, monkeypatch: pytest.MonkeyPatch):
    """--once mode enqueues current inbox contents, drains, and exits — for cron-style usage."""
    (sb_home / "inbox" / "note.md").write_text("# x\n\nbody.\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["watch", "--once"])
    assert result.exit_code == 0, result.output
    assert "drained" in result.output.lower() or "processed" in result.output.lower()
    assert any((sb_home / "sources").iterdir())
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_cli_automation.py::test_cli_watch_once_drains_then_exits -v`
Expected: `No such command 'watch'`.

- [ ] **Step 3: Implement**

Add to `src/second_brain/cli.py`:

```python
@cli.command(name="watch")
@click.option("--once", is_flag=True, help="Drain current inbox contents then exit (cron-style).")
def _watch(once: bool) -> None:
    """Watch ~/second-brain/inbox/ and ingest new drops."""
    import signal
    import time

    from second_brain.inbox.runner import InboxRunner
    from second_brain.watch.daemon import Watcher

    cfg = Config.load()

    if once:
        result = InboxRunner(cfg).run()
        click.echo(f"drained: ok={len(result.ok)} failed={len(result.failed)}")
        return

    watcher = Watcher(cfg)
    watcher.start()
    click.echo(f"watching {cfg.inbox_dir} (Ctrl-C to stop)")

    def _handle_sigint(signum, frame):  # type: ignore[no-untyped-def]
        watcher.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handle_sigint)
    signal.signal(signal.SIGTERM, _handle_sigint)
    try:
        while True:
            time.sleep(1.0)
    finally:
        watcher.stop()
```

- [ ] **Step 4: Run test, verify pass**

Run: `pytest tests/test_cli_automation.py::test_cli_watch_once_drains_then_exits -v`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_automation.py
git commit -m "feat(sb): add \`sb watch\` (daemon + --once mode)"
```

---

## Task 10: Index compaction helpers

**Files:**
- Create: `src/second_brain/maintain/compact.py`
- Test: `tests/test_maintain_compact.py`

Requirements:
- `compact_fts(cfg)` — open FtsStore, run `INSERT INTO claim_fts(claim_fts) VALUES('optimize')` and `VACUUM`.
- `compact_duckdb(cfg)` — open DuckStore, run `CHECKPOINT` (persistent durable write + free space reclaim).
- Both must be idempotent and no-op on missing databases.
- Return `CompactResult(fts_bytes_before, fts_bytes_after, duck_bytes_before, duck_bytes_after)`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_maintain_compact.py
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.maintain.compact import compact_duckdb, compact_fts
from second_brain.store.fts_store import FtsStore


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_compact_fts_noop_when_db_missing(sb_home: Path):
    cfg = Config.load()
    result = compact_fts(cfg)
    assert result.before == 0
    assert result.after == 0


def test_compact_fts_reduces_or_preserves_size(sb_home: Path):
    cfg = Config.load()
    with FtsStore.open(cfg.fts_path) as store:
        store.ensure_schema()
        for i in range(50):
            store.insert_claim(claim_id=f"c{i}", statement=f"stmt {i}", abstract="", body="", taxonomy="x")
    result = compact_fts(cfg)
    assert result.before > 0
    assert result.after <= result.before  # may equal on tiny DB; must not grow


def test_compact_duckdb_noop_when_db_missing(sb_home: Path):
    cfg = Config.load()
    result = compact_duckdb(cfg)
    assert result.before == 0
    assert result.after == 0
```

- [ ] **Step 2: Run test, verify failure**

Run: `pytest tests/test_maintain_compact.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/maintain/compact.py
from __future__ import annotations

from dataclasses import dataclass

from second_brain.config import Config
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore


@dataclass(frozen=True)
class CompactResult:
    before: int
    after: int


def _size(path) -> int:
    return path.stat().st_size if path.exists() else 0


def compact_fts(cfg: Config) -> CompactResult:
    before = _size(cfg.fts_path)
    if before == 0:
        return CompactResult(0, 0)
    with FtsStore.open(cfg.fts_path) as store:
        store.conn.execute("INSERT INTO claim_fts(claim_fts) VALUES('optimize')")
        store.conn.execute("INSERT INTO source_fts(source_fts) VALUES('optimize')")
        store.conn.commit()
        store.conn.execute("VACUUM")
    return CompactResult(before=before, after=_size(cfg.fts_path))


def compact_duckdb(cfg: Config) -> CompactResult:
    before = _size(cfg.duckdb_path)
    if before == 0:
        return CompactResult(0, 0)
    with DuckStore.open(cfg.duckdb_path) as store:
        store.conn.execute("CHECKPOINT")
    return CompactResult(before=before, after=_size(cfg.duckdb_path))
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_maintain_compact.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/maintain/compact.py tests/test_maintain_compact.py
git commit -m "feat(sb): compact_fts + compact_duckdb for maintain pipeline"
```

---

## Task 11: `MaintainRunner` — compose lint + reconcile summary + compact

**Files:**
- Create: `src/second_brain/maintain/runner.py`
- Test: `tests/test_maintain_runner.py`

Pipeline steps (in order):
1. Run lint; count findings by severity.
2. Count open contradictions (edges with relation=contradicts and no resolution note).
3. Run `compact_fts` + `compact_duckdb`.
4. Detect stale abstracts (claims whose `abstract` is empty AND body > 200 chars). Return list of slugs (do not rewrite — that's Plan 6's responsibility).
5. Emit `EventKind.MAINTAIN` entry summarizing counts.
6. Return `MaintainReport` dataclass with all counts for downstream `sb stats`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_maintain_runner.py
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.maintain.runner import MaintainRunner


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _claim(home: Path, slug: str, *, abstract: str, body: str) -> None:
    folder = home / "claims"
    folder.mkdir(exist_ok=True)
    dump_document(
        folder / f"{slug}.md",
        {
            "id": slug,
            "statement": slug,
            "confidence": "extracted",
            "abstract": abstract,
            "taxonomy": "test",
        },
        body,
    )


def test_maintain_runner_returns_report_with_counts(sb_home: Path):
    _claim(sb_home, "clm_a", abstract="", body="x" * 500)  # stale
    _claim(sb_home, "clm_b", abstract="summary", body="x" * 500)  # not stale
    cfg = Config.load()

    report = MaintainRunner(cfg).run()

    assert "clm_a" in report.stale_abstracts
    assert "clm_b" not in report.stale_abstracts
    assert report.lint_counts is not None
    assert report.open_contradictions >= 0


def test_maintain_runner_emits_log_entry(sb_home: Path):
    cfg = Config.load()
    MaintainRunner(cfg).run()
    log = (sb_home / "log.md").read_text()
    assert "[MAINTAIN]" in log
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_maintain_runner.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/second_brain/maintain/runner.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.lint.runner import run_lint
from second_brain.log import EventKind, append_event
from second_brain.maintain.compact import compact_duckdb, compact_fts
from second_brain.store.duckdb_store import DuckStore

_STALE_BODY_MIN_CHARS = 200


@dataclass(frozen=True)
class MaintainReport:
    lint_counts: dict[str, int] = field(default_factory=dict)
    open_contradictions: int = 0
    stale_abstracts: list[str] = field(default_factory=list)
    fts_bytes_before: int = 0
    fts_bytes_after: int = 0
    duck_bytes_before: int = 0
    duck_bytes_after: int = 0


class MaintainRunner:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def run(self) -> MaintainReport:
        lint_findings = run_lint(self.cfg)
        lint_counts: dict[str, int] = {}
        for f in lint_findings:
            lint_counts[f.severity] = lint_counts.get(f.severity, 0) + 1

        open_contradictions = self._count_open_contradictions()
        stale = self._stale_abstracts()
        fts = compact_fts(self.cfg)
        duck = compact_duckdb(self.cfg)

        report = MaintainReport(
            lint_counts=lint_counts,
            open_contradictions=open_contradictions,
            stale_abstracts=stale,
            fts_bytes_before=fts.before,
            fts_bytes_after=fts.after,
            duck_bytes_before=duck.before,
            duck_bytes_after=duck.after,
        )
        append_event(
            kind=EventKind.MAINTAIN,
            op="maintain.run",
            subject="pipeline",
            value=(
                f"lint={sum(lint_counts.values())} "
                f"contradictions={open_contradictions} "
                f"stale={len(stale)}"
            ),
            reason={"lint": lint_counts, "stale_count": len(stale)},
            home=self.cfg.home,
        )
        return report

    def _count_open_contradictions(self) -> int:
        if not self.cfg.duckdb_path.exists():
            return 0
        with DuckStore.open(self.cfg.duckdb_path) as store:
            row = store.conn.execute(
                "SELECT COUNT(*) FROM edges WHERE relation = 'contradicts'"
            ).fetchone()
        return int(row[0]) if row else 0

    def _stale_abstracts(self) -> list[str]:
        stale: list[str] = []
        for claim_path in self.cfg.claims_dir.glob("*.md"):
            if claim_path.name == "conflicts.md":
                continue
            try:
                fm, body = load_document(claim_path)
            except Exception:  # noqa: BLE001
                continue
            abstract = (fm.get("abstract") or "").strip()
            if not abstract and len(body) >= _STALE_BODY_MIN_CHARS:
                stale.append(fm.get("id") or claim_path.stem)
        return sorted(stale)
```

Verify the lint runner's entry point is `second_brain.lint.runner.run_lint` and each finding has `.severity`. If the names differ, adapt the import accordingly.

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_maintain_runner.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/maintain/runner.py tests/test_maintain_runner.py
git commit -m "feat(sb): MaintainRunner composes lint + contradictions + compact + stale scan"
```

---

## Task 12: `sb maintain` CLI command

**Files:**
- Modify: `src/second_brain/cli.py`
- Test: `tests/test_cli_automation.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_cli_automation.py`:

```python
def test_cli_maintain_prints_report(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["maintain"])
    assert result.exit_code == 0, result.output
    assert "lint" in result.output.lower()
    assert "contradictions" in result.output.lower()
    assert "compact" in result.output.lower()


def test_cli_maintain_json_flag_emits_json(sb_home: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["maintain", "--json"])
    assert result.exit_code == 0, result.output
    import json as _json

    payload = _json.loads(result.output)
    assert "lint_counts" in payload
    assert "stale_abstracts" in payload
```

- [ ] **Step 2: Run tests, verify failure**

Run: `pytest tests/test_cli_automation.py -v`
Expected: `No such command 'maintain'`.

- [ ] **Step 3: Implement**

Add to `src/second_brain/cli.py`:

```python
@cli.command(name="maintain")
@click.option("--json", "as_json", is_flag=True, help="Emit report as JSON on stdout.")
def _maintain(as_json: bool) -> None:
    """Run nightly maintenance: lint, contradiction scan, compact, stale-abstract detect."""
    import dataclasses
    import json as _json

    from second_brain.maintain.runner import MaintainRunner

    cfg = Config.load()
    report = MaintainRunner(cfg).run()

    if as_json:
        click.echo(_json.dumps(dataclasses.asdict(report), indent=2))
        return

    click.echo("== sb maintain ==")
    click.echo(f"lint: {dict(report.lint_counts)}")
    click.echo(f"open contradictions: {report.open_contradictions}")
    click.echo(f"stale abstracts: {len(report.stale_abstracts)}")
    click.echo(
        f"compact fts: {report.fts_bytes_before}B -> {report.fts_bytes_after}B"
    )
    click.echo(
        f"compact duckdb: {report.duck_bytes_before}B -> {report.duck_bytes_after}B"
    )
```

- [ ] **Step 4: Run tests, verify pass**

Run: `pytest tests/test_cli_automation.py -v`
Expected: full suite passes (process-inbox + retry + watch --once + maintain + maintain --json).

- [ ] **Step 5: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add src/second_brain/cli.py tests/test_cli_automation.py
git commit -m "feat(sb): add \`sb maintain\` with text + JSON output"
```

---

## Task 13: Full suite green + coverage

**Files:** none new; verify quality gate.

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/jay/Developer/second-brain && pytest --ignore=tests/test_ingest_pdf.py -q`
Expected: all pass; coverage ≥75%.

- [ ] **Step 2: If coverage below 75%, add tests**

Investigate missing coverage via `pytest --cov=second_brain --cov-report=term-missing --ignore=tests/test_ingest_pdf.py`. Add targeted tests for any uncovered branch in the new code (inbox runner's manifest-load path, watcher's observer start/stop, etc.). Do not add tests just to inflate coverage — only for genuine branches.

- [ ] **Step 3: Commit if any new tests**

```bash
cd /Users/jay/Developer/second-brain
git add tests/
git commit -m "test(sb): plug coverage gaps in automation modules"
```

---

## Task 14: README + launchd/cron docs

**Files:**
- Modify: `README.md`
- Create: `docs/automation.md`

- [ ] **Step 1: Update README**

In `README.md`, add a new section after "Habits + inject + reconcile":

```markdown
### Automation
- `sb process-inbox` — ingest every file in `~/second-brain/inbox/` (non-recursive). Failures stay put; quarantined after 3 attempts.
- `sb ingest --retry <slug>` — replay a previously-failed converter against the preserved `raw/*`.
- `sb watch` — run the filesystem watcher daemon. `--once` drains current inbox then exits (cron/launchd-friendly).
- `sb maintain` — one-shot maintenance pipeline (lint + contradiction scan + index compact + stale-abstract detect). `--json` for machine output.

See `docs/automation.md` for launchd/cron installation.
```

- [ ] **Step 2: Create launchd snippet**

```markdown
# docs/automation.md

# Automation (launchd + cron)

## macOS — launchd

`~/Library/LaunchAgents/local.secondbrain.maintain.plist`:

\`\`\`xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>local.secondbrain.maintain</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>bash</string>
    <string>-lc</string>
    <string>SECOND_BRAIN_HOME=$HOME/second-brain /usr/local/bin/sb maintain --json >> $HOME/second-brain/.sb/maintain.log 2>&amp;1</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>30</integer></dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
\`\`\`

Load with `launchctl load ~/Library/LaunchAgents/local.secondbrain.maintain.plist`.

## Linux — cron

\`\`\`
30 3 * * * SECOND_BRAIN_HOME=$HOME/second-brain /usr/local/bin/sb maintain --json >> $HOME/second-brain/.sb/maintain.log 2>&1
\`\`\`

## Watch daemon (systemd unit)

\`\`\`ini
# ~/.config/systemd/user/sb-watch.service
[Unit]
Description=Second Brain inbox watcher

[Service]
Environment=SECOND_BRAIN_HOME=%h/second-brain
ExecStart=/usr/local/bin/sb watch
Restart=on-failure

[Install]
WantedBy=default.target
\`\`\`

Enable with `systemctl --user enable --now sb-watch.service`.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/jay/Developer/second-brain
git add README.md docs/automation.md
git commit -m "docs(sb): document automation commands + launchd/cron/systemd recipes"
```

---

## Task 15: claude-code-agent changelog + push

**Files:**
- Modify: `/Users/jay/Developer/claude-code-agent/docs/log.md`

- [ ] **Step 1: Add Unreleased entry**

Under `## [Unreleased]` → `### Added` (create the `Added` subheading if missing):

```markdown
- Second Brain automation: `sb process-inbox`, `sb ingest --retry`, `sb watch` (+ `--once`), `sb maintain` (+ `--json`). Launchd/cron/systemd recipes in the second-brain repo's `docs/automation.md`.
```

- [ ] **Step 2: Commit (claude-code-agent)**

```bash
cd /Users/jay/Developer/claude-code-agent
git add docs/log.md
git commit -m "docs(log): second-brain automation commands landed (plan 5)"
```

- [ ] **Step 3: Push both repos**

```bash
cd /Users/jay/Developer/second-brain && git push 2>/dev/null || echo "(no remote for second-brain — local only)"
cd /Users/jay/Developer/claude-code-agent && git push
```

---

## Self-review notes

- **Spec coverage:** §5.1 (process-inbox) = Task 3–4. §5.6 (ingest --retry) = Task 5–6. §9.1 watcher = Task 7–9. §9.1 maintain = Task 10–12.
- **No placeholders:** every step has code or an exact command.
- **Type consistency:** `Config`, `InboxRunner`, `InboxFailure`, `InboxRunResult`, `SerialQueue`, `Watcher`, `MaintainRunner`, `MaintainReport`, `CompactResult`, `retry_source`, `RetryError` — each defined once, referenced consistently.
- **Deferred to plan 6:** habit-learning detector, `sb eval`, `sb stats --json`, stale-abstract *regeneration*, analytics.duckdb. This plan only *detects* staleness — doesn't rewrite.
- **Error propagation:** retry errors raise `RetryError`; inbox failures captured in manifest; watcher failures logged via `EventKind.ERROR`; maintain emits `EventKind.MAINTAIN`.
- **Concurrency:** `SerialQueue` is the single coordination point. Watcher uses one worker thread. Maintain is single-threaded.
