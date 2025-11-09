"""
Job data gatherer - encapsulates all data collection from Arbeitsagentur

This module provides a clean interface to gather job data, abstracting away
the API client and scraping details.
"""

from typing import TYPE_CHECKING, Optional

from ..api_client import search_jobs
from ..config import config
from ..logging_config import get_module_logger
from ..scraper import extract_descriptions, fetch_detailed_listings

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

    def __init__(self, session: Optional["SearchSession"] = None, verbose: bool = True):
        """
        Initialize the job gatherer

        Args:
            session: Optional SearchSession for saving artifacts
            verbose: Whether to print progress messages
        """
        self.session = session
        self.verbose = verbose

    def gather(
        self,
        was: str,
        wo: str,
        umkreis: int | None = None,
        size: int | None = None,
        max_pages: int | None = None,
        arbeitszeit: str = "",
        include_weiterbildung: bool = False,
        enable_scraping: bool = True,
        scraping_delay: float | None = None,
    ) -> tuple[list[dict], list[dict], dict]:
        """
        Gather job data from Arbeitsagentur

        Args:
            was: Job title/description (e.g., "Softwareentwickler")
            wo: Location (e.g., "Bergisch Gladbach")
            umkreis: Search radius in km (defaults to config value)
            size: Results per page (max 100, defaults to config value)
            max_pages: Maximum number of pages to fetch (defaults to config value)
            arbeitszeit: Work time filter (vz, tz, ho, or empty)
            include_weiterbildung: Include training/education jobs
            enable_scraping: Whether to scrape detailed descriptions
            scraping_delay: Delay between scraping requests (defaults to config value)

        Returns:
            Tuple of (successful_jobs, failed_jobs, gathering_statistics):
            - successful_jobs: Job dictionaries with all available data
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
        # Step 1: Search for jobs via API
        logger.info("Searching for jobs...")
        logger.info(f"  Position: {was}")
        logger.info(f"  Location: {wo}")
        logger.info(f"  Radius: {umkreis} km")
        logger.info(f"  Pages: {max_pages} (size: {size})")

        jobs = search_jobs(
            was=was,
            wo=wo,
            size=size,
            max_pages=max_pages,
            umkreis=umkreis,
            arbeitszeit=arbeitszeit,
            exclude_weiterbildung=not include_weiterbildung,
            session=self.session,
        )

        if not jobs:
            logger.warning("No jobs found. Try different search parameters.")
            return (
                [],
                [],
                {"total_found": 0, "total_scraped": 0, "successfully_extracted": 0, "failed": 0},
            )

        total_jobs = len(jobs)

        logger.info(f"✓ Found {total_jobs} jobs")

        # Step 2: Scrape detailed descriptions (optional)
        if not enable_scraping:
            logger.info("Skipping job detail scraping (disabled)")
            stats = {
                "total_found": total_jobs,
                "total_scraped": total_jobs,
                "successfully_extracted": total_jobs,
                "failed": 0,
            }
            return jobs, [], stats

        logger.info("Fetching detailed job descriptions...")
        logger.info(f"  (This may take a while, ~{total_jobs * scraping_delay:.0f} seconds)")

        detailed_jobs = fetch_detailed_listings(
            jobs=jobs, delay=scraping_delay, verbose=self.verbose, session=self.session
        )

        # Extract successful and failed descriptions
        extracted_jobs, failed_jobs = extract_descriptions(detailed_jobs)

        logger.info(f"✓ Successfully fetched {len(extracted_jobs)}/{total_jobs} job descriptions")
        if failed_jobs:
            logger.warning(f"✗ Failed to scrape {len(failed_jobs)}/{total_jobs} jobs")

        stats = {
            "total_found": total_jobs,
            "total_scraped": len(detailed_jobs),
            "successfully_extracted": len(extracted_jobs),
            "failed": len(failed_jobs),
        }

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
