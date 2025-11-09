"""
Tests for session.py - Search session management

These tests verify:
1. Session directory creation and structure
2. Debug artifact saving (API responses, scraped data, LLM interactions)
3. User-facing output generation (classified jobs, reports, CSV)
4. File I/O operations and error handling
5. Config integration for file paths
"""

import csv
import json
from pathlib import Path
from unittest.mock import patch

from src.session import SearchSession


class TestSessionInitialization:
    """Test session creation and directory setup"""

    def test_session_creates_directories(self, tmp_path):
        """Should create session and debug directories on init"""
        session = SearchSession(
            base_dir=str(tmp_path), timestamp="test_20230101_120000", verbose=False
        )

        assert session.session_dir.exists()
        assert session.debug_dir.exists()
        assert session.session_dir == tmp_path / "test_20230101_120000"
        assert session.debug_dir == tmp_path / "test_20230101_120000" / "debug"

    def test_session_uses_custom_timestamp(self, tmp_path):
        """Should use provided timestamp instead of generating one"""
        custom_timestamp = "20250615_093000"
        session = SearchSession(base_dir=str(tmp_path), timestamp=custom_timestamp, verbose=False)

        assert session.timestamp == custom_timestamp
        assert custom_timestamp in str(session.session_dir)

    def test_session_generates_timestamp_when_none_provided(self, tmp_path):
        """Should generate timestamp automatically if not provided"""
        session = SearchSession(base_dir=str(tmp_path), verbose=False)

        # Timestamp should be in format YYYYMMDD_HHMMSS
        assert len(session.timestamp) == 15
        assert session.timestamp[8] == "_"

    def test_session_creates_nested_directories(self, tmp_path):
        """Should create parent directories if they don't exist"""
        nested_path = tmp_path / "level1" / "level2" / "level3"
        session = SearchSession(base_dir=str(nested_path), timestamp="test", verbose=False)

        assert session.session_dir.exists()
        assert nested_path.exists()

    def test_session_handles_existing_directories(self, tmp_path):
        """Should work correctly when directories already exist"""
        session_dir = tmp_path / "existing_session"
        session_dir.mkdir(parents=True)
        debug_dir = session_dir / "debug"
        debug_dir.mkdir()

        # Should not fail when directories exist
        session = SearchSession(base_dir=str(tmp_path), timestamp="existing_session", verbose=False)

        assert session.session_dir.exists()
        assert session.debug_dir.exists()


class TestDebugArtifacts:
    """Test saving debug artifacts (raw data for debugging)"""

    def test_save_raw_api_response(self, tmp_path):
        """Should save raw API response as JSON in debug directory"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        api_data = {
            "maxErgebnisse": "150",
            "stellenangebote": [{"beruf": "Developer", "refnr": "123"}],
        }

        session.save_raw_api_response(api_data)

        # Verify file was created
        json_file = session.debug_dir / "01_raw_api_response.json"
        assert json_file.exists()

        # Verify content
        with open(json_file, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == api_data

    def test_save_scraped_jobs(self, tmp_path):
        """Should save scraped jobs with details to JSON"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [
            {
                "titel": "Python Developer",
                "ort": "Berlin",
                "details": {"success": True, "text": "Job description here", "text_length": 100},
            }
        ]

        session.save_scraped_jobs(jobs)

        # Verify file was created
        json_file = session.debug_dir / "02_scraped_jobs.json"
        assert json_file.exists()

        # Verify content
        with open(json_file, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == jobs
        assert saved_data[0]["titel"] == "Python Developer"

    def test_save_llm_request(self, tmp_path):
        """Should save LLM request prompt to text file"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        request_text = """Classify the following job:
Job Title: Python Developer
Description: Looking for experienced Python engineer..."""

        session.save_llm_request(request_text)

        # Verify file was created
        txt_file = session.debug_dir / "03_llm_request.txt"
        assert txt_file.exists()

        # Verify content
        with open(txt_file, encoding="utf-8") as f:
            saved_text = f.read()
        assert saved_text == request_text
        assert "Python Developer" in saved_text

    def test_save_llm_response(self, tmp_path):
        """Should save LLM response to text file"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        response_text = '["Python", "Backend Development"]'

        session.save_llm_response(response_text)

        # Verify file was created
        txt_file = session.debug_dir / "04_llm_response.txt"
        assert txt_file.exists()

        # Verify content
        with open(txt_file, encoding="utf-8") as f:
            saved_text = f.read()
        assert saved_text == response_text

    def test_append_llm_interaction_first_time(self, tmp_path):
        """Should append LLM interaction to debug files (first time)"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        request = "Classify job 1"
        response = '["Category A"]'
        batch_info = "Batch 1/3"

        session.append_llm_interaction(request, response, batch_info)

        # Check request file
        request_file = session.debug_dir / "03_llm_request.txt"
        assert request_file.exists()
        content = request_file.read_text(encoding="utf-8")
        assert "Batch 1/3" in content
        assert "Classify job 1" in content

        # Check response file
        response_file = session.debug_dir / "04_llm_response.txt"
        assert response_file.exists()
        content = response_file.read_text(encoding="utf-8")
        assert "Batch 1/3" in content
        assert '["Category A"]' in content

    def test_append_llm_interaction_multiple_times(self, tmp_path):
        """Should append multiple LLM interactions with separators"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        # First interaction
        session.append_llm_interaction("Request 1", "Response 1", "Batch 1/2")

        # Second interaction
        session.append_llm_interaction("Request 2", "Response 2", "Batch 2/2")

        # Check request file has both
        request_file = session.debug_dir / "03_llm_request.txt"
        content = request_file.read_text(encoding="utf-8")
        assert "Batch 1/2" in content
        assert "Request 1" in content
        assert "Batch 2/2" in content
        assert "Request 2" in content
        assert "=" * 80 in content  # Separator

    def test_save_handles_unicode_characters(self, tmp_path):
        """Should correctly save Unicode characters (German umlauts, etc.)"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [
            {
                "titel": "Software-Entwickler für München",
                "ort": "München",
                "arbeitgeber": "Große Firma GmbH",
            }
        ]

        session.save_scraped_jobs(jobs)

        json_file = session.debug_dir / "02_scraped_jobs.json"
        with open(json_file, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert saved_data[0]["ort"] == "München"
        assert "Große" in saved_data[0]["arbeitgeber"]


class TestUserOutputs:
    """Test user-facing output files"""

    def test_save_classified_jobs(self, tmp_path):
        """Should save classified jobs to JSON in session root"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [{"titel": "Python Developer", "categories": ["Python", "Backend"], "ort": "Berlin"}]

        file_path = session.save_classified_jobs(jobs)

        # Verify file is in session root (not debug dir)
        assert "debug" not in file_path
        saved_file = Path(file_path)
        assert saved_file.exists()
        assert saved_file.parent == session.session_dir

        # Verify content
        with open(saved_file, encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data == jobs

    def test_save_analysis_report(self, tmp_path):
        """Should save analysis report as text file"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        report = """Job Search Analysis Report
================================

Total jobs analyzed: 50
Categories found:
- Python: 20 jobs
- Java: 15 jobs
- Other: 15 jobs
"""

        file_path = session.save_analysis_report(report)

        # Verify file exists
        saved_file = Path(file_path)
        assert saved_file.exists()

        # Verify content
        with open(saved_file, encoding="utf-8") as f:
            saved_text = f.read()
        assert saved_text == report
        assert "Total jobs analyzed: 50" in saved_text

    def test_save_csv_export_basic(self, tmp_path):
        """Should export jobs to CSV with correct columns"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [
            {
                "titel": "Python Developer",
                "ort": "Berlin",
                "arbeitgeber": "Tech Corp",
                "categories": ["Python", "Backend"],
                "url": "https://example.com/job1",
            }
        ]

        file_path = session.save_csv_export(jobs)

        # Verify file exists
        saved_file = Path(file_path)
        assert saved_file.exists()

        # Read and verify CSV content
        with open(saved_file, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Check header
        assert rows[0] == [
            "Titel",
            "Ort",
            "Arbeitgeber",
            "Categories",
            "Truncated",
            "Original_Length",
            "URL",
        ]

        # Check data row
        assert rows[1][0] == "Python Developer"
        assert rows[1][1] == "Berlin"
        assert rows[1][2] == "Tech Corp"
        assert rows[1][3] == "Python, Backend"
        assert rows[1][4] == "NO"  # Not truncated

    def test_save_csv_export_with_truncation_info(self, tmp_path):
        """Should include truncation information in CSV export"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [
            {
                "titel": "Job 1",
                "ort": "Berlin",
                "arbeitgeber": "Company",
                "categories": ["Python"],
                "_truncated": True,
                "_original_text_length": 5000,
                "url": "https://example.com/job1",
            },
            {
                "titel": "Job 2",
                "ort": "Hamburg",
                "arbeitgeber": "Company",
                "categories": ["Java"],
                "_truncated": False,
                "url": "https://example.com/job2",
            },
        ]

        file_path = session.save_csv_export(jobs)

        with open(file_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Job 1 should show truncation
        assert rows[1][4] == "YES"
        assert rows[1][5] == "5000"

        # Job 2 should not show truncation
        assert rows[2][4] == "NO"

    def test_save_csv_export_handles_missing_fields(self, tmp_path):
        """Should handle missing optional fields gracefully"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [
            {
                "titel": "Job Title",
                # Missing: ort, arbeitgeber, categories, url
            }
        ]

        file_path = session.save_csv_export(jobs)

        with open(file_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Should have empty strings for missing fields
        assert rows[1][0] == "Job Title"
        assert rows[1][1] == ""  # Missing ort
        assert rows[1][2] == ""  # Missing arbeitgeber
        assert rows[1][3] == ""  # Empty categories list
        assert rows[1][6] == ""  # Missing URL

    def test_save_csv_export_multiple_jobs(self, tmp_path):
        """Should export multiple jobs correctly"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [
            {
                "titel": "Job 1",
                "ort": "Berlin",
                "arbeitgeber": "A",
                "categories": ["Python"],
                "url": "url1",
            },
            {
                "titel": "Job 2",
                "ort": "Hamburg",
                "arbeitgeber": "B",
                "categories": ["Java"],
                "url": "url2",
            },
            {
                "titel": "Job 3",
                "ort": "Munich",
                "arbeitgeber": "C",
                "categories": ["C#"],
                "url": "url3",
            },
        ]

        file_path = session.save_csv_export(jobs)

        with open(file_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Should have header + 3 data rows
        assert len(rows) == 4
        assert rows[1][0] == "Job 1"
        assert rows[2][0] == "Job 2"
        assert rows[3][0] == "Job 3"


class TestSessionUtilities:
    """Test utility methods"""

    def test_get_summary_returns_structure_info(self, tmp_path):
        """Should return formatted summary of session structure"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        summary = session.get_summary()

        assert str(session.session_dir) in summary
        assert "debug/" in summary
        assert "01_raw_api_response.json" in summary
        assert "02_scraped_jobs.json" in summary
        assert "analysis_report.txt" in summary
        assert "jobs_classified.json" in summary


class TestConfigIntegration:
    """Test that session uses config for file paths"""

    def test_session_uses_config_for_base_directory(self, tmp_path):
        """Should use base directory from config when not specified"""

        with patch("src.session.config.get") as mock_get:
            mock_get.return_value = str(tmp_path / "custom_searches")

            session = SearchSession(timestamp="test", verbose=False)

            mock_get.assert_called_with("paths.directories.searches", "data/searches")
            assert "custom_searches" in str(session.session_dir)

    def test_session_uses_config_for_debug_filenames(self, tmp_path):
        """Should use debug filenames from config"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        with patch("src.session.config.get") as mock_get:
            mock_get.return_value = "custom_api_response.json"

            session.save_raw_api_response({"test": "data"})

            # Verify config was queried for filename
            mock_get.assert_called_with(
                "paths.files.debug.raw_api_response", "01_raw_api_response.json"
            )


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_session_saves_empty_list(self, tmp_path):
        """Should handle saving empty job lists"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        # Should not crash with empty list
        session.save_scraped_jobs([])
        session.save_classified_jobs([])
        file_path = session.save_csv_export([])

        # Verify CSV has only header
        with open(file_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 1  # Only header

    def test_session_handles_very_large_data(self, tmp_path):
        """Should handle large job lists without issues"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        # Create large job list
        large_jobs = [
            {
                "titel": f"Job {i}",
                "ort": "Berlin",
                "arbeitgeber": f"Company {i}",
                "categories": ["Python"],
                "text": "x" * 10000,  # 10KB per job
            }
            for i in range(100)  # 100 jobs = ~1MB
        ]

        # Should complete without errors
        session.save_scraped_jobs(large_jobs)

        # Verify file was created
        json_file = session.debug_dir / "02_scraped_jobs.json"
        assert json_file.exists()

        # Verify we can read it back
        with open(json_file, encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded) == 100

    def test_session_handles_special_characters_in_data(self, tmp_path):
        """Should handle special characters in job data"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        jobs = [
            {
                "titel": "Job with \"quotes\" and 'apostrophes'",
                "ort": "Berlin & Hamburg",
                "arbeitgeber": "Company <Special> Chars",
                "categories": ["C++", "C#"],
                "url": "https://example.com?param=value&other=123",
            }
        ]

        # Should save without errors
        session.save_classified_jobs(jobs)
        file_path = session.save_csv_export(jobs)

        # Verify CSV handling of special characters
        with open(file_path, encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert "quotes" in rows[1][0]
        assert "&" in rows[1][1]

    def test_session_overwrites_existing_files(self, tmp_path):
        """Should overwrite files if they already exist"""
        session = SearchSession(base_dir=str(tmp_path), timestamp="test", verbose=False)

        # Save first version
        session.save_classified_jobs([{"titel": "Job 1"}])

        # Save second version (should overwrite)
        session.save_classified_jobs([{"titel": "Job 2"}])

        # Read back - should have second version
        json_file = session.session_dir / "jobs_classified.json"
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["titel"] == "Job 2"
