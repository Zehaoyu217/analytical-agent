from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalRunner
from second_brain.eval.suites.retrieval import RetrievalSuite


@pytest.fixture()
def sb_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_retrieval_suite_passes_on_seed(sb_home: Path):
    cfg = Config.load()
    runner = EvalRunner(cfg, {"retrieval": RetrievalSuite()})
    fixtures = Path(__file__).parent / "eval" / "fixtures" / "retrieval"
    report = runner.run("retrieval", fixtures)
    assert report.suite == "retrieval"
    assert report.cases
    assert report.passed, [c for c in report.cases if not c.passed]
