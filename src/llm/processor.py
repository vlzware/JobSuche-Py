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
            model = config.get_required("llm.models.default")

        self.model = model
        self.session = session
        self.verbose = verbose

        # Load custom prompts if available
        self.custom_prompts = load_custom_prompts()

    def _classify_internal(
        self,
        jobs: list[dict],
        categories: list[str],
        category_definitions: dict[str, str] | None = None,
        batch_size: int | None = None,
        extra_api_params: dict | None = None,
    ) -> list[dict]:
        """
        Internal classification method used by matching workflow

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

    def classify_matching(
        self,
        jobs: list[dict],
        cv_content: str | None = None,
        perfect_job_description: str | None = None,
        return_only_matches: bool = False,
        batch_size: int | None = None,
        extra_api_params: dict | None = None,
    ) -> list[dict]:
        """
        Classify jobs based on match to your profile (CV and/or perfect job description)

        This unified matching method handles three scenarios:
        1. CV only: Match based on skills and experience
        2. Perfect job description only: Match based on desired role
        3. Both (recommended): Match based on both capabilities and preferences

        Jobs are classified as:
        - Excellent Match: Strong alignment with your profile
        - Good Match: Reasonable fit with some gaps
        - Poor Match: Significant misalignment

        Args:
            jobs: List of jobs to classify
            cv_content: Your CV content (optional)
            perfect_job_description: Description of your ideal job (optional)
            return_only_matches: If True, return only Excellent and Good matches (default: False)
            batch_size: If specified, use batch mode instead of mega-batch
            extra_api_params: Additional API parameters (e.g., {"reasoning": {"effort": "high"}})

        Returns:
            List of jobs with 'categories' field (filtered if return_only_matches=True)

        Raises:
            ValueError: If neither CV nor perfect job description provided
        """
        # Define categories for matching
        categories = ["Excellent Match", "Good Match", "Poor Match"]

        # Validate at least one input
        has_cv = cv_content and cv_content.strip()
        has_perfect_job = perfect_job_description and perfect_job_description.strip()

        if not has_cv and not has_perfect_job:
            raise ValueError(
                "At least one of cv_content or perfect_job_description must be provided"
            )

        # Build guidance based on what's provided
        guidance_parts = []

        logger.info("Matching jobs against your profile...")

        if has_cv:
            # Use custom prompt if provided, otherwise use default templates
            custom_cv_template = self.custom_prompts.get("cv_matching")

            if custom_cv_template:
                # Use legacy combined template for custom prompts
                cv_guidance = custom_cv_template.format(cv_content=cv_content)
            else:
                # Use split template approach
                cv_profile = CV_PROFILE_TEMPLATE.format(cv_content=cv_content)
                cv_guidance = cv_profile + "\n" + CV_CLASSIFICATION_CRITERIA

            guidance_parts.append(cv_guidance)

            cv_length = len(cv_content) if cv_content else 0
            logger.info(f"  CV provided: {cv_length:,} characters")

        if has_perfect_job:
            guidance_parts.append(f"IDEAL JOB CRITERIA:\n{perfect_job_description}")
            pj_length = len(perfect_job_description) if perfect_job_description else 0
            logger.info(f"  Perfect job description provided: {pj_length:,} characters")

        # Combine all guidance into one string for "Excellent Match" category
        # This prevents duplication in the prompt
        combined_guidance = "\n\n".join(guidance_parts)
        category_definitions = {
            "Excellent Match": combined_guidance,
        }

        if return_only_matches:
            logger.info("  Will return only Excellent and Good matches")

        # Classify using the internal classification method
        classified = self._classify_internal(
            jobs=jobs,
            categories=categories,
            category_definitions=category_definitions,
            batch_size=batch_size,
            extra_api_params=extra_api_params,
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
