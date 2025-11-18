# Typical Workflows Guide

Complete guide for common usage patterns with incremental processing, classification recovery, and database management.

---

## Table of Contents

1. [Scenario 1: First Run (Large Dataset)](#scenario-1-first-run-large-dataset)
2. [Scenario 2: Next Day - Check for New Jobs](#scenario-2-next-day---check-for-new-jobs)
3. [Scenario 3: Week Later - Changed Criteria](#scenario-3-week-later---changed-criteria)
4. [Scenario 4: Refresh Database (Deleted/Modified Jobs)](#scenario-4-refresh-database-deletedmodified-jobs)
5. [Complete Workflow Diagram](#complete-workflow-diagram)
6. [Key Principles](#key-principles)
7. [Common Patterns](#common-patterns)
8. [Summary Table](#summary-table)

---

## Scenario 1: First Run (Large Dataset)

### Initial Attempt

```bash
python main.py --was "Python Developer" --wo "Berlin"
```

**What happens:**
```
✓ API: Found 500 jobs
✓ Database: Created data/database/jobs_global.json (all 500 jobs are NEW)
✓ Scraping: 500/500 jobs scraped (saves 'details' to database)
✓ Database: Saved (all jobs now have scraped details)
✓ Classification: Batch 1/8 (70 jobs) ✓
✓ Classification: Batch 2/8 (140 jobs) ✓
✓ Classification: Batch 3/8 (210 jobs) ✓
✗ Classification: Batch 4/8 FAILED (LLM timeout/error)
  → Checkpoint saved: 210 completed, 290 pending
  → Partial results saved: data/searches/20231117_140000/debug/partial_classified_jobs.json
```

### Recovery (Same Day)

```bash
# Just re-run classify-only on the SAME session
python main.py --classify-only --input data/searches/20231117_140000
```

**What happens:**
```
✓ Loads 500 jobs from session
✓ Found checkpoint: 210 completed, 290 pending
✓ Resuming from job 211...
✓ Classification: Batch 4/8 (280 jobs) ✓
✓ Classification: Batch 5/8 (350 jobs) ✓
... continues ...
✓ All 500 jobs classified!
✓ Checkpoint deleted (success)
✓ Results: data/searches/20231117_140000/classified_jobs.json
```

**Database state after success:**
- Has all 500 jobs with scraped details ✓
- Does NOT have classifications (that's in the session)

---

## Scenario 2: Next Day - Check for New Jobs

### Incremental Update

```bash
# Same search, next day
python main.py --was "Python Developer" --wo "Berlin"
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
✓ Database: Updated with 7 jobs, now has 505 total
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
python main.py --classify-only --input data/searches/20231118_100000
```

**What happens:**
```
✓ Loads 7 jobs from today's session
✓ Classifies all 7
✓ Done!
```

---

## Scenario 3: Week Later - Changed Criteria

### Update CV and Re-classify Everything

```bash
# You now have 530 jobs in database (from multiple searches over the week)
# You updated your CV with new skills

python main.py --from-database --workflow matching \
    --cv cv_updated.md --perfect-job-description dream_job.txt
```

**What happens:**
```
✓ Loading database: data/database/jobs_global.json
✓ Loaded 530 jobs from database
✓ Extracted 518 valid job descriptions (12 failed scrapes skipped)
✓ Classification: Batch 1/8 (70 jobs) ✓
✓ Classification: Batch 2/8 (140 jobs) ✓
... continues ...
✓ All 518 jobs classified with NEW criteria!
✓ Results: data/searches/20231125_153000/
```

**Key points:**
- Database is READ-ONLY (not modified)
- All 518 jobs classified with updated CV
- New session created with results

### If This Fails (Large Re-classification)

```bash
# Classification failed at batch 5/8 (350 jobs done, 168 pending)
# Just re-run classify-only on that session

python main.py --classify-only --input data/searches/20231125_153000
```

**What happens:**
```
✓ Loads 518 jobs from session (from database export)
✓ Found checkpoint: 350 completed, 168 pending
✓ Resuming from job 351...
✓ Completes remaining 168 jobs
✓ Success!
```

---

## Scenario 4: Refresh Database (Deleted/Modified Jobs)

### Understanding Database Persistence

The database keeps ALL jobs you've ever found, including:
- **Active jobs** - Still on Arbeitsagentur
- **Historical jobs** - Filled/expired/deleted from Arbeitsagentur
- **Modified jobs** - Automatically detected and updated via `modifikationsTimestamp`

### When Jobs Are Modified

**Automatic detection:**
```bash
# Job was modified on Arbeitsagentur (description updated, requirements changed)
python main.py --was "Python Developer" --wo "Berlin"
```

**What happens:**
```
✓ Database exists → Incremental mode
✓ API: Found 30 jobs
✓ Database merge:
  - 0 new jobs
  - 3 updated jobs (modifikationsTimestamp changed) ← Automatically detected!
  - 27 unchanged
✓ Scraping: Only 3 updated jobs (re-scrape with new content)
✓ Database: Updated with new content for 3 jobs
✓ Classification: 3 jobs with updated content
```

**Result:** Modified jobs are automatically refreshed! No manual action needed.

### When Jobs Are Deleted/Filled

**Default behavior:** Database keeps historical jobs (useful for tracking what you've seen).

**If you want to clean up deleted jobs:**

#### Option 1: Full Refresh (Nuclear Option)
```bash
# Delete database and start fresh
rm data/database/jobs_global.json

# Re-run your searches
python main.py --was "Python Developer" --wo "Berlin"
python main.py --was "Backend Engineer" --wo "München"
# ... repeat all your searches ...
```

**Pros:**
- Fresh start, only current jobs
- Database reflects current Arbeitsagentur state

**Cons:**
- ❌ Expensive (re-fetches everything)
- ❌ Loses historical data
- ❌ Re-scrapes all jobs
- ❌ Must re-run all your search variations

#### Option 2: Keep Historical Data (Recommended)

**Don't delete the database!** Historical jobs are valuable:
- See which companies you've already applied to
- Track how job postings change over time
- Avoid re-applying to filled positions
- Compare old vs new job descriptions

**Why this is better:**
```bash
# Just keep running incremental updates
python main.py --was "Python Developer" --wo "Berlin"

# Database grows, but only fetches/scrapes/classifies NEW and UPDATED jobs
# Old/deleted jobs remain in database (marked with last_seen timestamp)
```

### Checking Job Status in Database

**Database metadata shows:**
```json
{
  "refnr": "12345-X",
  "titel": "Senior Python Developer",
  "metadata": {
    "first_seen": "2023-11-01T10:00:00",
    "last_seen": "2023-11-20T14:00:00"  ← Last time this job appeared in search
  }
}
```

**If `last_seen` is old** → Job likely deleted/filled on Arbeitsagentur

### When to Refresh

| Situation | Recommendation |
|-----------|---------------|
| **Jobs modified on Arbeitsagentur** | Automatic detection ✓ (no action needed) |
| **Jobs deleted/filled** | Keep in database (historical value) |
| **Database corrupted** | Delete and rebuild |
| **Want fresh start** | Delete database, re-run searches |
| **Testing/development** | Delete database for clean slate |

**Bottom line:** You rarely need to manually refresh. Modified jobs are handled automatically, and historical data is valuable.

---

## Complete Workflow Diagram

```
DAY 1: Initial Search
├─ Run: python main.py --was "Python" --wo "Berlin"
│  ├─ Fetch 500 jobs → Database created
│  ├─ Scrape 500 jobs → Database updated with details
│  └─ Classify 500 jobs → FAILS at 300
│
└─ Recovery: python main.py --classify-only --input data/searches/20231117_*
   └─ Resume from checkpoint → Complete 200 remaining jobs ✓

DAY 2: Check for Updates
├─ Run: python main.py --was "Python" --wo "Berlin"
│  ├─ Database exists → Incremental (last 7 days)
│  ├─ Fetch 30 jobs → Merge: 5 new, 2 updated, 23 unchanged
│  ├─ Scrape 7 jobs → Database now has 505 jobs
│  └─ Classify 7 jobs → Success ✓
│
└─ If fails: python main.py --classify-only --input data/searches/20231118_*
   └─ Classify 7 jobs ✓

DAY 3-7: More Searches
├─ Different searches: "Backend Dev", "Data Engineer", etc.
├─ Each adds to database (now 530 jobs total)
└─ Each creates its own session with classifications

DAY 8: Updated CV
├─ Run: python main.py --from-database --workflow matching --cv cv_updated.md
│  ├─ Load all 530 jobs from database
│  ├─ Classify all with NEW criteria → FAILS at 400
│  └─ Checkpoint saved
│
└─ Recovery: python main.py --classify-only --input data/searches/20231125_*
   └─ Resume from checkpoint → Complete remaining 130 jobs ✓

DAY 15: Database Refresh (Optional)
├─ Check database size: du -h data/database/jobs_global.json
│
├─ Option A: Keep historical data (recommended)
│  └─ Continue with incremental updates (no action needed)
│
└─ Option B: Fresh start
   ├─ Backup: cp data/database/jobs_global.json data/database/jobs_backup.json
   ├─ Delete: rm data/database/jobs_global.json
   └─ Rebuild: python main.py --was "Python" --wo "Berlin"
```

---

## Key Principles

### 1. Database = Cache for Arbeitsagentur Data

- **Purpose:** Avoid re-fetching and re-scraping
- **Incremental:** Only fetches recent jobs (last 7 days default)
- **Persistent:** Keeps growing with each search
- **Smart updates:** Automatically detects modified jobs

### 2. Sessions = Classification Results

- **Purpose:** Store classification results with specific criteria
- **Temporary:** Each run creates new session
- **Recoverable:** Checkpoint allows resuming failed classifications

### 3. Recovery Pattern

**ANY failed classification:**
```bash
python main.py --classify-only --input <failed_session_directory>
```

- Works for initial runs
- Works for incremental runs
- Works for database re-classifications
- Always resumes from checkpoint automatically

---

## Common Patterns

### Daily Job Hunting Routine

```bash
# Morning: Check for new jobs
python main.py --was "Python Dev" --wo "Berlin"

# New jobs classified, results in today's session
# Database grows incrementally
```

### Weekly CV Update

```bash
# Updated CV on Sunday
# Re-classify EVERYTHING in database with new criteria
python main.py --from-database --workflow matching --cv cv_updated.md

# All historical jobs re-evaluated with updated CV
```

### Try Different Search Terms

```bash
# Monday: "Python Developer"
python main.py --was "Python Developer" --wo "Berlin"

# Tuesday: "Backend Engineer"
python main.py --was "Backend Engineer" --wo "Berlin"

# Wednesday: "Software Engineer"
python main.py --was "Software Engineer" --wo "Berlin"

# Database now has jobs from all 3 searches (deduplicated by refnr)
# Each search has its own session with classifications
```

### Monthly Model Experiment

```bash
# Try expensive but higher-quality model on ALL data
python main.py --from-database --workflow matching \
    --cv cv.md --model "google/gemini-2.5-pro"

# See if better model finds better matches
```

### Check Database Statistics

```bash
# View database metadata
jq '.metadata' data/database/jobs_global.json

# Output:
# {
#   "created": "2023-11-01T10:00:00",
#   "last_updated": "2023-11-25T15:30:00",
#   "total_jobs": 530,
#   "active_jobs": 530
# }

# Count jobs by last_seen date (find stale jobs)
jq '.jobs | to_entries |
    map({refnr: .key, last_seen: .value.metadata.last_seen}) |
    sort_by(.last_seen)' data/database/jobs_global.json
```

---

## Summary Table

| Scenario | Command | What Happens | If Fails |
|----------|---------|--------------|----------|
| **First run** | `--was "Python" --wo "Berlin"` | Fetch → Scrape → Classify | `--classify-only --input <session>` |
| **Daily update** | Same search command | Incremental fetch (7 days) → Classify new/updated | `--classify-only --input <session>` |
| **Updated CV** | `--from-database --cv cv_new.md` | Load all → Classify all with new CV | `--classify-only --input <session>` |
| **New search terms** | `--was "Backend" --wo "Munich"` | Fetch → Merge with database → Classify | `--classify-only --input <session>` |
| **Try different model** | `--from-database --model gemini-2.5-pro` | Load all → Classify with new model | `--classify-only --input <session>` |
| **Modified jobs** | Same search (automatic) | Detects changes → Re-scrape → Re-classify | `--classify-only --input <session>` |
| **Database refresh** | `rm data/database/jobs_global.json` then re-run searches | Fresh database | N/A (clean start) |

**Recovery is ALWAYS the same:** `--classify-only --input <session_that_failed>`

---

## Performance Tips

### Incremental Updates are Fast

```bash
# First run: 500 jobs × 1.5s = ~12 minutes
python main.py --was "Python" --wo "Berlin"

# Daily update: 5 new jobs × 1.5s = ~8 seconds  ← 99% faster!
python main.py --was "Python" --wo "Berlin"
```

### Adjust Incremental Window

```bash
# Default: Last 7 days (config/search_config.yaml)
# For more frequent updates, reduce window:
python main.py --was "Python" --wo "Berlin" --veroeffentlichtseit 3

# For less frequent updates (weekly), increase window:
python main.py --was "Python" --wo "Berlin" --veroeffentlichtseit 14
```

### Database Size Management

**Typical sizes:**
- 100 jobs: ~500 KB
- 1000 jobs: ~5 MB
- 10000 jobs: ~50 MB

**If database gets large:**
- Consider periodically archiving old sessions
- Delete database and rebuild (fresh start)
- Keep database (historical data is valuable!)

---

## Troubleshooting

### "Database not found" Error

```bash
# When using --from-database before first search
python main.py --from-database --cv cv.md

# Error: Database not found at data/database/jobs_global.json
# Solution: Run a normal search first to create database
python main.py --was "Python" --wo "Berlin"
```

### Checkpoint Won't Resume

```bash
# Delete checkpoint and start fresh
rm data/searches/20231117_140000/debug/classification_checkpoint.json

# Or use --no-resume flag
python main.py --classify-only --input data/searches/20231117_140000 --no-resume
```

### Database Corruption

```bash
# Backup and rebuild
mv data/database/jobs_global.json data/database/jobs_backup.json
python main.py --was "Python" --wo "Berlin"

# If backup was good, restore
mv data/database/jobs_backup.json data/database/jobs_global.json
```

---

**Key Insight:** Database and sessions work together but have separate concerns:
- **Database** caches raw data from Arbeitsagentur
- **Sessions** store classification results with specific criteria
- **Recovery** is always the same pattern: `--classify-only --input <session>`
