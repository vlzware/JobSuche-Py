"""
Tests for fetch_detailed_listings orchestration function

This function is critical - it orchestrates the entire scraping workflow:
- Loops through all jobs
- Calls appropriate fetch function (external vs arbeitsagentur)
- Tracks errors and generates statistics
- Saves debug artifacts
"""

import json
from unittest.mock import Mock, patch

from src.config.loader import Config
from src.scraper import fetch_detailed_listings


class TestFetchDetailedListingsOrchestration:
    """Test the main orchestration logic"""

    def test_fetch_detailed_listings_processes_all_jobs(self, test_config):
        """Should process all jobs in the list"""
        jobs = [
            {"refnr": "123", "beruf": "Job 1", "arbeitsort": {"ort": "Berlin"}, "externeUrl": None},
            {
                "refnr": "456",
                "beruf": "Job 2",
                "arbeitsort": {"ort": "Hamburg"},
                "externeUrl": None,
            },
            {"refnr": "789", "beruf": "Job 3", "arbeitsort": {"ort": "Munich"}, "externeUrl": None},
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<jb-steadetail-beschreibung>Job content</jb-steadetail-beschreibung>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_detailed_listings(
            jobs=jobs,
            delay=0,  # No delay for tests
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        assert len(result) == 3
        assert all("details" in job for job in result)

    def test_fetch_detailed_listings_uses_external_url_when_present(self, test_config):
        """Should prefer external URL over internal refnr"""
        jobs = [
            {
                "refnr": "123",
                "beruf": "External Job",
                "arbeitsort": {"ort": "Berlin"},
                "externeUrl": "https://company.com/job/123",
                "arbeitgeber": "Company",
            }
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<main>External job content here</main>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_detailed_listings(
            jobs=jobs, delay=0, verbose=False, http_client=mock_client, config_obj=config
        )

        # Verify external URL was used
        call_args = mock_client.get.call_args[0]
        assert "company.com" in call_args[0]
        assert result[0]["details"]["source"] == "external"

    def test_fetch_detailed_listings_uses_arbeitsagentur_when_no_external_url(self, test_config):
        """Should use refnr for Arbeitsagentur when no external URL"""
        jobs = [
            {
                "refnr": "123456",
                "beruf": "Internal Job",
                "arbeitsort": {"ort": "Berlin"},
                "externeUrl": "",  # Empty string
                "arbeitgeber": "Company",
            }
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<jb-steadetail-beschreibung>Content</jb-steadetail-beschreibung>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_detailed_listings(
            jobs=jobs, delay=0, verbose=False, http_client=mock_client, config_obj=config
        )

        # Verify Arbeitsagentur URL was used
        call_args = mock_client.get.call_args[0]
        assert "arbeitsagentur.de" in call_args[0]
        assert "123456" in call_args[0]
        assert result[0]["details"]["source"] == "arbeitsagentur"

    def test_fetch_detailed_listings_handles_missing_url_and_refnr(self, test_config):
        """Should handle jobs with neither external URL nor refnr"""
        jobs = [
            {
                "beruf": "Broken Job",
                "arbeitsort": {"ort": "Berlin"},
                # No refnr, no externeUrl
            }
        ]

        config = Config(test_config)

        result = fetch_detailed_listings(jobs=jobs, delay=0, verbose=False, config_obj=config)

        assert not result[0]["details"]["success"]
        assert "No refnr or external URL" in result[0]["details"]["error"]


class TestFetchDetailedListingsErrorTracking:
    """Test error tracking and statistics"""

    def test_tracks_successful_vs_failed_jobs(self, test_config, caplog):
        """Should track success/failure counts"""
        jobs = [
            {
                "refnr": "111",
                "beruf": "Good Job",
                "arbeitsort": {"ort": "Berlin"},
                "externeUrl": None,
            },
            {
                "refnr": "222",
                "beruf": "Bad Job",
                "arbeitsort": {"ort": "Hamburg"},
                "externeUrl": None,
            },
        ]

        mock_client = Mock()

        # First call succeeds, second fails
        response_success = Mock()
        response_success.status_code = 200
        response_success.text = (
            "<jb-steadetail-beschreibung>Good content</jb-steadetail-beschreibung>"
        )

        response_fail = Mock()
        response_fail.status_code = 404

        mock_client.get.side_effect = [response_success, response_fail]

        config = Config(test_config)

        result = fetch_detailed_listings(
            jobs=jobs, delay=0, verbose=True, http_client=mock_client, config_obj=config
        )

        # Check results
        assert result[0]["details"]["success"]
        assert not result[1]["details"]["success"]

        # Check that error summary was logged
        assert "SCRAPING ERROR SUMMARY" in caplog.text
        assert "1/2 jobs" in caplog.text or "50.0%" in caplog.text

    def test_tracks_errors_by_domain(self, test_config):
        """Should track errors grouped by domain"""
        jobs = [
            {
                "refnr": None,
                "beruf": "Job 1",
                "arbeitsort": {"ort": "Berlin"},
                "externeUrl": "https://stepstone.de/job1",
            },
            {
                "refnr": None,
                "beruf": "Job 2",
                "arbeitsort": {"ort": "Hamburg"},
                "externeUrl": "https://stepstone.de/job2",
            },
            {
                "refnr": None,
                "beruf": "Job 3",
                "arbeitsort": {"ort": "Munich"},
                "externeUrl": "https://indeed.de/job3",
            },
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 404  # All fail
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_detailed_listings(
            jobs=jobs, delay=0, verbose=False, http_client=mock_client, config_obj=config
        )

        # All should fail
        assert all(not job["details"]["success"] for job in result)
        # Domains should be tracked
        assert result[0]["details"]["domain"] == "stepstone.de"
        assert result[1]["details"]["domain"] == "stepstone.de"
        assert result[2]["details"]["domain"] == "indeed.de"

    def test_tracks_errors_by_warning_type(self, test_config, load_fixture):
        """Should track different warning types (JS_REQUIRED, TIMEOUT, etc.)"""
        jobs = [
            {
                "refnr": None,
                "beruf": "JS Job",
                "arbeitsort": {"ort": "Berlin"},
                "externeUrl": "https://example.com/js",
            },
            {
                "refnr": None,
                "beruf": "Short Job",
                "arbeitsort": {"ort": "Hamburg"},
                "externeUrl": "https://example.com/short",
            },
        ]

        mock_client = Mock()

        # First returns JS-required page, second returns short content
        js_response = Mock()
        js_response.status_code = 200
        js_response.text = load_fixture("js_required_page.html")

        short_response = Mock()
        short_response.status_code = 200
        short_response.text = "<main><p>Short</p></main>"

        mock_client.get.side_effect = [js_response, short_response]

        config = Config(test_config)

        result = fetch_detailed_listings(
            jobs=jobs, delay=0, verbose=False, http_client=mock_client, config_obj=config
        )

        # Check warning types
        assert result[0]["details"]["warning"] == "JS_REQUIRED"
        assert result[1]["details"]["warning"] in ("SHORT_CONTENT", "LOW_QUALITY")


class TestFetchDetailedListingsSessionIntegration:
    """Test session integration for debug artifacts"""

    def test_saves_error_report_to_session(self, test_config, tmp_path):
        """Should save error report JSON when failures occur"""
        # Create mock session
        mock_session = Mock()
        mock_session.debug_dir = tmp_path

        jobs = [
            {"refnr": "123", "beruf": "Job 1", "arbeitsort": {"ort": "Berlin"}, "externeUrl": None},
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 500  # Failure
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        fetch_detailed_listings(
            jobs=jobs,
            delay=0,
            verbose=False,
            session=mock_session,
            http_client=mock_client,
            config_obj=config,
        )

        # Check that error report was saved
        error_file = tmp_path / "scraping_errors.json"
        assert error_file.exists()

        with open(error_file) as f:
            error_data = json.load(f)

        assert error_data["total_jobs"] == 1
        assert error_data["failed"] == 1
        assert len(error_data["failed_jobs"]) == 1

    def test_saves_scraped_jobs_to_session(self, test_config):
        """Should call session.save_scraped_jobs with results"""
        mock_session = Mock()

        jobs = [
            {"refnr": "123", "beruf": "Job 1", "arbeitsort": {"ort": "Berlin"}, "externeUrl": None},
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<jb-steadetail-beschreibung>Content</jb-steadetail-beschreibung>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        fetch_detailed_listings(
            jobs=jobs,
            delay=0,
            verbose=False,
            session=mock_session,
            http_client=mock_client,
            config_obj=config,
        )

        # Verify session method was called
        mock_session.save_scraped_jobs.assert_called_once()
        saved_jobs = mock_session.save_scraped_jobs.call_args[0][0]
        assert len(saved_jobs) == 1
        assert saved_jobs[0]["details"]["success"]


class TestFetchDetailedListingsDelayAndRateLimiting:
    """Test delay/rate limiting behavior"""

    @patch("src.scraper.time.sleep")
    def test_respects_delay_between_requests(self, mock_sleep, test_config):
        """Should add delay between requests"""
        jobs = [
            {"refnr": "111", "beruf": "Job 1", "arbeitsort": {"ort": "Berlin"}, "externeUrl": None},
            {
                "refnr": "222",
                "beruf": "Job 2",
                "arbeitsort": {"ort": "Hamburg"},
                "externeUrl": None,
            },
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<jb-steadetail-beschreibung>Content</jb-steadetail-beschreibung>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        fetch_detailed_listings(
            jobs=jobs,
            delay=1.5,  # 1.5 second delay
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should have one sleep call (between job 1 and job 2)
        # Note: no sleep after last job
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(1.5)

    @patch("src.scraper.time.sleep")
    def test_uses_config_delay_when_none_specified(self, mock_sleep, test_config):
        """Should use delay from config when not specified"""
        test_config["api"]["delays"] = {"scraping": 2.0}

        jobs = [
            {"refnr": "111", "beruf": "Job 1", "arbeitsort": {"ort": "Berlin"}, "externeUrl": None},
            {
                "refnr": "222",
                "beruf": "Job 2",
                "arbeitsort": {"ort": "Hamburg"},
                "externeUrl": None,
            },
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<jb-steadetail-beschreibung>Content</jb-steadetail-beschreibung>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        fetch_detailed_listings(
            jobs=jobs,
            delay=None,  # Use config default
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should use config delay
        mock_sleep.assert_called_with(2.0)


class TestFetchDetailedListingsStatistics:
    """Test statistics generation"""

    def test_generates_extraction_statistics_when_verbose(self, test_config):
        """Should generate extraction statistics when verbose=True without errors"""
        jobs = [
            {"refnr": "123", "beruf": "Job 1", "arbeitsort": {"ort": "Berlin"}, "externeUrl": None},
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = (
            "<jb-steadetail-beschreibung>Content for statistics</jb-steadetail-beschreibung>"
        )
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        # Should complete without raising exceptions
        result = fetch_detailed_listings(
            jobs=jobs,
            delay=0,
            verbose=True,  # Triggers statistics generation
            http_client=mock_client,
            config_obj=config,
        )

        # Verify it completed successfully
        assert len(result) == 1
        assert result[0]["details"]["success"]

    def test_returns_detailed_jobs_with_statistics_metadata(self, test_config):
        """Should return jobs with details that can be used for statistics"""
        jobs = [
            {"refnr": "123", "beruf": "Job 1", "arbeitsort": {"ort": "Berlin"}, "externeUrl": None},
        ]

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<jb-steadetail-beschreibung>Content</jb-steadetail-beschreibung>"
        mock_client.get.return_value = mock_response

        config = Config(test_config)

        result = fetch_detailed_listings(
            jobs=jobs, delay=0, verbose=False, http_client=mock_client, config_obj=config
        )

        # Verify result includes all necessary metadata for statistics
        assert result[0]["details"]["source"] == "arbeitsagentur"
        assert result[0]["details"]["extraction_method"] == "css_selector"
        assert "text_length" in result[0]["details"]
