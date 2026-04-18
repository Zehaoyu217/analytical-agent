"""Verify the 7 new Second-Brain digest ToolSchemas are exported and registered."""
from __future__ import annotations


def test_all_digest_tools_registered():
    from app.api.chat_api import (
        _SB_DIGEST_APPLY,
        _SB_DIGEST_LIST,
        _SB_DIGEST_PROPOSE,
        _SB_DIGEST_SHOW,
        _SB_DIGEST_SKIP,
        _SB_DIGEST_TODAY,
        _SB_STATS,
    )

    names = {
        s.name
        for s in [
            _SB_DIGEST_TODAY,
            _SB_DIGEST_LIST,
            _SB_DIGEST_SHOW,
            _SB_DIGEST_APPLY,
            _SB_DIGEST_SKIP,
            _SB_DIGEST_PROPOSE,
            _SB_STATS,
        ]
    }
    assert names == {
        "sb_digest_today",
        "sb_digest_list",
        "sb_digest_show",
        "sb_digest_apply",
        "sb_digest_skip",
        "sb_digest_propose",
        "sb_stats",
    }


def test_digest_tools_in_chat_tools_aggregate():
    from app.api.chat_api import _CHAT_TOOLS

    names = {t.name for t in _CHAT_TOOLS}
    assert {
        "sb_digest_today",
        "sb_digest_list",
        "sb_digest_show",
        "sb_digest_apply",
        "sb_digest_skip",
        "sb_digest_propose",
        "sb_stats",
    } <= names
