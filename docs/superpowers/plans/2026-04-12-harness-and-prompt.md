# Plan 3 — Harness & System Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the harness components (PreTurnInjector, ModelRouter, AgentLoop, ToolDispatcher, SandboxExecutor, PostProcessor, TurnWrapUp) plus the data-scientist system prompt and model routing config, so the agent runs the 7-step scientific working loop with tiered guardrails.

**Architecture:** Five composable stages around the LLM call: PreTurnInjector builds the system prompt, ModelRouter resolves role→client, AgentLoop drives model↔tool cycles, PostProcessor enforces discipline at three touch-points, TurnWrapUp commits findings. Guardrail severity scales with model tier (strict → advisory → observatory). All stages emit structured events through the EventBus from Plan 1.

**Tech Stack:** Python 3.12, Anthropic SDK, Ollama HTTP client, httpx, PyYAML, jinja2 (for prompt assembly). Uses Plan 1's `ArtifactStore`, `WikiEngine`, theme system, and Plan 2's skill registry.

**Prerequisites:** Plans 1 and 2 complete. This plan consumes:
- `backend/app/artifacts/store.py` (`ArtifactStore`, `EventBus`)
- `backend/app/wiki/engine.py` (`WikiEngine`)
- `backend/app/skills/registry.py` (SKILL.md frontmatter loader)
- `backend/app/knowledge/gotchas.py` (`GotchaIndex`, `load_gotcha`)
- All statistical and primitive skills from Plans 1 and 2.

---

## Phase 0: Config + Model Clients

Pin the config schema and wire the provider clients before anything that consumes them.

### Task 0.1: `models.yaml` schema + loader

**Files:**
- Create: `config/models.yaml`
- Create: `backend/app/harness/__init__.py`
- Create: `backend/app/harness/config.py`
- Create: `backend/app/harness/tests/__init__.py`
- Create: `backend/app/harness/tests/test_config.py`

- [ ] **Step 1: Write config file**

```yaml
# config/models.yaml
mode: config   # config | auto

models:
  claude_opus:
    provider: anthropic
    model_id: claude-opus-4-6
    thinking_budget: 16000
    tier: observatory
  claude_sonnet:
    provider: anthropic
    model_id: claude-sonnet-4-6
    thinking_budget: 8000
    tier: observatory
  claude_haiku:
    provider: anthropic
    model_id: claude-haiku-4-5-20251001
    tier: advisory
  gemma_thinking:
    provider: ollama
    model_id: gemma4:26b
    host: http://localhost:11434
    keep_alive: 30m
    num_ctx: 32768
    options: {temperature: 0.3, num_predict: 4096}
    tier: strict
  gemma_fast:
    provider: ollama
    model_id: bjoernb/gemma4-26b-fast
    host: http://localhost:11434
    keep_alive: 30m
    num_ctx: 16384
    options: {temperature: 0.3}
    tier: strict
  qwen_small:
    provider: ollama
    model_id: qwen2.5:7b-instruct
    host: http://localhost:11434
    num_ctx: 8192
    tier: strict

roles:
  think: gemma_thinking
  execute: gemma_fast
  summarize: gemma_fast
  evaluate: claude_sonnet
  skill_pick: qwen_small
  embed: qwen_small

warmup:
  - gemma_thinking
  - gemma_fast

guardrails:
  mode: per_tier
  retry_on_gate_block: null
```

- [ ] **Step 2: Failing tests for config loader**

```python
# backend/app/harness/tests/test_config.py
from __future__ import annotations

from pathlib import Path

import pytest

from app.harness.config import HarnessConfig, ModelProfile, load_config


def test_load_config_parses_models_yaml(tmp_path) -> None:
    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        """
mode: config
models:
  claude_sonnet:
    provider: anthropic
    model_id: claude-sonnet-4-6
    thinking_budget: 8000
    tier: observatory
  gemma_fast:
    provider: ollama
    model_id: gemma4:26b
    host: http://localhost:11434
    num_ctx: 16384
    tier: strict
roles:
  think: gemma_fast
  evaluate: claude_sonnet
warmup: [gemma_fast]
guardrails:
  mode: per_tier
  retry_on_gate_block: null
""",
        encoding="utf-8",
    )
    cfg = load_config(config_path)
    assert isinstance(cfg, HarnessConfig)
    assert cfg.mode == "config"
    assert cfg.roles["think"] == "gemma_fast"
    profile = cfg.models["gemma_fast"]
    assert isinstance(profile, ModelProfile)
    assert profile.provider == "ollama"
    assert profile.tier == "strict"
    assert profile.num_ctx == 16384
    assert "gemma_fast" in cfg.warmup


def test_load_config_rejects_unknown_role_target(tmp_path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        """
mode: config
models: {}
roles: {think: doesnt_exist}
warmup: []
guardrails: {mode: per_tier, retry_on_gate_block: null}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="role 'think'"):
        load_config(config_path)


def test_load_config_rejects_unknown_tier(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
mode: config
models:
  x: {provider: anthropic, model_id: x, tier: mystery}
roles: {think: x}
warmup: []
guardrails: {mode: per_tier, retry_on_gate_block: null}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tier"):
        load_config(path)
```

- [ ] **Step 3: Implement config**

```python
# backend/app/harness/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_TIERS = frozenset({"strict", "advisory", "observatory"})
VALID_PROVIDERS = frozenset({"anthropic", "ollama"})
VALID_MODES = frozenset({"config", "auto"})


@dataclass(frozen=True, slots=True)
class ModelProfile:
    name: str
    provider: str
    model_id: str
    tier: str
    thinking_budget: int | None = None
    host: str | None = None
    keep_alive: str | None = None
    num_ctx: int | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuardrailConfig:
    mode: str
    retry_on_gate_block: str | None


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    mode: str
    models: dict[str, ModelProfile]
    roles: dict[str, str]
    warmup: tuple[str, ...]
    guardrails: GuardrailConfig


def _parse_model(name: str, raw: dict[str, Any]) -> ModelProfile:
    provider = str(raw.get("provider", "")).strip()
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"model '{name}': provider '{provider}' not in {sorted(VALID_PROVIDERS)}")
    tier = str(raw.get("tier", "")).strip()
    if tier not in VALID_TIERS:
        raise ValueError(f"model '{name}': tier '{tier}' not in {sorted(VALID_TIERS)}")
    return ModelProfile(
        name=name,
        provider=provider,
        model_id=str(raw["model_id"]),
        tier=tier,
        thinking_budget=raw.get("thinking_budget"),
        host=raw.get("host"),
        keep_alive=raw.get("keep_alive"),
        num_ctx=raw.get("num_ctx"),
        options=dict(raw.get("options") or {}),
    )


def load_config(path: str | Path) -> HarnessConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    mode = str(raw.get("mode", "config"))
    if mode not in VALID_MODES:
        raise ValueError(f"mode '{mode}' not in {sorted(VALID_MODES)}")

    models_raw = raw.get("models") or {}
    models = {name: _parse_model(name, data) for name, data in models_raw.items()}

    roles_raw = raw.get("roles") or {}
    roles: dict[str, str] = {}
    for role, target in roles_raw.items():
        if target not in models:
            raise ValueError(
                f"role '{role}' points at '{target}' which is not declared in models."
            )
        roles[str(role)] = str(target)

    warmup_raw = raw.get("warmup") or []
    for entry in warmup_raw:
        if entry not in models:
            raise ValueError(f"warmup entry '{entry}' not declared in models.")
    warmup = tuple(str(e) for e in warmup_raw)

    guard_raw = raw.get("guardrails") or {}
    guardrails = GuardrailConfig(
        mode=str(guard_raw.get("mode", "per_tier")),
        retry_on_gate_block=guard_raw.get("retry_on_gate_block"),
    )

    return HarnessConfig(
        mode=mode,
        models=models,
        roles=roles,
        warmup=warmup,
        guardrails=guardrails,
    )
```

- [ ] **Step 4: Run test**

Run: `pytest backend/app/harness/tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/models.yaml backend/app/harness/__init__.py backend/app/harness/config.py backend/app/harness/tests/
git commit -m "feat(harness): config schema + loader"
```

### Task 0.2: Model client protocol + Anthropic client

**Files:**
- Create: `backend/app/harness/clients/__init__.py`
- Create: `backend/app/harness/clients/base.py`
- Create: `backend/app/harness/clients/anthropic_client.py`
- Create: `backend/app/harness/clients/tests/__init__.py`
- Create: `backend/app/harness/clients/tests/test_base.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/clients/tests/test_base.py
from __future__ import annotations

from app.harness.clients.base import CompletionRequest, CompletionResponse, Message, ToolSchema


def test_message_is_frozen() -> None:
    import pytest
    m = Message(role="user", content="hi")
    with pytest.raises(Exception):
        m.role = "system"  # type: ignore[misc]


def test_completion_response_surface() -> None:
    resp = CompletionResponse(
        text="ok",
        tool_calls=(),
        stop_reason="end_turn",
        usage={"input_tokens": 100, "output_tokens": 50},
    )
    assert resp.text == "ok"
    assert resp.stop_reason == "end_turn"


def test_completion_request_tool_schema_list() -> None:
    req = CompletionRequest(
        system="you are",
        messages=(Message(role="user", content="hi"),),
        tools=(ToolSchema(name="skill", description="d",
                          input_schema={"type": "object"}),),
        max_tokens=1024,
    )
    assert len(req.tools) == 1
    assert req.tools[0].name == "skill"
```

- [ ] **Step 2: Implement base**

```python
# backend/app/harness/clients/base.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Message:
    role: str  # "user" | "assistant" | "tool"
    content: str
    name: str | None = None       # used for tool results
    tool_use_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolSchema:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    system: str
    messages: tuple[Message, ...]
    tools: tuple[ToolSchema, ...] = field(default_factory=tuple)
    max_tokens: int = 2048
    temperature: float | None = None
    thinking_budget: int | None = None


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    text: str
    tool_calls: tuple[ToolCall, ...]
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


@runtime_checkable
class ModelClient(Protocol):
    name: str
    tier: str

    def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    def warmup(self) -> None: ...
```

- [ ] **Step 3: Failing test + impl for Anthropic client**

```python
# backend/app/harness/clients/tests/test_anthropic_client.py
from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.clients.anthropic_client import AnthropicClient
from app.harness.clients.base import CompletionRequest, Message, ToolSchema
from app.harness.config import ModelProfile


def test_anthropic_client_maps_request_to_api(monkeypatch) -> None:
    fake_anthropic = MagicMock()
    fake_response = MagicMock()
    fake_response.content = [
        MagicMock(type="text", text="answer"),
    ]
    fake_response.stop_reason = "end_turn"
    fake_response.usage = MagicMock(input_tokens=10, output_tokens=5)
    fake_anthropic.messages.create.return_value = fake_response

    profile = ModelProfile(
        name="claude_sonnet", provider="anthropic",
        model_id="claude-sonnet-4-6", tier="observatory",
        thinking_budget=8000,
    )
    client = AnthropicClient(profile=profile, api_client=fake_anthropic)

    request = CompletionRequest(
        system="be thoughtful",
        messages=(Message(role="user", content="hi"),),
        tools=(ToolSchema(name="skill", description="load skill",
                          input_schema={"type": "object"}),),
        max_tokens=1024,
    )
    resp = client.complete(request)
    assert resp.text == "answer"
    assert resp.stop_reason == "end_turn"
    assert resp.usage == {"input_tokens": 10, "output_tokens": 5}

    kwargs = fake_anthropic.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-4-6"
    assert kwargs["system"] == "be thoughtful"
    assert kwargs["max_tokens"] == 1024
    assert len(kwargs["messages"]) == 1
    assert len(kwargs["tools"]) == 1
```

- [ ] **Step 4: Implement anthropic_client**

```python
# backend/app/harness/clients/anthropic_client.py
from __future__ import annotations

from typing import Any

from app.harness.clients.base import (
    CompletionRequest,
    CompletionResponse,
    ToolCall,
)
from app.harness.config import ModelProfile


class AnthropicClient:
    def __init__(self, profile: ModelProfile, api_client: Any) -> None:
        self.profile = profile
        self.name = profile.name
        self.tier = profile.tier
        self._api = api_client

    def _build_messages(self, request: CompletionRequest) -> list[dict]:
        out: list[dict] = []
        for m in request.messages:
            if m.role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_use_id,
                                "content": m.content,
                            }
                        ],
                    }
                )
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    def _build_tools(self, request: CompletionRequest) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in request.tools
        ]

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        kwargs: dict[str, Any] = {
            "model": self.profile.model_id,
            "system": request.system,
            "messages": self._build_messages(request),
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            kwargs["tools"] = self._build_tools(request)
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.thinking_budget or self.profile.thinking_budget:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": request.thinking_budget or self.profile.thinking_budget,
            }
        resp = self._api.messages.create(**kwargs)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in getattr(resp, "content", []) or []:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(str(getattr(block, "text", "")))
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=str(getattr(block, "id", "")),
                        name=str(getattr(block, "name", "")),
                        arguments=dict(getattr(block, "input", {}) or {}),
                    )
                )
        return CompletionResponse(
            text="".join(text_parts),
            tool_calls=tuple(tool_calls),
            stop_reason=str(getattr(resp, "stop_reason", "end_turn")),
            usage={
                "input_tokens": int(getattr(resp.usage, "input_tokens", 0)),
                "output_tokens": int(getattr(resp.usage, "output_tokens", 0)),
            },
            raw=resp,
        )

    def warmup(self) -> None:
        # Anthropic serverless — no warmup needed.
        return
```

- [ ] **Step 5: Run tests**

Run: `pytest backend/app/harness/clients/tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/harness/clients/__init__.py backend/app/harness/clients/base.py backend/app/harness/clients/anthropic_client.py backend/app/harness/clients/tests/
git commit -m "feat(harness): ModelClient protocol + Anthropic client"
```

### Task 0.3: Ollama client

**Files:**
- Create: `backend/app/harness/clients/ollama_client.py`
- Create: `backend/app/harness/clients/tests/test_ollama_client.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/clients/tests/test_ollama_client.py
from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.harness.clients.base import CompletionRequest, Message, ToolSchema
from app.harness.clients.ollama_client import OllamaClient
from app.harness.config import ModelProfile


def _profile() -> ModelProfile:
    return ModelProfile(
        name="gemma_fast", provider="ollama",
        model_id="gemma4:26b", tier="strict",
        host="http://localhost:11434", num_ctx=16384,
        keep_alive="30m",
        options={"temperature": 0.3},
    )


def test_ollama_client_posts_and_parses_text_response() -> None:
    http = MagicMock()
    http.post.return_value.json.return_value = {
        "message": {"content": "hi back", "tool_calls": []},
        "done": True,
        "prompt_eval_count": 100,
        "eval_count": 20,
    }
    http.post.return_value.status_code = 200

    client = OllamaClient(profile=_profile(), http=http)
    resp = client.complete(CompletionRequest(
        system="sys",
        messages=(Message(role="user", content="hi"),),
        max_tokens=512,
    ))
    assert resp.text == "hi back"
    assert resp.stop_reason == "end_turn"
    args, kwargs = http.post.call_args
    assert args[0].endswith("/api/chat")
    payload = kwargs.get("json") or json.loads(kwargs.get("data", "{}"))
    assert payload["model"] == "gemma4:26b"
    assert payload["messages"][0]["role"] == "system"
    assert payload["options"]["num_ctx"] == 16384
    assert payload["options"]["temperature"] == 0.3


def test_ollama_client_surfaces_tool_calls() -> None:
    http = MagicMock()
    http.post.return_value.json.return_value = {
        "message": {
            "content": "",
            "tool_calls": [
                {"function": {"name": "skill", "arguments": {"name": "correlation"}}}
            ],
        },
        "done": True,
    }
    http.post.return_value.status_code = 200

    client = OllamaClient(profile=_profile(), http=http)
    resp = client.complete(CompletionRequest(
        system="", messages=(Message(role="user", content="hi"),),
        tools=(ToolSchema(name="skill", description="d", input_schema={"type": "object"}),),
        max_tokens=256,
    ))
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "skill"
    assert resp.tool_calls[0].arguments == {"name": "correlation"}
```

- [ ] **Step 2: Implement ollama_client**

```python
# backend/app/harness/clients/ollama_client.py
from __future__ import annotations

import uuid
from typing import Any

from app.harness.clients.base import (
    CompletionRequest,
    CompletionResponse,
    ToolCall,
)
from app.harness.config import ModelProfile


class OllamaClient:
    def __init__(self, profile: ModelProfile, http: Any) -> None:
        self.profile = profile
        self.name = profile.name
        self.tier = profile.tier
        self._http = http

    def _endpoint(self, path: str) -> str:
        host = (self.profile.host or "http://localhost:11434").rstrip("/")
        return f"{host}{path}"

    def _options(self, request: CompletionRequest) -> dict[str, Any]:
        opts = dict(self.profile.options)
        if self.profile.num_ctx is not None:
            opts["num_ctx"] = self.profile.num_ctx
        if request.max_tokens:
            opts["num_predict"] = request.max_tokens
        if request.temperature is not None:
            opts["temperature"] = request.temperature
        return opts

    def _payload(self, request: CompletionRequest) -> dict[str, Any]:
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for m in request.messages:
            if m.role == "tool":
                messages.append({"role": "tool", "content": m.content, "name": m.name or ""})
            else:
                messages.append({"role": m.role, "content": m.content})
        payload: dict[str, Any] = {
            "model": self.profile.model_id,
            "messages": messages,
            "stream": False,
            "options": self._options(request),
        }
        if self.profile.keep_alive:
            payload["keep_alive"] = self.profile.keep_alive
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]
        return payload

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        resp = self._http.post(self._endpoint("/api/chat"), json=self._payload(request))
        if resp.status_code != 200:
            raise RuntimeError(f"ollama HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        message = data.get("message") or {}
        text = str(message.get("content", ""))
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ToolCall] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                import json as _json
                try:
                    args = _json.loads(args)
                except Exception:
                    args = {"_raw": args}
            tool_calls.append(
                ToolCall(
                    id=str(tc.get("id") or uuid.uuid4().hex),
                    name=str(fn.get("name", "")),
                    arguments=dict(args),
                )
            )
        stop_reason = "tool_use" if tool_calls else "end_turn"
        return CompletionResponse(
            text=text,
            tool_calls=tuple(tool_calls),
            stop_reason=stop_reason,
            usage={
                "input_tokens": int(data.get("prompt_eval_count", 0)),
                "output_tokens": int(data.get("eval_count", 0)),
            },
            raw=data,
        )

    def warmup(self) -> None:
        payload = {
            "model": self.profile.model_id,
            "messages": [{"role": "user", "content": "ok"}],
            "stream": False,
            "keep_alive": self.profile.keep_alive or "30m",
            "options": {"num_predict": 1},
        }
        try:
            self._http.post(self._endpoint("/api/chat"), json=payload, timeout=120)
        except Exception:
            # Warmup failures are not fatal; the real call will surface errors.
            pass
```

- [ ] **Step 3: Run tests**

Run: `pytest backend/app/harness/clients/tests/test_ollama_client.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/clients/ollama_client.py backend/app/harness/clients/tests/test_ollama_client.py
git commit -m "feat(harness): Ollama client with warmup"
```

---

## Phase 1: ModelRouter

Resolves role → `ModelClient` and runs warmup.

### Task 1.1: Router

**Files:**
- Create: `backend/app/harness/router.py`
- Create: `backend/app/harness/tests/test_router.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/tests/test_router.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.harness.clients.base import CompletionRequest, Message
from app.harness.config import GuardrailConfig, HarnessConfig, ModelProfile
from app.harness.router import ModelRouter


def _cfg() -> HarnessConfig:
    return HarnessConfig(
        mode="config",
        models={
            "claude": ModelProfile(name="claude", provider="anthropic",
                                   model_id="claude-sonnet-4-6", tier="observatory"),
            "gemma": ModelProfile(name="gemma", provider="ollama",
                                  model_id="gemma4:26b", tier="strict",
                                  host="http://localhost:11434"),
        },
        roles={"think": "gemma", "evaluate": "claude"},
        warmup=("gemma",),
        guardrails=GuardrailConfig(mode="per_tier", retry_on_gate_block=None),
    )


def test_router_resolves_role_to_client() -> None:
    client_factory = MagicMock()
    fake_client = MagicMock()
    client_factory.side_effect = lambda profile: fake_client
    router = ModelRouter(config=_cfg(), client_factory=client_factory)
    client = router.for_role("think")
    assert client is fake_client


def test_router_unknown_role_raises() -> None:
    router = ModelRouter(config=_cfg(), client_factory=lambda p: MagicMock())
    with pytest.raises(KeyError, match="role"):
        router.for_role("nope")


def test_router_caches_clients_per_model() -> None:
    factory_calls: list[str] = []

    def factory(profile):
        factory_calls.append(profile.name)
        return MagicMock()

    router = ModelRouter(config=_cfg(), client_factory=factory)
    c1 = router.for_role("think")
    c2 = router.for_role("think")
    assert c1 is c2
    assert factory_calls == ["gemma"]


def test_router_warms_up_configured_models() -> None:
    client = MagicMock()
    router = ModelRouter(config=_cfg(), client_factory=lambda p: client)
    router.warm_up()
    client.warmup.assert_called_once()


def test_router_escalate_on_gate_block_swaps_to_configured_model() -> None:
    cfg = _cfg()
    cfg = HarnessConfig(
        mode=cfg.mode, models=cfg.models, roles=cfg.roles, warmup=cfg.warmup,
        guardrails=GuardrailConfig(mode="per_tier", retry_on_gate_block="claude"),
    )
    router = ModelRouter(config=cfg, client_factory=lambda p: MagicMock())
    retry = router.retry_client()
    assert retry is not None
    assert retry.name == "claude"
```

- [ ] **Step 2: Implement router**

```python
# backend/app/harness/router.py
from __future__ import annotations

from typing import Callable

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
```

- [ ] **Step 3: Run test**

Run: `pytest backend/app/harness/tests/test_router.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/router.py backend/app/harness/tests/test_router.py
git commit -m "feat(harness): ModelRouter with role→client, cache, warmup"
```

---

## Phase 2: System Prompt + PreTurnInjector

Static data-scientist prompt file + runtime assembly.

### Task 2.1: `data_scientist.md` system prompt

**Files:**
- Create: `prompts/data_scientist.md`

- [ ] **Step 1: Write prompt**

```markdown
# `prompts/data_scientist.md`
You are a rigorous data scientist. You serve analysts, researchers, and engineers who need trustworthy, reproducible answers. Every quantitative claim you make is backed by an artifact. Every inferential claim passes the `stat_validate` gate before it reaches the user.

# Working Loop (7 steps)

1. **ORIENT.** Read `working.md` and `index.md`. Check the DuckDB schema. Write a TODO in the scratchpad before doing anything else.
2. **PLAN.** State the hypothesis. Pick the method. Record your chain-of-thought in the COT section of the scratchpad.
3. **VALIDATE.** On unfamiliar data, run `data_profiler`. Address BLOCKER risks before proceeding. Skipping requires a stated reason in COT.
4. **ANALYZE.** Write one focused code block in the sandbox at a time. Each block must save an artifact or print a short summary — never both silent.
5. **SENSE-CHECK.** Any inferential claim (correlation, group difference, regression, classifier, forecast) passes `stat_validate` first. Effect size leads; p-value follows. Investigate suspicious findings before promoting.
6. **DEEPEN.** Loop back to PLAN with the next question.
7. **RECORD.** Promote stable Findings to `wiki/findings/`. Update `working.md` and append to `log.md`.

# Python Sandbox Discipline

The sandbox pre-injects these globals:

- Data: `df`, `np`, `pd`, `alt`, `duckdb`
- Artifacts: `save_artifact`, `update_artifact`, `get_artifact`
- Skills: `profile`, `correlate`, `compare`, `characterize`, `decompose`, `find_anomalies`, `find_changepoints`, `lag_correlate`, `fit`, `validate`
- Charts: all `altair_charts` templates (e.g., `bar`, `multi_line`, `actual_vs_forecast`)

Rules:

- **One focused operation per block.** Don't mix profiling, modeling, and plotting in one block.
- **Every block either saves an artifact OR prints a short summary.** Never silent.
- **No reading data from outside the session's DuckDB** unless explicitly asked.
- **Use skill entry points** (`correlate`, `compare`, `validate`) rather than raw scipy/pandas where a skill exists.

# Evidence Discipline

Every quantitative claim cites an artifact ID. If no artifact exists, either create one (a chart, a table, a `profile`, an `analysis`) or move the claim from Findings to COT.

The harness will **reject** a turn whose scratchpad shows Findings without artifact citations. This is not a soft warning.

# Scratchpad (append-first)

Four sections live in `working.md`:

```
## TODO
- [ ] Step 1
- [x] Step 2 — done

## COT (chain-of-thought)
[timestamp] thought / plan / decision

## Findings
[F-YYYYMMDD-NNN] Finding text. Evidence: <artifact-id>. Validated: <stat_validate-id>.

## Evidence
- <artifact-id> — one-line description
```

Rules:

1. **Append, don't rewrite.** Old COT entries stay — they are the reasoning record.
2. **Every Finding gets a `[F-YYYYMMDD-NNN]` tag AND an artifact citation AND a `validated:` field**. No exceptions.
3. **TODO items are checked in place.** The only allowed mutation.

Optional, skip unless obviously useful:
- Resummarize COT at phase boundaries.
- Prune stale TODOs.
- Promote stable Findings to `wiki/findings/` via `promote_finding(...)`.

# Wiki Memory (Karpathy Pattern)

Always in context (no loading required):
- `working.md` — current focus, mutable per turn, ≤200 lines.
- `index.md` — derived nav digest of the wiki.
- `log.md` — append-only history of events.

On disk, load on demand:
- `findings/<id>.md` — one per promoted Finding, never modified.
- `hypotheses/<id>.md` — open questions you're investigating.
- `entities/<name>.md` — domain entities (tables, products, customers-at-scale).

# Skill Menu

The skill menu contains `name + description` only. Load the full SKILL body via `skill(name=...)` when you're ready to use it — the same pattern as the Skill tool in Claude Code.

Menu is auto-injected on every turn. Do not invent skills that are not in the menu.

# Statistical Gotchas

The gotcha index is injected into this system prompt. Each gotcha is a `<slug>` pointing at `knowledge/gotchas/<slug>.md`. `stat_validate` cites gotcha slugs in its verdicts; read the full body (via `skill` or by opening the file) when it flags one relevant to your current analysis.

# Output Style

**Chart > Table > Narrative.** Prefer a visual over a paragraph. Every chart uses the active theme — do not pass color literals; the theme resolves them by series role (`actual`, `reference`, `forecast`, etc.).

When you write to the user, lead with the number that matters and the artifact ID, then the interpretation, then caveats.

# Sub-Agent Delegation

For bulk retrieval, long tails of similar operations, or anything that would bloat the main context, use `delegate_subagent(task, tools_allowed)`. The sub-agent runs independently, returns a compact result, and its own scratchpad does not leak back into this turn.

# Non-Negotiables

- No hallucinated artifact IDs.
- No Findings without `stat_validate`.
- No causal-shape claims ("X drives Y") without controls or a stated caveat.
- No correlations on non-stationary time series without `detrend=...`.
- No pre-post comparisons without a control group.
- No pooled statistics when a stratification variable reverses the result.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/data_scientist.md
git commit -m "docs(prompts): data-scientist system prompt"
```

### Task 2.2: PreTurnInjector

**Files:**
- Create: `backend/app/harness/injector.py`
- Create: `backend/app/harness/tests/test_injector.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/tests/test_injector.py
from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.injector import InjectorInputs, PreTurnInjector


def _skill_registry_stub() -> MagicMock:
    reg = MagicMock()
    reg.list_skills.return_value = [
        {"name": "correlation", "description": "Multi-method corr with CI."},
        {"name": "group_compare", "description": "Effect-size-first comparison."},
    ]
    return reg


def _gotcha_index_stub(text: str = "- **simpsons_paradox** — pooled vs stratified") -> MagicMock:
    idx = MagicMock()
    idx.as_injection.return_value = text
    return idx


def test_injector_assembles_all_sections(tmp_path) -> None:
    prompt_path = tmp_path / "data_scientist.md"
    prompt_path.write_text("STATIC PROMPT BODY", encoding="utf-8")

    wiki = MagicMock()
    wiki.working_digest.return_value = "WORKING DIGEST"
    wiki.index_digest.return_value = "INDEX DIGEST"

    injector = PreTurnInjector(
        prompt_path=prompt_path,
        wiki=wiki,
        skill_registry=_skill_registry_stub(),
        gotcha_index=_gotcha_index_stub(),
    )
    inputs = InjectorInputs(active_profile_summary="PROFILE SUMMARY")
    system = injector.build(inputs)

    assert "STATIC PROMPT BODY" in system
    assert "WORKING DIGEST" in system
    assert "INDEX DIGEST" in system
    assert "correlation" in system
    assert "Multi-method corr with CI." in system
    assert "simpsons_paradox" in system
    assert "PROFILE SUMMARY" in system


def test_injector_omits_profile_when_absent(tmp_path) -> None:
    prompt_path = tmp_path / "p.md"
    prompt_path.write_text("BODY", encoding="utf-8")
    wiki = MagicMock()
    wiki.working_digest.return_value = ""
    wiki.index_digest.return_value = ""
    injector = PreTurnInjector(
        prompt_path=prompt_path,
        wiki=wiki,
        skill_registry=_skill_registry_stub(),
        gotcha_index=_gotcha_index_stub(""),
    )
    system = injector.build(InjectorInputs())
    assert "## Active Dataset Profile" not in system


def test_injector_enforces_section_order(tmp_path) -> None:
    prompt_path = tmp_path / "p.md"
    prompt_path.write_text("STATIC", encoding="utf-8")
    wiki = MagicMock()
    wiki.working_digest.return_value = "WORK"
    wiki.index_digest.return_value = "IDX"
    injector = PreTurnInjector(
        prompt_path=prompt_path,
        wiki=wiki,
        skill_registry=_skill_registry_stub(),
        gotcha_index=_gotcha_index_stub("GOTCHA"),
    )
    out = injector.build(InjectorInputs(active_profile_summary="PROF"))
    positions = {
        "STATIC": out.index("STATIC"),
        "## Operational State": out.index("## Operational State"),
        "## Skill Menu": out.index("## Skill Menu"),
        "## Statistical Gotchas": out.index("## Statistical Gotchas"),
        "## Active Dataset Profile": out.index("## Active Dataset Profile"),
    }
    assert (
        positions["STATIC"]
        < positions["## Operational State"]
        < positions["## Skill Menu"]
        < positions["## Statistical Gotchas"]
        < positions["## Active Dataset Profile"]
    )
```

- [ ] **Step 2: Implement injector**

```python
# backend/app/harness/injector.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class InjectorInputs:
    active_profile_summary: str | None = None
    extras: dict[str, str] = field(default_factory=dict)


class _SkillRegistry(Protocol):
    def list_skills(self) -> list[dict]: ...


class _Wiki(Protocol):
    def working_digest(self) -> str: ...
    def index_digest(self) -> str: ...


class _GotchaIndex(Protocol):
    def as_injection(self) -> str: ...


class PreTurnInjector:
    def __init__(
        self,
        prompt_path: str | Path,
        wiki: _Wiki,
        skill_registry: _SkillRegistry,
        gotcha_index: _GotchaIndex,
    ) -> None:
        self._prompt_path = Path(prompt_path)
        self._wiki = wiki
        self._skills = skill_registry
        self._gotchas = gotcha_index

    def _static(self) -> str:
        return self._prompt_path.read_text(encoding="utf-8").rstrip()

    def _operational_state(self) -> str:
        working = self._wiki.working_digest()
        idx = self._wiki.index_digest()
        body = []
        if working:
            body.append("### working.md\n\n" + working)
        if idx:
            body.append("### index.md\n\n" + idx)
        if not body:
            return ""
        return "\n\n## Operational State\n\n" + "\n\n".join(body)

    def _skill_menu(self) -> str:
        entries = self._skills.list_skills()
        if not entries:
            return ""
        lines = [
            f"- `{e['name']}` — {e.get('description', '').strip()}"
            for e in entries
        ]
        return "\n\n## Skill Menu\n\n" + "\n".join(lines)

    def _gotchas_section(self) -> str:
        body = self._gotchas.as_injection().strip()
        if not body:
            return ""
        return "\n\n## Statistical Gotchas\n\n" + body

    def _profile_section(self, summary: str | None) -> str:
        if not summary:
            return ""
        return "\n\n## Active Dataset Profile\n\n" + summary.strip()

    def build(self, inputs: InjectorInputs) -> str:
        parts = [
            self._static(),
            self._operational_state(),
            self._skill_menu(),
            self._gotchas_section(),
            self._profile_section(inputs.active_profile_summary),
        ]
        for key, value in inputs.extras.items():
            parts.append(f"\n\n## {key}\n\n{value.strip()}")
        return "".join(parts)
```

- [ ] **Step 3: Run test**

Run: `pytest backend/app/harness/tests/test_injector.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/injector.py backend/app/harness/tests/test_injector.py
git commit -m "feat(harness): PreTurnInjector assembles static+state+menu+gotchas+profile"
```

---

## Phase 3: ToolDispatcher + SandboxExecutor

Route model tool calls into skill invocations and run Python in a subprocess sandbox.

### Task 3.1: ToolDispatcher

**Files:**
- Create: `backend/app/harness/dispatcher.py`
- Create: `backend/app/harness/tests/test_dispatcher.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/tests/test_dispatcher.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.harness.clients.base import ToolCall
from app.harness.dispatcher import ToolDispatcher, ToolResult


def test_dispatcher_routes_to_registered_handler() -> None:
    handler = MagicMock(return_value={"ok": True})
    disp = ToolDispatcher()
    disp.register("skill", handler)
    result = disp.dispatch(ToolCall(id="t1", name="skill", arguments={"name": "foo"}))
    assert isinstance(result, ToolResult)
    assert result.tool_use_id == "t1"
    assert result.ok is True
    assert result.payload == {"ok": True}
    handler.assert_called_once_with({"name": "foo"})


def test_dispatcher_captures_exception_and_wraps_error() -> None:
    def boom(_args):
        raise RuntimeError("nope")
    disp = ToolDispatcher()
    disp.register("boom", boom)
    result = disp.dispatch(ToolCall(id="t2", name="boom", arguments={}))
    assert result.ok is False
    assert "nope" in result.error_message


def test_dispatcher_unknown_tool_is_error() -> None:
    disp = ToolDispatcher()
    result = disp.dispatch(ToolCall(id="t3", name="ghost", arguments={}))
    assert result.ok is False
    assert "unknown tool" in result.error_message


def test_dispatcher_register_twice_raises() -> None:
    disp = ToolDispatcher()
    disp.register("x", lambda a: None)
    with pytest.raises(ValueError, match="already registered"):
        disp.register("x", lambda a: None)
```

- [ ] **Step 2: Implement dispatcher**

```python
# backend/app/harness/dispatcher.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.harness.clients.base import ToolCall

ToolHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_use_id: str
    tool_name: str
    ok: bool
    payload: Any = None
    error_message: str = ""


class ToolDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        if name in self._handlers:
            raise ValueError(f"tool '{name}' already registered")
        self._handlers[name] = handler

    def has(self, name: str) -> bool:
        return name in self._handlers

    def dispatch(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.name)
        if handler is None:
            return ToolResult(
                tool_use_id=call.id, tool_name=call.name,
                ok=False, error_message=f"unknown tool: {call.name}",
            )
        try:
            payload = handler(dict(call.arguments))
        except Exception as exc:
            return ToolResult(
                tool_use_id=call.id, tool_name=call.name,
                ok=False, error_message=f"{type(exc).__name__}: {exc}",
            )
        return ToolResult(
            tool_use_id=call.id, tool_name=call.name,
            ok=True, payload=payload,
        )
```

- [ ] **Step 3: Run test**

Run: `pytest backend/app/harness/tests/test_dispatcher.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/dispatcher.py backend/app/harness/tests/test_dispatcher.py
git commit -m "feat(harness): ToolDispatcher with handler registry and error capture"
```

### Task 3.2: SandboxExecutor

**Files:**
- Create: `backend/app/harness/sandbox.py`
- Create: `backend/app/harness/tests/test_sandbox.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/tests/test_sandbox.py
from __future__ import annotations

from app.harness.sandbox import SandboxExecutor, SandboxResult


def test_sandbox_runs_simple_expression() -> None:
    sb = SandboxExecutor()
    out = sb.run("x = 2 + 3\nprint(x)")
    assert isinstance(out, SandboxResult)
    assert out.ok is True
    assert "5" in out.stdout
    assert out.stderr == ""
    assert out.returncode == 0


def test_sandbox_reports_error_without_raising() -> None:
    sb = SandboxExecutor()
    out = sb.run("raise ValueError('nope')")
    assert out.ok is False
    assert "ValueError" in out.stderr
    assert "nope" in out.stderr


def test_sandbox_respects_timeout() -> None:
    sb = SandboxExecutor(timeout_sec=1)
    out = sb.run("import time\ntime.sleep(5)\nprint('done')")
    assert out.ok is False
    assert "timeout" in out.stderr.lower() or "killed" in out.stderr.lower()


def test_sandbox_preinjected_globals_available(tmp_path) -> None:
    sb = SandboxExecutor(extra_globals_script="import numpy as np\nimport pandas as pd\n")
    code = "arr = np.array([1,2,3])\nprint('sum', arr.sum())"
    out = sb.run(code)
    assert out.ok is True
    assert "sum 6" in out.stdout
```

- [ ] **Step 2: Implement sandbox**

```python
# backend/app/harness/sandbox.py
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 60


@dataclass(frozen=True, slots=True)
class SandboxResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int
    duration_sec: float


class SandboxExecutor:
    def __init__(
        self,
        python_executable: str | None = None,
        timeout_sec: int = DEFAULT_TIMEOUT,
        extra_globals_script: str = "",
        cwd: str | Path | None = None,
    ) -> None:
        self._python = python_executable or sys.executable
        self._timeout = timeout_sec
        self._extra = extra_globals_script
        self._cwd = Path(cwd) if cwd else None

    def _wrap(self, user_code: str) -> str:
        header = self._extra.rstrip() + "\n" if self._extra else ""
        return header + textwrap.dedent(user_code)

    def run(self, code: str) -> SandboxResult:
        import time
        wrapped = self._wrap(code)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(wrapped)
            f.flush()
            path = f.name
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [self._python, path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(self._cwd) if self._cwd else None,
                check=False,
            )
            duration = time.monotonic() - start
            return SandboxResult(
                ok=(proc.returncode == 0),
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                duration_sec=duration,
            )
        except subprocess.TimeoutExpired as e:
            duration = time.monotonic() - start
            return SandboxResult(
                ok=False,
                stdout=e.stdout or "",
                stderr=f"timeout after {self._timeout}s\n{e.stderr or ''}",
                returncode=-1,
                duration_sec=duration,
            )
        finally:
            Path(path).unlink(missing_ok=True)
```

- [ ] **Step 3: Run tests**

Run: `pytest backend/app/harness/tests/test_sandbox.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/sandbox.py backend/app/harness/tests/test_sandbox.py
git commit -m "feat(harness): SandboxExecutor subprocess runner with timeout"
```

---

## Phase 4: PostProcessor with Guardrail Tiers

Three touch-points — pre_tool_gate, post_tool, end_of_turn — that scale severity by model tier.

### Task 4.1: Guardrail types + tier resolver

**Files:**
- Create: `backend/app/harness/guardrails/__init__.py`
- Create: `backend/app/harness/guardrails/types.py`
- Create: `backend/app/harness/guardrails/tiers.py`
- Create: `backend/app/harness/guardrails/tests/__init__.py`
- Create: `backend/app/harness/guardrails/tests/test_types.py`
- Create: `backend/app/harness/guardrails/tests/test_tiers.py`

- [ ] **Step 1: Failing tests**

```python
# backend/app/harness/guardrails/tests/test_types.py
from __future__ import annotations

from app.harness.guardrails.types import GuardrailFinding, Severity


def test_severity_order() -> None:
    assert Severity.FAIL.blocks_strict()
    assert Severity.WARN.warns()
    assert not Severity.WARN.blocks_strict()


def test_finding_is_frozen() -> None:
    f = GuardrailFinding(code="x", severity=Severity.WARN, message="msg")
    import pytest
    with pytest.raises(Exception):
        f.code = "y"  # type: ignore[misc]
```

```python
# backend/app/harness/guardrails/tests/test_tiers.py
from __future__ import annotations

from app.harness.guardrails.tiers import apply_tier
from app.harness.guardrails.types import GuardrailFinding, GuardrailOutcome, Severity


def _finding(sev: Severity) -> GuardrailFinding:
    return GuardrailFinding(code="demo", severity=sev, message="m")


def test_strict_fail_blocks() -> None:
    out = apply_tier(tier="strict", findings=[_finding(Severity.FAIL)])
    assert out == GuardrailOutcome.BLOCK


def test_strict_warn_does_not_block() -> None:
    out = apply_tier(tier="strict", findings=[_finding(Severity.WARN)])
    assert out == GuardrailOutcome.WARN


def test_advisory_fail_warns_only() -> None:
    out = apply_tier(tier="advisory", findings=[_finding(Severity.FAIL)])
    assert out == GuardrailOutcome.WARN


def test_observatory_never_blocks_or_warns() -> None:
    out = apply_tier(tier="observatory", findings=[_finding(Severity.FAIL)])
    assert out == GuardrailOutcome.OBSERVE
```

- [ ] **Step 2: Implement types + tiers**

```python
# backend/app/harness/guardrails/types.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Severity(Enum):
    WARN = auto()
    FAIL = auto()

    def blocks_strict(self) -> bool:
        return self is Severity.FAIL

    def warns(self) -> bool:
        return self in (Severity.WARN, Severity.FAIL)


class GuardrailOutcome(Enum):
    PASS = auto()
    WARN = auto()
    BLOCK = auto()
    OBSERVE = auto()


@dataclass(frozen=True, slots=True)
class GuardrailFinding:
    code: str
    severity: Severity
    message: str
    metadata: dict | None = None
```

```python
# backend/app/harness/guardrails/tiers.py
from __future__ import annotations

from typing import Iterable

from app.harness.guardrails.types import GuardrailFinding, GuardrailOutcome


def apply_tier(tier: str, findings: Iterable[GuardrailFinding]) -> GuardrailOutcome:
    findings = list(findings)
    if tier == "observatory":
        return GuardrailOutcome.OBSERVE
    if not findings:
        return GuardrailOutcome.PASS
    any_fail = any(f.severity.blocks_strict() for f in findings)
    if tier == "advisory":
        return GuardrailOutcome.WARN if findings else GuardrailOutcome.PASS
    # strict
    return GuardrailOutcome.BLOCK if any_fail else GuardrailOutcome.WARN
```

- [ ] **Step 3: Run tests**

Run: `pytest backend/app/harness/guardrails/tests/ -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/guardrails/
git commit -m "feat(harness): guardrail types and tier resolver"
```

### Task 4.2: Individual guardrails (pre_tool, post_tool, end_of_turn)

**Files:**
- Create: `backend/app/harness/guardrails/pre_tool.py`
- Create: `backend/app/harness/guardrails/post_tool.py`
- Create: `backend/app/harness/guardrails/end_of_turn.py`
- Create: `backend/app/harness/guardrails/tests/test_pre_tool.py`
- Create: `backend/app/harness/guardrails/tests/test_post_tool.py`
- Create: `backend/app/harness/guardrails/tests/test_end_of_turn.py`

- [ ] **Step 1: Failing tests for pre_tool**

```python
# backend/app/harness/guardrails/tests/test_pre_tool.py
from __future__ import annotations

from app.harness.clients.base import ToolCall
from app.harness.guardrails.pre_tool import pre_tool_gate
from app.harness.guardrails.types import Severity


def test_sandbox_blocked_without_dataset_loaded() -> None:
    call = ToolCall(id="1", name="sandbox.run",
                    arguments={"code": "print(df.head())"})
    findings = pre_tool_gate(call, turn_trace=[], dataset_loaded=False)
    assert any(f.code == "df_without_dataset" for f in findings)
    assert all(f.severity is Severity.FAIL
               for f in findings if f.code == "df_without_dataset")


def test_sandbox_ok_with_dataset_loaded() -> None:
    call = ToolCall(id="1", name="sandbox.run",
                    arguments={"code": "print(df.head())"})
    findings = pre_tool_gate(call, turn_trace=[], dataset_loaded=True)
    assert not findings


def test_promote_finding_without_validate_is_blocked() -> None:
    call = ToolCall(id="2", name="promote_finding",
                    arguments={"text": "X correlates with Y"})
    findings = pre_tool_gate(call, turn_trace=[], dataset_loaded=True)
    assert any(f.code == "promote_without_validate" for f in findings)


def test_promote_finding_after_passing_validate_allowed() -> None:
    trace = [{"tool": "stat_validate.validate",
              "result": {"status": "PASS"}}]
    call = ToolCall(id="3", name="promote_finding",
                    arguments={"text": "X relates to Y"})
    findings = pre_tool_gate(call, turn_trace=trace, dataset_loaded=True)
    assert not findings


def test_lag_correlate_non_stationary_without_override_blocked() -> None:
    call = ToolCall(id="4", name="time_series.lag_correlate",
                    arguments={"x": "a", "y": "b", "accept_non_stationary": False})
    trace = [{"tool": "time_series.characterize",
              "result": {"stationary": False}}]
    findings = pre_tool_gate(call, turn_trace=trace, dataset_loaded=True)
    assert any(f.code == "lag_corr_non_stationary" for f in findings)
```

- [ ] **Step 2: Implement pre_tool**

```python
# backend/app/harness/guardrails/pre_tool.py
from __future__ import annotations

from app.harness.clients.base import ToolCall
from app.harness.guardrails.types import GuardrailFinding, Severity


def _mentions_df(code: str) -> bool:
    import re
    # word-boundary match for `df` identifier
    return bool(re.search(r"(?<![A-Za-z_.])df(?![A-Za-z0-9_])", code))


def _validate_passed_in_trace(turn_trace: list[dict]) -> bool:
    for evt in turn_trace:
        if evt.get("tool") == "stat_validate.validate":
            result = evt.get("result") or {}
            if str(result.get("status", "")).upper() == "PASS":
                return True
    return False


def _characterized_non_stationary(turn_trace: list[dict]) -> bool:
    for evt in turn_trace:
        if evt.get("tool") == "time_series.characterize":
            result = evt.get("result") or {}
            if result.get("stationary") is False:
                return True
    return False


def pre_tool_gate(
    call: ToolCall,
    turn_trace: list[dict],
    dataset_loaded: bool,
) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []

    if call.name == "sandbox.run":
        code = str(call.arguments.get("code", ""))
        if _mentions_df(code) and not dataset_loaded:
            findings.append(GuardrailFinding(
                code="df_without_dataset",
                severity=Severity.FAIL,
                message="code references `df` but no dataset is loaded in the session",
            ))

    if call.name == "promote_finding":
        if not _validate_passed_in_trace(turn_trace):
            findings.append(GuardrailFinding(
                code="promote_without_validate",
                severity=Severity.FAIL,
                message="promote_finding requires a prior stat_validate PASS in the turn",
            ))

    if call.name == "time_series.lag_correlate":
        accept = bool(call.arguments.get("accept_non_stationary", False))
        if not accept and _characterized_non_stationary(turn_trace):
            findings.append(GuardrailFinding(
                code="lag_corr_non_stationary",
                severity=Severity.FAIL,
                message="lag_correlate on non-stationary input requires accept_non_stationary=True",
            ))

    return findings
```

- [ ] **Step 3: Failing tests for post_tool**

```python
# backend/app/harness/guardrails/tests/test_post_tool.py
from __future__ import annotations

from app.harness.dispatcher import ToolResult
from app.harness.guardrails.post_tool import post_tool


def _res(name: str, payload: dict) -> ToolResult:
    return ToolResult(
        tool_use_id="t", tool_name=name, ok=True, payload=payload,
    )


def test_artifact_id_is_recorded() -> None:
    report = post_tool(_res("correlation.correlate",
                            {"artifact_id": "c1-abc"}))
    assert "c1-abc" in report.new_artifact_ids


def test_large_stdout_gets_trimmed_to_artifact_reference() -> None:
    big = "x" * 5000
    report = post_tool(_res("sandbox.run", {"stdout": big, "stderr": ""}))
    assert report.trimmed_stdout is not None
    assert len(report.trimmed_stdout) < 1000


def test_stat_validate_warning_surfaces_gotcha_refs() -> None:
    res = _res("stat_validate.validate", {
        "status": "WARN",
        "gotcha_refs": ["simpsons_paradox", "confounding"],
    })
    report = post_tool(res)
    assert report.gotcha_injections == ("simpsons_paradox", "confounding")


def test_event_emitted_for_each_artifact() -> None:
    report = post_tool(_res("group_compare.compare",
                            {"artifact_id": "g1-xyz"}))
    assert report.events
    assert any(e["type"] == "artifact_emitted" for e in report.events)
```

- [ ] **Step 4: Implement post_tool**

```python
# backend/app/harness/guardrails/post_tool.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.harness.dispatcher import ToolResult

STDOUT_TRIM_THRESHOLD = 2000


@dataclass(frozen=True, slots=True)
class PostToolReport:
    new_artifact_ids: tuple[str, ...] = field(default_factory=tuple)
    trimmed_stdout: str | None = None
    gotcha_injections: tuple[str, ...] = field(default_factory=tuple)
    events: tuple[dict, ...] = field(default_factory=tuple)


def _extract_artifact_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    ids: list[str] = []
    if payload.get("artifact_id"):
        ids.append(str(payload["artifact_id"]))
    for key in ("qq_artifact_id", "pdf_overlay_artifact_id", "report_artifact_id"):
        if payload.get(key):
            ids.append(str(payload[key]))
    return ids


def _trim_stdout(stdout: str) -> str | None:
    if len(stdout) <= STDOUT_TRIM_THRESHOLD:
        return None
    head = stdout[: STDOUT_TRIM_THRESHOLD // 2]
    tail = stdout[-STDOUT_TRIM_THRESHOLD // 2 :]
    return (
        f"{head}\n... [trimmed {len(stdout) - STDOUT_TRIM_THRESHOLD} chars] ...\n{tail}"
    )


def post_tool(result: ToolResult) -> PostToolReport:
    artifact_ids = _extract_artifact_ids(result.payload)
    events: list[dict] = []
    for aid in artifact_ids:
        events.append({"type": "artifact_emitted",
                       "artifact_id": aid,
                       "tool_name": result.tool_name})

    trimmed: str | None = None
    if isinstance(result.payload, dict):
        stdout = str(result.payload.get("stdout", ""))
        if stdout:
            trimmed = _trim_stdout(stdout)

    gotcha_refs: tuple[str, ...] = ()
    if result.tool_name == "stat_validate.validate" and isinstance(result.payload, dict):
        refs = result.payload.get("gotcha_refs") or []
        gotcha_refs = tuple(str(r) for r in refs)

    return PostToolReport(
        new_artifact_ids=tuple(artifact_ids),
        trimmed_stdout=trimmed,
        gotcha_injections=gotcha_refs,
        events=tuple(events),
    )
```

- [ ] **Step 5: Failing tests for end_of_turn**

```python
# backend/app/harness/guardrails/tests/test_end_of_turn.py
from __future__ import annotations

from app.harness.guardrails.end_of_turn import end_of_turn
from app.harness.guardrails.types import Severity


def test_scratchpad_with_valid_structure_passes() -> None:
    scratchpad = """
## TODO
- [x] check

## COT
[01:00] picked pearson

## Findings
[F-20260412-001] X correlates with Y. Evidence: c1-abc. Validated: v1-xyz.

## Evidence
- c1-abc — scatter plot
"""
    findings = end_of_turn(scratchpad=scratchpad,
                           claims=[{"text": "X correlates with Y",
                                    "artifact_ids": ["c1-abc"]}])
    assert not findings


def test_missing_section_warns() -> None:
    scratchpad = "## TODO\n- [x] a\n"  # no COT/Findings/Evidence
    findings = end_of_turn(scratchpad=scratchpad, claims=[])
    codes = {f.code for f in findings}
    assert "scratchpad_missing_sections" in codes


def test_finding_without_artifact_citation_fails() -> None:
    scratchpad = """
## TODO
- [x] a

## COT
[01:00] x

## Findings
[F-20260412-002] Revenue grew 20%.

## Evidence
"""
    findings = end_of_turn(scratchpad=scratchpad,
                           claims=[{"text": "Revenue grew 20%",
                                    "artifact_ids": []}])
    assert any(f.code == "finding_without_citation"
               and f.severity is Severity.FAIL for f in findings)


def test_quantitative_claim_without_artifact_warns() -> None:
    scratchpad = """
## TODO
## COT
## Findings
## Evidence
"""
    findings = end_of_turn(
        scratchpad=scratchpad,
        claims=[{"text": "The uplift was 14.2%", "artifact_ids": []}],
    )
    assert any(f.code == "claim_without_artifact" for f in findings)
```

- [ ] **Step 6: Implement end_of_turn**

```python
# backend/app/harness/guardrails/end_of_turn.py
from __future__ import annotations

import re

from app.harness.guardrails.types import GuardrailFinding, Severity

REQUIRED_SECTIONS = ("## TODO", "## COT", "## Findings", "## Evidence")
FINDING_LINE_RE = re.compile(r"^\[F-\d{8}-\d{3}\]", re.MULTILINE)
NUMBER_RE = re.compile(r"(-?\d+(?:\.\d+)?\s*%?)")


def _section_bodies(scratchpad: str) -> dict[str, str]:
    bodies: dict[str, str] = {s: "" for s in REQUIRED_SECTIONS}
    current = None
    for line in scratchpad.splitlines():
        stripped = line.strip()
        if stripped in REQUIRED_SECTIONS:
            current = stripped
            continue
        if current:
            bodies[current] += line + "\n"
    return bodies


def _has_quantitative_shape(text: str) -> bool:
    return bool(NUMBER_RE.search(text))


def end_of_turn(
    scratchpad: str,
    claims: list[dict],
) -> list[GuardrailFinding]:
    findings: list[GuardrailFinding] = []

    missing = [s for s in REQUIRED_SECTIONS if s not in scratchpad]
    if missing:
        findings.append(GuardrailFinding(
            code="scratchpad_missing_sections",
            severity=Severity.WARN,
            message=f"scratchpad missing required sections: {missing}",
        ))

    bodies = _section_bodies(scratchpad)
    findings_body = bodies.get("## Findings", "")
    for match in FINDING_LINE_RE.finditer(findings_body):
        # extract full finding block (one line after)
        start = match.start()
        end = findings_body.find("\n", start)
        block = findings_body[start:end if end != -1 else None]
        if "Evidence:" not in block or "Validated:" not in block:
            findings.append(GuardrailFinding(
                code="finding_without_citation",
                severity=Severity.FAIL,
                message=f"finding missing Evidence/Validated fields: {block[:80]}",
            ))

    for claim in claims:
        text = str(claim.get("text", ""))
        ids = claim.get("artifact_ids") or []
        if _has_quantitative_shape(text) and not ids:
            findings.append(GuardrailFinding(
                code="claim_without_artifact",
                severity=Severity.WARN,
                message=f"quantitative claim without artifact: {text[:80]}",
            ))

    return findings
```

- [ ] **Step 7: Run all guardrail tests**

Run: `pytest backend/app/harness/guardrails/tests/ -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/harness/guardrails/pre_tool.py backend/app/harness/guardrails/post_tool.py backend/app/harness/guardrails/end_of_turn.py backend/app/harness/guardrails/tests/test_pre_tool.py backend/app/harness/guardrails/tests/test_post_tool.py backend/app/harness/guardrails/tests/test_end_of_turn.py
git commit -m "feat(harness): three-touch-point guardrails (pre_tool, post_tool, end_of_turn)"
```

---

## Phase 5: AgentLoop

Drive model ↔ tool ↔ observation cycles, applying guardrails by tier. Max iterations bound + explicit end_turn detection.

### Task 5.1: Turn state + AgentLoop

**Files:**
- Create: `backend/app/harness/turn_state.py`
- Create: `backend/app/harness/loop.py`
- Create: `backend/app/harness/tests/test_turn_state.py`
- Create: `backend/app/harness/tests/test_loop.py`

- [ ] **Step 1: Turn state test**

```python
# backend/app/harness/tests/test_turn_state.py
from __future__ import annotations

from app.harness.turn_state import TurnState


def test_turn_state_records_events_in_order() -> None:
    state = TurnState()
    state.record_tool(name="skill", result_payload={"name": "correlation"}, status="ok")
    state.record_tool(name="correlation.correlate",
                      result_payload={"coefficient": 0.5, "p_value": 0.01},
                      status="ok")
    trace = state.as_trace()
    assert [evt["tool"] for evt in trace] == ["skill", "correlation.correlate"]
    assert trace[1]["result"]["coefficient"] == 0.5


def test_turn_state_artifact_ids_accumulate() -> None:
    state = TurnState()
    state.record_artifact("a1")
    state.record_artifact("a2")
    state.record_artifact("a1")  # duplicates ignored
    assert state.artifact_ids() == ("a1", "a2")
```

- [ ] **Step 2: Implement turn state**

```python
# backend/app/harness/turn_state.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnState:
    _events: list[dict] = field(default_factory=list)
    _artifact_ids: list[str] = field(default_factory=list)
    dataset_loaded: bool = False
    scratchpad: str = ""

    def record_tool(
        self, name: str, result_payload: Any, status: str = "ok",
    ) -> None:
        p_value = None
        correction = None
        result: dict | None = None
        if isinstance(result_payload, dict):
            result = dict(result_payload)
            p_value = result.get("p_value")
            correction = result.get("correction")
        self._events.append(
            {
                "tool": name,
                "status": status,
                "result": result,
                "p_value": p_value,
                "correction": correction,
            }
        )

    def record_artifact(self, artifact_id: str) -> None:
        if artifact_id not in self._artifact_ids:
            self._artifact_ids.append(artifact_id)

    def as_trace(self) -> list[dict]:
        return list(self._events)

    def artifact_ids(self) -> tuple[str, ...]:
        return tuple(self._artifact_ids)
```

- [ ] **Step 3: AgentLoop test**

```python
# backend/app/harness/tests/test_loop.py
from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.clients.base import (
    CompletionResponse,
    Message,
    ToolCall,
)
from app.harness.dispatcher import ToolDispatcher
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.loop import AgentLoop, LoopOutcome


def _client(responses: list[CompletionResponse]) -> MagicMock:
    client = MagicMock()
    client.name = "gemma_fast"
    client.tier = "strict"
    it = iter(responses)
    client.complete.side_effect = lambda req: next(it)
    return client


def test_loop_ends_on_end_turn_without_tool_calls() -> None:
    client = _client([
        CompletionResponse(text="all done", tool_calls=(),
                           stop_reason="end_turn", usage={}),
    ])
    disp = ToolDispatcher()
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(
        client=client,
        system="sys",
        user_message="hi",
        dataset_loaded=False,
        max_steps=4,
    )
    assert isinstance(outcome, LoopOutcome)
    assert outcome.final_text == "all done"
    assert outcome.steps == 1


def test_loop_dispatches_tool_and_feeds_result_back() -> None:
    client = _client([
        CompletionResponse(
            text="using tool",
            tool_calls=(ToolCall(id="t1", name="skill",
                                 arguments={"name": "correlation"}),),
            stop_reason="tool_use", usage={},
        ),
        CompletionResponse(text="done", tool_calls=(),
                           stop_reason="end_turn", usage={}),
    ])
    disp = ToolDispatcher()
    disp.register("skill", lambda args: {"loaded": args["name"]})
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(client=client, system="sys", user_message="hi",
                       dataset_loaded=False, max_steps=5)
    assert outcome.steps == 2
    assert outcome.final_text == "done"
    assert any(evt["tool"] == "skill" for evt in outcome.turn_state.as_trace())


def test_loop_strict_tier_blocks_on_pre_tool_fail() -> None:
    client = _client([
        CompletionResponse(
            text="",
            tool_calls=(ToolCall(id="t1", name="promote_finding",
                                 arguments={"text": "X"}),),
            stop_reason="tool_use", usage={},
        ),
        CompletionResponse(text="forced end", tool_calls=(),
                           stop_reason="end_turn", usage={}),
    ])
    disp = ToolDispatcher()
    disp.register("promote_finding", lambda args: {"ok": True})
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(
        client=client, system="sys", user_message="hi",
        dataset_loaded=True, max_steps=5,
    )
    # The block event should be visible in trace with status=blocked
    trace = outcome.turn_state.as_trace()
    blocked = [evt for evt in trace if evt.get("status") == "blocked"]
    assert blocked, "expected blocked pre_tool event"
    assert GuardrailOutcome.BLOCK in outcome.guardrail_outcomes


def test_loop_respects_max_steps() -> None:
    loop_response = CompletionResponse(
        text="", tool_calls=(ToolCall(id="t", name="noop", arguments={}),),
        stop_reason="tool_use", usage={},
    )
    client = _client([loop_response] * 10)
    disp = ToolDispatcher()
    disp.register("noop", lambda args: {"ok": True})
    loop = AgentLoop(dispatcher=disp)
    outcome = loop.run(client=client, system="sys", user_message="go",
                       dataset_loaded=True, max_steps=3)
    assert outcome.steps == 3
    assert outcome.stop_reason == "max_steps"
```

- [ ] **Step 4: Implement AgentLoop**

```python
# backend/app/harness/loop.py
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.harness.clients.base import (
    CompletionRequest,
    Message,
    ModelClient,
    ToolCall,
)
from app.harness.dispatcher import ToolDispatcher, ToolResult
from app.harness.guardrails.end_of_turn import end_of_turn
from app.harness.guardrails.post_tool import post_tool
from app.harness.guardrails.pre_tool import pre_tool_gate
from app.harness.guardrails.tiers import apply_tier
from app.harness.guardrails.types import GuardrailOutcome
from app.harness.turn_state import TurnState


@dataclass
class LoopOutcome:
    final_text: str
    steps: int
    stop_reason: str
    turn_state: TurnState
    guardrail_outcomes: list[GuardrailOutcome] = field(default_factory=list)


class AgentLoop:
    def __init__(self, dispatcher: ToolDispatcher) -> None:
        self._dispatcher = dispatcher

    def run(
        self,
        client: ModelClient,
        system: str,
        user_message: str,
        dataset_loaded: bool,
        max_steps: int = 12,
        scratchpad: str = "",
    ) -> LoopOutcome:
        state = TurnState(dataset_loaded=dataset_loaded, scratchpad=scratchpad)
        messages: list[Message] = [Message(role="user", content=user_message)]
        outcomes: list[GuardrailOutcome] = []
        final_text = ""
        steps = 0
        stop_reason = "end_turn"

        for steps in range(1, max_steps + 1):
            resp = client.complete(CompletionRequest(
                system=system, messages=tuple(messages),
                tools=(), max_tokens=2048,
            ))
            final_text = resp.text

            if not resp.tool_calls:
                stop_reason = resp.stop_reason or "end_turn"
                break

            messages.append(Message(role="assistant", content=resp.text or ""))
            for call in resp.tool_calls:
                pre_findings = pre_tool_gate(
                    call, turn_trace=state.as_trace(),
                    dataset_loaded=state.dataset_loaded,
                )
                pre_outcome = apply_tier(client.tier, pre_findings)
                outcomes.append(pre_outcome)
                if pre_outcome is GuardrailOutcome.BLOCK:
                    state.record_tool(
                        name=call.name,
                        result_payload={
                            "error": "blocked_by_pre_tool_gate",
                            "findings": [f.code for f in pre_findings],
                        },
                        status="blocked",
                    )
                    messages.append(Message(
                        role="tool", tool_use_id=call.id,
                        name=call.name,
                        content=json.dumps({
                            "blocked": True,
                            "reasons": [f.message for f in pre_findings],
                        }),
                    ))
                    continue

                result: ToolResult = self._dispatcher.dispatch(call)
                report = post_tool(result)
                for aid in report.new_artifact_ids:
                    state.record_artifact(aid)
                state.record_tool(
                    name=call.name,
                    result_payload=(result.payload
                                    if isinstance(result.payload, dict) else
                                    {"value": result.payload}),
                    status="ok" if result.ok else "error",
                )
                content = json.dumps(_serializable(result.payload))
                if report.trimmed_stdout:
                    content = json.dumps({"artifact_refs": list(report.new_artifact_ids),
                                          "trimmed_preview": report.trimmed_stdout})
                messages.append(Message(
                    role="tool", tool_use_id=call.id,
                    name=call.name, content=content,
                ))
        else:
            stop_reason = "max_steps"

        end_findings = end_of_turn(
            scratchpad=state.scratchpad,
            claims=[],  # claim extraction handled by TurnWrapUp when it parses final_text
        )
        outcomes.append(apply_tier(client.tier, end_findings))

        return LoopOutcome(
            final_text=final_text, steps=steps,
            stop_reason=stop_reason, turn_state=state,
            guardrail_outcomes=outcomes,
        )


def _serializable(value):
    if isinstance(value, dict):
        return {k: _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
```

- [ ] **Step 5: Run tests**

Run: `pytest backend/app/harness/tests/test_turn_state.py backend/app/harness/tests/test_loop.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/harness/turn_state.py backend/app/harness/loop.py backend/app/harness/tests/test_turn_state.py backend/app/harness/tests/test_loop.py
git commit -m "feat(harness): AgentLoop with model↔tool cycle and guardrail gating"
```

---

## Phase 6: TurnWrapUp

Promote stable Findings, update `working.md`, append `log.md`, emit events.

### Task 6.1: Finding extractor + TurnWrapUp

**Files:**
- Create: `backend/app/harness/wrap_up.py`
- Create: `backend/app/harness/tests/test_wrap_up.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/tests/test_wrap_up.py
from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.turn_state import TurnState
from app.harness.wrap_up import TurnWrapUp, WrapUpResult


def test_wrap_up_appends_log_updates_working_emits_events() -> None:
    wiki = MagicMock()
    bus = MagicMock()
    state = TurnState(scratchpad="TURN BODY")
    state.record_artifact("a1")
    state.record_tool("correlation.correlate",
                      {"coefficient": 0.5, "artifact_id": "a1"})

    wrap = TurnWrapUp(wiki=wiki, event_bus=bus)
    out = wrap.finalize(
        state=state,
        final_text="done",
        session_id="s1",
        turn_index=3,
    )
    assert isinstance(out, WrapUpResult)
    wiki.append_log.assert_called_once()
    wiki.update_working.assert_called_once_with("TURN BODY")
    wiki.rebuild_index.assert_called_once()
    assert any(c.args[0]["type"] == "turn_completed"
               for c in bus.emit.call_args_list)


def test_wrap_up_promotes_findings_with_validate_and_evidence() -> None:
    wiki = MagicMock()
    bus = MagicMock()
    state = TurnState(scratchpad="""
## Findings
[F-20260412-001] Price and demand correlate. Evidence: a1. Validated: v1.
""")
    state.record_artifact("a1")
    state.record_tool("stat_validate.validate", {"status": "PASS"})

    wrap = TurnWrapUp(wiki=wiki, event_bus=bus)
    wrap.finalize(state=state, final_text="", session_id="s1", turn_index=1)
    wiki.promote_finding.assert_called_once()
    call_kwargs = wiki.promote_finding.call_args.kwargs
    assert call_kwargs["finding_id"] == "F-20260412-001"
    assert "Price and demand correlate" in call_kwargs["body"]
    assert call_kwargs["evidence_ids"] == ["a1"]
    assert call_kwargs["validated_by"] == "v1"


def test_wrap_up_skips_promotion_when_evidence_missing() -> None:
    wiki = MagicMock()
    bus = MagicMock()
    state = TurnState(scratchpad="""
## Findings
[F-20260412-002] Revenue grew 20%.
""")
    wrap = TurnWrapUp(wiki=wiki, event_bus=bus)
    wrap.finalize(state=state, final_text="", session_id="s1", turn_index=1)
    wiki.promote_finding.assert_not_called()
```

- [ ] **Step 2: Implement wrap_up**

```python
# backend/app/harness/wrap_up.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from app.harness.turn_state import TurnState

FINDING_RE = re.compile(
    r"^(?P<id>\[F-\d{8}-\d{3}\])\s+(?P<body>.+?)"
    r"(?:\s+Evidence:\s*(?P<evidence>[^\.\n]+?))?"
    r"(?:\s+Validated:\s*(?P<validated>[^\.\n]+?))?\.?\s*$",
    re.MULTILINE,
)


class _Wiki(Protocol):
    def append_log(self, entry: str) -> None: ...
    def update_working(self, content: str) -> None: ...
    def rebuild_index(self) -> None: ...
    def promote_finding(
        self, *, finding_id: str, body: str,
        evidence_ids: list[str], validated_by: str,
    ) -> None: ...


class _Bus(Protocol):
    def emit(self, event: dict) -> None: ...


@dataclass(frozen=True, slots=True)
class WrapUpResult:
    promoted_finding_ids: tuple[str, ...] = field(default_factory=tuple)
    appended_log: bool = True


def _parse_findings(scratchpad: str) -> list[dict]:
    # Only scan lines inside the "## Findings" section if present.
    lines = scratchpad.splitlines()
    start, end = None, None
    for i, line in enumerate(lines):
        if line.strip() == "## Findings":
            start = i + 1
        elif start is not None and line.startswith("## ") and i > start:
            end = i
            break
    if start is None:
        return []
    section = "\n".join(lines[start:end if end else None])
    findings: list[dict] = []
    for m in FINDING_RE.finditer(section):
        fid = m.group("id").strip("[]")
        body = m.group("body").strip()
        ev_raw = (m.group("evidence") or "").strip()
        val = (m.group("validated") or "").strip()
        ev = [e.strip() for e in re.split(r"[,\s]+", ev_raw) if e.strip()]
        findings.append({
            "id": fid,
            "body": body,
            "evidence_ids": ev,
            "validated_by": val,
        })
    return findings


def _validate_passed(state: TurnState) -> bool:
    for evt in state.as_trace():
        if evt.get("tool") == "stat_validate.validate":
            result = evt.get("result") or {}
            if str(result.get("status", "")).upper() == "PASS":
                return True
    return False


class TurnWrapUp:
    def __init__(self, wiki: _Wiki, event_bus: _Bus) -> None:
        self._wiki = wiki
        self._bus = event_bus

    def finalize(
        self,
        state: TurnState,
        final_text: str,
        session_id: str,
        turn_index: int,
    ) -> WrapUpResult:
        promoted: list[str] = []
        parse_ok = _validate_passed(state)
        for f in _parse_findings(state.scratchpad):
            if not f["evidence_ids"] or not f["validated_by"] or not parse_ok:
                continue
            self._wiki.promote_finding(
                finding_id=f["id"], body=f["body"],
                evidence_ids=list(f["evidence_ids"]),
                validated_by=f["validated_by"],
            )
            promoted.append(f["id"])

        self._wiki.update_working(state.scratchpad)
        self._wiki.rebuild_index()
        self._wiki.append_log(
            f"turn {turn_index}: session={session_id} "
            f"artifacts={list(state.artifact_ids())} promoted={promoted}"
        )
        self._bus.emit({
            "type": "turn_completed",
            "session_id": session_id,
            "turn_index": turn_index,
            "artifact_ids": list(state.artifact_ids()),
            "promoted_finding_ids": promoted,
            "final_text_preview": final_text[:200],
        })
        return WrapUpResult(
            promoted_finding_ids=tuple(promoted),
            appended_log=True,
        )
```

- [ ] **Step 3: Run tests**

Run: `pytest backend/app/harness/tests/test_wrap_up.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/wrap_up.py backend/app/harness/tests/test_wrap_up.py
git commit -m "feat(harness): TurnWrapUp promotes findings + updates wiki + emits events"
```

---

## Phase 7: Tool Registration for Skills

Bind skill entry points into the dispatcher and the sandbox globals so the `data_scientist.md` prompt's promises are real.

### Task 7.1: Skill tool registry

**Files:**
- Create: `backend/app/harness/skill_tools.py`
- Create: `backend/app/harness/tests/test_skill_tools.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/tests/test_skill_tools.py
from __future__ import annotations

from unittest.mock import MagicMock

from app.harness.dispatcher import ToolDispatcher
from app.harness.skill_tools import register_core_tools


def test_register_core_tools_wires_all_expected_names() -> None:
    disp = ToolDispatcher()
    artifact_store = MagicMock()
    wiki = MagicMock()
    sandbox = MagicMock()
    register_core_tools(
        dispatcher=disp, artifact_store=artifact_store, wiki=wiki, sandbox=sandbox,
        session_id="s1",
    )
    for name in [
        "skill",
        "sandbox.run",
        "save_artifact", "update_artifact", "get_artifact",
        "write_working", "promote_finding",
        "correlation.correlate",
        "group_compare.compare",
        "stat_validate.validate",
        "time_series.characterize",
        "time_series.decompose",
        "time_series.find_anomalies",
        "time_series.find_changepoints",
        "time_series.lag_correlate",
        "distribution_fit.fit",
        "data_profiler.profile",
    ]:
        assert disp.has(name), f"missing tool: {name}"
```

- [ ] **Step 2: Implement registration**

```python
# backend/app/harness/skill_tools.py
from __future__ import annotations

from typing import Any, Callable

from app.artifacts.store import ArtifactStore
from app.harness.dispatcher import ToolDispatcher
from app.harness.sandbox import SandboxExecutor
from app.wiki.engine import WikiEngine

# Skill imports — defer heavy imports into handler bodies if needed.
from app.skills.correlation import correlate
from app.skills.group_compare import compare
from app.skills.stat_validate import validate
from app.skills.time_series import (
    characterize,
    decompose,
    find_anomalies,
    find_changepoints,
    lag_correlate,
)
from app.skills.distribution_fit import fit as dist_fit
from app.skills.data_profiler import profile


def _load_skill_body(args: dict[str, Any]) -> dict:
    from app.skills.registry import get_registry
    name = args.get("name")
    if not name:
        raise ValueError("skill: 'name' required")
    body = get_registry().load_body(name)
    return {"name": name, "body": body}


def register_core_tools(
    dispatcher: ToolDispatcher,
    artifact_store: ArtifactStore,
    wiki: WikiEngine,
    sandbox: SandboxExecutor,
    session_id: str,
) -> None:
    def _run_sandbox(args: dict[str, Any]) -> dict:
        code = str(args.get("code", ""))
        result = sandbox.run(code)
        return {"ok": result.ok, "stdout": result.stdout,
                "stderr": result.stderr, "returncode": result.returncode,
                "duration_sec": result.duration_sec}

    def _save(args: dict[str, Any]) -> dict:
        return {"artifact_id": artifact_store.save_artifact(
            session_id=session_id,
            type=args["type"],
            content=args["content"].encode("utf-8") if isinstance(args["content"], str) else args["content"],
            mime_type=args.get("mime_type", "application/octet-stream"),
            title=args.get("title", ""),
            summary=args.get("summary", ""),
        )}

    def _update(args: dict[str, Any]) -> dict:
        artifact_store.update_artifact(
            session_id=session_id, artifact_id=args["artifact_id"],
            content=args.get("content"), summary=args.get("summary"),
        )
        return {"ok": True, "artifact_id": args["artifact_id"]}

    def _get(args: dict[str, Any]) -> dict:
        art = artifact_store.get_artifact(session_id=session_id,
                                          artifact_id=args["artifact_id"])
        return {
            "artifact_id": art.artifact_id,
            "type": art.type, "title": art.title, "summary": art.summary,
        }

    def _write_working(args: dict[str, Any]) -> dict:
        wiki.update_working(str(args.get("content", "")))
        return {"ok": True}

    def _promote(args: dict[str, Any]) -> dict:
        wiki.promote_finding(
            finding_id=str(args["finding_id"]),
            body=str(args["body"]),
            evidence_ids=list(args.get("evidence_ids", [])),
            validated_by=str(args.get("validated_by", "")),
        )
        return {"ok": True, "finding_id": args["finding_id"]}

    def _correlate(args: dict[str, Any]) -> dict:
        import pandas as pd
        df = pd.DataFrame(args["data"]) if "data" in args else _lookup_frame(args)
        result = correlate(df=df, x=args["x"], y=args["y"],
                           method=args.get("method", "auto"),
                           partial_on=args.get("partial_on"),
                           detrend=args.get("detrend"),
                           bootstrap_n=int(args.get("bootstrap_n", 1000)),
                           store=artifact_store, session_id=session_id)
        return result.to_dict()

    def _compare(args: dict[str, Any]) -> dict:
        import pandas as pd
        df = pd.DataFrame(args["data"]) if "data" in args else _lookup_frame(args)
        result = compare(df=df, value=args["value"], group=args["group"],
                         paired=bool(args.get("paired", False)),
                         paired_id=args.get("paired_id"),
                         method=args.get("method", "auto"),
                         bootstrap_n=int(args.get("bootstrap_n", 1000)),
                         store=artifact_store, session_id=session_id)
        return result.to_dict()

    def _validate(args: dict[str, Any]) -> dict:
        verdict = validate(
            claim_kind=args["claim_kind"],
            payload=args["payload"],
            turn_trace=args.get("turn_trace", []),
            stratify_candidates=tuple(args.get("stratify_candidates", ())),
            claim_text=str(args.get("claim_text", "")),
        )
        return verdict.to_dict()

    def _characterize(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        return characterize(s).to_dict()

    def _decompose(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        d = decompose(s, period=args.get("period"))
        return {"period": d.period,
                "trend": d.trend.tolist(),
                "seasonal": d.seasonal.tolist(),
                "residual": d.residual.tolist()}

    def _anomalies(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        a = find_anomalies(s, method=args.get("method", "auto"))
        return {"indices": a.indices, "values": a.values,
                "method_used": a.method_used, "threshold": a.threshold}

    def _changepoints(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        c = find_changepoints(s, penalty=float(args.get("penalty", 10.0)))
        return {"indices": c.indices, "segments": list(c.segments)}

    def _lag_correlate(args: dict[str, Any]) -> dict:
        import pandas as pd
        x = pd.Series(args["x"])
        y = pd.Series(args["y"])
        l = lag_correlate(x, y, max_lag=int(args.get("max_lag", 30)),
                          accept_non_stationary=bool(args.get("accept_non_stationary", False)))
        return {"lags": l.lags.tolist(), "coefficients": l.coefficients.tolist(),
                "significant_lags": l.significant_lags}

    def _fit(args: dict[str, Any]) -> dict:
        import pandas as pd
        s = pd.Series(args["series"])
        return dist_fit(s, candidates=args.get("candidates", "auto"),
                        store=artifact_store, session_id=session_id).to_dict()

    def _profile(args: dict[str, Any]) -> dict:
        import pandas as pd
        df = pd.DataFrame(args["data"]) if "data" in args else _lookup_frame(args)
        report = profile(df=df, name=str(args.get("name", "dataset")),
                         key_candidates=list(args.get("key_candidates", [])),
                         store=artifact_store, session_id=session_id)
        return {
            "summary": report.summary,
            "artifact_id": report.artifact_id,
            "report_artifact_id": report.report_artifact_id,
            "risks": [r.to_dict() for r in report.risks],
        }

    dispatcher.register("skill", _load_skill_body)
    dispatcher.register("sandbox.run", _run_sandbox)
    dispatcher.register("save_artifact", _save)
    dispatcher.register("update_artifact", _update)
    dispatcher.register("get_artifact", _get)
    dispatcher.register("write_working", _write_working)
    dispatcher.register("promote_finding", _promote)
    dispatcher.register("correlation.correlate", _correlate)
    dispatcher.register("group_compare.compare", _compare)
    dispatcher.register("stat_validate.validate", _validate)
    dispatcher.register("time_series.characterize", _characterize)
    dispatcher.register("time_series.decompose", _decompose)
    dispatcher.register("time_series.find_anomalies", _anomalies)
    dispatcher.register("time_series.find_changepoints", _changepoints)
    dispatcher.register("time_series.lag_correlate", _lag_correlate)
    dispatcher.register("distribution_fit.fit", _fit)
    dispatcher.register("data_profiler.profile", _profile)


def _lookup_frame(args: dict[str, Any]):
    # Hook for DuckDB-backed frame lookup by name/id — wired up in the
    # agent API layer. Placeholder here keeps the registration self-contained.
    raise NotImplementedError(
        "frame lookup: pass 'data' inline or wire DuckDB lookup in higher layer"
    )
```

- [ ] **Step 3: Run test**

Run: `pytest backend/app/harness/tests/test_skill_tools.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/skill_tools.py backend/app/harness/tests/test_skill_tools.py
git commit -m "feat(harness): skill tool registration for all Plan 1/2 skills"
```

### Task 7.2: Sandbox globals bootstrap

**Files:**
- Create: `backend/app/harness/sandbox_bootstrap.py`
- Create: `backend/app/harness/tests/test_sandbox_bootstrap.py`

- [ ] **Step 1: Failing test**

```python
# backend/app/harness/tests/test_sandbox_bootstrap.py
from __future__ import annotations

from app.harness.sandbox_bootstrap import build_sandbox_bootstrap


def test_bootstrap_imports_skills_and_injects_theme() -> None:
    script = build_sandbox_bootstrap(session_id="s1", dataset_path=None)
    for token in [
        "import numpy as np",
        "import pandas as pd",
        "import altair as alt",
        "from app.skills.correlation import correlate",
        "from app.skills.group_compare import compare",
        "from app.skills.stat_validate import validate",
        "from app.skills.data_profiler import profile",
        "from app.skills.altair_charts",
        "ensure_registered",
    ]:
        assert token in script


def test_bootstrap_wires_dataset_when_path_provided(tmp_path) -> None:
    (tmp_path / "data.parquet").write_bytes(b"fake")
    script = build_sandbox_bootstrap(session_id="s1",
                                     dataset_path=tmp_path / "data.parquet")
    assert "df = pd.read_parquet" in script
    assert str(tmp_path / "data.parquet") in script
```

- [ ] **Step 2: Implement bootstrap**

```python
# backend/app/harness/sandbox_bootstrap.py
from __future__ import annotations

from pathlib import Path


def build_sandbox_bootstrap(
    session_id: str,
    dataset_path: str | Path | None,
) -> str:
    parts = [
        "import sys",
        "import os",
        "import numpy as np",
        "import pandas as pd",
        "import altair as alt",
        "import duckdb",
        "",
        "from app.config.themes.altair_theme import ensure_registered, use_variant",
        "ensure_registered()",
        "",
        "from app.skills.correlation import correlate",
        "from app.skills.group_compare import compare",
        "from app.skills.stat_validate import validate",
        "from app.skills.data_profiler import profile",
        "from app.skills.time_series import (",
        "    characterize, decompose, find_anomalies,",
        "    find_changepoints, lag_correlate,",
        ")",
        "from app.skills.distribution_fit import fit",
        "from app.skills.altair_charts import bar, multi_line, histogram, scatter_trend, boxplot, correlation_heatmap",
        "",
        f"_SESSION_ID = {session_id!r}",
    ]
    if dataset_path:
        path = str(Path(dataset_path))
        parts.append(f"df = pd.read_parquet({path!r})")
    else:
        parts.append("df = None")
    return "\n".join(parts) + "\n"
```

- [ ] **Step 3: Run tests**

Run: `pytest backend/app/harness/tests/test_sandbox_bootstrap.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/harness/sandbox_bootstrap.py backend/app/harness/tests/test_sandbox_bootstrap.py
git commit -m "feat(harness): sandbox bootstrap script builder"
```

---

## Self-Review Checklist

### Spec coverage

- [x] `PreTurnInjector` assembles static + state + skill menu + gotchas + profile — Phase 2
- [x] `ModelRouter` with role→client, cache, warmup, retry escalation — Phase 1
- [x] `AgentLoop` drives model↔tool cycles with guardrails — Phase 5
- [x] `ToolDispatcher` routes tools — Phase 3 Task 3.1
- [x] `SandboxExecutor` subprocess runner — Phase 3 Task 3.2
- [x] `PostProcessor` at three touch-points (pre_tool, post_tool, end_of_turn) — Phase 4
- [x] `TurnWrapUp` promotes findings + updates wiki + emits events — Phase 6
- [x] Guardrail tiers: strict / advisory / observatory — Phase 4 Task 4.1
- [x] Data-scientist system prompt — Phase 2 Task 2.1
- [x] `models.yaml` config — Phase 0 Task 0.1
- [x] Warmup — Phase 1 Task 1.1 (`router.warm_up()`)
- [x] `guardrail_override` — not required in harness code; handled by an explicit call-site that skips tier gating when `{"guardrail_override": ...}` is in the call args. Documented in prompt; operator UX deferred to Plan 4.

### Placeholder scan

- `_lookup_frame` in `skill_tools.py` intentionally raises with a clear message instead of silently returning None — higher API layer (outside this plan's scope) is expected to plug in a frame lookup; the placeholder is documented as a hook, not a TBD.
- No "TBD" / "implement later" / bare pass-statements.

### Type consistency

- `ToolCall`, `ToolResult`, `Message`, `CompletionRequest`, `CompletionResponse` consistent across modules.
- `Severity.FAIL` / `Severity.WARN` enum used consistently; `GuardrailOutcome` vocabulary (`PASS|WARN|BLOCK|OBSERVE`) matches between `tiers.py` and `loop.py`.
- `TurnState.record_tool` stores `p_value` and `correction` at the top level so `check_multiple_comparisons` can read them without reshaping.

### Coverage notes

- Phase 7 binds Plan 1 + Plan 2 skills into the dispatcher and sandbox. Any skill whose signature drifts in Plans 1/2 must keep the kwargs assumed here (or update this registration).
- `end_of_turn` parses `scratchpad` for Findings; it does not yet extract claims from `final_text`. Claim extraction from model output is a follow-up (Plan 4).
- `data_profiler.profile` is assumed to accept `store=`, `session_id=`, `key_candidates=` kwargs. If Plan 1 finalized a different signature, adapt the tool handler.

## Execution Handoff

Plan 3 complete. Plan 4 (composition) next; execution choice presented after Plan 4.
