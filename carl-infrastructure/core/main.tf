# CARL Minimal Core Infrastructure
# Cost: ~$10-20/month (just the brain, no storage or scanning)
#
# This deploys only what's needed to talk to CARL in Slack.
# CARL will suggest and deploy additional features based on your needs.
# Updated: 2026-01-28 - IAM permissions fixed for CloudWatch, API Gateway, SSM

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
  default_tags {
    tags = var.tags
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name
  name_prefix = "carl-${var.environment}"
}

# ============================================================================
# MINIMAL CORE COMPONENTS
# ============================================================================

# 1. Configuration Table (stores what features are enabled)
resource "aws_dynamodb_table" "config" {
  name         = "${local.name_prefix}-config"
  billing_mode = "PAY_PER_REQUEST" # No fixed cost, pay only for what you use
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

  # TTL for temporary data (cost optimization)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-config"
  })
}

# 2. Evidence Table (stores audit evidence)
resource "aws_dynamodb_table" "evidence" {
  name         = "${local.name_prefix}-evidence"
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

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-evidence"
  })
}

# 3. Findings Table (stores security findings)
resource "aws_dynamodb_table" "findings" {
  name         = "${local.name_prefix}-findings"
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

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-findings"
  })
}

# 4. Exceptions Table (stores risk exceptions)
resource "aws_dynamodb_table" "exceptions" {
  name         = "${local.name_prefix}-exceptions"
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

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-exceptions"
  })
}

# 5. Setup Configuration Table (stores workspace setup and preferences)
resource "aws_dynamodb_table" "setup_config" {
  name         = "${local.name_prefix}-setup-config"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "workspace_id"

  attribute {
    name = "workspace_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-setup-config"
  })
}

# 6. Evidence Bucket (stores evidence artifacts)
resource "aws_s3_bucket" "evidence" {
  bucket = "${local.name_prefix}-evidence"

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-evidence"
  })
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
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 6. Reports Bucket (stores generated reports)
resource "aws_s3_bucket" "reports" {
  bucket = "${local.name_prefix}-reports"

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-reports"
  })
}

# 6a. Terraform State Bucket (stores Terraform state for infrastructure deployments)
resource "aws_s3_bucket" "tfstate" {
  bucket = "carl-tfstate-${local.account_id}"

  tags = merge(var.tags, {
    Name        = "carl-tfstate-${local.account_id}"
    Description = "Terraform state storage for CARL infrastructure deployments"
  })
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 6b. Terraform State Lock Table (prevents concurrent state modifications)
resource "aws_dynamodb_table" "tfstate_locks" {
  name         = "carl-tfstate-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  ttl {
    attribute_name = "TTL"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = merge(var.tags, {
    Name        = "carl-tfstate-locks"
    Description = "Terraform state locking for CARL infrastructure deployments"
  })
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
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 7. Lambda Execution Role
resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

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

# Lambda basic execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access for all CARL tables
resource "aws_iam_role_policy" "dynamodb" {
  name = "dynamodb-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DeleteItem",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:DescribeTable"
        ]
        Resource = [
          aws_dynamodb_table.config.arn,
          "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${local.name_prefix}-*"
        ]
      }
    ]
  })
}

# S3 access for evidence and reports (read/write)
resource "aws_iam_role_policy" "s3_reports" {
  name = "s3-reports-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${local.name_prefix}-evidence",
          "arn:aws:s3:::${local.name_prefix}-evidence/*",
          "arn:aws:s3:::${local.name_prefix}-reports",
          "arn:aws:s3:::${local.name_prefix}-reports/*"
        ]
      }
    ]
  })
}

# Lambda self-invocation (for async processing)
resource "aws_iam_role_policy" "lambda_invoke" {
  name = "lambda-invoke"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${local.region}:${local.account_id}:function:${local.name_prefix}-*"
      }
    ]
  })
}

# Bedrock access (COST OPTIMIZED - Haiku only initially)
resource "aws_iam_role_policy" "bedrock" {
  name = "bedrock-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          # Allow all Anthropic models in any region (wildcard)
          "arn:aws:bedrock:*::foundation-model/anthropic.*",
          "arn:aws:bedrock:*:*:inference-profile/*anthropic*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe"
        ]
        Resource = "*"
      }
    ]
  })
}

# SSM Parameter Store access (for Slack secrets)
resource "aws_iam_role_policy" "ssm" {
  name = "ssm-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${local.region}:${local.account_id}:parameter/${var.environment}/carl/*"
      }
    ]
  })
}

# Secrets Manager access (for GitHub credentials)
resource "aws_iam_role_policy" "secrets_manager" {
  name = "secrets-manager-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:/carl/${var.environment}/github-app-credentials*",
          "arn:aws:secretsmanager:${local.region}:${local.account_id}:secret:/carl/${var.environment}/github-infra-token*"
        ]
      }
    ]
  })
}

# CloudFormation/Terraform deployment permissions (for feature deployment)
resource "aws_iam_role_policy" "deploy_features" {
  name = "deploy-features"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudformation:CreateStack",
          "cloudformation:DescribeStacks",
          "cloudformation:UpdateStack",
          "cloudformation:DeleteStack"
        ]
        Resource = "arn:aws:cloudformation:${local.region}:${local.account_id}:stack/carl-feature-*/*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = aws_iam_role.lambda.arn
      }
    ]
  })
}

# AWS environment scanning permissions (read-only)
resource "aws_iam_role_policy" "aws_scanner" {
  name = "aws-scanner"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          # IAM read-only
          "iam:GetAccountSummary",
          "iam:GetAccountPasswordPolicy",
          "iam:ListUsers",
          "iam:ListMFADevices",
          "iam:ListAccessKeys",
          # CloudTrail read-only
          "cloudtrail:DescribeTrails",
          "cloudtrail:GetTrailStatus",
          "cloudtrail:LookupEvents",
          # EC2/VPC read-only
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeVpcs",
          "ec2:DescribeSubnets",
          "ec2:DescribeFlowLogs",
          "ec2:GetEbsEncryptionByDefault",
          "ec2:DescribeVolumes",
          # S3 read-only
          "s3:ListAllMyBuckets",
          "s3:GetBucketAcl",
          "s3:GetBucketEncryption",
          "s3:GetBucketVersioning",
          "s3:GetBucketPublicAccessBlock",
          # KMS read-only
          "kms:ListKeys",
          "kms:DescribeKey",
          # RDS read-only
          "rds:DescribeDBInstances",
          "rds:DescribeDBClusters",
          # STS (for account ID)
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      }
    ]
  })
}

# Security Hub and AWS Config enablement permissions
resource "aws_iam_role_policy" "security_services" {
  name = "security-services-enablement"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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
        Resource = "arn:aws:s3:::aws-config-*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:GetRole",
          "iam:AttachRolePolicy",
          "iam:PassRole"
        ]
        Resource = [
          "arn:aws:iam::${local.account_id}:role/AWSConfigRole"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "iam:CreateServiceLinkedRole"
        ]
        Resource = [
          "arn:aws:iam::${local.account_id}:role/aws-service-role/config.amazonaws.com/*",
          "arn:aws:iam::${local.account_id}:role/aws-service-role/securityhub.amazonaws.com/*"
        ]
      }
    ]
  })
}

# 3. Lambda Function (CARL's Brain)
# Note: Lambda package is created by GitHub Actions workflow with dependencies
# The workflow installs requirements.txt into src/ before zipping
# Do NOT use data.archive_file here as it would recreate without dependencies

locals {
  lambda_zip_path = "${path.module}/lambda.zip"
}

resource "aws_lambda_function" "carl" {
  filename         = local.lambda_zip_path
  function_name    = "${local.name_prefix}-api"
  role             = aws_iam_role.lambda.arn
  handler          = "handlers.slack_router.lambda_handler"
  source_code_hash = fileexists(local.lambda_zip_path) ? filebase64sha256(local.lambda_zip_path) : ""
  runtime          = "python3.11"

  # Performance optimization: 1024MB provides 2x CPU, faster cold starts
  # Cost is similar since execution is 2x faster (GB-seconds remain constant)
  memory_size = 1024 # Faster cold starts, enough for Bedrock calls
  timeout     = 90   # Agentic workflows need 45-60s for complex questions

  # Force update when code changes
  publish = true

  environment {
    variables = {
      ENVIRONMENT = var.environment

      # Config table
      CONFIG_TABLE = aws_dynamodb_table.config.name

      # Reporting tables (will be created when reporting feature is enabled)
      EVIDENCE_TABLE   = "${local.name_prefix}-evidence"
      FINDINGS_TABLE   = "${local.name_prefix}-findings"
      EXCEPTIONS_TABLE = "${local.name_prefix}-exceptions"
      SETUP_TABLE_NAME = aws_dynamodb_table.setup_config.name
      EVIDENCE_BUCKET  = "${local.name_prefix}-evidence"
      REPORTS_BUCKET   = "${local.name_prefix}-reports"

      # Bedrock - Cost optimized (Claude Haiku 4.5 by default)
      BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
      BEDROCK_REGION   = local.region

      # Slack
      SLACK_BOT_TOKEN_SSM      = "/${var.environment}/carl/slack/bot-token"
      SLACK_SIGNING_SECRET_SSM = "/${var.environment}/carl/slack/signing-secret"

      # GitHub Infrastructure Repository (for GitOps deployments)
      # Preferred: GitHub App (short-lived tokens)
      GITHUB_APP_CREDENTIALS_SECRET = "/carl/${var.environment}/github-app-credentials"
      # Legacy: Static token (deprecated)
      GITHUB_INFRA_TOKEN_SECRET = "/carl/${var.environment}/github-infra-token"
      GITHUB_INFRA_OWNER        = var.github_infra_owner
      GITHUB_INFRA_REPO         = var.github_infra_repo

      # Feature flags (all disabled initially)
      FEATURE_MONITORING_ENABLED = "false"
      FEATURE_BOOTSTRAP_ENABLED  = "false"
      FEATURE_REPORTING_ENABLED  = "false"
      FEATURE_FOUNDATION_ENABLED = "false"

      # Onboarding state
      ONBOARDING_COMPLETE = "false"
    }
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-api"
  })
}

# CloudWatch Logs (cost optimization: 7-day retention)
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.carl.function_name}"
  retention_in_days = 7 # Minimal cost

  tags = var.tags
}

# 4. API Gateway (HTTP API - cheaper than REST API)
resource "aws_apigatewayv2_api" "carl" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"

  # CORS for future web interface
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET"]
    allow_headers = ["content-type"]
  }

  tags = var.tags
}

# API Gateway Integration
resource "aws_apigatewayv2_integration" "carl" {
  api_id           = aws_apigatewayv2_api.carl.id
  integration_type = "AWS_PROXY"

  integration_uri    = aws_lambda_function.carl.invoke_arn
  integration_method = "POST"
}

# API Gateway Route (Slack endpoint)
resource "aws_apigatewayv2_route" "slack" {
  api_id    = aws_apigatewayv2_api.carl.id
  route_key = "POST /slack"
  target    = "integrations/${aws_apigatewayv2_integration.carl.id}"
}

# API Gateway Route (Health check)
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.carl.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.carl.id}"
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.carl.id
  name        = "$default"
  auto_deploy = true

  # Cost optimization: No access logs initially
  tags = var.tags
}

# Lambda permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.carl.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.carl.execution_arn}/*/*"
}

# 5. Slack Secrets (SSM Parameter Store - Free tier)
resource "aws_ssm_parameter" "slack_bot_token" {
  count = var.slack_bot_token != "" ? 1 : 0

  name        = "/${var.environment}/carl/slack/bot-token"
  description = "Slack Bot Token for CARL"
  type        = "SecureString"
  value       = var.slack_bot_token

  tags = var.tags
}

resource "aws_ssm_parameter" "slack_signing_secret" {
  count = var.slack_signing_secret != "" ? 1 : 0

  name        = "/${var.environment}/carl/slack/signing-secret"
  description = "Slack Signing Secret for CARL"
  type        = "SecureString"
  value       = var.slack_signing_secret

  tags = var.tags
}

# ============================================================================
# FEATURE MODULES (Conditional Deployment via count)
# ============================================================================
# All modules available, but count=0 disables them until user enables

# Monitoring Module (Infrastructure Scanning + Compliance)
module "monitoring" {
  source = "../modules/monitoring"
  count  = var.enable_monitoring ? 1 : 0

  project_name        = "carl"
  environment         = var.environment
  kms_key_arn         = "" # Will be created in module if needed
  lambda_package_path = local.lambda_zip_path
  enable_xray         = var.environment == "prod"

  tags = merge(var.tags, {
    Feature = "monitoring"
  })
}

# Bootstrap Module (AWS Organizations & Account Setup)
module "bootstrap" {
  source = "../modules/bootstrap"
  count  = var.enable_bootstrap ? 1 : 0

  project_name        = "carl"
  environment         = var.environment
  kms_key_arn         = ""
  lambda_package_path = local.lambda_zip_path

  tags = merge(var.tags, {
    Feature = "bootstrap"
  })
}

# Reporting Module (Compliance Reports + Evidence Collection)
module "reporting" {
  source = "../modules/reporting"
  count  = var.enable_reporting ? 1 : 0

  project_name        = "carl"
  environment         = var.environment
  kms_key_arn         = ""
  lambda_package_path = local.lambda_zip_path

  tags = merge(var.tags, {
    Feature = "reporting"
  })
}

# Foundation Module (Guided Infrastructure Builder)
module "foundation" {
  source = "../modules/foundation"
  count  = var.enable_foundation ? 1 : 0

  project_name        = "carl"
  environment         = var.environment
  kms_key_arn         = ""
  lambda_package_path = local.lambda_zip_path

  tags = merge(var.tags, {
    Feature = "foundation"
  })
}

# Drift Detection Module (Detect infrastructure drift)
module "drift_detection" {
  source = "../modules/drift"
  count  = var.enable_drift_detection ? 1 : 0

  project_name        = "carl"
  environment         = var.environment
  kms_key_arn         = ""
  lambda_package_path = local.lambda_zip_path

  tags = merge(var.tags, {
    Feature = "drift_detection"
  })
}

# Auto-Remediation Module (Automatically fix violations)
module "auto_remediation" {
  source = "../modules/remediation"
  count  = var.enable_auto_remediation ? 1 : 0

  project_name        = "carl"
  environment         = var.environment
  kms_key_arn         = ""
  lambda_package_path = local.lambda_zip_path

  tags = merge(var.tags, {
    Feature = "auto_remediation"
  })
}

# ============================================================================
# KEEP LAMBDA WARM (Reduces cold starts for better Slack responsiveness)
# ============================================================================

# CloudWatch Event to ping Lambda every 5 minutes
resource "aws_cloudwatch_event_rule" "keep_warm" {
  name                = "${local.name_prefix}-keep-warm"
  description         = "Keep CARL Lambda warm to reduce cold starts"
  schedule_expression = "rate(5 minutes)"

  tags = merge(var.tags, {
    Purpose = "performance"
  })
}

resource "aws_cloudwatch_event_target" "keep_warm" {
  rule      = aws_cloudwatch_event_rule.keep_warm.name
  target_id = "KeepWarmLambda"
  arn       = aws_lambda_function.carl.arn

  input = jsonencode({
    action = "keep_warm"
  })
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.carl.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.keep_warm.arn
}

# ============================================================================
# OUTPUTS
# ============================================================================

output "api_endpoint" {
  description = "CARL API endpoint (configure in Slack)"
  value       = aws_apigatewayv2_api.carl.api_endpoint
}

output "slack_webhook_url" {
  description = "Slack webhook URL (use in Slack App settings)"
  value       = "${aws_apigatewayv2_api.carl.api_endpoint}/slack"
}

output "lambda_function_name" {
  description = "Lambda function name for logs"
  value       = aws_lambda_function.carl.function_name
}

output "config_table_name" {
  description = "DynamoDB config table name"
  value       = aws_dynamodb_table.config.name
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost for minimal core"
  value       = <<-EOT
    CARL Core Infrastructure (Minimal):

    Lambda: $5-10/month
      - 512 MB memory
      - ~10,000 invocations/month
      - Free tier: First 1M requests free

    API Gateway: $1-2/month
      - HTTP API: $1.00 per million requests
      - ~1,000 requests/month

    DynamoDB: $1-3/month
      - On-demand billing
      - ~100K reads, 10K writes/month

    Bedrock (Haiku): $3-5/month
      - $0.25 per 1M input tokens
      - $1.25 per 1M output tokens
      - ~200K input, 100K output/month

    CloudWatch Logs: $0-1/month
      - 7-day retention
      - ~100 MB logs/month

    SSM Parameter Store: $0/month
      - Standard parameters are free

    TOTAL: ~$10-21/month

    💡 Deploy only features you need to keep costs low:
      - `/carl enable monitoring` - Add scanning and storage
      - `/carl enable bootstrap` - Add AWS setup automation
      - `/carl enable reporting` - Add compliance reports
  EOT
}

output "next_steps" {
  description = "Next steps after deployment"
  value       = <<-EOT
    🎉 CARL Core Deployed!

    Next steps:

    1. Configure Slack App:
       - Go to https://api.slack.com/apps
       - Create new app or select existing
       - Under "Event Subscriptions", enable and set URL to:
         ${aws_apigatewayv2_api.carl.api_endpoint}/slack
       - Under "OAuth & Permissions", add bot token scopes:
         - chat:write, commands, users:read
       - Install app to workspace

    2. Test CARL:
       - In Slack: /carl hello
       - CARL will introduce itself and ask what you want to do

    3. Enable features as needed:
       - /carl enable monitoring
       - /carl enable bootstrap
       - /carl enable reporting

    4. View logs:
       - aws logs tail /aws/lambda/${aws_lambda_function.carl.function_name} --follow

    Documentation: https://github.com/your-org/carl
  EOT
}
