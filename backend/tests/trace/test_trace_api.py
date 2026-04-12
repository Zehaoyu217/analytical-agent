from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import create_app


def _trace_doc(session_id: str, grade: str | None = "F") -> dict[str, object]:
    return {
        "trace_schema_version": 1,
        "summary": {
            "session_id": session_id, "started_at": "t", "ended_at": "t",
            "duration_ms": 1, "level": 3, "level_label": "eval-level3",
            "turn_count": 1, "llm_call_count": 1,
            "total_input_tokens": 100, "total_output_tokens": 20,
            "outcome": "ok", "final_grade": grade,
            "step_ids": ["s1"], "trace_mode": "on_failure",
            "judge_runs_cached": 2,
        },
        "judge_runs": [
            {"dimensions": {"accuracy": 0.0}},
            {"dimensions": {"accuracy": 1.0}},
        ],
        "events": [
            {
                "kind": "session_start", "seq": 1, "timestamp": "t",
                "session_id": session_id, "started_at": "t",
                "level": 3, "level_label": "eval-level3", "input_query": "q",
            },
            {
                "kind": "llm_call", "seq": 2, "timestamp": "t",
                "step_id": "s1", "turn": 1, "model": "m",
                "temperature": 1.0, "max_tokens": 10, "prompt_text": "p",
                "sections": [{"source": "SYSTEM_PROMPT", "lines": "1-10", "text": "..."}],
                "response_text": "r", "tool_calls": [], "stop_reason": "end_turn",
                "input_tokens": 100, "output_tokens": 20,
                "cache_read_tokens": 0, "cache_creation_tokens": 0, "latency_ms": 0,
            },
            {
                "kind": "session_end", "seq": 3, "timestamp": "t",
                "ended_at": "t", "duration_ms": 1, "outcome": "ok", "error": None,
            },
        ],
    }


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TRACE_DIR", str(tmp_path))
    (tmp_path / "sess-1.yaml").write_text(
        yaml.safe_dump(_trace_doc("sess-1")), encoding="utf-8",
    )
    return TestClient(create_app())


def test_list_traces_returns_summaries(client: TestClient) -> None:
    r = client.get("/api/trace/traces")
    assert r.status_code == 200
    body = r.json()
    assert len(body["traces"]) == 1
    assert body["traces"][0]["session_id"] == "sess-1"


def test_get_trace_by_id(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1")
    assert r.status_code == 200
    assert r.json()["summary"]["session_id"] == "sess-1"


def test_get_trace_invalid_id_returns_400(client: TestClient) -> None:
    r = client.get("/api/trace/traces/..%2Fetc%2Fpasswd")
    assert r.status_code == 400


def test_get_trace_missing_returns_404(client: TestClient) -> None:
    r = client.get("/api/trace/traces/missing")
    assert r.status_code == 404


def test_prompt_assembly(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1/prompt/s1")
    assert r.status_code == 200
    body = r.json()
    assert len(body["sections"]) == 1
    assert body["sections"][0]["source"] == "SYSTEM_PROMPT"
    assert body["conflicts"] == []


def test_prompt_assembly_step_not_found_returns_404(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1/prompt/s99")
    assert r.status_code == 404


def test_prompt_assembly_invalid_step_id_returns_400(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1/prompt/notastep")
    assert r.status_code == 400


def test_timeline(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1/timeline")
    assert r.status_code == 200
    body = r.json()
    assert "turns" in body
    assert "events" in body


def test_judge_variance_cached(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1/judge-variance?refresh=0&n=5")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "cached"
    assert "accuracy" in body["variance"]


def test_judge_variance_live_without_api_key_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.get("/api/trace/traces/sess-1/judge-variance?refresh=1&n=5")
    assert r.status_code == 503


def test_events_filtered_by_kind(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1/events?kind=llm_call")
    assert r.status_code == 200
    body = r.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["kind"] == "llm_call"


def test_events_no_filter_returns_all(client: TestClient) -> None:
    r = client.get("/api/trace/traces/sess-1/events")
    assert r.status_code == 200
    assert len(r.json()["events"]) == 3
