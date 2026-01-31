"""
Generic AWS Resource Scanner for CARL.

Lightweight, reusable AWS resource scanning without storage or analysis overhead.
Used by multiple services:
- /carl ask (scan for questions)
- /carl drift scan (detect drift)
- /carl compliance assess (audit scanning)
- EvidenceCollector (wraps this + adds storage layer)

This scanner ONLY collects raw data from AWS APIs - no storage, no security analysis.
"""

import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceScanResult:
    """Lightweight scan result without storage metadata or security analysis."""
    service: str
    resource_type: str
    resource_id: str
    resource_name: str
    region: str
    account_id: str
    data: dict[str, Any]
    scanned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tags: dict[str, str] = field(default_factory=dict)


class AWSResourceScanner:
    """
    Generic AWS resource scanner.

    Scans AWS APIs and returns structured data without storage overhead.
    Designed to be lightweight and reusable across multiple CARL services.
    """

    def __init__(self, region: str = None):
        """
        Initialize AWS scanner.

        Args:
            region: AWS region (defaults to session region)
        """
        self.region = region or boto3.Session().region_name

        # AWS service clients
        self.iam = boto3.client("iam")
        self.s3 = boto3.client("s3")
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.rds = boto3.client("rds", region_name=self.region)
        self.config = boto3.client("config", region_name=self.region)
        self.securityhub = boto3.client("securityhub", region_name=self.region)
        self.cloudtrail = boto3.client("cloudtrail", region_name=self.region)
        self.guardduty = boto3.client("guardduty", region_name=self.region)
        self.lambda_client = boto3.client("lambda", region_name=self.region)
        self.kms = boto3.client("kms", region_name=self.region)
        self.secretsmanager = boto3.client("secretsmanager", region_name=self.region)
        self.ecs = boto3.client("ecs", region_name=self.region)
        self.eks = boto3.client("eks", region_name=self.region)
        self.dynamodb = boto3.client("dynamodb", region_name=self.region)
        self.logs = boto3.client("logs", region_name=self.region)
        self.cloudwatch = boto3.client("cloudwatch", region_name=self.region)
        self.inspector2 = boto3.client("inspector2", region_name=self.region)
        self.macie2 = boto3.client("macie2", region_name=self.region)
        self.sts = boto3.client("sts")

        self._account_id = None

    @property
    def account_id(self) -> str:
        """Get AWS account ID (cached)."""
        if self._account_id is None:
            self._account_id = self.sts.get_caller_identity()["Account"]
        return self._account_id

    def scan_iam(self) -> list[ResourceScanResult]:
        """Scan IAM resources for users, roles, policies, password policy."""
        results = []

        try:
            # 1. IAM Users with MFA status
            users = self.iam.list_users()["Users"]
            for user in users:
                user_name = user["UserName"]

                # Get MFA devices
                try:
                    mfa_devices = self.iam.list_mfa_devices(UserName=user_name)["MFADevices"]
                    mfa_enabled = len(mfa_devices) > 0
                except ClientError:
                    mfa_enabled = False

                results.append(ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::User",
                    resource_id=user["UserId"],
                    resource_name=user_name,
                    region="global",
                    account_id=self.account_id,
                    data={
                        "user_name": user_name,
                        "arn": user["Arn"],
                        "created_date": user["CreateDate"].isoformat(),
                        "mfa_enabled": mfa_enabled,
                        "mfa_device_count": len(mfa_devices) if mfa_enabled else 0
                    }
                ))

            logger.info(f"Scanned {len(users)} IAM users")

        except ClientError as e:
            logger.warning(f"Failed to scan IAM users: {e}")

        try:
            # 2. Password Policy
            policy = self.iam.get_account_password_policy()["PasswordPolicy"]
            results.append(ResourceScanResult(
                service="iam",
                resource_type="AWS::IAM::AccountPasswordPolicy",
                resource_id=self.account_id,
                resource_name="AccountPasswordPolicy",
                region="global",
                account_id=self.account_id,
                data={
                    "minimum_password_length": policy.get("MinimumPasswordLength", 0),
                    "require_symbols": policy.get("RequireSymbols", False),
                    "require_numbers": policy.get("RequireNumbers", False),
                    "require_uppercase": policy.get("RequireUppercaseCharacters", False),
                    "require_lowercase": policy.get("RequireLowercaseCharacters", False),
                    "allow_users_to_change": policy.get("AllowUsersToChangePassword", False),
                    "expire_passwords": policy.get("ExpirePasswords", False),
                    "max_password_age": policy.get("MaxPasswordAge", 0),
                    "password_reuse_prevention": policy.get("PasswordReusePrevention", 0),
                }
            ))
            logger.info("Scanned IAM password policy")

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                # No password policy configured
                results.append(ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::AccountPasswordPolicy",
                    resource_id=self.account_id,
                    resource_name="AccountPasswordPolicy",
                    region="global",
                    account_id=self.account_id,
                    data={"configured": False, "error": "NOT CONFIGURED"}
                ))
                logger.warning("IAM password policy not configured")
            else:
                logger.warning(f"Failed to get password policy: {e}")

        try:
            # 3. IAM Roles
            roles = self.iam.list_roles()["Roles"]
            for role in roles[:50]:  # Limit to first 50 to avoid overwhelming
                results.append(ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::Role",
                    resource_id=role["RoleId"],
                    resource_name=role["RoleName"],
                    region="global",
                    account_id=self.account_id,
                    data={
                        "role_name": role["RoleName"],
                        "arn": role["Arn"],
                        "created_date": role["CreateDate"].isoformat(),
                        "description": role.get("Description", ""),
                        "max_session_duration": role.get("MaxSessionDuration", 3600)
                    }
                ))

            logger.info(f"Scanned {len(roles)} IAM roles (showing first 50)")

        except ClientError as e:
            logger.warning(f"Failed to scan IAM roles: {e}")

        return results

    def scan_s3(self) -> list[ResourceScanResult]:
        """Scan S3 buckets for encryption, versioning, public access."""
        results = []

        try:
            buckets = self.s3.list_buckets()["Buckets"]

            for bucket in buckets:
                bucket_name = bucket["Name"]
                bucket_data = {
                    "bucket_name": bucket_name,
                    "created_date": bucket["CreationDate"].isoformat(),
                }

                # Get encryption
                try:
                    encryption = self.s3.get_bucket_encryption(Bucket=bucket_name)
                    bucket_data["encryption_enabled"] = True
                    bucket_data["encryption"] = encryption["ServerSideEncryptionConfiguration"]
                except ClientError as e:
                    if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                        bucket_data["encryption_enabled"] = False
                        bucket_data["encryption"] = None
                    else:
                        bucket_data["encryption_enabled"] = False
                        bucket_data["encryption"] = "ERROR"

                # Get public access block
                try:
                    public_access = self.s3.get_public_access_block(Bucket=bucket_name)
                    bucket_data["public_access_block"] = public_access["PublicAccessBlockConfiguration"]
                except ClientError:
                    bucket_data["public_access_block"] = None

                # Get versioning
                try:
                    versioning = self.s3.get_bucket_versioning(Bucket=bucket_name)
                    bucket_data["versioning_enabled"] = versioning.get("Status", "Disabled") == "Enabled"
                except ClientError:
                    bucket_data["versioning_enabled"] = False

                # Get tags
                try:
                    tag_response = self.s3.get_bucket_tagging(Bucket=bucket_name)
                    tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("TagSet", [])}
                except ClientError:
                    tags = {}

                results.append(ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id=bucket_name,
                    resource_name=bucket_name,
                    region="global",
                    account_id=self.account_id,
                    data=bucket_data,
                    tags=tags
                ))

            logger.info(f"Scanned {len(buckets)} S3 buckets")

        except ClientError as e:
            logger.warning(f"Failed to scan S3 buckets: {e}")

        return results

    def scan_vpc(self) -> list[ResourceScanResult]:
        """Scan VPC resources for security groups, flow logs, network ACLs."""
        results = []

        try:
            # 1. VPCs
            vpcs = self.ec2.describe_vpcs()["Vpcs"]
            for vpc in vpcs:
                vpc_id = vpc["VpcId"]
                results.append(ResourceScanResult(
                    service="vpc",
                    resource_type="AWS::EC2::VPC",
                    resource_id=vpc_id,
                    resource_name=vpc.get("Tags", [{}])[0].get("Value", vpc_id) if vpc.get("Tags") else vpc_id,
                    region=self.region,
                    account_id=self.account_id,
                    data={
                        "vpc_id": vpc_id,
                        "cidr_block": vpc.get("CidrBlock"),
                        "state": vpc.get("State"),
                        "is_default": vpc.get("IsDefault", False)
                    }
                ))

            logger.info(f"Scanned {len(vpcs)} VPCs")

        except ClientError as e:
            logger.warning(f"Failed to scan VPCs: {e}")

        try:
            # 2. Security Groups
            security_groups = self.ec2.describe_security_groups()["SecurityGroups"]
            for sg in security_groups:
                results.append(ResourceScanResult(
                    service="vpc",
                    resource_type="AWS::EC2::SecurityGroup",
                    resource_id=sg["GroupId"],
                    resource_name=sg.get("GroupName", sg["GroupId"]),
                    region=self.region,
                    account_id=self.account_id,
                    data={
                        "group_id": sg["GroupId"],
                        "group_name": sg.get("GroupName"),
                        "vpc_id": sg.get("VpcId"),
                        "description": sg.get("Description"),
                        "ingress_rules": sg.get("IpPermissions", []),
                        "egress_rules": sg.get("IpPermissionsEgress", [])
                    }
                ))

            logger.info(f"Scanned {len(security_groups)} security groups")

        except ClientError as e:
            logger.warning(f"Failed to scan security groups: {e}")

        try:
            # 3. Flow Logs
            flow_logs = self.ec2.describe_flow_logs()["FlowLogs"]
            for log in flow_logs:
                results.append(ResourceScanResult(
                    service="vpc",
                    resource_type="AWS::EC2::FlowLog",
                    resource_id=log["FlowLogId"],
                    resource_name=log["FlowLogId"],
                    region=self.region,
                    account_id=self.account_id,
                    data={
                        "flow_log_id": log["FlowLogId"],
                        "resource_id": log.get("ResourceId"),
                        "traffic_type": log.get("TrafficType"),
                        "log_destination": log.get("LogDestination"),
                        "status": log.get("FlowLogStatus")
                    }
                ))

            logger.info(f"Scanned {len(flow_logs)} VPC flow logs")

        except ClientError as e:
            logger.warning(f"Failed to scan VPC flow logs: {e}")

        return results

    def scan_ec2(self) -> list[ResourceScanResult]:
        """Scan EC2 instances."""
        results = []

        try:
            reservations = self.ec2.describe_instances()["Reservations"]
            for reservation in reservations:
                for instance in reservation["Instances"]:
                    instance_id = instance["InstanceId"]

                    # Get instance name from tags
                    name = instance_id
                    for tag in instance.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                            break

                    results.append(ResourceScanResult(
                        service="ec2",
                        resource_type="AWS::EC2::Instance",
                        resource_id=instance_id,
                        resource_name=name,
                        region=self.region,
                        account_id=self.account_id,
                        data={
                            "instance_id": instance_id,
                            "instance_type": instance.get("InstanceType"),
                            "state": instance.get("State", {}).get("Name"),
                            "launch_time": instance.get("LaunchTime").isoformat() if instance.get("LaunchTime") else None,
                            "vpc_id": instance.get("VpcId"),
                            "subnet_id": instance.get("SubnetId"),
                            "private_ip": instance.get("PrivateIpAddress"),
                            "public_ip": instance.get("PublicIpAddress")
                        },
                        tags={tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
                    ))

            total_instances = sum(len(r["Instances"]) for r in reservations)
            logger.info(f"Scanned {total_instances} EC2 instances")

        except ClientError as e:
            logger.warning(f"Failed to scan EC2 instances: {e}")

        return results

    def scan_all(self, progress_callback: Optional[Callable[[str, int, int, int], None]] = None) -> dict[str, list[ResourceScanResult]]:
        """
        Scan all AWS services.

        Args:
            progress_callback: Optional function(service_name, completed, total, resources_found)

        Returns:
            Dict mapping service name to list of scan results
        """
        services = [
            ("IAM", self.scan_iam),
            ("S3", self.scan_s3),
            ("VPC", self.scan_vpc),
            ("EC2", self.scan_ec2),
        ]

        results = {}
        total_services = len(services)

        for idx, (service_name, scan_func) in enumerate(services, 1):
            logger.info(f"Scanning {service_name}...")
            scan_results = scan_func()
            service_key = service_name.lower()
            results[service_key] = scan_results

            # Report progress
            if progress_callback:
                try:
                    progress_callback(
                        service_name=service_name,
                        completed=idx,
                        total=total_services,
                        resources_found=len(scan_results)
                    )
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

        total_resources = sum(len(items) for items in results.values())
        logger.info(f"Scan complete: {total_resources} resources across {len(results)} services")

        return results
