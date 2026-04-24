# AWS Architecture Advisor Skill

A Claude skill for AWS architecture recommendations with cost estimates (reference), compliance mappings, and decision frameworks.

## What It Does

Provides architecture guidance that includes:
- **Cost estimates** — Reference pricing for every recommendation (may be outdated)
- **Compliance mapping** — SOC 2 and HIPAA controls addressed
- **Option comparison** — 2-3 alternatives with tradeoffs
- **Decision logic** — When to use what
- **Common mistakes** — What to avoid

## How It Works

```
1. You ask: Architecture question (e.g., "Best database for HIPAA workload?")
                              ↓
2. Skill analyzes: Your requirements against 50+ decision patterns
                              ↓
3. Output: 2-3 options with costs, pros/cons, compliance coverage
                              ↓
4. You decide: Based on cost, compliance, and operational requirements
```

## Coverage

| Decision Area | Patterns Included |
|---------------|-------------------|
| **VPC Design** | CIDR planning, subnet tiers, AZ strategy, VPC endpoints, flow logs |
| **Database** | RDS deployment (Single/Multi-AZ/Multi-Region), Aurora, DynamoDB, ElastiCache |
| **Compute** | Lambda (public/VPC), Fargate, ECS on EC2, EC2 |
| **Containers** | ALB + Fargate, ALB + EC2, ALB + Lambda |
| **Security Tooling** | Security Hub, GuardDuty (organization-wide) |
| **Logging** | CloudTrail, log aggregation (S3/CloudWatch/OpenSearch) |
| **Encryption** | AWS Managed Keys, CMK strategy, CloudHSM |
| **Identity** | IAM Users, IAM Identity Center, Cognito |

## Usage

### VPC Design
```
How should I plan CIDR blocks for a multi-account environment?
```

### Database Selection
```
What's the best database for a HIPAA workload with variable traffic?
```

### Compute Comparison
```
Compare Lambda vs Fargate for an API backend
```

### Security Tooling
```
How should I deploy Security Hub across multiple accounts?
```

### Logging Architecture
```
Design a logging architecture that covers SOC 2 CC7.1 and CC7.2
```

## Example Output

**Input**: "How should I handle VPC endpoints?"

**Output**:
```markdown
## VPC Endpoints

| Pattern | Cost (ref) | Best For | SOC 2 |
|---------|------------|----------|-------|
| Gateway Only (S3 + DynamoDB) | FREE | All workloads | CC6.6, CC6.7 |
| Essential Interface | ~$20-90/mo | Private subnets, containers | CC6.6, CC6.7 |
| Comprehensive Interface | ~$100-300/mo | Air-gapped, zero internet | CC6.6, CC6.7, CC6.8 |

**Decision Logic:**
- ALWAYS deploy Gateway Endpoints (free savings)
- No NAT Gateway → Interface endpoints required
- Containers → Essential set (ECR, Logs, SSM)

**Essential Endpoints for Containers:**
- ecr.api, ecr.dkr, logs, ssm, ssmmessages, secretsmanager, s3 (gateway)
```

## Output Format

Every recommendation includes:

1. **Options table** — Patterns with reference costs and compliance
2. **Decision logic** — When to use each option
3. **Reference costs** — Approximate pricing (verify on AWS)
4. **SOC 2 controls** — Which controls are addressed
5. **HIPAA sections** — If applicable
6. **Common mistakes** — What to avoid

## Pricing Note

All costs are **reference estimates** that may be outdated. Actual costs vary by region, usage, and current AWS pricing. Always verify at [AWS Pricing](https://aws.amazon.com/pricing/).

## Files

```
aws-architecture-advisor/
├── SKILL.md    # 540+ lines: 50+ architecture patterns with costs and compliance
└── README.md   # This file
```

## Related

- [aws-compliance-review](../aws-compliance-review) — Review existing architectures for compliance
- [terraform-compliance](../terraform-compliance) — Scan Terraform for security issues
- [hipaa-eligible-check](../hipaa-eligible-check) — Validate HIPAA eligibility
