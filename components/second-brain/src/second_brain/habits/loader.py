from __future__ import annotations

from io import StringIO
from pathlib import Path

from pydantic import ValidationError
from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.habits.schema import Habits

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False


def habits_path(cfg: Config) -> Path:
    return cfg.sb_dir / "habits.yaml"


def load_habits(cfg: Config) -> Habits:
    path = habits_path(cfg)
    if not path.exists():
        return Habits.default()
    raw = _yaml.load(path.read_text(encoding="utf-8")) or {}
    return Habits.model_validate(raw)


def save_habits(cfg: Config, habits: Habits) -> None:
    path = habits_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = StringIO()
    _yaml.dump(habits.model_dump(mode="python"), buf)
    path.write_text(buf.getvalue(), encoding="utf-8")


def validate_habits_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        raw = _yaml.load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return [f"yaml parse error: {exc}"]
    try:
        Habits.model_validate(raw)
    except ValidationError as exc:
        return [str(e) for e in exc.errors()]
    return []
