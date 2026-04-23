from __future__ import annotations

from pathlib import Path

from second_brain.log import EventKind, append_event


def test_appends_structured_entry(sb_home: Path) -> None:
    append_event(
        kind=EventKind.AUTO,
        op="ingest.taxonomy",
        subject="src_test",
        value="papers/ml",
        reason={"matches": "neighbor"},
    )
    text = (sb_home / "log.md").read_text()
    assert "[AUTO]" in text
    assert "ingest.taxonomy" in text
    assert "src_test" in text
    assert "papers/ml" in text


def test_multiple_entries_preserve_order(sb_home: Path) -> None:
    append_event(kind=EventKind.AUTO, op="x", subject="a", value="1")
    append_event(kind=EventKind.USER_OVERRIDE, op="x", subject="a", value="2")
    lines = (sb_home / "log.md").read_text().splitlines()
    assert any("[AUTO]" in ln and "1" in ln for ln in lines)
    assert any("[USER_OVERRIDE]" in ln and "2" in ln for ln in lines)
