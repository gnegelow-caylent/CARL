# CARL MCP Quick Start

Get CARL running in Claude Desktop in 5 minutes using your existing infrastructure.

## Prerequisites

✅ You already have:
- CARL infrastructure deployed (from Slack version)
- AgentCore runtimes running
- AWS credentials configured

## Setup Steps

### Option 1: Automated Setup (Recommended)

Run the setup script:

```bash
cd /Users/gnegelow/Documents/CARL
./setup-mcp.sh
```

The script will:
1. ✅ Verify your AWS credentials
2. ✅ Get AgentCore ARNs from your deployment
3. ✅ Install the MCP server
4. ✅ Configure Claude Desktop automatically

### Option 2: Manual Setup

If you prefer to do it manually:

#### Step 1: Configure AWS Profile

Make sure your AWS credentials are working:

```bash
aws sts get-caller-identity --profile carl-dev
# Should show your account ID
```

#### Step 2: Get AgentCore ARNs

```bash
cd carl-infrastructure/core
terraform output agentcore_ask_runtime_arn
terraform output agentcore_architect_runtime_arn
terraform output agentcore_remediate_runtime_arn
```

**Save these ARNs!**

#### Step 3: Install MCP Server

**Important:** Due to macOS Python restrictions, use one of these methods:

**Method A - Using pipx (Recommended):**
```bash
# Install pipx if you don't have it
brew install pipx

# Install CARL MCP server
cd carl-mcp-server
pipx install -e .
```

**Method B - Using virtual environment:**
```bash
cd carl-mcp-server

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install
pip install -e .

# Note: You'll need to use the venv Python path in Claude config
which python  # Copy this path
```

**Method C - Break system packages (not recommended):**
```bash
cd carl-mcp-server
pip3 install --break-system-packages -e .
```

#### Step 4: Configure Claude Desktop

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "carl": {
      "command": "python3",
      "args": ["-m", "carl_mcp_server"],
      "env": {
        "AWS_PROFILE": "carl-dev",
        "AWS_REGION": "us-east-1",
        "CARL_AGENTCORE_ASK_ARN": "YOUR_ASK_ARN_HERE",
        "CARL_AGENTCORE_ARCHITECT_ARN": "YOUR_ARCHITECT_ARN_HERE",
        "CARL_AGENTCORE_REMEDIATE_ARN": "YOUR_REMEDIATE_ARN_HERE",
        "CARL_DYNAMODB_PREFIX": "carl-dev",
        "CARL_S3_EVIDENCE_BUCKET": "carl-dev-evidence-ACCOUNTID",
        "CARL_S3_REPORTS_BUCKET": "carl-dev-reports-ACCOUNTID"
      }
    }
  }
}
```

**If using venv, change `command` to your venv python path:**
```json
"command": "/Users/gnegelow/Documents/CARL/carl-mcp-server/venv/bin/python"
```

Get bucket names:
```bash
cd carl-infrastructure/core
terraform output foundation_evidence_bucket
terraform output foundation_reports_bucket
```

#### Step 5: Restart Claude Desktop

**Completely quit Claude Desktop:**
- Press `Cmd+Q` or
- Claude menu → Quit

**Reopen Claude Desktop**

## Testing

### Test 1: Check Connection

Look for the 🔌 icon in Claude Desktop's bottom-right corner. Click it - you should see "carl" with 6 tools.

### Test 2: Ask a Question

```
Use carl_ask to check my AWS security posture
```

Expected: CARL scans your AWS account and reports findings.

### Test 3: Scan Environment

```
Use carl_scan_environment with scope "s3"
```

Expected: List of S3 buckets with security findings.

### Test 4: Architecture Advice

```
Use carl_architect to design a secure VPC for a web application
```

Expected: Detailed architecture recommendation with costs.

## Troubleshooting

### "CARL_AGENTCORE_ASK_ARN not configured"

**Fix:** Check Claude Desktop config file has correct ARNs with no extra spaces/quotes.

### "AgentCore Runtime Not Found"

**Fix:** Verify ARN is correct:
```bash
aws bedrock-agentcore list-runtimes --region us-east-1 --profile carl-dev
```

### "Access Denied"

**Fix:** Check AWS credentials and IAM permissions:
```bash
# Verify credentials work
aws sts get-caller-identity --profile carl-dev

# Your IAM user/role needs:
# - bedrock:InvokeAgentRuntime
# - Access to AgentCore runtimes
```

### "Module not found: carl_mcp_server"

**Fix:** Reinstall MCP server or check Python path in Claude config.

### MCP Server Not Starting

**Check logs:**
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Look for errors about CARL
```

## Available Tools

Once working, you have access to:

| Tool | Description |
|------|-------------|
| `carl_ask` | Intelligent Q&A about your AWS environment |
| `carl_architect` | Architecture recommendations with costs |
| `carl_scan_environment` | Direct security scanning (IAM, S3, VPC, etc.) |
| `carl_remediate_finding` | Fix security issues with AI |
| `carl_collect_evidence` | Collect compliance evidence |
| `carl_generate_report` | Generate compliance reports |

## Example Prompts

```
Use carl_ask to:
- "What are my biggest security risks?"
- "How is my MFA configured?"
- "Show me unencrypted S3 buckets"

Use carl_architect to:
- "Design a serverless API architecture"
- "Recommend a secure web application setup"
- "How should I deploy a database?"

Use carl_scan_environment to:
- scope: "all" - Full security scan
- scope: "iam" - IAM-only scan
- scope: "s3" - S3 buckets scan

Use carl_collect_evidence to:
- framework: "soc2" - SOC 2 evidence
- framework: "hipaa" - HIPAA evidence

Use carl_generate_report to:
- report_type: "executive" - Executive summary
- report_type: "full" - Detailed report
```

## Support

- **Documentation:** [DEPLOYMENT.md](carl-mcp-server/DEPLOYMENT.md)
- **Issues:** https://github.com/gnegelow-caylent/CARL/issues
- **Branch:** `feature/mcp-migration`

---

**Ready to test!** 🚀

Run `./setup-mcp.sh` or follow the manual steps above.
