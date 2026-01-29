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

### Compliance Agent Released 🤖 (January 29, 2026)

**Revolutionary New Capability:** Full autonomous SOC 2 compliance assessment with a single command!

**What's New:**
1. ✅ **Compliance Agent** - Autonomous end-to-end compliance management using AWS Bedrock Agents
2. ✅ **Intelligent Evidence Collection** - Smart prioritization, pattern detection, root cause analysis
3. ✅ **SOC 2 Gap Analysis** - Maps findings to 43 SOC 2 controls, calculates coverage %
4. ✅ **Remediation Planning** - 4-phase plan with dependencies, effort estimates
5. ✅ **Jira Epic Creation** - Automatically creates epic + stories for tracking
6. ✅ **Async Processing** - 3-5 minute workflow without Lambda timeout

**New Command:**
- `/carl compliance assess` - Run complete autonomous SOC 2 assessment

**What It Does:**
```
User: /carl compliance assess

Agent autonomously (3-5 minutes):
1. Scans AWS environment (~150 resources intelligently)
2. Detects patterns and root causes
3. Analyzes SOC 2 control coverage (e.g., 53%)
4. Generates 4-phase remediation plan (37 tasks)
5. Creates Jira epic CARLSEC-EPIC-1 with child stories
6. Posts results to Slack with roadmap

Result: Complete compliance roadmap from 53% → 100% in 4-6 weeks
```

**Files Added:**
- `compliance_agent.py` - Full agent implementation (800+ lines)
- `COMPLIANCE_AGENT.md` - Complete configuration guide
- Enhanced `jira_service.py` with epic/story creation
- Slack commands: `/carl compliance assess|status`

**Cost:** ~$2/month | **ROI:** 1,000x (saves 20 hours/month)

See `COMPLIANCE_AGENT.md` and `AI_OPPORTUNITIES.md` for complete details.

### Smart Infrastructure Generation Released 🎯 (January 28, 2026)

**Revolutionary New Capability:** CARL now scans your AWS environment before generating infrastructure code!

**What Changed:**
1. ✅ **Environment-Aware Generation** - Scans AWS before creating code
2. ✅ **Resource Detection Service** - Detects GuardDuty, Security Hub, Config, CloudTrail, VPCs
3. ✅ **No Duplicate Resources** - Won't try to create what already exists
4. ✅ **Dynamic Code Generation** - Generates ONLY missing resources (uses data sources for existing)
5. ✅ **Smart Compliance Notes** - "Using existing CloudTrail: my-trail" vs "CloudTrail created"

**Updated Blueprints:**
- `security/basic-stack` - Smart detection for GuardDuty, Security Hub, CloudTrail
- `security/soc2-stack` - Full smart detection including AWS Config
- `networking/basic-vpc` - VPC detection by name tag

**New Files:**
- `resource_detector.py` - AWS resource scanning service (300 lines)
- Updated infrastructure_builder.py with smart generation (~2,000 lines refactored)

**Key Benefits:**
- Zero manual configuration (no more `create_XXX = false` variables)
- Cleaner generated code (only what's needed)
- Clear feedback (✓ exists vs ✗ missing)
- Faster deployments (less resources to create)

See `SMART_GENERATION.md` for complete details.

### Evidence Collection & Jira Sync Fixed 🔧 (January 28, 2026)

**Complete Pipeline Working:** Evidence collection now automatically creates findings and syncs to Jira!

**Major Fixes:**
1. ✅ **Security Findings Detection** - Evidence analysis creates Finding objects for all issues
2. ✅ **Stable Finding IDs** - Content-based IDs (account+resource+issue) prevent duplicates
3. ✅ **Multiple Findings Per Resource** - One S3 bucket with 3 issues = 3 findings
4. ✅ **Jira Duplicate Prevention** - Checks for existing tickets before creating new ones
5. ✅ **S3 Encryption Detection** - Handles both None and "ERROR" (permission denied)
6. ✅ **IAM Permissions** - Comprehensive read-only policy for evidence collection
7. ✅ **DynamoDB Composite Keys** - Fixed Query/Update operations for pk+sk schema
8. ✅ **Field Name Mappings** - Fixed Finding.to_dict() field references

**What Works Now:**
- `/carl evidence collect` → Scans AWS → Creates findings for all detected issues
- `/carl jira sync` → Creates Jira tickets for new findings only (no duplicates)
- Findings tracked: IAM password policies, S3 encryption, security groups, VPC flow logs

**Bug Fixes:**
- Fixed 6 nested f-string syntax errors (SyntaxError)
- Fixed KeyError 'finding_id' (wrong field name)
- Added missing update_finding() method to FindingsService
- Fixed jira_ticket_id preservation in get_finding()
- Changed to standard Jira issue types (Task, not custom types)
- Fixed evidence_collector to return lists (multiple findings per resource)

See `EVIDENCE_AND_FINDINGS.md` for complete documentation.

### Bootstrap Automation Released 🚀 (January 27, 2026)

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
│   │   ├── resource_detector.py   # **NEW:** AWS resource detection for smart generation
│   │   ├── infrastructure_builder.py # Smart infrastructure code generation
│   │   ├── foundation/            # Foundation builder wizard
│   │   └── bootstrap/             # Complete environment bootstrap
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

## Additional Documentation

For detailed guides and reference materials:

### User Guides
- **[FEATURES.md](./FEATURES.md)** - Complete feature status overview (what's live vs planned)
- **[SLACK_COMMANDS.md](./SLACK_COMMANDS.md)** - Comprehensive user guide for all Slack commands
- **[INFRASTRUCTURE_BLUEPRINTS.md](./INFRASTRUCTURE_BLUEPRINTS.md)** - All available infrastructure blueprints

### Technical Guides
- **[SMART_GENERATION.md](./SMART_GENERATION.md)** - Smart infrastructure generation (environment-aware code generation)
- **[BOOTSTRAP_AUTOMATION.md](./BOOTSTRAP_AUTOMATION.md)** - Complete AWS environment bootstrap automation
- **[EVIDENCE_AND_FINDINGS.md](./EVIDENCE_AND_FINDINGS.md)** - Evidence collection, findings detection, and Jira sync pipeline
- **[SLACK_IMPROVEMENTS.md](./SLACK_IMPROVEMENTS.md)** - Async processing, modals, button handlers
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Full technical architecture and component diagrams

### Planning
- **[ROADMAP.md](./ROADMAP.md)** - Priority roadmap and next steps
