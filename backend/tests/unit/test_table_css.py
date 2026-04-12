from __future__ import annotations

from pathlib import Path

from config.themes.table_css import render_table_css

TOKENS_PATH = Path(__file__).resolve().parents[3] / "config" / "themes" / "tokens.yaml"


def test_emits_style_block_with_variant_surface_color() -> None:
    css = render_table_css(variant="editorial", tokens_path=TOKENS_PATH)
    assert css.startswith("<style")
    assert "#FBF7EE" in css


def test_emits_semantic_color_for_positive_cells() -> None:
    css = render_table_css(variant="light", tokens_path=TOKENS_PATH)
    assert ".cell-positive" in css
    assert "#4E7A3C" in css


def test_print_variant_is_greyscale_only() -> None:
    css = render_table_css(variant="print", tokens_path=TOKENS_PATH)
    import re
    hex_codes = re.findall(r"#[0-9A-Fa-f]{6}", css)
    for code in hex_codes:
        r, g, b = int(code[1:3], 16), int(code[3:5], 16), int(code[5:7], 16)
        assert r == g == b, f"print variant should be achromatic, got {code}"
