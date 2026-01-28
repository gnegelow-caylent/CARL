# CARL OIDC Setup Guide

Deploy CARL securely with OIDC (OpenID Connect) - no hardcoded AWS credentials needed!

---

## Overview

Instead of storing AWS access keys in GitHub secrets, we use OIDC to allow GitHub Actions to assume IAM roles directly. This is more secure because:

✅ No long-lived credentials
✅ No credential rotation needed
✅ Automatic expiration (tokens valid for 1 hour)
✅ Fine-grained permissions per environment
✅ Audit trail in CloudTrail

---

## Quick Start

### Step 1: Deploy OIDC Infrastructure (One-Time Setup)

This creates the GitHub OIDC provider and IAM roles in your AWS account.

```bash
cd carl-infrastructure/oidc

# Initialize Terraform
terraform init

# Review what will be created
terraform plan

# Deploy
terraform apply
```

**What this creates:**
- GitHub OIDC provider in AWS
- IAM role: `carl-deployer-dev`
- IAM role: `carl-deployer-qa`
- IAM role: `carl-deployer-prod`
- Least-privilege policies for each role

**Time:** ~2 minutes

### Step 2: Add Role ARNs to GitHub Secrets

After the OIDC deployment completes, you'll see output like this:

```
Outputs:

deployer_role_arn_dev = "arn:aws:iam::123456789012:role/carl-deployer-dev"
deployer_role_arn_qa = "arn:aws:iam::123456789012:role/carl-deployer-qa"
deployer_role_arn_prod = "arn:aws:iam::123456789012:role/carl-deployer-prod"
```

**Add these to GitHub:**

1. Go to https://github.com/gnegelow-caylent/CARL/settings/secrets/actions
2. Click "New repository secret"
3. Add these 4 secrets:

```
Name: AWS_ROLE_ARN_DEV
Value: arn:aws:iam::123456789012:role/carl-deployer-dev

Name: AWS_ROLE_ARN_QA
Value: arn:aws:iam::123456789012:role/carl-deployer-qa

Name: AWS_ROLE_ARN_PROD
Value: arn:aws:iam::123456789012:role/carl-deployer-prod

Name: AWS_REGION
Value: us-east-1
```

### Step 3: Deploy CARL

Now deploy CARL using OIDC authentication:

```bash
# Push to develop branch (triggers auto-deploy to dev)
git checkout develop
git push origin develop

# Watch deployment in GitHub Actions
# https://github.com/gnegelow-caylent/CARL/actions
```

GitHub Actions will:
1. Request temporary credentials from AWS STS
2. Assume the `carl-deployer-dev` role
3. Deploy CARL infrastructure
4. Credentials expire after 1 hour

**That's it!** No AWS access keys stored anywhere.

---

## Detailed Setup

### Prerequisites

- AWS CLI installed and configured with admin access
- Terraform >= 1.0 installed
- GitHub repository: `gnegelow-caylent/CARL`

### Customize OIDC Configuration

If you need to customize the OIDC setup, edit `carl-infrastructure/oidc/variables.tf`:

```hcl
variable "github_org" {
  description = "GitHub organization or username"
  type        = string
  default     = "gnegelow-caylent"  # Change if different
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "CARL"  # Change if different
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"  # Change if different
}
```

Or pass as variables:

```bash
terraform apply \
  -var="github_org=your-org" \
  -var="github_repo=your-repo" \
  -var="region=us-west-2"
```

### Multiple AWS Accounts

If you want separate AWS accounts for dev/qa/prod:

**Option 1: Deploy OIDC in each account**

```bash
# In dev account
aws configure --profile dev
cd carl-infrastructure/oidc
terraform init
terraform apply

# In qa account
aws configure --profile qa
terraform init
terraform apply

# In prod account
aws configure --profile prod
terraform init
terraform apply
```

**Option 2: Cross-account role assumption**

Deploy OIDC provider in one account (e.g., dev), then create cross-account roles in qa/prod that trust the dev account OIDC provider.

---

## How OIDC Works

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflow                   │
│                                                              │
│  1. Request JWT token from GitHub                            │
│     - Token includes: repo, branch, workflow info           │
│     - Token signed by GitHub                                 │
│                                                              │
│  2. Send token to AWS STS                                    │
│     - AssumeRoleWithWebIdentity                             │
│     - Role ARN: carl-deployer-dev                           │
│                                                              │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                         AWS STS                              │
│                                                              │
│  3. Verify JWT token                                         │
│     - Validates signature from GitHub                        │
│     - Checks token claims match trust policy                 │
│                                                              │
│  4. Issue temporary credentials                              │
│     - Access key ID                                          │
│     - Secret access key                                      │
│     - Session token                                          │
│     - Valid for 1 hour                                       │
│                                                              │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              GitHub Actions (with temp creds)                │
│                                                              │
│  5. Deploy CARL infrastructure                               │
│     - terraform apply                                        │
│     - Uses temporary credentials                             │
│     - Credentials expire after workflow completes            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Trust Policy

The IAM roles trust GitHub Actions from your specific repository:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:gnegelow-caylent/CARL:*"
        }
      }
    }
  ]
}
```

This allows:
- ✅ Any branch in `gnegelow-caylent/CARL`
- ❌ Other repositories
- ❌ Other organizations

### Permissions

The deployer roles have least-privilege access:

**What they CAN do:**
- Create/manage Lambda functions (carl-* prefix)
- Create/manage API Gateway (carl-* prefix)
- Create/manage DynamoDB tables (carl-* prefix)
- Create/manage S3 buckets (carl-* prefix)
- Create/manage IAM roles (carl-* prefix)
- Read Bedrock models
- Manage SSM parameters (carl-* prefix)

**What they CANNOT do:**
- Create/delete VPCs
- Modify other AWS resources
- Access other applications' resources
- Delete CloudTrail logs
- Modify AWS Organizations (unless needed for bootstrap)

---

## GitHub Secrets Summary

With OIDC, you only need **4 secrets** (no AWS access keys!):

### Required Secrets

```
AWS_ROLE_ARN_DEV     - ARN of the dev deployment role
AWS_ROLE_ARN_QA      - ARN of the qa deployment role
AWS_ROLE_ARN_PROD    - ARN of the prod deployment role
AWS_REGION           - AWS region (e.g., us-east-1)
```

### Optional Secrets (For Full Features)

```
SLACK_BOT_TOKEN_DEV           - Slack bot token for dev
SLACK_SIGNING_SECRET_DEV      - Slack signing secret for dev
SLACK_BOT_TOKEN_QA            - Slack bot token for qa
SLACK_SIGNING_SECRET_QA       - Slack signing secret for qa
SLACK_BOT_TOKEN_PROD          - Slack bot token for prod
SLACK_SIGNING_SECRET_PROD     - Slack signing secret for prod
GITHUB_TOKEN                  - GitHub PAT for feature deployment
SLACK_WEBHOOK_URL             - Webhook for deployment notifications
PROD_APPROVERS                - Comma-separated GitHub usernames
CARL_DEPLOYMENT_TOKEN         - Token for CARL to call back
```

---

## Terraform State Backend (Optional)

If you want to use S3 backend for Terraform state:

### Create State Backend

```bash
# Create S3 bucket for state
aws s3 mb s3://carl-tfstate-${AWS_ACCOUNT_ID}

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket carl-tfstate-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name carl-tfstate-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### Configure Backend in OIDC Module

Update `carl-infrastructure/oidc/variables.tf`:

```hcl
variable "terraform_state_bucket" {
  default = "carl-tfstate-123456789012"  # Your bucket name
}

variable "terraform_state_lock_table" {
  default = "carl-tfstate-locks"
}
```

Then re-apply OIDC module to grant state access to deployer roles.

---

## Troubleshooting

### "AccessDenied" when assuming role

**Symptom:**
```
Error: AssumeRoleWithWebIdentity failed: AccessDenied
```

**Solutions:**

1. **Verify OIDC provider exists:**
   ```bash
   aws iam list-open-id-connect-providers
   ```

2. **Check role trust policy:**
   ```bash
   aws iam get-role --role-name carl-deployer-dev --query 'Role.AssumeRolePolicyDocument'
   ```

3. **Verify GitHub repository is correct:**
   - Trust policy must match: `repo:gnegelow-caylent/CARL:*`
   - If you forked the repo, update OIDC variables

4. **Check role ARN in GitHub secrets:**
   - Must match exactly (including account ID)

### "InvalidIdentityToken" error

**Symptom:**
```
Error: token.actions.githubusercontent.com invalid identity token
```

**Solution:**

Ensure workflow has `id-token: write` permission:

```yaml
permissions:
  id-token: write
  contents: read
```

### Role has insufficient permissions

**Symptom:**
```
Error: AccessDenied: User is not authorized to perform: lambda:CreateFunction
```

**Solutions:**

1. **Check if resource naming matches:**
   - Roles can only create resources with `carl-*` prefix
   - Check Lambda function name starts with `carl-`

2. **Grant additional permissions:**
   ```bash
   # Edit the policy in oidc/main.tf
   # Add the missing permission
   # Re-apply
   cd carl-infrastructure/oidc
   terraform apply
   ```

### OIDC provider thumbprint mismatch

**Symptom:**
```
Error: OpenIDConnectProvider has invalid thumbprint
```

**Solution:**

This is rare but can happen if GitHub rotates certificates. Update OIDC provider:

```bash
cd carl-infrastructure/oidc
terraform apply -replace="aws_iam_openid_connect_provider.github"
```

---

## Security Best Practices

### 1. Use Separate AWS Accounts

Best practice: dev, qa, prod in separate AWS accounts

**Benefits:**
- Blast radius containment
- Independent billing
- Stricter prod controls

**Implementation:**
Deploy OIDC infrastructure in each account, or use cross-account roles.

### 2. Restrict by Branch

For production, restrict to main branch only:

Update OIDC trust policy in `carl-infrastructure/oidc/main.tf`:

```hcl
# For prod role only
condition {
  test     = "StringEquals"
  variable = "token.actions.githubusercontent.com:sub"
  values   = ["repo:gnegelow-caylent/CARL:ref:refs/heads/main"]
}
```

### 3. Enable CloudTrail

Monitor all API calls made by deployer roles:

```bash
aws cloudtrail create-trail \
  --name carl-deployer-audit \
  --s3-bucket-name my-cloudtrail-bucket \
  --is-multi-region-trail

aws cloudtrail start-logging --name carl-deployer-audit
```

### 4. Set Up AWS Budget Alerts

Prevent runaway costs:

```bash
aws budgets create-budget \
  --account-id 123456789012 \
  --budget '{
    "BudgetName": "CARL-Monthly-Budget",
    "BudgetLimit": {
      "Amount": "100",
      "Unit": "USD"
    },
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }'
```

### 5. Regular Access Review

Quarterly review of:
- Who can approve prod deployments (PROD_APPROVERS)
- IAM role permissions
- GitHub Actions logs for unusual activity

---

## Comparison: OIDC vs Access Keys

| Feature | OIDC | Access Keys |
|---------|------|-------------|
| **Setup Complexity** | Medium (one-time) | Easy |
| **Security** | ✅ Excellent | ⚠️ Poor |
| **Credential Rotation** | Automatic | Manual (90 days) |
| **Credential Lifetime** | 1 hour | Permanent |
| **Audit Trail** | CloudTrail | CloudTrail |
| **Blast Radius** | Limited | Full |
| **Cost** | Free | Free |
| **Recommended For** | Production | Never |

**Verdict:** Always use OIDC for production workloads.

---

## Migration from Access Keys

If you already deployed with access keys, migrate to OIDC:

### Step 1: Deploy OIDC Infrastructure

```bash
cd carl-infrastructure/oidc
terraform init
terraform apply
```

### Step 2: Add Role ARNs to GitHub

Add the new secrets (AWS_ROLE_ARN_*) but keep the old ones (AWS_ACCESS_KEY_ID_*) temporarily.

### Step 3: Test with Dev

Push to develop branch and verify deployment works with OIDC.

### Step 4: Remove Access Keys

Once verified, delete the old secrets:
- AWS_ACCESS_KEY_ID_DEV
- AWS_SECRET_ACCESS_KEY_DEV
- AWS_ACCESS_KEY_ID_QA
- AWS_SECRET_ACCESS_KEY_QA
- AWS_ACCESS_KEY_ID_PROD
- AWS_SECRET_ACCESS_KEY_PROD

### Step 5: Revoke IAM User Keys

```bash
aws iam delete-access-key --user-name carl-deployer-dev --access-key-id AKIAIOSFODNN7EXAMPLE
aws iam delete-user --user-name carl-deployer-dev
```

---

## Next Steps

After OIDC setup is complete:

1. ✅ Deploy CARL minimal core to dev
2. ✅ Configure Slack integration
3. ✅ Test `/carl hello` in Slack
4. ✅ Enable features as needed
5. ✅ Deploy to qa/prod

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

---

## Support

- **OIDC Issues:** Check AWS CloudTrail logs
- **Permissions Issues:** Review IAM role policies
- **GitHub Actions Issues:** Check workflow logs
- **General Deployment:** See DEPLOYMENT.md

---

**Last Updated:** 2026-01-27
