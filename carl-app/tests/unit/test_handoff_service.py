"""
Tests for HandoffService - Multi-Agent Context Storage

These tests verify the handoff service correctly stores and retrieves
context for agent-to-agent handoffs.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.handoff_service import HandoffContext, HandoffService


class TestHandoffContext:
    """Tests for HandoffContext dataclass."""

    def test_create_handoff_context(self):
        """Test creating a HandoffContext."""
        context = HandoffContext(
            handoff_id="abc12345",
            source_agent="ask",
            target_agent="remediate",
            original_question="Fix my S3 encryption",
            context={"finding_count": 3, "finding_types": ["unencrypted S3"]},
            channel_id="C123456",
            thread_ts="1234567890.123456",
            user_id="U123456",
            created_at="2024-01-01T00:00:00Z",
            expires_at="2024-01-01T01:00:00Z",
            status="pending",
            session_id="session-123",
            reason="Found 3 security issues",
            confidence=0.85
        )

        assert context.handoff_id == "abc12345"
        assert context.source_agent == "ask"
        assert context.target_agent == "remediate"
        assert context.original_question == "Fix my S3 encryption"
        assert context.context["finding_count"] == 3
        assert context.status == "pending"
        assert context.confidence == 0.85

    def test_to_dynamodb_item(self):
        """Test converting HandoffContext to DynamoDB item."""
        context = HandoffContext(
            handoff_id="abc12345",
            source_agent="ask",
            target_agent="architect",
            original_question="Design my VPC",
            context={"scan_summary": "Scanned 50 resources"},
            channel_id="C123456",
            thread_ts=None,
            user_id="U123456",
            created_at="2024-01-01T00:00:00Z",
            expires_at="2024-01-01T01:00:00Z",
            status="pending",
            session_id="session-456",
            reason="Architecture question detected",
            confidence=0.9
        )

        item = context.to_dynamodb_item()

        assert item["pk"]["S"] == "HANDOFF#abc12345"
        assert item["sk"]["S"] == "CONTEXT#ask#architect"
        assert item["handoff_id"]["S"] == "abc12345"
        assert item["source_agent"]["S"] == "ask"
        assert item["target_agent"]["S"] == "architect"
        assert item["status"]["S"] == "pending"
        assert item["confidence"]["N"] == "0.9"
        assert "thread_ts" not in item  # None values should not be included
        assert "ttl" in item

    def test_from_dynamodb_item(self):
        """Test creating HandoffContext from DynamoDB item."""
        item = {
            "pk": {"S": "HANDOFF#xyz98765"},
            "sk": {"S": "CONTEXT#ask#remediate"},
            "handoff_id": {"S": "xyz98765"},
            "source_agent": {"S": "ask"},
            "target_agent": {"S": "remediate"},
            "original_question": {"S": "Enable S3 encryption"},
            "context": {"S": '{"finding_count": 5}'},
            "channel_id": {"S": "C789"},
            "thread_ts": {"S": "1234.5678"},
            "user_id": {"S": "U456"},
            "created_at": {"S": "2024-01-01T12:00:00Z"},
            "expires_at": {"S": "2024-01-01T13:00:00Z"},
            "status": {"S": "accepted"},
            "session_id": {"S": "sess-789"},
            "reason": {"S": "Security issues found"},
            "confidence": {"N": "0.95"}
        }

        context = HandoffContext.from_dynamodb_item(item)

        assert context.handoff_id == "xyz98765"
        assert context.source_agent == "ask"
        assert context.target_agent == "remediate"
        assert context.status == "accepted"
        assert context.confidence == 0.95
        assert context.context["finding_count"] == 5
        assert context.thread_ts == "1234.5678"


class TestHandoffService:
    """Tests for HandoffService."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Create a mock DynamoDB client."""
        with patch('boto3.client') as mock_client:
            mock_db = MagicMock()
            mock_client.return_value = mock_db
            # Table exists by default
            mock_db.describe_table.return_value = {"Table": {"TableName": "carl-dev-handoffs"}}
            yield mock_db

    def test_create_handoff_success(self, mock_dynamodb):
        """Test creating a handoff successfully."""
        mock_dynamodb.put_item.return_value = {}

        service = HandoffService(table_name="carl-dev-handoffs")
        handoff = service.create_handoff(
            source_agent="ask",
            target_agent="remediate",
            original_question="Fix security issues",
            context={"findings": ["S3 encryption missing"]},
            channel_id="C123",
            user_id="U456",
            thread_ts=None,
            session_id="session-abc",
            reason="Found security issues",
            confidence=0.8
        )

        assert handoff is not None
        assert handoff.source_agent == "ask"
        assert handoff.target_agent == "remediate"
        assert handoff.status == "pending"
        assert len(handoff.handoff_id) == 8  # Short UUID
        mock_dynamodb.put_item.assert_called_once()

    def test_create_handoff_table_not_exists(self, mock_dynamodb):
        """Test creating a handoff when table doesn't exist."""
        from botocore.exceptions import ClientError
        mock_dynamodb.describe_table.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}},
            "DescribeTable"
        )

        service = HandoffService(table_name="carl-dev-handoffs")
        handoff = service.create_handoff(
            source_agent="ask",
            target_agent="architect",
            original_question="Design VPC",
            context={},
            channel_id="C123",
            user_id="U456"
        )

        assert handoff is None
        mock_dynamodb.put_item.assert_not_called()

    def test_get_handoff_success(self, mock_dynamodb):
        """Test getting a handoff by ID."""
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        mock_dynamodb.query.return_value = {
            "Items": [{
                "pk": {"S": "HANDOFF#test123"},
                "sk": {"S": "CONTEXT#ask#remediate"},
                "handoff_id": {"S": "test123"},
                "source_agent": {"S": "ask"},
                "target_agent": {"S": "remediate"},
                "original_question": {"S": "Fix issues"},
                "context": {"S": "{}"},
                "channel_id": {"S": "C123"},
                "user_id": {"S": "U456"},
                "created_at": {"S": "2024-01-01T00:00:00Z"},
                "expires_at": {"S": future_time},
                "status": {"S": "pending"},
                "reason": {"S": "Test"},
                "confidence": {"N": "0.8"}
            }]
        }

        service = HandoffService(table_name="carl-dev-handoffs")
        handoff = service.get_handoff("test123")

        assert handoff is not None
        assert handoff.handoff_id == "test123"
        assert handoff.status == "pending"

    def test_get_handoff_not_found(self, mock_dynamodb):
        """Test getting a handoff that doesn't exist."""
        mock_dynamodb.query.return_value = {"Items": []}

        service = HandoffService(table_name="carl-dev-handoffs")
        handoff = service.get_handoff("nonexistent")

        assert handoff is None

    def test_get_handoff_expired(self, mock_dynamodb):
        """Test getting an expired handoff returns None."""
        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        mock_dynamodb.query.return_value = {
            "Items": [{
                "pk": {"S": "HANDOFF#expired123"},
                "sk": {"S": "CONTEXT#ask#remediate"},
                "handoff_id": {"S": "expired123"},
                "source_agent": {"S": "ask"},
                "target_agent": {"S": "remediate"},
                "original_question": {"S": "Old request"},
                "context": {"S": "{}"},
                "channel_id": {"S": "C123"},
                "user_id": {"S": "U456"},
                "created_at": {"S": "2024-01-01T00:00:00Z"},
                "expires_at": {"S": past_time},  # Already expired
                "status": {"S": "pending"},
                "reason": {"S": ""},
                "confidence": {"N": "0.8"}
            }]
        }

        service = HandoffService(table_name="carl-dev-handoffs")
        handoff = service.get_handoff("expired123")

        assert handoff is None

    def test_accept_handoff(self, mock_dynamodb):
        """Test accepting a handoff."""
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        mock_dynamodb.query.return_value = {
            "Items": [{
                "pk": {"S": "HANDOFF#accept123"},
                "sk": {"S": "CONTEXT#ask#remediate"},
                "handoff_id": {"S": "accept123"},
                "source_agent": {"S": "ask"},
                "target_agent": {"S": "remediate"},
                "original_question": {"S": "Fix security"},
                "context": {"S": '{"finding_count": 3}'},
                "channel_id": {"S": "C123"},
                "user_id": {"S": "U456"},
                "created_at": {"S": "2024-01-01T00:00:00Z"},
                "expires_at": {"S": future_time},
                "status": {"S": "pending"},
                "reason": {"S": "Issues found"},
                "confidence": {"N": "0.85"}
            }]
        }
        mock_dynamodb.update_item.return_value = {}

        service = HandoffService(table_name="carl-dev-handoffs")
        handoff = service.accept_handoff("accept123")

        assert handoff is not None
        assert handoff.status == "accepted"
        mock_dynamodb.update_item.assert_called_once()

    def test_accept_handoff_already_accepted(self, mock_dynamodb):
        """Test accepting a handoff that's already accepted."""
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        mock_dynamodb.query.return_value = {
            "Items": [{
                "pk": {"S": "HANDOFF#already"},
                "sk": {"S": "CONTEXT#ask#remediate"},
                "handoff_id": {"S": "already"},
                "source_agent": {"S": "ask"},
                "target_agent": {"S": "remediate"},
                "original_question": {"S": "Fix security"},
                "context": {"S": "{}"},
                "channel_id": {"S": "C123"},
                "user_id": {"S": "U456"},
                "created_at": {"S": "2024-01-01T00:00:00Z"},
                "expires_at": {"S": future_time},
                "status": {"S": "accepted"},  # Already accepted
                "reason": {"S": ""},
                "confidence": {"N": "0.8"}
            }]
        }

        service = HandoffService(table_name="carl-dev-handoffs")
        handoff = service.accept_handoff("already")

        assert handoff is None
        mock_dynamodb.update_item.assert_not_called()

    def test_decline_handoff(self, mock_dynamodb):
        """Test declining a handoff."""
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        mock_dynamodb.query.return_value = {
            "Items": [{
                "pk": {"S": "HANDOFF#decline123"},
                "sk": {"S": "CONTEXT#ask#architect"},
                "handoff_id": {"S": "decline123"},
                "source_agent": {"S": "ask"},
                "target_agent": {"S": "architect"},
                "original_question": {"S": "Design VPC"},
                "context": {"S": "{}"},
                "channel_id": {"S": "C123"},
                "user_id": {"S": "U456"},
                "created_at": {"S": "2024-01-01T00:00:00Z"},
                "expires_at": {"S": future_time},
                "status": {"S": "pending"},
                "reason": {"S": ""},
                "confidence": {"N": "0.9"}
            }]
        }
        mock_dynamodb.update_item.return_value = {}

        service = HandoffService(table_name="carl-dev-handoffs")
        result = service.decline_handoff("decline123")

        assert result is True
        mock_dynamodb.update_item.assert_called()


class TestHandoffServiceIntegration:
    """Integration-style tests for handoff workflows."""

    @pytest.fixture
    def mock_dynamodb(self):
        """Create a mock DynamoDB client."""
        with patch('boto3.client') as mock_client:
            mock_db = MagicMock()
            mock_client.return_value = mock_db
            mock_db.describe_table.return_value = {"Table": {"TableName": "carl-dev-handoffs"}}
            yield mock_db

    def test_full_handoff_workflow_remediate(self, mock_dynamodb):
        """Test complete handoff workflow to Remediate agent."""
        mock_dynamodb.put_item.return_value = {}

        service = HandoffService(table_name="carl-dev-handoffs")

        # Step 1: Create handoff from Ask to Remediate
        handoff = service.create_handoff(
            source_agent="ask",
            target_agent="remediate",
            original_question="My S3 buckets are not encrypted",
            context={
                "finding_count": 3,
                "finding_types": ["unencrypted S3 bucket", "public access not blocked"],
                "scan_results_summary": {"s3": 5, "iam": 3}
            },
            channel_id="C12345",
            user_id="U67890",
            session_id="session-workflow-test",
            reason="I found 3 security issues that can be remediated",
            confidence=0.88
        )

        assert handoff is not None
        assert handoff.target_agent == "remediate"
        assert handoff.context["finding_count"] == 3
        assert handoff.confidence == 0.88

    def test_full_handoff_workflow_architect(self, mock_dynamodb):
        """Test complete handoff workflow to Architect agent."""
        mock_dynamodb.put_item.return_value = {}

        service = HandoffService(table_name="carl-dev-handoffs")

        # Step 1: Create handoff from Ask to Architect
        handoff = service.create_handoff(
            source_agent="ask",
            target_agent="architect",
            original_question="How should I design my VPC for multi-tier application?",
            context={
                "original_question": "How should I design my VPC for multi-tier application?",
                "scan_summary": "Scanned 15 VPCs, 42 security groups, 8 subnets"
            },
            channel_id="C12345",
            user_id="U67890",
            session_id="session-arch-test",
            reason="Your question suggests you're looking for architecture recommendations",
            confidence=0.92
        )

        assert handoff is not None
        assert handoff.target_agent == "architect"
        assert "VPC" in handoff.context["original_question"]
        assert handoff.confidence == 0.92
