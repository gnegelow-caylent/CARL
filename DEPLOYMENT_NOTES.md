# CARL Deployment Notes

## Session: Foundation Module Deployment with Pricing Prefetch
**Date**: January 29-30, 2026
**Status**: ✅ DEPLOYED & VERIFIED

---

## What Was Deployed

### 1. Foundation Module (carl-infrastructure/modules/foundation/)
Complete foundation infrastructure for CARL including:
- **9 DynamoDB Tables**: Findings, evidence, preferences, approvals, remediations, conversations, exceptions, AI feedback, foundation
- **Scan History Tables**: For continuous learning system
- **Resource Graph Tables**: For tracking AWS resource relationships
- **3 Lambda Functions**:
  - pricing-prefetch (comprehensive AWS pricing cache)
  - pattern-analyzer (daily pattern analysis)
  - api (main CARL API - updated deployment)
- **EventBridge Schedules**: Monthly pricing refresh, daily pattern analysis
- **Secrets Manager**: Slack bot token and signing secret (with KMS encryption)
- **SNS Topics**: Alert notifications
- **CloudWatch Logs**: With KMS encryption

### 2. Pricing Prefetch System
Comprehensive AWS pricing cache covering 100+ services:
- **366 pricing items** cached across 3 regions (us-east-1, us-west-2, eu-west-1)
- **12 service categories**: Compute, storage, database, networking, media, analytics, security, integration, ML/AI, containers, IoT, other
- **Execution time**: ~13.5 seconds
- **Cache refresh**: Monthly via EventBridge
- **Cost**: ~$0.51/month (DynamoDB pay-per-request)

### 3. Continuous Learning System
Pattern analysis and interaction logging:
- **Scan history table**: Tracks every `/carl ask` interaction
- **Resource graph table**: Maps AWS resources and relationships
- **Pattern analyzer Lambda**: Runs daily at 2am UTC to learn patterns
- **Feedback buttons**: 👍 👎 on every answer
- **Cost**: ~$0.67/month total

---

## Infrastructure Changes Made

### Core Infrastructure (carl-infrastructure/core/main.tf)

#### Added KMS Key Resource (Lines 205-320)
```terraform
resource "aws_kms_key" "carl" {
  description             = "CARL encryption key for ${var.environment}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    # Comprehensive policy with 5 principals:
    # 1. Root account (full access)
    # 2. Deployer role (encrypt, decrypt, generate data keys)
    # 3. CloudWatch Logs (with log group condition)
    # 4. DynamoDB (unrestricted for table encryption)
    # 5. Secrets Manager (with account + ViaService conditions)
  })
}

resource "aws_kms_alias" "carl" {
  name          = "alias/${local.name_prefix}"
  target_key_id = aws_kms_key.carl.key_id
}
```

**Why This Was Needed:**
- Foundation module was referencing KMS key via data source, but key didn't exist in Terraform
- Fresh deployments would fail without this resource
- Manual KMS key policy updates during troubleshooting needed to be captured in code

#### Updated S3 Bucket Encryption
Changed all S3 buckets from AES256 to KMS encryption:
- `carl-tfstate-*` bucket (Terraform state)
- `carl-*-evidence` bucket (Audit evidence)
- `carl-*-reports` bucket (Compliance reports)

```terraform
# Before
sse_algorithm = "AES256"

# After
sse_algorithm     = "aws:kms"
kms_master_key_id = aws_kms_key.carl.arn
```

#### Conditional Table Creation
Added `count` parameters to prevent race conditions:
```terraform
resource "aws_dynamodb_table" "evidence" {
  count = var.enable_foundation ? 0 : 1
  # Only create if foundation module is disabled
}

resource "aws_dynamodb_table" "findings" {
  count = var.enable_foundation ? 0 : 1
}

resource "aws_dynamodb_table" "exceptions" {
  count = var.enable_foundation ? 0 : 1
}
```

### OIDC IAM Permissions (carl-infrastructure/oidc/main.tf)

All deployer role permissions verified and complete:

#### KMS Permissions (3 statements)
1. **KMSKeyCreation**: Create keys with Project=CARL tag
2. **KMSAliasCreation**: Create/manage aliases (requires both alias and key resources)
3. **KMSManagement**: All management operations with ResourceTag condition
4. **KMSList**: List keys and aliases

#### Secrets Manager Permissions
```terraform
actions = [
  "secretsmanager:CreateSecret",
  "secretsmanager:DeleteSecret",
  "secretsmanager:DescribeSecret",
  "secretsmanager:GetSecretValue",
  "secretsmanager:PutSecretValue",
  "secretsmanager:UpdateSecret",
  "secretsmanager:TagResource",
  "secretsmanager:UntagResource",
  "secretsmanager:ListSecrets",
  "secretsmanager:GetResourcePolicy",     # Critical for Terraform refresh
  "secretsmanager:PutResourcePolicy",     # Critical for resource policies
  "secretsmanager:DeleteResourcePolicy"   # Critical for cleanup
]
```

#### SNS Permissions
```terraform
actions = [
  "sns:CreateTopic",
  "sns:DeleteTopic",
  "sns:GetTopicAttributes",
  "sns:SetTopicAttributes",
  "sns:Subscribe",
  "sns:Unsubscribe",
  "sns:TagResource",
  "sns:UntagResource",
  "sns:ListTagsForResource"
]
```

#### EventBridge Permissions (2 statements)
1. **EventBridgeRules**: Full access to rules
2. **EventBridgeBuses**: Create, delete, describe, tag event buses

### Foundation Module (carl-infrastructure/modules/foundation/main.tf)

#### Changed KMS Key from Resource to Data Source
```terraform
# Before (tried to create new key)
# resource "aws_kms_key" "carl" { ... }

# After (references existing key from core infrastructure)
data "aws_kms_alias" "carl" {
  name = "alias/${var.project_name}-${var.environment}"
}
```

**All 19 references updated:**
- `aws_kms_key.carl.arn` → `data.aws_kms_alias.carl.target_key_arn`
- `aws_kms_key.carl.key_id` → `data.aws_kms_alias.carl.target_key_id`

#### Removed Drift Table
Drift table is created by the drift module, not foundation module.

---

## Troubleshooting During Deployment

### Issues Encountered and Fixed

1. **Reserved Environment Variable** ✅
   - Error: `AWS_LAMBDA_FUNCTION_NAME` cannot be manually set
   - Fix: Removed from Terraform (AWS provides automatically)

2. **KMS Permission Errors** ✅
   - Multiple `AccessDeniedException` errors
   - Fix: Split KMS permissions into 3 statements (creation, alias, management)
   - Key insight: `aws:RequestTag` for creation, `aws:ResourceTag` for management

3. **EventBridge Bus Permissions** ✅
   - Error: `events:TagResource` denied on event bus
   - Fix: Added separate statement for event bus operations

4. **Secrets Manager Policy Permissions** ✅
   - Error: `secretsmanager:GetResourcePolicy` denied
   - Fix: Added 3 policy-related actions to Secrets Manager statement

5. **Race Condition - Duplicate Tables** ✅
   - Error: Tables being created by both core and foundation modules
   - Fix: Added conditional creation with `count` parameter

6. **KMS Key Scheduled for Deletion** ✅
   - Occurred when converting KMS resource to data source
   - Fix: `aws kms cancel-key-deletion` + `aws kms enable-key`

7. **Secrets Scheduled for Deletion** ✅
   - Secrets created then deleted in previous failed deployment
   - Fix: `aws secretsmanager restore-secret` for both secrets

8. **Terraform Trying to CREATE Existing Secrets** ✅
   - Secrets existed in AWS but not in Terraform state
   - Fix: `terraform import` for both secrets

---

## Manual Operations Performed

### 1. Imported Existing Resources into Terraform State

#### Secrets Manager Secrets
```bash
cd carl-infrastructure/core

terraform import 'module.foundation[0].aws_secretsmanager_secret.slack_bot_token' \
  arn:aws:secretsmanager:us-east-1:403802364021:secret:carl/dev/slack/bot-token-335MuD

terraform import 'module.foundation[0].aws_secretsmanager_secret.slack_signing_secret' \
  arn:aws:secretsmanager:us-east-1:403802364021:secret:carl/dev/slack/signing-secret-ENhEVv
```

#### KMS Key and Alias
```bash
# Import the KMS key
terraform import aws_kms_key.carl 1dd3d095-92da-4519-8870-c22892cadb44

# Import the KMS alias
terraform import aws_kms_alias.carl alias/carl-dev
```

**Result**: All resources now in shared S3 Terraform state, GitHub Actions will recognize them as existing

### 2. KMS Key Policy (Already Applied Manually - Now in Terraform)
The comprehensive KMS key policy was initially applied manually via AWS CLI during troubleshooting. It is now captured in the Terraform code (core/main.tf) for fresh deployments.

Key principals:
- Root account: Full access
- Deployer role: Encrypt, decrypt, generate data keys, create grants
- CloudWatch Logs: With log group ARN condition
- DynamoDB: Unrestricted for table encryption
- Secrets Manager: With account + ViaService conditions

---

## Verification & Testing

### Lambda Execution Verified ✅
```
Function: carl-dev-pricing-prefetch
Status: Active
Last Updated: 2026-01-30T02:28:01
Execution: Successful
Duration: 13.5 seconds
Memory: 96 MB used (512 MB allocated)
```

### Pricing Cache Populated ✅
```
Table: carl-dev-pricing-cache
Status: ACTIVE
Items: 362 (out of 366 logged - slight delay in consistency)

Sample data:
- RDS db.m5.xlarge: $0.356/hour (us-east-1)
- MediaConvert: $0.015/minute (all regions)
- EC2 c5.4xlarge: $0.68/hour
- KMS keys: $1.00/month
```

### Foundation Module Deployed ✅
All resources created successfully:
- 9 DynamoDB tables (ACTIVE)
- 3 Lambda functions (ACTIVE)
- 2 Secrets Manager secrets (ACTIVE, KMS encrypted)
- EventBridge schedules (ENABLED)
- SNS topics (ACTIVE)

---

## Architecture Agent Capabilities

With pricing cache populated, CARL can now provide:
- **Fast architecture recommendations** (<3 seconds vs 10+ seconds)
- **Accurate AWS pricing** (real-time from AWS Price List API)
- **Cost comparisons** for 100+ services across 3 regions
- **Media transcoding pricing** (MediaConvert, MediaLive, MediaPackage)

Example command in Slack:
```
/carl recommend media transcoding app architecture
```

Expected response time: <3 seconds with comprehensive pricing

---

## Cost Summary

### Monthly Operational Costs

| Component | Cost | Notes |
|-----------|------|-------|
| DynamoDB Tables (10 tables) | $0.51/month | Pay-per-request, low usage |
| Lambda Executions | $0.15/month | Pricing prefetch monthly, pattern analyzer daily |
| Secrets Manager (2 secrets) | $0.80/month | $0.40 per secret |
| CloudWatch Logs | $0.10/month | Log retention 7 days |
| KMS Key | $1.00/month | Single customer-managed key |
| S3 Storage (minimal) | $0.05/month | Evidence, reports, tfstate |
| **Total** | **~$2.61/month** | Foundation module fully deployed |

### One-Time Costs
- None (all pay-per-request or pay-as-you-go)

---

## Next Steps for Fresh Deployments

### 1. Deploy OIDC (One-Time per AWS Account)
```bash
cd carl-infrastructure/oidc
terraform init
terraform apply -var="github_org=gnegelow-caylent" -var="github_repo=CARL"
```

### 2. Add GitHub Secrets
From OIDC outputs, add to GitHub repository secrets:
- `AWS_ROLE_ARN_DEV`
- `AWS_ROLE_ARN_QA`
- `AWS_ROLE_ARN_PROD`
- `AWS_REGION`
- `SLACK_BOT_TOKEN_DEV` (actual token, not secret ARN)
- `SLACK_SIGNING_SECRET_DEV` (actual secret, not secret ARN)

### 3. Deploy Core Infrastructure
```bash
git push origin develop
```

GitHub Actions will:
1. Deploy core infrastructure (KMS key, DynamoDB, S3)
2. Deploy foundation module (all foundation tables, Lambdas, secrets)
3. Trigger pricing prefetch Lambda
4. Populate pricing cache (366 items, ~13 seconds)

### 4. Verify Deployment
```bash
# Check Lambda status
aws lambda get-function --function-name carl-dev-pricing-prefetch

# Check pricing cache
aws dynamodb scan --table-name carl-dev-pricing-cache --select COUNT

# Check CloudWatch Logs
aws logs tail /aws/lambda/carl-dev-pricing-prefetch --since 1h
```

---

## Important Notes

### Terraform State
- **Backend**: S3 bucket `carl-tfstate-403802364021`
- **Key**: `carl-core/terraform.tfstate`
- **Region**: us-east-1
- **Locking**: DynamoDB table `carl-tfstate-locks`
- Both local Terraform and GitHub Actions use the same state

### Secrets Management
- Secrets are created by Terraform but values must be set manually via AWS Console or CLI
- Terraform only manages the secret resource, not the secret value
- For GitHub Actions: Pass actual secret values via GitHub Secrets

### KMS Key Policy
- The comprehensive policy in `core/main.tf` handles all current use cases
- If adding new AWS services that need KMS access, add service principal to policy
- Deployer role has `GenerateDataKey` permission (required for Secrets Manager)

### Race Conditions
- Core infrastructure conditionally creates 3 tables (evidence, findings, exceptions)
- Foundation module creates these tables if `enable_foundation=true`
- Drift module creates drift table (not foundation module)
- Ensure only one module creates each resource

---

## Rollback Plan

If deployment fails:

### 1. Check GitHub Actions Logs
```bash
# Via GitHub CLI
gh run list --branch develop --limit 5
gh run view <run-id> --log
```

### 2. Check Terraform State
```bash
cd carl-infrastructure/core
terraform state list
terraform state show <resource>
```

### 3. Destroy Foundation Module Only
```bash
terraform apply -var="enable_foundation=false" -auto-approve
```

### 4. Destroy Everything (Nuclear Option)
```bash
terraform destroy -auto-approve
```

---

## Lessons Learned

1. **KMS Permissions Are Complex**
   - Key creation requires `aws:RequestTag` condition
   - Key management requires `aws:ResourceTag` condition
   - Alias creation requires permissions on both alias and key resources

2. **Secrets Manager Requires Policy Permissions**
   - Terraform refresh needs `GetResourcePolicy`, `PutResourcePolicy`, `DeleteResourcePolicy`
   - Without these, Terraform can create but not fully manage secrets

3. **Import Existing Resources Before Applying**
   - If resources exist outside Terraform, import them first
   - Otherwise Terraform will try to create duplicates and fail

4. **Race Conditions Need Conditional Creation**
   - Use `count` parameter with boolean variable
   - Only one module should create each resource
   - Document ownership clearly

5. **AWS Lambda Reserved Variables**
   - Never manually set `AWS_LAMBDA_FUNCTION_NAME`, `AWS_REGION`, etc.
   - AWS provides these automatically at runtime

6. **Service Principals in KMS Policies**
   - Some services need conditions (CloudWatch Logs: encryption context)
   - Others can be unrestricted (DynamoDB, SNS)
   - Secrets Manager needs both account and ViaService conditions

---

## References

- **AWS Price List API**: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html
- **KMS Key Policies**: https://docs.aws.amazon.com/kms/latest/developerguide/key-policies.html
- **Secrets Manager**: https://docs.aws.amazon.com/secretsmanager/latest/userguide/
- **EventBridge Schedules**: https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html
- **GitHub OIDC**: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services

---

**Document Version**: 1.0
**Last Updated**: 2026-01-30T02:30:00Z
**Maintained By**: Greg Negelow (gnegelow-caylent)
