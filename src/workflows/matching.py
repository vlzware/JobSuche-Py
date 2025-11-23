"""
Matching workflow - match jobs against your profile

This workflow matches jobs against your personal criteria, which can include:
- Your CV (skills, experience) - what you CAN do
- Perfect job description - what you WANT to do
- Both combined (recommended for best results)

Results are classified as Excellent Match, Good Match, or Poor Match.
By default, only Excellent and Good matches are returned.
"""

from ..exceptions import WorkflowConfigurationError
from .base import BaseWorkflow


class MatchingWorkflow(BaseWorkflow):
    """
    Match jobs against your profile (CV and/or ideal job description)

    This workflow evaluates jobs based on your personal criteria:
    - CV only: Matches based on your skills and experience
    - Perfect job description only: Matches based on what you want
    - Both (recommended): Considers both your abilities and preferences

    Jobs are classified as:
    - Excellent Match: Strong alignment with your profile
    - Good Match: Reasonable fit with some gaps
    - Poor Match: Significant misalignment

    By default, only Excellent and Good matches are returned.

    Example use cases:
    - "Find jobs I'm qualified for" (CV only)
    - "Find my dream job" (perfect job description only)
    - "Find jobs I'm qualified for AND want" (both - recommended)
    """

    def process(
        self,
        jobs: list[dict],
        cv_content: str | None = None,
        perfect_job_description: str | None = None,
        return_only_matches: bool = True,
        batch_size: int | None = None,
        extra_api_params: dict | None = None,
    ) -> list[dict]:
        """
        Process jobs using profile-based matching

        Args:
            jobs: List of jobs to classify
            cv_content: Your CV content (skills, experience)
            perfect_job_description: Description of your ideal job
            return_only_matches: If True, return only Excellent/Good matches (default: True)
            batch_size: Optional batch size (uses mega-batch if None)
            extra_api_params: Additional API parameters (e.g., {"reasoning": {"effort": "high"}})

        Returns:
            List of jobs with match classification (filtered if return_only_matches=True)

        Raises:
            WorkflowConfigurationError: If neither CV nor perfect job description provided
        """
        # Validate that at least one input is provided
        has_cv = cv_content and cv_content.strip()
        has_perfect_job = perfect_job_description and perfect_job_description.strip()

        if not has_cv and not has_perfect_job:
            raise WorkflowConfigurationError(
                "At least one of CV or perfect job description is required for matching workflow",
                workflow_type="matching",
            )

        # Delegate to LLM processor with unified matching method
        return self.llm_processor.classify_matching(
            jobs=jobs,
            cv_content=cv_content if has_cv else None,
            perfect_job_description=perfect_job_description if has_perfect_job else None,
            return_only_matches=return_only_matches,
            batch_size=batch_size,
            extra_api_params=extra_api_params,
        )
