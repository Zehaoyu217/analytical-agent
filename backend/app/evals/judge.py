"""LLM judge for qualitative dimension grading.

Two implementations:
- ``LLMJudge``     — calls local Ollama (default model: gemma4:e2b).
                     Use when Ollama is running and the model is loaded.
- ``OpenRouterJudge`` — calls OpenRouter chat completions directly.
                     No agent loop overhead; uses the project's existing API key.
                     Use when Ollama is unavailable (resource contention, etc.).
- ``FallbackJudge`` — tries OpenRouterJudge first, falls back to LLMJudge.

To switch back to Ollama once gemma4:e2b loads reliably:
    judge = LLMJudge()                     # uses gemma4:e2b on localhost:11434
    judge = LLMJudge(JudgeConfig(model="gemma4:e2b"))  # explicit
See docs/eval-judge-setup.md for full setup instructions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

from app.evals.grading import grade_to_score
from app.evals.rubric import DimensionRubric
from app.evals.types import AgentTrace, DimensionGrade

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


# ── Ollama judge (primary when available) ─────────────────────────────────────

@dataclass(frozen=True)
class JudgeConfig:
    """Configuration for the Ollama LLM judge.

    To revert to Ollama once gemma4:e2b loads:
        judge = LLMJudge(JudgeConfig(model="gemma4:e2b"))
    """
    model: str = "gemma4:e2b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0


class LLMJudge:
    """Grades agent traces against rubric criteria using a local Ollama model.

    Requires Ollama running at ``JudgeConfig.base_url`` with the model loaded.
    Use ``FallbackJudge`` or ``OpenRouterJudge`` when Ollama is unavailable.
    """

    def __init__(self, config: JudgeConfig | None = None) -> None:
        self._config = config or JudgeConfig()

    async def grade_dimension(
        self,
        dimension_name: str,
        rubric: DimensionRubric,
        trace: AgentTrace,
    ) -> DimensionGrade:
        prompt = self.build_prompt(dimension_name, rubric, trace)
        response = await self._call_ollama(prompt)
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

    async def _call_ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._config.base_url}/api/generate",
                json={
                    "model": self._config.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self._config.temperature},
                },
                timeout=600.0,
            )
            resp.raise_for_status()
            return resp.json()["response"]

    def parse_response(self, response: str) -> tuple[str, str]:
        return _parse_grade_response(response)


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

    Activate instead of LLMJudge when local Ollama can't load models:
        judge = OpenRouterJudge()
        # or in run_eval.py: pass --judge (it auto-selects this class)

    To revert to Ollama:
        judge = LLMJudge()  # see docs/eval-judge-setup.md
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


# ── FallbackJudge: OpenRouter → Ollama ────────────────────────────────────────

class FallbackJudge:
    """Tries OpenRouterJudge; falls back to LLMJudge (Ollama) on failure.

    This is the recommended judge for environments where Ollama may have
    resource contention.  Configure via env vars:
        OPENROUTER_API_KEY  — required for OpenRouter path
        OLLAMA_URL          — optional, defaults to http://localhost:11434
    """

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
