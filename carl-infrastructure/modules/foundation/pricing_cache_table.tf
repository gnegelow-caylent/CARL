# Pricing Cache DynamoDB Table
#
# Stores pre-fetched AWS pricing data to avoid slow Price List API calls
# during architecture recommendations.
#
# Refreshed monthly (1st of each month at 3am UTC) by pricing_prefetch Lambda

resource "aws_dynamodb_table" "pricing_cache" {
  name         = "${var.project_name}-${var.environment}-pricing-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "service_resource"
  range_key    = "region"

  attribute {
    name = "service_resource"
    type = "S"
  }

  attribute {
    name = "region"
    type = "S"
  }

  attribute {
    name = "service"
    type = "S"
  }

  # GSI for querying all items for a service (e.g., all EC2 pricing)
  global_secondary_index {
    name            = "ServiceIndex"
    hash_key        = "service"
    range_key       = "service_resource"
    projection_type = "ALL"
  }

  # TTL for automatic cleanup of stale pricing data (90 days)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-pricing-cache"
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "Cache AWS pricing data for fast agent responses"
  }
}

# Table structure:
# - service_resource (PK): "ec2#t3.medium", "rds#db.t3.micro", "lambda#execution"
# - region (SK): "us-east-1", "us-west-2", etc.
# - service: "ec2", "rds", "lambda" (for GSI queries)
# - price_per_hour: Decimal string (e.g., "0.0416")
# - price_per_month: Decimal string (e.g., "30.37")
# - unit: "Hrs", "GB-Mo", "Requests", etc.
# - attributes: JSON blob with full product attributes
# - last_updated: ISO timestamp
# - ttl: Unix timestamp (90 days from last_updated)
