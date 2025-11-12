# JobSuchePy

**AI-powered Job Market Analysis for the German "Arbeitsagentur"**

Analyze job listings, classify them by skills, track market trends, find personalized good matches — with AI processing.

| Titel                    | Ort    | Arbeitgeber      | Match           | URL         |
|--------------------------|--------|------------------|-----------------|-------------|
| Senior Backend Developer | Berlin | TechFlow GmbH    | Excellent Match | https://... |
| Python Engineer          | Berlin | DataSync AG      | Excellent Match | https://... |
| Full-Stack Developer     | Berlin | CloudOps GmbH    | Good Match      | https://... |
| DevOps Engineer          | Berlin | AutoTech Systems | Good Match      | https://... |
| ...                      | ...    | ...              | ...             | ...         |

_example output with matching workflow (fictional data)_

## Features

- **Gather data** — Query Arbeitsagentur API with flexible parameters
- **AI Classification** — Automatically categorize jobs by skills/technologies or rate them by "good match for me"
- **Batch processing** — Configurable batch size and mega-batch mode
- **Cheap/free or smart/more expensive** — By choosing the right model
- **Rich Exports** — JSON, CSV, and text reports with direct application links
- **Configurable** — Customize categories for your domain
- **Multiple Workflows** — Market analysis, personalized job matching, career brainstorming...

Usable for jobseekers, or just for fun and education.

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

### 3. Run

```bash
# Activate venv (if not already active - check for (.venv) in prompt)
source .venv/bin/activate

# Run the tool
python main.py --was "Softwareentwickler" --wo "Berlin"
```

That's it! Results are automatically saved to `data/searches/YYYYMMDD_HHMMSS/`

---

## Workflows

JobSuchePy supports three workflows via the unified `main.py` entry point:

### 1. Matching Workflow
Personalized job matching based on your profile (CV and/or ideal job description).

**Three ways to match:**

**A) CV only** — Match based on your experience and skills
```bash
python main.py --workflow matching \
    --was "Software Developer" --wo "Hamburg" \
    --cv cv.md
```

**B) Perfect job description only** — Match based on your ideal role
```bash
python main.py --workflow matching \
    --was "Backend Developer" --wo "Berlin" \
    --perfect-job-description perfect_job_description.txt
```

**C) Both (recommended!)** — Match based on both your capabilities AND preferences
```bash
python main.py --workflow matching \
    --was "Python Developer" --wo "München" \
    --cv cv.md \
    --perfect-job-description perfect_job_description.txt
```

**Use case:** Personalized job search — find positions that match both what you CAN do and what you WANT to do

The LLM classifies each job as:
- **Excellent Match**: Strong alignment with your profile
- **Good Match**: Reasonable fit with some gaps
- **Poor Match**: Significant misalignment

By default, only Excellent and Good matches are returned. Use `--return-all` to see all jobs with their classifications.

**Note:** Markdown format works best for CVs — LLMs parse it more accurately.

**Re-classification:**
```bash
# Re-classify existing data with matching criteria
python main.py --classify-only --workflow matching \
    --input data/searches/20231020_142830 \
    --cv cv.md --perfect-job-description perfect_job_description.txt
```

---

### 2. Multi-Category Analysis
Standard market analysis — classify jobs into multiple categories. This workflow is used when no specific workflow parameters are set.

```bash
# Basic usage (multi-category is used when no workflow is specified)
python main.py --was "Softwareentwickler" --wo "Berlin"

# Explicit workflow specification
python main.py --workflow multi-category --was "Python Developer" --wo "München"

# Re-classify existing data with different categories (using session directory)
python main.py --classify-only --input data/searches/20231020_142830 \
    --categories "Backend" "Frontend" "DevOps" "Data Science"
```

**Use case:** Market research and skill demand analysis

Example: "What technologies are most in-demand? How many DevOps vs Backend roles exist in my area?"

---

### 3. Brainstorming
Discover relevant job titles ("Berufsbezeichnungen") based on your profile.

```bash
# Brainstorm using your CV
python main.py --workflow brainstorm --cv cv.md

# Brainstorm with CV and motivation description
python main.py --workflow brainstorm \
    --cv cv.md \
    --motivation-description motivation.txt

# Brainstorm with motivation only (no CV required)
python main.py --workflow brainstorm \
    --motivation-description "I'm passionate about cloud architecture and DevOps..."
```

**Use case:** Job search discovery - find what job titles to search for

The LLM analyzes your background (CV) and/or career motivations to suggest:
- Relevant German job titles ("Berufsbezeichnungen") to use in your searches
- Direct examples of how to use them with the tool
- Career direction insights based on your profile

**Note:** This workflow does NOT search for actual jobs. It helps you discover which job titles to search for in other workflows. Results are saved to `brainstorm_suggestions.md` in your session directory.

---

## CLI Reference

```bash
python main.py --help
```

---

## Output

Each search creates a timestamped directory with:

```
data/searches/YYYYMMDD_HHMMSS/
├── jobs_classified.json      # Complete data with classifications
├── jobs_all.csv              # Successfully parsed jobs (spreadsheet)
├── jobs_failed.csv           # Jobs that couldn't be scraped (title, employer, URL, error type)
├── analysis_report.txt       # Statistics and insights
├── session_info_*.json       # Session metadata (workflow, counts, parameters)
└── debug/                    # Raw data for troubleshooting
    ├── *_thinking.md         # LLM reasoning process (if available)
    └── ...
```

---

## Configuration

### Configuration Priority

Settings are applied in this order (later overrides earlier):

1. **Base defaults** - `config/*.yaml` files provide system defaults
2. **User preferences** - `categories.yaml` and `prompts.yaml` customize behavior
3. **Command-line arguments** - Override all settings for specific runs

**Example:** `config/search_config.yaml` sets `max_pages: 5`, but `--max-pages 2` overrides it for that execution.

### Categories

JobSuchePy classifies jobs into categories. Three configuration options:

**1. Config file** (recommended):
```bash
cp categories.example.yaml categories.yaml
# Edit with your categories
```

**2. Command line** (overrides config):
```bash
python main.py --was "DevOps" --wo "München" \
    --categories "Kubernetes" "Docker" "AWS" "Other"
```

**3. Defaults** (if not specified):
- Projektleitung, Agile Projektentwicklung, Java, Python, TypeScript, C#/.NET, Andere

See `categories.example.yaml` for format. Optional `description` field helps AI classify more accurately.

### Custom Prompts

**Customize AI matching criteria** for CV-based workflow:

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

### Local Configuration

**Personal files (not part of git):**
- `categories.yaml` - Your custom categories
- `data/` - Search results
- `cv.*` - Your CV files
- `my_*.sh`, `my_*.py` - Personal scripts
- `.env` - API keys

### Models

**Default:** `google/gemini-2.5-flash` (not the most accurate, but fast and cheap)

**Other options:**
```bash
--model "google/gemini-2.5-pro"        # my personal sweet spot for jobs, a bit more expensive though
--model "google/gemini-2.5-flash-lite" # cheapest, quickest
```

**Example Pricing** (per million tokens - input/output):
- **Gemini Flash Lite:** \$0.10 / \$0.40 (cheapest)
- **Gemini Flash:** \$0.30 / \$2.50 (default - good balance)
- **Gemini Pro:** \$1.25 / \$10.00 (better quality)

For my typical job searches (100-200 jobs), the costs were usually < \$0.03 with Flash or < \$0.10 with Pro.

**Note**: There are a _multitude_ of models available, so you can try different ones to find the best fit for your needs.

**Example: Using Gemini Flash Lite:**
```bash
# Basic search with the cheapest model
python main.py --was "Softwareentwickler" --wo "Berlin" \
    --model "google/gemini-2.5-flash-lite"
```

Check [OpenRouter](https://openrouter.ai/) for current pricing, models, ratings and options.

---

## How It Works

1. **Search** — Query Arbeitsagentur API
2. **Scrape** — Fetch full job descriptions (with application URLs)
3. **Classify** — AI categorizes/rates jobs (models from OpenRouter)
4. **Analyze** — Generate statistics and reports
5. **Export** — Save as JSON, CSV, or text

**Fast and Cheap or Slower, Accurate and Expensive:**
- Mega-batch processing: Process per default ~70 jobs per API call for cost-effectiveness. Larger searches are automatically split into multiple mega-batches.
- Model selection: Try different models to find the best fit for your needs.

---

## Re-Classification

When using `--classify-only` with a session directory, the tool uses `debug/02_scraped_jobs.json` (raw scraped data without existing classifications). This ensures clean re-classification with different models or categories. If this file doesn't exist (e.g., old session), you'll need to re-run the original search with scraping enabled.

The idea of re-classification is to try different models or categories on the same data — no point of re-scraping.

**Convenience wrappers** are available for re-classification:
- `./reclassify.sh [session_dir]` - Multi-category (defaults to latest session)
- `./reclassify_matching.sh [options] [session_dir]` - Matching workflow
  - `--cv cv.md` - CV only
  - `--perfect-job-description desc.txt` - Perfect job only
  - `--cv cv.md --perfect-job-description desc.txt` - Both (recommended!)

### Merging Multiple Sessions

You can merge and re-classify multiple search sessions together (e.g., different job titles, same skills):

```bash
# Merge multiple sessions and classify together
python main.py --classify-only --workflow matching \
    --input data/searches/20231020_142830 \
           data/searches/20231020_153045 \
           data/searches/20231020_164512 \
    --cv cv.md --perfect-job-description perfect_job.txt
```

The tool automatically deduplicates jobs by their reference number (refnr) before classification, ensuring each job is only processed once even if it appears in multiple search results.

---

## Known Limitations

- External scraping success rate varies by site (some sites require JavaScript/SPA)
  - Failed scrapes are tracked in `jobs_failed.csv` with error types
  - Common issues: JS_REQUIRED (Single Page Applications), SHORT_CONTENT, TIMEOUT

Currently, in the searches I made, the biggest culprit is germantechjobs.de, which is an SPA and even has some bot protection. From a recent search, I got 112 jobs scraped, from a total of 149. Almost all (31) of the failed jobs (37) were from this site.

---

## Errors with LLM-classifications

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
