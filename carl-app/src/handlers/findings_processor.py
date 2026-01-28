"""
CARL Findings Processor Lambda Handler

Processes security findings from various AWS services and normalizes them.
"""

import json
import os
from datetime import datetime
from typing import Any

from models.finding import Finding, FindingSource, FindingSeverity
from services.findings_service import FindingsService
from services.slack_service import SlackService
from utils.aws_client import get_parameter
from utils.logger import get_logger
from utils.soc2_mappings import get_soc2_controls

logger = get_logger(__name__)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
SLACK_TOKEN_SECRET_ARN = os.environ.get("SLACK_TOKEN_SECRET_ARN", "")
NOTIFICATION_CHANNEL = os.environ.get("NOTIFICATION_CHANNEL", "")

# Lazy-loaded services
_findings_service: FindingsService | None = None
_slack_service: SlackService | None = None


def get_findings_service() -> FindingsService:
    """Get or create FindingsService instance."""
    global _findings_service
    if _findings_service is None:
        _findings_service = FindingsService()
    return _findings_service


def get_slack_service() -> SlackService | None:
    """Get or create SlackService instance."""
    global _slack_service
    if _slack_service is None and SLACK_TOKEN_SECRET_ARN:
        try:
            token = get_parameter(SLACK_TOKEN_SECRET_ARN)
            _slack_service = SlackService(token)
        except Exception as e:
            logger.warning(f"Could not initialize Slack service: {e}")
    return _slack_service


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Process security findings from EventBridge events.

    Supports findings from:
    - AWS Config (compliance changes)
    - Security Hub (imported findings)
    - GuardDuty (threat findings)
    - Inspector (vulnerability findings)
    - Macie (sensitive data findings)
    - IAM Access Analyzer (access findings)
    """
    logger.info("Processing finding event", extra={"source": event.get("source", "")})

    try:
        source = event.get("source", "")
        detail_type = event.get("detail-type", "")
        detail = event.get("detail", {})

        # Determine source and normalize
        if source == "aws.config":
            finding = normalize_config_finding(detail)
        elif source == "aws.securityhub":
            finding = normalize_security_hub_finding(detail)
        elif source == "aws.guardduty":
            finding = normalize_guardduty_finding(detail)
        elif source == "aws.inspector2":
            finding = normalize_inspector_finding(detail)
        elif source == "aws.macie":
            finding = normalize_macie_finding(detail)
        elif source == "aws.access-analyzer":
            finding = normalize_access_analyzer_finding(detail)
        else:
            logger.warning(f"Unknown finding source: {source}")
            return {"statusCode": 200, "body": "Unknown source"}

        if finding is None:
            return {"statusCode": 200, "body": "Finding filtered out"}

        # Store finding
        findings_service = get_findings_service()
        findings_service.store_finding(finding)

        # Send notification for high-severity findings
        if finding.severity in [FindingSeverity.CRITICAL, FindingSeverity.HIGH]:
            send_notification(finding)

        return {"statusCode": 200, "body": "Finding processed"}

    except Exception as e:
        logger.exception("Error processing finding")
        return {"statusCode": 500, "body": str(e)}


def normalize_config_finding(detail: dict) -> Finding | None:
    """Normalize AWS Config compliance change to Finding."""
    compliance_type = detail.get("newEvaluationResult", {}).get("complianceType", "")

    # Only process non-compliant resources
    if compliance_type not in ["NON_COMPLIANT"]:
        return None

    config_rule = detail.get("configRuleName", "")
    resource_type = detail.get("resourceType", "")
    resource_id = detail.get("resourceId", "")

    return Finding(
        id=f"config-{config_rule}-{resource_id}",
        source=FindingSource.CONFIG,
        severity=map_config_severity(config_rule),
        title=f"Non-compliant: {config_rule}",
        description=f"Resource {resource_id} ({resource_type}) is non-compliant with rule {config_rule}",
        resource_type=resource_type,
        resource_id=resource_id,
        account_id=detail.get("awsAccountId", ""),
        region=detail.get("awsRegion", ""),
        control_ids=get_soc2_controls(config_rule),
        raw_finding=detail,
        created_at=datetime.utcnow(),
    )


def normalize_security_hub_finding(detail: dict) -> Finding | None:
    """Normalize Security Hub finding to Finding."""
    findings = detail.get("findings", [])
    if not findings:
        return None

    finding = findings[0]  # Process first finding

    # Skip resolved findings
    status = finding.get("Workflow", {}).get("Status", "")
    if status in ["RESOLVED", "SUPPRESSED"]:
        return None

    severity_label = finding.get("Severity", {}).get("Label", "MEDIUM")
    resources = finding.get("Resources", [{}])
    resource = resources[0] if resources else {}

    return Finding(
        id=finding.get("Id", ""),
        source=FindingSource.SECURITY_HUB,
        severity=map_severity_label(severity_label),
        title=finding.get("Title", ""),
        description=finding.get("Description", ""),
        resource_type=resource.get("Type", ""),
        resource_id=resource.get("Id", ""),
        account_id=finding.get("AwsAccountId", ""),
        region=finding.get("Region", ""),
        control_ids=extract_security_hub_controls(finding),
        remediation_steps=finding.get("Remediation", {}).get("Recommendation", {}).get("Text", ""),
        raw_finding=finding,
        created_at=datetime.utcnow(),
    )


def normalize_guardduty_finding(detail: dict) -> Finding | None:
    """Normalize GuardDuty finding to Finding."""
    severity = detail.get("severity", 0)

    resource = detail.get("resource", {})
    resource_type = resource.get("resourceType", "")

    # Extract resource ID based on type
    if resource_type == "Instance":
        resource_id = resource.get("instanceDetails", {}).get("instanceId", "")
    elif resource_type == "AccessKey":
        resource_id = resource.get("accessKeyDetails", {}).get("accessKeyId", "")
    else:
        resource_id = detail.get("id", "")

    return Finding(
        id=detail.get("id", ""),
        source=FindingSource.GUARDDUTY,
        severity=map_guardduty_severity(severity),
        title=detail.get("title", ""),
        description=detail.get("description", ""),
        resource_type=resource_type,
        resource_id=resource_id,
        account_id=detail.get("accountId", ""),
        region=detail.get("region", ""),
        control_ids=["CC7.2", "CC7.3"],  # Security monitoring controls
        raw_finding=detail,
        created_at=datetime.utcnow(),
    )


def normalize_inspector_finding(detail: dict) -> Finding | None:
    """Normalize Inspector finding to Finding."""
    severity = detail.get("severity", "MEDIUM")

    resources = detail.get("resources", [{}])
    resource = resources[0] if resources else {}

    return Finding(
        id=detail.get("findingArn", ""),
        source=FindingSource.INSPECTOR,
        severity=map_severity_label(severity),
        title=detail.get("title", ""),
        description=detail.get("description", ""),
        resource_type=resource.get("type", ""),
        resource_id=resource.get("id", ""),
        account_id=detail.get("awsAccountId", ""),
        region=detail.get("resources", [{}])[0].get("region", ""),
        control_ids=["CC7.1"],  # Vulnerability management
        remediation_steps=detail.get("remediation", {}).get("recommendation", {}).get("text", ""),
        raw_finding=detail,
        created_at=datetime.utcnow(),
    )


def normalize_macie_finding(detail: dict) -> Finding | None:
    """Normalize Macie finding to Finding."""
    severity = detail.get("severity", {}).get("description", "Medium")

    resources = detail.get("resourcesAffected", {})
    s3_bucket = resources.get("s3Bucket", {})
    s3_object = resources.get("s3Object", {})

    resource_id = s3_bucket.get("name", "")
    if s3_object.get("key"):
        resource_id = f"{resource_id}/{s3_object.get('key')}"

    return Finding(
        id=detail.get("id", ""),
        source=FindingSource.MACIE,
        severity=map_macie_severity(severity),
        title=detail.get("title", ""),
        description=detail.get("description", ""),
        resource_type="AWS::S3::Object",
        resource_id=resource_id,
        account_id=detail.get("accountId", ""),
        region=detail.get("region", ""),
        control_ids=["CC6.1", "CC6.5"],  # Data protection controls
        raw_finding=detail,
        created_at=datetime.utcnow(),
    )


def normalize_access_analyzer_finding(detail: dict) -> Finding | None:
    """Normalize IAM Access Analyzer finding to Finding."""
    status = detail.get("status", "")
    if status != "ACTIVE":
        return None

    resource_type = detail.get("resourceType", "")
    resource_arn = detail.get("resource", "")

    return Finding(
        id=detail.get("id", ""),
        source=FindingSource.ACCESS_ANALYZER,
        severity=FindingSeverity.HIGH,  # External access is always high
        title=f"External access detected: {resource_type}",
        description=f"Resource {resource_arn} is accessible from outside the account",
        resource_type=resource_type,
        resource_id=resource_arn,
        account_id=detail.get("resourceOwnerAccount", ""),
        region=detail.get("region", ""),
        control_ids=["CC6.1", "CC6.2", "CC6.3"],  # Access control
        raw_finding=detail,
        created_at=datetime.utcnow(),
    )


# Severity mapping functions
def map_config_severity(rule_name: str) -> FindingSeverity:
    """Map Config rule to severity based on rule type."""
    critical_rules = [
        "root-account-mfa-enabled",
        "iam-root-access-key-check",
        "s3-bucket-public-write-prohibited",
    ]
    high_rules = [
        "s3-bucket-public-read-prohibited",
        "encrypted-volumes",
        "rds-storage-encrypted",
        "restricted-ssh",
        "iam-user-mfa-enabled",
    ]

    rule_lower = rule_name.lower()
    if any(r in rule_lower for r in critical_rules):
        return FindingSeverity.CRITICAL
    elif any(r in rule_lower for r in high_rules):
        return FindingSeverity.HIGH
    else:
        return FindingSeverity.MEDIUM


def map_severity_label(label: str) -> FindingSeverity:
    """Map severity label to FindingSeverity."""
    mapping = {
        "CRITICAL": FindingSeverity.CRITICAL,
        "HIGH": FindingSeverity.HIGH,
        "MEDIUM": FindingSeverity.MEDIUM,
        "LOW": FindingSeverity.LOW,
        "INFORMATIONAL": FindingSeverity.INFORMATIONAL,
    }
    return mapping.get(label.upper(), FindingSeverity.MEDIUM)


def map_guardduty_severity(severity: float) -> FindingSeverity:
    """Map GuardDuty numeric severity to FindingSeverity."""
    if severity >= 7.0:
        return FindingSeverity.HIGH
    elif severity >= 4.0:
        return FindingSeverity.MEDIUM
    else:
        return FindingSeverity.LOW


def map_macie_severity(severity: str) -> FindingSeverity:
    """Map Macie severity to FindingSeverity."""
    mapping = {
        "High": FindingSeverity.HIGH,
        "Medium": FindingSeverity.MEDIUM,
        "Low": FindingSeverity.LOW,
    }
    return mapping.get(severity, FindingSeverity.MEDIUM)


def extract_security_hub_controls(finding: dict) -> list[str]:
    """Extract SOC 2 control IDs from Security Hub finding."""
    controls = []

    # Extract from compliance standards
    compliance = finding.get("Compliance", {})
    standards = compliance.get("AssociatedStandards", [])

    for standard in standards:
        standard_id = standard.get("StandardsId", "")
        if "soc2" in standard_id.lower():
            controls.extend(compliance.get("SecurityControlId", "").split(","))

    # Map from finding type if no explicit controls
    if not controls:
        finding_type = finding.get("Types", [""])[0]
        controls = get_soc2_controls(finding_type)

    return controls


def send_notification(finding: Finding) -> None:
    """Send Slack notification for high-severity finding."""
    slack = get_slack_service()
    if not slack or not NOTIFICATION_CHANNEL:
        return

    severity_emoji = {
        FindingSeverity.CRITICAL: ":rotating_light:",
        FindingSeverity.HIGH: ":warning:",
    }

    emoji = severity_emoji.get(finding.severity, ":information_source:")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {finding.severity.value} Finding Detected",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Source:* {finding.source.value}"},
                {"type": "mrkdwn", "text": f"*Account:* {finding.account_id}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{finding.title}*\n{finding.description[:500]}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Resource:* `{finding.resource_id}`",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Details"},
                    "action_id": f"finding_details_{finding.id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Remediate"},
                    "style": "primary",
                    "action_id": f"request_remediation_{finding.id}",
                },
            ],
        },
    ]

    try:
        slack.post_message(NOTIFICATION_CHANNEL, blocks=blocks)
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
