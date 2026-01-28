# Foundation Builder Module
"""
CARL Foundation Builder - Guided AWS infrastructure foundation building.

This module provides:
- Decision engine for guiding users through architecture choices
- Cost estimation with accurate AWS pricing
- Terraform code generation for selected patterns
- SOC 2 compliance mapping for all recommendations
"""

from .decision_engine import DecisionEngine, DecisionSession
from .foundation_builder import FoundationBuilder

__all__ = ["DecisionEngine", "DecisionSession", "FoundationBuilder"]
