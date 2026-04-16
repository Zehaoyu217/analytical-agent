# backend/app/harness/sandbox_bootstrap.py
from __future__ import annotations

from pathlib import Path

# Absolute path to the backend directory — injected into subprocess sys.path
# so that `config.*` and `app.*` packages are importable from the temp-file sandbox.
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent.parent)

_SKILL_IMPORTS: list[str] = [
    "import sys",
    "import os",
    # Ensure the backend directory is on sys.path so that config.* and app.*
    # packages are importable even when the sandbox runs from a temp file.
    f"if {_BACKEND_DIR!r} not in sys.path:",
    f"    sys.path.insert(0, {_BACKEND_DIR!r})",
    "import json",
    "import numpy as np",
    "import pandas as pd",
    "import altair as alt",
    "import duckdb",
    "",
    "from config.themes.altair_theme import register_all as ensure_registered, use_variant",
    "ensure_registered()",
    "",
    "from app.skills.statistical_analysis.correlation import correlate",
    "from app.skills.statistical_analysis.group_compare import compare",
    "from app.skills.statistical_analysis.stat_validate import validate",
    "from app.skills.data_profiler import profile",
    "from app.skills.statistical_analysis.time_series import characterize, decompose, find_anomalies, find_changepoints, lag_correlate",
    "from app.skills.statistical_analysis.distribution_fit import fit",
    "from app.skills.charting.altair_charts.pkg import actual_vs_forecast, area_cumulative, bar, bar_with_reference, boxplot, correlation_heatmap, dumbbell, ecdf, grouped_bar, histogram, kde, lollipop, multi_line, range_band, scatter_trend, slope, small_multiples, stacked_bar, violin, waterfall",
    "from app.skills.reporting.report_builder.pkg.build import build as report_build",
    "from app.skills.analysis_plan.pkg.plan import plan as analysis_plan",
    "from app.skills.reporting.dashboard_builder.pkg.build import build as dashboard_build",
]


# Module-level preamble cache: maps id(registry) → rendered import string.
# The skill tree is fixed at startup, so generating imports on every sandbox
# execution is unnecessary work.
_PREAMBLE_CACHE: dict[int, str] = {}


def _get_cached_preamble(registry=None) -> str:
    """Return the static import block for a given registry, building it once.

    The preamble contains the base Python imports plus all skill imports. Only
    the per-session lines (_SESSION_ID, _ARTIFACT_DIR, df, conn, save_artifact)
    change between calls, so those are kept outside this cache.

    When *registry* is None (tests / legacy paths) falls back to the static
    ``_SKILL_IMPORTS`` list, also cached under key ``id(None)`` = 0.
    """
    cache_key = id(registry)
    if cache_key not in _PREAMBLE_CACHE:
        if registry is not None:
            skill_lines = registry.generate_bootstrap_imports()
        else:
            skill_lines = [line for line in _SKILL_IMPORTS if line.startswith("from app.skills")]
        base_lines = [line for line in _SKILL_IMPORTS if not line.startswith("from app.skills")]
        _PREAMBLE_CACHE[cache_key] = "\n".join(base_lines + skill_lines)
    return _PREAMBLE_CACHE[cache_key]


# Absolute path — computed at import time so sandbox subprocesses find the DB
# regardless of their working directory.
_MAIN_DB_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "data" / "duckdb" / "eval.db"
)


def build_duckdb_globals(
    session_id: str,
    dataset_path: str | Path | None = None,
    db_path: str = _MAIN_DB_PATH,
    registry=None,  # SkillRegistry | None — injected by chat_api
) -> str:
    """Build a Python preamble for the sandbox that wires up DuckDB access.

    Connects read-only to the shared ``data/duckdb/analytical.db`` so the
    agent can query all loaded tables (bank_macro_panel, bank_wide, etc.)
    from the start — no file upload required.

    When *dataset_path* is provided (user uploaded a file), also reads it
    into ``df`` for direct pandas access.

    Exposes:
    * ``conn``   – read-only DuckDB connection to the shared database
    * ``df``     – pandas DataFrame from uploaded file, or ``None``
    * ``save_artifact(name, data)`` – writes JSON artifact to disk
    """
    artifact_dir = f"data/artifacts/{session_id}"

    parts: list[str] = [_get_cached_preamble(registry)] + [
        "",
        f"_SESSION_ID = {session_id!r}",
        f"_DB_PATH = {db_path!r}",
        f"_ARTIFACT_DIR = {artifact_dir!r}",
        # Per-call sentinel token — overridden at each sandbox.run() call by
        # prepending `_ARTIFACT_SENTINEL_TOKEN = "<uuid>"` to the user code.
        "_ARTIFACT_SENTINEL_TOKEN = ''",
        "",
        "import pathlib as _pathlib",
        # Connect read-only — safe for concurrent sandbox processes
        "conn = duckdb.connect(_DB_PATH, read_only=True)",
        "",
    ]

    if dataset_path:
        path = str(Path(dataset_path))
        suffix = Path(dataset_path).suffix.lower()
        read_expr = f"pd.read_csv({path!r})" if suffix == ".csv" else f"pd.read_parquet({path!r})"
        parts.append(f"df = {read_expr}")
    else:
        parts.append("df = None")

    parts += [
        "",
        # save_artifact: Python sandbox function that serializes data and emits a
        # capture marker. The marker is stripped by _execute_python in chat_api.py
        # and forwarded to the frontend artifact panel — same pipeline as Altair charts.
        # The function returns a confirmation string the model can read.
        "def save_artifact(data: object, title: str = 'Artifact', *, summary: str = '') -> str:",
        "    import json as _json_sa, sys as _sys_sa, pandas as _pd_sa",
        "    _type = 'analysis'; _fmt = 'text'; _content = ''",
        "    if isinstance(data, _pd_sa.DataFrame):",
        "        _d = _json_sa.loads(data.to_json(orient='split', default_handler=str))",
        "        _content = _json_sa.dumps({'columns': _d['columns'], 'rows': _d['data'], 'total_rows': len(data)})",
        "        _type = 'table'; _fmt = 'table-json'",
        "        _preview = f'{len(data)} rows x {len(data.columns)} cols'",
        "    elif hasattr(data, 'to_dict'):",
        "        try:",
        "            _spec = data.to_dict()",
        "            if isinstance(_spec, dict) and 'vega-lite' in str(_spec.get('$schema', '')):",
        "                _content = _json_sa.dumps(_spec); _type = 'chart'; _fmt = 'vega-lite'; _preview = 'chart'",
        "            else:",
        "                _content = str(data); _preview = _content[:80]",
        "        except Exception:",
        "            _content = str(data); _preview = _content[:80]",
        "    elif isinstance(data, (dict, list)):",
        "        try:",
        "            _content = _json_sa.dumps(data); _preview = _content[:80]",
        "        except Exception:",
        "            _content = str(data); _preview = _content[:80]",
        "    else:",
        "        _content = str(data); _preview = str(data)[:80]",
        "    _payload = _json_sa.dumps({'title': title, 'type': _type, 'format': _fmt, 'content': _content})",
        "    _tok_sa = _ARTIFACT_SENTINEL_TOKEN",
        "    _sys_sa.stdout.write('\\n__SAVED_ARTIFACT_' + _tok_sa + '__' + _payload + '__END_SAVED_ARTIFACT_' + _tok_sa + '__\\n')",
        "    _sys_sa.stdout.flush()",
        "    return f\"Saved artifact '{title}' ({_type}/{_fmt}): {_preview}\"",
        "",
    ]

    return "\n".join(parts) + "\n"
