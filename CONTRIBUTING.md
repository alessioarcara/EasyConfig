# Contributing to EasyConfig

Thank you for your interest in contributing! This guide will get you set up quickly.

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone https://github.com/alessioarcara/EasyConfig.git
cd EasyConfig

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (including dev extras)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

## Running Tests

```bash
uv run pytest                          # run all tests
uv run pytest --cov=src/ezconfy       # with coverage
uv run pytest tests/test_parser.py    # single module
```

## Type Checking

```bash
uv run mypy src/ezconfy --ignore-missing-imports
```

## Linting & Formatting

Pre-commit runs automatically on `git commit`. To run manually:

```bash
uv run ruff check src tests     # lint
uv run ruff format src tests    # format
```

## Submitting a Pull Request

1. Fork the repo and create a branch from `main`.
2. Make your changes with tests covering any new behaviour.
3. Run `pytest`, `mypy`, and `ruff` locally — all must pass.
4. Open a PR against `main`. Fill in the PR template.

## Reporting Issues

Use the [GitHub issue tracker](https://github.com/alessioarcara/EasyConfig/issues).  
Please use the provided templates for bug reports and feature requests.
