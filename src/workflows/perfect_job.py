"""
Perfect job workflow - find jobs matching a specific ideal role

This workflow classifies jobs based on how well they match your perfect job
description. Results are categorized as Excellent Match, Good Match, or Andere.
"""

from ..exceptions import WorkflowConfigurationError
from .base import BaseWorkflow


class PerfectJobWorkflow(BaseWorkflow):
    """
    Find jobs matching a "perfect job" description

    This workflow evaluates jobs against your ideal role description and
    classifies them as:
    - Excellent Match: Very close to your perfect job description
    - Good Match: Aligns well but not perfectly
    - Andere: Doesn't match the criteria

    By default, only Excellent and Good matches are returned.

    Example use case:
    - You know exactly what you want: "Industrial IoT with Python and embedded systems"
    - Focus only on the best matches
    """

    def process(
        self,
        jobs: list[dict],
        perfect_job_description: str | None = None,
        return_only_matches: bool = True,
        batch_size: int | None = None,
    ) -> list[dict]:
        """
        Process jobs using perfect job matching

        Args:
            jobs: List of jobs to classify
            perfect_job_description: Description of your perfect job (uses profile if None)
            return_only_matches: If True, return only Excellent/Good matches (default: True)
            batch_size: Optional batch size (uses mega-batch if None)

        Returns:
            List of jobs with match classification (filtered if return_only_matches=True)
        """
        # Use profile settings if not explicitly provided
        if perfect_job_description is None:
            categories = self.user_profile.get_categories()
            definitions = self.user_profile.get_category_definitions()

            if not categories or len(categories) > 2:
                raise WorkflowConfigurationError(
                    "Perfect job workflow requires exactly one category "
                    "(plus 'Andere'). Set via user_profile.set_perfect_job_category() "
                    "or pass perfect_job_description parameter.",
                    workflow_type="perfect-job",
                )

            # Get the first non-"Andere" category
            perfect_job_category = next(
                (cat for cat in categories if cat.lower() != "andere"), categories[0]
            )
            perfect_job_description = definitions.get(perfect_job_category, "")

            if not perfect_job_description:
                raise WorkflowConfigurationError(
                    f"No description provided for '{perfect_job_category}'. "
                    "Set via user_profile.set_perfect_job_category() or pass "
                    "perfect_job_description parameter.",
                    workflow_type="perfect-job",
                )

        return self.llm_processor.classify_perfect_job(
            jobs=jobs,
            perfect_job_description=perfect_job_description,
            return_only_matches=return_only_matches,
            batch_size=batch_size,
        )
