"""
Bedrock Service for CARL AI capabilities.

Supports multiple compliance frameworks (SOC 2, HIPAA).

Implements AWS-recommended retry patterns for Bedrock throttling:
- Exponential backoff with jitter for 429/503 errors
- Configurable retry limits
- Proper error classification (retryable vs non-retryable)

Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html
"""

import json
import os
import random
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from utils.logger import get_logger

# Import compliance frameworks for framework-aware prompts
try:
    from knowledge.compliance_frameworks import get_framework, get_ai_context, FRAMEWORKS
    FRAMEWORKS_AVAILABLE = True
except ImportError:
    FRAMEWORKS_AVAILABLE = False

logger = get_logger(__name__)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
# Use BEDROCK_REGION first, fall back to AWS_REGION, default to us-east-1
AWS_REGION = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION", "us-east-1")

# Default framework (can be overridden per request)
DEFAULT_FRAMEWORK = os.environ.get("COMPLIANCE_FRAMEWORK", "soc2")

# Retry configuration for Bedrock API calls
# Based on AWS best practices: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/retry-backoff.html
MAX_RETRIES = int(os.environ.get("BEDROCK_MAX_RETRIES", "3"))
BASE_BACKOFF_MS = int(os.environ.get("BEDROCK_BASE_BACKOFF_MS", "1000"))  # 1 second
MAX_BACKOFF_MS = int(os.environ.get("BEDROCK_MAX_BACKOFF_MS", "30000"))  # 30 seconds
JITTER_FACTOR = 0.5  # Random jitter up to 50% of backoff time

# Retryable error codes (per AWS documentation)
RETRYABLE_ERROR_CODES = {
    "ThrottlingException",  # 429 - Rate limit exceeded
    "ServiceUnavailable",   # 503 - Temporary unavailability
    "InternalFailure",      # 500 - Server error
    "ServiceException",     # Generic service error
    "ModelStreamErrorException",  # Streaming error
}

# Non-retryable errors (fail fast)
NON_RETRYABLE_ERROR_CODES = {
    "ValidationException",      # 400 - Bad input
    "AccessDeniedException",    # 403 - Permission denied
    "ResourceNotFoundException", # 404 - Model not found
    "ModelNotReadyException",   # Model still loading
    "ModelTimeoutException",    # Model took too long
}


def get_system_prompt(framework: str = None) -> str:
    """Get system prompt with framework-specific context.

    Args:
        framework: The compliance framework ("soc2" or "hipaa"). Defaults to SOC 2.

    Returns:
        System prompt with framework-specific controls and guidance.
    """
    framework = framework or DEFAULT_FRAMEWORK

    # Get framework-specific context if available
    if FRAMEWORKS_AVAILABLE:
        try:
            framework_context = get_ai_context(framework)
        except KeyError:
            framework_context = ""
    else:
        framework_context = ""

    base_prompt = """You are CARL (Cloud Automated Risk & Compliance Logic), an AI assistant specialized in AWS compliance and security."""

    if framework.lower() == "hipaa":
        return f"""{base_prompt} You help users understand and remediate compliance findings for HIPAA.

Your capabilities:
- Explain compliance findings in plain language
- Provide remediation guidance for AWS security issues
- Answer questions about HIPAA Security Rule requirements
- Recommend AWS security best practices for ePHI protection

Guidelines:
- Be concise and actionable
- Prioritize ePHI protection and patient privacy
- Reference specific AWS services and configurations
- Acknowledge when you're uncertain
- Never recommend disabling security controls
- Always consider HIPAA breach notification requirements

HIPAA Security Rule Technical Safeguards (45 CFR 164.312):
- 164.312(a) Access Control: Limit ePHI access to authorized persons
- 164.312(b) Audit Controls: Record and examine activity in ePHI systems
- 164.312(c) Integrity: Protect ePHI from improper alteration or destruction
- 164.312(d) Authentication: Verify person/entity seeking access to ePHI
- 164.312(e) Transmission Security: Guard against unauthorized ePHI access during transmission

{framework_context}

When explaining findings, always include:
1. What the issue is (plain language, with HIPAA context)
2. Why it matters (risk to ePHI, potential breach implications)
3. How to fix it (specific steps with AWS services)
"""
    else:  # Default to SOC 2
        return f"""{base_prompt} You help users understand and remediate compliance findings for SOC 2.

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

{framework_context}

When explaining findings, always include:
1. What the issue is (plain language)
2. Why it matters (risk/impact)
3. How to fix it (specific steps)
"""


# Default system prompt (SOC 2)
SYSTEM_PROMPT = get_system_prompt("soc2")


class BedrockService:
    """Service for interacting with Amazon Bedrock.

    Supports multiple compliance frameworks (SOC 2, HIPAA).
    """

    def __init__(self, framework: str = None):
        """Initialize the Bedrock service.

        Args:
            framework: The compliance framework to use ("soc2" or "hipaa").
                      Defaults to environment variable COMPLIANCE_FRAMEWORK or "soc2".
        """
        self.client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        self.model_id = BEDROCK_MODEL_ID
        self.framework = framework or DEFAULT_FRAMEWORK
        self.system_prompt = get_system_prompt(self.framework)

    def _calculate_backoff_with_jitter(self, attempt: int) -> float:
        """Calculate backoff time with exponential increase and random jitter.

        Uses AWS-recommended formula: min(max_backoff, base * 2^attempt) + random_jitter

        Args:
            attempt: The current retry attempt number (0-indexed)

        Returns:
            Backoff time in seconds
        """
        # Exponential backoff: base_ms * 2^attempt
        exponential_backoff_ms = BASE_BACKOFF_MS * (2 ** attempt)

        # Cap at maximum backoff
        capped_backoff_ms = min(exponential_backoff_ms, MAX_BACKOFF_MS)

        # Add random jitter (up to JITTER_FACTOR of the backoff time)
        jitter_ms = random.uniform(0, capped_backoff_ms * JITTER_FACTOR)

        total_backoff_ms = capped_backoff_ms + jitter_ms
        return total_backoff_ms / 1000.0  # Convert to seconds

    def _is_retryable_error(self, error: ClientError) -> bool:
        """Check if an error is retryable based on AWS documentation.

        Args:
            error: The botocore ClientError exception

        Returns:
            True if the error should be retried, False otherwise
        """
        error_code = error.response.get("Error", {}).get("Code", "")
        http_status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)

        # Check by error code first
        if error_code in RETRYABLE_ERROR_CODES:
            return True

        # Check by HTTP status code (429 = throttling, 503 = service unavailable, 500 = internal error)
        if http_status in (429, 500, 503):
            return True

        # Non-retryable errors
        if error_code in NON_RETRYABLE_ERROR_CODES:
            return False

        return False

    def invoke_model(
        self,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        """Invoke Bedrock model with prompt and automatic retry on transient errors.

        Implements AWS-recommended retry pattern with exponential backoff and jitter
        for handling throttling (429) and service unavailability (503) errors.

        Args:
            prompt: The user prompt to send
            system_prompt: Optional system prompt override. If not provided, uses
                          the framework-specific prompt.
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            The model's response text, or an error message if all retries fail.
        """
        # Use provided system prompt or fall back to framework-specific default
        system_prompt = system_prompt or self.system_prompt

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }

        last_error = None
        for attempt in range(MAX_RETRIES + 1):  # +1 for initial attempt
            try:
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json",
                )

                response_body = json.loads(response["body"].read())
                return response_body["content"][0]["text"]

            except ClientError as e:
                last_error = e
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                http_status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)

                # Check if we should retry
                if self._is_retryable_error(e) and attempt < MAX_RETRIES:
                    backoff_time = self._calculate_backoff_with_jitter(attempt)
                    logger.warning(
                        f"Bedrock API error (attempt {attempt + 1}/{MAX_RETRIES + 1}): "
                        f"{error_code} (HTTP {http_status}). Retrying in {backoff_time:.2f}s..."
                    )
                    time.sleep(backoff_time)
                    continue

                # Non-retryable error or max retries exceeded
                if error_code == "ThrottlingException":
                    logger.error(f"Bedrock throttling after {attempt + 1} attempts. Consider requesting quota increase.")
                    return "I'm experiencing high demand right now. Please try again in a moment."
                elif error_code == "AccessDeniedException":
                    logger.error(f"Bedrock access denied: {e}")
                    return "I don't have permission to access this model. Please check IAM permissions."
                elif error_code == "ValidationException":
                    logger.error(f"Bedrock validation error: {e}")
                    return f"There was an issue with my request format: {str(e)}"
                elif error_code == "ResourceNotFoundException":
                    logger.error(f"Bedrock model not found: {self.model_id}")
                    return f"The AI model '{self.model_id}' is not available. Please check model access."
                else:
                    logger.exception(f"Bedrock API error after {attempt + 1} attempts: {error_code}")
                    return f"I encountered an error: {error_code}. Please try again."

            except json.JSONDecodeError as e:
                logger.exception("Failed to parse Bedrock response")
                return "I received an invalid response from the AI service. Please try again."

            except Exception as e:
                last_error = e
                logger.exception(f"Unexpected error invoking Bedrock model (attempt {attempt + 1})")

                # Only retry on unexpected errors if we haven't exhausted retries
                if attempt < MAX_RETRIES:
                    backoff_time = self._calculate_backoff_with_jitter(attempt)
                    logger.warning(f"Retrying after unexpected error in {backoff_time:.2f}s...")
                    time.sleep(backoff_time)
                    continue

                return f"I encountered an unexpected error: {str(e)}"

        # Should not reach here, but just in case
        logger.error(f"All {MAX_RETRIES + 1} attempts failed for Bedrock invocation")
        return f"I couldn't complete your request after multiple attempts. Please try again later."

    def ask_compliance_question(self, question: str, context: str = "", framework: str = None) -> str:
        """Answer a compliance-related question using environment context.

        Args:
            question: The user's compliance question
            context: AWS environment scan data
            framework: Compliance framework ("soc2" or "hipaa"). Uses instance default if not provided.
        """
        has_scan_data = context and len(context.strip()) > 50
        framework = framework or self.framework

        # Framework-specific context
        if framework.lower() == "hipaa":
            framework_name = "HIPAA Security Rule"
            framework_controls = """
HIPAA Security Rule Controls:
• 164.312(a) Access Control - Limit ePHI access to authorized persons
• 164.312(b) Audit Controls - Record and examine system activity
• 164.312(c) Integrity - Protect ePHI from alteration/destruction
• 164.312(d) Authentication - Verify person/entity identity
• 164.312(e) Transmission Security - Guard ePHI during transmission"""
            compliance_examples = """
*HIPAA Requirements*
• Encrypt ePHI at rest and in transit (164.312(a)(2)(iv), 164.312(e)(2)(ii))
• Enable CloudTrail for audit logs (164.312(b) - Audit Controls)
• Implement MFA for ePHI access (164.312(d) - Authentication)
• Use VPC endpoints for private access (164.312(e)(1) - Transmission Security)"""
        else:  # Default to SOC 2
            framework_name = "SOC 2"
            framework_controls = """
SOC 2 Trust Service Criteria:
• CC6 - Logical and Physical Access Controls
• CC7 - System Operations (monitoring, incident response)
• A1 - Availability
• C1 - Confidentiality
• PI1 - Processing Integrity"""
            compliance_examples = """
*SOC 2 Requirements*
• Force HTTPS with ACM certificate (CC6.7 - Encryption in Transit)
• Enable ALB access logs (CC7.2 - Monitoring)
• Restrict SSH access, no 0.0.0.0/0 (CC6.1 - Access Controls)"""

        prompt = f"""You are CARL, an AI compliance expert for AWS infrastructure and {framework_name} compliance.

Your job: Answer the user's question clearly and actionably using LIVE AWS environment data.

CRITICAL RULE: You have already scanned relevant AWS resources. Use the scan data - don't ask permission.

What NOT to say:
❌ "Want me to scan your security groups?" (already scanned if relevant)
❌ "Should I check your VPCs?" (already scanned if relevant)
❌ "Want me to scan your network ACLs?" (already scanned if relevant)
❌ "Should I look at your..." (just report what you found)

What TO say:
✅ "I scanned your VPCs and found..." (report scan results)
✅ "Your security groups show..." (use actual data)
✅ "Need help with Glue configuration?" (offering additional help is fine)
✅ "Want me to also scan Route53?" (additional/deeper scan beyond what's relevant)

Rule: If it's relevant to their question, it's already scanned. Just report what you found.

ENVIRONMENT DATA AVAILABLE: {"YES - Use this data in your answer" if has_scan_data else "LIMITED - Provide general guidance"}

{f'''
SCANNED ENVIRONMENT DATA (from user's AWS account):
{context}

IMPORTANT: Use this actual data from their environment in your answer. Be specific with resource names, IDs, and configurations shown above. Don't ask permission to use data you already have.
''' if has_scan_data else '''
NOTE: Limited environment data available. Provide general AWS best practices and guidance, but explain what you'd need to scan to give a tailored answer.
'''}

User's Question: {question}

CRITICAL FORMATTING RULES (Slack markdown):
- Use *text* for bold (single asterisk), NOT **text**
- NO markdown headers (#, ##) - use *Section Name* on its own line instead
- NO horizontal rules (---) - use blank lines to separate sections
- NEVER use tildes (~) - they create strikethrough in Slack
- Always spell out "approximately" or "approx." instead of using ~
- For costs, write "$220/month" or "approx. $220/month" - NEVER "~$220/month"
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

{compliance_examples}

*Want More Detail?*
I can scan additional resources (load balancers, detailed security group rules, Route53 configs) for deeper recommendations. Or say "yes" and I'll hand off to the Architect Agent to generate Terraform code.

IMPORTANT: Don't ask permission to scan what's already relevant to the question. If you scanned VPCs, just use that data - don't say "Want me to scan VPCs?". Only mention additional/deeper scans if user wants more detail.

Example with cost analysis:
Question: "Should I use AWS Glue or build my own ETL on EC2?"
*ETL Solution Comparison*

*Option 1: AWS Glue (Serverless) - RECOMMENDED*
• Cost: Approx. $220/month (20 DPUs x 8 hours/day x 30 days x $0.44/DPU-hour)
• Best for: Minimal ops overhead, automatic scaling
• Pros: No servers to manage, pay only when running, built-in Spark
• Compliance: Automatic audit logging ({framework_name} audit controls)

*Option 2: Self-Managed EC2*
• Cost: Approx. $50/month (t3.large 24/7) + 20 hours/month ops time (approx. $330 total value)
• Best for: Custom logic, existing tools
• Pros: Full control, can use any tool
• Compliance: Must manage access controls, patching ({framework_name} access requirements)

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
        controls: list[str],
        compliance_status: str,
        framework: str = None,
    ) -> str:
        """Generate a clear, actionable Jira ticket description using AI.

        Args:
            controls: List of control IDs (SOC 2 or HIPAA depending on framework)
            framework: Compliance framework ("soc2" or "hipaa"). Uses instance default if not provided.
        """
        framework = framework or self.framework

        # Framework-specific compliance section
        if framework.lower() == "hipaa":
            framework_name = "HIPAA"
            controls_label = "HIPAA Security Rule Controls"
            compliance_section = f"""## HIPAA Compliance
{f"This finding affects HIPAA Security Rule controls: {', '.join(controls)}" if controls else "No specific HIPAA controls mapped yet."}
Explain briefly (1 sentence) why this matters for ePHI protection and HIPAA compliance."""
            compliance_impact = "potential ePHI breach, HIPAA violation, regulatory penalties"
        else:  # Default to SOC 2
            framework_name = "SOC 2"
            controls_label = "SOC 2 Controls"
            compliance_section = f"""## SOC 2 Compliance
{f"This finding affects SOC 2 controls: {', '.join(controls)}" if controls else "No specific SOC 2 controls mapped yet."}
Explain briefly (1 sentence) why this matters for auditors."""
            compliance_impact = "data exposure, compliance failure, security breach"

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
- {controls_label}: {', '.join(controls) if controls else 'None'}
- Technical Description: {raw_description}
- Framework: {framework_name}

Write a Jira ticket description following these EXACT sections (use h2 headers):

## Problem Statement
Write 2-3 sentences explaining what's wrong in plain English. Avoid jargon. Make it clear why this matters.

## Business Impact
1-2 sentences on the risk if this isn't fixed. Be specific about consequences ({compliance_impact}, etc.)

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

{compliance_section}

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
        requested_by: str,
        framework: str = None,
    ) -> str:
        """Generate a clear risk exception request description.

        Args:
            framework: Compliance framework ("soc2" or "hipaa"). Uses instance default if not provided.
        """
        framework = framework or self.framework

        # Framework-specific compliance acknowledgment
        if framework.lower() == "hipaa":
            compliance_ack = "- [ ] HIPAA Privacy Officer acknowledgment (for ePHI-related controls)"
        else:  # Default to SOC 2
            compliance_ack = "- [ ] Compliance officer acknowledgment (for SOC 2 controls)"

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
{compliance_ack}

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

    def explain_finding(self, finding: dict[str, Any], framework: str = None) -> str:
        """Explain a security finding in plain language.

        Args:
            finding: Finding dictionary with title, severity, resource_id, etc.
            framework: Compliance framework ("soc2" or "hipaa"). Uses instance default if not provided.
        """
        framework = framework or self.framework

        # Framework-specific labels
        if framework.lower() == "hipaa":
            controls_label = "HIPAA Controls"
            impact_header = "*HIPAA Impact*"
            impact_description = "[1 sentence about which HIPAA control this affects and ePHI risk]"
        else:  # Default to SOC 2
            controls_label = "SOC 2 Controls"
            impact_header = "*SOC 2 Impact*"
            impact_description = "[1 sentence about which control this affects]"

        prompt = f"""Explain this security finding briefly:

*Finding:* {finding.get('title', 'Unknown')}
*Severity:* {finding.get('severity', 'Unknown')}
*Resource:* {finding.get('resource_id', 'Unknown')} ({finding.get('resource_type', 'Unknown')})
*Description:* {finding.get('description', 'No description')}
*{controls_label}:* {', '.join(finding.get('control_ids', []))}

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

{impact_header}
{impact_description}"""

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
