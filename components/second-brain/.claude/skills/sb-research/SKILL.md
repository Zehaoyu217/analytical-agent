---
name: sb-research
description: Use when the user wants Claude to answer a question grounded in the second-brain KB — retrieve claims, walk supports/contradicts chains, and cite source ids before proposing an answer.
---

# Second Brain — Research

Use this skill when the user asks a factual question and wants KB-grounded answers rather than general knowledge.

## Retrieval-first contract

1. Call `sb_search` (or run `sb search <query> --k 10`) first. Prefer `scope=claims`.
2. For each promising hit, call `sb_load` (or `sb load <id> --depth 1`) to pull in neighbours.
3. When a claim has `contradicts:` edges, always fetch both sides before asserting either.
4. Use `sb_reason` (or `sb reason <id> supports --depth 3`) to follow support chains when asked "why".
5. Cite every non-trivial claim by its `clm_*` id. Name the source id when quoting.

## Never

- Never answer from memory when the KB has hits — the KB represents the user's curated truth.
- Never silently pick one side of a contradiction. Surface both, then offer a recommendation.

## See also

- `sb-claim-review` — when research turns up a new atomic claim worth persisting.
