"""
AWS Account Structure and Organization Patterns for CARL Foundation Builder.

Comprehensive patterns for multi-account architecture, OU design,
and account baseline configurations.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# ORGANIZATIONAL UNIT (OU) STRUCTURE PATTERNS
# =============================================================================

OU_STRUCTURE_PATTERNS = ArchitectureDecision(
    question="How should the AWS Organization OU structure be designed?",
    options=[
        DecisionOption(
            name="Flat Structure (Root + Workloads)",
            description="Minimal OU structure with workloads directly under root",
            when_to_use=[
                "Very small organization (< 10 accounts)",
                "Getting started with Organizations",
                "Simple governance requirements",
            ],
            when_not_to_use=[
                "Need differentiated policies by environment",
                "Multiple teams with different requirements",
                "Compliance requiring separation",
            ],
            pros=[
                "Simplest to manage",
                "Quick to set up",
                "Easy to understand",
            ],
            cons=[
                "Limited policy granularity",
                "All accounts get same SCPs",
                "Hard to scale",
                "No environment separation",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Organizations is free", "Cost is in account resources"],
            soc2_controls=["CC6.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Environment-Based OUs",
            description="OUs organized by environment (Prod, Staging, Dev, Sandbox)",
            when_to_use=[
                "Clear environment separation needed",
                "Different policies per environment",
                "10-50 accounts",
                "Multiple teams, similar workloads",
            ],
            when_not_to_use=[
                "Need team/business unit separation",
                "Complex compliance requirements",
                "Very large organizations",
            ],
            pros=[
                "Clear environment boundaries",
                "Easy to apply environment-specific SCPs",
                "Intuitive structure",
                "Good for most organizations",
            ],
            cons=[
                "Doesn't scale to 100+ accounts well",
                "Mixing workload types in same OU",
                "May need restructuring as you grow",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Organizations is free"],
            soc2_controls=["CC6.1", "CC6.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="AWS Recommended OU Structure",
            description="AWS best practice OU hierarchy with Security, Infrastructure, Workloads",
            when_to_use=[
                "Following AWS Well-Architected",
                "Using Control Tower",
                "20+ accounts",
                "Enterprise organizations",
                "SOC 2 / compliance requirements",
            ],
            when_not_to_use=[
                "Very small deployments (< 10 accounts)",
                "Simplicity is paramount",
            ],
            pros=[
                "AWS recommended pattern",
                "Control Tower compatible",
                "Clear separation of concerns",
                "Scales to hundreds of accounts",
                "Compliance-friendly",
            ],
            cons=[
                "More complex initial setup",
                "More OUs to manage",
                "May be overkill for small orgs",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Organizations is free"],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Business Unit + Environment OUs",
            description="Nested OUs: Business Units containing Environment OUs",
            when_to_use=[
                "Large enterprise with multiple BUs",
                "BUs have different compliance needs",
                "Chargeback by business unit",
                "100+ accounts",
            ],
            when_not_to_use=[
                "Single business unit",
                "Uniform compliance requirements",
                "Small organizations",
            ],
            pros=[
                "Maximum flexibility",
                "BU-specific policies possible",
                "Clear cost attribution",
                "Scales to largest enterprises",
            ],
            cons=[
                "Most complex structure",
                "Deep nesting can be confusing",
                "SCP inheritance complexity",
                "Harder to maintain",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Organizations is free"],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Decision tree for OU structure:

    1. How many accounts do you expect?
       < 10 accounts → Flat or Environment-based
       10-50 accounts → Environment-based or AWS Recommended
       50+ accounts → AWS Recommended or BU-based

    2. Do you use AWS Control Tower?
       YES → Use AWS Recommended (it creates this)
       NO → Any pattern works

    3. Do you have multiple business units with different needs?
       YES → Consider BU-based structure
       NO → Environment-based is simpler

    AWS Recommended OU Structure:
    ```
    Root
    ├── Security OU
    │   ├── Log Archive (centralized logs)
    │   ├── Audit (security tooling, read-only)
    │   └── Security Tooling (GuardDuty admin, etc.)
    ├── Infrastructure OU
    │   ├── Network (Transit Gateway, DNS)
    │   └── Shared Services (CI/CD, artifacts)
    ├── Workloads OU
    │   ├── Production OU
    │   │   └── [workload accounts]
    │   ├── Staging OU
    │   │   └── [workload accounts]
    │   └── Development OU
    │       └── [workload accounts]
    ├── Sandbox OU
    │   └── [individual sandbox accounts]
    ├── Policy Staging OU (test SCPs)
    └── Suspended OU (decommissioned accounts)
    ```

    Start simple, restructure later if needed.
    Moving accounts between OUs is straightforward.
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Account structure enables access control
    - CC6.2: User access managed through OU policies
    - CC6.6: Logical segmentation via account boundaries

    OU structure provides:
    - Environment isolation (prod vs dev)
    - Policy inheritance (SCPs)
    - Audit boundaries
    """,
    common_mistakes=[
        "Creating too many OUs initially",
        "Putting management account in an OU (should stay at root)",
        "Not planning for Suspended OU",
        "Forgetting Policy Staging OU for testing SCPs",
        "Deep nesting that makes SCP inheritance confusing",
    ],
)


# =============================================================================
# CORE ACCOUNTS PATTERNS
# =============================================================================

CORE_ACCOUNTS_PATTERNS = ArchitectureDecision(
    question="Which core/foundation accounts are needed?",
    options=[
        DecisionOption(
            name="Minimal Core (Log Archive Only)",
            description="Just a centralized log archive account",
            when_to_use=[
                "Very small organization (< 5 accounts)",
                "Getting started",
                "Cost optimization priority",
            ],
            when_not_to_use=[
                "Compliance requirements",
                "Need security tooling separation",
                "10+ accounts",
            ],
            pros=[
                "Simplest setup",
                "Lowest overhead",
                "Quick to implement",
            ],
            cons=[
                "Limited separation of duties",
                "Security tooling in workload accounts",
                "May not meet compliance",
            ],
            monthly_cost_range=(20.00, 100.00),
            cost_drivers=[
                "Log storage (S3): $20-50/mo",
                "Minimal compute in core account",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard Core (Log + Audit + Network)",
            description="Core accounts for logging, security audit, and networking",
            when_to_use=[
                "10-50 accounts",
                "SOC 2 compliance",
                "Centralized networking (TGW)",
                "Most organizations",
            ],
            when_not_to_use=[
                "Very small (< 5 accounts)",
                "No compliance requirements",
            ],
            pros=[
                "Clear separation of duties",
                "Centralized security visibility",
                "Meets SOC 2 requirements",
                "Scalable foundation",
            ],
            cons=[
                "More accounts to manage",
                "Higher base cost",
                "More complex networking",
            ],
            monthly_cost_range=(100.00, 500.00),
            cost_drivers=[
                "Log Archive: S3 storage ($50-200/mo)",
                "Audit: Security Hub, minimal compute ($30-100/mo)",
                "Network: TGW, NAT, DNS ($100-300/mo)",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Full Core (AWS Recommended)",
            description="Complete set of core accounts per AWS best practices",
            when_to_use=[
                "50+ accounts",
                "Enterprise compliance",
                "Multiple security tools",
                "Shared services needed",
                "Control Tower deployment",
            ],
            when_not_to_use=[
                "Small organizations",
                "Cost is primary concern",
            ],
            pros=[
                "AWS best practice",
                "Maximum separation of duties",
                "Scales to enterprise",
                "Control Tower compatible",
            ],
            cons=[
                "Many accounts to manage",
                "Higher cost",
                "More complex",
            ],
            monthly_cost_range=(300.00, 1500.00),
            cost_drivers=[
                "Log Archive: $50-200/mo",
                "Audit: $30-100/mo",
                "Security Tooling: $50-200/mo",
                "Network Hub: $200-500/mo",
                "Shared Services: $50-200/mo",
                "Backup: $50-200/mo",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6", "CC7.2", "CC7.3", "CC8.1"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Decision tree for core accounts:

    1. How many workload accounts will you have?
       1-5 → Minimal (Log Archive only)
       5-20 → Standard (Log + Audit + Network)
       20+ → Full core account set

    2. Do you have SOC 2 or other compliance requirements?
       YES → Minimum Standard core
       NO → Minimal may be sufficient

    3. Are you using Transit Gateway / centralized networking?
       YES → Need Network account
       NO → Can skip initially

    Recommended Core Accounts:

    1. **Log Archive** (Required)
       - Centralized CloudTrail logs
       - VPC Flow Logs from all accounts
       - Config snapshots
       - Application logs
       - Access: Write-only from other accounts, read by security

    2. **Audit / Security Audit** (Highly Recommended)
       - Read-only access to all accounts
       - Security Hub delegated admin
       - Cross-account security queries
       - Access: Security team read-only everywhere

    3. **Security Tooling** (Recommended for 20+ accounts)
       - GuardDuty delegated admin
       - Detective
       - Inspector delegated admin
       - Macie delegated admin
       - Security automation

    4. **Network Hub** (If using TGW)
       - Transit Gateway owner
       - Centralized egress VPC
       - DNS resolution (Route 53 Resolver)
       - Network Firewall
       - Direct Connect termination

    5. **Shared Services** (Optional)
       - CI/CD pipelines
       - Artifact repositories (ECR, CodeArtifact)
       - Shared AMIs
       - Internal tools

    6. **Backup** (Optional)
       - AWS Backup vault
       - Cross-account backup copies
       - DR coordination
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Account separation enforces access control
    - CC6.2: Dedicated audit account for security team
    - CC6.6: Network account for centralized controls
    - CC7.2: Log Archive for centralized monitoring
    - CC7.3: Audit account for security analysis
    - CC8.1: Shared Services for change management

    Core accounts demonstrate separation of duties to auditors.
    Log Archive is essential - auditors will ask for it.
    """,
    common_mistakes=[
        "Skipping Log Archive (required for compliance)",
        "Running security tools in management account",
        "Not restricting Log Archive access (should be write-only)",
        "Putting workloads in core accounts",
        "Not using delegated admin for security services",
    ],
)


# =============================================================================
# ACCOUNT BASELINE PATTERNS
# =============================================================================

ACCOUNT_BASELINE_PATTERNS = ArchitectureDecision(
    question="What should be included in every account baseline?",
    options=[
        DecisionOption(
            name="Minimal Baseline",
            description="Essential security configurations only",
            when_to_use=[
                "Cost optimization priority",
                "Development/sandbox accounts",
                "Getting started",
            ],
            when_not_to_use=[
                "Production accounts",
                "Compliance requirements",
            ],
            pros=[
                "Lowest cost",
                "Quick to deploy",
                "Minimal overhead",
            ],
            cons=[
                "Limited visibility",
                "May not meet compliance",
                "Manual security responses",
            ],
            monthly_cost_range=(10.00, 30.00),
            cost_drivers=[
                "CloudTrail (org trail shared): ~$5/mo",
                "Config (basic rules): ~$10-20/mo",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard Baseline (SOC 2 Ready)",
            description="Comprehensive baseline meeting SOC 2 requirements",
            when_to_use=[
                "Production accounts",
                "SOC 2 compliance",
                "Most workload accounts",
            ],
            when_not_to_use=[
                "Sandbox accounts (use minimal)",
                "Cost is primary concern",
            ],
            pros=[
                "Meets SOC 2 requirements",
                "Good security visibility",
                "Automated threat detection",
                "Industry standard",
            ],
            cons=[
                "Higher per-account cost",
                "More alerts to manage",
            ],
            monthly_cost_range=(40.00, 100.00),
            cost_drivers=[
                "CloudTrail: $5/mo (org trail share)",
                "Config: $15-30/mo",
                "GuardDuty: $10-30/mo",
                "Security Hub: $5-10/mo",
            ],
            soc2_controls=["CC6.6", "CC6.8", "CC7.1", "CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Enterprise Baseline",
            description="Full security stack with all detective controls",
            when_to_use=[
                "High-security environments",
                "Regulated industries",
                "HIPAA, PCI, FedRAMP",
                "Enterprise production",
            ],
            when_not_to_use=[
                "Cost sensitive",
                "Non-production accounts",
                "Small organizations",
            ],
            pros=[
                "Maximum security coverage",
                "All AWS security services",
                "Meets strictest compliance",
            ],
            cons=[
                "High per-account cost",
                "Many alerts to manage",
                "Complex to maintain",
            ],
            monthly_cost_range=(80.00, 200.00),
            cost_drivers=[
                "Standard baseline: $50-80/mo",
                "Inspector: $10-30/mo",
                "Macie: $10-50/mo (depends on S3 scanning)",
                "IAM Access Analyzer: $1-5/mo",
            ],
            soc2_controls=["CC6.1", "CC6.6", "CC6.8", "CC7.1", "CC7.2", "CC7.3"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Decision tree for account baseline:

    1. What type of account is this?
       Sandbox/Dev → Minimal baseline
       Staging → Standard baseline
       Production → Standard or Enterprise baseline

    2. What compliance requirements apply?
       None → Minimal or Standard
       SOC 2 → Standard minimum
       HIPAA/PCI/FedRAMP → Enterprise

    Account Baseline Components:

    **Always Include (All Accounts):**
    - CloudTrail logging (via org trail)
    - S3 Block Public Access (account-level)
    - EBS default encryption
    - IMDSv2 required
    - IAM password policy

    **Standard Baseline Adds:**
    - AWS Config with conformance packs
    - GuardDuty
    - Security Hub
    - VPC Flow Logs
    - IAM Access Analyzer

    **Enterprise Baseline Adds:**
    - Amazon Inspector
    - Amazon Macie (for S3 scanning)
    - Detective (security investigation)
    - Custom Config rules
    - Enhanced logging

    Implementation via:
    - Control Tower (automatic)
    - AFT customizations
    - Terraform modules
    - CloudFormation StackSets
    """,
    soc2_relevance="""
    SOC 2 controls addressed by baseline:

    - CC6.1: IAM password policy, MFA requirements
    - CC6.6: S3 Block Public Access, default encryption
    - CC6.8: GuardDuty threat detection
    - CC7.1: Config rules for compliance monitoring
    - CC7.2: CloudTrail, VPC Flow Logs
    - CC7.3: Security Hub aggregation

    Standard baseline is minimum for SOC 2 production accounts.
    """,
    common_mistakes=[
        "Different baselines with no documentation",
        "Forgetting to enable services in new accounts",
        "Not using org-level features (org trail, delegated admin)",
        "Manual baseline deployment (use automation)",
        "Not testing baseline in staging first",
    ],
)


# =============================================================================
# SERVICE CONTROL POLICY (SCP) PATTERNS
# =============================================================================

SCP_PATTERNS = ArchitectureDecision(
    question="Which Service Control Policies should be implemented?",
    options=[
        DecisionOption(
            name="Minimal SCPs (Guardrails Only)",
            description="Basic preventive controls only",
            when_to_use=[
                "Getting started with SCPs",
                "High trust environment",
                "Development-focused organization",
            ],
            when_not_to_use=[
                "Strict compliance requirements",
                "Low-trust environment",
                "Production workloads with regulations",
            ],
            pros=[
                "Won't break workloads",
                "Easy to implement",
                "Minimal operational impact",
            ],
            cons=[
                "Limited protection",
                "Security relies on IAM alone",
                "May not satisfy auditors",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["SCPs are free"],
            soc2_controls=["CC6.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard SCPs (AWS Recommended)",
            description="AWS recommended preventive and detective guardrails",
            when_to_use=[
                "SOC 2 compliance",
                "Production environments",
                "Multi-team organizations",
                "Control Tower deployments",
            ],
            when_not_to_use=[
                "Need maximum flexibility",
                "Very small organization",
            ],
            pros=[
                "AWS best practices",
                "Control Tower compatible",
                "Good security posture",
                "Well-documented",
            ],
            cons=[
                "May block some legitimate uses",
                "Need exception process",
                "Testing required before rollout",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["SCPs are free"],
            soc2_controls=["CC6.1", "CC6.6", "CC6.8"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Strict SCPs (Defense in Depth)",
            description="Comprehensive deny-by-default with explicit allows",
            when_to_use=[
                "Highly regulated environments",
                "Zero-trust approach",
                "FedRAMP, HIPAA, financial",
                "External threat model",
            ],
            when_not_to_use=[
                "Developer productivity priority",
                "Rapidly changing environments",
                "Without proper exception process",
            ],
            pros=[
                "Maximum protection",
                "Deny-by-default model",
                "Strong compliance posture",
            ],
            cons=[
                "Can block legitimate work",
                "Requires mature exception process",
                "Higher operational overhead",
                "May slow down development",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["SCPs are free"],
            soc2_controls=["CC6.1", "CC6.6", "CC6.8"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Decision tree for SCPs:

    1. Are you using Control Tower?
       YES → Start with Control Tower guardrails, add custom
       NO → Implement recommended SCPs manually

    2. What's your risk tolerance?
       High (fast-moving startup) → Minimal SCPs
       Medium (most organizations) → Standard SCPs
       Low (regulated, compliance) → Strict SCPs

    Recommended SCP Categories:

    **Always Implement:**
    - Deny leaving organization
    - Deny disabling CloudTrail
    - Deny disabling GuardDuty
    - Deny disabling Config
    - Deny root user access (except break-glass)
    - Require IMDSv2

    **Standard (Add for Production):**
    - Deny disabling S3 Block Public Access
    - Deny disabling EBS encryption
    - Deny creating unencrypted resources
    - Require specific regions only
    - Deny certain high-risk services

    **Strict (Add for Regulated):**
    - Deny all except approved services
    - Deny all except approved regions
    - Require specific tags on resources
    - Deny public S3 buckets
    - Deny public RDS/Redshift

    SCP Application Strategy:
    - Root: Minimal (affects management account)
    - Security OU: Strict (protect security accounts)
    - Infrastructure OU: Standard
    - Workloads/Prod OU: Standard + env-specific
    - Workloads/Dev OU: Minimal (flexibility)
    - Sandbox OU: Minimal + region/cost limits

    Testing SCPs:
    1. Create Policy Staging OU
    2. Move test account to Policy Staging
    3. Apply SCP
    4. Test workloads
    5. Roll out to target OUs
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: SCPs enforce access control
    - CC6.6: Network SCPs (region restrictions)
    - CC6.8: Deny disabling security services

    SCPs demonstrate preventive controls to auditors.
    Show your SCP inventory and explain rationale.
    """,
    common_mistakes=[
        "Applying strict SCPs to root (breaks management account)",
        "Not testing SCPs before production rollout",
        "Forgetting that SCPs don't affect management account",
        "No exception/break-glass process",
        "SCPs so strict they block AWS service functionality",
        "Not documenting SCP rationale",
    ],
)


def get_account_patterns() -> dict:
    """Get all account structure patterns."""
    return {
        "ou_structure": OU_STRUCTURE_PATTERNS,
        "core_accounts": CORE_ACCOUNTS_PATTERNS,
        "account_baseline": ACCOUNT_BASELINE_PATTERNS,
        "scps": SCP_PATTERNS,
    }
