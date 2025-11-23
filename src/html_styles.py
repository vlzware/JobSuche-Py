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
