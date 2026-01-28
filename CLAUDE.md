# CARL - Claude Context File

This file provides context for Claude Code sessions working on this project.

## Project Overview

**CARL** = Cloud Automated Risk & Compliance Logic

An AI-powered AWS compliance bot that:
- Scans AWS environments for SOC 2 compliance issues
- **NEW: Bootstraps complete AWS environments from scratch (Organizations, Identity Center, Security Services)**
- Builds compliant AWS infrastructure from scratch (Foundation Builder)
- Provides AI-driven architecture recommendations with accurate pricing
- Collects audit evidence automatically
- Generates compliance reports
- Manages risk exceptions
- Detects infrastructure drift

## Latest Updates (Current Session)

### Bootstrap Automation Released 🚀

**5 Critical Capabilities Added:**
1. ✅ **VPC Endpoints/PrivateLink Patterns** (3 patterns) - Private connectivity, security gap closed
2. ✅ **KMS Key Management Patterns** (4 patterns) - Encryption strategy, key rotation, policies
3. ✅ **Organizations Bootstrap Automation** - OU structure + SCPs through code
4. ✅ **IAM Identity Center Automation** - Permission sets, groups, assignments
5. ✅ **Security Services Delegated Admin** - Security Hub, GuardDuty, Inspector, Config, Macie, Detective

**Pattern Count:** 36 → **43+ patterns**

**New Code:** 3,100+ lines across 9 new files

See `BOOTSTRAP_AUTOMATION.md` for complete details.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CARL System                              │
├─────────────────────────────────────────────────────────────────┤
│  Slack Interface (/carl commands)                                │
│       ↓                                                          │
│  Lambda Handlers (slack_router.py)                               │
│       ↓                                                          │
│  Services Layer:                                                 │
│  - ai_architect.py (AI-driven recommendations)                   │
│  - evidence_collector.py (audit evidence)                        │
│  - report_generator.py (compliance reports)                      │
│  - exception_manager.py (risk acceptances)                       │
│  - drift_detector.py (configuration drift)                       │
│  - bedrock_service.py (Claude AI via Bedrock)                    │
│  - foundation/ (guided infrastructure builder)                   │
│       ↓                                                          │
│  Knowledge Layer:                                                │
│  - 36+ architecture patterns (vpc, identity, security, etc.)     │
│  - AWS pricing data (accurate, not estimated)                    │
│  - SOC 2 control mappings                                        │
│       ↓                                                          │
│  Infrastructure (Terraform):                                     │
│  - DynamoDB tables (findings, evidence, exceptions, drift)       │
│  - S3 buckets (evidence, reports)                                │
│  - Lambda, API Gateway, EventBridge                              │
│  - KMS, Secrets Manager                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Key Directories

```
carl-app/
├── src/
│   ├── handlers/          # Lambda entry points
│   │   └── slack_router.py  # Main Slack command router
│   ├── services/          # Business logic
│   │   ├── ai_architect.py        # AI recommendations (hybrid static+AI)
│   │   ├── evidence_collector.py  # Audit evidence collection
│   │   ├── report_generator.py    # Compliance report generation
│   │   ├── exception_manager.py   # Risk exception management
│   │   ├── drift_detector.py      # Infrastructure drift detection
│   │   ├── bedrock_service.py     # Claude/Bedrock integration
│   │   ├── knowledge_retrieval.py # RAG + continuous learning
│   │   ├── foundation/            # Foundation builder wizard
│   │   └── bootstrap/             # **NEW:** Complete environment bootstrap
│   │       ├── organizations_bootstrap.py     # Organizations + OU + SCPs
│   │       ├── identity_center_bootstrap.py  # IAM Identity Center setup
│   │       ├── security_services_bootstrap.py # Security services delegated admin
│   │       └── bootstrap_orchestrator.py     # 3-phase orchestration
│   ├── knowledge/         # Static knowledge base
│   │   ├── architecture_patterns.py  # Egress, ingress, transit, VPN, etc.
│   │   ├── vpc_patterns.py          # VPC design patterns
│   │   ├── vpc_endpoint_patterns.py # **NEW:** VPC endpoints & PrivateLink (3 patterns)
│   │   ├── kms_patterns.py          # **NEW:** KMS & encryption at rest (4 patterns)
│   │   ├── account_patterns.py      # Multi-account patterns
│   │   ├── identity_patterns.py     # IAM/Identity Center patterns
│   │   ├── security_tooling_patterns.py  # Security Hub, GuardDuty, etc.
│   │   ├── logging_patterns.py      # Centralized logging patterns
│   │   ├── operational_patterns.py  # Tagging, backup, cost management
│   │   └── aws_pricing.py           # Accurate AWS pricing data
│   └── utils/             # Utilities
│
carl-infrastructure/
├── modules/
│   ├── foundation/        # Core infrastructure (DynamoDB, S3, IAM, KMS)
│   └── scanning/          # Security Hub integration
└── environments/
    └── dev/               # Dev environment config
```

## Slack Commands

**Compliance:**
- `/carl status` - Compliance posture summary
- `/carl findings [severity]` - List findings
- `/carl ask <question>` - Natural language query

**Architecture:**
- `/carl foundation start` - Guided foundation builder wizard
- `/carl architect <question>` - AI architecture recommendations
- `/carl patterns [category]` - View architecture patterns
- `/carl recommend <requirement>` - Get recommendations with cost
- `/carl build <blueprint>` - Generate Terraform code
- `/carl estimate <component>` - Cost estimates

**Bootstrap (NEW - To Be Implemented):**
- `/carl bootstrap start` - Start complete environment bootstrap
- `/carl bootstrap quickstart` - Use AWS recommended configuration
- `/carl bootstrap minimal` - Minimal setup for getting started
- `/carl bootstrap status` - Check bootstrap progress
- `/carl bootstrap organizations` - Organizations setup only
- `/carl bootstrap identity-center` - Identity Center setup only
- `/carl bootstrap security-services` - Security services setup only

**Audit & Evidence:**
- `/carl evidence collect` - Collect audit evidence
- `/carl evidence status` - View evidence coverage
- `/carl report executive|full|control <id>` - Generate reports

**Risk Management:**
- `/carl exception list|request|approve|deny|stats`

**Drift Detection:**
- `/carl drift scan|status|acknowledge|terraform`

## Bootstrap Automation Usage

**Complete Environment Bootstrap (Python):**
```python
from carl.services.bootstrap import BootstrapOrchestrator

# Initialize orchestrator
orchestrator = BootstrapOrchestrator()

# Get quickstart config (AWS recommended)
config = orchestrator.get_quickstart_config(
    delegated_admin_account_id="999888777666",
    security_regions=["us-east-1", "us-west-2"]
)

# Customize account assignments
config.account_assignments = [
    AccountAssignment(
        account_id="111222333444",
        permission_set_name="AdministratorAccess",
        principal_type="GROUP",
        principal_name="CloudPlatformAdmins"
    )
]

# Execute 3-phase bootstrap
result = orchestrator.bootstrap_complete_environment(config)

if result.success:
    print(f"✓ Organization: {result.organization_result['organization_id']}")
    print(f"✓ Identity Center: {result.identity_center_result['instance_arn']}")
    print(f"✓ Security Hub Admin: {result.security_services_result['security_hub_admin']}")
```

**What Gets Created:**
1. **Phase 1 - Organizations:**
   - OU structure (Security, Infrastructure, Workloads, Sandbox, etc.)
   - SCPs (deny security service disabling, region restrictions, IMDSv2)

2. **Phase 2 - Identity Center:**
   - 5 permission sets (Admin, PowerUser, ReadOnly, SecurityAudit, Billing)
   - 5 groups (CloudPlatformAdmins, Developers, SecurityTeam, etc.)
   - Account assignments (group → account → permission set)

3. **Phase 3 - Security Services:**
   - Security Hub (delegated admin + auto-enable)
   - GuardDuty (all data sources + auto-enable)
   - Inspector (EC2, ECR, Lambda scanning)
   - Config organization aggregator

See `BOOTSTRAP_AUTOMATION.md` for complete documentation.

## Design Principles

1. **AI-Driven with Static Guardrails**: AI generates recommendations, static patterns provide structure and accurate pricing
2. **SOC 2 First**: Every feature maps to SOC 2 controls
3. **Accurate Pricing**: No wild assumptions - real AWS pricing data
4. **Continuous Learning**: User feedback improves recommendations over time
5. **Audit-Ready**: Evidence collection and report generation for auditors
6. **Bootstrap Through Code**: Complete AWS environment setup via automation (NEW)

## Current Capabilities (All Built)

| Feature | Status |
|---------|--------|
| AI architecture recommendations | ✅ |
| 43+ architecture patterns with pros/cons | ✅ |
| **VPC Endpoints & PrivateLink patterns** | ✅ **NEW** |
| **KMS key management & encryption patterns** | ✅ **NEW** |
| Accurate AWS pricing | ✅ |
| Foundation builder wizard | ✅ |
| **Organizations bootstrap automation** | ✅ **NEW** |
| **IAM Identity Center setup automation** | ✅ **NEW** |
| **Security services delegated admin automation** | ✅ **NEW** |
| **Complete environment orchestration (3-phase)** | ✅ **NEW** |
| Terraform code generation | ✅ |
| Security Hub integration | ✅ |
| Audit evidence collection | ✅ |
| Compliance report generation | ✅ |
| Risk exception management | ✅ |
| Infrastructure drift detection | ✅ |
| Continuous AI learning | ✅ |

## Estimated Costs

- **CARL operational cost**: $75-200/month (Bedrock API, Lambda, DynamoDB, S3)
- All new tables use pay-per-request pricing

## Next Steps / Priority Roadmap

See `ROADMAP.md` for detailed priority list.

**High Priority (Next):**
1. Integrate bootstrap services with Foundation Builder
2. Add Slack commands for bootstrap (`/carl bootstrap`)
3. Terraform module generation for bootstrap components
4. Account baseline deployment automation
5. CloudWatch alerting patterns
6. AWS WAF rule patterns
7. Certificate Manager patterns
8. Secrets Manager lifecycle patterns

**Medium Priority:**
- Compute security patterns (EC2, ECS, EKS, Lambda)
- Database deployment patterns (RDS, Aurora, DynamoDB)
- Application patterns (API Gateway, ALB/NLB, caching)
- Adaptive monitoring (auto-discovery, self-healing)
- Auto-remediation execution

**Long-Term:**
- Multi-framework support (HIPAA, PCI-DSS, ISO 27001)
- Dashboards and trend analysis
- CI/CD integration (pre-deployment compliance checks)
- ML-based anomaly detection
