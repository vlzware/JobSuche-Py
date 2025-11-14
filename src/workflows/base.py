"""
Base workflow - abstract base class for all job analysis workflows
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from ..analyzer import generate_report, print_statistics
from ..config import config
from ..data.gatherer import JobGatherer
from ..llm.processor import LLMProcessor
from ..preferences.user_profile import UserProfile

if TYPE_CHECKING:
    from ..session import SearchSession


class BaseWorkflow(ABC):
    """
    Abstract base class for job analysis workflows

    All workflows follow the same pattern:
    1. Gather data (from Arbeitsagentur or file)
    2. Process with LLM
    3. Analyze and report
    """

    def __init__(
        self,
        user_profile: UserProfile,
        llm_processor: LLMProcessor,
        job_gatherer: JobGatherer | None = None,
        session: Optional["SearchSession"] = None,
        verbose: bool = True,
    ):
        """
        Initialize the workflow

        Args:
            user_profile: User preferences and categories
            llm_processor: LLM processor for classification
            job_gatherer: Optional job gatherer (created if not provided)
            session: Optional SearchSession for saving artifacts
            verbose: Whether to print progress messages
        """
        self.user_profile = user_profile
        self.llm_processor = llm_processor
        self.job_gatherer = job_gatherer or JobGatherer(session=session, verbose=verbose)
        self.session = session
        self.verbose = verbose

    @abstractmethod
    def process(self, jobs: list[dict]) -> list[dict]:
        """
        Process jobs using LLM classification

        This is the core workflow-specific logic that each workflow
        must implement.

        Args:
            jobs: List of jobs to process

        Returns:
            List of processed/classified jobs
        """
        pass

    def run(
        self,
        was: str,
        wo: str,
        umkreis: int | None = None,
        size: int | None = None,
        max_pages: int | None = None,
        enable_scraping: bool = True,
        show_statistics: bool = True,
        **kwargs,
    ) -> tuple[list[dict], list[dict]]:
        """
        Run the complete workflow: gather → process → analyze

        Args:
            was: Job title/description
            wo: Location
            umkreis: Search radius in km (defaults to config value)
            size: Results per page (defaults to config value)
            max_pages: Maximum pages to fetch (defaults to config value)
            enable_scraping: Whether to scrape detailed descriptions
            show_statistics: Whether to print statistics
            **kwargs: Additional workflow-specific parameters

        Returns:
            Tuple of (classified_jobs, failed_jobs)
        """
        # Load defaults from config if not provided
        if umkreis is None:
            umkreis = config.get("search.defaults.radius_km", 25)
        if size is None:
            size = config.get("search.defaults.page_size", 100)
        if max_pages is None:
            max_pages = config.get("search.defaults.max_pages", 1)
        # Step 1: Gather data
        jobs, failed_jobs, gathering_stats = self.job_gatherer.gather(
            was=was,
            wo=wo,
            umkreis=umkreis,
            size=size,
            max_pages=max_pages,
            enable_scraping=enable_scraping,
        )

        if not jobs:
            return [], failed_jobs

        # Store gathering stats and failed jobs for report generation
        self.gathering_stats = gathering_stats
        self.failed_jobs = failed_jobs

        # Step 2: Process with LLM
        classified_jobs = self.process(jobs, **kwargs)

        # Step 3: Analyze and report
        if show_statistics:
            print_statistics(
                classified_jobs=classified_jobs,
                total_jobs=gathering_stats["total_found"],
                successful_fetches=gathering_stats["successfully_extracted"],
            )

        return classified_jobs, failed_jobs

    def run_from_file(
        self, jobs: list[dict], show_statistics: bool = True, resume: bool = True, **kwargs
    ) -> list[dict]:
        """
        Run workflow on pre-loaded job data

        Args:
            jobs: Pre-loaded job data
            show_statistics: Whether to print statistics
            resume: Whether to resume from checkpoint if exists (default: True)
            **kwargs: Additional workflow-specific parameters

        Returns:
            List of classified jobs
        """
        total_jobs = len(jobs)
        jobs_to_process = jobs
        partial_results = []

        # Handle checkpoint resume
        if self.session and resume:
            checkpoint = self.session.load_checkpoint()
            if checkpoint:
                completed_refnrs = set(checkpoint.get("completed_jobs", []))
                partial_results = self.session.load_partial_results()

                # Filter out already-classified jobs
                jobs_to_process = [
                    job for job in jobs if job.get("refnr", "") not in completed_refnrs
                ]

                if self.verbose:
                    print("\n✓ Resuming from checkpoint:")
                    print(f"  - Already classified: {len(partial_results)} jobs")
                    print(f"  - Remaining to classify: {len(jobs_to_process)} jobs")
                    print(
                        f"  - Batch {checkpoint.get('current_batch', 0)}/{checkpoint.get('total_batches', 0)}"
                    )
            else:
                if self.verbose:
                    print(f"\nProcessing {len(jobs)} pre-loaded jobs...")
        elif self.session and not resume:
            # Delete checkpoint if user wants fresh start
            if self.session.has_checkpoint():
                self.session.delete_checkpoint()
                if self.verbose:
                    print("\n✓ Checkpoint deleted - starting fresh classification")
            if self.verbose:
                print(f"\nProcessing {len(jobs)} pre-loaded jobs...")
        else:
            if self.verbose:
                print(f"\nProcessing {len(jobs)} pre-loaded jobs...")

        # Process remaining jobs with LLM (or skip if all done)
        if jobs_to_process:
            newly_classified = self.process(jobs_to_process, **kwargs)
        else:
            newly_classified = []
            if self.verbose:
                print("\n✓ All jobs already classified - nothing to do!")

        # Combine partial results with newly classified
        classified_jobs = partial_results + newly_classified

        # Analyze and report
        if show_statistics:
            print_statistics(
                classified_jobs=classified_jobs,
                total_jobs=total_jobs,
                successful_fetches=len(classified_jobs),
            )

        return classified_jobs

    def generate_report(
        self, classified_jobs: list[dict], total_jobs: int, search_params: dict | None = None
    ) -> str:
        """
        Generate a text report of the analysis

        Args:
            classified_jobs: Classified job data
            total_jobs: Total number of jobs processed
            search_params: Optional search parameters for context

        Returns:
            Formatted text report
        """
        return generate_report(
            classified_jobs=classified_jobs,
            total_jobs=total_jobs,
            search_params=search_params or {},
        )
