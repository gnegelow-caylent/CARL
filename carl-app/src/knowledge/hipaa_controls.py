"""
HIPAA Security Rule Control Definitions for CARL.

This module defines the HIPAA Security Rule technical safeguards (45 CFR 164.312)
with mappings to AWS services, evidence requirements, and implementation guidance.

Reference: https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html

Usage:
    from knowledge.hipaa_controls import HIPAA_CONTROLS, get_control, get_aws_controls

    # Get specific control
    access_control = get_control("164.312(a)(1)")

    # Get AWS controls for a HIPAA requirement
    aws_controls = get_aws_controls("164.312(e)(1)")
"""

from dataclasses import dataclass, field


@dataclass
class HIPAAControl:
    """Definition of a HIPAA Security Rule control."""

    id: str  # e.g., "164.312(a)(1)"
    name: str
    description: str
    requirement_type: str  # "required" or "addressable"

    # Implementation specifications (sub-controls)
    implementation_specs: list[dict] = field(default_factory=list)

    # AWS services that help implement this control
    aws_services: list[str] = field(default_factory=list)

    # Specific AWS controls/configurations
    aws_controls: list[str] = field(default_factory=list)

    # AWS Config rules that validate this control
    config_rules: list[str] = field(default_factory=list)

    # Evidence types to collect for audits
    evidence_types: list[str] = field(default_factory=list)

    # Terraform resources typically involved
    terraform_resources: list[str] = field(default_factory=list)


# =============================================================================
# HIPAA Security Rule Technical Safeguards (45 CFR 164.312)
# =============================================================================

HIPAA_CONTROLS: dict[str, HIPAAControl] = {
    # =========================================================================
    # 164.312(a) - Access Control
    # =========================================================================
    "164.312(a)(1)": HIPAAControl(
        id="164.312(a)(1)",
        name="Access Control",
        description="Implement technical policies and procedures for electronic information "
                    "systems that maintain ePHI to allow access only to those persons or "
                    "software programs that have been granted access rights.",
        requirement_type="required",
        implementation_specs=[
            {
                "id": "164.312(a)(2)(i)",
                "name": "Unique User Identification",
                "description": "Assign a unique name and/or number for identifying and tracking user identity",
                "requirement_type": "required",
            },
            {
                "id": "164.312(a)(2)(ii)",
                "name": "Emergency Access Procedure",
                "description": "Establish procedures for obtaining necessary ePHI during an emergency",
                "requirement_type": "required",
            },
            {
                "id": "164.312(a)(2)(iii)",
                "name": "Automatic Logoff",
                "description": "Implement electronic procedures that terminate an electronic session after a predetermined time of inactivity",
                "requirement_type": "addressable",
            },
            {
                "id": "164.312(a)(2)(iv)",
                "name": "Encryption and Decryption",
                "description": "Implement a mechanism to encrypt and decrypt ePHI",
                "requirement_type": "addressable",
            },
        ],
        aws_services=[
            "IAM",
            "IAM Identity Center (SSO)",
            "Cognito",
            "KMS",
            "Secrets Manager",
        ],
        aws_controls=[
            "Unique IAM users for each person (no shared credentials)",
            "IAM Identity Center for centralized access management",
            "MFA enabled for all IAM users and root account",
            "KMS encryption for all data stores containing ePHI",
            "Session timeout policies in Cognito/SSO",
            "Break-glass IAM role for emergency access",
            "Secrets Manager for credential management",
        ],
        config_rules=[
            "iam-user-mfa-enabled",
            "root-account-mfa-enabled",
            "iam-password-policy",
            "access-keys-rotated",
            "iam-user-no-policies-check",
            "s3-bucket-server-side-encryption-enabled",
            "encrypted-volumes",
            "rds-storage-encrypted",
        ],
        evidence_types=[
            "iam_credential_report",
            "iam_password_policy",
            "mfa_device_list",
            "kms_key_list",
            "kms_key_policies",
            "encryption_configuration",
        ],
        terraform_resources=[
            "aws_iam_user",
            "aws_iam_policy",
            "aws_iam_account_password_policy",
            "aws_kms_key",
            "aws_kms_alias",
        ],
    ),

    # =========================================================================
    # 164.312(b) - Audit Controls
    # =========================================================================
    "164.312(b)": HIPAAControl(
        id="164.312(b)",
        name="Audit Controls",
        description="Implement hardware, software, and/or procedural mechanisms that record "
                    "and examine activity in information systems that contain or use ePHI.",
        requirement_type="required",
        implementation_specs=[],  # No sub-specifications for audit controls
        aws_services=[
            "CloudTrail",
            "CloudWatch Logs",
            "VPC Flow Logs",
            "S3 Access Logs",
            "RDS Audit Logs",
            "GuardDuty",
            "Security Hub",
        ],
        aws_controls=[
            "CloudTrail enabled in all regions with multi-region trail",
            "CloudTrail log file validation enabled",
            "CloudTrail logs encrypted with KMS",
            "CloudTrail logs stored in S3 with 6-year retention",
            "VPC Flow Logs enabled for all VPCs",
            "S3 access logging enabled for ePHI buckets",
            "RDS audit logging enabled (MySQL/PostgreSQL/Oracle)",
            "CloudWatch Logs with 6-year retention",
            "GuardDuty enabled for threat detection",
            "Security Hub enabled for centralized findings",
        ],
        config_rules=[
            "cloudtrail-enabled",
            "cloud-trail-log-file-validation-enabled",
            "cloudtrail-s3-dataevents-enabled",
            "cloudtrail-security-trail-enabled",
            "vpc-flow-logs-enabled",
            "s3-bucket-logging-enabled",
            "rds-logging-enabled",
            "guardduty-enabled-centralized",
        ],
        evidence_types=[
            "cloudtrail_configuration",
            "cloudtrail_trails",
            "cloudwatch_log_groups",
            "vpc_flow_log_config",
            "s3_logging_config",
            "guardduty_detector_status",
            "security_hub_status",
        ],
        terraform_resources=[
            "aws_cloudtrail",
            "aws_cloudwatch_log_group",
            "aws_flow_log",
            "aws_s3_bucket_logging",
            "aws_guardduty_detector",
            "aws_securityhub_account",
        ],
    ),

    # =========================================================================
    # 164.312(c) - Integrity
    # =========================================================================
    "164.312(c)(1)": HIPAAControl(
        id="164.312(c)(1)",
        name="Integrity",
        description="Implement policies and procedures to protect ePHI from improper "
                    "alteration or destruction.",
        requirement_type="required",
        implementation_specs=[
            {
                "id": "164.312(c)(2)",
                "name": "Mechanism to Authenticate ePHI",
                "description": "Implement electronic mechanisms to corroborate that ePHI has not been altered or destroyed in an unauthorized manner",
                "requirement_type": "addressable",
            },
        ],
        aws_services=[
            "S3 Versioning",
            "S3 Object Lock",
            "RDS Automated Backups",
            "DynamoDB Point-in-Time Recovery",
            "AWS Backup",
            "CloudTrail Log Validation",
        ],
        aws_controls=[
            "S3 versioning enabled for ePHI buckets",
            "S3 Object Lock for immutable audit logs",
            "RDS automated backups with appropriate retention",
            "DynamoDB point-in-time recovery enabled",
            "AWS Backup for centralized backup management",
            "CloudTrail log file validation for integrity verification",
            "RDS deletion protection enabled",
            "S3 MFA delete enabled for critical buckets",
        ],
        config_rules=[
            "s3-bucket-versioning-enabled",
            "cloud-trail-log-file-validation-enabled",
            "dynamodb-pitr-enabled",
            "rds-instance-deletion-protection-enabled",
            "db-instance-backup-enabled",
            "backup-plan-min-frequency-and-min-retention-check",
        ],
        evidence_types=[
            "s3_versioning_config",
            "s3_object_lock_config",
            "rds_backup_config",
            "dynamodb_pitr_config",
            "backup_plans",
            "cloudtrail_log_validation",
        ],
        terraform_resources=[
            "aws_s3_bucket_versioning",
            "aws_s3_bucket_object_lock_configuration",
            "aws_db_instance",  # backup_retention_period
            "aws_dynamodb_table",  # point_in_time_recovery
            "aws_backup_plan",
        ],
    ),

    # =========================================================================
    # 164.312(d) - Authentication
    # =========================================================================
    "164.312(d)": HIPAAControl(
        id="164.312(d)",
        name="Person or Entity Authentication",
        description="Implement procedures to verify that a person or entity seeking access "
                    "to ePHI is the one claimed.",
        requirement_type="required",
        implementation_specs=[],  # No sub-specifications
        aws_services=[
            "IAM",
            "IAM Identity Center",
            "Cognito",
            "Directory Service",
        ],
        aws_controls=[
            "MFA required for all IAM users",
            "MFA required for root account",
            "Strong password policy (14+ characters, complexity)",
            "Cognito MFA for application users",
            "Certificate-based authentication where applicable",
            "Federation with enterprise IdP (SAML/OIDC)",
            "Hardware security keys for privileged access",
        ],
        config_rules=[
            "iam-user-mfa-enabled",
            "root-account-mfa-enabled",
            "mfa-enabled-for-iam-console-access",
            "iam-password-policy",
        ],
        evidence_types=[
            "iam_credential_report",
            "mfa_device_list",
            "password_policy",
            "cognito_mfa_config",
            "sso_mfa_config",
        ],
        terraform_resources=[
            "aws_iam_account_password_policy",
            "aws_iam_virtual_mfa_device",
            "aws_cognito_user_pool",  # mfa_configuration
        ],
    ),

    # =========================================================================
    # 164.312(e) - Transmission Security
    # =========================================================================
    "164.312(e)(1)": HIPAAControl(
        id="164.312(e)(1)",
        name="Transmission Security",
        description="Implement technical security measures to guard against unauthorized "
                    "access to ePHI that is being transmitted over an electronic "
                    "communications network.",
        requirement_type="required",
        implementation_specs=[
            {
                "id": "164.312(e)(2)(i)",
                "name": "Integrity Controls",
                "description": "Implement security measures to ensure that electronically transmitted ePHI is not improperly modified without detection until disposed of",
                "requirement_type": "addressable",
            },
            {
                "id": "164.312(e)(2)(ii)",
                "name": "Encryption",
                "description": "Implement a mechanism to encrypt ePHI whenever deemed appropriate",
                "requirement_type": "addressable",
            },
        ],
        aws_services=[
            "ACM (Certificate Manager)",
            "ALB/NLB",
            "CloudFront",
            "API Gateway",
            "VPN",
            "Direct Connect",
            "PrivateLink",
        ],
        aws_controls=[
            "TLS 1.2 or higher for all connections",
            "HTTPS enforced (HTTP disabled or redirected)",
            "ACM certificates for TLS termination",
            "ALB/NLB with TLS listeners only",
            "API Gateway with TLS and client certificates",
            "S3 bucket policies requiring SecureTransport",
            "RDS connections with SSL/TLS required",
            "VPC endpoints (PrivateLink) for AWS services",
            "Site-to-site VPN or Direct Connect for hybrid",
            "ElastiCache in-transit encryption",
        ],
        config_rules=[
            "s3-bucket-ssl-requests-only",
            "alb-http-to-https-redirection-check",
            "elb-tls-https-listeners-only",
            "api-gw-ssl-enabled",
            "redshift-require-tls-ssl",
            "elasticsearch-node-to-node-encryption-check",
            "elb-predefined-security-policy-ssl-check",
        ],
        evidence_types=[
            "alb_listener_config",
            "api_gateway_config",
            "s3_bucket_policy",
            "rds_ssl_config",
            "acm_certificates",
            "cloudfront_config",
            "vpn_config",
        ],
        terraform_resources=[
            "aws_lb_listener",  # protocol = "HTTPS"
            "aws_api_gateway_rest_api",
            "aws_s3_bucket_policy",  # SecureTransport condition
            "aws_db_instance",  # parameter_group with ssl
            "aws_acm_certificate",
            "aws_cloudfront_distribution",
            "aws_vpn_connection",
        ],
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_control(control_id: str) -> HIPAAControl:
    """
    Get a HIPAA control by ID.

    Args:
        control_id: Control ID (e.g., "164.312(a)(1)")

    Returns:
        HIPAAControl definition

    Raises:
        KeyError: If control_id is not found
    """
    # Normalize the control ID
    control_id = control_id.strip()

    if control_id in HIPAA_CONTROLS:
        return HIPAA_CONTROLS[control_id]

    # Try to find parent control if sub-control specified
    # e.g., "164.312(a)(2)(iv)" -> "164.312(a)(1)"
    for cid, control in HIPAA_CONTROLS.items():
        for spec in control.implementation_specs:
            if spec["id"] == control_id:
                return control

    raise KeyError(f"HIPAA control not found: {control_id}")


def get_aws_controls(control_id: str) -> list[str]:
    """
    Get AWS controls for a HIPAA requirement.

    Args:
        control_id: HIPAA control ID

    Returns:
        List of AWS control descriptions
    """
    control = get_control(control_id)
    return control.aws_controls


def get_config_rules(control_id: str) -> list[str]:
    """
    Get AWS Config rules for a HIPAA requirement.

    Args:
        control_id: HIPAA control ID

    Returns:
        List of AWS Config rule names
    """
    control = get_control(control_id)
    return control.config_rules


def get_evidence_types(control_id: str) -> list[str]:
    """
    Get evidence types needed for a HIPAA control.

    Args:
        control_id: HIPAA control ID

    Returns:
        List of evidence type identifiers
    """
    control = get_control(control_id)
    return control.evidence_types


def get_all_config_rules() -> list[str]:
    """
    Get all unique AWS Config rules for HIPAA compliance.

    Returns:
        Deduplicated list of AWS Config rule names
    """
    rules = set()
    for control in HIPAA_CONTROLS.values():
        rules.update(control.config_rules)
    return sorted(rules)


def get_all_evidence_types() -> list[str]:
    """
    Get all unique evidence types for HIPAA compliance.

    Returns:
        Deduplicated list of evidence type identifiers
    """
    evidence = set()
    for control in HIPAA_CONTROLS.values():
        evidence.update(control.evidence_types)
    return sorted(evidence)


def map_finding_to_controls(finding_type: str) -> list[str]:
    """
    Map an AWS finding type to relevant HIPAA controls.

    Args:
        finding_type: Type of security finding (e.g., "s3_encryption_disabled")

    Returns:
        List of HIPAA control IDs that this finding relates to
    """
    # Mapping of common finding types to HIPAA controls
    FINDING_TO_CONTROL_MAP = {
        # Encryption findings
        "s3_encryption_disabled": ["164.312(a)(1)", "164.312(c)(1)"],
        "ebs_encryption_disabled": ["164.312(a)(1)"],
        "rds_encryption_disabled": ["164.312(a)(1)"],
        "kms_key_rotation_disabled": ["164.312(a)(1)"],

        # Access control findings
        "mfa_not_enabled": ["164.312(a)(1)", "164.312(d)"],
        "root_mfa_not_enabled": ["164.312(a)(1)", "164.312(d)"],
        "iam_policy_too_permissive": ["164.312(a)(1)"],
        "public_s3_bucket": ["164.312(a)(1)"],
        "public_security_group": ["164.312(a)(1)"],

        # Audit findings
        "cloudtrail_disabled": ["164.312(b)"],
        "vpc_flow_logs_disabled": ["164.312(b)"],
        "s3_logging_disabled": ["164.312(b)"],
        "log_validation_disabled": ["164.312(b)", "164.312(c)(1)"],

        # Integrity findings
        "s3_versioning_disabled": ["164.312(c)(1)"],
        "backup_not_configured": ["164.312(c)(1)"],
        "deletion_protection_disabled": ["164.312(c)(1)"],

        # Transmission security findings
        "http_enabled": ["164.312(e)(1)"],
        "tls_outdated": ["164.312(e)(1)"],
        "ssl_certificate_expired": ["164.312(e)(1)"],
        "insecure_transport": ["164.312(e)(1)"],
    }

    return FINDING_TO_CONTROL_MAP.get(finding_type, [])


def get_control_summary() -> list[dict]:
    """
    Get a summary of all HIPAA controls for display.

    Returns:
        List of control summaries with id, name, and requirement_type
    """
    return [
        {
            "id": control.id,
            "name": control.name,
            "requirement_type": control.requirement_type,
            "aws_services_count": len(control.aws_services),
            "config_rules_count": len(control.config_rules),
        }
        for control in HIPAA_CONTROLS.values()
    ]
