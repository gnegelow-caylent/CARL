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

# 2. Lambda Execution Role
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

# DynamoDB access for config table
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
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.config.arn
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
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
          "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
        ]
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
  source_code_hash = filebase64sha256(local.lambda_zip_path)
  runtime          = "python3.11"

  # COST OPTIMIZATION: Start small, Lambda auto-scales
  memory_size = 512 # Enough for Bedrock calls
  timeout     = 30  # Most queries under 10s

  # Force update when code changes
  publish = true

  environment {
    variables = {
      ENVIRONMENT = var.environment

      # Config table
      CONFIG_TABLE = aws_dynamodb_table.config.name

      # Bedrock - Cost optimized (Haiku by default)
      BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
      BEDROCK_REGION   = local.region

      # Slack
      SLACK_BOT_TOKEN_SSM      = "/${var.environment}/carl/slack/bot-token"
      SLACK_SIGNING_SECRET_SSM = "/${var.environment}/carl/slack/signing-secret"

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
