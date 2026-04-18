#!/usr/bin/env python3
"""Graph ↔ wiki drift scan CLI.

Writes ``<repo>/telemetry/drift/YYYY-MM-DD.json`` matching the
telemetry sidecar convention established in Wave B. Resolves
``claims_dir`` + ``wiki_dir`` from either explicit ``--claims-dir`` /
``--wiki-dir`` flags or (when unspecified) the sibling
``second_brain.config.Config`` + ``<repo>/wiki`` fallback.

Exits 0 even when the KB is unavailable — the scan simply writes an
empty report.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date as date_t
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.integrity.drift_scan import scan_drift  # noqa: E402


@dataclass(frozen=True)
class _Cfg:
    claims_dir: Path
    wiki_dir: Path


def _resolve_cfg(
    claims_dir: Path | None,
    wiki_dir: Path | None,
) -> _Cfg:
    if claims_dir and wiki_dir:
        return _Cfg(claims_dir=claims_dir, wiki_dir=wiki_dir)
    # Try the sibling second-brain config.
    sb_claims: Path | None = None
    try:
        from second_brain.config import Config  # type: ignore

        sb_cfg = Config.load()
        sb_claims = Path(sb_cfg.claims_dir)
    except Exception:  # noqa: BLE001
        sb_claims = None
    wiki_default = REPO_ROOT / "wiki"
    knowledge_wiki = REPO_ROOT / "knowledge" / "wiki"
    if not wiki_default.exists() and knowledge_wiki.exists():
        wiki_default = knowledge_wiki
    return _Cfg(
        claims_dir=claims_dir or sb_claims or (REPO_ROOT / "claims"),
        wiki_dir=wiki_dir or wiki_default,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="sb-drift-scan")
    p.add_argument("--claims-dir", type=Path, default=None)
    p.add_argument("--wiki-dir", type=Path, default=None)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "telemetry" / "drift",
        help="Directory to write the YYYY-MM-DD.json snapshot into.",
    )
    p.add_argument("--date", type=str, default=None, help="Override YYYY-MM-DD filename.")
    p.add_argument(
        "--stale-threshold-days",
        type=int,
        default=30,
        help="Flag claims older than wiki page by N days (default: 30).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    cfg = _resolve_cfg(args.claims_dir, args.wiki_dir)
    report = scan_drift(cfg, stale_threshold_days=args.stale_threshold_days)

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    day = args.date or date_t.today().isoformat()
    target = out_dir / f"{day}.json"
    target.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    # Echo a one-line summary so the CLI is useful interactively too.
    print(f"drift: total={report.total} by_kind={report.by_kind} → {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
