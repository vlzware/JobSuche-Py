"""
Job data gatherer - encapsulates all data collection from Arbeitsagentur

This module provides a clean interface to gather job data, abstracting away
the API client and scraping details.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..api_client import search_jobs
from ..config import config
from ..logging_config import get_module_logger
from ..scraper import extract_descriptions, fetch_detailed_listings
from .job_database import JobDatabase

logger = get_module_logger("gatherer")

if TYPE_CHECKING:
    from ..session import SearchSession


class JobGatherer:
    """
    Handles all job data gathering from Arbeitsagentur

    This class encapsulates the entire data collection pipeline:
    1. Search via API
    2. Scrape detailed descriptions
    3. Extract and clean data
    """

    def __init__(
        self,
        session: Optional["SearchSession"] = None,
        verbose: bool = True,
        database_path: Path | None = None,
    ):
        """
        Initialize the job gatherer

        Args:
            session: Optional SearchSession for saving artifacts
            verbose: Whether to print progress messages
            database_path: Path to job database (default: data/database/jobs.json)
        """
        self.session = session
        self.verbose = verbose
        self.database = JobDatabase(database_path)

    def gather(
        self,
        was: str,
        wo: str | None = None,
        umkreis: int | None = None,
        size: int | None = None,
        max_pages: int | None = None,
        arbeitszeit: str = "",
        include_weiterbildung: bool = False,
        enable_scraping: bool = True,
        scraping_delay: float | None = None,
        veroeffentlichtseit: int | None = None,
        use_database: bool = True,
    ) -> tuple[list[dict], list[dict], dict]:
        """
        Gather job data from Arbeitsagentur with incremental database support

        Args:
            was: Job title/description (e.g., "Softwareentwickler")
            wo: Location (e.g., "Bergisch Gladbach"). Optional - if omitted, searches all of Germany.
            umkreis: Search radius in km (defaults to config value)
            size: Results per page (max 100, defaults to config value)
            max_pages: Maximum number of pages to fetch (defaults to config value)
            arbeitszeit: Work time filter (vz, tz, ho, or empty)
            include_weiterbildung: Include training/education jobs
            enable_scraping: Whether to scrape detailed descriptions
            scraping_delay: Delay between scraping requests (defaults to config value)
            veroeffentlichtseit: Days since publication (0-100). If None and database exists,
                                defaults to 7 days for incremental updates.
            use_database: Whether to use persistent database for incremental fetching

        Returns:
            Tuple of (successful_jobs, failed_jobs, gathering_statistics):
            - successful_jobs: Job dictionaries with all available data (NEW/UPDATED jobs only if using database)
            - failed_jobs: Jobs that failed to scrape with error info
            - gathering_statistics: Dict with counts and metrics
        """
        # Load defaults from config if not provided
        if umkreis is None:
            umkreis = config.get("search.defaults.radius_km", 25)
        if size is None:
            size = config.get("search.defaults.page_size", 100)
        if max_pages is None:
            max_pages = config.get("search.defaults.max_pages", 1)
        if scraping_delay is None:
            scraping_delay = config.get("api.delays.scraping", 1.0)

        # Database logic: determine if we should do incremental fetch
        database_exists = use_database and self.database.exists()

        if database_exists:
            logger.info(f"Loading existing job database from {self.database.database_path}")
            self.database.load()
            logger.info(f"Database loaded: {len(self.database.jobs)} existing jobs")

            # Validate geographic context - database is locked to one area
            is_valid, error_msg = self.database.validate_geographic_context(wo, umkreis)
            if not is_valid:
                logger.error(error_msg)
                raise ValueError("Geographic context mismatch - see error above")

            # Check if this search criteria has been used before
            search_params = {"was": was, "wo": wo, "umkreis": umkreis}
            has_history = self.database.has_search_history(search_params)

            # Only use incremental fetch if we've searched with these exact criteria before
            if veroeffentlichtseit is None:
                if has_history:
                    # Repeated search - use incremental fetch
                    veroeffentlichtseit = config.get("search.defaults.veroeffentlichtseit", 7)
                    logger.warning(
                        f"⚠️  Performing incremental fetch (jobs published in last {veroeffentlichtseit} days)"
                    )
                else:
                    # New search criteria - do full fetch
                    logger.info(
                        f"🔍 New search criteria detected (was='{was}') - performing FULL fetch"
                    )
                    # veroeffentlichtseit stays None for full fetch
        else:
            if use_database:
                logger.info(
                    f"No existing database found at {self.database.database_path} - performing full fetch"
                )
                # Set geographic context on first search
                self.database.set_geographic_context(wo, umkreis)
            else:
                logger.info("Database disabled - performing full fetch")

        # Step 1: Search for jobs via API
        logger.info("Searching for jobs...")
        logger.info(f"  Position: {was}")
        if wo:
            logger.info(f"  Location: {wo}")
            logger.info(f"  Radius: {umkreis} km")
        else:
            logger.warning("  Location: ALL OF GERMANY (no location filter specified)")
        logger.info(f"  Pages: {max_pages} (size: {size})")
        if veroeffentlichtseit is not None:
            logger.info(f"  Days since publication: {veroeffentlichtseit}")

        jobs = search_jobs(
            was=was,
            wo=wo,
            size=size,
            max_pages=max_pages,
            umkreis=umkreis,
            arbeitszeit=arbeitszeit,
            exclude_weiterbildung=not include_weiterbildung,
            veroeffentlichtseit=veroeffentlichtseit,
            session=self.session,
        )

        if not jobs:
            logger.warning("No jobs found from API.")
            if database_exists:
                logger.info("Database still contains existing jobs - no new updates to process")
                return (
                    [],
                    [],
                    {
                        "total_found": 0,
                        "total_scraped": 0,
                        "successfully_extracted": 0,
                        "failed": 0,
                        "database_total": len(self.database.jobs),
                        "new_jobs": 0,
                        "updated_jobs": 0,
                        "unchanged_jobs": 0,
                    },
                )
            return (
                [],
                [],
                {"total_found": 0, "total_scraped": 0, "successfully_extracted": 0, "failed": 0},
            )

        total_jobs_from_api = len(jobs)
        logger.info(f"✓ Found {total_jobs_from_api} jobs from API")

        # Step 1.5: Merge with database if using incremental fetch
        jobs_to_process = jobs  # By default, process all jobs
        new_jobs: list[dict] = []
        updated_jobs: list[dict] = []

        if use_database:
            search_params = {"was": was, "wo": wo, "umkreis": umkreis}
            new_jobs, updated_jobs, _unchanged_jobs = self.database.merge(jobs, search_params)

            # Only process NEW and UPDATED jobs (skip unchanged)
            jobs_to_process = new_jobs + updated_jobs

            delta_summary = self.database.get_delta_summary()
            logger.info(
                f"Database merge: {delta_summary['new']} new, "
                f"{delta_summary['updated']} updated, "
                f"{delta_summary['unchanged']} unchanged"
            )
            logger.info(f"Total in database: {delta_summary['total_in_database']} jobs")

            if not jobs_to_process:
                logger.info("No new or updated jobs to process - skipping scraping")
                # Save database even if no changes (updates last_seen timestamps)
                self.database.save()
                return (
                    [],
                    [],
                    {
                        "total_found": total_jobs_from_api,
                        "total_scraped": 0,
                        "successfully_extracted": 0,
                        "failed": 0,
                        "database_total": len(self.database.jobs),
                        "new_jobs": delta_summary["new"],
                        "updated_jobs": delta_summary["updated"],
                        "unchanged_jobs": delta_summary["unchanged"],
                    },
                )

            logger.info(f"Will scrape {len(jobs_to_process)} jobs (new + updated)")
        else:
            logger.info(f"Will scrape all {total_jobs_from_api} jobs (database disabled)")

        # Step 2: Scrape detailed descriptions (optional)
        if not enable_scraping:
            logger.info("Skipping job detail scraping (disabled)")

            # Save to database if enabled
            if use_database:
                self.database.save()

            stats = {
                "total_found": total_jobs_from_api,
                "total_scraped": len(jobs_to_process),
                "successfully_extracted": len(jobs_to_process),
                "failed": 0,
            }

            if use_database:
                delta_summary = self.database.get_delta_summary()
                stats.update(
                    {
                        "database_total": len(self.database.jobs),
                        "new_jobs": delta_summary["new"],
                        "updated_jobs": delta_summary["updated"],
                        "unchanged_jobs": delta_summary["unchanged"],
                    }
                )

            return jobs_to_process, [], stats

        logger.info("Fetching detailed job descriptions...")
        logger.info(
            f"  (This may take a while, ~{len(jobs_to_process) * scraping_delay:.0f} seconds)"
        )

        detailed_jobs = fetch_detailed_listings(
            jobs=jobs_to_process, delay=scraping_delay, verbose=self.verbose, session=self.session
        )

        # Extract successful and failed descriptions
        extracted_jobs, failed_jobs = extract_descriptions(detailed_jobs)

        logger.info(
            f"✓ Successfully fetched {len(extracted_jobs)}/{len(jobs_to_process)} job descriptions"
        )
        if failed_jobs:
            logger.warning(f"✗ Failed to scrape {len(failed_jobs)}/{len(jobs_to_process)} jobs")

        # Step 3: Update database with scraped details
        if use_database:
            logger.info("Updating database with scraped details...")
            for job in detailed_jobs:
                refnr = job.get("refnr")
                details = job.get("details", {})
                if refnr and details:
                    self.database.update_details(refnr, details)

            # Save updated database
            self.database.save()
            logger.info(f"✓ Database saved to {self.database.database_path}")

        stats = {
            "total_found": total_jobs_from_api,
            "total_scraped": len(detailed_jobs),
            "successfully_extracted": len(extracted_jobs),
            "failed": len(failed_jobs),
        }

        if use_database:
            delta_summary = self.database.get_delta_summary()
            stats.update(
                {
                    "database_total": len(self.database.jobs),
                    "new_jobs": delta_summary["new"],
                    "updated_jobs": delta_summary["updated"],
                    "unchanged_jobs": delta_summary["unchanged"],
                }
            )

        return extracted_jobs, failed_jobs, stats

    def gather_from_raw_data(self, jobs: list[dict]) -> list[dict]:
        """
        Process already-fetched job data (e.g., from saved JSON)

        Args:
            jobs: List of job dictionaries

        Returns:
            The same jobs (pass-through for consistency)
        """
        logger.info(f"Processing {len(jobs)} pre-fetched jobs")

        return jobs
