"""
Tests for single-job classification

These tests verify single job classification logic and response handling.
Batch and mega-batch tests are in test_classifier_batch.py
"""

from unittest.mock import Mock, patch

import pytest

from src.classifier import (
    DEFAULT_CATEGORIES,
    build_category_guidance,
    classify_job_description,
    classify_jobs,
    load_category_config,
)
from src.config.loader import Config
from tests.test_helpers import create_mock_http_client, create_test_config


class TestCategoryGuidance:
    """Test category guidance building"""

    def test_build_category_guidance_with_definitions(self):
        """Should build guidance from category definitions"""
        categories = ["Java", "Python", "Andere"]
        definitions = {
            "Java": "Use for jobs requiring Java, Spring Boot, or JEE",
            "Python": "Use for jobs requiring Python, Django, or FastAPI",
        }

        result = build_category_guidance(categories, definitions)

        assert "IMPORTANT: Use for jobs requiring Java" in result
        assert "IMPORTANT: Use for jobs requiring Python" in result
        assert "Andere" not in result  # No definition for Andere

    def test_build_category_guidance_no_definitions(self):
        """Should return empty string when no definitions provided"""
        categories = ["Java", "Python"]
        result = build_category_guidance(categories, None)
        assert result == ""


class TestClassifyJobDescription:
    """Test single job classification"""

    def test_classify_job_description_success(self):
        """Should classify job and return matching categories"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [{"message": {"content": '["Java", "Agile Projektentwicklung"]'}}]
            },
        )

        job_text = "Senior Java Developer with Scrum experience needed..."
        result = classify_job_description(
            job_text=job_text,
            categories=DEFAULT_CATEGORIES,
            api_key="test-key",
            http_client=mock_client,
            config_obj=config,
        )

        assert result == ["Java", "Agile Projektentwicklung"]
        mock_client.post.assert_called_once()

    def test_classify_job_description_validates_categories(self):
        """Should filter out invalid categories from LLM response"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [{"message": {"content": '["Java", "InvalidCategory", "Python"]'}}]
            },
        )

        result = classify_job_description(
            job_text="Test",
            categories=["Java", "Python", "Andere"],
            api_key="test-key",
            http_client=mock_client,
            config_obj=config,
        )

        # Should only include valid categories
        assert "Java" in result
        assert "Python" in result
        assert "InvalidCategory" not in result

    def test_classify_job_description_truncates_long_text(self):
        """Should truncate job text to max_chars limit"""
        config_dict = create_test_config()
        config_dict["processing"]["limits"]["job_text_single_job"] = 100
        config = Config(config_dict)

        mock_client = create_mock_http_client(
            status_code=200, json_response={"choices": [{"message": {"content": '["Andere"]'}}]}
        )

        long_text = "A" * 500  # 500 chars

        classify_job_description(
            job_text=long_text,
            categories=["Java"],
            api_key="test-key",
            http_client=mock_client,
            config_obj=config,
        )

        # Check that prompt was truncated
        call_args = mock_client.post.call_args
        prompt_content = call_args[1]["json"]["messages"][0]["content"]

        # Verify the prompt contains exactly 100 A's (truncated version)
        assert "A" * 100 in prompt_content, "Prompt should contain 100 A's (truncated)"
        assert "A" * 101 not in prompt_content, "Prompt should NOT contain more than 100 A's"

    def test_classify_job_description_raises_on_api_error(self):
        """Should raise exception when API call fails (no silent failures!)"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(status_code=500)
        mock_client.post.return_value.text = "Internal Server Error"

        # Should raise exception, not return ["Andere"]
        with pytest.raises(Exception) as exc_info:
            classify_job_description(
                job_text="Test job",
                categories=["Java", "Python"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=config,
            )

        assert "500" in str(exc_info.value)

    def test_classify_job_description_handles_malformed_json(self):
        """Should raise exception on malformed JSON (no silent failures!)"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [{"message": {"content": "This job is definitely Java related"}}]
            },
        )

        # Should raise LLMResponseError on malformed JSON
        from src.exceptions import LLMResponseError

        with pytest.raises(LLMResponseError) as exc_info:
            classify_job_description(
                job_text="Java developer needed",
                categories=["Java", "Python", "Andere"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=config,
            )

        assert "JSON array brackets" in str(exc_info.value)


class TestClassifyJobs:
    """Test classify_jobs() function - classifies multiple jobs"""

    def test_classify_jobs_basic(self):
        """Should classify multiple jobs and add categories"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200, json_response={"choices": [{"message": {"content": '["Python"]'}}]}
        )

        jobs = [
            {"titel": "Python Dev", "text": "Looking for Python developer..."},
            {"titel": "Java Dev", "text": "Looking for Java engineer..."},
        ]

        result = classify_jobs(
            jobs=jobs,
            categories=["Python", "Java", "Andere"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        assert len(result) == 2
        assert all("categories" in job for job in result)
        assert result[0]["categories"] == ["Python"]
        assert result[1]["categories"] == ["Python"]

    def test_classify_jobs_missing_api_key_raises(self):
        """Should raise ValueError when API key not provided"""
        config = Config(create_test_config())
        jobs = [{"titel": "Job", "text": "Content"}]

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                classify_jobs(
                    jobs=jobs,
                    categories=["Python"],
                    api_key=None,  # No API key
                    http_client=Mock(),
                    config_obj=config,
                )

            assert "OpenRouter API key not provided" in str(exc_info.value)

    def test_classify_jobs_handles_empty_text(self):
        """Should raise exception on jobs with no text (no silent failures!)"""
        config = Config(create_test_config())
        jobs = [
            {"titel": "Job 1", "text": ""},
            {"titel": "Job 2"},  # No text field
        ]

        # Should raise EmptyJobContentError on empty text
        from src.exceptions import EmptyJobContentError

        with pytest.raises(EmptyJobContentError) as exc_info:
            classify_jobs(
                jobs=jobs,
                categories=["Python", "Andere"],
                api_key="test-key",
                verbose=False,
                http_client=Mock(),
                config_obj=config,
            )

        assert "no text content" in str(exc_info.value).lower()

    def test_classify_jobs_preserves_original_job_data(self):
        """Should preserve all original job fields"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200, json_response={"choices": [{"message": {"content": '["Python"]'}}]}
        )

        jobs = [
            {
                "titel": "Python Dev",
                "text": "Developer needed",
                "ort": "Berlin",
                "arbeitgeber": "Company",
                "refnr": "123",
                "url": "https://example.com",
            }
        ]

        result = classify_jobs(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # All original fields should be preserved
        assert result[0]["titel"] == "Python Dev"
        assert result[0]["ort"] == "Berlin"
        assert result[0]["arbeitgeber"] == "Company"
        assert result[0]["refnr"] == "123"
        assert result[0]["url"] == "https://example.com"
        assert result[0]["categories"] == ["Python"]


class TestLoadCategoryConfig:
    """Test category config loading from YAML"""

    def test_load_category_config_file_not_found(self):
        """Should return (None, {}) when config file doesn't exist"""
        categories, definitions = load_category_config("/nonexistent/path.yaml")
        assert categories is None
        assert definitions == {}

    def test_load_category_config_with_valid_yaml(self, tmp_path):
        """Should load categories and definitions from YAML file"""
        yaml_content = """
categories:
  - name: "Python"
    description: "Python development jobs"
  - name: "Java"
    description: "Java development jobs"
  - name: "Andere"
"""
        yaml_file = tmp_path / "categories.yaml"
        yaml_file.write_text(yaml_content)

        categories, definitions = load_category_config(str(yaml_file))

        assert categories == ["Python", "Java", "Andere"]
        assert definitions["Python"] == "Python development jobs"
        assert definitions["Java"] == "Java development jobs"
        assert "Andere" not in definitions  # No description

    def test_load_category_config_without_descriptions(self, tmp_path):
        """Should handle categories without descriptions"""
        yaml_content = """
categories:
  - name: "Python"
  - name: "Java"
"""
        yaml_file = tmp_path / "categories.yaml"
        yaml_file.write_text(yaml_content)

        categories, definitions = load_category_config(str(yaml_file))

        assert categories == ["Python", "Java"]
        assert definitions == {}
