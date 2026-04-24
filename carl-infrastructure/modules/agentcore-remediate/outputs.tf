# Outputs for AgentCore Remediation Agent Module

output "runtime_id" {
  description = "ID of the AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.remediate.agent_runtime_id
}

output "runtime_arn" {
  description = "ARN of the AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.remediate.agent_runtime_arn
}

output "runtime_name" {
  description = "Name of the AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.remediate.agent_runtime_name
}

output "role_arn" {
  description = "ARN of the IAM role used by the runtime"
  value       = aws_iam_role.agentcore_execution.arn
}

output "container_image_uri" {
  description = "Full container image URI used by the AgentCore runtime"
  value       = "${var.ecr_repository_url}:${var.container_image_tag}"
}

output "memory_id" {
  description = "ID of the AgentCore Memory (if enabled)"
  value       = var.enable_memory ? aws_bedrockagentcore_memory.remediate[0].id : null
}

output "gateway_id" {
  description = "ID of the AgentCore Gateway (if enabled)"
  value       = var.enable_gateway ? aws_bedrockagentcore_gateway.remediate_tools[0].gateway_id : null
}

output "gateway_url" {
  description = "URL of the AgentCore Gateway (if enabled)"
  value       = var.enable_gateway ? aws_bedrockagentcore_gateway.remediate_tools[0].gateway_url : null
}
