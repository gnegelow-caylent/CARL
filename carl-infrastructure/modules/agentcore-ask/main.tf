# AWS Bedrock AgentCore Ask Agent Module
# Deploys the /carl ask command to AgentCore Runtime using container deployment
# Container is built and pushed by GitHub Actions to shared ECR repo with tag "agentcore-ask"

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
  name = "${var.name_prefix}-agentcore-ask-role"

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

# IAM Policy for AgentCore Runtime
resource "aws_iam_role_policy" "agentcore_execution" {
  name = "agentcore-ask-execution-policy"
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
      # Note: Inference profiles route to multiple regions, so we allow all regions for foundation models
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
      # Invoke Lambda tools (only if tool_lambda_arn is provided)
      # For now, allow invoking any Lambda in this account (for future tool integration)
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${local.region}:${local.account_id}:function:*"
      },
      # AWS API Read permissions for scanning
      {
        Effect = "Allow"
        Action = [
          "iam:ListUsers",
          "iam:ListMFADevices",
          "iam:GetAccountPasswordPolicy",
          "ec2:DescribeVpcs",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeFlowLogs",
          "ec2:DescribeInstances",
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      },
      # S3 bucket-level permissions for scanning (explicit bucket ARN format)
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
          "s3:GetBucketEncryption",
          "s3:GetPublicAccessBlock",
          "s3:GetBucketVersioning",
          "s3:GetBucketPolicy",
          "s3:GetBucketAcl",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::*"
      }
    ]
  })
}

# AgentCore Runtime for Ask Agent
# NOTE: Container image must be pushed to ECR before creating the runtime.
# The GitHub Actions workflow handles this: push image first, then terraform apply.
resource "aws_bedrockagentcore_agent_runtime" "ask" {
  agent_runtime_name = "${local.safe_name_prefix}_ask_agent"
  description        = "CARL Ask Agent - intelligent Q&A with AWS environment scanning"
  role_arn           = aws_iam_role.agentcore_execution.arn

  # Container deployment (ARM64 built by GitHub Actions)
  # Uses shared ECR repo with tag "agentcore-ask"
  agent_runtime_artifact {
    container_configuration {
      container_uri = "${var.ecr_repository_url}:${var.container_image_tag}"
    }
  }

  environment_variables = merge(var.environment_variables, {
    AWS_REGION       = local.region
    FOUNDATION_MODEL = var.foundation_model
  })

  # Network configuration - using AWS managed networking
  network_configuration {
    network_mode = "PUBLIC"
  }

  tags = var.tags
}

# AgentCore Memory for persistent learning (optional)
resource "aws_bedrockagentcore_memory" "ask" {
  count = var.enable_memory ? 1 : 0

  name                  = "${local.safe_name_prefix}_ask_memory"
  description           = "Persistent memory for CARL Ask Agent"
  event_expiry_duration = 30 # 30 days (must be 7-365)

  tags = var.tags
}

# AgentCore Gateway for tools (optional)
resource "aws_bedrockagentcore_gateway" "ask_tools" {
  count = var.enable_gateway ? 1 : 0

  name            = "${local.safe_name_prefix}_ask_gateway"
  description     = "Gateway for CARL scanning tools"
  protocol_type   = "MCP"
  authorizer_type = "AWS_IAM"
  role_arn        = aws_iam_role.agentcore_execution.arn

  tags = var.tags
}
