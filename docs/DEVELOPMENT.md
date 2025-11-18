# Development Guide

This guide covers development setup, code quality tools, testing, and project structure.

---

## Development Setup

### Prerequisites

- Python 3.10+
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
- **pytest** — Testing framework
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
pytest                    # Run all tests

# Or just commit - pre-commit runs automatically
git commit -m "your message"
```

All configuration is in `pyproject.toml`.

**Tip:** Pre-commit hooks run automatically when you commit, catching issues before they enter the repository.

---

## Testing

**Philosophy:** Error scenario tests only. Happy paths are tested through real-world usage.

```bash
# Activate venv (if not already active)
source .venv/bin/activate

# Run all error scenario tests
pytest

# With verbose output
pytest -v

# With coverage
pytest --cov=src
```

**Test coverage:**
- Exception handling (all error types)
- API/network errors
- Invalid inputs & missing files
- Workflow validation
- Configuration errors

---

## Arbeitsagentur API Resources

**Official Documentation:**
- **GitHub Repository:** https://github.com/bundesAPI/jobsuche-api
- **API Documentation:** https://jobsuche.api.bund.dev/

**Key API Parameters:**
- `veroeffentlichtseit` (days since publication):
  - **API Range:** 0-100 days
  - **Web UI Limit:** 28 days (4 weeks) at https://www.arbeitsagentur.de/jobsuche/
  - **Note:** The API supports a wider range than the web interface
- `wo` (location): Optional - omitting searches all of Germany

---

## Project Structure

```
jobsuche-py/
├── src/
│   ├── data/              # Data gathering and caching
│   │   ├── gatherer.py       # Job data orchestration
│   │   └── job_database.py   # Persistent job caching
│   ├── preferences/       # User profiles
│   │   └── user_profile.py   # CV loading
│   ├── llm/               # LLM processing
│   │   ├── processor.py
│   │   └── openrouter_client.py
│   ├── workflows/         # Matching workflow
│   │   ├── base.py
│   │   └── matching.py
│   ├── api_client.py      # Arbeitsagentur API
│   ├── scraper.py         # Web scraping
│   ├── classifier.py      # Classification logic
│   ├── analyzer.py        # Statistics
│   ├── session.py         # Session management
│   └── session_merger.py  # Session merging & deduplication
├── tests/                 # Error scenario tests
├── prompts.example.yaml   # Example prompt templates
├── main.py               # CLI entry point
└── README.md
```

---

## Core Development Principles

- **No Silent Failures** — Every error must be visible; never mask failures with default values
- **Exception Handling** — Use custom exceptions from `src/exceptions.py` (inherit from `JobSucheError`)
- **Virtual Environment** — activate `.venv` before any Python/pip/pytest/mypy/ruff command
- **Breaking Changes** — Acceptable, but always notify users what changed
- **Privacy** — Never commit personal information (CV, prompts.yaml, data/, .env, my_*.sh/py)
- **Configuration Priority** — Base defaults → User preferences → CLI args
- **Working with numbers** — Don't ask LLMs to count; use programmatic validation instead

---

## Key Features

### Incremental Job Fetching

**Architecture:** Persistent job caching to minimize redundant API calls and scraping.

**Database** (`data/database/jobs.json`):
- Persistent cache in current working directory
- Keys jobs by `refnr` (unique job ID)
- Detects new, updated, and unchanged jobs via `modifikationsTimestamp`

**Merge Algorithm:**
- **New job:** `refnr` not in database → Add, mark for processing
- **Updated job:** `refnr` exists, `modifikationsTimestamp` differs → Update, re-classify
- **Unchanged job:** `refnr` exists, `modifikationsTimestamp` identical → Skip processing

**Performance Impact:**
- **First run:** Full processing (e.g., 200 jobs × 1.5s = ~5 minutes)
- **Incremental run:** Delta only (e.g., 5 new jobs × 1.5s = ~8 seconds)
- **API savings:** ~95% reduction for daily updates
- **LLM cost savings:** Only classify new/modified jobs

### Session Merging

The `SessionMerger` class enables merging multiple search sessions:

```bash
python main.py --classify-only \
    --input data/searches/session1 data/searches/session2 \
    --cv cv.md
```

**Use case:** Search for multiple job titles (e.g., "Python Developer", "Backend Engineer"), then merge and classify together. Jobs are deduplicated by `refnr`.

### Session Metadata

Each session saves:
- **Session info** (`session_info_MA.json`) - Workflow type, search parameters, job counts
- **LLM thinking** (`debug/*_thinking.md`) - Extracted reasoning from models that support it

---
