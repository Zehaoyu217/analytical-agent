from __future__ import annotations

from unittest.mock import MagicMock

from app.api.chat_api import _make_client
from app.harness.clients.mlx_client import MLXClient


def test_make_client_routes_mlx_prefix() -> None:
    client = _make_client("mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit", MagicMock())
    assert isinstance(client, MLXClient)
