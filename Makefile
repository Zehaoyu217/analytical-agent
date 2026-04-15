.PHONY: dev backend frontend test test-backend test-frontend lint typecheck \
        skill-check skill-eval skill-new wiki-lint graphify seed-data \
        seed-eval eval eval-trace clean-traces sop \
        docker-build docker-up

# Development
dev:
	@echo "Starting backend and frontend..."
	$(MAKE) -j2 backend frontend

backend:
	cd backend && uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

# Quality
lint:
	cd backend && ruff check . --fix
	cd frontend && npm run lint 2>/dev/null || true

typecheck:
	cd backend && mypy app/
	cd frontend && npx tsc --noEmit 2>/dev/null || true

test: test-backend test-frontend

test-backend:
	cd backend && uv run python -m pytest -v --tb=short

test-frontend:
	cd frontend && npm test 2>/dev/null || echo "No frontend tests yet"

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
	@mkdir -p $(SKILL_DIR)/references
	@mkdir -p $(SKILL_DIR)/tests
	@mkdir -p $(SKILL_DIR)/evals/fixtures
	@touch $(SKILL_DIR)/pkg/__init__.py
	@printf -- "---\nname: $(name)\ndescription: ''\nlevel: 1\nversion: '0.1'\n---\n# $(name)\n\nOne-paragraph overview.\n\n## When to use\n\n...\n\n## Contract\n\n...\n" > $(SKILL_DIR)/SKILL.md
endif
	@printf "dependencies:\n  requires: []\n  used_by: []\n  packages: []\nerrors: {}\n" > $(SKILL_DIR)/skill.yaml
	@echo "Skill scaffolded at $(SKILL_DIR)/"
ifdef parent
	@echo "Hub: backend/app/skills/$(parent)/ — $(name) is now a sub-skill."
endif

# Knowledge
wiki-lint:
	cd backend && python -m app.wiki.lint 2>/dev/null || echo "Wiki lint not yet implemented"

graphify:
	@echo "Running graphify..." && echo "Not yet implemented"

# Data
seed-data:
	@echo "Seeding sample data..." && echo "Not yet implemented"

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
docker-build:
	docker compose build

docker-up:
	docker compose up -d
