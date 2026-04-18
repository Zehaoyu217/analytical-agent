"""Tests for /api/sb REST routes."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import config as app_config
from app.api import sb_api


def _client() -> TestClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(sb_api.router)
    return TestClient(app)


# ─────────────────────── gating ─────────────────────────────────────


def test_stats_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().get("/api/sb/stats")
    assert resp.status_code == 404


def test_stats_happy_path(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    from app.tools import sb_digest_tools

    monkeypatch.setattr(
        sb_digest_tools,
        "sb_stats",
        lambda _args: {
            "ok": True,
            "stats": {"claims": 10},
            "health": {"score": 88, "grade": "B"},
        },
        raising=False,
    )
    resp = _client().get("/api/sb/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["stats"] == {"claims": 10}
    assert body["health"]["score"] == 88


# ─────────────────────── pending / build ────────────────────────────


def test_digest_pending_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().get("/api/sb/digest/pending")
    assert resp.status_code == 404


def test_digest_pending_happy_path(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)

    class _Entry:
        def __init__(self, id_, section, line, action):
            self.id = id_
            self.section = section
            self.line = line
            self.action = action

    monkeypatch.setattr(
        sb_api,
        "_read_pending",
        lambda _cfg: [
            _Entry(
                "pend_0001",
                "Reconciliation",
                "upgrade clm_foo",
                {"action": "upgrade_confidence", "claim_id": "clm_foo"},
            )
        ],
        raising=False,
    )
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: object(), raising=False)

    resp = _client().get("/api/sb/digest/pending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert body["proposals"][0]["id"] == "pend_0001"
    assert body["proposals"][0]["section"] == "Reconciliation"
    assert body["proposals"][0]["line"] == "upgrade clm_foo"
    assert body["proposals"][0]["action"]["action"] == "upgrade_confidence"


def test_digest_build_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().post("/api/sb/digest/build")
    assert resp.status_code == 404


def test_digest_build_emits(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)

    class _Result:
        def __init__(self, n):
            self.entries = [object()] * n

    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    monkeypatch.setattr(sb_api, "_load_habits", lambda _cfg: object(), raising=False)
    monkeypatch.setattr(
        sb_api,
        "_run_build",
        lambda _cfg, _habits: _Result(3),
        raising=False,
    )
    resp = _client().post("/api/sb/digest/build")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["emitted"] is True
    assert body["entries"] == 3


# ─────────────────────── memory recall ──────────────────────────────


def test_memory_session_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().get("/api/sb/memory/session/s_123")
    assert resp.status_code == 404


def test_memory_session_prompt_override(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)

    class _Injection:
        block = "KB: claim_foo – foo is bar."
        hit_ids = ["clm_foo"]
        skipped_reason = None

    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: object(), raising=False)
    monkeypatch.setattr(sb_api, "_load_habits", lambda _cfg: object(), raising=False)
    monkeypatch.setattr(
        sb_api,
        "_build_injection",
        lambda _cfg, _habits, prompt: _Injection() if prompt else _Injection(),
        raising=False,
    )
    resp = _client().get("/api/sb/memory/session/s_xyz?prompt=hello+world")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["hits"] == [{"id": "clm_foo"}]
    assert body["block"].startswith("KB:")


def test_memory_session_no_prompt_reports_skipped(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setattr(sb_api, "_last_user_prompt_for", lambda _sid: None, raising=False)
    resp = _client().get("/api/sb/memory/session/missing_session")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["hits"] == []
    assert body["skipped_reason"] == "no_user_prompt"


def test_digest_build_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)

    class _Result:
        entries: list = []

    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    monkeypatch.setattr(sb_api, "_load_habits", lambda _cfg: object(), raising=False)
    monkeypatch.setattr(
        sb_api,
        "_run_build",
        lambda _cfg, _habits: _Result(),
        raising=False,
    )
    resp = _client().post("/api/sb/digest/build")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["emitted"] is False
    assert body["entries"] == 0


# ─────────────────────── digest build meta + costs ──────────────────


def test_digest_build_writes_meta_sidecar(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)

    class _Result:
        def __init__(self, n):
            self.entries = [object()] * n

    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    monkeypatch.setattr(sb_api, "_load_habits", lambda _cfg: object(), raising=False)
    monkeypatch.setattr(
        sb_api, "_run_build", lambda _cfg, _habits: _Result(2), raising=False
    )
    resp = _client().post("/api/sb/digest/build")
    assert resp.status_code == 200

    metas = list(tmp_path.glob("*.meta.json"))
    assert len(metas) == 1
    payload = json.loads(metas[0].read_text())
    assert payload["actor"] == "digest.build"
    assert payload["outcome"] == "ok"
    assert payload["detail"]["entries"] == 2
    assert payload["detail"]["emitted"] is True
    assert payload["input_tokens"] == 0
    assert payload["cost_usd"] == 0.0
    assert isinstance(payload["duration_ms"], int)
    assert payload["duration_ms"] >= 0


def test_digest_build_meta_on_error(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    monkeypatch.setattr(sb_api, "_load_habits", lambda _cfg: object(), raising=False)

    def _boom(_cfg, _habits):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(sb_api, "_run_build", _boom, raising=False)
    resp = _client().post("/api/sb/digest/build")
    assert resp.status_code == 500
    metas = list(tmp_path.glob("*.meta.json"))
    assert len(metas) == 1
    payload = json.loads(metas[0].read_text())
    assert payload["outcome"] == "error"


def test_digest_costs_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().get("/api/sb/digest/costs")
    assert resp.status_code == 404


def test_digest_costs_null_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    resp = _client().get("/api/sb/digest/costs")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"ok": True, "record": None}


def test_digest_costs_returns_record(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    from datetime import date as date_t

    payload = {"actor": "digest.build", "duration_ms": 7, "outcome": "ok"}
    (tmp_path / f"{date_t.today().isoformat()}.meta.json").write_text(
        json.dumps(payload)
    )
    resp = _client().get("/api/sb/digest/costs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["record"] == payload


def test_digest_costs_malformed(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    from datetime import date as date_t

    (tmp_path / f"{date_t.today().isoformat()}.meta.json").write_text("{not json")
    resp = _client().get("/api/sb/digest/costs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["record"] is None
    assert body["error"] == "malformed_meta"


def test_digest_costs_explicit_date(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    cfg = SimpleNamespace(digests_dir=tmp_path)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: cfg, raising=False)
    payload = {"actor": "digest.build", "outcome": "ok"}
    (tmp_path / "2026-04-18.meta.json").write_text(json.dumps(payload))
    resp = _client().get("/api/sb/digest/costs?date=2026-04-18")
    assert resp.status_code == 200
    assert resp.json()["record"] == payload


# ─────────────────────── graph viz ──────────────────────────────────


def test_graph_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().get("/api/sb/graph")
    assert resp.status_code == 404


def test_graph_happy_path_with_center(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: object(), raising=False)

    def _fake_query(cfg, *, center, depth, limit):  # noqa: ANN001
        assert center == "clm_foo"
        assert depth == 1
        assert limit == 60
        return {
            "ok": True,
            "center": center,
            "nodes": [
                {"id": "clm_foo", "kind": "claim", "label": "foo"},
                {"id": "src_bar", "kind": "source", "label": "bar"},
            ],
            "edges": [{"src": "clm_foo", "dst": "src_bar", "kind": "supports"}],
        }

    monkeypatch.setattr(sb_api, "_query_graph", _fake_query, raising=False)

    resp = _client().get("/api/sb/graph?center=clm_foo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["center"] == "clm_foo"
    assert len(body["nodes"]) == 2
    assert body["edges"][0]["kind"] == "supports"


def test_graph_empty_fallback(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: object(), raising=False)
    monkeypatch.setattr(
        sb_api,
        "_query_graph",
        lambda *_a, **_kw: {"ok": True, "nodes": [], "edges": [], "note": "no graph data"},
        raising=False,
    )
    resp = _client().get("/api/sb/graph")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["nodes"] == []
    assert body["note"] == "no graph data"


def test_graph_clamps_depth_and_limit(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setattr(sb_api, "_sb_cfg", lambda: object(), raising=False)

    captured: dict[str, Any] = {}

    def _fake(cfg, *, center, depth, limit):  # noqa: ANN001
        captured["depth"] = depth
        captured["limit"] = limit
        return {"ok": True, "nodes": [], "edges": []}

    monkeypatch.setattr(sb_api, "_query_graph", _fake, raising=False)
    resp = _client().get("/api/sb/graph?depth=99&limit=9999")
    assert resp.status_code == 200
    assert captured["depth"] == 2
    assert captured["limit"] == 200


# ─────────────────────── ingest ─────────────────────────────────────


def test_ingest_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().post("/api/sb/ingest", json={"path": "/tmp/x.md"})
    assert resp.status_code == 404


def test_ingest_happy_path(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    from app.tools import sb_tools

    captured: dict[str, Any] = {}

    def _fake(args):  # noqa: ANN001
        captured.update(args)
        return {"ok": True, "source_id": "src_abc", "folder": "/tmp/src_abc"}

    monkeypatch.setattr(sb_tools, "sb_ingest", _fake, raising=False)
    resp = _client().post("/api/sb/ingest", json={"path": "/tmp/file.md"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source_id"] == "src_abc"
    assert captured == {"path": "/tmp/file.md"}


def test_ingest_missing_path_is_422(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    resp = _client().post("/api/sb/ingest", json={})
    assert resp.status_code == 422


# ─────────────────────── drift ──────────────────────────────────────


def test_drift_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", False, raising=False)
    resp = _client().get("/api/sb/drift")
    assert resp.status_code == 404


def test_drift_returns_null_when_snapshot_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setattr(sb_api, "_drift_dir", lambda: tmp_path, raising=False)
    resp = _client().get("/api/sb/drift?date=2026-04-18")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["report"] is None


def test_drift_returns_parsed_report(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setattr(sb_api, "_drift_dir", lambda: tmp_path, raising=False)
    payload = {
        "timestamp": "2026-04-18T00:00:00Z",
        "total": 1,
        "by_kind": {"orphan_claim": 1},
        "findings": [
            {
                "kind": "orphan_claim",
                "subject_id": "clm_x",
                "detail": {"wiki_path": "missing.md"},
            }
        ],
    }
    (tmp_path / "2026-04-18.json").write_text(json.dumps(payload), encoding="utf-8")
    resp = _client().get("/api/sb/drift?date=2026-04-18")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["report"] == payload


def test_drift_handles_malformed_json(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "SECOND_BRAIN_ENABLED", True, raising=False)
    monkeypatch.setattr(sb_api, "_drift_dir", lambda: tmp_path, raising=False)
    (tmp_path / "2026-04-18.json").write_text("{not json", encoding="utf-8")
    resp = _client().get("/api/sb/drift?date=2026-04-18")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["report"] is None
    assert body["error"] == "malformed_report"


_ = Path  # keep import used
