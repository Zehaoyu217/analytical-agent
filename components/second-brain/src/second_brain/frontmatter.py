from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML(typ="rt")
_yaml.default_flow_style = False
_yaml.width = 10_000  # avoid wrapping long URLs / titles

_DELIM = "---\n"


def load_document(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith(_DELIM):
        raise ValueError(f"{path}: missing frontmatter (must start with '---')")
    # Split after the *second* delimiter line.
    remainder = text[len(_DELIM):]
    end = remainder.find("\n" + _DELIM.rstrip() + "\n")
    if end < 0:
        # Allow file that is *only* frontmatter + trailing newline.
        end = remainder.find("\n" + _DELIM.rstrip())
        if end < 0:
            raise ValueError(f"{path}: unterminated frontmatter")
    yaml_block = remainder[:end]
    body_start = end + len("\n" + _DELIM.rstrip() + "\n")
    body = remainder[body_start:] if body_start <= len(remainder) else ""
    meta = _yaml.load(yaml_block) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    return dict(meta), body


def dump_document(path: Path, meta: dict[str, Any], body: str) -> None:
    buf = io.StringIO()
    _yaml.dump(dict(meta), buf)
    rendered_yaml = buf.getvalue()
    path.write_text(f"---\n{rendered_yaml}---\n{body}", encoding="utf-8")
