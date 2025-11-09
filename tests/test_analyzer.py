"""
Tests for analyzer.py - Statistical analysis of classified job listings

These tests verify:
1. Category counting and analysis
2. Percentage calculations
3. Statistics printing (dashboard formatting)
4. Report generation with various options
5. Edge cases (empty data, division by zero, etc.)
"""

import logging

import pytest

from src.analyzer import (
    analyze_categories,
    calculate_percentages,
    generate_report,
    print_statistics,
    print_statistics_dashboard,
)


@pytest.fixture
def capture_logs(caplog):
    """Configure caplog to capture analyzer module logs"""
    caplog.set_level(logging.INFO, logger="analyzer")
    return caplog


class TestAnalyzeCategories:
    """Test category counting functionality"""

    def test_analyze_categories_basic(self):
        """Should count jobs in each category"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python", "Backend"]},
            {"titel": "Job 2", "categories": ["Python", "DevOps"]},
            {"titel": "Job 3", "categories": ["Java"]},
        ]

        result = analyze_categories(jobs)

        assert result["Python"] == 2
        assert result["Backend"] == 1
        assert result["DevOps"] == 1
        assert result["Java"] == 1

    def test_analyze_categories_empty_list(self):
        """Should handle empty job list"""
        result = analyze_categories([])
        assert result == {}

    def test_analyze_categories_no_categories(self):
        """Should handle jobs without categories field"""
        jobs: list[dict] = [
            {"titel": "Job 1"},
            {"titel": "Job 2", "categories": []},
            {"titel": "Job 3", "categories": ["Python"]},
        ]

        result = analyze_categories(jobs)

        assert result.get("Python") == 1
        # Jobs without categories should not create entries

    def test_analyze_categories_multiple_categories_per_job(self):
        """Should count each category separately"""
        jobs = [
            {"categories": ["Python", "Java", "C++"]},
        ]

        result = analyze_categories(jobs)

        assert result["Python"] == 1
        assert result["Java"] == 1
        assert result["C++"] == 1

    def test_analyze_categories_same_category_multiple_jobs(self):
        """Should accumulate counts across multiple jobs"""
        jobs = [
            {"categories": ["Python"]},
            {"categories": ["Python"]},
            {"categories": ["Python"]},
            {"categories": ["Java"]},
        ]

        result = analyze_categories(jobs)

        assert result["Python"] == 3
        assert result["Java"] == 1

    def test_analyze_categories_case_sensitivity(self):
        """Should treat categories as case-sensitive"""
        jobs = [
            {"categories": ["Python"]},
            {"categories": ["python"]},
            {"categories": ["PYTHON"]},
        ]

        result = analyze_categories(jobs)

        # Should be treated as 3 different categories
        assert result["Python"] == 1
        assert result["python"] == 1
        assert result["PYTHON"] == 1


class TestCalculatePercentages:
    """Test percentage calculation"""

    def test_calculate_percentages_basic(self):
        """Should calculate percentages correctly"""
        category_counts = {"Python": 30, "Java": 20, "Other": 10}
        total_jobs = 60

        result = calculate_percentages(category_counts, total_jobs)

        assert result["Python"] == (30, 50.0)
        assert result["Java"] == (20, 33.33333333333333)
        assert result["Other"] == (10, 16.666666666666664)

    def test_calculate_percentages_zero_total(self):
        """Should handle zero total jobs (division by zero)"""
        category_counts = {"Python": 0, "Java": 0}
        total_jobs = 0

        result = calculate_percentages(category_counts, total_jobs)

        assert result["Python"] == (0, 0)
        assert result["Java"] == (0, 0)

    def test_calculate_percentages_empty_counts(self):
        """Should handle empty category counts"""
        result = calculate_percentages({}, 100)
        assert result == {}

    def test_calculate_percentages_all_jobs_one_category(self):
        """Should correctly calculate 100% for single category"""
        category_counts = {"Python": 50}
        total_jobs = 50

        result = calculate_percentages(category_counts, total_jobs)

        assert result["Python"] == (50, 100.0)

    def test_calculate_percentages_fractional_percentages(self):
        """Should handle fractional percentages"""
        category_counts = {
            "Python": 1,
            "Java": 2,
        }
        total_jobs = 3

        result = calculate_percentages(category_counts, total_jobs)

        assert result["Python"] == (1, 33.33333333333333)
        assert result["Java"] == (2, 66.66666666666666)


class TestPrintStatistics:
    """Test statistics printing (legacy function)"""

    def test_print_statistics_basic(self):
        """Should print formatted statistics without crashing"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
            {"titel": "Job 2", "categories": ["Java"]},
            {"titel": "Job 3", "categories": ["Python"]},
        ]

        # Should complete without errors
        print_statistics(jobs, total_jobs=3, successful_fetches=3)

    def test_print_statistics_with_truncation_warning(self):
        """Should display truncation warnings without crashing"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"], "_truncated": True},
            {"titel": "Job 2", "categories": ["Java"], "_truncated": False},
            {"titel": "Job 3", "categories": ["Python"], "_truncated": True},
        ]

        # Should complete without errors
        print_statistics(jobs, total_jobs=3, successful_fetches=3)

    def test_print_statistics_no_truncation(self):
        """Should work when no jobs are truncated"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
            {"titel": "Job 2", "categories": ["Java"]},
        ]

        # Should complete without errors
        print_statistics(jobs, total_jobs=2, successful_fetches=2)

    def test_print_statistics_defaults_successful_fetches(self):
        """Should default successful_fetches to len(classified_jobs)"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
            {"titel": "Job 2", "categories": ["Java"]},
        ]

        # Should complete without errors (no successful_fetches arg)
        print_statistics(jobs, total_jobs=10)


class TestPrintStatisticsDashboard:
    """Test modern dashboard printing"""

    def test_dashboard_prints_summary(self):
        """Should print formatted dashboard summary without crashing"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
            {"titel": "Job 2", "categories": ["Java"]},
        ]

        # Should complete without errors
        print_statistics_dashboard(
            classified_jobs=jobs,
            total_jobs=10,
            successful_fetches=8,
            truncation_count=0,
            error_count=0,
        )

    def test_dashboard_shows_errors_when_present(self):
        """Should handle error information without crashing"""
        jobs = [{"titel": "Job 1", "categories": ["Python"]}]

        # Should complete without errors
        print_statistics_dashboard(
            classified_jobs=jobs,
            total_jobs=10,
            successful_fetches=5,
            truncation_count=0,
            error_count=5,
        )

    def test_dashboard_shows_truncation_warning_when_present(self):
        """Should handle truncation warnings without crashing"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
            {"titel": "Job 2", "categories": ["Java"]},
        ]

        # Should complete without errors
        print_statistics_dashboard(
            classified_jobs=jobs,
            total_jobs=10,
            successful_fetches=8,
            truncation_count=5,
            error_count=0,
        )

    def test_dashboard_shows_no_truncation_message(self):
        """Should work when no truncation present"""
        jobs = [{"titel": "Job 1", "categories": ["Python"]}]

        # Should complete without errors
        print_statistics_dashboard(
            classified_jobs=jobs,
            total_jobs=10,
            successful_fetches=8,
            truncation_count=0,
            error_count=0,
        )

    def test_dashboard_category_distribution(self):
        """Should show category distribution without crashing"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
            {"titel": "Job 2", "categories": ["Python"]},
            {"titel": "Job 3", "categories": ["Java"]},
        ]

        # Should complete without errors
        print_statistics_dashboard(
            classified_jobs=jobs,
            total_jobs=10,
            successful_fetches=3,
            truncation_count=0,
            error_count=0,
        )


class TestGenerateReport:
    """Test report generation"""

    def test_generate_report_basic(self):
        """Should generate formatted text report"""
        jobs = [
            {"titel": "Python Dev", "ort": "Berlin", "categories": ["Python"]},
            {"titel": "Java Dev", "ort": "Hamburg", "categories": ["Java"]},
        ]

        report = generate_report(jobs, total_jobs=2)

        assert "JOB MARKET ANALYSIS REPORT" in report
        assert "Total jobs found: 2" in report
        assert "Successfully analyzed: 2" in report
        assert "Python" in report
        assert "Java" in report

    def test_generate_report_with_search_params(self):
        """Should include search parameters in report"""
        jobs = [{"titel": "Dev", "categories": ["Python"]}]
        search_params = {"was": "Python Developer", "wo": "Berlin", "umkreis": 25}

        report = generate_report(jobs, total_jobs=1, search_params=search_params)

        assert "Search Parameters:" in report
        assert "Position: Python Developer" in report
        assert "Location: Berlin" in report
        assert "Radius: 25 km" in report

    def test_generate_report_with_gathering_stats(self):
        """Should use gathering stats when provided"""
        jobs = [{"titel": "Dev", "categories": ["Python"]}]
        gathering_stats = {"total_found": 100, "successfully_extracted": 80}

        report = generate_report(jobs, total_jobs=100, gathering_stats=gathering_stats)

        assert "Total jobs found: 100" in report
        assert "Successfully scraped: 80" in report
        assert "Successfully classified: 1" in report

    def test_generate_report_with_truncation_warning(self):
        """Should include truncation warnings in report"""
        jobs = [
            {
                "titel": "Job 1",
                "categories": ["Python"],
                "_truncated": True,
                "_original_text_length": 5000,
                "_truncation_loss": 2000,
            },
            {
                "titel": "Job 2",
                "categories": ["Java"],
                "_truncated": True,
                "_original_text_length": 3000,
                "_truncation_loss": 1000,
            },
        ]

        report = generate_report(jobs, total_jobs=2)

        assert "TRUNCATION WARNING" in report
        assert "2/2 jobs were truncated" in report
        assert "UNRELIABLE" in report
        assert "Most severely truncated:" in report

    def test_generate_report_with_extraction_stats(self):
        """Should include extraction statistics in report"""
        jobs = [{"titel": "Dev", "categories": ["Python"]}]
        extraction_stats = {
            "total_jobs": 10,
            "by_source": {
                "arbeitsagentur": {"total": 6, "successful": 5, "avg_text_length": 2500},
                "external": {"total": 4, "successful": 3, "avg_text_length": 1800},
            },
            "by_extraction_method": {"css_selector": 7, "json_ld": 3},
            "by_warning": {"JS_REQUIRED": 2, "SHORT_CONTENT": 1},
            "problem_domains": [
                {
                    "domain": "example.com",
                    "total": 3,
                    "success_rate": 33.3,
                    "primary_warning": "JS_REQUIRED",
                }
            ],
        }

        report = generate_report(jobs, total_jobs=10, extraction_stats=extraction_stats)

        assert "SCRAPING QUALITY REPORT" in report
        assert "By Source" in report
        assert "arbeitsagentur" in report
        assert "Extraction Methods" in report
        assert "css_selector" in report
        assert "Warnings" in report
        assert "JS_REQUIRED" in report
        assert "Top Problem Domains" in report
        assert "example.com" in report

    def test_generate_report_includes_example_jobs(self):
        """Should include example jobs for top categories"""
        jobs = [
            {
                "titel": "Python Developer",
                "ort": "Berlin",
                "arbeitgeber": "Tech Corp",
                "categories": ["Python"],
                "url": "https://example.com/job1",
            },
            {
                "titel": "Senior Python Engineer",
                "ort": "Munich",
                "arbeitgeber": "StartupX",
                "categories": ["Python"],
                "url": "https://example.com/job2",
            },
            {
                "titel": "Java Developer",
                "ort": "Hamburg",
                "categories": ["Java"],
                "url": "https://example.com/job3",
            },
        ]

        report = generate_report(jobs, total_jobs=3)

        assert "Example Jobs by Category:" in report
        assert "Python Developer" in report
        assert "Berlin" in report
        assert "Tech Corp" in report
        assert "Apply: https://example.com/job1" in report

    def test_generate_report_limits_examples_per_category(self):
        """Should limit to 3 examples per category"""
        jobs = [
            {"titel": f"Python Dev {i}", "ort": "Berlin", "categories": ["Python"]}
            for i in range(10)
        ]

        report = generate_report(jobs, total_jobs=10)

        # Should only show first 3 examples
        assert "Python Dev 0" in report
        assert "Python Dev 1" in report
        assert "Python Dev 2" in report
        # Should not show beyond 3
        assert "Python Dev 3" not in report

    def test_generate_report_limits_to_top_3_categories(self):
        """Should show examples only for top 3 categories"""
        jobs = [
            {"titel": "Job A1", "categories": ["Cat_A"]},
            {"titel": "Job A2", "categories": ["Cat_A"]},
            {"titel": "Job A3", "categories": ["Cat_A"]},
            {"titel": "Job A4", "categories": ["Cat_A"]},
            {"titel": "Job A5", "categories": ["Cat_A"]},  # 5 jobs
            {"titel": "Job B1", "categories": ["Cat_B"]},
            {"titel": "Job B2", "categories": ["Cat_B"]},
            {"titel": "Job B3", "categories": ["Cat_B"]},
            {"titel": "Job B4", "categories": ["Cat_B"]},  # 4 jobs
            {"titel": "Job C1", "categories": ["Cat_C"]},
            {"titel": "Job C2", "categories": ["Cat_C"]},
            {"titel": "Job C3", "categories": ["Cat_C"]},  # 3 jobs
            {"titel": "Job D1", "categories": ["Cat_D"]},  # 1 job
        ]

        report = generate_report(jobs, total_jobs=13)

        # Should show examples for top 3 categories
        assert "Cat_A:" in report
        assert "Cat_B:" in report
        assert "Cat_C:" in report
        # Should NOT show examples for 4th category
        assert (
            "Cat_D:" not in report
            or report.index("Cat_D:") > report.index("Example Jobs by Category:") + 1000
        )

    def test_generate_report_empty_jobs_list(self):
        """Should handle empty jobs list gracefully"""
        report = generate_report([], total_jobs=0)

        assert "JOB MARKET ANALYSIS REPORT" in report
        assert "Total jobs found: 0" in report
        # Should not crash


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_analyze_categories_with_none_categories(self):
        """Should handle None in categories field gracefully"""
        jobs: list[dict] = [
            {"titel": "Job 1", "categories": None},
            {"titel": "Job 2", "categories": ["Python"]},
        ]

        # Should not crash - None should be treated as empty list
        result = analyze_categories(jobs)
        assert result.get("Python") == 1
        # Job 1 with None categories should not contribute to counts

    def test_calculate_percentages_with_negative_counts(self):
        """Should handle negative counts (edge case)"""
        category_counts = {"Python": -5}  # Shouldn't happen, but test it
        result = calculate_percentages(category_counts, 10)

        # Should still calculate
        assert result["Python"] == (-5, -50.0)

    def test_generate_report_with_missing_job_fields(self):
        """Should handle jobs with missing fields"""
        jobs = [
            {
                "categories": ["Python"]
                # Missing: titel, ort, arbeitgeber, url
            }
        ]

        report = generate_report(jobs, total_jobs=1)

        # Should not crash and should handle N/A gracefully
        assert "N/A" in report

    def test_generate_report_calculates_coverage_correctly(self):
        """Should calculate coverage percentage correctly"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
        ]

        report = generate_report(jobs, total_jobs=10)

        assert "Coverage: 10.0%" in report

    def test_print_statistics_with_zero_jobs(self):
        """Should handle zero jobs without crashing"""
        # Should complete without division by zero error
        print_statistics([], total_jobs=0, successful_fetches=0)
        # If we get here, the test passed (no exception raised)

    def test_dashboard_calculates_rates_with_zero_totals(self):
        """Should handle zero totals in rate calculations"""
        # Should not crash with division by zero (dashboard handles this correctly)
        print_statistics_dashboard(
            classified_jobs=[],
            total_jobs=0,
            successful_fetches=0,
            truncation_count=0,
            error_count=0,
        )

    def test_generate_report_with_very_long_job_titles(self):
        """Should handle very long job titles"""
        jobs = [
            {
                "titel": "A" * 200,  # Very long title
                "ort": "Berlin",
                "categories": ["Python"],
                "_truncated": True,
                "_original_text_length": 5000,
                "_truncation_loss": 2000,
            }
        ]

        report = generate_report(jobs, total_jobs=1)

        # Should truncate title in display ([:40])
        assert "AAAA" in report
        assert len(report) < 10000  # Should not be excessively long

    def test_generate_report_sorts_categories_by_count(self):
        """Should sort categories by count (descending)"""
        jobs = [
            {"titel": "Job 1", "categories": ["Python"]},
            {"titel": "Job 2", "categories": ["Python"]},
            {"titel": "Job 3", "categories": ["Python"]},
            {"titel": "Job 4", "categories": ["Java"]},
            {"titel": "Job 5", "categories": ["Java"]},
            {"titel": "Job 6", "categories": ["C#"]},
        ]

        report = generate_report(jobs, total_jobs=6)

        # Python should appear before Java, Java before C#
        python_pos = report.index("Python")
        java_pos = report.index("Java")
        csharp_pos = report.index("C#")

        assert python_pos < java_pos < csharp_pos
