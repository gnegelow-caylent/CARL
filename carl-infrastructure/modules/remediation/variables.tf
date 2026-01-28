variable "project_name" { type = string }
variable "environment" { type = string }
variable "kms_key_arn" { type = string }
variable "lambda_package_path" { type = string }
variable "tags" { type = map(string); default = {} }
