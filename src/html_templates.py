"""
HTML templates for exports
Separated from logic to improve maintainability
"""

# Failed Jobs Export Templates

FAILED_JOBS_DOCUMENT = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Failed Jobs</title>
    <style>
{css}
    </style>
</head>
<body>
    <div class="header">
        <h1>Failed Jobs</h1>
        <div class="stats">Total: {total_count} failed job(s)</div>
    </div>

{sections}

    <script>
{javascript}
    </script>
</body>
</html>
"""

FAILED_JOBS_SECTION = """
    <div class="error-section" data-error="{error_class}">
        <div class="error-header">
            <span>{error_type} ({count})</span>
            <div class="error-controls">
                <button class="open-all-btn" onclick="openAllInSection('{error_class}')">Open All</button>
                <span class="toggle-icon">▼</span>
            </div>
        </div>
        <div class="jobs-container">
{jobs}
        </div>
    </div>
"""

FAILED_JOBS_CARD = """
            <div class="job-card" data-url="{url}">
                <div class="job-title">
                    <a href="{url}" target="_blank">{title}</a>
                </div>
                <div class="job-meta">
                    <span>📍 {location}</span>
                    <span>🏢 {employer}</span>
                </div>
            </div>
"""

FAILED_JOBS_SCRIPT = """
        // Toggle collapse/expand
        document.querySelectorAll('.error-header').forEach(header => {
            header.addEventListener('click', function(e) {
                if (e.target.classList.contains('open-all-btn')) return;
                const section = this.parentElement;
                section.classList.toggle('collapsed');
            });
        });

        // Open all jobs in a section
        function openAllInSection(errorClass) {
            const section = document.querySelector(`[data-error="${errorClass}"]`);
            const urls = Array.from(section.querySelectorAll('.job-card'))
                .map(card => card.dataset.url)
                .filter(url => url);

            if (urls.length === 0) return;

            if (urls.length > 20) {
                if (!confirm(`This will open ${urls.length} tabs. Continue?`)) return;
            }

            urls.forEach((url, index) => {
                setTimeout(() => {
                    window.open(url, '_blank');
                }, index * 100);
            });
        }
"""

# Classified Jobs Export Templates

CLASSIFIED_JOBS_DOCUMENT = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Search Results</title>
    <style>
{css}
    </style>
</head>
<body>
{header}
{controls}
    <div id="jobsContainer">
{sections}
    </div>

    <script>
{javascript}
    </script>
</body>
</html>
"""

CLASSIFIED_JOBS_HEADER = """    <div class="header">
        <h1>🔍 Job Search Results</h1>
        <div class="stats">
{stats}
        </div>
    </div>

"""

CLASSIFIED_JOBS_STAT = """            <div class="stat {css_class}">{category}: {count}</div>
"""

CLASSIFIED_JOBS_CONTROLS = """    <div class="controls">
        <input type="text" class="search-box" id="searchBox" placeholder="Search by title, location, or employer...">
        <div class="filter-buttons">
            <button class="filter-btn active" data-category="all">Show All ({total_jobs})</button>
{filter_buttons}
        </div>
    </div>

"""

CLASSIFIED_JOBS_FILTER_BUTTON = """            <button class="filter-btn" data-category="{css_class}">{category} ({count})</button>
"""

CLASSIFIED_JOBS_SECTION = """
    <div class="category-section {css_class}-section" data-category="{css_class}">
        <div class="category-header {css_class}">
            <span>{category} ({count})</span>
            <div class="category-controls">
                <button class="open-all-btn" onclick="openAllInCategory('{css_class}')">Open All</button>
                <span class="toggle-icon">▼</span>
            </div>
        </div>
        <div class="jobs-container">
{jobs}
        </div>
    </div>
"""

CLASSIFIED_JOBS_CARD = """
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

CLASSIFIED_JOBS_SCRIPT = """
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
"""
