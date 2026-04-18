"""Tests for second-brain digest tool handlers."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import config as app_config


@pytest.fixture
def sb_home(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / "digests").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    (home / ".sb").mkdir()
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    return home


def _write_digest(home: Path, today: date, entries: list[dict]) -> None:
    digest_dir = home / "digests"
    md = f"# Digest {today.isoformat()}\n\n"
    for e in entries:
        md += f"## {e['section']}\n- [{e['id']}] {e['line']}\n"
    (digest_dir / f"{today.isoformat()}.md").write_text(md)
    sidecar = digest_dir / f"{today.isoformat()}.actions.jsonl"
    with sidecar.open("w") as f:
        for e in entries:
            f.write(
                json.dumps({"id": e["id"], "section": e["section"], "action": e["action"]})
                + "\n"
            )


# ─────────────────────── sb_digest_today ──────────────────────────


def test_sb_digest_today_happy_path(sb_home):
    from app.tools.sb_digest_tools import sb_digest_today

    today = date.today()
    _write_digest(
        sb_home,
        today,
        [
            {
                "id": "r01",
                "section": "Reconciliation",
                "line": "upgrade clm_foo",
                "action": {
                    "action": "upgrade_confidence",
                    "claim_id": "clm_foo",
                    "from": "low",
                    "to": "medium",
                    "rationale": "x",
                },
            },
        ],
    )
    result = sb_digest_today({})
    assert result["ok"] is True
    assert result["date"] == today.isoformat()
    assert result["entry_count"] == 1
    assert result["unread"] == 1
    assert result["entries"][0]["id"] == "r01"


def test_sb_digest_today_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    from app.tools.sb_digest_tools import sb_digest_today

    result = sb_digest_today({})
    assert result == {"ok": False, "error": "second_brain_disabled"}


def test_sb_digest_today_missing(sb_home):
    from app.tools.sb_digest_tools import sb_digest_today

    result = sb_digest_today({})
    assert result["ok"] is True
    assert result["entry_count"] == 0
    assert result["entries"] == []


# ─────────────────────── sb_digest_list / show ─────────────────────


def test_sb_digest_list(sb_home):
    from app.tools.sb_digest_tools import sb_digest_list

    today = date.today()
    yday = today - timedelta(days=1)
    _write_digest(
        sb_home,
        today,
        [{"id": "r01", "section": "Reconciliation", "line": "a", "action": {"action": "keep"}}],
    )
    _write_digest(
        sb_home,
        yday,
        [{"id": "r01", "section": "Taxonomy", "line": "b", "action": {"action": "keep"}}],
    )
    result = sb_digest_list({"limit": 5})
    assert result["ok"] is True
    dates = [d["date"] for d in result["digests"]]
    assert dates == [today.isoformat(), yday.isoformat()]
    assert result["digests"][0]["entry_count"] == 1


def test_sb_digest_show(sb_home):
    from app.tools.sb_digest_tools import sb_digest_show

    today = date.today()
    _write_digest(
        sb_home,
        today,
        [{"id": "r01", "section": "Reconciliation", "line": "x", "action": {"action": "keep"}}],
    )
    result = sb_digest_show({"date": today.isoformat()})
    assert result["ok"] is True
    assert result["date"] == today.isoformat()
    assert "Digest" in result["markdown"]
    assert result["entries"][0]["id"] == "r01"


def test_sb_digest_show_missing(sb_home):
    from app.tools.sb_digest_tools import sb_digest_show

    result = sb_digest_show({"date": "2099-01-01"})
    assert result == {"ok": False, "error": "digest_not_found", "date": "2099-01-01"}


# ─────────────────────── sb_digest_apply ──────────────────────────


def test_sb_digest_apply_delegates_to_applier(sb_home, monkeypatch):
    from app.tools import sb_digest_tools

    today = date.today()
    called: dict[str, object] = {}

    class FakeResult:
        applied = ["r01"]
        skipped: list[str] = []
        failed: list[str] = []

    class FakeApplier:
        def __init__(self, cfg):
            called["cfg"] = cfg

        def apply(self, *, digest_date, entry_ids):
            called["date"] = digest_date
            called["ids"] = entry_ids
            return FakeResult()

    monkeypatch.setattr(sb_digest_tools, "_DigestApplier", FakeApplier, raising=False)
    result = sb_digest_tools.sb_digest_apply({"ids": ["r01"]})
    assert result == {"ok": True, "applied": ["r01"], "skipped": [], "failed": []}
    assert called["ids"] == ["r01"]
    assert called["date"] == today


def test_sb_digest_apply_invalid_args(sb_home):
    from app.tools.sb_digest_tools import sb_digest_apply

    assert sb_digest_apply({"ids": []})["ok"] is False


# ─────────────────────── sb_digest_skip ───────────────────────────


def test_sb_digest_skip_uses_registry(sb_home, monkeypatch):
    from app.tools import sb_digest_tools

    captured: dict[str, object] = {}

    class FakeRegistry:
        def __init__(self, cfg):
            captured["cfg"] = cfg
            # Simulate the real registry surface: a signatures dict at self.path.
            self.path = sb_home / ".sb" / "digest_skips.json"
            self.path.write_text("{}")

        def skip_by_id(self, *, digest_date, entry_id, ttl_days):
            captured["date"] = digest_date
            captured["id"] = entry_id
            captured["ttl"] = ttl_days
            # Emulate side effect: write a signature into the file.
            self.path.write_text(
                json.dumps({"sig_abc": "2099-01-01"})
            )
            return True

    monkeypatch.setattr(sb_digest_tools, "_SkipRegistry", FakeRegistry, raising=False)
    result = sb_digest_tools.sb_digest_skip({"id": "r01", "ttl_days": 30})
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["signature"] == "sig_abc"
    assert result["expires_at"] == "2099-01-01"
    assert captured["ttl"] == 30
    assert captured["id"] == "r01"


def test_sb_digest_skip_missing_id(sb_home):
    from app.tools.sb_digest_tools import sb_digest_skip

    assert sb_digest_skip({})["ok"] is False


def test_sb_digest_skip_entry_not_found(sb_home, monkeypatch):
    from app.tools import sb_digest_tools

    class FakeRegistry:
        def __init__(self, cfg):
            self.path = sb_home / ".sb" / "digest_skips.json"

        def skip_by_id(self, *, digest_date, entry_id, ttl_days):
            return False

    monkeypatch.setattr(sb_digest_tools, "_SkipRegistry", FakeRegistry, raising=False)
    result = sb_digest_tools.sb_digest_skip({"id": "nope"})
    assert result["ok"] is False
    assert result["error"] == "entry_not_found"


# ─────────────────────── sb_digest_propose ────────────────────────


def test_sb_digest_propose_appends_pending(sb_home):
    from app.tools.sb_digest_tools import sb_digest_propose

    action = {
        "action": "upgrade_confidence",
        "claim_id": "clm_x",
        "from": "low",
        "to": "medium",
        "rationale": "r",
    }
    r1 = sb_digest_propose({"section": "Reconciliation", "action": action})
    assert r1["ok"] is True
    assert r1["pending_id"].startswith("pend_")
    pending = sb_home / "digests" / "pending.jsonl"
    assert pending.exists()
    lines = pending.read_text().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["section"] == "Reconciliation"
    assert payload["action"]["claim_id"] == "clm_x"


def test_sb_digest_propose_rejects_unknown_action(sb_home):
    from app.tools.sb_digest_tools import sb_digest_propose

    result = sb_digest_propose(
        {"section": "Reconciliation", "action": {"action": "zzz"}}
    )
    assert result == {"ok": False, "error": "invalid_action_type"}


# ─────────────────────── sb_stats ─────────────────────────────────


def test_sb_stats_delegates(sb_home, monkeypatch):
    from app.tools import sb_digest_tools

    def fake_collect(cfg):
        return (
            {"claims": 42, "unread_stale_digests": 0},
            {"score": 87, "breakdown": {}},
        )

    monkeypatch.setattr(sb_digest_tools, "_collect_stats", fake_collect, raising=False)
    result = sb_digest_tools.sb_stats({})
    assert result == {
        "ok": True,
        "stats": {"claims": 42, "unread_stale_digests": 0},
        "health": {"score": 87, "breakdown": {}},
    }


def test_sb_stats_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    from app.tools.sb_digest_tools import sb_stats

    assert sb_stats({}) == {"ok": False, "error": "second_brain_disabled"}
