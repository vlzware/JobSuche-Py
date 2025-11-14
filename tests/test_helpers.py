"""
Shared test utilities and mock factories

This module provides reusable mock factories and helpers to reduce code duplication
across test files.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock


def create_mock_http_client(status_code=200, response_data=None, json_response=None):
    """
    Factory for creating mock HTTP clients

    Args:
        status_code: HTTP status code to return (default: 200)
        response_data: Response text/content (optional)
        json_response: JSON response data (optional)

    Returns:
        Mock HTTP client with configured responses
    """
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = status_code

    if response_data is not None:
        mock_response.text = response_data
        mock_response.content = (
            response_data.encode() if isinstance(response_data, str) else response_data
        )

    if json_response is not None:
        mock_response.json.return_value = json_response

    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response

    return mock_client


def create_mock_session(tmp_path=None, base_dir="/tmp/test"):
    """
    Factory for creating mock SearchSession objects

    Args:
        tmp_path: pytest tmp_path fixture (optional)
        base_dir: Base directory for session (default: /tmp/test)

    Returns:
        Mock SearchSession with common attributes
    """
    mock_session = MagicMock()

    if tmp_path:
        mock_session.session_dir = tmp_path / "session"
        mock_session.debug_dir = tmp_path / "session" / "debug"
        # Create the directories for tests that actually write files
        mock_session.debug_dir.mkdir(parents=True, exist_ok=True)
    else:
        mock_session.session_dir = Path(base_dir)
        mock_session.debug_dir = Path(base_dir) / "debug"

    # Common return values
    mock_session.save_classified_jobs.return_value = mock_session.session_dir / "jobs.json"
    mock_session.save_analysis_report.return_value = mock_session.session_dir / "report.txt"
    mock_session.save_csv_export.return_value = mock_session.session_dir / "export.csv"
    mock_session.has_checkpoint.return_value = False
    mock_session.load_checkpoint.return_value = None
    mock_session.load_partial_results.return_value = []

    return mock_session


def create_test_config(**overrides):
    """
    Factory for creating test configuration dictionaries

    Args:
        **overrides: Config values to override defaults

    Returns:
        Configuration dictionary with sensible test defaults
    """
    config = {
        "api": {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {
                "search": 30,
                "detail_fetch": 45,
                "classification": 60,
                "mega_batch_classification": 120,
            },
        },
        "scraper": {
            "headers": {
                "User-Agent": "Mozilla/5.0 (Test)",
                "Accept": "text/html,application/xhtml+xml",
            },
            "retry": {
                "max_attempts": 3,
                "backoff_factor": 1.0,
            },
        },
        "llm": {
            "models": {
                "default": "test-model",
            },
            "inference": {
                "temperature": 0.1,
                "max_tokens": 4000,
            },
        },
        "processing": {
            "limits": {
                "job_text_single_job": 3000,
                "job_text_batch": 1000,
                "job_text_mega_batch": 25000,
                "max_jobs_per_mega_batch": 100,
            }
        },
    }

    # Apply overrides using nested dict merge
    _deep_merge(config, overrides)

    return config


def _deep_merge(base_dict, override_dict):
    """Recursively merge override_dict into base_dict"""
    for key, value in override_dict.items():
        if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
            _deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value


def create_mock_user_profile(categories=None, category_definitions=None, has_cv=False):
    """
    Factory for creating mock UserProfile objects

    Args:
        categories: List of categories (default: ["Python", "Java", "DevOps", "Andere"])
        category_definitions: Dict of category definitions (optional)
        has_cv: Whether profile has a CV (default: False)

    Returns:
        Mock UserProfile with get_categories(), get_category_definitions(), and has_cv()
    """
    from src.preferences import UserProfile

    mock_profile = MagicMock(spec=UserProfile)
    default_categories = ["Python", "Java", "DevOps", "Andere"]
    default_definitions = {
        "Python": "Python development roles",
        "Java": "Java development roles",
        "DevOps": "DevOps and infrastructure roles",
    }

    mock_profile.categories = categories or default_categories
    mock_profile.get_categories.return_value = categories or default_categories
    mock_profile.get_category_definitions.return_value = (
        category_definitions if category_definitions is not None else default_definitions
    )
    mock_profile.has_cv.return_value = has_cv
    return mock_profile


def create_mock_llm_processor(classification_result=None):
    """
    Factory for creating mock LLMProcessor objects

    Args:
        classification_result: Default classification result to return

    Returns:
        Mock LLMProcessor with spec
    """
    from src.llm import LLMProcessor

    mock_processor = MagicMock(spec=LLMProcessor)

    if classification_result is not None:
        mock_processor.classify_multi_category.return_value = classification_result

    return mock_processor


def create_sample_jobs(count=3):
    """
    Factory for creating sample job data for testing

    Args:
        count: Number of jobs to create (default: 3)

    Returns:
        List of sample job dictionaries
    """
    jobs = [
        {
            "titel": "Python Developer",
            "ort": "Berlin",
            "arbeitgeber": "Tech Corp",
            "text": "Python, Django, REST API development",
            "url": "http://example.com/1",
            "refnr": "REF001",
        },
        {
            "titel": "Java Developer",
            "ort": "München",
            "arbeitgeber": "Enterprise GmbH",
            "text": "Java, Spring Boot, Microservices",
            "url": "http://example.com/2",
            "refnr": "REF002",
        },
        {
            "titel": "DevOps Engineer",
            "ort": "Hamburg",
            "arbeitgeber": "Cloud Solutions",
            "text": "AWS, Terraform, Docker, Kubernetes",
            "url": "http://example.com/3",
            "refnr": "REF003",
        },
    ]

    return jobs[:count]


def create_classified_jobs(count=2):
    """
    Factory for creating sample classified job data

    Args:
        count: Number of classified jobs to create (default: 2)

    Returns:
        List of classified job dictionaries
    """
    jobs = [
        {
            "titel": "Python Developer",
            "ort": "Berlin",
            "arbeitgeber": "Tech Corp",
            "text": "Python, Django, REST API development",
            "url": "http://example.com/1",
            "refnr": "REF001",
            "categories": ["Python", "Backend"],
        },
        {
            "titel": "Java Developer",
            "ort": "München",
            "arbeitgeber": "Enterprise GmbH",
            "text": "Java, Spring Boot, Microservices",
            "url": "http://example.com/2",
            "refnr": "REF002",
            "categories": ["Java", "Backend"],
        },
    ]

    return jobs[:count]
