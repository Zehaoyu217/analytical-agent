from __future__ import annotations

from second_brain.llm.mlx_client import MLXError, extract_tool_payload


def test_extract_tool_payload_strips_thinking_and_fences() -> None:
    payload = extract_tool_payload(
        "<think>drafting</think>\n```json\n{\"claims\": [{\"statement\": \"A\"}]}\n```",
        "record_claims",
    )
    assert payload == {"claims": [{"statement": "A"}]}


def test_extract_tool_payload_strips_unclosed_think_block() -> None:
    payload = extract_tool_payload(
        '<think>drafting\n{"claims":[{"statement":"C"}]}',
        "record_claims",
    )
    assert payload == {"claims": [{"statement": "C"}]}


def test_extract_tool_payload_accepts_arguments_wrapper() -> None:
    payload = extract_tool_payload(
        '{"name":"record_claims","arguments":{"claims":[{"statement":"B"}]}}',
        "record_claims",
    )
    assert payload == {"claims": [{"statement": "B"}]}


def test_extract_tool_payload_rejects_non_json_text() -> None:
    try:
        extract_tool_payload("plain text only", "record_claims")
    except MLXError as exc:
        assert "record_claims" in str(exc)
    else:  # pragma: no cover - assertion fallback
        raise AssertionError("expected MLXError")
