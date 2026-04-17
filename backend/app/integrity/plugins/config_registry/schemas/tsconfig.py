"""Schema validator for ``tsconfig*.json``."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .base import ValidationFailure

# Strip JSON-with-comments before parsing.
LINE_COMMENT = re.compile(r"//[^\n]*")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_jsonc(s: str) -> str:
    s = BLOCK_COMMENT.sub("", s)
    s = LINE_COMMENT.sub("", s)
    return s


class TsconfigSchema:
    type_name = "tsconfig"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        try:
            data = json.loads(_strip_jsonc(content))
        except json.JSONDecodeError as exc:
            return [ValidationFailure(
                rule="parse_error", location="<root>",
                message=f"JSON parse error: {exc}",
            )]
        failures: list[ValidationFailure] = []
        if "compilerOptions" not in data:
            failures.append(ValidationFailure(
                rule="missing_field", location="compilerOptions",
                message='"compilerOptions" is required',
            ))
        ext = data.get("extends")
        if isinstance(ext, str):
            target = (path.parent / ext).resolve()
            if not target.exists():
                failures.append(ValidationFailure(
                    rule="bad_extends", location="extends",
                    message=f'"extends" points to missing file: {ext}',
                ))
        return failures
