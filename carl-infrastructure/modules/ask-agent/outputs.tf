# Outputs for Ask Agent Module

output "agent_id" {
  description = "ID of the Bedrock Ask Agent"
  value       = aws_bedrockagent_agent.ask.agent_id
}

output "agent_arn" {
  description = "ARN of the Bedrock Ask Agent"
  value       = aws_bedrockagent_agent.ask.agent_arn
}

output "agent_alias_id" {
  description = "ID of the production alias"
  value       = aws_bedrockagent_agent_alias.prod.agent_alias_id
}

output "agent_alias_arn" {
  description = "ARN of the production alias"
  value       = aws_bedrockagent_agent_alias.prod.agent_alias_arn
}
