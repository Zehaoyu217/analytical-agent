# Eval Score History — Analytical Agent

> Running ledger of eval results across model + harness versions. **Append a new
> row per run** — do not overwrite history. Each row is a single point-in-time
> measurement; the goal is a visible quality trend line over the project's life.
>
> Populated from `docs/progress_eval_results_v1.md` (full bug-by-bug context for
> early runs) and from per-run summaries logged in `docs/log.md`.

## How to add a row

```bash
make seed-eval         # ensures eval.db is seeded (one-time per dataset change)
make eval level=1      # or just `make eval` for the full sweep
```

Then append a row to the table below with:
- **Date:** UTC date of the run
- **Model:** OpenRouter model id (e.g. `gpt-oss-120b:free`, `claude-sonnet-4-6`)
- **Commit:** short sha of the backend/harness commit under test
- **L1 / L2 / L3 / L4:** overall level grade (A–F) from the LLM judge
- **Notes:** what changed since the prior row, deterministic-check failures,
  variance observations. Be specific — "after P24 inline-table" beats "fixed
  bugs". Future-you will thank you.

If the agent or judge crashed, write `crashed` instead of a grade and link
the trace in the Notes column.

---

## Score Table

| Date       | Model               | Commit  | L1 | L2 | L3 | L4 | Notes |
|------------|---------------------|---------|----|----|----|----|-------|
| 2026-04-15 | gpt-oss-120b:free   | f5055c1 | C  | F  | D  | F  | First baseline. L2/L4 hit max_steps with empty `final_text`; L1 saved artifact instead of inline table; L3 filtered out `is_flagged=TRUE` rows. See `progress_eval_results_v1.md` §Baseline. |
| 2026-04-15 | gpt-oss-120b:free   | (post-v3 fixes) | C | B | C | B | After B1 (eval.db path), B2 (correlation step-fn), B3 (forced synthesis at max_steps), B4 (tool errors visible to model), B5 (3-location inline-table prompt), B6 (anomaly Working Loop). L1 `table_correctness:F` and L3 `false_positive_handling:F` persist as model-compliance issues. |

### Persistent failures to watch (rolling)

The deterministic-check failures below tend to recur run-to-run with
`gpt-oss-120b:free`. After P24 (inline-table fix-up) lands they should turn
from "model compliance" into "deterministically green":

| Check | Last status | Mitigation in place | Next action |
|-------|-------------|---------------------|-------------|
| L1 `table_correctness` (`"|" in t.final_output`) | failing as of 2026-04-15 | Prompt enforcement in 3 places (`data_scientist.md` + `injector.py` token budget + `_SYNTHESIS_SYSTEM`) | **P24 — post-turn `_inject_inline_table` re-synthesises with markdown table when user asked but response lacks one. Landed 2026-04-16; pending eval re-run to confirm.** |
| L3 `false_positive_handling` (keyword search for `bonus` / `home|house|down payment|savings` / `shopping|weekend|merchant|routine`) | failing as of 2026-04-15 | `data_scientist.md` step 4(d) + Non-Negotiable | P26 — concrete dismissal-table template in `data_scientist.md` |
| L3 `detection_recall` (wire / ATM cluster / Oceanic) | high variance A↔C | none — model-side | watch only |
| Skill name hallucination | ~1–2 per run | error response includes suggestions; model recovers in 1 call | P25 — register `read_file`/`glob_files`/`search_text` so recovery has fallback |

---

## How to interpret a row

- **A / B** — passing; ship it
- **C** — borderline; one or two dimensions failing, usually deterministic checks
- **D / F** — broken; either the agent crashed, hit `max_steps` with no final
  text, or the LLM judge graded multiple dimensions failing

Average grade across L1–L4 is *not* the right summary metric — a single F
usually points at one specific bug worth fixing, while three Bs point at
incremental polish work. Read the Notes column.

---

## Related docs

- `docs/progress_eval_results_v1.md` — first-run bug-by-bug post-mortem
- `docs/eval-readiness-audit.md` — what makes the eval harness trustworthy
- `docs/eval-judge-setup.md` — how to swap the LLM judge model
- `backend/tests/evals/rubrics/` — per-level rubric YAML (dimensions + weights)
- `docs/log.md` — every behaviour-changing harness/prompt edit lands here
