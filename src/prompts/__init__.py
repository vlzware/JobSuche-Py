"""
Prompt templates for job classification workflows

This module provides configurable prompt templates for different classification
workflows. Users can customize prompts via prompts.yaml configuration file.
"""

from .templates import (
    CV_CLASSIFICATION_CRITERIA,
    CV_MATCHING_TEMPLATE,
    CV_PROFILE_TEMPLATE,
    get_cv_matching_prompt,
    load_custom_prompts,
)

__all__ = [
    "CV_CLASSIFICATION_CRITERIA",
    "CV_MATCHING_TEMPLATE",
    "CV_PROFILE_TEMPLATE",
    "get_cv_matching_prompt",
    "load_custom_prompts",
]
