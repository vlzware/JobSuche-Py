"""
Tests for exception handling
"""

from unittest.mock import patch

import pytest

from src.exceptions import (
    EmptyJobContentError,
    LLMDataIntegrityError,
    LLMResponseError,
    OpenRouterAPIError,
    TruncationError,
    WorkflowConfigurationError,
)


class TestTruncationError:
    """Test TruncationError exception"""

    def test_truncation_error_attributes(self):
        """Test that TruncationError stores all required attributes"""
        error = TruncationError(job_id="test-123", original_length=5000, truncated_length=3000)

        assert error.job_id == "test-123"
        assert error.original_length == 5000
        assert error.truncated_length == 3000
        assert error.loss == 2000

    def test_truncation_error_message(self):
        """Test that TruncationError formats message correctly"""
        error = TruncationError(job_id="test-123", original_length=5000, truncated_length=3000)

        message = str(error)
        assert "test-123" in message
        assert "5000" in message
        assert "3000" in message
        assert "2000" in message  # loss


class TestLLMDataIntegrityError:
    """Test LLMDataIntegrityError exception"""

    def test_llm_data_integrity_error_with_counts(self):
        """Test LLMDataIntegrityError with count information"""
        error = LLMDataIntegrityError(
            "Missing jobs in batch",
            expected_count=10,
            actual_count=8,
            missing_indices=[2, 5],
        )

        assert error.expected_count == 10
        assert error.actual_count == 8
        assert error.missing_indices == [2, 5]
        assert "Missing jobs in batch" in str(error)

    def test_llm_data_integrity_error_minimal(self):
        """Test LLMDataIntegrityError with minimal parameters"""
        error = LLMDataIntegrityError("Data integrity issue")

        assert error.expected_count is None
        assert error.actual_count is None
        assert error.missing_indices is None
        assert "Data integrity issue" in str(error)


class TestLLMResponseError:
    """Test LLMResponseError exception"""

    def test_llm_response_error_with_raw_response(self):
        """Test LLMResponseError stores raw response"""
        raw = '{"invalid": json without closing brace'
        error = LLMResponseError("Invalid JSON", raw_response=raw)

        assert error.raw_response == raw
        assert "Invalid JSON" in str(error)

    def test_llm_response_error_without_raw_response(self):
        """Test LLMResponseError without raw response"""
        error = LLMResponseError("Parse error")

        assert error.raw_response is None
        assert "Parse error" in str(error)


class TestOpenRouterAPIError:
    """Test OpenRouterAPIError exception"""

    def test_openrouter_api_error_with_status_code(self):
        """Test OpenRouterAPIError stores status code and response"""
        error = OpenRouterAPIError("API Error", status_code=401, response_text="Unauthorized")

        assert error.status_code == 401
        assert error.response_text == "Unauthorized"
        assert "API Error" in str(error)

    def test_openrouter_api_error_minimal(self):
        """Test OpenRouterAPIError with minimal parameters"""
        error = OpenRouterAPIError("Generic API error")

        assert error.status_code is None
        assert error.response_text is None

    def test_get_user_guidance_401(self):
        """Test user guidance for 401 error"""
        error = OpenRouterAPIError("Auth failed", status_code=401)
        guidance = error.get_user_guidance()

        assert "Authentication failed" in guidance
        assert "API key" in guidance
        assert "openrouter.ai/keys" in guidance

    def test_get_user_guidance_402(self):
        """Test user guidance for 402 error (payment required)"""
        error = OpenRouterAPIError("No credits", status_code=402)
        guidance = error.get_user_guidance()

        assert "credits" in guidance.lower()

    def test_get_user_guidance_429(self):
        """Test user guidance for 429 error (rate limit)"""
        error = OpenRouterAPIError("Rate limit", status_code=429)
        guidance = error.get_user_guidance()

        assert "Rate limit" in guidance
        assert "batch size" in guidance.lower()

    def test_get_user_guidance_503(self):
        """Test user guidance for 503 error (service unavailable)"""
        error = OpenRouterAPIError("Service down", status_code=503)
        guidance = error.get_user_guidance()

        assert "temporarily unavailable" in guidance.lower()

    def test_get_user_guidance_500(self):
        """Test user guidance for 500+ server errors"""
        error = OpenRouterAPIError("Server error", status_code=500)
        guidance = error.get_user_guidance()

        assert "server error" in guidance.lower()
        assert "temporary" in guidance.lower()

    def test_get_user_guidance_unknown(self):
        """Test user guidance for unknown error codes"""
        error = OpenRouterAPIError("Unknown error", status_code=418)
        guidance = error.get_user_guidance()

        assert "configuration" in guidance.lower()


class TestWorkflowConfigurationError:
    """Test WorkflowConfigurationError exception"""

    def test_workflow_configuration_error_with_type(self):
        """Test WorkflowConfigurationError stores workflow type"""
        error = WorkflowConfigurationError("Missing CV", workflow_type="cv-based")

        assert error.workflow_type == "cv-based"
        assert "Missing CV" in str(error)

    def test_workflow_configuration_error_without_type(self):
        """Test WorkflowConfigurationError without workflow type"""
        error = WorkflowConfigurationError("Config error")

        assert error.workflow_type is None


class TestEmptyJobContentError:
    """Test EmptyJobContentError exception"""

    def test_empty_job_content_error_with_job_id(self):
        """Test EmptyJobContentError stores job ID"""
        error = EmptyJobContentError("No content", job_id="job-123")

        assert error.job_id == "job-123"
        assert "No content" in str(error)

    def test_empty_job_content_error_without_job_id(self):
        """Test EmptyJobContentError without job ID"""
        error = EmptyJobContentError("Empty job")

        assert error.job_id is None


class TestErrorHandling:
    """Test the centralized error handling in main.py"""

    @patch("sys.exit")
    @patch("main.logger")
    def test_handle_llm_data_integrity_error(self, mock_logger, mock_exit):
        """Test handling of LLMDataIntegrityError"""
        from main import handle_classification_error

        error = LLMDataIntegrityError("Test integrity error")

        # Call the error handler
        handle_classification_error(error)

        # Verify sys.exit was called with code 1
        mock_exit.assert_called_once_with(1)

        # Verify error messages were logged
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("LLM DATA INTEGRITY ERROR" in str(call) for call in error_calls)
        assert any("WHAT YOU CAN TRY:" in str(call) for call in error_calls)

    @patch("sys.exit")
    @patch("main.logger")
    def test_handle_llm_response_error(self, mock_logger, mock_exit):
        """Test handling of LLMResponseError"""
        from main import handle_classification_error

        error = LLMResponseError("Parse error")

        handle_classification_error(error)

        mock_exit.assert_called_once_with(1)
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("LLM RESPONSE PARSING ERROR" in str(call) for call in error_calls)
        assert any("WHAT YOU CAN TRY:" in str(call) for call in error_calls)

    @patch("sys.exit")
    @patch("main.logger")
    def test_handle_openrouter_api_error(self, mock_logger, mock_exit):
        """Test handling of OpenRouterAPIError"""
        from main import handle_classification_error

        error = OpenRouterAPIError("API failed", status_code=401)

        handle_classification_error(error)

        mock_exit.assert_called_once_with(1)
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("OPENROUTER API ERROR" in str(call) for call in error_calls)
        assert any("401" in str(call) for call in error_calls)

    @patch("sys.exit")
    @patch("main.logger")
    def test_handle_workflow_configuration_error(self, mock_logger, mock_exit):
        """Test handling of WorkflowConfigurationError"""
        from main import handle_classification_error

        error = WorkflowConfigurationError("Bad config", workflow_type="cv-based")

        handle_classification_error(error)

        mock_exit.assert_called_once_with(1)
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("WORKFLOW CONFIGURATION ERROR" in str(call) for call in error_calls)

    @patch("sys.exit")
    @patch("main.logger")
    def test_handle_empty_job_content_error(self, mock_logger, mock_exit):
        """Test handling of EmptyJobContentError"""
        from main import handle_classification_error

        error = EmptyJobContentError("No content", job_id="job-999")

        handle_classification_error(error)

        mock_exit.assert_called_once_with(1)
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("EMPTY JOB CONTENT ERROR" in str(call) for call in error_calls)
        assert any("job-999" in str(call) for call in error_calls)

    def test_handle_unknown_error_reraises(self):
        """Test that unknown exceptions are re-raised"""
        from main import handle_classification_error

        error = ValueError("Unknown error type")

        with pytest.raises(ValueError, match="Unknown error type"):
            handle_classification_error(error)


class TestClassifierExceptionRaising:
    """Test that classifier.py raises the correct exceptions"""

    @patch("src.classifier.default_http_client")
    def test_classify_job_description_raises_llm_response_error(self, mock_client):
        """Test that malformed LLM responses raise LLMResponseError"""
        from src.classifier import classify_job_description

        # Mock response with invalid JSON
        mock_response = type("Response", (), {})()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "choices": [{"message": {"content": "Invalid response without brackets"}}]
        }
        mock_client.post.return_value = mock_response

        with pytest.raises(LLMResponseError) as exc_info:
            classify_job_description(
                job_text="Test job",
                categories=["Python", "Java"],
                api_key="test-key",
            )

        # Check that the error message mentions missing JSON array brackets
        error_msg = str(exc_info.value).lower()
        assert "json array" in error_msg and "bracket" in error_msg

    @patch("src.classifier.default_http_client")
    def test_classify_job_description_raises_openrouter_api_error(self, mock_client):
        """Test that API errors raise OpenRouterAPIError"""
        from src.classifier import classify_job_description

        # Mock failed API response
        mock_response = type("Response", (), {})()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client.post.return_value = mock_response

        with pytest.raises(OpenRouterAPIError) as exc_info:
            classify_job_description(
                job_text="Test job",
                categories=["Python", "Java"],
                api_key="invalid-key",
            )

        assert exc_info.value.status_code == 401

    @patch("src.classifier.default_http_client")
    def test_classify_jobs_raises_empty_job_content_error(self, mock_client):
        """Test that empty job text raises EmptyJobContentError"""
        from src.classifier import classify_jobs

        jobs = [{"refnr": "123", "titel": "Test Job", "text": ""}]

        with pytest.raises(EmptyJobContentError) as exc_info:
            classify_jobs(
                jobs=jobs,
                categories=["Python", "Java"],
                api_key="test-key",
            )

        assert exc_info.value.job_id == "123"


class TestWorkflowExceptionRaising:
    """Test that workflows raise correct exceptions"""

    def test_matching_workflow_raises_configuration_error_without_inputs(self):
        """Test MatchingWorkflow raises WorkflowConfigurationError when neither CV nor perfect job provided"""
        from src.preferences import UserProfile
        from src.workflows.matching import MatchingWorkflow

        # Create workflow without CV or perfect job description
        profile = UserProfile()
        workflow = MatchingWorkflow(
            user_profile=profile,
            llm_processor=None,  # type: ignore
            session=None,
            verbose=False,
        )

        with pytest.raises(WorkflowConfigurationError) as exc_info:
            workflow.process(jobs=[])

        assert exc_info.value.workflow_type == "matching"
        assert "At least one of CV or perfect job description is required" in str(exc_info.value)

    def test_matching_workflow_raises_configuration_error_with_empty_inputs(self):
        """Test MatchingWorkflow raises WorkflowConfigurationError when inputs are empty strings"""
        from src.preferences import UserProfile
        from src.workflows.matching import MatchingWorkflow

        # Create workflow with empty string inputs
        profile = UserProfile()
        workflow = MatchingWorkflow(
            user_profile=profile,
            llm_processor=None,  # type: ignore
            session=None,
            verbose=False,
        )

        with pytest.raises(WorkflowConfigurationError) as exc_info:
            workflow.process(jobs=[], cv_content="   ", perfect_job_description="")

        assert exc_info.value.workflow_type == "matching"
