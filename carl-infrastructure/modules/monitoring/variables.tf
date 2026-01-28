# Monitoring Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "carl"
}

variable "environment" {
  description = "Environment name (dev, qa, prod)"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption"
  type        = string
}

variable "lambda_package_path" {
  description = "Path to Lambda deployment package"
  type        = string
}

variable "enable_xray" {
  description = "Enable X-Ray tracing"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
