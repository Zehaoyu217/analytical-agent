from __future__ import annotations

import json
import logging
from typing import Any

from app.harness.research.types import RoutePlan

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 512

_SYSTEM_PROMPT = """\
You are the routing agent for a research tool used by data scientists, ML engineers,
and quantitative analysts. Your job: given a research query, decide which source
modules to run, craft the best sub-query for each, allocate the token budget, and
determine if modules can run in parallel.

# Your default approach: start from the literature

Do not default to code or web first. Papers contain results — results tell you what
actually works. Only skip papers if the query is explicitly about implementation
details or a specific codebase.

## When to run modules in parallel

Run in parallel when each module can answer its sub-query independently:
- "best isotonic calibration methods" → papers + code simultaneously (parallel_ok: true)
- "find the dataset used in the Guo 2017 calibration paper" → papers first, then
  code/web with the dataset name (parallel_ok: false)

Rule: parallel_ok is false only when one module's output is the *input* to another's query.

## Budget allocation principles

You receive a total budget and must split it across the modules you select.
Allocation guidance:
- Papers crawls are expensive (citation graphs, section reads): give papers 50-70% when included
- Code search is cheap: 20-30% is usually enough
- Web fetch is cheapest: 10-20%
- If only one module runs, give it the full budget
- Never allocate less than 10,000 tokens to any module you include

## Output format

Respond ONLY with valid JSON. No prose before or after.

{
  "modules": ["papers", "code"],
  "sub_queries": {
    "papers": "isotonic regression calibration post-hoc methods imbalanced classification",
    "code": "isotonic calibration sklearn LightGBM example"
  },
  "budgets": {
    "papers": 90000,
    "code": 60000
  },
  "parallel_ok": true,
  "rationale": "one sentence explaining the routing decision"
}"""

_USER_TEMPLATE = """\
Query: {query}
Context: {context}
Available sources: {sources}
Total budget (tokens): {budget_tokens}

Route this query."""


def _fallback_plan(sources: list[str], budget_tokens: int, query: str) -> RoutePlan:
    per_module = max(10_000, budget_tokens // max(len(sources), 1))
    return RoutePlan(
        modules=tuple(sources),
        sub_queries={s: query for s in sources},
        budgets={s: per_module for s in sources},
        parallel_ok=True,
        rationale="fallback: equal split across all sources",
    )


class RoutingAgent:
    def __init__(self, api_client: Any) -> None:
        self._api = api_client

    def route(
        self,
        query: str,
        context: str,
        sources: list[str],
        budget_tokens: int,
    ) -> RoutePlan:
        user_msg = _USER_TEMPLATE.format(
            query=query,
            context=context or "none",
            sources=", ".join(sources),
            budget_tokens=budget_tokens,
        )
        try:
            resp = self._api.messages.create(
                model=_MODEL,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=_MAX_TOKENS,
            )
            text = ""
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    text += block.text
            data = json.loads(text.strip())
            return RoutePlan(
                modules=tuple(data["modules"]),
                sub_queries=data["sub_queries"],
                budgets=data["budgets"],
                parallel_ok=bool(data.get("parallel_ok", True)),
                rationale=data.get("rationale", ""),
            )
        except Exception as exc:
            logger.warning("RoutingAgent failed (%s) — using fallback plan", exc)
            return _fallback_plan(sources, budget_tokens, query)
