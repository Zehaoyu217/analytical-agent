from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    home: Path
    sb_dir: Path

    @property
    def enabled(self) -> bool:
        return self.home.exists() and self.sb_dir.exists()

    @property
    def sources_dir(self) -> Path:
        return self.home / "sources"

    @property
    def claims_dir(self) -> Path:
        return self.home / "claims"

    @property
    def inbox_dir(self) -> Path:
        return self.home / "inbox"

    @property
    def papers_dir(self) -> Path:
        return self.home / "papers"

    @property
    def projects_dir(self) -> Path:
        return self.home / "projects"

    @property
    def experiments_dir(self) -> Path:
        return self.home / "experiments"

    @property
    def syntheses_dir(self) -> Path:
        return self.home / "syntheses"

    @property
    def views_dir(self) -> Path:
        return self.home / "views"

    @property
    def obsidian_view_dir(self) -> Path:
        return self.views_dir / "obsidian"

    @property
    def duckdb_path(self) -> Path:
        return self.sb_dir / "graph.duckdb"

    @property
    def fts_path(self) -> Path:
        return self.sb_dir / "kb.sqlite"

    @property
    def vectors_path(self) -> Path:
        return self.sb_dir / "vectors.sqlite"

    @property
    def analytics_path(self) -> Path:
        return self.sb_dir / "analytics.duckdb"

    @property
    def proposals_dir(self) -> Path:
        return self.home / "proposals"

    @property
    def digests_dir(self) -> Path:
        return self.home / "digests"

    @property
    def log_path(self) -> Path:
        return self.home / "log.md"

    @property
    def readme_path(self) -> Path:
        return self.home / "README.md"

    @classmethod
    def load(cls) -> Config:
        env = os.environ.get("SECOND_BRAIN_HOME")
        home = Path(env).expanduser() if env else Path.home() / "second-brain"
        return cls(home=home, sb_dir=home / ".sb")
