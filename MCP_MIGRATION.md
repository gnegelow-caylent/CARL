# CARL MCP Migration Guide

This guide explains the architectural differences between CARL's Slack version and MCP version, and how to migrate.

## Architecture Comparison

### Slack Version (Centralized)

```
┌─────────────────────────────────────────────┐
│         Caylent's AWS Account               │
│                                             │
│  ┌──────────────┐         ┌──────────────┐ │
│  │ Slack Bot    │────────▶│ Lambda       │ │
│  │ (Workspace)  │         │ Router       │ │
│  └──────────────┘         └──────┬───────┘ │
│                                  │         │
│                           ┌──────▼───────┐ │
│                           │ AgentCore    │ │
│                           │ - Ask        │ │
│                           │ - Architect  │ │
│                           │ - Remediate  │ │
│                           └──────────────┘ │
│                                             │
│  Deployment: Terraform + GitHub Actions    │
│  Scans: Customer AWS via IAM role          │
└─────────────────────────────────────────────┘
```

**Characteristics:**
- ✅ Single deployment (Caylent's account)
- ✅ GitHub Actions CI/CD deploys infrastructure
- ✅ Slack interface for all users
- ✅ Cross-account scanning via IAM roles
- ❌ Requires Slack workspace access
- ❌ Single point of failure
- ❌ All customers share same infrastructure

---

### MCP Version (Distributed)

```
┌─────────────────────────────────────────────┐
│         Customer's AWS Account              │
│                                             │
│                           ┌──────────────┐  │
│  ┌──────────────┐         │ AgentCore    │  │
│  │ Claude       │────────▶│ - Ask        │  │
│  │ Desktop      │  (MCP)  │ - Architect  │  │
│  │ (Local)      │         │ - Remediate  │  │
│  └──────────────┘         └──────────────┘  │
│                                             │
│  Deployment: Customer runs terraform apply │
│  Scans: Local AWS account                  │
└─────────────────────────────────────────────┘
```

**Characteristics:**
- ✅ Self-deployed (customer's account)
- ✅ No Slack required
- ✅ Direct AWS access (no cross-account roles)
- ✅ Isolated per customer
- ✅ Works with Claude Desktop (AI interface)
- ❌ Customer must deploy infrastructure
- ❌ No centralized CI/CD deployment

---

## Key Differences

| Aspect | Slack Version | MCP Version |
|--------|---------------|-------------|
| **Deployment** | Caylent deploys once | Each customer deploys |
| **Interface** | Slack commands | Claude Desktop tools |
| **Infrastructure** | Centralized (Caylent AWS) | Distributed (customer AWS) |
| **GitHub Actions** | Builds + deploys to Caylent AWS | Validates code only (no deploy) |
| **AWS Access** | Cross-account IAM roles | Direct (same account) |
| **AgentCore** | Shared infrastructure | Same code, isolated instances |
| **IAM Setup** | Complex (cross-account) | Simple (same-account) |
| **Cost** | Caylent pays | Customer pays |
| **Isolation** | Shared | Complete |
| **Updates** | Caylent pushes updates | Customer pulls updates |

---

## Migration Steps

### For Existing CARL Users

If you already have CARL deployed via Slack:

**Good News:** You can use both simultaneously!

1. **Keep Slack version running** - No changes needed
2. **Deploy MCP version** - Follow QUICKSTART.md
3. **Use same AgentCore infrastructure** - MCP reuses existing runtimes
4. **Choose interface** - Use Slack OR Claude Desktop (or both!)

**Example: Same infrastructure, two interfaces**

```bash
# Slack version
/carl ask What's my security posture?

# MCP version (in Claude Desktop)
Use carl_ask to check my AWS security posture
```

Both use the **same AgentCore runtimes** - no duplication!

---

### For New Users

If you're deploying CARL for the first time:

**Recommended: MCP Version**

Why MCP is better for new deployments:
- ✅ Simpler IAM (no cross-account roles)
- ✅ Isolated infrastructure
- ✅ Better AI interface (Claude Desktop)
- ✅ Faster responses (no Slack API latency)

**Deploy MCP:**
1. Follow [QUICKSTART.md](./QUICKSTART.md) for existing infrastructure
2. OR follow [carl-mcp-server/DEPLOYMENT.md](./carl-mcp-server/DEPLOYMENT.md) for new deployment

---

## Technical Implementation Differences

### 1. Infrastructure Deployment

**Slack Version:**
```yaml
# .github/workflows/deploy.yml
- name: Deploy to AWS
  run: terraform apply -auto-approve
  # Deploys to Caylent's AWS account
```

**MCP Version:**
```yaml
# .github/workflows/deploy-mcp.yml
- name: Validate Terraform
  run: terraform validate
  # Only validates, doesn't deploy
  # Customer runs terraform apply manually
```

**Why the difference?**
- Slack: One deployment serves all customers → CI/CD can deploy
- MCP: Each customer deploys independently → No centralized deployment

---

### 2. AgentCore Infrastructure

**Slack Version:**
```hcl
# carl-infrastructure/modules/agentcore-ask/main.tf
resource "aws_agentcore_runtime" "ask" {
  name = "carl_prod_ask_agent"
  # Deployed in Caylent's account
  # Scans customer accounts via IAM roles
}
```

**MCP Version:**
```hcl
# carl-infrastructure/mcp-deployment/main.tf
resource "aws_agentcore_runtime" "ask" {
  name = "carl_${var.environment}_ask_agent"
  # Deployed in CUSTOMER's account
  # Scans same account (no cross-account roles)
}
```

**Why the difference?**
- Slack: Cross-account scanning requires complex IAM setup
- MCP: Same-account scanning is simpler and more secure

---

### 3. Tool Interface

**Slack Version:**
```python
# slack_router.py
@slack_app.command("/carl ask")
def handle_ask_command(ack, command):
    ack()  # Acknowledge Slack
    question = command['text']
    result = agentcore_client.invoke_ask(question)
    slack_client.post_message(result)
```

**MCP Version:**
```python
# carl-mcp-server/tools/ask.py
tool = {
    "name": "carl_ask",
    "description": "Intelligent Q&A about AWS environment",
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {"type": "string"}
        }
    }
}

def handle(question: str) -> str:
    result = agentcore_client.invoke_ask(question)
    return result
```

**Why the difference?**
- Slack: Command-based interface with Slack-specific code
- MCP: Tool-based interface following MCP protocol spec

---

### 4. Configuration

**Slack Version:**
```bash
# Environment variables (Lambda)
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_SIGNING_SECRET=...
export CARL_AGENTCORE_ASK_ARN=arn:aws:bedrock-agentcore:...:carl_prod_ask_agent
```

**MCP Version:**
```json
// Claude Desktop config
{
  "mcpServers": {
    "carl": {
      "command": "python3",
      "args": ["-m", "carl_mcp_server"],
      "env": {
        "AWS_PROFILE": "carl-dev",
        "CARL_AGENTCORE_ASK_ARN": "arn:aws:bedrock-agentcore:...:carl_dev_ask_agent"
      }
    }
  }
}
```

**Why the difference?**
- Slack: Server-side configuration (Lambda env vars)
- MCP: Client-side configuration (Claude Desktop config file)

---

## When to Use Which Version

### Use Slack Version When:
- ✅ You want centralized management (Caylent deploys)
- ✅ Multiple users need shared access
- ✅ Slack is your primary collaboration tool
- ✅ You don't want to manage AWS infrastructure
- ✅ You're okay with cross-account IAM roles

### Use MCP Version When:
- ✅ You want isolated infrastructure per customer
- ✅ You prefer Claude Desktop interface
- ✅ You want direct AWS access (no cross-account)
- ✅ You're okay deploying your own infrastructure
- ✅ You want faster responses (no Slack API)
- ✅ You're deploying CARL for the first time

### Use Both When:
- ✅ Different team members prefer different interfaces
- ✅ You want to test MCP without removing Slack
- ✅ Transitioning from Slack to MCP gradually

---

## Cost Implications

### Slack Version Costs (Caylent Pays)
- AgentCore: $30-50/month (shared across customers)
- DynamoDB: $5-20/month (shared)
- Lambda: $0-5/month (free tier)
- Slack: Free (using existing workspace)

**Total: ~$40-75/month** (amortized across customers)

### MCP Version Costs (Customer Pays)
- AgentCore: $30-50/month (dedicated)
- DynamoDB: $5-20/month (dedicated)
- S3: $1-5/month (evidence/reports)
- Bedrock: $10-30/month (Claude API)

**Total: ~$50-110/month** (per customer)

**Trade-off:** Higher cost per customer, but complete isolation and no Slack dependency.

---

## Migration Checklist

### Keeping Slack, Adding MCP
- [ ] Deploy MCP infrastructure (QUICKSTART.md)
- [ ] Configure Claude Desktop (claude_desktop_config.json)
- [ ] Test MCP tools work
- [ ] Document which interface to use when
- [ ] Keep Slack version running

### Migrating from Slack to MCP
- [ ] Deploy MCP infrastructure
- [ ] Configure Claude Desktop
- [ ] Test all 6 tools work in MCP
- [ ] Train team on Claude Desktop interface
- [ ] Run parallel for 1-2 weeks
- [ ] Sunset Slack version (terraform destroy Slack infra)
- [ ] Remove Slack bot from workspace

---

## Troubleshooting Migration Issues

### "AgentCore Runtime Not Found"

**Slack version uses:**
```
arn:aws:bedrock-agentcore:us-east-1:CAYLENT_ACCOUNT:runtime/carl_prod_ask_agent
```

**MCP version uses:**
```
arn:aws:bedrock-agentcore:us-east-1:CUSTOMER_ACCOUNT:runtime/carl_dev_ask_agent
```

**Fix:** Deploy AgentCore infrastructure in customer account:
```bash
cd carl-infrastructure/mcp-deployment
terraform apply
```

---

### "Access Denied" Errors

**Slack version:** Requires cross-account IAM role with trust policy

**MCP version:** Requires same-account IAM permissions

**Fix:** Check AWS_PROFILE in Claude Desktop config matches account with CARL infrastructure.

---

### "MCP Server Not Starting"

**Check logs:**
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Look for environment variable errors
```

**Fix:** Ensure Claude Desktop config has all required env vars:
- AWS_PROFILE or AWS_ACCESS_KEY_ID/SECRET
- CARL_AGENTCORE_ASK_ARN
- CARL_AGENTCORE_ARCHITECT_ARN
- CARL_AGENTCORE_REMEDIATE_ARN

---

## Rollback Plan

If MCP version has issues, you can roll back:

1. **Stop Claude Desktop** (Cmd+Q)
2. **Remove MCP config:**
   ```bash
   # Backup config
   mv ~/Library/Application\ Support/Claude/claude_desktop_config.json ~/.claude_backup.json

   # Or just remove CARL section
   jq 'del(.mcpServers.carl)' ~/.claude_backup.json > ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```
3. **Continue using Slack version** - Still works!
4. **Debug MCP issues** - Check VALIDATION.md for testing locally

---

## Future Direction

**Recommended path:**
1. New customers: Deploy MCP version only
2. Existing customers: Run both, migrate to MCP gradually
3. Long-term: Phase out Slack version (MCP is the future)

**Why MCP is the future:**
- Better AI integration (Claude Desktop native)
- Simpler architecture (no cross-account IAM)
- Better isolation (per-customer infrastructure)
- Faster development (no Slack API complexity)

---

## Questions?

- **Documentation:** [QUICKSTART.md](./QUICKSTART.md) | [DEPLOYMENT.md](./carl-mcp-server/DEPLOYMENT.md)
- **Validation:** [.github/VALIDATION.md](./.github/VALIDATION.md)
- **Issues:** https://github.com/gnegelow-caylent/CARL/issues

---

**Ready to migrate?** Start with [QUICKSTART.md](./QUICKSTART.md)
