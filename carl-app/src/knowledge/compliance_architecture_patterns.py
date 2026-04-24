"""
Compliance-Specific Architecture Patterns for CARL.

This module provides architecture patterns optimized for specific compliance frameworks:
- HIPAA (Healthcare)
- PCI DSS (Payment Card Industry)
- NIST CSF (General Cybersecurity)

These patterns are used as AI grounding context when generating Terraform code
or providing architecture recommendations for compliance workloads.

Usage:
    from knowledge.compliance_architecture_patterns import (
        HIPAA_PATTERNS, PCI_DSS_PATTERNS, NIST_CSF_PATTERNS,
        get_patterns_by_framework
    )

    # Get all HIPAA patterns
    hipaa_patterns = get_patterns_by_framework("hipaa")

    # Get specific pattern
    phi_storage = HIPAA_PATTERNS["phi_storage"]
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CompliancePattern:
    """Architecture pattern for compliance workloads."""

    id: str
    name: str
    framework: str  # hipaa, pci_dss, nist_csf
    description: str
    use_case: str

    # Compliance mappings
    controls_addressed: list[str] = field(default_factory=list)

    # Architecture components
    aws_services: list[str] = field(default_factory=list)
    key_configurations: list[str] = field(default_factory=list)

    # Cost and complexity
    estimated_monthly_cost: str = ""
    complexity: str = "medium"  # low, medium, high

    # Pros and cons
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)

    # Terraform modules/resources
    terraform_resources: list[str] = field(default_factory=list)

    # Security considerations
    security_notes: list[str] = field(default_factory=list)


# =============================================================================
# HIPAA Architecture Patterns
# =============================================================================

HIPAA_PATTERNS: dict[str, CompliancePattern] = {
    "phi_storage_encrypted": CompliancePattern(
        id="phi_storage_encrypted",
        name="Encrypted PHI Storage",
        framework="hipaa",
        description="Secure storage architecture for Protected Health Information (PHI) with "
                    "encryption at rest using customer-managed KMS keys.",
        use_case="Storing patient records, medical images, lab results, or any ePHI data",
        controls_addressed=[
            "164.312(a)(2)(iv) - Encryption and Decryption",
            "164.312(c)(1) - Integrity",
            "164.312(e)(1) - Transmission Security",
        ],
        aws_services=[
            "S3", "KMS", "Macie", "CloudTrail", "IAM"
        ],
        key_configurations=[
            "KMS CMK with automatic key rotation enabled",
            "S3 bucket with SSE-KMS encryption (aws:kms)",
            "S3 bucket policy requiring encrypted uploads",
            "S3 versioning enabled for data integrity",
            "S3 Object Lock for immutability (optional)",
            "Macie enabled for PHI detection",
            "S3 access logging to separate bucket",
            "VPC endpoint for S3 (no public internet)",
            "IAM policies with least privilege access",
            "CloudTrail data events for S3 enabled",
        ],
        estimated_monthly_cost="$50-200 (varies by storage volume)",
        complexity="medium",
        pros=[
            "HIPAA-compliant encryption at rest",
            "Automatic key rotation reduces key management burden",
            "Macie detects accidental PHI exposure",
            "Versioning protects against accidental deletion",
            "Full audit trail via CloudTrail",
        ],
        cons=[
            "KMS costs per API call (~$0.03 per 10,000 requests)",
            "Macie costs based on data scanned",
            "Requires BAA with AWS in place",
        ],
        terraform_resources=[
            "aws_kms_key",
            "aws_kms_alias",
            "aws_s3_bucket",
            "aws_s3_bucket_server_side_encryption_configuration",
            "aws_s3_bucket_versioning",
            "aws_s3_bucket_logging",
            "aws_s3_bucket_policy",
            "aws_macie2_account",
            "aws_macie2_classification_job",
            "aws_vpc_endpoint",
        ],
        security_notes=[
            "Ensure AWS BAA is signed before storing PHI",
            "Only use HIPAA-eligible AWS services",
            "Implement MFA delete for critical buckets",
            "Consider S3 Object Lock for compliance retention",
        ],
    ),

    "phi_database_rds": CompliancePattern(
        id="phi_database_rds",
        name="HIPAA-Compliant RDS Database",
        framework="hipaa",
        description="Relational database architecture for PHI with encryption, audit logging, "
                    "and high availability.",
        use_case="Electronic Health Records (EHR), patient databases, healthcare applications",
        controls_addressed=[
            "164.312(a)(1) - Access Control",
            "164.312(a)(2)(iv) - Encryption",
            "164.312(b) - Audit Controls",
            "164.312(c)(1) - Integrity",
            "164.312(e)(1) - Transmission Security",
        ],
        aws_services=[
            "RDS", "KMS", "CloudWatch", "Secrets Manager", "IAM"
        ],
        key_configurations=[
            "RDS encryption at rest with KMS CMK",
            "RDS SSL/TLS required for connections",
            "Multi-AZ deployment for availability",
            "Automated backups with 35-day retention",
            "Enhanced monitoring enabled",
            "Performance Insights enabled",
            "Audit logging to CloudWatch (MySQL/PostgreSQL)",
            "Deletion protection enabled",
            "Private subnet only (no public access)",
            "Security group restricts access to app layer only",
            "Secrets Manager for credential rotation",
            "IAM authentication where supported",
        ],
        estimated_monthly_cost="$200-1000 (varies by instance size)",
        complexity="medium",
        pros=[
            "Managed service reduces operational burden",
            "Automatic patching and backups",
            "Multi-AZ provides 99.95% availability SLA",
            "Native audit logging capabilities",
            "Automatic credential rotation with Secrets Manager",
        ],
        cons=[
            "Multi-AZ doubles instance costs",
            "Storage costs for 35-day backup retention",
            "Performance Insights adds ~$25/month per instance",
        ],
        terraform_resources=[
            "aws_db_instance",
            "aws_db_subnet_group",
            "aws_db_parameter_group",
            "aws_kms_key",
            "aws_security_group",
            "aws_secretsmanager_secret",
            "aws_secretsmanager_secret_rotation",
            "aws_cloudwatch_log_group",
        ],
        security_notes=[
            "Enable SSL certificate verification in application",
            "Use IAM authentication instead of passwords where possible",
            "Implement connection pooling to reduce credential exposure",
            "Regular access reviews for database users",
        ],
    ),

    "hipaa_vpc_isolation": CompliancePattern(
        id="hipaa_vpc_isolation",
        name="HIPAA-Isolated VPC Architecture",
        framework="hipaa",
        description="Network isolation architecture for HIPAA workloads with private subnets, "
                    "VPC endpoints, and strict access controls.",
        use_case="Healthcare applications processing PHI, isolated from non-HIPAA workloads",
        controls_addressed=[
            "164.312(a)(1) - Access Control",
            "164.312(b) - Audit Controls",
            "164.312(e)(1) - Transmission Security",
        ],
        aws_services=[
            "VPC", "PrivateLink", "Transit Gateway", "Network Firewall",
            "VPC Flow Logs", "CloudWatch"
        ],
        key_configurations=[
            "Dedicated VPC for HIPAA workloads",
            "Private subnets only (no public subnets)",
            "VPC endpoints for all AWS services (S3, DynamoDB, etc.)",
            "VPC Flow Logs enabled for all traffic",
            "Network Firewall for deep packet inspection",
            "Transit Gateway for controlled cross-VPC access",
            "No NAT Gateway (use VPC endpoints instead)",
            "Security groups with explicit deny-by-default",
            "NACLs for subnet-level filtering",
            "Systems Manager Session Manager for access (no bastion)",
        ],
        estimated_monthly_cost="$200-500 (varies by endpoints and traffic)",
        complexity="high",
        pros=[
            "Complete network isolation for PHI workloads",
            "No internet exposure for data plane",
            "Full traffic visibility via Flow Logs",
            "Network Firewall provides deep inspection",
        ],
        cons=[
            "VPC endpoint costs (~$7.50/month each + data transfer)",
            "Network Firewall costs (~$100/month + processing)",
            "Complex to manage without proper automation",
        ],
        terraform_resources=[
            "aws_vpc",
            "aws_subnet",
            "aws_vpc_endpoint",
            "aws_networkfirewall_firewall",
            "aws_flow_log",
            "aws_security_group",
            "aws_network_acl",
            "aws_ec2_transit_gateway",
        ],
        security_notes=[
            "Document all network flows for audit purposes",
            "Implement network segmentation within the VPC",
            "Use Transit Gateway for controlled inter-VPC traffic",
            "Consider AWS PrivateLink for SaaS vendor access",
        ],
    ),

    "hipaa_audit_logging": CompliancePattern(
        id="hipaa_audit_logging",
        name="HIPAA Audit Logging Architecture",
        framework="hipaa",
        description="Comprehensive audit logging architecture meeting HIPAA's 6-year retention "
                    "requirement with tamper-evident storage.",
        use_case="Audit trail for all PHI access, system activity, and security events",
        controls_addressed=[
            "164.312(b) - Audit Controls",
            "164.312(c)(1) - Integrity",
        ],
        aws_services=[
            "CloudTrail", "CloudWatch Logs", "S3", "Athena",
            "Security Hub", "KMS"
        ],
        key_configurations=[
            "CloudTrail organization trail with all events",
            "CloudTrail log file validation enabled",
            "CloudTrail logs encrypted with KMS CMK",
            "S3 bucket with Object Lock (WORM)",
            "6-year retention via S3 lifecycle",
            "Glacier Deep Archive for cost-effective long-term",
            "CloudWatch Logs for real-time analysis",
            "Athena for log querying and investigations",
            "Security Hub for aggregated findings",
            "Cross-account log aggregation for organizations",
        ],
        estimated_monthly_cost="$50-500 (varies by log volume)",
        complexity="medium",
        pros=[
            "Tamper-evident logs with Object Lock",
            "Cost-effective long-term storage with Glacier",
            "Real-time alerting via CloudWatch",
            "Easy querying with Athena",
        ],
        cons=[
            "Object Lock prevents accidental deletion but also legitimate deletion",
            "Athena query costs for large datasets",
            "Initial setup complexity for cross-account aggregation",
        ],
        terraform_resources=[
            "aws_cloudtrail",
            "aws_s3_bucket",
            "aws_s3_bucket_object_lock_configuration",
            "aws_s3_bucket_lifecycle_configuration",
            "aws_cloudwatch_log_group",
            "aws_kms_key",
            "aws_securityhub_account",
        ],
        security_notes=[
            "Test log restoration from Glacier periodically",
            "Implement alerts for failed log deliveries",
            "Separate log storage from PHI storage accounts",
            "Regular log analysis for anomaly detection",
        ],
    ),
}


# =============================================================================
# PCI DSS Architecture Patterns
# =============================================================================

PCI_DSS_PATTERNS: dict[str, CompliancePattern] = {
    "cde_network_segmentation": CompliancePattern(
        id="cde_network_segmentation",
        name="CDE Network Segmentation",
        framework="pci_dss",
        description="Network architecture isolating the Cardholder Data Environment (CDE) "
                    "from other networks to minimize PCI DSS scope.",
        use_case="Payment processing systems, card data storage, POS systems",
        controls_addressed=[
            "Req 1 - Network Security Controls",
            "Req 1.3 - Network access to CDE is restricted",
            "Req 1.4 - Trusted/untrusted network controls",
        ],
        aws_services=[
            "VPC", "Network Firewall", "Security Groups", "NACLs",
            "Transit Gateway", "PrivateLink"
        ],
        key_configurations=[
            "Dedicated VPC for CDE (separate from corporate)",
            "Network Firewall between CDE and other networks",
            "Security groups with explicit allow rules only",
            "Default deny in all NACLs",
            "No direct internet access to CDE",
            "VPC endpoints for AWS services (no NAT)",
            "Transit Gateway with route inspection",
            "Separate security groups per application tier",
            "Document all allowed network flows",
            "Quarterly network segmentation validation",
        ],
        estimated_monthly_cost="$300-800 (Network Firewall + endpoints)",
        complexity="high",
        pros=[
            "Reduces PCI DSS scope significantly",
            "Clear network boundaries for audit",
            "Deep packet inspection with Network Firewall",
            "Centralized traffic control via Transit Gateway",
        ],
        cons=[
            "Network Firewall costs (~$100/month + processing)",
            "VPC endpoint costs add up",
            "Requires careful planning and documentation",
            "Changes require security review",
        ],
        terraform_resources=[
            "aws_vpc",
            "aws_subnet",
            "aws_networkfirewall_firewall",
            "aws_networkfirewall_firewall_policy",
            "aws_ec2_transit_gateway",
            "aws_security_group",
            "aws_network_acl",
            "aws_vpc_endpoint",
        ],
        security_notes=[
            "Document network segmentation for QSA review",
            "Test segmentation controls quarterly",
            "Implement IDS/IPS rules in Network Firewall",
            "Monitor for lateral movement attempts",
        ],
    ),

    "pan_tokenization": CompliancePattern(
        id="pan_tokenization",
        name="PAN Tokenization Architecture",
        framework="pci_dss",
        description="Architecture for tokenizing Primary Account Numbers (PANs) to remove "
                    "card data from application databases.",
        use_case="E-commerce, recurring billing, card-on-file applications",
        controls_addressed=[
            "Req 3 - Protect Stored Account Data",
            "Req 3.4 - PAN is secured wherever stored",
            "Req 3.5 - PAN is rendered unreadable",
        ],
        aws_services=[
            "Payment Cryptography", "Lambda", "API Gateway",
            "DynamoDB", "KMS", "Secrets Manager"
        ],
        key_configurations=[
            "AWS Payment Cryptography for HSM-backed tokenization",
            "Token vault in DynamoDB (encrypted)",
            "API Gateway for tokenization service",
            "Lambda functions for tokenization logic",
            "KMS CMK for token encryption",
            "Format-preserving tokens (same length as PAN)",
            "Token-to-PAN mapping secured in HSM",
            "IAM policies restrict detokenization access",
            "Audit logging for all tokenization operations",
            "Token expiration and rotation policies",
        ],
        estimated_monthly_cost="$500-2000 (Payment Cryptography + API calls)",
        complexity="high",
        pros=[
            "Removes actual PANs from application layer",
            "Significantly reduces PCI scope",
            "HSM-backed security meets Req 3",
            "Format-preserving tokens minimize app changes",
        ],
        cons=[
            "Payment Cryptography costs (~$1/hour per HSM)",
            "Requires application refactoring",
            "Complexity in token lifecycle management",
            "Detokenization latency for real-time payments",
        ],
        terraform_resources=[
            "aws_paymentcryptography_key",
            "aws_dynamodb_table",
            "aws_api_gateway_rest_api",
            "aws_lambda_function",
            "aws_kms_key",
            "aws_secretsmanager_secret",
        ],
        security_notes=[
            "Never log or expose actual PANs",
            "Implement rate limiting on detokenization API",
            "Monitor for bulk detokenization attempts",
            "Consider third-party tokenization services for simplicity",
        ],
    ),

    "pci_logging_monitoring": CompliancePattern(
        id="pci_logging_monitoring",
        name="PCI DSS Logging and Monitoring",
        framework="pci_dss",
        description="Comprehensive logging architecture meeting PCI DSS Requirement 10 for "
                    "audit trails with 1-year retention.",
        use_case="CDE activity logging, security event monitoring, incident response",
        controls_addressed=[
            "Req 10 - Log and Monitor Access",
            "Req 10.2 - Audit logs implemented",
            "Req 10.3 - Audit logs protected",
            "Req 10.5 - Log history retained",
            "Req 10.7 - Security control failure detection",
        ],
        aws_services=[
            "CloudTrail", "CloudWatch", "S3", "OpenSearch",
            "Security Hub", "EventBridge", "SNS"
        ],
        key_configurations=[
            "CloudTrail enabled for all CDE accounts",
            "CloudTrail log file validation enabled",
            "CloudWatch Logs for application logs",
            "OpenSearch for centralized log analysis",
            "S3 with 1-year online retention + archive",
            "Real-time alerting via CloudWatch Alarms",
            "Security Hub for finding aggregation",
            "EventBridge rules for security event routing",
            "SNS for security team notifications",
            "NTP synchronization via Amazon Time Sync",
        ],
        estimated_monthly_cost="$200-1000 (varies by log volume)",
        complexity="medium",
        pros=[
            "Meets PCI Req 10 requirements",
            "Real-time alerting for security events",
            "Centralized log analysis with OpenSearch",
            "Tamper-evident logs with S3 Object Lock",
        ],
        cons=[
            "OpenSearch costs for large log volumes",
            "Requires tuning to reduce false positives",
            "Log storage costs for 1-year retention",
        ],
        terraform_resources=[
            "aws_cloudtrail",
            "aws_cloudwatch_log_group",
            "aws_cloudwatch_metric_alarm",
            "aws_opensearch_domain",
            "aws_s3_bucket",
            "aws_sns_topic",
            "aws_cloudwatch_event_rule",
        ],
        security_notes=[
            "Implement 24/7 monitoring or SIEM integration",
            "Daily log review process required by PCI",
            "Test alerting with simulated security events",
            "Separate log storage from CDE accounts",
        ],
    ),

    "pci_encryption_in_transit": CompliancePattern(
        id="pci_encryption_in_transit",
        name="PCI DSS Encryption in Transit",
        framework="pci_dss",
        description="Architecture ensuring all cardholder data is encrypted during transmission "
                    "with TLS 1.2 or higher.",
        use_case="Payment API endpoints, card processing, inter-service communication",
        controls_addressed=[
            "Req 4 - Protect Cardholder Data in Transit",
            "Req 4.2 - Strong cryptography for PAN transmission",
        ],
        aws_services=[
            "ACM", "ALB", "API Gateway", "CloudFront",
            "PrivateLink", "VPN"
        ],
        key_configurations=[
            "TLS 1.2 minimum (TLS 1.3 preferred)",
            "ACM certificates for all endpoints",
            "ALB with HTTPS listeners only (no HTTP)",
            "API Gateway with TLS 1.2 minimum",
            "CloudFront with TLS 1.2 security policy",
            "PrivateLink for internal AWS service access",
            "VPN with AES-256 for hybrid connectivity",
            "HSTS headers enabled on all responses",
            "Certificate pinning for mobile apps",
            "Monthly certificate expiration monitoring",
        ],
        estimated_monthly_cost="$50-200 (ACM free, ALB costs)",
        complexity="low",
        pros=[
            "ACM provides free certificates",
            "Automated certificate renewal",
            "Easy to implement with ALB/CloudFront",
            "Strong security with TLS 1.3",
        ],
        cons=[
            "Some legacy systems may require TLS 1.0/1.1 exceptions",
            "Certificate pinning complicates mobile app updates",
            "Must monitor certificate expiration",
        ],
        terraform_resources=[
            "aws_acm_certificate",
            "aws_lb_listener",
            "aws_api_gateway_domain_name",
            "aws_cloudfront_distribution",
            "aws_vpn_connection",
        ],
        security_notes=[
            "Scan for TLS 1.0/1.1 usage and remediate",
            "Implement certificate transparency monitoring",
            "Use only strong cipher suites",
            "Test with SSLLabs to verify configuration",
        ],
    ),
}


# =============================================================================
# NIST CSF Architecture Patterns
# =============================================================================

NIST_CSF_PATTERNS: dict[str, CompliancePattern] = {
    "zero_trust_identity": CompliancePattern(
        id="zero_trust_identity",
        name="Zero Trust Identity Architecture",
        framework="nist_csf",
        description="Identity-centric security architecture implementing zero trust principles "
                    "with continuous verification.",
        use_case="Enterprise access management, cloud-native applications, remote workforce",
        controls_addressed=[
            "PR.AA - Identity Management & Access Control",
            "PR.AA-01 - Identities managed",
            "PR.AA-03 - Users authenticated",
            "DE.CM - Continuous Monitoring",
        ],
        aws_services=[
            "IAM Identity Center", "IAM", "Cognito",
            "Verified Access", "Security Hub", "CloudTrail"
        ],
        key_configurations=[
            "IAM Identity Center as central identity provider",
            "MFA required for all access",
            "Context-aware access policies (device, location)",
            "AWS Verified Access for application access",
            "Just-in-time (JIT) privilege escalation",
            "Session duration limits (1-8 hours)",
            "Continuous session monitoring",
            "Device trust verification",
            "Attribute-based access control (ABAC)",
            "Regular access reviews and certification",
        ],
        estimated_monthly_cost="$100-500 (Verified Access + IdP)",
        complexity="high",
        pros=[
            "Strong security for remote workforce",
            "Continuous verification reduces breach impact",
            "Centralized access management",
            "Supports compliance with multiple frameworks",
        ],
        cons=[
            "Verified Access costs per user",
            "Requires identity provider integration",
            "User experience impact from frequent auth",
            "Complex policy management",
        ],
        terraform_resources=[
            "aws_ssoadmin_permission_set",
            "aws_ssoadmin_managed_policy_attachment",
            "aws_verifiedaccess_instance",
            "aws_verifiedaccess_trust_provider",
            "aws_iam_policy",
        ],
        security_notes=[
            "Implement device health checks",
            "Monitor for impossible travel",
            "Automated response to risky sign-ins",
            "Regular policy review and optimization",
        ],
    ),

    "continuous_vulnerability_management": CompliancePattern(
        id="continuous_vulnerability_management",
        name="Continuous Vulnerability Management",
        framework="nist_csf",
        description="Automated vulnerability scanning and remediation pipeline aligned with "
                    "NIST CSF Identify and Protect functions.",
        use_case="Enterprise vulnerability management, security operations, compliance",
        controls_addressed=[
            "ID.RA - Risk Assessment",
            "ID.RA-01 - Vulnerabilities identified",
            "PR.PS-02 - Software maintained",
            "DE.CM-03 - Software monitored",
        ],
        aws_services=[
            "Inspector", "Security Hub", "Systems Manager",
            "EventBridge", "Lambda", "SNS"
        ],
        key_configurations=[
            "Inspector enabled for all workloads",
            "Continuous scanning (not just periodic)",
            "Security Hub aggregates all findings",
            "Automated prioritization by severity",
            "SSM Patch Manager for automated patching",
            "EventBridge rules for auto-remediation",
            "Lambda functions for custom remediation",
            "30-day SLA for critical vulnerabilities",
            "90-day SLA for high vulnerabilities",
            "Integration with ticketing system",
        ],
        estimated_monthly_cost="$100-500 (Inspector scanning)",
        complexity="medium",
        pros=[
            "Continuous visibility into vulnerabilities",
            "Automated remediation reduces MTTR",
            "Centralized findings in Security Hub",
            "Compliance-friendly SLA tracking",
        ],
        cons=[
            "Inspector costs per scan",
            "False positives require tuning",
            "Auto-remediation needs careful testing",
            "Requires vulnerability management process",
        ],
        terraform_resources=[
            "aws_inspector2_enabler",
            "aws_securityhub_account",
            "aws_ssm_patch_baseline",
            "aws_cloudwatch_event_rule",
            "aws_lambda_function",
            "aws_sns_topic",
        ],
        security_notes=[
            "Establish vulnerability SLAs and enforce them",
            "Test patches in non-production first",
            "Maintain exception process for deferrals",
            "Track remediation metrics over time",
        ],
    ),

    "incident_response_automation": CompliancePattern(
        id="incident_response_automation",
        name="Automated Incident Response",
        framework="nist_csf",
        description="Automated incident detection and response architecture implementing "
                    "NIST CSF Detect and Respond functions.",
        use_case="Security operations center, incident response, threat hunting",
        controls_addressed=[
            "DE.AE - Adverse Event Analysis",
            "RS.MA - Incident Management",
            "RS.AN - Incident Analysis",
            "RS.MI - Incident Mitigation",
        ],
        aws_services=[
            "GuardDuty", "Detective", "Security Hub",
            "Incident Manager", "EventBridge", "Step Functions", "Lambda"
        ],
        key_configurations=[
            "GuardDuty for threat detection",
            "Detective for investigation workflows",
            "Security Hub for finding aggregation",
            "Incident Manager runbooks",
            "EventBridge for finding routing",
            "Step Functions for response orchestration",
            "Lambda for automated containment",
            "Auto-isolate compromised instances",
            "Auto-revoke compromised credentials",
            "Integration with SIEM/SOAR tools",
        ],
        estimated_monthly_cost="$200-1000 (GuardDuty + Detective)",
        complexity="high",
        pros=[
            "Rapid response reduces incident impact",
            "Consistent response via runbooks",
            "Investigation accelerated by Detective",
            "Documented response for compliance",
        ],
        cons=[
            "Detective costs based on data analyzed",
            "Requires runbook development effort",
            "Risk of auto-remediation false positives",
            "Needs 24/7 monitoring or on-call",
        ],
        terraform_resources=[
            "aws_guardduty_detector",
            "aws_detective_graph",
            "aws_securityhub_account",
            "aws_ssmincidents_response_plan",
            "aws_sfn_state_machine",
            "aws_lambda_function",
            "aws_cloudwatch_event_rule",
        ],
        security_notes=[
            "Test runbooks with tabletop exercises",
            "Implement escalation procedures",
            "Maintain incident response playbooks",
            "Post-incident review and improvement",
        ],
    ),

    "resilient_backup_recovery": CompliancePattern(
        id="resilient_backup_recovery",
        name="Resilient Backup and Recovery",
        framework="nist_csf",
        description="Comprehensive backup and disaster recovery architecture implementing "
                    "NIST CSF Recover function.",
        use_case="Business continuity, disaster recovery, ransomware protection",
        controls_addressed=[
            "RC.RP - Recovery Plan Execution",
            "RC.RP-03 - Backup integrity verified",
            "PR.DS-11 - Backups created and tested",
            "PR.IR-03 - Resilience requirements met",
        ],
        aws_services=[
            "AWS Backup", "S3", "Glacier", "DRS",
            "CloudEndure", "RDS", "DynamoDB"
        ],
        key_configurations=[
            "AWS Backup centralized backup management",
            "Cross-region backup replication",
            "Immutable backups with vault lock",
            "RTO/RPO objectives defined per tier",
            "Regular backup restoration testing",
            "Elastic Disaster Recovery for servers",
            "RDS automated snapshots (35 days)",
            "DynamoDB point-in-time recovery",
            "S3 versioning and replication",
            "Ransomware-resistant backup isolation",
        ],
        estimated_monthly_cost="$200-2000 (varies by data volume)",
        complexity="medium",
        pros=[
            "Centralized backup management",
            "Cross-region protection",
            "Immutable backups prevent ransomware",
            "Automated compliance reporting",
        ],
        cons=[
            "Cross-region storage costs",
            "DRS costs for protected servers",
            "Regular testing requires effort",
            "Complex RTO requirements may need DRS",
        ],
        terraform_resources=[
            "aws_backup_plan",
            "aws_backup_vault",
            "aws_backup_vault_lock_configuration",
            "aws_s3_bucket_replication_configuration",
            "aws_drs_replication_configuration_template",
        ],
        security_notes=[
            "Test recovery procedures quarterly",
            "Document RTO/RPO for each system",
            "Separate backup credentials from production",
            "Monitor backup job success/failure",
        ],
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_patterns_by_framework(framework: str) -> dict[str, CompliancePattern]:
    """
    Get all patterns for a specific compliance framework.

    Args:
        framework: Framework identifier (hipaa, pci_dss, nist_csf)

    Returns:
        Dictionary of patterns for that framework

    Raises:
        ValueError: If framework is not recognized
    """
    framework = framework.lower()
    if framework == "hipaa":
        return HIPAA_PATTERNS
    elif framework in ("pci_dss", "pci-dss", "pci"):
        return PCI_DSS_PATTERNS
    elif framework in ("nist_csf", "nist-csf", "nist"):
        return NIST_CSF_PATTERNS
    else:
        raise ValueError(f"Unknown framework: {framework}. Valid: hipaa, pci_dss, nist_csf")


def get_all_patterns() -> dict[str, CompliancePattern]:
    """
    Get all compliance patterns across all frameworks.

    Returns:
        Dictionary of all patterns with framework-prefixed keys
    """
    all_patterns = {}
    for pattern_id, pattern in HIPAA_PATTERNS.items():
        all_patterns[f"hipaa/{pattern_id}"] = pattern
    for pattern_id, pattern in PCI_DSS_PATTERNS.items():
        all_patterns[f"pci_dss/{pattern_id}"] = pattern
    for pattern_id, pattern in NIST_CSF_PATTERNS.items():
        all_patterns[f"nist_csf/{pattern_id}"] = pattern
    return all_patterns


def get_patterns_by_control(control_id: str) -> list[CompliancePattern]:
    """
    Get patterns that address a specific control.

    Args:
        control_id: Control identifier (e.g., "164.312(a)(1)", "Req 3", "PR.DS")

    Returns:
        List of patterns addressing that control
    """
    matching = []
    for pattern in get_all_patterns().values():
        for addressed in pattern.controls_addressed:
            if control_id.lower() in addressed.lower():
                matching.append(pattern)
                break
    return matching


def get_pattern_summary() -> list[dict]:
    """
    Get a summary of all compliance patterns.

    Returns:
        List of pattern summaries for display
    """
    return [
        {
            "id": pattern.id,
            "name": pattern.name,
            "framework": pattern.framework,
            "use_case": pattern.use_case,
            "complexity": pattern.complexity,
            "estimated_cost": pattern.estimated_monthly_cost,
        }
        for pattern in get_all_patterns().values()
    ]
