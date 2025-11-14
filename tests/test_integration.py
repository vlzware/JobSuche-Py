"""
Integration tests for the scraper workflow

These tests verify that multiple components work together correctly:
1. Config -> HTTP Client -> Scraper workflow
2. End-to-end fetching and parsing
"""

from unittest.mock import Mock

from src.config.loader import Config
from src.scraper import fetch_arbeitsagentur_details, fetch_external_details


class TestScraperIntegration:
    """Test complete scraper workflows"""

    def test_external_fetch_and_parse_workflow(self, load_fixture):
        """Should fetch HTML via HTTP client and parse it correctly"""
        # Setup mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = load_fixture("external_page_with_json_ld.html")
        mock_client.get.return_value = mock_response

        # Setup config
        config = Config(
            {
                "scraper": {
                    "headers": {"user_agent": "Test/1.0"},
                    "html_cleanup": {"remove_tags": ["script", "style", "nav"]},
                    "external": {
                        "content_selectors": {
                            "primary": "main",
                            "secondary": "article",
                            "content_pattern": "(content|job|detail)",
                            "id_pattern": "(content|job|detail|main)",
                        }
                    },
                },
                "api": {"timeouts": {"external_url": 15}},
            }
        )

        # Execute workflow
        result = fetch_external_details(
            external_url="https://techcorp.de/jobs/123", http_client=mock_client, config_obj=config
        )

        # Verify HTTP was called with correct params
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["timeout"] == 15
        assert "User-Agent" in call_kwargs["headers"]

        # Verify parsing succeeded
        assert result["success"]
        assert result["extraction_method"] == "json_ld"
        assert "Senior Java Developer" in result["text"]
        assert result["domain"] == "techcorp.de"

    def test_arbeitsagentur_fetch_and_parse_workflow(self, load_fixture):
        """Should fetch and parse Arbeitsagentur page correctly"""
        # Setup mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = load_fixture("arbeitsagentur_page.html")
        mock_client.get.return_value = mock_response

        # Setup config
        config = Config(
            {
                "scraper": {
                    "headers": {"user_agent": "Test/1.0"},
                    "html_cleanup": {"remove_tags": ["script", "style", "nav", "header", "footer"]},
                    "arbeitsagentur": {"content_selector": "jb-steadetail-beschreibung"},
                },
                "api": {"timeouts": {"arbeitsagentur_details": 10}},
            }
        )

        # Execute workflow
        result = fetch_arbeitsagentur_details(
            refnr="123456789", http_client=mock_client, config_obj=config
        )

        # Verify HTTP was called correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "arbeitsagentur.de" in call_args[0][0]
        assert "123456789" in call_args[0][0]

        # Verify parsing succeeded
        assert result["success"]
        assert result["extraction_method"] == "css_selector"
        assert "Software Developer" in result["text"]

    def test_workflow_handles_http_errors_gracefully(self):
        """Should handle HTTP errors without crashing"""
        # Setup mock that returns error
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 503
        mock_client.get.return_value = mock_response

        config = Config(
            {
                "scraper": {"headers": {"user_agent": "Test"}},
                "api": {"timeouts": {"external_url": 15}},
            }
        )

        # Execute workflow
        result = fetch_external_details(
            external_url="https://example.com/job", http_client=mock_client, config_obj=config
        )

        # Should return structured error
        assert not result["success"]
        assert "HTTP 503" in result["error"]
        assert result["source"] == "external"

    def test_workflow_handles_network_exceptions(self):
        """Should handle network exceptions gracefully"""
        # Setup mock that raises exception
        mock_client = Mock()
        mock_client.get.side_effect = Exception("Connection timeout")

        config = Config(
            {
                "scraper": {"headers": {"user_agent": "Test"}},
                "api": {"timeouts": {"external_url": 15}},
            }
        )

        # Execute workflow
        result = fetch_external_details(
            external_url="https://example.com/job", http_client=mock_client, config_obj=config
        )

        # Should return structured error
        assert not result["success"]
        assert "error" in result
        assert result["warning"] == "EXCEPTION"

    def test_fallback_extraction_strategies(self, load_fixture):
        """Should try multiple extraction strategies"""
        # Page with main tag (no JSON-LD)
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = load_fixture("external_page_with_main.html")
        mock_client.get.return_value = mock_response

        config = Config(
            {
                "scraper": {
                    "headers": {"user_agent": "Test"},
                    "html_cleanup": {
                        "remove_tags": ["script", "style", "nav"],
                        "remove_classes": "(nav|menu|sidebar)",
                    },
                    "external": {
                        "content_selectors": {
                            "primary": "main",
                            "secondary": "article",
                            "content_pattern": "(content|job|detail)",
                            "id_pattern": "(content|job|detail|main)",
                        }
                    },
                },
                "api": {"timeouts": {"external_url": 15}},
            }
        )

        result = fetch_external_details(
            external_url="https://startup.com/job", http_client=mock_client, config_obj=config
        )

        # Should succeed with CSS selector fallback
        assert result["success"]
        assert result["extraction_method"] == "css_selector"
        assert "Python Developer" in result["text"]


# Note: TestConfigPropagation class removed - already covered in test_scraper.py
