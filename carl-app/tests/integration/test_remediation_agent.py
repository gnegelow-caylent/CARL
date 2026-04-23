"""
Integration tests for Remediation Agent.

Tests the remediation workflow with mocked AWS and AI services.
"""

import pytest
from unittest.mock import patch, MagicMock
import boto3
from moto import mock_aws

from src.services.remediation_agent import (
    RemediationAgent,
    RiskLevel,
    RemediationMethod,
    classify_finding_risk,
    get_remediation_method,
)


class TestRiskClassification:
    """Tests for finding risk classification."""

    def test_classify_s3_encryption_as_low_risk(self):
        """S3 encryption findings should be LOW risk."""
        finding = {
            "title": "S3 bucket encryption not enabled",
            "description": "Server-side encryption is not configured",
            "resource_type": "AWS::S3::Bucket",
        }
        assert classify_finding_risk(finding) == RiskLevel.LOW

    def test_classify_s3_versioning_as_low_risk(self):
        """S3 versioning findings should be LOW risk."""
        finding = {
            "title": "S3 bucket versioning disabled",
            "description": "Versioning is not enabled on this bucket",
            "resource_type": "AWS::S3::Bucket",
        }
        assert classify_finding_risk(finding) == RiskLevel.LOW

    def test_classify_vpc_flow_logs_as_medium_risk(self):
        """VPC flow logs findings should be MEDIUM risk."""
        finding = {
            "title": "VPC flow logs not enabled",
            "description": "Flow logs are not configured for this VPC",
            "resource_type": "AWS::EC2::VPC",
        }
        assert classify_finding_risk(finding) == RiskLevel.MEDIUM

    def test_classify_security_group_as_high_risk(self):
        """Security group findings should be HIGH risk."""
        finding = {
            "title": "Security group allows 0.0.0.0/0 ingress",
            "description": "Unrestricted access from internet",
            "resource_type": "AWS::EC2::SecurityGroup",
        }
        assert classify_finding_risk(finding) == RiskLevel.HIGH

    def test_classify_public_access_as_high_risk(self):
        """Publicly accessible findings should be HIGH risk."""
        finding = {
            "title": "RDS instance publicly accessible",
            "description": "Database is accessible from the internet",
            "resource_type": "AWS::RDS::DBInstance",
        }
        assert classify_finding_risk(finding) == RiskLevel.HIGH


class TestRemediationMethod:
    """Tests for remediation method selection."""

    def test_low_risk_uses_direct_api(self):
        """LOW risk findings should use DIRECT_API method."""
        assert get_remediation_method(RiskLevel.LOW) == RemediationMethod.DIRECT_API

    def test_medium_risk_uses_terraform_pr(self):
        """MEDIUM risk findings should use TERRAFORM_PR method."""
        assert get_remediation_method(RiskLevel.MEDIUM) == RemediationMethod.TERRAFORM_PR

    def test_high_risk_uses_terraform_pr(self):
        """HIGH risk findings should use TERRAFORM_PR method."""
        assert get_remediation_method(RiskLevel.HIGH) == RemediationMethod.TERRAFORM_PR


class TestRemediationAgentResourceDetection:
    """Tests for remediation agent resource detection integration."""

    @mock_aws
    @patch('src.services.remediation_agent.FindingsService')
    @patch('src.services.remediation_agent.RemediationService')
    def test_skip_already_remediated_s3_encryption(self, mock_remediation, mock_findings):
        """Already-encrypted S3 buckets should be skipped."""
        # Setup S3 with encryption
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "already-encrypted-bucket"
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

        # Mock findings service to return a finding for this bucket
        mock_findings_instance = mock_findings.return_value
        mock_findings_instance.get_recent_findings.return_value = [{
            "id": "finding-123",
            "title": "S3 bucket encryption not enabled",
            "description": "Encryption is disabled",
            "resource_type": "AWS::S3::Bucket",
            "resource_id": bucket_name,
            "severity": "HIGH",
            "status": "NEW",
        }]

        # Mock remediation service
        mock_remediation_instance = mock_remediation.return_value
        mock_guidance = MagicMock()
        mock_guidance.estimated_time = "5 minutes"
        mock_remediation_instance.generate_remediation.return_value = mock_guidance

        # Create agent and get remediations
        agent = RemediationAgent(region="us-east-1")
        result = agent._get_pending_remediations()

        # Should skip the already-encrypted bucket
        assert result["success"] is True
        assert len(result["findings"]) == 0
        assert len(result.get("already_compliant", [])) == 1
        assert "already compliant" in result["message"]

    @mock_aws
    @patch('src.services.remediation_agent.FindingsService')
    @patch('src.services.remediation_agent.RemediationService')
    def test_include_findings_needing_remediation(self, mock_remediation, mock_findings):
        """Findings that need remediation should be included."""
        # Setup S3 WITHOUT encryption
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "needs-encryption-bucket"
        s3.create_bucket(Bucket=bucket_name)
        # No encryption configured

        # Mock findings service
        mock_findings_instance = mock_findings.return_value
        mock_findings_instance.get_recent_findings.return_value = [{
            "id": "finding-456",
            "title": "S3 bucket encryption not enabled",
            "description": "Encryption is disabled",
            "resource_type": "AWS::S3::Bucket",
            "resource_id": bucket_name,
            "severity": "HIGH",
            "status": "NEW",
        }]

        # Mock remediation service
        mock_remediation_instance = mock_remediation.return_value
        mock_guidance = MagicMock()
        mock_guidance.estimated_time = "5 minutes"
        mock_remediation_instance.generate_remediation.return_value = mock_guidance

        # Create agent and get remediations
        agent = RemediationAgent(region="us-east-1")
        result = agent._get_pending_remediations()

        # Should include the bucket needing encryption
        assert result["success"] is True
        assert len(result["findings"]) == 1
        assert result["findings"][0]["finding_id"] == "finding-456"
        assert result["findings"][0]["risk_level"] == "LOW"


class TestGenerateFixWithDetection:
    """Tests for generate_fix with resource detection."""

    @mock_aws
    @patch('src.services.remediation_agent.FindingsService')
    @patch('src.services.remediation_agent.RemediationService')
    def test_generate_fix_returns_already_remediated(self, mock_remediation, mock_findings):
        """generate_fix should return already_remediated when resource is compliant."""
        # Setup S3 with encryption
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "compliant-bucket"
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

        # Mock findings service
        mock_findings_instance = mock_findings.return_value
        mock_findings_instance.get_finding.return_value = {
            "id": "finding-789",
            "title": "S3 bucket encryption not enabled",
            "description": "Encryption is disabled",
            "resource_type": "AWS::S3::Bucket",
            "resource_id": bucket_name,
            "severity": "HIGH",
        }

        # Create agent and try to generate fix
        agent = RemediationAgent(region="us-east-1")
        result = agent._generate_fix("finding-789")

        # Should indicate already remediated
        assert result["success"] is False
        assert result.get("already_remediated") is True
        assert "AES256" in result["message"]


class TestExistingResourcesContext:
    """Tests for building existing resources context."""

    @mock_aws
    def test_build_context_for_vpc_flow_logs(self):
        """Context should include existing log groups for VPC."""
        # Setup
        logs = boto3.client("logs", region_name="us-east-1")
        vpc_id = "vpc-12345abc"
        log_group_name = f"/aws/vpc/flowlogs/{vpc_id}"
        logs.create_log_group(logGroupName=log_group_name)
        logs.put_retention_policy(logGroupName=log_group_name, retentionInDays=90)

        finding = {
            "title": "VPC flow logs not enabled",
            "resource_type": "AWS::EC2::VPC",
            "resource_id": vpc_id,
        }

        # Create agent and build context
        agent = RemediationAgent(region="us-east-1")
        context = agent._build_existing_resources_context(finding)

        # Context should mention the existing log group
        assert "CloudWatch Log Group EXISTS" in context
        assert log_group_name in context

    @mock_aws
    def test_build_context_for_s3_bucket(self):
        """Context should include S3 bucket status."""
        # Setup
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket_name = "test-context-bucket"
        s3.create_bucket(Bucket=bucket_name)
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Enabled"}
        )

        finding = {
            "title": "S3 bucket encryption not enabled",
            "resource_type": "AWS::S3::Bucket",
            "resource_id": bucket_name,
        }

        # Create agent and build context
        agent = RemediationAgent(region="us-east-1")
        context = agent._build_existing_resources_context(finding)

        # Context should include bucket status
        assert bucket_name in context
        assert "Versioning: enabled" in context


class TestTerraformCodeExtraction:
    """Tests for extracting Terraform code from AI responses."""

    def test_extract_from_markdown_code_block(self):
        """Should extract code from markdown HCL block."""
        agent = RemediationAgent(region="us-east-1")

        response = '''Here's the Terraform code:

```hcl
resource "aws_s3_bucket_versioning" "example" {
  bucket = "my-bucket"
  versioning_configuration {
    status = "Enabled"
  }
}
```

This will enable versioning.'''

        result = agent._extract_terraform_code(response)

        assert 'resource "aws_s3_bucket_versioning"' in result
        assert "my-bucket" in result
        assert "Here's the Terraform" not in result

    def test_extract_from_terraform_code_block(self):
        """Should extract code from markdown terraform block."""
        agent = RemediationAgent(region="us-east-1")

        response = '''```terraform
resource "aws_flow_log" "main" {
  vpc_id = "vpc-123"
}
```'''

        result = agent._extract_terraform_code(response)

        assert 'resource "aws_flow_log"' in result

    def test_extract_plain_terraform(self):
        """Should handle plain Terraform without code blocks."""
        agent = RemediationAgent(region="us-east-1")

        response = '''resource "aws_iam_account_password_policy" "strict" {
  minimum_password_length = 14
  require_symbols         = true
}'''

        result = agent._extract_terraform_code(response)

        assert 'resource "aws_iam_account_password_policy"' in result
        assert "minimum_password_length = 14" in result
