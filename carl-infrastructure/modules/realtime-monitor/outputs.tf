output "lambda_function_name" {
  description = "Name of the real-time security monitor Lambda function"
  value       = aws_lambda_function.realtime_security_monitor.function_name
}

output "lambda_function_arn" {
  description = "ARN of the real-time security monitor Lambda function"
  value       = aws_lambda_function.realtime_security_monitor.arn
}

output "security_alert_topic_arn" {
  description = "ARN of the SNS topic for security alerts"
  value       = aws_sns_topic.security_alerts.arn
}

output "eventbridge_rules" {
  description = "Map of EventBridge rule names and ARNs"
  value = {
    s3_security          = aws_cloudwatch_event_rule.s3_security.arn
    ec2_security         = aws_cloudwatch_event_rule.ec2_security.arn
    iam_security         = aws_cloudwatch_event_rule.iam_security.arn
    cloudtrail_security  = aws_cloudwatch_event_rule.cloudtrail_security.arn
    guardduty_security   = aws_cloudwatch_event_rule.guardduty_security.arn
    securityhub_security = aws_cloudwatch_event_rule.securityhub_security.arn
    rds_security         = aws_cloudwatch_event_rule.rds_security.arn
    kms_security         = aws_cloudwatch_event_rule.kms_security.arn
  }
}
