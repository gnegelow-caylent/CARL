# Pricing Prefetch Lambda and Monthly Schedule
#
# Runs on 1st of each month at 3am UTC to refresh AWS pricing cache
# Takes 5-10 minutes to fetch pricing for EC2, RDS, Lambda, S3, DynamoDB, ECS

# Lambda function for pricing prefetch
resource "aws_lambda_function" "pricing_prefetch" {
  function_name = "${var.project_name}-${var.environment}-pricing-prefetch"
  role          = aws_iam_role.pricing_prefetch_role.arn
  handler       = "handlers.pricing_prefetch.handler"
  runtime       = "python3.11"
  timeout       = 600  # 10 minutes (prefetch is slow but runs infrequently)
  memory_size   = 512  # More memory for faster execution

  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)

  environment {
    variables = {
      PRICING_CACHE_TABLE = aws_dynamodb_table.pricing_cache.name
      LOG_LEVEL           = "INFO"
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-pricing-prefetch"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# IAM role for pricing prefetch Lambda
resource "aws_iam_role" "pricing_prefetch_role" {
  name = "${var.project_name}-${var.environment}-pricing-prefetch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-pricing-prefetch-role"
    Environment = var.environment
  }
}

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "pricing_prefetch_basic" {
  role       = aws_iam_role.pricing_prefetch_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Policy for DynamoDB access (write to pricing cache)
resource "aws_iam_role_policy" "pricing_prefetch_dynamodb" {
  name = "${var.project_name}-${var.environment}-pricing-prefetch-dynamodb"
  role = aws_iam_role.pricing_prefetch_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.pricing_cache.arn,
          "${aws_dynamodb_table.pricing_cache.arn}/index/*"
        ]
      }
    ]
  })
}

# Policy for AWS Pricing API access
resource "aws_iam_role_policy" "pricing_prefetch_api" {
  name = "${var.project_name}-${var.environment}-pricing-prefetch-api"
  role = aws_iam_role.pricing_prefetch_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "pricing:GetProducts",
          "pricing:DescribeServices",
          "pricing:GetAttributeValues"
        ]
        Resource = "*"
      }
    ]
  })
}

# Policy for CloudWatch metrics
resource "aws_iam_role_policy" "pricing_prefetch_cloudwatch" {
  name = "${var.project_name}-${var.environment}-pricing-prefetch-cloudwatch"
  role = aws_iam_role.pricing_prefetch_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

# EventBridge rule - Monthly execution on 1st at 3am UTC
resource "aws_cloudwatch_event_rule" "pricing_prefetch_schedule" {
  name                = "${var.project_name}-${var.environment}-pricing-prefetch-schedule"
  description         = "Trigger pricing prefetch on 1st of month at 3am UTC"
  schedule_expression = "cron(0 3 1 * ? *)"  # 1st of month at 3am UTC

  tags = {
    Name        = "${var.project_name}-${var.environment}-pricing-prefetch-schedule"
    Environment = var.environment
  }
}

# EventBridge target - Invoke pricing prefetch Lambda
resource "aws_cloudwatch_event_target" "pricing_prefetch_target" {
  rule      = aws_cloudwatch_event_rule.pricing_prefetch_schedule.name
  target_id = "PricingPrefetchLambda"
  arn       = aws_lambda_function.pricing_prefetch.arn
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow_eventbridge_pricing_prefetch" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pricing_prefetch.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pricing_prefetch_schedule.arn
}

# CloudWatch Log Group for pricing prefetch Lambda
resource "aws_cloudwatch_log_group" "pricing_prefetch" {
  name              = "/aws/lambda/${aws_lambda_function.pricing_prefetch.function_name}"
  retention_in_days = 30

  tags = {
    Name        = "${var.project_name}-${var.environment}-pricing-prefetch-logs"
    Environment = var.environment
  }
}

# Note: Outputs moved to outputs.tf to avoid duplication
