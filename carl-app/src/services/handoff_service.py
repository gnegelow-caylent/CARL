"""
CARL Handoff Service - DynamoDB Context Storage for Multi-Agent Handoffs

This service manages handoff context between CARL's agents (Ask, Architect, Remediate),
enabling seamless transitions based on user intent.

Architecture:
    User → Ask Agent → (detects handoff intent) → HandoffService
                                                        ↓
    User confirms → HandoffService retrieves context → Target Agent

TTL: Handoff contexts expire after 1 hour to prevent stale data.
"""

import os
import json
import uuid
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class HandoffContext:
    """Context data stored for agent handoffs."""
    handoff_id: str
    source_agent: str  # "ask", "architect", "remediate"
    target_agent: str  # "ask", "architect", "remediate"
    original_question: str
    context: dict  # Additional context from source agent
    channel_id: str
    thread_ts: Optional[str]
    user_id: str
    created_at: str
    expires_at: str
    status: str  # "pending", "accepted", "declined", "expired"
    session_id: Optional[str] = None
    reason: str = ""  # Why handoff was suggested
    confidence: float = 0.0  # Confidence score (0.0-1.0)

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "pk": {"S": f"HANDOFF#{self.handoff_id}"},
            "sk": {"S": f"CONTEXT#{self.source_agent}#{self.target_agent}"},
            "handoff_id": {"S": self.handoff_id},
            "source_agent": {"S": self.source_agent},
            "target_agent": {"S": self.target_agent},
            "original_question": {"S": self.original_question},
            "context": {"S": json.dumps(self.context)},
            "channel_id": {"S": self.channel_id},
            "user_id": {"S": self.user_id},
            "created_at": {"S": self.created_at},
            "expires_at": {"S": self.expires_at},
            "status": {"S": self.status},
            "reason": {"S": self.reason},
            "confidence": {"N": str(self.confidence)},
            "ttl": {"N": str(int(datetime.fromisoformat(self.expires_at.replace("Z", "+00:00")).timestamp()))}
        }

        if self.thread_ts:
            item["thread_ts"] = {"S": self.thread_ts}
        if self.session_id:
            item["session_id"] = {"S": self.session_id}

        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "HandoffContext":
        """Create from DynamoDB item format."""
        return cls(
            handoff_id=item["handoff_id"]["S"],
            source_agent=item["source_agent"]["S"],
            target_agent=item["target_agent"]["S"],
            original_question=item["original_question"]["S"],
            context=json.loads(item["context"]["S"]),
            channel_id=item["channel_id"]["S"],
            thread_ts=item.get("thread_ts", {}).get("S"),
            user_id=item["user_id"]["S"],
            created_at=item["created_at"]["S"],
            expires_at=item["expires_at"]["S"],
            status=item["status"]["S"],
            session_id=item.get("session_id", {}).get("S"),
            reason=item.get("reason", {}).get("S", ""),
            confidence=float(item.get("confidence", {}).get("N", "0.0"))
        )


class HandoffService:
    """
    Service for managing multi-agent handoff contexts.

    Stores context in DynamoDB with 1-hour TTL for automatic cleanup.
    """

    def __init__(self, table_name: str = None):
        """
        Initialize the handoff service.

        Args:
            table_name: DynamoDB table name. Defaults to HANDOFFS_TABLE env var.
        """
        self.table_name = table_name or os.environ.get("HANDOFFS_TABLE", "carl-dev-handoffs")
        self.dynamodb = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        self._table_exists = None

    def _ensure_table_exists(self) -> bool:
        """Check if the DynamoDB table exists."""
        if self._table_exists is not None:
            return self._table_exists

        try:
            self.dynamodb.describe_table(TableName=self.table_name)
            self._table_exists = True
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.warning(f"Handoffs table {self.table_name} does not exist")
                self._table_exists = False
                return False
            raise

    def create_handoff(
        self,
        source_agent: str,
        target_agent: str,
        original_question: str,
        context: dict,
        channel_id: str,
        user_id: str,
        thread_ts: Optional[str] = None,
        session_id: Optional[str] = None,
        reason: str = "",
        confidence: float = 0.0
    ) -> Optional[HandoffContext]:
        """
        Create a new handoff context.

        Args:
            source_agent: Agent initiating handoff ("ask", "architect", "remediate")
            target_agent: Agent receiving handoff ("ask", "architect", "remediate")
            original_question: The user's original question
            context: Additional context from source agent (scan results, findings, etc.)
            channel_id: Slack channel ID
            user_id: Slack user ID
            thread_ts: Optional Slack thread timestamp
            session_id: Optional session ID for conversation continuity
            reason: Why the handoff is suggested
            confidence: Confidence score (0.0-1.0)

        Returns:
            HandoffContext if successful, None if table doesn't exist
        """
        if not self._ensure_table_exists():
            logger.warning("Handoffs table not available - handoff context not stored")
            return None

        handoff_id = str(uuid.uuid4())[:8]  # Short ID for easy reference
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=1)  # 1 hour TTL

        handoff = HandoffContext(
            handoff_id=handoff_id,
            source_agent=source_agent,
            target_agent=target_agent,
            original_question=original_question,
            context=context,
            channel_id=channel_id,
            thread_ts=thread_ts,
            user_id=user_id,
            created_at=now.isoformat() + "Z",
            expires_at=expires_at.isoformat() + "Z",
            status="pending",
            session_id=session_id,
            reason=reason,
            confidence=confidence
        )

        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item=handoff.to_dynamodb_item()
            )
            logger.info(f"Created handoff {handoff_id}: {source_agent} → {target_agent}")
            return handoff
        except ClientError as e:
            logger.error(f"Failed to create handoff: {e}")
            return None

    def get_handoff(self, handoff_id: str) -> Optional[HandoffContext]:
        """
        Retrieve a handoff context by ID.

        Args:
            handoff_id: The handoff ID

        Returns:
            HandoffContext if found and not expired, None otherwise
        """
        if not self._ensure_table_exists():
            return None

        try:
            # Query by pk prefix since we don't know the full sk
            response = self.dynamodb.query(
                TableName=self.table_name,
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={
                    ":pk": {"S": f"HANDOFF#{handoff_id}"}
                }
            )

            items = response.get("Items", [])
            if not items:
                logger.warning(f"Handoff {handoff_id} not found")
                return None

            handoff = HandoffContext.from_dynamodb_item(items[0])

            # Check if expired
            expires_at = datetime.fromisoformat(handoff.expires_at.replace("Z", "+00:00"))
            if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) > expires_at:
                logger.warning(f"Handoff {handoff_id} has expired")
                return None

            return handoff

        except ClientError as e:
            logger.error(f"Failed to get handoff {handoff_id}: {e}")
            return None

    def update_handoff_status(self, handoff_id: str, status: str) -> bool:
        """
        Update the status of a handoff.

        Args:
            handoff_id: The handoff ID
            status: New status ("pending", "accepted", "declined", "expired")

        Returns:
            True if successful, False otherwise
        """
        if not self._ensure_table_exists():
            return False

        # First get the handoff to find the sk
        handoff = self.get_handoff(handoff_id)
        if not handoff:
            return False

        try:
            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={
                    "pk": {"S": f"HANDOFF#{handoff_id}"},
                    "sk": {"S": f"CONTEXT#{handoff.source_agent}#{handoff.target_agent}"}
                },
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": {"S": status}}
            )
            logger.info(f"Updated handoff {handoff_id} status to {status}")
            return True
        except ClientError as e:
            logger.error(f"Failed to update handoff {handoff_id}: {e}")
            return False

    def accept_handoff(self, handoff_id: str) -> Optional[HandoffContext]:
        """
        Accept a handoff and return its context.

        Args:
            handoff_id: The handoff ID

        Returns:
            HandoffContext if successful, None otherwise
        """
        handoff = self.get_handoff(handoff_id)
        if not handoff:
            return None

        if handoff.status != "pending":
            logger.warning(f"Handoff {handoff_id} is not pending (status: {handoff.status})")
            return None

        if self.update_handoff_status(handoff_id, "accepted"):
            handoff.status = "accepted"
            return handoff

        return None

    def decline_handoff(self, handoff_id: str) -> bool:
        """
        Decline a handoff.

        Args:
            handoff_id: The handoff ID

        Returns:
            True if successful, False otherwise
        """
        handoff = self.get_handoff(handoff_id)
        if not handoff:
            return False

        return self.update_handoff_status(handoff_id, "declined")

    def list_pending_handoffs(self, user_id: str = None, channel_id: str = None) -> list[HandoffContext]:
        """
        List pending handoffs, optionally filtered by user or channel.

        Note: This does a scan which is inefficient for large tables.
        For production use, consider adding a GSI on status+user_id.

        Args:
            user_id: Optional filter by user
            channel_id: Optional filter by channel

        Returns:
            List of pending HandoffContext objects
        """
        if not self._ensure_table_exists():
            return []

        try:
            # Build filter expression
            filter_parts = ["#status = :pending"]
            expr_names = {"#status": "status"}
            expr_values = {":pending": {"S": "pending"}}

            if user_id:
                filter_parts.append("user_id = :user_id")
                expr_values[":user_id"] = {"S": user_id}

            if channel_id:
                filter_parts.append("channel_id = :channel_id")
                expr_values[":channel_id"] = {"S": channel_id}

            response = self.dynamodb.scan(
                TableName=self.table_name,
                FilterExpression=" AND ".join(filter_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values
            )

            handoffs = []
            for item in response.get("Items", []):
                try:
                    handoff = HandoffContext.from_dynamodb_item(item)
                    # Double-check expiration
                    expires_at = datetime.fromisoformat(handoff.expires_at.replace("Z", "+00:00"))
                    if datetime.utcnow().replace(tzinfo=expires_at.tzinfo) <= expires_at:
                        handoffs.append(handoff)
                except Exception as e:
                    logger.warning(f"Failed to parse handoff item: {e}")

            return handoffs

        except ClientError as e:
            logger.error(f"Failed to list pending handoffs: {e}")
            return []
