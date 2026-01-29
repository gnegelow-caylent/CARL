output "table_name" {
  description = "Name of the drift detection DynamoDB table"
  value       = aws_dynamodb_table.drift.name
}

output "table_arn" {
  description = "ARN of the drift detection DynamoDB table"
  value       = aws_dynamodb_table.drift.arn
}
