from pathlib import Path

from second_brain.config import Config
from second_brain.frontmatter import load_document
from second_brain.reconcile.client import ReconcileResponse
from second_brain.reconcile.finder import OpenDebate
from second_brain.reconcile.writer import write_resolution


def _init_cfg(tmp_path: Path) -> Config:
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    (home / "claims").mkdir()
    return Config(home=home, sb_dir=home / ".sb")


def _seed_claim(cfg: Config, slug: str, *, contradicts: list[str]) -> None:
    body = "\n".join([
        "---",
        f"id: {slug}",
        f"statement: 'stmt for {slug}'",
        "kind: empirical",
        "confidence: high",
        "scope: ''",
        f"contradicts: {contradicts}",
        "supports: []",
        "refines: []",
        "extracted_at: 2024-01-01T00:00:00Z",
        "status: active",
        "resolution: null",
        "abstract: ''",
        "---",
        "",
    ])
    (cfg.claims_dir / f"{slug}.md").write_text(body, encoding="utf-8")


def test_write_resolution_persists_note_and_updates_primary(tmp_path):
    cfg = _init_cfg(tmp_path)
    _seed_claim(cfg, "clm_a", contradicts=["clm_b"])
    _seed_claim(cfg, "clm_b", contradicts=["clm_a"])

    debate = OpenDebate(
        left_id="clm_a", right_id="clm_b",
        left_path=str(cfg.claims_dir / "clm_a.md"),
        right_path=str(cfg.claims_dir / "clm_b.md"),
    )
    resp = ReconcileResponse(
        resolution_md="The two claims differ in scope.",
        applies_where="scope",
        primary_claim_id="clm_a",
    )
    rel = write_resolution(cfg, debate, resp)

    # Resolution note exists at the expected relative path.
    assert rel.startswith("claims/resolutions/")
    assert (cfg.home / rel).exists()
    # Primary claim's frontmatter now points at the note.
    primary_meta, _ = load_document(cfg.claims_dir / "clm_a.md")
    assert primary_meta["resolution"] == rel
    # Other side left untouched.
    other_meta, _ = load_document(cfg.claims_dir / "clm_b.md")
    assert other_meta.get("resolution") in (None, "null", "")
