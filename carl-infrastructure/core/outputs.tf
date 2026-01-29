# API Gateway Outputs
output "api_endpoint" {
  description = "CARL API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_id" {
  description = "API Gateway ID"
  value       = aws_apigatewayv2_api.carl.id
}

# Lambda Outputs
output "lambda_function_name" {
  description = "CARL Lambda function name"
  value       = aws_lambda_function.carl.function_name
}

output "lambda_function_arn" {
  description = "CARL Lambda function ARN"
  value       = aws_lambda_function.carl.arn
}

# DynamoDB Outputs
output "findings_table_name" {
  description = "Findings DynamoDB table name"
  value       = aws_dynamodb_table.findings.name
}

output "evidence_table_name" {
  description = "Evidence DynamoDB table name"
  value       = aws_dynamodb_table.evidence.name
}

output "exceptions_table_name" {
  description = "Exceptions DynamoDB table name"
  value       = aws_dynamodb_table.exceptions.name
}

output "drift_table_name" {
  description = "Drift DynamoDB table name"
  value       = aws_dynamodb_table.drift.name
}

# S3 Outputs
output "evidence_bucket_name" {
  description = "Evidence S3 bucket name"
  value       = aws_s3_bucket.evidence.id
}

output "reports_bucket_name" {
  description = "Reports S3 bucket name"
  value       = aws_s3_bucket.reports.id
}
