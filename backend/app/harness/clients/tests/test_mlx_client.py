from __future__ import annotations

from app.harness.clients.base import CompletionRequest, Message, ToolSchema
from app.harness.clients.mlx_client import MLXClient
from app.harness.config import ModelProfile


class _FakeTokenizer:
    def apply_chat_template(
        self,
        messages,
        *,
        tokenize: bool = False,
        add_generation_prompt: bool = True,
    ) -> str:
        rendered = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}" for message in messages
        )
        return f"{rendered}\n\nASSISTANT:"

    def __call__(self, text: str, add_special_tokens: bool = False):
        tokens = text.split()
        return {"input_ids": list(range(max(1, len(tokens))))}


def _profile() -> ModelProfile:
    return ModelProfile(
        name="mlx_gemma",
        provider="mlx",
        model_id="mlx/mlx-community/gemma-4-e2b-it-OptiQ-4bit",
        tier="strict",
        options={"temperature": 0.2},
    )


def _install_fake_runtime(monkeypatch, generated: list[str]) -> None:
    import app.harness.clients.mlx_client as mlx_module

    mlx_module._MODEL_CACHE.clear()
    monkeypatch.setattr(mlx_module, "_mlx_load", lambda model: (object(), _FakeTokenizer()))

    def _generate(model_obj, tokenizer, **kwargs):
        assert kwargs["prompt"]
        return generated.pop(0)

    monkeypatch.setattr(mlx_module, "_mlx_generate", _generate)
    monkeypatch.setattr(mlx_module, "_mlx_make_sampler", lambda temp: {"temp": temp})


def test_mlx_client_returns_plain_text(monkeypatch) -> None:
    _install_fake_runtime(monkeypatch, ["Direct answer"])
    client = MLXClient(_profile())

    response = client.complete(
        CompletionRequest(
            system="Be concise.",
            messages=(Message(role="user", content="hello"),),
            max_tokens=64,
        )
    )

    assert response.text == "Direct answer"
    assert response.tool_calls == ()
    assert response.stop_reason == "end_turn"
    assert response.usage["input_tokens"] > 0
    assert response.usage["output_tokens"] > 0


def test_mlx_client_strips_channel_thought(monkeypatch) -> None:
    _install_fake_runtime(
        monkeypatch,
        ["<|channel>thought internal notes<channel|><|channel>final Final answer"],
    )
    client = MLXClient(_profile())

    response = client.complete(
        CompletionRequest(
            system="Reply directly.",
            messages=(Message(role="user", content="hello"),),
            max_tokens=64,
        )
    )

    assert response.text == "Final answer"


def test_mlx_client_parses_message_envelope(monkeypatch) -> None:
    _install_fake_runtime(
        monkeypatch,
        ['{"type":"message","content":"Here is the final answer."}'],
    )
    client = MLXClient(_profile())

    response = client.complete(
        CompletionRequest(
            system="Use tools when needed.",
            messages=(Message(role="user", content="Summarize the result"),),
            tools=(
                ToolSchema(
                    name="execute_python",
                    description="run python",
                    input_schema={"type": "object"},
                ),
            ),
            max_tokens=128,
        )
    )

    assert response.text == "Here is the final answer."
    assert response.tool_calls == ()
    assert response.stop_reason == "end_turn"


def test_mlx_client_parses_tool_calls(monkeypatch) -> None:
    _install_fake_runtime(
        monkeypatch,
        [
            (
                '{"type":"tool_calls","tool_calls":['
                '{"name":"execute_python","arguments":{"code":"print(1)"}}]}'
            )
        ],
    )
    client = MLXClient(_profile())

    response = client.complete(
        CompletionRequest(
            system="Use tools when needed.",
            messages=(Message(role="user", content="Analyze the dataset"),),
            tools=(
                ToolSchema(
                    name="execute_python",
                    description="run python",
                    input_schema={"type": "object"},
                ),
            ),
            max_tokens=128,
            tool_choice="required",
        )
    )

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "execute_python"
    assert response.tool_calls[0].arguments == {"code": "print(1)"}
    assert response.stop_reason == "tool_use"
