# CARL Foundation Module - Outputs

# KMS
output "kms_key_arn" {
  description = "ARN of the CARL KMS key"
  value       = aws_kms_key.carl.arn
}

output "kms_key_id" {
  description = "ID of the CARL KMS key"
  value       = aws_kms_key.carl.key_id
}

# S3
output "evidence_bucket_name" {
  description = "Name of the evidence S3 bucket"
  value       = aws_s3_bucket.evidence.id
}

output "evidence_bucket_arn" {
  description = "ARN of the evidence S3 bucket"
  value       = aws_s3_bucket.evidence.arn
}

# DynamoDB
output "findings_table_name" {
  description = "Name of the findings DynamoDB table"
  value       = aws_dynamodb_table.findings.name
}

output "findings_table_arn" {
  description = "ARN of the findings DynamoDB table"
  value       = aws_dynamodb_table.findings.arn
}

output "preferences_table_name" {
  description = "Name of the preferences DynamoDB table"
  value       = aws_dynamodb_table.preferences.name
}

output "preferences_table_arn" {
  description = "ARN of the preferences DynamoDB table"
  value       = aws_dynamodb_table.preferences.arn
}

output "approvals_table_name" {
  description = "Name of the approvals DynamoDB table"
  value       = aws_dynamodb_table.approvals.name
}

output "approvals_table_arn" {
  description = "ARN of the approvals DynamoDB table"
  value       = aws_dynamodb_table.approvals.arn
}

output "remediations_table_name" {
  description = "Name of the remediations DynamoDB table"
  value       = aws_dynamodb_table.remediations.name
}

output "remediations_table_arn" {
  description = "ARN of the remediations DynamoDB table"
  value       = aws_dynamodb_table.remediations.arn
}

output "conversations_table_name" {
  description = "Name of the conversations DynamoDB table"
  value       = aws_dynamodb_table.conversations.name
}

output "conversations_table_arn" {
  description = "ARN of the conversations DynamoDB table"
  value       = aws_dynamodb_table.conversations.arn
}

# Secrets
output "slack_bot_token_secret_arn" {
  description = "ARN of the Slack bot token secret"
  value       = aws_secretsmanager_secret.slack_bot_token.arn
}

output "slack_signing_secret_arn" {
  description = "ARN of the Slack signing secret"
  value       = aws_secretsmanager_secret.slack_signing_secret.arn
}

# IAM
output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.arn
}

output "lambda_execution_role_name" {
  description = "Name of the Lambda execution role"
  value       = aws_iam_role.lambda_execution.name
}

# EventBridge
output "event_bus_name" {
  description = "Name of the CARL EventBridge bus"
  value       = aws_cloudwatch_event_bus.carl.name
}

output "event_bus_arn" {
  description = "ARN of the CARL EventBridge bus"
  value       = aws_cloudwatch_event_bus.carl.arn
}

# SNS
output "alerts_topic_arn" {
  description = "ARN of the alerts SNS topic"
  value       = aws_sns_topic.alerts.arn
}

# CloudWatch
output "log_group_name" {
  description = "Name of the CARL CloudWatch log group"
  value       = aws_cloudwatch_log_group.carl.name
}

# Reports Bucket
output "reports_bucket_name" {
  description = "Name of the reports S3 bucket"
  value       = aws_s3_bucket.reports.id
}

output "reports_bucket_arn" {
  description = "ARN of the reports S3 bucket"
  value       = aws_s3_bucket.reports.arn
}

# Evidence Table
output "evidence_table_name" {
  description = "Name of the evidence DynamoDB table"
  value       = aws_dynamodb_table.evidence.name
}

output "evidence_table_arn" {
  description = "ARN of the evidence DynamoDB table"
  value       = aws_dynamodb_table.evidence.arn
}

# Exceptions Table
output "exceptions_table_name" {
  description = "Name of the exceptions DynamoDB table"
  value       = aws_dynamodb_table.exceptions.name
}

output "exceptions_table_arn" {
  description = "ARN of the exceptions DynamoDB table"
  value       = aws_dynamodb_table.exceptions.arn
}

# Drift Table
output "drift_table_name" {
  description = "Name of the drift detection DynamoDB table"
  value       = aws_dynamodb_table.drift.name
}

output "drift_table_arn" {
  description = "ARN of the drift detection DynamoDB table"
  value       = aws_dynamodb_table.drift.arn
}

# AI Feedback Table
output "ai_feedback_table_name" {
  description = "Name of the AI feedback DynamoDB table"
  value       = aws_dynamodb_table.ai_feedback.name
}

output "ai_feedback_table_arn" {
  description = "ARN of the AI feedback DynamoDB table"
  value       = aws_dynamodb_table.ai_feedback.arn
}

# Account Info
output "account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "region" {
  description = "AWS Region"
  value       = data.aws_region.current.id
}
