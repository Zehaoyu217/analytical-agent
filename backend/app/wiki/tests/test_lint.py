from __future__ import annotations

from pathlib import Path

import pytest

from app.wiki.lint import lint


@pytest.fixture
def wiki(tmp_path: Path) -> Path:
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "working.md").write_text("# Working\n")
    (root / "log.md").write_text("# Log\n")
    (root / "index.md").write_text("# Index\n")
    (root / "entities").mkdir()
    (root / "findings").mkdir()
    (root / "hypotheses").mkdir()
    (root / "sessions").mkdir()
    return root


def test_clean_wiki_has_no_errors(wiki: Path) -> None:
    report = lint(wiki)
    assert report.ok
    assert report.errors == []


def test_missing_working_is_error(wiki: Path) -> None:
    (wiki / "working.md").unlink()
    report = lint(wiki)
    assert not report.ok
    assert any("working" in i.message or "working" in str(i.path) for i in report.errors)


def test_oversized_working_is_error(wiki: Path) -> None:
    (wiki / "working.md").write_text("\n".join(f"line {i}" for i in range(300)))
    report = lint(wiki)
    assert not report.ok
    assert any("MAX_WORKING_LINES" in i.message for i in report.errors)


def test_broken_index_link_is_error(wiki: Path) -> None:
    (wiki / "index.md").write_text("# Index\n[bad](nonexistent.md)\n")
    report = lint(wiki)
    assert not report.ok
    assert any("broken link" in i.message for i in report.errors)


def test_external_link_in_index_is_fine(wiki: Path) -> None:
    (wiki / "index.md").write_text(
        "# Index\n[external](https://example.com)\n[local](#anchor)\n"
    )
    report = lint(wiki)
    assert report.ok


def test_unresolved_bidirectional_link_is_warning(wiki: Path) -> None:
    (wiki / "findings" / "f1.md").write_text("See [[unknown_entity]] for context.")
    report = lint(wiki)
    assert report.ok  # warnings only — still passes
    assert any("unresolved" in i.message for i in report.warnings)


def test_resolved_bidirectional_link_is_clean(wiki: Path) -> None:
    (wiki / "entities" / "alice.md").write_text("# Alice\n")
    (wiki / "findings" / "f1.md").write_text("See [[alice]] for context.")
    report = lint(wiki)
    assert report.ok
    assert not any("unresolved" in i.message for i in report.warnings)


def test_nonmd_file_in_subdir_is_warning(wiki: Path) -> None:
    (wiki / "findings" / "stray.txt").write_text("not markdown")
    report = lint(wiki)
    assert report.ok
    assert any("non-markdown" in i.message for i in report.warnings)


def test_missing_root_is_error(tmp_path: Path) -> None:
    report = lint(tmp_path / "does_not_exist")
    assert not report.ok
