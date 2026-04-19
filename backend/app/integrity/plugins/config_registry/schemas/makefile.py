"""Schema validator for ``Makefile``."""
from __future__ import annotations

import re
from pathlib import Path

from .base import ValidationFailure

PHONY_RE = re.compile(r"^\.PHONY:\s*(.+)$", re.MULTILINE)
TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+):", re.MULTILINE)
KEBAB_OK = re.compile(r"^[a-z0-9._-]+$")


def _join_continuations(content: str) -> str:
    """Collapse Makefile backslash line continuations onto a single line."""
    return re.sub(r"\\\n\s*", " ", content)


class MakefileSchema:
    type_name = "makefile"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []

        # `.PHONY: a b \` continuations span lines; collapse before scanning.
        joined = _join_continuations(content)
        phony_targets: set[str] = set()
        for m in PHONY_RE.finditer(joined):
            phony_targets.update(m.group(1).split())

        # Find every target (left-of-colon at line start, not indented).
        for tm in TARGET_RE.finditer(content):
            target = tm.group(1)
            if target.startswith("."):  # .PHONY etc.
                continue
            if not KEBAB_OK.match(target):
                failures.append(ValidationFailure(
                    rule="bad_target_case",
                    location=f"target:{target}",
                    message=f"Make target '{target}' should use kebab-case",
                ))
            # Heuristic: if a target produces no file (rule body uses no $@ or
            # ends in .PHONY-style action), require it be in .PHONY.
            if target not in phony_targets and not _looks_like_file_target(target):
                failures.append(ValidationFailure(
                    rule="missing_phony", location=".PHONY",
                    message=f"target '{target}' is not in .PHONY",
                ))
        return failures


def _looks_like_file_target(target: str) -> bool:
    return "/" in target or "." in target.lstrip(".")
