# CARL Multi-Agent Handoffs DynamoDB Table
#
# Stores context for seamless handoffs between CARL's agents (Ask, Architect, Remediate).
# TTL enabled for automatic cleanup after 1 hour.
#
# Schema:
#   pk: "HANDOFF#{handoff_id}"
#   sk: "CONTEXT#{source_agent}#{target_agent}"

resource "aws_dynamodb_table" "handoffs" {
  name         = "${var.project_name}-${var.environment}-handoffs"
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

  # TTL for automatic cleanup (handoffs expire after 1 hour)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  # Point-in-time recovery for production
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-handoffs"
    Description = "Multi-agent handoff context storage"
    Feature     = "agent-handoffs"
  })
}
