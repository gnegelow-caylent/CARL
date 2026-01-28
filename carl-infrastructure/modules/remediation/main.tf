# CARL Auto-Remediation Module
terraform {
  required_version = ">= 1.0"
}
resource "aws_dynamodb_table" "remediation" {
  name         = "${var.project_name}-${var.environment}-remediation"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"
  attribute { name = "pk"; type = "S" }
  attribute { name = "sk"; type = "S" }
  tags = var.tags
}
