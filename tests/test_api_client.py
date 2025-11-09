"""
Tests for api_client.py - Job search API integration

Tests cover:
- search_jobs() pagination logic
- Error handling for API failures
- exclude_weiterbildung filtering
- Config injection
- HTTP client injection
- Session integration
- simplify_job_data() transformation
"""

from unittest.mock import Mock

import pytest
import requests

from src.api_client import search_jobs, simplify_job_data
from src.config import Config

# Fixtures


@pytest.fixture
def mock_config():
    """Mock config with test values"""
    config_dict = {
        "search": {
            "defaults": {"page_size": 50, "max_pages": 2, "radius_km": 25},
            "filters": {"exclude_keywords": ["weiterbildung", "ausbildung"]},
        },
        "api": {
            "arbeitsagentur": {
                "base_url": "https://rest.arbeitsagentur.de/jobboerse",
                "headers": {
                    "user_agent": "JobSuche-Test/1.0",
                    "host": "rest.arbeitsagentur.de",
                    "api_key": "test-key-123",
                },
                "params": {"angebotsart": "1", "pav": "false"},
            },
            "timeouts": {"api_request": 30},
        },
    }
    return Config(config_dict)


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing"""
    return Mock()


@pytest.fixture
def sample_api_response_page1():
    """Sample API response for page 1"""
    return {
        "maxErgebnisse": "150",
        "stellenangebote": [
            {
                "beruf": "Software Developer",
                "arbeitsort": {"ort": "Berlin"},
                "arbeitgeber": "Tech Corp",
                "refnr": "12345",
                "externeUrl": "https://example.com/job1",
            },
            {
                "beruf": "Python Engineer",
                "arbeitsort": {"ort": "Hamburg"},
                "arbeitgeber": "Code Inc",
                "refnr": "12346",
                "externeUrl": "https://example.com/job2",
            },
            {
                "beruf": "Weiterbildung zum Developer",  # Should be filtered
                "arbeitsort": {"ort": "Munich"},
                "arbeitgeber": "Training GmbH",
                "refnr": "12347",
                "externeUrl": "https://example.com/job3",
            },
        ],
    }


@pytest.fixture
def sample_api_response_page2():
    """Sample API response for page 2"""
    return {
        "maxErgebnisse": "150",
        "stellenangebote": [
            {
                "beruf": "Senior Developer",
                "arbeitsort": {"ort": "Frankfurt"},
                "arbeitgeber": "Big Tech",
                "refnr": "12348",
                "externeUrl": "https://example.com/job4",
            }
        ],
    }


# Tests for search_jobs()


def test_search_jobs_basic_success(mock_http_client, mock_config, sample_api_response_page1):
    """Test basic job search with single page"""
    # Setup mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    # Execute search
    results = search_jobs(
        was="Developer",
        wo="Berlin",
        max_pages=1,
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Verify
    assert len(results) == 2  # 3 jobs, but 1 filtered out (Weiterbildung)
    assert results[0]["beruf"] == "Software Developer"
    assert results[1]["beruf"] == "Python Engineer"

    # Verify HTTP call was made correctly
    mock_http_client.get.assert_called_once()
    call_args = mock_http_client.get.call_args
    assert "/pc/v4/jobs" in call_args[0][0]
    assert call_args[1]["headers"]["X-API-Key"] == "test-key-123"


def test_search_jobs_pagination(
    mock_http_client, mock_config, sample_api_response_page1, sample_api_response_page2
):
    """Test that pagination works correctly across multiple pages"""
    # Setup mock to return different responses for different pages
    mock_response_1 = Mock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = sample_api_response_page1

    mock_response_2 = Mock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = sample_api_response_page2

    mock_http_client.get.side_effect = [mock_response_1, mock_response_2]

    # Execute search with 2 pages
    results = search_jobs(
        was="Developer",
        wo="Berlin",
        max_pages=2,
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Verify we got results from both pages (2 from page 1 + 1 from page 2)
    assert len(results) == 3
    assert results[0]["beruf"] == "Software Developer"
    assert results[1]["beruf"] == "Python Engineer"
    assert results[2]["beruf"] == "Senior Developer"

    # Verify two HTTP calls were made
    assert mock_http_client.get.call_count == 2


def test_search_jobs_empty_results(mock_http_client, mock_config):
    """Test handling of empty search results"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"maxErgebnisse": "0", "stellenangebote": []}
    mock_http_client.get.return_value = mock_response

    results = search_jobs(
        was="NonexistentJob", wo="Berlin", http_client=mock_http_client, config_obj=mock_config
    )

    assert len(results) == 0


def test_search_jobs_stops_on_empty_page(mock_http_client, mock_config, sample_api_response_page1):
    """Test that pagination stops when encountering empty page"""
    mock_response_1 = Mock()
    mock_response_1.status_code = 200
    mock_response_1.json.return_value = sample_api_response_page1

    mock_response_2 = Mock()
    mock_response_2.status_code = 200
    mock_response_2.json.return_value = {
        "maxErgebnisse": "150",
        "stellenangebote": [],  # Empty page
    }

    mock_http_client.get.side_effect = [mock_response_1, mock_response_2]

    # Request 5 pages, but should stop after 2
    results = search_jobs(
        was="Developer",
        wo="Berlin",
        max_pages=5,
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Should only have results from first page
    assert len(results) == 2
    # Should only make 2 HTTP calls (stops when page 2 is empty)
    assert mock_http_client.get.call_count == 2


def test_search_jobs_error_handling_http_error(mock_http_client, mock_config):
    """Test handling of HTTP errors (non-200 status)"""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_http_client.get.return_value = mock_response

    results = search_jobs(
        was="Developer", wo="Berlin", http_client=mock_http_client, config_obj=mock_config
    )

    assert len(results) == 0  # Should return empty list on error


def test_search_jobs_error_handling_network_exception(mock_http_client, mock_config):
    """Test handling of network exceptions"""
    mock_http_client.get.side_effect = requests.exceptions.ConnectionError("Network error")

    results = search_jobs(
        was="Developer", wo="Berlin", http_client=mock_http_client, config_obj=mock_config
    )

    assert len(results) == 0  # Should return empty list on exception


def test_search_jobs_exclude_weiterbildung_enabled(
    mock_http_client, mock_config, sample_api_response_page1
):
    """Test that Weiterbildung jobs are filtered when exclude_weiterbildung=True"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    results = search_jobs(
        was="Developer",
        wo="Berlin",
        max_pages=1,
        exclude_weiterbildung=True,  # Explicitly enable filtering
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Should filter out the "Weiterbildung zum Developer" job
    assert len(results) == 2
    assert all("weiterbildung" not in job["beruf"].lower() for job in results)


def test_search_jobs_exclude_weiterbildung_disabled(
    mock_http_client, mock_config, sample_api_response_page1
):
    """Test that Weiterbildung jobs are included when exclude_weiterbildung=False"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    results = search_jobs(
        was="Developer",
        wo="Berlin",
        max_pages=1,
        exclude_weiterbildung=False,  # Disable filtering
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Should include all 3 jobs
    assert len(results) == 3


def test_search_jobs_with_arbeitszeit_filter(
    mock_http_client, mock_config, sample_api_response_page1
):
    """Test that arbeitszeit parameter is included in request when specified"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    search_jobs(
        was="Developer",
        wo="Berlin",
        arbeitszeit="vz",  # Vollzeit
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Verify arbeitszeit was included in params
    call_args = mock_http_client.get.call_args
    params = call_args[1]["params"]
    assert ("arbeitszeit", "vz") in params


def test_search_jobs_without_arbeitszeit_filter(
    mock_http_client, mock_config, sample_api_response_page1
):
    """Test that arbeitszeit parameter is omitted when not specified"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    search_jobs(
        was="Developer",
        wo="Berlin",
        arbeitszeit="",  # Empty string
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Verify arbeitszeit was NOT included in params
    call_args = mock_http_client.get.call_args
    params = call_args[1]["params"]
    arbeitszeit_params = [p for p in params if p[0] == "arbeitszeit"]
    assert len(arbeitszeit_params) == 0


def test_search_jobs_config_defaults(mock_http_client, mock_config, sample_api_response_page1):
    """Test that config defaults are used when parameters not specified"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    # Don't specify size, max_pages, or umkreis - should use config defaults
    search_jobs(was="Developer", wo="Berlin", http_client=mock_http_client, config_obj=mock_config)

    # Verify config defaults were used
    call_args = mock_http_client.get.call_args
    params = dict(call_args[1]["params"])
    assert params["size"] == 50  # From mock_config
    assert params["umkreis"] == 25  # From mock_config


def test_search_jobs_parameter_override(mock_http_client, mock_config, sample_api_response_page1):
    """Test that explicit parameters override config defaults"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    search_jobs(
        was="Developer",
        wo="Berlin",
        size=25,  # Override config default of 50
        umkreis=50,  # Override config default of 25
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Verify overrides were used
    call_args = mock_http_client.get.call_args
    params = dict(call_args[1]["params"])
    assert params["size"] == 25
    assert params["umkreis"] == 50


def test_search_jobs_session_integration(mock_http_client, mock_config, sample_api_response_page1):
    """Test that raw API responses are saved when session is provided"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = sample_api_response_page1
    mock_http_client.get.return_value = mock_response

    # Create mock session
    mock_session = Mock()

    search_jobs(
        was="Developer",
        wo="Berlin",
        max_pages=1,
        session=mock_session,
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Verify session.save_raw_api_response was called
    mock_session.save_raw_api_response.assert_called_once()

    # Verify the saved data structure
    saved_data = mock_session.save_raw_api_response.call_args[0][0]
    assert "search_params" in saved_data
    assert "pages" in saved_data
    assert "total_jobs_found" in saved_data
    assert saved_data["total_jobs_found"] == 2  # 2 jobs after filtering


def test_search_jobs_stops_at_max_results(mock_http_client, mock_config):
    """Test that search stops when all available results are fetched"""
    # API says there are only 2 results total
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "maxErgebnisse": "2",  # Only 2 total results
        "stellenangebote": [
            {
                "beruf": "Job 1",
                "arbeitsort": {"ort": "Berlin"},
                "arbeitgeber": "A",
                "refnr": "1",
                "externeUrl": "url1",
            },
            {
                "beruf": "Job 2",
                "arbeitsort": {"ort": "Berlin"},
                "arbeitgeber": "B",
                "refnr": "2",
                "externeUrl": "url2",
            },
        ],
    }
    mock_http_client.get.return_value = mock_response

    # Request 5 pages, but should stop after 1
    results = search_jobs(
        was="Developer",
        wo="Berlin",
        max_pages=5,
        exclude_weiterbildung=False,
        http_client=mock_http_client,
        config_obj=mock_config,
    )

    # Should have 2 results
    assert len(results) == 2
    # Should only make 1 HTTP call (stops because we got all available results)
    assert mock_http_client.get.call_count == 1


# Tests for simplify_job_data()


def test_simplify_job_data_basic():
    """Test basic job data simplification"""
    jobs = [
        {
            "beruf": "Software Developer",
            "arbeitsort": {"ort": "Berlin", "region": "Berlin"},
            "arbeitgeber": "Tech Corp",
            "refnr": "12345",
            "externeUrl": "https://example.com/job1",
            "extra_field": "ignored",
        }
    ]

    simplified = simplify_job_data(jobs)

    assert len(simplified) == 1
    assert simplified[0]["titel"] == "Software Developer"
    assert simplified[0]["ort"] == "Berlin"
    assert simplified[0]["arbeitgeber"] == "Tech Corp"
    assert simplified[0]["refnr"] == "12345"
    assert simplified[0]["externeUrl"] == "https://example.com/job1"
    assert "extra_field" not in simplified[0]


def test_simplify_job_data_missing_arbeitsort():
    """Test handling of missing or non-dict arbeitsort"""
    jobs = [
        {
            "beruf": "Developer",
            "arbeitsort": "Berlin",  # Not a dict
            "arbeitgeber": "Corp",
            "refnr": "123",
            "externeUrl": "url",
        },
        {
            "beruf": "Engineer",
            # arbeitsort missing entirely
            "arbeitgeber": "Inc",
            "refnr": "456",
            "externeUrl": "url2",
        },
    ]

    simplified = simplify_job_data(jobs)

    assert len(simplified) == 2
    assert simplified[0]["ort"] == ""  # Non-dict arbeitsort
    assert simplified[1]["ort"] == ""  # Missing arbeitsort


def test_simplify_job_data_empty_list():
    """Test simplifying empty job list"""
    simplified = simplify_job_data([])
    assert simplified == []


def test_simplify_job_data_multiple_jobs():
    """Test simplifying multiple jobs"""
    jobs = [
        {
            "beruf": "Job 1",
            "arbeitsort": {"ort": "Berlin"},
            "arbeitgeber": "Company A",
            "refnr": "1",
            "externeUrl": "url1",
        },
        {
            "beruf": "Job 2",
            "arbeitsort": {"ort": "Hamburg"},
            "arbeitgeber": "Company B",
            "refnr": "2",
            "externeUrl": "url2",
        },
        {
            "beruf": "Job 3",
            "arbeitsort": {"ort": "Munich"},
            "arbeitgeber": "Company C",
            "refnr": "3",
            "externeUrl": "url3",
        },
    ]

    simplified = simplify_job_data(jobs)

    assert len(simplified) == 3
    assert [j["titel"] for j in simplified] == ["Job 1", "Job 2", "Job 3"]
    assert [j["ort"] for j in simplified] == ["Berlin", "Hamburg", "Munich"]
