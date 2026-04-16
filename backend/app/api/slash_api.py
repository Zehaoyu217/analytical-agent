"""REST endpoint for the slash-command registry.

Slash commands are dispatched client-side (see ChatInput.tsx). The backend
only owns the canonical command list so the frontend stays in sync if the
catalog changes.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api/slash", tags=["slash"])


class SlashCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    description: str


SLASH_COMMANDS: list[SlashCommand] = [
    SlashCommand(id="help", label="/help", description="Show slash command reference"),
    SlashCommand(id="clear", label="/clear", description="Clear current conversation view"),
    SlashCommand(id="new", label="/new", description="Start a new conversation"),
    SlashCommand(id="settings", label="/settings", description="Open settings"),
]


@router.get("")
def list_slash_commands() -> list[SlashCommand]:
    return SLASH_COMMANDS
