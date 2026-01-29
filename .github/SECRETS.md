# GitHub Secrets Configuration

This document lists all required GitHub secrets for CARL's CI/CD pipelines.

## Required Secrets

### AWS Credentials

**AWS_ROLE_ARN_DEV**
- **Description:** IAM role ARN for deploying to dev environment
- **Format:** `arn:aws:iam::ACCOUNT_ID:role/github-actions-carl-dev`
- **Used by:**
  - `deploy-core.yml`
  - `integration-tests.yml` (scheduled runs)
  - `pr-validation.yml`
- **Permissions needed:**
  - Lambda: Read/Write
  - DynamoDB: Read/Write
  - S3: Read/Write
  - IAM: Read
  - SSM: Read
  - Secrets Manager: Read
  - CloudWatch Logs: Read

**AWS_ROLE_ARN_QA** (optional)
- **Description:** IAM role ARN for deploying to QA environment
- **Format:** `arn:aws:iam::ACCOUNT_ID:role/github-actions-carl-qa`
- **Used by:**
  - `deploy-core.yml` (QA deployments)
  - `integration-tests.yml` (QA tests)

**AWS_ROLE_ARN_PROD** (optional)
- **Description:** IAM role ARN for deploying to production environment
- **Format:** `arn:aws:iam::ACCOUNT_ID:role/github-actions-carl-prod`
- **Used by:**
  - `deploy-core.yml` (prod deployments)
  - `integration-tests.yml` (prod tests)

### Slack Notifications (optional)

**SLACK_WEBHOOK_URL**
- **Description:** Slack webhook URL for deployment notifications
- **Format:** `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`
- **Used by:**
  - `deploy-core.yml` (deployment status)
  - `integration-tests.yml` (test results)
- **How to create:**
  1. Go to https://api.slack.com/apps
  2. Create new app → From scratch
  3. Enable Incoming Webhooks
  4. Add New Webhook to Workspace
  5. Copy webhook URL

## Setting Secrets

### Via GitHub UI

1. Go to repository: https://github.com/YOUR_ORG/CARL
2. Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Enter name and value
5. Click "Add secret"

### Via GitHub CLI

```bash
# Set dev role ARN
gh secret set AWS_ROLE_ARN_DEV --body "arn:aws:iam::123456789012:role/github-actions-carl-dev"

# Set QA role ARN
gh secret set AWS_ROLE_ARN_QA --body "arn:aws:iam::123456789012:role/github-actions-carl-qa"

# Set Slack webhook
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/..."
```

## Creating IAM Roles for GitHub Actions

### Trust Policy (for OIDC)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/CARL:*"
        }
      }
    }
  ]
}
```

### Permissions Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:PublishVersion",
        "lambda:CreateAlias",
        "lambda:UpdateAlias"
      ],
      "Resource": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:carl-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/carl-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::carl-*",
        "arn:aws:s3:::carl-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "arn:aws:ssm:us-east-1:ACCOUNT_ID:parameter/*/carl/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:/carl/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:ACCOUNT_ID:log-group:/aws/lambda/carl-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

## OIDC Provider Setup

If you haven't set up GitHub's OIDC provider in AWS:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

## Verification

### Test AWS Role

```bash
# Manually trigger integration tests
gh workflow run integration-tests.yml --ref develop

# Check workflow status
gh run list --workflow=integration-tests.yml --limit 1
```

### Test Slack Webhook

```bash
curl -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Test notification from CARL CI/CD setup"
  }'
```

## Troubleshooting

### "terraform: command not found"
- **Cause:** Terraform not installed in workflow
- **Fix:** Already fixed in integration-tests.yml with `setup-terraform` action

### "Could not assume role with OIDC"
- **Cause:** Trust policy doesn't allow GitHub Actions
- **Fix:** Update IAM role trust policy with correct repository path

### "AccessDenied on Lambda/DynamoDB"
- **Cause:** IAM role lacks required permissions
- **Fix:** Add missing permissions to role's policy

### Scheduled tests not running
- **Cause:** Workflow disabled or missing AWS_ROLE_ARN_DEV secret
- **Fix:**
  1. Go to Actions → Integration Tests → Enable workflow
  2. Add AWS_ROLE_ARN_DEV secret

## Security Notes

- **Never commit secrets to git**
- Rotate secrets regularly (every 90 days recommended)
- Use least-privilege IAM policies
- Enable AWS CloudTrail for audit logging
- Use environment protection rules for prod deployments
- Require manual approval for prod deployments

## Next Steps

After configuring secrets:

1. Verify secrets are set: `gh secret list`
2. Run manual test: `gh workflow run integration-tests.yml --ref develop`
3. Check logs: `gh run view --log`
4. Scheduled tests will run daily at 6 AM UTC
