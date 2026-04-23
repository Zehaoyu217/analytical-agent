from __future__ import annotations

from datetime import UTC, datetime

from second_brain.config import Config
from second_brain.frontmatter import dump_document
from second_brain.load import load_node
from second_brain.reindex import reindex
from second_brain.research.broker import broker_search
from second_brain.research.compiler import compile_center
from second_brain.research.obsidian import export_obsidian_view
from second_brain.research.schema import load_center_document
from second_brain.research.writeback import record_experiment, record_project
from second_brain.schema.claim import ClaimConfidence, ClaimFrontmatter, ClaimKind
from second_brain.schema.source import SourceFrontmatter, SourceKind
from second_brain.store.fts_store import FtsStore


def _seed_source(cfg: Config) -> None:
    folder = cfg.sources_dir / "src_attention"
    folder.mkdir(parents=True, exist_ok=True)
    dump_document(
        folder / "_source.md",
        SourceFrontmatter(
            id="src_attention",
            title="Attention Is All You Need",
            kind=SourceKind.NOTE,
            authors=["Vaswani et al."],
            year=2017,
            source_url=None,
            tags=["papers/ml"],
            ingested_at=datetime.now(tz=UTC),
            content_hash="sha256:attention",
            habit_taxonomy="papers/ml",
            raw=[],
            cites=[],
            related=[],
            supersedes=[],
            abstract="Transformers replace recurrence with self-attention.",
        ).to_frontmatter_dict(),
        "# Architecture\n\n<!-- page: 1 -->\nSelf-attention removes recurrence from sequence transduction.\n",
    )


def _seed_claim(cfg: Config) -> None:
    dump_document(
        cfg.claims_dir / "attention-claim.md",
        ClaimFrontmatter(
            id="clm_attention",
            statement="Self-attention can replace recurrence for translation tasks.",
            kind=ClaimKind.EMPIRICAL,
            confidence=ClaimConfidence.HIGH,
            supports=["src_attention"],
            contradicts=[],
            refines=[],
            extracted_at=datetime.now(tz=UTC),
            abstract="The transformer architecture outperforms recurrent baselines.",
        ).to_frontmatter_dict(),
        "This claim is grounded in the transformer paper.\n",
    )


def test_compile_center_creates_paper_cards(sb_home) -> None:
    cfg = Config.load()
    _seed_source(cfg)
    _seed_claim(cfg)

    report = compile_center(cfg)

    assert report.created == 1
    paper = cfg.papers_dir / "attention-is-all-you-need.md"
    assert paper.exists()
    text = paper.read_text(encoding="utf-8")
    assert "[[src_attention]]" in text
    assert "[[clm_attention]]" in text


def test_compile_center_summary_skips_page_markers_and_abstract_heading(sb_home) -> None:
    cfg = Config.load()
    folder = cfg.sources_dir / "src_selection"
    folder.mkdir(parents=True, exist_ok=True)
    dump_document(
        folder / "_source.md",
        SourceFrontmatter(
            id="src_selection",
            title="Selection Paper",
            kind=SourceKind.PDF,
            authors=[],
            year=2026,
            source_url=None,
            tags=["papers/ml"],
            ingested_at=datetime.now(tz=UTC),
            content_hash="sha256:selection",
            habit_taxonomy="papers/ml",
            raw=[],
            cites=[],
            related=[],
            supersedes=[],
            abstract="",
        ).to_frontmatter_dict(),
        "\n".join(
            [
                "<!-- page: 1 -->",
                "",
                "# Selection Paper",
                "",
                "Jane Doe University",
                "",
                "Abstract",
                "",
                "This paper studies doubly robust estimators under sample selection.",
                "",
            ]
        ),
    )

    compile_center(cfg)

    meta, _body = load_center_document(cfg.papers_dir / "selection-paper.md")
    assert meta.summary == "This paper studies doubly robust estimators under sample selection."


def test_compile_center_summary_skips_toc_like_paragraphs(sb_home) -> None:
    cfg = Config.load()
    folder = cfg.sources_dir / "src_book"
    folder.mkdir(parents=True, exist_ok=True)
    dump_document(
        folder / "_source.md",
        SourceFrontmatter(
            id="src_book",
            title="Causal Inference Book",
            kind=SourceKind.PDF,
            authors=[],
            year=2026,
            source_url=None,
            tags=["papers/ml"],
            ingested_at=datetime.now(tz=UTC),
            content_hash="sha256:book",
            habit_taxonomy="papers/ml",
            raw=[],
            cites=[],
            related=[],
            supersedes=[],
            abstract="",
        ).to_frontmatter_dict(),
        "\n".join(
            [
                "<!-- page: 1 -->",
                "",
                "# Causal Inference Book",
                "",
                "Table of Contents",
                "",
                "- 1.1 Difference-in-means estimation . . . . . . . . . . . . . . . . . . . 4",
                "- 1.2 Regression adjustments in randomized trials . . . . . . . . . . . . 10",
                "",
                "<!-- page: 2 -->",
                "",
                "This book introduces causal inference from a statistical learning perspective and develops modern estimators for observational and experimental data.",
                "",
            ]
        ),
    )

    compile_center(cfg)

    meta, _body = load_center_document(cfg.papers_dir / "causal-inference-book.md")
    assert meta.summary == (
        "This book introduces causal inference from a statistical learning perspective "
        "and develops modern estimators for observational and experimental data."
    )


def test_reindex_indexes_center_nodes_and_broker_returns_paper(sb_home) -> None:
    cfg = Config.load()
    _seed_source(cfg)
    _seed_claim(cfg)
    compile_center(cfg)
    record_project(
        cfg,
        title="Transformer Scaling",
        question="Should we prioritize transformer architectures for the current project?",
        paper_ids=["paper_attention-is-all-you-need"],
    )
    record_experiment(
        cfg,
        title="Transformer baseline",
        project_ids=["project_transformer-scaling"],
        paper_ids=["paper_attention-is-all-you-need"],
        claim_ids=["clm_attention"],
        hypothesis="A transformer baseline should outperform a recurrent baseline.",
        result_summary="Initial offline metrics improved.",
        decision="Keep transformer family in the candidate set.",
    )
    reindex(cfg)

    with FtsStore.open(cfg.fts_path) as store:
        rows = store.search_centers('"attention"', k=5)
        chunk_rows = store.search_chunks('"sequence"', k=5)
    assert any(row[0] == "paper_attention-is-all-you-need" for row in rows)
    assert chunk_rows
    assert chunk_rows[0][1] == "src_attention"

    loaded = load_node(cfg, "paper_attention-is-all-you-need", depth=1)
    assert loaded.root["kind"] == "paper"
    chunk = load_node(cfg, "chk_attention_001", depth=0)
    assert chunk.root["kind"] == "chunk"
    assert chunk.root["page_start"] == 1

    result = broker_search(
        cfg,
        query="should we use attention for sequence transduction?",
        k=5,
        project_id="project_transformer-scaling",
    )
    assert result.hits
    ids = [hit.id for hit in result.hits[:3]]
    assert "project_transformer-scaling" in ids
    assert "paper_attention-is-all-you-need" in ids
    paper_hit = next(hit for hit in result.hits if hit.id == "paper_attention-is-all-you-need")
    assert any(ev.id == "src_attention" for ev in paper_hit.evidence)
    chunk_evidence = next(ev for ev in paper_hit.evidence if ev.kind == "chunk")
    assert chunk_evidence.source_id == "src_attention"
    assert chunk_evidence.page_start == 1


def test_export_obsidian_view_creates_hub_pages(sb_home) -> None:
    cfg = Config.load()
    _seed_source(cfg)
    compile_center(cfg)
    record_project(cfg, title="Transformer Scaling", question="What should we test next?")
    reindex(cfg)

    target = export_obsidian_view(cfg)

    assert (target / "Home.md").exists()
    assert (target / "Index" / "By Paper.md").exists()
    assert (target / "Papers" / "paper_attention-is-all-you-need.md").exists()
    assert (cfg.sources_dir / "src_attention" / "chunk_manifest.json").exists()
