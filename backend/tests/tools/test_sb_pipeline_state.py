"""Tests for sb_pipeline_state helper."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.tools import sb_pipeline_state


@pytest.fixture
def cfg(tmp_path: Path) -> SimpleNamespace:
    sb_dir = tmp_path / "sb"
    sb_dir.mkdir()
    return SimpleNamespace(sb_dir=sb_dir)


def test_read_state_returns_empty_when_file_missing(cfg: SimpleNamespace) -> None:
    state = sb_pipeline_state.read_state(cfg)
    assert state == {
        "ingest": {"last_run_at": None, "result": None},
        "digest": {"last_run_at": None, "result": None},
        "maintain": {"last_run_at": None, "result": None},
    }


def test_write_phase_persists_and_reads_back(cfg: SimpleNamespace) -> None:
    assert sb_pipeline_state.write_phase(cfg, "ingest", {"sources_added": 3}) is True
    state = sb_pipeline_state.read_state(cfg)
    assert state["ingest"]["result"] == {"sources_added": 3}
    assert state["ingest"]["last_run_at"] is not None
    assert state["ingest"]["last_run_at"].endswith("Z")
    # other slots untouched
    assert state["digest"]["result"] is None


def test_write_phase_updates_only_target_slot(cfg: SimpleNamespace) -> None:
    sb_pipeline_state.write_phase(cfg, "ingest", {"sources_added": 1})
    sb_pipeline_state.write_phase(cfg, "digest", {"entries": 4, "emitted": True, "pending": 2})
    state = sb_pipeline_state.read_state(cfg)
    assert state["ingest"]["result"] == {"sources_added": 1}
    assert state["digest"]["result"] == {"entries": 4, "emitted": True, "pending": 2}
    assert state["maintain"]["result"] is None


def test_read_state_tolerates_malformed_json(cfg: SimpleNamespace) -> None:
    (cfg.sb_dir / ".state").mkdir()
    (cfg.sb_dir / ".state" / "pipeline.json").write_text("{not json")
    state = sb_pipeline_state.read_state(cfg)
    assert state["ingest"]["result"] is None


def test_run_maintain_writes_summary(
    cfg: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeReport:
        lint_counts = {"error": 0, "warning": 2}
        open_contradictions = 1
        stale_abstracts = ["claim_a"]
        analytics_rebuilt = True
        habit_proposals = 0
        fts_bytes_before = 100
        fts_bytes_after = 95
        duck_bytes_before = 200
        duck_bytes_after = 190

    class _FakeRunner:
        def __init__(self, _cfg: object) -> None:
            pass

        def run(self, *, build_digest: bool) -> _FakeReport:
            assert build_digest is False
            return _FakeReport()

    monkeypatch.setattr(
        "second_brain.maintain.runner.MaintainRunner", _FakeRunner
    )

    summary = sb_pipeline_state.run_maintain(cfg)
    assert summary["lint_warnings"] == 2
    assert summary["lint_errors"] == 0
    assert summary["stale_count"] == 1
    assert summary["open_contradictions"] == 1

    persisted = json.loads(
        (cfg.sb_dir / ".state" / "pipeline.json").read_text(encoding="utf-8")
    )
    assert persisted["maintain"]["result"]["lint_warnings"] == 2
