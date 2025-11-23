"""
CSS styles for HTML exports
Separated from logic to improve maintainability
"""

# Common base styles shared by all HTML exports
COMMON_BASE_STYLES = """
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
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            border-bottom: 3px solid;
            padding-bottom: 10px;
            margin: 0 0 15px 0;
        }
"""

# Common styles for job cards (used in both exports)
COMMON_JOB_CARD_STYLES = """
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
        .thinking-link {
            color: #8e44ad;
            text-decoration: none;
            font-weight: 500;
        }
        .thinking-link:hover {
            text-decoration: underline;
            color: #9b59b6;
        }
"""

# Common collapsible section styles
COMMON_SECTION_STYLES = """
        .toggle-icon {
            font-size: 20px;
            transition: transform 0.3s;
        }
        .collapsed .toggle-icon { transform: rotate(-90deg); }
        .jobs-container {
            max-height: 600px;
            overflow-y: auto;
            transition: max-height 0.3s;
        }
        .collapsed .jobs-container {
            max-height: 0;
            overflow: hidden;
        }
"""

# Styles specific to failed jobs export
FAILED_JOBS_STYLES = (
    COMMON_BASE_STYLES
    + """
        h1 {
            color: #721c24;
            border-bottom-color: #f8d7da;
        }
        .stats {
            color: #666;
            font-size: 14px;
        }
        .error-section {
            background: white;
            margin-bottom: 20px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .error-header {
            padding: 15px 20px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #f8d7da;
            color: #721c24;
            transition: background 0.2s;
        }
        .error-header:hover { background: #f5c6cb; }
        .error-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .open-all-btn {
            padding: 6px 12px;
            background: white;
            border: 2px solid #721c24;
            border-radius: 5px;
            cursor: pointer;
            font-size: 13px;
            font-weight: bold;
            color: #721c24;
            transition: all 0.2s;
        }
        .open-all-btn:hover {
            background: #721c24;
            color: white;
        }
"""
    + COMMON_SECTION_STYLES
    + """
        .error-section .jobs-container {
            max-height: 500px;
        }
        .job-card {
            border-bottom: 1px solid #e9ecef;
            padding: 12px 20px;
            transition: background 0.2s;
        }
        .job-card:hover { background: #f8f9fa; }
        .job-card:last-child { border-bottom: none; }
        .job-title {
            font-size: 16px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 6px;
        }
        .job-title a {
            color: #3498db;
            text-decoration: none;
        }
        .job-title a:hover { text-decoration: underline; }
        .job-meta {
            display: flex;
            gap: 15px;
            color: #666;
            font-size: 13px;
            flex-wrap: wrap;
        }
"""
)

# Styles specific to classified jobs export
CLASSIFIED_JOBS_STYLES = (
    COMMON_BASE_STYLES
    + """
        h1 {
            color: #2c3e50;
            border-bottom-color: #3498db;
        }
        .stats {
            display: flex;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .metadata {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e9ecef;
            color: #666;
            font-size: 13px;
            line-height: 1.8;
        }
        .metadata-item {
            margin-right: 20px;
            display: inline-block;
        }
        .metadata-label {
            font-weight: 600;
            color: #555;
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
"""
    + COMMON_SECTION_STYLES
    + COMMON_JOB_CARD_STYLES
)

# Styles for thinking log export
THINKING_LOG_STYLES = """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        h1 {
            color: #2c3e50;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #3498db;
        }

        h2 {
            color: #34495e;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 1.4em;
        }

        h3 {
            color: #555;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 1.2em;
        }

        .jobs-header {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 25px;
        }

        .jobs-header h2 {
            margin-top: 0;
            color: #2c3e50;
            font-size: 1.3em;
        }

        .jobs-list {
            list-style: none;
            padding: 0;
        }

        .jobs-list li {
            padding: 8px 0;
            border-bottom: 1px solid #e9ecef;
        }

        .jobs-list li:last-child {
            border-bottom: none;
        }

        .section-divider {
            border: none;
            border-top: 2px solid #dee2e6;
            margin: 30px 0;
        }

        .thinking-content {
            margin-top: 20px;
        }

        .thinking-content p {
            margin-bottom: 12px;
            line-height: 1.7;
        }

        .thinking-content hr {
            margin: 20px 0;
            border: none;
            border-top: 1px solid #dee2e6;
        }

        pre {
            background-color: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 16px;
            overflow-x: auto;
            margin: 15px 0;
        }

        code {
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.9em;
        }

        strong {
            font-weight: 600;
            color: #2c3e50;
        }

        .refnr-link {
            color: #3498db;
            text-decoration: none;
            font-weight: 600;
            padding: 2px 4px;
            border-radius: 3px;
            transition: all 0.2s ease;
            display: inline-block;
        }

        .refnr-link:hover {
            background-color: #3498db;
            color: white;
            text-decoration: none;
        }

        .refnr-link:target {
            background-color: #f39c12;
            color: white;
            animation: highlight-pulse 2s ease-in-out;
        }

        @keyframes highlight-pulse {
            0%, 100% { background-color: #f39c12; }
            50% { background-color: #e67e22; }
        }

        .refnr-unknown {
            color: #95a5a6;
            font-weight: 600;
        }

        /* CSS-based tooltips */
        [data-tooltip] {
            position: relative;
            cursor: help;
        }

        [data-tooltip]::before {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%) translateY(-8px);
            padding: 8px 12px;
            background-color: #2c3e50;
            color: white;
            font-size: 12px;
            font-weight: normal;
            white-space: nowrap;
            border-radius: 4px;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s, transform 0.3s;
            z-index: 1000;
        }

        [data-tooltip]::after {
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%) translateY(-2px);
            border: 5px solid transparent;
            border-top-color: #2c3e50;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s, transform 0.3s;
            z-index: 1000;
        }

        [data-tooltip]:hover::before,
        [data-tooltip]:hover::after {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }

        html {
            scroll-behavior: smooth;
        }

        [id] {
            scroll-margin-top: 20px;
        }
"""

# Styles for thinking index export
THINKING_INDEX_STYLES = """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        h1 {
            color: #2c3e50;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 3px solid #3498db;
        }

        .search-box {
            margin-bottom: 30px;
            display: flex;
            gap: 15px;
            align-items: center;
        }

        #searchInput {
            flex: 1;
            padding: 12px 20px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 6px;
            transition: border-color 0.3s;
        }

        #searchInput:focus {
            outline: none;
            border-color: #3498db;
        }

        .search-stats {
            color: #7f8c8d;
            font-size: 14px;
            white-space: nowrap;
        }

        .batch-section {
            margin-bottom: 40px;
        }

        .batch-header {
            color: #34495e;
            font-size: 1.3em;
            margin-bottom: 15px;
            padding: 10px 15px;
            background-color: #ecf0f1;
            border-left: 4px solid #3498db;
            border-radius: 4px;
        }

        .job-count {
            color: #7f8c8d;
            font-size: 0.9em;
            font-weight: normal;
        }

        .jobs-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }

        .jobs-table thead {
            background-color: #34495e;
            color: white;
        }

        .jobs-table th {
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }

        .jobs-table tbody tr {
            border-bottom: 1px solid #ecf0f1;
            transition: background-color 0.2s;
        }

        .jobs-table tbody tr:hover {
            background-color: #f8f9fa;
        }

        .jobs-table tbody tr.hidden {
            display: none;
        }

        .jobs-table td {
            padding: 12px;
        }

        .refnr-link {
            color: #3498db;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        }

        .refnr-link:hover {
            color: #2980b9;
            text-decoration: underline;
        }

        .view-link {
            color: #27ae60;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s;
        }

        .view-link:hover {
            color: #229954;
            text-decoration: underline;
        }

        .category-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .category-badge.excellentmatch {
            background-color: #d4edda;
            color: #155724;
        }

        .category-badge.goodmatch {
            background-color: #d1ecf1;
            color: #0c5460;
        }

        .category-badge.poormatch {
            background-color: #f8d7da;
            color: #721c24;
        }

        .no-results {
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
        }

        .batch-section.hidden {
            display: none;
        }
"""
