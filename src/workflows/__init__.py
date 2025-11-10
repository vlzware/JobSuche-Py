"""
Workflow module - different use case workflows for job analysis
"""

from .base import BaseWorkflow
from .brainstorm import BrainstormWorkflow
from .cv_based import CVBasedWorkflow
from .multi_category import MultiCategoryWorkflow
from .perfect_job import PerfectJobWorkflow

__all__ = [
    "BaseWorkflow",
    "BrainstormWorkflow",
    "CVBasedWorkflow",
    "MultiCategoryWorkflow",
    "PerfectJobWorkflow",
]
