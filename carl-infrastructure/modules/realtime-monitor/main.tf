/**
 * Real-Time Security Monitor Module
 *
 * Deploys Lambda function and EventBridge rules for instant security alerts.
 *
 * Architecture:
 *   CloudTrail → EventBridge Rules → Lambda → Slack
 *
 * Detects security-relevant changes within 60 seconds:
 * - S3 buckets made public or encryption disabled
 * - Security groups opened to 0.0.0.0/0
 * - IAM policy changes, MFA removed
 * - CloudTrail/GuardDuty/Security Hub disabled
 */

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Lambda function for real-time security monitoring
resource "aws_lambda_function" "realtime_security_monitor" {
  function_name = "${var.project_name}-${var.environment}-realtime-security-monitor"
  role          = aws_iam_role.realtime_monitor.arn
  handler       = "handlers.real_time_security_monitor.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60
  memory_size   = 256

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  environment {
    variables = {
      SECURITY_ALERT_CHANNEL   = var.security_alert_channel
      SECURITY_ALERT_TOPIC     = aws_sns_topic.security_alerts.arn
      SLACK_BOT_TOKEN_SSM_PATH = var.slack_bot_token_ssm_path
      SLACK_SIGNING_SSM_PATH   = var.slack_signing_secret_ssm_path
    }
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-realtime-security-monitor"
    Component   = "SecurityMonitoring"
    Description = "Real-time security change detection and alerting"
  })
}

# CloudWatch Logs for Lambda
resource "aws_cloudwatch_log_group" "realtime_monitor" {
  name              = "/aws/lambda/${aws_lambda_function.realtime_security_monitor.function_name}"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# SNS topic for fallback alerts
resource "aws_sns_topic" "security_alerts" {
  name = "${var.project_name}-${var.environment}-security-alerts"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-security-alerts"
    Description = "Fallback topic for security alerts when Slack unavailable"
  })
}

# IAM role for Lambda
resource "aws_iam_role" "realtime_monitor" {
  name = "${var.project_name}-${var.environment}-realtime-monitor-role"

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

# Lambda execution policy
resource "aws_iam_role_policy" "realtime_monitor" {
  name = "realtime-monitor-policy"
  role = aws_iam_role.realtime_monitor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.slack_bot_token_ssm_path}",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.slack_signing_secret_ssm_path}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.security_alerts.arn
      }
    ]
  })
}

# Data source for current account
data "aws_caller_identity" "current" {}

# EventBridge Rules for Security Events

# S3 Security Events
resource "aws_cloudwatch_event_rule" "s3_security" {
  name        = "${var.project_name}-${var.environment}-s3-security-events"
  description = "Capture S3 security-relevant events (public access, encryption changes)"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "PutBucketPublicAccessBlock",
        "DeleteBucketEncryption",
        "PutBucketEncryption",
        "PutBucketPolicy",
        "DeleteBucketPolicy",
        "PutBucketAcl"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "s3_security" {
  rule      = aws_cloudwatch_event_rule.s3_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "s3_security" {
  statement_id  = "AllowExecutionFromEventBridge-S3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.s3_security.arn
}

# EC2 Security Group Events
resource "aws_cloudwatch_event_rule" "ec2_security" {
  name        = "${var.project_name}-${var.environment}-ec2-security-events"
  description = "Capture EC2 security group changes (0.0.0.0/0 rules)"

  event_pattern = jsonencode({
    source      = ["aws.ec2"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "AuthorizeSecurityGroupIngress",
        "AuthorizeSecurityGroupEgress",
        "RevokeSecurityGroupIngress",
        "RevokeSecurityGroupEgress",
        "ModifySecurityGroupRules"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "ec2_security" {
  rule      = aws_cloudwatch_event_rule.ec2_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "ec2_security" {
  statement_id  = "AllowExecutionFromEventBridge-EC2"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_security.arn
}

# IAM Security Events
resource "aws_cloudwatch_event_rule" "iam_security" {
  name        = "${var.project_name}-${var.environment}-iam-security-events"
  description = "Capture IAM security changes (policies, MFA, access keys)"

  event_pattern = jsonencode({
    source      = ["aws.iam"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "PutUserPolicy",
        "AttachUserPolicy",
        "DetachUserPolicy",
        "CreateAccessKey",
        "DeleteAccessKey",
        "DeactivateMFADevice",
        "DeleteAccountPasswordPolicy",
        "UpdateAccountPasswordPolicy",
        "CreatePolicyVersion",
        "SetDefaultPolicyVersion"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "iam_security" {
  rule      = aws_cloudwatch_event_rule.iam_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "iam_security" {
  statement_id  = "AllowExecutionFromEventBridge-IAM"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.iam_security.arn
}

# CloudTrail Security Events
resource "aws_cloudwatch_event_rule" "cloudtrail_security" {
  name        = "${var.project_name}-${var.environment}-cloudtrail-security-events"
  description = "Capture CloudTrail being stopped or deleted"

  event_pattern = jsonencode({
    source      = ["aws.cloudtrail"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "StopLogging",
        "DeleteTrail",
        "UpdateTrail"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "cloudtrail_security" {
  rule      = aws_cloudwatch_event_rule.cloudtrail_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "cloudtrail_security" {
  statement_id  = "AllowExecutionFromEventBridge-CloudTrail"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cloudtrail_security.arn
}

# GuardDuty Security Events
resource "aws_cloudwatch_event_rule" "guardduty_security" {
  name        = "${var.project_name}-${var.environment}-guardduty-security-events"
  description = "Capture GuardDuty being disabled"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "DeleteDetector",
        "StopMonitoringMembers",
        "DisassociateFromMasterAccount"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "guardduty_security" {
  rule      = aws_cloudwatch_event_rule.guardduty_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "guardduty_security" {
  statement_id  = "AllowExecutionFromEventBridge-GuardDuty"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.guardduty_security.arn
}

# Security Hub Events
resource "aws_cloudwatch_event_rule" "securityhub_security" {
  name        = "${var.project_name}-${var.environment}-securityhub-security-events"
  description = "Capture Security Hub being disabled"

  event_pattern = jsonencode({
    source      = ["aws.securityhub"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "DisableSecurityHub",
        "DeleteMembers",
        "DisassociateFromMasterAccount"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "securityhub_security" {
  rule      = aws_cloudwatch_event_rule.securityhub_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "securityhub_security" {
  statement_id  = "AllowExecutionFromEventBridge-SecurityHub"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.securityhub_security.arn
}

# RDS Security Events
resource "aws_cloudwatch_event_rule" "rds_security" {
  name        = "${var.project_name}-${var.environment}-rds-security-events"
  description = "Capture RDS security changes (public accessibility)"

  event_pattern = jsonencode({
    source      = ["aws.rds"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "ModifyDBInstance",
        "ModifyDBCluster"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "rds_security" {
  rule      = aws_cloudwatch_event_rule.rds_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "rds_security" {
  statement_id  = "AllowExecutionFromEventBridge-RDS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.rds_security.arn
}

# KMS Security Events
resource "aws_cloudwatch_event_rule" "kms_security" {
  name        = "${var.project_name}-${var.environment}-kms-security-events"
  description = "Capture KMS key changes (disable, schedule deletion)"

  event_pattern = jsonencode({
    source      = ["aws.kms"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = [
        "DisableKey",
        "ScheduleKeyDeletion",
        "PutKeyPolicy"
      ]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "kms_security" {
  rule      = aws_cloudwatch_event_rule.kms_security.name
  target_id = "RealTimeSecurityMonitor"
  arn       = aws_lambda_function.realtime_security_monitor.arn
}

resource "aws_lambda_permission" "kms_security" {
  statement_id  = "AllowExecutionFromEventBridge-KMS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.realtime_security_monitor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.kms_security.arn
}
