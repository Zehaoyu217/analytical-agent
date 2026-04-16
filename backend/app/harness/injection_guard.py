"""Prompt-injection scanning for external content (wiki, skills, session notes).

Any text sourced outside the codebase (wiki pages, prior session notes, skill
instructions loaded at runtime) is scanned for patterns commonly used in
prompt-injection attacks before it is merged into the system prompt.

On a positive match the caller receives an :class:`InjectionAttemptError` and
should log a warning then *skip* the block — do not halt the whole session.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # Classic "ignore previous/prior/all instructions" variants (with optional filler word)
    re.compile(
        r"ignore\s+(?:all\s+|the\s+)?(previous|prior|above)\s+(instructions?|prompts?)", re.I
    ),
    # "Forget everything you learned"
    re.compile(r"forget\s+(everything|all)\s+(you([' ]ve)?\s+)?learned", re.I),
    # "Disregard your instructions"
    re.compile(r"disregard\s+(your\s+)?(previous\s+)?instructions?", re.I),
    # Inline "new instructions:" header
    re.compile(r"\bnew\s+instructions?\s*:", re.I),
    # Fake system-role preamble
    re.compile(r"\bsystem\s*:\s*you\s+are\b", re.I),
    # HTML-style role tags (</system>, <human>, etc.)
    re.compile(r"</?(?:system|human|assistant)\s*/?>", re.I),
    # LLaMA instruct tokens
    re.compile(r"\[INST\]|\[/INST\]"),
    # ChatML control tokens
    re.compile(r"<\|im_start\|>|<\|im_end\|>"),
    # "You are now an X that ignores…"
    re.compile(
        r"you\s+are\s+now\s+(?:a\s+|an\s+)?\w+(?:\s+\w+)?\s+"
        r"(?:that|who)\s+(?:ignores?|doesn'?t\s+follow)",
        re.I,
    ),
    # "Act as a different/uncensored …"
    re.compile(r"\bact\s+as\s+(?:a\s+|an\s+)?(?:different|new|another|uncensored)\b", re.I),
]


class InjectionAttemptError(ValueError):
    """Raised when an injection-like pattern is detected in external content."""

    def __init__(self, source: str, pattern: str) -> None:
        super().__init__(
            f"Injection attempt detected in {source!r}: matched {pattern!r}"
        )
        self.source = source
        self.pattern = pattern


def scan(text: str, source: str = "unknown") -> None:
    """Scan *text* for prompt-injection patterns.

    Raises :class:`InjectionAttemptError` on the first match found.
    Safe (no match) calls return ``None``.

    Args:
        text:   Content to scan.
        source: Human-readable label used in the error / log message.
    """
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            raise InjectionAttemptError(source=source, pattern=pat.pattern)
