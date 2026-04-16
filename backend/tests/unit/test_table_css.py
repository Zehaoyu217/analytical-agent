"""Table CSS contract tests.

``render_table_css`` returns a ``<style>`` block for the ``.ga-table``
scoped selector family.  These tests verify the output shape, required
selectors, and variant-arg behaviour.
"""
from __future__ import annotations

from config.themes.table_css import render_table_css


def test_returns_style_block() -> None:
    css = render_table_css()
    assert css.strip().startswith("<style>")
    assert css.strip().endswith("</style>")


def test_returns_nonempty_css() -> None:
    css = render_table_css()
    assert css
    assert "border-collapse: collapse" in css


def test_contains_ga_table_scoped_selectors() -> None:
    css = render_table_css()
    assert ".ga-table {" in css
    assert ".ga-table th" in css and ".ga-table td" in css


def test_variant_arg_accepted_but_ignored() -> None:
    """Variant arg is accepted; output is identical for all values."""
    default = render_table_css()
    editorial = render_table_css(variant="editorial")
    print_variant = render_table_css(variant="print")
    assert default == editorial == print_variant


def test_uses_monospace_family_for_data_density() -> None:
    """Swiss/terminal aesthetic — monospace is non-negotiable for tables."""
    assert "monospace" in render_table_css()
