---
name: analysis_plan
description: Scaffolds an ordered investigation plan (profile → hypothesize → analyze → validate → report) from a one-line question. Writes to wiki/working.md.
level: 3
version: 0.1.0
---

# analysis_plan

Turn a question into structured steps. The plan is written to `wiki/working.md` under the `TODO` section so the agent picks it up on the next ORIENT step.

## When to invoke

- New investigation, unfamiliar dataset, open-ended question.
- After a major context reset where the previous plan got lost.

## Not for

- Single-shot calculations (just run `correlate()` or `compare()` directly).
- Follow-up questions where `working.md` already has an active plan.

## Entry point

`plan(question: str, dataset: str | None = None, depth: Literal["quick", "standard", "deep"] = "standard") -> PlanResult`

Returns a `PlanResult` with an ordered list of steps (each step names the skill to use and what artifact to produce) and writes the plan into `wiki/working.md`.
