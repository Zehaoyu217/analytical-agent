# Gotchas

Known pitfalls, workarounds, and things that will bite you. Append-only with dates.

---

## [2026-04-11] reference/ is read-only

The `reference/` directory contains the original Claude Code CLI source. Do not modify files there. If you need to study a pattern, read it and reimplement in `backend/` or `frontend/`.

## [2026-04-11] Skill evals are sealed

The `evals/` directory inside each skill is never loaded into the agent's context. This is by design — the agent must not know what the eval assertions check for.

## [2026-04-14] Sandbox subprocess does not inherit `sys.path` from backend

The sandbox runs user code by writing it to a temp file in `/tmp/` and executing it
as a subprocess. Python sets `sys.path[0]` to the directory of the running script,
which is `/tmp/...` — **not** the backend directory. This means `import config`,
`from app.skills import ...`, and all project-internal imports fail with
`ModuleNotFoundError`, even though they work fine in the main process.

**Symptom:** The agent reports "Altair theme module not available" or other
misleading import errors when executing any code that imports project packages.

**Fix:** `sandbox_bootstrap.py` inserts `_BACKEND_DIR` (the absolute path to
`backend/`) into `sys.path` at the top of every generated preamble:

```python
if '/path/to/backend' not in sys.path:
    sys.path.insert(0, '/path/to/backend')
```

This is computed at module load time via `Path(__file__).resolve().parent.parent.parent`.

## [2026-04-14] OpenRouter multi-turn tool calls require `tool_calls` in assistant message

When an LLM makes a tool call, the subsequent user message references the call by
`tool_call_id`. For this to be valid, the *assistant message that preceded it* must
include `tool_calls` with the same IDs. Without it, OpenRouter returns the model's
tool call response but then fails to associate the tool result — the final response
comes back as empty content (`null`).

**Symptom:** Agent calls the tool, code runs, but the final text response is `""`.

**Root cause:** `Message` dataclass had no `tool_calls` field, so the assistant
message stored in conversation history was `{"role": "assistant", "content": ""}`,
stripped of the original `tool_calls` array.

**Fix:** Added `tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)` to
`Message`, updated all loop paths to pass `tool_calls=tuple(resp.tool_calls)` on the
assistant message, and updated the `OpenRouterClient` payload serializer (see `backend/app/harness/clients/openrouter_client.py`) to emit it:

```python
{"role": "assistant", "content": null, "tool_calls": [{...}]}
```

## [2026-04-14] Backend `--factory` flag and CWD are both required

See `docs/dev-setup.md` — Critical: How the Backend Must Be Started. Short version:

1. **Missing `--factory`** → `uvicorn` crashes with *"Attribute 'app' not found in module 'app.main'"* because `main.py` exports a factory function, not an `app` variable.
2. **Wrong CWD** → `pydantic-settings` resolves `env_file = "../.env"` relative to CWD, so secrets (e.g. `OPENROUTER_API_KEY`) silently fail to load. The API key ends up as `""` and every OpenRouter call returns 401.

Always use `make backend` (which runs `cd backend && uvicorn app.main:create_app --factory ...`) rather than invoking uvicorn directly from the project root.

## [2026-04-15] DO NOT modify the model list in models_api.py

`backend/app/api/models_api.py` contains a hardcoded list `_OPENROUTER_MODELS`. **Claude must never change this list** unless the user explicitly asks to add or remove a specific model. It has been silently modified in multiple sessions (Llama 4 Scout/Maverick → current set), breaking the user's configured workflow each time.

**Symptom:** After a coding session, the model selector dropdown shows a completely different set of models than before. The previously-selected model ID may no longer appear, so the selector resets to the first item.

**Root cause:** Claude refactors or "improves" the model list as a side effect of touching nearby code in models_api.py (e.g., adding Ollama filtering, updating OpenRouter models). Each refactor overwrites models the user was actually using.

**Rule:** The `_OPENROUTER_MODELS` list is **user-owned configuration**. Treat it like a `.env` file — read it for context, never overwrite it.

**To add/remove models:** Only do so on explicit user instruction, e.g., *"add claude-3-5-haiku to the model list"*.

## [2026-04-15] Tailwind opacity modifier breaks on CSS variable colors

`bg-brand-accent/8` (or any `/N` opacity modifier) does **not** work when the color token is defined as a plain CSS variable like `var(--color-accent)` that holds a hex value. Tailwind tries to generate `rgb(var(--color-accent) / 0.08)` which is invalid CSS when the variable contains `#e0733a`.

**Symptom:** Selected/active item background is invisible in menus, dropdowns, or highlighted rows.

**Fix:** Use a concrete Tailwind surface color instead:
- Instead of `bg-brand-accent/8` → use `bg-surface-800`
- Instead of `bg-brand-accent/10` → use `bg-surface-800`

Or define the CSS variable with RGB components so Tailwind can inject alpha:
```css
--color-accent-rgb: 224 115 58; /* same as #e0733a */
```
then use `bg-[rgb(var(--color-accent-rgb)/0.08)]` in Tailwind.
