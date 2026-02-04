# MCP Gateway Module Outputs

output "gateway_role_arn" {
  description = "ARN of the MCP Gateway IAM role"
  value       = aws_iam_role.mcp_gateway.arn
}

output "lambda_role_arn" {
  description = "ARN of the MCP Lambda IAM role"
  value       = aws_iam_role.mcp_lambda.arn
}

# GitHub MCP Outputs
output "github_mcp_function_arn" {
  description = "ARN of the GitHub MCP Lambda function"
  value       = var.enable_github_mcp ? aws_lambda_function.github_mcp[0].arn : null
}

output "github_mcp_function_name" {
  description = "Name of the GitHub MCP Lambda function"
  value       = var.enable_github_mcp ? aws_lambda_function.github_mcp[0].function_name : null
}

# Memory MCP Outputs
output "memory_mcp_function_arn" {
  description = "ARN of the Memory MCP Lambda function"
  value       = var.enable_memory_mcp ? aws_lambda_function.memory_mcp[0].arn : null
}

output "memory_mcp_function_name" {
  description = "Name of the Memory MCP Lambda function"
  value       = var.enable_memory_mcp ? aws_lambda_function.memory_mcp[0].function_name : null
}

output "knowledge_graph_table_name" {
  description = "Name of the Knowledge Graph DynamoDB table"
  value       = var.enable_memory_mcp ? aws_dynamodb_table.knowledge_graph[0].name : null
}

output "knowledge_graph_table_arn" {
  description = "ARN of the Knowledge Graph DynamoDB table"
  value       = var.enable_memory_mcp ? aws_dynamodb_table.knowledge_graph[0].arn : null
}

# Terraform MCP Outputs
output "terraform_mcp_function_arn" {
  description = "ARN of the Terraform MCP Lambda function"
  value       = var.enable_terraform_mcp ? aws_lambda_function.terraform_mcp[0].arn : null
}

output "terraform_mcp_function_name" {
  description = "Name of the Terraform MCP Lambda function"
  value       = var.enable_terraform_mcp ? aws_lambda_function.terraform_mcp[0].function_name : null
}

# Summary
output "mcp_servers_enabled" {
  description = "Map of which MCP servers are enabled"
  value = {
    github    = var.enable_github_mcp
    memory    = var.enable_memory_mcp
    terraform = var.enable_terraform_mcp
  }
}
