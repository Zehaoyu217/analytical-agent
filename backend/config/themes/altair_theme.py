"""Design token provider for chart and report theming.

Implements the Swiss/Terminal aesthetic: near-black backgrounds, orange accent
(#e0733a), monospace personality. All values are hardcoded defaults — a full
implementation would load from a YAML config.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ── Stroke descriptor ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StrokeStyle:
    width: float
    dash: list[int] | None = None


# ── Token object ──────────────────────────────────────────────────────────────


_SERIES_COLORS: dict[str, str] = {
    "primary":   "#e0733a",  # brand orange — actual / primary series
    "actual":    "#e0733a",
    "secondary": "#6b9eca",  # muted blue
    "forecast":  "#8b6bca",  # violet — future projection
    "upper":     "#4a6fa5",
    "lower":     "#4a6fa5",
    "residual":  "#888888",
}

_SERIES_STROKES: dict[str, StrokeStyle] = {
    "primary":   StrokeStyle(width=2.0),
    "actual":    StrokeStyle(width=2.0),
    "secondary": StrokeStyle(width=1.5),
    "forecast":  StrokeStyle(width=1.5, dash=[4, 3]),
    "upper":     StrokeStyle(width=1.0, dash=[2, 2]),
    "lower":     StrokeStyle(width=1.0, dash=[2, 2]),
    "residual":  StrokeStyle(width=1.0),
}

_TERMINAL_SURFACE_TOKENS: dict[str, str] = {
    "base":       "#09090b",
    "elevated":   "#18181b",
    "border":     "#2a2a2e",
    "text":       "#e0e0e0",
    "text_muted": "#71717a",
    "accent":     "#e0733a",
}

# Editorial variant — warm off-white for HTML report output
_EDITORIAL_SURFACE_TOKENS: dict[str, str] = {
    "base":       "#FBF7EE",
    "elevated":   "#FDFAF3",
    "border":     "#E2D9C6",
    "text":       "#1A1A1A",
    "text_muted": "#6B6455",
    "accent":     "#e0733a",
}

# Alias used by callers that don't specify a variant
_SURFACE_TOKENS = _TERMINAL_SURFACE_TOKENS

_SEMANTIC_TOKENS: dict[str, str] = {
    "positive": "#4caf7d",
    "negative": "#e05252",
    "warning":  "#e0933a",
    "info":     "#3a90e0",
    "neutral":  "#888888",
}

_DIVERGING_TOKENS: dict[str, str] = {
    "negative": _SEMANTIC_TOKENS["negative"],
    "neutral":  _SEMANTIC_TOKENS["neutral"],
    "positive": _SEMANTIC_TOKENS["positive"],
}

_VARIANT_SURFACE_MAP: dict[str, dict[str, str]] = {
    "terminal": _TERMINAL_SURFACE_TOKENS,
    "editorial": _EDITORIAL_SURFACE_TOKENS,
}


class _DesignTokens:
    """Design token accessor for chart and HTML report rendering."""

    def __init__(self, surface_tokens: dict[str, str] | None = None) -> None:
        self._surface = surface_tokens if surface_tokens is not None else _SURFACE_TOKENS

    def series_color(self, role: str) -> str:
        if role not in _SERIES_COLORS:
            raise KeyError(role)
        return _SERIES_COLORS[role]

    def series_stroke(self, role: str) -> StrokeStyle:
        if role not in _SERIES_STROKES:
            raise KeyError(role)
        return _SERIES_STROKES[role]

    def diverging(self) -> dict[str, str]:
        return dict(_DIVERGING_TOKENS)

    def surface(self, key: str) -> str:
        return self._surface.get(key, "#888888")

    def semantic(self, key: str) -> str:
        return _SEMANTIC_TOKENS.get(key, "#888888")


_TOKENS = _DesignTokens()
_active_variant: str = "terminal"


# ── Public API ────────────────────────────────────────────────────────────────


def register_all() -> None:
    """Register Altair themes.  No-op in stub — charts use default theme."""


def use_variant(name: str) -> None:
    """Switch active theme variant."""
    global _TOKENS, _active_variant
    surface = _VARIANT_SURFACE_MAP.get(name, _TERMINAL_SURFACE_TOKENS)
    _TOKENS = _DesignTokens(surface_tokens=surface)
    _active_variant = name


def active_tokens() -> _DesignTokens:
    """Return the active design token set."""
    return _TOKENS
