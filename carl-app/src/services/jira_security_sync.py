"""Jira Security Findings Synchronization Service.

Handles automatic synchronization of Security Hub findings with Jira tickets.
"""
import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from services.jira_service import JiraService
from utils.dynamodb_utils import get_table

logger = logging.getLogger(__name__)


class JiraSecuritySync:
    """Synchronizes Security Hub findings with Jira CARLSEC project."""

    def __init__(self, jira_service: Optional[JiraService] = None):
        """Initialize with optional JiraService (for testing)."""
        self.jira = jira_service or JiraService()
        from services.findings_service import FindingsService
        self.findings_service = FindingsService()

    def sync_finding_to_jira(
        self,
        finding_id: str,
        title: str,
        severity: str,
        resource_type: str,
        resource_id: str,
        compliance_status: str,
        recommendation: str,
        aws_account_id: str,
        region: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        Create or update Jira ticket for a Security Hub finding.

        Args:
            finding_id: Security Hub finding ID
            title: Finding title
            severity: CRITICAL, HIGH, MEDIUM, LOW
            resource_type: AWS resource type (e.g., AWS::S3::Bucket)
            resource_id: Resource identifier
            compliance_status: PASSED, FAILED, WARNING, NOT_AVAILABLE
            recommendation: Remediation recommendation
            aws_account_id: AWS account ID
            region: AWS region
            metadata: Additional finding metadata

        Returns:
            Dict with sync result including jira_key, jira_url, success status
        """
        try:
            # Check if finding already has a Jira ticket
            existing = self._get_finding_from_db(finding_id, aws_account_id)

            if existing and existing.get("jira_ticket_id"):
                # Update existing ticket
                logger.info(f"Updating existing Jira ticket for finding {finding_id}: {existing['jira_ticket_id']}")

                # Add comment about status change if needed
                if existing.get("compliance_status") != compliance_status:
                    comment = f"Compliance status changed: {existing.get('compliance_status')} → {compliance_status}"
                    self.jira.add_comment(existing["jira_ticket_id"], comment)

                # Update finding in DB
                self._update_finding_in_db(finding_id, {
                    "compliance_status": compliance_status,
                    "last_synced_at": datetime.utcnow().isoformat(),
                    "jira_last_updated": datetime.utcnow().isoformat()
                }, account_id=aws_account_id)

                return {
                    "success": True,
                    "action": "updated",
                    "jira_key": existing["jira_ticket_id"],
                    "jira_url": f"{self.jira.jira_url}/browse/{existing['jira_ticket_id']}"
                }

            else:
                # Create new Jira ticket
                logger.info(f"Creating new Jira ticket for finding {finding_id}")

                # Build resource ARN from resource_id
                resource_arn = resource_id if resource_id.startswith("arn:") else f"arn:aws:{resource_type}:{region}:{aws_account_id}:{resource_id}"

                # create_security_finding() returns the issue key string, not a dict
                jira_key = self.jira.create_security_finding(
                    finding_id=finding_id,
                    title=title,
                    severity=severity,
                    description=recommendation,  # Use recommendation as description
                    resource_arn=resource_arn,   # Fixed: was resource_type/resource_id
                    account_id=aws_account_id,   # Fixed: was aws_account_id
                    region=region,
                    soc2_controls=metadata.get("control_ids", []) if metadata else [],
                    compliance_status=compliance_status,
                    first_detected=datetime.utcnow().isoformat()
                )

                jira_url = f"{self.jira.jira_url}/browse/{jira_key}"

                # Store Jira ticket ID in DynamoDB
                self._update_finding_in_db(finding_id, {
                    "jira_ticket_id": jira_key,
                    "jira_url": jira_url,
                    "jira_created_at": datetime.utcnow().isoformat(),
                    "jira_last_updated": datetime.utcnow().isoformat(),
                    "last_synced_at": datetime.utcnow().isoformat()
                }, account_id=aws_account_id)

                logger.info(f"Created Jira ticket {jira_key} for finding {finding_id}")

                return {
                    "success": True,
                    "action": "created",
                    "jira_key": jira_key,
                    "jira_url": jira_url
                }

        except Exception as e:
            logger.error(f"Failed to sync finding {finding_id} to Jira: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def sync_exception_to_jira(
        self,
        exception_id: str,
        finding_title: str,
        justification: str,
        expiration_date: str,
        requested_by: str,
        finding_id: Optional[str] = None,
        jira_finding_key: Optional[str] = None
    ) -> dict:
        """
        Create Jira ticket for risk exception request.

        Args:
            exception_id: CARL exception ID
            finding_title: Title of the finding
            justification: Business justification
            expiration_date: When exception expires
            requested_by: User who requested
            finding_id: Related finding ID (optional)
            jira_finding_key: Related Jira finding key (optional)

        Returns:
            Dict with sync result
        """
        try:
            result = self.jira.create_exception_request(
                finding_title=finding_title,
                justification=justification,
                expiration_date=expiration_date,
                requested_by=requested_by,
                finding_id=finding_id
            )

            jira_key = result["key"]
            jira_url = f"{self.jira.jira_url}/browse/{jira_key}"

            # Link to finding ticket if provided
            if jira_finding_key:
                self.jira.link_issues(jira_key, jira_finding_key, "Relates")

            # Store in DynamoDB
            exceptions_table = get_table("carl-risk-exceptions")
            exceptions_table.update_item(
                Key={"exception_id": exception_id},
                UpdateExpression="SET jira_ticket_id = :jira_key, jira_url = :jira_url, jira_created_at = :created",
                ExpressionAttributeValues={
                    ":jira_key": jira_key,
                    ":jira_url": jira_url,
                    ":created": datetime.utcnow().isoformat()
                }
            )

            logger.info(f"Created Jira exception ticket {jira_key} for exception {exception_id}")

            return {
                "success": True,
                "action": "created",
                "jira_key": jira_key,
                "jira_url": jira_url
            }

        except Exception as e:
            logger.error(f"Failed to sync exception {exception_id} to Jira: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def sync_drift_to_jira(
        self,
        drift_id: str,
        resource_type: str,
        resource_id: str,
        drift_type: str,
        detected_at: str,
        expected_state: Dict[str, Any],
        actual_state: Dict[str, Any],
        drift_details: str
    ) -> dict:
        """
        Create Jira ticket for configuration drift.

        Args:
            drift_id: CARL drift ID
            resource_type: AWS resource type
            resource_id: Resource identifier
            drift_type: Type of drift (Modified, Deleted, Created)
            detected_at: When drift was detected
            expected_state: Expected configuration
            actual_state: Actual configuration
            drift_details: Human-readable drift description

        Returns:
            Dict with sync result
        """
        try:
            result = self.jira.create_drift_ticket(
                resource_type=resource_type,
                resource_id=resource_id,
                drift_type=drift_type,
                detected_at=detected_at,
                expected_state=expected_state,
                actual_state=actual_state,
                drift_details=drift_details
            )

            jira_key = result["key"]
            jira_url = f"{self.jira.jira_url}/browse/{jira_key}"

            # Store in DynamoDB
            drift_table = get_table(os.environ.get("DRIFT_TABLE", "carl-dev-drift"))
            drift_table.update_item(
                Key={"drift_id": drift_id},
                UpdateExpression="SET jira_ticket_id = :jira_key, jira_url = :jira_url, jira_created_at = :created",
                ExpressionAttributeValues={
                    ":jira_key": jira_key,
                    ":jira_url": jira_url,
                    ":created": datetime.utcnow().isoformat()
                }
            )

            logger.info(f"Created Jira drift ticket {jira_key} for drift {drift_id}")

            return {
                "success": True,
                "action": "created",
                "jira_key": jira_key,
                "jira_url": jira_url
            }

        except Exception as e:
            logger.error(f"Failed to sync drift {drift_id} to Jira: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_jira_webhook(self, webhook_payload: Dict[str, Any]) -> dict:
        """
        Handle incoming Jira webhook (bi-directional sync).

        Jira → CARL sync for status updates, comments, resolutions.

        Args:
            webhook_payload: Jira webhook JSON payload

        Returns:
            Dict with processing result
        """
        try:
            webhook_event = webhook_payload.get("webhookEvent")
            issue_key = webhook_payload.get("issue", {}).get("key")
            issue_fields = webhook_payload.get("issue", {}).get("fields", {})

            logger.info(f"Received Jira webhook: {webhook_event} for {issue_key}")

            # Handle different webhook events
            if webhook_event == "jira:issue_updated":
                return self._handle_issue_updated(issue_key, issue_fields, webhook_payload)

            elif webhook_event == "comment_created":
                return self._handle_comment_created(issue_key, webhook_payload.get("comment", {}))

            elif webhook_event == "jira:issue_deleted":
                return self._handle_issue_deleted(issue_key)

            else:
                logger.info(f"Unhandled webhook event: {webhook_event}")
                return {"success": True, "action": "ignored", "event": webhook_event}

        except Exception as e:
            logger.error(f"Failed to process Jira webhook: {e}")
            return {"success": False, "error": str(e)}

    def _handle_issue_updated(self, issue_key: str, fields: Dict[str, Any], payload: Dict[str, Any]) -> dict:
        """Handle Jira issue update webhook."""
        # Check if status changed
        changelog = payload.get("changelog", {})
        status_change = None

        for item in changelog.get("items", []):
            if item.get("field") == "status":
                status_change = {
                    "from": item.get("fromString"),
                    "to": item.get("toString")
                }
                break

        if status_change:
            logger.info(f"Jira {issue_key} status changed: {status_change['from']} → {status_change['to']}")

            # Update corresponding CARL record
            finding = self._get_finding_by_jira_key(issue_key)
            if finding:
                # Map Jira status to CARL status
                carl_status = self._map_jira_status_to_carl(status_change["to"])

                self._update_finding_in_db(finding["finding_id"], {
                    "status": carl_status,
                    "jira_last_updated": datetime.utcnow().isoformat(),
                    "last_status_change": datetime.utcnow().isoformat()
                }, account_id=finding.get("account_id"))

                return {
                    "success": True,
                    "action": "status_synced",
                    "finding_id": finding["finding_id"],
                    "new_status": carl_status
                }

        return {"success": True, "action": "no_sync_needed"}

    def _handle_comment_created(self, issue_key: str, comment: Dict[str, Any]) -> dict:
        """Handle new Jira comment webhook."""
        comment_body = comment.get("body")
        author = comment.get("author", {}).get("displayName")

        logger.info(f"New comment on {issue_key} by {author}")

        # Could post to Slack thread or store in DynamoDB
        # For now, just log
        return {"success": True, "action": "comment_logged"}

    def _handle_issue_deleted(self, issue_key: str) -> dict:
        """Handle Jira issue deletion webhook."""
        logger.warning(f"Jira issue {issue_key} was deleted")

        # Find and update CARL record
        finding = self._get_finding_by_jira_key(issue_key)
        if finding:
            self._update_finding_in_db(finding["finding_id"], {
                "jira_ticket_deleted": True,
                "jira_deleted_at": datetime.utcnow().isoformat()
            }, account_id=finding.get("account_id"))

        return {"success": True, "action": "marked_deleted"}

    def _get_finding_from_db(self, finding_id: str, account_id: str = None) -> Optional[dict]:
        """Get finding from DynamoDB."""
        try:
            # Use FindingsService which handles the pk/sk composite key correctly
            return self.findings_service.get_finding(finding_id, account_id)
        except Exception as e:
            logger.error(f"Failed to get finding {finding_id} from DB: {e}")
            return None

    def _get_finding_by_jira_key(self, jira_key: str) -> Optional[dict]:
        """Get finding by Jira ticket key (requires GSI)."""
        try:
            # NOTE: This requires a Global Secondary Index on jira_ticket_id
            response = self.findings_table.query(
                IndexName="jira_ticket_id-index",
                KeyConditionExpression="jira_ticket_id = :jira_key",
                ExpressionAttributeValues={":jira_key": jira_key}
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except Exception as e:
            logger.error(f"Failed to query finding by Jira key {jira_key}: {e}")
            return None

    def _update_finding_in_db(self, finding_id: str, updates: Dict[str, Any], account_id: str = None):
        """Update finding in DynamoDB."""
        try:
            # Use FindingsService which handles the pk/sk composite key correctly
            self.findings_service.update_finding(
                finding_id=finding_id,
                account_id=account_id,
                **updates
            )
            logger.debug(f"Updated finding {finding_id} in DB")

        except Exception as e:
            logger.error(f"Failed to update finding {finding_id} in DB: {e}")

    def _map_jira_status_to_carl(self, jira_status: str) -> str:
        """Map Jira status to CARL status."""
        mapping = {
            "Open": "NEW",
            "In Progress": "IN_PROGRESS",
            "Resolved": "RESOLVED",
            "Closed": "SUPPRESSED",
            "Won't Fix": "SUPPRESSED",
            "Acknowledged": "NOTIFIED"
        }
        return mapping.get(jira_status, "NEW")

    def test_connection(self) -> dict:
        """Test Jira connection and permissions."""
        try:
            # Try to get CARLSEC project
            response = self.jira._request("GET", f"/rest/api/3/project/CARLSEC")

            return {
                "success": True,
                "message": "Jira connection successful",
                "project": response.get("name")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
