from pathlib import Path

from click.testing import CliRunner

from second_brain.cli import cli


def _seed_source(home: Path, slug: str, taxonomy: str, kind: str = "pdf") -> None:
    src_dir = home / "sources" / slug
    src_dir.mkdir(parents=True)
    (src_dir / "raw").mkdir()
    fm = "\n".join([
        "---",
        f"id: {slug}",
        f"title: '{slug}'",
        f"kind: {kind}",
        "authors: []",
        "year: 2024",
        "source_url: null",
        "tags: []",
        "ingested_at: 2024-01-01T00:00:00Z",
        "content_hash: sha256:abc",
        f"habit_taxonomy: {taxonomy}",
        "raw: []",
        "cites: []",
        "related: []",
        "supersedes: []",
        "abstract: ''",
        "---",
    ])
    (src_dir / "_source.md").write_text(fm + "\n\nbody\n", encoding="utf-8")


def test_sb_extract_uses_habits_density_when_not_supplied(tmp_path, monkeypatch):
    home = tmp_path / "sb"
    (home / ".sb").mkdir(parents=True)
    monkeypatch.setenv("SECOND_BRAIN_HOME", str(home))
    monkeypatch.setenv("SB_FAKE_CLAIMS", "[]")  # fake empty extraction, keeps run green
    monkeypatch.setenv("SB_DENSITY_PROBE", "1")  # see cli change below
    _seed_source(home, "src_paper", taxonomy="papers/ml")
    _seed_source(home, "src_blogpost", taxonomy="blog/web")
    runner = CliRunner()

    res_paper = runner.invoke(cli, ["extract", "src_paper"])
    res_blog = runner.invoke(cli, ["extract", "src_blogpost"])
    assert res_paper.exit_code == 0, res_paper.output
    assert res_blog.exit_code == 0, res_blog.output
    # The probe prints the resolved density so we can assert without touching extractor internals.
    assert "density=dense" in res_paper.output
    assert "density=sparse" in res_blog.output
