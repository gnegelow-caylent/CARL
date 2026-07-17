# CARL MCP Deployment
# Simplified infrastructure for self-deployed CARL via MCP
#
# This deploys ONLY what's needed for MCP:
# - AgentCore runtimes (3 agents)
# - Storage (DynamoDB, S3)
# - IAM roles
#
# NOT INCLUDED (Slack-specific):
# - Lambda functions
# - API Gateway
# - Slack secrets

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.18"
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
  region      = data.aws_region.current.id
  name_prefix = "carl-${var.environment}"
}

# ============================================================================
# ECR Repository for Agent Containers
# ============================================================================

resource "aws_ecr_repository" "agents" {
  name                 = "${local.name_prefix}-agents"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-agents"
  })
}

# ============================================================================
# KMS Key for Encryption
# ============================================================================

resource "aws_kms_key" "carl" {
  description             = "CARL encryption key for ${var.environment}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow AgentCore to use the key"
        Effect = "Allow"
        Principal = {
          Service = "bedrock-agentcore.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "dynamodb.${local.region}.amazonaws.com",
              "s3.${local.region}.amazonaws.com"
            ]
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${local.name_prefix}-key"
  })
}

resource "aws_kms_alias" "carl" {
  name          = "alias/${local.name_prefix}"
  target_key_id = aws_kms_key.carl.key_id
}

# ============================================================================
# Foundation Module (DynamoDB + S3)
# ============================================================================

module "foundation" {
  source = "../modules/foundation"

  project_name = "carl"
  environment  = var.environment
  region       = local.region
  tags         = var.tags

  # Pass KMS key ARN (foundation module expects it from data source)
  # We'll need to adjust the foundation module to accept this as a variable
}

# ============================================================================
# AgentCore Modules
# ============================================================================

# Ask Agent
module "agentcore_ask" {
  source = "../modules/agentcore-ask"

  name_prefix          = local.name_prefix
  ecr_repository_url   = aws_ecr_repository.agents.repository_url
  container_image_tag  = "agentcore-ask-${var.environment}"
  environment          = var.environment
  foundation_model     = var.foundation_model
  enable_memory        = true
  enable_gateway       = false

  environment_variables = {
    DYNAMODB_FINDINGS_TABLE  = module.foundation.findings_table_name
    DYNAMODB_EVIDENCE_TABLE  = module.foundation.evidence_table_name
    DYNAMODB_SCAN_HISTORY    = module.foundation.scan_history_table_name
    DYNAMODB_RESOURCE_GRAPH  = module.foundation.resource_graph_table_name
    S3_EVIDENCE_BUCKET       = module.foundation.evidence_bucket_name
  }

  tags = var.tags
}

# Architect Agent
module "agentcore_architect" {
  source = "../modules/agentcore-architect"

  name_prefix          = local.name_prefix
  ecr_repository_url   = aws_ecr_repository.agents.repository_url
  container_image_tag  = "agentcore-architect-${var.environment}"
  environment          = var.environment
  foundation_model     = var.foundation_model

  environment_variables = {
    DYNAMODB_PRICING_CACHE = module.foundation.pricing_cache_table_name
  }

  tags = var.tags
}

# Remediate Agent
module "agentcore_remediate" {
  source = "../modules/agentcore-remediate"

  name_prefix          = local.name_prefix
  ecr_repository_url   = aws_ecr_repository.agents.repository_url
  container_image_tag  = "agentcore-remediate-${var.environment}"
  environment          = var.environment
  foundation_model     = var.foundation_model

  environment_variables = {
    DYNAMODB_FINDINGS_TABLE      = module.foundation.findings_table_name
    DYNAMODB_REMEDIATIONS_TABLE  = module.foundation.remediations_table_name
    DYNAMODB_APPROVALS_TABLE     = module.foundation.approvals_table_name
    S3_EVIDENCE_BUCKET           = module.foundation.evidence_bucket_name
  }

  tags = var.tags
}
