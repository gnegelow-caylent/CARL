"""
Architecture Tools for CARL's AI Agent

Wraps architecture services as AgentCore Tools so the AI agent can
autonomously provide architecture recommendations, pricing, and compliance guidance.
"""

import json
import os
from typing import Any

from services.agent_core import Tool
from services.architecture_advisor import ArchitectureAdvisor
from services.pricing_tool import get_aws_pricing
from services.pricing_prefetch_service import PricingPrefetchService
from services.cost_estimator import CostEstimator
from services.ai_terraform_generator import (
    AITerraformGenerator,
    TerraformGenerationRequest,
    get_patterns_for_module,
)
from knowledge.architecture_patterns import get_all_patterns
from knowledge.vpc_patterns import get_vpc_patterns
from knowledge.security_tooling_patterns import get_security_tooling_patterns
from knowledge.identity_patterns import get_identity_patterns
from knowledge.cloudwatch_alerting_patterns import get_cloudwatch_patterns as get_cloudwatch_alerting_patterns
from knowledge.waf_patterns import get_waf_patterns
from knowledge.certificate_manager_patterns import get_certificate_manager_patterns
# Rewritten patterns (using correct ArchitectureDecision API)
from knowledge.etl_patterns import PATTERNS as ETL_PATTERNS
from knowledge.serverless_patterns import PATTERNS as SERVERLESS_PATTERNS
from knowledge.container_patterns import PATTERNS as CONTAINER_PATTERNS
from knowledge.cicd_patterns import PATTERNS as CICD_PATTERNS

# Temporarily disabled - these patterns still use wrong ArchitectureDecision API (name/context/options dict)
# TODO: Rewrite these patterns to use correct API (question/options list/recommendation_logic/soc2_relevance)
# from knowledge.backup_dr_patterns import PATTERNS as BACKUP_DR_PATTERNS
# from knowledge.file_storage_patterns import PATTERNS as FILE_STORAGE_PATTERNS
# from knowledge.streaming_patterns import PATTERNS as STREAMING_PATTERNS
# from knowledge.additional_service_patterns import PATTERNS as ADDITIONAL_SERVICE_PATTERNS
# from knowledge.static_website_patterns import PATTERNS as STATIC_WEBSITE_PATTERNS
from utils.logger import get_logger

logger = get_logger(__name__)

# Initialize pricing cache service
_pricing_cache = None

def _get_pricing_cache():
    """Get or create pricing cache service instance."""
    global _pricing_cache
    if _pricing_cache is None:
        pricing_cache_table = os.environ.get("PRICING_CACHE_TABLE", "carl-dev-pricing-cache")
        _pricing_cache = PricingPrefetchService(pricing_cache_table=pricing_cache_table)
    return _pricing_cache

# Static fallback pricing for common services (updated Jan 2026)
# Used when cache is unavailable to prevent slow API calls
STATIC_PRICING = {
    "ec2": {
        "t3.micro": {"price_per_hour": "0.0104", "price_per_month": "7.59"},
        "t3.small": {"price_per_hour": "0.0208", "price_per_month": "15.18"},
        "t3.medium": {"price_per_hour": "0.0416", "price_per_month": "30.37"},
        "t3.large": {"price_per_hour": "0.0832", "price_per_month": "60.74"},
        "t3.xlarge": {"price_per_hour": "0.1664", "price_per_month": "121.47"},
        "m5.large": {"price_per_hour": "0.096", "price_per_month": "70.08"},
        "m5.xlarge": {"price_per_hour": "0.192", "price_per_month": "140.16"},
        "c5.large": {"price_per_hour": "0.085", "price_per_month": "62.05"},
        "c5.xlarge": {"price_per_hour": "0.17", "price_per_month": "124.10"},
        "r5.large": {"price_per_hour": "0.126", "price_per_month": "91.98"},
    },
    "rds": {
        "db.t3.micro": {"price_per_hour": "0.017", "price_per_month": "12.41"},
        "db.t3.small": {"price_per_hour": "0.034", "price_per_month": "24.82"},
        "db.t3.medium": {"price_per_hour": "0.068", "price_per_month": "49.64"},
        "db.m5.large": {"price_per_hour": "0.192", "price_per_month": "140.16"},
    },
    "lambda": {
        "execution": {"price_per_gb_second": "0.0000166667", "price_per_million_requests": "0.20"},
    },
    "s3": {
        "storage": {"price_per_gb_month": "0.023"},
        "requests": {"put_per_1000": "0.005", "get_per_1000": "0.0004"},
    },
    "dynamodb": {
        "on-demand": {"write_per_million": "1.25", "read_per_million": "0.25", "storage_per_gb": "0.25"},
    },
    "ecs": {
        "fargate": {"vcpu_per_hour": "0.04048", "gb_memory_per_hour": "0.004445"},
    },
}


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
            category: One of:
                - networking, vpc: VPC design, Transit Gateway, Direct Connect, VPN
                - security: Security Hub, GuardDuty, Config, CloudTrail, WAF, firewall
                - identity: IAM Identity Center, permission sets, SSO
                - cloudwatch, monitoring, alerting: CloudWatch alarms, dashboards, notifications
                - waf, firewall: AWS WAF, managed rules, bot control
                - certificate, acm, ssl: AWS Certificate Manager, SSL/TLS certificates
                - etl, data-processing: AWS Glue, Step Functions, data quality
                - serverless, api: Lambda, API Gateway, AppSync, Amplify
                - containers, ecs: ECS Fargate, EKS patterns
                - backup, disaster-recovery, dr: AWS Backup, cross-region replication
                - cicd, deployment: GitHub Actions, CodePipeline, blue/green
                - storage, file-storage: EFS, FSx for Windows, FSx for Lustre
                - streaming, real-time, kinesis: Kinesis Data Streams, Firehose
                - database, redshift, documentdb: Redshift, DocumentDB
                - cognito, authentication: Cognito User Pools
                - website, static-website, cloudfront: S3 + CloudFront + WAF

        Returns:
            Dict with patterns including pros, cons, cost estimates, compliance info
        """
        try:
            category = category.lower().strip()

            patterns_map = {
                "networking": get_all_patterns(),
                "vpc": get_vpc_patterns(),
                "security": get_security_tooling_patterns(),
                "identity": get_identity_patterns(),
                "cloudwatch": get_cloudwatch_alerting_patterns(),
                "monitoring": get_cloudwatch_alerting_patterns(),
                "alerting": get_cloudwatch_alerting_patterns(),
                "waf": get_waf_patterns(),
                "firewall": get_waf_patterns(),
                "certificate": get_certificate_manager_patterns(),
                "acm": get_certificate_manager_patterns(),
                "ssl": get_certificate_manager_patterns(),
                # Rewritten patterns (using correct API)
                "etl": ETL_PATTERNS,
                "data-processing": ETL_PATTERNS,
                "serverless": SERVERLESS_PATTERNS,
                "api": SERVERLESS_PATTERNS,
                "containers": CONTAINER_PATTERNS,
                "ecs": CONTAINER_PATTERNS,
                "cicd": CICD_PATTERNS,
                "deployment": CICD_PATTERNS,
                # Temporarily disabled patterns with wrong API - TODO: Rewrite these
                # "backup": BACKUP_DR_PATTERNS,
                # "disaster-recovery": BACKUP_DR_PATTERNS,
                # "dr": BACKUP_DR_PATTERNS,
                # "storage": FILE_STORAGE_PATTERNS,
                # "file-storage": FILE_STORAGE_PATTERNS,
                # "streaming": STREAMING_PATTERNS,
                # "real-time": STREAMING_PATTERNS,
                # "kinesis": STREAMING_PATTERNS,
                # "database": ADDITIONAL_SERVICE_PATTERNS,
                # "redshift": ADDITIONAL_SERVICE_PATTERNS,
                # "documentdb": ADDITIONAL_SERVICE_PATTERNS,
                # "cognito": ADDITIONAL_SERVICE_PATTERNS,
                # "authentication": ADDITIONAL_SERVICE_PATTERNS,
                # "website": STATIC_WEBSITE_PATTERNS,
                # "static-website": STATIC_WEBSITE_PATTERNS,
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
        Get AWS pricing for a service (cached or real-time).

        This function first checks the pricing cache (DynamoDB) for instant results,
        then falls back to AWS Price List API if not cached.

        Args:
            service_name: AWS service (ec2, rds, s3, lambda, dynamodb, etc.)
            **kwargs: Service-specific parameters (instance_type, region, storage_type, etc.)

        Returns:
            Dict with pricing information
        """
        try:
            region = kwargs.get("region", "us-east-1")

            # Try cache first for instant results
            cache_key = None
            if service_name == "ec2" and "instance_type" in kwargs:
                cache_key = f"ec2#{kwargs['instance_type']}"
            elif service_name == "rds" and "instance_class" in kwargs:
                cache_key = f"rds#{kwargs['instance_class']}"
            elif service_name == "lambda":
                cache_key = "lambda#execution"
            elif service_name == "s3":
                cache_key = "s3#standard-storage"
            elif service_name == "dynamodb":
                cache_key = "dynamodb#on-demand-write"
            elif service_name == "ecs":
                cache_key = "ecs#fargate-vcpu"

            # Check cache if we have a key
            if cache_key:
                try:
                    pricing_cache = _get_pricing_cache()
                    cached = pricing_cache.get_cached_price(cache_key, region)
                    if cached:
                        logger.info(f"✓ Pricing cache hit: {cache_key} in {region}")
                        return {
                            "success": True,
                            "service": service_name,
                            "pricing": cached,
                            "source": "cache"
                        }
                except Exception as cache_error:
                    logger.warning(f"Cache lookup failed: {cache_error}")

            # Try static fallback pricing (fast, no API call)
            static_price = None
            if service_name in STATIC_PRICING:
                if service_name == "ec2" and "instance_type" in kwargs:
                    instance_type = kwargs["instance_type"]
                    static_price = STATIC_PRICING["ec2"].get(instance_type)
                elif service_name == "rds" and "instance_class" in kwargs:
                    instance_class = kwargs["instance_class"]
                    static_price = STATIC_PRICING["rds"].get(instance_class)
                elif service_name in ["lambda", "s3", "dynamodb", "ecs"]:
                    static_price = STATIC_PRICING[service_name]

            if static_price:
                logger.info(f"✓ Using static pricing fallback: {cache_key or service_name}")
                return {
                    "success": True,
                    "service": service_name,
                    "pricing": static_price,
                    "source": "static",
                    "note": "Approximate pricing (us-east-1). Deploy pricing cache for real-time data."
                }

            # Last resort: API call (slow, should rarely happen)
            logger.warning(f"No cached or static pricing, calling API (slow): {service_name}")
            result = get_aws_pricing(service_code=service_name, **kwargs)
            return {
                "success": True,
                "service": service_name,
                "pricing": result,
                "source": "api"
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

                pricing = get_aws_pricing(service_code=service, **pricing_kwargs)

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

        Tool(
            name="generate_terraform",
            description="""Generate Terraform code using AI with architecture patterns as grounding context.

Use this to dynamically generate production-ready Terraform for:
- VPCs (vpc) - with subnets, NAT, flow logs
- Security services (security_services) - GuardDuty, Security Hub, Config, Inspector
- CloudTrail (cloudtrail) - organization trail with logging
- CloudWatch alarms (cloudwatch_alarms) - security monitoring
- AWS Config rules (config_rules) - compliance rules
- SCPs (scp) - service control policies
- IAM password policy (iam_password_policy)
- Central logging bucket (central_logging_bucket)
- Egress architecture (egress) - NAT, Network Firewall
- AFT account requests (aft_account_request)
- AFT main module (aft_main)

The AI is grounded by architecture patterns from knowledge/ to ensure:
- Accurate AWS configurations
- SOC 2 compliance mappings
- Cost-aware recommendations
- Best practices

Example: generate_terraform(module_type="vpc", requirements={"vpc_name": "prod", "cidr": "10.0.0.0/16", "azs": 3})""",
            function=generate_terraform_code,
            input_schema={
                "type": "object",
                "properties": {
                    "module_type": {
                        "type": "string",
                        "description": "Type of module: vpc, security_services, cloudtrail, cloudwatch_alarms, config_rules, scp, iam_password_policy, central_logging_bucket, egress, aft_account_request, aft_main"
                    },
                    "requirements": {
                        "type": "object",
                        "description": "Module-specific requirements (vpc_name, cidr, enable_nat, etc.)"
                    },
                    "compliance_framework": {
                        "type": "string",
                        "description": "Compliance framework: SOC2, HIPAA, PCI (default: SOC2)"
                    }
                },
                "required": ["module_type", "requirements"]
            }
        ),
    ]

    return tools


# =============================================================================
# AI-Driven Terraform Generation
# =============================================================================

# Singleton generator instance
_terraform_generator = None


def _get_terraform_generator() -> AITerraformGenerator:
    """Get or create the AI Terraform generator instance."""
    global _terraform_generator
    if _terraform_generator is None:
        _terraform_generator = AITerraformGenerator()
    return _terraform_generator


def generate_terraform_code(
    module_type: str,
    requirements: dict,
    compliance_framework: str = "SOC2"
) -> dict:
    """
    Generate Terraform code using AI with architecture patterns as grounding.

    This function is used by agents to dynamically generate Terraform code
    instead of using static templates. The AI is grounded by:
    - Architecture patterns from knowledge/ directory
    - Compliance framework requirements
    - AWS best practices

    Args:
        module_type: Type of Terraform module to generate
            - vpc: VPC with subnets, NAT, flow logs
            - security_services: GuardDuty, Security Hub, Config, Inspector
            - cloudtrail: Organization CloudTrail
            - cloudwatch_alarms: Security monitoring alarms
            - config_rules: AWS Config compliance rules
            - scp: Service Control Policies
            - iam_password_policy: IAM password policy
            - central_logging_bucket: S3 bucket for centralized logs
            - egress: Egress architecture (NAT, Network Firewall)
            - aft_account_request: AFT account request
            - aft_main: AFT main module configuration

        requirements: Module-specific requirements dict
            - vpc: {vpc_name, cidr, azs, enable_nat, enable_flow_logs}
            - security_services: {enable_guardduty, enable_security_hub, etc.}
            - cloudtrail: {multi_region, is_organization_trail, retention_days}
            - scp: {scp_name, description, policy_statements, target_ous}
            - etc.

        compliance_framework: SOC2, HIPAA, PCI (default: SOC2)

    Returns:
        dict with:
            - success: bool
            - content: Generated Terraform code
            - module_type: The module type
            - validation_errors: List of errors if any
    """
    try:
        generator = _get_terraform_generator()

        # Route to appropriate generator method based on module_type
        module_type_lower = module_type.lower().replace("-", "_")

        if module_type_lower == "vpc":
            result = generator.generate_vpc_module(
                vpc_name=requirements.get("vpc_name", "main"),
                cidr=requirements.get("cidr", "10.0.0.0/16"),
                azs=requirements.get("azs", 2),
                enable_nat=requirements.get("enable_nat", True),
                enable_flow_logs=requirements.get("enable_flow_logs", True),
                enable_endpoints=requirements.get("enable_endpoints", False),
                environment=requirements.get("environment", "production"),
                compliance=compliance_framework,
            )
        elif module_type_lower == "security_services":
            result = generator.generate_security_services_module(
                enable_guardduty=requirements.get("enable_guardduty", True),
                enable_security_hub=requirements.get("enable_security_hub", True),
                enable_config=requirements.get("enable_config", True),
                enable_inspector=requirements.get("enable_inspector", True),
                enable_macie=requirements.get("enable_macie", False),
                compliance=compliance_framework,
            )
        elif module_type_lower == "cloudtrail":
            result = generator.generate_cloudtrail_module(
                multi_region=requirements.get("multi_region", True),
                is_organization_trail=requirements.get("is_organization_trail", False),
                enable_log_validation=requirements.get("enable_log_validation", True),
                retention_days=requirements.get("retention_days", 2555),
                compliance=compliance_framework,
            )
        elif module_type_lower == "cloudwatch_alarms":
            result = generator.generate_cloudwatch_alarms(
                cloudtrail_log_group=requirements.get("cloudtrail_log_group", "/aws/cloudtrail/organization"),
                sns_topic_name=requirements.get("sns_topic_name", "security-alerts"),
                compliance=compliance_framework,
            )
        elif module_type_lower == "config_rules":
            result = generator.generate_config_rules(
                enable_org_rules=requirements.get("enable_org_rules", True),
                rules=requirements.get("rules"),
                compliance=compliance_framework,
            )
        elif module_type_lower == "scp":
            result = generator.generate_scp(
                scp_name=requirements.get("scp_name", "default-scp"),
                description=requirements.get("description", ""),
                policy_statements=requirements.get("policy_statements", []),
                target_ous=requirements.get("target_ous", []),
                compliance=compliance_framework,
            )
        elif module_type_lower == "scp_consolidated":
            # Generate all SCPs in a single file (AWS limit: 5 SCPs per OU)
            result = generator.generate_terraform(
                TerraformGenerationRequest(
                    module_type="scp_consolidated",
                    requirements=requirements,
                    compliance_framework=compliance_framework,
                    patterns_context="""Generate all Service Control Policies (SCPs) in a single main.tf file.

AWS Organizations has a limit of 5 SCPs per OU, so consolidating all SCPs into one file makes it easier to manage.

Structure:
- Use for_each or count to iterate over SCPs
- Each SCP should be a separate aws_organizations_policy resource
- Include aws_organizations_policy_attachment resources to attach SCPs to OUs
- Use locals to define SCP policy documents as JSON

Example pattern:
```hcl
locals {
  scps = {
    "deny-root-account" = {
      description = "Prevent root account usage"
      policy = jsonencode({...})
      target_ous = ["Workloads", "Security"]
    }
  }
}

resource "aws_organizations_policy" "scp" {
  for_each = local.scps

  name        = each.key
  description = each.value.description
  content     = each.value.policy
  type        = "SERVICE_CONTROL_POLICY"
}

resource "aws_organizations_policy_attachment" "scp" {
  for_each = {
    for pair in flatten([
      for scp_name, scp in local.scps : [
        for ou in scp.target_ous : {
          key = "\${scp_name}-\${ou}"
          policy_id = aws_organizations_policy.scp[scp_name].id
          target_id = var.target_ou_ids[ou]
        }
      ]
    ]) : pair.key => pair
  }

  policy_id = each.value.policy_id
  target_id = each.value.target_id
}
```
""",
                )
            )
        elif module_type_lower == "iam_password_policy":
            result = generator.generate_iam_password_policy(
                minimum_length=requirements.get("minimum_length", 14),
                require_uppercase=requirements.get("require_uppercase", True),
                require_lowercase=requirements.get("require_lowercase", True),
                require_numbers=requirements.get("require_numbers", True),
                require_symbols=requirements.get("require_symbols", True),
                max_age_days=requirements.get("max_age_days", 90),
                reuse_prevention=requirements.get("reuse_prevention", 24),
                compliance=compliance_framework,
            )
        elif module_type_lower == "central_logging_bucket":
            result = generator.generate_central_logging_bucket(
                bucket_name_suffix=requirements.get("bucket_name_suffix", "central-logs"),
                retention_days=requirements.get("retention_days", 2555),
                enable_access_logging=requirements.get("enable_access_logging", True),
                compliance=compliance_framework,
            )
        elif module_type_lower == "egress":
            result = generator.generate_egress_module(
                egress_type=requirements.get("egress_type", "distributed_nat"),
                vpc_count=requirements.get("vpc_count", 1),
                availability_zones=requirements.get("availability_zones", 2),
                transit_gateway_id=requirements.get("transit_gateway_id"),
                compliance=compliance_framework,
            )
        elif module_type_lower == "aft_account_request":
            result = generator.generate_aft_account_request(
                account_name=requirements.get("account_name", "new-account"),
                account_email=requirements.get("account_email", ""),
                ou_name=requirements.get("ou_name", "Workloads"),
                purpose=requirements.get("purpose", ""),
                sso_user_email=requirements.get("sso_user_email", ""),
                compliance=compliance_framework,
                tags=requirements.get("tags"),
            )
        elif module_type_lower == "aft_main":
            result = generator.generate_aft_main_module(
                primary_region=requirements.get("primary_region", "us-east-1"),
                terraform_version=requirements.get("terraform_version", "1.6.0"),
                delete_default_vpcs=requirements.get("delete_default_vpcs", True),
                compliance=compliance_framework,
            )
        elif module_type_lower == "providers":
            # Terraform provider configuration
            result = generator.generate_terraform(
                TerraformGenerationRequest(
                    module_type="providers",
                    requirements=requirements,
                    compliance_framework=compliance_framework,
                    patterns_context="Generate Terraform provider configuration for AWS, including region setup and required providers block.",
                )
            )
        elif module_type_lower == "variables":
            # Terraform variables
            result = generator.generate_terraform(
                TerraformGenerationRequest(
                    module_type="variables",
                    requirements=requirements,
                    compliance_framework=compliance_framework,
                    patterns_context="Generate Terraform variable definitions for the specified requirements.",
                )
            )
        elif module_type_lower == "account_customization":
            # AFT account customizations per OU
            result = generator.generate_terraform(
                TerraformGenerationRequest(
                    module_type="account_customization",
                    requirements=requirements,
                    compliance_framework=compliance_framework,
                    patterns_context=f"Generate AFT account customization Terraform for {requirements.get('customization_type', 'default')} OU with security services.",
                )
            )
        elif module_type_lower == "global_customization":
            # AFT global customizations
            result = generator.generate_terraform(
                TerraformGenerationRequest(
                    module_type="global_customization",
                    requirements=requirements,
                    compliance_framework=compliance_framework,
                    patterns_context="Generate AFT global customizations including IAM password policy, S3 block public access, and EBS encryption defaults.",
                )
            )
        else:
            # Generic generation using the base method
            result = generator.generate_terraform(
                TerraformGenerationRequest(
                    module_type=module_type,
                    requirements=requirements,
                    compliance_framework=compliance_framework,
                    patterns_context=get_patterns_for_module(module_type),
                )
            )

        return {
            "success": result.success,
            "content": result.content,
            "module_type": result.module_type,
            "validation_errors": result.validation_errors,
        }

    except Exception as e:
        logger.exception(f"Error generating Terraform for {module_type}")
        return {
            "success": False,
            "content": f"# Error generating Terraform: {str(e)}",
            "module_type": module_type,
            "validation_errors": [str(e)],
        }
