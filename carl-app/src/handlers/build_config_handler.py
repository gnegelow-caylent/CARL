"""
Build configuration modal handler - temporary file for refactoring.

This will be integrated into slack_router.py
"""

def handle_build_config_submission(payload: dict) -> dict:
    """Handle build configuration modal submission with validation."""
    import ipaddress
    import re
    import json

    from services.slack_service import SlackService

    slack = SlackService()
    user_id = payload["user"]["id"]

    # Parse callback_id: build_config_submit:{session_id}:{option_number}
    callback_id = payload["view"]["callback_id"]
    parts = callback_id.split(":")
    if len(parts) < 3:
        return {"statusCode": 200, "body": ""}

    session_id = parts[1]
    option_number = parts[2]

    # Extract form values
    values = payload["view"]["state"]["values"]

    # Parse inputs
    vpc_selection = values.get("vpc_selection", {}).get("vpc_select", {}).get("selected_option", {}).get("value")
    vpc_cidr = values.get("vpc_cidr", {}).get("vpc_cidr_input", {}).get("value", "")
    prefix = values.get("resource_prefix", {}).get("prefix_input", {}).get("value", "carl")
    environment = values.get("environment", {}).get("env_select", {}).get("selected_option", {}).get("value", "prod")
    use_tgw = values.get("use_transit_gateway", {}).get("tgw_select", {}).get("selected_option", {}).get("value", "no")

    # Validate inputs
    errors = {}

    # Validate CIDR if creating new VPC
    if vpc_selection == "create_new":
        if not vpc_cidr:
            errors["vpc_cidr"] = "CIDR required when creating new VPC"
        else:
            try:
                ipaddress.ip_network(vpc_cidr)
            except ValueError:
                errors["vpc_cidr"] = "Invalid CIDR format (e.g., 10.0.0.0/16)"

    # Validate prefix
    if not re.match(r'^[a-z][a-z0-9-]*$', prefix):
        errors["resource_prefix"] = "Must start with letter, lowercase, hyphens only"

    if errors:
        return {
            "response_action": "errors",
            "errors": errors
        }

    # Get channel from response_urls or fallback to DM
    response_urls = payload.get("response_urls", [])
    channel_id = user_id  # Fallback to DM

    # Generate Terraform configuration
    terraform_config = {
        "vpc_id": vpc_selection if vpc_selection != "create_new" else None,
        "vpc_cidr": vpc_cidr if vpc_selection == "create_new" else None,
        "prefix": prefix,
        "environment": environment,
        "use_transit_gateway": use_tgw == "yes"
    }

    # Post success message
    slack.post_message(
        channel_id,
        text=f"✅ *Configuration Validated!*\n\n"
             f"• VPC: {'Create New (' + vpc_cidr + ')' if vpc_selection == 'create_new' else vpc_selection}\n"
             f"• Prefix: `{prefix}`\n"
             f"• Environment: {environment}\n"
             f"• Transit Gateway: {'Yes' if use_tgw == 'yes' else 'No'}\n\n"
             f"🏗️ Generating Terraform code..."
    )

    # TODO: Generate actual Terraform from terraform_config
    # For now, show what would be generated
    slack.post_message(
        channel_id,
        text="🚧 *Terraform Generation (Coming Soon)*\n\n"
             f"Configuration stored:\n```{json.dumps(terraform_config, indent=2)}```\n\n"
             "Next steps:\n"
             "• Generate Terraform modules\n"
             "• Push to GitHub repository\n"
             "• Provide deployment instructions"
    )

    return {"statusCode": 200, "body": ""}
