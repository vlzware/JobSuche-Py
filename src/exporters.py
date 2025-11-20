"""
Export modules for different output formats (HTML, CSV, etc.)
"""

from html import escape
from pathlib import Path


class HTMLExporter:
    """Exports job listings to interactive HTML format"""

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
        html = self._html_head()
        html += self._html_header(jobs, category_groups)
        html += self._html_controls(jobs, category_groups)
        html += self._html_jobs_sections(category_groups)
        html += self._html_scripts()
        html += "</body>\n</html>"
        return html

    def _html_head(self) -> str:
        """Generate HTML head with styles"""
        return """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Search Results</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin: 0;
        }
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .stat {
            padding: 10px 20px;
            border-radius: 5px;
            font-weight: bold;
        }
        .stat.excellentmatch { background: #d4edda; color: #155724; }
        .stat.goodmatch { background: #d1ecf1; color: #0c5460; }
        .stat.poormatch { background: #f8d7da; color: #721c24; }
        .controls {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .search-box {
            width: 100%;
            padding: 10px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .filter-buttons {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 8px 16px;
            border: 2px solid #ddd;
            background: white;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        .filter-btn:hover { background: #f0f0f0; }
        .filter-btn.active { background: #3498db; color: white; border-color: #3498db; }
        .category-section {
            background: white;
            margin-bottom: 20px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .category-header {
            padding: 15px 20px;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s;
        }
        .category-header:hover { background: #f8f9fa; }
        .category-header.excellentmatch { background: #d4edda; color: #155724; }
        .category-header.goodmatch { background: #d1ecf1; color: #0c5460; }
        .category-header.poormatch { background: #f8d7da; color: #721c24; }
        .category-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .open-all-btn {
            padding: 6px 12px;
            background: white;
            border: 2px solid currentColor;
            border-radius: 5px;
            cursor: pointer;
            font-size: 13px;
            font-weight: bold;
            transition: all 0.2s;
        }
        .open-all-btn:hover { opacity: 0.8; transform: scale(1.05); }
        .toggle-icon {
            font-size: 20px;
            transition: transform 0.3s;
        }
        .category-section.collapsed .toggle-icon { transform: rotate(-90deg); }
        .jobs-container {
            max-height: 600px;
            overflow-y: auto;
            transition: max-height 0.3s;
        }
        .category-section.collapsed .jobs-container {
            max-height: 0;
            overflow: hidden;
        }
        .job-card {
            border-bottom: 1px solid #e9ecef;
            padding: 15px 20px;
            transition: background 0.2s;
        }
        .job-card:hover { background: #f8f9fa; }
        .job-card:last-child { border-bottom: none; }
        .job-title {
            font-size: 18px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        .job-title a {
            color: #3498db;
            text-decoration: none;
        }
        .job-title a:hover {
            text-decoration: underline;
        }
        .job-meta {
            display: flex;
            gap: 20px;
            color: #666;
            font-size: 14px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }
        .job-meta-item {
            display: flex;
            gap: 5px;
        }
        .job-meta-label {
            font-weight: 600;
        }
    </style>
</head>
<body>
"""

    def _html_header(self, jobs: list[dict], category_groups: dict) -> str:
        """Generate header section with stats"""
        html = """    <div class="header">
        <h1>🔍 Job Search Results</h1>
        <div class="stats">
"""
        for category, cat_jobs in category_groups.items():
            if cat_jobs:
                css_class = category.lower().replace(" ", "")
                count = len(cat_jobs)
                html += f'            <div class="stat {css_class}">{category}: {count}</div>\n'

        html += """        </div>
    </div>

"""
        return html

    def _html_controls(self, jobs: list[dict], category_groups: dict) -> str:
        """Generate search and filter controls"""
        total_jobs = len(jobs)
        html = f"""    <div class="controls">
        <input type="text" class="search-box" id="searchBox" placeholder="Search by title, location, or employer...">
        <div class="filter-buttons">
            <button class="filter-btn active" data-category="all">Show All ({total_jobs})</button>
"""

        for category, cat_jobs in category_groups.items():
            if cat_jobs:
                css_class = category.lower().replace(" ", "")
                html += (
                    f'            <button class="filter-btn" data-category="{css_class}">'
                    f"{category} ({len(cat_jobs)})</button>\n"
                )

        html += """        </div>
    </div>

    <div id="jobsContainer">
"""
        return html

    def _html_jobs_sections(self, category_groups: dict) -> str:
        """Generate job listing sections"""
        html = ""
        for category, cat_jobs in category_groups.items():
            if not cat_jobs:
                continue

            css_class = category.lower().replace(" ", "")
            html += f"""
    <div class="category-section {css_class}-section" data-category="{css_class}">
        <div class="category-header {css_class}">
            <span>{category} ({len(cat_jobs)})</span>
            <div class="category-controls">
                <button class="open-all-btn" onclick="openAllInCategory('{css_class}')">Open All</button>
                <span class="toggle-icon">▼</span>
            </div>
        </div>
        <div class="jobs-container">
"""

            for job in cat_jobs:
                html += self._html_job_card(job)

            html += """        </div>
    </div>
"""

        html += "    </div>\n\n"
        return html

    def _html_job_card(self, job: dict) -> str:
        """Generate a single job card"""
        title = escape(job.get("titel", "N/A"))
        location = escape(job.get("ort", "N/A"))
        employer = escape(job.get("arbeitgeber", "N/A"))
        url = escape(job.get("url", ""))

        return f"""
            <div class="job-card" data-url="{url}">
                <div class="job-title">
                    <a href="{url}" target="_blank">{title}</a>
                </div>
                <div class="job-meta">
                    <div class="job-meta-item">
                        <span class="job-meta-label">📍</span>
                        <span>{location}</span>
                    </div>
                    <div class="job-meta-item">
                        <span class="job-meta-label">🏢</span>
                        <span>{employer}</span>
                    </div>
                </div>
            </div>
"""

    def _html_scripts(self) -> str:
        """Generate JavaScript for interactivity"""
        return """    <script>
        // Search functionality
        document.getElementById('searchBox').addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const jobCards = document.querySelectorAll('.job-card');

            jobCards.forEach(card => {
                const text = card.textContent.toLowerCase();
                card.style.display = text.includes(searchTerm) ? 'block' : 'none';
            });
        });

        // Filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                // Update active state
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                // Show/hide sections
                const category = this.dataset.category;
                const sections = document.querySelectorAll('.category-section');

                sections.forEach(section => {
                    if (category === 'all' || section.dataset.category === category) {
                        section.style.display = 'block';
                    } else {
                        section.style.display = 'none';
                    }
                });
            });
        });

        // Toggle collapse/expand
        document.querySelectorAll('.category-header').forEach(header => {
            header.addEventListener('click', function(e) {
                // Don't toggle if clicking the "Open All" button
                if (e.target.classList.contains('open-all-btn')) return;

                const section = this.parentElement;
                section.classList.toggle('collapsed');
            });
        });

        // Open all jobs in category
        function openAllInCategory(category) {
            const section = document.querySelector(`.${category}-section`);
            const urls = Array.from(section.querySelectorAll('.job-card'))
                .map(card => card.dataset.url)
                .filter(url => url);

            if (urls.length === 0) return;

            // Warn if opening many tabs
            if (urls.length > 20) {
                if (!confirm(`This will open ${urls.length} tabs. Continue?`)) return;
            }

            // Open tabs with small delay to avoid browser blocking
            urls.forEach((url, index) => {
                setTimeout(() => {
                    window.open(url, '_blank');
                }, index * 100);
            });
        }
    </script>
"""
