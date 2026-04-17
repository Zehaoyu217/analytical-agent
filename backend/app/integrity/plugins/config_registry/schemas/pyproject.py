"""Schema validator for ``pyproject.toml``."""
from __future__ import annotations

import sys
from pathlib import Path

from .base import ValidationFailure

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


class PyprojectSchema:
    type_name = "pyproject"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        try:
            data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            return [ValidationFailure(
                rule="parse_error", location="<root>",
                message=f"TOML parse error: {exc}",
            )]

        project = data.get("project")
        if not isinstance(project, dict):
            failures.append(ValidationFailure(
                rule="missing_field", location="[project]",
                message="pyproject.toml must define a [project] table",
            ))
            return failures

        if "name" not in project:
            failures.append(ValidationFailure(
                rule="missing_field", location="[project].name",
                message="[project].name is required",
            ))
        if "version" not in project:
            failures.append(ValidationFailure(
                rule="missing_field", location="[project].version",
                message="[project].version is required",
            ))

        return failures
