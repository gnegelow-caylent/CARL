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
