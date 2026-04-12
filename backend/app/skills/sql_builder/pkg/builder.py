from __future__ import annotations

import re

from app.skills.base import SkillError

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ERRORS = {
    "NOT_IDENTIFIER": {
        "message": "Identifier '{ident}' is not a safe SQL identifier.",
        "guidance": "Use only letters, digits, and underscore; must not start with a digit.",
        "recovery": "Rename the column or pass it through quote().",
    }
}


def quote(ident: str) -> str:
    if not isinstance(ident, str) or not _IDENT.match(ident):
        raise SkillError("NOT_IDENTIFIER", {"ident": ident}, _ERRORS)
    return f'"{ident}"'


def select(
    table: str,
    columns: list[str],
    where: str | None = None,
    limit: int | None = None,
) -> str:
    # `where` is interpolated raw — callers must pass a trusted SQL fragment
    # (not user input). Quote identifiers inside the fragment via quote().
    cols = ", ".join(quote(c) for c in columns)
    tbl = quote(table)
    sql = f"SELECT {cols} FROM {tbl}"
    if where:
        sql += f" WHERE {where}"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return sql


def groupby_counts(table: str, column: str) -> str:
    col = quote(column)
    tbl = quote(table)
    return (
        f"SELECT {col} AS value, COUNT(*) AS cnt "
        f"FROM {tbl} GROUP BY {col} ORDER BY cnt DESC"
    )


def summary_stats(table: str, column: str) -> str:
    col = quote(column)
    tbl = quote(table)
    return (
        f"SELECT COUNT(*) AS count, "
        f"COUNT(*) - COUNT({col}) AS nulls, "
        f"min({col}) AS min, max({col}) AS max, "
        f"avg({col}) AS mean, stddev({col}) AS stddev, "
        f"quantile_cont({col}, 0.01) AS p01, "
        f"quantile_cont({col}, 0.05) AS p05, "
        f"quantile_cont({col}, 0.50) AS p50, "
        f"quantile_cont({col}, 0.95) AS p95, "
        f"quantile_cont({col}, 0.99) AS p99 "
        f"FROM {tbl}"
    )
