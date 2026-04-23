"""Tests for RetrievalSuite modes (bm25 / hybrid / compare) + CLI plumbing."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("sqlite_vec")

from second_brain.cli import cli  # noqa: E402
from second_brain.config import Config  # noqa: E402
from second_brain.eval.runner import EvalRunner  # noqa: E402
from second_brain.eval.suites.retrieval import RetrievalSuite  # noqa: E402
from second_brain.index.vector_store import VectorStore  # noqa: E402


class DictEmbedder:
    """Maps known query+statement strings to canned vectors."""

    def __init__(self, mapping: dict[str, list[float]], dim: int = 3):
        self.mapping = mapping
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            if t in self.mapping:
                out.append(self.mapping[t])
            else:
                # deterministic fallback so unknown queries still produce vectors
                h = (hash(t) & 0xFFFF) / 0xFFFF
                out.append([h, 1.0 - h, 0.5])
        return out


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _seed_vectors(cfg: Config) -> None:
    # Seed vectors so the hybrid path has something to fuse.
    with VectorStore.open(cfg.vectors_path) as store:
        store.ensure_schema(dim=3)
        store.upsert("claim", "clm_transformer_attention", [1.0, 0.0, 0.0])
        store.upsert("claim", "clm_transformer_layernorm", [0.0, 1.0, 0.0])
        store.upsert("claim", "clm_rnn_gradient_vanishing", [0.0, 0.0, 1.0])


def test_bm25_mode_emits_one_row_per_query(sb_home: Path):
    cfg = Config.load()
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "retrieval"
    suite = RetrievalSuite(mode="bm25")
    runner = EvalRunner(cfg, {"retrieval": suite})
    report = runner.run("retrieval", fixtures)
    assert len(report.cases) == 2  # seed.yaml has 2 queries
    assert all(c.name.startswith("[bm25]") for c in report.cases)


def test_hybrid_mode_runs_and_reports(sb_home: Path):
    cfg = Config.load()
    _seed_vectors(cfg)
    embedder = DictEmbedder(
        {
            "self attention weighted sum": [1.0, 0.0, 0.0],
            "vanishing gradient recurrent": [0.0, 0.0, 1.0],
        }
    )
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "retrieval"
    suite = RetrievalSuite(mode="hybrid", embedder=embedder)
    runner = EvalRunner(cfg, {"retrieval": suite})
    report = runner.run("retrieval", fixtures)
    assert len(report.cases) == 2
    assert all(c.name.startswith("[hybrid]") for c in report.cases)


def test_compare_mode_emits_both_bm25_and_hybrid_rows(sb_home: Path):
    cfg = Config.load()
    _seed_vectors(cfg)
    embedder = DictEmbedder(
        {
            "self attention weighted sum": [1.0, 0.0, 0.0],
            "vanishing gradient recurrent": [0.0, 0.0, 1.0],
        }
    )
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "retrieval"
    suite = RetrievalSuite(mode="compare", embedder=embedder)
    runner = EvalRunner(cfg, {"retrieval": suite})
    report = runner.run("retrieval", fixtures)
    assert len(report.cases) == 4  # 2 queries * 2 modes
    labels = [c.name[:8] for c in report.cases]
    assert any(label.startswith("[bm25]") for label in labels)
    assert any(label.startswith("[hybrid") for label in labels)


def test_cli_eval_mode_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    fixtures = Path(__file__).parent / "eval" / "fixtures"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["eval", "--suite", "retrieval", "--fixtures-dir", str(fixtures),
         "--mode", "bm25"],
    )
    # Exit 0 on pass, 1 on eval-exception; we care that the command parsed.
    assert "--mode" not in result.output  # no usage error
    assert result.exit_code in (0, 1)
    assert "retrieval" in result.output
