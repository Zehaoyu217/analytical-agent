from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner

from second_brain.cli import cli
from second_brain.config import Config
from second_brain.habits import Habits
from second_brain.habits.loader import save_habits
from second_brain.habits.schema import DigestHabits


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    (home / "digests").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    cfg = Config.load()
    # Habits with digest enabled, all passes on
    habits = Habits(digest=DigestHabits(enabled=True))
    save_habits(cfg, habits)
    return cfg


def test_digest_build_empty_prints_no_emit_message(cli_env: Config, monkeypatch) -> None:
    # No claims → all passes produce nothing → no digest.
    monkeypatch.delenv("SB_WIKI_DIR", raising=False)
    # Force reconciliation fake to silence DigestPassError — but with 0 claims
    # the pass exits early and never consults the env var.
    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "build", "--date", "2026-04-18"])
    assert result.exit_code == 0, result.output
    assert "Digest 2026-04-18" in result.output or "no entries" in result.output.lower()


def test_digest_build_writes_files_when_entries_present(cli_env: Config, monkeypatch, write_claim) -> None:
    # Seed a retracted claim cited by an active one → edge_audit pass emits one entry.
    write_claim(cli_env, "clm_target", status="retracted")
    write_claim(cli_env, "clm_src", contradicts=["clm_target"])
    monkeypatch.delenv("SB_WIKI_DIR", raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "build", "--date", "2026-04-18"])
    assert result.exit_code == 0, result.output

    md = cli_env.digests_dir / "2026-04-18.md"
    sidecar = cli_env.digests_dir / "2026-04-18.actions.jsonl"
    assert md.exists()
    assert sidecar.exists()
    lines = sidecar.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1


def test_digest_apply_all(cli_env: Config, write_claim) -> None:
    write_claim(cli_env, "clm_a", confidence="low")
    sidecar = cli_env.digests_dir / "2026-04-18.actions.jsonl"
    sidecar.write_text(
        json.dumps(
            {
                "id": "r01",
                "section": "Reconciliation",
                "action": {
                    "action": "upgrade_confidence",
                    "claim_id": "clm_a",
                    "from": "low",
                    "to": "medium",
                    "rationale": "",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "apply", "--all", "--date", "2026-04-18"])
    assert result.exit_code == 0, result.output
    assert "confidence: medium" in (cli_env.claims_dir / "clm_a.md").read_text()


def test_digest_apply_specific_ids(cli_env: Config, write_claim) -> None:
    write_claim(cli_env, "clm_a", confidence="low")
    write_claim(cli_env, "clm_b", confidence="low")
    sidecar = cli_env.digests_dir / "2026-04-18.actions.jsonl"
    sidecar.write_text(
        "\n".join(
            json.dumps(
                {
                    "id": id_,
                    "section": "Reconciliation",
                    "action": {
                        "action": "upgrade_confidence",
                        "claim_id": cid,
                        "from": "low",
                        "to": "medium",
                        "rationale": "",
                    },
                }
            )
            for id_, cid in [("r01", "clm_a"), ("r02", "clm_b")]
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "apply", "r01", "--date", "2026-04-18"])
    assert result.exit_code == 0, result.output
    assert "confidence: medium" in (cli_env.claims_dir / "clm_a.md").read_text()
    assert "confidence: low" in (cli_env.claims_dir / "clm_b.md").read_text()


def test_digest_skip(cli_env: Config) -> None:
    sidecar = cli_env.digests_dir / "2026-04-18.actions.jsonl"
    sidecar.write_text(
        json.dumps(
            {
                "id": "r01",
                "section": "Reconciliation",
                "action": {"action": "keep", "claim_id": "clm_a"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "skip", "r01", "--date", "2026-04-18"])
    assert result.exit_code == 0, result.output
    skip_file = cli_env.sb_dir / "digest_skips.json"
    assert skip_file.exists()
    data = json.loads(skip_file.read_text(encoding="utf-8"))
    assert len(data) == 1


def test_digest_read_mark(cli_env: Config) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "read", "--mark", "2026-04-18"])
    assert result.exit_code == 0, result.output
    marks = cli_env.digests_dir / ".read_marks"
    assert marks.exists()
    assert "2026-04-18" in marks.read_text(encoding="utf-8")


def test_digest_ls(cli_env: Config) -> None:
    (cli_env.digests_dir / "2026-04-18.md").write_text("# Digest 2026-04-18\n", encoding="utf-8")
    (cli_env.digests_dir / "2026-04-18.actions.jsonl").write_text(
        json.dumps({"id": "r01", "section": "Reconciliation", "action": {"action": "keep", "claim_id": "clm_a"}}) + "\n",
        encoding="utf-8",
    )
    (cli_env.digests_dir / "2026-04-17.md").write_text("# Digest 2026-04-17\n", encoding="utf-8")
    (cli_env.digests_dir / "2026-04-17.actions.jsonl").write_text("", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, ["digest", "ls"])
    assert result.exit_code == 0, result.output
    assert "2026-04-18" in result.output
    assert "2026-04-17" in result.output


