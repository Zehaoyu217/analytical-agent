from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SeriesStroke:
    width: float
    dash: list[int] | None


@dataclass(frozen=True)
class VariantTokens:
    """A single variant's resolved tokens."""

    name: str
    raw: dict[str, Any]
    series_strokes: dict[str, SeriesStroke]
    typography: dict[str, Any]

    def surface(self, key: str) -> str:
        return str(self.raw["surface"][key])

    def series_color(self, role: str) -> str:
        return str(self.raw["series_blues"][role])

    def series_stroke(self, role: str) -> SeriesStroke:
        return self.series_strokes[role]

    def semantic(self, role: str) -> str:
        return str(self.raw["semantic"][role])

    def categorical(self) -> list[str]:
        return list(self.raw["categorical"])

    def diverging(self) -> dict[str, str]:
        return dict(self.raw["diverging"])

    def chart(self, key: str) -> Any:
        return self.raw["chart"][key]

    def typography_override(self) -> dict[str, Any]:
        return dict(self.raw.get("typography_override", {}))


@dataclass(frozen=True)
class ThemeTokens:
    variants: dict[str, dict[str, Any]]
    typography: dict[str, Any]
    series_strokes: dict[str, SeriesStroke]
    default_variant: str

    @classmethod
    def load(cls, path: Path) -> ThemeTokens:
        data = yaml.safe_load(path.read_text())
        strokes = {
            role: SeriesStroke(width=float(s["width"]), dash=s.get("dash"))
            for role, s in data["series_strokes"].items()
        }
        return cls(
            variants=data["variants"],
            typography=data["typography"],
            series_strokes=strokes,
            default_variant=data.get("default_variant", "light"),
        )

    def for_variant(self, name: str) -> VariantTokens:
        if name not in self.variants:
            raise KeyError(name)
        return VariantTokens(
            name=name,
            raw=self.variants[name],
            series_strokes=self.series_strokes,
            typography=self.typography,
        )

    def default(self) -> VariantTokens:
        return self.for_variant(self.default_variant)
