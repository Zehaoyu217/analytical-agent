# backend/app/skills/altair_charts/pkg/_common.py
from __future__ import annotations

from typing import Any

import altair as alt
from config.themes.altair_theme import active_tokens, register_all


def ensure_theme_registered() -> None:
    """Call once at chart build time to guarantee themes exist."""
    try:
        if "gir_light" not in alt.themes.names():
            register_all()
    except AttributeError:
        register_all()


_FALLBACK_ROLE = "actual"


def resolve_series_style(role: str) -> dict[str, Any]:
    """Return Altair mark kwargs for a named series role.

    Data-driven role values (from `multi_line` series columns) may not match any
    registered token — fall back to the `actual` role and let the caller
    distinguish runs by other encodings (category hue, panel, etc.).
    """
    tokens = active_tokens()
    try:
        color = tokens.series_color(role)
        stroke = tokens.series_stroke(role)
    except KeyError:
        color = tokens.series_color(_FALLBACK_ROLE)
        stroke = tokens.series_stroke(_FALLBACK_ROLE)
    props: dict[str, Any] = {"color": color, "strokeWidth": stroke.width}
    if stroke.dash is not None:
        props["strokeDash"] = stroke.dash
    return props


def diverging_scheme_values() -> list[str]:
    tokens = active_tokens()
    div = tokens.diverging()
    return [div["negative"], div["neutral"], div["positive"]]
