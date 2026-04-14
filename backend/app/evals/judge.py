"""LLM judge for qualitative dimension grading via local Ollama."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.evals.grading import grade_to_score
from app.evals.rubric import DimensionRubric
from app.evals.types import AgentTrace, DimensionGrade


@dataclass(frozen=True)
class JudgeConfig:
    """Configuration for the LLM judge."""

    model: str = "qwen3.5:9b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0


class LLMJudge:
    """Grades agent traces against rubric criteria using a local LLM."""

    def __init__(self, config: JudgeConfig | None = None) -> None:
        self._config = config or JudgeConfig()

    async def grade_dimension(
        self,
        dimension_name: str,
        rubric: DimensionRubric,
        trace: AgentTrace,
    ) -> DimensionGrade:
        """Grade a single dimension by calling the LLM judge."""
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
        """Build the grading prompt for the LLM."""
        errors_text = "\n".join(trace.errors) if trace.errors else "None"
        queries_text = "\n".join(trace.queries) if trace.queries else "None"
        return (
            f"You are grading an AI agent's performance on the dimension: "
            f"{dimension_name}\n\n"
            f"Agent's final output:\n{trace.final_output}\n\n"
            f"SQL queries executed:\n{queries_text}\n\n"
            f"Errors encountered:\n{errors_text}\n\n"
            f"Grading criteria:\n"
            f"- A (excellent): {rubric.criteria['A']}\n"
            f"- B (pretty useful): {rubric.criteria['B']}\n"
            f"- C (minimally ok): {rubric.criteria['C']}\n\n"
            f"Respond with exactly one line: "
            f"GRADE: <A|B|C|F> — <one-sentence justification>"
        )

    async def _call_ollama(self, prompt: str) -> str:
        """Call the Ollama generate API."""
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
        """Parse the judge's response into (grade, justification)."""
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
