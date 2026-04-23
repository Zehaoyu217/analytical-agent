---
name: sb-claim-review
description: Use when the user asks Claude to promote a finding, research result, or wiki insight into a second-brain atomic claim (`claims/*.md`) — covers drafting, edge-binding, and calling `sb_promote_claim`.
---

# Second Brain — Claim Review & Promotion

Use this skill when a conversation produces an insight the user wants to persist as a durable claim.

## Workflow

1. Restate the finding as a single **atomic, falsifiable** sentence. If you can't, stop — it is not a claim.
2. Classify the claim:
   - `kind`: one of `empirical`, `theoretical`, `definitional`, `opinion`, `prediction`.
   - `confidence`: `low` | `medium` | `high` (match the evidence, not the user's tone).
3. Identify related claims in the KB via `sb_search` and choose `supports`, `contradicts`, or `refines` edges. Empty lists are fine.
4. Call `sb_promote_claim` with:
   - `statement` (the atomic sentence)
   - `abstract` (≤ 2 sentences, why this claim matters)
   - `kind`, `confidence`
   - `supports` / `contradicts` / `refines` (list of `clm_*` ids; omit if empty)
   - `taxonomy` (e.g. `notes/personal`, `papers/ml`)
   - optional `source_ids` — list of `src_*` anchors for provenance.
5. Confirm the written path back to the user.

## Do not

- Do not write claims directly with `Write`. Always go through `sb_promote_claim` so reindexing and logging happen correctly.
- Do not invent `clm_*` ids when specifying edges — only reference ids that `sb_search` returned.
