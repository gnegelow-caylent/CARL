# CARL Scanning Module
# Phase 1-2: Security services configuration and API Gateway/Lambda for Slack

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.18"
    }
  }
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  common_tags = {
    Application = "CARL"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# -----------------------------------------------------------------------------
# AWS Config
# -----------------------------------------------------------------------------

resource "aws_config_configuration_recorder" "carl" {
  count = var.create_config_recorder ? 1 : 0

  name     = "carl-recorder"
  role_arn = aws_iam_role.config[0].arn

  recording_group {
    all_supported = true
  }
}

resource "aws_iam_role" "config" {
  count = var.create_config_recorder ? 1 : 0

  name = "carl-config-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "config" {
  count = var.create_config_recorder ? 1 : 0

  role       = aws_iam_role.config[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

resource "aws_config_delivery_channel" "carl" {
  count = var.create_config_recorder ? 1 : 0

  name           = "carl-delivery-channel"
  s3_bucket_name = var.foundation_outputs.evidence_bucket_name
  s3_key_prefix  = "config"

  depends_on = [aws_config_configuration_recorder.carl]
}

resource "aws_config_configuration_recorder_status" "carl" {
  count = var.create_config_recorder ? 1 : 0

  name       = aws_config_configuration_recorder.carl[0].name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.carl]
}

# SOC 2 Conformance Pack
resource "aws_config_conformance_pack" "soc2" {
  count = var.enable_soc2_conformance_pack ? 1 : 0

  name = "carl-soc2-conformance-pack"

  template_body = <<-EOT
    AWSTemplateFormatVersion: '2010-09-09'
    Description: SOC 2 Compliance Conformance Pack for CARL

    Resources:
      S3BucketPublicReadProhibited:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: s3-bucket-public-read-prohibited
          Source:
            Owner: AWS
            SourceIdentifier: S3_BUCKET_PUBLIC_READ_PROHIBITED

      S3BucketPublicWriteProhibited:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: s3-bucket-public-write-prohibited
          Source:
            Owner: AWS
            SourceIdentifier: S3_BUCKET_PUBLIC_WRITE_PROHIBITED

      S3BucketSSLRequestsOnly:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: s3-bucket-ssl-requests-only
          Source:
            Owner: AWS
            SourceIdentifier: S3_BUCKET_SSL_REQUESTS_ONLY

      S3BucketServerSideEncryption:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: s3-bucket-server-side-encryption-enabled
          Source:
            Owner: AWS
            SourceIdentifier: S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED

      EncryptedVolumes:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: encrypted-volumes
          Source:
            Owner: AWS
            SourceIdentifier: ENCRYPTED_VOLUMES

      RDSStorageEncrypted:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: rds-storage-encrypted
          Source:
            Owner: AWS
            SourceIdentifier: RDS_STORAGE_ENCRYPTED

      CloudTrailEnabled:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: cloudtrail-enabled
          Source:
            Owner: AWS
            SourceIdentifier: CLOUD_TRAIL_ENABLED

      CloudTrailEncryptionEnabled:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: cloud-trail-encryption-enabled
          Source:
            Owner: AWS
            SourceIdentifier: CLOUD_TRAIL_ENCRYPTION_ENABLED

      IAMPasswordPolicy:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: iam-password-policy
          Source:
            Owner: AWS
            SourceIdentifier: IAM_PASSWORD_POLICY

      IAMUserMFAEnabled:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: iam-user-mfa-enabled
          Source:
            Owner: AWS
            SourceIdentifier: IAM_USER_MFA_ENABLED

      RootAccountMFAEnabled:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: root-account-mfa-enabled
          Source:
            Owner: AWS
            SourceIdentifier: ROOT_ACCOUNT_MFA_ENABLED

      IAMRootAccessKeyCheck:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: iam-root-access-key-check
          Source:
            Owner: AWS
            SourceIdentifier: IAM_ROOT_ACCESS_KEY_CHECK

      VPCDefaultSecurityGroupClosed:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: vpc-default-security-group-closed
          Source:
            Owner: AWS
            SourceIdentifier: VPC_DEFAULT_SECURITY_GROUP_CLOSED

      RestrictedSSH:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: restricted-ssh
          Source:
            Owner: AWS
            SourceIdentifier: INCOMING_SSH_DISABLED

      RestrictedCommonPorts:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: restricted-common-ports
          Source:
            Owner: AWS
            SourceIdentifier: RESTRICTED_INCOMING_TRAFFIC
          InputParameters:
            blockedPort1: '3389'
            blockedPort2: '3306'
            blockedPort3: '1433'
            blockedPort4: '5432'

      RDSInstancePublicAccessCheck:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: rds-instance-public-access-check
          Source:
            Owner: AWS
            SourceIdentifier: RDS_INSTANCE_PUBLIC_ACCESS_CHECK

      RDSMultiAZSupport:
        Type: AWS::Config::ConfigRule
        Properties:
          ConfigRuleName: rds-multi-az-support
          Source:
            Owner: AWS
            SourceIdentifier: RDS_MULTI_AZ_SUPPORT
  EOT

  depends_on = [aws_config_configuration_recorder_status.carl]

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Security Hub
# -----------------------------------------------------------------------------

resource "aws_securityhub_account" "carl" {
  count = var.enable_security_hub ? 1 : 0

  enable_default_standards = false
}

resource "aws_securityhub_standards_subscription" "aws_foundational" {
  count = var.enable_security_hub ? 1 : 0

  standards_arn = "arn:aws:securityhub:${local.region}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.carl]
}

resource "aws_securityhub_standards_subscription" "cis" {
  count = var.enable_security_hub && var.enable_cis_benchmark ? 1 : 0

  standards_arn = "arn:aws:securityhub:${local.region}::standards/cis-aws-foundations-benchmark/v/1.4.0"

  depends_on = [aws_securityhub_account.carl]
}

# -----------------------------------------------------------------------------
# GuardDuty
# -----------------------------------------------------------------------------

resource "aws_guardduty_detector" "carl" {
  count = var.enable_guardduty ? 1 : 0

  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"

  datasources {
    s3_logs {
      enable = var.guardduty_s3_protection
    }
    kubernetes {
      audit_logs {
        enable = var.guardduty_eks_protection
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = var.guardduty_malware_protection
        }
      }
    }
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Inspector
# -----------------------------------------------------------------------------

resource "aws_inspector2_enabler" "carl" {
  count = var.enable_inspector ? 1 : 0

  account_ids    = [local.account_id]
  resource_types = var.inspector_resource_types
}

# -----------------------------------------------------------------------------
# Macie
# -----------------------------------------------------------------------------

resource "aws_macie2_account" "carl" {
  count = var.enable_macie ? 1 : 0

  finding_publishing_frequency = "FIFTEEN_MINUTES"
  status                       = "ENABLED"
}

resource "aws_macie2_classification_job" "sensitive_data" {
  count = var.enable_macie && length(var.macie_bucket_list) > 0 ? 1 : 0

  name     = "carl-sensitive-data-discovery"
  job_type = "SCHEDULED"

  s3_job_definition {
    bucket_definitions {
      account_id = local.account_id
      buckets    = var.macie_bucket_list
    }
    scoping {
      excludes {
        and {
          simple_scope_term {
            comparator = "STARTS_WITH"
            key        = "OBJECT_KEY"
            values     = ["."]
          }
        }
      }
    }
  }

  schedule_frequency {
    weekly_schedule = "SUNDAY"
  }

  sampling_percentage = var.macie_sampling_percentage

  depends_on = [aws_macie2_account.carl]

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# IAM Access Analyzer
# -----------------------------------------------------------------------------

resource "aws_accessanalyzer_analyzer" "carl" {
  count = var.enable_access_analyzer ? 1 : 0

  analyzer_name = "carl-access-analyzer-${var.environment}"
  type          = "ACCOUNT"

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# EventBridge Rules for Finding Aggregation
# -----------------------------------------------------------------------------

# Security Hub Findings
resource "aws_cloudwatch_event_rule" "security_hub_findings" {
  count = var.enable_security_hub ? 1 : 0

  name           = "carl-security-hub-findings-${var.environment}"
  description    = "Capture Security Hub findings for CARL"
  event_bus_name = "default"

  event_pattern = jsonencode({
    source      = ["aws.securityhub"]
    detail-type = ["Security Hub Findings - Imported"]
  })

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "security_hub_to_carl" {
  count = var.enable_security_hub ? 1 : 0

  rule           = aws_cloudwatch_event_rule.security_hub_findings[0].name
  event_bus_name = "default"
  target_id      = "carl-findings-processor"
  arn            = aws_lambda_function.findings_processor.arn
}

# GuardDuty Findings
resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  count = var.enable_guardduty ? 1 : 0

  name           = "carl-guardduty-findings-${var.environment}"
  description    = "Capture GuardDuty findings for CARL"
  event_bus_name = "default"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
  })

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "guardduty_to_carl" {
  count = var.enable_guardduty ? 1 : 0

  rule           = aws_cloudwatch_event_rule.guardduty_findings[0].name
  event_bus_name = "default"
  target_id      = "carl-findings-processor"
  arn            = aws_lambda_function.findings_processor.arn
}

# Inspector Findings
resource "aws_cloudwatch_event_rule" "inspector_findings" {
  count = var.enable_inspector ? 1 : 0

  name           = "carl-inspector-findings-${var.environment}"
  description    = "Capture Inspector findings for CARL"
  event_bus_name = "default"

  event_pattern = jsonencode({
    source      = ["aws.inspector2"]
    detail-type = ["Inspector2 Finding"]
  })

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "inspector_to_carl" {
  count = var.enable_inspector ? 1 : 0

  rule           = aws_cloudwatch_event_rule.inspector_findings[0].name
  event_bus_name = "default"
  target_id      = "carl-findings-processor"
  arn            = aws_lambda_function.findings_processor.arn
}

# Macie Findings
resource "aws_cloudwatch_event_rule" "macie_findings" {
  count = var.enable_macie ? 1 : 0

  name           = "carl-macie-findings-${var.environment}"
  description    = "Capture Macie findings for CARL"
  event_bus_name = "default"

  event_pattern = jsonencode({
    source      = ["aws.macie"]
    detail-type = ["Macie Finding"]
  })

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "macie_to_carl" {
  count = var.enable_macie ? 1 : 0

  rule           = aws_cloudwatch_event_rule.macie_findings[0].name
  event_bus_name = "default"
  target_id      = "carl-findings-processor"
  arn            = aws_lambda_function.findings_processor.arn
}

# IAM Access Analyzer Findings
resource "aws_cloudwatch_event_rule" "access_analyzer_findings" {
  count = var.enable_access_analyzer ? 1 : 0

  name           = "carl-access-analyzer-findings-${var.environment}"
  description    = "Capture IAM Access Analyzer findings for CARL"
  event_bus_name = "default"

  event_pattern = jsonencode({
    source      = ["aws.access-analyzer"]
    detail-type = ["Access Analyzer Finding"]
  })

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "access_analyzer_to_carl" {
  count = var.enable_access_analyzer ? 1 : 0

  rule           = aws_cloudwatch_event_rule.access_analyzer_findings[0].name
  event_bus_name = "default"
  target_id      = "carl-findings-processor"
  arn            = aws_lambda_function.findings_processor.arn
}

# Config Compliance Changes
resource "aws_cloudwatch_event_rule" "config_compliance" {
  name           = "carl-config-compliance-${var.environment}"
  description    = "Capture Config compliance changes for CARL"
  event_bus_name = "default"

  event_pattern = jsonencode({
    source      = ["aws.config"]
    detail-type = ["Config Rules Compliance Change"]
  })

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "config_to_carl" {
  rule           = aws_cloudwatch_event_rule.config_compliance.name
  event_bus_name = "default"
  target_id      = "carl-findings-processor"
  arn            = aws_lambda_function.findings_processor.arn
}

# -----------------------------------------------------------------------------
# Lambda: Findings Processor
# -----------------------------------------------------------------------------

resource "aws_lambda_function" "findings_processor" {
  function_name = "carl-findings-processor-${var.environment}"
  role          = var.foundation_outputs.lambda_execution_role_arn
  handler       = "findings_processor.handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 256

  filename         = var.lambda_package_path != "" ? var.lambda_package_path : "${path.module}/placeholder.zip"
  source_code_hash = var.lambda_package_path != "" ? filebase64sha256(var.lambda_package_path) : null

  architectures = ["arm64"]

  environment {
    variables = {
      ENVIRONMENT       = var.environment
      FINDINGS_TABLE    = var.foundation_outputs.findings_table_name
      PREFERENCES_TABLE = var.foundation_outputs.preferences_table_name
      EVIDENCE_BUCKET   = var.foundation_outputs.evidence_bucket_name
      SLACK_SECRET_ARN  = var.foundation_outputs.slack_bot_token_secret_arn
      EVENT_BUS_NAME    = var.foundation_outputs.event_bus_name
      LOG_LEVEL         = var.log_level
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "eventbridge_findings" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.findings_processor.function_name
  principal     = "events.amazonaws.com"
}

# -----------------------------------------------------------------------------
# API Gateway for Slack
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "slack" {
  name          = "carl-slack-api-${var.environment}"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://slack.com"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type", "x-slack-signature", "x-slack-request-timestamp"]
    max_age       = 300
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_stage" "slack" {
  api_id      = aws_apigatewayv2_api.slack.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      ip               = "$context.identity.sourceIp"
      requestTime      = "$context.requestTime"
      httpMethod       = "$context.httpMethod"
      routeKey         = "$context.routeKey"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      integrationError = "$context.integrationErrorMessage"
    })
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/carl-slack-${var.environment}"
  retention_in_days = 14

  tags = local.common_tags
}

# Lambda: Slack Router
resource "aws_lambda_function" "slack_router" {
  function_name = "carl-slack-router-${var.environment}"
  role          = var.foundation_outputs.lambda_execution_role_arn
  handler       = "slack_router.handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 256

  filename         = var.lambda_package_path != "" ? var.lambda_package_path : "${path.module}/placeholder.zip"
  source_code_hash = var.lambda_package_path != "" ? filebase64sha256(var.lambda_package_path) : null

  architectures = ["arm64"]

  environment {
    variables = {
      ENVIRONMENT              = var.environment
      FINDINGS_TABLE           = var.foundation_outputs.findings_table_name
      PREFERENCES_TABLE        = var.foundation_outputs.preferences_table_name
      CONVERSATIONS_TABLE      = var.foundation_outputs.conversations_table_name
      SLACK_TOKEN_SECRET_ARN   = var.foundation_outputs.slack_bot_token_secret_arn
      SLACK_SIGNING_SECRET_ARN = var.foundation_outputs.slack_signing_secret_arn
      BEDROCK_MODEL_ID         = var.bedrock_model_id
      LOG_LEVEL                = var.log_level
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_permission" "api_gateway_slack" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_router.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.slack.execution_arn}/*/*"
}

# API Gateway Routes
resource "aws_apigatewayv2_integration" "slack_router" {
  api_id                 = aws_apigatewayv2_api.slack.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.slack_router.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "slack_events" {
  api_id    = aws_apigatewayv2_api.slack.id
  route_key = "POST /slack/events"
  target    = "integrations/${aws_apigatewayv2_integration.slack_router.id}"
}

resource "aws_apigatewayv2_route" "slack_commands" {
  api_id    = aws_apigatewayv2_api.slack.id
  route_key = "POST /slack/commands"
  target    = "integrations/${aws_apigatewayv2_integration.slack_router.id}"
}

resource "aws_apigatewayv2_route" "slack_interactions" {
  api_id    = aws_apigatewayv2_api.slack.id
  route_key = "POST /slack/interactions"
  target    = "integrations/${aws_apigatewayv2_integration.slack_router.id}"
}

# Create placeholder zip for initial deployment
resource "local_file" "placeholder_handler" {
  count    = var.lambda_package_path == "" ? 1 : 0
  filename = "${path.module}/placeholder_handler.py"
  content  = <<-EOT
    def handler(event, context):
        return {
            'statusCode': 200,
            'body': 'CARL placeholder - deploy actual code'
        }
  EOT
}

data "archive_file" "placeholder" {
  count       = var.lambda_package_path == "" ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"

  source {
    content  = <<-EOT
      def handler(event, context):
          return {
              'statusCode': 200,
              'body': 'CARL placeholder - deploy actual code'
          }
    EOT
    filename = "findings_processor.py"
  }

  source {
    content  = <<-EOT
      def handler(event, context):
          return {
              'statusCode': 200,
              'body': 'CARL placeholder - deploy actual code'
          }
    EOT
    filename = "slack_router.py"
  }
}
