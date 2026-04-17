"""Schema registry — maps config type → SchemaValidator."""
from __future__ import annotations

from .base import SchemaValidator, ValidationFailure
from .claude_settings import ClaudeSettingsSchema
from .dockerfile import DockerfileSchema
from .env_example import EnvExampleSchema
from .integrity_yaml import IntegrityYamlSchema
from .makefile import MakefileSchema
from .package_json import PackageJsonSchema
from .pyproject import PyprojectSchema
from .tsconfig import TsconfigSchema
from .vite_config import ViteConfigSchema

SCHEMA_REGISTRY: dict[str, SchemaValidator] = {
    "pyproject": PyprojectSchema(),
    "package_json": PackageJsonSchema(),
    "claude_settings": ClaudeSettingsSchema(),
    "integrity_yaml": IntegrityYamlSchema(),
    "makefile": MakefileSchema(),
    "dockerfile": DockerfileSchema(),
    "env_example": EnvExampleSchema(),
    "vite_config": ViteConfigSchema(),
    "tsconfig": TsconfigSchema(),
}

__all__ = ["SchemaValidator", "ValidationFailure", "SCHEMA_REGISTRY"]
