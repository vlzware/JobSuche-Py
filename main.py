#!/usr/bin/env python3
"""
JobSuchePy - German Job Market Analysis Tool

Analyzes job listings from the German Arbeitsagentur to provide
insights into market trends and skill demands.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from src.config import config
from src.data import JobGatherer
from src.exceptions import (
    EmptyJobContentError,
    LLMDataIntegrityError,
    LLMResponseError,
    OpenRouterAPIError,
    WorkflowConfigurationError,
)
from src.llm import LLMProcessor
from src.logging_config import get_module_logger
from src.session import SearchSession
from src.workflows import MatchingWorkflow

logger = get_module_logger("main")


def _print_error_box(title: str, details: str, suggestions: str | None = None) -> None:
    """
    Print a formatted error box with title, details, and optional suggestions.

    Args:
        title: Error title/header
        details: Error details/description
        suggestions: Optional suggestions for resolving the error
    """
    logger.error("=" * 80)
    logger.error(title)
    logger.error("=" * 80)
    logger.error("")
    logger.error(details)
    logger.error("")
    if suggestions:
        logger.error(suggestions)
        logger.error("")
    logger.error("=" * 80)


def handle_classification_error(error: Exception) -> None:
    """
    Centralized error handling for classification exceptions.

    Args:
        error: The exception to handle

    Exits the program with status code 1 after displaying the error.
    """
    # Common suggestions for LLM-related errors
    llm_suggestions = (
        "WHAT YOU CAN TRY:\n"
        "  1. Run the command again - LLM responses have inherent randomness\n"
        "  2. Use a smaller batch size (--batch-size parameter)\n"
        "  3. Try a different model (--model parameter)"
    )

    if isinstance(error, LLMDataIntegrityError):
        details = (
            "The LLM returned data that failed validation checks.\n"
            "This prevents us from reliably matching classifications to jobs.\n"
            "\n"
            f"Details: {error!s}"
        )
        _print_error_box("LLM DATA INTEGRITY ERROR", details, llm_suggestions)

    elif isinstance(error, LLMResponseError):
        details = (
            "The LLM returned a response that could not be parsed.\n"
            "This typically means the model didn't follow the expected format.\n"
            "\n"
            f"Details: {error!s}"
        )
        _print_error_box("LLM RESPONSE PARSING ERROR", details, llm_suggestions)

    elif isinstance(error, OpenRouterAPIError):
        details = f"Status Code: {error.status_code}\nError: {error!s}"
        suggestions = error.get_user_guidance()
        _print_error_box("OPENROUTER API ERROR", details, suggestions)

    elif isinstance(error, WorkflowConfigurationError):
        details = f"Workflow: {error.workflow_type or 'unknown'}\nError: {error!s}"
        suggestions = (
            "Please check your configuration and try again.\n"
            "Refer to the documentation for proper workflow setup."
        )
        _print_error_box("WORKFLOW CONFIGURATION ERROR", details, suggestions)

    elif isinstance(error, EmptyJobContentError):
        details = (
            f"Job ID: {error.job_id or 'unknown'}\n"
            f"Error: {error!s}\n"
            "\n"
            "This job has no text content to classify.\n"
            "This typically indicates a problem with:\n"
            "  - Web scraping failed to extract content\n"
            "  - The job listing has no description\n"
            "  - Data extraction/processing issues"
        )
        _print_error_box("EMPTY JOB CONTENT ERROR", details)

    else:
        # Re-raise if it's not one of our known exception types
        raise error

    sys.exit(1)


def load_description_from_file_or_string(description_arg: str | None) -> str | None:
    """
    Load job description from file or return as-is if it's a direct string.

    Args:
        description_arg: Either a file path or direct description text

    Returns:
        Description content or None if not provided
    """
    if not description_arg:
        return None

    # Check if it's a file path
    description_path = Path(description_arg)
    if description_path.exists() and description_path.is_file():
        try:
            with open(description_path, encoding="utf-8") as f:
                content = f.read().strip()
                logger.info(f"Loaded perfect job description from file: {description_arg}")
                logger.info(f"Description length: {len(content)} characters")
                return content
        except Exception as e:
            logger.error(f"Could not read description file {description_arg}: {e}")
            sys.exit(1)

    # Not a file, use as-is (backward compatibility)
    return description_arg


def main():
    parser = argparse.ArgumentParser(
        description="Analyze job listings from the German Arbeitsagentur",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration:
  Defaults shown above come from config/*.yaml files:
    - config/search_config.yaml  → --umkreis, --size, --max-pages
    - config/llm_config.yaml     → --model
    - config/api_config.yaml     → --delay

  User preferences (prompts.yaml) can override CV matching prompts.
  Command-line arguments override everything.

Examples:
  # Match using CV only
  python main.py --was "Developer" --wo "Hamburg" --cv cv.md

  # Match using perfect job description only
  python main.py --was "Backend Dev" --wo "Berlin" \\
      --perfect-job-description perfect_job_description.txt

  # Match using BOTH CV and perfect job description (recommended!)
  python main.py --was "Python Developer" --wo "München" \\
      --cv cv.md --perfect-job-description perfect_job_description.txt

  # Extended search with custom parameters
  python main.py --was "Softwareentwickler" --wo "Berlin" \\
      --cv cv.md --umkreis 50 --max-pages 2 --size 100

  # Return ALL jobs including poor matches (default: only good & excellent)
  python main.py --was "Developer" --wo "Berlin" --cv cv.md --return-all

  # Re-classify existing jobs using session directory
  python main.py --classify-only --input data/searches/20231020_142830 --cv cv_updated.md

  # Or specify a JSON file directly
  python main.py --classify-only --input data/searches/20231020_142830/debug/02_scraped_jobs.json \\
      --cv cv.md --perfect-job-description perfect.txt

  # Re-classify ALL jobs from database with updated CV/criteria
  python main.py --from-database --cv cv_updated.md
  python main.py --from-database --cv cv.md --perfect-job-description new_dream.txt
        """,
    )

    # Get defaults from config
    default_umkreis = config.get("search.defaults.radius_km", 25)
    default_size = config.get("search.defaults.page_size", 100)
    default_max_pages = config.get("search.defaults.max_pages", 1)
    default_model = config.get("llm.models.default", "google/gemini-2.5-flash")
    default_delay = config.get("api.delays.scraping", 1.0)

    # Workflow is now always "matching" - parameter removed for simplicity

    # Search parameters
    parser.add_argument(
        "--was", type=str, required=False, help='Job title/description (e.g., "Softwareentwickler")'
    )
    parser.add_argument(
        "--wo",
        type=str,
        required=False,
        help='Location (e.g., "Berlin" or "München"). Optional - if omitted, searches all of Germany.',
    )
    parser.add_argument(
        "--umkreis",
        type=int,
        default=default_umkreis,
        help=f"Search radius in km (default: {default_umkreis})",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=default_size,
        help=f"Results per page, max 100 (default: {default_size})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=default_max_pages,
        help=f"Maximum number of pages to fetch (default: {default_max_pages})",
    )
    parser.add_argument(
        "--arbeitszeit",
        type=str,
        default="",
        help="Filter by work time: vz (fulltime), tz (parttime), ho (homeoffice), combine with ; (default: all)",
    )
    parser.add_argument(
        "--veroeffentlichtseit",
        type=int,
        default=None,
        help="Days since publication (0-100). If database exists, defaults to 7 for incremental updates. Use without value for full refresh.",
    )

    # Classification parameters
    parser.add_argument(
        "--model",
        type=str,
        default=default_model,
        help=f"OpenRouter model to use (default: {default_model})",
    )
    parser.add_argument(
        "--api-key", type=str, help="OpenRouter API key (or set OPENROUTER_API_KEY env var)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Use smaller batches instead of mega-batch (e.g., --batch-size 5). Default: mega-batch",
    )
    parser.add_argument(
        "--reasoning-effort",
        type=str,
        choices=["low", "medium", "high"],
        default=None,
        help="Reasoning effort for models that support it (e.g., Gemini Pro)",
    )

    # Matching workflow options
    parser.add_argument(
        "--cv",
        type=str,
        help="Path to your CV file for matching (optional, but at least one of --cv or --perfect-job-description required)",
    )
    parser.add_argument(
        "--perfect-job-description",
        type=str,
        help="Description of your perfect job - can be a file path (.txt/.md) or direct text (optional, but at least one of --cv or --perfect-job-description required)",
    )
    parser.add_argument(
        "--return-all",
        action="store_true",
        help="Return all jobs including poor matches (default: only return excellent and good matches)",
    )

    # Output options
    parser.add_argument(
        "--output", type=str, help="Additional JSON output path (auto-saved to session dir)"
    )
    parser.add_argument(
        "--report", type=str, help="Additional report output path (auto-saved to session dir)"
    )
    parser.add_argument(
        "--export", type=str, help="Additional CSV output path (auto-saved to session dir)"
    )

    # Processing options
    parser.add_argument(
        "--classify-only",
        action="store_true",
        help="Classify existing jobs from JSON file or session directory (use with --input)",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input JSON file or session directory (use with --classify-only). "
        "If directory: uses debug/02_scraped_jobs.json (raw scraped data).",
    )
    parser.add_argument(
        "--no-scraping",
        action="store_true",
        help="Skip scraping job details - only collect basic listing info (titles, employer, location) from Arbeitsagentur API",
    )
    parser.add_argument(
        "--no-classification", action="store_true", help="Skip LLM classification (only fetch jobs)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=default_delay,
        help=f"Delay between scraping requests in seconds (default: {default_delay})",
    )
    parser.add_argument(
        "--include-weiterbildung",
        action="store_true",
        help="Include Weiterbildung/Ausbildung jobs (excluded by default)",
    )
    parser.add_argument(
        "--from-database",
        action="store_true",
        help="Classify all jobs from database with new criteria (updated CV, categories, or model)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore checkpoint and start fresh classification (deletes partial progress)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    # Parse arguments with better error handling
    try:
        args = parser.parse_args()
    except SystemExit:
        # Check if user forgot --input with --classify-only
        if "--classify-only" in sys.argv:
            # Look for what might be a path argument without --input
            for arg in sys.argv[1:]:
                if not arg.startswith("--") and arg != sys.argv[0] and "/" in arg:
                    logger.error("")
                    logger.error(f"Did you forget '--input' before '{arg}'?")
                    logger.error(f"Correct usage: python main.py --classify-only --input {arg}")
                    logger.error("")
        raise

    # Validate classify-only mode
    if args.classify_only:
        if not args.input:
            logger.error("--classify-only requires --input <file.json or session_directory>")
            logger.error("Usage: python main.py --classify-only --input <path>")
            sys.exit(1)

        # Validate input path exists
        input_path = Path(args.input)
        if not input_path.exists():
            logger.error(f"Input path not found: {args.input}")
            sys.exit(1)

        if args.no_classification:
            logger.error("--classify-only and --no-classification are mutually exclusive")
            sys.exit(1)

    # Validate from-database mode
    if args.from_database:
        if args.input:
            logger.error("--from-database and --input are mutually exclusive")
            logger.error("--from-database loads ALL jobs from the database automatically")
            sys.exit(1)

        if args.classify_only:
            logger.error("--from-database and --classify-only are mutually exclusive")
            logger.error("Use --from-database alone (it implies classification)")
            sys.exit(1)

        if args.no_classification:
            logger.error("--from-database requires classification (can't use --no-classification)")
            sys.exit(1)

        if args.was or args.wo:
            logger.error("--from-database doesn't need --was or --wo")
            logger.error("It uses ALL jobs already in the database")
            sys.exit(1)

    if not args.classify_only and not args.from_database:
        # Normal mode requires search parameters
        if not args.was:
            logger.error("--was is required (unless using --classify-only or --from-database)")
            logger.error("Run 'python main.py --help' for usage information")
            sys.exit(1)

        # Warn if wo is not provided
        if not args.wo:
            logger.warning("")
            logger.warning("=" * 80)
            logger.warning("⚠️  NO LOCATION SPECIFIED - SEARCHING ALL OF GERMANY")
            logger.warning("=" * 80)
            logger.warning("")

    # Load perfect job description from file if it's a file path
    if args.perfect_job_description:
        args.perfect_job_description = load_description_from_file_or_string(
            args.perfect_job_description
        )

    # Validate matching workflow requirements
    # Matching workflow requires at least one of CV or perfect job description
    if not args.cv and not args.perfect_job_description:
        logger.error("Matching workflow requires at least one of:")
        logger.error("  --cv /path/to/cv.md")
        logger.error("  --perfect-job-description 'Description of ideal role...'")
        logger.error("Note: You can provide both for best results!")
        sys.exit(1)

    # Validate CV file exists if provided
    if args.cv:
        cv_path = Path(args.cv)
        if not cv_path.exists():
            logger.error(f"CV file not found: {args.cv}")
            sys.exit(1)

    # Validate API key if classification is enabled
    if not args.no_classification:
        api_key = args.api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.error("OpenRouter API key required for classification")
            logger.error("Either set OPENROUTER_API_KEY environment variable or use --api-key")
            logger.error("Get your key at: https://openrouter.ai/keys")
            logger.error("Use --no-classification to skip this step.")
            sys.exit(1)
    else:
        api_key = None

    verbose = not args.quiet

    # Create search session
    session = SearchSession(verbose=verbose)

    if session:
        logger.info(f"Session directory: {session.session_dir}")
        logger.info("All artifacts will be saved automatically")

    # Load CV content if provided
    cv_content = None
    if args.cv:
        cv_path = Path(args.cv)
        try:
            with open(cv_path, encoding="utf-8") as f:
                cv_content = f.read()
            logger.info(f"CV: {args.cv}")
            logger.info(f"CV length: {len(cv_content)} characters")
        except Exception as e:
            logger.error(f"Could not read CV file {args.cv}: {e}")
            sys.exit(1)

    # Display what's being used for matching
    if cv_content and args.perfect_job_description:
        logger.info("Matching workflow: Using BOTH CV and perfect job description (recommended!)")
    elif cv_content:
        logger.info("Matching workflow: Using CV only")
    elif args.perfect_job_description:
        logger.info("Matching workflow: Using perfect job description only")
        if args.perfect_job_description:
            logger.info(
                f"Perfect job description length: {len(args.perfect_job_description)} characters"
            )

    logger.info(f"Return only matches: {not args.return_all}")

    # FROM-DATABASE MODE: Load all jobs from database and classify with new criteria
    if args.from_database:
        from src.data.job_database import JobDatabase

        # Load database
        database = JobDatabase()
        if not database.exists():
            logger.error(f"Database not found at {database.database_path}")
            logger.error("Have you run a search yet? Database is created after first run.")
            logger.error("")
            logger.error("To create database, run a normal search first:")
            logger.error('  python main.py --was "Python Developer" --wo "Berlin"')
            sys.exit(1)

        logger.info(f"Loading database from {database.database_path}")
        database.load()

        total_jobs = len(database.jobs)
        logger.info(f"✓ Loaded {total_jobs} jobs from database")

        if total_jobs == 0:
            logger.warning("Database is empty - no jobs to classify")
            sys.exit(0)

        # Get all jobs (these have the full structure including 'details' dict)
        raw_jobs = database.get_all_jobs()

        # Extract and flatten job data (arbeitsort.ort -> ort, details.url -> url, etc.)
        # This also filters out failed scrapes (JS_REQUIRED, SHORT_CONTENT, etc.)
        from src.scraper import extract_descriptions

        jobs, failed_jobs = extract_descriptions(raw_jobs)

        logger.info(f"✓ Extracted {len(jobs)} valid job descriptions from database")
        if failed_jobs:
            logger.warning(
                f"✗ Skipping {len(failed_jobs)} jobs with incomplete/failed scraping data"
            )

        # Create LLM processor and workflow
        llm_processor = LLMProcessor(
            api_key=api_key, model=args.model, session=session, verbose=verbose
        )

        # Create and run matching workflow
        try:
            matching_workflow = MatchingWorkflow(
                llm_processor=llm_processor,
                session=session,
                verbose=verbose,
            )
            classified_jobs = matching_workflow.run_from_file(
                jobs=jobs,
                resume=not args.no_resume,
                cv_content=cv_content,
                perfect_job_description=args.perfect_job_description,
                return_only_matches=not args.return_all,
                batch_size=args.batch_size,
            )

        except (
            LLMDataIntegrityError,
            LLMResponseError,
            OpenRouterAPIError,
            WorkflowConfigurationError,
            EmptyJobContentError,
        ) as e:
            handle_classification_error(e)

        # Set total_jobs for statistics display
        total_jobs = len(raw_jobs)

    # CLASSIFY-ONLY MODE: Load jobs from JSON file or session directory
    elif args.classify_only:
        input_path = Path(args.input)

        # If it's a directory, resolve to raw scraped data
        if input_path.is_dir():
            scraped_jobs_path = input_path / "debug" / "02_scraped_jobs.json"
            if scraped_jobs_path.exists():
                input_file = scraped_jobs_path
                logger.info(f"Loading jobs from session: {input_path.name}")
            else:
                logger.error(f"Raw scraped data not found in session: {input_path}")
                logger.error(f"Expected: {scraped_jobs_path}")
                sys.exit(1)
        else:
            input_file = input_path
            logger.info(f"Loading jobs from file: {input_file}")

        with open(input_file, encoding="utf-8") as f:
            raw_jobs = json.load(f)

        total_jobs = len(raw_jobs)
        logger.info(f"✓ Loaded {total_jobs} raw jobs")

        # Extract and flatten job data (arbeitsort.ort -> ort, details.url -> url, etc.)
        # This also filters out failed scrapes (JS_REQUIRED, SHORT_CONTENT, etc.)
        from src.scraper import extract_descriptions

        jobs, failed_jobs = extract_descriptions(raw_jobs)

        logger.info(f"✓ Extracted {len(jobs)} valid job descriptions")
        if failed_jobs:
            logger.warning(
                f"✗ Skipping {len(failed_jobs)} jobs with incomplete/failed scraping data"
            )

        # Create LLM processor and workflow
        llm_processor = LLMProcessor(
            api_key=api_key, model=args.model, session=session, verbose=verbose
        )

        # Create and run matching workflow
        try:
            matching_workflow = MatchingWorkflow(
                llm_processor=llm_processor,
                session=session,
                verbose=verbose,
            )
            classified_jobs = matching_workflow.run_from_file(
                jobs=jobs,
                resume=not args.no_resume,
                cv_content=cv_content,
                perfect_job_description=args.perfect_job_description,
                return_only_matches=not args.return_all,
                batch_size=args.batch_size,
            )

        except (
            LLMDataIntegrityError,
            LLMResponseError,
            OpenRouterAPIError,
            WorkflowConfigurationError,
            EmptyJobContentError,
        ) as e:
            handle_classification_error(e)

        # failed_jobs already extracted from raw data above

    # NORMAL MODE: Search, scrape, classify
    else:
        # Skip classification if requested
        if args.no_classification:
            logger.warning("Classification disabled - will only gather job data")

            # Just gather data without classification
            gatherer = JobGatherer(session=session, verbose=verbose)
            jobs, failed_jobs, gathering_stats = gatherer.gather(
                was=args.was,
                wo=args.wo,
                umkreis=args.umkreis,
                size=args.size,
                max_pages=args.max_pages,
                arbeitszeit=args.arbeitszeit,
                include_weiterbildung=args.include_weiterbildung,
                enable_scraping=not args.no_scraping,
                scraping_delay=args.delay,
                veroeffentlichtseit=args.veroeffentlichtseit,
            )

            classified_jobs = jobs
            total_jobs = gathering_stats.get("total_found", len(jobs))

            if jobs:
                logger.info(f"✓ Gathered {len(jobs)} jobs (no classification)")

        else:
            # Full workflow with classification
            llm_processor = LLMProcessor(
                api_key=api_key, model=args.model, session=session, verbose=verbose
            )

            gatherer = JobGatherer(session=session, verbose=verbose)

            # Create and run workflow based on type

            try:
                matching_workflow = MatchingWorkflow(
                    llm_processor=llm_processor,
                    job_gatherer=gatherer,
                    session=session,
                    verbose=verbose,
                )
                classified_jobs, failed_jobs = matching_workflow.run(
                    was=args.was,
                    wo=args.wo,
                    umkreis=args.umkreis,
                    size=args.size,
                    max_pages=args.max_pages,
                    arbeitszeit=args.arbeitszeit,
                    enable_scraping=not args.no_scraping,
                    show_statistics=True,
                    cv_content=cv_content,
                    perfect_job_description=args.perfect_job_description,
                    return_only_matches=not args.return_all,
                    batch_size=args.batch_size,
                    veroeffentlichtseit=args.veroeffentlichtseit,
                    include_weiterbildung=args.include_weiterbildung,
                )
                completed_workflow = matching_workflow  # For later reference to gathering_stats

                # Get actual total from API (not just classified count)
                total_jobs = completed_workflow.gathering_stats.get(
                    "total_found", len(classified_jobs)
                )

            except (
                LLMDataIntegrityError,
                LLMResponseError,
                OpenRouterAPIError,
                WorkflowConfigurationError,
                EmptyJobContentError,
            ) as e:
                handle_classification_error(e)

    # Display statistics dashboard
    if classified_jobs and not args.no_classification:
        from src.analyzer import print_statistics_dashboard

        # Count errors (from gathering_stats)
        if "completed_workflow" in locals() and hasattr(completed_workflow, "gathering_stats"):
            error_count = completed_workflow.gathering_stats.get("failed", 0)
            successful_fetches = completed_workflow.gathering_stats.get(
                "successfully_extracted", len(classified_jobs)
            )
            total_jobs_for_dashboard = completed_workflow.gathering_stats.get(
                "total_found", len(classified_jobs)
            )

            # For filtered matching workflow (without --return-all):
            # All scraped jobs are classified, but only matches are returned
            # Filtered workflow: total_classified = all scraped jobs
            # No filtering: total_classified = returned count
            total_classified = successful_fetches if not args.return_all else len(classified_jobs)
        else:
            # classify-only mode or no workflow
            # In classify-only mode, we have access to failed_jobs from extract_descriptions() above
            error_count = len(failed_jobs)
            successful_fetches = len(jobs)  # Jobs with successful extraction
            total_jobs_for_dashboard = total_jobs  # All jobs from the raw file

            # In classify-only or from-database mode, check if filtering was requested
            if (args.classify_only or args.from_database) and not args.return_all:
                # All jobs in input file/database were classified
                total_classified = total_jobs  # total_jobs was set earlier
            else:
                total_classified = len(classified_jobs)

        # Show dashboard
        print_statistics_dashboard(
            classified_jobs=classified_jobs,
            total_jobs=total_jobs_for_dashboard,
            successful_fetches=successful_fetches,
            error_count=error_count,
            total_classified=total_classified,
        )

    # Save outputs
    if not classified_jobs:
        logger.warning("No jobs to save.")
        sys.exit(0)

    # Auto-save to session directory
    if session and not args.no_classification:
        # Save classified jobs
        json_path = session.save_classified_jobs(classified_jobs)
        logger.info(f"✓ Classified jobs saved to {json_path}")

        # Prepare data for summary
        search_params = {
            "was": args.was if not args.classify_only else None,
            "wo": args.wo if not args.classify_only else None,
            "umkreis": args.umkreis if not args.classify_only else None,
        }

        # Get gathering stats from workflow if available
        report_gathering_stats: dict[str, Any] | None = (
            getattr(completed_workflow, "gathering_stats", None)
            if "completed_workflow" in locals()
            else None
        )

        # Save CSV export
        csv_path = session.save_csv_export(classified_jobs)
        logger.info(f"✓ CSV export saved to {csv_path}")

        # Save failed jobs CSV (if any failures)
        if failed_jobs:
            failed_csv_path = session.save_failed_jobs_csv(failed_jobs)
            logger.warning(f"✗ Failed jobs saved to {failed_csv_path}")
            logger.warning(
                f"  {len(failed_jobs)} job(s) could not be scraped (see CSV for details)"
            )

        # Determine mode for summary
        if args.from_database:
            mode = f"From Database ({total_jobs} cached jobs)"
        elif args.classify_only:
            mode = "Classify Only"
        else:
            mode = "Search"

        # Build profile info
        profile_info = {}
        if cv_content:
            profile_info["cv_length"] = len(cv_content)
        if args.perfect_job_description:
            profile_info["perfect_job_length"] = len(args.perfect_job_description)

        # Save session summary
        summary_path = session.save_session_summary(
            classified_jobs=classified_jobs,
            total_jobs=total_jobs,
            mode=mode,
            model=args.model,
            profile_info=profile_info if profile_info else None,
            search_params=search_params,
            return_only_matches=not args.return_all,
            gathering_stats=report_gathering_stats,
        )
        logger.info(f"✓ Session summary saved to {summary_path}")

    # Additional custom output paths (if specified)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(classified_jobs, f, ensure_ascii=False, indent=2)
        logger.info(f"✓ Also saved to custom path: {args.output}")

    if args.report:
        from src.analyzer import generate_report

        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        search_params = {"was": args.was, "wo": args.wo, "umkreis": args.umkreis}
        report = generate_report(
            classified_jobs=classified_jobs, total_jobs=total_jobs, search_params=search_params
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"✓ Also saved to custom path: {args.report}")

    if args.export:
        export_path = Path(args.export)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        import csv

        with open(export_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Titel", "Ort", "Arbeitgeber", "Categories", "URL"])
            for job in classified_jobs:
                writer.writerow(
                    [
                        job.get("titel", ""),
                        job.get("ort", ""),
                        job.get("arbeitgeber", ""),
                        ", ".join(job.get("categories", [])),
                        job.get("url", ""),
                    ]
                )
        logger.info(f"✓ Also saved to custom path: {args.export}")

    logger.info("✓ Analysis complete!")
    if session:
        logger.info(f"All results saved in: {session.session_dir}")


if __name__ == "__main__":
    main()
