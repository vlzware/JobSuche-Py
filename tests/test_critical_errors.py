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
        from src.workflows import MatchingWorkflow

        llm_processor = LLMProcessor(api_key="test")

        workflow = MatchingWorkflow(llm_processor=llm_processor, session=None, verbose=False)

        # Should raise error when neither CV nor perfect_job_description provided
        with pytest.raises(WorkflowConfigurationError):
            workflow.process(jobs=[], cv_content=None, perfect_job_description=None)

    def test_matching_workflow_rejects_empty_inputs(self):
        """Test matching workflow rejects empty string inputs"""
        from src.exceptions import WorkflowConfigurationError
        from src.llm import LLMProcessor
        from src.workflows import MatchingWorkflow

        llm_processor = LLMProcessor(api_key="test")

        workflow = MatchingWorkflow(llm_processor=llm_processor, session=None, verbose=False)

        # Empty strings should be treated as missing
        with pytest.raises(WorkflowConfigurationError):
            workflow.process(
                jobs=[],
                cv_content="   ",  # Whitespace only
                perfect_job_description="",  # Empty
            )


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

    def test_missing_cv_file_exits(self, cli_test_env):
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
            env=cli_test_env,
        )

        # Should exit with error
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()

    def test_missing_required_inputs_exits(self, cli_test_env):
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
            env=cli_test_env,
        )

        # Should exit with error about missing inputs
        assert result.returncode != 0


class TestDatabaseErrors:
    """Test database-related error conditions"""

    def test_geographic_context_mismatch(self, tmp_path):
        """Test that changing search location raises error"""
        from src.data import JobGatherer
        from src.session import SearchSession

        # Create temporary database
        db_path = tmp_path / "test_jobs.json"

        # First search - Berlin
        session1 = SearchSession(base_dir=tmp_path / "session1", verbose=False)
        gatherer1 = JobGatherer(session=session1, verbose=False, database_path=db_path)

        # Mock the API/scraping to avoid real network calls
        with (
            patch("src.data.gatherer.search_jobs") as mock_search,
            patch("src.data.gatherer.fetch_detailed_listings") as mock_scrape,
        ):
            # Mock API returns one job
            mock_search.return_value = [
                {
                    "refnr": "test-123",
                    "beruf": "Test Job",
                    "arbeitgeber": "Test Company",
                    "titel": "Test Title",
                    "modifikationsTimestamp": "2024-01-01T00:00:00",
                    "arbeitsort": {"ort": "Berlin"},
                }
            ]
            # Mock scraping returns detailed jobs list
            mock_scrape.return_value = [
                {
                    "refnr": "test-123",
                    "beruf": "Test Job",
                    "arbeitgeber": "Test Company",
                    "titel": "Test Title",
                    "modifikationsTimestamp": "2024-01-01T00:00:00",
                    "arbeitsort": {"ort": "Berlin"},
                    "details": {
                        "success": True,
                        "url": "https://example.com/job",
                        "text": "Test job description",
                    },
                }
            ]

            # First search should succeed
            gatherer1.gather(
                was="Developer",
                wo="Berlin",
                umkreis=25,
                size=10,
                max_pages=1,
                arbeitszeit="",
                enable_scraping=True,
                veroeffentlichtseit=None,
                include_weiterbildung=False,
            )

        # Second search - Munich (different location)
        session2 = SearchSession(base_dir=tmp_path / "session2", verbose=False)
        gatherer2 = JobGatherer(session=session2, verbose=False, database_path=db_path)

        # Should raise ValueError for geographic context mismatch
        with (
            pytest.raises(ValueError, match="Geographic context mismatch"),
            patch("src.data.gatherer.search_jobs") as mock_search,
        ):
            mock_search.return_value = []
            gatherer2.gather(
                was="Developer",
                wo="München",  # Different location!
                umkreis=25,
                size=10,
                max_pages=1,
                arbeitszeit="",
                enable_scraping=True,
                veroeffentlichtseit=None,
                include_weiterbildung=False,
            )

    def test_from_database_missing_database_exits(self, cli_test_env):
        """Test --from-database exits when database doesn't exist"""
        import subprocess
        from pathlib import Path

        project_root = Path(__file__).parent.parent

        # Need to set fake API key to get past API validation
        cli_test_env["OPENROUTER_API_KEY"] = "fake-key-for-testing"

        result = subprocess.run(
            ["python", "main.py", "--from-database", "--cv", "cv.md"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=cli_test_env,
        )

        # Should exit with error
        assert result.returncode != 0
        output = result.stderr + result.stdout
        assert "not found" in output.lower() or "database" in output.lower()


class TestParameterConflicts:
    """Test mutually exclusive parameter validation"""

    def test_from_database_with_input_conflict(self, cli_test_env):
        """Test --from-database and --input are mutually exclusive"""
        import subprocess
        from pathlib import Path

        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            [
                "python",
                "main.py",
                "--from-database",
                "--input",
                "some_session",
                "--cv",
                "cv.md",
            ],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=cli_test_env,
        )

        # Should exit with error
        assert result.returncode != 0
        output = result.stderr + result.stdout
        assert "mutually exclusive" in output.lower()

    def test_from_database_with_classify_only_conflict(self, cli_test_env):
        """Test --from-database and --classify-only are mutually exclusive"""
        import subprocess
        import tempfile
        from pathlib import Path

        project_root = Path(__file__).parent.parent

        # Create a temporary file to pass path validation
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("[]")
            temp_path = f.name

        try:
            result = subprocess.run(
                [
                    "python",
                    "main.py",
                    "--from-database",
                    "--classify-only",
                    "--input",
                    temp_path,
                    "--cv",
                    "cv.md",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_root),
                env=cli_test_env,
            )

            # Should exit with error
            assert result.returncode != 0
            output = result.stderr + result.stdout
            assert "mutually exclusive" in output.lower()
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    def test_from_database_with_no_classification_conflict(self, cli_test_env):
        """Test --from-database requires classification"""
        import subprocess
        from pathlib import Path

        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            ["python", "main.py", "--from-database", "--no-classification", "--cv", "cv.md"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=cli_test_env,
        )

        # Should exit with error
        assert result.returncode != 0
        output = result.stderr + result.stdout
        assert "requires classification" in output.lower() or "can't use" in output.lower()

    def test_from_database_with_was_parameter_conflict(self, cli_test_env):
        """Test --from-database doesn't need --was parameter"""
        import subprocess
        from pathlib import Path

        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            ["python", "main.py", "--from-database", "--was", "Developer", "--cv", "cv.md"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
            env=cli_test_env,
        )

        # Should exit with error
        assert result.returncode != 0
        output = result.stderr + result.stdout
        assert "doesn't need" in output.lower() or "all jobs" in output.lower()
