"""Unit tests for SemanticCompactor (H4.T1)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.harness.clients.base import CompletionResponse, Message
from app.harness.semantic_compactor import SemanticCompactor, _estimate_tokens, _identify_turn_boundaries


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(text: str) -> Message:
    return Message(role="user", content=text)


def _assistant(text: str) -> Message:
    return Message(role="assistant", content=text)


def _mock_client(summary_text: str = "Summary of middle turns.") -> MagicMock:
    client = MagicMock()
    client.complete.return_value = CompletionResponse(
        text=summary_text,
        tool_calls=(),
        stop_reason="end_turn",
    )
    return client


# ── should_compact ─────────────────────────────────────────────────────────────

def test_should_compact_below_threshold_returns_false():
    sc = SemanticCompactor()
    # 60 % of limit → below 80 %
    assert sc.should_compact([], token_count=60_000, model_limit=100_000) is False


def test_should_compact_at_threshold_returns_true():
    sc = SemanticCompactor()
    # exactly 80 % → over threshold (> 80 %)
    assert sc.should_compact([], token_count=80_001, model_limit=100_000) is True


def test_should_compact_above_threshold_returns_true():
    sc = SemanticCompactor()
    assert sc.should_compact([], token_count=95_000, model_limit=100_000) is True


# ── compact — short conversation (no middle window) ───────────────────────────

def test_compact_short_conversation_returns_unchanged():
    sc = SemanticCompactor(head_turns=2, tail_turns=3)
    # Only 4 turns → head=2 + tail=3 > total → no middle
    msgs = [
        _user("q1"), _assistant("a1"),
        _user("q2"), _assistant("a2"),
        _user("q3"), _assistant("a3"),
        _user("q4"), _assistant("a4"),
    ]
    client = _mock_client()
    result = sc.compact(msgs, client)

    assert result.turns_summarized == 0
    assert result.messages is msgs  # exact identity — nothing was copied
    client.complete.assert_not_called()


# ── compact — enough turns to compress ───────────────────────────────────────

def test_compact_replaces_middle_with_summary_message():
    sc = SemanticCompactor(head_turns=1, tail_turns=1)
    msgs = [
        _user("head-q"),  _assistant("head-a"),
        _user("mid-q1"),  _assistant("mid-a1"),
        _user("mid-q2"),  _assistant("mid-a2"),
        _user("tail-q"),  _assistant("tail-a"),
    ]
    summary_text = "The agent investigated mid-q1 and mid-q2."
    client = _mock_client(summary_text)

    result = sc.compact(msgs, client)

    assert result.turns_summarized > 0
    assert result.tokens_before > 0
    # Middle replaced with single summary message
    roles = [m.role for m in result.messages]
    assert "user" in roles
    # Summary message is present in the compacted messages
    summary_msgs = [m for m in result.messages if "Prior conversation summary" in (m.content or "")]
    assert len(summary_msgs) == 1
    assert summary_text in summary_msgs[0].content  # type: ignore[operator]


def test_compact_preserves_head_and_tail():
    sc = SemanticCompactor(head_turns=1, tail_turns=1)
    msgs = [
        _user("first-user"),  _assistant("first-asst"),
        _user("mid1"),        _assistant("mid1-a"),
        _user("mid2"),        _assistant("mid2-a"),
        _user("last-user"),   _assistant("last-asst"),
    ]
    client = _mock_client("summary")
    result = sc.compact(msgs, client)

    content_values = [m.content for m in result.messages]
    assert "first-user" in content_values
    assert "last-user" in content_values


def test_compact_client_failure_returns_original():
    sc = SemanticCompactor(head_turns=1, tail_turns=1)
    msgs = [
        _user("q1"), _assistant("a1"),
        _user("q2"), _assistant("a2"),
        _user("q3"), _assistant("a3"),
        _user("q4"), _assistant("a4"),
    ]
    bad_client = MagicMock()
    bad_client.complete.side_effect = RuntimeError("network error")

    result = sc.compact(msgs, bad_client)

    assert result.turns_summarized == 0
    assert result.messages is msgs


# ── _estimate_tokens helper ───────────────────────────────────────────────────

def test_estimate_tokens_approximates_correctly():
    msgs = [_user("a" * 400), _assistant("b" * 400)]
    tokens = _estimate_tokens(msgs)
    assert tokens == 200  # (400 + 400) // 4


# ── _identify_turn_boundaries helper ─────────────────────────────────────────

def test_identify_turn_boundaries_groups_correctly():
    msgs = [
        _user("u1"), _assistant("a1"),
        _user("u2"), _assistant("a2"),
    ]
    boundaries = _identify_turn_boundaries(msgs)
    assert len(boundaries) == 2
    assert boundaries[0] == [0, 1]
    assert boundaries[1] == [2, 3]
