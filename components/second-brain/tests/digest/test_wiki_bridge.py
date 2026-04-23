from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from second_brain.digest.passes.wiki_bridge import STALE_CLAIM_DAYS, WikiBridgePass


def test_pass_conforms_to_protocol() -> None:
    from second_brain.digest.passes import Pass

    p = WikiBridgePass()
    assert isinstance(p, Pass)
    assert p.prefix == "w"


def test_no_env_var_returns_empty(digest_cfg, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SB_WIKI_DIR", raising=False)
    assert WikiBridgePass().run(digest_cfg, client=None) == []


def test_missing_wiki_dir_returns_empty(
    digest_cfg, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SB_WIKI_DIR", str(tmp_path / "does-not-exist"))
    assert WikiBridgePass().run(digest_cfg, client=None) == []


def test_empty_wiki_dir_returns_empty(
    digest_cfg, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    monkeypatch.setenv("SB_WIKI_DIR", str(wiki))
    assert WikiBridgePass().run(digest_cfg, client=None) == []


def test_mature_finding_emits_promote_entry(
    digest_cfg, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "finding.md").write_text(
        "---\nstatus: mature\ntaxonomy: papers/ml\n---\nsome insight here\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SB_WIKI_DIR", str(wiki))

    entries = WikiBridgePass().run(digest_cfg, client=None)
    assert len(entries) == 1
    assert entries[0].action == {
        "action": "promote_wiki_to_claim",
        "wiki_path": "finding.md",
        "proposed_taxonomy": "papers/ml",
    }
    assert entries[0].section == "Wiki ↔ KB drift"


def test_draft_finding_is_ignored(
    digest_cfg, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "draft.md").write_text(
        "---\nstatus: draft\n---\nnot mature\n", encoding="utf-8"
    )
    monkeypatch.setenv("SB_WIKI_DIR", str(wiki))
    assert WikiBridgePass().run(digest_cfg, client=None) == []


def test_stale_claim_with_wiki_mention_emits_backlink(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stale_old = datetime.now(UTC) - timedelta(days=STALE_CLAIM_DAYS + 5)
    path = write_claim(digest_cfg, "clm_foo", extracted_at=stale_old)
    # Force an old filesystem mtime.
    old_ts = (datetime.now(UTC) - timedelta(days=STALE_CLAIM_DAYS + 5)).timestamp()
    os.utime(path, (old_ts, old_ts))

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "ref.md").write_text(
        "---\nstatus: mature\n---\nsee clm_foo for details\n", encoding="utf-8"
    )
    monkeypatch.setenv("SB_WIKI_DIR", str(wiki))

    entries = WikiBridgePass().run(digest_cfg, client=None)
    # Wiki mentions claim → not a promote; is a backlink.
    actions = [e.action["action"] for e in entries]
    assert actions == ["backlink_claim_to_wiki"]
    payload = entries[0].action
    assert payload["claim_id"] == "clm_foo"
    assert payload["wiki_path"] == "ref.md"


def test_fresh_claim_yields_no_backlink(
    digest_cfg, write_claim, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_claim(digest_cfg, "clm_fresh")
    # Let its mtime be now.
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "ref.md").write_text(
        "---\nstatus: mature\n---\nsee clm_fresh for details\n", encoding="utf-8"
    )
    monkeypatch.setenv("SB_WIKI_DIR", str(wiki))

    entries = WikiBridgePass().run(digest_cfg, client=None)
    # Fresh claim → no backlink. Wiki references claim_fresh so no promote either.
    assert entries == []
    # touch time assertion so linter is happy
    _ = time.time()
