# Slack Setup Guide for CARL

Complete guide to setting up Slack integration for CARL.

---

## Overview

CARL uses Slack as its primary interface. Users interact with CARL through slash commands like `/carl status`, `/carl architect`, etc. This guide walks you through creating and configuring a Slack app for CARL.

---

## Prerequisites

- Admin access to your Slack workspace
- GitHub repository with CARL code
- AWS infrastructure deployed (or ready to deploy)
- **AWS Bedrock model access enabled** (Claude 3.5 Sonnet and Claude 3 Haiku)
  - Required for CARL's AI features to function
  - Enable at: AWS Console → Bedrock → Model access

---

## Quick Start

### Step 1: Create Slack App

1. Go to: https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. **App Name**: `CARL-dev` (or `CARL` for single environment)
4. **Workspace**: Select your Slack workspace
5. Click **"Create App"**

### Step 2: Configure OAuth Scopes

1. Click **"OAuth & Permissions"** in the left sidebar
2. Scroll to **"Redirect URLs"**
3. Click **"Add New Redirect URL"**
4. Enter: `https://slack.com/oauth/redirect` (temporary placeholder)
5. Click **"Save URLs"**
6. Scroll to **"Bot Token Scopes"**
7. Click **"Add an OAuth Scope"** and add:
   - `chat:write` - Required for CARL to send messages

### Step 3: Install App to Workspace

1. Scroll to top of **"OAuth & Permissions"** page
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)
   - Example: `xoxb-YOUR-BOT-TOKEN-GOES-HERE`

### Step 4: Get Signing Secret

1. Click **"Basic Information"** in the left sidebar
2. Scroll to **"App Credentials"**
3. Click **"Show"** next to **"Signing Secret"**
4. Copy the signing secret
   - Example: `your-signing-secret-here`

### Step 5: Add Secrets to GitHub

**Option A: Using GitHub CLI**
```bash
export GH_TOKEN=your_github_token

gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-your-bot-token" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_DEV -b "your-signing-secret" -R your-org/CARL
```

**Option B: Using GitHub UI**
1. Go to: https://github.com/your-org/CARL/settings/secrets/actions
2. Click "New repository secret"
3. Add two secrets:
   - Name: `SLACK_BOT_TOKEN_DEV`, Value: `xoxb-...`
   - Name: `SLACK_SIGNING_SECRET_DEV`, Value: `...`

---

## Post-Deployment Configuration

After CARL is deployed to AWS, you need to configure Slack to send events to CARL's API Gateway.

### Step 6: Get API Gateway URL

After deployment, get the API Gateway URL:

**From Terraform Output:**
```bash
cd carl-infrastructure/core
terraform output slack_endpoint_url
```

**From AWS Console:**
1. Go to API Gateway console
2. Find API: `carl-dev-api`
3. Go to Stages → `prod`
4. Copy the **Invoke URL**
5. Add `/slack/events` to the end
   - Example: `https://abc123.execute-api.us-east-1.amazonaws.com/prod/slack/events`

### Step 7: Update Redirect URL

1. Go to your Slack app: https://api.slack.com/apps
2. Click **"OAuth & Permissions"**
3. Under **"Redirect URLs"**, remove the placeholder
4. Add your real API Gateway URL:
   - `https://abc123.execute-api.us-east-1.amazonaws.com/prod/slack/oauth/callback`
5. Click **"Save URLs"**

### Step 8: Configure Slash Commands

1. Click **"Slash Commands"** in the left sidebar
2. Click **"Create New Command"**
3. Configure the `/carl` command:
   - **Command**: `/carl`
   - **Request URL**: `https://abc123.execute-api.us-east-1.amazonaws.com/prod/slack/events`
   - **Short Description**: `Interact with CARL AI assistant`
   - **Usage Hint**: `status | findings | architect <question> | help`
4. Click **"Save"**

### Step 9: Enable Event Subscriptions

1. Click **"Event Subscriptions"** in the left sidebar
2. Toggle **"Enable Events"** to **On**
3. **Request URL**: `https://abc123.execute-api.us-east-1.amazonaws.com/prod/slack/events`
4. Wait for the green "Verified" checkmark
5. Scroll to **"Subscribe to bot events"**
6. Click **"Add Bot User Event"** and add:
   - `app_mention` - When users @mention CARL
   - `message.channels` - Messages in channels CARL is in
7. Click **"Save Changes"**
8. Slack will prompt you to **"Reinstall your app"** - click the link and approve

### Step 10: Test CARL

In any Slack channel:

1. Type: `/carl help`
2. CARL should respond with available commands

Try:
```
/carl status
/carl architect how do I set up a VPC?
/carl foundation start
```

---

## Multiple Environments

If deploying CARL to multiple environments (dev, qa, prod), you have two options:

### Option 1: Same Slack App for All Environments

Use the same Slack app but deploy CARL to different AWS accounts/regions. The Slack app talks to whichever environment's API Gateway you configured.

**Pros:**
- Simpler (one Slack app)
- Single interface for all environments

**Cons:**
- No environment separation in Slack
- Same credentials used across environments

### Option 2: Separate Slack Apps per Environment

Create separate Slack apps: `CARL-dev`, `CARL-qa`, `CARL-prod`.

**Pros:**
- Complete environment isolation
- Different API Gateway URLs per environment
- Separate credentials

**Cons:**
- More setup work
- Need multiple Slack workspaces or use different slash commands (`/carl-dev`, `/carl-qa`, `/carl-prod`)

**For separate apps, create GitHub secrets:**
```bash
# Dev environment
gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-dev-token" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_DEV -b "dev-secret" -R your-org/CARL

# QA environment
gh secret set SLACK_BOT_TOKEN_QA -b "xoxb-qa-token" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_QA -b "qa-secret" -R your-org/CARL

# Prod environment
gh secret set SLACK_BOT_TOKEN_PROD -b "xoxb-prod-token" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_PROD -b "prod-secret" -R your-org/CARL
```

---

## Troubleshooting

### "CARL doesn't respond to /carl command"

**Check:**
1. Slash command is configured with correct Request URL
2. API Gateway URL is accessible (test with `curl`)
3. Lambda function is deployed and healthy
4. Signing secret matches in both Slack and AWS SSM Parameter Store

**Debug:**
```bash
# Check Lambda logs
aws logs tail /aws/lambda/carl-dev-slack-router --follow

# Test API Gateway endpoint
curl -X POST https://your-api-gateway-url/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test"}'
```

### "Event subscription verification failed"

**Causes:**
- Lambda not deployed yet
- API Gateway URL incorrect
- Lambda not responding within 3 seconds
- Signing secret mismatch

**Fix:**
1. Deploy CARL infrastructure first
2. Verify API Gateway URL is correct
3. Check Lambda logs for errors
4. Ensure signing secret in GitHub matches Slack app

### "CARL responds but commands don't work"

**Check:**
1. DynamoDB tables exist and Lambda has permissions
2. Bedrock is enabled in your AWS region
3. SSM parameters are set correctly
4. IAM role for Lambda has necessary permissions

**Debug:**
```bash
# Check SSM parameters
aws ssm get-parameter --name /dev/carl/slack_bot_token --with-decryption
aws ssm get-parameter --name /dev/carl/slack_signing_secret --with-decryption

# Check DynamoDB tables
aws dynamodb list-tables --query "TableNames[?contains(@, 'carl')]"
```

### "Bedrock model access denied"

**This is the most common deployment blocker!**

CARL requires AWS Bedrock Claude models. The bootstrap script verifies model access, but if you skipped bootstrap or deployed manually, you must enable it:

**Quick Fix:**
```bash
# Direct link (replace us-east-1 with your region)
open "https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess"
```

**Manual Steps:**
1. Go to AWS Bedrock console
2. Select your region (must match CARL deployment region: `us-east-1`)
3. Click "Model access" in left sidebar
4. Click "Enable specific models"
5. Enable:
   - **Claude 3.5 Sonnet** (required for architecture recommendations)
   - **Claude 3 Haiku** (required for simple queries)
6. Click "Save changes"
7. Access is typically granted instantly

**Verify Access:**
```bash
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `anthropic.claude-3-5-sonnet`)].modelId'
```

If models are listed, Bedrock access is working!

---

## Security Best Practices

### Rotate Secrets Regularly

**Slack Bot Token:**
1. Go to https://api.slack.com/apps
2. Click your CARL app
3. Go to "OAuth & Permissions"
4. Click "Rotate Token"
5. Update GitHub secret with new token
6. Redeploy CARL

**Signing Secret:**

Can't be rotated directly. If compromised:
1. Create a new Slack app
2. Configure it with same settings
3. Update GitHub secrets
4. Redeploy CARL

### Use Separate Apps for Production

For production deployments:
- Use a separate Slack app (`CARL-prod`)
- Deploy to a separate AWS account
- Use different GitHub secrets (`_PROD` suffix)
- Restrict Slack app to specific channels

### Monitor API Usage

Watch CloudWatch metrics:
- Lambda invocations
- API Gateway 4xx/5xx errors
- Lambda errors and throttles
- DynamoDB read/write consumption

Set up alarms for unusual activity.

---

## GitHub Secrets Reference

**Required Secrets:**

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `SLACK_BOT_TOKEN_DEV` | Bot OAuth token for dev | `xoxb-141542311302-...` |
| `SLACK_SIGNING_SECRET_DEV` | Signing secret for dev | `17d614f64958045b1...` |
| `SLACK_BOT_TOKEN_QA` | Bot OAuth token for qa | `xoxb-...` |
| `SLACK_SIGNING_SECRET_QA` | Signing secret for qa | `...` |
| `SLACK_BOT_TOKEN_PROD` | Bot OAuth token for prod | `xoxb-...` |
| `SLACK_SIGNING_SECRET_PROD` | Signing secret for prod | `...` |
| `SLACK_WEBHOOK_URL` | Optional: deployment notifications | `https://hooks.slack.com/...` |

---

## Next Steps

After Slack is configured:

1. **Test basic commands**: `/carl help`, `/carl status`
2. **Enable Bedrock model access** (if not already done)
3. **Run initial scan**: `/carl scan now`
4. **Review findings**: `/carl findings high`
5. **Configure monitoring**: `/carl monitoring enable`
6. **Set up architecture patterns**: `/carl patterns`

---

## Additional Resources

- [Slack API Documentation](https://api.slack.com/docs)
- [CARL Deployment Guide](DEPLOYMENT.md)
- [OIDC Setup Guide](OIDC_SETUP.md)
- [Bootstrap Guide](BOOTSTRAP.md)

---

**Last Updated:** 2026-01-28
