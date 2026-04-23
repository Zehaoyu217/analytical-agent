from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from second_brain.config import Config
from second_brain.digest.passes.stale_review import (
    BATCH_SIZE,
    STALE_DAYS,
    StaleReviewPass,
)


def _write_source(cfg: Config, sid: str, taxonomy: str) -> None:
    folder = cfg.sources_dir / sid
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    (folder / "_source.md").write_text(
        "\n".join(
            [
                "---",
                f"id: {sid}",
                "title: t",
                "kind: note",
                f"ingested_at: {now}",
                "content_hash: sha256:deadbeef",
                f"habit_taxonomy: {taxonomy}",
                "raw: []",
                "cites: []",
                "related: []",
                "supersedes: []",
                "abstract: ''",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _stale_claim(cfg: Config, write_claim, slug: str, taxonomy: str, *, abstract: str = "x") -> Path:
    sid = f"src_{slug}"
    _write_source(cfg, sid, taxonomy)
    path = write_claim(cfg, slug)
    txt = path.read_text(encoding="utf-8")
    txt = txt.replace("supports: []", f"supports: ['{sid}']")
    txt = txt.replace("abstract: ''", f"abstract: '{abstract}'")
    path.write_text(txt, encoding="utf-8")
    # Force old mtime.
    old_ts = (datetime.now(UTC) - timedelta(days=STALE_DAYS + 10)).timestamp()
    os.utime(path, (old_ts, old_ts))
    return path


def test_pass_conforms_to_protocol() -> None:
    from second_brain.digest.passes import Pass

    p = StaleReviewPass()
    assert isinstance(p, Pass)
    assert p.prefix == "s"


def test_empty_kb_returns_empty(digest_cfg) -> None:
    assert StaleReviewPass().run(digest_cfg, client=None) == []


def test_three_stale_under_papers_ml_yields_single_batch(digest_cfg, write_claim) -> None:
    for i in range(3):
        _stale_claim(digest_cfg, write_claim, f"clm_ml{i:02d}", "papers/ml/transformers")
    entries = StaleReviewPass().run(digest_cfg, client=None)
    assert len(entries) == 1
    payload = entries[0].action
    assert payload["action"] == "re_abstract_batch"
    assert payload["taxonomy"] == "papers/ml/*"
    assert sorted(payload["claim_ids"]) == ["clm_ml00", "clm_ml01", "clm_ml02"]
    assert entries[0].section == "Stale review"


def test_fresh_mtime_excluded(digest_cfg, write_claim) -> None:
    sid = "src_fresh"
    _write_source(digest_cfg, sid, "papers/ml/foo")
    path = write_claim(digest_cfg, "clm_fresh")
    txt = path.read_text(encoding="utf-8")
    txt = txt.replace("supports: []", f"supports: ['{sid}']")
    txt = txt.replace("abstract: ''", "abstract: 'x'")
    path.write_text(txt, encoding="utf-8")
    # Leave mtime recent.
    assert StaleReviewPass().run(digest_cfg, client=None) == []


def test_empty_abstract_excluded(digest_cfg, write_claim) -> None:
    _stale_claim(digest_cfg, write_claim, "clm_noabs", "papers/ml/x", abstract="")
    # Overwrite: _stale_claim already set abstract = "" via literal; re-touch mtime.
    assert StaleReviewPass().run(digest_cfg, client=None) == []


def test_batch_size_caps_claim_ids(digest_cfg, write_claim) -> None:
    for i in range(BATCH_SIZE + 3):
        _stale_claim(digest_cfg, write_claim, f"clm_big{i:02d}", "papers/ml/massive")
    entries = StaleReviewPass().run(digest_cfg, client=None)
    assert len(entries) == 1
    assert len(entries[0].action["claim_ids"]) == BATCH_SIZE


def test_different_taxonomies_yield_separate_entries(digest_cfg, write_claim) -> None:
    _stale_claim(digest_cfg, write_claim, "clm_mla", "papers/ml/a")
    _stale_claim(digest_cfg, write_claim, "clm_mlb", "papers/ml/b")
    _stale_claim(digest_cfg, write_claim, "clm_sysa", "papers/systems/a")
    entries = StaleReviewPass().run(digest_cfg, client=None)
    tax_set = {e.action["taxonomy"] for e in entries}
    assert tax_set == {"papers/ml/*", "papers/systems/*"}


def test_retracted_claim_is_excluded(digest_cfg, write_claim) -> None:
    sid = "src_ret"
    _write_source(digest_cfg, sid, "papers/ml/x")
    path = write_claim(digest_cfg, "clm_ret", status="retracted")
    txt = path.read_text(encoding="utf-8")
    txt = txt.replace("supports: []", f"supports: ['{sid}']")
    txt = txt.replace("abstract: ''", "abstract: 'x'")
    path.write_text(txt, encoding="utf-8")
    old_ts = (datetime.now(UTC) - timedelta(days=STALE_DAYS + 10)).timestamp()
    os.utime(path, (old_ts, old_ts))
    assert StaleReviewPass().run(digest_cfg, client=None) == []
