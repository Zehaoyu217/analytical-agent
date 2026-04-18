"""Tests for sb_digest_hook injection into the system prompt."""
from __future__ import annotations

from unittest.mock import patch


def test_system_prompt_includes_digest_summary():
    with patch(
        "app.hooks.sb_digest_hook.build_digest_summary",
        return_value="2 pending KB decisions",
    ):
        from app.api.chat_api import _build_system_prompt

        prompt = _build_system_prompt()
    assert "Pending knowledge base digest" in prompt
    assert "2 pending KB decisions" in prompt


def test_system_prompt_omits_section_when_no_digest():
    with patch(
        "app.hooks.sb_digest_hook.build_digest_summary",
        return_value=None,
    ):
        from app.api.chat_api import _build_system_prompt

        prompt = _build_system_prompt()
    assert "Pending knowledge base digest" not in prompt
