"""
CARL MCP Server

Implements Model Context Protocol for CARL AWS security/compliance tools.
"""
import os
import sys
import logging
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# CARL tools
from .tools.ask import carl_ask_tool, handle_carl_ask
from .tools.scan import carl_scan_tool, handle_carl_scan
from .tools.remediate import carl_remediate_tool, handle_carl_remediate
from .tools.evidence import carl_evidence_tool, handle_carl_evidence
from .tools.architect import carl_architect_tool, handle_carl_architect
from .tools.report import carl_report_tool, handle_carl_report

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

def create_server() -> Server:
    """Create and configure the CARL MCP server."""

    # Validate required environment variables
    required_envs = [
        'CARL_AGENTCORE_ASK_ARN',
        'CARL_AGENTCORE_ARCHITECT_ARN',
        'CARL_AGENTCORE_REMEDIATE_ARN',
    ]

    missing = [env for env in required_envs if not os.getenv(env)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please configure Claude Desktop with CARL AgentCore ARNs")
        raise ValueError(f"Missing environment variables: {missing}")

    # Create MCP server
    server = Server("carl")
    logger.info("🚀 CARL MCP Server initializing...")

    # Register tools
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available CARL tools."""
        return [
            carl_ask_tool(),
            carl_scan_tool(),
            carl_remediate_tool(),
            carl_evidence_tool(),
            carl_report_tool(),
            carl_architect_tool(),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute a CARL tool."""
        logger.info(f"Tool called: {name}")

        try:
            if name == "carl_ask":
                result = await handle_carl_ask(arguments)
            elif name == "carl_scan_environment":
                result = await handle_carl_scan(arguments)
            elif name == "carl_remediate_finding":
                result = await handle_carl_remediate(arguments)
            elif name == "carl_collect_evidence":
                result = await handle_carl_evidence(arguments)
            elif name == "carl_generate_report":
                result = await handle_carl_report(arguments)
            elif name == "carl_architect":
                result = await handle_carl_architect(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

            return [TextContent(type="text", text=result)]

        except Exception as e:
            logger.exception(f"Tool execution failed: {e}")
            error_msg = f"❌ Error executing {name}: {str(e)}"
            return [TextContent(type="text", text=error_msg)]

    logger.info("✅ CARL MCP Server ready")
    logger.info(f"   Ask Agent: {os.getenv('CARL_AGENTCORE_ASK_ARN', 'not set')}")
    logger.info(f"   Architect Agent: {os.getenv('CARL_AGENTCORE_ARCHITECT_ARN', 'not set')}")
    logger.info(f"   Remediate Agent: {os.getenv('CARL_AGENTCORE_REMEDIATE_ARN', 'not set')}")

    return server

async def run_server():
    """Run the MCP server with stdio transport."""
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
