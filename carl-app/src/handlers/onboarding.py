"""
CARL Onboarding Handler

Manages first-time user interaction and feature selection.
"""

import logging
import boto3
from typing import Dict, Any

logger = logging.getLogger(__name__)


class OnboardingHandler:
    """Handles CARL's onboarding conversation."""

    def __init__(self, config_table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.config_table = self.dynamodb.Table(config_table_name)

    def get_onboarding_state(self, workspace_id: str) -> Dict[str, Any]:
        """Check if workspace has completed onboarding."""
        try:
            response = self.config_table.get_item(
                Key={
                    'pk': f'WORKSPACE#{workspace_id}',
                    'sk': 'CONFIG'
                }
            )
            return response.get('Item', {})
        except Exception as e:
            logger.error(f"Error getting onboarding state: {e}")
            return {}

    def is_onboarding_complete(self, workspace_id: str) -> bool:
        """Check if onboarding is complete."""
        state = self.get_onboarding_state(workspace_id)
        return state.get('onboarding_complete', False)

    def get_welcome_message(self, user_id: str) -> Dict[str, Any]:
        """Get initial welcome message for new users."""
        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"👋 Hi <@{user_id}>! I'm *CARL* (Cloud Automated Risk & Compliance Logic).\n\n"
                        "I'm your AI-powered AWS compliance and architecture assistant."
                    }
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*What would you like me to help with?*\n\n"
                        "Choose what fits your needs best. I'll only deploy what you actually use."
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*1️⃣ Monitor Existing Infrastructure*\n"
                        "Scan your AWS accounts, check compliance, find security issues.\n\n"
                        "*What I'll deploy:*\n"
                        "• Security Hub integration\n"
                        "• Scanning lambdas\n"
                        "• Evidence storage (S3 + DynamoDB)\n"
                        "• Compliance reports\n\n"
                        "*Cost:* ~$30-50/month additional\n"
                        "*Good for:* Existing AWS infrastructure"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*2️⃣ Build Compliant Infrastructure*\n"
                        "Set up AWS from scratch with Organizations, Identity Center, security services.\n\n"
                        "*What I'll deploy:*\n"
                        "• Organizations bootstrap automation\n"
                        "• Identity Center setup\n"
                        "• Security baseline deployment\n"
                        "• Terraform code generation\n\n"
                        "*Cost:* ~$20-30/month additional\n"
                        "*Good for:* New AWS accounts, greenfield projects"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*3️⃣ Architecture Advisor Only*\n"
                        "Ask questions, get recommendations, review designs. No scanning or automation.\n\n"
                        "*What I'll deploy:*\n"
                        "• Nothing! Just me (already deployed)\n\n"
                        "*Cost:* Current $10-20/month (no change)\n"
                        "*Good for:* Consulting, design reviews, learning"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*4️⃣ Full Platform (Everything)*\n"
                        "All features enabled: monitoring, building, reporting, automation.\n\n"
                        "*What I'll deploy:*\n"
                        "• Everything from options 1 & 2\n"
                        "• Advanced reporting\n"
                        "• Drift detection\n"
                        "• Auto-remediation\n\n"
                        "*Cost:* ~$75-150/month total\n"
                        "*Good for:* Enterprise teams, compliance-heavy industries"
                    }
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "1️⃣ Monitor"},
                            "style": "primary",
                            "value": "monitoring",
                            "action_id": "onboarding_select_monitoring"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "2️⃣ Build"},
                            "value": "bootstrap",
                            "action_id": "onboarding_select_bootstrap"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "3️⃣ Advisor"},
                            "value": "advisor",
                            "action_id": "onboarding_select_advisor"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "4️⃣ Everything"},
                            "value": "full",
                            "action_id": "onboarding_select_full"
                        }
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "💡 _You can always enable more features later with `/carl enable <feature>`_"
                        }
                    ]
                }
            ]
        }

    def handle_selection(self, selection: str, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """Handle user's feature selection."""

        selections = {
            "monitoring": {
                "name": "Infrastructure Monitoring",
                "features": ["monitoring", "scanning", "evidence_collection", "reporting"],
                "cost": "$30-50/month",
                "deploy_command": "cloudformation deploy --stack-name carl-monitoring --template-file features/monitoring.yaml"
            },
            "bootstrap": {
                "name": "Infrastructure Builder",
                "features": ["bootstrap", "organizations", "identity_center", "security_baseline"],
                "cost": "$20-30/month",
                "deploy_command": "cloudformation deploy --stack-name carl-bootstrap --template-file features/bootstrap.yaml"
            },
            "advisor": {
                "name": "Architecture Advisor",
                "features": [],
                "cost": "$0/month (no change)",
                "deploy_command": None
            },
            "full": {
                "name": "Full Platform",
                "features": ["monitoring", "bootstrap", "reporting", "automation", "drift_detection"],
                "cost": "$75-150/month",
                "deploy_command": "cloudformation deploy --stack-name carl-full --template-file features/full-platform.yaml"
            }
        }

        config = selections.get(selection, selections["advisor"])

        # Save selection to config
        try:
            self.config_table.put_item(
                Item={
                    'pk': f'WORKSPACE#{workspace_id}',
                    'sk': 'CONFIG',
                    'onboarding_complete': False,  # Will be True after deployment
                    'selected_features': config["features"],
                    'deploy_command': config["deploy_command"],
                    'user_id': user_id
                }
            )
        except Exception as e:
            logger.error(f"Error saving selection: {e}")

        if selection == "advisor":
            # No deployment needed
            return self._complete_advisor_setup(user_id, workspace_id)
        else:
            # Show deployment confirmation
            return self._show_deployment_confirmation(config, user_id)

    def _complete_advisor_setup(self, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """Complete setup for advisor-only mode."""
        try:
            self.config_table.update_item(
                Key={
                    'pk': f'WORKSPACE#{workspace_id}',
                    'sk': 'CONFIG'
                },
                UpdateExpression='SET onboarding_complete = :true',
                ExpressionAttributeValues={':true': True}
            )
        except Exception as e:
            logger.error(f"Error completing onboarding: {e}")

        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "✅ *Setup Complete!*\n\n"
                        "I'm ready to help as your Architecture Advisor.\n\n"
                        "*Try these commands:*\n"
                        "• `/carl architect <question>` - Get architecture recommendations\n"
                        "• `/carl patterns vpc` - View VPC design patterns\n"
                        "• `/carl recommend database` - Get database recommendations\n"
                        "• `/carl estimate ec2 instance` - Get cost estimates\n\n"
                        "*Want more features later?*\n"
                        "• `/carl enable monitoring` - Add infrastructure scanning\n"
                        "• `/carl enable bootstrap` - Add AWS setup automation"
                    }
                }
            ]
        }

    def _show_deployment_confirmation(self, config: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Show deployment confirmation message."""
        features_list = "\n".join([f"• {f.replace('_', ' ').title()}" for f in config["features"]])

        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🚀 *Ready to deploy: {config['name']}*\n\n"
                        f"*Features that will be enabled:*\n{features_list}\n\n"
                        f"*Additional cost:* {config['cost']}"
                    }
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Deployment Options:*\n\n"
                        "*Option 1: I'll deploy it (Automated)*\n"
                        "I'll create the CloudFormation stack automatically.\n"
                        "Takes ~5-10 minutes.\n\n"
                        "*Option 2: You deploy it (Manual)*\n"
                        "I'll give you the deployment command to run yourself.\n"
                        "Good for tightly controlled environments."
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Auto-Deploy (Recommended)"},
                            "style": "primary",
                            "value": f"auto|{config['deploy_command']}",
                            "action_id": "onboarding_deploy_auto"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Show Commands (Manual)"},
                            "value": f"manual|{config['deploy_command']}",
                            "action_id": "onboarding_deploy_manual"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "style": "danger",
                            "value": "cancel",
                            "action_id": "onboarding_cancel"
                        }
                    ]
                }
            ]
        }

    def handle_deploy_auto(self, deploy_command: str, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """Handle automated deployment."""
        # TODO: Trigger CloudFormation stack creation
        # For now, return instructions

        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🚀 *Deploying features...*\n\n"
                        "This will take ~5-10 minutes. I'll notify you when complete.\n\n"
                        "⏳ _Automated deployment is being implemented..._"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*For now, please deploy manually:*\n\n"
                        f"```\n{deploy_command}\n```\n\n"
                        "After deployment completes, run:\n"
                        "`/carl onboarding complete`"
                    }
                }
            ]
        }

    def handle_deploy_manual(self, deploy_command: str) -> Dict[str, Any]:
        """Handle manual deployment instructions."""
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Manual Deployment Instructions*"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Run this command in your terminal:\n\n```\n{deploy_command}\n```\n\n"
                        "After deployment completes, run:\n"
                        "`/carl onboarding complete`"
                    }
                }
            ]
        }

    def complete_onboarding(self, workspace_id: str) -> Dict[str, Any]:
        """Mark onboarding as complete."""
        try:
            self.config_table.update_item(
                Key={
                    'pk': f'WORKSPACE#{workspace_id}',
                    'sk': 'CONFIG'
                },
                UpdateExpression='SET onboarding_complete = :true',
                ExpressionAttributeValues={':true': True}
            )

            return {
                "response_type": "in_channel",
                "text": "✅ Onboarding complete! CARL is ready to use. Try: `/carl status`"
            }
        except Exception as e:
            logger.error(f"Error completing onboarding: {e}")
            return {
                "response_type": "ephemeral",
                "text": f"❌ Error completing onboarding: {str(e)}"
            }
