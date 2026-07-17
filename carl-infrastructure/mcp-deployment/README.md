# CARL MCP Deployment

Deploy CARL infrastructure to your AWS account for use with Claude Desktop via MCP.

## Overview

This deployment creates:
- **3 AgentCore Runtimes** (Ask, Architect, Remediate agents)
- **DynamoDB Tables** (findings, evidence, scan history, etc.)
- **S3 Buckets** (evidence storage, reports)
- **ECR Repository** (agent container images)
- **IAM Roles** (AgentCore execution permissions)

**Cost Estimate:** ~$50-100/month depending on usage

## Prerequisites

1. **AWS Account** with admin permissions
2. **AWS CLI** configured (`aws configure`)
3. **Terraform** >= 1.0 installed
4. **Docker** installed (for building agent containers)
5. **Python** 3.11+ installed
6. **Claude Desktop** installed

## Quick Start

### 1. Deploy Infrastructure

```bash
# Clone the repository
git clone https://github.com/gnegelow-caylent/CARL.git
cd CARL/carl-infrastructure/mcp-deployment

# Initialize Terraform
terraform init

# Review the plan
terraform plan -var="environment=prod" -var="region=us-east-1"

# Deploy (takes ~10-15 minutes)
terraform apply -var="environment=prod" -var="region=us-east-1"
```

**Note:** Save the outputs - you'll need them for configuration!

### 2. Build and Push Agent Containers

```bash
# Get ECR repository URL from terraform output
ECR_REPO=$(terraform output -raw ecr_repository_url)

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REPO

# Build and push all three agents
cd ../agentcore-code

# Ask Agent
docker buildx build --platform linux/arm64 \
  -t $ECR_REPO:agentcore-ask-prod \
  -f ask-agent/Dockerfile \
  --push .

# Architect Agent
docker buildx build --platform linux/arm64 \
  -t $ECR_REPO:agentcore-architect-prod \
  -f architect-agent/Dockerfile \
  --push .

# Remediate Agent
docker buildx build --platform linux/arm64 \
  -t $ECR_REPO:agentcore-remediate-prod \
  -f remediate-agent/Dockerfile \
  --push .
```

### 3. Install MCP Server

```bash
pip install carl-mcp-server
```

### 4. Configure Claude Desktop

Get your configuration:
```bash
terraform output -raw claude_desktop_config
```

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "carl": {
      "command": "python",
      "args": ["-m", "carl_mcp_server"],
      "env": {
        "AWS_PROFILE": "your-aws-profile",
        "AWS_REGION": "us-east-1",
        "CARL_AGENTCORE_ASK_ARN": "arn:aws:bedrock-agentcore:...",
        "CARL_AGENTCORE_ARCHITECT_ARN": "arn:aws:bedrock-agentcore:...",
        "CARL_AGENTCORE_REMEDIATE_ARN": "arn:aws:bedrock-agentcore:...",
        "CARL_DYNAMODB_PREFIX": "carl-prod",
        "CARL_S3_EVIDENCE_BUCKET": "carl-prod-evidence-...",
        "CARL_S3_REPORTS_BUCKET": "carl-prod-reports-..."
      }
    }
  }
}
```

### 5. Restart Claude Desktop

### 6. Test

Ask Claude:
```
Use carl_ask to check my AWS security posture
```

## Detailed Setup

### IAM Permissions Required

The AWS credentials used for deployment need:
- Full access to deploy infrastructure (admin recommended)

The AWS profile used in MCP needs:
- `bedrock:InvokeAgentRuntime` (to call AgentCore)
- `ec2:Describe*`, `s3:Get*`, `iam:Get*`, etc. (SecurityAudit policy recommended)
- `dynamodb:PutItem`, `dynamodb:GetItem` (for storing results)
- `s3:PutObject`, `s3:GetObject` (for evidence storage)

### Environment Variables

**Required:**
- `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`
- `CARL_AGENTCORE_ASK_ARN` - Ask agent ARN (from terraform output)
- `CARL_AGENTCORE_ARCHITECT_ARN` - Architect agent ARN (from terraform output)
- `CARL_AGENTCORE_REMEDIATE_ARN` - Remediate agent ARN (from terraform output)

**Optional:**
- `AWS_REGION` (default: us-east-1)
- `CARL_DYNAMODB_PREFIX` (default: carl-prod)
- `CARL_S3_EVIDENCE_BUCKET` (for evidence storage)
- `CARL_S3_REPORTS_BUCKET` (for reports)

### Customization

Edit `variables.tf` to customize:
- `environment` - Environment name (prod, dev, staging)
- `region` - AWS region
- `foundation_model` - Bedrock model (default: Sonnet 4.5)
- `tags` - Resource tags

### Multi-Environment Setup

Deploy to multiple environments:

```bash
# Production
terraform workspace new prod
terraform apply -var="environment=prod"

# Development
terraform workspace new dev
terraform apply -var="environment=dev"
```

## Troubleshooting

### "AgentCore not found"
- Verify AgentCore ARNs in your Claude Desktop config
- Ensure containers are pushed to ECR
- Check terraform apply completed successfully

### "Access Denied"
- Verify IAM permissions for bedrock:InvokeAgentRuntime
- Check AWS_PROFILE is set correctly
- Ensure AgentCore execution role has proper permissions

### "Container image not found"
- Build and push all three agent containers to ECR
- Verify ECR repository URL matches terraform output
- Check docker images were tagged correctly

### Logs
- **AgentCore logs:** CloudWatch Logs `/aws/bedrock-agentcore/runtimes/*`
- **MCP logs:** Check Claude Desktop logs
- **Terraform:** `terraform show` to see deployed resources

## Updating

### Update Agent Code
```bash
# Rebuild and push containers
cd agentcore-code
./build-and-push.sh $(terraform output -raw ecr_repository_url) prod

# AgentCore will automatically use new images on next invocation
```

### Update Infrastructure
```bash
cd carl-infrastructure/mcp-deployment
terraform apply
```

## Uninstalling

```bash
# Destroy all resources
terraform destroy

# This will delete:
# - AgentCore runtimes
# - DynamoDB tables (all data!)
# - S3 buckets (all evidence!)
# - ECR repository
```

**Warning:** This deletes all your CARL data. Export any reports first!

## Cost Breakdown

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| AgentCore (3 agents) | $30-50 | Pay per invocation + runtime |
| DynamoDB (on-demand) | $5-20 | Pay per request |
| S3 (evidence/reports) | $1-5 | Minimal storage |
| Bedrock (Sonnet 4.5) | $10-30 | Pay per token |
| CloudWatch Logs | $1-5 | Minimal logging |
| **Total** | **$50-110/month** | Varies with usage |

## Support

- **Issues:** https://github.com/gnegelow-caylent/CARL/issues
- **Docs:** https://github.com/gnegelow-caylent/CARL/tree/main/docs
- **Caylent:** Contact your Caylent representative
