# CARL MCP Migration Plan

**Status:** In Progress (Branch: `feature/mcp-migration`)
**Goal:** Migrate CARL from Slack bot to MCP server for Claude Desktop/EVO integration

---

## 🎯 Overview

**Current:** CARL is a Slack bot (Lambda + API Gateway)
**Target:** CARL is an MCP server (local Python process) with self-deployed AgentCore

**Architecture Decision:** Each customer deploys their own CARL infrastructure to their AWS account for full data isolation and security.

---

## 🏗️ Target Architecture

```
Customer AWS Account
├─ AgentCore Runtimes (3 agents)
│  ├─ ask-agent (containerized)
│  ├─ architect-agent (containerized)
│  └─ remediate-agent (containerized)
│
├─ Infrastructure
│  ├─ ECR Repository
│  ├─ DynamoDB Tables
│  ├─ S3 Buckets
│  └─ IAM Roles
│
Customer Machine
└─ Claude Desktop
   └─ CARL MCP Server (local)
      └─ Calls customer's AgentCore via bedrock-agentcore API
```

---

## 📦 What's Been Built

### ✅ Infrastructure (Terraform)
- **`carl-infrastructure/mcp-deployment/`** - Simplified deployment for MCP
  - Creates AgentCore runtimes
  - Creates DynamoDB tables, S3 buckets
  - Creates IAM roles
  - Outputs configuration for Claude Desktop

### ✅ MCP Server (Python Package)
- **`carl-mcp-server/`** - Installable Python package
  - `carl_ask` tool - Intelligent Q&A
  - `carl_architect` tool - Architecture recommendations
  - Calls AgentCore agents via boto3
  - Stubs for scan/remediate/evidence (future)

### ✅ Installation
- **`install-carl-mcp.sh`** - One-command setup script
  - Deploys Terraform infrastructure
  - Builds and pushes containers
  - Installs MCP server
  - Configures Claude Desktop

### ✅ CI/CD
- **`.github/workflows/deploy-mcp.yml`** - Auto-builds containers on push

---

## 🚀 Deployment Flow for Customers

### Step 1: Deploy Infrastructure (15 min)

```bash
git clone https://github.com/gnegelow-caylent/CARL.git
cd CARL/carl-infrastructure/mcp-deployment
terraform init
terraform apply
```

**Creates:**
- 3 AgentCore runtimes
- ECR repository for containers
- DynamoDB tables (findings, evidence, scan history, etc.)
- S3 buckets (evidence, reports)
- IAM roles with proper permissions

**Cost:** ~$50-100/month

### Step 2: Build and Push Containers (10 min)

```bash
# Get ECR URL from terraform output
ECR_REPO=$(terraform output -raw ecr_repository_url)

# Build and push all agents
cd ../agentcore-code
./build-and-push.sh $ECR_REPO prod
```

### Step 3: Install MCP Server (2 min)

```bash
pip install carl-mcp-server
```

### Step 4: Configure Claude Desktop (2 min)

Copy terraform output to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "carl": {
      "command": "python",
      "args": ["-m", "carl_mcp_server"],
      "env": {
        "AWS_PROFILE": "customer-profile",
        "CARL_AGENTCORE_ASK_ARN": "arn:aws:bedrock-agentcore:...",
        "CARL_AGENTCORE_ARCHITECT_ARN": "arn:aws:bedrock-agentcore:...",
        "CARL_AGENTCORE_REMEDIATE_ARN": "arn:aws:bedrock-agentcore:..."
      }
    }
  }
}
```

### Step 5: Test (1 min)

Restart Claude Desktop and ask:
```
Use carl_ask to check my AWS security posture
```

**Total Time:** ~30 minutes
**OR use one-liner:** `./install-carl-mcp.sh --profile my-aws`

---

## 🛣️ Implementation Phases

### Phase 1: Core MCP Functionality ✅ (DONE)

**What's Working:**
- ✅ MCP server skeleton
- ✅ `carl_ask` tool (full functionality)
- ✅ `carl_architect` tool (full functionality)
- ✅ AgentCore integration
- ✅ Terraform deployment
- ✅ Installation script
- ✅ GitHub Actions

**Deliverable:** Can ask CARL questions and get architecture recommendations via Claude Desktop

### Phase 2: Additional Tools (Next - Week 1)

**To Build:**
- `carl_scan_environment` - Direct AWS scanning
- `carl_remediate_finding` - Fix security findings
- `carl_collect_evidence` - Compliance evidence collection
- `carl_generate_report` - Compliance reports

**Deliverable:** Full feature parity with Slack bot

### Phase 3: EVO Integration (Week 2)

**To Build:**
- Caylent SSO/auth integration
- Multi-customer deployment automation
- Centralized monitoring/logging
- Cost tracking per customer

**Deliverable:** Production-ready for Caylent EVO

### Phase 4: Migration & Deprecation (Week 3)

**Tasks:**
- User migration guide
- Update all documentation
- Slack bot deprecation timeline (6 months?)
- Keep Slack bot for legacy support

---

## 🔑 Key Decisions Made

1. **Self-Deployment:** Each customer deploys their own infrastructure
   - **Why:** Data isolation, security, compliance
   - **Trade-off:** More complex setup vs. shared infrastructure

2. **Reuse AgentCore:** Keep existing containerized agents
   - **Why:** Zero rewrite, proven functionality
   - **Trade-off:** Still requires AgentCore deployment

3. **Local MCP Server:** Thin wrapper, heavy lifting in AgentCore
   - **Why:** Simple, fast, leverages existing work
   - **Trade-off:** Requires AWS creds on local machine

4. **Terraform-Based:** Infrastructure as code
   - **Why:** Repeatable, auditable, version-controlled
   - **Trade-off:** Requires Terraform knowledge (mitigated by install script)

---

## 📊 Comparison: Slack vs MCP

| Feature | Slack Bot | MCP Server |
|---------|-----------|------------|
| **Interface** | Slack | Claude Desktop |
| **Deployment** | Caylent-hosted | Customer self-deployed |
| **Data Location** | Caylent AWS | Customer AWS |
| **Cost (Caylent)** | $200/month | $0 |
| **Cost (Customer)** | $0 | $50-100/month |
| **Setup Time** | 0 (invite bot) | 30 min (terraform) |
| **Isolation** | Shared | Fully isolated |
| **AgentCore** | Yes | Yes (reused) |
| **EVO Integration** | No | Yes (future) |

---

## 🧪 Testing Plan

### Unit Tests
- MCP tool definitions
- AgentCore client
- Error handling

### Integration Tests
- End-to-end tool execution
- AgentCore invocation
- AWS scanning

### User Acceptance Testing
1. Fresh AWS account
2. Run `install-carl-mcp.sh`
3. Verify all tools work
4. Test error scenarios

---

## 📝 Documentation Needed

- [x] Infrastructure deployment guide (`mcp-deployment/README.md`)
- [x] MCP server usage guide (`carl-mcp-server/README.md`)
- [x] Installation script
- [ ] Troubleshooting guide
- [ ] EVO integration guide (Phase 3)
- [ ] Migration guide for Slack users (Phase 4)

---

## 🚧 Known Limitations

1. **Tools in Progress:** scan, remediate, evidence are stubs (Phase 2)
2. **No Continuous Learning:** Feedback buttons won't work until we build MCP-compatible storage
3. **No Multi-Account:** Each deployment is single-account (can deploy multiple times)
4. **Local Only:** No remote MCP server option yet (EVO Phase 3)

---

## 💰 Cost Analysis

**Per Customer (Monthly):**
- AgentCore (3 runtimes): $30-50
- DynamoDB (on-demand): $5-20
- S3 (evidence/reports): $1-5
- Bedrock (Sonnet 4.5): $10-30
- CloudWatch Logs: $1-5
- **Total:** $50-110/month

**Scaling:**
- 10 customers: $500-1,100/month (customers pay)
- 100 customers: $5,000-11,000/month (customers pay)
- Caylent cost: $0 (vs. $200/month for Slack infrastructure)

---

## 🎯 Success Criteria

**Phase 1 Complete When:**
- [x] Customer can deploy infrastructure in < 30 min
- [x] `carl_ask` works in Claude Desktop
- [x] `carl_architect` works in Claude Desktop
- [x] Documentation is clear

**Phase 2 Complete When:**
- [ ] All core tools implemented (scan, remediate, evidence)
- [ ] Feature parity with Slack bot
- [ ] Comprehensive tests

**Phase 3 Complete When:**
- [ ] EVO integration working
- [ ] Multi-customer deployment automated
- [ ] Production-ready monitoring

---

## 📞 Open Questions

1. **EVO Integration:** How does EVO MCP server discovery work?
2. **Multi-Tenancy:** Does EVO need per-customer MCP servers or shared?
3. **Auth:** How does Caylent SSO integrate with MCP?
4. **Monitoring:** Centralized logging for all customer deployments?

---

## 🔄 Next Steps

1. **Test Phase 1** - Deploy to test AWS account, verify everything works
2. **Demo to Caylent** - Show working MCP integration
3. **Get EVO Requirements** - Understand EVO-specific needs
4. **Build Phase 2** - Implement remaining tools
5. **Pilot with 1-2 Customers** - Real-world testing
6. **Scale to All Customers** - Full rollout

---

## 📅 Timeline

- **Week 1:** Phase 1 complete ✅
- **Week 2:** Phase 2 (additional tools)
- **Week 3:** Phase 3 (EVO integration)
- **Week 4:** Phase 4 (migration, docs)
- **Month 2:** Pilot customers
- **Month 3:** Full rollout

---

## 📚 Resources

- **Branch:** `feature/mcp-migration`
- **Terraform:** `carl-infrastructure/mcp-deployment/`
- **MCP Server:** `carl-mcp-server/`
- **Install Script:** `install-carl-mcp.sh`
- **GitHub Actions:** `.github/workflows/deploy-mcp.yml`
