"""MaintainRunner — nightly pipeline: lint + contradictions + compact + stale scan."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_t, datetime
from typing import Any

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.lint.runner import run_lint
from second_brain.log import EventKind, append_event
from second_brain.maintain.compact import compact_duckdb, compact_fts
from second_brain.store.duckdb_store import DuckStore

_STALE_BODY_MIN_CHARS = 200


@dataclass(frozen=True)
class MaintainReport:
    lint_counts: dict[str, int] = field(default_factory=dict)
    open_contradictions: int = 0
    stale_abstracts: list[str] = field(default_factory=list)
    fts_bytes_before: int = 0
    fts_bytes_after: int = 0
    duck_bytes_before: int = 0
    duck_bytes_after: int = 0
    analytics_rebuilt: bool = False
    habit_proposals: int = 0
    digest_entries: int = 0
    digest_path: str | None = None


class MaintainRunner:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def run(
        self,
        *,
        build_digest: bool = False,
        digest_passes: list[Any] | None = None,
        digest_client: Any | None = None,
        digest_date: date_t | None = None,
    ) -> MaintainReport:
        from second_brain.analytics.builder import AnalyticsBuilder
        from second_brain.habits.learning import detect_overrides, write_proposal

        lint_report = run_lint(self.cfg)
        lint_counts = dict(lint_report.counts_by_severity)

        open_contradictions = self._count_open_contradictions()

        AnalyticsBuilder(self.cfg).rebuild()
        analytics_rebuilt = True

        proposals = detect_overrides(self.cfg, window_days=60, threshold=3)
        for p in proposals:
            write_proposal(p, self.cfg)
        habit_proposals = len(proposals)

        fts = compact_fts(self.cfg)
        duck = compact_duckdb(self.cfg)
        stale = self._stale_abstracts()

        digest_entries = 0
        digest_path: str | None = None
        if build_digest:
            digest_entries, digest_path = self._build_digest(
                passes=digest_passes, client=digest_client, today=digest_date
            )

        report = MaintainReport(
            lint_counts=lint_counts,
            open_contradictions=open_contradictions,
            stale_abstracts=stale,
            fts_bytes_before=fts.before,
            fts_bytes_after=fts.after,
            duck_bytes_before=duck.before,
            duck_bytes_after=duck.after,
            analytics_rebuilt=analytics_rebuilt,
            habit_proposals=habit_proposals,
            digest_entries=digest_entries,
            digest_path=digest_path,
        )
        append_event(
            kind=EventKind.MAINTAIN,
            op="maintain.run",
            subject="pipeline",
            value=(
                f"lint={sum(lint_counts.values())} "
                f"contradictions={open_contradictions} "
                f"stale={len(stale)} "
                f"habits={habit_proposals}"
            ),
            reason={
                "lint": lint_counts,
                "stale_count": len(stale),
                "habit_proposals": habit_proposals,
                "analytics_rebuilt": analytics_rebuilt,
            },
            home=self.cfg.home,
        )
        return report

    def _count_open_contradictions(self) -> int:
        if not self.cfg.duckdb_path.exists():
            return 0
        with DuckStore.open(self.cfg.duckdb_path) as store:
            # "edges" table may not exist on fresh DBs — guard via information_schema.
            tables = {
                r[0]
                for r in store.conn.execute(
                    "SELECT table_name FROM information_schema.tables"
                ).fetchall()
            }
            if "edges" not in tables:
                return 0
            row = store.conn.execute(
                "SELECT COUNT(*) FROM edges WHERE relation = 'contradicts'"
            ).fetchone()
        return int(row[0]) if row else 0

    def _stale_abstracts(self) -> list[str]:
        if not self.cfg.claims_dir.exists():
            return []
        stale: list[str] = []
        for claim_path in self.cfg.claims_dir.glob("*.md"):
            if claim_path.name == "conflicts.md":
                continue
            try:
                fm, body = load_document(claim_path)
            except Exception:  # noqa: BLE001 — skip unparseable claim files
                continue
            abstract = (fm.get("abstract") or "").strip()
            if not abstract and len(body) >= _STALE_BODY_MIN_CHARS:
                stale.append(fm.get("id") or claim_path.stem)
        return sorted(stale)

    def _build_digest(
        self,
        *,
        passes: list[Any] | None,
        client: Any | None,
        today: date_t | None,
    ) -> tuple[int, str | None]:
        from second_brain.digest.builder import DigestBuilder
        from second_brain.habits.loader import load_habits

        habits = load_habits(self.cfg)
        if not habits.digest.enabled:
            return 0, None

        d = today or datetime.now().date()
        builder = DigestBuilder(self.cfg, habits=habits, client=client, passes=passes)
        result = builder.build(today=d)
        if not result.entries:
            return 0, None

        self.cfg.digests_dir.mkdir(parents=True, exist_ok=True)
        md_path = self.cfg.digests_dir / f"{d.isoformat()}.md"
        jsonl_path = self.cfg.digests_dir / f"{d.isoformat()}.actions.jsonl"
        md_path.write_text(result.markdown, encoding="utf-8")
        jsonl_path.write_text(result.actions_jsonl, encoding="utf-8")
        return len(result.entries), str(md_path)
