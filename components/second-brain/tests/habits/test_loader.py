from pathlib import Path

from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.habits.loader import (
    habits_path,
    load_habits,
    save_habits,
    validate_habits_file,
)


def _cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    home.mkdir()
    (home / ".sb").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def test_load_returns_defaults_when_file_missing(tmp_path):
    cfg = _cfg(tmp_path)
    assert load_habits(cfg) == Habits.default()


def test_save_then_load_round_trip(tmp_path):
    cfg = _cfg(tmp_path)
    h = Habits.default().model_copy(update={})
    save_habits(cfg, h)
    assert habits_path(cfg).exists()
    assert load_habits(cfg) == h


def test_partial_yaml_fills_in_defaults(tmp_path):
    cfg = _cfg(tmp_path)
    habits_path(cfg).write_text(
        "injection:\n  k: 9\n  max_tokens: 1200\n",
        encoding="utf-8",
    )
    h = load_habits(cfg)
    assert h.injection.k == 9
    assert h.injection.max_tokens == 1200
    # Untouched fields fall back to defaults.
    assert h.injection.enabled is True
    assert h.conflicts.grace_period_days == 14


def test_validate_habits_file_reports_errors(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("autonomy:\n  default: yolo\n", encoding="utf-8")
    errs = validate_habits_file(p)
    assert errs, "expected at least one validation error"
    assert any("default" in e for e in errs)
