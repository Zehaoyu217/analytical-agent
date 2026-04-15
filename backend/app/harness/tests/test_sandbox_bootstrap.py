# backend/app/harness/tests/test_sandbox_bootstrap.py
from __future__ import annotations

from app.harness.sandbox_bootstrap import build_sandbox_bootstrap


def test_bootstrap_imports_skills_and_injects_theme() -> None:
    script = build_sandbox_bootstrap(session_id="s1", dataset_path=None)
    for token in [
        "import numpy as np",
        "import pandas as pd",
        "import altair as alt",
        "from app.skills.statistical_analysis.correlation import correlate",
        "from app.skills.statistical_analysis.group_compare import compare",
        "from app.skills.statistical_analysis.stat_validate import validate",
        "from app.skills.data_profiler import profile",
        "from app.skills.charting.altair_charts",
        "ensure_registered",
    ]:
        assert token in script


def test_bootstrap_wires_dataset_when_path_provided(tmp_path) -> None:
    (tmp_path / "data.parquet").write_bytes(b"fake")
    script = build_sandbox_bootstrap(session_id="s1",
                                     dataset_path=tmp_path / "data.parquet")
    assert "df = pd.read_parquet" in script
    assert str(tmp_path / "data.parquet") in script
