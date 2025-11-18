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
│   │   └── job_database.py   # Persistent job caching (NEW)
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
│   ├── session.py         # Session management
│   └── session_merger.py  # Session merging & deduplication
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

## Key Features

### Incremental Job Fetching

**Architecture:** Persistent job caching to minimize redundant API calls and scraping.

**Separation of Concerns:**
- **Database** (`data/database/jobs_global.json`): Tracks Arbeitsagentur job data for incremental fetching
- **Checkpoints** (`debug/classification_checkpoint.json`): Tracks classification progress within a session

**1. JobDatabase Class** (`src/data/job_database.py`)
- **Purpose:** Avoid re-fetching and re-scraping jobs from Arbeitsagentur
- **Scope:** Global, persistent across all searches
- **Storage:** JSON file at `data/database/jobs_global.json`, keyed by `refnr` (unique job ID)
- **Schema:**
  ```python
  {
    "metadata": {
      "created": "2025-11-17T10:00:00",
      "last_updated": "2025-11-17T14:00:00",
      "total_jobs": 203,
      "active_jobs": 203
    },
    "jobs": {
      "refnr": {
        "titel": "...",
        "modifikationsTimestamp": "2025-11-16T15:20:00",  # Key for change detection
        "aktuelleVeroeffentlichungsdatum": "2025-11-15",
        "details": {...},  # Scraped content
        "metadata": {
          "first_seen": "...",
          "last_seen": "..."
        },
        "found_in_searches": [...]  # Track which searches found this job
      }
    }
  }
  ```

**2. Merge Algorithm** (`JobDatabase.merge()`)
- **New job:** `refnr` not in database → Add to database, mark for processing
- **Updated job:** `refnr` exists, `modifikationsTimestamp` differs → Update database, mark for re-classification
- **Unchanged job:** `refnr` exists, `modifikationsTimestamp` identical → Update `last_seen`, skip processing
- **Returns:** Tuple of `(new_jobs, updated_jobs, unchanged_jobs)` for delta processing

**3. API Integration** (`api_client.py`)
- **Parameter:** `veroeffentlichtseit` (0-100 days) filters jobs by publication date
- **Date fields extracted:** `modifikationsTimestamp`, `aktuelleVeroeffentlichungsdatum`
- **Incremental mode:** When database exists, defaults to `veroeffentlichtseit=7` from config

**4. Workflow Integration** (`gatherer.py`)
- **Database check:** Load existing database or create new
- **Fetch strategy:**
  - Database exists → Use `veroeffentlichtseit` filter
  - No database → Full fetch (no filter)
- **Delta processing:** Only scrape/classify `new_jobs + updated_jobs`
- **Database update:** Save after scraping completes

**5. Testing Considerations**
- **Test isolation:** Use `@pytest.fixture(autouse=True)` with `clean_test_database` to remove `data/database/jobs_global.json` before/after each test
- **Temp paths:** Pass `tmp_path / "test_db.json"` to `JobGatherer(database_path=...)` for isolated tests
- **Coverage:** ~60% indirect coverage via `test_gatherer.py` (no dedicated unit tests yet)
- **Mock requirements:** Tests mock `search_jobs()` - ensure mock returns jobs with `modifikationsTimestamp` field

**6. Performance Impact**
- **First run:** Full processing (e.g., 200 jobs × 1.5s = ~5 minutes)
- **Incremental run:** Delta only (e.g., 5 new jobs × 1.5s = ~8 seconds)
- **API savings:** ~95% reduction for daily updates
- **LLM cost savings:** Only classify new/modified jobs

**7. Edge Cases Handled**
- Missing `modifikationsTimestamp` → Treat as new job
- Database corruption → Log error, raise exception (no silent failures)
- Empty API response → Keep existing database, return empty delta
- Multiple searches → Same `refnr` tracked across searches via `found_in_searches`

**8. Classification Recovery**
- **Not handled by database** - Use session checkpoints instead
- Classification failures: Re-run with `--classify-only --input <session_dir>`
- Changed criteria (CV, categories): Re-classify old sessions with `--classify-only`
- See "Re-Classification Scenarios" in README.md for details

### Session Merging

The `SessionMerger` class (`src/session_merger.py`) enables merging multiple search sessions:

```python
from src.session_merger import SessionMerger

merger = SessionMerger(verbose=True)
merged_jobs = merger.merge_sessions([
    "data/searches/20251112_084239",
    "data/searches/20251112_090241",
    "data/searches/20251112_091022",
])
```

**Use case:** Search for multiple job titles (e.g., "Python Developer", "Backend Engineer", "Software Engineer"), then merge and classify together. Jobs are deduplicated by `refnr` (Arbeitsagentur reference number).

**CLI usage:**
```bash
python main.py --classify-only --workflow matching \
    --input data/searches/session1 data/searches/session2 data/searches/session3 \
    --cv cv.md
```

### Session Metadata & Debugging

Each session now saves:
- **Session info** (`session_info_*.json`) - Workflow type, search parameters, job counts
- **LLM thinking** (`debug/*_thinking.md`) - Extracted reasoning process from models that support it

Filename conventions for session info:
- `session_info_MC.json` - MultiCategory workflow
- `session_info_MA.json` - Matching workflow
- `session_info_BR.json` - Brainstorm workflow
- `session_info_*_CO.json` - Classify-only sessions (appends `_CO`)

---
