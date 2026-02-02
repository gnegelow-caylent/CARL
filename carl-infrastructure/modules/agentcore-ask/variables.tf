# Variables for AgentCore Ask Agent Module

variable "name_prefix" {
  description = "Prefix for resource names (e.g., carl-dev)"
  type        = string
}

variable "code_bucket_name" {
  description = "S3 bucket name containing agent code"
  type        = string
}

variable "code_bucket_arn" {
  description = "S3 bucket ARN containing agent code"
  type        = string
}

variable "code_object_prefix" {
  description = "S3 prefix for agent code (directory containing carl_ask_agent.py)"
  type        = string
  default     = "agentcore/ask-agent"
}

variable "agent_source_path" {
  description = "Path to the directory containing agent source code (carl_ask_agent.py and requirements.txt)"
  type        = string
}

variable "tool_lambda_arn" {
  description = "ARN of Lambda function that handles tool calls"
  type        = string
}

variable "foundation_model" {
  description = "Bedrock foundation model to use"
  type        = string
  default     = "anthropic.claude-sonnet-4-20250514-v1:0"
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
