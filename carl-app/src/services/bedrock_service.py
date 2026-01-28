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
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
# Use BEDROCK_REGION first, fall back to AWS_REGION, default to us-east-1
AWS_REGION = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "us-east-1")

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
        prompt = f"""You are a compliance assistant. Answer clearly and concisely.

Environment scan results:
{context}

Question: {question}

CRITICAL FORMATTING RULES (Slack markdown):
- Use *text* for bold (single asterisk), NOT **text**
- NO markdown headers (#, ##) - use *Section Name* on its own line instead
- NO horizontal rules (---) - use blank lines to separate sections
- Each bullet must start on a new line with proper spacing
- Keep explanations to ONE sentence per bullet

Example format:

*Compliance Status: NOT COMPLIANT*

*Critical Issues (Fix Immediately)*
• *No CloudTrail enabled*: Enable CloudTrail to log all API activity (AWS Console → CloudTrail → Create trail → All regions → Enable)
• *Root MFA disabled*: Enable MFA on root account immediately (AWS Console → My Security Credentials → MFA → Activate MFA)

*High Priority Issues*
• *1 user without MFA (username)*: Enable MFA for this user (AWS Console → IAM → Users → username → Security credentials → Assign MFA)
• *No password policy*: Create password policy (AWS Console → IAM → Account settings → Password policy)

*Immediate Action Plan*
Today: Enable CloudTrail, Enable root MFA
This week: Fix all MFA gaps, Create password policy

Keep total response under 800 words. No introductions or closings. Start with most critical issues."""

        return self.invoke_model(prompt, max_tokens=1024)

    def explain_finding(self, finding: dict[str, Any]) -> str:
        """Explain a security finding in plain language."""
        prompt = f"""Explain this security finding briefly:

*Finding:* {finding.get('title', 'Unknown')}
*Severity:* {finding.get('severity', 'Unknown')}
*Resource:* {finding.get('resource_id', 'Unknown')} ({finding.get('resource_type', 'Unknown')})
*Description:* {finding.get('description', 'No description')}
*SOC 2 Controls:* {', '.join(finding.get('control_ids', []))}

SLACK FORMATTING RULES:
- Use *text* for bold (single asterisk), NOT **text**
- NO markdown headers (#, ##) - use *Section Name* instead
- NO horizontal rules (---)
- Use bullet points with •

Format (max 300 words):

*What This Means*
[1-2 sentences]

*Security Risk*
[1 sentence]

*How to Fix*
• Step 1
• Step 2
• Step 3

*SOC 2 Impact*
[1 sentence about which control this affects]"""

        return self.invoke_model(prompt, max_tokens=512)

    def suggest_remediation(self, finding: dict[str, Any]) -> str:
        """Suggest remediation steps for a finding."""
        prompt = f"""Fix this AWS security issue:

*Issue:* {finding.get('title', 'Unknown')}
*Resource:* {finding.get('resource_id', 'Unknown')} ({finding.get('resource_type', 'Unknown')})
*Problem:* {finding.get('description', 'Unknown')}

SLACK FORMATTING RULES:
- Use *text* for bold (single asterisk), NOT **text**
- NO markdown headers (#, ##) - use *Section Name* instead
- Code blocks OK with ```

Provide (max 400 words):

*AWS Console Steps*
1. [Step 1]
2. [Step 2]
3. [Step 3]

*AWS CLI*
```bash
# Command to fix
```

*Verify*
```bash
# Command to verify fix
```

Keep it brief and actionable."""

        return self.invoke_model(prompt, max_tokens=768)

    def generate_executive_summary(
        self, summary: dict[str, Any], findings: list[dict]
    ) -> str:
        """Generate an executive summary of compliance status."""
        prompt = f"""Executive summary (max 250 words):

*Findings:*
• Critical: {summary.get('critical', 0)}
• High: {summary.get('high', 0)}
• Medium: {summary.get('medium', 0)}
• Low: {summary.get('low', 0)}

*Top 5 Issues:*
{json.dumps(findings[:5], indent=2)}

SLACK FORMATTING RULES:
- Use *text* for bold (single asterisk), NOT **text**
- NO markdown headers (#, ##) - use *Section Name* instead
- NO horizontal rules (---)

Format:

*Status*
[1-2 sentences: overall compliance posture]

*Key Risks*
• [Risk area 1]
• [Risk area 2]
• [Risk area 3]

*Next Steps*
1. [Priority 1]
2. [Priority 2]
3. [Priority 3]

Be direct. No fluff."""

        return self.invoke_model(prompt, max_tokens=512)

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
