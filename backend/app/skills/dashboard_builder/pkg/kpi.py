# backend/app/skills/dashboard_builder/pkg/kpi.py
from __future__ import annotations

from dataclasses import dataclass

from app.skills.dashboard_builder.pkg.build import KPICard


@dataclass(frozen=True)
class RenderedKPITile:
    kind: str
    label: str
    value: str
    delta_str: str
    delta_class: str   # positive | negative | neutral
    comparison_period: str
    span: int
    sparkline_svg: str | None = None
    title: str | None = None


def render_kpi_tile(card: KPICard, span: int = 3) -> RenderedKPITile:
    value_str = _format_value(card.value, card.unit)
    delta_pct = card.delta * 100 if card.delta is not None else 0.0
    sign = "+" if delta_pct >= 0 else ""
    delta_str = f"{sign}{delta_pct:.1f}%"

    if card.delta is None or card.delta == 0:
        cls = "neutral"
    elif card.direction == "up_is_good":
        cls = "positive" if card.delta > 0 else "negative"
    else:  # down_is_good
        cls = "negative" if card.delta > 0 else "positive"

    return RenderedKPITile(
        kind="kpi",
        label=card.label,
        value=value_str,
        delta_str=delta_str,
        delta_class=cls,
        comparison_period=card.comparison_period,
        span=span,
    )


def _format_value(v: float | int | str, unit: str | None) -> str:
    if isinstance(v, str):
        return v
    if unit == "USD":
        if abs(v) >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        if abs(v) >= 1_000:
            return f"${v/1_000:.1f}K"
        return f"${v:,.2f}"
    if unit == "%":
        return f"{v*100:.1f}%"
    if unit:
        return f"{v:,.2f} {unit}"
    return f"{v:,.4g}"
