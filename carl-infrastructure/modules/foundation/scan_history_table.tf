# Scan History Table for Continuous Learning
# Stores every scan interaction to learn patterns and improve over time

resource "aws_dynamodb_table" "scan_history" {
  name         = "${var.project_name}-${var.environment}-scan-history"
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
    name = "account_id"
    type = "S"
  }

  attribute {
    name = "question_hash"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # GSI for querying by account
  global_secondary_index {
    name            = "AccountIndex"
    hash_key        = "account_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # GSI for querying similar questions
  global_secondary_index {
    name            = "QuestionPatternIndex"
    hash_key        = "question_hash"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = {
    Name        = "${var.project_name}-scan-history"
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "continuous-learning"
  }
}

# Resource Knowledge Graph Table
# Stores learned relationships between AWS resources

resource "aws_dynamodb_table" "resource_graph" {
  name         = "${var.project_name}-${var.environment}-resource-graph"
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
    name = "resource_id"
    type = "S"
  }

  attribute {
    name = "resource_type"
    type = "S"
  }

  # GSI for querying by resource ID
  global_secondary_index {
    name            = "ResourceIndex"
    hash_key        = "resource_id"
    range_key       = "resource_type"
    projection_type = "ALL"
  }

  # GSI for querying by resource type
  global_secondary_index {
    name            = "TypeIndex"
    hash_key        = "resource_type"
    range_key       = "resource_id"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = data.aws_kms_alias.carl.target_key_arn
  }

  tags = {
    Name        = "${var.project_name}-resource-graph"
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "continuous-learning"
  }
}
