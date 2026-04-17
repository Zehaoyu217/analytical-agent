"""Schema registry — maps config type → SchemaValidator."""
from __future__ import annotations

from .base import SchemaValidator, ValidationFailure
from .claude_settings import ClaudeSettingsSchema
from .package_json import PackageJsonSchema
from .pyproject import PyprojectSchema

SCHEMA_REGISTRY: dict[str, SchemaValidator] = {
    "pyproject": PyprojectSchema(),
    "package_json": PackageJsonSchema(),
    "claude_settings": ClaudeSettingsSchema(),
}

__all__ = ["SchemaValidator", "ValidationFailure", "SCHEMA_REGISTRY"]
