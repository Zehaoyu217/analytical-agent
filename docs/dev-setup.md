# Development Setup

## Prerequisites

- Python 3.12+
- Node.js 20+ (for frontend)
- Docker + Docker Compose (for local services)
- Ollama (for local models)

## Quick Start

```bash
# 1. Clone and enter
git clone https://github.com/Zehaoyu217/analytical-agent.git
cd analytical-agent

# 2. Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ..

# 3. Frontend
cd frontend
npm install
cd ..

# 4. Environment
cp .env.example .env
# Edit .env with your settings

# 5. Start everything
make dev
```

## Individual Services

```bash
make backend          # Backend only (uvicorn on :8000)
make frontend         # Frontend only (vite on :5173)
```

## Running Tests

```bash
make test             # All tests
make test-backend     # Backend only (pytest)
make test-frontend    # Frontend only (vitest)
```

## MLX Local Model Setup

```bash
cd backend
uv sync --extra mlx
uv run --extra mlx python scripts/preload_mlx_models.py --smoke
```

---

## Critical: How the Backend Must Be Started

> These rules exist because of hard-won debugging — violating any one of them
> produces a symptom that looks unrelated to the actual cause.

### 1. Always start from the `backend/` directory

```bash
# CORRECT
cd backend && uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

# WRONG — .env will not load
uvicorn backend.app.main:create_app --factory ...
```

**Why:** `AppConfig` in `app/config.py` sets `env_file = "../.env"`. This path is
resolved relative to the **current working directory at startup**, not relative to
the source file. Starting from the project root makes `../.env` point one level
*above* the project, so `OPENROUTER_API_KEY` and other secrets are never loaded.

### 2. Always use the `--factory` flag

```bash
# CORRECT
uvicorn app.main:create_app --factory --reload ...

# WRONG — produces "Attribute 'app' not found in module 'app.main'"
uvicorn app.main:app --reload ...
```

**Why:** `app/main.py` exports a `create_app()` factory function, not a module-level
`app` variable. The `--factory` flag tells uvicorn to call `create_app()` at startup
instead of looking for a module attribute.

The `Makefile` already encodes both rules:

```makefile
backend:
	cd backend && uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Run `make backend` rather than invoking uvicorn directly.

---

## Environment Variables

Place secrets in `<project-root>/.env` (one level above `backend/`):

```
# .env
OPENROUTER_API_KEY=sk-or-v1-...
```

`pydantic-settings` reads this file automatically when the backend is started from
`backend/`. Do not duplicate variables in `backend/.env` — there is only one `.env`
file.

---

## OpenRouter Models

Only models that list `"tools"` in their `supported_parameters` actually support
function calling. Before adding a new model to `app/api/models_api.py`, verify it:

```bash
curl -s "https://openrouter.ai/api/v1/models" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
for m in data['data']:
    if 'tools' in m.get('supported_parameters', []):
        print(m['id'])
"
```

Models that say `"No endpoints found that support tool use"` at runtime are not
usable with this agent regardless of what they advertise.

---

## DuckDB / Data Pipeline

The shared analytical database lives at `backend/data/duckdb/eval.db`. It is
created on first backend startup by `initialize_db()` in `app/data/db_init.py`.

Source data is loaded from `BANK_MACRO_DATA_DIR` (default:
`~/Developer/bank-macro-analysis/data/processed`). If that directory is absent,
startup skips loading and logs a warning — the backend still works, but
`bank_macro_panel` and `bank_wide` tables will not exist.

The schema is injected into the agent system prompt on every request via
`get_data_context()` so the model knows what columns are available without a
separate schema lookup.

---

## Vite Proxy

`frontend/vite.config.ts` proxies `/api/*` to the backend. The target port **must
match** the backend port (default `8000`). A mismatch causes silent failures — API
calls return connection refused, the frontend falls back to Zustand-persisted state,
and the model dropdown appears to work but never fetches live data.

```ts
// vite.config.ts — must match the uvicorn port
proxy: {
  '/api': { target: 'http://localhost:8000', ... }
}
```
