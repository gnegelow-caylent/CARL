"""
Exception and Risk Acceptance Manager for CARL.

Manages compliance exceptions and risk acceptances:
- Risk acceptance workflow (request -> review -> approve/deny)
- Exception tracking with expiration
- Audit trail of all exception decisions
- Automated expiration notifications
- Integration with findings for exception matching

Every organization has accepted risks - this service makes them
visible, trackable, and auditable.
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
import boto3
from boto3.dynamodb.conditions import Key, Attr

from utils.logger import get_logger

logger = get_logger(__name__)


class ExceptionStatus(Enum):
    """Status of a risk exception."""
    PENDING = "pending"  # Awaiting review
    APPROVED = "approved"  # Approved and active
    DENIED = "denied"  # Denied by reviewer
    EXPIRED = "expired"  # Past expiration date
    REVOKED = "revoked"  # Manually revoked before expiration
    SUPERSEDED = "superseded"  # Replaced by a new exception


class ExceptionType(Enum):
    """Types of compliance exceptions."""
    RISK_ACCEPTANCE = "risk_acceptance"  # Accept the risk, no remediation
    COMPENSATING_CONTROL = "compensating_control"  # Alternative control in place
    PLANNED_REMEDIATION = "planned_remediation"  # Will be fixed by date
    FALSE_POSITIVE = "false_positive"  # Finding is incorrect
    NOT_APPLICABLE = "not_applicable"  # Control doesn't apply


class RiskLevel(Enum):
    """Risk level of the exception."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Exception:
    """A compliance exception or risk acceptance."""
    exception_id: str
    title: str
    description: str
    exception_type: str
    risk_level: str
    status: str

    # What this exception applies to
    finding_id: Optional[str]  # Specific finding, if applicable
    control_ids: list[str]  # SOC 2 controls affected
    resource_type: str
    resource_id: str
    account_id: str

    # Business justification
    business_justification: str
    compensating_controls: str  # If type is compensating_control
    remediation_plan: str  # If type is planned_remediation
    remediation_date: Optional[str]  # Target date for planned remediation

    # Lifecycle
    requested_by: str
    requested_at: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: str = ""
    expires_at: str = ""  # When the exception expires
    expired_at: Optional[str] = None  # Actual expiration timestamp
    revoked_by: Optional[str] = None
    revoked_at: Optional[str] = None
    revoke_reason: str = ""

    # Metadata
    tags: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)  # S3 keys for supporting docs
    audit_trail: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Exception":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_active(self) -> bool:
        """Check if exception is currently active."""
        if self.status != ExceptionStatus.APPROVED.value:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow().isoformat():
            return False
        return True


@dataclass
class ExceptionRequest:
    """A request to create a new exception."""
    title: str
    description: str
    exception_type: ExceptionType
    risk_level: RiskLevel
    finding_id: Optional[str]
    control_ids: list[str]
    resource_type: str
    resource_id: str
    business_justification: str
    compensating_controls: str = ""
    remediation_plan: str = ""
    remediation_date: Optional[str] = None
    requested_duration_days: int = 90  # Default 90 days
    tags: list[str] = field(default_factory=list)


class ExceptionManager:
    """Service for managing compliance exceptions."""

    def __init__(
        self,
        exceptions_table: str,
        findings_table: str = None,
        notifications_enabled: bool = True
    ):
        self.exceptions_table = exceptions_table
        self.findings_table = findings_table
        self.notifications_enabled = notifications_enabled

        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(exceptions_table)
        self.sts = boto3.client("sts")

        if findings_table:
            self.findings_db = self.dynamodb.Table(findings_table)
        else:
            self.findings_db = None

        self._account_id = None

    @property
    def account_id(self) -> str:
        if self._account_id is None:
            self._account_id = self.sts.get_caller_identity()["Account"]
        return self._account_id

    def request_exception(
        self,
        request: ExceptionRequest,
        requester_id: str
    ) -> Exception:
        """Create a new exception request."""
        timestamp = datetime.utcnow()
        exception_id = f"exc_{timestamp.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Calculate expiration date
        expires_at = (timestamp + timedelta(days=request.requested_duration_days)).isoformat()

        # Create exception
        exception = Exception(
            exception_id=exception_id,
            title=request.title,
            description=request.description,
            exception_type=request.exception_type.value,
            risk_level=request.risk_level.value,
            status=ExceptionStatus.PENDING.value,
            finding_id=request.finding_id,
            control_ids=request.control_ids,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            account_id=self.account_id,
            business_justification=request.business_justification,
            compensating_controls=request.compensating_controls,
            remediation_plan=request.remediation_plan,
            remediation_date=request.remediation_date,
            requested_by=requester_id,
            requested_at=timestamp.isoformat(),
            expires_at=expires_at,
            tags=request.tags,
            audit_trail=[{
                "action": "requested",
                "timestamp": timestamp.isoformat(),
                "user": requester_id,
                "details": f"Exception requested for {request.requested_duration_days} days"
            }]
        )

        # Store in DynamoDB
        self.table.put_item(Item=exception.to_dict())

        logger.info(f"Exception requested: {exception_id} by {requester_id}")
        return exception

    def approve_exception(
        self,
        exception_id: str,
        approver_id: str,
        notes: str = "",
        modified_expiration: str = None
    ) -> Exception:
        """Approve a pending exception request."""
        exception = self.get_exception(exception_id)
        if not exception:
            raise ValueError(f"Exception {exception_id} not found")

        if exception.status != ExceptionStatus.PENDING.value:
            raise ValueError(f"Exception {exception_id} is not pending (status: {exception.status})")

        timestamp = datetime.utcnow()

        # Update exception
        exception.status = ExceptionStatus.APPROVED.value
        exception.reviewed_by = approver_id
        exception.reviewed_at = timestamp.isoformat()
        exception.review_notes = notes
        if modified_expiration:
            exception.expires_at = modified_expiration

        exception.audit_trail.append({
            "action": "approved",
            "timestamp": timestamp.isoformat(),
            "user": approver_id,
            "details": notes or "Exception approved"
        })

        # Save
        self.table.put_item(Item=exception.to_dict())

        # If this exception is for a specific finding, update the finding
        if exception.finding_id and self.findings_db:
            self._link_exception_to_finding(exception)

        logger.info(f"Exception approved: {exception_id} by {approver_id}")
        return exception

    def deny_exception(
        self,
        exception_id: str,
        denier_id: str,
        reason: str
    ) -> Exception:
        """Deny a pending exception request."""
        exception = self.get_exception(exception_id)
        if not exception:
            raise ValueError(f"Exception {exception_id} not found")

        if exception.status != ExceptionStatus.PENDING.value:
            raise ValueError(f"Exception {exception_id} is not pending (status: {exception.status})")

        timestamp = datetime.utcnow()

        exception.status = ExceptionStatus.DENIED.value
        exception.reviewed_by = denier_id
        exception.reviewed_at = timestamp.isoformat()
        exception.review_notes = reason

        exception.audit_trail.append({
            "action": "denied",
            "timestamp": timestamp.isoformat(),
            "user": denier_id,
            "details": reason
        })

        self.table.put_item(Item=exception.to_dict())

        logger.info(f"Exception denied: {exception_id} by {denier_id}")
        return exception

    def revoke_exception(
        self,
        exception_id: str,
        revoker_id: str,
        reason: str
    ) -> Exception:
        """Revoke an approved exception before expiration."""
        exception = self.get_exception(exception_id)
        if not exception:
            raise ValueError(f"Exception {exception_id} not found")

        if exception.status != ExceptionStatus.APPROVED.value:
            raise ValueError(f"Exception {exception_id} is not approved (status: {exception.status})")

        timestamp = datetime.utcnow()

        exception.status = ExceptionStatus.REVOKED.value
        exception.revoked_by = revoker_id
        exception.revoked_at = timestamp.isoformat()
        exception.revoke_reason = reason

        exception.audit_trail.append({
            "action": "revoked",
            "timestamp": timestamp.isoformat(),
            "user": revoker_id,
            "details": reason
        })

        self.table.put_item(Item=exception.to_dict())

        logger.info(f"Exception revoked: {exception_id} by {revoker_id}")
        return exception

    def renew_exception(
        self,
        exception_id: str,
        requester_id: str,
        additional_days: int = 90,
        updated_justification: str = ""
    ) -> Exception:
        """Renew an exception that is expiring or expired."""
        old_exception = self.get_exception(exception_id)
        if not old_exception:
            raise ValueError(f"Exception {exception_id} not found")

        # Mark old exception as superseded
        timestamp = datetime.utcnow()
        old_exception.status = ExceptionStatus.SUPERSEDED.value
        old_exception.audit_trail.append({
            "action": "superseded",
            "timestamp": timestamp.isoformat(),
            "user": requester_id,
            "details": "Renewed with new exception"
        })
        self.table.put_item(Item=old_exception.to_dict())

        # Create new exception request
        new_request = ExceptionRequest(
            title=f"[Renewal] {old_exception.title}",
            description=old_exception.description,
            exception_type=ExceptionType(old_exception.exception_type),
            risk_level=RiskLevel(old_exception.risk_level),
            finding_id=old_exception.finding_id,
            control_ids=old_exception.control_ids,
            resource_type=old_exception.resource_type,
            resource_id=old_exception.resource_id,
            business_justification=updated_justification or old_exception.business_justification,
            compensating_controls=old_exception.compensating_controls,
            remediation_plan=old_exception.remediation_plan,
            remediation_date=old_exception.remediation_date,
            requested_duration_days=additional_days,
            tags=old_exception.tags + ["renewal"]
        )

        new_exception = self.request_exception(new_request, requester_id)

        # Add reference to old exception
        new_exception.audit_trail.append({
            "action": "renewed_from",
            "timestamp": timestamp.isoformat(),
            "user": requester_id,
            "details": f"Renewed from {exception_id}"
        })
        self.table.put_item(Item=new_exception.to_dict())

        logger.info(f"Exception renewed: {exception_id} -> {new_exception.exception_id}")
        return new_exception

    def get_exception(self, exception_id: str) -> Optional[Exception]:
        """Get an exception by ID."""
        try:
            response = self.table.get_item(Key={"exception_id": exception_id})
            item = response.get("Item")
            return Exception.from_dict(item) if item else None
        except Exception as e:
            logger.exception(f"Error getting exception {exception_id}")
            return None

    def list_exceptions(
        self,
        status: ExceptionStatus = None,
        control_id: str = None,
        resource_id: str = None,
        include_expired: bool = False
    ) -> list[Exception]:
        """List exceptions with optional filters."""
        try:
            # Build filter expression
            filter_parts = []
            expression_values = {}

            if status:
                filter_parts.append("status = :status")
                expression_values[":status"] = status.value

            if control_id:
                filter_parts.append("contains(control_ids, :control)")
                expression_values[":control"] = control_id

            if resource_id:
                filter_parts.append("resource_id = :resource")
                expression_values[":resource"] = resource_id

            if not include_expired:
                filter_parts.append("(expires_at > :now OR attribute_not_exists(expires_at))")
                expression_values[":now"] = datetime.utcnow().isoformat()

            if filter_parts:
                response = self.table.scan(
                    FilterExpression=" AND ".join(filter_parts),
                    ExpressionAttributeValues=expression_values
                )
            else:
                response = self.table.scan()

            return [Exception.from_dict(item) for item in response.get("Items", [])]

        except Exception as e:
            logger.exception("Error listing exceptions")
            return []

    def get_pending_exceptions(self) -> list[Exception]:
        """Get all exceptions awaiting review."""
        return self.list_exceptions(status=ExceptionStatus.PENDING)

    def get_active_exceptions(self) -> list[Exception]:
        """Get all currently active exceptions."""
        return self.list_exceptions(status=ExceptionStatus.APPROVED, include_expired=False)

    def get_expiring_exceptions(self, days: int = 30) -> list[Exception]:
        """Get exceptions expiring within the specified number of days."""
        now = datetime.utcnow()
        threshold = (now + timedelta(days=days)).isoformat()

        try:
            response = self.table.scan(
                FilterExpression="status = :status AND expires_at <= :threshold AND expires_at > :now",
                ExpressionAttributeValues={
                    ":status": ExceptionStatus.APPROVED.value,
                    ":threshold": threshold,
                    ":now": now.isoformat()
                }
            )
            return [Exception.from_dict(item) for item in response.get("Items", [])]
        except Exception as e:
            logger.exception("Error getting expiring exceptions")
            return []

    def process_expirations(self) -> list[Exception]:
        """Process expired exceptions (run periodically)."""
        now = datetime.utcnow()
        expired = []

        try:
            # Find expired but not yet marked as expired
            response = self.table.scan(
                FilterExpression="status = :status AND expires_at <= :now",
                ExpressionAttributeValues={
                    ":status": ExceptionStatus.APPROVED.value,
                    ":now": now.isoformat()
                }
            )

            for item in response.get("Items", []):
                exception = Exception.from_dict(item)
                exception.status = ExceptionStatus.EXPIRED.value
                exception.expired_at = now.isoformat()
                exception.audit_trail.append({
                    "action": "expired",
                    "timestamp": now.isoformat(),
                    "user": "system",
                    "details": "Exception expired automatically"
                })
                self.table.put_item(Item=exception.to_dict())
                expired.append(exception)

            if expired:
                logger.info(f"Processed {len(expired)} expired exceptions")

            return expired

        except Exception as e:
            logger.exception("Error processing expirations")
            return []

    def check_finding_has_exception(self, finding_id: str) -> Optional[Exception]:
        """Check if a finding has an active exception."""
        try:
            response = self.table.scan(
                FilterExpression="finding_id = :finding AND status = :status AND expires_at > :now",
                ExpressionAttributeValues={
                    ":finding": finding_id,
                    ":status": ExceptionStatus.APPROVED.value,
                    ":now": datetime.utcnow().isoformat()
                }
            )
            items = response.get("Items", [])
            return Exception.from_dict(items[0]) if items else None
        except Exception as e:
            logger.exception(f"Error checking exception for finding {finding_id}")
            return None

    def check_resource_has_exception(
        self,
        resource_id: str,
        control_id: str = None
    ) -> Optional[Exception]:
        """Check if a resource has an active exception for a control."""
        try:
            filter_expr = "resource_id = :resource AND status = :status AND expires_at > :now"
            expr_values = {
                ":resource": resource_id,
                ":status": ExceptionStatus.APPROVED.value,
                ":now": datetime.utcnow().isoformat()
            }

            if control_id:
                filter_expr += " AND contains(control_ids, :control)"
                expr_values[":control"] = control_id

            response = self.table.scan(
                FilterExpression=filter_expr,
                ExpressionAttributeValues=expr_values
            )
            items = response.get("Items", [])
            return Exception.from_dict(items[0]) if items else None
        except Exception as e:
            logger.exception(f"Error checking exception for resource {resource_id}")
            return None

    def _link_exception_to_finding(self, exception: Exception) -> None:
        """Update a finding to reference its exception."""
        if not self.findings_db or not exception.finding_id:
            return

        try:
            self.findings_db.update_item(
                Key={"id": exception.finding_id},
                UpdateExpression="SET exception_id = :exc, exception_status = :status",
                ExpressionAttributeValues={
                    ":exc": exception.exception_id,
                    ":status": exception.status
                }
            )
        except Exception as e:
            logger.warning(f"Could not link exception to finding: {e}")

    def get_exception_statistics(self) -> dict:
        """Get statistics about exceptions."""
        try:
            response = self.table.scan()
            items = response.get("Items", [])

            now = datetime.utcnow().isoformat()

            stats = {
                "total": len(items),
                "by_status": {},
                "by_type": {},
                "by_risk_level": {},
                "pending_review": 0,
                "active": 0,
                "expiring_soon": 0,  # Within 30 days
                "expired_last_30_days": 0,
                "average_duration_days": 0,
            }

            durations = []
            thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
            thirty_days_ahead = (datetime.utcnow() + timedelta(days=30)).isoformat()

            for item in items:
                status = item.get("status", "unknown")
                exc_type = item.get("exception_type", "unknown")
                risk = item.get("risk_level", "unknown")

                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                stats["by_type"][exc_type] = stats["by_type"].get(exc_type, 0) + 1
                stats["by_risk_level"][risk] = stats["by_risk_level"].get(risk, 0) + 1

                if status == "pending":
                    stats["pending_review"] += 1
                elif status == "approved":
                    expires = item.get("expires_at", "9999")
                    if expires > now:
                        stats["active"] += 1
                        if expires <= thirty_days_ahead:
                            stats["expiring_soon"] += 1
                elif status == "expired":
                    expired_at = item.get("expired_at", "")
                    if expired_at >= thirty_days_ago:
                        stats["expired_last_30_days"] += 1

                # Calculate duration
                requested = item.get("requested_at", "")
                expires = item.get("expires_at", "")
                if requested and expires:
                    try:
                        req_dt = datetime.fromisoformat(requested.replace("Z", "+00:00"))
                        exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                        durations.append((exp_dt - req_dt).days)
                    except:
                        pass

            if durations:
                stats["average_duration_days"] = sum(durations) / len(durations)

            return stats

        except Exception as e:
            logger.exception("Error getting exception statistics")
            return {"error": str(e)}

    def format_exception_for_slack(self, exception: Exception) -> dict:
        """Format an exception for Slack display."""
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "denied": "❌",
            "expired": "⌛",
            "revoked": "🚫",
            "superseded": "🔄"
        }

        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji.get(exception.status, '❓')} {exception.title}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*ID:* `{exception.exception_id}`"},
                    {"type": "mrkdwn", "text": f"*Status:* {exception.status.title()}"},
                    {"type": "mrkdwn", "text": f"*Risk:* {risk_emoji.get(exception.risk_level, '')} {exception.risk_level.title()}"},
                    {"type": "mrkdwn", "text": f"*Type:* {exception.exception_type.replace('_', ' ').title()}"},
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Resource:* `{exception.resource_id}`\n*Controls:* {', '.join(exception.control_ids)}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Justification:*\n{exception.business_justification[:500]}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Requested by <@{exception.requested_by}> on {exception.requested_at[:10]}"},
                    {"type": "mrkdwn", "text": f"Expires: {exception.expires_at[:10]}"}
                ]
            }
        ]

        # Add action buttons for pending exceptions
        if exception.status == ExceptionStatus.PENDING.value:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "action_id": f"exception_approve_{exception.exception_id}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Deny"},
                        "style": "danger",
                        "action_id": f"exception_deny_{exception.exception_id}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Request Info"},
                        "action_id": f"exception_info_{exception.exception_id}"
                    }
                ]
            })

        return {"blocks": blocks}
