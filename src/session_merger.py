"""
Session merging utility for combining scraped data from multiple sessions

This module provides functionality to merge raw job data from multiple search sessions,
using job reference numbers (refnr) for deduplication.
"""

import json
from pathlib import Path
from typing import Any

from .logging_config import get_module_logger

logger = get_module_logger("session_merger")


class SessionMerger:
    """
    Merges raw scraped job data from multiple search sessions.

    Uses the 'refnr' field (Arbeitsagentur reference number) to deduplicate
    jobs across sessions. This allows combining results from multiple searches
    (e.g., different job titles) into a single dataset for classification.

    Example usage:
        merger = SessionMerger()
        merged_jobs = merger.merge_sessions([
            "data/searches/20251112_084239",
            "data/searches/20251112_090241",
            "data/searches/20251112_091022",
        ])
    """

    def __init__(self, verbose: bool = True):
        """
        Initialize SessionMerger

        Args:
            verbose: Whether to log progress information
        """
        self.verbose = verbose

    def merge_sessions(self, session_paths: list[str | Path]) -> list[dict[str, Any]]:
        """
        Merge raw scraped data from multiple session directories

        Args:
            session_paths: List of paths to session directories or JSON files

        Returns:
            List of merged and deduplicated job dictionaries

        Raises:
            FileNotFoundError: If a session path or scraped data file doesn't exist
            ValueError: If no valid jobs found in any session
        """
        merged_jobs: dict[str, dict[str, Any]] = {}  # refnr -> job dict
        session_stats: list[dict[str, Any]] = []

        for session_path in session_paths:
            session_path = Path(session_path)

            # Resolve to scraped_jobs.json if directory
            if session_path.is_dir():
                scraped_jobs_path = session_path / "debug" / "02_scraped_jobs.json"
                if not scraped_jobs_path.exists():
                    logger.warning(
                        f"Skipping session {session_path.name}: no scraped data found "
                        f"(expected {scraped_jobs_path})"
                    )
                    continue
                jobs_file = scraped_jobs_path
                session_name = session_path.name
            elif session_path.is_file():
                jobs_file = session_path
                session_name = session_path.stem
            else:
                raise FileNotFoundError(f"Session path not found: {session_path}")

            # Load jobs from file
            try:
                with open(jobs_file, encoding="utf-8") as f:
                    jobs = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from {jobs_file}: {e}")
                continue

            # Count jobs and deduplicate by refnr
            total_count = len(jobs)
            new_count = 0
            duplicate_count = 0

            for job in jobs:
                refnr = job.get("refnr")
                if not refnr:
                    logger.warning(
                        f"Skipping job without refnr in {session_name}: {job.get('titel', 'unknown')}"
                    )
                    continue

                if refnr not in merged_jobs:
                    merged_jobs[refnr] = job
                    new_count += 1
                else:
                    duplicate_count += 1

            session_stats.append(
                {
                    "session": session_name,
                    "total": total_count,
                    "new": new_count,
                    "duplicates": duplicate_count,
                }
            )

            if self.verbose:
                logger.info(
                    f"Session {session_name}: {total_count} jobs "
                    f"({new_count} new, {duplicate_count} duplicates)"
                )

        # Summary
        total_merged = len(merged_jobs)
        total_processed = sum(stat["total"] for stat in session_stats)
        total_duplicates = sum(stat["duplicates"] for stat in session_stats)

        if total_merged == 0:
            raise ValueError("No valid jobs found in any session")

        if self.verbose:
            logger.info("=" * 80)
            logger.info("Merge complete:")
            logger.info(f"  Sessions merged: {len(session_stats)}")
            logger.info(f"  Total jobs processed: {total_processed}")
            logger.info(f"  Duplicates removed: {total_duplicates}")
            logger.info(f"  Unique jobs: {total_merged}")
            logger.info("=" * 80)

        return list(merged_jobs.values())

    def save_merged_data(self, merged_jobs: list[dict[str, Any]], output_path: str | Path) -> None:
        """
        Save merged job data to a JSON file

        Args:
            merged_jobs: List of merged job dictionaries
            output_path: Path where to save the merged data
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged_jobs, f, ensure_ascii=False, indent=2)

        if self.verbose:
            logger.info(f"Merged data saved to {output_path}")
