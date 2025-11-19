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
    ├── SUMMARY.txt
    ├── jobs_classified.json
    ├── jobs_all.csv
    ├── jobs_failed.csv (if any failures)
    └── debug/
        ├── session.log
        ├── *_prompt.txt
        ├── *_response.txt
        ├── *_thinking.md
        └── *_full_response.json
    """

    def __init__(
        self,
        base_dir: str | None = None,
        timestamp: str | None = None,
        verbose: bool = True,
    ):
        """
        Initialize a new search session

        Args:
            base_dir: Base directory for search sessions (defaults to value from paths_config.yaml)
            timestamp: Optional custom timestamp (defaults to current time)
            verbose: Whether to print logs to console (default: True)
        """
        if base_dir is None:
            # Check for environment variable override (useful for testing)
            import os

            base_dir = os.environ.get(
                "JOBSUCHE_SEARCHES_DIR", config.get("paths.directories.searches", "data/searches")
            )

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

    def save_session_summary(
        self,
        classified_jobs: list[dict],
        total_jobs: int,
        mode: str,
        model: str,
        profile_info: dict | None = None,
        search_params: dict | None = None,
        return_only_matches: bool = False,
        gathering_stats: dict | None = None,
        llm_stats: dict | None = None,
    ):
        """
        Save a concise human-readable session summary

        Args:
            classified_jobs: List of classified jobs (possibly filtered)
            total_jobs: Total number of jobs found/loaded
            mode: Mode description (e.g., "From Database", "Search", "Classify Only")
            model: LLM model used
            profile_info: Dict with cv_length, perfect_job_length, etc.
            search_params: Optional dict with was, wo, umkreis
            return_only_matches: Whether filtering was applied
            gathering_stats: Optional stats from workflow
            llm_stats: Optional LLM usage stats (batches, tokens, etc.)

        Returns:
            Path to the saved summary file
        """
        filename = "SUMMARY.txt"
        file_path = self.session_dir / filename

        # Build the summary
        lines = []
        lines.append("=" * 68)
        lines.append("JOB SEARCH SUMMARY")
        lines.append("=" * 68)

        # Session metadata
        timestamp_human = datetime.strptime(self.timestamp, "%Y%m%d_%H%M%S").strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        lines.append(f"Session:     {self.timestamp} ({timestamp_human})")
        lines.append(f"Mode:        {mode}")
        lines.append(f"Model:       {model}")

        # Profile information
        if profile_info:
            profile_parts = []
            if profile_info.get("cv_length"):
                profile_parts.append(f"CV ({profile_info['cv_length']:,} chars)")
            if profile_info.get("perfect_job_length"):
                profile_parts.append(f"Perfect Job ({profile_info['perfect_job_length']:,} chars)")
            if profile_parts:
                lines.append(f"Profile:     {', '.join(profile_parts)}")

        # Filter information
        if return_only_matches:
            lines.append("Filter:      Return only Good/Excellent matches")

        # Search parameters (if applicable)
        if search_params:
            if search_params.get("was"):
                lines.append(f"Search:      {search_params['was']}")
            if search_params.get("wo"):
                lines.append(f"Location:    {search_params['wo']}")
            if search_params.get("umkreis"):
                lines.append(f"Radius:      {search_params['umkreis']} km")

        lines.append("")
        lines.append("=" * 68)
        lines.append("RESULTS")
        lines.append("=" * 68)

        # Calculate statistics
        num_matches = len(classified_jobs)
        category_counts: dict[str, int] = {}
        for job in classified_jobs:
            for category in job.get("categories", []):
                category_counts[category] = category_counts.get(category, 0) + 1

        # Results summary
        lines.append(f"Total Jobs:           {total_jobs}")

        if gathering_stats and gathering_stats.get("successfully_extracted") is not None:
            successfully_scraped = gathering_stats["successfully_extracted"]
            lines.append(
                f"Successfully Scraped: {successfully_scraped} ({successfully_scraped / total_jobs * 100:.1f}%)"
            )

        if return_only_matches:
            # Show both total classified and matches
            total_classified = (
                gathering_stats.get("successfully_extracted", total_jobs)
                if gathering_stats
                else total_jobs
            )
            lines.append(f"Total Classified:     {total_classified}")
            lines.append(
                f"Matches Returned:     {num_matches} ({num_matches / total_classified * 100:.1f}%)"
            )
        else:
            lines.append(
                f"Successfully Matched: {num_matches} ({num_matches / total_jobs * 100:.1f}%)"
            )

        # Category breakdown
        if category_counts:
            lines.append("")
            sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
            for category, count in sorted_categories:
                percentage = (count / num_matches * 100) if num_matches > 0 else 0
                lines.append(f"  - {category:20} {count:3} ({percentage:.1f}% of matches)")

        # LLM statistics
        if llm_stats:
            lines.append("")
            if llm_stats.get("num_batches"):
                batch_info = llm_stats.get("batch_sizes", [])
                if batch_info:
                    batch_str = "+".join(str(s) for s in batch_info)
                    lines.append(
                        f"Batches:              {llm_stats['num_batches']} ({batch_str} jobs)"
                    )
                else:
                    lines.append(f"Batches:              {llm_stats['num_batches']}")

            if llm_stats.get("total_tokens"):
                prompt_tokens = llm_stats.get("prompt_tokens", 0)
                completion_tokens = llm_stats.get("completion_tokens", 0)
                lines.append(
                    f"Tokens:               {llm_stats['total_tokens']:,} "
                    f"({prompt_tokens:,} prompt + {completion_tokens:,} completion)"
                )

        lines.append("")
        lines.append("=" * 68)
        lines.append("FILES")
        lines.append("=" * 68)
        lines.append("jobs_classified.json  - Full data with classifications")
        lines.append("jobs_all.csv          - Spreadsheet view")
        lines.append("debug/session.log     - Complete execution log")
        lines.append("debug/*_thinking.md   - LLM reasoning (if available)")
        lines.append("")
        lines.append("Cost details: https://openrouter.ai/activity")
        lines.append("=" * 68)

        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return str(file_path)

    def save_csv_export(self, jobs: list[dict]):
        """Save CSV export of jobs"""
        import csv

        filename = config.get("paths.files.output.csv_export", "jobs_all.csv")
        file_path = self.session_dir / filename
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Titel", "Ort", "Arbeitgeber", "Categories", "URL"])

            for job in jobs:
                writer.writerow(
                    [
                        job.get("titel", ""),
                        job.get("ort", ""),
                        job.get("arbeitgeber", ""),
                        ", ".join(job.get("categories", [])),
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
  ├── SUMMARY.txt
  ├── jobs_classified.json
  ├── jobs_all.csv
  └── debug/
      ├── session.log
      ├── *_prompt.txt
      ├── *_response.txt
      ├── *_thinking.md
      └── *_full_response.json
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
