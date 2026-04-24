"""
IAM and Identity Patterns for CARL Foundation Builder.

Comprehensive patterns for IAM Identity Center, permission sets,
SCPs, and access management.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# IAM IDENTITY CENTER (SSO) PATTERNS
# =============================================================================

IDENTITY_CENTER_PATTERNS = ArchitectureDecision(
    question="How should IAM Identity Center (SSO) be configured?",
    options=[
        DecisionOption(
            name="Identity Center with Built-in Directory",
            description="Use IAM Identity Center's native identity store",
            when_to_use=[
                "Small organization (< 50 users)",
                "No existing identity provider",
                "Getting started quickly",
                "Simple user management needs",
            ],
            when_not_to_use=[
                "Existing corporate IdP (Okta, Azure AD)",
                "Complex user lifecycle management",
                "Enterprise with HR system integration",
            ],
            pros=[
                "Simplest to set up",
                "No external dependencies",
                "Free (no IdP license needed)",
                "Native AWS integration",
            ],
            cons=[
                "Manual user management",
                "No HR system integration",
                "Limited to 50,000 users",
                "Basic group management",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["IAM Identity Center is free", "No external IdP costs"],
            soc2_controls=["CC6.1", "CC6.2", "CC6.3"],
            hipaa_controls=["164.312(a)(1)", "164.312(a)(2)(i)", "164.312(d)"],  # Access Control, Unique User ID, Authentication
            implementation_complexity="low",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Identity Center with External IdP (SAML)",
            description="Federate with Okta, Azure AD, or other SAML IdP",
            when_to_use=[
                "Existing corporate identity provider",
                "Centralized user management required",
                "Enterprise SSO requirements",
                "HR system integration needed",
            ],
            when_not_to_use=[
                "No existing IdP",
                "Very small organization",
                "Budget doesn't allow IdP licensing",
            ],
            pros=[
                "Single source of truth for identities",
                "Automated provisioning (SCIM)",
                "MFA managed centrally",
                "Consistent with other enterprise apps",
            ],
            cons=[
                "IdP licensing costs",
                "More complex setup",
                "Dependency on external service",
                "Need to maintain SAML config",
            ],
            monthly_cost_range=(0, 50.00),
            cost_drivers=[
                "Identity Center: Free",
                "IdP costs vary (Okta approx. $2-6/user/mo)",
                "Azure AD included with M365",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.3"],
            hipaa_controls=["164.312(a)(1)", "164.312(a)(2)(i)", "164.312(d)"],  # Access Control, Unique User ID, Authentication
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Identity Center with Active Directory",
            description="Integrate with on-premises or AWS Managed AD",
            when_to_use=[
                "Existing Active Directory investment",
                "Hybrid cloud with on-premises",
                "Windows-centric environment",
                "Need AD group-based access",
            ],
            when_not_to_use=[
                "Cloud-native organization",
                "No existing AD",
                "Moving away from AD",
            ],
            pros=[
                "Leverages existing AD investment",
                "AD groups for permissions",
                "Familiar for Windows shops",
                "Seamless for hybrid",
            ],
            cons=[
                "AD Connector or Managed AD costs",
                "AD maintenance overhead",
                "Legacy technology",
                "Complex for cloud-native",
            ],
            monthly_cost_range=(50.00, 300.00),
            cost_drivers=[
                "AD Connector: approx. $30/mo (small)",
                "AWS Managed AD: approx. $150-500/mo",
                "Plus EC2 for on-prem AD connectivity",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.3"],
            hipaa_controls=["164.312(a)(1)", "164.312(a)(2)(i)", "164.312(d)"],  # Access Control, Unique User ID, Authentication
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Decision tree for Identity Center:

    1. Do you have an existing corporate IdP?
       YES (Okta, Azure AD, etc.) → External IdP via SAML
       NO → Continue to 2

    2. Do you have Active Directory?
       YES, and want to keep using it → AD integration
       NO, or moving away → Continue to 3

    3. How many users?
       < 50 → Built-in directory is fine
       50+ → Consider external IdP for management

    Best practices:
    - ALWAYS use Identity Center (not IAM users)
    - Enable MFA (required for SOC 2)
    - Use SCIM for automatic provisioning if using external IdP
    - Create groups that map to job functions
    - Review access quarterly

    Identity Center setup:
    1. Enable in management account
    2. Choose identity source
    3. Create permission sets
    4. Create groups (Admin, Developer, ReadOnly, etc.)
    5. Assign groups to accounts with permission sets
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Access provisioning through Identity Center
    - CC6.2: User registration and authorization
    - CC6.3: User removal (disable in IdP, automatic in AWS)

    Identity Center with MFA satisfies most SOC 2 access controls.
    Centralized identity management is strongly preferred by auditors.
    """,
    common_mistakes=[
        "Creating IAM users instead of using Identity Center",
        "Not enabling MFA",
        "Too many permission sets (keep it simple)",
        "Not using groups (assigning directly to users)",
        "Forgetting to disable users when they leave",
    ],
)


# =============================================================================
# PERMISSION SET PATTERNS
# =============================================================================

PERMISSION_SET_PATTERNS = ArchitectureDecision(
    question="How should IAM Identity Center permission sets be designed?",
    options=[
        DecisionOption(
            name="Job Function-Based Permission Sets",
            description="Permission sets aligned to job roles",
            when_to_use=[
                "Clear job functions (Admin, Developer, Analyst)",
                "Most organizations",
                "Simple access model",
            ],
            when_not_to_use=[
                "Complex matrix organizations",
                "Need very granular access control",
            ],
            pros=[
                "Easy to understand",
                "Maps to job roles",
                "Simple to maintain",
                "Easy onboarding",
            ],
            cons=[
                "May be too broad for some",
                "Doesn't handle edge cases well",
                "One-size-fits-all per role",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Permission sets are free"],
            soc2_controls=["CC6.1", "CC6.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Environment-Tiered Permission Sets",
            description="Different access levels per environment (prod vs dev)",
            when_to_use=[
                "Different permissions needed per environment",
                "Developers need more access in dev",
                "Strict production access controls",
            ],
            when_not_to_use=[
                "Same access needed everywhere",
                "Very simple environment setup",
            ],
            pros=[
                "Tighter production controls",
                "More freedom in dev/sandbox",
                "Clear environment boundaries",
            ],
            cons=[
                "More permission sets to manage",
                "More complex assignments",
                "Users need multiple sessions",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Permission sets are free"],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Service-Specific Permission Sets",
            description="Fine-grained permission sets per AWS service",
            when_to_use=[
                "Strict least-privilege requirements",
                "Large organizations with specialized teams",
                "High security environments",
            ],
            when_not_to_use=[
                "Small teams wearing many hats",
                "Simplicity is priority",
                "Operational overhead concern",
            ],
            pros=[
                "True least privilege",
                "Granular access control",
                "Clear audit trail",
            ],
            cons=[
                "Many permission sets to manage",
                "Complex user assignments",
                "Higher operational overhead",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Permission sets are free"],
            soc2_controls=["CC6.1", "CC6.2", "CC6.6"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Recommended permission sets for most organizations:

    **Core Permission Sets:**

    1. **AdministratorAccess**
       - Full access to everything
       - Assign to: Cloud Platform team only
       - Use for: Account setup, break-glass

    2. **PowerUserAccess**
       - Full access except IAM/Organizations
       - Assign to: Senior engineers (non-prod)
       - Use for: Development work

    3. **DeveloperAccess** (Custom)
       - Read/write to compute, storage, databases
       - Read-only to networking, security
       - No IAM user/role creation
       - Assign to: Developers (non-prod)

    4. **ReadOnlyAccess**
       - Read access to all services
       - Assign to: Auditors, analysts, support
       - Use for: Troubleshooting, reporting

    5. **SecurityAudit** (Custom)
       - Read access to security services
       - Can run Security Hub insights
       - Assign to: Security team

    6. **BillingAccess** (Custom)
       - Access to Cost Explorer, Budgets
       - No resource access
       - Assign to: Finance, management

    **Environment Strategy:**
    - Production: ReadOnly for most, Admin for platform team
    - Staging: PowerUser for devs, Admin for platform
    - Development: PowerUser for devs
    - Sandbox: AdministratorAccess (with budget limits)

    Permission set session duration:
    - Default: 1 hour
    - PowerUser: 4 hours
    - ReadOnly: 12 hours
    - Admin: 1 hour (security)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Permission sets define access rights
    - CC6.2: Group-based assignment is auditable
    - CC6.6: Environment-based restrictions

    Demonstrate least privilege with permission set design.
    Document the rationale for each permission set.
    """,
    common_mistakes=[
        "Giving everyone AdministratorAccess",
        "Not using managed policies where appropriate",
        "Permission sets too granular (hard to manage)",
        "Not considering session duration",
        "Forgetting to assign to both groups AND accounts",
    ],
)


# =============================================================================
# CROSS-ACCOUNT ACCESS PATTERNS
# =============================================================================

CROSS_ACCOUNT_PATTERNS = ArchitectureDecision(
    question="How should cross-account access be managed?",
    options=[
        DecisionOption(
            name="Identity Center (Recommended)",
            description="Use IAM Identity Center for all human cross-account access",
            when_to_use=[
                "Human users accessing multiple accounts",
                "Primary access method",
                "All organizations",
            ],
            when_not_to_use=[
                "Service-to-service access (use roles)",
                "External partner access (consider)",
            ],
            pros=[
                "Centralized access management",
                "MFA enforced",
                "Session audit trail",
                "Easy onboarding/offboarding",
            ],
            cons=[
                "Requires Identity Center setup",
                "Not for service accounts",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Identity Center is free"],
            soc2_controls=["CC6.1", "CC6.2", "CC6.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Cross-Account IAM Roles",
            description="IAM roles with trust policies for service-to-service",
            when_to_use=[
                "Service-to-service access",
                "CI/CD pipelines",
                "Lambda cross-account access",
                "Automated processes",
            ],
            when_not_to_use=[
                "Human access (use Identity Center)",
                "One-off access",
            ],
            pros=[
                "Standard AWS pattern",
                "Temporary credentials",
                "Auditable via CloudTrail",
                "No stored credentials",
            ],
            cons=[
                "Must manage trust policies",
                "External ID recommended",
                "Role chaining limits",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["IAM is free"],
            soc2_controls=["CC6.1", "CC6.6"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Resource-Based Policies",
            description="Cross-account access via resource policies (S3, KMS, etc.)",
            when_to_use=[
                "Sharing specific resources",
                "S3 bucket access",
                "KMS key access",
                "SNS/SQS cross-account",
            ],
            when_not_to_use=[
                "Broad service access",
                "Human access",
            ],
            pros=[
                "No role assumption needed",
                "Simple for specific resources",
                "Works with service principals",
            ],
            cons=[
                "Doesn't scale well",
                "Harder to audit centrally",
                "Must update each resource",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["IAM is free"],
            soc2_controls=["CC6.1", "CC6.6"],
            implementation_complexity="low",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="AWS RAM (Resource Access Manager)",
            description="Share resources across accounts in Organization",
            when_to_use=[
                "Sharing VPCs (subnets)",
                "Transit Gateway sharing",
                "Route 53 Resolver rules",
                "License Manager",
            ],
            when_not_to_use=[
                "Resources RAM doesn't support",
                "Non-Organization accounts",
            ],
            pros=[
                "Native AWS sharing",
                "Works with Organizations",
                "No complex policies needed",
                "Central management",
            ],
            cons=[
                "Limited resource types",
                "Must be in same Organization",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["RAM is free"],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Cross-account access decision matrix:

    | Access Type | Method |
    |-------------|--------|
    | Human users | Identity Center |
    | CI/CD pipeline | Cross-account role |
    | Lambda/ECS | Cross-account role |
    | S3 bucket sharing | Resource policy or RAM |
    | KMS key sharing | Resource policy |
    | VPC sharing | RAM |
    | TGW sharing | RAM |

    Best practices:
    - ALWAYS use IAM Identity Center for humans
    - Use external IDs for third-party role trust
    - Limit role session duration appropriately
    - Use Organizations condition keys in trust policies
    - Audit cross-account access regularly

    Trust policy best practice (internal):
    ```json
    {
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::SOURCE_ACCOUNT:root"},
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:PrincipalOrgID": "o-xxxxxxxxxx"
        }
      }
    }
    ```

    Trust policy best practice (external):
    ```json
    {
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::EXTERNAL_ACCOUNT:root"},
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "unique-secret-id"
        }
      }
    }
    ```
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Cross-account access must be controlled
    - CC6.2: Access provisioning auditable
    - CC6.3: Removal must be timely
    - CC6.6: Trust policies define boundaries

    Document all cross-account access paths.
    Auditors will ask about cross-account trust relationships.
    """,
    common_mistakes=[
        "Using IAM users for cross-account (use roles)",
        "Overly permissive trust policies",
        "Forgetting external ID for third parties",
        "Not using Organization condition keys",
        "Long-lived credentials instead of STS",
    ],
)


# =============================================================================
# BREAK-GLASS ACCESS PATTERNS
# =============================================================================

BREAK_GLASS_PATTERNS = ArchitectureDecision(
    question="How should emergency/break-glass access be handled?",
    options=[
        DecisionOption(
            name="Root User with Hardware MFA",
            description="Secure root user credentials for emergencies only",
            when_to_use=[
                "All accounts (required for some operations)",
                "Account recovery scenarios",
                "Certain billing/support operations",
            ],
            when_not_to_use=[
                "Day-to-day operations (never)",
            ],
            pros=[
                "Required for some AWS operations",
                "Ultimate access recovery",
                "Simple to secure",
            ],
            cons=[
                "Can bypass all controls",
                "Must be physically secured",
                "Hard to audit usage",
            ],
            monthly_cost_range=(0, 50.00),
            cost_drivers=[
                "Hardware MFA devices: approx. $20-50 each",
                "Secure storage (safe): One-time cost",
            ],
            soc2_controls=["CC6.1", "CC6.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Privileged Access Management (PAM)",
            description="Time-limited, approved access elevation",
            when_to_use=[
                "Enterprise environments",
                "Strict audit requirements",
                "Just-in-time access needs",
            ],
            when_not_to_use=[
                "Small organizations",
                "Simple access needs",
            ],
            pros=[
                "Audited access elevation",
                "Time-limited sessions",
                "Approval workflows",
                "Just-in-time access",
            ],
            cons=[
                "Additional tooling needed",
                "Process overhead",
                "Cost for PAM solution",
            ],
            monthly_cost_range=(0, 500.00),
            cost_drivers=[
                "PAM solutions vary widely",
                "CyberArk, HashiCorp Vault, etc.",
                "AWS native: Permissions on demand",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC6.3"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Break-Glass IAM Role with Alerting",
            description="Dedicated high-privilege role with automated alerts",
            when_to_use=[
                "Most organizations",
                "Balance of security and simplicity",
                "When PAM is overkill",
            ],
            when_not_to_use=[
                "Very high security requirements",
                "Need approval workflow",
            ],
            pros=[
                "Native AWS solution",
                "Automatic alerting",
                "Simple to implement",
                "Auditable",
            ],
            cons=[
                "No pre-approval workflow",
                "Reactive alerting only",
                "Must be restricted carefully",
            ],
            monthly_cost_range=(0, 10.00),
            cost_drivers=[
                "IAM is free",
                "CloudWatch alerts: approx. $0.10/alert",
                "SNS notifications: Minimal",
            ],
            soc2_controls=["CC6.1", "CC6.2", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Break-glass access setup:

    **Root User Security:**
    1. Enable hardware MFA on all root users
    2. Store hardware MFA in physical safe
    3. Store root password in separate secure location
    4. Enable root login alerts via CloudTrail
    5. Document root user access procedure
    6. Never use root for daily operations

    **Break-Glass Role Setup:**
    1. Create BreakGlass role with AdministratorAccess
    2. Restrict trust to specific users/roles
    3. Set session duration to minimum (1 hour)
    4. Create CloudTrail metric filter for AssumeRole
    5. Alert security team on any use
    6. Review usage monthly

    **Alert on break-glass usage:**
    ```
    CloudTrail filter:
    { $.eventName = "AssumeRole" &&
      $.requestParameters.roleArn = "*BreakGlass*" }
    ```

    **Runbook for break-glass:**
    1. Assess if break-glass is truly needed
    2. Get verbal approval from security lead
    3. Access the role (alerts will fire)
    4. Perform necessary actions
    5. Document actions taken
    6. Exit session immediately
    7. Post-incident review
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Emergency access is still controlled
    - CC6.2: Break-glass procedures documented
    - CC7.2: All usage is logged and alerted

    Auditors want to see:
    - Documented break-glass procedure
    - Evidence that root access is rare
    - Alerts configured for emergency access
    """,
    common_mistakes=[
        "Root user without MFA",
        "Using break-glass for routine tasks",
        "No alerting on emergency access",
        "Break-glass procedure not documented",
        "Too many people with break-glass access",
    ],
)


def get_identity_patterns() -> dict:
    """Get all identity and access management patterns."""
    return {
        "identity_center": IDENTITY_CENTER_PATTERNS,
        "permission_sets": PERMISSION_SET_PATTERNS,
        "cross_account": CROSS_ACCOUNT_PATTERNS,
        "break_glass": BREAK_GLASS_PATTERNS,
    }
