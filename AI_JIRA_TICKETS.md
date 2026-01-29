# AI-Powered Jira Ticket Generation

CARL now uses Claude AI (via AWS Bedrock) to generate intelligent, human-friendly Jira tickets instead of robotic templates.

## What Changed

### Before (Robotic Templates)
```
Finding Details
Description: S3 bucket my-bucket has no encryption configured

Affected Resource
ARN: arn:aws:s3:::my-bucket

SOC 2 Controls
CC6.7, C1.1
```

### After (AI-Generated, Human-Friendly)
```
## Problem Statement
The S3 bucket "my-bucket" doesn't have default encryption enabled. This means any files
uploaded without explicit encryption will be stored in plaintext on disk, potentially
exposing sensitive data to unauthorized access.

## Business Impact
If this bucket contains customer data, PII, or confidential information, you're at risk of:
- Data breach if bucket permissions are misconfigured
- Compliance violations for SOC 2 (CC6.7 - Confidentiality) and potentially GDPR/HIPAA
- Audit findings that could delay certification

## Affected Resource
• Type: S3 Bucket
• Identifier: my-bucket
• ARN: arn:aws:s3:::my-bucket
• Account: 403802364021
• Region: us-east-1

## Remediation Steps
1. **Open S3 Console**: Navigate to AWS Console → S3 → Select "my-bucket"
2. **Enable Default Encryption**:
   - Go to "Properties" tab
   - Scroll to "Default encryption"
   - Click "Edit"
   - Select "Enable" and choose:
     - AES-256 (SSE-S3) for general use
     - AWS KMS (SSE-KMS) for compliance requirements
   - Click "Save changes"
3. **Verify Encryption**:
   ```bash
   aws s3api get-bucket-encryption --bucket my-bucket
   ```
   Should return encryption configuration, not "ServerSideEncryptionConfigurationNotFoundError"
4. **Document Change**: Add entry to change log with date, person, and reason

## Acceptance Criteria
- [x] Default encryption enabled on bucket (either SSE-S3 or SSE-KMS)
- [x] Encryption verified via AWS CLI
- [x] Change documented in change log
- [x] Next compliance scan shows this finding as resolved

## SOC 2 Compliance
This finding affects SOC 2 controls CC6.7 (Confidentiality) and C1.1 (Data Protection).
Auditors will look for evidence that sensitive data is encrypted at rest to meet
confidentiality requirements.

## References
- AWS Documentation: https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-bucket-encryption.html
- CARL Finding ID: my-bucket
```

## Key Improvements

### 1. **Crystal Clear Problem Statement**
- Explains what's wrong in plain English
- No jargon or acronyms without explanation
- Anyone can understand the issue

### 2. **Business Impact**
- Specific consequences if not fixed
- Compliance implications
- Real-world risks (not just "security issue")

### 3. **Step-by-Step Instructions**
- Exact console paths: "AWS Console → S3 → Properties"
- Actual CLI commands with the resource name filled in
- Verification steps so they know it worked
- Documentation reminders

### 4. **Acceptance Criteria**
- Checkboxes for testing
- Specific, measurable outcomes
- Clear definition of "done"

### 5. **Context for Auditors**
- Which SOC 2 controls are affected
- Why auditors care about this
- What they'll be looking for

## How It Works

### 1. **Bedrock Service Enhancement**
```python
# New method in bedrock_service.py
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
    # AI analyzes the finding and generates human-friendly description
    # with problem statement, impact, steps, acceptance criteria, etc.
```

### 2. **Jira Service Integration**
```python
# Updated in jira_service.py
def create_security_finding(...):
    # Generate AI description
    bedrock = BedrockService()
    ai_description = bedrock.generate_jira_ticket_description(...)

    # Convert markdown to Jira's Atlassian Document Format (ADF)
    jira_description = self._markdown_to_adf(ai_description)

    # Create ticket with AI-generated content
    result = self._make_request("POST", "issue", data=issue_data)
```

### 3. **Markdown to ADF Converter**
- AI generates clean markdown (headers, bullets, checkboxes)
- Custom converter translates to Jira's proprietary format
- Handles formatting: bold, lists, code blocks, checkboxes

## Ticket Types Enhanced

### Security Findings
- **Problem**: What's misconfigured
- **Impact**: Business risk
- **Steps**: Console paths + CLI commands
- **Criteria**: Testable checkboxes
- **Compliance**: SOC 2 mapping

### Drift Detection
- **What Changed**: Configuration delta
- **Impact**: Why drift matters
- **Root Cause**: Likely causes (manual change, failed deploy, etc.)
- **Remediation**: Steps to restore expected state
- **Prevention**: How to avoid recurrence

### Risk Exceptions
- **Summary**: What risk is being accepted
- **Justification**: Business reason
- **Compensating Controls**: What mitigates the risk
- **Risk Assessment**: Residual risk after controls
- **Approval Requirements**: Who needs to sign off
- **Expiration**: When exception needs review

## AI Model Details

**Model**: Claude 3.5 Haiku (via AWS Bedrock)
- **Model ID**: `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- **Cost**: ~$0.25 per 1M input tokens, ~$1.25 per 1M output tokens
- **Latency**: ~1-2 seconds per ticket
- **Temperature**: 0.5 (balanced between consistency and creativity)
- **Max Tokens**: 2048 (allows detailed descriptions)

**Estimated Cost**: $0.001 per Jira ticket (1/10th of a penny)

## Fallback Behavior

If Bedrock API fails or times out:
1. **Graceful Degradation**: Falls back to basic template
2. **Logging**: Error logged to CloudWatch for investigation
3. **No Failure**: Jira ticket still gets created (just less detailed)
4. **User Experience**: No error shown to user, ticket still actionable

Example fallback:
```python
except Exception as e:
    logger.warning(f"Failed to generate AI description, using template: {e}")
    # Use basic template with essential info
    jira_description = {...}  # Simple template
```

## Configuration

### Environment Variables
```bash
# Already configured in Lambda
BEDROCK_MODEL_ID="us.anthropic.claude-haiku-4-5-20251001-v1:0"
BEDROCK_REGION="us-east-1"  # Or your region
```

### IAM Permissions
Lambda role already has Bedrock permissions:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel"
  ],
  "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-*"
}
```

## Testing

### Test AI-Generated Ticket
```bash
# Run evidence collection (will create findings with AI tickets)
/carl evidence collect

# Sync findings to Jira
/carl jira sync
```

### Check Ticket Quality
1. Go to Jira → CARLSEC project
2. Open any ticket created by CARL
3. Verify it has:
   - Clear problem statement
   - Business impact explanation
   - Step-by-step instructions
   - Acceptance criteria checkboxes
   - SOC 2 context

### Compare Before/After
- Before: Generic template, technical jargon, no steps
- After: Clear English, specific paths, actionable steps, testable criteria

## Benefits

**For Engineers:**
- ✅ Don't need to guess what to do
- ✅ Exact console paths and CLI commands
- ✅ Know when they're done (acceptance criteria)
- ✅ Understand the urgency (business impact)

**For Security Team:**
- ✅ Clear tracking of what needs fixing
- ✅ Evidence for auditors (detailed remediation)
- ✅ Consistency across all tickets
- ✅ Professional documentation

**For Auditors:**
- ✅ Clear mapping to SOC 2 controls
- ✅ Evidence of systematic approach
- ✅ Verification that issues were properly addressed
- ✅ Documentation trail

**For Management:**
- ✅ Understand security risks in business terms
- ✅ Track remediation progress
- ✅ Evidence of due diligence
- ✅ Professional compliance program

## Future Enhancements

**Planned:**
1. **Learning from Feedback**: Track which tickets get closed fastest, improve prompts
2. **Custom Templates**: Allow teams to define their own ticket structure
3. **Multi-Language**: Generate tickets in different languages
4. **Severity-Based Detail**: More detail for critical findings, less for low severity
5. **Integration with Runbooks**: Link to internal documentation/runbooks
6. **Auto-Assignment**: AI suggests who should fix based on resource type

## Troubleshooting

### "AI description seems generic"
- Check finding has detailed `description` field
- Verify `resource_type` and `resource_id` are specific
- Consider increasing `temperature` parameter (currently 0.5)

### "Bedrock API timeout"
- Check Lambda timeout (should be ≥ 90 seconds)
- Check Bedrock endpoint health
- Fallback template will be used automatically

### "Jira formatting looks wrong"
- Check `_markdown_to_adf()` converter
- Verify AI is generating proper markdown
- Test with simple ticket first

### "Tickets missing context"
- Ensure all parameters passed to `generate_jira_ticket_description()`
- Check finding has `soc2_controls` populated
- Verify `resource_arn` is complete

## Cost Analysis

**Per Ticket:**
- Input tokens: ~500 tokens (finding details)
- Output tokens: ~1,500 tokens (full description)
- Cost: ~$0.001 per ticket (1/10th of a penny)

**Monthly (100 findings):**
- Total: ~$0.10/month for AI ticket generation
- Bedrock cost: Negligible compared to Lambda/DynamoDB

**ROI:**
- Engineer time saved: ~10 minutes per ticket (understanding + fixing)
- 100 findings × 10 min = 1,000 minutes = 16.7 hours saved
- At $100/hour engineer rate = $1,670 value
- **ROI: 16,700x** (cost $0.10, value $1,670)
