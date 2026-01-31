variable "project_name" {
  description = "Project name (e.g., 'carl')"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., 'dev', 'prod')"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "lambda_zip_path" {
  description = "Path to Lambda deployment package"
  type        = string
}

variable "slack_bot_token_ssm_path" {
  description = "SSM Parameter Store path for Slack bot token"
  type        = string
}

variable "slack_signing_secret_ssm_path" {
  description = "SSM Parameter Store path for Slack signing secret"
  type        = string
}

variable "security_alert_channel" {
  description = "Slack channel for security alerts (e.g., '#carl-security-alerts')"
  type        = string
  default     = "#carl-security-alerts"
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
