from __future__ import annotations

from pathlib import Path

from config.themes.theme_switcher import ThemeTokens


def render_table_css(variant: str = "light", tokens_path: Path | None = None) -> str:
    path = tokens_path or (Path(__file__).parent / "tokens.yaml")
    tokens = ThemeTokens.load(path).for_variant(variant)
    typography = ThemeTokens.load(path).typography
    sans = typography["sans"]
    base = typography["scale"]["base"]
    sm = typography["scale"]["sm"]

    css = f"""<style>
.ga-table {{
  font-family: {sans};
  font-size: {base}px;
  color: {tokens.surface("text")};
  background: {tokens.surface("base")};
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}}
.ga-table thead th {{
  background: {tokens.surface("panel")};
  color: {tokens.surface("text")};
  text-align: left;
  font-weight: {typography["weight"]["semibold"]};
  border-bottom: 2px solid {tokens.surface("border")};
  padding: 6px 10px;
  font-size: {sm}px;
}}
.ga-table tbody td {{
  border-bottom: 1px solid {tokens.surface("grid")};
  padding: 5px 10px;
  font-size: {sm}px;
}}
.ga-table tbody tr:hover {{ background: {tokens.surface("panel")}; }}
.ga-table .cell-num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.ga-table .cell-positive {{ color: {tokens.semantic("positive")}; font-weight: 500; }}
.ga-table .cell-negative {{ color: {tokens.semantic("negative")}; font-weight: 500; }}
.ga-table .cell-warning  {{ color: {tokens.semantic("warning")}; }}
.ga-table .cell-muted    {{ color: {tokens.surface("text_muted")}; }}
.ga-table caption {{
  text-align: left;
  caption-side: top;
  font-weight: {typography["weight"]["semibold"]};
  color: {tokens.surface("text")};
  padding-bottom: 4px;
}}
</style>"""
    return css
