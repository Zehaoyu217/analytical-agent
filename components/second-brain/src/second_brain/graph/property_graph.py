from __future__ import annotations

import duckdb

from second_brain.graph.extension import ensure_duckpgq
from second_brain.schema.edges import RelationType

_EDGE_LABELS = [r.value for r in RelationType]


def create_property_graph(conn: duckdb.DuckDBPyConnection) -> bool:
    """Create the sb_graph property graph view. Returns False if DuckPGQ unavailable."""
    try:
        ensure_duckpgq(conn)
    except duckdb.Error:
        return False

    conn.execute("DROP PROPERTY GRAPH IF EXISTS sb_graph")

    # DuckPGQ requires one EDGE TABLES clause per relation label.
    edge_clauses = []
    for label in _EDGE_LABELS:
        edge_clauses.append(
            f"""(SELECT src_id, dst_id, rationale, confidence_edge
                 FROM edges WHERE relation = '{label}')
              AS {label}
              SOURCE KEY (src_id) REFERENCES sources(id)
              DESTINATION KEY (dst_id) REFERENCES sources(id)
              LABEL {label}"""
        )
    # Fallback: edges between claims/sources — DuckPGQ resolves references against
    # whichever vertex table has the matching id.  We define both vertex tables
    # and let the planner pick.
    ddl = f"""
    CREATE PROPERTY GRAPH sb_graph
    VERTEX TABLES (sources, claims)
    EDGE TABLES (
      {",".join(edge_clauses)}
    )
    """
    conn.execute(ddl)
    return True
