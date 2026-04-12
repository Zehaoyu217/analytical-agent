from __future__ import annotations

import pandas as pd

from app.skills.html_tables.pkg.renderer import render


def test_render_emits_table_and_style() -> None:
    df = pd.DataFrame({"name": ["a", "b"], "count": [10, 20]})
    out = render(df, title="Counts")
    assert '<table class="ga-table"' in out
    assert "<style" in out
    assert "<caption>Counts</caption>" in out


def test_numeric_columns_get_cell_num_class() -> None:
    df = pd.DataFrame({"name": ["a"], "count": [10]})
    out = render(df)
    assert 'class="cell-num"' in out


def test_truncates_beyond_max_rows() -> None:
    df = pd.DataFrame({"x": list(range(25))})
    out = render(df, max_rows=10)
    assert "15 rows truncated" in out


def test_custom_cell_classes_applied() -> None:
    df = pd.DataFrame({"delta": [1.0, -2.0]})
    classes = {(0, "delta"): ["cell-positive"], (1, "delta"): ["cell-negative"]}
    out = render(df, cell_classes=classes)
    assert "cell-positive" in out
    assert "cell-negative" in out


def test_escapes_unsafe_content_in_headers_and_cells() -> None:
    df = pd.DataFrame({"<script>": ["a & b", "<img src=x>"]})
    out = render(df)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "a &amp; b" in out
    assert "<img src=x>" not in out


def test_escapes_quote_in_custom_class_tokens() -> None:
    df = pd.DataFrame({"x": [1]})
    classes = {(0, "x"): ['foo" onmouseover="alert(1)']}
    out = render(df, cell_classes=classes)
    assert 'onmouseover="alert(1)"' not in out


def test_renders_list_valued_cell_without_crashing() -> None:
    df = pd.DataFrame({"items": [["a", "b"], None]})
    out = render(df)
    assert "ga-table" in out
