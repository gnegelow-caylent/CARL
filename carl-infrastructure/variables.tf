# CARL Infrastructure Variables

variable "environment" {
  description = "Environment name (dev, qa, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "qa", "prod"], var.environment)
    error_message = "Environment must be dev, qa, or prod."
  }
}

variable "primary_region" {
  description = "Primary AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "sizing_profile" {
  description = "Sizing profile for cost optimization (minimal, moderate, standard)"
  type        = string
  default     = "moderate"

  validation {
    condition     = contains(["minimal", "moderate", "standard"], var.sizing_profile)
    error_message = "Sizing profile must be minimal, moderate, or standard."
  }
}

variable "enable_cost_optimization" {
  description = "Enable aggressive cost optimization features"
  type        = bool
  default     = true
}

variable "enable_bedrock_caching" {
  description = "Enable response caching for Bedrock to reduce API calls"
  type        = bool
  default     = true
}

variable "enable_slack" {
  description = "Enable Slack integration"
  type        = bool
  default     = false
}

variable "slack_bot_token" {
  description = "Slack Bot Token (xoxb-...)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "slack_signing_secret" {
  description = "Slack Signing Secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "alert_email" {
  description = "Email address for CloudWatch alarms"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project   = "CARL"
    ManagedBy = "Terraform"
  }
}
