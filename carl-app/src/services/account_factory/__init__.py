"""
Account Factory Service for CARL.

Generates AWS Account Factory for Terraform (AFT) configurations
based on compliance frameworks (SOC2, HIPAA, PCI-DSS, etc.).

Uses the same modular framework approach as Foundation Builder,
allowing any compliance framework to be plugged in.
"""

from .account_factory_service import (
    AccountFactoryService,
    AccountFactorySession,
    AccountConfig,
    get_account_factory_service,
)
from .aft_generator import (
    AFTGenerator,
    AFTModuleConfig,
)

__all__ = [
    "AccountFactoryService",
    "AccountFactorySession",
    "AccountConfig",
    "get_account_factory_service",
    "AFTGenerator",
    "AFTModuleConfig",
]
