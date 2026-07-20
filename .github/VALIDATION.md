# CARL MCP Validation Strategy

This document explains all validations run by the GitHub Actions workflow for the MCP implementation.

## Overview

Since MCP deploys to **customer AWS accounts** (not Caylent's centralized infrastructure), we cannot deploy from CI/CD. Instead, we perform comprehensive validation to catch issues before they reach customers.

## Validation Jobs

### 1. Terraform Validation (`validate-terraform`)

**What it checks:**
- ✅ Terraform syntax validity (`terraform validate`)
- ✅ Terraform formatting (`terraform fmt -check`)
- ✅ Documentation completeness (README.md exists)
- ✅ Deployment instructions present

**Files validated:**
- `carl-infrastructure/mcp-deployment/*.tf`
- `carl-infrastructure/mcp-deployment/README.md`

**Why it matters:** Catches Terraform configuration errors before customers run `terraform apply`.

---

### 2. Python Linting (`lint-python`)

**What it checks:**
- ✅ **Ruff linting** - Code style, imports, naming conventions
  - Checks: E (errors), F (pyflakes), W (warnings), C90 (complexity), I (imports), N (naming), UP (upgrades)
  - Ignores: E501 (line length) for readability
- ✅ **Mypy type checking** - Type hint validation
- ✅ **Bandit security scanning** - Common security issues (SQL injection, hardcoded passwords, etc.)
- ✅ **AgentCore Python syntax** - Validates all agent code compiles

**Files validated:**
- `carl-mcp-server/src/**/*.py`
- `carl-infrastructure/agentcore-code/ask-agent/*.py`
- `carl-infrastructure/agentcore-code/architect-agent/*.py`
- `carl-infrastructure/agentcore-code/remediate-agent/*.py`

**Why it matters:** Catches Python errors, security issues, and type problems before runtime.

---

### 3. MCP Server Tests (`test-mcp-server`)

**What it checks:**
- ✅ **Unit tests** - pytest with coverage reporting
- ✅ **Import validation** - All modules import successfully
  - `carl_mcp_server.server`
  - `carl_mcp_server.clients.agentcore`
  - `carl_mcp_server.tools.*`
- ✅ **MCP protocol compliance** - All tools have required fields:
  - `name` - Tool identifier
  - `description` - What the tool does
  - `inputSchema` - Parameter definitions
- ✅ **Package metadata** - Version, name, author fields present

**Files validated:**
- `carl-mcp-server/src/**/*.py`
- `carl-mcp-server/tests/**/*.py`
- `carl-mcp-server/setup.py`

**Why it matters:** Ensures MCP server works with Claude Desktop and follows MCP specification.

---

### 4. Security Scan (`security-scan`)

**What it checks:**
- ✅ **Dependency vulnerabilities** - pip-audit checks for known CVEs
- ✅ **Secret detection** - Searches for:
  - AWS access keys (AKIA...)
  - Hardcoded secrets
  - Exposed credentials

**Files scanned:**
- `carl-mcp-server/**`
- `carl-infrastructure/**`

**Why it matters:** Prevents shipping vulnerable dependencies or leaked secrets to customers.

---

### 5. Documentation Validation (`validate-docs`)

**What it checks:**
- ✅ **Required files exist:**
  - `carl-mcp-server/README.md` - Package overview
  - `carl-mcp-server/DEPLOYMENT.md` - Full deployment guide
  - `QUICKSTART.md` - Quick setup guide
- ✅ **Markdown links** - Internal links to other docs

**Files validated:**
- `carl-mcp-server/README.md`
- `carl-mcp-server/DEPLOYMENT.md`
- `QUICKSTART.md`

**Why it matters:** Ensures customers have complete documentation for setup.

---

### 6. AgentCore Validation (`validate-agentcore`)

**What it checks:**
- ✅ **Python dependencies** - requirements.txt files are installable
- ✅ **Dockerfile syntax** - All agent Dockerfiles are valid
- ✅ **Build compatibility** - Containers can be built successfully

**Files validated:**
- `carl-infrastructure/agentcore-code/ask-agent/`
- `carl-infrastructure/agentcore-code/architect-agent/`
- `carl-infrastructure/agentcore-code/remediate-agent/`

**Why it matters:** Catches Docker build issues before customers push to ECR.

---

## What's NOT Validated (Intentionally)

These require actual AWS credentials and are validated during customer deployment:

- ❌ **AWS resource creation** - Requires `terraform apply` in customer account
- ❌ **AgentCore runtime invocation** - Requires deployed infrastructure
- ❌ **S3/DynamoDB access** - Requires real AWS resources
- ❌ **IAM permissions** - Validated during actual deployment
- ❌ **Container registry push** - ECR requires customer credentials

## Validation Triggers

Workflow runs on:

```yaml
push:
  branches:
    - feature/mcp-migration
    - main
  paths:
    - 'carl-infrastructure/agentcore-code/**'
    - 'carl-infrastructure/mcp-deployment/**'
    - 'carl-mcp-server/**'
    - '.github/workflows/deploy-mcp.yml'

pull_request:
  branches:
    - main
    - develop
```

## Running Validations Locally

### Terraform Validation
```bash
cd carl-infrastructure/mcp-deployment
terraform init -backend=false
terraform validate
terraform fmt -check -recursive
```

### Python Linting
```bash
cd carl-mcp-server
pip install ruff bandit mypy
ruff check src/
mypy src/ --ignore-missing-imports
bandit -r src/ -ll
```

### MCP Server Tests
```bash
cd carl-mcp-server
pip install -e .
pip install pytest pytest-asyncio pytest-cov
pytest tests/ --cov=src
```

### Security Scan
```bash
cd carl-mcp-server
pip install pip-audit
pip-audit
```

### AgentCore Validation
```bash
cd carl-infrastructure/agentcore-code/ask-agent
docker build --check .
```

## Continuous Improvement

As we identify new failure modes in customer deployments, we'll add validation for them:

**Future validations to add:**
- [ ] Terraform plan dry-run (without state)
- [ ] Python 3.11+ specific syntax validation
- [ ] MCP protocol integration tests (mock Claude Desktop)
- [ ] Load testing for AgentCore tool definitions
- [ ] Automated documentation generation validation

## Cost

All validations run on GitHub-hosted runners:
- **Public repos:** Free (unlimited minutes)
- **Private repos:** Included in GitHub plan

No AWS costs since we don't deploy from CI/CD.

---

**Questions or issues?** Open an issue at https://github.com/gnegelow-caylent/CARL/issues
