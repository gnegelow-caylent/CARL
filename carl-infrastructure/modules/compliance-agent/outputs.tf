output "agent_id" {
  description = "Bedrock Agent ID"
  value       = aws_bedrockagent_agent.compliance.agent_id
}

output "agent_arn" {
  description = "Bedrock Agent ARN"
  value       = aws_bedrockagent_agent.compliance.agent_arn
}

output "agent_alias_id" {
  description = "Bedrock Agent Alias ID (PROD)"
  value       = aws_bedrockagent_agent_alias.prod.agent_alias_id
}

output "agent_alias_arn" {
  description = "Bedrock Agent Alias ARN"
  value       = aws_bedrockagent_agent_alias.prod.agent_alias_arn
}

output "agent_role_arn" {
  description = "IAM role ARN for Bedrock Agent"
  value       = aws_iam_role.agent.arn
}
