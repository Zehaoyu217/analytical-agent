# Eval Judge Setup

The eval pipeline uses an LLM judge to grade qualitative dimensions (e.g. "correctness", "reasoning depth") against a rubric. Three judge implementations are available.

## Current default: OpenRouterJudge

`run_eval.py --judge` uses `OpenRouterJudge` with model `openai/gpt-oss-120b:free`.

**Prerequisites:**
- `OPENROUTER_API_KEY` set in `.env` or environment
- No local model required

**Usage:**
```bash
cd backend
uv run python scripts/run_eval.py --judge
```

The judge makes a direct chat completions call to `https://openrouter.ai/api/v1/chat/completions` — no agent loop, no tool calls.

---

## Reverting to Ollama (gemma4:e2b)

When `gemma4:e2b` loads reliably on your machine, switch back to `LLMJudge`:

### 1. Pull the model

```bash
ollama pull gemma4:e2b
```

Verify it loads without resource contention:
```bash
ollama run gemma4:e2b "Say hello"
```

### 2. Update run_eval.py

In `backend/scripts/run_eval.py`, change the judge instantiation:

```python
# Before (OpenRouter):
judge = OpenRouterJudge()

# After (Ollama):
from app.evals.judge import JudgeConfig, LLMJudge
judge = LLMJudge(JudgeConfig(model="gemma4:e2b"))
```

### 3. Update the help text

```python
# Change:
help="Enable LLM grading via OpenRouter (set OPENROUTER_API_KEY)",
# To:
help="Enable LLM grading via Ollama (requires gemma4:e2b loaded)",
```

---

## Judge classes

| Class | Backend | Model | When to use |
|-------|---------|-------|-------------|
| `OpenRouterJudge` | OpenRouter API | `openai/gpt-oss-120b:free` | Ollama unavailable / resource contention |
| `LLMJudge` | Local Ollama | `gemma4:e2b` (default) | Ollama running, model loaded |
| `FallbackJudge` | OpenRouter → Ollama | Both | Resilient runs; tries OpenRouter first |

### FallbackJudge (resilient option)

```python
from app.evals.judge import FallbackJudge
judge = FallbackJudge()  # tries OpenRouter, falls back to Ollama
```

---

## Custom model

```python
from app.evals.judge import OpenRouterJudgeConfig, OpenRouterJudge

judge = OpenRouterJudge(OpenRouterJudgeConfig(model="mistralai/mistral-7b-instruct:free"))
```

```python
from app.evals.judge import JudgeConfig, LLMJudge

judge = LLMJudge(JudgeConfig(model="llama3.2:3b", base_url="http://localhost:11434"))
```

---

## Troubleshooting

**`OPENROUTER_API_KEY` missing:**
The `OpenRouterJudge` constructor tries `os.environ` first, then falls back to loading `.env`. If the key is still missing, grading will raise `httpx.HTTPStatusError 401`.

**Ollama HTTP 500 on generate:**
Model is listed in `/api/tags` but fails to load — memory pressure. Free VRAM or use `OpenRouterJudge` instead.

**`Could not parse judge response`:**
The judge returned text that doesn't match `GRADE: <A|B|C|F> — <justification>`. This is grade `F` with score 0. Try a stronger model or check if the judge prompt is too long.
