from __future__ import annotations

import shutil
from pathlib import Path

from second_brain.config import Config
from second_brain.research.schema import CenterKind, iter_center_documents


def export_obsidian_view(cfg: Config) -> Path:
    root = cfg.obsidian_view_dir
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    for folder in ("Index", "Projects", "Papers", "Experiments", "Syntheses", "Sources", ".drafts", ".meta"):
        (root / folder).mkdir(parents=True, exist_ok=True)

    docs = iter_center_documents(cfg)
    entries: dict[CenterKind, list[str]] = {
        CenterKind.PROJECT: [],
        CenterKind.PAPER: [],
        CenterKind.EXPERIMENT: [],
        CenterKind.SYNTHESIS: [],
    }
    for _path, doc, body in docs:
        target_dir = {
            CenterKind.PROJECT: root / "Projects",
            CenterKind.PAPER: root / "Papers",
            CenterKind.EXPERIMENT: root / "Experiments",
            CenterKind.SYNTHESIS: root / "Syntheses",
        }[doc.kind]
        target = target_dir / f"{doc.id}.md"
        target.write_text(body, encoding="utf-8")
        entries[doc.kind].append(f"- [[{doc.id}|{doc.title}]]")

    (root / "Home.md").write_text(
        "\n".join(
            [
                "# Research Home",
                "",
                "## Hubs",
                "",
                "- [[Index/By Project|By Project]]",
                "- [[Index/By Paper|By Paper]]",
                "- [[Index/By Experiment|By Experiment]]",
                "- [[Index/By Synthesis|By Synthesis]]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_index(root / "Index" / "By Project.md", "Projects", entries[CenterKind.PROJECT])
    _write_index(root / "Index" / "By Paper.md", "Papers", entries[CenterKind.PAPER])
    _write_index(root / "Index" / "By Experiment.md", "Experiments", entries[CenterKind.EXPERIMENT])
    _write_index(root / "Index" / "By Synthesis.md", "Syntheses", entries[CenterKind.SYNTHESIS])
    return root


def _write_index(path: Path, title: str, entries: list[str]) -> None:
    body = "\n".join([f"# {title}", "", *(entries or ["- none"])]) + "\n"
    path.write_text(body, encoding="utf-8")
