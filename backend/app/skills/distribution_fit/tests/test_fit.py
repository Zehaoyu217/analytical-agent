from __future__ import annotations

import numpy as np
import pytest

from app.artifacts.store import ArtifactStore
from app.skills.distribution_fit import fit


def _store(tmp_path) -> ArtifactStore:
    return ArtifactStore(db_path=tmp_path / "art.db", disk_root=tmp_path / "disk")


def test_fit_normal_series_picks_norm_and_emits_artifacts(tmp_path) -> None:
    rng = np.random.default_rng(0)
    s = rng.normal(0, 1, 800)
    result = fit(s, candidates="auto",
                 store=_store(tmp_path), session_id="s1")
    assert result.best.name in {"norm", "t", "laplace"}
    assert result.qq_artifact_id is not None
    assert result.pdf_overlay_artifact_id is not None


def test_fit_heavy_tail_detects_hill_alpha(heavy_1k, tmp_path) -> None:
    result = fit(heavy_1k, candidates="auto",
                 store=_store(tmp_path), session_id="s1")
    assert result.hill_alpha is not None
    assert result.hill_alpha < 3.0


def test_fit_small_n_raises() -> None:
    with pytest.raises(ValueError, match="n="):
        fit(np.arange(20, dtype=float))
