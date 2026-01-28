# CARL Scanning Module - Variables

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "foundation_outputs" {
  description = "Outputs from the foundation module"
  type = object({
    kms_key_arn                = string
    evidence_bucket_name       = string
    evidence_bucket_arn        = string
    findings_table_name        = string
    findings_table_arn         = string
    preferences_table_name     = string
    preferences_table_arn      = string
    conversations_table_name   = string
    conversations_table_arn    = string
    slack_bot_token_secret_arn = string
    slack_signing_secret_arn   = string
    lambda_execution_role_arn  = string
    event_bus_name             = string
    event_bus_arn              = string
  })
}

# AWS Config
variable "create_config_recorder" {
  description = "Create AWS Config recorder (set to false if already exists)"
  type        = bool
  default     = true
}

variable "enable_soc2_conformance_pack" {
  description = "Deploy SOC 2 conformance pack"
  type        = bool
  default     = true
}

# Security Hub
variable "enable_security_hub" {
  description = "Enable AWS Security Hub"
  type        = bool
  default     = true
}

variable "enable_cis_benchmark" {
  description = "Enable CIS AWS Foundations Benchmark in Security Hub"
  type        = bool
  default     = true
}

# GuardDuty
variable "enable_guardduty" {
  description = "Enable Amazon GuardDuty"
  type        = bool
  default     = true
}

variable "guardduty_s3_protection" {
  description = "Enable GuardDuty S3 protection"
  type        = bool
  default     = false # Cost optimization - enable if needed
}

variable "guardduty_eks_protection" {
  description = "Enable GuardDuty EKS protection"
  type        = bool
  default     = false # Enable if using EKS
}

variable "guardduty_malware_protection" {
  description = "Enable GuardDuty malware protection"
  type        = bool
  default     = false # Cost optimization - enable if needed
}

# Inspector
variable "enable_inspector" {
  description = "Enable Amazon Inspector"
  type        = bool
  default     = true
}

variable "inspector_resource_types" {
  description = "Resource types to scan with Inspector"
  type        = list(string)
  default     = ["EC2", "LAMBDA"]
}

# Macie
variable "enable_macie" {
  description = "Enable Amazon Macie"
  type        = bool
  default     = true
}

variable "macie_bucket_list" {
  description = "List of S3 buckets to scan with Macie"
  type        = list(string)
  default     = []
}

variable "macie_sampling_percentage" {
  description = "Percentage of objects to sample in Macie scans"
  type        = number
  default     = 10 # Cost optimization
}

# IAM Access Analyzer
variable "enable_access_analyzer" {
  description = "Enable IAM Access Analyzer"
  type        = bool
  default     = true
}

# Lambda
variable "lambda_package_path" {
  description = "Path to Lambda deployment package (leave empty for placeholder)"
  type        = string
  default     = ""
}

variable "bedrock_model_id" {
  description = "Bedrock model ID for AI processing"
  type        = string
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "log_level" {
  description = "Log level for Lambda functions"
  type        = string
  default     = "INFO"
}
