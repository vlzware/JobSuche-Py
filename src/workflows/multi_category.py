"""
Multi-category workflow - standard job classification into multiple categories

This is the default workflow, matching the original behavior of classifying
jobs into multiple predefined categories.
"""

from .base import BaseWorkflow


class MultiCategoryWorkflow(BaseWorkflow):
    """
    Classify jobs into multiple categories

    This workflow assigns each job to one or more categories from a
    predefined list. It's useful for market analysis and understanding
    the distribution of different technologies/roles.

    Example use cases:
    - Market survey: "What technologies are in demand?"
    - Skill analysis: "How many Java vs Python jobs are there?"
    - Role distribution: "What percentage are management roles?"
    """

    def process(self, jobs: list[dict], batch_size: int | None = None) -> list[dict]:
        """
        Process jobs using multi-category classification

        Args:
            jobs: List of jobs to classify
            batch_size: Optional batch size (uses mega-batch if None)

        Returns:
            List of jobs with 'categories' field added
        """
        return self.llm_processor.classify_multi_category(
            jobs=jobs,
            categories=self.user_profile.get_categories(),
            category_definitions=self.user_profile.get_category_definitions(),
            batch_size=batch_size,
        )
