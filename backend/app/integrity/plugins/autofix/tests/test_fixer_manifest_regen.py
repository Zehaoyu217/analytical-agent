"""Tests for manifest_regen fixer."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.integrity.plugins.autofix.fixers.manifest_regen import propose
from app.integrity.plugins.autofix.loader import SiblingArtifacts


def _artifacts(*, has_drift: bool = True) -> SiblingArtifacts:
    issues = []
    if has_drift:
        issues = [
            {"rule": "config.added", "evidence": {"path": "scripts/new.sh"},
             "message": "added", "severity": "INFO",
             "node_id": "scripts/new.sh", "location": "scripts/new.sh",
             "fix_class": None, "first_seen": ""},
        ]
    return SiblingArtifacts(
        doc_audit={}, graph_lint={},
        config_registry={"plugin": "config_registry", "issues": issues},
        aggregate={}, failures={},
    )


def test_no_drift_returns_empty(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("inputs: []\n")

    artifacts = _artifacts(has_drift=False)
    diffs = propose(artifacts, tmp_path, {})
    assert diffs == []


def test_drift_with_changed_manifest_emits_diff(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("inputs: []\n")

    artifacts = _artifacts(has_drift=True)

    with patch(
        "backend.app.integrity.plugins.autofix.fixers.manifest_regen._regenerate_manifest_text",
        return_value="inputs:\n  - scripts/new.sh\n",
    ):
        diffs = propose(artifacts, tmp_path, {})

    assert len(diffs) == 1
    assert diffs[0].path == Path("config/manifest.yaml")
    assert "scripts/new.sh" in diffs[0].new_content
    assert diffs[0].original_content == "inputs: []\n"


def test_drift_with_byte_identical_regen_skips(tmp_path: Path) -> None:
    manifest = tmp_path / "config" / "manifest.yaml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("inputs: []\n")

    artifacts = _artifacts(has_drift=True)

    with patch(
        "backend.app.integrity.plugins.autofix.fixers.manifest_regen._regenerate_manifest_text",
        return_value="inputs: []\n",
    ):
        diffs = propose(artifacts, tmp_path, {})
    assert diffs == []
