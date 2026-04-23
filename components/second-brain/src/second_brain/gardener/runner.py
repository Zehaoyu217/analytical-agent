"""Gardener runner — orchestrates enabled passes under a budget.

The runner iterates passes in a fixed order, runs each (wired with the shared
LLM client + budget), and streams emitted proposals into two sinks:

- ``digests/pending.jsonl`` — the existing proposal queue consumed by the
  digest applier, so gardener output flows through the same acceptance UI.
- ``.sb/.state/gardener.log.jsonl`` — the dual-layer audit log.

A :class:`BudgetExceeded` during a pass halts the run; any proposals emitted
before the trip are retained. ``dry_run=True`` makes passes run but suppresses
both sinks and the ledger update.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable

from second_brain.gardener import audit
from second_brain.gardener.client import LLMClient
from second_brain.gardener.cost import estimate_cost
from second_brain.gardener.passes import (
    ContradictPass,
    DedupePass,
    ExtractPass,
    ReAbstractPass,
    SemanticLinkPass,
    TaxonomyCuratePass,
    WikiSummarizePass,
)
from second_brain.gardener.protocol import (
    Budget,
    BudgetExceeded,
    CostEstimate,
    GardenerPass,
    PassEstimate,
    Proposal,
    RunResult,
    Tier,
)

# Fixed execution order. Disabled passes are skipped per habits.
_PASS_ORDER: list[str] = [
    "extract",
    "re_abstract",
    "semantic_link",
    "dedupe",
    "contradict",
    "taxonomy_curate",
    "wiki_summarize",
]


def _default_passes() -> list[GardenerPass]:
    return [
        ExtractPass(),
        ReAbstractPass(),
        SemanticLinkPass(),
        DedupePass(),
        ContradictPass(),
        TaxonomyCuratePass(),
        WikiSummarizePass(),
    ]


class GardenerRunner:
    def __init__(
        self,
        cfg: Any,
        habits: Any,
        *,
        passes: list[GardenerPass] | None = None,
        client_factory: Any | None = None,
    ) -> None:
        self.cfg = cfg
        self.habits = habits
        self._passes: list[GardenerPass] = passes or _default_passes()
        self._client_factory = client_factory or (lambda model: LLMClient(model))

    # ------------------------------------------------------------------
    # estimate
    # ------------------------------------------------------------------

    def estimate(self) -> CostEstimate:
        out: dict[str, PassEstimate] = {}
        enabled = set(self._enabled_pass_names())
        for p in self._passes:
            if p.name not in enabled:
                continue
            try:
                out[p.name] = p.estimate(self.cfg, self.habits)
            except Exception:  # pragma: no cover - defensive
                out[p.name] = PassEstimate(tokens=0, cost_usd=0.0)
        return CostEstimate(passes=out)

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        dry_run: bool | None = None,
        only: list[str] | None = None,
    ) -> RunResult:
        start = time.monotonic()
        dry = bool(self.habits.gardener.dry_run if dry_run is None else dry_run)
        enabled = set(self._enabled_pass_names())
        if only is not None:
            enabled &= set(only)

        budget = Budget(
            max_cost_usd_per_run=float(self.habits.gardener.max_cost_usd_per_run),
            max_tokens_per_source=int(self.habits.gardener.max_tokens_per_source),
        )

        passes_by_name = {p.name: p for p in self._passes}
        tier_models = self.habits.gardener.models

        passes_run: list[str] = []
        proposals_added = 0
        errors: list[str] = []

        for pass_name in _PASS_ORDER:
            if pass_name not in enabled or pass_name not in passes_by_name:
                continue
            pass_obj = passes_by_name[pass_name]
            model = _resolve_model(tier_models, pass_obj.tier)
            client = None if dry else self._client_factory(model)
            passes_run.append(pass_name)

            autonomous = (
                not dry
                and getattr(self.habits.gardener, "mode", "proposal") == "autonomous"
            )
            try:
                for prop in pass_obj.run(self.cfg, self.habits, client, budget):
                    proposals_added += 1
                    if dry:
                        continue
                    if autonomous:
                        direct_ok, direct_err = _try_direct_write(self.cfg, prop)
                        if direct_ok:
                            audit.append(
                                self.cfg,
                                _audit_entry(prop, accepted=True, direct_write=True),
                            )
                        else:
                            # Fall back to proposal queue on direct-write failure.
                            _append_pending(self.cfg, prop)
                            audit.append(
                                self.cfg,
                                _audit_entry(
                                    prop,
                                    accepted=None,
                                    direct_write=False,
                                    error=direct_err,
                                ),
                            )
                    else:
                        _append_pending(self.cfg, prop)
                        audit.append(self.cfg, _audit_entry(prop, accepted=None))
            except BudgetExceeded as exc:
                errors.append(f"{pass_name}: {exc}")
                break
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(f"{pass_name}: {exc}")

        duration_ms = int((time.monotonic() - start) * 1000)
        result = RunResult(
            passes_run=passes_run,
            proposals_added=proposals_added,
            total_tokens=budget.tokens_spent,
            total_cost_usd=round(budget.spent_usd, 6),
            duration_ms=duration_ms,
            errors=errors,
        )

        if not dry:
            _write_ledger_slot(self.cfg, result)

        return result

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _enabled_pass_names(self) -> list[str]:
        toggles: dict[str, bool] = dict(self.habits.gardener.passes)
        return [name for name in _PASS_ORDER if toggles.get(name, False)]


def _resolve_model(tier_models: dict[str, str], tier: Tier) -> str:
    return tier_models.get(tier) or tier_models.get("default", "")


def _append_pending(cfg: Any, prop: Proposal) -> None:
    path: Path = cfg.digests_dir / "pending.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "id": "",  # applier assigns final id
        "section": prop.section,
        "line": prop.line,
        "action": prop.action,
        "origin": prop.origin,
        "pass": prop.pass_name,
        "input_refs": prop.input_refs,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _audit_entry(
    prop: Proposal,
    *,
    accepted: bool | None,
    direct_write: bool = False,
    error: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "pass": prop.pass_name,
        "section": prop.section,
        "line": prop.line,
        "action": prop.action,
        "input_refs": prop.input_refs,
        "tokens_in": prop.tokens_in,
        "tokens_out": prop.tokens_out,
        "cost_usd": prop.cost_usd,
        "accepted": accepted,
        "direct_write": direct_write,
    }
    if error:
        entry["error"] = error
    return entry


def _try_direct_write(cfg: Any, prop: Proposal) -> tuple[bool, str | None]:
    """Apply a proposal immediately via the digest applier handlers.

    Returns ``(True, None)`` on success, ``(False, error_str)`` otherwise.
    """
    try:
        from second_brain.digest.applier import _HANDLERS  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive import
        return False, f"applier import failed: {exc}"
    action = dict(prop.action)
    action_type = action.get("type")
    handler = _HANDLERS.get(action_type) if action_type else None
    if handler is None:
        return False, f"no handler for action type {action_type!r}"
    try:
        handler(cfg, action)
    except Exception as exc:
        return False, str(exc)
    return True, None


def _write_ledger_slot(cfg: Any, result: RunResult) -> None:
    """Best-effort ledger update; swallowed if ledger module unavailable."""
    try:
        from second_brain.state import pipeline as _pipe  # type: ignore

        _pipe.write_phase(  # type: ignore[attr-defined]
            cfg,
            "gardener",
            {
                "passes_run": result.passes_run,
                "proposals_added": result.proposals_added,
                "total_tokens": result.total_tokens,
                "total_cost_usd": result.total_cost_usd,
                "duration_ms": result.duration_ms,
                "errors": result.errors,
            },
        )
    except Exception:
        # Ledger is optional on the gardener side; backend tool owns the
        # cross-pipeline ledger shape. Skip silently.
        pass
