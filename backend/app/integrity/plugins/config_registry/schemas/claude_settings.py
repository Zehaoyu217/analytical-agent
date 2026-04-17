"""Schema validator for ``.claude/settings.json``."""
from __future__ import annotations

import json
from pathlib import Path

from .base import ValidationFailure


class ClaudeSettingsSchema:
    type_name = "claude_settings"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            return [ValidationFailure(
                rule="parse_error", location="<root>",
                message=f"JSON parse error: {exc}",
            )]

        hooks = data.get("hooks")
        if hooks is None:
            return failures
        if not isinstance(hooks, dict):
            failures.append(ValidationFailure(
                rule="wrong_type", location="hooks",
                message=f'"hooks" must be an object, got {type(hooks).__name__}',
            ))
            return failures

        for event, entries in hooks.items():
            if not isinstance(entries, list):
                failures.append(ValidationFailure(
                    rule="wrong_type", location=f"hooks.{event}",
                    message=f'"hooks.{event}" must be a list',
                ))
                continue
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    failures.append(ValidationFailure(
                        rule="wrong_type", location=f"hooks.{event}[{i}]",
                        message="hook entry must be an object",
                    ))
                    continue
                for required in ("matcher", "command"):
                    if required not in entry:
                        failures.append(ValidationFailure(
                            rule="missing_field",
                            location=f"hooks.{event}[{i}].{required}",
                            message=f'"{required}" is required for hook entries',
                        ))

        return failures
