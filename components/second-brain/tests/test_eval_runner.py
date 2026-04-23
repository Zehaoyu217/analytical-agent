from __future__ import annotations

from pathlib import Path

import pytest

from second_brain.config import Config
from second_brain.eval.runner import EvalCase, EvalRunner


class _FakeSuite:
    name = "fake"

    def run(self, cfg, fixtures_dir):
        return [
            EvalCase(name="a", passed=True, metric=1.0),
            EvalCase(name="b", passed=False, metric=0.0),
        ]


def test_runner_dispatches_to_named_suite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    (tmp_path / ".sb").mkdir()
    cfg = Config.load()
    runner = EvalRunner(cfg, {"fake": _FakeSuite()})
    report = runner.run("fake", tmp_path)
    assert report.suite == "fake"
    assert report.pass_rate == 0.5
    assert not report.passed


def test_runner_raises_on_unknown(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    (tmp_path / ".sb").mkdir()
    cfg = Config.load()
    runner = EvalRunner(cfg, {})
    with pytest.raises(KeyError):
        runner.run("ghost", tmp_path)


def test_report_passed_true_when_all_cases_pass(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    (tmp_path / ".sb").mkdir()
    cfg = Config.load()

    class _AllPass:
        name = "ok"

        def run(self, cfg, fixtures_dir):
            return [EvalCase(name="a", passed=True, metric=1.0)]

    runner = EvalRunner(cfg, {"ok": _AllPass()})
    report = runner.run("ok", tmp_path)
    assert report.passed
    assert report.pass_rate == 1.0


def test_empty_report_pass_rate_zero(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(tmp_path))
    (tmp_path / ".sb").mkdir()
    cfg = Config.load()

    class _Empty:
        name = "empty"

        def run(self, cfg, fixtures_dir):
            return []

    runner = EvalRunner(cfg, {"empty": _Empty()})
    report = runner.run("empty", tmp_path)
    assert report.pass_rate == 0.0
    # vacuously true: no cases means no failures
    assert report.passed
