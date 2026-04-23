"""Contradict pass — surface claim pairs that may disagree on the same topic.

Candidates are claim pairs with moderate Jaccard overlap (topic-similar but
not near-duplicate). The LLM decides whether they actually contradict and, if
so, emits a ``resolve_contradiction`` proposal consumed by the existing
digest applier.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterator

from second_brain.frontmatter import load_document
from second_brain.gardener.client import LLMClient, LLMError
from second_brain.gardener.cost import estimate_cost
from second_brain.gardener.protocol import (
    Budget,
    BudgetExceeded,
    PassEstimate,
    Proposal,
    Tier,
)

log = logging.getLogger(__name__)
_WORD_RE = re.compile(r"[a-z0-9]{3,}")
_MIN_JACCARD = 0.30
_MAX_JACCARD = 0.55  # above this → dedupe territory

_SYSTEM_PROMPT = """\
You decide whether two KB claims contradict each other about the same topic.
Return JSON: {"contradicts": true|false,
"resolution": "A"|"B"|"both_hold"|"neither_holds",
"rationale": str}
Only set contradicts=true when the claims cannot both be true as stated.
"""


class ContradictPass:
    name = "contradict"
    tier: Tier = "deep"
    prefix = "gc"

    def _candidates(
        self, cfg: Any
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        claims_dir: Path = cfg.claims_dir
        if not claims_dir.exists():
            return []
        items: list[dict[str, Any]] = []
        for p in sorted(claims_dir.glob("*.md")):
            try:
                fm, _body = load_document(p)
            except (ValueError, OSError):
                continue
            statement = str(fm.get("statement") or "")
            toks = set(_WORD_RE.findall(statement.lower()))
            if not toks:
                continue
            items.append(
                {
                    "id": str(fm.get("id") or p.stem),
                    "statement": statement,
                    "tokens": toks,
                }
            )
        out: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                u = len(a["tokens"] | b["tokens"])
                if u == 0:
                    continue
                jac = len(a["tokens"] & b["tokens"]) / u
                if _MIN_JACCARD <= jac < _MAX_JACCARD:
                    out.append((a, b))
        return out

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        pairs = self._candidates(cfg)
        model = habits.gardener.models.get("deep") or habits.gardener.models.get(
            "default", ""
        )
        tokens_in = 250 * len(pairs)
        tokens_out = 60 * len(pairs)
        cost = estimate_cost(model, tokens_in, tokens_out) if model else 0.0
        return PassEstimate(tokens=tokens_in + tokens_out, cost_usd=cost)

    def run(
        self, cfg: Any, habits: Any, client: LLMClient, budget: Budget
    ) -> Iterator[Proposal]:
        for a, b in self._candidates(cfg):
            user = f"Claim A ({a['id']}): {a['statement']}\nClaim B ({b['id']}): {b['statement']}"
            try:
                result = client.complete(
                    _SYSTEM_PROMPT, user, max_tokens=160, temperature=0.0
                )
            except LLMError as exc:
                log.warning("contradict: llm failed for %s/%s: %s", a["id"], b["id"], exc)
                continue
            cost = estimate_cost(client.model, result.tokens_in, result.tokens_out)
            try:
                budget.charge(cost, tokens=result.tokens_in + result.tokens_out)
            except BudgetExceeded:
                raise
            decision = _parse_decision(result.text)
            if not decision.get("contradicts"):
                continue
            action = {
                "type": "resolve_contradiction",
                "left_id": a["id"],
                "right_id": b["id"],
                "rationale": decision.get("rationale", ""),
                "resolution": decision.get("resolution", "both_hold"),
            }
            yield Proposal(
                pass_name=self.name,
                section="Gardener contradict",
                line=f"{a['id']} vs {b['id']}",
                action=action,
                input_refs=[a["id"], b["id"]],
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=cost,
            )


def _parse_decision(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return obj if isinstance(obj, dict) else {}
