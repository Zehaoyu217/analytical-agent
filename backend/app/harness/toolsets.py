"""Named composable toolset groups (H5).

``ToolsetResolver`` loads toolset definitions from a YAML file and resolves
each named set to a flat ``frozenset[str]`` of tool names via recursive
``includes`` flattening.  Cycle detection prevents infinite recursion.

Typical usage::

    resolver = ToolsetResolver.from_yaml(Path("config/toolsets.yaml"))
    tools = resolver.resolve("readonly")   # frozenset of tool names
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ToolsetResolver:
    """Resolves named toolset groups defined in a YAML config file."""

    def __init__(self, config: dict[str, Any]) -> None:
        # ``config`` is the ``toolsets:`` mapping:
        #   {name: {tools: [...], includes: [...]}}
        self._config = config

    @classmethod
    def from_yaml(cls, path: Path) -> ToolsetResolver:
        """Load toolset definitions from *path* and return a resolver."""
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(raw.get("toolsets", {}))

    # ── Public API ────────────────────────────────────────────────────────────

    def names(self) -> list[str]:
        """Return all defined toolset names."""
        return list(self._config.keys())

    def resolve(
        self,
        name: str,
        _seen: frozenset[str] = frozenset(),
    ) -> frozenset[str]:
        """Return the full flattened set of tool names for *name*.

        Raises:
            KeyError: if *name* is not defined.
            ValueError: if a circular ``includes`` reference is detected.
        """
        if name not in self._config:
            raise KeyError(f"unknown toolset: {name!r}")
        if name in _seen:
            raise ValueError(
                f"toolset cycle detected at {name!r} — "
                f"resolution path: {' -> '.join(sorted(_seen))} -> {name}"
            )

        _seen = _seen | {name}
        entry = self._config[name]
        tools: set[str] = set(entry.get("tools", []))

        for included in entry.get("includes", []):
            tools |= self.resolve(included, _seen)

        return frozenset(tools)
