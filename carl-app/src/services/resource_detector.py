"""
AWS resource detection service.

Scans AWS environment to detect existing resources so CARL can generate
code only for what's missing.
"""
import boto3
from botocore.exceptions import ClientError
from typing import Optional
from dataclasses import dataclass

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


class ResourceDetector:
    """Detects existing AWS resources to avoid duplicate creation."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.guardduty = boto3.client("guardduty", region_name=region)
        self.securityhub = boto3.client("securityhub", region_name=region)
        self.config = boto3.client("config", region_name=region)
        self.cloudtrail = boto3.client("cloudtrail", region_name=region)
        self.ec2 = boto3.client("ec2", region_name=region)

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
