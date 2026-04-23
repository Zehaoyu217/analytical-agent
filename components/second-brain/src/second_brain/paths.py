from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceFolderPaths:
    root: Path
    source_md: Path
    raw_dir: Path
    raw_manifest: Path
