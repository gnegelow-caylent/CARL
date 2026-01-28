"""
CARL Feature Manager

Manages dynamic enable/disable of CARL features with dependency resolution.
Triggers GitHub Actions workflows to deploy infrastructure.
"""

import logging
import os
import time
import boto3
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class FeatureManager:
    """Manage CARL features dynamically."""

    FEATURES = {
        "monitoring": {
            "name": "Infrastructure Monitoring",
            "description": "Scan AWS accounts, compliance checking, Security Hub integration",
            "dependencies": ["reporting"],
            "terraform_var": "enable_monitoring",
            "monthly_cost": "$30-50"
        },
        "bootstrap": {
            "name": "Infrastructure Builder",
            "description": "AWS Organizations setup, Identity Center, security baselines",
            "dependencies": [],
            "terraform_var": "enable_bootstrap",
            "monthly_cost": "$20-30"
        },
        "reporting": {
            "name": "Compliance Reporting",
            "description": "Generate compliance reports, evidence collection, audit trails",
            "dependencies": [],
            "terraform_var": "enable_reporting",
            "monthly_cost": "$15-25"
        },
        "foundation": {
            "name": "Foundation Builder",
            "description": "Guided infrastructure creation, Terraform generation",
            "dependencies": [],
            "terraform_var": "enable_foundation",
            "monthly_cost": "$10-20"
        },
        "drift_detection": {
            "name": "Drift Detection",
            "description": "Detect infrastructure drift from desired state",
            "dependencies": ["monitoring"],
            "terraform_var": "enable_drift_detection",
            "monthly_cost": "$10-15"
        },
        "auto_remediation": {
            "name": "Auto-Remediation",
            "description": "Automatically fix compliance violations and drift",
            "dependencies": ["monitoring", "drift_detection"],
            "terraform_var": "enable_auto_remediation",
            "monthly_cost": "$15-25"
        }
    }

    def __init__(self, config_table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.config_table = self.dynamodb.Table(config_table_name)

    def get_enabled_features(self, workspace_id: str) -> List[str]:
        """Get list of enabled features for workspace."""
        try:
            response = self.config_table.get_item(
                Key={
                    'pk': f'WORKSPACE#{workspace_id}',
                    'sk': 'CONFIG'
                }
            )
            return response.get('Item', {}).get('enabled_features', [])
        except Exception as e:
            logger.error(f"Error getting enabled features: {e}")
            return []

    def enable_feature(self, workspace_id: str, feature_id: str, user_id: str, environment: str = "dev") -> Dict[str, Any]:
        """Enable a feature (with dependency resolution)."""

        # Validate feature exists
        if feature_id not in self.FEATURES:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Unknown feature: {feature_id}\n\nAvailable features: {', '.join(self.FEATURES.keys())}"
            }

        feature = self.FEATURES[feature_id]

        # Check if already enabled
        enabled_features = self.get_enabled_features(workspace_id)
        if feature_id in enabled_features:
            return {
                "response_type": "ephemeral",
                "text": f"✅ {feature['name']} is already enabled."
            }

        # Check dependencies
        missing_deps = [dep for dep in feature["dependencies"] if dep not in enabled_features]

        if missing_deps:
            dep_names = [self.FEATURES[dep]["name"] for dep in missing_deps]
            return {
                "response_type": "ephemeral",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"⚠️ *Cannot enable {feature['name']}*\n\n"
                            f"**Missing dependencies:**\n" + "\n".join([f"• {name}" for name in dep_names]) + "\n\n"
                            f"Would you like me to enable these dependencies first?"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Yes, enable all"},
                                "style": "primary",
                                "value": f"{feature_id}|{','.join(missing_deps)}",
                                "action_id": "feature_enable_with_deps"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Cancel"},
                                "action_id": "feature_cancel"
                            }
                        ]
                    }
                ]
            }

        # Trigger deployment
        return self._trigger_deployment(workspace_id, feature_id, user_id, environment, "enable")

    def enable_feature_with_deps(self, workspace_id: str, feature_id: str, dependencies: List[str],
                                  user_id: str, environment: str = "dev") -> Dict[str, Any]:
        """Enable a feature along with its dependencies."""

        # Enable dependencies first
        for dep_id in dependencies:
            result = self._trigger_deployment(workspace_id, dep_id, user_id, environment, "enable")
            if "❌" in result.get("text", ""):
                return result

        # Enable main feature
        return self._trigger_deployment(workspace_id, feature_id, user_id, environment, "enable")

    def disable_feature(self, workspace_id: str, feature_id: str, user_id: str, environment: str = "dev") -> Dict[str, Any]:
        """Disable a feature."""

        # Validate feature exists
        if feature_id not in self.FEATURES:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Unknown feature: {feature_id}"
            }

        feature = self.FEATURES[feature_id]

        # Check if already disabled
        enabled_features = self.get_enabled_features(workspace_id)
        if feature_id not in enabled_features:
            return {
                "response_type": "ephemeral",
                "text": f"✅ {feature['name']} is already disabled."
            }

        # Check for dependent features
        dependents = [
            fid for fid, fconf in self.FEATURES.items()
            if feature_id in fconf["dependencies"] and fid in enabled_features
        ]

        if dependents:
            dep_names = [self.FEATURES[dep]["name"] for dep in dependents]
            return {
                "response_type": "ephemeral",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"⚠️ *Cannot disable {feature['name']}*\n\n"
                            f"**These features depend on it:**\n" + "\n".join([f"• {name}" for name in dep_names]) + "\n\n"
                            f"Disable these features first, or disable all together?"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Disable all"},
                                "style": "danger",
                                "value": f"{feature_id}|{','.join(dependents)}",
                                "action_id": "feature_disable_with_deps"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Cancel"},
                                "action_id": "feature_cancel"
                            }
                        ]
                    }
                ]
            }

        # Trigger deployment
        return self._trigger_deployment(workspace_id, feature_id, user_id, environment, "disable")

    def _trigger_deployment(self, workspace_id: str, feature_id: str, user_id: str,
                           environment: str, action: str) -> Dict[str, Any]:
        """Trigger GitHub Actions workflow to deploy feature."""

        feature = self.FEATURES[feature_id]

        # Get GitHub credentials from environment
        github_token = os.environ.get('GITHUB_TOKEN')
        github_repo = os.environ.get('GITHUB_REPO')  # format: "owner/repo"

        if not github_token or not github_repo:
            # GitHub integration not configured, return manual instructions
            return self._manual_deployment_instructions(feature_id, environment, action)

        # Trigger GitHub Actions workflow
        try:
            workflow_result = self.trigger_github_workflow(
                repo=github_repo,
                token=github_token,
                workflow="deploy-features.yml",
                inputs={
                    "feature": feature_id,
                    "environment": environment,
                    "action": action
                }
            )

            if workflow_result:
                # Save deployment tracking
                self._save_deployment_status(workspace_id, feature_id, action, "in_progress", user_id)

                return {
                    "response_type": "in_channel",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"🚀 *{action.title()}ing {feature['name']}...*\n\n"
                                f"Deployment started. This will take 5-10 minutes.\n"
                                f"I'll notify you when complete."
                            }
                        }
                    ]
                }
            else:
                return {
                    "response_type": "ephemeral",
                    "text": f"❌ Failed to trigger deployment. Check GitHub Actions logs."
                }

        except Exception as e:
            logger.error(f"Error triggering GitHub workflow: {e}")
            return self._manual_deployment_instructions(feature_id, environment, action)

    def trigger_github_workflow(self, repo: str, token: str, workflow: str, inputs: dict) -> bool:
        """Trigger GitHub Actions workflow dispatch."""

        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        payload = {
            "ref": "main",  # or "develop" depending on environment
            "inputs": inputs
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            return False

    def _manual_deployment_instructions(self, feature_id: str, environment: str, action: str) -> Dict[str, Any]:
        """Return manual deployment instructions when GitHub integration not available."""

        feature = self.FEATURES[feature_id]
        var_name = feature["terraform_var"]
        var_value = "true" if action == "enable" else "false"

        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Manual Deployment Required*\n\n"
                        f"GitHub integration not configured. Run this command:\n\n"
                        f"```bash\n"
                        f"cd carl-infrastructure/core\n"
                        f"terraform apply -var=\"{var_name}={var_value}\" -var=\"environment={environment}\"\n"
                        f"```\n\n"
                        f"After deployment, run: `/carl feature deployed {feature_id}`"
                    }
                }
            ]
        }

    def _save_deployment_status(self, workspace_id: str, feature_id: str, action: str,
                                status: str, user_id: str) -> None:
        """Save deployment status to DynamoDB."""
        try:
            self.config_table.put_item(
                Item={
                    'pk': f'WORKSPACE#{workspace_id}',
                    'sk': f'DEPLOYMENT#{feature_id}#{int(time.time())}',
                    'feature_id': feature_id,
                    'action': action,
                    'status': status,
                    'user_id': user_id,
                    'timestamp': int(time.time())
                }
            )
        except Exception as e:
            logger.error(f"Error saving deployment status: {e}")

    def mark_feature_deployed(self, workspace_id: str, feature_id: str) -> Dict[str, Any]:
        """Mark a feature as successfully deployed."""

        if feature_id not in self.FEATURES:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Unknown feature: {feature_id}"
            }

        feature = self.FEATURES[feature_id]

        try:
            # Get current enabled features
            enabled_features = self.get_enabled_features(workspace_id)

            # Add this feature if not already present
            if feature_id not in enabled_features:
                enabled_features.append(feature_id)

                # Update config
                self.config_table.update_item(
                    Key={
                        'pk': f'WORKSPACE#{workspace_id}',
                        'sk': 'CONFIG'
                    },
                    UpdateExpression='SET enabled_features = :features',
                    ExpressionAttributeValues={':features': enabled_features}
                )

            return {
                "response_type": "in_channel",
                "text": f"✅ {feature['name']} is now enabled and ready to use!"
            }

        except Exception as e:
            logger.error(f"Error marking feature deployed: {e}")
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error: {str(e)}"
            }

    def list_features(self, workspace_id: str) -> Dict[str, Any]:
        """List all available features and their status."""

        enabled_features = self.get_enabled_features(workspace_id)

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*CARL Features*\n\nAvailable features and their current status:"
                }
            },
            {"type": "divider"}
        ]

        for feature_id, feature in self.FEATURES.items():
            status = "✅ Enabled" if feature_id in enabled_features else "⚪ Disabled"
            deps = ", ".join([self.FEATURES[d]["name"] for d in feature["dependencies"]]) if feature["dependencies"] else "None"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{feature['name']}* {status}\n"
                    f"{feature['description']}\n"
                    f"_Dependencies: {deps}_"
                }
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 _Use `/carl enable <feature>` or `/carl disable <feature>` to manage features_"
                }
            ]
        })

        return {
            "response_type": "in_channel",
            "blocks": blocks
        }
