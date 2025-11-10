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
from src.preferences import UserProfile
from src.session import SearchSession
from src.workflows import (
    BrainstormWorkflow,
    CVBasedWorkflow,
    MultiCategoryWorkflow,
    PerfectJobWorkflow,
)

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

  User preferences (categories.yaml, prompts.yaml) override config defaults.
  Command-line arguments override everything.

Examples:
  # Basic search
  python main.py --was "Softwareentwickler" --wo "Berlin"

  # Extended search with custom parameters
  python main.py --was "Softwareentwickler" --wo "Berlin" \\
      --umkreis 50 --max-pages 2 --size 100

  # Use custom categories
  python main.py --was "DevOps" --wo "München" \\
      --categories "Docker" "Kubernetes" "CI/CD" "Cloud" "Andere"

  # Re-classify existing jobs using session directory
  python main.py --classify-only --input data/searches/20231020_142830

  # Or specify a JSON file directly
  python main.py --classify-only --input data/searches/20231020_142830/debug/02_scraped_jobs.json

  # Different workflows
  python main.py --workflow perfect-job --was "Backend Dev" --wo "Berlin" \\
      --perfect-job-category "Dream Job" \\
      --perfect-job-description perfect_job_description.txt

  python main.py --workflow cv-based --was "Developer" --wo "Hamburg" --cv cv.md

  # Brainstorm job titles (discover "Berufsbezeichnungen")
  python main.py --workflow brainstorm --cv cv.md
  python main.py --workflow brainstorm --cv cv.md --motivation-description motivation.txt
  python main.py --workflow brainstorm --motivation-description motivation.txt
        """,
    )

    # Get defaults from config
    default_umkreis = config.get("search.defaults.radius_km", 25)
    default_size = config.get("search.defaults.page_size", 100)
    default_max_pages = config.get("search.defaults.max_pages", 1)
    default_model = config.get("llm.models.default", "google/gemini-2.5-flash")
    default_delay = config.get("api.delays.scraping", 1.0)

    # Workflow selection
    parser.add_argument(
        "--workflow",
        type=str,
        choices=["multi-category", "perfect-job", "cv-based", "brainstorm"],
        default="multi-category",
        help="Analysis workflow (default: multi-category)",
    )

    # Search parameters
    parser.add_argument(
        "--was", type=str, required=False, help='Job title/description (e.g., "Softwareentwickler")'
    )
    parser.add_argument(
        "--wo", type=str, required=False, help='Location (e.g., "Berlin" or "München")'
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

    # Classification parameters
    parser.add_argument(
        "--categories",
        type=str,
        nargs="+",
        default=None,
        help="Categories for classification (uses categories.yaml if exists, otherwise defaults)",
    )
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

    # Workflow-specific options
    parser.add_argument(
        "--cv",
        type=str,
        help="Path to your CV file (required for cv-based; optional for brainstorm)",
    )
    parser.add_argument(
        "--perfect-job-category",
        type=str,
        help="Label for matching jobs in output/reports - binary classification into this vs 'Andere' (required for perfect-job workflow)",
    )
    parser.add_argument(
        "--perfect-job-description",
        type=str,
        help="Description of your perfect job - can be a file path (.txt/.md) or direct text (required for perfect-job workflow)",
    )
    parser.add_argument(
        "--motivation-description",
        type=str,
        help="Description of what motivates you in your career - can be a file path (.txt/.md) or direct text (optional for brainstorm workflow)",
    )
    parser.add_argument(
        "--return-all",
        action="store_true",
        help="Return all jobs including non-matches (perfect-job/cv-based workflows)",
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
        "If directory: uses debug/02_scraped_jobs.json (raw scraped data). "
        "Always uses unclassified data for clean re-classification",
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

        input_path = Path(args.input)
        if not input_path.exists():
            logger.error(f"Input path not found: {args.input}")
            sys.exit(1)

        # If it's a directory, resolve to raw scraped data
        if input_path.is_dir():
            # Re-classification should always use raw scraped data (no existing classifications)
            scraped_jobs_path = input_path / "debug" / "02_scraped_jobs.json"

            if scraped_jobs_path.exists():
                args.input = str(scraped_jobs_path)
                # Display path relative to cwd if possible, otherwise use as-is
                try:
                    display_path = scraped_jobs_path.resolve().relative_to(Path.cwd())
                except ValueError:
                    display_path = scraped_jobs_path
                logger.info(f"Using raw scraped data: {display_path}")
            else:
                # Display path relative to cwd if possible, otherwise use as-is
                try:
                    display_path = scraped_jobs_path.resolve().relative_to(Path.cwd())
                except ValueError:
                    display_path = scraped_jobs_path
                logger.error(f"Raw scraped data not found in session: {input_path}")
                logger.error(f"Expected: {display_path}")
                logger.error("")
                logger.error(
                    "Re-classification requires raw scraped data (without existing classifications)."
                )
                logger.error(
                    "If this is an old session, you may need to re-run the original search with scraping enabled."
                )
                sys.exit(1)

        if args.no_classification:
            logger.error("--classify-only and --no-classification are mutually exclusive")
            sys.exit(1)
    else:
        # Normal mode requires search parameters (except for brainstorm workflow)
        if args.workflow != "brainstorm" and (not args.was or not args.wo):
            logger.error(
                "--was and --wo are required (unless using --classify-only or --workflow brainstorm)"
            )
            logger.error("Run 'python main.py --help' for usage information")
            sys.exit(1)

    # Load perfect job description from file if it's a file path
    if args.perfect_job_description:
        args.perfect_job_description = load_description_from_file_or_string(
            args.perfect_job_description
        )

    # Load motivation description from file if it's a file path
    if args.motivation_description:
        args.motivation_description = load_description_from_file_or_string(
            args.motivation_description
        )

    # Validate workflow-specific requirements
    if args.workflow == "perfect-job":
        # Only validate for new searches, not re-classification
        if not args.classify_only and (
            not args.perfect_job_category or not args.perfect_job_description
        ):
            logger.error("--workflow perfect-job requires:")
            logger.error("  --perfect-job-category 'Category Name'")
            logger.error("  --perfect-job-description 'Description of ideal role...'")
            sys.exit(1)
    elif args.workflow == "cv-based":
        if not args.cv:
            logger.error("--workflow cv-based requires --cv /path/to/cv.md")
            sys.exit(1)
        cv_path = Path(args.cv)
        if not cv_path.exists():
            logger.error(f"CV file not found: {args.cv}")
            sys.exit(1)
    elif args.workflow == "brainstorm":
        # Brainstorm requires at least one of CV or motivation
        if not args.cv and not args.motivation_description:
            logger.error("--workflow brainstorm requires at least one of:")
            logger.error("  --cv /path/to/cv.md")
            logger.error("  --motivation-description 'description...' or /path/to/motivation.txt")
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

    # BRAINSTORM WORKFLOW: Special case - doesn't need job data
    if args.workflow == "brainstorm":
        # Brainstorm workflow runs independently - doesn't fetch/classify jobs

        # Load CV if provided
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

        # Motivation is already loaded from file if needed (see load_description_from_file_or_string above)
        motivation_content = args.motivation_description
        if motivation_content:
            logger.info(f"Motivation length: {len(motivation_content)} characters")

        # Validate API key for LLM
        if not api_key:
            logger.error("OpenRouter API key required for brainstorming")
            logger.error("Either set OPENROUTER_API_KEY environment variable or use --api-key")
            logger.error("Get your key at: https://openrouter.ai/keys")
            sys.exit(1)

        # Run brainstorm workflow
        try:
            brainstorm_workflow = BrainstormWorkflow(
                api_key=api_key,
                model=args.model,
                session=session,
                verbose=verbose,
            )

            suggestions = brainstorm_workflow.run(
                cv_content=cv_content,
                motivation_description=motivation_content,
            )

            # Format the output
            output = brainstorm_workflow.format_output(suggestions)

            # Save to file
            if session:
                output_path = session.session_dir / "brainstorm_suggestions.md"
            else:
                output_path = Path("brainstorm_suggestions.md")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output)

            # Print concise summary instead of full output
            print("\n" + "=" * 80)
            print("BRAINSTORMING COMPLETE")
            print("=" * 80)
            print(f"\n✓ Received answer ({len(suggestions)} characters)")
            print(f"✓ Saved to: {output_path}")
            print("\nOpen the file to view the suggestions and usage examples.")
            print("=" * 80)

            sys.exit(0)

        except (
            WorkflowConfigurationError,
            OpenRouterAPIError,
        ) as e:
            handle_classification_error(e)

    # Create user profile based on workflow
    if args.workflow == "multi-category":
        user_profile = UserProfile(categories=args.categories)
        logger.info(
            f"Categories ({user_profile.get_category_source()}): {', '.join(user_profile.get_categories())}"
        )
    elif args.workflow == "perfect-job":
        user_profile = UserProfile()
        # For re-classification, we need the parameters
        if args.classify_only and (
            not args.perfect_job_category or not args.perfect_job_description
        ):
            logger.error("--classify-only with --workflow perfect-job requires:")
            logger.error("  --perfect-job-category and --perfect-job-description")
            sys.exit(1)
        user_profile.set_perfect_job_category(
            category_name=args.perfect_job_category, description=args.perfect_job_description
        )
        logger.info(f"Perfect job category: {args.perfect_job_category}")
        logger.info(f"Return only matches: {not args.return_all}")
    else:  # cv-based
        user_profile = UserProfile(cv_path=args.cv)
        if not user_profile.has_cv():
            logger.error(f"Could not load CV from {args.cv}")
            sys.exit(1)
        logger.info(f"CV: {args.cv}")
        cv_content = user_profile.get_cv_content()
        if cv_content:
            logger.info(f"CV length: {len(cv_content)} characters")
        logger.info(f"Return only matches: {not args.return_all}")

    # CLASSIFY-ONLY MODE: Load jobs from JSON
    if args.classify_only:
        logger.info(f"Loading jobs from {args.input}...")

        with open(args.input, encoding="utf-8") as f:
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

        # Build extra API parameters
        extra_api_params: dict[str, Any] = {}
        if args.reasoning_effort:
            extra_api_params["reasoning"] = {"effort": args.reasoning_effort}
            extra_api_params["include_reasoning"] = True

        # Create and run workflow based on type
        try:
            if args.workflow == "multi-category":
                multi_workflow = MultiCategoryWorkflow(
                    user_profile=user_profile,
                    llm_processor=llm_processor,
                    session=session,
                    verbose=verbose,
                )
                classified_jobs = multi_workflow.process(jobs=jobs, batch_size=args.batch_size)
            elif args.workflow == "perfect-job":
                perfect_workflow = PerfectJobWorkflow(
                    user_profile=user_profile,
                    llm_processor=llm_processor,
                    session=session,
                    verbose=verbose,
                )
                classified_jobs = perfect_workflow.process(
                    jobs=jobs,
                    perfect_job_category=args.perfect_job_category,
                    perfect_job_description=args.perfect_job_description,
                    return_only_matches=not args.return_all,
                    batch_size=args.batch_size,
                )
            else:  # cv-based
                cv_workflow = CVBasedWorkflow(
                    user_profile=user_profile,
                    llm_processor=llm_processor,
                    session=session,
                    verbose=verbose,
                )
                classified_jobs = cv_workflow.process(
                    jobs=jobs, return_only_matches=not args.return_all, batch_size=args.batch_size
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
            from src.workflows.base import BaseWorkflow

            try:
                completed_workflow: BaseWorkflow
                if args.workflow == "multi-category":
                    multi_workflow = MultiCategoryWorkflow(
                        user_profile=user_profile,
                        llm_processor=llm_processor,
                        job_gatherer=gatherer,
                        session=session,
                        verbose=verbose,
                    )
                    classified_jobs, failed_jobs = multi_workflow.run(
                        was=args.was,
                        wo=args.wo,
                        umkreis=args.umkreis,
                        size=args.size,
                        max_pages=args.max_pages,
                        enable_scraping=not args.no_scraping,
                        show_statistics=True,
                        batch_size=args.batch_size,
                    )
                    completed_workflow = multi_workflow  # For later reference to gathering_stats
                elif args.workflow == "perfect-job":
                    perfect_workflow = PerfectJobWorkflow(
                        user_profile=user_profile,
                        llm_processor=llm_processor,
                        job_gatherer=gatherer,
                        session=session,
                        verbose=verbose,
                    )
                    classified_jobs, failed_jobs = perfect_workflow.run(
                        was=args.was,
                        wo=args.wo,
                        umkreis=args.umkreis,
                        size=args.size,
                        max_pages=args.max_pages,
                        enable_scraping=not args.no_scraping,
                        perfect_job_category=args.perfect_job_category,
                        perfect_job_description=args.perfect_job_description,
                        return_only_matches=not args.return_all,
                        show_statistics=True,
                        batch_size=args.batch_size,
                    )
                    completed_workflow = perfect_workflow  # For later reference to gathering_stats
                else:  # cv-based
                    cv_workflow = CVBasedWorkflow(
                        user_profile=user_profile,
                        llm_processor=llm_processor,
                        job_gatherer=gatherer,
                        session=session,
                        verbose=verbose,
                    )
                    classified_jobs, failed_jobs = cv_workflow.run(
                        was=args.was,
                        wo=args.wo,
                        umkreis=args.umkreis,
                        size=args.size,
                        max_pages=args.max_pages,
                        enable_scraping=not args.no_scraping,
                        return_only_matches=not args.return_all,
                        show_statistics=True,
                        batch_size=args.batch_size,
                    )
                    completed_workflow = cv_workflow  # For later reference to gathering_stats

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

        # Count truncated jobs
        truncated_count = sum(1 for job in classified_jobs if job.get("_truncated", False))

        # Count errors (from gathering_stats)
        if "completed_workflow" in locals() and hasattr(completed_workflow, "gathering_stats"):
            error_count = completed_workflow.gathering_stats.get("failed", 0)
            successful_fetches = completed_workflow.gathering_stats.get(
                "successfully_extracted", len(classified_jobs)
            )
            total_jobs_for_dashboard = completed_workflow.gathering_stats.get(
                "total_found", len(classified_jobs)
            )

            # For filtered workflows (cv-based, perfect-job without --return-all):
            # All scraped jobs are classified, but only matches are returned
            # For multi-category: all scraped jobs are both classified and returned
            if (
                args.workflow == "cv-based" or args.workflow == "perfect-job"
            ) and not args.return_all:
                # Filtered workflow: total_classified = all scraped jobs
                total_classified = successful_fetches
            else:
                # No filtering: total_classified = returned count
                total_classified = len(classified_jobs)
        else:
            # classify-only mode or no workflow
            # In classify-only mode, we have access to failed_jobs from extract_descriptions() above
            error_count = len(failed_jobs)
            successful_fetches = len(jobs)  # Jobs with successful extraction
            total_jobs_for_dashboard = total_jobs  # All jobs from the raw file

            # In classify-only mode, check if filtering was requested
            if (
                args.classify_only
                and (args.workflow == "cv-based" or args.workflow == "perfect-job")
                and not args.return_all
            ):
                # All jobs in input file were classified
                total_classified = total_jobs  # total_jobs was set to len(jobs) earlier
            else:
                total_classified = len(classified_jobs)

        # Show dashboard
        print_statistics_dashboard(
            classified_jobs=classified_jobs,
            total_jobs=total_jobs_for_dashboard,
            successful_fetches=successful_fetches,
            truncation_count=truncated_count,
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

        # Generate and save report
        from src.analyzer import generate_report
        from src.scraper import ExtractionStats, generate_extraction_statistics

        search_params = {
            "was": args.was if not args.classify_only else "N/A",
            "wo": args.wo if not args.classify_only else "N/A",
            "umkreis": args.umkreis if not args.classify_only else "N/A",
        }

        # Get gathering stats from workflow if available
        report_gathering_stats: dict[str, Any] | None = (
            getattr(completed_workflow, "gathering_stats", None)
            if "completed_workflow" in locals()
            else None
        )

        # Load scraped jobs to generate extraction statistics
        extraction_stats: ExtractionStats | None = None
        scraped_jobs_path = session.debug_dir / "02_scraped_jobs.json"
        if scraped_jobs_path.exists():
            with open(scraped_jobs_path, encoding="utf-8") as f:
                scraped_jobs = json.load(f)
                extraction_stats = generate_extraction_statistics(scraped_jobs)

        # Calculate total_classified for report (same logic as dashboard)
        if "completed_workflow" in locals() and hasattr(completed_workflow, "gathering_stats"):
            if (
                args.workflow == "cv-based" or args.workflow == "perfect-job"
            ) and not args.return_all:
                report_total_classified = completed_workflow.gathering_stats.get(
                    "successfully_extracted", len(classified_jobs)
                )
            else:
                report_total_classified = len(classified_jobs)
        elif (
            args.classify_only
            and (args.workflow == "cv-based" or args.workflow == "perfect-job")
            and not args.return_all
        ):
            # For filtered workflows in classify-only mode: all successfully extracted jobs were classified
            report_total_classified = len(jobs)  # Use jobs (successfully extracted), not total_jobs
        else:
            report_total_classified = len(classified_jobs)

        report = generate_report(
            classified_jobs=classified_jobs,
            total_jobs=total_jobs,
            search_params=search_params,
            gathering_stats=report_gathering_stats,
            extraction_stats=extraction_stats,
            total_classified=report_total_classified,
        )
        report_path = session.save_analysis_report(report)
        logger.info(f"✓ Analysis report saved to {report_path}")

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
