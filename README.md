# CARL - Cloud Automated Risk & Compliance Logic

> AI-powered AWS compliance automation for SOC 2, HIPAA, and beyond

## What is CARL?

CARL is an intelligent compliance platform that helps organizations achieve and maintain SOC 2 and HIPAA compliance on AWS. Built on AWS-native services and powered by Amazon Bedrock (Claude), CARL provides **end-to-end compliance automation**:

| Capability | Description |
|------------|-------------|
| **AI Architecture Advisor** | Get personalized AWS architecture recommendations that learn from feedback |
| **Foundation Builder** | Guided wizard to build compliant AWS infrastructure from scratch |
| **Compliance Monitoring** | Real-time scanning via Security Hub, GuardDuty, Config |
| **Audit Evidence Collection** | Automated collection mapped to SOC 2, HIPAA, PCI DSS, and NIST CSF controls |
| **Multi-Framework Support** | SOC 2, HIPAA, PCI DSS 4.0, NIST CSF 2.0 compliance frameworks |
| **Compliance Reports** | Executive summaries and audit-ready documentation (per framework) |
| **Risk Exception Management** | Track and manage accepted risks with approval workflows |
| **Drift Detection** | Detect configuration drift and security misconfigurations |
| **Terraform Generation** | Generate compliant infrastructure code on demand |
| **AgentCore Cold Start Resilience** | 5-minute timeout handles cold starts gracefully |

## Current Status: Fully Built + Deployed to AWS

All core capabilities have been implemented and deployed, including **NEW: Foundation Module with Real-Time Pricing**:

| Feature | Status | Service |
|---------|--------|---------|
| AI-driven architecture recommendations | ✅ Deployed | `ai_architect.py` |
| 43+ architecture patterns with pros/cons | ✅ Deployed | `knowledge/*.py` |
| **VPC Endpoints & PrivateLink patterns** | ✅ Deployed | `vpc_endpoint_patterns.py` |
| **KMS key management patterns** | ✅ Deployed | `kms_patterns.py` |
| **Real-time AWS pricing (100+ services)** | ✅ **NEW** | `pricing_prefetch_service.py` |
| **Foundation module (10 DynamoDB tables)** | ✅ **NEW** | `modules/foundation/` |
| **KMS encryption key** | ✅ **NEW** | Core infrastructure |
| **Continuous learning system** | ✅ **NEW** | `learning_service.py` |
| Foundation builder wizard | ✅ Deployed | `foundation/` |
| **Organizations bootstrap automation** | ✅ Deployed | `bootstrap/organizations_bootstrap.py` |
| **IAM Identity Center automation** | ✅ Deployed | `bootstrap/identity_center_bootstrap.py` |
| **Security services delegated admin** | ✅ Deployed | `bootstrap/security_services_bootstrap.py` |
| **Complete environment orchestration** | ✅ Deployed | `bootstrap/bootstrap_orchestrator.py` |
| Terraform code generation | ✅ Deployed | `foundation_builder.py` |
| Security Hub integration | ✅ Deployed | `findings_service.py` |
| Audit evidence collection | ✅ Deployed | `evidence_collector.py` |
| Compliance report generation | ✅ Deployed | `report_generator.py` |
| Risk exception management | ✅ Deployed | `exception_manager.py` |
| Infrastructure drift detection | ✅ Deployed | `drift_detector.py` |

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Full technical architecture, component diagrams, data models |
| [DEPLOYMENT_NOTES.md](./DEPLOYMENT_NOTES.md) | **NEW:** Complete deployment guide with foundation module details (500+ lines) |
| [FEATURES.md](./FEATURES.md) | **UPDATED:** Complete feature status - what's live vs planned |
| [BOOTSTRAP_AUTOMATION.md](./BOOTSTRAP_AUTOMATION.md) | Complete AWS environment bootstrap automation guide |
| [CONTINUOUS_LEARNING.md](./CONTINUOUS_LEARNING.md) | Continuous learning system - pattern analysis and adaptation |
| [SLACK_COMMANDS.md](./SLACK_COMMANDS.md) | Comprehensive Slack commands user guide with examples |
| [SLACK_IMPROVEMENTS.md](./SLACK_IMPROVEMENTS.md) | Technical implementation guide for Slack integration improvements |
| [ROADMAP.md](./ROADMAP.md) | Priority roadmap and next steps |
| [IMPLEMENTATION_PHASES.md](./IMPLEMENTATION_PHASES.md) | Phased implementation plan with completed status |
| [COST_ESTIMATES.md](./COST_ESTIMATES.md) | Detailed cost breakdown |
| [CLAUDE.md](./CLAUDE.md) | Context file for Claude Code sessions |

## Quick Facts

| Attribute | Value |
|-----------|-------|
| **Target Frameworks** | SOC 2 (all controls), HIPAA (18 safeguards), CIS Benchmarks |
| **Deployment Model** | Centralized management account |
| **User Interface** | Slack |
| **AI Backend** | Amazon Bedrock (Claude Haiku for simple queries, Sonnet for architecture) |
| **Foundation Cost** | **$2.61/month** (DynamoDB, Lambda, KMS, Secrets, S3, CloudWatch) |
| **With Security Scanning** | $22-50/month per account (adds Security Hub + Bedrock API usage) |
| **AWS Services Covered** | 100+ services with real-time pricing (366 items across 3 regions) |

## Slack Commands

### Compliance & Monitoring
```
/carl status                    - Compliance posture summary
/carl findings [severity]       - List findings (CRITICAL, HIGH, MEDIUM, LOW)
/carl ask <question>            - Natural language compliance query
```

### Architecture & Building
```
/carl foundation start          - Launch guided foundation builder wizard
/carl foundation status         - Check current session
/carl architect <question>      - AI architecture recommendations (learns from feedback)
/carl patterns [category]       - View architecture patterns with pros/cons
/carl recommend <requirement>   - Get recommendations with cost comparison
/carl build <blueprint>         - Generate Terraform code
/carl estimate <component>      - Get cost estimates
/carl blueprints                - List available blueprints
```

### Audit & Evidence
```
/carl evidence collect [framework]   - Collect audit evidence (soc2, hipaa, pci, nist)
/carl evidence status [framework]    - View evidence collection coverage by framework
/carl report executive [framework]   - Generate compliance summary for framework
/carl report full               - Generate full audit report
/carl report control <id>       - Generate control-specific report (e.g., CC6.1)
```

### Risk Management
```
/carl exception list            - View pending/active exceptions
/carl exception request         - Request a new risk exception
/carl exception approve <id>    - Approve an exception
/carl exception deny <id>       - Deny an exception
/carl exception stats           - View exception statistics
```

### Drift Detection
```
/carl drift scan                - Run infrastructure drift detection
/carl drift status              - View current drift summary
/carl drift acknowledge <id>    - Mark drift as reviewed
/carl drift terraform <key>     - Compare with Terraform state
```

### Remediation (Auto-Fix with Approval)
```
/carl remediate list            - List findings with available fixes
/carl remediate <finding_id>    - Request fix for specific finding
/carl remediate help            - Show remediation help
```

**How it works:**
- 🟢 **LOW risk** (S3 encryption, versioning): Applied directly via AWS API
- 🟡 **MEDIUM risk** (flow logs): Creates GitHub PR for review
- 🔴 **HIGH risk** (security groups): Creates GitHub PR for careful review

CARL **never** applies fixes without explicit user approval.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CARL System                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Slack Interface                        │   │
│  │            /carl commands + interactive buttons           │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │              API Gateway + Lambda Router                  │   │
│  │                  (slack_router.py)                        │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                   Services Layer                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │ AI Architect│  │  Evidence   │  │  Report         │   │   │
│  │  │  (Sonnet)   │  │  Collector  │  │  Generator      │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │  Exception  │  │   Drift     │  │   Foundation    │   │   │
│  │  │  Manager    │  │  Detector   │  │   Builder       │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                  Knowledge Layer                          │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │  36+ Architecture Patterns (VPC, IAM, Security...)  │ │   │
│  │  │  Accurate AWS Pricing Data                          │ │   │
│  │  │  SOC 2 + HIPAA Control Mappings                     │ │   │
│  │  │  RAG + Continuous Learning                          │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │                Infrastructure Layer                       │   │
│  │  DynamoDB: findings, evidence, exceptions, drift, feedback│   │
│  │  S3: evidence bucket, reports bucket                      │   │
│  │  Bedrock: Claude Haiku + Sonnet                          │   │
│  │  Security Hub, GuardDuty, Config                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
CARL/
├── carl-app/                      # Application code
│   └── src/
│       ├── handlers/              # Lambda entry points
│       │   └── slack_router.py    # Main Slack command router
│       ├── services/              # Business logic
│       │   ├── ai_architect.py         # AI-driven recommendations
│       │   ├── bedrock_service.py      # Claude/Bedrock integration
│       │   ├── evidence_collector.py   # Audit evidence collection
│       │   ├── report_generator.py     # Compliance reports
│       │   ├── exception_manager.py    # Risk exceptions
│       │   ├── drift_detector.py       # Drift detection
│       │   ├── knowledge_retrieval.py  # RAG + learning
│       │   ├── findings_service.py     # Security Hub findings
│       │   ├── architecture_advisor.py # Pattern recommendations
│       │   ├── cost_estimator.py       # Cost estimation
│       │   ├── infrastructure_builder.py # Terraform generation
│       │   ├── foundation/             # Foundation builder
│       │   │   ├── decision_engine.py  # Guided wizard
│       │   │   └── foundation_builder.py # Code generation
│       │   └── bootstrap/              # **NEW:** Environment bootstrap
│       │       ├── organizations_bootstrap.py    # Organizations + OU + SCPs
│       │       ├── identity_center_bootstrap.py # IAM Identity Center setup
│       │       ├── security_services_bootstrap.py # Security services delegated admin
│       │       └── bootstrap_orchestrator.py    # Complete environment orchestration
│       ├── knowledge/             # Static knowledge base
│       │   ├── architecture_patterns.py   # Core networking patterns
│       │   ├── vpc_patterns.py           # VPC design
│       │   ├── vpc_endpoint_patterns.py  # **NEW:** VPC endpoints & PrivateLink
│       │   ├── kms_patterns.py           # **NEW:** KMS & encryption at rest
│       │   ├── account_patterns.py       # Multi-account
│       │   ├── identity_patterns.py      # IAM/Identity Center
│       │   ├── security_tooling_patterns.py # Security Hub, GuardDuty
│       │   ├── logging_patterns.py       # Centralized logging
│       │   ├── operational_patterns.py   # Tagging, backup, cost
│       │   └── aws_pricing.py            # Accurate pricing data
│       └── utils/                 # Utilities
│
├── carl-infrastructure/           # Terraform
│   ├── modules/
│   │   ├── foundation/           # Core resources
│   │   └── scanning/             # Security Hub integration
│   └── environments/
│       └── dev/                  # Dev environment
│
├── ARCHITECTURE.md               # Technical architecture
├── IMPLEMENTATION_PHASES.md      # Implementation plan
├── COST_ESTIMATES.md             # Cost breakdown
├── CLAUDE.md                     # Claude Code context
└── README.md                     # This file
```

## Architecture Patterns Included

CARL includes **43+ architecture decision patterns** with:
- Detailed pros and cons
- Accurate AWS pricing
- SOC 2 control mappings
- When to use / when not to use

| Category | Patterns |
|----------|----------|
| **Networking** | Egress (NAT, Network Firewall), Ingress (ALB, CloudFront), Transit (TGW, Peering) |
| **Connectivity** | Site-to-Site VPN, Client VPN, Direct Connect |
| **VPC Design** | CIDR planning, Subnet tiers, AZ strategy, VPC endpoints |
| **VPC Endpoints** | **NEW:** Endpoint strategy, Endpoint policies, PrivateLink (3 patterns) |
| **Encryption** | **NEW:** KMS strategy, Key rotation, Key policies, Encryption at rest (4 patterns) |
| **Account Structure** | OU hierarchy, Core accounts, Account baselines, SCPs |
| **Identity** | IAM Identity Center, Permission sets, Cross-account, Break-glass |
| **Security Tooling** | Security Hub, GuardDuty, Config, Inspector, Firewall Manager, Detective |
| **Logging** | Log aggregation, CloudTrail, Application logs, Retention |
| **Operational** | Tagging strategy, Backup/DR, Cost management, Systems Manager |

### NEW: Bootstrap Automation

CARL now provides **complete AWS environment bootstrap automation**:

| Capability | Description |
|------------|-------------|
| **Organizations Setup** | Automated OU structure + SCPs (AWS recommended best practices) |
| **Identity Center** | Permission sets, groups, account assignments |
| **Security Services** | Delegated admin setup for Security Hub, GuardDuty, Inspector, Config |
| **VPC Endpoints** | Private connectivity patterns for AWS services (no internet egress) |
| **KMS Encryption** | Key management strategy, rotation, encryption at rest |

**Bootstrap in 3 commands:**
```python
from carl.services.bootstrap import BootstrapOrchestrator

orchestrator = BootstrapOrchestrator()
config = orchestrator.get_quickstart_config(delegated_admin_account_id="999888777666")
result = orchestrator.bootstrap_complete_environment(config)
```

See [BOOTSTRAP_AUTOMATION.md](./BOOTSTRAP_AUTOMATION.md) for complete guide.

## Compliance Framework Coverage

CARL maps all features to SOC 2 Trust Services Criteria and HIPAA safeguards:

| Control Area | Coverage |
|--------------|----------|
| **CC1-CC5** | Control Environment, Communication, Risk Assessment, Monitoring, Control Activities |
| **CC6** | Logical Access (IAM, MFA, access reviews, encryption) |
| **CC7** | System Operations (monitoring, incident response, logging) |
| **CC8** | Change Management (drift detection, Terraform state) |
| **CC9** | Risk Mitigation (exception management, vendor controls) |
| **A1** | Availability (backup, DR, capacity planning) |
| **C1** | Confidentiality (encryption, data classification) |

## Cost Summary

| Deployment | Monthly Cost |
|------------|--------------|
| Single Account | $75-200 |
| 5 Accounts | $250-550 |
| 20 Accounts | $900-2,100 |

**Cost breakdown:**
- Bedrock API (Claude): $30-100/mo (usage-based)
- Lambda: $5-20/mo
- DynamoDB: $10-30/mo (pay-per-request)
- S3: $5-15/mo
- Security Hub: $20-50/mo per account

## Getting Started

### Prerequisites

**AWS Requirements:**
- AWS Account with admin access
- AWS CLI configured
- Terraform >= 1.0
- **AWS Bedrock model access enabled** (Claude 3.5 Sonnet and Claude 3 Haiku)

**Slack Requirements:**
- Slack Workspace with admin access
- Ability to create Slack apps

**GitHub Requirements:**
- GitHub repository for CARL code
- GitHub Actions enabled

### Quick Start (3 Commands!)

**1. Run bootstrap script**
```bash
./bootstrap.sh
```

This single script:
- Creates S3 bucket for Terraform state
- Deploys OIDC provider (no hardcoded AWS credentials!)
- Creates IAM roles for deployment
- Verifies Bedrock model access
- Outputs GitHub secrets

**2. Add GitHub secrets**

The bootstrap script will output 4 AWS secrets. Add them to GitHub:
```bash
export GH_TOKEN=your_github_token
gh secret set AWS_ROLE_ARN_DEV -b "arn:aws:iam::ACCOUNT:role/carl-deployer-dev" -R your-org/CARL
gh secret set AWS_ROLE_ARN_QA -b "arn:aws:iam::ACCOUNT:role/carl-deployer-qa" -R your-org/CARL
gh secret set AWS_ROLE_ARN_PROD -b "arn:aws:iam::ACCOUNT:role/carl-deployer-prod" -R your-org/CARL
gh secret set AWS_REGION -b "us-east-1" -R your-org/CARL
```

**3. Add Slack secrets**

Create a Slack app and add bot credentials:
```bash
gh secret set SLACK_BOT_TOKEN_DEV -b "xoxb-your-token" -R your-org/CARL
gh secret set SLACK_SIGNING_SECRET_DEV -b "your-secret" -R your-org/CARL
```

**4. Deploy via GitHub Actions**
```bash
git checkout -b develop
git push origin develop
```

That's it! GitHub Actions deploys everything automatically using OIDC.

See detailed guides:
- **[BOOTSTRAP.md](./BOOTSTRAP.md)** - Complete bootstrap guide
- **[SLACK_SETUP.md](./SLACK_SETUP.md)** - Slack app configuration
- **[OIDC_SETUP.md](./OIDC_SETUP.md)** - OIDC authentication details

### First Commands

```bash
# In Slack:
/carl help                    # See all commands
/carl status                  # Check compliance posture
/carl foundation start        # Build your foundation
/carl evidence collect        # Collect audit evidence
/carl report executive        # Generate compliance report
```

## Design Principles

1. **AI-Driven with Static Guardrails**: AI generates personalized recommendations; static patterns provide structure and accurate pricing (AI can hallucinate costs)

2. **Compliance First**: Every feature maps to SOC 2 and HIPAA controls; evidence collection and reports are audit-ready

3. **Accurate Pricing**: Real AWS pricing data, not estimates; users can trust the cost comparisons

4. **Continuous Learning**: User feedback improves AI recommendations over time

5. **Hybrid Intelligence**: Best of both worlds - AI reasoning + curated best practices

## What's New (Latest Update)

### HIPAA Compliance Framework 🏥 (April 2026) - COMPLETE

Full HIPAA compliance support for healthcare workloads on AWS:

| Component | Details |
|-----------|---------|
| **HIPAA Controls** | 18 safeguard categories mapped to AWS services |
| **Eligible Services** | 140+ AWS services with eligibility status and BAA coverage |
| **Evidence Collection** | HIPAA-aware audit evidence collection |
| **AI Integration** | Bedrock prompts include HIPAA context for recommendations |

**HIPAA Safeguard Categories:**
- **Administrative (8):** Security Management, Workforce Security, Information Access, Training, Incident Response, Contingency Planning, Evaluation, BAA
- **Physical (4):** Facility Access, Workstation Use, Workstation Security, Device Controls
- **Technical (5):** Access Control, Audit Controls, Integrity, Person Authentication, Transmission Security
- **Organizational (2):** BAA Requirements, Policies & Procedures

**Files Added:**
- `carl-app/src/knowledge/hipaa_controls.py` - HIPAA safeguards mapped to AWS
- `carl-app/src/knowledge/hipaa_eligible_services.py` - 140+ service eligibility catalog
- `carl-app/src/knowledge/compliance_frameworks.py` - Extensible framework base

### AWS Bedrock AgentCore Deployment ☁️ (April 2026) - COMPLETE

All CARL agents now run on **AWS Bedrock AgentCore**, the managed agent runtime platform:

| Agent | Status | Description |
|-------|--------|-------------|
| **Ask Agent** | ✅ Deployed | Q&A with intelligent AWS environment scanning |
| **Architect Agent** | ✅ Deployed | Architecture recommendations with real-time pricing |
| **Remediation Agent** | ✅ Deployed | AI-powered auto-fix with human approval |

**Benefits:**
- AWS-managed scaling and orchestration
- 8-hour task support (no Lambda timeout limits)
- Built-in observability (CloudWatch, X-Ray)
- Container-based deployment via GitHub Actions

**Infrastructure:**
- `modules/agentcore-ask/` - Ask Agent
- `modules/agentcore-architect/` - Architect Agent
- `modules/agentcore-remediate/` - Remediation Agent

### Remediation Agent 🔧 (April 2026) - Now on AgentCore

AI-powered auto-fix with human-in-the-loop approval:
- **Risk Classification**: LOW/MEDIUM/HIGH automatic categorization
- **Hybrid Method**: Direct AWS API for LOW risk, GitHub PR for MEDIUM/HIGH
- **Safety**: Never applies fixes without explicit user approval
- **AI-Generated Terraform**: All fixes include Terraform code for audit
- Commands: `/carl remediate list`, `/carl remediate <id>`, `/carl remediate help`

### Bootstrap Automation Released 🚀

CARL now includes **complete AWS environment bootstrap automation**, enabling you to set up production-ready, SOC 2 and HIPAA-compliant AWS environments from scratch through code.

**New Capabilities:**
- ✅ **Organizations Bootstrap** - Automated OU structure + SCPs
- ✅ **Identity Center Setup** - Permission sets, groups, account assignments
- ✅ **Security Services** - Delegated admin for Security Hub, GuardDuty, Inspector, Config
- ✅ **VPC Endpoints Patterns** - 3 new patterns for private connectivity
- ✅ **KMS Patterns** - 4 new patterns for encryption strategy

**Pattern Count:** 36 → **43+ patterns**

**New Code:** 3,100+ lines across 9 new files

See [BOOTSTRAP_AUTOMATION.md](./BOOTSTRAP_AUTOMATION.md) for complete guide.

---

## MCP Gateway (NEW)

CARL now includes three MCP (Model Context Protocol) servers for enhanced capabilities:

| MCP Server | Purpose | Key Tools |
|------------|---------|-----------|
| **GitHub MCP** | Repository & PR management | `create_terraform_pr`, `create_pull_request`, `list_repositories` |
| **Memory MCP** | Persistent knowledge graph | `create_entity`, `create_relation`, `store_learning_pattern` |
| **Terraform MCP** | Validation & module discovery | `validate_terraform`, `search_modules`, `get_provider_docs` |

**Architecture:**
```
┌─────────────────────────────────────────────────────────────────┐
│                    Bedrock AgentCore                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Gateway                                  │
│              (Cognito JWT Authentication)                        │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │ GitHub MCP  │      │ Memory MCP  │      │Terraform MCP│
    │  (Lambda)   │      │  (Lambda)   │      │  (Lambda)   │
    └─────────────┘      └─────────────┘      └─────────────┘
```

See [modules/mcp-gateway/README.md](./carl-infrastructure/modules/mcp-gateway/README.md) for setup details.

## What's Next

See [ROADMAP.md](./ROADMAP.md) for the complete priority roadmap.

**High Priority:**
1. ~~Migrate to AWS Bedrock AgentCore~~ ✅ COMPLETE (All agents on AgentCore)
2. Regression testing framework
3. CARL uninstall & cleanup process

**Medium Priority:**
4. Compute security patterns (EC2, ECS, EKS, Lambda)
5. Database deployment patterns (RDS, Aurora, DynamoDB)
6. Application patterns (API Gateway, ALB/NLB, caching)
7. Adaptive monitoring (auto-discovery, self-healing)
8. Multi-framework support (~~HIPAA~~ ✅, PCI-DSS, ISO 27001)

---

## License

Proprietary

---

*Built with Claude Code*
