# CARL Continuous Learning System

**Design Principle #4: Continuous Learning & Environment Adaptation**

CARL learns from every interaction to become smarter and more adapted to your specific AWS environment.

---

## Overview

The Continuous Learning System enables CARL to:
- **Remember** what AWS resources you have
- **Learn** which scans are most useful for different questions
- **Adapt** recommendations based on your environment and feedback
- **Improve** automatically over time without code changes

**Cost:** ~$0.67/month (DynamoDB + pattern analysis Lambda)

---

## How It Works

### 1. Interaction Logging

Every `/carl ask` question logs:
- What you asked
- Which scans CARL performed
- What resources were found
- How long it took

```python
# Automatically logged for every /carl ask
interaction_id = learning_service.log_interaction(
    user_id="U123456",
    question="How's my database connectivity?",
    scans_performed=["scan_vpc", "scan_security_hub"],
    resources_found=["vpc-abc123", "sg-xyz789"],
    scan_duration_ms=3500
)
```

### 2. User Feedback

After each answer, you see feedback buttons:

```
Was this answer helpful?
[👍 Yes]  [👎 No]
```

Your feedback teaches CARL:
- **👍 Thumbs Up**: "These scans were useful for this question type"
- **👎 Thumbs Down**: "Try different scans next time"

### 3. Pattern Analysis

Daily at 2am UTC, CARL analyzes all interactions:
- Groups similar questions together
- Identifies which scans got positive feedback
- Tracks frequently checked resources
- Discovers common topics users ask about

### 4. Learned Context

When you ask a question, CARL includes learned context:

```
Agent Instructions:
- You are a scanning agent for AWS compliance...
- Analyze question and decide what to scan...

Learned from past interactions:
• Users frequently ask about: vpc, security, database, connectivity, mfa
• Frequently checked resources: vpc-abc123, sg-xyz789, rds-prod-db
• For similar questions, these scans were most useful: scan_vpc, scan_security_hub
```

This makes the AI smarter with every question you ask!

---

## Data Storage

### Scan History Table (`carl-scan-history`)

Stores every interaction:

```json
{
  "pk": "ACCOUNT#123456789012",
  "sk": "INTERACTION#2026-01-29T10:30:00Z#int_abc123",
  "interaction_id": "int_20260129103000_abc123",
  "user_id": "U123456",
  "question": "How's my database connectivity?",
  "question_hash": "7f8d3c9e...",  // For pattern matching
  "scans_performed": ["scan_vpc", "scan_security_hub"],
  "resources_found": ["vpc-abc123", "sg-xyz789"],
  "scan_duration_ms": 3500,
  "was_useful": true,  // From feedback
  "timestamp": "2026-01-29T10:30:00Z"
}
```

**Indexes:**
- `AccountIndex`: Query by account + timestamp
- `QuestionPatternIndex`: Find similar questions

### Resource Knowledge Graph (`carl-resource-graph`)

Tracks your AWS resources:

```json
{
  "pk": "ACCOUNT#123456789012#RESOURCE#vpc-abc123",
  "sk": "TYPE#VPC",
  "resource_id": "vpc-abc123",
  "resource_type": "VPC",
  "region": "us-east-1",
  "properties": {
    "cidr_block": "10.0.0.0/16",
    "tags": {"Name": "Production VPC"}
  },
  "relationships": {
    "contains": ["sg-xyz789", "subnet-111", "subnet-222"],
    "used_by": ["rds-prod-db", "ec2-web-server"]
  },
  "last_scanned": "2026-01-29T10:30:00Z",
  "scan_count": 15,
  "issues_found": 2
}
```

**Indexes:**
- `ResourceIndex`: Query by resource ID
- `TypeIndex`: Query by resource type

---

## Pattern Analysis

### What Gets Analyzed

**1. Question → Scans Mapping**
- Groups similar questions (using question hash)
- Identifies which scans were most helpful
- Calculates confidence based on positive feedback

Example learned pattern:
```
Question type: "database connectivity"
→ Scans: [scan_vpc, scan_security_hub]
→ Confidence: 85% (17/20 got thumbs up)
→ Sample size: 20 interactions
```

**2. Resource Frequency**
- Tracks which resources are checked most often
- Helps prioritize scanning and caching
- Shows what users care about

Example:
```
Top resources:
1. vpc-abc123 - checked 47 times
2. sg-xyz789 - checked 35 times
3. rds-prod-db - checked 28 times
```

**3. Common Topics**
- Extracts keywords from questions
- Identifies what users ask about most
- Helps anticipate needs

Example:
```
Common topics:
1. "vpc" - 52 mentions
2. "security" - 48 mentions
3. "database" - 39 mentions
4. "connectivity" - 31 mentions
5. "mfa" - 27 mentions
```

### Pattern Analysis Schedule

**Frequency:** Daily at 2am UTC
**Duration:** ~30 seconds
**Cost:** $0/month (within Lambda free tier)

Triggered by EventBridge rule:
```hcl
schedule_expression = "cron(0 2 * * ? *)"
```

Analyzes last 30 days of interactions and logs insights to CloudWatch.

---

## CloudWatch Metrics

Pattern analysis publishes metrics to `CARL/Learning` namespace:

| Metric | Description | Unit |
|--------|-------------|------|
| `PatternsLearned` | Number of question → scan patterns learned | Count |
| `PatternConfidence` | Average confidence of learned patterns | Percent |
| `InteractionsAnalyzed` | Total interactions analyzed | Count |

**Use these metrics to monitor:**
- Is CARL learning effectively?
- Are confidence scores improving over time?
- How much data do we have?

---

## Integration with `/carl ask`

### Before Learning

```python
# Static keyword matching - brittle
if "mfa" in question:
    scan_iam()
elif "vpc" in question:
    scan_vpc()
# ...114 lines of if/else
```

### After Learning

```python
# 1. Initialize learning service
learning_service = LearningService(...)

# 2. Get learned context
learned_context = learning_service.get_learned_context(question)

# 3. Create agent with learned context
agent = Agent(
    tools=scanning_tools,
    instructions=base_instructions + learned_context  # AI gets smarter!
)

# 4. Let AI decide what to scan
scan_results = agent.execute("Analyze and scan relevant resources")

# 5. Log interaction for future learning
interaction_id = learning_service.log_interaction(
    user_id=user_id,
    question=question,
    scans_performed=["scan_vpc", "scan_iam"],
    resources_found=["vpc-123", "user-john"],
    scan_duration_ms=3500
)

# 6. Show feedback buttons
[👍 Yes]  [👎 No]  # User clicks, CARL learns
```

---

## Code Architecture

### Files Created

**1. `learning_service.py` (580 lines)**
- `LearningService` class
- `log_interaction()` - Store scan interaction
- `record_feedback()` - Store user feedback
- `update_resource_graph()` - Track resources
- `analyze_patterns()` - Generate learned insights
- `get_learned_context()` - Context for agent instructions

**2. `pattern_analyzer.py` (200 lines)**
- Lambda handler for daily pattern analysis
- Analyzes last 30 days of data
- Logs insights to CloudWatch
- Publishes learning metrics

**3. `scan_history_table.tf` (130 lines)**
- DynamoDB table for scan history
- DynamoDB table for resource graph
- GSI indexes for efficient queries

**4. `pattern_analyzer_schedule.tf` (180 lines)**
- Lambda function definition
- EventBridge rule (daily at 2am UTC)
- IAM permissions for tables
- CloudWatch log group

### Integration Points

**slack_router.py:**
- `handle_ask_command_fallback()` - Logs interactions and shows feedback buttons
- `handle_learning_feedback()` - Processes thumbs up/down clicks

**scanning_tools.py:**
- Tools track resources found during scans
- Results used to update resource knowledge graph

---

## Benefits

### 1. Smarter Over Time
- Week 1: CARL guesses which scans to run
- Week 4: CARL knows your environment and question patterns
- Week 12: CARL anticipates what you need before you ask

### 2. Environment-Specific
- Generic AI: "You should scan VPC for network questions"
- CARL: "You usually check vpc-abc123, which has 2 known issues in sg-xyz789"

### 3. Adaptive to Your Team
- If your team asks about security groups daily, CARL prioritizes those scans
- If you never ask about GuardDuty, CARL stops checking it unnecessarily

### 4. Reduced AWS API Calls
- Resource graph caches scan results
- Avoids re-scanning recently checked resources
- Saves time and reduces AWS API throttling risk

### 5. Measurable Improvement
- CloudWatch metrics show learning progress
- Confidence scores increase over time
- Feedback rate shows user satisfaction

---

## Privacy & Data Retention

### What's Stored
- Questions you ask (text)
- Scans performed (tool names)
- Resources found (AWS resource IDs)
- Your feedback (thumbs up/down)
- Timestamps

### What's NOT Stored
- Actual scan results (only summaries)
- Resource configurations (only metadata)
- User credentials or secrets
- Data outside your AWS account

### Data Retention
- **Scan history**: 30 days (for pattern analysis)
- **Resource graph**: Indefinite (updated on each scan)
- **Learned patterns**: Recalculated daily from recent data

### Security
- All data encrypted at rest (KMS)
- IAM role-based access only
- No cross-account access
- Data never leaves your AWS account

---

## Cost Breakdown

| Component | Usage | Cost/Month |
|-----------|-------|------------|
| Scan History Table | 3,000 writes/month, 10K reads/month | $0.01 |
| Resource Graph Table | 5MB storage, 1K updates/month | $0.50 |
| Pattern Analyzer Lambda | 30 invocations × 30 seconds | $0.00 (free tier) |
| Bedrock API (pattern extraction) | 10 calls × 5K tokens | $0.15 |
| CloudWatch Metrics | 3 metrics × 30 days | $0.01 |
| **Total** | | **$0.67/month** |

**Comparison:**
- Without learning: CARL asks same questions, makes same mistakes
- With learning: CARL gets smarter, costs <$1/month
- **ROI:** Priceless - your team's time saved learning CARL's quirks

---

## Monitoring

### Check Pattern Analysis Logs

```bash
# View pattern analysis results
aws logs tail /aws/lambda/carl-dev-pattern-analyzer --follow

# Check for patterns learned
aws logs filter-pattern /aws/lambda/carl-dev-pattern-analyzer "Pattern Type"
```

### Query CloudWatch Metrics

```bash
# Get patterns learned over time
aws cloudwatch get-metric-statistics \
  --namespace CARL/Learning \
  --metric-name PatternsLearned \
  --start-time 2026-01-01T00:00:00Z \
  --end-time 2026-01-31T23:59:59Z \
  --period 86400 \
  --statistics Maximum

# Check pattern confidence
aws cloudwatch get-metric-statistics \
  --namespace CARL/Learning \
  --metric-name PatternConfidence \
  --start-time 2026-01-01T00:00:00Z \
  --end-time 2026-01-31T23:59:59Z \
  --period 86400 \
  --statistics Average
```

### Query Scan History

```python
from services.learning_service import LearningService

learning = LearningService(
    scan_history_table="carl-dev-scan-history",
    resource_graph_table="carl-dev-resource-graph"
)

# Analyze recent patterns
patterns = learning.analyze_patterns(days_lookback=7)

# Get learned context
context = learning.get_learned_context("How's my VPC configured?")
print(context)
```

---

## Future Enhancements

### Phase 3: Predictive Intelligence (Planned)
- **Proactive Recommendations**: "You usually ask about VPC after deploying RDS"
- **Trend Detection**: "Your security group checks increased 3x this week"
- **Cost Forecasting**: "Based on scan patterns, costs will increase Friday"

### Phase 4: Self-Healing (Future)
- **Drift Detection**: "vpc-abc123 security rules changed since last scan"
- **Auto-Remediation**: "Applied fix you approved 5 times before"
- **Smart Caching**: "Resource hasn't changed, using cached scan from 2 hours ago"

### Phase 5: Multi-Account Learning (Future)
- Learn patterns across all accounts in your organization
- "Other teams ask about X after deploying Y"
- Aggregate best practices from your entire company

---

## Troubleshooting

### Feedback Buttons Not Appearing

**Check:**
1. Is `SCAN_HISTORY_TABLE` environment variable set?
2. Does Lambda have permissions to write to scan history table?
3. Check CloudWatch logs for errors in `log_interaction()`

### Pattern Analysis Not Running

**Check:**
1. EventBridge rule enabled?
   ```bash
   aws events describe-rule --name carl-dev-pattern-analysis
   ```
2. Lambda has permissions?
3. Check CloudWatch logs: `/aws/lambda/carl-dev-pattern-analyzer`

### No Patterns Being Learned

**Possible causes:**
- Not enough data yet (need at least 10 interactions)
- No feedback provided (thumbs up/down needed for confidence scoring)
- Pattern analysis Lambda not running daily

**Fix:**
- Use CARL more (ask 10-20 questions)
- Provide feedback on answers
- Manually invoke pattern analyzer:
  ```bash
  aws lambda invoke --function-name carl-dev-pattern-analyzer output.json
  ```

---

## Summary

**What You Get:**
- AI that learns your environment and improves automatically
- Smarter scan decisions with every question
- Resource knowledge graph of your AWS infrastructure
- Measurable improvement via CloudWatch metrics
- All for ~$0.67/month

**What You Give:**
- Click thumbs up/down occasionally
- Let CARL remember your questions and resources
- Trust the AI to get smarter over time

**The Promise:**
CARL learns continuously, adapts to your specific environment, and becomes more valuable the more you use it - without requiring any code changes or manual configuration.

**Welcome to truly intelligent AWS compliance assistance!** 🧠
