"""Analytics builder: populates ``.sb/analytics.duckdb`` from graph + filesystem.

The analytics DB is a pure read-only derived artifact. Sources of truth:

- ``cfg.duckdb_path`` — graph DB written by ``sb reindex``.
- ``cfg.sources_dir`` / ``cfg.claims_dir`` — markdown frontmatter on disk.

Schema:

- ``sources_by_kind (kind TEXT, n INT)``
- ``claims_by_taxonomy (taxonomy TEXT, n INT)``
- ``zero_claim_sources (source_id TEXT)``
- ``orphan_claims (claim_id TEXT)``
- ``contradiction_counts (status TEXT, n INT)``

Every ``rebuild()`` deletes the existing DB and rewrites it from scratch —
rebuilds are idempotent.
"""
from __future__ import annotations

import duckdb

from second_brain.config import Config
from second_brain.frontmatter import load_document


class AnalyticsBuilder:
    """Populates ``.sb/analytics.duckdb`` from graph + filesystem state."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def rebuild(self) -> None:
        self.cfg.sb_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg.analytics_path
        if path.exists():
            path.unlink()

        con = duckdb.connect(str(path))
        try:
            self._build_schema(con)
            self._populate_sources(con)
            self._populate_claims(con)
            self._populate_from_graph(con)
        finally:
            con.close()

    # ------------------------------------------------------------------ schema

    def _build_schema(self, con: duckdb.DuckDBPyConnection) -> None:
        con.execute("CREATE TABLE sources_by_kind (kind TEXT, n INT)")
        con.execute("CREATE TABLE claims_by_taxonomy (taxonomy TEXT, n INT)")
        con.execute("CREATE TABLE zero_claim_sources (source_id TEXT)")
        con.execute("CREATE TABLE orphan_claims (claim_id TEXT)")
        con.execute("CREATE TABLE contradiction_counts (status TEXT, n INT)")

    # --------------------------------------------------------------- populate

    def _populate_sources(self, con: duckdb.DuckDBPyConnection) -> None:
        counts: dict[str, int] = {}
        for folder in sorted(self.cfg.sources_dir.glob("*")):
            source_md = folder / "_source.md"
            if not source_md.exists():
                continue
            try:
                fm, _ = load_document(source_md)
            except Exception:  # noqa: BLE001
                continue
            kind = fm.get("kind", "unknown")
            counts[kind] = counts.get(kind, 0) + 1
        for k, n in counts.items():
            con.execute("INSERT INTO sources_by_kind VALUES (?, ?)", [k, n])

    def _populate_claims(self, con: duckdb.DuckDBPyConnection) -> None:
        counts: dict[str, int] = {}
        for claim_md in sorted(self.cfg.claims_dir.glob("*.md")):
            if claim_md.name == "conflicts.md":
                continue
            try:
                fm, _ = load_document(claim_md)
            except Exception:  # noqa: BLE001
                continue
            tax = fm.get("taxonomy") or "unknown"
            counts[tax] = counts.get(tax, 0) + 1
        for t, n in counts.items():
            con.execute("INSERT INTO claims_by_taxonomy VALUES (?, ?)", [t, n])

    def _populate_from_graph(self, con: duckdb.DuckDBPyConnection) -> None:
        graph_path = self.cfg.duckdb_path
        if graph_path.exists():
            con.execute(f"ATTACH '{graph_path}' AS g (READ_ONLY)")
            try:
                con.execute(
                    """
                    INSERT INTO zero_claim_sources
                    SELECT DISTINCT s.id FROM g.sources s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM g.edges e
                        WHERE e.dst_id = s.id
                          AND e.relation IN ('evidenced_by','supports','cites')
                    )
                    """
                )
                con.execute(
                    """
                    INSERT INTO orphan_claims
                    SELECT DISTINCT c.id FROM g.claims c
                    WHERE NOT EXISTS (
                        SELECT 1 FROM g.edges e
                        WHERE e.src_id = c.id AND e.relation = 'evidenced_by'
                    )
                    """
                )
                con.execute(
                    """
                    INSERT INTO contradiction_counts
                    SELECT
                      CASE WHEN COALESCE(rationale, '') = '' THEN 'open' ELSE 'resolved' END
                        AS status,
                      COUNT(*) AS n
                    FROM g.edges
                    WHERE relation = 'contradicts'
                    GROUP BY status
                    """
                )
            finally:
                con.execute("DETACH g")
            return

        # Filesystem fallback: use claim frontmatter to detect references.
        referenced: set[str] = set()
        for claim_md in sorted(self.cfg.claims_dir.glob("*.md")):
            if claim_md.name == "conflicts.md":
                continue
            try:
                fm, _ = load_document(claim_md)
            except Exception:  # noqa: BLE001
                continue
            for rel in ("evidenced_by", "supports", "cites"):
                for entry in fm.get(rel, []) or []:
                    if isinstance(entry, dict):
                        sid = entry.get("id", "")
                        if sid:
                            referenced.add(sid)
                    elif isinstance(entry, str):
                        referenced.add(entry)
        for folder in sorted(self.cfg.sources_dir.glob("*")):
            source_md = folder / "_source.md"
            if not source_md.exists():
                continue
            try:
                fm, _ = load_document(source_md)
            except Exception:  # noqa: BLE001
                continue
            sid = fm.get("id", folder.name)
            if sid not in referenced:
                con.execute("INSERT INTO zero_claim_sources VALUES (?)", [sid])
