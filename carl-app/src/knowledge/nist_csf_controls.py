"""
NIST Cybersecurity Framework (CSF) Control Definitions for CARL.

This module defines the NIST CSF 2.0 framework with its 6 core functions,
categories, and subcategories mapped to AWS services and evidence requirements.

Reference: https://www.nist.gov/cyberframework

NIST CSF Structure:
- 6 Functions: Govern, Identify, Protect, Detect, Respond, Recover
- 22 Categories (e.g., ID.AM, PR.AC)
- 106 Subcategories (specific controls)

Usage:
    from knowledge.nist_csf_controls import NIST_CONTROLS, get_control, get_function_controls

    # Get specific control
    asset_mgmt = get_control("ID.AM")

    # Get all controls for a function
    protect_controls = get_function_controls("PR")
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NISTControl:
    """Definition of a NIST CSF control (category or subcategory)."""

    id: str  # e.g., "ID.AM" or "ID.AM-1"
    name: str
    description: str
    function: str  # GV, ID, PR, DE, RS, RC
    function_name: str  # Govern, Identify, Protect, Detect, Respond, Recover

    # Subcategories (for category-level controls)
    subcategories: list[dict] = field(default_factory=list)

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

    # Mapping to other frameworks
    soc2_mapping: list[str] = field(default_factory=list)
    hipaa_mapping: list[str] = field(default_factory=list)


# =============================================================================
# NIST CSF 2.0 Core Functions and Categories
# =============================================================================

NIST_CONTROLS: dict[str, NISTControl] = {
    # =========================================================================
    # GOVERN (GV) - New in CSF 2.0
    # =========================================================================
    "GV.OC": NISTControl(
        id="GV.OC",
        name="Organizational Context",
        description="The circumstances surrounding the organization's cybersecurity risk "
                    "management decisions are understood.",
        function="GV",
        function_name="Govern",
        subcategories=[
            {"id": "GV.OC-01", "description": "The organizational mission is understood and informs cybersecurity risk management"},
            {"id": "GV.OC-02", "description": "Internal and external stakeholders are understood"},
            {"id": "GV.OC-03", "description": "Legal, regulatory, and contractual requirements are understood"},
            {"id": "GV.OC-04", "description": "Critical objectives, capabilities, and services are understood"},
            {"id": "GV.OC-05", "description": "Outcomes, capabilities, and services that depend on third parties are understood"},
        ],
        aws_services=["AWS Organizations", "AWS Control Tower", "Service Catalog"],
        aws_controls=[
            "AWS Organizations structure documented",
            "Service Control Policies defined",
            "AWS Config for compliance monitoring",
        ],
        config_rules=[],
        evidence_types=["org_structure", "scp_policies", "account_inventory"],
        terraform_resources=["aws_organizations_organization", "aws_organizations_policy"],
        soc2_mapping=["CC1.1", "CC1.2"],
        hipaa_mapping=[],
    ),

    "GV.RM": NISTControl(
        id="GV.RM",
        name="Risk Management Strategy",
        description="The organization's priorities, constraints, risk tolerance, and assumptions "
                    "are established, communicated, and used to support operational risk decisions.",
        function="GV",
        function_name="Govern",
        subcategories=[
            {"id": "GV.RM-01", "description": "Risk management objectives are established and agreed to"},
            {"id": "GV.RM-02", "description": "Risk appetite and risk tolerance statements are established"},
            {"id": "GV.RM-03", "description": "Cybersecurity risk management activities are integrated into enterprise risk management"},
            {"id": "GV.RM-04", "description": "Strategic direction for cybersecurity is established"},
        ],
        aws_services=["Security Hub", "AWS Audit Manager", "AWS Config"],
        aws_controls=[
            "Security Hub enabled with standards",
            "AWS Audit Manager frameworks configured",
            "Risk scoring and prioritization",
        ],
        config_rules=["securityhub-enabled"],
        evidence_types=["security_hub_findings", "audit_manager_assessments"],
        terraform_resources=["aws_securityhub_account", "aws_auditmanager_assessment"],
        soc2_mapping=["CC3.1", "CC3.2"],
        hipaa_mapping=[],
    ),

    "GV.SC": NISTControl(
        id="GV.SC",
        name="Supply Chain Risk Management",
        description="Cyber supply chain risk management processes are identified, established, "
                    "managed, monitored, and improved.",
        function="GV",
        function_name="Govern",
        subcategories=[
            {"id": "GV.SC-01", "description": "Cybersecurity supply chain risk management program is established"},
            {"id": "GV.SC-02", "description": "Cybersecurity roles and responsibilities for suppliers are established"},
            {"id": "GV.SC-03", "description": "Supply chain risk assessment processes are established"},
        ],
        aws_services=["AWS Artifact", "AWS Marketplace", "Inspector"],
        aws_controls=[
            "AWS Artifact compliance reports reviewed",
            "Third-party AMI scanning with Inspector",
            "Software bill of materials (SBOM) for containers",
        ],
        config_rules=["ecr-private-image-scanning-enabled"],
        evidence_types=["artifact_reports", "inspector_findings", "ecr_scan_results"],
        terraform_resources=["aws_ecr_repository"],
        soc2_mapping=["CC9.2"],
        hipaa_mapping=[],
    ),

    # =========================================================================
    # IDENTIFY (ID)
    # =========================================================================
    "ID.AM": NISTControl(
        id="ID.AM",
        name="Asset Management",
        description="The data, personnel, devices, systems, and facilities that enable the "
                    "organization to achieve business purposes are identified and managed.",
        function="ID",
        function_name="Identify",
        subcategories=[
            {"id": "ID.AM-01", "description": "Inventories of hardware managed by the organization are maintained"},
            {"id": "ID.AM-02", "description": "Inventories of software, services, and systems managed by the organization are maintained"},
            {"id": "ID.AM-03", "description": "Representations of the organization's authorized network communication and data flows are maintained"},
            {"id": "ID.AM-04", "description": "Inventories of services provided by suppliers are maintained"},
            {"id": "ID.AM-05", "description": "Assets are prioritized based on classification, criticality, resources, and impact"},
            {"id": "ID.AM-07", "description": "Inventories of data and corresponding metadata are maintained"},
            {"id": "ID.AM-08", "description": "Systems, hardware, software, and services are managed throughout their life cycles"},
        ],
        aws_services=[
            "AWS Config", "Systems Manager", "Resource Groups",
            "Service Catalog", "License Manager", "Resource Explorer"
        ],
        aws_controls=[
            "AWS Config enabled in all regions",
            "Systems Manager inventory enabled",
            "Resource tagging strategy implemented",
            "Service Catalog portfolios defined",
            "Resource Groups for asset organization",
        ],
        config_rules=[
            "ec2-instance-managed-by-systems-manager",
            "required-tags",
            "ec2-stopped-instance",
        ],
        evidence_types=[
            "config_resource_inventory",
            "ssm_inventory",
            "resource_tags",
            "ec2_instances",
            "rds_instances",
            "s3_buckets",
        ],
        terraform_resources=[
            "aws_config_configuration_recorder",
            "aws_ssm_resource_data_sync",
            "aws_resourcegroups_group",
        ],
        soc2_mapping=["CC6.1"],
        hipaa_mapping=["164.312(a)(1)"],
    ),

    "ID.RA": NISTControl(
        id="ID.RA",
        name="Risk Assessment",
        description="The organization understands the cybersecurity risk to organizational "
                    "operations, assets, and individuals.",
        function="ID",
        function_name="Identify",
        subcategories=[
            {"id": "ID.RA-01", "description": "Vulnerabilities in assets are identified, validated, and recorded"},
            {"id": "ID.RA-02", "description": "Cyber threat intelligence is received from information sharing forums and sources"},
            {"id": "ID.RA-03", "description": "Internal and external threats to the organization are identified and recorded"},
            {"id": "ID.RA-04", "description": "Potential impacts and likelihoods of threats exploiting vulnerabilities are identified"},
            {"id": "ID.RA-05", "description": "Threats, vulnerabilities, likelihoods, and impacts are used to understand inherent risk"},
            {"id": "ID.RA-06", "description": "Risk responses are identified and prioritized"},
        ],
        aws_services=[
            "Inspector", "GuardDuty", "Security Hub",
            "Macie", "Detective", "IAM Access Analyzer"
        ],
        aws_controls=[
            "Inspector enabled for vulnerability scanning",
            "GuardDuty enabled for threat detection",
            "Security Hub aggregates findings",
            "IAM Access Analyzer for permission analysis",
            "Macie for data classification",
        ],
        config_rules=[
            "inspector-lambda-standard-scan-enabled",
            "guardduty-enabled-centralized",
            "securityhub-enabled",
        ],
        evidence_types=[
            "inspector_findings",
            "guardduty_findings",
            "security_hub_findings",
            "iam_access_analyzer_findings",
            "macie_findings",
        ],
        terraform_resources=[
            "aws_inspector2_enabler",
            "aws_guardduty_detector",
            "aws_securityhub_account",
            "aws_accessanalyzer_analyzer",
            "aws_macie2_account",
        ],
        soc2_mapping=["CC3.2", "CC4.1"],
        hipaa_mapping=["164.308(a)(1)(ii)(A)"],
    ),

    "ID.IM": NISTControl(
        id="ID.IM",
        name="Improvement",
        description="Improvements to organizational cybersecurity risk management processes, "
                    "procedures, and activities are identified.",
        function="ID",
        function_name="Identify",
        subcategories=[
            {"id": "ID.IM-01", "description": "Improvements are identified from evaluations"},
            {"id": "ID.IM-02", "description": "Improvements are identified from security tests and exercises"},
            {"id": "ID.IM-03", "description": "Improvements are identified from execution of operational processes"},
            {"id": "ID.IM-04", "description": "Incident response plans and other cybersecurity plans are improved"},
        ],
        aws_services=["AWS Audit Manager", "Security Hub", "Well-Architected Tool"],
        aws_controls=[
            "Regular Well-Architected reviews",
            "Audit Manager continuous assessments",
            "Security Hub insight tracking",
        ],
        config_rules=[],
        evidence_types=["well_architected_reviews", "audit_assessments"],
        terraform_resources=[],
        soc2_mapping=["CC4.2"],
        hipaa_mapping=["164.308(a)(8)"],
    ),

    # =========================================================================
    # PROTECT (PR)
    # =========================================================================
    "PR.AA": NISTControl(
        id="PR.AA",
        name="Identity Management, Authentication, and Access Control",
        description="Access to physical and logical assets is limited to authorized users, "
                    "services, and hardware and managed commensurate with the assessed risk.",
        function="PR",
        function_name="Protect",
        subcategories=[
            {"id": "PR.AA-01", "description": "Identities and credentials for authorized users, services, and hardware are managed"},
            {"id": "PR.AA-02", "description": "Identities are proofed and bound to credentials based on context"},
            {"id": "PR.AA-03", "description": "Users, services, and hardware are authenticated"},
            {"id": "PR.AA-04", "description": "Identity assertions are protected, conveyed, and verified"},
            {"id": "PR.AA-05", "description": "Access permissions, entitlements, and authorizations are defined and managed"},
            {"id": "PR.AA-06", "description": "Physical access to assets is managed, monitored, and enforced"},
        ],
        aws_services=[
            "IAM", "IAM Identity Center", "Cognito",
            "Directory Service", "Secrets Manager", "KMS"
        ],
        aws_controls=[
            "IAM Identity Center for centralized access",
            "MFA required for all users",
            "Strong password policy (14+ characters)",
            "Access keys rotated every 90 days",
            "Least privilege IAM policies",
            "Service control policies for guardrails",
            "Cognito for application authentication",
        ],
        config_rules=[
            "iam-password-policy",
            "iam-user-mfa-enabled",
            "root-account-mfa-enabled",
            "access-keys-rotated",
            "iam-user-no-policies-check",
            "iam-root-access-key-check",
            "iam-policy-no-statements-with-admin-access",
            "iam-policy-no-statements-with-full-access",
        ],
        evidence_types=[
            "iam_credential_report",
            "iam_password_policy",
            "mfa_devices",
            "iam_policies",
            "sso_configuration",
            "scp_policies",
        ],
        terraform_resources=[
            "aws_iam_account_password_policy",
            "aws_iam_user",
            "aws_iam_policy",
            "aws_iam_role",
            "aws_ssoadmin_permission_set",
            "aws_organizations_policy",
        ],
        soc2_mapping=["CC6.1", "CC6.2", "CC6.3"],
        hipaa_mapping=["164.312(a)(1)", "164.312(d)"],
    ),

    "PR.AT": NISTControl(
        id="PR.AT",
        name="Awareness and Training",
        description="The organization's personnel are provided cybersecurity awareness and "
                    "training so they can perform their cybersecurity-related duties.",
        function="PR",
        function_name="Protect",
        subcategories=[
            {"id": "PR.AT-01", "description": "Personnel are provided awareness and training"},
            {"id": "PR.AT-02", "description": "Individuals in specialized roles are provided awareness and training"},
        ],
        aws_services=["AWS Training", "AWS Skill Builder"],
        aws_controls=[
            "Security awareness training completed",
            "Role-based security training",
            "Phishing simulation exercises",
        ],
        config_rules=[],
        evidence_types=["training_records", "certification_records"],
        terraform_resources=[],
        soc2_mapping=["CC1.4"],
        hipaa_mapping=["164.308(a)(5)"],
    ),

    "PR.DS": NISTControl(
        id="PR.DS",
        name="Data Security",
        description="Data are managed consistent with the organization's risk strategy to "
                    "protect the confidentiality, integrity, and availability of information.",
        function="PR",
        function_name="Protect",
        subcategories=[
            {"id": "PR.DS-01", "description": "The confidentiality, integrity, and availability of data-at-rest are protected"},
            {"id": "PR.DS-02", "description": "The confidentiality, integrity, and availability of data-in-transit are protected"},
            {"id": "PR.DS-10", "description": "The confidentiality, integrity, and availability of data-in-use are protected"},
            {"id": "PR.DS-11", "description": "Backups of data are created, protected, maintained, and tested"},
        ],
        aws_services=[
            "KMS", "S3", "EBS", "RDS", "DynamoDB",
            "ACM", "CloudFront", "ALB/NLB", "AWS Backup",
            "Macie", "CloudHSM"
        ],
        aws_controls=[
            "KMS CMK for all encryption",
            "S3 default encryption enabled",
            "S3 bucket versioning enabled",
            "EBS encryption by default",
            "RDS encryption at rest",
            "DynamoDB encryption at rest",
            "TLS 1.2+ for all connections",
            "HTTPS enforced (no HTTP)",
            "VPC endpoints for AWS services",
            "AWS Backup for centralized backups",
            "Cross-region backup replication",
        ],
        config_rules=[
            "s3-bucket-server-side-encryption-enabled",
            "s3-default-encryption-kms",
            "s3-bucket-ssl-requests-only",
            "encrypted-volumes",
            "rds-storage-encrypted",
            "dynamodb-table-encrypted-kms",
            "cmk-backing-key-rotation-enabled",
            "alb-http-to-https-redirection-check",
            "elb-tls-https-listeners-only",
            "backup-plan-min-frequency-and-min-retention-check",
            "s3-bucket-versioning-enabled",
        ],
        evidence_types=[
            "kms_keys",
            "s3_encryption_config",
            "ebs_encryption_config",
            "rds_encryption_config",
            "tls_certificates",
            "backup_plans",
            "backup_vaults",
        ],
        terraform_resources=[
            "aws_kms_key",
            "aws_s3_bucket_server_side_encryption_configuration",
            "aws_ebs_encryption_by_default",
            "aws_db_instance",
            "aws_backup_plan",
            "aws_backup_vault",
        ],
        soc2_mapping=["CC6.7", "A1.2"],
        hipaa_mapping=["164.312(a)(2)(iv)", "164.312(c)(1)", "164.312(e)(1)"],
    ),

    "PR.PS": NISTControl(
        id="PR.PS",
        name="Platform Security",
        description="The hardware, software, and services of physical and virtual platforms "
                    "are managed consistent with risk strategy.",
        function="PR",
        function_name="Protect",
        subcategories=[
            {"id": "PR.PS-01", "description": "Configuration management practices are established and applied"},
            {"id": "PR.PS-02", "description": "Software is maintained, replaced, and removed"},
            {"id": "PR.PS-03", "description": "Hardware is maintained, replaced, and removed"},
            {"id": "PR.PS-04", "description": "Log records are generated and made available for analysis"},
            {"id": "PR.PS-05", "description": "Installation and execution of unauthorized software is prevented"},
            {"id": "PR.PS-06", "description": "Secure software development practices are integrated"},
        ],
        aws_services=[
            "Systems Manager", "AWS Config", "CloudTrail",
            "CodePipeline", "CodeBuild", "Inspector", "ECR"
        ],
        aws_controls=[
            "SSM Patch Manager for patching",
            "AWS Config for configuration compliance",
            "CloudTrail for API logging",
            "CodePipeline with security scanning",
            "Inspector for vulnerability scanning",
            "ECR image scanning enabled",
            "IMDSv2 required for EC2",
        ],
        config_rules=[
            "ec2-instance-managed-by-systems-manager",
            "ec2-managedinstance-patch-compliance-status-check",
            "cloudtrail-enabled",
            "cloud-trail-log-file-validation-enabled",
            "ec2-imdsv2-check",
            "ecr-private-image-scanning-enabled",
        ],
        evidence_types=[
            "ssm_patch_compliance",
            "config_compliance",
            "cloudtrail_config",
            "ecr_scan_findings",
        ],
        terraform_resources=[
            "aws_ssm_patch_baseline",
            "aws_config_config_rule",
            "aws_cloudtrail",
            "aws_ecr_repository",
        ],
        soc2_mapping=["CC6.1", "CC7.1", "CC8.1"],
        hipaa_mapping=["164.312(b)"],
    ),

    "PR.IR": NISTControl(
        id="PR.IR",
        name="Technology Infrastructure Resilience",
        description="Security architectures are managed with the organization's risk strategy "
                    "to protect asset confidentiality, integrity, and availability.",
        function="PR",
        function_name="Protect",
        subcategories=[
            {"id": "PR.IR-01", "description": "Networks and environments are protected from unauthorized logical access"},
            {"id": "PR.IR-02", "description": "The organization's technology assets are protected from environmental threats"},
            {"id": "PR.IR-03", "description": "Mechanisms are implemented to achieve resilience requirements"},
            {"id": "PR.IR-04", "description": "Adequate resource capacity to ensure availability is maintained"},
        ],
        aws_services=[
            "VPC", "Security Groups", "NACLs", "WAF",
            "Shield", "Network Firewall", "Transit Gateway",
            "Auto Scaling", "Multi-AZ", "Multi-Region"
        ],
        aws_controls=[
            "VPC with private subnets",
            "Security groups with least privilege",
            "NACLs for subnet-level filtering",
            "WAF for web application protection",
            "Shield Advanced for DDoS protection",
            "Network Firewall for inspection",
            "Multi-AZ deployments",
            "Auto Scaling for capacity",
            "Cross-region replication",
        ],
        config_rules=[
            "vpc-default-security-group-closed",
            "restricted-ssh",
            "restricted-common-ports",
            "vpc-sg-open-only-to-authorized-ports",
            "rds-multi-az-support",
            "dynamodb-autoscaling-enabled",
            "elb-cross-zone-load-balancing-enabled",
        ],
        evidence_types=[
            "vpc_config",
            "security_groups",
            "nacls",
            "waf_rules",
            "auto_scaling_config",
        ],
        terraform_resources=[
            "aws_vpc",
            "aws_security_group",
            "aws_network_acl",
            "aws_wafv2_web_acl",
            "aws_autoscaling_group",
        ],
        soc2_mapping=["CC6.6", "A1.1", "A1.2"],
        hipaa_mapping=["164.312(a)(1)"],
    ),

    # =========================================================================
    # DETECT (DE)
    # =========================================================================
    "DE.CM": NISTControl(
        id="DE.CM",
        name="Continuous Monitoring",
        description="Assets are monitored to find anomalies, indicators of compromise, and "
                    "other potentially adverse events.",
        function="DE",
        function_name="Detect",
        subcategories=[
            {"id": "DE.CM-01", "description": "Networks and network services are monitored for anomalies"},
            {"id": "DE.CM-02", "description": "The physical environment is monitored for anomalies"},
            {"id": "DE.CM-03", "description": "Computing hardware and software, runtime environments, and their data are monitored"},
            {"id": "DE.CM-06", "description": "External service provider activities and services are monitored"},
            {"id": "DE.CM-09", "description": "Computing hardware and software, runtime environments, and their data are monitored"},
        ],
        aws_services=[
            "GuardDuty", "Security Hub", "CloudWatch",
            "VPC Flow Logs", "CloudTrail", "Detective",
            "Inspector", "Macie"
        ],
        aws_controls=[
            "GuardDuty enabled in all regions",
            "Security Hub enabled with findings aggregation",
            "CloudWatch alarms for critical metrics",
            "VPC Flow Logs enabled",
            "CloudTrail enabled in all regions",
            "Detective for investigation",
            "Inspector continuous scanning",
        ],
        config_rules=[
            "guardduty-enabled-centralized",
            "securityhub-enabled",
            "cloudwatch-alarm-action-check",
            "vpc-flow-logs-enabled",
            "cloudtrail-enabled",
            "inspector-lambda-standard-scan-enabled",
        ],
        evidence_types=[
            "guardduty_findings",
            "security_hub_findings",
            "cloudwatch_alarms",
            "vpc_flow_logs",
            "cloudtrail_events",
            "inspector_findings",
        ],
        terraform_resources=[
            "aws_guardduty_detector",
            "aws_securityhub_account",
            "aws_cloudwatch_metric_alarm",
            "aws_flow_log",
            "aws_cloudtrail",
            "aws_inspector2_enabler",
        ],
        soc2_mapping=["CC7.1", "CC7.2"],
        hipaa_mapping=["164.312(b)"],
    ),

    "DE.AE": NISTControl(
        id="DE.AE",
        name="Adverse Event Analysis",
        description="Anomalies, indicators of compromise, and other potentially adverse "
                    "events are analyzed to characterize the events and detect incidents.",
        function="DE",
        function_name="Detect",
        subcategories=[
            {"id": "DE.AE-02", "description": "Potentially adverse events are analyzed to understand the attack"},
            {"id": "DE.AE-03", "description": "Information is correlated from multiple sources"},
            {"id": "DE.AE-04", "description": "The estimated impact and scope of adverse events are understood"},
            {"id": "DE.AE-06", "description": "Information on adverse events is provided to authorized staff and tools"},
            {"id": "DE.AE-07", "description": "Cyber threat intelligence and other contextual information are integrated"},
            {"id": "DE.AE-08", "description": "Incidents are declared when adverse events meet incident criteria"},
        ],
        aws_services=[
            "Detective", "Security Hub", "CloudWatch Logs Insights",
            "Athena", "OpenSearch", "EventBridge"
        ],
        aws_controls=[
            "Detective for investigation workflows",
            "Security Hub insights and custom actions",
            "CloudWatch Logs Insights for log analysis",
            "Centralized logging with OpenSearch",
            "EventBridge rules for event correlation",
        ],
        config_rules=[
            "securityhub-enabled",
        ],
        evidence_types=[
            "detective_investigations",
            "security_hub_insights",
            "log_analysis_queries",
        ],
        terraform_resources=[
            "aws_detective_graph",
            "aws_cloudwatch_query_definition",
            "aws_cloudwatch_event_rule",
        ],
        soc2_mapping=["CC7.3", "CC7.4"],
        hipaa_mapping=["164.308(a)(6)(ii)"],
    ),

    # =========================================================================
    # RESPOND (RS)
    # =========================================================================
    "RS.MA": NISTControl(
        id="RS.MA",
        name="Incident Management",
        description="Responses to detected cybersecurity incidents are managed.",
        function="RS",
        function_name="Respond",
        subcategories=[
            {"id": "RS.MA-01", "description": "The incident response plan is executed in coordination with relevant third parties"},
            {"id": "RS.MA-02", "description": "Incident reports are triaged and validated"},
            {"id": "RS.MA-03", "description": "Incidents are categorized and prioritized"},
            {"id": "RS.MA-04", "description": "Incidents are escalated or elevated as needed"},
            {"id": "RS.MA-05", "description": "The criteria for initiating incident recovery are applied"},
        ],
        aws_services=[
            "Systems Manager Incident Manager", "Security Hub",
            "SNS", "EventBridge", "Lambda"
        ],
        aws_controls=[
            "Incident Manager runbooks defined",
            "Security Hub custom actions",
            "SNS topics for incident notification",
            "EventBridge rules for automated response",
            "Lambda for automated remediation",
        ],
        config_rules=[],
        evidence_types=[
            "incident_response_plans",
            "runbooks",
            "incident_records",
        ],
        terraform_resources=[
            "aws_ssmincidents_response_plan",
            "aws_sns_topic",
            "aws_cloudwatch_event_rule",
        ],
        soc2_mapping=["CC7.4", "CC7.5"],
        hipaa_mapping=["164.308(a)(6)"],
    ),

    "RS.AN": NISTControl(
        id="RS.AN",
        name="Incident Analysis",
        description="Investigations are conducted to ensure effective response and support "
                    "forensics and recovery activities.",
        function="RS",
        function_name="Respond",
        subcategories=[
            {"id": "RS.AN-03", "description": "Analysis is performed to establish what has taken place"},
            {"id": "RS.AN-06", "description": "Actions performed during an investigation are recorded"},
            {"id": "RS.AN-07", "description": "Incident data and metadata are collected and their integrity preserved"},
            {"id": "RS.AN-08", "description": "An incident's magnitude is estimated and validated"},
        ],
        aws_services=[
            "Detective", "CloudTrail Lake", "Athena",
            "S3", "CloudWatch Logs"
        ],
        aws_controls=[
            "Detective for automated investigation",
            "CloudTrail Lake for long-term log retention",
            "Athena for log querying",
            "S3 with Object Lock for evidence preservation",
            "Immutable audit logs",
        ],
        config_rules=[
            "cloud-trail-log-file-validation-enabled",
            "s3-bucket-versioning-enabled",
        ],
        evidence_types=[
            "investigation_reports",
            "forensic_evidence",
            "audit_logs",
        ],
        terraform_resources=[
            "aws_detective_graph",
            "aws_cloudtrail",
            "aws_s3_bucket_object_lock_configuration",
        ],
        soc2_mapping=["CC7.3"],
        hipaa_mapping=["164.308(a)(6)(ii)"],
    ),

    "RS.CO": NISTControl(
        id="RS.CO",
        name="Incident Response Reporting and Communication",
        description="Response activities are coordinated with internal and external stakeholders.",
        function="RS",
        function_name="Respond",
        subcategories=[
            {"id": "RS.CO-02", "description": "Internal and external stakeholders are notified of incidents"},
            {"id": "RS.CO-03", "description": "Information is shared consistent with response plans"},
        ],
        aws_services=["SNS", "SES", "EventBridge"],
        aws_controls=[
            "SNS for stakeholder notifications",
            "SES for email notifications",
            "EventBridge for cross-account sharing",
        ],
        config_rules=[],
        evidence_types=["notification_records", "communication_logs"],
        terraform_resources=["aws_sns_topic", "aws_ses_email_identity"],
        soc2_mapping=["CC2.2", "CC2.3"],
        hipaa_mapping=["164.308(a)(6)(ii)"],
    ),

    "RS.MI": NISTControl(
        id="RS.MI",
        name="Incident Mitigation",
        description="Activities are performed to prevent expansion of an event and mitigate its effects.",
        function="RS",
        function_name="Respond",
        subcategories=[
            {"id": "RS.MI-01", "description": "Incidents are contained"},
            {"id": "RS.MI-02", "description": "Incidents are eradicated"},
        ],
        aws_services=[
            "Security Groups", "NACLs", "WAF",
            "Systems Manager", "Lambda", "Step Functions"
        ],
        aws_controls=[
            "Security group isolation for containment",
            "NACL rules for network isolation",
            "WAF rules for attack blocking",
            "SSM Automation for remediation",
            "Lambda for automated response",
        ],
        config_rules=[],
        evidence_types=["containment_actions", "remediation_records"],
        terraform_resources=[
            "aws_security_group",
            "aws_network_acl",
            "aws_wafv2_rule_group",
        ],
        soc2_mapping=["CC7.4"],
        hipaa_mapping=["164.308(a)(6)"],
    ),

    # =========================================================================
    # RECOVER (RC)
    # =========================================================================
    "RC.RP": NISTControl(
        id="RC.RP",
        name="Incident Recovery Plan Execution",
        description="Restoration activities are performed to ensure operational availability.",
        function="RC",
        function_name="Recover",
        subcategories=[
            {"id": "RC.RP-01", "description": "The recovery portion of the incident response plan is executed"},
            {"id": "RC.RP-02", "description": "Recovery actions are selected, scoped, prioritized, and performed"},
            {"id": "RC.RP-03", "description": "The integrity of backups and other restoration assets is verified"},
            {"id": "RC.RP-04", "description": "Critical mission functions and cybersecurity risk management are considered"},
            {"id": "RC.RP-05", "description": "The integrity of restored assets is verified, systems tested, and declared operational"},
            {"id": "RC.RP-06", "description": "The end of incident recovery is declared based on criteria"},
        ],
        aws_services=[
            "AWS Backup", "CloudEndure", "Elastic Disaster Recovery",
            "S3", "RDS", "DynamoDB"
        ],
        aws_controls=[
            "AWS Backup plans for all critical data",
            "Cross-region backup replication",
            "Regular backup testing",
            "RDS automated snapshots",
            "DynamoDB point-in-time recovery",
            "Elastic Disaster Recovery for servers",
        ],
        config_rules=[
            "backup-plan-min-frequency-and-min-retention-check",
            "backup-recovery-point-minimum-retention-check",
            "dynamodb-pitr-enabled",
            "db-instance-backup-enabled",
        ],
        evidence_types=[
            "backup_plans",
            "recovery_tests",
            "restoration_records",
        ],
        terraform_resources=[
            "aws_backup_plan",
            "aws_backup_vault",
            "aws_db_instance",
            "aws_dynamodb_table",
        ],
        soc2_mapping=["A1.2", "A1.3"],
        hipaa_mapping=["164.308(a)(7)", "164.312(c)(1)"],
    ),

    "RC.CO": NISTControl(
        id="RC.CO",
        name="Incident Recovery Communication",
        description="Restoration activities are coordinated with internal and external parties.",
        function="RC",
        function_name="Recover",
        subcategories=[
            {"id": "RC.CO-03", "description": "Recovery activities and progress are communicated to stakeholders"},
            {"id": "RC.CO-04", "description": "Public updates on incident recovery are shared"},
        ],
        aws_services=["SNS", "SES", "EventBridge"],
        aws_controls=[
            "Status page updates",
            "Stakeholder notifications",
            "Recovery status dashboards",
        ],
        config_rules=[],
        evidence_types=["recovery_communications", "status_updates"],
        terraform_resources=["aws_sns_topic"],
        soc2_mapping=["CC2.2"],
        hipaa_mapping=["164.308(a)(6)(ii)"],
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_control(control_id: str) -> NISTControl:
    """
    Get a NIST CSF control by ID.

    Args:
        control_id: Control ID (e.g., "ID.AM", "PR.DS-01")

    Returns:
        NISTControl definition

    Raises:
        KeyError: If control_id is not found
    """
    control_id = control_id.strip().upper()

    if control_id in NIST_CONTROLS:
        return NIST_CONTROLS[control_id]

    # Try to find parent control if subcategory specified
    # e.g., "ID.AM-01" -> "ID.AM"
    parent_id = "-".join(control_id.split("-")[:-1]) if "-" in control_id else control_id
    if parent_id in NIST_CONTROLS:
        return NIST_CONTROLS[parent_id]

    raise KeyError(f"NIST CSF control not found: {control_id}")


def get_function_controls(function: str) -> list[NISTControl]:
    """
    Get all controls for a NIST CSF function.

    Args:
        function: Function code (GV, ID, PR, DE, RS, RC)

    Returns:
        List of NISTControl objects for that function
    """
    function = function.upper()
    return [c for c in NIST_CONTROLS.values() if c.function == function]


def get_all_config_rules() -> list[str]:
    """
    Get all unique AWS Config rules for NIST CSF compliance.

    Returns:
        Deduplicated list of AWS Config rule names
    """
    rules = set()
    for control in NIST_CONTROLS.values():
        rules.update(control.config_rules)
    return sorted(rules)


def get_all_evidence_types() -> list[str]:
    """
    Get all unique evidence types for NIST CSF compliance.

    Returns:
        Deduplicated list of evidence type identifiers
    """
    evidence = set()
    for control in NIST_CONTROLS.values():
        evidence.update(control.evidence_types)
    return sorted(evidence)


def map_to_soc2(control_id: str) -> list[str]:
    """
    Get SOC 2 control mappings for a NIST CSF control.

    Args:
        control_id: NIST CSF control ID

    Returns:
        List of SOC 2 control IDs
    """
    control = get_control(control_id)
    return control.soc2_mapping


def map_to_hipaa(control_id: str) -> list[str]:
    """
    Get HIPAA control mappings for a NIST CSF control.

    Args:
        control_id: NIST CSF control ID

    Returns:
        List of HIPAA control IDs
    """
    control = get_control(control_id)
    return control.hipaa_mapping


def get_control_summary() -> list[dict]:
    """
    Get a summary of all NIST CSF controls for display.

    Returns:
        List of control summaries grouped by function
    """
    return [
        {
            "id": control.id,
            "name": control.name,
            "function": control.function,
            "function_name": control.function_name,
            "aws_services_count": len(control.aws_services),
            "config_rules_count": len(control.config_rules),
        }
        for control in NIST_CONTROLS.values()
    ]


def get_function_summary() -> dict:
    """
    Get summary statistics by NIST CSF function.

    Returns:
        Dict with function codes as keys and control counts as values
    """
    functions = {}
    for control in NIST_CONTROLS.values():
        if control.function not in functions:
            functions[control.function] = {
                "name": control.function_name,
                "count": 0,
                "controls": []
            }
        functions[control.function]["count"] += 1
        functions[control.function]["controls"].append(control.id)
    return functions
