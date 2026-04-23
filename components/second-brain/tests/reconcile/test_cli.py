import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _init_sb_home(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    return home


def _seed_pair(home: Path) -> None:
    old = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for slug, other in [("clm_a", "clm_b"), ("clm_b", "clm_a")]:
        (home / "claims" / f"{slug}.md").write_text(
            "\n".join([
                "---", f"id: {slug}", f"statement: '{slug}'",
                "kind: empirical", "confidence: high", "scope: ''",
                f"contradicts: [{other}]", "supports: []", "refines: []",
                f"extracted_at: {old}", "status: active", "resolution: null",
                "abstract: ''", "---", "",
            ]),
            encoding="utf-8",
        )


def test_sb_reconcile_fake_writes_resolution(tmp_path, monkeypatch):
    home = _init_sb_home(tmp_path, monkeypatch)
    _seed_pair(home)
    monkeypatch.setenv("SB_FAKE_RESOLUTION", json.dumps({
        "resolution_md": "scope diff",
        "applies_where": "scope",
        "primary_claim_id": "clm_a",
    }))
    res = CliRunner().invoke(cli, ["reconcile", "--fake", "--limit", "10"])
    assert res.exit_code == 0, res.output
    assert (home / "claims" / "resolutions").exists()
    assert any((home / "claims" / "resolutions").iterdir())


def test_sb_reconcile_dry_run_reports_without_writing(tmp_path, monkeypatch):
    home = _init_sb_home(tmp_path, monkeypatch)
    _seed_pair(home)
    monkeypatch.setenv("SB_FAKE_RESOLUTION", json.dumps({
        "resolution_md": "x", "applies_where": "scope", "primary_claim_id": "clm_a",
    }))
    res = CliRunner().invoke(
        cli, ["reconcile", "--fake", "--dry-run", "--limit", "10"]
    )
    assert res.exit_code == 0, res.output
    assert "proposed=1" in res.output
    assert not (home / "claims" / "resolutions").exists()
