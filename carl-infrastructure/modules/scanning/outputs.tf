# CARL Scanning Module - Outputs

# Security Hub
output "security_hub_enabled" {
  description = "Whether Security Hub is enabled"
  value       = var.enable_security_hub
}

# GuardDuty
output "guardduty_detector_id" {
  description = "GuardDuty detector ID"
  value       = var.enable_guardduty ? aws_guardduty_detector.carl[0].id : null
}

# Inspector
output "inspector_enabled" {
  description = "Whether Inspector is enabled"
  value       = var.enable_inspector
}

# Macie
output "macie_enabled" {
  description = "Whether Macie is enabled"
  value       = var.enable_macie
}

# IAM Access Analyzer
output "access_analyzer_arn" {
  description = "ARN of IAM Access Analyzer"
  value       = var.enable_access_analyzer ? aws_accessanalyzer_analyzer.carl[0].arn : null
}

# Lambda Functions
output "findings_processor_arn" {
  description = "ARN of the findings processor Lambda"
  value       = aws_lambda_function.findings_processor.arn
}

output "findings_processor_name" {
  description = "Name of the findings processor Lambda"
  value       = aws_lambda_function.findings_processor.function_name
}

output "slack_router_arn" {
  description = "ARN of the Slack router Lambda"
  value       = aws_lambda_function.slack_router.arn
}

output "slack_router_name" {
  description = "Name of the Slack router Lambda"
  value       = aws_lambda_function.slack_router.function_name
}

# API Gateway
output "api_gateway_endpoint" {
  description = "API Gateway endpoint URL for Slack webhooks"
  value       = aws_apigatewayv2_api.slack.api_endpoint
}

output "slack_events_url" {
  description = "URL for Slack Events subscription"
  value       = "${aws_apigatewayv2_api.slack.api_endpoint}/slack/events"
}

output "slack_commands_url" {
  description = "URL for Slack slash commands"
  value       = "${aws_apigatewayv2_api.slack.api_endpoint}/slack/commands"
}

output "slack_interactions_url" {
  description = "URL for Slack interactive components"
  value       = "${aws_apigatewayv2_api.slack.api_endpoint}/slack/interactions"
}
