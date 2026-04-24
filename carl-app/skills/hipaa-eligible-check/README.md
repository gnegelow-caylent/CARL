# HIPAA Eligible Check Skill

A Claude skill for validating AWS services against the official HIPAA-eligible services list. **Provides replacement Terraform code when non-eligible services are found.**

## What It Does

Checks whether AWS services in your architecture are covered under the AWS Business Associate Addendum (BAA) for handling electronic Protected Health Information (ePHI).

- **100+ eligible services** catalogued by category
- **Common mistakes** flagged (services people assume are eligible but aren't)
- **Terraform mapping** — knows which `aws_*` resources map to which services
- **Replacement code** — provides HIPAA-eligible alternatives with complete Terraform

## How It Works

```
1. You provide: Terraform code, architecture diagram, or service list
                              ↓
2. Skill checks: Each AWS service against the BAA-covered list
                              ↓
3. Output: Eligible ✅ or Not Eligible ❌ with replacement code
                              ↓
4. You copy-paste: Replace non-eligible services with compliant alternatives
```

## Why This Matters

Using a non-HIPAA-eligible AWS service for ePHI is a **HIPAA violation** that can result in:
- OCR investigations
- Fines up to $1.5M per violation category
- Breach notification requirements
- Reputational damage

## Usage

### Check Architecture
```
Is this architecture HIPAA eligible?
```

### Check Terraform
```
Check if all AWS services in this Terraform are HIPAA eligible
```

### Check Specific Service
```
Is AWS Amplify HIPAA eligible?
```

### Get Alternatives
```
I need to use GameLift but need HIPAA compliance - what are my options?
```

## Output Format

Every non-eligible service includes **replacement code**:

```markdown
## HIPAA Eligibility Check Results

**Services Analyzed**: 8
**Eligible**: 7
**Not Eligible**: 1

### ✅ Eligible Services
| Service | Resource | Notes |
|---------|----------|-------|
| Amazon S3 | aws_s3_bucket.data | Ensure encryption enabled |
| Amazon RDS | aws_db_instance.main | Ensure encryption enabled |

### ❌ Not Eligible - ACTION REQUIRED

#### AWS Amplify Hosting → S3 + CloudFront

**Current (Non-Compliant)**:
```hcl
resource "aws_amplify_app" "frontend" {
  name       = "my-healthcare-app"
  repository = "https://github.com/org/repo"
}
```

**Replacement (HIPAA Eligible)**:
```hcl
resource "aws_s3_bucket" "frontend" {
  bucket = "my-healthcare-app-frontend"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_cloudfront_distribution" "frontend" {
  # ... complete CloudFront config with TLS 1.2+
}
```

**Migration Notes**: Move static assets to S3, update CI/CD to deploy to S3
```

### ⚠️ Configuration Warnings

Services that are eligible but need HIPAA-compliant configuration also include fix code.

## Coverage

| Category | Services | Examples |
|----------|----------|----------|
| Compute | 13 | EC2, Lambda, ECS, EKS, Fargate |
| Storage | 8 | S3, EBS, EFS, FSx, Glacier |
| Database | 11 | RDS, Aurora, DynamoDB, DocumentDB, Redshift |
| Networking | 13 | VPC, ELB, CloudFront, API Gateway |
| Security | 17 | IAM, KMS, WAF, GuardDuty, Security Hub |
| Analytics | 11 | Athena, EMR, Kinesis, Glue, OpenSearch |
| ML | 16 | SageMaker, Bedrock, Comprehend Medical, HealthLake |
| And more... | 20+ | Developer tools, media, migration services |

## Files

```
hipaa-eligible-check/
├── SKILL.md    # 450+ lines: eligible services list, replacement code templates
└── README.md   # This file
```

## Related

- [aws-compliance-review](../aws-compliance-review) — Full SOC 2 + HIPAA compliance review
- [terraform-compliance](../terraform-compliance) — Scan Terraform for security issues
- [aws-architecture-advisor](../aws-architecture-advisor) — Architecture recommendations with costs

## Note

The eligible services list is updated quarterly by AWS. This skill reflects the list as of Q1 2026. Always verify against the [official AWS HIPAA page](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/) for the most current list.
