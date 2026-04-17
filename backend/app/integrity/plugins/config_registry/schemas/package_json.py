"""Schema validator for ``package.json``."""
from __future__ import annotations

import json
from pathlib import Path

from .base import ValidationFailure


class PackageJsonSchema:
    type_name = "package_json"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return [ValidationFailure(
                rule="parse_error", location="<root>",
                message=f"JSON parse error: {exc}",
            )]

        if not isinstance(data, dict):
            return [ValidationFailure(
                rule="bad_root", location="<root>",
                message="package.json root must be an object",
            )]

        if "name" not in data:
            failures.append(ValidationFailure(
                rule="missing_field", location="name",
                message='"name" is required',
            ))
        if "version" not in data:
            failures.append(ValidationFailure(
                rule="missing_field", location="version",
                message='"version" is required',
            ))

        for field_name in ("scripts", "dependencies", "devDependencies"):
            if field_name in data and not isinstance(data[field_name], dict):
                failures.append(ValidationFailure(
                    rule="wrong_type", location=field_name,
                    message=f'"{field_name}" must be an object, got {type(data[field_name]).__name__}',
                ))

        return failures
