"""
MCP Prompts for Paperbase

Reusable prompt templates for common analysis workflows.
"""

from .analysis import (
    analyze_low_confidence_prompt,
    compare_templates_prompt,
    document_summary_prompt
)

__all__ = [
    "analyze_low_confidence_prompt",
    "compare_templates_prompt",
    "document_summary_prompt"
]
