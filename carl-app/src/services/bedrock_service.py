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
        """Answer a compliance-related question using environment context."""
        has_scan_data = context and len(context.strip()) > 50

        prompt = f"""You are CARL, an AI compliance expert for AWS infrastructure and SOC 2 compliance.

Your job: Answer the user's question clearly and actionably.

ENVIRONMENT DATA AVAILABLE: {"YES - Use this data in your answer" if has_scan_data else "LIMITED - Provide general guidance"}

{f'''
SCANNED ENVIRONMENT DATA (from user's AWS account):
{context}

IMPORTANT: Use this actual data from their environment in your answer. Be specific with resource names, IDs, and configurations shown above.
''' if has_scan_data else '''
NOTE: Limited environment data available. Provide general AWS best practices and guidance, but explain what you'd need to scan to give a tailored answer.
'''}

User's Question: {question}

CRITICAL FORMATTING RULES (Slack markdown):
- Use *text* for bold (single asterisk), NOT **text**
- NO markdown headers (#, ##) - use *Section Name* on its own line instead
- NO horizontal rules (---) - use blank lines to separate sections
- Each bullet must start on a new line with proper spacing
- Keep explanations to ONE sentence per bullet

HOW TO ANSWER:
1. If environment data is available: Use REAL resource names, IDs, and configurations from the scan
2. If environment data is limited: Provide general AWS guidance and explain what you'd need to scan for a tailored answer
3. For architecture questions: ALWAYS include cost estimates and comparisons between options
4. Always provide actionable next steps (2-3 specific actions)
5. Keep total response under 500 words

COST CONSIDERATIONS (Critical):
- When recommending AWS services, ALWAYS include approximate monthly costs
- Compare options with cost tradeoffs: "Option A: $X/month (best for...), Option B: $Y/month (best for...)"
- Factor in ops overhead: "$50/month EC2 + 10 hours ops time vs $200/month managed service"
- Show break-even analysis when relevant: "VPC endpoints break even vs NAT at 160GB/month"
- Recommend best VALUE, not necessarily cheapest: Balance cost with operational complexity

Examples with scan data:
Question: "Do we have encryption at rest enabled?"
*Encryption Status: PARTIALLY ENABLED*

*What's Encrypted (from your account)*
• S3 buckets: 3/5 buckets encrypted (my-prod-data, my-backups, my-logs)
• 2 buckets NOT encrypted: my-archive-bucket, my-temp-storage

*Fix It*
1. Enable default encryption on my-archive-bucket (S3 Console → Bucket → Properties → Default encryption)
2. Enable default encryption on my-temp-storage (same steps)

Example with limited scan data:
Question: "How do I stand up a web server?"
*Web Server Deployment on AWS*

*Your Current Setup*
• I scanned your VPCs and found: vpc-abc123 in us-east-1 with 3 subnets

*Recommended Approach*
1. *Deploy EC2 instances* in your existing VPC (vpc-abc123)
2. *Add Application Load Balancer* for traffic distribution
3. *Configure security groups* to allow HTTPS (443) from internet

*SOC 2 Requirements*
• Force HTTPS with ACM certificate (CC6.7 - Encryption in Transit)
• Enable ALB access logs (CC7.2 - Monitoring)
• Restrict SSH access, no 0.0.0.0/0 (CC6.1 - Access Controls)

*Want More Detail?*
I can scan your load balancers, security groups, and provide specific recommendations. Or say "yes" and I'll hand off to the Architect Agent to generate Terraform code.

Example with cost analysis:
Question: "Should I use AWS Glue or build my own ETL on EC2?"
*ETL Solution Comparison*

*Option 1: AWS Glue (Serverless) - RECOMMENDED*
• Cost: ~$220/month (20 DPUs x 8 hours/day x 30 days x $0.44/DPU-hour)
• Best for: Minimal ops overhead, automatic scaling
• Pros: No servers to manage, pay only when running, built-in Spark
• SOC 2: CC7.2 (CloudWatch logging automatic)

*Option 2: Self-Managed EC2*
• Cost: ~$50/month (t3.large 24/7) + 20 hours/month ops time (~$330 total value)
• Best for: Custom logic, existing tools
• Pros: Full control, can use any tool
• SOC 2: CC6.1 (Must manage SSH access, patching)

*💰 Recommended: AWS Glue*
• Saves $110/month in ops time
• Scales automatically
• Less security overhead

Remember: Answer the SPECIFIC question. Include costs when relevant. Be helpful and actionable."""

        return self.invoke_model(prompt, max_tokens=1024)

    def generate_jira_ticket_description(
        self,
        finding_title: str,
        severity: str,
        resource_type: str,
        resource_id: str,
        resource_arn: str,
        account_id: str,
        region: str,
        raw_description: str,
        soc2_controls: list[str],
        compliance_status: str,
    ) -> str:
        """Generate a clear, actionable Jira ticket description using AI."""
        prompt = f"""You are writing a Jira ticket for a security finding. Write it in a clear, professional, human-friendly way that an engineer can immediately understand and act on.

FINDING DETAILS:
- Title: {finding_title}
- Severity: {severity}
- Resource Type: {resource_type}
- Resource ID: {resource_id}
- Resource ARN: {resource_arn}
- AWS Account: {account_id}
- Region: {region}
- Compliance Status: {compliance_status}
- SOC 2 Controls: {', '.join(soc2_controls) if soc2_controls else 'None'}
- Technical Description: {raw_description}

Write a Jira ticket description following these EXACT sections (use h2 headers):

## Problem Statement
Write 2-3 sentences explaining what's wrong in plain English. Avoid jargon. Make it clear why this matters.

## Business Impact
1-2 sentences on the risk if this isn't fixed. Be specific about consequences (data exposure, compliance failure, security breach, etc.)

## Affected Resource
• *Type:* {resource_type}
• *Identifier:* {resource_id}
• *ARN:* {resource_arn}
• *Account:* {account_id}
• *Region:* {region}

## Remediation Steps
Number each step clearly. Be specific with AWS console paths or CLI commands. Include verification steps.

1. [First action with specific console path or CLI command]
2. [Second action with specific details]
3. [Verification step]

## Acceptance Criteria
What needs to be true for this ticket to be considered done? Write 3-5 specific, testable criteria:
- [ ] [Specific thing that must be true]
- [ ] [Another testable condition]
- [ ] [Verification completed]

## SOC 2 Compliance
{f"This finding affects SOC 2 controls: {', '.join(soc2_controls)}" if soc2_controls else "No specific SOC 2 controls mapped yet."}
Explain briefly (1 sentence) why this matters for auditors.

## References
- AWS Documentation: [Include relevant AWS doc link if applicable]
- CARL Finding ID: {resource_id[:50]}

CRITICAL RULES:
- Write like a human, not a robot
- Be direct and actionable
- No fluff or unnecessary text
- Specific console paths, not "go to the console"
- Include actual CLI commands when relevant
- Make it so clear that anyone can follow the steps
- Keep the whole response under 600 words
- Use proper Jira markdown (## for headers, * for bullets, - [ ] for checkboxes)"""

        return self.invoke_model(prompt, max_tokens=2048, temperature=0.5)

    def generate_drift_ticket_description(
        self,
        resource_type: str,
        resource_id: str,
        drift_type: str,
        attribute: str,
        expected_value: str,
        actual_value: str,
        severity: str,
        environment: str
    ) -> str:
        """Generate a clear, actionable Jira ticket for configuration drift."""
        prompt = f"""You are writing a Jira ticket for a configuration drift detection. Make it clear what changed, why it matters, and how to fix it.

DRIFT DETAILS:
- Resource Type: {resource_type}
- Resource ID: {resource_id}
- Drift Type: {drift_type}
- Attribute Changed: {attribute}
- Expected Value: {expected_value}
- Actual Value: {actual_value}
- Severity: {severity}
- Environment: {environment}

Write a Jira ticket description following these EXACT sections:

## What Changed
Explain in 1-2 sentences what configuration drift was detected. Be specific about the resource and what changed.

## Impact
1-2 sentences on why this drift matters. Explain security implications, compliance risks, or operational impact.

## Drift Details
• *Resource:* {resource_type} - {resource_id}
• *Attribute:* {attribute}
• *Expected:* {expected_value}
• *Actual:* {actual_value}
• *Environment:* {environment}

## Root Cause Analysis
What likely caused this drift? Consider:
- Manual changes via AWS console
- Automated scripts or tools
- Failed deployments
- External processes

## Remediation Steps
Provide specific steps to fix this drift:

1. [Verify the change was not intentional]
2. [Specific AWS console path or CLI command to restore expected value]
3. [Verify the change took effect]
4. [Document the change in change log]

## Prevention
How to prevent this drift from happening again:
- [ ] [Specific control or process]
- [ ] [Monitoring or alerting]
- [ ] [Infrastructure as code update]

## Acceptance Criteria
- [ ] Resource configuration matches expected value
- [ ] Change is documented
- [ ] Drift no longer detected in next scan

CRITICAL RULES:
- Be specific, not generic
- Include actual CLI commands or console paths
- Assume this might have been an intentional change - ask them to verify first
- Keep under 500 words
- Use proper Jira markdown"""

        return self.invoke_model(prompt, max_tokens=2048, temperature=0.5)

    def generate_exception_request_description(
        self,
        finding_title: str,
        risk_level: str,
        business_justification: str,
        compensating_controls: str,
        expiration_date: str,
        requested_by: str
    ) -> str:
        """Generate a clear risk exception request description."""
        prompt = f"""You are writing a Jira ticket for a risk exception request. This is a formal request to accept a security risk instead of fixing it. Make it professional and thorough.

EXCEPTION REQUEST DETAILS:
- Finding: {finding_title}
- Risk Level: {risk_level}
- Requested By: {requested_by}
- Expiration Date: {expiration_date}
- Business Justification: {business_justification}
- Compensating Controls: {compensating_controls}

Write a Jira ticket description following these EXACT sections:

## Exception Request Summary
1-2 sentences explaining what risk is being accepted and why.

## Original Finding
Brief description of the security issue that prompted this exception request.

## Business Justification
{business_justification}

*Why this matters:* [Add 1 sentence about the business value or constraint]

## Compensating Controls
{compensating_controls}

*How these reduce risk:* [Explain briefly how compensating controls mitigate the original risk]

## Risk Assessment
• *Risk Level:* {risk_level}
• *Requested By:* {requested_by}
• *Valid Until:* {expiration_date}
• *Residual Risk:* [High/Medium/Low after compensating controls]

## Approval Requirements
This exception request requires:
- [ ] Security team review
- [ ] Engineering manager approval
- [ ] Compliance officer acknowledgment (for SOC 2 controls)

## Expiration and Review
- This exception expires on {expiration_date}
- A review will be scheduled 30 days before expiration
- The exception will be automatically revoked if compensating controls are not maintained

## Acceptance Criteria
- [ ] All required approvals obtained
- [ ] Compensating controls implemented and verified
- [ ] Exception documented in compliance records
- [ ] Calendar reminder set for expiration review

CRITICAL RULES:
- Professional tone (this is a formal request)
- Clear about what risk is being accepted
- Specific about compensating controls
- Under 500 words
- Use proper Jira markdown"""

        return self.invoke_model(prompt, max_tokens=2048, temperature=0.4)

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
