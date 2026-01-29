# CARL Core Design Principles

## The Fundamental Rule: ALWAYS USE LIVE AWS DATA

**CARL's entire value proposition:** It sits IN your AWS environment with credentials and live access.

**Without this, CARL is just generic AI advice** - which users can get from ChatGPT for free.

---

## Design Principle: Environment-First Architecture

Every CARL command should:
1. **Scan first, answer second** - Query AWS APIs before responding
2. **Use actual resource names** - "Your S3 bucket 'prod-data' is not encrypted" not "S3 buckets should be encrypted"
3. **Provide contextual recommendations** - Based on what YOU have, not generic best practices
4. **Know your current state** - Don't recommend what you already have

---

## Command-by-Command Requirements

### ✅ DOING IT RIGHT

**`/carl evidence collect`**
- Scans IAM, S3, VPC, CloudTrail, Security Hub
- Uses actual resource data
- Creates findings with real resource IDs

**`/carl ask` (FIXED)**
- Analyzes question
- Scans relevant AWS services
- Answers with YOUR actual data (usernames, bucket names, etc.)

### ❌ NEEDS FIXING

**`/carl status`**
- Currently: Shows stored findings from database
- Should: Run live scan, show current state
- Fix: Add live scanning before showing status

**`/carl architect <question>`**
- Currently: Generic architecture advice
- Should: Scan your VPCs, subnets, resources first
- Should: "You have 2 VPCs in us-east-1 with X subnets, here's how to add egress..."
- Fix: Scan network topology before recommending

**`/carl recommend <requirement>`**
- Currently: Generic recommendations
- Should: Analyze current infrastructure first
- Should: "You're using t3.medium instances, here's why t3.large would be better for YOUR workload"
- Fix: Scan compute/network resources before recommending

**`/carl foundation start`**
- Currently: Asks questions, generates code
- Should: Detect existing resources (VPCs, subnets, CloudTrail, etc.)
- Should: "I see you have CloudTrail enabled already, skipping..."
- Fix: Use resource_detector.py before generating code

**`/carl findings`**
- Currently: Shows stored findings
- Should: Run live scan and compare to stored findings
- Should: "You have 3 stored findings, but live scan shows 5 - 2 are new"
- Fix: Optional live scan parameter

---

## Implementation Pattern

Every command should follow this pattern:

```python
def handle_command(slack, channel_id, user_id, args):
    # 1. Post "Scanning your environment..." message
    slack.post_message(channel_id, text="🔍 Scanning your AWS environment...")

    # 2. Scan relevant AWS resources
    evidence_collector = EvidenceCollector()
    live_data = evidence_collector.collect_relevant_evidence(args)

    # 3. Use AI with live data context
    bedrock = BedrockService()
    response = bedrock.generate_response(
        question=args,
        live_environment_data=live_data  # ACTUAL AWS data
    )

    # 4. Post response with specific resource names
    slack.post_message(channel_id, text=response)
```

---

## Why This Matters

**Without live data:**
- User: "Do I have MFA enabled?"
- CARL: "You should enable MFA for all users"
- User: "That's useless, ChatGPT could tell me that"

**With live data:**
- User: "Do I have MFA enabled?"
- CARL: "2 of 3 users have MFA. User 'john@company.com' needs MFA enabled."
- User: "NOW THAT'S HELPFUL"

---

## Red Flags in Code

If you see:
- ❌ Generic recommendations without resource names
- ❌ "You should..." without "You currently have..."
- ❌ Responding from stored data without scanning
- ❌ Architecture advice without seeing actual infrastructure

**Then it's broken** - it's not using CARL's core advantage.

---

## The Test

Before deploying any feature, ask:
> "Could the user get this same answer from ChatGPT?"

If YES → Feature is broken, needs live AWS integration
If NO → Feature is using CARL's advantage correctly

---

## Priority Fixes (In Order)

1. `/carl status` - Add live scan
2. `/carl architect` - Scan network topology first
3. `/carl recommend` - Scan infrastructure first
4. `/carl foundation start` - Detect existing resources
5. `/carl findings` - Add live scan option

**The goal:** Make every command impossible to replicate without AWS credentials.
