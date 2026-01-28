# GitHub Secrets Setup Guide

**DEPRECATED:** This guide uses the legacy AWS access key approach. For new deployments, use the modern OIDC approach documented in [BOOTSTRAP.md](BOOTSTRAP.md).

---

## Modern Approach (Recommended)

Use the bootstrap script and OIDC authentication:

```bash
./bootstrap.sh
```

This creates:
- S3 state bucket
- OIDC provider
- IAM roles (no access keys!)
- Backend configurations

Then add **6 GitHub secrets** (no AWS keys stored!):

```
AWS_ROLE_ARN_DEV
AWS_ROLE_ARN_QA
AWS_ROLE_ARN_PROD
AWS_REGION
SLACK_BOT_TOKEN_DEV
SLACK_SIGNING_SECRET_DEV
```

See [BOOTSTRAP.md](BOOTSTRAP.md) for complete instructions.

---

## Quick Reference: All GitHub Secrets

### AWS Secrets (4 - from bootstrap)

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `AWS_ROLE_ARN_DEV` | Dev deployer role ARN | `arn:aws:iam::403802364021:role/carl-deployer-dev` |
| `AWS_ROLE_ARN_QA` | QA deployer role ARN | `arn:aws:iam::403802364021:role/carl-deployer-qa` |
| `AWS_ROLE_ARN_PROD` | Prod deployer role ARN | `arn:aws:iam::403802364021:role/carl-deployer-prod` |
| `AWS_REGION` | AWS region | `us-east-1` |

### Slack Secrets (6 - required for CARL to function)

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `SLACK_BOT_TOKEN_DEV` | Dev bot token | `xoxb-141542311302-...` |
| `SLACK_SIGNING_SECRET_DEV` | Dev signing secret | `17d614f64958045b1...` |
| `SLACK_BOT_TOKEN_QA` | QA bot token | `xoxb-...` |
| `SLACK_SIGNING_SECRET_QA` | QA signing secret | `...` |
| `SLACK_BOT_TOKEN_PROD` | Prod bot token | `xoxb-...` |
| `SLACK_SIGNING_SECRET_PROD` | Prod signing secret | `...` |

### Optional Secrets (1)

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `SLACK_WEBHOOK_URL` | Deployment notifications | `https://hooks.slack.com/services/...` |

---

## Quick Setup with GitHub CLI

```bash
export GH_TOKEN=your_github_token

# AWS secrets (from bootstrap output)
gh secret set AWS_ROLE_ARN_DEV -b "arn:aws:iam::ACCOUNT:role/carl-deployer-dev" -R your-org/CARL
gh secret set AWS_ROLE_ARN_QA -b "arn:aws:iam::ACCOUNT:role/carl-deployer-qa" -R your-org/CARL
gh secret set AWS_ROLE_ARN_PROD -b "arn:aws:iam::ACCOUNT:role/carl-deployer-prod" -R your-org/CARL
gh secret set AWS_REGION -b "us-east-1" -R your-org/CARL

# Slack secrets (from Slack app configuration)
gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-your-token" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_DEV -b "your-secret" -R your-org/CARL
```

See [SLACK_SETUP.md](SLACK_SETUP.md) for Slack configuration details.

---

## Legacy Approach (Access Keys)

**WARNING:** This approach is deprecated. Use OIDC instead.

### Step 1: Create AWS IAM User for Deployment (DEPRECATED)

### 1.1 Create IAM User

```bash
aws iam create-user --user-name carl-deployer-dev
```

### 1.2 Attach Required Policies

```bash
# Administrator access (simplest for initial deployment)
aws iam attach-user-policy \
  --user-name carl-deployer-dev \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

> **Note:** For production, use least-privilege IAM policies. See "Production IAM Policy" section below.

### 1.3 Create Access Keys

```bash
aws iam create-access-key --user-name carl-deployer-dev
```

**Save the output:**
```json
{
  "AccessKey": {
    "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
    "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }
}
```

---

## Step 2: Get Slack Credentials

### 2.1 Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "CARL-dev"
4. Select your workspace
5. Click "Create App"

### 2.2 Configure OAuth & Permissions

Under "OAuth & Permissions", add these **Bot Token Scopes**:
- `chat:write` - Send messages
- `commands` - Respond to slash commands
- `users:read` - Read user information

### 2.3 Install to Workspace

1. Click "Install to Workspace"
2. Review permissions
3. Click "Allow"

### 2.4 Copy Credentials

**Bot Token** (starts with `xoxb-`):
- Found under "OAuth & Permissions" → "Bot User OAuth Token"
- Example: `xoxb-YOUR-TOKEN-HERE-REPLACE-ME`

**Signing Secret**:
- Found under "Basic Information" → "App Credentials" → "Signing Secret"
- Example: `YOUR-SIGNING-SECRET-HERE-REPLACE-ME`

### 2.5 Placeholder Values (For Testing Without Slack)

If you want to deploy CARL first and configure Slack later:
```
SLACK_BOT_TOKEN_DEV=xoxb-placeholder-token
SLACK_SIGNING_SECRET_DEV=placeholder-secret-value
```

---

## Step 3: Add Secrets to GitHub

### 3.1 Navigate to Repository Settings

1. Go to https://github.com/gnegelow-caylent/CARL
2. Click "Settings" tab
3. Click "Secrets and variables" → "Actions"

### 3.2 Add Repository Secrets

Click "New repository secret" for each:

**AWS Credentials (Dev):**
```
Name: AWS_ACCESS_KEY_ID_DEV
Value: AKIAIOSFODNN7EXAMPLE

Name: AWS_SECRET_ACCESS_KEY_DEV
Value: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**Slack Credentials (Dev):**
```
Name: SLACK_BOT_TOKEN_DEV
Value: xoxb-YOUR-ACTUAL-TOKEN-GOES-HERE

Name: SLACK_SIGNING_SECRET_DEV
Value: your-actual-signing-secret-here
```

---

## Step 4: Deploy CARL Minimal Core

### 4.1 Trigger Deployment via GitHub Actions

**Option A: Push to develop branch**
```bash
git checkout develop
git push origin develop
# Watches Actions tab - auto-deploys to dev
```

**Option B: Manual workflow trigger**
1. Go to Actions tab
2. Select "Deploy CARL Core"
3. Click "Run workflow"
4. Select branch: develop
5. Click "Run workflow"

### 4.2 Monitor Deployment

1. Go to "Actions" tab
2. Click on the running workflow
3. Watch the deployment progress (~5-10 minutes)

### 4.3 Get API Endpoint

After deployment completes:
1. Check workflow output for "api_endpoint"
2. Or run locally:
```bash
cd carl-infrastructure/core
terraform init
terraform output api_endpoint
```

Example output: `https://abc123xyz.execute-api.us-east-1.amazonaws.com`

---

## Step 5: Configure Slack App (Connect to CARL)

### 5.1 Set Webhook URL

1. Go to your Slack app settings
2. Under "Event Subscriptions":
   - Enable Events: ON
   - Request URL: `<api_endpoint>/slack`
   - Example: `https://abc123xyz.execute-api.us-east-1.amazonaws.com/slack`
   - Wait for "Verified" checkmark

3. Subscribe to bot events:
   - `app_mention`
   - `message.im`

4. Click "Save Changes"

### 5.2 Add Slash Command

1. Under "Slash Commands" → "Create New Command"
2. Command: `/carl`
3. Request URL: `<api_endpoint>/slack`
4. Short Description: "CARL - Cloud Automated Risk & Compliance Logic"
5. Usage Hint: `status | architect | recommend | patterns`
6. Click "Save"

### 5.3 Test CARL

In Slack:
```
/carl hello
```

Expected response: Welcome message with feature selection buttons

---

## Additional Secrets (For Full Pipeline)

### QA Environment

```
AWS_ACCESS_KEY_ID_QA=<qa-aws-access-key>
AWS_SECRET_ACCESS_KEY_QA=<qa-aws-secret-key>
SLACK_BOT_TOKEN_QA=<qa-slack-bot-token>
SLACK_SIGNING_SECRET_QA=<qa-slack-signing-secret>
```

### Prod Environment

```
AWS_ACCESS_KEY_ID_PROD=<prod-aws-access-key>
AWS_SECRET_ACCESS_KEY_PROD=<prod-aws-secret-key>
SLACK_BOT_TOKEN_PROD=<prod-slack-bot-token>
SLACK_SIGNING_SECRET_PROD=<prod-slack-signing-secret>
```

### GitHub Integration (For Feature Deployment)

```
Name: GITHUB_TOKEN
Value: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**How to create:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token"
3. Scopes needed:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
4. Copy the token

### Notifications

```
Name: SLACK_WEBHOOK_URL
Value: https://hooks.slack.com/services/YOUR-WEBHOOK-URL-HERE
```

**How to create:**
1. Go to https://api.slack.com/apps
2. Select your CARL app
3. Under "Incoming Webhooks" → "Activate Incoming Webhooks"
4. Click "Add New Webhook to Workspace"
5. Select channel for notifications
6. Copy the webhook URL

### Approvers

```
Name: PROD_APPROVERS
Value: gnegelow-caylent,other-github-username
```

(Comma-separated list of GitHub usernames who can approve prod deployments)

---

## Production IAM Policy (Least Privilege)

Instead of AdministratorAccess, use this policy for production:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:*",
        "apigateway:*",
        "dynamodb:*",
        "s3:*",
        "iam:*",
        "logs:*",
        "cloudwatch:*",
        "ssm:*",
        "kms:*",
        "bedrock:*",
        "events:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeSubnets",
        "ec2:DescribeVpcs"
      ],
      "Resource": "*"
    }
  ]
}
```

Save as `carl-deployer-policy.json`, then:
```bash
aws iam create-policy \
  --policy-name CARLDeployerPolicy \
  --policy-document file://carl-deployer-policy.json

aws iam attach-user-policy \
  --user-name carl-deployer-prod \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/CARLDeployerPolicy
```

---

## Secrets Summary Checklist

### Minimal (Dev Only)
- [ ] AWS_ACCESS_KEY_ID_DEV
- [ ] AWS_SECRET_ACCESS_KEY_DEV
- [ ] SLACK_BOT_TOKEN_DEV
- [ ] SLACK_SIGNING_SECRET_DEV

### Full Pipeline
- [ ] All dev secrets above
- [ ] AWS_ACCESS_KEY_ID_QA
- [ ] AWS_SECRET_ACCESS_KEY_QA
- [ ] SLACK_BOT_TOKEN_QA
- [ ] SLACK_SIGNING_SECRET_QA
- [ ] AWS_ACCESS_KEY_ID_PROD
- [ ] AWS_SECRET_ACCESS_KEY_PROD
- [ ] SLACK_BOT_TOKEN_PROD
- [ ] SLACK_SIGNING_SECRET_PROD
- [ ] GITHUB_TOKEN (for feature deployment)
- [ ] SLACK_WEBHOOK_URL (for notifications)
- [ ] PROD_APPROVERS (for prod approvals)

---

## Troubleshooting

### "AccessDenied" during deployment

**Issue:** IAM user doesn't have sufficient permissions

**Solution:**
```bash
# Check current policies
aws iam list-attached-user-policies --user-name carl-deployer-dev

# Attach AdministratorAccess (for testing)
aws iam attach-user-policy \
  --user-name carl-deployer-dev \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

### "Invalid Slack token"

**Issue:** Token format is incorrect or app not installed

**Solution:**
- Verify token starts with `xoxb-`
- Reinstall app to workspace
- Generate new token in Slack app settings

### "url_verification failed" in Slack

**Issue:** Slack can't verify webhook URL

**Solution:**
1. Check API endpoint is correct
2. Verify Lambda is deployed and running
3. Check Lambda logs:
```bash
aws logs tail /aws/lambda/carl-dev-api --follow
```

### GitHub Actions fails with "Secret not found"

**Issue:** Secret name doesn't match workflow

**Solution:**
- Check secret name matches exactly (case-sensitive)
- Verify secret is repository secret, not environment secret
- Re-add secret if necessary

---

## Security Best Practices

1. **Rotate AWS keys every 90 days**
   ```bash
   aws iam update-access-key --user-name carl-deployer-dev --access-key-id AKIAIOSFODNN7EXAMPLE --status Inactive
   ```

2. **Use separate AWS accounts for dev/qa/prod**
   - Prevents accidental prod changes from dev
   - Better cost tracking

3. **Restrict GitHub token scope**
   - Only give `repo` and `workflow` permissions
   - Regenerate if leaked

4. **Enable MFA for IAM users** (optional but recommended)
   ```bash
   aws iam enable-mfa-device --user-name carl-deployer-prod --serial-number arn:aws:iam::ACCOUNT:mfa/carl-deployer-prod --authentication-code1 123456 --authentication-code2 789012
   ```

5. **Audit secret access**
   - Monitor GitHub Actions logs
   - Enable AWS CloudTrail for API key usage

---

## Next Steps

After secrets are configured:

1. ✅ Deploy CARL minimal core to dev
2. ✅ Test `/carl hello` in Slack
3. ✅ Enable features as needed: `/carl enable monitoring`
4. ✅ Deploy to qa/prod when ready

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md)

---

**Last Updated:** 2026-01-27
