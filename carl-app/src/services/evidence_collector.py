"""
Audit Evidence Collection Service for CARL.

Automatically collects and stores evidence for SOC 2 audits:
- Resource configurations (IAM policies, S3 bucket settings, etc.)
- Security tool outputs (Security Hub findings, GuardDuty alerts)
- Access logs and CloudTrail events
- Point-in-time snapshots for historical compliance proof

Evidence is stored in S3 with metadata in DynamoDB for quick retrieval.
"""

import json
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
import boto3
from botocore.exceptions import ClientError

from utils.logger import get_logger
from models.finding import Finding, FindingSource, FindingSeverity, FindingStatus

logger = get_logger(__name__)


class EvidenceType(Enum):
    """Types of audit evidence."""
    CONFIG_SNAPSHOT = "config_snapshot"  # Resource configuration at point in time
    SECURITY_FINDING = "security_finding"  # Security Hub/GuardDuty finding
    ACCESS_LOG = "access_log"  # CloudTrail, VPC Flow Logs
    POLICY_DOCUMENT = "policy_document"  # IAM policies, SCPs, bucket policies
    COMPLIANCE_CHECK = "compliance_check"  # AWS Config rule evaluation
    SCREENSHOT = "screenshot"  # Console screenshots (manual upload)
    ATTESTATION = "attestation"  # Manual attestations
    REPORT = "report"  # Generated reports


class SOC2Control(Enum):
    """SOC 2 Trust Service Criteria."""
    # Security (Common Criteria)
    CC1_1 = "CC1.1"  # Control Environment - Integrity and Ethics
    CC1_2 = "CC1.2"  # Control Environment - Board Oversight
    CC1_3 = "CC1.3"  # Control Environment - Structure and Authority
    CC1_4 = "CC1.4"  # Control Environment - Commitment to Competence
    CC1_5 = "CC1.5"  # Control Environment - Accountability

    CC2_1 = "CC2.1"  # Communication - Internal Communication
    CC2_2 = "CC2.2"  # Communication - External Communication
    CC2_3 = "CC2.3"  # Communication - Security Policies

    CC3_1 = "CC3.1"  # Risk Assessment - Objectives
    CC3_2 = "CC3.2"  # Risk Assessment - Risk Identification
    CC3_3 = "CC3.3"  # Risk Assessment - Fraud Risk
    CC3_4 = "CC3.4"  # Risk Assessment - Change Impact

    CC4_1 = "CC4.1"  # Monitoring - Ongoing Evaluations
    CC4_2 = "CC4.2"  # Monitoring - Internal Audit

    CC5_1 = "CC5.1"  # Control Activities - Selection
    CC5_2 = "CC5.2"  # Control Activities - Technology Controls
    CC5_3 = "CC5.3"  # Control Activities - Policies and Procedures

    CC6_1 = "CC6.1"  # Logical Access - Access Controls
    CC6_2 = "CC6.2"  # Logical Access - Registration/Authorization
    CC6_3 = "CC6.3"  # Logical Access - Removal
    CC6_4 = "CC6.4"  # Logical Access - Restriction
    CC6_5 = "CC6.5"  # Logical Access - Accountability
    CC6_6 = "CC6.6"  # Logical Access - Access Review
    CC6_7 = "CC6.7"  # Logical Access - Data Classification
    CC6_8 = "CC6.8"  # Logical Access - Malware Protection

    CC7_1 = "CC7.1"  # System Operations - Detection
    CC7_2 = "CC7.2"  # System Operations - Monitoring
    CC7_3 = "CC7.3"  # System Operations - Incident Response
    CC7_4 = "CC7.4"  # System Operations - Recovery
    CC7_5 = "CC7.5"  # System Operations - Restoration

    CC8_1 = "CC8.1"  # Change Management - Changes
    CC9_1 = "CC9.1"  # Risk Mitigation - Vendor Management
    CC9_2 = "CC9.2"  # Risk Mitigation - Business Continuity

    # Availability
    A1_1 = "A1.1"  # Availability - Capacity Planning
    A1_2 = "A1.2"  # Availability - Environmental Protection
    A1_3 = "A1.3"  # Availability - Recovery

    # Confidentiality
    C1_1 = "C1.1"  # Confidentiality - Identification
    C1_2 = "C1.2"  # Confidentiality - Destruction

    # Processing Integrity
    PI1_1 = "PI1.1"  # Processing Integrity - Accuracy
    PI1_2 = "PI1.2"  # Processing Integrity - Completeness
    PI1_3 = "PI1.3"  # Processing Integrity - Timeliness
    PI1_4 = "PI1.4"  # Processing Integrity - Authorization
    PI1_5 = "PI1.5"  # Processing Integrity - Error Handling


# Mapping of AWS resources/checks to SOC 2 controls
RESOURCE_CONTROL_MAPPING = {
    "iam_user": [SOC2Control.CC6_1, SOC2Control.CC6_2, SOC2Control.CC6_3],
    "iam_role": [SOC2Control.CC6_1, SOC2Control.CC6_4, SOC2Control.CC6_5],
    "iam_policy": [SOC2Control.CC6_1, SOC2Control.CC6_4, SOC2Control.CC5_3],
    "iam_mfa": [SOC2Control.CC6_1, SOC2Control.CC6_5],
    "s3_bucket": [SOC2Control.CC6_7, SOC2Control.C1_1, SOC2Control.C1_2],
    "s3_encryption": [SOC2Control.CC6_7, SOC2Control.C1_1],
    "s3_logging": [SOC2Control.CC7_2, SOC2Control.CC4_1],
    "cloudtrail": [SOC2Control.CC7_1, SOC2Control.CC7_2, SOC2Control.CC4_1],
    "security_hub": [SOC2Control.CC7_1, SOC2Control.CC7_2, SOC2Control.CC4_1],
    "guardduty": [SOC2Control.CC7_1, SOC2Control.CC6_8],
    "config": [SOC2Control.CC7_2, SOC2Control.CC4_1, SOC2Control.CC8_1],
    "vpc_flow_logs": [SOC2Control.CC7_2, SOC2Control.CC6_5],
    "kms": [SOC2Control.CC6_7, SOC2Control.C1_1],
    "backup": [SOC2Control.A1_3, SOC2Control.CC9_2],
    "rds_encryption": [SOC2Control.CC6_7, SOC2Control.C1_1],
    "rds_backup": [SOC2Control.A1_3, SOC2Control.CC9_2],
    "ec2_imdsv2": [SOC2Control.CC6_1, SOC2Control.CC6_4],
    "ebs_encryption": [SOC2Control.CC6_7, SOC2Control.C1_1],
    "waf": [SOC2Control.CC6_8, SOC2Control.CC7_1],
    "shield": [SOC2Control.A1_2, SOC2Control.CC7_1],
    "secrets_manager": [SOC2Control.CC6_7, SOC2Control.C1_1],
    "ssm_patch": [SOC2Control.CC6_8, SOC2Control.CC8_1],
    "access_analyzer": [SOC2Control.CC6_6, SOC2Control.CC4_1],
}


@dataclass
class Evidence:
    """An audit evidence item."""
    evidence_id: str
    evidence_type: str
    title: str
    description: str
    controls: list[str]  # SOC 2 control IDs
    resource_type: str
    resource_id: str
    account_id: str
    region: str
    collected_at: str
    collected_by: str  # "automated" or user ID
    s3_key: str  # S3 location of full evidence
    content_hash: str  # SHA-256 of content for integrity
    metadata: dict = field(default_factory=dict)
    audit_period_start: str = ""
    audit_period_end: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format with required keys."""
        from datetime import datetime

        # Parse timestamp from collected_at
        try:
            timestamp = datetime.fromisoformat(self.collected_at.replace('Z', '+00:00')).timestamp()
        except:
            timestamp = datetime.utcnow().timestamp()

        item = {
            "evidence_id": self.evidence_id,
            "timestamp": self.collected_at,  # Required range key - use ISO format
            "evidence_type": self.evidence_type,
            "title": self.title,
            "description": self.description,
            "controls": self.controls,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "account_id": self.account_id,
            "region": self.region,
            "collected_at": self.collected_at,
            "collected_by": self.collected_by,
            "s3_key": self.s3_key,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "audit_period_start": self.audit_period_start,
            "audit_period_end": self.audit_period_end,
            "tags": self.tags,
        }
        return item

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class EvidenceCollection:
    """A collection of evidence for a specific audit period."""
    collection_id: str
    name: str
    description: str
    audit_period_start: str
    audit_period_end: str
    framework: str  # "SOC2", "HIPAA", etc.
    status: str  # "collecting", "complete", "archived"
    created_at: str
    created_by: str
    evidence_count: int = 0
    controls_covered: list[str] = field(default_factory=list)
    controls_missing: list[str] = field(default_factory=list)


class EvidenceCollector:
    """Service for collecting and managing audit evidence."""

    def __init__(
        self,
        evidence_bucket: str,
        evidence_table: str,
        collections_table: str = None
    ):
        self.evidence_bucket = evidence_bucket
        self.evidence_table = evidence_table
        self.collections_table = collections_table or f"{evidence_table}_collections"

        self.s3 = boto3.client("s3")
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(evidence_table)

        # AWS service clients for evidence collection
        self.iam = boto3.client("iam")
        self.s3_client = boto3.client("s3")
        self.ec2 = boto3.client("ec2")
        self.rds = boto3.client("rds")
        self.config = boto3.client("config")
        self.securityhub = boto3.client("securityhub")
        self.cloudtrail = boto3.client("cloudtrail")
        self.sts = boto3.client("sts")

        self._account_id = None

    @property
    def account_id(self) -> str:
        if self._account_id is None:
            self._account_id = self.sts.get_caller_identity()["Account"]
        return self._account_id

    def collect_iam_evidence(self) -> list[Evidence]:
        """Collect IAM-related evidence for access control compliance."""
        evidence_items = []
        timestamp = datetime.utcnow().isoformat()

        # 1. IAM Users with MFA status
        try:
            users = self.iam.list_users()["Users"]
            for user in users:
                user_name = user["UserName"]

                # Get MFA devices
                mfa_devices = self.iam.list_mfa_devices(UserName=user_name)["MFADevices"]
                has_mfa = len(mfa_devices) > 0

                # Get attached policies
                attached_policies = self.iam.list_attached_user_policies(UserName=user_name)["AttachedPolicies"]

                # Get access keys
                access_keys = self.iam.list_access_keys(UserName=user_name)["AccessKeyMetadata"]

                user_evidence = {
                    "user_name": user_name,
                    "user_id": user["UserId"],
                    "arn": user["Arn"],
                    "created_date": user["CreateDate"].isoformat(),
                    "password_last_used": user.get("PasswordLastUsed", "Never").isoformat() if isinstance(user.get("PasswordLastUsed"), datetime) else str(user.get("PasswordLastUsed", "Never")),
                    "mfa_enabled": has_mfa,
                    "mfa_devices": [d["SerialNumber"] for d in mfa_devices],
                    "attached_policies": [p["PolicyName"] for p in attached_policies],
                    "access_keys": [
                        {
                            "key_id": k["AccessKeyId"],
                            "status": k["Status"],
                            "created": k["CreateDate"].isoformat()
                        }
                        for k in access_keys
                    ]
                }

                evidence = self._store_evidence(
                    evidence_type=EvidenceType.CONFIG_SNAPSHOT,
                    title=f"IAM User Configuration: {user_name}",
                    description=f"IAM user configuration including MFA status, policies, and access keys",
                    resource_type="iam_user",
                    resource_id=user["Arn"],
                    content=user_evidence,
                    controls=[SOC2Control.CC6_1, SOC2Control.CC6_2, SOC2Control.CC6_5],
                )
                evidence_items.append(evidence)

        except ClientError as e:
            logger.exception("Error collecting IAM user evidence")

        # 2. IAM Password Policy
        try:
            password_policy = self.iam.get_account_password_policy()["PasswordPolicy"]
            evidence = self._store_evidence(
                evidence_type=EvidenceType.POLICY_DOCUMENT,
                title="IAM Password Policy",
                description="Account-level password policy settings",
                resource_type="iam_policy",
                resource_id=f"arn:aws:iam::{self.account_id}:account-password-policy",
                content=password_policy,
                controls=[SOC2Control.CC6_1, SOC2Control.CC5_3],
            )
            evidence_items.append(evidence)
        except self.iam.exceptions.NoSuchEntityException:
            # No password policy set - this is a finding
            evidence = self._store_evidence(
                evidence_type=EvidenceType.COMPLIANCE_CHECK,
                title="IAM Password Policy - NOT CONFIGURED",
                description="No account-level password policy is configured",
                resource_type="iam_policy",
                resource_id=f"arn:aws:iam::{self.account_id}:account-password-policy",
                content={"status": "NOT_CONFIGURED", "risk": "HIGH"},
                controls=[SOC2Control.CC6_1, SOC2Control.CC5_3],
            )
            evidence_items.append(evidence)
        except ClientError as e:
            logger.exception("Error collecting password policy evidence")

        # 3. IAM Roles
        try:
            roles = self.iam.list_roles()["Roles"]
            for role in roles:
                if role["Path"].startswith("/aws-service-role/"):
                    continue  # Skip service-linked roles

                role_detail = self.iam.get_role(RoleName=role["RoleName"])["Role"]
                attached_policies = self.iam.list_attached_role_policies(RoleName=role["RoleName"])["AttachedPolicies"]

                role_evidence = {
                    "role_name": role["RoleName"],
                    "role_id": role["RoleId"],
                    "arn": role["Arn"],
                    "created_date": role["CreateDate"].isoformat(),
                    "assume_role_policy": role_detail["AssumeRolePolicyDocument"],
                    "attached_policies": [p["PolicyName"] for p in attached_policies],
                    "max_session_duration": role_detail.get("MaxSessionDuration", 3600),
                }

                evidence = self._store_evidence(
                    evidence_type=EvidenceType.CONFIG_SNAPSHOT,
                    title=f"IAM Role Configuration: {role['RoleName']}",
                    description="IAM role configuration including trust policy and permissions",
                    resource_type="iam_role",
                    resource_id=role["Arn"],
                    content=role_evidence,
                    controls=[SOC2Control.CC6_1, SOC2Control.CC6_4],
                )
                evidence_items.append(evidence)

        except ClientError as e:
            logger.exception("Error collecting IAM role evidence")

        return evidence_items

    def collect_s3_evidence(self) -> list[Evidence]:
        """Collect S3 bucket security evidence."""
        evidence_items = []

        try:
            buckets = self.s3_client.list_buckets()["Buckets"]

            for bucket in buckets:
                bucket_name = bucket["Name"]
                bucket_evidence = {
                    "bucket_name": bucket_name,
                    "created_date": bucket["CreationDate"].isoformat(),
                }

                # Encryption
                try:
                    encryption = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
                    bucket_evidence["encryption"] = encryption["ServerSideEncryptionConfiguration"]
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                        bucket_evidence["encryption"] = None
                    else:
                        bucket_evidence["encryption"] = "ERROR"

                # Public access block
                try:
                    public_access = self.s3_client.get_public_access_block(Bucket=bucket_name)
                    bucket_evidence["public_access_block"] = public_access["PublicAccessBlockConfiguration"]
                except ClientError:
                    bucket_evidence["public_access_block"] = None

                # Versioning
                try:
                    versioning = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                    bucket_evidence["versioning"] = versioning.get("Status", "Disabled")
                except ClientError:
                    bucket_evidence["versioning"] = "ERROR"

                # Logging
                try:
                    logging = self.s3_client.get_bucket_logging(Bucket=bucket_name)
                    bucket_evidence["logging"] = logging.get("LoggingEnabled")
                except ClientError:
                    bucket_evidence["logging"] = "ERROR"

                evidence = self._store_evidence(
                    evidence_type=EvidenceType.CONFIG_SNAPSHOT,
                    title=f"S3 Bucket Configuration: {bucket_name}",
                    description="S3 bucket security configuration including encryption, public access, versioning",
                    resource_type="s3_bucket",
                    resource_id=f"arn:aws:s3:::{bucket_name}",
                    content=bucket_evidence,
                    controls=[SOC2Control.CC6_7, SOC2Control.C1_1, SOC2Control.CC7_2],
                )
                evidence_items.append(evidence)

        except ClientError as e:
            logger.exception("Error collecting S3 evidence")

        return evidence_items

    def collect_cloudtrail_evidence(self) -> list[Evidence]:
        """Collect CloudTrail configuration evidence."""
        evidence_items = []

        try:
            trails = self.cloudtrail.describe_trails()["trailList"]

            for trail in trails:
                trail_name = trail["Name"]

                # Get trail status
                status = self.cloudtrail.get_trail_status(Name=trail_name)

                trail_evidence = {
                    "trail_name": trail_name,
                    "trail_arn": trail["TrailARN"],
                    "is_multi_region": trail.get("IsMultiRegionTrail", False),
                    "is_organization_trail": trail.get("IsOrganizationTrail", False),
                    "s3_bucket": trail.get("S3BucketName"),
                    "log_file_validation": trail.get("LogFileValidationEnabled", False),
                    "kms_key_id": trail.get("KmsKeyId"),
                    "is_logging": status.get("IsLogging", False),
                    "latest_delivery_time": status.get("LatestDeliveryTime", "").isoformat() if status.get("LatestDeliveryTime") else None,
                    "cloudwatch_logs_log_group": trail.get("CloudWatchLogsLogGroupArn"),
                }

                evidence = self._store_evidence(
                    evidence_type=EvidenceType.CONFIG_SNAPSHOT,
                    title=f"CloudTrail Configuration: {trail_name}",
                    description="CloudTrail trail configuration for audit logging",
                    resource_type="cloudtrail",
                    resource_id=trail["TrailARN"],
                    content=trail_evidence,
                    controls=[SOC2Control.CC7_1, SOC2Control.CC7_2, SOC2Control.CC4_1],
                )
                evidence_items.append(evidence)

        except ClientError as e:
            logger.exception("Error collecting CloudTrail evidence")

        return evidence_items

    def collect_security_hub_evidence(self) -> list[Evidence]:
        """Collect Security Hub findings as evidence."""
        evidence_items = []

        try:
            # Get Security Hub enabled standards
            standards = self.securityhub.get_enabled_standards()["StandardsSubscriptions"]

            standards_evidence = {
                "enabled_standards": [
                    {
                        "standard_arn": s["StandardsArn"],
                        "subscription_arn": s["StandardsSubscriptionArn"],
                        "status": s["StandardsStatus"]
                    }
                    for s in standards
                ],
                "collected_at": datetime.utcnow().isoformat()
            }

            evidence = self._store_evidence(
                evidence_type=EvidenceType.CONFIG_SNAPSHOT,
                title="Security Hub Enabled Standards",
                description="List of compliance standards enabled in Security Hub",
                resource_type="security_hub",
                resource_id=f"arn:aws:securityhub:{boto3.Session().region_name}:{self.account_id}:hub/default",
                content=standards_evidence,
                controls=[SOC2Control.CC7_1, SOC2Control.CC7_2, SOC2Control.CC4_1],
            )
            evidence_items.append(evidence)

            # Get findings summary by severity
            findings_filter = {
                "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
                "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}],
            }

            findings = self.securityhub.get_findings(Filters=findings_filter, MaxResults=100)

            findings_summary = {
                "total_findings": len(findings.get("Findings", [])),
                "by_severity": {},
                "by_compliance_status": {},
                "sample_findings": []
            }

            for finding in findings.get("Findings", [])[:100]:
                severity = finding.get("Severity", {}).get("Label", "UNKNOWN")
                findings_summary["by_severity"][severity] = findings_summary["by_severity"].get(severity, 0) + 1

                compliance = finding.get("Compliance", {}).get("Status", "UNKNOWN")
                findings_summary["by_compliance_status"][compliance] = findings_summary["by_compliance_status"].get(compliance, 0) + 1

                if len(findings_summary["sample_findings"]) < 10:
                    findings_summary["sample_findings"].append({
                        "id": finding["Id"],
                        "title": finding["Title"],
                        "severity": severity,
                        "resource": finding.get("Resources", [{}])[0].get("Id", "Unknown")
                    })

            evidence = self._store_evidence(
                evidence_type=EvidenceType.SECURITY_FINDING,
                title="Security Hub Findings Summary",
                description="Summary of active Security Hub findings",
                resource_type="security_hub",
                resource_id=f"arn:aws:securityhub:{boto3.Session().region_name}:{self.account_id}:hub/default",
                content=findings_summary,
                controls=[SOC2Control.CC7_1, SOC2Control.CC7_2],
            )
            evidence_items.append(evidence)

        except ClientError as e:
            logger.exception("Error collecting Security Hub evidence")

        return evidence_items

    def collect_vpc_evidence(self) -> list[Evidence]:
        """Collect VPC and network security evidence."""
        evidence_items = []

        try:
            vpcs = self.ec2.describe_vpcs()["Vpcs"]

            for vpc in vpcs:
                vpc_id = vpc["VpcId"]

                # Get flow logs
                flow_logs = self.ec2.describe_flow_logs(
                    Filters=[{"Name": "resource-id", "Values": [vpc_id]}]
                )["FlowLogs"]

                # Get security groups
                security_groups = self.ec2.describe_security_groups(
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
                )["SecurityGroups"]

                # Get NACLs
                nacls = self.ec2.describe_network_acls(
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
                )["NetworkAcls"]

                vpc_evidence = {
                    "vpc_id": vpc_id,
                    "cidr_block": vpc["CidrBlock"],
                    "is_default": vpc.get("IsDefault", False),
                    "tags": {t["Key"]: t["Value"] for t in vpc.get("Tags", [])},
                    "flow_logs_enabled": len(flow_logs) > 0,
                    "flow_logs": [
                        {
                            "id": fl["FlowLogId"],
                            "status": fl["FlowLogStatus"],
                            "traffic_type": fl["TrafficType"],
                            "destination": fl.get("LogDestination", fl.get("LogGroupName", "Unknown"))
                        }
                        for fl in flow_logs
                    ],
                    "security_group_count": len(security_groups),
                    "risky_security_groups": [
                        {
                            "id": sg["GroupId"],
                            "name": sg["GroupName"],
                            "issue": "Allows 0.0.0.0/0 ingress"
                        }
                        for sg in security_groups
                        if any(
                            ip.get("CidrIp") == "0.0.0.0/0"
                            for rule in sg.get("IpPermissions", [])
                            for ip in rule.get("IpRanges", [])
                        )
                    ],
                    "nacl_count": len(nacls),
                }

                evidence = self._store_evidence(
                    evidence_type=EvidenceType.CONFIG_SNAPSHOT,
                    title=f"VPC Security Configuration: {vpc_id}",
                    description="VPC network security configuration including flow logs, security groups, and NACLs",
                    resource_type="vpc",
                    resource_id=f"arn:aws:ec2:{boto3.Session().region_name}:{self.account_id}:vpc/{vpc_id}",
                    content=vpc_evidence,
                    controls=[SOC2Control.CC6_1, SOC2Control.CC6_4, SOC2Control.CC7_2],
                )
                evidence_items.append(evidence)

        except ClientError as e:
            logger.exception("Error collecting VPC evidence")

        return evidence_items

    def collect_all_evidence(self) -> dict[str, list[Evidence]]:
        """Collect all evidence types for a comprehensive audit."""
        logger.info("Starting comprehensive evidence collection")

        results = {
            "iam": self.collect_iam_evidence(),
            "s3": self.collect_s3_evidence(),
            "cloudtrail": self.collect_cloudtrail_evidence(),
            "security_hub": self.collect_security_hub_evidence(),
            "vpc": self.collect_vpc_evidence(),
        }

        total = sum(len(items) for items in results.values())
        logger.info(f"Evidence collection complete: {total} items collected")

        return results

    def create_findings_from_evidence(self, evidence_results: dict[str, list[Evidence]]) -> list[Finding]:
        """
        Analyze evidence and create findings for security issues.

        Converts evidence items that represent security problems into Finding objects
        that can be tracked, remediated, and synced to Jira.

        Only creates findings that don't already exist in the findings table.

        Args:
            evidence_results: Dict of evidence items by category from collect_all_evidence()

        Returns:
            List of Finding objects created from security issues (new only, not duplicates)
        """
        findings = []
        skipped = 0

        # Import here to avoid circular dependency
        from services.findings_service import FindingsService
        findings_service = FindingsService()

        for category, evidence_items in evidence_results.items():
            for evidence in evidence_items:
                # Check if this evidence represents security issues (can return multiple)
                evidence_findings = self._analyze_evidence_for_findings(evidence, category)
                for finding in evidence_findings:
                    # Check if finding already exists
                    existing = findings_service.get_finding(finding.id, finding.account_id)
                    if existing:
                        logger.debug(f"Finding {finding.id} already exists, skipping")
                        skipped += 1
                    else:
                        findings.append(finding)

        logger.info(f"Created {len(findings)} new findings from evidence analysis ({skipped} already existed)")
        return findings

    def _analyze_evidence_for_findings(self, evidence: Evidence, category: str) -> list[Finding]:
        """
        Analyze a single evidence item to determine if it represents security findings.

        Returns list of Finding objects for all security issues detected in this evidence.
        Can return multiple findings per evidence item (e.g., S3 bucket with multiple issues).
        """
        import hashlib

        findings = []

        # Check for explicit risk indicators in content
        content = evidence.metadata if isinstance(evidence.metadata, dict) else {}

        # IAM Issues
        if category == "iam":
            # Password policy not configured
            if "NOT CONFIGURED" in evidence.title and "Password Policy" in evidence.title:
                # Use stable ID based on account + issue type (not evidence ID)
                finding_key = f"{evidence.account_id}-iam-password-policy"
                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.HIGH,
                    title="IAM Password Policy Not Configured",
                    description="Account does not have a password policy configured. This allows weak passwords and increases risk of unauthorized access.",
                    resource_type="AWS::IAM::AccountPasswordPolicy",
                    resource_id=evidence.resource_id,
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps="Configure an IAM password policy with minimum requirements: 14+ characters, complexity requirements, password expiration, and password reuse prevention.",
                    raw_finding={"evidence_id": evidence.evidence_id, "source": "evidence_collector"}
                ))

            # Users without MFA
            if "mfa_devices" in str(content).lower() and content.get("mfa_enabled") == False:
                user_name = content.get('user_name', 'Unknown')
                # Use stable ID based on account + user + issue type
                finding_key = f"{evidence.account_id}-iam-user-{user_name}-mfa"
                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.MEDIUM,
                    title=f"IAM User Without MFA: {user_name}",
                    description=f"IAM user {user_name} does not have MFA enabled, increasing risk of credential compromise.",
                    resource_type="AWS::IAM::User",
                    resource_id=evidence.resource_id,
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps=f"Enable MFA for user {user_name} in IAM console or via CLI.",
                    raw_finding={"evidence_id": evidence.evidence_id, "source": "evidence_collector"}
                ))

        # S3 Issues
        elif category == "s3":
            content_str = json.dumps(content, default=str).lower()
            bucket_name = content.get("bucket_name", "unknown")

            # Unencrypted bucket (or unable to determine due to permissions)
            encryption = content.get("encryption")
            if encryption is None or encryption == "ERROR":
                # Use stable ID based on account + bucket + issue type
                finding_key = f"{evidence.account_id}-s3-{bucket_name}-encryption"
                # Determine appropriate title based on whether we could check or not
                if encryption == "ERROR":
                    title = f"S3 Bucket Encryption Status Unknown: {bucket_name}"
                    description = f"S3 bucket '{bucket_name}' encryption status could not be verified (permissions issue). Verify encryption is enabled."
                else:
                    title = f"S3 Bucket Not Encrypted: {bucket_name}"
                    description = f"S3 bucket '{bucket_name}' does not have default encryption enabled. Data at rest is not encrypted."

                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.HIGH,
                    title=title,
                    description=description,
                    resource_type="AWS::S3::Bucket",
                    resource_id=evidence.resource_id,
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps=f"Enable default encryption for bucket '{bucket_name}' using AES-256 or KMS encryption. If encryption is already enabled, grant s3:GetEncryptionConfiguration permission to verify.",
                    raw_finding={"evidence_id": evidence.evidence_id, "bucket": bucket_name, "source": "evidence_collector", "encryption_status": encryption}
                ))

            # No versioning (check for None, "Disabled", or "Suspended")
            versioning_status = content.get("versioning")
            if versioning_status in ["Disabled", "Suspended", None]:
                # Use stable ID based on account + bucket + issue type
                finding_key = f"{evidence.account_id}-s3-{bucket_name}-versioning"
                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.MEDIUM,
                    title=f"S3 Bucket Versioning Disabled: {bucket_name}",
                    description=f"S3 bucket '{bucket_name}' does not have versioning enabled (status: {versioning_status}). Cannot recover from accidental deletions or overwrites.",
                    resource_type="AWS::S3::Bucket",
                    resource_id=evidence.resource_id,
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps=f"Enable versioning for bucket '{bucket_name}' to protect against accidental deletion.",
                    raw_finding={"evidence_id": evidence.evidence_id, "bucket": bucket_name, "source": "evidence_collector"}
                ))

            # Public access not blocked
            public_block = content.get("public_access_block")
            if public_block is None or not all([
                public_block.get("BlockPublicAcls"),
                public_block.get("BlockPublicPolicy"),
                public_block.get("IgnorePublicAcls"),
                public_block.get("RestrictPublicBuckets")
            ]):
                # Use stable ID based on account + bucket + issue type
                finding_key = f"{evidence.account_id}-s3-{bucket_name}-public"
                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.HIGH,
                    title=f"S3 Bucket Public Access Not Fully Blocked: {bucket_name}",
                    description=f"S3 bucket '{bucket_name}' does not have all public access blocks enabled. Bucket may be inadvertently exposed.",
                    resource_type="AWS::S3::Bucket",
                    resource_id=evidence.resource_id,
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps=f"Enable all public access block settings for bucket '{bucket_name}'.",
                    raw_finding={"evidence_id": evidence.evidence_id, "bucket": bucket_name, "source": "evidence_collector"}
                ))

        # VPC Issues
        elif category == "vpc":
            content_str = json.dumps(content, default=str).lower()

            # No flow logs
            if "flow_logs_enabled" in content_str and content.get("flow_logs_enabled") == False:
                vpc_id = content.get("vpc_id", "unknown")
                # Use stable ID based on account + vpc + issue type
                finding_key = f"{evidence.account_id}-vpc-{vpc_id}-flowlogs"
                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.MEDIUM,
                    title=f"VPC Flow Logs Not Enabled: {vpc_id}",
                    description=f"VPC {vpc_id} does not have flow logs enabled. Network traffic cannot be monitored or audited.",
                    resource_type="AWS::EC2::VPC",
                    resource_id=evidence.resource_id,
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps=f"Enable VPC flow logs for {vpc_id} and send to CloudWatch Logs or S3.",
                    raw_finding={"evidence_id": evidence.evidence_id, "vpc_id": vpc_id, "source": "evidence_collector"}
                ))

            # Risky security groups - create one finding PER security group
            risky_sgs = content.get("risky_security_groups", [])
            for sg_info in risky_sgs:
                # Use stable ID based on account + sg + issue type
                finding_key = f"{evidence.account_id}-sg-{sg_info['id']}-permissive"
                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.HIGH,
                    title=f"Overly Permissive Security Group: {sg_info['name']}",
                    description=f"Security group {sg_info['name']} ({sg_info['id']}) allows 0.0.0.0/0 ingress access.",
                    resource_type="AWS::EC2::SecurityGroup",
                    resource_id=f"arn:aws:ec2:{evidence.region}:{evidence.account_id}:security-group/{sg_info['id']}",
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps=f"Restrict security group {sg_info['name']} to specific IP ranges instead of 0.0.0.0/0.",
                    raw_finding={"evidence_id": evidence.evidence_id, "security_group": sg_info, "source": "evidence_collector"}
                ))

        # CloudTrail Issues
        elif category == "cloudtrail":
            # Check if CloudTrail is not enabled or not properly configured
            if "NOT ENABLED" in evidence.title or "not logging" in evidence.description.lower():
                # Use stable ID based on account + issue type
                finding_key = f"{evidence.account_id}-cloudtrail-not-enabled"
                findings.append(Finding(
                    id=f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}",
                    source=FindingSource.CONFIG,
                    severity=FindingSeverity.HIGH,
                    title="CloudTrail Not Properly Configured",
                    description="CloudTrail is not enabled or not logging. Audit trail of AWS API calls is not being captured.",
                    resource_type="AWS::CloudTrail::Trail",
                    resource_id=evidence.resource_id,
                    account_id=evidence.account_id,
                    region=evidence.region,
                    control_ids=[c.value if isinstance(c, SOC2Control) else c for c in evidence.controls],
                    status=FindingStatus.NEW,
                    remediation_steps="Enable CloudTrail with multi-region logging and log file validation.",
                    raw_finding={"evidence_id": evidence.evidence_id, "source": "evidence_collector"}
                ))

        return findings

    def _store_evidence(
        self,
        evidence_type: EvidenceType,
        title: str,
        description: str,
        resource_type: str,
        resource_id: str,
        content: Any,
        controls: list[SOC2Control],
    ) -> Evidence:
        """Store evidence in S3 and metadata in DynamoDB."""
        timestamp = datetime.utcnow()
        content_json = json.dumps(content, default=str, indent=2)
        content_hash = hashlib.sha256(content_json.encode()).hexdigest()

        evidence_id = f"ev_{timestamp.strftime('%Y%m%d%H%M%S')}_{content_hash[:8]}"
        s3_key = f"evidence/{timestamp.strftime('%Y/%m/%d')}/{evidence_type.value}/{evidence_id}.json"

        # Store content in S3
        self.s3.put_object(
            Bucket=self.evidence_bucket,
            Key=s3_key,
            Body=content_json,
            ContentType="application/json",
            Metadata={
                "evidence-id": evidence_id,
                "resource-type": resource_type,
                "content-hash": content_hash,
            }
        )

        # Create evidence record
        evidence = Evidence(
            evidence_id=evidence_id,
            evidence_type=evidence_type.value,
            title=title,
            description=description,
            controls=[c.value for c in controls],
            resource_type=resource_type,
            resource_id=resource_id,
            account_id=self.account_id,
            region=boto3.Session().region_name,
            collected_at=timestamp.isoformat(),
            collected_by="automated",
            s3_key=s3_key,
            content_hash=content_hash,
            metadata=content if isinstance(content, dict) else {"raw": content}  # Store content for analysis
        )

        # Store metadata in DynamoDB
        self.table.put_item(Item=evidence.to_dynamodb_item())

        logger.info(f"Stored evidence: {evidence_id} - {title}")
        return evidence

    def get_recent_evidence(self, limit: int = 50, evidence_type: str = None) -> list[Evidence]:
        """
        Get recent evidence items across all types.

        Args:
            limit: Maximum number of items to return
            evidence_type: Optional filter by evidence type (e.g., 'config_snapshot')

        Returns:
            List of Evidence objects, sorted by collection time (newest first)
        """
        from boto3.dynamodb.conditions import Attr, Key

        try:
            # Scan for recent evidence (DynamoDB limitations - can't efficiently query by timestamp across accounts)
            scan_kwargs = {"Limit": limit * 2}  # Get more than we need to allow for filtering

            if evidence_type:
                scan_kwargs["FilterExpression"] = Attr("evidence_type").eq(evidence_type)

            response = self.table.scan(**scan_kwargs)
            items = response.get("Items", [])

            # Convert to Evidence objects
            evidence_list = []
            for item in items:
                try:
                    evidence_list.append(Evidence.from_dict(item))
                except Exception as e:
                    logger.warning(f"Failed to parse evidence item: {e}")
                    continue

            # Sort by collected_at timestamp (newest first)
            evidence_list.sort(key=lambda e: e.collected_at, reverse=True)

            # Return up to limit items
            return evidence_list[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent evidence: {e}")
            return []

    def get_evidence_by_control(self, control: str) -> list[Evidence]:
        """Get all evidence items for a specific SOC 2 control."""
        from boto3.dynamodb.conditions import Attr

        response = self.table.scan(
            FilterExpression=Attr("controls").contains(control)
        )

        return [Evidence.from_dict(item) for item in response.get("Items", [])]

    def get_evidence_for_audit_period(
        self,
        start_date: str,
        end_date: str
    ) -> list[Evidence]:
        """Get all evidence collected within an audit period."""
        from boto3.dynamodb.conditions import Attr

        response = self.table.scan(
            FilterExpression=Attr("collected_at").between(start_date, end_date)
        )

        return [Evidence.from_dict(item) for item in response.get("Items", [])]

    def get_evidence_content(self, evidence: Evidence) -> dict:
        """Retrieve the full evidence content from S3."""
        response = self.s3.get_object(
            Bucket=self.evidence_bucket,
            Key=evidence.s3_key
        )
        return json.loads(response["Body"].read().decode("utf-8"))

    def get_control_coverage(self) -> dict[str, list[str]]:
        """Get coverage report showing which controls have evidence."""
        all_controls = [c.value for c in SOC2Control]

        # Get all evidence
        response = self.table.scan()
        evidence_items = response.get("Items", [])

        covered_controls = set()
        control_evidence = {control: [] for control in all_controls}

        for item in evidence_items:
            for control in item.get("controls", []):
                covered_controls.add(control)
                control_evidence[control].append(item["evidence_id"])

        return {
            "covered": list(covered_controls),
            "missing": [c for c in all_controls if c not in covered_controls],
            "coverage_percent": len(covered_controls) / len(all_controls) * 100,
            "control_evidence": control_evidence,
        }
