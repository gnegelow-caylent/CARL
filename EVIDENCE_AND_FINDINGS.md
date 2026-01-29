# Evidence Collection & Findings Pipeline

## Overview

CARL automates the collection of audit evidence and detection of security findings, then syncs them to Jira for remediation tracking.

## Complete Pipeline Flow

```
/carl evidence collect
    ↓
Scan AWS resources (IAM, S3, Security Groups, etc.)
    ↓
Store raw evidence in DynamoDB (EVIDENCE table)
    ↓
Analyze evidence for security issues
    ↓
Create Finding objects (stable IDs)
    ↓
Store findings in DynamoDB (FINDINGS table)
    ↓
/carl jira sync
    ↓
Check for existing Jira tickets (duplicate prevention)
    ↓
Create Jira tickets for new findings
    ↓
Update findings with jira_ticket_id
    ↓
Post results to Slack
```

## Evidence Collection

### What Gets Collected

**IAM Evidence:**
- Password policy (length, complexity, rotation, etc.)
- User MFA status
- Root account MFA status
- Access key rotation
- User permissions audit

**S3 Evidence:**
- Bucket encryption status
- Versioning enabled/disabled
- Public access configuration
- Logging enabled/disabled
- Bucket policies

**Network Evidence:**
- Security groups (ingress/egress rules)
- VPC flow logs
- Network ACLs
- Internet gateways

**Security Services:**
- Security Hub enabled/disabled
- GuardDuty enabled/disabled
- AWS Config status
- CloudTrail configuration

### Usage

```bash
/carl evidence collect
```

**Output:**
- ✅ Created X new findings from evidence analysis
- Evidence stored in DynamoDB with category tags
- Findings automatically created for detected issues

## Findings Detection

### Stable Finding IDs

Findings use **content-based IDs** to prevent duplicates across evidence collection runs:

```python
# IAM password policy finding
finding_key = f"{account_id}-iam-password-policy"
finding_id = f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}"

# S3 encryption finding (per bucket)
finding_key = f"{account_id}-s3-{bucket_name}-encryption"
finding_id = f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}"

# Security group finding (per security group)
finding_key = f"{account_id}-sg-{sg_id}-permissive"
finding_id = f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}"
```

**Why stable IDs matter:**
- Same issue = same ID across collection runs
- Prevents duplicate findings in database
- Enables proper Jira ticket tracking
- Allows status updates without creating new records

### Multiple Findings Per Resource

A single evidence item can generate **multiple findings**:

**Example - S3 Bucket with 3 issues:**
```
Bucket: my-app-data
  ❌ Encryption not enabled     → Finding: finding-abc123
  ❌ Versioning not enabled     → Finding: finding-def456
  ❌ Logging not enabled        → Finding: finding-ghi789
```

**Example - Multiple Security Groups:**
```
Security Group: sg-0a1b2c3d (allows 0.0.0.0/0:22)  → Finding: finding-jkl012
Security Group: sg-4e5f6g7h (allows 0.0.0.0/0:3389) → Finding: finding-mno345
```

### Detection Logic

**IAM Issues Detected:**
- Password policy too weak (length < 14, no complexity, no rotation)
- Users without MFA
- Root account without MFA
- Access keys not rotated (>90 days)

**S3 Issues Detected:**
- Encryption disabled or permission denied (status = "ERROR")
- Versioning disabled
- Public access not blocked
- Logging disabled

**Network Issues Detected:**
- Security groups allowing 0.0.0.0/0 on sensitive ports (22, 3389, 3306, 5432, etc.)
- VPCs without flow logs enabled
- Overly permissive network ACLs

**Security Service Issues:**
- Security Hub not enabled
- GuardDuty not enabled
- CloudTrail not configured properly
- AWS Config not enabled

## Jira Sync

### How It Works

```bash
/carl jira sync
```

**Process:**
1. Query recent findings from DynamoDB (NEW or IN_PROGRESS status)
2. Check each finding for existing `jira_ticket_id` field
3. Skip findings that already have Jira tickets (duplicate prevention)
4. Create Jira tickets for new findings
5. Update findings with `jira_ticket_id`, `jira_url`, `jira_created_at`
6. Report sync results to Slack

### Duplicate Prevention

**How duplicates are prevented:**

1. **Stable Finding IDs:** Same issue generates same finding_id
2. **Database Check:** Finding record stores `jira_ticket_id` field
3. **Sync Check:** Before creating ticket, check if `jira_ticket_id` exists
4. **Skip Logic:** If ticket exists, skip (counted in "Skipped" metric)

**Example:**
```
Run 1: IAM password policy issue detected
  → Finding: finding-abc123 created
  → Jira ticket CARL-101 created
  → Finding updated: jira_ticket_id = "CARL-101"

Run 2: IAM password policy still an issue
  → Finding: finding-abc123 already exists
  → Check: jira_ticket_id = "CARL-101" (exists!)
  → Skip creating new ticket
  → Result: Skipped: 1 (already have tickets)
```

### Jira Ticket Format

**Issue Type:** Task (standard Jira type)

**Fields:**
- **Summary:** Finding title (e.g., "IAM password policy does not meet requirements")
- **Description:** Detailed remediation steps
- **Priority:** Mapped from severity (Critical→Highest, High→High, Medium→Medium, Low→Low)
- **Labels:** `carl`, `security`, `soc2`, `{severity}`
- **Custom Fields:**
  - Resource ARN
  - AWS Account ID
  - AWS Region
  - SOC 2 Controls (mapped)
  - Compliance Status
  - First Detected timestamp

**Example Ticket:**
```
CARL-101: IAM password policy does not meet requirements

Description:
Resource: arn:aws:iam::123456789012:account-password-policy
Account: 123456789012
Region: us-east-1
Severity: HIGH

Recommendation:
Update IAM password policy to require minimum 14 characters,
complexity requirements, and 90-day rotation.

SOC 2 Controls: CC6.1, CC6.6
Status: NEW
First Detected: 2026-01-28T20:45:00Z
```

## IAM Permissions Required

The CARL Lambda function needs these permissions for evidence collection:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets",
        "s3:GetBucketEncryption",
        "s3:GetBucketVersioning",
        "s3:GetBucketPublicAccessBlock",
        "s3:GetBucketLogging",
        "s3:GetBucketPolicy"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:GetAccountPasswordPolicy",
        "iam:ListUsers",
        "iam:GetUser",
        "iam:ListMFADevices",
        "iam:ListAccessKeys",
        "iam:GetAccessKeyLastUsed",
        "iam:ListUserPolicies",
        "iam:ListAttachedUserPolicies",
        "iam:ListRoles",
        "iam:GetRole"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "securityhub:GetEnabledStandards",
        "securityhub:GetFindings",
        "securityhub:DescribeHub"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudtrail:DescribeTrails",
        "cloudtrail:GetTrailStatus"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVpcs",
        "ec2:DescribeFlowLogs",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeNetworkAcls"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "config:DescribeConfigRules",
        "config:DescribeComplianceByConfigRule"
      ],
      "Resource": "*"
    }
  ]
}
```

**These permissions are READ-ONLY** and allow CARL to:
- Scan AWS resources for compliance issues
- Detect misconfigurations
- Collect audit evidence

**Location:** `/Users/gnegelow/Documents/CARL/carl-infrastructure/core/main.tf` (evidence_collection policy)

## Database Schema

### Evidence Table

```python
{
    "pk": "ACCOUNT#{account_id}",
    "sk": "EVIDENCE#{category}#{timestamp}",
    "evidence_id": "evidence-abc123def456",  # Unique per collection run
    "category": "IAM",  # IAM, S3, NETWORK, SECURITY_SERVICES
    "collected_at": "2026-01-28T20:45:00Z",
    "account_id": "123456789012",
    "content": {
        "password_policy": {...},
        "users": [...],
        "mfa_enabled": false
    }
}
```

### Findings Table

```python
{
    "pk": "ACCOUNT#{account_id}#FINDING#{finding_id}",
    "sk": "TIMESTAMP#{timestamp}",
    "finding_id": "finding-abc123",  # Stable, content-based ID
    "source": "CARL_SCANNER",
    "severity": "HIGH",
    "status": "NEW",
    "title": "IAM password policy does not meet requirements",
    "description": "...",
    "resource_type": "IAM",
    "resource_id": "arn:aws:iam::123456789012:policy",
    "account_id": "123456789012",
    "region": "us-east-1",
    "remediation_steps": "Update password policy to...",
    "control_ids": ["CC6.1", "CC6.6"],
    "created_at": "2026-01-28T20:45:00Z",
    "updated_at": "2026-01-28T20:45:00Z",

    # Jira tracking fields (added after sync)
    "jira_ticket_id": "CARL-101",
    "jira_url": "https://yourorg.atlassian.net/browse/CARL-101",
    "jira_created_at": "2026-01-28T20:50:00Z"
}
```

**Note on jira_ticket_id:**
- This field is added AFTER Jira sync completes
- Used for duplicate prevention on subsequent syncs
- Preserved when converting findings to dictionaries
- Critical for "already have tickets" logic

## Troubleshooting

### No findings created after evidence collect

**Symptoms:** Evidence collected but no findings created

**Causes:**
1. All resources are compliant (no issues detected)
2. Syntax errors in evidence_collector.py (check CloudWatch logs)
3. Missing IAM permissions (check for AccessDenied errors)

**Fix:**
- Check CloudWatch logs for errors
- Verify IAM permissions are applied
- Run `/carl evidence collect` and check Slack response

### Duplicate Jira tickets created

**Symptoms:** Multiple tickets for same issue

**Causes:**
1. Finding IDs not stable (changing each run)
2. jira_ticket_id not preserved in findings
3. Database query not finding existing finding

**Should NOT happen** - fixed in latest code with:
- Stable content-based finding IDs
- jira_ticket_id preservation in get_finding()
- Proper duplicate check before ticket creation

### Only some categories syncing (e.g., only IAM, no S3)

**Symptoms:** Some finding types create tickets, others don't

**Causes:**
1. IAM permissions missing for specific services (e.g., s3:GetBucketEncryption)
2. Detection logic not checking for permission errors
3. S3 encryption returns "ERROR" but detection only checks for None

**Fix:**
- Added comprehensive IAM permissions
- Detection checks for both `None` and `"ERROR"` status
- All categories should sync now

### Jira sync shows "Failed: 1" errors

**Symptoms:** Sync completes but shows failed count

**Causes:**
1. Field name mismatches (finding["finding_id"] vs finding["id"])
2. Missing parameters to Jira API
3. Invalid issue type (custom types don't exist)

**Fixed:**
- All field names corrected to use Finding.to_dict() format
- create_security_finding() parameters fixed
- Changed to standard Jira issue type (Task)

## Recent Fixes (January 28, 2026)

### Issue 1: Nested f-string syntax errors
**Problem:** Python syntax errors in evidence_collector.py prevented module import
**Fix:** Extracted inner f-strings to variables first
**Impact:** ALL /carl commands broken → Fixed

### Issue 2: KeyError 'finding_id'
**Problem:** Finding.to_dict() returns "id" but code looked for "finding_id"
**Fix:** Changed all references to use correct field names
**Files:** slack_router.py, jira_security_sync.py

### Issue 3: DynamoDB composite key errors
**Problem:** GetItem requires both pk+sk, but only provided pk
**Fix:** Changed to Query which only needs pk
**Files:** findings_service.py (all methods)

### Issue 4: Missing update_finding method
**Problem:** FindingsService didn't have update_finding() method
**Fix:** Added method that queries for sk, then updates with pk+sk
**Files:** findings_service.py

### Issue 5: jira_ticket_id not preserved
**Problem:** Finding.to_dict() doesn't include jira_ticket_id, lost during conversion
**Fix:** Manually add jira_ticket_id back to dict after conversion
**Files:** findings_service.py (get_finding, get_recent_findings, get_findings_by_control)

### Issue 6: Duplicate findings across runs
**Problem:** Evidence-based IDs changed each run (evidence-702b, evidence-20ee, evidence-4183)
**Fix:** Changed to stable content-based IDs (account+resource+issue_type)
**Cleanup:** Removed 3 old duplicate findings with "evidence-" prefix

### Issue 7: Only one finding per evidence item
**Problem:** S3 bucket with 3 issues only created 1 finding
**Fix:** Changed method to return list, collect ALL findings
**Files:** evidence_collector.py (_analyze_evidence_for_findings)

### Issue 8: S3 encryption detection failing
**Problem:** Permission denied returns "ERROR" but detection only checked None
**Fix:** Check for both None and "ERROR"
**Files:** evidence_collector.py

### Issue 9: Missing IAM permissions
**Problem:** Lambda lacks evidence collection permissions
**Fix:** Added comprehensive read-only policy
**Files:** carl-infrastructure/core/main.tf (evidence_collection policy)

### Issue 10: Invalid Jira issue type
**Problem:** Custom type "Security Finding" doesn't exist
**Fix:** Changed to standard type "Task"
**Files:** jira_service.py

## Related Documentation

- [SLACK_COMMANDS.md](./SLACK_COMMANDS.md) - All available Slack commands
- [FEATURES.md](./FEATURES.md) - Feature status overview
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture details
