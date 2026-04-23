# Analytical Agent

Full-stack analytical platform for MLE, data scientists, and quants. AI-powered data analysis with transparent agent operations.

## Quick Start

```bash
cd backend && pip install -e ".[dev]"
cd frontend && npm install
make dev
```

Open http://localhost:5173

## Documentation

- [Development Setup](docs/dev-setup.md)
- [Architecture](docs/architecture.md)
- [Testing Guide](docs/testing.md)
- [Skill Creation](docs/skill-creation.md)
- [Nested Knowledge Engine](components/second-brain/README.md)

## Project Structure

```
backend/       Python/FastAPI backend
frontend/      React+Vite analytical UI
components/    Nested standalone subsystems such as second-brain
reference/     Claude Code CLI source (read-only study material)
knowledge/     Wiki, ADRs, graphify graphs
docs/          SOPs and guides
infra/         Docker, Helm, Grafana, Ollama
mcp/           MCP explorer server
```

## License

See [LICENSE](LICENSE).
