"""SchemaValidator protocol + ValidationFailure dataclass."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ValidationFailure:
    rule: str           # short id like "missing_field" or "parse_error"
    location: str       # JSON-ish path inside the file, e.g. "[project].name"
    message: str


@runtime_checkable
class SchemaValidator(Protocol):
    type_name: str

    def validate(self, path: Path, content: str) -> list[ValidationFailure]: ...
