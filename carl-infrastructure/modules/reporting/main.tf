# CARL Reporting Module
# Compliance reports and advanced evidence collection

terraform {
  required_version = ">= 1.0"
}

resource "aws_dynamodb_table" "reports" {
  name         = "${var.project_name}-${var.environment}-reports"
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

  tags = var.tags
}
