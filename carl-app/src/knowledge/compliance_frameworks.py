"""
Compliance Framework Definitions for CARL.

This module provides a framework-agnostic abstraction layer that allows CARL
to support multiple compliance frameworks (SOC 2, HIPAA, ISO 27001, etc.)
without hardcoding framework-specific logic throughout the codebase.

Usage:
    from knowledge.compliance_frameworks import get_framework, ComplianceFramework

    # Get framework config
    hipaa = get_framework("hipaa")
    print(hipaa.evidence_retention_days)  # 2190

    # Use in evidence collection
    framework = get_framework(user_selected_framework)
    config_rules = framework.aws_config_rules
"""

from dataclasses import dataclass, field
from enum import Enum


class ComplianceFramework(Enum):
    """Supported compliance frameworks."""
    SOC2 = "soc2"
    HIPAA = "hipaa"
    # Future frameworks:
    # ISO27001 = "iso27001"
    # PCI_DSS = "pci_dss"
    # NIST_800_53 = "nist_800_53"
    # FEDRAMP = "fedramp"


@dataclass
class FrameworkConfig:
    """Configuration for a compliance framework."""

    id: str
    name: str
    short_name: str
    description: str
    controls_prefix: str
    evidence_retention_days: int
    report_template: str

    # AWS Config rules relevant to this framework
    aws_config_rules: list[str] = field(default_factory=list)

    # Security Hub standards to enable
    security_hub_standards: list[str] = field(default_factory=list)

    # AI prompt context for this framework
    ai_prompt_context: str = ""

    # Control categories for grouping
    control_categories: list[str] = field(default_factory=list)


# =============================================================================
# SOC 2 Framework Configuration
# =============================================================================

SOC2_CONFIG = FrameworkConfig(
    id="soc2",
    name="SOC 2 Type II",
    short_name="SOC 2",
    description="Service Organization Control 2 - Trust Services Criteria",
    controls_prefix="CC",
    evidence_retention_days=2555,  # 7 years
    report_template="soc2_report.html",
    control_categories=[
        "CC1 - Control Environment",
        "CC2 - Communication and Information",
        "CC3 - Risk Assessment",
        "CC4 - Monitoring Activities",
        "CC5 - Control Activities",
        "CC6 - Logical and Physical Access Controls",
        "CC7 - System Operations",
        "CC8 - Change Management",
        "CC9 - Risk Mitigation",
    ],
    aws_config_rules=[
        # CC6 - Access Controls
        "iam-password-policy",
        "iam-user-mfa-enabled",
        "root-account-mfa-enabled",
        "access-keys-rotated",
        "iam-user-no-policies-check",
        "iam-root-access-key-check",
        # CC6 - Encryption
        "s3-bucket-server-side-encryption-enabled",
        "s3-bucket-ssl-requests-only",
        "encrypted-volumes",
        "rds-storage-encrypted",
        "cmk-backing-key-rotation-enabled",
        # CC7 - Operations & Monitoring
        "cloudtrail-enabled",
        "cloud-trail-log-file-validation-enabled",
        "guardduty-enabled-centralized",
        "vpc-flow-logs-enabled",
        "cloudwatch-alarm-action-check",
        # CC6 - Network Security
        "s3-bucket-public-read-prohibited",
        "s3-bucket-public-write-prohibited",
        "restricted-ssh",
        "ec2-imdsv2-check",
    ],
    security_hub_standards=[
        "aws-foundational-security-best-practices/v/1.0.0",
        "cis-aws-foundations-benchmark/v/1.4.0",
    ],
    ai_prompt_context="""You are advising on SOC 2 Type II compliance.

SOC 2 Trust Services Criteria:
- CC6.1: Logical Access - Implement access controls, unique IDs, MFA
- CC6.6: System Boundaries - Restrict access at network boundaries
- CC6.7: Encryption - Encrypt data at rest and in transit
- CC7.1: Threat Detection - Monitor for security threats
- CC7.2: Monitoring - Log and monitor system activity
- CC8.1: Change Management - Control changes to infrastructure

Always map recommendations to specific CC controls (e.g., "This addresses CC6.7 - Encryption").
Prioritize encryption, access control, logging, and monitoring.
Evidence retention: 7 years minimum for audit purposes.
""",
)


# =============================================================================
# HIPAA Framework Configuration
# =============================================================================

HIPAA_CONFIG = FrameworkConfig(
    id="hipaa",
    name="HIPAA Security Rule",
    short_name="HIPAA",
    description="Health Insurance Portability and Accountability Act - Security Rule for ePHI",
    controls_prefix="164.312",
    evidence_retention_days=2190,  # 6 years per HIPAA requirements
    report_template="hipaa_report.html",
    control_categories=[
        "164.312(a) - Access Control",
        "164.312(b) - Audit Controls",
        "164.312(c) - Integrity",
        "164.312(d) - Person or Entity Authentication",
        "164.312(e) - Transmission Security",
    ],
    aws_config_rules=[
        # 164.312(a) - Access Control
        "iam-password-policy",
        "iam-user-mfa-enabled",
        "root-account-mfa-enabled",
        "access-keys-rotated",
        "iam-user-no-policies-check",
        # 164.312(a)(2)(iv) - Encryption
        "s3-bucket-server-side-encryption-enabled",
        "encrypted-volumes",
        "rds-storage-encrypted",
        "dynamodb-table-encrypted-kms",
        "cmk-backing-key-rotation-enabled",
        # 164.312(b) - Audit Controls
        "cloudtrail-enabled",
        "cloud-trail-log-file-validation-enabled",
        "cloudtrail-s3-dataevents-enabled",
        "vpc-flow-logs-enabled",
        "rds-logging-enabled",
        "s3-bucket-logging-enabled",
        # 164.312(c) - Integrity
        "s3-bucket-versioning-enabled",
        "cloud-trail-log-file-validation-enabled",
        "dynamodb-pitr-enabled",
        "rds-instance-deletion-protection-enabled",
        # 164.312(d) - Authentication
        "iam-user-mfa-enabled",
        "root-account-mfa-enabled",
        "mfa-enabled-for-iam-console-access",
        # 164.312(e) - Transmission Security
        "s3-bucket-ssl-requests-only",
        "alb-http-to-https-redirection-check",
        "elb-tls-https-listeners-only",
        "api-gw-ssl-enabled",
        "redshift-require-tls-ssl",
        "elasticsearch-node-to-node-encryption-check",
    ],
    security_hub_standards=[
        "aws-foundational-security-best-practices/v/1.0.0",
        # Note: AWS Security Hub has a HIPAA standard but requires explicit enablement
    ],
    ai_prompt_context="""You are advising on HIPAA Security Rule compliance for Protected Health Information (ePHI).

HIPAA Security Rule Technical Safeguards (45 CFR 164.312):

164.312(a)(1) - Access Control:
  - 164.312(a)(2)(i): Unique User Identification - Assign unique IDs
  - 164.312(a)(2)(ii): Emergency Access Procedure - Allow emergency access
  - 164.312(a)(2)(iii): Automatic Logoff - Terminate sessions after inactivity
  - 164.312(a)(2)(iv): Encryption and Decryption - Encrypt ePHI at rest

164.312(b) - Audit Controls:
  - Implement mechanisms to record and examine activity in systems containing ePHI
  - Retain audit logs for minimum 6 years

164.312(c)(1) - Integrity:
  - Protect ePHI from improper alteration or destruction
  - Implement electronic measures to confirm ePHI not improperly modified

164.312(d) - Person or Entity Authentication:
  - Verify identity of person or entity seeking access to ePHI
  - Implement MFA for all access to ePHI

164.312(e)(1) - Transmission Security:
  - Protect ePHI during electronic transmission
  - Implement encryption for ePHI in transit (TLS 1.2+)

CRITICAL HIPAA Requirements:
1. Only use HIPAA-eligible AWS services for ePHI workloads
2. Ensure AWS Business Associate Agreement (BAA) is in place
3. Encrypt ALL ePHI at rest and in transit
4. Implement comprehensive audit logging
5. Evidence retention: 6 years minimum

Always map recommendations to specific HIPAA sections (e.g., "This addresses 164.312(a)(2)(iv) - Encryption").
Flag any use of non-HIPAA-eligible AWS services.
""",
)


# =============================================================================
# Framework Registry
# =============================================================================

FRAMEWORKS: dict[str, FrameworkConfig] = {
    "soc2": SOC2_CONFIG,
    "hipaa": HIPAA_CONFIG,
}

# Default framework if none specified
DEFAULT_FRAMEWORK = "soc2"


def get_framework(framework_id: str) -> FrameworkConfig:
    """
    Get framework configuration by ID.

    Args:
        framework_id: Framework identifier (e.g., "soc2", "hipaa")

    Returns:
        FrameworkConfig for the requested framework

    Raises:
        ValueError: If framework_id is not recognized
    """
    framework_id = framework_id.lower()
    if framework_id not in FRAMEWORKS:
        valid = ", ".join(FRAMEWORKS.keys())
        raise ValueError(f"Unknown framework '{framework_id}'. Valid options: {valid}")
    return FRAMEWORKS[framework_id]


def list_frameworks() -> list[dict]:
    """
    List all available compliance frameworks.

    Returns:
        List of dicts with id, name, and description for each framework
    """
    return [
        {
            "id": f.id,
            "name": f.name,
            "short_name": f.short_name,
            "description": f.description,
        }
        for f in FRAMEWORKS.values()
    ]


def get_combined_config_rules(*framework_ids: str) -> list[str]:
    """
    Get combined AWS Config rules for multiple frameworks.

    Useful when an organization needs to comply with multiple frameworks.

    Args:
        *framework_ids: Framework IDs to combine

    Returns:
        Deduplicated list of AWS Config rules
    """
    rules = set()
    for fid in framework_ids:
        framework = get_framework(fid)
        rules.update(framework.aws_config_rules)
    return sorted(rules)


def get_ai_context(framework_id: str) -> str:
    """
    Get AI prompt context for a framework.

    Args:
        framework_id: Framework identifier

    Returns:
        AI prompt context string for the framework
    """
    return get_framework(framework_id).ai_prompt_context
