from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.skills.statistical_analysis.distribution_fit.fit_one import FitCandidate


@dataclass(frozen=True, slots=True)
class FitResult:
    best: FitCandidate
    ranked: tuple[FitCandidate, ...]
    hill_alpha: float | None
    qq_artifact_id: str | None
    pdf_overlay_artifact_id: str | None
    outlier_threshold: float
    outlier_indices: tuple[int, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "best": asdict(self.best),
            "ranked": [asdict(c) for c in self.ranked],
            "hill_alpha": self.hill_alpha,
            "qq_artifact_id": self.qq_artifact_id,
            "pdf_overlay_artifact_id": self.pdf_overlay_artifact_id,
            "outlier_threshold": self.outlier_threshold,
            "outlier_indices": list(self.outlier_indices),
        }
        for c in d["ranked"]:
            c["params"] = list(c["params"])
        d["best"]["params"] = list(d["best"]["params"])
        return d
