from __future__ import annotations

from pathlib import Path

import altair as alt
import pytest

from config.themes.altair_theme import register_all, use_variant

TOKENS_PATH = Path(__file__).resolve().parents[3] / "config" / "themes" / "tokens.yaml"


@pytest.fixture(autouse=True)
def reset_active():
    register_all(TOKENS_PATH)
    yield


def test_register_all_registers_five_variant_names() -> None:
    names = alt.themes.names()
    for variant in ("light", "dark", "editorial", "presentation", "print"):
        assert f"gir_{variant}" in names


def test_use_variant_activates_theme() -> None:
    use_variant("editorial")
    config = alt.themes.get()()
    assert "config" in config
    assert config["config"]["background"].startswith("#FB")


def test_theme_provides_range_category_of_18_colors() -> None:
    use_variant("light")
    config = alt.themes.get()()
    assert len(config["config"]["range"]["category"]) >= 18


def test_theme_title_anchor_is_start() -> None:
    use_variant("editorial")
    config = alt.themes.get()()
    assert config["config"]["title"]["anchor"] == "start"
