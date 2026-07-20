"""
CARL Ask Tool

Intelligent Q&A about AWS environment with automatic scanning.
"""
import os
import json
import logging
from typing import Dict, Any
from mcp.types import Tool
from ..clients.agentcore import invoke_agentcore_agent

logger = logging.getLogger(__name__)

def carl_ask_tool() -> Tool:
    """Define the carl_ask MCP tool."""
    return Tool(
        name="carl_ask",
        description="""Ask CARL questions about your AWS environment.

CARL will:
1. Analyze your question to determine what needs to be scanned
2. Scan relevant AWS resources (VPCs, S3, IAM, Security Hub, etc.)
3. Provide detailed answers with security recommendations
4. Map findings to SOC 2 compliance controls

Examples:
- "What are my biggest security risks?"
- "How is my MFA configured?"
- "Which S3 buckets lack encryption?"
- "Show me my VPC security group rules"
- "Am I compliant with SOC 2 CC6.1?"

The answer includes actionable recommendations and compliance context.""",
        inputSchema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Your question about AWS security, compliance, or infrastructure"
                }
            },
            "required": ["question"]
        }
    )

async def handle_carl_ask(arguments: Dict[str, Any]) -> str:
    """Execute the carl_ask tool."""
    question = arguments.get("question", "")

    if not question:
        return "❌ Error: Please provide a question"

    logger.info(f"Carl Ask: {question}")

    try:
        # Get AgentCore ARN from environment
        ask_agent_arn = os.getenv("CARL_AGENTCORE_ASK_ARN")
        if not ask_agent_arn:
            return "❌ Error: CARL_AGENTCORE_ASK_ARN not configured. Please check your Claude Desktop config."

        # Call AgentCore Ask Agent
        response = await invoke_agentcore_agent(
            runtime_arn=ask_agent_arn,
            payload={"prompt": question}
        )

        return response

    except Exception as e:
        logger.exception(f"Carl Ask failed: {e}")
        return f"❌ Error: {str(e)}\n\nPlease check:\n1. AWS credentials are configured\n2. AgentCore agents are deployed\n3. IAM permissions for bedrock:InvokeAgentRuntime"
