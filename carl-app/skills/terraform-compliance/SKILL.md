---
name: terraform-compliance
description: Scan Terraform code for security misconfigurations and compliance violations. Provides auto-fix suggestions with corrected HCL code. Use when reviewing .tf files, modules, or Terraform plans for security issues.
---

# Terraform Compliance Skill

Scan Terraform configurations for security misconfigurations, compliance violations, and AWS best practice deviations. Provide auto-fix HCL code for every issue found.

## Scan Approach

### 1. Parse Resource Types

Identify all AWS resources in the Terraform code:
```hcl
resource "aws_*" "..." { }
module "..." { source = "..." }
data "aws_*" "..." { }
```

### 2. Apply Security Rules

For each resource type, check against the security rules below. Every rule includes the compliant configuration.

---

## Security Rules by Resource Type

### aws_s3_bucket

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| S3-001 | Encryption enabled | CRITICAL | SOC2 C1.1, HIPAA 164.312(a)(2)(iv) |
| S3-002 | Public access blocked | CRITICAL | SOC2 CC6.7, HIPAA 164.312(a)(1) |
| S3-003 | Versioning enabled | HIGH | SOC2 A1.3, HIPAA 164.312(c)(1) |
| S3-004 | Logging enabled | MEDIUM | SOC2 CC7.2, HIPAA 164.312(b) |
| S3-005 | SSL enforced | HIGH | SOC2 C1.1, HIPAA 164.312(e)(2)(ii) |

**S3-001: Encryption**
```hcl
# VIOLATION: No encryption configuration
resource "aws_s3_bucket" "example" {
  bucket = "my-bucket"
}

# FIX: Add server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}
```

**S3-002: Public Access Block**
```hcl
# REQUIRED for every S3 bucket
resource "aws_s3_bucket_public_access_block" "example" {
  bucket = aws_s3_bucket.example.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**S3-005: SSL Enforcement**
```hcl
resource "aws_s3_bucket_policy" "ssl_only" {
  bucket = aws_s3_bucket.example.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceSSL"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.example.arn,
          "${aws_s3_bucket.example.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
```

### aws_security_group

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| SG-001 | No 0.0.0.0/0 SSH (22) | CRITICAL | SOC2 CC6.1, HIPAA 164.312(a)(1) |
| SG-002 | No 0.0.0.0/0 RDP (3389) | CRITICAL | SOC2 CC6.1, HIPAA 164.312(a)(1) |
| SG-003 | No 0.0.0.0/0 on all ports | HIGH | SOC2 CC6.1, HIPAA 164.312(a)(1) |
| SG-004 | Description provided | LOW | SOC2 CC5.3 |

**SG-001/002: No Open SSH/RDP**
```hcl
# VIOLATION
ingress {
  from_port   = 22
  to_port     = 22
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]  # DANGEROUS
}

# FIX: Restrict to specific IPs or use SSM
ingress {
  from_port   = 22
  to_port     = 22
  protocol    = "tcp"
  cidr_blocks = ["10.0.0.0/8"]  # Internal only
  description = "SSH from internal network"
}

# BETTER: Use SSM Session Manager (no SSH needed)
# Remove SSH ingress entirely, use aws_iam_instance_profile with SSM
```

### aws_db_instance (RDS)

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| RDS-001 | storage_encrypted = true | CRITICAL | SOC2 C1.1, HIPAA 164.312(a)(2)(iv) |
| RDS-002 | publicly_accessible = false | CRITICAL | SOC2 CC6.1, HIPAA 164.312(a)(1) |
| RDS-003 | multi_az = true | HIGH | SOC2 A1.1, HIPAA 164.312(c)(1) |
| RDS-004 | backup_retention_period >= 7 | HIGH | SOC2 A1.3, HIPAA 164.312(c)(1) |
| RDS-005 | deletion_protection = true | MEDIUM | SOC2 A1.3 |
| RDS-006 | iam_database_authentication_enabled | MEDIUM | SOC2 CC6.1, HIPAA 164.312(d) |

**Compliant RDS Configuration:**
```hcl
resource "aws_db_instance" "main" {
  identifier = "prod-database"

  # Security
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.rds.arn
  publicly_accessible             = false
  iam_database_authentication_enabled = true

  # Availability
  multi_az = true

  # Backup & Recovery
  backup_retention_period = 14
  deletion_protection     = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "prod-database-final"

  # Network
  db_subnet_group_name   = aws_db_subnet_group.private.name
  vpc_security_group_ids = [aws_security_group.rds.id]
}
```

### aws_instance (EC2)

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| EC2-001 | IMDSv2 required | HIGH | SOC2 CC6.1, HIPAA 164.312(a)(1) |
| EC2-002 | EBS volumes encrypted | CRITICAL | SOC2 C1.1, HIPAA 164.312(a)(2)(iv) |
| EC2-003 | No public IP for private workloads | HIGH | SOC2 CC6.1, HIPAA 164.312(a)(1) |
| EC2-004 | Monitoring enabled | MEDIUM | SOC2 CC7.2, HIPAA 164.312(b) |

**EC2-001: IMDSv2**
```hcl
resource "aws_instance" "example" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.medium"

  # REQUIRED: Enforce IMDSv2
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"  # Forces IMDSv2
    http_put_response_hop_limit = 1
  }

  # Encrypted root volume
  root_block_device {
    encrypted   = true
    kms_key_id  = aws_kms_key.ebs.arn
    volume_type = "gp3"
  }

  monitoring = true
}
```

### aws_lambda_function

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| LAM-001 | VPC config for sensitive workloads | MEDIUM | SOC2 CC6.7, HIPAA 164.312(e)(1) |
| LAM-002 | Reserved concurrency set | LOW | SOC2 A1.1 |
| LAM-003 | X-Ray tracing enabled | LOW | SOC2 CC7.2, HIPAA 164.312(b) |
| LAM-004 | Environment variables encrypted | HIGH | SOC2 C1.1, HIPAA 164.312(a)(2)(iv) |

**Compliant Lambda:**
```hcl
resource "aws_lambda_function" "secure" {
  function_name = "secure-processor"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  # VPC for private access
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  # Encrypt environment variables
  kms_key_arn = aws_kms_key.lambda.arn

  environment {
    variables = {
      DB_HOST = var.db_host  # Encrypted with KMS key above
    }
  }

  # Observability
  tracing_config {
    mode = "Active"
  }

  reserved_concurrent_executions = 100
}
```

### aws_cloudtrail

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| CT-001 | Log file validation enabled | HIGH | SOC2 CC7.2, HIPAA 164.312(c)(1) |
| CT-002 | Multi-region enabled | HIGH | SOC2 CC7.1, HIPAA 164.312(b) |
| CT-003 | S3 bucket encrypted | CRITICAL | SOC2 C1.1, HIPAA 164.312(a)(2)(iv) |
| CT-004 | CloudWatch Logs integration | MEDIUM | SOC2 CC7.2, HIPAA 164.312(b) |

**Compliant CloudTrail:**
```hcl
resource "aws_cloudtrail" "main" {
  name                          = "org-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id

  # Required settings
  is_multi_region_trail         = true
  include_global_service_events = true
  enable_log_file_validation    = true

  # KMS encryption
  kms_key_id = aws_kms_key.cloudtrail.arn

  # CloudWatch integration
  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_cloudwatch.arn

  # Capture all events
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3"]
    }
  }
}
```

### aws_kms_key

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| KMS-001 | Key rotation enabled | HIGH | SOC2 CC6.5, HIPAA 164.312(a)(2)(iv) |
| KMS-002 | Deletion window >= 7 days | MEDIUM | SOC2 A1.3 |
| KMS-003 | Key policy restricts access | HIGH | SOC2 CC6.1, HIPAA 164.312(a)(1) |

**Compliant KMS Key:**
```hcl
resource "aws_kms_key" "main" {
  description             = "Main encryption key for production"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "KeyAdministration"
        Effect = "Allow"
        Principal = {
          AWS = var.key_admin_role_arns
        }
        Action = [
          "kms:Create*",
          "kms:Describe*",
          "kms:Enable*",
          "kms:List*",
          "kms:Put*",
          "kms:Update*",
          "kms:Revoke*",
          "kms:Disable*",
          "kms:Get*",
          "kms:Delete*",
          "kms:ScheduleKeyDeletion",
          "kms:CancelKeyDeletion"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Environment = "production"
  }
}

resource "aws_kms_alias" "main" {
  name          = "alias/production-main"
  target_key_id = aws_kms_key.main.key_id
}
```

### aws_iam_policy / aws_iam_role

| Rule ID | Check | Severity | Control |
|---------|-------|----------|---------|
| IAM-001 | No Action: "*" | CRITICAL | SOC2 CC6.4, HIPAA 164.312(a)(1) |
| IAM-002 | No Resource: "*" with sensitive actions | HIGH | SOC2 CC6.4, HIPAA 164.312(a)(1) |
| IAM-003 | Conditions used where possible | MEDIUM | SOC2 CC6.4 |

**IAM-001/002: Least Privilege**
```hcl
# VIOLATION
statement {
  actions   = ["*"]
  resources = ["*"]
}

# FIX: Specific permissions only
statement {
  actions = [
    "s3:GetObject",
    "s3:PutObject"
  ]
  resources = [
    "${aws_s3_bucket.data.arn}/*"
  ]
  condition {
    test     = "StringEquals"
    variable = "aws:RequestedRegion"
    values   = ["us-east-1"]
  }
}
```

---

## Output Format

**CRITICAL RULE**: Every finding MUST include complete, copy-paste ready Terraform code to fix it. Never report an issue without providing the fix.

```markdown
## Terraform Compliance Scan Results

**Files Scanned**: [list]
**Resources Found**: [count by type]
**Issues Found**: Critical: X, High: X, Medium: X, Low: X

---

## Critical Issues

### [RULE-ID] [Resource Name]
**File**: `path/to/file.tf` line XX
**Issue**: [Description]
**Control**: [SOC2/HIPAA reference]

**Current Code**:
```hcl
[The exact violating code from the file]
```

**Fixed Code** (copy-paste ready):
```hcl
[Complete fixed code - include ALL required resources, not just the changed lines]
[If fixing S3 encryption, include the bucket AND the encryption configuration resource]
[User should be able to copy this directly into their .tf file]
```

**Additional Resources Needed** (if any):
```hcl
[Any additional resources like KMS keys, IAM roles, etc. that the fix requires]
```

---

## High Issues
[Same format - every issue has Current Code and Fixed Code]

---

## Compliance Summary

| Category | Status | Notes |
|----------|--------|-------|
| Encryption at Rest | ⚠️ Partial | 3/5 resources encrypted |
| Network Security | ❌ Fail | Open security groups found |
| Logging & Monitoring | ✅ Pass | CloudTrail configured |
| IAM Least Privilege | ⚠️ Partial | 2 overly permissive policies |

---

## Complete Fix Script

At the end, provide a consolidated section with ALL fixes combined:

```hcl
# ============================================
# COMPLIANCE FIXES - Add this to your Terraform
# ============================================

# Fix 1: [Description]
[code]

# Fix 2: [Description]
[code]

# ... all fixes in one copy-paste block
```
```

## When to Use

- Pre-commit hook validation
- PR review for Terraform changes
- Security audit of existing infrastructure code
- Generating compliant Terraform from scratch
