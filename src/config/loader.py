"""Configuration loader for the JobSuche application.

This module loads all configuration files from the config/ directory
and provides a singleton config object for easy access throughout the application.
"""

from pathlib import Path
from typing import Any, cast

import yaml


class Config:
    """Configuration manager that loads and provides access to all config files."""

    def __init__(self, config_dict: dict[str, Any] | None = None):
        """
        Initialize the configuration manager.

        Args:
            config_dict: Optional dictionary of config values for testing.
                        If provided, config files won't be loaded from disk.
        """
        self._configs: dict[str, Any]
        self._config_dir: Path | None

        if config_dict is not None:
            # Testing mode: use provided config
            self._configs = config_dict
            self._config_dir = None
        else:
            # Normal mode: load from files
            self._configs = {}
            self._config_dir = self._find_config_dir()
            self._load_all_configs()

    def _find_config_dir(self) -> Path:
        """Find the config directory relative to the project root."""
        # Start from this file's location and go up to project root
        current = Path(__file__).resolve()
        # Go up from src/config/loader.py to project root
        project_root = current.parent.parent.parent
        config_dir = project_root / "config"

        if not config_dir.exists():
            raise FileNotFoundError(
                f"Config directory not found at {config_dir}. "
                f"Please ensure the config/ directory exists in the project root."
            )

        return config_dir

    def _load_all_configs(self):
        """Load all YAML configuration files from the config directory."""
        if self._config_dir is None:
            return

        config_files = {
            "api": "api_config.yaml",
            "llm": "llm_config.yaml",
            "search": "search_config.yaml",
            "paths": "paths_config.yaml",
            "processing": "processing_config.yaml",
            "scraper": "scraper_config.yaml",
        }

        for key, filename in config_files.items():
            config_path = self._config_dir / filename
            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    loaded_config = yaml.safe_load(f)

                # Validate that loaded config is a dictionary
                if not isinstance(loaded_config, dict):
                    print(
                        f"Warning: Config file {filename} must contain a dictionary, "
                        f"got {type(loaded_config).__name__}. Using empty config."
                    )
                    self._configs[key] = {}
                else:
                    self._configs[key] = loaded_config
            else:
                print(f"Warning: Config file {filename} not found at {config_path}")
                self._configs[key] = {}

    def get(self, path: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.

        Args:
            path: Dot-separated path to the config value (e.g., "api.timeouts.api_request")
            default: Default value to return if path is not found

        Returns:
            The configuration value or default if not found

        Example:
            >>> config.get("api.timeouts.api_request")
            30
            >>> config.get("llm.models.default")
            "google/gemini-2.5-flash"
        """
        parts = path.split(".")
        value = self._configs

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    @property
    def api(self) -> dict[str, Any]:
        """Get API configuration."""
        # Safe cast: _load_all_configs validates all config values are dicts
        return cast(dict[str, Any], self._configs.get("api", {}))

    @property
    def llm(self) -> dict[str, Any]:
        """Get LLM configuration."""
        # Safe cast: _load_all_configs validates all config values are dicts
        return cast(dict[str, Any], self._configs.get("llm", {}))

    @property
    def search(self) -> dict[str, Any]:
        """Get search configuration."""
        # Safe cast: _load_all_configs validates all config values are dicts
        return cast(dict[str, Any], self._configs.get("search", {}))

    @property
    def paths(self) -> dict[str, Any]:
        """Get paths configuration."""
        # Safe cast: _load_all_configs validates all config values are dicts
        return cast(dict[str, Any], self._configs.get("paths", {}))

    @property
    def processing(self) -> dict[str, Any]:
        """Get processing configuration."""
        # Safe cast: _load_all_configs validates all config values are dicts
        return cast(dict[str, Any], self._configs.get("processing", {}))

    @property
    def scraper(self) -> dict[str, Any]:
        """Get scraper configuration."""
        # Safe cast: _load_all_configs validates all config values are dicts
        return cast(dict[str, Any], self._configs.get("scraper", {}))

    def reload(self):
        """Reload all configuration files."""
        self._configs.clear()
        self._load_all_configs()


# Create a singleton instance
config = Config()
