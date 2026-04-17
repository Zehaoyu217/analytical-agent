from __future__ import annotations
import ast

from backend.app.integrity.plugins.graph_extension.extractors._ast_helpers import (
    extract_kw_str,
    name_of,
)


def test_name_of_simple_name() -> None:
    tree = ast.parse("foo")
    assert name_of(tree.body[0].value) == "foo"


def test_name_of_attribute() -> None:
    tree = ast.parse("router.get")
    assert name_of(tree.body[0].value) == "router.get"


def test_name_of_returns_none_for_subscript() -> None:
    tree = ast.parse("Components[k]")
    assert name_of(tree.body[0].value) is None


def test_extract_kw_str_finds_string_kwarg() -> None:
    tree = ast.parse("APIRouter(prefix='/foo', tags=['x'])")
    call = tree.body[0].value
    assert extract_kw_str(call, "prefix") == "/foo"


def test_extract_kw_str_returns_none_when_missing() -> None:
    tree = ast.parse("APIRouter()")
    call = tree.body[0].value
    assert extract_kw_str(call, "prefix") is None


def test_extract_kw_str_returns_none_for_non_string() -> None:
    tree = ast.parse("APIRouter(prefix=variable)")
    call = tree.body[0].value
    assert extract_kw_str(call, "prefix") is None
