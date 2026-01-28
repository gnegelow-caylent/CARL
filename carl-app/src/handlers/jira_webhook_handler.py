"""
CARL Jira Webhook Handler Lambda Function

Processes incoming webhooks from Jira for bi-directional sync (Jira → CARL).

Webhook Events Handled:
- jira:issue_updated (status changes, field updates)
- comment_created (new comments on tickets)
- jira:issue_deleted (ticket deletions)

AWS Resources:
- Lambda function: carl-dev-jira-webhook
- API Gateway: POST /jira/webhook
- DynamoDB: carl-findings, carl-risk-exceptions, carl-drift-detections
"""

import json
import hmac
import hashlib
import os
from typing import Any, Dict
from services.jira_security_sync import JiraSecuritySync
from utils.logger import get_logger

logger = get_logger(__name__)

# Environment variables
JIRA_WEBHOOK_SECRET = os.environ.get("JIRA_WEBHOOK_SECRET", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for Jira webhooks.

    Event structure:
    {
        "rawPath": "/jira/webhook",
        "requestContext": {...},
        "headers": {...},
        "body": "{...}"  # JSON string
    }
    """
    logger.info("Received Jira webhook", extra={"path": event.get("rawPath", "")})

    # Health check endpoint
    if event.get("rawPath") == "/jira/health" or event.get("path") == "/jira/health":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "healthy",
                "service": "carl-jira-webhook",
                "version": "1.0"
            })
        }

    try:
        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            payload = json.loads(body)
        else:
            payload = body

        # Verify webhook signature (if configured)
        if JIRA_WEBHOOK_SECRET:
            if not verify_webhook_signature(event, payload):
                logger.warning("Invalid webhook signature")
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "Invalid signature"})
                }

        # Process webhook
        jira_sync = JiraSecuritySync()
        result = jira_sync.handle_jira_webhook(payload)

        # Log result
        if result["success"]:
            logger.info(f"Webhook processed successfully: {result.get('action')}")
        else:
            logger.error(f"Webhook processing failed: {result.get('error')}")

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result)
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook body: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON"})
        }

    except Exception as e:
        logger.exception("Error processing Jira webhook")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def verify_webhook_signature(event: Dict[str, Any], payload: Dict[str, Any]) -> bool:
    """
    Verify Jira webhook signature for security.

    Jira sends webhooks with a signature in the header:
    X-Hub-Signature: sha256=<hmac>

    We compute HMAC of the payload and compare.
    """
    try:
        # Get signature from headers
        headers = event.get("headers", {})
        # Headers may be lowercase
        signature_header = (
            headers.get("X-Hub-Signature") or
            headers.get("x-hub-signature") or
            ""
        )

        if not signature_header:
            logger.warning("No signature header found in webhook")
            # If no secret configured, allow (for testing)
            return not JIRA_WEBHOOK_SECRET

        # Parse signature (format: "sha256=<hash>")
        if "=" not in signature_header:
            logger.warning("Invalid signature format")
            return False

        algorithm, provided_signature = signature_header.split("=", 1)

        # Compute expected signature
        body = event.get("body", "")
        if isinstance(body, dict):
            body = json.dumps(body)

        expected_signature = hmac.new(
            JIRA_WEBHOOK_SECRET.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures (constant-time comparison)
        return hmac.compare_digest(expected_signature, provided_signature)

    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


def get_webhook_event_type(payload: Dict[str, Any]) -> str:
    """Extract webhook event type from payload."""
    return payload.get("webhookEvent", "unknown")


def get_issue_key(payload: Dict[str, Any]) -> str:
    """Extract Jira issue key from payload."""
    issue = payload.get("issue", {})
    return issue.get("key", "")


def get_issue_status(payload: Dict[str, Any]) -> str:
    """Extract current issue status from payload."""
    issue = payload.get("issue", {})
    fields = issue.get("fields", {})
    status = fields.get("status", {})
    return status.get("name", "")


# Optional: CloudWatch metrics helper
def publish_metric(metric_name: str, value: float, unit: str = "Count"):
    """Publish custom CloudWatch metric."""
    try:
        import boto3
        cloudwatch = boto3.client("cloudwatch")

        cloudwatch.put_metric_data(
            Namespace=f"CARL/{ENVIRONMENT}",
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to publish metric {metric_name}: {e}")
