# CARL Development Environment - Variables

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "slack_bot_token" {
  description = "Slack Bot OAuth Token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "slack_signing_secret" {
  description = "Slack Signing Secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "lambda_package_path" {
  description = "Path to Lambda deployment package"
  type        = string
  default     = ""
}
