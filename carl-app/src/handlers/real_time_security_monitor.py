"""
Real-Time Security Monitor for CARL.

Receives CloudTrail events from EventBridge and instantly alerts on security-relevant changes.

Architecture:
  CloudTrail → EventBridge → Lambda (this handler) → Slack

Detects:
- S3 bucket made public
- Security group opened to 0.0.0.0/0
- IAM policy changes
- Encryption disabled
- CloudTrail stopped
- GuardDuty disabled
- Security Hub disabled
- MFA removed

Latency: < 60 seconds from AWS change to Slack notification
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import boto3
from dataclasses import dataclass

from utils.logger import get_logger
from services.slack_service import SlackService
from utils.aws_client import get_parameter

logger = get_logger(__name__)


@dataclass
class SecurityEvent:
    """A security-relevant AWS change detected in real-time."""
    event_id: str
    event_time: str
    event_name: str
    service: str
    resource_type: str
    resource_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    title: str
    description: str
    user: str
    source_ip: str
    user_agent: str
    region: str
    account_id: str
    raw_event: dict


class RealTimeSecurityMonitor:
    """
    Real-time security change detector.

    Analyzes CloudTrail events as they occur and alerts on security violations.
    """

    def __init__(self):
        self.slack = SlackService()
        self.sns = boto3.client('sns')
        self.alert_topic = os.environ.get('SECURITY_ALERT_TOPIC')

    def process_cloudtrail_event(self, event: Dict[str, Any]) -> Optional[SecurityEvent]:
        """
        Process a CloudTrail event and determine if it's security-relevant.

        Args:
            event: CloudTrail event from EventBridge

        Returns:
            SecurityEvent if security-relevant, None otherwise
        """
        detail = event.get('detail', {})

        event_name = detail.get('eventName', '')
        event_source = detail.get('eventSource', '').replace('.amazonaws.com', '')
        event_time = detail.get('eventTime', '')

        user_identity = detail.get('userIdentity', {})
        user_name = user_identity.get('principalId', 'Unknown')
        if 'userName' in user_identity:
            user_name = user_identity['userName']
        elif 'sessionContext' in user_identity and 'sessionIssuer' in user_identity['sessionContext']:
            user_name = user_identity['sessionContext']['sessionIssuer'].get('userName', user_name)

        source_ip = detail.get('sourceIPAddress', 'Unknown')
        user_agent = detail.get('userAgent', 'Unknown')
        region = detail.get('awsRegion', 'Unknown')
        account_id = detail.get('recipientAccountId', event.get('account', 'Unknown'))

        # Check if this event is security-relevant
        security_issue = self._analyze_security_impact(detail)

        if not security_issue:
            return None

        # Create security event
        return SecurityEvent(
            event_id=detail.get('eventID', 'unknown'),
            event_time=event_time,
            event_name=event_name,
            service=event_source,
            resource_type=security_issue['resource_type'],
            resource_id=security_issue['resource_id'],
            severity=security_issue['severity'],
            title=security_issue['title'],
            description=security_issue['description'],
            user=user_name,
            source_ip=source_ip,
            user_agent=user_agent,
            region=region,
            account_id=account_id,
            raw_event=detail
        )

    def _analyze_security_impact(self, event_detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze CloudTrail event to determine security impact.

        Returns:
            Dict with security issue details if relevant, None otherwise
        """
        event_name = event_detail.get('eventName', '')
        event_source = event_detail.get('eventSource', '').replace('.amazonaws.com', '')
        request_params = event_detail.get('requestParameters', {})
        response_elements = event_detail.get('responseElements', {})

        # S3 Security Issues
        if event_source == 's3':
            if event_name == 'PutBucketPublicAccessBlock':
                # Check if public access was ENABLED or DISABLED
                config = request_params.get('PublicAccessBlockConfiguration', {})
                if not all([
                    config.get('BlockPublicAcls', False),
                    config.get('IgnorePublicAcls', False),
                    config.get('BlockPublicPolicy', False),
                    config.get('RestrictPublicBuckets', False)
                ]):
                    return {
                        'severity': 'CRITICAL',
                        'resource_type': 's3_bucket',
                        'resource_id': request_params.get('bucketName', 'Unknown'),
                        'title': f"S3 Bucket Public Access Enabled",
                        'description': f"Public access block was weakened on bucket {request_params.get('bucketName', 'Unknown')}"
                    }

            elif event_name == 'DeleteBucketEncryption':
                return {
                    'severity': 'HIGH',
                    'resource_type': 's3_bucket',
                    'resource_id': request_params.get('bucketName', 'Unknown'),
                    'title': "S3 Bucket Encryption Disabled",
                    'description': f"Default encryption was removed from bucket {request_params.get('bucketName', 'Unknown')}"
                }

            elif event_name == 'PutBucketPolicy':
                # TODO: Parse policy to check for public statements
                return {
                    'severity': 'HIGH',
                    'resource_type': 's3_bucket',
                    'resource_id': request_params.get('bucketName', 'Unknown'),
                    'title': "S3 Bucket Policy Modified",
                    'description': f"Bucket policy changed on {request_params.get('bucketName', 'Unknown')} - review for public access"
                }

        # EC2 Security Group Changes
        elif event_source == 'ec2':
            if event_name == 'AuthorizeSecurityGroupIngress':
                ip_permissions = request_params.get('ipPermissions', {}).get('items', [])
                for permission in ip_permissions:
                    ip_ranges = permission.get('ipRanges', {}).get('items', [])
                    for ip_range in ip_ranges:
                        if ip_range.get('cidrIp') == '0.0.0.0/0':
                            from_port = permission.get('fromPort', 'any')
                            to_port = permission.get('toPort', 'any')
                            return {
                                'severity': 'CRITICAL',
                                'resource_type': 'security_group',
                                'resource_id': request_params.get('groupId', 'Unknown'),
                                'title': "Security Group Opened to Internet",
                                'description': f"Security group {request_params.get('groupId', 'Unknown')} allows 0.0.0.0/0 on ports {from_port}-{to_port}"
                            }

        # IAM Changes
        elif event_source == 'iam':
            if event_name == 'PutUserPolicy':
                return {
                    'severity': 'HIGH',
                    'resource_type': 'iam_user',
                    'resource_id': request_params.get('userName', 'Unknown'),
                    'title': "IAM Inline Policy Added",
                    'description': f"Inline policy {request_params.get('policyName', 'Unknown')} added to user {request_params.get('userName', 'Unknown')}"
                }

            elif event_name == 'AttachUserPolicy':
                return {
                    'severity': 'MEDIUM',
                    'resource_type': 'iam_user',
                    'resource_id': request_params.get('userName', 'Unknown'),
                    'title': "IAM Policy Attached",
                    'description': f"Policy {request_params.get('policyArn', 'Unknown')} attached to user {request_params.get('userName', 'Unknown')}"
                }

            elif event_name == 'CreateAccessKey':
                return {
                    'severity': 'MEDIUM',
                    'resource_type': 'iam_user',
                    'resource_id': request_params.get('userName', 'Unknown'),
                    'title': "IAM Access Key Created",
                    'description': f"New access key created for user {request_params.get('userName', 'Unknown')}"
                }

            elif event_name == 'DeleteAccountPasswordPolicy':
                return {
                    'severity': 'HIGH',
                    'resource_type': 'iam_password_policy',
                    'resource_id': 'account',
                    'title': "IAM Password Policy Deleted",
                    'description': "Account password policy was deleted - users can now use weak passwords"
                }

            elif event_name == 'DeactivateMFADevice':
                return {
                    'severity': 'HIGH',
                    'resource_type': 'iam_user',
                    'resource_id': request_params.get('userName', 'Unknown'),
                    'title': "MFA Device Deactivated",
                    'description': f"MFA was removed from user {request_params.get('userName', 'Unknown')}"
                }

        # CloudTrail Changes
        elif event_source == 'cloudtrail':
            if event_name == 'StopLogging':
                return {
                    'severity': 'CRITICAL',
                    'resource_type': 'cloudtrail',
                    'resource_id': request_params.get('name', 'Unknown'),
                    'title': "CloudTrail Logging Stopped",
                    'description': f"CloudTrail {request_params.get('name', 'Unknown')} logging was disabled - audit trail stopped"
                }

            elif event_name == 'DeleteTrail':
                return {
                    'severity': 'CRITICAL',
                    'resource_type': 'cloudtrail',
                    'resource_id': request_params.get('name', 'Unknown'),
                    'title': "CloudTrail Deleted",
                    'description': f"CloudTrail {request_params.get('name', 'Unknown')} was permanently deleted"
                }

        # GuardDuty Changes
        elif event_source == 'guardduty':
            if event_name == 'DeleteDetector':
                return {
                    'severity': 'CRITICAL',
                    'resource_type': 'guardduty',
                    'resource_id': request_params.get('detectorId', 'Unknown'),
                    'title': "GuardDuty Disabled",
                    'description': f"GuardDuty detector {request_params.get('detectorId', 'Unknown')} was deleted - threat detection stopped"
                }

        # Security Hub Changes
        elif event_source == 'securityhub':
            if event_name == 'DisableSecurityHub':
                return {
                    'severity': 'CRITICAL',
                    'resource_type': 'securityhub',
                    'resource_id': 'account',
                    'title': "Security Hub Disabled",
                    'description': "Security Hub was disabled - centralized security findings stopped"
                }

        # RDS Changes
        elif event_source == 'rds':
            if event_name == 'ModifyDBInstance':
                if request_params.get('publiclyAccessible'):
                    return {
                        'severity': 'CRITICAL',
                        'resource_type': 'rds_instance',
                        'resource_id': request_params.get('dBInstanceIdentifier', 'Unknown'),
                        'title': "RDS Database Made Public",
                        'description': f"Database {request_params.get('dBInstanceIdentifier', 'Unknown')} is now publicly accessible from the internet"
                    }

        # KMS Changes
        elif event_source == 'kms':
            if event_name == 'DisableKey':
                return {
                    'severity': 'HIGH',
                    'resource_type': 'kms_key',
                    'resource_id': request_params.get('keyId', 'Unknown'),
                    'title': "KMS Key Disabled",
                    'description': f"KMS key {request_params.get('keyId', 'Unknown')} was disabled - encrypted data may become inaccessible"
                }

            elif event_name == 'ScheduleKeyDeletion':
                return {
                    'severity': 'HIGH',
                    'resource_type': 'kms_key',
                    'resource_id': request_params.get('keyId', 'Unknown'),
                    'title': "KMS Key Scheduled for Deletion",
                    'description': f"KMS key {request_params.get('keyId', 'Unknown')} scheduled for deletion - encrypted data will become inaccessible"
                }

        return None

    def alert_to_slack(self, security_event: SecurityEvent) -> None:
        """
        Send security alert to Slack.

        Args:
            security_event: Detected security event
        """
        severity_emoji = {
            'CRITICAL': '🚨',
            'HIGH': '🟠',
            'MEDIUM': '🟡',
            'LOW': '🔵'
        }

        emoji = severity_emoji.get(security_event.severity, '⚠️')

        # Get alert channel from environment or use default
        channel = os.environ.get('SECURITY_ALERT_CHANNEL', '#carl-security-alerts')

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Security Alert: {security_event.title}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:* {security_event.severity}"},
                    {"type": "mrkdwn", "text": f"*Resource:* {security_event.resource_id}"},
                    {"type": "mrkdwn", "text": f"*Service:* {security_event.service}"},
                    {"type": "mrkdwn", "text": f"*User:* {security_event.user}"},
                    {"type": "mrkdwn", "text": f"*Region:* {security_event.region}"},
                    {"type": "mrkdwn", "text": f"*Time:* {security_event.event_time}"},
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Description:*\n{security_event.description}"}
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Source IP: {security_event.source_ip} | Event ID: {security_event.event_id}"}
                ]
            }
        ]

        try:
            self.slack.post_message(
                channel=channel,
                text=f"{emoji} {security_event.title}",
                blocks=blocks
            )
            logger.info(f"Sent security alert to Slack: {security_event.title}")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

            # Fallback to SNS if Slack fails
            if self.alert_topic:
                try:
                    self.sns.publish(
                        TopicArn=self.alert_topic,
                        Subject=f"[{security_event.severity}] {security_event.title}",
                        Message=json.dumps({
                            'severity': security_event.severity,
                            'title': security_event.title,
                            'description': security_event.description,
                            'resource_id': security_event.resource_id,
                            'user': security_event.user,
                            'event_time': security_event.event_time
                        }, indent=2)
                    )
                    logger.info(f"Sent security alert to SNS as fallback")
                except Exception as sns_error:
                    logger.error(f"Failed to send SNS alert: {sns_error}")


def lambda_handler(event, context):
    """
    Lambda handler for real-time security monitoring.

    Receives CloudTrail events from EventBridge and alerts on security violations.

    Args:
        event: EventBridge event containing CloudTrail detail
        context: Lambda context

    Returns:
        Response with processing status
    """
    logger.info(f"Processing CloudTrail event: {event.get('detail', {}).get('eventName', 'Unknown')}")

    try:
        monitor = RealTimeSecurityMonitor()

        # Process event
        security_event = monitor.process_cloudtrail_event(event)

        if security_event:
            logger.info(f"Security event detected: {security_event.title} (Severity: {security_event.severity})")

            # Alert to Slack
            monitor.alert_to_slack(security_event)

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Security alert sent',
                    'event_id': security_event.event_id,
                    'severity': security_event.severity,
                    'title': security_event.title
                })
            }
        else:
            logger.debug(f"Event {event.get('detail', {}).get('eventName', 'Unknown')} not security-relevant")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Event not security-relevant'})
            }

    except Exception as e:
        logger.exception("Error processing security event")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
