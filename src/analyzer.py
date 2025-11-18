"""
Statistical analysis of classified job listings
"""

from collections import Counter

from .logging_config import get_module_logger
from .scraper import ExtractionStats

logger = get_module_logger("analyzer")


def analyze_categories(classified_jobs: list[dict]) -> dict[str, int]:
    """
    Count how many jobs fall into each category

    Args:
        classified_jobs: List of jobs with 'categories' field

    Returns:
        Dictionary mapping category name to count
    """
    category_counts: Counter[str] = Counter()

    for job in classified_jobs:
        categories = job.get("categories", [])
        # Handle None categories field explicitly
        if categories is None:
            categories = []
        for category in categories:
            category_counts[category] += 1

    return dict(category_counts)


def calculate_percentages(
    category_counts: dict[str, int], total_jobs: int
) -> dict[str, tuple[int, float]]:
    """
    Calculate percentages for each category

    Args:
        category_counts: Dictionary of category counts
        total_jobs: Total number of jobs analyzed

    Returns:
        Dictionary mapping category to (count, percentage)
    """
    results = {}

    for category, count in category_counts.items():
        percentage = (count / total_jobs * 100) if total_jobs > 0 else 0
        results[category] = (count, percentage)

    return results


def print_statistics(
    classified_jobs: list[dict], total_jobs: int, successful_fetches: int | None = None
):
    """
    Print formatted statistics to console (legacy function - use print_statistics_dashboard instead)

    Args:
        classified_jobs: List of classified jobs
        total_jobs: Total number of jobs from initial search
        successful_fetches: Number of successfully fetched job descriptions
    """
    if successful_fetches is None:
        successful_fetches = len(classified_jobs)

    category_counts = analyze_categories(classified_jobs)
    percentages = calculate_percentages(category_counts, total_jobs)

    # Sort by count (descending)
    sorted_categories = sorted(percentages.items(), key=lambda x: x[1][0], reverse=True)

    logger.info("=" * 60)
    logger.info("JOB MARKET ANALYSIS RESULTS")
    logger.info("=" * 60)
    logger.info(f"Total jobs found: {total_jobs}")
    logger.info(f"Successfully analyzed: {successful_fetches}")
    # Avoid division by zero when total_jobs is 0
    coverage_pct = (successful_fetches / total_jobs * 100) if total_jobs > 0 else 0
    logger.info(f"Analysis coverage: {coverage_pct:.1f}%")
    logger.info("-" * 60)
    logger.info(f"{'Category':<30} {'Jobs':>8} {'Percentage':>10}")
    logger.info("-" * 60)

    for category, (count, percentage) in sorted_categories:
        logger.info(f"{category:<30} {count:>8} {percentage:>9.1f}%")

    logger.info("=" * 60)


def print_statistics_dashboard(
    classified_jobs: list[dict],
    total_jobs: int,
    successful_fetches: int,
    error_count: int = 0,
    total_classified: int | None = None,
) -> None:
    """
    Print prominent statistics dashboard

    Makes success/failure impossible to miss

    Args:
        classified_jobs: List of classified jobs (may be filtered to only matches)
        total_jobs: Total number of jobs from initial search
        successful_fetches: Number of successfully fetched job descriptions
        error_count: Number of scraping errors
        total_classified: Total number of jobs that went through LLM classification
                         (if different from len(classified_jobs), filtering was applied)
    """
    # Calculate stats
    returned_count = len(classified_jobs)

    # If total_classified not provided, assume all returned jobs were classified (no filtering)
    if total_classified is None:
        total_classified = returned_count

    fetch_rate = (successful_fetches / total_jobs * 100) if total_jobs > 0 else 0
    classification_rate = (total_classified / total_jobs * 100) if total_jobs > 0 else 0

    # Detect if filtering was applied
    is_filtered = total_classified > returned_count

    # Build dashboard (simplified formatting)
    logger.info("")
    logger.info("=" * 70)
    logger.info("JOB ANALYSIS SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total jobs found:          {total_jobs:>5}")
    logger.info(f"✓ Successfully scraped:    {successful_fetches:>5} ({fetch_rate:>5.1f}%)")

    if is_filtered:
        # Filtered workflow: show both total classified and matches
        logger.info(
            f"✓ Successfully classified: {total_classified:>5} ({classification_rate:>5.1f}%)"
        )
        match_rate = (returned_count / total_classified * 100) if total_classified > 0 else 0
        logger.info(f"✓ Good/Excellent matches:  {returned_count:>5} ({match_rate:>5.1f}%)")
    else:
        # Regular workflow or no filtering: show just classified
        logger.info(
            f"✓ Successfully classified: {returned_count:>5} ({classification_rate:>5.1f}%)"
        )

    if error_count > 0:
        error_rate = (error_count / total_jobs * 100) if total_jobs > 0 else 0
        logger.info(f"✗ Scraping failures:       {error_count:>5} ({error_rate:>5.1f}%)")

    logger.info("=" * 70)
    logger.info("")

    # Category breakdown (simplified - no bars)
    category_counts = analyze_categories(classified_jobs)

    logger.info("Category Distribution:")
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / returned_count * 100) if returned_count > 0 else 0
        logger.info(f"  {category:.<40} {count:>4} ({percentage:>5.1f}%)")

    logger.info("")


def generate_report(
    classified_jobs: list[dict],
    total_jobs: int,
    search_params: dict | None = None,
    gathering_stats: dict | None = None,
    extraction_stats: ExtractionStats | dict | None = None,
    total_classified: int | None = None,
) -> str:
    """
    Generate a formatted text report

    Args:
        classified_jobs: List of classified jobs (may be filtered to only matches)
        total_jobs: Total number of jobs
        search_params: Search parameters used (was, wo, umkreis)
        gathering_stats: Statistics from job gathering (total_found, successfully_extracted, etc.)
        extraction_stats: Detailed extraction statistics from scraper
        total_classified: Total number of jobs that went through LLM classification
                         (if different from len(classified_jobs), filtering was applied)

    Returns:
        Formatted report as string
    """
    category_counts = analyze_categories(classified_jobs)
    percentages = calculate_percentages(category_counts, total_jobs)

    sorted_categories = sorted(percentages.items(), key=lambda x: x[1][0], reverse=True)

    returned_count = len(classified_jobs)

    # If total_classified not provided, assume all returned jobs were classified (no filtering)
    if total_classified is None:
        total_classified = returned_count

    # Detect if filtering was applied
    is_filtered = total_classified > returned_count

    lines = []
    lines.append("=" * 60)
    lines.append("JOB MARKET ANALYSIS REPORT")
    lines.append("=" * 60)

    if search_params:
        lines.append("\nSearch Parameters:")
        lines.append(f"  Position: {search_params.get('was', 'N/A')}")
        lines.append(f"  Location: {search_params.get('wo', 'N/A')}")
        lines.append(f"  Radius: {search_params.get('umkreis', 'N/A')} km")

    # Use gathering_stats if available, otherwise fall back to total_jobs
    if gathering_stats:
        lines.append(f"\nTotal jobs found: {gathering_stats['total_found']}")
        lines.append(f"Successfully scraped: {gathering_stats['successfully_extracted']}")

        if is_filtered:
            # Filtered workflow: show both total classified and matches
            lines.append(f"Successfully classified: {total_classified}")
            lines.append(f"Good/Excellent matches: {returned_count}")
            classification_coverage = (
                (total_classified / gathering_stats["total_found"] * 100)
                if gathering_stats["total_found"] > 0
                else 0
            )
            match_rate = (returned_count / total_classified * 100) if total_classified > 0 else 0
            lines.append(f"Classification coverage: {classification_coverage:.1f}%")
            lines.append(f"Match rate: {match_rate:.1f}%")
        else:
            # Regular workflow: show just classified
            lines.append(f"Successfully classified: {returned_count}")
            coverage = (
                (returned_count / gathering_stats["total_found"] * 100)
                if gathering_stats["total_found"] > 0
                else 0
            )
            lines.append(f"Overall coverage: {coverage:.1f}%")
    else:
        lines.append(f"\nTotal jobs found: {total_jobs}")
        if is_filtered:
            lines.append(f"Successfully classified: {total_classified}")
            lines.append(f"Good/Excellent matches: {returned_count}")
            match_rate = (returned_count / total_classified * 100) if total_classified > 0 else 0
            lines.append(f"Match rate: {match_rate:.1f}%")
        else:
            lines.append(f"Successfully analyzed: {returned_count}")
            coverage = (returned_count / total_jobs * 100) if total_jobs > 0 else 0
            lines.append(f"Coverage: {coverage:.1f}%")

    # Add extraction statistics if available
    if extraction_stats:
        lines.append("\n" + "=" * 60)
        lines.append("SCRAPING QUALITY REPORT (DEBUG)")
        lines.append("=" * 60)

        # Overall summary
        lines.append(f"\nTotal jobs scraped: {extraction_stats['total_jobs']}")

        # By source
        if extraction_stats.get("by_source"):
            lines.append("\n--- By Source ---")
            for source, data in extraction_stats["by_source"].items():
                success_rate = (
                    (data["successful"] / data["total"] * 100) if data["total"] > 0 else 0
                )
                lines.append(
                    f"  {source}: {data['successful']}/{data['total']} successful ({success_rate:.1f}%)"
                )
                lines.append(f"    Avg text length: {data['avg_text_length']:,} chars")

        # Extraction methods
        if extraction_stats.get("by_extraction_method"):
            lines.append("\n--- Extraction Methods ---")
            total_extracted = sum(extraction_stats["by_extraction_method"].values())
            for method, count in sorted(
                extraction_stats["by_extraction_method"].items(), key=lambda x: x[1], reverse=True
            ):
                percentage = (count / total_extracted * 100) if total_extracted > 0 else 0
                lines.append(f"  {method}: {count} ({percentage:.1f}%)")

        # Warnings
        if extraction_stats.get("by_warning"):
            lines.append("\n--- Warnings ---")
            for warning, count in sorted(
                extraction_stats["by_warning"].items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {warning}: {count} jobs")

        # Problem domains
        if extraction_stats.get("problem_domains"):
            lines.append("\n--- Top Problem Domains ---")
            for domain_info in extraction_stats["problem_domains"][:5]:
                lines.append(
                    f"  {domain_info['domain']}: {domain_info['success_rate']}% success ({domain_info['total']} jobs)"
                )
                if domain_info.get("primary_warning"):
                    lines.append(f"    Primary issue: {domain_info['primary_warning']}")

    lines.append("\n" + "-" * 60)
    lines.append(f"{'Category':<30} {'Jobs':>8} {'Percentage':>10}")
    lines.append("-" * 60)

    for category, (count, percentage) in sorted_categories:
        lines.append(f"{category:<30} {count:>8} {percentage:>9.1f}%")

    lines.append("=" * 60)

    # Add example jobs for top categories
    lines.append("\nExample Jobs by Category:")
    lines.append("-" * 60)

    for category, _ in sorted_categories[:3]:  # Top 3 categories
        lines.append(f"\n{category}:")
        examples = [job for job in classified_jobs if category in job.get("categories", [])][
            :3
        ]  # First 3 examples

        for job in examples:
            lines.append(f"  - {job.get('titel', 'N/A')} ({job.get('ort', 'N/A')})")
            if job.get("arbeitgeber"):
                lines.append(f"    {job.get('arbeitgeber')}")
            if job.get("url"):
                lines.append(f"    Apply: {job.get('url')}")

    return "\n".join(lines)
