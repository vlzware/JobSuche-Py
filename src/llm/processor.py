"""
LLM processor - handles all LLM interactions for job classification

This module encapsulates all LLM API calls, providing a clean interface
for different classification strategies.
"""

import os
from typing import TYPE_CHECKING, Optional

from ..classifier import classify_jobs_batch, classify_jobs_mega_batch
from ..config import config
from ..logging_config import get_module_logger
from ..prompts import (
    CV_CLASSIFICATION_CRITERIA,
    CV_PROFILE_TEMPLATE,
    load_custom_prompts,
)

logger = get_module_logger("llm_processor")

if TYPE_CHECKING:
    from ..session import SearchSession


class LLMProcessor:
    """
    Handles all LLM-based job classification

    This class provides a unified interface for different classification
    approaches (mega-batch, batch, custom prompts, etc.)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        session: Optional["SearchSession"] = None,
        verbose: bool = True,
    ):
        """
        Initialize the LLM processor

        Args:
            api_key: OpenRouter API key (uses OPENROUTER_API_KEY env var if None)
            model: Model to use for classification (defaults to value from llm_config.yaml)
            session: Optional SearchSession for saving LLM interactions
            verbose: Whether to print progress messages
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. "
                "Set OPENROUTER_API_KEY environment variable or pass api_key parameter."
            )

        if model is None:
            model = config.get("llm.models.default", "google/gemini-2.5-flash")

        self.model = model
        self.session = session
        self.verbose = verbose

        # Load custom prompts if available
        self.custom_prompts = load_custom_prompts()

    def classify_multi_category(
        self,
        jobs: list[dict],
        categories: list[str],
        category_definitions: dict[str, str] | None = None,
        batch_size: int | None = None,
        extra_api_params: dict | None = None,
    ) -> list[dict]:
        """
        Classify jobs into multiple categories

        This is the standard classification workflow - assigns each job
        to one or more categories from the provided list.

        Args:
            jobs: List of jobs to classify
            categories: List of category names
            category_definitions: Optional category descriptions for better accuracy
            batch_size: If specified, use batch mode instead of mega-batch
            extra_api_params: Additional API parameters (e.g., reasoning effort)

        Returns:
            List of jobs with 'categories' field added
        """
        logger.info(f"Classifying jobs using {self.model}...")
        logger.info(f"  Categories: {', '.join(categories)}")

        # Use mega-batch by default, or smaller batches if requested
        if batch_size:
            logger.info(f"  Mode: Batch processing ({batch_size} jobs per request)")

            return classify_jobs_batch(
                jobs=jobs,
                categories=categories,
                api_key=self.api_key,
                model=self.model,
                batch_size=batch_size,
                verbose=self.verbose,
                extra_api_params=extra_api_params,
                session=self.session,
                category_definitions=category_definitions,
            )
        else:
            logger.info(f"  Mode: Mega-batch (all {len(jobs)} jobs in ONE request)")

            return classify_jobs_mega_batch(
                jobs=jobs,
                categories=categories,
                api_key=self.api_key,
                model=self.model,
                verbose=self.verbose,
                extra_api_params=extra_api_params,
                session=self.session,
                category_definitions=category_definitions,
            )

    def classify_perfect_job(
        self,
        jobs: list[dict],
        perfect_job_description: str,
        return_only_matches: bool = False,
        batch_size: int | None = None,
    ) -> list[dict]:
        """
        Classify jobs based on how well they match a "perfect job" description

        This is a specialized workflow for finding jobs that match a specific,
        detailed description of your ideal role. Jobs are classified as:
        - Excellent Match: Very close to the perfect job description
        - Good Match: Aligns well but not perfectly
        - Andere: Doesn't match the criteria

        Args:
            jobs: List of jobs to classify
            perfect_job_description: Detailed description of your ideal job
            return_only_matches: If True, return only Excellent and Good matches (default: False)
            batch_size: If specified, use batch mode instead of mega-batch

        Returns:
            List of jobs with 'categories' field (filtered if return_only_matches=True)
        """
        # Use "Andere" as fallback for consistency with other workflows
        categories = ["Excellent Match", "Good Match", "Andere"]
        category_definitions = {
            "Excellent Match": perfect_job_description,
        }

        logger.info("Finding jobs matching your perfect job description")
        if return_only_matches:
            logger.info("  Will return only Excellent and Good matches")

        classified = self.classify_multi_category(
            jobs=jobs,
            categories=categories,
            category_definitions=category_definitions,
            batch_size=batch_size,
        )

        # Filter to only good matches if requested
        if return_only_matches:
            matches = [
                job
                for job in classified
                if any(
                    cat in job.get("categories", []) for cat in ["Excellent Match", "Good Match"]
                )
            ]

            excellent = sum(1 for job in matches if "Excellent Match" in job.get("categories", []))
            good = sum(1 for job in matches if "Good Match" in job.get("categories", []))
            logger.info(f"✓ Found {len(matches)}/{len(classified)} matching jobs")
            logger.info(f"  {excellent} Excellent, {good} Good")

            return matches

        return classified

    def classify_cv_based(
        self,
        jobs: list[dict],
        cv_content: str,
        return_only_matches: bool = False,
        batch_size: int | None = None,
    ) -> list[dict]:
        """
        Classify jobs based on CV match

        Uses your CV to determine if jobs are a good fit. The LLM analyzes
        both the job description and your CV to assess compatibility.

        Args:
            jobs: List of jobs to classify
            cv_content: Your CV content (markdown or text) - full content is sent
            return_only_matches: If True, return only jobs that match your CV
            batch_size: If specified, use batch mode instead of mega-batch

        Returns:
            List of jobs with 'categories' field and 'cv_match_score' (filtered if requested)
        """
        # Define categories for CV-based matching
        categories = ["Excellent Match", "Good Match", "Poor Match"]

        # Note CV size (larger documents use more tokens)
        cv_length = len(cv_content)
        logger.info("Matching jobs against your CV...")
        logger.info(f"  CV length: {cv_length:,} characters")
        logger.info("  Note: Larger documents will consume more tokens")

        # Build CV-based classification guidance
        # Split into two parts to avoid CV duplication:
        # 1. CV profile (shown once via category definition)
        # 2. Classification criteria (embedded in the CV profile)

        # Use custom prompt if provided, otherwise use default split templates
        custom_cv_template = self.custom_prompts.get("cv_matching")

        if custom_cv_template:
            # Use legacy combined template for custom prompts
            cv_guidance = custom_cv_template.format(cv_content=cv_content)
            # Assign to only ONE category to avoid duplication
            category_definitions = {
                "Excellent Match": cv_guidance,
            }
        else:
            # Use new split template approach
            # Format CV profile with actual content
            cv_profile = CV_PROFILE_TEMPLATE.format(cv_content=cv_content)
            # Combine profile + criteria into a single guidance string
            cv_guidance = cv_profile + "\n" + CV_CLASSIFICATION_CRITERIA

            # CRITICAL: Assign to only ONE category to prevent duplication
            # build_category_guidance() will add this once with "IMPORTANT:" prefix
            category_definitions = {
                "Excellent Match": cv_guidance,
            }

        if return_only_matches:
            logger.info("  Will return only Excellent and Good matches")

        classified = self.classify_multi_category(
            jobs=jobs,
            categories=categories,
            category_definitions=category_definitions,
            batch_size=batch_size,
        )

        # Filter to only good matches if requested
        if return_only_matches:
            matches = [
                job
                for job in classified
                if any(
                    cat in job.get("categories", []) for cat in ["Excellent Match", "Good Match"]
                )
            ]

            excellent = sum(1 for job in matches if "Excellent Match" in job.get("categories", []))
            good = sum(1 for job in matches if "Good Match" in job.get("categories", []))
            logger.info(f"✓ Found {len(matches)}/{len(classified)} matching jobs")
            logger.info(f"  {excellent} Excellent, {good} Good")

            return matches

        return classified

    def get_model(self) -> str:
        """Get the current model name"""
        return self.model

    def set_model(self, model: str) -> None:
        """Change the LLM model"""
        self.model = model
