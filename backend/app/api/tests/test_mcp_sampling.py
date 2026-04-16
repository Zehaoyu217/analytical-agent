"""Unit tests for POST /api/mcp/sample (H6.T2)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.mcp_sampling_api import reset_sampling_counts_for_tests, router
from fastapi import FastAPI

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _mock_client(text: str = "Sample response") -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.content = text
    client.complete.return_value = response
    return client


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_counts() -> None:
    reset_sampling_counts_for_tests()
    yield
    reset_sampling_counts_for_tests()


def test_sample_endpoint_returns_text() -> None:
    """Endpoint should return the model's text output."""
    app = _make_app()
    client = TestClient(app)
    mock_model = _mock_client("Analysis complete.")

    with (
        patch("app.api.mcp_sampling_api._get_model_client", return_value=mock_model),
        patch("app.api.mcp_sampling_api._get_session_db", return_value=MagicMock()),
    ):
        resp = client.post(
            "/api/mcp/sample",
            json={"session_id": "sess-001", "prompt": "Summarise the data"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "Analysis complete."
    assert body["session_id"] == "sess-001"
    assert body["sampling_call_index"] == 1


def test_rate_limit_returns_429_after_5_calls() -> None:
    """The 6th request for the same session_id must return HTTP 429."""
    from app.harness.turn_state import SAMPLING_LIMIT_PER_TURN

    app = _make_app()
    client = TestClient(app)
    mock_model = _mock_client()

    with (
        patch("app.api.mcp_sampling_api._get_model_client", return_value=mock_model),
        patch("app.api.mcp_sampling_api._get_session_db", return_value=MagicMock()),
    ):
        for _ in range(SAMPLING_LIMIT_PER_TURN):
            resp = client.post(
                "/api/mcp/sample",
                json={"session_id": "sess-rate", "prompt": "do something"},
            )
            assert resp.status_code == 200

        # 6th call — should hit the limit
        resp = client.post(
            "/api/mcp/sample",
            json={"session_id": "sess-rate", "prompt": "one more"},
        )

    assert resp.status_code == 429
