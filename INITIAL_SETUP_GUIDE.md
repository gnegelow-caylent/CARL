# CARL Initial Setup Guide

This guide walks through the complete initial setup of CARL, including both the main CARL repository and the infrastructure deployments repository.

## Overview

CARL consists of two repositories:
1. **gnegelow-caylent/CARL** - Main application code and infrastructure definitions
2. **gnegelow-caylent/carl_infra** - GitOps repository for infrastructure deployments

## Current Status ✅

### CARL Repository (gnegelow-caylent/CARL)
- ✅ Code merged to `develop` branch
- ✅ GitHub Actions workflows configured
- ✅ GitHub Variables configured:
  - `TF_VAR_GITHUB_INFRA_OWNER` = `gnegelow-caylent`
  - `TF_VAR_GITHUB_INFRA_REPO` = `carl_infra`

### AWS Configuration
- ✅ GitHub token stored in Secrets Manager: `/carl/dev/github-infra-token`
- ✅ Terraform state backend ready:
  - S3 bucket: `carl-tfstate-403802364021`
  - DynamoDB table: `carl-tfstate-locks`

### Infrastructure Repository (carl_infra)
- ⏳ Repository exists but not configured yet
- ⏳ Needs GitHub secrets/variables
- ⏳ Needs branch structure and workflows

---

## Phase 1: Initial One-Time Setup (Do Once)

### Step 1: Set Up AWS IAM Roles for GitHub Actions

The carl_infra repository needs IAM roles to deploy infrastructure. These use OIDC (no long-lived credentials).

#### Create OIDC Provider (if not exists)

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 1c58a3a8518e8759bf075b76b750d4f2df264fcd
```

#### Create IAM Roles

**Option A: Using Terraform** (Recommended)

Create a file `carl-infrastructure/github-roles/main.tf`:

```hcl
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

# OIDC Provider for GitHub Actions
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# Plan Role (Read-Only)
resource "aws_iam_role" "github_plan_dev" {
  name = "carl-github-plan-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:gnegelow-caylent/carl_infra:*"
        }
      }
    }]
  })

  tags = {
    Project = "CARL"
    Purpose = "GitHub Actions Terraform Plan"
  }
}

resource "aws_iam_role_policy_attachment" "github_plan_readonly" {
  role       = aws_iam_role.github_plan_dev.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Apply Role (Write Access)
resource "aws_iam_role" "github_apply_dev" {
  name = "carl-github-apply-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:gnegelow-caylent/carl_infra:*"
        }
      }
    }]
  })

  tags = {
    Project = "CARL"
    Purpose = "GitHub Actions Terraform Apply"
  }
}

# Custom policy for apply role (adjust permissions as needed)
resource "aws_iam_role_policy" "github_apply_permissions" {
  name = "terraform-apply-permissions"
  role = aws_iam_role.github_apply_dev.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:*",
          "vpc:*",
          "s3:*",
          "dynamodb:*",
          "lambda:*",
          "iam:*",
          "kms:*",
          "cloudwatch:*",
          "logs:*",
          "rds:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::carl-tfstate-${local.account_id}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem"
        ]
        Resource = "arn:aws:dynamodb:*:${local.account_id}:table/carl-tfstate-locks"
      }
    ]
  })
}

output "plan_role_arn" {
  value = aws_iam_role.github_plan_dev.arn
}

output "apply_role_arn" {
  value = aws_iam_role.github_apply_dev.arn
}
```

Deploy:
```bash
cd carl-infrastructure/github-roles
terraform init
terraform apply
```

Save the output ARNs - you'll need them for GitHub secrets.

### Step 2: Configure Slack Webhook

Get your Slack webhook URL from: https://api.slack.com/apps

Or create a new incoming webhook:
1. Go to https://api.slack.com/apps
2. Select your CARL app
3. Navigate to "Incoming Webhooks"
4. Add new webhook to workspace
5. Copy the webhook URL (format: `https://hooks.slack.com/services/...`)

### Step 3: Configure carl_infra Repository

#### A. Create Repository Variables (Not Sensitive)

```bash
# Using GitHub API
export GITHUB_TOKEN="YOUR_GITHUB_TOKEN_HERE"

# AWS Account ID
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/gnegelow-caylent/carl_infra/actions/variables" \
  -d '{
    "name": "AWS_ACCOUNT_ID",
    "value": "403802364021"
  }'

# AWS Role ARNs (from Step 1 output)
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/gnegelow-caylent/carl_infra/actions/variables" \
  -d '{
    "name": "AWS_ROLE_ARN_DEV_PLAN",
    "value": "arn:aws:iam::403802364021:role/carl-github-plan-dev"
  }'

curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/gnegelow-caylent/carl_infra/actions/variables" \
  -d '{
    "name": "AWS_ROLE_ARN_DEV_APPLY",
    "value": "arn:aws:iam::403802364021:role/carl-github-apply-dev"
  }'
```

Or via GitHub UI:
- Go to: https://github.com/gnegelow-caylent/carl_infra/settings/variables/actions
- Click "New repository variable"
- Add each variable

#### B. Create Repository Secrets (Sensitive)

You'll need to encrypt secrets before uploading via API. It's easier to use the UI:

Go to: https://github.com/gnegelow-caylent/carl_infra/settings/secrets/actions

Add secret:
- **Name**: `SLACK_WEBHOOK_CARL`
- **Value**: Your Slack webhook URL from Step 2

### Step 4: Set Up carl_infra Repository Structure

Run the setup script:

```bash
/private/tmp/claude/-Users-gnegelow/e0ec1bd1-774c-47f5-a280-c61be1310620/scratchpad/setup_carl_infra_repo.sh
```

This will:
- Clone/update the repository
- Create directory structure
- Add GitHub Actions workflows
- Create branches (main, develop, qa)
- Push changes

### Step 5: Configure Branch Protection

Go to: https://github.com/gnegelow-caylent/carl_infra/settings/branches

**Protect `develop` branch:**
- Branch name pattern: `develop`
- ☑️ Require status checks to pass before merging
  - Required checks: `validate`
- ☐ Require approvals: 0

**Protect `main` branch:**
- Branch name pattern: `main`
- ☑️ Require status checks to pass before merging
  - Required checks: `validate`, `plan-prod`
- ☑️ Require approvals: 1

---

## Phase 2: Testing the Setup

### Test 1: Verify GitHub Configuration

```bash
export GITHUB_TOKEN="YOUR_GITHUB_TOKEN_HERE"

# Check CARL repo variables
echo "=== CARL Repository ==="
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/gnegelow-caylent/CARL/actions/variables" | \
  jq -r '.variables[] | "\(.name) = \(.value)"'

# Check carl_infra repo configuration
echo ""
echo "=== carl_infra Repository ==="
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/gnegelow-caylent/carl_infra/actions/variables" | \
  jq -r '.variables[] | "\(.name) = \(.value)"'

echo ""
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/repos/gnegelow-caylent/carl_infra/actions/secrets" | \
  jq -r '.secrets[] | "SECRET: \(.name)"'
```

### Test 2: Verify AWS Configuration

```bash
# Check GitHub token in Secrets Manager
aws secretsmanager describe-secret \
  --secret-id /carl/dev/github-infra-token \
  --region us-east-1

# Check Lambda configuration
aws lambda get-function-configuration \
  --function-name carl-dev-api \
  --region us-east-1 \
  --query 'Environment.Variables.{Owner:GITHUB_INFRA_OWNER,Repo:GITHUB_INFRA_REPO,Token:GITHUB_INFRA_TOKEN_SECRET}'
```

### Test 3: Test End-to-End Flow (When Ready)

Once Lambda is deployed with new code:

```
/carl build networking/basic-vpc
```

Expected behavior:
1. ✅ CARL generates Terraform code
2. ✅ Creates PR in carl_infra repository
3. ✅ Posts to Slack with PR link
4. ✅ GitHub Actions validate code
5. ✅ GitHub Actions generate plan
6. ✅ Plan posted to Slack

---

## Phase 3: Ongoing Operations

### Deploying New CARL Features

When you merge code to `develop` in the CARL repo:

1. GitHub Actions automatically runs `deploy-core.yml`
2. Validates code
3. Builds Lambda package
4. Runs `terraform plan`
5. Deploys infrastructure changes

### Deploying User-Generated Infrastructure

When users run `/carl build <blueprint>`:

1. CARL creates PR in carl_infra repo
2. GitHub Actions validate and plan
3. Team reviews PR
4. Merge PR
5. Manually trigger apply workflow
6. Infrastructure deployed

---

## Architecture Decision: Why Two Repos?

### CARL Repository (gnegelow-caylent/CARL)
**Purpose**: Application code and infrastructure definitions
**Deployment**: CI/CD via GitHub Actions
**Who deploys**: Automated on merge
**Contents**:
- Python application code
- Terraform modules for CARL itself
- CARL's own infrastructure

### Infrastructure Repository (carl_infra)
**Purpose**: User-generated infrastructure code
**Deployment**: GitOps with manual approval
**Who deploys**: Users via PR review
**Contents**:
- Terraform code generated by CARL
- Deployed via `/carl build` commands
- Requires review before deployment

**Benefits**:
1. **Separation of Concerns**: CARL's own infra separate from user infra
2. **Audit Trail**: All user infrastructure changes tracked in PRs
3. **Review Process**: Team can review before infrastructure is created
4. **Rollback**: Easy to revert PRs if needed
5. **Security**: No direct deployment from Slack

---

## Troubleshooting

### Issue: "Resource already managed by Terraform"

**Cause**: S3 bucket `carl-tfstate-403802364021` already exists
**Solution**: This is expected - the bucket was created manually. GitHub Actions will handle the state.

### Issue: "GitHub token invalid"

**Cause**: Token missing scopes
**Solution**: Generate new token with scopes: `repo`, `workflow`

### Issue: "IAM role not assumable"

**Cause**: Trust policy doesn't allow GitHub Actions
**Solution**: Verify the trust policy includes the correct repository name

---

## Summary Checklist

Before first use:
- [ ] IAM roles created (plan & apply)
- [ ] Slack webhook configured
- [ ] carl_infra repository configured with secrets/variables
- [ ] carl_infra repository has workflows
- [ ] Branch protection rules configured
- [ ] GitHub token stored in AWS Secrets Manager
- [ ] Lambda deployed with new code

After initial setup:
- [ ] Test `/carl build` command
- [ ] Verify PR created in carl_infra
- [ ] Verify GitHub Actions run successfully
- [ ] Verify plan posted to Slack

---

## Next Steps

1. Complete Phase 1 (one-time setup)
2. Deploy Lambda with new code
3. Run test build in Slack
4. Verify end-to-end flow

See also:
- [DEPLOYMENT_WORKFLOW.md](./DEPLOYMENT_WORKFLOW.md) - User guide
- [SETUP_YOUR_REPO.md](./SETUP_YOUR_REPO.md) - Repository-specific setup
