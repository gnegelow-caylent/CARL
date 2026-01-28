# CARL Infrastructure Blueprints

**Status:** 6 Production-Ready Blueprints | January 2026

This document provides complete reference for all CARL infrastructure blueprints. All blueprints feature **smart generation** - CARL scans your AWS environment and only creates resources that don't already exist.

---

## 🎯 Blueprint Overview

| Blueprint | Category | Complexity | Smart Generation | Status |
|-----------|----------|------------|------------------|--------|
| `security/basic-stack` | Security | Basic | ✅ Yes | ✅ Production |
| `security/soc2-stack` | Security | Advanced | ✅ Yes | ✅ Production |
| `networking/basic-vpc` | Networking | Basic | ✅ Yes | ✅ Production |
| `networking/standard-vpc` | Networking | Standard | ✅ Yes | ✅ Production |
| `networking/enterprise-vpc` | Networking | Advanced | ✅ Yes | ✅ Production |
| `storage/compliant-s3` | Storage | Basic | 🔄 Partial | ✅ Production |

---

## 🔐 Security Blueprints

### `security/basic-stack`

**Purpose:** Essential security services for development/test environments

**What It Creates (if missing):**
- GuardDuty detector with basic configuration
- Security Hub with AWS Foundational Security standard
- CloudTrail with 1-year log retention
- Multi-region trail with log file validation

**Smart Detection:**
- ✅ Detects existing GuardDuty detector
- ✅ Detects existing Security Hub
- ✅ Detects existing CloudTrail trail

**SOC 2 Controls Addressed:**
- CC6.1 - Threat detection (GuardDuty)
- CC6.6 - Security monitoring (Security Hub)
- CC7.2 - Audit logging (CloudTrail)

**Cost Estimate:**
- GuardDuty: $4-8/month (depends on volume)
- Security Hub: $0.001/check/month (~$5-10/month)
- CloudTrail: $2/100,000 events (~$5/month)
- **Total: ~$15-25/month**

**Usage:**
```
/carl build security/basic-stack
```

**Configuration Options:**
- `name` - Stack name (default: "basic")
- `environment` - Environment tag (default: "dev")

**Generated Resources:**
- `aws_guardduty_detector.main` (if missing)
- `aws_securityhub_account.main` (if missing)
- `aws_securityhub_standards_subscription.aws_foundational` (if missing)
- `aws_cloudtrail.main` (if missing)
- `aws_s3_bucket.cloudtrail` (if creating trail)

**Example Output:**
```
Blueprint: security/basic-stack

🔍 Environment Scan:
  ✗ GuardDuty not found (will create)
  ✓ Security Hub already enabled (using existing)
  ✗ CloudTrail not found (will create)

🔐 Compliance Notes:
  • GuardDuty threat detection enabled
  • Using existing Security Hub
  • Multi-region CloudTrail with 1-year retention
  • SMART GENERATION: Only creates missing resources

📋 Deployment Steps:
  1. Review generated code
  2. terraform init
  3. terraform plan
  4. terraform apply
  5. Review Security Hub findings after 24 hours
```

**When to Use:**
- Development/test environments
- Cost-sensitive deployments
- Quick security baseline
- Non-production workloads

**Upgrade Path:** Use `security/soc2-stack` for production/compliance requirements

---

### `security/soc2-stack`

**Purpose:** Comprehensive SOC 2 compliant security stack for production environments

**What It Creates (if missing):**
- GuardDuty detector with all data sources enabled
  - S3 protection
  - Kubernetes audit logs
  - Malware protection (EBS scanning)
- Security Hub with CIS Benchmark + AWS Foundational standards
- AWS Config with continuous configuration monitoring
- CloudTrail with 7-year log retention (SOC 2 requirement)
- KMS key for log encryption with automatic rotation
- SNS topic for security alerts
- CloudWatch log group for security events

**Smart Detection:**
- ✅ Detects existing GuardDuty detector
- ✅ Detects existing Security Hub
- ✅ Detects existing AWS Config recorder
- ✅ Detects existing CloudTrail trail

**SOC 2 Controls Addressed:**
- CC6.1 - Threat detection and response
- CC6.5 - Encryption at rest
- CC6.6 - Security monitoring
- CC7.2 - Audit logging and monitoring
- CC8.1 - Configuration management
- A1.2 - Data retention (7 years)

**Cost Estimate:**
- GuardDuty: $4-15/month (with all protections)
- Security Hub: $0.001/check/month (~$10-20/month with 2 standards)
- AWS Config: $2/active rule + $0.003/config item (~$10-20/month)
- CloudTrail: $2/100,000 events (~$10/month)
- KMS: $1/month + $0.03/10,000 requests
- SNS: Free tier (first 1,000 notifications free)
- **Total: ~$40-70/month**

**Usage:**
```
/carl build security/soc2-stack
```

**Configuration Options:**
- `name` - Stack name (default: "main")
- `environment` - Environment tag (default: "prod")
- `alert_email` - Email for security alerts (default: "security@example.com")

**Generated Resources:**
- `aws_guardduty_detector.main` (if missing - with all data sources)
- `aws_securityhub_account.main` (if missing)
- `aws_securityhub_standards_subscription.cis` (if missing)
- `aws_securityhub_standards_subscription.aws_foundational` (if missing)
- `aws_config_configuration_recorder.main` (if missing)
- `aws_config_delivery_channel.main` (if missing)
- `aws_cloudtrail.main` (if missing - with insights)
- `aws_kms_key.logs` (always created)
- `aws_sns_topic.security_alerts` (always created)
- `aws_cloudwatch_log_group.security` (always created)

**Example Output:**
```
Blueprint: security/soc2-stack

🔍 Environment Scan:
  ✗ GuardDuty not found (will create with all data sources)
  ✓ Security Hub already enabled (using existing)
  ✗ AWS Config not configured (will create recorder)
  ✓ CloudTrail already active (using existing: org-trail)

🔐 Compliance Notes:
  • GuardDuty threat detection enabled (CC6.1, CC7.2)
  • Using existing Security Hub (CC6.1)
  • AWS Config continuous monitoring created (CC7.2, CC8.1)
  • Using existing CloudTrail: org-trail (CC7.2, A1.2)
  • KMS encryption for logs (CC6.5)
  • SNS alerts for security events (CC7.2)
  • SMART GENERATION: Only creates missing resources

📋 Deployment Steps:
  1. Review generated code - only missing resources will be created
  2. Update alert_email if needed
  3. terraform init
  4. terraform plan (verify correct resources)
  5. terraform apply
  6. Check email for SNS subscription confirmation
  7. Review Security Hub findings after 24 hours
```

**When to Use:**
- Production environments
- SOC 2 compliance requirements
- Enterprise security posture
- Organizations requiring audit trails
- Long-term data retention needs

**Audit Readiness:**
- 7-year log retention (exceeds SOC 2 requirement)
- All controls documented with mappings
- Evidence collection automated
- Configuration monitoring enabled

---

## 🌐 Networking Blueprints

### `networking/basic-vpc`

**Purpose:** Cost-optimized 2-AZ VPC with compliance features

**What It Creates (if VPC doesn't exist):**
- VPC with custom CIDR
- Public subnets (2 AZs)
- Private subnets (2 AZs)
- Internet Gateway
- Single NAT Gateway (cost-optimized)
- Route tables for public/private
- VPC Flow Logs (90-day retention)
- Hardened default security group (deny all)

**Smart Detection:**
- ✅ Detects existing VPC by name tag
- ✅ If found: Returns data source only
- ✅ If not found: Creates full stack

**SOC 2 Controls Addressed:**
- CC6.6 - Network segmentation
- CC7.2 - Flow logs for audit

**Cost Estimate:**
- VPC: Free
- NAT Gateway: $32/month (~$0.045/hour)
- NAT Gateway data: $0.045/GB
- VPC Flow Logs: $0.50/GB ingested (~$5-10/month)
- **Total: ~$40-50/month**

**Usage:**
```
/carl build networking/basic-vpc
```

**Configuration Options:**
- `name` - VPC name (default: "main")
- `cidr` - VPC CIDR block (default: "10.0.0.0/16")
- `azs` - Number of AZs (default: 2)
- `environment` - Environment tag (default: "dev")

**Subnet Layout:**
- Public subnets: `10.0.0.0/24`, `10.0.1.0/24`
- Private subnets: `10.0.10.0/24`, `10.0.11.0/24`

**Generated Resources:**
- `aws_vpc.main` (if VPC doesn't exist)
- `aws_internet_gateway.main` (if VPC doesn't exist)
- `aws_subnet.public[*]` (if VPC doesn't exist)
- `aws_subnet.private[*]` (if VPC doesn't exist)
- `aws_nat_gateway.main` (if VPC doesn't exist)
- `aws_eip.nat` (if VPC doesn't exist)
- `aws_route_table.public` (if VPC doesn't exist)
- `aws_route_table.private` (if VPC doesn't exist)
- `aws_flow_log.main` (if VPC doesn't exist)
- `aws_default_security_group.default` (if VPC doesn't exist)

**Example Output (VPC doesn't exist):**
```
Blueprint: networking/basic-vpc

🔍 Environment Scan:
  ✗ No existing VPC found with name "main-vpc"

✅ Will create new compliant VPC with:
  • Public and private subnets across 2 AZs
  • Single NAT Gateway (cost-optimized)
  • VPC Flow Logs for audit compliance
  • Hardened default security group

📋 Deployment Steps:
  1. Review CIDR block configuration
  2. terraform init
  3. terraform plan
  4. terraform apply
  5. Note subnet IDs for workload deployment
```

**Example Output (VPC exists):**
```
Blueprint: networking/basic-vpc

🔍 Environment Scan:
  ✓ Found existing VPC: vpc-abc123 (10.0.0.0/16)

⚠️ Using existing VPC. Subnets and networking resources are NOT managed.

📋 Deployment Steps:
  1. Review existing VPC configuration
  2. terraform init
  3. terraform plan (data sources only)
  4. terraform apply
  5. Use existing subnet IDs for workloads
```

**When to Use:**
- Development/test environments
- Cost-sensitive deployments
- Single-region workloads
- Non-critical applications

**Upgrade Path:** Use `networking/standard-vpc` for HA or `networking/enterprise-vpc` for multi-region

---

### `networking/standard-vpc`

**Purpose:** High-availability 3-AZ VPC with WAF-ready setup

**What It Creates (if VPC doesn't exist):**
- VPC with custom CIDR
- Public subnets (3 AZs)
- Private subnets (3 AZs)
- Database subnets (3 AZs)
- Internet Gateway
- NAT Gateways in each AZ (HA)
- Route tables for each tier
- VPC Flow Logs (90-day retention)
- Hardened default security group

**Smart Detection:**
- ✅ Same as basic-vpc

**Cost Estimate:**
- NAT Gateways: $96/month (3 x $32/month)
- NAT Gateway data: $0.045/GB
- VPC Flow Logs: $0.50/GB (~$10-20/month)
- **Total: ~$110-130/month**

**Usage:**
```
/carl build networking/standard-vpc
```

**Configuration Options:**
- `name` - VPC name (default: "main")
- `cidr` - VPC CIDR block (default: "10.0.0.0/16")
- `environment` - Environment tag (default: "prod")

**Subnet Layout:**
- Public: `10.0.0.0/24`, `10.0.1.0/24`, `10.0.2.0/24`
- Private: `10.0.10.0/24`, `10.0.11.0/24`, `10.0.12.0/24`
- Database: `10.0.20.0/24`, `10.0.21.0/24`, `10.0.22.0/24`

**When to Use:**
- Production workloads
- HA requirements
- Multi-tier applications
- ALB/NLB deployments

---

### `networking/enterprise-vpc`

**Purpose:** Multi-region ready VPC with Transit Gateway support

**What It Creates:**
- Same as standard-vpc, plus:
- VPN Gateway (optional)
- Transit Gateway attachments (optional)
- Route 53 Resolver endpoints
- Enhanced flow log analysis

**Cost Estimate:**
- Base VPC: ~$110-130/month (from standard)
- VPN Gateway: $36/month (if enabled)
- Transit Gateway attachments: $36/month per attachment
- **Total: ~$150-200/month**

**When to Use:**
- Multi-region architectures
- Hybrid cloud connectivity
- Complex networking requirements
- Enterprise organizations

---

## 💾 Storage Blueprints

### `storage/compliant-s3`

**Purpose:** SOC 2 compliant S3 bucket with all security features

**What It Creates:**
- S3 bucket with versioning
- KMS encryption with key rotation
- Public access block (all)
- Access logging bucket
- Lifecycle policies (archive old versions)
- SSL requirement policy

**Smart Detection:**
- 🔄 Partial (not fully implemented)

**SOC 2 Controls Addressed:**
- A1.2 - Versioning for data protection
- CC6.5 - Encryption at rest (KMS)
- CC6.6 - Public access prevention
- CC6.7 - SSL/TLS requirements
- CC7.2 - Access logging

**Cost Estimate:**
- S3 storage: $0.023/GB/month
- KMS: $1/month + $0.03/10,000 requests
- Lifecycle transitions: Included
- **Total: Varies by data volume, ~$5-50/month typical**

**Usage:**
```
/carl build storage/compliant-s3
```

**Configuration Options:**
- `name` - Bucket name prefix (default: "data")

**Generated Resources:**
- `aws_s3_bucket.main`
- `aws_s3_bucket_versioning.main`
- `aws_s3_bucket_server_side_encryption_configuration.main`
- `aws_s3_bucket_public_access_block.main`
- `aws_s3_bucket.logs` (for access logs)
- `aws_s3_bucket_logging.main`
- `aws_s3_bucket_lifecycle_configuration.main`
- `aws_s3_bucket_policy.require_ssl`

**Lifecycle Policy:**
- Current versions: Immediate
- 30 days: STANDARD_IA
- 90 days: GLACIER
- 365 days: Delete noncurrent versions

**When to Use:**
- All production data storage
- Compliance-sensitive data
- Audit logs and archives
- Application data requiring retention

---

## 🔮 Coming Soon

### Compute Blueprints

| Blueprint | Status | Target |
|-----------|--------|--------|
| `compute/basic-ec2` | 📋 Planned | Q1 2026 |
| `compute/ecs-fargate` | 📋 Planned | Q1 2026 |
| `compute/eks-cluster` | 📋 Planned | Q2 2026 |

### Database Blueprints

| Blueprint | Status | Target |
|-----------|--------|--------|
| `database/rds-single` | 📋 Planned | Q2 2026 |
| `database/rds-multi-az` | 📋 Planned | Q2 2026 |
| `database/aurora-serverless` | 📋 Planned | Q2 2026 |

### Serverless Blueprints

| Blueprint | Status | Target |
|-----------|--------|--------|
| `serverless/api` | 📋 Planned | Q2 2026 |

---

## 📋 Blueprint Selection Guide

### By Environment Type

**Development/Test:**
- `security/basic-stack`
- `networking/basic-vpc`
- `storage/compliant-s3`

**Production (Standard):**
- `security/soc2-stack`
- `networking/standard-vpc`
- `storage/compliant-s3`

**Production (Enterprise):**
- `security/soc2-stack`
- `networking/enterprise-vpc`
- `storage/compliant-s3`

### By Compliance Requirement

**SOC 2 Type II:**
- `security/soc2-stack` ✅ Required
- `networking/standard-vpc` or `enterprise-vpc`
- `storage/compliant-s3` ✅ Required

**Basic Security Baseline:**
- `security/basic-stack`
- `networking/basic-vpc`
- `storage/compliant-s3`

### By Cost Sensitivity

**Cost-Optimized (<$100/month):**
- `security/basic-stack` (~$25/month)
- `networking/basic-vpc` (~$50/month)
- `storage/compliant-s3` (varies)

**Standard Production (~$150/month):**
- `security/soc2-stack` (~$60/month)
- `networking/standard-vpc` (~$120/month)
- `storage/compliant-s3` (varies)

**Enterprise (>$200/month):**
- `security/soc2-stack` (~$60/month)
- `networking/enterprise-vpc` (~$180/month)
- `storage/compliant-s3` (varies)

---

## 🛠️ Common Workflows

### New AWS Account Setup

**Step 1: Security baseline**
```
/carl build security/soc2-stack
```

**Step 2: Network foundation**
```
/carl build networking/standard-vpc
```

**Step 3: Storage**
```
/carl build storage/compliant-s3
```

### Existing Account Audit

**CARL will detect and report:**
```
/carl build security/soc2-stack

🔍 Environment Scan:
  ✓ GuardDuty already exists
  ✓ Security Hub already enabled
  ✗ AWS Config not configured
  ✓ CloudTrail already active

✅ Only missing: AWS Config
💰 Cost to add: ~$15/month
```

### Cost Optimization Review

**Check what you're paying for:**
```
/carl build networking/basic-vpc

✓ Found existing VPC with 3 NAT Gateways

💡 Cost optimization opportunity:
   Current: $96/month (3 NAT Gateways)
   Possible: $32/month (1 NAT Gateway)
   Savings: $64/month (~$768/year)

   Trade-off: Reduced availability (single point of failure)
```

---

## 📚 Related Documentation

- **[SMART_GENERATION.md](./SMART_GENERATION.md)** - How smart generation works
- **[FEATURES.md](./FEATURES.md)** - All CARL features
- **[SLACK_COMMANDS.md](./SLACK_COMMANDS.md)** - Command reference
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Technical architecture

---

## 💡 Tips & Best Practices

### Naming Conventions

- Use environment prefix: `dev-`, `staging-`, `prod-`
- Keep names short and descriptive
- Use consistent naming across blueprints
- Example: `prod-main` for VPC, `prod-main` for security stack

### Deployment Order

1. **Security first** - Always deploy security stack before workloads
2. **Network second** - VPC before any compute/database
3. **Storage as needed** - S3 buckets can be created anytime
4. **Workloads last** - Deploy applications after foundation

### Cost Management

- Start with basic blueprints for dev/test
- Use standard blueprints for production
- Monitor CloudWatch costs (Flow Logs can add up)
- Review NAT Gateway usage monthly

### Compliance

- Always use SOC 2 stack for production
- Review compliance notes in generated code
- Keep evidence for auditors (CARL automates this)
- Update blueprints quarterly as requirements change

---

*Last Updated: January 28, 2026*
