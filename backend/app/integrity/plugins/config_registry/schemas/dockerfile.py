"""Schema validator for ``Dockerfile*``."""
from __future__ import annotations

import re
from pathlib import Path

from .base import ValidationFailure

FROM_RE = re.compile(r"^FROM\s+\S+(?:\s+AS\s+(\S+))?", re.IGNORECASE | re.MULTILINE)
COPY_FROM_RE = re.compile(r"^COPY\s+--from=(\S+)", re.IGNORECASE | re.MULTILINE)


class DockerfileSchema:
    type_name = "dockerfile"

    def validate(self, path: Path, content: str) -> list[ValidationFailure]:
        failures: list[ValidationFailure] = []
        first_meaningful = next(
            (l.strip() for l in content.splitlines()
             if l.strip() and not l.strip().startswith("#")),
            "",
        )
        if not first_meaningful.upper().startswith("FROM"):
            failures.append(ValidationFailure(
                rule="missing_from", location="line:1",
                message="Dockerfile must start with FROM",
            ))

        stage_names = {m.group(1) for m in FROM_RE.finditer(content) if m.group(1)}
        for cm in COPY_FROM_RE.finditer(content):
            ref = cm.group(1)
            # Numeric refs and image refs (with /) are valid.
            if ref.isdigit() or "/" in ref or ":" in ref:
                continue
            if ref not in stage_names:
                failures.append(ValidationFailure(
                    rule="undeclared_stage",
                    location=f"COPY --from={ref}",
                    message=f"COPY --from references undeclared stage '{ref}'",
                ))
        return failures
