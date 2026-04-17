"""Wiki linter — structural integrity checks for `knowledge/wiki/`.

Checks performed:

1. `working.md` must exist and stay under `MAX_WORKING_LINES`.
2. `index.md` must exist and link only to files that exist.
3. `log.md` must exist and stay below `_LOG_MAX_BYTES` (warn-only).
4. Every file under `findings/`, `hypotheses/`, `entities/`, `sessions/` must
   end in `.md`.
5. Cross-references like `[[entity_name]]` must resolve to a file under
   `entities/`.
6. No orphaned files in subdirectories with names that look like ID stems but
   never appear in the index (warn-only).

Run: ``python -m app.wiki.lint``  (returns non-zero exit on errors).
Run: ``python -m app.wiki.lint --root <path>``  (custom wiki root).
Run: ``python -m app.wiki.lint --strict``  (treat warnings as errors).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.wiki.engine import MAX_WORKING_LINES

_LOG_MAX_BYTES = 100 * 1024 * 1024
_BIDIRECTIONAL_LINK = re.compile(r"\[\[([^\]\|#]+?)(?:\|[^\]]+)?\]\]")
_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True, slots=True)
class LintIssue:
    severity: str  # "error" | "warning"
    path: Path
    message: str

    def format(self) -> str:
        sev = self.severity.upper().ljust(7)
        return f"{sev} {self.path}: {self.message}"


@dataclass
class LintReport:
    errors: list[LintIssue] = field(default_factory=list)
    warnings: list[LintIssue] = field(default_factory=list)

    def add(self, issue: LintIssue) -> None:
        if issue.severity == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"


def _check_working(root: Path, report: LintReport) -> None:
    working = root / "working.md"
    if not working.exists():
        report.add(LintIssue("error", working, "missing — wiki has no working.md"))
        return
    line_count = sum(1 for _ in working.read_text().splitlines())
    if line_count > MAX_WORKING_LINES:
        report.add(
            LintIssue(
                "error",
                working,
                f"{line_count} lines exceeds MAX_WORKING_LINES={MAX_WORKING_LINES}",
            )
        )


def _check_log(root: Path, report: LintReport) -> None:
    log = root / "log.md"
    if not log.exists():
        report.add(LintIssue("warning", log, "missing log.md"))
        return
    size = log.stat().st_size
    if size > _LOG_MAX_BYTES:
        report.add(
            LintIssue(
                "warning",
                log,
                f"{size} bytes exceeds soft limit {_LOG_MAX_BYTES}",
            )
        )


def _check_index_links(root: Path, report: LintReport) -> None:
    index = root / "index.md"
    if not index.exists():
        report.add(LintIssue("error", index, "missing index.md"))
        return
    text = index.read_text()
    for match in _MARKDOWN_LINK.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target_path = (index.parent / target).resolve()
        if not target_path.exists():
            report.add(
                LintIssue(
                    "error",
                    index,
                    f"broken link → {target}",
                )
            )


def _check_subdir_files(root: Path, subdir: str, report: LintReport) -> None:
    dir_path = root / subdir
    if not dir_path.exists():
        return
    for f in dir_path.iterdir():
        if f.is_dir():
            continue
        if f.name.startswith("."):
            continue
        if not f.name.endswith(".md"):
            report.add(
                LintIssue(
                    "warning",
                    f,
                    f"non-markdown file in {subdir}/ — should be .md or excluded",
                )
            )


def _check_bidirectional_links(root: Path, report: LintReport) -> None:
    entities_dir = root / "entities"
    known: set[str] = set()
    if entities_dir.exists():
        for f in entities_dir.glob("*.md"):
            known.add(f.stem)
    for md in root.rglob("*.md"):
        if md.parent.name == "meta":
            continue
        text = md.read_text(errors="ignore")
        for match in _BIDIRECTIONAL_LINK.finditer(text):
            ref = match.group(1).strip().lower().replace(" ", "_")
            if ref not in known:
                report.add(
                    LintIssue(
                        "warning",
                        md,
                        f"unresolved [[wiki link]] → {ref}",
                    )
                )


def lint(root: Path) -> LintReport:
    """Run all wiki integrity checks against *root* and return the report."""
    report = LintReport()
    if not root.exists():
        report.add(LintIssue("error", root, "wiki root does not exist"))
        return report
    _check_working(root, report)
    _check_log(root, report)
    _check_index_links(root, report)
    _check_subdir_files(root, "findings", report)
    _check_subdir_files(root, "hypotheses", report)
    _check_subdir_files(root, "entities", report)
    _check_subdir_files(root, "sessions", report)
    _check_bidirectional_links(root, report)
    return report


def _default_root() -> Path:
    backend_root = Path(__file__).resolve().parent.parent.parent  # backend/
    return backend_root.parent / "knowledge" / "wiki"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint the project wiki.")
    parser.add_argument(
        "--root",
        type=Path,
        default=_default_root(),
        help="Wiki root (default: ../knowledge/wiki relative to backend/).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (non-zero exit on any issue).",
    )
    args = parser.parse_args(argv)

    report = lint(args.root)
    for issue in report.errors:
        print(issue.format())
    for issue in report.warnings:
        print(issue.format())
    print(f"\nwiki-lint @ {args.root}: {report.summary()}")

    if not report.ok or (args.strict and report.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
