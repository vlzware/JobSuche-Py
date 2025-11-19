"""
Pytest configuration and fixtures for error scenario tests
"""

import os

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


@pytest.fixture
def cli_test_env(tmp_path):
    """
    Environment variables for CLI subprocess tests.

    Sets JOBSUCHE_SEARCHES_DIR and JOBSUCHE_DATABASE_PATH to temporary
    directories to prevent pollution of the project's data directories.

    Usage:
        def test_something(cli_test_env):
            result = subprocess.run(
                ["python", "main.py", ...],
                env=cli_test_env,
                ...
            )
    """
    env = os.environ.copy()
    env["JOBSUCHE_SEARCHES_DIR"] = str(tmp_path / "test_searches")
    env["JOBSUCHE_DATABASE_PATH"] = str(tmp_path / "test_database" / "jobs.json")
    return env
