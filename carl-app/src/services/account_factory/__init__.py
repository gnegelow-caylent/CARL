"""
Account Factory Service for CARL.

Generates AWS Account Factory for Terraform (AFT) configurations
based on compliance frameworks (SOC2, HIPAA, PCI-DSS, etc.).

Uses AI-driven Terraform generation (Design Principle #11).
No static templates - AI generates code dynamically with architecture
patterns as grounding context.
"""

from .account_factory_service import (
    AccountFactoryService,
    AccountFactorySession,
    AccountConfig,
    get_account_factory_service,
)

__all__ = [
    "AccountFactoryService",
    "AccountFactorySession",
    "AccountConfig",
    "get_account_factory_service",
]
