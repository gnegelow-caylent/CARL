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
from services.code_uploader import CodeUploader
from utils.aws_client import get_parameter, get_secret
from utils.logger import get_logger

logger = get_logger(__name__)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
SLACK_BOT_TOKEN_SSM = os.environ.get("SLACK_BOT_TOKEN_SSM", "")
SLACK_SIGNING_SECRET_SSM = os.environ.get("SLACK_SIGNING_SECRET_SSM", "")
GITHUB_INFRA_TOKEN_SECRET = os.environ.get("GITHUB_INFRA_TOKEN_SECRET", "/carl/dev/github-infra-token")
GITHUB_INFRA_OWNER = os.environ.get("GITHUB_INFRA_OWNER", "your-org")
GITHUB_INFRA_REPO = os.environ.get("GITHUB_INFRA_REPO", "carl-infrastructure-deployments")

# Lazy-loaded services
_slack_service: SlackService | None = None
_bedrock_service: BedrockService | None = None
_findings_service: FindingsService | None = None
_architecture_advisor: ArchitectureAdvisor | None = None
_infrastructure_builder: InfrastructureBuilder | None = None
_cost_estimator: CostEstimator | None = None
_decision_engine: DecisionEngine | None = None
_foundation_builder: FoundationBuilder | None = None
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


def get_github_service() -> GitHubService:
    """Get or create GitHub service instance with token from Secrets Manager."""
    global _github_service
    if _github_service is None:
        # Get token from Secrets Manager
        token = get_secret(GITHUB_INFRA_TOKEN_SECRET)
        _github_service = GitHubService(token, GITHUB_INFRA_OWNER, GITHUB_INFRA_REPO)
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


def format_markdown_to_blocks(markdown_text: str, title: str = None) -> list[list[dict]]:
    """
    Convert markdown text to formatted Slack blocks.
    Returns a list of block groups (to handle 50-block limit per message).
    """
    import re

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

        # Handle headers
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
        logger.info("Processing async architect command")
        slack = get_slack_service()
        return handle_architect_command_sync(
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
        return handle_findings_command(slack, channel_id, user_id, args)
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
    elif subcommand == "help":
        return handle_help_command(slack, channel_id, user_id)
    else:
        # Treat unknown subcommand as a question
        return handle_ask_command(slack, channel_id, user_id, text)


def handle_status_command(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Handle /carl status command."""
    findings_service = get_findings_service()

    summary = findings_service.get_compliance_summary()

    # Calculate overall health score
    total = summary.get('total', 0)
    critical = summary.get('critical', 0)
    high = summary.get('high', 0)
    medium = summary.get('medium', 0)
    low = summary.get('low', 0)

    # Determine health status and emoji
    if critical > 0:
        health_status = "🔴 Critical Issues"
        health_color = "#d32f2f"
    elif high > 5:
        health_status = "🟠 Needs Attention"
        health_color = "#f57c00"
    elif high > 0 or medium > 10:
        health_status = "🟡 Monitor Closely"
        health_color = "#fbc02d"
    else:
        health_status = "🟢 Healthy"
        health_color = "#388e3c"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Compliance Status",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Overall Health:* {health_status}"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Security Findings Breakdown:*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"🔴 *Critical*\n{critical}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"🟠 *High*\n{high}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"🟡 *Medium*\n{medium}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"⚪ *Low*\n{low}",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📈 *Total Open Issues:* `{total}`",
            },
        },
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🕐 Last updated: {summary.get('last_updated', 'N/A')} | Use `/carl findings` to see details",
                }
            ],
        },
    ]

    slack.post_message(channel_id, blocks=blocks)

    return {"statusCode": 200, "body": ""}


def handle_findings_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl findings command."""
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
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{finding.get('severity', 'UNKNOWN')}* | "
                    f"{finding.get('title', 'No title')}\n"
                    f"Resource: `{finding.get('resource_id', 'N/A')}`"
                ),
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Details"},
                "action_id": f"finding_details_{finding.get('id', '')}",
            },
        })

    slack.post_message(channel_id, blocks=blocks)

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
    """Synchronous version of ask command (for async processing or fallback)."""
    # Get context and generate response
    bedrock = get_bedrock_service()
    findings_service = get_findings_service()

    # Check if question is about bad practices or environment scanning
    question_lower = question.lower()
    should_scan = any(keyword in question_lower for keyword in [
        'bad practice', 'misconfiguration', 'security issue',
        'vulnerability', 'my environment', 'my aws', 'scan',
        'check my', 'what\'s wrong', 'issues in my'
    ])

    context = ""

    if should_scan:
        # Perform live AWS environment scan
        try:
            from services.aws_scanner import AWSScanner
            scanner = AWSScanner()
            scan_results = scanner.scan_environment()
            scan_summary = scanner.get_summary(scan_results)

            context = f"""
LIVE AWS ENVIRONMENT SCAN RESULTS:
{scan_summary}

This is real data from the user's AWS account, scanned moments ago.
"""
            logger.info("Performed live AWS environment scan")
        except Exception as e:
            logger.error(f"Failed to scan AWS environment: {e}")
            context = f"Note: Could not scan AWS environment: {str(e)}\n\n"

    # Add Security Hub findings ONLY if there are actual issues
    summary = findings_service.get_compliance_summary()
    recent_findings = findings_service.get_recent_findings(limit=5)

    # Only add Security Hub context if there are findings
    total_findings = summary.get('critical', 0) + summary.get('high', 0) + summary.get('medium', 0) + summary.get('low', 0)
    if total_findings > 0 or recent_findings:
        context += f"""
Security Hub compliance summary:
- Critical findings: {summary.get('critical', 0)}
- High findings: {summary.get('high', 0)}
- Medium findings: {summary.get('medium', 0)}
- Low findings: {summary.get('low', 0)}

Recent Security Hub findings:
{json.dumps(recent_findings, indent=2)}
"""
        logger.info(f"Added Security Hub context: {total_findings} findings")

    response = bedrock.ask_compliance_question(question, context)

    # Format and post response with better structure
    formatted_blocks = format_markdown_to_blocks(response, "💬 CARL's Response")
    for block_group in formatted_blocks:
        slack.post_message(channel_id, blocks=block_group)

    return {"statusCode": 200, "body": ""}


def handle_help_command(
    slack: SlackService, channel_id: str, user_id: str
) -> dict:
    """Handle /carl help command."""
    help_text = """
*CARL - Cloud Automated Risk & Compliance Logic*

*Compliance Commands:*
- `/carl status` - View compliance posture summary
- `/carl findings [severity]` - List recent findings
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
                    "text": f"*Question 1/{len(engine.get_all_patterns()) + 10}:* {first_question['question']}\n\n_{first_question['description']}_",
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
    """Synchronous version of recommend command (for async processing or fallback)."""
    advisor = get_architecture_advisor()
    recommendation = advisor.recommend(requirement)

    # Build response blocks
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Architecture Recommendations"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Requirement:* {requirement}"},
        },
        {"type": "divider"},
    ]

    for i, opt in enumerate(recommendation.options):
        recommended_tag = " :star: *RECOMMENDED*" if opt.name == recommendation.recommended_option else ""
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Option {i+1}: {opt.name}*{recommended_tag}\n"
                    f"{opt.description}\n\n"
                    f"*Cost:* ${opt.monthly_cost_estimate[0]:.0f} - ${opt.monthly_cost_estimate[1]:.0f}/month\n"
                    f"*Compliance:* {opt.compliance_level.value.title()}\n"
                    f"*SOC 2 Controls:* {', '.join(opt.soc2_controls_addressed[:5])}"
                ),
            },
        })

        # Components as bullet points
        components_text = "\n".join([f"• {c}" for c in opt.components[:6]])
        if len(opt.components) > 6:
            components_text += f"\n• _...and {len(opt.components) - 6} more_"

        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"*Components:*\n{components_text}"}],
        })

        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Generate Code"},
                    "action_id": f"build_blueprint_{opt.terraform_blueprint}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Detailed Estimate"},
                    "action_id": f"estimate_option_{opt.name}",
                },
            ],
        })

        blocks.append({"type": "divider"})

    # Post options blocks
    slack.post_message(channel_id, blocks=blocks)

    # AI Analysis - use formatted blocks for better readability
    ai_blocks = format_markdown_to_blocks(recommendation.ai_analysis, "🤖 AI Analysis")
    for block_group in ai_blocks:
        slack.post_message(channel_id, blocks=block_group)

    # Considerations
    considerations_text = "\n".join([f"• {c}" for c in recommendation.considerations[:4]])
    slack.post_message(channel_id, blocks=[
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"*Cost Considerations:*\n{considerations_text}"}],
        }
    ])

    return {"statusCode": 200, "body": ""}


def handle_build_command(
    slack: SlackService, channel_id: str, user_id: str, blueprint_name: str, config: dict = None, trigger_id: str = None
) -> dict:
    """Handle /carl build command - generate and upload to GitHub."""
    if not blueprint_name:
        return handle_blueprints_command(slack, channel_id, user_id)

    # Check if this is a VPC-related blueprint that needs CIDR input
    # Show modal for any blueprint with "vpc" in the name
    needs_cidr = "vpc" in blueprint_name.lower()

    # If VPC blueprint and no config provided, ask for CIDR via modal
    if needs_cidr and config is None and trigger_id:
        return show_vpc_config_modal(slack, trigger_id, channel_id, user_id, blueprint_name)

    builder = get_infrastructure_builder()

    try:
        # Use provided config or defaults
        if config is None:
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


def handle_vpc_config_submission(payload: dict) -> dict:
    """Handle VPC configuration modal submission."""
    import json as json_lib

    slack = get_slack_service()

    # Extract values from modal submission
    view = payload.get("view", {})
    values = view.get("state", {}).get("values", {})
    private_metadata = json_lib.loads(view.get("private_metadata", "{}"))

    channel_id = private_metadata.get("channel_id")
    blueprint_name = private_metadata.get("blueprint_name")

    # Extract input values
    vpc_cidr = values.get("vpc_cidr_block", {}).get("vpc_cidr_input", {}).get("value", "10.0.0.0/16")
    vpc_name = values.get("vpc_name_block", {}).get("vpc_name_input", {}).get("value", "main")
    environment = values.get("environment_block", {}).get("environment_input", {}).get("selected_option", {}).get("value", "prod")

    # Build configuration
    config = {
        "name": vpc_name,
        "environment": environment,
        "cidr": vpc_cidr  # Use "cidr" key to match what infrastructure_builder expects
    }

    # Post confirmation message
    slack.post_message(channel_id, text=f"✅ Configuration received! Generating {blueprint_name} with CIDR `{vpc_cidr}`...")

    # Generate the Terraform code with the provided configuration
    user_id = payload.get("user", {}).get("id", "")
    handle_build_command(slack, channel_id, user_id, blueprint_name, config, trigger_id=None)

    # Return 200 response to close modal successfully
    # Slack expects an empty response body to close the modal without errors
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
        if callback_id == "vpc_config_modal":
            return handle_vpc_config_submission(payload)

    if action_type == "block_actions":
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id", "")
            if action_id.startswith("finding_details_"):
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
            elif action_id.startswith("feedback_"):
                return handle_feedback(payload, action)
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
    """Show detailed information about a finding."""
    channel = payload.get("channel", {}).get("id", "")
    user = payload.get("user", {}).get("id", "")

    slack = get_slack_service()
    findings_service = get_findings_service()
    bedrock = get_bedrock_service()

    finding = findings_service.get_finding(finding_id)
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
    Handle /carl architect command - AGENTIC architecture recommendations.

    This uses Agent Core where Claude autonomously:
    - Scans the actual AWS environment
    - Queries real pricing data
    - Retrieves architecture patterns
    - Makes informed, data-driven recommendations

    The agent decides its own workflow based on the question.
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
                "_Note: I'll autonomously scan your AWS account and query pricing to provide accurate recommendations._"
            ),
        )
        return {"statusCode": 200, "body": ""}

    # Post initial message via Slack API
    slack.post_message(
        channel_id,
        text=f"🏗️ Analyzing: _{question}_\n\n_Starting agentic analysis (scanning environment, querying pricing, retrieving patterns)..._"
    )

    # Invoke async processing in background
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps({
                'action': 'process_architect_async',
                'channel_id': channel_id,
                'user_id': user_id,
                'question': question
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async processing: {e}")
        # Fallback to synchronous if async fails
        return handle_architect_command_sync(slack, channel_id, user_id, question)

    # Return empty 200 OK immediately to Slack (prevents timeout)
    return {"statusCode": 200, "body": ""}


def handle_architect_command_sync(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """
    Synchronous version of architect command (for async processing or fallback).

    This is where the actual agentic work happens:
    - Agent autonomously decides which tools to call
    - Scans AWS environment if needed
    - Queries pricing if needed
    - Retrieves patterns if needed
    - Generates personalized recommendation
    """
    try:
        from services.agentic_architect import get_agentic_architect

        logger.info(f"Processing architect question: {question[:100]}")

        # Post initial status message and get timestamp for updates
        status_response = slack.post_message(
            channel_id,
            text=f"🏗️ **Analyzing:** _{question}_\n\n🔄 Initializing agent..."
        )
        status_ts = status_response.get("ts") if status_response else None

        # Create progress callback to update Slack message
        def update_progress(status: str):
            """Update the status message in Slack."""
            if status_ts:
                try:
                    slack.update_message(
                        channel_id,
                        status_ts,
                        text=f"🏗️ **Analyzing:** _{question}_\n\n{status}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to update progress: {e}")

        # Get the agentic architect (ONE agent with multiple tools)
        architect = get_agentic_architect()

        # Agent executes autonomously with progress updates
        response = architect.answer_question(question, progress_callback=update_progress)

        # Delete the status message (cleanup)
        if status_ts:
            try:
                slack.delete_message(channel_id, status_ts)
            except Exception as e:
                logger.warning(f"Failed to delete status message: {e}")

        # Format and post response with better structure
        formatted_blocks = format_markdown_to_blocks(response, "🏗️ Architecture Recommendation")
        for block_group in formatted_blocks:
            slack.post_message(channel_id, blocks=block_group)

        # Add feedback buttons
        blocks = [
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Was this recommendation helpful?_",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👍 Helpful"},
                        "style": "primary",
                        "action_id": f"feedback_helpful_architect_{hash(question) % 10000}",
                        "value": question[:100],
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👎 Not Helpful"},
                        "action_id": f"feedback_not_helpful_architect_{hash(question) % 10000}",
                        "value": question[:100],
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "💡 Suggest Improvement"},
                        "action_id": f"feedback_improve_architect_{hash(question) % 10000}",
                        "value": question[:100],
                    },
                ],
            },
        ]
        slack.post_message(channel_id, blocks=blocks)

        logger.info("Architect recommendation completed successfully")

    except Exception as e:
        logger.exception("Error in Agentic Architect")
        slack.post_message(
            channel_id,
            text=f"❌ I encountered an error while analyzing your architecture question:\n\n```{str(e)}```\n\nPlease try again or rephrase your question.",
        )

    return {"statusCode": 200, "body": ""}


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


# =============================================================================
# AUDIT EVIDENCE HANDLERS
# =============================================================================


def handle_evidence_command(
    slack: SlackService, channel_id: str, user_id: str, args: str
) -> dict:
    """Handle /carl evidence command - audit evidence collection."""
    import os
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
            slack.post_message(channel_id, text="Starting evidence collection across all resources... This may take a few minutes.")

            results = collector.collect_all_evidence()

            total = sum(len(items) for items in results.values())
            summary_lines = [f"*Evidence Collection Complete*\n\nCollected *{total}* evidence items:\n"]
            for category, items in results.items():
                summary_lines.append(f"• {category.upper()}: {len(items)} items")

            slack.post_message(channel_id, text="\n".join(summary_lines))

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

            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Collect Evidence"},
                        "style": "primary",
                        "action_id": "evidence_collect_all"
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
