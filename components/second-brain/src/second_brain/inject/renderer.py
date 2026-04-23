from __future__ import annotations

from second_brain.index.retriever import RetrievalHit

_HEADER = "### Second Brain — top matches for this prompt"
_FOOTER = "Use sb_load(<id>, depth=1) to expand any of these."


def _approx_tokens(text: str) -> int:
    # A rough 4-char-per-token heuristic is fine for the budget cap.
    return max(1, len(text) // 4)


def _render_hit(idx: int, hit: RetrievalHit) -> str:
    lines = [f"{idx}. [{hit.id}] (score {hit.score:.2f})"]
    if hit.snippet:
        lines.append(f"   {hit.snippet.strip()}")
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
