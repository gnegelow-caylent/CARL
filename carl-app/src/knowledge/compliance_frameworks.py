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
    NIST_CSF = "nist_csf"
    PCI_DSS = "pci_dss"
    # Future frameworks:
    # ISO27001 = "iso27001"
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
# NIST CSF 2.0 Framework Configuration
# =============================================================================

NIST_CSF_CONFIG = FrameworkConfig(
    id="nist_csf",
    name="NIST Cybersecurity Framework 2.0",
    short_name="NIST CSF",
    description="NIST Cybersecurity Framework - voluntary guidance for managing cybersecurity risk",
    controls_prefix="",
    evidence_retention_days=2555,  # 7 years (common for federal)
    report_template="nist_csf_report.html",
    control_categories=[
        "GV - Govern",
        "ID - Identify",
        "PR - Protect",
        "DE - Detect",
        "RS - Respond",
        "RC - Recover",
    ],
    aws_config_rules=[
        # GV - Govern
        "securityhub-enabled",
        # ID - Identify (Asset Management, Risk Assessment)
        "ec2-instance-managed-by-systems-manager",
        "required-tags",
        "guardduty-enabled-centralized",
        "inspector-lambda-standard-scan-enabled",
        # PR - Protect (Access Control, Data Security)
        "iam-password-policy",
        "iam-user-mfa-enabled",
        "root-account-mfa-enabled",
        "access-keys-rotated",
        "iam-user-no-policies-check",
        "iam-policy-no-statements-with-admin-access",
        "s3-bucket-server-side-encryption-enabled",
        "s3-bucket-ssl-requests-only",
        "encrypted-volumes",
        "rds-storage-encrypted",
        "cmk-backing-key-rotation-enabled",
        "backup-plan-min-frequency-and-min-retention-check",
        # DE - Detect (Continuous Monitoring)
        "cloudtrail-enabled",
        "cloud-trail-log-file-validation-enabled",
        "vpc-flow-logs-enabled",
        "cloudwatch-alarm-action-check",
        # RS/RC - Respond/Recover
        "dynamodb-pitr-enabled",
        "db-instance-backup-enabled",
    ],
    security_hub_standards=[
        "aws-foundational-security-best-practices/v/1.0.0",
        "cis-aws-foundations-benchmark/v/1.4.0",
        "nist-800-53/v/5.0.0",
    ],
    ai_prompt_context="""You are advising on NIST Cybersecurity Framework (CSF) 2.0 compliance.

NIST CSF 2.0 Core Functions:

GOVERN (GV) - New in CSF 2.0:
  - GV.OC: Organizational Context - understand mission and risk context
  - GV.RM: Risk Management Strategy - establish risk appetite and tolerance
  - GV.SC: Supply Chain Risk Management - manage third-party risks

IDENTIFY (ID):
  - ID.AM: Asset Management - inventory hardware, software, data
  - ID.RA: Risk Assessment - identify vulnerabilities and threats
  - ID.IM: Improvement - continuous improvement processes

PROTECT (PR):
  - PR.AA: Identity Management & Access Control - manage identities and authentication
  - PR.AT: Awareness and Training - security training programs
  - PR.DS: Data Security - protect data at rest and in transit
  - PR.PS: Platform Security - secure configurations, patching
  - PR.IR: Technology Infrastructure Resilience - network security, availability

DETECT (DE):
  - DE.CM: Continuous Monitoring - monitor for anomalies and threats
  - DE.AE: Adverse Event Analysis - analyze and correlate security events

RESPOND (RS):
  - RS.MA: Incident Management - execute incident response plans
  - RS.AN: Incident Analysis - investigate and preserve evidence
  - RS.CO: Incident Communication - notify stakeholders
  - RS.MI: Incident Mitigation - contain and eradicate threats

RECOVER (RC):
  - RC.RP: Recovery Plan Execution - restore systems and verify integrity
  - RC.CO: Recovery Communication - communicate recovery progress

Key NIST CSF Principles:
1. Risk-based approach - prioritize based on risk assessment
2. Continuous improvement - iterate and improve security posture
3. Framework is voluntary but widely adopted as baseline
4. Maps to other standards (SOC 2, HIPAA, PCI-DSS, ISO 27001)

Always map recommendations to specific NIST CSF categories (e.g., "This addresses PR.DS - Data Security").
Reference the CSF function when discussing controls.
""",
)


# =============================================================================
# PCI DSS 4.0 Framework Configuration
# =============================================================================

PCI_DSS_CONFIG = FrameworkConfig(
    id="pci_dss",
    name="PCI DSS 4.0",
    short_name="PCI DSS",
    description="Payment Card Industry Data Security Standard for protecting cardholder data",
    controls_prefix="Req",
    evidence_retention_days=365,  # 1 year online, longer in archive
    report_template="pci_dss_report.html",
    control_categories=[
        "Goal 1: Build and Maintain a Secure Network",
        "Goal 2: Protect Cardholder Data",
        "Goal 3: Maintain a Vulnerability Management Program",
        "Goal 4: Implement Strong Access Control Measures",
        "Goal 5: Regularly Monitor and Test Networks",
        "Goal 6: Maintain an Information Security Policy",
    ],
    aws_config_rules=[
        # Requirement 1 - Network Security
        "vpc-default-security-group-closed",
        "restricted-ssh",
        "restricted-common-ports",
        "vpc-sg-open-only-to-authorized-ports",
        "ec2-instance-no-public-ip",
        "rds-instance-public-access-check",
        # Requirement 2 - Secure Configurations
        "ec2-instance-managed-by-systems-manager",
        "ec2-imdsv2-check",
        "ec2-managedinstance-patch-compliance-status-check",
        # Requirement 3 - Protect Stored Data
        "cmk-backing-key-rotation-enabled",
        "s3-bucket-server-side-encryption-enabled",
        "s3-default-encryption-kms",
        "rds-storage-encrypted",
        "dynamodb-table-encrypted-kms",
        "encrypted-volumes",
        # Requirement 4 - Protect Data in Transit
        "alb-http-to-https-redirection-check",
        "elb-tls-https-listeners-only",
        "api-gw-ssl-enabled",
        "s3-bucket-ssl-requests-only",
        "acm-certificate-expiration-check",
        # Requirement 5 - Malware Protection
        "guardduty-enabled-centralized",
        "inspector-lambda-standard-scan-enabled",
        "ecr-private-image-scanning-enabled",
        # Requirement 6 - Secure Development
        "ec2-managedinstance-patch-compliance-status-check",
        # Requirement 7 - Access Control
        "iam-policy-no-statements-with-admin-access",
        "iam-policy-no-statements-with-full-access",
        "iam-user-no-policies-check",
        "iam-user-unused-credentials-check",
        # Requirement 8 - Authentication
        "iam-user-mfa-enabled",
        "root-account-mfa-enabled",
        "mfa-enabled-for-iam-console-access",
        "iam-password-policy",
        "access-keys-rotated",
        # Requirement 10 - Logging
        "cloudtrail-enabled",
        "cloud-trail-log-file-validation-enabled",
        "cloudtrail-s3-dataevents-enabled",
        "vpc-flow-logs-enabled",
        "s3-bucket-logging-enabled",
        "cloudwatch-alarm-action-check",
        # Requirement 11 - Security Testing
        "securityhub-enabled",
    ],
    security_hub_standards=[
        "aws-foundational-security-best-practices/v/1.0.0",
        "pci-dss/v/3.2.1",
    ],
    ai_prompt_context="""You are advising on PCI DSS 4.0 compliance for protecting cardholder data.

PCI DSS 4.0 Requirements (12 Requirements in 6 Goals):

GOAL 1: Build and Maintain a Secure Network and Systems
  - Req 1: Install and maintain network security controls (firewalls, segmentation)
  - Req 2: Apply secure configurations to all system components

GOAL 2: Protect Cardholder Data
  - Req 3: Protect stored account data (encryption, tokenization, masking)
  - Req 4: Protect cardholder data during transmission (TLS 1.2+)

GOAL 3: Maintain a Vulnerability Management Program
  - Req 5: Protect from malicious software (anti-malware)
  - Req 6: Develop and maintain secure systems (patching, secure SDLC)

GOAL 4: Implement Strong Access Control Measures
  - Req 7: Restrict access by business need to know (least privilege)
  - Req 8: Identify users and authenticate access (MFA, passwords)
  - Req 9: Restrict physical access to cardholder data

GOAL 5: Regularly Monitor and Test Networks
  - Req 10: Log and monitor all access (audit trails, SIEM)
  - Req 11: Test security regularly (vulnerability scans, pen tests)

GOAL 6: Maintain an Information Security Policy
  - Req 12: Support information security with policies and programs

CRITICAL PCI DSS Concepts:
1. Cardholder Data Environment (CDE) - systems that store, process, or transmit cardholder data
2. Network Segmentation - isolate CDE from other networks to reduce scope
3. Primary Account Number (PAN) - must be encrypted or tokenized
4. Sensitive Authentication Data (SAD) - CVV, PIN, track data - NEVER store after authorization
5. Quarterly ASV (Approved Scanning Vendor) scans required
6. Annual penetration testing required
7. MFA required for all access to CDE

AWS PCI DSS Compliance:
- AWS is PCI DSS Level 1 Service Provider
- Use only PCI-compliant AWS services in CDE
- Customer responsible for their own PCI compliance
- AWS Artifact provides PCI AOC (Attestation of Compliance)

Always map recommendations to specific PCI DSS requirements (e.g., "This addresses Requirement 3.5 - Protect Stored PAN").
Flag any configurations that could expose PAN or SAD.
Recommend network segmentation to minimize CDE scope.
""",
)


# =============================================================================
# Framework Registry
# =============================================================================

FRAMEWORKS: dict[str, FrameworkConfig] = {
    "soc2": SOC2_CONFIG,
    "hipaa": HIPAA_CONFIG,
    "nist_csf": NIST_CSF_CONFIG,
    "pci_dss": PCI_DSS_CONFIG,
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
