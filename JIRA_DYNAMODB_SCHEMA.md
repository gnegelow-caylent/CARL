# CARL DynamoDB Schema Changes for Jira Integration

This document describes the schema changes needed to support Jira integration.

---

## Overview

Jira integration requires adding new attributes to existing DynamoDB tables to track ticket associations and sync status.

**Affected Tables:**
1. `carl-findings` (Security Hub findings)
2. `carl-risk-exceptions` (Risk exception requests)
3. `carl-drift-detections` (Configuration drift)

---

## Schema Changes

### 1. carl-findings Table

**New Attributes:**

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `jira_ticket_id` | String | Jira ticket key | `CARLSEC-123` |
| `jira_url` | String | Full URL to Jira ticket | `https://yourcompany.atlassian.net/browse/CARLSEC-123` |
| `jira_created_at` | String (ISO 8601) | When Jira ticket was created | `2026-01-28T10:30:00Z` |
| `jira_last_updated` | String (ISO 8601) | Last time Jira ticket was updated | `2026-01-28T15:45:00Z` |
| `jira_ticket_deleted` | Boolean (optional) | Flag if Jira ticket was deleted | `true` |
| `jira_deleted_at` | String (ISO 8601, optional) | When Jira ticket was deleted | `2026-01-29T08:00:00Z` |
| `last_synced_at` | String (ISO 8601) | Last successful sync to Jira | `2026-01-28T15:45:00Z` |

**Global Secondary Index (GSI) Required:**

**Index Name:** `jira_ticket_id-index`
- **Partition Key:** `jira_ticket_id` (String)
- **Purpose:** Lookup findings by Jira ticket key (for webhook processing)
- **Projection:** ALL

**Example Item (with Jira):**
```json
{
  "finding_id": "arn:aws:securityhub:us-east-1:123456789012:finding/abc-123",
  "title": "S3 bucket encryption is not enabled",
  "severity": "HIGH",
  "resource_id": "arn:aws:s3:::my-bucket",
  "resource_type": "AWS::S3::Bucket",
  "compliance_status": "FAILED",
  "aws_account_id": "123456789012",
  "region": "us-east-1",
  "first_observed_at": "2026-01-28T10:00:00Z",
  "last_observed_at": "2026-01-28T10:00:00Z",
  "status": "NEW",

  // NEW Jira fields
  "jira_ticket_id": "CARLSEC-123",
  "jira_url": "https://yourcompany.atlassian.net/browse/CARLSEC-123",
  "jira_created_at": "2026-01-28T10:30:00Z",
  "jira_last_updated": "2026-01-28T15:45:00Z",
  "last_synced_at": "2026-01-28T15:45:00Z"
}
```

**Terraform Update:**

```hcl
# Add to carl-infrastructure/modules/foundation/dynamodb.tf

resource "aws_dynamodb_table" "findings" {
  name         = "carl-findings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "finding_id"

  attribute {
    name = "finding_id"
    type = "S"
  }

  # NEW: GSI for Jira ticket lookup
  attribute {
    name = "jira_ticket_id"
    type = "S"
  }

  global_secondary_index {
    name            = "jira_ticket_id-index"
    hash_key        = "jira_ticket_id"
    projection_type = "ALL"
  }

  # ... existing attributes ...
}
```

---

### 2. carl-risk-exceptions Table

**New Attributes:**

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `jira_ticket_id` | String | Jira ticket key | `CARLSEC-456` |
| `jira_url` | String | Full URL to Jira ticket | `https://yourcompany.atlassian.net/browse/CARLSEC-456` |
| `jira_created_at` | String (ISO 8601) | When Jira ticket was created | `2026-01-28T11:00:00Z` |
| `jira_last_updated` | String (ISO 8601) | Last time Jira ticket was updated | `2026-01-28T16:00:00Z` |
| `related_finding_jira` | String (optional) | Jira key of related finding | `CARLSEC-123` |

**Global Secondary Index (GSI) Required:**

**Index Name:** `jira_ticket_id-index`
- **Partition Key:** `jira_ticket_id` (String)
- **Purpose:** Lookup exceptions by Jira ticket key
- **Projection:** ALL

**Example Item (with Jira):**
```json
{
  "exception_id": "exc-20260128-001",
  "finding_title": "S3 bucket encryption is not enabled",
  "finding_id": "arn:aws:securityhub:us-east-1:123456789012:finding/abc-123",
  "justification": "This bucket contains public marketing assets only",
  "expiration_date": "2026-06-30",
  "requested_by": "U123456",
  "requested_at": "2026-01-28T11:00:00Z",
  "status": "PENDING",

  // NEW Jira fields
  "jira_ticket_id": "CARLSEC-456",
  "jira_url": "https://yourcompany.atlassian.net/browse/CARLSEC-456",
  "jira_created_at": "2026-01-28T11:00:00Z",
  "jira_last_updated": "2026-01-28T16:00:00Z",
  "related_finding_jira": "CARLSEC-123"
}
```

**Terraform Update:**

```hcl
# Add to carl-infrastructure/modules/foundation/dynamodb.tf

resource "aws_dynamodb_table" "risk_exceptions" {
  name         = "carl-risk-exceptions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "exception_id"

  attribute {
    name = "exception_id"
    type = "S"
  }

  # NEW: GSI for Jira ticket lookup
  attribute {
    name = "jira_ticket_id"
    type = "S"
  }

  global_secondary_index {
    name            = "jira_ticket_id-index"
    hash_key        = "jira_ticket_id"
    projection_type = "ALL"
  }

  # ... existing attributes ...
}
```

---

### 3. carl-drift-detections Table

**New Attributes:**

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `jira_ticket_id` | String | Jira ticket key | `CARLSEC-789` |
| `jira_url` | String | Full URL to Jira ticket | `https://yourcompany.atlassian.net/browse/CARLSEC-789` |
| `jira_created_at` | String (ISO 8601) | When Jira ticket was created | `2026-01-28T12:00:00Z` |
| `jira_last_updated` | String (ISO 8601) | Last time Jira ticket was updated | `2026-01-28T17:00:00Z` |

**Global Secondary Index (GSI) Required:**

**Index Name:** `jira_ticket_id-index`
- **Partition Key:** `jira_ticket_id` (String)
- **Purpose:** Lookup drift by Jira ticket key
- **Projection:** ALL

**Example Item (with Jira):**
```json
{
  "drift_id": "drift-20260128-001",
  "resource_type": "AWS::S3::Bucket",
  "resource_id": "arn:aws:s3:::my-bucket",
  "drift_type": "Modified",
  "detected_at": "2026-01-28T12:00:00Z",
  "expected_state": {
    "Versioning": "Enabled"
  },
  "actual_state": {
    "Versioning": "Suspended"
  },
  "drift_details": "Versioning was disabled on bucket",
  "status": "ACTIVE",

  // NEW Jira fields
  "jira_ticket_id": "CARLSEC-789",
  "jira_url": "https://yourcompany.atlassian.net/browse/CARLSEC-789",
  "jira_created_at": "2026-01-28T12:00:00Z",
  "jira_last_updated": "2026-01-28T17:00:00Z"
}
```

**Terraform Update:**

```hcl
# Add to carl-infrastructure/modules/foundation/dynamodb.tf

resource "aws_dynamodb_table" "drift_detections" {
  name         = "carl-drift-detections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "drift_id"

  attribute {
    name = "drift_id"
    type = "S"
  }

  # NEW: GSI for Jira ticket lookup
  attribute {
    name = "jira_ticket_id"
    type = "S"
  }

  global_secondary_index {
    name            = "jira_ticket_id-index"
    hash_key        = "jira_ticket_id"
    projection_type = "ALL"
  }

  # ... existing attributes ...
}
```

---

## Migration Strategy

### Option 1: No Migration (Recommended)

Since DynamoDB is schema-less, **no migration is required**. Simply deploy the updated code and:

1. New findings/exceptions/drift will automatically include Jira fields when synced
2. Existing items without Jira fields will continue to work (code checks for `get("jira_ticket_id")`)
3. Users can run `/carl jira sync` to backfill Jira tickets for existing items

### Option 2: Backfill Script (Optional)

If you want to sync all existing items to Jira immediately:

```python
# scripts/backfill_jira_tickets.py

from services.jira_security_sync import JiraSecuritySync
from utils.dynamodb_utils import get_table

def backfill_findings():
    """Backfill Jira tickets for existing findings."""
    findings_table = get_table("carl-findings")
    jira_sync = JiraSecuritySync()

    # Scan all findings
    response = findings_table.scan()
    findings = response.get("Items", [])

    for finding in findings:
        # Skip if already has Jira ticket
        if finding.get("jira_ticket_id"):
            print(f"Skipping {finding['finding_id']} - already has Jira ticket")
            continue

        # Create Jira ticket
        result = jira_sync.sync_finding_to_jira(
            finding_id=finding["finding_id"],
            title=finding["title"],
            severity=finding["severity"],
            resource_type=finding.get("resource_type", "Unknown"),
            resource_id=finding["resource_id"],
            compliance_status=finding.get("compliance_status", "FAILED"),
            recommendation=finding.get("recommendation", "Review this finding"),
            aws_account_id=finding.get("aws_account_id", "N/A"),
            region=finding.get("region", "us-east-1")
        )

        if result["success"]:
            print(f"✓ Created Jira ticket {result['jira_key']} for {finding['finding_id']}")
        else:
            print(f"✗ Failed to create Jira ticket for {finding['finding_id']}: {result.get('error')}")

if __name__ == "__main__":
    backfill_findings()
```

---

## GSI Cost Impact

**Global Secondary Indexes:**
- **Storage:** No additional cost (same data, just indexed differently)
- **Read/Write:** Pay-per-request billing (same as base table)
- **Estimated Cost:** $0 (assuming existing usage patterns)

**Why GSI is Required:**
- Webhooks from Jira provide `issue_key` (e.g., `CARLSEC-123`)
- Need to quickly find the corresponding CARL finding/exception/drift
- Without GSI, would need to scan entire table (slow and expensive)

---

## Deployment Steps

### 1. Update Terraform

```bash
cd carl-infrastructure/modules/foundation
# Update dynamodb.tf with new GSIs
terraform plan
terraform apply
```

**Note:** Adding GSIs to existing tables is a non-breaking change. DynamoDB will backfill the index automatically.

### 2. Deploy Updated Lambda Code

```bash
cd carl-app
# Code already handles optional Jira fields
# No code changes needed for schema migration
./deploy.sh
```

### 3. Test Jira Integration

```bash
# In Slack
/carl jira test

# Create a test finding with Jira ticket
/carl jira sync
```

### 4. (Optional) Backfill Existing Items

```bash
python scripts/backfill_jira_tickets.py
```

---

## Rollback Plan

If Jira integration needs to be disabled:

1. **Disable Jira commands:** Comment out Jira command routing in `slack_router.py`
2. **Stop automatic sync:** Remove Jira sync calls from findings collection
3. **Keep GSIs:** They don't affect existing functionality and cost nothing if unused
4. **Data preserved:** Jira fields remain in DynamoDB (can be ignored or used later)

**No data loss occurs during rollback.**

---

## Testing Checklist

- [ ] Create new finding → Jira ticket created automatically
- [ ] `/carl findings` shows Jira link for synced findings
- [ ] `/carl jira test` returns success
- [ ] `/carl jira status` shows sync stats
- [ ] `/carl jira sync` syncs unsynced findings
- [ ] Jira webhook updates CARL when ticket status changes
- [ ] GSI lookup works (finding by Jira key)
- [ ] Exception and drift sync works
- [ ] Manual "Create Jira Ticket" button works

---

## Monitoring

**CloudWatch Metrics to Track:**
- `JiraAPICallCount` - Number of Jira API calls
- `JiraAPIErrorRate` - Failed Jira API calls
- `JiraSyncDuration` - Time to sync item to Jira
- `WebhookProcessingTime` - Jira webhook processing time

**Alarms:**
- Jira API error rate > 5%
- Webhook processing time > 5 seconds

---

## Security Considerations

1. **Jira Credentials:** Stored in AWS Secrets Manager (encrypted at rest)
2. **Webhook Authentication:** Jira webhooks include secret token
3. **API Permissions:** Jira service account has minimal permissions (create/update issues only)
4. **Data Sensitivity:** No sensitive data sent to Jira (resource IDs are anonymized if needed)

---

*Last Updated: 2026-01-28*
