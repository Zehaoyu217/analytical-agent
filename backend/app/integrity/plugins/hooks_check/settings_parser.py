"""Parser for ``.claude/settings.json`` → flat ``list[HookRecord]``.

Strict: any structural violation raises ``ValueError`` with a path prefix.
Missing file returns ``[]`` (handled at plugin layer as "no hooks configured").

Claude Code's settings.json schema (v2)::

    {
      "hooks": {
        "<EventName>": [
          {"matcher": "<pipe-joined>", "hooks": [{"type": "command", "command": "..."}]}
        ]
      }
    }

The top-level event names (PreToolUse, PostToolUse, Stop, UserPromptSubmit, ...)
are not validated against an enum — Claude Code adds new events over time and we
shouldn't fail a scan because the user adopted a new event before this code knew
about it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HookRecord:
    event: str
    matcher: str
    command: str
    source_index: tuple[int, int, int]


def parse_settings(path: Path) -> list[HookRecord]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: JSON parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level must be a JSON object")

    hooks_root = data.get("hooks")
    if hooks_root is None:
        return []
    if not isinstance(hooks_root, dict):
        raise ValueError(f"{path}: 'hooks' must be an object")

    records: list[HookRecord] = []
    for event, blocks in hooks_root.items():
        if not isinstance(blocks, list):
            raise ValueError(
                f"{path}: 'hooks.{event}' must be a list, "
                f"got {type(blocks).__name__}"
            )
        for block_idx, block in enumerate(blocks):
            if not isinstance(block, dict):
                raise ValueError(
                    f"{path}: 'hooks.{event}[{block_idx}]' must be an object"
                )
            matcher = block.get("matcher", "")
            if not isinstance(matcher, str):
                raise ValueError(
                    f"{path}: 'hooks.{event}[{block_idx}].matcher' "
                    f"must be a string"
                )
            inner = block.get("hooks", [])
            if not isinstance(inner, list):
                raise ValueError(
                    f"{path}: 'hooks.{event}[{block_idx}].hooks' must be a list"
                )
            event_block_idx = list(hooks_root.keys()).index(event)
            for hook_idx, hook in enumerate(inner):
                if not isinstance(hook, dict):
                    raise ValueError(
                        f"{path}: 'hooks.{event}[{block_idx}]"
                        f".hooks[{hook_idx}]' must be an object"
                    )
                if hook.get("type") != "command":
                    continue
                command = hook.get("command")
                if not isinstance(command, str):
                    raise ValueError(
                        f"{path}: 'hooks.{event}[{block_idx}]"
                        f".hooks[{hook_idx}].command' must be a string"
                    )
                records.append(HookRecord(
                    event=event,
                    matcher=matcher,
                    command=command,
                    source_index=(event_block_idx, block_idx, hook_idx),
                ))
    return records
