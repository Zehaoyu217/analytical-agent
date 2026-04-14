# backend/app/skills/dashboard_builder/pkg/__init__.py
from app.skills.dashboard_builder.pkg.build import (
    DashboardResult,
    DashboardSpec,
    KPICard,
    SectionSpec,
    build,
)

__all__ = [
    "DashboardResult",
    "DashboardSpec",
    "KPICard",
    "SectionSpec",
    "build",
]
