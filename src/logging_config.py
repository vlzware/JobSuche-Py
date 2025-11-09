"""
Logging configuration for JobSuche-Py

Provides structured logging with file output and optional console output.
All logs saved to session debug/ directory.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


class JobSucheLogger:
    """Centralized logger for the application"""

    def __init__(
        self, name: str = "jobsuche", log_file: Path | None = None, console_output: bool = True
    ):
        """
        Initialize logger

        Args:
            name: Logger name (usually "jobsuche" for main logger)
            log_file: Path to log file (optional)
            console_output: Whether to print to console
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Clear existing handlers
        self.logger.handlers = []

        # Format: timestamp - module - level - message
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Console handler (if enabled)
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        # File handler (if path provided)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        """Get the underlying logger instance"""
        return self.logger


def setup_session_logging(session_dir: Path, verbose: bool = True) -> logging.Logger:
    """
    Setup logging for a search session

    Args:
        session_dir: Session directory (e.g., data/searches/20251101_132537/)
        verbose: Whether to also print to console

    Returns:
        Configured logger instance
    """
    log_file = session_dir / "debug" / "session.log"

    logger_wrapper = JobSucheLogger(name="jobsuche", log_file=log_file, console_output=verbose)

    logger = logger_wrapper.get_logger()

    # Log session start
    logger.info("=" * 70)
    logger.info(f"JobSuche-Py Session Started: {datetime.now().isoformat()}")
    logger.info(f"Session directory: {session_dir}")
    logger.info("=" * 70)

    return logger


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Get logger for a specific module

    Args:
        module_name: Name of the module (e.g., 'scraper', 'classifier')

    Returns:
        Logger instance
    """
    return logging.getLogger(f"jobsuche.{module_name}")
