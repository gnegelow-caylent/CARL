# CARL Cost Estimates

## Overview

CARL is designed to be cost-effective while providing enterprise-grade compliance capabilities. This document provides detailed cost estimates for running CARL.

---

## Cost Summary

| Deployment | Monthly Cost |
|------------|--------------|
| **Single Account** | $75-200 |
| **5 Accounts** | $250-550 |
| **20 Accounts** | $900-2,100 |

---

## Cost Comparison: CARL vs Enterprise Tools

| Solution | Monthly Cost | Annual Cost |
|----------|-------------|-------------|
| **CARL (Single Account)** | $75-200 | $900-2,400 |
| **CARL (5 Accounts)** | $250-550 | $3,000-6,600 |
| Lacework | $500-2,000+ | $6,000-24,000+ |
| Prisma Cloud | $500-3,000+ | $6,000-36,000+ |
| Wiz | $1,000-5,000+ | $12,000-60,000+ |

**CARL provides 70-90% cost savings** compared to enterprise alternatives.

---

## Detailed Cost Breakdown

### CARL Core Services (Management Account)

| Service | Usage Assumption | Est. Monthly |
|---------|-----------------|--------------|
| **Bedrock (Claude Haiku)** | 1M input tokens, 500K output | $1-5 |
| **Bedrock (Claude Sonnet)** | 500K input tokens, 250K output | $25-75 |
| **Lambda** | 500K invocations, 256MB, 500ms avg | $5-15 |
| **DynamoDB** | Pay-per-request, 9 tables | $10-30 |
| **S3** | 10-50GB storage (evidence + reports) | $5-15 |
| **API Gateway** | 100K requests | $1-3 |
| **Secrets Manager** | 2 secrets (Slack tokens) | $1 |
| **EventBridge** | 1M events | Free (first 14M) |
| **SNS** | 10K notifications | Free (first 1M) |
| **KMS** | 1 CMK, 100K requests | $1-2 |
| **CloudWatch Logs** | 5GB ingestion | $3-5 |

**Core Services Subtotal: ~$55-150/month**

### Security Services (Per Account)

| Service | Usage Assumption | Est. Monthly |
|---------|-----------------|--------------|
| **Security Hub** | Standard tier | $15-40 |
| **AWS Config** | 500 resources, 30 rules | $10-25 |
| **GuardDuty** | Moderate event volume | $5-15 |
| **CloudTrail** | Management events | Free (first trail) |
| **IAM Access Analyzer** | N/A | Free |

**Security Services Subtotal: ~$30-80/month per account**

---

## Total Cost Estimates by Deployment Size

### Single Account Deployment

| Component | Low | High |
|-----------|-----|------|
| Core Services | $55 | $150 |
| Security Services | $30 | $80 |
| **Total** | **$85** | **$230** |
| **Typical** | **$75-200** | |

### Multi-Account (5 accounts)

| Component | Low | High |
|-----------|-----|------|
| Core Services | $55 | $150 |
| Security Services (x5) | $150 | $400 |
| **Total** | **$205** | **$550** |
| **Typical** | **$250-550** | |

### Multi-Account (20 accounts)

| Component | Low | High |
|-----------|-----|------|
| Core Services | $75 | $200 |
| Security Services (x20) | $600 | $1,600 |
| Cross-account EventBridge | $20 | $50 |
| **Total** | **$695** | **$1,850** |
| **Typical** | **$900-2,100** | |

---

## Cost Drivers by Feature

### AI/Bedrock Costs (30-50% of total)

The AI capabilities are the largest cost component:

| Use Case | Model | Approx. Cost |
|----------|-------|--------------|
| Simple queries, routing | Claude Haiku | $0.25/$1.25 per 1M tokens |
| Architecture recommendations | Claude Sonnet | $3/$15 per 1M tokens |
| Report generation | Claude Sonnet | $3/$15 per 1M tokens |
| Finding explanations | Claude Haiku | $0.25/$1.25 per 1M tokens |

**Optimization**: CARL uses Haiku for ~80% of queries (simple questions, routing, status) and Sonnet only for complex analysis (architecture, reports).

### DynamoDB Costs (15-20% of total)

All tables use **pay-per-request pricing** for cost optimization:

| Table | Reads/Month | Writes/Month | Est. Cost |
|-------|-------------|--------------|-----------|
| findings | 50K | 20K | $1-3 |
| evidence | 10K | 5K | $0.50-1 |
| exceptions | 5K | 2K | $0.25-0.50 |
| drift | 10K | 5K | $0.50-1 |
| ai_feedback | 5K | 2K | $0.25-0.50 |
| preferences | 10K | 1K | $0.25-0.50 |
| approvals | 5K | 2K | $0.25-0.50 |
| remediations | 5K | 2K | $0.25-0.50 |
| conversations | 20K | 10K | $1-2 |

**Total DynamoDB: ~$5-10/month** (pay-per-request)

### S3 Costs (5-10% of total)

| Bucket | Storage | Requests | Est. Cost |
|--------|---------|----------|-----------|
| Evidence | 5-20GB | 50K GET, 20K PUT | $2-8 |
| Reports | 1-5GB | 10K GET, 5K PUT | $1-3 |

**Lifecycle policies** reduce long-term storage costs:
- 0-90 days: Standard ($0.023/GB)
- 90-180 days: Standard-IA ($0.0125/GB)
- 180+ days: Glacier Instant ($0.004/GB)

---

## Cost Optimization Strategies

### 1. Bedrock Optimization (Saves 40-60%)

**Model Tiering**:
- Use Claude Haiku for: status queries, finding lookups, simple questions
- Use Claude Sonnet for: architecture recommendations, reports, complex analysis

**Response Caching**:
- Cache common responses in DynamoDB
- TTL: 1 hour for dynamic, 24 hours for static explanations

### 2. DynamoDB Optimization (Saves 20-30%)

**Pay-Per-Request Pricing**:
- No capacity planning needed
- Perfect for variable CARL workloads
- Only pay for actual usage

**TTL for Ephemeral Data**:
- Conversations: 24-hour TTL
- Reduces storage for old context

### 3. S3 Optimization (Saves 40-60%)

**Lifecycle Policies**:
```
Evidence retention:
- 0-90 days: Standard
- 90-180 days: Standard-IA (45% cheaper)
- 180-365 days: Glacier Instant (83% cheaper)
- 365+ days: Delete or Glacier Deep Archive
```

### 4. Security Services Optimization

**AWS Config**:
- Use only essential rules (30-40 vs 100+)
- Use CHANGE_TRIGGERED evaluation where possible

**GuardDuty**:
- S3 protection is optional
- Enable only for buckets with sensitive data

---

## Cost Monitoring

### CloudWatch Billing Alarms

Set up alarms at:
- 50% of monthly budget (warning)
- 80% of monthly budget (alert)
- 100% of monthly budget (critical)

### Cost Allocation Tags

Apply to all CARL resources:
```
Application: CARL
Environment: prod/staging
Component: core/scanning/evidence
```

### Monthly Review

Monitor costs via:
- AWS Cost Explorer (filter by tags)
- CloudWatch billing dashboard
- Monthly Bedrock usage reports

---

## Cost Scenarios

### Scenario 1: Small Startup (1 account, low usage)
```
Resources: 50 EC2, 10 S3, 3 RDS
Bedrock queries: 5K/month
Evidence: 5GB

Estimated Cost: $75-100/month
```

### Scenario 2: Growing Company (1 account, moderate usage)
```
Resources: 200 EC2, 50 S3, 10 RDS
Bedrock queries: 20K/month
Evidence: 20GB

Estimated Cost: $125-175/month
```

### Scenario 3: Mid-Size (5 accounts, standard usage)
```
Resources: 500 EC2, 100 S3, 25 RDS (total)
Bedrock queries: 50K/month
Evidence: 50GB

Estimated Cost: $300-450/month
```

### Scenario 4: Enterprise (20 accounts, heavy usage)
```
Resources: 2000+ EC2, 500+ S3, 100+ RDS
Bedrock queries: 200K/month
Evidence: 200GB
Multiple reports per week

Estimated Cost: $1,200-1,800/month
```

---

## Free Tier Benefits (Year 1)

New AWS accounts receive free tier benefits that reduce CARL costs:

| Service | Free Tier | Monthly Savings |
|---------|-----------|-----------------|
| Lambda | 1M requests, 400K GB-seconds | ~$5-10 |
| DynamoDB | 25GB storage, 25 WCU, 25 RCU | ~$5 |
| S3 | 5GB storage, 20K GET, 2K PUT | ~$1 |
| CloudWatch | 10 custom metrics, 5GB logs | ~$3 |
| SNS | 1M publishes | Full coverage |
| EventBridge | 14M default bus events | Full coverage |

**First Year Savings: ~$15-20/month**

---

## ROI Analysis

### Time Savings

| Task | Manual Time | With CARL | Annual Savings |
|------|-------------|-----------|----------------|
| Compliance monitoring | 20 hrs/week | 2 hrs/week | 936 hours |
| Evidence collection | 40 hrs/audit | 2 hrs/audit | 76 hours (2 audits) |
| Report generation | 20 hrs/report | 10 minutes | 80 hours |
| Architecture decisions | 10 hrs/project | 1 hr/project | 90 hours |

**Total Time Savings: ~1,182 hours/year**

### Cost Comparison

| Item | Without CARL | With CARL |
|------|--------------|-----------|
| Enterprise tool | $12,000-36,000/year | $0 |
| CARL costs | $0 | $900-2,400/year |
| Staff time (at $100/hr) | $118,200 | $11,820 |
| **Total** | **$130,200-154,200** | **$12,720-14,220** |

**Annual Savings: $117,000-140,000**

---

## Summary

CARL provides enterprise-grade compliance automation at a fraction of the cost of commercial alternatives:

- **Single account**: $75-200/month
- **5 accounts**: $250-550/month
- **20 accounts**: $900-2,100/month

Key cost optimizations built into CARL:
- AI model tiering (Haiku vs Sonnet)
- Pay-per-request DynamoDB pricing
- S3 lifecycle policies for evidence
- Essential-only Config rules

The ROI is significant: **$100,000+ annual savings** compared to enterprise tools plus staff time.
