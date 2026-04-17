from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ...schema import GraphSnapshot
from .schema import EXTENSION_TAG, ExtractedEdge, ExtractedNode, ExtractionResult

ExtractorFn = Callable[[Path, GraphSnapshot], ExtractionResult]


def augment(repo_root: Path, extractors: list[tuple[str, ExtractorFn]]) -> dict:
    """Run extractors, dedupe, write graph.augmented.json + manifest. Return manifest."""
    graph = GraphSnapshot.load(repo_root)
    nodes_by_id: dict[str, dict] = {}
    edges: list[dict] = []
    edge_keys: set[tuple[str, str, str]] = set()
    failures: list[str] = []
    files_skipped: list[str] = []

    for name, fn in extractors:
        try:
            result = fn(repo_root, graph)
        except Exception as exc:  # noqa: BLE001 — extractor isolation by design
            failures.append(f"{name}: {exc!r}")
            continue
        for node in result.nodes:
            nodes_by_id.setdefault(node.id, _node_to_dict(node))
        for edge in result.edges:
            key = (edge.source, edge.target, edge.relation)
            if key in edge_keys:
                continue
            edge_keys.add(key)
            edges.append(_edge_to_dict(edge))
        failures.extend(result.failures)
        files_skipped.extend(result.files_skipped)

    out_path = repo_root / "graphify" / "graph.augmented.json"
    out_path.write_text(
        json.dumps(
            {"nodes": list(nodes_by_id.values()), "links": edges},
            indent=2,
            sort_keys=True,
        )
    )

    manifest = {
        "extension": EXTENSION_TAG,
        "extractors": [name for name, _ in extractors],
        "nodes_emitted": len(nodes_by_id),
        "edges_emitted": len(edges),
        "files_skipped": sorted(set(files_skipped)),
        "failures": failures,
    }
    (repo_root / "graphify" / "graph.augmented.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True)
    )
    return manifest


def _node_to_dict(node: ExtractedNode) -> dict:
    return {
        "id": node.id,
        "label": node.label,
        "file_type": node.file_type,
        "source_file": node.source_file,
        "source_location": node.source_location,
        "extension": EXTENSION_TAG,
        "extractor": node.extractor,
    }


def _edge_to_dict(edge: ExtractedEdge) -> dict:
    return {
        "source": edge.source,
        "target": edge.target,
        "relation": edge.relation,
        "confidence": edge.confidence,
        "confidence_score": edge.confidence_score,
        "source_file": edge.source_file,
        "source_location": edge.source_location,
        "extension": EXTENSION_TAG,
        "extractor": edge.extractor,
    }
