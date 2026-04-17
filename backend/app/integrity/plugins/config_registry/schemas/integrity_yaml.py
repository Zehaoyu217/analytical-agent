"""Schema validator for ``config/integrity.yaml``."""
from __future__ import annotations

from pathlib import Path

import yaml

from .base import ValidationFailure


class IntegrityYamlSchema:
    type_name = "integrity_yaml"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        try:
            data = yaml.safe_load(content) or {}
        except yaml.YAMLError as exc:
            return [ValidationFailure(
                rule="parse_error", location="<root>",
                message=f"YAML parse error: {exc}",
            )]
        plugins = data.get("plugins")
        if plugins is None:
            return failures
        if not isinstance(plugins, dict):
            return [ValidationFailure(
                rule="wrong_type", location="plugins",
                message=f'"plugins" must be a mapping, got {type(plugins).__name__}',
            )]
        for name, entry in plugins.items():
            if not isinstance(entry, dict):
                failures.append(ValidationFailure(
                    rule="wrong_type", location=f"plugins.{name}",
                    message=f'"plugins.{name}" must be a mapping',
                ))
                continue
            if "enabled" not in entry:
                failures.append(ValidationFailure(
                    rule="missing_field", location=f"plugins.{name}.enabled",
                    message=f'"plugins.{name}.enabled" is required (bool)',
                ))
        return failures
