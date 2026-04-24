"""
Integration Tests for Multi-Agent Handoff Handlers

These tests verify the Slack handlers for accepting and declining handoffs
work correctly with the HandoffService.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestHandoffAcceptHandler:
    """Tests for handle_handoff_accept handler."""

    @pytest.fixture
    def mock_services(self):
        """Set up mocked services."""
        with patch('handlers.slack_router.get_slack_service') as mock_slack_fn, \
             patch('handlers.slack_router.invoke_agentcore_architect') as mock_architect, \
             patch('handlers.slack_router.invoke_agentcore_remediate') as mock_remediate, \
             patch('handlers.slack_router.format_markdown_to_blocks') as mock_format:

            mock_slack = MagicMock()
            mock_slack_fn.return_value = mock_slack

            # Default successful responses
            mock_architect.return_value = {
                "success": True,
                "response": "Here are my architecture recommendations...",
                "session_id": "session-123"
            }
            mock_remediate.return_value = {
                "success": True,
                "response": "Here are the available remediations...",
                "session_id": "session-123"
            }
            mock_format.return_value = [[{"type": "section", "text": {"type": "mrkdwn", "text": "Response"}}]]

            yield {
                "slack": mock_slack,
                "slack_fn": mock_slack_fn,
                "architect": mock_architect,
                "remediate": mock_remediate,
                "format": mock_format
            }

    @pytest.fixture
    def mock_handoff_service(self):
        """Set up mocked HandoffService."""
        with patch('services.handoff_service.HandoffService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service
            yield mock_service

    def test_accept_handoff_to_architect(self, mock_services, mock_handoff_service):
        """Test accepting handoff to Architect agent."""
        from services.handoff_service import HandoffContext

        # Set up handoff context
        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        mock_handoff = HandoffContext(
            handoff_id="test123",
            source_agent="ask",
            target_agent="architect",
            original_question="How should I design my VPC?",
            context={"scan_summary": "Scanned 50 resources"},
            channel_id="C123",
            thread_ts=None,
            user_id="U456",
            created_at="2024-01-01T00:00:00Z",
            expires_at=future_time,
            status="accepted",
            session_id="session-abc",
            reason="Architecture question detected",
            confidence=0.9
        )
        mock_handoff_service.accept_handoff.return_value = mock_handoff

        # Create payload
        payload = {
            "channel": {"id": "C123"},
            "user": {"id": "U456"},
            "message": {"ts": "1234567890.123456"},
            "actions": [{"action_id": "handoff_accept_test123", "value": "test123"}]
        }
        action = {"action_id": "handoff_accept_test123", "value": "test123"}

        # Import and call handler
        with patch('handlers.slack_router.HandoffService', return_value=mock_handoff_service):
            from handlers.slack_router import handle_handoff_accept
            result = handle_handoff_accept(payload, action)

        # Verify architect agent was invoked
        mock_services["architect"].assert_called_once()
        call_args = mock_services["architect"].call_args
        assert "VPC" in call_args[0][0]  # Original question in prompt
        assert call_args[0][1] == "session-abc"  # Session ID preserved

        # Verify messages were posted
        assert mock_services["slack"].post_message.called
        assert result["statusCode"] == 200

    def test_accept_handoff_to_remediate(self, mock_services, mock_handoff_service):
        """Test accepting handoff to Remediate agent."""
        from services.handoff_service import HandoffContext

        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        mock_handoff = HandoffContext(
            handoff_id="fix456",
            source_agent="ask",
            target_agent="remediate",
            original_question="Fix my S3 encryption",
            context={
                "finding_count": 3,
                "finding_types": ["unencrypted S3 bucket", "public access not blocked"]
            },
            channel_id="C789",
            thread_ts=None,
            user_id="U101",
            created_at="2024-01-01T00:00:00Z",
            expires_at=future_time,
            status="accepted",
            session_id="session-fix",
            reason="Found 3 security issues",
            confidence=0.85
        )
        mock_handoff_service.accept_handoff.return_value = mock_handoff

        payload = {
            "channel": {"id": "C789"},
            "user": {"id": "U101"},
            "message": {"ts": "1234567890.123456"},
            "actions": [{"action_id": "handoff_accept_fix456", "value": "fix456"}]
        }
        action = {"action_id": "handoff_accept_fix456", "value": "fix456"}

        with patch('handlers.slack_router.HandoffService', return_value=mock_handoff_service):
            from handlers.slack_router import handle_handoff_accept
            result = handle_handoff_accept(payload, action)

        # Verify remediate agent was invoked with context
        mock_services["remediate"].assert_called_once()
        call_args = mock_services["remediate"].call_args
        assert "S3" in call_args[0][0]  # Original question in prompt
        assert call_args[1].get("context") is not None  # Context passed

        assert result["statusCode"] == 200

    def test_accept_expired_handoff(self, mock_services, mock_handoff_service):
        """Test accepting an expired handoff shows error."""
        mock_handoff_service.accept_handoff.return_value = None  # Expired/not found

        payload = {
            "channel": {"id": "C123"},
            "user": {"id": "U456"},
            "message": {"ts": "1234567890.123456"},
            "actions": [{"action_id": "handoff_accept_expired", "value": "expired"}]
        }
        action = {"action_id": "handoff_accept_expired", "value": "expired"}

        with patch('handlers.slack_router.HandoffService', return_value=mock_handoff_service):
            from handlers.slack_router import handle_handoff_accept
            result = handle_handoff_accept(payload, action)

        # Verify error message was posted
        mock_services["slack"].post_message.assert_called()
        call_args = mock_services["slack"].post_message.call_args
        assert "expired" in call_args[1].get("text", "").lower() or "expired" in str(call_args)

        # Neither agent should be invoked
        mock_services["architect"].assert_not_called()
        mock_services["remediate"].assert_not_called()


class TestHandoffDeclineHandler:
    """Tests for handle_handoff_decline handler."""

    @pytest.fixture
    def mock_services(self):
        """Set up mocked services."""
        with patch('handlers.slack_router.get_slack_service') as mock_slack_fn:
            mock_slack = MagicMock()
            mock_slack_fn.return_value = mock_slack
            yield {"slack": mock_slack}

    @pytest.fixture
    def mock_handoff_service(self):
        """Set up mocked HandoffService."""
        with patch('services.handoff_service.HandoffService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service
            yield mock_service

    def test_decline_handoff(self, mock_services, mock_handoff_service):
        """Test declining a handoff."""
        from services.handoff_service import HandoffContext

        future_time = (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z"
        mock_handoff = HandoffContext(
            handoff_id="decline123",
            source_agent="ask",
            target_agent="architect",
            original_question="Design question",
            context={},
            channel_id="C123",
            thread_ts=None,
            user_id="U456",
            created_at="2024-01-01T00:00:00Z",
            expires_at=future_time,
            status="pending",
            reason="",
            confidence=0.8
        )
        mock_handoff_service.get_handoff.return_value = mock_handoff
        mock_handoff_service.decline_handoff.return_value = True

        payload = {
            "channel": {"id": "C123"},
            "user": {"id": "U456"},
            "message": {"ts": "1234567890.123456"},
            "actions": [{"action_id": "handoff_decline_decline123", "value": "decline123"}]
        }
        action = {"action_id": "handoff_decline_decline123", "value": "decline123"}

        with patch('handlers.slack_router.HandoffService', return_value=mock_handoff_service):
            from handlers.slack_router import handle_handoff_decline
            result = handle_handoff_decline(payload, action)

        # Verify decline was called
        mock_handoff_service.decline_handoff.assert_called_once_with("decline123")

        # Verify acknowledgment message
        mock_services["slack"].post_message.assert_called()

        assert result["statusCode"] == 200

    def test_decline_removes_message(self, mock_services, mock_handoff_service):
        """Test that declining removes the handoff suggestion message."""
        mock_handoff_service.get_handoff.return_value = None

        payload = {
            "channel": {"id": "C123"},
            "user": {"id": "U456"},
            "message": {"ts": "1234567890.123456"},
            "actions": [{"action_id": "handoff_decline_test", "value": "test"}]
        }
        action = {"action_id": "handoff_decline_test", "value": "test"}

        with patch('handlers.slack_router.HandoffService', return_value=mock_handoff_service):
            from handlers.slack_router import handle_handoff_decline
            result = handle_handoff_decline(payload, action)

        # Verify message deletion was attempted
        mock_services["slack"].client.chat_delete.assert_called_once_with(
            channel="C123",
            ts="1234567890.123456"
        )


class TestHandoffWorkflowIntegration:
    """End-to-end workflow tests for handoff functionality."""

    def test_ask_to_remediate_workflow(self):
        """Test complete Ask → Remediate handoff workflow."""
        from services.handoff_service import HandoffContext, HandoffService

        # This test verifies the data flow, not actual AWS calls
        with patch('boto3.client') as mock_boto:
            mock_db = MagicMock()
            mock_boto.return_value = mock_db
            mock_db.describe_table.return_value = {"Table": {"TableName": "test"}}
            mock_db.put_item.return_value = {}

            service = HandoffService(table_name="test-handoffs")

            # Step 1: Ask Agent creates handoff
            handoff = service.create_handoff(
                source_agent="ask",
                target_agent="remediate",
                original_question="Fix my S3 security issues",
                context={
                    "finding_count": 2,
                    "finding_types": ["unencrypted S3 bucket", "public access"]
                },
                channel_id="C12345",
                user_id="U67890",
                session_id="session-test",
                reason="Found 2 security issues that can be remediated",
                confidence=0.88
            )

            assert handoff is not None
            assert handoff.source_agent == "ask"
            assert handoff.target_agent == "remediate"
            assert handoff.status == "pending"
            assert handoff.context["finding_count"] == 2

    def test_ask_to_architect_workflow(self):
        """Test complete Ask → Architect handoff workflow."""
        from services.handoff_service import HandoffContext, HandoffService

        with patch('boto3.client') as mock_boto:
            mock_db = MagicMock()
            mock_boto.return_value = mock_db
            mock_db.describe_table.return_value = {"Table": {"TableName": "test"}}
            mock_db.put_item.return_value = {}

            service = HandoffService(table_name="test-handoffs")

            # Step 1: Ask Agent creates handoff
            handoff = service.create_handoff(
                source_agent="ask",
                target_agent="architect",
                original_question="How should I design my multi-region VPC?",
                context={
                    "original_question": "How should I design my multi-region VPC?",
                    "scan_summary": "Scanned 5 VPCs, 20 subnets"
                },
                channel_id="C12345",
                user_id="U67890",
                session_id="session-arch",
                reason="Your question suggests you need architecture recommendations",
                confidence=0.92
            )

            assert handoff is not None
            assert handoff.source_agent == "ask"
            assert handoff.target_agent == "architect"
            assert "multi-region" in handoff.original_question.lower()
