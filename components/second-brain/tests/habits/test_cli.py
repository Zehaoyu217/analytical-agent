from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.habits.loader import habits_path


def _init_home(tmp_path: Path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def test_sb_habits_init_writes_default_file(tmp_path, monkeypatch):
    home = _init_home(tmp_path, monkeypatch)
    res = CliRunner().invoke(cli, ["habits", "init"])
    assert res.exit_code == 0, res.output
    assert (home / ".sb" / "habits.yaml").exists()


def test_sb_habits_show_prints_injection_k(tmp_path, monkeypatch):
    _init_home(tmp_path, monkeypatch)
    res = CliRunner().invoke(cli, ["habits", "show"])
    assert res.exit_code == 0
    assert "injection" in res.output
    assert "k: 5" in res.output


def test_sb_habits_validate_reports_invalid(tmp_path, monkeypatch):
    home = _init_home(tmp_path, monkeypatch)
    habits_path_ = home / ".sb" / "habits.yaml"
    habits_path_.write_text("autonomy:\n  default: yolo\n", encoding="utf-8")
    res = CliRunner().invoke(cli, ["habits", "validate"])
    assert res.exit_code != 0
    assert "default" in res.output
