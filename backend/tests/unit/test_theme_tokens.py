from __future__ import annotations

from pathlib import Path

import pytest
from config.themes.theme_switcher import ThemeTokens

TOKENS_PATH = Path(__file__).resolve().parents[3] / "config" / "themes" / "tokens.yaml"


def test_loads_all_five_variants() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH)
    assert sorted(tokens.variants) == ["dark", "editorial", "light", "presentation", "print"]


def test_resolves_series_blues_by_role() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    assert tokens.series_color("actual") == "#0B2545"
    assert tokens.series_color("forecast") == "#8CB0D9"


def test_series_stroke_actual_is_solid_and_thick() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    stroke = tokens.series_stroke("actual")
    assert stroke.width == 2.5
    assert stroke.dash is None


def test_series_stroke_forecast_is_dashed() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    stroke = tokens.series_stroke("forecast")
    assert stroke.dash == [6, 3]


def test_editorial_uses_cream_surface() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("editorial")
    assert tokens.surface("base").startswith("#FB")


def test_unknown_variant_raises() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH)
    with pytest.raises(KeyError):
        tokens.for_variant("neon")


def test_categorical_has_at_least_18_colors() -> None:
    tokens = ThemeTokens.load(TOKENS_PATH).for_variant("light")
    assert len(tokens.categorical()) >= 18


def test_malformed_yaml_raises_useful_error(tmp_path: Path) -> None:
    """default_variant pointing to a missing variant should raise ValueError with a clear message."""
    bad_yaml = tmp_path / "tokens.yaml"
    bad_yaml.write_text(
        """
default_variant: neon
typography: {sans: "Inter"}
series_strokes:
  actual: {width: 2.5, dash: null}
variants:
  light:
    surface: {}
    series_blues: {}
    semantic: {}
    categorical: []
    diverging: {}
    chart: {}
"""
    )
    with pytest.raises(ValueError, match="default_variant"):
        ThemeTokens.load(bad_yaml)
