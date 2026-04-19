"""Small JSON storage helper used by the BE1 REST routers.

Single-process assumption: concurrent safety via per-resource locking is NOT
required for this iteration. Writes are atomic (write-tmp + os.replace) so
a single process won't leave half-written files behind, but cross-process
coordination is not attempted here.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)


class JsonStoreError(RuntimeError):
    """Raised when a JSON file cannot be read or parsed into the target model."""


def read_json(path: Path, model: type[M], default: M | None = None) -> M:  # noqa: UP047 — TypeVar generic keeps older call sites intact
    """Read `path` and validate it against `model`.

    If the file does not exist, return `default` when provided, otherwise raise
    FileNotFoundError. On corrupt JSON or schema mismatch, raises JsonStoreError.
    """
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(str(path))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise JsonStoreError(f"corrupt JSON at {path}: {exc}") from exc
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise JsonStoreError(f"schema mismatch at {path}: {exc}") from exc


def write_json_atomic(path: Path, model: BaseModel) -> None:
    """Write `model` as JSON to `path` atomically.

    Creates the parent directory on demand. The payload is written to a sibling
    temp file and then renamed into place via os.replace, which is atomic on
    POSIX for same-filesystem moves.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump_json(indent=2)
    # NamedTemporaryFile with delete=False so we can os.replace after close.
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup — the tmp file may or may not exist at this point.
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise
