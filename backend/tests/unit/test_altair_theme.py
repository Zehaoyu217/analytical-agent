"""Altair theme contract tests.

Tests pin the public API of the design-token module: ``register_all``,
``use_variant``, and ``active_tokens``.  The module ships a real token
set (terminal dark + editorial light variants); these tests verify the
accessor methods and variant-switching behaviour.
"""
from __future__ import annotations

from config.themes.altair_theme import active_tokens, register_all, use_variant


def test_register_all_is_callable_and_returns_none() -> None:
    assert register_all() is None


def test_use_variant_accepts_any_name() -> None:
    # All known and unknown variant names must not raise.
    assert use_variant("terminal") is None
    assert use_variant("editorial") is None
    assert use_variant("nonexistent") is None
    # Reset to terminal so other tests see the default palette.
    use_variant("terminal")


def test_active_tokens_returns_token_object_with_surface_method() -> None:
    use_variant("terminal")
    tokens = active_tokens()
    # Must expose surface() / semantic() / series_color() methods.
    assert callable(getattr(tokens, "surface", None))
    assert callable(getattr(tokens, "semantic", None))
    assert callable(getattr(tokens, "series_color", None))


def test_terminal_variant_base_is_near_black() -> None:
    use_variant("terminal")
    tokens = active_tokens()
    assert tokens.surface("base") == "#09090b"


def test_editorial_variant_base_is_warm_white() -> None:
    use_variant("editorial")
    tokens = active_tokens()
    assert tokens.surface("base") == "#FBF7EE"
    # Reset
    use_variant("terminal")
