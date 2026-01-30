"""
Build Session Service - Manages iterative infrastructure build conversations.

Stores session data for intelligent build flows where AI asks questions
iteratively until it has enough information to generate code.
"""
import boto3
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BuildSession:
    """Build session data."""
    session_id: str
    user_id: str
    channel_id: str
    requirement: str  # Original user request
    environment_scan: Dict[str, Any]  # AWS environment scan results
    environment_summary: str  # Human-readable summary for AI context
    conversation_history: List[Dict[str, str]]  # Q&A history
    created_at: str
    updated_at: str
    status: str  # active, ready_to_build, completed, expired

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item."""
        return {
            "pk": f"BUILD_SESSION#{self.session_id}",
            "sk": f"USER#{self.user_id}",
            "session_id": self.session_id,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "requirement": self.requirement,
            "environment_scan": json.dumps(self.environment_scan),
            "environment_summary": self.environment_summary,
            "conversation_history": json.dumps(self.conversation_history),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "ttl": int((datetime.utcnow() + timedelta(hours=24)).timestamp())  # Expire after 24 hours
        }

    @staticmethod
    def from_dynamodb_item(item: Dict[str, Any]) -> 'BuildSession':
        """Create from DynamoDB item."""
        return BuildSession(
            session_id=item["session_id"],
            user_id=item["user_id"],
            channel_id=item["channel_id"],
            requirement=item["requirement"],
            environment_scan=json.loads(item["environment_scan"]),
            environment_summary=item.get("environment_summary", ""),
            conversation_history=json.loads(item["conversation_history"]),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            status=item["status"]
        )


class BuildSessionService:
    """Manages build session storage and retrieval."""

    def __init__(self, table_name: str = None):
        self.table_name = table_name or "carl-dev-config"  # Use config table for now
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.table_name)

    def create_session(
        self,
        user_id: str,
        channel_id: str,
        requirement: str,
        environment_scan: Dict[str, Any],
        environment_summary: str = ""
    ) -> BuildSession:
        """Create new build session."""
        session_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()

        session = BuildSession(
            session_id=session_id,
            user_id=user_id,
            channel_id=channel_id,
            requirement=requirement,
            environment_scan=environment_scan,
            environment_summary=environment_summary,
            conversation_history=[],
            created_at=now,
            updated_at=now,
            status="active"
        )

        self.table.put_item(Item=session.to_dynamodb_item())
        logger.info(f"Created build session {session_id} for user {user_id}")

        return session

    def get_session(self, session_id: str, user_id: str) -> Optional[BuildSession]:
        """Retrieve build session."""
        try:
            response = self.table.get_item(
                Key={
                    "pk": f"BUILD_SESSION#{session_id}",
                    "sk": f"USER#{user_id}"
                }
            )

            if "Item" not in response:
                logger.warning(f"Build session {session_id} not found")
                return None

            return BuildSession.from_dynamodb_item(response["Item"])

        except Exception as e:
            logger.error(f"Error retrieving build session {session_id}: {e}")
            return None

    def add_conversation_turn(
        self,
        session_id: str,
        user_id: str,
        question: str,
        answer: str
    ) -> Optional[BuildSession]:
        """Add Q&A turn to conversation history."""
        session = self.get_session(session_id, user_id)
        if not session:
            return None

        session.conversation_history.append({
            "question": question,
            "answer": answer,
            "timestamp": datetime.utcnow().isoformat()
        })

        session.updated_at = datetime.utcnow().isoformat()

        self.table.put_item(Item=session.to_dynamodb_item())
        logger.info(f"Added conversation turn to session {session_id}")

        return session

    def update_session_status(
        self,
        session_id: str,
        user_id: str,
        status: str
    ) -> Optional[BuildSession]:
        """Update session status."""
        session = self.get_session(session_id, user_id)
        if not session:
            return None

        session.status = status
        session.updated_at = datetime.utcnow().isoformat()

        self.table.put_item(Item=session.to_dynamodb_item())
        logger.info(f"Updated session {session_id} status to {status}")

        return session

    def delete_session(self, session_id: str, user_id: str):
        """Delete build session."""
        try:
            self.table.delete_item(
                Key={
                    "pk": f"BUILD_SESSION#{session_id}",
                    "sk": f"USER#{user_id}"
                }
            )
            logger.info(f"Deleted build session {session_id}")
        except Exception as e:
            logger.error(f"Error deleting build session {session_id}: {e}")
