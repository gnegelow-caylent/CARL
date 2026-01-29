# CARL Core Design Principles

## The Fundamental Rule: ALWAYS USE LIVE AWS DATA

**CARL's entire value proposition:** It runs as a Lambda function IN your AWS environment with IAM role-based access to AWS APIs.

**Without this, CARL is just generic AI advice** - which users can get from ChatGPT for free.

### How CARL Gets AWS Access
- CARL runs as an AWS Lambda function
- Lambda execution role grants specific IAM permissions (read-only for scanning)
- No credentials stored - uses AWS IAM roles and policies
- Can call AWS APIs (IAM, S3, EC2, VPC, CloudTrail, etc.) through boto3
- Permissions defined in Terraform IAM policies

---

## Design Principle #1: Environment-First Architecture

Every CARL command should:
1. **Scan first, answer second** - Query AWS APIs before responding
2. **Use actual resource names** - "Your S3 bucket 'prod-data' is not encrypted" not "S3 buckets should be encrypted"
3. **Provide contextual recommendations** - Based on what YOU have, not generic best practices
4. **Know your current state** - Don't recommend what you already have

---

## Design Principle #2: Compliance-Native Intelligence

**CARL's second core value:** Deep understanding of compliance frameworks paired with environment access.

**Without this, CARL is just an AWS scanner** - which CloudFormation Guard or AWS Config could do.

### What Makes CARL Different

**Generic scanner:**
- "Your S3 bucket is not encrypted"
- "Enable MFA on IAM users"

**CARL (Compliance-Native):**
- "Your S3 bucket 'prod-data' is not encrypted, violating **SOC 2 CC6.7** (Logical and Physical Access Controls)"
- "This affects your **Data Confidentiality** trust service criteria"
- "IAM user 'john@company.com' lacks MFA, non-compliant with **SOC 2 CC6.1** (Logical Access Controls)"
- "This creates an auditor finding in the **Access Control** section of your audit report"

### Deep Compliance Knowledge Required

CARL must understand:

**1. SOC 2 Trust Service Criteria (Current Focus)**
- **CC6.1** - Logical access controls (MFA, password policies)
- **CC6.6** - Encryption at rest (S3, RDS, EBS)
- **CC6.7** - Encryption in transit (TLS, HTTPS)
- **CC7.2** - System monitoring (CloudTrail, CloudWatch)
- **CC8.1** - Change management (Infrastructure as Code)
- And 38 other SOC 2 controls

**2. What Controls Mean in AWS Terms**
- CC6.1 → IAM password policies, MFA enforcement, access keys rotation
- CC6.6 → S3 bucket encryption, RDS encryption, EBS encryption
- CC7.2 → CloudTrail enabled, VPC Flow Logs, CloudWatch alarms
- A1.2 → Multi-AZ deployments, backup plans, disaster recovery

**3. How to Implement Controls**
- Not just "enable encryption"
- Specific: "aws s3api put-bucket-encryption --bucket prod-data --server-side-encryption-configuration..."
- Terraform code for the fix
- Step-by-step remediation plan

**4. Audit Evidence Requirements**
- What auditors will ask for
- How to collect and present evidence
- How to document exceptions and compensating controls

### Compliance-Environment Pairing

Every finding should map:
```
[AWS Resource] → [Issue] → [SOC 2 Control] → [Remediation] → [Evidence]

Example:
S3 bucket "prod-data"
  → Not encrypted
  → Violates CC6.6 (Encryption at Rest)
  → Enable AES-256 encryption (here's the Terraform code)
  → Store encryption config as evidence for auditors
```

### Multi-Framework Support (Roadmap)

**Phase 1: SOC 2 (Current)**
- Full SOC 2 Type II control mapping
- Evidence collection automation
- Gap analysis and remediation plans

**Phase 2: Expand to Other Frameworks**
- **HIPAA** - Health data compliance
- **PCI-DSS** - Payment card data security
- **ISO 27001** - Information security management
- **FedRAMP** - Federal government requirements
- **GDPR** - EU data protection

**Cross-Framework Intelligence:**
- "This S3 encryption issue violates:"
  - SOC 2 CC6.6
  - HIPAA 164.312(a)(2)(iv)
  - PCI-DSS 3.4
  - ISO 27001 A.10.1.1
- Fix once, satisfy multiple compliance requirements

### Why This Matters

**Without compliance knowledge:**
- "You have 15 security issues"
- User: "Which ones matter for my SOC 2 audit?"
- CARL: "¯\_(ツ)_/¯"

**With compliance knowledge:**
- "You have 15 security issues:"
- "7 are SOC 2 blockers (won't pass audit)"
- "5 are high priority (auditor will mention)"
- "3 are best practices (nice to have)"
- "Fix these 7 first to pass your audit"

### Implementation in Code

Every finding must include:
```python
Finding(
    id="finding-abc123",
    title="S3 Bucket Not Encrypted",
    resource_id="arn:aws:s3:::prod-data",
    severity="HIGH",
    control_ids=["CC6.6", "A1.2"],  # SOC 2 controls affected
    control_names=[
        "Encryption at Rest",
        "Availability Criteria"
    ],
    compliance_frameworks=["SOC2"],  # Future: ["SOC2", "HIPAA", "PCI-DSS"]
    audit_impact="HIGH",  # Will this cause audit failure?
    remediation_steps="...",  # Specific AWS actions
    terraform_fix="...",  # Infrastructure as code
    evidence_required="...",  # What auditors need
)
```

### The Test

Before deploying any compliance feature, ask:
> "Does this help the user pass their SOC 2 audit?"

If YES → Feature provides compliance value
If NO → Feature is just security scanning (not enough)

---

## Design Principle #3: Cost-Aware Recommendations

**CARL's third core value:** Always factor cost into architecture decisions using real AWS pricing data.

**Without this, CARL gives incomplete advice** - users need to know what things cost to make informed decisions.

### Why Cost Matters

**Generic architecture advice:**
- "Use AWS Glue for your ETL" (no cost context)
- "Deploy a NAT Gateway" (ignores $32/month cost)
- "Add VPC endpoints" (doesn't mention break-even analysis)

**CARL (Cost-Aware):**
- "AWS Glue: $0.44/DPU-hour, estimate $150/month for your 10GB/day workload"
- "NAT Gateway costs $32/month + $0.045/GB. For your 50GB/month egress, that's ~$34/month total"
- "VPC endpoints: $7.20/month each. Break-even vs NAT Gateway at 160GB egress/month"

### CARL Has Real-Time Pricing Data

**Available via `pricing_tool.py` (Real-Time AWS Price List API):**
- Uses AWS Price List API for current, accurate pricing
- Supports all major services: EC2, RDS, S3, Glue, DMS, Lambda, DynamoDB, Redshift, EMR, Kinesis, VPC, ELB
- Pricing is queried on-demand - always current, never stale
- Region-aware pricing (us-east-1, us-west-2, eu-west-1, etc.)
- Instance-specific pricing (t3.medium, db.t3.large, etc.)

**How Agents Use It:**
```python
from services.pricing_tool import pricing_tool

# Register tool with any agent
agent.add_tool(pricing_tool)

# Agent autonomously calls pricing_tool when answering cost questions
# Agent: "What's the cost of t3.medium?"
# → Calls get_aws_pricing(service_name="ec2", instance_type="t3.medium")
# → Returns real-time price: $0.0416/hour = $30/month
```

**Fallback Static Data (`aws_pricing.py`):**
- 879 lines of comprehensive static pricing (as of 2024)
- Used for patterns and documentation
- Should be updated periodically, but real-time API is preferred

### Cost-Aware Recommendation Pattern

Every recommendation with multiple options should include:

```
Option 1: AWS Glue (Serverless ETL)
• Best for: Minimal ops overhead, auto-scaling
• Cost: ~$150-300/month (10-20 DPUs x 8 hours/day)
• SOC 2: CC7.2 (CloudWatch logging)

Option 2: AWS DMS (Database Migration Service)
• Best for: Continuous replication, real-time sync
• Cost: ~$200/month (t3.medium replication instance 24/7)
• SOC 2: CC6.7 (Encrypted replication)

Option 3: Self-Managed on EC2
• Best for: Custom logic, existing tools
• Cost: ~$35-100/month (t3.medium-large 24/7) + ops time
• SOC 2: CC6.1 (SSH access control required)

💰 Recommended: AWS Glue - Best value for typical workloads
   (Serverless = pay only when running, no ops overhead)
```

### The Cost Test

Before giving any architecture recommendation, ask:
> "Did I include actual costs and explain the value tradeoff?"

If NO → Add pricing data and cost comparison
If YES → Recommendation is complete ✓

### Examples

❌ **Bad:** Cost not mentioned
```
Use AWS Glue for your ETL pipeline. It's serverless and scales automatically.
```

⚠️ **Half-Good:** Generic cost range, no comparison
```
Use AWS Glue ($150-300/month) for your ETL pipeline.
```

✅ **Excellent:** Specific cost + comparison + value explanation
```
AWS Glue: ~$220/month for your 10GB/day workload (20 DPUs x 8 hrs x 30 days x $0.44/DPU-hour)
vs Self-managed EC2: ~$50/month for t3.large + 20 hours/month ops time (~$330 total value)

Glue saves $110/month in ops time and scales automatically. Recommended.
```

### Key Principles

1. **Always show cost** - Include actual monthly cost estimates
2. **Compare options** - "Option A costs X, Option B costs Y, here's why A is better value"
3. **Factor ops overhead** - "$50/month EC2" is misleading if it requires 10 hours/month to manage
4. **Use real pricing data** - Never guess, always use aws_pricing.py
5. **Explain value** - "Costs more but saves 20 hours/month" or "Costs less, same functionality"
6. **Show break-even points** - "VPC endpoints break even vs NAT at 160GB/month"
7. **Recommend best value** - Not cheapest, not most expensive, but best return on investment

### Cost + Compliance Together

Best recommendations combine all three principles:

```
💡 Recommended: AWS Glue + VPC Endpoints

Environment Context:
• Your VPC: vpc-abc123 with 3 private subnets
• No NAT Gateway deployed (would cost $32/month + egress)

Cost Analysis:
• Glue: ~$220/month (based on 10GB/day)
• VPC Endpoints (Glue + S3): $14.40/month (2 endpoints x $7.20)
• Total: ~$234/month
• vs EC2 + NAT: ~$380/month (EC2 $50 + NAT $32 + egress $298)
• Savings: $146/month

SOC 2 Compliance:
• CC6.7: Traffic stays on AWS backbone (VPC endpoints)
• CC7.2: CloudWatch logging enabled automatically
• CC6.1: IAM roles, no credentials in code

💰 Best value: Fully managed + compliant + $146/month cheaper
```

---

## Design Principle #4: Continuous Learning & Environment Adaptation

**CARL's fourth core value:** AI that learns your environment and adapts to your usage patterns.

**Without this, CARL is just a static tool** - users need intelligence that improves with every interaction.

### Why Continuous Learning Matters

**Static Rule-Based Approach:**
- "If question contains 'MFA', scan IAM" (rigid keyword matching)
- "If question contains 'bucket', scan S3" (brittle pattern matching)
- Requires 114+ lines of hardcoded if/else statements
- Can't handle new AWS services without code changes
- Doesn't learn from user behavior

**CARL (Adaptive Intelligence):**
- AI analyzes question semantics: "Do I have MFA enabled?" → understands this needs IAM scan
- AI recognizes context: "How's my database connectivity?" → understands this needs VPC + RDS scan
- AI learns patterns: User frequently asks about security groups → prioritizes network scans
- AI adapts to new services: AWS releases new service → AI can scan it without code changes

### How CARL Learns Your Environment

**1. Intelligent Scanning Decisions**
- Agent analyzes user questions using natural language understanding
- Agent decides which AWS resources to scan based on context
- No hardcoded keywords - AI reasons about what's needed

**Before (Static Keywords - 114 lines):**
```python
if any(kw in question for kw in ['mfa', 'multi-factor', 'iam user', 'password', ...]):
    scan_iam()
if any(kw in question for kw in ['vpc', 'network', 'security group', 'firewall', ...]):
    scan_vpc()
# ...100+ more lines
```

**After (AI-Driven - Scalable):**
```python
agent = Agent(tools=[scan_iam, scan_s3, scan_vpc, scan_cloudtrail, ...])
agent.execute("Analyze question and scan relevant AWS resources")
# AI decides what to scan based on question semantics
```

**2. Context Awareness**
- AI remembers what resources exist in your environment
- AI understands relationships: "database connectivity" requires both VPC and database scans
- AI prioritizes based on what you have: If no RDS, doesn't waste time scanning RDS

**3. Adaptive Recommendations**
- The more CARL scans your environment, the better it understands your architecture
- Recommendations become more specific: "Your t3.medium instances in vpc-abc123..."
- Cost estimates become more accurate: "Based on your typical usage pattern..."

**4. Learning from Patterns**
- User asks about security groups frequently → CARL proactively includes network security
- User never asks about GuardDuty → CARL doesn't include it unless relevant
- User's environment is multi-region → CARL automatically considers cross-region factors

### Benefits of AI-Driven Scanning

**Scalability:**
- Static keywords: Need to update code for every AWS service (200+ services)
- AI-driven: AI can reason about any AWS service without code changes

**Flexibility:**
- Static keywords: "web server" must be explicitly mapped to VPC scan
- AI-driven: AI understands "I need a database for my app" requires VPC + RDS + security groups

**Maintainability:**
- Static keywords: 114 lines of if/else statements to maintain
- AI-driven: 6 tool definitions, AI handles the decision logic

**Intelligence:**
- Static keywords: Can only match exact phrases
- AI-driven: Understands synonyms, context, and intent

### Implementation: Agent-Based Scanning

**Created `scanning_tools.py` (340 lines):**
- Wraps EvidenceCollector scanning functions as AgentCore Tools
- 6 intelligent tools: scan_iam, scan_s3, scan_vpc, scan_cloudtrail, scan_security_hub, scan_all
- Each tool has rich descriptions that help AI decide when to use it

**Refactored `/carl ask` command:**
- Removed 114 lines of static keyword matching
- Now uses Agent with scanning tools
- AI analyzes question → decides what to scan → scans → answers with context

**Example:**
```
User: "How's my database connectivity configured?"

AI Agent reasoning:
1. "Database connectivity" involves network configuration
2. Need to check VPC, security groups, subnets
3. Should call scan_vpc tool
4. [Calls scan_vpc]
5. Receives: "vpc-abc123 has 3 security groups, 2 allow 0.0.0.0/0..."
6. Answers: "Your VPC vpc-abc123 has database connectivity configured through..."
```

### Future Enhancements

**Phase 1: Intelligent Scanning (Current - ✅ Complete)**
- AI-driven scan decisions via AgentCore
- Natural language understanding of questions
- Dynamic tool selection

**Phase 2: Memory & Context (Planned)**
- Remember previous scans to avoid redundant AWS API calls
- Build knowledge graph of your environment
- Understand resource relationships: "This RDS instance is in VPC X with security group Y"

**Phase 3: Predictive Intelligence (Future)**
- "You usually ask about VPC after deploying RDS - here's your network config"
- "Based on your scan history, these 3 resources might need attention"
- "Your EC2 instances typically scale up on Fridays - cost will increase"

**Phase 4: Self-Healing (Future)**
- Detect when resources drift from compliant state
- Automatically propose remediation based on past fixes
- Learn which remediations you typically approve vs reject

### The Continuous Learning Test

Before implementing any feature, ask:
> "Will this get smarter the more the user interacts with CARL?"

If YES → Feature uses continuous learning ✓
If NO → Consider how to make it adaptive

### Examples

❌ **Bad:** Static, never improves
```python
if "mfa" in question:
    scan_iam()
# Always the same logic, forever
```

✅ **Good:** Adaptive, learns context
```python
agent.execute("Analyze this question and scan relevant resources")
# AI decides what to scan, can handle new question patterns
# No code changes needed for new AWS services or question formats
```

### Key Principles

1. **AI makes decisions** - Not hardcoded rules, AI reasoning
2. **Learn from interactions** - Environment understanding improves over time
3. **Adapt to patterns** - Recognize what users care about
4. **Scalable intelligence** - No code changes for new services/questions
5. **Context-aware** - Understand relationships between resources
6. **Proactive** - Anticipate needs based on patterns

### Why This Matters

**Static tool:** Same answers forever, requires constant code updates
**Adaptive AI:** Gets smarter with every scan, adapts to your environment

This is the key difference between a tool and an intelligent assistant.

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

## The Combined Value Proposition

CARL = **Live AWS Environment Access** + **Deep Compliance Knowledge**

### Two Tests for Every Feature

**Test #1: Environment Access**
> "Could the user get this answer from ChatGPT?"

- If YES → Feature is broken, needs live AWS integration
- If NO → Feature is using CARL's environment advantage ✓

**Test #2: Compliance Intelligence**
> "Does this help the user pass their SOC 2 audit?"

- If YES → Feature provides compliance value ✓
- If NO → Feature is just security scanning (not enough)

**Both must pass** for a feature to deliver CARL's full value.

### Examples

❌ **Bad:** Generic advice without environment data or compliance context
- "You should enable MFA" (no environment scan, no SOC 2 mapping)

⚠️ **Half-Good:** Environment data but no compliance context
- "User john@company.com doesn't have MFA" (has environment data, but missing why it matters for SOC 2)

⚠️ **Half-Good:** Compliance advice but no environment data
- "SOC 2 CC6.1 requires MFA" (knows SOC 2, but doesn't know if YOUR users have MFA)

✅ **Excellent:** Environment data + Compliance intelligence
- "User john@company.com doesn't have MFA, violating SOC 2 CC6.1 (Logical Access Controls). This is an audit blocker. Fix: aws iam enable-mfa-device --user-name john@company.com..."

---

## Priority Fixes (In Order)

### Environment Access Fixes
1. **`/carl status`** - Add live scan + SOC 2 control mapping
2. **`/carl architect`** - Scan network topology first + map to compliance requirements
3. **`/carl recommend`** - Scan infrastructure first + compliance impact analysis
4. **`/carl foundation start`** - Detect existing resources + compliance coverage check
5. **`/carl findings`** - Add live scan option + always show SOC 2 control IDs

### Compliance Intelligence Enhancements
1. **Findings → SOC 2 mapping** - Every finding must show which controls it violates
2. **Audit impact scoring** - "This will fail your audit" vs "auditor will mention" vs "nice to have"
3. **Evidence automation** - Auto-collect evidence for each SOC 2 control
4. **Gap analysis** - "You're 78% compliant with SOC 2, here are the 12 gaps"
5. **Multi-framework roadmap** - Add HIPAA, PCI-DSS, ISO 27001 mappings

### The Goal
Make every command impossible to replicate without:
1. AWS IAM access (Lambda execution role) - *for environment data*
2. Deep SOC 2 compliance knowledge - *for audit-ready guidance*

**Together, these make CARL uniquely valuable.**
