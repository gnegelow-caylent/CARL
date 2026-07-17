# CARL MCP Server

AWS Security & Compliance assistant for Claude Desktop via Model Context Protocol.

## What is CARL?

**CARL (Cloud Automated Risk & Compliance Logic)** is an AI-powered AWS security assistant that:
- 🔍 Scans your AWS environment intelligently
- 🛡️ Identifies security risks and compliance gaps
- 🏗️ Recommends architecture with cost estimates
- ✅ Maps everything to SOC 2, HIPAA, PCI DSS controls
- 🔧 Can auto-fix issues with your approval

## 🚀 Quick Start

**→ [Complete Deployment Guide](./DEPLOYMENT.md)** ← Start here for step-by-step instructions

Deployment takes ~30-45 minutes and includes:
1. Deploy AWS infrastructure (Terraform)
2. Build and push containers (Docker)
3. Install MCP server (Python)
4. Configure Claude Desktop

## Prerequisites

1. **AWS Account** with CARL infrastructure deployed
2. **Claude Desktop** installed
3. **Python 3.11+**
4. **AWS CLI** configured

## Installation

### 1. Deploy CARL Infrastructure

First, deploy CARL to your AWS account:

```bash
git clone https://github.com/gnegelow-caylent/CARL.git
cd CARL/carl-infrastructure/mcp-deployment
terraform init
terraform apply
```

**Save the outputs!** You'll need the AgentCore ARNs.

### 2. Install MCP Server

```bash
pip install carl-mcp-server
```

Or install from source:
```bash
cd CARL/carl-mcp-server
pip install -e .
```

### 3. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "carl": {
      "command": "python",
      "args": ["-m", "carl_mcp_server"],
      "env": {
        "AWS_PROFILE": "your-aws-profile",
        "AWS_REGION": "us-east-1",
        "CARL_AGENTCORE_ASK_ARN": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/carl_prod_ask_agent",
        "CARL_AGENTCORE_ARCHITECT_ARN": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/carl_prod_architect_agent",
        "CARL_AGENTCORE_REMEDIATE_ARN": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/carl_prod_remediate_agent"
      }
    }
  }
}
```

Get your ARNs from terraform:
```bash
cd carl-infrastructure/mcp-deployment
terraform output claude_desktop_config
```

### 4. Restart Claude Desktop

### 5. Test

Ask Claude:
```
Use carl_ask to check my AWS security posture
```

## Available Tools

### `carl_ask`

Intelligent Q&A about your AWS environment.

**Examples:**
```
Use carl_ask to:
- "What are my biggest security risks?"
- "How is my MFA configured?"
- "Which S3 buckets lack encryption?"
- "Show me my VPC security group rules"
- "Am I compliant with SOC 2 CC6.1?"
```

### `carl_architect`

Get architecture recommendations with costs and compliance implications.

**Examples:**
```
Use carl_architect to:
- "How should I deploy a secure web application?"
- "What's the best way to host static websites?"
- "Recommend a serverless API architecture"
- "Design a compliant data processing pipeline"
```

### `carl_scan_environment`

Scan AWS environment for security findings.

**Examples:**
```
Use carl_scan_environment to:
- Scan all AWS services for security issues
- scope: "all" - comprehensive scan
- scope: "iam" - IAM-specific scan
- scope: "s3" - S3 bucket security scan
- scope: "vpc" - VPC and network security
```

Returns findings with severity levels (CRITICAL, HIGH, MEDIUM, LOW) and recommendations.

### `carl_remediate_finding`

Auto-fix security issues with AI-generated solutions.

**Examples:**
```
Use carl_remediate_finding to:
- finding_id: "s3-bucket-my-bucket-no-encryption"
- auto_approve: false (requires approval for all changes)

CARL will:
1. Analyze the finding
2. Generate appropriate fix (Terraform or direct API)
3. Show preview with risk level
4. Apply fix after your approval
```

### `carl_collect_evidence`

Collect compliance evidence for audits.

**Examples:**
```
Use carl_collect_evidence to:
- framework: "soc2" - SOC 2 evidence
- framework: "hipaa" - HIPAA evidence
- framework: "all" - All frameworks
- store: true - Store in DynamoDB/S3

Collects evidence across IAM, S3, VPC, CloudTrail, Security Hub, KMS
Maps to compliance controls (CC6.1, HIPAA §164.312, etc.)
```

### `carl_generate_report`

Generate compliance reports for auditors.

**Examples:**
```
Use carl_generate_report to:
- report_type: "executive" - Executive summary
- report_type: "full" - Detailed compliance report
- report_type: "control", control_id: "CC6.1" - Specific control
- framework: "soc2"
- save_to_s3: true - Save to S3 bucket
```

## Configuration

### Environment Variables

**Required:**
- `CARL_AGENTCORE_ASK_ARN` - Ask agent runtime ARN
- `CARL_AGENTCORE_ARCHITECT_ARN` - Architect agent runtime ARN
- `CARL_AGENTCORE_REMEDIATE_ARN` - Remediate agent runtime ARN

**AWS Credentials (one of):**
- `AWS_PROFILE` - AWS profile name
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`

**Optional:**
- `AWS_REGION` - AWS region (default: us-east-1)
- `CARL_DYNAMODB_PREFIX` - DynamoDB table prefix (default: carl-prod)
- `CARL_S3_EVIDENCE_BUCKET` - Evidence storage bucket
- `CARL_S3_REPORTS_BUCKET` - Reports storage bucket

### IAM Permissions Required

Your AWS credentials need:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock:InvokeAgentRuntime",
      "Resource": "arn:aws:bedrock-agentcore:*:*:runtime/carl_*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "s3:Get*",
        "iam:Get*",
        "securityhub:GetFindings",
        "config:Describe*"
      ],
      "Resource": "*"
    }
  ]
}
```

Or attach `SecurityAudit` managed policy for full read access.

## Troubleshooting

### "CARL_AGENTCORE_ASK_ARN not configured"

- Check your Claude Desktop config file
- Ensure ARNs are copied correctly from terraform output
- Restart Claude Desktop after config changes

### "Access Denied" when calling AgentCore

- Verify AWS credentials: `aws sts get-caller-identity`
- Ensure IAM user/role has `bedrock:InvokeAgentRuntime` permission
- Check AgentCore runtime ARN is correct

### "AgentCore Runtime Not Found"

- Deploy CARL infrastructure first: `terraform apply`
- Verify containers are pushed to ECR
- Check terraform completed successfully

### Enable Debug Logging

Set environment variable in Claude Desktop config:
```json
{
  "env": {
    "CARL_LOG_LEVEL": "DEBUG"
  }
}
```

## Development

### Running Locally

```bash
# Install in development mode
cd carl-mcp-server
pip install -e .

# Run directly
python -m carl_mcp_server

# Or use entry point
carl-mcp
```

### Testing

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

## Cost

Running CARL costs approximately **$50-110/month**:
- AgentCore: $30-50/month (pay per invocation)
- DynamoDB: $5-20/month (pay per request)
- S3: $1-5/month (minimal storage)
- Bedrock: $10-30/month (pay per token)

Cost varies with usage. First month may be higher due to initial scans.

## Support

- **Issues:** https://github.com/gnegelow-caylent/CARL/issues
- **Docs:** https://github.com/gnegelow-caylent/CARL/tree/main/docs
- **Caylent:** Contact your Caylent representative

## License

MIT License - see LICENSE file for details.
