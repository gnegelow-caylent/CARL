# Compliance Agent - Autonomous SOC 2 Assessment

**Status:** ✅ Code Complete | ⚙️ Requires AWS Bedrock Agent Configuration

The Compliance Agent provides end-to-end autonomous compliance management using AWS Bedrock Agents.

---

## What It Does

Runs complete SOC 2 compliance assessment with a single command:

```
/carl compliance assess
```

The agent autonomously:
1. **Scans AWS environment** - Smart prioritization (~150 resources)
2. **Detects patterns** - Identifies root causes, not symptoms
3. **Analyzes SOC 2 controls** - Maps to 43 controls, calculates coverage
4. **Generates remediation plan** - 4-phase plan with dependencies
5. **Creates Jira epic + stories** - Automated ticket creation
6. **Posts results to Slack** - Executive summary with roadmap

---

## Example Output

```
📊 SOC 2 Compliance Assessment Complete

Coverage: 53%
Gaps: 20

Current Status:
• Controls Met: 23/43 (53%)
• Critical Gaps: 5
• High Priority: 8
• Medium Priority: 7

🎯 Recommended Phases:

Phase 1 (This Week - CRITICAL):
  ☐ Enable CloudTrail in all regions (CARLSEC-100)
  ☐ Fix root account MFA (CARLSEC-101)
  ☐ Set password policy (CARLSEC-102)
  → Unlocks 11 other controls

Phase 2 (Week 2-3 - HIGH):
  ☐ Enable AWS Config (CARLSEC-103)
  ☐ Fix S3 encryption (8 buckets) (CARLSEC-104-111)
  → Covers 8 additional controls

Phase 3 (Week 3-4 - MEDIUM):
  ☐ IAM access key rotation (CARLSEC-112-118)
  ☐ Security group hardening (CARLSEC-119-123)
  → Covers 6 additional controls

Phase 4 (Week 4-6 - FINAL):
  ☐ Enable VPC flow logs (CARLSEC-124-127)
  ☐ Documentation updates (CARLSEC-128-137)
  → Achieves 100% coverage

📋 Jira Epic: CARLSEC-EPIC-1
    37 stories created and prioritized

⏱️ Estimated Timeline: 4-6 weeks
💰 Estimated Cost: ~$200/month in AWS services

Ready to start? Begin with Phase 1.
```

---

## Configuration (Required Before Use)

The Compliance Agent uses **AWS Bedrock Agents** for autonomous multi-step reasoning.
You must configure this before the agent will work.

### Step 1: Create Bedrock Agent

**Via AWS Console:**

1. Go to **AWS Bedrock** → **Agents**
2. Click **Create Agent**
3. Configure:
   - **Name:** `carl-compliance-agent`
   - **Description:** `Autonomous SOC 2 compliance assessment and remediation planning`
   - **Model:** Claude 3.5 Sonnet
   - **IAM Role:** Create new or use existing (needs Lambda invoke permissions)

4. Add **Agent Instructions:**
   ```
   You are a compliance assessment agent for AWS environments.
   Your goal is to assess SOC 2 compliance readiness by:
   1. Intelligently scanning AWS resources
   2. Detecting patterns and root causes
   3. Mapping findings to SOC 2 controls
   4. Generating phased remediation plans
   5. Creating Jira tickets for tracking

   Be thorough but efficient. Prioritize production resources.
   Look for systemic issues, not just individual problems.
   Consider dependencies when planning remediation.
   ```

5. Add **Action Groups** (Tools):

**Action Group: ComplianceTools**
- **Lambda Function:** `carl-dev-api` (CARL's existing Lambda)
- **OpenAPI Schema:** (See below)

6. **Create Alias:**
   - Name: `PROD`
   - Description: `Production alias`

7. **Prepare Agent** (this builds the agent)

8. **Note the Agent ID** (e.g., `AGENT123456`)

### Step 2: OpenAPI Schema for Action Group

Create this schema for the Bedrock Agent to know what tools are available:

```yaml
openapi: 3.0.0
info:
  title: CARL Compliance Agent Tools
  version: 1.0.0
  description: Tools for compliance assessment and remediation

paths:
  /tools/scan-environment:
    post:
      summary: Scan AWS environment intelligently
      operationId: scanEnvironment
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                prioritize_production:
                  type: boolean
                  description: Focus on production resources first
                sample_dev:
                  type: boolean
                  description: Sample dev resources (don't scan all)
                max_resources:
                  type: integer
                  description: Maximum resources to scan deeply
      responses:
        '200':
          description: Scan results
          content:
            application/json:
              schema:
                type: object

  /tools/detect-patterns:
    post:
      summary: Detect patterns and root causes in evidence
      operationId: detectPatterns
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                evidence:
                  type: object
                  description: Evidence data from scan
      responses:
        '200':
          description: Detected patterns

  /tools/analyze-soc2:
    post:
      summary: Analyze SOC 2 control coverage
      operationId: analyzeSoc2Controls
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                evidence:
                  type: object
                patterns:
                  type: array
      responses:
        '200':
          description: Control coverage analysis

  /tools/generate-plan:
    post:
      summary: Generate phased remediation plan
      operationId: generateRemediationPlan
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                gaps:
                  type: array
                patterns:
                  type: array
      responses:
        '200':
          description: Remediation plan

  /tools/create-jira-epic:
    post:
      summary: Create Jira epic with stories
      operationId: createJiraEpic
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                remediation_plan:
                  type: object
                coverage_percent:
                  type: integer
      responses:
        '200':
          description: Epic and stories created
```

### Step 3: Update Lambda Function

Update CARL Lambda with Bedrock Agent ID:

**Environment Variable:**
```bash
COMPLIANCE_AGENT_ID=<agent-id-from-step-1>
```

**IAM Permissions** (Lambda execution role needs):
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeAgent",
    "bedrock:GetAgent"
  ],
  "Resource": "arn:aws:bedrock:us-east-1:*:agent/*"
}
```

### Step 4: Test

Run in Slack:
```
/carl compliance assess
```

You should see:
- Immediate "Starting assessment..." message
- 3-5 minutes later: Complete assessment results
- Jira epic created with stories

---

## Commands

### `/carl compliance assess`
Run complete autonomous SOC 2 assessment.

**What it does:**
- Scans AWS environment (3-5 minutes)
- Analyzes compliance gaps
- Generates remediation plan
- Creates Jira epic + stories
- Posts results to Slack

**When to use:** Monthly or quarterly compliance reviews

### `/carl compliance status`
Quick compliance status check.

**What it does:**
- Shows current findings count
- Estimates coverage based on findings
- Suggests running full assessment

**When to use:** Quick check between assessments

---

## Cost Analysis

### Per Assessment
- Agent orchestration: $0.002
- Tool calls (6-10): $0.01-0.02
- AI analysis: $0.03-0.05
- **Total:** ~$0.05-0.10 per assessment

### Monthly (20 assessments)
- **Total:** ~$1-2/month

### ROI
- Engineer time saved: 20 hours/month
- At $100/hour: $2,000/month value
- Cost: $2/month
- **ROI: 1,000x**

---

## How It Works (Technical)

### 1. Intelligent Scanning

Instead of checking every resource blindly:

```python
# Traditional approach (slow, inefficient)
for bucket in s3.list_buckets():  # All 200 buckets
    check_encryption(bucket)

# Agent approach (smart, efficient)
production_buckets = [b for b in buckets if b.tags['Environment'] == 'prod']
dev_sample = random.sample(dev_buckets, k=int(len(dev_buckets) * 0.2))
check_resources(production_buckets + dev_sample)  # ~50 buckets
```

**Result:** 10x faster, focuses on what matters

### 2. Pattern Detection

Agent looks for systemic issues:

```
Found: 20 S3 buckets missing encryption

Traditional: Create 20 individual tickets
Agent: Investigates → finds all created by Jenkins pipeline
       Creates 1 ticket: "Fix Jenkins S3 module"
       → Fixes 20 buckets + prevents future issues
```

### 3. Dependency Analysis

Agent understands dependencies:

```
Phase 1: Enable CloudTrail (required for AWS Config)
Phase 2: Enable AWS Config (now CloudTrail exists)
Phase 3: Fix individual resources (Config provides visibility)
```

### 4. Jira Epic Structure

```
CARLSEC-EPIC-1: SOC 2 Compliance Readiness
├── CARLSEC-100: Enable CloudTrail (Phase 1)
├── CARLSEC-101: Fix root account MFA (Phase 1)
├── CARLSEC-102: Set password policy (Phase 1)
├── CARLSEC-103: Enable AWS Config (Phase 2)
├── CARLSEC-104: Fix S3 bucket encryption - bucket-1 (Phase 2)
├── CARLSEC-105: Fix S3 bucket encryption - bucket-2 (Phase 2)
...
└── CARLSEC-137: Update compliance documentation (Phase 4)
```

---

## Troubleshooting

### "Compliance agent not yet configured"

**Problem:** Agent ID not set in environment variable

**Solution:**
1. Complete Step 1-3 above (configure Bedrock Agent)
2. Set `COMPLIANCE_AGENT_ID` environment variable
3. Redeploy Lambda

### "Agent invocation failed"

**Problem:** IAM permissions missing

**Solution:**
Add Bedrock permissions to Lambda execution role:
```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeAgent"],
  "Resource": "*"
}
```

### "Tool call failed: Lambda timeout"

**Problem:** Tool Lambda function timing out

**Solution:**
- Increase Lambda timeout to 90 seconds
- Check tool implementation for inefficiencies
- Review CloudWatch logs for errors

### "No Jira epic created"

**Problem:** Jira credentials or permissions issue

**Solution:**
1. Test Jira connection: `/carl jira test`
2. Verify project key exists (CARLSEC)
3. Check Jira user has permission to create epics

---

## Limitations

### What It DOES Do
- ✅ Scans AWS environment (read-only)
- ✅ Analyzes compliance gaps
- ✅ Generates remediation plans
- ✅ Creates Jira tickets
- ✅ Tracks progress

### What It DOES NOT Do
- ❌ Apply fixes automatically (human approval required)
- ❌ Make changes to AWS resources
- ❌ Delete or modify existing resources
- ❌ Deploy infrastructure
- ❌ Access production data

**All changes require human review and approval.**

---

## Future Enhancements

Planned features:
1. **Multi-framework support** - HIPAA, PCI-DSS, ISO 27001
2. **Custom control mapping** - Define your own controls
3. **Automated fix generation** - Generate Terraform to fix issues
4. **Progress tracking** - Weekly status updates
5. **Trend analysis** - Coverage over time, improvement rate
6. **Cost optimization** - Identify unused resources during scan

---

## Support

- **Documentation:** This file + `AI_OPPORTUNITIES.md`
- **Code:** `carl-app/src/services/compliance_agent.py`
- **Slack:** `/carl help`
- **Issues:** GitHub Issues

---

## Credits

Built using:
- **AWS Bedrock Agents** - Autonomous reasoning
- **Claude 3.5 Sonnet** - Natural language understanding
- **CARL Infrastructure** - Evidence collection, findings management
- **Jira Cloud API** - Ticket management

**Estimated Development:** 2 weeks
**Lines of Code:** ~1,000
**Cost:** ~$2/month
**Value:** $2,000/month in engineer time saved
**ROI:** 1,000x
