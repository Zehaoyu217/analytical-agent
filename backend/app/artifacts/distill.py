from __future__ import annotations

from html.parser import HTMLParser

from app.artifacts.models import Artifact

MAX_TABLE_HTML_BYTES_FOR_DISTILL = 500_000  # cap to prevent pathological HTMLParser slowdowns


def _round(v: str) -> str:
    try:
        f = float(v.replace(",", ""))
        return str(int(f)) if f == int(f) else f"{f:.2f}"
    except (ValueError, AttributeError):
        return v


def _distill_chart(a: Artifact) -> str:
    cd = a.chart_data or {}
    mark_raw = cd.get("mark", "unknown")
    mark = mark_raw["type"] if isinstance(mark_raw, dict) else str(mark_raw)
    encodings: list[str] = []
    for ch in ("x", "y", "color", "size", "column", "row"):
        enc = cd.get(ch, {})
        if isinstance(enc, dict) and "field" in enc:
            encodings.append(f"{ch}={enc['field']}")
    enc_str = ", ".join(encodings) or "no encodings"
    out = f"- [chart] '{a.name or a.id}' \"{a.title}\" — mark={mark}, {enc_str}"
    ds = cd.get("data_sample", {})
    if isinstance(ds, dict) and ds:
        cols = list(ds.keys())
        col_values = [ds[c] for c in cols]
        rows = list(zip(*col_values))
        n_rows = int(cd.get("data_rows", len(rows) or 0))
        if rows:
            header = ",".join(str(c) for c in cols)
            body = "\n  ".join(",".join(_round(str(v)) for v in r) for r in rows)
            out += f"\n  {header}\n  {body}"
            if n_rows > len(rows):
                out += f"\n  ... [{n_rows - len(rows)} rows truncated]"
    return out


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] = []
        self._in_cell = False
        self._text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._text = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._row.append(self._text.strip())
            self._in_cell = False
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = []

    def handle_data(self, data):
        if self._in_cell:
            self._text += data


def _distill_table(a: Artifact, max_rows: int = 50) -> str:
    row_info = ""
    if a.total_rows is not None:
        row_info = f", {a.total_rows} rows"
        if a.displayed_rows is not None and a.displayed_rows < a.total_rows:
            row_info += f", displayed {a.displayed_rows}"
    summary = f"- [table] '{a.name or a.id}' \"{a.title}\"{row_info}"
    if a.content:
        p = _TableParser()
        try:
            p.feed(a.content[:MAX_TABLE_HTML_BYTES_FOR_DISTILL])
            if p.rows:
                header = p.rows[0]
                body = p.rows[1 : max_rows + 1]
                truncated = max(0, len(p.rows) - 1 - len(body))
                def fmt(cells: list[str], is_header: bool = False) -> str:
                    vals = cells if is_header else [_round(c) for c in cells]
                    return ",".join(v.replace(",", ";") for v in vals)
                preview = "\n  " + fmt(header, True) + "\n  " + "\n  ".join(fmt(r) for r in body)
                if truncated > 0:
                    preview += f"\n  ... [{truncated} rows truncated]"
                summary += preview
        except Exception:  # noqa: BLE001
            pass
    return summary


def _distill_profile(a: Artifact) -> str:
    if a.profile_summary:
        return f"- [profile] '{a.name or a.id}' \"{a.title}\" — {a.profile_summary}"
    return f"- [profile] '{a.name or a.id}' \"{a.title}\" — (no summary available)"


def _distill_generic(a: Artifact) -> str:
    return f"- [{a.type}] '{a.name or a.id}' \"{a.title}\""


def distill_artifact(a: Artifact) -> str:
    if a.type == "chart":
        return _distill_chart(a)
    if a.type == "table":
        return _distill_table(a)
    if a.type == "profile":
        return _distill_profile(a)
    return _distill_generic(a)


def format_artifacts_for_compaction(artifacts: list[Artifact]) -> str:
    if not artifacts:
        return ""
    lines = [f"## Artifacts ({len(artifacts)} total)"]
    lines.extend(distill_artifact(a) for a in artifacts)
    return "\n".join(lines)
