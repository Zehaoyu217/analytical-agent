# backend/app/skills/dashboard_builder/pkg/build.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Layout = Literal["bento", "grid", "single_column"]
Mode = Literal["standalone_html", "a2ui"]
Direction = Literal["up_is_good", "down_is_good"]
SectionKind = Literal["kpi", "chart", "table"]


@dataclass(frozen=True)
class KPICard:
    label: str
    value: float | int | str
    delta: float | None
    comparison_period: str
    direction: Direction
    sparkline_artifact_id: str | None = None
    unit: str | None = None


@dataclass(frozen=True)
class SectionSpec:
    kind: SectionKind
    span: int                        # 1-12 grid columns; bento spans up to 12
    payload: Any                     # KPICard | chart artifact id (str) | table artifact id (str)
    title: str | None = None


@dataclass(frozen=True)
class DashboardSpec:
    title: str
    author: str
    layout: Layout
    sections: tuple[SectionSpec, ...]
    theme_variant: str = "light"
    subtitle: str | None = None


@dataclass(frozen=True)
class DashboardResult:
    mode: Mode
    path: Path | None                # None for a2ui in-memory result
    a2ui_payload: dict[str, Any] | None
    artifact_id: str


_MAX_SECTIONS = 12
_VALID_LAYOUTS = {"bento", "grid", "single_column"}
_VALID_MODES = {"standalone_html", "a2ui"}
_VALID_DIRECTIONS = {"up_is_good", "down_is_good"}


def validate_spec(spec: DashboardSpec) -> None:
    if not spec.sections:
        raise ValueError("EMPTY_DASHBOARD: Dashboard has no sections.")
    if len(spec.sections) > _MAX_SECTIONS:
        raise ValueError(
            f"TOO_MANY_SECTIONS: Dashboard has {len(spec.sections)} sections; "
            f"maximum is {_MAX_SECTIONS}."
        )
    if spec.layout not in _VALID_LAYOUTS:
        raise ValueError(
            f"UNKNOWN_LAYOUT: Unknown layout '{spec.layout}'. "
            "Use bento | grid | single_column."
        )
    for section in spec.sections:
        if section.kind == "kpi":
            kpi: KPICard = section.payload
            if kpi.delta is None:
                raise ValueError(
                    f"KPI_NO_DELTA: KPI '{kpi.label}' has no delta; "
                    "cards must show delta or be dropped."
                )
            if kpi.direction not in _VALID_DIRECTIONS:
                raise ValueError(
                    f"UNKNOWN_DIRECTION: KPI '{kpi.label}' has direction='{kpi.direction}'. "
                    "Use up_is_good | down_is_good."
                )


# ---------------------------------------------------------------------------
# Orchestrator. Renders standalone_html or a2ui.
# ---------------------------------------------------------------------------
from datetime import date as _date  # noqa: E402

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

from app.skills.reporting.dashboard_builder.pkg.a2ui import to_a2ui  # noqa: E402
from app.skills.reporting.dashboard_builder.pkg.kpi import render_kpi_tile  # noqa: E402
from app.skills.reporting.dashboard_builder.pkg.layouts import resolve_spans  # noqa: E402

_OUTPUT_DIR = Path("data/dashboards")
_DASHBOARD_CSS = Path("config/themes/dashboard.css")
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html", "htm", "xml"), default=True),
    trim_blocks=True,
    lstrip_blocks=True,
)


def build(
    spec: DashboardSpec,
    mode: Mode = "standalone_html",
    session_id: str | None = None,
    today: _date | None = None,
    chart_resolver: Any = None,
    table_resolver: Any = None,
) -> DashboardResult:
    validate_spec(spec)
    if mode not in _VALID_MODES:
        raise ValueError(f"UNKNOWN_MODE: Unknown mode '{mode}'. Use standalone_html | a2ui.")

    stem = _slugify(spec.title) or "dashboard"

    if mode == "a2ui":
        payload = to_a2ui(spec)
        return DashboardResult(
            mode=mode,
            path=None,
            a2ui_payload=payload,
            artifact_id=f"dash-a2ui-{stem}",
        )

    # standalone_html
    spans = resolve_spans([s.span for s in spec.sections], layout=spec.layout)
    rendered = []
    for section, span in zip(spec.sections, spans, strict=True):
        if section.kind == "kpi":
            tile = render_kpi_tile(section.payload, span=span)
            rendered.append(
                {
                    "kind": "kpi",
                    "span": span,
                    "label": tile.label,
                    "value": tile.value,
                    "delta_str": tile.delta_str,
                    "delta_class": tile.delta_class,
                    "comparison_period": tile.comparison_period,
                    "sparkline_svg": None,
                }
            )
        elif section.kind == "chart":
            chart_svg = (
                chart_resolver(section.payload)
                if chart_resolver
                else f"<!-- chart {section.payload} -->"
            )
            rendered.append({
                "kind": "chart",
                "span": span,
                "title": section.title,
                "chart_svg": chart_svg,
            })
        elif section.kind == "table":
            table_html = (
                table_resolver(section.payload)
                if table_resolver
                else f"<!-- table {section.payload} -->"
            )
            rendered.append({
                "kind": "table",
                "span": span,
                "title": section.title,
                "table_html": table_html,
            })
        else:
            raise ValueError(f"Unknown section kind '{section.kind}'")

    tpl = _env.get_template("dashboard.html.j2")
    html = tpl.render(
        spec=spec,
        rendered_tiles=rendered,
        today=(today or _date.today()).isoformat(),
        dashboard_css_uri=str(_DASHBOARD_CSS),
    )

    base = _OUTPUT_DIR / (session_id or "default")
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{stem}.html"
    out.write_text(html, encoding="utf-8")

    return DashboardResult(
        mode=mode,
        path=out,
        a2ui_payload=None,
        artifact_id=f"dash-html-{stem}",
    )


def _slugify(s: str) -> str:
    import re

    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower())
    return s.strip("-")
