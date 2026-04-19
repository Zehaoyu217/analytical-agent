.PHONY: dev backend frontend test test-backend test-frontend lint typecheck check \
        skill-check skill-eval skill-new wiki-lint graphify seed-data \
        seed-eval eval eval-trace clean-traces sop \
        docker-build docker-up integrity-augment integrity-test \
        e2e-panels

# Development
dev:
	@echo "Starting backend and frontend..."
	$(MAKE) -j2 backend frontend

backend:
	@if [ ! -x backend/.venv/bin/uvicorn ]; then \
		echo "[backend] .venv missing — bootstrapping with uv sync..."; \
		cd backend && uv sync; \
	fi
	cd backend && .venv/bin/uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

# Quality
lint:
	cd backend && .venv/bin/ruff check . --fix
	cd frontend && npm run lint

typecheck:
	cd backend && .venv/bin/mypy app/
	cd frontend && npx tsc --noEmit

check: lint typecheck integrity ## Full quality pipeline: lint + typecheck + integrity graph audit

test: test-backend test-frontend

test-backend:
	cd backend && uv run python -m pytest -v --tb=short

test-frontend:
	cd frontend && npm test 2>/dev/null || echo "No frontend tests yet"

e2e-panels:
	cd frontend && pnpm playwright test e2e/panels.spec.ts 2>/dev/null || cd frontend && npx playwright test e2e/panels.spec.ts

# Skills
skill-check:
	cd backend && .venv/bin/python3 -m app.skills.manifest

skill-eval:
ifdef skill
	cd backend && python -m pytest tests/evals/test_$(skill).py -v
else
	cd backend && python -m pytest tests/evals/ -v 2>/dev/null || echo "No skill evals yet"
endif

skill-new:
ifndef name
	$(error Usage: make skill-new name=<skill_name> [parent=<parent_skill>] [type=reference])
endif
ifdef parent
	$(eval SKILL_DIR := backend/app/skills/$(parent)/$(name))
else
	$(eval SKILL_DIR := backend/app/skills/$(name))
endif
ifdef parent
	@# Ensure parent hub has __init__.py for Python import traversal
	@touch backend/app/skills/$(parent)/__init__.py
endif
	@mkdir -p $(SKILL_DIR)
ifdef type
	@# Reference skill: no pkg/, description prefixed with [Reference]
	@printf -- "---\nname: $(name)\ndescription: '[Reference] Describe what this documents and when to load it.'\nversion: '0.1'\n---\n# $(name)\n\nReference documentation.\n\n## Contents\n\n...\n" > $(SKILL_DIR)/SKILL.md
else
	@mkdir -p $(SKILL_DIR)/pkg
	@mkdir -p $(SKILL_DIR)/tests
	@touch $(SKILL_DIR)/pkg/__init__.py
	@printf -- "---\nname: $(name)\ndescription: 'One-line description of what this skill does.'\nversion: '0.1'\n---\n# $(name)\n\nOne-paragraph overview.\n\n## When to use\n\n...\n\n## Contract\n\n...\n" > $(SKILL_DIR)/SKILL.md
endif
	@printf "dependencies:\n  requires: []\n  used_by: []\n  packages: []\nerrors: {}\n" > $(SKILL_DIR)/skill.yaml
	@echo "Skill scaffolded at $(SKILL_DIR)/"
ifdef parent
	@echo "Hub: backend/app/skills/$(parent)/ — $(name) is now a sub-skill."
endif

# Knowledge
wiki-lint:
	cd backend && .venv/bin/python -m app.wiki.lint $(if $(strict),--strict,)

graphify:
	bash scripts/run_graphify.sh $(args)

# Data
seed-data:
	cd backend && .venv/bin/python -m scripts.seed_data

# Eval framework
seed-eval:
	cd backend && python -m scripts.seed_eval_data

eval:
ifdef level
	cd backend && python -m pytest tests/evals/test_level$(level).py -v -s
else
	cd backend && python -m pytest tests/evals/ -v -s
endif

eval-trace:
	TRACE_MODE=always $(MAKE) eval

clean-traces:
	cd backend && uv run python -m app.trace.retention --clear-all

# SOP
sop:
ifndef level
	$(error Usage: make sop level=<1..5>)
endif
	cd backend && uv run python -m app.sop.cli --level $(level)

# Infrastructure
COMPOSE_FILE := infra/docker/docker-compose.yml

docker-build:
	docker compose -f $(COMPOSE_FILE) build

docker-up:
	docker compose -f $(COMPOSE_FILE) up -d

# Integrity (self-maintaining graph)
.PHONY: integrity-augment integrity-test
integrity-augment:
	cd backend && uv run python -m app.integrity.plugins.graph_extension --repo-root ..

integrity-test:
	cd backend && uv run python -m pytest tests/integrity/ -v

.PHONY: integrity integrity-lint integrity-doc integrity-config integrity-hooks integrity-autofix integrity-autofix-apply integrity-autofix-sync integrity-snapshot-prune

integrity: ## Run the full integrity pipeline (A→B→C→D→E→F); writes integrity-out/ + docs/health/
	uv run python -m backend.app.integrity

integrity-lint: ## Run only Plugin B (graph_lint) — assumes A has run
	uv run python -m backend.app.integrity --plugin graph_lint --no-augment

integrity-doc: ## Run only Plugin C (doc_audit) — assumes A has run
	uv run python -m backend.app.integrity --plugin doc_audit --no-augment

integrity-config: ## Run only Plugin E (config_registry) — gate δ
	uv run python -m backend.app.integrity --plugin config_registry --no-augment

integrity-hooks: ## Run only Plugin D (hooks_check) — gate ε
	uv run python -m backend.app.integrity --plugin hooks_check --no-augment

integrity-autofix: ## Run only Plugin F (autofix) — gate ζ — DRY-RUN
	uv run python -m backend.app.integrity --plugin autofix --no-augment

integrity-autofix-apply: ## Run Plugin F in APPLY mode — opens PRs (gated by config)
	uv run python -m backend.app.integrity --plugin autofix --no-augment --apply

integrity-autofix-sync: ## Update config/autofix_state.yaml from merged autofix PRs
	uv run python -m backend.app.integrity.plugins.autofix.sync

integrity-snapshot-prune: ## Prune integrity-out/snapshots/ older than 30 days
	uv run python -c "from datetime import date; from pathlib import Path; from backend.app.integrity.snapshots import prune_older_than; n = prune_older_than(Path.cwd(), days=30, today=date.today()); print(f'pruned {n}')"
