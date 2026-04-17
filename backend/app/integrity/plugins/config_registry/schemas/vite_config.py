"""Schema validator for ``vite.config.{ts,js,mjs}``.

Cannot exec arbitrary TypeScript safely, so we only check that
``export default`` is present (Vite requires it).
"""
from __future__ import annotations

from pathlib import Path

from .base import ValidationFailure


class ViteConfigSchema:
    type_name = "vite_config"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        if "export default" not in content:
            return [ValidationFailure(
                rule="missing_export_default", location="<root>",
                message="vite.config must contain `export default`",
            )]
        return []
