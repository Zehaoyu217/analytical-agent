"""Render host-app wiring instructions for a newly-initialised KB."""
from __future__ import annotations

_TEMPLATE = """\
claude-code-agent integration
-----------------------------

1. Export the data home in your shell so backend + hooks agree:

     export SECOND_BRAIN_HOME={home}

2. Symlink the `sb` CLI onto your PATH (if not already):

     ln -s "$(pwd)/.venv/bin/sb" ~/.local/bin/sb

3. Ensure the following hooks are present in the host repo's
   `.claude/settings.json`:

     "UserPromptSubmit": [
       {{"command": "sb inject --k 5 --scope claims --max-tokens 800 --prompt-stdin"}}
     ],
     "PostToolUse": [
       {{"matcher": "sb_ingest|sb_promote_claim",
         "command": "sb reindex"}}
     ]

4. Restart the claude-code-agent backend so `SECOND_BRAIN_ENABLED` picks
   up the now-present `.sb/` directory.
"""


def render_wiring_instructions(home: str | None = None) -> str:
    home_txt = home or "$HOME/second-brain"
    return _TEMPLATE.format(home=home_txt)
