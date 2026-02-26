# Contributing to TIMEPOINT Flash

This is the open-source reference implementation of TIMEPOINT Flash — the AI-powered temporal simulation engine. Contributions are welcome.

## How It Works

This repo contains the full standalone pipeline: 14 agents, scene generation, evaluation, and storage. It ships with `NoOpBilling` so access is unlimited out of the box.

Changes merged here are periodically pulled into the production deployment (a separate private repo). Your contributions directly improve the live product at [timepointai.com](https://timepointai.com).

## Getting Started

```bash
git clone https://github.com/timepoint-ai/timepoint-flash.git
cd timepoint-flash
pip install -e ".[dev]"
cp .env.example .env    # Add your API keys
alembic upgrade head
./run.sh -r
```

## Submitting Changes

1. Fork the repo and create a feature branch
2. Make your changes
3. Run tests: `pytest -m fast -v`
4. Run linting: `ruff check app/ tests/`
5. Open a pull request against `main`

## What to Contribute

- Bug fixes and performance improvements
- New agents or pipeline enhancements
- Documentation improvements
- Test coverage

## Code Style

- Python 3.10+, type hints throughout
- Ruff for linting and formatting (`ruff check`, `ruff format`)
- Async-first (FastAPI + SQLAlchemy async)
- Tests with pytest-asyncio

## License

Apache 2.0 — see [LICENSE](LICENSE).
