"""
PCI DSS 4.0 Control Definitions for CARL.

This module defines the Payment Card Industry Data Security Standard (PCI DSS) 4.0
requirements with mappings to AWS services, evidence requirements, and implementation guidance.

Reference: https://www.pcisecuritystandards.org/document_library/

PCI DSS 4.0 Structure:
- 12 Requirements grouped into 6 Goals
- Each requirement has multiple sub-requirements
- ~250+ individual controls

Usage:
    from knowledge.pci_dss_controls import PCI_CONTROLS, get_requirement, get_goal_requirements

    # Get specific requirement
    firewall = get_requirement("1")

    # Get all requirements for a goal
    network_controls = get_goal_requirements("build_secure_network")
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PCIRequirement:
    """Definition of a PCI DSS requirement."""

    id: str  # e.g., "1", "1.1", "1.1.1"
    name: str
    description: str
    goal: str  # Goal category
    goal_name: str  # Human-readable goal name

    # Sub-requirements
    sub_requirements: list[dict] = field(default_factory=list)

    # AWS services that help implement this requirement
    aws_services: list[str] = field(default_factory=list)

    # Specific AWS controls/configurations
    aws_controls: list[str] = field(default_factory=list)

    # AWS Config rules that validate this requirement
    config_rules: list[str] = field(default_factory=list)

    # Evidence types to collect for audits
    evidence_types: list[str] = field(default_factory=list)

    # Terraform resources typically involved
    terraform_resources: list[str] = field(default_factory=list)

    # Mapping to other frameworks
    nist_mapping: list[str] = field(default_factory=list)
    soc2_mapping: list[str] = field(default_factory=list)

    # SAQ (Self-Assessment Questionnaire) applicability
    saq_applicable: list[str] = field(default_factory=list)


# =============================================================================
# PCI DSS 4.0 Goals and Requirements
# =============================================================================

# Goal definitions
PCI_GOALS = {
    "build_secure_network": "Build and Maintain a Secure Network and Systems",
    "protect_cardholder_data": "Protect Cardholder Data",
    "vulnerability_management": "Maintain a Vulnerability Management Program",
    "access_control": "Implement Strong Access Control Measures",
    "monitoring_testing": "Regularly Monitor and Test Networks",
    "security_policy": "Maintain an Information Security Policy",
}


PCI_CONTROLS: dict[str, PCIRequirement] = {
    # =========================================================================
    # GOAL 1: Build and Maintain a Secure Network and Systems
    # =========================================================================

    # Requirement 1: Install and Maintain Network Security Controls
    "1": PCIRequirement(
        id="1",
        name="Network Security Controls",
        description="Install and maintain network security controls to protect the cardholder "
                    "data environment (CDE) from unauthorized access.",
        goal="build_secure_network",
        goal_name="Build and Maintain a Secure Network and Systems",
        sub_requirements=[
            {"id": "1.1", "name": "Network security control processes and configuration standards are defined and understood"},
            {"id": "1.2", "name": "Network security controls (NSCs) are configured and maintained"},
            {"id": "1.3", "name": "Network access to and from the CDE is restricted"},
            {"id": "1.4", "name": "Network connections between trusted and untrusted networks are controlled"},
            {"id": "1.5", "name": "Risks to the CDE from computing devices that connect to untrusted networks are mitigated"},
        ],
        aws_services=[
            "VPC", "Security Groups", "NACLs", "Network Firewall",
            "WAF", "Transit Gateway", "PrivateLink", "Client VPN"
        ],
        aws_controls=[
            "Dedicated VPC for CDE (Cardholder Data Environment)",
            "Security groups with explicit allow rules only",
            "Network ACLs for subnet-level filtering",
            "AWS Network Firewall for deep packet inspection",
            "WAF for web application protection",
            "No direct internet access to CDE",
            "VPC endpoints for AWS service access",
            "Transit Gateway for controlled inter-VPC traffic",
            "Private subnets for all CDE resources",
            "Bastion hosts or Systems Manager Session Manager for access",
        ],
        config_rules=[
            "vpc-default-security-group-closed",
            "restricted-ssh",
            "restricted-common-ports",
            "vpc-sg-open-only-to-authorized-ports",
            "ec2-instance-no-public-ip",
            "rds-instance-public-access-check",
            "redshift-cluster-public-access-check",
            "lambda-function-public-access-prohibited",
        ],
        evidence_types=[
            "vpc_configuration",
            "security_group_rules",
            "nacl_rules",
            "network_firewall_rules",
            "vpc_flow_logs",
            "network_diagrams",
        ],
        terraform_resources=[
            "aws_vpc",
            "aws_security_group",
            "aws_security_group_rule",
            "aws_network_acl",
            "aws_networkfirewall_firewall",
            "aws_wafv2_web_acl",
            "aws_vpc_endpoint",
        ],
        nist_mapping=["PR.IR-01", "PR.AA-05"],
        soc2_mapping=["CC6.1", "CC6.6"],
        saq_applicable=["A", "A-EP", "B", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),

    # Requirement 2: Apply Secure Configurations
    "2": PCIRequirement(
        id="2",
        name="Secure Configurations",
        description="Apply secure configurations to all system components to reduce "
                    "vulnerabilities introduced by default settings.",
        goal="build_secure_network",
        goal_name="Build and Maintain a Secure Network and Systems",
        sub_requirements=[
            {"id": "2.1", "name": "Secure configuration processes and configuration standards are defined and understood"},
            {"id": "2.2", "name": "System components are configured and managed securely"},
            {"id": "2.3", "name": "Wireless environments are configured and managed securely"},
        ],
        aws_services=[
            "Systems Manager", "AWS Config", "Service Catalog",
            "EC2 Image Builder", "Inspector", "Security Hub"
        ],
        aws_controls=[
            "Golden AMIs with hardened configurations",
            "AWS Config rules for configuration compliance",
            "Systems Manager State Manager for configuration enforcement",
            "Service Catalog for approved configurations",
            "No default credentials (changed immediately)",
            "Unnecessary services disabled",
            "IMDSv2 required for EC2 instances",
            "EBS encryption by default",
            "Inspector for vulnerability scanning",
        ],
        config_rules=[
            "ec2-instance-managed-by-systems-manager",
            "ec2-imdsv2-check",
            "ec2-no-amazon-key-pair",
            "ebs-optimized-instance",
            "ec2-instance-profile-attached",
            "approved-amis-by-id",
        ],
        evidence_types=[
            "system_configurations",
            "hardening_standards",
            "ami_configurations",
            "config_compliance_status",
            "patch_status",
        ],
        terraform_resources=[
            "aws_launch_template",
            "aws_imagebuilder_image_recipe",
            "aws_ssm_document",
            "aws_config_config_rule",
        ],
        nist_mapping=["PR.PS-01", "PR.PS-02"],
        soc2_mapping=["CC6.1", "CC7.1"],
        saq_applicable=["A", "A-EP", "B", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),

    # =========================================================================
    # GOAL 2: Protect Cardholder Data
    # =========================================================================

    # Requirement 3: Protect Stored Account Data
    "3": PCIRequirement(
        id="3",
        name="Protect Stored Account Data",
        description="Protection methods such as encryption, truncation, masking, and hashing "
                    "are critical components of cardholder data protection.",
        goal="protect_cardholder_data",
        goal_name="Protect Cardholder Data",
        sub_requirements=[
            {"id": "3.1", "name": "Stored account data protection processes and mechanisms are defined and understood"},
            {"id": "3.2", "name": "Storage of account data is kept to a minimum"},
            {"id": "3.3", "name": "Sensitive authentication data (SAD) is not stored after authorization"},
            {"id": "3.4", "name": "Access to displays of full PAN and ability to copy PAN is restricted"},
            {"id": "3.5", "name": "PAN is secured wherever it is stored"},
            {"id": "3.6", "name": "Cryptographic keys used to protect stored account data are secured"},
            {"id": "3.7", "name": "Where cryptography is used to protect stored account data, key management processes are defined"},
        ],
        aws_services=[
            "KMS", "CloudHSM", "DynamoDB", "RDS", "S3",
            "Secrets Manager", "Macie", "Payment Cryptography"
        ],
        aws_controls=[
            "KMS CMK for all cardholder data encryption",
            "CloudHSM for key management (HSM requirement)",
            "AWS Payment Cryptography for payment-specific keys",
            "Field-level encryption for PAN in databases",
            "S3 bucket encryption with KMS",
            "RDS encryption at rest",
            "DynamoDB encryption at rest",
            "Key rotation enabled (annual minimum)",
            "Split knowledge/dual control for key access",
            "Macie for PAN detection in S3",
            "Data masking for PAN display (show only last 4)",
            "Tokenization for stored PANs",
        ],
        config_rules=[
            "cmk-backing-key-rotation-enabled",
            "kms-cmk-not-scheduled-for-deletion",
            "s3-bucket-server-side-encryption-enabled",
            "s3-default-encryption-kms",
            "rds-storage-encrypted",
            "dynamodb-table-encrypted-kms",
            "encrypted-volumes",
            "redshift-cluster-kms-enabled",
        ],
        evidence_types=[
            "kms_key_configuration",
            "encryption_policies",
            "data_retention_policies",
            "tokenization_configuration",
            "key_rotation_records",
            "macie_findings",
        ],
        terraform_resources=[
            "aws_kms_key",
            "aws_kms_alias",
            "aws_cloudhsm_v2_cluster",
            "aws_s3_bucket_server_side_encryption_configuration",
            "aws_db_instance",
            "aws_dynamodb_table",
        ],
        nist_mapping=["PR.DS-01", "PR.DS-02"],
        soc2_mapping=["CC6.7", "C1.1"],
        saq_applicable=["A-EP", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),

    # Requirement 4: Protect Cardholder Data in Transit
    "4": PCIRequirement(
        id="4",
        name="Protect Cardholder Data in Transit",
        description="Protect cardholder data with strong cryptography during transmission "
                    "over open, public networks.",
        goal="protect_cardholder_data",
        goal_name="Protect Cardholder Data",
        sub_requirements=[
            {"id": "4.1", "name": "Processes to protect cardholder data in transit are defined and understood"},
            {"id": "4.2", "name": "PAN is protected with strong cryptography during transmission"},
        ],
        aws_services=[
            "ACM", "ALB/NLB", "CloudFront", "API Gateway",
            "VPN", "Direct Connect", "PrivateLink"
        ],
        aws_controls=[
            "TLS 1.2 or higher required (TLS 1.3 preferred)",
            "ACM certificates for TLS termination",
            "ALB/NLB with HTTPS listeners only",
            "CloudFront with TLS 1.2 minimum",
            "API Gateway with TLS",
            "No HTTP allowed (redirect or block)",
            "VPN or Direct Connect for hybrid connectivity",
            "PrivateLink for private AWS service access",
            "Certificate pinning for mobile apps",
            "HSTS headers enabled",
        ],
        config_rules=[
            "alb-http-to-https-redirection-check",
            "elb-tls-https-listeners-only",
            "api-gw-ssl-enabled",
            "cloudfront-viewer-policy-https",
            "s3-bucket-ssl-requests-only",
            "redshift-require-tls-ssl",
            "elb-predefined-security-policy-ssl-check",
            "acm-certificate-expiration-check",
        ],
        evidence_types=[
            "tls_configuration",
            "certificate_inventory",
            "listener_configuration",
            "security_policy_configuration",
        ],
        terraform_resources=[
            "aws_acm_certificate",
            "aws_lb_listener",
            "aws_cloudfront_distribution",
            "aws_api_gateway_rest_api",
            "aws_vpn_connection",
        ],
        nist_mapping=["PR.DS-02"],
        soc2_mapping=["CC6.7"],
        saq_applicable=["A", "A-EP", "B", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),

    # =========================================================================
    # GOAL 3: Maintain a Vulnerability Management Program
    # =========================================================================

    # Requirement 5: Protect from Malicious Software
    "5": PCIRequirement(
        id="5",
        name="Protect from Malicious Software",
        description="Protect all systems and networks from malicious software using "
                    "anti-malware solutions that are actively maintained.",
        goal="vulnerability_management",
        goal_name="Maintain a Vulnerability Management Program",
        sub_requirements=[
            {"id": "5.1", "name": "Anti-malware processes and mechanisms are defined and understood"},
            {"id": "5.2", "name": "Malicious software is prevented, detected, and addressed"},
            {"id": "5.3", "name": "Anti-malware mechanisms and processes are active, maintained, and monitored"},
            {"id": "5.4", "name": "Anti-phishing mechanisms protect users against phishing attacks"},
        ],
        aws_services=[
            "GuardDuty", "Inspector", "Security Hub",
            "CloudWatch", "Lambda", "ECR"
        ],
        aws_controls=[
            "GuardDuty for malware detection",
            "GuardDuty Malware Protection for EBS",
            "Inspector for vulnerability scanning",
            "ECR image scanning for container malware",
            "CloudWatch alarms for malware indicators",
            "Third-party endpoint protection (CrowdStrike, etc.)",
            "Systems Manager for antivirus deployment",
        ],
        config_rules=[
            "guardduty-enabled-centralized",
            "inspector-lambda-standard-scan-enabled",
            "ecr-private-image-scanning-enabled",
            "ec2-instance-managed-by-systems-manager",
        ],
        evidence_types=[
            "antimalware_configuration",
            "guardduty_findings",
            "inspector_findings",
            "scan_logs",
        ],
        terraform_resources=[
            "aws_guardduty_detector",
            "aws_inspector2_enabler",
            "aws_ecr_repository",
        ],
        nist_mapping=["DE.CM-03", "PR.PS-02"],
        soc2_mapping=["CC6.8"],
        saq_applicable=["A-EP", "B-IP", "C", "C-VT", "D"],
    ),

    # Requirement 6: Develop and Maintain Secure Systems
    "6": PCIRequirement(
        id="6",
        name="Develop and Maintain Secure Systems",
        description="Develop and maintain secure systems and software by applying secure "
                    "development practices and addressing vulnerabilities.",
        goal="vulnerability_management",
        goal_name="Maintain a Vulnerability Management Program",
        sub_requirements=[
            {"id": "6.1", "name": "Security vulnerability processes are defined and understood"},
            {"id": "6.2", "name": "Bespoke and custom software are developed securely"},
            {"id": "6.3", "name": "Security vulnerabilities are identified and addressed"},
            {"id": "6.4", "name": "Public-facing web applications are protected against attacks"},
            {"id": "6.5", "name": "Changes to all system components are managed securely"},
        ],
        aws_services=[
            "CodePipeline", "CodeBuild", "CodeArtifact",
            "Inspector", "WAF", "Systems Manager"
        ],
        aws_controls=[
            "CodePipeline for CI/CD with security gates",
            "CodeBuild with SAST/DAST scanning",
            "CodeArtifact for dependency management",
            "Inspector for continuous vulnerability scanning",
            "WAF for web application protection",
            "Patch management with Systems Manager",
            "Critical patches within 30 days",
            "High severity patches within 90 days",
            "Security code review process",
        ],
        config_rules=[
            "ec2-managedinstance-patch-compliance-status-check",
            "inspector-lambda-standard-scan-enabled",
            "ecr-private-image-scanning-enabled",
        ],
        evidence_types=[
            "patch_management_records",
            "vulnerability_scan_results",
            "code_review_records",
            "change_management_records",
            "waf_rules",
        ],
        terraform_resources=[
            "aws_codepipeline",
            "aws_codebuild_project",
            "aws_wafv2_web_acl",
            "aws_ssm_patch_baseline",
        ],
        nist_mapping=["PR.PS-01", "PR.PS-06", "ID.RA-01"],
        soc2_mapping=["CC7.1", "CC8.1"],
        saq_applicable=["A-EP", "B-IP", "C", "C-VT", "D"],
    ),

    # =========================================================================
    # GOAL 4: Implement Strong Access Control Measures
    # =========================================================================

    # Requirement 7: Restrict Access by Business Need
    "7": PCIRequirement(
        id="7",
        name="Restrict Access by Business Need",
        description="Restrict access to system components and cardholder data to only those "
                    "individuals whose job requires such access.",
        goal="access_control",
        goal_name="Implement Strong Access Control Measures",
        sub_requirements=[
            {"id": "7.1", "name": "Access control processes are defined and understood"},
            {"id": "7.2", "name": "Access to system components and data is appropriately defined and assigned"},
            {"id": "7.3", "name": "Access to system components and data is managed via an access control system"},
        ],
        aws_services=[
            "IAM", "IAM Identity Center", "Organizations",
            "Lake Formation", "Secrets Manager", "Resource Access Manager"
        ],
        aws_controls=[
            "IAM policies with least privilege",
            "IAM Identity Center for centralized access",
            "Service Control Policies for guardrails",
            "Role-based access control (RBAC)",
            "Attribute-based access control (ABAC) with tags",
            "Lake Formation for fine-grained data access",
            "Regular access reviews (quarterly)",
            "Separation of duties",
            "No shared accounts",
        ],
        config_rules=[
            "iam-policy-no-statements-with-admin-access",
            "iam-policy-no-statements-with-full-access",
            "iam-user-no-policies-check",
            "iam-root-access-key-check",
            "iam-user-unused-credentials-check",
        ],
        evidence_types=[
            "iam_policies",
            "access_control_lists",
            "access_review_records",
            "role_assignments",
            "scp_policies",
        ],
        terraform_resources=[
            "aws_iam_policy",
            "aws_iam_role",
            "aws_iam_user",
            "aws_ssoadmin_permission_set",
            "aws_organizations_policy",
        ],
        nist_mapping=["PR.AA-05", "PR.AA-01"],
        soc2_mapping=["CC6.1", "CC6.2", "CC6.3"],
        saq_applicable=["A", "A-EP", "B", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),

    # Requirement 8: Identify Users and Authenticate Access
    "8": PCIRequirement(
        id="8",
        name="Identify Users and Authenticate Access",
        description="Identify users and authenticate access to system components using "
                    "strong authentication methods.",
        goal="access_control",
        goal_name="Implement Strong Access Control Measures",
        sub_requirements=[
            {"id": "8.1", "name": "User identification and authentication processes are defined and understood"},
            {"id": "8.2", "name": "User identification and related accounts are strictly managed"},
            {"id": "8.3", "name": "Strong authentication is established and managed"},
            {"id": "8.4", "name": "Multi-factor authentication (MFA) is implemented"},
            {"id": "8.5", "name": "Single-factor authentication for non-console access is limited"},
            {"id": "8.6", "name": "Use of application and system accounts is strictly managed"},
        ],
        aws_services=[
            "IAM", "IAM Identity Center", "Cognito",
            "Directory Service", "Secrets Manager"
        ],
        aws_controls=[
            "Unique user IDs for all users",
            "MFA required for all CDE access",
            "MFA required for all console access",
            "MFA required for root account",
            "Password policy: 12+ characters, complexity",
            "Password history: 4 passwords remembered",
            "Account lockout after 10 failed attempts",
            "Session timeout: 15 minutes of inactivity",
            "Service accounts with unique credentials",
            "Disable inactive accounts after 90 days",
        ],
        config_rules=[
            "iam-user-mfa-enabled",
            "root-account-mfa-enabled",
            "mfa-enabled-for-iam-console-access",
            "iam-password-policy",
            "access-keys-rotated",
            "iam-user-unused-credentials-check",
        ],
        evidence_types=[
            "mfa_configuration",
            "password_policy",
            "credential_report",
            "access_logs",
            "session_configuration",
        ],
        terraform_resources=[
            "aws_iam_account_password_policy",
            "aws_iam_virtual_mfa_device",
            "aws_cognito_user_pool",
        ],
        nist_mapping=["PR.AA-01", "PR.AA-03"],
        soc2_mapping=["CC6.1"],
        saq_applicable=["A", "A-EP", "B", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),

    # Requirement 9: Restrict Physical Access
    "9": PCIRequirement(
        id="9",
        name="Restrict Physical Access",
        description="Restrict physical access to cardholder data and systems that store, "
                    "process, or transmit cardholder data.",
        goal="access_control",
        goal_name="Implement Strong Access Control Measures",
        sub_requirements=[
            {"id": "9.1", "name": "Physical access control processes are defined and understood"},
            {"id": "9.2", "name": "Physical access controls manage entry into facilities"},
            {"id": "9.3", "name": "Physical access for personnel and visitors is authorized and managed"},
            {"id": "9.4", "name": "Media with cardholder data is securely stored, accessed, and destroyed"},
            {"id": "9.5", "name": "POI devices are protected from tampering and unauthorized substitution"},
        ],
        aws_services=[
            "AWS Data Centers", "S3", "EBS", "Glacier"
        ],
        aws_controls=[
            "AWS manages physical security of data centers",
            "AWS SOC 2 Type II reports for physical controls",
            "S3 lifecycle policies for data destruction",
            "EBS volume encryption",
            "Glacier vault lock for compliance retention",
            "Media sanitization handled by AWS",
        ],
        config_rules=[
            "ebs-encrypted-volumes",
            "s3-bucket-server-side-encryption-enabled",
        ],
        evidence_types=[
            "aws_compliance_reports",
            "data_destruction_records",
            "media_handling_procedures",
        ],
        terraform_resources=[
            "aws_s3_bucket_lifecycle_configuration",
            "aws_glacier_vault_lock",
        ],
        nist_mapping=["PR.AA-06"],
        soc2_mapping=["CC6.4", "CC6.5"],
        saq_applicable=["B", "B-IP", "C-VT", "D", "P2PE"],
    ),

    # =========================================================================
    # GOAL 5: Regularly Monitor and Test Networks
    # =========================================================================

    # Requirement 10: Log and Monitor Access
    "10": PCIRequirement(
        id="10",
        name="Log and Monitor Access",
        description="Log and monitor all access to system components and cardholder data "
                    "to detect and respond to security events.",
        goal="monitoring_testing",
        goal_name="Regularly Monitor and Test Networks",
        sub_requirements=[
            {"id": "10.1", "name": "Logging and monitoring processes are defined and understood"},
            {"id": "10.2", "name": "Audit logs are implemented to support detection of anomalies"},
            {"id": "10.3", "name": "Audit logs are protected from destruction and unauthorized modifications"},
            {"id": "10.4", "name": "Audit logs are reviewed to identify anomalies or suspicious activity"},
            {"id": "10.5", "name": "Audit log history is retained and available for analysis"},
            {"id": "10.6", "name": "Time-synchronization mechanisms support consistent time settings"},
            {"id": "10.7", "name": "Failures of critical security control systems are detected and responded to"},
        ],
        aws_services=[
            "CloudTrail", "CloudWatch Logs", "VPC Flow Logs",
            "S3 Access Logs", "Security Hub", "OpenSearch",
            "Kinesis", "GuardDuty"
        ],
        aws_controls=[
            "CloudTrail enabled in all regions",
            "CloudTrail log file validation enabled",
            "CloudTrail logs encrypted with KMS",
            "CloudTrail logs to S3 with object lock",
            "VPC Flow Logs enabled for CDE VPCs",
            "CloudWatch Logs for application logs",
            "Log retention: 1 year online, archive for compliance",
            "Security Hub for centralized findings",
            "Real-time alerting on security events",
            "NTP synchronization via Amazon Time Sync",
            "Log tamper protection with S3 Object Lock",
        ],
        config_rules=[
            "cloudtrail-enabled",
            "cloud-trail-log-file-validation-enabled",
            "cloudtrail-s3-dataevents-enabled",
            "cloudtrail-security-trail-enabled",
            "vpc-flow-logs-enabled",
            "s3-bucket-logging-enabled",
            "cloudwatch-alarm-action-check",
            "cloudwatch-log-group-encrypted",
        ],
        evidence_types=[
            "cloudtrail_configuration",
            "log_retention_configuration",
            "alerting_configuration",
            "log_review_records",
            "time_sync_configuration",
        ],
        terraform_resources=[
            "aws_cloudtrail",
            "aws_cloudwatch_log_group",
            "aws_flow_log",
            "aws_s3_bucket_object_lock_configuration",
            "aws_cloudwatch_metric_alarm",
        ],
        nist_mapping=["DE.CM-01", "DE.CM-03", "PR.PS-04"],
        soc2_mapping=["CC7.2"],
        saq_applicable=["A", "A-EP", "B", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),

    # Requirement 11: Test Security Regularly
    "11": PCIRequirement(
        id="11",
        name="Test Security Regularly",
        description="Test security of systems and networks regularly to ensure controls "
                    "continue to reflect the changing threat environment.",
        goal="monitoring_testing",
        goal_name="Regularly Monitor and Test Networks",
        sub_requirements=[
            {"id": "11.1", "name": "Security testing processes are defined and understood"},
            {"id": "11.2", "name": "Wireless access points are identified and monitored"},
            {"id": "11.3", "name": "External and internal vulnerabilities are regularly identified"},
            {"id": "11.4", "name": "External and internal penetration testing is regularly performed"},
            {"id": "11.5", "name": "Network intrusions and unexpected file changes are detected and responded to"},
            {"id": "11.6", "name": "Unauthorized changes on payment pages are detected and responded to"},
        ],
        aws_services=[
            "Inspector", "GuardDuty", "Security Hub",
            "Config", "CloudWatch", "Detective"
        ],
        aws_controls=[
            "Inspector for continuous vulnerability scanning",
            "Internal vulnerability scans quarterly minimum",
            "External ASV scans quarterly",
            "Penetration testing annually",
            "GuardDuty for intrusion detection",
            "File integrity monitoring (FIM)",
            "AWS Config for change detection",
            "Security Hub for aggregated findings",
            "Critical/high vulnerabilities fixed within 30 days",
        ],
        config_rules=[
            "inspector-lambda-standard-scan-enabled",
            "guardduty-enabled-centralized",
            "securityhub-enabled",
        ],
        evidence_types=[
            "vulnerability_scan_reports",
            "penetration_test_reports",
            "asv_scan_reports",
            "remediation_records",
            "fim_configuration",
        ],
        terraform_resources=[
            "aws_inspector2_enabler",
            "aws_guardduty_detector",
            "aws_securityhub_account",
        ],
        nist_mapping=["ID.RA-01", "DE.CM-01"],
        soc2_mapping=["CC4.1", "CC7.1"],
        saq_applicable=["A-EP", "B-IP", "C", "D"],
    ),

    # =========================================================================
    # GOAL 6: Maintain an Information Security Policy
    # =========================================================================

    # Requirement 12: Support Information Security with Policies
    "12": PCIRequirement(
        id="12",
        name="Information Security Policy",
        description="Support information security with organizational policies and programs "
                    "that govern how personnel protect cardholder data.",
        goal="security_policy",
        goal_name="Maintain an Information Security Policy",
        sub_requirements=[
            {"id": "12.1", "name": "Information security policy is established, published, and communicated"},
            {"id": "12.2", "name": "Acceptable use policies are defined and understood"},
            {"id": "12.3", "name": "Risks to the CDE are formally identified, evaluated, and managed"},
            {"id": "12.4", "name": "PCI DSS scope is documented and validated"},
            {"id": "12.5", "name": "PCI DSS scope is documented and confirmed by the entity"},
            {"id": "12.6", "name": "Security awareness education is an ongoing activity"},
            {"id": "12.7", "name": "Personnel are screened to reduce risks from insider threats"},
            {"id": "12.8", "name": "Risk to information assets from third party service providers is managed"},
            {"id": "12.9", "name": "Third-party service providers support PCI DSS compliance"},
            {"id": "12.10", "name": "Security incidents and suspected compromises are responded to immediately"},
        ],
        aws_services=[
            "AWS Artifact", "Audit Manager", "Security Hub",
            "Systems Manager Incident Manager", "Organizations"
        ],
        aws_controls=[
            "AWS Artifact for compliance documentation",
            "Audit Manager for compliance assessments",
            "Security Hub for policy violation detection",
            "Incident response plans documented",
            "Incident Manager for response orchestration",
            "Third-party security assessments",
            "Annual PCI scope validation",
            "Security awareness training program",
        ],
        config_rules=[
            "securityhub-enabled",
        ],
        evidence_types=[
            "security_policies",
            "risk_assessments",
            "training_records",
            "incident_response_plans",
            "third_party_agreements",
            "scope_documentation",
        ],
        terraform_resources=[
            "aws_auditmanager_assessment",
            "aws_ssmincidents_response_plan",
        ],
        nist_mapping=["GV.OC", "GV.RM", "GV.SC", "PR.AT"],
        soc2_mapping=["CC1.1", "CC1.2", "CC1.4", "CC2.2", "CC3.1"],
        saq_applicable=["A", "A-EP", "B", "B-IP", "C", "C-VT", "D", "P2PE"],
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_requirement(requirement_id: str) -> PCIRequirement:
    """
    Get a PCI DSS requirement by ID.

    Args:
        requirement_id: Requirement ID (e.g., "1", "3.5", "8.3.1")

    Returns:
        PCIRequirement definition

    Raises:
        KeyError: If requirement_id is not found
    """
    requirement_id = requirement_id.strip()

    # Direct match
    if requirement_id in PCI_CONTROLS:
        return PCI_CONTROLS[requirement_id]

    # Try parent requirement (e.g., "3.5.1" -> "3")
    parent_id = requirement_id.split(".")[0]
    if parent_id in PCI_CONTROLS:
        return PCI_CONTROLS[parent_id]

    raise KeyError(f"PCI DSS requirement not found: {requirement_id}")


def get_goal_requirements(goal: str) -> list[PCIRequirement]:
    """
    Get all requirements for a PCI DSS goal.

    Args:
        goal: Goal identifier (e.g., "build_secure_network", "protect_cardholder_data")

    Returns:
        List of PCIRequirement objects for that goal
    """
    return [r for r in PCI_CONTROLS.values() if r.goal == goal]


def get_all_config_rules() -> list[str]:
    """
    Get all unique AWS Config rules for PCI DSS compliance.

    Returns:
        Deduplicated list of AWS Config rule names
    """
    rules = set()
    for req in PCI_CONTROLS.values():
        rules.update(req.config_rules)
    return sorted(rules)


def get_all_evidence_types() -> list[str]:
    """
    Get all unique evidence types for PCI DSS compliance.

    Returns:
        Deduplicated list of evidence type identifiers
    """
    evidence = set()
    for req in PCI_CONTROLS.values():
        evidence.update(req.evidence_types)
    return sorted(evidence)


def get_saq_requirements(saq_type: str) -> list[PCIRequirement]:
    """
    Get requirements applicable to a specific SAQ type.

    Args:
        saq_type: SAQ type (A, A-EP, B, B-IP, C, C-VT, D, P2PE)

    Returns:
        List of applicable PCIRequirement objects
    """
    return [r for r in PCI_CONTROLS.values() if saq_type in r.saq_applicable]


def map_to_nist(requirement_id: str) -> list[str]:
    """
    Get NIST CSF control mappings for a PCI DSS requirement.

    Args:
        requirement_id: PCI DSS requirement ID

    Returns:
        List of NIST CSF control IDs
    """
    req = get_requirement(requirement_id)
    return req.nist_mapping


def map_to_soc2(requirement_id: str) -> list[str]:
    """
    Get SOC 2 control mappings for a PCI DSS requirement.

    Args:
        requirement_id: PCI DSS requirement ID

    Returns:
        List of SOC 2 control IDs
    """
    req = get_requirement(requirement_id)
    return req.soc2_mapping


def get_requirement_summary() -> list[dict]:
    """
    Get a summary of all PCI DSS requirements for display.

    Returns:
        List of requirement summaries
    """
    return [
        {
            "id": req.id,
            "name": req.name,
            "goal": req.goal,
            "goal_name": req.goal_name,
            "sub_requirements_count": len(req.sub_requirements),
            "aws_services_count": len(req.aws_services),
            "config_rules_count": len(req.config_rules),
        }
        for req in PCI_CONTROLS.values()
    ]


def get_goal_summary() -> dict:
    """
    Get summary statistics by PCI DSS goal.

    Returns:
        Dict with goal identifiers as keys and requirement counts as values
    """
    goals = {}
    for req in PCI_CONTROLS.values():
        if req.goal not in goals:
            goals[req.goal] = {
                "name": req.goal_name,
                "count": 0,
                "requirements": []
            }
        goals[req.goal]["count"] += 1
        goals[req.goal]["requirements"].append(req.id)
    return goals
