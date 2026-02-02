# AWS Bedrock AgentCore Ask Agent Module
# Deploys the /carl ask command to AgentCore Runtime

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.18"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
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

# Create zip archive of agent code
data "archive_file" "agent_code" {
  type        = "zip"
  source_dir  = var.agent_source_path
  output_path = "${path.module}/.build/ask-agent.zip"
}

# Upload agent code to S3
resource "aws_s3_object" "agent_code" {
  bucket = var.code_bucket_name
  key    = "${var.code_object_prefix}/ask-agent.zip"
  source = data.archive_file.agent_code.output_path
  etag   = data.archive_file.agent_code.output_md5

  tags = var.tags
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
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.*",
          "arn:aws:bedrock:*:*:inference-profile/*anthropic*"
        ]
      },
      # S3 Code Access
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${var.code_bucket_arn}/*"
      },
      # Invoke Lambda tools
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = var.tool_lambda_arn
      }
    ]
  })
}

# Note: AmazonBedrockAgentCoreFullAccess managed policy doesn't exist yet
# AgentCore permissions are included in the inline policy above

# AgentCore Runtime for Ask Agent
resource "aws_bedrockagentcore_agent_runtime" "ask" {
  agent_runtime_name = "${local.safe_name_prefix}_ask_agent"
  description        = "CARL Ask Agent - intelligent Q&A with AWS environment scanning"
  role_arn           = aws_iam_role.agentcore_execution.arn

  # S3 code deployment (zip file required)
  agent_runtime_artifact {
    code_configuration {
      entry_point = ["carl_ask_agent.py"]
      runtime     = "PYTHON_3_12"

      code {
        s3 {
          bucket     = var.code_bucket_name
          object_key = aws_s3_object.agent_code.key
        }
      }
    }
  }

  depends_on = [aws_s3_object.agent_code]

  environment_variables = merge(var.environment_variables, {
    AWS_REGION       = local.region
    TOOL_LAMBDA_ARN  = var.tool_lambda_arn
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

# Note: Gateway Target removed for Phase 1 POC
# The agent invokes Lambda tools directly via IAM permissions
# Gateway targets with full tool schemas can be added later if needed
