from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from second_brain.config import Config
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import IngestError, ingest

_MANIFEST_VERSION = 1
_MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class InboxFailure:
    path: str
    error: str
    attempts: int
    quarantined: bool


@dataclass(frozen=True)
class InboxRunResult:
    ok: list[str] = field(default_factory=list)
    failed: list[InboxFailure] = field(default_factory=list)


class InboxRunner:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def run(self) -> InboxRunResult:
        self.cfg.inbox_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._load_manifest()
        items: list[dict] = []
        ok: list[str] = []
        failed: list[InboxFailure] = []

        for path in sorted(self._candidates()):
            prior = self._prior_attempts(manifest, path)
            try:
                source = IngestInput.from_path(path)
                folder = ingest(source, cfg=self.cfg)
            except (IngestError, Exception) as exc:  # noqa: BLE001 — converter can raise anything
                attempts = prior + 1
                quarantined = attempts >= _MAX_ATTEMPTS
                failure = InboxFailure(
                    path=str(path), error=str(exc), attempts=attempts, quarantined=quarantined
                )
                failed.append(failure)
                items.append(
                    {
                        "path": str(path),
                        "status": "failed",
                        "error": str(exc),
                        "attempts": attempts,
                        "quarantined": quarantined,
                    }
                )
                continue
            slug = folder.root.name
            ok.append(slug)
            self._move_to_processed(path)
            items.append({"path": str(path), "status": "ok", "slug": slug})

        manifest["runs"].append(
            {"started_at": datetime.now(UTC).isoformat(), "items": items}
        )
        self._save_manifest(manifest)
        return InboxRunResult(ok=ok, failed=failed)

    def _candidates(self) -> list[Path]:
        if not self.cfg.inbox_dir.exists():
            return []
        return [
            p
            for p in self.cfg.inbox_dir.iterdir()
            if p.is_file() and not p.name.startswith(".")
        ]

    def _move_to_processed(self, path: Path) -> None:
        date_dir = self.cfg.inbox_dir / ".processed" / datetime.now(UTC).strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(date_dir / path.name))

    def _manifest_path(self) -> Path:
        return self.cfg.sb_dir / "inbox_manifest.json"

    def _load_manifest(self) -> dict:
        p = self._manifest_path()
        if not p.exists():
            return {"version": _MANIFEST_VERSION, "runs": []}
        return json.loads(p.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest: dict) -> None:
        self.cfg.sb_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path().write_text(
            json.dumps(manifest, indent=2, sort_keys=False), encoding="utf-8"
        )

    def _prior_attempts(self, manifest: dict, path: Path) -> int:
        total = 0
        target = str(path)
        for run in manifest.get("runs", []):
            for item in run.get("items", []):
                if item.get("path") == target and item.get("status") == "failed":
                    total += 1
        return total
