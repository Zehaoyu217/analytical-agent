# backend/app/skills/report_builder/pkg/render_pdf.py
from __future__ import annotations

from datetime import date as _date
from pathlib import Path

from app.skills.reporting.report_builder.pkg.build import ReportSpec, Template
from app.skills.reporting.report_builder.pkg.render_html import render_html


class PDFBackendUnavailable(RuntimeError):  # noqa: N818 — keep existing public name
    """Raised when weasyprint (or its system deps) are missing."""


def render_pdf(
    spec: ReportSpec,
    template: Template,
    output_path: Path,
    today: _date | None = None,
) -> Path:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as exc:  # noqa: BLE001 — we re-raise as a typed error
        raise PDFBackendUnavailable(
            "PDF_BACKEND_UNAVAILABLE: weasyprint could not be imported. "
            "Install system libcairo + pango, then `pip install weasyprint`."
        ) from exc

    html = render_html(spec, template=template, today=today)
    HTML(string=html, base_url=str(Path.cwd())).write_pdf(str(output_path))
    return output_path
