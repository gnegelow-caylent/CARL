variable "name_prefix" {
  description = "Prefix for resource names (e.g., carl-dev)"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL for AgentCore container images"
  type        = string
}

variable "ecr_repository_arn" {
  description = "ECR repository ARN for IAM permissions"
  type        = string
}

variable "container_image_tag" {
  description = "Tag for the architect agent container image"
  type        = string
  default     = "agentcore-architect"
}

variable "foundation_model" {
  description = "Bedrock model ID to use (inference profile recommended)"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "environment_variables" {
  description = "Additional environment variables for the agent"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
