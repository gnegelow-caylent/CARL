"""
Operational Foundation Patterns for CARL Foundation Builder.

Comprehensive patterns for tagging, backup/DR, cost management,
network security, and operational excellence.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# TAGGING STRATEGY PATTERNS
# =============================================================================

TAGGING_STRATEGY_PATTERNS = ArchitectureDecision(
    question="What tagging strategy should be implemented?",
    options=[
        DecisionOption(
            name="Minimal Tags (Cost Only)",
            description="Basic tags for cost allocation",
            when_to_use=[
                "Getting started",
                "Small organization",
                "Cost tracking primary goal",
            ],
            when_not_to_use=[
                "Compliance requirements",
                "Automation needs",
                "Large organization",
            ],
            pros=[
                "Simple to implement",
                "Low overhead",
                "Cost Explorer ready",
            ],
            cons=[
                "Limited visibility",
                "No automation support",
                "Hard to manage at scale",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Tags are free"],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard Tags (AWS Recommended)",
            description="AWS recommended tag set for governance",
            when_to_use=[
                "Most organizations",
                "SOC 2 compliance",
                "Multi-team environments",
            ],
            when_not_to_use=[
                "Very simple environments",
            ],
            pros=[
                "Comprehensive governance",
                "Automation ready",
                "Compliance friendly",
            ],
            cons=[
                "More tags to manage",
                "Enforcement needed",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Tags are free", "Cost is in enforcement tooling"],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Enterprise Tags (Full Governance)",
            description="Comprehensive tagging with automation and enforcement",
            when_to_use=[
                "Large enterprises",
                "Strict compliance",
                "Chargeback requirements",
                "Complex automation needs",
            ],
            when_not_to_use=[
                "Small organizations",
                "Simple environments",
            ],
            pros=[
                "Full visibility",
                "Automated enforcement",
                "Chargeback enabled",
                "Compliance documentation",
            ],
            cons=[
                "Complex to implement",
                "Needs ongoing maintenance",
                "Tag propagation issues",
            ],
            monthly_cost_range=(0, 50.00),
            cost_drivers=[
                "Config rules for tag compliance: $5-20/mo",
                "Lambda for tag enforcement: $1-5/mo",
            ],
            soc2_controls=["CC6.1", "CC7.2", "CC8.1"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Recommended tag schema:

    **Required Tags (enforce via SCP or Config):**
    | Tag | Purpose | Example |
    |-----|---------|---------|
    | Environment | Cost allocation, access control | prod, staging, dev |
    | Owner | Accountability | team-platform |
    | Application | Cost allocation, grouping | order-service |
    | CostCenter | Chargeback | CC-12345 |

    **Recommended Tags:**
    | Tag | Purpose | Example |
    |-----|---------|---------|
    | DataClassification | Security, compliance | confidential, internal |
    | Compliance | Regulatory scope | soc2, hipaa, pci |
    | ManagedBy | IaC tracking | terraform, cloudformation |
    | CreatedBy | Audit trail | arn:aws:iam::...:user/jane |
    | ExpirationDate | Cleanup automation | 2024-12-31 |

    **Automation Tags:**
    | Tag | Purpose | Example |
    |-----|---------|---------|
    | AutoShutdown | Cost savings | true |
    | BackupPolicy | AWS Backup selection | daily |
    | PatchGroup | Systems Manager | prod-linux |

    Tag enforcement methods:
    1. SCPs: Deny resource creation without required tags
    2. Config Rules: Detect non-compliant resources
    3. Tag Policies: Organization-wide tag standardization
    4. Lambda: Auto-remediate missing tags

    Cost allocation tags:
    - Enable in Billing Console
    - Takes 24 hours to activate
    - Retroactive tagging doesn't backfill costs
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Tags enable access control (resource-based policies)
    - CC7.2: Tags enable monitoring and reporting
    - CC8.1: Tags track change management

    Auditors appreciate:
    - Documented tagging policy
    - Evidence of enforcement
    - Reports using tags for compliance scope
    """,
    common_mistakes=[
        "Inconsistent tag values (Prod vs prod vs Production)",
        "No enforcement (tags are optional)",
        "Too many required tags (compliance burden)",
        "Not enabling cost allocation tags",
        "Forgetting tag propagation (ASG, etc.)",
    ],
)


# =============================================================================
# BACKUP AND DR PATTERNS
# =============================================================================

BACKUP_DR_PATTERNS = ArchitectureDecision(
    question="How should backup and disaster recovery be implemented?",
    options=[
        DecisionOption(
            name="AWS Backup Centralized",
            description="AWS Backup with centralized backup vault",
            when_to_use=[
                "Multi-account environments",
                "Compliance requiring backup",
                "Standard RPO/RTO needs",
                "Most organizations",
            ],
            when_not_to_use=[
                "Application-specific backup needs",
                "Very custom RPO/RTO",
            ],
            pros=[
                "Centralized management",
                "Cross-account backup copies",
                "Policy-based scheduling",
                "Compliance reporting",
            ],
            cons=[
                "May not fit all workloads",
                "Vault storage costs",
                "Cross-region copy costs",
            ],
            monthly_cost_range=(20.00, 500.00),
            cost_drivers=[
                "Backup storage: ~$0.05/GB warm, $0.01/GB cold",
                "Cross-region copy: Data transfer + storage",
                "Restore: Data retrieval costs",
            ],
            soc2_controls=["A1.2", "A1.3"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Multi-Region DR (Pilot Light)",
            description="Minimal DR resources in secondary region",
            when_to_use=[
                "RTO of 1-4 hours acceptable",
                "Cost-conscious DR",
                "Data replication primary need",
            ],
            when_not_to_use=[
                "RTO < 1 hour required",
                "Complex failover needs",
            ],
            pros=[
                "Low ongoing cost",
                "Data continuously replicated",
                "Can scale up when needed",
            ],
            cons=[
                "Manual or semi-automated failover",
                "Takes time to scale up",
                "Testing requires coordination",
            ],
            monthly_cost_range=(50.00, 300.00),
            cost_drivers=[
                "Cross-region data replication",
                "Minimal standby resources",
                "DB replica costs",
            ],
            soc2_controls=["A1.2", "A1.3"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Multi-Region DR (Warm Standby)",
            description="Scaled-down but functional environment in DR region",
            when_to_use=[
                "RTO of 15-60 minutes",
                "Mission-critical applications",
                "Budget allows higher DR cost",
            ],
            when_not_to_use=[
                "RTO > 4 hours acceptable",
                "Cost is primary concern",
            ],
            pros=[
                "Faster failover",
                "Environment always running",
                "Easier to test",
            ],
            cons=[
                "Higher ongoing cost",
                "Scaled-down may have issues",
                "Config drift risk",
            ],
            monthly_cost_range=(200.00, 2000.00),
            cost_drivers=[
                "Scaled-down compute (20-50% of prod)",
                "Database replicas",
                "Network costs",
            ],
            soc2_controls=["A1.2", "A1.3"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
        DecisionOption(
            name="Multi-Region Active-Active",
            description="Full capacity in multiple regions",
            when_to_use=[
                "RTO near zero required",
                "Global user base",
                "No tolerance for downtime",
            ],
            when_not_to_use=[
                "Budget constraints",
                "Simple applications",
                "Single-region users",
            ],
            pros=[
                "Highest availability",
                "No failover needed",
                "Global performance",
            ],
            cons=[
                "2x+ infrastructure cost",
                "Complex data consistency",
                "Highest operational overhead",
            ],
            monthly_cost_range=(1000.00, 10000.00),
            cost_drivers=[
                "Full duplicate infrastructure",
                "Global database (DynamoDB Global Tables, Aurora Global)",
                "Cross-region traffic",
            ],
            soc2_controls=["A1.1", "A1.2", "A1.3"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    DR strategy by RTO/RPO:

    | RTO | RPO | Strategy |
    |-----|-----|----------|
    | > 24 hours | > 24 hours | Backup & Restore |
    | 4-24 hours | 1-24 hours | Pilot Light |
    | 1-4 hours | < 1 hour | Warm Standby |
    | < 1 hour | Near zero | Active-Active |

    AWS Backup setup:
    1. Create backup vault in central account
    2. Create backup plans (daily, weekly, monthly)
    3. Assign resources via tags
    4. Configure cross-region copy
    5. Test restores quarterly

    Backup plan recommendations:
    - Daily: 35-day retention
    - Weekly: 3-month retention
    - Monthly: 1-year retention
    - Cross-region: Critical data only

    Resources to backup:
    - EBS volumes
    - RDS databases
    - DynamoDB tables
    - EFS file systems
    - Aurora clusters
    - EC2 instances (AMIs)
    """,
    soc2_relevance="""
    SOC 2 Availability controls:
    - A1.2: Recovery procedures defined
    - A1.3: Recovery testing performed

    Auditors want to see:
    - Documented backup policy
    - Evidence of backup completion
    - Restore test results
    - RPO/RTO definitions
    """,
    common_mistakes=[
        "No cross-region backups",
        "Never testing restores",
        "Backup retention too short",
        "Not backing up all critical data",
        "DR environment config drift",
    ],
)


# =============================================================================
# COST MANAGEMENT PATTERNS
# =============================================================================

COST_MANAGEMENT_PATTERNS = ArchitectureDecision(
    question="How should cost management be implemented?",
    options=[
        DecisionOption(
            name="Basic Cost Visibility",
            description="Cost Explorer and basic budgets",
            when_to_use=[
                "Getting started",
                "Small spend (< $10K/mo)",
                "Simple environment",
            ],
            when_not_to_use=[
                "Large spend",
                "Multiple teams/accounts",
                "Chargeback requirements",
            ],
            pros=[
                "Free (Cost Explorer)",
                "Easy to set up",
                "Good starting point",
            ],
            cons=[
                "Limited granularity",
                "Manual analysis",
                "No chargeback",
            ],
            monthly_cost_range=(0, 10.00),
            cost_drivers=[
                "Cost Explorer: Free",
                "Budgets: First 2 free, then $0.02/budget/day",
            ],
            soc2_controls=[],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard Cost Management",
            description="Full AWS cost tools with budgets and anomaly detection",
            when_to_use=[
                "Multi-account environments",
                "Spend $10K-100K/mo",
                "Need cost accountability",
            ],
            when_not_to_use=[
                "Very small spend",
            ],
            pros=[
                "Anomaly detection",
                "Account-level visibility",
                "RI/SP recommendations",
            ],
            cons=[
                "Some tool costs",
                "Requires governance process",
            ],
            monthly_cost_range=(10.00, 100.00),
            cost_drivers=[
                "Budgets (many): $10-30/mo",
                "Cost Anomaly Detection: Free",
                "Savings Plans analysis: Free",
            ],
            soc2_controls=[],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Enterprise FinOps",
            description="Full FinOps practice with chargeback and optimization",
            when_to_use=[
                "Large spend (> $100K/mo)",
                "Chargeback requirements",
                "Dedicated FinOps team",
            ],
            when_not_to_use=[
                "Small organizations",
                "No FinOps resources",
            ],
            pros=[
                "Full cost accountability",
                "Automated optimization",
                "Chargeback/showback",
            ],
            cons=[
                "Requires FinOps practice",
                "Tool costs",
                "Ongoing effort",
            ],
            monthly_cost_range=(100.00, 1000.00),
            cost_drivers=[
                "Third-party tools (optional): $100-500/mo",
                "AWS CUR storage and processing",
                "Staff time is largest cost",
            ],
            soc2_controls=[],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Cost management setup:

    1. **Enable Cost Tools:**
       - Cost Explorer (free, enable in management account)
       - AWS Budgets (per account and total)
       - Cost Anomaly Detection (free)

    2. **Set Up Budgets:**
       - Organization total budget
       - Per-account budgets
       - Per-service budgets (EC2, RDS, etc.)
       - Alert at 50%, 80%, 100%

    3. **Enable Cost Allocation Tags:**
       - Environment
       - Application
       - CostCenter
       - Owner

    4. **Reserved Instances / Savings Plans:**
       - Analyze stable workloads
       - Start with Compute Savings Plans (flexible)
       - Add EC2 Savings Plans for committed workloads
       - Use RI for RDS, ElastiCache, Redshift

    5. **Cost Optimization:**
       - Rightsizing recommendations
       - Idle resource identification
       - S3 storage class optimization
       - Spot instances where appropriate

    Budget thresholds:
    - 50%: Informational
    - 80%: Warning (review spending)
    - 100%: Alert (take action)
    - 120%: Critical (immediate action)
    """,
    soc2_relevance="""
    While not directly a SOC 2 control, cost management
    supports operational excellence and demonstrates
    mature governance practices.
    """,
    common_mistakes=[
        "No budgets set",
        "Cost allocation tags not enabled",
        "Not using Savings Plans for stable workloads",
        "Ignoring rightsizing recommendations",
        "No cost review process",
    ],
)


# =============================================================================
# NETWORK SECURITY PATTERNS
# =============================================================================

NETWORK_SECURITY_PATTERNS = ArchitectureDecision(
    question="How should network security controls be implemented?",
    options=[
        DecisionOption(
            name="Security Groups (Application-Centric)",
            description="Security groups organized by application/service",
            when_to_use=[
                "Microservices architecture",
                "Clear service boundaries",
                "Team-owned services",
            ],
            when_not_to_use=[
                "Traditional tier-based architecture",
                "Central network team manages all",
            ],
            pros=[
                "Clear ownership",
                "Service-specific rules",
                "Self-service for teams",
            ],
            cons=[
                "More SGs to manage",
                "Potential rule sprawl",
                "Cross-service complexity",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Security Groups are free"],
            soc2_controls=["CC6.6"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Security Groups (Tier-Based)",
            description="Security groups organized by tier (web, app, data)",
            when_to_use=[
                "Traditional three-tier architecture",
                "Central network management",
                "Simple application patterns",
            ],
            when_not_to_use=[
                "Microservices",
                "Many diverse applications",
            ],
            pros=[
                "Simple to understand",
                "Fewer SGs",
                "Traditional model",
            ],
            cons=[
                "Less granular",
                "May over-permit",
                "Doesn't scale to many apps",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Security Groups are free"],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Security Groups + NACLs (Defense in Depth)",
            description="Layered security with both SGs and Network ACLs",
            when_to_use=[
                "High security environments",
                "Compliance requiring layers",
                "Subnet-level blocking needed",
            ],
            when_not_to_use=[
                "Simple environments",
                "When SGs alone are sufficient",
            ],
            pros=[
                "Defense in depth",
                "Subnet-level deny rules",
                "Compliance checkbox",
            ],
            cons=[
                "More complex",
                "NACLs are stateless",
                "Harder to troubleshoot",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["NACLs are free"],
            soc2_controls=["CC6.6", "CC6.8"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Security Group best practices:

    1. **Naming convention:**
       - {app}-{tier}-{purpose}
       - Example: orderservice-app-ecs

    2. **Rule principles:**
       - Never use 0.0.0.0/0 for ingress (except ALB)
       - Reference other SGs, not CIDR blocks
       - Document purpose of each rule
       - Use description field

    3. **Common SG patterns:**
       - ALB SG: Allow 443 from 0.0.0.0/0
       - App SG: Allow from ALB SG only
       - DB SG: Allow from App SG only

    4. **When to use NACLs:**
       - Block known bad IPs at subnet level
       - Compliance requires network-layer control
       - Emergency blocking (faster than SG)
       - Generally: Don't use unless required

    SG reference pattern:
    ```
    [ALB SG] ──allows──> [App SG] ──allows──> [DB SG]

    ALB SG rules:
    - Inbound: 443 from 0.0.0.0/0
    - Outbound: App SG port

    App SG rules:
    - Inbound: App port from ALB SG
    - Outbound: DB port to DB SG, 443 to 0.0.0.0/0

    DB SG rules:
    - Inbound: DB port from App SG
    - Outbound: None (or responses)
    ```
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: Network access controls

    Security Groups are key evidence for:
    - Network segmentation
    - Least privilege network access
    - Defense in depth (with NACLs)
    """,
    common_mistakes=[
        "0.0.0.0/0 inbound rules",
        "Using IP addresses instead of SG references",
        "No rule descriptions",
        "Overly permissive outbound rules",
        "Not using prefix lists for AWS services",
    ],
)


# =============================================================================
# SYSTEMS MANAGER PATTERNS
# =============================================================================

SYSTEMS_MANAGER_PATTERNS = ArchitectureDecision(
    question="How should AWS Systems Manager be configured?",
    options=[
        DecisionOption(
            name="SSM for Instance Management",
            description="Systems Manager for EC2 management and patching",
            when_to_use=[
                "EC2-based workloads",
                "Need remote access without SSH",
                "Patch management needs",
            ],
            when_not_to_use=[
                "Serverless-only",
                "Container-only (ECS/EKS)",
            ],
            pros=[
                "No bastion hosts needed",
                "Centralized patching",
                "Session logging",
                "No inbound ports",
            ],
            cons=[
                "SSM agent required",
                "IAM configuration needed",
                "VPC endpoints if no NAT",
            ],
            monthly_cost_range=(0, 20.00),
            cost_drivers=[
                "SSM: Free tier generous",
                "Session Manager: Free",
                "Patch Manager: Free",
                "Automation: $0.00003/step/resource",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="SSM Full Suite",
            description="Complete Systems Manager deployment",
            when_to_use=[
                "Large EC2 fleet",
                "Compliance requirements",
                "Configuration management",
            ],
            when_not_to_use=[
                "Small, simple environments",
                "Container-first architecture",
            ],
            pros=[
                "Complete management solution",
                "State Manager for config",
                "OpsCenter for operations",
                "Parameter Store for config",
            ],
            cons=[
                "Learning curve",
                "Setup complexity",
            ],
            monthly_cost_range=(0, 100.00),
            cost_drivers=[
                "Most features free",
                "Advanced Parameter Store: $0.05/10K API calls",
                "OpsCenter: Based on OpsItems",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC7.1", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Systems Manager setup:

    1. **Prerequisites:**
       - SSM Agent installed (default on Amazon Linux 2+)
       - IAM role with SSM permissions
       - Network path (NAT or VPC endpoints)

    2. **Core features to enable:**
       - Session Manager (replace SSH)
       - Patch Manager (automated patching)
       - Inventory (track installed software)
       - State Manager (enforce configuration)

    3. **Session Manager setup:**
       - Enable logging to CloudWatch/S3
       - Configure KMS encryption
       - Set idle session timeout
       - Restrict via IAM policies

    4. **Patch management:**
       - Create patch baselines
       - Define maintenance windows
       - Test patches in dev first
       - Configure notifications

    Required VPC endpoints (if no NAT):
    - ssm
    - ssmmessages
    - ec2messages

    Session Manager benefits:
    - No SSH keys to manage
    - No bastion hosts
    - All sessions logged
    - IAM-based access control
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Session Manager access via IAM
    - CC6.6: No inbound ports required
    - CC7.1: Patch compliance tracking
    - CC7.2: Session logging

    SSM provides:
    - Audited access to instances
    - Compliance evidence for patching
    - Configuration baselines
    """,
    common_mistakes=[
        "Using SSH instead of Session Manager",
        "No session logging enabled",
        "Missing VPC endpoints (sessions fail)",
        "IAM role without required permissions",
        "Not testing patches before production",
    ],
)


def get_operational_patterns() -> dict:
    """Get all operational foundation patterns."""
    return {
        "tagging": TAGGING_STRATEGY_PATTERNS,
        "backup_dr": BACKUP_DR_PATTERNS,
        "cost_management": COST_MANAGEMENT_PATTERNS,
        "network_security": NETWORK_SECURITY_PATTERNS,
        "systems_manager": SYSTEMS_MANAGER_PATTERNS,
    }
