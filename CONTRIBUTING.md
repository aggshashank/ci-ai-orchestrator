# Contributing

Thank you for your interest in contributing to the AI Decisioning Platform.

## Ways to contribute

- **Bug reports** — open a GitHub issue using the bug report template
- **Feature requests** — open a GitHub issue using the feature request template
- **Code** — fork the repo, make changes, open a pull request
- **Documentation** — improvements to `docs/` or inline comments
- **Policy documents** — add or improve the RAG policy corpus in `policy-documents/`

## Development setup

### Prerequisites

- Docker Desktop
- Python 3.11+
- Node 20+ (for the dashboard)
- Java 21 + Maven 3.9+ (for the decision-api)
- Ollama with `llama3:latest` and `nomic-embed-text` pulled

### First-time setup

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Install Python dependencies
cd ai-orchestrator
pip install -r requirements.txt

# 3. Run DB migrations
alembic upgrade head

# 4. Ingest policy documents
python -m rag.ingest

# 5. Start the orchestrator
uvicorn main:app --reload --port 8001

# 6. Dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

### Running tests

```bash
cd ai-orchestrator
pytest tests/ -v
```

All PRs must pass the full test suite before merge.

## Pull request guidelines

1. Fork the repo and create a feature branch from `main`
2. Keep PRs focused — one logical change per PR
3. Add or update tests for any new behaviour
4. Update `docs/` if you change an API or config option
5. Add an entry to `CHANGELOG.md` under `[Unreleased]`
6. Fill in the PR template

## Code style

- **Python**: PEP 8, 4-space indent. `ruff` for linting, `black` for formatting.
- **JavaScript/JSX**: 2-space indent. Functional components with hooks only.
- **No comments for what**: name your variables well. Comments only for non-obvious WHY.

## Commit messages

Use conventional commits:

```
feat: add revenue impact estimator
fix: correct 4/5ths rule denominator when segment has zero decisions
docs: add deployment-aws guide
test: add golden dataset for cross-sell workflow
```

## Reporting security issues

Do **not** open a public issue for security vulnerabilities.
Email `security@example.com` with details. We aim to respond within 48 hours.

## License

By contributing, you agree that your contributions will be licensed under the
Apache 2.0 License (see [LICENSE](LICENSE)).
