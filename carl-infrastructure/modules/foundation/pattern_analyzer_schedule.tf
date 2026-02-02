# Pattern Analyzer Lambda - Daily Analysis Schedule
# Runs daily at 2am UTC to analyze scan patterns and generate learned insights

# EventBridge rule for daily pattern analysis
resource "aws_cloudwatch_event_rule" "pattern_analysis" {
  name                = "${var.project_name}-${var.environment}-pattern-analysis"
  description         = "Trigger pattern analysis daily at 2am UTC"
  schedule_expression = "cron(0 2 * * ? *)" # 2am UTC daily

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-pattern-analysis"
    }
  )
}

# Lambda function for pattern analysis
resource "aws_lambda_function" "pattern_analyzer" {
  function_name = "${var.project_name}-${var.environment}-pattern-analyzer"
  role          = aws_iam_role.lambda_execution.arn
  handler       = "handlers.pattern_analyzer.handler"
  runtime       = "python3.11"
  timeout       = 60 # 1 minute should be enough for pattern analysis
  memory_size   = 512

  # Code is deployed via GitHub Actions workflow
  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)

  environment {
    variables = {
      ENVIRONMENT          = var.environment
      SCAN_HISTORY_TABLE   = aws_dynamodb_table.scan_history.name
      RESOURCE_GRAPH_TABLE = aws_dynamodb_table.resource_graph.name
      LOG_LEVEL            = var.log_level
    }
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-pattern-analyzer"
    }
  )
}

# CloudWatch Log Group for pattern analyzer
resource "aws_cloudwatch_log_group" "pattern_analyzer" {
  name              = "/aws/lambda/${aws_lambda_function.pattern_analyzer.function_name}"
  retention_in_days = 14

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-pattern-analyzer-logs"
    }
  )
}

# EventBridge target - invoke pattern analyzer Lambda
resource "aws_cloudwatch_event_target" "pattern_analyzer" {
  rule      = aws_cloudwatch_event_rule.pattern_analysis.name
  target_id = "PatternAnalyzer"
  arn       = aws_lambda_function.pattern_analyzer.arn
}

# Lambda permission for EventBridge to invoke
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pattern_analyzer.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pattern_analysis.arn
}

# IAM policy for pattern analyzer to access learning tables
resource "aws_iam_role_policy" "pattern_analyzer_tables" {
  name = "${var.project_name}-pattern-analyzer-tables"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          aws_dynamodb_table.scan_history.arn,
          "${aws_dynamodb_table.scan_history.arn}/index/*",
          aws_dynamodb_table.resource_graph.arn,
          "${aws_dynamodb_table.resource_graph.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "CARL/Learning"
          }
        }
      }
    ]
  })
}
