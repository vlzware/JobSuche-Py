"""
Pytest configuration and fixtures for error scenario tests
"""

import pytest


@pytest.fixture
def test_config():
    """Minimal test configuration"""
    return {
        "api": {"timeouts": {"classification": 60, "scraping": 10}, "delays": {"scraping": 0.1}},
        "processing": {"limits": {"job_text_single_job": 3000, "max_jobs_per_mega_batch": 100}},
    }


@pytest.fixture
def sample_job():
    """Sample job data for testing"""
    return {
        "refnr": "12345",
        "titel": "Software Developer",
        "arbeitgeber": "Test Company GmbH",
        "arbeitsort": {"ort": "Berlin"},
        "text": "Job description text here",
        "details": {"url": "https://example.com/job/12345"},
    }
