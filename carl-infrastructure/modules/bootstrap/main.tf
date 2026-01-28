# CARL Bootstrap Module
# AWS Organizations setup, Identity Center, Security Services

terraform {
  required_version = ">= 1.0"
}

# S3 bucket for bootstrap state
resource "aws_s3_bucket" "bootstrap_state" {
  bucket = "${var.project_name}-${var.environment}-bootstrap-state-${data.aws_caller_identity.current.account_id}"

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "bootstrap_state" {
  bucket = aws_s3_bucket.bootstrap_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# DynamoDB table for bootstrap tracking
resource "aws_dynamodb_table" "bootstrap_tracking" {
  name         = "${var.project_name}-${var.environment}-bootstrap"
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
    kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  tags = var.tags
}

# Lambda for bootstrap orchestration
resource "aws_lambda_function" "bootstrap_orchestrator" {
  filename      = var.lambda_package_path
  function_name = "${var.project_name}-${var.environment}-bootstrap"
  role          = aws_iam_role.bootstrap_role.arn
  handler       = "services.bootstrap.bootstrap_orchestrator.lambda_handler"
  runtime       = "python3.11"
  timeout       = 900 # 15 minutes for long operations
  memory_size   = 1024

  environment {
    variables = {
      BOOTSTRAP_STATE_BUCKET = aws_s3_bucket.bootstrap_state.id
      BOOTSTRAP_TABLE        = aws_dynamodb_table.bootstrap_tracking.name
    }
  }

  tags = var.tags
}

# IAM role for bootstrap Lambda
resource "aws_iam_role" "bootstrap_role" {
  name = "${var.project_name}-${var.environment}-bootstrap-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

# IAM policies for bootstrap (Organizations admin access)
resource "aws_iam_role_policy" "bootstrap_policy" {
  name = "${var.project_name}-${var.environment}-bootstrap-policy"
  role = aws_iam_role.bootstrap_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "organizations:*",
          "sso:*",
          "sso-directory:*",
          "iam:*",
          "securityhub:*",
          "guardduty:*",
          "inspector2:*",
          "config:*"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:*",
          "s3:*"
        ]
        Resource = [
          aws_dynamodb_table.bootstrap_tracking.arn,
          aws_s3_bucket.bootstrap_state.arn,
          "${aws_s3_bucket.bootstrap_state.arn}/*"
        ]
      }
    ]
  })
}

data "aws_caller_identity" "current" {}
