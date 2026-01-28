"""
Security Services Enablement Module.

Detects and enables critical AWS security services:
- AWS Security Hub
- AWS Config
"""

import boto3
from typing import Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class SecurityServicesEnabler:
    """Service for detecting and enabling AWS security services."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.securityhub = boto3.client("securityhub", region_name=region)
        self.config = boto3.client("config", region_name=region)
        self.iam = boto3.client("iam")
        self.s3 = boto3.client("s3")
        self.sts = boto3.client("sts")

    def get_account_id(self) -> str:
        """Get AWS account ID."""
        try:
            return self.sts.get_caller_identity()["Account"]
        except Exception as e:
            logger.error(f"Error getting account ID: {e}")
            return "unknown"

    def check_security_hub_status(self) -> Dict[str, Any]:
        """Check if Security Hub is enabled."""
        try:
            hub = self.securityhub.describe_hub()
            return {
                "enabled": True,
                "hub_arn": hub.get("HubArn"),
                "subscribed_at": hub.get("SubscribedAt"),
                "auto_enable_controls": hub.get("AutoEnableControls", False)
            }
        except self.securityhub.exceptions.InvalidAccessException:
            return {"enabled": False, "reason": "Not subscribed"}
        except Exception as e:
            logger.error(f"Error checking Security Hub: {e}")
            return {"enabled": False, "error": str(e)}

    def check_config_status(self) -> Dict[str, Any]:
        """Check if AWS Config is enabled."""
        try:
            recorders = self.config.describe_configuration_recorders()
            if not recorders.get("ConfigurationRecorders"):
                return {"enabled": False, "reason": "No configuration recorders"}

            recorder_status = self.config.describe_configuration_recorder_status()
            if not recorder_status.get("ConfigurationRecordersStatus"):
                return {"enabled": False, "reason": "Recorder exists but not active"}

            status = recorder_status["ConfigurationRecordersStatus"][0]
            return {
                "enabled": status.get("recording", False),
                "recorder_name": status.get("name"),
                "last_status": status.get("lastStatus"),
                "last_start_time": status.get("lastStartTime")
            }
        except Exception as e:
            logger.error(f"Error checking Config: {e}")
            return {"enabled": False, "error": str(e)}

    def enable_security_hub(self, enable_standards: bool = True) -> Dict[str, Any]:
        """
        Enable AWS Security Hub.

        Args:
            enable_standards: Whether to enable default security standards (CIS, PCI-DSS, AWS Foundational Security)

        Returns:
            Result dictionary with success status and details
        """
        try:
            # Enable Security Hub
            response = self.securityhub.enable_security_hub(
                EnableDefaultStandards=enable_standards
            )

            logger.info(f"Security Hub enabled successfully: {response.get('HubArn')}")

            return {
                "success": True,
                "hub_arn": response.get("HubArn"),
                "standards_enabled": enable_standards,
                "message": "Security Hub enabled successfully"
            }

        except self.securityhub.exceptions.ResourceConflictException:
            logger.info("Security Hub already enabled")
            return {
                "success": True,
                "message": "Security Hub already enabled",
                "already_enabled": True
            }

        except Exception as e:
            logger.error(f"Failed to enable Security Hub: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to enable Security Hub: {str(e)}"
            }

    def enable_config(self, create_resources: bool = True) -> Dict[str, Any]:
        """
        Enable AWS Config.

        Args:
            create_resources: Whether to create required S3 bucket and IAM role

        Returns:
            Result dictionary with success status and details
        """
        try:
            account_id = self.get_account_id()

            # Create S3 bucket for Config if needed
            bucket_name = f"aws-config-{account_id}-{self.region}"
            s3_bucket_created = False

            if create_resources:
                try:
                    # Check if bucket exists
                    self.s3.head_bucket(Bucket=bucket_name)
                    logger.info(f"Config bucket already exists: {bucket_name}")
                except:
                    # Create bucket
                    if self.region == "us-east-1":
                        self.s3.create_bucket(Bucket=bucket_name)
                    else:
                        self.s3.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={"LocationConstraint": self.region}
                        )

                    # Enable versioning
                    self.s3.put_bucket_versioning(
                        Bucket=bucket_name,
                        VersioningConfiguration={"Status": "Enabled"}
                    )

                    # Add bucket policy for Config
                    bucket_policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "AWSConfigBucketPermissionsCheck",
                                "Effect": "Allow",
                                "Principal": {"Service": "config.amazonaws.com"},
                                "Action": "s3:GetBucketAcl",
                                "Resource": f"arn:aws:s3:::{bucket_name}"
                            },
                            {
                                "Sid": "AWSConfigBucketExistenceCheck",
                                "Effect": "Allow",
                                "Principal": {"Service": "config.amazonaws.com"},
                                "Action": "s3:ListBucket",
                                "Resource": f"arn:aws:s3:::{bucket_name}"
                            },
                            {
                                "Sid": "AWSConfigBucketPut",
                                "Effect": "Allow",
                                "Principal": {"Service": "config.amazonaws.com"},
                                "Action": "s3:PutObject",
                                "Resource": f"arn:aws:s3:::{bucket_name}/*",
                                "Condition": {
                                    "StringEquals": {
                                        "s3:x-amz-acl": "bucket-owner-full-control"
                                    }
                                }
                            }
                        ]
                    }

                    import json
                    self.s3.put_bucket_policy(
                        Bucket=bucket_name,
                        Policy=json.dumps(bucket_policy)
                    )

                    s3_bucket_created = True
                    logger.info(f"Created Config bucket: {bucket_name}")

            # Create IAM role for Config if needed
            role_name = "AWSConfigRole"
            role_arn = None

            if create_resources:
                try:
                    # Check if role exists
                    role = self.iam.get_role(RoleName=role_name)
                    role_arn = role["Role"]["Arn"]
                    logger.info(f"Config role already exists: {role_arn}")
                except self.iam.exceptions.NoSuchEntityException:
                    # Create role
                    import json
                    assume_role_policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"Service": "config.amazonaws.com"},
                                "Action": "sts:AssumeRole"
                            }
                        ]
                    }

                    role_response = self.iam.create_role(
                        RoleName=role_name,
                        AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                        Description="Role for AWS Config service"
                    )
                    role_arn = role_response["Role"]["Arn"]

                    # Attach AWS managed policy for Config
                    self.iam.attach_role_policy(
                        RoleName=role_name,
                        PolicyArn="arn:aws:iam::aws:policy/service-role/ConfigRole"
                    )

                    logger.info(f"Created Config role: {role_arn}")

                    # Wait a bit for role propagation
                    import time
                    time.sleep(10)

            # Create configuration recorder
            recorder_name = "default"
            try:
                self.config.put_configuration_recorder(
                    ConfigurationRecorder={
                        "name": recorder_name,
                        "roleARN": role_arn or f"arn:aws:iam::{account_id}:role/AWSConfigRole",
                        "recordingGroup": {
                            "allSupported": True,
                            "includeGlobalResources": True
                        }
                    }
                )
                logger.info("Created configuration recorder")
            except Exception as e:
                logger.warning(f"Configuration recorder may already exist: {e}")

            # Create delivery channel
            try:
                self.config.put_delivery_channel(
                    DeliveryChannel={
                        "name": "default",
                        "s3BucketName": bucket_name,
                        "configSnapshotDeliveryProperties": {
                            "deliveryFrequency": "TwentyFour_Hours"
                        }
                    }
                )
                logger.info("Created delivery channel")
            except Exception as e:
                logger.warning(f"Delivery channel may already exist: {e}")

            # Start configuration recorder
            self.config.start_configuration_recorder(
                ConfigurationRecorderName=recorder_name
            )

            logger.info("AWS Config enabled and started successfully")

            return {
                "success": True,
                "recorder_name": recorder_name,
                "bucket_name": bucket_name,
                "bucket_created": s3_bucket_created,
                "role_arn": role_arn,
                "message": "AWS Config enabled successfully"
            }

        except Exception as e:
            logger.error(f"Failed to enable AWS Config: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to enable AWS Config: {str(e)}"
            }

    def check_and_enable_all(self) -> Dict[str, Any]:
        """
        Check status of Security Hub and Config, and enable if not already enabled.

        Returns:
            Dictionary with status and results for both services
        """
        results = {
            "security_hub": {},
            "config": {}
        }

        # Check and enable Security Hub
        sh_status = self.check_security_hub_status()
        if sh_status.get("enabled"):
            results["security_hub"] = {
                "status": "already_enabled",
                "details": sh_status
            }
            logger.info("Security Hub is already enabled")
        else:
            logger.info("Security Hub not enabled, enabling now...")
            enable_result = self.enable_security_hub()
            results["security_hub"] = {
                "status": "enabled" if enable_result["success"] else "failed",
                "details": enable_result
            }

        # Check and enable Config
        config_status = self.check_config_status()
        if config_status.get("enabled"):
            results["config"] = {
                "status": "already_enabled",
                "details": config_status
            }
            logger.info("AWS Config is already enabled")
        else:
            logger.info("AWS Config not enabled, enabling now...")
            enable_result = self.enable_config()
            results["config"] = {
                "status": "enabled" if enable_result["success"] else "failed",
                "details": enable_result
            }

        return results
