"""
CARL Slack Router Lambda Handler

Routes incoming Slack events, commands, and interactions to appropriate handlers.
"""

import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs

import boto3

from services.bedrock_service import BedrockService
from services.findings_service import FindingsService
from services.slack_service import SlackService
from services.architecture_advisor import ArchitectureAdvisor
from services.infrastructure_builder import InfrastructureBuilder
from services.cost_estimator import CostEstimator, format_cost_estimate
from services.foundation import DecisionEngine, FoundationBuilder
from services.foundation.decision_engine import SessionState
from services.github_service import GitHubService
from services.github_app_service import GitHubAppAuth
from services.code_uploader import CodeUploader
from services.jira_security_sync import JiraSecuritySync
from utils.aws_client import get_parameter, get_secret
from utils.logger import get_logger
from utils.dynamodb_utils import get_table

logger = get_logger(__name__)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
SLACK_BOT_TOKEN_SSM = os.environ.get("SLACK_BOT_TOKEN_SSM", "")
SLACK_SIGNING_SECRET_SSM = os.environ.get("SLACK_SIGNING_SECRET_SSM", "")

# GitHub App configuration (preferred over static token)
GITHUB_APP_CREDENTIALS_SECRET = os.environ.get("GITHUB_APP_CREDENTIALS_SECRET", "/carl/dev/github-app-credentials")
GITHUB_INFRA_OWNER = os.environ.get("GITHUB_INFRA_OWNER", "your-org")
GITHUB_INFRA_REPO = os.environ.get("GITHUB_INFRA_REPO", "carl-infrastructure-deployments")

# Legacy: Static token (deprecated, use GitHub App instead)
GITHUB_INFRA_TOKEN_SECRET = os.environ.get("GITHUB_INFRA_TOKEN_SECRET", "")

# Lazy-loaded services
_slack_service: SlackService | None = None
_bedrock_service: BedrockService | None = None
_findings_service: FindingsService | None = None
_architecture_advisor: ArchitectureAdvisor | None = None
_infrastructure_builder: InfrastructureBuilder | None = None
_cost_estimator: CostEstimator | None = None
_decision_engine: DecisionEngine | None = None
_foundation_builder: FoundationBuilder | None = None
_github_app_auth: GitHubAppAuth | None = None
_github_service: GitHubService | None = None


def get_slack_service() -> SlackService:
    """Get or create Slack service instance."""
    global _slack_service
    if _slack_service is None:
        token = get_parameter(SLACK_BOT_TOKEN_SSM)
        _slack_service = SlackService(token)
    return _slack_service


def get_bedrock_service() -> BedrockService:
    """Get or create Bedrock service instance."""
    global _bedrock_service
    if _bedrock_service is None:
        _bedrock_service = BedrockService()
    return _bedrock_service


def get_findings_service() -> FindingsService:
    """Get or create Findings service instance."""
    global _findings_service
    if _findings_service is None:
        _findings_service = FindingsService()
    return _findings_service


def get_architecture_advisor() -> ArchitectureAdvisor:
    """Get or create Architecture Advisor instance."""
    global _architecture_advisor
    if _architecture_advisor is None:
        _architecture_advisor = ArchitectureAdvisor()
    return _architecture_advisor


def get_infrastructure_builder() -> InfrastructureBuilder:
    """Get or create Infrastructure Builder instance."""
    global _infrastructure_builder
    if _infrastructure_builder is None:
        _infrastructure_builder = InfrastructureBuilder()
    return _infrastructure_builder


def get_cost_estimator() -> CostEstimator:
    """Get or create Cost Estimator instance."""
    global _cost_estimator
    if _cost_estimator is None:
        _cost_estimator = CostEstimator()
    return _cost_estimator


def get_decision_engine() -> DecisionEngine:
    """Get or create Decision Engine instance."""
    global _decision_engine
    if _decision_engine is None:
        _decision_engine = DecisionEngine()
    return _decision_engine


def get_foundation_builder() -> FoundationBuilder:
    """Get or create Foundation Builder instance."""
    global _foundation_builder
    if _foundation_builder is None:
        _foundation_builder = FoundationBuilder()
    return _foundation_builder


def get_github_app_auth() -> GitHubAppAuth:
    """Get or create GitHub App authentication instance."""
    global _github_app_auth
    if _github_app_auth is None:
        # Get GitHub App credentials from Secrets Manager
        import json as json_lib
        credentials_json = get_secret(GITHUB_APP_CREDENTIALS_SECRET)
        credentials = json_lib.loads(credentials_json)

        _github_app_auth = GitHubAppAuth(
            app_id=credentials["app_id"],
            private_key=credentials["private_key"],
            installation_id=credentials["installation_id"]
        )
    return _github_app_auth


def get_github_service() -> GitHubService:
    """
    Get or create GitHub service instance.

    Uses GitHub App (preferred) or falls back to static token (legacy).
    """
    global _github_service
    if _github_service is None:
        try:
            # Try GitHub App first (preferred)
            github_app = get_github_app_auth()
            # Pass token provider function (not static token)
            _github_service = GitHubService(
                github_app.get_installation_token,
                GITHUB_INFRA_OWNER,
                GITHUB_INFRA_REPO
            )
            logger.info("Using GitHub App authentication")
        except Exception as e:
            # Fallback to static token (legacy)
            if GITHUB_INFRA_TOKEN_SECRET:
                logger.warning(f"GitHub App not configured, falling back to static token: {e}")
                token = get_secret(GITHUB_INFRA_TOKEN_SECRET)
                _github_service = GitHubService(token, GITHUB_INFRA_OWNER, GITHUB_INFRA_REPO)
                logger.info("Using static token authentication (legacy)")
            else:
                raise ValueError("No GitHub authentication configured. Set up GitHub App or provide static token.")
    return _github_service


def invoke_agentcore_ask(question: str, session_id: str = None) -> dict:
    """
    Invoke AgentCore Ask Agent for intelligent Q&A (Phase 1).

    Args:
        question: The user's question
        session_id: Optional session ID for conversation continuity

    Returns:
        dict with 'response' (text) and 'success' (bool)
    """
    import uuid

    runtime_arn = os.environ.get("AGENTCORE_ASK_RUNTIME_ARN", "")
    if not runtime_arn:
        return {"success": False, "response": "", "error": "AgentCore not configured"}

    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))

        payload = {"prompt": question}

        logger.info(f"Invoking AgentCore runtime: {runtime_arn}")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode("utf-8")
        )

        # Process response - AgentCore returns an event stream
        full_response = ""
        event_stream = response.get("responseStream")
        if event_stream:
            for event in event_stream:
                # AgentCore events contain chunks of the response
                if "chunk" in event:
                    chunk_data = event["chunk"]
                    if "bytes" in chunk_data:
                        chunk_text = chunk_data["bytes"].decode("utf-8")
                        full_response += chunk_text
                elif "trace" in event:
                    # Trace events contain debugging info, skip for now
                    pass

        # Also check for direct response body (AgentCore returns JSON with "result" key)
        if not full_response:
            resp = response.get("response")
            if resp and hasattr(resp, "read"):
                body = resp.read()
                if isinstance(body, bytes):
                    body = body.decode("utf-8")
                # Parse JSON response - AgentCore wraps result in {"result": "..."}
                try:
                    parsed = json.loads(body)
                    full_response = parsed.get("result", body)
                except json.JSONDecodeError:
                    full_response = body

        if full_response:
            logger.info(f"AgentCore response received: {len(full_response)} chars")
            return {"success": True, "response": full_response, "session_id": session_id}
        else:
            logger.warning("AgentCore returned empty response")
            return {"success": False, "response": "", "error": "Empty response from AgentCore"}

    except Exception as e:
        logger.error(f"AgentCore invocation failed: {e}", exc_info=True)
        return {"success": False, "response": "", "error": str(e)}


def invoke_agentcore_architect(requirement: str, session_id: str = None) -> dict:
    """
    Invoke AgentCore Architect Agent for architecture recommendations.

    Args:
        requirement: The user's architecture requirement
        session_id: Optional session ID for conversation continuity

    Returns:
        dict with 'response' (text) and 'success' (bool)
    """
    import uuid

    runtime_arn = os.environ.get("AGENTCORE_ARCHITECT_RUNTIME_ARN", "")
    if not runtime_arn:
        return {"success": False, "response": "", "error": "AgentCore Architect not configured"}

    if not session_id:
        session_id = str(uuid.uuid4())

    try:
        client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))

        payload = {"prompt": requirement}

        logger.info(f"Invoking AgentCore Architect runtime: {runtime_arn}")
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode("utf-8")
        )

        # Process response - AgentCore returns an event stream
        full_response = ""
        event_stream = response.get("responseStream")
        if event_stream:
            for event in event_stream:
                # AgentCore events contain chunks of the response
                if "chunk" in event:
                    chunk_data = event["chunk"]
                    if "bytes" in chunk_data:
                        chunk_text = chunk_data["bytes"].decode("utf-8")
                        full_response += chunk_text
                elif "trace" in event:
                    # Trace events contain debugging info, skip for now
                    pass

        # Also check for direct response body (AgentCore returns JSON with "result" key)
        if not full_response:
            resp = response.get("response")
            if resp and hasattr(resp, "read"):
                body = resp.read()
                if isinstance(body, bytes):
                    body = body.decode("utf-8")
                # Parse JSON response - AgentCore wraps result in {"result": "..."}
                try:
                    parsed = json.loads(body)
                    full_response = parsed.get("result", body)
                except json.JSONDecodeError:
                    full_response = body

        if full_response:
            logger.info(f"AgentCore Architect response received: {len(full_response)} chars")
            return {"success": True, "response": full_response, "session_id": session_id}
        else:
            logger.warning("AgentCore Architect returned empty response")
            return {"success": False, "response": "", "error": "Empty response from AgentCore Architect"}

    except Exception as e:
        logger.error(f"AgentCore Architect invocation failed: {e}", exc_info=True)
        return {"success": False, "response": "", "error": str(e)}


def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: str,
    signature: str,
) -> bool:
    """Verify the Slack request signature."""
    # Check if timestamp is valid
    if not timestamp:
        logger.warning("Missing timestamp header")
        return False

    try:
        ts_int = int(timestamp)
    except ValueError:
        logger.warning(f"Invalid timestamp format: {timestamp}")
        return False

    if abs(time.time() - ts_int) > 60 * 5:
        logger.warning("Request timestamp is too old")
        return False

    sig_basestring = f"v0:{timestamp}:{body}"
    my_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(my_signature, signature)


def is_response_too_verbose(response: str) -> bool:
    """
    Detect if response needs condensing using intelligent heuristics.

    Returns True if response is too long/verbose.
    """
    word_count = len(response.split())
    section_count = response.count('***OPTION')

    # Too many words per option (indicates verbose descriptions)
    if section_count > 0 and word_count / section_count > 200:
        logger.info(f"Response verbose: {word_count / section_count:.0f} words per option (>200)")
        return True

    # Too long overall
    if word_count > 800:
        logger.info(f"Response verbose: {word_count} total words (>800)")
        return True

    # Too many bold headers (indicates excessive sections)
    bold_count = response.count('**')
    if bold_count > 30:
        logger.info(f"Response verbose: {bold_count} bold markers (>30)")
        return True

    return False


def condense_response(verbose_response: str) -> str:
    """
    Use AI to intelligently condense verbose responses while keeping key information.

    Uses Claude Haiku for fast, cheap condensing.
    """
    from services.agent_core import Agent

    logger.info("Condensing verbose response with AI...")

    condenser_agent = Agent(
        tools=[],  # No tools needed for condensing
        instructions="""You condense architecture recommendations to be more scannable.

Your job: Take verbose responses and make them concise while keeping all critical information.

CRITICAL: Use plain text format, NO markdown asterisks. The system will format it for Slack.

What to keep:
- Option headers: OPTION 1: Service Name
- RECOMMENDED tag (on its own line after option header)
- Costs and pricing
- Service names
- Key tradeoffs (3-5 bullets per option)
- Final recommendation (2-3 sentences)

What to remove/reduce:
- Reduce bullet points to 3-5 per option (cut redundant ones)
- Remove separate "Network Requirements" sections (fold into bullets)
- Remove "SOC 2 Compliance Notes" sections (fold into bullets)
- Remove "Questions to help refine?" sections
- Remove "When to choose Option X" paragraphs

Example format you MUST maintain:

OPTION 1: Service Name
RECOMMENDED
Best for: One sentence
Cost: $X-Y/month
Key points:
- Bullet 1
- Bullet 2
- Bullet 3

OPTION 2: Service Name
**Best for:** One sentence
**Cost:** $X-Y/month
**Key points:**
- Bullet 1
- Bullet 2

---

***My Recommendation:*** Brief reasoning (2-3 sentences).

**Ready to build?** Click [Build This] below.
""",
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0"  # Use same model as main agent
    )

    condensed = condenser_agent.execute(
        f"Condense this response to be more scannable while keeping critical info:\n\n{verbose_response}"
    )

    logger.info(f"Condensed {len(verbose_response.split())} words → {len(condensed.split())} words")

    return condensed


def format_recommendation_to_slack_blocks(response: str) -> list:
    """
    Parse plain text recommendation response and build native Slack blocks.
    No markdown asterisks - uses Slack's mrkdwn format directly.
    """
    import re

    blocks = []
    lines = response.strip().split('\n')
    current_section = []

    for line in lines:
        stripped = line.strip()

        # OPTION header (e.g., "OPTION 1: EC2 Auto Scaling")
        if re.match(r'^OPTION \d+:', stripped):
            # Flush previous section
            if current_section:
                text = '\n'.join(current_section)
                if text:
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
                current_section = []

            # Add divider before option (except first)
            if blocks:
                blocks.append({"type": "divider"})

            # Extract option number and name
            match = re.match(r'^OPTION (\d+): (.+)$', stripped)
            if match:
                option_num = match.group(1)
                option_name = match.group(2)

                # Add option header (bold)
                current_section.append(f"*Option {option_num}: {option_name}*")

        # RECOMMENDED tag
        elif stripped == "RECOMMENDED":
            current_section.append("✓ RECOMMENDED")

        # Section headers (Best for, Cost, Key points)
        elif re.match(r'^(Best for|Cost|Key points|Architecture|Details):', stripped):
            # Make the header bold
            match = re.match(r'^([^:]+):\s*(.*)$', stripped)
            if match:
                header = match.group(1)
                content = match.group(2)
                if content:
                    current_section.append(f"*{header}:* {content}")
                else:
                    current_section.append(f"*{header}:*")

        # My Recommendation section
        elif stripped.startswith("My Recommendation:"):
            # Flush previous section
            if current_section:
                text = '\n'.join(current_section)
                if text:
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
                current_section = []

            # Add divider
            blocks.append({"type": "divider"})

            # Extract recommendation text
            rec_text = stripped.replace("My Recommendation:", "").strip()
            current_section.append(f"*My Recommendation:* {rec_text}")

        # Bullet points or regular text
        elif stripped:
            # Bold important considerations/warnings/limitations
            important_keywords = ['Important:', 'Warning:', 'Note:', 'Caution:', 'Critical:', 'Limitation:', 'Consideration:', 'Pro:', 'Con:']
            for keyword in important_keywords:
                if keyword in stripped:
                    stripped = stripped.replace(keyword, f"*{keyword}*", 1)
                    break
            current_section.append(stripped)

    # Flush final section
    if current_section:
        text = '\n'.join(current_section)
        if text:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    return blocks


def normalize_formatting(response: str) -> str:
    """
    Comprehensive formatting cleanup - fix common asterisk and structure issues.
    """
    import re

    # STEP 1: Fix OPTION headers that are missing proper formatting or stuck to other text
    # "OPTION 1: EC2..." -> "***OPTION 1: EC2***"
    # "*OPTION 1:" or "**OPTION 1:" -> "***OPTION 1:***"
    response = re.sub(r'(?:^|\n)\*{0,2}OPTION (\d+):\s*([^\n]+?)(?=\*{0,2}(?:Best for|Cost|Key points|OPTION|\n|$))',
                      r'\n\n***OPTION \1: \2***\n', response)

    # STEP 2: Fix text crammed together without line breaks
    # "ALB**Best" -> "ALB\n\n**Best"
    response = re.sub(r'([a-z])\*\*([A-Z][a-z]+)', r'\1\n\n**\2', response)

    # "ALBRECOMMENDED" or "ALB RECOMMENDED" -> "ALB\nRECOMMENDED"
    response = re.sub(r'([A-Z]{3,})\s*RECOMMENDED', r'\1\nRECOMMENDED', response)
    response = re.sub(r'([a-z])(RECOMMENDED)', r'\1\n\2', response)

    # "RECOMMENDEDBest for" -> "RECOMMENDED\n\n**Best for"
    response = re.sub(r'RECOMMENDED\*{0,2}([A-Z][a-z]+)', r'RECOMMENDED\n\n**\1', response)

    # STEP 3: Clean RECOMMENDED formatting (no asterisks around it)
    response = re.sub(r'\*{1,}\s*RECOMMENDED\s*\*{1,}', 'RECOMMENDED', response)

    # STEP 4: Fix section headers (Best for, Cost, Key points, etc.)
    # Remove excessive asterisks before or after section headers
    # "***Best for:**" -> "**Best for:**"
    # "**Best for:***" -> "**Best for:**"
    response = re.sub(r'\*{3,}(Best for|Cost|Key points|Architecture|My Recommendation):\*{0,}', r'**\1:**', response)
    response = re.sub(r'\*{2}(Best for|Cost|Key points|Architecture|My Recommendation):\*{2,}', r'**\1:**', response)

    # STEP 5: Ensure proper line breaks after OPTION headers
    # "***OPTION 1: Text***RECOMMENDED" -> "***OPTION 1: Text***\nRECOMMENDED"
    response = re.sub(r'(\*{3}OPTION \d+:[^\*]+\*{3})\s*(RECOMMENDED|Best|\*\*)', r'\1\n\2', response)

    # STEP 6: Fix "My Recommendation" variations
    response = re.sub(r'\*{1,}My\s+\*{0,}Recommendation:\*{1,}', r'**My Recommendation:**', response)

    # STEP 7: General cleanup - excessive asterisks
    lines = response.split('\n')
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and dividers
        if not stripped or stripped == '---':
            cleaned_lines.append(line)
            continue

        # For OPTION headers - keep exactly 3 asterisks on each side
        if 'OPTION' in line and ':' in line:
            # Remove any extra asterisks and standardize
            line = re.sub(r'\*+OPTION (\d+):[^\*]+\*+', lambda m: f"***OPTION {m.group(1)}: {m.group(0).split(':')[1].split('***')[0].strip()}***", line)

        # For regular lines, convert 3+ consecutive asterisks to 2
        else:
            line = re.sub(r'(?<!\*)\*{3,}(?!\*)', '**', line)

        cleaned_lines.append(line)

    response = '\n'.join(cleaned_lines)

    # STEP 8: Ensure dividers between options
    lines = response.split('\n')
    result_lines = []
    last_option_index = -10

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect OPTION headers
        if 'OPTION' in stripped and ':' in stripped and '***' in stripped:
            # Add divider before this option (except for first option)
            if last_option_index >= 0 and i - last_option_index > 1:
                # Check if there's already a divider nearby
                recent_lines = result_lines[-5:] if len(result_lines) >= 5 else result_lines
                has_divider = any('---' in l for l in recent_lines)

                if not has_divider:
                    # Add blank line, divider, blank line
                    if result_lines and result_lines[-1].strip():
                        result_lines.append('')
                    result_lines.append('---')
                    result_lines.append('')

            last_option_index = len(result_lines)

        result_lines.append(line)

    response = '\n'.join(result_lines)

    # STEP 9: Final cleanup - remove excessive blank lines
    response = re.sub(r'\n{4,}', '\n\n\n', response)

    # STEP 10: Convert markdown bold (**text**) to Slack bold (*text*)
    # Match **text** but not ***text*** (which is already handled)
    response = re.sub(r'(?<!\*)\*\*([^*]+)\*\*(?!\*)', r'*\1*', response)

    return response


def format_markdown_to_blocks(markdown_text: str, title: str = None) -> list[list[dict]]:
    """
    Convert markdown text to formatted Slack blocks.
    Returns a list of block groups (to handle 50-block limit per message).
    """
    import re

    # Simple normalization (complex cleanup moved to normalize_formatting())
    markdown_text = normalize_formatting(markdown_text)

    blocks = []

    # Add header if provided
    if title:
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": title
            }
        })

    # Split into sections based on markdown headers
    lines = markdown_text.split('\n')
    current_section = []
    in_code_block = False
    code_block_lines = []
    code_language = ""

    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if not in_code_block:
                # Start of code block
                in_code_block = True
                code_language = line.strip()[3:].strip() or "text"
                code_block_lines = []
            else:
                # End of code block
                in_code_block = False
                if code_block_lines:
                    code_text = '\n'.join(code_block_lines)
                    # Limit code block size
                    if len(code_text) > 2500:
                        code_text = code_text[:2500] + "\n... (truncated)"
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"```{code_text}``"
                        }
                    })
                code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Handle dividers (---)
        if line.strip() == '---':
            # Flush current section before divider
            if current_section:
                section_text = '\n'.join(current_section).strip()
                if section_text:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": section_text
                        }
                    })
                current_section = []
            blocks.append({"type": "divider"})
            continue

        # Handle headers (## or ### heading)
        if line.startswith('### ') or line.startswith('## '):
            # Flush current section
            if current_section:
                section_text = '\n'.join(current_section).strip()
                if section_text:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": section_text
                        }
                    })
                current_section = []

            # Determine header level and extract text
            if line.startswith('### '):
                header_text = line[4:].strip()
            else:
                header_text = line[3:].strip()

            # Add header and divider
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{header_text}*"
                }
            })
            continue

        # Handle bold headers with multiple asterisks (***text*** or ****text****)
        # Convert to single asterisk for Slack bold
        stripped = line.strip()
        if (stripped.startswith('***') or stripped.startswith('****')) and len(stripped) > 6:
            # Flush current section
            if current_section:
                section_text = '\n'.join(current_section).strip()
                if section_text:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": section_text
                        }
                    })
                current_section = []

            # Remove all leading and trailing asterisks, then add single asterisk
            import re
            cleaned_line = re.sub(r'^\*+', '', stripped)  # Remove leading asterisks
            cleaned_line = re.sub(r'\*+$', '', cleaned_line)  # Remove trailing asterisks
            cleaned_line = cleaned_line.strip()
            if cleaned_line:
                current_section.append(f"*{cleaned_line}*")
            continue

        # Handle bold/emphasized lines (likely important callouts)
        if line.strip().startswith('**') and line.strip().endswith('**'):
            # Flush current section
            if current_section:
                section_text = '\n'.join(current_section).strip()
                if section_text:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": section_text
                        }
                    })
                current_section = []

            # Add as emphasized section
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": line
                }
            })
            continue

        # Add to current section
        current_section.append(line)

        # If current section gets too long, flush it
        if len('\n'.join(current_section)) > 2500:
            section_text = '\n'.join(current_section).strip()
            if section_text:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": section_text
                    }
                })
            current_section = []

    # Flush remaining section
    if current_section:
        section_text = '\n'.join(current_section).strip()
        if section_text:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": section_text
                }
            })

    # Split into groups of 45 blocks (leave room for feedback buttons)
    block_groups = []
    for i in range(0, len(blocks), 45):
        block_groups.append(blocks[i:i+45])

    return block_groups if block_groups else [[{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": markdown_text[:3000]
        }
    }]]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Main Lambda handler for Slack events.

    Routes to appropriate handler based on request type:
    - URL verification (Slack challenge)
    - Slash commands (/carl)
    - Events (app_mention, message)
    - Interactive components (buttons, modals)
    - Async processing (self-invoked)
    """
    logger.info("Received Slack event", extra={"path": event.get("rawPath", "")})

    # Health check endpoint for monitoring/integration tests
    if event.get("rawPath") == "/health" or event.get("path") == "/health":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "healthy",
                "service": "carl-api",
                "version": "1.0"
            })
        }

    # Keep-warm ping from CloudWatch Events (reduces cold starts)
    if event.get("action") == "keep_warm":
        logger.info("Keep-warm ping received")
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "warm"})
        }

    # Check if this is an async processing request (Lambda self-invoked)
    if event.get("action") == "process_ask_async":
        logger.info("Processing async ask command")
        slack = get_slack_service()
        return handle_ask_command_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("question")
        )

    if event.get("action") == "process_architect_async":
        logger.info("Processing async architect command (redirected to recommend)")
        slack = get_slack_service()
        return handle_recommend_command_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("question")
        )

    if event.get("action") == "process_recommend_async":
        logger.info("Processing async recommend command")
        slack = get_slack_service()
        return handle_recommend_command_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("requirement")
        )

    if event.get("action") == "process_report_async":
        logger.info("Processing async report command")
        slack = get_slack_service()
        return handle_report_command_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("report_type"),
            event.get("control_id")
        )

    if event.get("action") == "process_evidence_collect_async":
        logger.info("Processing async evidence collection")
        slack = get_slack_service()
        return handle_evidence_collect_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id")
        )

    if event.get("action") == "process_drift_scan_async":
        logger.info("Processing async drift scan")
        slack = get_slack_service()
        return handle_drift_scan_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id")
        )

    if event.get("action") == "process_jira_sync_async":
        logger.info("Processing async Jira sync")
        slack = get_slack_service()
        return handle_jira_sync_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("args", "")
        )

    if event.get("action") == "process_drift_jira_sync_async":
        logger.info("Processing async drift Jira sync")
        slack = get_slack_service()
        return handle_drift_jira_sync_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id")
        )

    if event.get("action") == "process_compliance_assess_async":
        logger.info("Processing async compliance assessment")
        slack = get_slack_service()
        return handle_compliance_assess_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("args", "")
        )

    if event.get("action") == "process_drift_show_fix_async":
        logger.info("Processing async drift show fix")
        slack = get_slack_service()
        return handle_drift_show_fix_sync(
            slack,
            event.get("channel_id"),
            event.get("drift_id")
        )

    if event.get("action") == "process_finding_details_async":
        logger.info("Processing async finding details")
        return handle_finding_details_sync(
            event.get("channel_id"),
            event.get("user_id"),
            event.get("finding_id"),
            event.get("account_id")
        )

    if event.get("action") == "process_status_async":
        logger.info("Processing async status command")
        slack = get_slack_service()
        return handle_status_command_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id")
        )

    if event.get("action") == "process_vpc_config_async":
        logger.info("Processing async VPC config submission")
        slack = get_slack_service()
        channel_id = event.get("channel_id")
        user_id = event.get("user_id")
        blueprint_name = event.get("blueprint_name")
        config = event.get("config")

        # Post confirmation message
        slack.post_message(
            channel_id,
            text=f"✅ Configuration received! Generating {blueprint_name} with CIDR {config.get('cidr')}..."
        )

        # Generate the Terraform code
        return handle_build_command(slack, channel_id, user_id, blueprint_name, config, trigger_id=None)

    if event.get("action") == "process_s3_config_async":
        logger.info("Processing async S3 config submission")
        slack = get_slack_service()
        channel_id = event.get("channel_id")
        user_id = event.get("user_id")
        blueprint_name = event.get("blueprint_name")
        config = event.get("config")

        # Post confirmation message
        slack.post_message(
            channel_id,
            text=f"✅ Configuration received! Generating {blueprint_name} with bucket name {config.get('name')}..."
        )

        # Generate the Terraform code
        return handle_build_command(slack, channel_id, user_id, blueprint_name, config, trigger_id=None)

    if event.get("action") == "process_intelligent_build":
        logger.info("Processing intelligent build request")
        slack = get_slack_service()
        channel_id = event.get("channel_id")
        user_id = event.get("user_id")
        requirement = event.get("requirement")
        trigger_id = event.get("trigger_id")

        return handle_intelligent_build(slack, channel_id, user_id, requirement, trigger_id)

    if event.get("action") == "generate_terraform_async":
        # datetime is imported at top of file (line 13)
        logger.info("Processing async Terraform generation")
        slack = get_slack_service()
        terraform_config = event.get("terraform_config", {})
        channel_id = terraform_config.get("channel_id")
        user_id = terraform_config.get("user_id")

        # Post initial message
        vpc_display = f"Create New ({terraform_config.get('vpc_cidr')})" if terraform_config.get('vpc_cidr') else f"Use Existing ({terraform_config.get('vpc_id')})"
        slack.post_message(
            channel_id,
            text=f"✅ Configuration Validated!\n\n"
                 f"• VPC: {vpc_display}\n"
                 f"• Prefix: `{terraform_config.get('prefix')}\n"
                 f"• Environment: {terraform_config.get('environment')}\n"
                 f"• Transit Gateway: {'Yes' if terraform_config.get('use_transit_gateway') else 'No'}\n\n"
                 f"⏳ Generating Terraform code with AI..."
        )

        # Generate Terraform using AI with progress updates
        try:
            logger.info("Starting Terraform generation")

            # Progress callback to update Slack message
            def post_progress(step: str):
                try:
                    slack.post_message(channel_id, text=f"⏳ {step}")
                except Exception as e:
                    logger.warning(f"Failed to post progress: {e}")

            terraform_files = _generate_terraform_with_ai(terraform_config, progress_callback=post_progress)
            logger.info("Terraform generation complete")

            # Create blueprint name from requirement
            requirement = terraform_config.get('requirement', 'infrastructure')
            blueprint_name = f"{requirement[:50].replace(' ', '-').lower()}/{terraform_config.get('prefix', 'infra')}"

            # Extract SOC 2 controls and best practices from README
            soc2_controls = _extract_soc2_controls(terraform_files.get('readme', ''))
            security_practices = _extract_security_practices(terraform_files.get('readme', ''))

            # Prepare metadata (clean up formatting)
            raw_option_text = terraform_config.get('option_text', '')
            # Convert escaped newlines to actual newlines for proper formatting
            clean_option_text = raw_option_text.replace('\\n', '\n').strip() if raw_option_text else ''

            metadata = {
                "requirement": requirement,
                "option_text": clean_option_text,
                "vpc_id": terraform_config.get('vpc_id'),
                "vpc_cidr": terraform_config.get('vpc_cidr'),
                "prefix": terraform_config.get('prefix'),
                "environment": terraform_config.get('environment'),
                "use_transit_gateway": terraform_config.get('use_transit_gateway'),
                "generated_at": datetime.now().isoformat(),
                "generated_by": "CARL AI-driven infrastructure builder",
                "soc2_controls": soc2_controls,
                "security_practices": security_practices
            }

            # Upload to GitHub and notify
            github = get_github_service()
            uploader = CodeUploader(github, slack)

            # Update message to show completion
            try:
                slack.update_message(
                    channel_id,
                    initial_msg.get('ts'),
                    text=f"✅ Configuration Validated!\n\n"
                         f"• VPC: {vpc_display}\n"
                         f"• Prefix: `{terraform_config.get('prefix')}\n"
                         f"• Environment: {terraform_config.get('environment')}\n"
                         f"• Transit Gateway: {'Yes' if terraform_config.get('use_transit_gateway') else 'No'}\n\n"
                         f"✅ Terraform code generated! Uploading to GitHub..."
                )
            except:
                pass

            upload_result = uploader.upload_and_notify(
                channel_id=channel_id,
                user_id=user_id,
                blueprint_name=blueprint_name,
                terraform_files=terraform_files,
                metadata=metadata
            )

            logger.info(f"Terraform uploaded to GitHub: {upload_result['pr_url']}")

        except Exception as e:
            stop_progress.set()  # Stop progress updates on error
            logger.exception(f"Error generating or uploading Terraform: {e}")

            # Update original message to show error
            try:
                slack.update_message(
                    channel_id,
                    initial_msg.get('ts'),
                    text=f"✅ Configuration Validated!\n\n"
                         f"• VPC: {vpc_display}\n"
                         f"• Prefix: `{terraform_config.get('prefix')}\n"
                         f"• Environment: {terraform_config.get('environment')}\n"
                         f"• Transit Gateway: {'Yes' if terraform_config.get('use_transit_gateway') else 'No'}\n\n"
                         f"❌ Failed to generate Terraform code"
                )
            except:
                pass

            slack.post_message(
                channel_id,
                text=f"❌ Error: {str(e)}\n\nPlease try again or contact support."
            )

        return {"statusCode": 200, "body": ""}

    if event.get("action") == "process_account_factory_generate":
        logger.info("Processing async Account Factory generation")
        slack = get_slack_service()
        channel_id = event.get("channel_id")
        user_id = event.get("user_id")
        session_id = event.get("session_id")

        from services.account_factory import get_account_factory_service
        # CodeUploader is imported at top of file (line 29)

        service = get_account_factory_service()
        session = service.get_session(session_id)

        if not session:
            slack.post_message(channel_id, text="❌ Session expired. Please start again with `/carl account-factory start`")
            return {"statusCode": 200, "body": ""}

        try:
            # Create status callback for live updates
            def status_update(message: str):
                """Post status updates to Slack."""
                slack.post_message(channel_id, text=message)

            # Initial status
            status_update("⏳ Starting AFT Terraform generation...")

            # Generate AFT Terraform with status updates
            result = service.generate_aft_terraform(session, status_callback=status_update)

            if not result["success"]:
                slack.post_message(channel_id, text=f"❌ Error: {result.get('error', 'Unknown error')}")
                return {"statusCode": 200, "body": ""}

            terraform_files = result["terraform_files"]
            metadata = result["metadata"]

            slack.post_message(channel_id, text=f"⏳ Generated {len(terraform_files)} files. Uploading to GitHub...")

            # Upload to GitHub
            github = get_github_service()
            uploader = CodeUploader(github, slack)

            # Build metadata for PR
            pr_metadata = {
                "description": f"AFT multi-account setup for {metadata['framework']} compliance",
                "framework": metadata["framework"],
                "accounts": metadata["total_accounts"],
                "vpcs": metadata["total_vpcs"],
                "estimated_cost": metadata["estimated_monthly_cost"],
                "primary_region": metadata["primary_region"],
                "scps": metadata["scps"],
                "generated_at": datetime.now().isoformat()
            }

            blueprint_name = f"account-factory/{metadata['framework'].lower().replace(' ', '-')}"

            upload_result = uploader.upload_and_notify(
                channel_id=channel_id,
                user_id=user_id,
                blueprint_name=blueprint_name,
                terraform_files=terraform_files,
                metadata=pr_metadata
            )

            logger.info(f"AFT code uploaded to GitHub: {upload_result['pr_url']}")

            # Show summary
            summary_text = f"✅ *AFT Configuration Generated!*\n\n"
            summary_text += f"• Framework: {metadata['framework']}\n"
            summary_text += f"• Accounts: {metadata['total_accounts']}\n"
            summary_text += f"• VPCs: {metadata['total_vpcs']}\n"
            summary_text += f"• Estimated Cost: {metadata['estimated_monthly_cost']}\n"
            summary_text += f"• SCPs: {', '.join(metadata['scps'])}\n"
            summary_text += f"\n*Files Generated:* {len(terraform_files)}\n"

            slack.post_message(channel_id, text=summary_text)

            # Clean up session
            if session_id in service.sessions:
                del service.sessions[session_id]

        except Exception as e:
            logger.exception(f"Error generating AFT code: {e}")
            slack.post_message(
                channel_id,
                text=f"❌ Error: {str(e)}\n\nPlease try again or contact support."
            )

        return {"statusCode": 200, "body": ""}

    if event.get("action") == "process_foundation_generate":
        logger.info("Processing async foundation generation")
        slack = get_slack_service()
        channel_id = event.get("channel_id")
        user_id = event.get("user_id")
        session_id = event.get("session_id")

        engine = get_decision_engine()
        session = engine.get_session(session_id)

        if not session:
            slack.post_message(channel_id, text="❌ Session expired. Please start again with `/carl foundation start`")
            return {"statusCode": 200, "body": ""}

        try:
            # Progress update
            slack.post_message(channel_id, text="⏳ Step 1/5: Generating Terraform modules (AI-driven)...")

            # Progress callback to show which module is being generated
            def progress_callback(message: str):
                slack.post_message(channel_id, text=f"   🔧 {message}")

            # Generate the code with progress updates
            builder = get_foundation_builder()
            modules = builder.generate_foundation(session, progress_callback=progress_callback)

            if not modules:
                slack.post_message(channel_id, text="❌ No Terraform code was generated. Please try again.")
                return {"statusCode": 200, "body": ""}

            # Progress update
            slack.post_message(channel_id, text="⏳ Step 2/5: Organizing files per Terraform best practices...")

            # Organize modules into proper Terraform file structure
            terraform_files = _organize_foundation_terraform_files(modules, session)

            if not terraform_files.get('main'):
                slack.post_message(channel_id, text="❌ No main Terraform content was generated. Please try again.")
                return {"statusCode": 200, "body": ""}

            # Progress update
            slack.post_message(channel_id, text="⏳ Step 3/5: Creating GitHub branch and PR...")

            # Upload to GitHub
            github = get_github_service()
            uploader = CodeUploader(github, slack)

            # Build metadata for the PR
            framework_name = session.framework.name if session.framework else "Best Practices"
            metadata = {
                "description": f"Foundation infrastructure for {framework_name} compliance",
                "requirements": session.requirements,
                "estimated_cost": f"${session.estimated_monthly_cost:.2f}/month" if session.estimated_monthly_cost else "N/A",
                "framework": framework_name,
                "vpcs": session.requirements.get("vpcs", []),
                "generated_at": datetime.now().isoformat(),
                "modules_generated": len(modules),
            }

            # Create a meaningful blueprint name
            blueprint_name = f"foundation/{framework_name.lower().replace(' ', '-')}"

            # Progress update
            slack.post_message(channel_id, text="⏳ Step 4/5: Committing files to GitHub...")

            upload_result = uploader.upload_and_notify(
                channel_id=channel_id,
                user_id=user_id,
                blueprint_name=blueprint_name,
                terraform_files=terraform_files,
                metadata=metadata
            )

            # Progress update
            slack.post_message(channel_id, text="⏳ Step 5/5: Finalizing...")

            logger.info(f"Foundation code uploaded to GitHub: {upload_result['pr_url']}")

            # Clean up session from memory (DynamoDB copy remains for history)
            if session_id in engine.sessions:
                del engine.sessions[session_id]

        except Exception as e:
            logger.exception(f"Error generating or uploading foundation code: {e}")
            slack.post_message(
                channel_id,
                text=f"❌ Error: {str(e)}\n\nPlease try again or contact support."
            )

        return {"statusCode": 200, "body": ""}

    # Parse request
    headers = event.get("headers", {})
    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)

    # Log all headers for debugging
    logger.info(f"All headers: {json.dumps(headers)}")

    if is_base64:
        import base64
        body = base64.b64decode(body).decode("utf-8")

    # Parse body first to check if it's a URL verification request
    # URL verification doesn't include valid Slack signatures, so check this first
    # Try to parse as JSON regardless of Content-Type header (API Gateway may not pass it)
    logger.info(f"Body length: {len(body)}")

    if body:
        try:
            payload = json.loads(body)
            request_type = payload.get("type", "")
            logger.info(f"Parsed JSON request type: {request_type}")

            # Skip signature verification for URL verification challenges
            if request_type == "url_verification":
                logger.info("URL verification request detected, bypassing signature check")
                return handle_url_verification(payload)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON body: {e}")
            pass

    # Verify Slack signature for all other requests
    # Headers may be lowercase or capitalized depending on API Gateway configuration
    timestamp = (headers.get("x-slack-request-timestamp") or
                 headers.get("X-Slack-Request-Timestamp") or "")
    signature = (headers.get("x-slack-signature") or
                 headers.get("X-Slack-Signature") or "")

    # If no timestamp/signature, this might be a malformed request
    if not timestamp or not signature:
        logger.warning(f"Missing Slack headers - timestamp: {bool(timestamp)}, signature: {bool(signature)}")
        logger.warning(f"Available headers: {list(headers.keys())}")
        return {"statusCode": 401, "body": json.dumps({"error": "Missing Slack signature headers"})}

    signing_secret = get_parameter(SLACK_SIGNING_SECRET_SSM)

    if not verify_slack_signature(signing_secret, timestamp, body, signature):
        logger.error("Invalid Slack signature")
        return {"statusCode": 401, "body": "Invalid signature"}

    # Parse body based on content type
    # Headers may be lowercase or capitalized
    content_type = (headers.get("content-type") or headers.get("Content-Type") or "").lower()
    logger.info(f"Content-Type for body parsing: {content_type}")

    if "application/json" in content_type:
        payload = json.loads(body)
        logger.info(f"Parsed as JSON: {list(payload.keys())}")
    elif "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body)
        logger.info(f"Parsed as URL-encoded, keys: {list(parsed.keys())}")
        # Check if it's an interaction payload
        if "payload" in parsed:
            payload = json.loads(parsed["payload"][0])
        else:
            payload = {k: v[0] for k, v in parsed.items()}
        logger.info(f"Final payload keys: {list(payload.keys())}")
    else:
        logger.warning(f"Unknown content type: {content_type}, attempting JSON parse")
        payload = json.loads(body) if body else {}

    # Route based on request type
    request_type = payload.get("type", "")
    path = event.get("rawPath", "")

    try:
        # URL verification challenge
        if request_type == "url_verification":
            return handle_url_verification(payload)

        # Slash commands
        if path == "/slack/commands" or "command" in payload:
            return handle_slash_command(payload)

        # Interactive components
        if path == "/slack/interactions" or request_type in [
            "block_actions",
            "view_submission",
            "shortcut",
        ]:
            return handle_interaction(payload)

        # Events
        if request_type == "event_callback":
            return handle_event(payload)

        logger.warning(f"Unknown request type: {request_type}")
        return {"statusCode": 200, "body": "OK"}

    except Exception as e:
        logger.exception("Error handling Slack request")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


def handle_url_verification(payload: dict) -> dict:
    """Handle Slack URL verification challenge."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"challenge": payload.get("challenge", "")}),
    }


def handle_slash_command(payload: dict) -> dict:
    """
    Handle /carl slash commands.

    Supported commands:
    - /carl status - Compliance posture summary
    - /carl findings [severity] - List findings
    - /carl help - Show help
    - /carl ask <question> - Natural language query
    """
    command = payload.get("command", "")
    text = payload.get("text", "").strip()
    channel_id = payload.get("channel_id", "")
    user_id = payload.get("user_id", "")

    logger.info(f"Slash command: {command} {text}", extra={"user": user_id})

    slack = get_slack_service()
    parts = text.split(maxsplit=1)
    subcommand = parts[0].lower() if parts else "help"
    args = parts[1] if len(parts) > 1 else ""

    if subcommand == "status":
        return handle_status_command(slack, channel_id, user_id)
    elif subcommand == "findings":
        # Parse findings subcommand
        parts_findings = args.split(maxsplit=1) if args else []
        findings_action = parts_findings[0] if parts_findings else "list"
        findings_args = parts_findings[1] if len(parts_findings) > 1 else ""

        if findings_action == "list":
            return handle_findings_list_command(slack, channel_id, user_id, findings_args)
        elif findings_action == "accept":
            return handle_findings_accept_command(slack, channel_id, user_id, findings_args)
        elif findings_action == "ignore":
            return handle_findings_ignore_command(slack, channel_id, user_id, findings_args)
        elif findings_action == "create-ticket":
            return handle_findings_create_ticket_command(slack, channel_id, user_id, findings_args)
        else:
            # Backward compatibility: treat as severity filter
            return handle_findings_list_command(slack, channel_id, user_id, args)
    elif subcommand == "ask":
        return handle_ask_command(slack, channel_id, user_id, args)
    elif subcommand == "recommend":
        return handle_recommend_command(slack, channel_id, user_id, args)
    elif subcommand == "build":
        trigger_id = payload.get("trigger_id")
        return handle_build_command(slack, channel_id, user_id, args, trigger_id=trigger_id)
    elif subcommand == "estimate":
        return handle_estimate_command(slack, channel_id, user_id, args)
    elif subcommand == "blueprints":
        return handle_blueprints_command(slack, channel_id, user_id)
    elif subcommand == "foundation":
        return handle_foundation_command(slack, channel_id, user_id, args)
    elif subcommand == "account-factory":
        return handle_account_factory_command(slack, channel_id, user_id, args)
    elif subcommand == "patterns":
        return handle_patterns_command(slack, channel_id, user_id, args)
    elif subcommand == "architect":
        return handle_architect_command(slack, channel_id, user_id, args)
    elif subcommand == "evidence":
        return handle_evidence_command(slack, channel_id, user_id, args)
    elif subcommand == "report":
        return handle_report_command(slack, channel_id, user_id, args)
    elif subcommand == "exception":
        return handle_exception_command(slack, channel_id, user_id, args)
    elif subcommand == "drift":
        return handle_drift_command(slack, channel_id, user_id, args)
    elif subcommand == "jira":
        return handle_jira_command(slack, channel_id, user_id, args)
    elif subcommand == "compliance":
        return handle_compliance_command(slack, channel_id, user_id, args)
    elif subcommand == "setup":
        return handle_setup_command(slack, channel_id, user_id, args, payload.get("trigger_id"), payload.get("team_id"))
    elif subcommand == "settings":
        return handle_settings_command(slack, channel_id, user_id, args, payload.get("team_id"))
    elif subcommand == "help":
        return handle_help_command(slack, channel_id, user_id)
    else:
        # Treat unknown subcommand as a question
        return handle_ask_command(slack, channel_id, user_id, text)


def handle_status_command(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Handle /carl status command - async wrapper for live scanning."""
    import boto3
    import json
    import os

    # Post immediate response
    slack.post_message(channel_id, text="🔍 Scanning your AWS environment for SOC 2 compliance status...")

    # Invoke async processing
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'action': 'process_status_async',
                'channel_id': channel_id,
                'user_id': user_id
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async status: {e}")
        # Fallback to synchronous
        return handle_status_command_sync(slack, channel_id, user_id)

    return {"statusCode": 200, "body": ""}


def handle_status_command_sync(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Handle /carl status command - synchronous version with live scanning."""
    import os
    from services.evidence_collector import EvidenceCollector
    from collections import defaultdict

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")
    findings_service = get_findings_service()

    try:
        # 1. LIVE SCAN - Environment-First Principle
        logger.info("🔍 Running live AWS environment scan for status check")
        collector = EvidenceCollector(
            evidence_bucket=evidence_bucket,
            evidence_table=evidence_table
        )

        # Collect all evidence
        all_evidence = collector.collect_all_evidence()

        # Analyze evidence to create findings
        findings = collector.create_findings_from_evidence(all_evidence)

        # Store new findings
        new_findings_count = 0
        for finding in findings:
            try:
                findings_service.store_finding(finding)
                new_findings_count += 1
            except Exception as e:
                logger.error(f"Failed to store finding: {e}")

        logger.info(f"✓ Live scan complete: {new_findings_count} findings created/updated")

        # 2. COMPLIANCE MAPPING - Compliance-Native Principle
        # Get all current findings (including newly created)
        all_findings = findings_service.get_recent_findings(limit=100)

        # Count by severity
        critical = sum(1 for f in all_findings if f.get('severity') == 'CRITICAL')
        high = sum(1 for f in all_findings if f.get('severity') == 'HIGH')
        medium = sum(1 for f in all_findings if f.get('severity') == 'MEDIUM')
        low = sum(1 for f in all_findings if f.get('severity') == 'LOW')
        total = len(all_findings)

        # Map findings to SOC 2 controls
        controls_with_issues = defaultdict(list)
        for finding in all_findings:
            control_ids = finding.get('control_ids', [])
            for control_id in control_ids:
                controls_with_issues[control_id].append(finding)

        # Calculate SOC 2 compliance percentage (43 total controls)
        total_soc2_controls = 43
        controls_violated = len(controls_with_issues)
        controls_compliant = total_soc2_controls - controls_violated
        compliance_percentage = int((controls_compliant / total_soc2_controls) * 100)

        # Determine audit impact
        audit_blockers = sum(1 for f in all_findings if f.get('severity') in ['CRITICAL', 'HIGH'])

        # Determine health status
        if critical > 0:
            health_status = "🔴 CRITICAL - Audit Blockers Found"
            health_emoji = "🔴"
        elif high > 5:
            health_status = "🟠 NEEDS ATTENTION - Multiple High Issues"
            health_emoji = "🟠"
        elif high > 0 or medium > 10:
            health_status = "🟡 MONITOR CLOSELY - Some Issues Found"
            health_emoji = "🟡"
        else:
            health_status = "🟢 HEALTHY - Audit Ready"
            health_emoji = "🟢"

        # Build Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 SOC 2 Compliance Status (Live Scan)"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Overall Status:* {health_status}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*SOC 2 Compliance*\n{health_emoji} {compliance_percentage}% Compliant"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Audit Blockers*\n🚫 {audit_blockers} Critical/High"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Security Findings (by Severity):*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"🔴 *Critical*\n{critical} (audit blockers)"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"🟠 *High*\n{high} (auditor will flag)"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"🟡 *Medium*\n{medium} (should fix)"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"⚪ *Low*\n{low} (nice to have)"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*SOC 2 Controls Affected:* {controls_violated} of {total_soc2_controls}"
                }
            }
        ]

        # Show top 3 violated controls
        if controls_with_issues:
            top_controls = sorted(controls_with_issues.items(), key=lambda x: len(x[1]), reverse=True)[:3]
            controls_text = []
            for control_id, control_findings in top_controls:
                count = len(control_findings)
                controls_text.append(f"• *{control_id}*: {count} finding{'s' if count > 1 else ''}")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Top Violated Controls:*\n" + "\n".join(controls_text)
                }
            })

        # Add action items
        blocks.extend([
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Next Steps:*\n" +
                           (f"1. Fix {audit_blockers} audit blockers immediately\n" if audit_blockers > 0 else "") +
                           f"2. Run /carl findings` to see all issues\n" +
                           f"3. Run /carl jira sync` to create tickets\n" +
                           f"4. Run /carl evidence collect` to refresh data"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🔍 Live scan completed just now | {total} total findings"
                    }
                ]
            }
        ])

        slack.post_message(channel_id, blocks=blocks)

        return {"statusCode": 200, "body": ""}

    except Exception as e:
        logger.exception("Error in status command")
        slack.post_message(channel_id, text=f"❌ Failed to get status: {str(e)}")
        return {"statusCode": 200, "body": ""}


def handle_findings_list_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl findings list command."""
    findings_service = get_findings_service()

    severity = args.upper() if args else None
    findings = findings_service.get_recent_findings(severity=severity, limit=10)

    if not findings:
        slack.post_message(
            channel_id,
            text=f"No {severity.lower() if severity else ''} findings found.",
        )
        return {"statusCode": 200, "body": ""}

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Recent {severity or 'All'} Findings",
            },
        },
    ]

    for finding in findings[:10]:
        # Build finding text with Jira link if available
        finding_id = finding.get('id', '')
        jira_ticket_id = finding.get("jira_ticket_id")
        jira_url = finding.get("jira_url")
        status = finding.get("status", "NEW")

        finding_text = (
            f"*{finding.get('severity', 'UNKNOWN')}* | "
            f"{finding.get('title', 'No title')}\n"
            f"Resource: `{finding.get('resource_id', 'N/A')}\n"
            f"Status: {status}"
        )

        if jira_ticket_id and jira_url:
            finding_text += f"\n🔗 Jira: <{jira_url}|{jira_ticket_id}>"

        # Section with finding info
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": finding_text
            }
        })

        # Action buttons based on status
        action_buttons = []

        # Show "Create Ticket" if no ticket and not accepted/ignored
        if not jira_ticket_id and status not in ["ACCEPTED_RISK", "IGNORED", "SUPPRESSED", "REMEDIATED"]:
            action_buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "🎫 Create Ticket"},
                "action_id": f"finding_create_ticket_{finding_id}",
                "style": "primary"
            })

        # Show "Accept Risk" if not already accepted/ignored/remediated
        if status not in ["ACCEPTED_RISK", "IGNORED", "REMEDIATED"]:
            action_buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Accept Risk"},
                "action_id": f"finding_accept_risk_{finding_id}",
            })

        # Show "Ignore" if not already ignored/remediated
        if status not in ["IGNORED", "REMEDIATED"]:
            action_buttons.append({
                "type": "button",
                "text": {"type": "plain_text", "text": "👁️ Ignore"},
                "action_id": f"finding_ignore_{finding_id}",
            })

        # Show "Show Fix" button for remediable findings
        action_buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "🔧 Show Fix"},
            "action_id": f"finding_show_fix_{finding_id}",
            "style": "primary"
        })

        # Always show "Details" button
        action_buttons.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "ℹ️ Details"},
            "action_id": f"finding_details_{finding_id}",
        })

        if action_buttons:
            blocks.append({
                "type": "actions",
                "elements": action_buttons
            })

        # Add divider between findings
        blocks.append({"type": "divider"})

    # Add reminder to refresh evidence
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "💡 _To refresh findings with latest AWS state, run /carl evidence collect`_"
            }
        ]
    })

    slack.post_message(channel_id, blocks=blocks)

    return {"statusCode": 200, "body": ""}


def handle_findings_accept_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl findings accept <id> "<justification>" command."""
    import re
    from services.findings_service import FindingsService

    findings_service = FindingsService()

    # Parse: finding_id "justification"
    # Support both: finding-123 "text" and finding-123 text
    match = re.match(r'(\S+)\s+"([^"]+)"', args) or re.match(r'(\S+)\s+(.+)', args)

    if not match:
        slack.post_message(
            channel_id,
            text='Usage: /carl findings accept <finding_id> "<justification>"\nExample: /carl findings accept finding-04a95 "Dev environment, accepted risk"`'
        )
        return {"statusCode": 200, "body": ""}

    finding_id, justification = match.groups()

    # Get account ID (would normally come from context, using env for now)
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Accept the risk
    success = findings_service.accept_risk(
        finding_id=finding_id,
        account_id=account_id,
        justification=justification,
        accepted_by=user_id
    )

    if success:
        slack.post_message(
            channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ Risk accepted for finding {finding_id}\n\n*Justification:* {justification}\n*Accepted by:* <@{user_id}>"
                    }
                }
            ]
        )
    else:
        slack.post_message(
            channel_id,
            text=f"❌ Failed to accept risk for finding {finding_id}. Finding may not exist."
        )

    return {"statusCode": 200, "body": ""}


def handle_findings_ignore_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl findings ignore <id> command."""
    from services.findings_service import FindingsService

    findings_service = FindingsService()

    if not args:
        slack.post_message(
            channel_id,
            text='Usage: /carl findings ignore <finding_id>\nExample: /carl findings ignore finding-04a95`'
        )
        return {"statusCode": 200, "body": ""}

    finding_id = args.strip()

    # Get account ID
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Ignore the finding
    success = findings_service.ignore_finding(
        finding_id=finding_id,
        account_id=account_id,
        ignored_by=user_id
    )

    if success:
        slack.post_message(
            channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"👁️ Finding {finding_id} marked as ignored\n*By:* <@{user_id}>"
                    }
                }
            ]
        )
    else:
        slack.post_message(
            channel_id,
            text=f"❌ Failed to ignore finding {finding_id}. Finding may not exist."
        )

    return {"statusCode": 200, "body": ""}


def handle_findings_create_ticket_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl findings create-ticket <id> [<id> ...] command - uses AI-enhanced logic."""
    from services.findings_service import FindingsService
    from services.jira_security_sync import JiraSecuritySync

    findings_service = FindingsService()

    if not args:
        slack.post_message(
            channel_id,
            text='Usage: /carl findings create-ticket <finding_id> [<finding_id> ...]\nExample: /carl findings create-ticket finding-04a95 finding-9f705`'
        )
        return {"statusCode": 200, "body": ""}

    finding_ids = args.strip().split()

    # Get account ID
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Get Jira sync service (uses AI for ticket descriptions)
    try:
        jira_sync = JiraSecuritySync()
    except Exception as e:
        logger.error(f"Failed to initialize Jira service: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Jira is not configured. Please set up Jira credentials first."
        )
        return {"statusCode": 200, "body": ""}

    created = []
    failed = []

    for finding_id in finding_ids:
        try:
            # Get finding
            finding = findings_service.get_finding(finding_id, account_id)
            if not finding:
                failed.append(f"{finding_id} (not found)")
                continue

            # Skip if already has ticket
            if finding.get('jira_ticket_id'):
                failed.append(f"{finding_id} (already has ticket)")
                continue

            # Create Jira ticket using AI-enhanced sync logic
            result = jira_sync.sync_finding_to_jira(
                finding_id=finding_id,
                title=finding.get('title', 'Security Finding'),
                severity=finding.get('severity', 'MEDIUM'),
                resource_type=finding.get('resource_type', 'Unknown'),
                resource_id=finding.get('resource_id', 'N/A'),
                compliance_status=finding.get('compliance_status', 'FAILED'),
                recommendation=finding.get('remediation_steps', finding.get('description', 'Review this finding')),
                aws_account_id=account_id,
                region=finding.get('region', 'us-east-1'),
                metadata={"control_ids": finding.get('control_ids', [])}  # Pass SOC 2 controls for AI context
            )

            if result["success"]:
                created.append((finding_id, result['jira_key'], result['jira_url']))
            else:
                failed.append(f"{finding_id} ({result.get('error', 'unknown error')})")

        except Exception as e:
            logger.exception(f"Error creating ticket for {finding_id}")
            failed.append(f"{finding_id} ({str(e)})")

    # Post results
    result_text = []
    if created:
        result_text.append(f"✅ Created {len(created)} ticket(s):")
        for fid, ticket_id, ticket_url in created:
            result_text.append(f"  • {fid} → <{ticket_url}|{ticket_id}>")

    if failed:
        result_text.append(f"\n❌ Failed {len(failed)} finding(s):")
        for failure in failed:
            result_text.append(f"  • {failure}")

    slack.post_message(channel_id, text="\n".join(result_text))

    return {"statusCode": 200, "body": ""}


def handle_ask_command(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """Handle /carl ask command - natural language query."""
    if not question:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "response_type": "ephemeral",
                "text": "Please provide a question. Example: /carl ask What is my S3 compliance status?"
            })
        }

    # Post "Thinking..." message via Slack API (not in HTTP response)
    slack.post_message(channel_id, text=f"🤔 Analyzing your question...")

    # Invoke async processing in background
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'action': 'process_ask_async',
                'channel_id': channel_id,
                'user_id': user_id,
                'question': question
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async processing: {e}")
        # Fallback to synchronous if async fails
        return handle_ask_command_sync(slack, channel_id, user_id, question)

    # Return empty 200 OK immediately to Slack (prevents timeout)
    return {"statusCode": 200, "body": ""}


def classify_question_type(question: str) -> str:
    """
    Classify a question as 'compliance' (scan existing) or 'architecture' (design new).

    Args:
        question: User's question

    Returns:
        'compliance' or 'architecture'
    """
    from services.bedrock_service import BedrockService

    question_lower = question.lower()

    # Simple heuristics first (fast path)
    # Architecture = "how do I build/setup something new?"
    architecture_keywords = [
        "design", "build", "create", "architect", "recommend", "best practice",
        "should i use", "what service", "which is better", "how to implement",
        "what's the best way", "how much would", "cost estimate", "pricing",
        "options for", "alternatives to",
        # "How to build" patterns
        "setup", "set up", "deploy", "launch", "host", "run a", "install",
        "how do i", "how do you", "how would", "how should", "how can i",
        "want to", "need to", "looking to", "trying to",
        "migrate", "move to", "switch to",
        "configure a", "configure new", "new vpc", "new bucket", "new database"
    ]

    # Compliance = "what's the status of my existing resources?"
    compliance_keywords = [
        "is my", "are my", "do i have", "am i", "show me my", "check my",
        "my vpc", "my bucket", "my iam", "my s3", "my ec2", "my security",
        "currently configured", "currently enabled", "compliant", "secure",
        "vulnerability", "findings", "status of my", "scan my", "audit my",
        "what does my", "how is my"
    ]

    arch_score = sum(1 for kw in architecture_keywords if kw in question_lower)
    comp_score = sum(1 for kw in compliance_keywords if kw in question_lower)

    if arch_score > comp_score:
        return "architecture"
    elif comp_score > arch_score:
        return "compliance"
    else:
        # Ambiguous - use AI to classify
        bedrock = BedrockService()
        prompt = f"""Classify this AWS question as either "COMPLIANCE" or "ARCHITECTURE":

Question: {question}

- COMPLIANCE: Questions about existing deployed AWS resources (checking status, configuration, security)
- ARCHITECTURE: Questions about what to build or how to design something new

Reply with ONLY one word: COMPLIANCE or ARCHITECTURE"""

        try:
            response = bedrock.bedrock_client.invoke_model(
                modelId=bedrock.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 10,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )

            response_body = json.loads(response['body'].read())
            classification = response_body['content'][0]['text'].strip().upper()

            if "ARCHITECTURE" in classification:
                return "architecture"
            else:
                return "compliance"

        except Exception as e:
            logger.warning(f"AI classification failed: {e}, defaulting to compliance")
            return "compliance"


def handle_architecture_question(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """
    Handle architecture/design questions - REDIRECTS to recommend handler.

    Consolidated to avoid code duplication. All architecture questions
    now use the same handler as /carl recommend.
    """
    # Redirect to consolidated recommend handler
    return handle_recommend_command_sync(slack, channel_id, user_id, question)


def _scan_results_to_context_summary(scan_results: dict) -> str:
    """
    Convert AWSResourceScanner results to human-readable context summary for AI.

    Args:
        scan_results: Dict of ResourceScanResult objects by service from AWSResourceScanner

    Returns:
        Human-readable summary string for AI context
    """
    summary = "AWS ENVIRONMENT SCAN RESULTS\n\n"

    # Count total resources
    total_resources = sum(len(items) for items in scan_results.values())
    summary += f"Total Resources Scanned: {total_resources} across {len(scan_results)} service categories\n\n"

    # IAM
    if 'iam' in scan_results and scan_results['iam']:
        iam_items = scan_results['iam']
        user_count = sum(1 for r in iam_items if 'User' in r.resource_type)
        role_count = sum(1 for r in iam_items if 'Role' in r.resource_type)
        summary += f"IAM: {user_count} users, {role_count} roles\n"

    # S3
    if 's3' in scan_results and scan_results['s3']:
        summary += f"S3: {len(scan_results['s3'])} buckets\n"

    # VPC
    if 'vpc' in scan_results and scan_results['vpc']:
        vpc_items = scan_results['vpc']
        vpc_count = sum(1 for r in vpc_items if r.resource_type == "AWS::EC2::VPC")
        sg_count = sum(1 for r in vpc_items if 'SecurityGroup' in r.resource_type)
        summary += f"VPC/Networking: {vpc_count} VPCs, {sg_count} security groups\n"

    # EC2
    if 'ec2' in scan_results and scan_results['ec2']:
        summary += f"EC2: {len(scan_results['ec2'])} instances\n"

    summary += "\nNOTE: Use this environment data to answer the user's question with specific details about their AWS resources.\n"

    return summary


def _evidence_to_context_summary(evidence_results: dict) -> str:
    """
    Convert evidence collection results to human-readable context summary for AI.

    Args:
        evidence_results: Dict of evidence items by category from EvidenceCollector

    Returns:
        Human-readable summary string for AI context
    """
    summary = "AWS ENVIRONMENT SCAN RESULTS\n\n"

    # Count total resources
    total_resources = sum(len(items) for items in evidence_results.values())
    summary += f"Total Resources Scanned: {total_resources} across {len(evidence_results)} service categories\n\n"

    # IAM
    if 'iam' in evidence_results and evidence_results['iam']:
        iam_items = evidence_results['iam']
        user_count = sum(1 for e in iam_items if 'iam_user' in getattr(e, 'resource_type', ''))
        role_count = sum(1 for e in iam_items if 'iam_role' in getattr(e, 'resource_type', ''))
        summary += f"IAM: {user_count} users, {role_count} roles\n"

    # S3
    if 's3' in evidence_results and evidence_results['s3']:
        s3_items = evidence_results['s3']
        summary += f"S3: {len(s3_items)} buckets\n"

    # EC2
    if 'ec2' in evidence_results and evidence_results['ec2']:
        ec2_items = evidence_results['ec2']
        summary += f"EC2: {len(ec2_items)} instances\n"

    # RDS
    if 'rds' in evidence_results and evidence_results['rds']:
        rds_items = evidence_results['rds']
        summary += f"RDS: {len(rds_items)} database instances\n"

    # Lambda
    if 'lambda' in evidence_results and evidence_results['lambda']:
        lambda_items = evidence_results['lambda']
        summary += f"Lambda: {len(lambda_items)} functions\n"

    # VPC
    if 'vpc' in evidence_results and evidence_results['vpc']:
        vpc_items = evidence_results['vpc']
        summary += f"VPC/Networking: {len(vpc_items)} resources\n"

    # Security Services
    security_services = []
    if 'guardduty' in evidence_results and evidence_results['guardduty']:
        security_services.append(f"GuardDuty ({len(evidence_results['guardduty'])} items)")
    if 'security_hub' in evidence_results and evidence_results['security_hub']:
        security_services.append(f"Security Hub ({len(evidence_results['security_hub'])} items)")
    if 'inspector' in evidence_results and evidence_results['inspector']:
        security_services.append(f"Inspector ({len(evidence_results['inspector'])} items)")
    if 'macie' in evidence_results and evidence_results['macie']:
        security_services.append(f"Macie ({len(evidence_results['macie'])} items)")

    if security_services:
        summary += f"Security Services: {', '.join(security_services)}\n"

    # CloudTrail
    if 'cloudtrail' in evidence_results and evidence_results['cloudtrail']:
        summary += f"CloudTrail: {len(evidence_results['cloudtrail'])} trails\n"

    # Config
    if 'config' in evidence_results and evidence_results['config']:
        summary += f"AWS Config: {len(evidence_results['config'])} recorders/rules\n"

    # KMS
    if 'kms' in evidence_results and evidence_results['kms']:
        summary += f"KMS: {len(evidence_results['kms'])} customer-managed keys\n"

    # Secrets Manager
    if 'secrets_manager' in evidence_results and evidence_results['secrets_manager']:
        summary += f"Secrets Manager: {len(evidence_results['secrets_manager'])} secrets\n"

    # DynamoDB
    if 'dynamodb' in evidence_results and evidence_results['dynamodb']:
        summary += f"DynamoDB: {len(evidence_results['dynamodb'])} tables\n"

    # ECS
    if 'ecs' in evidence_results and evidence_results['ecs']:
        summary += f"ECS: {len(evidence_results['ecs'])} clusters/services\n"

    # EKS
    if 'eks' in evidence_results and evidence_results['eks']:
        summary += f"EKS: {len(evidence_results['eks'])} clusters\n"

    # CloudWatch
    if 'cloudwatch' in evidence_results and evidence_results['cloudwatch']:
        summary += f"CloudWatch: {len(evidence_results['cloudwatch'])} log groups/alarms\n"

    summary += "\nNOTE: Use this environment data to answer the user's question with specific details about their AWS resources.\n"

    return summary


def handle_ask_command_sync(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """
    Synchronous version of ask command - uses AgentCore for intelligent Q&A.
    Falls back to local scanning if AgentCore is not configured or fails.
    """
    import os
    import time
    import uuid
    from services.learning_service import LearningService

    logger.info(f"Processing ask command: {question}")
    scan_start_time = time.time()

    # Classify question type first
    question_type = classify_question_type(question)
    logger.info(f"Question classified as: {question_type}")

    # Route architecture questions to architecture handler
    if question_type == "architecture":
        logger.info("Routing to architecture agent")
        return handle_architecture_question(slack, channel_id, user_id, question)

    # Try AgentCore first (Phase 1 - intelligent Q&A with scanning)
    agentcore_arn = os.environ.get("AGENTCORE_ASK_RUNTIME_ARN", "")
    response = None
    session_id = str(uuid.uuid4())

    if agentcore_arn:
        logger.info(f"Using AgentCore for /carl ask: {agentcore_arn}")
        slack.post_message(channel_id, text="🤖 Analyzing your question with CARL AgentCore...")

        result = invoke_agentcore_ask(question, session_id)

        if result["success"]:
            response = result["response"]
            logger.info(f"AgentCore response: {len(response)} chars")
        else:
            logger.warning(f"AgentCore failed: {result.get('error')}, falling back to local scanning")
            slack.post_message(channel_id, text="⚠️ AgentCore unavailable, falling back to local scanning...")

    # Fallback to local scanning if AgentCore not configured or failed
    if not response:
        logger.info("Using local scanning fallback")
        response = _handle_ask_with_local_scanning(slack, channel_id, question)

    # Calculate duration
    scan_duration_ms = int((time.time() - scan_start_time) * 1000)

    # Log interaction for learning
    interaction_id = None
    try:
        learning_service = LearningService(
            scan_history_table=os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history"),
            resource_graph_table=os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")
        )

        interaction_id = learning_service.log_interaction(
            user_id=user_id,
            question=question,
            scans_performed=["agentcore"] if agentcore_arn else ["local_scanner"],
            resources_found=[],
            scan_duration_ms=scan_duration_ms,
            metadata={"channel_id": channel_id, "session_id": session_id}
        )
        logger.info(f"Logged interaction {interaction_id} for learning")
    except Exception as e:
        logger.warning(f"Failed to log interaction for learning: {e}")

    # Format and post response
    formatted_blocks = format_markdown_to_blocks(response, "💬 CARL's Response")
    for block_group in formatted_blocks:
        slack.post_message(channel_id, blocks=block_group)

    # Add action buttons for follow-up actions
    action_buttons = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_Need more details?_"
            }
        },
        {
            "type": "actions",
            "block_id": f"ask_actions_{session_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🔍 Deep Scan",
                        "emoji": True
                    },
                    "value": json.dumps({"action": "deep_scan", "question": question, "session_id": session_id}),
                    "action_id": "ask_deep_scan"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Full Report",
                        "emoji": True
                    },
                    "value": json.dumps({"action": "full_report", "question": question, "session_id": session_id}),
                    "action_id": "ask_full_report"
                }
            ]
        }
    ]

    # Add feedback buttons if interaction was logged
    if interaction_id:
        action_buttons.append({
            "type": "divider"
        })
        action_buttons.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_Was this answer helpful?_"
            }
        })
        action_buttons.append({
            "type": "actions",
            "block_id": f"feedback_{interaction_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "👍 Yes",
                        "emoji": True
                    },
                    "value": f"{interaction_id}:helpful",
                    "action_id": "feedback_positive"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "👎 No",
                        "emoji": True
                    },
                    "value": f"{interaction_id}:not_helpful",
                    "action_id": "feedback_negative"
                }
            ]
        })

    slack.post_message(channel_id, blocks=action_buttons)


def _handle_ask_with_local_scanning(slack: SlackService, channel_id: str, question: str) -> str:
    """
    Fallback handler that uses local AWS scanning (original implementation).
    Used when AgentCore is not configured or fails.
    """
    import os
    from services.aws_resource_scanner import AWSResourceScanner
    from services.learning_service import LearningService

    bedrock = get_bedrock_service()
    context = ""

    try:
        logger.info("🔍 Performing local AWS environment scan...")
        slack.post_message(channel_id, text="🔍 Scanning your AWS environment...")

        scanner = AWSResourceScanner(region=os.environ.get("AWS_REGION", "us-east-1"))

        total_resources_scanned = 0

        def progress_callback(service_name, completed, total, resources_found):
            nonlocal total_resources_scanned
            total_resources_scanned += resources_found
            percent = int((completed / total) * 100)
            if percent in [25, 50, 75] or completed == total:
                slack.post_message(
                    channel_id,
                    text=f"⏳ Scanning: {completed}/{total} services ({percent}%) - {total_resources_scanned} resources"
                )

        scan_results = scanner.scan_all(progress_callback=progress_callback)
        environment_summary = _scan_results_to_context_summary(scan_results)

        total_resources = sum(len(items) for items in scan_results.values())
        logger.info(f"✅ Scan complete: {total_resources} resources")

        # Get learned context
        learning_service = LearningService(
            scan_history_table=os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history"),
            resource_graph_table=os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")
        )
        learned_context = learning_service.get_learned_context(question, interaction_type="ask")

        context = environment_summary
        if learned_context:
            context += f"\n\n{learned_context}"

    except Exception as e:
        logger.error(f"Local scanning failed: {e}", exc_info=True)
        context += f"\nNote: Environment scan error: {str(e)}\n"
        slack.post_message(channel_id, text="⚠️ Scan error, proceeding with available information...")

    return bedrock.ask_compliance_question(question, context)


def handle_ask_deep_scan(payload: dict, action: dict) -> dict:
    """
    Handle Deep Scan button click from /carl ask response.
    Runs a comprehensive scan with more detail.
    """
    import os
    from services.aws_resource_scanner import AWSResourceScanner

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    slack = get_slack_service()

    # Parse the action value
    try:
        action_data = json.loads(action.get("value", "{}"))
        question = action_data.get("question", "")
        session_id = action_data.get("session_id", "")
    except json.JSONDecodeError:
        question = ""
        session_id = ""

    # Update the message to show scanning is in progress
    message_ts = payload.get("message", {}).get("ts", "")
    slack.post_message(channel, text=f"🔬 *Deep Scan requested* - Running comprehensive AWS scan...\n_Original question: {question}_")

    # Perform comprehensive scan
    try:
        scanner = AWSResourceScanner(region=os.environ.get("AWS_REGION", "us-east-1"))
        scan_results = scanner.scan_all()

        # Build detailed summary
        total_resources = sum(len(items) for items in scan_results.values())

        # Convert to context for AI
        environment_summary = _scan_results_to_context_summary(scan_results)

        # Generate deep analysis using AgentCore or Bedrock
        agentcore_arn = os.environ.get("AGENTCORE_ASK_RUNTIME_ARN", "")
        deep_prompt = f"""The user asked: "{question}"

They requested a DEEP SCAN for more details. Here is comprehensive AWS environment data:

{environment_summary}

Please provide a DETAILED analysis with:
1. Specific resource names, IDs, and configurations
2. Any compliance concerns or security issues found
3. Specific recommendations with remediation steps
4. Resource counts and statistics

Be thorough and specific - the user wants maximum detail."""

        if agentcore_arn:
            result = invoke_agentcore_ask(deep_prompt, session_id)
            if result["success"]:
                response = result["response"]
            else:
                bedrock = get_bedrock_service()
                response = bedrock.ask_compliance_question(deep_prompt, "")
        else:
            bedrock = get_bedrock_service()
            response = bedrock.ask_compliance_question(deep_prompt, "")

        # Post deep scan results
        formatted_blocks = format_markdown_to_blocks(response, "🔬 Deep Scan Results")
        for block_group in formatted_blocks:
            slack.post_message(channel, blocks=block_group)

    except Exception as e:
        logger.error(f"Deep scan failed: {e}", exc_info=True)
        slack.post_message(channel, text=f"❌ Deep scan failed: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_ask_full_report(payload: dict, action: dict) -> dict:
    """
    Handle Full Report button click from /carl ask response.
    Generates a comprehensive compliance report.
    """
    import os
    from services.aws_resource_scanner import AWSResourceScanner

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    slack = get_slack_service()

    # Parse the action value
    try:
        action_data = json.loads(action.get("value", "{}"))
        question = action_data.get("question", "")
        session_id = action_data.get("session_id", "")
    except json.JSONDecodeError:
        question = ""
        session_id = ""

    slack.post_message(channel, text=f"📊 *Full Report requested* - Generating comprehensive compliance report...\n_Original question: {question}_")

    try:
        # Run comprehensive scan
        scanner = AWSResourceScanner(region=os.environ.get("AWS_REGION", "us-east-1"))
        scan_results = scanner.scan_all()

        environment_summary = _scan_results_to_context_summary(scan_results)
        total_resources = sum(len(items) for items in scan_results.values())

        # Generate full report using AgentCore or Bedrock
        report_prompt = f"""Generate a FULL COMPLIANCE REPORT for this AWS environment.

User's original question: "{question}"

AWS Environment Data:
{environment_summary}

Generate a comprehensive compliance report with the following sections:

## Executive Summary
- Overall compliance posture (percentage estimate)
- Key findings summary
- Critical issues requiring immediate attention

## Resource Inventory
- List all resources found by category
- Include resource IDs and key configurations

## Compliance Findings
For each finding:
- Severity (CRITICAL/HIGH/MEDIUM/LOW)
- Resource affected
- Issue description
- SOC 2 control mapping
- Remediation recommendation

## Recommendations
- Prioritized list of actions
- Quick wins (easy to fix)
- Strategic improvements

## Next Steps
- Specific actions the team should take

Format this as a professional compliance report."""

        agentcore_arn = os.environ.get("AGENTCORE_ASK_RUNTIME_ARN", "")

        if agentcore_arn:
            result = invoke_agentcore_ask(report_prompt, session_id)
            if result["success"]:
                response = result["response"]
            else:
                bedrock = get_bedrock_service()
                response = bedrock.ask_compliance_question(report_prompt, "")
        else:
            bedrock = get_bedrock_service()
            response = bedrock.ask_compliance_question(report_prompt, "")

        # Post full report
        formatted_blocks = format_markdown_to_blocks(response, "📊 Full Compliance Report")
        for block_group in formatted_blocks:
            slack.post_message(channel, blocks=block_group)

        # Add follow-up actions
        report_actions = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Report generated. What would you like to do next?_"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📥 Export to PDF",
                            "emoji": True
                        },
                        "value": "export_pdf",
                        "action_id": "report_export_pdf"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🎫 Create Jira Tickets",
                            "emoji": True
                        },
                        "value": "create_tickets",
                        "action_id": "report_create_tickets"
                    }
                ]
            }
        ]
        slack.post_message(channel, blocks=report_actions)

    except Exception as e:
        logger.error(f"Full report generation failed: {e}", exc_info=True)
        slack.post_message(channel, text=f"❌ Report generation failed: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_help_command(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Handle /carl help command - returns immediate response for orange Slack formatting."""

    # Return immediate in-channel response (shows with formatting)
    response = {
        "response_type": "in_channel",
        "text": "*CARL - Cloud Automated Risk & Compliance Logic*\n\n*Setup & Configuration:*\n• `/carl setup start` - Initial setup wizard (first-time setup)\n• `/carl setup status` - View setup status\n• `/carl settings` - View current configuration\n\n*Compliance Commands:*\n• `/carl status` - View compliance posture summary\n• `/carl compliance assess` - Run complete SOC 2 compliance assessment with remediation plan\n• `/carl compliance status` - Show current compliance assessment status\n• `/carl findings list [severity]` - List recent findings with interactive buttons\n• `/carl findings accept <id> '<justification>'` - Accept risk with documented justification\n• `/carl findings ignore <id>` - Ignore a finding (will not create ticket)\n• `/carl findings create-ticket <id> [<id> ...]` - Create Jira tickets for specific findings\n• `/carl ask <question>` - Ask compliance questions\n\n*Architecture & Build Commands:*\n• `/carl recommend <requirement>` - Smart: AI analyzes needs, scans environment, recommends with costs\n• `/carl build <blueprint>` - Quick: Pick from templates, fill params, generate code & PR instantly\n• `/carl blueprints` - List all quick-build templates\n• `/carl estimate <component>` - Get cost estimates\n\n*Foundation Builder:*\n• `/carl foundation start` - Start guided foundation building wizard\n• `/carl foundation status` - Check current foundation session\n• `/carl foundation cancel` - Cancel current session\n• `/carl patterns [category]` - View architecture patterns with pros/cons\n\n*Account Factory (Multi-Account Setup):*\n• `/carl account-factory start` - Start AFT-based multi-account setup wizard\n• `/carl account-factory status` - Check current session status\n• `/carl account-factory cancel` - Cancel current session\n\n*AI Architecture Advisor:*\n• `/carl architect <question>` - Ask AI for architecture recommendations (learns from feedback)\n\n*Audit & Evidence:*\n• `/carl evidence collect` - Collect audit evidence across all resources\n• `/carl evidence list [type]` - View all collected evidence items\n• `/carl evidence status` - View evidence collection status\n• `/carl report executive` - Generate executive compliance summary\n• `/carl report full` - Generate full audit report\n• `/carl report control <control-id>` - Generate control-specific report\n\n*Risk Management:*\n• `/carl exception request` - Request a risk exception\n• `/carl exception list` - View pending/active exceptions\n• `/carl exception approve <id>` - Approve an exception (requires permission)\n\n*Drift Detection:*\n• `/carl drift scan` - Run drift detection scan\n• `/carl drift status` - View current drift summary\n• `/carl drift details <drift-id>` - View drift item details\n• `/carl drift jira-sync` - Create Jira tickets for drift items\n\n*Jira Integration:*\n• `/carl jira test` - Test Jira connection and permissions\n• `/carl jira sync` - Sync findings to Jira tickets\n• `/carl jira status` - View Jira integration statistics\n\n*Coming Soon:*\n• `/carl remediate <finding-id>` - Request auto-remediation\n\n*Examples:*\n• `/carl foundation start` - Build your AWS foundation from scratch\n• `/carl patterns egress` - See egress architecture options\n• `/carl recommend compliant VPC with firewall`\n• `/carl build networking/standard-vpc`\n• `/carl estimate rds multi-az db.r5.large`"
    }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response)
    }


def handle_setup_command(
    slack: SlackService, channel_id: str, user_id: str, args: str, trigger_id: str = None, team_id: str = None
) -> dict:
    """Handle /carl setup command - initial setup wizard."""
    from services.setup_service import SetupService

    setup = SetupService()
    parts = args.split() if args else []
    subcommand = parts[0].lower() if parts else "start"

    # Get workspace ID from payload or fallback to API call
    workspace_id = team_id
    if not workspace_id:
        try:
            team_info = slack.client.team_info()
            workspace_id = team_info["team"]["id"]
        except Exception as e:
            logger.error(f"Failed to get workspace ID: {e}")
            slack.post_message(channel_id, text="❌ Failed to get workspace information.\n\nPlease ensure the CARL bot has the team:read OAuth scope.")
            return {"statusCode": 500, "body": str(e)}

    if subcommand == "start":
        # Check if already set up
        if setup.is_setup_complete(workspace_id):
            slack.post_message(
                channel_id,
                text="✅ CARL is already set up!\n\n"
                     "Use /carl settings` to view or update your configuration.\n"
                     "Use /carl setup reset` to run the setup wizard again."
            )
            return {"statusCode": 200, "body": ""}

        # Run connectivity validation
        slack.post_message(channel_id, text="🔍 Welcome to CARL Setup!\n\nValidating connectivity...")

        validation_results = setup.validate_connectivity()
        validation_text = setup.format_validation_results(validation_results)

        # Check if any services have critical errors (not warnings)
        has_errors = any(result.get("status") == "error" for result in validation_results.values())

        if has_errors:
            slack.post_message(
                channel_id,
                text=f"❌ Setup Validation Failed\n\n{validation_text}\n\n"
                     "Please fix the connectivity issues before proceeding with setup.\n"
                     "Contact your administrator if you need help."
            )
            return {"statusCode": 200, "body": ""}

        # Validation passed, show success and start wizard
        slack.post_message(
            channel_id,
            text=f"✅ Validation Complete!\n\n{validation_text}\n\n"
                 "Ready to configure CARL for your team!"
        )

        # Enable critical security services if not already enabled
        slack.post_message(
            channel_id,
            text="🔧 Enabling Critical Security Services\n\nChecking and enabling Security Hub and AWS Config..."
        )

        try:
            from services.security_services_enabler import SecurityServicesEnabler

            enabler = SecurityServicesEnabler()
            security_results = enabler.check_and_enable_all()

            # Format results
            sh_status = security_results["security_hub"]["status"]
            config_status = security_results["config"]["status"]

            security_text = "Security Services Status:\n\n"

            if sh_status == "already_enabled":
                security_text += "✅ *Security Hub:* Already enabled\n"
            elif sh_status == "enabled":
                security_text += "✅ *Security Hub:* Enabled successfully\n"
            else:
                error_msg = security_results['security_hub']['details'].get('error', 'Unknown error')
                security_text += f"⚠️ *Security Hub:* Failed - {error_msg}\n"

            if config_status == "already_enabled":
                security_text += "✅ *AWS Config:* Already enabled\n"
            elif config_status == "enabled":
                security_text += "✅ *AWS Config:* Enabled successfully (may take a few minutes to start recording)\n"
            else:
                error_msg = security_results['config']['details'].get('error', 'Unknown error')
                security_text += f"⚠️ *AWS Config:* Failed - {error_msg}\n"

            slack.post_message(channel_id, text=security_text)

        except Exception as e:
            logger.error(f"Failed to enable security services: {e}", exc_info=True)
            slack.post_message(
                channel_id,
                text=f"⚠️ Warning: Could not enable security services automatically.\n\n"
                     f"Error: {str(e)}\n\n"
                     f"You can enable them manually:\n"
                     f"• Security Hub: https://console.aws.amazon.com/securityhub/\n"
                     f"• AWS Config: https://console.aws.amazon.com/config/"
            )

        # Show setup modal if trigger_id available
        if trigger_id:
            return show_setup_modal(slack, trigger_id, channel_id, workspace_id, step=1)
        else:
            slack.post_message(
                channel_id,
                text="⚠️ Please run /carl setup start` again to open the configuration wizard."
            )
            return {"statusCode": 200, "body": ""}

    elif subcommand == "reset":
        # Allow re-running setup
        setup.update_workspace_config(workspace_id, {"setup_complete": False})
        slack.post_message(
            channel_id,
            text="✅ Setup has been reset. Run /carl setup start` to begin again."
        )
        return {"statusCode": 200, "body": ""}

    elif subcommand == "status":
        # Show current setup status
        config = setup.get_workspace_config(workspace_id)
        if not config:
            slack.post_message(
                channel_id,
                text="⚠️ CARL has not been set up yet. Run /carl setup start` to begin."
            )
        else:
            status_text = f"""*CARL Setup Status*

*Setup Complete:* {"✅ Yes" if config.get("setup_complete") else "❌ No"}
*Notification Channel:* {f"<#{config.get('notification_channel')}>" if config.get('notification_channel') else "Not set"}
*Scan Schedule:* {config.get('scan_schedule', 'Not set')}
*Scan Regions:* {', '.join(config.get('scan_regions', [])) or 'Not set'}
*Auto-scan on Deploy:* {"✅ Enabled" if config.get('auto_scan_on_deploy') else "❌ Disabled"}
*Compliance Frameworks:* {', '.join(config.get('compliance_frameworks', [])) or 'Not set'}

Run /carl settings` to update configuration."""
            slack.post_message(channel_id, text=status_text)
        return {"statusCode": 200, "body": ""}

    else:
        slack.post_message(
            channel_id,
            text="❌ Unknown setup command.\n\n"
                 "*Available commands:*\n"
                 "• /carl setup start` - Start setup wizard\n"
                 "• /carl setup status` - View setup status\n"
                 "• /carl setup reset` - Reset and re-run setup"
        )
        return {"statusCode": 200, "body": ""}


def handle_settings_command(
    slack: SlackService, channel_id: str, user_id: str, args: str, team_id: str = None
) -> dict:
    """Handle /carl settings command - view/update configuration."""
    from services.setup_service import SetupService

    setup = SetupService()

    # Get workspace ID from payload or fallback to API call
    workspace_id = team_id
    if not workspace_id:
        try:
            team_info = slack.client.team_info()
            workspace_id = team_info["team"]["id"]
        except Exception as e:
            logger.error(f"Failed to get workspace ID: {e}")
            slack.post_message(channel_id, text="❌ Failed to get workspace information.\n\nPlease ensure the CARL bot has the team:read OAuth scope.")
            return {"statusCode": 500, "body": str(e)}

    config = setup.get_workspace_config(workspace_id)

    if not config or not config.get("setup_complete"):
        slack.post_message(
            channel_id,
            text="⚠️ CARL has not been set up yet. Run /carl setup start` to begin."
        )
        return {"statusCode": 200, "body": ""}

    # Show current settings with buttons to update
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚙️ CARL Configuration"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Notification Channel:* <#{config.get('notification_channel')}>\n"
                        f"*Scan Schedule:* {config.get('scan_schedule', 'on_demand')}\n"
                        f"*Scan Regions:* {', '.join(config.get('scan_regions', ['us-east-1']))}\n"
                        f"*Auto-scan on Deploy:* {'✅ Enabled' if config.get('auto_scan_on_deploy', True) else '❌ Disabled'}\n"
                        f"*Compliance Frameworks:* {', '.join(config.get('compliance_frameworks', ['soc2']))}\n"
                        f"*Evidence Collection:* {'✅ Enabled' if config.get('evidence_collection', True) else '❌ Disabled'}\n"
                        f"*Evidence Retention:* {config.get('evidence_retention_years', 7)} years"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Need to update settings?*\nRun /carl setup start` to re-configure."
            }
        }
    ]

    slack.post_message(channel_id, blocks=blocks)
    return {"statusCode": 200, "body": ""}


def handle_foundation_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl foundation command - guided foundation building."""
    engine = get_decision_engine()
    parts = args.split() if args else []
    subcommand = parts[0].lower() if parts else "start"

    if subcommand == "start":
        # Check for existing session
        existing = engine.get_user_session(user_id, channel_id)
        if existing:
            slack.post_message(
                channel_id,
                text="You already have a foundation session in progress. Use /carl foundation status to continue or /carl foundation cancel to start over.",
            )
            return {"statusCode": 200, "body": ""}

        # NEW: First ask for framework selection
        from services.framework_loader import get_framework_loader
        loader = get_framework_loader()
        available_frameworks = loader.list_available_frameworks()

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "CARL Foundation Builder"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Welcome to the CARL Foundation Builder!\n\n"
                        "I'll help you build a compliant AWS foundation. "
                        "First, let's determine if you need compliance framework support."
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Do you need compliance framework support?*\n\nIf you select a framework, CARL will:\n"
                           "• Scan your AWS environment\n"
                           "• Identify compliance gaps\n"
                           "• Generate only what you need\n"
                           "• Include control mappings and audit evidence\n"
                           "• Ask fewer questions (5-6 vs 10)"
                },
            },
        ]

        # Framework selection buttons
        framework_elements = []

        # Add available frameworks
        for fw_id in available_frameworks:
            metadata = loader.get_framework_metadata(fw_id)
            framework_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": metadata.get('name', fw_id)[:75]},
                "value": fw_id,
                "action_id": f"foundation_select_framework_{fw_id}",
                "style": "primary" if fw_id == "soc2" else None
            })

        # Add "Best Practices" option (no framework)
        framework_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Best Practices Only"},
            "value": "none",
            "action_id": "foundation_select_framework_none",
        })

        blocks.append({
            "type": "actions",
            "elements": framework_elements[:5],  # Max 5 buttons per action block
        })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Tip: Select SOC 2 if selling to enterprises | Use Best Practices for general setup"}
            ],
        })

        slack.post_message(channel_id, blocks=blocks)
        return {"statusCode": 200, "body": ""}

    elif subcommand == "status":
        session = engine.get_user_session(user_id, channel_id)
        if not session:
            slack.post_message(
                channel_id,
                text="No active foundation session. Use /carl foundation start` to begin.",
            )
            return {"statusCode": 200, "body": ""}

        # Show current session status
        progress = f"{session.current_question_index}/{len(engine.get_all_patterns()) + 10}"
        collected = "\n".join([f"• {k}: {v}" for k, v in session.requirements.items()])

        slack.post_message(
            channel_id,
            text=f"Foundation Session Status\n\nProgress: {progress}\nState: {session.state.value}\n\nCollected Requirements:\n{collected or 'None yet'}",
        )
        return {"statusCode": 200, "body": ""}

    elif subcommand == "cancel":
        session = engine.get_user_session(user_id, channel_id)
        if session:
            del engine.sessions[session.session_id]
            slack.post_message(channel_id, text="Foundation session cancelled.")
        else:
            slack.post_message(channel_id, text="No active session to cancel.")
        return {"statusCode": 200, "body": ""}

    else:
        slack.post_message(
            channel_id,
            text="Unknown foundation command. Use start, status, or `cancel.",
        )
        return {"statusCode": 200, "body": ""}


def handle_account_factory_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl account-factory command - multi-account AFT setup."""
    from services.account_factory import get_account_factory_service

    service = get_account_factory_service()
    parts = args.split() if args else []
    subcommand = parts[0].lower() if parts else "start"

    if subcommand == "start":
        # Create new session
        session = service.create_session(user_id, channel_id)

        # Show framework selection
        from services.framework_loader import get_framework_loader
        loader = get_framework_loader()
        available_frameworks = loader.list_available_frameworks()

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "CARL Account Factory"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Welcome to the CARL Account Factory!\n\n"
                        "I'll help you set up a compliant multi-account AWS environment using "
                        "*AWS Account Factory for Terraform (AFT)*.\n\n"
                        "The compliance framework you choose will determine:\n"
                        "• Organizational structure (OUs)\n"
                        "• Accounts to create\n"
                        "• Service Control Policies (SCPs)\n"
                        "• Security services configuration\n"
                        "• VPC configuration per account"
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Select your compliance framework:*"
                },
            },
        ]

        # Framework selection buttons
        framework_elements = []
        for fw_id in available_frameworks:
            metadata = loader.get_framework_metadata(fw_id)
            framework_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": metadata.get('name', fw_id)[:75]},
                "value": fw_id,
                "action_id": f"account_factory_framework_{session.session_id}_{fw_id}",
                "style": "primary" if fw_id == "soc2" else None
            })

        blocks.append({
            "type": "actions",
            "elements": framework_elements[:5],
        })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Session ID: {session.session_id} | Tip: SOC 2 is recommended for enterprise B2B"}
            ],
        })

        slack.post_message(channel_id, blocks=blocks)
        return {"statusCode": 200, "body": ""}

    elif subcommand == "status":
        # Find user's session
        for session in service.sessions.values():
            if session.user_id == user_id and session.channel_id == channel_id:
                summary = service.get_summary(session)
                text = f"*Account Factory Status*\n\n"
                text += f"• State: {summary['state']}\n"
                text += f"• Framework: {summary['framework'] or 'Not selected'}\n"
                text += f"• Primary Region: {summary['primary_region'] or 'Not set'}\n"
                text += f"• Accounts: {len(summary['accounts'])}\n"

                if summary['accounts']:
                    text += "\n*Accounts:*\n"
                    for acc in summary['accounts']:
                        text += f"  - {acc['name']} ({acc['ou']}) - {acc['email']}\n"

                slack.post_message(channel_id, text=text)
                return {"statusCode": 200, "body": ""}

        slack.post_message(
            channel_id,
            text="No active Account Factory session. Use `/carl account-factory start` to begin.",
        )
        return {"statusCode": 200, "body": ""}

    elif subcommand == "cancel":
        for session_id, session in list(service.sessions.items()):
            if session.user_id == user_id and session.channel_id == channel_id:
                del service.sessions[session_id]
                slack.post_message(channel_id, text="Account Factory session cancelled.")
                return {"statusCode": 200, "body": ""}

        slack.post_message(channel_id, text="No active session to cancel.")
        return {"statusCode": 200, "body": ""}

    else:
        slack.post_message(
            channel_id,
            text="Unknown account-factory command. Use `start`, `status`, or `cancel`.",
        )
        return {"statusCode": 200, "body": ""}


def handle_account_factory_framework_selection(payload: dict, action: dict) -> dict:
    """Handle Account Factory framework selection."""
    from services.account_factory import get_account_factory_service

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    action_id = action.get("action_id", "")

    # Parse: account_factory_framework_{session_id}_{framework_id}
    parts = action_id.replace("account_factory_framework_", "").split("_", 1)
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    framework_id = parts[1]

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        slack.post_message(channel, text="Session expired. Please start again with `/carl account-factory start`")
        return {"statusCode": 200, "body": ""}

    # Select framework
    result = service.select_framework(session, framework_id)

    if not result["success"]:
        slack.post_message(channel, text=f"❌ Error: {result.get('error', 'Unknown error')}")
        return {"statusCode": 200, "body": ""}

    # Show organizational structure from framework
    org_text = f"✅ *{result['framework_name']}* framework selected!\n\n"
    org_text += "*Organizational Structure (from framework):*\n"
    for ou in result["org_structure"]:
        org_text += f"\n*{ou['ou_name']} OU* - {ou['purpose']}\n"
        for acc in ou["accounts"]:
            org_text += f"  • {acc['name']}: {acc['purpose']}\n"

    org_text += f"\n*Service Control Policies (SCPs):*\n"
    for scp in result["scps"]:
        org_text += f"  • {scp['name']}: {scp['description']}\n"

    org_text += f"\n*Total Accounts:* {result['total_accounts']} (including AFT management)"

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": org_text}
        },
        {"type": "divider"},
    ]

    # Now ask for AFT account email
    next_question = service.get_next_question(session)
    if next_question:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{next_question['question']}*\n_{next_question.get('description', '')}_"
            }
        })

        if next_question["type"] in ["aft_email", "account_email"]:
            # Text input - use button to trigger modal
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "👇 *Click the button below to enter the email address:*"}
            })
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📧 Enter Email Address"},
                    "action_id": f"account_factory_answer_{session_id}_{next_question['type']}",
                    "style": "primary"
                }]
            })
        elif next_question.get("options"):
            # Use buttons for selection
            elements = []
            for opt in next_question["options"]:
                elements.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": opt["label"][:75]},
                    "value": opt["value"],
                    "action_id": f"account_factory_answer_{session_id}_{next_question['type']}_{opt['value']}",
                })
            blocks.append({
                "type": "actions",
                "elements": elements[:5]
            })

    slack.post_message(channel, blocks=blocks)
    return {"statusCode": 200, "body": ""}


def handle_account_factory_answer(payload: dict, action: dict) -> dict:
    """Handle Account Factory answer buttons/inputs."""
    from services.account_factory import get_account_factory_service

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    trigger_id = payload.get("trigger_id", "")
    action_id = action.get("action_id", "")

    # Parse: account_factory_answer_{session_id}_{question_type}[_{value}]
    # session_id is 8 chars (UUID prefix, no underscores)
    # question_type may contain underscores (aft_email, account_email, primary_region)
    parts = action_id.replace("account_factory_answer_", "").split("_")
    session_id = parts[0]
    rest = "_".join(parts[1:]) if len(parts) > 1 else ""

    # Known question types that may have underscores
    known_question_types = ["aft_email", "account_email", "primary_region", "vpc_config", "framework_select"]
    question_type = ""
    value = action.get("value", "")  # Prefer value from button itself

    for qt in known_question_types:
        if rest == qt:
            question_type = qt
            break
        elif rest.startswith(qt + "_"):
            question_type = qt
            # Extract value from rest if not already set
            if not value:
                value = rest[len(qt) + 1:]
            break

    # Fallback: if no known type matched, use first part as question_type
    if not question_type and len(parts) > 1:
        question_type = parts[1]
        if not value:
            value = "_".join(parts[2:]) if len(parts) > 2 else ""

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        slack.post_message(channel, text="Session expired. Please start again.")
        return {"statusCode": 200, "body": ""}

    # Handle email inputs via modal
    if question_type in ["aft_email", "account_email"] and not value:
        # Open modal for email input
        _show_account_factory_email_modal(slack, trigger_id, session_id, question_type)
        return {"statusCode": 200, "body": ""}

    # Handle region selection
    if question_type == "primary_region" and value:
        service.set_primary_region(session, value)
        slack.post_message(channel, text=f"✓ Primary region set to *{value}*")

    # Continue with next question
    next_question = service.get_next_question(session)
    if next_question:
        _show_account_factory_next_question(slack, channel, session_id, next_question)
    else:
        # All questions answered - show summary and accept button
        _show_account_factory_summary(slack, channel, session, session_id)

    return {"statusCode": 200, "body": ""}


def _show_account_factory_email_modal(slack: SlackService, trigger_id: str, session_id: str, question_type: str):
    """Show modal for email input."""
    title = "AFT Account Email" if question_type == "aft_email" else "Account Email"

    modal = {
        "type": "modal",
        "callback_id": f"account_factory_email_{session_id}_{question_type}",
        "title": {"type": "plain_text", "text": title[:24]},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "email_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "email_input",
                    "placeholder": {"type": "plain_text", "text": "email@example.com"}
                },
                "label": {"type": "plain_text", "text": "Email Address"},
                "hint": {"type": "plain_text", "text": "Must be a unique email not already used by an AWS account"}
            }
        ]
    }

    try:
        slack.client.views_open(trigger_id=trigger_id, view=modal)
    except Exception as e:
        logger.error(f"Failed to open email modal: {e}")


def _show_account_factory_next_question(slack: SlackService, channel: str, session_id: str, question: dict):
    """Show the next question in the Account Factory wizard."""
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{question['question']}*\n_{question.get('description', '')}_"
            }
        }
    ]

    if question["type"] == "all_account_emails":
        # Show all accounts needing emails with a button to open multi-email modal
        accounts = question.get("accounts", [])
        account_list = "\n".join([
            f"• *{acc['name']}* - {acc['purpose']} (OU: {acc['ou_name']})"
            for acc in accounts
        ])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Accounts needing email addresses:*\n{account_list}"}
        })
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "👇 *Click the button below to enter email addresses for all accounts:*"}
        })
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "📧 Configure Account Emails"},
                "action_id": f"account_factory_all_emails_{session_id}",
                "style": "primary"
            }]
        })
    elif question["type"] in ["aft_email", "account_email"]:
        # Text input - use button to trigger modal with clear instructions
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "👇 *Click the button below to enter the email address:*"}
        })
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "📧 Enter Email Address"},
                "action_id": f"account_factory_answer_{session_id}_{question['type']}",
                "style": "primary"
            }]
        })
    elif question["type"] == "vpc_config":
        # VPC configuration - show button to open VPC modal
        account_name = question.get("account_name", "")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "👇 *Click the button below to configure the VPC:*"}
        })
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "🌐 Configure VPC"},
                "action_id": f"account_factory_vpc_config_{session_id}_{account_name}",
                "style": "primary"
            }]
        })
    elif question.get("options"):
        elements = []
        for opt in question["options"]:
            elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": opt["label"][:75]},
                "value": opt["value"],
                "action_id": f"account_factory_answer_{session_id}_{question['type']}_{opt['value']}",
            })
        blocks.append({
            "type": "actions",
            "elements": elements[:5]
        })

    slack.post_message(channel, blocks=blocks)


def handle_account_factory_all_emails_button(payload: dict, action: dict) -> dict:
    """Handle button click to open multi-account email modal."""
    from services.account_factory import get_account_factory_service

    trigger_id = payload.get("trigger_id", "")
    action_id = action.get("action_id", "")
    session_id = action_id.replace("account_factory_all_emails_", "")

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        channel = payload.get("channel", {}).get("id", "")
        slack.post_message(channel, text="Session expired. Please start again with `/carl account-factory start`")
        return {"statusCode": 200, "body": ""}

    # Get accounts needing emails
    accounts_needing_emails = [
        {"name": acc.name, "purpose": acc.purpose, "ou_name": acc.ou_name}
        for acc in session.accounts
        if not acc.email and acc.name != "aft-management"
    ]

    _show_account_factory_all_emails_modal(slack, trigger_id, session_id, accounts_needing_emails)
    return {"statusCode": 200, "body": ""}


def _show_account_factory_all_emails_modal(slack: SlackService, trigger_id: str, session_id: str, accounts: list):
    """Show modal for entering all account emails at once."""
    logger = get_logger(__name__)

    # Build input blocks for each account (max 10 inputs in a modal)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Configure email addresses for your AWS accounts*\n_Each account needs a unique email not already associated with an AWS account._"
            }
        },
        {"type": "divider"}
    ]

    for acc in accounts[:10]:  # Slack modal limit
        blocks.append({
            "type": "input",
            "block_id": f"email_{acc['name']}",
            "element": {
                "type": "plain_text_input",
                "action_id": "email_input",
                "placeholder": {"type": "plain_text", "text": f"{acc['name']}@yourcompany.com"}
            },
            "label": {"type": "plain_text", "text": f"{acc['name']}"},
            "hint": {"type": "plain_text", "text": f"{acc['purpose']} (OU: {acc['ou_name']})"}
        })

    modal = {
        "type": "modal",
        "callback_id": f"account_factory_all_emails_submit_{session_id}",
        "title": {"type": "plain_text", "text": "Account Emails"},
        "submit": {"type": "plain_text", "text": "Save All"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks
    }

    try:
        slack.client.views_open(trigger_id=trigger_id, view=modal)
    except Exception as e:
        logger.error(f"Failed to open all emails modal: {e}")


def handle_account_factory_all_emails_submission(payload: dict) -> dict:
    """Handle submission of all account emails modal."""
    from services.account_factory import get_account_factory_service

    logger = get_logger(__name__)
    callback_id = payload.get("view", {}).get("callback_id", "")
    session_id = callback_id.replace("account_factory_all_emails_submit_", "")

    values = payload.get("view", {}).get("state", {}).get("values", {})

    # Extract emails from each input block
    emails = {}
    for block_id, block_data in values.items():
        if block_id.startswith("email_"):
            account_name = block_id.replace("email_", "")
            email = block_data.get("email_input", {}).get("value", "")
            if email:
                emails[account_name] = email

    logger.info(f"All emails submission - session_id: {session_id}, emails: {list(emails.keys())}")

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        logger.error(f"All emails submission - session not found: {session_id}")
        return {"statusCode": 200, "body": ""}

    channel = session.channel_id

    # Set all emails at once
    result = service.set_account_emails(session, emails)
    logger.info(f"All emails submission - set result: {result}")

    # Confirmation message
    email_summary = "\n".join([f"• *{name}*: {email}" for name, email in emails.items()])
    slack.post_message(channel, text=f"✓ Account emails configured:\n{email_summary}")

    # Continue with next question
    next_question = service.get_next_question(session)
    if next_question:
        _show_account_factory_next_question(slack, channel, session_id, next_question)
    else:
        _show_account_factory_summary(slack, channel, session, session_id)

    return {"statusCode": 200, "body": ""}


def _show_account_factory_summary(slack: SlackService, channel: str, session, session_id: str):
    """Show summary and generate button."""
    from services.account_factory import get_account_factory_service

    service = get_account_factory_service()
    summary = service.get_summary(session)

    text = f"*Account Factory Configuration Complete!*\n\n"
    text += f"• Framework: {summary['framework']}\n"
    text += f"• Primary Region: {summary['primary_region']}\n"
    text += f"• Accounts: {len(summary['accounts'])}\n\n"

    text += "*Accounts to Create:*\n"
    for acc in summary["accounts"]:
        text += f"  • *{acc['name']}* ({acc['ou']}) - {acc['email']}\n"

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text}
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✓ Generate AFT & Push to GitHub"},
                    "action_id": f"account_factory_accept_{session_id}",
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "action_id": f"account_factory_cancel_{session_id}",
                }
            ]
        }
    ]

    slack.post_message(channel, blocks=blocks)


def handle_account_factory_email_submission(payload: dict) -> dict:
    """Handle email modal submission."""
    from services.account_factory import get_account_factory_service

    logger = get_logger(__name__)
    callback_id = payload.get("view", {}).get("callback_id", "")
    logger.info(f"Email submission - callback_id: {callback_id}")

    # Parse: account_factory_email_{session_id}_{question_type}
    parts = callback_id.replace("account_factory_email_", "").split("_")
    session_id = parts[0]
    question_type = "_".join(parts[1:])
    logger.info(f"Email submission - session_id: {session_id}, question_type: {question_type}")

    values = payload.get("view", {}).get("state", {}).get("values", {})
    email = values.get("email_block", {}).get("email_input", {}).get("value", "")
    logger.info(f"Email submission - email: {email}")

    # Channel will be retrieved from session below, but try to get from payload first
    response_urls = payload.get("response_urls", [])
    channel = payload.get("view", {}).get("private_metadata", "") or (response_urls[0].get("channel_id", "") if response_urls else "")

    # Try to get channel from user's recent message
    user_id = payload.get("user", {}).get("id", "")

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        logger.error(f"Email submission - session not found: {session_id}")
        return {"statusCode": 200, "body": ""}

    logger.info(f"Email submission - before set: session.aft_account_email={session.aft_account_email}")
    channel = session.channel_id

    # Set the email
    if question_type == "aft_email":
        service.set_aft_account_email(session, email)
        logger.info(f"Email submission - after set: session.aft_account_email={session.aft_account_email}")
        slack.post_message(channel, text=f"✓ AFT account email set to *{email}*")
    elif question_type.startswith("account_email"):
        # For specific account emails, need account name
        pass

    # Continue with next question
    next_question = service.get_next_question(session)
    logger.info(f"Email submission - next_question type: {next_question.get('type') if next_question else 'None'}")
    if next_question:
        _show_account_factory_next_question(slack, channel, session_id, next_question)
    else:
        _show_account_factory_summary(slack, channel, session, session_id)

    return {"statusCode": 200, "body": ""}


def handle_account_factory_accept(payload: dict, action: dict) -> dict:
    """Handle Account Factory accept - generate AFT Terraform and push to GitHub."""
    import json
    import os
    import boto3
    from services.account_factory import get_account_factory_service

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    action_id = action.get("action_id", "")

    session_id = action_id.replace("account_factory_accept_", "")

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        slack.post_message(channel, text="Session expired.")
        return {"statusCode": 200, "body": ""}

    # Post acknowledgement
    slack.post_message(channel, text="🔄 Starting AFT Terraform generation...")

    # Invoke async generation
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',
            Payload=json.dumps({
                'action': 'process_account_factory_generate',
                'channel_id': channel,
                'user_id': user,
                'session_id': session_id
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async account factory generation: {e}")
        slack.post_message(channel, text=f"❌ Failed to start generation: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_account_factory_vpc_config_button(payload: dict, action: dict) -> dict:
    """Handle button click to open VPC config modal for Account Factory."""
    from services.account_factory import get_account_factory_service

    trigger_id = payload.get("trigger_id", "")
    action_id = action.get("action_id", "")

    # Parse: account_factory_vpc_config_{session_id}_{account_name}
    parts = action_id.replace("account_factory_vpc_config_", "").split("_", 1)
    session_id = parts[0]
    account_name = parts[1] if len(parts) > 1 else ""

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        channel = payload.get("channel", {}).get("id", "")
        slack.post_message(channel, text="Session expired. Please start again with `/carl account-factory start`")
        return {"statusCode": 200, "body": ""}

    _show_account_factory_vpc_modal(slack, trigger_id, session_id, account_name)
    return {"statusCode": 200, "body": ""}


def _show_account_factory_vpc_modal(slack: SlackService, trigger_id: str, session_id: str, account_name: str):
    """Show VPC configuration modal for Account Factory."""
    logger = get_logger(__name__)

    modal = {
        "type": "modal",
        "callback_id": f"account_factory_vpc_{session_id}_{account_name}",
        "title": {"type": "plain_text", "text": f"VPC for {account_name}"[:24]},
        "submit": {"type": "plain_text", "text": "Save VPC"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Configure VPC for {account_name}*"}
            },
            {
                "type": "input",
                "block_id": "vpc_name",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input",
                    "placeholder": {"type": "plain_text", "text": "main-vpc"}
                },
                "label": {"type": "plain_text", "text": "VPC Name"},
                "hint": {"type": "plain_text", "text": "A descriptive name for this VPC"}
            },
            {
                "type": "input",
                "block_id": "vpc_cidr",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input",
                    "placeholder": {"type": "plain_text", "text": "10.0.0.0/16"}
                },
                "label": {"type": "plain_text", "text": "CIDR Block"},
                "hint": {"type": "plain_text", "text": "e.g., 10.0.0.0/16 for dev, 10.1.0.0/16 for staging, 10.2.0.0/16 for prod"}
            },
            {
                "type": "input",
                "block_id": "az_count",
                "element": {
                    "type": "static_select",
                    "action_id": "select",
                    "placeholder": {"type": "plain_text", "text": "Select AZ count"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "2 AZs"}, "value": "2"},
                        {"text": {"type": "plain_text", "text": "3 AZs"}, "value": "3"},
                    ],
                    "initial_option": {"text": {"type": "plain_text", "text": "2 AZs"}, "value": "2"}
                },
                "label": {"type": "plain_text", "text": "Availability Zones"}
            },
            {
                "type": "input",
                "block_id": "nat_gateway",
                "element": {
                    "type": "static_select",
                    "action_id": "select",
                    "placeholder": {"type": "plain_text", "text": "NAT Gateway"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Yes (required for private subnets)"}, "value": "true"},
                        {"text": {"type": "plain_text", "text": "No"}, "value": "false"},
                    ],
                    "initial_option": {"text": {"type": "plain_text", "text": "Yes (required for private subnets)"}, "value": "true"}
                },
                "label": {"type": "plain_text", "text": "Enable NAT Gateway?"}
            },
            {
                "type": "input",
                "block_id": "vpc_endpoints",
                "element": {
                    "type": "static_select",
                    "action_id": "select",
                    "placeholder": {"type": "plain_text", "text": "VPC Endpoints"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Yes (S3, DynamoDB, SSM)"}, "value": "true"},
                        {"text": {"type": "plain_text", "text": "No"}, "value": "false"},
                    ],
                    "initial_option": {"text": {"type": "plain_text", "text": "Yes (S3, DynamoDB, SSM)"}, "value": "true"}
                },
                "label": {"type": "plain_text", "text": "Enable VPC Endpoints?"}
            },
            {
                "type": "input",
                "block_id": "transit_gateway",
                "element": {
                    "type": "static_select",
                    "action_id": "select",
                    "placeholder": {"type": "plain_text", "text": "Transit Gateway"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Yes - Attach to TGW (SOC2 recommended)"}, "value": "true"},
                        {"text": {"type": "plain_text", "text": "No - Isolated VPC"}, "value": "false"},
                    ],
                    "initial_option": {"text": {"type": "plain_text", "text": "Yes - Attach to TGW (SOC2 recommended)"}, "value": "true"}
                },
                "label": {"type": "plain_text", "text": "Attach to Transit Gateway?"},
                "hint": {"type": "plain_text", "text": "Requires Network account with TGW. Enables centralized egress/inspection."}
            }
        ]
    }

    try:
        slack.client.views_open(trigger_id=trigger_id, view=modal)
    except Exception as e:
        logger.error(f"Failed to open VPC config modal: {e}")


def handle_account_factory_vpc_submission(payload: dict) -> dict:
    """Handle VPC configuration modal submission for Account Factory."""
    from services.account_factory import get_account_factory_service
    from services.account_factory.account_factory_service import VPCConfig

    logger = get_logger(__name__)
    callback_id = payload.get("view", {}).get("callback_id", "")

    # Parse: account_factory_vpc_{session_id}_{account_name}
    parts = callback_id.replace("account_factory_vpc_", "").split("_", 1)
    session_id = parts[0]
    account_name = parts[1] if len(parts) > 1 else ""

    values = payload.get("view", {}).get("state", {}).get("values", {})

    vpc_name = values.get("vpc_name", {}).get("input", {}).get("value", "main-vpc")
    vpc_cidr = values.get("vpc_cidr", {}).get("input", {}).get("value", "10.0.0.0/16")
    az_count = int(values.get("az_count", {}).get("select", {}).get("selected_option", {}).get("value", "2"))
    nat_gateway = values.get("nat_gateway", {}).get("select", {}).get("selected_option", {}).get("value", "true") == "true"
    vpc_endpoints = values.get("vpc_endpoints", {}).get("select", {}).get("selected_option", {}).get("value", "true") == "true"
    transit_gateway = values.get("transit_gateway", {}).get("select", {}).get("selected_option", {}).get("value", "true") == "true"

    logger.info(f"VPC submission - session: {session_id}, account: {account_name}, cidr: {vpc_cidr}, tgw: {transit_gateway}")

    service = get_account_factory_service()
    session = service.get_session(session_id)
    slack = get_slack_service()

    if not session:
        logger.error(f"VPC submission - session not found: {session_id}")
        return {"statusCode": 200, "body": ""}

    channel = session.channel_id

    # Create VPC config and add to account
    vpc_config = VPCConfig(
        name=vpc_name,
        cidr=vpc_cidr,
        environment=account_name,
        availability_zones=az_count,
        enable_nat_gateway=nat_gateway,
        enable_vpc_endpoints=vpc_endpoints,
        attach_transit_gateway=transit_gateway,
    )

    result = service.add_vpc_to_account(session, account_name, vpc_config)

    if result.get("success"):
        tgw_status = " + TGW attachment" if transit_gateway else " (isolated)"
        slack.post_message(channel, text=f"✓ VPC *{vpc_name}* configured for *{account_name}* ({vpc_cidr}{tgw_status})")

        # Notify if Network account was auto-added for TGW
        if result.get("network_account_added"):
            slack.post_message(
                channel,
                text="📡 *Network account added* - Transit Gateway requires a dedicated Network account in Shared Services OU. "
                     "This account will host the TGW for centralized egress and inspection (SOC2 best practice)."
            )
    else:
        slack.post_message(channel, text=f"❌ Failed to configure VPC: {result.get('error')}")
        return {"statusCode": 200, "body": ""}

    # Continue with next question
    next_question = service.get_next_question(session)
    if next_question:
        _show_account_factory_next_question(slack, channel, session_id, next_question)
    else:
        _show_account_factory_summary(slack, channel, session, session_id)

    return {"statusCode": 200, "body": ""}


def handle_patterns_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl patterns command - view architecture patterns with pros/cons."""
    from knowledge.architecture_patterns import get_pattern_by_category, get_all_patterns
    from knowledge.vpc_patterns import get_vpc_patterns
    from knowledge.identity_patterns import get_identity_patterns
    from knowledge.security_tooling_patterns import get_security_tooling_patterns
    from knowledge.etl_patterns import PATTERNS as ETL_PATTERNS
    from knowledge.serverless_patterns import PATTERNS as SERVERLESS_PATTERNS
    from knowledge.container_patterns import PATTERNS as CONTAINER_PATTERNS
    from knowledge.cicd_patterns import PATTERNS as CICD_PATTERNS

    category = args.strip().lower() if args else ""

    if not category:
        # List all pattern categories with better formatting
        # Combine all patterns from all modules
        patterns = {}

        # Networking patterns
        patterns.update(get_all_patterns())

        # VPC patterns
        vpc_patterns = get_vpc_patterns()
        for key, pattern in vpc_patterns.items():
            patterns[f"vpc_{key}"] = pattern

        # Identity patterns
        identity_patterns = get_identity_patterns()
        for key, pattern in identity_patterns.items():
            patterns[f"identity_{key}"] = pattern

        # Security patterns
        security_patterns = get_security_tooling_patterns()
        for key, pattern in security_patterns.items():
            patterns[f"security_{key}"] = pattern

        # ETL patterns
        for i, pattern in enumerate(ETL_PATTERNS):
            patterns[f"etl_{i}"] = pattern

        # Serverless patterns
        for i, pattern in enumerate(SERVERLESS_PATTERNS):
            patterns[f"serverless_{i}"] = pattern

        # Container patterns
        for i, pattern in enumerate(CONTAINER_PATTERNS):
            patterns[f"container_{i}"] = pattern

        # CI/CD patterns
        for i, pattern in enumerate(CICD_PATTERNS):
            patterns[f"cicd_{i}"] = pattern

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📚 Architecture Pattern Library"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Proven AWS architecture patterns with trade-offs, costs, and SOC 2 mappings_"
                }
            },
            {"type": "divider"}
        ]

        # Group patterns by theme
        networking_patterns = []
        security_patterns = []
        compute_patterns = []
        data_patterns = []
        cicd_patterns_list = []

        for cat, p in patterns.items():
            # Determine category and emoji based on pattern type
            if cat in ["egress", "ingress", "transit", "dns", "inspection"] or cat.startswith("vpc_"):
                emoji = "🌐"
                pattern_line = f"{emoji} *{p.question.split('?')[0]}?*"
                networking_patterns.append(pattern_line)
            elif cat in ["landing_zone", "client_vpn", "site_to_site_vpn"] or cat.startswith("security_") or cat.startswith("identity_"):
                emoji = "🔒"
                pattern_line = f"{emoji} *{p.question.split('?')[0]}?*"
                security_patterns.append(pattern_line)
            elif cat.startswith("serverless_") or cat.startswith("container_"):
                emoji = "⚡" if cat.startswith("serverless_") else "📦"
                pattern_line = f"{emoji} *{p.question.split('?')[0]}?*"
                compute_patterns.append(pattern_line)
            elif cat.startswith("etl_"):
                emoji = "🔄"
                pattern_line = f"{emoji} *{p.question.split('?')[0]}?*"
                data_patterns.append(pattern_line)
            elif cat.startswith("cicd_"):
                emoji = "🚀"
                pattern_line = f"{emoji} *{p.question.split('?')[0]}?*"
                cicd_patterns_list.append(pattern_line)

        if networking_patterns:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🌐 Networking Patterns:*\n" + "\n".join(networking_patterns)
                }
            })
            blocks.append({"type": "divider"})

        if security_patterns:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🔒 Security & Identity Patterns:*\n" + "\n".join(security_patterns)
                }
            })
            blocks.append({"type": "divider"})

        if compute_patterns:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*⚡ Compute Patterns (Serverless & Containers):*\n" + "\n".join(compute_patterns)
                }
            })
            blocks.append({"type": "divider"})

        if data_patterns:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🔄 Data Processing Patterns (ETL):*\n" + "\n".join(data_patterns)
                }
            })
            blocks.append({"type": "divider"})

        if cicd_patterns_list:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🚀 CI/CD Patterns:*\n" + "\n".join(cicd_patterns_list)
                }
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"💡 Showing {len(patterns)} architecture patterns | Use /carl recommend <requirement>` for personalized recommendations"
            }]
        })

        slack.post_message(channel_id, blocks=blocks)
        return {"statusCode": 200, "body": ""}

    pattern = get_pattern_by_category(category)
    if not pattern:
        slack.post_message(
            channel_id,
            text=f"Unknown category: {category}. Use /carl patterns` to see available categories.",
        )
        return {"statusCode": 200, "body": ""}

    # Build detailed pattern view
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📚 {category.replace('_', ' ').title()} Patterns"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Decision:* _{pattern.question}_"},
        },
        {"type": "divider"},
    ]

    for i, opt in enumerate(pattern.options, 1):
        # Option header with cost
        cost_range = f"${opt.monthly_cost_range[0]:.0f}-${opt.monthly_cost_range[1]:.0f}/mo"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Option {i}: {opt.name}*  💰 _{cost_range}_\n"
                    f"{opt.description}"
                ),
            },
        })

        # Pros and Cons (show top 3, indicate more)
        pros_list = opt.pros[:3]
        cons_list = opt.cons[:3]

        pros_text = "\n".join([f"✅ {p}" for p in pros_list])
        if len(opt.pros) > 3:
            pros_text += f"\n_+{len(opt.pros) - 3} more..._"

        cons_text = "\n".join([f"⚠️ {c}" for c in cons_list])
        if len(opt.cons) > 3:
            cons_text += f"\n_+{len(opt.cons) - 3} more..._"

        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": pros_text},
                {"type": "mrkdwn", "text": cons_text},
            ],
        })

        # When to use (compact, top 2)
        when_list = opt.when_to_use[:2]
        when_text = " • ".join(when_list)
        if len(opt.when_to_use) > 2:
            when_text += f" _(+{len(opt.when_to_use) - 2} more)_"

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"*Best for:* {when_text}"},
            ],
        })

        # Metadata row (SOC 2, complexity, operations)
        complexity_emoji = "🟢" if opt.implementation_complexity == "Low" else "🟡" if opt.implementation_complexity == "Medium" else "🔴"
        ops_emoji = "🟢" if opt.operational_overhead == "Low" else "🟡" if opt.operational_overhead == "Medium" else "🔴"

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🔒 SOC 2: {', '.join(opt.soc2_controls[:4])} | {complexity_emoji} Setup: {opt.implementation_complexity} | {ops_emoji} Ops: {opt.operational_overhead}",
                },
            ],
        })

        blocks.append({"type": "divider"})

    # Decision logic (truncated for readability)
    logic_preview = pattern.recommendation_logic.strip()[:800]
    if len(pattern.recommendation_logic) > 800:
        logic_preview += "...\n_(truncated - ask CARL for full guidance)_"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*💡 Decision Framework:*\n```{logic_preview}``",
        },
    })

    # Common mistakes (top 3)
    mistakes_list = pattern.common_mistakes[:3]
    mistakes_text = "\n".join([f"🚨 {m}" for m in mistakes_list])
    if len(pattern.common_mistakes) > 3:
        mistakes_text += f"\n_+{len(pattern.common_mistakes) - 3} more mistakes to avoid..._"

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Common Mistakes to Avoid:*\n{mistakes_text}",
        },
    })

    slack.post_message(channel_id, blocks=blocks)
    return {"statusCode": 200, "body": ""}


def handle_recommend_command(
    slack: SlackService, channel_id: str, user_id: str, requirement: str
) -> dict:
    """Handle /carl recommend command - get architecture recommendations."""
    if not requirement:
        slack.post_message(
            channel_id,
            text="Please describe what you need. Example: /carl recommend I need a compliant VPC with WAF",
        )
        return {"statusCode": 200, "body": ""}

    # Post "Analyzing..." message
    slack.post_message(channel_id, text=f"🔍 Analyzing architecture options for: {requirement}...")

    # Invoke async processing in background
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'action': 'process_recommend_async',
                'channel_id': channel_id,
                'user_id': user_id,
                'requirement': requirement
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async processing: {e}")
        # Fallback to synchronous if async fails
        return handle_recommend_command_sync(slack, channel_id, user_id, requirement)

    # Return empty 200 OK immediately to Slack (prevents timeout)
    return {"statusCode": 200, "body": ""}


def handle_recommend_command_sync(
    slack: SlackService, channel_id: str, user_id: str, requirement: str
) -> dict:
    """
    Synchronous version of recommend command - uses AgentCore Architect agent.

    Tries AgentCore first for architecture recommendations, falls back to local agent if unavailable.
    """
    import time
    import uuid
    from services.learning_service import LearningService

    logger.info(f"Processing /carl recommend: {requirement[:100]}...")

    # Track timing
    start_time = time.time()
    tools_used = []
    components_mentioned = []
    session_id = str(uuid.uuid4())

    try:
        # Try AgentCore Architect first
        agentcore_arn = os.environ.get("AGENTCORE_ARCHITECT_RUNTIME_ARN", "")
        response = None

        if agentcore_arn:
            logger.info(f"Using AgentCore Architect for /carl recommend: {agentcore_arn}")
            slack.post_message(channel_id, text="🏗️ Analyzing your architecture requirement with CARL Architect...")

            result = invoke_agentcore_architect(requirement, session_id)

            if result["success"]:
                response = result["response"]
                tools_used.append("agentcore_architect")
                logger.info(f"AgentCore Architect response: {len(response)} chars")
            else:
                logger.warning(f"AgentCore Architect failed: {result.get('error')}, falling back to local agent")
                slack.post_message(channel_id, text="⚠️ AgentCore Architect unavailable, using local agent...")

        # Fallback to local agent if AgentCore not configured or failed
        if not response:
            logger.info("Using local architecture agent fallback")
            response = _handle_recommend_with_local_agent(slack, channel_id, user_id, requirement)
            tools_used.append("local_architecture_agent")

        # Intelligently condense if response is too verbose
        if is_response_too_verbose(response):
            response = condense_response(response)

        # Extract components mentioned (for learning)
        if "ec2" in response.lower():
            components_mentioned.append("ec2")
        if "rds" in response.lower():
            components_mentioned.append("rds")
        if "lambda" in response.lower():
            components_mentioned.append("lambda")
        if "s3" in response.lower():
            components_mentioned.append("s3")
        if "dynamodb" in response.lower():
            components_mentioned.append("dynamodb")
        if "vpc" in response.lower():
            components_mentioned.append("vpc")

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Initialize learning service
        scan_history_table = os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history")
        resource_graph_table = os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")
        learning_service = LearningService(
            scan_history_table=scan_history_table,
            resource_graph_table=resource_graph_table
        )

        # Log interaction for learning
        interaction_id = learning_service.log_interaction(
            question=requirement,
            scans_performed=tools_used,
            resources_found=components_mentioned,
            response_length=len(response),
            duration_ms=duration_ms
        )

        # Format and post response
        formatted_blocks = format_markdown_to_blocks(response, "🏗️ Architecture Recommendation")
        for block_group in formatted_blocks:
            slack.post_message(channel_id, blocks=block_group)

        # Add feedback buttons
        feedback_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Was this recommendation helpful?_"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👍 Helpful"},
                        "style": "primary",
                        "action_id": f"feedback_helpful_{interaction_id}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👎 Not Helpful"},
                        "action_id": f"feedback_not_helpful_{interaction_id}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🔨 Build This"},
                        "style": "primary",
                        "action_id": f"build_architecture_{requirement[:50].replace(' ', '_')}"
                    }
                ]
            }
        ]
        slack.post_message(channel_id, blocks=feedback_blocks)

        return {"statusCode": 200, "body": ""}

    except Exception as e:
        logger.error(f"Error in recommend command: {e}", exc_info=True)
        slack.post_message(
            channel_id,
            text=f"❌ Error processing recommendation: {str(e)}"
        )
        return {"statusCode": 200, "body": ""}


def _handle_recommend_with_local_agent(
    slack: SlackService, channel_id: str, user_id: str, requirement: str
) -> str:
    """
    Fallback: Use local architecture agent for recommendations.

    Returns the response text.
    """
    from services.agent_core import Agent
    from services.architecture_tools import create_architecture_tools
    from services.learning_service import LearningService

    try:
        # Scan AWS environment for context-aware recommendations
        from services.aws_environment_scanner import AWSEnvironmentScanner

        scanner = AWSEnvironmentScanner()
        scan_result = scanner.scan()
        environment_summary = scan_result.to_context_summary()

        # Initialize learning service
        scan_history_table = os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history")
        resource_graph_table = os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")

        learning_service = LearningService(
            scan_history_table=scan_history_table,
            resource_graph_table=resource_graph_table
        )

        # Get learned context for architecture recommendations
        learned_context = learning_service.get_learned_context(requirement, interaction_type="architecture")

        # Combine AWS scan with learned context
        if learned_context:
            learned_context = f"\n\nCURRENT AWS ENVIRONMENT:\n{environment_summary}\n\n{learned_context}"
        else:
            learned_context = f"\n\nCURRENT AWS ENVIRONMENT:\n{environment_summary}"

        # Create architecture tools
        architecture_tools = create_architecture_tools()

        # Build agent instructions
        base_instructions = """You are CARL's architecture advisor.

Your job: Provide AWS architecture recommendations that are secure, cost-effective, and compliant.

Available tools:
- get_architecture_patterns: Get proven architecture patterns by category
- get_aws_pricing: Get real-time AWS pricing (ALWAYS use this for accurate costs)
- estimate_architecture_cost: Estimate total monthly cost for a solution
- get_compliance_requirements: Get SOC 2 compliance requirements for patterns
- compare_architecture_options: Compare two options across criteria

Guidelines:
1. ALWAYS show 2-3 OPTIONS with tradeoffs - let user choose
2. ALWAYS include cost information - use get_aws_pricing for accuracy
3. Explain key tradeoffs clearly (cost vs complexity, scalability vs simplicity)
4. Consider SOC 2 compliance requirements
5. Recommend best VALUE (not always cheapest - factor in operational overhead)
6. Be thorough - include relevant details about architecture, networking, compliance

Response Format (use plain text, NO markdown asterisks):

OPTION 1: Service Name
RECOMMENDED (if applicable)
Best for: One sentence
Cost: $X-Y/month
Key points:
- List key components and how they work
- Include compliance considerations if relevant
- Mention networking requirements if needed
- Note key tradeoffs

OPTION 2: Service Name
Best for: One sentence
Cost: $X-Y/month
Key points:
- List key components
- Tradeoffs and considerations

My Recommendation: State preferred option with reasoning.

IMPORTANT FORMATTING RULES:
- Do NOT use markdown asterisks (**) - use plain text, the system will format it
- Do NOT use tildes (~) for "approximately" - Slack renders them as strikethrough. Write "about" or "approximately" instead
- Do NOT use pound signs (#) for headers - they don't render in Slack
"""

        # Add learned context if available
        if learned_context:
            base_instructions += learned_context

        # Create architecture agent (no progress callback for fallback - AgentCore handles progress)
        architecture_agent = Agent(
            tools=architecture_tools,
            instructions=base_instructions
        )

        # Execute agent
        logger.info("🏗️ Local architecture agent analyzing requirement")
        response = architecture_agent.execute(
            f"Provide architecture recommendation for: {requirement}"
        )

        logger.info(f"Local architecture agent response: {response[:500]}...")
        return response

    except Exception as e:
        logger.error(f"Local architecture agent failed: {e}", exc_info=True)
        return f"Error generating architecture recommendation: {str(e)}"


def handle_build_command(
    slack: SlackService, channel_id: str, user_id: str, blueprint_name: str, config: dict = None, trigger_id: str = None
) -> dict:
    """
    Handle /carl build command - generate and upload to GitHub.

    NEW: Uses intelligent parameter detection instead of hardcoded pattern matching.
    """
    if not blueprint_name:
        return handle_blueprints_command(slack, channel_id, user_id)

    # Use intelligent parameter detection (replaces hardcoded "vpc" and "s3" checks)
    from services.blueprint_parameter_detector import BlueprintParameterDetector

    detector = BlueprintParameterDetector()
    required_params = detector.get_required_parameters(blueprint_name)

    # If no config provided and parameters are required, ask for them
    if config is None and required_params and trigger_id:
        logger.info(f"Blueprint {blueprint_name} requires {len(required_params)} parameters")
        return show_blueprint_config_modal(slack, trigger_id, channel_id, user_id, blueprint_name, required_params)

    # If config provided, validate it
    if config:
        is_valid, errors = detector.validate_parameters(blueprint_name, config)
        if not is_valid:
            error_msg = "Invalid parameters:\n" + "\n".join([f"• {err}" for err in errors])
            slack.post_message(channel_id, text=f"❌ {error_msg}")
            return {"statusCode": 400, "body": "Invalid parameters"}

    builder = get_infrastructure_builder()

    try:
        # Use provided config or build from parameter defaults
        if config is None:
            # Build default config from required parameters
            config = {}
            for param in required_params:
                if param.default:
                    config[param.name] = param.default
            # Fallback if no parameters defined
            if not config:
                config = {"name": "main", "environment": "prod"}

        result = builder.generate(blueprint_name.strip(), config)

        # Upload to GitHub and post to Slack
        try:
            github = get_github_service()
            uploader = CodeUploader(github, slack)

            upload_result = uploader.upload_and_notify(
                channel_id=channel_id,
                user_id=user_id,
                blueprint_name=blueprint_name,
                terraform_code=result.terraform_code,
                metadata={
                    "compliance_notes": result.compliance_notes,
                    "deployment_steps": result.deployment_steps,
                    "config": config
                }
            )

            logger.info(f"Uploaded code to GitHub: PR #{upload_result['pr_number']}")

            # Log interaction for learning
            try:
                from services.learning_service import LearningService

                scan_history_table = os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history")
                resource_graph_table = os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")

                learning_service = LearningService(
                    scan_history_table=scan_history_table,
                    resource_graph_table=resource_graph_table
                )

                interaction_id = learning_service.log_interaction(
                    user_id=user_id,
                    question=f"Build blueprint: {blueprint_name}",
                    scans_performed=["build_infrastructure"],
                    resources_found=[blueprint_name],
                    scan_duration_ms=0,  # Track if needed
                    interaction_type="architecture",
                    metadata={
                        "channel_id": channel_id,
                        "pr_number": upload_result.get('pr_number'),
                        "config": config
                    }
                )

                logger.info(f"Logged build interaction {interaction_id}")
            except Exception as e:
                logger.warning(f"Failed to log build interaction: {e}")

        except Exception as e:
            logger.error(f"Failed to upload to GitHub: {e}")
            slack.post_message(
                channel_id,
                text=f"❌ Failed to upload to GitHub: {str(e)}\n\nCode was generated but not uploaded. Please contact platform team."
            )
            return {"statusCode": 500, "body": str(e)}

    except ValueError as e:
        slack.post_message(channel_id, text=f"Error: {str(e)}. Use /carl blueprints` to see available options.")

    return {"statusCode": 200, "body": ""}


def show_blueprint_config_modal(
    slack: SlackService,
    trigger_id: str,
    channel_id: str,
    user_id: str,
    blueprint_name: str,
    required_params: list
) -> dict:
    """
    Show modal to collect blueprint parameters (intelligent, not hardcoded).

    Dynamically builds modal based on required_params list.
    """
    import json as json_lib
    from services.blueprint_parameter_detector import ParameterType

    # Build blocks dynamically based on required parameters
    blocks = []

    for param in required_params:
        # Create input block based on parameter type
        if param.type == ParameterType.ENVIRONMENT:
            # Environment dropdown
            element = {
                "type": "static_select",
                "action_id": f"param_{param.name}",
                "placeholder": {
                    "type": "plain_text",
                    "text": param.description
                },
                "initial_option": {
                    "text": {"type": "plain_text", "text": param.default or "Production"},
                    "value": param.default or "prod"
                },
                "options": [
                    {"text": {"type": "plain_text", "text": "Development"}, "value": "dev"},
                    {"text": {"type": "plain_text", "text": "Staging"}, "value": "staging"},
                    {"text": {"type": "plain_text", "text": "Production"}, "value": "prod"},
                ]
            }
        else:
            # Text input for everything else
            element = {
                "type": "plain_text_input",
                "action_id": f"param_{param.name}",
                "placeholder": {
                    "type": "plain_text",
                    "text": param.description
                },
            }
            if param.default:
                element["initial_value"] = param.default

        blocks.append({
            "type": "input",
            "block_id": f"block_{param.name}",
            "element": element,
            "label": {
                "type": "plain_text",
                "text": param.name.replace("_", " ").title()
            },
            "hint": {
                "type": "plain_text",
                "text": param.description
            },
            "optional": not param.required
        })

    modal = {
        "type": "modal",
        "callback_id": "blueprint_config_modal",
        "private_metadata": json_lib.dumps({
            "channel_id": channel_id,
            "blueprint_name": blueprint_name
        }),
        "title": {
            "type": "plain_text",
            "text": f"{blueprint_name.split('/')[-1].title()} Config"
        },
        "submit": {
            "type": "plain_text",
            "text": "Generate Code"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": blocks
    }

    try:
        slack.client.views_open(trigger_id=trigger_id, view=modal)
        return {"statusCode": 200, "body": ""}
    except Exception as e:
        logger.error(f"Failed to show blueprint config modal: {e}")
        return {"statusCode": 500, "body": str(e)}


def show_vpc_config_modal(slack: SlackService, trigger_id: str, channel_id: str, user_id: str, blueprint_name: str) -> dict:
    """Show modal to collect VPC configuration (CIDR, etc.)."""
    import json as json_lib

    modal = {
        "type": "modal",
        "callback_id": "vpc_config_modal",
        "private_metadata": json_lib.dumps({
            "channel_id": channel_id,
            "blueprint_name": blueprint_name
        }),
        "title": {
            "type": "plain_text",
            "text": "VPC Configuration"
        },
        "submit": {
            "type": "plain_text",
            "text": "Generate Code"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "vpc_cidr_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "vpc_cidr_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "10.0.0.0/16"
                    },
                    "initial_value": "10.0.0.0/16"
                },
                "label": {
                    "type": "plain_text",
                    "text": "VPC CIDR Block"
                },
                "hint": {
                    "type": "plain_text",
                    "text": "Enter a valid CIDR block (e.g., 10.0.0.0/16 or 172.16.0.0/12)"
                }
            },
            {
                "type": "input",
                "block_id": "vpc_name_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "vpc_name_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "main"
                    },
                    "initial_value": "main"
                },
                "label": {
                    "type": "plain_text",
                    "text": "VPC Name"
                },
                "hint": {
                    "type": "plain_text",
                    "text": "A name for your VPC resources"
                }
            },
            {
                "type": "input",
                "block_id": "environment_block",
                "element": {
                    "type": "static_select",
                    "action_id": "environment_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select environment"
                    },
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "Production"
                        },
                        "value": "prod"
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Development"
                            },
                            "value": "dev"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Staging"
                            },
                            "value": "staging"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Production"
                            },
                            "value": "prod"
                        }
                    ]
                },
                "label": {
                    "type": "plain_text",
                    "text": "Environment"
                }
            }
        ]
    }

    try:
        # Open the modal using the Slack API
        response = slack.client.views_open(
            trigger_id=trigger_id,
            view=modal
        )
        logger.info(f"Modal opened: {response}")
    except Exception as e:
        logger.exception("Error opening modal")
        slack.post_message(channel_id, text=f"❌ Error showing configuration form: {str(e)}\n\nUsing default configuration instead...")
        # Fallback to default config
        return handle_build_command(slack, channel_id, user_id, blueprint_name, {"name": "main", "environment": "prod", "cidr": "10.0.0.0/16"}, trigger_id=None)

    return {"statusCode": 200, "body": ""}


def show_s3_config_modal(slack: SlackService, trigger_id: str, channel_id: str, user_id: str, blueprint_name: str) -> dict:
    """Show modal to collect S3 bucket configuration."""
    import json as json_lib

    modal = {
        "type": "modal",
        "callback_id": "s3_config_modal",
        "private_metadata": json_lib.dumps({
            "channel_id": channel_id,
            "blueprint_name": blueprint_name
        }),
        "title": {
            "type": "plain_text",
            "text": "S3 Bucket Config"
        },
        "submit": {
            "type": "plain_text",
            "text": "Generate Code"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": [
            {
                "type": "input",
                "block_id": "bucket_name_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "bucket_name_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "my-data-bucket"
                    },
                    "initial_value": "my-data-bucket"
                },
                "label": {
                    "type": "plain_text",
                    "text": "Bucket Name Prefix"
                },
                "hint": {
                    "type": "plain_text",
                    "text": "Bucket name prefix (lowercase, 3-63 chars). Account ID will be appended automatically."
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "ℹ️ *Note:* Your AWS account ID will be automatically appended to ensure global uniqueness.\n\n*Example:* my-data-bucket → `my-data-bucket-123456789012"
                    }
                ]
            }
        ]
    }

    try:
        # Open the modal using the Slack API
        response = slack.client.views_open(
            trigger_id=trigger_id,
            view=modal
        )
        logger.info(f"S3 config modal opened: {response}")
    except Exception as e:
        logger.exception("Error opening S3 config modal")
        slack.post_message(channel_id, text=f"❌ Error showing configuration form: {str(e)}\n\nUsing default configuration instead...")
        # Fallback to default config
        return handle_build_command(slack, channel_id, user_id, blueprint_name, {"name": "my-data-bucket"}, trigger_id=None)

    return {"statusCode": 200, "body": ""}


def show_setup_modal(slack: SlackService, trigger_id: str, channel_id: str, workspace_id: str, step: int = 1) -> dict:
    """Show setup configuration modal."""
    import json as json_lib

    # Step 1: Notification channel and scan schedule
    modal = {
        "type": "modal",
        "callback_id": "setup_modal",
        "private_metadata": json_lib.dumps({
            "channel_id": channel_id,
            "workspace_id": workspace_id,
            "step": step
        }),
        "title": {
            "type": "plain_text",
            "text": "CARL Setup (1/2)"
        },
        "submit": {
            "type": "plain_text",
            "text": "Next"
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel"
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Step 1: Notifications & Scanning*\n\nConfigure where CARL sends notifications and how often to scan your environment."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "input",
                "block_id": "notification_channel_block",
                "element": {
                    "type": "channels_select",
                    "action_id": "notification_channel_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a channel"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Default Notification Channel"
                },
                "hint": {
                    "type": "plain_text",
                    "text": "This channel will receive daily summaries and critical alerts"
                }
            },
            {
                "type": "input",
                "block_id": "scan_schedule_block",
                "element": {
                    "type": "static_select",
                    "action_id": "scan_schedule_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select scan schedule"
                    },
                    "initial_option": {
                        "text": {
                            "type": "plain_text",
                            "text": "On-demand only"
                        },
                        "value": "on_demand"
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "On-demand only"
                            },
                            "value": "on_demand"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Daily at 6 AM UTC"
                            },
                            "value": "daily"
                        }
                    ]
                },
                "label": {
                    "type": "plain_text",
                    "text": "Scan Schedule"
                },
                "hint": {
                    "type": "plain_text",
                    "text": "How often to automatically scan your AWS environment"
                }
            },
            {
                "type": "input",
                "block_id": "auto_scan_block",
                "optional": True,
                "element": {
                    "type": "checkboxes",
                    "action_id": "auto_scan_input",
                    "initial_options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Enable auto-scan after deployments"
                            },
                            "value": "auto_scan"
                        }
                    ],
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "Enable auto-scan after deployments"
                            },
                            "value": "auto_scan"
                        }
                    ]
                },
                "label": {
                    "type": "plain_text",
                    "text": "Auto-scan Options"
                }
            }
        ]
    }

    try:
        response = slack.client.views_open(
            trigger_id=trigger_id,
            view=modal
        )
        logger.info(f"Setup modal opened: {response}")
    except Exception as e:
        logger.exception("Error opening setup modal")
        slack.post_message(channel_id, text=f"❌ Error showing setup wizard: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_exception_request_modal_submission(payload: dict) -> dict:
    """Handle exception request modal submission - creates formal exception."""
    from services.findings_service import FindingsService
    from services.exception_manager import ExceptionManager, ExceptionRequest, ExceptionType, RiskLevel
    from datetime import datetime, timedelta
    import os

    view = payload.get("view", {})
    user = payload.get("user", {}).get("id", "")

    # Get finding ID and account ID from private_metadata
    metadata = view.get("private_metadata", "")
    finding_id, account_id = metadata.split("|") if "|" in metadata else (metadata, None)

    # Get values from modal
    values = view.get("state", {}).get("values", {})
    justification = values.get("justification_block", {}).get("justification_input", {}).get("value", "")
    expiration_days = values.get("expiration_block", {}).get("expiration_input", {}).get("value", "90")

    if not justification:
        return {
            "response_action": "errors",
            "errors": {
                "justification_block": "Business justification is required"
            }
        }

    try:
        expiration_days = int(expiration_days)
    except ValueError:
        return {
            "response_action": "errors",
            "errors": {
                "expiration_block": "Must be a number"
            }
        }

    findings_service = FindingsService()
    finding = findings_service.get_finding(finding_id, account_id)

    if not finding:
        return {"statusCode": 200, "body": ""}

    # Create exception request
    exceptions_table = os.environ.get("EXCEPTIONS_TABLE", "carl-exceptions")
    findings_table = os.environ.get("FINDINGS_TABLE", "carl-findings")
    manager = ExceptionManager(exceptions_table, findings_table)

    expiration_date = (datetime.utcnow() + timedelta(days=expiration_days)).isoformat()

    exception = manager.create_exception(
        finding_id=finding_id,
        finding_title=finding.get('title', 'Unknown Finding'),
        justification=justification,
        exception_type=ExceptionType.RISK_ACCEPTANCE,
        risk_level=RiskLevel[finding.get('severity', 'MEDIUM')],
        expiration_date=expiration_date,
        requested_by=user,
        compensating_controls=[]
    )

    slack = get_slack_service()
    channel = payload.get("view", {}).get("private_metadata", "")  # Would need to pass channel

    # Post confirmation (we don't have channel here, so this would need to be improved)
    logger.info(f"Exception request created: {exception.exception_id} for finding {finding_id}")

    return {"statusCode": 200, "body": ""}


def handle_accept_risk_modal_submission(payload: dict) -> dict:
    """Handle Accept Risk modal submission."""
    from services.findings_service import FindingsService

    view = payload.get("view", {})
    user = payload.get("user", {}).get("id", "")

    # Get finding ID from private_metadata
    finding_id = view.get("private_metadata", "")

    # Get justification from modal input
    values = view.get("state", {}).get("values", {})
    justification = values.get("justification_block", {}).get("justification_input", {}).get("value", "")

    if not justification:
        # Return error - justification is required
        return {
            "response_action": "errors",
            "errors": {
                "justification_block": "Justification is required for accepting a risk"
            }
        }

    findings_service = FindingsService()

    # Get account ID
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Accept the risk
    success = findings_service.accept_risk(
        finding_id=finding_id,
        account_id=account_id,
        justification=justification,
        accepted_by=user
    )

    if success:
        # Post success message to channel (requires getting channel from metadata or response_url)
        # Since we don't have channel easily, we'll return success and let Slack close modal
        logger.info(f"Risk accepted for finding {finding_id} by {user}")
    else:
        logger.error(f"Failed to accept risk for finding {finding_id}")

    # Close modal
    return {"statusCode": 200, "body": ""}


def handle_blueprint_config_submission(payload: dict) -> dict:
    """
    Handle blueprint config modal submission (intelligent parameter collection).

    Extracts all parameters dynamically and validates them before building.
    """
    slack = get_slack_service()
    view = payload.get("view", {})
    private_metadata = json.loads(view.get("private_metadata", "{}"))
    channel_id = private_metadata.get("channel_id")
    blueprint_name = private_metadata.get("blueprint_name")

    # Extract all parameter values from modal
    values = view.get("state", {}).get("values", {})
    config = {}

    for block_id, block_values in values.items():
        # Block ID format: block_{param_name}
        if block_id.startswith("block_"):
            param_name = block_id.replace("block_", "")

            # Find the value in the block (could be text input or select)
            for action_id, action_value in block_values.items():
                if action_id.startswith("param_"):
                    # Get value based on type
                    if "selected_option" in action_value:
                        # Dropdown selection
                        config[param_name] = action_value["selected_option"]["value"]
                    elif "value" in action_value:
                        # Text input
                        config[param_name] = action_value["value"]

    logger.info(f"Blueprint config collected: {config}")

    # Validate parameters
    from services.blueprint_parameter_detector import BlueprintParameterDetector

    detector = BlueprintParameterDetector()
    is_valid, errors = detector.validate_parameters(blueprint_name, config)

    if not is_valid:
        # Return validation errors to modal
        error_msg = "Validation failed:\n" + "\n".join([f"• {err}" for err in errors])
        return {
            "response_action": "errors",
            "errors": {
                f"block_{list(config.keys())[0]}": error_msg[:150]  # Show first error
            }
        }

    # Parameters valid - proceed with build
    user_id = payload.get("user", {}).get("id")

    # Call handle_build_command with validated config
    return handle_build_command(
        slack=slack,
        channel_id=channel_id,
        user_id=user_id,
        blueprint_name=blueprint_name,
        config=config,
        trigger_id=None  # Already in modal submission, no trigger_id needed
    )


def handle_vpc_config_submission(payload: dict) -> dict:
    """Handle VPC configuration modal submission with validation."""
    import json as json_lib
    from utils.input_validation import validate_cidr, validate_resource_name, sanitize_resource_name, validate_environment

    slack = get_slack_service()

    # Extract values from modal submission
    view = payload.get("view", {})
    values = view.get("state", {}).get("values", {})
    private_metadata = json_lib.loads(view.get("private_metadata", "{}"))

    channel_id = private_metadata.get("channel_id")
    blueprint_name = private_metadata.get("blueprint_name")

    # Extract input values
    vpc_cidr = values.get("vpc_cidr_block", {}).get("vpc_cidr_input", {}).get("value", "10.0.0.0/16").strip()
    vpc_name = values.get("vpc_name_block", {}).get("vpc_name_input", {}).get("value", "main").strip()
    environment = values.get("environment_block", {}).get("environment_input", {}).get("selected_option", {}).get("value", "prod")

    # Validate inputs
    errors = {}

    # Validate CIDR
    cidr_valid, cidr_error = validate_cidr(vpc_cidr)
    if not cidr_valid:
        errors["vpc_cidr_block"] = cidr_error

    # Validate VPC name
    name_valid, name_error = validate_resource_name(vpc_name, "VPC")
    if not name_valid:
        # Try to sanitize and suggest
        sanitized = sanitize_resource_name(vpc_name)
        errors["vpc_name_block"] = f"{name_error}. Suggestion: '{sanitized}'"

    # Validate environment
    env_valid, env_error = validate_environment(environment)
    if not env_valid:
        errors["environment_block"] = env_error

    # If there are validation errors, return them to Slack
    if errors:
        return {
            "response_action": "errors",
            "errors": errors
        }

    # Sanitize the VPC name (in case it has minor issues)
    vpc_name = sanitize_resource_name(vpc_name)

    # Build configuration
    config = {
        "name": vpc_name,
        "environment": environment,
        "cidr": vpc_cidr
    }

    # Invoke async processing in background to avoid 3-second timeout
    user_id = payload.get("user", {}).get("id", "")
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json_lib.dumps({
                'action': 'process_vpc_config_async',
                'channel_id': channel_id,
                'user_id': user_id,
                'blueprint_name': blueprint_name,
                'config': config
            })
        )
        logger.info("Invoked async VPC config processing")
    except Exception as e:
        logger.error(f"Failed to invoke async processing: {e}")
        # Fallback to synchronous if async fails
        try:
            slack.post_message(channel_id, text=f"✅ Configuration received! Generating {blueprint_name} with CIDR {vpc_cidr}...")
            handle_build_command(slack, channel_id, user_id, blueprint_name, config, trigger_id=None)
        except Exception as e2:
            logger.error(f"Error processing VPC config: {e2}")

    # Return 200 immediately to close modal (must be within 3 seconds)
    return {"statusCode": 200, "body": ""}


def handle_build_config_submission(payload: dict) -> dict:
    """Handle build configuration modal submission with validation."""
    import ipaddress
    import re
    import json as json_lib

    slack = get_slack_service()
    user_id = payload["user"]["id"]

    # Parse callback_id: build_config_submit:{session_id}:{option_number}
    callback_id = payload["view"]["callback_id"]
    parts = callback_id.split(":")
    if len(parts) < 3:
        return {"statusCode": 200, "body": ""}

    session_id = parts[1]
    option_number = parts[2]

    # Get the session to retrieve the original requirement
    from services.build_session_service import BuildSessionService
    session_service = BuildSessionService()
    session = session_service.get_session(session_id, user_id)

    # Extract what the user originally asked for
    requirement = ""
    option_text = ""
    if session:
        requirement = session.requirement
        recommendation = session.environment_scan.get("recommendation", "")
        # Extract the specific option text
        import re
        pattern = rf'OPTION\s+{option_number}:.*?(?=OPTION\s+\d+:|My Recommendation:|$)'
        option_match = re.search(pattern, recommendation, re.IGNORECASE | re.DOTALL)
        if option_match:
            option_text = option_match.group(0).strip()

    # Extract form values
    values = payload["view"]["state"]["values"]

    # Parse inputs
    vpc_selection = values.get("vpc_selection", {}).get("vpc_select", {}).get("selected_option", {}).get("value")
    vpc_cidr = values.get("vpc_cidr", {}).get("vpc_cidr_input", {}).get("value", "")
    prefix = values.get("resource_prefix", {}).get("prefix_input", {}).get("value", "carl")
    environment = values.get("environment", {}).get("env_select", {}).get("selected_option", {}).get("value", "prod")
    use_tgw = values.get("use_transit_gateway", {}).get("tgw_select", {}).get("selected_option", {}).get("value", "no")

    # Validate inputs
    errors = {}

    # Validate VPC input based on selection
    vpc_id = None
    cidr = None

    if not vpc_cidr or not vpc_cidr.strip():
        errors["vpc_cidr"] = "VPC ID or CIDR is required"
    elif vpc_selection == "create_new":
        # Validate as CIDR
        try:
            ipaddress.ip_network(vpc_cidr.strip())
            cidr = vpc_cidr.strip()
        except ValueError:
            errors["vpc_cidr"] = "Invalid CIDR format (e.g., 10.0.0.0/16)"
    elif vpc_selection == "existing":
        # Validate as VPC ID
        if re.match(r'^vpc-[a-f0-9]{8,17}$', vpc_cidr.strip()):
            vpc_id = vpc_cidr.strip()
        else:
            errors["vpc_cidr"] = "Invalid VPC ID format (must be vpc-xxxxxxxx)"

    # Validate prefix
    if not re.match(r'^[a-z][a-z0-9-]*$', prefix):
        errors["resource_prefix"] = "Must start with letter, lowercase, hyphens only"

    if errors:
        return {
            "response_action": "errors",
            "errors": errors
        }

    # Get channel from private_metadata
    private_metadata = payload["view"].get("private_metadata", "{}")
    try:
        metadata = json_lib.loads(private_metadata) if private_metadata else {}
        channel_id = metadata.get("channel_id", "")
    except:
        # Fallback: post to user's DM
        channel_id = user_id

    # Generate Terraform configuration
    terraform_config = {
        "vpc_id": vpc_id,
        "vpc_cidr": cidr,
        "prefix": prefix,
        "environment": environment,
        "use_transit_gateway": use_tgw == "yes",
        "requirement": requirement,
        "option_text": option_text,
        "channel_id": channel_id,
        "user_id": user_id
    }

    # Invoke async Lambda to generate Terraform (avoids 3-second modal timeout)
    import boto3
    import os
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async
            Payload=json_lib.dumps({
                'action': 'generate_terraform_async',
                'terraform_config': terraform_config
            })
        )
        logger.info("Invoked async Terraform generation")
    except Exception as e:
        logger.error(f"Failed to invoke async generation: {e}")
        # Fallback: notify user of error
        slack.post_message(
            channel_id,
            text=f"❌ Failed to start Terraform generation: {str(e)}"
        )

    # Return 200 immediately to close modal (must be within 3 seconds)
    return {"statusCode": 200, "body": ""}


def _generate_terraform_with_ai(config: dict, progress_callback=None) -> dict:
    """Use AI to generate appropriate Terraform based on user's requirement.

    Splits generation into multiple Bedrock calls to avoid timeouts on complex infrastructure.

    Args:
        config: Infrastructure configuration
        progress_callback: Optional callback function to report progress (e.g., post to Slack)

    Returns dict with keys: 'variables', 'main', 'outputs', 'tfvars_example', 'readme' for separate files.
    """
    from services.bedrock_service import BedrockService
    import logging

    logger = logging.getLogger(__name__)
    bedrock = BedrockService()

    # Build context for AI
    requirement = config.get("requirement", "infrastructure setup")
    option_text = config.get("option_text", "")

    # Clean up option_text: convert escaped newlines to actual newlines
    if option_text:
        option_text = option_text.replace('\\n', '\n')  # Convert escaped newlines
        option_text = option_text.strip()

    vpc_info = f"VPC ID: {config['vpc_id']}" if config.get('vpc_id') else f"VPC CIDR: {config['vpc_cidr']}"

    # Common context for all prompts
    common_context = f"""
**USER'S REQUIREMENT:**
{requirement}

**SELECTED OPTION:**
{option_text}

**CONFIGURATION:**
- {vpc_info}
- Resource Prefix: {config['prefix']}
- Environment: {config['environment']}
- Transit Gateway: {'Yes' if config.get('use_transit_gateway') else 'No'}
"""

    # Step 1: Generate variables.tf
    logger.info("Step 1/5: Generating variables.tf")
    if progress_callback:
        progress_callback("Step 1/5: Generating variables.tf...")

    variables_prompt = f"""Generate ONLY the variables.tf file for the following AWS infrastructure requirement.
{common_context}

**CRITICAL REQUIREMENTS - FOLLOW EXACTLY:**

1. **Every variable MUST have ALL of these:**
   - description (required, clear explanation of what it controls)
   - type (required, use proper types: string, number, bool, list(string), map(string), object({{...}}))
   - default value OR validation block (required for production-ready code)

2. **Required Variables (MUST include):**
   - resource_prefix (string, used for naming all resources)
   - environment (string, e.g., dev/staging/prod, with validation)
   - aws_region (string, default to us-east-1)
   - tags (map(string), common tags for all resources)

3. **Infrastructure-Specific Variables:**
   Based on the requirement, include relevant variables:
   - VPC: vpc_cidr, enable_vpc_flow_logs, vpc_id (if using existing)
   - EC2: instance_type, key_name, ami_id
   - RDS: db_instance_class, db_engine, db_name, multi_az
   - S3: bucket_name, enable_versioning, enable_encryption
   - Lambda: runtime, memory_size, timeout
   - Static Website: domain_name, create_acm_certificate
   - API: api_name, api_type (rest/http)
   - Containers: cluster_name, service_name, task_cpu, task_memory

4. **Validation Blocks (where applicable):**
   - environment: condition = contains(["dev", "staging", "prod"], var.environment)
   - instance_type: condition = contains(["t3.micro", "t3.small", "t3.medium"], var.instance_type)
   - aws_region: condition = can(regex("^[a-z]{2}-[a-z]+-\\\\d{1}$", var.aws_region))
   - CIDR: condition = can(cidrhost(var.vpc_cidr, 0))

5. **Naming Conventions:**
   - Use snake_case for all variable names
   - Group related variables with # comment headers
   - Order: General → Networking → Compute → Database → Storage → Monitoring

6. **Example Format:**
```hcl
variable "environment" {{
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {{
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod"
  }}
}}
``"

Return ONLY the Terraform variables.tf file content following the format above. No markers, no extra text."""

    variables_content = bedrock.invoke_model(
        prompt=variables_prompt,
        max_tokens=4000  # Increased for detailed variables with validation
    )

    # Step 2: Generate main.tf (the big one - resources)
    logger.info("Step 2/5: Generating main.tf with resources")
    if progress_callback:
        progress_callback("Step 2/5: Generating main.tf (infrastructure resources)...")
    main_prompt = f"""Generate ONLY the main.tf file for the following AWS infrastructure requirement.
{common_context}

**INCLUDE IN main.tf:**
- Terraform block with required_version >= 1.5
- Provider configuration (AWS ~> 5.0)
- Locals for name prefixes and common tags
- Data sources for existing resources (VPC if ID provided)
- ALL infrastructure resources needed for the requirement
- ALL security best practices implemented:
  * Encryption at rest (KMS keys where applicable)
  * Encryption in transit (TLS/SSL)
  * Logging (CloudWatch Logs, VPC Flow Logs, access logs)
  * Monitoring (CloudWatch alarms for critical metrics)
  * WAF (for web-facing infrastructure like CloudFront, ALBs, API Gateway)
  * Private connectivity (VPC endpoints for AWS services where applicable)
  * Backup and recovery (backup plans, automated snapshots)
  * Least privilege security groups

**RESOURCE STANDARDS:**
- Consistent naming using locals (e.g., local.name_prefix)
- All resources tagged: Name, Environment, ManagedBy, Project
- Add lifecycle blocks where appropriate (prevent_destroy for stateful resources)
- Include comments above complex resources

**CRITICAL FOR SPECIFIC TYPES:**
- **Static Websites**: S3 (private) + CloudFront + WAF + ACM certificate
- **APIs**: API Gateway + Lambda + Cognito/authorizer + WAF + CloudWatch
- **Databases**: KMS encryption + automated backups + Multi-AZ + monitoring
- **Container Apps**: ECS + ALB + WAF + ECR + monitoring

**DO NOT INCLUDE:**
- DO NOT include output blocks - those belong in outputs.tf (generated separately)
- DO NOT include variable definitions - those are in variables.tf

Return ONLY the main.tf file content (terraform block, provider, locals, data sources, resources), no markers or extra text."""

    main_content = bedrock.invoke_model(
        prompt=main_prompt,
        max_tokens=8000  # Biggest file, needs most tokens
    )

    # Step 3: Generate outputs.tf
    logger.info("Step 3/5: Generating outputs.tf")
    if progress_callback:
        progress_callback("Step 3/5: Generating outputs.tf...")
    outputs_prompt = f"""Generate ONLY the outputs.tf file for the infrastructure described below.
{common_context}

Based on the resources that would be created, generate outputs for:
- Resource IDs (VPC, subnets, security groups, etc.)
- ARNs (KMS keys, S3 buckets, Lambda functions, etc.)
- DNS names (ALB, CloudFront, RDS endpoints, etc.)
- URLs (API Gateway endpoints, website URLs, etc.)

**OUTPUT STANDARDS:**
- Every major resource should have outputs
- Include descriptions for all outputs
- Mark sensitive data as sensitive = true (credentials, private keys, etc.)

Return ONLY the outputs.tf file content, no markers or extra text."""

    outputs_content = bedrock.invoke_model(
        prompt=outputs_prompt,
        max_tokens=2000
    )

    # Step 4: Generate terraform.tfvars.example
    logger.info("Step 4/5: Generating terraform.tfvars.example")
    if progress_callback:
        progress_callback("Step 4/5: Generating terraform.tfvars.example...")
    tfvars_prompt = f"""Generate ONLY the terraform.tfvars.example file showing example values for all variables.
{common_context}

Include example values for all variables that would be defined in variables.tf.
Add comments explaining what each value controls.

Return ONLY the terraform.tfvars.example file content, no markers or extra text."""

    tfvars_content = bedrock.invoke_model(
        prompt=tfvars_prompt,
        max_tokens=1500
    )

    # Step 5: Generate README.md
    logger.info("Step 5/5: Generating README.md")
    if progress_callback:
        progress_callback("Step 5/5: Generating README.md (documentation)...")
    readme_prompt = f"""Generate ONLY the README.md documentation file for this infrastructure.
{common_context}

**INCLUDE IN README:**
1. Brief description of what this deploys
2. **SOC 2 Controls Addressed**: List relevant controls (CC6.1, CC6.7, CC7.1, CC7.2, A1.3, PI1.1, etc.)
3. **Security Best Practices Implemented**: What's included (encryption, logging, monitoring, WAF, etc.)
4. **Additional Recommendations**: What could be added (GuardDuty, Inspector, etc.)
5. Prerequisites (existing VPC, AWS permissions, Terraform version, etc.)
6. Usage instructions (terraform init/plan/apply commands)
7. List of resources created
8. Inputs table (variable names, types, descriptions)
9. Outputs table (output names, descriptions)
10. Post-deployment steps (configure alarms, review logs, test connectivity, etc.)

Return ONLY the README.md file content, no markers or extra text."""

    readme_content = bedrock.invoke_model(
        prompt=readme_prompt,
        max_tokens=3000
    )

    logger.info("Terraform generation complete (5/5 steps done)")
    if progress_callback:
        progress_callback("✅ All files generated! Creating GitHub Pull Request...")

    # Return all files
    return {
        'variables': variables_content.strip(),
        'main': main_content.strip(),
        'outputs': outputs_content.strip(),
        'tfvars_example': tfvars_content.strip(),
        'readme': readme_content.strip()
    }



def _organize_foundation_terraform_files(modules: list, session) -> dict:
    """
    Organize foundation modules into proper Terraform file structure.

    Follows Terraform best practices:
    - main.tf: Main resource definitions (organized by category)
    - variables.tf: All input variable definitions
    - outputs.tf: All output definitions
    - providers.tf: Provider configuration
    - versions.tf: Terraform version constraints
    - terraform.tfvars.example: Example variable values
    - README.md: Documentation

    Args:
        modules: List of TerraformModule objects from FoundationBuilder
        session: DecisionSession with requirements and framework info

    Returns:
        Dict with keys: main, variables, outputs, tfvars_example, readme
    """
    import re

    # Collect all content, variables, and outputs
    networking_content = []
    security_content = []
    connectivity_content = []
    compliance_content = []
    all_variables = []
    all_outputs = []

    for module in modules:
        if not module.content or len(module.content) < 50:
            continue

        content = module.content

        # Extract variable blocks
        var_pattern = r'(variable\s+"[^"]+"\s*\{[^}]+\})'
        variables = re.findall(var_pattern, content, re.DOTALL)
        for var in variables:
            if var not in all_variables:
                all_variables.append(var)
        # Remove variables from content (they go in variables.tf)
        content = re.sub(var_pattern, '', content, flags=re.DOTALL)

        # Extract output blocks
        out_pattern = r'(output\s+"[^"]+"\s*\{[^}]+\})'
        outputs = re.findall(out_pattern, content, re.DOTALL)
        for out in outputs:
            if out not in all_outputs:
                all_outputs.append(out)
        # Remove outputs from content (they go in outputs.tf)
        content = re.sub(out_pattern, '', content, flags=re.DOTALL)

        # Categorize remaining content
        content = content.strip()
        if not content:
            continue

        # Add module header comment
        header = f"\n# {'=' * 60}\n# {module.name.upper()} - {module.description}\n# {'=' * 60}\n\n"

        if module.name in ['egress', 'ingress', 'transit', 'vpc']:
            networking_content.append(header + content)
        elif module.name in ['site_vpn', 'client_vpn', 'direct_connect']:
            connectivity_content.append(header + content)
        elif module.name in ['security', 'guardduty', 'security_hub', 'config', 'inspector']:
            security_content.append(header + content)
        else:
            compliance_content.append(header + content)

    # Build main.tf with organized sections
    main_tf = '''# Foundation Infrastructure
# Generated by CARL - Compliant AWS Resource Logic
#
# This module creates the foundation infrastructure including:
# - Networking (VPCs, NAT, Transit Gateway)
# - Security Services (GuardDuty, Security Hub, Config)
# - Connectivity (VPN, Direct Connect)
#
# Terraform Best Practices Applied:
# - Separate files for variables, outputs, providers
# - Organized by resource category
# - Consistent tagging
# - Security-first configuration

'''

    if networking_content:
        main_tf += "\n# " + "=" * 70 + "\n"
        main_tf += "# NETWORKING\n"
        main_tf += "# " + "=" * 70 + "\n"
        main_tf += "\n".join(networking_content)

    if security_content:
        main_tf += "\n\n# " + "=" * 70 + "\n"
        main_tf += "# SECURITY SERVICES\n"
        main_tf += "# " + "=" * 70 + "\n"
        main_tf += "\n".join(security_content)

    if connectivity_content:
        main_tf += "\n\n# " + "=" * 70 + "\n"
        main_tf += "# CONNECTIVITY\n"
        main_tf += "# " + "=" * 70 + "\n"
        main_tf += "\n".join(connectivity_content)

    if compliance_content:
        main_tf += "\n\n# " + "=" * 70 + "\n"
        main_tf += "# COMPLIANCE & OTHER\n"
        main_tf += "# " + "=" * 70 + "\n"
        main_tf += "\n".join(compliance_content)

    # Add data sources at the end
    main_tf += '''

# ============================================================================
# DATA SOURCES
# ============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# ============================================================================
# LOCALS
# ============================================================================

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  azs        = slice(data.aws_availability_zones.available.names, 0, var.az_count)

  common_tags = {
    ManagedBy  = "CARL"
    Environment = var.environment
    Project    = var.project_name
  }
}
'''

    # Build variables.tf
    variables_tf = '''# Input Variables
# Generated by CARL

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "foundation"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "az_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 1 && var.az_count <= 3
    error_message = "AZ count must be between 1 and 3."
  }
}

'''

    # Add extracted variables
    if all_variables:
        variables_tf += "\n# Module-specific variables\n"
        variables_tf += "\n\n".join(all_variables)

    # Build outputs.tf
    outputs_tf = '''# Output Values
# Generated by CARL

output "account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "region" {
  description = "AWS Region"
  value       = data.aws_region.current.name
}

'''

    # Add extracted outputs
    if all_outputs:
        outputs_tf += "\n# Module-specific outputs\n"
        outputs_tf += "\n\n".join(all_outputs)

    # Build providers.tf (separate from versions.tf per Hashicorp recommendation)
    framework_name = session.framework.name if session.framework else "Best Practices"
    providers_tf = f'''# Provider Configuration
# Generated by CARL for {framework_name}

provider "aws" {{
  region = var.aws_region

  default_tags {{
    tags = {{
      ManagedBy   = "CARL"
      Compliance  = "{framework_name}"
      Environment = var.environment
    }}
  }}
}}

# US-East-1 provider (required for global services like CloudFront, WAF global)
provider "aws" {{
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {{
    tags = {{
      ManagedBy   = "CARL"
      Compliance  = "{framework_name}"
      Environment = var.environment
    }}
  }}
}}
'''

    # Build versions.tf
    versions_tf = '''# Terraform Configuration
# Generated by CARL

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}
'''

    # Build terraform.tfvars.example
    vpc_count = session.requirements.get("vpc_count", 1)
    tfvars_example = f'''# Example Variable Values
# Copy this file to terraform.tfvars and customize

environment  = "dev"
project_name = "my-foundation"
aws_region   = "us-east-1"
az_count     = 2

# VPC Configuration
# vpc_count = {vpc_count}
'''

    # Build README.md
    vpcs = session.requirements.get("vpcs", [])
    vpc_summary = ""
    if vpcs:
        for vpc in vpcs:
            vpc_summary += f"- **{vpc.get('name', 'VPC')}**: {vpc.get('cidr', 'N/A')} ({vpc.get('environment', 'N/A')})\n"

    readme = f'''# Foundation Infrastructure

Generated by **CARL** - Compliant AWS Resource Logic

## Overview

This Terraform configuration creates a compliant AWS foundation infrastructure based on **{framework_name}** requirements.

## Components

### Networking
{vpc_summary or "- VPC with public and private subnets"}

### Security Services
- GuardDuty threat detection
- Security Hub compliance monitoring
- AWS Config configuration tracking

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Terraform >= 1.5.0
3. S3 bucket for state storage (configure in backend.tf)

## Usage

```bash
# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply the configuration
terraform apply
```

## Files

| File | Description |
|------|-------------|
| `main.tf` | Main resource definitions |
| `variables.tf` | Input variable definitions |
| `outputs.tf` | Output value definitions |
| `providers.tf` | Provider configuration |
| `versions.tf` | Terraform version constraints |
| `terraform.tfvars.example` | Example variable values |
| `backend.tf` | State storage configuration |

## Estimated Monthly Cost

{f"${session.estimated_monthly_cost:.2f}/month" if session.estimated_monthly_cost else "N/A"}

## Compliance

This infrastructure is designed for **{framework_name}** compliance with:
- Encryption at rest (KMS)
- Encryption in transit (TLS)
- VPC Flow Logs enabled
- CloudWatch monitoring
- Security Hub compliance checks

---
*Generated by CARL on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
'''

    return {
        'main': main_tf.strip(),
        'variables': variables_tf.strip(),
        'outputs': outputs_tf.strip(),
        'tfvars_example': tfvars_example.strip(),
        'readme': readme.strip(),
        # Also include separate files for organization
        'providers': providers_tf.strip(),
        'versions': versions_tf.strip(),
    }


def _extract_soc2_controls(readme: str) -> list:
    """Extract SOC 2 controls mentioned in README."""
    import re
    # Match patterns like CC6.1, CC7.2, A1.3, C1.1, etc.
    control_pattern = r'\b(CC|A|C|PI)\d+\.\d+\b'
    controls = re.findall(control_pattern, readme)
    return list(set(controls))  # Unique controls


def _extract_security_practices(readme: str) -> list:
    """Extract security best practices from README."""
    practices = []

    # Common practice keywords
    keywords = {
        'encryption at rest': 'Encryption at rest (KMS)',
        'encryption in transit': 'Encryption in transit (TLS/SSL)',
        'vpc flow logs': 'VPC Flow Logs enabled',
        'cloudwatch': 'CloudWatch monitoring',
        'cloudtrail': 'CloudTrail logging',
        'backup': 'Automated backups configured',
        'multi-az': 'Multi-AZ deployment',
        'vpc endpoint': 'VPC endpoints for private access',
        'security group': 'Security groups with least privilege',
        'kms': 'KMS encryption',
        'ssl': 'SSL/TLS enforcement',
        'versioning': 'Versioning enabled',
        'mfa': 'MFA protection',
        'waf': 'AWS WAF protection',
        'access logging': 'Access logging enabled'
    }

    readme_lower = readme.lower()
    for keyword, practice in keywords.items():
        if keyword in readme_lower:
            practices.append(practice)

    return practices


def _parse_terraform_files(response: str) -> dict:
    """Parse AI response into separate Terraform files.

    Expected format:
    ### variables.tf ###
    <content>

    ### main.tf ###
    <content>

    ### outputs.tf ###
    <content>

    ### terraform.tfvars.example ###
    <content>

    ### README.md ###
    <content>
    """
    import re

    files = {}

    # Extract variables.tf
    variables_match = re.search(r'### variables\.tf ###\s*(.*?)\s*(?=### |$)', response, re.DOTALL)
    if variables_match:
        files['variables'] = variables_match.group(1).strip()
    else:
        files['variables'] = "# No variables defined\n"

    # Extract main.tf
    main_match = re.search(r'### main\.tf ###\s*(.*?)\s*(?=### |$)', response, re.DOTALL)
    if main_match:
        files['main'] = main_match.group(1).strip()
    else:
        # Fallback: If no markers, assume entire response is main.tf
        files['main'] = response.strip()

    # Extract outputs.tf
    outputs_match = re.search(r'### outputs\.tf ###\s*(.*?)\s*(?=### |$)', response, re.DOTALL)
    if outputs_match:
        files['outputs'] = outputs_match.group(1).strip()
    else:
        files['outputs'] = "# No outputs defined\n"

    # Extract terraform.tfvars.example
    tfvars_match = re.search(r'### terraform\.tfvars\.example ###\s*(.*?)\s*(?=### |$)', response, re.DOTALL)
    if tfvars_match:
        files['tfvars_example'] = tfvars_match.group(1).strip()
    else:
        files['tfvars_example'] = "# Copy this file to terraform.tfvars and customize\n"

    # Extract README.md
    readme_match = re.search(r'### README\.md ###\s*(.*?)$', response, re.DOTALL)
    if readme_match:
        files['readme'] = readme_match.group(1).strip()
    else:
        files['readme'] = f"# Terraform Infrastructure\n\nGenerated by CARL Infrastructure Builder\n"

    return files


def _generate_terraform_from_config(config: dict) -> str:
    """DEPRECATED: Generate Terraform HCL code from validated configuration.

    Use _generate_terraform_with_ai instead for intelligent generation.
    """
    terraform_lines = []

    # Detect what type of infrastructure to generate based on requirement
    requirement = config.get("requirement", "").lower()
    option_text = config.get("option_text", "").lower()
    combined_text = f"{requirement} {option_text}"

    # Detect resource types needed
    needs_vpn = any(kw in combined_text for kw in ['vpn', 'site-to-site', 'ipsec'])
    needs_direct_connect = any(kw in combined_text for kw in ['direct connect', 'dx', 'dedicated connection'])
    needs_transit_gateway = config.get("use_transit_gateway", False)

    # Header
    terraform_lines.append("# Infrastructure Configuration")
    terraform_lines.append(f"# Generated by CARL for: {config.get('requirement', 'infrastructure')}\n")
    terraform_lines.append("terraform {")
    terraform_lines.append("  required_version = \">= 1.0\"")
    terraform_lines.append("  required_providers {")
    terraform_lines.append("    aws = {")
    terraform_lines.append("      source  = \"hashicorp/aws\"")
    terraform_lines.append("      version = \"~> 5.0\"")
    terraform_lines.append("    }")
    terraform_lines.append("  }")
    terraform_lines.append("}\n")

    # VPC - Either data source or resource
    if config.get("vpc_id"):
        # Using existing VPC
        terraform_lines.append("# Reference existing VPC")
        terraform_lines.append("data \"aws_vpc\" \"existing\" {")
        terraform_lines.append(f"  id = \"{config['vpc_id']}\"")
        terraform_lines.append("}\n")
        vpc_ref = "data.aws_vpc.existing.id"
    else:
        # Create new VPC
        terraform_lines.append("# Create new VPC")
        terraform_lines.append("resource \"aws_vpc\" \"main\" {")
        terraform_lines.append(f"  cidr_block           = \"{config['vpc_cidr']}\"")
        terraform_lines.append("  enable_dns_hostnames = true")
        terraform_lines.append("  enable_dns_support   = true\n")
        terraform_lines.append("  tags = {")
        terraform_lines.append(f"    Name        = \"{config['prefix']}-vpc\"")
        terraform_lines.append(f"    Environment = \"{config['environment']}\"")
        terraform_lines.append("    ManagedBy   = \"CARL\"")
        terraform_lines.append("  }")
        terraform_lines.append("}\n")
        vpc_ref = "aws_vpc.main.id"

    # VPN Gateway and Site-to-Site VPN (if requested)
    if needs_vpn:
        terraform_lines.append("# VPN Gateway")
        terraform_lines.append("resource \"aws_vpn_gateway\" \"main\" {")
        terraform_lines.append(f"  vpc_id          = {vpc_ref}")
        terraform_lines.append("  amazon_side_asn = 64512\n")
        terraform_lines.append("  tags = {")
        terraform_lines.append(f"    Name        = \"{config['prefix']}-vgw\"")
        terraform_lines.append(f"    Environment = \"{config['environment']}\"")
        terraform_lines.append("    ManagedBy   = \"CARL\"")
        terraform_lines.append("  }")
        terraform_lines.append("}\n")

        terraform_lines.append("# Customer Gateway")
        terraform_lines.append("# TODO: Replace with your on-premises public IP address")
        terraform_lines.append("resource \"aws_customer_gateway\" \"main\" {")
        terraform_lines.append("  bgp_asn    = 65000")
        terraform_lines.append("  ip_address = \"203.0.113.1\"  # REPLACE with your public IP")
        terraform_lines.append("  type       = \"ipsec.1\"\n")
        terraform_lines.append("  tags = {")
        terraform_lines.append(f"    Name        = \"{config['prefix']}-cgw\"")
        terraform_lines.append(f"    Environment = \"{config['environment']}\"")
        terraform_lines.append("    ManagedBy   = \"CARL\"")
        terraform_lines.append("  }")
        terraform_lines.append("}\n")

        terraform_lines.append("# Site-to-Site VPN Connection")
        terraform_lines.append("resource \"aws_vpn_connection\" \"main\" {")
        terraform_lines.append("  vpn_gateway_id      = aws_vpn_gateway.main.id")
        terraform_lines.append("  customer_gateway_id = aws_customer_gateway.main.id")
        terraform_lines.append("  type                = \"ipsec.1\"")
        terraform_lines.append("  static_routes_only  = false  # Use BGP for dynamic routing\n")
        terraform_lines.append("  tags = {")
        terraform_lines.append(f"    Name        = \"{config['prefix']}-vpn\"")
        terraform_lines.append(f"    Environment = \"{config['environment']}\"")
        terraform_lines.append("    ManagedBy   = \"CARL\"")
        terraform_lines.append("  }")
        terraform_lines.append("}\n")

    # Direct Connect (if requested)
    if needs_direct_connect:
        terraform_lines.append("# Direct Connect Virtual Interface")
        terraform_lines.append("# NOTE: Direct Connect connection must be ordered through AWS Console")
        terraform_lines.append("# This creates the Virtual Interface once connection is active")
        terraform_lines.append("resource \"aws_dx_gateway\" \"main\" {")
        terraform_lines.append(f"  name            = \"{config['prefix']}-dxgw\"")
        terraform_lines.append("  amazon_side_asn = \"64512\"\n")
        terraform_lines.append("  tags = {")
        terraform_lines.append(f"    Name        = \"{config['prefix']}-dxgw\"")
        terraform_lines.append(f"    Environment = \"{config['environment']}\"")
        terraform_lines.append("    ManagedBy   = \"CARL\"")
        terraform_lines.append("  }")
        terraform_lines.append("}\n")

        terraform_lines.append("# TODO: Create private VIF after DX connection is active")
        terraform_lines.append("# resource \"aws_dx_private_virtual_interface\" \"main\" {")
        terraform_lines.append(f"#   connection_id    = \"dxcon-xxxxxxxx\"  # REPLACE with your DX connection ID")
        terraform_lines.append(f"#   name             = \"{config['prefix']}-vif\"")
        terraform_lines.append("#   vlan             = 1000")
        terraform_lines.append("#   address_family   = \"ipv4\"")
        terraform_lines.append("#   bgp_asn          = 65000")
        terraform_lines.append("#   dx_gateway_id    = aws_dx_gateway.main.id")
        terraform_lines.append("# }\n")

    # Transit Gateway (if requested)
    if needs_transit_gateway:
        terraform_lines.append("# Transit Gateway for inter-VPC connectivity")
        terraform_lines.append("resource \"aws_ec2_transit_gateway\" \"main\" {")
        terraform_lines.append("  description                     = \"Transit Gateway for multi-VPC connectivity\"")
        terraform_lines.append("  default_route_table_association = \"enable\"")
        terraform_lines.append("  default_route_table_propagation = \"enable\"")
        terraform_lines.append("  dns_support                     = \"enable\"")
        terraform_lines.append("  vpn_ecmp_support               = \"enable\"\n")
        terraform_lines.append("  tags = {")
        terraform_lines.append(f"    Name        = \"{config['prefix']}-tgw\"")
        terraform_lines.append(f"    Environment = \"{config['environment']}\"")
        terraform_lines.append("    ManagedBy   = \"CARL\"")
        terraform_lines.append("  }")
        terraform_lines.append("}\n")

        # Transit Gateway VPC attachment
        terraform_lines.append("# Attach VPC to Transit Gateway")
        terraform_lines.append("resource \"aws_ec2_transit_gateway_vpc_attachment\" \"main\" {")
        terraform_lines.append(f"  transit_gateway_id = aws_ec2_transit_gateway.main.id")
        terraform_lines.append(f"  vpc_id             = {vpc_ref}")
        terraform_lines.append("  subnet_ids         = [] # TODO: Add subnet IDs\n")
        terraform_lines.append("  tags = {")
        terraform_lines.append(f"    Name        = \"{config['prefix']}-tgw-attachment\"")
        terraform_lines.append(f"    Environment = \"{config['environment']}\"")
        terraform_lines.append("    ManagedBy   = \"CARL\"")
        terraform_lines.append("  }")
        terraform_lines.append("}\n")

    # Output
    terraform_lines.append("# Outputs")
    terraform_lines.append("output \"vpc_id\" {")
    terraform_lines.append(f"  value       = {vpc_ref}")
    terraform_lines.append("  description = \"VPC ID\"")
    terraform_lines.append("}\n")

    if config.get("use_transit_gateway"):
        terraform_lines.append("output \"transit_gateway_id\" {")
        terraform_lines.append("  value       = aws_ec2_transit_gateway.main.id")
        terraform_lines.append("  description = \"Transit Gateway ID\"")
        terraform_lines.append("}")

    return "\n".join(terraform_lines)


def handle_s3_config_submission(payload: dict) -> dict:
    """Handle S3 bucket configuration modal submission with validation."""
    import json as json_lib
    from utils.input_validation import validate_s3_bucket_name, sanitize_s3_bucket_name

    slack = get_slack_service()

    # Extract values from modal submission
    view = payload.get("view", {})
    values = view.get("state", {}).get("values", {})
    private_metadata = json_lib.loads(view.get("private_metadata", "{}"))

    channel_id = private_metadata.get("channel_id")
    blueprint_name = private_metadata.get("blueprint_name")

    # Extract input values
    bucket_name = values.get("bucket_name_block", {}).get("bucket_name_input", {}).get("value", "my-data-bucket").strip()

    # Validate inputs
    errors = {}

    # Validate bucket name
    name_valid, name_error = validate_s3_bucket_name(bucket_name)
    if not name_valid:
        # Try to sanitize and suggest
        sanitized = sanitize_s3_bucket_name(bucket_name)
        errors["bucket_name_block"] = f"{name_error}. Suggestion: '{sanitized}'"

    # If there are validation errors, return them to Slack
    if errors:
        return {
            "response_action": "errors",
            "errors": errors
        }

    # Sanitize the bucket name (in case it has minor issues)
    bucket_name = sanitize_s3_bucket_name(bucket_name)

    # Build configuration
    config = {
        "name": bucket_name
    }

    # Invoke async processing in background to avoid 3-second timeout
    user_id = payload.get("user", {}).get("id", "")
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json_lib.dumps({
                'action': 'process_s3_config_async',
                'channel_id': channel_id,
                'user_id': user_id,
                'blueprint_name': blueprint_name,
                'config': config
            })
        )
        logger.info("Invoked async S3 config processing")
    except Exception as e:
        logger.error(f"Failed to invoke async processing: {e}")
        # Fallback to synchronous if async fails
        try:
            slack.post_message(channel_id, text=f"✅ Configuration received! Generating {blueprint_name} with bucket name {bucket_name}...")
            handle_build_command(slack, channel_id, user_id, blueprint_name, config, trigger_id=None)
        except Exception as e2:
            logger.error(f"Error processing S3 config: {e2}")

    # Return 200 immediately to close modal (must be within 3 seconds)
    return {"statusCode": 200, "body": ""}


def handle_setup_submission(payload: dict) -> dict:
    """Handle setup wizard modal submission."""
    import json as json_lib
    from services.setup_service import SetupService

    slack = get_slack_service()
    setup = SetupService()

    # Extract values from modal submission
    view = payload.get("view", {})
    values = view.get("state", {}).get("values", {})
    private_metadata = json_lib.loads(view.get("private_metadata", "{}"))

    channel_id = private_metadata.get("channel_id")
    workspace_id = private_metadata.get("workspace_id")

    # Extract input values
    notification_channel = values.get("notification_channel_block", {}).get("notification_channel_input", {}).get("selected_channel")
    scan_schedule = values.get("scan_schedule_block", {}).get("scan_schedule_input", {}).get("selected_option", {}).get("value", "on_demand")
    auto_scan_options = values.get("auto_scan_block", {}).get("auto_scan_input", {}).get("selected_options", [])
    auto_scan = len(auto_scan_options) > 0

    # Validate
    errors = {}
    if not notification_channel:
        errors["notification_channel_block"] = "Please select a notification channel"

    if errors:
        return {
            "response_action": "errors",
            "errors": errors
        }

    # Save configuration
    config = {
        "notification_channel": notification_channel,
        "scan_schedule": scan_schedule,
        "scan_regions": ["us-east-1"],  # Default for now
        "auto_scan_on_deploy": auto_scan,
        "compliance_frameworks": ["soc2"],
        "evidence_collection": True,
        "evidence_retention_years": 7,
        "setup_complete": True,
        "setup_version": "1.0",
    }

    success = setup.save_workspace_config(workspace_id, config)

    if not success:
        slack.post_message(
            channel_id,
            text="❌ Failed to save configuration. Please try again or contact support."
        )
        return {"statusCode": 500, "body": "Failed to save config"}

    # Post success message
    slack.post_message(
        channel_id,
        text=f"""✅ *Setup Complete!*

*Configuration Summary:*
• Notification channel: <#{notification_channel}>
• Scan schedule: {scan_schedule}
• Auto-scan on deploy: {'✅ Enabled' if auto_scan else '❌ Disabled'}
• Compliance: SOC 2
• Evidence collection: ✅ Enabled

*Next Steps:*
1. Run /carl status` to see your compliance posture
2. Try /carl build networking/standard-vpc` to generate infrastructure
3. Use /carl ask <question>` for compliance help

*Useful Commands:*
• /carl help` - View all commands
• /carl settings` - View current configuration
• /carl setup reset` - Re-run setup wizard

Ready to help you build compliant infrastructure! 🚀"""
    )

    return {"statusCode": 200, "body": ""}


def handle_deploy_review(payload: dict, action: dict) -> dict:
    """DEPRECATED: Direct deployment removed - infrastructure changes now go through GitHub."""
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]
    slack.post_message(
        channel_id,
        text="⚠️ Direct deployment has been removed.\n\n"
             "All infrastructure changes now go through GitHub for proper review and approval.\n\n"
             "Use /carl build <blueprint>` to generate code and create a Pull Request."
    )
    return {"statusCode": 200, "body": ""}


def handle_deploy_confirm(payload: dict, action: dict) -> dict:
    """DEPRECATED: Direct deployment removed - infrastructure changes now go through GitHub."""
    return handle_deploy_review(payload, action)


def handle_deploy_cancel(payload: dict, action: dict) -> dict:
    """DEPRECATED: Direct deployment removed - infrastructure changes now go through GitHub."""
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]
    slack.post_message(channel_id, text="✅ Cancelled.")
    return {"statusCode": 200, "body": ""}


def handle_build_blueprint_button(payload: dict, action: dict) -> dict:
    """Handle 'Generate Code' button click from recommendations."""
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]
    user_id = payload["user"]["id"]
    trigger_id = payload.get("trigger_id")

    # Extract blueprint name from action_id (format: build_blueprint_<name>)
    action_id = action.get("action_id", "")
    blueprint_name = action_id.replace("build_blueprint_", "")

    # Call the build command handler
    return handle_build_command(slack, channel_id, user_id, blueprint_name, trigger_id=trigger_id)


def handle_intelligent_build(
    slack: SlackService, channel_id: str, user_id: str, requirement: str, trigger_id: str
) -> dict:
    """
    Intelligent build handler that scans AWS and asks context-aware questions.

    Instead of static predetermined questions, this:
    1. Scans AWS to see what exists
    2. Uses AI to decide what questions to ask
    3. Only asks relevant questions based on context
    """
    import json
    from datetime import datetime
    from services.aws_environment_scanner import AWSEnvironmentScanner
    from services.agent_core import Agent

    try:
        # Comprehensive AWS environment scan
        slack.post_message(channel_id, text="🔍 Performing deep scan of your AWS environment...")

        scanner = AWSEnvironmentScanner(region="us-east-1")
        scan_result = scanner.scan()

        # Get human-readable summary for AI context
        environment_summary = scan_result.to_context_summary()

        slack.post_message(channel_id, text=f"✅ Scan complete! Found: {len(scan_result.networking.vpcs)} VPCs, {len(scan_result.databases.rds_instances)} RDS instances, {len(scan_result.compute.ec2_instances)} EC2 instances")

        # Build context for AI agent with deep AWS knowledge
        context = f"""You are CARL's infrastructure build assistant with deep AWS architecture expertise.

USER'S REQUEST:
{requirement}

{environment_summary}

YOUR TASK:
Analyze the user's request and current AWS environment. Determine what information you need to build this infrastructure correctly.

YOUR AWS ARCHITECTURE KNOWLEDGE:
- Web apps typically need: VPC, subnets (public + private), load balancer, compute (EC2/ECS/Lambda), database
- SQL Server on AWS options: RDS SQL Server (managed), SQL Server on EC2 (self-managed)
- Redundancy requires: Multi-AZ, multiple subnets, load balancer, Auto Scaling
- Direct Connect/VPN redundancy: Use Transit Gateway with multiple connections or VPN as backup to Direct Connect
- If existing VPC has proper subnets (public + private across AZs), can reuse
- If no VPC or inadequate subnets, need to create new infrastructure

INTELLIGENT DECISION MAKING:
- Ask questions iteratively - each answer may lead to more questions
- Don't ask unnecessary questions if you can infer the answer from the scan
- Ask as many questions as needed to build correctly - NO arbitrary limits
- Be specific and context-aware - reference actual resources from the scan
- Stop asking when you have everything needed

CRITICAL OUTPUT FORMAT RULES:
You MUST ask ONE question at a time. Do NOT list multiple questions.

Each option MUST include a brief explanation (1-2 sentences) for IT generalists who may not know these terms.

If you need information, output EXACTLY this format:
Question: <your single specific question here>
Options:
1. <Option Name> - <What it is in plain English>. <When to use it>. <Approximate cost if relevant>.
2. <Option Name> - <What it is in plain English>. <When to use it>. <Approximate cost if relevant>.
3. <Option Name> - <What it is in plain English>. <When to use it>. <Approximate cost if relevant>.

Example of CORRECT format:
Question: What type of connectivity do you need to your on-premises environment?
Options:
1. AWS Direct Connect - Dedicated fiber connection from your datacenter to AWS. Provides consistent low latency and high bandwidth (1-100 Gbps). Best for mission-critical workloads requiring reliable performance. Cost: approx. $500-2000/month.
2. Site-to-Site VPN - Encrypted tunnel over the public internet. Quick to set up, lower cost. Best for smaller workloads or testing. Bandwidth up to 1.25 Gbps. Cost: approx. $36/month.
3. Both (hybrid redundancy) - Direct Connect as primary with VPN as backup. Best for critical workloads needing guaranteed uptime. Cost: combines both options.
4. Transit Gateway - Central hub connecting multiple VPNs or Direct Connect links. Best for complex multi-site networks with many connections. Cost: approx. $36/month + data processing fees.

IMPORTANT: NEVER use tilde (~) for "approximately" as it creates strikethrough in Slack. Always spell out "approx." or "approximately".

Example of WRONG format (DO NOT DO THIS):
Question: What type of connectivity...
Options: Direct Connect, VPN, Both
(Missing explanations - user won't understand what these mean!)

If you have everything needed:
READY: <explain what you'll build with specific details>
"""

        # Create agent to decide what questions to ask
        build_planner = Agent(
            tools=[],  # No tools needed for planning
            instructions=context
        )

        # Create session to track iterative Q&A
        from services.build_session_service import BuildSessionService

        session_service = BuildSessionService()
        session = session_service.create_session(
            user_id=user_id,
            channel_id=channel_id,
            requirement=requirement,
            environment_scan=scan_result.to_dict(),
            environment_summary=environment_summary
        )

        logger.info(f"Created build session {session.session_id}")

        # Get first question(s) from AI with progress indicator
        slack.post_message(channel_id, text="🤔 Analyzing requirements...")

        questions_response = build_planner.execute("Analyze the environment and user request. What information do you need to build this?")

        logger.info(f"Build planner response: {questions_response}")

        # Parse response
        if "READY:" in questions_response:
            # AI has everything it needs - proceed to generation
            ready_text = questions_response.split('READY:')[1].strip()
            slack.post_message(
                channel_id,
                text=f"✅ I have everything needed to generate your infrastructure!\n\n{ready_text}\n\nGenerating Terraform code..."
            )

            # TODO: Call infrastructure generation
            slack.post_message(channel_id, text="🚧 Infrastructure generation coming soon!")

        elif "Question:" in questions_response or "Question 1:" in questions_response:
            # AI needs information - parse and show question
            # Extract question and options with robust parsing
            import re

            question_text = None
            options = []

            # Try multiple parsing strategies

            # Strategy 1: Look for "Question:" or "Question 1:" etc.
            question_match = re.search(r'(?:Question\s*\d*\s*:)\s*(.+?)(?:\n|$)', questions_response, re.IGNORECASE)
            if question_match:
                question_text = question_match.group(1).strip()

            # Strategy 2: Look for "Options:" line - capture until newline
            options_match = re.search(r'Options:\s*(.+?)(?:\n|$)', questions_response, re.IGNORECASE)
            if options_match:
                options_text = options_match.group(1).strip()

                # Try parsing as numbered list first (1. option, 2. option, etc.)
                numbered_options = re.findall(r'\d+\.\s*(.+?)(?:,|\n|$)', options_text)
                if numbered_options and len(numbered_options) >= 2:
                    options = [opt.strip() for opt in numbered_options]
                else:
                    # Try parsing as comma-separated (most common format)
                    comma_separated = [opt.strip() for opt in options_text.split(',') if opt.strip()]
                    if comma_separated and len(comma_separated) >= 2:
                        options = comma_separated

            logger.info(f"Parsed question: {question_text}")
            logger.info(f"Parsed options: {options}")

            if question_text and options and len(options) >= 2:
                # Store the current question in session for reference
                session.conversation_history.append({
                    "question": question_text,
                    "answer": None,  # Will be filled when user responds
                    "timestamp": datetime.utcnow().isoformat()
                })
                session_service.table.put_item(Item=session.to_dynamodb_item())

                # Helper function to shorten button text
                def shorten_button_text(text: str, max_length: int = 40) -> str:
                    """Extract main part before parentheses or truncate intelligently."""
                    # Remove parenthetical explanations for button text
                    if '(' in text:
                        main_part = text.split('(')[0].strip()
                        if len(main_part) > 0:
                            return main_part[:max_length]
                    # Truncate if still too long
                    return text[:max_length] if len(text) > max_length else text

                # Build Slack blocks with buttons
                blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Question:*\n{question_text}"
                        }
                    },
                    {
                        "type": "actions",
                        "block_id": f"build_question_{session.session_id}",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": shorten_button_text(option)},
                                "value": json.dumps({"option": option, "question": question_text}),
                                "action_id": f"build_answer_{session.session_id}_{i}"
                            }
                            for i, option in enumerate(options[:5])  # Max 5 buttons
                        ]
                    }
                ]

                slack.post_message(channel_id, blocks=blocks)
                logger.info(f"Asked question in build session {session.session_id}")
            else:
                # Couldn't parse question format properly
                logger.warning(f"Failed to parse AI response. Question: {question_text}, Options: {options}")
                slack.post_message(
                    channel_id,
                    text=f"⚠️ I'm having trouble formatting my questions properly. Let me try rephrasing...\n\nRaw response:\n```{questions_response[:500]}``\n\nPlease describe your requirements in more detail and I'll help build your infrastructure."
                )
        else:
            # Unexpected format - no question found
            slack.post_message(
                channel_id,
                text=f"🤔 I analyzed your environment but couldn't determine what questions to ask.\n\nCould you provide more details about your requirements?\n\nWhat I found:\n```{questions_response[:500]}``"
            )

        return {"statusCode": 200, "body": ""}

    except Exception as e:
        logger.exception(f"Error in intelligent build: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Failed to analyze build requirements: {str(e)}"
        )
        return {"statusCode": 200, "body": ""}


def handle_build_answer_button(payload: dict, action: dict) -> dict:
    """
    Handle user's answer to an intelligent build question.

    This continues the iterative Q&A conversation until AI has enough info.
    """
    import json
    from datetime import datetime
    from services.build_session_service import BuildSessionService
    from services.aws_environment_scanner import AWSEnvironmentScan
    from services.agent_core import Agent

    slack = get_slack_service()
    channel_id = payload["channel"]["id"]
    user_id = payload["user"]["id"]

    # Parse action_id: build_answer_{session_id}_{index}
    action_id = action.get("action_id", "")
    parts = action_id.replace("build_answer_", "").split("_")
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]

    # Parse answer value (contains both the option and the question)
    answer_data = json.loads(action.get("value", "{}"))
    answer_option = answer_data.get("option", "")
    question_text = answer_data.get("question", "")

    logger.info(f"Build answer received: session={session_id}, answer={answer_option}")

    try:
        # Retrieve session
        session_service = BuildSessionService()
        session = session_service.get_session(session_id, user_id)

        if not session:
            slack.post_message(
                channel_id,
                text="❌ Session expired or not found. Please start over with the Build This button."
            )
            return {"statusCode": 200, "body": ""}

        # Update conversation history with the answer
        if session.conversation_history and session.conversation_history[-1].get("answer") is None:
            session.conversation_history[-1]["answer"] = answer_option

        # Acknowledge answer with progress indicator
        slack.post_message(
            channel_id,
            text=f"✓ Recorded: {answer_option}"
        )

        slack.post_message(
            channel_id,
            text="🤔 Analyzing your answer and determining next steps..."
        )

        # Build context for AI with conversation history
        conversation_summary = "\n".join([
            f"Q: {turn['question']}\nA: {turn.get('answer', 'pending')}"
            for turn in session.conversation_history
        ])

        # Use stored environment summary
        environment_summary = session.environment_summary

        context = f"""You are CARL's infrastructure build assistant with deep AWS architecture expertise.

USER'S ORIGINAL REQUEST:
{session.requirement}

{environment_summary}

CONVERSATION SO FAR:
{conversation_summary}

YOUR TASK:
Based on the user's answers, decide what to do next:
1. If you need more information → ask another question
2. If you have everything needed → output READY with build plan

AWS ARCHITECTURE KNOWLEDGE:
- Web apps need: VPC, subnets (public + private), load balancer, compute, database
- SQL Server options: RDS SQL Server (managed), SQL Server on EC2
- Redundancy: Multi-AZ, multiple subnets, load balancer, Auto Scaling
- Direct Connect/VPN redundancy: Use Transit Gateway with multiple connections or VPN as backup

CRITICAL OUTPUT FORMAT RULES:
You MUST ask ONE question at a time. Do NOT list multiple questions.

Each option MUST include a brief explanation (1-2 sentences) for IT generalists who may not know these terms.

If more info needed, output EXACTLY this format:
Question: <your single specific question here>
Options:
1. <Option Name> - <What it is in plain English>. <When to use it>. <Approximate cost if relevant>.
2. <Option Name> - <What it is in plain English>. <When to use it>. <Approximate cost if relevant>.
3. <Option Name> - <What it is in plain English>. <When to use it>. <Approximate cost if relevant>.

Example CORRECT format:
Question: What bandwidth do you need for the VPN connection?
Options:
1. Low (<100 Mbps) - Basic connectivity for file access and light traffic. Suitable for small offices or testing. Lowest cost.
2. Medium (100 Mbps - 1 Gbps) - Good for moderate traffic like multiple users, file transfers, and business applications. Balanced cost/performance.
3. High (>1 Gbps) - High-bandwidth connectivity for data-intensive operations, large file transfers, or many concurrent users. Higher cost.
4. Variable/burst - Starts low but can burst to higher speeds when needed. Good for unpredictable traffic patterns. Pay for what you use.

DO NOT use this format (missing explanations):
Options: Low, Medium, High, Variable
(Users won't understand what these mean!)

If ready to build:
READY: <detailed build plan with specific resources and configurations>
"""

        # Ask AI what's next
        build_planner = Agent(
            tools=[],
            instructions=context
        )

        next_response = build_planner.execute("Based on the conversation so far, what do you need next?")

        logger.info(f"AI next step response: {next_response}")

        # Parse AI response
        if "READY:" in next_response:
            # AI is ready to build - show modal for exact inputs
            ready_text = next_response.split('READY:')[1].strip()

            session_service.update_session_status(session_id, user_id, "ready_to_build")

            # Store the ready_text in session for later use
            session.conversation_history.append({
                "question": "BUILD_PLAN",
                "answer": ready_text,
                "timestamp": datetime.utcnow().isoformat()
            })
            session_service.table.put_item(Item=session.to_dynamodb_item())

            slack.post_message(
                channel_id,
                text=f"✅ I have everything I need to design your infrastructure!\n\n{ready_text[:500]}..."
            )

            # Open modal for exact configuration values
            # We need a trigger_id, so we'll respond with interactive message
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "📝 *Final Step: Configuration Details*\n\nI need a few exact values to generate your Terraform code."
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"open_config_modal_{session_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "⚙️ Enter Configuration"},
                            "action_id": f"open_build_config_modal_{session_id}",
                            "style": "primary"
                        }
                    ]
                }
            ]
            slack.post_message(channel_id, blocks=blocks)

            return {"statusCode": 200, "body": ""}

        # Keep the old generate code path as fallback
        if "READY_OLD:" in next_response:
            # Legacy path - generate immediately without modal
            ready_text = next_response.split('READY_OLD:')[1].strip()

            session_service.update_session_status(session_id, user_id, "ready_to_build")

            slack.post_message(
                channel_id,
                text=f"✅ I have everything needed!\n\n{ready_text}\n\n🏗️ Generating Terraform code..."
            )

            # Generate and push infrastructure code
            try:
                # Use AI to generate custom Terraform based on conversation
                prompt = f"""Generate production-ready Terraform code for this requirement:

USER'S REQUEST: {session.requirement}

BUILD PLAN:
{ready_text}

CONVERSATION ANSWERS:
{conversation_summary}

{environment_summary}

Generate complete Terraform code including:
- main.tf with all resources
- variables.tf for configurability
- outputs.tf for important values
- Proper resource dependencies
- Best practices (tags, encryption, Multi-AZ where needed)
"""

                # Generate code using AI
                bedrock = get_bedrock_service()
                terraform_code = bedrock.invoke_model(
                    prompt=prompt,
                    max_tokens=4096
                )

                # Upload to GitHub and notify
                # CodeUploader is imported at top of file (line 29)
                from services.github_service import GitHubService

                github = GitHubService()
                uploader = CodeUploader(github, slack)

                blueprint_name = f"intelligent-build/{session.requirement[:30].replace(' ', '-')}"

                result = uploader.upload_and_notify(
                    channel_id=channel_id,
                    user_id=user_id,
                    blueprint_name=blueprint_name,
                    terraform_code=terraform_code,
                    metadata={
                        "requirement": session.requirement,
                        "conversation": session.conversation_history,
                        "generated_at": datetime.utcnow().isoformat(),
                        "session_id": session_id
                    }
                )

                session_service.update_session_status(session_id, user_id, "completed")

                slack.post_message(
                    channel_id,
                    text=f"🎉 Infrastructure code generated!\n\nPull Request: {result.get('pr_url', 'N/A')}\n\nReview the code and merge when ready."
                )

            except Exception as e:
                logger.exception(f"Error generating/uploading infrastructure: {e}")
                slack.post_message(
                    channel_id,
                    text=f"❌ Error generating code: {str(e)}\n\nI can provide the build plan for manual implementation."
                )

        elif "Question:" in next_response or "Question 1:" in next_response:
            # AI has another question - use robust parsing
            import re

            question_text = None
            options = []

            # Parse question
            question_match = re.search(r'(?:Question\s*\d*\s*:)\s*(.+?)(?:\n|$)', next_response, re.IGNORECASE)
            if question_match:
                question_text = question_match.group(1).strip()

            # Parse options with multi-line descriptions
            # Look for numbered options (1. 2. 3. etc) with everything until next number or end
            numbered_options = re.findall(r'\d+\.\s*(.+?)(?=\n\d+\.|\n\n|$)', next_response, re.DOTALL)
            if numbered_options and len(numbered_options) >= 2:
                # Clean up each option (remove extra whitespace but keep descriptions)
                options = [' '.join(opt.strip().split()) for opt in numbered_options]
            else:
                # Fallback: Try single-line comma-separated format
                options_match = re.search(r'Options:\s*(.+?)(?:\n\n|$)', next_response, re.IGNORECASE | re.DOTALL)
                if options_match:
                    options_text = options_match.group(1).strip()
                    comma_separated = [opt.strip() for opt in options_text.split(',') if opt.strip()]
                    if comma_separated and len(comma_separated) >= 2:
                        options = comma_separated

            logger.info(f"Parsed next question: {question_text}")
            logger.info(f"Parsed {len(options)} options")

            if question_text and options and len(options) >= 2:
                # Add new question to conversation history
                session.conversation_history.append({
                    "question": question_text,
                    "answer": None,
                    "timestamp": datetime.utcnow().isoformat()
                })
                session_service.table.put_item(Item=session.to_dynamodb_item())

                # Helper function to extract short button text
                def extract_option_name(text: str) -> str:
                    """Extract short name for button (max 3 words or 25 chars)."""
                    # Remove markdown bold formatting
                    text = text.replace('**', '')

                    # Extract text before dash or parentheses (the option name)
                    if ' - ' in text:
                        text = text.split(' - ')[0].strip()
                    if '(' in text:
                        text = text.split('(')[0].strip()

                    # Take first 3 words max
                    words = text.split()
                    if len(words) > 3:
                        text = ' '.join(words[:3])

                    # Enforce 25 char max
                    if len(text) > 25:
                        text = text[:25].rsplit(' ', 1)[0]  # Cut at last space

                    return text.strip()

                # Build formatted options text with full descriptions (strip markdown bold)
                clean_options = [opt.replace('**', '') for opt in options]
                options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(clean_options)])

                # Show next question with full descriptions + buttons
                blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Question:*\n{question_text}\n\n*Options:*\n{options_text}"
                        }
                    },
                    {
                        "type": "actions",
                        "block_id": f"build_question_{session_id}_{len(session.conversation_history)}",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": extract_option_name(option)},
                                "value": json.dumps({"option": option, "question": question_text}),
                                "action_id": f"build_answer_{session_id}_{i}"
                            }
                            for i, option in enumerate(options[:5])
                        ]
                    }
                ]

                slack.post_message(channel_id, blocks=blocks)
            else:
                # Couldn't parse next question
                logger.warning(f"Failed to parse AI next question. Question: {question_text}, Options: {options}")
                slack.post_message(
                    channel_id,
                    text=f"⚠️ I'm having trouble formatting my next question. Let me provide the information I need:\n\n```{next_response[:500]}``\n\nPlease provide additional details and I'll continue building your infrastructure."
                )
        else:
            # Unexpected response - no question or READY found
            slack.post_message(
                channel_id,
                text=f"🤔 I'm analyzing your requirements but need clarification.\n\nWhat I found:\n```{next_response[:500]}``\n\nPlease provide more details about your requirements."
            )

        return {"statusCode": 200, "body": ""}

    except Exception as e:
        logger.exception(f"Error in build answer handler: {e}")

        # Check if this is a timeout
        error_msg = str(e).lower()
        is_timeout = "timeout" in error_msg or "timed out" in error_msg

        if is_timeout:
            slack.post_message(
                channel_id,
                text=(
                    "⏱️ The AI took too long to generate the next question.\n\n"
                    f"**What we know so far:**\n{len(session.conversation_history)} questions answered\n\n"
                    "**Options:**\n"
                    "• Reply with additional details and I'll continue\n"
                    "• Or use /carl build <blueprint>` with a standard blueprint\n\n"
                    "_Tip: For complex requirements, break them into smaller pieces_"
                )
            )
        else:
            slack.post_message(
                channel_id,
                text=f"❌ Error processing answer: {str(e)}\n\nPlease try again or start over."
            )
        return {"statusCode": 200, "body": ""}


def handle_architecture_build_button(payload: dict, action: dict) -> dict:
    """Handle 'Build This' button click from architecture recommendations."""
    import re
    from services.build_session_service import BuildSessionService

    slack = get_slack_service()
    channel_id = payload["channel"]["id"]
    user_id = payload["user"]["id"]
    trigger_id = payload.get("trigger_id")

    # Extract context from button value
    button_value = action.get("value", "")

    if button_value.startswith("rec_session:"):
        # New flow: Ask which option from recommendation to build

        session_id = button_value.replace("rec_session:", "")
        session_service = BuildSessionService()
        rec_session = session_service.get_session(session_id, user_id)

        if not rec_session:
            slack.post_message(channel_id, text="❌ Recommendation session expired. Please run /carl recommend` again.")
            return {"statusCode": 200, "body": ""}

        # Extract recommendation text
        recommendation = rec_session.environment_scan.get("recommendation", "")

        # Parse options from recommendation (look for "OPTION 1:", "OPTION 2:", etc.)
        options = []
        option_matches = re.findall(r'OPTION\s+(\d+):\s*([^\n]+)', recommendation, re.IGNORECASE)

        if option_matches:
            for num, title in option_matches:
                # Extract the detailed description for this option
                # Find text between this OPTION and the next OPTION or end
                pattern = rf'OPTION\s+{num}:.*?(?=OPTION\s+\d+:|My Recommendation:|$)'
                option_detail = re.search(pattern, recommendation, re.IGNORECASE | re.DOTALL)

                if option_detail:
                    detail_text = option_detail.group(0).strip()
                    # Clean up and shorten for button/display
                    options.append({
                        "number": num,
                        "title": title.strip(),
                        "detail": detail_text[:500]  # First 500 chars
                    })

        if options:
            # Ask which option to build
            options_text = "\n\n".join([
                f"*Option {opt['number']}: {opt['title']}*"
                for opt in options
            ])

            # Build button elements with conditional style
            button_elements = []
            for idx, opt in enumerate(options[:5]):  # Max 5 options
                button = {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"Option {opt['number']}"},
                    "value": f"build_option:{session_id}:{opt['number']}",
                    "action_id": f"build_chosen_option_{opt['number']}"
                }
                # Only add style for first button
                if idx == 0:
                    button["style"] = "primary"
                button_elements.append(button)

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Which option do you want to build?*\n\n{options_text}"
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"choose_option_{session_id}",
                    "elements": button_elements
                }
            ]

            slack.post_message(channel_id, blocks=blocks)
        else:
            # Couldn't parse options, fall back to generic build
            requirement = rec_session.requirement
            slack.post_message(channel_id, text=f"🏗️ Starting build for: {requirement}")

            # Proceed with intelligent build
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
                InvocationType='Event',
                Payload=json.dumps({
                    'action': 'process_intelligent_build',
                    'channel_id': channel_id,
                    'user_id': user_id,
                    'requirement': requirement,
                    'trigger_id': trigger_id
                })
            )

        return {"statusCode": 200, "body": ""}

    elif button_value.startswith("build_option:"):
        # User chose a specific option - start intelligent build for that option
        import json as json_module
        parts = button_value.split(":")
        if len(parts) < 3:
            slack.post_message(channel_id, text="❌ Invalid option selection")
            return {"statusCode": 200, "body": ""}

        session_id = parts[1]
        option_number = parts[2]

        from services.build_session_service import BuildSessionService
        session_service = BuildSessionService()
        rec_session = session_service.get_session(session_id, user_id)

        if not rec_session:
            slack.post_message(channel_id, text="❌ Session expired")
            return {"statusCode": 200, "body": ""}

        # Get the recommendation and extract chosen option details
        recommendation = rec_session.environment_scan.get("recommendation", "")
        pattern = rf'OPTION\s+{option_number}:.*?(?=OPTION\s+\d+:|My Recommendation:|$)'
        option_match = re.search(pattern, recommendation, re.IGNORECASE | re.DOTALL)

        if option_match:
            chosen_option_text = option_match.group(0).strip()
            requirement = f"{rec_session.requirement} - {chosen_option_text[:200]}"
        else:
            requirement = f"{rec_session.requirement} - Option {option_number}"

        # Open modal immediately (must be within 3 seconds to avoid trigger_id expiration)
        # Skip AWS environment scan - user will input VPC ID or CIDR directly

        try:
            modal_blocks = []

            # VPC Configuration - simplified to avoid scan delay
            modal_blocks.append({
                "type": "input",
                "block_id": "vpc_selection",
                "label": {"type": "plain_text", "text": "VPC Configuration"},
                "element": {
                    "type": "static_select",
                    "action_id": "vpc_select",
                    "initial_option": {"text": {"type": "plain_text", "text": "Create New VPC"}, "value": "create_new"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Use Existing VPC"}, "value": "existing"},
                        {"text": {"type": "plain_text", "text": "Create New VPC"}, "value": "create_new"}
                    ]
                }
            })

            # VPC ID or CIDR
            modal_blocks.append({
                "type": "input",
                "block_id": "vpc_cidr",
                "label": {"type": "plain_text", "text": "VPC ID or CIDR Block"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "vpc_cidr_input",
                    "placeholder": {"type": "plain_text", "text": "vpc-abc123 OR 10.0.0.0/16"}
                },
                "hint": {"type": "plain_text", "text": "Enter VPC ID (vpc-xxx) if using existing, or CIDR (10.0.0.0/16) if creating new"}
            })

            # Resource name prefix
            modal_blocks.append({
                "type": "input",
                "block_id": "resource_prefix",
                "label": {"type": "plain_text", "text": "Resource Name Prefix"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "prefix_input",
                    "initial_value": "carl",
                    "placeholder": {"type": "plain_text", "text": "my-app"}
                },
                "hint": {"type": "plain_text", "text": "Used in all resource names (lowercase, hyphens only)"}
            })

            # Environment
            modal_blocks.append({
                "type": "input",
                "block_id": "environment",
                "label": {"type": "plain_text", "text": "Environment"},
                "element": {
                    "type": "static_select",
                    "action_id": "env_select",
                    "initial_option": {"text": {"type": "plain_text", "text": "Production"}, "value": "prod"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Development"}, "value": "dev"},
                        {"text": {"type": "plain_text", "text": "Staging"}, "value": "staging"},
                        {"text": {"type": "plain_text", "text": "Production"}, "value": "prod"}
                    ]
                }
            })

            # Option-specific fields based on what they chose
            option_text = option_match.group(0).strip() if option_match else ""

            # If this involves connectivity, add those fields
            if any(kw in option_text.lower() for kw in ['connect', 'vpn', 'direct connect', 'transit']):
                modal_blocks.append({
                    "type": "input",
                    "block_id": "use_transit_gateway",
                    "label": {"type": "plain_text", "text": "Use Transit Gateway?"},
                    "element": {
                        "type": "static_select",
                        "action_id": "tgw_select",
                        "initial_option": {"text": {"type": "plain_text", "text": "No"}, "value": "no"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Yes (+$36/month)"}, "value": "yes"},
                            {"text": {"type": "plain_text", "text": "No"}, "value": "no"}
                        ]
                    },
                    "hint": {"type": "plain_text", "text": "Only needed for connecting multiple VPCs or complex routing"}
                })

            # Create modal view
            import json as json_module
            modal_view = {
                "type": "modal",
                "callback_id": f"build_config_submit:{session_id}:{option_number}",
                "private_metadata": json_module.dumps({"channel_id": channel_id}),
                "title": {"type": "plain_text", "text": "Configuration"},
                "submit": {"type": "plain_text", "text": "Generate"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": modal_blocks
            }

            # Open modal
            slack.client.views_open(
                trigger_id=trigger_id,
                view=modal_view
            )

        except Exception as e:
            logger.exception(f"Error scanning/opening modal: {e}")
            slack.post_message(channel_id, text=f"❌ Failed to scan environment or open form: {str(e)}")

        return {"statusCode": 200, "body": ""}

    elif button_value.startswith("build_context:"):
        # New intelligent build - extract what user asked for
        requirement = button_value.replace("build_context:", "")

        logger.info(f"Intelligent build requested for: {requirement}")

        # Invoke intelligent build agent asynchronously
        # This agent will:
        # 1. Scan AWS to understand current state (VPCs, subnets, etc.)
        # 2. Analyze the requirement context
        # 3. Ask only relevant questions intelligently
        # 4. Generate Terraform code
        slack.post_message(
            channel_id,
            text=f"🏗️ Analyzing your AWS environment and determining what's needed for: {requirement}\n\nThis may take a moment..."
        )

        try:
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
                InvocationType='Event',  # Async
                Payload=json.dumps({
                    'action': 'process_intelligent_build',
                    'channel_id': channel_id,
                    'user_id': user_id,
                    'requirement': requirement,
                    'trigger_id': trigger_id
                })
            )
        except Exception as e:
            logger.error(f"Failed to invoke intelligent build: {e}")
            slack.post_message(
                channel_id,
                text=f"❌ Failed to start build process: {str(e)}"
            )

        return {"statusCode": 200, "body": ""}

    elif button_value.startswith("build:"):
        # Legacy blueprint-based build
        blueprint_name = button_value.replace("build:", "")
        logger.info(f"Blueprint build button clicked: {blueprint_name}")
        return handle_build_command(slack, channel_id, user_id, blueprint_name, trigger_id=trigger_id)
    else:
        slack.post_message(channel_id, text="❌ Invalid build action")
        return {"statusCode": 200, "body": ""}


def handle_estimate_option_button(payload: dict, action: dict) -> dict:
    """Handle 'Detailed Estimate' button click from recommendations."""
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]

    # Extract option name from action_id (format: estimate_option_<name>)
    action_id = action.get("action_id", "")
    option_name = action_id.replace("estimate_option_", "")

    # Show helpful message
    slack.post_message(
        channel_id,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"💰 *Cost Estimate Details*\n\nFor a detailed cost breakdown of *{option_name}*, use the /carl estimate` command with your specific requirements.\n\n*Example:*\n/carl estimate {option_name.lower().replace(' ', '-')}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 The /carl estimate` command provides itemized cost breakdowns based on your specific configuration needs."
                    }
                ]
            }
        ]
    )

    return {"statusCode": 200, "body": ""}


def handle_estimate_command(
    slack: SlackService, channel_id: str, user_id: str, component: str
) -> dict:
    """Handle /carl estimate command - get cost estimates."""
    if not component:
        slack.post_message(
            channel_id,
            text="Please specify a component. Example: /carl estimate rds multi-az 100gb",
        )
        return {"statusCode": 200, "body": ""}

    estimator = get_cost_estimator()
    bedrock = get_bedrock_service()

    # Parse component and configuration from natural language
    prompt = f"""Parse this cost estimate request and return JSON with component_type and config.

Request: "{component}"

Component types: vpc, nat_gateway, network_firewall, waf, ec2, fargate, eks, alb, rds, aurora, s3, security_stack

Return JSON like: {{"component_type": "rds", "config": {{"instance_type": "db.t3.medium", "multi_az": true, "storage_gb": 100}}}}

Return ONLY valid JSON."""

    try:
        response = bedrock.invoke_model(prompt, max_tokens=200, temperature=0.1)
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(response[start:end])
            component_type = parsed.get("component_type", "ec2")
            config = parsed.get("config", {})
        else:
            component_type = "ec2"
            config = {}
    except Exception:
        component_type = "ec2"
        config = {}

    estimate = estimator.estimate_component(component_type, config)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Cost Estimate"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{estimate.component}*\n"
                        f"Monthly: *${estimate.monthly_min:.2f} - ${estimate.monthly_max:.2f}*\n"
                        f"Annual: *${estimate.monthly_min * 12:.2f} - ${estimate.monthly_max * 12:.2f}*",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Assumptions:*\n" + "\n".join([f"• {a}" for a in estimate.assumptions]),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Optimization Tips:*\n" + "\n".join([f"• {t}" for t in estimate.optimization_tips]),
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "_Estimates are approximate and based on us-east-1 pricing_"}
            ],
        },
    ]

    slack.post_message(channel_id, blocks=blocks)

    return {"statusCode": 200, "body": ""}


def handle_blueprints_command(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Handle /carl blueprints command - list available blueprints."""
    builder = get_infrastructure_builder()
    blueprints = builder.list_blueprints()

    # Group by category
    categories: dict[str, list] = {}
    for bp in blueprints:
        category = bp["name"].split("/")[0]
        if category not in categories:
            categories[category] = []
        categories[category].append(bp)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Available Infrastructure Blueprints"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Use /carl build <blueprint-name>` to generate Terraform code.",
            },
        },
        {"type": "divider"},
    ]

    for category, bps in categories.items():
        bp_list = "\n".join([f"• {bp['name']} - {bp['description']}" for bp in bps])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{category.title()}*\n{bp_list}",
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": "_All blueprints follow SOC 2 compliance best practices_"}
        ],
    })

    slack.post_message(channel_id, blocks=blocks)

    return {"statusCode": 200, "body": ""}


def handle_event(payload: dict) -> dict:
    """Handle Slack events (app_mention, message)."""
    event = payload.get("event", {})
    event_type = event.get("type", "")

    if event_type == "app_mention":
        return handle_app_mention(event)
    elif event_type == "message":
        # Ignore bot messages to prevent loops
        if event.get("bot_id"):
            return {"statusCode": 200, "body": "OK"}

        # Ignore system messages (channel_join, channel_leave, etc.)
        if event.get("subtype"):
            logger.debug(f"Ignoring message with subtype: {event.get('subtype')}")
            return {"statusCode": 200, "body": "OK"}

        # Only respond to direct messages (DMs), not channel messages
        # Channel IDs start with "C", DM IDs start with "D"
        channel = event.get("channel", "")
        channel_type = event.get("channel_type", "")

        # Only handle if it's a DM (channel_type is "im" or channel starts with "D")
        if channel_type == "im" or channel.startswith("D"):
            return handle_direct_message(event)

        # Ignore all other channel messages (user talking to others)
        logger.debug(f"Ignoring channel message in {channel}")
        return {"statusCode": 200, "body": "OK"}

    return {"statusCode": 200, "body": "OK"}


def handle_app_mention(event: dict) -> dict:
    """Handle @carl mentions."""
    channel = event.get("channel", "")
    text = event.get("text", "")
    user = event.get("user", "")

    # Remove the mention from the text
    import re
    question = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if question:
        slack = get_slack_service()
        return handle_ask_command(slack, channel, user, question)

    return {"statusCode": 200, "body": "OK"}


def handle_direct_message(event: dict) -> dict:
    """Handle direct messages to CARL."""
    channel = event.get("channel", "")
    text = event.get("text", "")
    user = event.get("user", "")

    if text:
        slack = get_slack_service()
        return handle_ask_command(slack, channel, user, text)

    return {"statusCode": 200, "body": "OK"}


def handle_interaction(payload: dict) -> dict:
    """Handle interactive components (buttons, modals)."""
    logger = get_logger(__name__)
    action_type = payload.get("type", "")

    if action_type == "view_submission":
        callback_id = payload.get("view", {}).get("callback_id", "")
        if callback_id == "blueprint_config_modal":
            return handle_blueprint_config_submission(payload)
        elif callback_id == "vpc_config_modal":
            return handle_vpc_config_submission(payload)
        elif callback_id == "s3_config_modal":
            return handle_s3_config_submission(payload)
        elif callback_id == "setup_modal":
            return handle_setup_submission(payload)
        elif callback_id.startswith("exception_request_modal_"):
            return handle_exception_request_modal_submission(payload)
        elif callback_id.startswith("accept_risk_modal_"):
            return handle_accept_risk_modal_submission(payload)
        elif callback_id.startswith("build_config_submit:"):
            return handle_build_config_submission(payload)
        elif callback_id.startswith("foundation_text_submit_"):
            return handle_foundation_text_submission(payload)
        elif callback_id.startswith("foundation_vpc_submit_"):
            return handle_foundation_vpc_submission(payload)
        elif callback_id.startswith("account_factory_email_"):
            return handle_account_factory_email_submission(payload)
        elif callback_id.startswith("account_factory_all_emails_submit_"):
            return handle_account_factory_all_emails_submission(payload)
        elif callback_id.startswith("account_factory_vpc_"):
            return handle_account_factory_vpc_submission(payload)

    if action_type == "block_actions":
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id", "")
            if action_id.startswith("finding_create_ticket_"):
                finding_id = action_id.replace("finding_create_ticket_", "")
                return handle_finding_create_ticket_button(payload, finding_id)
            elif action_id.startswith("finding_request_exception_"):
                finding_id = action_id.replace("finding_request_exception_", "")
                return handle_finding_request_exception_button(payload, finding_id)
            elif action_id.startswith("finding_accept_risk_"):
                finding_id = action_id.replace("finding_accept_risk_", "")
                return handle_finding_accept_risk_button(payload, finding_id)
            elif action_id.startswith("finding_ignore_"):
                finding_id = action_id.replace("finding_ignore_", "")
                return handle_finding_ignore_button(payload, finding_id)
            elif action_id.startswith("finding_details_"):
                finding_id = action_id.replace("finding_details_", "")
                return handle_finding_details(payload, finding_id)
            elif action_id.startswith("finding_show_fix_"):
                finding_id = action_id.replace("finding_show_fix_", "")
                return handle_finding_show_fix(payload, finding_id)
            elif action_id.startswith("approve_remediation_"):
                remediation_id = action_id.replace("approve_remediation_", "")
                return handle_remediation_approval(payload, remediation_id, True)
            elif action_id.startswith("deny_remediation_"):
                remediation_id = action_id.replace("deny_remediation_", "")
                return handle_remediation_approval(payload, remediation_id, False)
            elif action_id.startswith("foundation_select_framework_"):
                return handle_foundation_framework_selection(payload, action)
            elif action_id.startswith("account_factory_framework_"):
                return handle_account_factory_framework_selection(payload, action)
            elif action_id.startswith("account_factory_answer_"):
                return handle_account_factory_answer(payload, action)
            elif action_id.startswith("account_factory_all_emails_"):
                return handle_account_factory_all_emails_button(payload, action)
            elif action_id.startswith("account_factory_vpc_config_"):
                return handle_account_factory_vpc_config_button(payload, action)
            elif action_id.startswith("account_factory_accept_"):
                return handle_account_factory_accept(payload, action)
            elif action_id.startswith("foundation_select_"):
                # Handle dropdown select answers
                return handle_foundation_select_answer(payload, action)
            elif action_id.startswith("foundation_multiselect_submit_"):
                # Handle multi-select submit
                return handle_foundation_multiselect_submit(payload, action)
            elif action_id.startswith("foundation_multiselect_"):
                # Store multi-select state (doesn't submit yet)
                return {"statusCode": 200, "body": ""}
            elif action_id.startswith("foundation_text_modal_"):
                # Open modal for text/number input
                return handle_foundation_text_modal(payload, action)
            elif action_id.startswith("foundation_answer_"):
                return handle_foundation_answer(payload, action)
            elif action_id.startswith("foundation_vpc_config_"):
                return handle_foundation_vpc_config_button(payload, action)
            elif action_id.startswith("foundation_accept_"):
                return handle_foundation_accept(payload, action)
            elif action_id.startswith("foundation_change_"):
                return handle_foundation_change(payload, action)
            elif action_id.startswith("foundation_explain_"):
                return handle_foundation_explain(payload, action)
            elif action_id.startswith("foundation_compare_"):
                return handle_foundation_compare(payload, action)
            elif action_id == "feedback_positive" or action_id == "feedback_negative":
                return handle_learning_feedback(payload, action)
            elif action_id == "ask_deep_scan":
                return handle_ask_deep_scan(payload, action)
            elif action_id == "ask_full_report":
                return handle_ask_full_report(payload, action)
            elif action_id == "deploy_infrastructure":
                return handle_deploy_review(payload, action)
            elif action_id == "confirm_deploy":
                return handle_deploy_confirm(payload, action)
            elif action_id == "cancel_deploy":
                return handle_deploy_cancel(payload, action)
            elif action_id.startswith("build_blueprint_"):
                return handle_build_blueprint_button(payload, action)
            elif action_id.startswith("estimate_option_"):
                return handle_estimate_option_button(payload, action)
            elif action_id.startswith("architecture_build_"):
                return handle_architecture_build_button(payload, action)
            elif action_id.startswith("build_chosen_option_"):
                return handle_architecture_build_button(payload, action)
            elif action_id.startswith("build_answer_"):
                return handle_build_answer_button(payload, action)
            elif action_id.startswith("create_jira_ticket_"):
                return handle_create_jira_ticket_action(payload, action)
            elif action_id.startswith("drift_create_ticket_"):
                drift_id = action_id.replace("drift_create_ticket_", "")
                return handle_drift_create_ticket_button(payload, drift_id)
            elif action_id.startswith("drift_acknowledge_"):
                drift_id = action_id.replace("drift_acknowledge_", "")
                return handle_drift_acknowledge_button(payload, drift_id)
            elif action_id.startswith("drift_show_fix_"):
                drift_id = action_id.replace("drift_show_fix_", "")
                return handle_drift_show_fix_button(payload, drift_id)
            elif action_id.startswith("drift_suppress_"):
                drift_id = action_id.replace("drift_suppress_", "")
                return handle_drift_suppress_button(payload, drift_id)

    return {"statusCode": 200, "body": "OK"}


def handle_foundation_framework_selection(payload: dict, action: dict) -> dict:
    """Handle framework selection for foundation builder (NEW)."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    slack = get_slack_service()
    engine = get_decision_engine()

    # Parse framework selection
    action_id = action.get("action_id", "")
    framework_id = action_id.replace("foundation_select_framework_", "")

    # Remove existing message
    message_ts = payload.get("message", {}).get("ts", "")
    if message_ts:
        try:
            slack.client.chat_delete(channel=channel, ts=message_ts)
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

    if framework_id == "none":
        # Best practices mode (original 10-question flow)
        session = engine.create_session(user, channel)
        first_question, _ = engine.get_next_question(session)

        slack.post_message(
            channel,
            text=(
                f"*AWS Foundation Builder - Best Practices Mode*\n\n"
                f"Question 1/{len(engine.patterns)}: {first_question['question']}\n\n"
                f"_{first_question['description']}_"
            )
        )
        # Continue with original question flow...
        return {"statusCode": 200, "body": ""}

    # Framework mode: Load framework and perform gap analysis
    slack.post_message(
        channel,
        text=f"🔍 Loading {framework_id.upper()} framework and scanning your AWS environment..."
    )

    try:
        from services.framework_loader import get_framework_loader
        loader = get_framework_loader()
        framework = loader.load(framework_id)

        # Get AWS account ID and region
        import boto3
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        region = boto3.Session().region_name or "us-east-1"

        # Create framework session with gap analysis
        session, gap_analysis = engine.create_framework_session(
            user,
            channel,
            framework_id,
            account_id,
            region
        )

        # Show gap analysis results with detailed service list
        from services.framework_gap_analyzer import GapStatus

        total_services = gap_analysis.total_services

        # Build service lists by status
        compliant_services = [g.service for g in gap_analysis.gaps if g.status == GapStatus.COMPLIANT]
        missing_services = [g.service for g in gap_analysis.gaps if g.status == GapStatus.MISSING]
        misconfigured_services = [g.service for g in gap_analysis.gaps if g.status == GapStatus.MISCONFIGURED]

        # Build detailed explanation
        explanation = f"*{framework.name} Gap Analysis Complete*\n\n"
        explanation += f"Scanned *{total_services} required services* for {framework.name} compliance:\n\n"

        # Compliant services
        if compliant_services:
            explanation += f"✅ *Compliant* ({len(compliant_services)}):\n"
            for svc in compliant_services:
                explanation += f"   • {svc}\n"

        # Missing services
        if missing_services:
            explanation += f"\n❌ *Missing* ({len(missing_services)} - not deployed):\n"
            for svc in missing_services[:5]:  # Show first 5
                explanation += f"   • {svc}\n"
            if len(missing_services) > 5:
                explanation += f"   • ... and {len(missing_services) - 5} more\n"

        # Misconfigured services
        if misconfigured_services:
            explanation += f"\n⚠️ *Misconfigured* ({len(misconfigured_services)} - needs adjustment):\n"
            for svc in misconfigured_services[:5]:  # Show first 5
                explanation += f"   • {svc}\n"
            if len(misconfigured_services) > 5:
                explanation += f"   • ... and {len(misconfigured_services) - 5} more\n"

        explanation += f"\n_Next: I'll ask you {len(framework.questions)} configuration questions, then generate Terraform code to fix all gaps._"

        slack.post_message(channel, text=explanation)

        # Start asking framework questions
        first_question, _ = engine.get_next_question(session)
        if first_question:
            question_num = 1
            total_questions = len(framework.questions)

            # Build Slack blocks based on question type
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Question {question_num}/{total_questions}:* {first_question['question']}\n\n_{first_question['description']}_"
                    }
                }
            ]

            # Add interactive elements based on input_type
            if first_question.get('input_type') == 'select' and first_question.get('options'):
                # Render as buttons (max 5 options) or dropdown (more than 5)
                options = first_question['options']
                if len(options) <= 5:
                    # Use buttons for 5 or fewer options
                    button_elements = []
                    for option in options:
                        button_elements.append({
                            "type": "button",
                            "text": {"type": "plain_text", "text": option['label'][:75]},
                            "action_id": f"foundation_answer_{session.session_id}_{first_question['id']}_{option['value']}",
                            "value": option['value']
                        })

                    blocks.append({
                        "type": "actions",
                        "elements": button_elements
                    })
                else:
                    # Use static select for more than 5 options
                    select_options = [
                        {
                            "text": {"type": "plain_text", "text": opt['label'][:75]},
                            "value": opt['value']
                        }
                        for opt in options
                    ]
                    blocks.append({
                        "type": "actions",
                        "elements": [{
                            "type": "static_select",
                            "action_id": f"foundation_select_{session.session_id}_{first_question['id']}",
                            "placeholder": {"type": "plain_text", "text": "Select an option"},
                            "options": select_options
                        }]
                    })

            elif first_question.get('input_type') == 'multi_select' and first_question.get('options'):
                # Use checkboxes for multi-select
                checkbox_options = [
                    {
                        "text": {"type": "plain_text", "text": opt['label'][:75]},
                        "value": opt['value']
                    }
                    for opt in first_question['options']
                ]
                blocks.append({
                    "type": "actions",
                    "elements": [{
                        "type": "checkboxes",
                        "action_id": f"foundation_multiselect_{session.session_id}_{first_question['id']}",
                        "options": checkbox_options
                    }]
                })
                # Add submit button for multi-select
                blocks.append({
                    "type": "actions",
                    "elements": [{
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Submit"},
                        "action_id": f"foundation_multiselect_submit_{session.session_id}_{first_question['id']}",
                        "style": "primary"
                    }]
                })

            elif first_question.get('input_type') in ['text', 'number']:
                # For text/number, show a button to open modal
                blocks.append({
                    "type": "actions",
                    "elements": [{
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Enter Answer"},
                        "action_id": f"foundation_text_modal_{session.session_id}_{first_question['id']}",
                        "style": "primary"
                    }]
                })

            slack.post_message(channel, text=first_question['question'], blocks=blocks)

    except Exception as e:
        logger.error(f"Framework selection failed: {e}", exc_info=True)
        slack.post_message(
            channel,
            text=f"❌ Error loading framework: {str(e)}\n\nPlease try again or contact support."
        )

    return {"statusCode": 200, "body": ""}


def handle_foundation_answer(payload: dict, action: dict) -> dict:
    """Handle foundation builder question answers."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    # Parse action_id: foundation_answer_{session_id}_{question_id}_{value}
    action_id = action.get("action_id", "")
    parts = action_id.replace("foundation_answer_", "").split("_", 2)
    if len(parts) < 3:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    question_id = parts[1]
    answer_value = parts[2]

    engine = get_decision_engine()
    session = engine.get_session(session_id)

    if not session:
        slack = get_slack_service()
        slack.post_message(channel, text="Session expired. Please start a new foundation session.")
        return {"statusCode": 200, "body": ""}

    # Process the answer
    result = engine.process_answer(session, question_id, answer_value)
    slack = get_slack_service()

    if result["action"] == "ask_question":
        # Show next question
        question = result["question"]
        progress = result["progress"]

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✓ Recorded: *{answer_value}*",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question {progress}:* {question['question']}\n\n_{question.get('description', '')}_",
                },
            },
        ]

        # Add interactive elements based on question type
        input_type = question.get('input_type', 'select')
        options = question.get('options', [])

        if input_type == 'select' and options:
            # Use buttons for select questions with options
            elements = []
            for opt in options:
                elements.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": opt["label"][:75]},
                    "value": opt["value"],
                    "action_id": f"foundation_answer_{session_id}_{question['id']}_{opt['value']}",
                })
            blocks.append({
                "type": "actions",
                "elements": elements[:5],
            })
            if len(elements) > 5:
                blocks.append({
                    "type": "actions",
                    "elements": elements[5:],
                })

        elif input_type == 'multi_select' and options:
            # Use checkboxes for multi-select questions
            checkbox_options = [
                {"text": {"type": "plain_text", "text": opt['label'][:75]}, "value": opt['value']}
                for opt in options
            ]
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "checkboxes",
                    "action_id": f"foundation_multiselect_{session_id}_{question['id']}",
                    "options": checkbox_options
                }]
            })
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Submit"},
                    "action_id": f"foundation_multiselect_submit_{session_id}_{question['id']}",
                    "style": "primary"
                }]
            })

        elif input_type in ['text', 'number']:
            # Use button to open modal for text/number input
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Enter Answer"},
                    "action_id": f"foundation_text_modal_{session_id}_{question['id']}",
                    "style": "primary"
                }]
            })

        slack.post_message(channel, blocks=blocks)

    elif result["action"] == "show_recommendations":
        # Show recommendations
        message = engine.format_recommendations_message(session)

        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Generate Terraform Code"},
                        "style": "primary",
                        "action_id": f"foundation_accept_{session_id}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Cancel"},
                        "action_id": f"foundation_cancel_{session_id}",
                    },
                ],
            },
        ]

        slack.post_message(channel, blocks=blocks)

    return {"statusCode": 200, "body": ""}


def handle_foundation_select_answer(payload: dict, action: dict) -> dict:
    """Handle dropdown select answer (foundation_select_)."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    # Parse action_id: foundation_select_{session_id}_{question_id}
    action_id = action.get("action_id", "")
    parts = action_id.replace("foundation_select_", "").split("_", 1)
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    question_id = parts[1]

    # Get selected value from static_select
    selected_option = action.get("selected_option", {})
    answer_value = selected_option.get("value", "")

    if not answer_value:
        return {"statusCode": 200, "body": "No value selected"}

    # Process the answer (same as button answer)
    engine = get_decision_engine()
    session = engine.get_session(session_id)

    if not session:
        slack = get_slack_service()
        slack.post_message(channel, text="Session expired. Please start a new foundation session.")
        return {"statusCode": 200, "body": ""}

    result = engine.process_answer(session, question_id, answer_value)
    slack = get_slack_service()

    # Show next question or recommendations (same logic as handle_foundation_answer)
    _show_foundation_next_step(slack, channel, session_id, result)

    return {"statusCode": 200, "body": ""}


def handle_foundation_multiselect_submit(payload: dict, action: dict) -> dict:
    """Handle multi-select checkbox submission (foundation_multiselect_submit_)."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    # Parse action_id: foundation_multiselect_submit_{session_id}_{question_id}
    action_id = action.get("action_id", "")
    parts = action_id.replace("foundation_multiselect_submit_", "").split("_", 1)
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    question_id = parts[1]

    # Find the checkboxes action in the message to get selected values
    # Look through the message blocks for the checkbox component
    message_blocks = payload.get("message", {}).get("blocks", [])
    selected_values = []

    for block in message_blocks:
        if block.get("type") == "actions":
            for element in block.get("elements", []):
                if element.get("action_id", "").startswith(f"foundation_multiselect_{session_id}_{question_id}"):
                    selected_values = [opt.get("value") for opt in element.get("selected_options", [])]
                    break

    # Join multiple values with commas
    answer_value = ",".join(selected_values) if selected_values else ""

    engine = get_decision_engine()
    session = engine.get_session(session_id)

    if not session:
        slack = get_slack_service()
        slack.post_message(channel, text="Session expired. Please start a new foundation session.")
        return {"statusCode": 200, "body": ""}

    result = engine.process_answer(session, question_id, answer_value)
    slack = get_slack_service()

    # Show next question or recommendations
    _show_foundation_next_step(slack, channel, session_id, result)

    return {"statusCode": 200, "body": ""}


def handle_foundation_text_modal(payload: dict, action: dict) -> dict:
    """Open modal for text/number input (foundation_text_modal_)."""
    trigger_id = payload.get("trigger_id", "")

    # Parse action_id: foundation_text_modal_{session_id}_{question_id}
    action_id = action.get("action_id", "")
    parts = action_id.replace("foundation_text_modal_", "").split("_", 1)
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    question_id = parts[1]

    # Get the question details
    engine = get_decision_engine()
    session = engine.get_session(session_id)

    if not session:
        return {"statusCode": 200, "body": "Session expired"}

    # Find the question - check framework mode first, then pattern mode
    question = None
    if session.framework_mode and session.framework:
        # Framework mode - look up in framework questions
        question = session.framework.get_question_by_id(question_id)
    else:
        # Pattern mode - look up in REQUIREMENT_QUESTIONS
        from types import SimpleNamespace
        from services.foundation.decision_engine import REQUIREMENT_QUESTIONS
        for q in REQUIREMENT_QUESTIONS:
            if q.get('id') == question_id:
                question = SimpleNamespace(**q)  # Convert dict to object-like
                break

    if not question:
        return {"statusCode": 200, "body": "Question not found"}

    # Create modal
    slack = get_slack_service()
    modal_view = {
        "type": "modal",
        "callback_id": f"foundation_text_submit_{session_id}_{question_id}",
        "title": {"type": "plain_text", "text": "Answer Question"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{question.question}*\n\n_{question.description}_"}
            },
            {
                "type": "input",
                "block_id": "answer_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "answer_value",
                    "placeholder": {"type": "plain_text", "text": str(question.default) if question.default else "Enter your answer"},
                },
                "label": {"type": "plain_text", "text": "Answer"}
            }
        ]
    }

    # Open modal
    slack.client.views_open(trigger_id=trigger_id, view=modal_view)

    return {"statusCode": 200, "body": ""}


def _show_foundation_next_step(slack, channel: str, session_id: str, result: dict):
    """Helper to show next question or recommendations after answer."""
    if result["action"] == "ask_question":
        # Show next question
        question = result["question"]
        progress = result["progress"]

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✓ Answer recorded",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question {progress}:* {question['question']}\n\n_{question.get('description', '')}_",
                },
            },
        ]

        # Add interactive elements based on question type
        if question.get('input_type') == 'select' and question.get('options'):
            options = question['options']
            if len(options) <= 5:
                button_elements = []
                for option in options:
                    button_elements.append({
                        "type": "button",
                        "text": {"type": "plain_text", "text": option['label'][:75]},
                        "action_id": f"foundation_answer_{session_id}_{question['id']}_{option['value']}",
                        "value": option['value']
                    })
                blocks.append({"type": "actions", "elements": button_elements})
            else:
                select_options = [
                    {"text": {"type": "plain_text", "text": opt['label'][:75]}, "value": opt['value']}
                    for opt in options
                ]
                blocks.append({
                    "type": "actions",
                    "elements": [{
                        "type": "static_select",
                        "action_id": f"foundation_select_{session_id}_{question['id']}",
                        "placeholder": {"type": "plain_text", "text": "Select an option"},
                        "options": select_options
                    }]
                })

        elif question.get('input_type') == 'multi_select' and question.get('options'):
            checkbox_options = [
                {"text": {"type": "plain_text", "text": opt['label'][:75]}, "value": opt['value']}
                for opt in question['options']
            ]
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "checkboxes",
                    "action_id": f"foundation_multiselect_{session_id}_{question['id']}",
                    "options": checkbox_options
                }]
            })
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Submit"},
                    "action_id": f"foundation_multiselect_submit_{session_id}_{question['id']}",
                    "style": "primary"
                }]
            })

        elif question.get('input_type') in ['text', 'number']:
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Enter Answer"},
                    "action_id": f"foundation_text_modal_{session_id}_{question['id']}",
                    "style": "primary"
                }]
            })

        slack.post_message(channel, blocks=blocks, text=question['question'])

    elif result["action"] == "show_recommendations":
        # Show recommendations
        engine = get_decision_engine()
        session = engine.get_session(session_id)
        message = engine.format_recommendations_message(session)

        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✓ Generate Terraform"},
                        "action_id": f"foundation_accept_{session_id}",
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Start Over"},
                        "action_id": f"foundation_change_{session_id}",
                    },
                ],
            },
        ]

        slack.post_message(channel, blocks=blocks, text="Recommendations ready")


def handle_foundation_text_submission(payload: dict) -> dict:
    """Handle modal submission for text/number input."""
    callback_id = payload.get("view", {}).get("callback_id", "")
    parts = callback_id.replace("foundation_text_submit_", "").split("_", 1)
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid callback"}

    session_id = parts[0]
    question_id = parts[1]

    # Get the answer value from modal
    view_values = payload.get("view", {}).get("state", {}).get("values", {})
    answer_value = ""

    for block_id, block_value in view_values.items():
        if "answer_value" in block_value:
            answer_value = block_value["answer_value"].get("value", "")
            break

    if not answer_value:
        return {"statusCode": 200, "body": "No answer provided"}

    # Get channel from private_metadata or user info
    user_id = payload.get("user", {}).get("id", "")

    # Process the answer
    engine = get_decision_engine()
    session = engine.get_session(session_id)
    slack = get_slack_service()

    if not session:
        # Can't send message directly from modal, user needs to retry
        return {"statusCode": 200, "body": "Session expired"}

    # Get channel from session
    channel = session.channel_id

    # Special handling for vpc_count - trigger VPC config modal flow
    if question_id == "vpc_count":
        try:
            vpc_count = int(answer_value)
            if vpc_count < 1:
                vpc_count = 1
            elif vpc_count > 10:
                vpc_count = 10

            # Store VPC count and initialize VPC list in session
            session.requirements["vpc_count"] = vpc_count
            session.requirements["vpcs"] = []
            session.requirements["vpc_config_index"] = 0
            engine._save_session_to_dynamodb(session)

            # Post button to open VPC config modal (can't open modal directly from view_submission)
            slack.post_message(
                channel,
                text=f"✓ Configuring {vpc_count} VPC(s). Click below to set up each VPC.",
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"✓ Configuring *{vpc_count} VPC(s)*. Click below to set up each one."}
                    },
                    {
                        "type": "actions",
                        "elements": [{
                            "type": "button",
                            "text": {"type": "plain_text", "text": f"Configure VPC 1/{vpc_count}"},
                            "action_id": f"foundation_vpc_config_{session_id}_0",
                            "style": "primary"
                        }]
                    }
                ]
            )
            return {"statusCode": 200, "body": ""}
        except ValueError:
            slack.post_message(channel, text="❌ Please enter a valid number for VPC count.")
            return {"statusCode": 200, "body": ""}

    result = engine.process_answer(session, question_id, answer_value)

    # Show next question or recommendations in the channel
    _show_foundation_next_step(slack, channel, session_id, result)

    return {"statusCode": 200, "body": ""}


def _show_foundation_vpc_modal(slack, trigger_id: str, session_id: str, vpc_num: int, total_vpcs: int):
    """Show modal to configure a single VPC in foundation flow."""
    import json as json_lib

    modal = {
        "type": "modal",
        "callback_id": f"foundation_vpc_submit_{session_id}_{vpc_num - 1}",
        "private_metadata": json_lib.dumps({
            "session_id": session_id,
            "vpc_index": vpc_num - 1,
            "total_vpcs": total_vpcs
        }),
        "title": {"type": "plain_text", "text": f"Configure VPC {vpc_num}/{total_vpcs}"},
        "submit": {"type": "plain_text", "text": "Save VPC"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "vpc_cidr_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "vpc_cidr_input",
                    "placeholder": {"type": "plain_text", "text": "10.0.0.0/16"},
                    "initial_value": f"10.{vpc_num - 1}.0.0/16"
                },
                "label": {"type": "plain_text", "text": "VPC CIDR Block"},
                "hint": {"type": "plain_text", "text": "e.g., 10.0.0.0/16 or 172.16.0.0/16"}
            },
            {
                "type": "input",
                "block_id": "vpc_name_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "vpc_name_input",
                    "placeholder": {"type": "plain_text", "text": "main"},
                    "initial_value": f"vpc-{vpc_num}" if vpc_num > 1 else "main"
                },
                "label": {"type": "plain_text", "text": "VPC Name"},
                "hint": {"type": "plain_text", "text": "Used for resource naming and tags"}
            },
            {
                "type": "input",
                "block_id": "vpc_environment_block",
                "element": {
                    "type": "static_select",
                    "action_id": "vpc_environment_input",
                    "placeholder": {"type": "plain_text", "text": "Select environment"},
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "Production"},
                        "value": "production"
                    },
                    "options": [
                        {"text": {"type": "plain_text", "text": "Production"}, "value": "production"},
                        {"text": {"type": "plain_text", "text": "Staging"}, "value": "staging"},
                        {"text": {"type": "plain_text", "text": "Development"}, "value": "development"},
                        {"text": {"type": "plain_text", "text": "Shared Services"}, "value": "shared"}
                    ]
                },
                "label": {"type": "plain_text", "text": "Environment"}
            }
        ]
    }

    slack.client.views_open(trigger_id=trigger_id, view=modal)


def handle_foundation_vpc_config_button(payload: dict, action: dict) -> dict:
    """Handle button click to open VPC config modal."""
    logger = get_logger(__name__)

    try:
        trigger_id = payload.get("trigger_id", "")
        action_id = action.get("action_id", "")

        logger.info(f"VPC config button clicked: action_id={action_id}")

        # Parse: foundation_vpc_config_{session_id}_{vpc_index}
        parts = action_id.replace("foundation_vpc_config_", "").rsplit("_", 1)
        if len(parts) < 2:
            logger.error(f"Invalid action_id format: {action_id}")
            return {"statusCode": 200, "body": "Invalid action"}

        session_id = parts[0]
        vpc_index = int(parts[1])

        logger.info(f"Parsed session_id={session_id}, vpc_index={vpc_index}")

        engine = get_decision_engine()
        session = engine.get_session(session_id)

        if not session:
            logger.error(f"Session not found: {session_id}")
            # Try to notify user via channel from payload
            try:
                channel = payload.get("channel", {}).get("id")
                if channel:
                    slack = get_slack_service()
                    slack.post_message(channel, text="❌ Session expired. Please run `/carl foundation start` again.")
            except Exception:
                pass
            return {"statusCode": 200, "body": "Session expired"}

        total_vpcs = session.requirements.get("vpc_count", 1)
        slack = get_slack_service()

        logger.info(f"Opening VPC modal: vpc_index={vpc_index + 1}, total_vpcs={total_vpcs}")

        _show_foundation_vpc_modal(slack, trigger_id, session_id, vpc_index + 1, total_vpcs)

        return {"statusCode": 200, "body": ""}

    except Exception as e:
        logger.error(f"Error in handle_foundation_vpc_config_button: {e}", exc_info=True)
        # Return 200 to acknowledge the action, even on error
        return {"statusCode": 200, "body": str(e)}


def handle_foundation_vpc_submission(payload: dict) -> dict:
    """Handle VPC config modal submission in foundation flow."""
    import json as json_lib

    callback_id = payload.get("view", {}).get("callback_id", "")
    private_metadata = payload.get("view", {}).get("private_metadata", "{}")

    try:
        metadata = json_lib.loads(private_metadata)
    except:
        metadata = {}

    session_id = metadata.get("session_id", "")
    vpc_index = metadata.get("vpc_index", 0)
    total_vpcs = metadata.get("total_vpcs", 1)

    engine = get_decision_engine()
    session = engine.get_session(session_id)
    slack = get_slack_service()

    if not session:
        return {"statusCode": 200, "body": "Session expired"}

    channel = session.channel_id

    # Extract VPC config from modal
    view_values = payload.get("view", {}).get("state", {}).get("values", {})
    vpc_cidr = view_values.get("vpc_cidr_block", {}).get("vpc_cidr_input", {}).get("value", "10.0.0.0/16")
    vpc_name = view_values.get("vpc_name_block", {}).get("vpc_name_input", {}).get("value", "main")
    vpc_env_data = view_values.get("vpc_environment_block", {}).get("vpc_environment_input", {}).get("selected_option", {})
    vpc_environment = vpc_env_data.get("value", "production") if vpc_env_data else "production"

    # Store VPC config
    vpc_config = {
        "cidr": vpc_cidr,
        "name": vpc_name,
        "environment": vpc_environment
    }

    if "vpcs" not in session.requirements:
        session.requirements["vpcs"] = []

    # Add or update VPC at this index
    while len(session.requirements["vpcs"]) <= vpc_index:
        session.requirements["vpcs"].append({})
    session.requirements["vpcs"][vpc_index] = vpc_config

    engine._save_session_to_dynamodb(session)

    # Check if more VPCs to configure
    next_index = vpc_index + 1
    if next_index < total_vpcs:
        slack.post_message(
            channel,
            text=f"✓ VPC {vpc_index + 1} configured: *{vpc_name}* ({vpc_cidr})\n\nNext: Configure VPC {next_index + 1}/{total_vpcs}",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"✓ VPC {vpc_index + 1} configured: *{vpc_name}* ({vpc_cidr}, {vpc_environment})"}
                },
                {
                    "type": "actions",
                    "elements": [{
                        "type": "button",
                        "text": {"type": "plain_text", "text": f"Configure VPC {next_index + 1}/{total_vpcs}"},
                        "action_id": f"foundation_vpc_config_{session_id}_{next_index}",
                        "style": "primary"
                    }]
                }
            ]
        )
    else:
        # All VPCs configured - generate recommendations and show button
        vpc_summary = "\n".join([
            f"• *{v['name']}*: {v['cidr']} ({v['environment']})"
            for v in session.requirements["vpcs"]
        ])

        # Mark session as complete and generate recommendations
        session.current_phase = "decisions"
        session.state = SessionState.REVIEWING_DECISIONS
        engine._generate_recommendations(session)
        engine._save_session_to_dynamodb(session)

        # Format recommendations message
        message = engine.format_recommendations_message(session)

        # Show summary with Generate Terraform button
        slack.post_message(
            channel,
            text=f"✓ All {total_vpcs} VPC(s) configured!",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"✓ *All {total_vpcs} VPC(s) configured!*\n\n{vpc_summary}"}
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                },
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✓ Generate & Push to GitHub"},
                            "action_id": f"foundation_accept_{session_id}",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Start Over"},
                            "action_id": f"foundation_restart_{session_id}"
                        }
                    ]
                }
            ]
        )

    return {"statusCode": 200, "body": ""}


def handle_foundation_accept(payload: dict, action: dict) -> dict:
    """Handle acceptance of foundation recommendations - trigger async generation."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    action_id = action.get("action_id", "")
    session_id = action_id.replace("foundation_accept_", "")

    engine = get_decision_engine()
    session = engine.get_session(session_id)
    slack = get_slack_service()

    if not session:
        slack.post_message(channel, text="Session expired.")
        return {"statusCode": 200, "body": ""}

    # Post acknowledgement immediately
    slack.post_message(channel, text="🔄 Starting Terraform generation...")

    # Invoke Lambda asynchronously to do the actual work
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async
            Payload=json.dumps({
                'action': 'process_foundation_generate',
                'channel_id': channel,
                'user_id': user,
                'session_id': session_id
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async foundation generation: {e}")
        slack.post_message(channel, text=f"❌ Failed to start generation: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_foundation_change(payload: dict, action: dict) -> dict:
    """Handle request to change a foundation decision."""
    channel = payload.get("channel", {}).get("id", "")
    slack = get_slack_service()

    # Parse action_id: foundation_change_{session_id}_{decision_index}
    action_id = action.get("action_id", "")
    parts = action_id.replace("foundation_change_", "").split("_")
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    decision_index = int(parts[1])

    engine = get_decision_engine()
    session = engine.get_session(session_id)

    if not session or decision_index >= len(session.decisions):
        slack.post_message(channel, text="Session expired or invalid decision.")
        return {"statusCode": 200, "body": ""}

    decision = session.decisions[decision_index]
    alternatives_message = engine.format_alternatives(decision)

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": alternatives_message},
        },
    ]

    # Add selection buttons for alternatives
    elements = []
    for i, opt in enumerate(decision.decision.options):
        elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": opt.name[:75]},
            "action_id": f"foundation_select_{session_id}_{decision_index}_{i}",
        })

    blocks.append({
        "type": "actions",
        "elements": elements[:5],
    })

    slack.post_message(channel, blocks=blocks)
    return {"statusCode": 200, "body": ""}


def handle_finding_details(payload: dict, finding_id: str) -> dict:
    """Show detailed information about a finding - async wrapper."""
    import boto3
    import json
    import os

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    slack = get_slack_service()

    # Post immediate response
    slack.post_message(channel, text="🔍 Loading finding details...")

    # Get account ID
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Invoke async processing
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'action': 'process_finding_details_async',
                'channel_id': channel,
                'user_id': user,
                'finding_id': finding_id,
                'account_id': account_id
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async finding details: {e}")
        # Fallback to synchronous
        return handle_finding_details_sync(channel, user, finding_id, account_id)

    return {"statusCode": 200, "body": ""}


def handle_finding_details_sync(channel: str, user: str, finding_id: str, account_id: str) -> dict:
    """Synchronous version of finding details - does the actual work."""
    slack = get_slack_service()
    findings_service = get_findings_service()
    bedrock = get_bedrock_service()

    finding = findings_service.get_finding(finding_id, account_id)
    if not finding:
        slack.post_message(channel, text=f"Finding {finding_id} not found.")
        return {"statusCode": 200, "body": ""}

    # Get AI explanation
    explanation = bedrock.explain_finding(finding)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Finding: {finding.get('title', 'Unknown')}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:* {finding.get('severity', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Source:* {finding.get('source', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Resource:* `{finding.get('resource_id', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Status:* {finding.get('status', 'N/A')}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{finding.get('description', 'No description')}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*AI Analysis:*\n{explanation}",
            },
        },
        {
            "type": "divider",
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Remediation"},
                    "style": "primary",
                    "action_id": f"request_remediation_{finding_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Suppress"},
                    "action_id": f"suppress_finding_{finding_id}",
                },
            ],
        },
    ]

    slack.post_message(channel, blocks=blocks)

    return {"statusCode": 200, "body": ""}


def handle_finding_create_ticket_button(payload: dict, finding_id: str) -> dict:
    """Handle Create Ticket button click - uses same AI-enhanced logic as jira sync."""
    from datetime import datetime
    from services.findings_service import FindingsService
    from services.jira_security_sync import JiraSecuritySync

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    slack = get_slack_service()
    findings_service = FindingsService()

    # Get account ID
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Get finding
    finding = findings_service.get_finding(finding_id, account_id)
    if not finding:
        slack.post_message(channel, text=f"❌ Finding {finding_id} not found.")
        return {"statusCode": 200, "body": ""}

    # Check if already has ticket
    if finding.get('jira_ticket_id'):
        slack.post_message(
            channel,
            text=f"ℹ️ Finding {finding_id} already has Jira ticket: {finding['jira_ticket_id']}"
        )
        return {"statusCode": 200, "body": ""}

    # Create Jira ticket using AI-enhanced sync logic (same as /carl jira sync)
    try:
        jira_sync = JiraSecuritySync()

        # Use sync_finding_to_jira which generates AI-enhanced ticket descriptions
        result = jira_sync.sync_finding_to_jira(
            finding_id=finding_id,
            title=finding.get('title', 'Security Finding'),
            severity=finding.get('severity', 'MEDIUM'),
            resource_type=finding.get('resource_type', 'Unknown'),
            resource_id=finding.get('resource_id', 'N/A'),
            compliance_status=finding.get('compliance_status', 'FAILED'),
            recommendation=finding.get('remediation_steps', finding.get('description', 'Review this finding')),
            aws_account_id=account_id,
            region=finding.get('region', 'us-east-1'),
            metadata={"control_ids": finding.get('control_ids', [])}  # Pass SOC 2 controls for AI context
        )

        if result["success"]:
            slack.post_message(
                channel,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ Created Jira ticket for finding {finding_id}\n🔗 <{result['jira_url']}|{result['jira_key']}>"
                        }
                    }
                ]
            )
        else:
            slack.post_message(channel, text=f"❌ Failed to create Jira ticket: {result.get('error', 'Unknown error')}")

    except Exception as e:
        logger.exception(f"Error creating Jira ticket: {e}")
        slack.post_message(channel, text=f"❌ Failed to create Jira ticket. Error: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_finding_request_exception_button(payload: dict, finding_id: str) -> dict:
    """Handle Request Exception button - creates formal exception request."""
    from services.findings_service import FindingsService

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    trigger_id = payload.get("trigger_id")

    slack = get_slack_service()
    findings_service = FindingsService()

    # Get account ID
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Get finding
    finding = findings_service.get_finding(finding_id, account_id)
    if not finding:
        slack.post_message(channel, text=f"❌ Finding {finding_id} not found.")
        return {"statusCode": 200, "body": ""}

    # Open modal for exception request details
    if not trigger_id:
        slack.post_message(channel, text="❌ Unable to open exception request form.")
        return {"statusCode": 200, "body": ""}

    slack.client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": f"exception_request_modal_{finding_id}",
            "title": {"type": "plain_text", "text": "Request Exception"},
            "submit": {"type": "plain_text", "text": "Submit Request"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Finding:* {finding.get('title')}\n*Severity:* {finding.get('severity')}\n*Resource:* `{finding.get('resource_id')}"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "input",
                    "block_id": "justification_block",
                    "label": {"type": "plain_text", "text": "Business Justification"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "justification_input",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "Explain why this risk should be accepted (e.g., compensating controls, business requirements)..."}
                    }
                },
                {
                    "type": "input",
                    "block_id": "expiration_block",
                    "label": {"type": "plain_text", "text": "Exception Expiration (days)"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "expiration_input",
                        "placeholder": {"type": "plain_text", "text": "90"}
                    },
                    "hint": {"type": "plain_text", "text": "How many days until this exception should be re-reviewed?"}
                }
            ],
            "private_metadata": f"{finding_id}|{account_id}"
        }
    )

    return {"statusCode": 200, "body": ""}


def handle_finding_accept_risk_button(payload: dict, finding_id: str) -> dict:
    """Handle Accept Risk button click - open modal for justification."""
    slack = get_slack_service()
    trigger_id = payload.get("trigger_id")

    if not trigger_id:
        return {"statusCode": 200, "body": ""}

    # Open modal to get justification
    slack.client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": f"accept_risk_modal_{finding_id}",
            "title": {"type": "plain_text", "text": "Accept Risk"},
            "submit": {"type": "plain_text", "text": "Accept"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "justification_block",
                    "label": {"type": "plain_text", "text": "Business Justification"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "justification_input",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "Explain why this risk is acceptable..."}
                    }
                }
            ],
            "private_metadata": finding_id
        }
    )

    return {"statusCode": 200, "body": ""}


def handle_finding_ignore_button(payload: dict, finding_id: str) -> dict:
    """Handle Ignore button click."""
    from services.findings_service import FindingsService

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    slack = get_slack_service()
    findings_service = FindingsService()

    # Get account ID
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Ignore the finding
    success = findings_service.ignore_finding(
        finding_id=finding_id,
        account_id=account_id,
        ignored_by=user
    )

    if success:
        slack.post_message(
            channel,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"👁️ Finding {finding_id} marked as ignored\n*By:* <@{user}>"
                    }
                }
            ]
        )
    else:
        slack.post_message(channel, text=f"❌ Failed to ignore finding {finding_id}")

    return {"statusCode": 200, "body": ""}


def handle_finding_show_fix(payload: dict, finding_id: str) -> dict:
    """Handle Show Fix button click - displays remediation guidance."""
    from services.findings_service import FindingsService
    from services.remediation_service import RemediationService

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    slack = get_slack_service()
    findings_service = FindingsService()
    remediation_service = RemediationService()

    # Get account ID
    import boto3
    account_id = boto3.client('sts').get_caller_identity()['Account']

    # Get finding
    finding = findings_service.get_finding(finding_id, account_id)

    if not finding:
        slack.post_message(channel, text=f"❌ Finding {finding_id} not found")
        return {"statusCode": 404, "body": "Finding not found"}

    # Generate remediation guidance
    guidance = remediation_service.generate_remediation(finding)

    if not guidance:
        slack.post_message(
            channel,
            text=f"⚠️ No automated remediation guidance available for this finding.\n\n"
                 f"*Finding:* {finding.get('title', 'Unknown')}\n"
                 f"Please refer to AWS documentation or contact your security team for remediation steps."
        )
        return {"statusCode": 200, "body": "No guidance available"}

    # Format and send remediation guidance to Slack
    guidance_blocks = remediation_service.format_for_slack(guidance)

    slack.post_message(
        channel,
        text=f"🔧 Remediation Guidance for: {finding.get('title', 'Unknown')}",
        blocks=guidance_blocks['blocks']
    )

    return {"statusCode": 200, "body": "Remediation guidance sent"}


def handle_remediation_approval(
    payload: dict, remediation_id: str, approved: bool
) -> dict:
    """Handle remediation approval/denial."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    slack = get_slack_service()

    if approved:
        # TODO: Trigger remediation execution
        slack.post_message(
            channel,
            text=f"Remediation {remediation_id} approved by <@{user}>. Executing...",
        )
    else:
        slack.post_message(
            channel,
            text=f"Remediation {remediation_id} denied by <@{user}>.",
        )

    return {"statusCode": 200, "body": ""}


# =============================================================================
# AI-DRIVEN ARCHITECTURE HANDLERS
# =============================================================================


def handle_architect_command(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """
    Handle /carl architect command - ALIAS for /carl recommend.

    Consolidated to avoid redundancy. Both provide architecture recommendations
    with the same agent, tools, and features.
    """
    if not question:
        slack.post_message(
            channel_id,
            text=(
                "Ask me any AWS architecture question. I'll scan your environment and provide personalized recommendations. Examples:\n"
                "• /carl architect How should I design my VPC for a multi-region deployment?\n"
                "• /carl architect Compare Transit Gateway vs VPC Peering for 10 VPCs\n"
                "• /carl architect What's the best egress pattern for SOC 2 compliance?\n"
                "• /carl architect Design a complete AWS foundation for my startup\n\n"
                "_Note: /carl architect and /carl recommend are equivalent - use whichever you prefer!_"
            ),
        )
        return {"statusCode": 200, "body": ""}

    # Redirect to recommend handler - they're consolidated now
    return handle_recommend_command_sync(slack, channel_id, user_id, question)


def handle_foundation_explain(payload: dict, action: dict) -> dict:
    """Handle request to explain a foundation decision with AI."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    # Parse action_id: foundation_explain_{session_id}_{decision_index}
    action_id = action.get("action_id", "")
    parts = action_id.replace("foundation_explain_", "").split("_")
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    decision_index = int(parts[1])

    engine = get_decision_engine()
    session = engine.get_session(session_id)
    slack = get_slack_service()

    if not session:
        slack.post_message(channel, text="Session expired.")
        return {"statusCode": 200, "body": ""}

    slack.post_message(channel, text="_Getting AI-powered explanation..._")

    # Get AI explanation
    explanation = engine.get_ai_explanation(session, decision_index)

    # Split if too long
    if len(explanation) > 3000:
        chunks = [explanation[i:i+3000] for i in range(0, len(explanation), 3000)]
        for chunk in chunks:
            slack.post_message(channel, text=chunk)
    else:
        slack.post_message(channel, text=explanation)

    return {"statusCode": 200, "body": ""}


def handle_foundation_compare(payload: dict, action: dict) -> dict:
    """Handle request to compare alternatives with AI."""
    channel = payload.get("channel", {}).get("id", "")

    # Parse action_id: foundation_compare_{session_id}_{decision_index}
    action_id = action.get("action_id", "")
    parts = action_id.replace("foundation_compare_", "").split("_")
    if len(parts) < 2:
        return {"statusCode": 200, "body": "Invalid action"}

    session_id = parts[0]
    decision_index = int(parts[1])

    engine = get_decision_engine()
    session = engine.get_session(session_id)
    slack = get_slack_service()

    if not session:
        slack.post_message(channel, text="Session expired.")
        return {"statusCode": 200, "body": ""}

    slack.post_message(channel, text="_Generating AI-powered comparison..._")

    # Get AI comparison
    comparison = engine.compare_alternatives(session, decision_index)

    if len(comparison) > 3000:
        chunks = [comparison[i:i+3000] for i in range(0, len(comparison), 3000)]
        for chunk in chunks:
            slack.post_message(channel, text=chunk)
    else:
        slack.post_message(channel, text=comparison)

    return {"statusCode": 200, "body": ""}


def handle_feedback(payload: dict, action: dict) -> dict:
    """Handle feedback on AI recommendations."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    action_id = action.get("action_id", "")
    question_context = action.get("value", "")
    slack = get_slack_service()

    if "helpful" in action_id and "not_helpful" not in action_id:
        # Positive feedback
        slack.post_message(
            channel,
            text="Thanks for the feedback! This helps CARL learn and improve.",
        )
        # Record feedback (would store in DynamoDB in production)
        logger.info(f"Positive feedback from {user} for: {question_context}")

    elif "not_helpful" in action_id:
        # Negative feedback - ask for details
        slack.post_message(
            channel,
            text="Sorry the recommendation wasn't helpful. Could you tell me what was wrong or what you expected? Your feedback helps CARL improve.",
        )
        logger.info(f"Negative feedback from {user} for: {question_context}")

    elif "improve" in action_id:
        # Improvement suggestion - prompt for details
        slack.post_message(
            channel,
            text="What improvement would you suggest? Reply with your suggestion and CARL will learn from it.",
        )
        logger.info(f"Improvement request from {user} for: {question_context}")

    return {"statusCode": 200, "body": ""}


def handle_learning_feedback(payload: dict, action: dict) -> dict:
    """
    Handle feedback on /carl ask responses for continuous learning.

    This records whether the AI's scan decisions and answers were helpful,
    enabling the system to learn and improve over time.
    """
    import os
    from services.learning_service import LearningService

    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")
    slack = get_slack_service()

    action_id = action.get("action_id", "")
    value = action.get("value", "")  # Format: "interaction_id:helpful" or "interaction_id:not_helpful"

    try:
        # Parse interaction ID from value
        parts = value.split(":", 1)
        if len(parts) != 2:
            logger.error(f"Invalid feedback value format: {value}")
            return {"statusCode": 200, "body": ""}

        interaction_id = parts[0]
        feedback_type = parts[1]
        was_useful = (feedback_type == "helpful")

        # Record feedback in learning service
        learning_service = LearningService(
            scan_history_table=os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history"),
            resource_graph_table=os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")
        )

        success = learning_service.record_feedback(interaction_id, was_useful)

        # Send ephemeral message to user (visible only to them)
        if success:
            if was_useful:
                response_text = "✅ Thanks! This helps CARL learn what scans are most useful for your environment."
            else:
                response_text = "📝 Thanks for the feedback! CARL will adjust its scanning strategy to be more helpful."
        else:
            response_text = "⚠️ Feedback recorded, but the interaction wasn't found in history (this is normal for architecture questions)."

        # Send ephemeral response
        slack.post_ephemeral(
            channel,
            user,
            text=response_text
        )

        logger.info(f"Recorded learning feedback: interaction={interaction_id}, useful={was_useful}, found={success}, user={user}")

    except Exception as e:
        logger.error(f"Failed to handle learning feedback: {e}", exc_info=True)
        # Send ephemeral error message
        try:
            slack.post_ephemeral(
                channel,
                user,
                text="⚠️ Failed to record feedback, but I appreciate you trying to help me learn!"
            )
        except:
            pass

    return {"statusCode": 200, "body": ""}


# =============================================================================
# AUDIT EVIDENCE HANDLERS
# =============================================================================


def handle_evidence_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl evidence command - audit evidence collection (async wrapper)."""
    import os
    import json
    import boto3

    parts = args.split() if args else []
    subcommand = parts[0].lower() if parts else "status"

    # For "collect" command, invoke async immediately without initializing heavy resources
    if subcommand == "collect":
        # Invoke async processing in background FIRST (before any Slack API calls or heavy init)
        try:
            lambda_client = boto3.client('lambda')
            lambda_client.invoke(
                FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
                InvocationType='Event',  # Async invocation
                Payload=json.dumps({
                    'action': 'process_evidence_collect_async',
                    'channel_id': channel_id,
                    'user_id': user_id
                })
            )
        except Exception as e:
            logger.error(f"Failed to invoke async evidence collection: {e}")
            # Fallback to synchronous if async fails
            from services.evidence_collector import EvidenceCollector
            evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
            evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")
            collector = EvidenceCollector(
                evidence_bucket=evidence_bucket,
                evidence_table=evidence_table
            )
            return handle_evidence_collect_sync(slack, channel_id, user_id)

        # Return immediate response in body (shows to user without additional API call)
        # This is MUCH faster than slack.post_message() and prevents timeout
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "response_type": "ephemeral",
                "text": "🔍 *Starting evidence collection across all resources...*\n\n_This may take a few minutes. I'll post results when complete._"
            })
        }

    # For other subcommands, initialize collector as needed
    from services.evidence_collector import EvidenceCollector
    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")

    try:
        collector = EvidenceCollector(
            evidence_bucket=evidence_bucket,
            evidence_table=evidence_table
        )

        if subcommand == "list":
            # Parse optional type filter (e.g., /carl evidence list IAM)
            evidence_type_filter = parts[1] if len(parts) > 1 else None
            return handle_evidence_list_command(slack, channel_id, user_id, evidence_type_filter)

        elif subcommand == "status":
            coverage = collector.get_control_coverage()

            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Evidence Collection Status"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Coverage:* {coverage['coverage_percent']:.1f}%"},
                        {"type": "mrkdwn", "text": f"*Controls Covered:* {len(coverage['covered'])}"},
                        {"type": "mrkdwn", "text": f"*Controls Missing:* {len(coverage['missing'])}"},
                    ]
                }
            ]

            if coverage["missing"]:
                missing_list = ", ".join(coverage["missing"][:10])
                if len(coverage["missing"]) > 10:
                    missing_list += f" (+{len(coverage['missing']) - 10} more)"
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Missing Controls:* {missing_list}"}
                })

            # Add hint to collect evidence (no button - keep UI consistent)
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 Run /carl evidence collect` to gather evidence for missing controls"
                    }
                ]
            })

            slack.post_message(channel_id, blocks=blocks)

        else:
            slack.post_message(
                channel_id,
                text="Unknown evidence command. Use collect or `status."
            )

    except Exception as e:
        logger.exception("Error in evidence command")
        slack.post_message(channel_id, text=f"Error: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_evidence_collect_sync(slack: SlackService, channel_id: str, user_id: str) -> dict:
    """Synchronous version of evidence collect - does the actual work."""
    import os
    from services.evidence_collector import EvidenceCollector

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")

    try:
        collector = EvidenceCollector(
            evidence_bucket=evidence_bucket,
            evidence_table=evidence_table
        )

        # Collect evidence
        results = collector.collect_all_evidence()

        # Post collection summary
        total = sum(len(items) for items in results.values())
        summary_lines = [f"*Evidence Collection Complete*\n\nCollected *{total}* evidence items:\n"]
        for category, items in results.items():
            summary_lines.append(f"• {category.upper()}: {len(items)} items")

        logger.info(f"Posting evidence collection summary to channel {channel_id}")
        try:
            slack.post_message(channel_id, text="\n".join(summary_lines))
            logger.info("Successfully posted collection summary")
        except Exception as slack_err:
            logger.error(f"Failed to post collection summary: {slack_err}")

        # Create findings from security issues detected in evidence
        logger.info("Posting 'Analyzing evidence' message")
        try:
            slack.post_message(channel_id, text="🔍 Analyzing evidence for security issues...")
            logger.info("Successfully posted analyzing message")
        except Exception as slack_err:
            logger.error(f"Failed to post analyzing message: {slack_err}")

        findings = collector.create_findings_from_evidence(results)

        # Store findings in DynamoDB
        findings_service = get_findings_service()
        stored_count = 0
        for finding in findings:
            try:
                findings_service.store_finding(finding)
                stored_count += 1
            except Exception as e:
                logger.error(f"Failed to store finding {finding.id}: {e}")

        logger.info(f"Posting findings result: stored_count={stored_count}")
        if stored_count > 0:
            try:
                slack.post_message(
                    channel_id,
                    text=f"✅ Created {stored_count} new findings from evidence analysis.\n\n"
                         f"Run /carl jira sync` to create Jira tickets for these issues."
                )
                logger.info("Successfully posted new findings message")
            except Exception as slack_err:
                logger.error(f"Failed to post new findings message: {slack_err}")
        else:
            try:
                slack.post_message(
                    channel_id,
                    text="✓ No new security issues found (all findings already exist)."
                )
                logger.info("Successfully posted no new findings message")
            except Exception as slack_err:
                logger.error(f"Failed to post no new findings message: {slack_err}")

    except Exception as e:
        logger.exception("Error collecting evidence")
        slack.post_message(channel_id, text=f"❌ Evidence collection failed: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_evidence_list_command(
    slack: SlackService, channel_id: str, user_id: str, evidence_type_filter: str = None
) -> dict:
    """Handle /carl evidence list command - shows all collected evidence items with findings status."""
    import os
    from services.evidence_collector import EvidenceCollector

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")

    try:
        collector = EvidenceCollector(
            evidence_bucket=evidence_bucket,
            evidence_table=evidence_table
        )
        findings_service = get_findings_service()

        # Get recent evidence items (limit to 10 to stay under Slack's 50 block limit)
        evidence_items = collector.get_recent_evidence(limit=10, evidence_type=evidence_type_filter)

        if not evidence_items:
            slack.post_message(
                channel_id,
                text=f"No evidence items found{' for type: ' + evidence_type_filter if evidence_type_filter else ''}.\n\n"
                     f"Run /carl evidence collect` to gather evidence."
            )
            return {"statusCode": 200, "body": ""}

        # Get all findings to match with evidence
        all_findings = findings_service.get_recent_findings(limit=100)

        logger.info(f"🔍 DEBUG: Loaded {len(all_findings)} findings")
        if all_findings:
            logger.info(f"🔍 DEBUG: First finding resource_id example: '{all_findings[0].get('resource_id')}'")
            logger.info(f"🔍 DEBUG: First finding ID: '{all_findings[0].get('id')}'")
            logger.info(f"🔍 DEBUG: First finding has jira_ticket_id: {all_findings[0].get('jira_ticket_id')}")

        # Create lookup dict - try both exact resource_id match and partial match
        findings_by_resource = {}
        for f in all_findings:
            resource_id = f.get('resource_id', '')
            findings_by_resource[resource_id] = f
            # Also index by last part of resource ID (after last /)
            if '/' in resource_id:
                resource_name = resource_id.split('/')[-1]
                if resource_name not in findings_by_resource:
                    findings_by_resource[resource_name] = f
            # Also index by ARN suffix (after last :)
            if ':' in resource_id:
                arn_suffix = resource_id.split(':')[-1]
                if arn_suffix not in findings_by_resource:
                    findings_by_resource[arn_suffix] = f

        logger.info(f"🔍 DEBUG: Indexed {len(findings_by_resource)} resource ID keys")
        logger.info(f"🔍 DEBUG: Sample finding keys: {list(findings_by_resource.keys())[:3]}")

        # Build Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Collected Evidence{' - ' + evidence_type_filter if evidence_type_filter else ''}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Showing {len(evidence_items)} most recent items | ✅ = Compliant | ⚠️ = Issue Found"
                    }
                ]
            }
        ]

        # Display each evidence item (limited to 10 to avoid Slack's 50 block limit)
        for idx, evidence in enumerate(evidence_items[:10]):
            logger.info(f"🔍 DEBUG [{idx}]: Evidence resource_id='{evidence.resource_id}'")
            logger.info(f"🔍 DEBUG [{idx}]: Evidence title='{evidence.title}'")

            # Check if there's a finding for this resource - try exact match first, then partial
            resource_finding = findings_by_resource.get(evidence.resource_id)

            # If no exact match, try partial match (last part of resource ID)
            if not resource_finding and '/' in evidence.resource_id:
                resource_name = evidence.resource_id.split('/')[-1]
                resource_finding = findings_by_resource.get(resource_name)
                if resource_finding:
                    logger.info(f"🔍 DEBUG [{idx}]: Matched by / suffix '{resource_name}'")

            # Also try matching by removing 'arn:aws:...:' prefix
            if not resource_finding and evidence.resource_id.startswith('arn:'):
                simple_resource = evidence.resource_id.split(':')[-1]
                resource_finding = findings_by_resource.get(simple_resource)
                if resource_finding:
                    logger.info(f"🔍 DEBUG [{idx}]: Matched by : suffix '{simple_resource}'")

            # Log for debugging
            if resource_finding:
                logger.info(f"🔍 DEBUG [{idx}]: ✓ MATCHED to finding '{resource_finding.get('id')}' (jira: {resource_finding.get('jira_ticket_id', 'none')}, status: {resource_finding.get('status')})")
            else:
                logger.warning(f"🔍 DEBUG [{idx}]: ✗ NO MATCH for evidence '{evidence.resource_id}'")

            # Determine status and severity
            if resource_finding:
                severity = resource_finding.get('severity', 'UNKNOWN')
                status = resource_finding.get('status', 'NEW')
                finding_id = resource_finding.get('id', '')
                jira_ticket_id = resource_finding.get('jira_ticket_id')
                jira_url = resource_finding.get('jira_url')

                # Severity emoji
                severity_emoji = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟠',
                    'MEDIUM': '🟡',
                    'LOW': '🔵',
                    'INFORMATIONAL': 'ℹ️'
                }.get(severity, '⚠️')

                status_text = f"{severity_emoji} {severity}"
                if jira_ticket_id and jira_url:
                    status_text += f" | <{jira_url}|{jira_ticket_id}>"

            else:
                status_text = "✅ Compliant"
                finding_id = None
                jira_ticket_id = None
                status = None

            # Build evidence text
            evidence_text = (
                f"{status_text}\n"
                f"*{evidence.title}*\n"
                f"{evidence.description[:150]}{'...' if len(evidence.description) > 150 else ''}\n"
                f"Resource: `{evidence.resource_id}"
            )

            # Add section with optional accessory button for compliant items
            section_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": evidence_text
                }
            }
            blocks.append(section_block)

            # Add action buttons if there's a finding
            if resource_finding:
                action_buttons = []

                # Show "Create Ticket" if no ticket and not accepted/ignored
                if not jira_ticket_id and status not in ["ACCEPTED_RISK", "IGNORED", "SUPPRESSED", "REMEDIATED"]:
                    action_buttons.append({
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🎫 Create Ticket"},
                        "action_id": f"finding_create_ticket_{finding_id}",
                        "style": "primary"
                    })

                # Show "Request Exception" for formal risk acceptance process
                if status not in ["ACCEPTED_RISK", "IGNORED", "REMEDIATED"]:
                    action_buttons.append({
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📋 Request Exception"},
                        "action_id": f"finding_request_exception_{finding_id}",
                    })

                # Show "Ignore" if not already ignored/remediated
                if status not in ["IGNORED", "REMEDIATED"]:
                    action_buttons.append({
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👁️ Ignore"},
                        "action_id": f"finding_ignore_{finding_id}",
                    })

                # Always show "Details" button
                action_buttons.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": "ℹ️ Details"},
                    "action_id": f"finding_details_{finding_id}",
                })

                if action_buttons:
                    blocks.append({
                        "type": "actions",
                        "elements": action_buttons
                    })

        # Add section showing unmatched findings with issues
        unmatched_findings = [f for f in all_findings if not f.get('jira_ticket_id') and f.get('status') not in ['ACCEPTED_RISK', 'IGNORED', 'SUPPRESSED', 'REMEDIATED']]

        if unmatched_findings and len(unmatched_findings) > 0:
            logger.info(f"🔍 DEBUG: Found {len(unmatched_findings)} findings without tickets")
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🎫 {len(unmatched_findings)} Finding(s) Need Tickets*"
                }
            })

            # Show up to 3 findings that need tickets
            for finding in unmatched_findings[:3]:
                finding_id = finding.get('id', '')
                severity = finding.get('severity', 'UNKNOWN')

                severity_emoji = {
                    'CRITICAL': '🔴',
                    'HIGH': '🟠',
                    'MEDIUM': '🟡',
                    'LOW': '🔵',
                    'INFORMATIONAL': 'ℹ️'
                }.get(severity, '⚠️')

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{severity_emoji} *{severity}* | {finding.get('title', 'Unknown')}\nResource: `{finding.get('resource_id', 'N/A')}"
                    }
                })
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🎫 Create Ticket"},
                            "action_id": f"finding_create_ticket_{finding_id}",
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "ℹ️ Details"},
                            "action_id": f"finding_details_{finding_id}",
                        }
                    ]
                })

        # Add footer with helpful commands
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 Showing 10 most recent items | Run /carl evidence collect to refresh | /carl jira sync to sync all findings"
                }
            ]
        })

        slack.post_message(channel_id, blocks=blocks)

    except Exception as e:
        logger.exception("Error listing evidence")
        slack.post_message(channel_id, text=f"❌ Failed to list evidence: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_report_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl report command - generate compliance reports (async)."""
    import os
    import json
    import boto3

    parts = args.split() if args else []
    report_type = parts[0].lower() if parts else "executive"
    control_id = parts[1] if len(parts) > 1 else None

    # Validate report type
    if report_type not in ["executive", "full", "control"]:
        slack.post_message(
            channel_id,
            text="Usage: /carl report executive|full|control <control-id>"
        )
        return {"statusCode": 200, "body": ""}

    if report_type == "control" and not control_id:
        slack.post_message(
            channel_id,
            text="Error: Control report requires a control ID. Usage: /carl report control CC6.1"
        )
        return {"statusCode": 200, "body": ""}

    # Invoke async processing in background (sync handler will post status message)
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'action': 'process_report_async',
                'channel_id': channel_id,
                'user_id': user_id,
                'report_type': report_type,
                'control_id': control_id
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async report processing: {e}")
        # Fallback to synchronous if async fails
        return handle_report_command_sync(slack, channel_id, user_id, report_type, control_id)

    # Return empty 200 OK immediately to Slack (prevents timeout)
    return {"statusCode": 200, "body": ""}


def handle_report_command_sync(
    slack: SlackService, channel_id: str, user_id: str, report_type: str, control_id: str | None
) -> dict:
    """Synchronous version of report command - generates reports from collected evidence."""
    import os
    from services.evidence_collector import EvidenceCollector
    from services.report_generator import ReportGenerator, ReportType
    from datetime import datetime, timedelta

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")
    findings_table = os.environ.get("FINDINGS_TABLE", "carl-findings")
    exceptions_table = os.environ.get("EXCEPTIONS_TABLE", "carl-exceptions")
    reports_bucket = os.environ.get("REPORTS_BUCKET", "carl-reports")

    # Post initial status message and get timestamp for updates
    status_response = slack.post_message(
        channel_id,
        text=f"📊 Generating {report_type} report...\n\n🔄 Loading evidence and findings..."
    )
    status_ts = status_response.get("ts") if status_response else None

    def update_progress(status: str):
        """Update the status message in Slack."""
        if status_ts:
            try:
                slack.update_message(
                    channel_id,
                    status_ts,
                    text=f"📊 Generating {report_type} report...\n\n{status}"
                )
            except Exception as e:
                logger.warning(f"Failed to update progress: {e}")

    try:
        # Step 1: Initialize services
        update_progress("📋 Loading evidence and findings...")

        collector = EvidenceCollector(
            evidence_bucket=evidence_bucket,
            evidence_table=evidence_table
        )

        generator = ReportGenerator(
            evidence_collector=collector,
            findings_table=findings_table,
            exceptions_table=exceptions_table,
            reports_bucket=reports_bucket
        )

        # Step 2: Get evidence and findings summary from DynamoDB
        coverage = collector.get_control_coverage()
        findings_summary = generator._get_findings_summary()

        total_evidence = sum(len(evidence_list) for evidence_list in coverage.get("control_evidence", {}).values())
        total_controls = len(coverage.get("covered", [])) + len(coverage.get("missing", []))
        controls_covered = len(coverage.get("covered", []))

        scan_summary = (
            f"{total_evidence} evidence items, "
            f"{findings_summary.get('total', 0)} findings "
            f"({findings_summary.get('critical', 0)} critical, "
            f"{findings_summary.get('high', 0)} high), "
            f"{controls_covered}/{total_controls} controls covered"
        )
        logger.info(f"Report data loaded: {scan_summary}")

        # Default audit period: last 12 months
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")

        # Step 3: Generate report with scan context
        update_progress(f"📝 Generating {report_type} report with live data...")

        # Add scan context to report generation
        report_context = f"""
# Current Environment Context
{scan_summary}

---

"""

        # Generate PDF reports (Docker container has WeasyPrint support)
        update_progress("📝 Generating professional PDF report...")

        if report_type == "executive":
            pdf_bytes, report_data = generator.generate_executive_summary_pdf(
                start_date,
                end_date,
                organization_name="Your Organization"
            )
            filename = f"executive-summary-{datetime.utcnow().strftime('%Y%m%d')}.pdf"
            report_type_enum = ReportType.EXECUTIVE_SUMMARY

        elif report_type == "full":
            pdf_bytes, report_data = generator.generate_full_audit_pdf(
                start_date,
                end_date,
                organization_name="Your Organization"
            )
            filename = f"full-audit-report-{datetime.utcnow().strftime('%Y%m%d')}.pdf"
            report_type_enum = ReportType.FULL_AUDIT

        elif report_type == "control" and control_id:
            # Control reports don't have PDF version yet - fallback to markdown
            update_progress("📝 Generating control report (markdown)...")
            report = generator.generate_control_report(control_id.upper())
            report = report_context + report
            report_type_enum = ReportType.CONTROL_SPECIFIC

            # Save to S3
            s3_key = generator.save_report(report, report_type_enum)
            download_url = generator.generate_presigned_url(s3_key, expiration=86400)

            summary_text = f"""📊 Control Report Generated Successfully

Control ID: {control_id.upper()}
Audit Period: {start_date} to {end_date}

📥 Download Report (Markdown):
{download_url}

Link expires in 24 hours. PDF format coming soon!"""

            slack.post_message(channel_id, text=summary_text)
            return {"statusCode": 200, "body": "Control report generated"}

        else:
            raise ValueError(f"Unknown report type: {report_type}")

        # Delete the status message before uploading (cleaner UX)
        if status_ts:
            try:
                slack.delete_message(channel_id, status_ts)
            except Exception as e:
                logger.warning(f"Failed to delete status message: {e}")

        # Upload PDF file to Slack channel
        try:
            slack.upload_file(
                channels=channel_id,
                file_content=pdf_bytes,
                filename=filename,
                title=f"{report_type.title()} Compliance Report",
                initial_comment=f"📊 {report_type.title()} Report Generated\n\nAudit Period: {start_date} to {end_date}\n\nEnvironment: {scan_summary}\n\nProfessional PDF report attached below ⬇️"
            )
        except Exception as e:
            logger.error(f"Failed to upload PDF to Slack: {e}")
            # Fallback: save to S3 and provide download link
            update_progress("☁️ Uploading to S3 as fallback...")
            s3_key = generator.save_pdf_report(pdf_bytes, report_type_enum)
            download_url = generator.generate_presigned_url(s3_key, expiration=86400)

            if not download_url:
                logger.error("Failed to generate presigned URL for S3 fallback")
                slack.post_message(
                    channel_id,
                    text=f"❌ Error: Could not upload to Slack or generate S3 download link. S3 key: {s3_key}"
                )
                return {"statusCode": 500, "body": "Failed to generate download URL"}

            # Use plain URL format (not markdown) to avoid Slack formatting issues
            summary_text = f"""📊 {report_type.title()} Report Generated Successfully

Audit Period: {start_date} to {end_date}

Environment: {scan_summary}

⚠️ Could not upload directly to Slack.

📥 Download PDF Report:
{download_url}

Link expires in 24 hours"""

            slack.post_message(channel_id, text=summary_text)
            return {"statusCode": 200, "body": "Report generated (S3 fallback)"}

        # Success message already sent with file upload (no additional message needed)

    except Exception as e:
        logger.exception("Error generating report")

        # Delete status message on error too
        if status_ts:
            try:
                slack.delete_message(channel_id, status_ts)
            except Exception as e2:
                logger.warning(f"Failed to delete status message: {e2}")

        slack.post_message(channel_id, text=f"❌ Error generating report: {str(e)}")

    return {"statusCode": 200, "body": ""}


# =============================================================================
# EXCEPTION MANAGEMENT HANDLERS
# =============================================================================


def handle_exception_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl exception command - risk exception management."""
    import os
    from services.exception_manager import (
        ExceptionManager,
        ExceptionRequest,
        ExceptionType,
        RiskLevel,
        ExceptionStatus
    )

    parts = args.split() if args else []
    subcommand = parts[0].lower() if parts else "list"
    extra_args = parts[1:] if len(parts) > 1 else []

    exceptions_table = os.environ.get("EXCEPTIONS_TABLE", "carl-exceptions")
    findings_table = os.environ.get("FINDINGS_TABLE", "carl-findings")

    try:
        manager = ExceptionManager(
            exceptions_table=exceptions_table,
            findings_table=findings_table
        )

        if subcommand == "list":
            # List pending and active exceptions
            pending = manager.get_pending_exceptions()
            active = manager.get_active_exceptions()
            expiring = manager.get_expiring_exceptions(days=30)

            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Risk Exceptions"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Pending Review:* {len(pending)}"},
                        {"type": "mrkdwn", "text": f"*Active:* {len(active)}"},
                        {"type": "mrkdwn", "text": f"*Expiring Soon:* {len(expiring)}"},
                    ]
                },
                {"type": "divider"}
            ]

            if pending:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*⏳ Pending Review:*"}
                })
                for exc in pending[:5]:
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"• {exc.exception_id[:12]} - {exc.title[:50]}"},
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Review"},
                            "action_id": f"exception_review_{exc.exception_id}"
                        }
                    })

            if expiring:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*⚠️ Expiring Within 30 Days:*"}
                })
                for exc in expiring[:5]:
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"• {exc.exception_id[:12]} - {exc.title[:50]} (expires {exc.expires_at[:10]})"}
                    })

            slack.post_message(channel_id, blocks=blocks)

        elif subcommand == "request":
            # Show exception request form guidance
            slack.post_message(
                channel_id,
                text=(
                    "*To request a risk exception, provide:*\n\n"
                    "1. Title (brief description)\n"
                    "2. Resource ID or Finding ID\n"
                    "3. SOC 2 Controls affected\n"
                    "4. Business justification\n"
                    "5. Duration requested (days)\n\n"
                    "Example: /carl exception create \"API key rotation exception\" finding-123 CC6.1,CC6.5 \"Legacy system requires 180-day keys\" 90\n\n"
                    "_Or use the interactive form:_ Click the button below."
                ),
            )
            # Would add interactive modal button here

        elif subcommand == "approve" and extra_args:
            exception_id = extra_args[0]
            notes = " ".join(extra_args[1:]) if len(extra_args) > 1 else ""

            exc = manager.approve_exception(exception_id, user_id, notes)
            slack.post_message(
                channel_id,
                text=f"✅ Exception {exception_id} approved. Expires: {exc.expires_at[:10]}"
            )

        elif subcommand == "deny" and extra_args:
            exception_id = extra_args[0]
            reason = " ".join(extra_args[1:]) if len(extra_args) > 1 else "No reason provided"

            manager.deny_exception(exception_id, user_id, reason)
            slack.post_message(
                channel_id,
                text=f"❌ Exception {exception_id} denied. Reason: {reason}"
            )

        elif subcommand == "stats":
            stats = manager.get_exception_statistics()

            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Exception Statistics"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Total Exceptions:* {stats.get('total', 0)}"},
                        {"type": "mrkdwn", "text": f"*Pending Review:* {stats.get('pending_review', 0)}"},
                        {"type": "mrkdwn", "text": f"*Active:* {stats.get('active', 0)}"},
                        {"type": "mrkdwn", "text": f"*Expiring Soon:* {stats.get('expiring_soon', 0)}"},
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*By Risk Level:* {json.dumps(stats.get('by_risk_level', {}))}"}
                }
            ]
            slack.post_message(channel_id, blocks=blocks)

        else:
            slack.post_message(
                channel_id,
                text="Usage: /carl exception list|request|approve <id>|deny <id> <reason>|stats"
            )

    except Exception as e:
        logger.exception("Error in exception command")
        slack.post_message(channel_id, text=f"Error: {str(e)}")

    return {"statusCode": 200, "body": ""}


# =============================================================================
# DRIFT DETECTION HANDLERS
# =============================================================================


def handle_drift_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl drift command - infrastructure drift detection."""
    import os
    import json
    import boto3
    from services.drift_detector import DriftDetector

    parts = args.split() if args else []
    subcommand = parts[0].lower() if parts else "status"
    extra_args = parts[1:] if len(parts) > 1 else []

    drift_table = os.environ.get("DRIFT_TABLE", "carl-drift")
    terraform_bucket = os.environ.get("TERRAFORM_STATE_BUCKET", "")

    try:
        detector = DriftDetector(
            drift_table=drift_table,
            terraform_state_bucket=terraform_bucket if terraform_bucket else None
        )

        if subcommand == "scan":
            # Invoke async processing in background FIRST (before any Slack API calls)
            try:
                lambda_client = boto3.client('lambda')
                lambda_client.invoke(
                    FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
                    InvocationType='Event',  # Async invocation
                    Payload=json.dumps({
                        'action': 'process_drift_scan_async',
                        'channel_id': channel_id,
                        'user_id': user_id
                    })
                )
            except Exception as e:
                logger.error(f"Failed to invoke async drift scan: {e}")
                # Fallback to synchronous if async fails
                return handle_drift_scan_sync(slack, channel_id, user_id)

            # Return immediate response in body (shows to user without additional API call)
            # This is MUCH faster than slack.post_message() and prevents timeout
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "response_type": "ephemeral",
                    "text": "🔍 *Starting drift detection scan across all resources...*\n\n_This may take a few minutes. I'll post results when complete._"
                })
            }

        elif subcommand == "status":
            summary = detector.get_drift_summary()

            if "error" in summary:
                slack.post_message(channel_id, text=f"Error getting drift status: {summary['error']}")
                return {"statusCode": 200, "body": ""}

            severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "ℹ️"}

            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Infrastructure Drift Status"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Total Drift Items:* {summary.get('total_drift_items', 0)}"},
                        {"type": "mrkdwn", "text": f"*Critical:* {summary.get('critical_count', 0)}"},
                        {"type": "mrkdwn", "text": f"*Security Relevant:* {summary.get('security_relevant_count', 0)}"},
                    ]
                }
            ]

            # Add severity breakdown
            if summary.get("by_severity"):
                severity_text = " | ".join([
                    f"{severity_emoji.get(sev, '❓')} {sev}: {count}"
                    for sev, count in summary["by_severity"].items()
                ])
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*By Severity:* {severity_text}"}
                })

            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Run Scan"},
                        "style": "primary",
                        "action_id": "drift_scan_all"
                    }
                ]
            })

            if summary.get("last_scan"):
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"Last scan: {summary['last_scan']}"}]
                })

            slack.post_message(channel_id, blocks=blocks)

        elif subcommand == "acknowledge" and extra_args:
            drift_id = extra_args[0]
            notes = " ".join(extra_args[1:]) if len(extra_args) > 1 else ""

            if detector.acknowledge_drift(drift_id, user_id, notes):
                slack.post_message(channel_id, text=f"✓ Drift item {drift_id} acknowledged.")
            else:
                slack.post_message(channel_id, text=f"Failed to acknowledge drift item {drift_id}.")

        elif subcommand == "terraform" and extra_args:
            # Compare with Terraform state
            state_key = extra_args[0]
            slack.post_message(channel_id, text=f"Comparing with Terraform state: {state_key}...")

            drift_items = detector.compare_with_terraform_state(state_key)

            if drift_items:
                slack.post_message(
                    channel_id,
                    text=f"Found {len(drift_items)} drift items compared to Terraform state."
                )
                for item in drift_items[:5]:
                    slack.post_message(
                        channel_id,
                        text=f"• {item.resource_id} - {item.description}"
                    )
            else:
                slack.post_message(channel_id, text="✓ No drift detected compared to Terraform state.")

        elif subcommand == "jira-sync":
            # Sync drift items to Jira tickets (async)
            return handle_drift_jira_sync(slack, channel_id, user_id)

        else:
            slack.post_message(
                channel_id,
                text="Usage: /carl drift scan|status|acknowledge <drift-id>|terraform <state-key>|jira-sync"
            )

    except Exception as e:
        logger.exception("Error in drift command")
        slack.post_message(channel_id, text=f"Error: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_drift_scan_sync(slack: SlackService, channel_id: str, user_id: str) -> dict:
    """Synchronous version of drift scan - does the actual work."""
    import os
    from services.drift_detector import DriftDetector

    drift_table = os.environ.get("DRIFT_TABLE", "carl-drift")
    terraform_bucket = os.environ.get("TERRAFORM_STATE_BUCKET", "")

    try:
        detector = DriftDetector(
            drift_table=drift_table,
            terraform_state_bucket=terraform_bucket if terraform_bucket else None
        )

        # Perform drift detection
        report = detector.detect_all_drift()

        # Format and send report
        slack_format = detector.format_drift_report_for_slack(report)
        slack.post_message(channel_id, blocks=slack_format["blocks"])

        if report.critical_drifts:
            slack.post_message(
                channel_id,
                text=f"⚠️ {len(report.critical_drifts)} critical drift items require immediate attention!"
            )

    except Exception as e:
        logger.exception("Error in drift scan")
        slack.post_message(
            channel_id,
            text=f"❌ Drift scan failed: {str(e)}\n\n"
                 f"Please check CloudWatch logs for details."
        )

    return {"statusCode": 200, "body": ""}


def handle_drift_acknowledge_button(payload: dict, drift_id: str) -> dict:
    """Handle Acknowledge button click for drift items."""
    import os
    from services.drift_detector import DriftDetector

    slack = get_slack_service()
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")
    channel = payload.get("channel", {}).get("id", "")

    drift_table = os.environ.get("DRIFT_TABLE", "carl-drift")

    try:
        detector = DriftDetector(drift_table=drift_table)

        # Acknowledge the drift
        success = detector.acknowledge_drift(drift_id, user_id, notes="Acknowledged via Slack")

        if success:
            slack.post_message(
                channel,
                text=f"✓ Drift item {drift_id} acknowledged by <@{user_id}>"
            )
        else:
            slack.post_message(
                channel,
                text=f"❌ Failed to acknowledge drift item {drift_id}"
            )

    except Exception as e:
        logger.exception(f"Error acknowledging drift {drift_id}")
        slack.post_message(channel, text=f"❌ Error: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_drift_show_fix_button(payload: dict, drift_id: str) -> dict:
    """Handle Show Fix button click for drift items."""
    import os
    import json
    import boto3

    channel = payload.get("channel", {}).get("id", "")

    logger.info(f"Show Fix button clicked for drift_id: {drift_id}")

    # Invoke async Lambda to process in background
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'action': 'process_drift_show_fix_async',
                'channel_id': channel,
                'drift_id': drift_id
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async drift show fix: {e}")
        # Fallback to sync if async fails
        slack = get_slack_service()
        return handle_drift_show_fix_sync(slack, channel, drift_id)

    # Return immediate response in body (no API call needed, super fast)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "response_type": "ephemeral",
            "text": "⏳ Generating remediation guidance...\n_This will take a few seconds._"
        })
    }


def handle_drift_show_fix_sync(slack: SlackService, channel_id: str, drift_id: str) -> dict:
    """Process drift show fix synchronously - called by async Lambda."""
    import os
    from services.drift_detector import DriftDetector
    from services.remediation_service import RemediationService

    drift_table = os.environ.get("DRIFT_TABLE", "carl-drift")

    try:
        detector = DriftDetector(drift_table=drift_table)

        # Get drift item details
        drift_item = detector.get_drift_item(drift_id)

        if not drift_item:
            logger.error(f"Drift item not found in DynamoDB: {drift_id}")
            slack.post_message(channel_id, text=f"❌ Drift item {drift_id} not found")
            return {"statusCode": 200, "body": ""}

        # Convert drift item to finding format for remediation service
        # Use description as title so remediation service can match keywords like "encryption", "public", etc.
        finding = {
            "id": drift_item.drift_id,
            "title": drift_item.description,  # Use actual description with keywords
            "resource_type": drift_item.resource_type,
            "resource_id": drift_item.resource_id,
            "severity": drift_item.severity.upper(),
            "description": drift_item.description
        }

        # Generate remediation guidance
        remediation_service = RemediationService()
        guidance = remediation_service.generate_remediation(finding)

        if guidance:
            # Format for Slack
            guidance_blocks = remediation_service.format_for_slack(guidance)
            slack.post_message(channel_id, blocks=guidance_blocks['blocks'])
        else:
            # No automatic guidance - show manual instructions
            slack.post_message(
                channel_id,
                text=f"ℹ️ No automatic remediation guidance available for this drift type.\n\n"
                     f"*Drift Details:*\n{drift_item.description}\n\n"
                     f"*Next Steps:*\n"
                     f"1. Review the drift details above\n"
                     f"2. Fix manually in AWS Console or via AWS CLI\n"
                     f"3. Run /carl drift scan` to verify the fix"
            )

        return {"statusCode": 200, "body": ""}

    except Exception as e:
        logger.exception(f"Error showing fix for drift {drift_id}")
        slack.post_message(channel_id, text=f"❌ Error: {str(e)}")
        return {"statusCode": 200, "body": ""}


def handle_drift_suppress_button(payload: dict, drift_id: str) -> dict:
    """Handle Suppress button click for drift items."""
    import os
    from services.drift_detector import DriftDetector

    slack = get_slack_service()
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")
    channel = payload.get("channel", {}).get("id", "")

    drift_table = os.environ.get("DRIFT_TABLE", "carl-drift")

    try:
        detector = DriftDetector(drift_table=drift_table)

        # Mark as remediated (suppressed)
        success = detector.mark_remediated(drift_id)

        if success:
            slack.post_message(
                channel,
                text=f"🙈 Drift item {drift_id} suppressed by <@{user_id}>\n\n"
                     f"_This drift will be hidden from future reports. Re-run /carl drift scan` to detect if it recurs._"
            )
        else:
            slack.post_message(
                channel,
                text=f"❌ Failed to suppress drift item {drift_id}"
            )

    except Exception as e:
        logger.exception(f"Error suppressing drift {drift_id}")
        slack.post_message(channel, text=f"❌ Error: {str(e)}")

    return {"statusCode": 200, "body": ""}


def handle_drift_create_ticket_button(payload: dict, drift_id: str) -> dict:
    """Handle Create Ticket button click for drift items."""
    import os
    from services.drift_detector import DriftDetector
    from services.jira_service import JiraService

    slack = get_slack_service()
    user = payload.get("user", {})
    user_id = user.get("id", "unknown")
    channel = payload.get("channel", {}).get("id", "")

    drift_table = os.environ.get("DRIFT_TABLE", "carl-drift")

    try:
        detector = DriftDetector(drift_table=drift_table)
        jira = JiraService()

        # Get drift item details
        drift_items = detector.get_drift_items_for_ticketing(limit=100)
        drift_item = next((item for item in drift_items if item.get("drift_id") == drift_id), None)

        if not drift_item:
            slack.post_message(
                channel,
                text=f"❌ Drift item {drift_id} not found"
            )
            return {"statusCode": 200, "body": ""}

        # Check if ticket already exists
        existing_ticket_id = drift_item.get("jira_ticket_id")
        if existing_ticket_id:
            # Verify ticket exists in Jira
            try:
                jira.get_issue(existing_ticket_id)
                slack.post_message(
                    channel,
                    text=f"ℹ️ Ticket already exists: {existing_ticket_id}\n{jira.JIRA_URL}/browse/{existing_ticket_id}"
                )
                return {"statusCode": 200, "body": ""}
            except Exception:
                # Ticket doesn't exist in Jira, create new one
                pass

        # Create Jira ticket
        result = jira.create_drift_ticket(
            resource_type=drift_item.get("resource_type", "Unknown"),
            resource_id=drift_item.get("resource_id", ""),
            drift_type=drift_item.get("drift_type", "modified"),
            detected_at=drift_item.get("detected_at", ""),
            expected_state={"attribute": drift_item.get("attribute"), "value": str(drift_item.get("expected_value", ""))},
            actual_state={"attribute": drift_item.get("attribute"), "value": str(drift_item.get("actual_value", ""))},
            drift_details=drift_item.get("description", "")
        )

        ticket_key = result.get("key")
        if ticket_key:
            jira_url = f"{jira.JIRA_URL}/browse/{ticket_key}"

            # Update drift item with ticket ID
            detector.update_drift_jira(
                drift_id=drift_id,
                jira_ticket_id=ticket_key,
                jira_url=jira_url,
                account_id=drift_item.get("account_id")
            )

            slack.post_message(
                channel,
                text=f"✅ Jira ticket created by <@{user_id}>:\n\n"
                     f"🎫 *{ticket_key}*: {drift_item.get('description', 'Drift detected')}\n"
                     f"🔗 {jira_url}"
            )
        else:
            slack.post_message(
                channel,
                text=f"❌ Failed to create Jira ticket for drift {drift_id}"
            )

    except Exception as e:
        logger.exception(f"Error creating ticket for drift {drift_id}")
        slack.post_message(channel, text=f"❌ Error: {str(e)}")

    return {"statusCode": 200, "body": ""}


# ============================================================================
# JIRA INTEGRATION HANDLERS
# ============================================================================

def handle_jira_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """
    Handle /carl jira command.

    Subcommands:
    - /carl jira test - Test Jira connection
    - /carl jira sync - Manually sync findings to Jira
    - /carl jira status - Show Jira integration status
    """
    parts = args.split(maxsplit=1)
    subcommand = parts[0].lower() if parts else "status"
    sub_args = parts[1] if len(parts) > 1 else ""

    if subcommand == "test":
        return handle_jira_test(slack, channel_id, user_id)
    elif subcommand == "sync":
        return handle_jira_sync(slack, channel_id, user_id, sub_args)
    elif subcommand == "status":
        return handle_jira_status(slack, channel_id, user_id)
    else:
        slack.post_message(
            channel_id,
            text="Unknown Jira subcommand. Use: test, sync, or `status"
        )
        return {"statusCode": 200, "body": ""}


def handle_jira_test(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Test Jira connection and permissions."""
    try:
        jira_sync = JiraSecuritySync()
        result = jira_sync.test_connection()

        if result["success"]:
            slack.post_message(
                channel_id,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *Jira Connection Successful*\n\n"
                                   f"Project: {result.get('project', 'CARLSEC')}\n"
                                   f"Status: Connected"
                        }
                    }
                ]
            )
        else:
            slack.post_message(
                channel_id,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"❌ *Jira Connection Failed*\n\n"
                                   f"Error: {result.get('error', 'Unknown error')}\n\n"
                                   f"Please check:\n"
                                   f"• Jira URL is correct\n"
                                   f"• API token is valid\n"
                                   f"• Secrets Manager contains credentials"
                        }
                    }
                ]
            )
    except Exception as e:
        logger.error(f"Jira test failed: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Jira test failed: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_jira_sync(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Manually sync findings to Jira (async wrapper)."""
    import boto3
    import json
    import os

    # Post immediate response
    slack.post_message(
        channel_id,
        text="🔄 Starting Jira sync... This may take a few minutes for large numbers of findings."
    )

    try:
        # Invoke Lambda asynchronously to avoid timeout
        lambda_client = boto3.client('lambda')
        function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')

        if function_name:
            try:
                lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='Event',  # Async invocation
                    Payload=json.dumps({
                        'action': 'process_jira_sync_async',
                        'channel_id': channel_id,
                        'user_id': user_id,
                        'args': args
                    })
                )
                logger.info("Async Jira sync invocation successful")
            except Exception as e:
                logger.error(f"Failed to invoke async Jira sync: {e}")
                # Fallback to synchronous if async fails
                return handle_jira_sync_sync(slack, channel_id, user_id, args)
        else:
            # Not running in Lambda, do synchronous
            return handle_jira_sync_sync(slack, channel_id, user_id, args)

    except Exception as e:
        logger.error(f"Error starting Jira sync: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Failed to start Jira sync: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_jira_sync_sync(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Synchronous version of Jira sync - does the actual work."""
    try:
        findings_service = get_findings_service()
        jira_sync = JiraSecuritySync()

        # Get findings that need Jira tickets (excludes accepted/ignored/suppressed)
        findings = findings_service.get_findings_for_ticketing(limit=50)

        total_findings = len(findings)
        synced_count = 0
        failed_count = 0
        skipped_count = 0
        recreated_count = 0

        # Post initial progress
        if total_findings > 0:
            slack.post_message(
                channel_id,
                text=f"📋 Processing {total_findings} findings..."
            )

        for idx, finding in enumerate(findings, 1):
            # Check if already has Jira ticket ID in DynamoDB
            existing_ticket_id = finding.get("jira_ticket_id")

            if existing_ticket_id:
                # Verify ticket actually exists in Jira (may have been deleted)
                try:
                    jira_sync.jira.get_issue(existing_ticket_id)
                    # Ticket exists, skip it
                    skipped_count += 1
                    continue
                except Exception as e:
                    # Ticket doesn't exist in Jira anymore - recreate it
                    logger.info(f"Jira ticket {existing_ticket_id} not found, will recreate for finding {finding['id']}")
                    # Clear old ticket ID from DynamoDB
                    findings_service.update_finding(
                        finding_id=finding["id"],
                        account_id=finding.get("account_id", "N/A"),
                        jira_ticket_id=None,
                        jira_url=None,
                        jira_created_at=None
                    )
                    recreated_count += 1
                    # Continue to create new ticket below

            # Sync to Jira (create new ticket)
            result = jira_sync.sync_finding_to_jira(
                finding_id=finding["id"],  # Fixed: use "id" not "finding_id"
                title=finding["title"],
                severity=finding["severity"],
                resource_type=finding.get("resource_type", "Unknown"),
                resource_id=finding["resource_id"],
                compliance_status=finding.get("compliance_status", "FAILED"),
                recommendation=finding.get("remediation_steps", "Review this finding"),  # Fixed: use "remediation_steps"
                aws_account_id=finding.get("account_id", "N/A"),  # Fixed: use "account_id"
                region=finding.get("region", "us-east-1"),
                metadata={"control_ids": finding.get("control_ids", [])}  # Pass SOC 2 controls for AI ticket generation
            )

            if result["success"]:
                synced_count += 1
            else:
                failed_count += 1
                logger.error(f"Failed to sync finding {finding['id']}: {result.get('error')}")

            # Post progress updates every 5 findings or at 25%, 50%, 75% milestones
            if total_findings > 5:
                if idx % 5 == 0 or idx in [total_findings // 4, total_findings // 2, total_findings * 3 // 4]:
                    progress_pct = int((idx / total_findings) * 100)
                    slack.post_message(
                        channel_id,
                        text=f"⏳ Progress: {idx}/{total_findings} ({progress_pct}%) - {synced_count} synced, {skipped_count} skipped"
                    )

        # Report results
        result_text = f"✅ Jira Sync Complete\n\n"
        result_text += f"• Synced: {synced_count} new tickets\n"
        result_text += f"• Skipped: {skipped_count} (tickets already exist)\n"

        if recreated_count > 0:
            result_text += f"• Recreated: {recreated_count} (tickets were deleted in Jira)\n"

        result_text += f"• Failed: {failed_count}"

        slack.post_message(
            channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": result_text
                    }
                }
            ]
        )

    except Exception as e:
        logger.error(f"Jira sync failed: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Jira sync failed: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_drift_jira_sync(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Sync drift items to Jira tickets (async wrapper)."""
    import boto3
    import json
    import os

    # Post immediate response
    slack.post_message(
        channel_id,
        text="🔄 Starting Jira sync for drift items... This may take a few minutes."
    )

    try:
        # Invoke Lambda asynchronously to avoid timeout
        lambda_client = boto3.client('lambda')
        function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')

        if function_name:
            try:
                lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='Event',  # Async invocation
                    Payload=json.dumps({
                        'action': 'process_drift_jira_sync_async',
                        'channel_id': channel_id,
                        'user_id': user_id
                    })
                )
                logger.info("Async drift Jira sync invocation successful")
            except Exception as e:
                logger.error(f"Failed to invoke async drift Jira sync: {e}")
                # Fallback to synchronous if async fails
                return handle_drift_jira_sync_sync(slack, channel_id, user_id)
        else:
            # Not running in Lambda, do synchronous
            return handle_drift_jira_sync_sync(slack, channel_id, user_id)

    except Exception as e:
        logger.error(f"Error starting drift Jira sync: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Failed to start drift Jira sync: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_drift_jira_sync_sync(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Synchronous version of drift Jira sync - does the actual work."""
    try:
        from services.drift_detector import DriftDetector
        from services.jira_service import JiraService
        import os

        drift_table = os.environ.get("DRIFT_TABLE", "carl-drift")
        detector = DriftDetector(drift_table=drift_table)
        jira = JiraService()

        # Get drift items that need Jira tickets
        drift_items = detector.get_drift_items_for_ticketing(limit=50)

        total_items = len(drift_items)
        synced_count = 0
        failed_count = 0
        skipped_count = 0
        recreated_count = 0

        # Post initial progress
        if total_items > 0:
            slack.post_message(
                channel_id,
                text=f"📋 Processing {total_items} drift items..."
            )

        for idx, item in enumerate(drift_items, 1):
            drift_id = item.get("drift_id")

            # Check if already has Jira ticket ID in DynamoDB
            existing_ticket_id = item.get("jira_ticket_id")

            if existing_ticket_id:
                # Verify ticket actually exists in Jira (may have been deleted)
                try:
                    jira.get_issue(existing_ticket_id)
                    # Ticket exists, skip it
                    skipped_count += 1
                    continue
                except Exception as e:
                    # Ticket doesn't exist in Jira anymore - recreate it
                    logger.info(f"Jira ticket {existing_ticket_id} not found, will recreate for drift {drift_id}")
                    # Clear old ticket ID from DynamoDB
                    detector.update_drift_jira(
                        drift_id=drift_id,
                        jira_ticket_id="",
                        jira_url="",
                        account_id=item.get("account_id")
                    )
                    recreated_count += 1
                    # Continue to create new ticket below

            # Create Jira ticket
            try:
                result = jira.create_drift_ticket(
                    resource_type=item.get("resource_type", "Unknown"),
                    resource_id=item.get("resource_id", ""),
                    drift_type=item.get("drift_type", "modified"),
                    detected_at=item.get("detected_at", ""),
                    expected_state={"attribute": item.get("attribute"), "value": str(item.get("expected_value", ""))},
                    actual_state={"attribute": item.get("attribute"), "value": str(item.get("actual_value", ""))},
                    drift_details=item.get("description", "")
                )

                ticket_key = result.get("key")
                if ticket_key:
                    # Update drift item with Jira ticket info
                    jira_url = f"{jira.JIRA_URL}/browse/{ticket_key}"
                    detector.update_drift_jira(
                        drift_id=drift_id,
                        jira_ticket_id=ticket_key,
                        jira_url=jira_url,
                        account_id=item.get("account_id")
                    )
                    synced_count += 1
                else:
                    failed_count += 1
                    logger.error(f"Failed to create Jira ticket for drift {drift_id}")

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to sync drift {drift_id}: {e}")

            # Post progress updates every 5 items or at 25%, 50%, 75% milestones
            if total_items > 5:
                if idx % 5 == 0 or idx in [total_items // 4, total_items // 2, total_items * 3 // 4]:
                    progress_pct = int((idx / total_items) * 100)
                    slack.post_message(
                        channel_id,
                        text=f"⏳ Progress: {idx}/{total_items} ({progress_pct}%) - {synced_count} synced, {skipped_count} skipped"
                    )

        # Report results
        result_text = f"✅ Drift Jira Sync Complete\n\n"
        result_text += f"• Synced: {synced_count} new tickets\n"
        result_text += f"• Skipped: {skipped_count} (tickets already exist)\n"

        if recreated_count > 0:
            result_text += f"• Recreated: {recreated_count} (tickets were deleted in Jira)\n"

        result_text += f"• Failed: {failed_count}"

        slack.post_message(
            channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": result_text
                    }
                }
            ]
        )

    except Exception as e:
        logger.error(f"Drift Jira sync failed: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Drift Jira sync failed: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_jira_status(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Show Jira integration status."""
    try:
        findings_service = get_findings_service()
        findings = findings_service.get_recent_findings(limit=100)

        total_findings = len(findings)
        with_jira = sum(1 for f in findings if f.get("jira_ticket_id"))
        without_jira = total_findings - with_jira

        # Get exception and drift stats
        exceptions_table = get_table("carl-risk-exceptions")
        drift_table = get_table(os.environ.get("DRIFT_TABLE", "carl-dev-drift"))

        exceptions_scan = exceptions_table.scan(
            ProjectionExpression="exception_id, jira_ticket_id"
        )
        total_exceptions = len(exceptions_scan.get("Items", []))
        exceptions_with_jira = sum(1 for e in exceptions_scan.get("Items", []) if e.get("jira_ticket_id"))

        drift_scan = drift_table.scan(
            ProjectionExpression="drift_id, jira_ticket_id"
        )
        total_drift = len(drift_scan.get("Items", []))
        drift_with_jira = sum(1 for d in drift_scan.get("Items", []) if d.get("jira_ticket_id"))

        slack.post_message(
            channel_id,
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "📊 Jira Integration Status"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Findings*\n{with_jira}/{total_findings} have Jira tickets"},
                        {"type": "mrkdwn", "text": f"*Exceptions*\n{exceptions_with_jira}/{total_exceptions} have Jira tickets"}
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Configuration Drift*\n{drift_with_jira}/{total_drift} have Jira tickets"},
                        {"type": "mrkdwn", "text": f"*Coverage*\n{int((with_jira/total_findings*100) if total_findings > 0 else 0)}% synced"}
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "Run /carl jira sync` to sync remaining findings"}
                    ]
                }
            ]
        )

    except Exception as e:
        logger.error(f"Failed to get Jira status: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Failed to get Jira status: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_compliance_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """
    Handle /carl compliance command.

    Subcommands:
    - /carl compliance assess - Run complete SOC 2 compliance assessment
    - /carl compliance status - Show current compliance status
    """
    parts = args.split(maxsplit=1)
    subcommand = parts[0].lower() if parts else "status"
    sub_args = parts[1] if len(parts) > 1 else ""

    if subcommand == "assess":
        return handle_compliance_assess(slack, channel_id, user_id, sub_args)
    elif subcommand == "status":
        return handle_compliance_status(slack, channel_id, user_id)
    else:
        slack.post_message(
            channel_id,
            text="Unknown compliance subcommand. Use: assess or `status"
        )

    return {"statusCode": 200, "body": ""}


def handle_compliance_assess(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Run complete compliance assessment (async wrapper)."""
    import boto3
    import json
    import os

    # Post immediate response
    slack.post_message(
        channel_id,
        text="🔍 Starting comprehensive SOC 2 compliance assessment...\n\nThis will take 3-5 minutes to:\n• Scan AWS environment intelligently\n• Detect patterns and root causes\n• Analyze SOC 2 control coverage\n• Generate phased remediation plan\n• Create Jira epic with stories\n\nI'll post results when complete."
    )

    try:
        # Invoke Lambda asynchronously to avoid timeout
        lambda_client = boto3.client('lambda')
        function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')

        if function_name:
            try:
                lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType='Event',  # Async invocation
                    Payload=json.dumps({
                        'action': 'process_compliance_assess_async',
                        'channel_id': channel_id,
                        'user_id': user_id,
                        'args': args
                    })
                )
                logger.info("Async compliance assessment invocation successful")
            except Exception as e:
                logger.error(f"Failed to invoke async compliance assessment: {e}")
                # Fallback to synchronous if async fails
                return handle_compliance_assess_sync(slack, channel_id, user_id, args)
        else:
            # Not running in Lambda, do synchronous
            return handle_compliance_assess_sync(slack, channel_id, user_id, args)

    except Exception as e:
        logger.error(f"Error starting compliance assessment: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Failed to start compliance assessment: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_compliance_assess_sync(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Synchronous version - compliance assessment (not yet implemented)."""
    slack.post_message(
        channel_id,
        text="⚠️ Autonomous compliance assessment is planned for a future release.\n\nFor now, you can use:\n• /carl evidence collect - Collect compliance evidence\n• /carl jira sync - Create Jira tickets for findings\n• /carl drift scan - Check for infrastructure drift\n• /carl status - View compliance posture summary"
    )
    return {"statusCode": 200, "body": ""}


def handle_compliance_status(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Show current compliance status."""
    try:
        findings_service = get_findings_service()
        findings = findings_service.get_recent_findings(limit=100)

        # Calculate basic compliance metrics
        total_findings = len(findings)
        critical_findings = sum(1 for f in findings if f.get("severity") == "CRITICAL")
        high_findings = sum(1 for f in findings if f.get("severity") == "HIGH")

        # Estimate coverage (simplified)
        estimated_coverage = max(0, 100 - (critical_findings * 5 + high_findings * 2))

        slack.post_message(
            channel_id,
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "📊 Compliance Status"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Estimated Coverage:*\n~{estimated_coverage}%"},
                        {"type": "mrkdwn", "text": f"*Total Findings:*\n{total_findings}"}
                    ]
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Critical:*\n{critical_findings}"},
                        {"type": "mrkdwn", "text": f"*High:*\n{high_findings}"}
                    ]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "💡 Run /carl compliance assess` for complete SOC 2 analysis with remediation plan."
                    }
                }
            ]
        )

    except Exception as e:
        logger.error(f"Compliance status failed: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Failed to get compliance status: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_create_jira_ticket_action(payload: dict, action: dict) -> dict:
    """Handle 'Create Jira Ticket' button click."""
    action_id = action.get("action_id", "")
    finding_id = action_id.replace("create_jira_ticket_", "")

    channel_id = payload.get("channel", {}).get("id")
    user_id = payload.get("user", {}).get("id")

    slack = get_slack_service()

    # Acknowledge button click
    slack.post_message(
        channel_id,
        thread_ts=payload.get("message", {}).get("ts"),
        text=f"🔄 Creating Jira ticket for finding {finding_id}..."
    )

    try:
        # Get finding details
        findings_table = get_table("carl-findings")
        response = findings_table.get_item(Key={"finding_id": finding_id})
        finding = response.get("Item")

        if not finding:
            slack.post_message(
                channel_id,
                thread_ts=payload.get("message", {}).get("ts"),
                text=f"❌ Finding not found: {finding_id}"
            )
            return {"statusCode": 200, "body": ""}

        # Create Jira ticket
        jira_sync = JiraSecuritySync()
        result = jira_sync.sync_finding_to_jira(
            finding_id=finding["finding_id"],
            title=finding["title"],
            severity=finding["severity"],
            resource_type=finding.get("resource_type", "Unknown"),
            resource_id=finding["resource_id"],
            compliance_status=finding.get("compliance_status", "FAILED"),
            recommendation=finding.get("recommendation", "Review this finding"),
            aws_account_id=finding.get("aws_account_id", "N/A"),
            region=finding.get("region", "us-east-1")
        )

        if result["success"]:
            slack.post_message(
                channel_id,
                thread_ts=payload.get("message", {}).get("ts"),
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *Jira Ticket Created*\n\n"
                                   f"Ticket: <{result['jira_url']}|{result['jira_key']}>\n"
                                   f"Finding: `{finding_id}"
                        }
                    }
                ]
            )
        else:
            slack.post_message(
                channel_id,
                thread_ts=payload.get("message", {}).get("ts"),
                text=f"❌ Failed to create Jira ticket: {result.get('error', 'Unknown error')}"
            )

    except Exception as e:
        logger.error(f"Failed to create Jira ticket for finding {finding_id}: {e}")
        slack.post_message(
            channel_id,
            thread_ts=payload.get("message", {}).get("ts"),
            text=f"❌ Failed to create Jira ticket: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}
