"""Reconciliation digest pass.

Inputs:
    - Open contradictions (from lint `UNRESOLVED_CONTRADICTION` issues).
    - Stale low-confidence claims (``status=active``, ``confidence=low``,
      ``extracted_at`` older than ``STALE_LOW_CONF_DAYS``).

For each candidate the pass asks the Anthropic client (or a fake client loaded
from ``SB_DIGEST_FAKE_RECONCILIATION``) to choose one of:

- ``upgrade_confidence``
- ``resolve_contradiction``
- ``keep``

The returned :class:`DigestEntry` ``action`` payloads follow the schemas the
``DigestApplier`` (Batch 2) will dispatch on. Ids are set to ``""`` — the
Builder rewrites them to ``r01, r02, …``.

No Claude call is ever made implicitly. When the fake-client env var is absent
and no real client is supplied the pass raises :class:`DigestPassError` so the
misconfiguration is loud.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry, DigestPassError
from second_brain.lint import run_lint
from second_brain.lint.rules import Severity
from second_brain.lint.snapshot import load_snapshot
from second_brain.schema.claim import ClaimConfidence, ClaimStatus

STALE_LOW_CONF_DAYS = 60
_FAKE_ENV = "SB_DIGEST_FAKE_RECONCILIATION"

_VALID_ACTIONS = frozenset({"upgrade_confidence", "resolve_contradiction", "keep"})


@dataclass(frozen=True)
class _Candidate:
    """One reconciliation target the pass asks the client to decide on."""

    kind: str  # "contradiction" | "low_conf"
    primary_id: str
    secondary_id: str | None  # right side of a contradiction, None otherwise


def _load_fake_response(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DigestPassError(
            f"{_FAKE_ENV}={path} does not exist; provide a canned JSON "
            "for the digest reconciliation pass or unset the env var"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DigestPassError(f"{_FAKE_ENV} JSON at {path} is invalid: {exc}") from exc
    if not isinstance(data, dict) or "entries" not in data:
        raise DigestPassError(
            f"{_FAKE_ENV} JSON at {path} missing top-level 'entries' list"
        )
    entries = data["entries"]
    if not isinstance(entries, list):
        raise DigestPassError(f"{_FAKE_ENV} 'entries' must be a list, got {type(entries).__name__}")
    return data


def _collect_candidates(cfg: Config) -> list[_Candidate]:
    """Union of open contradictions + stale low-confidence claims."""
    report = run_lint(cfg)
    snap = load_snapshot(cfg)

    contradiction_pairs: set[tuple[str, str]] = set()
    for issue in report.issues:
        if issue.rule != "UNRESOLVED_CONTRADICTION":
            continue
        if issue.severity not in (Severity.WARNING, Severity.ERROR):
            continue
        left = issue.subject_id
        # details.contradicts is a list of claim ids
        targets = issue.details.get("contradicts", [])
        if not isinstance(targets, list):
            continue
        for right in targets:
            if not isinstance(right, str):
                continue
            right_id = right.split("#", 1)[0]
            pair = tuple(sorted((left, right_id)))
            contradiction_pairs.add(pair)

    contradictions = [
        _Candidate(kind="contradiction", primary_id=a, secondary_id=b)
        for a, b in sorted(contradiction_pairs)
    ]

    cutoff = datetime.now(UTC) - timedelta(days=STALE_LOW_CONF_DAYS)
    low_conf: list[_Candidate] = []
    for cid, claim in sorted(snap.claims.items()):
        if claim.status != ClaimStatus.ACTIVE:
            continue
        if claim.confidence != ClaimConfidence.LOW:
            continue
        extracted = claim.extracted_at
        if extracted.tzinfo is None:
            extracted = extracted.replace(tzinfo=UTC)
        if extracted > cutoff:
            continue
        low_conf.append(_Candidate(kind="low_conf", primary_id=cid, secondary_id=None))

    return contradictions + low_conf


def _validate_response_entry(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DigestPassError(f"reconciliation response entry not a dict: {raw!r}")
    action = raw.get("action")
    if action not in _VALID_ACTIONS:
        raise DigestPassError(
            f"reconciliation action {action!r} not in {sorted(_VALID_ACTIONS)}"
        )
    target = raw.get("target_id")
    if not isinstance(target, str) or not target:
        raise DigestPassError(f"reconciliation entry missing target_id: {raw!r}")
    rationale = raw.get("rationale", "")
    if not isinstance(rationale, str):
        raise DigestPassError(f"reconciliation rationale must be str: {raw!r}")
    return {"action": action, "target_id": target, "rationale": rationale}


def _entry_for(cand: _Candidate, decision: dict[str, Any]) -> DigestEntry:
    action_name = decision["action"]
    rationale = decision["rationale"]

    if action_name == "resolve_contradiction":
        # Contradictions always carry a secondary; ensure we have one.
        if cand.secondary_id is None:
            raise DigestPassError(
                f"resolve_contradiction chosen for non-contradiction candidate {cand.primary_id}"
            )
        left, right = sorted((cand.primary_id, cand.secondary_id))
        payload: dict[str, Any] = {
            "action": "resolve_contradiction",
            "left_id": left,
            "right_id": right,
            "rationale": rationale,
        }
        line = f"Resolve contradiction {left} vs {right}?"
    elif action_name == "upgrade_confidence":
        payload = {
            "action": "upgrade_confidence",
            "claim_id": cand.primary_id,
            "from": "low",
            "to": "medium",
            "rationale": rationale,
        }
        line = f"Upgrade {cand.primary_id} confidence low→medium?"
    else:  # keep
        payload = {
            "action": "keep",
            "claim_id": cand.primary_id,
            "rationale": rationale,
        }
        line = f"Keep {cand.primary_id} as-is."

    return DigestEntry(id="", section="Reconciliation", line=line, action=payload)


class ReconciliationPass:
    """Digest pass — proposes decisions on contradictions and stale low-conf claims."""

    prefix = "r"
    section = "Reconciliation"

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]:
        candidates = _collect_candidates(cfg)
        if not candidates:
            return []

        fake_path = os.environ.get(_FAKE_ENV)
        if fake_path:
            data = _load_fake_response(Path(fake_path))
            raw_entries = data["entries"]
        elif client is not None:
            raw_entries = _call_real_client(client, candidates)
        else:
            raise DigestPassError(
                f"reconciliation pass has no client and {_FAKE_ENV} is unset; "
                "set the env var to a canned JSON path for tests or pass a real client"
            )

        decisions: dict[str, dict[str, Any]] = {}
        for raw in raw_entries:
            validated = _validate_response_entry(raw)
            decisions[validated["target_id"]] = validated

        out: list[DigestEntry] = []
        for cand in candidates:
            # Contradiction decisions may be keyed by either side — accept both.
            decision = decisions.get(cand.primary_id)
            if decision is None and cand.secondary_id:
                decision = decisions.get(cand.secondary_id)
            if decision is None:
                # Treat missing as "keep" to keep the digest stable.
                decision = {"action": "keep", "target_id": cand.primary_id, "rationale": ""}
            out.append(_entry_for(cand, decision))
        return out


def _call_real_client(client: Any, candidates: list[_Candidate]) -> list[dict[str, Any]]:
    """Placeholder for a real Anthropic client hook.

    The hermetic test path always sets ``SB_DIGEST_FAKE_RECONCILIATION``. A real
    Anthropic tool-use adaptor can be introduced in a later batch; for now we
    delegate to a ``client.reconcile_digest(candidates)`` duck-typed call if the
    method exists, and raise otherwise.
    """
    if not hasattr(client, "reconcile_digest"):
        raise DigestPassError(
            "real client missing reconcile_digest(); supply a fake via "
            f"{_FAKE_ENV} for tests"
        )
    return list(client.reconcile_digest(candidates))
