"""
Tests for src/data/gatherer.py - Job data gathering orchestration

The gatherer module coordinates job searches, scraping, and data extraction.
These tests verify the orchestration logic while mocking external dependencies.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.data.gatherer import JobGatherer


@pytest.fixture(autouse=True)
def clean_test_database():
    """Clean up test database before each test"""
    db_path = Path("data/database/jobs_global.json")
    if db_path.exists():
        db_path.unlink()
    yield
    # Cleanup after test too
    if db_path.exists():
        db_path.unlink()


class TestJobGathererInitialization:
    """Test JobGatherer instance creation and configuration"""

    def test_gatherer_initializes_with_defaults(self):
        """Should create gatherer with default values"""
        gatherer = JobGatherer()

        assert gatherer.session is None
        assert gatherer.verbose is True

    def test_gatherer_initializes_with_session(self):
        """Should store session reference when provided"""
        mock_session = Mock()
        gatherer = JobGatherer(session=mock_session, verbose=False)

        assert gatherer.session is mock_session
        assert gatherer.verbose is False


class TestGatherBasicWorkflow:
    """Test the main gather() method with different configurations"""

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_complete_workflow(self, mock_extract, mock_fetch, mock_search, tmp_path):
        """Should execute full workflow: search -> scrape -> extract"""
        # Arrange
        mock_search.return_value = [
            {"refnr": "123", "titel": "Python Dev"},
            {"refnr": "456", "titel": "Java Dev"},
        ]
        mock_fetch.return_value = [
            {"refnr": "123", "titel": "Python Dev", "html": "<p>Details</p>"},
            {"refnr": "456", "titel": "Java Dev", "html": "<p>More details</p>"},
        ]
        mock_extract.return_value = (
            [
                {"refnr": "123", "titel": "Python Dev", "description": "Python job"},
                {"refnr": "456", "titel": "Java Dev", "description": "Java job"},
            ],
            [],  # No failed jobs
        )

        gatherer = JobGatherer(database_path=tmp_path / "test_db.json")

        # Act
        jobs, _failed_jobs, stats = gatherer.gather(
            was="Developer", wo="Berlin", umkreis=50, size=100, max_pages=1
        )

        # Assert
        assert len(jobs) == 2
        assert jobs[0]["description"] == "Python job"
        assert stats["total_found"] == 2
        assert stats["total_scraped"] == 2
        assert stats["successfully_extracted"] == 2

        # Verify function calls
        mock_search.assert_called_once()
        mock_fetch.assert_called_once()
        mock_extract.assert_called_once()

    @patch("src.data.gatherer.search_jobs")
    def test_gather_returns_empty_when_no_jobs_found(self, mock_search, tmp_path):
        """Should return empty list and zero stats when no jobs found"""
        # Arrange
        mock_search.return_value = []
        gatherer = JobGatherer(database_path=tmp_path / "test_db.json")

        # Act
        jobs, _failed_jobs, stats = gatherer.gather(was="Nonexistent", wo="Nowhere")

        # Assert
        assert jobs == []
        assert stats["total_found"] == 0
        assert stats["total_scraped"] == 0
        assert stats["successfully_extracted"] == 0

    @patch("src.data.gatherer.search_jobs")
    def test_gather_skips_scraping_when_disabled(self, mock_search, tmp_path):
        """Should skip scraping when enable_scraping=False"""
        # Arrange
        mock_search.return_value = [{"refnr": "123", "titel": "Dev Job"}]
        gatherer = JobGatherer(database_path=tmp_path / "test_db.json")

        # Act
        with patch("src.data.gatherer.fetch_detailed_listings") as mock_fetch:
            jobs, _failed_jobs, stats = gatherer.gather(
                was="Dev", wo="Berlin", enable_scraping=False
            )

            # Assert
            assert len(jobs) == 1
            assert stats["total_found"] == 1
            assert stats["total_scraped"] == 1
            assert stats["successfully_extracted"] == 1
            mock_fetch.assert_not_called()

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_uses_config_defaults_when_params_none(
        self, mock_extract, mock_fetch, mock_search, test_config, tmp_path
    ):
        """Should use config defaults when optional parameters not provided"""
        # Arrange

        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer()

        # Act
        with patch("src.data.gatherer.config.get") as mock_config_get:

            def config_side_effect(key, default=None):
                config_values = {
                    "search.defaults.radius_km": 30,
                    "search.defaults.page_size": 50,
                    "search.defaults.max_pages": 2,
                    "api.delays.scraping": 0.5,
                }
                return config_values.get(key, default)

            mock_config_get.side_effect = config_side_effect

            _jobs, _failed_jobs, _stats = gatherer.gather(was="Dev", wo="Berlin")

            # Assert - search_jobs should be called with config defaults
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args.kwargs
            assert call_kwargs["size"] == 50
            assert call_kwargs["max_pages"] == 2
            assert call_kwargs["umkreis"] == 30


class TestGatherSessionIntegration:
    """Test gatherer integration with SearchSession"""

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_passes_session_to_search(self, mock_extract, mock_fetch, mock_search):
        """Should pass session to search_jobs function"""
        # Arrange
        mock_session = Mock()
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer(session=mock_session)

        # Act
        _jobs, _failed_jobs, _stats = gatherer.gather(was="Dev", wo="Berlin")

        # Assert
        mock_search.assert_called_once()
        assert mock_search.call_args.kwargs["session"] is mock_session

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_passes_session_to_fetch(self, mock_extract, mock_fetch, mock_search):
        """Should pass session to fetch_detailed_listings function"""
        # Arrange
        mock_session = Mock()
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer(session=mock_session)

        # Act
        _jobs, _failed_jobs, _stats = gatherer.gather(was="Dev", wo="Berlin")

        # Assert
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args.kwargs["session"] is mock_session


class TestGatherSearchParameters:
    """Test that search parameters are correctly passed through"""

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_passes_arbeitszeit_filter(self, mock_extract, mock_fetch, mock_search):
        """Should pass arbeitszeit filter to search_jobs"""
        # Arrange
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer()

        # Act
        _jobs, _failed_jobs, _stats = gatherer.gather(
            was="Dev",
            wo="Berlin",
            arbeitszeit="vz",  # Full-time
        )

        # Assert
        mock_search.assert_called_once()
        assert mock_search.call_args.kwargs["arbeitszeit"] == "vz"

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_handles_weiterbildung_inclusion(self, mock_extract, mock_fetch, mock_search):
        """Should correctly set exclude_weiterbildung based on include_weiterbildung"""
        # Arrange
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer()

        # Act - include_weiterbildung=True means exclude_weiterbildung=False
        _jobs, _failed_jobs, _stats = gatherer.gather(
            was="Dev", wo="Berlin", include_weiterbildung=True
        )

        # Assert
        mock_search.assert_called_once()
        assert mock_search.call_args.kwargs["exclude_weiterbildung"] is False

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_excludes_weiterbildung_by_default(self, mock_extract, mock_fetch, mock_search):
        """Should exclude weiterbildung by default"""
        # Arrange
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer()

        # Act
        _jobs, _failed_jobs, _stats = gatherer.gather(was="Dev", wo="Berlin")

        # Assert
        mock_search.assert_called_once()
        assert mock_search.call_args.kwargs["exclude_weiterbildung"] is True


class TestGatherScrapingConfiguration:
    """Test scraping delay and verbosity configuration"""

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_uses_custom_scraping_delay(self, mock_extract, mock_fetch, mock_search):
        """Should pass custom scraping delay to fetch_detailed_listings"""
        # Arrange
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer()

        # Act
        _jobs, _failed_jobs, _stats = gatherer.gather(was="Dev", wo="Berlin", scraping_delay=2.5)

        # Assert
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args.kwargs["delay"] == 2.5

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_passes_verbose_flag(self, mock_extract, mock_fetch, mock_search):
        """Should pass verbose flag to fetch_detailed_listings"""
        # Arrange
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer(verbose=False)

        # Act
        _jobs, _failed_jobs, _stats = gatherer.gather(was="Dev", wo="Berlin")

        # Assert
        mock_fetch.assert_called_once()
        assert mock_fetch.call_args.kwargs["verbose"] is False


class TestGatherFromRawData:
    """Test processing of pre-fetched job data"""

    def test_gather_from_raw_data_returns_jobs_unchanged(self):
        """Should return jobs as-is (pass-through)"""
        # Arrange
        jobs = [{"refnr": "123", "titel": "Dev Job 1"}, {"refnr": "456", "titel": "Dev Job 2"}]
        gatherer = JobGatherer()

        # Act
        result = gatherer.gather_from_raw_data(jobs)

        # Assert
        assert result == jobs
        assert result is jobs  # Should be the same object

    def test_gather_from_raw_data_handles_empty_list(self):
        """Should handle empty job list"""
        # Arrange
        gatherer = JobGatherer()

        # Act
        result = gatherer.gather_from_raw_data([])

        # Assert
        assert result == []


class TestGatherStatistics:
    """Test gathering statistics calculation"""

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_calculates_stats_correctly(self, mock_extract, mock_fetch, mock_search):
        """Should calculate accurate statistics for partial extraction success"""
        # Arrange - 5 found, 4 scraped, 3 extracted
        mock_search.return_value = [
            {"refnr": "1"},
            {"refnr": "2"},
            {"refnr": "3"},
            {"refnr": "4"},
            {"refnr": "5"},
        ]
        mock_fetch.return_value = [
            {"refnr": "1", "html": "test1"},
            {"refnr": "2", "html": "test2"},
            {"refnr": "3", "html": "test3"},
            {"refnr": "4", "html": "test4"},
        ]
        mock_extract.return_value = (
            [
                {"refnr": "1", "description": "desc1"},
                {"refnr": "2", "description": "desc2"},
                {"refnr": "3", "description": "desc3"},
            ],
            [{"titel": "Failed Job", "url": "http://fail.com"}],  # One failed job
        )

        gatherer = JobGatherer()

        # Act
        jobs, _failed_jobs, stats = gatherer.gather(was="Dev", wo="Berlin")

        # Assert
        assert stats["total_found"] == 5
        assert stats["total_scraped"] == 4
        assert stats["successfully_extracted"] == 3
        assert len(jobs) == 3

    @patch("src.data.gatherer.search_jobs")
    def test_gather_stats_when_scraping_disabled(self, mock_search):
        """Should set all stats equal when scraping is disabled"""
        # Arrange
        mock_search.return_value = [{"refnr": "1"}, {"refnr": "2"}, {"refnr": "3"}]
        gatherer = JobGatherer()

        # Act
        _jobs, _failed_jobs, stats = gatherer.gather(was="Dev", wo="Berlin", enable_scraping=False)

        # Assert
        assert stats["total_found"] == 3
        assert stats["total_scraped"] == 3
        assert stats["successfully_extracted"] == 3


class TestGatherEdgeCases:
    """Test edge cases and error conditions"""

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_handles_empty_extraction_result(self, mock_extract, mock_fetch, mock_search):
        """Should handle case where scraping succeeds but extraction fails"""
        # Arrange
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "<div>Bad HTML</div>"}]
        mock_extract.return_value = ([], [])  # (successful, failed) - all failed extraction

        gatherer = JobGatherer()

        # Act
        jobs, _failed_jobs, stats = gatherer.gather(was="Dev", wo="Berlin")

        # Assert
        assert len(jobs) == 0
        assert stats["total_found"] == 1
        assert stats["total_scraped"] == 1
        assert stats["successfully_extracted"] == 0

    @patch("src.data.gatherer.search_jobs")
    @patch("src.data.gatherer.fetch_detailed_listings")
    @patch("src.data.gatherer.extract_descriptions")
    def test_gather_with_all_parameters_specified(self, mock_extract, mock_fetch, mock_search):
        """Should handle all parameters being explicitly provided"""
        # Arrange
        mock_search.return_value = [{"refnr": "123"}]
        mock_fetch.return_value = [{"refnr": "123", "html": "test"}]
        mock_extract.return_value = (
            [{"refnr": "123", "description": "test"}],
            [],
        )  # (successful, failed)

        gatherer = JobGatherer(session=Mock(), verbose=False)

        # Act
        jobs, _failed_jobs, _stats = gatherer.gather(
            was="Senior Python Developer",
            wo="Bergisch Gladbach",
            umkreis=15,
            size=50,
            max_pages=3,
            arbeitszeit="vz",
            include_weiterbildung=False,
            enable_scraping=True,
            scraping_delay=1.5,
        )

        # Assert
        assert len(jobs) == 1
        mock_search.assert_called_once()
        mock_fetch.assert_called_once()

        # Verify all parameters were passed correctly
        search_kwargs = mock_search.call_args.kwargs
        assert search_kwargs["was"] == "Senior Python Developer"
        assert search_kwargs["wo"] == "Bergisch Gladbach"
        assert search_kwargs["size"] == 50
        assert search_kwargs["max_pages"] == 3
        assert search_kwargs["umkreis"] == 15
        assert search_kwargs["arbeitszeit"] == "vz"
        assert search_kwargs["exclude_weiterbildung"] is True
