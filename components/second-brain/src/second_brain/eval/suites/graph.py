"""Graph eval suite: BFS walk over in-memory fixture edges.

The suite does NOT touch ``graph.duckdb`` — it builds an adjacency map from
``seed.yaml`` and runs BFS constrained to the query's relation and max depth.
Keeping the suite hermetic means it can run in CI without any prior ingest /
reindex steps.
"""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

from ruamel.yaml import YAML

from second_brain.config import Config
from second_brain.eval.runner import EvalCase

_yaml = YAML(typ="safe")


class GraphSuite:
    name = "graph"

    def run(self, cfg: Config, fixtures_dir: Path) -> list[EvalCase]:
        seed = _yaml.load(
            (fixtures_dir / "seed.yaml").read_text(encoding="utf-8")
        )
        adjacency: dict[tuple[str, str], list[str]] = defaultdict(list)
        for e in seed["graph"]["edges"]:
            adjacency[(e["src"], e["relation"])].append(e["dst"])

        cases: list[EvalCase] = []
        for q in seed["queries"]:
            visited: set[str] = set()
            queue: deque[tuple[str, int]] = deque([(q["start"], 0)])
            while queue:
                node, d = queue.popleft()
                if d >= q["depth"]:
                    continue
                for nxt in adjacency.get((node, q["relation"]), []):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append((nxt, d + 1))
            expected = set(q["expected"])
            passed = visited == expected
            cases.append(
                EvalCase(
                    name=f"{q['start']}-{q['relation']}-d{q['depth']}",
                    passed=passed,
                    metric=1.0 if passed else 0.0,
                    details=(
                        f"got={sorted(visited)} expected={sorted(expected)}"
                    ),
                )
            )
        return cases
