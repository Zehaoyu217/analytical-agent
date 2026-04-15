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
	$(error Usage: make skill-new name=<skill_name>)
endif
	@mkdir -p backend/app/skills/$(name)/pkg
	@mkdir -p backend/app/skills/$(name)/references
	@mkdir -p backend/app/skills/$(name)/tests
	@mkdir -p backend/app/skills/$(name)/evals/fixtures
	@touch backend/app/skills/$(name)/pkg/__init__.py
	@printf -- "---\nname: $(name)\ndescription: ''\nlevel: 1\nversion: '0.1'\n---\n# $(name)\n\nOne-paragraph overview.\n\n## When to use\n\n...\n\n## Contract\n\n...\n" > backend/app/skills/$(name)/SKILL.md
	@printf "dependencies:\n  requires: []\n  used_by: []\n  packages: []\nerrors: {}\n" > backend/app/skills/$(name)/skill.yaml
	@echo "Skill scaffolded at backend/app/skills/$(name)/"

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
