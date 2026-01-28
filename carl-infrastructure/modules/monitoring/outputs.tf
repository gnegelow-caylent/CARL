# Monitoring Module Outputs

output "findings_table_name" {
  description = "Name of the findings DynamoDB table"
  value       = aws_dynamodb_table.findings.name
}

output "findings_table_arn" {
  description = "ARN of the findings DynamoDB table"
  value       = aws_dynamodb_table.findings.arn
}

output "evidence_table_name" {
  description = "Name of the evidence DynamoDB table"
  value       = aws_dynamodb_table.evidence.name
}

output "evidence_bucket_name" {
  description = "Name of the evidence S3 bucket"
  value       = aws_s3_bucket.evidence.id
}

output "reports_bucket_name" {
  description = "Name of the reports S3 bucket"
  value       = aws_s3_bucket.reports.id
}

output "scanner_function_arn" {
  description = "ARN of the scanner Lambda function"
  value       = aws_lambda_function.scanner.arn
}
