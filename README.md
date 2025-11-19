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

- **Personalized Matching** — Find jobs matching your skills and preferences
- **Incremental Updates** — Smart caching avoids redundant API calls
- **AI Classification** — Rate jobs as Excellent, Good, or Poor matches
- **Flexible Models** — Choose from cheap/fast to smart/expensive
- **Rich Exports** — JSON, CSV, and text reports with application links
- **Resume from Failures** — Automatic checkpoint recovery
- **Customizable** — Adjust matching criteria via custom prompts

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

# Search all available (no location filter - includes Germany, Austria...)
python main.py --was "Python Developer" --cv cv.md
```

**Note on `--wo` (location):**
- Omit to search **all available listings** (Germany, Austria, etc.)
- Limit to Germany: `--wo "Deutschland (Land)"`

Results save to `data/searches/YYYYMMDD_HHMMSS/`

**📖 See [docs/WORKFLOWS.md](docs/WORKFLOWS.md) for:**
- Daily incremental updates
- Re-classification with updated CV
- Recovery from failures
- Database management

---

## How It Works

1. **Search** — Query Arbeitsagentur API for jobs
2. **Scrape** — Fetch full descriptions with application URLs
3. **Classify** — AI rates jobs as Excellent, Good, or Poor match
4. **Export** — Save results as JSON, CSV, and text

**Matching Options:**
- `--cv` — Match based on your skills/experience
- `--perfect-job-description` — Match based on ideal role criteria
- Both (recommended) — Match what you CAN do AND WANT to do

---

## Configuration

### Smart Caching

First run fetches all jobs and creates a database. Subsequent runs fetch only recent jobs (last 7 days by default), processing only new/modified ones.

```bash
# First run - fetches all
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md

# Next run - only fetches recent (last 7 days)
python main.py --was "Python Developer" --wo "Berlin" --cv cv.md
# → "Database merge: 2 new, 1 updated, 185 unchanged" (processes only 3!)

# Custom timeframe (1-100 days)
python main.py --was "..." --cv cv.md --veroeffentlichtseit 1   # Last 24h
python main.py --was "..." --cv cv.md --veroeffentlichtseit 30  # Last month
```

**Force refresh:** `rm data/database/jobs.json` then run again.

### Custom Prompts

Adjust AI matching criteria:

```bash
cp prompts.example.yaml prompts.yaml
nano prompts.yaml  # Edit matching rules
```

Fine-tune strictness, emphasize criteria (remote work, company size), or add domain-specific rules.

### Models

**Default:** `google/gemini-2.5-flash` (fast, cheap)

```bash
--model "google/gemini-2.5-pro"        # Better quality, more expensive
--model "google/gemini-2.5-flash-lite" # Cheapest, fastest
```

**Typical costs** (100-200 jobs): < $0.03 with Flash, < $0.10 with Pro.

See [OpenRouter](https://openrouter.ai/) for pricing and models.

---

## Output

Each search creates a timestamped directory:

```
data/searches/YYYYMMDD_HHMMSS/
├── SUMMARY.txt            # Human-readable summary
├── jobs_classified.json   # Complete data with classifications
├── jobs_all.csv          # Successfully scraped jobs
├── jobs_failed.csv       # Failed scrapes with error types
└── debug/                # Logs and raw data
```

---

## Known Limitations

**Scraping:** Some sites require JavaScript or have bot protection (e.g., germantechjobs.de). Failed scrapes are logged in `jobs_failed.csv` with error types.

**LLM variability:** Classification may occasionally fail due to unexpected model responses. Use `--session` to resume, try a different model, or adjust batch size.

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
