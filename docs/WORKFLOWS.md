# Typical Workflows Guide

Complete guide for common usage patterns with incremental processing, classification recovery, and database management.

---

## Table of Contents

1. [Scenario 1: First Run (Large Dataset)](#scenario-1-first-run-large-dataset)
2. [Scenario 2: Next Day - Check for New Jobs](#scenario-2-next-day---check-for-new-jobs)
3. [Scenario 3: Week Later - Changed Criteria](#scenario-3-week-later---changed-criteria)
4. [Scenario 4: Refresh Database](#scenario-4-refresh-database)
5. [Key Principles](#key-principles)
6. [Common Patterns](#common-patterns)

---

## Scenario 1: First Run (Large Dataset)

### Initial Attempt

```bash
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

**What happens:**
```
✓ API: Found 500 jobs
✓ Database: Created data/database/jobs.json (all 500 jobs are NEW)
✓ Scraping: 500/500 jobs scraped (saves to database)
✓ Database: Saved (all jobs now have scraped details)
✓ Classification: Batch 1/8 (70 jobs) ✓
✓ Classification: Batch 2/8 (140 jobs) ✓
✓ Classification: Batch 3/8 (210 jobs) ✓
✗ Classification: Batch 4/8 FAILED (LLM timeout/error)
  → Checkpoint saved: 210 completed, 290 pending
  → Partial results saved: debug/partial_classified_jobs.json
```

### Recovery (Same Day)

```bash
# Just re-run classify-only on the SAME session
python main.py --classify-only --input data/searches/20231117_140000 --cv cv.md
```

**What happens:**
```
✓ Loads 500 jobs from session
✓ Found checkpoint: 210 completed, 290 pending
✓ Resuming from job 211...
✓ Classification: Batch 4/8 (280 jobs) ✓
... continues ...
✓ All 500 jobs classified!
✓ Checkpoint deleted (success)
✓ Results: data/searches/20231117_140000/classified_jobs.json
```

**Database state after success:**
- Has all 500 jobs with scraped details ✓
- Does NOT have classifications (those are in the session)

---

## Scenario 2: Next Day - Check for New Jobs

### Incremental Update

```bash
# Same search, next day
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

**What happens:**
```
✓ Database exists → Incremental mode (fetches last 7 days only)
✓ API: Found 30 jobs (last 7 days parameter)
✓ Database merge:
  - 5 new jobs (never seen before)
  - 2 updated jobs (modifikationsTimestamp changed)
  - 23 unchanged (already in database, not modified)
✓ Scraping: Only 7 jobs (5 new + 2 updated)
✓ Database: Updated, now has 505 total
✓ Classification: Only 7 jobs
✓ Success!
✓ Results: data/searches/20231118_100000/
```

**Database state:**
- Now has 505 jobs total (500 old + 5 new)
- All have scraped details

### If Classification Fails

```bash
# Classify-only on today's session
python main.py --classify-only --input data/searches/20231118_100000 --cv cv.md
```

**What happens:**
- Resumes from checkpoint
- Only processes the 7 jobs from this session
- Database unchanged (already has scraped data)

---

## Scenario 3: Week Later - Changed Criteria

### You Updated Your CV

```bash
# Use --from-database to re-classify ALL jobs with new CV
python main.py --from-database --cv cv_updated.md --perfect-job-description new_dream.txt
```

**What happens:**
```
✓ Loads ALL 505 jobs from database
✓ Filters: Removes failed scrapes
✓ Valid jobs: 492 (13 failed scrapes excluded)
✓ Classification: 492 jobs with NEW criteria
✓ New session: data/searches/20231125_093000/
```

**Database state:**
- Unchanged (still has original 505 jobs with old classifications)
- New session has updated classifications based on new CV

**Alternative - Re-classify Single Session:**
```bash
# Only re-classify specific session with new criteria
python main.py --classify-only --input data/searches/20231117_140000 \
    --cv cv_updated.md --perfect-job-description perfect.txt
```

---

## Scenario 4: Refresh Database

### When to Refresh

- Jobs were deleted/closed from Arbeitsagentur
- You want to reset and start fresh
- Database file is corrupted

### Force Full Refresh

```bash
# Delete database
rm data/database/jobs.json

# Run search - creates new database from scratch
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

**What happens:**
- Fetches ALL jobs (no incremental filter)
- Creates fresh database
- Full scraping and classification

---

## Key Principles

### 1. Database vs Session

**Database** (`data/database/jobs.json`):
- Persistent cache in current working directory
- Contains scraped job data (details, URLs)
- Does NOT contain classifications
- Used for incremental fetching

**Session** (`data/searches/YYYYMMDD_HHMMSS/`):
- Specific to one search run
- Contains classifications for that run
- Can be re-classified without re-scraping

### 2. Incremental Fetching

**How it works:**
- Database exists → Fetch only last 7 days (configurable)
- Compare `modifikationsTimestamp` to detect updates
- Only scrape/classify NEW or UPDATED jobs

**Benefits:**
- 95% reduction in API calls
- Faster runs (seconds instead of minutes)
- Lower LLM costs

### 3. Classification Recovery

**Checkpoints:**
- Saved after each mega-batch
- Automatic resume on re-run
- Clean up after success

**When to use `--classify-only`:**
- LLM error mid-classification
- Want to change criteria (CV, perfect job description, model)

**When to use `--from-database`:**
- Re-classify ALL jobs ever searched
- Updated CV/criteria and want comprehensive results
- One command for everything

### 4. Three Levels of Re-Classification

**Level 1: Resume Failed Classification (Same Session)**
```bash
python main.py --classify-only --input data/searches/20231117_140000 --cv cv.md
```
- Resumes from checkpoint
- Same criteria
- Completes interrupted classification

**Level 2: Re-Classify with New Criteria (Single Session)**
```bash
python main.py --classify-only --input data/searches/20231117_140000 \
    --cv cv_updated.md --perfect-job-description perfect.txt
```
- Re-classifies one session
- New criteria
- Useful for testing different matching strategies

**Level 3: Re-Classify Everything (Database)**
```bash
python main.py --from-database --cv cv_updated.md
```
- Re-classifies ALL jobs ever searched
- New criteria
- Most comprehensive, one command

---

## Common Patterns

### Daily Job Check
```bash
# Same search daily - only processes new/updated jobs
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

### Test Different Models
```bash
# Re-classify with different model
python main.py --classify-only --input data/searches/20231117_140000 \
    --cv cv.md --model "google/gemini-2.5-pro"
```

### Updated CV Strategy
```bash
# Re-classify everything with updated CV
python main.py --from-database --cv cv_updated.md --perfect-job-description new_dream.txt
```

---

## Summary

**For daily use:**
- Just run the same search → Only new/updated jobs processed

**If classification fails:**
- Re-run with `--classify-only --input <session>` → Resumes from checkpoint

**If criteria changed:**
- Single session: `--classify-only --input <session>` with new criteria
- All jobs: `--from-database` with new criteria

**Start fresh:**
- Delete database, run search → Full refresh

---
