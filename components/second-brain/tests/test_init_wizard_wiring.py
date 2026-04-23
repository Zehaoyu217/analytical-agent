from __future__ import annotations

from second_brain.init_wizard.wiring import render_wiring_instructions


def test_render_wiring_instructions_mentions_cc_agent_hook_keys():
    text = render_wiring_instructions(home="/Users/jay/second-brain")

    assert "UserPromptSubmit" in text
    assert "PostToolUse" in text
    assert "sb inject" in text
    assert "sb reindex" in text
    assert "SECOND_BRAIN_HOME" in text
    assert "/Users/jay/second-brain" in text


def test_render_wiring_instructions_works_without_home():
    text = render_wiring_instructions()
    assert "SECOND_BRAIN_HOME" in text
    assert "UserPromptSubmit" in text
