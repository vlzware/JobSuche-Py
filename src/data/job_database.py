"""
Job Database Manager

Manages a persistent database of job listings to support incremental fetching
and avoid redundant API calls and scraping.

The database stores all jobs keyed by their unique refnr (reference number).
Jobs track metadata including first_seen, last_seen, and modification timestamps
to support efficient incremental updates.

Note: Classification status is NOT tracked here. Use session checkpoints for
classification recovery (see SearchSession.save_checkpoint/load_checkpoint).
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class JobDatabase:
    """
    Manages persistent storage of job listings.

    Supports:
    - Loading existing database
    - Merging new API results
    - Tracking new vs updated vs unchanged jobs
    - Saving updated database
    """

    def __init__(self, database_path: Path | None = None):
        """
        Initialize job database.

        Args:
            database_path: Path to database file. If None, uses default location.
        """
        if database_path is None:
            database_path = Path("data/database/jobs_global.json")

        self.database_path = Path(database_path)
        self.jobs: dict[str, dict] = {}  # Keyed by refnr
        self.metadata: dict = {
            "created": None,
            "last_updated": None,
            "total_jobs": 0,
            "active_jobs": 0,
        }

        # Track changes in current session
        self.new_jobs: set[str] = set()  # refnr of new jobs
        self.updated_jobs: set[str] = set()  # refnr of updated jobs
        self.unchanged_jobs: set[str] = set()  # refnr of unchanged jobs

    def exists(self) -> bool:
        """Check if database file exists."""
        return self.database_path.exists()

    def load(self) -> bool:
        """
        Load database from disk.

        Returns:
            True if database was loaded, False if no database exists
        """
        if not self.exists():
            logger.info(f"No existing database found at {self.database_path}")
            return False

        try:
            with open(self.database_path, encoding="utf-8") as f:
                data = json.load(f)

            self.metadata = data.get("metadata", {})
            self.jobs = data.get("jobs", {})

            logger.info(f"Loaded database with {len(self.jobs)} jobs from {self.database_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading database: {e}")
            raise

    def merge(
        self, api_jobs: list[dict], search_params: dict
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """
        Merge API results with existing database.

        Determines which jobs are new, updated, or unchanged based on:
        - refnr (unique identifier)
        - modifikationsTimestamp (modification timestamp)

        Args:
            api_jobs: List of jobs from API (must include modifikationsTimestamp)
            search_params: Search parameters that found these jobs

        Returns:
            Tuple of (new_jobs, updated_jobs, unchanged_jobs)
        """
        new_jobs = []
        updated_jobs = []
        unchanged_jobs = []

        current_time = datetime.now().isoformat()

        for api_job in api_jobs:
            refnr = api_job.get("refnr")
            if not refnr:
                logger.warning(f"Job missing refnr, skipping: {api_job.get('beruf', 'Unknown')}")
                continue

            modification_timestamp = api_job.get("modifikationsTimestamp")

            if refnr not in self.jobs:
                # New job - never seen before
                job_entry = {
                    **api_job,
                    "metadata": {
                        "first_seen": current_time,
                        "last_seen": current_time,
                    },
                    "found_in_searches": [
                        {
                            "was": search_params.get("was"),
                            "wo": search_params.get("wo"),
                            "first_match": current_time,
                        }
                    ],
                }
                self.jobs[refnr] = job_entry
                self.new_jobs.add(refnr)
                new_jobs.append(job_entry)
                logger.debug(f"New job: {refnr} - {api_job.get('beruf')}")

            else:
                # Existing job - check if modified
                existing_job = self.jobs[refnr]
                existing_modification = existing_job.get("modifikationsTimestamp")

                # Update last_seen timestamp
                existing_job["metadata"]["last_seen"] = current_time

                # Check if this search already found this job
                found_in_searches = existing_job.get("found_in_searches", [])
                search_key = (search_params.get("was"), search_params.get("wo"))
                if not any(
                    s.get("was") == search_key[0] and s.get("wo") == search_key[1]
                    for s in found_in_searches
                ):
                    found_in_searches.append(
                        {
                            "was": search_params.get("was"),
                            "wo": search_params.get("wo"),
                            "first_match": current_time,
                        }
                    )
                    existing_job["found_in_searches"] = found_in_searches

                # Compare modification timestamps
                if modification_timestamp and modification_timestamp != existing_modification:
                    # Job was modified - update it
                    logger.info(f"Job modified: {refnr} - {api_job.get('beruf')}")

                    # Update job data but preserve metadata
                    old_metadata = existing_job.get("metadata", {})

                    # Update with new API data
                    self.jobs[refnr] = {
                        **api_job,
                        "metadata": {
                            **old_metadata,
                            "last_seen": current_time,
                        },
                        "found_in_searches": found_in_searches,
                    }

                    self.updated_jobs.add(refnr)
                    updated_jobs.append(self.jobs[refnr])
                else:
                    # Job unchanged
                    self.unchanged_jobs.add(refnr)
                    unchanged_jobs.append(existing_job)

        logger.info(
            f"Merge complete: {len(new_jobs)} new, {len(updated_jobs)} updated, {len(unchanged_jobs)} unchanged"
        )
        return new_jobs, updated_jobs, unchanged_jobs

    def save(self):
        """Save database to disk."""
        # Update metadata
        if self.metadata.get("created") is None:
            self.metadata["created"] = datetime.now().isoformat()

        self.metadata["last_updated"] = datetime.now().isoformat()
        self.metadata["total_jobs"] = len(self.jobs)
        self.metadata["active_jobs"] = len(self.jobs)  # All jobs are active (deleted ones removed)

        # Ensure directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to file
        data = {"metadata": self.metadata, "jobs": self.jobs}

        with open(self.database_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Database saved to {self.database_path} ({len(self.jobs)} jobs)")

    def update_details(self, refnr: str, details: dict):
        """
        Update scraped details for a job.

        Args:
            refnr: Job reference number
            details: Details dictionary from scraper
        """
        if refnr in self.jobs:
            self.jobs[refnr]["details"] = details

    def get_delta_summary(self) -> dict:
        """
        Get summary of changes in current session.

        Returns:
            Dictionary with counts of new, updated, and unchanged jobs
        """
        return {
            "new": len(self.new_jobs),
            "updated": len(self.updated_jobs),
            "unchanged": len(self.unchanged_jobs),
            "total_in_database": len(self.jobs),
        }

    def get_job(self, refnr: str) -> dict | None:
        """Get a specific job by reference number."""
        return self.jobs.get(refnr)

    def get_all_jobs(self) -> list[dict]:
        """Get all jobs in database."""
        return list(self.jobs.values())
