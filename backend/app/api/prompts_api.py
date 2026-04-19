"""GET /api/prompts — expose the prompt catalog to the frontend."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptEntry(BaseModel):
    id: str
    category: str  # "system" | "skill_injection" | "tool_description" | "injector_template"
    label: str
    description: str
    layer: str  # "L1" | "L2" | "tool"
    compactable: bool
    approx_tokens: int  # rough estimate: len(text) // 4
    text: str


def _skills_root() -> Path:
    return Path(os.environ.get("SKILLS_ROOT", "app/skills"))


def _injector_prompt_path() -> Path:
    """Return the static injector prompt path if it exists."""
    candidates = [
        Path("app/harness/prompts/pre_turn.md"),
        Path("app/harness/pre_turn.md"),
        Path("app/prompts/pre_turn.md"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path("app/harness/prompts/pre_turn.md")


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _get_system_prompt() -> str:
    # Build a fresh prompt for the devtools view — _SYSTEM_PROMPT was removed
    # to avoid eager singleton init at import time.
    from app.api.chat_api import _build_system_prompt  # noqa: PLC0415
    return _build_system_prompt()


def _get_tool_schemas() -> list[dict]:
    from app.api.chat_api import _CHAT_TOOLS  # noqa: PLC0415
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in _CHAT_TOOLS
    ]


def _get_injector_template() -> str:
    """Build a representative injector template showing its structure."""
    prompt_path = _injector_prompt_path()
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    # Return a representative template showing the injector structure
    return "\n".join([
        "## Operational State",
        "",
        "### working.md",
        "",
        "{working_digest}",
        "",
        "### index.md",
        "",
        "{index_digest}",
        "",
        "## Skill Menu",
        "",
        "{skill_menu}",
        "",
        "## Statistical Gotchas",
        "",
        "{gotchas}",
        "",
        "## Active Dataset Profile",
        "",
        "{profile_summary}",
    ])


def _read_skill_md(skill_dir: Path) -> str:
    """Read SKILL.md from a skill directory."""
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        return skill_md.read_text(encoding="utf-8")
    return ""


def _skill_description(skill_md_text: str, fallback_name: str) -> str:
    """Extract description from SKILL.md frontmatter or first paragraph."""
    import yaml  # noqa: PLC0415

    lines = skill_md_text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        # No frontmatter — extract first paragraph
        for line in skill_md_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped
        return fallback_name

    try:
        end = next(
            i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        return fallback_name

    raw = "".join(lines[1:end])
    try:
        parsed = yaml.safe_load(raw)
    except Exception:
        return fallback_name

    if isinstance(parsed, dict) and parsed.get("description"):
        return str(parsed["description"])

    return fallback_name


@router.get("")
def list_prompts() -> list[PromptEntry]:
    """Return all prompt entries: system, skill injections, tools, injector template."""
    entries: list[PromptEntry] = []

    # 1. System prompt
    system_text = _get_system_prompt()
    entries.append(PromptEntry(
        id="system_prompt",
        category="system",
        label="System Prompt",
        description="Core identity and behavioral rules injected into every chat request.",
        layer="L1",
        compactable=False,
        approx_tokens=_approx_tokens(system_text),
        text=system_text,
    ))

    # 2. Skill injections — one per discovered skill SKILL.md
    skills_root = _skills_root()
    if skills_root.exists():
        for skill_dir in sorted(skills_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md_text = _read_skill_md(skill_dir)
            if not skill_md_text:
                continue
            skill_name = skill_dir.name
            description = _skill_description(skill_md_text, skill_name)
            entries.append(PromptEntry(
                id=f"skill_{skill_name}",
                category="skill_injection",
                label=skill_name,
                description=description,
                layer="L2",
                compactable=True,
                approx_tokens=_approx_tokens(skill_md_text),
                text=skill_md_text,
            ))

    # 3. Tool descriptions
    try:
        tool_schemas = _get_tool_schemas()
    except Exception:
        tool_schemas = []

    for tool in tool_schemas:
        desc_text = tool.get("description", "")
        schema_text = json.dumps(tool.get("input_schema", {}), indent=2)
        full_text = f"Description:\n{desc_text}\n\nInput Schema:\n{schema_text}"
        entries.append(PromptEntry(
            id=f"tool_{tool['name']}",
            category="tool_description",
            label=tool["name"],
            description=desc_text[:120] + "..." if len(desc_text) > 120 else desc_text,
            layer="tool",
            compactable=False,
            approx_tokens=_approx_tokens(full_text),
            text=full_text,
        ))

    # 4. Injector template
    injector_text = _get_injector_template()
    entries.append(PromptEntry(
        id="injector_pre_turn",
        category="injector_template",
        label="Pre-Turn Injector",
        description="Dynamic context injected before each turn: operational state, skill menu, gotchas, dataset profile.",  # noqa: E501
        layer="L2",
        compactable=True,
        approx_tokens=_approx_tokens(injector_text),
        text=injector_text,
    ))

    return entries
