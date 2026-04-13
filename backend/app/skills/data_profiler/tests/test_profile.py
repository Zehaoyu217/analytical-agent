from __future__ import annotations

import pandas as pd
import pytest

pytest_plugins = ["app.skills.data_profiler.tests.fixtures.conftest"]


def test_profile_returns_report_with_risks_sorted(duplicated_key_df: pd.DataFrame) -> None:
    from app.skills.data_profiler.pkg.profile import profile

    report = profile(duplicated_key_df, name="cust", key_candidates=["customer_id"])
    assert report.n_rows == 4
    assert report.risks[0].severity == "BLOCKER"
    assert "customer_id" in report.summary


def test_profile_saves_json_and_html_artifacts_when_store_given(
    small_df: pd.DataFrame, tmp_path
) -> None:
    from app.artifacts.store import ArtifactStore
    from app.skills.data_profiler.pkg.profile import profile

    store = ArtifactStore(db_path=tmp_path / "a.db", disk_root=tmp_path / "blobs")
    report = profile(small_df, name="customers_v1", store=store, session_id="s1")
    assert report.artifact_id is not None
    assert report.report_artifact_id is not None

    saved_json = store.get_artifact("s1", report.artifact_id)
    assert saved_json is not None and saved_json.format == "profile-json"

    saved_html = store.get_artifact("s1", report.report_artifact_id)
    assert saved_html is not None and saved_html.format == "profile-html"
    assert "<html" in saved_html.content.lower()


def test_profile_empty_dataframe_raises(tmp_path) -> None:
    from app.skills.base import SkillError
    from app.skills.data_profiler.pkg.profile import profile

    with pytest.raises(SkillError):
        profile(pd.DataFrame(), name="empty")
