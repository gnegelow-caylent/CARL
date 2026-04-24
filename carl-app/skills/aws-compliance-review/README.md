# AWS Compliance Review Skill

A Claude skill for reviewing AWS architectures and Terraform configurations against SOC 2 and HIPAA compliance requirements. **Provides complete, copy-paste ready Terraform code to fix every issue found.**

## What It Does

Reviews AWS infrastructure for compliance gaps and **generates the fix code** for each finding:

- **SOC 2 Trust Services Criteria** — CC6 (Access), CC7 (Operations), A1 (Availability), C1 (Confidentiality)
- **HIPAA Security Rule** — Access Control, Audit Controls, Integrity, Authentication, Transmission Security

### Resource Coverage

| Category | Resources | Fix Code Included |
|----------|-----------|-------------------|
| IAM | Users, roles, policies, MFA, password policy | ✅ |
| S3 | Encryption, public access, versioning, logging, SSL | ✅ |
| VPC | Flow logs, security groups, NACLs, endpoints | ✅ |
| RDS | Encryption, Multi-AZ, backups, IAM auth | ✅ |
| EC2 | IMDSv2, EBS encryption, SSM access | ✅ |
| Logging | CloudTrail, CloudWatch, GuardDuty, Security Hub | ✅ |
| KMS | Key rotation, policies, aliases | ✅ |

## How It Works

```
1. You provide: Terraform code, architecture diagram, or AWS description
                              ↓
2. Skill analyzes: Checks against 50+ security rules with control mappings
                              ↓
3. Output: Each finding includes the complete Terraform code to fix it
                              ↓
4. You copy-paste: Add the fix code directly to your .tf files
```

## Usage

```
Review this Terraform for SOC 2 compliance
```

```
Check this AWS architecture for HIPAA compliance gaps
```

```
We have a SOC 2 audit next month. Review our infrastructure and tell me what to fix.
```

## Output Format

Every finding includes **fix code**:

```markdown
### CRITICAL: S3 Bucket Missing Encryption
**Resource**: aws_s3_bucket.patient_data
**Violation**: HIPAA 164.312(a)(2)(iv), SOC 2 C1.1
**Risk**: ePHI exposure, breach notification requirements

**Current Code**:
```hcl
resource "aws_s3_bucket" "patient_data" {
  bucket = "patient-records"
}
```

**Fixed Code** (copy-paste ready):
```hcl
resource "aws_s3_bucket" "patient_data" {
  bucket = "patient-records"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "patient_data" {
  bucket = aws_s3_bucket.patient_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
    bucket_key_enabled = true
  }
}
```
```

At the end, all fixes are consolidated into one copy-paste block.

## Files

```
aws-compliance-review/
├── SKILL.md    # 800+ lines: security rules, control mappings, fix code templates
└── README.md   # This file
```

## Related

- [terraform-compliance](../terraform-compliance) — Scan Terraform for security issues
- [hipaa-eligible-check](../hipaa-eligible-check) — Validate HIPAA eligibility
- [aws-architecture-advisor](../aws-architecture-advisor) — Architecture recommendations with costs

## References

- [AWS Security Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/)
- [SOC 2 Trust Services Criteria](https://www.aicpa.org/resources/landing/system-and-organization-controls-soc-suite-of-services)
- [AWS HIPAA Eligible Services](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/)
