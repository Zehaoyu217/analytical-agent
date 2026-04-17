"""Schema validator for ``config/hooks_coverage.yaml`` — non-raising shape check.

Mirrors Plugin E's per-type schema validators (``ClaudeSettingsSchema`` etc.):
returns ``list[ValidationFailure]`` rather than raising. The plugin's strict
``coverage.load_coverage`` raises; this validator is for surfacing failures
in the report without aborting the rest of the scan.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ...config_registry.schemas.base import ValidationFailure


class CoverageSchemaValidator:
    type_name = "hooks_coverage"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            return [ValidationFailure(
                rule="parse_error",
                location="<root>",
                message=f"YAML parse error: {exc}",
            )]
        if data is None:
            data = {}
        if not isinstance(data, dict):
            return [ValidationFailure(
                rule="wrong_type",
                location="<root>",
                message=f"top-level must be a mapping, got {type(data).__name__}",
            )]

        rules = data.get("rules")
        if rules is None:
            failures.append(ValidationFailure(
                rule="missing_field",
                location="rules",
                message="'rules' is required",
            ))
        elif not isinstance(rules, list):
            failures.append(ValidationFailure(
                rule="wrong_type",
                location="rules",
                message=f"'rules' must be a list, got {type(rules).__name__}",
            ))
        else:
            for idx, raw_rule in enumerate(rules):
                failures.extend(_validate_rule(raw_rule, idx))

        tolerated = data.get("tolerated")
        if tolerated is not None and not isinstance(tolerated, list):
            failures.append(ValidationFailure(
                rule="wrong_type",
                location="tolerated",
                message=f"'tolerated' must be a list, got {type(tolerated).__name__}",
            ))
        return failures


def _validate_rule(raw_rule: object, idx: int) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    if not isinstance(raw_rule, dict):
        return [ValidationFailure(
            rule="wrong_type",
            location=f"rules[{idx}]",
            message=f"rule must be a mapping, got {type(raw_rule).__name__}",
        )]
    label = f"rules[{idx}]"
    rid = raw_rule.get("id")
    if isinstance(rid, str) and rid:
        label = f"rules[{rid}]"

    for field in ("id", "description", "when", "requires_hook"):
        if field not in raw_rule:
            failures.append(ValidationFailure(
                rule="missing_field",
                location=f"{label}.{field}",
                message=f"'{field}' is required",
            ))

    when = raw_rule.get("when")
    if isinstance(when, dict):
        if "paths" not in when:
            failures.append(ValidationFailure(
                rule="missing_field",
                location=f"{label}.when.paths",
                message="'paths' is required",
            ))
        elif not isinstance(when["paths"], list):
            failures.append(ValidationFailure(
                rule="wrong_type",
                location=f"{label}.when.paths",
                message="'paths' must be a list",
            ))

    rh = raw_rule.get("requires_hook")
    if isinstance(rh, dict):
        for field in ("event", "matcher", "command_substring"):
            if field not in rh:
                failures.append(ValidationFailure(
                    rule="missing_field",
                    location=f"{label}.requires_hook.{field}",
                    message=f"'{field}' is required",
                ))
    return failures
