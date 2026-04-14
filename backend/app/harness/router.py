from __future__ import annotations

from collections.abc import Callable

from app.harness.clients.base import ModelClient
from app.harness.config import HarnessConfig, ModelProfile


class ModelRouter:
    def __init__(
        self,
        config: HarnessConfig,
        client_factory: Callable[[ModelProfile], ModelClient],
    ) -> None:
        self._config = config
        self._factory = client_factory
        self._cache: dict[str, ModelClient] = {}

    def _client_for_model(self, name: str) -> ModelClient:
        if name not in self._config.models:
            raise KeyError(f"model '{name}' not declared")
        if name not in self._cache:
            self._cache[name] = self._factory(self._config.models[name])
        return self._cache[name]

    def for_role(self, role: str) -> ModelClient:
        if role not in self._config.roles:
            raise KeyError(f"role '{role}' not configured")
        return self._client_for_model(self._config.roles[role])

    def retry_client(self) -> ModelClient | None:
        target = self._config.guardrails.retry_on_gate_block
        return self._client_for_model(target) if target else None

    def warm_up(self) -> None:
        for name in self._config.warmup:
            self._client_for_model(name).warmup()

    @property
    def config(self) -> HarnessConfig:
        return self._config
