from __future__ import annotations

from collections.abc import Iterable

from slugify import slugify

from second_brain.schema.source import SourceKind

DEFAULT_MAX_LENGTH = 80


def propose_source_slug(
    *,
    kind: SourceKind,
    title: str,
    year: int | None = None,
    max_length: int = DEFAULT_MAX_LENGTH,
    taken: Iterable[str] = (),
) -> str:
    """Deterministic slug: `src_{year?_}{title-kebab}`, truncated + collision-safe."""
    parts: list[str] = ["src"]
    if year is not None:
        parts.append(str(year))
    parts.append(slugify(title, lowercase=True, max_length=max_length))
    base = "_".join(parts)
    # hard truncate to max_length after joining
    if len(base) > max_length:
        base = base[:max_length].rstrip("-_")

    taken_set = set(taken)
    if base not in taken_set:
        return base
    n = 2
    while f"{base}-{n}" in taken_set:
        n += 1
    return f"{base}-{n}"
