output "agent_runtime_arn" {
  description = "ARN of the AgentCore Runtime for the architect agent"
  value       = aws_bedrockagentcore_agent_runtime.architect.arn
}

output "agent_runtime_id" {
  description = "ID of the AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.architect.id
}

output "agent_runtime_name" {
  description = "Name of the AgentCore Runtime"
  value       = aws_bedrockagentcore_agent_runtime.architect.agent_runtime_name
}

output "execution_role_arn" {
  description = "ARN of the IAM execution role"
  value       = aws_iam_role.agentcore_execution.arn
}

output "execution_role_name" {
  description = "Name of the IAM execution role"
  value       = aws_iam_role.agentcore_execution.name
}
