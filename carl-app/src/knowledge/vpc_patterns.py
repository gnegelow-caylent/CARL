"""
VPC Design Patterns for CARL Foundation Builder.

Comprehensive VPC architecture decisions including CIDR planning,
subnet design, AZ strategy, and VPC endpoints.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# CIDR PLANNING PATTERNS
# =============================================================================

CIDR_PLANNING_PATTERNS = ArchitectureDecision(
    question="How should VPC CIDR blocks be planned?",
    options=[
        DecisionOption(
            name="Small VPC (/24 - 256 IPs)",
            description="Single /24 CIDR for small, focused workloads",
            when_to_use=[
                "Single small application",
                "Development/sandbox environments",
                "Isolated single-purpose VPC",
                "Testing environments",
            ],
            when_not_to_use=[
                "Production workloads that may grow",
                "Multiple applications in same VPC",
                "Need more than ~250 hosts",
                "EKS clusters (need more IPs)",
            ],
            pros=[
                "Minimal IP space consumption",
                "Simple to manage",
                "Easy to fit in larger CIDR plan",
                "Sufficient for small workloads",
            ],
            cons=[
                "Very limited growth room",
                "Only ~250 usable IPs",
                "May need VPC replacement to grow",
                "Not suitable for EKS (IP exhaustion)",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["CIDR blocks are free", "Cost is in resources deployed"],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Medium VPC (/20 - 4,096 IPs)",
            description="Balanced /20 CIDR for typical production workloads",
            when_to_use=[
                "Standard production VPCs",
                "Multiple applications with moderate scale",
                "ECS Fargate workloads",
                "Most general-purpose deployments",
            ],
            when_not_to_use=[
                "Large EKS clusters",
                "Thousands of EC2 instances",
                "IP-heavy architectures",
            ],
            pros=[
                "Good balance of space and efficiency",
                "Room for growth",
                "Supports multiple subnet tiers",
                "Works for most workloads",
            ],
            cons=[
                "May be tight for large EKS",
                "Limited if using EC2 mode EKS",
                "Need to plan subnets carefully",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["CIDR blocks are free"],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Large VPC (/16 - 65,536 IPs)",
            description="Large /16 CIDR for enterprise or EKS-heavy workloads",
            when_to_use=[
                "Large EKS clusters (especially EC2 mode)",
                "Enterprise production environments",
                "High-density compute workloads",
                "When future growth is uncertain",
            ],
            when_not_to_use=[
                "Small organizations with limited IP space",
                "Many VPCs needed (will exhaust 10.x.x.x)",
                "Need to peer with on-premises (overlap risk)",
            ],
            pros=[
                "Massive room for growth",
                "No IP exhaustion concerns",
                "Supports any workload type",
                "Can subdivide extensively",
            ],
            cons=[
                "Consumes large IP block",
                "May overlap with on-premises",
                "Limits number of VPCs possible",
                "Can mask poor subnet planning",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["CIDR blocks are free"],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="IPAM-Managed CIDR Allocation",
            description="Use AWS IPAM for centralized CIDR management",
            when_to_use=[
                "Multi-account environments (10+ accounts)",
                "Need to prevent CIDR overlaps",
                "Automated VPC provisioning (AFT)",
                "Enterprise governance requirements",
            ],
            when_not_to_use=[
                "Small deployments (< 5 VPCs)",
                "Single account",
                "Manual VPC creation is acceptable",
            ],
            pros=[
                "Prevents CIDR conflicts automatically",
                "Centralized IP management",
                "Audit trail for IP allocation",
                "Integrates with Organizations",
                "Supports both IPv4 and IPv6",
            ],
            cons=[
                "Additional complexity",
                "Cost for IPAM ($0.01/IP/month for public IPs)",
                "Learning curve",
                "Overkill for small deployments",
            ],
            monthly_cost_range=(0, 100.00),
            cost_drivers=[
                "IPAM for private IPs: Free",
                "IPAM for public IPs: $0.01/IP/month",
                "Active IP addresses only",
            ],
            soc2_controls=["CC6.6", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Decision tree for CIDR planning:

    1. Are you using EKS with EC2 nodes?
       YES → Large VPC (/16) or custom CNI
       NO → Continue to 2

    2. Expected number of hosts per VPC?
       < 200 → Small (/24)
       200-3000 → Medium (/20)
       > 3000 → Large (/16)

    3. Multi-account with 10+ VPCs?
       YES → Consider IPAM for governance
       NO → Manual allocation is fine

    CIDR planning best practices:
    - Reserve 10.0.0.0/8 for AWS (or portion of it)
    - Reserve 172.16.0.0/12 for on-premises
    - Use 192.168.0.0/16 for dev/sandbox only
    - Document all allocations in a central registry
    - Plan for 3x expected growth

    Example allocation scheme:
    - 10.0.0.0/16 - Production VPCs
    - 10.1.0.0/16 - Staging VPCs
    - 10.2.0.0/16 - Development VPCs
    - 10.10.0.0/16 - Shared Services
    - 10.20.0.0/16 - Network Hub (TGW attachments)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Network segmentation via VPC isolation
    - CC7.2: IPAM provides audit trail

    Proper CIDR planning prevents accidental exposure and enables
    network segmentation required for compliance.
    """,
    common_mistakes=[
        "Using 10.0.0.0/16 for everything (common default, causes overlaps)",
        "Not planning for VPC peering/TGW (overlapping CIDRs)",
        "Undersizing for EKS (IP exhaustion)",
        "No documentation of CIDR allocations",
        "Forgetting AWS reserves 5 IPs per subnet",
    ],
)


# =============================================================================
# SUBNET TIER PATTERNS
# =============================================================================

SUBNET_TIER_PATTERNS = ArchitectureDecision(
    question="How should subnets be organized within VPCs?",
    options=[
        DecisionOption(
            name="Two-Tier (Public + Private)",
            description="Simple public and private subnet tiers",
            when_to_use=[
                "Simple applications",
                "Development environments",
                "Single application per VPC",
                "Serverless workloads (Lambda, Fargate)",
            ],
            when_not_to_use=[
                "Need database isolation",
                "Compliance requires network segmentation",
                "Multiple security zones needed",
            ],
            pros=[
                "Simplest to understand and manage",
                "Fewer route tables",
                "Lower operational overhead",
                "Sufficient for many workloads",
            ],
            cons=[
                "No database tier isolation",
                "Less granular security",
                "May not meet compliance requirements",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Subnets are free", "Cost is in NAT Gateways, etc."],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Three-Tier (Public + App + Data)",
            description="Classic three-tier with dedicated data subnet",
            when_to_use=[
                "Production applications",
                "Compliance requirements (SOC 2, PCI)",
                "Applications with databases",
                "Need to restrict database network access",
            ],
            when_not_to_use=[
                "Very simple applications",
                "Serverless-only workloads",
                "When simplicity is paramount",
            ],
            pros=[
                "Database isolation",
                "Defense in depth",
                "Meets most compliance requirements",
                "Industry standard pattern",
            ],
            cons=[
                "More route tables to manage",
                "Slightly more complex",
                "Need to plan CIDR subdivision",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Subnets are free"],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Four-Tier (Public + App + Data + Management)",
            description="Full isolation with dedicated management/TGW tier",
            when_to_use=[
                "Enterprise production",
                "Transit Gateway attachments",
                "Network Firewall deployments",
                "Bastion hosts or management access",
                "Strict compliance (PCI-DSS, HIPAA)",
            ],
            when_not_to_use=[
                "Simple deployments",
                "Cost optimization priority",
                "No TGW or centralized connectivity",
            ],
            pros=[
                "Maximum isolation",
                "Dedicated TGW attachment subnets",
                "Cleaner routing for inspection",
                "Management plane isolation",
            ],
            cons=[
                "Most complex routing",
                "More subnets to manage",
                "Need larger CIDR allocation",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Subnets are free", "Complexity cost is operational"],
            soc2_controls=["CC6.6", "CC6.7", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Five-Tier (+ Firewall Tier)",
            description="Full enterprise with dedicated firewall inspection tier",
            when_to_use=[
                "AWS Network Firewall deployment",
                "Gateway Load Balancer integration",
                "Third-party firewall appliances",
                "Traffic inspection requirements",
            ],
            when_not_to_use=[
                "No traffic inspection requirement",
                "Cost sensitive deployments",
                "Simple architectures",
            ],
            pros=[
                "Proper firewall traffic flow",
                "Symmetric routing for inspection",
                "Supports complex inspection patterns",
                "Enterprise-grade segmentation",
            ],
            cons=[
                "Most complex to design",
                "Routing can be tricky",
                "Highest operational overhead",
                "Need significant CIDR space",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Network Firewall is the cost, not subnets"],
            soc2_controls=["CC6.6", "CC6.7", "CC6.8", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Decision tree for subnet tiers:

    1. Do you have compliance requirements (SOC 2, PCI, HIPAA)?
       YES → Minimum three-tier
       NO → Two-tier may be sufficient

    2. Will you use Transit Gateway?
       YES → Consider four-tier (dedicated TGW subnets)
       NO → Three-tier is typically sufficient

    3. Do you need traffic inspection (Network Firewall)?
       YES → Five-tier with firewall subnets
       NO → Skip firewall tier

    4. What's running in the VPC?
       Serverless only → Two-tier
       EC2/ECS + RDS → Three-tier
       Complex enterprise → Four or five-tier

    Subnet sizing guidance (for /20 VPC):
    - Public: /24 per AZ (256 IPs) - ALB, NAT GW
    - App: /22 per AZ (1024 IPs) - Compute
    - Data: /24 per AZ (256 IPs) - RDS, ElastiCache
    - TGW/Mgmt: /28 per AZ (16 IPs) - Attachments only
    - Firewall: /28 per AZ (16 IPs) - GWLB endpoints
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Logical access controls through segmentation
    - CC6.7: Data transmission security (internal routing)
    - CC6.8: Network-level protection
    - CC7.2: Monitoring capability per tier

    Three-tier minimum is recommended for SOC 2 to demonstrate
    defense in depth and database isolation.
    """,
    common_mistakes=[
        "Putting databases in app subnets",
        "Using same route table for all private subnets",
        "TGW attachment in app subnets (routing issues)",
        "Undersizing firewall subnets (need room for scaling)",
        "Not reserving IPs for future growth",
    ],
)


# =============================================================================
# AVAILABILITY ZONE PATTERNS
# =============================================================================

AVAILABILITY_ZONE_PATTERNS = ArchitectureDecision(
    question="How many Availability Zones should be used?",
    options=[
        DecisionOption(
            name="Single AZ",
            description="All resources in one Availability Zone",
            when_to_use=[
                "Development/test environments",
                "Cost optimization is top priority",
                "Non-critical workloads",
                "Temporary/short-lived environments",
            ],
            when_not_to_use=[
                "Production workloads",
                "Any SLA requirements",
                "Compliance requires HA",
                "Stateful applications",
            ],
            pros=[
                "Lowest cost (no cross-AZ traffic)",
                "Simplest architecture",
                "No cross-AZ latency",
            ],
            cons=[
                "No fault tolerance",
                "Single point of failure",
                "AZ outage = full outage",
                "Does not meet most compliance",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=[
                "Saves cross-AZ data transfer ($0.01/GB)",
                "One NAT Gateway instead of multiple",
            ],
            soc2_controls=[],  # Does not address availability
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Two AZs (Standard HA)",
            description="Resources spread across two Availability Zones",
            when_to_use=[
                "Standard production workloads",
                "Cost-conscious HA",
                "Regions with only 2-3 AZs",
                "Most SOC 2 compliant deployments",
            ],
            when_not_to_use=[
                "Maximum availability requirements",
                "Services requiring 3 AZs (some AWS services)",
                "Very large scale deployments",
            ],
            pros=[
                "Survives single AZ failure",
                "Good balance of cost and availability",
                "Sufficient for most compliance",
                "Works in all regions",
            ],
            cons=[
                "50% capacity during AZ failure",
                "Some services prefer 3 AZs",
                "Cross-AZ data transfer costs",
            ],
            monthly_cost_range=(0, 50.00),
            cost_drivers=[
                "2x NAT Gateways: $64.80/mo",
                "Cross-AZ data: $0.01/GB each way",
                "Estimate 500GB cross-AZ: $10/mo",
            ],
            soc2_controls=["A1.1", "A1.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Three AZs (High Availability)",
            description="Resources spread across three Availability Zones",
            when_to_use=[
                "Mission-critical production",
                "99.99%+ availability targets",
                "EKS control plane best practice",
                "Large scale deployments",
                "Zonal services (Aurora, OpenSearch)",
            ],
            when_not_to_use=[
                "Cost optimization priority",
                "Regions with only 2 AZs",
                "Small workloads",
            ],
            pros=[
                "Maintains 66% capacity during AZ failure",
                "Best practice for many AWS services",
                "Enables zonal redundancy patterns",
                "Required for some managed services",
            ],
            cons=[
                "Higher cost (3x NAT, more cross-AZ)",
                "More resources to manage",
                "Not available in all regions",
            ],
            monthly_cost_range=(0, 100.00),
            cost_drivers=[
                "3x NAT Gateways: $97.20/mo",
                "More cross-AZ data transfer",
                "3x AZ-specific resources",
            ],
            soc2_controls=["A1.1", "A1.2"],
            implementation_complexity="low",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for AZ count:

    1. Is this production?
       NO → Single AZ (save costs)
       YES → Continue to 2

    2. What's your availability target?
       99.9% (8.76 hrs downtime/yr) → 2 AZs sufficient
       99.95% (4.38 hrs/yr) → 2-3 AZs
       99.99% (52 min/yr) → 3 AZs minimum

    3. What services are you using?
       EKS → 3 AZs recommended (control plane)
       Aurora → 3 AZs for Multi-AZ cluster
       Standard RDS → 2 AZs sufficient
       ElastiCache → 2-3 AZs per replication group

    Cost impact of cross-AZ traffic:
    - Estimate 10-30% of traffic crosses AZs
    - 1TB total traffic → $10-30/mo cross-AZ cost
    - Design to minimize cross-AZ where possible

    Best practice: Start with 2 AZs, expand to 3 for
    high-criticality workloads or specific service requirements.
    """,
    soc2_relevance="""
    SOC 2 Availability controls:
    - A1.1: Processing capacity to meet commitments
    - A1.2: Recovery infrastructure and processes

    2 AZs meets most SOC 2 availability requirements.
    3 AZs provides stronger availability evidence.
    """,
    common_mistakes=[
        "Using 3 AZs in region with only 2 (deployment fails)",
        "Not accounting for cross-AZ data transfer costs",
        "Assuming cross-AZ is automatic (must configure)",
        "Single AZ for production databases",
        "Not testing AZ failover procedures",
    ],
)


# =============================================================================
# VPC ENDPOINTS PATTERNS
# =============================================================================

VPC_ENDPOINT_PATTERNS = ArchitectureDecision(
    question="Which VPC Endpoints should be deployed?",
    options=[
        DecisionOption(
            name="Gateway Endpoints Only (S3 + DynamoDB)",
            description="Free gateway endpoints for S3 and DynamoDB",
            when_to_use=[
                "Cost optimization priority",
                "Only S3 and DynamoDB access needed",
                "Simple architectures",
                "All workloads",
            ],
            when_not_to_use=[
                "Never - these are always recommended",
            ],
            pros=[
                "Completely free",
                "Keeps traffic off internet",
                "Better performance",
                "No NAT Gateway data charges for S3/DDB",
            ],
            cons=[
                "Only S3 and DynamoDB",
                "Other services still use NAT",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=[
                "Gateway endpoints: FREE",
                "SAVES money by avoiding NAT for S3/DDB traffic",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Essential Interface Endpoints",
            description="Gateway + core interface endpoints (SSM, ECR, Secrets)",
            when_to_use=[
                "Private subnets with no NAT",
                "EC2 instances needing SSM",
                "Container workloads (ECS, EKS)",
                "Security-focused (no internet)",
            ],
            when_not_to_use=[
                "Have NAT and cost is concern",
                "Low AWS API usage",
            ],
            pros=[
                "Enables private-only subnets",
                "No internet required for management",
                "Better security posture",
                "Required for some compliance",
            ],
            cons=[
                "$7.20/mo per endpoint per AZ",
                "Adds up quickly (3 endpoints × 2 AZ = $43.20/mo)",
                "Need to identify which services needed",
            ],
            monthly_cost_range=(21.60, 86.40),
            cost_drivers=[
                "Interface endpoint: $7.20/mo per AZ",
                "Essential set (SSM, SSMMessages, EC2Messages): $21.60/mo (1 AZ)",
                "Add ECR (api + dkr): $14.40/mo per AZ",
                "Add Secrets Manager: $7.20/mo per AZ",
                "Data processing: $0.01/GB",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Comprehensive Interface Endpoints",
            description="Full set of endpoints for air-gapped operations",
            when_to_use=[
                "No NAT Gateway (fully private)",
                "Air-gapped or isolated environments",
                "Strict compliance (FedRAMP, financial)",
                "Zero internet egress requirement",
            ],
            when_not_to_use=[
                "Have NAT Gateway",
                "Cost sensitive",
                "Don't need full isolation",
            ],
            pros=[
                "No internet dependency",
                "Maximum security",
                "All AWS services via private path",
                "Strongest compliance posture",
            ],
            cons=[
                "Expensive ($150-300/mo typical)",
                "Complex to manage all endpoints",
                "Must add new endpoints for new services",
            ],
            monthly_cost_range=(100.00, 300.00),
            cost_drivers=[
                "10-20 endpoints typical",
                "$7.20/mo × 15 endpoints × 2 AZs = $216/mo",
                "Common set: SSM, SSMMessages, EC2Messages, ECR (api+dkr+logs), ",
                "Secrets Manager, KMS, STS, CloudWatch Logs, SNS, SQS",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC6.8"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Centralized Endpoints (via TGW/RAM)",
            description="Shared endpoints in central VPC via Resource Access Manager",
            when_to_use=[
                "Many VPCs needing same endpoints",
                "Cost optimization at scale",
                "Centralized network architecture",
                "10+ VPCs",
            ],
            when_not_to_use=[
                "Few VPCs (< 5)",
                "VPCs don't have TGW connectivity",
                "Need endpoint policies per VPC",
            ],
            pros=[
                "Major cost savings at scale",
                "Single set of endpoints to manage",
                "Centralized DNS resolution",
            ],
            cons=[
                "Requires TGW or VPC peering",
                "Complex DNS configuration",
                "Single point of failure",
                "Traffic routing through hub VPC",
            ],
            monthly_cost_range=(50.00, 200.00),
            cost_drivers=[
                "One set of endpoints instead of N sets",
                "But: TGW data processing for API calls",
                "Break-even: ~5 VPCs typically",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for VPC Endpoints:

    1. ALWAYS deploy Gateway Endpoints (S3 + DynamoDB)
       - Free
       - Saves NAT costs
       - Better performance

    2. Do you have NAT Gateway?
       YES → Interface endpoints are optional (cost vs security)
       NO → You MUST have interface endpoints for AWS services

    3. What workloads do you run?
       EC2/ECS with SSM → SSM, SSMMessages, EC2Messages
       Containers → Add ECR (api, dkr), CloudWatch Logs
       Secrets/Parameters → Secrets Manager, SSM (for params)
       Lambda in VPC → STS, Lambda, + whatever Lambda calls

    4. How many VPCs?
       1-4 VPCs → Endpoints per VPC
       5+ VPCs → Consider centralized endpoints

    Essential endpoints for container workloads:
    - com.amazonaws.region.ecr.api
    - com.amazonaws.region.ecr.dkr
    - com.amazonaws.region.logs (CloudWatch)
    - com.amazonaws.region.s3 (Gateway - free)
    - com.amazonaws.region.ssm (for ECS exec)

    Cost comparison (2 AZs, 10 endpoints):
    - Per-VPC: $144/mo per VPC
    - Centralized (5 VPCs): $144/mo + TGW costs (approx. $180/mo)
    - Break-even: When per-VPC costs exceed shared + TGW
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Private connectivity (no internet)
    - CC6.7: Encrypted transmission (TLS to endpoint)
    - CC6.8: Endpoint policies for access control

    VPC Endpoints demonstrate "private by design" for SOC 2.
    Endpoint policies provide additional access control layer.
    """,
    common_mistakes=[
        "Forgetting Gateway Endpoints (free savings)",
        "Not enabling Private DNS for interface endpoints",
        "Creating endpoints in wrong subnets",
        "Forgetting endpoint security groups",
        "Not using endpoint policies for S3",
    ],
)


# =============================================================================
# VPC FLOW LOGS PATTERNS
# =============================================================================

VPC_FLOW_LOG_PATTERNS = ArchitectureDecision(
    question="How should VPC Flow Logs be configured?",
    options=[
        DecisionOption(
            name="Flow Logs to CloudWatch (Standard)",
            description="VPC Flow Logs delivered to CloudWatch Logs",
            when_to_use=[
                "Real-time analysis needed",
                "CloudWatch Insights queries",
                "Smaller VPCs (lower volume)",
                "Quick troubleshooting priority",
            ],
            when_not_to_use=[
                "High volume traffic (expensive)",
                "Long-term retention (S3 cheaper)",
                "SIEM integration primary use case",
            ],
            pros=[
                "Real-time delivery",
                "CloudWatch Insights integration",
                "Metric filters and alarms",
                "Easy to query",
            ],
            cons=[
                "Expensive at scale ($0.50/GB)",
                "Retention costs add up",
                "30-day practical limit typically",
            ],
            monthly_cost_range=(10.00, 500.00),
            cost_drivers=[
                "Ingestion: $0.50/GB",
                "Storage: $0.03/GB/month",
                "10GB/day = approx. $150/mo ingestion + $9/mo storage",
                "100GB/day = approx. $1500/mo (use S3 instead)",
            ],
            soc2_controls=["CC6.6", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Flow Logs to S3 (Cost-Optimized)",
            description="VPC Flow Logs delivered to S3 bucket",
            when_to_use=[
                "High traffic volume",
                "Long-term retention required",
                "SIEM integration",
                "Cost optimization priority",
                "Compliance requiring 1+ year retention",
            ],
            when_not_to_use=[
                "Real-time analysis critical",
                "Simple CloudWatch queries preferred",
            ],
            pros=[
                "50% cheaper than CloudWatch ($0.25/GB)",
                "Cheap long-term storage (Glacier)",
                "Parquet format for Athena",
                "SIEM integration friendly",
            ],
            cons=[
                "Not real-time (5-10 min delay)",
                "Need Athena or SIEM for analysis",
                "More complex to query",
            ],
            monthly_cost_range=(5.00, 250.00),
            cost_drivers=[
                "Delivery: $0.25/GB (half of CloudWatch)",
                "S3 storage: $0.023/GB/month (Standard)",
                "Athena queries: $5/TB scanned",
                "10GB/day = approx. $75/mo delivery + $7/mo storage",
            ],
            soc2_controls=["CC6.6", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Flow Logs to Both (Hybrid)",
            description="Short-term CloudWatch + Long-term S3",
            when_to_use=[
                "Need real-time AND long-term",
                "Budget allows",
                "Compliance requires both",
                "Different teams need different access",
            ],
            when_not_to_use=[
                "Cost optimization priority",
                "One destination sufficient",
            ],
            pros=[
                "Best of both worlds",
                "Real-time troubleshooting",
                "Long-term compliance storage",
                "Flexible analysis options",
            ],
            cons=[
                "Double the delivery cost",
                "More complex architecture",
                "May be redundant",
            ],
            monthly_cost_range=(15.00, 750.00),
            cost_drivers=[
                "Both CloudWatch and S3 costs",
                "Can optimize with CloudWatch short retention",
                "S3 lifecycle to Glacier after 90 days",
            ],
            soc2_controls=["CC6.6", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Centralized Flow Logs (Organization)",
            description="All VPC Flow Logs to central account",
            when_to_use=[
                "Multi-account environment",
                "Central security team",
                "SIEM aggregation",
                "Compliance requiring central logging",
            ],
            when_not_to_use=[
                "Single account",
                "Decentralized operations",
            ],
            pros=[
                "Single pane of glass",
                "Cross-account correlation",
                "Easier SIEM integration",
                "Central retention policies",
            ],
            cons=[
                "Cross-account delivery setup",
                "Large central bucket to manage",
                "Bucket policies can be complex",
            ],
            monthly_cost_range=(50.00, 1000.00),
            cost_drivers=[
                "Same delivery costs, centralized storage",
                "Potential cross-region transfer costs",
                "Central Athena/SIEM costs",
            ],
            soc2_controls=["CC6.6", "CC7.2", "CC7.3"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for Flow Logs:

    1. What's your monthly traffic volume?
       < 100GB/month → CloudWatch is fine
       100GB-1TB/month → S3 recommended
       > 1TB/month → S3 required (CloudWatch too expensive)

    2. Do you need real-time analysis?
       YES → CloudWatch (or hybrid)
       NO → S3 is sufficient

    3. How long must you retain logs?
       < 30 days → CloudWatch
       30 days - 1 year → S3 Standard
       > 1 year → S3 with Glacier lifecycle

    4. Multi-account environment?
       YES → Centralize to Log Archive account
       NO → Per-VPC configuration

    Best practices:
    - Always enable Flow Logs (required for SOC 2)
    - Use custom format to reduce volume
    - Exclude ENIs you don't need (NAT GW, etc.)
    - Enable Parquet format for S3 (50% smaller)
    - Set up Athena table for queries

    Custom format recommendation (reduces volume ~40%):
    $${version} $${account-id} $${interface-id} $${srcaddr}
    $${dstaddr} $${srcport} $${dstport} $${protocol}
    $${packets} $${bytes} $${start} $${end} $${action} $${log-status}
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Flow logs show network access patterns
    - CC7.2: Monitoring network traffic
    - CC7.3: Evaluating security events

    Flow Logs are ESSENTIAL for SOC 2. Auditors will ask:
    - Where are network logs?
    - How long are they retained?
    - Can you demonstrate analysis of them?

    Minimum: 90 days retention. Recommended: 1 year.
    """,
    common_mistakes=[
        "Not enabling Flow Logs at all",
        "Using default format (verbose, expensive)",
        "No retention policy (storage grows forever)",
        "Not using Parquet for S3 (2x larger files)",
        "Forgetting to set up analysis (logs exist but unused)",
        "Logging everything including NAT GW traffic (expensive)",
    ],
)


def get_vpc_patterns() -> dict:
    """Get all VPC-related patterns."""
    return {
        "cidr_planning": CIDR_PLANNING_PATTERNS,
        "subnet_tiers": SUBNET_TIER_PATTERNS,
        "availability_zones": AVAILABILITY_ZONE_PATTERNS,
        "vpc_endpoints": VPC_ENDPOINT_PATTERNS,
        "flow_logs": VPC_FLOW_LOG_PATTERNS,
    }
