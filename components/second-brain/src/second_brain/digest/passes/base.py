"""Pass protocol — every digest pass conforms to this shape.

A Pass has:

- `prefix`: single-char tag ("r", "w", "t", "s", "e") used by the Builder to
  compose stable entry ids like "r01", "w02".
- `section`: human-readable section heading for the rendered digest.
- `run(cfg, client)`: returns `list[DigestEntry]` with `id=""` (or a local
  counter). The Builder rewrites ids before rendering. `client` is an optional
  Anthropic-shaped client — pure passes ignore it.

The protocol is `runtime_checkable` so the Builder can validate registered
passes cheaply and so tests can pass simple objects as fakes.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from second_brain.config import Config
from second_brain.digest.schema import DigestEntry


@runtime_checkable
class Pass(Protocol):
    prefix: str
    section: str

    def run(self, cfg: Config, client: Any | None) -> list[DigestEntry]: ...
