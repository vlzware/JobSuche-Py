"""
Export modules for different output formats (HTML, CSV, etc.)
"""

from html import escape
from pathlib import Path

from .html_styles import CLASSIFIED_JOBS_STYLES, FAILED_JOBS_STYLES
from .html_templates import (
    CLASSIFIED_JOBS_CARD,
    CLASSIFIED_JOBS_CONTROLS,
    CLASSIFIED_JOBS_DOCUMENT,
    CLASSIFIED_JOBS_FILTER_BUTTON,
    CLASSIFIED_JOBS_HEADER,
    CLASSIFIED_JOBS_SCRIPT,
    CLASSIFIED_JOBS_SECTION,
    CLASSIFIED_JOBS_STAT,
    FAILED_JOBS_CARD,
    FAILED_JOBS_DOCUMENT,
    FAILED_JOBS_SCRIPT,
    FAILED_JOBS_SECTION,
)


class HTMLExporter:
    """Exports job listings to interactive HTML format"""

    def export_failed_jobs(self, failed_jobs: list[dict], output_path: Path) -> str:
        """
        Export failed jobs to a simple HTML file grouped by error type

        Args:
            failed_jobs: List of jobs that failed to scrape
            output_path: Path where HTML file should be saved

        Returns:
            Path to the saved HTML file
        """
        # Group jobs by error type and sort groups by count (descending)
        error_groups: dict[str, list[dict]] = {}
        for job in failed_jobs:
            error_type = job.get("error_type", "UNKNOWN")
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(job)

        # Sort groups by count (most common first)
        sorted_groups = sorted(error_groups.items(), key=lambda x: len(x[1]), reverse=True)

        html_content = self._generate_failed_jobs_html(sorted_groups, len(failed_jobs))

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(output_path)

    def _generate_failed_jobs_html(
        self, error_groups: list[tuple[str, list[dict]]], total_count: int
    ) -> str:
        """Generate HTML for failed jobs"""
        # Build sections for each error type
        sections = []
        for error_type, jobs in error_groups:
            error_class = error_type.lower().replace("_", "").replace(" ", "")

            # Build job cards for this section
            job_cards = []
            for job in jobs:
                job_cards.append(
                    FAILED_JOBS_CARD.format(
                        url=escape(job.get("url", "")),
                        title=escape(job.get("titel", "N/A")),
                        location=escape(job.get("ort", "N/A")),
                        employer=escape(job.get("arbeitgeber", "N/A")),
                    )
                )

            # Build section
            sections.append(
                FAILED_JOBS_SECTION.format(
                    error_class=error_class,
                    error_type=error_type,
                    count=len(jobs),
                    jobs="".join(job_cards),
                )
            )

        # Assemble final document
        return FAILED_JOBS_DOCUMENT.format(
            css=FAILED_JOBS_STYLES,
            total_count=total_count,
            sections="".join(sections),
            javascript=FAILED_JOBS_SCRIPT,
        )

    def export(self, jobs: list[dict], output_path: Path) -> str:
        """
        Export jobs to an interactive HTML file

        Args:
            jobs: List of classified jobs
            output_path: Path where HTML file should be saved

        Returns:
            Path to the saved HTML file
        """
        # Group jobs by category
        category_groups: dict[str, list[dict]] = {
            "Excellent Match": [],
            "Good Match": [],
            "Poor Match": [],
        }
        for job in jobs:
            categories = job.get("categories", [])
            if "Excellent Match" in categories:
                category_groups["Excellent Match"].append(job)
            elif "Good Match" in categories:
                category_groups["Good Match"].append(job)
            elif "Poor Match" in categories:
                category_groups["Poor Match"].append(job)

        html_content = self._generate_html(jobs, category_groups)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return str(output_path)

    def _generate_html(self, jobs: list[dict], category_groups: dict) -> str:
        """Generate the full HTML content"""
        # Build stats
        stats = []
        for category, cat_jobs in category_groups.items():
            if cat_jobs:
                css_class = category.lower().replace(" ", "")
                stats.append(
                    CLASSIFIED_JOBS_STAT.format(
                        css_class=css_class, category=category, count=len(cat_jobs)
                    )
                )

        # Build filter buttons
        filter_buttons = []
        for category, cat_jobs in category_groups.items():
            if cat_jobs:
                css_class = category.lower().replace(" ", "")
                filter_buttons.append(
                    CLASSIFIED_JOBS_FILTER_BUTTON.format(
                        css_class=css_class, category=category, count=len(cat_jobs)
                    )
                )

        # Build sections
        sections = []
        for category, cat_jobs in category_groups.items():
            if not cat_jobs:
                continue

            css_class = category.lower().replace(" ", "")

            # Build job cards for this section
            job_cards = []
            for job in cat_jobs:
                job_cards.append(
                    CLASSIFIED_JOBS_CARD.format(
                        url=escape(job.get("url", "")),
                        title=escape(job.get("titel", "N/A")),
                        location=escape(job.get("ort", "N/A")),
                        employer=escape(job.get("arbeitgeber", "N/A")),
                    )
                )

            # Build section
            sections.append(
                CLASSIFIED_JOBS_SECTION.format(
                    css_class=css_class,
                    category=category,
                    count=len(cat_jobs),
                    jobs="".join(job_cards),
                )
            )

        # Assemble final document
        return CLASSIFIED_JOBS_DOCUMENT.format(
            css=CLASSIFIED_JOBS_STYLES,
            header=CLASSIFIED_JOBS_HEADER.format(stats="".join(stats)),
            controls=CLASSIFIED_JOBS_CONTROLS.format(
                total_jobs=len(jobs), filter_buttons="".join(filter_buttons)
            ),
            sections="".join(sections),
            javascript=CLASSIFIED_JOBS_SCRIPT,
        )
