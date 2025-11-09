"""
CV-based workflow - match jobs against your CV

This workflow uses your CV to determine job compatibility. The LLM analyzes
both the job description and your experience to assess fit.
"""

from ..exceptions import WorkflowConfigurationError
from .base import BaseWorkflow


class CVBasedWorkflow(BaseWorkflow):
    """
    Match jobs against your CV

    This workflow goes beyond keyword matching. It uses the LLM to:
    1. Understand your experience from your CV
    2. Analyze each job's requirements
    3. Assess the match quality

    Jobs are classified as:
    - Excellent Match: Requirements closely align with your experience
    - Good Match: Within your domain but requires some growth
    - Poor Match: Requires significantly different skills

    You can optionally filter to return only good matches.

    Example use case:
    - Your CV defines your expertise better than any category list
    - You want personalized matching beyond keywords
    - You want to focus on realistic opportunities
    """

    def process(
        self,
        jobs: list[dict],
        cv_content: str | None = None,
        return_only_matches: bool = True,
        batch_size: int | None = None,
    ) -> list[dict]:
        """
        Process jobs using CV-based matching

        Args:
            jobs: List of jobs to classify
            cv_content: Your CV content (uses profile CV if None)
            return_only_matches: If True, return only Excellent/Good matches (default: True)
            batch_size: Optional batch size (uses mega-batch if None)

        Returns:
            List of jobs with CV match classification
        """
        # Use profile CV if not explicitly provided
        if cv_content is None:
            if not self.user_profile.has_cv():
                raise WorkflowConfigurationError(
                    "CV content required. Either pass cv_content parameter "
                    "or initialize UserProfile with cv_path.",
                    workflow_type="cv-based",
                )
            cv_content = self.user_profile.get_cv_content()

        # Ensure cv_content is not None after all checks
        if cv_content is None:
            raise WorkflowConfigurationError(
                "CV content is unexpectedly None after loading from profile",
                workflow_type="cv-based",
            )

        return self.llm_processor.classify_cv_based(
            jobs=jobs,
            cv_content=cv_content,
            return_only_matches=return_only_matches,
            batch_size=batch_size,
        )
