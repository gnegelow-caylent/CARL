# CARL Slack Commands Guide

> Comprehensive guide to using CARL through Slack with interactive features

## Table of Contents

- [Overview](#overview)
- [Command Categories](#command-categories)
- [Interactive Features](#interactive-features)
- [Recent Improvements](#recent-improvements)
- [Command Reference](#command-reference)
- [Troubleshooting](#troubleshooting)

## Overview

CARL provides a natural, conversational interface through Slack. All commands start with `/carl` and support:

- **Async Processing**: Long-running operations (architect, ask, recommend) return immediately with progress updates
- **Interactive Modals**: Configuration input through user-friendly forms
- **Formatted Responses**: Structured blocks with headers, sections, code blocks, and buttons
- **Action Buttons**: Click-to-action workflow (e.g., Generate Code → Build → Deploy)

## Command Categories

### 1. Compliance & Monitoring

#### `/carl status`
Get a real-time compliance posture summary with health indicators.

**Features:**
- 🟢 Healthy (≤5 findings)
- 🟡 Needs Attention (6-20 findings)
- 🟠 Action Required (21-50 findings)
- 🔴 Critical (>50 findings)
- Severity breakdown (Critical, High, Medium, Low)
- Recent findings with details

**Example:**
```
/carl status
```

**Response Format:**
- Header with health indicator
- Finding counts by severity
- Recent findings list with timestamps
- Quick action buttons

---

#### `/carl findings [severity]`
List compliance findings, optionally filtered by severity.

**Severity Levels:**
- `CRITICAL` - Immediate action required
- `HIGH` - High priority
- `MEDIUM` - Medium priority
- `LOW` - Low priority

**Examples:**
```
/carl findings                 # All findings
/carl findings CRITICAL        # Critical only
/carl findings HIGH            # High severity only
```

**Response Format:**
- Finding title and description
- Affected resource
- Control ID (e.g., CC6.1)
- Remediation steps
- "View Details" button for each finding
- **Refresh reminder**: Suggests running `/carl evidence collect` to update with latest AWS state

**Note:** Findings are based on the most recent evidence collection. Run `/carl evidence collect` to refresh with current AWS configuration.

---

#### `/carl ask <question>`
Natural language query with context-aware responses.

**Features:**
- **Async processing** - returns immediately, processes in background
- **Security Hub integration** - includes real-time finding data
- **Formatted responses** - structured blocks with headers and sections
- **Context-aware** - understands your environment state

**Examples:**
```
/carl ask What are our critical security findings?
/carl ask Do we have encryption at rest enabled?
/carl ask What's the status of our VPC security groups?
/carl ask How do I enable GuardDuty?
```

**Processing Flow:**
1. Command submitted → immediate "🤔 Thinking..." response
2. Background processing (queries Security Hub, analyzes context)
3. Formatted response posted with sections and code blocks

**Response Format:**
- Header: "💬 CARL's Response"
- Structured sections based on content
- Code blocks for commands/configs
- Bullet points and lists
- Context boxes for additional info

**Multi-Agent Handoffs (NEW):**

When `/carl ask` detects certain intent patterns, it offers to hand off to a specialized agent:

**Architecture Intent → Architect Agent:**
```
/carl ask How should I design my VPC for a multi-tier application?

CARL: "Your question suggests you're looking for architecture
       recommendations. Would you like me to hand this off to the
       Architect Agent for detailed design guidance?"

       [✅ Yes, continue with Architect] [❌ No thanks]
```

**Remediation Intent → Remediate Agent:**
```
/carl ask Fix my S3 encryption issues

CARL: "I found 3 security issues that can be remediated:
       unencrypted S3 bucket, public access not blocked.
       Want me to hand off to the Remediate Agent?"

       [🔧 Fix with Remediate Agent] [ℹ️ Just show info]
```

**Handoff Flow:**
1. Ask Agent analyzes question + scan results
2. Detects intent (architecture or remediation)
3. Shows handoff suggestion with buttons (if confidence ≥70%)
4. User accepts → Target agent receives full context
5. User declines → Continue with Ask Agent response

**Context Passed to Target Agent:**
- Original question
- Scan results and findings
- Session ID for continuity
- Channel/thread info

---

### 2. Architecture & Building

#### `/carl architect <question>`
AI-driven architecture recommendations with continuous learning.

**Features:**
- **Async processing** - handles complex analysis without timeout
- **Multi-option recommendations** - presents 2-3 viable approaches
- **Pros/cons analysis** - detailed trade-offs for each option
- **Cost estimates** - accurate pricing for each approach
- **Learning feedback** - improves recommendations over time

**Examples:**
```
/carl architect How should I design a multi-tier application?
/carl architect What's the best way to implement private connectivity?
/carl architect I need a secure database architecture
/carl architect Design a compliant logging infrastructure
```

**Processing Flow:**
1. Command submitted → "🏗️ Analyzing your architecture question..." message
2. Background AI analysis (can take 30-60 seconds)
3. Formatted response with multiple options
4. Each option includes feedback buttons (👍/👎)

**Response Format:**
- Header: "🏗️ Architecture Recommendation"
- Multiple sections for different approaches
- Pros/cons for each approach
- Cost estimates
- Terraform blueprint references
- Feedback buttons for continuous learning

---

#### `/carl recommend <requirement>`
Get architecture recommendations with accurate cost comparison and interactive code generation.

**Features:**
- **Async processing** - no timeout on complex analysis
- **Multiple options** - 2-3 recommendations with detailed cost breakdowns
- **AI analysis** - formatted with structured sections and headers
- **Interactive buttons**:
  - **Generate Code** - triggers `/carl build` with the blueprint
  - **Detailed Estimate** - shows how to get itemized costs
- **Cost considerations** - real-world cost factors and optimization tips

**Examples:**
```
/carl recommend I need a compliant VPC with WAF protection
/carl recommend Private connectivity between VPCs in different regions
/carl recommend Multi-account security logging architecture
/carl recommend Centralized egress with inspection
```

**Processing Flow:**
1. Command submitted → "🔍 Analyzing architecture options..." message
2. Background processing:
   - Query architecture patterns knowledge base
   - Calculate accurate costs (not estimates!)
   - Generate AI analysis with recommendations
3. Response posted in multiple messages:
   - Options summary with costs
   - Each option has action buttons
   - AI analysis in formatted blocks
   - Cost considerations

**Response Format:**

**Message 1: Options Summary**
```
🎯 Architecture Recommendations: [Your Requirement]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Option 1: [Name]
💰 Est. Monthly Cost: $XXX-$XXX
📋 Pattern: [Category/Pattern Name]

[Description of the approach]

[Generate Code] [Detailed Estimate]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Option 2: [Name]
...
```

**Message 2: AI Analysis**
- Header: "🤖 AI Analysis"
- Structured sections with markdown formatting
- Code examples where relevant
- Comparison points between options
- Security considerations
- Compliance implications

**Message 3: Cost Considerations**
- Bullet points with cost optimization tips
- Variable cost factors to consider
- Scaling implications
- Hidden costs to watch for

**Interactive Buttons:**

1. **"Generate Code" Button**
   - Triggers `/carl build [blueprint]` command
   - Shows VPC configuration modal if needed
   - Generates production-ready Terraform code
   - Code displayed in formatted code blocks

2. **"Detailed Estimate" Button**
   - Shows helpful message about `/carl estimate` command
   - Provides example usage
   - Explains how to get itemized cost breakdowns

---

#### `/carl build <blueprint>`
Generate production-ready Terraform code for infrastructure patterns.

**Features:**
- **Interactive modals** - VPC blueprints show CIDR configuration form
- **Code block formatting** - syntax-highlighted Terraform output
- **Multi-part responses** - automatically splits large code into readable chunks
- **Production-ready** - includes compliance configurations and best practices

**VPC Blueprints (show modal):**
- `networking/basic-vpc` - Standard VPC with public/private subnets
- `networking/standard-vpc` - Standard VPC with NAT gateways
- `networking/three-tier-vpc` - Three-tier architecture VPC
- Any blueprint containing "vpc" in the name

**Non-VPC Blueprints (immediate generation):**
- `security/guardduty` - GuardDuty configuration
- `security/security-hub` - Security Hub setup
- `logging/cloudtrail` - CloudTrail logging
- `compliance/config-rules` - AWS Config rules
- And many more...

**Examples:**
```
/carl build networking/basic-vpc        # Shows modal for CIDR input
/carl build security/guardduty          # Generates code immediately
/carl build logging/cloudtrail          # Generates code immediately
```

**VPC Configuration Modal:**
```
┌─────────────────────────────────────────┐
│ VPC Configuration                       │
├─────────────────────────────────────────┤
│ VPC Name:        [main-vpc___________]  │
│ Environment:     [prod_______________]  │
│ CIDR Block:      [10.0.0.0/16________]  │
│                                         │
│         [Cancel]  [Generate Code]       │
└─────────────────────────────────────────┘
```

**Modal Validation:**
- CIDR format: `X.X.X.X/X` (e.g., 10.0.0.0/16)
- Must be valid IPv4 CIDR notation
- Typically /16 for VPCs (65,536 IPs)

**Processing Flow:**

1. **VPC Blueprints:**
   - Command submitted → Modal appears
   - User fills in configuration
   - "Generate Code" clicked
   - Confirmation message: "Configuration received! Generating..."
   - Terraform code posted in formatted blocks

2. **Non-VPC Blueprints:**
   - Command submitted → Immediate generation
   - "Generating compliant Terraform code..." message
   - Terraform code posted in formatted blocks

**Response Format:**
```
*Terraform Code: networking/basic-vpc*

```terraform
# Part 1

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

module "vpc" {
  source = "terraform-aws-modules/vpc/aws"
  ...
}
```

[If code > 2900 chars, shows Part 2...]
```

**Code Splitting:**
- Slack has a ~3000 character limit per message block
- CARL automatically splits at 2900 chars to be safe
- Shows "Part 1", "Part 2", etc. headers
- Preserves code block formatting in each part

---

#### `/carl patterns [category]`
Browse architecture patterns with visual categorization.

**Categories:**
- `networking` - VPC designs, egress, ingress, transit
- `connectivity` - VPN, Direct Connect, VPC peering
- `endpoints` - **NEW:** VPC endpoints, PrivateLink patterns
- `encryption` - **NEW:** KMS, encryption at rest
- `identity` - IAM, Identity Center, federation
- `security` - Security Hub, GuardDuty, WAF, Firewall
- `logging` - CloudTrail, CloudWatch, centralized logging
- `account` - Multi-account, Organizations, Control Tower
- `operational` - Tagging, backup, cost management
- `inspection` - Network inspection, egress filtering

**Examples:**
```
/carl patterns                  # All categories
/carl patterns networking       # Networking patterns only
/carl patterns encryption       # Encryption patterns
/carl patterns endpoints        # VPC endpoints and PrivateLink
```

**Response Format:**
```
🏗️ Architecture Patterns

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 NETWORKING PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Standard VPC with NAT Gateway
📦 Pattern: networking/standard-vpc
💰 Cost: $98-196/mo (2-3 AZ)
ℹ️ VPC with public/private subnets, NAT gateways for outbound traffic

📋 Three-Tier VPC Architecture
📦 Pattern: networking/three-tier-vpc
💰 Cost: $294/mo (3 AZ)
ℹ️ Web, app, database tiers with isolated subnets

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 ENCRYPTION PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
...
```

---

#### `/carl estimate <component>`
Get accurate cost estimates for AWS components.

**Examples:**
```
/carl estimate rds multi-az 100gb
/carl estimate nat gateway 2 availability zones
/carl estimate network firewall with 3 endpoints
/carl estimate waf with 10 rules
```

**Response Format:**
- Itemized cost breakdown
- Monthly and annual totals
- Data transfer considerations
- Cost optimization tips

---

#### `/carl blueprints`
List all available infrastructure blueprints.

**Response Format:**
- Organized by category
- Pattern name and description
- Estimated costs
- Use with `/carl build <blueprint>` command

---

### 3. Audit & Evidence

#### `/carl evidence collect`
Collect audit evidence across all AWS resources.

**What Gets Collected:**
- CloudTrail logs
- Config snapshots
- Security Hub findings
- GuardDuty detections
- IAM configurations
- Encryption status (S3, RDS, EBS)
- Network configurations
- Backup status

**Processing:**
- **Async operation** (no timeout, completes in background)
- Immediate response within 3 seconds
- Completion messages posted when done (2-5 minutes)
- Results stored in DynamoDB
- Mapped to SOC 2 controls
- **Auto-resolve**: Findings automatically marked as REMEDIATED when evidence shows issues are fixed

**Recent Improvements:**
- Fixed S3 encryption permission check (s3:GetEncryptionConfiguration)
- Eliminated timeout errors with instant async invocation
- Auto-resolution of fixed findings

---

#### `/carl evidence status`
View evidence collection coverage.

**Response Format:**
- Control coverage percentage
- Last collection time
- Evidence count by control
- Missing evidence alerts

---

#### `/carl report <type>`
Generate compliance reports in markdown format.

**Report Types:**
- `executive` - Executive summary (2-3 pages)
- `full` - Complete audit report (15-25 pages)
- `control <id>` - Specific control report (e.g., CC6.1)

**Processing Flow:**
1. Command submitted → "Generating report..." message
2. Environment scanning (if not recent)
3. Report generation
4. Upload to S3 with 24-hour presigned URL
5. Summary + download link posted to Slack

**Report Contents:**
- Executive summary
- Compliance posture
- Finding details with evidence
- Remediation recommendations
- Control mappings
- Risk exceptions
- Drift detections

**File Format:**
- Markdown (.md) files
- Viewable in any browser
- Easy to convert to PDF locally
- No binary dependencies

---

### 4. Risk Management

#### `/carl exception list`
View all risk exceptions.

**Response Format:**
- Pending exceptions (awaiting approval)
- Active exceptions (approved, with expiry dates)
- Expired exceptions
- Denied exceptions

---

#### `/carl exception request`
Request a new risk exception.

**Interactive Flow:**
1. Modal appears with form
2. Fill in:
   - Finding ID
   - Justification (business reason)
   - Compensating controls
   - Requested duration (days)
3. Submit for approval

---

#### `/carl exception approve <id>`
Approve a pending risk exception.

**Requires:** Approval permissions (security team)

---

#### `/carl exception deny <id>`
Deny a pending risk exception.

**Requires:** Approval permissions (security team)

---

#### `/carl exception stats`
View risk exception statistics.

**Metrics:**
- Total exceptions
- Pending approvals
- Expiring soon (< 30 days)
- By severity
- By control category

---

### 5. Drift Detection

#### `/carl drift scan`
Scan for infrastructure drift.

**What It Detects:**
- Security group changes
- IAM policy modifications
- Encryption setting changes
- Logging configuration drift
- Network configuration changes

---

#### `/carl drift status`
View detected drift.

**Response Format:**
- Drift count by resource type
- Recent drift detections
- Severity indicators
- Remediation recommendations

---

#### `/carl drift acknowledge <id>`
Acknowledge and accept drift.

**Use Cases:**
- Intentional changes
- Emergency fixes
- Approved modifications

---

#### `/carl drift terraform`
Generate Terraform to remediate drift.

**Features:**
- Analyzes current vs. desired state
- Generates corrective Terraform
- Includes rollback plan
- Shows impact preview

---

#### `/carl drift jira-sync`
Create Jira tickets for drift items.

**Features:**
- **Duplicate Prevention**: Checks for existing tickets before creating
- Verifies tickets still exist in Jira (handles deleted tickets)
- Skips acknowledged or remediated drift
- Only tickets security-relevant or high/critical drift
- Async processing (no timeout)
- Progress updates every 5 items

**Response Format:**
- Synced count (new tickets created)
- Skipped count (tickets already exist)
- Recreated count (tickets were deleted in Jira)
- Failed count

**Use Cases:**
- Track drift remediation in Jira
- Assign drift fixes to team members
- Report on configuration drift trends
- Integrate drift detection with project management

---

## Interactive Features

### 1. Configuration Modals

**When They Appear:**
- VPC builds (CIDR configuration)
- Risk exception requests
- Foundation builder wizard steps

**Features:**
- Input validation
- Help text and examples
- Error messages for invalid input
- Cancel/Submit buttons

**Response Format:**
```json
{
  "statusCode": 200,
  "body": ""
}
```

**Troubleshooting:**
- If you see "We had some trouble connecting", check:
  1. Slack App → Interactivity & Shortcuts is enabled
  2. Request URL is configured: `https://[your-api].execute-api.[region].amazonaws.com/slack`
  3. Lambda has proper permissions

---

### 2. Action Buttons

**Types of Buttons:**

1. **View Details** (findings)
   - Shows full finding details
   - Remediation steps
   - Affected resources

2. **Generate Code** (recommendations)
   - Triggers `/carl build` with blueprint
   - Shows VPC modal if needed
   - Posts formatted Terraform code

3. **Detailed Estimate** (recommendations)
   - Shows guidance on `/carl estimate`
   - Example usage
   - Cost breakdown info

4. **Feedback** (architect responses)
   - 👍 Thumbs up - helps improve recommendations
   - 👎 Thumbs down - marks for review
   - Stored for continuous learning

5. **Deploy Infrastructure** (foundation builder)
   - Reviews deployment plan
   - Shows confirmation modal
   - Executes deployment

**Button Response Time:**
- Immediate acknowledgment (< 1 second)
- Background processing if needed
- Progress updates posted

---

### 3. Formatted Responses

CARL uses Slack's Block Kit for rich formatting:

**Block Types:**
- **Headers** - Large, prominent titles
- **Sections** - Text with optional images/buttons
- **Dividers** - Visual separation
- **Code Blocks** - Syntax-highlighted code
- **Context** - Small, muted text for metadata
- **Actions** - Buttons and interactive elements

**Markdown Support:**
- `*bold*` - **bold text**
- `_italic_` - _italic text_
- `` `code` `` - `inline code`
- ` ```language ` - code blocks
- `• bullet` - bullet points
- `> quote` - quoted text

**Message Splitting:**
- Slack limits: 50 blocks per message, 3000 chars per text block
- CARL automatically splits long responses
- Maintains formatting across splits
- Posts as sequential messages

---

## Recent Improvements

### January 31, 2026 - Evidence Collection & Drift Management

#### 1. Fixed Evidence Collection Timeout ✅
**Problem:** `/carl evidence collect` showed "operation_timeout" error despite completing successfully.

**Solution:** Invoke async Lambda IMMEDIATELY without EvidenceCollector initialization:
- Responds within 3 seconds (before Slack timeout)
- Heavy boto3 client initialization happens in background
- Completion messages posted when done

**Result:** No more timeout errors, clear completion feedback

---

#### 2. Auto-Resolve Findings 🎯
**Problem:** Findings stayed "NEW" even after issues were fixed (e.g., S3 encryption enabled).

**Solution:** Auto-resolution logic in evidence collector:
- Tracks which findings SHOULD exist based on current evidence
- Scans existing findings in DynamoDB
- Marks findings as REMEDIATED when evidence shows issue is fixed
- Logs: "Resolved finding {id}: {title} (issue fixed)"

**Result:** Findings automatically update to reflect current AWS state

---

#### 3. S3 Encryption Permission Fix 🔐
**Problem:** Evidence collection showed S3 encryption as "ERROR" (AccessDenied).

**Root Cause:**
- Boto3 method: `get_bucket_encryption()`
- IAM action required: `s3:GetEncryptionConfiguration` (AWS named them differently!)
- Lambda role had wrong action: `s3:GetBucketEncryption`

**Solution:** Fixed IAM policy to use correct action name

**Result:** S3 encryption status now detected correctly

---

#### 4. Drift Detection Jira Integration 🎫
**New Feature:** `/carl drift jira-sync` command

**Capabilities:**
- Creates Jira tickets for drift items
- **Duplicate prevention**: Checks DynamoDB for existing ticket IDs
- Verifies tickets still exist in Jira (handles deleted tickets)
- Only tickets security-relevant or high/critical drift
- Async processing with progress updates
- Reuses same ticket creation engine as findings

**Use Case:** Track configuration drift remediation in Jira project management

---

#### 5. Fixed False Drift Alerts 🚨
**Problem:** ALL S3 buckets flagged as critical drift, even when fully compliant.

**Root Cause:** Evidence description "S3 bucket security configuration including encryption, **public** access, versioning" contained keyword "public" which triggered drift detector's issue indicator check.

**Solution:** Changed to neutral description: "S3 bucket configuration snapshot for {bucket_name}"

**Result:** Only actual drift (missing encryption, public buckets, etc.) is flagged

---

#### 6. Findings Refresh Reminder 💡
**Improvement:** `/carl findings` now shows context message:
- "💡 _To refresh findings with latest AWS state, run `/carl evidence collect`_"
- Helps users understand findings may be stale
- `/carl status` already does live scan, so no reminder needed there

---

### January 2026 Updates

#### 1. Async Processing (No More Timeouts!)
**Problem:** Commands like `/carl ask`, `/carl architect`, and `/carl recommend` were failing with "operation_timeout" errors.

**Solution:** Converted to async Lambda self-invocation pattern:
- Command returns immediately with "Analyzing..." message
- Processing happens in background (can take 30-90 seconds)
- Result posted when complete
- No Slack timeout (3-second limit)

**Affected Commands:**
- `/carl ask` ✅
- `/carl architect` ✅
- `/carl recommend` ✅
- `/carl report` ✅

**Commits:**
- 60404f2 - Report command async
- 644660f - Recommend command async

---

#### 2. VPC Modal Improvements
**Problem 1:** Modal only appeared for specific blueprint names, missing `networking/standard-vpc`.

**Solution:** Changed from hardcoded list to pattern matching - any blueprint with "vpc" in the name shows the modal.

**Problem 2:** User-entered CIDR values weren't being passed to generated code (defaulted to 10.0.0.0/16).

**Solution:** Fixed configuration key name mismatch (`vpc_cidr` → `cidr`).

**Commits:**
- 284a446 - Pattern-based modal triggering
- c8118eb - CIDR config key fix

---

#### 3. Response Formatting Overhaul
**Problem:** Responses were plain text walls, hard to read, no structure.

**Solution:** Created `format_markdown_to_blocks()` converter that transforms markdown into structured Slack blocks:
- Headers for sections
- Code blocks with syntax highlighting
- Bullet points and lists
- Dividers for visual separation
- Context boxes for metadata

**Improved Commands:**
- `/carl status` - Health indicators (🔴🟠🟡🟢)
- `/carl ask` - Structured response with sections
- `/carl architect` - Multiple options with pros/cons
- `/carl recommend` - AI analysis in formatted blocks ✅
- `/carl patterns` - Visual categorization with emojis

**Commits:**
- d6f74b6 - Initial formatting improvements
- 38971f0 - Recommend command formatting ✅

---

#### 4. Terraform Code Display Fix
**Problem:** Generated Terraform code showing as plain text, not in code blocks.

**Solution:** Use Slack blocks with `mrkdwn` type instead of plain text:
```python
{
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": "```terraform\n{code}\n```"
    }
}
```

**Additional Improvements:**
- Increased character limit from 2500 to 2900 per block
- Automatic splitting into "Part 1", "Part 2" for large code
- Preserves formatting across splits

**Commits:**
- 7943e8f - Code block formatting
- dc47f3b - Multi-part support

---

#### 5. Recommendation Button Handlers
**Problem:** "Generate Code" and "Detailed Estimate" buttons on `/carl recommend` responses didn't work.

**Solution:** Added action handlers in `handle_interaction()`:

**"Generate Code" Button:**
- Action ID pattern: `build_blueprint_<blueprint_name>`
- Handler: `handle_build_blueprint_button()`
- Flow: Extract blueprint name → trigger `/carl build` → show modal if VPC → generate code

**"Detailed Estimate" Button:**
- Action ID pattern: `estimate_option_<option_name>`
- Handler: `handle_estimate_option_button()`
- Flow: Extract option name → show helpful message with `/carl estimate` example

**Commit:** 38971f0 ✅

---

#### 6. VPC Modal Connection Fix
**Problem:** VPC modal submission showed "We had some trouble connecting. Try again?" error.

**Root Causes:**
1. Slack App → Interactivity & Shortcuts was disabled
2. Modal submission handler returned wrong response format

**Solution:**
1. User enabled Interactivity & Shortcuts in Slack app settings
2. Configured Request URL: `https://[api-gateway].execute-api.[region].amazonaws.com/slack`
3. Fixed response format: `{"statusCode": 200, "body": ""}` instead of `{}`

**Commits:**
- d6f74b6 - Initial attempt
- 7943e8f - Response format fix
- dc47f3b - Final working fix ✅

---

## Troubleshooting

### Command Timeouts

**Symptom:** "operation_timeout" error message

**Cause:** Slack requires response within 3 seconds

**Solution:** Commands now use async processing - this should not occur anymore. If it does:
1. Check CloudWatch logs for errors
2. Verify Lambda timeout is 90 seconds (not 30)
3. Check if Lambda self-invocation is working

---

### Modal Connection Errors

**Symptom:** "We had some trouble connecting. Try again?"

**Solution:**
1. Go to Slack App settings → Interactivity & Shortcuts
2. Enable if disabled
3. Set Request URL to: `https://[your-api].execute-api.[region].amazonaws.com/slack`
4. Save changes
5. Try command again

---

### Buttons Not Working

**Symptom:** Clicking buttons shows error or does nothing

**Possible Causes:**
1. Interactivity & Shortcuts disabled (see above)
2. Action handler missing in code
3. Lambda permissions issue

**Check:**
1. CloudWatch Logs → Lambda → Recent invocations
2. Look for errors related to action_id
3. Verify button action_id matches handler pattern

---

### Code Not Formatted

**Symptom:** Terraform code showing as plain text, not in code blocks

**Cause:** Using wrong message format

**Solution:** Ensure code is sent with blocks, not plain text:
```python
slack.post_message(channel_id, blocks=[{
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": f"```terraform\n{code}\n```"
    }
}])
```

---

### VPC CIDR Not Applied

**Symptom:** Entered CIDR in modal, but generated code shows 10.0.0.0/16

**Cause:** Configuration key mismatch

**Solution:** Fixed in commit c8118eb - ensure you're on latest version:
```bash
git pull origin develop
# GitHub Actions will auto-deploy
```

---

### Missing Progress Updates

**Symptom:** No "Analyzing..." or progress messages

**Cause:** Async invocation issue

**Check:**
1. Lambda environment variable: `AWS_LAMBDA_FUNCTION_NAME` set correctly
2. Lambda IAM role has `lambda:InvokeFunction` permission on itself
3. CloudWatch Logs for invocation errors

---

### Report Generation Fails

**Symptom:** "AccessDeniedException" when generating reports

**Cause:** Missing permissions or infrastructure

**Solution:**
1. Verify DynamoDB tables exist:
   - `carl-dev-evidence`
   - `carl-dev-findings`
   - `carl-dev-exceptions`
2. Verify S3 buckets exist:
   - `carl-dev-evidence-[account-id]`
   - `carl-dev-reports-[account-id]`
3. Check Lambda IAM role has read/write access

---

## Development Notes

### Adding New Commands

1. **Update slack_router.py:**
```python
def handle_new_command(slack: SlackService, channel_id: str, user_id: str, args: str) -> dict:
    """Handle /carl new command."""
    # Implementation
    return {"statusCode": 200, "body": ""}
```

2. **Add routing in main handler:**
```python
if command == "new":
    return handle_new_command(slack, channel_id, user_id, text)
```

3. **If long-running, use async pattern:**
```python
def handle_new_command(slack, channel_id, user_id, args):
    slack.post_message(channel_id, text="🔄 Processing...")

    lambda_client.invoke(
        FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME'),
        InvocationType='Event',
        Payload=json.dumps({
            'action': 'process_new_async',
            'channel_id': channel_id,
            'user_id': user_id,
            'args': args
        })
    )

    return {"statusCode": 200, "body": ""}

def handle_new_command_sync(slack, channel_id, user_id, args):
    # Actual processing
    result = do_work(args)
    slack.post_message(channel_id, text=f"✅ {result}")
    return {"statusCode": 200, "body": ""}
```

4. **Add async handler routing:**
```python
if event.get("action") == "process_new_async":
    return handle_new_command_sync(slack, event.get("channel_id"), ...)
```

---

### Adding Interactive Buttons

1. **Add button to message:**
```python
blocks.append({
    "type": "actions",
    "elements": [{
        "type": "button",
        "text": {"type": "plain_text", "text": "Click Me"},
        "action_id": "my_button_action",
    }]
})
```

2. **Add handler:**
```python
def handle_my_button(payload: dict, action: dict) -> dict:
    slack = get_slack_service()
    channel_id = payload["channel"]["id"]

    # Process action
    slack.post_message(channel_id, text="Button clicked!")

    return {"statusCode": 200, "body": ""}
```

3. **Add routing:**
```python
# In handle_interaction():
elif action_id == "my_button_action":
    return handle_my_button(payload, action)
```

---

### Creating Modals

1. **Define modal structure:**
```python
modal = {
    "type": "modal",
    "callback_id": "my_modal_submit",
    "title": {"type": "plain_text", "text": "Configuration"},
    "submit": {"type": "plain_text", "text": "Submit"},
    "close": {"type": "plain_text", "text": "Cancel"},
    "blocks": [
        {
            "type": "input",
            "block_id": "field1_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "field1_action",
                "placeholder": {"type": "plain_text", "text": "Enter value"}
            },
            "label": {"type": "plain_text", "text": "Field 1"}
        }
    ]
}
```

2. **Open modal:**
```python
slack_client.views_open(trigger_id=trigger_id, view=modal)
```

3. **Handle submission:**
```python
# In handle_interaction():
if view_type == "view_submission":
    callback_id = payload.get("view", {}).get("callback_id")

    if callback_id == "my_modal_submit":
        values = payload["view"]["state"]["values"]
        field1 = values["field1_block"]["field1_action"]["value"]

        # Process submission
        # MUST return proper format:
        return {"statusCode": 200, "body": ""}
```

---

## Support & Resources

- **GitHub Issues:** https://github.com/gnegelow-caylent/CARL/issues
- **Documentation:** See other .md files in project root
- **CloudWatch Logs:** Monitor Lambda invocations for debugging
- **Slack API Docs:** https://api.slack.com/block-kit

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-27 | Initial feature release |
| 1.1 | 2026-01-28 | Async processing, formatting improvements |
| 1.2 | 2026-01-28 | VPC modal fixes, button handlers, recommend improvements |

---

**Last Updated:** 2026-01-28
**Maintained By:** CARL Development Team
