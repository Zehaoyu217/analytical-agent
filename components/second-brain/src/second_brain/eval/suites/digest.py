"""Digest eval suite: hermetic golden comparison for each of the 5 passes.

For every pass (``reconciliation``, ``wiki_bridge``, ``taxonomy_drift``,
``stale_review``, ``edge_audit``) the suite:

1. Loads ``<fixtures_dir>/<pass>/input.yaml`` — a small spec of claims (and
   optional wiki/source rows) that seed a tmp KB.
2. Sets the pass's ``SB_DIGEST_FAKE_<PASS>`` env var to
   ``<fixtures_dir>/<pass>/fake_response.json`` when the file exists.
3. Runs the pass against the seeded KB, collecting ``DigestEntry.action``
   dicts.
4. Compares the collected actions against ``expected.yaml``'s ``actions``
   list. Matching is order-insensitive, keyed on a canonical JSON dump.

Each pass yields one :class:`EvalCase` — passed iff the produced action set
equals the expected action set. Precision / recall are surfaced in
``details``.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.digest.passes.edge_audit import EdgeAuditPass
from second_brain.digest.passes.reconciliation import ReconciliationPass
from second_brain.digest.passes.stale_review import StaleReviewPass
from second_brain.digest.passes.taxonomy_drift import TaxonomyDriftPass
from second_brain.digest.passes.wiki_bridge import WikiBridgePass
from second_brain.eval.runner import EvalCase

_yaml = YAML(typ="safe")

PASS_NAMES: tuple[str, ...] = (
    "reconciliation",
    "wiki_bridge",
    "taxonomy_drift",
    "stale_review",
    "edge_audit",
)

_PASS_FACTORIES = {
    "reconciliation": ReconciliationPass,
    "wiki_bridge": WikiBridgePass,
    "taxonomy_drift": TaxonomyDriftPass,
    "stale_review": StaleReviewPass,
    "edge_audit": EdgeAuditPass,
}

_FAKE_ENV = {
    "reconciliation": "SB_DIGEST_FAKE_RECONCILIATION",
}


@dataclass(frozen=True)
class _PassOutcome:
    """One-pass comparison outcome."""

    pass_name: str
    generated: int
    expected: int
    true_positives: int

    @property
    def precision(self) -> float:
        return self.true_positives / self.generated if self.generated else 0.0

    @property
    def recall(self) -> float:
        return self.true_positives / self.expected if self.expected else 1.0

    @property
    def passed(self) -> bool:
        return self.generated == self.expected == self.true_positives


def default_fixtures_dir() -> Path:
    """Fixtures bundled with the package (tests import the same files)."""
    return Path(__file__).with_name("digest_fixtures")


def run_digest_suite(
    fixtures_dir: Path | None = None,
    pass_filter: str | None = None,
) -> list[_PassOutcome]:
    """Run the per-pass golden comparison and return outcomes."""
    fixtures_dir = fixtures_dir or default_fixtures_dir()
    names = [pass_filter] if pass_filter else list(PASS_NAMES)
    outcomes: list[_PassOutcome] = []
    for name in names:
        if name not in _PASS_FACTORIES:
            raise KeyError(f"unknown digest pass: {name}")
        outcomes.append(_run_one_pass(name, fixtures_dir))
    return outcomes


class DigestSuite:
    """Adapter for the generic EvalRunner Protocol."""

    name = "digest"

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        outcomes = run_digest_suite(fixtures_dir)
        cases: list[EvalCase] = []
        for o in outcomes:
            cases.append(
                EvalCase(
                    name=o.pass_name,
                    passed=o.passed,
                    metric=o.recall,
                    details=(
                        f"generated={o.generated} expected={o.expected} "
                        f"tp={o.true_positives} "
                        f"precision={o.precision:.2f} recall={o.recall:.2f}"
                    ),
                )
            )
        return cases


# ---- internals ------------------------------------------------------------


def _run_one_pass(name: str, fixtures_dir: Path) -> _PassOutcome:
    base = fixtures_dir / name
    input_spec = _yaml.load((base / "input.yaml").read_text(encoding="utf-8")) or {}
    expected_spec = _yaml.load((base / "expected.yaml").read_text(encoding="utf-8")) or {}
    expected_actions: list[dict[str, Any]] = list(expected_spec.get("actions", []))

    tmp_root = Path(tempfile.mkdtemp(prefix="sb-digest-eval-"))
    try:
        cfg = _seed_kb(tmp_root, input_spec)
        env_overrides = _prepare_env(name, base, input_spec, tmp_root)
        generated = _run_pass_capture(name, cfg, env_overrides)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    gen_keys = [_canonical(a) for a in generated]
    exp_keys = [_canonical(a) for a in expected_actions]
    tp = _multiset_intersection_count(gen_keys, exp_keys)
    return _PassOutcome(
        pass_name=name,
        generated=len(generated),
        expected=len(expected_actions),
        true_positives=tp,
    )


def _canonical(action: dict[str, Any]) -> str:
    return json.dumps(action, sort_keys=True, default=str)


def _multiset_intersection_count(a: list[str], b: list[str]) -> int:
    rem = list(b)
    hits = 0
    for x in a:
        if x in rem:
            rem.remove(x)
            hits += 1
    return hits


def _seed_kb(tmp_root: Path, spec: dict[str, Any]) -> Config:
    home = tmp_root / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    (home / "sources").mkdir()
    (home / "digests").mkdir()
    cfg = Config(home=home, sb_dir=home / ".sb")

    for src in spec.get("sources", []) or []:
        src_id = src["id"]
        src_dir = cfg.sources_dir / src_id
        src_dir.mkdir()
        tax = src.get("habit_taxonomy", "")
        (src_dir / "_source.md").write_text(
            "---\n"
            f"id: {src_id}\n"
            f"title: 'fixture source {src_id}'\n"
            f"kind: {src.get('kind', 'pdf')}\n"
            "ingested_at: '2026-01-01T00:00:00Z'\n"
            f"content_hash: {src_id}_hash\n"
            f"habit_taxonomy: {tax}\n"
            "---\n",
            encoding="utf-8",
        )

    now = datetime.now(UTC)
    for clm in spec.get("claims", []) or []:
        cid = clm["id"]
        extracted = now - timedelta(days=int(clm.get("extracted_at_days_ago", 1)))
        lines = [
            "---",
            f"id: {cid}",
            f"statement: 'stmt for {cid}'",
            f"kind: {clm.get('kind', 'empirical')}",
            f"confidence: {clm.get('confidence', 'high')}",
            "scope: ''",
            f"contradicts: {clm.get('contradicts', [])}",
            f"supports: {clm.get('supports', [])}",
            f"refines: {clm.get('refines', [])}",
            f"extracted_at: {extracted.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"status: {clm.get('status', 'active')}",
            f"resolution: {clm.get('resolution', 'null')}",
            f"abstract: '{clm.get('abstract', '')}'",
        ]
        if "taxonomy" in clm:
            lines.append(f"taxonomy: {clm['taxonomy']}")
        lines += ["---", ""]
        path = cfg.claims_dir / f"{cid}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        mtime_days = clm.get("mtime_days_ago")
        if mtime_days is not None:
            ts = (now - timedelta(days=int(mtime_days))).timestamp()
            os.utime(path, (ts, ts))
    return cfg


def _prepare_env(
    pass_name: str, base: Path, spec: dict[str, Any], tmp_root: Path
) -> dict[str, str]:
    env: dict[str, str] = {}
    fake_file = base / "fake_response.json"
    env_var = _FAKE_ENV.get(pass_name)
    if env_var and fake_file.exists():
        env[env_var] = str(fake_file)

    wiki_entries = spec.get("wiki") or []
    if wiki_entries:
        wiki_dir = tmp_root / "wiki"
        wiki_dir.mkdir()
        for item in wiki_entries:
            path = wiki_dir / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            body = item.get("body", "")
            status = item.get("status", "mature")
            tax = item.get("taxonomy", "")
            tax_line = f"taxonomy: {tax}\n" if tax else ""
            path.write_text(
                f"---\nstatus: {status}\n{tax_line}---\n{body}\n",
                encoding="utf-8",
            )
        env["SB_WIKI_DIR"] = str(wiki_dir)
    return env


def _run_pass_capture(
    pass_name: str, cfg: Config, env: dict[str, str]
) -> list[dict[str, Any]]:
    """Run a pass with env overrides, returning the action dicts."""
    pass_inst = _PASS_FACTORIES[pass_name]()
    saved = {k: os.environ.get(k) for k in env}
    for k, v in env.items():
        os.environ[k] = v
    try:
        entries = pass_inst.run(cfg, client=None)
    finally:
        for k, old in saved.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old
    return [e.action for e in entries]
