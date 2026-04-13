from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.turn_state import TurnState
from app.harness.wrap_up import TurnWrapUp, WrapUpResult


def test_wrap_up_appends_log_updates_working_emits_events() -> None:
    wiki = MagicMock()
    bus = MagicMock()
    state = TurnState(scratchpad="TURN BODY")
    state.record_artifact("a1")
    state.record_tool("correlation.correlate",
                      {"coefficient": 0.5, "artifact_id": "a1"})

    wrap = TurnWrapUp(wiki=wiki, event_bus=bus)
    out = wrap.finalize(
        state=state,
        final_text="done",
        session_id="s1",
        turn_index=3,
    )
    assert isinstance(out, WrapUpResult)
    wiki.append_log.assert_called_once()
    wiki.update_working.assert_called_once_with("TURN BODY")
    wiki.rebuild_index.assert_called_once()
    assert any(c.args[0]["type"] == "turn_completed"
               for c in bus.emit.call_args_list)


def test_wrap_up_promotes_findings_with_validate_and_evidence() -> None:
    wiki = MagicMock()
    bus = MagicMock()
    state = TurnState(scratchpad="""
## Findings
[F-20260412-001] Price and demand correlate. Evidence: a1. Validated: v1.
""")
    state.record_artifact("a1")
    state.record_tool("stat_validate.validate", {"status": "PASS"})

    wrap = TurnWrapUp(wiki=wiki, event_bus=bus)
    wrap.finalize(state=state, final_text="", session_id="s1", turn_index=1)
    wiki.promote_finding.assert_called_once()
    call_kwargs = wiki.promote_finding.call_args.kwargs
    assert call_kwargs["finding_id"] == "F-20260412-001"
    assert "Price and demand correlate" in call_kwargs["body"]
    assert call_kwargs["evidence_ids"] == ["a1"]
    assert call_kwargs["validated_by"] == "v1"


def test_wrap_up_skips_promotion_when_evidence_missing() -> None:
    wiki = MagicMock()
    bus = MagicMock()
    state = TurnState(scratchpad="""
## Findings
[F-20260412-002] Revenue grew 20%.
""")
    wrap = TurnWrapUp(wiki=wiki, event_bus=bus)
    wrap.finalize(state=state, final_text="", session_id="s1", turn_index=1)
    wiki.promote_finding.assert_not_called()
