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
