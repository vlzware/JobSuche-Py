"""
Search session management for organizing artifacts and outputs
Creates timestamped directories and manages all debug/output files
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import config
from .logging_config import setup_session_logging


class SearchSession:
    """
    Manages a single job search session with organized file structure:

    data/searches/YYYYMMDD_HHMMSS/
    ├── debug/
    │   ├── 01_raw_api_response.json
    │   ├── 02_scraped_jobs.json
    │   ├── 03_llm_request.txt
    │   └── 04_llm_response.txt
    ├── analysis_report.txt
    ├── jobs_classified.json
    └── jobs_all.csv
    """

    def __init__(
        self, base_dir: str | None = None, timestamp: str | None = None, verbose: bool = True
    ):
        """
        Initialize a new search session

        Args:
            base_dir: Base directory for search sessions (defaults to value from paths_config.yaml)
            timestamp: Optional custom timestamp (defaults to current time)
            verbose: Whether to print logs to console (default: True)
        """
        if base_dir is None:
            base_dir = config.get("paths.directories.searches", "data/searches")

        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.timestamp = timestamp
        self.session_dir = Path(base_dir) / timestamp
        self.debug_dir = self.session_dir / "debug"

        # Create directories
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(exist_ok=True)

        # Setup logging
        self.logger = setup_session_logging(session_dir=self.session_dir, verbose=verbose)

        self.logger.info(f"Initialized session: {timestamp}")

    # Debug artifacts (raw data for debugging)

    def save_raw_api_response(self, data: Any):
        """Save raw API response from Arbeitsagentur"""
        filename = config.get("paths.files.debug.raw_api_response", "01_raw_api_response.json")
        file_path = self.debug_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_scraped_jobs(self, jobs: list[dict]):
        """Save jobs after scraping (with details attached)"""
        filename = config.get("paths.files.debug.scraped_jobs", "02_scraped_jobs.json")
        file_path = self.debug_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)

    def save_llm_request(self, request_text: str):
        """Save the prompt/request sent to the LLM"""
        filename = config.get("paths.files.debug.llm_request", "03_llm_request.txt")
        file_path = self.debug_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request_text)

    def save_llm_response(self, response_text: str):
        """Save the raw response from the LLM"""
        filename = config.get("paths.files.debug.llm_response", "04_llm_response.txt")
        file_path = self.debug_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(response_text)

    def append_llm_interaction(self, request: str, response: str, batch_info: str = ""):
        """
        Append an LLM interaction to debug files (for batch processing)

        Args:
            request: The prompt sent to LLM
            response: The response from LLM
            batch_info: Optional batch identifier (e.g., "Batch 1/3")
        """
        separator = f"\n{'=' * 80}\n"

        # Append to request file
        request_filename = config.get("paths.files.debug.llm_request", "03_llm_request.txt")
        request_file = self.debug_dir / request_filename
        with open(request_file, "a", encoding="utf-8") as f:
            if request_file.exists() and request_file.stat().st_size > 0:
                f.write(separator)
            if batch_info:
                f.write(f"{batch_info}\n{'-' * 80}\n")
            f.write(request)
            f.write("\n")

        # Append to response file
        response_filename = config.get("paths.files.debug.llm_response", "04_llm_response.txt")
        response_file = self.debug_dir / response_filename
        with open(response_file, "a", encoding="utf-8") as f:
            if response_file.exists() and response_file.stat().st_size > 0:
                f.write(separator)
            if batch_info:
                f.write(f"{batch_info}\n{'-' * 80}\n")
            f.write(response)
            f.write("\n")

    # User-facing outputs

    def save_classified_jobs(self, jobs: list[dict]):
        """Save final classified jobs JSON"""
        filename = config.get("paths.files.output.classified_jobs", "jobs_classified.json")
        file_path = self.session_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        return str(file_path)

    def save_analysis_report(self, report: str):
        """Save analysis report text file"""
        filename = config.get("paths.files.output.analysis_report", "analysis_report.txt")
        file_path = self.session_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report)
        return str(file_path)

    def save_csv_export(self, jobs: list[dict]):
        """Save CSV export of jobs with truncation indicator"""
        import csv

        filename = config.get("paths.files.output.csv_export", "jobs_all.csv")
        file_path = self.session_dir / filename
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Titel", "Ort", "Arbeitgeber", "Categories", "Truncated", "Original_Length", "URL"]
            )

            for job in jobs:
                writer.writerow(
                    [
                        job.get("titel", ""),
                        job.get("ort", ""),
                        job.get("arbeitgeber", ""),
                        ", ".join(job.get("categories", [])),
                        "YES" if job.get("_truncated", False) else "NO",
                        job.get("_original_text_length", "N/A"),
                        job.get("url", ""),
                    ]
                )

        return str(file_path)

    def save_failed_jobs_csv(self, failed_jobs: list[dict]):
        """
        Save CSV export of failed scraping attempts

        Args:
            failed_jobs: List of jobs that failed to scrape with error info

        Returns:
            Path to the saved CSV file
        """
        import csv

        filename = "jobs_failed.csv"
        file_path = self.session_dir / filename

        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Titel", "Ort", "Arbeitgeber", "URL", "Error_Type"])

            for job in failed_jobs:
                writer.writerow(
                    [
                        job.get("titel", ""),
                        job.get("ort", ""),
                        job.get("arbeitgeber", ""),
                        job.get("url", ""),
                        job.get("error_type", "UNKNOWN"),
                    ]
                )

        return str(file_path)

    def get_summary(self) -> str:
        """Get a summary of the session directory structure"""
        return f"""
Session directory: {self.session_dir}

Structure:
  {self.session_dir}/
  ├── debug/
  │   ├── 01_raw_api_response.json
  │   ├── 02_scraped_jobs.json
  │   ├── 03_llm_request.txt
  │   └── 04_llm_response.txt
  ├── analysis_report.txt
  ├── jobs_classified.json
  └── jobs_all.csv
""".strip()
