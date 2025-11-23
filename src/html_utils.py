"""
HTML utilities and constants for job exports
Provides helper functions and constants used across HTML exporters
"""

# Category name constants
CATEGORY_EXCELLENT = "Excellent Match"
CATEGORY_GOOD = "Good Match"
CATEGORY_POOR = "Poor Match"

# All valid categories
VALID_CATEGORIES = [CATEGORY_EXCELLENT, CATEGORY_GOOD, CATEGORY_POOR]


def sanitize_css_class(text: str) -> str:
    """
    Convert text to a safe CSS class name

    Converts category names or other text to lowercase, removes spaces and special chars.
    This ensures consistent class naming across all HTML exports.

    Examples:
        "Excellent Match" -> "excellentmatch"
        "Good Match" -> "goodmatch"
        "JS_REQUIRED" -> "jsrequired"

    Args:
        text: Text to convert to CSS class name

    Returns:
        Sanitized CSS class name (lowercase, no spaces/special chars)
    """
    return text.lower().replace(" ", "").replace("_", "").replace("-", "")


def get_category_css_class(category: str) -> str:
    """
    Get the CSS class name for a category

    This is the canonical way to convert category names to CSS classes.
    Uses sanitize_css_class for consistency.

    Args:
        category: Category name (e.g., "Excellent Match")

    Returns:
        CSS class name (e.g., "excellentmatch")
    """
    return sanitize_css_class(category)
