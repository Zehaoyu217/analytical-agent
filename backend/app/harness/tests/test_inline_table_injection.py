"""v4 P24: post-turn inline-table synthesis (Phase 4 of Gap-Closure).

Verifies that ``AgentLoop`` re-synthesises the final response into a markdown
table when the user explicitly asked to *show / display / list* rows but the
model's first response only cited an artifact.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.clients.base import CompletionResponse, Message
from app.harness.dispatcher import ToolDispatcher
from app.harness.loop import (
    AgentLoop,
    _response_has_table,
    _user_wants_inline_table,
)


# ── Predicate sanity ──────────────────────────────────────────────────────────


def test_user_wants_table_show_table() -> None:
    assert _user_wants_inline_table("show me the table of top spenders") is True


def test_user_wants_table_display_top_n() -> None:
    assert _user_wants_inline_table("Display the top 5 transactions") is True


def test_user_wants_table_list_rows() -> None:
    assert _user_wants_inline_table("list the rows where amount > 1000") is True


def test_user_wants_table_give_me_top() -> None:
    assert _user_wants_inline_table("give me top 10 customers") is True


def test_user_wants_table_negative_summary_only() -> None:
    assert _user_wants_inline_table("summarize the customer data") is False


def test_user_wants_table_negative_no_keywords() -> None:
    assert _user_wants_inline_table("how many transactions exceeded the median?") is False


def test_response_has_table_true() -> None:
    text = "Here it is:\n\n| Name | Amount |\n|---|---|\n| Alice | 100 |\n"
    assert _response_has_table(text) is True


def test_response_has_table_false_no_pipes() -> None:
    assert _response_has_table("There were 5 rows in the artifact.") is False


def test_response_has_table_false_single_pipe() -> None:
    # Not a table — just a single pipe in prose.
    assert _response_has_table("The mean | median split favored…") is False


# ── Loop wiring — run() ───────────────────────────────────────────────────────


def _client(*texts: str) -> MagicMock:
    """Mock client whose successive .complete() calls return *texts* in order."""
    c = MagicMock()
    c.name = "test"
    c.tier = "standard"
    c.complete.side_effect = [
        CompletionResponse(text=t, tool_calls=(), stop_reason="end_turn", usage={})
        for t in texts
    ]
    return c


_TABLE_RESPONSE = (
    "## Top spenders\n\n"
    "Brief summary.\n\n"
    "### Evidence\n\n"
    "| Customer | Total |\n|---|---|\n| Alice | 1234 |\n| Bob | 999 |\n\n"
    "### Caveats\n\n- 30-day window only\n"
)
_NO_TABLE_RESPONSE = (
    "## Top spenders\n\n"
    "Saved to artifact: top_spenders.\n\n"
    "### Evidence\n\n- **top_spenders** — table of 5 rows\n\n"
    "### Caveats\n\n- 30-day window only\n"
)


def test_run_injects_table_when_user_asks_and_response_lacks_one() -> None:
    """End-to-end: 1st reply has no table → fix-up call returns one with a table."""
    client = _client(_NO_TABLE_RESPONSE, _TABLE_RESPONSE)
    loop = AgentLoop(dispatcher=ToolDispatcher())
    outcome = loop.run(
        client=client,
        system="sys", user_message="show me the top 5 spenders as a table",
        dataset_loaded=False, max_steps=2,
    )
    assert _response_has_table(outcome.final_text) is True
    # 1 main call + 1 inline-table fix-up call = 2 client.complete calls
    assert client.complete.call_count == 2


def test_run_skips_injection_when_response_already_has_table() -> None:
    client = _client(_TABLE_RESPONSE)
    loop = AgentLoop(dispatcher=ToolDispatcher())
    loop.run(
        client=client,
        system="sys", user_message="show me the top 5 spenders as a table",
        dataset_loaded=False, max_steps=2,
    )
    # Only the main call ran; no fix-up.
    assert client.complete.call_count == 1


def test_run_skips_injection_when_user_did_not_ask_for_table() -> None:
    client = _client(_NO_TABLE_RESPONSE)
    loop = AgentLoop(dispatcher=ToolDispatcher())
    loop.run(
        client=client,
        system="sys", user_message="give me a brief summary of spending patterns",
        dataset_loaded=False, max_steps=2,
    )
    assert client.complete.call_count == 1


def test_run_keeps_original_when_fix_up_still_lacks_table() -> None:
    """If the rewrite also fails to produce a table, keep the original text."""
    client = _client(_NO_TABLE_RESPONSE, "Sorry, no rewrite happened.")
    loop = AgentLoop(dispatcher=ToolDispatcher())
    outcome = loop.run(
        client=client,
        system="sys", user_message="show me the top 5 rows",
        dataset_loaded=False, max_steps=2,
    )
    # Two completions tried; original text preserved (still no table, but the
    # rewrite produced no table either, so we don't adopt the worse rewrite).
    assert client.complete.call_count == 2
    assert outcome.final_text == _NO_TABLE_RESPONSE


def test_run_keeps_original_on_fix_up_exception() -> None:
    """Network/provider errors during the fix-up must never crash the turn."""
    c = MagicMock()
    c.name = "test"
    c.tier = "standard"
    c.complete.side_effect = [
        CompletionResponse(
            text=_NO_TABLE_RESPONSE, tool_calls=(),
            stop_reason="end_turn", usage={},
        ),
        RuntimeError("provider down"),
    ]
    loop = AgentLoop(dispatcher=ToolDispatcher())
    outcome = loop.run(
        client=c,
        system="sys", user_message="show me the table of top customers",
        dataset_loaded=False, max_steps=2,
    )
    assert outcome.final_text == _NO_TABLE_RESPONSE


# ── Loop wiring — run_stream() emits inline_table SSE event ───────────────────


def test_stream_emits_inline_table_event_when_injected() -> None:
    client = _client(_NO_TABLE_RESPONSE, _TABLE_RESPONSE)
    loop = AgentLoop(dispatcher=ToolDispatcher())
    events = list(loop.run_stream(
        client=client,
        system="sys", user_message="display the top 10 rows as a table",
        dataset_loaded=False, session_id="s", max_steps=2,
    ))
    inline_events = [e for e in events if e.type == "inline_table"]
    turn_end = [e for e in events if e.type == "turn_end"]
    assert len(inline_events) == 1
    assert inline_events[0].payload["reason"] == "user_requested_table_not_in_response"
    # The turn_end event carries the rewritten final_text.
    assert _response_has_table(turn_end[-1].payload["final_text"]) is True


def test_stream_no_inline_table_event_when_already_has_table() -> None:
    client = _client(_TABLE_RESPONSE)
    loop = AgentLoop(dispatcher=ToolDispatcher())
    events = list(loop.run_stream(
        client=client,
        system="sys", user_message="show me the top customers as a table",
        dataset_loaded=False, session_id="s", max_steps=2,
    ))
    assert not any(e.type == "inline_table" for e in events)


def test_stream_no_inline_table_event_when_user_did_not_ask() -> None:
    client = _client(_NO_TABLE_RESPONSE)
    loop = AgentLoop(dispatcher=ToolDispatcher())
    events = list(loop.run_stream(
        client=client,
        system="sys", user_message="explain the spending trend",
        dataset_loaded=False, session_id="s", max_steps=2,
    ))
    assert not any(e.type == "inline_table" for e in events)


def test_inline_table_synthesis_uses_minimal_system_prompt() -> None:
    """Fix-up must not re-use the noisy data-analyst system prompt."""
    captured: list[str] = []

    def _capture(req):  # noqa: ANN001
        captured.append(req.system)
        if len(captured) == 1:
            return CompletionResponse(
                text=_NO_TABLE_RESPONSE, tool_calls=(),
                stop_reason="end_turn", usage={},
            )
        return CompletionResponse(
            text=_TABLE_RESPONSE, tool_calls=(),
            stop_reason="end_turn", usage={},
        )

    c = MagicMock()
    c.name = "test"
    c.tier = "standard"
    c.complete.side_effect = _capture

    loop = AgentLoop(dispatcher=ToolDispatcher())
    loop.run(
        client=c, system="LONG NOISY DATA-ANALYST PROMPT",
        user_message="show me the top 5 rows", dataset_loaded=False, max_steps=2,
    )
    assert len(captured) == 2
    assert captured[0] == "LONG NOISY DATA-ANALYST PROMPT"
    # Fix-up call uses the dedicated minimal system prompt.
    assert "rewriting a previously-drafted response" in captured[1]
