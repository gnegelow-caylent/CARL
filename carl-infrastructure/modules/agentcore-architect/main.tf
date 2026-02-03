# AWS Bedrock AgentCore Architect Agent Module
# Deploys the architecture recommendation agent to AgentCore Runtime
# Container is built and pushed by GitHub Actions to shared ECR repo

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
  # AgentCore names can only contain letters, numbers, and underscores
  safe_name_prefix = replace(var.name_prefix, "-", "_")
}

# IAM Role for AgentCore Runtime
resource "aws_iam_role" "agentcore_execution" {
  name = "${var.name_prefix}-agentcore-architect-role"

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
  name = "agentcore-architect-execution-policy"
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
      # DynamoDB for pricing cache (read-only)
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${var.name_prefix}-pricing-cache"
      }
    ]
  })
}

# AgentCore Runtime for Architect Agent
resource "aws_bedrockagentcore_agent_runtime" "architect" {
  agent_runtime_name = "${local.safe_name_prefix}_architect_agent"
  description        = "CARL Architect Agent - architecture recommendations with cost estimates"
  role_arn           = aws_iam_role.agentcore_execution.arn

  # Container deployment
  agent_runtime_artifact {
    container_configuration {
      container_uri = "${var.ecr_repository_url}:${var.container_image_tag}"
    }
  }

  environment_variables = merge(var.environment_variables, {
    AWS_REGION       = local.region
    FOUNDATION_MODEL = var.foundation_model
  })

  # Network configuration
  network_configuration {
    network_mode = "PUBLIC"
  }

  tags = var.tags
}
