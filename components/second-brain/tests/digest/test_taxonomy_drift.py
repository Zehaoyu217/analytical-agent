from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from second_brain.config import Config
from second_brain.digest.passes.taxonomy_drift import (
    CLUSTER_MIN,
    TaxonomyDriftPass,
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


def test_pass_conforms_to_protocol() -> None:
    from second_brain.digest.passes import Pass

    p = TaxonomyDriftPass()
    assert isinstance(p, Pass)
    assert p.prefix == "t"


def test_empty_kb_returns_empty(digest_cfg) -> None:
    assert TaxonomyDriftPass().run(digest_cfg, client=None) == []


def test_below_threshold_returns_empty(digest_cfg, write_claim) -> None:
    for i in range(CLUSTER_MIN - 1):
        sid = f"src_sec{i:02d}"
        _write_source(digest_cfg, sid, "papers/security/paper")
        write_claim(digest_cfg, f"clm_sec{i:02d}")
        # Inject supports via rewrite.
        path = digest_cfg.claims_dir / f"clm_sec{i:02d}.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("supports: []", f"supports: ['{sid}']"),
            encoding="utf-8",
        )
    assert TaxonomyDriftPass().run(digest_cfg, client=None) == []


def test_at_threshold_emits_one_entry(digest_cfg, write_claim) -> None:
    for i in range(CLUSTER_MIN):
        sid = f"src_sec{i:02d}"
        _write_source(digest_cfg, sid, "papers/security/details")
        write_claim(digest_cfg, f"clm_sec{i:02d}")
        path = digest_cfg.claims_dir / f"clm_sec{i:02d}.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("supports: []", f"supports: ['{sid}']"),
            encoding="utf-8",
        )

    entries = TaxonomyDriftPass().run(digest_cfg, client=None)
    assert len(entries) == 1
    payload = entries[0].action
    assert payload["action"] == "add_taxonomy_root"
    assert payload["root"] == "papers/security"
    assert len(payload["example_claim_ids"]) == CLUSTER_MIN  # 5 ≤ first-5 cap

    assert entries[0].section == "Taxonomy drift"


def test_under_existing_root_is_not_drift(digest_cfg, write_claim) -> None:
    # papers/ml is a default root → not drift even with many claims.
    for i in range(CLUSTER_MIN + 2):
        sid = f"src_ml{i:02d}"
        _write_source(digest_cfg, sid, "papers/ml/transformers")
        write_claim(digest_cfg, f"clm_ml{i:02d}")
        path = digest_cfg.claims_dir / f"clm_ml{i:02d}.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("supports: []", f"supports: ['{sid}']"),
            encoding="utf-8",
        )
    assert TaxonomyDriftPass().run(digest_cfg, client=None) == []


def test_claim_without_supporting_source_is_ignored(digest_cfg, write_claim) -> None:
    for i in range(CLUSTER_MIN):
        write_claim(digest_cfg, f"clm_orphan{i:02d}")
    assert TaxonomyDriftPass().run(digest_cfg, client=None) == []


def test_habits_yaml_override_is_respected(digest_cfg, write_claim) -> None:
    # Write a habits.yaml that includes "papers/security" as a root.
    habits_yaml = "\n".join(
        [
            "identity: {name: '', primary_language: en}",
            "taxonomy:",
            "  roots: [papers/security]",
            "  enforce: soft",
            "naming_convention: {source_slug: 'x', claim_slug: 'y', max_slug_length: 80}",
            "extraction:",
            "  default_density: moderate",
            "  by_taxonomy: {}",
            "  by_kind: {}",
            "  claim_rubric: ''",
            "  confidence_policy: {require_quote_for_extracted: true, max_inferred_per_source: 20}",
            "retrieval:",
            "  prefer: claims",
            "  default_k: 10",
            "  default_scope: both",
            "  max_depth_content: 1",
            "  mode: bm25",
            "  embedding_model: local",
            "  rrf_k: 60",
            "injection:",
            "  enabled: true",
            "  k: 5",
            "  max_tokens: 800",
            "  min_score: 0.2",
            "  skip_patterns: []",
            "conflicts: {grace_period_days: 14, cluster_threshold: 3}",
            "repo_capture: {globs: [], exclude_globs: []}",
            "autonomy: {default: hitl, overrides: {}}",
            "learning: {enabled: true, threshold_overrides: 3, rolling_window_days: 90, dimensions: []}",
            "maintenance: {nightly: {enabled: true, time: '03:30', tasks: []}}",
            "digest: {enabled: false, passes: {}, min_entries_to_emit: 0, skip_ttl_days: 14}",
            "",
        ]
    )
    (digest_cfg.sb_dir / "habits.yaml").write_text(habits_yaml, encoding="utf-8")

    for i in range(CLUSTER_MIN):
        sid = f"src_sec{i:02d}"
        _write_source(digest_cfg, sid, "papers/security/thing")
        write_claim(digest_cfg, f"clm_sec{i:02d}")
        path = digest_cfg.claims_dir / f"clm_sec{i:02d}.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("supports: []", f"supports: ['{sid}']"),
            encoding="utf-8",
        )

    # With papers/security configured, this cluster is no longer drift.
    assert TaxonomyDriftPass().run(digest_cfg, client=None) == []
