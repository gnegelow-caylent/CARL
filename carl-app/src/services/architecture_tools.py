"""
Architecture Tools for CARL's AI Agent

Wraps architecture services as AgentCore Tools so the AI agent can
autonomously provide architecture recommendations, pricing, and compliance guidance.
"""

import json
from typing import Any

from agent_core import Tool
from services.architecture_advisor import ArchitectureAdvisor
from services.pricing_tool import get_aws_pricing
from services.cost_estimator import CostEstimator
from knowledge.architecture_patterns import get_all_patterns
from knowledge.vpc_patterns import VPC_PATTERNS
from knowledge.security_tooling_patterns import SECURITY_PATTERNS
from knowledge.identity_patterns import IDENTITY_PATTERNS
from utils.logger import get_logger

logger = get_logger(__name__)


def create_architecture_tools() -> list[Tool]:
    """
    Create all architecture tools for the AI agent.

    These tools allow the agent to autonomously:
    - Get architecture patterns
    - Calculate AWS pricing
    - Estimate costs
    - Compare options
    - Recommend compliant solutions
    """

    advisor = ArchitectureAdvisor()
    cost_estimator = CostEstimator()

    def get_patterns_for_category(category: str) -> dict:
        """
        Get architecture patterns for a specific category.

        Args:
            category: One of: networking, security, identity, compute, storage, database, serverless

        Returns:
            Dict with patterns including pros, cons, cost estimates, compliance info
        """
        try:
            category = category.lower().strip()

            patterns_map = {
                "networking": get_all_patterns(),
                "vpc": VPC_PATTERNS,
                "security": SECURITY_PATTERNS,
                "identity": IDENTITY_PATTERNS,
            }

            if category in patterns_map:
                return {
                    "success": True,
                    "category": category,
                    "patterns": patterns_map[category],
                    "count": len(patterns_map.get(category, []))
                }
            else:
                # Try to get from advisor's internal patterns
                if hasattr(advisor, 'patterns') and category in advisor.patterns:
                    patterns_list = advisor.patterns[category]
                    return {
                        "success": True,
                        "category": category,
                        "patterns": [p.__dict__ if hasattr(p, '__dict__') else p for p in patterns_list],
                        "count": len(patterns_list)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Unknown category: {category}. Available: networking, vpc, security, identity, compute, storage, database, serverless"
                    }

        except Exception as e:
            logger.error(f"Error getting patterns for {category}: {e}")
            return {"success": False, "error": str(e)}

    def get_pricing(service_name: str, **kwargs) -> dict:
        """
        Get real-time AWS pricing for a service.

        Args:
            service_name: AWS service (ec2, rds, s3, lambda, dynamodb, etc.)
            **kwargs: Service-specific parameters (instance_type, region, storage_type, etc.)

        Returns:
            Dict with pricing information
        """
        try:
            result = get_aws_pricing(service_name=service_name, **kwargs)
            return {
                "success": True,
                "service": service_name,
                "pricing": result
            }
        except Exception as e:
            logger.error(f"Error getting pricing for {service_name}: {e}")
            return {"success": False, "error": str(e)}

    def estimate_architecture_cost(
        components: list[str],
        usage_assumptions: dict = None
    ) -> dict:
        """
        Estimate monthly cost for an architecture with multiple components.

        Args:
            components: List of AWS services/resources (e.g., ["vpc", "ec2:t3.medium", "rds:db.t3.small"])
            usage_assumptions: Optional usage parameters (requests/month, data_transfer_gb, etc.)

        Returns:
            Dict with cost breakdown and total estimate
        """
        try:
            usage = usage_assumptions or {}

            # Parse components and estimate each
            cost_breakdown = []
            total_min = 0
            total_max = 0

            for component in components:
                # Parse component (e.g., "ec2:t3.medium" -> service="ec2", config="t3.medium")
                parts = component.split(":")
                service = parts[0].lower().strip()
                config = parts[1] if len(parts) > 1 else None

                # Get pricing
                pricing_kwargs = {}
                if config:
                    if service == "ec2":
                        pricing_kwargs["instance_type"] = config
                    elif service == "rds":
                        pricing_kwargs["instance_class"] = config

                pricing = get_aws_pricing(service_name=service, **pricing_kwargs)

                # Estimate monthly cost (simple heuristic)
                if isinstance(pricing, dict) and "price" in pricing:
                    hourly_price = pricing["price"]
                    monthly_cost = hourly_price * 730  # hours per month
                    cost_breakdown.append({
                        "service": service,
                        "config": config,
                        "monthly_cost": round(monthly_cost, 2)
                    })
                    total_min += monthly_cost * 0.8  # 80% utilization min
                    total_max += monthly_cost  # 100% utilization max

            return {
                "success": True,
                "breakdown": cost_breakdown,
                "total_estimate": {
                    "min": round(total_min, 2),
                    "max": round(total_max, 2),
                    "currency": "USD",
                    "period": "monthly"
                },
                "assumptions": usage
            }

        except Exception as e:
            logger.error(f"Error estimating cost: {e}")
            return {"success": False, "error": str(e)}

    def get_compliance_requirements(pattern_name: str) -> dict:
        """
        Get SOC 2 compliance requirements for an architecture pattern.

        Args:
            pattern_name: Name of architecture pattern

        Returns:
            Dict with compliance controls, requirements, and implementation guidance
        """
        try:
            # Map common patterns to SOC 2 controls
            compliance_mapping = {
                "vpc": [
                    "CC6.6 - Network segmentation and isolation",
                    "CC6.7 - Network security controls",
                ],
                "security": [
                    "CC6.1 - Logical access controls",
                    "CC6.2 - Authentication mechanisms",
                    "CC7.2 - Security monitoring and logging",
                ],
                "identity": [
                    "CC6.1 - Logical and physical access controls",
                    "CC6.2 - MFA and strong authentication",
                    "CC6.3 - Access removal procedures",
                ],
                "logging": [
                    "CC7.2 - System monitoring and logging",
                    "CC7.3 - Evaluation of security events",
                ],
                "encryption": [
                    "CC6.7 - Encryption of sensitive data",
                    "CC6.1 - Data protection controls",
                ],
            }

            # Find relevant controls
            controls = []
            pattern_lower = pattern_name.lower()
            for keyword, control_list in compliance_mapping.items():
                if keyword in pattern_lower:
                    controls.extend(control_list)

            if not controls:
                controls = ["CC6.1 - General security controls apply"]

            return {
                "success": True,
                "pattern": pattern_name,
                "soc2_controls": controls,
                "compliance_level": "standard",
                "recommendations": [
                    "Enable CloudTrail for audit logging",
                    "Use KMS for encryption at rest",
                    "Implement least privilege IAM policies",
                    "Enable VPC Flow Logs for network monitoring"
                ]
            }

        except Exception as e:
            logger.error(f"Error getting compliance requirements: {e}")
            return {"success": False, "error": str(e)}

    def compare_architecture_options(
        option_a: str,
        option_b: str,
        criteria: list[str] = None
    ) -> dict:
        """
        Compare two architecture options across multiple criteria.

        Args:
            option_a: First option description
            option_b: Second option description
            criteria: Optional list of comparison criteria (cost, complexity, scalability, compliance)

        Returns:
            Dict with side-by-side comparison and recommendation
        """
        try:
            criteria = criteria or ["cost", "complexity", "scalability", "compliance"]

            # Use AI to analyze and compare
            comparison_prompt = f"""
Compare these two AWS architecture options:

Option A: {option_a}
Option B: {option_b}

Compare across these criteria: {', '.join(criteria)}

Provide:
1. Pros and cons of each
2. Cost comparison (rough estimate)
3. Complexity assessment
4. Scalability characteristics
5. Compliance considerations
6. Recommendation with reasoning
"""

            # For now, return structured template
            # In production, this would call BedrockService for AI analysis
            return {
                "success": True,
                "option_a": option_a,
                "option_b": option_b,
                "criteria": criteria,
                "comparison": {
                    "cost": "Analysis pending - call get_pricing for each option",
                    "complexity": "Analysis pending - requires detailed evaluation",
                    "scalability": "Analysis pending",
                    "compliance": "Both can meet SOC 2 with proper configuration"
                },
                "recommendation": "Use compare functionality with specific pricing queries for accurate comparison"
            }

        except Exception as e:
            logger.error(f"Error comparing options: {e}")
            return {"success": False, "error": str(e)}

    # Create Tool instances
    tools = [
        Tool(
            name="get_architecture_patterns",
            description="""Get AWS architecture patterns for a category. Returns proven patterns with pros, cons, costs, and compliance info.

Categories: networking, vpc, security, identity, compute, storage, database, serverless

Use this to:
- Get design options for a requirement
- Understand tradeoffs between approaches
- Find compliant patterns

Example: get_architecture_patterns(category="vpc") returns VPC design patterns""",
            function=get_patterns_for_category,
            input_schema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Architecture category: networking, vpc, security, identity, compute, storage, database, serverless"
                    }
                },
                "required": ["category"]
            }
        ),

        Tool(
            name="get_aws_pricing",
            description="""Get real-time AWS pricing from AWS Price List API. Always use this for accurate cost information.

Supported services: ec2, rds, s3, lambda, dynamodb, glue, dms, redshift, emr, kinesis, vpc, elb, etc.

Use this to:
- Get current pricing for services
- Compare costs between instance types
- Calculate accurate cost estimates

Example: get_aws_pricing(service_name="ec2", instance_type="t3.medium", region="us-east-1")""",
            function=get_pricing,
            input_schema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "AWS service name (ec2, rds, s3, lambda, dynamodb, etc.)"
                    }
                },
                "required": ["service_name"]
            }
        ),

        Tool(
            name="estimate_architecture_cost",
            description="""Estimate monthly cost for a complete architecture with multiple AWS components.

Use this to:
- Get total cost for a solution
- Break down costs by service
- Provide cost ranges (min/max based on utilization)

Example: estimate_architecture_cost(components=["vpc", "ec2:t3.medium", "rds:db.t3.small", "s3"])""",
            function=estimate_architecture_cost,
            input_schema={
                "type": "object",
                "properties": {
                    "components": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of AWS components (e.g., ['vpc', 'ec2:t3.medium', 'rds:db.t3.small'])"
                    },
                    "usage_assumptions": {
                        "type": "object",
                        "description": "Optional usage assumptions (requests_per_month, data_transfer_gb, etc.)"
                    }
                },
                "required": ["components"]
            }
        ),

        Tool(
            name="get_compliance_requirements",
            description="""Get SOC 2 compliance requirements for an architecture pattern.

Use this to:
- Understand compliance obligations
- Get implementation guidance
- Map patterns to SOC 2 controls

Example: get_compliance_requirements(pattern_name="vpc with public and private subnets")""",
            function=get_compliance_requirements,
            input_schema={
                "type": "object",
                "properties": {
                    "pattern_name": {
                        "type": "string",
                        "description": "Architecture pattern name or description"
                    }
                },
                "required": ["pattern_name"]
            }
        ),

        Tool(
            name="compare_architecture_options",
            description="""Compare two architecture options across cost, complexity, scalability, and compliance.

Use this to:
- Help user decide between options
- Show tradeoffs clearly
- Provide recommendation with reasoning

Example: compare_architecture_options(option_a="EC2 with RDS", option_b="Lambda with DynamoDB", criteria=["cost", "scalability"])""",
            function=compare_architecture_options,
            input_schema={
                "type": "object",
                "properties": {
                    "option_a": {
                        "type": "string",
                        "description": "First architecture option"
                    },
                    "option_b": {
                        "type": "string",
                        "description": "Second architecture option"
                    },
                    "criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Comparison criteria (cost, complexity, scalability, compliance)"
                    }
                },
                "required": ["option_a", "option_b"]
            }
        ),
    ]

    return tools
