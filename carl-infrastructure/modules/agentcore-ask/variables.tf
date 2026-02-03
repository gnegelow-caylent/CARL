# Variables for AgentCore Ask Agent Module
# Container is built by GitHub Actions and pushed to shared ECR repo

variable "name_prefix" {
  description = "Prefix for resource names (e.g., carl-dev)"
  type        = string
}

variable "ecr_repository_url" {
  description = "URL of the shared ECR repository (e.g., 123456789.dkr.ecr.us-east-1.amazonaws.com/carl-lambda)"
  type        = string
}

variable "ecr_repository_arn" {
  description = "ARN of the shared ECR repository for IAM permissions"
  type        = string
}

variable "container_image_tag" {
  description = "Tag for the AgentCore container image"
  type        = string
  default     = "agentcore-ask"
}

variable "tool_lambda_arn" {
  description = "ARN of Lambda function that handles tool calls (optional - for future use)"
  type        = string
  default     = ""
}

variable "foundation_model" {
  description = "Bedrock inference profile ID to use (required for on-demand invocation)"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "enable_memory" {
  description = "Enable AgentCore Memory for persistent learning"
  type        = bool
  default     = true
}

variable "enable_gateway" {
  description = "Enable AgentCore Gateway for tool management"
  type        = bool
  default     = false # Start simple, can enable later
}

variable "environment_variables" {
  description = "Additional environment variables for the agent"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
