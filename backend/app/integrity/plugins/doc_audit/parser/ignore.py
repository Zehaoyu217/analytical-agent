from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class IgnoreMatcher:
    patterns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def load(cls, file_path: Path, *, repo_root: Path) -> IgnoreMatcher:
        if not file_path.exists():
            return cls(patterns=())
        text = file_path.read_text(encoding="utf-8", errors="replace")
        patterns: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
        return cls(patterns=tuple(patterns))

    def matches(self, rel_path: str) -> bool:
        normalized = rel_path.replace("\\", "/")
        return any(_glob_match(normalized, pat) for pat in self.patterns)


def _glob_match(path: str, pattern: str) -> bool:
    # Normalize gitignore-style `**` to fnmatch-friendly form.
    # We translate `dir/**` so that it matches `dir/anything/under/here`.
    pattern_norm = pattern.replace("\\", "/")
    if pattern_norm.endswith("/**"):
        prefix = pattern_norm[: -len("/**")]
        return path == prefix or path.startswith(prefix + "/")
    if "**" in pattern_norm:
        # Translate `a/**/b.md` → regex by hand: split on `**`
        parts = pattern_norm.split("**")
        # fnmatch.translate handles `*` but not `**`; emulate with substring tests
        # Simple form: anchor first part, last part, allow any depth between
        if len(parts) == 2:
            head, tail = parts[0].rstrip("/"), parts[1].lstrip("/")
            if head and not (path == head or path.startswith(head + "/")):
                return False
            return path.endswith(tail) if tail else True
    return fnmatch.fnmatch(path, pattern_norm)
