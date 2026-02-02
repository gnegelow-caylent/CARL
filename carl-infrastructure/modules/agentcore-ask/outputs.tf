# Outputs for AgentCore Ask Agent Module

output "runtime_id" {
  description = "ID of the AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.ask.agent_runtime_id
}

output "runtime_arn" {
  description = "ARN of the AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.ask.agent_runtime_arn
}

output "role_arn" {
  description = "ARN of the IAM role used by the runtime"
  value       = aws_iam_role.agentcore_execution.arn
}

output "memory_id" {
  description = "ID of the AgentCore Memory (if enabled)"
  value       = var.enable_memory ? aws_bedrockagentcore_memory.ask[0].id : null
}

output "gateway_id" {
  description = "ID of the AgentCore Gateway (if enabled)"
  value       = var.enable_gateway ? aws_bedrockagentcore_gateway.ask_tools[0].gateway_id : null
}

output "gateway_url" {
  description = "URL of the AgentCore Gateway (if enabled)"
  value       = var.enable_gateway ? aws_bedrockagentcore_gateway.ask_tools[0].gateway_url : null
}
