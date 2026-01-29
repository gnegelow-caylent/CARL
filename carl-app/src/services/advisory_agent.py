"""
Advisory Agent - Intelligent Q&A with environment awareness and compliance knowledge.

This agent provides intelligent question-answering that:
1. Understands complex questions about AWS and compliance
2. Scans relevant parts of your environment
3. Provides tailored recommendations based on what you HAVE
4. Factors in SOC 2 compliance requirements
5. Asks clarifying questions when needed
6. Hands off to Architect Agent for code generation

Uses AWS Bedrock Agents for autonomous multi-step reasoning.

IMPORTANT: This agent only READS from AWS - it never makes changes.
It provides recommendations and can hand off to other agents for implementation.
"""

import json
import boto3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AdvisoryAgent:
    """
    Autonomous advisory agent using AWS Bedrock Agents.

    This wraps the Bedrock Agent service and provides advisory-specific
    tools for environment scanning, analysis, and intelligent recommendations.
    """

    def __init__(self, agent_id: Optional[str] = None, agent_alias_id: str = "PROD"):
        """
        Initialize advisory agent.

        Args:
            agent_id: Bedrock Agent ID (if None, must be configured via env var)
            agent_alias_id: Agent alias name or ID (PROD, DEV, etc.)
        """
        self.client = boto3.client('bedrock-agent-runtime')
        self.bedrock_agent_client = boto3.client('bedrock-agent')
        self.agent_id = agent_id

        # Resolve alias name to ID if needed
        if agent_id:
            self.agent_alias_id = self._resolve_alias_id(agent_id, agent_alias_id)
        else:
            self.agent_alias_id = agent_alias_id

    def _resolve_alias_id(self, agent_id: str, alias_name_or_id: str) -> str:
        """
        Resolve alias name to ID. If already an ID, return as-is.

        Args:
            agent_id: Bedrock Agent ID
            alias_name_or_id: Alias name (e.g., "PROD") or ID

        Returns:
            Alias ID
        """
        # If it looks like an ID (alphanumeric, ~10 chars), return as-is
        if len(alias_name_or_id) > 5 and alias_name_or_id.isalnum():
            return alias_name_or_id

        # Otherwise, look up by name
        try:
            response = self.bedrock_agent_client.list_agent_aliases(
                agentId=agent_id,
                maxResults=10
            )

            for alias_summary in response.get('agentAliasSummaries', []):
                if alias_summary['agentAliasName'] == alias_name_or_id:
                    return alias_summary['agentAliasId']

            # If not found, return the input (will fail later with better error)
            logger.warning(f"Alias '{alias_name_or_id}' not found, using as-is")
            return alias_name_or_id

        except Exception as e:
            logger.warning(f"Failed to resolve alias name: {e}")
            return alias_name_or_id

    def ask_question(
        self,
        question: str,
        session_id: Optional[str] = None,
        enable_trace: bool = False
    ) -> Dict[str, Any]:
        """
        Ask the advisory agent a question.

        The agent will autonomously:
        1. Analyze the question to understand intent
        2. Determine what AWS resources to scan
        3. Scan your environment (targeted, not full scan)
        4. Analyze with compliance knowledge (SOC 2)
        5. Provide tailored recommendations
        6. Ask clarifying questions if needed
        7. Hand off to Architect Agent if code generation requested

        Args:
            question: User's question (e.g., "How do I stand up a web server?")
            session_id: Optional session ID for conversation continuity
            enable_trace: Enable trace for debugging

        Returns:
            Dict with response, actions taken, and metadata
        """
        if not self.agent_id:
            raise ValueError("Advisory Agent ID not configured. Set ADVISORY_AGENT_ID environment variable.")

        # Generate session ID if not provided
        if not session_id:
            import uuid
            session_id = f"advisory-{uuid.uuid4()}"

        logger.info(f"Advisory Agent invoked with question: {question[:100]}...")

        try:
            # Invoke the Bedrock Agent
            response = self.client.invoke_agent(
                agentId=self.agent_id,
                agentAliasId=self.agent_alias_id,
                sessionId=session_id,
                inputText=question,
                enableTrace=enable_trace
            )

            # Parse the agent's response
            result = self._parse_agent_response(response)

            logger.info(f"Advisory Agent completed. Actions: {len(result.get('actions', []))}")
            return result

        except Exception as e:
            logger.error(f"Advisory Agent failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"Advisory Agent encountered an error: {str(e)}",
                "actions": [],
                "metadata": {
                    "session_id": session_id,
                    "error_type": type(e).__name__
                }
            }

    def _parse_agent_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the agent's response stream.

        Args:
            response: Response from invoke_agent

        Returns:
            Parsed result with response text, actions taken, and metadata
        """
        response_text = ""
        actions_taken = []
        trace_data = []

        try:
            # Process the event stream
            event_stream = response.get('completion', [])

            for event in event_stream:
                if 'chunk' in event:
                    # Extract response text
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        response_text += chunk['bytes'].decode('utf-8')

                elif 'trace' in event:
                    # Extract trace information (tool calls, reasoning)
                    trace = event['trace']
                    trace_data.append(trace)

                    # Extract actions from trace
                    if 'orchestrationTrace' in trace:
                        orch = trace['orchestrationTrace']
                        if 'observation' in orch:
                            obs = orch['observation']
                            if 'actionGroupInvocationOutput' in obs:
                                action_output = obs['actionGroupInvocationOutput']
                                actions_taken.append({
                                    'action': action_output.get('text', ''),
                                    'timestamp': datetime.utcnow().isoformat()
                                })

        except Exception as e:
            logger.error(f"Error parsing agent response: {e}")
            response_text = "Error processing agent response."

        return {
            "success": True,
            "response": response_text.strip() if response_text else "No response from agent.",
            "actions": actions_taken,
            "metadata": {
                "actions_count": len(actions_taken),
                "trace_available": len(trace_data) > 0,
                "completed_at": datetime.utcnow().isoformat()
            }
        }

    def continue_conversation(
        self,
        follow_up: str,
        session_id: str,
        enable_trace: bool = False
    ) -> Dict[str, Any]:
        """
        Continue an existing conversation with the agent.

        Args:
            follow_up: Follow-up question or response
            session_id: Session ID from previous interaction
            enable_trace: Enable trace for debugging

        Returns:
            Dict with response, actions taken, and metadata
        """
        return self.ask_question(
            question=follow_up,
            session_id=session_id,
            enable_trace=enable_trace
        )


# Agent Tool Definitions (for reference - configured in AWS Bedrock Console)
ADVISORY_AGENT_TOOLS = {
    "scan_environment": {
        "description": "Scan specific AWS resources based on the question context",
        "parameters": {
            "resource_types": "List of AWS resource types to scan (e.g., ['vpc', 'ec2', 's3'])",
            "region": "AWS region to scan (default: current region)"
        },
        "returns": "JSON with scanned resource details"
    },
    "get_compliance_requirements": {
        "description": "Get SOC 2 compliance requirements for a specific resource type or scenario",
        "parameters": {
            "resource_type": "AWS resource type (e.g., 'ec2', 's3', 'rds')",
            "scenario": "Use case scenario (e.g., 'web server', 'database', 'file storage')"
        },
        "returns": "SOC 2 controls and requirements"
    },
    "analyze_architecture": {
        "description": "Analyze current architecture and identify patterns, gaps, or opportunities",
        "parameters": {
            "resources": "Resources to analyze (from scan_environment)",
            "intent": "What the user wants to achieve"
        },
        "returns": "Analysis with recommendations"
    },
    "get_best_practices": {
        "description": "Get AWS best practices for a specific scenario with compliance context",
        "parameters": {
            "scenario": "What the user is trying to do",
            "compliance_framework": "Compliance framework to consider (default: soc2)"
        },
        "returns": "Best practices and recommendations"
    },
    "check_existing_resources": {
        "description": "Check if specific resources already exist in the environment",
        "parameters": {
            "resource_type": "Type of resource to check",
            "filters": "Optional filters (e.g., tags, names)"
        },
        "returns": "Existing resources matching criteria"
    },
    "ask_clarification": {
        "description": "Ask the user a clarifying question when more information is needed",
        "parameters": {
            "question": "Question to ask the user",
            "options": "Optional multiple choice options"
        },
        "returns": "Signal to wait for user response"
    },
    "handoff_to_architect": {
        "description": "Hand off to Architect Agent for infrastructure code generation",
        "parameters": {
            "requirements": "Gathered requirements and context",
            "resources": "Existing resources to consider"
        },
        "returns": "Handoff confirmation"
    }
}


# Example Lambda function handler for agent tools
def advisory_agent_tool_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function handler for Advisory Agent tools.

    This function is called by Bedrock Agent when it needs to use a tool.

    Args:
        event: Event from Bedrock Agent with action_group, function, and parameters
        context: Lambda context

    Returns:
        Tool execution result
    """
    function_name = event.get('function', '')
    parameters = event.get('parameters', {})

    logger.info(f"Advisory Agent tool called: {function_name}")

    try:
        if function_name == 'scan_environment':
            return _tool_scan_environment(parameters)
        elif function_name == 'get_compliance_requirements':
            return _tool_get_compliance_requirements(parameters)
        elif function_name == 'analyze_architecture':
            return _tool_analyze_architecture(parameters)
        elif function_name == 'get_best_practices':
            return _tool_get_best_practices(parameters)
        elif function_name == 'check_existing_resources':
            return _tool_check_existing_resources(parameters)
        elif function_name == 'ask_clarification':
            return _tool_ask_clarification(parameters)
        elif function_name == 'handoff_to_architect':
            return _tool_handoff_to_architect(parameters)
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unknown function: {function_name}"})
            }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def _tool_scan_environment(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Scan environment tool implementation."""
    from services.evidence_collector import EvidenceCollector
    import os

    resource_types = parameters.get('resource_types', [])

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")

    collector = EvidenceCollector(
        evidence_bucket=evidence_bucket,
        evidence_table=evidence_table
    )

    results = {}

    for resource_type in resource_types:
        if resource_type.lower() == 'vpc':
            results['vpc'] = collector.collect_vpc_evidence()
        elif resource_type.lower() == 's3':
            results['s3'] = collector.collect_s3_evidence()
        elif resource_type.lower() == 'iam':
            results['iam'] = collector.collect_iam_evidence()
        elif resource_type.lower() == 'cloudtrail':
            results['cloudtrail'] = collector.collect_cloudtrail_evidence()
        elif resource_type.lower() == 'securityhub':
            results['securityhub'] = collector.collect_securityhub_evidence()

    return {
        "statusCode": 200,
        "body": json.dumps({
            "resources": results,
            "scanned_types": resource_types
        }, default=str)
    }


def _tool_get_compliance_requirements(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get compliance requirements tool implementation."""
    # This would map resource types to SOC 2 controls
    # Simplified version here

    resource_type = parameters.get('resource_type', '')
    scenario = parameters.get('scenario', '')

    # Map to SOC 2 controls
    requirements = {
        "ec2": ["CC6.1 (Access Controls)", "CC6.6 (Encryption)", "CC7.2 (Monitoring)"],
        "s3": ["CC6.6 (Encryption at Rest)", "CC6.1 (Access Controls)", "CC7.2 (Logging)"],
        "rds": ["CC6.6 (Encryption)", "CC8.1 (Backups)", "A1.2 (Availability)"],
        "web_server": ["CC6.7 (Encryption in Transit)", "CC6.1 (Access Controls)", "CC7.2 (Logging)"]
    }

    key = scenario if scenario else resource_type
    controls = requirements.get(key.lower(), ["CC6.1 (Access Controls)", "CC7.2 (Monitoring)"])

    return {
        "statusCode": 200,
        "body": json.dumps({
            "resource_type": resource_type,
            "scenario": scenario,
            "soc2_controls": controls,
            "requirements": [
                "Enable encryption at rest",
                "Configure proper access controls (IAM, security groups)",
                "Enable logging and monitoring (CloudTrail, CloudWatch)",
                "Implement least privilege access"
            ]
        })
    }


def _tool_analyze_architecture(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze architecture tool implementation."""
    resources = parameters.get('resources', {})
    intent = parameters.get('intent', '')

    # Analyze what exists
    analysis = {
        "existing": {},
        "gaps": [],
        "recommendations": []
    }

    # Example analysis logic
    if 'vpc' in resources:
        vpcs = resources['vpc']
        analysis['existing']['vpcs'] = len(vpcs)

        if len(vpcs) == 0:
            analysis['gaps'].append("No VPCs found")
            analysis['recommendations'].append("Create a VPC with public and private subnets")

    if 's3' in resources:
        buckets = resources['s3']
        analysis['existing']['s3_buckets'] = len(buckets)

    return {
        "statusCode": 200,
        "body": json.dumps(analysis, default=str)
    }


def _tool_get_best_practices(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get best practices tool implementation."""
    scenario = parameters.get('scenario', '')

    best_practices = {
        "general": [
            "Use VPCs with private and public subnets",
            "Enable encryption at rest and in transit",
            "Implement least privilege IAM policies",
            "Enable CloudTrail and VPC Flow Logs",
            "Use Security Groups as firewalls"
        ]
    }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "scenario": scenario,
            "best_practices": best_practices.get(scenario.lower(), best_practices['general'])
        })
    }


def _tool_check_existing_resources(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Check existing resources tool implementation."""
    resource_type = parameters.get('resource_type', '')

    # Would query AWS APIs here
    return {
        "statusCode": 200,
        "body": json.dumps({
            "resource_type": resource_type,
            "exists": False,
            "count": 0
        })
    }


def _tool_ask_clarification(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Ask clarification tool implementation."""
    question = parameters.get('question', '')
    options = parameters.get('options', [])

    return {
        "statusCode": 200,
        "body": json.dumps({
            "clarification_needed": True,
            "question": question,
            "options": options
        })
    }


def _tool_handoff_to_architect(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Handoff to architect tool implementation."""
    requirements = parameters.get('requirements', {})

    return {
        "statusCode": 200,
        "body": json.dumps({
            "handoff": "architect",
            "requirements": requirements,
            "message": "Requirements gathered, ready for code generation"
        })
    }
