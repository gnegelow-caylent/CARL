"""
Centralized Security Tooling Patterns for CARL Foundation Builder.

Comprehensive patterns for deploying and managing AWS security services
at scale across multiple accounts.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# SECURITY HUB PATTERNS
# =============================================================================

SECURITY_HUB_PATTERNS = ArchitectureDecision(
    question="How should AWS Security Hub be deployed and configured?",
    options=[
        DecisionOption(
            name="Per-Account Security Hub",
            description="Security Hub enabled independently in each account",
            when_to_use=[
                "Single account",
                "Decentralized security operations",
                "Getting started",
            ],
            when_not_to_use=[
                "Multi-account (use centralized)",
                "Central security team",
                "Compliance requiring aggregation",
            ],
            pros=[
                "Simplest setup",
                "No cross-account configuration",
                "Account teams own their findings",
            ],
            cons=[
                "No central visibility",
                "Duplicated dashboards",
                "Hard to see organization posture",
            ],
            monthly_cost_range=(5.00, 30.00),
            cost_drivers=[
                "Finding ingestion: $0.00003/finding",
                "Security checks: $0.0010/check",
                "Typical account: $5-30/mo",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="low",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Centralized Security Hub (Delegated Admin)",
            description="Security Hub with delegated administrator for organization",
            when_to_use=[
                "Multi-account environment",
                "Central security team",
                "SOC 2 compliance",
                "Unified security posture view",
            ],
            when_not_to_use=[
                "Single account",
                "Fully decentralized operations",
            ],
            pros=[
                "Single pane of glass",
                "Cross-account visibility",
                "Centralized compliance dashboards",
                "Easier to report on org posture",
            ],
            cons=[
                "More complex setup",
                "Central account must be sized for findings",
                "Cross-region configuration if needed",
            ],
            monthly_cost_range=(20.00, 200.00),
            cost_drivers=[
                "Same per-account costs",
                "Plus finding aggregation (minimal)",
                "Cross-region aggregation: Small additional cost",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Security Hub with Custom Insights & Automation",
            description="Full Security Hub with custom insights and auto-remediation",
            when_to_use=[
                "Mature security operations",
                "Auto-remediation desired",
                "Custom compliance requirements",
                "Large organization",
            ],
            when_not_to_use=[
                "Getting started",
                "Simple requirements",
            ],
            pros=[
                "Custom compliance tracking",
                "Automated remediation",
                "Tailored dashboards",
                "Integration with SIEM",
            ],
            cons=[
                "More complex to set up",
                "Custom insights need maintenance",
                "Auto-remediation risk if not careful",
            ],
            monthly_cost_range=(50.00, 500.00),
            cost_drivers=[
                "Base Security Hub costs",
                "Lambda for automation: $1-20/mo",
                "EventBridge rules: Minimal",
                "SIEM integration: Varies",
            ],
            soc2_controls=["CC7.1", "CC7.2", "CC7.3"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Security Hub deployment strategy:

    1. Enable Security Hub in all accounts
       - Use Organizations integration
       - Auto-enable for new accounts

    2. Set up Delegated Administrator
       - Designate Security Tooling or Audit account
       - NOT management account
       - Enable cross-region aggregation

    3. Enable standards based on needs:
       - AWS Foundational Security Best Practices: ALWAYS
       - CIS AWS Foundations Benchmark: Recommended
       - PCI-DSS: If processing payments
       - NIST: If federal/government

    4. Configure integrations:
       - GuardDuty → Security Hub: Built-in
       - Inspector → Security Hub: Built-in
       - Config → Security Hub: Via controls
       - Third-party: As needed

    5. Set up findings workflow:
       - Define severity thresholds for alerts
       - Create custom insights for key metrics
       - Route to SIEM or ticketing system
       - Consider auto-remediation for specific findings

    Controls to enable (minimum for SOC 2):
    - AWS Foundational Security Best Practices
    - Specific controls for your environment

    Controls to consider disabling:
    - Checks for services you don't use
    - Overly noisy checks (tune, don't disable)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.1: Security Hub detects configuration issues
    - CC7.2: Centralized monitoring of security events
    - CC7.3: Analysis of findings

    Security Hub is excellent for SOC 2:
    - Maps findings to compliance frameworks
    - Provides security score trends
    - Demonstrates continuous monitoring
    """,
    common_mistakes=[
        "Enabling in management account as admin (use delegated admin)",
        "Not enabling AWS Foundational Security Best Practices",
        "Ignoring findings (creates noise fatigue)",
        "Not tuning controls for your environment",
        "Missing cross-region findings",
    ],
)


# =============================================================================
# GUARDDUTY PATTERNS
# =============================================================================

GUARDDUTY_PATTERNS = ArchitectureDecision(
    question="How should Amazon GuardDuty be deployed?",
    options=[
        DecisionOption(
            name="GuardDuty with All Data Sources",
            description="Full GuardDuty deployment with all protection features",
            when_to_use=[
                "Production environments",
                "SOC 2 compliance",
                "All accounts (recommended)",
            ],
            when_not_to_use=[
                "Never - GuardDuty should always be enabled",
            ],
            pros=[
                "Comprehensive threat detection",
                "No agents to deploy",
                "Machine learning-based",
                "Minimal false positives",
            ],
            cons=[
                "Cost scales with activity",
                "Can be expensive for high-log accounts",
            ],
            monthly_cost_range=(10.00, 100.00),
            cost_drivers=[
                "CloudTrail events: $4/million events",
                "VPC Flow Logs: $1/GB first 500GB, then tiered",
                "S3 data events: $0.80/million events",
                "EKS audit logs: $1.60/million events",
            ],
            soc2_controls=["CC6.8", "CC7.2", "CC7.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="GuardDuty with Malware Protection",
            description="GuardDuty plus EBS malware scanning",
            when_to_use=[
                "EC2-based workloads",
                "Regulatory requirements for malware scanning",
                "Defense in depth strategy",
            ],
            when_not_to_use=[
                "Serverless-only environments",
                "Already have endpoint protection",
            ],
            pros=[
                "Scans EBS volumes on demand",
                "No agent required",
                "Integrated with GuardDuty findings",
            ],
            cons=[
                "Per-GB scanning cost",
                "Only scans on-demand",
                "Not real-time protection",
            ],
            monthly_cost_range=(10.00, 200.00),
            cost_drivers=[
                "Base GuardDuty costs",
                "Malware scanning: $0.05/GB scanned",
                "100GB scan = $5",
            ],
            soc2_controls=["CC6.8", "CC7.2", "CC7.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="GuardDuty Organization-Wide Deployment",
            description="GuardDuty with delegated admin and auto-enable",
            when_to_use=[
                "Multi-account environments",
                "Central security operations",
                "All organizations (strongly recommended)",
            ],
            when_not_to_use=[
                "Single account",
            ],
            pros=[
                "Automatic enablement for new accounts",
                "Centralized findings",
                "Delegated administrator model",
                "Consistent coverage",
            ],
            cons=[
                "Must configure once per region",
                "Delegated admin account receives all findings",
            ],
            monthly_cost_range=(50.00, 500.00),
            cost_drivers=[
                "Per-account costs aggregate",
                "Cross-region if needed",
                "Typically $10-30/account baseline",
            ],
            soc2_controls=["CC6.8", "CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    GuardDuty deployment strategy:

    1. Enable GuardDuty in ALL accounts, ALL regions
       - Use Organizations integration
       - Set up delegated administrator (Security account)
       - Auto-enable for new accounts

    2. Enable all data sources:
       - CloudTrail management events: Always
       - CloudTrail S3 data events: Recommended
       - VPC Flow Logs: Always
       - DNS logs: Always
       - EKS audit logs: If using EKS
       - S3 protection: Recommended
       - Malware protection: Consider for EC2 workloads

    3. Configure finding notifications:
       - High/Critical → Immediate alert (PagerDuty, etc.)
       - Medium → Daily summary
       - Low → Weekly review

    4. Integrate with Security Hub:
       - Automatic (just enable both)
       - Findings flow to Security Hub

    5. Consider GuardDuty S3 protection:
       - Detects anomalous S3 access
       - Useful for sensitive data buckets
       - Additional cost but valuable

    Finding response workflow:
    1. GuardDuty finding generated
    2. → Security Hub
    3. → EventBridge rule
    4. → Lambda/Step Functions
    5. → Alert or auto-remediation
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.8: GuardDuty detects malicious activity
    - CC7.2: Continuous monitoring of threats
    - CC7.3: Analysis and response to threats

    GuardDuty is ESSENTIAL for SOC 2:
    - Demonstrates proactive threat detection
    - No agent deployment (easy compliance story)
    - AWS machine learning = credible detection
    """,
    common_mistakes=[
        "Not enabling in all regions",
        "Ignoring findings (creates backlog)",
        "Not using delegated admin",
        "Forgetting to enable for new accounts",
        "Not configuring S3 protection for sensitive buckets",
    ],
)


# =============================================================================
# AWS CONFIG PATTERNS
# =============================================================================

CONFIG_PATTERNS = ArchitectureDecision(
    question="How should AWS Config be deployed?",
    options=[
        DecisionOption(
            name="Config with Conformance Packs",
            description="AWS Config with pre-built conformance packs",
            when_to_use=[
                "Quick compliance baseline",
                "SOC 2, CIS, HIPAA, PCI requirements",
                "Most organizations",
            ],
            when_not_to_use=[
                "Very custom compliance requirements",
                "Cost optimization priority (many rules = cost)",
            ],
            pros=[
                "Pre-built compliance mappings",
                "Easy to deploy",
                "Well-documented",
                "AWS maintained",
            ],
            cons=[
                "May include rules you don't need",
                "Cost scales with rules × resources",
                "Some rules may not fit your environment",
            ],
            monthly_cost_range=(15.00, 100.00),
            cost_drivers=[
                "Config items recorded: $0.003 each",
                "Rule evaluations: $0.001 each",
                "Conformance packs: $0.001/evaluation",
                "50 rules × 100 resources = ~$50/mo",
            ],
            soc2_controls=["CC7.1", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Config with Custom Rules",
            description="AWS Config with organization-specific rules",
            when_to_use=[
                "Custom compliance requirements",
                "Organization-specific standards",
                "When conformance packs don't fit",
            ],
            when_not_to_use=[
                "Standard compliance frameworks only",
                "Don't have rule development capacity",
            ],
            pros=[
                "Tailored to your needs",
                "Can enforce internal standards",
                "Flexible",
            ],
            cons=[
                "Must develop and maintain rules",
                "Lambda costs for custom rules",
                "More operational overhead",
            ],
            monthly_cost_range=(30.00, 200.00),
            cost_drivers=[
                "Base Config costs",
                "Lambda for custom rules: $5-30/mo",
                "More rule evaluations",
            ],
            soc2_controls=["CC7.1", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
        DecisionOption(
            name="Config Organization-Wide (Aggregator)",
            description="Config with organization aggregator for central view",
            when_to_use=[
                "Multi-account environments",
                "Central compliance reporting",
                "Auditor access to compliance data",
            ],
            when_not_to_use=[
                "Single account",
            ],
            pros=[
                "Centralized compliance view",
                "Cross-account resource inventory",
                "Single aggregator dashboard",
            ],
            cons=[
                "Aggregator setup complexity",
                "Large data volume in central account",
            ],
            monthly_cost_range=(50.00, 500.00),
            cost_drivers=[
                "Per-account Config costs",
                "Aggregator: Included",
                "Query costs for advanced queries: $0.005/query",
            ],
            soc2_controls=["CC7.1", "CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    AWS Config deployment strategy:

    1. Enable Config in all accounts
       - Record all resource types (initially)
       - Deliver to central S3 bucket
       - Use Organization aggregator

    2. Deploy conformance packs:
       - Operational Best Practices for SOC 2
       - CIS AWS Foundations Benchmark
       - (Add others based on compliance needs)

    3. Configure delivery:
       - S3 bucket in Log Archive account
       - SNS topic for rule violations
       - Retention in S3 with lifecycle

    4. Set up aggregator:
       - Create in Audit/Security account
       - Aggregate from all accounts and regions
       - Use for compliance dashboards

    Recommended conformance packs for SOC 2:
    - Operational-Best-Practices-for-SOC-2
    - Operational-Best-Practices-for-AWS-Identity-and-Access-Management
    - Operational-Best-Practices-for-Encryption-and-Key-Management
    - Operational-Best-Practices-for-Logging

    Cost optimization:
    - Exclude resource types you don't use
    - Disable rules that don't apply
    - Use periodic (vs continuous) for less critical rules
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.1: Config rules detect non-compliance
    - CC7.2: Continuous configuration monitoring
    - CC7.3: Config data enables analysis

    AWS Config is critical for SOC 2:
    - Demonstrates continuous compliance monitoring
    - Provides configuration change history
    - Maps directly to control frameworks
    """,
    common_mistakes=[
        "Recording all resource types forever (costs add up)",
        "Not using conformance packs (reinventing the wheel)",
        "Too many custom rules without maintenance plan",
        "Not setting up aggregator for multi-account",
        "Ignoring non-compliant resources",
    ],
)


# =============================================================================
# INSPECTOR PATTERNS
# =============================================================================

INSPECTOR_PATTERNS = ArchitectureDecision(
    question="How should Amazon Inspector be deployed?",
    options=[
        DecisionOption(
            name="Inspector for EC2 and ECR",
            description="Vulnerability scanning for EC2 instances and container images",
            when_to_use=[
                "EC2-based workloads",
                "Container deployments (ECS, EKS)",
                "Compliance requiring vulnerability scanning",
            ],
            when_not_to_use=[
                "Serverless-only (still scan Lambda)",
                "No compute workloads",
            ],
            pros=[
                "Agentless for EC2 (SSM-based)",
                "Automatic ECR scanning",
                "Continuous scanning",
                "Integration with Security Hub",
            ],
            cons=[
                "Per-instance/image costs",
                "SSM agent required for EC2",
                "Can generate many findings",
            ],
            monthly_cost_range=(10.00, 100.00),
            cost_drivers=[
                "EC2 scanning: $1.258/instance/month",
                "ECR initial scan: $0.09/image",
                "ECR rescan: $0.01/image",
                "Lambda: $0.30/function/month",
            ],
            soc2_controls=["CC6.8", "CC7.1"],
            implementation_complexity="low",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Inspector Organization-Wide",
            description="Inspector with delegated admin across organization",
            when_to_use=[
                "Multi-account environments",
                "Central security team",
                "Consistent vulnerability management",
            ],
            when_not_to_use=[
                "Single account",
            ],
            pros=[
                "Centralized vulnerability view",
                "Automatic enablement for new accounts",
                "Cross-account reporting",
            ],
            cons=[
                "More findings to manage",
                "Costs scale with resources",
            ],
            monthly_cost_range=(50.00, 500.00),
            cost_drivers=[
                "Per-account Inspector costs",
                "Scales with number of resources",
            ],
            soc2_controls=["CC6.8", "CC7.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Inspector deployment strategy:

    1. Enable Inspector in all accounts
       - Use Organizations delegated admin
       - Auto-enable for new accounts

    2. Configure scanning:
       - EC2: Enable for all instances
       - ECR: Enable for all repositories
       - Lambda: Enable for all functions

    3. Set up findings workflow:
       - Critical/High → Immediate remediation
       - Medium → 30-day remediation
       - Low → Risk acceptance or backlog

    4. Integrate with CI/CD:
       - Scan images before pushing to ECR
       - Block deployment of critical vulnerabilities
       - Inspector provides API for programmatic checks

    Best practices:
    - Use suppression rules for accepted risks
    - Create custom exclusions for false positives
    - Track vulnerability metrics over time
    - Set SLAs for remediation by severity
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.8: Vulnerability detection
    - CC7.1: System component monitoring
    - CC7.2: Anomaly and vulnerability detection

    Inspector demonstrates:
    - Proactive vulnerability management
    - Continuous security assessment
    - Remediation tracking
    """,
    common_mistakes=[
        "Not enabling for ECR (containers need scanning)",
        "Ignoring Lambda scanning",
        "No remediation SLAs defined",
        "Not integrating with CI/CD",
        "Alert fatigue from too many findings",
    ],
)


# =============================================================================
# FIREWALL MANAGER PATTERNS
# =============================================================================

FIREWALL_MANAGER_PATTERNS = ArchitectureDecision(
    question="How should AWS Firewall Manager be used?",
    options=[
        DecisionOption(
            name="Firewall Manager for WAF",
            description="Centralized WAF policy management across accounts",
            when_to_use=[
                "Multiple accounts with ALBs/CloudFront",
                "Consistent WAF rules across org",
                "Central security team manages WAF",
            ],
            when_not_to_use=[
                "Single account (manage WAF directly)",
                "Teams manage their own WAF",
            ],
            pros=[
                "Centralized WAF rules",
                "Auto-remediation (apply WAF to new resources)",
                "Consistent protection",
            ],
            cons=[
                "Firewall Manager has its own costs",
                "Less flexibility for individual teams",
            ],
            monthly_cost_range=(100.00, 300.00),
            cost_drivers=[
                "Firewall Manager policy: $100/month per policy per region",
                "Plus underlying WAF costs",
                "WAF: $5/web ACL + $1/rule + $0.60/million requests",
            ],
            soc2_controls=["CC6.6", "CC6.8"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Firewall Manager for Security Groups",
            description="Centralized security group compliance",
            when_to_use=[
                "Need to enforce SG standards",
                "Audit non-compliant security groups",
                "Auto-remediate SG issues",
            ],
            when_not_to_use=[
                "Teams manage SGs independently",
                "Simple SG requirements",
            ],
            pros=[
                "Enforces SG standards org-wide",
                "Detects overly permissive rules",
                "Can auto-remediate",
            ],
            cons=[
                "May conflict with team autonomy",
                "Careful testing required",
            ],
            monthly_cost_range=(100.00, 200.00),
            cost_drivers=[
                "Policy cost: $100/month per policy per region",
            ],
            soc2_controls=["CC6.6", "CC7.1"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Firewall Manager for Network Firewall",
            description="Deploy Network Firewall across accounts via FMS",
            when_to_use=[
                "Need Network Firewall in multiple accounts",
                "Consistent firewall rules org-wide",
                "Centralized inspection strategy",
            ],
            when_not_to_use=[
                "Single inspection VPC (use NFW directly)",
                "Few accounts",
            ],
            pros=[
                "Consistent NFW deployment",
                "Centralized rule management",
                "Compliance enforcement",
            ],
            cons=[
                "FMS + NFW costs add up quickly",
                "Complex to manage",
            ],
            monthly_cost_range=(500.00, 2000.00),
            cost_drivers=[
                "FMS policy: $100/month per policy per region",
                "Network Firewall: $284.40/endpoint/month",
                "Data processing: $0.065/GB",
            ],
            soc2_controls=["CC6.6", "CC6.8", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Firewall Manager decision:

    1. Do you have 5+ accounts with WAF needs?
       YES → FMS for WAF is valuable
       NO → Manage WAF per-account

    2. Do you need to enforce security group standards?
       YES → FMS for Security Groups
       NO → Config rules may be sufficient

    3. Distributed Network Firewall deployment?
       YES → FMS for Network Firewall
       NO → Centralized NFW is simpler

    Firewall Manager setup:
    1. Enable in management account
    2. Designate administrator account
    3. Create policies per service:
       - WAF policies (regional + global)
       - Security Group policies
       - Network Firewall policies (if needed)
    4. Define scope (all accounts or specific OUs)
    5. Configure auto-remediation carefully

    Note: FMS requires AWS Organizations and being
    compliant with FMS prerequisites.
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Centralized network security policies
    - CC6.8: Consistent protection (WAF, NFW)
    - CC7.1: SG compliance monitoring

    FMS demonstrates:
    - Consistent security policy enforcement
    - Central control of network security
    - Automated compliance remediation
    """,
    common_mistakes=[
        "FMS policy in wrong region (regional vs global)",
        "Auto-remediation without testing",
        "Too many policies (gets expensive)",
        "Not scoping policies properly (affects all accounts)",
        "Forgetting the $100/policy/region cost",
    ],
)


# =============================================================================
# DETECTIVE PATTERNS
# =============================================================================

DETECTIVE_PATTERNS = ArchitectureDecision(
    question="Should Amazon Detective be enabled?",
    options=[
        DecisionOption(
            name="Detective for Investigation",
            description="Enable Detective for security investigation",
            when_to_use=[
                "Security team needs investigation capability",
                "Mature security operations",
                "Complex environments to analyze",
            ],
            when_not_to_use=[
                "No dedicated security team",
                "Simple environments",
                "Cost optimization priority",
            ],
            pros=[
                "Deep investigation capability",
                "Visual analysis of findings",
                "Links related entities",
                "90-day data retention",
            ],
            cons=[
                "Cost scales with data volume",
                "Requires GuardDuty/CloudTrail",
                "Learning curve",
            ],
            monthly_cost_range=(10.00, 500.00),
            cost_drivers=[
                "CloudTrail ingestion: $2/GB",
                "VPC Flow Logs ingestion: $2/GB first 10TB",
                "Typically $10-100/account",
            ],
            soc2_controls=["CC7.3", "CC7.4"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Detective deployment:

    1. Prerequisites:
       - GuardDuty must be enabled
       - CloudTrail must be enabled
       - Sufficient data for analysis (48 hours min)

    2. Enable via delegated admin
       - Same admin as GuardDuty typically
       - Auto-enable for member accounts

    3. Use for:
       - GuardDuty finding investigation
       - User behavior analysis
       - Cross-account activity correlation
       - Incident response

    Best for organizations with:
    - Dedicated security analysts
    - Complex multi-account environments
    - Regular incident investigations
    - Need for entity relationship analysis
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.3: Analysis and investigation of events
    - CC7.4: Incident response and investigation

    Detective helps demonstrate:
    - Security event investigation capability
    - Root cause analysis process
    - Entity behavior analysis
    """,
    common_mistakes=[
        "Enabling without GuardDuty",
        "Expecting immediate value (needs 48hr warm-up)",
        "Not training team on usage",
        "Underestimating costs for high-volume accounts",
    ],
)


def get_security_tooling_patterns() -> dict:
    """Get all centralized security tooling patterns."""
    return {
        "security_hub": SECURITY_HUB_PATTERNS,
        "guardduty": GUARDDUTY_PATTERNS,
        "config": CONFIG_PATTERNS,
        "inspector": INSPECTOR_PATTERNS,
        "firewall_manager": FIREWALL_MANAGER_PATTERNS,
        "detective": DETECTIVE_PATTERNS,
    }
