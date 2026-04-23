"""Tests for Second Brain tool handlers with graceful-degradation contract."""
from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest


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


def _write_habits_hybrid(home: Path) -> None:
    """Drop a minimal habits.yaml that flips retrieval.mode to hybrid."""
    (home / ".sb" / "habits.yaml").write_text(
        "retrieval:\n  mode: hybrid\n",
        encoding="utf-8",
    )


def _seed_fts(home: Path) -> None:
    """Seed kb.sqlite so make_retriever has a BM25 index available."""
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


def test_sb_search_uses_make_retriever_factory(monkeypatch, tmp_path):
    """When habits mode=hybrid AND vectors.sqlite exists, factory returns hybrid."""
    pytest.importorskip("sqlite_vec")
    from second_brain.config import Config
    from second_brain.index.retriever import HybridRetriever
    from second_brain.index.vector_store import VectorStore

    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    _seed_fts(home)
    _write_habits_hybrid(home)
    # Create vectors.sqlite so the hybrid branch is taken.
    cfg_bootstrap = Config(home=home, sb_dir=home / ".sb")
    with VectorStore.open(cfg_bootstrap.vectors_path) as store:
        store.ensure_schema(dim=3)

    _point_at_home(monkeypatch, home, enabled=True)
    from app.tools import sb_tools
    importlib.reload(sb_tools)

    captured: dict = {}

    # Spy on the factory used by the broker layer.
    from second_brain.index import retriever as retriever_mod
    from second_brain.research import broker as broker_mod

    real_factory = retriever_mod.make_retriever

    def spy(cfg):  # noqa: ANN001, ANN202
        r = real_factory(cfg)
        captured["type"] = type(r).__name__
        return r

    monkeypatch.setattr(retriever_mod, "make_retriever", spy)
    monkeypatch.setattr(broker_mod, "make_retriever", spy)

    # Patch the embedder factory so we don't try to load sentence-transformers.
    from second_brain.index import vector_retriever as vr

    class _Stub:
        dim = 3

        def embed(self, texts):  # noqa: ANN001, ANN202
            return [[1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(vr, "_default_embedder_factory", lambda _cfg: _Stub())

    res = sb_tools.sb_search({"query": "attention", "k": 3, "scope": "claims"})
    assert res["ok"] is True
    assert captured["type"] == HybridRetriever.__name__


def test_sb_search_falls_back_to_bm25_when_no_vectors(monkeypatch, tmp_path):
    """Even with mode=hybrid, missing vectors.sqlite must degrade to BM25."""
    from second_brain.index.retriever import BM25Retriever

    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    _seed_fts(home)
    _write_habits_hybrid(home)
    # Note: no VectorStore created → vectors.sqlite absent.

    _point_at_home(monkeypatch, home, enabled=True)
    from app.tools import sb_tools
    importlib.reload(sb_tools)

    captured: dict = {}
    from second_brain.index import retriever as retriever_mod
    from second_brain.research import broker as broker_mod

    real_factory = retriever_mod.make_retriever

    def spy(cfg):  # noqa: ANN001, ANN202
        r = real_factory(cfg)
        captured["type"] = type(r).__name__
        return r

    monkeypatch.setattr(retriever_mod, "make_retriever", spy)
    monkeypatch.setattr(broker_mod, "make_retriever", spy)

    res = sb_tools.sb_search({"query": "attention", "k": 3, "scope": "claims"})
    assert res["ok"] is True
    assert captured["type"] == BM25Retriever.__name__
