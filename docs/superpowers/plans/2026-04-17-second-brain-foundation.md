# Second Brain — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `second-brain/` Python package, `sb` CLI, markdown-as-truth schema, deterministic reindex (markdown → DuckDB + FTS5), and end-to-end ingest for PDF + note converters. Produces a working KB that ingests artifacts and rebuilds the index.

**Architecture:** A standalone Python package (`second_brain`) with a Click CLI (`sb`). Source of truth is YAML-frontmatter markdown on disk under `~/second-brain/`. Indexes are rebuildable derivations in `.sb/` (DuckDB for graph + analytics, SQLite FTS5 for BM25). Ingest pipeline: `IngestInput` → `Converter` → `SourceFolder` → `orchestrator` writes `_source.md` → reindex. This plan stops before claim extraction; frontmatter is written with `claims` left empty, and the orchestrator emits a placeholder claim-extraction hook that's wired in the follow-up plan.

**Tech Stack:** Python 3.12, Click (CLI), Pydantic v2 (schema), ruamel.yaml (frontmatter roundtrip), DuckDB 1.1+ with DuckPGQ extension, sqlite3 (stdlib), markitdown, httpx, pytest, pytest-asyncio, pytest-cov.

**Scope boundary (what this plan excludes):**
- Claim extraction (Section 5.5 of spec) — stubbed out, plan 2.
- Graph reasoning (`sb_reason` / DuckPGQ queries) — plan 2.
- URL, repo, docx, epub converters — plan 3.
- Lint + `conflicts.md` — plan 3.
- `sb inject` + claude-code-agent hook — plan 4.
- Wizard (`sb init`) + habits learning — plan 5.
- Watcher, cron, `sb maintain` — plan 6.

---

## Repository Layout Created By This Plan

```
~/Developer/second-brain/             # the tool (new git repo)
├── README.md
├── pyproject.toml
├── .gitignore
├── .python-version
├── src/second_brain/
│   ├── __init__.py
│   ├── cli.py                        # sb init | ingest | reindex | status
│   ├── config.py                     # SECOND_BRAIN_HOME resolution
│   ├── frontmatter.py                # load/dump YAML frontmatter markdown
│   ├── slugs.py                      # Claude-free deterministic slug proposer
│   ├── paths.py                      # SourceFolder, path helpers
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── source.py                 # Pydantic SourceFrontmatter
│   │   ├── claim.py                  # Pydantic ClaimFrontmatter (stub, no extractor yet)
│   │   └── edges.py                  # RelationType, EdgeConfidence enums
│   ├── store/
│   │   ├── __init__.py
│   │   ├── duckdb_store.py           # DDL + open/close + atomic swap
│   │   └── fts_store.py              # SQLite FTS5 DDL + open/close + atomic swap
│   ├── reindex.py                    # deterministic rebuild
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── base.py                   # Converter protocol + IngestInput + SourceArtifacts
│   │   ├── note.py
│   │   ├── pdf.py
│   │   └── orchestrator.py
│   └── log.py                        # append structured entries to ~/second-brain/log.md
├── tests/
│   ├── conftest.py                   # tmp SECOND_BRAIN_HOME fixture
│   ├── fixtures/
│   │   ├── sources/                  # hand-written golden markdown
│   │   └── pdfs/
│   │       └── tiny.pdf              # 1-page test PDF
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_frontmatter.py
│   ├── test_slugs.py
│   ├── test_schema_source.py
│   ├── test_duckdb_store.py
│   ├── test_fts_store.py
│   ├── test_reindex.py
│   ├── test_ingest_note.py
│   ├── test_ingest_pdf.py
│   ├── test_orchestrator.py
│   └── test_e2e_ingest.py
└── docs/
    └── schema.md                     # schema doc regenerated from Pydantic
```

**Not created yet** (deferred to plan 2+): `src/second_brain/extract/`, `src/second_brain/graph/`, `src/second_brain/index/`, `src/second_brain/lint/`, `src/second_brain/wizard.py`, `src/second_brain/inject.py`, `src/second_brain/analytics/`.

---

## Task 1: Initialize repo + pyproject.toml

**Files:**
- Create: `~/Developer/second-brain/` (new git repo)
- Create: `~/Developer/second-brain/pyproject.toml`
- Create: `~/Developer/second-brain/.gitignore`
- Create: `~/Developer/second-brain/.python-version`
- Create: `~/Developer/second-brain/README.md`

- [ ] **Step 1: Create repo directory and initialize git**

```bash
mkdir -p ~/Developer/second-brain && cd ~/Developer/second-brain && git init -b main
```

- [ ] **Step 2: Write `.python-version`**

```
3.12
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
build/
dist/
*.egg-info/
.coverage
htmlcov/

# User data — should never be committed from tool repo
# (user data lives in ~/second-brain/, this repo is the tool)
```

- [ ] **Step 4: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "second-brain"
version = "0.1.0"
description = "Personal knowledge base maintained by Claude, graph-backed, markdown-as-truth."
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Jay" }]
dependencies = [
  "click>=8.1",
  "pydantic>=2.8",
  "ruamel.yaml>=0.18",
  "duckdb>=1.1.0",
  "markitdown>=0.0.1a2",
  "httpx>=0.27",
  "anthropic>=0.40",
  "python-slugify>=8.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "pytest-cov>=5",
  "ruff>=0.6",
  "mypy>=1.11",
]

[project.scripts]
sb = "second_brain.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/second_brain"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --strict-markers"
asyncio_mode = "auto"
markers = [
  "integration: slower end-to-end tests",
]

[tool.coverage.run]
branch = true
source = ["src/second_brain"]

[tool.coverage.report]
show_missing = true
fail_under = 75
```

- [ ] **Step 5: Write minimal `README.md`**

```markdown
# second-brain

Personal knowledge base maintained by Claude. Markdown-as-truth, graph-backed, continuously linted.

Status: **v0.1 foundation** (ingest + reindex). Claim extraction, retrieval tools, and the injection hook land in follow-up releases.

See `docs/superpowers/specs/2026-04-17-second-brain-design.md` in the companion `claude-code-agent` repo for the full spec.

## Install (dev)

    python -m venv .venv && source .venv/bin/activate
    pip install -e '.[dev]'
    sb --help

## Commands (v0.1)

- `sb reindex` — rebuild `.sb/` indexes from `~/second-brain/` markdown.
- `sb ingest <path>` — ingest a PDF or text/markdown note.
- `sb status` — size / freshness snapshot.

Data lives at `~/second-brain/` (override with `SECOND_BRAIN_HOME`).
```

- [ ] **Step 6: Create empty source and test directories with `__init__.py` files**

```bash
cd ~/Developer/second-brain
mkdir -p src/second_brain/schema src/second_brain/store src/second_brain/ingest tests/fixtures/sources tests/fixtures/pdfs docs
touch src/second_brain/__init__.py \
      src/second_brain/schema/__init__.py \
      src/second_brain/store/__init__.py \
      src/second_brain/ingest/__init__.py
```

- [ ] **Step 7: Install into venv and verify skeleton**

```bash
cd ~/Developer/second-brain
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Expected: install completes, no errors.

- [ ] **Step 8: First commit**

```bash
cd ~/Developer/second-brain
git add -A
git commit -m "chore: initialize second-brain package skeleton"
```

---

## Task 2: Config — `SECOND_BRAIN_HOME` resolution

**Files:**
- Create: `src/second_brain/config.py`
- Create: `tests/test_config.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `tests/conftest.py` (shared fixture)**

```python
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Isolated SECOND_BRAIN_HOME for the duration of the test."""
    home = tmp_path / "second-brain"
    home.mkdir()
    (home / ".sb").mkdir()
    (home / "sources").mkdir()
    (home / "claims").mkdir()
    (home / "inbox").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    yield home
```

- [ ] **Step 2: Write failing test `tests/test_config.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config


def test_resolves_home_from_env(sb_home: Path) -> None:
    cfg = Config.load()
    assert cfg.home == sb_home
    assert cfg.sb_dir == sb_home / ".sb"


def test_default_home_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECOND_BRAIN_HOME", raising=False)
    cfg = Config.load()
    assert cfg.home == Path.home() / "second-brain"


def test_enabled_false_when_sb_dir_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "bare"
    home.mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    assert cfg.enabled is False


def test_enabled_true_when_both_exist(sb_home: Path) -> None:
    cfg = Config.load()
    assert cfg.enabled is True
```

- [ ] **Step 3: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_config.py -v
```

Expected: `ImportError: cannot import name 'Config' from 'second_brain.config'`.

- [ ] **Step 4: Implement `src/second_brain/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    home: Path
    sb_dir: Path

    @property
    def enabled(self) -> bool:
        return self.home.exists() and self.sb_dir.exists()

    @property
    def sources_dir(self) -> Path:
        return self.home / "sources"

    @property
    def claims_dir(self) -> Path:
        return self.home / "claims"

    @property
    def inbox_dir(self) -> Path:
        return self.home / "inbox"

    @property
    def duckdb_path(self) -> Path:
        return self.sb_dir / "graph.duckdb"

    @property
    def fts_path(self) -> Path:
        return self.sb_dir / "kb.sqlite"

    @property
    def log_path(self) -> Path:
        return self.home / "log.md"

    @classmethod
    def load(cls) -> Config:
        env = os.environ.get("SECOND_BRAIN_HOME")
        home = Path(env).expanduser() if env else Path.home() / "second-brain"
        return cls(home=home, sb_dir=home / ".sb")
```

- [ ] **Step 5: Run test — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_config.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd ~/Developer/second-brain && git add -A && git commit -m "feat(config): resolve SECOND_BRAIN_HOME with enabled flag"
```

---

## Task 3: Frontmatter I/O

**Files:**
- Create: `src/second_brain/frontmatter.py`
- Create: `tests/test_frontmatter.py`

- [ ] **Step 1: Write failing test `tests/test_frontmatter.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.frontmatter import dump_document, load_document


def test_load_document_parses_yaml_and_body(tmp_path: Path) -> None:
    path = tmp_path / "source.md"
    path.write_text(
        "---\n"
        "id: src_test\n"
        "title: Hello\n"
        "tags: [a, b]\n"
        "---\n"
        "\n"
        "# Heading\n\n"
        "Body text.\n"
    )
    meta, body = load_document(path)
    assert meta["id"] == "src_test"
    assert meta["tags"] == ["a", "b"]
    assert body.startswith("\n# Heading")


def test_dump_document_writes_roundtrippable(tmp_path: Path) -> None:
    path = tmp_path / "out.md"
    dump_document(path, {"id": "src_x", "tags": ["ml"]}, "# Body\n")
    text = path.read_text()
    assert text.startswith("---\n")
    meta, body = load_document(path)
    assert meta == {"id": "src_x", "tags": ["ml"]}
    assert body == "# Body\n"


def test_load_rejects_missing_frontmatter(tmp_path: Path) -> None:
    import pytest

    path = tmp_path / "broken.md"
    path.write_text("# No frontmatter here\n")
    with pytest.raises(ValueError, match="missing frontmatter"):
        load_document(path)


def test_dump_preserves_key_order(tmp_path: Path) -> None:
    path = tmp_path / "ordered.md"
    meta = {"id": "src_z", "title": "t", "kind": "pdf", "content_hash": "sha256:abc"}
    dump_document(path, meta, "body\n")
    text = path.read_text().splitlines()
    # Keys appear in the same order we passed them
    assert text[1].startswith("id:")
    assert text[2].startswith("title:")
    assert text[3].startswith("kind:")
    assert text[4].startswith("content_hash:")
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_frontmatter.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/frontmatter.py`**

```python
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML(typ="rt")
_yaml.default_flow_style = False
_yaml.width = 10_000  # avoid wrapping long URLs / titles

_DELIM = "---\n"


def load_document(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(_DELIM):
        raise ValueError(f"{path}: missing frontmatter (must start with '---')")
    # Split after the *second* delimiter line.
    remainder = text[len(_DELIM):]
    end = remainder.find("\n" + _DELIM.rstrip() + "\n")
    if end < 0:
        # Allow file that is *only* frontmatter + trailing newline.
        end = remainder.find("\n" + _DELIM.rstrip())
        if end < 0:
            raise ValueError(f"{path}: unterminated frontmatter")
    yaml_block = remainder[:end]
    body_start = end + len("\n" + _DELIM.rstrip() + "\n")
    body = remainder[body_start:] if body_start <= len(remainder) else ""
    meta = _yaml.load(yaml_block) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    return dict(meta), body


def dump_document(path: Path, meta: dict[str, Any], body: str) -> None:
    buf = io.StringIO()
    _yaml.dump(dict(meta), buf)
    rendered_yaml = buf.getvalue()
    path.write_text(f"---\n{rendered_yaml}---\n{body}", encoding="utf-8")
```

- [ ] **Step 4: Run test — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_frontmatter.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(frontmatter): YAML frontmatter markdown load/dump"
```

---

## Task 4: Schema — `SourceFrontmatter`, `ClaimFrontmatter`, edge enums

**Files:**
- Create: `src/second_brain/schema/edges.py`
- Create: `src/second_brain/schema/source.py`
- Create: `src/second_brain/schema/claim.py`
- Create: `tests/test_schema_source.py`

- [ ] **Step 1: Write `src/second_brain/schema/edges.py`**

```python
from __future__ import annotations

from enum import StrEnum


class RelationType(StrEnum):
    CITES = "cites"
    RELATED = "related"
    SUPERSEDES = "supersedes"
    SUPPORTS = "supports"
    EVIDENCED_BY = "evidenced_by"
    CONTRADICTS = "contradicts"
    REFINES = "refines"


class EdgeConfidence(StrEnum):
    EXTRACTED = "extracted"
    INFERRED = "inferred"
    AMBIGUOUS = "ambiguous"


SOURCE_TO_SOURCE: frozenset[RelationType] = frozenset(
    {RelationType.CITES, RelationType.RELATED, RelationType.SUPERSEDES}
)
CLAIM_TO_SOURCE: frozenset[RelationType] = frozenset(
    {RelationType.SUPPORTS, RelationType.EVIDENCED_BY}
)
CLAIM_TO_CLAIM: frozenset[RelationType] = frozenset(
    {RelationType.CONTRADICTS, RelationType.REFINES}
)
```

- [ ] **Step 2: Write failing test `tests/test_schema_source.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind


def test_minimal_source_validates() -> None:
    sf = SourceFrontmatter(
        id="src_test",
        title="Test",
        kind=SourceKind.NOTE,
        content_hash="sha256:abc",
        ingested_at=datetime(2026, 4, 17, tzinfo=UTC),
        raw=[RawArtifact(path="raw/note.md", kind="original", sha256="sha256:abc")],
        abstract="A one-line abstract.",
    )
    assert sf.kind == SourceKind.NOTE
    assert sf.cites == []
    assert sf.related == []
    assert sf.supersedes == []
    assert sf.tags == []


def test_id_must_be_prefixed() -> None:
    with pytest.raises(ValueError, match="must start with 'src_'"):
        SourceFrontmatter(
            id="oops",
            title="x",
            kind=SourceKind.NOTE,
            content_hash="sha256:abc",
            ingested_at=datetime(2026, 4, 17, tzinfo=UTC),
            raw=[],
            abstract="",
        )


def test_roundtrip_via_dict() -> None:
    sf = SourceFrontmatter(
        id="src_a",
        title="A",
        kind=SourceKind.PDF,
        authors=["Smith, J."],
        year=2024,
        content_hash="sha256:0",
        ingested_at=datetime(2026, 4, 17, tzinfo=UTC),
        habit_taxonomy="papers/ml",
        raw=[RawArtifact(path="raw/a.pdf", kind="original", sha256="sha256:0")],
        cites=["src_b"],
        abstract="Short.",
    )
    dumped = sf.to_frontmatter_dict()
    restored = SourceFrontmatter.from_frontmatter_dict(dumped)
    assert restored == sf
```

- [ ] **Step 3: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_schema_source.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `src/second_brain/schema/source.py`**

```python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceKind(StrEnum):
    PDF = "pdf"
    URL = "url"
    REPO = "repo"
    NOTE = "note"
    DOCX = "docx"
    EPUB = "epub"
    FAILED = "failed"


class RawArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    kind: str = "original"
    sha256: str | None = None


class SourceFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    title: str
    kind: SourceKind
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    ingested_at: datetime
    content_hash: str
    habit_taxonomy: str | None = None
    raw: list[RawArtifact] = Field(default_factory=list)
    cites: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    supersedes: list[str] = Field(default_factory=list)
    abstract: str = ""

    @field_validator("id")
    @classmethod
    def _id_prefix(cls, v: str) -> str:
        if not v.startswith("src_"):
            raise ValueError("id must start with 'src_'")
        return v

    def to_frontmatter_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_frontmatter_dict(cls, data: dict[str, Any]) -> SourceFrontmatter:
        return cls.model_validate(data)
```

- [ ] **Step 5: Implement `src/second_brain/schema/claim.py` (stub, extractor lands in plan 2)**

```python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaimKind(StrEnum):
    EMPIRICAL = "empirical"
    THEORETICAL = "theoretical"
    DEFINITIONAL = "definitional"
    OPINION = "opinion"
    PREDICTION = "prediction"


class ClaimConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClaimStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"
    DISPUTED = "disputed"


class ClaimFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    statement: str
    kind: ClaimKind
    confidence: ClaimConfidence
    scope: str = ""
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    refines: list[str] = Field(default_factory=list)
    extracted_at: datetime
    status: ClaimStatus = ClaimStatus.ACTIVE
    resolution: str | None = None
    abstract: str = ""

    @field_validator("id")
    @classmethod
    def _id_prefix(cls, v: str) -> str:
        if not v.startswith("clm_"):
            raise ValueError("id must start with 'clm_'")
        return v

    def to_frontmatter_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_frontmatter_dict(cls, data: dict[str, Any]) -> ClaimFrontmatter:
        return cls.model_validate(data)
```

- [ ] **Step 6: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_schema_source.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(schema): Pydantic SourceFrontmatter and ClaimFrontmatter with edge enums"
```

---

## Task 5: Slug proposer (deterministic, no LLM)

In v0.1 the slug proposer is deterministic. Claude-driven slug refinement is layered in plan 5 (wizard).

**Files:**
- Create: `src/second_brain/slugs.py`
- Create: `tests/test_slugs.py`

- [ ] **Step 1: Write failing test `tests/test_slugs.py`**

```python
from __future__ import annotations

from second_brain.schema.source import SourceKind
from second_brain.slugs import propose_source_slug


def test_slug_from_title_with_year() -> None:
    slug = propose_source_slug(kind=SourceKind.PDF, title="Attention Is All You Need", year=2017)
    assert slug == "src_2017_attention-is-all-you-need"


def test_slug_from_title_without_year() -> None:
    slug = propose_source_slug(kind=SourceKind.NOTE, title="Planning Doc")
    assert slug == "src_planning-doc"


def test_slug_truncates_to_max_length() -> None:
    long_title = " ".join(["word"] * 40)
    slug = propose_source_slug(kind=SourceKind.PDF, title=long_title, max_length=40)
    assert len(slug) <= 40
    assert slug.startswith("src_")


def test_slug_avoids_collision_by_appending_digit(tmp_path) -> None:
    # Simulate prior collision: caller passes `taken` set.
    taken = {"src_planning-doc"}
    slug = propose_source_slug(kind=SourceKind.NOTE, title="Planning Doc", taken=taken)
    assert slug == "src_planning-doc-2"
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_slugs.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/slugs.py`**

```python
from __future__ import annotations

from collections.abc import Iterable

from slugify import slugify

from second_brain.schema.source import SourceKind

DEFAULT_MAX_LENGTH = 80


def propose_source_slug(
    *,
    kind: SourceKind,
    title: str,
    year: int | None = None,
    max_length: int = DEFAULT_MAX_LENGTH,
    taken: Iterable[str] = (),
) -> str:
    """Deterministic slug: `src_{year?_}{title-kebab}`, truncated + collision-safe."""
    parts: list[str] = ["src"]
    if year is not None:
        parts.append(str(year))
    parts.append(slugify(title, lowercase=True, max_length=max_length))
    base = "_".join(parts)
    # hard truncate to max_length after joining
    if len(base) > max_length:
        base = base[:max_length].rstrip("-_")

    taken_set = set(taken)
    if base not in taken_set:
        return base
    n = 2
    while f"{base}-{n}" in taken_set:
        n += 1
    return f"{base}-{n}"
```

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_slugs.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(slugs): deterministic source slug proposer with collision avoidance"
```

---

## Task 6: DuckDB store — schema + atomic open/swap

The DuckPGQ property graph DDL is included but extension loading is feature-flagged; plan 2 adds `sb_reason`. This plan only writes into the base tables.

**Files:**
- Create: `src/second_brain/store/duckdb_store.py`
- Create: `tests/test_duckdb_store.py`

- [ ] **Step 1: Write failing test `tests/test_duckdb_store.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.store.duckdb_store import DuckStore


def test_creates_tables_in_empty_file(tmp_path: Path) -> None:
    db = tmp_path / "graph.duckdb"
    with DuckStore.open(db) as store:
        store.ensure_schema()
        tables = store.list_tables()
    assert "sources" in tables
    assert "claims" in tables
    assert "edges" in tables


def test_insert_and_query_source(tmp_path: Path) -> None:
    db = tmp_path / "graph.duckdb"
    with DuckStore.open(db) as store:
        store.ensure_schema()
        store.insert_source(
            id="src_a", slug="a", title="A", kind="pdf",
            year=2024, habit_taxonomy="papers/ml",
            content_hash="sha256:0", abstract="abs",
        )
        rows = store.conn.execute("SELECT id, title FROM sources").fetchall()
    assert rows == [("src_a", "A")]


def test_atomic_swap_replaces_file(tmp_path: Path) -> None:
    target = tmp_path / "graph.duckdb"
    staging = tmp_path / "next" / "graph.duckdb"
    staging.parent.mkdir()
    with DuckStore.open(staging) as store:
        store.ensure_schema()
        store.insert_source(
            id="src_x", slug="x", title="X", kind="note",
            year=None, habit_taxonomy=None,
            content_hash="sha256:1", abstract="",
        )
    DuckStore.atomic_swap(staging=staging, target=target)
    assert target.exists()
    assert not staging.exists()
    with DuckStore.open(target) as store:
        rows = store.conn.execute("SELECT id FROM sources").fetchall()
    assert rows == [("src_x",)]
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_duckdb_store.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/store/duckdb_store.py`**

```python
from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb

DDL = """
CREATE TABLE IF NOT EXISTS sources (
  id              TEXT PRIMARY KEY,
  slug            TEXT,
  title           TEXT,
  kind            TEXT,
  year            INTEGER,
  habit_taxonomy  TEXT,
  content_hash    TEXT,
  abstract        TEXT,
  ingested_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claims (
  id               TEXT PRIMARY KEY,
  statement        TEXT,
  body             TEXT,
  abstract         TEXT,
  kind             TEXT,
  confidence_claim TEXT,
  status           TEXT,
  resolution       TEXT
);

CREATE TABLE IF NOT EXISTS edges (
  src_id           TEXT NOT NULL,
  dst_id           TEXT NOT NULL,
  relation         TEXT NOT NULL,
  confidence_edge  TEXT NOT NULL,
  rationale        TEXT,
  source_markdown  TEXT,
  PRIMARY KEY (src_id, dst_id, relation)
);

CREATE INDEX IF NOT EXISTS edges_src_rel ON edges(src_id, relation);
CREATE INDEX IF NOT EXISTS edges_dst_rel ON edges(dst_id, relation);
"""


class DuckStore:
    """Thin DuckDB wrapper. Property-graph view is added in plan 2."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, path: Path) -> None:
        self.conn = conn
        self.path = path

    @classmethod
    @contextmanager
    def open(cls, path: Path) -> Iterator[DuckStore]:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(path))
        try:
            yield cls(conn, path)
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        self.conn.execute(DDL)

    def list_tables(self) -> list[str]:
        rows = self.conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
        return sorted(r[0] for r in rows)

    def insert_source(
        self,
        *,
        id: str,
        slug: str,
        title: str,
        kind: str,
        year: int | None,
        habit_taxonomy: str | None,
        content_hash: str,
        abstract: str,
        ingested_at: str | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO sources (id, slug, title, kind, year, habit_taxonomy, "
            "content_hash, abstract, ingested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [id, slug, title, kind, year, habit_taxonomy, content_hash, abstract, ingested_at],
        )

    def insert_claim(
        self,
        *,
        id: str,
        statement: str,
        body: str,
        abstract: str,
        kind: str,
        confidence: str,
        status: str,
        resolution: str | None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO claims (id, statement, body, abstract, kind, "
            "confidence_claim, status, resolution) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [id, statement, body, abstract, kind, confidence, status, resolution],
        )

    def insert_edge(
        self,
        *,
        src_id: str,
        dst_id: str,
        relation: str,
        confidence: str,
        rationale: str | None,
        source_markdown: str,
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO edges (src_id, dst_id, relation, "
            "confidence_edge, rationale, source_markdown) VALUES (?, ?, ?, ?, ?, ?)",
            [src_id, dst_id, relation, confidence, rationale, source_markdown],
        )

    @staticmethod
    def atomic_swap(*, staging: Path, target: Path) -> None:
        """Rename staging DB file to target. POSIX atomic on same filesystem."""
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_suffix(target.suffix + ".prev")
            if backup.exists():
                backup.unlink()
            os.replace(target, backup)
        os.replace(staging, target)
        # Clean up empty staging parent if we made it.
        try:
            shutil.rmtree(staging.parent, ignore_errors=False)
        except OSError:
            pass
```

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_duckdb_store.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(store): DuckDB schema with atomic swap"
```

---

## Task 7: SQLite FTS5 store

**Files:**
- Create: `src/second_brain/store/fts_store.py`
- Create: `tests/test_fts_store.py`

- [ ] **Step 1: Write failing test `tests/test_fts_store.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.store.fts_store import FtsStore


def test_creates_virtual_tables(tmp_path: Path) -> None:
    db = tmp_path / "kb.sqlite"
    with FtsStore.open(db) as store:
        store.ensure_schema()
        names = store.list_tables()
    assert "source_fts" in names
    assert "claim_fts" in names


def test_insert_and_bm25_search(tmp_path: Path) -> None:
    db = tmp_path / "kb.sqlite"
    with FtsStore.open(db) as store:
        store.ensure_schema()
        store.insert_source(
            source_id="src_a",
            title="Attention Is All You Need",
            abstract="Transformer architecture using self-attention.",
            processed_body="The model relies entirely on self-attention mechanisms.",
            taxonomy="papers/ml",
        )
        store.insert_source(
            source_id="src_b",
            title="Cooking with Cast Iron",
            abstract="A guide to seasoning cookware.",
            processed_body="Cast iron pans benefit from polymerized oil.",
            taxonomy="notes/personal",
        )
        hits = store.search_sources("self attention", k=5)
    assert hits[0][0] == "src_a"
    assert hits[0][1] > 0


def test_atomic_swap(tmp_path: Path) -> None:
    target = tmp_path / "kb.sqlite"
    staging = tmp_path / "next" / "kb.sqlite"
    staging.parent.mkdir()
    with FtsStore.open(staging) as store:
        store.ensure_schema()
        store.insert_source(source_id="src_x", title="X", abstract="", processed_body="", taxonomy="")
    FtsStore.atomic_swap(staging=staging, target=target)
    assert target.exists()
    with FtsStore.open(target) as store:
        hits = store.search_sources("X", k=5)
    assert hits and hits[0][0] == "src_x"
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_fts_store.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/store/fts_store.py`**

```python
from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS source_fts USING fts5(
  source_id UNINDEXED,
  title,
  abstract,
  processed_body,
  taxonomy,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS claim_fts USING fts5(
  claim_id UNINDEXED,
  statement,
  abstract,
  body,
  taxonomy,
  tokenize = 'unicode61 remove_diacritics 2'
);
"""

# Column weight orderings match the virtual table definitions above.
SOURCE_BM25_WEIGHTS = "3.0, 2.0, 1.0, 0.5"
CLAIM_BM25_WEIGHTS = "3.0, 2.0, 1.0, 0.5"


class FtsStore:
    def __init__(self, conn: sqlite3.Connection, path: Path) -> None:
        self.conn = conn
        self.path = path

    @classmethod
    @contextmanager
    def open(cls, path: Path) -> Iterator[FtsStore]:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        try:
            yield cls(conn, path)
            conn.commit()
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        self.conn.executescript(DDL)

    def list_tables(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','virtual') OR name LIKE '%_fts'"
        ).fetchall()
        return sorted(r[0] for r in rows)

    def insert_source(
        self,
        *,
        source_id: str,
        title: str,
        abstract: str,
        processed_body: str,
        taxonomy: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO source_fts (source_id, title, abstract, processed_body, taxonomy) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_id, title, abstract, processed_body, taxonomy),
        )

    def insert_claim(
        self,
        *,
        claim_id: str,
        statement: str,
        abstract: str,
        body: str,
        taxonomy: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO claim_fts (claim_id, statement, abstract, body, taxonomy) "
            "VALUES (?, ?, ?, ?, ?)",
            (claim_id, statement, abstract, body, taxonomy),
        )

    def search_sources(self, query: str, k: int) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            f"SELECT source_id, -bm25(source_fts, {SOURCE_BM25_WEIGHTS}) AS score "
            "FROM source_fts WHERE source_fts MATCH ? ORDER BY score DESC LIMIT ?",
            (query, k),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def search_claims(self, query: str, k: int) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            f"SELECT claim_id, -bm25(claim_fts, {CLAIM_BM25_WEIGHTS}) AS score "
            "FROM claim_fts WHERE claim_fts MATCH ? ORDER BY score DESC LIMIT ?",
            (query, k),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    @staticmethod
    def atomic_swap(*, staging: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_suffix(target.suffix + ".prev")
            if backup.exists():
                backup.unlink()
            os.replace(target, backup)
        os.replace(staging, target)
        try:
            staging.parent.rmdir()
        except OSError:
            pass
```

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_fts_store.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(store): SQLite FTS5 store with BM25 search"
```

---

## Task 8: Log writer

**Files:**
- Create: `src/second_brain/log.py`
- Create: `tests/test_log.py`

- [ ] **Step 1: Write failing test `tests/test_log.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.log import EventKind, append_event


def test_appends_structured_entry(sb_home: Path) -> None:
    append_event(
        kind=EventKind.AUTO,
        op="ingest.taxonomy",
        subject="src_test",
        value="papers/ml",
        reason={"matches": "neighbor"},
    )
    text = (sb_home / "log.md").read_text()
    assert "[AUTO]" in text
    assert "ingest.taxonomy" in text
    assert "src_test" in text
    assert "papers/ml" in text


def test_multiple_entries_preserve_order(sb_home: Path) -> None:
    append_event(kind=EventKind.AUTO, op="x", subject="a", value="1")
    append_event(kind=EventKind.USER_OVERRIDE, op="x", subject="a", value="2")
    lines = (sb_home / "log.md").read_text().splitlines()
    assert any("[AUTO]" in ln and "1" in ln for ln in lines)
    assert any("[USER_OVERRIDE]" in ln and "2" in ln for ln in lines)
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_log.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/log.py`**

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from second_brain.config import Config


class EventKind(StrEnum):
    AUTO = "AUTO"
    USER_OVERRIDE = "USER_OVERRIDE"
    SUGGEST = "SUGGEST"
    INGEST = "INGEST"
    REINDEX = "REINDEX"
    ERROR = "ERROR"


def append_event(
    *,
    kind: EventKind,
    op: str,
    subject: str,
    value: str,
    reason: dict[str, Any] | None = None,
    home: Path | None = None,
) -> None:
    cfg = Config.load() if home is None else None
    log_path = (home / "log.md") if home else cfg.log_path  # type: ignore[union-attr]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"- {ts} [{kind}] {op} {subject} → {value}"
    if reason:
        line += f"\n  reason: {json.dumps(reason, separators=(',', ':'))}"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
```

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_log.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(log): structured append-only event log"
```

---

## Task 9: Reindex — markdown → DuckDB + FTS5

**Files:**
- Create: `src/second_brain/reindex.py`
- Create: `tests/test_reindex.py`
- Create: `tests/fixtures/sources/src_hello/_source.md`
- Create: `tests/fixtures/sources/src_hello/raw/hello.md`

- [ ] **Step 1: Write fixture `tests/fixtures/sources/src_hello/_source.md`**

```markdown
---
id: src_hello
title: Hello
kind: note
ingested_at: '2026-04-17T12:00:00+00:00'
content_hash: sha256:test
habit_taxonomy: notes/personal
raw:
- path: raw/hello.md
  kind: original
  sha256: sha256:test
abstract: A short hello.
---

# Hello

Body of the hello note.
```

- [ ] **Step 2: Write fixture `tests/fixtures/sources/src_hello/raw/hello.md`**

```markdown
Body of the hello note.
```

- [ ] **Step 3: Write failing test `tests/test_reindex.py`**

```python
from __future__ import annotations

import shutil
from pathlib import Path

from second_brain.config import Config
from second_brain.reindex import reindex
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore

FIXTURES = Path(__file__).parent / "fixtures" / "sources"


def _populate(sb_home: Path) -> None:
    shutil.copytree(FIXTURES / "src_hello", sb_home / "sources" / "src_hello")


def test_reindex_empty_home_produces_empty_dbs(sb_home: Path) -> None:
    cfg = Config.load()
    reindex(cfg)
    assert cfg.duckdb_path.exists()
    assert cfg.fts_path.exists()
    with DuckStore.open(cfg.duckdb_path) as store:
        assert store.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0


def test_reindex_populates_source_row(sb_home: Path) -> None:
    _populate(sb_home)
    cfg = Config.load()
    reindex(cfg)
    with DuckStore.open(cfg.duckdb_path) as store:
        rows = store.conn.execute("SELECT id, title, habit_taxonomy FROM sources").fetchall()
    assert rows == [("src_hello", "Hello", "notes/personal")]


def test_reindex_populates_fts(sb_home: Path) -> None:
    _populate(sb_home)
    cfg = Config.load()
    reindex(cfg)
    with FtsStore.open(cfg.fts_path) as store:
        hits = store.search_sources("hello", k=5)
    assert hits and hits[0][0] == "src_hello"


def test_reindex_is_deterministic(sb_home: Path) -> None:
    _populate(sb_home)
    cfg = Config.load()
    reindex(cfg)
    first = cfg.duckdb_path.read_bytes()
    cfg.duckdb_path.unlink()
    cfg.fts_path.unlink()
    reindex(cfg)
    second = cfg.duckdb_path.read_bytes()
    # DuckDB file content isn't byte-identical across runs, so query instead.
    with DuckStore.open(cfg.duckdb_path) as store:
        ids = [r[0] for r in store.conn.execute("SELECT id FROM sources ORDER BY id").fetchall()]
    assert ids == ["src_hello"]
```

- [ ] **Step 4: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_reindex.py -v
```

Expected: ImportError.

- [ ] **Step 5: Implement `src/second_brain/reindex.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.schema.claim import ClaimFrontmatter
from second_brain.schema.edges import (
    CLAIM_TO_CLAIM,
    CLAIM_TO_SOURCE,
    SOURCE_TO_SOURCE,
    EdgeConfidence,
    RelationType,
)
from second_brain.schema.source import SourceFrontmatter
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore


def reindex(cfg: Config) -> None:
    """Deterministic: markdown → DuckDB + FTS5. Atomic swap to live paths."""
    staging_dir = cfg.sb_dir / "next"
    staging_dir.mkdir(parents=True, exist_ok=True)
    stg_duck = staging_dir / "graph.duckdb"
    stg_fts = staging_dir / "kb.sqlite"
    if stg_duck.exists():
        stg_duck.unlink()
    if stg_fts.exists():
        stg_fts.unlink()

    sources = list(_iter_sources(cfg.sources_dir))
    claims = list(_iter_claims(cfg.claims_dir))

    with DuckStore.open(stg_duck) as dstore, FtsStore.open(stg_fts) as fstore:
        dstore.ensure_schema()
        fstore.ensure_schema()

        for path, sf, body in sources:
            dstore.insert_source(
                id=sf.id,
                slug=path.parent.name,
                title=sf.title,
                kind=sf.kind.value,
                year=sf.year,
                habit_taxonomy=sf.habit_taxonomy,
                content_hash=sf.content_hash,
                abstract=sf.abstract,
                ingested_at=sf.ingested_at.isoformat(),
            )
            fstore.insert_source(
                source_id=sf.id,
                title=sf.title,
                abstract=sf.abstract,
                processed_body=body,
                taxonomy=sf.habit_taxonomy or "",
            )
            _write_source_edges(dstore, sf, path)

        for path, cf, body in claims:
            dstore.insert_claim(
                id=cf.id,
                statement=cf.statement,
                body=body,
                abstract=cf.abstract,
                kind=cf.kind.value,
                confidence=cf.confidence.value,
                status=cf.status.value,
                resolution=cf.resolution,
            )
            fstore.insert_claim(
                claim_id=cf.id,
                statement=cf.statement,
                abstract=cf.abstract,
                body=body,
                taxonomy="",
            )
            _write_claim_edges(dstore, cf, path)

    DuckStore.atomic_swap(staging=stg_duck, target=cfg.duckdb_path)
    FtsStore.atomic_swap(staging=stg_fts, target=cfg.fts_path)


def _iter_sources(sources_dir: Path):
    if not sources_dir.exists():
        return
    for path in sorted(sources_dir.glob("*/_source.md")):
        meta, body = load_document(path)
        yield path, SourceFrontmatter.from_frontmatter_dict(meta), body


def _iter_claims(claims_dir: Path):
    if not claims_dir.exists():
        return
    for path in sorted(claims_dir.glob("*.md")):
        if path.parent.name == "resolutions":
            continue
        meta, body = load_document(path)
        yield path, ClaimFrontmatter.from_frontmatter_dict(meta), body


def _write_source_edges(store: DuckStore, sf: SourceFrontmatter, path: Path) -> None:
    rel_map = [
        (RelationType.CITES, sf.cites),
        (RelationType.RELATED, sf.related),
        (RelationType.SUPERSEDES, sf.supersedes),
    ]
    for rel, targets in rel_map:
        for target in targets:
            assert rel in SOURCE_TO_SOURCE
            store.insert_edge(
                src_id=sf.id,
                dst_id=target,
                relation=rel.value,
                confidence=EdgeConfidence.EXTRACTED.value,
                rationale=None,
                source_markdown=str(path),
            )


def _write_claim_edges(store: DuckStore, cf: ClaimFrontmatter, path: Path) -> None:
    for target in cf.supports:
        assert RelationType.SUPPORTS in CLAIM_TO_SOURCE
        store.insert_edge(
            src_id=cf.id, dst_id=target, relation=RelationType.SUPPORTS.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )
        # materialize reverse evidenced_by
        store.insert_edge(
            src_id=target, dst_id=cf.id, relation=RelationType.EVIDENCED_BY.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )
    for target in cf.contradicts:
        assert RelationType.CONTRADICTS in CLAIM_TO_CLAIM
        store.insert_edge(
            src_id=cf.id, dst_id=target, relation=RelationType.CONTRADICTS.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )
    for target in cf.refines:
        store.insert_edge(
            src_id=cf.id, dst_id=target, relation=RelationType.REFINES.value,
            confidence=EdgeConfidence.EXTRACTED.value, rationale=None,
            source_markdown=str(path),
        )
```

- [ ] **Step 6: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_reindex.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(reindex): deterministic markdown → DuckDB + FTS5 rebuild with atomic swap"
```

---

## Task 10: Converter protocol + `IngestInput`

**Files:**
- Create: `src/second_brain/paths.py`
- Create: `src/second_brain/ingest/base.py`
- Create: `tests/test_ingest_base.py`

- [ ] **Step 1: Write failing test `tests/test_ingest_base.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder


def test_ingest_input_from_local_path(tmp_path: Path) -> None:
    f = tmp_path / "note.md"
    f.write_text("hello")
    inp = IngestInput.from_path(f)
    assert inp.origin == str(f)
    with inp.open_stream() as stream:
        assert stream.read() == b"hello"
    assert inp.suffix == ".md"


def test_source_folder_create_and_paths(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "sources" / "src_x")
    assert folder.raw_dir.exists()
    assert folder.source_md == tmp_path / "sources" / "src_x" / "_source.md"
    assert folder.raw_manifest == tmp_path / "sources" / "src_x" / "raw_manifest.json"


def test_source_folder_refuses_existing(tmp_path: Path) -> None:
    (tmp_path / "sources" / "src_x").mkdir(parents=True)
    with pytest.raises(FileExistsError):
        SourceFolder.create(tmp_path / "sources" / "src_x")
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_ingest_base.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/paths.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceFolderPaths:
    root: Path
    source_md: Path
    raw_dir: Path
    raw_manifest: Path
```

- [ ] **Step 4: Implement `src/second_brain/ingest/base.py`**

```python
from __future__ import annotations

import hashlib
import io
import json
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, ClassVar, Protocol, runtime_checkable


@dataclass(frozen=True)
class IngestInput:
    origin: str
    suffix: str
    content: bytes

    @classmethod
    def from_path(cls, path: Path) -> IngestInput:
        return cls(
            origin=str(path),
            suffix=path.suffix.lower(),
            content=path.read_bytes(),
        )

    @classmethod
    def from_bytes(cls, *, origin: str, suffix: str, content: bytes) -> IngestInput:
        return cls(origin=origin, suffix=suffix, content=content)

    @contextmanager
    def open_stream(self) -> Iterator[IO[bytes]]:
        buf = io.BytesIO(self.content)
        try:
            yield buf
        finally:
            buf.close()

    @property
    def sha256(self) -> str:
        return "sha256:" + hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class RawWrite:
    path: str  # relative to folder root, e.g. "raw/paper.pdf"
    kind: str  # "original" | "screenshot" | "extracted-text" | ...
    sha256: str


@dataclass(frozen=True)
class SourceArtifacts:
    processed_body: str
    raw: list[RawWrite] = field(default_factory=list)
    title_hint: str | None = None
    year_hint: int | None = None
    authors_hint: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceFolder:
    root: Path

    KIND: ClassVar[str] = "folder"

    @classmethod
    def create(cls, root: Path) -> SourceFolder:
        if root.exists():
            raise FileExistsError(f"{root} already exists")
        root.mkdir(parents=True)
        (root / "raw").mkdir()
        return cls(root=root)

    @property
    def source_md(self) -> Path:
        return self.root / "_source.md"

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def raw_manifest(self) -> Path:
        return self.root / "raw_manifest.json"

    def write_raw(self, *, rel_path: str, content: bytes, kind: str) -> RawWrite:
        if not rel_path.startswith("raw/"):
            raise ValueError("rel_path must live under raw/")
        target = self.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        return RawWrite(path=rel_path, kind=kind, sha256=digest)

    def write_manifest(self, raws: list[RawWrite]) -> None:
        data = [{"path": r.path, "kind": r.kind, "sha256": r.sha256} for r in raws]
        self.raw_manifest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def destroy(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


@runtime_checkable
class Converter(Protocol):
    kind: ClassVar[str]

    def matches(self, source: IngestInput) -> bool: ...

    def convert(
        self, source: IngestInput, target: SourceFolder
    ) -> SourceArtifacts: ...
```

- [ ] **Step 5: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_ingest_base.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(ingest): Converter protocol, IngestInput, SourceFolder"
```

---

## Task 11: Note converter

**Files:**
- Create: `src/second_brain/ingest/note.py`
- Create: `tests/test_ingest_note.py`

- [ ] **Step 1: Write failing test `tests/test_ingest_note.py`**

```python
from __future__ import annotations

from pathlib import Path

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.note import NoteConverter


def test_matches_md_and_txt() -> None:
    c = NoteConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.md", suffix=".md", content=b""))
    assert c.matches(IngestInput.from_bytes(origin="x.txt", suffix=".txt", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))


def test_convert_md_preserves_body_and_extracts_title(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    md = b"# Planning\n\nNotes about Q2 planning."
    inp = IngestInput.from_bytes(origin="/path/plan.md", suffix=".md", content=md)
    artifacts = NoteConverter().convert(inp, folder)
    assert artifacts.title_hint == "Planning"
    assert "Notes about Q2 planning" in artifacts.processed_body
    assert len(artifacts.raw) == 1
    assert artifacts.raw[0].path == "raw/original.md"
    assert (folder.raw_dir / "original.md").exists()


def test_convert_txt_without_heading_uses_filename(tmp_path: Path) -> None:
    folder = SourceFolder.create(tmp_path / "src_y")
    inp = IngestInput.from_bytes(origin="/path/quick-thought.txt", suffix=".txt", content=b"Just a thought.")
    artifacts = NoteConverter().convert(inp, folder)
    assert artifacts.title_hint == "quick-thought"
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_ingest_note.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/ingest/note.py`**

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder

_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class NoteConverter(Converter):
    kind: ClassVar[str] = "note"
    _SUFFIXES = frozenset({".md", ".txt"})

    def matches(self, source: IngestInput) -> bool:
        return source.suffix in self._SUFFIXES

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        body = source.content.decode("utf-8", errors="replace")
        raw_write = target.write_raw(
            rel_path=f"raw/original{source.suffix}",
            content=source.content,
            kind="original",
        )
        match = _H1.search(body)
        if match:
            title = match.group(1).strip()
        else:
            title = Path(source.origin).stem
        return SourceArtifacts(
            processed_body=body if body.endswith("\n") else body + "\n",
            raw=[raw_write],
            title_hint=title,
        )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_ingest_note.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(ingest): note converter for .md/.txt passthrough"
```

---

## Task 12: PDF converter (markitdown wrapper)

**Files:**
- Create: `src/second_brain/ingest/pdf.py`
- Create: `tests/fixtures/pdfs/tiny.pdf` (generate at test time to avoid binary commit)
- Create: `tests/test_ingest_pdf.py`

- [ ] **Step 1: Write test `tests/test_ingest_pdf.py` (creates its own PDF)**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.ingest.base import IngestInput, SourceFolder
from second_brain.ingest.pdf import PdfConverter


@pytest.fixture
def tiny_pdf_bytes() -> bytes:
    """Minimal one-page PDF with the text 'Hello PDF'."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 20 100 Td (Hello PDF) Tj ET\nendstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n"
        b"0000000099 00000 n \n0000000193 00000 n \n0000000274 00000 n \n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n330\n%%EOF\n"
    )


def test_matches_pdf_suffix() -> None:
    c = PdfConverter()
    assert c.matches(IngestInput.from_bytes(origin="x.pdf", suffix=".pdf", content=b""))
    assert not c.matches(IngestInput.from_bytes(origin="x.md", suffix=".md", content=b""))


def test_convert_writes_raw_and_returns_body(tmp_path: Path, tiny_pdf_bytes: bytes) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="/p/tiny.pdf", suffix=".pdf", content=tiny_pdf_bytes)
    artifacts = PdfConverter().convert(inp, folder)
    assert (folder.raw_dir / "original.pdf").exists()
    assert len(artifacts.processed_body) > 0
    assert artifacts.raw[0].path == "raw/original.pdf"


@pytest.mark.integration
def test_convert_extracts_text(tmp_path: Path, tiny_pdf_bytes: bytes) -> None:
    folder = SourceFolder.create(tmp_path / "src_x")
    inp = IngestInput.from_bytes(origin="/p/tiny.pdf", suffix=".pdf", content=tiny_pdf_bytes)
    artifacts = PdfConverter().convert(inp, folder)
    assert "Hello PDF" in artifacts.processed_body
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_ingest_pdf.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/ingest/pdf.py`**

```python
from __future__ import annotations

import io
from pathlib import Path
from typing import ClassVar

from second_brain.ingest.base import Converter, IngestInput, SourceArtifacts, SourceFolder


class PdfConverter(Converter):
    kind: ClassVar[str] = "pdf"

    def matches(self, source: IngestInput) -> bool:
        return source.suffix == ".pdf"

    def convert(self, source: IngestInput, target: SourceFolder) -> SourceArtifacts:
        raw_write = target.write_raw(
            rel_path="raw/original.pdf",
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
        # markitdown is the preferred path; it handles PDFs through pdfminer under the hood.
        try:
            from markitdown import MarkItDown  # type: ignore[import-not-found]

            md = MarkItDown()
            with source.open_stream() as stream:
                result = md.convert_stream(stream, file_extension=".pdf")
            text = (result.text_content or "").strip()
            return text + "\n" if text else "\n"
        except Exception as exc:  # noqa: BLE001
            # Fallback: store a placeholder so ingest still succeeds; lint picks it up.
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

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_ingest_pdf.py -v -m "not integration"
```

Expected: 2 passed. The integration test is marked so the main run doesn't require a working markitdown install; run it separately:

```bash
cd ~/Developer/second-brain && pytest tests/test_ingest_pdf.py -v -m integration
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(ingest): PDF converter via markitdown with text fallback"
```

---

## Task 13: Orchestrator — pick converter, allocate folder, write frontmatter

**Files:**
- Create: `src/second_brain/ingest/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing test `tests/test_orchestrator.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest


def test_ingest_note_creates_folder(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/hello.md", suffix=".md", content=b"# Hello\n\nBody.")
    folder = ingest(inp, cfg=cfg)
    assert folder.source_md.exists()
    meta, body = load_document(folder.source_md)
    assert meta["id"].startswith("src_")
    assert meta["title"] == "Hello"
    assert meta["kind"] == "note"
    assert "Body." in body


def test_ingest_rejects_unknown_suffix(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/x.weird", suffix=".weird", content=b"")
    with pytest.raises(IngestError, match="no converter matched"):
        ingest(inp, cfg=cfg)


def test_ingest_dedupes_on_content_hash(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/a.md", suffix=".md", content=b"# Hello\n\nBody.")
    first = ingest(inp, cfg=cfg)
    with pytest.raises(IngestError, match="duplicate"):
        ingest(inp, cfg=cfg)
    assert first.source_md.exists()


def test_ingest_writes_raw_manifest(sb_home: Path) -> None:
    cfg = Config.load()
    inp = IngestInput.from_bytes(origin="/p/note.md", suffix=".md", content=b"# X\n\ncontent")
    folder = ingest(inp, cfg=cfg)
    import json
    manifest = json.loads(folder.raw_manifest.read_text())
    assert manifest[0]["kind"] == "original"
    assert manifest[0]["path"].startswith("raw/")
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_orchestrator.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/ingest/orchestrator.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.ingest.base import Converter, IngestInput, SourceFolder
from second_brain.ingest.note import NoteConverter
from second_brain.ingest.pdf import PdfConverter
from second_brain.log import EventKind, append_event
from second_brain.schema.source import RawArtifact, SourceFrontmatter, SourceKind
from second_brain.slugs import propose_source_slug


class IngestError(RuntimeError):
    pass


DEFAULT_CONVERTERS: list[Converter] = [NoteConverter(), PdfConverter()]


def ingest(
    source: IngestInput,
    *,
    cfg: Config,
    converters: list[Converter] | None = None,
) -> SourceFolder:
    cfg.sources_dir.mkdir(parents=True, exist_ok=True)
    registered = converters or DEFAULT_CONVERTERS

    _check_duplicate(cfg, source.sha256)

    converter = _pick_converter(source, registered)
    kind = SourceKind(converter.kind)

    # Speculative slug (may need bump after real title lands).
    taken = _taken_slugs(cfg)
    title_guess = _fallback_title(source)
    slug = propose_source_slug(kind=kind, title=title_guess, taken=taken)
    folder = SourceFolder.create(cfg.sources_dir / slug)

    try:
        artifacts = converter.convert(source, folder)
    except Exception:
        folder.destroy()
        raise

    title = (artifacts.title_hint or title_guess).strip() or title_guess
    # If the real title would produce a different slug, rename folder (once).
    desired = propose_source_slug(kind=kind, title=title, year=artifacts.year_hint, taken=taken)
    if desired != slug:
        new_root = cfg.sources_dir / desired
        folder.root.rename(new_root)
        folder = SourceFolder(root=new_root)
        slug = desired

    folder.write_manifest(artifacts.raw)

    frontmatter = SourceFrontmatter(
        id=slug,
        title=title,
        kind=kind,
        authors=artifacts.authors_hint,
        year=artifacts.year_hint,
        source_url=None,
        tags=[],
        ingested_at=datetime.now(UTC),
        content_hash=source.sha256,
        habit_taxonomy=None,
        raw=[
            RawArtifact(path=r.path, kind=r.kind, sha256=r.sha256) for r in artifacts.raw
        ],
        cites=[],
        related=[],
        supersedes=[],
        abstract="",
    )
    dump_document(folder.source_md, frontmatter.to_frontmatter_dict(), artifacts.processed_body)
    append_event(
        kind=EventKind.INGEST,
        op=f"ingest.{kind.value}",
        subject=slug,
        value=source.origin,
        home=cfg.home,
    )
    return folder


def _pick_converter(source: IngestInput, registered: list[Converter]) -> Converter:
    for c in registered:
        if c.matches(source):
            return c
    raise IngestError(f"no converter matched suffix={source.suffix!r}")


def _taken_slugs(cfg: Config) -> set[str]:
    if not cfg.sources_dir.exists():
        return set()
    return {p.name for p in cfg.sources_dir.iterdir() if p.is_dir()}


def _check_duplicate(cfg: Config, content_hash: str) -> None:
    for folder in cfg.sources_dir.glob("*/_source.md"):
        from second_brain.frontmatter import load_document
        meta, _ = load_document(folder)
        if meta.get("content_hash") == content_hash:
            raise IngestError(f"duplicate content_hash → existing: {folder.parent.name}")


def _fallback_title(source: IngestInput) -> str:
    from pathlib import Path
    return Path(source.origin).stem or "untitled"
```

- [ ] **Step 4: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_orchestrator.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(ingest): orchestrator wires converters, slug, frontmatter, manifest, log"
```

---

## Task 14: CLI — `sb reindex`, `sb ingest`, `sb status`

**Files:**
- Create: `src/second_brain/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing test `tests/test_cli.py`**

```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def test_help(sb_home: Path) -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.output
    assert "reindex" in result.output
    assert "status" in result.output


def test_status_empty_home(sb_home: Path) -> None:
    result = CliRunner().invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "sources: 0" in result.output


def test_ingest_and_reindex_roundtrip(sb_home: Path, tmp_path: Path) -> None:
    note = tmp_path / "hello.md"
    note.write_text("# Hello\n\nBody.")
    result = CliRunner().invoke(cli, ["ingest", str(note)])
    assert result.exit_code == 0, result.output
    assert "src_" in result.output

    result = CliRunner().invoke(cli, ["reindex"])
    assert result.exit_code == 0

    result = CliRunner().invoke(cli, ["status"])
    assert "sources: 1" in result.output
```

- [ ] **Step 2: Run test — verify failure**

```bash
cd ~/Developer/second-brain && pytest tests/test_cli.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/second_brain/cli.py`**

```python
from __future__ import annotations

from pathlib import Path

import click

from second_brain.config import Config
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest
from second_brain.reindex import reindex as run_reindex


@click.group()
@click.version_option(package_name="second-brain")
def cli() -> None:
    """Second Brain — personal knowledge base (v0.1 foundation)."""


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def ingest_cmd(path: Path) -> None:
    """Ingest a file into ~/second-brain/sources/."""
    cfg = Config.load()
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    inp = IngestInput.from_path(path)
    try:
        folder = ingest(inp, cfg=cfg)
    except IngestError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"ingested {folder.root.name}")


# Click will call this `ingest`, overriding our function name via command name.
cli.commands["ingest"] = ingest_cmd
del cli.commands["ingest-cmd"]


@cli.command()
def reindex() -> None:
    """Rebuild .sb/ indexes from markdown."""
    cfg = Config.load()
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    run_reindex(cfg)
    click.echo("reindex complete")


@cli.command()
def status() -> None:
    """Show KB size + index freshness snapshot."""
    cfg = Config.load()
    sources = 0
    if cfg.sources_dir.exists():
        sources = sum(1 for _ in cfg.sources_dir.glob("*/_source.md"))
    claims = 0
    if cfg.claims_dir.exists():
        claims = sum(1 for p in cfg.claims_dir.glob("*.md") if p.parent.name != "resolutions")
    duck_exists = cfg.duckdb_path.exists()
    fts_exists = cfg.fts_path.exists()
    click.echo(f"home: {cfg.home}")
    click.echo(f"sources: {sources}")
    click.echo(f"claims: {claims}")
    click.echo(f"indexes: duckdb={'y' if duck_exists else 'n'} fts={'y' if fts_exists else 'n'}")
```

- [ ] **Step 4: Fix CLI command wiring**

The naive `del/rename` approach above is fragile. Replace the `ingest_cmd` registration block with Click's built-in name override:

```python
@cli.command(name="ingest")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def _ingest(path: Path) -> None:
    """Ingest a file into ~/second-brain/sources/."""
    cfg = Config.load()
    cfg.sb_dir.mkdir(parents=True, exist_ok=True)
    inp = IngestInput.from_path(path)
    try:
        folder = ingest(inp, cfg=cfg)
    except IngestError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"ingested {folder.root.name}")
```

And remove both the prior `ingest_cmd` function and the `cli.commands["ingest"] = ingest_cmd` / `del` lines. Final `cli.py` keeps: `cli`, `_ingest` (name="ingest"), `reindex`, `status`.

- [ ] **Step 5: Run tests — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_cli.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Smoke-test the real CLI**

```bash
cd ~/Developer/second-brain
source .venv/bin/activate
export SECOND_BRAIN_HOME=/tmp/sb-smoke
rm -rf $SECOND_BRAIN_HOME && mkdir -p $SECOND_BRAIN_HOME/.sb
echo "# Smoke\nA smoke test note." > /tmp/smoke.md
sb ingest /tmp/smoke.md
sb reindex
sb status
```

Expected: `ingested src_smoke`, `reindex complete`, `sources: 1`.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat(cli): sb ingest, sb reindex, sb status"
```

---

## Task 15: End-to-end integration test

**Files:**
- Create: `tests/test_e2e_ingest.py`

- [ ] **Step 1: Write failing test `tests/test_e2e_ingest.py`**

```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.store.duckdb_store import DuckStore
from second_brain.store.fts_store import FtsStore


def test_ingest_two_notes_and_search_recovers_them(sb_home: Path, tmp_path: Path) -> None:
    a = tmp_path / "attention.md"
    a.write_text("# Attention\n\nSelf-attention is sufficient for seq transduction.\n")
    b = tmp_path / "recurrence.md"
    b.write_text("# Recurrence\n\nLong-range dependencies need recurrence.\n")

    runner = CliRunner()
    assert runner.invoke(cli, ["ingest", str(a)]).exit_code == 0
    assert runner.invoke(cli, ["ingest", str(b)]).exit_code == 0
    assert runner.invoke(cli, ["reindex"]).exit_code == 0

    cfg = Config.load()
    with FtsStore.open(cfg.fts_path) as store:
        hits = store.search_sources("attention", k=5)
    assert any(h[0].startswith("src_attention") for h in hits)

    with DuckStore.open(cfg.duckdb_path) as store:
        rows = store.conn.execute("SELECT id FROM sources ORDER BY id").fetchall()
    assert len(rows) == 2
```

- [ ] **Step 2: Run — verify pass**

```bash
cd ~/Developer/second-brain && pytest tests/test_e2e_ingest.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Run full test suite with coverage**

```bash
cd ~/Developer/second-brain && pytest --cov
```

Expected: all passing, coverage ≥ 75%.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test: end-to-end ingest + reindex + search round-trip"
```

---

## Task 16: Bootstrap the user's data home and write a welcome note

**Files:**
- Modify: user's filesystem (`~/second-brain/`)

This task is manual / interactive; the subagent should run it as a final smoke step.

- [ ] **Step 1: Create the data home**

```bash
mkdir -p ~/second-brain/.sb ~/second-brain/sources ~/second-brain/claims ~/second-brain/inbox
```

- [ ] **Step 2: Write a welcome note in the inbox**

```bash
cat > ~/second-brain/inbox/welcome.md <<'MD'
# Welcome to Second Brain

Drop PDFs, notes, or URLs into `~/second-brain/inbox/` and run
`sb ingest <path>` (or `sb process-inbox` when that lands in plan 2).

Tonight's foundation release supports: note and PDF ingest, frontmatter
validation, deterministic reindex to DuckDB + SQLite FTS5, and `sb status`.
MD
```

- [ ] **Step 3: Ingest the welcome note + reindex + check status**

```bash
sb ingest ~/second-brain/inbox/welcome.md
sb reindex
sb status
```

Expected: `sources: 1`, `indexes: duckdb=y fts=y`.

- [ ] **Step 4: No commit needed — this is user data, not tool code**

---

## Self-Review (done before handoff)

Spec coverage verified against `docs/superpowers/specs/2026-04-17-second-brain-design.md`:

| Spec section | Task | Status |
|---|---|---|
| §2 Two repos, clean boundary | Task 1, 2 | ✅ |
| §3 Tool repo layout | Task 1 | ✅ (subset — extract/graph/lint/inject/analytics deferred) |
| §3 Data layout | Tasks 2, 13 | ✅ |
| §4.1 Source frontmatter | Task 4 | ✅ |
| §4.2 Claim frontmatter | Task 4 | ✅ (stub, no extractor) |
| §4.3 Edge types & confidence | Task 4, 9 | ✅ |
| §4.4 Schema invariants | Tasks 4, 9, 13 | ✅ (1, 2, 3, 5) — (4, 6) require extractor, deferred |
| §5.1–5.4 Ingest pipeline | Tasks 10–14 | ✅ |
| §5.5 Claim extraction | — | ⏭ deferred to plan 2 |
| §5.6 Error handling (duplicate, converter fail) | Task 13 | ✅ |
| §6 Graph layer (DuckDB DDL) | Task 6 | ✅ (DDL) — DuckPGQ queries deferred |
| §6.3 Reindex guarantees (atomic, debounced, triggers) | Task 9 | ✅ (atomic) — debounce / triggers in plan 4 |
| §7 Lint | — | ⏭ deferred to plan 3 |
| §8 Retrieval | — | ⏭ deferred to plan 2 |
| §9 Maintenance | — | ⏭ deferred to plan 6 |
| §10 Habits & autonomy | — | ⏭ deferred to plan 5 |
| §11 Wizard | — | ⏭ deferred to plan 5 |
| §12 Consumer integration | — | ⏭ deferred to plan 4 |
| §13 Testing | Tasks 2–15 | ✅ (pytest, fixtures, coverage) |

Placeholder scan: no TBD / TODO / "implement later" / unresolved references. Task 14 Step 4 fixes a fragile Click wiring pattern from Step 3 and is called out explicitly with the final code. Integration-marked PDF text-extraction test is optional to keep the main run self-contained on machines without a working markitdown text-extraction dependency chain.

Type consistency: `SourceFolder`, `IngestInput`, `SourceArtifacts`, `RawArtifact`, `RawWrite`, `Config`, `Converter`, `DuckStore`, `FtsStore`, `SourceFrontmatter`, `ClaimFrontmatter`, `RelationType`, `EdgeConfidence`, `EventKind` — names match across tasks. `reindex()` (function) vs `run_reindex` import alias in CLI is intentional to avoid name collision with the Click command.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-second-brain-foundation.md`. The user has pre-authorized execution via subagents overnight:

> "and you can directly write your plan and directly start implementing with subagents without my confirmation, i am going to bed, you are fine."

Execution mode: **subagent-driven development** — one fresh subagent per task, with review between tasks. Follow-up plans (extraction, retrieval, injection, wizard, lint, maintenance) will be written after this foundation ships green.
