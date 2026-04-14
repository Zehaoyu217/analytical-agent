from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
from config.themes.altair_theme import active_tokens, register_all, use_variant
from config.themes.table_css import render_table_css

from app.skills.altair_charts.pkg.histogram import histogram
from app.skills.data_profiler.pkg.risks import Risk
from app.skills.html_tables.pkg.renderer import render as render_table

VARIANT = "editorial"


def _header(name: str, n_rows: int, n_cols: int, summary: str, tokens: Any) -> str:
    return (
        f'<header style="padding:24px 32px;border-bottom:1px solid {tokens.surface("border")};">'
        f'<h1 style="margin:0 0 6px 0;font-family:Source Serif Pro,Georgia,serif;'
        f'font-size:28px;color:{tokens.surface("text")};">{escape(name)} — data profile</h1>'
        f'<div style="color:{tokens.surface("text_muted")};font-size:13px;">'
        f"{n_rows:,} rows × {n_cols} cols</div>"
        f'<p style="margin:12px 0 0;font-size:15px;line-height:1.5;color:{tokens.surface("text")}">'
        f"{escape(summary)}</p></header>"
    )


def _risks_section(risks: list[Risk], tokens: Any) -> str:
    if not risks:
        return (
            f'<section style="padding:16px 32px;color:{tokens.surface("text_muted")};">'
            "No risks surfaced.</section>"
        )
    rows = []
    for r in sorted(risks, key=lambda x: x.sort_key()):
        chip_bg = {
            "BLOCKER": tokens.semantic("negative"),
            "HIGH": tokens.semantic("warning"),
            "MEDIUM": tokens.semantic("info"),
            "LOW": tokens.surface("text_muted"),
        }[r.severity]
        rows.append(
            f'<tr><td><span style="background:{chip_bg};color:#fff;padding:2px 8px;'
            f'border-radius:3px;font-size:11px;font-weight:600;">{r.severity}</span></td>'
            f"<td>{escape(r.kind)}</td>"
            f"<td>{escape(', '.join(r.columns))}</td>"
            f"<td>{escape(r.detail)}</td>"
            f"<td>{escape(r.mitigation)}</td></tr>"
        )
    return (
        '<section style="padding:16px 32px;">'
        '<h2 style="font-family:Source Serif Pro,serif;">Risks</h2>'
        '<table class="ga-table"><thead><tr>'
        "<th>Severity</th><th>Kind</th><th>Columns</th><th>Detail</th><th>Mitigation</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></section>"
    )


def _schema_section(sections: dict[str, Any]) -> str:
    sch = sections.get("schema")
    if not sch:
        return ""
    data = pd.DataFrame(sch["columns"])
    return (
        '<section style="padding:16px 32px;">'
        '<h2 style="font-family:Source Serif Pro,serif;">Schema</h2>'
        + render_table(data, variant=VARIANT, max_rows=100)
        + "</section>"
    )


def _distribution_section(df: pd.DataFrame) -> str:
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])][:4]
    if not numeric_cols:
        return ""
    charts_html = []
    for col in numeric_cols:
        try:
            chart = histogram(df, field=col, bins=30, title=col)
            charts_html.append(chart.to_html())
        except Exception:  # noqa: BLE001
            continue
    if not charts_html:
        return ""
    return (
        '<section style="padding:16px 32px;">'
        '<h2 style="font-family:Source Serif Pro,serif;">Distributions</h2>'
        + "".join(f'<div style="margin:12px 0;">{c}</div>' for c in charts_html)
        + "</section>"
    )


def render_html_report(
    name: str,
    n_rows: int,
    n_cols: int,
    summary: str,
    risks: list[Risk],
    sections: dict[str, Any],
    df: pd.DataFrame,
) -> str:
    register_all()
    use_variant(VARIANT)
    tokens = active_tokens()

    css = render_table_css(variant=VARIANT)
    body = [
        _header(name, n_rows, n_cols, summary, tokens),
        _risks_section(risks, tokens),
        _schema_section(sections),
        _distribution_section(df),
    ]
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{escape(name)} profile</title>"
        f"{css}</head>"
        f'<body style="margin:0;background:{tokens.surface("base")};color:{tokens.surface("text")};'
        'font-family:Inter,system-ui,sans-serif;">'
        + "".join(body)
        + "</body></html>"
    )
