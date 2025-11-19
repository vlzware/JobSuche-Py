# JobSuchePy

**AI-Powered Job Matching for the German "Arbeitsagentur"**

Find personalized job matches based on your CV and ideal job criteria — powered by AI.

| Titel                    | Ort    | Arbeitgeber      | Match           | URL         |
|--------------------------|--------|------------------|-----------------|-------------|
| Senior Backend Developer | Berlin | TechFlow GmbH    | Excellent Match | https://... |
| Python Engineer          | Berlin | DataSync AG      | Excellent Match | https://... |
| Full-Stack Developer     | Berlin | CloudOps GmbH    | Good Match      | https://... |
| DevOps Engineer          | Berlin | AutoTech Systems | Good Match      | https://... |
| ...                      | ...    | ...              | ...             | ...         |

_example output with matching workflow (fictional data)_

## Features

- **Personalized Matching** — Find jobs that match YOUR skills and preferences
- **Incremental fetching** — Automatic database caching to avoid redundant API calls
- **AI Classification** — Automatically rate jobs as Excellent, Good, or Poor matches
- **Batch processing** — Configurable batch size and mega-batch mode
- **Cheap/free or smart/more expensive** — By choosing the right model
- **Rich Exports** — JSON, CSV, and text reports with direct application links
- **Configurable** — Customize matching criteria via custom prompts
- **Resume from failures** — Automatic checkpoint recovery

Focus on what matters: finding jobs that match YOU.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/vlzware/jobsuche-py.git
cd jobsuche-py

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

**Note:** The virtual environment isolates this project's dependencies from other Python projects. You need to activate it (`source .venv/bin/activate`) in each new terminal session before running the project. When active, your prompt will show `(.venv)`.

### 2. Get API Key

Sign up at [OpenRouter](https://openrouter.ai/) and get your API key:

```bash
export OPENROUTER_API_KEY='your-key-here'
```

(or use the available script to export into the current session: ```source setup_key.sh```)

### 3. Create Your CV (Optional)

Create a simple markdown file `cv.md` with your experience, skills, and background.

### 4. Run

```bash
# Activate venv (if not already active - check for (.venv) in prompt)
source .venv/bin/activate

# Search using CV only
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md

# Or use a perfect job description
python main.py --was "Backend Developer" --wo "München" \\
    --perfect-job-description "I want a senior backend role with Python and PostgreSQL"

# Or use BOTH (recommended!)
python main.py --was "Software Developer" --wo "Hamburg" \\
    --cv cv.md --perfect-job-description perfect_job.txt
```

That's it! Results are automatically saved to `data/searches/YYYYMMDD_HHMMSS/`

**📖 See [docs/WORKFLOWS.md](docs/WORKFLOWS.md) for complete workflow examples:**
- First run with large datasets (with recovery patterns)
- Daily incremental updates
- Re-classifying with updated CV/criteria
- Database management and refresh scenarios

---

## How It Works

JobSuchePy uses AI to match jobs against your profile:

1. **Search** — Query Arbeitsagentur API for jobs
2. **Scrape** — Fetch full job descriptions (with application URLs)
3. **Match** — AI rates each job based on your CV and/or ideal job description
4. **Filter** — Return only Excellent and Good matches (configurable)
5. **Export** — Save as JSON, CSV, or text

### Matching Criteria

Jobs are classified into three categories:

- **Excellent Match**: Strong alignment with your profile — start immediately with minimal ramp-up
- **Good Match**: Realistic fit with some adaptation needed
- **Poor Match**: Significant misalignment (filtered out by default)

You can provide:
- **CV only** — Match based on your skills and experience
- **Perfect job description only** — Match based on your ideal role
- **Both (recommended!)** — Match based on what you CAN do AND what you WANT to do

---

## Configuration

### Incremental Fetching

JobSuchePy automatically caches jobs in a persistent database (`data/database/jobs.json`) to avoid redundant API calls, scraping, and classification.

**How it works:**
- **First run:** Fetches all jobs, creates database
- **Subsequent runs:** Fetches only jobs published in last 7 days (default), skips unchanged jobs
- **Smart merging:** Detects new jobs, modified jobs (by `modifikationsTimestamp`), and unchanged jobs
- **Only processes delta:** Scrapes and classifies only new/updated jobs

**Usage:**
```bash
# First run - creates database with all jobs
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md

# Next run - fetches only recent jobs (last 7 days)
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
# Output: "Database merge: 2 new, 1 updated, 185 unchanged"
# Only processes 3 jobs instead of 188!

# Custom time window (1-100 days)
python main.py --was "..." --wo "..." --cv cv.md --veroeffentlichtseit 1  # Last 24h
python main.py --was "..." --wo "..." --cv cv.md --veroeffentlichtseit 30 # Last month

# Force full refresh - delete database and run again
rm data/database/jobs.json
python main.py --was "..." --wo "..." --cv cv.md
```

**Configuration:** Edit `config/search_config.yaml`:
```yaml
defaults:
  veroeffentlichtseit: 7  # Days for incremental updates (default: 7)
```

### Custom Prompts

**Customize AI matching criteria:**

```bash
# Copy the example template
cp prompts.example.yaml prompts.yaml

# Edit with your custom matching criteria
nano prompts.yaml
```

**Example `prompts.yaml`:**
```yaml
prompts:
  cv_matching: |
    Your custom prompt for CV-based job matching.
    Adjust criteria to be more/less strict.
    {cv_content} will be replaced with your CV.
```

This allows you to:
- Adjust matching strictness (more/fewer matches)
- Emphasize specific criteria (e.g., remote work, company size)
- Add domain-specific evaluation rules
- Fine-tune for your job search strategy

### Models

**Default:** `google/gemini-2.5-flash` (fast and cheap)

**Other options:**
```bash
--model "google/gemini-2.5-pro"        # Better quality, more expensive
--model "google/gemini-2.5-flash-lite" # Cheapest, quickest
```

**Example Pricing** (per million tokens - input/output):
- **Gemini Flash Lite:** \$0.10 / \$0.40 (cheapest)
- **Gemini Flash:** \$0.30 / \$2.50 (default - good balance)
- **Gemini Pro:** \$1.25 / \$10.00 (better quality)

For my typical job searches (100-200 jobs), costs were usually < \$0.03 with Flash or < \$0.10 with Pro.

Check [OpenRouter](https://openrouter.ai/) for current pricing, models, and options.

**Reasoning and Reasoning Effort:** Use `--reasoning-effort high` with compatible models (Gemini Pro, Claude) for better accuracy at higher cost. When using a reasoning model, the thinking process is saved to `debug/*_thinking.md`.

---

## Output

Each search creates a timestamped directory with:

```
data/searches/YYYYMMDD_HHMMSS/
├── SUMMARY.txt               # Human-readable session summary
├── jobs_classified.json      # Complete data with match classifications
├── jobs_all.csv              # Successfully parsed jobs (spreadsheet)
├── jobs_failed.csv           # Jobs that couldn't be scraped (title, employer, URL, error type)
└── debug/                    # Raw data for troubleshooting
    ├── session.log           # Complete execution log
    ├── *_thinking.md         # LLM reasoning process (if available)
    └── ...
```

---

## Re-Classification

Re-classify existing data without re-fetching or re-scraping from Arbeitsagentur.

### Common Scenarios

**1. Classification Failed (LLM Error)**
```bash
# Resume from checkpoint automatically
python main.py --classify-only --input data/searches/20231117_140000 --cv cv.md
```

**2. Changed Classification Criteria (Single Session)**
```bash
# Updated CV or perfect job description - re-classify specific session(s)
python main.py --classify-only --input data/searches/20231117_140000 \\
    --cv cv_updated.md --perfect-job-description new_dream.txt

# Try different model
python main.py --classify-only --input data/searches/20231117_140000 \\
    --cv cv.md --model "google/gemini-2.5-pro"

# Multiple sessions at once
python main.py --classify-only --input data/searches/20231117_* \\
    --cv cv_updated.md
```

**3. Re-Classify ENTIRE Database (All Jobs)**
```bash
# Re-classify ALL jobs in database with new criteria (one command!)
python main.py --from-database --cv cv_updated.md --perfect-job-description new_dream.txt

# Try different model
python main.py --from-database --cv cv.md --model "google/gemini-2.5-pro"
```

**Why?** Database contains ALL jobs you've ever searched (potentially 1000s across multiple searches). `--from-database` loads them all for re-classification with updated CV/criteria/model without re-fetching from Arbeitsagentur.

**4. Fresh Start (Delete Cache)**
```bash
# Force re-fetch everything from Arbeitsagentur
rm data/database/jobs.json
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
```

**Technical Details:**
- Uses `debug/02_scraped_jobs.json` (raw scraped data without classifications)
- Automatically resumes from checkpoint if classification was interrupted
- Use `--no-resume` to discard checkpoint and start fresh

### Merging Multiple Sessions

You can merge and re-classify multiple search sessions together (e.g., different job titles, same skills):

```bash
# Merge multiple sessions and classify together
python main.py --classify-only \\
    --input data/searches/20231020_142830 \\
           data/searches/20231020_153045 \\
           data/searches/20231020_164512 \\
    --cv cv.md --perfect-job-description perfect_job.txt
```

The tool automatically deduplicates jobs by their reference number (refnr) before classification, ensuring each job is only processed once even if it appears in multiple search results.

### Auto-Resume After Errors

Classification automatically saves checkpoints after each mega-batch. If classification fails mid-process (LLM failure, API errors, network issues, etc.), simply re-run `--classify-only` with the same session to resume from where it left off:

```bash
# First run - fails at job 150/300
python main.py --classify-only --input data/searches/20231020_142830 --cv cv.md

# Re-run - automatically resumes from job 150
python main.py --classify-only --input data/searches/20231020_142830 --cv cv.md
```

**Fresh restart:** Use `--no-resume` to discard checkpoint and restart classification.

Checkpoint files (`debug/classification_checkpoint.json`, `debug/partial_classified_jobs.json`) are automatically cleaned up after successful completion.

---

## Known Limitations

- External scraping success rate varies by site (some sites require JavaScript/SPA)
  - Failed scrapes are tracked in `jobs_failed.csv` with error types
  - Common issues: JS_REQUIRED (Single Page Applications), SHORT_CONTENT, TIMEOUT

From my personal testing with tech-related criteria, the biggest culprit is germantechjobs.de, which is an SPA and has some bot protection. From a recent search, I got 112 jobs scraped from a total of 149. Almost all (31) of the failed jobs (37) were from this site. In another search with different criteria, I got only 21 errors from a total of 511 jobs scraped, so your mileage may vary.

---

## Errors with LLM-Classifications

If there is even the slightest misalignment between our request and the data returned from the LLM, an exception is thrown and the current task gets interrupted because we can't rely on this data anymore. Because of the inherent variability of LLMs you may need to rerun the search in such cases until you get a proper result. Alternatively, you can try a smaller batch size or a different model.

---

## Note on the use of AI

This project is developed with assistance from [Claude Code](https://claude.ai/code). While I aim to review and control every change it makes, some slips, inaccuracies, or even bad code are still possible. Still, given the productivity gains in relation to the goal and context of this project, I consider this a good tradeoff.

---

## License

GPL-3.0 - See [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Data: [Bundesagentur für Arbeit](https://www.arbeitsagentur.de/)
- API: [bundesAPI](https://github.com/bundesAPI/jobsuche-api)
- AI Models: [OpenRouter](https://openrouter.ai/)

---
