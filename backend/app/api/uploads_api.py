"""User dataset uploads — ingest a CSV/Parquet/JSON file into a per-conversation
DuckDB and record it on the conversation so the agent sees it next turn.

File layout::

    data/conversations/{conv_id}.json   # Conversation (with datasets[])
    data/user_data/{conv_id}.duckdb     # one DuckDB file per conversation

The agent-facing side of this lives in:
  - ``harness/sandbox_bootstrap.py`` — ATTACHes the per-conversation DB
  - ``harness/injector.py`` — emits the "## User-uploaded datasets" block
"""
from __future__ import annotations

import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Annotated

import duckdb
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.conversations_api import (
    ColumnInfo,
    Conversation,
    UploadedDataset,
    _conv_lock,
    _conv_path,
    _data_dir,
    _load_or_404,
    _validate_id,
)
from app.storage.json_store import write_json_atomic

router = APIRouter(prefix="/api/conversations", tags=["uploads"])

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
_TABLE_NAME_RE = re.compile(r"[^a-zA-Z0-9_]+")
_VALID_SUFFIXES = frozenset(
    {".csv", ".parquet", ".json", ".jsonl", ".ndjson", ".xlsx", ".xls"},
)
_EXCEL_SUFFIXES = frozenset({".xlsx", ".xls"})


def _user_data_root() -> Path:
    root = _data_dir() / "user_data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_data_db_path(conv_id: str) -> Path:
    """Public helper — used by chat_api to wire the sandbox."""
    return _user_data_root() / f"{conv_id}.duckdb"


def _sanitize_table_name(stem: str) -> str:
    cleaned = _TABLE_NAME_RE.sub("_", stem).strip("_").lower()
    if not cleaned:
        cleaned = "dataset"
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned[:48]


def _ensure_unique_table(con: duckdb.DuckDBPyConnection, base: str) -> str:
    existing = {str(row[0]) for row in con.execute("SHOW TABLES").fetchall()}
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def _read_expr(suffix: str, tmp_path: Path) -> str:
    path = str(tmp_path).replace("'", "''")  # single-quote escape for SQL literal
    if suffix == ".csv":
        return f"read_csv_auto('{path}')"
    if suffix == ".parquet":
        return f"read_parquet('{path}')"
    if suffix == ".json":
        return f"read_json_auto('{path}')"
    # .jsonl / .ndjson — newline-delimited JSON
    return f"read_json_auto('{path}', format='newline_delimited')"


@router.post("/{conv_id}/uploads", response_model=UploadedDataset)
async def upload_dataset(
    conv_id: str,
    file: Annotated[UploadFile, File()],
) -> UploadedDataset:
    _validate_id(conv_id)
    conv: Conversation = _load_or_404(conv_id)

    filename = file.filename or "dataset"
    suffix = Path(filename).suffix.lower()
    if suffix not in _VALID_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unsupported file type '{suffix}'. "
                "Use .csv, .parquet, .json, .jsonl, .ndjson, .xlsx, or .xls."
            ),
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="ccagent-upload-"))
    try:
        tmp_path = tmpdir / filename
        total = 0
        with tmp_path.open("wb") as out:
            while True:
                chunk = await file.read(1 << 20)  # 1 MiB
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="file too large (100 MB max)",
                    )
                out.write(chunk)

        base_table = _sanitize_table_name(Path(filename).stem)
        db_path = user_data_db_path(conv_id)

        with _conv_lock(conv_id):
            con = duckdb.connect(str(db_path))
            try:
                table_name = _ensure_unique_table(con, base_table)
                try:
                    if suffix in _EXCEL_SUFFIXES:
                        # DuckDB has no first-party Excel reader; go via pandas.
                        # Only the first sheet is ingested; users wanting a
                        # specific sheet should pre-export to CSV.
                        import pandas as pd  # noqa: PLC0415
                        df = pd.read_excel(tmp_path)
                        con.register("_ccagent_upload_tmp", df)
                        try:
                            con.execute(
                                f'CREATE TABLE "{table_name}" AS '
                                'SELECT * FROM _ccagent_upload_tmp'
                            )
                        finally:
                            con.unregister("_ccagent_upload_tmp")
                    else:
                        expr = _read_expr(suffix, tmp_path)
                        con.execute(
                            f'CREATE TABLE "{table_name}" AS SELECT * FROM {expr}'
                        )
                except (duckdb.Error, ValueError, ImportError) as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"failed to ingest file: {exc}",
                    ) from exc
                cols = con.execute(f'DESCRIBE "{table_name}"').fetchall()
                columns = [
                    ColumnInfo(name=str(c[0]), type=str(c[1])) for c in cols
                ]
                row_count_row = con.execute(
                    f'SELECT count(*) FROM "{table_name}"'
                ).fetchone()
                row_count = int(row_count_row[0]) if row_count_row else 0
            finally:
                con.close()

            dataset = UploadedDataset(
                table_name=table_name,
                filename=filename,
                columns=columns,
                row_count=row_count,
                size_bytes=total,
                uploaded_at=time.time(),
            )
            updated = conv.model_copy(update={
                "datasets": [*conv.datasets, dataset],
                "updated_at": dataset.uploaded_at,
            })
            write_json_atomic(_conv_path(conv_id), updated)

        return dataset
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@router.delete("/{conv_id}/datasets/{table_name}")
def delete_dataset(conv_id: str, table_name: str) -> dict[str, object]:
    _validate_id(conv_id)
    conv = _load_or_404(conv_id)
    remaining = [d for d in conv.datasets if d.table_name != table_name]
    if len(remaining) == len(conv.datasets):
        raise HTTPException(status_code=404, detail="dataset not found")

    with _conv_lock(conv_id):
        db_path = user_data_db_path(conv_id)
        if db_path.exists():
            con = duckdb.connect(str(db_path))
            try:
                con.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            finally:
                con.close()

        updated = conv.model_copy(update={
            "datasets": remaining,
            "updated_at": time.time(),
        })
        write_json_atomic(_conv_path(conv_id), updated)

    return {"ok": True, "table_name": table_name}
