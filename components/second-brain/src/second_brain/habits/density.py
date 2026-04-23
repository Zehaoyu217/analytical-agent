from __future__ import annotations

from second_brain.habits.schema import Density, Habits


def _prefix_match(pattern: str, taxonomy: str) -> bool:
    # Pattern is a glob-like prefix ending in /* — we match on path segments,
    # not raw substrings, so "blog/*" does NOT match "blog-archive/x".
    if pattern.endswith("/*"):
        base = pattern[:-2]
        return taxonomy == base or taxonomy.startswith(base + "/")
    return taxonomy == pattern


def resolve_density(
    *,
    kind: str,
    taxonomy: str | None,
    habits: Habits,
    explicit: Density | None,
) -> Density:
    if explicit is not None:
        return explicit

    by_kind = habits.extraction.by_kind.get(kind)
    if by_kind is not None:
        return by_kind

    if taxonomy:
        candidates = [
            (pattern, density)
            for pattern, density in habits.extraction.by_taxonomy.items()
            if _prefix_match(pattern, taxonomy)
        ]
        if candidates:
            # Most-specific = longest base (without the trailing /*).
            candidates.sort(key=lambda p: len(p[0].rstrip("*").rstrip("/")), reverse=True)
            return candidates[0][1]

    return habits.extraction.default_density
