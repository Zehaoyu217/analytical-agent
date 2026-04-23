"""Create the `~/second-brain/` tree. Idempotent: never overwrites user content."""
from __future__ import annotations

from dataclasses import dataclass

from second_brain.config import Config

_README_TEMPLATE = """# Second Brain

Personal knowledge base. Markdown is source of truth.

```
~/second-brain/
  .sb/               # derived indexes (gitignored)
  sources/           # one folder per ingested artefact
  claims/            # atomic claims (*.md)
  inbox/             # drop files for `sb ingest`
  proposals/         # habit-learning proposals
  log.md             # append-only activity log
```

Run `sb --help` for commands. See the component README in
`claude-code-agent/components/second-brain/README.md` for the full guide.
"""

_LOG_HEADER = "# Second Brain — activity log\n\n"


@dataclass(frozen=True)
class ScaffoldResult:
    created_dirs: int
    created_files: int


def create_tree(cfg: Config) -> ScaffoldResult:
    """Create directories and starter files. Existing content is preserved."""
    dirs = [
        cfg.home,
        cfg.sb_dir,
        cfg.sources_dir,
        cfg.claims_dir,
        cfg.inbox_dir,
        cfg.proposals_dir,
    ]
    created_dirs = 0
    for d in dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=False)
            created_dirs += 1
        elif not d.is_dir():
            raise RuntimeError(f"{d} exists but is not a directory")

    created_files = 0
    if not cfg.readme_path.exists():
        cfg.readme_path.write_text(_README_TEMPLATE, encoding="utf-8")
        created_files += 1
    if not cfg.log_path.exists():
        cfg.log_path.write_text(_LOG_HEADER, encoding="utf-8")
        created_files += 1

    return ScaffoldResult(created_dirs=created_dirs, created_files=created_files)
