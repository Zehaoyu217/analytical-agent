"""LLM judge for qualitative dimension grading.

Three implementations:
- ``LLMJudge``        — calls a local MLX model (default: Gemma 4 E4B text-only).
- ``OpenRouterJudge`` — calls OpenRouter chat completions directly.
- ``FallbackJudge``   — tries OpenRouterJudge first, falls back to LLMJudge.

The local judge is intentionally tool-free and uses the same MLX runtime family as
the main backend chat harness, so evals can run without Ollama.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field

import httpx

from app.evals.grading import grade_to_score
from app.evals.rubric import DimensionRubric
from app.evals.types import AgentTrace, DimensionGrade
from app.harness.clients.base import CompletionRequest, Message
from app.harness.clients.mlx_client import MLXClient, cached_model_ids, mlx_available
from app.harness.config import ModelProfile

# ── Shared prompt builder ──────────────────────────────────────────────────────

def _build_grading_prompt(
    dimension_name: str,
    rubric: DimensionRubric,
    trace: AgentTrace,
) -> str:
    errors_text = "\n".join(trace.errors) if trace.errors else "None"
    queries_text = "\n".join(trace.queries) if trace.queries else "None"
    return (
        f"You are grading an AI agent's performance on the dimension: "
        f"{dimension_name}\n\n"
        f"Agent's final output:\n{trace.final_output}\n\n"
        f"SQL queries / code executed:\n{queries_text}\n\n"
        f"Errors encountered:\n{errors_text}\n\n"
        f"Grading criteria:\n"
        f"- A (excellent): {rubric.criteria['A']}\n"
        f"- B (pretty useful): {rubric.criteria['B']}\n"
        f"- C (minimally ok): {rubric.criteria['C']}\n\n"
        f"Respond with exactly one line: "
        f"GRADE: <A|B|C|F> — <one-sentence justification>"
    )


def _parse_grade_response(response: str) -> tuple[str, str]:
    """Parse 'GRADE: X — justification' from judge response."""
    for line in response.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("GRADE:"):
            rest = line[6:].strip()
            parts = rest.split("—", 1)
            if not parts:
                continue
            grade = parts[0].strip().upper()
            justification = parts[1].strip() if len(parts) > 1 else ""
            if grade in ("A", "B", "C", "F"):
                return grade, justification
    return "F", "Could not parse judge response"


# ── Local MLX judge (primary local path) ──────────────────────────────────────

@dataclass(frozen=True)
class JudgeConfig:
    """Configuration for the local MLX LLM judge."""

    model: str = "mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit"
    temperature: float = 0.0
    max_tokens: int = 256


class LLMJudge:
    """Grades agent traces against rubric criteria using a local MLX model."""

    def __init__(self, config: JudgeConfig | None = None) -> None:
        self._config = config or JudgeConfig()
        self._client = MLXClient(
            ModelProfile(
                name="eval_judge",
                provider="mlx",
                model_id=self._config.model,
                tier="observatory",
                options={"temperature": self._config.temperature},
            )
        )

    async def grade_dimension(
        self,
        dimension_name: str,
        rubric: DimensionRubric,
        trace: AgentTrace,
    ) -> DimensionGrade:
        prompt = self.build_prompt(dimension_name, rubric, trace)
        response = await self._call_local_model(prompt)
        grade, justification = self.parse_response(response)
        return DimensionGrade(
            name=dimension_name,
            grade=grade,
            score=grade_to_score(grade),
            weight=rubric.weight,
            justification=justification,
        )

    def build_prompt(
        self,
        dimension_name: str,
        rubric: DimensionRubric,
        trace: AgentTrace,
    ) -> str:
        return _build_grading_prompt(dimension_name, rubric, trace)

    async def _call_local_model(self, prompt: str) -> str:
        return await asyncio.to_thread(self._complete, prompt)

    def probe_ready(self) -> None:
        self._complete("Reply with exactly: GRADE: B — warmup")

    def parse_response(self, response: str) -> tuple[str, str]:
        return _parse_grade_response(response)

    def _complete(self, prompt: str) -> str:
        response = self._client.complete(
            CompletionRequest(
                system=(
                    "You are an evaluation judge. Respond with exactly one line in the format: "
                    "GRADE: <A|B|C|F> — <one-sentence justification>"
                ),
                messages=(Message(role="user", content=prompt),),
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )
        )
        return response.text


def local_judge_ready_reason(model: str | None = None) -> str:
    """Return an empty string when the configured MLX judge is ready, else a reason."""

    judge = LLMJudge(JudgeConfig(model=model or JudgeConfig().model))
    model_id = judge._config.model
    if not mlx_available():
        return "mlx-lm runtime is not available"
    if model_id not in cached_model_ids():
        return (
            f"Judge model '{model_id}' is not cached for MLX — "
            "download it once before running the eval suite"
        )
    try:
        judge.probe_ready()
    except Exception as exc:
        return f"Judge model '{model_id}' failed local MLX warmup: {exc}"
    return ""


# ── OpenRouter judge (fallback when Ollama is unavailable) ────────────────────

@dataclass(frozen=True)
class OpenRouterJudgeConfig:
    """Configuration for the OpenRouter-based judge.

    Uses the project's OPENROUTER_API_KEY. No local model required.
    Model should be capable of following a simple grading instruction.
    """
    model: str = "openai/gpt-oss-120b:free"
    base_url: str = "https://openrouter.ai/api/v1"
    temperature: float = 0.0
    max_tokens: int = 256
    api_key: str = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", ""))


class OpenRouterJudge:
    """Grades agent traces via OpenRouter chat completions API.

    Does NOT use the agent loop — makes a direct chat completion call so there
    is no risk of the judge itself calling execute_python or other tools.

    Activate instead of LLMJudge when local MLX isn't available:
        judge = OpenRouterJudge()
        # or in run_eval.py: pass --judge (it auto-selects this class)
    """

    def __init__(self, config: OpenRouterJudgeConfig | None = None) -> None:
        self._config = config or OpenRouterJudgeConfig()
        if not self._config.api_key:
            # Try loading from the project .env as a fallback
            _load_dotenv()
            object.__setattr__(
                self._config, "api_key",
                os.environ.get("OPENROUTER_API_KEY", ""),
            )

    async def grade_dimension(
        self,
        dimension_name: str,
        rubric: DimensionRubric,
        trace: AgentTrace,
    ) -> DimensionGrade:
        prompt = _build_grading_prompt(dimension_name, rubric, trace)
        response = await self._call_openrouter(prompt)
        grade, justification = _parse_grade_response(response)
        return DimensionGrade(
            name=dimension_name,
            grade=grade,
            score=grade_to_score(grade),
            weight=rubric.weight,
            justification=justification,
        )

    async def _call_openrouter(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self._config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "claude-code-agent-eval-judge",
                },
                json={
                    "model": self._config.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an evaluation judge. "
                                "Respond with exactly one line in the format: "
                                "GRADE: <A|B|C|F> — <one-sentence justification>"
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": self._config.max_tokens,
                    "temperature": self._config.temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


# ── FallbackJudge: OpenRouter → local MLX ─────────────────────────────────────

class FallbackJudge:
    """Tries OpenRouterJudge; falls back to LLMJudge (local MLX) on failure."""

    def __init__(
        self,
        primary: OpenRouterJudge | None = None,
        fallback: LLMJudge | None = None,
    ) -> None:
        self._primary = primary or OpenRouterJudge()
        self._fallback = fallback or LLMJudge()

    async def grade_dimension(
        self,
        dimension_name: str,
        rubric: DimensionRubric,
        trace: AgentTrace,
    ) -> DimensionGrade:
        try:
            return await self._primary.grade_dimension(dimension_name, rubric, trace)
        except Exception:
            return await self._fallback.grade_dimension(dimension_name, rubric, trace)


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_dotenv() -> None:
    """Best-effort load of project .env (no dependency on python-dotenv)."""
    from pathlib import Path
    env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value
