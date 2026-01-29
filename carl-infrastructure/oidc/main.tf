# GitHub OIDC Provider and Roles for CARL Deployment
# This must be deployed ONCE per AWS account before deploying CARL

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
  region = var.region
}

data "aws_caller_identity" "current" {}

# ============================================================================
# GitHub OIDC Provider
# ============================================================================

data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]

  tags = {
    Name        = "github-oidc-provider"
    ManagedBy   = "Terraform"
    Description = "OIDC provider for GitHub Actions"
  }
}

# ============================================================================
# IAM Role for CARL Deployment (per environment)
# ============================================================================

# Trust policy that allows GitHub Actions from your repo to assume the role
data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    actions = ["sts:AssumeRoleWithWebIdentity"]

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      # Allow any branch in your repo
      values = ["repo:${var.github_org}/${var.github_repo}:*"]
    }
  }
}

# Deployment role for dev environment
resource "aws_iam_role" "carl_deployer_dev" {
  name               = "carl-deployer-dev"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
  description        = "Role for GitHub Actions to deploy CARL to dev environment"

  tags = {
    Name        = "carl-deployer-dev"
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}

# Deployment role for qa environment
resource "aws_iam_role" "carl_deployer_qa" {
  name               = "carl-deployer-qa"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
  description        = "Role for GitHub Actions to deploy CARL to qa environment"

  tags = {
    Name        = "carl-deployer-qa"
    Environment = "qa"
    ManagedBy   = "Terraform"
  }
}

# Deployment role for prod environment
resource "aws_iam_role" "carl_deployer_prod" {
  name               = "carl-deployer-prod"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json
  description        = "Role for GitHub Actions to deploy CARL to prod environment"

  tags = {
    Name        = "carl-deployer-prod"
    Environment = "prod"
    ManagedBy   = "Terraform"
  }
}

# ============================================================================
# IAM Policies for Deployment
# ============================================================================

# Policy for CARL deployment - least privilege
data "aws_iam_policy_document" "carl_deployer" {
  # Lambda
  statement {
    sid    = "LambdaManagement"
    effect = "Allow"
    actions = [
      "lambda:*"
    ]
    resources = [
      "arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:carl-*"
    ]
  }

  # API Gateway
  statement {
    sid    = "APIGatewayManagement"
    effect = "Allow"
    actions = [
      "apigateway:*"
    ]
    resources = [
      "arn:aws:apigateway:${var.region}::/apis*",
      "arn:aws:apigateway:${var.region}::/restapis*",
      "arn:aws:apigateway:${var.region}::/tags*"
    ]
  }

  # DynamoDB
  statement {
    sid    = "DynamoDBManagement"
    effect = "Allow"
    actions = [
      "dynamodb:*"
    ]
    resources = [
      "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/carl-*"
    ]
  }

  # S3
  statement {
    sid    = "S3Management"
    effect = "Allow"
    actions = [
      "s3:*"
    ]
    resources = [
      "arn:aws:s3:::carl-*",
      "arn:aws:s3:::carl-*/*"
    ]
  }

  # IAM (limited to CARL resources)
  statement {
    sid    = "IAMManagement"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:UpdateRole",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:ListRolePolicies",
      "iam:PassRole",
      "iam:TagRole",
      "iam:UntagRole"
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/carl-*"
    ]
  }

  # IAM (read-only for policy creation)
  statement {
    sid    = "IAMReadOnly"
    effect = "Allow"
    actions = [
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions"
    ]
    resources = ["*"]
  }

  # CloudWatch Logs
  statement {
    sid    = "CloudWatchLogsManagement"
    effect = "Allow"
    actions = [
      "logs:*"
    ]
    resources = [
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/carl-*",
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/apigateway/carl-*"
    ]
  }

  # CloudWatch Logs - DescribeLogGroups (requires wildcard resource)
  statement {
    sid    = "CloudWatchLogsDescribe"
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups"
    ]
    resources = ["*"]
  }

  # SSM Parameter Store
  statement {
    sid    = "SSMManagement"
    effect = "Allow"
    actions = [
      "ssm:PutParameter",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:DeleteParameter",
      "ssm:AddTagsToResource",
      "ssm:RemoveTagsFromResource",
      "ssm:ListTagsForResource"
    ]
    resources = [
      "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/*/carl/*"
    ]
  }

  # SSM Parameter Store - DescribeParameters (requires wildcard resource)
  statement {
    sid    = "SSMDescribe"
    effect = "Allow"
    actions = [
      "ssm:DescribeParameters"
    ]
    resources = ["*"]
  }

  # KMS
  statement {
    sid    = "KMSManagement"
    effect = "Allow"
    actions = [
      "kms:CreateKey",
      "kms:CreateAlias",
      "kms:DeleteAlias",
      "kms:DescribeKey",
      "kms:GetKeyPolicy",
      "kms:PutKeyPolicy",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
      "kms:EnableKeyRotation",
      "kms:DisableKeyRotation",
      "kms:ListAliases",
      "kms:ListKeys",
      "kms:TagResource",
      "kms:UntagResource"
    ]
    resources = ["*"]
    condition {
      test     = "StringLike"
      variable = "aws:RequestTag/Project"
      values   = ["CARL"]
    }
  }

  # EventBridge
  statement {
    sid    = "EventBridgeManagement"
    effect = "Allow"
    actions = [
      "events:*"
    ]
    resources = [
      "arn:aws:events:${var.region}:${data.aws_caller_identity.current.account_id}:rule/carl-*"
    ]
  }

  # Bedrock (model invocation)
  statement {
    sid    = "BedrockAccess"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:ListFoundationModels",
      "bedrock:GetFoundationModel"
    ]
    resources = [
      "arn:aws:bedrock:${var.region}::foundation-model/*"
    ]
  }

  # Bedrock Agent Management
  statement {
    sid    = "BedrockAgentManagement"
    effect = "Allow"
    actions = [
      "bedrock:CreateAgent",
      "bedrock:UpdateAgent",
      "bedrock:DeleteAgent",
      "bedrock:GetAgent",
      "bedrock:ListAgents",
      "bedrock:PrepareAgent",
      "bedrock:CreateAgentActionGroup",
      "bedrock:UpdateAgentActionGroup",
      "bedrock:DeleteAgentActionGroup",
      "bedrock:GetAgentActionGroup",
      "bedrock:ListAgentActionGroups",
      "bedrock:CreateAgentAlias",
      "bedrock:UpdateAgentAlias",
      "bedrock:DeleteAgentAlias",
      "bedrock:GetAgentAlias",
      "bedrock:ListAgentAliases"
    ]
    resources = [
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:agent/*",
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:agent-alias/*/*"
    ]
  }

  # EC2 (for VPC resource discovery)
  statement {
    sid    = "EC2ReadOnly"
    effect = "Allow"
    actions = [
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:DescribeVpcs",
      "ec2:DescribeAvailabilityZones"
    ]
    resources = ["*"]
  }

  # Terraform state management (S3 backend)
  statement {
    sid    = "TerraformStateAccess"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]
    resources = [
      "arn:aws:s3:::carl-tfstate-*",
      "arn:aws:s3:::carl-tfstate-*/*"
    ]
  }
}

resource "aws_iam_policy" "carl_deployer" {
  name        = "carl-deployer-policy"
  description = "Policy for deploying CARL infrastructure via GitHub Actions"
  policy      = data.aws_iam_policy_document.carl_deployer.json

  tags = {
    Name      = "carl-deployer-policy"
    ManagedBy = "Terraform"
  }
}

# Attach policy to all deployment roles
resource "aws_iam_role_policy_attachment" "deployer_dev" {
  role       = aws_iam_role.carl_deployer_dev.name
  policy_arn = aws_iam_policy.carl_deployer.arn
}

resource "aws_iam_role_policy_attachment" "deployer_qa" {
  role       = aws_iam_role.carl_deployer_qa.name
  policy_arn = aws_iam_policy.carl_deployer.arn
}

resource "aws_iam_role_policy_attachment" "deployer_prod" {
  role       = aws_iam_role.carl_deployer_prod.name
  policy_arn = aws_iam_policy.carl_deployer.arn
}

# ============================================================================
# Outputs
# ============================================================================

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}

output "deployer_role_arn_dev" {
  description = "ARN of the dev deployment role"
  value       = aws_iam_role.carl_deployer_dev.arn
}

output "deployer_role_arn_qa" {
  description = "ARN of the qa deployment role"
  value       = aws_iam_role.carl_deployer_qa.arn
}

output "deployer_role_arn_prod" {
  description = "ARN of the prod deployment role"
  value       = aws_iam_role.carl_deployer_prod.arn
}

output "next_steps" {
  description = "Next steps after OIDC setup"
  value       = <<-EOT
    ✅ GitHub OIDC Provider Created!

    Add these secrets to GitHub:
    1. Go to https://github.com/${var.github_org}/${var.github_repo}/settings/secrets/actions
    2. Add these repository secrets:

    AWS_ROLE_ARN_DEV=${aws_iam_role.carl_deployer_dev.arn}
    AWS_ROLE_ARN_QA=${aws_iam_role.carl_deployer_qa.arn}
    AWS_ROLE_ARN_PROD=${aws_iam_role.carl_deployer_prod.arn}
    AWS_REGION=${var.region}

    That's it! No access keys needed. GitHub Actions will use OIDC to assume these roles.

    Next: Deploy CARL
    cd ../core
    git push origin develop
  EOT
}
