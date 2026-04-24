---
name: aws-architecture-advisor
description: Get AWS architecture recommendations with cost estimates and compliance mappings. Compares options with pros/cons, pricing, and SOC 2/HIPAA control coverage. Use when designing AWS infrastructure or evaluating architecture decisions.
---

# AWS Architecture Advisor Skill

Provide AWS architecture recommendations that balance cost, compliance, operational overhead, and best practices. Every recommendation includes pricing estimates (as reference) and compliance control mappings.

## Core Principles

1. **Always Include Cost** — Compare options with cost tradeoffs (reference pricing, may be outdated)
2. **Map to Compliance Controls** — SOC 2 Trust Services Criteria + HIPAA Security Rule
3. **Compare 2-3 Options** — Simpler/cheaper vs more capable/costlier
4. **Be Specific** — Actual service names, instance types, configurations

---

## VPC Design Patterns

### CIDR Planning

| Pattern | IPs | Best For | SOC 2 |
|---------|-----|----------|-------|
| Small (/24) | 256 | Dev/sandbox, single app | CC6.6 |
| Medium (/20) | 4,096 | Standard production, Fargate | CC6.6 |
| Large (/16) | 65,536 | EKS clusters, enterprise | CC6.6 |
| IPAM-Managed | Varies | Multi-account (10+ VPCs) | CC6.6, CC7.2 |

**Decision Logic:**
- EKS with EC2 nodes → Large (/16) or custom CNI
- Expected hosts < 200 → Small (/24)
- Expected hosts 200-3000 → Medium (/20)
- Expected hosts > 3000 → Large (/16)
- Multi-account with 10+ VPCs → Consider IPAM

**Common Mistakes:**
- Using 10.0.0.0/16 for everything (causes overlaps)
- Undersizing for EKS (IP exhaustion)
- Forgetting AWS reserves 5 IPs per subnet

---

### Subnet Tiers

| Pattern | Tiers | Best For | SOC 2 |
|---------|-------|----------|-------|
| Two-Tier | Public + Private | Dev, serverless, simple apps | CC6.6 |
| Three-Tier | Public + App + Data | Production, compliance (SOC 2, PCI) | CC6.6, CC6.7 |
| Four-Tier | + Management/TGW | Enterprise, Transit Gateway | CC6.6, CC6.7, CC7.2 |
| Five-Tier | + Firewall | Network Firewall, GWLB | CC6.6, CC6.7, CC6.8, CC7.2 |

**Decision Logic:**
- Compliance requirements (SOC 2, PCI, HIPAA) → Minimum three-tier
- Transit Gateway → Four-tier (dedicated TGW subnets)
- Traffic inspection (Network Firewall) → Five-tier
- Serverless only → Two-tier

**Common Mistakes:**
- Putting databases in app subnets
- TGW attachment in app subnets (routing issues)
- Same route table for all private subnets

---

### Availability Zones

| Pattern | AZs | Cost Impact | SOC 2 |
|---------|-----|-------------|-------|
| Single AZ | 1 | Lowest | — |
| Two AZs | 2 | ~$65/mo (2 NAT GWs) | A1.1, A1.2 |
| Three AZs | 3 | ~$97/mo (3 NAT GWs) | A1.1, A1.2 |

**Reference Costs:**
- NAT Gateway: ~$32/mo each + $0.045/GB
- Cross-AZ data transfer: ~$0.01/GB each way

**Decision Logic:**
- Development → Single AZ (cost savings)
- Production 99.9% SLA → 2 AZs
- Production 99.99% SLA → 3 AZs
- EKS → 3 AZs recommended
- Aurora Multi-AZ Cluster → 3 AZs

**Common Mistakes:**
- Using 3 AZs in region with only 2 (deployment fails)
- Single AZ for production databases
- Not testing AZ failover procedures

---

### VPC Endpoints

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| Gateway Only (S3 + DynamoDB) | FREE | All workloads | CC6.6, CC6.7 |
| Essential Interface | ~$20-90/mo | Private subnets, containers | CC6.6, CC6.7 |
| Comprehensive Interface | ~$100-300/mo | Air-gapped, zero internet | CC6.6, CC6.7, CC6.8 |
| Centralized (via TGW) | ~$50-200/mo | 10+ VPCs | CC6.6, CC6.7 |

**Reference Costs:**
- Gateway endpoints (S3, DynamoDB): FREE
- Interface endpoints: ~$7.20/mo per AZ + $0.01/GB

**Essential Endpoints for Containers:**
- ecr.api, ecr.dkr (container images)
- logs (CloudWatch Logs)
- ssm, ssmmessages, ec2messages (ECS Exec, SSM)
- secretsmanager (secrets)
- s3 (gateway - free)

**Decision Logic:**
- ALWAYS deploy Gateway Endpoints (free savings)
- No NAT Gateway → Interface endpoints required
- Containers → Essential set (ECR, Logs, SSM)
- Air-gapped/compliance → Comprehensive set
- 5+ VPCs → Consider centralized endpoints

**Common Mistakes:**
- Forgetting Gateway Endpoints (free savings missed)
- Not enabling Private DNS for interface endpoints
- Forgetting endpoint security groups

---

### VPC Flow Logs

| Destination | Cost (ref) | Best For | SOC 2 |
|-------------|------------|----------|-------|
| CloudWatch Logs | ~$0.50/GB | Real-time analysis, < 100GB/mo | CC6.6, CC7.2 |
| S3 | ~$0.25/GB | High volume, long retention | CC6.6, CC7.2 |
| Both (Hybrid) | Combined | Real-time + compliance | CC6.6, CC7.2 |

**Decision Logic:**
- Traffic < 100GB/month → CloudWatch is fine
- Traffic 100GB-1TB/month → S3 primary
- Traffic > 1TB/month → S3 required (CloudWatch too expensive)
- Need real-time → CloudWatch or hybrid
- 1+ year retention → S3 with Glacier lifecycle

**Best Practices:**
- Use custom format (reduces volume ~40%)
- Use Parquet format for S3 (50% smaller)
- Set up Athena for queries
- Minimum 90 days retention for SOC 2

**HIPAA:** 164.312(b) - Audit Controls

---

## Database Patterns

### RDS Deployment Strategy

| Pattern | Cost (ref) | Availability | SOC 2 |
|---------|------------|--------------|-------|
| Single-AZ Dev | ~$15-100/mo | None | CC6.1, A1.2 |
| Multi-AZ Production | ~$70-500/mo | 99.95% SLA | CC6.1, A1.2, A1.3 |
| Multi-AZ + Read Replicas | ~$400-2000/mo | + Read scaling | CC6.1, A1.2, A1.3 |
| Multi-Region | ~$1500-5000/mo | DR, ~15min RTO | A1.2, A1.3 |

**Reference Costs:**
- db.t3.micro: ~$15/mo (Single-AZ)
- db.t3.small Multi-AZ: ~$60/mo
- db.m5.large Multi-AZ: ~$280/mo
- Read replica: Same as primary
- Cross-region replication: ~$0.02/GB

**Decision Logic:**
- Development/test → Single-AZ
- Production → Multi-AZ (automatic failover)
- Read-heavy (reporting) → Add Read Replicas
- Geographic DR required → Multi-Region

**RDS Security Checklist:**
- `storage_encrypted = true` (SOC 2 C1.1, HIPAA 164.312(a)(2)(iv))
- `publicly_accessible = false` (SOC 2 CC6.1, HIPAA 164.312(a)(1))
- `multi_az = true` for production (SOC 2 A1.1)
- `backup_retention_period >= 7` (SOC 2 A1.3)
- `iam_database_authentication_enabled = true` (SOC 2 CC6.1)
- `deletion_protection = true` (SOC 2 A1.3)

**HIPAA:** 164.312(a)(2)(iv) - Encryption, 164.312(c)(1) - Integrity

---

### Database Selection

| Database | Cost (ref) | Best For | SOC 2 |
|----------|------------|----------|-------|
| RDS PostgreSQL | ~$50-200/mo | Traditional SQL, joins | CC6.7, A1.1, A1.3 |
| Aurora Serverless v2 | ~$43/mo min | Variable workloads | CC6.7, A1.1, A1.3 |
| DynamoDB On-Demand | Pay per request | Key-value, unpredictable traffic | CC6.7, A1.1 |
| ElastiCache | ~$25-200/mo | Caching, sessions | CC6.7 |

**Reference Costs:**
- Aurora Serverless v2: $0.12/ACU-hour (min 0.5 ACU = ~$43/mo)
- DynamoDB: $1.25/million writes, $0.25/million reads
- ElastiCache: ~$0.034/hour per node (cache.t3.micro)

**Decision Logic:**
- Need SQL joins → RDS or Aurora
- Variable workload, uncertain capacity → Aurora Serverless v2
- Key-value access patterns → DynamoDB
- Need caching → ElastiCache (Redis or Memcached)
- HIPAA workload → Ensure encryption + eligible service

---

## Compute Patterns

### Compute Selection

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| Lambda | ~$0.20/M requests | Event-driven, APIs, < 15min | CC6.1, CC7.2 |
| Fargate | ~$0.04/vCPU-hr | Containers, no server mgmt | CC6.1, CC7.2 |
| ECS on EC2 | EC2 cost | Cost optimization, GPU, high util | CC6.1, CC7.2 |
| EC2 | ~$30/mo (t3.medium) | Full control, special needs | CC6.1, CC7.2 |

**Reference Costs:**
- Lambda: $0.20/M invocations + $0.0000166667/GB-second
- Fargate: $0.04/vCPU-hour + $0.004/GB-hour
- 1 Fargate task (1 vCPU, 2GB, 24/7): ~$45/mo
- t3.medium On-Demand: ~$30/mo, Reserved: ~$18/mo

**Decision Logic:**
- Event-driven, short duration → Lambda
- Containers, no server management → Fargate
- High utilization (>70%), cost optimize → ECS on EC2
- Full control, GPU, special requirements → EC2

---

### Lambda Security

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| Public Lambda | ~$5-100/mo | Simple APIs, no VPC resources | CC6.1, CC7.2 |
| VPC Lambda | ~$20-150/mo | RDS/ElastiCache access | CC6.1, CC6.6, CC6.7, CC7.2 |
| VPC + Reserved Concurrency | ~$30-200/mo | Production, prevent exhaustion | CC6.1, CC6.6, CC6.7, CC7.2 |

**Decision Logic:**
- Need VPC resources (RDS, ElastiCache) → VPC Lambda
- Production workloads → Reserved concurrency
- Latency-sensitive → Provisioned concurrency

**Lambda Security Checklist:**
- Least privilege execution role
- KMS encryption for environment variables
- VPC placement for sensitive workloads
- Reserved concurrency to prevent exhaustion
- Dead Letter Queue for failed invocations

**VPC Lambda Endpoints Needed:**
- s3 (gateway - free)
- secretsmanager (~$7.20/mo)
- logs (~$7.20/mo)

**HIPAA:** 164.312(a)(1) - Access Control, 164.312(b) - Audit

---

### Container Architecture

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| ALB + Fargate | ~$30-150/mo | Containers, serverless | CC6.1, A1.2, CC7.2 |
| ALB + EC2 ASG | ~$76-200/mo | High utilization, control | CC6.1, A1.2, CC7.2 |
| ALB + Lambda | ~$20-80/mo | Very high traffic APIs | CC6.1, CC7.2 |

**Reference Costs:**
- ALB: ~$16/mo base + LCUs
- Fargate task (0.25 vCPU, 0.5GB): ~$10/mo per task

**Decision Logic:**
- Containerized app → ALB + Fargate (default)
- High utilization (>70%), need control → ALB + EC2
- Very high traffic API (>10M req/mo) → ALB + Lambda

**Common Mistakes:**
- Using ALB for low-traffic APIs (<5M req - API Gateway cheaper)
- Using EC2 when Fargate simpler at low utilization
- Forgetting WAF for public-facing applications

---

## Security Tooling Patterns

### Security Hub

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| Per-Account | ~$5-30/mo | Single account, getting started | CC7.2, CC7.3 |
| Centralized (Delegated Admin) | ~$20-200/mo | Multi-account, SOC 2 | CC7.2, CC7.3 |
| + Custom Insights & Automation | ~$50-500/mo | Mature security ops | CC7.1, CC7.2, CC7.3 |

**Reference Costs:**
- Finding ingestion: ~$0.00003/finding
- Security checks: ~$0.0010/check

**Decision Logic:**
- Multi-account → Centralized with delegated admin
- SOC 2 compliance → Enable AWS Foundational Security Best Practices
- Mature ops → Add custom insights and auto-remediation

**Standards to Enable:**
- AWS Foundational Security Best Practices: ALWAYS
- CIS AWS Foundations Benchmark: Recommended
- PCI-DSS: If processing payments

**Common Mistakes:**
- Using management account as admin (use delegated admin)
- Not enabling AWS Foundational Security Best Practices
- Ignoring findings (creates noise fatigue)

---

### GuardDuty

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| All Data Sources | ~$10-100/mo | All accounts (recommended) | CC6.8, CC7.2, CC7.3 |
| + Malware Protection | ~$10-200/mo | EC2 workloads | CC6.8, CC7.2, CC7.3 |
| Organization-Wide | ~$50-500/mo | Multi-account | CC6.8, CC7.2, CC7.3 |

**Reference Costs:**
- CloudTrail events: ~$4/million events
- VPC Flow Logs: ~$1/GB first 500GB
- S3 data events: ~$0.80/million events
- Malware scanning: ~$0.05/GB scanned

**Decision Logic:**
- Enable GuardDuty in ALL accounts, ALL regions
- Use Organizations integration + delegated admin
- Enable all data sources (CloudTrail, VPC Flow, DNS, S3)
- Enable EKS audit logs if using EKS

**HIPAA:** 164.312(b) - Audit Controls

---

## Logging Patterns

### Log Aggregation

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| S3 Central Bucket | ~$20-500/mo | Multi-account, long retention | CC7.2, CC7.3 |
| CloudWatch Cross-Account | ~$50-2000/mo | Real-time, small volume | CC7.2, CC7.3 |
| Hybrid (CloudWatch + S3) | ~$50-1000/mo | Real-time + compliance | CC7.2, CC7.3 |
| OpenSearch | ~$200-2000/mo | Complex analysis, Kibana | CC7.2, CC7.3 |

**Reference Costs:**
- S3 Standard: ~$0.023/GB
- S3 Glacier: ~$0.004/GB
- CloudWatch ingestion: ~$0.50/GB
- CloudWatch storage: ~$0.03/GB/month

**Decision Logic:**
- Log volume < 50GB/month → CloudWatch
- Log volume 50-500GB/month → S3 primary, CloudWatch for select logs
- Log volume > 500GB/month → S3 required
- Complex analysis needed → OpenSearch
- Have SIEM → S3 delivery, SIEM does analysis

**Log Types to Centralize:**
- CloudTrail (required) - via Organization trail
- VPC Flow Logs
- Application logs
- Load balancer access logs
- CloudFront access logs
- WAF logs

**HIPAA:** 164.312(b) - Audit Controls, 164.312(c)(1) - Integrity

---

### CloudTrail

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| Organization Trail | FREE (mgmt events) | Multi-account | CC6.1, CC7.2 |
| + Data Events | ~$10-1000/mo | S3 object-level logging | CC6.1, CC7.2 |
| + Insights | ~$0.35/100K events | Anomaly detection | CC6.1, CC7.1, CC7.2 |

**Reference Costs:**
- First trail (management events): FREE
- S3 storage: ~$0.023/GB
- Data events: ~$0.10/100K events
- Insights: ~$0.35/100K events analyzed

**CloudTrail Checklist:**
- `is_multi_region_trail = true`
- `include_global_service_events = true`
- `enable_log_file_validation = true`
- KMS encryption
- CloudWatch Logs integration

**Decision Logic:**
- Multi-account → Organization trail
- Need S3 object-level audit → Enable data events (select buckets)
- Want anomaly detection → Enable Insights

---

## Encryption Patterns

### Encryption Strategy

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| AWS Managed Keys | FREE | Simple, low-risk | CC6.7, C1.1 |
| Customer Managed Keys (CMK) | ~$1/key/mo | Audit, key control | CC6.7, C1.1 |
| CloudHSM | ~$1,100/mo | FIPS 140-2 Level 3 | CC6.7, C1.1 |

**Recommended CMK Strategy (5 keys = ~$5/mo):**
1. `cmk-data` - S3, EBS, RDS
2. `cmk-secrets` - Secrets Manager, SSM
3. `cmk-logs` - CloudWatch, CloudTrail
4. `cmk-compute` - Lambda env vars, ECS secrets
5. `cmk-backup` - AWS Backup

**KMS Checklist:**
- `enable_key_rotation = true`
- `deletion_window_in_days >= 7`
- Least privilege key policy
- Descriptive aliases

**HIPAA:** 164.312(a)(2)(iv) - Encryption, 164.312(c)(1) - Integrity

---

### Identity & Access

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| IAM Users | FREE | Service accounts only | CC6.1 |
| IAM Identity Center | FREE | Human users, SSO | CC6.1, CC6.2 |
| Cognito | ~$0.0055/MAU | Customer-facing apps | CC6.1 |

**Recommended: IAM Identity Center + Role-Based Access**
- IAM Identity Center for all human access
- Permission Sets mapped to job functions
- No long-lived IAM user credentials
- IAM Roles for service-to-service

**Permission Sets:**
- Admin: Full access (break-glass only)
- Developer: Dev account full, prod read-only
- Operator: Specific services, no IAM changes
- Auditor: Read-only everywhere

**HIPAA:** 164.312(a)(1) - Access Control, 164.312(d) - Authentication

---

## Response Format

When providing architecture advice:

```markdown
## Architecture Recommendation: [Topic]

### Requirements Understood
- [Bullet list of what user asked for]

### Option 1: [Name] (Recommended)
**Monthly Cost (ref)**: $X-Y
**Architecture**: [Brief description]

**Pros**:
- [List]

**Cons**:
- [List]

**Compliance**:
- SOC 2: [Controls covered]
- HIPAA: [Sections covered, if applicable]

### Option 2: [Name]
[Same format]

### Comparison
| Factor | Option 1 | Option 2 |
|--------|----------|----------|
| Cost (ref) | $X | $Y |
| Complexity | Low/Med/High | Low/Med/High |
| Compliance | Full/Partial | Full/Partial |

### Recommendation
[1-2 sentences on which option and why]

### Next Steps
1. [Actionable items]
```

---

## Compliance Quick Reference

### SOC 2 Control Families
- **CC6**: Logical and Physical Access Controls
- **CC7**: System Operations (monitoring, incident response)
- **A1**: Availability
- **C1**: Confidentiality

### HIPAA Security Rule (45 CFR 164.312)
- **164.312(a)(1)**: Access Control
- **164.312(a)(2)(iv)**: Encryption
- **164.312(b)**: Audit Controls
- **164.312(c)(1)**: Integrity
- **164.312(d)**: Authentication
- **164.312(e)(1)**: Transmission Security

---

## Pricing Disclaimer

All costs are **reference estimates** based on typical configurations. Actual costs vary by:
- Region
- Usage patterns
- Reserved capacity
- Current AWS pricing

Verify current pricing at [AWS Pricing](https://aws.amazon.com/pricing/).

---

## When to Use This Skill

- Greenfield architecture design
- Evaluating service alternatives
- Cost optimization reviews
- Compliance-driven architecture decisions
- Migration planning
