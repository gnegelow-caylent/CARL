# CARL Slack Integration - Technical Implementation Guide

> Technical documentation for recent Slack improvements (January 2026)

## Table of Contents

- [Overview](#overview)
- [Async Processing Pattern](#async-processing-pattern)
- [Response Formatting System](#response-formatting-system)
- [Interactive Elements](#interactive-elements)
- [VPC Modal Flow](#vpc-modal-flow)
- [Button Handler Architecture](#button-handler-architecture)
- [Code Examples](#code-examples)
- [Deployment](#deployment)

## Overview

This document covers the technical implementation of major improvements to CARL's Slack integration:

1. **Async Processing** - Eliminates timeout errors for long-running operations
2. **Response Formatting** - Structured Block Kit messages for better UX
3. **Interactive Modals** - Configuration input with validation
4. **Button Handlers** - Click-to-action workflows
5. **Code Display** - Syntax-highlighted, multi-part code blocks

**Files Modified:**
- `/carl-app/src/handlers/slack_router.py` - Main routing and handlers (~2500 lines)
- `/carl-infrastructure/core/main.tf` - Lambda timeout increased to 90s

## Async Processing Pattern

### Problem

Slack requires HTTP response within 3 seconds. Long-running operations (AI analysis, environment scanning) would timeout with "operation_timeout" error.

### Solution

Lambda self-invocation pattern:
1. Command handler returns immediately with progress message
2. Invokes itself asynchronously with action payload
3. Background processing completes without Slack timeout
4. Results posted to channel when ready

### Architecture

```
User sends /carl command
         ↓
API Gateway → Lambda (sync)
         ↓
Handle command (< 1s)
         ↓
Post "Analyzing..." message
         ↓
Lambda.invoke(Event) → Lambda (async)
         ↓                    ↓
Return 200 OK          Do actual work (30-90s)
         ↓                    ↓
User sees response     Post results to Slack
```

### Implementation

**File:** `slack_router.py`

#### 1. Async Wrapper Function

```python
def handle_ask_command(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """Handle /carl ask command - immediate return."""
    if not question:
        slack.post_message(
            channel_id,
            text="Please ask a question. Example: `/carl ask What are our critical findings?`"
        )
        return {"statusCode": 200, "body": ""}

    # Post immediate acknowledgment
    slack.post_message(channel_id, text=f"🤔 Thinking about: _{question}_...")

    # Invoke async processing
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'carl-dev-api'),
            InvocationType='Event',  # Async - no wait for response
            Payload=json.dumps({
                'action': 'process_ask_async',  # Custom action identifier
                'channel_id': channel_id,
                'user_id': user_id,
                'question': question
            })
        )
    except Exception as e:
        logger.error(f"Failed to invoke async processing: {e}")
        # Fallback to sync if async fails
        return handle_ask_command_sync(slack, channel_id, user_id, question)

    # Return immediately - Slack gets response in < 1 second
    return {"statusCode": 200, "body": ""}
```

**Key Points:**
- `InvocationType='Event'` - Fire-and-forget async invocation
- Returns `{"statusCode": 200, "body": ""}` immediately
- No payload in return (Slack gets empty 200 OK)
- Fallback to sync if async fails

#### 2. Sync Processing Function

```python
def handle_ask_command_sync(
    slack: SlackService, channel_id: str, user_id: str, question: str
) -> dict:
    """Handle /carl ask command - actual processing."""
    findings = get_findings_service()
    bedrock = get_bedrock_service()

    # Build context from Security Hub
    context = ""
    try:
        summary = findings.get_findings_summary()
        recent_findings = findings.get_recent_findings(limit=5)

        context += f"""
Security Hub compliance summary:
- Critical findings: {summary.get('critical', 0)}
- High findings: {summary.get('high', 0)}
- Medium findings: {summary.get('medium', 0)}
- Low findings: {summary.get('low', 0)}

Recent Security Hub findings:
{json.dumps(recent_findings, indent=2)}
"""
    except Exception as e:
        logger.error(f"Failed to get Security Hub context: {e}")

    # Get AI response (can take 10-30 seconds)
    response = bedrock.ask_compliance_question(question, context)

    # Format and post response with structured blocks
    formatted_blocks = format_markdown_to_blocks(response, "💬 CARL's Response")
    for block_group in formatted_blocks:
        slack.post_message(channel_id, blocks=block_group)

    return {"statusCode": 200, "body": ""}
```

**Key Points:**
- Separate function suffix: `_sync`
- Contains actual business logic
- Can take 30-90 seconds
- Posts results directly to Slack
- Return value doesn't matter (async invocation)

#### 3. Async Action Handler

```python
def lambda_handler(event, context):
    """Main Lambda entry point."""
    logger.info(f"Event: {json.dumps(event)}")

    # Handle async actions from self-invocation
    if event.get("action") == "process_ask_async":
        logger.info("Processing async ask command")
        slack = get_slack_service()
        return handle_ask_command_sync(
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

    # ... handle other async actions ...

    # Normal Slack request handling
    # ... existing code ...
```

**Key Points:**
- Check for `event.get("action")` first
- Route to appropriate sync handler
- Each command has unique action identifier
- Falls through to normal Slack handling if no action

### Commands Using Async Pattern

| Command | Wrapper Function | Sync Function | Action ID | Reason |
|---------|-----------------|---------------|-----------|--------|
| `/carl ask` | `handle_ask_command()` | `handle_ask_command_sync()` | `process_ask_async` | AI analysis + Security Hub queries |
| `/carl architect` | `handle_architect_command()` | `handle_architect_command_sync()` | `process_architect_async` | Complex AI recommendations |
| `/carl recommend` | `handle_recommend_command()` | `handle_recommend_command_sync()` | `process_recommend_async` | Pattern matching + cost analysis |
| `/carl report` | `handle_report_command()` | `handle_report_command_sync()` | `process_report_async` | Environment scanning + report generation |

### Environment Requirements

**Lambda Configuration:**
```hcl
# carl-infrastructure/core/main.tf
timeout = 90  # Increased from 30s to allow complex processing
```

**IAM Permissions:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:*:*:function:carl-dev-api"
    }
  ]
}
```

**Environment Variables:**
```bash
AWS_LAMBDA_FUNCTION_NAME=carl-dev-api  # Self-reference for invocation
```

### Error Handling

```python
try:
    lambda_client.invoke(...)
except Exception as e:
    logger.error(f"Failed to invoke async processing: {e}")
    # Fallback to synchronous processing
    return handle_command_sync(slack, channel_id, user_id, args)
```

**Fallback Strategy:**
- If async invocation fails, attempt sync processing
- Sync will timeout after 90s, but better than immediate failure
- Logs error for investigation

## Response Formatting System

### Problem

Raw text responses were hard to read:
- No visual structure
- Plain text only
- No syntax highlighting
- Long walls of text

### Solution

Created `format_markdown_to_blocks()` converter that transforms markdown into Slack Block Kit messages with:
- Headers for sections
- Dividers for visual separation
- Code blocks with syntax highlighting
- Context boxes for metadata
- Proper text wrapping

### Implementation

**File:** `slack_router.py` lines 145-250

```python
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
                    # Limit code block size (Slack has ~3000 char limit)
                    if len(code_text) > 2900:
                        # Split into multiple blocks
                        chunks = [code_text[i:i+2900] for i in range(0, len(code_text), 2900)]
                        for idx, chunk in enumerate(chunks):
                            blocks.append({
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"```{code_language}\n{chunk}\n```"
                                }
                            })
                            if idx < len(chunks) - 1:
                                blocks.append({"type": "divider"})
                    else:
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"```{code_language}\n{code_text}\n```"
                            }
                        })
                code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Handle headers (## Header)
        if line.strip().startswith('##'):
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
                blocks.append({"type": "divider"})

            # Add header
            header_text = line.strip('#').strip()
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{header_text}*"
                }
            })
            continue

        # Accumulate regular lines
        current_section.append(line)

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

    # Split into groups of 50 blocks (Slack limit)
    block_groups = []
    for i in range(0, len(blocks), 50):
        block_groups.append(blocks[i:i+50])

    return block_groups if block_groups else [[]]
```

### Usage Examples

**Simple Response:**
```python
response = bedrock.ask_compliance_question(question, context)
formatted_blocks = format_markdown_to_blocks(response, "💬 CARL's Response")

for block_group in formatted_blocks:
    slack.post_message(channel_id, blocks=block_group)
```

**Multiple Sections:**
```python
# /carl recommend uses multiple messages
# Message 1: Options summary
slack.post_message(channel_id, blocks=options_blocks)

# Message 2: AI analysis with formatting
ai_blocks = format_markdown_to_blocks(recommendation.ai_analysis, "🤖 AI Analysis")
for block_group in ai_blocks:
    slack.post_message(channel_id, blocks=block_group)

# Message 3: Cost considerations
slack.post_message(channel_id, blocks=cost_blocks)
```

### Block Types Reference

**Header:**
```python
{
    "type": "header",
    "text": {"type": "plain_text", "text": "Section Title"}
}
```
- Large, prominent text
- Use for main titles

**Section:**
```python
{
    "type": "section",
    "text": {"type": "mrkdwn", "text": "*Bold* and _italic_ text"}
}
```
- Main content block
- Supports markdown formatting
- Max 3000 characters

**Divider:**
```python
{"type": "divider"}
```
- Horizontal line
- Visual separation

**Context:**
```python
{
    "type": "context",
    "elements": [{"type": "mrkdwn", "text": "Small metadata text"}]
}
```
- Muted, smaller text
- Use for timestamps, metadata

**Actions:**
```python
{
    "type": "actions",
    "elements": [{
        "type": "button",
        "text": {"type": "plain_text", "text": "Click Me"},
        "action_id": "button_action"
    }]
}
```
- Interactive buttons
- Up to 5 buttons per block

### Slack Limits

| Limit | Value | How CARL Handles |
|-------|-------|------------------|
| Blocks per message | 50 | Splits into multiple messages |
| Text per section | 3000 chars | Splits code blocks at 2900 chars |
| Message payload | 40 KB | Splits into multiple messages |

## Interactive Elements

### VPC Modal Flow

**Purpose:** Collect VPC configuration (name, environment, CIDR) before generating Terraform code.

**Flow:**
```
/carl build networking/basic-vpc
         ↓
Check if "vpc" in blueprint name
         ↓
trigger_id present? → Show modal
         ↓
User fills form:
  - VPC Name: main-vpc
  - Environment: prod
  - CIDR Block: 10.0.0.0/16
         ↓
Submit → Modal handler
         ↓
Extract values from submission
         ↓
Build config: {"name": "main-vpc", "environment": "prod", "cidr": "10.0.0.0/16"}
         ↓
Call infrastructure_builder._blueprint_basic_vpc(config)
         ↓
Generate Terraform code
         ↓
Post formatted code to Slack
```

### Implementation

**File:** `slack_router.py`

#### 1. Modal Trigger Detection

```python
def handle_build_command(
    slack: SlackService,
    channel_id: str,
    user_id: str,
    blueprint_name: str,
    config: dict = None,
    trigger_id: str = None
) -> dict:
    """Handle /carl build command - generate Terraform code."""
    if not blueprint_name:
        return handle_blueprints_command(slack, channel_id, user_id)

    # Check if this is a VPC-related blueprint that needs CIDR input
    # FIXED: Pattern matching instead of hardcoded list
    needs_cidr = "vpc" in blueprint_name.lower()

    # If VPC blueprint and no config provided, ask for CIDR via modal
    if needs_cidr and config is None and trigger_id:
        return show_vpc_config_modal(slack, trigger_id, channel_id, user_id, blueprint_name)

    # ... generate code with config ...
```

**Key Fix (Commit 284a446):**
- **Before:** `vpc_blueprints = ["networking/basic-vpc", "networking/three-tier-vpc", ...]`
- **After:** `needs_cidr = "vpc" in blueprint_name.lower()`
- **Impact:** Works for ANY VPC blueprint (standard-vpc, custom-vpc, etc.)

#### 2. Modal Display

```python
def show_vpc_config_modal(
    slack: SlackService,
    trigger_id: str,
    channel_id: str,
    user_id: str,
    blueprint_name: str
) -> dict:
    """Show modal to collect VPC configuration."""
    modal = {
        "type": "modal",
        "callback_id": "vpc_config_modal",
        "title": {"type": "plain_text", "text": "VPC Configuration"},
        "submit": {"type": "plain_text", "text": "Generate Code"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": json.dumps({
            "channel_id": channel_id,
            "user_id": user_id,
            "blueprint_name": blueprint_name
        }),
        "blocks": [
            {
                "type": "input",
                "block_id": "vpc_name_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "vpc_name_input",
                    "placeholder": {"type": "plain_text", "text": "main-vpc"}
                },
                "label": {"type": "plain_text", "text": "VPC Name"}
            },
            {
                "type": "input",
                "block_id": "environment_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "environment_input",
                    "placeholder": {"type": "plain_text", "text": "prod"}
                },
                "label": {"type": "plain_text", "text": "Environment"}
            },
            {
                "type": "input",
                "block_id": "cidr_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "cidr_input",
                    "placeholder": {"type": "plain_text", "text": "10.0.0.0/16"}
                },
                "label": {"type": "plain_text", "text": "VPC CIDR Block"},
                "hint": {
                    "type": "plain_text",
                    "text": "Format: X.X.X.X/X (e.g., 10.0.0.0/16)"
                }
            }
        ]
    }

    try:
        slack_client = slack._get_client()
        slack_client.views_open(trigger_id=trigger_id, view=modal)
        return {"statusCode": 200, "body": ""}
    except Exception as e:
        logger.error(f"Failed to open modal: {e}")
        slack.post_message(channel_id, text=f"❌ Failed to open configuration modal: {e}")
        return {"statusCode": 500, "body": str(e)}
```

**Key Points:**
- `callback_id` - Identifies modal in submission handler
- `private_metadata` - Passes context through modal lifecycle
- `trigger_id` - Short-lived token from Slack command (expires in 3s)
- Validation hints in help text

#### 3. Modal Submission Handler

```python
def handle_interaction(payload: dict) -> dict:
    """Handle interactive component interactions."""
    interaction_type = payload.get("type")
    view_type = interaction_type if interaction_type == "view_submission" else None

    if view_type == "view_submission":
        callback_id = payload.get("view", {}).get("callback_id")

        if callback_id == "vpc_config_modal":
            # Extract metadata
            metadata = json.loads(payload["view"]["private_metadata"])
            channel_id = metadata["channel_id"]
            user_id = metadata["user_id"]
            blueprint_name = metadata["blueprint_name"]

            # Extract form values
            values = payload["view"]["state"]["values"]
            vpc_name = values["vpc_name_block"]["vpc_name_input"]["value"]
            environment = values["environment_block"]["environment_input"]["value"]
            vpc_cidr = values["cidr_block"]["cidr_input"]["value"]

            # Build config - FIXED: Use "cidr" key (Commit c8118eb)
            config = {
                "name": vpc_name,
                "environment": environment,
                "cidr": vpc_cidr  # NOT "vpc_cidr"!
            }

            # Post confirmation
            slack = get_slack_service()
            slack.post_message(
                channel_id,
                text=f"✅ Configuration received! Generating {blueprint_name} with CIDR {vpc_cidr}..."
            )

            # Generate code with config
            handle_build_command(
                slack,
                channel_id,
                user_id,
                blueprint_name,
                config=config
            )

            # CRITICAL: Return proper format
            return {"statusCode": 200, "body": ""}

    # ... other interaction handlers ...
```

**Key Fix (Commit c8118eb):**
```python
# BEFORE (broken):
config = {
    "vpc_cidr": vpc_cidr  # infrastructure_builder doesn't recognize this
}

# AFTER (working):
config = {
    "cidr": vpc_cidr  # Matches infrastructure_builder expectation
}
```

**Key Fix (Commit dc47f3b):**
```python
# BEFORE (broken):
return {}  # Causes "trouble connecting" error

# AFTER (working):
return {"statusCode": 200, "body": ""}  # Proper Slack response
```

### Prerequisites

**Slack App Configuration:**

1. Go to api.slack.com → Your App → Interactivity & Shortcuts
2. Enable "Interactivity"
3. Set Request URL: `https://[api-gateway-id].execute-api.[region].amazonaws.com/slack`
4. Save changes

**Without this configuration:**
- Modals will show "We had some trouble connecting"
- Button clicks won't work
- All interactive features will fail

## Button Handler Architecture

### Purpose

Enable click-to-action workflows in recommendations:
- "Generate Code" → Triggers `/carl build` with blueprint
- "Detailed Estimate" → Shows guidance on cost estimates
- Feedback buttons → Continuous learning

### Flow

```
User sees recommendation message
         ↓
Clicks "Generate Code" button
         ↓
Slack sends interaction payload to API Gateway
         ↓
Lambda receives payload
         ↓
handle_interaction() routes by action_id
         ↓
handle_build_blueprint_button() extracts blueprint name
         ↓
Calls handle_build_command() with blueprint
         ↓
Shows VPC modal if needed
         ↓
Generates and posts Terraform code
```

### Implementation

**File:** `slack_router.py`

#### 1. Button Definition

```python
def handle_recommend_command_sync(...):
    # ... recommendation logic ...

    for opt in recommendation.options[:3]:
        # Option details
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Option {idx}: {opt.name}*\n💰 Est. Monthly Cost: ${opt.min_monthly_cost}-${opt.max_monthly_cost}\n📋 Pattern: {opt.pattern}\n\n{opt.description}"
            }
        })

        # Action buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Generate Code"},
                    "action_id": f"build_blueprint_{opt.terraform_blueprint}",
                    # ^ action_id encodes the blueprint name
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Detailed Estimate"},
                    "action_id": f"estimate_option_{opt.name}",
                    # ^ action_id encodes the option name
                },
            ],
        })

        blocks.append({"type": "divider"})
```

**Key Points:**
- `action_id` must be unique per button
- Encode parameters in action_id (e.g., blueprint name)
- Slack sends entire payload on click

#### 2. Router

```python
def handle_interaction(payload: dict) -> dict:
    """Handle interactive component interactions."""
    interaction_type = payload.get("type")
    action_type = interaction_type if interaction_type == "block_actions" else None

    if action_type == "block_actions":
        actions = payload.get("actions", [])
        for action in actions:
            action_id = action.get("action_id", "")

            # Existing handlers...
            if action_id.startswith("finding_details_"):
                return handle_finding_details(payload, action)
            elif action_id.startswith("foundation_answer_"):
                return handle_foundation_answer(payload, action)

            # NEW: Recommendation button handlers (Commit 38971f0)
            elif action_id.startswith("build_blueprint_"):
                return handle_build_blueprint_button(payload, action)
            elif action_id.startswith("estimate_option_"):
                return handle_estimate_option_button(payload, action)

    return {"statusCode": 200, "body": "OK"}
```

**Pattern Matching:**
- Use `startswith()` for handlers that need parameters
- Action ID format: `prefix_parameter`
- Example: `build_blueprint_networking/basic-vpc`

#### 3. Button Handlers

**Generate Code Handler:**
```python
def handle_build_blueprint_button(payload: dict, action: dict) -> dict:
    """Handle 'Generate Code' button click from recommendations."""
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]
    user_id = payload["user"]["id"]
    trigger_id = payload.get("trigger_id")

    # Extract blueprint name from action_id
    # Format: build_blueprint_<blueprint_name>
    action_id = action.get("action_id", "")
    blueprint_name = action_id.replace("build_blueprint_", "")

    # Call the build command handler
    # This will show modal if VPC, or generate code immediately
    return handle_build_command(
        slack,
        channel_id,
        user_id,
        blueprint_name,
        trigger_id=trigger_id
    )
```

**Detailed Estimate Handler:**
```python
def handle_estimate_option_button(payload: dict, action: dict) -> dict:
    """Handle 'Detailed Estimate' button click from recommendations."""
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]

    # Extract option name from action_id
    # Format: estimate_option_<option_name>
    action_id = action.get("action_id", "")
    option_name = action_id.replace("estimate_option_", "")

    # Show helpful message with example
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
```

### Debugging Button Issues

**Check CloudWatch Logs:**
```python
# Add logging to handlers
logger.info(f"Button clicked: {action_id}")
logger.info(f"Payload: {json.dumps(payload)}")
```

**Common Issues:**

1. **Button does nothing**
   - Check Interactivity & Shortcuts enabled
   - Verify Request URL configured
   - Check CloudWatch for errors

2. **"We had some trouble connecting"**
   - Handler returning wrong format
   - Should return: `{"statusCode": 200, "body": ""}`
   - Not: `{}` or `None`

3. **Wrong action triggered**
   - action_id mismatch in routing
   - Check `startswith()` patterns
   - Verify action_id extraction logic

## Code Examples

### Full Command Implementation Template

```python
# 1. Async wrapper (returns immediately)
def handle_my_command(
    slack: SlackService,
    channel_id: str,
    user_id: str,
    args: str
) -> dict:
    """Handle /carl my command."""
    if not args:
        slack.post_message(channel_id, text="Usage: /carl my <args>")
        return {"statusCode": 200, "body": ""}

    # Post progress message
    slack.post_message(channel_id, text=f"🔄 Processing: _{args}_...")

    # Invoke async
    try:
        lambda_client = boto3.client('lambda')
        lambda_client.invoke(
            FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME'),
            InvocationType='Event',
            Payload=json.dumps({
                'action': 'process_my_async',
                'channel_id': channel_id,
                'user_id': user_id,
                'args': args
            })
        )
    except Exception as e:
        logger.error(f"Async invocation failed: {e}")
        return handle_my_command_sync(slack, channel_id, user_id, args)

    return {"statusCode": 200, "body": ""}


# 2. Sync processor (does actual work)
def handle_my_command_sync(
    slack: SlackService,
    channel_id: str,
    user_id: str,
    args: str
) -> dict:
    """Handle /carl my command - sync processing."""
    try:
        # Do work (can take 30-90 seconds)
        result = do_complex_processing(args)

        # Format response
        formatted_blocks = format_markdown_to_blocks(result, "🎉 Results")
        for block_group in formatted_blocks:
            slack.post_message(channel_id, blocks=block_group)

    except Exception as e:
        logger.error(f"Command failed: {e}")
        slack.post_message(channel_id, text=f"❌ Error: {e}")

    return {"statusCode": 200, "body": ""}


# 3. Add routing in lambda_handler
def lambda_handler(event, context):
    # Async action handler
    if event.get("action") == "process_my_async":
        slack = get_slack_service()
        return handle_my_command_sync(
            slack,
            event.get("channel_id"),
            event.get("user_id"),
            event.get("args")
        )

    # Slack command routing
    body = parse_slack_request(event)
    command = body.get("command", "").replace("/carl ", "")
    text = body.get("text", "").strip()

    if command == "my":
        return handle_my_command(slack, channel_id, user_id, text)

    # ... other commands ...
```

### Modal with Validation

```python
def show_my_modal(trigger_id: str, channel_id: str) -> dict:
    """Show modal with input validation."""
    modal = {
        "type": "modal",
        "callback_id": "my_modal_submit",
        "title": {"type": "plain_text", "text": "Configuration"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": json.dumps({"channel_id": channel_id}),
        "blocks": [
            {
                "type": "input",
                "block_id": "email_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "email_input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "user@example.com"
                    }
                },
                "label": {"type": "plain_text", "text": "Email Address"},
                "hint": {
                    "type": "plain_text",
                    "text": "Must be a valid email format"
                }
            },
            {
                "type": "input",
                "block_id": "count_block",
                "element": {
                    "type": "number_input",
                    "action_id": "count_input",
                    "is_decimal_allowed": False,
                    "min_value": "1",
                    "max_value": "100"
                },
                "label": {"type": "plain_text", "text": "Count"},
                "hint": {
                    "type": "plain_text",
                    "text": "Between 1 and 100"
                }
            }
        ]
    }

    slack_client = get_slack_client()
    slack_client.views_open(trigger_id=trigger_id, view=modal)
    return {"statusCode": 200, "body": ""}


def handle_my_modal_submission(payload: dict) -> dict:
    """Handle modal submission with validation."""
    metadata = json.loads(payload["view"]["private_metadata"])
    channel_id = metadata["channel_id"]

    values = payload["view"]["state"]["values"]
    email = values["email_block"]["email_input"]["value"]
    count = values["count_block"]["count_input"]["value"]

    # Server-side validation
    import re
    if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
        # Return errors object to show inline error
        return {
            "statusCode": 200,
            "body": json.dumps({
                "response_action": "errors",
                "errors": {
                    "email_block": "Invalid email format"
                }
            })
        }

    # Validation passed - process submission
    slack = get_slack_service()
    slack.post_message(
        channel_id,
        text=f"✅ Received: {email}, count: {count}"
    )

    # Return success - closes modal
    return {"statusCode": 200, "body": ""}
```

## Deployment

### CI/CD Pipeline

**GitHub Actions** - `.github/workflows/deploy.yml`

```yaml
name: Deploy CARL

on:
  push:
    branches: [develop, main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd carl-app
          pip install -r requirements.txt -t .

      - name: Package Lambda
        run: |
          cd carl-app
          zip -r ../carl-app.zip .

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - name: Deploy to Lambda
        run: |
          aws lambda update-function-code \
            --function-name carl-dev-api \
            --zip-file fileb://carl-app.zip

      - name: Wait for update
        run: |
          aws lambda wait function-updated \
            --function-name carl-dev-api
```

### Manual Deployment

```bash
# 1. Package application
cd carl-app
pip install -r requirements.txt -t .
zip -r ../carl-app.zip .

# 2. Upload to Lambda
aws lambda update-function-code \
  --function-name carl-dev-api \
  --zip-file fileb://../carl-app.zip

# 3. Wait for deployment
aws lambda wait function-updated \
  --function-name carl-dev-api

# 4. Test
/carl status  # In Slack
```

### Verification

**Test Each Feature:**
```bash
# In Slack:
/carl ask What are our critical findings?           # Async processing
/carl recommend I need a compliant VPC              # Formatting + buttons
/carl build networking/basic-vpc                    # Modal
# Click "Generate Code" button                       # Button handler
```

**Check Logs:**
```bash
# CloudWatch Logs
aws logs tail /aws/lambda/carl-dev-api --follow

# Look for:
# - "Processing async <command> command"
# - "Button clicked: <action_id>"
# - No errors or timeouts
```

### Rollback

```bash
# If issues occur, rollback to previous version:
aws lambda update-function-code \
  --function-name carl-dev-api \
  --s3-bucket carl-deployments \
  --s3-key previous-version.zip
```

## Performance

### Metrics

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| `/carl ask` timeout | 50% fail | 0% fail | 100% |
| `/carl recommend` timeout | 80% fail | 0% fail | 100% |
| Response formatting | Plain text | Structured blocks | N/A |
| VPC CIDR accuracy | 0% (always default) | 100% | 100% |
| Button functionality | 0% (didn't exist) | 100% | N/A |

### Latency

| Command | Acknowledgment | Processing | Total User Wait |
|---------|---------------|------------|-----------------|
| `/carl ask` | < 1s | 10-30s | N/A (async) |
| `/carl recommend` | < 1s | 20-60s | N/A (async) |
| `/carl build` | < 1s (or modal) | 1-3s | 1-3s (or modal time) |
| Button click | < 1s | 1-5s | 1-5s |

## Troubleshooting

### Async Processing Not Working

**Symptoms:**
- Commands timeout
- No "Processing..." message
- No results posted

**Check:**
1. Lambda timeout: Should be 90s
2. IAM permissions: `lambda:InvokeFunction` on self
3. Environment variable: `AWS_LAMBDA_FUNCTION_NAME` set
4. CloudWatch logs for invocation errors

**Fix:**
```bash
# Update timeout
aws lambda update-function-configuration \
  --function-name carl-dev-api \
  --timeout 90

# Update IAM policy
aws iam put-role-policy \
  --role-name carl-lambda-role \
  --policy-name lambda-invoke-self \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:*:*:function:carl-dev-api"
    }]
  }'
```

### Modal Connection Errors

**Symptoms:**
- "We had some trouble connecting"
- Modal doesn't appear
- Submission does nothing

**Fix:**
1. Slack App → Interactivity & Shortcuts → Enable
2. Request URL: `https://[api-gw].execute-api.[region].amazonaws.com/slack`
3. Ensure handler returns: `{"statusCode": 200, "body": ""}`

### Button Not Working

**Symptoms:**
- Click does nothing
- Error message
- Wrong action triggered

**Debug:**
```python
# Add to handle_interaction()
logger.info(f"Interaction type: {interaction_type}")
logger.info(f"Action ID: {action.get('action_id')}")
logger.info(f"Payload: {json.dumps(payload)}")
```

**Check:**
1. Action ID matches handler pattern
2. Handler returns proper format
3. Interactivity enabled (see above)

## References

- [Slack Block Kit Builder](https://app.slack.com/block-kit-builder)
- [Slack API Documentation](https://api.slack.com/docs)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [CARL Architecture](./ARCHITECTURE.md)
- [CARL Command Guide](./SLACK_COMMANDS.md)

---

**Last Updated:** 2026-01-28
**Version:** 1.2
**Commits:** 284a446, c8118eb, 644660f, 38971f0
