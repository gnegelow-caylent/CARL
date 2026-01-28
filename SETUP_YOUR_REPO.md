# Setup Guide for carl_infra Repository

Your specific repository: https://github.com/gnegelow-caylent/carl_infra

## Quick Setup (5 minutes)

### Step 1: Store GitHub Token

```bash
# Replace with your actual GitHub token
aws secretsmanager create-secret \
  --name /carl/dev/github-infra-token \
  --description "GitHub token for CARL infrastructure repo" \
  --secret-string "ghp_YOUR_TOKEN_HERE" \
  --region us-east-1
```

**If secret already exists:**
```bash
aws secretsmanager update-secret \
  --secret-id /carl/dev/github-infra-token \
  --secret-string "ghp_YOUR_TOKEN_HERE" \
  --region us-east-1
```

### Step 2: Configure CARL Infrastructure

```bash
cd /Users/gnegelow/Documents/CARL/carl-infrastructure/core

# Add to terraform.tfvars
cat >> terraform.tfvars << 'EOF'

# GitHub Infrastructure Repository
github_infra_owner = "gnegelow-caylent"
github_infra_repo  = "carl_infra"
EOF

# Apply changes
terraform apply
```

### Step 3: Set Up Your Repository

Run the automated setup script:

```bash
/private/tmp/claude/-Users-gnegelow/e0ec1bd1-774c-47f5-a280-c61be1310620/scratchpad/setup_carl_infra_repo.sh
```

This will:
- Clone/update your repository
- Create directory structure
- Add workflow files
- Create branches (main, develop, qa)
- Commit and push changes

### Step 4: Configure GitHub Settings

#### A. Set Up GitHub Secrets

Go to: https://github.com/gnegelow-caylent/carl_infra/settings/secrets/actions

Add these secrets:

```
AWS_ACCOUNT_ID=<your-aws-account-id>
AWS_ROLE_ARN_DEV_PLAN=arn:aws:iam::<account-id>:role/carl-github-plan-dev
AWS_ROLE_ARN_DEV_APPLY=arn:aws:iam::<account-id>:role/carl-github-apply-dev
SLACK_WEBHOOK_CARL=<your-slack-webhook-url>
```

#### B. Set Up Branch Protection

Go to: https://github.com/gnegelow-caylent/carl_infra/settings/branches

**Protect `develop` branch:**
- Branch name pattern: `develop`
- ☑️ Require status checks to pass before merging
  - Required checks: `validate`
- ☑️ Require conversation resolution before merging
- ☐ Require approvals: 0 (for dev, it's optional)

**Protect `qa` branch:**
- Branch name pattern: `qa`
- ☑️ Require status checks to pass before merging
  - Required checks: `validate`, `plan-qa`
- ☑️ Require approvals: 1
- ☑️ Require conversation resolution before merging

**Protect `main` branch:**
- Branch name pattern: `main`
- ☑️ Require status checks to pass before merging
  - Required checks: `validate`, `plan-prod`
- ☑️ Require approvals: 2
- ☑️ Require conversation resolution before merging

#### C. Create GitHub Environments

Go to: https://github.com/gnegelow-caylent/carl_infra/settings/environments

Create these environments:
- **dev-plan** (no protection)
- **dev-apply** (no protection)
- **qa-plan** (no protection)
- **qa-apply** (1 required reviewer)
- **prod-plan** (no protection)
- **prod-apply** (2 required reviewers, 30 min wait)

### Step 5: Set Up AWS IAM Roles

You need to create GitHub OIDC provider and IAM roles. Here's a minimal Terraform config:

```hcl
# oidc-provider.tf
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]
}

# Plan role (read-only)
resource "aws_iam_role" "github_plan_dev" {
  name = "carl-github-plan-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
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
}

# Attach read-only policies to plan role
resource "aws_iam_role_policy_attachment" "github_plan_readonly" {
  role       = aws_iam_role.github_plan_dev.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Apply role (write access)
resource "aws_iam_role" "github_apply_dev" {
  name = "carl-github-apply-dev"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
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
}

# Attach admin policies to apply role (or create custom policy with needed permissions)
resource "aws_iam_role_policy_attachment" "github_apply_admin" {
  role       = aws_iam_role.github_apply_dev.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
```

Save this to a file and apply:

```bash
terraform init
terraform apply
```

## Verification

### Test the Complete Flow

1. **Verify Lambda Configuration:**
```bash
aws lambda get-function-configuration \
  --function-name carl-dev-api \
  --query 'Environment.Variables.{Owner:GITHUB_INFRA_OWNER,Repo:GITHUB_INFRA_REPO,Token:GITHUB_INFRA_TOKEN_SECRET}' \
  --output table
```

Expected output:
```
+--------------------------------------------------+
|         GetFunctionConfiguration                 |
+------------------+-------------------------------+
|      Owner       |      gnegelow-caylent        |
|      Repo        |         carl_infra           |
|      Token       | /carl/dev/github-infra-token |
+------------------+-------------------------------+
```

2. **Test in Slack:**
```
/carl build networking/basic-vpc
```

You should see:
- ✅ Slack message with summary and PR link
- ✅ GitHub PR created in https://github.com/gnegelow-caylent/carl_infra/pulls
- ✅ GitHub Actions validating the code
- ✅ Plan posted to PR comments
- ✅ Plan notification in Slack

3. **Check the PR:**
- Go to: https://github.com/gnegelow-caylent/carl_infra/pulls
- You should see a PR with title "Deploy networking/basic-vpc"
- Files should be in: `deployments/users/{user-id}/networking-basic-vpc/{timestamp}/`

## Troubleshooting

### Token Not Found Error

```bash
# Verify secret exists
aws secretsmanager describe-secret \
  --secret-id /carl/dev/github-infra-token \
  --region us-east-1
```

### Permission Denied from Lambda

```bash
# Check Lambda execution role has secrets manager permission
aws iam get-role-policy \
  --role-name carl-dev-lambda-role \
  --policy-name secrets-manager-access
```

### GitHub API Error

```bash
# Test GitHub token
curl -H "Authorization: Bearer ghp_YOUR_TOKEN" \
  https://api.github.com/repos/gnegelow-caylent/carl_infra
```

## Summary

Your configuration:
- **Repository**: https://github.com/gnegelow-caylent/carl_infra
- **Owner**: `gnegelow-caylent`
- **Repo Name**: `carl_infra`
- **Token Location**: AWS Secrets Manager `/carl/dev/github-infra-token`

After completing these steps, when you run `/carl build <blueprint>` in Slack:
1. CARL generates Terraform code
2. Creates PR in your carl_infra repository
3. GitHub Actions validate and plan
4. You review and merge in GitHub
5. Manually trigger apply workflow

## Next Steps

After successful setup:
1. Read the [Deployment Workflow Guide](./DEPLOYMENT_WORKFLOW.md)
2. Try building different blueprints with `/carl blueprints`
3. Review the workflows in `.github/workflows/` to customize as needed
