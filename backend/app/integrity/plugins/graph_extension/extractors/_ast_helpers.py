from __future__ import annotations

import ast


def name_of(node: ast.AST | None) -> str | None:
    """Resolve `Name` or dotted `Attribute` chains to a string. Else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = name_of(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def extract_kw_str(call: ast.Call, key: str) -> str | None:
    """Return string value of `key=` kwarg, or None if missing/non-string."""
    for kw in call.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None
