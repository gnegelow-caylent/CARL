# CARL Infrastructure - Main Configuration
# Cost-optimized deployment with flexible sizing profiles

terraform {
  required_version = ">= 1.0"

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

provider "aws" {
  region = var.primary_region

  default_tags {
    tags = merge(var.tags, {
      SizingProfile = var.sizing_profile
      CostOptimized = var.enable_cost_optimization
    })
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local variables for cost optimization
locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.id

  # Cost-optimized settings based on sizing profile
  sizing_config = {
    minimal = {
      lambda_memory               = 128
      lambda_timeout              = 30
      lambda_reserved_concurrency = -1 # No reservation
      dynamodb_billing_mode       = "PAY_PER_REQUEST"
      dynamodb_read_capacity      = 0
      dynamodb_write_capacity     = 0
      s3_lifecycle_enabled        = true
      s3_intelligent_tiering      = false
      bedrock_model               = "anthropic.claude-3-haiku-20240307-v1:0"
      bedrock_cache_ttl_seconds   = 3600 # 1 hour cache
      enable_xray                 = false
      cloudwatch_retention_days   = 7
    }
    moderate = {
      lambda_memory               = 512
      lambda_timeout              = 60
      lambda_reserved_concurrency = -1 # No reservation (pay per use)
      dynamodb_billing_mode       = "PAY_PER_REQUEST"
      dynamodb_read_capacity      = 0
      dynamodb_write_capacity     = 0
      s3_lifecycle_enabled        = true
      s3_intelligent_tiering      = true
      bedrock_model               = "anthropic.claude-3-haiku-20240307-v1:0" # Start with Haiku
      bedrock_cache_ttl_seconds   = 1800                                     # 30 min cache
      enable_xray                 = true
      cloudwatch_retention_days   = 14
    }
    standard = {
      lambda_memory               = 1024
      lambda_timeout              = 120
      lambda_reserved_concurrency = 10
      dynamodb_billing_mode       = "PROVISIONED"
      dynamodb_read_capacity      = 5
      dynamodb_write_capacity     = 5
      s3_lifecycle_enabled        = true
      s3_intelligent_tiering      = true
      bedrock_model               = "anthropic.claude-3-5-sonnet-20241022-v2:0"
      bedrock_cache_ttl_seconds   = 900 # 15 min cache
      enable_xray                 = true
      cloudwatch_retention_days   = 30
    }
  }

  config = local.sizing_config[var.sizing_profile]

  # Bedrock model selection with cost optimization
  # Haiku: $0.25/$1.25 per 1M tokens (input/output)
  # Sonnet: $3/$15 per 1M tokens (input/output)
  bedrock_models = {
    haiku  = "anthropic.claude-3-haiku-20240307-v1:0"
    sonnet = "anthropic.claude-3-5-sonnet-20241022-v2:0"
  }

  # Common resource naming
  name_prefix = "carl-${var.environment}"
}

# DynamoDB Tables (Cost-optimized with on-demand billing)
module "dynamodb" {
  source = "./modules/dynamodb"

  environment    = var.environment
  name_prefix    = local.name_prefix
  billing_mode   = local.config.dynamodb_billing_mode
  read_capacity  = local.config.dynamodb_read_capacity
  write_capacity = local.config.dynamodb_write_capacity

  # Cost optimization: Enable TTL to auto-delete old items
  enable_ttl = var.enable_cost_optimization

  tags = var.tags
}

# S3 Buckets (Cost-optimized with lifecycle rules)
module "s3" {
  source = "./modules/s3"

  environment             = var.environment
  name_prefix             = local.name_prefix
  enable_lifecycle        = local.config.s3_lifecycle_enabled
  enable_intelligent_tier = local.config.s3_intelligent_tiering
  enable_versioning       = var.environment == "prod"

  # Cost optimization: Transition old data to cheaper storage
  lifecycle_rules = var.enable_cost_optimization ? [
    {
      name    = "transition-old-evidence"
      enabled = true
      transitions = [
        {
          days          = 30
          storage_class = "STANDARD_IA" # Cheaper after 30 days
        },
        {
          days          = 90
          storage_class = "GLACIER_INSTANT_RETRIEVAL"
        }
      ]
    }
  ] : []

  tags = var.tags
}

# Lambda Functions (Cost-optimized with right-sized memory)
module "lambda" {
  source = "./modules/lambda"

  environment          = var.environment
  name_prefix          = local.name_prefix
  memory_size          = local.config.lambda_memory
  timeout              = local.config.lambda_timeout
  reserved_concurrency = local.config.lambda_reserved_concurrency

  # Environment variables with cost optimization settings
  environment_variables = {
    ENVIRONMENT = var.environment

    # Bedrock configuration - Cost optimized
    BEDROCK_MODEL_ID          = local.bedrock_models.haiku  # Default to cheapest
    BEDROCK_FALLBACK_MODEL_ID = local.bedrock_models.sonnet # Upgrade for complex queries
    BEDROCK_ENABLE_CACHING    = var.enable_bedrock_caching ? "true" : "false"
    BEDROCK_CACHE_TTL_SECONDS = tostring(local.config.bedrock_cache_ttl_seconds)

    # Model selection rules (cost optimization)
    # Use Haiku for: status, findings, simple queries
    # Use Sonnet for: architect, recommend, complex analysis
    BEDROCK_HAIKU_COMMANDS  = "status,findings,evidence,drift"
    BEDROCK_SONNET_COMMANDS = "architect,recommend,foundation"

    # DynamoDB tables
    FINDINGS_TABLE   = module.dynamodb.findings_table_name
    EVIDENCE_TABLE   = module.dynamodb.evidence_table_name
    EXCEPTIONS_TABLE = module.dynamodb.exceptions_table_name
    DRIFT_TABLE      = module.dynamodb.drift_table_name
    BOOTSTRAP_TABLE  = module.dynamodb.bootstrap_table_name
    FEEDBACK_TABLE   = module.dynamodb.feedback_table_name

    # S3 buckets
    EVIDENCE_BUCKET = module.s3.evidence_bucket_name
    REPORTS_BUCKET  = module.s3.reports_bucket_name

    # Slack
    SLACK_ENABLED            = var.enable_slack ? "true" : "false"
    SLACK_BOT_TOKEN_SSM      = var.enable_slack ? aws_ssm_parameter.slack_bot_token[0].name : ""
    SLACK_SIGNING_SECRET_SSM = var.enable_slack ? aws_ssm_parameter.slack_signing_secret[0].name : ""

    # Cost optimization flags
    ENABLE_RESPONSE_CACHING = "true"
    CACHE_REDIS_ENABLED     = "false" # Use in-memory cache for cost savings
  }

  # DynamoDB table ARNs for IAM permissions
  dynamodb_table_arns = [
    module.dynamodb.findings_table_arn,
    module.dynamodb.evidence_table_arn,
    module.dynamodb.exceptions_table_arn,
    module.dynamodb.drift_table_arn,
    module.dynamodb.bootstrap_table_arn,
    module.dynamodb.feedback_table_arn,
  ]

  # S3 bucket ARNs for IAM permissions
  s3_bucket_arns = [
    module.s3.evidence_bucket_arn,
    module.s3.reports_bucket_arn,
  ]

  # Bedrock access
  enable_bedrock = true
  bedrock_model_arns = [
    "arn:aws:bedrock:${local.region}::foundation-model/${local.bedrock_models.haiku}",
    "arn:aws:bedrock:${local.region}::foundation-model/${local.bedrock_models.sonnet}",
  ]

  # CloudWatch Logs
  log_retention_days = local.config.cloudwatch_retention_days

  # X-Ray tracing (disabled for minimal to save cost)
  enable_xray = local.config.enable_xray

  tags = var.tags
}

# API Gateway (Cost-optimized with HTTP API instead of REST)
module "api_gateway" {
  source = "./modules/api-gateway"

  environment = var.environment
  name_prefix = local.name_prefix
  lambda_arn  = module.lambda.function_arn
  lambda_name = module.lambda.function_name

  # Use HTTP API for cost savings (cheaper than REST API)
  # HTTP API: $1.00 per million requests
  # REST API: $3.50 per million requests
  api_type = "http"

  # Throttling for cost control
  throttle_burst_limit = var.environment == "prod" ? 5000 : 100
  throttle_rate_limit  = var.environment == "prod" ? 1000 : 50

  tags = var.tags
}

# CloudWatch Alarms (Cost-optimized with essential alarms only)
module "monitoring" {
  source = "./modules/monitoring"

  environment = var.environment
  name_prefix = local.name_prefix

  lambda_function_name = module.lambda.function_name
  api_gateway_id       = module.api_gateway.api_id

  # Alarm thresholds based on sizing profile
  lambda_error_threshold    = var.environment == "prod" ? 1 : 10
  lambda_duration_threshold = local.config.lambda_timeout * 0.8
  api_latency_threshold     = var.environment == "prod" ? 3000 : 10000

  # Cost optimization: Only essential alarms
  enable_detailed_monitoring = var.sizing_profile == "standard"

  # SNS topic for alerts (optional)
  create_sns_topic = var.environment == "prod"
  alert_email      = var.alert_email

  tags = var.tags
}

# Slack Secrets (stored in Parameter Store)
resource "aws_ssm_parameter" "slack_bot_token" {
  count = var.enable_slack ? 1 : 0

  name        = "/${var.environment}/carl/slack/bot-token"
  description = "Slack Bot Token for CARL"
  type        = "SecureString"
  value       = var.slack_bot_token

  tags = var.tags
}

resource "aws_ssm_parameter" "slack_signing_secret" {
  count = var.enable_slack ? 1 : 0

  name        = "/${var.environment}/carl/slack/signing-secret"
  description = "Slack Signing Secret for CARL"
  type        = "SecureString"
  value       = var.slack_signing_secret

  tags = var.tags
}

# Outputs
output "api_endpoint" {
  description = "CARL API endpoint URL"
  value       = module.api_gateway.api_endpoint
}

output "lambda_function_name" {
  description = "CARL Lambda function name"
  value       = module.lambda.function_name
}

output "lambda_function_arn" {
  description = "CARL Lambda function ARN"
  value       = module.lambda.function_arn
}

output "findings_table_name" {
  description = "DynamoDB findings table name"
  value       = module.dynamodb.findings_table_name
}

output "evidence_bucket_name" {
  description = "S3 evidence bucket name"
  value       = module.s3.evidence_bucket_name
}

output "reports_bucket_name" {
  description = "S3 reports bucket name"
  value       = module.s3.reports_bucket_name
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost based on sizing profile"
  value = {
    minimal  = "$50-75 (Haiku only, minimal resources)"
    moderate = "$100-200 (Haiku + Sonnet fallback, balanced resources)"
    standard = "$200-500 (Sonnet primary, high availability)"
  }[var.sizing_profile]
}

output "bedrock_models" {
  description = "Bedrock models configured"
  value = {
    primary  = local.bedrock_models.haiku
    fallback = local.bedrock_models.sonnet
  }
}
