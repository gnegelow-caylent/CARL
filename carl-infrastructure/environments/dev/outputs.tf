# CARL Development Environment - Outputs

output "api_gateway_endpoint" {
  description = "API Gateway endpoint for Slack"
  value       = module.scanning.api_gateway_endpoint
}

output "slack_events_url" {
  description = "URL to configure in Slack App for Events"
  value       = module.scanning.slack_events_url
}

output "slack_commands_url" {
  description = "URL to configure in Slack App for Commands"
  value       = module.scanning.slack_commands_url
}

output "slack_interactions_url" {
  description = "URL to configure in Slack App for Interactions"
  value       = module.scanning.slack_interactions_url
}

output "evidence_bucket" {
  description = "S3 bucket for evidence storage"
  value       = module.foundation.evidence_bucket_name
}

output "findings_table" {
  description = "DynamoDB table for findings"
  value       = module.foundation.findings_table_name
}

output "findings_processor_function" {
  description = "Findings processor Lambda function name"
  value       = module.scanning.findings_processor_name
}

output "slack_router_function" {
  description = "Slack router Lambda function name"
  value       = module.scanning.slack_router_name
}
