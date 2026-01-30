"""
Agent Core - Agentic AI Framework for CARL

This implements an agentic pattern where Claude autonomously decides which tools to use.
The agent can call multiple tools in sequence based on what information it needs.

Key concepts:
- ONE agent (Claude Sonnet 4.5) with multiple tools
- Agent decides autonomously which tools to call and when
- Tools are Python functions that return data
- Framework handles the tool-calling protocol and conversation loop

This is NOT multiple agents being orchestrated - it's ONE agent making autonomous decisions.
"""

import json
from typing import Any, Callable, Optional
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal

import boto3

from utils.logger import get_logger

logger = get_logger(__name__)


def sanitize_for_bedrock(obj: Any) -> Any:
    """
    Sanitize Python objects to be JSON-serializable for Bedrock Converse API.

    Converts:
    - Enum → string value (e.g., CostTier.MINIMAL → "MINIMAL")
    - tuple → list (e.g., (50, 200) → [50, 200])
    - Decimal → int or float (e.g., Decimal('1777515653') → 1777515653)
    - Recursively processes nested dicts and lists

    Args:
        obj: Python object that may contain non-serializable types

    Returns:
        JSON-serializable version of the object
    """
    # Handle None
    if obj is None:
        return None

    # Handle Enum - convert to string value
    if isinstance(obj, Enum):
        return obj.value

    # Handle tuple - convert to list
    if isinstance(obj, tuple):
        return [sanitize_for_bedrock(item) for item in obj]

    # Handle Decimal - convert to int or float
    if isinstance(obj, Decimal):
        # If it's a whole number, return int; otherwise float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)

    # Handle dict - recursively sanitize values
    if isinstance(obj, dict):
        return {key: sanitize_for_bedrock(value) for key, value in obj.items()}

    # Handle list - recursively sanitize items
    if isinstance(obj, list):
        return [sanitize_for_bedrock(item) for item in obj]

    # Handle primitives (str, int, float, bool) - return as-is
    if isinstance(obj, (str, int, float, bool)):
        return obj

    # For any other type, try to convert to string as fallback
    try:
        return str(obj)
    except Exception as e:
        logger.warning(f"Could not sanitize object of type {type(obj)}: {e}")
        return None


@dataclass
class Tool:
    """
    A tool that the agent can call.

    Tools are Python functions that the agent can invoke to gather information.
    The agent decides when to call which tool based on the user's question.
    """
    name: str
    description: str
    function: Callable
    input_schema: dict


class AgentCore:
    """
    Core agentic AI framework using Bedrock's Converse API.

    This implements the agentic loop:
    1. Agent receives question
    2. Agent decides which tool(s) to call (if any)
    3. Framework executes the tool
    4. Framework returns result to agent
    5. Agent decides what to do next (call more tools or respond)
    6. Repeat until agent generates final response
    """

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        system_instructions: str = "",
        max_turns: int = 10,
        region: str = "us-east-1",
        progress_callback: Callable[[str], None] = None
    ):
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = model_id
        self.system_instructions = system_instructions
        self.max_turns = max_turns
        self.tools = []
        self.tool_map = {}
        self.progress_callback = progress_callback

    def add_tool(self, tool: Tool):
        """Register a tool that the agent can call."""
        self.tools.append(tool)
        self.tool_map[tool.name] = tool.function
        logger.info(f"Registered tool: {tool.name}")

    def execute(
        self,
        user_message: str,
        conversation_history: list[dict] = None
    ) -> str:
        """
        Execute the agent with autonomous tool calling.

        The agent will:
        1. Analyze the user's question
        2. Decide which tools (if any) to call
        3. Call tools autonomously
        4. Reason about the results
        5. Call more tools if needed
        6. Generate final response

        Args:
            user_message: The user's question or request
            conversation_history: Optional prior messages for context

        Returns:
            The agent's final response after calling any necessary tools
        """
        # Initialize conversation
        messages = conversation_history or []
        messages.append({
            "role": "user",
            "content": [{"text": user_message}]
        })

        # Convert tools to Bedrock format
        tool_config = self._build_tool_config()

        # Agentic loop - agent decides what to do at each turn
        for turn in range(self.max_turns):
            logger.info(f"[Turn {turn + 1}] Agent thinking...")

            # Report progress
            if self.progress_callback:
                self.progress_callback(f"🔄 Turn {turn + 1}: Analyzing...")

            try:
                # Call Bedrock with tools available
                request = {
                    "modelId": self.model_id,
                    "messages": messages,
                }

                if self.system_instructions:
                    request["system"] = [{"text": self.system_instructions}]

                if tool_config:
                    request["toolConfig"] = tool_config

                response = self.bedrock.converse(**request)

                # Get agent's response
                stop_reason = response["stopReason"]
                output_message = response["output"]["message"]

                # Add agent's response to conversation
                messages.append(output_message)

                # Check what agent decided to do
                if stop_reason == "end_turn":
                    # Agent is done - return final response
                    logger.info(f"[Turn {turn + 1}] Agent finished")
                    if self.progress_callback:
                        self.progress_callback(f"✅ Analysis complete, generating recommendation...")
                    return self._extract_text_response(output_message)

                elif stop_reason == "tool_use":
                    # Agent wants to call tool(s)
                    logger.info(f"[Turn {turn + 1}] Agent calling tools")

                    # Collect tool names for progress update
                    tool_names = []
                    for content_block in output_message["content"]:
                        if "toolUse" in content_block:
                            tool_names.append(content_block["toolUse"]["name"])

                    # Report progress
                    if self.progress_callback and tool_names:
                        tools_str = ", ".join(tool_names)
                        self.progress_callback(f"🔧 Turn {turn + 1}: Calling {len(tool_names)} tool(s) ({tools_str})")

                    # Execute all requested tools
                    tool_results = []
                    for content_block in output_message["content"]:
                        if "toolUse" in content_block:
                            tool_use = content_block["toolUse"]
                            tool_name = tool_use["name"]
                            tool_input = tool_use["input"]
                            tool_use_id = tool_use["toolUseId"]

                            logger.info(f"  → Calling tool: {tool_name}")
                            logger.debug(f"    Input: {json.dumps(tool_input, indent=2)}")

                            # Execute the tool
                            try:
                                result = self._execute_tool(tool_name, tool_input)
                                logger.info(f"  ✓ Tool {tool_name} completed")
                                logger.debug(f"    Result: {str(result)[:200]}...")

                                # Sanitize result to ensure it's JSON-serializable for Bedrock
                                sanitized_result = sanitize_for_bedrock(result)

                                tool_results.append({
                                    "toolUseId": tool_use_id,
                                    "content": [{"json": {"result": sanitized_result}}]
                                })
                            except Exception as e:
                                logger.error(f"  ✗ Tool {tool_name} failed: {e}")
                                tool_results.append({
                                    "toolUseId": tool_use_id,
                                    "content": [{"text": f"Error: {str(e)}"}],
                                    "status": "error"
                                })

                    # Add tool results to conversation
                    messages.append({
                        "role": "user",
                        "content": [{"toolResult": result} for result in tool_results]
                    })

                    # Loop continues - agent will process results and decide next step

                else:
                    logger.warning(f"Unexpected stop reason: {stop_reason}")
                    return self._extract_text_response(output_message)

            except Exception as e:
                logger.exception(f"Error in agent turn {turn + 1}")
                return f"I encountered an error: {str(e)}"

        # Max turns reached
        logger.warning(f"Agent reached max turns ({self.max_turns})")
        return "I've analyzed your question thoroughly but need to gather more information. Could you be more specific about what you'd like to know?"

    def _build_tool_config(self) -> Optional[dict]:
        """Convert registered tools to Bedrock tool config format."""
        if not self.tools:
            return None

        tool_specs = []
        for tool in self.tools:
            tool_specs.append({
                "toolSpec": {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": {
                        "json": tool.input_schema
                    }
                }
            })

        return {"tools": tool_specs}

    def _execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool function."""
        if tool_name not in self.tool_map:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_function = self.tool_map[tool_name]

        # Call the tool function with unpacked arguments
        return tool_function(**tool_input)

    def _extract_text_response(self, message: dict) -> str:
        """Extract text from agent's response message."""
        text_parts = []
        for content_block in message.get("content", []):
            if "text" in content_block:
                text_parts.append(content_block["text"])
        return "\n\n".join(text_parts)


class Agent:
    """
    High-level Agent interface for creating agents with tools.

    This is the main API for creating agentic workflows in CARL.

    Example:
        agent = Agent(
            tools=[
                Tool(name="scan_aws", function=scan_aws_function, ...),
                Tool(name="get_pricing", function=pricing_function, ...)
            ],
            instructions="You are an AWS architect..."
        )

        response = agent.execute("Design a VPC for me")
        # Agent autonomously decides which tools to call
    """

    def __init__(
        self,
        tools: list[Tool] = None,
        instructions: str = "",
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        max_turns: int = 10,
        progress_callback: Callable[[str], None] = None
    ):
        self.core = AgentCore(
            model_id=model_id,
            system_instructions=instructions,
            max_turns=max_turns,
            progress_callback=progress_callback
        )

        # Register tools
        if tools:
            for tool in tools:
                self.core.add_tool(tool)

    def execute(self, question: str) -> str:
        """Execute the agent with a user question."""
        return self.core.execute(question)
