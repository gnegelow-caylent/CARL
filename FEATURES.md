# CARL Features - Status Overview

**Last Updated:** January 28, 2026

This document provides a clear view of what CARL can do today vs what's planned for the future.

---

## ✅ Production Ready Features

### 🤖 AI-Powered Capabilities

| Feature | Status | Description |
|---------|--------|-------------|
| Natural Language Compliance Queries | ✅ Live | Ask CARL compliance questions in plain English via `/carl ask` |
| AI Architecture Recommendations | ✅ Live | Get intelligent AWS architecture suggestions based on requirements |
| Adaptive Learning | ✅ Live | CARL learns from user feedback to improve recommendations |
| Context-Aware Responses | ✅ Live | AI maintains conversation context for follow-up questions |
| Slack-Optimized Formatting | ✅ Live | Responses automatically formatted for Slack (no raw markdown) |

### 🏗️ Smart Infrastructure Generation (NEW)

| Feature | Status | Description |
|---------|--------|-------------|
| **Environment-Aware Generation** | ✅ Live | Scans AWS before generating code to detect existing resources |
| **No Duplicate Resources** | ✅ Live | Won't try to create GuardDuty if it already exists in your account |
| **Dynamic Code Generation** | ✅ Live | Generates ONLY the Terraform needed (uses data sources for existing) |
| **Intelligent Detection Notes** | ✅ Live | Shows ✓ for existing resources, ✗ for what will be created |
| **Smart Compliance Notes** | ✅ Live | "Using existing CloudTrail: my-trail" vs "CloudTrail created" |
| Security Services Detection | ✅ Live | GuardDuty, Security Hub, AWS Config, CloudTrail |
| Networking Detection | ✅ Live | VPC, Subnets, NAT Gateways, Internet Gateways |
| S3 Bucket Detection | 🔄 Partial | Name-based detection (not fully implemented) |

### 📐 Architecture Patterns Library

**Total Patterns:** 43+ production-ready patterns

| Category | Count | Status | Details |
|----------|-------|--------|---------|
| **VPC & Networking** | 8 patterns | ✅ Live | Egress, ingress, transit, VPN, endpoints, peering |
| **VPC Endpoints & PrivateLink** | 3 patterns | ✅ Live | Interface, Gateway, PrivateLink service patterns |
| **Identity & Access** | 6 patterns | ✅ Live | IAM roles, Identity Center, SAML, cross-account access |
| **Security Tooling** | 7 patterns | ✅ Live | GuardDuty, Security Hub, Inspector, Config, WAF |
| **Logging & Monitoring** | 5 patterns | ✅ Live | CloudTrail, CloudWatch, centralized logging |
| **KMS & Encryption** | 4 patterns | ✅ Live | Key management, rotation, cross-account, envelope encryption |
| **Operational Patterns** | 5 patterns | ✅ Live | Tagging, backup, cost management, automation |
| **Multi-Account** | 5 patterns | ✅ Live | Organizations, Control Tower, landing zones |

### 🔧 Infrastructure Code Generation

| Blueprint | Status | Description |
|-----------|--------|-------------|
| **Security - Basic Stack** | ✅ Live | GuardDuty + Security Hub + CloudTrail (smart generation) |
| **Security - SOC 2 Stack** | ✅ Live | Full compliance stack with Config + 7-year retention (smart) |
| **Networking - Basic VPC** | ✅ Live | 2-AZ VPC with single NAT, flow logs (smart generation) |
| **Networking - Standard VPC** | ✅ Live | 3-AZ HA VPC with WAF-ready setup |
| **Networking - Enterprise VPC** | ✅ Live | Multi-region, Transit Gateway ready |
| **Storage - Compliant S3** | ✅ Live | SOC 2 compliant S3 bucket with encryption, versioning, logging |

### 🔐 Security & Compliance

| Feature | Status | Description |
|---------|--------|-------------|
| Security Hub Integration | ✅ Live | Real-time findings from Security Hub |
| SOC 2 Control Mapping | ✅ Live | All findings mapped to SOC 2 controls (CC6.x, CC7.x, A1.x) |
| Compliance Status Dashboard | ✅ Live | `/carl status` shows overall compliance posture |
| Findings Management | ✅ Live | `/carl findings` to view, filter, acknowledge findings |
| Risk Exception Management | ✅ Live | Accept risks with expiration dates and business justification |

### 📊 Audit & Evidence

| Feature | Status | Description |
|---------|--------|-------------|
| Automated Evidence Collection | ✅ Live | Collects screenshots, configs, logs automatically |
| Evidence Storage (S3) | ✅ Live | Secure storage with encryption and retention |
| Evidence Coverage Tracking | ✅ Live | Shows which controls have evidence |
| Report Generation | ✅ Live | Executive, detailed, and control-specific reports |
| Audit-Ready Export | ✅ Live | PDF/JSON exports for auditors |

### 🔄 Configuration Management

| Feature | Status | Description |
|---------|--------|-------------|
| Infrastructure Drift Detection | ✅ Live | Detects changes to deployed infrastructure |
| Drift Acknowledgment | ✅ Live | Mark expected drift as acknowledged |
| Terraform State Analysis | ✅ Live | Analyzes Terraform state for drift |
| Drift Reporting | ✅ Live | `/carl drift status` shows all drift |

### 🚀 AWS Environment Bootstrap (NEW)

| Feature | Status | Description |
|---------|--------|-------------|
| **Organizations Automation** | ✅ Live | Create OU structure + SCPs via code |
| **Identity Center Automation** | ✅ Live | Permission sets + groups + assignments via code |
| **Security Services Setup** | ✅ Live | Delegated admin for Security Hub, GuardDuty, Inspector, Config |
| **3-Phase Orchestration** | ✅ Live | Complete environment bootstrap in correct order |
| Quickstart Configuration | ✅ Live | AWS-recommended setup out of the box |
| Custom Configuration | ✅ Live | Customize OUs, permission sets, account assignments |

### 💬 Slack Integration

| Feature | Status | Description |
|---------|--------|-------------|
| Command Interface | ✅ Live | 30+ slash commands (`/carl help` for full list) |
| Interactive Buttons | ✅ Live | Click to acknowledge findings, approve actions |
| Modal Dialogs | ✅ Live | VPC config modal, setup wizards |
| Async Processing | ✅ Live | Long-running operations don't timeout |
| Threaded Responses | ✅ Live | Keeps conversations organized |
| File Uploads | ✅ Live | Terraform code uploaded as attachments |
| Keep-Warm Optimization | ✅ Live | Lambda stays warm to avoid cold start timeouts |

### 💰 Cost Transparency

| Feature | Status | Description |
|---------|--------|-------------|
| Accurate AWS Pricing | ✅ Live | Real pricing data (not estimates) for all patterns |
| Cost Ranges | ✅ Live | Shows min-max monthly costs for each option |
| Cost Comparison | ✅ Live | Compare costs across architecture options |
| CARL Operational Cost | ✅ Live | ~$1-2/month actual cost (mostly free tier) |

---

## 🔄 In Development

### Phase 1: Enhanced Integration (Weeks 1-8)

| Feature | Status | Target | Description |
|---------|--------|--------|-------------|
| Slack Bootstrap Commands | 📋 Planned | Week 2 | `/carl bootstrap` commands for environment setup |
| GitHub PR Workflow | 📋 Planned | Week 3 | Auto-create PRs for infrastructure changes |
| GitHub Actions Integration | 📋 Planned | Week 4 | Automated terraform validate/plan/apply |
| CloudWatch Alerting Patterns | 📋 Planned | Week 5 | Metric alarms, dashboards, SNS integration (4 patterns) |
| AWS WAF Patterns | 📋 Planned | Week 6 | Rule patterns, managed rules, rate limiting (3 patterns) |
| Certificate Manager Patterns | 📋 Planned | Week 7 | Lifecycle management, auto-renewal (2 patterns) |
| Secrets Manager Patterns | 📋 Planned | Week 8 | Rotation strategies, Lambda functions (3 patterns) |

### Phase 2: Complete Pattern Coverage (Weeks 9-16)

| Category | Status | Target | Pattern Count |
|----------|--------|--------|---------------|
| **Compute Security** | 📋 Planned | Week 10 | +12 patterns (EC2, ECS, EKS, Lambda) |
| **Database Deployment** | 📋 Planned | Week 12 | +11 patterns (RDS, Aurora, DynamoDB, ElastiCache) |
| **Application Services** | 📋 Planned | Week 14 | +9 patterns (API Gateway, ALB/NLB, SQS/SNS) |
| **Storage Advanced** | 📋 Planned | Week 16 | +5 patterns (S3 lifecycle, replication, EFS/FSx) |

### Phase 3: Intelligence & Multi-Framework (Weeks 17-30)

| Feature | Status | Target | Description |
|---------|--------|--------|-------------|
| Auto-Discovery | 📋 Planned | Week 20 | Detect new AWS services/resources automatically |
| Auto-Remediation | 📋 Planned | Week 22 | Execute fixes for common compliance issues |
| HIPAA Support | 📋 Planned | Week 24 | HIPAA control mappings and patterns |
| PCI-DSS Support | 📋 Planned | Week 26 | PCI-DSS control mappings and patterns |
| ISO 27001 Support | 📋 Planned | Week 28 | ISO 27001 control mappings and patterns |
| ML Anomaly Detection | 📋 Planned | Week 30 | Cost and security anomaly detection |

---

## ❌ Not Planned / Out of Scope

### Explicitly Not Building

| Feature | Reason |
|---------|--------|
| Infrastructure Deployment | CARL generates code; users deploy via GitHub Actions/CI-CD |
| Direct AWS API Writes | Read-only security scanning only (no destructive actions) |
| Multi-Cloud Support | AWS-focused (Azure/GCP out of scope) |
| Custom Compliance Frameworks | Focused on SOC 2, HIPAA, PCI-DSS, ISO 27001 |
| Real-Time Alerting | Use CloudWatch/SNS; CARL is advisory, not operational |
| Credential Management | Uses AWS IAM roles, not stored credentials |

### Intentional Limitations

| Limitation | Reason |
|------------|--------|
| No Terraform State Management | Users manage state (S3 backend); CARL doesn't touch state |
| No Auto-Apply | All changes require human approval (security/compliance) |
| No Production Deployment | CARL generates code for dev; users promote to prod |
| Read-Only Scanning | Safe compliance checking without infrastructure changes |

---

## 🎯 Feature Request Process

Want a new feature? Here's how:

1. **Check this document** - Is it already planned?
2. **GitHub Issue** - Open an issue at `https://github.com/your-org/carl/issues`
3. **Slack Discussion** - Discuss in `#carl-feedback` channel
4. **Priority Review** - Team reviews monthly and updates roadmap

### Top Community Requests

| Feature | Votes | Status |
|---------|-------|--------|
| GitLab Integration | 12 | Under consideration |
| Terraform Cloud Integration | 8 | Planned (Q2) |
| Azure AD SSO | 6 | Not planned |
| Cost Optimization Recommendations | 15 | Planned (Phase 3) |

---

## 📊 Stats

- **Total Slack Commands:** 30+
- **Architecture Patterns:** 43+ (growing)
- **Infrastructure Blueprints:** 6 production-ready
- **Lines of Code:** 15,000+
- **Supported AWS Services:** 25+
- **SOC 2 Controls Covered:** 45+
- **Average Response Time:** <2 seconds (with keep-warm)
- **Current Cost:** $1-2/month operational (mostly free tier)

---

## 🔗 Related Documentation

- **[SLACK_COMMANDS.md](./SLACK_COMMANDS.md)** - Complete command reference
- **[INFRASTRUCTURE_BLUEPRINTS.md](./INFRASTRUCTURE_BLUEPRINTS.md)** - Blueprint documentation
- **[SMART_GENERATION.md](./SMART_GENERATION.md)** - Smart infrastructure generation guide
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Technical architecture
- **[ROADMAP.md](./ROADMAP.md)** - Detailed development roadmap
- **[BOOTSTRAP_AUTOMATION.md](./BOOTSTRAP_AUTOMATION.md)** - Environment bootstrap guide

---

## 📝 Legend

- ✅ **Live** - Production ready, fully tested
- 🔄 **Partial** - Partially implemented
- 📋 **Planned** - In roadmap with target date
- ❌ **Not Planned** - Out of scope
- 🚧 **In Development** - Currently being built

---

*This document is updated monthly. For real-time status, see project board or ask in #carl-updates*
