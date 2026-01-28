"""
Infrastructure Drift Detection Service for CARL.

Detects configuration drift between:
- Terraform state and actual AWS resources
- Baseline configurations and current state
- Compliance requirements and actual settings

Drift can indicate:
- Manual changes (console cowboys)
- Unauthorized modifications
- Failed deployments
- Security misconfigurations

This service helps maintain infrastructure-as-code discipline
and ensures compliance controls remain in place.
"""

import json
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
import boto3
from botocore.exceptions import ClientError

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DriftType(Enum):
    """Types of configuration drift."""
    ADDED = "added"  # Resource exists in AWS but not in state
    REMOVED = "removed"  # Resource in state but not in AWS
    MODIFIED = "modified"  # Resource differs from state
    COMPLIANT = "compliant"  # No drift detected


class DriftSeverity(Enum):
    """Severity of detected drift."""
    INFO = "info"  # Cosmetic changes (tags, descriptions)
    LOW = "low"  # Minor configuration differences
    MEDIUM = "medium"  # Significant but not security-impacting
    HIGH = "high"  # Security-relevant configuration changes
    CRITICAL = "critical"  # Critical security drift (e.g., public S3, open SG)


class ResourceCategory(Enum):
    """Categories of AWS resources for drift detection."""
    IAM = "iam"
    S3 = "s3"
    EC2 = "ec2"
    VPC = "vpc"
    RDS = "rds"
    SECURITY = "security"
    LOGGING = "logging"
    KMS = "kms"


# Security-sensitive attributes that should trigger high/critical severity
SECURITY_SENSITIVE_ATTRIBUTES = {
    "s3": [
        "public_access_block",
        "bucket_policy",
        "encryption",
        "versioning",
        "logging"
    ],
    "iam": [
        "assume_role_policy",
        "attached_policies",
        "inline_policies",
        "mfa_enabled",
        "access_keys"
    ],
    "ec2": [
        "security_groups",
        "iam_instance_profile",
        "metadata_options",
        "ebs_encryption"
    ],
    "vpc": [
        "security_group_rules",
        "nacl_rules",
        "flow_logs",
        "route_table_routes"
    ],
    "rds": [
        "publicly_accessible",
        "encryption",
        "iam_auth",
        "security_groups",
        "backup_retention"
    ],
    "kms": [
        "key_policy",
        "key_rotation",
        "key_state"
    ]
}


@dataclass
class DriftItem:
    """A single drift detection result."""
    drift_id: str
    resource_type: str
    resource_id: str
    resource_arn: str
    drift_type: str
    severity: str
    account_id: str
    region: str

    # What changed
    attribute: str
    expected_value: Any
    actual_value: Any
    description: str

    # Metadata
    detected_at: str
    baseline_source: str  # "terraform_state", "config_rule", "baseline_snapshot"
    baseline_timestamp: str
    is_security_relevant: bool = False
    soc2_controls: list[str] = field(default_factory=list)

    # Status
    acknowledged: bool = False
    acknowledged_by: str = ""
    acknowledged_at: str = ""
    remediated: bool = False
    remediated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DriftItem":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DriftReport:
    """Summary of drift detection results."""
    report_id: str
    scan_started: str
    scan_completed: str
    account_id: str
    regions: list[str]

    total_resources_scanned: int
    resources_with_drift: int
    drift_items: list[DriftItem]

    by_severity: dict = field(default_factory=dict)
    by_resource_type: dict = field(default_factory=dict)
    by_drift_type: dict = field(default_factory=dict)

    critical_drifts: list[str] = field(default_factory=list)
    security_relevant_drifts: list[str] = field(default_factory=list)


# SOC 2 control mapping for drift items
DRIFT_CONTROL_MAPPING = {
    "s3.public_access_block": ["CC6.1", "CC6.7", "C1.1"],
    "s3.encryption": ["CC6.7", "C1.1"],
    "s3.versioning": ["A1.3", "CC9.2"],
    "s3.logging": ["CC7.2", "CC4.1"],
    "iam.mfa_enabled": ["CC6.1", "CC6.5"],
    "iam.attached_policies": ["CC6.1", "CC6.4"],
    "iam.assume_role_policy": ["CC6.1", "CC6.4"],
    "ec2.security_groups": ["CC6.1", "CC6.6"],
    "ec2.metadata_options": ["CC6.1", "CC6.4"],
    "vpc.security_group_rules": ["CC6.1", "CC6.6"],
    "vpc.flow_logs": ["CC7.2", "CC4.1"],
    "rds.publicly_accessible": ["CC6.1", "CC6.6"],
    "rds.encryption": ["CC6.7", "C1.1"],
    "kms.key_policy": ["CC6.7", "C1.1"],
}


class DriftDetector:
    """Service for detecting infrastructure drift."""

    def __init__(
        self,
        drift_table: str,
        baselines_bucket: str = None,
        terraform_state_bucket: str = None
    ):
        self.drift_table = drift_table
        self.baselines_bucket = baselines_bucket
        self.terraform_state_bucket = terraform_state_bucket

        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(drift_table)
        self.s3 = boto3.client("s3")

        # AWS service clients
        self.iam = boto3.client("iam")
        self.s3_client = boto3.client("s3")
        self.ec2 = boto3.client("ec2")
        self.rds = boto3.client("rds")
        self.kms = boto3.client("kms")
        self.sts = boto3.client("sts")
        self.config = boto3.client("config")

        self._account_id = None

    @property
    def account_id(self) -> str:
        if self._account_id is None:
            self._account_id = self.sts.get_caller_identity()["Account"]
        return self._account_id

    def detect_all_drift(self) -> DriftReport:
        """Run drift detection across all supported resource types."""
        scan_started = datetime.utcnow()
        report_id = f"drift_{scan_started.strftime('%Y%m%d%H%M%S')}"

        drift_items = []
        total_resources = 0

        # Detect drift for each category
        logger.info("Starting comprehensive drift detection")

        s3_drift, s3_count = self._detect_s3_drift()
        drift_items.extend(s3_drift)
        total_resources += s3_count

        iam_drift, iam_count = self._detect_iam_drift()
        drift_items.extend(iam_drift)
        total_resources += iam_count

        vpc_drift, vpc_count = self._detect_vpc_drift()
        drift_items.extend(vpc_drift)
        total_resources += vpc_count

        # Store drift items
        for item in drift_items:
            self.table.put_item(Item=item.to_dict())

        # Build report
        scan_completed = datetime.utcnow()

        report = DriftReport(
            report_id=report_id,
            scan_started=scan_started.isoformat(),
            scan_completed=scan_completed.isoformat(),
            account_id=self.account_id,
            regions=[boto3.Session().region_name],
            total_resources_scanned=total_resources,
            resources_with_drift=len(set(d.resource_id for d in drift_items)),
            drift_items=drift_items,
            by_severity={},
            by_resource_type={},
            by_drift_type={},
            critical_drifts=[],
            security_relevant_drifts=[]
        )

        # Calculate summaries
        for item in drift_items:
            report.by_severity[item.severity] = report.by_severity.get(item.severity, 0) + 1
            report.by_resource_type[item.resource_type] = report.by_resource_type.get(item.resource_type, 0) + 1
            report.by_drift_type[item.drift_type] = report.by_drift_type.get(item.drift_type, 0) + 1

            if item.severity == DriftSeverity.CRITICAL.value:
                report.critical_drifts.append(item.drift_id)
            if item.is_security_relevant:
                report.security_relevant_drifts.append(item.drift_id)

        logger.info(f"Drift detection complete: {len(drift_items)} drift items found across {total_resources} resources")
        return report

    def _detect_s3_drift(self) -> tuple[list[DriftItem], int]:
        """Detect drift in S3 bucket configurations."""
        drift_items = []
        bucket_count = 0

        try:
            buckets = self.s3_client.list_buckets()["Buckets"]
            bucket_count = len(buckets)

            for bucket in buckets:
                bucket_name = bucket["Name"]
                bucket_arn = f"arn:aws:s3:::{bucket_name}"

                # Check public access block
                try:
                    pab = self.s3_client.get_public_access_block(Bucket=bucket_name)
                    config = pab["PublicAccessBlockConfiguration"]

                    # All should be True for compliant buckets
                    expected_all_blocked = True
                    actual_all_blocked = all([
                        config.get("BlockPublicAcls", False),
                        config.get("IgnorePublicAcls", False),
                        config.get("BlockPublicPolicy", False),
                        config.get("RestrictPublicBuckets", False)
                    ])

                    if not actual_all_blocked:
                        drift_items.append(self._create_drift_item(
                            resource_type="s3_bucket",
                            resource_id=bucket_name,
                            resource_arn=bucket_arn,
                            attribute="public_access_block",
                            expected_value="All blocked",
                            actual_value=config,
                            description=f"S3 bucket {bucket_name} does not have all public access blocked",
                            severity=DriftSeverity.CRITICAL,
                            is_security_relevant=True
                        ))

                except ClientError as e:
                    if e.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
                        drift_items.append(self._create_drift_item(
                            resource_type="s3_bucket",
                            resource_id=bucket_name,
                            resource_arn=bucket_arn,
                            attribute="public_access_block",
                            expected_value="Configured",
                            actual_value="Not configured",
                            description=f"S3 bucket {bucket_name} has no public access block configured",
                            severity=DriftSeverity.CRITICAL,
                            is_security_relevant=True
                        ))

                # Check encryption
                try:
                    encryption = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
                    # Has encryption, check if it's proper
                    rules = encryption["ServerSideEncryptionConfiguration"]["Rules"]
                    has_proper_encryption = any(
                        r.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") in ["aws:kms", "AES256"]
                        for r in rules
                    )
                    if not has_proper_encryption:
                        drift_items.append(self._create_drift_item(
                            resource_type="s3_bucket",
                            resource_id=bucket_name,
                            resource_arn=bucket_arn,
                            attribute="encryption",
                            expected_value="AES256 or aws:kms",
                            actual_value=rules,
                            description=f"S3 bucket {bucket_name} encryption configuration may be insufficient",
                            severity=DriftSeverity.HIGH,
                            is_security_relevant=True
                        ))
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                        drift_items.append(self._create_drift_item(
                            resource_type="s3_bucket",
                            resource_id=bucket_name,
                            resource_arn=bucket_arn,
                            attribute="encryption",
                            expected_value="Enabled",
                            actual_value="Not configured",
                            description=f"S3 bucket {bucket_name} has no default encryption configured",
                            severity=DriftSeverity.HIGH,
                            is_security_relevant=True
                        ))

                # Check versioning
                try:
                    versioning = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                    status = versioning.get("Status", "Disabled")
                    if status != "Enabled":
                        drift_items.append(self._create_drift_item(
                            resource_type="s3_bucket",
                            resource_id=bucket_name,
                            resource_arn=bucket_arn,
                            attribute="versioning",
                            expected_value="Enabled",
                            actual_value=status,
                            description=f"S3 bucket {bucket_name} versioning is not enabled",
                            severity=DriftSeverity.MEDIUM,
                            is_security_relevant=False
                        ))
                except ClientError:
                    pass

        except ClientError as e:
            logger.exception("Error detecting S3 drift")

        return drift_items, bucket_count

    def _detect_iam_drift(self) -> tuple[list[DriftItem], int]:
        """Detect drift in IAM configurations."""
        drift_items = []
        resource_count = 0

        try:
            # Check IAM users for MFA
            users = self.iam.list_users()["Users"]
            resource_count += len(users)

            for user in users:
                user_name = user["UserName"]
                user_arn = user["Arn"]

                # Check MFA
                mfa_devices = self.iam.list_mfa_devices(UserName=user_name)["MFADevices"]
                if not mfa_devices:
                    # Check if user has console access
                    try:
                        self.iam.get_login_profile(UserName=user_name)
                        has_console = True
                    except self.iam.exceptions.NoSuchEntityException:
                        has_console = False

                    if has_console:
                        drift_items.append(self._create_drift_item(
                            resource_type="iam_user",
                            resource_id=user_name,
                            resource_arn=user_arn,
                            attribute="mfa_enabled",
                            expected_value=True,
                            actual_value=False,
                            description=f"IAM user {user_name} has console access without MFA",
                            severity=DriftSeverity.CRITICAL,
                            is_security_relevant=True
                        ))

                # Check for old access keys
                access_keys = self.iam.list_access_keys(UserName=user_name)["AccessKeyMetadata"]
                for key in access_keys:
                    if key["Status"] == "Active":
                        age_days = (datetime.utcnow() - key["CreateDate"].replace(tzinfo=None)).days
                        if age_days > 90:
                            drift_items.append(self._create_drift_item(
                                resource_type="iam_user",
                                resource_id=user_name,
                                resource_arn=user_arn,
                                attribute="access_key_age",
                                expected_value="< 90 days",
                                actual_value=f"{age_days} days",
                                description=f"IAM user {user_name} has access key {key['AccessKeyId']} that is {age_days} days old",
                                severity=DriftSeverity.HIGH if age_days > 180 else DriftSeverity.MEDIUM,
                                is_security_relevant=True
                            ))

            # Check password policy
            try:
                policy = self.iam.get_account_password_policy()["PasswordPolicy"]

                if policy.get("MinimumPasswordLength", 0) < 14:
                    drift_items.append(self._create_drift_item(
                        resource_type="iam_password_policy",
                        resource_id="account_password_policy",
                        resource_arn=f"arn:aws:iam::{self.account_id}:account-password-policy",
                        attribute="minimum_length",
                        expected_value=14,
                        actual_value=policy.get("MinimumPasswordLength", 0),
                        description="IAM password policy minimum length is less than 14 characters",
                        severity=DriftSeverity.MEDIUM,
                        is_security_relevant=True
                    ))

                if not policy.get("RequireMFA", False):
                    drift_items.append(self._create_drift_item(
                        resource_type="iam_password_policy",
                        resource_id="account_password_policy",
                        resource_arn=f"arn:aws:iam::{self.account_id}:account-password-policy",
                        attribute="require_mfa",
                        expected_value=True,
                        actual_value=False,
                        description="IAM password policy does not require MFA",
                        severity=DriftSeverity.HIGH,
                        is_security_relevant=True
                    ))

                resource_count += 1

            except self.iam.exceptions.NoSuchEntityException:
                drift_items.append(self._create_drift_item(
                    resource_type="iam_password_policy",
                    resource_id="account_password_policy",
                    resource_arn=f"arn:aws:iam::{self.account_id}:account-password-policy",
                    attribute="policy_exists",
                    expected_value=True,
                    actual_value=False,
                    description="No IAM password policy is configured for the account",
                    severity=DriftSeverity.HIGH,
                    is_security_relevant=True
                ))

        except ClientError as e:
            logger.exception("Error detecting IAM drift")

        return drift_items, resource_count

    def _detect_vpc_drift(self) -> tuple[list[DriftItem], int]:
        """Detect drift in VPC configurations."""
        drift_items = []
        resource_count = 0

        try:
            # Check for overly permissive security groups
            security_groups = self.ec2.describe_security_groups()["SecurityGroups"]
            resource_count += len(security_groups)

            for sg in security_groups:
                sg_id = sg["GroupId"]
                sg_name = sg["GroupName"]
                vpc_id = sg.get("VpcId", "ec2-classic")

                # Check for 0.0.0.0/0 ingress on sensitive ports
                sensitive_ports = {22: "SSH", 3389: "RDP", 3306: "MySQL", 5432: "PostgreSQL", 1433: "MSSQL", 27017: "MongoDB"}

                for rule in sg.get("IpPermissions", []):
                    from_port = rule.get("FromPort", 0)
                    to_port = rule.get("ToPort", 65535)

                    for ip_range in rule.get("IpRanges", []):
                        if ip_range.get("CidrIp") == "0.0.0.0/0":
                            # Check if any sensitive port is in range
                            for port, service in sensitive_ports.items():
                                if from_port <= port <= to_port:
                                    drift_items.append(self._create_drift_item(
                                        resource_type="security_group",
                                        resource_id=sg_id,
                                        resource_arn=f"arn:aws:ec2:{boto3.Session().region_name}:{self.account_id}:security-group/{sg_id}",
                                        attribute="ingress_rule",
                                        expected_value="Restricted CIDR",
                                        actual_value=f"0.0.0.0/0 on port {port} ({service})",
                                        description=f"Security group {sg_name} ({sg_id}) allows {service} from anywhere",
                                        severity=DriftSeverity.CRITICAL,
                                        is_security_relevant=True
                                    ))
                                    break

            # Check VPCs for flow logs
            vpcs = self.ec2.describe_vpcs()["Vpcs"]
            resource_count += len(vpcs)

            for vpc in vpcs:
                vpc_id = vpc["VpcId"]

                flow_logs = self.ec2.describe_flow_logs(
                    Filters=[{"Name": "resource-id", "Values": [vpc_id]}]
                )["FlowLogs"]

                if not flow_logs:
                    drift_items.append(self._create_drift_item(
                        resource_type="vpc",
                        resource_id=vpc_id,
                        resource_arn=f"arn:aws:ec2:{boto3.Session().region_name}:{self.account_id}:vpc/{vpc_id}",
                        attribute="flow_logs",
                        expected_value="Enabled",
                        actual_value="Not configured",
                        description=f"VPC {vpc_id} does not have flow logs enabled",
                        severity=DriftSeverity.HIGH,
                        is_security_relevant=True
                    ))

        except ClientError as e:
            logger.exception("Error detecting VPC drift")

        return drift_items, resource_count

    def _create_drift_item(
        self,
        resource_type: str,
        resource_id: str,
        resource_arn: str,
        attribute: str,
        expected_value: Any,
        actual_value: Any,
        description: str,
        severity: DriftSeverity,
        is_security_relevant: bool
    ) -> DriftItem:
        """Create a drift item."""
        timestamp = datetime.utcnow()

        # Look up SOC 2 controls
        control_key = f"{resource_type.split('_')[0]}.{attribute}"
        soc2_controls = DRIFT_CONTROL_MAPPING.get(control_key, [])

        drift_id = f"drift_{timestamp.strftime('%Y%m%d%H%M%S')}_{hashlib.sha256(f'{resource_id}:{attribute}'.encode()).hexdigest()[:8]}"

        return DriftItem(
            drift_id=drift_id,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_arn=resource_arn,
            drift_type=DriftType.MODIFIED.value,
            severity=severity.value,
            account_id=self.account_id,
            region=boto3.Session().region_name,
            attribute=attribute,
            expected_value=json.dumps(expected_value) if not isinstance(expected_value, str) else expected_value,
            actual_value=json.dumps(actual_value) if not isinstance(actual_value, str) else actual_value,
            description=description,
            detected_at=timestamp.isoformat(),
            baseline_source="compliance_baseline",
            baseline_timestamp=timestamp.isoformat(),
            is_security_relevant=is_security_relevant,
            soc2_controls=soc2_controls
        )

    def compare_with_terraform_state(self, state_file_key: str) -> list[DriftItem]:
        """Compare current state with Terraform state file."""
        if not self.terraform_state_bucket:
            logger.warning("No Terraform state bucket configured")
            return []

        drift_items = []

        try:
            # Fetch Terraform state
            response = self.s3.get_object(
                Bucket=self.terraform_state_bucket,
                Key=state_file_key
            )
            state = json.loads(response["Body"].read().decode("utf-8"))

            # Parse resources from state
            resources = state.get("resources", [])

            for resource in resources:
                resource_type = resource.get("type", "")
                instances = resource.get("instances", [])

                for instance in instances:
                    attributes = instance.get("attributes", {})

                    # Compare based on resource type
                    if resource_type == "aws_s3_bucket":
                        bucket_name = attributes.get("bucket")
                        bucket_drifts = self._compare_s3_bucket(bucket_name, attributes)
                        drift_items.extend(bucket_drifts)

                    elif resource_type == "aws_security_group":
                        sg_id = attributes.get("id")
                        sg_drifts = self._compare_security_group(sg_id, attributes)
                        drift_items.extend(sg_drifts)

            logger.info(f"Terraform state comparison found {len(drift_items)} drift items")

        except ClientError as e:
            logger.exception("Error comparing with Terraform state")

        return drift_items

    def _compare_s3_bucket(self, bucket_name: str, tf_attributes: dict) -> list[DriftItem]:
        """Compare S3 bucket with Terraform state."""
        drift_items = []

        try:
            # Get current encryption
            try:
                current_encryption = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
            except ClientError:
                current_encryption = None

            tf_encryption = tf_attributes.get("server_side_encryption_configuration", [])

            # Simple comparison - in production this would be more sophisticated
            if bool(current_encryption) != bool(tf_encryption):
                drift_items.append(self._create_drift_item(
                    resource_type="s3_bucket",
                    resource_id=bucket_name,
                    resource_arn=f"arn:aws:s3:::{bucket_name}",
                    attribute="encryption",
                    expected_value=tf_encryption,
                    actual_value=current_encryption,
                    description=f"S3 bucket {bucket_name} encryption differs from Terraform state",
                    severity=DriftSeverity.HIGH,
                    is_security_relevant=True
                ))

        except Exception as e:
            logger.warning(f"Error comparing S3 bucket {bucket_name}: {e}")

        return drift_items

    def _compare_security_group(self, sg_id: str, tf_attributes: dict) -> list[DriftItem]:
        """Compare security group with Terraform state."""
        drift_items = []

        try:
            current_sg = self.ec2.describe_security_groups(GroupIds=[sg_id])["SecurityGroups"][0]

            # Compare ingress rules count as simple check
            tf_ingress = tf_attributes.get("ingress", [])
            current_ingress = current_sg.get("IpPermissions", [])

            if len(tf_ingress) != len(current_ingress):
                drift_items.append(self._create_drift_item(
                    resource_type="security_group",
                    resource_id=sg_id,
                    resource_arn=f"arn:aws:ec2:{boto3.Session().region_name}:{self.account_id}:security-group/{sg_id}",
                    attribute="ingress_rules",
                    expected_value=f"{len(tf_ingress)} rules",
                    actual_value=f"{len(current_ingress)} rules",
                    description=f"Security group {sg_id} ingress rule count differs from Terraform state",
                    severity=DriftSeverity.HIGH,
                    is_security_relevant=True
                ))

        except Exception as e:
            logger.warning(f"Error comparing security group {sg_id}: {e}")

        return drift_items

    def get_drift_summary(self) -> dict:
        """Get summary of current drift status."""
        try:
            response = self.table.scan()
            items = response.get("Items", [])

            # Only count unacknowledged drift
            active_drift = [i for i in items if not i.get("acknowledged", False) and not i.get("remediated", False)]

            summary = {
                "total_drift_items": len(active_drift),
                "by_severity": {},
                "by_resource_type": {},
                "critical_count": 0,
                "security_relevant_count": 0,
                "last_scan": None
            }

            for item in active_drift:
                severity = item.get("severity", "unknown")
                resource_type = item.get("resource_type", "unknown")

                summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
                summary["by_resource_type"][resource_type] = summary["by_resource_type"].get(resource_type, 0) + 1

                if severity == "critical":
                    summary["critical_count"] += 1
                if item.get("is_security_relevant"):
                    summary["security_relevant_count"] += 1

            # Get last scan time
            if items:
                summary["last_scan"] = max(i.get("detected_at", "") for i in items)

            return summary

        except Exception as e:
            logger.exception("Error getting drift summary")
            return {"error": str(e)}

    def acknowledge_drift(self, drift_id: str, user_id: str, notes: str = "") -> bool:
        """Acknowledge a drift item (mark as reviewed)."""
        try:
            self.table.update_item(
                Key={"drift_id": drift_id},
                UpdateExpression="SET acknowledged = :ack, acknowledged_by = :user, acknowledged_at = :time, notes = :notes",
                ExpressionAttributeValues={
                    ":ack": True,
                    ":user": user_id,
                    ":time": datetime.utcnow().isoformat(),
                    ":notes": notes
                }
            )
            return True
        except Exception as e:
            logger.exception(f"Error acknowledging drift {drift_id}")
            return False

    def mark_remediated(self, drift_id: str) -> bool:
        """Mark a drift item as remediated."""
        try:
            self.table.update_item(
                Key={"drift_id": drift_id},
                UpdateExpression="SET remediated = :rem, remediated_at = :time",
                ExpressionAttributeValues={
                    ":rem": True,
                    ":time": datetime.utcnow().isoformat()
                }
            )
            return True
        except Exception as e:
            logger.exception(f"Error marking drift {drift_id} as remediated")
            return False

    def format_drift_report_for_slack(self, report: DriftReport) -> dict:
        """Format drift report for Slack."""
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "info": "ℹ️"
        }

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Infrastructure Drift Report"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Resources Scanned:* {report.total_resources_scanned}"},
                    {"type": "mrkdwn", "text": f"*Resources with Drift:* {report.resources_with_drift}"},
                    {"type": "mrkdwn", "text": f"*Total Drift Items:* {len(report.drift_items)}"},
                    {"type": "mrkdwn", "text": f"*Critical:* {report.by_severity.get('critical', 0)}"},
                ]
            },
            {"type": "divider"}
        ]

        # Add severity breakdown
        severity_text = " | ".join([
            f"{severity_emoji.get(sev, '❓')} {sev.title()}: {count}"
            for sev, count in sorted(report.by_severity.items(), key=lambda x: ["critical", "high", "medium", "low", "info"].index(x[0]) if x[0] in ["critical", "high", "medium", "low", "info"] else 99)
        ])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*By Severity:* {severity_text}"}
        })

        # Show critical items
        if report.critical_drifts:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*🔴 Critical Drift Items:*"}
            })

            for drift_id in report.critical_drifts[:5]:
                item = next((d for d in report.drift_items if d.drift_id == drift_id), None)
                if item:
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"• `{item.resource_id}` - {item.description[:100]}"}
                    })

            if len(report.critical_drifts) > 5:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"_...and {len(report.critical_drifts) - 5} more critical items_"}]
                })

        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Scan completed: {report.scan_completed}"}]
        })

        return {"blocks": blocks}
