"""
Tests for the Config loader

These tests verify:
1. Config can be instantiated with test data (dependency injection)
2. Config.get() works with dot notation
3. Config handles missing keys gracefully
"""

from typing import Any

from src.config.loader import Config


class TestConfigDependencyInjection:
    """Test that Config supports dependency injection for testing"""

    def test_config_with_test_dict(self):
        """Should accept config dictionary for testing"""
        test_config = {
            "api": {"timeouts": {"api_request": 30}},
            "llm": {"models": {"default": "test-model"}},
        }

        config = Config(test_config)

        assert config.get("api.timeouts.api_request") == 30
        assert config.get("llm.models.default") == "test-model"

    def test_config_get_with_dot_notation(self):
        """Should navigate nested config with dot notation"""
        test_config = {"level1": {"level2": {"level3": {"value": "deep_value"}}}}

        config = Config(test_config)

        assert config.get("level1.level2.level3.value") == "deep_value"

    def test_config_get_returns_default_when_not_found(self):
        """Should return default value for missing keys"""
        test_config = {"existing": {"key": "value"}}

        config = Config(test_config)

        assert config.get("non.existent.key", "default") == "default"
        assert config.get("existing.missing", 42) == 42
        assert config.get("missing") is None

    def test_config_get_handles_non_dict_values(self):
        """Should return default if path goes through non-dict value"""
        test_config = {"string_value": "just a string", "number": 42}

        config = Config(test_config)

        # Trying to navigate through a string should return default
        assert config.get("string_value.key", "default") == "default"
        assert config.get("number.nested", "default") == "default"

    def test_config_property_accessors(self):
        """Should provide property accessors for major config sections"""
        test_config = {
            "api": {"key": "api_value"},
            "llm": {"key": "llm_value"},
            "search": {"key": "search_value"},
            "paths": {"key": "paths_value"},
            "processing": {"key": "processing_value"},
            "scraper": {"key": "scraper_value"},
        }

        config = Config(test_config)

        assert config.api == {"key": "api_value"}
        assert config.llm == {"key": "llm_value"}
        assert config.search == {"key": "search_value"}
        assert config.paths == {"key": "paths_value"}
        assert config.processing == {"key": "processing_value"}
        assert config.scraper == {"key": "scraper_value"}

    def test_config_property_returns_empty_dict_when_missing(self):
        """Should return empty dict for missing config sections"""
        test_config: dict[str, Any] = {}

        config = Config(test_config)

        assert config.api == {}
        assert config.llm == {}


class TestConfigIntegrationWithCodebase:
    """Test that Config works correctly with actual code"""

    def test_config_injection_prevents_file_system_access(self):
        """Injected config should not try to load from files"""
        test_config = {"api": {"arbeitsagentur": {"base_url": "https://test.api.com"}}}

        # This should work without any config files present
        config = Config(test_config)

        assert config.get("api.arbeitsagentur.base_url") == "https://test.api.com"
        # _config_dir should be None in test mode
        assert config._config_dir is None

    def test_config_supports_realistic_structure(self):
        """Should work with realistic config structure"""
        realistic_config = {
            "api": {
                "arbeitsagentur": {
                    "base_url": "https://rest.arbeitsagentur.de",
                    "headers": {
                        "user_agent": "JobSuche/1.0",
                        "host": "rest.arbeitsagentur.de",
                        "api_key": "test-key",
                    },
                    "params": {"angebotsart": "1", "pav": "false"},
                },
                "openrouter": {"endpoint": "https://openrouter.ai/api/v1/chat/completions"},
                "timeouts": {"api_request": 30, "classification": 30, "external_url": 15},
            },
            "llm": {
                "models": {"default": "google/gemini-2.5-flash"},
                "inference": {"temperature": 0.1},
            },
            "scraper": {
                "headers": {"user_agent": "Mozilla/5.0"},
                "html_cleanup": {"remove_tags": ["script", "style", "nav"]},
            },
            "processing": {
                "limits": {
                    "job_text_single_job": 3000,
                    "job_text_batch": 1000,
                    "job_text_mega_batch": 25000,
                }
            },
        }

        config = Config(realistic_config)

        # Test various access patterns
        assert config.get("api.arbeitsagentur.base_url") == "https://rest.arbeitsagentur.de"
        assert config.get("api.timeouts.api_request") == 30
        assert config.get("llm.models.default") == "google/gemini-2.5-flash"
        assert config.get("scraper.html_cleanup.remove_tags") == ["script", "style", "nav"]
        assert config.get("processing.limits.job_text_mega_batch") == 25000
