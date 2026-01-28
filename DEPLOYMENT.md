# CARL Deployment Guide

Complete guide for deploying CARL (Cloud Automated Risk & Compliance Logic).

## Table of Contents
- [Quick Start (5 minutes)](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Cost Breakdown](#cost-breakdown)
- [Deployment Options](#deployment-options)
- [CI/CD Setup](#cicd-setup)
- [Feature Modules](#feature-modules)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

Deploy CARL in ~5 minutes using the automated bootstrap script:

### Prerequisites

**AWS Requirements:**
- AWS Account with admin access
- AWS CLI configured (`aws configure`)
- Terraform >= 1.0 installed
- **AWS Bedrock model access enabled** (Claude 3.5 Sonnet and Claude 3 Haiku)

**Slack Requirements:**
- Slack workspace with admin access
- Slack app created (see [SLACK_SETUP.md](./SLACK_SETUP.md))

**GitHub Requirements:**
- GitHub repository with CARL code
- GitHub Actions enabled

### 1. Run Bootstrap Script

```bash
./bootstrap.sh
```

This automated script:
- ✅ Creates S3 bucket for Terraform state
- ✅ Deploys OIDC provider (no hardcoded credentials!)
- ✅ Creates IAM roles: `carl-deployer-dev`, `carl-deployer-qa`, `carl-deployer-prod`
- ✅ Verifies Bedrock model access
- ✅ Outputs GitHub secrets to add

**Bootstrap completes in ~2-3 minutes**

### 2. Add GitHub Secrets

Add the 6 secrets output by bootstrap:

**AWS Secrets (4):**
```bash
export GH_TOKEN=your_github_token
gh secret set AWS_ROLE_ARN_DEV -b "arn:aws:iam::ACCOUNT:role/carl-deployer-dev"
gh secret set AWS_ROLE_ARN_QA -b "arn:aws:iam::ACCOUNT:role/carl-deployer-qa"
gh secret set AWS_ROLE_ARN_PROD -b "arn:aws:iam::ACCOUNT:role/carl-deployer-prod"
gh secret set AWS_REGION -b "us-east-1"
```

**Slack Secrets (2):**
```bash
gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-your-bot-token"
gh secret set SLACK_SIGNING_SECRET_DEV -b "your-signing-secret"
```

### 3. Deploy via GitHub Actions

```bash
git checkout -b develop
git push origin develop
```

GitHub Actions will:
- Authenticate via OIDC (no credentials stored!)
- Deploy CARL infrastructure via Terraform
- Create Lambda functions, API Gateway, DynamoDB tables
- Configure IAM roles and policies

**Deployment takes ~5-10 minutes**

### 4. Configure Slack Integration

After deployment, get the API Gateway URL:

```bash
cd carl-infrastructure/core
terraform output slack_webhook_url
```

Example output: `https://bz9vbzlh56.execute-api.us-east-1.amazonaws.com/slack`

**IMPORTANT:** Follow the complete, verified Slack setup guide:

📖 **See [SLACK_SETUP.md](./SLACK_SETUP.md) for step-by-step instructions**

The guide includes:
- Slack app creation and OAuth configuration
- Event Subscriptions and slash command setup
- All verified fixes and troubleshooting
- Testing checklist

**Quick summary:**
1. Create Slack app with required OAuth scopes
2. Set Event Subscriptions URL to your API endpoint (`/slack`)
3. Create `/carl` slash command with same URL
4. Install app to workspace

### 5. Test CARL

In Slack:
```
/carl help
/carl status
/carl architect how do I build a VPC?
```

CARL is now live! 🎉

---

## Detailed Guides

- **[BOOTSTRAP.md](./BOOTSTRAP.md)** - Complete bootstrap guide with troubleshooting
- **[SLACK_SETUP.md](./SLACK_SETUP.md)** - Step-by-step Slack app setup
- **[OIDC_SETUP.md](./OIDC_SETUP.md)** - Deep dive into OIDC authentication
- **[.github/WORKFLOWS.md](./.github/WORKFLOWS.md)** - CI/CD pipeline details

---

## Architecture Overview

### Minimal Core (What Gets Deployed First)

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Account                               │
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │  API Gateway │────────▶│    Lambda    │                  │
│  │  (HTTP API)  │         │  (CARL Core) │                  │
│  └──────────────┘         └──────┬───────┘                  │
│         ▲                        │                           │
│         │                        │                           │
│         │                        ▼                           │
│  ┌──────────────┐        ┌──────────────┐                   │
│  │    Slack     │        │  DynamoDB    │                   │
│  │              │        │  (Config)    │                   │
│  └──────────────┘        └──────────────┘                   │
│                                 │                            │
│                                 ▼                            │
│                          ┌──────────────┐                    │
│                          │   Bedrock    │                    │
│                          │  (Claude)    │                    │
│                          └──────────────┘                    │
└──────────────────────────────────────────────────────────────┘

Cost: ~$10-20/month
```

**Components:**
- **API Gateway HTTP API**: Handles Slack requests ($1/million requests)
- **Lambda (512 MB)**: CARL's brain, talks to Bedrock ($5-10/month)
- **DynamoDB Config Table**: Stores feature flags, user preferences (on-demand, ~$1-3/month)
- **Bedrock Claude Haiku**: AI model for responses ($3-5/month)
- **CloudWatch Logs**: 7-day retention (~$1/month)
- **SSM Parameter Store**: Slack secrets (free)

### Feature Modules (Deploy On-Demand)

After initial setup, CARL asks what you want to do:

**Option 1: Monitor Existing Infrastructure**
```
Adds:
- Security Hub integration
- Scanning Lambdas
- DynamoDB tables (findings, evidence, exceptions, drift)
- S3 buckets (evidence, reports)
- CloudWatch scheduled scans

Additional Cost: +$30-50/month
```

**Option 2: Build Compliant Infrastructure**
```
Adds:
- Organizations bootstrap automation
- Identity Center setup
- Security baseline deployment
- Terraform code generation

Additional Cost: +$20-30/month
```

**Option 3: Architecture Advisor Only**
```
Adds: Nothing (use core only)

Additional Cost: $0 (stays at $10-20/month)
```

**Option 4: Full Platform**
```
Adds: Everything from Options 1 & 2 + advanced features

Additional Cost: +$65-130/month
Total: $75-150/month
```

---

## Cost Breakdown

### Minimal Core (~$10-20/month)

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 10K invocations, 512 MB, 5s avg | $5-10 |
| API Gateway (HTTP) | 1K requests | $1-2 |
| DynamoDB (on-demand) | 100K reads, 10K writes | $1-3 |
| Bedrock (Haiku) | 200K input tokens, 100K output | $3-5 |
| CloudWatch Logs | 100 MB, 7-day retention | $0-1 |
| SSM Parameter Store | 2 parameters | $0 (free) |
| **TOTAL** | | **$10-21** |

### Cost Optimization Features

**1. Model Selection (Saves 85% on AI costs)**
```python
# Simple queries → Haiku ($0.25/$1.25 per 1M tokens)
commands = ["status", "findings", "evidence", "drift"]

# Complex queries → Sonnet ($3/$15 per 1M tokens)
commands = ["architect", "recommend", "foundation"]
```

**2. Response Caching (Saves 70% on API calls)**
```python
# Cache common responses for 30 minutes
# Reduces Bedrock API calls by ~70%
BEDROCK_CACHE_TTL_SECONDS = 1800
```

**3. On-Demand DynamoDB (Saves vs. Provisioned)**
- Only pay for what you use
- No wasted capacity
- Auto-scales with load

**4. HTTP API vs REST API (Saves 70%)**
- HTTP API: $1.00 per million requests
- REST API: $3.50 per million requests

**5. 7-Day Log Retention (Saves vs. 30-day)**
- Minimal cost for logs
- Increase to 30 days for prod if needed

---

## Deployment Options

### Option A: Quick Deploy (Automated Script)

**Best for:** First-time users, simple setups

```bash
./setup-core.sh
```

Asks 3 questions, deploys in 5 minutes.

### Option B: Manual Terraform

**Best for:** Existing Terraform workflows, customization

```bash
cd carl-infrastructure/core

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
environment = "dev"
region      = "us-east-1"
EOF

# Deploy
terraform init
terraform plan
terraform apply
```

### Option C: GitHub Actions CI/CD

**Best for:** Team deployments, multiple environments

See [CI/CD Setup](#cicd-setup) below.

---

## CI/CD Setup

### GitHub Actions Workflow

CARL includes a complete CI/CD pipeline:

```
develop branch push → Auto-deploy to dev → Manual approval → Deploy to qa
main branch push    → Manual approval → Deploy to prod
```

### Setup Steps

**1. Configure GitHub Secrets**

Add these secrets in your repository settings:

```
Development:
- AWS_ACCESS_KEY_ID_DEV
- AWS_SECRET_ACCESS_KEY_DEV
- SLACK_BOT_TOKEN_DEV
- SLACK_SIGNING_SECRET_DEV

QA:
- AWS_ACCESS_KEY_ID_QA
- AWS_SECRET_ACCESS_KEY_QA
- SLACK_BOT_TOKEN_QA
- SLACK_SIGNING_SECRET_QA

Production:
- AWS_ACCESS_KEY_ID_PROD
- AWS_SECRET_ACCESS_KEY_PROD
- SLACK_BOT_TOKEN_PROD
- SLACK_SIGNING_SECRET_PROD
- PROD_APPROVERS (comma-separated GitHub usernames)
- SLACK_WEBHOOK_URL (for deployment notifications)
```

**2. Create GitHub Environments**

In your repository settings, create three environments:
- **dev**: No protection rules (auto-deploy)
- **qa**: Require 1 reviewer approval
- **prod**: Require 2 reviewer approvals + restrict to main branch

**3. Push to Trigger Deployment**

```bash
# Deploy to dev
git checkout develop
git commit -m "Update CARL core"
git push origin develop

# Deploy to prod (after testing)
git checkout main
git merge develop
git push origin main
```

**4. Monitor Deployment**

- Watch GitHub Actions tab for deployment progress
- Approve deployments in GitHub UI when prompted
- Check Slack for deployment notifications (prod only)

### Deployment Pipeline Features

✅ **Automatic Validation**
- Terraform format check
- Terraform validate
- Python linting (pylint)
- Security scanning (Trivy)

✅ **Environment Isolation**
- Separate AWS accounts per environment
- Separate Slack workspaces (optional)
- Independent Terraform state files

✅ **Cost Safety**
- Terraform plan on PR (shows cost changes)
- Manual approval for qa/prod
- Deployment summary in PR comments

✅ **Rollback Support**
- Revert git commit
- Push to trigger redeployment
- Terraform state preserved

---

## Feature Modules

After core deployment, enable features as needed.

### Enable Monitoring

Adds infrastructure scanning and compliance reporting.

**Via Slack:**
```
/carl enable monitoring
```

**Manually:**
```bash
cd carl-infrastructure/features
terraform apply -target=module.monitoring
```

**What it deploys:**
- DynamoDB tables: findings, evidence, exceptions, drift
- S3 buckets: evidence, reports
- Lambda functions: scanner, evidence collector
- CloudWatch rules: scheduled scans
- IAM roles: Security Hub access

**Cost:** +$30-50/month

### Enable Bootstrap

Adds AWS Organizations and security baseline automation.

**Via Slack:**
```
/carl enable bootstrap
```

**Manually:**
```bash
cd carl-infrastructure/features
terraform apply -target=module.bootstrap
```

**What it deploys:**
- Lambda functions: Organizations, Identity Center, security services
- S3 bucket: bootstrap state
- IAM roles: Organizations admin access
- CloudWatch logs: bootstrap execution logs

**Cost:** +$20-30/month

### Enable Reporting

Adds advanced compliance reporting and evidence collection.

**Via Slack:**
```
/carl enable reporting
```

**Cost:** +$15-25/month

### Enable Foundation Builder

Adds guided infrastructure creation wizard.

**Via Slack:**
```
/carl enable foundation
```

**Cost:** +$10-20/month

---

## Slack Configuration

**IMPORTANT:** Slack integration has been fully tested and verified working.

📖 **Complete guide:** [SLACK_SETUP.md](./SLACK_SETUP.md)

The SLACK_SETUP.md guide includes:
- ✅ Verified working step-by-step instructions
- ✅ All required OAuth scopes and permissions
- ✅ Event Subscriptions and slash command configuration
- ✅ Comprehensive troubleshooting for common issues
- ✅ Testing checklist to verify everything works

### Quick Reference

**Required OAuth Scopes:**
- `chat:write` - Send messages
- `commands` - Respond to slash commands
- `users:read` - Read user information

**Slash Command:**
- Command: `/carl`
- Request URL: `<your-api-endpoint>/slack` (from `terraform output slack_webhook_url`)

**Event Subscriptions:**
- Request URL: Same as slash command URL
- Bot events: `app_mention`, `message.channels`, `message.im`

**Credentials needed:**
- Bot Token (starts with `xoxb-`) → Store in GitHub Secrets as `SLACK_BOT_TOKEN_DEV`
- Signing Secret → Store in GitHub Secrets as `SLACK_SIGNING_SECRET_DEV`

For complete setup instructions with troubleshooting, see [SLACK_SETUP.md](./SLACK_SETUP.md).

---

## Troubleshooting

### Common Issues

**Issue: Terraform state locked**
```
Error: Error acquiring the state lock
```

**Solution:**
```bash
# Remove lock from DynamoDB
aws dynamodb delete-item \
  --table-name carl-tfstate-locks \
  --key '{"LockID": {"S": "carl-core/dev/terraform.tfstate-md5"}}'
```

---

**Issue: Lambda timeout**
```
Task timed out after 30.00 seconds
```

**Solution:**
```hcl
# Increase timeout in variables.tf
lambda_timeout = 60  # Increase to 60 seconds
```

---

**Issue: Bedrock access denied**
```
AccessDeniedException: Could not access model
```

**Solution:**
1. Enable Bedrock in AWS Console
2. Request model access for Claude Haiku and Sonnet
3. Wait 5-10 minutes for activation

---

**Issue: High Bedrock costs**
```
Bill shows $50 for Bedrock last month
```

**Solution:**
```python
# Ensure you're using Haiku for simple queries
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"

# Enable caching
BEDROCK_ENABLE_CACHING = "true"
BEDROCK_CACHE_TTL_SECONDS = "1800"
```

---

**Issue: Slack webhook fails**
```
Error: Verification token mismatch
```

**Solution:**
1. Check Slack signing secret is correct
2. Verify API Gateway endpoint in Slack app settings
3. Test with: `curl -X POST <api-endpoint>/health`

---

### Debugging

**View Lambda logs:**
```bash
aws logs tail /aws/lambda/carl-dev-api --follow
```

**Test Lambda locally:**
```bash
cd carl-app
python -c "from handlers.slack_router import lambda_handler; \
  print(lambda_handler({'body': '{}'}, {}))"
```

**Check DynamoDB config:**
```bash
aws dynamodb scan --table-name carl-dev-config
```

**Verify Bedrock access:**
```bash
aws bedrock list-foundation-models --region us-east-1
```

---

## Support

- **Documentation:** https://github.com/your-org/carl/tree/main/docs
- **Issues:** https://github.com/your-org/carl/issues
- **Slack:** #carl-support

---

## What's Next?

After successful deployment:

1. **Test CARL**: `/carl hello` in Slack
2. **Complete onboarding**: Choose features you need
3. **Explore patterns**: `/carl patterns vpc`
4. **Get recommendations**: `/carl architect "What database should I use?"`
5. **Enable more features**: `/carl enable monitoring`

Enjoy CARL! 🚀
