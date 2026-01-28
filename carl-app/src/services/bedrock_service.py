"""
Bedrock Service for CARL AI capabilities.
"""

import json
import os
from typing import Any

import boto3

from utils.logger import get_logger

logger = get_logger(__name__)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0"
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """You are CARL (Cloud Automated Risk & Compliance Logic), an AI assistant specialized in AWS compliance and security. You help users understand and remediate compliance findings, particularly for SOC 2.

Your capabilities:
- Explain compliance findings in plain language
- Provide remediation guidance for AWS security issues
- Answer questions about SOC 2 controls and requirements
- Recommend AWS security best practices

Guidelines:
- Be concise and actionable
- Prioritize security without being alarmist
- Reference specific AWS services and configurations
- Acknowledge when you're uncertain
- Never recommend disabling security controls unless absolutely necessary

SOC 2 Trust Service Criteria you're familiar with:
- CC6: Logical and Physical Access Controls
- CC7: System Operations (monitoring, incident response)
- A1: Availability
- C1: Confidentiality
- PI1: Processing Integrity
- P1: Privacy

When explaining findings, always include:
1. What the issue is (plain language)
2. Why it matters (risk/impact)
3. How to fix it (specific steps)
"""


class BedrockService:
    """Service for interacting with Amazon Bedrock."""

    def __init__(self):
        self.client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        self.model_id = BEDROCK_MODEL_ID

    def invoke_model(
        self,
        prompt: str,
        system_prompt: str = SYSTEM_PROMPT,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        """Invoke Bedrock model with prompt."""
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except Exception as e:
            logger.exception("Error invoking Bedrock model")
            return f"I encountered an error processing your request: {str(e)}"

    def ask_compliance_question(self, question: str, context: str = "") -> str:
        """Answer a compliance-related question."""
        prompt = f"""Context about the current environment:
{context}

User question: {question}

Please provide a helpful, concise answer based on the context and your knowledge of AWS compliance and SOC 2."""

        return self.invoke_model(prompt)

    def explain_finding(self, finding: dict[str, Any]) -> str:
        """Explain a security finding in plain language."""
        prompt = f"""Please explain this security finding:

Finding Details:
- Title: {finding.get('title', 'Unknown')}
- Severity: {finding.get('severity', 'Unknown')}
- Source: {finding.get('source', 'Unknown')}
- Resource: {finding.get('resource_id', 'Unknown')} ({finding.get('resource_type', 'Unknown')})
- Description: {finding.get('description', 'No description')}
- SOC 2 Controls: {', '.join(finding.get('control_ids', []))}

Provide:
1. A plain-language explanation of what this means
2. The potential security risk if not addressed
3. Specific remediation steps for AWS
4. Any relevant SOC 2 compliance implications"""

        return self.invoke_model(prompt)

    def suggest_remediation(self, finding: dict[str, Any]) -> str:
        """Suggest remediation steps for a finding."""
        prompt = f"""Suggest remediation for this AWS security finding:

Finding:
- Title: {finding.get('title', 'Unknown')}
- Resource Type: {finding.get('resource_type', 'Unknown')}
- Resource ID: {finding.get('resource_id', 'Unknown')}
- Current Issue: {finding.get('description', 'Unknown')}

Provide step-by-step remediation instructions using:
1. AWS Console steps (for manual remediation)
2. AWS CLI commands (for automation)
3. Any Terraform/CloudFormation considerations
4. Post-remediation verification steps

Be specific and actionable."""

        return self.invoke_model(prompt, max_tokens=2048)

    def generate_executive_summary(
        self, summary: dict[str, Any], findings: list[dict]
    ) -> str:
        """Generate an executive summary of compliance status."""
        prompt = f"""Generate a brief executive summary of the compliance status:

Compliance Summary:
- Critical Findings: {summary.get('critical', 0)}
- High Findings: {summary.get('high', 0)}
- Medium Findings: {summary.get('medium', 0)}
- Low Findings: {summary.get('low', 0)}
- Total Open: {summary.get('total', 0)}

Recent High-Priority Findings:
{json.dumps(findings[:5], indent=2)}

Write a 2-3 paragraph executive summary covering:
1. Overall compliance posture
2. Key risk areas requiring attention
3. Recommended priorities for remediation

Keep it concise and business-focused."""

        return self.invoke_model(prompt)

    def analyze_risk(self, findings: list[dict]) -> str:
        """Analyze risk across multiple findings."""
        prompt = f"""Analyze the risk across these findings:

Findings:
{json.dumps(findings, indent=2)}

Provide:
1. Pattern analysis - are there common issues?
2. Attack path considerations - how might these be chained?
3. Prioritization recommendations
4. Quick wins vs. larger remediation efforts"""

        return self.invoke_model(prompt, max_tokens=2048)
