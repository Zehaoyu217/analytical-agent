"""RoutesBuilder — re-export route nodes from GraphSnapshot.

Plugin A's ``fastapi_routes`` extractor populates
``graphify/graph.augmented.json`` with ``route::METHOD::/path`` nodes.
We just project the relevant fields. No graph → empty list + failure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ....schema import GraphSnapshot


@dataclass(frozen=True)
class RouteEntry:
    id: str
    method: str
    path: str
    source_file: str | None
    source_location: int | None
    extractor: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "method": self.method, "path": self.path,
            "source_file": self.source_file, "source_location": self.source_location,
            "extractor": self.extractor,
        }


def _parse_route_id(node_id: str) -> tuple[str, str] | None:
    """``"route::POST::/api/trace"`` → ``("POST", "/api/trace")`` or None."""
    parts = node_id.split("::", 2)
    if len(parts) != 3 or parts[0] != "route":
        return None
    return parts[1], parts[2]


class RoutesBuilder:
    def __init__(self, graph: GraphSnapshot) -> None:
        self.graph = graph

    def build(self) -> tuple[list[RouteEntry], list[str]]:
        entries: list[RouteEntry] = []
        failures: list[str] = []

        if not self.graph.nodes:
            failures.append("routes: graph.augmented.json absent — routes inventory is empty")
            return entries, failures

        for node in self.graph.nodes:
            node_id = str(node.get("id", ""))
            parsed = _parse_route_id(node_id)
            if parsed is None:
                continue
            method, path = parsed
            entries.append(RouteEntry(
                id=node_id,
                method=method,
                path=path,
                source_file=node.get("source_file"),
                source_location=node.get("source_location"),
                extractor=str(node.get("extractor", "fastapi_routes")),
            ))

        return entries, failures
