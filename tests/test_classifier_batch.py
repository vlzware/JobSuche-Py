"""
Tests for batch and mega-batch classification

These tests verify batch processing logic, mega-batch splitting, and checkpoint functionality.
Single job tests are in test_classifier_single.py
"""

import json
from unittest.mock import Mock

import pytest

from src.classifier import classify_jobs_batch, classify_jobs_mega_batch
from src.config.loader import Config
from tests.test_helpers import create_mock_http_client, create_mock_session, create_test_config


class TestClassifyJobsBatch:
    """Test classify_jobs_batch() function - batch classification"""

    def test_classify_jobs_batch_basic(self):
        """Should classify multiple jobs in a single batch"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [
                    {
                        "message": {
                            "content": "[JOB_000] → Python\n[JOB_001] → Java\n[JOB_002] → Python"
                        }
                    }
                ]
            },
        )

        jobs = [
            {"titel": "Python Dev", "text": "Python developer needed"},
            {"titel": "Java Dev", "text": "Java engineer required"},
            {"titel": "Python Senior", "text": "Senior Python position"},
        ]

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

    def test_classify_jobs_batch_multiple_batches(self):
        """Should process jobs in multiple batches"""
        config = Config(create_test_config())

        # First batch response
        response1 = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": "[JOB_000] → Python\n[JOB_001] → Java"}}]
            },
        )

        # Second batch response
        response2 = Mock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "[JOB_000] → Python"}}]},
        )

        mock_client = Mock()
        mock_client.post.side_effect = [response1, response2]

        jobs = [
            {"titel": "Job 1", "text": "Text 1"},
            {"titel": "Job 2", "text": "Text 2"},
            {"titel": "Job 3", "text": "Text 3"},
        ]

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

    def test_classify_jobs_batch_handles_malformed_response(self):
        """Should raise exception on malformed batch responses (NO SILENT FAILURES!)"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [{"message": {"content": "Invalid format - missing job IDs"}}]
            },
        )

        jobs = [{"titel": "Job 1", "text": "Text"}]

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

    def test_classify_jobs_batch_preserves_job_fields(self):
        """Should preserve all original job fields"""
        config = Config(create_test_config())
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={"choices": [{"message": {"content": "[JOB_000] → Python"}}]},
        )

        jobs = [
            {
                "titel": "Dev",
                "text": "Text",
                "ort": "Berlin",
                "arbeitgeber": "Company",
                "url": "https://example.com",
            }
        ]

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

    def test_classify_jobs_batch_empty_jobs_list(self):
        """Should handle empty jobs list"""
        config = Config(create_test_config())

        result = classify_jobs_batch(
            jobs=[],
            categories=["Python"],
            api_key="test-key",
            http_client=Mock(),
            config_obj=config,
        )

        assert result == []


class TestClassifyJobsMegaBatch:
    """Test mega-batch splitting and recursive processing"""

    def test_mega_batch_splits_large_job_lists(self):
        """Should split large job lists into multiple mega-batches"""
        config_dict = create_test_config()
        config_dict["processing"]["limits"]["max_jobs_per_mega_batch"] = 5  # Force splitting
        config_dict["api"]["timeouts"]["mega_batch_classification"] = 120
        config = Config(config_dict)

        # Mock responses for each batch (3 batches of 5 jobs each)
        batch_responses = [
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
            )
            for _ in range(3)
        ]

        mock_client = Mock()
        mock_client.post.side_effect = batch_responses

        # Create 15 jobs (will be split into 3 batches of 5)
        jobs = [{"titel": f"Dev {i}", "text": "Python job"} for i in range(15)]

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

    def test_mega_batch_no_split_when_within_limit(self):
        """Should not split when jobs are within limit"""
        config_dict = create_test_config()
        config_dict["processing"]["limits"]["max_jobs_per_mega_batch"] = 100
        config_dict["api"]["timeouts"]["mega_batch_classification"] = 120
        config = Config(config_dict)

        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [{"message": {"content": "[JOB_000] → Python\n[JOB_001] → Java"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

        jobs = [{"titel": "Dev 1", "text": "Python job"}, {"titel": "Dev 2", "text": "Java job"}]

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


class TestTruncationReportSaving:
    """Test that truncation reports are properly saved to debug files"""

    def test_truncation_report_saved_when_jobs_truncated(self, tmp_path):
        """Should save truncation_report.json when jobs are truncated"""
        config_dict = create_test_config()
        config_dict["processing"]["limits"]["job_text_mega_batch"] = (
            50  # Very low to force truncation
        )
        config_dict["api"]["timeouts"]["mega_batch_classification"] = 30
        config = Config(config_dict)

        # Mock session with debug_dir
        mock_session = create_mock_session(tmp_path)

        # Mock HTTP client with successful response
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [{"message": {"content": "[JOB_000] → Java\n[JOB_001] → Python"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

        # Create jobs with text that will be truncated
        jobs = [
            {"titel": "Job 1", "text": "A" * 500, "refnr": "123"},
            {"titel": "Job 2", "text": "B" * 500, "refnr": "456"},
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
        truncation_file = mock_session.debug_dir / "truncation_report.json"
        assert truncation_file.exists(), "truncation_report.json should be created"

        # Verify the content of the truncation report
        with open(truncation_file, encoding="utf-8") as f:
            truncation_data = json.load(f)

        assert truncation_data["jobs_truncated"] > 0
        assert truncation_data["total_jobs"] == 2
        assert "truncated_jobs" in truncation_data
        assert len(truncation_data["truncated_jobs"]) > 0

    def test_truncation_report_not_saved_when_no_truncation(self, tmp_path):
        """Should not save truncation_report.json when no jobs are truncated"""
        config_dict = create_test_config()
        config_dict["processing"]["limits"]["job_text_mega_batch"] = (
            10000  # High enough to avoid truncation
        )
        config_dict["api"]["timeouts"]["mega_batch_classification"] = 30
        config = Config(config_dict)

        # Mock session with debug_dir
        mock_session = create_mock_session(tmp_path)

        # Mock HTTP client
        mock_client = create_mock_http_client(
            status_code=200,
            json_response={
                "choices": [{"message": {"content": "[JOB_000] → Java"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

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
        truncation_file = mock_session.debug_dir / "truncation_report.json"
        assert (
            not truncation_file.exists()
        ), "truncation_report.json should not be created when no truncation"


@pytest.mark.parametrize("status_code", [400, 429, 500, 502, 503])
def test_batch_api_errors_raise_exception(status_code):
    """Should raise exception when API returns errors (consolidated error test)"""
    config = Config(create_test_config())
    mock_client = create_mock_http_client(status_code=status_code)
    mock_client.post.return_value.text = f"API Error {status_code}"

    jobs = [{"titel": "Dev", "text": "Python developer"}]

    with pytest.raises(Exception) as exc_info:
        classify_jobs_batch(
            jobs=jobs,
            categories=["Python"],
            api_key="test-key",
            http_client=mock_client,
            config_obj=config,
        )

    assert "API error" in str(exc_info.value) or str(status_code) in str(exc_info.value)
