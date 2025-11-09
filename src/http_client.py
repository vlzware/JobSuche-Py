"""HTTP client abstraction for dependency injection and testability."""

from typing import Any

import requests


class HttpClient:
    """
    HTTP client wrapper for making requests.

    This abstraction enables:
    - Dependency injection for testing
    - Easy mocking in unit tests
    - Centralized HTTP configuration
    """

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: Any | None = None,
        timeout: float | None = None,
        **kwargs,
    ) -> requests.Response:
        """
        Send a GET request.

        Args:
            url: URL to request
            headers: Optional HTTP headers
            params: Optional query parameters
            timeout: Optional request timeout in seconds
            **kwargs: Additional arguments to pass to requests.get()

        Returns:
            requests.Response object
        """
        return requests.get(url, headers=headers, params=params, timeout=timeout, **kwargs)

    def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        data: Any | None = None,
        timeout: float | None = None,
        **kwargs,
    ) -> requests.Response:
        """
        Send a POST request.

        Args:
            url: URL to request
            headers: Optional HTTP headers
            json: Optional JSON data to send
            data: Optional form data to send
            timeout: Optional request timeout in seconds
            **kwargs: Additional arguments to pass to requests.post()

        Returns:
            requests.Response object
        """
        return requests.post(url, headers=headers, json=json, data=data, timeout=timeout, **kwargs)


# Create a default instance for backward compatibility
default_http_client = HttpClient()
