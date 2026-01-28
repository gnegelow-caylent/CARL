"""
Tools for the Architect Agent.

These are Python functions that the agent can call autonomously to gather information.
The agent decides which tools to use based on the user's question.

Available tools:
- scan_aws_account: Scan actual AWS environment
- get_architecture_patterns: Retrieve relevant architecture patterns
- query_aws_pricing: Get accurate AWS pricing data
- calculate_cost_estimate: Estimate monthly costs for an architecture
"""

import json
from typing import Any

from utils.logger import get_logger
from services.aws_scanner import AWSScanner
from knowledge import (
    get_vpc_patterns,
    get_account_patterns,
    get_identity_patterns,
    get_security_tooling_patterns,
    get_logging_patterns,
    get_operational_patterns,
    NETWORKING_PRICING,
    VPN_PRICING,
    DIRECT_CONNECT_PRICING,
    SECURITY_PRICING,
    LANDING_ZONE_PRICING,
)
from knowledge.aws_pricing import (
    BACKUP_PRICING,
    LOGGING_PRICING,
    SYSTEMS_MANAGER_PRICING,
    IDENTITY_PRICING,
    FIREWALL_MANAGER_PRICING,
)

logger = get_logger(__name__)


def scan_aws_account(scope: str = "all") -> str:
    """
    Scan the actual AWS account to understand current infrastructure.

    The agent calls this when it needs to know what actually exists in the AWS account
    before making recommendations. This provides real data instead of assumptions.

    Args:
        scope: What to scan - "all", "network", "security", "identity", "compute"

    Returns:
        JSON string with scan results
    """
    logger.info(f"Tool called: scan_aws_account(scope={scope})")

    try:
        scanner = AWSScanner()

        if scope == "all":
            results = scanner.scan_environment()
        elif scope == "network":
            results = {
                "network": scanner._scan_network()
            }
        elif scope == "security":
            results = {
                "security_groups": scanner._scan_security_groups(),
                "encryption": scanner._scan_encryption()
            }
        elif scope == "identity":
            results = {
                "iam": scanner._scan_iam()
            }
        elif scope == "compliance":
            results = {
                "cloudtrail": scanner._scan_cloudtrail(),
                "s3": scanner._scan_s3_buckets()
            }
        else:
            results = scanner.scan_environment()

        # Summarize findings
        summary = scanner.get_summary(results)

        return json.dumps({
            "summary": summary,
            "detailed_findings": results
        }, indent=2)

    except Exception as e:
        logger.error(f"Error scanning AWS account: {e}")
        return json.dumps({
            "error": str(e),
            "message": "Could not scan AWS account. Proceeding with general recommendations."
        })


def get_architecture_patterns(category: str = "all") -> str:
    """
    Retrieve proven architecture patterns from CARL's knowledge base.

    The agent calls this to get reference architectures, best practices,
    and proven patterns for specific categories.

    Args:
        category: Pattern category - "vpc", "account", "identity", "security",
                  "logging", "operational", "all"

    Returns:
        JSON string with architecture patterns
    """
    logger.info(f"Tool called: get_architecture_patterns(category={category})")

    try:
        patterns = {}

        if category in ("vpc", "all"):
            patterns["vpc"] = get_vpc_patterns()

        if category in ("account", "all"):
            patterns["account"] = get_account_patterns()

        if category in ("identity", "all"):
            patterns["identity"] = get_identity_patterns()

        if category in ("security", "all"):
            patterns["security"] = get_security_tooling_patterns()

        if category in ("logging", "all"):
            patterns["logging"] = get_logging_patterns()

        if category in ("operational", "all"):
            patterns["operational"] = get_operational_patterns()

        # Simplify for agent consumption
        simplified = {}
        for cat, cat_patterns in patterns.items():
            simplified[cat] = {}
            for name, pattern in cat_patterns.items():
                if isinstance(pattern, dict):
                    simplified[cat][name] = {
                        "description": pattern.get("description", ""),
                        "when_to_use": pattern.get("when_to_use", ""),
                        "pros": pattern.get("pros", []),
                        "cons": pattern.get("cons", []),
                        "cost_profile": pattern.get("cost_profile", "")
                    }

        return json.dumps(simplified, indent=2)

    except Exception as e:
        logger.error(f"Error retrieving patterns: {e}")
        return json.dumps({
            "error": str(e),
            "message": "Could not retrieve architecture patterns"
        })


def query_aws_pricing(services: list[str]) -> str:
    """
    Get accurate AWS pricing data for specific services.

    The agent calls this to get real pricing information instead of guessing.
    This ensures cost estimates are accurate, not hallucinated.

    Args:
        services: List of services to get pricing for. Options:
                 - "networking" (NAT Gateway, Transit Gateway, VPC, etc.)
                 - "vpn" (Site-to-Site VPN, Client VPN)
                 - "direct_connect" (Direct Connect connections and data transfer)
                 - "security" (Security Hub, GuardDuty, Config, Inspector, etc.)
                 - "landing_zone" (Control Tower, Organizations, etc.)
                 - "backup" (AWS Backup)
                 - "logging" (CloudTrail, CloudWatch Logs, S3 storage)
                 - "systems_manager" (Systems Manager, Session Manager, Patch Manager)
                 - "identity" (IAM Identity Center)
                 - "firewall_manager" (AWS Firewall Manager)

    Returns:
        JSON string with pricing data
    """
    logger.info(f"Tool called: query_aws_pricing(services={services})")

    pricing_map = {
        "networking": NETWORKING_PRICING,
        "vpn": VPN_PRICING,
        "direct_connect": DIRECT_CONNECT_PRICING,
        "security": SECURITY_PRICING,
        "landing_zone": LANDING_ZONE_PRICING,
        "backup": BACKUP_PRICING,
        "logging": LOGGING_PRICING,
        "systems_manager": SYSTEMS_MANAGER_PRICING,
        "identity": IDENTITY_PRICING,
        "firewall_manager": FIREWALL_MANAGER_PRICING,
    }

    result = {}
    for service in services:
        if service in pricing_map:
            result[service] = pricing_map[service]
        else:
            result[service] = f"Unknown service: {service}"

    return json.dumps(result, indent=2)


def calculate_cost_estimate(
    architecture: str,
    components: dict[str, Any]
) -> str:
    """
    Calculate estimated monthly costs for a proposed architecture.

    The agent calls this to provide accurate cost breakdowns.

    Args:
        architecture: Short description of the architecture
        components: Dictionary of components and quantities, e.g.:
                   {
                       "nat_gateways": 2,
                       "transit_gateway": 1,
                       "vpcs": 3,
                       "data_transfer_gb": 1000,
                       "guardduty_accounts": 5
                   }

    Returns:
        JSON string with itemized cost estimate
    """
    logger.info(f"Tool called: calculate_cost_estimate(architecture={architecture})")

    # Define cost rates (from pricing data)
    rates = {
        "nat_gateway": 32.85,  # $0.045/hr
        "transit_gateway": 36.50,  # $0.05/hr
        "transit_gateway_attachment": 36.50,  # $0.05/hr
        "site_to_site_vpn": 36.50,  # $0.05/hr
        "guardduty_per_account": 4.60,  # Per account per month
        "security_hub_per_account": 1.00,  # Finding ingestion costs
        "config_per_rule": 2.00,  # Per rule per month
        "cloudtrail_per_trail": 0.00,  # First trail free, management events
        "data_transfer_gb": 0.09,  # Per GB inter-region/internet
        "vpc": 0.00,  # VPCs are free
        "control_tower": 0.00,  # Control Tower itself is free (pays for underlying services)
        "s3_standard_gb": 0.023,  # First 50 TB per month
        "cloudwatch_logs_gb": 0.50,  # Ingestion per GB
    }

    line_items = []
    total = 0.0

    for component, quantity in components.items():
        if component in rates:
            cost = rates[component] * quantity
            line_items.append({
                "component": component,
                "quantity": quantity,
                "unit_cost": rates[component],
                "monthly_cost": round(cost, 2)
            })
            total += cost
        else:
            logger.warning(f"Unknown component for pricing: {component}")

    result = {
        "architecture": architecture,
        "line_items": line_items,
        "total_monthly_cost": round(total, 2),
        "notes": [
            "Estimates based on us-east-1 pricing",
            "Data transfer costs vary by source/destination",
            "Actual costs may vary based on usage patterns"
        ]
    }

    return json.dumps(result, indent=2)


# Tool definitions for Agent Core
ARCHITECT_TOOLS = [
    {
        "name": "scan_aws_account",
        "description": """Scan the user's actual AWS account to understand current infrastructure.

        Use this when you need to know what actually exists before making recommendations.
        This provides real data about VPCs, security groups, IAM configuration, encryption,
        CloudTrail, S3 buckets, and more.

        Call this FIRST when the user asks questions about their specific environment.""",
        "function": scan_aws_account,
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["all", "network", "security", "identity", "compliance"],
                    "description": "What to scan: 'all' for complete scan, or specific area"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_architecture_patterns",
        "description": """Retrieve proven architecture patterns from CARL's knowledge base.

        Use this to get reference architectures, best practices, and design patterns.
        Patterns include VPC designs, multi-account structures, identity management,
        security tooling, logging, and operational best practices.

        Call this when you need examples or reference architectures to inform your recommendation.""",
        "function": get_architecture_patterns,
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["all", "vpc", "account", "identity", "security", "logging", "operational"],
                    "description": "Pattern category to retrieve"
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "query_aws_pricing",
        "description": """Get accurate AWS pricing data for services.

        ALWAYS use this for cost estimates - never guess at pricing.
        Returns real AWS pricing for networking, security services, logging,
        identity services, and more.

        Call this before providing any cost estimates in your recommendations.""",
        "function": query_aws_pricing,
        "input_schema": {
            "type": "object",
            "properties": {
                "services": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "networking", "vpn", "direct_connect", "security",
                            "landing_zone", "backup", "logging", "systems_manager",
                            "identity", "firewall_manager"
                        ]
                    },
                    "description": "List of AWS service categories to get pricing for"
                }
            },
            "required": ["services"]
        }
    },
    {
        "name": "calculate_cost_estimate",
        "description": """Calculate estimated monthly costs for a proposed architecture.

        Use this AFTER querying pricing to provide an itemized cost breakdown.
        Specify the architecture components and their quantities.

        Call this at the end of your recommendation to provide accurate cost estimates.""",
        "function": calculate_cost_estimate,
        "input_schema": {
            "type": "object",
            "properties": {
                "architecture": {
                    "type": "string",
                    "description": "Brief description of the architecture being estimated"
                },
                "components": {
                    "type": "object",
                    "description": "Dictionary of components and quantities (e.g., {'nat_gateways': 2, 'vpcs': 3})",
                    "additionalProperties": True
                }
            },
            "required": ["architecture", "components"]
        }
    }
]
