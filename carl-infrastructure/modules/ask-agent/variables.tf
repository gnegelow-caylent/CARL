# Variables for Ask Agent Module

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "tool_lambda_arn" {
  description = "ARN of Lambda function that handles tool calls"
  type        = string
}

variable "tool_lambda_name" {
  description = "Name of Lambda function that handles tool calls"
  type        = string
}

variable "foundation_model" {
  description = "Bedrock foundation model to use"
  type        = string
  default     = "anthropic.claude-sonnet-4-20250514-v1:0"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
