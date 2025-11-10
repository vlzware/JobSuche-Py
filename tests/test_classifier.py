"""
Tests for the classifier module

These tests verify:
1. Category classification logic
2. Config loading for categories
3. Truncation handling and warnings
4. HTTP client integration
"""

import json
from unittest.mock import Mock, patch

import pytest

from src.classifier import (
    DEFAULT_CATEGORIES,
    build_category_guidance,
    classify_job_description,
    classify_jobs,
    classify_jobs_batch,
    classify_jobs_mega_batch,
    load_category_config,
)
from src.config.loader import Config


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

    def test_build_category_guidance_empty_definitions(self):
        """Should return empty string for empty definitions dict"""
        categories = ["Java", "Python"]
        definitions: dict[str, str] = {}

        result = build_category_guidance(categories, definitions)

        assert result == ""


class TestClassifyJobDescription:
    """Test single job classification"""

    def test_classify_job_description_success(self, test_config):
        """Should classify job and return matching categories"""
        # Mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '["Java", "Agile Projektentwicklung"]'}}]
        }
        mock_client.post.return_value = mock_response

        config = Config(test_config)
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

    def test_classify_job_description_calls_openrouter_api(self, test_config):
        """Should make POST request to OpenRouter API with correct payload"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Java"]'}}]}
        mock_client.post.return_value = mock_response

        test_config["api"] = {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {"classification": 30},
        }
        config = Config(test_config)

        classify_job_description(
            job_text="Test job",
            categories=["Java", "Python"],
            api_key="test-api-key",
            http_client=mock_client,
            config_obj=config,
        )

        # Verify API call
        call_args = mock_client.post.call_args
        assert call_args[1]["url"] == "https://openrouter.ai/api/v1/chat/completions"
        assert call_args[1]["headers"]["Authorization"] == "Bearer test-api-key"
        assert call_args[1]["json"]["model"]  # Some model specified
        assert "messages" in call_args[1]["json"]

    def test_classify_job_description_raises_on_api_error(self, test_config):
        """Should raise exception when API call fails (no silent failures!)"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response

        config = Config(test_config)

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

    def test_classify_job_description_handles_malformed_json(self, test_config):
        """Should raise exception on malformed JSON (no silent failures!)"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "This job is definitely Java related"  # Not JSON
                    }
                }
            ]
        }
        mock_client.post.return_value = mock_response

        config = Config(test_config)

        # Should raise LLMResponseError on malformed JSON, not fall back to keyword matching
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

    def test_classify_job_description_validates_categories(self, test_config):
        """Should filter out invalid categories from LLM response"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '["Java", "InvalidCategory", "Python"]'}}]
        }
        mock_client.post.return_value = mock_response

        config = Config(test_config)

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

    def test_classify_job_description_truncates_long_text(self, test_config):
        """Should truncate job text to max_chars limit"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Andere"]'}}]}
        mock_client.post.return_value = mock_response

        test_config["processing"] = {"limits": {"job_text_single_job": 100}}
        config = Config(test_config)

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

        # Verify original text was indeed long
        assert len(long_text) == 500

        # Verify the prompt contains exactly 100 A's (truncated version)
        # The prompt should have the job text truncated to max 100 chars
        assert "A" * 100 in prompt_content, "Prompt should contain 100 A's (truncated)"
        assert "A" * 101 not in prompt_content, "Prompt should NOT contain more than 100 A's"


class TestConfigIntegration:
    """Test config integration with classifier"""

    def test_classifier_uses_config_temperature(self, test_config):
        """Should use temperature from config"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Andere"]'}}]}
        mock_client.post.return_value = mock_response

        test_config["llm"] = {"inference": {"temperature": 0.5}}
        config = Config(test_config)

        classify_job_description(
            job_text="Test",
            categories=["Java"],
            api_key="test-key",
            http_client=mock_client,
            config_obj=config,
        )

        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["temperature"] == 0.5

    def test_classifier_uses_config_timeout(self, test_config):
        """Should use timeout from config"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Andere"]'}}]}
        mock_client.post.return_value = mock_response

        test_config["api"] = {"timeouts": {"classification": 45}}
        config = Config(test_config)

        classify_job_description(
            job_text="Test",
            categories=["Java"],
            api_key="test-key",
            http_client=mock_client,
            config_obj=config,
        )

        call_args = mock_client.post.call_args
        assert call_args[1]["timeout"] == 45


class TestTruncationReportSaving:
    """Test that truncation reports are properly saved to debug files"""

    def test_truncation_report_saved_when_jobs_truncated(self, test_config, tmp_path):
        """Should save truncation_report.json when jobs are truncated"""
        # Mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200

        # Mock API response with classification results in line format
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Java\n[JOB_001] → Python"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        mock_client.post.return_value = mock_response

        # Create test config with very low character limit to force truncation
        test_config["processing"] = {
            "limits": {
                "job_text_mega_batch": 50  # Very low to force truncation
            }
        }
        test_config["api"] = {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {"classification": 30},
        }
        test_config["llm"] = {"inference": {"temperature": 0, "model": "test-model"}}
        config = Config(test_config)

        # Create mock session with debug_dir
        mock_session = Mock()
        mock_session.debug_dir = tmp_path

        # Create jobs with text that will be truncated
        jobs = [
            {
                "titel": "Job 1",
                "text": "A" * 500,  # Long text that will be truncated
                "refnr": "123",
            },
            {
                "titel": "Job 2",
                "text": "B" * 500,  # Long text that will be truncated
                "refnr": "456",
            },
        ]

        # Call classify_jobs_mega_batch
        classify_jobs_mega_batch(
            jobs=jobs,
            categories=["Java", "Python", "Andere"],
            api_key="test-key",
            session=mock_session,
            http_client=mock_client,
            config_obj=config,
        )

        # Verify truncation_report.json was created
        truncation_file = tmp_path / "truncation_report.json"
        assert truncation_file.exists(), "truncation_report.json should be created"

        # Verify the content of the truncation report
        with open(truncation_file, encoding="utf-8") as f:
            truncation_data = json.load(f)

        assert truncation_data["jobs_truncated"] > 0
        assert truncation_data["total_jobs"] == 2
        assert "truncated_jobs" in truncation_data
        assert len(truncation_data["truncated_jobs"]) > 0
        # Verify structure of truncated_jobs entries
        first_job = truncation_data["truncated_jobs"][0]
        assert "index" in first_job
        assert "job_id" in first_job
        assert "title" in first_job
        assert "original_length" in first_job
        assert "truncated_length" in first_job
        assert "loss" in first_job

    def test_truncation_report_not_saved_when_no_truncation(self, test_config, tmp_path):
        """Should not save truncation_report.json when no jobs are truncated"""
        # Mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200

        # Mock API response with classification results in line format
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Java"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        mock_client.post.return_value = mock_response

        # Create test config with high character limit (no truncation)
        test_config["processing"] = {
            "limits": {
                "job_text_mega_batch": 10000  # High enough to avoid truncation
            }
        }
        test_config["api"] = {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {"classification": 30},
        }
        test_config["llm"] = {"inference": {"temperature": 0, "model": "test-model"}}
        config = Config(test_config)

        # Create mock session with debug_dir
        mock_session = Mock()
        mock_session.debug_dir = tmp_path

        # Create jobs with short text that won't be truncated
        jobs = [{"titel": "Job 1", "text": "Short description", "refnr": "123"}]

        # Call classify_jobs_mega_batch
        classify_jobs_mega_batch(
            jobs=jobs,
            categories=["Java", "Python", "Andere"],
            api_key="test-key",
            session=mock_session,
            http_client=mock_client,
            config_obj=config,
        )

        # Verify truncation_report.json was NOT created
        truncation_file = tmp_path / "truncation_report.json"
        assert (
            not truncation_file.exists()
        ), "truncation_report.json should not be created when no truncation"

    def test_truncation_report_not_saved_when_no_session(self, test_config):
        """Should not crash when session is None"""
        # Mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200

        # Mock API response with classification results in line format
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Java"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        mock_client.post.return_value = mock_response

        # Create test config with very low character limit to force truncation
        test_config["processing"] = {"limits": {"job_text_mega_batch": 50}}
        test_config["api"] = {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {"classification": 30},
        }
        test_config["llm"] = {"inference": {"temperature": 0, "model": "test-model"}}
        config = Config(test_config)

        # Create jobs with text that will be truncated
        jobs = [{"titel": "Job 1", "text": "A" * 500, "refnr": "123"}]

        # Call classify_jobs_mega_batch with no session - should not crash
        result = classify_jobs_mega_batch(
            jobs=jobs,
            categories=["Java", "Python", "Andere"],
            api_key="test-key",
            session=None,  # No session
            http_client=mock_client,
            config_obj=config,
        )

        # Should complete without error
        assert len(result) == 1


class TestClassifyJobs:
    """Test classify_jobs() function - classifies multiple jobs"""

    def test_classify_jobs_basic(self, test_config):
        """Should classify multiple jobs and add categories"""
        # Mock HTTP client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Python"]'}}]}
        mock_client.post.return_value = mock_response

        jobs = [
            {"titel": "Python Dev", "text": "Looking for Python developer..."},
            {"titel": "Java Dev", "text": "Looking for Java engineer..."},
        ]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 3000}}
        config = Config(test_config)

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

    def test_classify_jobs_missing_api_key_raises(self, test_config):
        """Should raise ValueError when API key not provided"""
        jobs = [{"titel": "Job", "text": "Content"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 3000}}
        config = Config(test_config)

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

    def test_classify_jobs_uses_env_var_for_api_key(self, test_config):
        """Should use OPENROUTER_API_KEY environment variable"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Python"]'}}]}
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Job", "text": "Python developer"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 3000}}
        config = Config(test_config)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "env-api-key"}):
            result = classify_jobs(
                jobs=jobs,
                categories=["Python"],
                api_key=None,  # Should use env var
                verbose=False,
                http_client=mock_client,
                config_obj=config,
            )

        assert len(result) == 1
        # Verify it used the env var by checking the call was made
        assert mock_client.post.called

    def test_classify_jobs_handles_empty_text(self, test_config):
        """Should raise exception on jobs with no text (no silent failures!)"""
        jobs = [
            {"titel": "Job 1", "text": ""},
            {"titel": "Job 2"},  # No text field
        ]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 3000}}
        config = Config(test_config)

        # Should raise EmptyJobContentError on empty text, not silently assign "Andere"
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

    def test_classify_jobs_truncation_handling(self, test_config):
        """Should detect and log truncation"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Python"]'}}]}
        mock_client.post.return_value = mock_response

        # Job with very long text
        long_text = "Python developer " * 500  # ~8000 chars
        jobs = [{"titel": "Job 1", "text": long_text}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 100}}  # Low limit
        config = Config(test_config)

        result = classify_jobs(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should mark as truncated
        assert result[0]["was_truncated"]
        assert result[0]["original_length"] == len(long_text)
        assert result[0]["truncated_to"] == 100

    def test_classify_jobs_no_truncation(self, test_config):
        """Should mark jobs as not truncated when text is short enough"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Python"]'}}]}
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Job 1", "text": "Short text"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 3000}}
        config = Config(test_config)

        result = classify_jobs(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        assert not result[0]["was_truncated"]
        assert "original_length" not in result[0]
        assert "truncated_to" not in result[0]

    def test_classify_jobs_preserves_original_job_data(self, test_config):
        """Should preserve all original job fields"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Python"]'}}]}
        mock_client.post.return_value = mock_response

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

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 3000}}
        config = Config(test_config)

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

    def test_classify_jobs_uses_default_categories(self, test_config):
        """Should use DEFAULT_CATEGORIES when none provided"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": '["Andere"]'}}]}
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Job", "text": "Text"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_single_job": 3000}}
        config = Config(test_config)

        with patch("src.classifier.load_category_config", return_value=(None, {})):
            result = classify_jobs(
                jobs=jobs,
                categories=None,  # Should use defaults
                api_key="test-key",
                verbose=False,
                http_client=mock_client,
                config_obj=config,
            )

        # Should complete successfully
        assert len(result) == 1


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

    def test_load_category_config_malformed_yaml(self, tmp_path):
        """Should handle malformed YAML gracefully"""
        yaml_content = "invalid: yaml: content:"
        yaml_file = tmp_path / "categories.yaml"
        yaml_file.write_text(yaml_content)

        categories, definitions = load_category_config(str(yaml_file))

        # Should return defaults on error
        assert categories is None or categories == []
        assert definitions == {} or isinstance(definitions, dict)

    def test_load_category_config_empty_file(self, tmp_path):
        """Should handle empty YAML file"""
        yaml_file = tmp_path / "categories.yaml"
        yaml_file.write_text("")

        categories, definitions = load_category_config(str(yaml_file))

        assert categories is None
        assert definitions == {}


class TestClassifyJobsBatch:
    """Test classify_jobs_batch() function - batch classification"""

    def test_classify_jobs_batch_basic(self, test_config):
        """Should classify multiple jobs in a single batch"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": """[JOB_000] → Python
[JOB_001] → Java
[JOB_002] → Python"""
                    }
                }
            ]
        }
        mock_client.post.return_value = mock_response

        jobs = [
            {"titel": "Python Dev", "text": "Python developer needed"},
            {"titel": "Java Dev", "text": "Java engineer required"},
            {"titel": "Python Senior", "text": "Senior Python position"},
        ]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        result = classify_jobs_batch(
            jobs=jobs,
            categories=["Python", "Java", "Andere"],
            api_key="test-key",
            batch_size=5,
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        assert len(result) == 3
        assert result[0]["categories"] == ["Python"]
        assert result[1]["categories"] == ["Java"]
        assert result[2]["categories"] == ["Python"]

    def test_classify_jobs_batch_multiple_batches(self, test_config):
        """Should process jobs in multiple batches"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200

        # First batch response
        response1 = Mock()
        response1.status_code = 200
        response1.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Python\n[JOB_001] → Java"}}]
        }

        # Second batch response
        response2 = Mock()
        response2.status_code = 200
        response2.json.return_value = {"choices": [{"message": {"content": "[JOB_000] → Python"}}]}

        mock_client.post.side_effect = [response1, response2]

        jobs = [
            {"titel": "Job 1", "text": "Text 1"},
            {"titel": "Job 2", "text": "Text 2"},
            {"titel": "Job 3", "text": "Text 3"},
        ]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        result = classify_jobs_batch(
            jobs=jobs,
            categories=["Python", "Java"],
            api_key="test-key",
            batch_size=2,  # Small batch size to force multiple batches
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should have made 2 API calls
        assert mock_client.post.call_count == 2
        assert len(result) == 3

    def test_classify_jobs_batch_truncation_warning(self, test_config):
        """Should warn about truncated jobs in batch"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Python"}}]
        }
        mock_client.post.return_value = mock_response

        long_text = "Python " * 1000  # Very long text
        jobs = [{"titel": "Job 1", "text": long_text}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 100}}  # Low limit
        config = Config(test_config)

        result = classify_jobs_batch(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should still complete successfully
        assert len(result) == 1

    def test_classify_jobs_batch_missing_api_key_raises(self, test_config):
        """Should raise ValueError when API key not provided"""
        jobs = [{"titel": "Job", "text": "Content"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                classify_jobs_batch(
                    jobs=jobs,
                    categories=["Python"],
                    api_key=None,
                    http_client=Mock(),
                    config_obj=config,
                )

            assert "API key required" in str(exc_info.value)

    def test_classify_jobs_batch_handles_malformed_response(self, test_config):
        """Should raise exception on malformed batch responses (NO SILENT FAILURES!)"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Invalid format - missing job IDs"}}]
        }
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Job 1", "text": "Text"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        # Should raise exception instead of silently returning ["Andere"]
        with pytest.raises(Exception) as exc_info:
            classify_jobs_batch(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                verbose=False,
                http_client=mock_client,
                config_obj=config,
            )

        assert "CRITICAL ERROR" in str(exc_info.value)
        assert "incomplete results" in str(exc_info.value)

    def test_classify_jobs_batch_with_session_saves_llm_interactions(self, test_config, tmp_path):
        """Should save LLM request/response to session"""
        mock_session = Mock()
        mock_session.debug_dir = tmp_path

        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Python"}}]
        }
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Job 1", "text": "Python dev"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        classify_jobs_batch(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            session=mock_session,
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should have called session.save_llm_interaction (new unified method)
        assert mock_session.save_llm_interaction.called

    def test_classify_jobs_batch_preserves_job_fields(self, test_config):
        """Should preserve all original job fields"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Python"}}]
        }
        mock_client.post.return_value = mock_response

        jobs = [
            {
                "titel": "Dev",
                "text": "Text",
                "ort": "Berlin",
                "arbeitgeber": "Company",
                "url": "https://example.com",
            }
        ]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        result = classify_jobs_batch(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # All fields preserved
        assert result[0]["titel"] == "Dev"
        assert result[0]["ort"] == "Berlin"
        assert result[0]["arbeitgeber"] == "Company"
        assert result[0]["url"] == "https://example.com"

    def test_classify_jobs_batch_uses_default_categories(self, test_config):
        """Should use DEFAULT_CATEGORIES when none provided"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Andere"}}]
        }
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Job", "text": "Text"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        with patch("src.classifier.load_category_config", return_value=(None, {})):
            result = classify_jobs_batch(
                jobs=jobs,
                categories=None,
                api_key="test-key",
                verbose=False,
                http_client=mock_client,
                config_obj=config,
            )

        assert len(result) == 1

    def test_classify_jobs_batch_empty_jobs_list(self, test_config):
        """Should handle empty jobs list"""
        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        result = classify_jobs_batch(
            jobs=[],
            categories=["Python"],
            api_key="test-key",
            http_client=Mock(),
            config_obj=config,
        )

        assert result == []


class TestClassifyJobDescriptionErrorHandling:
    """Test error handling in classify_job_description function"""

    def test_json_content_parse_error_fallback_to_keyword_matching(self, test_config):
        """Should raise exception when JSON parsing fails (no silent failures!)"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        # Valid JSON response, but content is not valid JSON
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "This response mentions Python development but is not JSON"
                    }
                }
            ]
        }
        mock_client.post.return_value = mock_response

        config = Config(test_config)

        # Should raise LLMResponseError, not fall back to keyword matching
        from src.exceptions import LLMResponseError

        with pytest.raises(LLMResponseError) as exc_info:
            classify_job_description(
                job_text="Python developer needed",
                categories=["Python", "Java", "Andere"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=config,
            )

        assert "JSON array brackets" in str(exc_info.value)

    def test_json_content_parse_error_returns_andere_when_no_match(self, test_config):
        """Should raise exception when JSON parsing fails (no silent failures!)"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        # Valid JSON response, but content doesn't contain valid JSON or keywords
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "Random content with no category keywords or JSON"}}
            ]
        }
        mock_client.post.return_value = mock_response

        config = Config(test_config)

        # Should raise LLMResponseError, not return ["Andere"]
        from src.exceptions import LLMResponseError

        with pytest.raises(LLMResponseError) as exc_info:
            classify_job_description(
                job_text="Job description",
                categories=["Python", "Java"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=config,
            )

        assert "JSON array brackets" in str(exc_info.value)

    def test_api_error_raises_exception(self, test_config):
        """Should raise exception on API error status codes"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response

        config = Config(test_config)

        with pytest.raises(Exception) as exc_info:
            classify_job_description(
                job_text="Test job",
                categories=["Python"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=config,
            )

        assert "OpenRouter API error" in str(exc_info.value)
        assert "500" in str(exc_info.value)


class TestClassifyJobsBatchErrorHandling:
    """Test error handling in classify_jobs_batch function"""

    def test_batch_api_error_raises_exception(self, test_config):
        """Should raise exception when API returns error in batch mode"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 429  # Rate limit
        mock_response.text = "Rate limit exceeded"
        mock_client.post.return_value = mock_response

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        jobs = [{"titel": "Dev", "text": "Python developer"}]

        with pytest.raises(Exception) as exc_info:
            classify_jobs_batch(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=config,
            )

        assert "API error" in str(exc_info.value)
        assert "429" in str(exc_info.value)

    def test_batch_uses_default_http_client_when_none(self, test_config):
        """Should use default http_client when none provided"""
        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {"limits": {"job_text_batch": 1000}}
        config = Config(test_config)

        jobs = [{"titel": "Dev", "text": "Python job"}]

        with patch("src.classifier.default_http_client") as mock_default_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "[JOB_000] → Python"}}]
            }
            mock_default_client.post.return_value = mock_response

            classify_jobs_batch(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                http_client=None,  # Should use default
                config_obj=config,
            )

            # Should have used the default client
            mock_default_client.post.assert_called_once()

    def test_batch_uses_default_config_when_none(self, test_config):
        """Should use default config when none provided"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Python"}}]
        }
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Dev", "text": "Python job"}]

        with patch("src.classifier.config") as mock_default_config:
            mock_default_config.get.side_effect = lambda key, default=None: {
                "llm.models.default": "test-model",
                "processing.limits.job_text_batch": 1000,
            }.get(key, default)

            classify_jobs_batch(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=None,  # Should use default
            )

            # Should have used the default config
            assert mock_default_config.get.called


class TestClassifyJobsMegaBatchRecursion:
    """Test mega-batch splitting and recursive processing"""

    def test_mega_batch_splits_large_job_lists(self, test_config):
        """Should split large job lists into multiple mega-batches"""
        mock_client = Mock()

        # Mock responses for each batch (3 batches of 5 jobs each)
        # Each batch must return results for ALL 5 jobs
        batch_responses = [
            # Batch 1: Jobs 0-4
            Mock(
                status_code=200,
                json=lambda: {
                    "choices": [
                        {
                            "message": {
                                "content": "\n".join([f"[JOB_{i:03d}] → Python" for i in range(5)])
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
            ),
            # Batch 2: Jobs 0-4 (relative to this batch)
            Mock(
                status_code=200,
                json=lambda: {
                    "choices": [
                        {
                            "message": {
                                "content": "\n".join([f"[JOB_{i:03d}] → Python" for i in range(5)])
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
            ),
            # Batch 3: Jobs 0-4 (relative to this batch)
            Mock(
                status_code=200,
                json=lambda: {
                    "choices": [
                        {
                            "message": {
                                "content": "\n".join([f"[JOB_{i:03d}] → Python" for i in range(5)])
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                },
            ),
        ]

        mock_client.post.side_effect = batch_responses

        # Create 15 jobs, with max_jobs_per_mega_batch = 5 should create 3 batches
        jobs = [{"titel": f"Dev {i}", "text": "Python job"} for i in range(15)]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {
            "limits": {
                "job_text_mega_batch": 25000,
                "max_jobs_per_mega_batch": 5,  # Force splitting
            }
        }
        test_config["api"] = {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {"mega_batch_classification": 120},
        }
        test_config["llm"]["inference"] = {"temperature": 0.1}
        config = Config(test_config)

        result = classify_jobs_mega_batch(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should have made 3 API calls (3 batches)
        assert mock_client.post.call_count == 3
        assert len(result) == 15

    def test_mega_batch_no_split_when_within_limit(self, test_config):
        """Should not split when jobs are within limit"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "[JOB_000] → Python\n[JOB_001] → Java"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Dev 1", "text": "Python job"}, {"titel": "Dev 2", "text": "Java job"}]

        test_config["llm"] = {"models": {"default": "test-model"}}
        test_config["processing"] = {
            "limits": {
                "job_text_mega_batch": 25000,
                "max_jobs_per_mega_batch": 100,  # Well above our 2 jobs
            }
        }
        test_config["api"] = {
            "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
            "timeouts": {"mega_batch_classification": 120},
        }
        test_config["llm"]["inference"] = {"temperature": 0.1}
        config = Config(test_config)

        result = classify_jobs_mega_batch(
            jobs=jobs,
            categories=["Python", "Java"],
            api_key="test-key",
            verbose=False,
            http_client=mock_client,
            config_obj=config,
        )

        # Should make only 1 API call
        assert mock_client.post.call_count == 1
        assert len(result) == 2


class TestLoadCategoryConfigEdgeCases:
    """Test additional edge cases for load_category_config"""

    def test_load_category_config_when_yaml_unavailable(self):
        """Should return (None, {}) when YAML is not available"""
        with patch("src.classifier.YAML_AVAILABLE", False):
            categories, definitions = load_category_config()

            assert categories is None
            assert definitions == {}

    def test_load_category_config_uses_default_path(self, tmp_path):
        """Should use config path when none provided"""
        # Create a test categories file
        categories_file = tmp_path / "categories.yaml"
        categories_file.write_text("""categories:
  - name: Python
    description: Python jobs
  - name: Java
    description: Java jobs
""")

        with patch("src.classifier.config.get", return_value=str(categories_file)):
            categories, definitions = load_category_config(config_path=None)

            assert categories == ["Python", "Java"]
            assert definitions["Python"] == "Python jobs"


class TestClassifyJobsConfigDefaults:
    """Test that classify_jobs uses config defaults correctly"""

    def test_classify_jobs_uses_default_model_from_config(self, test_config):
        """Should use model from config when not specified"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"categories": ["Python"]}'}}]
        }
        mock_client.post.return_value = mock_response

        test_config["llm"] = {
            "models": {"default": "custom-model-from-config"},
            "temperature": 0.0,
            "timeout": 30,
        }
        test_config["processing"] = {"limits": {"job_text_single": 5000}}
        config = Config(test_config)

        jobs = [{"titel": "Dev", "text": "Python job"}]

        with patch("src.classifier.load_category_config", return_value=(None, {})):
            classify_jobs(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                model=None,  # Should use config default
                http_client=mock_client,
                config_obj=config,
            )

            # Check that the model from config was used
            call_kwargs = mock_client.post.call_args.kwargs
            assert "custom-model-from-config" in call_kwargs["json"]["model"]


class TestClassifyJobsDefaultClientAndConfig:
    """Test default http_client and config usage in classify_jobs"""

    def test_classify_jobs_uses_default_http_client(self, test_config):
        """Should use default_http_client when none provided"""
        test_config["llm"] = {
            "models": {"default": "test-model"},
            "temperature": 0.0,
            "timeout": 30,
        }
        test_config["processing"] = {"limits": {"job_text_single": 5000}}
        config = Config(test_config)

        jobs = [{"titel": "Dev", "text": "Python job"}]

        with (
            patch("src.classifier.default_http_client") as mock_default_client,
            patch("src.classifier.load_category_config", return_value=(None, {})),
        ):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": '{"categories": ["Python"]}'}}]
            }
            mock_default_client.post.return_value = mock_response

            classify_jobs(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                http_client=None,  # Should trigger default
                config_obj=config,
            )

            # Verify default client was used
            mock_default_client.post.assert_called_once()

    def test_classify_jobs_uses_default_config(self):
        """Should use default config when none provided"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"categories": ["Python"]}'}}]
        }
        mock_client.post.return_value = mock_response

        jobs = [{"titel": "Dev", "text": "Python job"}]

        with (
            patch("src.classifier.config") as mock_default_config,
            patch("src.classifier.load_category_config", return_value=(None, {})),
        ):
            mock_default_config.get.side_effect = lambda key, default=None: {
                "llm.models.default": "test-model",
                "llm.temperature": 0.0,
                "llm.timeout": 30,
                "processing.limits.job_text_single": 5000,
            }.get(key, default)

            classify_jobs(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                http_client=mock_client,
                config_obj=None,  # Should trigger default
            )

            # Verify default config was accessed
            assert mock_default_config.get.called


class TestClassifyJobsDefinitionsHandling:
    """Test category definitions handling in classify_jobs"""

    def test_classify_jobs_uses_provided_definitions(self, test_config):
        """Should use provided category_definitions parameter"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"categories": ["Python"]}'}}]
        }
        mock_client.post.return_value = mock_response

        test_config["llm"] = {
            "models": {"default": "test-model"},
            "temperature": 0.0,
            "timeout": 30,
        }
        test_config["processing"] = {"limits": {"job_text_single": 5000}}
        config = Config(test_config)

        jobs = [{"titel": "Dev", "text": "Python job"}]
        custom_definitions = {"Python": "For Python development jobs"}

        with patch("src.classifier.load_category_config", return_value=(None, {})):
            classify_jobs(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                category_definitions=custom_definitions,
                http_client=mock_client,
                config_obj=config,
            )

            # Verify the definition was included in the prompt
            call_kwargs = mock_client.post.call_args.kwargs
            prompt_content = call_kwargs["json"]["messages"][0]["content"]
            assert "For Python development jobs" in prompt_content

    def test_classify_jobs_uses_config_definitions_when_none_provided(self, test_config):
        """Should load definitions from config when not provided"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"categories": ["Python"]}'}}]
        }
        mock_client.post.return_value = mock_response

        test_config["llm"] = {
            "models": {"default": "test-model"},
            "temperature": 0.0,
            "timeout": 30,
        }
        test_config["processing"] = {"limits": {"job_text_single": 5000}}
        config = Config(test_config)

        jobs = [{"titel": "Dev", "text": "Python job"}]

        config_definitions = {"Python": "Config-based definition"}

        with patch("src.classifier.load_category_config", return_value=(None, config_definitions)):
            classify_jobs(
                jobs=jobs,
                categories=["Python"],
                api_key="test-key",
                category_definitions=None,  # Should use config definitions
                http_client=mock_client,
                config_obj=config,
            )

            # Verify config definition was used
            call_kwargs = mock_client.post.call_args.kwargs
            prompt_content = call_kwargs["json"]["messages"][0]["content"]
            assert "Config-based definition" in prompt_content
