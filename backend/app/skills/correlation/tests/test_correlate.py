from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.artifacts.store import ArtifactStore
from app.skills.correlation import correlate


def _store(tmp_path) -> ArtifactStore:
    return ArtifactStore(
        db_path=tmp_path / "artifacts.db",
        disk_root=tmp_path / "disk",
    )


def test_correlate_linear_returns_high_coefficient(tmp_path, linear_07) -> None:
    x, y = linear_07
    df = pd.DataFrame({"x": x, "y": y})
    r = correlate(df, x="x", y="y", method="auto",
                  store=_store(tmp_path), session_id="s1")
    assert 0.6 <= r.coefficient <= 0.8
    assert r.method_used == "pearson"
    assert r.nonlinear_warning is False
    assert r.ci_low <= r.coefficient <= r.ci_high
    assert r.artifact_id is not None
    assert r.n_effective == len(df)


def test_correlate_nonlinear_flips_to_spearman(tmp_path, monotonic_df) -> None:
    r = correlate(monotonic_df, x="x", y="y", method="auto",
                  store=_store(tmp_path), session_id="s1")
    assert r.method_used == "spearman"
    assert r.nonlinear_warning is True


def test_correlate_handles_nans_and_reports(tmp_path) -> None:
    df = pd.DataFrame({"x": [1.0, 2, np.nan, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                       "y": [2.0, 4, 6, np.nan, 10, 12, 14, 16, 18, 20, 22, 24]})
    r = correlate(df, x="x", y="y", method="pearson",
                  store=_store(tmp_path), session_id="s1", bootstrap_n=100)
    assert r.na_dropped == 2
    assert r.n_effective == 10


def test_correlate_partial_on_removes_confounder(tmp_path, confounded_df) -> None:
    r_raw = correlate(confounded_df, x="x", y="y", method="pearson",
                      store=_store(tmp_path), session_id="s1", bootstrap_n=100)
    r_part = correlate(confounded_df, x="x", y="y", method="pearson",
                       partial_on=["confounder"],
                       store=_store(tmp_path), session_id="s1", bootstrap_n=100)
    assert abs(r_part.coefficient) < abs(r_raw.coefficient) - 0.4
    assert r_part.partial_on == ("confounder",)


def test_correlate_unknown_column_raises(tmp_path) -> None:
    df = pd.DataFrame({"a": [1.0, 2], "b": [3.0, 4]})
    with pytest.raises(KeyError, match="column 'missing'"):
        correlate(df, x="missing", y="a", method="pearson",
                  store=_store(tmp_path), session_id="s1")


def test_correlate_insufficient_rows_raises(tmp_path) -> None:
    df = pd.DataFrame({"x": [1.0, 2, 3, 4], "y": [2.0, 4, 6, 8]})
    with pytest.raises(ValueError, match="n_effective"):
        correlate(df, x="x", y="y", method="pearson",
                  store=_store(tmp_path), session_id="s1", bootstrap_n=10)
