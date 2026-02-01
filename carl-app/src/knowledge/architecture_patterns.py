"""
AWS Architecture Patterns Knowledge Base for CARL.

Contains decision logic and guidance for AWS foundational architecture.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScaleTier(Enum):
    """Organization scale tiers."""
    STARTUP = "startup"       # 1-5 accounts, < 10 VPCs
    GROWTH = "growth"         # 5-20 accounts, 10-50 VPCs
    ENTERPRISE = "enterprise" # 20-100+ accounts, 50+ VPCs


@dataclass
class ArchitectureDecision:
    """Represents an architecture decision with full context."""
    question: str
    options: list["DecisionOption"]
    recommendation_logic: str
    soc2_relevance: str
    common_mistakes: list[str]


@dataclass
class DecisionOption:
    """An option for an architecture decision."""
    name: str
    description: str
    when_to_use: list[str]
    when_not_to_use: list[str]
    pros: list[str]
    cons: list[str]
    monthly_cost_range: tuple[float, float]
    cost_drivers: list[str]
    soc2_controls: list[str]
    implementation_complexity: str  # low, medium, high
    operational_overhead: str       # low, medium, high


# =============================================================================
# EGRESS ARCHITECTURE PATTERNS
# =============================================================================

EGRESS_PATTERNS = ArchitectureDecision(
    question="How should outbound internet traffic be handled?",
    options=[
        DecisionOption(
            name="Distributed NAT (NAT per VPC)",
            description="Each VPC has its own NAT Gateway(s) for outbound traffic",
            when_to_use=[
                "Small number of VPCs (< 5)",
                "VPCs are independent with no shared egress requirements",
                "Simple architecture is preferred",
                "Teams manage their own networking",
                "Low cross-VPC traffic",
            ],
            when_not_to_use=[
                "Need centralized traffic inspection",
                "Compliance requires egress logging in one place",
                "More than 5-10 VPCs (cost becomes significant)",
                "Need consistent egress IP addresses",
            ],
            pros=[
                "Simple to implement and understand",
                "No single point of failure across VPCs",
                "Teams have autonomy",
                "No Transit Gateway costs",
            ],
            cons=[
                "No centralized inspection capability",
                "Costs multiply with each VPC",
                "Multiple egress IPs to whitelist",
                "Inconsistent security posture possible",
            ],
            monthly_cost_range=(32.40, 200.00),  # Per VPC
            cost_drivers=[
                "NAT Gateway: $32.40/mo base per gateway",
                "Data processing: $0.045/GB",
                "Multiply by number of AZs for HA (typically 2-3x)",
                "Each VPC bears full cost",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Centralized NAT (Shared Egress VPC)",
            description="Dedicated egress VPC with NAT Gateways, connected via Transit Gateway",
            when_to_use=[
                "5+ VPCs or growing",
                "Need consistent egress IP addresses",
                "Want to reduce NAT Gateway costs",
                "Preparing for future centralized inspection",
            ],
            when_not_to_use=[
                "Single VPC deployment",
                "VPCs don't need to communicate",
                "Very low egress traffic (< 100GB/mo total)",
            ],
            pros=[
                "Predictable egress IPs",
                "Lower cost at scale (NAT shared)",
                "Foundation for adding inspection later",
                "Centralized logging",
            ],
            cons=[
                "Transit Gateway costs ($36/mo per attachment)",
                "Single egress path (though HA within egress VPC)",
                "More complex routing",
                "Cross-AZ data transfer costs",
            ],
            monthly_cost_range=(150.00, 500.00),  # Base for small deployment
            cost_drivers=[
                "Transit Gateway: $36/mo per VPC attachment",
                "NAT Gateway: $32.40/mo x 3 AZs = $97.20",
                "Data processing: $0.02/GB (TGW) + $0.045/GB (NAT)",
                "Break-even vs distributed: typically 4-5 VPCs",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Centralized Inspection (Network Firewall)",
            description="AWS Network Firewall in egress VPC inspecting all outbound traffic",
            when_to_use=[
                "Compliance requires traffic inspection",
                "Need to block malicious domains/IPs",
                "IDS/IPS capabilities required",
                "Defense in depth is a priority",
                "Regulated industry (finance, healthcare)",
            ],
            when_not_to_use=[
                "Cost is primary concern",
                "Very low traffic volume",
                "No compliance requirement for inspection",
                "Startup/early stage",
            ],
            pros=[
                "Deep packet inspection",
                "Domain/IP filtering",
                "IDS/IPS capabilities",
                "Centralized security policy",
                "Full traffic visibility",
            ],
            cons=[
                "Significant cost (approx. $285/mo per endpoint)",
                "Added latency (minimal but present)",
                "Complexity in rule management",
                "Need 1 endpoint per AZ",
            ],
            monthly_cost_range=(600.00, 2000.00),
            cost_drivers=[
                "Firewall endpoints: $284.40/mo each (need 2-3 for HA)",
                "Data processing: $0.065/GB",
                "Plus Transit Gateway costs",
                "Plus NAT Gateway costs",
                "500GB/mo processed = approx. $32.50 data processing",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC6.8", "CC7.1", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for egress architecture:

    1. Do you have compliance requirements for traffic inspection?
       YES → Centralized Inspection with Network Firewall
       NO → Continue to 2

    2. How many VPCs do you have or plan to have?
       1-3 VPCs → Distributed NAT (simpler, similar cost)
       4-10 VPCs → Centralized NAT (cost savings, consistency)
       10+ VPCs → Centralized NAT (significant savings)

    3. Do you need consistent egress IPs for partner whitelisting?
       YES → Centralized NAT or Inspection
       NO → Either pattern works

    Cost break-even analysis:
    - Distributed: approx. $100/mo per VPC (assuming 2 AZs)
    - Centralized: approx. $150/mo base + $36/mo per VPC
    - Break-even point: ~4 VPCs
    """,
    soc2_relevance="""
    SOC 2 controls addressed:
    - CC6.6: Logical access security measures
    - CC6.7: Transmission security (encrypted, controlled)
    - CC7.2: Monitoring system components

    Centralized egress provides better audit trail and consistent policy enforcement.
    Network Firewall adds IDS/IPS for CC6.8 (malicious software prevention).
    """,
    common_mistakes=[
        "Forgetting cross-AZ data transfer costs ($0.01/GB)",
        "Not accounting for TGW data processing costs",
        "Single NAT Gateway without HA (creates AZ dependency)",
        "Oversizing for future that may never come",
        "Forgetting that TGW attachments are per-account, not per-VPC",
    ],
)


# =============================================================================
# INGRESS ARCHITECTURE PATTERNS
# =============================================================================

INGRESS_PATTERNS = ArchitectureDecision(
    question="How should inbound traffic (internet to applications) be handled?",
    options=[
        DecisionOption(
            name="Distributed Ingress (ALB per VPC)",
            description="Each VPC has its own ALB/NLB for inbound traffic",
            when_to_use=[
                "Applications are independent",
                "Different teams own different apps",
                "No shared WAF rules needed",
                "Simple deployment model",
            ],
            when_not_to_use=[
                "Need centralized WAF management",
                "Many applications sharing similar rules",
                "Want to minimize public endpoints",
            ],
            pros=[
                "Simple to understand",
                "Team autonomy",
                "Failure isolation",
                "No shared components",
            ],
            cons=[
                "Multiple WAF configurations to manage",
                "More public endpoints to secure",
                "Inconsistent security possible",
            ],
            monthly_cost_range=(25.00, 100.00),  # Per ALB
            cost_drivers=[
                "ALB base: $16.20/mo",
                "LCU charges: approx. $10-50/mo depending on traffic",
                "WAF: $5/mo + $1/rule + $0.60/million requests",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Centralized Ingress (Shared ALB/Inspection VPC)",
            description="Central ingress VPC with ALB, WAF, and optional Network Firewall",
            when_to_use=[
                "Consistent WAF rules across applications",
                "Centralized security team manages ingress",
                "Need to minimize public endpoints",
                "Want centralized logging",
            ],
            when_not_to_use=[
                "Teams need full autonomy",
                "Applications have very different requirements",
                "Simple deployment (< 3 apps)",
            ],
            pros=[
                "Centralized WAF management",
                "Fewer public endpoints",
                "Consistent security policy",
                "Easier to audit",
            ],
            cons=[
                "Shared fate (central ALB issues affect all)",
                "More complex routing",
                "May not fit all application patterns",
            ],
            monthly_cost_range=(100.00, 500.00),
            cost_drivers=[
                "Centralized ALB + WAF",
                "Transit Gateway for routing to spoke VPCs",
                "Optional Network Firewall for inspection",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="CloudFront + WAF (Edge-first)",
            description="CloudFront distribution with WAF at edge, ALB as origin",
            when_to_use=[
                "Global user base",
                "Static content + API mix",
                "DDoS protection is priority",
                "Want to reduce origin load",
                "Cost optimization for bandwidth",
            ],
            when_not_to_use=[
                "Purely internal applications",
                "Real-time/WebSocket heavy applications",
                "Single region with local users only",
            ],
            pros=[
                "DDoS protection at edge",
                "Global performance",
                "Reduces origin bandwidth costs",
                "WAF at edge blocks attacks early",
                "Caching reduces origin load",
            ],
            cons=[
                "Additional complexity",
                "Cache invalidation considerations",
                "Not suitable for all traffic types",
                "Origin must still be secured",
            ],
            monthly_cost_range=(50.00, 500.00),  # Highly variable
            cost_drivers=[
                "CloudFront: Based on data transfer and requests",
                "WAF: $5/mo + rules + requests",
                "Often CHEAPER than direct serving for high bandwidth",
                "Shield Advanced: $3,000/mo if needed",
            ],
            soc2_controls=["CC6.6", "CC6.7", "A1.1"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Decision tree for ingress architecture:

    1. Is this a global application with worldwide users?
       YES → CloudFront + WAF at edge
       NO → Continue to 2

    2. Do you need centralized WAF rule management?
       YES → Centralized Ingress VPC
       NO → Continue to 3

    3. How many applications/services?
       1-5, independent → Distributed (ALB per VPC)
       5+, shared rules → Centralized Ingress

    CloudFront often provides cost SAVINGS at scale due to:
    - Cheaper bandwidth than direct serving
    - Reduced origin load
    - Free Shield Standard DDoS protection
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: WAF provides logical access controls
    - CC6.7: HTTPS termination, TLS enforcement
    - A1.1: CloudFront + Shield for availability

    WAF is highly recommended for SOC 2. OWASP Top 10 protection.
    """,
    common_mistakes=[
        "Not using WAF at all (easy SOC 2 win)",
        "WAF at ALB but not CloudFront (attacks hit origin)",
        "Forgetting to secure origin when using CloudFront",
        "Over-engineering for simple use cases",
    ],
)


# =============================================================================
# TRANSIT ARCHITECTURE PATTERNS
# =============================================================================

TRANSIT_PATTERNS = ArchitectureDecision(
    question="How should VPCs communicate with each other?",
    options=[
        DecisionOption(
            name="No Inter-VPC Communication",
            description="VPCs are isolated, no direct communication",
            when_to_use=[
                "VPCs are truly independent",
                "All communication via public APIs",
                "Maximum isolation required",
                "Single VPC deployment",
            ],
            when_not_to_use=[
                "Services need to communicate privately",
                "Shared databases or services",
                "Microservices architecture spanning VPCs",
            ],
            pros=[
                "Maximum isolation",
                "Simplest architecture",
                "No transit costs",
                "Clear security boundaries",
            ],
            cons=[
                "No private communication path",
                "Must use public endpoints",
                "Higher latency for cross-service calls",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["No inter-VPC costs", "May have higher API/data transfer costs"],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="VPC Peering",
            description="Direct peering connections between VPCs",
            when_to_use=[
                "2-5 VPCs that need to communicate",
                "Simple hub-and-spoke or mesh",
                "Low/moderate traffic volume",
                "Cost optimization is priority",
            ],
            when_not_to_use=[
                "More than 5-10 VPCs (management overhead)",
                "Need transitive routing",
                "Overlapping CIDR ranges",
                "Multi-region with many VPCs",
            ],
            pros=[
                "No hourly costs (free to create)",
                "Simple for small deployments",
                "Direct path (low latency)",
                "No single point of failure",
            ],
            cons=[
                "Not transitive (A-B-C doesn't mean A-C)",
                "N*(N-1)/2 connections for full mesh",
                "Management overhead at scale",
                "Cross-region peering costs $0.01/GB",
            ],
            monthly_cost_range=(0, 100.00),  # Just data transfer
            cost_drivers=[
                "No hourly/monthly fee",
                "Cross-AZ data: $0.01/GB each way",
                "Cross-region data: $0.02/GB",
                "Management overhead is the real cost",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="medium",  # Increases with VPC count
        ),
        DecisionOption(
            name="Transit Gateway",
            description="Hub-and-spoke connectivity with AWS Transit Gateway",
            when_to_use=[
                "5+ VPCs",
                "Need transitive routing",
                "Connecting VPCs + VPN + Direct Connect",
                "Centralized network management",
                "Single region with growth plans",
            ],
            when_not_to_use=[
                "1-3 VPCs with simple peering needs",
                "Cost is the primary concern",
                "Multi-region (consider Cloud WAN)",
            ],
            pros=[
                "Transitive routing",
                "Centralized management",
                "Scales to thousands of attachments",
                "Supports VPN and DX attachments",
                "Route tables for segmentation",
            ],
            cons=[
                "$36/mo per VPC attachment",
                "$0.02/GB data processing",
                "Regional (need one per region)",
                "Single point of management",
            ],
            monthly_cost_range=(36.00, 500.00),  # Per region
            cost_drivers=[
                "Attachment: $36/mo per VPC",
                "Data processing: $0.02/GB",
                "Cross-region peering: Additional $0.02/GB",
                "5 VPCs + 500GB/mo = approx. $190/mo",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="AWS Cloud WAN",
            description="Global network with policy-driven management",
            when_to_use=[
                "Multi-region deployment",
                "Global enterprise",
                "Complex routing requirements",
                "Need centralized global policy",
                "50+ VPCs or complex topology",
            ],
            when_not_to_use=[
                "Single region",
                "Simple deployments",
                "Cost sensitivity (similar to TGW but more features)",
            ],
            pros=[
                "Global network management",
                "Policy-driven segmentation",
                "Built-in multi-region",
                "Simplified operations at scale",
            ],
            cons=[
                "Similar cost to TGW",
                "Overkill for simple deployments",
                "Learning curve",
            ],
            monthly_cost_range=(100.00, 2000.00),
            cost_drivers=[
                "Core Network Edge: $36/mo per attachment",
                "Data processing: $0.02/GB",
                "Similar to TGW but with global features",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for transit architecture:

    1. How many VPCs need to communicate?
       0-1 → No inter-VPC needed
       2-4 → VPC Peering (if non-transitive is OK)
       5+ → Transit Gateway

    2. Do you need transitive routing (A→B→C)?
       YES → Transit Gateway or Cloud WAN
       NO → VPC Peering may work

    3. Multi-region deployment?
       YES, complex → Cloud WAN
       YES, simple → TGW per region + peering
       NO → Transit Gateway

    4. Connecting to on-premises?
       YES → Transit Gateway (VPN/DX attachment)
       NO → Either pattern works

    Cost comparison for 5 VPCs, 500GB/mo traffic:
    - VPC Peering (full mesh): approx. $50/mo (just data)
    - Transit Gateway: approx. $190/mo
    - Cloud WAN: approx. $200/mo

    At 10 VPCs, peering management becomes painful.
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Network segmentation via route tables
    - CC6.7: Private connectivity (no internet exposure)
    - CC7.2: Centralized flow logs and monitoring

    Transit Gateway provides better audit capabilities with flow logs.
    """,
    common_mistakes=[
        "Using TGW for 2 VPCs (VPC peering is simpler/cheaper)",
        "Forgetting TGW data processing costs in estimates",
        "Not planning CIDR ranges (overlaps break peering/TGW)",
        "Over-engineering with Cloud WAN for single region",
    ],
)


# =============================================================================
# VPN PATTERNS
# =============================================================================

SITE_TO_SITE_VPN_PATTERNS = ArchitectureDecision(
    question="How should on-premises connectivity be established?",
    options=[
        DecisionOption(
            name="AWS Site-to-Site VPN",
            description="IPsec VPN tunnels from on-premises to AWS",
            when_to_use=[
                "Getting started with hybrid connectivity",
                "Backup for Direct Connect",
                "Low/moderate bandwidth needs (< 1.25 Gbps)",
                "Quick deployment needed",
                "Cost-effective entry point",
            ],
            when_not_to_use=[
                "Need consistent latency",
                "High bandwidth requirements (> 1.25 Gbps)",
                "Latency-sensitive applications",
            ],
            pros=[
                "Quick to set up (hours, not months)",
                "Encrypted by default",
                "No physical infrastructure",
                "Redundant tunnels included",
                "Works with most firewalls",
            ],
            cons=[
                "Internet-dependent (variable latency)",
                "1.25 Gbps max per tunnel",
                "IPsec overhead",
            ],
            monthly_cost_range=(36.00, 150.00),
            cost_drivers=[
                "VPN connection: $36/mo per connection",
                "Data transfer out: $0.09/GB",
                "Redundancy = 2 connections = $72/mo",
                "1TB/mo data = approx. $90 transfer",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Accelerated Site-to-Site VPN",
            description="VPN with AWS Global Accelerator for improved performance",
            when_to_use=[
                "Global offices connecting to AWS",
                "Need better performance than standard VPN",
                "Internet quality is variable",
                "Not ready for Direct Connect",
            ],
            when_not_to_use=[
                "Single location near AWS region",
                "Very cost-sensitive",
                "Direct Connect is feasible",
            ],
            pros=[
                "Better performance than standard VPN",
                "Uses AWS backbone after nearest edge",
                "Improved reliability",
                "Still quick to deploy",
            ],
            cons=[
                "Additional cost (approx. $36/mo per direction)",
                "Still internet-dependent initially",
                "Not as good as Direct Connect",
            ],
            monthly_cost_range=(72.00, 250.00),
            cost_drivers=[
                "VPN connection: $36/mo",
                "Accelerator fee: approx. $36/mo additional",
                "Data transfer premium: $0.015/GB additional",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="AWS Direct Connect",
            description="Dedicated network connection from on-premises to AWS",
            when_to_use=[
                "High bandwidth requirements (1+ Gbps)",
                "Consistent latency needed",
                "Large data transfers",
                "Mission-critical workloads",
                "Long-term commitment",
            ],
            when_not_to_use=[
                "Quick deployment needed (takes weeks/months)",
                "Low bandwidth needs",
                "No colocation facility access",
                "Short-term project",
            ],
            pros=[
                "Consistent, predictable performance",
                "Up to 100 Gbps",
                "Lower data transfer costs",
                "Private connectivity",
                "Bypass internet",
            ],
            cons=[
                "Long lead time (weeks to months)",
                "Requires physical infrastructure",
                "Higher base cost",
                "Need backup (usually VPN)",
            ],
            monthly_cost_range=(220.00, 5000.00),  # Varies widely
            cost_drivers=[
                "Port fee: $0.30/hr (1Gbps) = $216/mo",
                "Port fee: $2.25/hr (10Gbps) = $1,620/mo",
                "Partner/carrier circuit: Varies ($500-5000/mo)",
                "Data transfer: $0.02/GB (much cheaper than internet)",
            ],
            soc2_controls=["CC6.6", "CC6.7", "A1.1"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for on-premises connectivity:

    1. What's your bandwidth requirement?
       < 500 Mbps → AWS VPN is likely sufficient
       500 Mbps - 1.25 Gbps → VPN or entry Direct Connect
       > 1.25 Gbps → Direct Connect needed

    2. How critical is consistent latency?
       Critical (real-time apps) → Direct Connect
       Important but flexible → Accelerated VPN
       Best-effort OK → Standard VPN

    3. Timeline?
       Need it this week → VPN
       Can wait 4-8 weeks → Direct Connect

    4. Budget?
       Minimal → Standard VPN ($36/mo)
       Moderate → Accelerated VPN ($72/mo)
       Can invest → Direct Connect ($500+/mo)

    Best practice: Use VPN as backup for Direct Connect.
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Private network connectivity
    - CC6.7: Encrypted transmission (VPN) or dedicated circuit (DX)
    - A1.1: Redundant connectivity for availability

    All options provide SOC 2 compliant connectivity.
    VPN encryption is automatic; DX can add MACsec for encryption.
    """,
    common_mistakes=[
        "Single VPN connection without redundancy",
        "Underestimating Direct Connect lead time",
        "Forgetting VPN as backup for Direct Connect",
        "Not considering data transfer costs in ROI",
    ],
)


CLIENT_VPN_PATTERNS = ArchitectureDecision(
    question="How should remote users access AWS resources?",
    options=[
        DecisionOption(
            name="AWS Client VPN",
            description="AWS-managed OpenVPN-compatible client VPN",
            when_to_use=[
                "Need managed VPN solution",
                "OpenVPN compatibility required",
                "Integration with AWS IAM/SSO",
                "Moderate user count (< 100)",
            ],
            when_not_to_use=[
                "Very large user count (costs add up)",
                "Need specific VPN features not supported",
                "Already have enterprise VPN solution",
            ],
            pros=[
                "Fully managed by AWS",
                "Integrates with IAM, SSO, AD",
                "OpenVPN compatible clients",
                "Split tunnel support",
                "Authorization rules",
            ],
            cons=[
                "Can get expensive at scale",
                "Per-connection + per-subnet pricing",
                "Limited to OpenVPN protocol",
            ],
            monthly_cost_range=(75.00, 500.00),
            cost_drivers=[
                "Endpoint association: $72/mo per subnet",
                "Active connections: $0.05/hr",
                "10 users × 8hr/day × 22 days = $88/mo",
                "2 subnets + 10 users = approx. $232/mo",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Third-Party VPN (on EC2)",
            description="Run your own VPN server (OpenVPN, WireGuard, etc.)",
            when_to_use=[
                "Need specific VPN features",
                "Cost optimization for many users",
                "Already have VPN expertise",
                "Want WireGuard or other protocols",
            ],
            when_not_to_use=[
                "Want managed solution",
                "No VPN expertise in team",
                "Small user count (AWS Client VPN simpler)",
            ],
            pros=[
                "Lower cost at scale",
                "Full control over features",
                "Protocol flexibility",
                "Can reuse existing licenses",
            ],
            cons=[
                "Self-managed (patching, HA)",
                "Need EC2 instances",
                "More operational overhead",
            ],
            monthly_cost_range=(30.00, 200.00),
            cost_drivers=[
                "EC2 instance: $30-100/mo",
                "Need HA = 2 instances",
                "EBS storage: approx. $5/mo",
                "No per-user fees",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="high",
        ),
        DecisionOption(
            name="AWS Verified Access (Zero Trust)",
            description="Zero-trust access to applications without VPN",
            when_to_use=[
                "Zero-trust architecture",
                "Application-level access (not network)",
                "Integration with identity providers",
                "Modern security approach",
            ],
            when_not_to_use=[
                "Need full network access",
                "Legacy applications",
                "SSH/RDP access required",
            ],
            pros=[
                "No VPN client needed",
                "Per-application access control",
                "Identity-based security",
                "Modern zero-trust approach",
            ],
            cons=[
                "Application-level only",
                "Newer service (less mature)",
                "Requires application changes sometimes",
            ],
            monthly_cost_range=(50.00, 300.00),
            cost_drivers=[
                "Per application endpoint",
                "Per user pricing",
                "Varies by usage pattern",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Decision tree for remote access:

    1. Do users need full network access or just specific apps?
       Full network → VPN (Client VPN or self-managed)
       Specific apps → Consider Verified Access

    2. How many concurrent users?
       < 50 users → AWS Client VPN is simple
       50-500 users → Compare costs (Client VPN vs self-managed)
       500+ users → Self-managed or enterprise solution

    3. Do you have VPN expertise?
       YES → Self-managed may save money
       NO → AWS Client VPN (managed)

    Cost comparison for 50 users, 8hr/day:
    - AWS Client VPN: approx. $500-600/mo
    - Self-managed (2x m5.large): approx. $150/mo

    But self-managed has operational overhead.
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: User authentication
    - CC6.2: Access provisioning
    - CC6.6: Secure remote access
    - CC6.7: Encrypted transmission

    All options provide compliant remote access.
    Verified Access provides best zero-trust alignment.
    """,
    common_mistakes=[
        "Forgetting per-connection costs in estimates",
        "Not setting up split tunnel (full tunnel = high costs)",
        "Single subnet association (no HA)",
        "Not integrating with SSO/identity provider",
    ],
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# =============================================================================
# CLOUDFRONT COMPLIANCE PATTERNS
# =============================================================================

CLOUDFRONT_PATTERNS = ArchitectureDecision(
    question="How should CloudFront be configured for compliance?",
    options=[
        DecisionOption(
            name="CloudFront Standard (Public Content)",
            description="Standard CloudFront distribution for public websites/assets",
            when_to_use=[
                "Public marketing sites",
                "Static assets (images, CSS, JS)",
                "No sensitive data",
                "Global audience",
            ],
            when_not_to_use=[
                "Authenticated content",
                "Sensitive data transmission",
                "Compliance requires origin restriction",
            ],
            pros=[
                "Simple to configure",
                "Global edge caching",
                "DDoS protection (Shield Standard free)",
                "Cost-effective for static content",
            ],
            cons=[
                "No origin access restriction by default",
                "Caching may expose stale data",
                "Origin still accessible directly",
            ],
            monthly_cost_range=(10.00, 200.00),
            cost_drivers=[
                "Data transfer: $0.085/GB (first 10TB)",
                "Requests: $0.0075/10k HTTP, $0.01/10k HTTPS",
                "Heavily dependent on traffic volume",
            ],
            soc2_controls=["CC6.7", "A1.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="CloudFront + OAC (S3 Origin Secured)",
            description="CloudFront with Origin Access Control for S3",
            when_to_use=[
                "S3-hosted content that should only be accessed via CloudFront",
                "Need to prevent direct S3 access",
                "Compliance requires controlled access path",
            ],
            when_not_to_use=[
                "ALB/EC2 origins (use custom headers instead)",
                "Need direct S3 access for some users",
            ],
            pros=[
                "S3 bucket can be completely private",
                "All access through CloudFront (auditable)",
                "Better security posture",
                "Supports KMS encryption",
            ],
            cons=[
                "More complex initial setup",
                "Must use CloudFront for all access",
                "Debugging can be harder",
            ],
            monthly_cost_range=(10.00, 200.00),
            cost_drivers=[
                "Same as standard CloudFront",
                "No additional cost for OAC",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="CloudFront + WAF + Field-Level Encryption",
            description="Full security stack with WAF and encryption",
            when_to_use=[
                "Handling sensitive data (PII, PHI)",
                "HIPAA/PCI-DSS requirements",
                "Need field-level encryption for specific data",
                "Advanced bot protection needed",
            ],
            when_not_to_use=[
                "Simple static sites",
                "No sensitive data handling",
                "Cost is a primary concern",
            ],
            pros=[
                "WAF protection at edge",
                "Field-level encryption for sensitive fields",
                "Bot control capabilities",
                "Comprehensive logging",
            ],
            cons=[
                "Higher cost (WAF + optional bot control)",
                "More complex configuration",
                "Field encryption requires key management",
            ],
            monthly_cost_range=(50.00, 500.00),
            cost_drivers=[
                "WAF: $5/mo + $1/rule + $0.60/million requests",
                "Bot Control: $10/mo + $1/million requests (if enabled)",
                "Field encryption: $0.02/10k requests",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC6.7", "CC6.8"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="CloudFront + Shield Advanced",
            description="Enterprise DDoS protection with SLA",
            when_to_use=[
                "High-value targets for DDoS",
                "Need DDoS cost protection",
                "Require 24/7 DDoS response team access",
                "Enterprise SLA requirements",
            ],
            when_not_to_use=[
                "Shield Standard is sufficient (most cases)",
                "Budget doesn't support $3000/mo",
                "Low-traffic applications",
            ],
            pros=[
                "DDoS cost protection",
                "24/7 DDoS Response Team",
                "Advanced metrics and reporting",
                "WAF included at no extra cost",
            ],
            cons=[
                "$3,000/mo minimum commitment",
                "1-year commitment required",
                "Overkill for most applications",
            ],
            monthly_cost_range=(3000.00, 5000.00),
            cost_drivers=[
                "Shield Advanced: $3,000/mo flat",
                "Data transfer: $0.025/GB above baseline",
                "WAF included",
            ],
            soc2_controls=["CC6.6", "CC6.8", "A1.1", "A1.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Decision tree for CloudFront compliance:

    1. What type of content are you serving?
       Static public content → CloudFront Standard
       S3 private content → CloudFront + OAC
       Sensitive data → CloudFront + WAF + Encryption

    2. Do you handle sensitive data (PII, PHI, financial)?
       YES → Add WAF with managed rules
       YES + field-level sensitive → Add Field-Level Encryption
       NO → Standard WAF optional but recommended

    3. Are you a high-value DDoS target?
       YES, enterprise → Shield Advanced
       NO → Shield Standard (free, automatic)

    Cost-benefit analysis:
    - WAF at edge: approx. $10-50/mo, blocks attacks before origin
    - Shield Standard: Free, sufficient for 99% of cases
    - Shield Advanced: Only if you need SLA/DRT access
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: CloudFront logging provides access audit trail
    - CC6.6: WAF rules enforce access policies
    - CC6.7: HTTPS enforced, TLS 1.2+ required
    - CC6.8: WAF protects against malicious requests
    - A1.1: CDN improves availability, Shield for DDoS

    CloudFront + WAF is a strong SOC 2 story for web applications.
    """,
    common_mistakes=[
        "Forgetting to secure origin (ALB still publicly accessible)",
        "Not enabling logging for compliance evidence",
        "Using TLS 1.0/1.1 (should be 1.2+)",
        "WAF at CloudFront but not at origin ALB",
        "Caching authenticated responses",
    ],
)


# =============================================================================
# LANDING ZONE / CONTROL TOWER PATTERNS
# =============================================================================

LANDING_ZONE_PATTERNS = ArchitectureDecision(
    question="How should your multi-account environment be structured?",
    options=[
        DecisionOption(
            name="Single Account (No Landing Zone)",
            description="All resources in one AWS account",
            when_to_use=[
                "Very early stage startup",
                "Single application/workload",
                "Small team (< 5 people)",
                "Proof of concept",
            ],
            when_not_to_use=[
                "Multiple environments (dev/staging/prod)",
                "Compliance requirements",
                "Team larger than 5 people",
                "Multiple independent applications",
            ],
            pros=[
                "Simplest to manage",
                "No cross-account complexity",
                "Cheapest (no account overhead)",
            ],
            cons=[
                "No blast radius isolation",
                "Hard to separate billing",
                "Permissions become complex",
                "Doesn't scale",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=[
                "No landing zone overhead",
                "All costs in single account",
            ],
            soc2_controls=["CC6.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="AWS Organizations (Manual)",
            description="Multi-account with manual account management",
            when_to_use=[
                "Small multi-account setup (< 10 accounts)",
                "Custom requirements not met by Control Tower",
                "Terraform-first infrastructure approach",
                "Existing manual setup to formalize",
            ],
            when_not_to_use=[
                "Need automated account vending",
                "Prefer AWS-managed guardrails",
                "Large scale (20+ accounts)",
            ],
            pros=[
                "Full control over setup",
                "No Control Tower constraints",
                "Works with existing Terraform",
                "Organizations is free",
            ],
            cons=[
                "Manual guardrail implementation",
                "More operational overhead",
                "No automated account vending",
                "Must build compliance yourself",
            ],
            monthly_cost_range=(50.00, 200.00),
            cost_drivers=[
                "Organizations: Free",
                "CloudTrail org trail: approx. $5/account",
                "Config: approx. $15/account",
                "Security services: approx. $30/account",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="AWS Control Tower",
            description="AWS-managed landing zone with guardrails",
            when_to_use=[
                "Starting fresh with multi-account",
                "Want AWS best practices built-in",
                "Need guardrails for compliance",
                "Moderate scale (5-50 accounts)",
            ],
            when_not_to_use=[
                "Existing complex Organizations setup",
                "Need customizations Control Tower doesn't support",
                "Single account is sufficient",
            ],
            pros=[
                "Pre-configured guardrails",
                "AWS best practices built-in",
                "Account Factory for provisioning",
                "Easier compliance story",
            ],
            cons=[
                "Control Tower is opinionated",
                "Some customizations are difficult",
                "Can't easily remove once enabled",
                "Limited to supported regions",
            ],
            monthly_cost_range=(100.00, 500.00),
            cost_drivers=[
                "Control Tower: Free (underlying services charged)",
                "Mandatory: CloudTrail, Config per account",
                "Typical: approx. $50/account baseline",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6", "CC7.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Control Tower + AFT (Account Factory for Terraform)",
            description="Control Tower with Terraform-based account vending",
            when_to_use=[
                "Terraform-centric organization",
                "Need automated account provisioning",
                "Want custom account baselines",
                "Self-service account vending",
                "Large scale (20+ accounts)",
            ],
            when_not_to_use=[
                "Not using Terraform",
                "Small deployment (< 10 accounts)",
                "Don't need custom baselines",
            ],
            pros=[
                "Infrastructure as Code for accounts",
                "Custom account baselines via Terraform",
                "GitOps workflow for account requests",
                "Scales to hundreds of accounts",
                "Combines Control Tower guardrails + Terraform flexibility",
            ],
            cons=[
                "Most complex to set up",
                "Requires Terraform expertise",
                "AFT pipeline maintenance",
                "~2-4 weeks to implement properly",
            ],
            monthly_cost_range=(200.00, 800.00),
            cost_drivers=[
                "All Control Tower costs",
                "AFT pipeline: CodePipeline, CodeBuild, Lambda",
                "AFT itself: approx. $50-100/mo",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6", "CC7.1", "CC7.2", "CC8.1"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for landing zone:

    1. How many AWS accounts do you need?
       1 account → Single Account (keep it simple)
       2-5 accounts → Organizations (manual) or Control Tower
       5-20 accounts → Control Tower
       20+ accounts → Control Tower + AFT

    2. Are you using Terraform extensively?
       YES + 20+ accounts → Control Tower + AFT
       YES + < 20 accounts → Organizations (manual) or Control Tower
       NO → Control Tower

    3. Do you need automated account provisioning?
       YES → Control Tower + AFT (or custom pipeline)
       NO → Control Tower or Organizations

    4. Compliance requirements?
       Heavy (SOC 2, HIPAA, PCI) → Control Tower (guardrails built-in)
       Light → Any option works

    Typical journey:
    1. Start with Control Tower for multi-account
    2. Add AFT when you need automated provisioning
    3. Customize account baselines as needed
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Account separation for access control
    - CC6.2: IAM Identity Center (SSO) for user management
    - CC6.6: SCPs enforce organization-wide policies
    - CC7.1: Mandatory guardrails detect misconfigurations
    - CC7.2: Centralized logging across accounts
    - CC8.1: IaC for account provisioning (AFT)

    Control Tower provides a strong SOC 2 foundation with:
    - Mandatory guardrails (preventive controls)
    - Detective guardrails (monitoring)
    - Centralized logging (CloudTrail, Config)
    """,
    common_mistakes=[
        "Jumping to Control Tower for 2-3 accounts (overkill)",
        "Not planning OU structure before enabling Control Tower",
        "Forgetting that Control Tower changes are hard to undo",
        "Not budgeting for per-account security service costs",
        "Assuming single account is 'simpler' for compliance (opposite is often true)",
    ],
)


# =============================================================================
# DNS AND ROUTE 53 PATTERNS
# =============================================================================

DNS_PATTERNS = ArchitectureDecision(
    question="How should DNS be architected?",
    options=[
        DecisionOption(
            name="Route 53 Public Hosted Zone",
            description="Standard public DNS hosting",
            when_to_use=[
                "Public-facing domains",
                "Simple DNS requirements",
                "No hybrid DNS needs",
            ],
            when_not_to_use=[
                "Need DNS resolution for on-premises",
                "Private-only DNS",
            ],
            pros=[
                "Simple and reliable",
                "100% SLA",
                "Global anycast",
                "Health checks included",
            ],
            cons=[
                "No private resolution",
                "Must manage records manually or via IaC",
            ],
            monthly_cost_range=(0.50, 10.00),
            cost_drivers=[
                "Hosted zone: $0.50/mo",
                "Queries: $0.40/million (first 1B)",
                "Health checks: $0.50-2.00/check",
            ],
            soc2_controls=["A1.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Route 53 Private Hosted Zone",
            description="Private DNS within VPCs",
            when_to_use=[
                "Internal service discovery",
                "Private endpoints",
                "Multi-VPC private DNS",
            ],
            when_not_to_use=[
                "Public DNS resolution needed",
                "No VPC deployment",
            ],
            pros=[
                "Private DNS resolution",
                "Split-horizon DNS",
                "Associate with multiple VPCs",
            ],
            cons=[
                "VPC-only resolution",
                "Must associate with each VPC",
            ],
            monthly_cost_range=(0.50, 5.00),
            cost_drivers=[
                "Hosted zone: $0.50/mo",
                "Queries: $0.40/million",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Route 53 Resolver (Hybrid DNS)",
            description="DNS resolution between AWS and on-premises",
            when_to_use=[
                "Hybrid cloud with on-premises",
                "Need to resolve on-premises domains from AWS",
                "Need to resolve AWS private zones from on-premises",
            ],
            when_not_to_use=[
                "No on-premises connectivity",
                "No hybrid DNS requirements",
            ],
            pros=[
                "Bi-directional DNS resolution",
                "Integrates with existing on-prem DNS",
                "Centralized DNS management",
            ],
            cons=[
                "Endpoint costs per AZ",
                "Requires VPN/DX connectivity",
                "More complex configuration",
            ],
            monthly_cost_range=(50.00, 200.00),
            cost_drivers=[
                "Inbound endpoints: $0.125/hr per ENI",
                "Outbound endpoints: $0.125/hr per ENI",
                "Need 2 ENIs minimum per endpoint for HA",
                "2 endpoints × 2 ENIs = approx. $180/mo",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for DNS:

    1. Do you have on-premises DNS to integrate with?
       YES → Route 53 Resolver (Hybrid)
       NO → Continue to 2

    2. Do you need private DNS within VPCs?
       YES → Private Hosted Zone
       NO → Public Hosted Zone only

    3. Using multiple VPCs?
       YES → Associate Private Hosted Zone with all VPCs
       YES + Centralized → Consider Route 53 Resolver for forwarding

    Best practices:
    - Always use Private Hosted Zones for internal services
    - Use descriptive names (service.env.internal)
    - Enable query logging for compliance
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Private DNS prevents exposure
    - CC6.7: DNS over HTTPS/TLS available
    - A1.1: Route 53 100% SLA

    Query logging provides audit trail for SOC 2.
    """,
    common_mistakes=[
        "Using public DNS for internal services",
        "Forgetting to associate Private Hosted Zone with new VPCs",
        "Not enabling query logging",
        "Single Resolver endpoint (no HA)",
    ],
)


# =============================================================================
# CENTRAL EGRESS AND INSPECTION PATTERN
# =============================================================================

INSPECTION_PATTERNS = ArchitectureDecision(
    question="How should I implement centralized traffic inspection?",
    options=[
        DecisionOption(
            name="Central Egress with AWS Network Firewall",
            description="Dedicated inspection VPC with AWS Network Firewall for deep packet inspection of all outbound traffic",
            when_to_use=[
                "SOC 2, PCI-DSS, HIPAA compliance required",
                "5+ VPCs with outbound internet traffic",
                "Need IDS/IPS capabilities",
                "Defense-in-depth security posture",
                "URL/domain filtering requirements",
                "Centralized logging mandatory",
                "Consistent egress IPs needed for partner whitelisting",
            ],
            when_not_to_use=[
                "Single VPC with minimal traffic",
                "Startup without compliance requirements",
                "Cost primary constraint (< 500GB/mo egress)",
                "Development/test environments only",
            ],
            pros=[
                "Deep packet inspection (Layer 7)",
                "IDS/IPS capabilities (detect malware, C2 traffic)",
                "Domain and IP filtering",
                "Centralized security policy enforcement",
                "Single logging destination",
                "Consistent egress IP addresses",
                "Protection against data exfiltration",
                "SOC 2 / compliance-ready",
            ],
            cons=[
                "Higher cost ($600-2000/mo base)",
                "Increased complexity (TGW, routing, firewall rules)",
                "Single egress path (though HA within VPC)",
                "Added latency (1-3ms)",
                "Operational overhead for rule management",
            ],
            monthly_cost_range=(600.00, 3500.00),
            cost_drivers=[
                "Transit Gateway: $36/mo per VPC attachment",
                "Network Firewall endpoints: $284.40/mo each (2-3 for HA)",
                "NAT Gateways: $32.40/mo each (2-3 for HA)",
                "Data processing: $0.02/GB (TGW) + $0.065/GB (NFW) + $0.045/GB (NAT)",
                "Small (5 VPCs, 500GB): $900-1000/mo",
                "Medium (10 VPCs, 2TB): $1300-1500/mo",
                "Enterprise (25 VPCs, 10TB): $3000-3500/mo",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC6.8", "CC7.1", "CC7.2", "CC7.3"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Third-Party Firewall Appliances (Palo Alto, Fortinet)",
            description="Enterprise firewalls deployed via Gateway Load Balancer for advanced inspection",
            when_to_use=[
                "Advanced features needed (App-ID, User-ID, SSL decryption)",
                "Existing enterprise firewall licensing",
                "Need unified management with on-prem firewalls",
                "Very large scale (100+ VPCs)",
                "Specific vendor features required",
            ],
            when_not_to_use=[
                "No existing licensing",
                "AWS-native preferred",
                "Limited firewall expertise",
                "Cost-sensitive deployment",
            ],
            pros=[
                "Advanced application awareness",
                "SSL/TLS decryption and inspection",
                "User-based policies (AD integration)",
                "Unified management with on-prem",
                "Mature IPS/IDS capabilities",
                "Advanced threat prevention",
            ],
            cons=[
                "Higher cost ($2000-5000/mo typical)",
                "More complex (appliance management, patching)",
                "Gateway Load Balancer costs",
                "Instance costs for firewall VMs",
                "Vendor lock-in",
            ],
            monthly_cost_range=(2000.00, 5000.00),
            cost_drivers=[
                "Firewall instances: $200-500/mo per instance",
                "Gateway Load Balancer: $16.20/mo + $0.004/GB",
                "Transit Gateway: $36/mo per attachment",
                "NAT Gateways: $32.40/mo each",
                "Vendor licensing: $500-2000/mo",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC6.8", "CC7.1", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
        DecisionOption(
            name="Distributed Inspection (NFW per VPC)",
            description="AWS Network Firewall deployed in each VPC independently",
            when_to_use=[
                "VPCs are completely isolated",
                "No inter-VPC communication needed",
                "Team autonomy important",
                "Avoid single egress path",
            ],
            when_not_to_use=[
                "Many VPCs (cost multiplies)",
                "Need centralized management",
                "Consistent policy enforcement required",
                "Limited networking team",
            ],
            pros=[
                "No Transit Gateway needed",
                "Team independence",
                "Failure isolation",
                "Simpler per-VPC",
            ],
            cons=[
                "Cost multiplies by VPC count",
                "Inconsistent policies possible",
                "More management overhead",
                "Multiple egress IPs",
            ],
            monthly_cost_range=(600.00, 600.00),  # Per VPC
            cost_drivers=[
                "Network Firewall: $568.80/mo (2 endpoints)",
                "NAT Gateways: $64.80/mo (2 gateways)",
                "Per VPC: approx. $650/mo",
                "10 VPCs = $6500/mo vs $1500/mo centralized",
            ],
            soc2_controls=["CC6.6", "CC6.7", "CC6.8"],
            implementation_complexity="medium",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Decision tree for inspection architecture:

    1. Do you have compliance requiring traffic inspection?
       NO → Consider basic centralized egress without inspection
       YES → Continue to 2

    2. Do you have existing enterprise firewall investments?
       YES → Third-party firewall appliances (maintain consistency)
       NO → Continue to 3

    3. How many VPCs do you need to protect?
       1-3 VPCs → Distributed inspection (simpler, similar cost)
       4-10 VPCs → Central egress with AWS Network Firewall
       10+ VPCs → Central egress (significant cost savings)

    4. Do you need advanced features like SSL decryption, App-ID?
       YES → Third-party firewall appliances
       NO → AWS Network Firewall (simpler, AWS-native)

    Cost comparison (10 VPCs):
    - Distributed NFW: approx. $6500/mo
    - Central AWS NFW: approx. $1500/mo
    - Central 3rd-party: approx. $3000/mo
    """,
    soc2_relevance="""
    SOC 2 controls for centralized inspection:

    - CC6.6: Logical access security - Centralized egress control
    - CC6.7: Transmission security - Encrypted traffic inspection
    - CC6.8: Malicious software prevention - IDS/IPS detection
    - CC7.1: Detection of security events - Alert generation
    - CC7.2: System monitoring - Centralized logging
    - CC7.3: Evaluation of infrastructure - Network metrics

    Centralized inspection provides:
    - Single audit trail for all internet traffic
    - Consistent policy enforcement across all workloads
    - Detection of data exfiltration attempts
    - Protection against malware/C2 communication
    - Compliance-ready architecture
    """,
    common_mistakes=[
        "Forgetting return traffic routing (asymmetric routing)",
        "Not planning for IP exhaustion in firewall subnets",
        "Undersizing firewall capacity (throughput limits)",
        "Single NAT Gateway without HA (creates outage)",
        "Not testing failover before production",
        "Overly permissive firewall rules (defeats purpose)",
        "Not monitoring firewall capacity metrics",
        "Forgetting to update TGW routes for new VPCs",
        "Not accounting for cross-AZ data transfer costs",
        "Missing documentation for future troubleshooting",
    ],
)


def get_pattern_by_category(category: str) -> ArchitectureDecision | None:
    """Get architecture pattern by category."""
    patterns = {
        "egress": EGRESS_PATTERNS,
        "ingress": INGRESS_PATTERNS,
        "transit": TRANSIT_PATTERNS,
        "site_to_site_vpn": SITE_TO_SITE_VPN_PATTERNS,
        "client_vpn": CLIENT_VPN_PATTERNS,
        "cloudfront": CLOUDFRONT_PATTERNS,
        "landing_zone": LANDING_ZONE_PATTERNS,
        "dns": DNS_PATTERNS,
        "inspection": INSPECTION_PATTERNS,
    }
    return patterns.get(category)


def get_all_patterns() -> dict[str, ArchitectureDecision]:
    """Get all architecture patterns."""
    return {
        "egress": EGRESS_PATTERNS,
        "ingress": INGRESS_PATTERNS,
        "transit": TRANSIT_PATTERNS,
        "site_to_site_vpn": SITE_TO_SITE_VPN_PATTERNS,
        "client_vpn": CLIENT_VPN_PATTERNS,
        "cloudfront": CLOUDFRONT_PATTERNS,
        "landing_zone": LANDING_ZONE_PATTERNS,
        "dns": DNS_PATTERNS,
        "inspection": INSPECTION_PATTERNS,
    }


def recommend_option(
    pattern: ArchitectureDecision,
    inputs: dict[str, Any],
) -> DecisionOption:
    """
    Recommend an option based on inputs.

    This is a simplified recommendation engine. In production,
    this would have more sophisticated logic.
    """
    # Example logic for egress
    if pattern == EGRESS_PATTERNS:
        vpc_count = int(inputs.get("vpc_count", 1))
        need_inspection = inputs.get("need_inspection", False)

        if need_inspection:
            return pattern.options[2]  # Network Firewall
        elif vpc_count <= 3:
            return pattern.options[0]  # Distributed NAT
        else:
            return pattern.options[1]  # Centralized NAT

    # Default to first option
    return pattern.options[0]
