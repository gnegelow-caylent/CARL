"""
AWS resource detection service.

Scans AWS environment to detect existing resources so CARL can generate
code only for what's missing.

Used by:
- Foundation Builder (smart infrastructure generation)
- Remediation Agent (skip already-compliant resources)
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SecurityResourcesStatus:
    """Status of security resources in the AWS account."""
    guardduty_exists: bool
    guardduty_detector_id: Optional[str]
    security_hub_exists: bool
    security_hub_arn: Optional[str]
    config_exists: bool
    config_recorder_name: Optional[str]
    cloudtrail_exists: bool
    cloudtrail_name: Optional[str]
    cloudtrail_bucket: Optional[str]


@dataclass
class VPCResourcesStatus:
    """Status of VPC resources in the AWS account."""
    vpc_exists: bool
    vpc_id: Optional[str]
    vpc_cidr: Optional[str]
    subnets_exist: bool
    subnet_count: int
    nat_gateways_exist: bool
    nat_gateway_count: int
    internet_gateway_exists: bool


@dataclass
class VPCFlowLogsStatus:
    """Status of VPC Flow Logs for a specific VPC."""
    flow_logs_enabled: bool
    flow_log_id: Optional[str] = None
    log_destination_type: Optional[str] = None  # cloud-watch-logs, s3
    log_destination: Optional[str] = None  # Log group ARN or S3 bucket ARN
    traffic_type: Optional[str] = None  # ACCEPT, REJECT, ALL


@dataclass
class S3BucketStatus:
    """Status of S3 bucket security configuration."""
    bucket_name: str
    encryption_enabled: bool
    encryption_type: Optional[str] = None  # AES256, aws:kms
    kms_key_id: Optional[str] = None
    versioning_enabled: bool = False
    public_access_block_enabled: bool = False
    block_public_acls: bool = False
    ignore_public_acls: bool = False
    block_public_policy: bool = False
    restrict_public_buckets: bool = False


@dataclass
class IAMPasswordPolicyStatus:
    """Status of IAM account password policy."""
    policy_exists: bool
    minimum_password_length: int = 0
    require_symbols: bool = False
    require_numbers: bool = False
    require_uppercase: bool = False
    require_lowercase: bool = False
    allow_users_to_change: bool = True
    max_password_age: int = 0
    password_reuse_prevention: int = 0
    hard_expiry: bool = False
    is_compliant: bool = False  # Meets SOC2/CIS standards


@dataclass
class CloudWatchLogGroupStatus:
    """Status of a CloudWatch Log Group."""
    log_group_name: str
    exists: bool
    arn: Optional[str] = None
    retention_days: Optional[int] = None
    kms_key_id: Optional[str] = None


class ResourceDetector:
    """Detects existing AWS resources to avoid duplicate creation."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.guardduty = boto3.client("guardduty", region_name=region)
        self.securityhub = boto3.client("securityhub", region_name=region)
        self.config = boto3.client("config", region_name=region)
        self.cloudtrail = boto3.client("cloudtrail", region_name=region)
        self.ec2 = boto3.client("ec2", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)
        self.iam = boto3.client("iam", region_name=region)
        self.logs = boto3.client("logs", region_name=region)

    def detect_security_resources(self) -> SecurityResourcesStatus:
        """
        Detect existing security resources in the AWS account.

        Returns:
            SecurityResourcesStatus with detection results
        """
        guardduty_detector_id = None
        guardduty_exists = False

        security_hub_exists = False
        security_hub_arn = None

        config_exists = False
        config_recorder_name = None

        cloudtrail_exists = False
        cloudtrail_name = None
        cloudtrail_bucket = None

        # Check GuardDuty
        try:
            response = self.guardduty.list_detectors()
            if response.get("DetectorIds"):
                guardduty_exists = True
                guardduty_detector_id = response["DetectorIds"][0]
                logger.info(f"Found existing GuardDuty detector: {guardduty_detector_id}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "AccessDeniedException":
                logger.warning(f"Error checking GuardDuty: {e}")

        # Check Security Hub
        try:
            response = self.securityhub.describe_hub()
            if response.get("HubArn"):
                security_hub_exists = True
                security_hub_arn = response["HubArn"]
                logger.info(f"Found existing Security Hub: {security_hub_arn}")
        except ClientError as e:
            if e.response["Error"]["Code"] not in ["ResourceNotFoundException", "InvalidAccessException"]:
                logger.warning(f"Error checking Security Hub: {e}")

        # Check AWS Config
        try:
            response = self.config.describe_configuration_recorders()
            if response.get("ConfigurationRecorders"):
                config_exists = True
                config_recorder_name = response["ConfigurationRecorders"][0]["name"]
                logger.info(f"Found existing Config recorder: {config_recorder_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "AccessDeniedException":
                logger.warning(f"Error checking Config: {e}")

        # Check CloudTrail
        try:
            response = self.cloudtrail.describe_trails()
            if response.get("trailList"):
                # Find multi-region trail
                for trail in response["trailList"]:
                    if trail.get("IsMultiRegionTrail"):
                        cloudtrail_exists = True
                        cloudtrail_name = trail["Name"]
                        cloudtrail_bucket = trail.get("S3BucketName")
                        logger.info(f"Found existing CloudTrail: {cloudtrail_name}")
                        break
        except ClientError as e:
            if e.response["Error"]["Code"] != "AccessDeniedException":
                logger.warning(f"Error checking CloudTrail: {e}")

        return SecurityResourcesStatus(
            guardduty_exists=guardduty_exists,
            guardduty_detector_id=guardduty_detector_id,
            security_hub_exists=security_hub_exists,
            security_hub_arn=security_hub_arn,
            config_exists=config_exists,
            config_recorder_name=config_recorder_name,
            cloudtrail_exists=cloudtrail_exists,
            cloudtrail_name=cloudtrail_name,
            cloudtrail_bucket=cloudtrail_bucket,
        )

    def detect_vpc_resources(self, vpc_name_filter: Optional[str] = None) -> VPCResourcesStatus:
        """
        Detect existing VPC resources.

        Args:
            vpc_name_filter: Optional VPC name to look for

        Returns:
            VPCResourcesStatus with detection results
        """
        vpc_exists = False
        vpc_id = None
        vpc_cidr = None
        subnets_exist = False
        subnet_count = 0
        nat_gateways_exist = False
        nat_gateway_count = 0
        internet_gateway_exists = False

        try:
            # Check VPCs
            filters = []
            if vpc_name_filter:
                filters.append({"Name": "tag:Name", "Values": [vpc_name_filter]})

            response = self.ec2.describe_vpcs(Filters=filters) if filters else self.ec2.describe_vpcs()

            if response.get("Vpcs"):
                # Get the first VPC (or the named one)
                vpc = response["Vpcs"][0]
                vpc_exists = True
                vpc_id = vpc["VpcId"]
                vpc_cidr = vpc["CidrBlock"]
                logger.info(f"Found existing VPC: {vpc_id} ({vpc_cidr})")

                # Check subnets in this VPC
                subnet_response = self.ec2.describe_subnets(
                    Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
                )
                if subnet_response.get("Subnets"):
                    subnets_exist = True
                    subnet_count = len(subnet_response["Subnets"])
                    logger.info(f"Found {subnet_count} subnets in VPC {vpc_id}")

                # Check NAT Gateways
                nat_response = self.ec2.describe_nat_gateways(
                    Filters=[
                        {"Name": "vpc-id", "Values": [vpc_id]},
                        {"Name": "state", "Values": ["available"]}
                    ]
                )
                if nat_response.get("NatGateways"):
                    nat_gateways_exist = True
                    nat_gateway_count = len(nat_response["NatGateways"])
                    logger.info(f"Found {nat_gateway_count} NAT Gateways in VPC {vpc_id}")

                # Check Internet Gateway
                igw_response = self.ec2.describe_internet_gateways(
                    Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
                )
                if igw_response.get("InternetGateways"):
                    internet_gateway_exists = True
                    logger.info(f"Found Internet Gateway in VPC {vpc_id}")

        except ClientError as e:
            logger.warning(f"Error checking VPC resources: {e}")

        return VPCResourcesStatus(
            vpc_exists=vpc_exists,
            vpc_id=vpc_id,
            vpc_cidr=vpc_cidr,
            subnets_exist=subnets_exist,
            subnet_count=subnet_count,
            nat_gateways_exist=nat_gateways_exist,
            nat_gateway_count=nat_gateway_count,
            internet_gateway_exists=internet_gateway_exists,
        )

    def detect_vpc_flow_logs(self, vpc_id: str) -> VPCFlowLogsStatus:
        """
        Detect if VPC Flow Logs are enabled for a specific VPC.

        Args:
            vpc_id: The VPC ID to check

        Returns:
            VPCFlowLogsStatus with detection results
        """
        try:
            response = self.ec2.describe_flow_logs(
                Filters=[{"Name": "resource-id", "Values": [vpc_id]}]
            )

            if response.get("FlowLogs"):
                flow_log = response["FlowLogs"][0]
                logger.info(f"Found existing VPC Flow Logs for {vpc_id}: {flow_log['FlowLogId']}")
                return VPCFlowLogsStatus(
                    flow_logs_enabled=True,
                    flow_log_id=flow_log["FlowLogId"],
                    log_destination_type=flow_log.get("LogDestinationType"),
                    log_destination=flow_log.get("LogDestination") or flow_log.get("LogGroupName"),
                    traffic_type=flow_log.get("TrafficType"),
                )

            logger.info(f"No VPC Flow Logs found for {vpc_id}")
            return VPCFlowLogsStatus(flow_logs_enabled=False)

        except ClientError as e:
            logger.warning(f"Error checking VPC Flow Logs for {vpc_id}: {e}")
            return VPCFlowLogsStatus(flow_logs_enabled=False)

    def detect_s3_bucket_status(self, bucket_name: str) -> S3BucketStatus:
        """
        Detect security configuration of an S3 bucket.

        Args:
            bucket_name: The S3 bucket name (not ARN)

        Returns:
            S3BucketStatus with detection results
        """
        # Extract bucket name from ARN if needed
        if bucket_name.startswith("arn:aws:s3:::"):
            bucket_name = bucket_name.replace("arn:aws:s3:::", "")

        status = S3BucketStatus(
            bucket_name=bucket_name,
            encryption_enabled=False,
            versioning_enabled=False,
            public_access_block_enabled=False,
        )

        # Check encryption
        try:
            response = self.s3.get_bucket_encryption(Bucket=bucket_name)
            rules = response.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
            if rules:
                sse = rules[0].get("ApplyServerSideEncryptionByDefault", {})
                status.encryption_enabled = True
                status.encryption_type = sse.get("SSEAlgorithm")
                status.kms_key_id = sse.get("KMSMasterKeyID")
                logger.info(f"S3 bucket {bucket_name} has encryption enabled: {status.encryption_type}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                logger.info(f"S3 bucket {bucket_name} does not have encryption enabled")
            else:
                logger.warning(f"Error checking S3 encryption for {bucket_name}: {e}")

        # Check versioning
        try:
            response = self.s3.get_bucket_versioning(Bucket=bucket_name)
            status.versioning_enabled = response.get("Status") == "Enabled"
            logger.info(f"S3 bucket {bucket_name} versioning: {status.versioning_enabled}")
        except ClientError as e:
            logger.warning(f"Error checking S3 versioning for {bucket_name}: {e}")

        # Check public access block
        try:
            response = self.s3.get_public_access_block(Bucket=bucket_name)
            config = response.get("PublicAccessBlockConfiguration", {})
            status.block_public_acls = config.get("BlockPublicAcls", False)
            status.ignore_public_acls = config.get("IgnorePublicAcls", False)
            status.block_public_policy = config.get("BlockPublicPolicy", False)
            status.restrict_public_buckets = config.get("RestrictPublicBuckets", False)
            # All four must be True for full protection
            status.public_access_block_enabled = all([
                status.block_public_acls,
                status.ignore_public_acls,
                status.block_public_policy,
                status.restrict_public_buckets,
            ])
            logger.info(f"S3 bucket {bucket_name} public access block: {status.public_access_block_enabled}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchPublicAccessBlockConfiguration":
                logger.info(f"S3 bucket {bucket_name} has no public access block")
            else:
                logger.warning(f"Error checking S3 public access block for {bucket_name}: {e}")

        return status

    def detect_iam_password_policy(self) -> IAMPasswordPolicyStatus:
        """
        Detect the IAM account password policy.

        Returns:
            IAMPasswordPolicyStatus with detection results
        """
        try:
            response = self.iam.get_account_password_policy()
            policy = response.get("PasswordPolicy", {})

            status = IAMPasswordPolicyStatus(
                policy_exists=True,
                minimum_password_length=policy.get("MinimumPasswordLength", 0),
                require_symbols=policy.get("RequireSymbols", False),
                require_numbers=policy.get("RequireNumbers", False),
                require_uppercase=policy.get("RequireUppercaseCharacters", False),
                require_lowercase=policy.get("RequireLowercaseCharacters", False),
                allow_users_to_change=policy.get("AllowUsersToChangePassword", True),
                max_password_age=policy.get("MaxPasswordAge", 0),
                password_reuse_prevention=policy.get("PasswordReusePrevention", 0),
                hard_expiry=policy.get("HardExpiry", False),
            )

            # Check if compliant with SOC2/CIS standards
            # Minimum: 14 chars, symbols, numbers, upper, lower, rotation, reuse prevention
            status.is_compliant = all([
                status.minimum_password_length >= 14,
                status.require_symbols,
                status.require_numbers,
                status.require_uppercase,
                status.require_lowercase,
                status.max_password_age > 0 and status.max_password_age <= 90,
                status.password_reuse_prevention >= 24,
            ])

            logger.info(f"IAM password policy exists, compliant: {status.is_compliant}")
            return status

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                logger.info("No IAM password policy configured")
                return IAMPasswordPolicyStatus(policy_exists=False)
            logger.warning(f"Error checking IAM password policy: {e}")
            return IAMPasswordPolicyStatus(policy_exists=False)

    def detect_cloudwatch_log_group(self, log_group_name: str) -> CloudWatchLogGroupStatus:
        """
        Detect if a CloudWatch Log Group exists.

        Args:
            log_group_name: The log group name to check

        Returns:
            CloudWatchLogGroupStatus with detection results
        """
        try:
            response = self.logs.describe_log_groups(
                logGroupNamePrefix=log_group_name,
                limit=1
            )

            log_groups = response.get("logGroups", [])
            # Find exact match
            for lg in log_groups:
                if lg["logGroupName"] == log_group_name:
                    logger.info(f"Found existing CloudWatch Log Group: {log_group_name}")
                    return CloudWatchLogGroupStatus(
                        log_group_name=log_group_name,
                        exists=True,
                        arn=lg.get("arn"),
                        retention_days=lg.get("retentionInDays"),
                        kms_key_id=lg.get("kmsKeyId"),
                    )

            logger.info(f"CloudWatch Log Group not found: {log_group_name}")
            return CloudWatchLogGroupStatus(log_group_name=log_group_name, exists=False)

        except ClientError as e:
            logger.warning(f"Error checking CloudWatch Log Group {log_group_name}: {e}")
            return CloudWatchLogGroupStatus(log_group_name=log_group_name, exists=False)

    def detect_remediation_status(self, finding: dict) -> dict:
        """
        Detect if a finding has already been remediated.

        This is the main method used by the Remediation Agent to check
        if resources already exist before generating fix code.

        Args:
            finding: The finding dict with title, resource_type, resource_id

        Returns:
            Dict with:
                - already_remediated: bool
                - existing_resource: Optional details about existing resource
                - message: Human-readable status
        """
        title_lower = finding.get("title", "").lower()
        resource_id = finding.get("resource_id", "")
        resource_type = finding.get("resource_type", "").lower()

        result = {
            "already_remediated": False,
            "existing_resource": None,
            "message": "Resource needs remediation"
        }

        try:
            # S3 Encryption
            if "encryption" in title_lower and "s3" in resource_type:
                status = self.detect_s3_bucket_status(resource_id)
                if status.encryption_enabled:
                    result["already_remediated"] = True
                    result["existing_resource"] = {
                        "type": "s3_encryption",
                        "encryption_type": status.encryption_type,
                        "kms_key_id": status.kms_key_id,
                    }
                    result["message"] = f"S3 bucket already has {status.encryption_type} encryption enabled"

            # S3 Versioning
            elif "versioning" in title_lower and "s3" in resource_type:
                status = self.detect_s3_bucket_status(resource_id)
                if status.versioning_enabled:
                    result["already_remediated"] = True
                    result["existing_resource"] = {"type": "s3_versioning"}
                    result["message"] = "S3 bucket already has versioning enabled"

            # S3 Public Access Block
            elif "public access" in title_lower and "s3" in resource_type:
                status = self.detect_s3_bucket_status(resource_id)
                if status.public_access_block_enabled:
                    result["already_remediated"] = True
                    result["existing_resource"] = {
                        "type": "s3_public_access_block",
                        "all_blocked": True,
                    }
                    result["message"] = "S3 bucket already has public access blocked"

            # VPC Flow Logs
            elif "flow log" in title_lower:
                # Extract VPC ID from resource_id
                vpc_id = resource_id
                if not vpc_id.startswith("vpc-"):
                    # Try to extract from ARN
                    if ":vpc/" in resource_id:
                        vpc_id = resource_id.split(":vpc/")[-1]
                    elif "vpc-" in resource_id:
                        # Find vpc-xxx pattern
                        import re
                        match = re.search(r'(vpc-[a-z0-9]+)', resource_id)
                        if match:
                            vpc_id = match.group(1)

                if vpc_id.startswith("vpc-"):
                    status = self.detect_vpc_flow_logs(vpc_id)
                    if status.flow_logs_enabled:
                        result["already_remediated"] = True
                        result["existing_resource"] = {
                            "type": "vpc_flow_logs",
                            "flow_log_id": status.flow_log_id,
                            "destination_type": status.log_destination_type,
                            "destination": status.log_destination,
                        }
                        result["message"] = f"VPC Flow Logs already enabled (ID: {status.flow_log_id})"

            # IAM Password Policy
            elif "password policy" in title_lower:
                status = self.detect_iam_password_policy()
                if status.policy_exists and status.is_compliant:
                    result["already_remediated"] = True
                    result["existing_resource"] = {
                        "type": "iam_password_policy",
                        "minimum_length": status.minimum_password_length,
                        "max_age": status.max_password_age,
                    }
                    result["message"] = "IAM password policy already meets compliance requirements"

            # CloudWatch Log Groups (for various logging findings)
            elif "cloudwatch" in title_lower and "logging" in title_lower:
                log_group_name = resource_id
                status = self.detect_cloudwatch_log_group(log_group_name)
                if status.exists:
                    result["already_remediated"] = True
                    result["existing_resource"] = {
                        "type": "cloudwatch_log_group",
                        "arn": status.arn,
                        "retention_days": status.retention_days,
                    }
                    result["message"] = f"CloudWatch Log Group already exists: {log_group_name}"

        except Exception as e:
            logger.warning(f"Error detecting remediation status: {e}")
            # Don't block remediation on detection errors
            result["message"] = f"Could not verify current status: {e}"

        return result

    def get_summary(self) -> dict:
        """Get a summary of all detected resources."""
        security = self.detect_security_resources()
        vpc = self.detect_vpc_resources()

        return {
            "security": {
                "guardduty": "exists" if security.guardduty_exists else "missing",
                "security_hub": "exists" if security.security_hub_exists else "missing",
                "config": "exists" if security.config_exists else "missing",
                "cloudtrail": "exists" if security.cloudtrail_exists else "missing",
            },
            "networking": {
                "vpc": "exists" if vpc.vpc_exists else "missing",
                "subnets": f"{vpc.subnet_count} found" if vpc.subnets_exist else "missing",
                "nat_gateways": f"{vpc.nat_gateway_count} found" if vpc.nat_gateways_exist else "missing",
                "internet_gateway": "exists" if vpc.internet_gateway_exists else "missing",
            }
        }

    def scan(self) -> dict:
        """
        Unified scan method for framework gap analysis.

        Scans both security and VPC resources and returns a unified dictionary
        suitable for framework gap analysis.

        Returns:
            Dict mapping service names to their configuration details
        """
        try:
            security = self.detect_security_resources()
            vpc = self.detect_vpc_resources()

            # Return unified dict with service details
            return {
                "guardduty": {
                    "exists": security.guardduty_exists,
                    "detector_id": security.guardduty_detector_id,
                } if security.guardduty_exists else {},
                "security_hub": {
                    "exists": security.security_hub_exists,
                    "arn": security.security_hub_arn,
                } if security.security_hub_exists else {},
                "config": {
                    "exists": security.config_exists,
                    "recorder_name": security.config_recorder_name,
                } if security.config_exists else {},
                "cloudtrail": {
                    "exists": security.cloudtrail_exists,
                    "name": security.cloudtrail_name,
                    "bucket": security.cloudtrail_bucket,
                    "retention_days": 90,  # Default assumption (would need additional API call to get actual)
                } if security.cloudtrail_exists else {},
                "vpc": {
                    "exists": vpc.vpc_exists,
                    "vpc_id": vpc.vpc_id,
                    "cidr": vpc.vpc_cidr,
                } if vpc.vpc_exists else {},
                "vpc_flow_logs": {
                    # TODO: Add VPC Flow Logs detection
                    "exists": False,
                },
                "iam_password_policy": {
                    # TODO: Add IAM password policy detection
                    "exists": False,
                },
                "kms": {
                    # TODO: Add KMS key detection
                    "exists": False,
                },
            }
        except Exception as e:
            logger.error(f"Error scanning AWS resources: {e}", exc_info=True)
            return {}
