from __future__ import annotations
import json
from pathlib import Path

from backend.app.integrity.plugins.graph_extension.augmenter import augment
from backend.app.integrity.plugins.graph_extension.schema import (
    ExtractedEdge,
    ExtractedNode,
    ExtractionResult,
)


def _seed_graph(tmp_path: Path) -> None:
    g = tmp_path / "graphify"
    g.mkdir()
    (g / "graph.json").write_text(json.dumps({"nodes": [], "links": []}))


def test_augment_with_no_extractors_writes_empty_outputs(tmp_path: Path) -> None:
    _seed_graph(tmp_path)
    manifest = augment(tmp_path, extractors=[])

    out = json.loads((tmp_path / "graphify" / "graph.augmented.json").read_text())
    assert out == {"nodes": [], "links": []}
    assert manifest["nodes_emitted"] == 0
    assert manifest["edges_emitted"] == 0
    assert manifest["extension"] == "cca-v1"


def test_augment_dedupes_nodes_by_id_and_edges_by_triple(tmp_path: Path) -> None:
    _seed_graph(tmp_path)

    def ext_a(repo, graph):
        return ExtractionResult(
            nodes=[ExtractedNode("n1", "L1", "code", "a.py", 1, "fastapi_routes")],
            edges=[ExtractedEdge("n1", "n2", "calls", "a.py", 1, "fastapi_routes")],
        )

    def ext_b(repo, graph):
        return ExtractionResult(
            nodes=[ExtractedNode("n1", "L1-dup", "code", "a.py", 1, "intra_file_calls")],
            edges=[ExtractedEdge("n1", "n2", "calls", "a.py", 5, "intra_file_calls")],
        )

    augment(tmp_path, extractors=[("a", ext_a), ("b", ext_b)])
    out = json.loads((tmp_path / "graphify" / "graph.augmented.json").read_text())
    assert len(out["nodes"]) == 1  # node id deduped
    assert len(out["links"]) == 1  # (source, target, relation) deduped
    assert out["nodes"][0]["extension"] == "cca-v1"


def test_augment_records_extractor_failure_in_manifest(tmp_path: Path) -> None:
    _seed_graph(tmp_path)

    def explode(repo, graph):
        raise RuntimeError("boom")

    manifest = augment(tmp_path, extractors=[("bad", explode)])
    assert any("boom" in f for f in manifest["failures"])


def test_augment_is_idempotent(tmp_path: Path) -> None:
    _seed_graph(tmp_path)

    def ext(repo, graph):
        return ExtractionResult(
            nodes=[ExtractedNode("n1", "L1", "code", "a.py", 1, "fastapi_routes")],
            edges=[],
        )

    augment(tmp_path, extractors=[("a", ext)])
    first = (tmp_path / "graphify" / "graph.augmented.json").read_bytes()
    augment(tmp_path, extractors=[("a", ext)])
    second = (tmp_path / "graphify" / "graph.augmented.json").read_bytes()
    assert first == second
