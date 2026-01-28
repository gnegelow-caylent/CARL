"""
Tests for Finding model.
"""

from datetime import datetime

import pytest

from src.models.finding import Finding, FindingSeverity, FindingSource, FindingStatus


class TestFinding:
    """Tests for Finding model."""

    def test_create_finding(self):
        """Test creating a finding."""
        finding = Finding(
            id="test-123",
            source=FindingSource.CONFIG,
            severity=FindingSeverity.HIGH,
            title="Test Finding",
            description="This is a test finding",
            resource_type="AWS::S3::Bucket",
            resource_id="my-bucket",
            account_id="123456789012",
            region="us-east-1",
            control_ids=["CC6.5", "CC6.6"],
        )

        assert finding.id == "test-123"
        assert finding.source == FindingSource.CONFIG
        assert finding.severity == FindingSeverity.HIGH
        assert finding.status == FindingStatus.NEW
        assert "CC6.5" in finding.control_ids

    def test_to_dynamodb_item(self):
        """Test converting finding to DynamoDB item."""
        finding = Finding(
            id="test-123",
            source=FindingSource.SECURITY_HUB,
            severity=FindingSeverity.CRITICAL,
            title="Critical Finding",
            description="Description",
            resource_type="AWS::EC2::Instance",
            resource_id="i-1234567890abcdef0",
            account_id="123456789012",
            region="us-east-1",
        )

        item = finding.to_dynamodb_item()

        assert item["pk"] == "ACCOUNT#123456789012#FINDING#test-123"
        assert item["finding_id"] == "test-123"
        assert item["source"] == "SECURITY_HUB"
        assert item["severity"] == "CRITICAL"

    def test_from_dynamodb_item(self):
        """Test creating finding from DynamoDB item."""
        item = {
            "pk": "ACCOUNT#123456789012#FINDING#test-456",
            "sk": "SOURCE#GUARDDUTY#TIMESTAMP#1234567890",
            "finding_id": "test-456",
            "source": "GUARDDUTY",
            "severity": "MEDIUM",
            "title": "GuardDuty Finding",
            "description": "Suspicious activity",
            "resource_type": "AWS::EC2::Instance",
            "resource_id": "i-abcdef",
            "account_id": "123456789012",
            "region": "us-east-1",
            "control_ids": ["CC7.2"],
            "status": "IN_PROGRESS",
            "created_at": "2024-01-01T00:00:00",
        }

        finding = Finding.from_dynamodb_item(item)

        assert finding.id == "test-456"
        assert finding.source == FindingSource.GUARDDUTY
        assert finding.severity == FindingSeverity.MEDIUM
        assert finding.status == FindingStatus.IN_PROGRESS

    def test_to_dict(self):
        """Test converting finding to dictionary."""
        finding = Finding(
            id="test-789",
            source=FindingSource.INSPECTOR,
            severity=FindingSeverity.LOW,
            title="Vulnerability",
            description="CVE-2024-1234",
            resource_type="AWS::Lambda::Function",
            resource_id="my-function",
            account_id="123456789012",
            region="us-east-1",
        )

        result = finding.to_dict()

        assert result["id"] == "test-789"
        assert result["source"] == "INSPECTOR"
        assert result["severity"] == "LOW"
        assert "created_at" in result
