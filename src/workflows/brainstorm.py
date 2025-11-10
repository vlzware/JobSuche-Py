"""
Brainstorm workflow - discover potential job titles for Arbeitsagentur search

This workflow helps users discover "Berufsbezeichnungen" (job titles) they might
not know about by combining their CV with an optional description of what motivates them.
The LLM brainstorms relevant job titles that can then be used with the
Arbeitsagentur API.
"""

from typing import TYPE_CHECKING

from ..config import config
from ..exceptions import OpenRouterAPIError, WorkflowConfigurationError
from ..http_client import default_http_client
from ..llm.openrouter_client import OpenRouterClient
from ..prompts.templates import (
    BRAINSTORM_PROMPT_CV_ONLY_TEMPLATE,
    BRAINSTORM_PROMPT_MOTIVATION_ONLY_TEMPLATE,
    BRAINSTORM_PROMPT_TEMPLATE,
)

if TYPE_CHECKING:
    from ..session import SearchSession


class BrainstormWorkflow:
    """
    Brainstorm potential job titles based on CV and optional motivation

    Unlike other workflows, this doesn't search or classify jobs.
    Instead, it helps discover relevant "Berufsbezeichnungen" to use
    with the --was parameter in other workflows.

    The workflow:
    1. Takes CV and optional motivation description as input
    2. Uses LLM to brainstorm relevant job titles
    3. Returns suggestions with explanations and confidence levels
    4. Includes disclaimer about Arbeitsagentur's inherent variability

    Output format:
    - Job title ("Berufsbezeichnung")
    - Why it might match
    - Confidence level (High/Medium/Low)
    - Related variations (companies use different titles)

    Note: For better results, consider using a more capable model
    (e.g., claude-3-7-sonnet, gpt-4, gemini-2.0-flash-thinking-exp)
    """

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        session: "SearchSession | None" = None,
        verbose: bool = True,
    ):
        """
        Initialize the brainstorm workflow

        Args:
            api_key: OpenRouter API key
            model: LLM model to use (defaults to config value)
            session: Optional SearchSession for saving artifacts
            verbose: Whether to print progress messages
        """
        self.api_key = api_key
        self.model = model or config.get("llm.models.default", "google/gemini-2.5-flash")
        self.session = session
        self.verbose = verbose

    def run(
        self,
        cv_content: str | None = None,
        motivation_description: str | None = None,
    ) -> str:
        """
        Run the brainstorming workflow

        Args:
            cv_content: Optional user's CV content
            motivation_description: Optional user's description of what moves them

        Returns:
            Formatted text with job title suggestions

        Raises:
            WorkflowConfigurationError: If both CV and motivation are missing
        """
        # Validate that at least one input is provided
        has_cv = cv_content and cv_content.strip()
        has_motivation = motivation_description and motivation_description.strip()

        if not has_cv and not has_motivation:
            raise WorkflowConfigurationError(
                "At least one of CV or motivation description is required for brainstorming",
                workflow_type="brainstorm",
            )

        if self.verbose:
            print("\n" + "=" * 80)
            print("BRAINSTORMING JOB TITLES")
            print("=" * 80)
            print()
            if has_cv and cv_content is not None:
                print(f"CV length: {len(cv_content)} characters")
            else:
                print("CV: Not provided")
            if has_motivation and motivation_description is not None:
                print(f"Motivation length: {len(motivation_description)} characters")
            else:
                print("Motivation: Not provided")
            print(f"Using model: {self.model}")

            # Show hint about better models
            default_model = config.get("llm.models.default", "google/gemini-2.5-flash")
            if self.model == default_model:
                print("\n💡 Tip: For better brainstorming results, you may try different")
                print("   or more capable model with --model")

            print("\nGenerating suggestions...\n")

        # Build the prompt - use appropriate template based on what's provided
        if has_cv and has_motivation:
            # Both CV and motivation provided
            prompt = BRAINSTORM_PROMPT_TEMPLATE.format(
                cv_content=cv_content,
                motivation_description=motivation_description,
            )
        elif has_cv:
            # Only CV provided
            prompt = BRAINSTORM_PROMPT_CV_ONLY_TEMPLATE.format(
                cv_content=cv_content,
            )
        else:
            # Only motivation provided
            prompt = BRAINSTORM_PROMPT_MOTIVATION_ONLY_TEMPLATE.format(
                motivation_description=motivation_description,
            )

        # Call the LLM via unified OpenRouter client
        try:
            client = OpenRouterClient(api_key=self.api_key, http_client=default_http_client)

            suggestions, _full_response = client.complete(
                prompt=prompt,
                model=self.model,
                temperature=config.get("llm.inference.temperature", 0.7),
                max_tokens=4000,
                timeout=config.get("api.timeouts.classification", 60),
                session=self.session,
                interaction_label="brainstorm",
            )

            if not suggestions or not suggestions.strip():
                raise WorkflowConfigurationError(
                    "LLM returned empty response",
                    workflow_type="brainstorm",
                )

            return suggestions

        except OpenRouterAPIError:
            # Re-raise API errors as-is
            raise
        except Exception as e:
            if self.verbose:
                print(f"Error during brainstorming: {e}")
            raise WorkflowConfigurationError(
                f"Failed to generate suggestions: {e}",
                workflow_type="brainstorm",
            ) from e

    def format_output(self, suggestions: str) -> str:
        """
        Format the suggestions with disclaimer as markdown

        Args:
            suggestions: Raw LLM suggestions

        Returns:
            Formatted output with disclaimer
        """
        disclaimer = """# Job Title Brainstorming Results

## Important Disclaimer

These suggestions are meant to help you explore job titles you might not have
considered. However, please keep in mind:

- The Arbeitsagentur job listings are created by companies themselves
- Companies use different job titles for the same role
- There will be variations, unexpected descriptions, and mismatches
- The same job may appear under multiple categories (e.g., "Softwareentwickler",
  "Anwendungsentwickler", "Java-Entwickler" for the same position)

**These are just ideas to get you started - not definitive answers!**

---

## Job Title Suggestions

"""
        usage_hint = """

---

## How to Use These Suggestions

Use these job titles with the `--was` parameter in your searches:

### Examples:

```bash
python main.py --workflow cv-based --was "Softwareentwickler" --wo "Berlin" --cv cv.md

python main.py --workflow perfect-job --was "Backend Developer" --wo "München" \\
    --perfect-job-category "Dream Job" \\
    --perfect-job-description motivation.txt
```

**Tip:** Try multiple variations and combinations to get the best results!
"""

        return disclaimer + suggestions + usage_hint
