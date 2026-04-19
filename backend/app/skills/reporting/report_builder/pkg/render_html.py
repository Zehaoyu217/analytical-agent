# backend/app/skills/report_builder/pkg/render_html.py
from __future__ import annotations

from datetime import date as _date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.skills.reporting.report_builder.pkg.build import (
    FindingSection,
    ReportSpec,
    Template,
    validate_spec,
)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html", "htm", "xml"), default=True),
    trim_blocks=True,
    lstrip_blocks=True,
)

_EDITORIAL_CSS = Path("config/themes/editorial.css")


def _md_to_html(md: str) -> str:
    """Very small markdown conversion: bold + paragraphs. Real projects use markdown-it-py.
    Kept deliberately tiny so report_builder has zero optional-dep surface."""
    import re

    html = md
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    # paragraphs on blank-line splits
    parts = [p.strip() for p in re.split(r"\n\s*\n", html.strip()) if p.strip()]
    return "\n".join(f"<p>{p}</p>" for p in parts)


def _augment(section: FindingSection) -> FindingSection:
    # Mutate-free: rebuild with body_html attribute attached via a shim dict.
    return FindingSection(
        finding=section.finding,
        body=section.body,
        chart_id=section.chart_id,
        table_id=section.table_id,
        caveats=section.caveats,
    )


def render_html(
    spec: ReportSpec,
    template: Template = "research_memo",
    today: _date | None = None,
) -> str:
    validate_spec(spec, template)
    # Compute a shimmed spec where each FindingSection exposes `body_html`.
    shimmed_findings = []
    for fs in spec.findings:
        body_html = _md_to_html(fs.body)
        shimmed = _ShimSection(fs, body_html)
        shimmed_findings.append(shimmed)
    shim = _ShimSpec(spec, tuple(shimmed_findings))

    tpl = _env.get_template(f"{template}.html.j2")
    return tpl.render(
        spec=shim,
        today=(today or _date.today()).isoformat(),
        editorial_css_uri=str(_EDITORIAL_CSS),
    )


class _ShimSection:
    """Read-only view over FindingSection adding body_html for Jinja2."""

    def __init__(self, fs: FindingSection, body_html: str) -> None:
        self._fs = fs
        self.body_html = body_html

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fs, name)


class _ShimSpec:
    def __init__(self, spec: ReportSpec, findings: tuple[_ShimSection, ...]) -> None:
        self._spec = spec
        self.findings = findings

    def __getattr__(self, name: str) -> Any:
        return getattr(self._spec, name)
