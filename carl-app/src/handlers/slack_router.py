"""
CARL Slack Router Lambda Handler

Routes incoming Slack events, commands, and interactions to appropriate handlers.
"""

import hashlib
import hmac
import json
import os
import time
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
                            "text": f"```{code_text}```"
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

        # Handle headers (## heading)
        if line.startswith('## '):
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

            # Add header and divider
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{line[3:].strip()}*"
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

    if event.get("action") == "process_jira_sync_async":
        logger.info("Processing async Jira sync")
        slack = get_slack_service()
        return handle_jira_sync_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("args", "")
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
            text=f"✅ Configuration received! Generating {blueprint_name} with CIDR `{config.get('cidr')}`..."
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
            text=f"✅ Configuration received! Generating {blueprint_name} with bucket name `{config.get('name')}`..."
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
                           f"2. Run `/carl findings` to see all issues\n" +
                           f"3. Run `/carl jira sync` to create tickets\n" +
                           f"4. Run `/carl evidence collect` to refresh data"
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
            f"Resource: `{finding.get('resource_id', 'N/A')}`\n"
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
            text='Usage: `/carl findings accept <finding_id> "<justification>"`\nExample: `/carl findings accept finding-04a95 "Dev environment, accepted risk"`'
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
                        "text": f"✅ Risk accepted for finding `{finding_id}`\n\n*Justification:* {justification}\n*Accepted by:* <@{user_id}>"
                    }
                }
            ]
        )
    else:
        slack.post_message(
            channel_id,
            text=f"❌ Failed to accept risk for finding `{finding_id}`. Finding may not exist."
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
            text='Usage: `/carl findings ignore <finding_id>`\nExample: `/carl findings ignore finding-04a95`'
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
                        "text": f"👁️ Finding `{finding_id}` marked as ignored\n*By:* <@{user_id}>"
                    }
                }
            ]
        )
    else:
        slack.post_message(
            channel_id,
            text=f"❌ Failed to ignore finding `{finding_id}`. Finding may not exist."
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
            text='Usage: `/carl findings create-ticket <finding_id> [<finding_id> ...]`\nExample: `/carl findings create-ticket finding-04a95 finding-9f705`'
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
            result_text.append(f"  • `{fid}` → <{ticket_url}|{ticket_id}>")

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
                "text": "Please provide a question. Example: `/carl ask What is my S3 compliance status?`"
            })
        }

    # Post "Thinking..." message via Slack API (not in HTTP response)
    slack.post_message(channel_id, text=f"🤔 Thinking about: _{question}_...")

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


def handle_ask_command_sync(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """Synchronous version of ask command - uses Advisory Agent."""
    import os
    from services.advisory_agent import AdvisoryAgent

    # Check if Advisory Agent is configured
    advisory_agent_id = os.environ.get("ADVISORY_AGENT_ID")

    if not advisory_agent_id:
        logger.warning("Advisory Agent not configured, falling back to basic Q&A")
        return handle_ask_command_fallback(slack, channel_id, user_id, question)

    logger.info(f"Invoking Advisory Agent for question: {question[:100]}...")

    try:
        # Initialize Advisory Agent
        agent = AdvisoryAgent(agent_id=advisory_agent_id)

        # Invoke the agent
        result = agent.ask_question(
            question=question,
            session_id=f"slack-{user_id}-{channel_id}",
            enable_trace=False
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            slack.post_message(
                channel_id,
                text=f"❌ Advisory Agent encountered an error: {error_msg}"
            )
            return {"statusCode": 200, "body": ""}

        # Get the agent's response
        response_text = result.get('response', 'No response from agent.')
        actions_taken = result.get('actions', [])

        # Format and post response
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "💬 CARL Advisory Agent"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": response_text
                }
            }
        ]

        # Show actions taken if any
        if actions_taken:
            actions_text = "\n".join([f"• {action.get('action', 'Unknown action')}" for action in actions_taken[:3]])
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🔍 Agent actions: {len(actions_taken)} steps\n{actions_text}"
                    }
                ]
            })

        slack.post_message(channel_id, blocks=blocks)

        return {"statusCode": 200, "body": ""}

    except Exception as e:
        logger.exception(f"Advisory Agent failed: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Advisory Agent failed: {str(e)}\n\nFalling back to basic Q&A..."
        )
        return handle_ask_command_fallback(slack, channel_id, user_id, question)


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
    architecture_keywords = [
        "design", "build", "create", "architect", "recommend", "best practice",
        "should i use", "what service", "which is better", "how to implement",
        "what's the best way", "how much would", "cost estimate", "pricing",
        "options for", "alternatives to"
    ]

    compliance_keywords = [
        "is my", "are my", "do i have", "am i", "show me", "check",
        "configured", "enabled", "compliant", "secure", "vulnerability",
        "findings", "status of"
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


def handle_ask_command_fallback(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """
    Fallback ask command - Comprehensive AWS scanning for compliance questions.
    """
    import os
    import json
    import time
    from services.evidence_collector import EvidenceCollector
    from services.scanning_tools import create_scanning_tools
    from services.agent_core import Agent
    from services.learning_service import LearningService

    # Get Bedrock service for final response generation
    bedrock = get_bedrock_service()

    logger.info(f"Processing ask command: {question}")

    # Classify question type first
    question_type = classify_question_type(question)
    logger.info(f"Question classified as: {question_type}")

    # Route to appropriate handler
    if question_type == "architecture":
        logger.info("Routing to architecture agent")
        return handle_architecture_question(slack, channel_id, user_id, question)

    # Continue with compliance/scanning agent
    logger.info("Processing as compliance question with comprehensive AWS scanning")

    # Track for learning
    scan_start_time = time.time()
    scans_performed = []
    resources_found = []

    context = ""

    # Use comprehensive AWS environment scanner
    try:
        # Perform comprehensive AWS environment scan
        from services.aws_environment_scanner import AWSEnvironmentScanner

        logger.info("🔍 Performing comprehensive AWS environment scan...")
        slack.post_message(channel_id, text="🔍 Scanning your AWS environment to answer your question...")

        scanner = AWSEnvironmentScanner(region="us-east-1")
        scan_result = scanner.scan()
        environment_summary = scan_result.to_context_summary()

        logger.info(f"✅ Scan complete: {len(scan_result.networking.vpcs)} VPCs, "
                   f"{len(scan_result.databases.rds_instances)} RDS, "
                   f"{len(scan_result.compute.ec2_instances)} EC2")

        # Initialize learning service
        scan_history_table = os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history")
        resource_graph_table = os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")

        learning_service = LearningService(
            scan_history_table=scan_history_table,
            resource_graph_table=resource_graph_table
        )

        # Get learned context to make agent smarter
        learned_context = learning_service.get_learned_context(question, interaction_type="ask")

        # Build comprehensive context
        context = environment_summary

        # Add learned context if available
        if learned_context:
            context += f"\n\n{learned_context}"

        # Track scans performed
        scans_performed = ["comprehensive_aws_scan"]

        # Track resources found
        for vpc in scan_result.networking.vpcs:
            resources_found.append({"type": "vpc", "id": vpc.vpc_id})
        for db in scan_result.databases.rds_instances:
            resources_found.append({"type": "rds", "id": db['identifier']})
        for instance in scan_result.compute.ec2_instances:
            resources_found.append({"type": "ec2", "id": instance['instance_id']})

    except Exception as e:
        logger.error(f"Comprehensive AWS scanning failed: {e}", exc_info=True)
        context += f"\nNote: Environment scan encountered an error: {str(e)}\n\n"
        slack.post_message(channel_id, text=f"⚠️ Environment scan encountered an error, proceeding with available information...")

    # Generate AI response using scan data
    # Note: No stored findings lookup - /carl ask is scan-first
    # For stored findings, users should use /carl status or /carl findings
    response = bedrock.ask_compliance_question(question, context)

    # Calculate scan duration
    scan_duration_ms = int((time.time() - scan_start_time) * 1000)

    # Log interaction for learning (fire and forget - don't block on errors)
    interaction_id = None
    try:
        learning_service = LearningService(
            scan_history_table=os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history"),
            resource_graph_table=os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")
        )

        interaction_id = learning_service.log_interaction(
            user_id=user_id,
            question=question,
            scans_performed=scans_performed,
            resources_found=resources_found,
            scan_duration_ms=scan_duration_ms,
            metadata={"channel_id": channel_id}
        )

        logger.info(f"Logged interaction {interaction_id} for learning")
    except Exception as e:
        logger.warning(f"Failed to log interaction for learning: {e}")

    # Format and post response with better structure
    formatted_blocks = format_markdown_to_blocks(response, "💬 CARL's Response")
    for block_group in formatted_blocks:
        slack.post_message(channel_id, blocks=block_group)

    # Add feedback buttons if interaction was logged
    if interaction_id:
        feedback_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Was this answer helpful?_"
                }
            },
            {
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
            }
        ]

        slack.post_message(channel_id, blocks=feedback_blocks)

    return {"statusCode": 200, "body": ""}


def handle_help_command(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Handle /carl help command."""
    help_text = """
*CARL - Cloud Automated Risk & Compliance Logic*

*Setup & Configuration:*
- `/carl setup start` - Initial setup wizard (first-time setup)
- `/carl setup status` - View setup status
- `/carl settings` - View current configuration

*Compliance Commands:*
- `/carl status` - View compliance posture summary
- `/carl findings list [severity]` - List recent findings with interactive buttons
- `/carl findings accept <id> '<justification>'` - Accept risk with documented justification
- `/carl findings ignore <id>` - Ignore a finding (will not create ticket)
- `/carl findings create-ticket <id> [<id> ...]` - Create Jira tickets for specific findings
- `/carl ask <question>` - Ask compliance questions

*Architecture & Build Commands:*
- `/carl recommend <requirement>` - Get architecture recommendations with cost comparison
- `/carl build <blueprint>` - Generate compliant Terraform code
- `/carl estimate <component>` - Get cost estimates
- `/carl blueprints` - List available infrastructure blueprints

*Foundation Builder:*
- `/carl foundation start` - Start guided foundation building wizard
- `/carl foundation status` - Check current foundation session
- `/carl patterns [category]` - View architecture patterns with pros/cons

*AI Architecture Advisor:*
- `/carl architect <question>` - Ask AI for architecture recommendations (learns from feedback)

*Audit & Evidence:*
- `/carl evidence collect` - Collect audit evidence across all resources
- `/carl evidence list [type]` - View all collected evidence items
- `/carl evidence status` - View evidence collection status
- `/carl report executive` - Generate executive compliance summary
- `/carl report full` - Generate full audit report
- `/carl report control <control-id>` - Generate control-specific report

*Risk Management:*
- `/carl exception request` - Request a risk exception
- `/carl exception list` - View pending/active exceptions
- `/carl exception approve <id>` - Approve an exception (requires permission)

*Drift Detection:*
- `/carl drift scan` - Run drift detection scan
- `/carl drift status` - View current drift summary
- `/carl drift details <drift-id>` - View drift item details

*Jira Integration:*
- `/carl jira test` - Test Jira connection and permissions
- `/carl jira sync` - Sync findings to Jira tickets
- `/carl jira status` - View Jira integration statistics

*Coming Soon:*
- `/carl remediate <finding-id>` - Request auto-remediation

*Examples:*
- `/carl foundation start` - Build your AWS foundation from scratch
- `/carl patterns egress` - See egress architecture options
- `/carl recommend compliant VPC with firewall`
- `/carl build networking/standard-vpc`
- `/carl estimate rds multi-az db.r5.large`
"""

    slack.post_message(channel_id, text=help_text)

    return {"statusCode": 200, "body": ""}


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
            slack.post_message(channel_id, text="❌ Failed to get workspace information.\n\nPlease ensure the CARL bot has the `team:read` OAuth scope.")
            return {"statusCode": 500, "body": str(e)}

    if subcommand == "start":
        # Check if already set up
        if setup.is_setup_complete(workspace_id):
            slack.post_message(
                channel_id,
                text="✅ *CARL is already set up!*\n\n"
                     "Use `/carl settings` to view or update your configuration.\n"
                     "Use `/carl setup reset` to run the setup wizard again."
            )
            return {"statusCode": 200, "body": ""}

        # Run connectivity validation
        slack.post_message(channel_id, text="🔍 *Welcome to CARL Setup!*\n\nValidating connectivity...")

        validation_results = setup.validate_connectivity()
        validation_text = setup.format_validation_results(validation_results)

        # Check if any services have critical errors (not warnings)
        has_errors = any(result.get("status") == "error" for result in validation_results.values())

        if has_errors:
            slack.post_message(
                channel_id,
                text=f"❌ *Setup Validation Failed*\n\n{validation_text}\n\n"
                     "Please fix the connectivity issues before proceeding with setup.\n"
                     "Contact your administrator if you need help."
            )
            return {"statusCode": 200, "body": ""}

        # Validation passed, show success and start wizard
        slack.post_message(
            channel_id,
            text=f"✅ *Validation Complete!*\n\n{validation_text}\n\n"
                 "Ready to configure CARL for your team!"
        )

        # Enable critical security services if not already enabled
        slack.post_message(
            channel_id,
            text="🔧 *Enabling Critical Security Services*\n\nChecking and enabling Security Hub and AWS Config..."
        )

        try:
            from services.security_services_enabler import SecurityServicesEnabler

            enabler = SecurityServicesEnabler()
            security_results = enabler.check_and_enable_all()

            # Format results
            sh_status = security_results["security_hub"]["status"]
            config_status = security_results["config"]["status"]

            security_text = "*Security Services Status:*\n\n"

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
                text=f"⚠️ *Warning:* Could not enable security services automatically.\n\n"
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
                text="⚠️ Please run `/carl setup start` again to open the configuration wizard."
            )
            return {"statusCode": 200, "body": ""}

    elif subcommand == "reset":
        # Allow re-running setup
        setup.update_workspace_config(workspace_id, {"setup_complete": False})
        slack.post_message(
            channel_id,
            text="✅ Setup has been reset. Run `/carl setup start` to begin again."
        )
        return {"statusCode": 200, "body": ""}

    elif subcommand == "status":
        # Show current setup status
        config = setup.get_workspace_config(workspace_id)
        if not config:
            slack.post_message(
                channel_id,
                text="⚠️ CARL has not been set up yet. Run `/carl setup start` to begin."
            )
        else:
            status_text = f"""*CARL Setup Status*

*Setup Complete:* {"✅ Yes" if config.get("setup_complete") else "❌ No"}
*Notification Channel:* {f"<#{config.get('notification_channel')}>" if config.get('notification_channel') else "Not set"}
*Scan Schedule:* {config.get('scan_schedule', 'Not set')}
*Scan Regions:* {', '.join(config.get('scan_regions', [])) or 'Not set'}
*Auto-scan on Deploy:* {"✅ Enabled" if config.get('auto_scan_on_deploy') else "❌ Disabled"}
*Compliance Frameworks:* {', '.join(config.get('compliance_frameworks', [])) or 'Not set'}

Run `/carl settings` to update configuration."""
            slack.post_message(channel_id, text=status_text)
        return {"statusCode": 200, "body": ""}

    else:
        slack.post_message(
            channel_id,
            text="❌ Unknown setup command.\n\n"
                 "*Available commands:*\n"
                 "• `/carl setup start` - Start setup wizard\n"
                 "• `/carl setup status` - View setup status\n"
                 "• `/carl setup reset` - Reset and re-run setup"
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
            slack.post_message(channel_id, text="❌ Failed to get workspace information.\n\nPlease ensure the CARL bot has the `team:read` OAuth scope.")
            return {"statusCode": 500, "body": str(e)}

    config = setup.get_workspace_config(workspace_id)

    if not config or not config.get("setup_complete"):
        slack.post_message(
            channel_id,
            text="⚠️ CARL has not been set up yet. Run `/carl setup start` to begin."
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
                "text": "*Need to update settings?*\nRun `/carl setup start` to re-configure."
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
                text="You already have a foundation session in progress. Use `/carl foundation status` to continue or `/carl foundation cancel` to start over.",
            )
            return {"statusCode": 200, "body": ""}

        # Create new session
        session = engine.create_session(user_id, channel_id)
        first_question = engine.get_next_question(session)

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "AWS Foundation Builder"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Welcome to the CARL Foundation Builder. "
                        "I'll guide you through a series of questions to understand your requirements, "
                        "then recommend the best architecture with accurate cost estimates.\n\n"
                        "Each recommendation includes:\n"
                        "• *Pros and cons* for informed decisions\n"
                        "• *Accurate AWS pricing* (no wild assumptions)\n"
                        "• *SOC 2 control mappings*\n"
                        "• *Ready-to-deploy Terraform code*"
                    ),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question 1:* {first_question['question']}\n\n_{first_question['description']}_",
                },
            },
        ]

        # Add options as buttons or dropdown
        if "options" in first_question:
            elements = []
            for opt in first_question["options"]:
                elements.append({
                    "type": "button",
                    "text": {"type": "plain_text", "text": opt["label"][:75]},
                    "value": opt["value"],
                    "action_id": f"foundation_answer_{session.session_id}_{first_question['id']}_{opt['value']}",
                })
            blocks.append({
                "type": "actions",
                "elements": elements[:5],  # Max 5 buttons per action block
            })
            if len(elements) > 5:
                blocks.append({
                    "type": "actions",
                    "elements": elements[5:],
                })

        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Session ID: `{session.session_id[:8]}...` | Use `/carl foundation cancel` to exit"}
            ],
        })

        slack.post_message(channel_id, blocks=blocks)
        return {"statusCode": 200, "body": ""}

    elif subcommand == "status":
        session = engine.get_user_session(user_id, channel_id)
        if not session:
            slack.post_message(
                channel_id,
                text="No active foundation session. Use `/carl foundation start` to begin.",
            )
            return {"statusCode": 200, "body": ""}

        # Show current session status
        progress = f"{session.current_question_index}/{len(engine.get_all_patterns()) + 10}"
        collected = "\n".join([f"• {k}: {v}" for k, v in session.requirements.items()])

        slack.post_message(
            channel_id,
            text=f"*Foundation Session Status*\n\nProgress: {progress}\nState: {session.state.value}\n\n*Collected Requirements:*\n{collected or 'None yet'}",
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
            text="Unknown foundation command. Use `start`, `status`, or `cancel`.",
        )
        return {"statusCode": 200, "body": ""}


def handle_patterns_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl patterns command - view architecture patterns with pros/cons."""
    from knowledge.architecture_patterns import get_pattern_by_category, get_all_patterns

    category = args.strip().lower() if args else ""

    if not category:
        # List all pattern categories with better formatting
        patterns = get_all_patterns()

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
        other_patterns = []

        for cat, p in patterns.items():
            emoji = "🌐" if cat in ["egress", "ingress", "transit", "dns", "inspection"] else \
                    "🔒" if cat in ["landing_zone", "client_vpn", "site_to_site_vpn"] else "📊"

            pattern_line = f"{emoji} *`{cat}`*\n_{p.question}_"

            if cat in ["egress", "ingress", "transit", "dns", "inspection"]:
                networking_patterns.append(pattern_line)
            elif cat in ["landing_zone", "client_vpn", "site_to_site_vpn"]:
                security_patterns.append(pattern_line)
            else:
                other_patterns.append(pattern_line)

        if networking_patterns:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Networking Patterns:*\n" + "\n\n".join(networking_patterns)
                }
            })
            blocks.append({"type": "divider"})

        if security_patterns:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Security Patterns:*\n" + "\n\n".join(security_patterns)
                }
            })
            blocks.append({"type": "divider"})

        if other_patterns:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Other Patterns:*\n" + "\n\n".join(other_patterns)
                }
            })

        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": "💡 Use `/carl patterns <category>` to see detailed comparisons"
            }]
        })

        slack.post_message(channel_id, blocks=blocks)
        return {"statusCode": 200, "body": ""}

    pattern = get_pattern_by_category(category)
    if not pattern:
        slack.post_message(
            channel_id,
            text=f"Unknown category: `{category}`. Use `/carl patterns` to see available categories.",
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
            "text": f"*💡 Decision Framework:*\n```{logic_preview}```",
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
            text="Please describe what you need. Example: `/carl recommend I need a compliant VPC with WAF`",
        )
        return {"statusCode": 200, "body": ""}

    # Post "Analyzing..." message
    slack.post_message(channel_id, text=f"🔍 Analyzing architecture options for: _{requirement}_...")

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
    Synchronous version of recommend command - uses NEW architecture agent.

    This is essentially the same as handle_architecture_question but triggered by /carl recommend.
    """
    import time
    from services.agent_core import Agent
    from services.architecture_tools import create_architecture_tools
    from services.learning_service import LearningService
    # Note: format_markdown_to_blocks is defined in this same file, no import needed

    logger.info(f"Processing /carl recommend: {requirement[:100]}...")

    # Track timing
    start_time = time.time()
    tools_used = []
    components_mentioned = []

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

IMPORTANT: Do NOT use markdown asterisks. Use plain text - the system will format it for Slack.
"""

        # Add learned context if available
        if learned_context:
            base_instructions += learned_context

        # Create progress callback to update Slack in real-time
        def progress_callback(status_message: str):
            """Post progress updates to Slack as agent works."""
            try:
                slack.post_message(channel_id, text=status_message)
            except Exception as e:
                logger.warning(f"Failed to post progress update: {e}")

        # Create architecture agent with progress callback
        architecture_agent = Agent(
            tools=architecture_tools,
            instructions=base_instructions,
            progress_callback=progress_callback
        )

        # Execute agent (progress updates will be posted automatically)
        logger.info("🏗️ Architecture agent analyzing requirement")
        response = architecture_agent.execute(
            f"Provide architecture recommendation for: {requirement}"
        )

        logger.info(f"Architecture agent response: {response[:500]}...")

        # Intelligently condense if response is too verbose
        if is_response_too_verbose(response):
            response = condense_response(response)

        # Extract tools used and components mentioned (for learning)
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

        tools_used = ["architecture_agent"]

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log interaction for learning
        interaction_id = None
        try:
            interaction_id = learning_service.log_interaction(
                user_id=user_id,
                question=f"/carl recommend: {requirement}",
                scans_performed=tools_used,
                resources_found=components_mentioned,
                scan_duration_ms=duration_ms,
                interaction_type="architecture",
                metadata={"channel_id": channel_id, "command": "recommend"}
            )

            logger.info(f"Logged /carl recommend interaction {interaction_id}")
        except Exception as e:
            logger.warning(f"Failed to log recommend interaction: {e}")

        # Format and post response using native Slack blocks
        # Add header
        header_blocks = [{
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🏗️ Architecture Recommendation"
            }
        }]
        slack.post_message(channel_id, blocks=header_blocks)

        # Parse plain text and create native Slack blocks
        content_blocks = format_recommendation_to_slack_blocks(response)

        # Split into groups of 50 blocks (Slack limit)
        for i in range(0, len(content_blocks), 50):
            block_group = content_blocks[i:i+50]
            slack.post_message(channel_id, blocks=block_group)

        # Store recommendation in session for build flow
        # This allows build to ask "Which option?" instead of starting over
        from services.build_session_service import BuildSessionService
        session_service = BuildSessionService()

        try:
            # Create a recommendation session (not a full build session yet)
            rec_session = session_service.create_session(
                user_id=user_id,
                channel_id=channel_id,
                requirement=requirement,
                environment_scan={"recommendation": response[:4000]},  # Store recommendation
                environment_summary=f"Recommendation generated for: {requirement}"
            )

            # Add "Build This" button that references the recommendation session
            action_blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_Ready to generate Terraform code for one of these options?_"
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"architecture_actions_{interaction_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🏗️ Build This",
                                "emoji": True
                            },
                            "value": f"rec_session:{rec_session.session_id}",
                            "action_id": "architecture_build_from_recommendation",
                            "style": "primary"
                        }
                    ]
                }
            ]
            slack.post_message(channel_id, blocks=action_blocks)
        except Exception as e:
            logger.warning(f"Failed to create recommendation session: {e}")
            # Fallback to old behavior
            action_blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_Ready to generate Terraform code?_"
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"architecture_actions_{interaction_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "🏗️ Build This",
                                "emoji": True
                            },
                            "value": f"build_context:{requirement[:100]}",
                            "action_id": "architecture_build_from_recommendation",
                            "style": "primary"
                        }
                    ]
                }
            ]
            slack.post_message(channel_id, blocks=action_blocks)

        # Add feedback buttons
        if interaction_id:
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
                }
            ]

            slack.post_message(channel_id, blocks=feedback_blocks)

    except Exception as e:
        logger.error(f"Architecture agent failed: {e}", exc_info=True)
        slack.post_message(
            channel_id,
            text=f"❌ Sorry, I encountered an error providing architecture recommendations: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


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
        slack.post_message(channel_id, text=f"Error: {str(e)}. Use `/carl blueprints` to see available options.")

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
                        "text": "ℹ️ *Note:* Your AWS account ID will be automatically appended to ensure global uniqueness.\n\n*Example:* `my-data-bucket` → `my-data-bucket-123456789012`"
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
            slack.post_message(channel_id, text=f"✅ Configuration received! Generating {blueprint_name} with CIDR `{vpc_cidr}`...")
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
        "option_text": option_text
    }

    # Post success message
    vpc_display = f"Create New ({cidr})" if cidr else f"Use Existing ({vpc_id})"
    slack.post_message(
        channel_id,
        text=f"✅ *Configuration Validated!*\n\n"
             f"• VPC: {vpc_display}\n"
             f"• Prefix: `{prefix}`\n"
             f"• Environment: {environment}\n"
             f"• Transit Gateway: {'Yes' if use_tgw == 'yes' else 'No'}\n\n"
             f"🏗️ Generating Terraform code..."
    )

    # Generate Terraform code using AI
    try:
        terraform_code = _generate_terraform_with_ai(terraform_config)
    except Exception as e:
        logger.exception(f"Error generating Terraform: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Failed to generate Terraform code: {str(e)}\n\nPlease try again or contact support."
        )
        return {"statusCode": 200, "body": ""}

    # Post Terraform code to Slack
    slack.post_message(
        channel_id,
        text=f"✅ *Terraform Code Generated!*\n\n```hcl\n{terraform_code[:2500]}```\n\n"
             "📋 *Next Steps:*\n"
             "• Review the generated code\n"
             "• Save to a `.tf` file in your Terraform workspace\n"
             "• Run `terraform init` and `terraform plan`\n"
             "• Apply with `terraform apply` when ready"
    )

    return {"statusCode": 200, "body": ""}


def _generate_terraform_with_ai(config: dict) -> str:
    """Use AI to generate appropriate Terraform based on user's requirement."""
    from services.bedrock_service import BedrockService

    bedrock = BedrockService()

    # Build context for AI
    requirement = config.get("requirement", "infrastructure setup")
    option_text = config.get("option_text", "")
    vpc_info = f"VPC ID: {config['vpc_id']}" if config.get('vpc_id') else f"VPC CIDR: {config['vpc_cidr']}"

    prompt = f"""Generate complete, production-ready Terraform code for the following AWS infrastructure requirement.

**USER'S REQUIREMENT:**
{requirement}

**SELECTED OPTION:**
{option_text}

**CONFIGURATION:**
- {vpc_info}
- Resource Prefix: {config['prefix']}
- Environment: {config['environment']}
- Transit Gateway: {'Yes' if config.get('use_transit_gateway') else 'No'}

**INSTRUCTIONS:**
1. Generate ONLY the Terraform HCL code - no explanations
2. Include terraform {{}} block with required_providers
3. Use data sources for existing resources (VPC ID provided)
4. Create new resources as needed based on the requirement
5. Include proper tags (Name, Environment, ManagedBy = "CARL")
6. Add TODO comments where user input is needed (IPs, ASNs, etc.)
7. Include outputs for all major resources
8. Follow AWS best practices

**CRITICAL:** Generate the COMPLETE infrastructure needed for the requirement, not just a VPC.
For example:
- If VPN mentioned: Include VPN Gateway, Customer Gateway, VPN Connection
- If Direct Connect: Include DX Gateway, Virtual Interface
- If database: Include RDS instance with proper security groups
- If web app: Include ALB, target groups, security groups

Return ONLY the Terraform code, nothing else."""

    terraform_code = bedrock.invoke_model(
        prompt=prompt,
        max_tokens=4096
    )

    return terraform_code


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
            slack.post_message(channel_id, text=f"✅ Configuration received! Generating {blueprint_name} with bucket name `{bucket_name}`...")
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
1. Run `/carl status` to see your compliance posture
2. Try `/carl build networking/standard-vpc` to generate infrastructure
3. Use `/carl ask <question>` for compliance help

*Useful Commands:*
• `/carl help` - View all commands
• `/carl settings` - View current configuration
• `/carl setup reset` - Re-run setup wizard

Ready to help you build compliant infrastructure! 🚀"""
    )

    return {"statusCode": 200, "body": ""}


def handle_deploy_review(payload: dict, action: dict) -> dict:
    """DEPRECATED: Direct deployment removed - infrastructure changes now go through GitHub."""
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]
    slack.post_message(
        channel_id,
        text="⚠️ *Direct deployment has been removed.*\n\n"
             "All infrastructure changes now go through GitHub for proper review and approval.\n\n"
             "Use `/carl build <blueprint>` to generate code and create a Pull Request."
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
1. AWS Direct Connect - Dedicated fiber connection from your datacenter to AWS. Provides consistent low latency and high bandwidth (1-100 Gbps). Best for mission-critical workloads requiring reliable performance. Cost: ~$500-2000/month.
2. Site-to-Site VPN - Encrypted tunnel over the public internet. Quick to set up, lower cost. Best for smaller workloads or testing. Bandwidth up to 1.25 Gbps. Cost: ~$36/month.
3. Both (hybrid redundancy) - Direct Connect as primary with VPN as backup. Best for critical workloads needing guaranteed uptime. Cost: combines both options.
4. Transit Gateway - Central hub connecting multiple VPNs or Direct Connect links. Best for complex multi-site networks with many connections. Cost: ~$36/month + data processing fees.

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
                    text=f"⚠️ I'm having trouble formatting my questions properly. Let me try rephrasing...\n\nRaw response:\n```{questions_response[:500]}```\n\nPlease describe your requirements in more detail and I'll help build your infrastructure."
                )
        else:
            # Unexpected format - no question found
            slack.post_message(
                channel_id,
                text=f"🤔 I analyzed your environment but couldn't determine what questions to ask.\n\nCould you provide more details about your requirements?\n\nWhat I found:\n```{questions_response[:500]}```"
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
            text=f"✓ Recorded: *{answer_option}*"
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
                text=f"✅ *I have everything I need to design your infrastructure!*\n\n{ready_text[:500]}..."
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
                text=f"✅ *I have everything needed!*\n\n{ready_text}\n\n🏗️ Generating Terraform code..."
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
                from services.code_uploader import CodeUploader
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
                    text=f"🎉 *Infrastructure code generated!*\n\nPull Request: {result.get('pr_url', 'N/A')}\n\nReview the code and merge when ready."
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
                    text=f"⚠️ I'm having trouble formatting my next question. Let me provide the information I need:\n\n```{next_response[:500]}```\n\nPlease provide additional details and I'll continue building your infrastructure."
                )
        else:
            # Unexpected response - no question or READY found
            slack.post_message(
                channel_id,
                text=f"🤔 I'm analyzing your requirements but need clarification.\n\nWhat I found:\n```{next_response[:500]}```\n\nPlease provide more details about your requirements."
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
                    "• Or use `/carl build <blueprint>` with a standard blueprint\n\n"
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
            slack.post_message(channel_id, text="❌ Recommendation session expired. Please run `/carl recommend` again.")
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
            slack.post_message(channel_id, text=f"🏗️ Starting build for: _{requirement}_")

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
            text=f"🏗️ Analyzing your AWS environment and determining what's needed for: _{requirement}_\n\nThis may take a moment..."
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
                    "text": f"💰 *Cost Estimate Details*\n\nFor a detailed cost breakdown of *{option_name}*, use the `/carl estimate` command with your specific requirements.\n\n*Example:*\n`/carl estimate {option_name.lower().replace(' ', '-')}`"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 The `/carl estimate` command provides itemized cost breakdowns based on your specific configuration needs."
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
            text="Please specify a component. Example: `/carl estimate rds multi-az 100gb`",
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
                "text": "Use `/carl build <blueprint-name>` to generate Terraform code.",
            },
        },
        {"type": "divider"},
    ]

    for category, bps in categories.items():
        bp_list = "\n".join([f"• `{bp['name']}` - {bp['description']}" for bp in bps])
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
            elif action_id.startswith("approve_remediation_"):
                remediation_id = action_id.replace("approve_remediation_", "")
                return handle_remediation_approval(payload, remediation_id, True)
            elif action_id.startswith("deny_remediation_"):
                remediation_id = action_id.replace("deny_remediation_", "")
                return handle_remediation_approval(payload, remediation_id, False)
            elif action_id.startswith("foundation_answer_"):
                return handle_foundation_answer(payload, action)
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

    return {"statusCode": 200, "body": "OK"}


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

        # Add options
        if "options" in question:
            elements = []
            for opt in question["options"]:
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


def handle_foundation_accept(payload: dict, action: dict) -> dict:
    """Handle acceptance of foundation recommendations - generate code."""
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

    slack.post_message(channel, text="Generating Terraform modules...")

    # Generate the code
    builder = get_foundation_builder()
    modules = builder.generate_foundation(session)

    # Send summary
    summary = builder.format_generated_code_summary(modules, session)
    slack.post_message(channel, text=summary)

    # Upload each module as a file
    for module in modules:
        if module.content and len(module.content) > 100:
            slack.upload_file(
                channels=[channel],
                content=module.content,
                filename=f"{module.name}.tf",
                title=f"Terraform: {module.name}",
                initial_comment=f"Module: {module.description}",
            )

    # Clean up session
    del engine.sessions[session_id]

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
                {"type": "mrkdwn", "text": f"*Resource:* `{finding.get('resource_id', 'N/A')}`"},
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
        slack.post_message(channel, text=f"❌ Finding `{finding_id}` not found.")
        return {"statusCode": 200, "body": ""}

    # Check if already has ticket
    if finding.get('jira_ticket_id'):
        slack.post_message(
            channel,
            text=f"ℹ️ Finding `{finding_id}` already has Jira ticket: {finding['jira_ticket_id']}"
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
                            "text": f"✅ Created Jira ticket for finding `{finding_id}`\n🔗 <{result['jira_url']}|{result['jira_key']}>"
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
        slack.post_message(channel, text=f"❌ Finding `{finding_id}` not found.")
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
                        "text": f"*Finding:* {finding.get('title')}\n*Severity:* {finding.get('severity')}\n*Resource:* `{finding.get('resource_id')}`"
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
                        "text": f"👁️ Finding `{finding_id}` marked as ignored\n*By:* <@{user}>"
                    }
                }
            ]
        )
    else:
        slack.post_message(channel, text=f"❌ Failed to ignore finding `{finding_id}`")

    return {"statusCode": 200, "body": ""}


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
                "• `/carl architect How should I design my VPC for a multi-region deployment?`\n"
                "• `/carl architect Compare Transit Gateway vs VPC Peering for 10 VPCs`\n"
                "• `/carl architect What's the best egress pattern for SOC 2 compliance?`\n"
                "• `/carl architect Design a complete AWS foundation for my startup`\n\n"
                "_Note: `/carl architect` and `/carl recommend` are equivalent - use whichever you prefer!_"
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

        learning_service.record_feedback(interaction_id, was_useful)

        # Update the message to show feedback was recorded
        if was_useful:
            response_text = "✅ Thanks! This helps CARL learn what scans are most useful for your environment."
        else:
            response_text = "📝 Thanks for the feedback! CARL will adjust its scanning strategy to be more helpful."

        # Remove the feedback buttons by updating the message
        slack.post_message(
            channel,
            text=response_text,
            replace_original=True  # This removes the buttons
        )

        logger.info(f"Recorded learning feedback: interaction={interaction_id}, useful={was_useful}, user={user}")

    except Exception as e:
        logger.error(f"Failed to handle learning feedback: {e}", exc_info=True)
        slack.post_message(
            channel,
            text="⚠️ Failed to record feedback, but I appreciate you trying to help me learn!"
        )

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
    from services.evidence_collector import EvidenceCollector

    parts = args.split() if args else []
    subcommand = parts[0].lower() if parts else "status"

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")

    try:
        collector = EvidenceCollector(
            evidence_bucket=evidence_bucket,
            evidence_table=evidence_table
        )

        if subcommand == "collect":
            # Post initial message
            slack.post_message(
                channel_id,
                text="🔍 *Starting evidence collection across all resources...*\n\n"
                     "_This may take a few minutes. I'll post results when complete._"
            )

            # Invoke async processing in background
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
                return handle_evidence_collect_sync(slack, channel_id, user_id)

            # Return empty 200 OK immediately to Slack (prevents timeout)
            return {"statusCode": 200, "body": ""}

        elif subcommand == "list":
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
                        "text": "💡 Run `/carl evidence collect` to gather evidence for missing controls"
                    }
                ]
            })

            slack.post_message(channel_id, blocks=blocks)

        else:
            slack.post_message(
                channel_id,
                text="Unknown evidence command. Use `collect` or `status`."
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

        slack.post_message(channel_id, text="\n".join(summary_lines))

        # Create findings from security issues detected in evidence
        slack.post_message(channel_id, text="🔍 Analyzing evidence for security issues...")

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

        if stored_count > 0:
            slack.post_message(
                channel_id,
                text=f"✅ Created *{stored_count}* new findings from evidence analysis.\n\n"
                     f"Run `/carl jira sync` to create Jira tickets for these issues."
            )
        else:
            slack.post_message(
                channel_id,
                text="✓ No new security issues found (all findings already exist)."
            )

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
                     f"Run `/carl evidence collect` to gather evidence."
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

                status_text = f"{severity_emoji} *{severity}*"
                if jira_ticket_id and jira_url:
                    status_text += f" | <{jira_url}|{jira_ticket_id}>"

            else:
                status_text = "✅ *Compliant*"
                finding_id = None
                jira_ticket_id = None
                status = None

            # Build evidence text
            evidence_text = (
                f"{status_text}\n"
                f"*{evidence.title}*\n"
                f"{evidence.description[:150]}{'...' if len(evidence.description) > 150 else ''}\n"
                f"Resource: `{evidence.resource_id}`"
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
                        "text": f"{severity_emoji} *{severity}* | {finding.get('title', 'Unknown')}\nResource: `{finding.get('resource_id', 'N/A')}`"
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
                    "text": "💡 Showing 10 most recent items | Run `/carl evidence collect` to refresh | `/carl jira sync` to sync all findings"
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
            text="Usage: `/carl report executive|full|control <control-id>`"
        )
        return {"statusCode": 200, "body": ""}

    if report_type == "control" and not control_id:
        slack.post_message(
            channel_id,
            text="Error: Control report requires a control ID. Usage: `/carl report control CC6.1`"
        )
        return {"statusCode": 200, "body": ""}

    # Post initial message
    slack.post_message(
        channel_id,
        text=f"📊 **Generating {report_type} report...**\n\n_Scanning environment and collecting evidence..._"
    )

    # Invoke async processing in background
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
    """Synchronous version of report command with environment scanning and progress updates."""
    import os
    from services.evidence_collector import EvidenceCollector
    from services.report_generator import ReportGenerator, ReportType
    from services.aws_scanner import AWSScanner
    from datetime import datetime, timedelta

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")
    findings_table = os.environ.get("FINDINGS_TABLE", "carl-findings")
    exceptions_table = os.environ.get("EXCEPTIONS_TABLE", "carl-exceptions")
    reports_bucket = os.environ.get("REPORTS_BUCKET", "carl-reports")

    # Post initial status message and get timestamp for updates
    status_response = slack.post_message(
        channel_id,
        text=f"📊 **Generating {report_type} report...**\n\n🔄 Scanning AWS environment..."
    )
    status_ts = status_response.get("ts") if status_response else None

    def update_progress(status: str):
        """Update the status message in Slack."""
        if status_ts:
            try:
                slack.update_message(
                    channel_id,
                    status_ts,
                    text=f"📊 **Generating {report_type} report...**\n\n{status}"
                )
            except Exception as e:
                logger.warning(f"Failed to update progress: {e}")

    try:
        # Step 1: Scan AWS environment
        update_progress("🔍 Scanning AWS environment for compliance data...")
        scanner = AWSScanner()
        scan_results = scanner.scan_environment()

        scan_summary = (
            f"Scanned: {scan_results.get('vpcs_count', 0)} VPCs, "
            f"{scan_results.get('security_groups_count', 0)} security groups, "
            f"{scan_results.get('iam_users_count', 0)} IAM users, "
            f"{scan_results.get('encryption_findings', 0)} encryption findings"
        )
        logger.info(f"Environment scan complete: {scan_summary}")

        # Step 2: Initialize services
        update_progress("📋 Collecting audit evidence...")

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

        if report_type == "executive":
            report = generator.generate_executive_summary(start_date, end_date)
            # Prepend scan context
            report = report_context + report
            report_type_enum = ReportType.EXECUTIVE_SUMMARY

        elif report_type == "full":
            report = generator.generate_full_audit_report(start_date, end_date)
            report = report_context + report
            report_type_enum = ReportType.FULL_AUDIT

        elif report_type == "control" and control_id:
            report = generator.generate_control_report(control_id.upper())
            report = report_context + report
            report_type_enum = ReportType.CONTROL_SPECIFIC

        else:
            report_type_enum = None

        # Step 4: Save markdown report to S3
        update_progress("☁️ Uploading report to S3...")

        # Save as markdown file
        s3_key = generator.save_report(report, report_type_enum)

        # Generate presigned URL
        download_url = generator.generate_presigned_url(s3_key, expiration=86400)  # 24 hours

        # Delete the status message (cleanup)
        if status_ts:
            try:
                slack.delete_message(channel_id, status_ts)
            except Exception as e:
                logger.warning(f"Failed to delete status message: {e}")

        # Step 5: Post summary with download link
        update_progress("✅ Report generation complete!")

        # Extract key metrics for summary
        summary_text = f"""📊 **{report_type.title()} Report Generated Successfully**

**Audit Period:** {start_date} to {end_date}
**Environment Scan:** {scan_summary}

📥 **Download Report (Markdown):**
{download_url}

_Link expires in 24 hours_

The report is in Markdown format - you can:
• View directly in your browser
• Open in any text editor
• Convert to PDF using tools like pandoc or online converters"""

        slack.post_message(channel_id, text=summary_text)

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
                        "text": {"type": "mrkdwn", "text": f"• `{exc.exception_id[:12]}` - {exc.title[:50]}"},
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
                        "text": {"type": "mrkdwn", "text": f"• `{exc.exception_id[:12]}` - {exc.title[:50]} (expires {exc.expires_at[:10]})"}
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
                    "Example: `/carl exception create \"API key rotation exception\" finding-123 CC6.1,CC6.5 \"Legacy system requires 180-day keys\" 90`\n\n"
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
                text=f"✅ Exception `{exception_id}` approved. Expires: {exc.expires_at[:10]}"
            )

        elif subcommand == "deny" and extra_args:
            exception_id = extra_args[0]
            reason = " ".join(extra_args[1:]) if len(extra_args) > 1 else "No reason provided"

            manager.deny_exception(exception_id, user_id, reason)
            slack.post_message(
                channel_id,
                text=f"❌ Exception `{exception_id}` denied. Reason: {reason}"
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
                text="Usage: `/carl exception list|request|approve <id>|deny <id> <reason>|stats`"
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
            slack.post_message(channel_id, text="Starting drift detection scan... This may take a few minutes.")

            report = detector.detect_all_drift()

            # Format and send report
            slack_format = detector.format_drift_report_for_slack(report)
            slack.post_message(channel_id, blocks=slack_format["blocks"])

            if report.critical_drifts:
                slack.post_message(
                    channel_id,
                    text=f"⚠️ *{len(report.critical_drifts)} critical drift items require immediate attention!*"
                )

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
                slack.post_message(channel_id, text=f"✓ Drift item `{drift_id}` acknowledged.")
            else:
                slack.post_message(channel_id, text=f"Failed to acknowledge drift item `{drift_id}`.")

        elif subcommand == "terraform" and extra_args:
            # Compare with Terraform state
            state_key = extra_args[0]
            slack.post_message(channel_id, text=f"Comparing with Terraform state: {state_key}...")

            drift_items = detector.compare_with_terraform_state(state_key)

            if drift_items:
                slack.post_message(
                    channel_id,
                    text=f"Found *{len(drift_items)}* drift items compared to Terraform state."
                )
                for item in drift_items[:5]:
                    slack.post_message(
                        channel_id,
                        text=f"• `{item.resource_id}` - {item.description}"
                    )
            else:
                slack.post_message(channel_id, text="✓ No drift detected compared to Terraform state.")

        else:
            slack.post_message(
                channel_id,
                text="Usage: `/carl drift scan|status|acknowledge <drift-id>|terraform <state-key>`"
            )

    except Exception as e:
        logger.exception("Error in drift command")
        slack.post_message(channel_id, text=f"Error: {str(e)}")

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
            text="Unknown Jira subcommand. Use: `test`, `sync`, or `status`"
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

        synced_count = 0
        failed_count = 0
        skipped_count = 0
        recreated_count = 0

        for finding in findings:
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

        # Report results
        result_text = f"✅ *Jira Sync Complete*\n\n"
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
                        {"type": "mrkdwn", "text": "Run `/carl jira sync` to sync remaining findings"}
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
            text="Unknown compliance subcommand. Use: `assess` or `status`"
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
    """Synchronous version - does the actual compliance assessment work."""
    import time

    start_time = time.time()
    interaction_id = None

    try:
        from services.compliance_agent import ComplianceAgent
        from services.learning_service import LearningService
        import os

        # Get agent ID and alias ID from environment (will be configured via CDK/CloudFormation)
        agent_id = os.environ.get("COMPLIANCE_AGENT_ID")
        agent_alias_id = os.environ.get("COMPLIANCE_AGENT_ALIAS_ID", "PROD")

        if not agent_id:
            # Agent not configured yet - use fallback approach
            logger.warning("Compliance agent not configured, using fallback")
            return handle_compliance_assess_fallback(slack, channel_id, user_id)

        # Initialize agent
        agent = ComplianceAgent(agent_id=agent_id, agent_alias_id=agent_alias_id)

        # Run assessment
        result = agent.assess_compliance(
            framework="soc2",
            auto_create_tickets=True
        )

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Post results to Slack
        coverage = result.get("coverage_percent", 0)
        gaps_count = len(result.get("gaps", []))
        epic_url = result.get("jira_epic_url")
        story_count = result.get("jira_story_count", 0)
        finding_ids = [f"FND-{i}" for i in range(gaps_count)]  # Simplified - would get actual IDs

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 SOC 2 Compliance Assessment Complete"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Coverage:*\n{coverage}%"},
                    {"type": "mrkdwn", "text": f"*Gaps:*\n{gaps_count}"}
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": result.get("executive_summary", "Assessment complete.")
                }
            }
        ]

        if epic_url:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📋 Jira Epic Created:* <{epic_url}|View Roadmap>\n{story_count} stories created for phased remediation."
                }
            })

        slack.post_message(channel_id, blocks=blocks)

        # Log interaction for learning
        try:
            scan_history_table = os.environ.get("SCAN_HISTORY_TABLE", "carl-dev-scan-history")
            resource_graph_table = os.environ.get("RESOURCE_GRAPH_TABLE", "carl-dev-resource-graph")

            learning_service = LearningService(
                scan_history_table=scan_history_table,
                resource_graph_table=resource_graph_table
            )

            interaction_id = learning_service.log_interaction(
                user_id=user_id,
                question="SOC 2 compliance assessment",
                scans_performed=["assess_soc2", "create_epic"],
                resources_found=finding_ids,
                scan_duration_ms=duration_ms,
                interaction_type="compliance",
                metadata={
                    "channel_id": channel_id,
                    "coverage": coverage,
                    "gaps_count": gaps_count,
                    "epic_url": epic_url,
                    "story_count": story_count
                }
            )

            logger.info(f"Logged compliance assessment interaction {interaction_id}")
        except Exception as e:
            logger.warning(f"Failed to log compliance interaction: {e}")

        # Add feedback buttons
        if interaction_id:
            feedback_blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_Was this assessment helpful?_"
                    }
                },
                {
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
                }
            ]

            slack.post_message(channel_id, blocks=feedback_blocks)

    except Exception as e:
        logger.error(f"Compliance assessment failed: {e}")
        slack.post_message(
            channel_id,
            text=f"❌ Compliance assessment failed: {str(e)}"
        )

    return {"statusCode": 200, "body": ""}


def handle_compliance_assess_fallback(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Fallback when Bedrock Agent not configured - use simpler approach."""
    slack.post_message(
        channel_id,
        text="⚠️ Compliance agent not yet configured.\n\nTo enable autonomous compliance assessment:\n1. Configure AWS Bedrock Agent\n2. Set COMPLIANCE_AGENT_ID environment variable\n3. Deploy updated Lambda\n\nFor now, you can use:\n• `/carl evidence collect` - Manual evidence collection\n• `/carl jira sync` - Create tickets manually"
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
                        "text": "💡 Run `/carl compliance assess` for complete SOC 2 analysis with remediation plan."
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
        text=f"🔄 Creating Jira ticket for finding `{finding_id}`..."
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
                                   f"Finding: `{finding_id}`"
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
