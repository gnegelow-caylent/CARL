"""
CARL Remediate Tool

Fix security findings with AI-generated Terraform or direct AWS API calls.
"""
import os
import logging
from typing import Dict, Any
from mcp.types import Tool
from ..clients.agentcore import invoke_agentcore_agent

logger = logging.getLogger(__name__)

def carl_remediate_tool() -> Tool:
    """Define the carl_remediate_finding MCP tool."""
    return Tool(
        name="carl_remediate_finding",
        description="""Request automated fix for a security finding.

CARL's Remediation Agent will:
1. Analyze the finding and classify risk level (LOW/MEDIUM/HIGH)
2. Generate appropriate fix (Terraform code or direct AWS API)
3. Provide preview of changes with approval request
4. Apply fix with your approval

Risk-based approach:
- LOW risk: Direct AWS API calls (e.g., enable S3 encryption)
- MEDIUM/HIGH risk: Terraform PR for review

Supported findings:
- S3 encryption, versioning, public access
- IAM password policies, MFA
- VPC flow logs
- Security group rules
- CloudTrail configuration
- And more...

Example:
To fix S3 bucket encryption:
  finding_id: "s3-bucket-my-bucket-no-encryption"

CARL will generate and apply the fix after your approval.""",
        inputSchema={
            "type": "object",
            "properties": {
                "finding_id": {
                    "type": "string",
                    "description": "Finding ID to remediate (from carl_scan_environment or Security Hub)"
                },
                "auto_approve": {
                    "type": "boolean",
                    "description": "Automatically approve LOW risk changes without confirmation (default: false)",
                    "default": False
                }
            },
            "required": ["finding_id"]
        }
    )

async def handle_carl_remediate(arguments: Dict[str, Any]) -> str:
    """Execute the carl_remediate_finding tool."""
    finding_id = arguments.get("finding_id", "")
    auto_approve = arguments.get("auto_approve", False)

    if not finding_id:
        return "❌ Error: Please provide a finding_id"

    try:
        # Get AgentCore ARN from environment
        remediate_agent_arn = os.getenv("CARL_AGENTCORE_REMEDIATE_ARN")
        if not remediate_agent_arn:
            return "❌ Error: CARL_AGENTCORE_REMEDIATE_ARN not configured. Please check your Claude Desktop config."

        logger.info(f"Requesting remediation for finding: {finding_id}")

        # Call Remediate Agent
        response = await invoke_agentcore_agent(
            runtime_arn=remediate_agent_arn,
            payload={
                "action": "remediate",
                "finding_id": finding_id,
                "auto_approve_low_risk": auto_approve
            }
        )

        return response

    except Exception as e:
        logger.exception(f"Remediation failed: {e}")
        return f"""❌ Error: {str(e)}

Please check:
1. AWS credentials are configured
2. AgentCore remediate agent is deployed
3. IAM permissions for bedrock:InvokeAgentRuntime
4. Finding ID is valid (use carl_scan_environment to list findings)

To deploy the remediate agent:
cd carl-infrastructure/mcp-deployment
terraform apply"""
