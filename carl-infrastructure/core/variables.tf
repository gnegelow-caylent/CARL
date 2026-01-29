# CARL Core Infrastructure Variables

variable "environment" {
  description = "Environment name (dev, qa, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "qa", "prod"], var.environment)
    error_message = "Environment must be dev, qa, or prod."
  }
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "slack_bot_token" {
  description = "Slack Bot Token (xoxb-...) - Leave empty to configure later"
  type        = string
  default     = ""
  sensitive   = true
}

variable "slack_signing_secret" {
  description = "Slack Signing Secret - Leave empty to configure later"
  type        = string
  default     = ""
  sensitive   = true
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project   = "CARL"
    ManagedBy = "Terraform"
  }
}

# ============================================================================
# FEATURE FLAGS (All disabled by default - deploy on-demand)
# ============================================================================

variable "enable_monitoring" {
  description = "Enable infrastructure monitoring and compliance scanning"
  type        = bool
  default     = false
}

variable "enable_bootstrap" {
  description = "Enable AWS Organizations and account bootstrap automation"
  type        = bool
  default     = false
}

variable "enable_reporting" {
  description = "Enable compliance reporting and evidence collection"
  type        = bool
  default     = false
}

variable "enable_foundation" {
  description = "Enable guided infrastructure builder"
  type        = bool
  default     = false
}

variable "enable_drift_detection" {
  description = "Enable infrastructure drift detection"
  type        = bool
  default     = true
}

variable "enable_auto_remediation" {
  description = "Enable automatic remediation of compliance violations"
  type        = bool
  default     = false
}

variable "enable_compliance_agent" {
  description = "Enable AWS Bedrock Compliance Agent for autonomous SOC 2 assessment"
  type        = bool
  default     = true
}

# ============================================================================
# GITHUB INTEGRATION (For automatic feature deployment)
# ============================================================================

variable "github_token" {
  description = "GitHub Personal Access Token for triggering workflows"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_repo" {
  description = "GitHub repository (format: owner/repo)"
  type        = string
  default     = ""
}

# ============================================================================
# GITHUB INFRASTRUCTURE REPOSITORY (For GitOps infrastructure deployments)
# ============================================================================

variable "github_infra_owner" {
  description = "GitHub organization/user for infrastructure deployments repository"
  type        = string
  default     = "gnegelow-caylent"
}

variable "github_infra_repo" {
  description = "GitHub repository name for infrastructure deployments"
  type        = string
  default     = "carl_infra"
}
