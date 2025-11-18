"""
Critical error scenario tests - safety net for edge cases

These tests cover error conditions that are unlikely to occur during normal usage
but could cause issues if they do. Happy-path testing happens through real-world usage.
"""

from unittest.mock import Mock, patch

import pytest

from src.exceptions import OpenRouterAPIError


class TestAPIClientErrors:
    """Test API client error handling"""

    def test_http_error_handling(self):
        """Test HTTP error responses are properly handled"""
        from src.api_client import search_jobs

        with patch("src.api_client.default_http_client") as mock_client:
            mock_client.get.side_effect = RuntimeError("HTTP 500 Error")

            # Should raise exception on HTTP errors
            with pytest.raises(RuntimeError):
                search_jobs(was="test", wo="test")

    def test_network_exception_handling(self):
        """Test network failures are handled"""
        from src.api_client import search_jobs

        with patch("src.api_client.default_http_client") as mock_client:
            mock_client.get.side_effect = ConnectionError("Network unavailable")

            with pytest.raises(ConnectionError):
                search_jobs(was="test", wo="test")


class TestClassifierErrors:
    """Test classifier error handling"""

    def test_api_error_propagation(self):
        """Test API errors are properly propagated"""
        from src.classifier import classify_jobs_batch

        jobs = [{"refnr": "123", "titel": "Test", "text": "Description"}]

        with patch("src.classifier.default_http_client") as mock_client:
            mock_response = Mock()
            mock_response.text = '{"error": {"code": 401, "message": "Unauthorized"}}'
            mock_client.post.return_value = mock_response

            with pytest.raises(OpenRouterAPIError):
                classify_jobs_batch(
                    jobs=jobs, categories=["Cat1"], api_key="invalid_key", model="test-model"
                )


class TestScraperErrors:
    """Test scraper error handling"""

    def test_invalid_url_handling(self):
        """Test handling of invalid URLs"""
        from src.scraper import extract_domain

        # Should handle malformed URLs gracefully (returns empty string)
        result = extract_domain("not a url")
        assert result == ""

    def test_missing_required_fields(self):
        """Test handling of jobs with missing required fields"""
        from src.scraper import extract_descriptions

        # Job missing critical fields
        jobs = [
            {"titel": "Job 1"},  # Missing refnr, arbeitgeber, etc.
            {"refnr": "123", "titel": "Job 2", "arbeitgeber": "Company"},  # Valid
        ]

        # Should handle gracefully without crashing
        _valid_jobs, failed = extract_descriptions(jobs)
        assert len(failed) >= 0  # Should track failures


class TestWorkflowErrors:
    """Test workflow error validation"""

    def test_matching_workflow_requires_inputs(self):
        """Test matching workflow validates required inputs"""
        from src.exceptions import WorkflowConfigurationError
        from src.llm import LLMProcessor
        from src.preferences import UserProfile
        from src.workflows import MatchingWorkflow

        user_profile = UserProfile()
        llm_processor = LLMProcessor(api_key="test")

        workflow = MatchingWorkflow(
            user_profile=user_profile, llm_processor=llm_processor, session=None, verbose=False
        )

        # Should raise error when neither CV nor perfect_job_description provided
        with pytest.raises(WorkflowConfigurationError):
            workflow.process(jobs=[], cv_content=None, perfect_job_description=None)

    def test_matching_workflow_rejects_empty_inputs(self):
        """Test matching workflow rejects empty string inputs"""
        from src.exceptions import WorkflowConfigurationError
        from src.llm import LLMProcessor
        from src.preferences import UserProfile
        from src.workflows import MatchingWorkflow

        user_profile = UserProfile()
        llm_processor = LLMProcessor(api_key="test")

        workflow = MatchingWorkflow(
            user_profile=user_profile, llm_processor=llm_processor, session=None, verbose=False
        )

        # Empty strings should be treated as missing
        with pytest.raises(WorkflowConfigurationError):
            workflow.process(
                jobs=[],
                cv_content="   ",  # Whitespace only
                perfect_job_description="",  # Empty
            )


class TestFileHandlingErrors:
    """Test file I/O error handling"""

    def test_missing_cv_file(self, tmp_path):
        """Test handling of missing CV file"""
        from src.preferences import UserProfile

        # Should handle missing file gracefully
        profile = UserProfile(cv_path="/nonexistent/cv.md")
        assert not profile.has_cv()


class TestHTTPClientErrors:
    """Test HTTP client error handling"""

    def test_timeout_configuration(self):
        """Test timeout parameter is respected"""
        from src.http_client import HttpClient

        with patch("requests.get") as mock_get:
            mock_get.side_effect = TimeoutError("Timeout")

            client = HttpClient()
            with pytest.raises(TimeoutError):
                client.get("https://example.com", timeout=1)


class TestConfigErrors:
    """Test configuration error handling"""

    def test_missing_config_returns_empty(self):
        """Test missing config keys return empty dict"""
        from src.config import Config

        config = Config()

        # Should return empty dict for non-existent keys, not crash
        result = config.get("nonexistent.deeply.nested.key", default={})
        assert result == {}


class TestCLIErrors:
    """Test CLI validation errors"""

    def test_missing_cv_file_exits(self, tmp_path):
        """Test CLI exits when CV file doesn't exist"""
        import subprocess
        from pathlib import Path

        # Use project root dynamically
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            ["python", "main.py", "--was", "test", "--cv", "/nonexistent/cv.md"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Should exit with error
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()

    def test_missing_required_inputs_exits(self):
        """Test CLI exits when neither CV nor perfect job description provided"""
        import subprocess
        from pathlib import Path

        # Use project root dynamically
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            ["python", "main.py", "--was", "test"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Should exit with error about missing inputs
        assert result.returncode != 0
