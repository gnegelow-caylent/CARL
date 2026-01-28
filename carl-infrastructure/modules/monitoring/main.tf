# CARL Monitoring Module
# Infrastructure scanning, compliance checking, Security Hub integration

terraform {
  required_version = ">= 1.0"
}

# DynamoDB table for findings
resource "aws_dynamodb_table" "findings" {
  name         = "${var.project_name}-${var.environment}-findings"
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

  attribute {
    name = "severity"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  global_secondary_index {
    name            = "severity-timestamp-index"
    hash_key        = "severity"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

# DynamoDB table for evidence
resource "aws_dynamodb_table" "evidence" {
  name         = "${var.project_name}-${var.environment}-evidence"
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

  attribute {
    name = "control_id"
    type = "S"
  }

  global_secondary_index {
    name            = "control-index"
    hash_key        = "control_id"
    range_key       = "sk"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

# DynamoDB table for exceptions
resource "aws_dynamodb_table" "exceptions" {
  name         = "${var.project_name}-${var.environment}-exceptions"
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

  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "status-index"
    hash_key        = "status"
    range_key       = "sk"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = var.tags
}

# S3 bucket for evidence storage
resource "aws_s3_bucket" "evidence" {
  bucket = "${var.project_name}-${var.environment}-evidence-${data.aws_caller_identity.current.account_id}"

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    id     = "transition-old-evidence"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
  }
}

# S3 bucket for reports
resource "aws_s3_bucket" "reports" {
  bucket = "${var.project_name}-${var.environment}-reports-${data.aws_caller_identity.current.account_id}"

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lambda for scanning
resource "aws_lambda_function" "scanner" {
  filename         = var.lambda_package_path
  function_name    = "${var.project_name}-${var.environment}-scanner"
  role             = aws_iam_role.scanner_role.arn
  handler          = "handlers.scanner.lambda_handler"
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 512
  source_code_hash = filebase64sha256(var.lambda_package_path)

  environment {
    variables = {
      FINDINGS_TABLE  = aws_dynamodb_table.findings.name
      EVIDENCE_TABLE  = aws_dynamodb_table.evidence.name
      EVIDENCE_BUCKET = aws_s3_bucket.evidence.id
      ENVIRONMENT     = var.environment
    }
  }

  tracing_config {
    mode = var.enable_xray ? "Active" : "PassThrough"
  }

  tags = var.tags
}

# IAM role for scanner Lambda
resource "aws_iam_role" "scanner_role" {
  name = "${var.project_name}-${var.environment}-scanner-role"

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

  tags = var.tags
}

# IAM policies for scanner
resource "aws_iam_role_policy" "scanner_policy" {
  name = "${var.project_name}-${var.environment}-scanner-policy"
  role = aws_iam_role.scanner_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.findings.arn,
          aws_dynamodb_table.evidence.arn,
          "${aws_dynamodb_table.findings.arn}/index/*",
          "${aws_dynamodb_table.evidence.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.evidence.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "securityhub:GetFindings",
          "securityhub:BatchImportFindings"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# CloudWatch Event Rule for scheduled scans
resource "aws_cloudwatch_event_rule" "daily_scan" {
  name                = "${var.project_name}-${var.environment}-daily-scan"
  description         = "Trigger daily compliance scan"
  schedule_expression = "cron(0 2 * * ? *)" # 2 AM UTC daily

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "daily_scan" {
  rule      = aws_cloudwatch_event_rule.daily_scan.name
  target_id = "ScannerLambda"
  arn       = aws_lambda_function.scanner.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_scan.arn
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
