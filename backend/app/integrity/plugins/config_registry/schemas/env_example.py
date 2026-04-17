"""Schema validator for ``.env.example``."""
from __future__ import annotations

import re
from pathlib import Path

from .base import ValidationFailure

KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class EnvExampleSchema:
    type_name = "env_example"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                failures.append(ValidationFailure(
                    rule="bad_format", location=f"line:{i}",
                    message=f"line {i}: expected KEY=VALUE, got {stripped!r}",
                ))
                continue
            key, _ = stripped.split("=", 1)
            if not KEY_RE.match(key):
                failures.append(ValidationFailure(
                    rule="bad_key", location=f"line:{i}:key:{key}",
                    message=f"line {i}: key '{key}' must match [A-Z_][A-Z0-9_]*",
                ))
        return failures
