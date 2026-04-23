"""Wiki summarize pass — compact long wiki pages into a digestible note.

Scans ``SB_WIKI_DIR`` for pages over a length threshold and emits a ``keep``
proposal per page whose ``line`` carries the LLM-generated compact summary.
The digest UI surfaces the proposal for human review; no applier handler is
needed because ``keep`` is a no-op — the value is in human-read curation.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Iterator

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
_MIN_CHARS = 1500  # pages longer than this are candidates

_SYSTEM_PROMPT = """\
You compress a long personal-wiki page into a single-paragraph summary
(<=320 chars) that captures the page's purpose and key facts. Return JSON:
{"summary": str}
"""


class WikiSummarizePass:
    name = "wiki_summarize"
    tier: Tier = "default"
    prefix = "gw"

    def _candidates(self, cfg: Any) -> list[tuple[Path, str]]:
        wiki_dir_env = os.environ.get("SB_WIKI_DIR", "")
        if not wiki_dir_env:
            return []
        wiki_dir = Path(wiki_dir_env)
        if not wiki_dir.exists():
            return []
        out: list[tuple[Path, str]] = []
        for md in sorted(wiki_dir.rglob("*.md")):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            if len(text) < _MIN_CHARS:
                continue
            out.append((md, text))
        return out

    def estimate(self, cfg: Any, habits: Any) -> PassEstimate:
        pages = self._candidates(cfg)
        model = habits.gardener.models.get("default", "")
        tokens_in = 1200 * len(pages)
        tokens_out = 120 * len(pages)
        cost = estimate_cost(model, tokens_in, tokens_out) if model else 0.0
        return PassEstimate(tokens=tokens_in + tokens_out, cost_usd=cost)

    def run(
        self, cfg: Any, habits: Any, client: LLMClient, budget: Budget
    ) -> Iterator[Proposal]:
        wiki_dir_env = os.environ.get("SB_WIKI_DIR", "")
        wiki_dir = Path(wiki_dir_env) if wiki_dir_env else None
        for path, text in self._candidates(cfg):
            user = f"Wiki page ({path.name}):\n{text[:4000]}"
            try:
                result = client.complete(
                    _SYSTEM_PROMPT, user, max_tokens=220, temperature=0.0
                )
            except LLMError as exc:
                log.warning("wiki_summarize: llm failed for %s: %s", path, exc)
                continue
            cost = estimate_cost(client.model, result.tokens_in, result.tokens_out)
            try:
                budget.charge(cost, tokens=result.tokens_in + result.tokens_out)
            except BudgetExceeded:
                raise
            summary = _parse_summary(result.text)
            if not summary:
                continue
            try:
                rel = path.relative_to(wiki_dir) if wiki_dir else path
                rel_str = str(rel)
            except ValueError:
                rel_str = path.name
            action = {
                "type": "keep",
                "wiki_path": rel_str,
                "summary": summary,
            }
            yield Proposal(
                pass_name=self.name,
                section="Gardener wiki_summarize",
                line=f"{rel_str} · {summary}",
                action=action,
                input_refs=[rel_str],
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost_usd=cost,
            )


def _parse_summary(raw: str) -> str:
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
    val = obj.get("summary")
    if not isinstance(val, str):
        return ""
    return val.strip()[:320]
