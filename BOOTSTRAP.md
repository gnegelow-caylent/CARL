# CARL Bootstrap Guide

Single-command setup for CARL with OIDC authentication and Terraform state management.

---

## TL;DR

```bash
./bootstrap.sh
# Follow prompts
# Add 4 GitHub secrets (script outputs the values)
# Deploy CARL
```

**That's it!** No manual OIDC setup, no DynamoDB lock tables, no hardcoded credentials.

---

## What the Bootstrap Script Does

The `bootstrap.sh` script automates the entire setup process:

### 1. Creates S3 Bucket for Terraform State
- Bucket name: `carl-tfstate-{AWS_ACCOUNT_ID}`
- Enables versioning (for state history)
- Enables encryption (AES256)
- Blocks public access
- Lifecycle policy (deletes old versions after 90 days)

**Modern approach:** Uses S3 native state locking (no DynamoDB needed!)

### 2. Deploys OIDC Infrastructure
- GitHub OIDC provider in AWS
- IAM roles for dev/qa/prod: `carl-deployer-{env}`
- Least-privilege policies
- Trust relationships configured for your GitHub repo

### 3. Configures Backend for CARL Core
- Creates backend configuration
- Points to S3 state bucket
- Ready for deployment

### 4. Verifies AWS Bedrock Model Access
- Checks if Claude models are available
- Provides instructions if model access needs to be enabled
- Ensures CARL can use AI features

### 5. Outputs GitHub Secrets
- Displays exactly what secrets to add
- Pre-formatted with actual ARNs
- Copy/paste ready

---

## Prerequisites

- AWS CLI installed and configured
- Terraform >= 1.0 installed
- Admin access to AWS account
- GitHub repository: `gnegelow-caylent/CARL`

---

## Quick Start

### Step 1: Configure (Optional)

Set these environment variables to customize:

```bash
export AWS_REGION=us-east-1           # Default: us-east-1
export GITHUB_ORG=gnegelow-caylent    # Default: gnegelow-caylent
export GITHUB_REPO=CARL               # Default: CARL
```

Or accept the defaults (recommended for initial setup).

### Step 2: Run Bootstrap

```bash
./bootstrap.sh
```

**What happens:**
```
🚀 CARL Bootstrap - Setting up OIDC and Terraform Backend

Configuration:
  AWS Account: 123456789012
  AWS Region: us-east-1
  GitHub Repo: gnegelow-caylent/CARL

Is this correct? (y/n) y

📦 Step 1: Creating S3 bucket for Terraform state...
  ✓ Created bucket: carl-tfstate-123456789012
  ✓ Enabled versioning
  ✓ Enabled encryption
  ✓ Blocked public access
  ✓ Added lifecycle policy

🔐 Step 2: Deploying OIDC authentication...
  ✓ Created backend configuration
  ✓ Created terraform.tfvars

  Deploying OIDC provider and IAM roles...
  [Terraform output...]

  ✓ OIDC infrastructure deployed!

⚙️  Step 3: Configuring CARL core backend...
  ✓ Created backend configuration for core

🤖 Step 4: Verifying AWS Bedrock model access...
  ✓ Bedrock access verified - Claude models available

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Bootstrap Complete!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 Next Step: Add these secrets to GitHub

[Displays 4 secrets with actual values...]
```

**Time:** ~2-3 minutes

### Step 3: Add AWS GitHub Secrets

The bootstrap script will output the AWS role ARNs. Add these to GitHub:

1. Go to: https://github.com/gnegelow-caylent/CARL/settings/secrets/actions
2. Click "New repository secret"
3. Add the 4 AWS secrets shown in bootstrap output:
   - `AWS_ROLE_ARN_DEV`
   - `AWS_ROLE_ARN_QA`
   - `AWS_ROLE_ARN_PROD`
   - `AWS_REGION`

Or use the GitHub CLI:
```bash
export GH_TOKEN=your_github_token
gh secret set AWS_ROLE_ARN_DEV -b "arn:aws:iam::ACCOUNT_ID:role/carl-deployer-dev" -R your-org/CARL
gh secret set AWS_ROLE_ARN_QA -b "arn:aws:iam::ACCOUNT_ID:role/carl-deployer-qa" -R your-org/CARL
gh secret set AWS_ROLE_ARN_PROD -b "arn:aws:iam::ACCOUNT_ID:role/carl-deployer-prod" -R your-org/CARL
gh secret set AWS_REGION -b "us-east-1" -R your-org/CARL
```

### Step 4: Configure Slack App

CARL requires a Slack app to function. Create one for each environment:

**Create Slack App:**
1. Go to: https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. App Name: `CARL-dev` (or `CARL` for single environment)
4. Workspace: Select your Slack workspace
5. Click "Create App"

**Configure OAuth & Permissions:**
1. Click "OAuth & Permissions" in the left sidebar
2. Scroll to "Redirect URLs" → Click "Add New Redirect URL"
3. Enter: `https://slack.com/oauth/redirect` (temporary, will update after deployment)
4. Click "Save URLs"
5. Scroll to "Scopes" → "Bot Token Scopes"
6. Add scope: `chat:write`
7. Scroll to top → Click "Install to Workspace"
8. Click "Allow"
9. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

**Get Signing Secret:**
1. Click "Basic Information" in the left sidebar
2. Scroll to "App Credentials"
3. Copy the "Signing Secret"

**Add Slack Secrets to GitHub:**
```bash
export GH_TOKEN=your_github_token
gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-your-token" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_DEV -b "your-signing-secret" -R your-org/CARL
```

For multiple environments, repeat for `_QA` and `_PROD` suffixes.

### Step 5: Deploy CARL

```bash
git checkout -b develop
git push origin develop
```

Or use GitHub UI:
1. Go to Actions tab
2. Select "Deploy CARL Core"
3. Click "Run workflow"
4. Select branch: develop
5. Click "Run workflow"

GitHub Actions will use OIDC to assume the deployment role and deploy CARL!

---

## What Gets Created in AWS

### S3 Bucket
```
Name: carl-tfstate-{ACCOUNT_ID}
Purpose: Terraform state storage
Features:
  - Versioning enabled
  - Encryption enabled (AES256)
  - Public access blocked
  - Lifecycle: Delete old versions after 90 days
Cost: ~$0.50/month
```

### OIDC Provider
```
Provider: token.actions.githubusercontent.com
Purpose: Trust GitHub Actions
ARN: arn:aws:iam::{ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com
Cost: Free
```

### IAM Roles (3)
```
carl-deployer-dev
carl-deployer-qa
carl-deployer-prod

Purpose: GitHub Actions assumes these roles
Permissions: Create/manage CARL resources only (carl-* prefix)
Trust: Only your GitHub repository
Cost: Free
```

**Total Bootstrap Cost:** ~$0.50/month (S3 bucket only)

---

## Modern vs Legacy Approaches

### Modern Approach (This Script) ✅

```bash
./bootstrap.sh
# Creates S3 bucket with native locking
# Deploys OIDC automatically
# Outputs secrets
# Time: 2-3 minutes
```

**Benefits:**
- ✅ Single command
- ✅ No DynamoDB lock table needed
- ✅ S3 native state locking
- ✅ OIDC configured automatically
- ✅ No hardcoded credentials

### Legacy Approach ❌

```bash
# Manually create S3 bucket
aws s3 mb s3://my-state-bucket

# Manually create DynamoDB lock table
aws dynamodb create-table --table-name tfstate-locks ...

# Manually deploy OIDC
cd carl-infrastructure/oidc
terraform init
terraform apply

# Manually configure backends
# ... lots of manual steps
```

**Drawbacks:**
- ❌ 10+ manual commands
- ❌ Requires DynamoDB lock table
- ❌ Easy to make mistakes
- ❌ Takes 15-20 minutes

---

## S3 State Locking (No DynamoDB Needed!)

Modern Terraform (v1.0+) with S3 backend supports **native state locking** without DynamoDB:

```hcl
terraform {
  backend "s3" {
    bucket = "carl-tfstate-123456789012"
    key    = "carl-core/terraform.tfstate"
    region = "us-east-1"
  }
}
```

**How it works:**
1. Terraform creates a lock file in S3: `{key}.tflock`
2. Lock uses S3 object versioning and consistency
3. Automatic cleanup on lock release
4. No DynamoDB table needed
5. No extra cost

**Why this is better:**
- ✅ Simpler (one service instead of two)
- ✅ Cheaper (no DynamoDB costs)
- ✅ More reliable (fewer moving parts)
- ✅ Easier to troubleshoot

---

## Multiple AWS Accounts

If you want separate AWS accounts for dev/qa/prod:

### Option 1: Bootstrap in Each Account

```bash
# In dev account
aws configure --profile dev
export AWS_PROFILE=dev
./bootstrap.sh

# In qa account
aws configure --profile qa
export AWS_PROFILE=qa
./bootstrap.sh

# In prod account
aws configure --profile prod
export AWS_PROFILE=prod
./bootstrap.sh
```

Each account gets:
- Its own S3 state bucket
- Its own OIDC provider
- Its own deployer roles

### Option 2: Single Account with Cross-Account Roles

Bootstrap in one account, manually create cross-account trust relationships in others.

**Recommendation:** Use Option 1 for simplicity.

---

## Troubleshooting

### "Bucket already exists"

**Symptom:**
```
BucketAlreadyExists: The requested bucket name is not available
```

**Solution:**

Someone else owns a bucket with that name. The script uses your account ID to make it unique, so this is rare. If it happens:

```bash
export STATE_BUCKET_SUFFIX="-mycompany"
# Bucket becomes: carl-tfstate-{ACCOUNT_ID}-mycompany
./bootstrap.sh
```

### "Access Denied" during OIDC deployment

**Symptom:**
```
Error: creating IAM OIDC Provider: AccessDenied
```

**Solution:**

Your AWS credentials don't have permission to create OIDC providers. Ensure you have:
- `iam:CreateOpenIDConnectProvider`
- `iam:CreateRole`
- `iam:CreatePolicy`

Or use admin credentials for initial bootstrap.

### "OIDC provider already exists"

**Symptom:**
```
Error: OIDC Provider already exists
```

**Solution:**

OIDC provider already created (maybe from previous run). This is fine! Terraform will use the existing provider. Just continue.

### Bootstrap fails midway

**Symptom:**

Script exits with error after creating S3 bucket but before OIDC deployment.

**Solution:**

Run bootstrap again. Script is idempotent - won't recreate existing resources. Safe to re-run.

### Wrong GitHub org/repo

**Symptom:**

Bootstrap completes but GitHub Actions fails with "AccessDenied" when assuming role.

**Solution:**

OIDC trust policy has wrong repo. Fix it:

```bash
cd carl-infrastructure/oidc

# Update terraform.tfvars
cat > terraform.tfvars <<EOF
github_org = "correct-org"
github_repo = "correct-repo"
region = "us-east-1"
EOF

# Re-apply
terraform apply
```

---

## Cost Breakdown

| Resource | Cost |
|----------|------|
| S3 bucket (state) | ~$0.50/month |
| OIDC provider | Free |
| IAM roles (3) | Free |
| **Total** | **~$0.50/month** |

**Compare to DynamoDB approach:**
- S3 bucket: $0.50/month
- DynamoDB table: $0.25/month (on-demand)
- **Total: $0.75/month** (50% more expensive)

---

## Security

### What the Bootstrap Creates

✅ **S3 Bucket:**
- Encrypted at rest (AES256)
- Versioning enabled
- Public access blocked
- No public bucket policies

✅ **OIDC Provider:**
- Trusts only GitHub Actions
- Validates JWT tokens
- Short-lived credentials (1 hour)

✅ **IAM Roles:**
- Least-privilege policies
- Can only manage carl-* resources
- Trust only your GitHub repo
- No wildcard permissions

### What It Doesn't Do

❌ Create IAM users (uses OIDC instead)
❌ Store credentials anywhere
❌ Expose any resources publicly
❌ Grant admin permissions

---

## Cleanup

To remove all bootstrap resources:

```bash
# Delete OIDC infrastructure
cd carl-infrastructure/oidc
terraform destroy

# Delete S3 state bucket (WARNING: destroys state history!)
aws s3 rb s3://carl-tfstate-${AWS_ACCOUNT_ID} --force
```

**Warning:** Only do this if you're completely removing CARL. Otherwise you'll lose your infrastructure state!

---

## Next Steps

After bootstrap completes:

1. ✅ Add GitHub secrets (script outputs values)
2. ✅ Deploy CARL to dev: `git push origin develop`
3. ✅ Test in Slack: `/carl hello`
4. ✅ Enable features: `/carl enable monitoring`
5. ✅ Deploy to qa/prod when ready

---

## Documentation

- **OIDC_SETUP.md** - Deep dive into OIDC authentication
- **DEPLOYMENT.md** - Complete deployment guide
- **COST_OPTIMIZATION.md** - Cost saving strategies
- **.github/WORKFLOWS.md** - CI/CD pipeline details

---

## Comparison: Bootstrap vs Manual

| Step | Bootstrap Script | Manual Process |
|------|------------------|----------------|
| Create S3 bucket | ✅ Automated | ❌ 5 commands |
| Configure bucket | ✅ Automated | ❌ 4 commands |
| Deploy OIDC | ✅ Automated | ❌ terraform init/apply |
| Configure backend | ✅ Automated | ❌ Manual editing |
| Output secrets | ✅ Automated | ❌ Copy from terraform output |
| **Total time** | **2-3 minutes** | **15-20 minutes** |
| **Commands** | **1** | **15+** |
| **Error prone** | **Low** | **High** |

---

**Recommendation:** Always use `./bootstrap.sh` for new deployments. It's faster, safer, and follows modern best practices.

---

**Last Updated:** 2026-01-27
