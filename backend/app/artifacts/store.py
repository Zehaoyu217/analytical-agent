from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from app.artifacts.events import EventBus, get_event_bus
from app.artifacts.models import Artifact

logger = logging.getLogger(__name__)

INLINE_THRESHOLD_BYTES = 512 * 1024  # 512KB


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().strip()).strip("_")
    return slug[:60] if slug else "artifact"


class ArtifactStore:
    def __init__(
        self,
        db_path: str | Path | None = None,
        disk_root: str | Path | None = None,
        inline_threshold: int = INLINE_THRESHOLD_BYTES,
        event_bus: EventBus | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else None
        self._disk_root = Path(disk_root) if disk_root else None
        self._inline_threshold = inline_threshold
        self._events = event_bus or get_event_bus()
        self._cache: dict[str, list[Artifact]] = {}
        self._loaded: set[str] = set()
        if self._db_path:
            self._init_db()

    # ── DB ──────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    type TEXT NOT NULL DEFAULT 'table',
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    disk_path TEXT DEFAULT NULL,
                    format TEXT NOT NULL DEFAULT 'html',
                    chart_data_json TEXT DEFAULT NULL,
                    total_rows INTEGER DEFAULT NULL,
                    displayed_rows INTEGER DEFAULT NULL,
                    profile_summary TEXT DEFAULT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    PRIMARY KEY (session_id, id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_art_session ON artifacts(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_art_name ON artifacts(session_id, name)")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    # ── Disk overflow ───────────────────────────────────────────────────────

    def _disk_path_for(self, session_id: str, artifact_id: str, fmt: str) -> Path:
        assert self._disk_root is not None
        folder = self._disk_root / session_id
        folder.mkdir(parents=True, exist_ok=True)
        ext = re.sub(r"[^A-Za-z0-9]+", "", fmt) or "bin"
        return folder / f"{artifact_id}.{ext}"

    def _should_offload(self, content: str) -> bool:
        return self._disk_root is not None and len(content.encode("utf-8")) >= self._inline_threshold

    # ── Row (de)serialization ───────────────────────────────────────────────

    def _to_row(self, a: Artifact) -> tuple:
        if self._should_offload(a.content):
            disk_path = self._disk_path_for(a.session_id, a.id, a.format)
            disk_path.write_text(a.content)
            inline_content = ""
            disk_str = str(disk_path)
        else:
            inline_content = a.content
            disk_str = None
        return (
            a.id, a.session_id, a.name, a.type, a.title, a.description,
            inline_content, disk_str, a.format,
            json.dumps(a.chart_data) if a.chart_data else None,
            a.total_rows, a.displayed_rows, a.profile_summary,
            json.dumps(a.metadata), a.created_at,
        )

    def _from_row(self, row: tuple) -> Artifact:
        (id_, session_id, name, type_, title, desc, inline_content, disk_path,
         fmt, chart_json, total_rows, disp_rows, profile_summary, meta_json, created_at) = row
        content = inline_content
        if disk_path and Path(disk_path).exists():
            content = Path(disk_path).read_text()
        return Artifact(
            id=id_, session_id=session_id, name=name, type=type_,
            title=title, description=desc, content=content, format=fmt,
            chart_data=json.loads(chart_json) if chart_json else None,
            total_rows=total_rows, displayed_rows=disp_rows,
            profile_summary=profile_summary,
            metadata=json.loads(meta_json) if meta_json else {},
            created_at=created_at,
        )

    # ── Session load ────────────────────────────────────────────────────────

    def _load_session(self, session_id: str) -> None:
        if session_id in self._loaded or not self._db_path:
            self._loaded.add(session_id)
            return
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, session_id, name, type, title, description, content, disk_path, "
                "format, chart_data_json, total_rows, displayed_rows, profile_summary, "
                "metadata_json, created_at FROM artifacts WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        self._cache[session_id] = [self._from_row(r) for r in rows]
        self._loaded.add(session_id)

    def _persist(self, a: Artifact) -> None:
        if not self._db_path:
            return
        # Read existing disk_path (if any) before overwriting, so we can clean up orphans.
        old_disk_path: str | None = None
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT disk_path FROM artifacts WHERE session_id = ? AND id = ?",
                (a.session_id, a.id),
            )
            row = cur.fetchone()
            if row:
                old_disk_path = row[0]

        new_row = self._to_row(a)
        new_disk_path = new_row[7]  # index 7 = disk_path (see column order)
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    new_row,
                )
                conn.commit()
        except Exception:
            # Commit failed — orphan any freshly-written blob before re-raising.
            if new_disk_path and new_disk_path != old_disk_path:
                Path(new_disk_path).unlink(missing_ok=True)
            raise
        # Commit succeeded — clean up the old blob if we replaced or removed it.
        if old_disk_path and old_disk_path != new_disk_path:
            Path(old_disk_path).unlink(missing_ok=True)

    # ── Public API ──────────────────────────────────────────────────────────

    def add_artifact(self, session_id: str, artifact: Artifact) -> Artifact:
        self._load_session(session_id)
        artifact.session_id = session_id
        if not artifact.name and artifact.title:
            base = _slugify(artifact.title)
            existing = {a.name for a in self._cache.get(session_id, [])}
            slug, counter = base, 2
            while slug in existing:
                slug = f"{base}_{counter}"
                counter += 1
            artifact.name = slug
        self._cache.setdefault(session_id, []).append(artifact)
        self._persist(artifact)
        self._events.emit("artifact.saved", {"session_id": session_id, "artifact_id": artifact.id, "type": artifact.type})
        return artifact

    def update_artifact(self, session_id: str, artifact_id: str, **kwargs: Any) -> Artifact | None:
        self._load_session(session_id)
        items = self._cache.get(session_id, [])
        for idx, a in enumerate(items):
            if a.id == artifact_id:
                updated = a.model_copy(update=kwargs)
                items[idx] = updated
                self._persist(updated)
                self._events.emit("artifact.updated", {"session_id": session_id, "artifact_id": updated.id})
                return updated
        return None

    def get_artifacts(self, session_id: str) -> list[Artifact]:
        self._load_session(session_id)
        return list(self._cache.get(session_id, []))

    def get_artifact(self, session_id: str, artifact_id: str) -> Artifact | None:
        self._load_session(session_id)
        for a in self._cache.get(session_id, []):
            if a.id == artifact_id:
                return a
        return None

    def get_artifact_by_name(self, session_id: str, name: str) -> Artifact | None:
        self._load_session(session_id)
        nlower = name.lower()
        for a in self._cache.get(session_id, []):
            if a.name == nlower or a.title.lower() == nlower:
                return a
        return None
