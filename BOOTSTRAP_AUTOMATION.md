# CARL Bootstrap Automation

## Overview

CARL now includes **complete AWS environment bootstrap automation**, enabling you to set up a production-ready, SOC 2-compliant AWS environment from scratch through code.

This addresses the critical gaps identified:
- ✅ Organizations + OU structure setup
- ✅ IAM Identity Center configuration
- ✅ Security services delegated admin setup
- ✅ VPC Endpoints patterns
- ✅ KMS key management patterns

---

## New Capabilities

### 1. Organizations Bootstrap (`organizations_bootstrap.py`)

**Automates:**
- AWS Organizations creation
- OU (Organizational Unit) structure
- Service Control Policies (SCPs)
- Account baseline policies

**Key Features:**
- AWS recommended OU structure (Security, Infrastructure, Workloads, Sandbox)
- Production-ready SCPs (prevent security service disabling, region restrictions, IMDSv2 requirements)
- Automatic SCP attachment to target OUs
- Idempotent operations (safe to re-run)

**Example Usage:**
```python
from carl.services.bootstrap import OrganizationsBootstrapService

service = OrganizationsBootstrapService()

# Get AWS recommended structure
ou_structure = service.get_aws_recommended_ou_structure()
scps = service.get_recommended_scps()

# Bootstrap organization
result = service.bootstrap_organization(
    feature_set="ALL",
    ou_structure=ou_structure,
    scps=scps
)

print(f"Organization ID: {result.organization_id}")
print(f"Created OUs: {result.ou_map}")
print(f"Created SCPs: {result.scp_map}")
```

**AWS Recommended OU Structure:**
```
Root
├── Security (Log Archive, Audit, Security Tooling)
├── Infrastructure (Network, Shared Services)
├── Workloads
│   ├── Production
│   ├── Staging
│   └── Development
├── Sandbox
├── PolicyStaging (test SCPs)
└── Suspended (decommissioned accounts)
```

**Recommended SCPs:**
- Deny security service disabling (CloudTrail, GuardDuty, Security Hub, Config)
- Deny leaving organization
- Restrict to approved regions
- Require IMDSv2 for EC2
- Deny root user access (except break-glass)

---

### 2. Identity Center Bootstrap (`identity_center_bootstrap.py`)

**Automates:**
- IAM Identity Center permission sets
- Groups creation
- Account assignments (group → account → permission set)

**Key Features:**
- 5 baseline permission sets (Admin, PowerUser, ReadOnly, SecurityAudit, Billing)
- 5 baseline groups (CloudPlatformAdmins, Developers, SecurityTeam, ReadOnlyUsers, FinanceTeam)
- Flexible session durations per permission set
- Support for managed policies + inline policies
- Idempotent operations

**Example Usage:**
```python
from carl.services.bootstrap import IdentityCenterBootstrapService

service = IdentityCenterBootstrapService()

# Get recommended baseline
permission_sets = service.get_recommended_permission_sets()
groups = service.get_recommended_groups()

# Define assignments
assignments = [
    AccountAssignment(
        account_id="123456789012",
        permission_set_name="AdministratorAccess",
        principal_type="GROUP",
        principal_name="CloudPlatformAdmins"
    )
]

# Bootstrap Identity Center
result = service.bootstrap_identity_center(
    permission_sets=permission_sets,
    groups=groups,
    assignments=assignments
)

print(f"Created Permission Sets: {len(result.permission_set_map)}")
print(f"Created Groups: {len(result.group_map)}")
print(f"Created Assignments: {len(result.assignment_results)}")
```

**Recommended Permission Sets:**
| Name | Session Duration | Use Case |
|------|------------------|----------|
| AdministratorAccess | 1 hour | Full AWS access (platform team) |
| PowerUserAccess | 4 hours | Full access except IAM (developers in non-prod) |
| ReadOnlyAccess | 12 hours | Read access (audit, analysis) |
| SecurityAudit | 8 hours | Security service access (security team) |
| BillingAccess | 8 hours | Cost & billing (finance team) |

---

### 3. Security Services Bootstrap (`security_services_bootstrap.py`)

**Automates:**
- Security Hub delegated administrator
- GuardDuty organization-wide
- Inspector enablement
- Macie (optional)
- Detective (optional)
- Config organization aggregator

**Key Features:**
- Multi-region support
- Delegated administrator model (not management account)
- Auto-enable for new accounts
- All data sources enabled (S3, Kubernetes, malware protection)
- Idempotent operations

**Example Usage:**
```python
from carl.services.bootstrap import SecurityServicesBootstrapService

service = SecurityServicesBootstrapService(
    delegated_admin_account_id="999888777666",  # Security account
    regions=["us-east-1", "us-west-2"]
)

result = service.bootstrap_all_services(
    enable_security_hub=True,
    enable_guardduty=True,
    enable_inspector=True,
    enable_macie=False,  # Optional
    enable_detective=False,  # Optional
    enable_config_aggregator=True
)

print(f"Security Hub Admin: {result.security_hub_admin}")
print(f"GuardDuty Admin: {result.guardduty_admin}")
```

**What Gets Configured:**

**Security Hub:**
- Enabled with default standards (AWS Foundational Security Best Practices)
- Delegated admin in security account
- Auto-enable for new accounts
- AWS recommended standards enabled

**GuardDuty:**
- All data sources enabled (CloudTrail, VPC Flow Logs, DNS, S3, Kubernetes)
- 15-minute finding frequency
- Delegated admin in security account
- Auto-enable for new accounts and data sources

**Inspector:**
- Scans EC2, ECR, Lambda
- Delegated admin in security account
- Auto-enable for new accounts

**Config:**
- Organization aggregator in delegated admin account
- All regions included
- Enables cross-account compliance reporting

---

### 4. Bootstrap Orchestrator (`bootstrap_orchestrator.py`)

**Orchestrates complete environment setup in 3 phases:**

1. **Organizations** → Create OU structure + SCPs
2. **Identity Center** → Create permission sets, groups, assignments
3. **Security Services** → Enable and configure security tooling

**Example Usage:**
```python
from carl.services.bootstrap import BootstrapOrchestrator

orchestrator = BootstrapOrchestrator()

# Get quickstart config (AWS recommended)
config = orchestrator.get_quickstart_config(
    delegated_admin_account_id="999888777666",
    security_regions=["us-east-1", "us-west-2"]
)

# Customize assignments
config.account_assignments = [
    AccountAssignment(
        account_id="111222333444",
        permission_set_name="AdministratorAccess",
        principal_type="GROUP",
        principal_name="CloudPlatformAdmins"
    ),
    # ... more assignments
]

# Run complete bootstrap
result = orchestrator.bootstrap_complete_environment(config)

if result.success:
    print("✓ Bootstrap complete!")
    print(f"Organization: {result.organization_result['organization_id']}")
    print(f"Identity Center: {result.identity_center_result['instance_arn']}")
    print(f"Security Hub Admin: {result.security_services_result['security_hub_admin']}")
else:
    print("✗ Bootstrap failed:")
    for error in result.errors:
        print(f"  - {error}")
```

**Quickstart vs Minimal:**
- **Quickstart**: AWS recommended structure, all security services, production-ready
- **Minimal**: Basic OUs, essential SCPs, Security Hub + GuardDuty only, development-friendly

---

## New Architecture Patterns

### 5. VPC Endpoints Patterns (`vpc_endpoint_patterns.py`)

**3 Decision Categories:**
1. **VPC Endpoint Strategy** - When and how to use VPC endpoints
2. **Endpoint Policies** - How to secure endpoints with policies
3. **PrivateLink** - Service provider and consumer patterns

**Key Patterns:**
- **Gateway Endpoints Only** (S3 + DynamoDB, free)
- **Selective Interface Endpoints** (critical services only, $20-100/mo)
- **Comprehensive Interface Endpoints** (no internet egress, $100-500/mo)
- **Centralized Endpoint VPC** (shared via TGW, cost-effective at scale)

**Essential Interface Endpoints (Priority Order):**

**Tier 1 (Security Critical):**
- `ssm`, `ssmmessages`, `ec2messages` (Session Manager - no SSH needed)
- `kms` (encryption key access)
- `secretsmanager` (secrets access)
- `logs` (CloudWatch Logs)

**Tier 2 (Common Services):**
- `ecr.dkr`, `ecr.api` (container images)
- `s3` (if need interface endpoint features)
- `sts` (temporary credentials)
- `ec2` (EC2 API calls)

**Tier 3 (Service-Specific):**
- `rds`, `lambda`, `ecs`, `elasticloadbalancing`, `execute-api`

**Cost Analysis:**
- Interface Endpoint: $0.01/hr = $7.20/mo per AZ
- Data processing: $0.01/GB
- 3 endpoints × 2 AZs = $43/mo
- Break-even vs NAT Gateway at ~5 endpoints

---

### 6. KMS Patterns (`kms_patterns.py`)

**4 Decision Categories:**
1. **KMS Key Strategy** - How many keys, what architecture
2. **Key Rotation** - Automatic vs manual rotation
3. **Key Policies** - Least privilege key access control
4. **Encryption at Rest** - What to encrypt and how

**Key Patterns:**
- **AWS Managed Keys** (free, limited control)
- **Single CMK per Service** (recommended, $5-20/mo)
- **Multi-Key Strategy** (per workload/environment, $20-100/mo)
- **Centralized Key Management** (multi-account, shared keys)

**Recommended Key Architecture:**
```
Production Account:
├── kms-prod-s3 (S3 bucket encryption)
├── kms-prod-rds (RDS/Aurora encryption)
├── kms-prod-ebs (EBS volume encryption)
├── kms-prod-secrets (Secrets Manager)
├── kms-prod-logs (CloudWatch Logs)
├── kms-prod-backup (AWS Backup)
├── kms-prod-sns (SNS topics)
└── kms-prod-sqs (SQS queues)
```

**Key Rotation:**
- **Automatic**: Yearly, transparent, no downtime (RECOMMENDED)
- **Manual**: Custom schedule, requires alias management

**Always Encrypt:**
- RDS/Aurora databases
- S3 buckets with sensitive data
- EBS volumes (enable account default)
- Secrets Manager secrets
- DynamoDB tables with PII

**Enable EBS Encryption by Default:**
```bash
aws ec2 enable-ebs-encryption-by-default --region us-east-1
aws ec2 modify-ebs-default-kms-key-id --kms-key-id KEY_ARN
```

---

## Integration with CARL

### Slack Commands (Proposed)

```
# Bootstrap complete environment
/carl bootstrap start

# Bootstrap with quickstart config
/carl bootstrap quickstart --admin-account 999888777666

# Bootstrap with minimal config
/carl bootstrap minimal

# Check bootstrap status
/carl bootstrap status

# View bootstrap configuration
/carl bootstrap config show

# Organizations setup only
/carl bootstrap organizations

# Identity Center setup only
/carl bootstrap identity-center

# Security services setup only
/carl bootstrap security-services --admin-account 999888777666
```

### API Integration

The bootstrap services are designed to integrate with CARL's existing Slack router:

```python
# In slack_router.py
from services.bootstrap import BootstrapOrchestrator

def handle_bootstrap_command(command_text: str, user_id: str):
    """Handle /carl bootstrap commands."""
    orchestrator = BootstrapOrchestrator()

    if "quickstart" in command_text:
        # Get admin account from command
        admin_account = extract_account_id(command_text)
        config = orchestrator.get_quickstart_config(admin_account)

        # Show config and ask for confirmation
        return show_bootstrap_preview(config)

    elif "start" in command_text:
        # Execute bootstrap with stored config
        result = orchestrator.bootstrap_complete_environment(config)
        return format_bootstrap_result(result)
```

---

## SOC 2 Compliance Impact

These new capabilities significantly strengthen CARL's SOC 2 compliance posture:

### Organizations Bootstrap
- **CC6.1**: Account separation enforces access control
- **CC6.6**: SCPs enforce organization-wide policies
- **CC8.1**: Infrastructure as Code for account structure

### Identity Center Bootstrap
- **CC6.1**: Centralized access provisioning
- **CC6.2**: Group-based access management
- **CC6.3**: Automated access removal (disable in IdP)

### Security Services Bootstrap
- **CC6.8**: Automated threat detection (GuardDuty)
- **CC7.1**: Vulnerability management (Inspector)
- **CC7.2**: Centralized security monitoring (Security Hub)
- **CC7.3**: Security event analysis (Detective)

### VPC Endpoints
- **CC6.6**: Private connectivity (no internet exposure)
- **CC6.7**: Data stays on AWS network
- **CC6.8**: Reduced attack surface

### KMS Patterns
- **CC6.5**: Encryption at rest for all sensitive data
- **C1.1**: Confidentiality through encryption
- **CC8.1**: Automated key rotation

---

## Cost Summary

**One-Time Setup:**
- Organizations: Free
- IAM Identity Center: Free
- Security Services: Free (underlying service costs apply)

**Ongoing Costs (per account):**
| Service | Monthly Cost |
|---------|--------------|
| Security Hub | $5-30 |
| GuardDuty | $10-30 |
| Inspector | $10-100 (if using EC2/containers) |
| Config | $15-30 |
| **Subtotal** | **$40-190 per account** |

**VPC Endpoints (optional but recommended):**
| Configuration | Monthly Cost |
|---------------|--------------|
| Essential only (SSM, KMS, Secrets) | $20-45 |
| Standard (10 endpoints) | $70-150 |
| Comprehensive (20 endpoints) | $140-290 |

**KMS:**
| Strategy | Monthly Cost |
|----------|--------------|
| Single per service | $5-20 |
| Multi-key | $20-100 |

**Total Baseline (per account):**
- **Minimal**: $50-100/mo (Security Hub + GuardDuty + Config)
- **Standard**: $100-250/mo (+ VPC endpoints + KMS)
- **Enterprise**: $200-500/mo (+ Inspector + Macie + comprehensive endpoints)

---

## Next Steps

### Immediate (Ready to Use)
1. ✅ Organizations bootstrap automation
2. ✅ Identity Center setup automation
3. ✅ Security services delegated admin setup
4. ✅ VPC endpoint patterns
5. ✅ KMS patterns

### Short-Term (Integration)
1. Integrate with Foundation Builder
2. Add Slack command handlers
3. Add interactive approval workflows
4. Add progress tracking to DynamoDB

### Medium-Term (Enhancements)
1. Terraform code generation for all bootstrap components
2. Account baseline deployment automation
3. VPC endpoints deployment module
4. KMS key creation automation
5. Drift detection for bootstrap config

---

## Documentation

**Pattern Files:**
- `vpc_endpoint_patterns.py` - VPC endpoints and PrivateLink
- `kms_patterns.py` - KMS key management and encryption

**Bootstrap Services:**
- `organizations_bootstrap.py` - Organizations and OU setup
- `identity_center_bootstrap.py` - IAM Identity Center setup
- `security_services_bootstrap.py` - Security services setup
- `bootstrap_orchestrator.py` - Complete environment orchestration

**Example Scripts:**
- See `examples/bootstrap_quickstart.py` (to be created)
- See `examples/bootstrap_custom.py` (to be created)

---

## Testing

**Pre-requisites:**
- AWS Organizations must NOT be already enabled (or test in fresh account)
- IAM Identity Center must NOT be already enabled
- Admin credentials in management account

**Test Scenarios:**
1. **Quickstart Bootstrap** - Full AWS recommended setup
2. **Minimal Bootstrap** - Basic setup for getting started
3. **Custom Bootstrap** - User-defined configuration
4. **Re-run Idempotency** - Verify safe to re-run
5. **Error Handling** - Test with invalid configurations

**Test Commands:**
```bash
# Run quickstart bootstrap
python examples/bootstrap_quickstart.py --admin-account 999888777666

# Run minimal bootstrap
python examples/bootstrap_minimal.py

# Verify bootstrap
python examples/verify_bootstrap.py
```

---

## Summary

CARL now provides **complete AWS environment automation** from scratch:

✅ **5 Critical Gaps Fixed:**
1. VPC Endpoints/PrivateLink patterns (security gap closed)
2. KMS key management patterns (encryption strategy defined)
3. Organizations bootstrap automation (OU structure + SCPs)
4. IAM Identity Center automation (SSO + permission sets)
5. Security services automation (delegated admin setup)

**Total New Patterns: 43+** (7 new patterns added to existing 36)

**What You Can Now Do:**
- Bootstrap a production-ready AWS environment in minutes
- Set up SOC 2-compliant Organizations structure
- Configure IAM Identity Center with best practices
- Enable security services organization-wide
- Deploy VPC endpoints for private connectivity
- Implement KMS encryption at rest strategy

**All Through Code** - Repeatable, testable, auditable
