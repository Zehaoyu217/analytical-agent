from __future__ import annotations

from html import escape

import pandas as pd
from config.themes.table_css import render_table_css


def _is_numeric(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series)


def _is_missing(val: object) -> bool:
    # pd.isna raises on array-like cells ("truth value is ambiguous"); guard first.
    if not pd.api.types.is_scalar(val):
        return False
    return bool(pd.isna(val))


def render(
    df: pd.DataFrame,
    title: str | None = None,
    caption: str | None = None,
    variant: str = "light",
    max_rows: int = 200,
    cell_classes: dict[tuple[int, str], list[str]] | None = None,
) -> str:
    cell_classes = cell_classes or {}
    css = render_table_css(variant=variant)
    caption_text = caption or title
    caption_html = f"<caption>{escape(caption_text)}</caption>" if caption_text else ""

    numeric_cols = {c for c in df.columns if _is_numeric(df[c])}
    thead = "<thead><tr>" + "".join(f"<th>{escape(str(c))}</th>" for c in df.columns) + "</tr></thead>"

    rows_html: list[str] = []
    truncated = max(0, len(df) - max_rows)
    for row_i, (_, row) in enumerate(df.head(max_rows).iterrows()):
        cells: list[str] = []
        for col in df.columns:
            classes: list[str] = []
            if col in numeric_cols:
                classes.append("cell-num")
            classes.extend(cell_classes.get((row_i, col), []))
            cls_attr = (
                f' class="{escape(" ".join(classes), quote=True)}"' if classes else ""
            )
            val = row[col]
            shown = "" if _is_missing(val) else escape(str(val))
            cells.append(f"<td{cls_attr}>{shown}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")
    if truncated > 0:
        span = len(df.columns)
        rows_html.append(
            f'<tr><td colspan="{span}" class="cell-muted">'
            f"… [{truncated} rows truncated]</td></tr>"
        )
    tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
    table = f'<table class="ga-table">{caption_html}{thead}{tbody}</table>'
    return css + "\n" + table
