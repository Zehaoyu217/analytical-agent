"""Rule↔hook matching predicate.

A coverage rule is *satisfied* by a hook iff:
    1. ``hook.event == rule.requires_hook.event``
    2. The hook's matcher tokens overlap the rule's matcher tokens
       (or hook matcher is empty, meaning universal).
    3. ``rule.requires_hook.command_substring`` appears in ``hook.command``.

Matchers are pipe-joined literal tool names — ``Write|Edit|MultiEdit``. We treat
each side as a token set and check intersection. Empty hook matcher is treated
as the universal set (Claude Code applies it to every tool). Empty rule matcher
means "no constraint" — the token-overlap check is skipped.
"""
from __future__ import annotations

from .coverage import CoverageRule
from .settings_parser import HookRecord


def matches(rule: CoverageRule, hook: HookRecord) -> bool:
    if hook.event != rule.requires_hook.event:
        return False
    rule_tokens = set(filter(None, rule.requires_hook.matcher.split("|")))
    hook_tokens = set(filter(None, hook.matcher.split("|")))
    if rule_tokens and hook_tokens and rule_tokens.isdisjoint(hook_tokens):
        return False
    return rule.requires_hook.command_substring in hook.command
