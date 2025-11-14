"""
Tests for the HttpClient abstraction

These tests verify that the HttpClient wrapper correctly delegates to requests
and supports dependency injection for testing.
"""

from unittest.mock import Mock, patch

from src.http_client import HttpClient


class TestHttpClient:
    """Test HttpClient wrapper functionality"""

    @patch("src.http_client.requests.get")
    def test_get_basic_request(self, mock_get):
        """Should make a basic GET request via requests.get"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = HttpClient()
        response = client.get("https://example.com")

        mock_get.assert_called_once_with(
            "https://example.com", headers=None, params=None, timeout=None
        )
        assert response == mock_response

    @patch("src.http_client.requests.get")
    def test_get_with_headers(self, mock_get):
        """Should pass headers to requests.get"""
        mock_get.return_value = Mock()

        client = HttpClient()
        headers = {"User-Agent": "Test/1.0", "Accept": "text/html"}
        client.get("https://example.com", headers=headers)

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["headers"] == headers

    @patch("src.http_client.requests.get")
    def test_get_with_params(self, mock_get):
        """Should pass query parameters to requests.get"""
        mock_get.return_value = Mock()

        client = HttpClient()
        params = {"page": 1, "size": 100}
        client.get("https://api.example.com", params=params)

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"] == params

    @patch("src.http_client.requests.get")
    def test_get_with_timeout(self, mock_get):
        """Should pass timeout to requests.get"""
        mock_get.return_value = Mock()

        client = HttpClient()
        client.get("https://example.com", timeout=30)

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 30

    @patch("src.http_client.requests.get")
    def test_get_with_additional_kwargs(self, mock_get):
        """Should pass additional kwargs to requests.get"""
        mock_get.return_value = Mock()

        client = HttpClient()
        client.get("https://example.com", verify=False, allow_redirects=True)

        call_kwargs = mock_get.call_args[1]
        assert not call_kwargs["verify"]
        assert call_kwargs["allow_redirects"]

    @patch("src.http_client.requests.post")
    def test_post_basic_request(self, mock_post):
        """Should make a basic POST request via requests.post"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        client = HttpClient()
        response = client.post("https://api.example.com")

        mock_post.assert_called_once()
        assert response == mock_response

    @patch("src.http_client.requests.post")
    def test_post_with_json(self, mock_post):
        """Should pass JSON payload to requests.post"""
        mock_post.return_value = Mock()

        client = HttpClient()
        json_data = {"key": "value", "number": 42}
        client.post("https://api.example.com", json=json_data)

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"] == json_data

    @patch("src.http_client.requests.post")
    def test_post_with_form_data(self, mock_post):
        """Should pass form data to requests.post"""
        mock_post.return_value = Mock()

        client = HttpClient()
        form_data = {"username": "test", "password": "secret"}
        client.post("https://api.example.com", data=form_data)

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["data"] == form_data

    @patch("src.http_client.requests.post")
    def test_post_with_headers_and_timeout(self, mock_post):
        """Should pass headers and timeout to requests.post"""
        mock_post.return_value = Mock()

        client = HttpClient()
        headers = {"Authorization": "Bearer token"}
        client.post("https://api.example.com", headers=headers, timeout=60)

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"] == headers
        assert call_kwargs["timeout"] == 60
