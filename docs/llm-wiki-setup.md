# llm_wiki sidecar setup

Integrate the [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) desktop
app as your KB extraction engine, while this project continues to handle
the chat UI, agent retrieval, and Knowledge-page browsing.

## Why

The in-house extractor does flat bullet-point claims from each source.
`llm_wiki` uses a two-stage **analyze → generate** pipeline that emits a
navigable Obsidian-style vault — one page per entity, one per concept,
one per source, cross-linked with `[[wikilinks]]`. See
`docs/second-brain/notes.md` for the architectural comparison.

This is the "A1 sidecar" path: **they do extraction, we do retrieval + UI**.

## Steps

### 1. Install llm_wiki

Download a release or build from source:

```bash
# macOS release download:
# https://github.com/nashsu/llm_wiki/releases

# Or build from source (requires Rust toolchain + Node.js + pnpm):
git clone https://github.com/nashsu/llm_wiki.git
cd llm_wiki
pnpm install
pnpm tauri dev      # run in dev mode
# or
pnpm tauri build    # produce a platform-native binary
```

### 2. Create a project in llm_wiki

Open the app. Click **New Project**. Point it at a directory you'll use
as the vault — we'll point this project at the same directory so the UI
picks it up.

Recommended path: `~/knowledge-vault/` (a fresh directory that's neither
of our existing `~/.ccagent/` nor `~/second-brain/`).

### 3. Configure llm_wiki's LLM provider

In llm_wiki's settings, add a provider:

- **OpenAI-compatible custom provider** (works with OpenRouter):
  - Base URL: `https://openrouter.ai/api/v1`
  - API key: your `OPENROUTER_API_KEY`
  - Model: `openai/gpt-oss-120b:free` (or any id you prefer)
- **Ollama** (local): point at `http://localhost:11434`
- **Anthropic** if you have that key

(llm_wiki does not natively support MLX. If you want local inference,
run Ollama.)

### 4. Point this project at the same vault

Either edit `.env` at the repo root:

```bash
echo "LLM_WIKI_DIR=$HOME/knowledge-vault" >> .env
```

Or set it in the **Settings → Environment** tab of the running app (UI
still requires a backend restart — env is read at boot).

Restart the backend:

```bash
make backend
```

### 5. Verify

1. Open `http://localhost:5173` → **Knowledge** section → the left
   sidebar tree should now show `~/knowledge-vault` contents (empty if
   you haven't ingested anything yet).
2. In llm_wiki's desktop app, ingest a PDF (File → Ingest). It writes
   `wiki/entities/*.md`, `wiki/concepts/*.md`, `wiki/sources/*.md` into
   your vault.
3. Refresh the Knowledge page. The new pages should appear in the tree.
   Click any to read the two-stage output.

## Resolution order (for debugging)

The Knowledge page's wiki root is resolved in this order — first match wins:

1. `$WIKI_ROOT` env var — explicit override
2. `$LLM_WIKI_DIR` env var **or** `llm_wiki_dir` AppConfig field
3. `$SECOND_BRAIN_HOME` when `SECOND_BRAIN_ENABLED` is true
4. `knowledge/wiki/` repo default

Check which one is active with:

```bash
curl -s http://127.0.0.1:8000/api/wiki/tree | head -c 200
```

## What this A1 integration does NOT do (yet)

- **No agent-retrieval integration.** Our pre-turn injection still uses
  Second Brain's BM25/vector store. llm_wiki pages don't feed the system
  prompt until we add an indexer for them (a planned follow-up — "B").
- **No one-click ingest from this UI.** You run llm_wiki's desktop app
  for extraction; this app is read-only over its output.
- **No migration of existing SB claims.** Your 37 SB claims stay under
  `~/second-brain/claims/` untouched. The Knowledge page prefers the
  llm_wiki vault when configured; remove `LLM_WIKI_DIR` to see SB again.

## Troubleshooting

**Tree is empty after pointing at the vault**

- The llm_wiki tree hides empty directories (our wiki walker skips any
  dir with no `.md` descendants). If you haven't ingested yet, only
  `llm-wiki.json` exists — which isn't markdown.
- Ingest at least one source in llm_wiki to populate `wiki/`.

**Settings page "Environment" tab shows LLM_WIKI_DIR as unset**

- The .env loader runs at backend startup. Restart `make backend` after
  editing .env.

**Path contains `~` and the backend can't find it**

- Use an absolute path in `.env`. Shell tilde-expansion doesn't apply
  when the value is read through `os.environ.get`.
