"""
SOC 2 Trust Service Criteria mappings for CARL.
"""

# Mapping of AWS Config rules to SOC 2 controls
CONFIG_RULE_TO_SOC2: dict[str, list[str]] = {
    # CC6.1 - Logical access security
    "iam-password-policy": ["CC6.1"],
    "iam-user-mfa-enabled": ["CC6.1"],
    "iam-user-unused-credentials-check": ["CC6.1", "CC6.3"],
    "iam-root-access-key-check": ["CC6.1"],
    "root-account-mfa-enabled": ["CC6.1"],
    "access-keys-rotated": ["CC6.1"],

    # CC6.2 - Access provisioning
    "iam-group-has-users-check": ["CC6.2"],
    "iam-user-group-membership-check": ["CC6.2"],

    # CC6.3 - Access removal
    "iam-user-unused-credentials-check": ["CC6.3"],

    # CC6.5 - Data protection
    "s3-bucket-server-side-encryption-enabled": ["CC6.5"],
    "encrypted-volumes": ["CC6.5"],
    "rds-storage-encrypted": ["CC6.5"],
    "cloud-trail-encryption-enabled": ["CC6.5"],
    "kms-cmk-not-scheduled-for-deletion": ["CC6.5"],

    # CC6.6 - Security configuration
    "s3-bucket-public-read-prohibited": ["CC6.6"],
    "s3-bucket-public-write-prohibited": ["CC6.6"],
    "vpc-default-security-group-closed": ["CC6.6"],
    "restricted-ssh": ["CC6.6"],
    "restricted-common-ports": ["CC6.6"],
    "ec2-imdsv2-check": ["CC6.6"],
    "ec2-instance-no-public-ip": ["CC6.6"],
    "rds-instance-public-access-check": ["CC6.6"],

    # CC6.7 - Transmission security
    "s3-bucket-ssl-requests-only": ["CC6.7"],
    "alb-http-to-https-redirection-check": ["CC6.7"],
    "elb-tls-https-listeners-only": ["CC6.7"],
    "redshift-require-tls-ssl": ["CC6.7"],

    # CC6.8 - Change management
    "cloud-trail-enabled": ["CC6.8", "CC7.2"],
    "cloudtrail-s3-dataevents-enabled": ["CC6.8"],
    "multi-region-cloudtrail-enabled": ["CC6.8"],

    # CC7.1 - Vulnerability management
    "ec2-managedinstance-patch-compliance-status-check": ["CC7.1"],

    # CC7.2 - Security monitoring
    "cloudwatch-alarm-action-check": ["CC7.2"],
    "guardduty-enabled-centralized": ["CC7.2"],
    "securityhub-enabled": ["CC7.2"],

    # A1.1 - Processing capacity
    "rds-multi-az-support": ["A1.1", "A1.2"],
    "dynamodb-autoscaling-enabled": ["A1.1"],
    "elb-cross-zone-load-balancing-enabled": ["A1.1"],

    # A1.2 - Recovery
    "db-instance-backup-enabled": ["A1.2"],
    "dynamodb-pitr-enabled": ["A1.2"],
    "s3-bucket-versioning-enabled": ["A1.2"],
}

# Security Hub finding types to SOC 2 controls
SECURITY_HUB_TO_SOC2: dict[str, list[str]] = {
    "Software and Configuration Checks/AWS Security Best Practices": ["CC6.6"],
    "Software and Configuration Checks/Industry and Regulatory Standards/CIS AWS Foundations Benchmark": ["CC6.1", "CC6.6"],
    "Effects/Data Exposure": ["CC6.5"],
    "Sensitive Data Identifications": ["CC6.5"],
    "TTPs/Initial Access": ["CC7.2", "CC7.3"],
    "TTPs/Persistence": ["CC7.2", "CC7.3"],
    "TTPs/Privilege Escalation": ["CC6.1", "CC7.2"],
    "Unusual Behaviors": ["CC7.2"],
}

# GuardDuty finding types to SOC 2 controls
GUARDDUTY_TO_SOC2: dict[str, list[str]] = {
    "UnauthorizedAccess": ["CC6.1", "CC7.2", "CC7.3"],
    "Recon": ["CC7.2"],
    "Trojan": ["CC7.2", "CC7.3"],
    "CryptoCurrency": ["CC7.2"],
    "Backdoor": ["CC7.2", "CC7.3"],
    "Stealth": ["CC7.2"],
    "CredentialAccess": ["CC6.1", "CC7.2"],
    "Impact": ["CC7.3", "A1.1"],
    "Exfiltration": ["CC6.5", "CC7.2"],
}


def get_soc2_controls(identifier: str) -> list[str]:
    """
    Get SOC 2 controls for a given identifier.

    Args:
        identifier: Config rule name, Security Hub type, or GuardDuty type

    Returns:
        List of SOC 2 control IDs
    """
    identifier_lower = identifier.lower()

    # Check Config rules first
    for rule, controls in CONFIG_RULE_TO_SOC2.items():
        if rule.lower() in identifier_lower:
            return controls

    # Check Security Hub types
    for finding_type, controls in SECURITY_HUB_TO_SOC2.items():
        if finding_type.lower() in identifier_lower:
            return controls

    # Check GuardDuty types
    for gd_type, controls in GUARDDUTY_TO_SOC2.items():
        if gd_type.lower() in identifier_lower:
            return controls

    # Default controls for unknown findings
    return ["CC6.6"]  # General security configuration


def get_control_description(control_id: str) -> str:
    """Get description for a SOC 2 control."""
    descriptions = {
        "CC6.1": "Logical access security software, infrastructure, and architectures",
        "CC6.2": "Prior to granting access, entity registers and authorizes new users",
        "CC6.3": "Entity removes access when no longer required",
        "CC6.5": "Entity protects data from unauthorized access",
        "CC6.6": "Entity implements logical access security measures to protect against threats",
        "CC6.7": "Entity restricts the transmission of information to authorized channels",
        "CC6.8": "Entity implements controls to prevent or detect against unauthorized or malicious software",
        "CC7.1": "Entity identifies and assesses changes that could significantly impact internal control",
        "CC7.2": "Entity monitors system components and operation of those components",
        "CC7.3": "Entity evaluates security events to determine whether they could impact organizational objectives",
        "A1.1": "Entity maintains current processing capacity and plans future capacity needs",
        "A1.2": "Entity authorizes, designs, develops, implements, operates, and maintains a recovery infrastructure",
    }
    return descriptions.get(control_id, f"SOC 2 Control {control_id}")


def get_controls_for_service(service: str) -> list[str]:
    """Get relevant SOC 2 controls for an AWS service."""
    service_controls = {
        "s3": ["CC6.5", "CC6.6", "CC6.7", "A1.2"],
        "ec2": ["CC6.6", "CC7.1", "A1.1"],
        "iam": ["CC6.1", "CC6.2", "CC6.3"],
        "rds": ["CC6.5", "CC6.6", "A1.1", "A1.2"],
        "cloudtrail": ["CC6.8", "CC7.2"],
        "kms": ["CC6.5"],
        "lambda": ["CC6.6", "CC7.1"],
        "vpc": ["CC6.6"],
        "guardduty": ["CC7.2"],
        "securityhub": ["CC7.2"],
        "config": ["CC6.6", "CC7.2"],
        "macie": ["CC6.5"],
    }
    return service_controls.get(service.lower(), ["CC6.6"])
