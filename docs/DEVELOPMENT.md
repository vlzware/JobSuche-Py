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
- `wo` (location): Optional - omitting searches all available (Germany, Austria, ...). Set "Deutschland (Land)" for Germany

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

## Architecture Details

### Incremental Job Fetching

**Problem:** Fetching and processing 100s of jobs daily is expensive (API calls, scraping, LLM costs).

**Solution:** Persistent job caching with smart delta detection.

**Database** (`data/database/jobs.json`):
- Persistent cache in current working directory
- Keys jobs by `refnr` (unique job ID from Arbeitsagentur)
- Stores scraped job details (full descriptions, URLs, metadata)
- Does NOT store classifications (those live in sessions)

**Merge Algorithm:**
1. **First run:** Database empty → fetch all jobs → create database
2. **Subsequent runs:** Database exists → fetch only last N days (default: 7)
3. **Merge logic:**
   - **New job:** `refnr` not in database → Add, mark for processing
   - **Updated job:** `refnr` exists, `modifikationsTimestamp` differs → Update, re-process
   - **Unchanged job:** `refnr` exists, `modifikationsTimestamp` identical → Skip processing

**Configuration:**
- `config/search_config.yaml`: Set `veroeffentlichtseit` (days) for incremental window
- CLI override: `--veroeffentlichtseit N` (1-100 days)

**Performance Impact:**
- **First run:** 200 jobs × 1.5s = ~5 minutes
- **Incremental:** 5 new jobs × 1.5s = ~8 seconds
- **API savings:** ~95% reduction for daily updates
- **LLM cost savings:** Only classify new/modified jobs

### Session Management & Checkpoints

**Session Structure:**
- Each run creates timestamped directory: `data/searches/YYYYMMDD_HHMMSS/`
- Contains classifications, results, and checkpoints for that run
- Database remains single source of truth for scraped job data

**Checkpoint System:**
- Saved after each mega-batch during classification
- Files: `debug/classification_checkpoint.json`, `debug/partial_classified_jobs.json`
- Automatic resume on re-run with `--session <timestamp>`
- Cleanup after successful completion

**Use Cases:**
1. **LLM failures mid-classification:**
   ```bash
   # First run fails at job 1500/3600
   python main.py --from-database --cv cv.md
   # → Session: data/searches/20231125_150000

   # Resume from checkpoint
   python main.py --from-database --cv cv.md --session 20231125_150000
   ```

2. **Re-classification workflows:**
   - `--from-database` loads ALL jobs from database (no API calls)
   - Creates new session with updated classifications
   - Database unchanged (still has original scraped data)

**Session Metadata:**
- `SUMMARY.txt` — Human-readable summary with session info, statistics, and file index
- `debug/session.log` — Complete execution log
- `debug/*_thinking.md` — LLM reasoning in markdown (all example models support thinking)
- `debug/*_thinking.html` — LLM reasoning in HTML with clickable job links and metadata
- `debug/thinking_index.html` — Searchable index mapping jobs to their batch thinking logs

**Thinking Extraction:**
All example models (Gemini Flash/Pro, Grok) support thinking/reasoning extraction. The system captures the LLM's reasoning process and exports it in both markdown and HTML formats. HTML exports include:
- Clickable job references (links to job details in JSON)
- Batch metadata (job titles, employers, locations)
- Cross-referenced thinking logs via searchable index

**LLM Prompt Design (Hybrid Approach):**
The classification system uses a hybrid approach for job identification:
1. **Internal tracking:** Maps simple sequential IDs (001, 002, etc.) to actual `refnr` values
2. **LLM prompts:** Uses simple IDs to reduce confusion and improve success rates
3. **Response parsing:** Converts simple IDs back to `refnr` for database operations

This evolved from: simple → refnr-based (for HTML tracking) → hybrid (best of both)

### LLM Error Handling

**Challenge:** LLM responses are non-deterministic; unexpected formats break classification.

**Strategy:**
- **Strict validation:** Throw exception on any format mismatch
- **Fail fast:** Don't continue with unreliable data
- **Checkpoint recovery:** Resume from last successful batch
- **User options:**
  - Re-run with `--session` to resume
  - Try different model: `--model "google/gemini-2.5-pro"`
  - Reduce batch size to minimize impact of failures

**Common Issues:**
- Timeout/rate limits → Resume with `--session`
- Format errors → Try different model
- Repeated failures → Check prompts.yaml or reduce batch size

### Database vs Session Flow

**Normal Search:**
```
API → Database (scraped jobs) → Session (classifications)
```

**Incremental Search:**
```
API (last 7 days) → Merge with Database → Session (classify delta only)
```

**Re-classification:**
```
Database (all jobs) → Session (new classifications, new criteria)
```

---
