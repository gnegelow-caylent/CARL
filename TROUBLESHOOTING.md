# CARL Troubleshooting Guide

This document contains solutions to common issues encountered with CARL.

---

## Lambda Deployment Issues

### ImportModuleError: No module named 'handlers'

**Symptoms:**
- Health check returns 500 error
- CloudWatch logs show: `Runtime.ImportModuleError: Unable to import module 'handlers.slack_router': No module named 'handlers'`
- Lambda deployment succeeded but function doesn't work

**Root Cause:**
Lambda package has incorrect directory structure. The handler is configured as `handlers.slack_router.lambda_handler` but the `handlers/` directory is not at the root of the zip file.

**Solution:**

1. **Check GitHub Actions packaging** (`.github/workflows/deploy-core.yml`):
   ```yaml
   - name: Package Lambda
     run: |
       mkdir -p carl-app/package
       pip install \
         --platform manylinux2014_x86_64 \
         --target carl-app/package \
         --implementation cp \
         --python-version 3.11 \
         --only-binary=:all: \
         --upgrade \
         -r carl-app/requirements.txt
       # Copy source code into package
       cp -r carl-app/src/* carl-app/package/
       # Package everything including dependencies
       cd carl-app/package
       zip -r ../../carl-infrastructure/core/lambda.zip . -x "*.pyc" -x "__pycache__/*" -x "tests/*"
   ```

2. **Verify source structure** (`carl-app/src/`):
   ```
   carl-app/src/
   ├── handlers/
   │   └── slack_router.py
   ├── services/
   ├── models/
   └── utils/
   ```

3. **Expected zip structure** (at root):
   ```
   lambda.zip
   ├── handlers/
   │   └── slack_router.py
   ├── services/
   ├── models/
   ├── utils/
   └── [dependencies: boto3, slack_sdk, etc.]
   ```

4. **Test locally**:
   ```bash
   cd /path/to/CARL
   mkdir -p test-package
   cp -r carl-app/src/* test-package/
   cd test-package
   zip -r ../test-lambda.zip . -x "*.pyc" -x "__pycache__/*"
   cd ..
   unzip -l test-lambda.zip | grep "handlers/"
   # Should show: handlers/ at root level
   rm -rf test-package test-lambda.zip
   ```

**Prevention:**
- Always verify `cp -r carl-app/src/* carl-app/package/` copies directories correctly
- The `cd carl-app/package` before zipping is critical (ensures files at root)
- Never use `zip -r lambda.zip carl-app/package/` from parent directory

### Python Syntax Errors After Code Changes

**Symptoms:**
- All `/carl` commands fail
- Error: `SyntaxError: f-string: unmatched '('`
- Module import fails

**Root Cause:**
Python doesn't allow nested f-strings with the same quote type.

**Example - BROKEN:**
```python
id=f"evidence-{hashlib.md5(f"{evidence.evidence_id}-mfa".encode()).hexdigest()[:12]}"
```

**Example - FIXED:**
```python
finding_key = f"{evidence.evidence_id}-mfa"
id=f"evidence-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}"
```

**Solution:**
1. Extract inner f-string to a variable first
2. Test locally with `python3 -m py_compile <file.py>`
3. Check CloudWatch logs for exact line number

**Prevention:**
- Run `python3 -m py_compile` on changed files before committing
- GitHub Actions validation should catch this (if running pylint)

---

## Evidence Collection & Findings

### Evidence Collected But No Findings Created

**Symptoms:**
- `/carl evidence collect` succeeds
- Shows "IAM: X items, S3: Y items"
- But no "Created X new findings" message
- DynamoDB FINDINGS table has no new records

**Root Cause:**
Evidence collector not calling `create_findings_from_evidence()` or method has syntax errors.

**Solution:**

1. **Check slack_router.py** (~line 3242):
   ```python
   # Create findings from security issues detected in evidence
   findings = collector.create_findings_from_evidence(results)

   # Store findings in DynamoDB
   findings_service = get_findings_service()
   stored_count = 0
   for finding in findings:
       try:
           findings_service.store_finding(finding)
           stored_count += 1
       except Exception as e:
           logger.error(f"Failed to store finding {finding.id}: {e}")

   if stored_count > 0:
       slack.post_message(
           channel_id,
           text=f"✅ Created *{stored_count}* new findings from evidence analysis."
       )
   ```

2. **Check CloudWatch logs** for errors in `evidence_collector.py`

3. **Verify method exists**:
   ```bash
   grep -n "def create_findings_from_evidence" carl-app/src/services/evidence_collector.py
   ```

**Prevention:**
- Always check CloudWatch logs after deploying evidence collector changes
- Test locally before deploying

### Only IAM Findings Created (No S3, Network, etc.)

**Symptoms:**
- Jira sync shows "Synced: 1" (only IAM)
- S3 buckets exist but no S3 findings created
- Security groups exist but no network findings

**Root Cause:**
One of:
1. IAM permissions missing for S3/EC2/VPC APIs
2. Detection logic only checks for `None`, not `"ERROR"` (permission denied)
3. Evidence collector returns early instead of collecting all findings

**Solutions:**

1. **Check IAM permissions** (`carl-infrastructure/core/main.tf`):
   ```hcl
   resource "aws_iam_role_policy" "evidence_collection" {
     name = "evidence-collection"
     role = aws_iam_role.lambda.id

     policy = jsonencode({
       Version = "2012-10-17"
       Statement = [
         {
           Effect = "Allow"
           Action = [
             "s3:ListAllMyBuckets",
             "s3:GetBucketEncryption",
             "s3:GetBucketVersioning",
             "s3:GetBucketPublicAccessBlock",
             "s3:GetBucketLogging",
             "ec2:DescribeSecurityGroups",
             "ec2:DescribeFlowLogs",
             "ec2:DescribeVpcs"
           ]
           Resource = "*"
         }
       ]
     })
   }
   ```

2. **Fix detection logic** (check for both `None` and `"ERROR"`):
   ```python
   # BROKEN - only checks None
   if content.get("encryption") is None:
       # Create finding...

   # FIXED - checks both None and ERROR
   encryption = content.get("encryption")
   if encryption is None or encryption == "ERROR":
       # Create finding...
   ```

3. **Return list, not early return**:
   ```python
   # BROKEN - returns after first issue
   def _analyze_evidence_for_finding(self, evidence: Evidence) -> Finding | None:
       if issue1_detected:
           return Finding(...)  # Stops here!
       if issue2_detected:
           return Finding(...)  # Never reached

   # FIXED - collects all issues
   def _analyze_evidence_for_findings(self, evidence: Evidence) -> list[Finding]:
       findings = []
       if issue1_detected:
           findings.append(Finding(...))
       if issue2_detected:
           findings.append(Finding(...))
       return findings
   ```

**Verification:**
```bash
# Check CloudWatch logs for AccessDenied errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/carl-dev-api \
  --filter-pattern "AccessDenied" \
  --start-time $(date -u -d '5 minutes ago' +%s)000
```

**Prevention:**
- Add comprehensive IAM permissions upfront
- Check for both `None` and `"ERROR"` in detection logic
- Use list accumulation instead of early returns

---

## Jira Sync Issues

### Duplicate Jira Tickets Created

**Symptoms:**
- Same issue creates multiple tickets: CARL-101, CARL-102, CARL-103
- `/carl jira sync` doesn't skip existing tickets
- "Skipped: 0 (already have tickets)" always shows 0

**Root Cause:**
One of:
1. Finding IDs not stable (changes each evidence collection run)
2. `jira_ticket_id` field not preserved when converting findings
3. Duplicate check not querying correctly

**Solutions:**

1. **Use content-based finding IDs** (not evidence-based):
   ```python
   # BROKEN - changes each run (evidence_id is unique per run)
   finding_key = f"{evidence.evidence_id}-mfa"
   finding_id = f"evidence-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}"

   # FIXED - stable across runs (same issue = same ID)
   finding_key = f"{account_id}-iam-password-policy"
   finding_id = f"finding-{hashlib.md5(finding_key.encode()).hexdigest()[:12]}"
   ```

2. **Preserve jira_ticket_id** in `findings_service.py`:
   ```python
   def get_finding(self, finding_id: str, account_id: str | None = None) -> dict | None:
       # ... query logic ...
       if item:
           finding_dict = Finding.from_dynamodb_item(item).to_dict()
           # CRITICAL: Add back jira_ticket_id (not in Finding model)
           if "jira_ticket_id" in item:
               finding_dict["jira_ticket_id"] = item["jira_ticket_id"]
           if "jira_url" in item:
               finding_dict["jira_url"] = item["jira_url"]
           return finding_dict
       return None
   ```

3. **Check for existing ticket** in `jira_security_sync.py`:
   ```python
   # Get finding from database
   finding = self._get_finding_from_db(finding_id, aws_account_id)

   # Skip if already has Jira ticket
   if finding and finding.get("jira_ticket_id"):
       logger.info(f"Finding {finding_id} already has Jira ticket: {finding['jira_ticket_id']}")
       return None  # Skip
   ```

**Cleanup Old Duplicates:**
```python
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('carl-dev-findings')

# Find old evidence-based IDs
response = table.scan()
items = response.get('Items', [])
old_findings = [item for item in items if item.get('finding_id', '').startswith('evidence-')]

for finding in old_findings:
    pk = finding['pk']
    sk = finding['sk']
    print(f"Deleting: {finding.get('finding_id')}")
    table.delete_item(Key={'pk': pk, 'sk': sk})
```

**Prevention:**
- Always use content-based IDs (account + resource + issue type)
- Preserve all DynamoDB fields not in Finding model
- Test duplicate prevention before deploying

### Jira Sync Failed: 'finding_id' KeyError

**Symptoms:**
- `/carl jira sync` shows "Jira sync failed: 'finding_id'"
- Works for some findings, fails for others
- Error in CloudWatch logs: `KeyError: 'finding_id'`

**Root Cause:**
Field name mismatch. `Finding.to_dict()` returns `"id"` but code looks for `"finding_id"`.

**Solution:**

Fix all field name references in `slack_router.py` and `jira_security_sync.py`:

```python
# BROKEN
finding_id=finding["finding_id"],  # KeyError!
recommendation=finding["recommendation"],  # KeyError!
aws_account_id=finding["aws_account_id"],  # KeyError!

# FIXED
finding_id=finding["id"],
recommendation=finding.get("remediation_steps", "Review this finding"),
aws_account_id=finding.get("account_id", "N/A"),
```

**Find all occurrences:**
```bash
grep -rn 'finding\["finding_id"\]' carl-app/src/
grep -rn 'finding\["recommendation"\]' carl-app/src/
grep -rn 'finding\["aws_account_id"\]' carl-app/src/
```

**Prevention:**
- Use `.get()` with defaults instead of direct dictionary access
- Check Finding model's `to_dict()` method for actual field names
- Test with actual findings data before deploying

### Jira API Error: Invalid Issue Type

**Symptoms:**
- Error: `Jira API 400: "Specify a valid issue type"`
- Ticket creation fails
- Custom issue type doesn't exist in Jira project

**Root Cause:**
Using custom issue type ("Security Finding") that doesn't exist in Jira project.

**Solution:**

Change to standard Jira issue types in `jira_service.py`:

```python
# BROKEN - custom type doesn't exist
ISSUE_TYPE_SECURITY_FINDING = "Security Finding"

# FIXED - standard types work immediately
ISSUE_TYPE_SECURITY_FINDING = "Task"
ISSUE_TYPE_RISK_EXCEPTION = "Task"
ISSUE_TYPE_DRIFT = "Task"
```

**Alternative - Create Custom Type:**
1. Go to Jira Project Settings → Issue Types
2. Create new issue type: "Security Finding"
3. Add to project's issue type scheme
4. Add required fields to screens

**Prevention:**
- Use standard types (Task, Bug, Story, Epic) unless custom types already exist
- Test Jira API calls in dev environment first
- Document custom Jira configuration requirements

---

## DynamoDB Issues

### ValidationException: The provided key element does not match the schema

**Symptoms:**
- Error: `ValidationException: The provided key element does not match the schema`
- Operations like `get_finding()` or `update_finding()` fail
- Error mentions missing pk or sk

**Root Cause:**
CARL uses composite keys (pk + sk), but code only provides pk to `GetItem` or `UpdateItem`.

**Solution:**

Change from `GetItem` to `Query` (only needs pk):

```python
# BROKEN - GetItem requires both pk AND sk
response = self.table.get_item(
    Key={"pk": f"ACCOUNT#{account_id}#FINDING#{finding_id}"}
)

# FIXED - Query only needs pk
response = self.table.query(
    KeyConditionExpression=Key("pk").eq(f"ACCOUNT#{account_id}#FINDING#{finding_id}"),
    Limit=1
)
items = response.get("Items", [])
item = items[0] if items else None
```

For updates, query first to get sk, then update with both:

```python
# Query to get sk
response = self.table.query(
    KeyConditionExpression=Key("pk").eq(f"ACCOUNT#{account_id}#FINDING#{finding_id}"),
    Limit=1
)
items = response.get("Items", [])
if not items:
    return False

item = items[0]
pk = item["pk"]
sk = item["sk"]

# Update with both pk and sk
self.table.update_item(
    Key={"pk": pk, "sk": sk},
    UpdateExpression="SET #status = :status",
    ExpressionAttributeValues={":status": new_status},
    ExpressionAttributeNames={"#status": "status"}
)
```

**Prevention:**
- Never use `GetItem` with composite key tables
- Always query first for updates/deletes
- Document table schema in code comments

---

## Terraform Issues

### Terraform Apply Runs Locally Instead of GitHub Actions

**Symptoms:**
- User says "why are you running terraform locally STOP"
- Changes made directly to AWS resources
- No audit trail in GitHub

**Root Cause:**
Running `terraform apply` from local machine instead of pushing to GitHub and letting GitHub Actions deploy.

**Correct Workflow:**

1. Make changes to Terraform code
2. Commit and push to `develop` branch:
   ```bash
   git add carl-infrastructure/
   git commit -m "feat: add evidence collection IAM permissions"
   git push origin develop
   ```
3. GitHub Actions automatically:
   - Validates Terraform
   - Runs security scans
   - Creates plan
   - Applies to dev environment
   - Runs integration tests

**Never do this:**
```bash
cd carl-infrastructure/core
terraform init
terraform apply  # ❌ WRONG - bypasses CI/CD
```

**Prevention:**
- **Always** push changes to GitHub
- Let GitHub Actions handle deployment
- Local Terraform only for testing/validation (never apply)

---

## Resources

### Log Files
- **Lambda Logs:** CloudWatch `/aws/lambda/carl-dev-api`
- **GitHub Actions:** `.github/workflows/deploy-core.yml` run history

### Configuration Files
- **Lambda Handler:** `carl-infrastructure/core/main.tf` (line ~741)
- **Lambda Packaging:** `.github/workflows/deploy-core.yml` (lines 216-234)
- **IAM Permissions:** `carl-infrastructure/core/main.tf` (evidence_collection policy)

### Useful Commands
```bash
# Check Lambda logs
aws logs tail /aws/lambda/carl-dev-api --follow

# Test Lambda locally
python3 -c "from carl-app.src.handlers.slack_router import lambda_handler; print('OK')"

# Validate Terraform
cd carl-infrastructure/core && terraform validate

# Check GitHub Actions status
gh run list --workflow=deploy-core.yml --limit 5

# Test Jira API
curl -X GET \
  -H "Authorization: Bearer $JIRA_API_TOKEN" \
  https://yourorg.atlassian.net/rest/api/3/issue/CARL-101
```

### Related Documentation
- [EVIDENCE_AND_FINDINGS.md](./EVIDENCE_AND_FINDINGS.md) - Evidence collection pipeline
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [SLACK_COMMANDS.md](./SLACK_COMMANDS.md) - All Slack commands
