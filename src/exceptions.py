"""
Custom exceptions for JobSuche-Py
"""


class JobSucheError(Exception):
    """Base exception for all JobSuche errors"""

    pass


class TruncationError(JobSucheError):
    """Raised when job text is truncated (job-level failure)"""

    def __init__(self, job_id: str, original_length: int, truncated_length: int):
        self.job_id = job_id
        self.original_length = original_length
        self.truncated_length = truncated_length
        self.loss = original_length - truncated_length

        super().__init__(
            f"Job '{job_id}' truncated: {original_length} → {truncated_length} chars "
            f"(loss: {self.loss} chars)"
        )


class ScrapingError(JobSucheError):
    """Web scraping errors"""

    pass


class ClassificationError(JobSucheError):
    """LLM classification errors"""

    pass


class LLMDataIntegrityError(ClassificationError):
    """
    Raised when LLM returns data that fails validation checks.

    This indicates issues like:
    - Missing or incomplete results (jobs missing from batch)
    - Incorrectly ordered results
    - Data that doesn't match expected structure

    This is often due to context window limits, model failures, or inherent LLM randomness.
    """

    def __init__(
        self,
        message: str,
        expected_count: int | None = None,
        actual_count: int | None = None,
        missing_indices: list[int] | None = None,
    ):
        self.expected_count = expected_count
        self.actual_count = actual_count
        self.missing_indices = missing_indices
        super().__init__(message)


class LLMResponseError(ClassificationError):
    """
    Raised when LLM returns a response that cannot be parsed.

    This includes:
    - Malformed JSON
    - Missing required structure elements
    - Invalid response format

    This is typically due to model confusion or context window issues.
    """

    def __init__(self, message: str, raw_response: str | None = None):
        self.raw_response = raw_response
        super().__init__(message)


class OpenRouterAPIError(ClassificationError):
    """
    Raised when OpenRouter API returns an error response.

    Includes structured information about the failure to enable better user guidance.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(message)

    def get_user_guidance(self) -> str:
        """Get user-friendly guidance based on status code"""
        if self.status_code == 401:
            return (
                "Authentication failed. Please check your OpenRouter API key.\n"
                "Get a key at: https://openrouter.ai/keys"
            )
        elif self.status_code == 402:
            return "Insufficient credits. Please add credits to your OpenRouter account."
        elif self.status_code == 429:
            return (
                "Rate limit exceeded. Please:\n"
                "  - Wait a few moments and try again\n"
                "  - Use a smaller batch size (--batch-size parameter)\n"
                "  - Consider upgrading your OpenRouter plan"
            )
        elif self.status_code == 503:
            return (
                "OpenRouter service is temporarily unavailable.\nPlease try again in a few moments."
            )
        elif self.status_code and self.status_code >= 500:
            return (
                "OpenRouter server error. This is usually temporary.\n"
                "Please try again in a few moments."
            )
        else:
            return "Please check your OpenRouter configuration and try again."


class WorkflowConfigurationError(JobSucheError):
    """
    Raised when workflow is misconfigured.

    This includes:
    - Missing required parameters
    - Invalid parameter combinations
    - Invalid category selections
    """

    def __init__(self, message: str, workflow_type: str | None = None):
        self.workflow_type = workflow_type
        super().__init__(message)


class EmptyJobContentError(ClassificationError):
    """
    Raised when a job has no content to classify.

    This typically indicates a problem with scraping or data extraction.
    """

    def __init__(self, message: str, job_id: str | None = None):
        self.job_id = job_id
        super().__init__(message)


class APIError(JobSucheError):
    """Arbeitsagentur API errors"""

    pass


class ConfigurationError(JobSucheError):
    """
    Raised when required configuration values are missing or invalid.

    This ensures the config file is the single source of truth - missing required
    values are caught early rather than silently falling back to hardcoded defaults.
    """

    def __init__(self, message: str, config_key: str | None = None):
        self.config_key = config_key
        if config_key:
            super().__init__(f"Configuration error for '{config_key}': {message}")
        else:
            super().__init__(f"Configuration error: {message}")
