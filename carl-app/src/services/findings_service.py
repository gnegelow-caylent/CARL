"""
Findings Service for CARL.
"""

import os
from datetime import datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from models.finding import Finding, FindingSeverity, FindingStatus
from utils.logger import get_logger

logger = get_logger(__name__)

FINDINGS_TABLE = os.environ.get("FINDINGS_TABLE", "carl-findings-dev")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


class FindingsService:
    """Service for managing findings."""

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        self.table = self.dynamodb.Table(FINDINGS_TABLE)

    def store_finding(self, finding: Finding) -> None:
        """Store a finding in DynamoDB."""
        try:
            item = finding.to_dynamodb_item()
            self.table.put_item(Item=item)
            logger.info(f"Stored finding: {finding.id}")
        except Exception as e:
            logger.exception(f"Error storing finding: {finding.id}")
            raise

    def get_finding(self, finding_id: str, account_id: str | None = None) -> dict | None:
        """Get a finding by ID."""
        try:
            # If we don't have account_id, we need to scan (less efficient)
            if account_id:
                # Use Query instead of GetItem since we have composite keys (pk + sk)
                # We know the pk but not the exact sk (which includes timestamp)
                response = self.table.query(
                    KeyConditionExpression=Key("pk").eq(f"ACCOUNT#{account_id}#FINDING#{finding_id}"),
                    Limit=1
                )
                items = response.get("Items", [])
                item = items[0] if items else None
            else:
                # Query by finding_id across accounts
                response = self.table.scan(
                    FilterExpression="finding_id = :fid",
                    ExpressionAttributeValues={":fid": finding_id},
                    Limit=1,
                )
                items = response.get("Items", [])
                item = items[0] if items else None

            if item:
                return Finding.from_dynamodb_item(item).to_dict()
            return None

        except Exception as e:
            logger.exception(f"Error getting finding: {finding_id}")
            return None

    def get_recent_findings(
        self,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get recent findings, optionally filtered by severity."""
        try:
            if severity:
                # Use GSI for severity
                response = self.table.query(
                    IndexName="severity-timestamp-index",
                    KeyConditionExpression=Key("severity").eq(severity),
                    ScanIndexForward=False,  # Most recent first
                    Limit=limit,
                )
            else:
                # Scan recent items
                response = self.table.scan(
                    Limit=limit,
                )

            items = response.get("Items", [])

            # Filter by status if provided
            if status:
                items = [i for i in items if i.get("status") == status]

            # Convert to dicts
            return [Finding.from_dynamodb_item(item).to_dict() for item in items]

        except Exception as e:
            logger.exception("Error getting recent findings")
            return []

    def get_findings_by_control(
        self, control_id: str, status: str | None = None
    ) -> list[dict]:
        """Get findings mapped to a specific SOC 2 control."""
        try:
            response = self.table.query(
                IndexName="control-status-index",
                KeyConditionExpression=Key("control_id").eq(control_id),
            )

            items = response.get("Items", [])

            if status:
                items = [i for i in items if i.get("status") == status]

            return [Finding.from_dynamodb_item(item).to_dict() for item in items]

        except Exception as e:
            logger.exception(f"Error getting findings for control: {control_id}")
            return []

    def get_compliance_summary(self, account_id: str | None = None) -> dict[str, Any]:
        """Get compliance summary statistics."""
        try:
            # Scan all findings or filter by account
            scan_kwargs: dict[str, Any] = {}
            if account_id:
                scan_kwargs["FilterExpression"] = "account_id = :aid"
                scan_kwargs["ExpressionAttributeValues"] = {":aid": account_id}

            response = self.table.scan(**scan_kwargs)
            items = response.get("Items", [])

            # Continue scanning if there are more items
            while "LastEvaluatedKey" in response:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                response = self.table.scan(**scan_kwargs)
                items.extend(response.get("Items", []))

            # Filter to open findings only
            open_statuses = [FindingStatus.NEW.value, FindingStatus.IN_PROGRESS.value]
            open_findings = [i for i in items if i.get("status") in open_statuses]

            # Count by severity
            summary = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "informational": 0,
                "total": len(open_findings),
                "last_updated": datetime.utcnow().isoformat(),
            }

            for finding in open_findings:
                severity = finding.get("severity", "MEDIUM").lower()
                if severity in summary:
                    summary[severity] += 1

            return summary

        except Exception as e:
            logger.exception("Error getting compliance summary")
            return {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "informational": 0,
                "total": 0,
                "error": str(e),
            }

    def update_finding(
        self,
        finding_id: str,
        account_id: str,
        **updates
    ) -> bool:
        """Update arbitrary fields of a finding."""
        try:
            if not updates:
                return True

            # First, query to get the existing item and its sk
            # (Table has composite keys: pk + sk)
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(f"ACCOUNT#{account_id}#FINDING#{finding_id}"),
                Limit=1
            )
            items = response.get("Items", [])
            if not items:
                logger.warning(f"Finding {finding_id} not found for update")
                return False

            item = items[0]
            pk = item["pk"]
            sk = item["sk"]

            # Build update expression
            update_expr_parts = []
            expr_values = {}
            expr_names = {}

            # Always update timestamp
            updates["updated_at"] = datetime.utcnow().isoformat()

            for key, value in updates.items():
                # Use expression attribute names for reserved words
                attr_name = f"#{key}"
                attr_value = f":{key}"
                update_expr_parts.append(f"{attr_name} = {attr_value}")
                expr_values[attr_value] = value
                expr_names[attr_name] = key

            update_expr = "SET " + ", ".join(update_expr_parts)

            # Update using both pk and sk
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names,
            )

            logger.info(f"Updated finding: {finding_id}")
            return True

        except Exception as e:
            logger.exception(f"Error updating finding: {finding_id}")
            return False

    def update_finding_status(
        self,
        finding_id: str,
        account_id: str,
        status: FindingStatus,
        remediation_id: str | None = None,
    ) -> bool:
        """Update the status of a finding."""
        try:
            # First, query to get the existing item and its sk
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(f"ACCOUNT#{account_id}#FINDING#{finding_id}"),
                Limit=1
            )
            items = response.get("Items", [])
            if not items:
                logger.warning(f"Finding {finding_id} not found for status update")
                return False

            item = items[0]
            pk = item["pk"]
            sk = item["sk"]

            update_expr = "SET #status = :status, updated_at = :updated"
            expr_values: dict[str, Any] = {
                ":status": status.value,
                ":updated": datetime.utcnow().isoformat(),
            }
            expr_names = {"#status": "status"}

            if remediation_id:
                update_expr += ", remediation_id = :rid"
                expr_values[":rid"] = remediation_id

            # Update using both pk and sk
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=expr_names,
            )

            logger.info(f"Updated finding {finding_id} status to {status.value}")
            return True

        except Exception as e:
            logger.exception(f"Error updating finding status: {finding_id}")
            return False

    def suppress_finding(
        self,
        finding_id: str,
        account_id: str,
        reason: str,
        suppressed_by: str,
    ) -> bool:
        """Suppress a finding."""
        try:
            # First, query to get the existing item and its sk
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(f"ACCOUNT#{account_id}#FINDING#{finding_id}"),
                Limit=1
            )
            items = response.get("Items", [])
            if not items:
                logger.warning(f"Finding {finding_id} not found for suppression")
                return False

            item = items[0]
            pk = item["pk"]
            sk = item["sk"]

            # Update using both pk and sk
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression=(
                    "SET #status = :status, updated_at = :updated, "
                    "suppression_reason = :reason, suppressed_by = :by"
                ),
                ExpressionAttributeValues={
                    ":status": FindingStatus.SUPPRESSED.value,
                    ":updated": datetime.utcnow().isoformat(),
                    ":reason": reason,
                    ":by": suppressed_by,
                },
                ExpressionAttributeNames={"#status": "status"},
            )

            logger.info(f"Suppressed finding {finding_id}")
            return True

        except Exception as e:
            logger.exception(f"Error suppressing finding: {finding_id}")
            return False

    def store_scanner_findings(self, scan_results: dict[str, Any], region: str = "us-east-1") -> list[str]:
        """
        Convert AWSScanner results to Finding objects and store in DynamoDB.

        Args:
            scan_results: Results from AWSScanner.scan_environment()
            region: AWS region where scan was performed

        Returns:
            List of finding IDs that were stored
        """
        from models.finding import FindingSource
        import hashlib

        stored_finding_ids = []
        account_id = scan_results.get("account_id", "unknown")

        try:
            # Iterate through all scan categories
            for category, results in scan_results.items():
                if category == "account_id":
                    continue

                if not isinstance(results, dict):
                    continue

                issues = results.get("issues", [])

                for issue in issues:
                    # Generate unique finding ID from content
                    finding_content = f"{category}:{issue['finding']}:{account_id}"
                    finding_id = f"scanner-{hashlib.md5(finding_content.encode()).hexdigest()[:12]}"

                    # Check if finding already exists
                    existing = self.get_finding(finding_id, account_id)
                    if existing:
                        # Skip if already stored
                        logger.debug(f"Finding {finding_id} already exists, skipping")
                        continue

                    # Create Finding object
                    finding = Finding(
                        id=finding_id,
                        source=FindingSource.CARL_SCANNER,
                        severity=FindingSeverity(issue["severity"]),
                        title=issue["finding"],
                        description=f"Category: {category}\n{issue['finding']}",
                        resource_type=category,
                        resource_id=account_id,  # Scanner findings are account-level
                        account_id=account_id,
                        region=region,
                        control_ids=[],  # Can be mapped later
                        status=FindingStatus.NEW,
                        remediation_steps=issue.get("recommendation", ""),
                        raw_finding=issue
                    )

                    # Store in DynamoDB
                    self.store_finding(finding)
                    stored_finding_ids.append(finding_id)
                    logger.info(f"Stored scanner finding: {finding_id} - {issue['finding']}")

            logger.info(f"Stored {len(stored_finding_ids)} new scanner findings")
            return stored_finding_ids

        except Exception as e:
            logger.exception("Error storing scanner findings")
            return stored_finding_ids
