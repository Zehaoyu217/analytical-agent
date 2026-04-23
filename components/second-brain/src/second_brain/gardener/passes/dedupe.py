"""Dedupe pass — find near-duplicate claims and propose drop_edge on one.

Uses Jaccard token overlap over statements to surface candidate pairs, then
asks the LLM whether they state the same thing. On "yes" emits a
``drop_edge`` proposal (a light action that the applier already supports)
targeting the lower-confidence claim.
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
_MIN_JACCARD = 0.55

_CONF_RANK = {"low": 0, "medium": 1, "high": 2}

_SYSTEM_PROMPT = """\
You decide whether two KB claims state the same atomic fact. Return JSON:
{"duplicate": true|false, "reason": str}
"""


class DedupePass:
    name = "dedupe"
    tier: Tier = "default"
    prefix = "gd"

    def _candidates(self, cfg: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        claims_dir: Path = cfg.claims_dir
        if not claims_dir.exists():
            return []
        items: list[dict[str, Any]] = []
        for p in sorted(claims_dir.glob("*.md")):
            try:
                fm, _body = load_document(p)
            except (ValueError, OSError):
                continue
            cid = str(fm.get("id") or p.stem)
            statement = str(fm.get("statement") or "")
            toks = set(_WORD_RE.findall(statement.lower()))
            if not toks:
                continue
            items.append(
                {
                    "id": cid,
                    "statement": statement,
                    "confidence": str(fm.get("confidence") or "medium"),
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
                if jac >= _MIN_JACCARD:
                    out.append((a, b))
        return out

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        pairs = self._candidates(cfg)
        model = habits.gardener.models.get("default", "")
        tokens_in = 200 * len(pairs)
        tokens_out = 40 * len(pairs)
        cost = estimate_cost(model, tokens_in, tokens_out) if model else 0.0
        return PassEstimate(tokens=tokens_in + tokens_out, cost_usd=cost)

    def run(
        self, cfg: Any, habits: Any, client: LLMClient, budget: Budget
    ) -> Iterator[Proposal]:
        for a, b in self._candidates(cfg):
            user = f"Claim A: {a['statement']}\nClaim B: {b['statement']}"
            try:
                result = client.complete(
                    _SYSTEM_PROMPT, user, max_tokens=128, temperature=0.0
                )
            except LLMError as exc:
                log.warning("dedupe: llm failed for %s/%s: %s", a["id"], b["id"], exc)
                continue
            cost = estimate_cost(client.model, result.tokens_in, result.tokens_out)
            try:
                budget.charge(cost, tokens=result.tokens_in + result.tokens_out)
            except BudgetExceeded:
                raise
            decision = _parse_decision(result.text)
            if not decision.get("duplicate"):
                continue
            # Drop the lower-confidence one; ties drop B.
            ra = _CONF_RANK.get(a["confidence"], 1)
            rb = _CONF_RANK.get(b["confidence"], 1)
            loser = a if ra < rb else b
            keeper = b if loser is a else a
            action = {
                "type": "drop_edge",
                "src_id": loser["id"],
                "dst_id": keeper["id"],
                "relation": "supports",
                "reason": decision.get("reason", ""),
            }
            yield Proposal(
                pass_name=self.name,
                section="Gardener dedupe",
                line=f"Drop duplicate {loser['id']} (keep {keeper['id']})",
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
