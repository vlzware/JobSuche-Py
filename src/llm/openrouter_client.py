"""
Unified OpenRouter API client

Handles all interactions with the OpenRouter API, including:
- Request building and sending
- Response parsing and validation
- Error handling
- Full response logging to session
"""

from typing import TYPE_CHECKING, Optional

from ..config import Config, config
from ..exceptions import OpenRouterAPIError
from ..http_client import HttpClient, default_http_client

if TYPE_CHECKING:
    from ..session import SearchSession


class OpenRouterClient:
    """
    Unified client for OpenRouter API interactions

    This class encapsulates all the common logic for calling OpenRouter:
    - Building requests with proper headers and auth
    - Making HTTP calls
    - Parsing responses
    - Error handling
    - Saving full responses to session for debugging
    """

    def __init__(
        self,
        api_key: str,
        http_client: HttpClient | None = None,
        config_obj: Config | None = None,
    ):
        """
        Initialize OpenRouter client

        Args:
            api_key: OpenRouter API key
            http_client: HTTP client for making requests (uses default if None)
            config_obj: Config object (uses global config if None)
        """
        self.api_key = api_key
        self.http_client = http_client or default_http_client
        self.config = config_obj or config

    def complete(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int | None = None,
        extra_params: dict | None = None,
        timeout: int = 60,
        session: Optional["SearchSession"] = None,
        interaction_label: str = "",
        batch_metadata: list[dict] | None = None,
    ) -> tuple[str, dict]:
        """
        Make a completion request to OpenRouter

        Args:
            prompt: The prompt/message to send to the LLM
            model: Model identifier (e.g., "google/gemini-2.5-flash")
            temperature: Sampling temperature (0.0-1.0+)
            max_tokens: Maximum tokens in response (None for model default)
            extra_params: Additional API parameters (e.g., {"reasoning": {"effort": "high"}})
            timeout: Request timeout in seconds
            session: Optional SearchSession for saving request/response
            interaction_label: Label for this interaction (e.g., "Batch 1/3", "Brainstorm")
            batch_metadata: Optional list of job metadata dicts for HTML export
                           (e.g., [{"refnr": "...", "titel": "...", "ort": "...", "arbeitgeber": "..."}])

        Returns:
            tuple of (content_string, full_response_dict)
                - content_string: The actual text response from the LLM
                - full_response_dict: Complete API response including metadata, usage, etc.

        Raises:
            OpenRouterAPIError: If API returns non-200 status
        """
        # Build request payload
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # Merge any extra API parameters
        if extra_params:
            payload.update(extra_params)

        # Make the request
        response = self.http_client.post(
            url=self.config.get_required("api.openrouter.endpoint"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/vlzware/JobSuche-Py",
                "X-Title": "JobSuche-Py",
            },
            json=payload,
            timeout=timeout,
        )

        # Check for errors
        if response.status_code != 200:
            error_msg = f"OpenRouter API error: {response.status_code} - {response.text}"
            raise OpenRouterAPIError(
                error_msg,
                status_code=response.status_code,
                response_text=response.text,
            )

        # Parse response
        full_response = response.json()
        content = full_response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Save to session if provided
        if session:
            session.save_llm_interaction(
                prompt=prompt,
                content=content,
                full_response=full_response,
                label=interaction_label,
                batch_metadata=batch_metadata,
            )

        return content, full_response
