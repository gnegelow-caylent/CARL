variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "tool_lambda_arn" {
  description = "ARN of Lambda function that implements agent tools"
  type        = string
}

variable "tool_lambda_name" {
  description = "Name of Lambda function that implements agent tools"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
