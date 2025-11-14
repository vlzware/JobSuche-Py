"""
Test workflow classes with mocked dependencies

Tests the workflow types (multi-category, matching, brainstorm)
and the base workflow functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.data import JobGatherer
from src.llm import LLMProcessor
from src.preferences import UserProfile
from src.workflows import (
    BrainstormWorkflow,
    MatchingWorkflow,
    MultiCategoryWorkflow,
)


@pytest.fixture
def sample_jobs():
    """Sample job data for testing"""
    return [
        {
            "titel": "Python Developer",
            "ort": "Berlin",
            "arbeitgeber": "Tech Corp",
            "text": "Python, Django, REST APIs, Docker",
            "url": "https://example.com/job/1",
        },
        {
            "titel": "Java Backend Engineer",
            "ort": "München",
            "arbeitgeber": "Enterprise GmbH",
            "text": "Java, Spring Boot, Microservices, Kubernetes",
            "url": "https://example.com/job/2",
        },
        {
            "titel": "DevOps Engineer",
            "ort": "Hamburg",
            "arbeitgeber": "Cloud Solutions",
            "text": "AWS, Terraform, CI/CD, Docker, Kubernetes",
            "url": "https://example.com/job/3",
        },
    ]


@pytest.fixture
def classified_jobs():
    """Sample classified job data"""
    return [
        {
            "titel": "Python Developer",
            "ort": "Berlin",
            "arbeitgeber": "Tech Corp",
            "text": "Python, Django, REST APIs",
            "categories": ["Python", "Backend"],
            "url": "https://example.com/job/1",
        },
        {
            "titel": "Java Backend Engineer",
            "ort": "München",
            "arbeitgeber": "Enterprise GmbH",
            "text": "Java, Spring Boot, Microservices",
            "categories": ["Java", "Backend"],
            "url": "https://example.com/job/2",
        },
    ]


@pytest.fixture
def mock_user_profile():
    """Mock UserProfile"""
    profile = MagicMock(spec=UserProfile)
    profile.get_categories.return_value = ["Python", "Java", "DevOps", "Andere"]
    profile.get_category_definitions.return_value = {
        "Python": "Python development roles",
        "Java": "Java development roles",
        "DevOps": "DevOps and infrastructure roles",
    }
    profile.has_cv.return_value = False
    return profile


@pytest.fixture
def mock_llm_processor():
    """Mock LLMProcessor"""
    processor = MagicMock(spec=LLMProcessor)
    return processor


@pytest.fixture
def mock_job_gatherer():
    """Mock JobGatherer"""
    gatherer = MagicMock(spec=JobGatherer)
    return gatherer


@pytest.fixture
def mock_session(tmp_path):
    """Mock SearchSession"""
    session = MagicMock()
    session.session_dir = tmp_path / "session"
    session.debug_dir = tmp_path / "session/debug"
    return session


class TestMultiCategoryWorkflow:
    """Test multi-category workflow"""

    def test_process_with_default_categories(
        self, sample_jobs, classified_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should use UserProfile categories for classification"""
        # Setup
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result = workflow.process(sample_jobs)

        # Verify
        assert result == classified_jobs
        mock_llm_processor.classify_multi_category.assert_called_once_with(
            jobs=sample_jobs,
            categories=["Python", "Java", "DevOps", "Andere"],
            category_definitions={
                "Python": "Python development roles",
                "Java": "Java development roles",
                "DevOps": "DevOps and infrastructure roles",
            },
            batch_size=None,
        )

    def test_process_with_custom_batch_size(
        self, sample_jobs, classified_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should respect custom batch_size parameter"""
        # Setup
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result = workflow.process(sample_jobs, batch_size=5)

        # Verify
        assert result == classified_jobs
        call_args = mock_llm_processor.classify_multi_category.call_args
        assert call_args[1]["batch_size"] == 5

    def test_run_complete_workflow(
        self,
        sample_jobs,
        classified_jobs,
        mock_user_profile,
        mock_llm_processor,
        mock_job_gatherer,
        mock_session,
    ):
        """Should execute complete workflow: gather → classify → analyze"""
        # Setup
        mock_job_gatherer.gather.return_value = (
            sample_jobs,
            [],  # No failed jobs
            {"total_found": 3, "successfully_extracted": 3, "failed": 0},
        )
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            job_gatherer=mock_job_gatherer,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result_jobs, failed_jobs = workflow.run(
            was="Python Developer",
            wo="Berlin",
            umkreis=25,
            size=100,
            max_pages=1,
            enable_scraping=True,
            show_statistics=False,
        )

        # Verify
        assert result_jobs == classified_jobs
        assert failed_jobs == []
        mock_job_gatherer.gather.assert_called_once()
        mock_llm_processor.classify_multi_category.assert_called_once()

    def test_run_with_config_defaults(
        self,
        sample_jobs,
        classified_jobs,
        mock_user_profile,
        mock_llm_processor,
        mock_job_gatherer,
        mock_session,
    ):
        """Should load defaults from config when parameters not provided"""
        # Setup
        mock_job_gatherer.gather.return_value = (
            sample_jobs,
            [],
            {"total_found": 3, "successfully_extracted": 3, "failed": 0},
        )
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            job_gatherer=mock_job_gatherer,
            session=mock_session,
            verbose=False,
        )

        # Execute - no umkreis, size, max_pages specified
        with patch("src.workflows.base.config") as mock_config:
            mock_config.get.side_effect = lambda key, default: {
                "search.defaults.radius_km": 50,
                "search.defaults.page_size": 200,
                "search.defaults.max_pages": 3,
            }.get(key, default)

            _result_jobs, _failed_jobs = workflow.run(
                was="Developer", wo="Berlin", show_statistics=False
            )

        # Verify config was consulted
        assert mock_config.get.call_count >= 3

    def test_run_returns_empty_when_no_jobs_gathered(
        self, mock_user_profile, mock_llm_processor, mock_job_gatherer, mock_session
    ):
        """Should return empty lists when no jobs are gathered"""
        # Setup
        mock_job_gatherer.gather.return_value = (
            [],
            [],
            {"total_found": 0, "successfully_extracted": 0, "failed": 0},
        )

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            job_gatherer=mock_job_gatherer,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result_jobs, failed_jobs = workflow.run(
            was="NonexistentJob", wo="Mars", show_statistics=False
        )

        # Verify
        assert result_jobs == []
        assert failed_jobs == []
        # LLM processor should not be called
        mock_llm_processor.classify_multi_category.assert_not_called()


class TestMatchingWorkflow:
    """Test matching workflow (unified CV-based and perfect-job)"""

    def test_process_with_perfect_job_only(
        self, sample_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should work with only perfect job description"""
        # Setup
        matching_jobs = [sample_jobs[0]]
        mock_llm_processor.classify_matching.return_value = matching_jobs

        workflow = MatchingWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result = workflow.process(
            jobs=sample_jobs,
            perfect_job_description="Python, Docker, remote work",
            return_only_matches=True,
        )

        # Verify
        assert result == matching_jobs
        mock_llm_processor.classify_matching.assert_called_once_with(
            jobs=sample_jobs,
            cv_content=None,
            perfect_job_description="Python, Docker, remote work",
            return_only_matches=True,
            batch_size=None,
        )

    def test_process_with_cv_only(
        self, sample_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should work with only CV content"""
        # Setup
        cv_content = "5 years Python experience, Django, REST APIs, Docker"
        matching_jobs = [sample_jobs[0]]
        mock_llm_processor.classify_matching.return_value = matching_jobs

        workflow = MatchingWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result = workflow.process(
            jobs=sample_jobs,
            cv_content=cv_content,
            return_only_matches=True,
        )

        # Verify
        assert result == matching_jobs
        mock_llm_processor.classify_matching.assert_called_once_with(
            jobs=sample_jobs,
            cv_content=cv_content,
            perfect_job_description=None,
            return_only_matches=True,
            batch_size=None,
        )

    def test_process_with_both_cv_and_perfect_job(
        self, sample_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should work with both CV and perfect job description (recommended)"""
        # Setup
        cv_content = "5 years Python experience"
        perfect_job_desc = "Remote Python position with Docker"
        matching_jobs = [sample_jobs[0]]
        mock_llm_processor.classify_matching.return_value = matching_jobs

        workflow = MatchingWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result = workflow.process(
            jobs=sample_jobs,
            cv_content=cv_content,
            perfect_job_description=perfect_job_desc,
            return_only_matches=True,
        )

        # Verify
        assert result == matching_jobs
        mock_llm_processor.classify_matching.assert_called_once_with(
            jobs=sample_jobs,
            cv_content=cv_content,
            perfect_job_description=perfect_job_desc,
            return_only_matches=True,
            batch_size=None,
        )

    def test_return_only_matches_filters(
        self, sample_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """return_only_matches=True should filter non-matches"""
        # Setup
        matching_jobs = [sample_jobs[0]]
        mock_llm_processor.classify_matching.return_value = matching_jobs

        workflow = MatchingWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        workflow.process(
            jobs=sample_jobs,
            cv_content="Python developer",
            return_only_matches=True,
        )

        # Verify
        call_args = mock_llm_processor.classify_matching.call_args
        assert call_args[1]["return_only_matches"] is True

    def test_return_all_includes_non_matches(
        self, sample_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """return_only_matches=False should include all jobs"""
        # Setup
        all_jobs_classified = sample_jobs.copy()
        for job in all_jobs_classified:
            job["categories"] = ["Poor Match"]
        all_jobs_classified[0]["categories"] = ["Excellent Match"]

        mock_llm_processor.classify_matching.return_value = all_jobs_classified

        workflow = MatchingWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result = workflow.process(
            jobs=sample_jobs,
            perfect_job_description="Python developer",
            return_only_matches=False,
        )

        # Verify
        assert len(result) == 3  # All jobs returned
        call_args = mock_llm_processor.classify_matching.call_args
        assert call_args[1]["return_only_matches"] is False

    def test_raises_error_without_inputs(self, sample_jobs, mock_llm_processor, mock_session):
        """Should raise error when neither CV nor perfect job description provided"""
        # Setup
        profile = MagicMock(spec=UserProfile)

        workflow = MatchingWorkflow(
            user_profile=profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute & Verify
        from src.exceptions import WorkflowConfigurationError

        with pytest.raises(
            WorkflowConfigurationError,
            match="At least one of CV or perfect job description is required",
        ):
            workflow.process(jobs=sample_jobs)

    def test_raises_error_with_empty_strings(self, sample_jobs, mock_llm_processor, mock_session):
        """Should raise error when inputs are empty/whitespace strings"""
        # Setup
        workflow = MatchingWorkflow(
            user_profile=MagicMock(spec=UserProfile),
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute & Verify
        from src.exceptions import WorkflowConfigurationError

        with pytest.raises(WorkflowConfigurationError):
            workflow.process(jobs=sample_jobs, cv_content="   ", perfect_job_description="")


class TestBaseWorkflow:
    """Test base workflow functionality"""

    def test_creates_job_gatherer_when_not_provided(
        self, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should create JobGatherer if not provided"""
        # Execute
        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            job_gatherer=None,  # Not provided
            session=mock_session,
            verbose=False,
        )

        # Verify
        assert workflow.job_gatherer is not None
        assert isinstance(workflow.job_gatherer, JobGatherer)

    def test_run_stores_gathering_stats(
        self,
        sample_jobs,
        classified_jobs,
        mock_user_profile,
        mock_llm_processor,
        mock_job_gatherer,
        mock_session,
    ):
        """Should store gathering_stats for later use"""
        # Setup
        gathering_stats = {"total_found": 10, "successfully_extracted": 3, "failed": 0}
        mock_job_gatherer.gather.return_value = (sample_jobs, [], gathering_stats)
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            job_gatherer=mock_job_gatherer,
            session=mock_session,
            verbose=False,
        )

        # Execute
        workflow.run(was="Developer", wo="Berlin", show_statistics=False)

        # Verify
        assert hasattr(workflow, "gathering_stats")
        assert workflow.gathering_stats == gathering_stats

    def test_run_returns_classified_and_failed_jobs(
        self,
        sample_jobs,
        classified_jobs,
        mock_user_profile,
        mock_llm_processor,
        mock_job_gatherer,
        mock_session,
    ):
        """Should return tuple of (classified_jobs, failed_jobs)"""
        # Setup
        failed_jobs = [{"titel": "Failed Job", "error": "TIMEOUT"}]
        mock_job_gatherer.gather.return_value = (
            sample_jobs,
            failed_jobs,
            {"total_found": 3, "successfully_extracted": 3, "failed": 1},
        )
        mock_llm_processor.classify_multi_category.return_value = classified_jobs

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            job_gatherer=mock_job_gatherer,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result_classified, result_failed = workflow.run(
            was="Developer", wo="Berlin", show_statistics=False
        )

        # Verify
        assert result_classified == classified_jobs
        assert result_failed == failed_jobs

    def test_run_from_file(
        self, sample_jobs, classified_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should process pre-loaded jobs without gathering"""
        # Setup
        mock_llm_processor.classify_multi_category.return_value = classified_jobs
        # Mock checkpoint methods to return no checkpoint (fresh start)
        mock_session.load_checkpoint.return_value = None
        mock_session.load_partial_results.return_value = []

        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        # Execute
        result = workflow.run_from_file(jobs=sample_jobs, show_statistics=False)

        # Verify
        assert result == classified_jobs
        mock_llm_processor.classify_multi_category.assert_called_once()

    def test_generate_report(
        self, classified_jobs, mock_user_profile, mock_llm_processor, mock_session
    ):
        """Should generate text report"""
        # Setup
        workflow = MultiCategoryWorkflow(
            user_profile=mock_user_profile,
            llm_processor=mock_llm_processor,
            session=mock_session,
            verbose=False,
        )

        search_params = {"was": "Developer", "wo": "Berlin", "umkreis": 25}

        # Execute
        with patch("src.workflows.base.generate_report") as mock_generate:
            mock_generate.return_value = "Test Report"

            report = workflow.generate_report(
                classified_jobs=classified_jobs,
                total_jobs=len(classified_jobs),
                search_params=search_params,
            )

        # Verify
        assert report == "Test Report"
        mock_generate.assert_called_once()


class TestBrainstormWorkflow:
    """Test brainstorm workflow"""

    @pytest.fixture
    def mock_http_response(self):
        """Mock HTTP response from OpenRouter API"""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": """## Software Developer
**Confidence:** High
**Reasoning:** Matches your background in Python and web development.

## DevOps Engineer
**Confidence:** Medium
**Reasoning:** Your Docker and CI/CD experience aligns well."""
                    }
                }
            ]
        }
        return response

    def test_run_with_both_cv_and_motivation(self, mock_http_response):
        """Should process both CV and motivation description"""
        # Setup
        with patch("src.workflows.brainstorm.default_http_client") as mock_http_client:
            mock_http_client.post.return_value = mock_http_response

            workflow = BrainstormWorkflow(
                api_key="test-api-key", model="test-model", session=None, verbose=False
            )

            # Execute
            result = workflow.run(
                cv_content="Python developer with 5 years experience",
                motivation_description="I want to work on challenging projects",
            )

            # Verify
            assert "Software Developer" in result
            assert "DevOps Engineer" in result
            mock_http_client.post.assert_called_once()

    def test_run_with_cv_only(self, mock_http_response):
        """Should work with only CV content"""
        # Setup
        with patch("src.workflows.brainstorm.default_http_client") as mock_http_client:
            mock_http_client.post.return_value = mock_http_response

            workflow = BrainstormWorkflow(
                api_key="test-api-key", model="test-model", session=None, verbose=False
            )

            # Execute
            result = workflow.run(cv_content="Python developer with 5 years experience")

            # Verify
            assert "Software Developer" in result
            mock_http_client.post.assert_called_once()

    def test_run_with_motivation_only(self, mock_http_response):
        """Should work with only motivation description"""
        # Setup
        with patch("src.workflows.brainstorm.default_http_client") as mock_http_client:
            mock_http_client.post.return_value = mock_http_response

            workflow = BrainstormWorkflow(
                api_key="test-api-key", model="test-model", session=None, verbose=False
            )

            # Execute
            result = workflow.run(motivation_description="I want to work on challenging projects")

            # Verify
            assert "Software Developer" in result
            mock_http_client.post.assert_called_once()

    def test_raises_error_without_input(self):
        """Should raise error when neither CV nor motivation is provided"""
        # Setup
        workflow = BrainstormWorkflow(api_key="test-api-key", session=None, verbose=False)

        # Execute & Verify
        from src.exceptions import WorkflowConfigurationError

        with pytest.raises(
            WorkflowConfigurationError,
            match="At least one of CV or motivation description is required",
        ):
            workflow.run()

    def test_raises_error_with_empty_strings(self):
        """Should raise error when inputs are empty strings"""
        # Setup
        workflow = BrainstormWorkflow(api_key="test-api-key", session=None, verbose=False)

        # Execute & Verify
        from src.exceptions import WorkflowConfigurationError

        with pytest.raises(WorkflowConfigurationError):
            workflow.run(cv_content="   ", motivation_description="")

    def test_handles_api_error(self):
        """Should handle OpenRouter API errors properly"""
        # Setup
        with patch("src.workflows.brainstorm.default_http_client") as mock_http_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Invalid API key"
            mock_http_client.post.return_value = mock_response

            workflow = BrainstormWorkflow(
                api_key="invalid-key", model="test-model", session=None, verbose=False
            )

            # Execute & Verify
            from src.exceptions import OpenRouterAPIError

            with pytest.raises(OpenRouterAPIError):
                workflow.run(cv_content="Test CV")

    def test_handles_empty_llm_response(self):
        """Should handle empty LLM responses"""
        # Setup
        with patch("src.workflows.brainstorm.default_http_client") as mock_http_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": ""}}]  # Empty content
            }
            mock_http_client.post.return_value = mock_response

            workflow = BrainstormWorkflow(
                api_key="test-api-key", model="test-model", session=None, verbose=False
            )

            # Execute & Verify
            from src.exceptions import WorkflowConfigurationError

            with pytest.raises(WorkflowConfigurationError, match="LLM returned empty response"):
                workflow.run(cv_content="Test CV")

    def test_saves_artifacts_to_session(self, tmp_path):
        """Should save prompt and response to session directory"""
        # Setup - use real SearchSession so files are actually written
        from src.session import SearchSession

        session = SearchSession(base_dir=str(tmp_path), timestamp="test_session", verbose=False)

        with patch("src.workflows.brainstorm.default_http_client") as mock_http_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test suggestions"}}]
            }
            mock_http_client.post.return_value = mock_response

            workflow = BrainstormWorkflow(
                api_key="test-api-key", model="test-model", session=session, verbose=False
            )

            # Execute
            workflow.run(cv_content="Test CV")

            # Verify files were created (new unified naming)
            assert (session.debug_dir / "brainstorm_prompt.txt").exists()
            assert (session.debug_dir / "brainstorm_response.txt").exists()
            assert (session.debug_dir / "brainstorm_full_response.json").exists()

    def test_format_output_includes_disclaimer(self):
        """Should format output with disclaimer and usage hints"""
        # Setup
        workflow = BrainstormWorkflow(api_key="test-api-key", session=None, verbose=False)

        # Execute
        formatted = workflow.format_output("Test suggestions")

        # Verify
        assert "Important Disclaimer" in formatted or "IMPORTANT DISCLAIMER" in formatted
        assert "Test suggestions" in formatted
        assert "How to Use" in formatted or "HOW TO USE" in formatted
        assert "--was" in formatted

    def test_uses_default_model_from_config(self):
        """Should use default model from config when not specified"""
        # Setup
        with patch("src.workflows.brainstorm.config") as mock_config:
            mock_config.get.return_value = "google/gemini-2.5-flash"

            workflow = BrainstormWorkflow(api_key="test-api-key", session=None, verbose=False)

            # Verify
            assert workflow.model == "google/gemini-2.5-flash"

    def test_verbose_mode_prints_progress(self, mock_http_response, capsys):
        """Should print progress messages in verbose mode"""
        # Setup
        with patch("src.workflows.brainstorm.default_http_client") as mock_http_client:
            mock_http_client.post.return_value = mock_http_response

            workflow = BrainstormWorkflow(
                api_key="test-api-key", model="test-model", session=None, verbose=True
            )

            # Execute
            workflow.run(cv_content="Test CV")

            # Verify
            captured = capsys.readouterr()
            assert "BRAINSTORMING JOB TITLES" in captured.out
            assert "CV length:" in captured.out
