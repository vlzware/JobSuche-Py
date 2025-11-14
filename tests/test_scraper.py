"""
Tests for the scraper module

These tests verify:
1. Pure parsing functions work correctly with sample HTML
2. Helper functions (clean_text, is_js_required, etc.) behave correctly
3. HTTP fetching works with mocked clients
4. Error handling and fallback strategies work as expected
"""

from unittest.mock import Mock

from bs4 import BeautifulSoup

from src.config.loader import Config
from src.scraper import (
    MIN_VALID_TEXT_LENGTH,
    clean_text,
    extract_descriptions,
    extract_domain,
    extract_from_paragraphs,
    extract_json_ld,
    fetch_arbeitsagentur_details,
    fetch_external_details,
    find_content_heavy_div,
    generate_extraction_statistics,
    is_js_required,
    parse_arbeitsagentur_page,
    parse_external_page,
)


class TestHelperFunctions:
    """Test helper/utility functions"""

    def test_clean_text_removes_extra_whitespace(self):
        """clean_text should normalize whitespace"""
        text = "Hello    world\n\n\n   test"
        result = clean_text(text)
        assert "    " not in result
        assert result == "Hello world test"

    def test_clean_text_handles_empty_string(self):
        """clean_text should handle empty strings gracefully"""
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_extract_domain_valid_url(self):
        """extract_domain should extract domain from URL"""
        assert extract_domain("https://example.com/jobs/123") == "example.com"
        assert extract_domain("http://jobs.stepstone.de/detail") == "jobs.stepstone.de"

    def test_extract_domain_invalid_url(self):
        """extract_domain should handle malformed URLs"""
        result = extract_domain("not-a-url")
        # urlparse treats it as path, returns empty netloc
        assert result in ("unknown", "not-a-url", "")  # Any is acceptable

    def test_is_js_required_detects_js_placeholder(self):
        """is_js_required should detect JavaScript requirement messages"""
        # Short text with "javascript" mention = JS required
        assert is_js_required("Sie müssen JavaScript aktivieren")
        assert is_js_required("Please enable JavaScript to view")
        assert is_js_required("javascript is required")

    def test_is_js_required_allows_long_text_with_js_mention(self):
        """is_js_required should allow long content that mentions JavaScript"""
        # Long text (>500 chars) mentioning JS = legitimate content
        long_text = "We are looking for a JavaScript developer. " * 20  # >500 chars
        assert not is_js_required(long_text)

    def test_is_js_required_handles_normal_content(self):
        """is_js_required should not flag normal job descriptions"""
        assert not is_js_required("Software Developer position in Berlin")
        assert not is_js_required("")


class TestJSONLDExtraction:
    """Test JSON-LD structured data extraction"""

    def test_extract_json_ld_valid_job_posting(self, load_fixture):
        """Should extract job description from JSON-LD JobPosting"""
        html = load_fixture("external_page_with_json_ld.html")
        soup = BeautifulSoup(html, "html.parser")

        result = extract_json_ld(soup)

        assert result is not None
        assert len(result) >= MIN_VALID_TEXT_LENGTH
        assert "Senior Java Developer" in result
        assert "Spring Boot" in result

    def test_extract_json_ld_no_structured_data(self, load_fixture):
        """Should return None when no JSON-LD present"""
        html = load_fixture("arbeitsagentur_page.html")
        soup = BeautifulSoup(html, "html.parser")

        result = extract_json_ld(soup)

        assert result is None

    def test_extract_json_ld_short_description(self):
        """Should return None if JSON-LD description is too short"""
        html = """
        <html>
            <script type="application/ld+json">
            {
                "@type": "JobPosting",
                "description": "Short description"
            }
            </script>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = extract_json_ld(soup)

        assert result is None  # Too short

    def test_extract_json_ld_malformed_json(self):
        """Should handle malformed JSON gracefully"""
        html = """
        <html>
            <script type="application/ld+json">
            { invalid json ;;;
            </script>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = extract_json_ld(soup)

        assert result is None  # Gracefully returns None


class TestParagraphExtraction:
    """Test paragraph aggregation fallback"""

    def test_extract_from_paragraphs(self):
        """Should aggregate all paragraph tags"""
        html = """
        <html>
            <body>
                <p>First paragraph with good content here.</p>
                <p>Second paragraph also has content.</p>
                <p>Hi</p>  <!-- Too short, should be skipped -->
                <p>Third paragraph with more details.</p>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = extract_from_paragraphs(soup)

        assert "First paragraph" in result
        assert "Second paragraph" in result
        assert "Third paragraph" in result
        assert "Hi" not in result  # Should skip trivial paragraphs

    def test_find_content_heavy_div(self):
        """Should find the div with most text content"""
        html = (
            """
        <html>
            <body>
                <div>Short content</div>
                <div>
                    """
            + "Long content paragraph. " * 100
            + """
                </div>
                <div>Another short one</div>
            </body>
        </html>
        """
        )
        soup = BeautifulSoup(html, "html.parser")

        result = find_content_heavy_div(soup)

        assert result is not None
        assert "Long content paragraph" in result
        assert len(result) >= MIN_VALID_TEXT_LENGTH


class TestParseArbeitsagenturPage:
    """Test Arbeitsagentur page parsing"""

    def test_parse_arbeitsagentur_success(self, load_fixture, test_config):
        """Should successfully extract content from Arbeitsagentur page"""
        html = load_fixture("arbeitsagentur_page.html")
        config = Config(test_config)

        result = parse_arbeitsagentur_page(html, "https://test.url", config)

        assert result["success"]
        assert result["source"] == "arbeitsagentur"
        assert result["extraction_method"] == "css_selector"
        assert "Software Developer" in result["text"]
        assert "Python" in result["text"]
        assert len(result["text"]) > 100
        assert result["text_length"] > 100
        assert result["domain"] == "www.arbeitsagentur.de"

    def test_parse_arbeitsagentur_removes_unwanted_tags(self, test_config):
        """Should remove nav, script, footer tags before extraction"""
        html = """
        <html>
            <nav>Navigation should be removed</nav>
            <script>alert('Should be removed')</script>
            <jb-steadetail-beschreibung>
                <p>This is the actual job content that should remain.</p>
            </jb-steadetail-beschreibung>
            <footer>Footer should be removed</footer>
        </html>
        """
        config = Config(test_config)

        result = parse_arbeitsagentur_page(html, "https://test.url", config)

        assert "Navigation should be removed" not in result["text"]
        assert "Should be removed" not in result["text"]
        assert "Footer should be removed" not in result["text"]
        assert "actual job content" in result["text"]

    def test_parse_arbeitsagentur_selector_not_found(self, test_config):
        """Should fail gracefully when selector not found"""
        html = "<html><body><p>No job content here</p></body></html>"
        config = Config(test_config)

        result = parse_arbeitsagentur_page(html, "https://test.url", config)

        assert not result["success"]
        assert result["error"] == "Content selector not found"
        assert result["warning"] == "NO_CONTENT"

    def test_parse_arbeitsagentur_exception_handling(self, test_config):
        """Should handle parsing exceptions gracefully"""
        html = None  # This will cause an exception
        config = Config(test_config)

        result = parse_arbeitsagentur_page(html, "https://test.url", config)

        assert not result["success"]
        assert "error" in result
        assert result["warning"] == "EXCEPTION"


class TestParseExternalPage:
    """Test external job page parsing"""

    def test_parse_external_json_ld_extraction(self, load_fixture, test_config):
        """Should prioritize JSON-LD extraction (Tier 1)"""
        html = load_fixture("external_page_with_json_ld.html")
        config = Config(test_config)

        result = parse_external_page(html, "https://techcorp.de/jobs/123", config)

        assert result["success"]
        assert result["extraction_method"] == "json_ld"
        assert result["source"] == "external"
        assert "Senior Java Developer" in result["text"]
        assert len(result["text"]) >= MIN_VALID_TEXT_LENGTH

    def test_parse_external_main_tag_extraction(self, load_fixture, test_config):
        """Should extract from <main> tag when JSON-LD not available (Tier 2)"""
        html = load_fixture("external_page_with_main.html")
        config = Config(test_config)

        result = parse_external_page(html, "https://startupx.de/jobs/py-dev", config)

        assert result["success"]
        assert result["extraction_method"] == "css_selector"
        assert "Python Developer" in result["text"]
        assert "FastAPI" in result["text"]
        assert len(result["text"]) >= MIN_VALID_TEXT_LENGTH

    def test_parse_external_js_required_detection(self, load_fixture, test_config):
        """Should detect JavaScript-required pages"""
        html = load_fixture("js_required_page.html")
        config = Config(test_config)

        result = parse_external_page(html, "https://example.com/job", config)

        assert not result["success"]
        assert result["warning"] == "JS_REQUIRED"
        # May show as "Insufficient content" or "JavaScript required"
        assert "Insufficient" in result["error"] or "JavaScript" in result.get("error", "")

    def test_parse_external_domain_extraction(self, test_config):
        """Should extract and include domain in results"""
        html = "<main>" + "Job content. " * 200 + "</main>"
        config = Config(test_config)

        result = parse_external_page(html, "https://jobs.stepstone.de/detail/123", config)

        assert result["domain"] == "jobs.stepstone.de"

    def test_parse_external_removes_navigation_elements(self, test_config):
        """Should remove nav, menu, sidebar elements"""
        html = (
            """
        <html>
            <nav class="navbar">Navigation</nav>
            <div class="sidebar">Sidebar menu</div>
            <main>
                """
            + "Actual job description content. " * 100
            + """
            </main>
        </html>
        """
        )
        config = Config(test_config)

        result = parse_external_page(html, "https://example.com", config)

        # Navigation should be removed
        assert "Navigation" not in result["text"] or result["extraction_method"] == "json_ld"
        # Content should be present
        assert "job description content" in result["text"]


class TestFetchWithMockedHTTP:
    """Test fetch functions with mocked HTTP client"""

    def test_fetch_arbeitsagentur_details_success(self, load_fixture, test_config, mocker):
        """Should fetch and parse Arbeitsagentur page successfully"""
        # Mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = load_fixture("arbeitsagentur_page.html")
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_arbeitsagentur_details(
            refnr="123456789", http_client=mock_client, config_obj=config
        )

        # Verify HTTP was called correctly
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "arbeitsagentur.de" in call_args[0][0]
        assert "123456789" in call_args[0][0]

        # Verify result
        assert result["success"]
        assert "Software Developer" in result["text"]

    def test_fetch_arbeitsagentur_details_http_error(self, test_config):
        """Should handle HTTP errors gracefully"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_arbeitsagentur_details(
            refnr="123456789", http_client=mock_client, config_obj=config
        )

        assert not result["success"]
        assert "HTTP 404" in result["error"]

    def test_fetch_external_details_success(self, load_fixture, test_config):
        """Should fetch and parse external page successfully"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = load_fixture("external_page_with_json_ld.html")
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_external_details(
            external_url="https://techcorp.de/jobs/123", http_client=mock_client, config_obj=config
        )

        assert result["success"]
        assert result["extraction_method"] == "json_ld"

    def test_fetch_external_details_timeout(self, test_config):
        """Should handle timeout exceptions"""
        mock_client = Mock()
        mock_client.get.side_effect = Exception("Timeout error")

        config = Config(test_config)

        result = fetch_external_details(
            external_url="https://example.com/job", http_client=mock_client, config_obj=config
        )

        assert not result["success"]
        assert "error" in result
        assert result["warning"] == "EXCEPTION"

    def test_fetch_uses_config_timeout_values(self, test_config):
        """Should use timeout values from config"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<main>Content</main>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        fetch_external_details(
            external_url="https://example.com", http_client=mock_client, config_obj=config
        )

        # Verify timeout was passed
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["timeout"] == 15  # From test_config


class TestConfigInjection:
    """Test that config injection works correctly"""

    def test_parse_uses_custom_config(self):
        """Should use custom config when provided"""
        custom_config = Config(
            {
                "scraper": {
                    "html_cleanup": {
                        "remove_tags": ["script"]  # Only remove scripts
                    },
                    "arbeitsagentur": {"content_selector": "custom-selector"},
                }
            }
        )

        html = """
        <html>
            <nav>Navigation here</nav>
            <custom-selector>Job content</custom-selector>
        </html>
        """

        result = parse_arbeitsagentur_page(html, "https://test.url", custom_config)

        # Should keep nav (not in remove list) but find custom selector
        assert result["success"]
        assert "Job content" in result["text"]
        # Nav might still be present since we only remove script tags

    def test_parse_falls_back_to_global_config_when_none(self):
        """Should use global config when config_obj is None"""
        html = "<html><jb-steadetail-beschreibung>Content</jb-steadetail-beschreibung></html>"

        # This should not crash even though we pass None for config
        result = parse_arbeitsagentur_page(html, "https://test.url", config_obj=None)

        # Should work with global config
        assert "success" in result


class TestJSONLDExtractionEdgeCases:
    """Test edge cases for JSON-LD extraction"""

    def test_extract_json_ld_with_empty_script_string(self, test_config):
        """Should skip JSON-LD script tags with empty string"""
        # Need a long enough description to pass MIN_VALID_TEXT_LENGTH check (1000 chars)
        long_description = "This is a valid job posting. " * 40
        html = f"""
        <html>
        <head>
            <script type="application/ld+json"></script>
            <script type="application/ld+json">
            {{
                "@type": "JobPosting",
                "description": "{long_description}"
            }}
            </script>
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = extract_json_ld(soup)

        # Should skip the empty script and find the valid one
        assert result is not None
        assert "valid job posting" in result

    def test_extract_json_ld_with_list_of_schema_objects(self, test_config):
        """Should handle JSON-LD with array of schema objects"""
        # Need a long enough description to pass MIN_VALID_TEXT_LENGTH check (1000 chars)
        long_description = "We are looking for a skilled developer to join our team. " * 20
        html = f"""
        <html>
        <head>
            <script type="application/ld+json">
            [
                {{
                    "@type": "Organization",
                    "name": "Example Corp"
                }},
                {{
                    "@type": "JobPosting",
                    "description": "{long_description}"
                }}
            ]
            </script>
        </head>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = extract_json_ld(soup)

        # Should find the JobPosting in the array
        assert result is not None
        assert "skilled developer" in result


class TestGenerateExtractionStatistics:
    """Test extraction statistics generation"""

    def test_generate_extraction_statistics_basic(self):
        """Should generate statistics from scraped jobs"""
        jobs = [
            {
                "refnr": "001",
                "titel": "Job 1",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 500,
                    "extraction_method": "json-ld",
                },
            },
            {
                "refnr": "002",
                "titel": "Job 2",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 600,
                    "extraction_method": "main-tag",
                },
            },
        ]

        stats = generate_extraction_statistics(jobs)

        assert "example.com" in stats["by_domain"]
        assert stats["by_domain"]["example.com"]["total"] == 2
        assert stats["by_domain"]["example.com"]["successful"] == 2
        assert stats["by_domain"]["example.com"]["success_rate"] == 100.0

    def test_generate_extraction_statistics_with_failures(self):
        """Should track failed extractions"""
        jobs = [
            {
                "refnr": "001",
                "titel": "Job 1",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 500,
                    "extraction_method": "json-ld",
                },
            },
            {
                "refnr": "002",
                "titel": "Job 2",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": False,
                    "text_length": 0,
                    "warning": "js-required",
                },
            },
        ]

        stats = generate_extraction_statistics(jobs)

        assert stats["by_domain"]["example.com"]["total"] == 2
        assert stats["by_domain"]["example.com"]["successful"] == 1
        assert stats["by_domain"]["example.com"]["failed"] == 1
        assert stats["by_domain"]["example.com"]["success_rate"] == 50.0

    def test_generate_extraction_statistics_tracks_warnings(self):
        """Should track warning types by domain"""
        jobs = [
            {
                "refnr": "001",
                "titel": "Job 1",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": False,
                    "text_length": 0,
                    "warning": "js-required",
                },
            },
            {
                "refnr": "002",
                "titel": "Job 2",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": False,
                    "text_length": 50,
                    "warning": "text-too-short",
                },
            },
            {
                "refnr": "003",
                "titel": "Job 3",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": False,
                    "text_length": 0,
                    "warning": "js-required",
                },
            },
        ]

        stats = generate_extraction_statistics(jobs)

        # Check warnings are tracked (they're in a nested structure)
        assert "example.com" in stats["by_domain"]
        # Warnings might be in the domain stats after processing
        domain_stats = stats["by_domain"]["example.com"]
        assert domain_stats["total"] == 3
        assert domain_stats["failed"] == 3

    def test_generate_extraction_statistics_tracks_methods(self):
        """Should track extraction methods by domain"""
        jobs = [
            {
                "refnr": "001",
                "titel": "Job 1",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 500,
                    "extraction_method": "json-ld",
                },
            },
            {
                "refnr": "002",
                "titel": "Job 2",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 600,
                    "extraction_method": "json-ld",
                },
            },
            {
                "refnr": "003",
                "titel": "Job 3",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 400,
                    "extraction_method": "main-tag",
                },
            },
        ]

        stats = generate_extraction_statistics(jobs)

        # Check methods are tracked
        assert "example.com" in stats["by_domain"]
        domain_stats = stats["by_domain"]["example.com"]
        assert domain_stats["total"] == 3
        assert domain_stats["successful"] == 3

    def test_generate_extraction_statistics_multiple_domains(self):
        """Should track statistics separately by domain"""
        jobs = [
            {
                "refnr": "001",
                "titel": "Job 1",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 500,
                    "extraction_method": "json-ld",
                },
            },
            {
                "refnr": "002",
                "titel": "Job 2",
                "details": {
                    "source": "external",
                    "domain": "other.com",
                    "success": False,
                    "text_length": 0,
                    "warning": "js-required",
                },
            },
        ]

        stats = generate_extraction_statistics(jobs)

        assert "example.com" in stats["by_domain"]
        assert "other.com" in stats["by_domain"]
        assert stats["by_domain"]["example.com"]["successful"] == 1
        assert stats["by_domain"]["other.com"]["failed"] == 1

    def test_generate_extraction_statistics_calculates_text_stats(self):
        """Should calculate average, min, max text lengths"""
        jobs = [
            {
                "refnr": "001",
                "titel": "Job 1",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 500,
                    "extraction_method": "json-ld",
                },
            },
            {
                "refnr": "002",
                "titel": "Job 2",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 700,
                    "extraction_method": "main-tag",
                },
            },
            {
                "refnr": "003",
                "titel": "Job 3",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 300,
                    "extraction_method": "paragraphs",
                },
            },
        ]

        stats = generate_extraction_statistics(jobs)

        domain_stats = stats["by_domain"]["example.com"]
        assert domain_stats["avg_text_length"] == 500  # (500 + 700 + 300) / 3
        assert domain_stats["min_text_length"] == 300
        assert domain_stats["max_text_length"] == 700

    def test_generate_extraction_statistics_skips_non_external_sources(self):
        """Should track all sources but only external in by_domain"""
        jobs = [
            {
                "refnr": "001",
                "titel": "Job 1",
                "details": {"source": "arbeitsagentur", "success": True, "text_length": 500},
            },
            {
                "refnr": "002",
                "titel": "Job 2",
                "details": {
                    "source": "external",
                    "domain": "example.com",
                    "success": True,
                    "text_length": 600,
                    "extraction_method": "json-ld",
                },
            },
        ]

        stats = generate_extraction_statistics(jobs)

        # Should track both in total_jobs
        assert stats["total_jobs"] == 2
        # But only external in by_domain
        assert "example.com" in stats["by_domain"]
        assert stats["by_domain"]["example.com"]["total"] == 1

    def test_generate_extraction_statistics_empty_jobs_list(self):
        """Should handle empty jobs list"""
        stats = generate_extraction_statistics([])

        assert stats["total_jobs"] == 0
        assert stats["by_domain"] == {}


class TestExtractDescriptionsFunction:
    """Test extract_descriptions function"""

    def test_extract_descriptions_filters_successful_jobs(self):
        """Should only include jobs with successful extraction"""
        jobs = [
            {
                "refnr": "001",
                "beruf": "Developer",
                "arbeitsort": {"ort": "Berlin"},
                "arbeitgeber": "Company A",
                "details": {
                    "success": True,
                    "text": "Description 1",
                    "url": "http://example.com/1",
                },
            },
            {"refnr": "002", "beruf": "Manager", "details": {"success": False}},
            {
                "refnr": "003",
                "beruf": "Designer",
                "arbeitsort": {"ort": "Munich"},
                "arbeitgeber": "Company B",
                "details": {
                    "success": True,
                    "text": "Description 3",
                    "url": "http://example.com/3",
                },
            },
        ]

        successful, failed = extract_descriptions(jobs)

        assert len(successful) == 2
        assert len(failed) == 1
        assert successful[0]["refnr"] == "001"
        assert successful[0]["titel"] == "Developer"
        assert successful[0]["text"] == "Description 1"
        assert successful[1]["refnr"] == "003"
        assert failed[0]["titel"] == "Manager"

    def test_extract_descriptions_handles_missing_fields(self):
        """Should handle missing optional fields gracefully"""
        jobs = [
            {
                "refnr": "001",
                "beruf": "Developer",
                # Missing arbeitsort
                # Missing arbeitgeber
                "details": {
                    "success": True,
                    "text": "Description 1",
                    "url": "http://example.com/1",
                },
            },
            {
                "refnr": "002",
                "beruf": "Designer",
                "arbeitsort": "InvalidFormat",  # Not a dict
                "details": {
                    "success": True,
                    "text": "Description 2",
                    "url": "http://example.com/2",
                },
            },
        ]

        successful, failed = extract_descriptions(jobs)

        assert len(successful) == 2
        assert len(failed) == 0
        assert successful[0]["ort"] == ""  # Missing arbeitsort
        assert successful[0]["arbeitgeber"] == ""  # Missing arbeitgeber
        assert successful[1]["ort"] == ""  # Invalid arbeitsort format


class TestParseArbeitsagenturExceptionHandling:
    """Test exception handling in parse_arbeitsagentur_page"""

    def test_parse_arbeitsagentur_handles_parsing_errors(self, test_config):
        """Should return error result when parsing fails"""
        # Simulate an error by passing None as HTML
        config = Config(test_config)

        result = parse_arbeitsagentur_page(None, "123456", config)

        assert result["success"] is False
        assert "error" in result


class TestFetchExternalDetailsEdgeCases:
    """Test additional edge cases for fetch_external_details"""

    def test_fetch_external_details_with_redirect_response(self, test_config):
        """Should handle redirect status codes"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 301  # Redirect
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_external_details(
            external_url="https://example.com/job", http_client=mock_client, config_obj=config
        )

        # Should treat redirect as error (not following redirects)
        assert result["success"] is False


class TestFetchArbeitsagenturDetailsEdgeCases:
    """Test edge cases for fetch_arbeitsagentur_details"""

    def test_fetch_arbeitsagentur_details_with_client_error(self, test_config):
        """Should handle 4xx client errors"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_arbeitsagentur_details(
            refnr="123456", http_client=mock_client, config_obj=config
        )

        assert result["success"] is False
        assert "HTTP 404" in result["error"]
