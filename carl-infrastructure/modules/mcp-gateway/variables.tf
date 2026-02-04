# MCP Gateway Module Variables

variable "environment" {
  description = "Environment name (dev, qa, prod)"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# GitHub MCP Configuration
variable "github_token_secret_arn" {
  description = "ARN of the Secrets Manager secret containing GitHub token"
  type        = string
  default     = ""
}

variable "enable_github_mcp" {
  description = "Enable GitHub MCP server"
  type        = bool
  default     = true
}

# Memory MCP Configuration
variable "enable_memory_mcp" {
  description = "Enable Memory MCP server for knowledge graph"
  type        = bool
  default     = true
}

variable "memory_table_name" {
  description = "DynamoDB table name for memory storage"
  type        = string
  default     = ""
}

# Terraform MCP Configuration
variable "enable_terraform_mcp" {
  description = "Enable Terraform MCP server for validation"
  type        = bool
  default     = true
}

variable "terraform_cloud_token_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Terraform Cloud token"
  type        = string
  default     = ""
}

# ECR Configuration
variable "ecr_repository_url" {
  description = "URL of the ECR repository for MCP server images"
  type        = string
}

# Lambda Configuration
variable "lambda_memory_size" {
  description = "Memory size for MCP Lambda functions"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Timeout for MCP Lambda functions"
  type        = number
  default     = 60
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}
