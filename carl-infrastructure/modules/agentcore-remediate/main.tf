# AWS Bedrock AgentCore Remediation Agent Module
# Deploys the /carl remediate command to AgentCore Runtime
# Container is built and pushed by GitHub Actions to shared ECR repo with tag "agentcore-remediate"

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.18"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.id
  # AgentCore names can only contain letters, numbers, and underscores (no hyphens)
  safe_name_prefix = replace(var.name_prefix, "-", "_")
}

# IAM Role for AgentCore Runtime
resource "aws_iam_role" "agentcore_execution" {
  name = "${var.name_prefix}-agentcore-remediate-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
          ArnLike = {
            "aws:SourceArn" = "arn:aws:bedrock-agentcore:${local.region}:${local.account_id}:runtime/*"
          }
        }
      }
    ]
  })

  tags = var.tags
}

# IAM Policy for AgentCore Runtime - Remediation requires more permissions
resource "aws_iam_role_policy" "agentcore_execution" {
  name = "agentcore-remediate-execution-policy"
  role = aws_iam_role.agentcore_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch Logs
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
      },
      # X-Ray Tracing
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      },
      # CloudWatch Metrics
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "bedrock-agentcore"
          }
        }
      },
      # Bedrock Model Invocation
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.*",
          "arn:aws:bedrock:*:*:inference-profile/*anthropic*"
        ]
      },
      # AWS Marketplace permissions (required for Bedrock model access)
      {
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe"
        ]
        Resource = "*"
      },
      # ECR Image Pull
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = var.ecr_repository_arn
      },
      # DynamoDB - Read/Write for findings and remediations
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.name_prefix}-findings",
          "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.name_prefix}-findings/index/*",
          "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.name_prefix}-remediations",
          "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.name_prefix}-remediations/index/*",
          "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.name_prefix}-approvals",
          "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.name_prefix}-approvals/index/*"
        ]
      },
      # IAM - Read for scanning, Write for password policy
      {
        Effect = "Allow"
        Action = [
          "iam:ListUsers",
          "iam:ListMFADevices",
          "iam:GetAccountPasswordPolicy",
          "iam:UpdateAccountPasswordPolicy"
        ]
        Resource = "*"
      },
      # S3 - List and Read for scanning
      {
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetEncryptionConfiguration",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetBucketVersioning",
          "s3:GetBucketPolicy",
          "s3:GetBucketAcl",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::*"
      },
      # S3 - Write for remediation (encryption, versioning, public access block)
      {
        Effect = "Allow"
        Action = [
          "s3:PutEncryptionConfiguration",
          "s3:PutBucketVersioning",
          "s3:PutBucketPublicAccessBlock"
        ]
        Resource = "arn:aws:s3:::*"
      },
      # EC2 - Read for scanning VPCs, security groups, flow logs
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeVpcs",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeFlowLogs",
          "ec2:DescribeInstances",
          "ec2:DescribeNetworkAcls",
          "ec2:DescribeSubnets"
        ]
        Resource = "*"
      },
      # EC2 - Write for VPC flow logs (MEDIUM risk - requires PR)
      # Note: In practice, these changes should go through PR, not direct API
      # Kept here for potential future direct apply of flow logs
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateFlowLogs",
          "ec2:DeleteFlowLogs"
        ]
        Resource = "*"
      },
      # CloudWatch Logs - For VPC Flow Logs destination
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:CreateLogGroup",
          "logs:PutRetentionPolicy"
        ]
        Resource = "arn:aws:logs:${local.region}:${local.account_id}:log-group:*"
      },
      # STS for identity
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      },
      # Secrets Manager - Read GitHub token for PR creation
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:${var.name_prefix}-github-token*"
        ]
      }
    ]
  })
}

# AgentCore Runtime for Remediation Agent
resource "aws_bedrockagentcore_agent_runtime" "remediate" {
  agent_runtime_name = "${local.safe_name_prefix}_remediate_agent"
  description        = "CARL Remediation Agent - AI-powered security fixes with human approval"
  role_arn           = aws_iam_role.agentcore_execution.arn

  # Container deployment (ARM64 built by GitHub Actions)
  agent_runtime_artifact {
    container_configuration {
      container_uri = "${var.ecr_repository_url}:${var.container_image_tag}"
    }
  }

  environment_variables = merge(var.environment_variables, {
    AWS_REGION         = local.region
    FOUNDATION_MODEL   = var.foundation_model
    FINDINGS_TABLE     = "${var.name_prefix}-findings"
    REMEDIATIONS_TABLE = "${var.name_prefix}-remediations"
    GITHUB_SECRET_ARN  = "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:${var.name_prefix}-github-token"
  })

  # Network configuration - using AWS managed networking
  network_configuration {
    network_mode = "PUBLIC"
  }

  tags = var.tags
}

# AgentCore Memory for remediation history (optional)
resource "aws_bedrockagentcore_memory" "remediate" {
  count = var.enable_memory ? 1 : 0

  name                  = "${local.safe_name_prefix}_remediate_memory"
  description           = "Persistent memory for CARL Remediation Agent - tracks fix history"
  event_expiry_duration = 30 # 30 days

  tags = var.tags
}

# AgentCore Gateway for remediation tools (optional)
resource "aws_bedrockagentcore_gateway" "remediate_tools" {
  count = var.enable_gateway ? 1 : 0

  name            = "${local.safe_name_prefix}_remediate_gateway"
  description     = "Gateway for CARL remediation tools"
  protocol_type   = "MCP"
  authorizer_type = "AWS_IAM"
  role_arn        = aws_iam_role.agentcore_execution.arn

  tags = var.tags
}
