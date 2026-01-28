# CARL Knowledge Base
"""
CARL Knowledge Base - Comprehensive AWS architecture patterns and pricing.

Modules:
- architecture_patterns: Core networking and connectivity patterns
- vpc_patterns: VPC design, CIDR, subnets, endpoints
- vpc_endpoint_patterns: VPC endpoints, PrivateLink (NEW)
- kms_patterns: KMS key management, encryption at rest (NEW)
- account_patterns: Multi-account, OU structure, baselines
- identity_patterns: IAM Identity Center, permission sets, cross-account
- security_tooling_patterns: Security Hub, GuardDuty, Config, Inspector
- logging_patterns: Centralized logging, CloudTrail, retention
- operational_patterns: Tagging, backup/DR, cost management, SSM
- aws_pricing: Accurate AWS pricing data
"""

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
)

from .vpc_patterns import get_vpc_patterns
from .vpc_endpoint_patterns import get_vpc_endpoint_patterns
from .kms_patterns import get_kms_patterns
from .account_patterns import get_account_patterns
from .identity_patterns import get_identity_patterns
from .security_tooling_patterns import get_security_tooling_patterns
from .logging_patterns import get_logging_patterns
from .operational_patterns import get_operational_patterns

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


def get_all_foundation_patterns() -> dict:
    """Get all foundation patterns across all categories."""
    patterns = {}

    # Core networking patterns
    patterns.update(get_all_patterns())

    # VPC design patterns
    patterns.update({f"vpc_{k}": v for k, v in get_vpc_patterns().items()})

    # VPC endpoint patterns (NEW)
    patterns.update({f"vpc_endpoint_{k}": v for k, v in get_vpc_endpoint_patterns().items()})

    # KMS patterns (NEW)
    patterns.update({f"kms_{k}": v for k, v in get_kms_patterns().items()})

    # Account structure patterns
    patterns.update({f"account_{k}": v for k, v in get_account_patterns().items()})

    # Identity patterns
    patterns.update({f"identity_{k}": v for k, v in get_identity_patterns().items()})

    # Security tooling patterns
    patterns.update({f"security_{k}": v for k, v in get_security_tooling_patterns().items()})

    # Logging patterns
    patterns.update({f"logging_{k}": v for k, v in get_logging_patterns().items()})

    # Operational patterns
    patterns.update({f"ops_{k}": v for k, v in get_operational_patterns().items()})

    return patterns


__all__ = [
    "get_all_patterns",
    "get_pattern_by_category",
    "get_all_foundation_patterns",
    "get_vpc_patterns",
    "get_vpc_endpoint_patterns",
    "get_kms_patterns",
    "get_account_patterns",
    "get_identity_patterns",
    "get_security_tooling_patterns",
    "get_logging_patterns",
    "get_operational_patterns",
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
