"""
Integration tests for ResourceDetector.

Tests resource detection capabilities with mocked AWS services.
"""

import pytest
from unittest.mock import patch, MagicMock
import boto3
from moto import mock_aws

from src.services.resource_detector import (
    ResourceDetector,
    VPCFlowLogsStatus,
    S3BucketStatus,
    IAMPasswordPolicyStatus,
    CloudWatchLogGroupStatus,
)


@pytest.fixture
def resource_detector():
    """Create a ResourceDetector instance."""
    return ResourceDetector(region="us-east-1")


class TestVPCFlowLogsDetection:
    """Tests for VPC Flow Logs detection."""

    @mock_aws
    def test_detect_flow_logs_enabled(self):
        """Test detecting when VPC flow logs are enabled."""
        # Setup
        ec2 = boto3.client("ec2", region_name="us-east-1")
        logs = boto3.client("logs", region_name="us-east-1")

        # Create VPC
        vpc_response = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc_response["Vpc"]["VpcId"]

        # Create log group
        log_group_name = f"/aws/vpc/flowlogs/{vpc_id}"
        logs.create_log_group(logGroupName=log_group_name)

        # Create flow log
        ec2.create_flow_logs(
            ResourceIds=[vpc_id],
            ResourceType="VPC",
            TrafficType="ALL",
            LogDestinationType="cloud-watch-logs",
            LogGroupName=log_group_name,
        )

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_vpc_flow_logs(vpc_id)

        assert result.flow_logs_enabled is True
        assert result.flow_log_id is not None
        assert result.traffic_type == "ALL"

    @mock_aws
    def test_detect_flow_logs_disabled(self):
        """Test detecting when VPC flow logs are NOT enabled."""
        # Setup
        ec2 = boto3.client("ec2", region_name="us-east-1")

        # Create VPC without flow logs
        vpc_response = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc_response["Vpc"]["VpcId"]

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_vpc_flow_logs(vpc_id)

        assert result.flow_logs_enabled is False
        assert result.flow_log_id is None


class TestS3BucketDetection:
    """Tests for S3 bucket security detection."""

    @mock_aws
    def test_detect_s3_encryption_enabled(self):
        """Test detecting S3 bucket with encryption enabled."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket-encrypted"

        s3.create_bucket(Bucket=bucket_name)
        s3.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }]
            }
        )

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_s3_bucket_status(bucket_name)

        assert result.encryption_enabled is True
        assert result.encryption_type == "AES256"

    @mock_aws
    def test_detect_s3_encryption_disabled(self):
        """Test detecting S3 bucket without encryption."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket-no-encryption"

        s3.create_bucket(Bucket=bucket_name)

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_s3_bucket_status(bucket_name)

        assert result.encryption_enabled is False

    @mock_aws
    def test_detect_s3_versioning_enabled(self):
        """Test detecting S3 bucket with versioning enabled."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket-versioned"

        s3.create_bucket(Bucket=bucket_name)
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Enabled"}
        )

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_s3_bucket_status(bucket_name)

        assert result.versioning_enabled is True

    @mock_aws
    def test_detect_s3_public_access_block_enabled(self):
        """Test detecting S3 bucket with public access block."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket-blocked"

        s3.create_bucket(Bucket=bucket_name)
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True
            }
        )

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_s3_bucket_status(bucket_name)

        assert result.public_access_block_enabled is True
        assert result.block_public_acls is True
        assert result.ignore_public_acls is True
        assert result.block_public_policy is True
        assert result.restrict_public_buckets is True

    @mock_aws
    def test_detect_s3_from_arn(self):
        """Test detecting S3 bucket from ARN."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-bucket-arn"
        bucket_arn = f"arn:aws:s3:::{bucket_name}"

        s3.create_bucket(Bucket=bucket_name)
        s3.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }]
            }
        )

        # Test - pass ARN instead of bucket name
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_s3_bucket_status(bucket_arn)

        assert result.bucket_name == bucket_name
        assert result.encryption_enabled is True


class TestIAMPasswordPolicyDetection:
    """Tests for IAM password policy detection."""

    @mock_aws
    def test_detect_password_policy_compliant(self):
        """Test detecting a compliant IAM password policy."""
        # Setup
        iam = boto3.client("iam", region_name="us-east-1")

        iam.update_account_password_policy(
            MinimumPasswordLength=14,
            RequireSymbols=True,
            RequireNumbers=True,
            RequireUppercaseCharacters=True,
            RequireLowercaseCharacters=True,
            AllowUsersToChangePassword=True,
            MaxPasswordAge=90,
            PasswordReusePrevention=24,
        )

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_iam_password_policy()

        assert result.policy_exists is True
        assert result.minimum_password_length >= 14
        assert result.require_symbols is True
        assert result.require_numbers is True
        assert result.is_compliant is True

    @mock_aws
    def test_detect_password_policy_non_compliant(self):
        """Test detecting a non-compliant IAM password policy."""
        # Setup
        iam = boto3.client("iam", region_name="us-east-1")

        # Weak policy
        iam.update_account_password_policy(
            MinimumPasswordLength=8,
            RequireSymbols=False,
            RequireNumbers=True,
        )

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_iam_password_policy()

        assert result.policy_exists is True
        assert result.minimum_password_length == 8
        assert result.is_compliant is False

    @mock_aws
    def test_detect_no_password_policy(self):
        """Test detecting when no password policy is configured."""
        # No setup - default account has no policy

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_iam_password_policy()

        assert result.policy_exists is False
        assert result.is_compliant is False


class TestCloudWatchLogGroupDetection:
    """Tests for CloudWatch Log Group detection."""

    @mock_aws
    def test_detect_log_group_exists(self):
        """Test detecting an existing CloudWatch Log Group."""
        # Setup
        logs = boto3.client("logs", region_name="us-east-1")
        log_group_name = "/aws/vpc/flowlogs/vpc-test123"

        logs.create_log_group(logGroupName=log_group_name)
        logs.put_retention_policy(
            logGroupName=log_group_name,
            retentionInDays=90
        )

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_cloudwatch_log_group(log_group_name)

        assert result.exists is True
        assert result.log_group_name == log_group_name
        assert result.retention_days == 90

    @mock_aws
    def test_detect_log_group_not_exists(self):
        """Test detecting a non-existent CloudWatch Log Group."""
        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_cloudwatch_log_group("/nonexistent/log/group")

        assert result.exists is False


class TestRemediationStatusDetection:
    """Tests for detect_remediation_status (main integration point)."""

    @mock_aws
    def test_detect_s3_encryption_already_remediated(self):
        """Test detecting that S3 encryption is already enabled."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-already-encrypted"

        s3.create_bucket(Bucket=bucket_name)
        s3.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256"
                    }
                }]
            }
        )

        # Create finding
        finding = {
            "id": "finding-123",
            "title": "S3 bucket encryption not enabled",
            "resource_type": "AWS::S3::Bucket",
            "resource_id": bucket_name,
        }

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_remediation_status(finding)

        assert result["already_remediated"] is True
        assert "AES256" in result["message"]
        assert result["existing_resource"]["type"] == "s3_encryption"

    @mock_aws
    def test_detect_s3_encryption_needs_remediation(self):
        """Test detecting that S3 encryption is needed."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-needs-encryption"

        s3.create_bucket(Bucket=bucket_name)
        # No encryption configured

        # Create finding
        finding = {
            "id": "finding-456",
            "title": "S3 bucket encryption not enabled",
            "resource_type": "AWS::S3::Bucket",
            "resource_id": bucket_name,
        }

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_remediation_status(finding)

        assert result["already_remediated"] is False
        assert result["message"] == "Resource needs remediation"

    @mock_aws
    def test_detect_vpc_flow_logs_already_enabled(self):
        """Test detecting that VPC flow logs are already enabled."""
        # Setup
        ec2 = boto3.client("ec2", region_name="us-east-1")
        logs = boto3.client("logs", region_name="us-east-1")

        vpc_response = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc_response["Vpc"]["VpcId"]

        log_group_name = f"/aws/vpc/flowlogs/{vpc_id}"
        logs.create_log_group(logGroupName=log_group_name)

        ec2.create_flow_logs(
            ResourceIds=[vpc_id],
            ResourceType="VPC",
            TrafficType="ALL",
            LogDestinationType="cloud-watch-logs",
            LogGroupName=log_group_name,
        )

        # Create finding
        finding = {
            "id": "finding-789",
            "title": "VPC flow logs not enabled",
            "resource_type": "AWS::EC2::VPC",
            "resource_id": vpc_id,
        }

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_remediation_status(finding)

        assert result["already_remediated"] is True
        assert "Flow Logs already enabled" in result["message"]

    @mock_aws
    def test_detect_iam_password_policy_already_compliant(self):
        """Test detecting that IAM password policy is already compliant."""
        # Setup
        iam = boto3.client("iam", region_name="us-east-1")

        iam.update_account_password_policy(
            MinimumPasswordLength=14,
            RequireSymbols=True,
            RequireNumbers=True,
            RequireUppercaseCharacters=True,
            RequireLowercaseCharacters=True,
            MaxPasswordAge=90,
            PasswordReusePrevention=24,
        )

        # Create finding
        finding = {
            "id": "finding-policy",
            "title": "IAM password policy does not meet requirements",
            "resource_type": "AWS::IAM::AccountPasswordPolicy",
            "resource_id": "account-password-policy",
        }

        # Test
        detector = ResourceDetector(region="us-east-1")
        result = detector.detect_remediation_status(finding)

        assert result["already_remediated"] is True
        assert "compliance requirements" in result["message"]
