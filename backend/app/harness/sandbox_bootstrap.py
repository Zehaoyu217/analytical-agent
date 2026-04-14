# backend/app/harness/sandbox_bootstrap.py
from __future__ import annotations

from pathlib import Path

_SKILL_IMPORTS: list[str] = [
    "import sys",
    "import os",
    "import json",
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
    "from app.skills.altair_charts.pkg import (",
    "    bar, multi_line, histogram,",
    "    scatter_trend, boxplot, correlation_heatmap,",
    ")",
    "from app.skills.report_builder.pkg.build import build as report_build",
    "from app.skills.analysis_plan.pkg.plan import plan as analysis_plan",
    "from app.skills.dashboard_builder.pkg.build import build as dashboard_build",
]


def build_sandbox_bootstrap(
    session_id: str,
    dataset_path: str | Path | None,
) -> str:
    parts = list(_SKILL_IMPORTS) + [
        "",
        f"_SESSION_ID = {session_id!r}",
    ]
    if dataset_path:
        path = str(Path(dataset_path))
        parts.append(f"df = pd.read_parquet({path!r})")
    else:
        parts.append("df = None")
    return "\n".join(parts) + "\n"


def build_duckdb_globals(
    session_id: str,
    dataset_path: str | Path | None,
) -> str:
    """Build a Python preamble for the sandbox that wires up a DuckDB session.

    Opens (or creates) ``data/sessions/{session_id}.duckdb`` and, when
    *dataset_path* is provided, reads the file into a pandas DataFrame and
    registers it as a DuckDB table named ``"dataset"``.

    The returned string is valid Python source intended to be prepended to
    user code inside the sandbox subprocess.  It exposes:

    * ``df``        – pandas DataFrame (or ``None`` when no dataset)
    * ``conn``      – the open DuckDB connection for this session
    * ``save_artifact(name, data)`` – writes JSON to
                      ``data/artifacts/{session_id}/{name}.json``
    """
    db_path = f"data/sessions/{session_id}.duckdb"
    artifact_dir = f"data/artifacts/{session_id}"

    parts: list[str] = list(_SKILL_IMPORTS) + [
        "",
        f"_SESSION_ID = {session_id!r}",
        f"_DB_PATH = {db_path!r}",
        f"_ARTIFACT_DIR = {artifact_dir!r}",
        "",
        "import pathlib as _pathlib",
        "_pathlib.Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)",
        "conn = duckdb.connect(_DB_PATH)",
        "",
    ]

    if dataset_path:
        path = str(Path(dataset_path))
        suffix = Path(dataset_path).suffix.lower()
        if suffix == ".csv":
            read_expr = f"pd.read_csv({path!r})"
        else:
            read_expr = f"pd.read_parquet({path!r})"
        parts += [
            f"df = {read_expr}",
            'conn.register("dataset", df)',
        ]
    else:
        parts.append("df = None")

    parts += [
        "",
        "def save_artifact(name: str, data: object) -> str:",
        "    _art_dir = _pathlib.Path(_ARTIFACT_DIR)",
        "    _art_dir.mkdir(parents=True, exist_ok=True)",
        "    _art_path = _art_dir / f'{name}.json'",
        "    with open(_art_path, 'w', encoding='utf-8') as _fh:",
        "        json.dump(data, _fh)",
        "    return str(_art_path)",
        "",
    ]

    return "\n".join(parts) + "\n"
