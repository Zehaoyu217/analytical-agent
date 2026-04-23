"""DigestApplier — replay the actions.jsonl sidecar to mutate the KB.

The Applier reads ``digests/YYYY-MM-DD.actions.jsonl``, dispatches each entry
to a per-action handler, and records results in
``digests/YYYY-MM-DD.applied.jsonl``.

Failure is per-entry: a handler that raises does not abort the batch — the
failure is reported in ``ApplyResult.failed`` and other entries continue.

Handler coverage (matches the 8 action types emitted by the 5 passes):

- ``upgrade_confidence``     — bump claim frontmatter ``confidence``.
- ``resolve_contradiction``  — write a ``claims/resolutions/<a>__vs__<b>.md``.
- ``keep``                   — no-op, marked applied.
- ``promote_wiki_to_claim``  — create a stub claim file with the wiki ref.
- ``backlink_claim_to_wiki`` — append a backlink line to the wiki file.
- ``add_taxonomy_root``      — append a root to ``habits.taxonomy.roots``.
- ``re_abstract_batch``      — set ``needs_reabstract: true`` on claims.
- ``drop_edge``              — remove one target id from a relation list.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, date as date_t
from pathlib import Path
from typing import Any, Literal

from second_brain.config import Config
from second_brain.frontmatter import dump_document, load_document
from second_brain.habits import Habits
from second_brain.habits.loader import load_habits, save_habits

EntryIds = list[str] | Literal["all"]


@dataclass(frozen=True)
class ApplyResult:
    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


class DigestApplier:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    # ---- public API -------------------------------------------------------

    def apply(self, *, digest_date: date_t, entry_ids: EntryIds) -> ApplyResult:
        sidecar = self.cfg.digests_dir / f"{digest_date.isoformat()}.actions.jsonl"
        if not sidecar.exists():
            return ApplyResult()

        applied: list[str] = []
        skipped: list[str] = []
        failed: list[tuple[str, str]] = []

        rows = _read_sidecar(sidecar)
        target_set = None if entry_ids == "all" else set(entry_ids)

        applied_sidecar = self.cfg.digests_dir / f"{digest_date.isoformat()}.applied.jsonl"
        applied_sidecar.parent.mkdir(parents=True, exist_ok=True)

        for row in rows:
            eid = row.get("id", "")
            action = row.get("action", {}) or {}
            if target_set is not None and eid not in target_set:
                skipped.append(eid)
                continue
            try:
                self._dispatch(action)
            except Exception as exc:  # noqa: BLE001 — per-entry isolation is by design
                failed.append((eid, str(exc)))
                continue
            applied.append(eid)
            _append_applied(applied_sidecar, eid, action)

        return ApplyResult(applied=applied, skipped=skipped, failed=failed)

    # ---- dispatch ---------------------------------------------------------

    def _dispatch(self, action: dict[str, Any]) -> None:
        name = action.get("action")
        handler = _HANDLERS.get(name or "")
        if handler is None:
            raise ValueError(f"unknown digest action: {name!r}")
        handler(self.cfg, action)


# ---- io helpers -----------------------------------------------------------


def _read_sidecar(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _append_applied(path: Path, entry_id: str, action: dict[str, Any]) -> None:
    now = datetime.now(UTC).isoformat()
    row = {"id": entry_id, "applied_at": now, "action": action}
    line = json.dumps(row, sort_keys=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _load_claim(cfg: Config, claim_id: str) -> tuple[Path, dict[str, Any], str]:
    path = cfg.claims_dir / f"{claim_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"claim not found: {claim_id}")
    fm, body = load_document(path)
    return path, fm, body


# ---- handlers -------------------------------------------------------------


def _handle_upgrade_confidence(cfg: Config, action: dict[str, Any]) -> None:
    claim_id = action["claim_id"]
    to = action.get("to") or "medium"
    path, fm, body = _load_claim(cfg, claim_id)
    fm["confidence"] = to
    dump_document(path, fm, body)


def _handle_keep(_cfg: Config, _action: dict[str, Any]) -> None:
    return None


def _handle_resolve_contradiction(cfg: Config, action: dict[str, Any]) -> None:
    left = action["left_id"]
    right = action["right_id"]
    rationale = action.get("rationale", "")
    out_dir = cfg.claims_dir / "resolutions"
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{left}__vs__{right}.md"
    body = (
        f"# Contradiction: {left} vs {right}\n\n"
        f"Rationale: {rationale}\n"
    )
    dst.write_text(body, encoding="utf-8")


def _handle_promote_wiki_to_claim(cfg: Config, action: dict[str, Any]) -> None:
    wiki_path = action["wiki_path"]
    taxonomy = action.get("proposed_taxonomy", "")
    suggested = action.get("suggested_claim_id") or f"clm_{uuid.uuid4().hex[:8]}"
    dst = cfg.claims_dir / f"{suggested}.md"
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fm = {
        "id": suggested,
        "statement": f"Promoted from wiki: {wiki_path}",
        "kind": "empirical",
        "confidence": "low",
        "scope": "",
        "supports": [],
        "contradicts": [],
        "refines": [],
        "extracted_at": now,
        "status": "active",
        "resolution": None,
        "abstract": "",
    }
    if taxonomy:
        fm["taxonomy"] = taxonomy
    body = f"Promoted from wiki path: {wiki_path}\n"
    dump_document(dst, fm, body)


def _handle_backlink_claim_to_wiki(cfg: Config, action: dict[str, Any]) -> None:
    claim_id = action["claim_id"]
    rel_path = action["wiki_path"]
    wiki_dir = os.environ.get("SB_WIKI_DIR", "").strip()
    if not wiki_dir:
        raise RuntimeError("SB_WIKI_DIR not set; cannot backlink")
    wiki_file = Path(wiki_dir).expanduser() / rel_path
    if not wiki_file.exists():
        raise FileNotFoundError(f"wiki file not found: {wiki_file}")
    line = f"\nRelated claim: {claim_id}\n"
    with wiki_file.open("a", encoding="utf-8") as fh:
        fh.write(line)


def _handle_add_taxonomy_root(cfg: Config, action: dict[str, Any]) -> None:
    root = action["root"]
    habits = load_habits(cfg)
    existing = list(habits.taxonomy.roots)
    if root in existing:
        return
    existing.append(root)
    new_taxonomy = habits.taxonomy.model_copy(update={"roots": existing})
    new_habits = habits.model_copy(update={"taxonomy": new_taxonomy})
    save_habits(cfg, new_habits)


def _handle_re_abstract_batch(cfg: Config, action: dict[str, Any]) -> None:
    claim_ids = action.get("claim_ids") or []
    if not isinstance(claim_ids, list):
        raise ValueError("re_abstract_batch.claim_ids must be a list")
    for cid in claim_ids:
        if not isinstance(cid, str):
            continue
        path, fm, body = _load_claim(cfg, cid)
        fm["needs_reabstract"] = True
        dump_document(path, fm, body)


def _handle_drop_edge(cfg: Config, action: dict[str, Any]) -> None:
    src = action["src_id"]
    dst = action["dst_id"]
    relation = action["relation"]
    path, fm, body = _load_claim(cfg, src)
    current = fm.get(relation)
    if not isinstance(current, list):
        return
    new_list = [t for t in current if t.split("#", 1)[0] != dst]
    fm[relation] = new_list
    dump_document(path, fm, body)


_HANDLERS: dict[str, Any] = {
    "upgrade_confidence": _handle_upgrade_confidence,
    "keep": _handle_keep,
    "resolve_contradiction": _handle_resolve_contradiction,
    "promote_wiki_to_claim": _handle_promote_wiki_to_claim,
    "backlink_claim_to_wiki": _handle_backlink_claim_to_wiki,
    "add_taxonomy_root": _handle_add_taxonomy_root,
    "re_abstract_batch": _handle_re_abstract_batch,
    "drop_edge": _handle_drop_edge,
}
