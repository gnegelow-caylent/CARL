# GitHub OIDC Provider and Roles for CARL Deployment
# This must be deployed ONCE per AWS account before deploying CARL

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.18"
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

  # ECR - Container Registry for Lambda images
  statement {
    sid    = "ECRAuthToken"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ECRRepositoryManagement"
    effect = "Allow"
    actions = [
      "ecr:CreateRepository",
      "ecr:DeleteRepository",
      "ecr:DescribeRepositories",
      "ecr:ListTagsForResource",
      "ecr:TagResource",
      "ecr:UntagResource",
      "ecr:PutLifecyclePolicy",
      "ecr:GetLifecyclePolicy",
      "ecr:DeleteLifecyclePolicy",
      "ecr:SetRepositoryPolicy",
      "ecr:GetRepositoryPolicy",
      "ecr:DeleteRepositoryPolicy",
      "ecr:PutImageScanningConfiguration",
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:ListImages"
    ]
    resources = [
      "arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/carl-*"
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

  # KMS - Key creation with tag condition
  statement {
    sid    = "KMSKeyCreation"
    effect = "Allow"
    actions = [
      "kms:CreateKey"
    ]
    resources = ["*"]
    condition {
      test     = "StringLike"
      variable = "aws:RequestTag/Project"
      values   = ["CARL"]
    }
  }

  # KMS - Alias creation (requires permission on alias resource)
  statement {
    sid    = "KMSAliasCreation"
    effect = "Allow"
    actions = [
      "kms:CreateAlias"
    ]
    resources = [
      "arn:aws:kms:${var.region}:${data.aws_caller_identity.current.account_id}:alias/carl-*",
      "arn:aws:kms:${var.region}:${data.aws_caller_identity.current.account_id}:key/*"
    ]
  }

  # KMS - Management operations on CARL keys
  statement {
    sid    = "KMSManagement"
    effect = "Allow"
    actions = [
      "kms:DeleteAlias",
      "kms:DescribeKey",
      "kms:GetKeyPolicy",
      "kms:PutKeyPolicy",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
      "kms:EnableKeyRotation",
      "kms:DisableKeyRotation",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:GetKeyRotationStatus",
      "kms:ListResourceTags",
      "kms:CreateGrant",
      "kms:RetireGrant",
      "kms:RevokeGrant"
    ]
    resources = ["*"]
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/Project"
      values   = ["CARL"]
    }
  }

  # KMS - List operations
  statement {
    sid    = "KMSList"
    effect = "Allow"
    actions = [
      "kms:ListAliases",
      "kms:ListKeys"
    ]
    resources = ["*"]
  }

  # Secrets Manager
  statement {
    sid    = "SecretsManagerManagement"
    effect = "Allow"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue",
      "secretsmanager:UpdateSecret",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource",
      "secretsmanager:ListSecrets",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:PutResourcePolicy",
      "secretsmanager:DeleteResourcePolicy"
    ]
    resources = [
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:carl/*"
    ]
  }

  # SNS
  statement {
    sid    = "SNSManagement"
    effect = "Allow"
    actions = [
      "sns:CreateTopic",
      "sns:DeleteTopic",
      "sns:GetTopicAttributes",
      "sns:SetTopicAttributes",
      "sns:Subscribe",
      "sns:Unsubscribe",
      "sns:TagResource",
      "sns:UntagResource",
      "sns:ListTagsForResource"
    ]
    resources = [
      "arn:aws:sns:${var.region}:${data.aws_caller_identity.current.account_id}:carl-*"
    ]
  }

  # EventBridge - Rules
  statement {
    sid    = "EventBridgeRules"
    effect = "Allow"
    actions = [
      "events:*"
    ]
    resources = [
      "arn:aws:events:${var.region}:${data.aws_caller_identity.current.account_id}:rule/carl-*"
    ]
  }

  # EventBridge - Event Buses
  statement {
    sid    = "EventBridgeBuses"
    effect = "Allow"
    actions = [
      "events:CreateEventBus",
      "events:DeleteEventBus",
      "events:DescribeEventBus",
      "events:PutPermission",
      "events:RemovePermission",
      "events:TagResource",
      "events:UntagResource",
      "events:ListTagsForResource"
    ]
    resources = [
      "arn:aws:events:${var.region}:${data.aws_caller_identity.current.account_id}:event-bus/carl-*"
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
      "bedrock:ListAgentAliases",
      "bedrock:TagResource",
      "bedrock:UntagResource",
      "bedrock:ListTagsForResource"
    ]
    resources = ["*"]
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

# Separate policy for AgentCore (to avoid policy size limits)
resource "aws_iam_policy" "carl_deployer_agentcore" {
  name        = "carl-deployer-agentcore-policy"
  description = "Policy for deploying AgentCore resources"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "BedrockAgentCoreManagement"
        Effect   = "Allow"
        Action   = "bedrock-agentcore:*"
        Resource = "*"
      },
      {
        Sid      = "AgentCoreServiceLinkedRole"
        Effect   = "Allow"
        Action   = "iam:CreateServiceLinkedRole"
        Resource = "arn:aws:iam::*:role/aws-service-role/agentcore.bedrock.amazonaws.com/*"
        Condition = {
          StringEquals = {
            "iam:AWSServiceName" = "agentcore.bedrock.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name      = "carl-deployer-agentcore-policy"
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

# Attach AgentCore policy to all deployment roles
resource "aws_iam_role_policy_attachment" "deployer_dev_agentcore" {
  role       = aws_iam_role.carl_deployer_dev.name
  policy_arn = aws_iam_policy.carl_deployer_agentcore.arn
}

resource "aws_iam_role_policy_attachment" "deployer_qa_agentcore" {
  role       = aws_iam_role.carl_deployer_qa.name
  policy_arn = aws_iam_policy.carl_deployer_agentcore.arn
}

resource "aws_iam_role_policy_attachment" "deployer_prod_agentcore" {
  role       = aws_iam_role.carl_deployer_prod.name
  policy_arn = aws_iam_policy.carl_deployer_agentcore.arn
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
