"""Dataset upload endpoint.

Accepts CSV and Parquet files and stores them under
``data/uploads/{session_id}/{filename}`` for later use by the agent loop.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

_ALLOWED_EXTENSIONS = {".csv", ".parquet"}
_UPLOAD_ROOT = Path("data/uploads")


class DatasetUploadResponse(BaseModel):
    session_id: str
    path: str
    filename: str


@router.post("/upload", response_model=DatasetUploadResponse)
def upload_dataset(
    file: UploadFile = File(...),
    session_id: str = Form(...),
) -> DatasetUploadResponse:
    """Upload a CSV or Parquet file for a given session."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is required")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file type {suffix!r}; allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    dest_dir = _UPLOAD_ROOT / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / file.filename
    contents = file.file.read()
    dest_path.write_bytes(contents)

    return DatasetUploadResponse(
        session_id=session_id,
        path=str(dest_path),
        filename=file.filename,
    )
