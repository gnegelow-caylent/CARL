# CARL Infrastructure

Terraform modules for deploying CARL (Cloud Automated Risk & Compliance Logic) on AWS.

## Structure

```
carl-infrastructure/
├── modules/
│   ├── foundation/         # Phase 0: Core resources (DynamoDB, S3, IAM, Secrets)
│   ├── scanning/           # Phase 1-2: Security services and findings processing
│   ├── remediation/        # Phase 3: Step Functions, remediation Lambda
│   ├── multi-account/      # Phase 4: Cross-account roles and EventBridge
│   ├── github-integration/ # Phase 5: GitHub App webhook handling
│   ├── agentcore-ask/      # AWS Bedrock AgentCore - Ask Agent ✅ DEPLOYED
│   ├── agentcore-architect/# AWS Bedrock AgentCore - Architect Agent ✅ DEPLOYED
│   └── mcp-gateway/        # MCP Gateway for tool integration
├── environments/
│   ├── dev/               # Development environment
│   └── prod/              # Production environment
├── scripts/               # Helper scripts
└── .github/workflows/     # CI/CD pipelines
```

## AWS Bedrock AgentCore Modules

CARL's agents run on AWS Bedrock AgentCore, the managed agent runtime platform.

### Ask Agent (`modules/agentcore-ask/`)
- Intelligent Q&A with AWS environment scanning
- Container deployment via GitHub Actions
- IAM permissions for Bedrock, EC2, S3, IAM read access
- Optional AgentCore Memory and Gateway integration

### Architect Agent (`modules/agentcore-architect/`)
- Architecture recommendations with real-time pricing
- DynamoDB access for pricing cache
- Container deployment via GitHub Actions

### Remediation Agent (`modules/agentcore-remediate/`)
- AI-powered security fixes with human-in-the-loop approval
- Risk-based classification (LOW/MEDIUM/HIGH)
- LOW risk: Direct AWS API (S3 encryption, versioning, IAM password policy)
- MEDIUM/HIGH risk: Creates GitHub PR with Terraform code
- AI-generated Terraform for all fix types
- Container code at `agentcore-code/remediate-agent/`

## Prerequisites

- Terraform >= 1.5.0
- AWS CLI configured with appropriate credentials
- S3 bucket for Terraform state (create manually or use `scripts/bootstrap.sh`)

## Quick Start

### 1. Bootstrap (First Time Only)

```bash
# Create S3 bucket and DynamoDB table for Terraform state
./scripts/bootstrap.sh
```

### 2. Deploy Development Environment

```bash
cd environments/dev
terraform init
terraform plan
terraform apply
```

### 3. Deploy Production Environment

```bash
cd environments/prod
terraform init
terraform plan
terraform apply
```

## Module Usage

### Foundation Module

```hcl
module "foundation" {
  source = "../../modules/foundation"

  environment    = "dev"
  aws_region     = "us-east-1"

  slack_bot_token      = var.slack_bot_token
  slack_signing_secret = var.slack_signing_secret
}
```

### Scanning Module

```hcl
module "scanning" {
  source = "../../modules/scanning"

  environment = "dev"
  aws_region  = "us-east-1"

  foundation_outputs = module.foundation

  enable_guardduty  = true
  enable_inspector  = true
  enable_macie      = true
  macie_bucket_list = ["my-data-bucket"]
}
```

## Variables

See each module's `variables.tf` for available configuration options.

## Outputs

Each module exports outputs that can be used by dependent modules or the application layer.

## State Management

State is stored in S3 with DynamoDB locking:
- Bucket: `carl-terraform-state-{account_id}`
- DynamoDB Table: `carl-terraform-locks`

## Security

- All secrets stored in AWS Secrets Manager
- IAM roles follow least privilege
- S3 buckets encrypted with KMS
- No hardcoded credentials
