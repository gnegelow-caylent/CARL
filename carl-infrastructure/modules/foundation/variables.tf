variable "project_name" {
  type    = string
  default = "carl"
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "kms_key_arn" {
  type    = string
  default = ""
}

variable "lambda_package_path" {
  type = string
}

variable "slack_bot_token" {
  type      = string
  sensitive = true
}

variable "slack_signing_secret" {
  type      = string
  sensitive = true
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "evidence_retention_days" {
  type    = number
  default = 365
}

variable "tags" {
  type    = map(string)
  default = {}
}
