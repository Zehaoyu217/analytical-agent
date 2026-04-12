from __future__ import annotations

import pytest

from app.skills.base import SkillError
from app.skills.sql_builder.pkg.builder import (
    groupby_counts,
    quote,
    select,
    summary_stats,
)


def test_quote_wraps_identifier() -> None:
    assert quote("age") == '"age"'


def test_quote_rejects_spaces_and_punctuation() -> None:
    with pytest.raises(SkillError):
        quote("age; DROP TABLE")


def test_quote_rejects_leading_digit() -> None:
    with pytest.raises(SkillError):
        quote("1st_col")


def test_quote_rejects_empty_and_non_string() -> None:
    with pytest.raises(SkillError):
        quote("")
    with pytest.raises(SkillError):
        quote(None)  # type: ignore[arg-type]


def test_select_renders_columns_and_limit() -> None:
    sql = select("df", ["a", "b"], limit=10)
    assert sql == 'SELECT "a", "b" FROM "df" LIMIT 10'


def test_select_accepts_where_clause() -> None:
    sql = select("df", ["a"], where='"a" > 5', limit=None)
    assert sql == 'SELECT "a" FROM "df" WHERE "a" > 5'


def test_groupby_counts_orders_desc() -> None:
    sql = groupby_counts("df", "country")
    assert 'GROUP BY "country"' in sql
    assert "ORDER BY cnt DESC" in sql


def test_summary_stats_has_eleven_fields() -> None:
    sql = summary_stats("df", "revenue")
    for token in (
        "count", "nulls", "min(", "max(", "avg(", "stddev(",
        "quantile_cont(\"revenue\", 0.01)",
        "quantile_cont(\"revenue\", 0.95)",
    ):
        assert token in sql
