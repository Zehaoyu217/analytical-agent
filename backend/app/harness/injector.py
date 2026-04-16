from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from app.harness.injection_guard import InjectionAttemptError, scan
from app.skills.base import SkillNode

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TokenBudget:
    """Token-budget guidance surfaced in the system prompt (P21).

    Everything is in rough tokens / chars — the values are telemetry for the
    agent, not hard enforcement.  Enforcement lives in the MicroCompactor.
    """

    max_tokens: int = 200_000
    compact_threshold: float = 0.80
    char_budget: int = 40_000
    keep_recent_tool_results: int = 3


@dataclass(frozen=True, slots=True)
class InjectorInputs:
    active_profile_summary: str | None = None
    extras: dict[str, str] = field(default_factory=dict)
    token_budget: TokenBudget | None = None
    plan_mode: bool = False
    session_id: str = ""


class _SkillRegistry(Protocol):
    def list_top_level(self) -> list[SkillNode]: ...


class _Wiki(Protocol):
    def working_digest(self) -> str: ...
    def index_digest(self) -> str: ...
    def latest_session_notes(self, exclude_session_id: str = "") -> str: ...


class _GotchaIndex(Protocol):
    def as_injection(self) -> str: ...


class PreTurnInjector:
    def __init__(
        self,
        prompt_path: str | Path,
        wiki: _Wiki,
        skill_registry: _SkillRegistry,
        gotcha_index: _GotchaIndex,
        agent_persona: str = "",
    ) -> None:
        self._prompt_path = Path(prompt_path)
        self._wiki = wiki
        self._skills = skill_registry
        self._gotchas = gotcha_index
        self._agent_persona = agent_persona

    def _static(self) -> str:
        return self._prompt_path.read_text(encoding="utf-8").rstrip()

    def _operational_state(self) -> str:
        working = self._wiki.working_digest()
        idx = self._wiki.index_digest()
        body = []
        if working:
            try:
                scan(working, source="wiki/working.md")
                body.append("### working.md\n\n" + working)
            except InjectionAttemptError:
                logger.warning("Injection attempt detected in wiki/working.md — block skipped")
        if idx:
            try:
                scan(idx, source="wiki/index.md")
                body.append("### index.md\n\n" + idx)
            except InjectionAttemptError:
                logger.warning("Injection attempt detected in wiki/index.md — block skipped")
        if not body:
            return ""
        return "\n\n## Operational State\n\n" + "\n\n".join(body)

    def _skill_menu(self) -> str:
        roots = self._skills.list_top_level()
        if not roots:
            return ""
        preamble = (
            "Use the `skill` tool to load any skill before using it. "
            "Hub skills expand into sub-skills when loaded — read the "
            "sub-skill catalog before deciding which to use."
        )
        lines: list[str] = []
        for node in roots:
            desc = node.metadata.description.strip()
            child_count = len(node.children)
            annotation = f" [{child_count} sub-skills]" if child_count > 0 else ""
            lines.append(f"- `{node.metadata.name}` — {desc}{annotation}")
        return "\n\n## Skills\n\n" + preamble + "\n\n" + "\n".join(lines)

    def _gotchas_section(self) -> str:
        body = self._gotchas.as_injection().strip()
        if not body:
            return ""
        return "\n\n## Statistical Gotchas\n\n" + body

    def _profile_section(self, summary: str | None) -> str:
        if not summary:
            return ""
        return "\n\n## Active Dataset Profile\n\n" + summary.strip()

    def _plan_mode_section(self, plan_mode: bool) -> str:
        if not plan_mode:
            return ""
        lines = [
            "## Plan Mode",
            "",
            "You are in **PLAN MODE**. Produce a plan only — do not execute.",
            "",
            "- DO NOT call `execute_python`, `save_artifact`, `promote_finding`, "
            "or `delegate_subagent` — they are unavailable in this mode.",
            "- DO use `todo_write` to declare the full plan as discrete, "
            "action-oriented items (one `in_progress` at most).",
            "- DO use `skill` to pre-read any skill you intend to invoke later, "
            "and `write_working` to capture the plan's rationale.",
            "- End with a short plain-text summary of the plan and ask the user "
            "to confirm before switching out of plan mode.",
        ]
        return "\n\n" + "\n".join(lines)

    def _session_memory_section(self, session_id: str) -> str:
        """Inject the most-recent prior session notes for cross-session continuity (P18)."""
        notes = self._wiki.latest_session_notes(exclude_session_id=session_id)
        if not notes.strip():
            return ""
        try:
            scan(notes, source="wiki/session_notes")
        except InjectionAttemptError:
            logger.warning("Injection attempt detected in session notes — block skipped")
            return ""
        return "\n\n## Prior Session Memory\n\n" + notes.strip()

    def _token_budget_section(self, budget: TokenBudget | None) -> str:
        if budget is None:
            return ""
        compact_pct = int(round(budget.compact_threshold * 100))
        rough_tokens_budget = budget.char_budget // 4
        lines = [
            "## Context Budget",
            "",
            f"- Context window: ~{budget.max_tokens:,} tokens.",
            f"- Proactive compaction kicks in at ~{compact_pct}% utilization.",
            (
                f"- Tool-result history budget: ~{budget.char_budget:,} chars "
                f"(≈{rough_tokens_budget:,} tokens). Older results beyond the "
                f"last {budget.keep_recent_tool_results} are dropped "
                "automatically — their artifact refs survive so you can "
                "re-fetch via `get_artifact`."
            ),
            "- Prefer `save_artifact` over dumping full tables or stdout "
            "into the conversation. Cite the artifact id in findings.",
            "- Keep tool outputs small: print heads, summaries, or a single "
            "aggregate — not the raw data.",
        ]
        return "\n\n" + "\n".join(lines)

    def build_static(self) -> str:
        """Build the stable, per-session part of the system prompt.

        Call this **once** at session start and pass the result as the ``system``
        parameter to every LLM call.  Because the content never changes within a
        session, the Anthropic API can cache the prefix and avoid re-encoding it
        on every turn.

        Includes: base prompt text, skill catalog, statistical gotchas.
        """
        parts: list[str] = []
        if self._agent_persona:
            parts.append(self._agent_persona.rstrip())
            parts.append("\n\n")
        parts.append(self._static())
        parts.append(self._skill_menu())
        parts.append(self._gotchas_section())
        return "".join(parts)

    def build_dynamic(self, inputs: InjectorInputs) -> str | None:
        """Build the per-turn dynamic context fragment.

        Call this **each turn**.  Returns ``None`` when there is nothing to
        inject (all sources empty).  When non-``None``, the caller must merge
        the result *into* the last user message content — prepend it — rather
        than inserting it as a separate message (the Anthropic API rejects
        consecutive user-role messages).

        Includes: wiki operational state, prior session memory, active dataset
        profile, token-budget guidance, plan-mode instructions, and any extras.
        """
        parts: list[str] = []
        op = self._operational_state()
        if op:
            parts.append(op)
        mem = self._session_memory_section(inputs.session_id)
        if mem:
            parts.append(mem)
        profile = self._profile_section(inputs.active_profile_summary)
        if profile:
            parts.append(profile)
        budget = self._token_budget_section(inputs.token_budget)
        if budget:
            parts.append(budget)
        plan = self._plan_mode_section(inputs.plan_mode)
        if plan:
            parts.append(plan)
        for key, value in inputs.extras.items():
            parts.append(f"\n\n## {key}\n\n{value.strip()}")
        return "".join(parts) if parts else None

    def build(self, inputs: InjectorInputs) -> str:
        """Build the full combined system prompt (static + dynamic).

        Kept for backward compatibility with callers that have not yet been
        updated to use :meth:`build_static` + :meth:`build_dynamic`.
        """
        parts = [
            self._static(),
            self._operational_state(),
            self._session_memory_section(inputs.session_id),
            self._skill_menu(),
            self._gotchas_section(),
            self._profile_section(inputs.active_profile_summary),
            self._token_budget_section(inputs.token_budget),
            self._plan_mode_section(inputs.plan_mode),
        ]
        for key, value in inputs.extras.items():
            parts.append(f"\n\n## {key}\n\n{value.strip()}")
        return "".join(parts)
