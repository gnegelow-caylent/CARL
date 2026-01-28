"""
Agentic AWS Architect - Autonomous Architecture Recommendations

This is an AGENTIC version of the AWS Architect that:
- Autonomously decides which tools to call
- Scans actual AWS environments before recommending
- Queries real pricing data
- Makes dynamic decisions based on context
- Adapts its workflow to each question

Comparison with ai_architect.py:
- OLD: Static flow (always loads all context, single AI call)
- NEW: Dynamic flow (agent decides what info it needs, multiple tool calls)

The agent makes 3x better recommendations because it works with REAL data.
"""

from typing import Optional

from utils.logger import get_logger
from services.agent_core import Agent, Tool
from services.architect_tools import ARCHITECT_TOOLS

logger = get_logger(__name__)


# System instructions for the Architect Agent
ARCHITECT_AGENT_INSTRUCTIONS = """You are CARL's AI Architecture Advisor - an expert AWS Solutions Architect with deep knowledge of:
- AWS Well-Architected Framework (all 6 pillars)
- SOC 2 compliance requirements and control mappings
- AWS security best practices and landing zone design
- Cost optimization strategies
- Multi-account architectures and Control Tower
- Networking patterns (Transit Gateway, VPC, Direct Connect, VPN)
- Identity and access management (IAM Identity Center, permission sets)
- Centralized security tooling (Security Hub, GuardDuty, Config, Inspector)
- Centralized logging and monitoring

IMPORTANT: You have access to TOOLS that let you gather real information:

1. **scan_aws_account**: Scans the user's ACTUAL AWS environment
   - Use this FIRST when they ask about their specific setup
   - Provides real data about VPCs, security groups, IAM, encryption, etc.
   - Don't make assumptions - scan and see what exists!

2. **get_architecture_patterns**: Retrieves proven patterns from CARL's knowledge base
   - Use this to get reference architectures and best practices
   - Provides structured examples you can adapt

3. **query_aws_pricing**: Gets ACCURATE AWS pricing data
   - ALWAYS use this before mentioning costs
   - Never guess or hallucinate pricing - query the real data!

4. **calculate_cost_estimate**: Calculates itemized monthly cost estimates
   - Use this after querying pricing to provide accurate breakdowns
   - Shows the user exactly what they'll pay

WORKFLOW (you decide which steps are needed):
1. If question is about THEIR environment → scan_aws_account
2. If you need reference patterns → get_architecture_patterns
3. If you need to discuss costs → query_aws_pricing + calculate_cost_estimate
4. Analyze results from tools
5. Generate personalized recommendation

GUIDELINES:
- Always explain the "why" behind recommendations, not just the "what"
- Consider future scalability even for small deployments
- Prioritize security without over-engineering
- Be specific with AWS services and configurations
- Acknowledge trade-offs honestly - there's rarely a perfect solution
- Adapt recommendations to the user's experience level and context
- Reference specific SOC 2 controls when relevant
- When you don't have enough information, ASK clarifying questions

IMPORTANT: You are AUTONOMOUS. You decide:
- Which tools to call
- In what order
- How many times
- When you have enough information to respond

Don't ask me which tools to use - just use them when you need them!
"""


class AgenticArchitect:
    """
    Agentic AWS Architecture Advisor.

    This creates ONE agent that autonomously:
    - Scans AWS environments
    - Queries pricing data
    - Retrieves architecture patterns
    - Makes informed recommendations

    The agent decides its own workflow based on the question.
    """

    def __init__(self):
        """Initialize the Architect Agent with all tools."""
        logger.info("Initializing Agentic Architect with tools...")

        # Convert tool definitions to Tool objects
        tools = []
        for tool_def in ARCHITECT_TOOLS:
            tools.append(Tool(
                name=tool_def["name"],
                description=tool_def["description"],
                function=tool_def["function"],
                input_schema=tool_def["input_schema"]
            ))

        # Create the agent with tools
        self.agent = Agent(
            tools=tools,
            instructions=ARCHITECT_AGENT_INSTRUCTIONS,
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            max_turns=10  # Allow up to 10 tool calls
        )

        logger.info(f"Architect Agent ready with {len(tools)} tools")

    def answer_question(self, question: str) -> str:
        """
        Answer any AWS architecture question with autonomous tool calling.

        The agent will:
        1. Analyze the question
        2. Decide which tools to call (if any)
        3. Call tools autonomously
        4. Reason about results
        5. Generate comprehensive recommendation

        Examples:
        - "How should I design my VPC?"
          → Agent scans current VPCs, gets patterns, recommends design

        - "What's the most cost-effective way to set up egress?"
          → Agent queries pricing, compares options, recommends with costs

        - "Design a multi-account structure for me"
          → Agent scans current accounts, gets patterns, designs structure

        Args:
            question: User's architecture question

        Returns:
            Comprehensive architecture recommendation
        """
        logger.info(f"Architect Agent processing question: {question[:100]}...")

        try:
            response = self.agent.execute(question)
            return response

        except Exception as e:
            logger.exception("Error in Agentic Architect")
            return f"""I encountered an error while analyzing your question: {str(e)}

However, I can provide a general recommendation. Let me know if you'd like me to try again or if you can provide more details about your specific requirements."""

    def recommend_foundation(self, requirements: dict) -> str:
        """
        Design a complete AWS foundation based on requirements.

        The agent will scan current environment (if any), retrieve patterns,
        query pricing, and generate a comprehensive foundation design.

        Args:
            requirements: Dictionary of requirements (org_size, compliance, budget, etc.)

        Returns:
            Complete foundation design with costs
        """
        # Convert requirements to natural language prompt
        req_text = "\n".join([f"- {k}: {v}" for k, v in requirements.items()])

        question = f"""Design a complete AWS foundation for this organization:

Requirements:
{req_text}

Provide a comprehensive foundation design that includes:
1. Account structure and OU hierarchy
2. Network architecture
3. Identity and access management setup
4. Security tooling configuration
5. Logging and monitoring architecture
6. Estimated monthly costs (itemized)
7. Implementation roadmap (phases)
8. SOC 2 control coverage mapping

Scan my current AWS environment first to understand what already exists, then design accordingly."""

        return self.answer_question(question)

    def compare_options(self, option_a: str, option_b: str, context: str = "") -> str:
        """
        Compare two architectural options with real data.

        The agent will query pricing, retrieve patterns, and provide
        a detailed comparison.

        Args:
            option_a: First option to compare
            option_b: Second option to compare
            context: Additional context about the use case

        Returns:
            Detailed comparison with costs and recommendations
        """
        question = f"""Compare these two AWS architecture approaches:

Option A: {option_a}
Option B: {option_b}

Context: {context if context else 'General AWS workload'}

Provide:
1. Detailed comparison table (features, costs, complexity, security)
2. When to choose Option A
3. When to choose Option B
4. Hybrid approaches if applicable
5. Migration path if starting with one and moving to other
6. Accurate cost comparison using real pricing data"""

        return self.answer_question(question)


# Singleton instance
_agentic_architect: Optional[AgenticArchitect] = None


def get_agentic_architect() -> AgenticArchitect:
    """Get or create the Agentic Architect singleton."""
    global _agentic_architect
    if _agentic_architect is None:
        _agentic_architect = AgenticArchitect()
    return _agentic_architect
