"""
CARL Architect Tool

Get architecture recommendations with cost estimates and compliance guidance.
"""
import os
import logging
from typing import Dict, Any
from mcp.types import Tool
from ..clients.agentcore import invoke_agentcore_agent

logger = logging.getLogger(__name__)

def carl_architect_tool() -> Tool:
    """Define the carl_architect MCP tool."""
    return Tool(
        name="carl_architect",
        description="""Get AWS architecture recommendations from CARL.

CARL provides 2-3 options with:
- Cost estimates (monthly $)
- Pros and cons
- SOC 2 compliance implications
- Recommended option with justification

Examples:
- "How should I deploy a secure web application?"
- "What's the best way to host static websites?"
- "Recommend a serverless API architecture"
- "I need to run containers cost-effectively"
- "Design a compliant data processing pipeline"

Returns detailed options with clear tradeoffs.""",
        inputSchema={
            "type": "object",
            "properties": {
                "requirement": {
                    "type": "string",
                    "description": "Your architecture requirement or question"
                }
            },
            "required": ["requirement"]
        }
    )

async def handle_carl_architect(arguments: Dict[str, Any]) -> str:
    """Execute the carl_architect tool."""
    requirement = arguments.get("requirement", "")

    if not requirement:
        return "❌ Error: Please provide an architecture requirement"

    logger.info(f"Carl Architect: {requirement}")

    try:
        architect_agent_arn = os.getenv("CARL_AGENTCORE_ARCHITECT_ARN")
        if not architect_agent_arn:
            return "❌ Error: CARL_AGENTCORE_ARCHITECT_ARN not configured"

        response = await invoke_agentcore_agent(
            runtime_arn=architect_agent_arn,
            payload={"prompt": requirement}
        )

        return response

    except Exception as e:
        logger.exception(f"Carl Architect failed: {e}")
        return f"❌ Error: {str(e)}"
