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
