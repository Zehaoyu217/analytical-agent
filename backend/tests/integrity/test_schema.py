from __future__ import annotations
import json
from pathlib import Path

from backend.app.integrity.schema import GraphSnapshot


def test_graph_snapshot_loads_from_graphify_dir(tmp_path: Path) -> None:
    graph_dir = tmp_path / "graphify"
    graph_dir.mkdir()
    payload = {"nodes": [{"id": "a"}, {"id": "b"}], "links": [{"source": "a", "target": "b"}]}
    (graph_dir / "graph.json").write_text(json.dumps(payload))

    snap = GraphSnapshot.load(tmp_path)

    assert snap.nodes == payload["nodes"]
    assert snap.links == payload["links"]


def test_graph_snapshot_load_missing_file_raises(tmp_path: Path) -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        GraphSnapshot.load(tmp_path)
