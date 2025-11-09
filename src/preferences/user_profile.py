"""
User profile and preferences management

Handles user categories, preferences, and CV-based job matching
"""

from pathlib import Path

from ..classifier import DEFAULT_CATEGORIES, load_category_config
from ..config import config


class UserProfile:
    """
    Represents user preferences for job classification and matching

    This class encapsulates:
    - Category preferences
    - Category definitions for better LLM classification
    - CV parsing (future feature)
    - User-specific job criteria
    """

    def __init__(
        self,
        categories: list[str] | None = None,
        cv_path: str | None = None,
        config_path: str | None = None,
    ):
        """
        Initialize user profile

        Args:
            categories: Explicit category list (overrides config)
            cv_path: Path to user's CV (for CV-based matching)
            config_path: Path to categories config file (defaults to value from paths_config.yaml)
        """
        self.cv_path = cv_path
        self.cv_content: str | None = None

        # Get default config path if not provided
        if config_path is None:
            config_path = config.get("paths.files.categories", "categories.yaml")

        # Load categories with three-tier priority:
        # 1. Explicit categories (highest priority)
        # 2. Config file
        # 3. Defaults
        if categories is not None:
            self.categories = categories
            self.category_definitions = {}
            self.category_source = "explicit"
        else:
            config_categories, config_definitions = load_category_config(config_path)
            if config_categories:
                self.categories = config_categories
                self.category_definitions = config_definitions
                self.category_source = "config"
            else:
                self.categories = DEFAULT_CATEGORIES
                self.category_definitions = {}
                self.category_source = "defaults"

        # Load CV if provided
        if cv_path:
            self._load_cv()

    def _load_cv(self) -> None:
        """Load and parse CV content"""
        if not self.cv_path:
            return

        cv_file = Path(self.cv_path)
        if not cv_file.exists():
            print(f"Warning: CV file not found: {self.cv_path}")
            return

        try:
            with open(cv_file, encoding="utf-8") as f:
                self.cv_content = f.read()
        except Exception as e:
            print(f"Warning: Could not load CV: {e}")

    def get_categories(self) -> list[str]:
        """Get the list of categories for classification"""
        return self.categories

    def get_category_definitions(self) -> dict[str, str]:
        """Get category definitions for LLM guidance"""
        return self.category_definitions

    def get_category_source(self) -> str:
        """Get the source of categories (explicit, config, or defaults)"""
        return self.category_source

    def has_cv(self) -> bool:
        """Check if CV is loaded"""
        return self.cv_content is not None

    def get_cv_content(self) -> str | None:
        """Get CV content for LLM processing"""
        return self.cv_content

    def set_perfect_job_category(self, category_name: str, description: str) -> None:
        """
        Define a single "perfect job" category with detailed description

        This is useful for the "perfect job" workflow where you want to
        classify jobs as either matching your ideal or not.

        Args:
            category_name: Name of your perfect job category (e.g., "My Perfect Job")
            description: Detailed description of what makes a job perfect for you
        """
        self.categories = [category_name, "Andere"]
        self.category_definitions = {category_name: description}
        self.category_source = "perfect_job"

    def add_category_definition(self, category: str, definition: str) -> None:
        """
        Add or update a category definition

        Args:
            category: Category name
            definition: Detailed definition for LLM guidance
        """
        if category not in self.categories:
            self.categories.append(category)

        self.category_definitions[category] = definition

    def to_dict(self) -> dict:
        """Export profile as dictionary"""
        return {
            "categories": self.categories,
            "category_definitions": self.category_definitions,
            "category_source": self.category_source,
            "cv_path": self.cv_path,
            "has_cv": self.has_cv(),
        }

    def __repr__(self) -> str:
        return (
            f"UserProfile(categories={len(self.categories)}, "
            f"source={self.category_source}, "
            f"has_cv={self.has_cv()})"
        )
