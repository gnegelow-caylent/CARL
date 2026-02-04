# MCP Gateway Module
# Deploys GitHub, Memory, and Terraform MCP servers on Bedrock AgentCore

locals {
  gateway_name = "${var.name_prefix}-mcp-gateway"
}

# -----------------------------------------------------------------------------
# IAM Role for MCP Gateway
# -----------------------------------------------------------------------------
resource "aws_iam_role" "mcp_gateway" {
  name = "${var.name_prefix}-mcp-gateway-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "bedrock.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "mcp_gateway" {
  name = "${var.name_prefix}-mcp-gateway-policy"
  role = aws_iam_role.mcp_gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaInvoke"
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:*:function:${var.name_prefix}-mcp-*"
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Sid    = "SecretsAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = compact([
          var.github_token_secret_arn,
          var.terraform_cloud_token_secret_arn
        ])
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = var.enable_memory_mcp ? [
          aws_dynamodb_table.knowledge_graph[0].arn,
          "${aws_dynamodb_table.knowledge_graph[0].arn}/index/*"
        ] : []
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Cognito for Gateway Authentication
# -----------------------------------------------------------------------------
resource "aws_cognito_user_pool" "mcp_gateway" {
  name = "${var.name_prefix}-mcp-gateway-pool"

  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = var.tags
}

resource "aws_cognito_user_pool_client" "mcp_gateway" {
  name         = "${var.name_prefix}-mcp-gateway-client"
  user_pool_id = aws_cognito_user_pool.mcp_gateway.id

  generate_secret = true

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30
}

resource "aws_cognito_resource_server" "mcp_gateway" {
  identifier   = "mcp-gateway"
  name         = "${var.name_prefix}-mcp-gateway"
  user_pool_id = aws_cognito_user_pool.mcp_gateway.id

  scope {
    scope_name        = "invoke"
    scope_description = "Invoke MCP tools"
  }
}

# -----------------------------------------------------------------------------
# Knowledge Graph DynamoDB Table (for Memory MCP)
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "knowledge_graph" {
  count = var.enable_memory_mcp ? 1 : 0

  name         = "${var.name_prefix}-knowledge-graph"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "entity_type"
    type = "S"
  }

  # GSI for querying by entity type
  global_secondary_index {
    name            = "entity-type-index"
    hash_key        = "entity_type"
    range_key       = "pk"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = merge(var.tags, {
    Purpose = "MCP Memory Knowledge Graph"
  })
}

# -----------------------------------------------------------------------------
# Lambda Function for GitHub MCP
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "github_mcp" {
  count = var.enable_github_mcp ? 1 : 0

  function_name = "${var.name_prefix}-mcp-github"
  role          = aws_iam_role.mcp_lambda.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:github-latest"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size

  environment {
    variables = {
      GITHUB_TOKEN_SECRET_ARN = var.github_token_secret_arn
      ENVIRONMENT             = var.environment
    }
  }

  tags = merge(var.tags, {
    MCP = "github"
  })

  depends_on = [aws_cloudwatch_log_group.github_mcp]
}

resource "aws_cloudwatch_log_group" "github_mcp" {
  count = var.enable_github_mcp ? 1 : 0

  name              = "/aws/lambda/${var.name_prefix}-mcp-github"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Lambda Function for Memory MCP
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "memory_mcp" {
  count = var.enable_memory_mcp ? 1 : 0

  function_name = "${var.name_prefix}-mcp-memory"
  role          = aws_iam_role.mcp_lambda.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:memory-latest"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size

  environment {
    variables = {
      KNOWLEDGE_GRAPH_TABLE = aws_dynamodb_table.knowledge_graph[0].name
      ENVIRONMENT           = var.environment
    }
  }

  tags = merge(var.tags, {
    MCP = "memory"
  })

  depends_on = [aws_cloudwatch_log_group.memory_mcp]
}

resource "aws_cloudwatch_log_group" "memory_mcp" {
  count = var.enable_memory_mcp ? 1 : 0

  name              = "/aws/lambda/${var.name_prefix}-mcp-memory"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Lambda Function for Terraform MCP
# -----------------------------------------------------------------------------
resource "aws_lambda_function" "terraform_mcp" {
  count = var.enable_terraform_mcp ? 1 : 0

  function_name = "${var.name_prefix}-mcp-terraform"
  role          = aws_iam_role.mcp_lambda.arn
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:terraform-latest"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_size

  environment {
    variables = {
      TF_CLOUD_TOKEN_SECRET_ARN = var.terraform_cloud_token_secret_arn
      ENVIRONMENT               = var.environment
    }
  }

  tags = merge(var.tags, {
    MCP = "terraform"
  })

  depends_on = [aws_cloudwatch_log_group.terraform_mcp]
}

resource "aws_cloudwatch_log_group" "terraform_mcp" {
  count = var.enable_terraform_mcp ? 1 : 0

  name              = "/aws/lambda/${var.name_prefix}-mcp-terraform"
  retention_in_days = var.log_retention_days

  tags = var.tags
}

# -----------------------------------------------------------------------------
# Lambda IAM Role
# -----------------------------------------------------------------------------
resource "aws_iam_role" "mcp_lambda" {
  name = "${var.name_prefix}-mcp-lambda-role"

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

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "mcp_lambda_basic" {
  role       = aws_iam_role.mcp_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "mcp_lambda" {
  name = "${var.name_prefix}-mcp-lambda-policy"
  role = aws_iam_role.mcp_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = compact([
          var.github_token_secret_arn,
          var.terraform_cloud_token_secret_arn
        ])
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = var.enable_memory_mcp ? [
          aws_dynamodb_table.knowledge_graph[0].arn,
          "${aws_dynamodb_table.knowledge_graph[0].arn}/index/*"
        ] : []
      }
    ]
  })
}

# ECR Repository is created by GitHub Actions workflow
# Images are pushed with tags: github-latest, memory-latest, terraform-latest
