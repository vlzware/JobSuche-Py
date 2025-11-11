# Development Guide

This guide covers development setup, code quality tools, testing, and project structure for contributors.

---

## Development Setup

### Prerequisites

- Python 3.x
- Virtual environment activated

### Installation

```bash
# Activate virtual environment (if not already active)
source .venv/bin/activate

# Install with development tools
pip install -e ".[dev]"

# Install pre-commit hooks (runs automatically on git commit)
pre-commit install
```

---

## Development Tools

This project uses automated code quality tools:

### Tools Used
- **ruff** — Fast Python linter and formatter (replaces Black, isort, flake8)
- **mypy** — Static type checker
- **pre-commit** — Git hooks for automated checks before commits

### Usage

```bash
# Ensure venv is activated
source .venv/bin/activate

# Manual checks
ruff check .              # Lint code
ruff check --fix .        # Lint and auto-fix issues
ruff format .             # Format code
mypy .                    # Type check

# Or just commit - pre-commit runs automatically
git commit -m "your message"
```

All configuration is in `pyproject.toml`.

**Tip:** Pre-commit hooks run automatically when you commit, catching issues before they enter the repository. Quality tools run separately from tests for faster feedback.

---

## Automated Tests

```bash
# Activate venv (if not already active)
source .venv/bin/activate

# Unit tests
pytest

# Integration tests
pytest -m integration
```

---

## Project Structure

```
jobsuche-py/
├── src/
│   ├── data/              # Data gathering
│   │   └── gatherer.py
│   ├── preferences/       # User profiles & categories
│   │   └── user_profile.py
│   ├── llm/               # LLM processing
│   │   └── processor.py
│   ├── workflows/         # Different use case workflows
│   │   ├── base.py
│   │   ├── multi_category.py
│   │   ├── matching.py
│   │   └── brainstorm.py
│   ├── api_client.py      # Arbeitsagentur API
│   ├── scraper.py         # Web scraping
│   ├── classifier.py      # Core classification logic
│   ├── analyzer.py        # Statistics
│   └── session.py         # Session management
├── categories.example.yaml # Example category config
├── prompts.example.yaml    # Example prompt templates
├── main.py                 # CLI entry point
└── README.md
```

---

## Core Development Principles

For use with _Claude.md_:

- **No Silent Failures** — Every error must be visible; never mask failures with default values
- **Exception Handling** — Use custom exceptions from `src/exceptions.py` (inherit from `JobSucheError`)
- **Virtual Environment** — activate `.venv` before any Python/pip/pytest/mypy/ruff command
- **Breaking Changes** — Acceptable, but always notify users what changed
- **Privacy** — Control the visibility in git for personal information (CV, categories.yaml, prompts.yaml, data/, .env, my_*.sh/py)
- **Configuration Priority** — Base defaults → User preferences → CLI args (later overrides earlier)
- **Working with numbers** — Don't ask LLMs to count or work with numbers in general, use programmatic validation instead. The same applies to Claude itself.

---
