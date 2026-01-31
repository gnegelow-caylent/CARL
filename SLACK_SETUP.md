# Slack Setup Guide for CARL

**VERIFIED WORKING** - Updated 2026-01-28 with tested, working configuration.

Complete guide to setting up Slack integration for CARL, including all fixes and troubleshooting tips.

---

## Overview

CARL uses Slack as its primary interface. Users interact with CARL through slash commands like `/carl status`, `/carl architect`, etc. This guide walks you through creating and configuring a Slack app for CARL with **verified working steps**.

---

## Prerequisites

- Admin access to your Slack workspace
- CARL deployed to AWS (with API Gateway endpoint)
- AWS Bedrock model access enabled (Claude 3.5 Sonnet and Claude 3 Haiku)
- Slack bot token and signing secret stored in GitHub Secrets

---

## Quick Start (Verified Working)

### Step 1: Create Slack App

1. Go to: https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. **App Name**: `CARL` (or `CARL-dev` for dev environment)
4. **Workspace**: Select your Slack workspace
5. Click **"Create App"**

### Step 2: Configure OAuth Scopes

1. Click **"OAuth & Permissions"** in the left sidebar
2. Scroll to **"Bot Token Scopes"**
3. Click **"Add an OAuth Scope"** and add these scopes:
   - `app_mentions:read` - CARL can read @mentions
   - `channels:history` - CARL can read channel messages (for context)
   - `chat:write` - CARL sends messages
   - `commands` - CARL responds to slash commands
   - `files:write` - CARL uploads PDF reports directly to Slack
   - `im:history` - CARL can read direct messages (for context)

### Step 3: Install App to Workspace

1. Scroll to top of **"OAuth & Permissions"** page
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. **Copy the "Bot User OAuth Token"** (starts with `xoxb-`)
   - Example: `xoxb-YOUR-WORKSPACE-ID-YOUR-APP-ID-YOUR-TOKEN`
   - **Save this - you'll need it for GitHub Secrets**

### Step 4: Get Signing Secret

1. Click **"Basic Information"** in the left sidebar
2. Scroll to **"App Credentials"**
3. Click **"Show"** next to **"Signing Secret"**
4. **Copy the signing secret**
   - Example: `1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p`
   - **Save this - you'll need it for GitHub Secrets**

### Step 5: Add Secrets to GitHub

Add the Slack credentials to your GitHub repository secrets:

**Using GitHub UI:**
1. Go to: `https://github.com/YOUR-ORG/CARL/settings/secrets/actions`
2. Click "New repository secret"
3. Add these two secrets:

| Secret Name | Value |
|-------------|-------|
| `SLACK_BOT_TOKEN_DEV` | Your `xoxb-...` token from Step 3 |
| `SLACK_SIGNING_SECRET_DEV` | Your signing secret from Step 4 |

**Using GitHub CLI:**
```bash
gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-your-token-here" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_DEV -b "your-signing-secret" -R your-org/CARL
```

### Step 6: Deploy CARL

Push to `develop` branch to trigger deployment:
```bash
git push origin develop
```

Wait for GitHub Actions to complete (~3-5 minutes).

Get your API Gateway endpoint:
```bash
cd carl-infrastructure/core
terraform output slack_webhook_url
```

Example output: `https://bz9vbzlh56.execute-api.us-east-1.amazonaws.com/slack`

---

## Post-Deployment: Configure Slack App

**IMPORTANT:** Do these steps AFTER CARL is deployed to AWS, otherwise URL verification will fail.

### Step 7: Enable Event Subscriptions

1. Go to your Slack app: https://api.slack.com/apps
2. Click **"Event Subscriptions"** in the left sidebar
3. Toggle **"Enable Events"** to **ON**
4. **Request URL**: Enter your API Gateway URL:
   ```
   https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/slack
   ```
5. Wait for the green **"Verified"** checkmark ✅
   - If it says "Your URL didn't respond", see [Troubleshooting](#troubleshooting) below
6. Scroll to **"Subscribe to bot events"**
7. Click **"Add Bot User Event"** and add:
   - `app_mention` - When users @mention CARL
   - `message.channels` - Messages in channels CARL is in
   - `message.im` - Direct messages to CARL
8. Click **"Save Changes"**
9. Slack will show a yellow banner saying **"Reinstall your app"** - **Click it and approve**

### Step 8: Create Slash Command

1. Click **"Slash Commands"** in the left sidebar
2. Click **"Create New Command"**
3. Fill in the form:
   ```
   Command: /carl
   Request URL: https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/slack
   Short Description: AWS compliance assistant
   Usage Hint: help
   ```
4. Click **"Save"**
5. **IMPORTANT:** You MUST reinstall the app after adding slash commands
   - Click **"Install App"** in the left sidebar
   - Click **"Reinstall to Workspace"**
   - Click **"Allow"**

### Step 9: Test CARL in Slack

In any Slack channel where CARL is present:

```
/carl help
```

CARL should respond with the help menu showing all available commands.

**Try these commands:**
```
/carl status
/carl ask how do I enable MFA for IAM users?
/carl recommend VPC with high availability
```

---

## Troubleshooting

### "Your URL didn't respond with the value of the challenge parameter"

This is the most common issue during Event Subscriptions setup.

**Symptoms:**
- Slack URL verification fails
- Red X appears next to Request URL
- Error message about challenge parameter

**Fixes Applied (Already in CARL Code):**
1. ✅ Lambda parses JSON regardless of Content-Type header
2. ✅ Lambda handles both lowercase and capitalized headers
3. ✅ Lambda bypasses signature verification for URL challenges
4. ✅ Lambda properly packages Python dependencies

**How to Verify It's Fixed:**

Test the endpoint directly:
```bash
curl -X POST "https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/slack" \
  -H "Content-Type: application/json" \
  -d '{"type": "url_verification", "challenge": "test123"}'
```

**Expected response:**
```json
{"challenge": "test123"}
```

If you see this, your Lambda is working! Retry Slack URL verification.

**If Still Failing:**

Check Lambda logs:
```bash
aws logs tail /aws/lambda/carl-dev-api --since 5m --follow --region us-east-1
```

Look for errors in the logs and share them for help.

### "dispatch_failed" Error on `/carl` Commands

**Symptoms:**
- Slash command shows "dispatch_failed" error
- Lambda receives request but crashes

**Cause:** Lambda was trying to parse URL-encoded slash command data as JSON.

**Fix:** ✅ Already fixed in code (commit `dd7ac92`)
- Lambda now properly handles `application/x-www-form-urlencoded` content type
- Slash commands are parsed with `parse_qs()` instead of `json.loads()`

**Verify:**
```bash
aws logs tail /aws/lambda/carl-dev-api --since 3m --region us-east-1
```

You should see log entries like:
```
Parsed as URL-encoded, keys: ['token', 'command', 'text', ...]
```

### "/carl is not a valid command"

**Symptoms:**
- When you type `/carl` in Slack, it says command not found
- The command doesn't appear in the autocomplete list

**Causes:**
1. Slash command not created in Slack app settings
2. App not reinstalled after creating the command
3. Command takes time to propagate across Slack servers

**Fixes:**
1. Go to https://api.slack.com/apps → Your app → "Slash Commands"
2. Verify `/carl` command exists with correct Request URL
3. If missing, create it (see Step 8 above)
4. **CRITICAL:** Go to "Install App" and click "Reinstall to Workspace"
5. Wait 30-60 seconds for Slack to propagate the changes
6. Refresh Slack (`Cmd+R` on Mac, `Ctrl+R` on Windows)
7. Try typing `/` and look for `carl` in the autocomplete

### Lambda Crashes with "AccessDeniedException"

**Symptoms:**
- Lambda logs show `AccessDeniedException` errors
- Error mentions `dynamodb:Scan` or `ssm:GetParameter` or `secretsmanager:GetSecretValue`

**Fixes Applied:**
1. ✅ Changed from Secrets Manager to SSM Parameter Store
2. ✅ Lambda IAM role has `ssm:GetParameter` permission
3. ✅ Code uses `get_parameter()` instead of `get_secret()`

**All IAM permissions are configured in Terraform** (`carl-infrastructure/core/main.tf`).

If you see this error, the Lambda role might be missing permissions. Check:
```bash
aws iam get-role-policy --role-name carl-dev-lambda-role --policy-name ssm-access
```

### Lambda Crashes with "ImportModuleError"

**Symptoms:**
- `Unable to import module 'handlers.slack_router'`
- `No module named 'slack_sdk'` or `No module named 'boto3'`

**Cause:** Python dependencies not packaged with Lambda code.

**Fix:** ✅ Already fixed in GitHub Actions workflow (`.github/workflows/deploy-core.yml`):
```yaml
- name: Package Lambda
  run: |
    pip install -r carl-app/requirements.txt -t carl-app/src/
    cd carl-app/src
    zip -r ../../carl-infrastructure/core/lambda.zip .
```

Dependencies are now installed before packaging.

### Event Subscriptions Work, But Slash Commands Don't

**Symptoms:**
- URL verification succeeds ✅
- CARL responds to @mentions
- But `/carl help` fails with "dispatch_failed"

**Cause:** Different content types for events vs slash commands:
- Events: `application/json`
- Slash commands: `application/x-www-form-urlencoded`

**Fix:** ✅ Already fixed (commit `dd7ac92`)

Lambda now handles both content types correctly.

---

## Known Issues & Fixes Applied

All of these issues have been **resolved** in the current code:

### Issue 1: Import Paths ✅ FIXED
**Problem:** `from src.services` imports failed in Lambda
**Fix:** Changed to relative imports `from services`
**Commit:** `98a857c`

### Issue 2: Lambda Packaging ✅ FIXED
**Problem:** Terraform recreated zip without dependencies
**Fix:** Use pre-built zip from GitHub Actions
**Commit:** `3342cdb`

### Issue 3: Secrets Manager vs SSM ✅ FIXED
**Problem:** Code used Secrets Manager, but secrets in SSM Parameter Store
**Fix:** Changed `get_secret()` to `get_parameter()`
**Commit:** `5d0b4a1`

### Issue 4: Terraform Validation ✅ FIXED
**Problem:** `filebase64sha256: no such file` during validation
**Fix:** Create placeholder lambda.zip before validation
**Commit:** `b8728b4`

### Issue 5: Empty Timestamp ✅ FIXED
**Problem:** `ValueError: invalid literal for int()` with empty timestamp
**Fix:** Validate timestamp before parsing
**Commit:** `f1d27cb`

### Issue 6: Content-Type Header ✅ FIXED
**Problem:** API Gateway not passing Content-Type header
**Fix:** Parse JSON regardless of Content-Type
**Commit:** `4818b69`

### Issue 7: Case-Sensitive Headers ✅ FIXED
**Problem:** `X-Slack-Request-Timestamp` vs `x-slack-request-timestamp`
**Fix:** Check for both lowercase and capitalized headers
**Commit:** `dd6b742`

### Issue 8: URL-Encoded Slash Commands ✅ FIXED
**Problem:** Slash commands send URL-encoded data, not JSON
**Fix:** Parse `application/x-www-form-urlencoded` with `parse_qs()`
**Commit:** `dd7ac92`

---

## Multiple Environments

### Same Slack App for All Environments (Recommended)

Use one Slack app, but point it to different API Gateway URLs:
- Dev: `https://dev-api.execute-api.us-east-1.amazonaws.com/slack`
- QA: `https://qa-api.execute-api.us-east-1.amazonaws.com/slack`
- Prod: `https://prod-api.execute-api.us-east-1.amazonaws.com/slack`

**Pros:**
- Single interface
- Less maintenance

**Cons:**
- Shared credentials across environments

### Separate Slack Apps per Environment

Create separate apps: `CARL-dev`, `CARL-qa`, `CARL-prod`.

**GitHub Secrets:**
```bash
# Dev
gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-dev-token"
gh secret set SLACK_SIGNING_SECRET_DEV -b "dev-secret"

# QA
gh secret set SLACK_BOT_TOKEN_QA -b "xoxb-qa-token"
gh secret set SLACK_SIGNING_SECRET_QA -b "qa-secret"

# Prod
gh secret set SLACK_BOT_TOKEN_PROD -b "xoxb-prod-token"
gh secret set SLACK_SIGNING_SECRET_PROD -b "prod-secret"
```

**Pros:**
- Complete isolation
- Separate credentials

**Cons:**
- More setup
- Need different slash commands (`/carl-dev`, `/carl-qa`, `/carl`)

---

## Security Best Practices

### Rotate Credentials Regularly

**Slack Bot Token:**
1. Go to Slack app → "OAuth & Permissions"
2. Click "Rotate Token"
3. Update GitHub secret
4. Redeploy CARL

**Signing Secret:**
- Cannot be rotated directly
- If compromised, create a new Slack app

### Monitor Lambda Invocations

Set up CloudWatch alarms for:
- High error rates
- Unusual invocation patterns
- Throttling

### Restrict Channel Access

In production:
- Add CARL only to specific channels
- Don't use CARL in public channels with sensitive data
- Review Slack audit logs regularly

---

## Testing Checklist

After setup, verify these work:

- [ ] `/carl help` shows help menu
- [ ] `/carl status` shows compliance status
- [ ] `/carl ask <question>` responds with AI answer
- [ ] `@CARL hello` responds to @mentions
- [ ] CARL sends typing indicator while thinking
- [ ] CARL responds within 10 seconds
- [ ] Lambda logs show no errors
- [ ] Signature verification works (no 401 errors)

---

## API Gateway Endpoint Format

**Correct format:**
```
https://YOUR-API-ID.execute-api.REGION.amazonaws.com/slack
```

**Examples:**
```
https://bz9vbzlh56.execute-api.us-east-1.amazonaws.com/slack
https://abc123xyz.execute-api.us-west-2.amazonaws.com/slack
```

**Common mistakes:**
- ❌ Missing `/slack` at the end
- ❌ Wrong region
- ❌ Using stage name (`/prod/slack`) - not needed for HTTP API

---

## CloudWatch Logs

View Lambda logs:
```bash
# Tail recent logs
aws logs tail /aws/lambda/carl-dev-api --since 5m --region us-east-1

# Follow logs in real-time
aws logs tail /aws/lambda/carl-dev-api --follow --region us-east-1

# Filter for errors only
aws logs tail /aws/lambda/carl-dev-api --since 1h --region us-east-1 | grep ERROR
```

---

## Additional Resources

- [Slack API Documentation](https://api.slack.com/docs)
- [AWS Lambda Function URLs](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html)
- [CARL Deployment Guide](DEPLOYMENT.md)
- [CARL Architecture](ARCHITECTURE.md)

---

**Status:** ✅ **VERIFIED WORKING**
**Last Tested:** 2026-01-28
**Last Updated:** 2026-01-28
**Commits with Fixes:** `98a857c` through `dd7ac92`

