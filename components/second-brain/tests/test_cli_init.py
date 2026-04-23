from __future__ import annotations

from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.habits.loader import habits_path, load_habits


def test_sb_init_defaults_scaffolds_tree_and_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))

    res = CliRunner().invoke(cli, ["init", "--defaults"])
    assert res.exit_code == 0, res.output

    cfg = Config.load()
    assert cfg.sources_dir.is_dir()
    assert cfg.claims_dir.is_dir()
    assert cfg.sb_dir.is_dir()
    assert habits_path(cfg).is_file()
    assert load_habits(cfg) is not None
    assert "UserPromptSubmit" in res.output
    assert "SECOND_BRAIN_HOME" in res.output


def test_sb_init_refuses_to_clobber_existing_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    runner = CliRunner()

    first = runner.invoke(cli, ["init", "--defaults"])
    assert first.exit_code == 0

    second = runner.invoke(cli, ["init", "--defaults"])
    # Scaffolding is idempotent, but habits.yaml must not be silently overwritten.
    assert second.exit_code != 0
    assert "habits.yaml already exists" in (second.output + (second.stderr or ""))


def test_sb_init_reconfigure_rewrites_habits(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    runner = CliRunner()

    runner.invoke(cli, ["init", "--defaults"])
    res = runner.invoke(cli, ["init", "--reconfigure", "--defaults"])

    assert res.exit_code == 0
    assert habits_path(Config.load()).is_file()
