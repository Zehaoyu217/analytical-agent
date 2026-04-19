"""Graph ↔ wiki drift detection.

Scans a second-brain-shaped `claims_dir` + `wiki_dir` pair and flags
three kinds of drift:

- ``orphan_claim``      — claim frontmatter references a missing wiki page.
- ``orphan_backlink``   — wiki page backlinks a non-existent claim id.
- ``stale_claim``       — claim's ``updated_at`` is older than the
  referenced wiki page by more than ``stale_threshold_days``.

The scanner inspects the filesystem only. When either directory is
missing (or the sibling KB is not installed) the function degrades
gracefully: ``DriftReport(total=0, findings=[])``.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


class _CfgLike(Protocol):
    claims_dir: Path
    wiki_dir: Path


DEFAULT_STALE_THRESHOLD_DAYS = 30


@dataclass(frozen=True)
class DriftFinding:
    """A single drift event."""

    kind: str  # "orphan_claim" | "orphan_backlink" | "stale_claim"
    subject_id: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DriftReport:
    """Aggregated drift-scan output."""

    timestamp: str
    total: int
    by_kind: dict[str, int]
    findings: list[DriftFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total": self.total,
            "by_kind": dict(self.by_kind),
            "findings": [
                {"kind": f.kind, "subject_id": f.subject_id, "detail": dict(f.detail)}
                for f in self.findings
            ],
        }


# ── Frontmatter parsing (minimal, no PyYAML dep) ────────────────────


def _read_frontmatter(path: Path) -> dict[str, Any]:
    """Return the YAML frontmatter of ``path`` as a dict.

    Very small hand-rolled parser — supports scalar ``key: value`` and
    ``key:\n  - item`` list form. Non-trivial frontmatter falls back to
    whatever :mod:`yaml` yields when available. Returns ``{}`` on any
    failure rather than raising.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    # Split after the second ``---`` line.
    parts = text.split("\n")
    if parts[0].strip() != "---":
        return {}
    body_lines: list[str] = []
    for i in range(1, len(parts)):
        if parts[i].strip() == "---":
            body_lines = parts[1:i]
            break
    else:
        return {}

    # Try PyYAML first for robust parsing.
    try:
        import yaml as _yaml

        loaded = _yaml.safe_load("\n".join(body_lines))
        if isinstance(loaded, dict):
            return loaded
    except Exception:  # noqa: BLE001
        pass

    # Fallback parser
    result: dict[str, Any] = {}
    current_list: list[str] | None = None
    for line in body_lines:
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list is not None:
            current_list.append(line[4:].strip())
            continue
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                current_list = []
                result[key] = current_list
            else:
                result[key] = val
                current_list = None
    return result


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        txt = value.strip().rstrip("Z")
        try:
            dt = datetime.fromisoformat(txt)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


# ── Main scan ───────────────────────────────────────────────────────


def _iter_md(path: Path) -> Iterable[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(path.rglob("*.md"))


def scan_drift(
    cfg: _CfgLike,
    *,
    stale_threshold_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
) -> DriftReport:
    """Run a drift scan against ``cfg``.

    Never raises — returns an empty report on any IO failure.
    """
    timestamp = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")

    try:
        claims_dir = Path(getattr(cfg, "claims_dir", ""))
        wiki_dir = Path(getattr(cfg, "wiki_dir", ""))
    except Exception:  # noqa: BLE001
        return DriftReport(timestamp=timestamp, total=0, by_kind={}, findings=[])

    # Collect claims: map claim_id → (path, frontmatter)
    claims: dict[str, dict[str, Any]] = {}
    for md in _iter_md(claims_dir):
        fm = _read_frontmatter(md)
        if not fm:
            continue
        cid = fm.get("id") or md.stem
        if not isinstance(cid, str):
            continue
        claims[cid] = {"path": md, "fm": fm}

    # Collect wiki: map rel path (str) → (path, frontmatter, backlinks)
    wiki_pages: dict[str, dict[str, Any]] = {}
    wiki_backlinks: list[tuple[str, Path]] = []  # (claim_id, wiki_path)
    if wiki_dir.exists() and wiki_dir.is_dir():
        for md in _iter_md(wiki_dir):
            rel = md.relative_to(wiki_dir).as_posix()
            fm = _read_frontmatter(md)
            wiki_pages[rel] = {"path": md, "fm": fm}
            bl = fm.get("backlinks")
            if isinstance(bl, list):
                for b in bl:
                    if isinstance(b, str) and b.strip():
                        wiki_backlinks.append((b.strip(), md))

    findings: list[DriftFinding] = []

    # Rule 1: orphan_claim — wiki_path missing
    for cid, info in claims.items():
        fm = info["fm"]
        wp = fm.get("wiki_path")
        if not isinstance(wp, str) or not wp.strip():
            continue
        rel = wp.strip()
        if rel not in wiki_pages:
            findings.append(
                DriftFinding(
                    kind="orphan_claim",
                    subject_id=cid,
                    detail={"wiki_path": rel, "claim_path": str(info["path"])},
                )
            )

    # Rule 2: orphan_backlink — backlink claim_id missing
    for cid, wiki_path in wiki_backlinks:
        if cid not in claims:
            findings.append(
                DriftFinding(
                    kind="orphan_backlink",
                    subject_id=cid,
                    detail={"wiki_path": str(wiki_path)},
                )
            )

    # Rule 3: stale_claim — claim older than referenced wiki page
    threshold_delta = stale_threshold_days
    for cid, info in claims.items():
        fm = info["fm"]
        wp = fm.get("wiki_path")
        if not isinstance(wp, str) or wp not in wiki_pages:
            continue
        claim_ts = _parse_timestamp(fm.get("updated_at"))
        wiki_ts = _parse_timestamp(wiki_pages[wp]["fm"].get("updated_at"))
        if claim_ts is None or wiki_ts is None:
            continue
        delta_days = (wiki_ts - claim_ts).days
        if delta_days > threshold_delta:
            findings.append(
                DriftFinding(
                    kind="stale_claim",
                    subject_id=cid,
                    detail={
                        "wiki_path": wp,
                        "delta_days": delta_days,
                        "claim_updated_at": fm.get("updated_at"),
                        "wiki_updated_at": wiki_pages[wp]["fm"].get("updated_at"),
                    },
                )
            )

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1

    return DriftReport(
        timestamp=timestamp,
        total=len(findings),
        by_kind=by_kind,
        findings=findings,
    )
