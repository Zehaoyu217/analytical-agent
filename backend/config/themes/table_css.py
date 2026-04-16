"""Table CSS theme for HTML report rendering.

Returns a ``<style>`` block that matches the Swiss/Terminal aesthetic:
dark surfaces, monospace type, orange accent highlights.
"""
from __future__ import annotations

_TABLE_CSS = """
.ga-table {
  border-collapse: collapse;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 13px;
  width: 100%;
}
.ga-table th, .ga-table td {
  border: 1px solid #2a2a2e;
  padding: 4px 10px;
  text-align: left;
  white-space: nowrap;
}
.ga-table th {
  background: #18181b;
  color: #a0a0a8;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.ga-table tr:nth-child(even) { background: #111114; }
.ga-table tr:hover { background: #1f1f23; }
.ga-table .cell-num { text-align: right; font-variant-numeric: tabular-nums; }
.ga-table .cell-muted { color: #555; font-style: italic; }
.ga-table .cell-positive { color: #4caf7d; }
.ga-table .cell-negative { color: #e05252; }
.ga-table caption {
  caption-side: top;
  text-align: left;
  padding: 0 0 8px 0;
  font-size: 12px;
  color: #71717a;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
""".strip()


def render_table_css(variant: str = "light") -> str:
    """Return a ``<style>`` block for the requested variant."""
    return f"<style>\n{_TABLE_CSS}\n</style>"
