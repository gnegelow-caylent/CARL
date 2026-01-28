"""
Slack command handlers for CARL bootstrap automation.

Handles /carl bootstrap commands for complete AWS environment setup.
"""

import json
import logging
from typing import Any, Dict, Optional

from services.bootstrap import (
    BootstrapOrchestrator,
    BootstrapConfiguration,
    AccountAssignment,
)

logger = logging.getLogger(__name__)


class BootstrapCommandHandler:
    """Handler for /carl bootstrap commands."""

    def __init__(self):
        self.orchestrator = BootstrapOrchestrator()

    def handle_bootstrap_command(
        self, command_text: str, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """
        Route bootstrap commands to appropriate handlers.

        Commands:
        - /carl bootstrap start
        - /carl bootstrap quickstart --admin-account <id>
        - /carl bootstrap minimal
        - /carl bootstrap status
        - /carl bootstrap config show
        - /carl bootstrap organizations
        - /carl bootstrap identity-center
        - /carl bootstrap security-services
        """
        parts = command_text.strip().split()

        if not parts or parts[0].lower() != "bootstrap":
            return self._help_response()

        if len(parts) == 1:
            return self._help_response()

        subcommand = parts[1].lower()

        if subcommand == "start":
            return self._start_interactive_bootstrap(user_id, channel_id)

        elif subcommand == "quickstart":
            admin_account = self._extract_admin_account(parts)
            return self._quickstart_bootstrap(admin_account, user_id, channel_id)

        elif subcommand == "minimal":
            return self._minimal_bootstrap(user_id, channel_id)

        elif subcommand == "status":
            return self._bootstrap_status(user_id, channel_id)

        elif subcommand == "config":
            if len(parts) > 2 and parts[2].lower() == "show":
                return self._show_config(user_id, channel_id)
            return self._help_response()

        elif subcommand == "organizations":
            return self._organizations_only(user_id, channel_id)

        elif subcommand == "identity-center":
            return self._identity_center_only(user_id, channel_id)

        elif subcommand == "security-services":
            admin_account = self._extract_admin_account(parts)
            return self._security_services_only(admin_account, user_id, channel_id)

        else:
            return self._help_response()

    def _start_interactive_bootstrap(
        self, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Start interactive bootstrap wizard."""
        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🚀 *CARL Bootstrap Wizard*\n\nI'll help you set up a complete AWS environment from scratch.",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*What will be configured:*\n"
                        "• AWS Organizations with OU structure\n"
                        "• Service Control Policies (SCPs)\n"
                        "• IAM Identity Center (SSO)\n"
                        "• Permission sets and groups\n"
                        "• Security services (Security Hub, GuardDuty, Inspector, Config)\n"
                        "• Delegated administrator setup",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Choose your bootstrap strategy:*",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Quickstart (Recommended)"},
                            "style": "primary",
                            "value": "quickstart",
                            "action_id": "bootstrap_quickstart",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Minimal Setup"},
                            "value": "minimal",
                            "action_id": "bootstrap_minimal",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Custom Configuration"},
                            "value": "custom",
                            "action_id": "bootstrap_custom",
                        },
                    ],
                },
            ],
        }

    def _quickstart_bootstrap(
        self, admin_account: Optional[str], user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Show quickstart configuration preview."""
        if not admin_account:
            return {
                "response_type": "ephemeral",
                "text": "❌ Please provide the delegated admin account ID:\n"
                "`/carl bootstrap quickstart --admin-account 999888777666`",
            }

        # Get quickstart config
        config = self.orchestrator.get_quickstart_config(
            delegated_admin_account_id=admin_account,
            security_regions=["us-east-1", "us-west-2"],
        )

        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚡ *Quickstart Bootstrap Configuration*\n\n"
                        f"Delegated Admin Account: `{admin_account}`\n"
                        "Security Regions: `us-east-1`, `us-west-2`",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Phase 1: Organizations*\n"
                        f"• {len(config.ou_structure)} OUs (Security, Infrastructure, Workloads, Sandbox, etc.)\n"
                        f"• {len(config.scps)} SCPs (deny security disabling, region restrictions, IMDSv2)",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Phase 2: Identity Center*\n"
                        f"• {len(config.permission_sets)} permission sets (Admin, PowerUser, ReadOnly, etc.)\n"
                        f"• {len(config.groups)} groups (CloudPlatformAdmins, Developers, etc.)\n"
                        "• Account assignments (you'll configure next)",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Phase 3: Security Services*\n"
                        "• Security Hub (delegated admin + auto-enable)\n"
                        "• GuardDuty (all data sources + auto-enable)\n"
                        "• Inspector (EC2, ECR, Lambda)\n"
                        "• Config (organization aggregator)",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚠️ *Important:*\n"
                        "• This will create Organizations (if not exists)\n"
                        "• This will enable IAM Identity Center\n"
                        "• Security services cost ~$40-190/account/month\n"
                        "• Estimated time: 10-15 minutes",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✓ Approve & Execute"},
                            "style": "primary",
                            "value": f"quickstart|{admin_account}",
                            "action_id": "bootstrap_execute_quickstart",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Configure Account Assignments"},
                            "value": f"quickstart|{admin_account}",
                            "action_id": "bootstrap_configure_assignments",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "style": "danger",
                            "value": "cancel",
                            "action_id": "bootstrap_cancel",
                        },
                    ],
                },
            ],
        }

    def _minimal_bootstrap(
        self, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Show minimal configuration preview."""
        config = self.orchestrator.get_minimal_config()

        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🔹 *Minimal Bootstrap Configuration*\n\n"
                        "Basic setup for getting started quickly.",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Phase 1: Organizations*\n"
                        "• 2 OUs (Workloads, Sandbox)\n"
                        "• 1 SCP (deny leaving organization)",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Phase 2: Identity Center*\n"
                        "• 2 permission sets (AdministratorAccess, ReadOnlyAccess)\n"
                        "• 1 group (Administrators)",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Phase 3: Security Services*\n"
                        "• Security Hub (basic)\n"
                        "• GuardDuty (basic)\n"
                        "• Config aggregator",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚠️ *Note:* Minimal setup is good for development/testing. "
                        "For production, use Quickstart configuration.",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✓ Approve & Execute"},
                            "style": "primary",
                            "value": "minimal",
                            "action_id": "bootstrap_execute_minimal",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "style": "danger",
                            "value": "cancel",
                            "action_id": "bootstrap_cancel",
                        },
                    ],
                },
            ],
        }

    def _bootstrap_status(
        self, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Check bootstrap status."""
        # TODO: Implement progress tracking from DynamoDB
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📊 *Bootstrap Status*\n\n"
                        "No bootstrap in progress.\n\n"
                        "Start a new bootstrap with:\n"
                        "`/carl bootstrap start`",
                    },
                },
            ],
        }

    def _show_config(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Show current bootstrap configuration."""
        # TODO: Retrieve saved config from DynamoDB
        return {
            "response_type": "ephemeral",
            "text": "No bootstrap configuration saved. Start with `/carl bootstrap start`",
        }

    def _organizations_only(
        self, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Bootstrap Organizations only."""
        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🏢 *Organizations Bootstrap Only*\n\n"
                        "This will create:\n"
                        "• AWS Organizations (if not exists)\n"
                        "• OU structure (AWS recommended)\n"
                        "• Service Control Policies (SCPs)",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✓ Execute"},
                            "style": "primary",
                            "value": "organizations",
                            "action_id": "bootstrap_execute_organizations",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "style": "danger",
                            "value": "cancel",
                            "action_id": "bootstrap_cancel",
                        },
                    ],
                },
            ],
        }

    def _identity_center_only(
        self, user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Bootstrap Identity Center only."""
        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "🔐 *Identity Center Bootstrap Only*\n\n"
                        "This will create:\n"
                        "• 5 permission sets\n"
                        "• 5 groups\n"
                        "• Account assignments (you'll configure)",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✓ Execute"},
                            "style": "primary",
                            "value": "identity_center",
                            "action_id": "bootstrap_execute_identity_center",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "style": "danger",
                            "value": "cancel",
                            "action_id": "bootstrap_cancel",
                        },
                    ],
                },
            ],
        }

    def _security_services_only(
        self, admin_account: Optional[str], user_id: str, channel_id: str
    ) -> Dict[str, Any]:
        """Bootstrap security services only."""
        if not admin_account:
            return {
                "response_type": "ephemeral",
                "text": "❌ Please provide the delegated admin account ID:\n"
                "`/carl bootstrap security-services --admin-account 999888777666`",
            }

        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🛡️ *Security Services Bootstrap Only*\n\n"
                        f"Delegated Admin: `{admin_account}`\n\n"
                        "This will enable:\n"
                        "• Security Hub (delegated admin + auto-enable)\n"
                        "• GuardDuty (all data sources)\n"
                        "• Inspector (EC2, ECR, Lambda)\n"
                        "• Config organization aggregator",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✓ Execute"},
                            "style": "primary",
                            "value": f"security_services|{admin_account}",
                            "action_id": "bootstrap_execute_security_services",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Cancel"},
                            "style": "danger",
                            "value": "cancel",
                            "action_id": "bootstrap_cancel",
                        },
                    ],
                },
            ],
        }

    def _help_response(self) -> Dict[str, Any]:
        """Return help message for bootstrap commands."""
        return {
            "response_type": "ephemeral",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*CARL Bootstrap Commands*\n\n"
                        "Complete AWS environment setup automation.",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Complete Bootstrap:*\n"
                        "`/carl bootstrap start` - Interactive wizard\n"
                        "`/carl bootstrap quickstart --admin-account <id>` - AWS recommended\n"
                        "`/carl bootstrap minimal` - Basic setup\n"
                        "`/carl bootstrap status` - Check progress\n"
                        "`/carl bootstrap config show` - View configuration",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Individual Components:*\n"
                        "`/carl bootstrap organizations` - Organizations + OU + SCPs only\n"
                        "`/carl bootstrap identity-center` - Identity Center only\n"
                        "`/carl bootstrap security-services --admin-account <id>` - Security services only",
                    },
                },
            ],
        }

    def _extract_admin_account(self, parts: list[str]) -> Optional[str]:
        """Extract admin account ID from command arguments."""
        try:
            idx = parts.index("--admin-account")
            if idx + 1 < len(parts):
                account_id = parts[idx + 1]
                # Validate it's a 12-digit number
                if account_id.isdigit() and len(account_id) == 12:
                    return account_id
        except (ValueError, IndexError):
            pass
        return None
