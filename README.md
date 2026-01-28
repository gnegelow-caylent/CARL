# CARL - Cloud Automated Risk & Compliance Logic

> AI-powered AWS compliance automation for SOC 2 and beyond

## What is CARL?

CARL is an intelligent compliance platform that helps organizations achieve and maintain SOC 2 compliance on AWS. Built on AWS-native services and powered by Amazon Bedrock (Claude), CARL provides **end-to-end compliance automation**:

| Capability | Description |
|------------|-------------|
| **AI Architecture Advisor** | Get personalized AWS architecture recommendations that learn from feedback |
| **Foundation Builder** | Guided wizard to build compliant AWS infrastructure from scratch |
| **Compliance Monitoring** | Real-time scanning via Security Hub, GuardDuty, Config |
| **Audit Evidence Collection** | Automated collection mapped to SOC 2 controls |
| **Compliance Reports** | Executive summaries and audit-ready documentation |
| **Risk Exception Management** | Track and manage accepted risks with approval workflows |
| **Drift Detection** | Detect configuration drift and security misconfigurations |
| **Terraform Generation** | Generate compliant infrastructure code on demand |

## Current Status: Fully Built + Bootstrap Automation

All core capabilities have been implemented, including **NEW: Complete AWS Environment Bootstrap Automation**:

| Feature | Status | Service |
|---------|--------|---------|
| AI-driven architecture recommendations | ✅ Complete | `ai_architect.py` |
| 43+ architecture patterns with pros/cons | ✅ Complete | `knowledge/*.py` |
| **VPC Endpoints & PrivateLink patterns** | ✅ **NEW** | `vpc_endpoint_patterns.py` |
| **KMS key management patterns** | ✅ **NEW** | `kms_patterns.py` |
| Accurate AWS pricing (not estimated) | ✅ Complete | `aws_pricing.py` |
| Foundation builder wizard | ✅ Complete | `foundation/` |
| **Organizations bootstrap automation** | ✅ **NEW** | `bootstrap/organizations_bootstrap.py` |
| **IAM Identity Center automation** | ✅ **NEW** | `bootstrap/identity_center_bootstrap.py` |
| **Security services delegated admin** | ✅ **NEW** | `bootstrap/security_services_bootstrap.py` |
| **Complete environment orchestration** | ✅ **NEW** | `bootstrap/bootstrap_orchestrator.py` |
| Terraform code generation | ✅ Complete | `foundation_builder.py` |
| Security Hub integration | ✅ Complete | `findings_service.py` |
| Audit evidence collection | ✅ Complete | `evidence_collector.py` |
| Compliance report generation | ✅ Complete | `report_generator.py` |
| Risk exception management | ✅ Complete | `exception_manager.py` |
| Infrastructure drift detection | ✅ Complete | `drift_detector.py` |
| Continuous AI learning | ✅ Complete | `knowledge_retrieval.py` |

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Full technical architecture, component diagrams, data models |
| [BOOTSTRAP_AUTOMATION.md](./BOOTSTRAP_AUTOMATION.md) | **NEW:** Complete AWS environment bootstrap automation guide |
| [SLACK_COMMANDS.md](./SLACK_COMMANDS.md) | **NEW:** Comprehensive Slack commands user guide with examples |
| [SLACK_IMPROVEMENTS.md](./SLACK_IMPROVEMENTS.md) | **NEW:** Technical implementation guide for Slack integration improvements |
| [ROADMAP.md](./ROADMAP.md) | **NEW:** Priority roadmap and next steps |
| [IMPLEMENTATION_PHASES.md](./IMPLEMENTATION_PHASES.md) | Phased implementation plan with completed status |
| [COST_ESTIMATES.md](./COST_ESTIMATES.md) | Detailed cost breakdown |
| [CLAUDE.md](./CLAUDE.md) | Context file for Claude Code sessions |

## Quick Facts

| Attribute | Value |
|-----------|-------|
| **Target Frameworks** | SOC 2 (all controls), CIS Benchmarks |
| **Deployment Model** | Centralized management account |
| **User Interface** | Slack |
| **AI Backend** | Amazon Bedrock (Claude Haiku for simple queries, Sonnet for architecture) |
| **Monthly Cost** | $75-200 (single account) |

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
/carl evidence collect          - Collect audit evidence across all resources
/carl evidence status           - View evidence collection coverage
/carl report executive          - Generate executive compliance summary
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
│  │  │  SOC 2 Control Mappings                             │ │   │
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

## SOC 2 Control Coverage

CARL maps all features to SOC 2 Trust Services Criteria:

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

2. **SOC 2 First**: Every feature maps to SOC 2 controls; evidence collection and reports are audit-ready

3. **Accurate Pricing**: Real AWS pricing data, not estimates; users can trust the cost comparisons

4. **Continuous Learning**: User feedback improves AI recommendations over time

5. **Hybrid Intelligence**: Best of both worlds - AI reasoning + curated best practices

## What's New (Latest Update)

### Bootstrap Automation Released 🚀

CARL now includes **complete AWS environment bootstrap automation**, enabling you to set up production-ready, SOC 2-compliant AWS environments from scratch through code.

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

## What's Next

See [ROADMAP.md](./ROADMAP.md) for the complete priority roadmap.

**High Priority:**
1. Integrate bootstrap services with Foundation Builder
2. Add Slack commands for bootstrap (`/carl bootstrap`)
3. Terraform module generation for bootstrap components
4. Account baseline deployment automation
5. CloudWatch alerting patterns

**Medium Priority:**
6. Compute security patterns (EC2, ECS, EKS, Lambda)
7. Database deployment patterns (RDS, Aurora, DynamoDB)
8. Application patterns (API Gateway, ALB/NLB, caching)
9. Adaptive monitoring (auto-discovery, self-healing)
10. Multi-framework support (HIPAA, PCI-DSS, ISO 27001)

---

## License

Proprietary

---

*Built with Claude Code*
