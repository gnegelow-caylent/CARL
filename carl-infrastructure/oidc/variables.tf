# OIDC Module Variables

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "github_org" {
  description = "GitHub organization or username"
  type        = string
  default     = "gnegelow-caylent"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "CARL"
}

variable "terraform_state_bucket" {
  description = "S3 bucket for Terraform state (if using remote backend)"
  type        = string
  default     = "carl-tfstate"
}

variable "terraform_state_lock_table" {
  description = "DynamoDB table for Terraform state locking"
  type        = string
  default     = "carl-tfstate-locks"
}
