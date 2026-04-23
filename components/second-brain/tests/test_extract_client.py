from __future__ import annotations

import json

import httpx

from second_brain.extract.client import AutoExtractorClient, ExtractRequest, FakeExtractorClient


def test_fake_client_returns_canned_response() -> None:
    client = FakeExtractorClient(canned=[
        {"statement": "X", "kind": "empirical", "confidence": "high",
         "scope": "", "supports": [], "contradicts": [], "refines": [], "abstract": "x"}
    ])
    resp = client.extract(ExtractRequest(
        body="doesn't matter", density="moderate", rubric="", source_id="src_x"
    ))
    assert len(resp.claims) == 1
    assert resp.claims[0]["statement"] == "X"


def test_auto_client_falls_back_to_small_model_when_large_model_is_unavailable(
    monkeypatch,
) -> None:
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
                                "name": "record_claims",
                                "arguments": {
                                    "claims": [
                                        {
                                            "statement": "Fallback works.",
                                            "kind": "empirical",
                                            "confidence": "high",
                                            "scope": "",
                                            "supports": [],
                                            "contradicts": [],
                                            "refines": [],
                                            "abstract": "fallback",
                                        }
                                    ]
                                },
                            }
                        }
                    ]
                },
            },
        )

    client = AutoExtractorClient(
        small_model="ollama/gemma4:e4b",
        large_model="openai/gpt-oss-120b:free",
        large_input_chars=10,
        transport=httpx.MockTransport(handler),
    )
    resp = client.extract(ExtractRequest(
        body="This body is long enough to prefer the large model first.",
        density="moderate",
        rubric="",
        source_id="src_x",
    ))
    assert resp.claims[0]["statement"] == "Fallback works."
