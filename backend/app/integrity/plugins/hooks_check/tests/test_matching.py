"""Tests for the rule↔hook matching predicate."""
from __future__ import annotations

from backend.app.integrity.plugins.hooks_check.coverage import (
    CoverageRule,
    CoverageWhen,
    RequiredHook,
)
from backend.app.integrity.plugins.hooks_check.matching import matches
from backend.app.integrity.plugins.hooks_check.settings_parser import HookRecord


def _rule(event="PostToolUse", matcher="Write|Edit", substr="ruff") -> CoverageRule:
    return CoverageRule(
        id="r",
        description="d",
        when=CoverageWhen(paths=("*.py",)),
        requires_hook=RequiredHook(
            event=event, matcher=matcher, command_substring=substr,
        ),
    )


def _hook(event="PostToolUse", matcher="Write|Edit", command="uv run ruff check") -> HookRecord:
    return HookRecord(event=event, matcher=matcher, command=command, source_index=(0, 0, 0))


def test_match_event_matcher_substring() -> None:
    assert matches(_rule(), _hook())


def test_event_mismatch_returns_false() -> None:
    assert not matches(_rule(event="PostToolUse"), _hook(event="PreToolUse"))


def test_substring_absent_returns_false() -> None:
    assert not matches(_rule(substr="mypy"), _hook(command="uv run ruff check"))


def test_matcher_overlap_partial() -> None:
    # rule needs Write|Edit, hook fires on Edit|MultiEdit → overlap on Edit
    assert matches(_rule(matcher="Write|Edit"), _hook(matcher="Edit|MultiEdit"))


def test_matcher_disjoint_returns_false() -> None:
    assert not matches(_rule(matcher="Write"), _hook(matcher="Bash"))


def test_universal_hook_matcher_satisfies_any_rule() -> None:
    # hook matcher empty == universal; should still satisfy if event + substr match
    assert matches(_rule(matcher="Write"), _hook(matcher=""))


def test_empty_rule_matcher_skips_token_check() -> None:
    # rule has no token constraint — only event + substring matter
    assert matches(_rule(matcher=""), _hook(matcher="Write"))


def test_substring_case_sensitive() -> None:
    assert not matches(_rule(substr="Ruff"), _hook(command="uv run ruff"))


def test_pipe_with_extra_whitespace_ignored() -> None:
    # tokens are split on '|' — Claude Code matchers are exact pipe-joined names,
    # not regex, so leading/trailing whitespace in a token *is* significant. Verify.
    assert not matches(_rule(matcher="Write"), _hook(matcher=" Write "))


def test_substring_anywhere_in_command() -> None:
    assert matches(_rule(substr="ruff"), _hook(command="cd backend && uv run ruff && echo done"))
