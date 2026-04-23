from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalRunner
from second_brain.eval.suites.graph import GraphSuite


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_graph_suite_passes_on_seed(sb_home: Path):
    cfg = Config.load()
    runner = EvalRunner(cfg, {"graph": GraphSuite()})
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "graph"
    report = runner.run("graph", fixtures)
    assert report.passed, [c for c in report.cases if not c.passed]
    assert len(report.cases) >= 2
