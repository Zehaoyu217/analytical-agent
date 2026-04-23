---
name: sb-daily
description: Use when the user asks Claude to review today's ingested sources, triage the inbox, run `sb maintain`, or summarise recent claim activity in the second-brain KB.
---

# Second Brain — Daily Review

Use this skill when the user says things like "run my daily second-brain review", "triage today's inbox", or "what did I capture recently?".

## Workflow

1. Run `sb status` and `sb process-inbox` in parallel via the Bash tool. Report counts (ok/failed/quarantined).
2. Run `sb maintain --json` and surface:
   - Lint error/warning counts
   - Open contradictions (highlight any ≥ 5)
   - Stale abstract count
   - Whether analytics was rebuilt and any habit proposals
3. Run `sb stats --json`. Report the health score and its top two deductions.
4. If any proposals exist under `~/second-brain/proposals/`, list them and ask the user whether to apply (do NOT apply automatically).

## Do not

- Do not auto-answer habit proposals. Let the user confirm.
- Do not run `sb eval` in the daily flow — it's for CI / explicit requests.
- Do not push the git repo under `~/second-brain/` unless the user asks.

## See also

- `sb-research` — for targeted retrieval / reasoning flows.
- `sb-claim-review` — for promoting findings into claims.
