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
                    <span>🔖 {refnr}</span>
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
        <div class="metadata">
{metadata}
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
            <div class="job-card" data-url="{url}" data-refnr="{refnr}">
                <div class="job-title">
                    <a href="{url}" target="_blank">{title}</a>
                </div>
                <div class="job-meta">
                    <div class="job-meta-item">
                        <span class="job-meta-label">🔖</span>
                        <span>{refnr}</span>
                    </div>
                    <div class="job-meta-item">
                        <span class="job-meta-label">📍</span>
                        <span>{location}</span>
                    </div>
                    <div class="job-meta-item">
                        <span class="job-meta-label">🏢</span>
                        <span>{employer}</span>
                    </div>
                    <div class="job-meta-item">
                        <span class="job-meta-label">🧠</span>
                        <span><a href="debug/thinking_index.html#{refnr}" class="thinking-link">View Thinking</a></span>
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

# Thinking Log Export Templates

THINKING_LOG_DOCUMENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thinking Log{batch_label_title}</title>
    <style>
{css}
    </style>
</head>
<body>
    <div class="container">
        <h1>LLM Thinking Process{batch_label_header}</h1>

{jobs_header}

        <div class="thinking-content">
{thinking_html}
        </div>
    </div>

    <script>
{javascript}
    </script>
</body>
</html>"""

THINKING_LOG_JOBS_HEADER = """        <div class="jobs-header">
            <h2>Jobs in this batch:</h2>
            <ul class="jobs-list">
{jobs_list}
            </ul>
        </div>
        <hr class="section-divider">
"""

THINKING_LOG_JOB_ITEM = """                <li><a href="{url}" target="_blank" class="refnr-link">[{refnr}]</a> {titel} | {ort} | {arbeitgeber}</li>"""

THINKING_LOG_SCRIPT = """
        // Smooth scroll to refnr when URL has hash
        window.addEventListener('load', function() {
            if (window.location.hash) {
                const target = document.querySelector(window.location.hash);
                if (target) {
                    setTimeout(() => {
                        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }, 100);
                }
            }
        });

        // Highlight clicked refnr links
        document.querySelectorAll('.refnr-link').forEach(link => {
            link.addEventListener('click', function(e) {
                // Only prevent default if it's an internal link (has id)
                const id = this.getAttribute('id');
                if (id) {
                    e.preventDefault();
                    window.location.hash = '#' + id;
                    this.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        });
"""

# Thinking Index Export Templates

THINKING_INDEX_DOCUMENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thinking Logs Index</title>
    <style>
{css}
    </style>
</head>
<body>
    <div class="container">
        <h1>LLM Thinking Logs Index</h1>

        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search by Ref ID, Title, Location, Employer, or Category..." />
            <div class="search-stats">
                <span id="visibleCount">{total_jobs}</span>
                <span> / </span>
                <span id="totalCount">{total_jobs}</span>
                <span> jobs</span>
            </div>
        </div>

        <div id="batchesContainer">
{batch_sections}
        </div>

        <div id="noResults" class="no-results" style="display: none;">
            <p>No jobs match your search.</p>
        </div>
    </div>

    <script>
{javascript}
    </script>
</body>
</html>"""

THINKING_INDEX_BATCH_SECTION = """            <div class="batch-section">
                <h2 class="batch-header">
                    {batch_label}
                    <span class="job-count">({job_count} jobs)</span>
                </h2>
                <table class="jobs-table">
                    <thead>
                        <tr>
                            <th>Ref ID</th>
                            <th>Titel</th>
                            <th>Ort</th>
                            <th>Arbeitgeber</th>
                            <th>Category</th>
                            <th>Thinking</th>
                        </tr>
                    </thead>
                    <tbody>
{job_rows}
                    </tbody>
                </table>
            </div>
"""

THINKING_INDEX_JOB_ROW = """                        <tr data-refnr="{refnr}" data-titel="{titel}"
                            data-ort="{ort}" data-arbeitgeber="{arbeitgeber}"
                            data-category="{category}">
                            <td>
                                <a href="{arbeitsagentur_url}" target="_blank" class="refnr-link">
                                    {refnr}
                                </a>
                            </td>
                            <td>{titel}</td>
                            <td>{ort}</td>
                            <td>{arbeitgeber}</td>
                            <td>{category_badge}</td>
                            <td>
                                <a href="{thinking_link}" class="view-link">
                                    View Thinking →
                                </a>
                            </td>
                        </tr>
"""

THINKING_INDEX_CATEGORY_BADGE = (
    """<span class="category-badge {category_class}">{category}</span>"""
)

THINKING_INDEX_SCRIPT = """
        const searchInput = document.getElementById('searchInput');
        const batchesContainer = document.getElementById('batchesContainer');
        const noResults = document.getElementById('noResults');
        const visibleCount = document.getElementById('visibleCount');
        const totalCount = document.getElementById('totalCount');

        // Get all job rows and batch sections
        const allRows = Array.from(document.querySelectorAll('.jobs-table tbody tr'));
        const allBatches = Array.from(document.querySelectorAll('.batch-section'));

        // Search function
        function performSearch() {
            const query = searchInput.value.toLowerCase().trim();

            if (query === '') {
                // Show all rows and batches
                allRows.forEach(row => row.classList.remove('hidden'));
                allBatches.forEach(batch => batch.classList.remove('hidden'));
                visibleCount.textContent = allRows.length;
                noResults.style.display = 'none';
                batchesContainer.style.display = 'block';
                return;
            }

            let matchCount = 0;

            // Search through each row
            allRows.forEach(row => {
                const refnr = row.dataset.refnr.toLowerCase();
                const titel = row.dataset.titel.toLowerCase();
                const ort = row.dataset.ort.toLowerCase();
                const arbeitgeber = row.dataset.arbeitgeber.toLowerCase();
                const category = row.dataset.category.toLowerCase();

                const matches =
                    refnr.includes(query) ||
                    titel.includes(query) ||
                    ort.includes(query) ||
                    arbeitgeber.includes(query) ||
                    category.includes(query);

                if (matches) {
                    row.classList.remove('hidden');
                    matchCount++;
                } else {
                    row.classList.add('hidden');
                }
            });

            // Hide batches that have no visible rows
            allBatches.forEach(batch => {
                const visibleRows = batch.querySelectorAll('tbody tr:not(.hidden)');
                if (visibleRows.length === 0) {
                    batch.classList.add('hidden');
                } else {
                    batch.classList.remove('hidden');
                }
            });

            // Update stats
            visibleCount.textContent = matchCount;

            // Show/hide no results message
            if (matchCount === 0) {
                noResults.style.display = 'block';
                batchesContainer.style.display = 'none';
            } else {
                noResults.style.display = 'none';
                batchesContainer.style.display = 'block';
            }
        }

        // Attach search event listener
        searchInput.addEventListener('input', performSearch);

        // Auto-search if URL hash contains refnr
        window.addEventListener('load', function() {
            const hash = window.location.hash.substring(1); // Remove the #
            if (hash) {
                searchInput.value = hash;
                performSearch();
            }
        });

        // Focus search box on page load
        searchInput.focus();
"""
