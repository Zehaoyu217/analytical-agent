# backend/app/harness/sandbox_bootstrap.py
from __future__ import annotations

from pathlib import Path


def build_sandbox_bootstrap(
    session_id: str,
    dataset_path: str | Path | None,
) -> str:
    parts = [
        "import sys",
        "import os",
        "import numpy as np",
        "import pandas as pd",
        "import altair as alt",
        "import duckdb",
        "",
        "from config.themes.altair_theme import register_all as ensure_registered, use_variant",
        "ensure_registered()",
        "",
        "from app.skills.correlation import correlate",
        "from app.skills.group_compare import compare",
        "from app.skills.stat_validate import validate",
        "from app.skills.data_profiler import profile",
        "from app.skills.time_series import (",
        "    characterize, decompose, find_anomalies,",
        "    find_changepoints, lag_correlate,",
        ")",
        "from app.skills.distribution_fit import fit",
        "from app.skills.altair_charts.pkg import bar, multi_line, histogram, scatter_trend, boxplot, correlation_heatmap",
        "from app.skills.report_builder.pkg import build as report_build",
        "from app.skills.analysis_plan.pkg import plan as analysis_plan",
        "from app.skills.dashboard_builder.pkg import build as dashboard_build",
        "",
        f"_SESSION_ID = {session_id!r}",
    ]
    if dataset_path:
        path = str(Path(dataset_path))
        parts.append(f"df = pd.read_parquet({path!r})")
    else:
        parts.append("df = None")
    return "\n".join(parts) + "\n"
