# CARL Development Environment

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.18"
    }
  }

  backend "s3" {
    bucket         = "carl-terraform-state" # Update after bootstrap
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "carl-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Application = "CARL"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}

# -----------------------------------------------------------------------------
# Foundation Module
# -----------------------------------------------------------------------------

module "foundation" {
  source = "../../modules/foundation"

  environment          = "dev"
  aws_region           = var.aws_region
  slack_bot_token      = var.slack_bot_token
  slack_signing_secret = var.slack_signing_secret
  lambda_package_path  = var.lambda_package_path

  evidence_retention_days = 90 # Shorter for dev
}

# -----------------------------------------------------------------------------
# Scanning Module
# -----------------------------------------------------------------------------

module "scanning" {
  source = "../../modules/scanning"

  environment        = "dev"
  foundation_outputs = module.foundation

  # AWS Config
  create_config_recorder       = true
  enable_soc2_conformance_pack = true

  # Security Services
  enable_security_hub    = true
  enable_cis_benchmark   = true
  enable_guardduty       = true
  enable_inspector       = true
  enable_macie           = false # Disable in dev to save costs
  enable_access_analyzer = true

  # GuardDuty - minimal for dev
  guardduty_s3_protection      = false
  guardduty_eks_protection     = false
  guardduty_malware_protection = false

  # Inspector
  inspector_resource_types = ["EC2", "LAMBDA"]

  # Lambda
  lambda_package_path = var.lambda_package_path
  bedrock_model_id    = "anthropic.claude-3-haiku-20240307-v1:0"
  log_level           = "DEBUG"
}

# -----------------------------------------------------------------------------
# AgentCore Ask Agent Module (Phase 1)
# -----------------------------------------------------------------------------

module "agentcore_ask" {
  source = "../../modules/agentcore-ask"

  name_prefix        = "carl-dev"
  code_bucket_name   = module.foundation.evidence_bucket_name
  code_bucket_arn    = module.foundation.evidence_bucket_arn
  code_object_prefix = "agentcore/ask-agent"
  tool_lambda_arn    = module.scanning.slack_router_arn

  # Use Claude Sonnet for intelligent responses
  foundation_model = "anthropic.claude-sonnet-4-20250514-v1:0"

  # Enable memory for persistent learning
  enable_memory  = true
  enable_gateway = false # Direct Lambda invocation for Phase 1

  environment_variables = {
    ENVIRONMENT = "dev"
  }

  tags = {
    Application = "CARL"
    Environment = "dev"
    Component   = "AgentCore-Ask"
  }
}
