# Eval Judge Setup

The eval pipeline uses an LLM judge to grade qualitative dimensions (e.g. "correctness", "reasoning depth") against a rubric. Three judge implementations are available.

## Current default local path: MLX `LLMJudge`

`LLMJudge()` now uses a local MLX model by default: `mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit`.

**Prerequisites:**
- `backend[mlx]` installed on Apple Silicon
- the judge model cached locally in Hugging Face / MLX cache

**Usage:**
```bash
cd backend
uv run python scripts/run_eval.py --no-judge   # deterministic-only
uv run python scripts/run_eval.py --judge      # local MLX judge
```

The judge makes a direct local MLX completion call — no agent loop, no tool calls.

---

## OpenRouter fallback

When you want a remote fallback, use `OpenRouterJudge` directly or `FallbackJudge`.

### 1. Set the API key

```bash
export OPENROUTER_API_KEY=...
```

### 2. Use `OpenRouterJudge`

```python
from app.evals.judge import OpenRouterJudge

judge = OpenRouterJudge()
```

The judge makes a direct chat completions call to `https://openrouter.ai/api/v1/chat/completions`.

---

## Local MLX model warmup

If you want to pre-download the default judge model manually:

```bash
cd backend
uv run --extra mlx python scripts/preload_mlx_models.py mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit --smoke
```

---

## Judge classes

| Class | Backend | Model | When to use |
|-------|---------|-------|-------------|
| `LLMJudge` | Local MLX | `mlx/mlx-community/gemma-4-e4b-it-OptiQ-4bit` (default) | Local evals, no Ollama required |
| `OpenRouterJudge` | OpenRouter API | `openai/gpt-oss-120b:free` | Remote fallback |
| `FallbackJudge` | OpenRouter → local MLX | Both | Resilient runs; tries OpenRouter first |

### FallbackJudge (resilient option)

```python
from app.evals.judge import FallbackJudge
judge = FallbackJudge()  # tries OpenRouter, falls back to local MLX
```

---

## Custom model

```python
from app.evals.judge import OpenRouterJudgeConfig, OpenRouterJudge

judge = OpenRouterJudge(OpenRouterJudgeConfig(model="mistralai/mistral-7b-instruct:free"))
```

```python
from app.evals.judge import JudgeConfig, LLMJudge

judge = LLMJudge(JudgeConfig(model="mlx/mlx-community/Qwen3.5-9B-OptiQ-4bit"))
```

---

## Troubleshooting

**`OPENROUTER_API_KEY` missing:**
The `OpenRouterJudge` constructor tries `os.environ` first, then falls back to loading `.env`. If the key is still missing, grading will raise `httpx.HTTPStatusError 401`.

**Local MLX warmup fails:**
The model may not be cached yet or the first local load may still be compiling. Preload it once with the `mlx_lm.load(...)` command above and retry.

**`Could not parse judge response`:**
The judge returned text that doesn't match `GRADE: <A|B|C|F> — <justification>`. This is grade `F` with score 0. Try a stronger model or check if the judge prompt is too long.
