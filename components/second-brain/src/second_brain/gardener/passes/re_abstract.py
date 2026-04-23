"""Re-abstract pass — rewrite claim abstracts flagged as stale.

Scans ``claims/*.md`` for frontmatter ``needs_reabstract: true``, batches by
taxonomy prefix, asks the LLM for a compact new abstract per claim, and emits
one ``re_abstract_batch`` proposal per prefix. The existing digest applier
(``_handle_re_abstract_batch``) already knows how to apply this action.
"""
from __future__ import annotations

import json
import logging
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

_SYSTEM_PROMPT = """\
You rewrite claim abstracts for a personal research KB. Given a claim's
statement, prior abstract, and supporting evidence, return a single JSON object:

{"abstract": "<one sentence, <=160 chars, no pronouns, no invented facts>"}

Return ONLY the JSON object.
"""


class ReAbstractPass:
    name = "re_abstract"
    tier: Tier = "default"
    prefix = "gr"

    def _stale_claims(self, cfg: Any) -> list[tuple[str, Path, dict[str, Any], str]]:
        out: list[tuple[str, Path, dict[str, Any], str]] = []
        claims_dir: Path = cfg.claims_dir
        if not claims_dir.exists():
            return out
        for p in sorted(claims_dir.glob("*.md")):
            try:
                fm, body = load_document(p)
            except (ValueError, OSError):
                continue
            if not fm.get("needs_reabstract"):
                continue
            cid = str(fm.get("id") or p.stem)
            out.append((cid, p, fm, body))
        return out

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        todo = self._stale_claims(cfg)
        model = habits.gardener.models.get("default", "")
        # ~500 tokens in + 80 out per claim.
        tokens_in = 500 * len(todo)
        tokens_out = 80 * len(todo)
        cost = estimate_cost(model, tokens_in, tokens_out) if model else 0.0
        return PassEstimate(tokens=tokens_in + tokens_out, cost_usd=cost)

    def run(
        self, cfg: Any, habits: Any, client: LLMClient, budget: Budget
    ) -> Iterator[Proposal]:
        todo = self._stale_claims(cfg)
        batches: dict[str, list[dict[str, str]]] = {}
        refs_by_prefix: dict[str, list[str]] = {}
        totals_by_prefix: dict[str, tuple[int, int, float]] = {}

        for cid, _path, fm, body in todo:
            statement = str(fm.get("statement") or "")
            prior = str(fm.get("abstract") or "")
            taxonomy = str(fm.get("taxonomy") or "uncategorized")
            prefix = taxonomy.split("/", 1)[0]
            user = (
                f"Statement: {statement}\n"
                f"Prior abstract: {prior}\n"
                f"Evidence body:\n{body[:1200]}"
            )
            try:
                result = client.complete(
                    _SYSTEM_PROMPT, user, max_tokens=256, temperature=0.0
                )
            except LLMError as exc:
                log.warning("re_abstract: llm failed for %s: %s", cid, exc)
                continue
            cost = estimate_cost(client.model, result.tokens_in, result.tokens_out)
            try:
                budget.charge(cost, tokens=result.tokens_in + result.tokens_out)
            except BudgetExceeded:
                raise
            new_abstract = _parse_abstract(result.text)
            if not new_abstract:
                continue
            batches.setdefault(prefix, []).append(
                {"claim_id": cid, "abstract": new_abstract}
            )
            refs_by_prefix.setdefault(prefix, []).append(cid)
            tin, tout, spent = totals_by_prefix.get(prefix, (0, 0, 0.0))
            totals_by_prefix[prefix] = (
                tin + result.tokens_in,
                tout + result.tokens_out,
                spent + cost,
            )

        for prefix, items in batches.items():
            action = {
                "type": "re_abstract_batch",
                "claim_ids": [i["claim_id"] for i in items],
                "new_abstracts": {i["claim_id"]: i["abstract"] for i in items},
            }
            tin, tout, spent = totals_by_prefix[prefix]
            yield Proposal(
                pass_name=self.name,
                section=f"Gardener re_abstract · {prefix}",
                line=f"{len(items)} claim abstracts rewritten under {prefix}/",
                action=action,
                input_refs=refs_by_prefix[prefix],
                tokens_in=tin,
                tokens_out=tout,
                cost_usd=spent,
            )


def _parse_abstract(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(obj, dict):
        return ""
    val = obj.get("abstract")
    if not isinstance(val, str):
        return ""
    return val.strip()[:160]
