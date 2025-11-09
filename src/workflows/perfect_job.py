"""
Perfect job workflow - find jobs matching a specific ideal role

This workflow simplifies classification to a binary decision: does this job
match my ideal role or not?
"""

from ..exceptions import WorkflowConfigurationError
from .base import BaseWorkflow


class PerfectJobWorkflow(BaseWorkflow):
    """
    Find jobs matching a "perfect job" description

    Instead of categorizing into multiple buckets, this workflow asks
    a simple question: "Is this my perfect job?"

    The LLM classifies each job as either:
    - Matching your perfect job description
    - Not matching (classified as "Andere")

    You can optionally filter to return ONLY the matching jobs.

    Example use case:
    - You know exactly what you want: "Industrial IoT with Python and embedded systems"
    - You want to ignore everything else
    - Focus only on the best matches
    """

    def process(
        self,
        jobs: list[dict],
        perfect_job_category: str | None = None,
        perfect_job_description: str | None = None,
        return_only_matches: bool = True,
        batch_size: int | None = None,
    ) -> list[dict]:
        """
        Process jobs using perfect job matching

        Args:
            jobs: List of jobs to classify
            perfect_job_category: Name of your perfect job (uses profile if None)
            perfect_job_description: Description of your perfect job (uses profile if None)
            return_only_matches: If True, return only matching jobs (default: True)
            batch_size: Optional batch size (uses mega-batch if None)

        Returns:
            List of jobs (filtered to matches if return_only_matches=True)
        """
        # Use profile settings if not explicitly provided
        if perfect_job_category is None or perfect_job_description is None:
            categories = self.user_profile.get_categories()
            definitions = self.user_profile.get_category_definitions()

            if not categories or len(categories) > 2:
                raise WorkflowConfigurationError(
                    "Perfect job workflow requires exactly one category "
                    "(plus 'Andere'). Set via user_profile.set_perfect_job_category() "
                    "or pass perfect_job_category and perfect_job_description parameters.",
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
            perfect_job_category=perfect_job_category,
            perfect_job_description=perfect_job_description,
            return_only_matches=return_only_matches,
            batch_size=batch_size,
        )
