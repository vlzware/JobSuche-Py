# Typical Workflows

Common usage patterns for job searching, re-classification, and database management.

---

# Quick Reference

| Task              | Command                                 |
|-------------------|-----------------------------------------|
| Incremental check | Run same search                         |
| Resume failed run | Add `--session <timestamp>`             |
| Re-classify all   | Use `--from-database` with new criteria |
| Fresh start       | Delete database, run search             |

---

# Key Concepts

**Database** (`data/database/jobs.json`):
- Persistent cache of scraped jobs (no classifications)
- Used for incremental fetching - new/modified jobs are merged

**Session** (`data/searches/YYYYMMDD_HHMMSS/`):
- Contains classifications for one search run
- Includes checkpoints for recovery (i.e. if classification fails)

**Incremental Fetching:**
- Database exists → fetch only last 7 days
- Only process new/modified jobs
- 95% reduction in API calls

**Recovery:**
- Checkpoints saved after each batch
- Use `--session <timestamp>` to resume

---

## Scenario 1: First Run (Large Dataset)

**Initial run:**
```bash
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

Creates database, scrapes 500 jobs, classifies them. If classification fails mid-process, checkpoint is saved.

**Resume after failure:**
```bash
python main.py --from-database --cv cv.md --session 20231117_140000
```

Loads from checkpoint, continues where it left off. Database has scraped data; session has classifications.

---

## Scenario 2: Incremental Update

**Run same search over and over (for example, every couple of days):**
```bash
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

Fetches only last 7 days (default), merges into database. Example: finds 30 jobs, only 7 are new/modified → processes only those 7.

**If classification fails:**

```bash
python main.py --from-database --cv cv.md --session 20231118_100000
```

Resumes from checkpoint - i.e. where it failed last time.

---

## Scenario 3: Re-classify with New/Updated Criteria

**Re-classify ALL jobs in database:**
```bash
python main.py --from-database --cv cv_updated.md --perfect-job-description new_dream.txt
```

Loads all jobs from database, applies new criteria, creates new session with updated classifications. Database unchanged.

**Resume if interrupted or if the classification failed:**
```bash
python main.py --from-database --cv cv_updated.md --perfect-job-description new_dream.txt \
    --session 20231125_093000
```

---

## Scenario 4: Fresh Database

**When:** Jobs deleted, want to reset, or database corrupted.

```bash
rm data/database/jobs.json
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

Fetches all jobs, creates new database from scratch.

---
