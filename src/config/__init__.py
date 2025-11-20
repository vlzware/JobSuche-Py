"""Configuration module for loading and accessing application settings."""

from src.exceptions import ConfigurationError

from .loader import Config, config

__all__ = ["Config", "ConfigurationError", "config"]
