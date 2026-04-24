"""Render a retrieval result into a system-prompt block.

Design goal: make the agent able to cite faithfully without a follow-up
``sb_load`` tool call. The old renderer emitted only a ~1-line abstract;
this one adds, for claim hits:

- the atomic claim statement (the falsifiable assertion)
- the source ids it supports (so the agent can say "per src_foo")
- a short evidence snippet when the snippet ≠ the statement

Non-claim hits stay compact. Token cost is bounded by
``render_injection_block(max_tokens=...)``; when we'd exceed it we drop
hits from the tail and annotate truncation, same as before.
"""
from __future__ import annotations

from second_brain.index.retriever import RetrievalHit

_HEADER = "### Second Brain — top matches for this prompt"
_FOOTER = (
    "Cite inline with the [clm_…] id. "
    "Use sb_load(<id>, depth=1) to expand any of these."
)


def _approx_tokens(text: str) -> int:
    # A rough 4-char-per-token heuristic is fine for the budget cap.
    return max(1, len(text) // 4)


def _truncate(text: str, max_chars: int) -> str:
    """Collapse whitespace and cap to *max_chars* with an ellipsis when cut."""
    clean = " ".join((text or "").split()).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "…"


def _render_hit(idx: int, hit: RetrievalHit) -> str:
    supports_str = ""
    if hit.kind == "claim" and hit.supports:
        shown = ", ".join(hit.supports[:3])
        more = f" (+{len(hit.supports) - 3})" if len(hit.supports) > 3 else ""
        supports_str = f" — supports: {shown}{more}"

    lines = [f"{idx}. [{hit.id}] (score {hit.score:.2f}){supports_str}"]

    statement_shown = False
    if hit.kind == "claim" and hit.statement:
        lines.append(f"   STATEMENT: {_truncate(hit.statement, 240)}")
        statement_shown = True

    if hit.snippet:
        snippet_clean = _truncate(hit.snippet, 280)
        # Skip the snippet when it's the same text as the statement —
        # avoids printing the same sentence twice within one hit.
        statement_clean = _truncate(hit.statement, 280) if statement_shown else ""
        if not statement_shown or snippet_clean.lower() != statement_clean.lower():
            label = "excerpt" if statement_shown else None
            lines.append(
                f"   {label}: {snippet_clean}" if label else f"   {snippet_clean}"
            )

    for n in hit.neighbors:
        lines.append(f"   ◇ neighbor: {n}")
    return "\n".join(lines)


def render_injection_block(
    hits: list[RetrievalHit],
    *,
    max_tokens: int | None = None,
) -> str:
    if not hits:
        return ""

    rendered: list[str] = [_HEADER, ""]
    truncated = False
    running = _approx_tokens(_HEADER) + _approx_tokens(_FOOTER)

    for i, h in enumerate(hits, 1):
        block = _render_hit(i, h)
        cost = _approx_tokens(block)
        if max_tokens is not None and running + cost > max_tokens and i > 1:
            truncated = True
            break
        rendered.append(block)
        running += cost

    rendered.append("")
    if truncated:
        rendered.append("(truncated by injection budget)")
    rendered.append(_FOOTER)
    return "\n".join(rendered)
