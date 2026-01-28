"""
VPC Endpoint and PrivateLink Patterns for CARL Foundation Builder.

Comprehensive patterns for VPC endpoints, PrivateLink, and private
connectivity to AWS services without internet gateway or NAT.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# VPC ENDPOINT STRATEGY PATTERNS
# =============================================================================

VPC_ENDPOINT_STRATEGY_PATTERNS = ArchitectureDecision(
    question="What VPC endpoint strategy should be implemented?",
    options=[
        DecisionOption(
            name="Gateway Endpoints Only (S3 + DynamoDB)",
            description="Free gateway endpoints for S3 and DynamoDB only",
            when_to_use=[
                "Cost optimization priority",
                "Only need S3 and DynamoDB private access",
                "Getting started with endpoints",
                "Development environments",
            ],
            when_not_to_use=[
                "Need private access to other AWS services",
                "Security requires no internet egress",
                "SOC 2 compliance requiring private connectivity",
            ],
            pros=[
                "Free (no charges)",
                "Simple to implement",
                "No ENI management",
                "No AZ dependency",
            ],
            cons=[
                "Only S3 and DynamoDB supported",
                "Must use NAT/IGW for other services",
                "Route table management needed",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=[
                "Gateway endpoints are free",
                "No hourly or data processing charges",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Selective Interface Endpoints",
            description="Interface endpoints for critical services only",
            when_to_use=[
                "Private connectivity to specific services",
                "Want to avoid NAT Gateway costs",
                "Security-critical services (SSM, Secrets Manager, KMS)",
                "Most production environments",
            ],
            when_not_to_use=[
                "Need endpoints for 10+ services (use comprehensive)",
                "Very cost-sensitive environments",
            ],
            pros=[
                "Private connectivity to critical services",
                "Reduces NAT Gateway costs",
                "Better security posture",
                "Pay only for what you use",
            ],
            cons=[
                "Per-endpoint charges ($7.20/mo each)",
                "Must manage ENIs per AZ",
                "DNS configuration needed",
            ],
            monthly_cost_range=(20.00, 100.00),
            cost_drivers=[
                "Interface endpoint: $0.01/hr = $7.20/mo",
                "Data processing: $0.01/GB",
                "Multiply by number of AZs (typically 2-3)",
                "3 endpoints × 2 AZs = ~$43/mo base",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Comprehensive Interface Endpoints",
            description="Interface endpoints for all AWS services in use",
            when_to_use=[
                "No NAT Gateway/IGW allowed",
                "Strict compliance (HIPAA, FedRAMP)",
                "Air-gapped or isolated VPCs",
                "Security > cost optimization",
            ],
            when_not_to_use=[
                "Cost is primary concern",
                "Simple workloads with few service dependencies",
            ],
            pros=[
                "Maximum security",
                "No internet gateway needed",
                "All traffic stays on AWS backbone",
                "Compliance-friendly",
            ],
            cons=[
                "High cost (many endpoints)",
                "Complex DNS management",
                "Many ENIs to manage",
            ],
            monthly_cost_range=(100.00, 500.00),
            cost_drivers=[
                "10-20 endpoints typical",
                "Each endpoint: $7.20/mo × AZs",
                "20 endpoints × 2 AZs = $288/mo",
                "Data processing adds $0.01/GB",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC6.8"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
        DecisionOption(
            name="Centralized Endpoint VPC",
            description="Shared VPC with endpoints, connected via Transit Gateway",
            when_to_use=[
                "Multi-VPC environment (5+ VPCs)",
                "Want to share endpoints across accounts",
                "Reduce per-VPC endpoint costs",
                "Centralized network architecture",
            ],
            when_not_to_use=[
                "Single VPC deployment",
                "Low endpoint usage",
                "No Transit Gateway in place",
            ],
            pros=[
                "Cost savings at scale",
                "Centralized management",
                "Single set of endpoints",
                "Easier to audit",
            ],
            cons=[
                "Transit Gateway costs",
                "More complex routing",
                "Single point of failure",
                "Higher latency",
            ],
            monthly_cost_range=(150.00, 400.00),
            cost_drivers=[
                "Endpoints: $100-200/mo",
                "TGW attachments: $36/mo per VPC",
                "TGW data processing: $0.02/GB",
                "Break-even at ~5-7 VPCs",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for VPC endpoint strategy:

    1. Do you have internet gateway or NAT gateway?
       NO (isolated VPC) → Comprehensive endpoints required
       YES → Continue to 2

    2. How many VPCs need endpoints?
       1-3 VPCs → Selective or Comprehensive per VPC
       4-10 VPCs → Consider centralized endpoint VPC
       10+ VPCs → Centralized endpoint VPC recommended

    3. What's your security requirement?
       Maximum (no internet) → Comprehensive endpoints
       Standard (SOC 2) → Selective endpoints for critical services
       Basic → Gateway endpoints only

    Essential Interface Endpoints (Priority Order):

    **Tier 1 (Security Critical):**
    - ssm, ssmmessages, ec2messages (Session Manager)
    - kms (encryption)
    - secretsmanager (secrets access)
    - logs (CloudWatch Logs)

    **Tier 2 (Common Services):**
    - ecr.dkr, ecr.api (container images)
    - s3 (if need interface endpoint features)
    - sts (temporary credentials)
    - ec2 (EC2 API calls)

    **Tier 3 (Service-Specific):**
    - rds (database API)
    - lambda (Lambda API)
    - ecs, ecs-telemetry, ecs-agent (ECS)
    - elasticloadbalancing (ALB/NLB API)
    - execute-api (API Gateway private endpoints)

    Cost optimization tips:
    - Start with gateway endpoints (free)
    - Add interface endpoints only when needed
    - Use centralized endpoint VPC at 5+ VPCs
    - Monitor data processing charges
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: VPC endpoints provide network segmentation
    - CC6.7: Private connectivity without internet exposure
    - CC6.8: Reduces attack surface

    VPC endpoints demonstrate:
    - Defense in depth (no internet gateway needed)
    - Data protection (traffic stays on AWS network)
    - Access control (endpoint policies)

    Auditors appreciate:
    - Documented endpoint strategy
    - Private connectivity for sensitive services
    - Endpoint policies restricting access
    """,
    common_mistakes=[
        "Forgetting gateway endpoints (S3, DynamoDB are free)",
        "Creating endpoints in only one AZ (no HA)",
        "Not enabling private DNS (manual DNS configuration)",
        "No endpoint policies (allowing all access)",
        "Interface endpoints when gateway would work",
        "Not monitoring endpoint costs (can add up)",
    ],
)


# =============================================================================
# ENDPOINT POLICY PATTERNS
# =============================================================================

ENDPOINT_POLICY_PATTERNS = ArchitectureDecision(
    question="How should VPC endpoint policies be configured?",
    options=[
        DecisionOption(
            name="Full Access (Default)",
            description="Allow all actions through endpoint",
            when_to_use=[
                "Getting started",
                "Development environments",
                "Trust internal services",
            ],
            when_not_to_use=[
                "Production environments",
                "Compliance requirements",
                "Need least privilege",
            ],
            pros=[
                "Simplest to implement",
                "No policy to maintain",
                "Won't block legitimate traffic",
            ],
            cons=[
                "No additional security layer",
                "Can't restrict by principal/action",
                "Auditors may question",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Endpoint policies are free"],
            soc2_controls=[],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Least Privilege Policies",
            description="Restrict access by principal, action, and resource",
            when_to_use=[
                "Production environments",
                "SOC 2 compliance",
                "Need defense in depth",
                "Sensitive data access",
            ],
            when_not_to_use=[
                "Development environments",
                "When IAM policies already very restrictive",
            ],
            pros=[
                "Additional security layer",
                "Defense in depth",
                "Compliance-friendly",
                "Prevent data exfiltration",
            ],
            cons=[
                "More complex to manage",
                "Can accidentally block legitimate traffic",
                "Requires testing",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Endpoint policies are free"],
            soc2_controls=["CC6.1", "CC6.6"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Endpoint policy best practices:

    **S3 Gateway Endpoint Policy Example:**
    Restrict to specific buckets and prevent data exfiltration:
    ```json
    {
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": "*",
          "Action": [
            "s3:GetObject",
            "s3:PutObject",
            "s3:ListBucket"
          ],
          "Resource": [
            "arn:aws:s3:::my-trusted-bucket/*",
            "arn:aws:s3:::my-trusted-bucket"
          ]
        },
        {
          "Effect": "Allow",
          "Principal": "*",
          "Action": "s3:GetObject",
          "Resource": "arn:aws:s3:::aws-managed-service-bucket/*"
        }
      ]
    }
    ```

    **Secrets Manager Interface Endpoint Policy:**
    Restrict to specific secrets and principals:
    ```json
    {
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:iam::ACCOUNT:role/MyAppRole"
          },
          "Action": [
            "secretsmanager:GetSecretValue"
          ],
          "Resource": [
            "arn:aws:secretsmanager:REGION:ACCOUNT:secret:prod/*"
          ]
        }
      ]
    }
    ```

    **KMS Interface Endpoint Policy:**
    Restrict to specific keys:
    ```json
    {
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": "*",
          "Action": [
            "kms:Decrypt",
            "kms:GenerateDataKey"
          ],
          "Resource": [
            "arn:aws:kms:REGION:ACCOUNT:key/KEY_ID"
          ]
        }
      ]
    }
    ```

    When to use endpoint policies:
    - Always for S3 gateway endpoints (prevent exfiltration)
    - Production environments for sensitive services
    - Compliance environments (HIPAA, PCI, FedRAMP)
    - When you need an additional security layer

    When to skip:
    - Development/sandbox environments
    - When IAM policies are already very restrictive
    - Simple use cases with high trust
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Endpoint policies provide additional access control
    - CC6.6: Network-layer restriction

    Endpoint policies provide defense in depth:
    - IAM policy controls who can do what
    - Endpoint policy controls what can flow through network
    - Both must allow for access to succeed
    """,
    common_mistakes=[
        "Not using S3 gateway endpoint policies (data exfiltration risk)",
        "Endpoint policy blocks AWS service-to-service calls",
        "Testing endpoint policy in production first",
        "Forgetting to allow AWS service principals",
    ],
)


# =============================================================================
# PRIVATELINK (SERVICE PROVIDER) PATTERNS
# =============================================================================

PRIVATELINK_PROVIDER_PATTERNS = ArchitectureDecision(
    question="How should PrivateLink be used for exposing services?",
    options=[
        DecisionOption(
            name="PrivateLink for SaaS Delivery",
            description="Expose your service to customers via PrivateLink",
            when_to_use=[
                "SaaS product with enterprise customers",
                "Customers require private connectivity",
                "No internet exposure allowed for customers",
                "Compliance-sensitive customers",
            ],
            when_not_to_use=[
                "Public API is acceptable",
                "Small customer base",
                "Cost optimization priority",
            ],
            pros=[
                "Customers stay on AWS network",
                "No internet exposure",
                "Scales automatically",
                "Customer-friendly for compliance",
            ],
            cons=[
                "NLB costs (provider side)",
                "Data processing charges",
                "More complex than public API",
            ],
            monthly_cost_range=(50.00, 500.00),
            cost_drivers=[
                "NLB: $16.20/mo + LCU charges",
                "Data processing: $0.01/GB",
                "Scales with customer usage",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="PrivateLink for Partner Integration",
            description="Private connectivity to partner services",
            when_to_use=[
                "Integration with partner SaaS",
                "Partner offers PrivateLink endpoint",
                "Compliance requires private connectivity",
                "High-bandwidth partner integration",
            ],
            when_not_to_use=[
                "Partner doesn't offer PrivateLink",
                "Low-volume integration",
                "Public internet is acceptable",
            ],
            pros=[
                "Private connectivity to partner",
                "Better performance",
                "Compliance-friendly",
                "No VPN needed",
            ],
            cons=[
                "Interface endpoint costs",
                "Partner must support PrivateLink",
                "Setup coordination needed",
            ],
            monthly_cost_range=(20.00, 100.00),
            cost_drivers=[
                "Interface endpoint: $7.20/mo per AZ",
                "Data processing: $0.01/GB",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="PrivateLink for Internal Services",
            description="Cross-account or cross-VPC service sharing",
            when_to_use=[
                "Shared services across accounts/VPCs",
                "Microservices architecture",
                "Service mesh requirements",
                "Need service-level access control",
            ],
            when_not_to_use=[
                "VPC peering or TGW sufficient",
                "Simple cross-account access",
                "Cost optimization priority",
            ],
            pros=[
                "Service-level isolation",
                "Consumer controls access",
                "Scalable",
                "No route table management",
            ],
            cons=[
                "NLB + endpoint costs",
                "More complex than VPC peering",
                "Adds latency",
            ],
            monthly_cost_range=(30.00, 200.00),
            cost_drivers=[
                "NLB (provider): $16.20/mo",
                "Interface endpoint (consumer): $7.20/mo per AZ",
                "Data processing: $0.01/GB both sides",
            ],
            soc2_controls=["CC6.6"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    PrivateLink decision tree:

    1. What's the use case?
       Expose service to customers → PrivateLink for SaaS
       Connect to partner service → PrivateLink consumer
       Internal service sharing → Evaluate vs TGW/peering

    2. Is private connectivity required or nice-to-have?
       Required (compliance) → PrivateLink
       Nice-to-have → Consider cost vs benefit

    3. How many consumers?
       1-5 → VPC peering may be simpler
       5+ → PrivateLink scales better

    PrivateLink provider setup:
    1. Deploy service behind NLB
    2. Create VPC Endpoint Service
    3. Configure acceptance (manual or automatic)
    4. Whitelist consumer accounts/principals
    5. Share service name with consumers

    PrivateLink consumer setup:
    1. Get service name from provider
    2. Create interface VPC endpoint
    3. Request connection (if manual acceptance)
    4. Wait for provider approval
    5. Use private DNS or endpoint DNS

    PrivateLink vs alternatives:
    - vs Public API: PrivateLink = private, better security
    - vs VPN: PrivateLink = easier, more scalable
    - vs VPC Peering: PrivateLink = service-level, no route overlap issues
    - vs TGW: PrivateLink = service-level, consumer controls
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: PrivateLink provides network isolation
    - CC6.7: Private connectivity (no internet)

    PrivateLink for compliance:
    - Customer data stays on AWS network
    - No internet exposure
    - Service provider can't reach consumer VPC
    - Consumer controls access via security groups
    """,
    common_mistakes=[
        "Using ALB instead of NLB (PrivateLink requires NLB)",
        "Not enabling private DNS (consumers must use endpoint DNS)",
        "Forgetting endpoint service permissions",
        "Not testing cross-AZ connectivity",
        "Assuming low latency (adds hop through NLB)",
    ],
)


def get_vpc_endpoint_patterns() -> dict:
    """Get all VPC endpoint and PrivateLink patterns."""
    return {
        "vpc_endpoint_strategy": VPC_ENDPOINT_STRATEGY_PATTERNS,
        "endpoint_policies": ENDPOINT_POLICY_PATTERNS,
        "privatelink": PRIVATELINK_PROVIDER_PATTERNS,
    }
