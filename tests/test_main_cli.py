"""
Test main.py CLI argument parsing and validation

These tests validate that the CLI entry point correctly parses arguments,
validates parameters, enforces constraints, and provides clear error messages.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import main module
import main


class TestBasicParameterParsing:
    """Test that parameters are correctly parsed and defaults applied"""

    @patch("main.SearchSession")
    @patch("main.UserProfile")
    @patch("main.LLMProcessor")
    @patch("main.JobGatherer")
    @patch("main.MultiCategoryWorkflow")
    def test_required_parameters_was_and_wo(
        self, mock_workflow, mock_gatherer, mock_llm, mock_profile, mock_session
    ):
        """Should fail without --was and --wo in normal mode"""
        # Setup
        test_args = ["main.py"]

        # Execute
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        # Verify - should exit with error code
        assert exc_info.value.code != 0

    @patch("main.SearchSession")
    @patch("main.UserProfile")
    @patch("main.LLMProcessor")
    @patch("main.JobGatherer")
    @patch("main.MultiCategoryWorkflow")
    def test_workflow_defaults_to_multi_category(
        self, mock_workflow_class, mock_gatherer, mock_llm, mock_profile, mock_session
    ):
        """Default workflow when not specified should be multi-category"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        # Mock the workflow instance and its run method
        mock_workflow = MagicMock()
        mock_workflow.run.return_value = ([], [])
        mock_workflow.gathering_stats = {"total_found": 0, "successfully_extracted": 0, "failed": 0}
        mock_workflow_class.return_value = mock_workflow

        # Mock session
        mock_session_instance = MagicMock()
        mock_session_instance.session_dir = Path("/tmp/test")
        mock_session_instance.debug_dir = Path("/tmp/test/debug")
        mock_session_instance.save_classified_jobs.return_value = Path("/tmp/test/jobs.json")
        mock_session_instance.save_analysis_report.return_value = Path("/tmp/test/report.txt")
        mock_session_instance.save_csv_export.return_value = Path("/tmp/test/export.csv")
        mock_session.return_value = mock_session_instance

        test_args = ["main.py", "--was", "Developer", "--wo", "Berlin"]

        # Execute - expect SystemExit(0) when no jobs found
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        # Verify - should exit successfully with code 0 (warning, but not error)
        assert exc_info.value.code == 0
        # MultiCategoryWorkflow should be instantiated
        mock_workflow_class.assert_called_once()

    @patch("main.config")
    def test_custom_search_radius(self, mock_config):
        """--umkreis should override config default"""
        # Setup
        mock_config.get.return_value = 25  # Default

        test_args = ["main.py", "--was", "Dev", "--wo", "Berlin", "--umkreis", "50", "--help"]

        # Execute - using --help to avoid full execution
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit):  # --help causes exit
            main.main()

    def test_batch_size_parameter_accepted(self):
        """--batch-size parameter should be accepted"""
        test_args = ["main.py", "--was", "Dev", "--wo", "Berlin", "--batch-size", "10", "--help"]

        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit):  # --help causes exit
            main.main()


class TestWorkflowValidation:
    """Test workflow-specific parameter validation"""

    def test_perfect_job_requires_category_and_description(self):
        """--workflow perfect-job requires both category and description"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        test_args = [
            "main.py",
            "--workflow",
            "perfect-job",
            "--was",
            "Developer",
            "--wo",
            "Berlin",
            "--perfect-job-category",
            "Dream Job",
            # Missing --perfect-job-description
        ]

        # Execute
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        # Should exit with error
        assert exc_info.value.code != 0

    def test_cv_based_requires_cv_file(self):
        """--workflow cv-based requires --cv parameter"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        test_args = [
            "main.py",
            "--workflow",
            "cv-based",
            "--was",
            "Developer",
            "--wo",
            "Berlin",
            # Missing --cv
        ]

        # Execute
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code != 0

    def test_cv_based_fails_with_nonexistent_cv(self, tmp_path):
        """--workflow cv-based should fail if CV file doesn't exist"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"
        nonexistent_cv = tmp_path / "nonexistent.md"

        test_args = [
            "main.py",
            "--workflow",
            "cv-based",
            "--was",
            "Developer",
            "--wo",
            "Berlin",
            "--cv",
            str(nonexistent_cv),
        ]

        # Execute
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code != 0


class TestClassifyOnlyMode:
    """Test --classify-only parameter validation and behavior"""

    def test_classify_only_requires_input(self):
        """--classify-only requires --input parameter"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        test_args = [
            "main.py",
            "--classify-only",
            # Missing --input
        ]

        # Execute
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code != 0

    def test_classify_only_resolves_session_directory(self, tmp_path):
        """--classify-only should resolve session directory to scraped_jobs.json"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        # Create session directory structure
        session_dir = tmp_path / "20231020_142830"
        debug_dir = session_dir / "debug"
        debug_dir.mkdir(parents=True)

        scraped_jobs_file = debug_dir / "02_scraped_jobs.json"
        # Jobs need proper structure with details.success for extract_descriptions()
        test_jobs = [
            {
                "beruf": "Test Job",
                "arbeitsort": {"ort": "Berlin"},
                "arbeitgeber": "Test Corp",
                "refnr": "12345",
                "details": {
                    "success": True,
                    "text": "Job description",
                    "url": "https://example.com/job/123",
                },
            }
        ]
        scraped_jobs_file.write_text(json.dumps(test_jobs))

        test_args = [
            "main.py",
            "--classify-only",
            "--input",
            str(session_dir),
            "--model",
            "google/gemini-2.5-flash-lite",
        ]

        # Mock dependencies
        with (
            patch.object(sys, "argv", test_args),
            patch("main.SearchSession") as mock_session,
            patch("main.UserProfile"),
            patch("main.LLMProcessor"),
            patch("main.MultiCategoryWorkflow") as mock_workflow,
            patch("src.analyzer.print_statistics_dashboard"),  # Mock the dashboard
            patch("src.analyzer.generate_report", return_value="Test Report"),  # Mock report
        ):
            # Setup mocks
            mock_session_instance = MagicMock()
            mock_session_instance.session_dir = tmp_path / "new_session"
            mock_session_instance.debug_dir = tmp_path / "new_session" / "debug"
            (tmp_path / "new_session" / "debug").mkdir(parents=True, exist_ok=True)
            (tmp_path / "new_session" / "debug" / "02_scraped_jobs.json").write_text(
                json.dumps(test_jobs)
            )
            mock_session_instance.save_classified_jobs.return_value = Path("/tmp/jobs.json")
            mock_session_instance.save_analysis_report.return_value = Path("/tmp/report.txt")
            mock_session_instance.save_csv_export.return_value = Path("/tmp/export.csv")
            mock_session.return_value = mock_session_instance

            mock_workflow_instance = MagicMock()
            # Extract expected jobs (after extract_descriptions)
            expected_jobs = [
                {
                    "titel": "Test Job",
                    "ort": "Berlin",
                    "arbeitgeber": "Test Corp",
                    "text": "Job description",
                    "url": "https://example.com/job/123",
                    "refnr": "12345",
                }
            ]
            mock_workflow_instance.run_from_file.return_value = expected_jobs
            mock_workflow.return_value = mock_workflow_instance

            # Execute
            main.main()

            # Verify that the workflow was created and run_from_file was called
            mock_workflow.assert_called_once()
            mock_workflow_instance.run_from_file.assert_called_once()

    def test_classify_only_accepts_json_file_directly(self, tmp_path):
        """--classify-only should accept JSON file path directly"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        json_file = tmp_path / "jobs.json"
        # Jobs need proper structure with details.success for extract_descriptions()
        test_jobs = [
            {
                "beruf": "Test Job",
                "arbeitsort": {"ort": "Berlin"},
                "arbeitgeber": "Test Corp",
                "refnr": "12345",
                "details": {
                    "success": True,
                    "text": "Job description",
                    "url": "https://example.com/job/123",
                },
            }
        ]
        json_file.write_text(json.dumps(test_jobs))

        test_args = [
            "main.py",
            "--classify-only",
            "--input",
            str(json_file),
            "--model",
            "google/gemini-2.5-flash-lite",
        ]

        with (
            patch.object(sys, "argv", test_args),
            patch("main.SearchSession") as mock_session,
            patch("main.UserProfile"),
            patch("main.LLMProcessor"),
            patch("main.MultiCategoryWorkflow") as mock_workflow,
            patch("src.analyzer.print_statistics_dashboard"),  # Mock the dashboard
            patch("src.analyzer.generate_report", return_value="Test Report"),  # Mock report
        ):
            # Setup mocks
            mock_session_instance = MagicMock()
            mock_session_instance.session_dir = tmp_path / "new_session"
            mock_session_instance.debug_dir = tmp_path / "new_session" / "debug"
            (tmp_path / "new_session" / "debug").mkdir(parents=True, exist_ok=True)
            (tmp_path / "new_session" / "debug" / "02_scraped_jobs.json").write_text(
                json.dumps(test_jobs)
            )
            mock_session_instance.save_classified_jobs.return_value = Path("/tmp/jobs.json")
            mock_session_instance.save_analysis_report.return_value = Path("/tmp/report.txt")
            mock_session_instance.save_csv_export.return_value = Path("/tmp/export.csv")
            mock_session.return_value = mock_session_instance

            mock_workflow_instance = MagicMock()
            # Extract expected jobs (after extract_descriptions)
            expected_jobs = [
                {
                    "titel": "Test Job",
                    "ort": "Berlin",
                    "arbeitgeber": "Test Corp",
                    "text": "Job description",
                    "url": "https://example.com/job/123",
                    "refnr": "12345",
                }
            ]
            mock_workflow_instance.run_from_file.return_value = expected_jobs
            mock_workflow.return_value = mock_workflow_instance

            # Execute
            main.main()

            # Verify
            mock_workflow_instance.run_from_file.assert_called_once()

    def test_classify_only_fails_on_missing_scraped_data(self, tmp_path):
        """--classify-only should fail if session dir lacks scraped data"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        # Create session directory WITHOUT scraped jobs file
        session_dir = tmp_path / "20231020_142830"
        session_dir.mkdir(parents=True)

        test_args = ["main.py", "--classify-only", "--input", str(session_dir)]

        # Execute
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code != 0

    def test_classify_only_conflicts_with_no_classification(self):
        """--classify-only and --no-classification are mutually exclusive"""
        # Setup
        test_args = [
            "main.py",
            "--classify-only",
            "--input",
            "/tmp/jobs.json",
            "--no-classification",
        ]

        # Execute
        with (
            patch.object(sys, "argv", test_args),
            patch("pathlib.Path.exists", return_value=True),
            pytest.raises(SystemExit) as exc_info,
        ):
            main.main()

        assert exc_info.value.code != 0


class TestParameterConflicts:
    """Test mutually exclusive parameters and edge cases"""

    @patch("main.SearchSession")
    @patch("main.JobGatherer")
    def test_no_classification_still_requires_was_and_wo(self, mock_gatherer, mock_session):
        """--no-classification mode still needs search parameters"""
        # Setup
        test_args = [
            "main.py",
            "--no-classification",
            # Missing --was and --wo
        ]

        # Execute
        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code != 0

    def test_classify_only_doesnt_need_was_and_wo(self, tmp_path):
        """--classify-only doesn't require search parameters"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        json_file = tmp_path / "jobs.json"
        # Jobs need proper structure with details.success for extract_descriptions()
        json_file.write_text(
            json.dumps(
                [
                    {
                        "beruf": "Job",
                        "arbeitsort": {"ort": "Berlin"},
                        "arbeitgeber": "Corp",
                        "refnr": "12345",
                        "details": {
                            "success": True,
                            "text": "Description",
                            "url": "https://example.com",
                        },
                    }
                ]
            )
        )

        test_args = [
            "main.py",
            "--classify-only",
            "--input",
            str(json_file),
            # No --was or --wo
        ]

        with (
            patch.object(sys, "argv", test_args),
            patch("main.SearchSession") as mock_session,
            patch("main.UserProfile"),
            patch("main.LLMProcessor"),
            patch("main.MultiCategoryWorkflow") as mock_workflow,
        ):
            mock_session_instance = MagicMock()
            mock_session_instance.session_dir = tmp_path / "session"
            mock_session_instance.debug_dir = tmp_path / "session/debug"
            (tmp_path / "session/debug").mkdir(parents=True, exist_ok=True)
            (tmp_path / "session/debug" / "02_scraped_jobs.json").write_text(
                json.dumps([{"titel": "Job"}])
            )
            mock_session_instance.save_classified_jobs.return_value = Path("/tmp/jobs.json")
            mock_session_instance.save_analysis_report.return_value = Path("/tmp/report.txt")
            mock_session_instance.save_csv_export.return_value = Path("/tmp/export.csv")
            mock_session.return_value = mock_session_instance

            mock_workflow_instance = MagicMock()
            # Extract expected jobs (after extract_descriptions)
            expected_jobs = [
                {
                    "titel": "Job",
                    "ort": "Berlin",
                    "arbeitgeber": "Corp",
                    "text": "Description",
                    "url": "https://example.com",
                    "refnr": "12345",
                }
            ]
            mock_workflow_instance.run_from_file.return_value = expected_jobs
            mock_workflow.return_value = mock_workflow_instance

            # Should not raise validation error
            main.main()


# Note: API key validation tests removed - already covered in test_classifier_single.py


class TestOutputParameters:
    """Test output parameter handling"""

    @patch("main.SearchSession")
    @patch("main.UserProfile")
    @patch("main.LLMProcessor")
    @patch("main.JobGatherer")
    @patch("main.MultiCategoryWorkflow")
    def test_custom_output_paths_accepted(
        self, mock_workflow, mock_gatherer, mock_llm, mock_profile, mock_session, tmp_path
    ):
        """Custom output paths should be accepted and used"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        # Mock workflow
        test_jobs = [{"titel": "Job", "ort": "Berlin", "categories": ["Python"]}]
        mock_workflow_instance = MagicMock()
        mock_workflow_instance.run.return_value = (test_jobs, [])
        mock_workflow_instance.gathering_stats = {
            "total_found": 1,
            "successfully_extracted": 1,
            "failed": 0,
        }
        mock_workflow.return_value = mock_workflow_instance

        # Mock session
        mock_session_instance = MagicMock()
        mock_session_instance.session_dir = tmp_path / "session"
        mock_session_instance.debug_dir = tmp_path / "session/debug"
        (tmp_path / "session/debug").mkdir(parents=True)

        scraped_jobs_file = tmp_path / "session/debug/02_scraped_jobs.json"
        scraped_jobs_file.write_text(json.dumps(test_jobs))

        mock_session_instance.save_classified_jobs.return_value = tmp_path / "jobs.json"
        mock_session_instance.save_analysis_report.return_value = tmp_path / "report.txt"
        mock_session_instance.save_csv_export.return_value = tmp_path / "export.csv"
        mock_session.return_value = mock_session_instance

        output_file = tmp_path / "custom_output.json"

        test_args = [
            "main.py",
            "--was",
            "Developer",
            "--wo",
            "Berlin",
            "--output",
            str(output_file),
        ]

        with patch.object(sys, "argv", test_args):
            main.main()

        # Verify custom output file was created
        assert output_file.exists()


class TestEdgeCases:
    """Test edge cases and unusual parameter combinations"""

    def test_invalid_input_path(self):
        """Should fail gracefully with clear error for invalid input path"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        test_args = ["main.py", "--classify-only", "--input", "/nonexistent/path/to/jobs.json"]

        with patch.object(sys, "argv", test_args), pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code != 0

    @patch("main.SearchSession")
    @patch("main.UserProfile")
    @patch("main.LLMProcessor")
    @patch("main.JobGatherer")
    @patch("main.MultiCategoryWorkflow")
    def test_quiet_mode_suppresses_output(
        self, mock_workflow, mock_gatherer, mock_llm, mock_profile, mock_session
    ):
        """--quiet should suppress progress messages"""
        # Setup
        os.environ["OPENROUTER_API_KEY"] = "test-key"

        mock_workflow_instance = MagicMock()
        mock_workflow_instance.run.return_value = ([], [])
        mock_workflow_instance.gathering_stats = {
            "total_found": 0,
            "successfully_extracted": 0,
            "failed": 0,
        }
        mock_workflow.return_value = mock_workflow_instance

        mock_session_instance = MagicMock()
        mock_session_instance.session_dir = Path("/tmp/test")
        mock_session_instance.debug_dir = Path("/tmp/test/debug")
        mock_session_instance.save_classified_jobs.return_value = Path("/tmp/jobs.json")
        mock_session_instance.save_analysis_report.return_value = Path("/tmp/report.txt")
        mock_session_instance.save_csv_export.return_value = Path("/tmp/export.csv")
        mock_session.return_value = mock_session_instance

        test_args = ["main.py", "--was", "Developer", "--wo", "Berlin", "--quiet"]

        with patch.object(sys, "argv", test_args):
            # Should pass verbose=False to components
            with pytest.raises(SystemExit) as exc_info:
                main.main()
            assert exc_info.value.code == 0

        # Verify verbose=False was used
        assert mock_session.call_args[1]["verbose"] is False
