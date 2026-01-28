"""
Setup and configuration management service for CARL.

Handles workspace setup, configuration storage, and validation.
"""

import os
from datetime import datetime, timezone
from typing import Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

from utils.logger import get_logger

logger = get_logger(__name__)

# DynamoDB table name
SETUP_TABLE = os.environ.get("SETUP_TABLE_NAME", "carl-dev-setup-config")


class SetupService:
    """Service for managing CARL setup and configuration."""

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(SETUP_TABLE)

    def get_workspace_config(self, workspace_id: str) -> Optional[dict]:
        """
        Get configuration for a workspace.

        Returns:
            Configuration dict or None if not found
        """
        try:
            response = self.table.get_item(Key={"workspace_id": workspace_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Error getting workspace config: {e}")
            return None

    def is_setup_complete(self, workspace_id: str) -> bool:
        """Check if workspace has completed setup."""
        config = self.get_workspace_config(workspace_id)
        return config is not None and config.get("setup_complete", False)

    def save_workspace_config(
        self, workspace_id: str, config: dict[str, Any]
    ) -> bool:
        """
        Save workspace configuration.

        Args:
            workspace_id: Slack workspace ID
            config: Configuration dictionary

        Returns:
            True if successful
        """
        try:
            item = {
                "workspace_id": workspace_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                **config,
            }

            self.table.put_item(Item=item)
            logger.info(f"Saved workspace config for {workspace_id}")
            return True
        except ClientError as e:
            logger.error(f"Error saving workspace config: {e}")
            return False

    def update_workspace_config(
        self, workspace_id: str, updates: dict[str, Any]
    ) -> bool:
        """
        Update specific fields in workspace configuration.

        Args:
            workspace_id: Slack workspace ID
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        try:
            # Build update expression
            update_expr = "SET updated_at = :updated_at"
            expr_values = {":updated_at": datetime.now(timezone.utc).isoformat()}

            for key, value in updates.items():
                update_expr += f", {key} = :{key}"
                expr_values[f":{key}"] = value

            self.table.update_item(
                Key={"workspace_id": workspace_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )
            logger.info(f"Updated workspace config for {workspace_id}")
            return True
        except ClientError as e:
            logger.error(f"Error updating workspace config: {e}")
            return False

    def validate_connectivity(self) -> dict[str, dict[str, Any]]:
        """
        Validate connectivity to all required services.

        Returns:
            Dictionary with validation results for each service
        """
        results = {}

        # Check AWS connectivity
        results["aws"] = self._check_aws_connectivity()

        # Check GitHub connectivity
        results["github"] = self._check_github_connectivity()

        # Check Slack connectivity
        results["slack"] = self._check_slack_connectivity()

        # Check DynamoDB tables
        results["dynamodb"] = self._check_dynamodb_tables()

        return results

    def _check_aws_connectivity(self) -> dict[str, Any]:
        """Check AWS connectivity and permissions."""
        try:
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()

            return {
                "status": "ok",
                "account_id": identity["Account"],
                "arn": identity["Arn"],
            }
        except Exception as e:
            logger.error(f"AWS connectivity check failed: {e}")
            return {"status": "error", "error": str(e)}

    def _check_github_connectivity(self) -> dict[str, Any]:
        """Check GitHub App connectivity."""
        try:
            # Simple check - GitHub integration is optional for setup
            import requests
            response = requests.get("https://api.github.com", timeout=5)
            if response.status_code == 200:
                return {"status": "ok", "note": "GitHub API reachable (optional)"}
            else:
                return {"status": "warning", "note": "GitHub integration optional"}
        except Exception as e:
            logger.error(f"GitHub connectivity check failed: {e}")
            return {"status": "warning", "note": "GitHub integration optional", "error": str(e)}

    def _check_slack_connectivity(self) -> dict[str, Any]:
        """Check Slack connectivity."""
        try:
            from services.slack_service import SlackService
            import os

            # Get Slack token from environment or SSM
            slack_token = os.environ.get("SLACK_BOT_TOKEN")
            if not slack_token:
                # Try to get from SSM Parameter Store
                ssm = boto3.client("ssm")
                param_name = os.environ.get("SLACK_BOT_TOKEN_SSM", "/carl/dev/slack-bot-token")
                try:
                    response = ssm.get_parameter(Name=param_name, WithDecryption=True)
                    slack_token = response["Parameter"]["Value"]
                except:
                    pass

            if not slack_token:
                return {"status": "warning", "note": "Slack token not configured"}

            slack = SlackService(slack_token)
            # Test auth
            response = slack.client.auth_test()

            return {
                "status": "ok",
                "team_id": response.get("team_id"),
                "bot_id": response.get("bot_id"),
            }
        except Exception as e:
            logger.error(f"Slack connectivity check failed: {e}")
            return {"status": "error", "error": str(e)}

    def _check_dynamodb_tables(self) -> dict[str, Any]:
        """Check DynamoDB tables exist and are accessible."""
        try:
            dynamodb = boto3.client("dynamodb")

            # Use correct environment variable names and defaults matching actual services
            tables_to_check = [
                SETUP_TABLE,  # carl-dev-setup-config
                os.environ.get("FINDINGS_TABLE", "carl-findings-dev"),
                os.environ.get("EVIDENCE_TABLE", "carl-evidence-dev"),
            ]

            table_status = {}
            for table_name in tables_to_check:
                try:
                    response = dynamodb.describe_table(TableName=table_name)
                    table_status[table_name] = response["Table"]["TableStatus"]
                except ClientError as e:
                    table_status[table_name] = "NOT_FOUND"
                    logger.warning(f"Table {table_name} not found: {e}")

            all_active = all(status == "ACTIVE" for status in table_status.values())

            return {
                "status": "ok" if all_active else "warning",
                "tables": table_status,
            }
        except Exception as e:
            logger.error(f"DynamoDB check failed: {e}")
            return {"status": "error", "error": str(e)}

    def get_default_config(self) -> dict[str, Any]:
        """Get default configuration values."""
        return {
            "notification_channel": None,
            "scan_schedule": "on_demand",  # on_demand, daily, custom
            "scan_regions": ["us-east-1"],
            "auto_scan_on_deploy": True,
            "compliance_frameworks": ["soc2"],
            "evidence_collection": True,
            "evidence_retention_years": 7,
            "setup_complete": False,
            "setup_version": "1.0",
        }

    def format_validation_results(self, results: dict[str, dict]) -> str:
        """Format validation results for display in Slack."""
        lines = []

        for service, result in results.items():
            status = result.get("status")
            if status == "ok":
                lines.append(f"✅ {service.upper()}: Connected")
                if service == "aws":
                    lines.append(f"   Account: {result.get('account_id')}")
                elif service == "github":
                    lines.append(
                        f"   Installation: {result.get('installation_id')}"
                    )
                elif service == "dynamodb":
                    active_tables = sum(
                        1
                        for s in result.get("tables", {}).values()
                        if s == "ACTIVE"
                    )
                    lines.append(f"   Tables: {active_tables} active")
            else:
                lines.append(f"❌ {service.upper()}: {result.get('error', 'Failed')}")

        return "\n".join(lines)
