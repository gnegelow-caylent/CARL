# CARL Knowledge Base
"""
CARL Knowledge Base - Comprehensive AWS architecture patterns and pricing.

Auto-discovers pattern modules using naming convention:
- Files ending in *_patterns.py are automatically imported
- Functions named get_*_patterns() are automatically registered
- New pattern files work immediately without code changes

Current Pattern Categories (auto-discovered):
- architecture_patterns: Core networking and connectivity patterns
- vpc_patterns: VPC design, CIDR, subnets, endpoints
- vpc_endpoint_patterns: VPC endpoints, PrivateLink
- kms_patterns: KMS key management, encryption at rest
- account_patterns: Multi-account, OU structure, baselines
- identity_patterns: IAM Identity Center, permission sets, cross-account
- security_tooling_patterns: Security Hub, GuardDuty, Config, Inspector
- logging_patterns: Centralized logging, CloudTrail, retention
- operational_patterns: Tagging, backup/DR, cost management, SSM
- cloudwatch_alerting_patterns: CloudWatch alarms, notifications, dashboards
- waf_patterns: AWS WAF deployment, managed rules, bot control
- certificate_manager_patterns: ACM certificates, monitoring, automation
- ... and more (automatically added as new *_patterns.py files are created)

Other Modules:
- aws_pricing: Accurate AWS pricing data
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Callable

# Import core architecture patterns explicitly (has special exports)
from .architecture_patterns import (
    get_all_patterns,
    get_pattern_by_category,
    EGRESS_PATTERNS,
    INGRESS_PATTERNS,
    TRANSIT_PATTERNS,
    SITE_TO_SITE_VPN_PATTERNS,
    CLIENT_VPN_PATTERNS,
    CLOUDFRONT_PATTERNS,
    LANDING_ZONE_PATTERNS,
    DNS_PATTERNS,
    INSPECTION_PATTERNS,
)

# Import pricing utilities
from .aws_pricing import (
    calculate_monthly_cost,
    NETWORKING_PRICING,
    VPN_PRICING,
    DIRECT_CONNECT_PRICING,
    COMPUTE_PRICING,
    DATABASE_PRICING,
    STORAGE_PRICING,
    SECURITY_PRICING,
    LANDING_ZONE_PRICING,
)


# Auto-discovery registry
_PATTERN_GETTERS: dict[str, Callable] = {}


def _discover_pattern_modules():
    """
    Auto-discover pattern modules and their getter functions.

    Scans for *_patterns.py files and imports get_*_patterns() functions.
    This allows adding new pattern files without updating this __init__.py.
    """
    global _PATTERN_GETTERS

    # Get path to knowledge directory
    knowledge_dir = Path(__file__).parent

    # Find all *_patterns.py files
    for module_info in pkgutil.iter_modules([str(knowledge_dir)]):
        module_name = module_info.name

        # Skip non-pattern files
        if not module_name.endswith('_patterns'):
            continue

        # Skip architecture_patterns (already imported explicitly)
        if module_name == 'architecture_patterns':
            continue

        try:
            # Import the module
            module = importlib.import_module(f'.{module_name}', package='knowledge')

            # Look for get_*_patterns() function
            getter_name = f'get_{module_name}'
            if hasattr(module, getter_name):
                _PATTERN_GETTERS[module_name] = getattr(module, getter_name)
        except Exception:
            # Skip modules that can't be imported
            pass


# Run auto-discovery on import
_discover_pattern_modules()


def get_all_foundation_patterns() -> dict:
    """
    Get all foundation patterns across all categories.

    Auto-discovers and combines patterns from all *_patterns.py files.
    Adding a new pattern file automatically includes it here.
    """
    patterns = {}

    # Core networking patterns (special case - has its own prefix)
    patterns.update(get_all_patterns())

    # Auto-discovered pattern modules
    for module_name, getter_func in _PATTERN_GETTERS.items():
        try:
            # Extract category prefix from module name
            # Example: "vpc_patterns" → "vpc", "cloudwatch_alerting_patterns" → "cloudwatch_alerting"
            category_prefix = module_name.replace('_patterns', '')

            # Get patterns from module
            module_patterns = getter_func()

            # Add with category prefix
            patterns.update({f"{category_prefix}_{k}": v for k, v in module_patterns.items()})
        except Exception:
            # Skip modules with errors
            pass

    # Special patterns (non-standard naming)
    try:
        from .central_egress_inspection_pattern import get_central_egress_inspection_pattern
        patterns.update({"central_egress_inspection": get_central_egress_inspection_pattern()})
    except Exception:
        pass

    return patterns


def get_discovered_pattern_modules() -> list[str]:
    """Get list of auto-discovered pattern module names."""
    return sorted(_PATTERN_GETTERS.keys())


# Build __all__ dynamically
__all__ = [
    # Core functions
    "get_all_patterns",
    "get_pattern_by_category",
    "get_all_foundation_patterns",
    "get_discovered_pattern_modules",

    # Core pattern constants
    "EGRESS_PATTERNS",
    "INGRESS_PATTERNS",
    "TRANSIT_PATTERNS",
    "SITE_TO_SITE_VPN_PATTERNS",
    "CLIENT_VPN_PATTERNS",
    "CLOUDFRONT_PATTERNS",
    "LANDING_ZONE_PATTERNS",
    "DNS_PATTERNS",
    "INSPECTION_PATTERNS",

    # Pricing
    "calculate_monthly_cost",
    "NETWORKING_PRICING",
    "VPN_PRICING",
    "DIRECT_CONNECT_PRICING",
    "COMPUTE_PRICING",
    "DATABASE_PRICING",
    "STORAGE_PRICING",
    "SECURITY_PRICING",
    "LANDING_ZONE_PRICING",
]

# Add auto-discovered getters to exports
for module_name, getter_func in _PATTERN_GETTERS.items():
    getter_name = f'get_{module_name}'
    globals()[getter_name] = getter_func
    __all__.append(getter_name)
