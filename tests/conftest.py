"""
Pytest configuration and shared fixtures for JobSuche tests
"""

from pathlib import Path

import pytest


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
    """Return a test configuration dictionary"""
    return {
        "scraper": {
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
            "headers": {"user_agent": "JobSuche-Test/1.0"},
        },
        "api": {"timeouts": {"arbeitsagentur_details": 10, "external_url": 15}},
    }
