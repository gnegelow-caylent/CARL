# CARL Automated Installation

**Complete CARL deployment in 15-20 minutes with minimal user interaction.**

---

## Overview

The automated installer handles:
- ✅ AWS service enablement (Security Hub, GuardDuty, Config, Bedrock)
- ✅ Terraform backend creation (S3 + DynamoDB)
- ✅ Configuration file updates (no manual editing)
- ✅ Secrets storage (Slack, GitHub, Jira)
- ✅ Core infrastructure deployment
- ✅ Post-deployment validation
- ✅ Rollback capability

---

## Prerequisites

### 1. Required Software

Install these tools before running the installer:

```bash
# macOS
brew install terraform awscli python3 jq git

# Linux (Ubuntu/Debian)
sudo apt-get install -y terraform awscli python3 jq git

# Verify installation
terraform version  # Should be 1.0+
aws --version      # Should be 2.0+
python3 --version  # Should be 3.12+
jq --version
git --version
```

### 2. AWS Credentials

Configure AWS CLI with credentials:

```bash
aws configure
# AWS Access Key ID: [your-access-key]
# AWS Secret Access Key: [your-secret-key]
# Default region: us-east-1
# Default output format: json

# Verify
aws sts get-caller-identity
# Should return your account ID and user ARN
```

### 3. Required Credentials

**Slack (REQUIRED)**
- Create Slack app: https://api.slack.com/apps
- Get Bot User OAuth Token (starts with `xoxb-`)
- Get Signing Secret from Basic Information page

**GitHub App (REQUIRED)**
- Create GitHub App for secure, short-lived tokens (not Personal Access Token)
- Why GitHub App? Tokens expire after 1 hour, not tied to user, better audit trail
- Run `./scripts/setup-github-app.sh` for guided setup
- See `GITHUB_APP_SETUP.md` for detailed instructions
- Create repository for generated infrastructure: `carl-infrastructure-deployments`

**Jira (OPTIONAL)**
- Generate API Token: https://id.atlassian.com/manage-profile/security/api-tokens
- Note your Jira URL and project key

---

## Quick Start (Minimal Install)

### Step 1: Set Required Environment Variables

```bash
# Navigate to CARL directory
cd /path/to/carl

# Slack credentials (REQUIRED)
export SLACK_BOT_TOKEN=xoxb-your-bot-token-here
export SLACK_SIGNING_SECRET=your-signing-secret-here

# GitHub App credentials (REQUIRED)
# First, run: ./scripts/setup-github-app.sh to create GitHub App
export GITHUB_APP_ID=123456
export GITHUB_INSTALLATION_ID=789012
export GITHUB_PRIVATE_KEY_PATH=/path/to/app-private-key.pem
export GITHUB_ORG=your-github-org-or-username
export GITHUB_REPO=carl-infrastructure-deployments

# Optional: Customize deployment
export CARL_REGION=us-east-1  # Default: us-east-1
export CARL_ENVIRONMENT=dev   # Default: dev
```

### Step 2: Run Installer

```bash
./install-carl.sh
```

The installer will:
1. Check prerequisites (30 sec)
2. Enable AWS services (2-3 min)
3. Create Terraform backend (30 sec)
4. Update configuration files (10 sec)
5. Store secrets in AWS (30 sec)
6. Deploy core infrastructure (5-10 min)
7. Display next steps

**Total time: 15-20 minutes**

### Step 3: Enable Bedrock Models (Manual Step)

During installation, you'll be prompted to enable Bedrock model access:

1. Go to: https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess
2. Click "Enable specific models"
3. Enable:
   - ✅ Claude 3.5 Sonnet v2
   - ✅ Claude 3 Haiku
4. Click "Save changes"
5. Press ENTER in the installer to continue

### Step 4: Configure Slack App

After deployment, you'll receive an API Gateway URL. Update your Slack app:

1. Go to: https://api.slack.com/apps
2. Select your CARL app
3. Update these sections with `YOUR_API_URL/slack/events`:
   - **Slash Commands** → `/carl` → Request URL
   - **Event Subscriptions** → Request URL
   - **Interactivity & Shortcuts** → Request URL
4. Click "Save Changes" for each

### Step 5: Test CARL

In your Slack workspace:

```
/carl help
```

You should see CARL's command list!

---

## Full Install (with Jira)

If you want Jira ticket sync:

```bash
# Set required credentials
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_SIGNING_SECRET=...

# GitHub App credentials (run ./scripts/setup-github-app.sh first)
export GITHUB_APP_ID=123456
export GITHUB_INSTALLATION_ID=789012
export GITHUB_PRIVATE_KEY_PATH=/path/to/app-private-key.pem
export GITHUB_ORG=your-username
export GITHUB_REPO=carl-infrastructure-deployments

# Set Jira credentials
export JIRA_URL=https://your-domain.atlassian.net
export JIRA_API_TOKEN=your-jira-api-token
export JIRA_USER=your-email@example.com
export JIRA_PROJECT=CARL

# Run installer
./install-carl.sh
```

Jira integration will be configured automatically.

---

## Adding Jira Later

If you skipped Jira during initial install, add it anytime:

```bash
# Set Jira credentials
export JIRA_URL=https://your-domain.atlassian.net
export JIRA_API_TOKEN=your-jira-api-token
export JIRA_USER=your-email@example.com
export JIRA_PROJECT=CARL

# Run Jira configuration script
./configure-jira.sh
```

---

## Validation

After installation, validate deployment:

```bash
./validate-deployment.sh
```

This checks:
- ✅ AWS services enabled
- ✅ Terraform backend created
- ✅ Core infrastructure deployed
- ✅ Lambda function working
- ✅ API Gateway accessible
- ✅ DynamoDB tables created
- ✅ S3 buckets configured
- ✅ KMS encryption enabled
- ✅ Secrets stored correctly
- ✅ IAM roles configured
- ✅ CloudWatch logs available

**Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Validation Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Passed:   47
  Failed:   0
  Warnings: 2

✓ All critical checks passed! CARL is ready to use.
```

---

## Rollback

If something goes wrong, rollback the entire installation:

```bash
./install-carl.sh --rollback
```

This deletes (in reverse order):
1. Terraform infrastructure (`terraform destroy`)
2. Secrets Manager secrets
3. KMS keys (7-day deletion window)
4. GuardDuty detector
5. Security Hub
6. DynamoDB lock table
7. S3 state bucket (empties first)
8. Installation state file

**Warning:** This is destructive and cannot be undone!

---

## What Gets Installed

### AWS Services
- **Security Hub** - Compliance findings aggregation
- **GuardDuty** - Threat detection
- **AWS Config** - Configuration compliance
- **Bedrock** - Claude AI models (requires manual enablement)

### Terraform Backend
- **S3 Bucket** - `carl-terraform-state-<account-id>`
  - Versioning enabled
  - AES256 encryption
  - Public access blocked
- **DynamoDB Table** - `carl-terraform-state-lock`
  - Pay-per-request billing

### Core Infrastructure
- **Lambda Functions**
  - `carl-slack-router-dev` - Main Slack interface
  - `carl-pricing-prefetch-dev` - AWS pricing cache
  - `carl-pattern-analyzer-dev` - Learning system
- **DynamoDB Tables** (12 tables)
  - Findings, evidence, scan history, preferences, approvals
  - Resource graph, pricing cache, learning patterns
  - Jira mapping, feedback, conversations, exceptions
- **S3 Buckets**
  - `carl-evidence-<account-id>-dev` - Audit evidence
  - `carl-reports-<account-id>-dev` - Compliance reports
- **KMS Key** - Customer-managed encryption key
- **Secrets Manager** - Slack, GitHub, Jira credentials
- **API Gateway** - HTTPS endpoint for Slack webhook
- **CloudWatch Logs** - Lambda logging with KMS encryption
- **EventBridge Rules** - Scheduled pricing refresh, pattern analysis

### Estimated Monthly Cost
**$75-200/month** depending on usage:
- Bedrock API: $30-100 (variable)
- Lambda: $5-20
- DynamoDB: $10-30 (on-demand)
- S3: $5-15
- KMS + Secrets: $2-5
- Other: $20-35

---

## Installation Locations

All resources are created in:
- **AWS Account**: Your configured AWS account
- **Region**: `us-east-1` (default) or `$CARL_REGION`
- **Environment**: `dev` (default) or `$CARL_ENVIRONMENT`

Resource naming pattern: `carl-<resource>-<environment>`

---

## Configuration Files Created/Modified

The installer automatically updates:

### Created Files
- `carl-infrastructure/core/backend.tf` - Terraform backend config
- `carl-infrastructure/core/terraform.tfvars` - Deployment variables
- `.carl-install-state.json` - Installation state (for rollback)

### Modified Files
- `.github/workflows/*.yml` - AWS account ID updated
- `carl-infrastructure/core/variables.tf` - Region/environment defaults

### No Manual Editing Required!
All placeholder values (`CHANGEME`, `123456789012`, etc.) are replaced automatically.

---

## Troubleshooting

### Issue: "Missing required tools"

**Solution:** Install missing prerequisites:
```bash
brew install terraform awscli python3 jq git  # macOS
```

### Issue: "AWS credentials not configured"

**Solution:** Run `aws configure` and provide credentials.

### Issue: "Slack credentials are REQUIRED!"

**Solution:** Set environment variables:
```bash
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_SIGNING_SECRET=...
```

### Issue: "GitHub credentials are REQUIRED!"

**Solution:** Set environment variables:
```bash
export GITHUB_TOKEN=ghp_...
export GITHUB_ORG=your-username
export GITHUB_REPO=carl-infrastructure-deployments
```

### Issue: Terraform apply fails

**Solution:** Check the error message. Common issues:
- Bedrock models not enabled (enable manually)
- IAM permissions insufficient (need admin or near-admin)
- Region doesn't support Bedrock (use us-east-1, us-west-2, or eu-west-1)

### Issue: Rollback fails partway through

**Solution:** Manually clean up remaining resources:
```bash
# View installation state
cat .carl-install-state.json

# Manually delete resources listed in state file
aws s3 rb s3://carl-terraform-state-<account-id> --force
aws dynamodb delete-table --table-name carl-terraform-state-lock
# etc.
```

### Issue: "Cannot find validation script"

**Solution:** Ensure you're in the CARL root directory:
```bash
cd /path/to/carl
./validate-deployment.sh
```

---

## Security Best Practices

### Credentials Management
- ✅ Secrets stored in AWS Secrets Manager (encrypted with KMS)
- ✅ No hardcoded credentials in code
- ✅ Environment variables cleared after installation
- ✅ Use IAM roles where possible

### Encryption
- ✅ All S3 buckets encrypted (KMS or AES256)
- ✅ All DynamoDB tables encrypted (KMS)
- ✅ CloudWatch logs encrypted (KMS)
- ✅ Secrets Manager uses KMS encryption

### Access Control
- ✅ S3 buckets block public access
- ✅ IAM roles follow least privilege
- ✅ KMS key policies restrict access
- ✅ Secrets Manager access controlled by IAM

### Audit & Compliance
- ✅ CloudTrail logs all API calls
- ✅ Security Hub monitors compliance
- ✅ GuardDuty detects threats
- ✅ AWS Config tracks configuration changes

---

## Advanced Usage

### Custom Region Deployment

```bash
export CARL_REGION=eu-west-1
./install-carl.sh
```

**Note:** Bedrock availability varies by region. Recommended regions:
- `us-east-1` (N. Virginia) - **Best availability**
- `us-west-2` (Oregon)
- `eu-west-1` (Ireland)

### Production Environment

```bash
export CARL_ENVIRONMENT=prod
./install-carl.sh
```

Creates resources with `-prod` suffix instead of `-dev`.

### Multiple Environments

Deploy multiple CARL environments in the same account:

```bash
# Dev environment
export CARL_ENVIRONMENT=dev
./install-carl.sh

# QA environment
export CARL_ENVIRONMENT=qa
./install-carl.sh

# Prod environment
export CARL_ENVIRONMENT=prod
./install-carl.sh
```

Each environment is isolated with separate resources.

### Automated CI/CD Deployment

Use the installer in CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Install CARL
  env:
    SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
    SLACK_SIGNING_SECRET: ${{ secrets.SLACK_SIGNING_SECRET }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    GITHUB_ORG: ${{ github.repository_owner }}
    GITHUB_REPO: carl-infrastructure-deployments
  run: |
    ./install-carl.sh
```

---

## Post-Installation

### Test CARL Commands

```bash
# In Slack
/carl help                              # View commands
/carl ask How do I create a VPC?        # AI recommendations
/carl scan                              # Compliance scan
/carl build networking/vpc              # Generate infrastructure
/carl foundation start                  # Guided builder
```

### View Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/carl-slack-router-dev --follow

# Recent errors
aws logs tail /aws/lambda/carl-slack-router-dev --since 1h --filter-pattern ERROR
```

### Monitor Costs

```bash
# Current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost"
```

### Update CARL

```bash
# Pull latest code
git pull origin main

# Re-run installer (updates infrastructure)
./install-carl.sh
```

---

## Support

### Documentation
- **DEPLOYMENT_SETUP_GUIDE.md** - Complete manual setup guide
- **CONFIGURATION_CHANGES_REQUIRED.md** - Configuration reference
- **DEPLOYMENT_VALIDATION_CHECKLIST.md** - Manual validation steps
- **ARCHITECTURE.md** - Technical architecture
- **SLACK_COMMANDS.md** - Command reference

### Getting Help
1. Check troubleshooting section above
2. Run validation: `./validate-deployment.sh`
3. Review logs: `aws logs tail /aws/lambda/carl-slack-router-dev --follow`
4. Check GitHub issues: https://github.com/your-org/carl/issues

---

## Comparison: Manual vs Automated Installation

| Task | Manual | Automated |
|------|--------|-----------|
| **Time** | 2-4 hours | 15-20 minutes |
| **Steps** | 50+ manual steps | 2 commands |
| **Configuration** | Edit 10+ files | Set env vars |
| **Error-prone** | High (typos, missed steps) | Low (validated) |
| **Rollback** | Manual cleanup | One command |
| **Validation** | Manual checks | Automated script |
| **Reproducible** | No (manual steps vary) | Yes (identical every time) |

**Recommendation:** Use automated installation unless you need deep customization.

---

## FAQ

**Q: Can I use an existing S3 bucket for Terraform state?**
A: Yes, but the installer creates one automatically. To use existing, modify `backend.tf` after installation.

**Q: Do I need a GitHub organization or can I use a personal account?**
A: Personal accounts work fine. Set `GITHUB_ORG=your-username`.

**Q: Why GitHub App instead of Personal Access Token?**
A: GitHub Apps are much more secure:
- Tokens expire after 1 hour (vs permanent PAT)
- Not tied to a user account (doesn't break if user leaves)
- Fine-grained permissions (only repos you specify)
- Better audit trail in GitHub
Run `./scripts/setup-github-app.sh` for guided setup.

**Q: Can I deploy CARL without Jira?**
A: Yes! Jira is optional. Findings are stored in DynamoDB regardless.

**Q: What if I don't have a Slack workspace?**
A: You need Slack - it's CARL's only interface. Create a free workspace at https://slack.com/create.

**Q: Can I deploy to multiple AWS accounts?**
A: Yes, but each account needs a separate installation. Configure AWS CLI for each account and run the installer.

**Q: Is the installer idempotent?**
A: Yes, you can re-run it safely. Existing resources are detected and skipped.

**Q: Can I customize the Terraform code before deploying?**
A: Yes, but do it after running the installer. It will update your changes to match configuration.

**Q: How do I upgrade CARL?**
A: Pull latest code (`git pull`) and re-run the installer. It updates infrastructure in place.

---

## License

CARL is provided as-is for internal use. See LICENSE file for details.

---

**Ready to install CARL? Start with the [Quick Start](#quick-start-minimal-install) section above!**
