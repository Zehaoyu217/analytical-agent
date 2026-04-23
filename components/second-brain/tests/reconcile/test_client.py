import json

import httpx

from second_brain.reconcile.client import (
    AutoReconcilerClient,
    FakeReconcilerClient,
    ReconcileRequest,
    ReconcileResponse,
)
from second_brain.reconcile.schema import RECORD_RESOLUTION_TOOL, validate_resolution_record


def test_tool_schema_shape():
    assert RECORD_RESOLUTION_TOOL["name"] == "record_resolution"
    props = RECORD_RESOLUTION_TOOL["input_schema"]["properties"]
    assert set(props.keys()) >= {"resolution_md", "applies_where", "primary_claim_id"}


def test_validate_resolution_record_accepts_minimum():
    validate_resolution_record({
        "resolution_md": "Scope differs: paper A covers X; paper B covers Y.",
        "applies_where": "scope",
        "primary_claim_id": "clm_x",
    })


def test_validate_resolution_record_rejects_unknown_applies_where():
    import pytest
    with pytest.raises(ValueError):
        validate_resolution_record({
            "resolution_md": "...",
            "applies_where": "vibes",
            "primary_claim_id": "clm_x",
        })


def test_fake_client_returns_canned_payload():
    client = FakeReconcilerClient(canned={
        "resolution_md": "scope diff",
        "applies_where": "scope",
        "primary_claim_id": "clm_a",
    })
    res = client.reconcile(ReconcileRequest(
        claim_a_id="clm_a", claim_a_body="A",
        claim_b_id="clm_b", claim_b_body="B",
        supports_a="src_x body", supports_b="src_y body",
    ))
    assert isinstance(res, ReconcileResponse)
    assert res.primary_claim_id == "clm_a"
    assert res.applies_where == "scope"
    assert "scope diff" in res.resolution_md


def test_auto_reconciler_falls_back_to_small_model_when_large_model_is_unavailable(
    monkeypatch,
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "gemma4:e4b"}]})
        body = json.loads(request.content.decode())
        assert body["model"] == "gemma4:e4b"
        return httpx.Response(
            200,
            json={
                "model": "gemma4:e4b",
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "record_resolution",
                                "arguments": {
                                    "resolution_md": "scope diff",
                                    "applies_where": "scope",
                                    "primary_claim_id": "clm_a",
                                },
                            }
                        }
                    ]
                },
            },
        )

    client = AutoReconcilerClient(
        small_model="ollama/gemma4:e4b",
        large_model="openai/gpt-oss-120b:free",
        large_input_chars=10,
        transport=httpx.MockTransport(handler),
    )
    res = client.reconcile(ReconcileRequest(
        claim_a_id="clm_a", claim_a_body="A",
        claim_b_id="clm_b", claim_b_body="B",
        supports_a="support A is long enough to trigger large-model preference",
        supports_b="support B is also long enough to trigger large-model preference",
    ))
    assert res.primary_claim_id == "clm_a"
