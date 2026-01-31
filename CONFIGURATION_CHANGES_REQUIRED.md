# CARL - Required Configuration Changes

**Quick Reference Guide for Deployment**

This document lists all files that need to be updated with your specific AWS account and integration details before deploying CARL.

---

## Critical Changes (Must Complete Before Deployment)

### 1. Terraform Backend Configuration

**File**: `carl-infrastructure/core/backend.tf`

```hcl
# CHANGE THIS LINE:
bucket = "carl-terraform-state-CHANGEME"

# TO YOUR AWS ACCOUNT ID:
bucket = "carl-terraform-state-123456789012"  # Replace with your account ID
```

**How to get your AWS Account ID**:
```bash
aws sts get-caller-identity --query Account --output text
```

---

### 2. GitHub Workflow Files

**Files to Update**:
- `.github/workflows/deploy-core.yml`
- `.github/workflows/deploy-features.yml`
- `.github/workflows/integration-tests.yml`

**Change**:
```yaml
# CURRENT:
env:
  AWS_ACCOUNT_ID: 123456789012  # PLACEHOLDER

# CHANGE TO:
env:
  AWS_ACCOUNT_ID: YOUR_ACTUAL_ACCOUNT_ID
```

**Find and replace**:
```bash
# From carl root directory:
cd /Users/gnegelow/Documents/carl
grep -r "123456789012" .github/workflows/
# Replace each occurrence with your actual AWS account ID
```

---

### 3. Terraform Variables

**File**: `carl-infrastructure/core/variables.tf`

Review and confirm these defaults:

```hcl
variable "aws_region" {
  default = "us-east-1"  # Change if using different region
}

variable "environment" {
  default = "dev"  # Change to "prod" for production
}

variable "tags" {
  default = {
    Environment = "dev"  # Match environment variable
    Owner       = "your-email@example.com"  # Add your email
  }
}
```

---

### 4. Create Environment Configuration File

**File**: `carl-infrastructure/environments/dev/terraform.tfvars`

**Create this file with**:

```hcl
# AWS Configuration
aws_region  = "us-east-1"
environment = "dev"

# GitHub Configuration
github_repo = "your-username/carl"  # REQUIRED: Update with your GitHub username

# Tags
tags = {
  Project     = "CARL"
  ManagedBy   = "Terraform"
  Environment = "dev"
  Owner       = "your-email@example.com"  # REQUIRED: Update with your email
}
```

---

### 5. GitHub OIDC Trust Policy

**File**: Create `/tmp/github-trust-policy.json` during setup

**Update this line**:
```json
"token.actions.githubusercontent.com:sub": "repo:YOUR_USERNAME/carl:*"
```

**Change to**:
```json
"token.actions.githubusercontent.com:sub": "repo:your-actual-username/carl:*"
```

---

## Integration-Specific Changes

### Slack Configuration

**After creating Slack app, store credentials**:

```bash
# Replace with your actual values
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_SIGNING_SECRET="your-signing-secret"

# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name carl/slack/credentials \
  --secret-string "{
    \"bot_token\": \"${SLACK_BOT_TOKEN}\",
    \"signing_secret\": \"${SLACK_SIGNING_SECRET}\"
  }" \
  --region us-east-1
```

**Update Slack App URLs after deployment**:
1. Get API Gateway URL: `terraform output -raw api_gateway_url`
2. Update in Slack App:
   - Slash Commands → Request URL
   - Event Subscriptions → Request URL
   - Interactivity → Request URL
3. Append `/slack/events` to the URL

---

### Jira Configuration

**After generating Jira API token, store credentials**:

```bash
# Replace with your actual values
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_USER="your-email@example.com"
export JIRA_API_TOKEN="your-api-token"
export JIRA_PROJECT="CARL"

# Store in AWS Secrets Manager
aws secretsmanager create-secret \
  --name carl/jira/credentials \
  --secret-string "{
    \"url\": \"${JIRA_URL}\",
    \"user\": \"${JIRA_USER}\",
    \"api_token\": \"${JIRA_API_TOKEN}\",
    \"project\": \"${JIRA_PROJECT}\"
  }" \
  --region us-east-1
```

---

### GitHub Secrets

**Add these secrets to your GitHub repository**:

Navigate to: `Settings → Secrets and variables → Actions → New repository secret`

```
AWS_REGION = us-east-1
AWS_ACCOUNT_ID = <your-aws-account-id>
AWS_ROLE_ARN = arn:aws:iam::<account-id>:role/GitHubActionsCARL
TERRAFORM_STATE_BUCKET = carl-terraform-state-<account-id>
```

---

## Files That DON'T Need Changes

The following files are already configured correctly and don't require changes:

- `carl-app/src/**/*.py` - Application code
- `carl-infrastructure/modules/**/*.tf` - Module definitions
- `.github/workflows/*.yml` - Workflow logic (except AWS account ID)
- `README.md` - Documentation
- All knowledge base files in `carl-app/src/knowledge/`

---

## Validation Commands

After making changes, validate your configuration:

### 1. Check AWS Account ID is Updated

```bash
# Search for placeholder account ID
cd /Users/gnegelow/Documents/carl
grep -r "123456789012" . --exclude-dir=.git

# Should return NO results (or only in documentation)
```

### 2. Check Backend Configuration

```bash
# Verify backend bucket name
grep -A 5 "backend \"s3\"" carl-infrastructure/core/backend.tf

# Should show your actual bucket name, not CHANGEME
```

### 3. Check GitHub Username

```bash
# Verify GitHub repo is set
grep -r "your-username/carl" .

# Replace all occurrences with your actual username
```

### 4. Validate Terraform Configuration

```bash
cd carl-infrastructure/core
terraform init
terraform validate

# Should return: Success! The configuration is valid.
```

### 5. Check Secrets Are Created

```bash
# Verify Slack credentials
aws secretsmanager describe-secret --secret-id carl/slack/credentials

# Verify Jira credentials
aws secretsmanager describe-secret --secret-id carl/jira/credentials
```

---

## Configuration Checklist

Use this checklist to track your changes:

- [ ] **Terraform Backend**
  - [ ] Updated `carl-infrastructure/core/backend.tf` with bucket name
  - [ ] Bucket name uses your AWS account ID
  - [ ] No "CHANGEME" placeholders remain

- [ ] **GitHub Workflows**
  - [ ] Updated `.github/workflows/deploy-core.yml`
  - [ ] Updated `.github/workflows/deploy-features.yml`
  - [ ] Updated `.github/workflows/integration-tests.yml`
  - [ ] All files use your actual AWS account ID

- [ ] **Terraform Variables**
  - [ ] Reviewed `carl-infrastructure/core/variables.tf`
  - [ ] Updated region if not using us-east-1
  - [ ] Updated environment if not using dev
  - [ ] Added your email to tags

- [ ] **Environment Configuration**
  - [ ] Created `carl-infrastructure/environments/dev/terraform.tfvars`
  - [ ] Updated GitHub repo with your username
  - [ ] Updated owner email

- [ ] **Slack Integration**
  - [ ] Created Slack app
  - [ ] Stored credentials in Secrets Manager
  - [ ] Ready to update URLs after deployment

- [ ] **Jira Integration**
  - [ ] Generated Jira API token
  - [ ] Stored credentials in Secrets Manager
  - [ ] Verified Jira project exists

- [ ] **GitHub Repository**
  - [ ] Created GitHub repository
  - [ ] Added remote to local git
  - [ ] Added GitHub secrets
  - [ ] Set up OIDC provider

- [ ] **Validation**
  - [ ] No placeholder values remain
  - [ ] Terraform validate passes
  - [ ] Secrets created in AWS
  - [ ] Ready to deploy

---

## Quick Start Commands

After completing all configuration changes:

```bash
# 1. Verify configuration
cd /Users/gnegelow/Documents/carl/carl-infrastructure/core
terraform init
terraform validate

# 2. Review plan
terraform plan -out=tfplan

# 3. Deploy
terraform apply tfplan

# 4. Get API Gateway URL
terraform output -raw api_gateway_url

# 5. Update Slack app with URL
echo "Update Slack app with: $(terraform output -raw api_gateway_url)/slack/events"

# 6. Test deployment
# In Slack: /carl help
```

---

## Common Mistakes to Avoid

1. **Forgetting to replace placeholders**
   - Search for "CHANGEME", "your-username", "123456789012"
   - Replace ALL occurrences

2. **Mismatched AWS regions**
   - Use the same region throughout (recommend us-east-1)
   - Bedrock is not available in all regions

3. **Not updating Slack app URLs**
   - Must update AFTER deploying API Gateway
   - URLs must end with `/slack/events`

4. **Incorrect GitHub repo format**
   - Format: `username/repository-name`
   - Don't include "https://github.com/"

5. **Missing GitHub secrets**
   - All 4 secrets must be added
   - Values must match your AWS configuration

6. **Not enabling Bedrock model access**
   - Must enable Claude 3.5 Sonnet AND Haiku
   - Wait 5 minutes after enabling

---

## Need Help?

- **Deployment Guide**: See `DEPLOYMENT_SETUP_GUIDE.md` for complete instructions
- **Troubleshooting**: See `TROUBLESHOOTING.md` for common issues
- **Architecture**: See `ARCHITECTURE.md` for technical details
- **Slack Commands**: See `SLACK_COMMANDS.md` for usage examples

---

**Last Updated**: 2026-01-30
