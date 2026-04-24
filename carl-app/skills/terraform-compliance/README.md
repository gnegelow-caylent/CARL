# Terraform Compliance Skill

A Claude skill for scanning Terraform code for security misconfigurations and compliance violations. **Provides complete, copy-paste ready Terraform code to fix every issue found.**

## What It Does

Scans `.tf` files and identifies security issues, then **generates the fix code** for each finding:

- **SOC 2 Trust Services Criteria** — CC6 (Access), CC7 (Operations), A1 (Availability), C1 (Confidentiality)
- **HIPAA Security Rule** — Access Control, Audit Controls, Integrity, Transmission Security

## How It Works

```
1. You provide: Terraform files (.tf) or HCL code snippets
                              ↓
2. Skill analyzes: Checks 30+ security rules by resource type
                              ↓
3. Output: Each finding includes the complete Terraform code to fix it
                              ↓
4. You copy-paste: Add the fix code directly to your .tf files
```

## Resource Coverage

| Resource Type | Checks | Fix Code Included |
|---------------|--------|-------------------|
| `aws_s3_bucket` | Encryption, public access, versioning, logging, SSL | ✅ |
| `aws_security_group` | Open SSH/RDP, unrestricted ingress | ✅ |
| `aws_db_instance` | Encryption, public access, Multi-AZ, backups, IAM auth | ✅ |
| `aws_instance` | IMDSv2, EBS encryption, monitoring | ✅ |
| `aws_lambda_function` | VPC config, env encryption, tracing | ✅ |
| `aws_cloudtrail` | Log validation, multi-region, encryption | ✅ |
| `aws_kms_key` | Rotation, deletion window, key policy | ✅ |
| `aws_iam_policy` | Least privilege, no wildcards | ✅ |

## Usage

### Scan Terraform Files
```
Scan this Terraform for security issues
```

### Review with Auto-Fix
```
Review this .tf file and give me the fixed code
```

### Check Specific Resource
```
Is this S3 bucket configuration compliant?
```

### Pre-Commit Check
```
Check if this Terraform is ready for production
```

## Output Format

Every finding includes **fix code**:

```markdown
### [S3-001] aws_s3_bucket.data - CRITICAL
**File**: `main.tf` line 15
**Issue**: No encryption configured
**Control**: SOC2 C1.1, HIPAA 164.312(a)(2)(iv)

**Current Code**:
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
}
```

**Fixed Code** (copy-paste ready):
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

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

## Example Session

**Input:**
```
Scan this Terraform for security issues:

resource "aws_security_group" "web" {
  name = "web-sg"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

**Output includes:**
- Issue identified: Open SSH to internet
- Control mapping: SOC2 CC6.1, HIPAA 164.312(a)(1)
- Fixed code with restricted CIDR or SSM alternative
- Complete fix script at the end

## Files

```
terraform-compliance/
├── SKILL.md    # 460+ lines: security rules, control mappings, fix code templates
└── README.md   # This file
```

## Related

- [aws-compliance-review](../aws-compliance-review) — Full infrastructure compliance review
- [hipaa-eligible-check](../hipaa-eligible-check) — Validate HIPAA eligibility
- [aws-architecture-advisor](../aws-architecture-advisor) — Architecture recommendations with costs
