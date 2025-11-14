"""
Pytest configuration and shared fixtures for JobSuche tests
"""

from pathlib import Path

import pytest

from src.config.loader import Config
from tests.test_helpers import (
    create_classified_jobs,
    create_mock_http_client,
    create_mock_llm_processor,
    create_mock_session,
    create_mock_user_profile,
    create_sample_jobs,
    create_test_config,
)


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (makes real network calls, slow, expensive)",
    )


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture(fixtures_dir):
    """Factory fixture to load HTML fixtures by name"""

    def _load(filename):
        filepath = fixtures_dir / filename
        with open(filepath, encoding="utf-8") as f:
            return f.read()

    return _load


@pytest.fixture
def test_config():
    """Return a test configuration dictionary with sensible defaults"""
    config = create_test_config()

    # Merge in scraper-specific config for backward compatibility
    config["scraper"].update(
        {
            "html_cleanup": {"remove_tags": ["script", "style", "nav", "header", "footer"]},
            "arbeitsagentur": {"content_selector": "jb-steadetail-beschreibung"},
            "external": {
                "content_selectors": {
                    "primary": "main",
                    "secondary": "article",
                    "content_pattern": "(content|job|detail|description)",
                    "id_pattern": "(content|job|detail|main)",
                }
            },
        }
    )
    config["api"]["timeouts"].update({"arbeitsagentur_details": 10, "external_url": 15})

    return config


@pytest.fixture
def config_obj(test_config):
    """Provide a Config object from test_config"""
    return Config(test_config)


@pytest.fixture
def mock_http_client():
    """Provide a mock HTTP client with successful response"""
    return create_mock_http_client(status_code=200)


@pytest.fixture
def mock_session(tmp_path):
    """Provide a mock SearchSession"""
    return create_mock_session(tmp_path)


@pytest.fixture
def mock_user_profile():
    """Provide a mock UserProfile"""
    return create_mock_user_profile()


@pytest.fixture
def mock_llm_processor():
    """Provide a mock LLMProcessor"""
    return create_mock_llm_processor()


@pytest.fixture
def sample_jobs():
    """Provide sample job data for testing"""
    return create_sample_jobs()


@pytest.fixture
def classified_jobs():
    """Provide sample classified job data for testing"""
    return create_classified_jobs()
