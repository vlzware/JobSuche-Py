"""
User profile management - handles CV loading for matching workflow
"""

from pathlib import Path


class UserProfile:
    """
    Represents user CV for job matching

    This class handles CV loading and provides access to CV content
    for the matching workflow.
    """

    def __init__(self, cv_path: str | None = None):
        """
        Initialize user profile

        Args:
            cv_path: Path to user's CV (for CV-based matching)
        """
        self.cv_path = cv_path
        self.cv_content: str | None = None

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

    def has_cv(self) -> bool:
        """Check if CV is loaded"""
        return self.cv_content is not None

    def get_cv_content(self) -> str | None:
        """Get CV content for LLM processing"""
        return self.cv_content

    def to_dict(self) -> dict:
        """Export profile as dictionary"""
        return {
            "cv_path": self.cv_path,
            "has_cv": self.has_cv(),
        }

    def __repr__(self) -> str:
        return f"UserProfile(has_cv={self.has_cv()})"
