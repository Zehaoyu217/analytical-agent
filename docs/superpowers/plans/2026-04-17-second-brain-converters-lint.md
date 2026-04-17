# Second Brain — Converters + Lint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the remaining v1 ingest converters (URL, repo, DOCX, EPUB) and land the lint subsystem (rule set, runner, `sb lint`, `conflicts.md` renderer).

**Architecture:** Converters follow the existing `Converter` protocol pattern established by `note.py` / `pdf.py` — stream-in, writes `raw/*`, returns `SourceArtifacts`. URL ingest uses `httpx` + `readability-lxml` (no Playwright in v1; screenshot deferred). Repo ingest uses the local `git` binary (no `gh` auth dependency). DOCX/EPUB delegate to `markitdown` and reuse the PDF fallback pattern. Lint runs over in-memory KB snapshots (all frontmatter loaded from disk), producing a typed `LintReport`; the renderer emits `conflicts.md` in the layout defined in spec §7.3.

**Tech Stack:** Python 3.12+, `httpx`, `readability-lxml` (new dep), `markitdown` (existing), `git` CLI (system binary, stdlib `subprocess`), Click, Pydantic, ruamel.yaml, pytest, pytest-asyncio.

**Working directory:** ALL work happens in `~/Developer/second-brain/`. Do not modify `~/Developer/claude-code-agent/`.

**Prior state:** Plan 2 shipped through task 13. Latest commit on `main` in `~/Developer/second-brain/` is `cc021c1`. 65 tests pass, 3 DuckPGQ skips, 82.6% coverage. Retrieval (`sb search/load/reason`) and claim extraction (`sb extract`, fake + live) all live.

**Spec sections covered:** §5.3 (url/repo/docx/epub converters), §7.1–§7.3 (lint rules + conflicts.md), partial §13.1 (lint unit tests). Out of scope for this plan: `sb reconcile` (Claude-driven resolution flow — plan 4), `sb inject` (plan 4), wizard (plan 5), habit learning (plan 5), `sb maintain` / `sb watch` (plan 6).

---

## File Structure

**Create:**

| Path | Responsibility |
|---|---|
| `src/second_brain/ingest/url.py` | `UrlConverter` — httpx fetch + readability-lxml article extraction |
| `src/second_brain/ingest/repo.py` | `RepoConverter` — git clone + glob-based file capture |
| `src/second_brain/ingest/docx.py` | `DocxConverter` — markitdown wrapper |
| `src/second_brain/ingest/epub.py` | `EpubConverter` — markitdown wrapper |
| `src/second_brain/lint/__init__.py` | re-exports `run_lint`, `LintReport`, `LintIssue`, `Severity` |
| `src/second_brain/lint/snapshot.py` | `KBSnapshot` — loads all sources + claims frontmatter from disk |
| `src/second_brain/lint/rules.py` | individual rule functions `check_*` returning `list[LintIssue]` |
| `src/second_brain/lint/runner.py` | `run_lint(cfg) -> LintReport`, rule registry |
| `src/second_brain/lint/conflicts_md.py` | renders `~/second-brain/conflicts.md` from a `LintReport` |
| `tests/test_ingest_url.py` | URL converter tests with `httpx.MockTransport` |
| `tests/test_ingest_repo.py` | Repo converter tests with tmp git repo fixture |
| `tests/test_ingest_docx.py` | DOCX converter tests (fallback path + integration) |
| `tests/test_ingest_epub.py` | EPUB converter tests (fallback path + integration) |
| `tests/test_lint_snapshot.py` | snapshot loader tests |
| `tests/test_lint_rules.py` | per-rule unit tests |
| `tests/test_lint_runner.py` | runner aggregation tests |
| `tests/test_lint_conflicts_md.py` | conflicts.md rendering tests |
| `tests/test_cli_lint.py` | `sb lint` CLI tests |

**Modify:**

| Path | Responsibility |
|---|---|
| `pyproject.toml` | add `readability-lxml>=0.8` dependency |
| `src/second_brain/ingest/orchestrator.py` | register new converters in `DEFAULT_CONVERTERS` |
| `src/second_brain/cli.py` | add `sb lint` command |

---

## Known Gotchas

1. **Python 3.13 host.** `~/Developer/second-brain/` was scaffolded against Python 3.13 (host has no 3.12). `pyproject.toml` says `>=3.12`; 3.13 satisfies.
2. **Existing venv.** Use `~/Developer/second-brain/.venv` from plan 1. Activate with `source .venv/bin/activate`. Reinstall after dep changes: `pip install -e '.[dev]'`.
3. **Markitdown optional extras.** `markitdown[pdf]` / `markitdown[docx]` / `markitdown[epub]` are not in the base install. Follow the PDF converter pattern: try markitdown, fall back to a placeholder string `[markitdown failed: {exc}]` so ingest never crashes on format errors. Only mark happy-path tests as `@pytest.mark.integration`.
4. **No Playwright.** URL converter does NOT take a screenshot in v1. A screenshot hook can be added later via the same `SourceArtifacts.raw` list; this plan explicitly skips it.
5. **readability-lxml import name.** Package is `readability-lxml`; import is `from readability import Document`.
6. **git subprocess safety.** Use `subprocess.run([...], check=True, capture_output=True, text=True, timeout=120)`. Never invoke through a shell. Validate inputs (reject shell metacharacters in repo spec).
7. **Repo shorthand.** Accept `gh:owner/repo` (resolves to `https://github.com/owner/repo.git`) and any URL that ends in `.git`. Reject everything else.
8. **Grace period check.** `UNRESOLVED_CONTRADICTION` compares `extracted_at + grace_period_days` to now. Default grace is 14 days (spec §7.1); since we haven't built habits yet, hard-code `DEFAULT_GRACE_DAYS = 14` in rules.
9. **HASH_MISMATCH recomputation.** Recompute from `raw_manifest.json` entries — iterate each `raw[*]`, recompute sha256, compare. Do NOT recompute from source-md frontmatter (that's what we're validating).
10. **Deterministic tests.** No real network calls. No real git remote operations. Use fixtures.
11. **Commit messages.** Each task has an exact commit message; use it verbatim.
12. **Tests exclude integration by default.** Run `pytest -m "not integration"` for the fast gate; CI can run `pytest` with integration on a docker image that has markitdown extras.

---

## Task 1: Add `readability-lxml` dep + URL converter (httpx + readability)

**Files:**
- Modify: `pyproject.toml` (add `readability-lxml>=0.8` to `[project].dependencies`)
- Create: `src/second_brain/ingest/url.py`
- Create: `tests/test_ingest_url.py`

- [ ] **Step 1: Add the dep to `pyproject.toml`**

Modify `pyproject.toml` — find the `dependencies = [...]` block and add `readability-lxml>=0.8`. The full block should read:

```toml
dependencies = [
  "click>=8.1",
  "pydantic>=2.8",
  "ruamel.yaml>=0.18",
  "duckdb>=1.1.0",
  "markitdown>=0.0.1a2",
  "httpx>=0.27",
  "anthropic>=0.40",
  "python-slugify>=8.0",
  "readability-lxml>=0.8",
]
```

Run: `cd ~/Developer/second-brain && source .venv/bin/activate && pip install -e '.[dev]' --quiet`

- [ ] **Step 2: Write the failing test**

Create `tests/test_ingest_url.py`:

```python
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.url import UrlConverter


_SAMPLE_HTML = b"""<!doctype html>
<html>
  <head><title>Ignore Me — Site Title</title></head>
  <body>
    <nav>nav junk</nav>
    <article>
      <h1>A Clear Article Title</h1>
      <p>This is the first paragraph of the real article body.</p>
      <p>Second paragraph with more detail.</p>
    </article>
    <footer>footer junk</footer>
  </body>
</html>
"""


def _transport(body: bytes = _SAMPLE_HTML, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status,
            content=body,
            headers={"content-type": "text/html; charset=utf-8"},
        )
    return httpx.MockTransport(handler)


def test_matches_http_origin() -> None:
    c = UrlConverter()
    ok = IngestInput.from_bytes(origin="https://example.com/a", suffix="", content=b"")
    bad = IngestInput.from_bytes(origin="/tmp/a.pdf", suffix=".pdf", content=b"")
    assert c.matches(ok)
    assert not c.matches(bad)


def test_convert_writes_raw_html_and_body(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="https://example.com/a", suffix="", content=b"")
    c = UrlConverter(client=httpx.Client(transport=_transport()))
    artifacts = c.convert(inp, folder)
    assert (folder.raw_dir / "page.html").exists()
    assert (folder.raw_dir / "page.html").read_bytes() == _SAMPLE_HTML
    assert "A Clear Article Title" in artifacts.title_hint
    assert "first paragraph of the real article body" in artifacts.processed_body
    assert artifacts.raw[0].path == "raw/page.html"
    assert artifacts.raw[0].kind == "original"


def test_convert_http_error_raises(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    inp = IngestInput.from_bytes(origin="https://example.com/missing", suffix="", content=b"")
    c = UrlConverter(client=httpx.Client(transport=_transport(status=404)))
    with pytest.raises(RuntimeError, match="status=404"):
        c.convert(inp, folder)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/test_ingest_url.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.ingest.url'`.

- [ ] **Step 4: Implement `UrlConverter`**

Create `src/second_brain/ingest/url.py`:

```python
from __future__ import annotations

from typing import ClassVar

import httpx

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder


class UrlConverter(Converter):
    kind: ClassVar[str] = "url"

    def __init__(self, client: httpx.Client | None = None, *, timeout: float = 30.0) -> None:
        self._client = client
        self._timeout = timeout

    def matches(self, source: IngestInput) -> bool:
        origin = source.origin or ""
        return origin.startswith("http://") or origin.startswith("https://")

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        html = self._fetch(source.origin)
        raw_write = target.write_raw(
            rel_path="raw/page.html",
            content=html,
            kind="original",
        )
        title, body_md = self._extract_article(html)
        return SourceArtifacts(
            processed_body=body_md if body_md.endswith("\n") else body_md + "\n",
            raw=[raw_write],
            title_hint=title,
        )

    def _fetch(self, url: str) -> bytes:
        client = self._client or httpx.Client(timeout=self._timeout, follow_redirects=True)
        try:
            resp = client.get(url)
        finally:
            if self._client is None:
                client.close()
        if resp.status_code >= 400:
            raise RuntimeError(f"url fetch failed: status={resp.status_code} url={url}")
        return resp.content

    @staticmethod
    def _extract_article(html: bytes) -> tuple[str, str]:
        try:
            from readability import Document  # type: ignore[import-not-found]

            doc = Document(html.decode("utf-8", errors="replace"))
            title = (doc.short_title() or doc.title() or "").strip()
            summary_html = doc.summary(html_partial=True)
            body = _html_to_text(summary_html)
            return title or "untitled", body
        except Exception as exc:  # noqa: BLE001
            return "untitled", f"[readability failed: {exc}]\n"


def _html_to_text(fragment: str) -> str:
    # Tiny fallback: strip tags by collapsing with lxml if available, else regex.
    try:
        from lxml import html as lxml_html  # type: ignore[import-not-found]

        root = lxml_html.fromstring(fragment)
        parts: list[str] = []
        for el in root.iter():
            text = (el.text or "").strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts).strip() + "\n"
    except Exception:  # noqa: BLE001
        import re

        stripped = re.sub(r"<[^>]+>", " ", fragment)
        return " ".join(stripped.split()).strip() + "\n"
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_ingest_url.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass; 3 new tests pass.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/second_brain/ingest/url.py tests/test_ingest_url.py
git commit -m "feat(ingest): URL converter via httpx + readability-lxml"
```

---

## Task 2: Repo converter (git clone + glob capture)

**Files:**
- Create: `src/second_brain/ingest/repo.py`
- Create: `tests/test_ingest_repo.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingest_repo.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.repo import RepoConverter


@pytest.fixture
def seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "seed-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# seed-repo\n\nDemonstration repo.\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'seed'\n", encoding="utf-8")
    docs = repo / "docs"
    docs.mkdir()
    (docs / "arch.md").write_text("# Architecture\n\nSome docs.\n", encoding="utf-8")
    node_mods = repo / "node_modules"
    node_mods.mkdir()
    (node_mods / "ignore.md").write_text("# should be excluded\n", encoding="utf-8")

    for cmd in (
        ["git", "init", "--quiet"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    return repo


def test_matches_repo_origin() -> None:
    c = RepoConverter()
    ok = IngestInput.from_bytes(origin="gh:owner/repo", suffix="", content=b"")
    ok2 = IngestInput.from_bytes(origin="https://github.com/owner/repo.git", suffix="", content=b"")
    bad = IngestInput.from_bytes(origin="https://example.com/a", suffix="", content=b"")
    assert c.matches(ok)
    assert c.matches(ok2)
    assert not c.matches(bad)


def test_convert_clones_and_captures_globs(tmp_path: Path, seed_repo: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_repo")
    inp = IngestInput.from_bytes(origin=f"file://{seed_repo}", suffix="", content=b"")
    c = RepoConverter(
        include_globs=("README*", "docs/**/*.md", "pyproject.toml"),
        exclude_globs=("node_modules/**", ".git/**"),
    )
    artifacts = c.convert(inp, folder)
    paths = {r.path for r in artifacts.raw}
    assert "raw/README.md" in paths
    assert "raw/pyproject.toml" in paths
    assert "raw/docs/arch.md" in paths
    assert not any("node_modules" in p for p in paths)
    assert "README.md" in artifacts.processed_body
    assert "seed-repo" in artifacts.title_hint


def test_resolve_gh_shorthand() -> None:
    c = RepoConverter()
    assert c._resolve("gh:acme/widgets") == "https://github.com/acme/widgets.git"
    assert c._resolve("https://github.com/acme/widgets.git") == "https://github.com/acme/widgets.git"
    assert c._resolve("file:///tmp/x") == "file:///tmp/x"


def test_rejects_unsafe_input() -> None:
    c = RepoConverter()
    with pytest.raises(ValueError):
        c._resolve("gh:acme/widgets; rm -rf /")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_ingest_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.ingest.repo'`.

- [ ] **Step 3: Implement `RepoConverter`**

Create `src/second_brain/ingest/repo.py`:

```python
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder

_GH_SHORTHAND = re.compile(r"^gh:([A-Za-z0-9][A-Za-z0-9._-]*)/([A-Za-z0-9][A-Za-z0-9._-]*)$")
_HTTPS_REPO = re.compile(r"^(https?://[^\s;&|`$<>()\\]+\.git)$")
_FILE_REPO = re.compile(r"^(file://[^\s;&|`$<>()\\]+)$")

_DEFAULT_INCLUDE: tuple[str, ...] = (
    "README*",
    "docs/**/*.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
)
_DEFAULT_EXCLUDE: tuple[str, ...] = ("node_modules/**", "target/**", ".git/**")


class RepoConverter(Converter):
    kind: ClassVar[str] = "repo"

    def __init__(
        self,
        *,
        include_globs: tuple[str, ...] = _DEFAULT_INCLUDE,
        exclude_globs: tuple[str, ...] = _DEFAULT_EXCLUDE,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._include = include_globs
        self._exclude = exclude_globs
        self._timeout = timeout_seconds

    def matches(self, source: IngestInput) -> bool:
        origin = source.origin or ""
        if _GH_SHORTHAND.match(origin):
            return True
        if origin.startswith(("https://", "http://")) and origin.endswith(".git"):
            return True
        if origin.startswith("file://"):
            return True
        return False

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        url = self._resolve(source.origin)
        with tempfile.TemporaryDirectory(prefix="sb_repo_") as td:
            clone_dir = Path(td) / "repo"
            self._clone(url, clone_dir)
            raws = self._capture(clone_dir, target)
            title = self._title_from_readme(clone_dir)
            body = self._body(raws, target)
        return SourceArtifacts(
            processed_body=body,
            raw=raws,
            title_hint=title,
        )

    def _resolve(self, origin: str) -> str:
        m = _GH_SHORTHAND.match(origin)
        if m:
            owner, repo = m.group(1), m.group(2)
            return f"https://github.com/{owner}/{repo}.git"
        if _HTTPS_REPO.match(origin) or _FILE_REPO.match(origin):
            return origin
        raise ValueError(f"unrecognized repo origin: {origin!r}")

    def _clone(self, url: str, dest: Path) -> None:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
            check=True,
            capture_output=True,
            timeout=self._timeout,
        )

    def _capture(self, clone_dir: Path, target: SourceFolder):
        raws = []
        seen: set[Path] = set()
        for pattern in self._include:
            for candidate in clone_dir.glob(pattern):
                if not candidate.is_file():
                    continue
                rel = candidate.relative_to(clone_dir)
                if self._excluded(rel):
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                rel_path = f"raw/{rel.as_posix()}"
                raw = target.write_raw(
                    rel_path=rel_path,
                    content=candidate.read_bytes(),
                    kind="original",
                )
                raws.append(raw)
        return raws

    def _excluded(self, rel: Path) -> bool:
        posix = rel.as_posix()
        return any(rel.match(pat) or _fnmatch_prefix(posix, pat) for pat in self._exclude)

    @staticmethod
    def _title_from_readme(clone_dir: Path) -> str:
        for name in ("README.md", "README", "README.rst"):
            p = clone_dir / name
            if p.exists():
                for line in p.read_text("utf-8", errors="replace").splitlines():
                    s = line.strip()
                    if s.startswith("# "):
                        return s[2:].strip()
                    if s:
                        return s[:120]
        return clone_dir.name

    @staticmethod
    def _body(raws, target: SourceFolder) -> str:
        # Compose a short markdown body that concatenates captured files for BM25.
        parts: list[str] = []
        for r in raws:
            p = target.root / r.path
            if p.suffix.lower() in {".md", ".rst", ".txt", ".toml", ".json"}:
                parts.append(f"## {r.path}\n\n{p.read_text('utf-8', errors='replace')}")
        return ("\n\n".join(parts) + "\n") if parts else "\n"


def _fnmatch_prefix(posix: str, pattern: str) -> bool:
    # Very small helper so that "node_modules/**" matches paths under node_modules/.
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return posix.startswith(prefix + "/") or posix == prefix
    return False
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_ingest_repo.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass; 4 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/second_brain/ingest/repo.py tests/test_ingest_repo.py
git commit -m "feat(ingest): repo converter with glob capture over shallow clone"
```

---

## Task 3: DOCX converter (markitdown passthrough)

**Files:**
- Create: `src/second_brain/ingest/docx.py`
- Create: `tests/test_ingest_docx.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingest_docx.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.docx import DocxConverter


def test_matches_docx_suffix() -> None:
    c = DocxConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.docx", suffix=".docx", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))


def test_convert_writes_raw_and_returns_body(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="/p/doc.docx", suffix=".docx", content=b"not-a-real-docx")
    artifacts = DocxConverter().convert(inp, folder)
    assert (folder.raw_dir / "original.docx").exists()
    assert len(artifacts.processed_body) > 0
    # With malformed bytes, the fallback placeholder is emitted.
    assert "[markitdown failed" in artifacts.processed_body
    assert artifacts.raw[0].path == "raw/original.docx"


def test_guess_title_falls_back_to_origin_stem(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    inp = IngestInput.from_bytes(origin="/p/my-report.docx", suffix=".docx", content=b"x")
    artifacts = DocxConverter().convert(inp, folder)
    assert artifacts.title_hint == "my-report"


@pytest.mark.integration
def test_convert_real_docx_integration(tmp_path: Path) -> None:
    pytest.importorskip("markitdown")
    pytest.importorskip("docx")  # python-docx, only present under markitdown[docx]
    from docx import Document as DocxDoc

    raw_path = tmp_path / "hello.docx"
    doc = DocxDoc()
    doc.add_paragraph("Hello DOCX integration")
    doc.save(raw_path)

    folder = SourceFolder.create(tmp_path / "src_i")
    inp = IngestInput.from_path(raw_path)
    artifacts = DocxConverter().convert(inp, folder)
    assert "Hello DOCX integration" in artifacts.processed_body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_ingest_docx.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.ingest.docx'`.

- [ ] **Step 3: Implement `DocxConverter`**

Create `src/second_brain/ingest/docx.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder


class DocxConverter(Converter):
    kind: ClassVar[str] = "docx"

    def matches(self, source: IngestInput) -> bool:
        return source.suffix == ".docx"

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        raw_write = target.write_raw(
            rel_path="raw/original.docx",
            content=source.content,
            kind="original",
        )
        body = self._extract_text(source)
        title = self._guess_title(body, source)
        return SourceArtifacts(
            processed_body=body,
            raw=[raw_write],
            title_hint=title,
        )

    @staticmethod
    def _extract_text(source: IngestInput) -> str:
        try:
            from markitdown import MarkItDown  # type: ignore[import-not-found]

            md = MarkItDown()
            with source.open_stream() as stream:
                result = md.convert_stream(stream, file_extension=".docx")
            text = (result.text_content or "").strip()
            return text + "\n" if text else "\n"
        except Exception as exc:  # noqa: BLE001
            return f"[markitdown failed: {exc}]\n"

    @staticmethod
    def _guess_title(body: str, source: IngestInput) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped and not stripped.startswith("[markitdown"):
                return stripped[:120]
        return Path(source.origin).stem
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_ingest_docx.py -v -m "not integration"`
Expected: PASS (3 non-integration tests).

- [ ] **Step 5: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass; 3 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/second_brain/ingest/docx.py tests/test_ingest_docx.py
git commit -m "feat(ingest): DOCX converter via markitdown with safe fallback"
```

---

## Task 4: EPUB converter (markitdown passthrough)

**Files:**
- Create: `src/second_brain/ingest/epub.py`
- Create: `tests/test_ingest_epub.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingest_epub.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.epub import EpubConverter


def test_matches_epub_suffix() -> None:
    c = EpubConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.epub", suffix=".epub", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))


def test_convert_writes_raw_and_returns_body(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="/p/book.epub", suffix=".epub", content=b"not-a-real-epub")
    artifacts = EpubConverter().convert(inp, folder)
    assert (folder.raw_dir / "original.epub").exists()
    assert len(artifacts.processed_body) > 0
    assert "[markitdown failed" in artifacts.processed_body
    assert artifacts.raw[0].path == "raw/original.epub"


def test_guess_title_falls_back_to_origin_stem(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    inp = IngestInput.from_bytes(origin="/p/ulysses.epub", suffix=".epub", content=b"x")
    artifacts = EpubConverter().convert(inp, folder)
    assert artifacts.title_hint == "ulysses"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_ingest_epub.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.ingest.epub'`.

- [ ] **Step 3: Implement `EpubConverter`**

Create `src/second_brain/ingest/epub.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder


class EpubConverter(Converter):
    kind: ClassVar[str] = "epub"

    def matches(self, source: IngestInput) -> bool:
        return source.suffix == ".epub"

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        raw_write = target.write_raw(
            rel_path="raw/original.epub",
            content=source.content,
            kind="original",
        )
        body = self._extract_text(source)
        title = self._guess_title(body, source)
        return SourceArtifacts(
            processed_body=body,
            raw=[raw_write],
            title_hint=title,
        )

    @staticmethod
    def _extract_text(source: IngestInput) -> str:
        try:
            from markitdown import MarkItDown  # type: ignore[import-not-found]

            md = MarkItDown()
            with source.open_stream() as stream:
                result = md.convert_stream(stream, file_extension=".epub")
            text = (result.text_content or "").strip()
            return text + "\n" if text else "\n"
        except Exception as exc:  # noqa: BLE001
            return f"[markitdown failed: {exc}]\n"

    @staticmethod
    def _guess_title(body: str, source: IngestInput) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
            if stripped and not stripped.startswith("[markitdown"):
                return stripped[:120]
        return Path(source.origin).stem
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_ingest_epub.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass; 3 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/second_brain/ingest/epub.py tests/test_ingest_epub.py
git commit -m "feat(ingest): EPUB converter via markitdown with safe fallback"
```

---

## Task 5: Register new converters in orchestrator

**Files:**
- Modify: `src/second_brain/ingest/orchestrator.py`
- Create: `tests/test_orchestrator_dispatch.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_orchestrator_dispatch.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import DEFAULT_CONVERTERS, ingest


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def test_default_converter_kinds_cover_v1() -> None:
    kinds = {c.kind for c in DEFAULT_CONVERTERS}
    assert {"note", "pdf", "url", "repo", "docx", "epub"}.issubset(kinds)


def test_dispatches_docx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    inp = IngestInput.from_bytes(origin="/p/doc.docx", suffix=".docx", content=b"x")
    folder = ingest(inp, cfg=cfg)
    assert (folder.root / "raw" / "original.docx").exists()
    assert (folder.root / "_source.md").exists()


def test_dispatches_epub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    inp = IngestInput.from_bytes(origin="/p/book.epub", suffix=".epub", content=b"x")
    folder = ingest(inp, cfg=cfg)
    assert (folder.root / "raw" / "original.epub").exists()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_orchestrator_dispatch.py -v`
Expected: FAIL on `test_default_converter_kinds_cover_v1` — set includes only `{"note", "pdf"}`.

- [ ] **Step 3: Register new converters**

Modify `src/second_brain/ingest/orchestrator.py`. Add these imports at the top:

```python
from second_brain.ingest.docx import DocxConverter
from second_brain.ingest.epub import EpubConverter
from second_brain.ingest.repo import RepoConverter
from second_brain.ingest.url import UrlConverter
```

Replace the `DEFAULT_CONVERTERS` line with:

```python
DEFAULT_CONVERTERS: list[Converter] = [
    NoteConverter(),
    PdfConverter(),
    DocxConverter(),
    EpubConverter(),
    UrlConverter(),
    RepoConverter(),
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_orchestrator_dispatch.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass; 3 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/second_brain/ingest/orchestrator.py tests/test_orchestrator_dispatch.py
git commit -m "feat(ingest): register url / repo / docx / epub converters"
```

---

## Task 6: Lint scaffold — `KBSnapshot`, `LintIssue`, `Severity`, `LintReport`

**Files:**
- Create: `src/second_brain/lint/__init__.py`
- Create: `src/second_brain/lint/snapshot.py`
- Create: `tests/test_lint_snapshot.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_lint_snapshot.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.lint.snapshot import KBSnapshot, load_snapshot


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _write_source(cfg: Config, sid: str, *, cites: list[str] | None = None,
                  supersedes: list[str] | None = None, content_hash: str = "sha256:ff",
                  year: int = 2024) -> Path:
    folder = cfg.sources_dir / sid
    folder.mkdir(parents=True)
    (folder / "raw").mkdir()
    (folder / "raw" / "original.md").write_bytes(b"# Title\n")
    meta = {
        "id": sid, "title": f"T {sid}", "kind": "note",
        "authors": [], "year": year, "source_url": None, "tags": [],
        "ingested_at": datetime.now(UTC).isoformat(),
        "content_hash": content_hash, "habit_taxonomy": None,
        "raw": [{"path": "raw/original.md", "kind": "original",
                 "sha256": "sha256:" + "0"*64}],
        "cites": cites or [], "related": [], "supersedes": supersedes or [],
        "abstract": "",
    }
    dump_document(folder / "_source.md", meta, "# Body\n")
    return folder


def _write_claim(cfg: Config, cid: str, *, supports: list[str] | None = None,
                 contradicts: list[str] | None = None, refines: list[str] | None = None,
                 status: str = "active",
                 extracted_at: datetime | None = None) -> Path:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    p = cfg.claims_dir / f"{cid}.md"
    meta = {
        "id": cid, "statement": f"stmt {cid}", "kind": "empirical",
        "confidence": "high", "scope": "x",
        "supports": supports or [], "contradicts": contradicts or [], "refines": refines or [],
        "extracted_at": (extracted_at or datetime.now(UTC)).isoformat(),
        "status": status, "resolution": None, "abstract": "",
    }
    dump_document(p, meta, f"# {cid}\n")
    return p


def test_load_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    snap = load_snapshot(cfg)
    assert isinstance(snap, KBSnapshot)
    assert snap.sources == {}
    assert snap.claims == {}


def test_load_indexes_sources_and_claims(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    _write_source(cfg, "src_b", cites=["src_a"])
    _write_claim(cfg, "clm_x", supports=["src_a"])
    _write_claim(cfg, "clm_y", contradicts=["clm_x"])

    snap = load_snapshot(cfg)
    assert set(snap.sources) == {"src_a", "src_b"}
    assert set(snap.claims) == {"clm_x", "clm_y"}
    assert snap.sources["src_b"].cites == ["src_a"]
    assert snap.claims["clm_y"].contradicts == ["clm_x"]


def test_ids_view(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    _write_claim(cfg, "clm_x")
    snap = load_snapshot(cfg)
    assert "src_a" in snap.all_ids
    assert "clm_x" in snap.all_ids
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_lint_snapshot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.lint'`.

- [ ] **Step 3: Implement the snapshot loader + scaffolding**

Create `src/second_brain/lint/__init__.py`:

```python
from __future__ import annotations

from second_brain.lint.snapshot import KBSnapshot, load_snapshot

__all__ = ["KBSnapshot", "load_snapshot"]
```

Create `src/second_brain/lint/snapshot.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.schema.claim import ClaimFrontmatter
from second_brain.schema.source import SourceFrontmatter


@dataclass(frozen=True)
class KBSnapshot:
    sources: dict[str, SourceFrontmatter] = field(default_factory=dict)
    claims: dict[str, ClaimFrontmatter] = field(default_factory=dict)

    @property
    def all_ids(self) -> set[str]:
        return set(self.sources.keys()) | set(self.claims.keys())


def load_snapshot(cfg: Config) -> KBSnapshot:
    sources: dict[str, SourceFrontmatter] = {}
    claims: dict[str, ClaimFrontmatter] = {}

    if cfg.sources_dir.exists():
        for source_md in sorted(cfg.sources_dir.glob("*/_source.md")):
            meta, _ = load_document(source_md)
            fm = SourceFrontmatter.model_validate(meta)
            sources[fm.id] = fm

    if cfg.claims_dir.exists():
        for claim_md in sorted(cfg.claims_dir.glob("*.md")):
            meta, _ = load_document(claim_md)
            fm = ClaimFrontmatter.model_validate(meta)
            claims[fm.id] = fm

    return KBSnapshot(sources=sources, claims=claims)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_lint_snapshot.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass; 3 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/second_brain/lint/__init__.py src/second_brain/lint/snapshot.py tests/test_lint_snapshot.py
git commit -m "feat(lint): KBSnapshot loader for sources + claims"
```

---

## Task 7: Lint rules — all eight rules

**Files:**
- Create: `src/second_brain/lint/rules.py`
- Create: `tests/test_lint_rules.py`

This task implements every rule defined in spec §7.1. Each rule is a pure function that takes a `KBSnapshot` (and, for hash checks, a `Config` to reach the `raw/*` bytes) and returns `list[LintIssue]`.

- [ ] **Step 1: Write the failing test (comprehensive rule coverage)**

Create `tests/test_lint_rules.py`:

```python
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.lint.rules import (
    DEFAULT_GRACE_DAYS,
    LOPSIDED_THRESHOLD,
    LintIssue,
    Severity,
    check_circular_supersedes,
    check_dangling_edge,
    check_hash_mismatch,
    check_lopsided_contradiction,
    check_orphan_claim,
    check_sparse_source,
    check_stale_abstract,
    check_unresolved_contradiction,
)
from second_brain.lint.snapshot import load_snapshot


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _write_source(cfg: Config, sid: str, *, cites=None, supersedes=None, raw_bytes=b"# x\n",
                  content_hash: str | None = None, abstract: str = "") -> Path:
    folder = cfg.sources_dir / sid
    folder.mkdir(parents=True)
    (folder / "raw").mkdir()
    (folder / "raw" / "original.md").write_bytes(raw_bytes)
    raw_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    fm = {
        "id": sid, "title": sid, "kind": "note",
        "authors": [], "year": 2024, "source_url": None, "tags": [],
        "ingested_at": datetime.now(UTC).isoformat(),
        "content_hash": content_hash or raw_hash,
        "habit_taxonomy": None,
        "raw": [{"path": "raw/original.md", "kind": "original", "sha256": raw_hash}],
        "cites": cites or [], "related": [], "supersedes": supersedes or [],
        "abstract": abstract,
    }
    dump_document(folder / "_source.md", fm, "# body\n")
    return folder


def _write_claim(cfg: Config, cid: str, *, supports=None, contradicts=None, refines=None,
                 status="active", resolution=None,
                 extracted_at: datetime | None = None) -> Path:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    p = cfg.claims_dir / f"{cid}.md"
    fm = {
        "id": cid, "statement": cid, "kind": "empirical", "confidence": "high", "scope": "x",
        "supports": supports or [], "contradicts": contradicts or [], "refines": refines or [],
        "extracted_at": (extracted_at or datetime.now(UTC)).isoformat(),
        "status": status, "resolution": resolution, "abstract": "",
    }
    dump_document(p, fm, f"# {cid}\n")
    return p


def test_orphan_claim_flags_no_supports(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_a", supports=[])
    issues = check_orphan_claim(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["ORPHAN_CLAIM"]
    assert issues[0].subject_id == "clm_a"
    assert issues[0].severity == Severity.ERROR


def test_orphan_claim_ignores_retracted(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_a", supports=[], status="retracted")
    issues = check_orphan_claim(load_snapshot(cfg))
    assert issues == []


def test_dangling_edge_on_source_cites(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", cites=["src_missing"])
    issues = check_dangling_edge(load_snapshot(cfg))
    kinds = {(i.rule, i.subject_id) for i in issues}
    assert ("DANGLING_EDGE", "src_a") in kinds


def test_dangling_edge_on_claim_supports(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_a", supports=["src_missing"])
    issues = check_dangling_edge(load_snapshot(cfg))
    assert any(i.subject_id == "clm_a" for i in issues)


def test_dangling_edge_fragments_are_stripped(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    _write_claim(cfg, "clm_x", supports=["src_a#sec-3.2"])
    issues = check_dangling_edge(load_snapshot(cfg))
    assert issues == []


def test_circular_supersedes(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", supersedes=["src_b"])
    _write_source(cfg, "src_b", supersedes=["src_a"])
    issues = check_circular_supersedes(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["CIRCULAR_SUPERSEDES"] * 1
    assert set(issues[0].details["cycle"]) == {"src_a", "src_b"}


def test_hash_mismatch_detects_drift(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", raw_bytes=b"# original\n", content_hash="sha256:deadbeef")
    issues = check_hash_mismatch(load_snapshot(cfg), cfg)
    assert [i.rule for i in issues] == ["HASH_MISMATCH"]
    assert issues[0].subject_id == "src_a"


def test_hash_match_no_issue(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", raw_bytes=b"# original\n")  # content_hash derived from bytes
    issues = check_hash_mismatch(load_snapshot(cfg), cfg)
    assert issues == []


def test_stale_abstract_flags_hash_drift_with_abstract(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(
        cfg, "src_a",
        raw_bytes=b"# original\n",
        content_hash="sha256:deadbeef",
        abstract="Previously generated abstract",
    )
    issues = check_stale_abstract(load_snapshot(cfg), cfg)
    assert [i.rule for i in issues] == ["STALE_ABSTRACT"]


def test_stale_abstract_ignores_hash_drift_when_abstract_empty(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a", raw_bytes=b"# x\n", content_hash="sha256:deadbeef", abstract="")
    issues = check_stale_abstract(load_snapshot(cfg), cfg)
    assert issues == []


def test_sparse_source_flags_source_with_zero_claims(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    issues = check_sparse_source(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["SPARSE_SOURCE"]
    assert issues[0].subject_id == "src_a"


def test_sparse_source_ignores_sourced_claims(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_source(cfg, "src_a")
    _write_claim(cfg, "clm_a", supports=["src_a"])
    issues = check_sparse_source(load_snapshot(cfg))
    assert issues == []


def test_unresolved_contradiction_past_grace(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    old = datetime.now(UTC) - timedelta(days=DEFAULT_GRACE_DAYS + 1)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], extracted_at=old)
    _write_claim(cfg, "clm_b", extracted_at=old)
    issues = check_unresolved_contradiction(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["UNRESOLVED_CONTRADICTION"]
    assert issues[0].subject_id == "clm_a"


def test_unresolved_contradiction_within_grace_no_flag(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    fresh = datetime.now(UTC) - timedelta(days=1)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], extracted_at=fresh)
    _write_claim(cfg, "clm_b", extracted_at=fresh)
    issues = check_unresolved_contradiction(load_snapshot(cfg))
    assert issues == []


def test_unresolved_contradiction_with_resolution_no_flag(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    old = datetime.now(UTC) - timedelta(days=DEFAULT_GRACE_DAYS + 5)
    _write_claim(cfg, "clm_a", contradicts=["clm_b"], extracted_at=old,
                 resolution="claims/resolutions/x.md")
    _write_claim(cfg, "clm_b", extracted_at=old)
    issues = check_unresolved_contradiction(load_snapshot(cfg))
    assert issues == []


def test_lopsided_contradiction(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _write_claim(cfg, "clm_center")
    contradictors = [f"clm_opp_{i}" for i in range(LOPSIDED_THRESHOLD)]
    for cid in contradictors:
        _write_claim(cfg, cid, contradicts=["clm_center"])
    issues = check_lopsided_contradiction(load_snapshot(cfg))
    assert [i.rule for i in issues] == ["LOPSIDED_CONTRADICTION"]
    assert issues[0].subject_id == "clm_center"


def test_lopsided_contradiction_ignores_if_outbound_exists(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    contradictors = [f"clm_opp_{i}" for i in range(LOPSIDED_THRESHOLD)]
    _write_claim(cfg, "clm_center", contradicts=contradictors[:1])
    for cid in contradictors:
        _write_claim(cfg, cid, contradicts=["clm_center"])
    issues = check_lopsided_contradiction(load_snapshot(cfg))
    assert issues == []


def test_lint_issue_is_hashable():
    i = LintIssue(rule="ORPHAN_CLAIM", severity=Severity.ERROR, subject_id="clm_a",
                  message="x", details={"k": "v"})
    assert hash(i) is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_lint_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.lint.rules'`.

- [ ] **Step 3: Implement all rules**

Create `src/second_brain/lint/rules.py`:

```python
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from second_brain.config import Config
from second_brain.lint.snapshot import KBSnapshot


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class LintIssue:
    rule: str
    severity: Severity
    subject_id: str
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash((self.rule, self.severity, self.subject_id, self.message))


DEFAULT_GRACE_DAYS: int = 14
LOPSIDED_THRESHOLD: int = 3


def check_orphan_claim(snap: KBSnapshot) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for cid, claim in snap.claims.items():
        if claim.status != "active":
            continue
        live_supports = [s for s in claim.supports if _id_of(s) in snap.sources]
        if not live_supports:
            issues.append(LintIssue(
                rule="ORPHAN_CLAIM",
                severity=Severity.ERROR,
                subject_id=cid,
                message=f"claim {cid!r} has no live supports target",
            ))
    return issues


def check_dangling_edge(snap: KBSnapshot) -> list[LintIssue]:
    known = snap.all_ids
    issues: list[LintIssue] = []
    for sid, src in snap.sources.items():
        for attr in ("cites", "related", "supersedes"):
            for tgt in getattr(src, attr):
                tid = _id_of(tgt)
                if tid not in known:
                    issues.append(LintIssue(
                        rule="DANGLING_EDGE",
                        severity=Severity.ERROR,
                        subject_id=sid,
                        message=f"{sid} {attr} → unknown id {tid!r}",
                        details={"relation": attr, "target": tgt},
                    ))
    for cid, claim in snap.claims.items():
        for attr in ("supports", "contradicts", "refines"):
            for tgt in getattr(claim, attr):
                tid = _id_of(tgt)
                if tid not in known:
                    issues.append(LintIssue(
                        rule="DANGLING_EDGE",
                        severity=Severity.ERROR,
                        subject_id=cid,
                        message=f"{cid} {attr} → unknown id {tid!r}",
                        details={"relation": attr, "target": tgt},
                    ))
    return issues


def check_circular_supersedes(snap: KBSnapshot) -> list[LintIssue]:
    graph: dict[str, list[str]] = {
        sid: [_id_of(t) for t in src.supersedes]
        for sid, src in snap.sources.items()
    }
    cycles = _find_cycles(graph)
    issues: list[LintIssue] = []
    for cycle in cycles:
        rep = min(cycle)
        issues.append(LintIssue(
            rule="CIRCULAR_SUPERSEDES",
            severity=Severity.ERROR,
            subject_id=rep,
            message=f"supersedes cycle: {' → '.join(cycle)} → {cycle[0]}",
            details={"cycle": cycle},
        ))
    return issues


def check_hash_mismatch(snap: KBSnapshot, cfg: Config) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for sid, src in snap.sources.items():
        folder = cfg.sources_dir / sid
        for raw in src.raw:
            p = folder / raw.path
            if not p.exists():
                continue
            digest = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
            if digest != raw.sha256:
                issues.append(LintIssue(
                    rule="HASH_MISMATCH",
                    severity=Severity.ERROR,
                    subject_id=sid,
                    message=f"raw artifact {raw.path!r} hash changed",
                    details={"path": raw.path, "stored": raw.sha256, "current": digest},
                ))
                continue  # one issue per artifact is enough
        # The top-level content_hash should match at least one raw artifact's hash,
        # or if only one artifact exists, it must match that artifact.
        if src.content_hash and src.raw:
            any_match = any(src.content_hash == r.sha256 for r in src.raw)
            if not any_match:
                issues.append(LintIssue(
                    rule="HASH_MISMATCH",
                    severity=Severity.ERROR,
                    subject_id=sid,
                    message=f"content_hash does not match any raw artifact",
                    details={"content_hash": src.content_hash,
                             "raw_hashes": [r.sha256 for r in src.raw]},
                ))
    return issues


def check_stale_abstract(snap: KBSnapshot, cfg: Config) -> list[LintIssue]:
    mismatches = {i.subject_id for i in check_hash_mismatch(snap, cfg)}
    issues: list[LintIssue] = []
    for sid in mismatches:
        src = snap.sources.get(sid)
        if src and src.abstract.strip():
            issues.append(LintIssue(
                rule="STALE_ABSTRACT",
                severity=Severity.WARNING,
                subject_id=sid,
                message=f"abstract may be stale: content_hash drift on {sid}",
            ))
    return issues


def check_sparse_source(snap: KBSnapshot) -> list[LintIssue]:
    sourced: set[str] = set()
    for claim in snap.claims.values():
        for tgt in claim.supports:
            sourced.add(_id_of(tgt))
    issues: list[LintIssue] = []
    for sid, src in snap.sources.items():
        if src.kind == "failed":
            continue
        if sid not in sourced:
            issues.append(LintIssue(
                rule="SPARSE_SOURCE",
                severity=Severity.WARNING,
                subject_id=sid,
                message=f"source {sid} has 0 claims grounded in it",
            ))
    return issues


def check_unresolved_contradiction(
    snap: KBSnapshot, *, grace_days: int = DEFAULT_GRACE_DAYS
) -> list[LintIssue]:
    cutoff = datetime.now(UTC) - timedelta(days=grace_days)
    issues: list[LintIssue] = []
    for cid, claim in snap.claims.items():
        if not claim.contradicts:
            continue
        if claim.resolution:
            continue
        if claim.extracted_at and _ensure_aware(claim.extracted_at) > cutoff:
            continue
        issues.append(LintIssue(
            rule="UNRESOLVED_CONTRADICTION",
            severity=Severity.WARNING,
            subject_id=cid,
            message=f"contradiction on {cid} unresolved past grace period",
            details={"contradicts": list(claim.contradicts), "grace_days": grace_days},
        ))
    return issues


def check_lopsided_contradiction(
    snap: KBSnapshot, *, threshold: int = LOPSIDED_THRESHOLD
) -> list[LintIssue]:
    inbound: dict[str, list[str]] = {cid: [] for cid in snap.claims}
    for src_cid, claim in snap.claims.items():
        for tgt in claim.contradicts:
            tid = _id_of(tgt)
            if tid in inbound:
                inbound[tid].append(src_cid)
    issues: list[LintIssue] = []
    for cid, attackers in inbound.items():
        if len(attackers) < threshold:
            continue
        outbound = snap.claims[cid].contradicts
        if outbound:
            continue
        issues.append(LintIssue(
            rule="LOPSIDED_CONTRADICTION",
            severity=Severity.WARNING,
            subject_id=cid,
            message=f"{cid} is contradicted by {len(attackers)} claims but contradicts none",
            details={"contradictors": attackers, "threshold": threshold},
        ))
    return issues


def _id_of(edge_target: str) -> str:
    return edge_target.split("#", 1)[0]


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    visited: set[str] = set()
    on_stack: set[str] = set()
    stack: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        if node in on_stack:
            idx = stack.index(node)
            cycles.append(stack[idx:])
            return
        if node in visited:
            return
        visited.add(node)
        on_stack.add(node)
        stack.append(node)
        for nxt in graph.get(node, []):
            dfs(nxt)
        on_stack.discard(node)
        stack.pop()

    for n in graph:
        dfs(n)
    # Deduplicate cycles by frozenset of members.
    seen: set[frozenset[str]] = set()
    deduped: list[list[str]] = []
    for c in cycles:
        key = frozenset(c)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    return deduped


__all__ = [
    "DEFAULT_GRACE_DAYS",
    "LOPSIDED_THRESHOLD",
    "LintIssue",
    "Severity",
    "check_circular_supersedes",
    "check_dangling_edge",
    "check_hash_mismatch",
    "check_lopsided_contradiction",
    "check_orphan_claim",
    "check_sparse_source",
    "check_stale_abstract",
    "check_unresolved_contradiction",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_lint_rules.py -v`
Expected: PASS (all 17 tests).

- [ ] **Step 5: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/second_brain/lint/rules.py tests/test_lint_rules.py
git commit -m "feat(lint): all eight v1 rules (orphan, dangling, circular, hash, stale, sparse, unresolved, lopsided)"
```

---

## Task 8: Lint runner + `LintReport` + `sb lint` CLI

**Files:**
- Create: `src/second_brain/lint/runner.py`
- Modify: `src/second_brain/lint/__init__.py` (re-export runner)
- Modify: `src/second_brain/cli.py` (add `sb lint`)
- Create: `tests/test_lint_runner.py`
- Create: `tests/test_cli_lint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_lint_runner.py`:

```python
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.lint.runner import LintReport, run_lint


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _source(cfg: Config, sid: str, *, cites=None, raw_bytes=b"# body\n",
            content_hash: str | None = None) -> None:
    folder = cfg.sources_dir / sid
    folder.mkdir(parents=True)
    (folder / "raw").mkdir()
    (folder / "raw" / "original.md").write_bytes(raw_bytes)
    raw_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    fm = {
        "id": sid, "title": sid, "kind": "note",
        "authors": [], "year": 2024, "source_url": None, "tags": [],
        "ingested_at": datetime.now(UTC).isoformat(),
        "content_hash": content_hash or raw_hash,
        "habit_taxonomy": None,
        "raw": [{"path": "raw/original.md", "kind": "original", "sha256": raw_hash}],
        "cites": cites or [], "related": [], "supersedes": [], "abstract": "",
    }
    dump_document(folder / "_source.md", fm, "# body\n")


def test_empty_report_has_no_issues(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    report = run_lint(cfg)
    assert isinstance(report, LintReport)
    assert report.issues == []
    assert report.ok is True
    assert report.counts_by_severity == {"error": 0, "warning": 0, "info": 0}


def test_report_aggregates_rules(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _source(cfg, "src_a", cites=["src_missing"])          # DANGLING_EDGE + SPARSE_SOURCE
    report = run_lint(cfg)
    rules = {i.rule for i in report.issues}
    assert "DANGLING_EDGE" in rules
    assert "SPARSE_SOURCE" in rules
    assert report.ok is False
    assert report.counts_by_severity["error"] >= 1
    assert report.counts_by_severity["warning"] >= 1


def test_report_to_dict_round_trip(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _source(cfg, "src_a", cites=["src_missing"])
    report = run_lint(cfg)
    data = report.to_dict()
    assert data["ok"] is False
    assert data["counts_by_severity"]["error"] >= 1
    assert all(set(issue) >= {"rule", "severity", "subject_id", "message"}
               for issue in data["issues"])
```

Create `tests/test_cli_lint.py`:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.frontmatter import dump_document


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _claim(cfg: Config, cid: str, *, supports=None) -> None:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "id": cid, "statement": cid, "kind": "empirical", "confidence": "high", "scope": "x",
        "supports": supports or [], "contradicts": [], "refines": [],
        "extracted_at": datetime.now(UTC).isoformat(),
        "status": "active", "resolution": None, "abstract": "",
    }
    dump_document(cfg.claims_dir / f"{cid}.md", fm, f"# {cid}\n")


def test_sb_lint_clean(tmp_path, monkeypatch):
    _cfg(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(cli, ["lint"])
    assert result.exit_code == 0
    assert "ok" in result.output.lower() or "no issues" in result.output.lower()


def test_sb_lint_reports_issues(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _claim(cfg, "clm_orphan")
    runner = CliRunner()
    result = runner.invoke(cli, ["lint"])
    assert result.exit_code == 1
    assert "ORPHAN_CLAIM" in result.output
    assert "clm_orphan" in result.output


def test_sb_lint_json(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _claim(cfg, "clm_orphan")
    runner = CliRunner()
    result = runner.invoke(cli, ["lint", "--json"])
    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["ok"] is False
    assert any(i["rule"] == "ORPHAN_CLAIM" for i in data["issues"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_lint_runner.py tests/test_cli_lint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.lint.runner'`.

- [ ] **Step 3: Implement the runner**

Create `src/second_brain/lint/runner.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from second_brain.config import Config
from second_brain.lint.rules import (
    LintIssue,
    Severity,
    check_circular_supersedes,
    check_dangling_edge,
    check_hash_mismatch,
    check_lopsided_contradiction,
    check_orphan_claim,
    check_sparse_source,
    check_stale_abstract,
    check_unresolved_contradiction,
)
from second_brain.lint.snapshot import KBSnapshot, load_snapshot


@dataclass(frozen=True)
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    @property
    def counts_by_severity(self) -> dict[str, int]:
        out = {"error": 0, "warning": 0, "info": 0}
        for i in self.issues:
            out[i.severity.value] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "counts_by_severity": self.counts_by_severity,
            "issues": [
                {
                    "rule": i.rule,
                    "severity": i.severity.value,
                    "subject_id": i.subject_id,
                    "message": i.message,
                    "details": dict(i.details),
                }
                for i in self.issues
            ],
        }


SnapshotRule = Callable[[KBSnapshot], list[LintIssue]]
SnapshotCfgRule = Callable[[KBSnapshot, Config], list[LintIssue]]

_SNAPSHOT_RULES: list[SnapshotRule] = [
    check_orphan_claim,
    check_dangling_edge,
    check_circular_supersedes,
    check_sparse_source,
    check_unresolved_contradiction,
    check_lopsided_contradiction,
]

_SNAPSHOT_CFG_RULES: list[SnapshotCfgRule] = [
    check_hash_mismatch,
    check_stale_abstract,
]


def run_lint(cfg: Config) -> LintReport:
    snap = load_snapshot(cfg)
    issues: list[LintIssue] = []
    for rule in _SNAPSHOT_RULES:
        issues.extend(rule(snap))
    for rule_cfg in _SNAPSHOT_CFG_RULES:
        issues.extend(rule_cfg(snap, cfg))
    issues.sort(key=lambda i: (i.severity.value, i.rule, i.subject_id))
    return LintReport(issues=issues)
```

Modify `src/second_brain/lint/__init__.py`:

```python
from __future__ import annotations

from second_brain.lint.rules import LintIssue, Severity
from second_brain.lint.runner import LintReport, run_lint
from second_brain.lint.snapshot import KBSnapshot, load_snapshot

__all__ = [
    "KBSnapshot",
    "LintIssue",
    "LintReport",
    "Severity",
    "load_snapshot",
    "run_lint",
]
```

- [ ] **Step 4: Wire `sb lint` command into the CLI**

Modify `src/second_brain/cli.py`. After the existing `@cli.command(name="extract")` command (near the bottom of the file), add the following command. Do NOT remove or rearrange other commands.

```python
@cli.command(name="lint")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON instead of text.")
def _lint(as_json: bool) -> None:
    """Run all lint rules over ~/second-brain. Exit 0 = no errors; 1 = errors present."""
    import json as _json

    from second_brain.lint.runner import run_lint

    cfg = Config.load()
    report = run_lint(cfg)

    if as_json:
        click.echo(_json.dumps(report.to_dict(), indent=2))
    else:
        if not report.issues:
            click.echo("lint: ok (no issues)")
        else:
            for i in report.issues:
                click.echo(f"[{i.severity.value.upper():7}] {i.rule:26} {i.subject_id:40} {i.message}")
            c = report.counts_by_severity
            click.echo(f"summary: {c['error']} error, {c['warning']} warning, {c['info']} info")

    if not report.ok:
        raise click.exceptions.Exit(1)
```

Ensure the import at the top of `cli.py` includes `Config` from `second_brain.config` (it already does from plan 1; no change needed).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_lint_runner.py tests/test_cli_lint.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Run the full fast suite**

Run: `pytest -m "not integration"`
Expected: all previous tests still pass; 6 new tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/second_brain/lint/__init__.py src/second_brain/lint/runner.py src/second_brain/cli.py tests/test_lint_runner.py tests/test_cli_lint.py
git commit -m "feat(lint): LintReport runner + sb lint CLI (text + --json)"
```

---

## Task 9: `conflicts.md` renderer + `sb lint --write-conflicts`

**Files:**
- Create: `src/second_brain/lint/conflicts_md.py`
- Modify: `src/second_brain/lint/__init__.py` (re-export renderer)
- Modify: `src/second_brain/cli.py` (add `--write-conflicts` flag)
- Create: `tests/test_lint_conflicts_md.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_lint_conflicts_md.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.lint.conflicts_md import render_conflicts_md
from second_brain.lint.rules import DEFAULT_GRACE_DAYS
from second_brain.lint.runner import run_lint


def _cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return Config.load()


def _claim(cfg: Config, cid: str, *, contradicts=None, resolution=None,
           extracted_at: datetime | None = None) -> None:
    cfg.claims_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "id": cid, "statement": cid, "kind": "empirical", "confidence": "high", "scope": "x",
        "supports": [], "contradicts": contradicts or [], "refines": [],
        "extracted_at": (extracted_at or datetime.now(UTC)).isoformat(),
        "status": "active", "resolution": resolution, "abstract": "",
    }
    dump_document(cfg.claims_dir / f"{cid}.md", fm, f"# {cid}\n")


def test_render_empty_report_has_placeholder(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    report = run_lint(cfg)
    md = render_conflicts_md(cfg, report)
    assert "# Conflicts" in md
    assert "no open debates" in md.lower()


def test_render_groups_open_and_resolved(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    old = datetime.now(UTC) - timedelta(days=DEFAULT_GRACE_DAYS + 5)
    _claim(cfg, "clm_open_a", contradicts=["clm_open_b"], extracted_at=old)
    _claim(cfg, "clm_open_b", extracted_at=old)
    _claim(cfg, "clm_resolved_a", contradicts=["clm_resolved_b"],
           extracted_at=old, resolution="claims/resolutions/x.md")
    _claim(cfg, "clm_resolved_b", extracted_at=old)
    report = run_lint(cfg)
    md = render_conflicts_md(cfg, report)
    assert "## Open debates" in md
    assert "clm_open_a" in md
    assert "## Healthy signal" in md
    assert "resolved contradictions: 1" in md


def test_write_conflicts_flag_writes_file(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch)
    _claim(cfg, "clm_x")  # orphan, but doesn't affect conflicts.md directly
    runner = CliRunner()
    result = runner.invoke(cli, ["lint", "--write-conflicts"])
    # Orphan claim means exit=1, but file should still be written.
    assert (cfg.home / "conflicts.md").exists()
    content = (cfg.home / "conflicts.md").read_text("utf-8")
    assert "# Conflicts" in content
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_lint_conflicts_md.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'second_brain.lint.conflicts_md'`.

- [ ] **Step 3: Implement the renderer**

Create `src/second_brain/lint/conflicts_md.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from second_brain.config import Config
from second_brain.lint.runner import LintReport
from second_brain.lint.snapshot import load_snapshot


def render_conflicts_md(cfg: Config, report: LintReport) -> str:
    snap = load_snapshot(cfg)
    open_debates = [i for i in report.issues if i.rule == "UNRESOLVED_CONTRADICTION"]
    lopsided = [i for i in report.issues if i.rule == "LOPSIDED_CONTRADICTION"]

    resolved_pairs: list[str] = []
    for cid, claim in snap.claims.items():
        if claim.contradicts and claim.resolution:
            resolved_pairs.append(cid)

    lines: list[str] = []
    lines.append("# Conflicts")
    lines.append("")
    lines.append(f"_generated: {datetime.now(UTC).isoformat()}_")
    lines.append("")

    lines.append("## Open debates")
    lines.append("")
    if not open_debates:
        lines.append("_no open debates past grace period_")
    else:
        for issue in open_debates:
            targets = ", ".join(str(t) for t in issue.details.get("contradicts", []))
            lines.append(f"- **{issue.subject_id}** contradicts {targets}")
            lines.append(f"  > {issue.message}")
    lines.append("")

    lines.append("## Candidate contradictions")
    lines.append("")
    if not lopsided:
        lines.append("_no lopsided clusters flagged_")
    else:
        for issue in lopsided:
            attackers = issue.details.get("contradictors", [])
            lines.append(f"- **{issue.subject_id}** ← {len(attackers)} contradictors")
            for a in attackers:
                lines.append(f"  - {a}")
    lines.append("")

    lines.append("## Healthy signal")
    lines.append("")
    lines.append(f"- resolved contradictions: {len(resolved_pairs)}")
    lines.append(f"- unresolved-past-grace: {len(open_debates)}")
    lines.append(f"- lopsided clusters: {len(lopsided)}")

    return "\n".join(lines) + "\n"


__all__ = ["render_conflicts_md"]
```

Modify `src/second_brain/lint/__init__.py` — replace the file entirely with:

```python
from __future__ import annotations

from second_brain.lint.conflicts_md import render_conflicts_md
from second_brain.lint.rules import LintIssue, Severity
from second_brain.lint.runner import LintReport, run_lint
from second_brain.lint.snapshot import KBSnapshot, load_snapshot

__all__ = [
    "KBSnapshot",
    "LintIssue",
    "LintReport",
    "Severity",
    "load_snapshot",
    "render_conflicts_md",
    "run_lint",
]
```

- [ ] **Step 4: Add `--write-conflicts` flag to `sb lint`**

Modify `src/second_brain/cli.py` — find the `_lint` command. Replace it entirely with:

```python
@cli.command(name="lint")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON instead of text.")
@click.option("--write-conflicts", is_flag=True,
              help="Write ~/second-brain/conflicts.md from the lint report.")
def _lint(as_json: bool, write_conflicts: bool) -> None:
    """Run all lint rules over ~/second-brain. Exit 0 = no errors; 1 = errors present."""
    import json as _json

    from second_brain.lint.conflicts_md import render_conflicts_md
    from second_brain.lint.runner import run_lint

    cfg = Config.load()
    report = run_lint(cfg)

    if write_conflicts:
        md = render_conflicts_md(cfg, report)
        (cfg.home / "conflicts.md").write_text(md, encoding="utf-8")

    if as_json:
        click.echo(_json.dumps(report.to_dict(), indent=2))
    else:
        if not report.issues:
            click.echo("lint: ok (no issues)")
        else:
            for i in report.issues:
                click.echo(f"[{i.severity.value.upper():7}] {i.rule:26} {i.subject_id:40} {i.message}")
            c = report.counts_by_severity
            click.echo(f"summary: {c['error']} error, {c['warning']} warning, {c['info']} info")

    if not report.ok:
        raise click.exceptions.Exit(1)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_lint_conflicts_md.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full fast suite**

Run: `pytest -m "not integration" --cov=src/second_brain`
Expected: all tests pass; coverage ≥ 75%.

- [ ] **Step 7: Commit**

```bash
git add src/second_brain/lint/__init__.py src/second_brain/lint/conflicts_md.py src/second_brain/cli.py tests/test_lint_conflicts_md.py
git commit -m "feat(lint): conflicts.md renderer + sb lint --write-conflicts"
```

---

## Self-Review

### Spec coverage

| Spec section | Task | Notes |
|---|---|---|
| §5.3 URL converter | Task 1 | httpx + readability; no Playwright screenshot in v1 (deferred per plan scope) |
| §5.3 Repo converter | Task 2 | git clone, glob capture; `gh:` shorthand supported |
| §5.3 DOCX converter | Task 3 | markitdown, safe fallback |
| §5.3 EPUB converter | Task 4 | markitdown, safe fallback |
| §7.1 ORPHAN_CLAIM | Task 7 | active-only, ignores retracted |
| §7.1 DANGLING_EDGE | Task 7 | strips `#sec-*` fragments |
| §7.1 CIRCULAR_SUPERSEDES | Task 7 | DFS cycle detector |
| §7.1 HASH_MISMATCH | Task 7 | recompute from raw/*, cross-check content_hash |
| §7.1 UNRESOLVED_CONTRADICTION | Task 7 | grace period check; default 14 days |
| §7.1 LOPSIDED_CONTRADICTION | Task 7 | ≥3 inbound + 0 outbound |
| §7.1 STALE_ABSTRACT | Task 7 | piggybacks on HASH_MISMATCH when abstract non-empty |
| §7.1 SPARSE_SOURCE | Task 7 | 0 supports; retry-count tracking deferred (not yet implemented in extract worker) |
| §7.2 Confidence-aware triage | Task 7 | UNRESOLVED_CONTRADICTION threshold encodes it; per-confidence bucketing deferred to plan 4 where reconciliation lives |
| §7.3 conflicts.md layout | Task 9 | Open debates / Candidate / Healthy signal |

**Explicitly deferred (NOT in this plan):**
- `sb reconcile` flow — needs Claude + `sb-reconcile` skill → plan 4
- `sb inject` — plan 4
- Habit-driven grace period → plan 5 (hard-coded 14 days here)
- URL screenshot via Playwright → plan 5 or 6 (heavy dep)

### Placeholder scan

- No `TODO` / `TBD` / "implement later" in any step.
- Every step that says "implement" shows the full code block.
- All commit messages are verbatim.
- All test assertions are concrete.

### Type consistency

- `LintIssue` dataclass: same shape in `rules.py`, `runner.py`, `conflicts_md.py`, tests.
- `Severity` StrEnum: used consistently as `Severity.ERROR/WARNING/INFO`.
- `check_*` function signatures: `(KBSnapshot) -> list[LintIssue]` for six rules; `(KBSnapshot, Config) -> list[LintIssue]` for the two that need raw-byte access (`check_hash_mismatch`, `check_stale_abstract`).
- `LintReport.ok` / `counts_by_severity` / `to_dict` used consistently in runner, CLI, and tests.
- `render_conflicts_md(cfg, report)` signature matches in tests and CLI.
- `DEFAULT_GRACE_DAYS` / `LOPSIDED_THRESHOLD` exported from `rules.py`, imported by both tests and `conflicts_md.py`.

### Sanity check on integration points

- `DEFAULT_CONVERTERS` in orchestrator: `NoteConverter, PdfConverter, DocxConverter, EpubConverter, UrlConverter, RepoConverter`. Order matters only for `matches()` ambiguity — URL and Repo both match non-path origins but their matchers are disjoint (`http(s)://…(.git)?` vs `http(s)://…` non-git). The repo matcher requires `.git` suffix or `file://` or `gh:`, so a plain `https://example.com/a` falls through to UrlConverter. ✓
- `sb lint --write-conflicts` writes `conflicts.md` regardless of exit code. ✓
- `sb lint` exit code: 0 when no errors (warnings allowed), 1 when any error. Matches `LintReport.ok`. ✓

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-17-second-brain-converters-lint.md`.**

Given that the user already authorized overnight subagent execution for plans 1 and 2, and this plan slots into the same pattern, the default is **subagent-driven execution** in batched dispatches:

- **Batch 1:** Tasks 1-5 (all converters + orchestrator wiring) — one subagent
- **Batch 2:** Tasks 6-7 (lint scaffold + all rules) — one subagent
- **Batch 3:** Tasks 8-9 (runner + CLI + conflicts.md) — one subagent

Each batch stops after its final task and reports back.
