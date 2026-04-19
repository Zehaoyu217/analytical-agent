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

        # Claude Code hook entries have shape:
        #   {"matcher": "<glob>", "hooks": [{"type": "command", "command": "..."}]}
        # `matcher` is optional for events without a tool concept (e.g.
        # UserPromptSubmit, Stop). `hooks[]` is required and each inner entry
        # needs `type` + `command`.
        _MATCHER_OPTIONAL_EVENTS = {"UserPromptSubmit", "Stop", "Notification", "SessionStart"}

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
                if "matcher" not in entry and event not in _MATCHER_OPTIONAL_EVENTS:
                    failures.append(ValidationFailure(
                        rule="missing_field",
                        location=f"hooks.{event}[{i}].matcher",
                        message='"matcher" is required for hook entries',
                    ))
                inner = entry.get("hooks")
                if inner is None:
                    failures.append(ValidationFailure(
                        rule="missing_field",
                        location=f"hooks.{event}[{i}].hooks",
                        message='"hooks" array is required for hook entries',
                    ))
                    continue
                if not isinstance(inner, list):
                    failures.append(ValidationFailure(
                        rule="wrong_type", location=f"hooks.{event}[{i}].hooks",
                        message='"hooks" must be a list',
                    ))
                    continue
                for j, h in enumerate(inner):
                    if not isinstance(h, dict):
                        failures.append(ValidationFailure(
                            rule="wrong_type",
                            location=f"hooks.{event}[{i}].hooks[{j}]",
                            message="inner hook must be an object",
                        ))
                        continue
                    for required in ("type", "command"):
                        if required not in h:
                            failures.append(ValidationFailure(
                                rule="missing_field",
                                location=f"hooks.{event}[{i}].hooks[{j}].{required}",
                                message=f'"{required}" is required',
                            ))

        return failures
