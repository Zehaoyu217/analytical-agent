"""Typed read-only queries over ``.sb/analytics.duckdb``.

All query functions return concrete lists (never cursors) so callers can use
them without keeping the DB file open. Missing analytics DB -> empty result.
"""
from __future__ import annotations

from collections.abc import Iterable

import duckdb

from second_brain.config import Config


def _connect(cfg: Config) -> duckdb.DuckDBPyConnection | None:
    if not cfg.analytics_path.exists():
        return None
    return duckdb.connect(str(cfg.analytics_path), read_only=True)


def sources_by_kind(cfg: Config) -> Iterable[tuple[str, int]]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return list(con.execute("SELECT kind, n FROM sources_by_kind").fetchall())
    finally:
        con.close()


def claims_by_taxonomy(cfg: Config) -> Iterable[tuple[str, int]]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return list(
            con.execute("SELECT taxonomy, n FROM claims_by_taxonomy").fetchall()
        )
    finally:
        con.close()


def zero_claim_sources(cfg: Config) -> Iterable[str]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return [
            r[0]
            for r in con.execute(
                "SELECT source_id FROM zero_claim_sources"
            ).fetchall()
        ]
    finally:
        con.close()


def orphan_claims(cfg: Config) -> Iterable[str]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return [
            r[0]
            for r in con.execute("SELECT claim_id FROM orphan_claims").fetchall()
        ]
    finally:
        con.close()


def contradiction_counts(cfg: Config) -> Iterable[tuple[str, int]]:
    con = _connect(cfg)
    if con is None:
        return []
    try:
        return list(
            con.execute("SELECT status, n FROM contradiction_counts").fetchall()
        )
    finally:
        con.close()
