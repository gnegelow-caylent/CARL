"""
Slack Service for CARL notifications and interactions.
"""

from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from utils.logger import get_logger

logger = get_logger(__name__)


class SlackService:
    """Service for interacting with Slack."""

    def __init__(self, token: str):
        self.client = WebClient(token=token)

    def post_message(
        self,
        channel: str,
        text: str = "",
        blocks: list[dict] | None = None,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Post a message to a Slack channel."""
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks,
                thread_ts=thread_ts,
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            raise

    def update_message(
        self,
        channel: str,
        ts: str,
        text: str = "",
        blocks: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Update an existing Slack message."""
        try:
            response = self.client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=blocks,
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            raise

    def post_ephemeral(
        self,
        channel: str,
        user: str,
        text: str = "",
        blocks: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Post an ephemeral message visible only to one user."""
        try:
            response = self.client.chat_postEphemeral(
                channel=channel,
                user=user,
                text=text,
                blocks=blocks,
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            raise

    def get_user_info(self, user_id: str) -> dict[str, Any]:
        """Get information about a Slack user."""
        try:
            response = self.client.users_info(user=user_id)
            return response.data.get("user", {})
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            raise

    def open_modal(
        self,
        trigger_id: str,
        view: dict[str, Any],
    ) -> dict[str, Any]:
        """Open a modal dialog."""
        try:
            response = self.client.views_open(
                trigger_id=trigger_id,
                view=view,
            )
            return response.data
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            raise

    def upload_file(
        self,
        channels: list[str] | str,
        file_path: str | None = None,
        file_content: bytes | str | None = None,
        content: str | None = None,  # Deprecated: use file_content
        filename: str = "file.txt",
        title: str | None = None,
        initial_comment: str | None = None,
    ) -> dict[str, Any]:
        """
        Upload a file to Slack using files_upload_v2 API.

        Args:
            channels: Channel ID(s) to upload to
            file_path: Path to file on disk
            file_content: File content as bytes or string (for PDFs, images, etc.)
            content: Deprecated alias for file_content (string only)
            filename: Name for the uploaded file
            title: Title for the file
            initial_comment: Message to post with the file
        """
        import tempfile
        import os

        try:
            # Normalize channels to list
            if isinstance(channels, str):
                channels = [channels]

            # files_upload_v2 expects channel_id (singular), not channels
            # Use the first channel if multiple are provided
            channel_id = channels[0] if channels else None
            if not channel_id:
                raise ValueError("No channel specified for file upload")

            temp_file = None

            # For binary content (like PDFs), write to temp file first
            if file_content is not None and isinstance(file_content, bytes):
                # Create temp file
                fd, temp_file = tempfile.mkstemp(suffix=f"_{filename}")
                try:
                    os.write(fd, file_content)
                    os.close(fd)
                    file_path = temp_file
                except Exception as e:
                    os.close(fd)
                    if temp_file:
                        os.unlink(temp_file)
                    raise

            kwargs: dict[str, Any] = {
                "channel": channel_id,  # Use 'channel' not 'channel_id' for files_upload_v2
                "filename": filename,
            }

            if file_path:
                kwargs["file"] = file_path
            elif file_content is not None and isinstance(file_content, str):
                kwargs["content"] = file_content
            elif content is not None:
                # Backward compatibility
                kwargs["content"] = content
            else:
                raise ValueError("Must provide either file_path, file_content, or content")

            if title:
                kwargs["title"] = title
            if initial_comment:
                kwargs["initial_comment"] = initial_comment

            response = self.client.files_upload_v2(**kwargs)

            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")

            return response.data
        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            raise


def build_finding_notification_blocks(finding: dict) -> list[dict]:
    """Build Slack blocks for a finding notification."""
    severity_emoji = {
        "CRITICAL": ":rotating_light:",
        "HIGH": ":warning:",
        "MEDIUM": ":large_orange_diamond:",
        "LOW": ":large_blue_diamond:",
        "INFORMATIONAL": ":information_source:",
    }

    severity = finding.get("severity", "MEDIUM")
    emoji = severity_emoji.get(severity, ":question:")

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {severity} Finding Detected",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Source:* {finding.get('source', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Account:* {finding.get('account_id', 'N/A')}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{finding.get('title', 'Unknown Finding')}*\n{finding.get('description', '')[:500]}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Resource:* `{finding.get('resource_id', 'N/A')}`",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"SOC 2 Controls: {', '.join(finding.get('control_ids', ['N/A']))}",
                }
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Details"},
                    "action_id": f"finding_details_{finding.get('id', '')}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Remediate"},
                    "style": "primary",
                    "action_id": f"request_remediation_{finding.get('id', '')}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Suppress"},
                    "action_id": f"suppress_finding_{finding.get('id', '')}",
                },
            ],
        },
    ]


def build_remediation_approval_blocks(
    finding: dict, remediation: dict
) -> list[dict]:
    """Build Slack blocks for remediation approval request."""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":wrench: Remediation Approval Required",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Finding:* {finding.get('title', 'Unknown')}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Resource:* `{finding.get('resource_id', 'N/A')}`",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Proposed Action:*\n{remediation.get('description', 'No description')}",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Risk Level:* {remediation.get('risk_level', 'Medium')}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Rollback:* {'Available' if remediation.get('rollback_available') else 'Not Available'}",
                },
            ],
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": f"approve_remediation_{remediation.get('id', '')}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Deny"},
                    "style": "danger",
                    "action_id": f"deny_remediation_{remediation.get('id', '')}",
                },
            ],
        },
    ]
