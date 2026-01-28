"""
Architecture Advisor Service for CARL.

Provides compliant architecture recommendations based on requirements,
balancing security, cost, and AWS best practices.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from services.bedrock_service import BedrockService
from services.cost_estimator import CostEstimator
from utils.logger import get_logger

logger = get_logger(__name__)


class CostTier(Enum):
    """Cost tier classifications."""
    MINIMAL = "minimal"      # <$100/month
    MODERATE = "moderate"    # $100-500/month
    STANDARD = "standard"    # $500-2000/month
    ENTERPRISE = "enterprise"  # $2000+/month


class ComplianceLevel(Enum):
    """Compliance strictness levels."""
    BASIC = "basic"          # Minimum viable compliance
    STANDARD = "standard"    # Recommended for most workloads
    STRICT = "strict"        # Maximum security, audit-ready


@dataclass
class ArchitectureOption:
    """Represents an architecture recommendation option."""
    name: str
    description: str
    cost_tier: CostTier
    monthly_cost_estimate: tuple[float, float]  # (min, max)
    compliance_level: ComplianceLevel
    components: list[str]
    pros: list[str]
    cons: list[str]
    soc2_controls_addressed: list[str]
    terraform_blueprint: str  # Blueprint name to use
    recommended: bool = False


@dataclass
class ArchitectureRecommendation:
    """Complete architecture recommendation with options."""
    requirement: str
    options: list[ArchitectureOption]
    ai_analysis: str
    recommended_option: str
    considerations: list[str]


class ArchitectureAdvisor:
    """Service for providing architecture recommendations."""

    def __init__(self):
        self.bedrock = BedrockService()
        self.cost_estimator = CostEstimator()
        self._load_patterns()

    def _load_patterns(self):
        """Load architecture patterns knowledge base."""
        self.patterns = {
            "networking": self._get_networking_patterns(),
            "compute": self._get_compute_patterns(),
            "database": self._get_database_patterns(),
            "storage": self._get_storage_patterns(),
            "security": self._get_security_patterns(),
            "serverless": self._get_serverless_patterns(),
        }

    def recommend(
        self,
        requirement: str,
        constraints: dict[str, Any] | None = None,
    ) -> ArchitectureRecommendation:
        """
        Generate architecture recommendations for a requirement.

        Args:
            requirement: Natural language description of what's needed
            constraints: Optional constraints (budget, compliance level, etc.)

        Returns:
            ArchitectureRecommendation with options
        """
        constraints = constraints or {}
        budget = constraints.get("budget")
        compliance_level = constraints.get("compliance_level", "standard")

        # Analyze requirement with AI
        category = self._categorize_requirement(requirement)
        patterns = self.patterns.get(category, self.patterns["security"])

        # Filter by constraints
        options = self._filter_options(patterns, budget, compliance_level)

        # Get AI analysis
        ai_analysis = self._get_ai_analysis(requirement, options, constraints)

        # Determine recommended option
        recommended = self._select_recommended(options, constraints)

        return ArchitectureRecommendation(
            requirement=requirement,
            options=options,
            ai_analysis=ai_analysis,
            recommended_option=recommended,
            considerations=self._get_considerations(category, constraints),
        )

    def _categorize_requirement(self, requirement: str) -> str:
        """Categorize requirement into architecture domain."""
        requirement_lower = requirement.lower()

        if any(w in requirement_lower for w in ["vpc", "network", "firewall", "waf", "subnet", "transit"]):
            return "networking"
        elif any(w in requirement_lower for w in ["ec2", "ecs", "eks", "container", "kubernetes", "compute"]):
            return "compute"
        elif any(w in requirement_lower for w in ["rds", "database", "dynamo", "aurora", "postgres", "mysql"]):
            return "database"
        elif any(w in requirement_lower for w in ["s3", "storage", "backup", "archive"]):
            return "storage"
        elif any(w in requirement_lower for w in ["lambda", "serverless", "api gateway", "step function"]):
            return "serverless"
        else:
            return "security"

    def _get_networking_patterns(self) -> list[ArchitectureOption]:
        """Get compliant networking architecture patterns."""
        return [
            ArchitectureOption(
                name="Basic Compliant VPC",
                description="Simple VPC with public/private subnets, NAT Gateway, and Security Groups",
                cost_tier=CostTier.MINIMAL,
                monthly_cost_estimate=(50, 150),
                compliance_level=ComplianceLevel.BASIC,
                components=[
                    "VPC with /16 CIDR",
                    "2 AZ deployment",
                    "Public and private subnets",
                    "Single NAT Gateway",
                    "Security Groups",
                    "VPC Flow Logs",
                ],
                pros=[
                    "Low cost",
                    "Simple to manage",
                    "Sufficient for dev/staging",
                ],
                cons=[
                    "Single NAT Gateway = single point of failure",
                    "No advanced threat protection",
                    "Limited for production SOC 2",
                ],
                soc2_controls_addressed=["CC6.6", "CC6.7"],
                terraform_blueprint="networking/basic-vpc",
            ),
            ArchitectureOption(
                name="Standard Compliant Network",
                description="Production-ready VPC with HA NAT, Network ACLs, and WAF",
                cost_tier=CostTier.MODERATE,
                monthly_cost_estimate=(200, 500),
                compliance_level=ComplianceLevel.STANDARD,
                components=[
                    "VPC with /16 CIDR",
                    "3 AZ deployment",
                    "Public, private, and isolated subnets",
                    "NAT Gateway per AZ (HA)",
                    "Network ACLs",
                    "Security Groups",
                    "VPC Flow Logs to CloudWatch",
                    "AWS WAF (if ALB present)",
                    "VPC Endpoints for AWS services",
                ],
                pros=[
                    "High availability",
                    "Defense in depth",
                    "SOC 2 compliant",
                    "Reduced data transfer costs via endpoints",
                ],
                cons=[
                    "Higher cost (3x NAT Gateways)",
                    "More complex to manage",
                ],
                soc2_controls_addressed=["CC6.6", "CC6.7", "CC7.2", "A1.1"],
                terraform_blueprint="networking/standard-vpc",
                recommended=True,
            ),
            ArchitectureOption(
                name="Enterprise Secure Network",
                description="Maximum security with AWS Network Firewall, WAF, Shield Advanced, and centralized inspection",
                cost_tier=CostTier.ENTERPRISE,
                monthly_cost_estimate=(1500, 5000),
                compliance_level=ComplianceLevel.STRICT,
                components=[
                    "VPC with /16 CIDR",
                    "3 AZ deployment",
                    "Public, private, isolated, and firewall subnets",
                    "NAT Gateway per AZ",
                    "AWS Network Firewall",
                    "AWS WAF with managed rules",
                    "AWS Shield Advanced",
                    "VPC Flow Logs to S3 + Athena",
                    "VPC Endpoints (all common services)",
                    "Transit Gateway (multi-VPC ready)",
                    "Route 53 Resolver DNS Firewall",
                    "Network ACLs with deny rules",
                ],
                pros=[
                    "Maximum security posture",
                    "Deep packet inspection",
                    "DDoS protection with SLA",
                    "Centralized traffic inspection",
                    "Full audit trail",
                ],
                cons=[
                    "Significant cost",
                    "Complex to manage",
                    "May be overkill for smaller workloads",
                ],
                soc2_controls_addressed=["CC6.6", "CC6.7", "CC6.8", "CC7.1", "CC7.2", "CC7.3", "A1.1", "A1.2"],
                terraform_blueprint="networking/enterprise-vpc",
            ),
        ]

    def _get_compute_patterns(self) -> list[ArchitectureOption]:
        """Get compliant compute architecture patterns."""
        return [
            ArchitectureOption(
                name="Basic EC2 Deployment",
                description="Simple EC2 instances with SSM access, no SSH",
                cost_tier=CostTier.MINIMAL,
                monthly_cost_estimate=(50, 200),
                compliance_level=ComplianceLevel.BASIC,
                components=[
                    "EC2 instances in private subnets",
                    "SSM Session Manager (no SSH)",
                    "IMDSv2 required",
                    "EBS encryption",
                    "CloudWatch agent",
                ],
                pros=["Low cost", "Simple", "No bastion needed"],
                cons=["No auto-scaling", "Manual patching"],
                soc2_controls_addressed=["CC6.1", "CC6.6", "CC6.5"],
                terraform_blueprint="compute/basic-ec2",
            ),
            ArchitectureOption(
                name="ECS Fargate Deployment",
                description="Serverless containers with ECS Fargate, ALB, and auto-scaling",
                cost_tier=CostTier.MODERATE,
                monthly_cost_estimate=(150, 600),
                compliance_level=ComplianceLevel.STANDARD,
                components=[
                    "ECS Cluster with Fargate",
                    "Application Load Balancer",
                    "ECR for container images",
                    "ECR image scanning",
                    "Auto-scaling policies",
                    "CloudWatch Container Insights",
                    "Secrets Manager integration",
                    "IAM task roles (least privilege)",
                ],
                pros=[
                    "No server management",
                    "Auto-scaling",
                    "Pay per use",
                    "Compliant by default",
                ],
                cons=[
                    "Higher per-compute cost than EC2",
                    "Cold start latency",
                ],
                soc2_controls_addressed=["CC6.1", "CC6.5", "CC6.6", "CC7.1", "A1.1"],
                terraform_blueprint="compute/ecs-fargate",
                recommended=True,
            ),
            ArchitectureOption(
                name="EKS Production Cluster",
                description="Managed Kubernetes with security best practices",
                cost_tier=CostTier.STANDARD,
                monthly_cost_estimate=(500, 2000),
                compliance_level=ComplianceLevel.STRICT,
                components=[
                    "EKS cluster (managed control plane)",
                    "Managed node groups (Bottlerocket)",
                    "Cluster autoscaler",
                    "AWS Load Balancer Controller",
                    "EBS CSI driver with encryption",
                    "Secrets Store CSI driver",
                    "Pod security standards",
                    "Network policies (Calico)",
                    "Fluent Bit logging",
                    "Container Insights",
                    "GuardDuty EKS protection",
                ],
                pros=[
                    "Full Kubernetes flexibility",
                    "Enterprise-grade",
                    "Strong isolation",
                ],
                cons=[
                    "Complexity",
                    "Requires Kubernetes expertise",
                    "Higher base cost",
                ],
                soc2_controls_addressed=["CC6.1", "CC6.5", "CC6.6", "CC6.8", "CC7.1", "CC7.2", "A1.1"],
                terraform_blueprint="compute/eks-cluster",
            ),
        ]

    def _get_database_patterns(self) -> list[ArchitectureOption]:
        """Get compliant database architecture patterns."""
        return [
            ArchitectureOption(
                name="RDS Single-AZ",
                description="Single-AZ RDS with encryption and automated backups",
                cost_tier=CostTier.MINIMAL,
                monthly_cost_estimate=(30, 150),
                compliance_level=ComplianceLevel.BASIC,
                components=[
                    "RDS instance (single-AZ)",
                    "Encryption at rest (KMS)",
                    "Encryption in transit (SSL)",
                    "Automated backups (7 days)",
                    "Private subnet only",
                    "Security group restricted",
                ],
                pros=["Low cost", "Simple", "Managed"],
                cons=["No HA", "RPO = backup interval"],
                soc2_controls_addressed=["CC6.5", "CC6.6", "A1.2"],
                terraform_blueprint="database/rds-single",
            ),
            ArchitectureOption(
                name="RDS Multi-AZ",
                description="High-availability RDS with Multi-AZ and enhanced monitoring",
                cost_tier=CostTier.MODERATE,
                monthly_cost_estimate=(150, 500),
                compliance_level=ComplianceLevel.STANDARD,
                components=[
                    "RDS Multi-AZ deployment",
                    "Encryption at rest (CMK)",
                    "Encryption in transit",
                    "Automated backups (30 days)",
                    "Enhanced monitoring",
                    "Performance Insights",
                    "IAM database authentication",
                    "Private subnet only",
                    "Deletion protection",
                ],
                pros=[
                    "Automatic failover",
                    "Strong durability",
                    "SOC 2 compliant",
                ],
                cons=["2x cost of single-AZ"],
                soc2_controls_addressed=["CC6.1", "CC6.5", "CC6.6", "A1.1", "A1.2"],
                terraform_blueprint="database/rds-multi-az",
                recommended=True,
            ),
            ArchitectureOption(
                name="Aurora Serverless v2",
                description="Auto-scaling Aurora with maximum availability",
                cost_tier=CostTier.STANDARD,
                monthly_cost_estimate=(200, 1500),
                compliance_level=ComplianceLevel.STRICT,
                components=[
                    "Aurora Serverless v2",
                    "Multi-AZ (3 AZs)",
                    "Encryption (CMK)",
                    "Automated backups (35 days)",
                    "PITR enabled",
                    "Global database ready",
                    "Enhanced monitoring",
                    "Performance Insights",
                    "IAM authentication",
                    "Audit logging to CloudWatch",
                    "Data API (optional)",
                ],
                pros=[
                    "Auto-scaling",
                    "High availability",
                    "Superior performance",
                    "Pay for actual use",
                ],
                cons=[
                    "Higher unit cost",
                    "Aurora-specific features",
                ],
                soc2_controls_addressed=["CC6.1", "CC6.5", "CC6.6", "CC7.2", "A1.1", "A1.2"],
                terraform_blueprint="database/aurora-serverless",
            ),
        ]

    def _get_storage_patterns(self) -> list[ArchitectureOption]:
        """Get compliant storage architecture patterns."""
        return [
            ArchitectureOption(
                name="Compliant S3 Bucket",
                description="S3 bucket with encryption, versioning, and access controls",
                cost_tier=CostTier.MINIMAL,
                monthly_cost_estimate=(5, 50),
                compliance_level=ComplianceLevel.STANDARD,
                components=[
                    "S3 bucket with versioning",
                    "SSE-S3 or SSE-KMS encryption",
                    "Block all public access",
                    "Bucket policy (least privilege)",
                    "Access logging enabled",
                    "Lifecycle rules",
                    "Object Lock (optional)",
                ],
                pros=[
                    "Low cost",
                    "Highly durable",
                    "Easy to implement",
                ],
                cons=["Manual policy management"],
                soc2_controls_addressed=["CC6.5", "CC6.6", "CC6.7", "A1.2"],
                terraform_blueprint="storage/compliant-s3",
                recommended=True,
            ),
            ArchitectureOption(
                name="S3 with Macie & GuardDuty",
                description="S3 with advanced data protection and threat detection",
                cost_tier=CostTier.MODERATE,
                monthly_cost_estimate=(50, 200),
                compliance_level=ComplianceLevel.STRICT,
                components=[
                    "All Standard S3 features",
                    "SSE-KMS (CMK)",
                    "Macie sensitive data discovery",
                    "GuardDuty S3 protection",
                    "S3 Object Lambda (data masking)",
                    "Replication (cross-region optional)",
                    "Object Lock (WORM)",
                    "EventBridge notifications",
                ],
                pros=[
                    "Maximum data protection",
                    "Automated PII detection",
                    "Threat detection",
                ],
                cons=["Higher cost", "More complex"],
                soc2_controls_addressed=["CC6.5", "CC6.6", "CC6.7", "CC7.2", "A1.2"],
                terraform_blueprint="storage/secure-s3",
            ),
        ]

    def _get_security_patterns(self) -> list[ArchitectureOption]:
        """Get security-focused architecture patterns."""
        return [
            ArchitectureOption(
                name="Basic Security Stack",
                description="Essential security services for compliance",
                cost_tier=CostTier.MINIMAL,
                monthly_cost_estimate=(30, 100),
                compliance_level=ComplianceLevel.BASIC,
                components=[
                    "AWS Config (essential rules)",
                    "CloudTrail (management events)",
                    "GuardDuty (basic)",
                    "Security Hub (1 standard)",
                    "IAM Access Analyzer",
                ],
                pros=["Low cost", "Quick to deploy", "Essential coverage"],
                cons=["Limited visibility", "Manual remediation"],
                soc2_controls_addressed=["CC6.1", "CC6.6", "CC7.2"],
                terraform_blueprint="security/basic-stack",
            ),
            ArchitectureOption(
                name="SOC 2 Security Stack",
                description="Complete security stack for SOC 2 Type II compliance",
                cost_tier=CostTier.MODERATE,
                monthly_cost_estimate=(100, 300),
                compliance_level=ComplianceLevel.STANDARD,
                components=[
                    "AWS Config (SOC 2 conformance pack)",
                    "CloudTrail (all events, multi-region)",
                    "GuardDuty (all protections)",
                    "Security Hub (multiple standards)",
                    "IAM Access Analyzer",
                    "Inspector (EC2 + Lambda)",
                    "Macie (sampling)",
                    "Audit Manager (SOC 2 framework)",
                    "KMS (CMKs with rotation)",
                ],
                pros=[
                    "SOC 2 ready",
                    "Automated evidence collection",
                    "Comprehensive monitoring",
                ],
                cons=["Moderate cost", "Alert fatigue possible"],
                soc2_controls_addressed=["CC6.1", "CC6.5", "CC6.6", "CC6.8", "CC7.1", "CC7.2", "CC7.3"],
                terraform_blueprint="security/soc2-stack",
                recommended=True,
            ),
        ]

    def _get_serverless_patterns(self) -> list[ArchitectureOption]:
        """Get serverless architecture patterns."""
        return [
            ArchitectureOption(
                name="Serverless API",
                description="API Gateway + Lambda with security best practices",
                cost_tier=CostTier.MINIMAL,
                monthly_cost_estimate=(10, 100),
                compliance_level=ComplianceLevel.STANDARD,
                components=[
                    "API Gateway (REST or HTTP)",
                    "Lambda functions (ARM64)",
                    "Lambda in VPC (optional)",
                    "Cognito or IAM auth",
                    "WAF on API Gateway",
                    "X-Ray tracing",
                    "CloudWatch Logs (encrypted)",
                    "Secrets Manager for secrets",
                ],
                pros=[
                    "Pay per request",
                    "Auto-scaling",
                    "Minimal ops",
                ],
                cons=["Cold starts", "Execution limits"],
                soc2_controls_addressed=["CC6.1", "CC6.6", "CC6.7", "CC7.2"],
                terraform_blueprint="serverless/api",
                recommended=True,
            ),
        ]

    def _filter_options(
        self,
        options: list[ArchitectureOption],
        budget: float | None,
        compliance_level: str,
    ) -> list[ArchitectureOption]:
        """Filter options based on constraints."""
        filtered = []

        for opt in options:
            # Budget filter
            if budget and opt.monthly_cost_estimate[0] > budget:
                continue

            # Compliance level filter (include same or higher)
            levels = ["basic", "standard", "strict"]
            opt_level = opt.compliance_level.value
            req_level = compliance_level.lower()

            if levels.index(opt_level) < levels.index(req_level):
                continue

            filtered.append(opt)

        return filtered if filtered else options  # Return all if none match

    def _get_ai_analysis(
        self,
        requirement: str,
        options: list[ArchitectureOption],
        constraints: dict,
    ) -> str:
        """Get AI-powered analysis of options."""
        options_summary = "\n".join([
            f"- {opt.name}: ${opt.monthly_cost_estimate[0]}-${opt.monthly_cost_estimate[1]}/mo, "
            f"{opt.compliance_level.value} compliance"
            for opt in options
        ])

        prompt = f"""Analyze these AWS architecture options for the requirement:

Requirement: {requirement}
Constraints: {json.dumps(constraints)}

Options:
{options_summary}

Provide a brief (2-3 sentences) analysis of:
1. Which option best fits the requirement
2. Key tradeoffs to consider
3. Any compliance considerations specific to SOC 2

Be concise and actionable."""

        return self.bedrock.invoke_model(prompt, max_tokens=300)

    def _select_recommended(
        self,
        options: list[ArchitectureOption],
        constraints: dict,
    ) -> str:
        """Select the recommended option based on constraints."""
        # If there's already a recommended option marked, use it
        for opt in options:
            if opt.recommended:
                return opt.name

        # Otherwise, pick middle ground (standard compliance, moderate cost)
        for opt in options:
            if opt.compliance_level == ComplianceLevel.STANDARD:
                return opt.name

        return options[0].name if options else "None"

    def _get_considerations(self, category: str, constraints: dict) -> list[str]:
        """Get category-specific considerations."""
        base_considerations = [
            "All estimates are approximate and may vary based on usage",
            "Consider starting with lower tier and scaling up as needed",
            "Review AWS pricing calculator for detailed estimates",
        ]

        category_considerations = {
            "networking": [
                "NAT Gateway charges for data processing ($0.045/GB)",
                "Network Firewall has separate endpoint and data processing charges",
                "VPC endpoints reduce NAT Gateway costs for AWS services",
            ],
            "compute": [
                "Consider Reserved Instances or Savings Plans for steady-state workloads",
                "Fargate Spot can reduce costs by 50-70% for fault-tolerant workloads",
                "Right-size instances using AWS Compute Optimizer",
            ],
            "database": [
                "Reserved Instances offer up to 60% savings",
                "Aurora Serverless charges per ACU-hour",
                "Consider read replicas for read-heavy workloads",
            ],
            "storage": [
                "S3 Intelligent-Tiering optimizes costs automatically",
                "Glacier for archives (retrieval has costs/delays)",
                "Consider S3 Lifecycle policies for cost optimization",
            ],
        }

        return base_considerations + category_considerations.get(category, [])
