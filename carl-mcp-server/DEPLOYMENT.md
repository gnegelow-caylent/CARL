# CARL MCP Server - Deployment Guide

Complete guide to deploy CARL as an MCP server for Claude Desktop.

## Overview

**What You're Deploying:**
- CARL infrastructure to your AWS account (AgentCore runtimes, DynamoDB, S3)
- MCP server on your local machine (Python package)
- Configuration for Claude Desktop

**Time Required:** 30-45 minutes
**Cost:** $50-110/month (your AWS account)

---

## Prerequisites

### 1. Software Requirements

**Required:**
- **AWS CLI** - [Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Terraform** (>= 1.9.0) - [Install Guide](https://developer.hashicorp.com/terraform/install)
- **Docker** - [Install Guide](https://docs.docker.com/get-docker/)
- **Python 3.11+** - [Install Guide](https://www.python.org/downloads/)
- **Claude Desktop** - [Download](https://claude.ai/download)

**Check versions:**
```bash
aws --version        # Should be 2.x
terraform --version  # Should be >= 1.9.0
docker --version     # Should be 20.x+
python3 --version    # Should be 3.11+
```

### 2. AWS Account Requirements

**IAM Permissions Needed:**
- Administrator access OR these specific permissions:
  - `bedrock:*` (AgentCore)
  - `ecr:*` (Container registry)
  - `dynamodb:*` (Tables)
  - `s3:*` (Buckets)
  - `iam:*` (Roles and policies)
  - `kms:*` (Encryption keys)
  - `secretsmanager:*` (Secrets)

**Configure AWS credentials:**
```bash
aws configure --profile carl-prod
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Region: us-east-1 (or your preferred region)
# Output format: json
```

**Verify credentials:**
```bash
aws sts get-caller-identity --profile carl-prod
# Should show your Account ID, UserId, and ARN
```

---

## Deployment Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/gnegelow-caylent/CARL.git
cd CARL

# Switch to MCP migration branch
git checkout feature/mcp-migration
```

### Step 2: Deploy AWS Infrastructure

This creates AgentCore runtimes, DynamoDB tables, S3 buckets, and IAM roles.

```bash
cd carl-infrastructure/mcp-deployment

# Initialize Terraform
terraform init

# Review what will be created
terraform plan \
  -var="environment=prod" \
  -var="region=us-east-1"

# Deploy infrastructure
terraform apply \
  -var="environment=prod" \
  -var="region=us-east-1"

# Type 'yes' when prompted
```

**What gets created:**
- 3 AgentCore runtimes (ask, architect, remediate)
- ECR repository for container images
- DynamoDB tables (findings, evidence, scan history)
- S3 buckets (evidence, reports)
- KMS encryption key
- IAM roles with proper permissions

**Expected output:**
```
Apply complete! Resources: 25 added, 0 changed, 0 destroyed.

Outputs:
ecr_repository_url = "123456789012.dkr.ecr.us-east-1.amazonaws.com/carl-prod-agents"
mcp_configuration = {
  "ask_agent_arn" = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/carl_prod_ask_agent"
  "architect_agent_arn" = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/carl_prod_architect_agent"
  "remediate_agent_arn" = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/carl_prod_remediate_agent"
}
```

**💾 Save the ARNs - you'll need them for Claude Desktop configuration!**

### Step 3: Build and Push Container Images

This builds Docker images for the 3 AgentCore agents and pushes them to ECR.

```bash
# Get ECR repository URL from terraform
ECR_REPO=$(terraform output -raw ecr_repository_url)
echo "ECR Repository: $ECR_REPO"

# Login to ECR
aws ecr get-login-password --region us-east-1 --profile carl-prod | \
  docker login --username AWS --password-stdin $ECR_REPO

# Navigate to agent code
cd ../agentcore-code

# Build and push Ask Agent
echo "Building Ask Agent..."
docker buildx build --platform linux/arm64 \
  --provenance=false \
  -t $ECR_REPO:agentcore-ask-prod \
  -f ask-agent/Dockerfile \
  --push .

# Build and push Architect Agent
echo "Building Architect Agent..."
docker buildx build --platform linux/arm64 \
  --provenance=false \
  -t $ECR_REPO:agentcore-architect-prod \
  -f architect-agent/Dockerfile \
  --push .

# Build and push Remediate Agent
echo "Building Remediate Agent..."
docker buildx build --platform linux/arm64 \
  --provenance=false \
  -t $ECR_REPO:agentcore-remediate-prod \
  -f remediate-agent/Dockerfile \
  --push .

echo "✅ All agents built and pushed successfully!"
```

**Expected time:** 10-15 minutes (depending on internet speed)

**Troubleshooting:**
- If `docker buildx` fails: Install buildx plugin or use regular `docker build` (remove `--platform` flag)
- If ECR login fails: Check AWS credentials and region
- If push fails: Verify ECR repository exists in AWS console

### Step 4: Install MCP Server

Install the CARL MCP server Python package on your local machine.

```bash
cd ../../carl-mcp-server

# Install in development mode (editable)
pip3 install -e .

# Verify installation
python3 -m carl_mcp_server --help
```

**Expected output:**
```
CARL MCP Server
AWS Security & Compliance assistant for Claude Desktop

Usage: python -m carl_mcp_server
```

### Step 5: Configure Claude Desktop

Configure Claude Desktop to use the CARL MCP server.

**1. Get your configuration values:**

```bash
cd ../carl-infrastructure/mcp-deployment

# Get AgentCore ARNs
terraform output -json mcp_configuration | jq .
```

**2. Open Claude Desktop config file:**

**macOS:**
```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
notepad %APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

**3. Add CARL configuration:**

If the file doesn't exist or is empty, create this:

```json
{
  "mcpServers": {
    "carl": {
      "command": "python3",
      "args": ["-m", "carl_mcp_server"],
      "env": {
        "AWS_PROFILE": "carl-prod",
        "AWS_REGION": "us-east-1",
        "CARL_AGENTCORE_ASK_ARN": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/carl_prod_ask_agent",
        "CARL_AGENTCORE_ARCHITECT_ARN": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/carl_prod_architect_agent",
        "CARL_AGENTCORE_REMEDIATE_ARN": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/carl_prod_remediate_agent",
        "CARL_DYNAMODB_PREFIX": "carl-prod",
        "CARL_S3_EVIDENCE_BUCKET": "carl-prod-evidence-ACCOUNT",
        "CARL_S3_REPORTS_BUCKET": "carl-prod-reports-ACCOUNT"
      }
    }
  }
}
```

If the file already has `mcpServers`, add the `carl` section inside it:

```json
{
  "mcpServers": {
    "existing-server": { ... },
    "carl": { ... }
  }
}
```

**4. Replace placeholder values:**

- Replace `ACCOUNT` with your AWS account ID
- Replace ARNs with actual values from `terraform output`
- Replace bucket names with actual values from `terraform output`

**5. Get bucket names:**

```bash
terraform output -json foundation_buckets | jq .
```

**6. Save the file**

### Step 6: Restart Claude Desktop

**Quit Claude Desktop completely:**
- macOS: `Cmd+Q` or Claude menu → Quit
- Windows: Right-click taskbar icon → Quit
- Linux: File → Quit

**Reopen Claude Desktop**

---

## Verification & Testing

### Test 1: Check MCP Server Connection

Open Claude Desktop and look for the 🔌 icon in the bottom-right corner. Click it to see connected MCP servers.

**Expected:** CARL should be listed with 6 tools available.

### Test 2: Ask CARL a Question

In Claude Desktop, type:

```
Use carl_ask to check my AWS security posture
```

**Expected output:**
```
🔍 Scanning AWS Environment...

Analyzing IAM, S3, VPC, Security Hub, CloudTrail...

Security Findings:
- ⚠️ 3 S3 buckets without encryption
- ⚠️ 2 IAM users without MFA
- ✅ CloudTrail logging enabled
- ✅ VPC Flow Logs configured

Recommendations:
1. Enable S3 encryption on all buckets
2. Enable MFA for IAM users
...
```

### Test 3: Architecture Recommendations

```
Use carl_architect to design a secure VPC for a web application
```

**Expected:** Detailed architecture recommendation with AWS services, cost estimates, and compliance considerations.

### Test 4: Scan AWS Environment

```
Use carl_scan_environment with scope "s3"
```

**Expected:** List of S3 buckets with security findings (encryption, versioning, public access).

### Test 5: Collect Evidence

```
Use carl_collect_evidence with framework "soc2"
```

**Expected:** Evidence collection summary with compliance status and DynamoDB storage confirmation.

---

## Troubleshooting

### Issue: "CARL_AGENTCORE_ASK_ARN not configured"

**Cause:** Claude Desktop config is missing or incorrect.

**Fix:**
1. Open `claude_desktop_config.json`
2. Verify ARNs are correct (no extra quotes, spaces, or line breaks)
3. Save file
4. Restart Claude Desktop completely

### Issue: "AgentCore Runtime Not Found"

**Cause:** Infrastructure not deployed or incorrect ARN.

**Fix:**
```bash
# Verify AgentCore runtimes exist
cd carl-infrastructure/mcp-deployment
terraform output mcp_configuration

# If empty, redeploy infrastructure
terraform apply -var="environment=prod" -var="region=us-east-1"
```

### Issue: "Access Denied" when calling AgentCore

**Cause:** AWS credentials don't have `bedrock:InvokeAgentRuntime` permission.

**Fix:**
```bash
# Verify credentials
aws sts get-caller-identity --profile carl-prod

# Add IAM policy to your user/role:
# - bedrock:InvokeAgentRuntime
# - Resource: arn:aws:bedrock-agentcore:*:*:runtime/carl_*
```

### Issue: Container images not found

**Cause:** Docker images not pushed to ECR.

**Fix:**
```bash
# Re-push containers
cd carl-infrastructure/mcp-deployment
ECR_REPO=$(terraform output -raw ecr_repository_url)

# Login and rebuild
aws ecr get-login-password --region us-east-1 --profile carl-prod | \
  docker login --username AWS --password-stdin $ECR_REPO

cd ../agentcore-code
docker buildx build --platform linux/arm64 --provenance=false \
  -t $ECR_REPO:agentcore-ask-prod -f ask-agent/Dockerfile --push .
```

### Issue: "Module not found: mcp"

**Cause:** MCP server not installed or wrong Python version.

**Fix:**
```bash
# Reinstall MCP server
cd carl-mcp-server
pip3 install -e .

# Verify Python version (must be 3.11+)
python3 --version

# If using pyenv or virtualenv, ensure Claude Desktop uses the right Python
which python3
```

### Issue: Claude Desktop doesn't show CARL tools

**Cause:** MCP server failed to start.

**Fix:**
1. Check Claude Desktop logs:
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Windows: `%APPDATA%\Claude\logs\mcp*.log`
   - Linux: `~/.config/Claude/logs/mcp*.log`

2. Look for error messages about CARL

3. Test MCP server manually:
   ```bash
   AWS_PROFILE=carl-prod \
   AWS_REGION=us-east-1 \
   CARL_AGENTCORE_ASK_ARN="arn:aws:..." \
   CARL_AGENTCORE_ARCHITECT_ARN="arn:aws:..." \
   CARL_AGENTCORE_REMEDIATE_ARN="arn:aws:..." \
   python3 -m carl_mcp_server
   ```

4. If you see errors, fix them and restart Claude Desktop

---

## One-Command Installation (Alternative)

For automated deployment, use the install script:

```bash
cd CARL
./install-carl-mcp.sh --profile carl-prod --region us-east-1 --environment prod
```

This script automates all steps above:
- Deploys Terraform infrastructure
- Builds and pushes containers
- Installs MCP server
- Generates Claude Desktop config

**Note:** You'll still need to manually copy the config to Claude Desktop and restart.

---

## Updating CARL

### Update Code

```bash
cd CARL
git pull origin feature/mcp-migration
```

### Update Infrastructure

```bash
cd carl-infrastructure/mcp-deployment
terraform apply -var="environment=prod" -var="region=us-east-1"
```

### Update Containers

```bash
cd ../agentcore-code
ECR_REPO=$(terraform output -raw ecr_repository_url -chdir=../mcp-deployment)

# Rebuild and push (example for ask agent)
docker buildx build --platform linux/arm64 --provenance=false \
  -t $ECR_REPO:agentcore-ask-prod -f ask-agent/Dockerfile --push .
```

### Update MCP Server

```bash
cd ../../carl-mcp-server
pip3 install -e . --upgrade
```

### Restart Claude Desktop

Quit and reopen Claude Desktop to reload the MCP server.

---

## Uninstalling CARL

### Step 1: Remove Claude Desktop Configuration

Edit `claude_desktop_config.json` and remove the `"carl"` section from `mcpServers`.

Restart Claude Desktop.

### Step 2: Uninstall MCP Server

```bash
pip3 uninstall carl-mcp-server
```

### Step 3: Destroy AWS Infrastructure

⚠️ **WARNING:** This will delete all CARL data (findings, evidence, reports).

```bash
cd carl-infrastructure/mcp-deployment

# Review what will be destroyed
terraform plan -destroy -var="environment=prod" -var="region=us-east-1"

# Destroy infrastructure
terraform destroy -var="environment=prod" -var="region=us-east-1"

# Type 'yes' when prompted
```

**Cost:** Deleting resources stops all charges immediately.

---

## Cost Management

### Monthly Cost Breakdown

| Service | Estimated Cost | Usage |
|---------|----------------|-------|
| AgentCore (3 runtimes) | $30-50 | Pay per invocation |
| DynamoDB (on-demand) | $5-20 | Pay per request |
| S3 (evidence/reports) | $1-5 | Minimal storage |
| Bedrock API (Sonnet 4.5) | $10-30 | Pay per token |
| CloudWatch Logs | $1-5 | Minimal logging |
| ECR | $1-2 | Container storage |
| **Total** | **$50-110/month** | Varies with usage |

### Cost Optimization Tips

1. **Use scoped scans** instead of "all" to reduce API calls
2. **Collect evidence weekly** instead of daily
3. **Delete old reports** from S3 after audits complete
4. **Set CloudWatch log retention** to 7 days instead of forever
5. **Monitor with AWS Cost Explorer** to track spending

### Set Cost Alerts

```bash
# Create budget alert
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget file://budget.json
```

**budget.json:**
```json
{
  "BudgetName": "CARL-Monthly-Budget",
  "BudgetType": "COST",
  "TimeUnit": "MONTHLY",
  "BudgetLimit": {
    "Amount": "100",
    "Unit": "USD"
  }
}
```

---

## Support

### Documentation
- [README.md](./README.md) - Feature overview
- [MCP_MIGRATION_PLAN.md](../MCP_MIGRATION_PLAN.md) - Architecture details
- [CARL Design Principles](../CARL_DESIGN_PRINCIPLES.md) - Design philosophy

### Issues
Report bugs or request features: https://github.com/gnegelow-caylent/CARL/issues

### Caylent Support
Contact your Caylent representative for enterprise support.

---

## Next Steps

Once CARL is deployed:

1. **Explore Tools:**
   - Try `carl_scan_environment` with different scopes
   - Test `carl_collect_evidence` for your compliance framework
   - Generate reports with `carl_generate_report`

2. **Integrate with Workflow:**
   - Schedule weekly evidence collection
   - Set up monthly compliance reports
   - Use CARL for architecture reviews

3. **Monitor Usage:**
   - Check AWS Cost Explorer weekly
   - Review CloudWatch logs for errors
   - Track compliance posture improvements

4. **Phase 3 (Coming Soon):**
   - EVO integration for Caylent customers
   - Multi-customer deployment automation
   - Centralized monitoring

---

## FAQ

**Q: Can I deploy to a different region?**
A: Yes, change `--region` in all commands. Ensure Bedrock is available in that region.

**Q: Can multiple people use the same CARL deployment?**
A: Yes, they all need AWS credentials for the same account and the same Claude Desktop config.

**Q: Does CARL modify my AWS resources?**
A: Only with explicit approval via `carl_remediate_finding`. Scanning and evidence collection are read-only.

**Q: Can I use CARL with multiple AWS accounts?**
A: Deploy CARL once per account. In Claude Desktop, use different MCP server names (`carl-prod`, `carl-dev`).

**Q: How do I upgrade to newer versions?**
A: `git pull`, `terraform apply`, rebuild containers, restart Claude Desktop.

**Q: Is my data secure?**
A: Yes. All data stays in your AWS account. Evidence and findings are encrypted at rest (KMS).

---

## License

MIT License - see [LICENSE](../LICENSE) file for details.

---

**Deployment complete!** 🎉

You now have CARL running as an MCP server in Claude Desktop with full access to your AWS environment for security scanning, compliance evidence collection, and architecture recommendations.
