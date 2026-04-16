# E2E Eval Results v1 — Analytical Agent Quality Baseline

**Date:** 2026-04-15  
**Model tested:** `gpt-oss-120b:free` (OpenRouter)  
**Backend commit:** `f5055c1` (feat/v2-os-platform merge)  
**Eval script:** `/tmp/e2e_eval.py` → `/tmp/e2e_l1_l3.py`  
**Rubrics:** `backend/tests/evals/rubrics/`  
**Judge:** `OpenRouterJudge` (LLM-based, dimension-level grades A–F)

---

## Eval Architecture

```
RealAgentAdapter
  ↓  POST /api/chat/stream  (SSE)
AgentLoop  →  ToolDispatcher  →  SandboxExecutor
  ↓
AgentTrace { final_output, queries, errors, token_count }
  ↓
evaluate_level(rubric, trace, judge, deterministic_checks)
  ↓
LevelResult { grade, dimensions[] { name, weight, grade, justification } }
```

Rubric files define LLM-judged dimensions with weights. Each level also has deterministic checks (lambda functions) that must pass for a passing grade on that dimension.

---

## Level Descriptions

| Level | Name | Key Skills Tested |
|---|---|---|
| L1 | Basic Rendering | Bar chart, top-N table, mermaid ERD |
| L2 | Systematic Exploration | Driver identification, confounder control, evidence chain |
| L3 | Anomaly Detection | Outlier flagging, false positive triage, per-item reasoning |
| L4 | Free Exploration | Dataset profiling, correlation finding, surprise discovery |

---

## Baseline Scores (pre-fix, first run)

Issues discovered before any fixes:

| Level | Grade | Notes |
|---|---|---|
| L1 | C | Table empty (agent saved artifact, didn't show inline); mermaid ERD inline |
| L2 | F | Empty response — agent hit 20-step max without writing final text |
| L3 | D | Agent filtered OUT is_flagged rows; detection recall missed seeded fraud patterns |
| L4 | F | Empty response — hit max_steps |

---

## Bugs Found and Fixed

### B1 — eval.db path mismatch

**Symptom:** Seed script seeded the wrong DB. Backend read from `backend/data/duckdb/eval.db` but seed targeted `data/duckdb/eval.db` (repo root, never read by sandbox).

**Fix:** `backend/scripts/seed_eval_data.py`  
Changed `DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "duckdb" / "eval.db"`  
→ `DB_PATH = Path(__file__).resolve().parent.parent / "data" / "duckdb" / "eval.db"`

### B2 — Weak credit score correlation

**Symptom:** L2 seeded data had credit score correlation = +0.0244 (effectively flat). Linear default probability formula produced 3–14% range across 80 loans — too flat for any model to detect.

**Fix:** Replaced linear formula with step-function in `seed_eval_data.py`:
```python
if score < 620:   default_prob = 0.85
elif score < 650: default_prob = 0.55
elif score < 680: default_prob = 0.25
elif score < 710: default_prob = 0.08
elif score < 740: default_prob = 0.03
else:             default_prob = 0.01
```
Result: correlation = −0.3508, default rate <650 = 42.9% vs 720+ = 6.5%.

### B3 — Empty response at max_steps (L2, L4)

**Symptom:** Agent exhausted the 20-step budget doing analysis without writing a final text response. `final_text` was empty; session ended silently.

**Fix:** `backend/app/harness/loop.py` — added forced synthesis in the for-else clause:
```python
else:
    stop_reason = "max_steps"
    if not final_text.strip() and messages:
        synth_msgs = _build_synthesis_messages(user_message, messages)
        synth_req = CompletionRequest(
            system=_SYNTHESIS_SYSTEM,
            messages=tuple(synth_msgs),
            tools=(),
            tool_choice=None,
        )
        synth_resp = client.complete(synth_req)
        final_text = (synth_resp.text or "").strip()
```

Note: Initial fix had a bug — called `client.complete(system=..., messages=...)` (kwargs). `complete()` takes a single `CompletionRequest` object. Silent `TypeError` swallowed. Fixed by constructing the object explicitly.

### B4 — Tool errors invisible to model

**Symptom:** Failed tool calls returned `json.dumps(None)` = `"null"` as tool result content. Model received no error context and had no way to recover.

**Fix:** `backend/app/harness/loop.py` — include error message in tool result:
```python
if not result.ok:
    content = json.dumps({"error": result.error_message or "tool call failed"})
```
Also updated `_SingleToolResult.result_payload` for SSE preview.

### B5 — Inline table blocked by two conflicting instructions

**Symptom:** L1 prompt asked to "show the top 10 customers as a table" but agent saved artifact and cited by title instead of showing rows inline. Two sources blocked inline display:
1. `prompts/data_scientist.md` Non-Negotiables: "Never write raw data inline. Save with `save_artifact`."
2. `backend/app/harness/injector.py` token budget section: "Prefer `save_artifact` over dumping full tables."

**Fix:** Both locations updated with inline display exception:
> When the user explicitly asks to "show", "display", or "list" a specific table or set of rows, include it inline (≤20 rows as markdown) AND save as artifact.

Also updated `_SYNTHESIS_SYSTEM` in `loop.py` which had a separate "do not reproduce raw data inline" instruction.

### B6 — L3 agent skipping pre-flagged transactions

**Symptom:** Agent filtered OUT `is_flagged=TRUE` rows ("already handled" reasoning), then ran statistical detection on the remainder. Missed the seeded fraud patterns entirely.

**Fix:** `prompts/data_scientist.md` Working Loop step 4 — explicit anomaly workflow:
```
(a) inspect ALL rows with is_flagged=TRUE first — pre-known flags requiring review, not items to skip
(b) then apply statistical detection to ALL transactions  
(c) then triage: confirm real anomalies vs false positives
(d) final response must list BOTH confirmed anomalies AND dismissed false positives with per-item reasoning
```

Also added Non-Negotiable: "Anomaly reports must include dismissals."

---

## Post-Fix Scores (best run)

| Level | Grade | Dimensions |
|---|---|---|
| L1 | C | chart_correctness:A  table_correctness:F  mermaid_erd:C  process_quality:B |
| L2 | B | (multiple runs, grade stabilized around B after synthesis fix) |
| L3 | C | detection_recall:A  false_positive_handling:F  methodology:A  final_report:B |
| L4 | B | (free exploration; synthesis path produced coherent findings) |

---

## Remaining Failures

### RF1 — L1 table_correctness: F (persistent)

**Root cause:** `gpt-oss-120b:free` consistently saves to artifact rather than showing inline, even with three-location prompt enforcement (data_scientist.md + injector.py + synthesis system). When agent finishes in 8 steps via `end_turn`, synthesis path is not triggered — the regular system prompt drives behavior and the model doesn't comply.

**Nature:** Model compliance issue, not a harness bug.

**Mitigation applied:** All three prompt locations updated. Average-case behavior will improve. Deterministic pass rate depends on model compliance per-run.

### RF2 — L3 false_positive_handling: F (persistent)

**Root cause:** Agent finds confirmed anomalies but doesn't explicitly name the false positive patterns ("Annual Performance Bonus", "home purchase down payment", "Purchase at Target"). Deterministic checks look for keywords: `bonus`, `home/house/down payment/savings`, `shopping/weekend/merchant/routine`.

Seeded false positive transactions (all have `is_flagged=TRUE`):
```
txn_id=18: "Annual Performance Bonus 2025"  +$15,000  category=payroll
txn_id=19: "Transfer from savings — home purchase down payment"  +$50,000  category=transfer
txn_id=20: "Purchase at Target"  −$86.10  category=merchant
```

**Mitigation applied:** Step (d) in Working Loop + Non-Negotiable added. Model needs to name each dismissed item by description.

### RF3 — L3 detection_recall: high variance

**Root cause:** Statistical outlier detection (find_anomalies seasonal-ESD) finds 500+ rows across the whole series. Whether the agent's final 12 confirmed anomalies include the wire transfer ("47"), ATM withdrawals ("12"), and "Oceanic Holdings" depends on whether the model inspects the `is_flagged=TRUE` rows in detail.

Seeded true anomaly descriptions:
```
txn_id=1:  "Wire transfer — urgent request"  −$47,000  category=wire
txn_id=2–13: "ATM withdrawal #1–12"  −$300–$465 each  same account, same day
txn_id=14–17: "Transfer to Oceanic Holdings — invoice 1000–1003"  −$11k–$15k each
```

Grade swings A (when agent inspects pre-flagged rows) → C (when agent goes straight to statistical detection). Variance is model-side.

### RF4 — Skill name hallucination (~1-2 per run)

**Symptom:** `gpt-oss-120b:free` calls `skill("find_anomalies")`, `skill("statistical_analysis.time_series")`, etc. — names that don't exist.

**Mitigation applied:** Error message now includes suggestions: `{"error": "KeyError: 'find_anomalies' not found. 16 skills available. Suggestions: ..."}`. Model recovers within 1 tool call by loading the correct parent skill.

---

## Seeded Eval Data (backend/scripts/seed_eval_data.py)

```
tables:   customers (80), accounts (80), transactions (4900+), loans (80), daily_rates (366)
period:   2024-01-01 – 2025-12-31
Q3 2025:  27 is_flagged transactions (true anomalies + false positives, all pre-labeled)
DB path:  backend/data/duckdb/eval.db
```

True anomaly patterns (check keywords):
- Wire: "wire" + "47" (amount -47000)
- ATM cloning: "atm" + "12" (12 withdrawals, same account, same day)
- Shell entity: "oceanic"

False positive patterns (check keywords):
- "bonus" / "annual" + "performance"
- "home" / "savings" / "down payment"
- "merchant" / "target"

---

## Eval Infrastructure Files

| File | Purpose |
|---|---|
| `tests/evals/rubrics/level1_rendering.yaml` | L1 LLM rubric |
| `tests/evals/rubrics/level2_exploration.yaml` | L2 LLM rubric |
| `tests/evals/rubrics/level3_anomaly.yaml` | L3 LLM rubric |
| `tests/evals/rubrics/level4_free_explore.yaml` | L4 LLM rubric |
| `tests/evals/real_agent.py` | RealAgentAdapter (SSE client → AgentTrace) |
| `app/evals/judge.py` | OpenRouterJudge (LLM-based grade per dimension) |
| `app/evals/runner.py` | evaluate_level(), format_level_result() |
| `app/evals/rubric.py` | load_rubric() |
| `app/evals/types.py` | AgentTrace, LevelResult, DimensionResult |
| `backend/scripts/seed_eval_data.py` | Seeds deterministic eval dataset |

---

## Next Steps → See progress_plan_v4.md
