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
        self,
        base_dir: str | None = None,
        timestamp: str | None = None,
        verbose: bool = True,
        workflow: str | None = None,
        classify_only: bool = False,
    ):
        """
        Initialize a new search session

        Args:
            base_dir: Base directory for search sessions (defaults to value from paths_config.yaml)
            timestamp: Optional custom timestamp (defaults to current time)
            verbose: Whether to print logs to console (default: True)
            workflow: Workflow type (multi-category, matching, brainstorm)
            classify_only: Whether this is a classify-only session
        """
        if base_dir is None:
            base_dir = config.get("paths.directories.searches", "data/searches")

        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.timestamp = timestamp
        self.session_dir = Path(base_dir) / timestamp
        self.debug_dir = self.session_dir / "debug"
        self.workflow = workflow
        self.classify_only = classify_only

        # Session metadata (to be populated during workflow)
        self.search_term: str | None = None
        self.location: str | None = None
        self.total_jobs: int | None = None
        self.classified_jobs: int | None = None

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

    def save_llm_interaction(self, prompt: str, content: str, full_response: dict, label: str = ""):
        """
        Save a complete LLM interaction with full API response

        This is the preferred method for saving LLM interactions as it
        captures all metadata (tokens, model info, etc.) in addition to
        the prompt and response content.

        Args:
            prompt: The prompt sent to LLM
            content: The extracted text content from LLM response
            full_response: Complete API response dict (includes usage, metadata, etc.)
            label: Optional label for this interaction (e.g., "Batch 1", "Brainstorm")
        """
        # Determine filename based on label or use counter
        if label:
            # Sanitize label for filename
            safe_label = label.lower().replace(" ", "_").replace("/", "_")
            base_name = safe_label

            # Check if file already exists and add counter to make it unique
            counter = 1
            original_base_name = base_name
            while (self.debug_dir / f"{base_name}_full_response.json").exists():
                base_name = f"{original_base_name}_{counter:02d}"
                counter += 1
        else:
            # Count existing interaction files to generate unique name
            existing = list(self.debug_dir.glob("llm_interaction_*.json"))
            base_name = f"interaction_{len(existing) + 1:03d}"

        # Save prompt
        prompt_file = self.debug_dir / f"{base_name}_prompt.txt"
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Save response content
        response_file = self.debug_dir / f"{base_name}_response.txt"
        with open(response_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Save full API response
        full_response_file = self.debug_dir / f"{base_name}_full_response.json"
        with open(full_response_file, "w", encoding="utf-8") as f:
            json.dump(full_response, f, ensure_ascii=False, indent=2)

        # Extract and save thinking process (if available)
        thinking = self._extract_thinking_process(full_response)
        if thinking:
            thinking_file = self.debug_dir / f"{base_name}_thinking.md"
            with open(thinking_file, "w", encoding="utf-8") as f:
                f.write(thinking)

    def _extract_thinking_process(self, full_response: dict) -> str | None:
        """
        Extract thinking/reasoning process from LLM response and format as Markdown

        Args:
            full_response: Complete API response dict

        Returns:
            Formatted markdown string with thinking process, or None if not available
        """
        # Extract metadata for the header
        model = full_response.get("model", "unknown")
        response_id = full_response.get("id", "unknown")

        # Get usage information
        usage = full_response.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        completion_details = usage.get("completion_tokens_details", {})
        reasoning_tokens = completion_details.get("reasoning_tokens", 0)

        # Try to get reasoning from the message
        choices = full_response.get("choices", [])
        if not choices:
            return None

        message = choices[0].get("message", {})
        reasoning_text = message.get("reasoning", "")
        reasoning_details = message.get("reasoning_details", [])

        # If no reasoning available, return None
        if not reasoning_text and not reasoning_details:
            return None

        # Build the markdown document
        markdown_parts = []

        # Add header with metadata
        markdown_parts.append("# LLM Thinking Process\n")
        markdown_parts.append(f"**Model:** {model}\n")
        markdown_parts.append(f"**Response ID:** {response_id}\n")
        markdown_parts.append(f"**Total Tokens:** {total_tokens:,}\n")
        if reasoning_tokens > 0:
            markdown_parts.append(f"**Reasoning Tokens:** {reasoning_tokens:,}\n")
        markdown_parts.append("\n---\n\n")

        # Add the reasoning text
        if reasoning_text:
            markdown_parts.append(reasoning_text.strip())
        elif reasoning_details:
            # If we only have reasoning_details, extract text from there
            for detail in reasoning_details:
                if detail.get("type") == "reasoning.text":
                    text = detail.get("text", "")
                    if text:
                        markdown_parts.append(text.strip())

        return "\n".join(markdown_parts)

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

    def save_session_info(self) -> str:
        """
        Save session metadata to a JSON file with abbreviated workflow name

        The filename indicates the workflow type:
        - MC = MultiCategory workflow
        - MA = Matching workflow
        - BR = Brainstorm workflow
        - Appends _CO for classify-only sessions

        Returns:
            Path to the saved session info file
        """
        # Determine workflow abbreviation
        workflow_abbrev_map = {
            "multi-category": "MC",
            "matching": "MA",
            "brainstorm": "BR",
        }
        workflow_abbrev = workflow_abbrev_map.get(self.workflow or "", "UNK")

        # Append CO for classify-only
        if self.classify_only:
            workflow_abbrev += "_CO"

        # Build filename
        filename = f"session_info_{workflow_abbrev}.json"
        file_path = self.session_dir / filename

        # Prepare metadata
        session_info = {
            "timestamp": self.timestamp,
            "timestamp_human": datetime.strptime(self.timestamp, "%Y%m%d_%H%M%S").strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "workflow": self.workflow or "unknown",
            "classify_only": self.classify_only,
            "search_term": self.search_term,
            "location": self.location,
            "total_jobs": self.total_jobs,
            "classified_jobs": self.classified_jobs,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_info, f, ensure_ascii=False, indent=2)

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

    # Checkpoint management for resumable classification

    def has_checkpoint(self) -> bool:
        """Check if a classification checkpoint exists"""
        checkpoint_file = self.debug_dir / "classification_checkpoint.json"
        return checkpoint_file.exists()

    def save_checkpoint(
        self,
        completed_refnrs: list[str],
        pending_refnrs: list[str],
        current_batch: int,
        total_batches: int,
    ):
        """
        Save classification progress checkpoint

        Args:
            completed_refnrs: List of refnr values for jobs that have been classified
            pending_refnrs: List of refnr values for jobs still to be classified
            current_batch: Current batch number (0-indexed)
            total_batches: Total number of batches
        """
        checkpoint_file = self.debug_dir / "classification_checkpoint.json"
        checkpoint_data = {
            "completed_jobs": completed_refnrs,
            "pending_jobs": pending_refnrs,
            "current_batch": current_batch,
            "total_batches": total_batches,
            "last_updated": datetime.now().isoformat(),
        }
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

    def load_checkpoint(self) -> dict | None:
        """
        Load classification checkpoint if it exists

        Returns:
            Checkpoint data dict or None if no checkpoint exists
        """
        checkpoint_file = self.debug_dir / "classification_checkpoint.json"
        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, encoding="utf-8") as f:
            result: dict = json.load(f)
            return result

    def save_partial_results(self, classified_jobs: list[dict]):
        """
        Save partial classification results (append mode)

        Args:
            classified_jobs: List of newly classified jobs to append
        """
        partial_file = self.debug_dir / "partial_classified_jobs.json"

        # Load existing partial results if any
        existing_results: list[dict] = []
        if partial_file.exists():
            with open(partial_file, encoding="utf-8") as f:
                existing_results = json.load(f)

        # Append new results
        existing_results.extend(classified_jobs)

        # Save combined results
        with open(partial_file, "w", encoding="utf-8") as f:
            json.dump(existing_results, f, ensure_ascii=False, indent=2)

    def load_partial_results(self) -> list[dict]:
        """
        Load partial classification results if they exist

        Returns:
            List of partially classified jobs, or empty list if no partial results
        """
        partial_file = self.debug_dir / "partial_classified_jobs.json"
        if not partial_file.exists():
            return []

        with open(partial_file, encoding="utf-8") as f:
            result: list[dict] = json.load(f)
            return result

    def delete_checkpoint(self):
        """
        Delete checkpoint and partial results files

        This is used when starting a fresh classification (--no-resume)
        or when classification completes successfully.
        """
        checkpoint_file = self.debug_dir / "classification_checkpoint.json"
        partial_file = self.debug_dir / "partial_classified_jobs.json"

        if checkpoint_file.exists():
            checkpoint_file.unlink()

        if partial_file.exists():
            partial_file.unlink()
