"""Ingest eval suite: hermetic, note-only.

Ingest extraction (claim structuring) requires the Anthropic API. To keep the
suite runnable offline we only exercise the converter dispatch + filesystem
ingest: each fixture writes markdown content to a temp file under
``cfg.home``, calls :func:`ingest`, then verifies the resulting source
frontmatter records the expected ``kind``.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.eval.runner import EvalCase
from second_brain.frontmatter import load_document
from second_brain.ingest.base import IngestInput
from second_brain.ingest.orchestrator import ingest

_yaml = YAML(typ="safe")


class IngestSuite:
    name = "ingest"

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        seed = _yaml.load(
            (fixtures_dir / "note_sample.yaml").read_text(encoding="utf-8")
        )
        cases: list[EvalCase] = []
        for c in seed["cases"]:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".md",
                dir=cfg.home,
                delete=False,
                encoding="utf-8",
            ) as fh:
                fh.write(c["content"])
                path = Path(fh.name)
            try:
                folder = ingest(IngestInput.from_path(path), cfg=cfg)
                fm, _ = load_document(folder.source_md)
                kind_ok = fm.get("kind") == c["expected_kind"]
                cases.append(
                    EvalCase(
                        name=c["name"],
                        passed=kind_ok,
                        metric=1.0 if kind_ok else 0.0,
                        details=(
                            f"kind={fm.get('kind')} "
                            f"(expected {c['expected_kind']})"
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                cases.append(
                    EvalCase(
                        name=c["name"],
                        passed=False,
                        metric=0.0,
                        details=f"error: {exc}",
                    )
                )
            finally:
                path.unlink(missing_ok=True)
        return cases
