# CARL Foundation Module
# Creates all core infrastructure resources for CARL

terraform {
  required_version = ">= 1.0"
}

# ============================================================================
# Data Sources
# ============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ============================================================================
# KMS Key for Encryption
# ============================================================================

# Use existing KMS key (created by core infrastructure)
data "aws_kms_alias" "carl" {
  name = "alias/${var.project_name}-${var.environment}"
}

# Uncomment to create new key if needed
# resource "aws_kms_key" "carl" {
#   description             = "CARL encryption key for ${var.environment}"
#   deletion_window_in_days = 30
#   enable_key_rotation     = true
#
#   policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [...]
#   })
#   tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-key" })
# }

resource "aws_kms_alias" "carl" {
  name          = "alias/${var.project_name}-${var.environment}"
  target_key_id = data.aws_kms_alias.carl.target_key_id
}

# ============================================================================
# S3 Buckets
# ============================================================================

# Evidence Storage
resource "aws_s3_bucket" "evidence" {
  bucket = "${var.project_name}-${var.environment}-evidence-${data.aws_caller_identity.current.account_id}"
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-evidence"
    }
  )
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = data.aws_kms_alias.carl.target_key_arn
    }
  }
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Reports Storage
resource "aws_s3_bucket" "reports" {
  bucket = "${var.project_name}-${var.environment}-reports-${data.aws_caller_identity.current.account_id}"
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-reports"
    }
  )
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = data.aws_kms_alias.carl.target_key_arn
    }
  }
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ============================================================================
# DynamoDB Tables
# ============================================================================

# Findings Table
resource "aws_dynamodb_table" "findings" {
  name         = "${var.project_name}-${var.environment}-findings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "finding_id"
  range_key    = "timestamp"

  attribute {
    name = "finding_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-findings"
    }
  )
}

# Preferences Table
resource "aws_dynamodb_table" "preferences" {
  name         = "${var.project_name}-${var.environment}-preferences"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "workspace_id"
  range_key    = "preference_key"

  attribute {
    name = "workspace_id"
    type = "S"
  }
  attribute {
    name = "preference_key"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-preferences"
    }
  )
}

# Approvals Table
resource "aws_dynamodb_table" "approvals" {
  name         = "${var.project_name}-${var.environment}-approvals"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "approval_id"
  range_key    = "timestamp"

  attribute {
    name = "approval_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-approvals"
    }
  )
}

# Remediations Table
resource "aws_dynamodb_table" "remediations" {
  name         = "${var.project_name}-${var.environment}-remediations"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "remediation_id"
  range_key    = "timestamp"

  attribute {
    name = "remediation_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-remediations"
    }
  )
}

# Conversations Table (for architect conversations)
resource "aws_dynamodb_table" "conversations" {
  name         = "${var.project_name}-${var.environment}-conversations"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "conversation_id"
  range_key    = "timestamp"

  attribute {
    name = "conversation_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-conversations"
    }
  )
}

# Evidence Table
resource "aws_dynamodb_table" "evidence" {
  name         = "${var.project_name}-${var.environment}-evidence"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "evidence_id"
  range_key    = "timestamp"

  attribute {
    name = "evidence_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-evidence"
    }
  )
}

# Exceptions Table
resource "aws_dynamodb_table" "exceptions" {
  name         = "${var.project_name}-${var.environment}-exceptions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "exception_id"
  range_key    = "timestamp"

  attribute {
    name = "exception_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-exceptions"
    }
  )
}

# Drift Table - Removed (created by drift module)

# AI Feedback Table
resource "aws_dynamodb_table" "ai_feedback" {
  name         = "${var.project_name}-${var.environment}-ai-feedback"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "feedback_id"
  range_key    = "timestamp"

  attribute {
    name = "feedback_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-ai-feedback"
    }
  )
}

# Foundation Session Table (original)
resource "aws_dynamodb_table" "foundation" {
  name         = "${var.project_name}-${var.environment}-foundation"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-foundation"
    }
  )
}

# ============================================================================
# Secrets Manager
# ============================================================================

# Slack Bot Token Secret (placeholder - actual value set via Terraform variable)
resource "aws_secretsmanager_secret" "slack_bot_token" {
  name                    = "${var.project_name}/${var.environment}/slack/bot-token"
  description             = "Slack bot token for CARL ${var.environment}"
  kms_key_id              = data.aws_kms_alias.carl.target_key_arn
  recovery_window_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-slack-bot-token"
    }
  )
}

# Slack Signing Secret
resource "aws_secretsmanager_secret" "slack_signing_secret" {
  name                    = "${var.project_name}/${var.environment}/slack/signing-secret"
  description             = "Slack signing secret for CARL ${var.environment}"
  kms_key_id              = data.aws_kms_alias.carl.target_key_arn
  recovery_window_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-slack-signing-secret"
    }
  )
}

# ============================================================================
# IAM Role for Lambda Execution
# ============================================================================

resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-${var.environment}-lambda-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-lambda-execution"
    }
  )
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# SecurityAudit policy for read-only evidence collection across all AWS services
resource "aws_iam_role_policy_attachment" "lambda_security_audit" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/SecurityAudit"
}

# Policy for Lambda to access CARL resources
resource "aws_iam_role_policy" "lambda_carl_access" {
  name = "carl-access"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.findings.arn,
          aws_dynamodb_table.preferences.arn,
          aws_dynamodb_table.approvals.arn,
          aws_dynamodb_table.remediations.arn,
          aws_dynamodb_table.conversations.arn,
          aws_dynamodb_table.evidence.arn,
          aws_dynamodb_table.exceptions.arn,
          aws_dynamodb_table.ai_feedback.arn,
          aws_dynamodb_table.foundation.arn,
          aws_dynamodb_table.scan_history.arn,
          aws_dynamodb_table.resource_graph.arn,
          aws_dynamodb_table.pricing_cache.arn
          # drift table removed (created by drift module)
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.evidence.arn,
          "${aws_s3_bucket.evidence.arn}/*",
          aws_s3_bucket.reports.arn,
          "${aws_s3_bucket.reports.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.slack_bot_token.arn,
          aws_secretsmanager_secret.slack_signing_secret.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          data.aws_kms_alias.carl.target_key_arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.id}::foundation-model/*",
          "arn:aws:bedrock:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "events:PutEvents"
        ]
        Resource = [
          aws_cloudwatch_event_bus.carl.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = [
          aws_sns_topic.alerts.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "securityhub:EnableSecurityHub",
          "securityhub:DescribeHub",
          "securityhub:GetFindings",
          "securityhub:BatchImportFindings",
          "securityhub:BatchUpdateFindings"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "config:PutConfigurationRecorder",
          "config:PutDeliveryChannel",
          "config:StartConfigurationRecorder",
          "config:DescribeConfigurationRecorders",
          "config:DescribeConfigurationRecorderStatus",
          "config:DescribeDeliveryChannels"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:PutBucketPolicy",
          "s3:PutBucketVersioning",
          "s3:GetBucketAcl",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::aws-config-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:GetRole",
          "iam:AttachRolePolicy",
          "iam:PassRole",
          "iam:CreateServiceLinkedRole"
        ]
        Resource = [
          "arn:aws:iam::*:role/AWSConfigRole",
          "arn:aws:iam::*:role/aws-service-role/config.amazonaws.com/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:function:${var.project_name}-${var.environment}-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          "arn:aws:ssm:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:parameter/${var.environment}/${var.project_name}/*"
        ]
      }
    ]
  })
}

# ============================================================================
# EventBridge
# ============================================================================

resource "aws_cloudwatch_event_bus" "carl" {
  name = "${var.project_name}-${var.environment}"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-event-bus"
    }
  )
}

# ============================================================================
# SNS Topic for Alerts
# ============================================================================

resource "aws_sns_topic" "alerts" {
  name              = "${var.project_name}-${var.environment}-alerts"
  kms_master_key_id = data.aws_kms_alias.carl.target_key_id

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-alerts"
    }
  )
}

# ============================================================================
# CloudWatch Log Group
# ============================================================================

resource "aws_cloudwatch_log_group" "carl" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}"
  retention_in_days = 30
  kms_key_id        = data.aws_kms_alias.carl.target_key_arn

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.environment}-logs"
    }
  )
}
