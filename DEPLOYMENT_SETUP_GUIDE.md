# CARL Deployment Setup Guide

**Target Environment:** New AWS Account
**Integrations:** Slack + Jira + GitHub CI/CD
**Starting Point:** Complete setup from scratch
**Estimated Setup Time:** 2-4 hours

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites Checklist](#prerequisites-checklist)
3. [AWS Account Configuration](#aws-account-configuration)
4. [Required Changes Before Deployment](#required-changes-before-deployment)
5. [Slack Integration Setup](#slack-integration-setup)
6. [Jira Integration Setup](#jira-integration-setup)
7. [GitHub Repository & CI/CD Setup](#github-repository--cicd-setup)
8. [Core Infrastructure Deployment](#core-infrastructure-deployment)
9. [Feature Modules Deployment](#feature-modules-deployment)
10. [Post-Deployment Validation](#post-deployment-validation)
11. [Troubleshooting](#troubleshooting)

---

## Overview

CARL (Cloud Automated Risk & Compliance Logic) is an AI-powered AWS compliance platform that runs entirely in your AWS account. This guide walks you through deploying CARL from scratch in a new AWS account with all integrations enabled.

### What You'll Deploy

- **Core Infrastructure**: Lambda functions, DynamoDB tables, S3 buckets, KMS keys
- **Compliance Monitoring**: Security Hub, GuardDuty, AWS Config integration
- **AI Services**: AWS Bedrock (Claude 3.5 Sonnet) for recommendations
- **Integrations**: Slack workspace bot, Jira Cloud sync, GitHub Actions CI/CD
- **Estimated Monthly Cost**: $75-200/month

---

## Prerequisites Checklist

### Required Accounts & Access

- [ ] **AWS Account** with administrator access
  - Root email access (for Bedrock model enablement)
  - CLI credentials configured (`aws configure`)
  - Default region set (recommend `us-east-1` for Bedrock availability)

- [ ] **Slack Workspace** with admin permissions
  - Ability to install Slack apps
  - Access to create slash commands

- [ ] **Jira Cloud Instance** with admin access
  - Ability to generate API tokens
  - Project key where findings will be created

- [ ] **GitHub Account** with repository admin access
  - Ability to create repositories
  - Access to configure GitHub Actions secrets

### Required Software

- [ ] **Terraform** >= 1.0 ([Install](https://www.terraform.io/downloads))
- [ ] **AWS CLI** >= 2.0 ([Install](https://aws.amazon.com/cli/))
- [ ] **Python** >= 3.12 ([Install](https://www.python.org/downloads/))
- [ ] **Git** ([Install](https://git-scm.com/downloads))
- [ ] **jq** (for JSON parsing) - `brew install jq` or `apt-get install jq`

### Verify Prerequisites

```bash
# Check versions
terraform version      # Should show v1.0+
aws --version         # Should show aws-cli/2.0+
python3 --version     # Should show Python 3.12+
git --version
jq --version

# Verify AWS credentials
aws sts get-caller-identity

# Should return your AWS account ID and user/role ARN
```

---

## AWS Account Configuration

### Step 1: Enable Required AWS Services

CARL requires several AWS services to be enabled in your account.

#### 1.1 Enable AWS Bedrock Model Access

```bash
# Navigate to AWS Console
# Go to: Bedrock > Model access (in left sidebar)
# Click "Manage model access"
# Enable the following models:
#   - Claude 3.5 Sonnet v2 (anthropic.claude-3-5-sonnet-20241022-v2:0)
#   - Claude 3 Haiku (anthropic.claude-3-haiku-20240307-v1:0)
# Click "Save changes"
# Wait 2-3 minutes for access to be granted

# Verify Bedrock access
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`)].modelId'

# Should return Claude model IDs
```

**IMPORTANT**: If you don't see the Bedrock service or can't request access, your account may need to be in a supported region. Bedrock is available in:
- us-east-1 (N. Virginia) - **RECOMMENDED**
- us-west-2 (Oregon)
- eu-west-1 (Ireland)
- ap-southeast-1 (Singapore)

#### 1.2 Enable Security Hub

```bash
# Enable Security Hub
aws securityhub enable-security-hub --region us-east-1

# Enable AWS Foundational Security Best Practices standard
aws securityhub batch-enable-standards \
  --standards-subscription-requests '[
    {
      "StandardsArn": "arn:aws:securityhub:us-east-1::standards/aws-foundational-security-best-practices/v/1.0.0"
    }
  ]'

# Verify Security Hub is enabled
aws securityhub describe-hub --region us-east-1
```

#### 1.3 Enable GuardDuty

```bash
# Enable GuardDuty
aws guardduty create-detector --enable --region us-east-1

# Get detector ID
DETECTOR_ID=$(aws guardduty list-detectors --region us-east-1 --query 'DetectorIds[0]' --output text)

# Verify GuardDuty is enabled
aws guardduty get-detector --detector-id $DETECTOR_ID --region us-east-1
```

#### 1.4 Enable AWS Config

```bash
# Create S3 bucket for Config recordings
aws s3 mb s3://config-recordings-$(aws sts get-caller-identity --query Account --output text) --region us-east-1

# Create IAM role for Config (required)
cat > /tmp/config-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "config.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name AWSConfigRole \
  --assume-role-policy-document file:///tmp/config-trust-policy.json

# Attach AWS managed policy
aws iam attach-role-policy \
  --role-name AWSConfigRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/ConfigRole

# Enable Config
aws configservice put-configuration-recorder \
  --configuration-recorder name=default,roleARN=arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/AWSConfigRole \
  --recording-group allSupported=true,includeGlobalResourceTypes=true

aws configservice put-delivery-channel \
  --delivery-channel name=default,s3BucketName=config-recordings-$(aws sts get-caller-identity --query Account --output text)

# Start Config recording
aws configservice start-configuration-recorder --configuration-recorder-name default
```

#### 1.5 Enable AWS Inspector (Optional but Recommended)

```bash
# Enable Inspector for EC2, ECR, Lambda scanning
aws inspector2 enable --resource-types EC2 ECR LAMBDA --region us-east-1
```

### Step 2: Create S3 Bucket for Terraform State

```bash
# Set variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION="us-east-1"
export TERRAFORM_STATE_BUCKET="carl-terraform-state-${AWS_ACCOUNT_ID}"
export TERRAFORM_STATE_LOCK_TABLE="carl-terraform-state-lock"

# Create S3 bucket
aws s3 mb s3://${TERRAFORM_STATE_BUCKET} --region ${AWS_REGION}

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket ${TERRAFORM_STATE_BUCKET} \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket ${TERRAFORM_STATE_BUCKET} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket ${TERRAFORM_STATE_BUCKET} \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name ${TERRAFORM_STATE_LOCK_TABLE} \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ${AWS_REGION}

echo "Terraform state bucket created: ${TERRAFORM_STATE_BUCKET}"
echo "DynamoDB lock table created: ${TERRAFORM_STATE_LOCK_TABLE}"
```

---

## Required Changes Before Deployment

Before you can deploy CARL, you need to update several configuration files with your specific AWS account details.

### Change 1: Update Terraform Backend Configuration

**File**: `carl-infrastructure/core/backend.tf`

```hcl
# CURRENT (placeholder values):
terraform {
  backend "s3" {
    bucket         = "carl-terraform-state-CHANGEME"
    key            = "core/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "carl-terraform-state-lock"
    encrypt        = true
  }
}

# CHANGE TO (use your values):
terraform {
  backend "s3" {
    bucket         = "carl-terraform-state-<YOUR_AWS_ACCOUNT_ID>"  # e.g., carl-terraform-state-123456789012
    key            = "core/terraform.tfstate"
    region         = "us-east-1"  # or your chosen region
    dynamodb_table = "carl-terraform-state-lock"
    encrypt        = true
  }
}
```

**Action**: Replace `<YOUR_AWS_ACCOUNT_ID>` with your actual AWS account ID.

### Change 2: Update Core Infrastructure Variables

**File**: `carl-infrastructure/core/variables.tf`

Review and update the following variables:

```hcl
variable "aws_region" {
  description = "AWS region for CARL deployment"
  type        = string
  default     = "us-east-1"  # CHANGE if using different region
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"  # CHANGE to "prod" for production deployment
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "CARL"
    ManagedBy   = "Terraform"
    Environment = "dev"  # CHANGE to match environment variable
  }
}
```

### Change 3: Update Lambda Function Configurations

**Files**: All module `main.tf` files with Lambda functions

Search for Lambda environment variables that need configuration:

```bash
# Find all Lambda environment variable configurations
cd /Users/gnegelow/Documents/carl
grep -r "SLACK_TOKEN_SECRET" carl-infrastructure/modules/*/main.tf
```

Ensure the following Lambda environment variables are configured:

```hcl
environment {
  variables = {
    ENVIRONMENT        = var.environment
    AWS_ACCOUNT_ID     = data.aws_caller_identity.current.account_id
    SLACK_TOKEN_SECRET = aws_secretsmanager_secret.slack_credentials.arn  # Should reference actual secret
    FINDINGS_TABLE     = aws_dynamodb_table.findings.name
    EVIDENCE_BUCKET    = aws_s3_bucket.evidence.bucket
    BEDROCK_MODEL_ID   = "anthropic.claude-3-5-sonnet-20241022-v2:0"
  }
}
```

### Change 4: Create GitHub Actions Secrets Configuration File

**File**: `carl-infrastructure/environments/dev/terraform.tfvars`

Create this file if it doesn't exist:

```hcl
# AWS Configuration
aws_region  = "us-east-1"  # CHANGE to your region
environment = "dev"

# Slack Configuration (will be added after Slack setup)
slack_bot_token       = ""  # Leave empty, will be stored in Secrets Manager
slack_signing_secret  = ""  # Leave empty, will be stored in Secrets Manager

# Jira Configuration (will be added after Jira setup)
jira_url       = ""  # e.g., "https://your-domain.atlassian.net"
jira_user      = ""  # Your Jira user email
jira_api_token = ""  # Leave empty, will be stored in Secrets Manager
jira_project   = ""  # e.g., "CARL"

# GitHub Configuration
github_repo = "your-username/carl"  # CHANGE to your GitHub repo

# Tags
tags = {
  Project     = "CARL"
  ManagedBy   = "Terraform"
  Environment = "dev"
  Owner       = "your-email@example.com"  # CHANGE to your email
}
```

### Change 5: Update GitHub Workflows with Your AWS Account ID

**Files**: `.github/workflows/*.yml`

Update all workflow files with your AWS account ID:

```bash
# Find all AWS account ID references in workflows
grep -r "123456789012" .github/workflows/
```

**Files to Update**:
1. `.github/workflows/deploy-core.yml`
2. `.github/workflows/deploy-features.yml`
3. `.github/workflows/integration-tests.yml`

**Change**:
```yaml
# CURRENT:
env:
  AWS_REGION: us-east-1
  AWS_ACCOUNT_ID: 123456789012  # CHANGE THIS

# TO:
env:
  AWS_REGION: us-east-1
  AWS_ACCOUNT_ID: <YOUR_AWS_ACCOUNT_ID>
```

### Change 6: Update Application Configuration

**File**: `carl-app/src/config.py` (if exists)

Verify or create configuration:

```python
import os

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ACCOUNT_ID = os.environ.get("AWS_ACCOUNT_ID")

# Bedrock Configuration
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20241022-v2:0"
)
BEDROCK_HAIKU_MODEL_ID = os.environ.get(
    "BEDROCK_HAIKU_MODEL_ID",
    "anthropic.claude-3-haiku-20240307-v1:0"
)

# DynamoDB Tables
FINDINGS_TABLE = os.environ.get("FINDINGS_TABLE", "carl-findings-dev")
EVIDENCE_TABLE = os.environ.get("EVIDENCE_TABLE", "carl-evidence-dev")
SCAN_HISTORY_TABLE = os.environ.get("SCAN_HISTORY_TABLE", "carl-scan-history-dev")
PREFERENCES_TABLE = os.environ.get("PREFERENCES_TABLE", "carl-preferences-dev")

# S3 Buckets
EVIDENCE_BUCKET = os.environ.get("EVIDENCE_BUCKET")
REPORTS_BUCKET = os.environ.get("REPORTS_BUCKET")

# Secrets
SLACK_TOKEN_SECRET = os.environ.get("SLACK_TOKEN_SECRET")
JIRA_TOKEN_SECRET = os.environ.get("JIRA_TOKEN_SECRET")
```

---

## Slack Integration Setup

### Step 1: Create Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Name: `CARL` (or your preferred name)
4. Workspace: Select your workspace
5. Click **"Create App"**

### Step 2: Configure OAuth & Permissions

1. In left sidebar, go to **OAuth & Permissions**
2. Scroll to **Scopes** → **Bot Token Scopes**
3. Add the following scopes:
   ```
   channels:history     - Read messages in public channels
   channels:read        - View basic channel info
   chat:write          - Send messages
   commands            - Add slash commands
   files:write         - Upload files
   users:read          - View users in workspace
   app_mentions:read   - View messages that mention @CARL
   im:history          - Read direct messages
   im:write            - Send direct messages
   ```
4. Scroll to top, click **"Install to Workspace"**
5. Authorize the app
6. **Save the Bot User OAuth Token** (starts with `xoxb-`)

### Step 3: Configure Slash Command

1. In left sidebar, go to **Slash Commands**
2. Click **"Create New Command"**
3. Configure:
   ```
   Command: /carl
   Request URL: https://PLACEHOLDER.execute-api.us-east-1.amazonaws.com/prod/slack/events
   Short Description: AI-powered AWS compliance assistant
   Usage Hint: [ask|scan|generate|bootstrap] <query>
   ```
4. Click **"Save"**

**Note**: The Request URL will be updated after deploying the API Gateway. For now, use a placeholder.

### Step 4: Enable Event Subscriptions

1. In left sidebar, go to **Event Subscriptions**
2. Toggle **"Enable Events"** to ON
3. Request URL: `https://PLACEHOLDER.execute-api.us-east-1.amazonaws.com/prod/slack/events`
4. Under **Subscribe to bot events**, add:
   ```
   app_mention        - When @CARL is mentioned
   message.channels   - Message posted to channel
   message.im         - Message posted in direct message
   ```
5. Click **"Save Changes"**

### Step 5: Configure Interactivity

1. In left sidebar, go to **Interactivity & Shortcuts**
2. Toggle **"Interactivity"** to ON
3. Request URL: `https://PLACEHOLDER.execute-api.us-east-1.amazonaws.com/prod/slack/events`
4. Click **"Save Changes"**

### Step 6: Get Signing Secret

1. In left sidebar, go to **Basic Information**
2. Scroll to **App Credentials**
3. **Save the Signing Secret** (click "Show" to reveal)

### Step 7: Store Slack Credentials in AWS Secrets Manager

```bash
# Set your Slack credentials
export SLACK_BOT_TOKEN="xoxb-your-bot-token-here"
export SLACK_SIGNING_SECRET="your-signing-secret-here"

# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name carl/slack/credentials \
  --description "CARL Slack integration credentials" \
  --secret-string "{
    \"bot_token\": \"${SLACK_BOT_TOKEN}\",
    \"signing_secret\": \"${SLACK_SIGNING_SECRET}\"
  }" \
  --region us-east-1

# Verify secret was created
aws secretsmanager describe-secret --secret-id carl/slack/credentials --region us-east-1
```

---

## Jira Integration Setup

### Step 1: Get Jira API Token

1. Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **"Create API token"**
3. Label: `CARL Integration`
4. Click **"Create"**
5. **Copy the API token** (you won't see it again)

### Step 2: Get Jira Configuration Details

```
Jira URL: https://your-domain.atlassian.net
Jira User Email: your-email@example.com
Jira Project Key: CARL (or your project key)
```

### Step 3: Store Jira Credentials in AWS Secrets Manager

```bash
# Set your Jira credentials
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_USER="your-email@example.com"
export JIRA_API_TOKEN="your-jira-api-token-here"
export JIRA_PROJECT="CARL"

# Create secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name carl/jira/credentials \
  --description "CARL Jira integration credentials" \
  --secret-string "{
    \"url\": \"${JIRA_URL}\",
    \"user\": \"${JIRA_USER}\",
    \"api_token\": \"${JIRA_API_TOKEN}\",
    \"project\": \"${JIRA_PROJECT}\"
  }" \
  --region us-east-1

# Verify secret was created
aws secretsmanager describe-secret --secret-id carl/jira/credentials --region us-east-1
```

### Step 4: Create Jira Project (if needed)

If you haven't created a Jira project yet:

1. Go to your Jira Cloud instance
2. Click **"Projects"** → **"Create project"**
3. Template: **Software development** or **IT service management**
4. Project name: `CARL Security Findings`
5. Project key: `CARL`
6. Click **"Create"**

---

## GitHub Repository & CI/CD Setup

### Step 1: Create GitHub Repository

```bash
# If you haven't already, create a GitHub repository
# Go to: https://github.com/new
# Repository name: carl
# Visibility: Private (recommended) or Public
# Do NOT initialize with README (we already have one)

# Add GitHub remote to your local repository
cd /Users/gnegelow/Documents/carl
git remote add origin https://github.com/YOUR_USERNAME/carl.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 2: Configure GitHub OIDC for AWS

CARL uses OpenID Connect (OIDC) to deploy to AWS without storing long-lived credentials.

```bash
# Run the bootstrap script to set up OIDC
cd /Users/gnegelow/Documents/carl
chmod +x bootstrap.sh
./bootstrap.sh

# This script will:
# 1. Create OIDC identity provider in AWS
# 2. Create IAM roles for GitHub Actions
# 3. Set up trust relationships
```

Alternatively, set up manually:

```bash
# Create OIDC provider
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"

# Create trust policy for GitHub Actions
cat > /tmp/github-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_USERNAME/carl:*"
        }
      }
    }
  ]
}
EOF

# Create IAM role for GitHub Actions
aws iam create-role \
  --role-name GitHubActionsCARL \
  --assume-role-policy-document file:///tmp/github-trust-policy.json

# Attach AdministratorAccess policy (or create more restrictive policy)
aws iam attach-role-policy \
  --role-name GitHubActionsCARL \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

echo "GitHub OIDC Role ARN:"
aws iam get-role --role-name GitHubActionsCARL --query 'Role.Arn' --output text
```

### Step 3: Configure GitHub Secrets

Add the following secrets to your GitHub repository:

1. Go to your GitHub repository
2. Settings → Secrets and variables → Actions
3. Click **"New repository secret"** for each:

```
AWS_REGION = us-east-1
AWS_ACCOUNT_ID = <your-aws-account-id>
AWS_ROLE_ARN = arn:aws:iam::<account-id>:role/GitHubActionsCARL
TERRAFORM_STATE_BUCKET = carl-terraform-state-<account-id>
```

### Step 4: Verify GitHub Actions Configuration

```bash
# Check workflow files exist
ls -la .github/workflows/

# Should see:
# - pr-validation.yml
# - deploy-core.yml
# - deploy-features.yml
# - integration-tests.yml
# - release.yml
```

---

## Core Infrastructure Deployment

### Step 1: Initialize Terraform

```bash
cd /Users/gnegelow/Documents/carl/carl-infrastructure/core

# Initialize Terraform (downloads providers and modules)
terraform init

# Expected output:
# Terraform has been successfully initialized!
```

### Step 2: Review Terraform Plan

```bash
# Generate and review execution plan
terraform plan -out=tfplan

# Review the plan carefully
# Should show creation of:
# - KMS keys
# - DynamoDB tables (12 tables)
# - S3 buckets (evidence, reports)
# - Lambda functions
# - API Gateway
# - IAM roles and policies
# - CloudWatch log groups
# - Secrets Manager secrets (if not created manually)
```

### Step 3: Deploy Core Infrastructure

```bash
# Apply the Terraform plan
terraform apply tfplan

# Type 'yes' when prompted
# Wait 5-10 minutes for deployment to complete

# Save outputs
terraform output -json > /tmp/carl-outputs.json

# Display important outputs
echo "API Gateway URL:"
terraform output -raw api_gateway_url

echo "Lambda Function ARN:"
terraform output -raw slack_router_function_arn
```

### Step 4: Update Slack App with API Gateway URL

After deployment, update the Slack app configuration:

1. Get the API Gateway URL:
   ```bash
   API_URL=$(terraform output -raw api_gateway_url)
   echo "Your API Gateway URL: ${API_URL}/slack/events"
   ```

2. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
3. Select your CARL app
4. Update the following sections with `${API_URL}/slack/events`:
   - **Slash Commands** → `/carl` → Request URL
   - **Event Subscriptions** → Request URL
   - **Interactivity & Shortcuts** → Request URL
5. Click **"Save Changes"** for each

### Step 5: Verify Core Deployment

```bash
# Test Lambda function
aws lambda invoke \
  --function-name carl-slack-router-dev \
  --payload '{"body": "{\"type\": \"url_verification\", \"challenge\": \"test\"}"}' \
  /tmp/response.json

cat /tmp/response.json
# Should show: {"challenge": "test"}

# Check DynamoDB tables
aws dynamodb list-tables --query 'TableNames[?starts_with(@, `carl-`)]'

# Should show:
# - carl-findings-dev
# - carl-evidence-dev
# - carl-scan-history-dev
# - carl-preferences-dev
# - carl-approvals-dev
# - carl-resource-graph-dev
# - carl-pricing-cache-dev
# - carl-learning-patterns-dev
# - carl-jira-mapping-dev
# - [3+ more tables]

# Check S3 buckets
aws s3 ls | grep carl

# Should show:
# - carl-evidence-<account-id>-dev
# - carl-reports-<account-id>-dev

# Check KMS keys
aws kms list-aliases --query 'Aliases[?contains(AliasName, `carl`)]'
```

---

## Feature Modules Deployment

After core infrastructure is deployed, you can deploy optional feature modules.

### Available Feature Modules

1. **scanning** - Security Hub findings integration
2. **drift** - Configuration drift detection
3. **bootstrap** - AWS environment automation
4. **compliance-agent** - Autonomous compliance assessment
5. **realtime-monitor** - Real-time security alerts
6. **remediation** - Auto-remediation engine
7. **reporting** - Advanced report generation

### Deploying Feature Modules

#### Option 1: Deploy via GitHub Actions (Recommended)

```bash
# Push your changes to GitHub
git add .
git commit -m "Initial CARL deployment"
git push origin main

# GitHub Actions will automatically deploy
# Monitor deployment at: https://github.com/YOUR_USERNAME/carl/actions
```

#### Option 2: Deploy Manually with Terraform

```bash
# Example: Deploy scanning module
cd /Users/gnegelow/Documents/carl/carl-infrastructure/modules/scanning

terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Repeat for other modules as needed
```

### Recommended Deployment Order

1. **Core** (already deployed)
2. **scanning** - Essential for compliance monitoring
3. **reporting** - Generate compliance reports
4. **drift** - Monitor infrastructure changes
5. **compliance-agent** - AI-powered assessments
6. **bootstrap** - Environment automation (if needed)
7. **realtime-monitor** - Real-time alerts
8. **remediation** - Auto-fix findings

---

## Post-Deployment Validation

### Step 1: Test Slack Integration

```bash
# In your Slack workspace, type:
/carl help

# Should respond with:
# CARL - Cloud Automated Risk & Compliance Logic
# Available commands:
# /carl ask <question>
# /carl scan
# /carl generate <pattern>
# /carl bootstrap
# [etc.]
```

### Step 2: Test AI Recommendations

```bash
# In Slack, type:
/carl ask How do I set up a secure VPC?

# Should respond with:
# - AI-generated recommendations
# - Relevant architecture patterns
# - Terraform code examples
```

### Step 3: Run Compliance Scan

```bash
# In Slack, type:
/carl scan

# Should respond with:
# Scanning your AWS environment...
# Found X findings across Y services
# - Critical: X
# - High: X
# - Medium: X
# [View full report]
```

### Step 4: Verify Jira Integration

```bash
# In Slack, type:
/carl scan

# Check your Jira project
# New issues should be created for each finding
# Issues should have:
# - Summary: Finding title
# - Description: Detailed finding info
# - Labels: SOC2 control mappings
# - Priority: Based on severity
```

### Step 5: Test Infrastructure Generation

```bash
# In Slack, type:
/carl generate secure s3 bucket

# Should respond with:
# - Terraform code for secure S3 bucket
# - Compliance controls covered
# - Estimated monthly cost
# - Option to download or save to repository
```

### Step 6: Check CloudWatch Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/carl-slack-router-dev --follow

# Test a Slack command, then watch logs in real-time
```

### Step 7: Verify DynamoDB Data

```bash
# Check scan history
aws dynamodb scan --table-name carl-scan-history-dev --limit 10

# Check pricing cache
aws dynamodb scan --table-name carl-pricing-cache-dev --limit 10

# Should show populated data after first scan
```

---

## Troubleshooting

### Issue: Slack Commands Not Responding

**Symptoms**: `/carl` command shows "Command not found" or no response

**Solutions**:
1. Verify API Gateway URL is configured in Slack app
2. Check Lambda function logs:
   ```bash
   aws logs tail /aws/lambda/carl-slack-router-dev --follow
   ```
3. Verify Slack credentials in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id carl/slack/credentials
   ```
4. Test Lambda function directly:
   ```bash
   aws lambda invoke \
     --function-name carl-slack-router-dev \
     --payload '{"body": "test"}' \
     /tmp/response.json
   ```

### Issue: Bedrock Access Denied

**Symptoms**: Error: "You don't have access to the model with the specified model ID"

**Solutions**:
1. Verify model access is enabled:
   ```bash
   aws bedrock list-foundation-models --region us-east-1 | grep claude
   ```
2. Check IAM permissions for Lambda execution role
3. Wait 5 minutes after enabling Bedrock access
4. Try different region (us-west-2, eu-west-1)

### Issue: Terraform State Lock Error

**Symptoms**: "Error acquiring the state lock"

**Solutions**:
```bash
# List locks
aws dynamodb scan --table-name carl-terraform-state-lock

# Force unlock (if no other apply is running)
terraform force-unlock <LOCK_ID>
```

### Issue: GitHub Actions Deployment Fails

**Symptoms**: "Error: Could not assume role"

**Solutions**:
1. Verify OIDC provider exists:
   ```bash
   aws iam list-open-id-connect-providers
   ```
2. Check IAM role trust policy allows your GitHub repo
3. Verify GitHub secrets are set correctly
4. Check workflow file references correct AWS region/account

### Issue: Jira Tickets Not Creating

**Symptoms**: Findings detected but no Jira tickets created

**Solutions**:
1. Verify Jira credentials in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id carl/jira/credentials
   ```
2. Test Jira API connection:
   ```bash
   curl -u "YOUR_EMAIL:YOUR_API_TOKEN" \
     https://your-domain.atlassian.net/rest/api/3/myself
   ```
3. Check Lambda logs for Jira errors:
   ```bash
   aws logs tail /aws/lambda/carl-slack-router-dev --follow
   ```
4. Verify Jira project key exists

### Issue: High Lambda Costs

**Symptoms**: Lambda costs higher than expected

**Solutions**:
1. Check Lambda metrics:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Invocations \
     --dimensions Name=FunctionName,Value=carl-slack-router-dev \
     --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 86400 \
     --statistics Sum
   ```
2. Enable pricing prefetch to reduce API calls
3. Increase Lambda memory to reduce execution time
4. Review CloudWatch logs for excessive invocations

### Issue: Security Hub Not Showing Findings

**Symptoms**: `/carl scan` shows "No findings detected"

**Solutions**:
1. Verify Security Hub is enabled:
   ```bash
   aws securityhub describe-hub
   ```
2. Wait 24 hours for initial findings to populate
3. Enable AWS Foundational Security Best Practices standard
4. Check Security Hub console manually

---

## Next Steps

After successful deployment:

1. **Configure Team Access**
   - Add team members to Slack workspace
   - Share `/carl` command documentation
   - Set up Slack channels for notifications

2. **Set Up Monitoring**
   - Configure CloudWatch alarms for Lambda errors
   - Set up billing alerts
   - Enable X-Ray tracing for Lambda functions

3. **Schedule Regular Scans**
   - Configure EventBridge rule for daily scans
   - Set up weekly compliance reports
   - Enable real-time monitoring for critical findings

4. **Customize CARL**
   - Add custom architecture patterns
   - Configure organization-specific compliance controls
   - Adjust AI prompts for your use case

5. **Review & Optimize**
   - Monitor costs in Cost Explorer
   - Review Lambda performance and optimize memory
   - Fine-tune DynamoDB capacity (if needed)

---

## Additional Resources

- **README**: `/Users/gnegelow/Documents/carl/README.md`
- **Architecture Guide**: `/Users/gnegelow/Documents/carl/ARCHITECTURE.md`
- **Slack Commands Reference**: `/Users/gnegelow/Documents/carl/SLACK_COMMANDS.md`
- **Deployment Notes**: `/Users/gnegelow/Documents/carl/DEPLOYMENT_NOTES.md`
- **Troubleshooting Guide**: `/Users/gnegelow/Documents/carl/TROUBLESHOOTING.md`
- **Session History**: `/Users/gnegelow/Documents/carl/SESSION_INDEX.md`

---

## Summary Checklist

Use this checklist to track your deployment progress:

- [ ] AWS Prerequisites
  - [ ] Bedrock model access enabled (Claude 3.5 Sonnet + Haiku)
  - [ ] Security Hub enabled
  - [ ] GuardDuty enabled
  - [ ] AWS Config enabled
  - [ ] Inspector enabled (optional)
  - [ ] Terraform state bucket created
  - [ ] DynamoDB lock table created

- [ ] Configuration Changes
  - [ ] Updated `backend.tf` with S3 bucket name
  - [ ] Updated `variables.tf` with AWS region and environment
  - [ ] Updated GitHub workflow files with AWS account ID
  - [ ] Created `terraform.tfvars` with configuration

- [ ] Slack Integration
  - [ ] Created Slack app
  - [ ] Configured OAuth scopes
  - [ ] Created `/carl` slash command
  - [ ] Enabled event subscriptions
  - [ ] Enabled interactivity
  - [ ] Stored credentials in Secrets Manager

- [ ] Jira Integration
  - [ ] Generated Jira API token
  - [ ] Created Jira project
  - [ ] Stored credentials in Secrets Manager

- [ ] GitHub CI/CD
  - [ ] Created GitHub repository
  - [ ] Configured OIDC provider in AWS
  - [ ] Created IAM role for GitHub Actions
  - [ ] Added GitHub secrets

- [ ] Core Deployment
  - [ ] Terraform init successful
  - [ ] Terraform plan reviewed
  - [ ] Core infrastructure deployed
  - [ ] API Gateway URL updated in Slack app

- [ ] Validation
  - [ ] Slack `/carl help` command works
  - [ ] AI recommendations working (`/carl ask`)
  - [ ] Compliance scan working (`/carl scan`)
  - [ ] Jira tickets creating automatically
  - [ ] Infrastructure generation working

---

**Deployment Complete!** 🎉

CARL is now deployed and operational in your AWS account. Start by running `/carl help` in Slack to explore available commands.
