---
name: aws-compliance-review
description: Review AWS architectures and Terraform configurations for SOC 2 and HIPAA compliance. Identifies security gaps, missing controls, and provides remediation guidance with specific AWS service recommendations.
---

# AWS Compliance Review Skill

Review AWS architectures, Terraform code, and infrastructure configurations for compliance with SOC 2 Trust Services Criteria and HIPAA Security Rule requirements. Provide actionable remediation guidance.

## Supported Frameworks

### SOC 2 Trust Services Criteria
- **CC6**: Logical and Physical Access Controls
- **CC7**: System Operations (monitoring, incident response)
- **A1**: Availability
- **C1**: Confidentiality
- **PI1**: Processing Integrity

### HIPAA Security Rule (45 CFR 164.312)
- **164.312(a)**: Access Control
- **164.312(b)**: Audit Controls
- **164.312(c)**: Integrity
- **164.312(d)**: Person or Entity Authentication
- **164.312(e)**: Transmission Security

## Review Process

### 1. Identify Resources Under Review

Scan for AWS resources in the provided content:
- Terraform resources (`aws_*`)
- CloudFormation resources
- Architecture diagrams or descriptions
- AWS CLI output or console screenshots

### 2. Check Security Baseline

For each resource type, verify baseline security controls:

#### IAM (Identity & Access Management)
| Control | SOC 2 | HIPAA | Check |
|---------|-------|-------|-------|
| MFA enabled for console users | CC6.1 | 164.312(d) | All IAM users with console access have MFA |
| No inline policies | CC6.1 | 164.312(a)(1) | Policies attached via managed policies, not inline |
| Least privilege | CC6.4 | 164.312(a)(1) | No `*` actions or resources without justification |
| Access key rotation | CC6.5 | 164.312(a)(1) | Keys rotated within 90 days |
| Password policy | CC6.1 | 164.312(a)(1) | Minimum 14 chars, complexity requirements |

#### S3 Buckets
| Control | SOC 2 | HIPAA | Check |
|---------|-------|-------|-------|
| Encryption at rest | C1.1 | 164.312(a)(2)(iv) | SSE-S3, SSE-KMS, or SSE-C enabled |
| Block public access | CC6.7 | 164.312(a)(1) | `block_public_acls = true`, all 4 settings |
| Versioning enabled | A1.3 | 164.312(c)(1) | For data integrity and recovery |
| Access logging | CC7.2 | 164.312(b) | Server access logging to separate bucket |
| Lifecycle policies | C1.2 | 164.312(c)(1) | Retention and deletion policies defined |

#### VPC & Networking
| Control | SOC 2 | HIPAA | Check |
|---------|-------|-------|-------|
| VPC Flow Logs | CC7.2 | 164.312(b) | Enabled, sent to CloudWatch or S3 |
| No 0.0.0.0/0 ingress | CC6.1 | 164.312(a)(1) | Security groups restrict source IPs |
| Private subnets for data | C1.1 | 164.312(e)(1) | Databases, sensitive workloads not public |
| NACLs configured | CC6.1 | 164.312(a)(1) | Defense in depth beyond security groups |
| VPC endpoints | CC6.7 | 164.312(e)(1) | Private access to AWS services |

#### RDS / Databases
| Control | SOC 2 | HIPAA | Check |
|---------|-------|-------|-------|
| Encryption at rest | C1.1 | 164.312(a)(2)(iv) | `storage_encrypted = true` |
| Encryption in transit | C1.1 | 164.312(e)(2)(ii) | SSL/TLS enforced |
| Multi-AZ | A1.1 | 164.312(c)(1) | High availability enabled |
| Automated backups | A1.3 | 164.312(c)(1) | Retention period >= 7 days |
| No public access | CC6.1 | 164.312(a)(1) | `publicly_accessible = false` |
| IAM authentication | CC6.1 | 164.312(d) | Prefer IAM auth over passwords |

#### Compute (EC2, ECS, Lambda)
| Control | SOC 2 | HIPAA | Check |
|---------|-------|-------|-------|
| IMDSv2 required | CC6.1 | 164.312(a)(1) | `http_tokens = "required"` |
| EBS encryption | C1.1 | 164.312(a)(2)(iv) | All volumes encrypted |
| No SSH from 0.0.0.0/0 | CC6.1 | 164.312(a)(1) | Restrict SSH/RDP access |
| SSM for access | CC6.5 | 164.312(b) | Session Manager instead of SSH |
| VPC placement | CC6.7 | 164.312(e)(1) | Lambda in VPC for sensitive workloads |

#### Logging & Monitoring
| Control | SOC 2 | HIPAA | Check |
|---------|-------|-------|-------|
| CloudTrail enabled | CC7.1 | 164.312(b) | Multi-region, management events |
| CloudTrail log validation | CC7.2 | 164.312(c)(1) | `enable_log_file_validation = true` |
| CloudWatch alarms | CC7.2 | 164.312(b) | Critical metric alerts configured |
| GuardDuty enabled | CC7.1 | 164.312(b) | Threat detection active |
| Security Hub enabled | CC7.1 | 164.312(b) | Centralized findings |
| Config enabled | CC7.2 | 164.312(b) | Configuration recording |

#### Encryption & Key Management
| Control | SOC 2 | HIPAA | Check |
|---------|-------|-------|-------|
| KMS CMK for sensitive data | C1.1 | 164.312(a)(2)(iv) | Customer-managed keys, not AWS-managed |
| Key rotation enabled | CC6.5 | 164.312(a)(2)(iv) | Automatic annual rotation |
| Key policy least privilege | CC6.1 | 164.312(a)(1) | Restricted key administrators |
| Secrets in Secrets Manager | C1.1 | 164.312(a)(2)(iv) | No hardcoded credentials |

### 3. HIPAA-Specific Checks

If HIPAA compliance is required, additionally verify:

#### HIPAA Eligible Services
Only these AWS services are covered under the AWS BAA for ePHI:
- **Compute**: EC2, Lambda, ECS, EKS, Fargate, Batch
- **Storage**: S3, EBS, EFS, FSx, Storage Gateway, Backup
- **Database**: RDS, Aurora, DynamoDB, DocumentDB, ElastiCache, Neptune, Redshift
- **Networking**: VPC, ELB, API Gateway, CloudFront, Route 53, Direct Connect
- **Security**: IAM, KMS, Secrets Manager, ACM, WAF, Shield, GuardDuty, Security Hub
- **Management**: CloudWatch, CloudTrail, Config, Systems Manager, Organizations

**Flag if**: Architecture uses services NOT on the HIPAA eligible list for ePHI workloads.

#### ePHI Data Flow
- Identify where ePHI enters, is processed, stored, and transmitted
- Verify encryption at every stage
- Check for data residency requirements

### 4. Cross-Reference Checks

After individual resource review:

1. **Logging Coverage**: Every resource should have audit trail (CloudTrail + service-specific logs)
2. **Encryption Consistency**: If one resource encrypts data, all downstream resources must too
3. **Network Isolation**: Sensitive resources should be in private subnets with controlled access
4. **Backup Coverage**: Critical data stores should have backup policies

## Output Format

**CRITICAL RULE**: Every finding MUST include the Terraform/code to fix it. No finding without a fix.

Structure review as:

```markdown
## Compliance Summary
- **Framework**: [SOC 2 / HIPAA / Both]
- **Resources Reviewed**: [Count and types]
- **Critical Findings**: [Count]
- **High Findings**: [Count]
- **Medium Findings**: [Count]

## Critical Findings
[For each finding, include the fix code - see format below]

## High Priority Findings
[Same format with fix code]

## Medium Priority Findings
[Same format with fix code]

## Compliant Controls
[What's already done well - brief list]
```

**Required format for EVERY finding:**

```markdown
### [SEVERITY] [Issue Title]
**Resource**: [resource name/type]
**Violation**: [SOC 2 CC#.# or HIPAA 164.312(x)]
**Risk**: [1 sentence on business impact]

**Current State** (if reviewing existing code):
```hcl
[The problematic code or configuration]
```

**Required Fix**:
```hcl
[Complete, copy-paste ready Terraform code to fix the issue]
```

**Verification**: [How to confirm the fix worked]
```

## Example Findings

### Critical: S3 Bucket Publicly Accessible
```
**What**: Bucket `my-data-bucket` has `block_public_acls = false`
**Why**: Violates SOC 2 CC6.7 (Data Classification), HIPAA 164.312(a)(1) (Access Control)
**Risk**: Data exposure, regulatory fines, breach notification requirements
**Fix**:
```hcl
resource "aws_s3_bucket_public_access_block" "my_data_bucket" {
  bucket = aws_s3_bucket.my_data_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```
```

### High: CloudTrail Not Enabled
```
**What**: No CloudTrail trail found in configuration
**Why**: Violates SOC 2 CC7.1 (Detection), HIPAA 164.312(b) (Audit Controls)
**Risk**: No audit trail for security investigations, compliance audit failure
**Fix**:
```hcl
resource "aws_cloudtrail" "main" {
  name                          = "main-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }
}
```
```

---

## Fix Code Reference

Use these Terraform snippets when generating fixes. Always provide complete, copy-paste ready code.

### S3 Bucket - Complete Compliant Configuration

```hcl
# Compliant S3 bucket with all required security controls
resource "aws_s3_bucket" "compliant" {
  bucket = "my-compliant-bucket"

  tags = {
    Environment = "production"
    Compliance  = "soc2-hipaa"
  }
}

# REQUIRED: Block all public access
resource "aws_s3_bucket_public_access_block" "compliant" {
  bucket = aws_s3_bucket.compliant.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# REQUIRED: Enable encryption with KMS
resource "aws_s3_bucket_server_side_encryption_configuration" "compliant" {
  bucket = aws_s3_bucket.compliant.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}

# REQUIRED: Enable versioning for data integrity
resource "aws_s3_bucket_versioning" "compliant" {
  bucket = aws_s3_bucket.compliant.id
  versioning_configuration {
    status = "Enabled"
  }
}

# REQUIRED: Enable access logging
resource "aws_s3_bucket_logging" "compliant" {
  bucket = aws_s3_bucket.compliant.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "s3-access-logs/${aws_s3_bucket.compliant.id}/"
}

# REQUIRED: Enforce SSL/TLS
resource "aws_s3_bucket_policy" "ssl_only" {
  bucket = aws_s3_bucket.compliant.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceSSLOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.compliant.arn,
          "${aws_s3_bucket.compliant.arn}/*"
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

# RECOMMENDED: Lifecycle policy for cost and retention
resource "aws_s3_bucket_lifecycle_configuration" "compliant" {
  bucket = aws_s3_bucket.compliant.id

  rule {
    id     = "archive-old-versions"
    status = "Enabled"

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}
```

### RDS - Complete Compliant Configuration

```hcl
# Compliant RDS instance with all required security controls
resource "aws_db_instance" "compliant" {
  identifier = "prod-database"

  # Engine configuration
  engine               = "postgres"
  engine_version       = "15.4"
  instance_class       = "db.t3.medium"
  allocated_storage    = 100
  max_allocated_storage = 500
  storage_type         = "gp3"

  # REQUIRED: Encryption at rest
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  # REQUIRED: No public access
  publicly_accessible = false

  # REQUIRED: High availability
  multi_az = true

  # REQUIRED: Backup configuration
  backup_retention_period = 14
  backup_window          = "03:00-04:00"
  maintenance_window     = "Mon:04:00-Mon:05:00"

  # REQUIRED: Deletion protection
  deletion_protection      = true
  skip_final_snapshot      = false
  final_snapshot_identifier = "prod-database-final-snapshot"
  copy_tags_to_snapshot    = true

  # RECOMMENDED: IAM authentication
  iam_database_authentication_enabled = true

  # RECOMMENDED: Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  # RECOMMENDED: Performance insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.rds.arn

  # REQUIRED: Network isolation
  db_subnet_group_name   = aws_db_subnet_group.private.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # RECOMMENDED: Auto minor version upgrade
  auto_minor_version_upgrade = true

  tags = {
    Environment = "production"
    Compliance  = "soc2-hipaa"
  }
}

# Compliant security group for RDS
resource "aws_security_group" "rds" {
  name        = "rds-compliant-sg"
  description = "Security group for compliant RDS instance"
  vpc_id      = var.vpc_id

  # Only allow access from application security group
  ingress {
    description     = "PostgreSQL from app servers"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    description = "No outbound required"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []
  }

  tags = {
    Name       = "rds-compliant-sg"
    Compliance = "soc2-hipaa"
  }
}
```

### EC2 - Complete Compliant Configuration

```hcl
# Compliant EC2 instance with all required security controls
resource "aws_instance" "compliant" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.medium"
  subnet_id     = var.private_subnet_id

  # REQUIRED: IMDSv2 enforcement
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"  # Forces IMDSv2
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  # REQUIRED: Encrypted root volume
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 50
    encrypted             = true
    kms_key_id            = aws_kms_key.ebs.arn
    delete_on_termination = true

    tags = {
      Name       = "compliant-instance-root"
      Compliance = "soc2-hipaa"
    }
  }

  # REQUIRED: Encrypted data volume (if needed)
  ebs_block_device {
    device_name           = "/dev/sdf"
    volume_type           = "gp3"
    volume_size           = 100
    encrypted             = true
    kms_key_id            = aws_kms_key.ebs.arn
    delete_on_termination = false

    tags = {
      Name       = "compliant-instance-data"
      Compliance = "soc2-hipaa"
    }
  }

  # REQUIRED: No public IP for private workloads
  associate_public_ip_address = false

  # REQUIRED: IAM role for SSM (no SSH keys)
  iam_instance_profile = aws_iam_instance_profile.ssm.name

  # REQUIRED: Security group
  vpc_security_group_ids = [aws_security_group.ec2_compliant.id]

  # RECOMMENDED: Detailed monitoring
  monitoring = true

  tags = {
    Name       = "compliant-instance"
    Compliance = "soc2-hipaa"
  }
}

# Compliant security group - no SSH from internet
resource "aws_security_group" "ec2_compliant" {
  name        = "ec2-compliant-sg"
  description = "Compliant security group - no direct SSH"
  vpc_id      = var.vpc_id

  # NO SSH ingress - use SSM Session Manager instead

  # Application traffic only from load balancer
  ingress {
    description     = "HTTPS from ALB"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Outbound for SSM and updates
  egress {
    description = "HTTPS outbound for SSM and updates"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name       = "ec2-compliant-sg"
    Compliance = "soc2-hipaa"
  }
}

# IAM role for SSM access (replaces SSH)
resource "aws_iam_role" "ssm" {
  name = "ec2-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  name = "ec2-ssm-profile"
  role = aws_iam_role.ssm.name
}
```

### CloudTrail - Complete Compliant Configuration

```hcl
# Compliant CloudTrail with all required settings
resource "aws_cloudtrail" "compliant" {
  name           = "org-compliant-trail"
  s3_bucket_name = aws_s3_bucket.cloudtrail.id
  s3_key_prefix  = "cloudtrail"

  # REQUIRED: Multi-region trail
  is_multi_region_trail = true

  # REQUIRED: Global service events (IAM, STS, CloudFront)
  include_global_service_events = true

  # REQUIRED: Log file integrity validation
  enable_log_file_validation = true

  # REQUIRED: KMS encryption
  kms_key_id = aws_kms_key.cloudtrail.arn

  # REQUIRED: CloudWatch Logs integration
  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.cloudtrail.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.cloudtrail_cloudwatch.arn

  # REQUIRED: Enable for organization (if using AWS Organizations)
  # is_organization_trail = true

  # Capture all management events
  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }

  # Capture S3 data events for sensitive buckets
  event_selector {
    read_write_type           = "All"
    include_management_events = false

    data_resource {
      type   = "AWS::S3::Object"
      values = ["${aws_s3_bucket.sensitive_data.arn}/"]
    }
  }

  # Capture Lambda invocations
  event_selector {
    read_write_type           = "All"
    include_management_events = false

    data_resource {
      type   = "AWS::Lambda::Function"
      values = ["arn:aws:lambda"]
    }
  }

  tags = {
    Name       = "org-compliant-trail"
    Compliance = "soc2-hipaa"
  }
}

# CloudWatch Log Group for CloudTrail
resource "aws_cloudwatch_log_group" "cloudtrail" {
  name              = "/aws/cloudtrail/org-trail"
  retention_in_days = 365  # HIPAA requires minimum 6 years for some records
  kms_key_id        = aws_kms_key.cloudwatch.arn

  tags = {
    Compliance = "soc2-hipaa"
  }
}
```

### KMS Key - Complete Compliant Configuration

```hcl
# Compliant KMS key with proper policy and rotation
resource "aws_kms_key" "compliant" {
  description             = "Compliant encryption key for production data"
  deletion_window_in_days = 30

  # REQUIRED: Enable automatic key rotation
  enable_key_rotation = true

  # REQUIRED: Multi-region for DR (if needed)
  multi_region = false

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Root account access (required for key management)
      {
        Sid    = "EnableRootPermissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      # Key administrators
      {
        Sid    = "AllowKeyAdministration"
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
          "kms:TagResource",
          "kms:UntagResource",
          "kms:ScheduleKeyDeletion",
          "kms:CancelKeyDeletion"
        ]
        Resource = "*"
      },
      # Key users (services that encrypt/decrypt)
      {
        Sid    = "AllowKeyUsage"
        Effect = "Allow"
        Principal = {
          AWS = var.key_user_role_arns
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      # Allow AWS services to use the key
      {
        Sid    = "AllowServicePrincipals"
        Effect = "Allow"
        Principal = {
          Service = [
            "logs.${data.aws_region.current.name}.amazonaws.com",
            "s3.amazonaws.com",
            "rds.amazonaws.com"
          ]
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = {
    Name       = "compliant-data-key"
    Compliance = "soc2-hipaa"
  }
}

resource "aws_kms_alias" "compliant" {
  name          = "alias/compliant-data-key"
  target_key_id = aws_kms_key.compliant.key_id
}
```

### VPC Flow Logs - Complete Compliant Configuration

```hcl
# REQUIRED: VPC Flow Logs for all VPCs
resource "aws_flow_log" "compliant" {
  vpc_id                   = aws_vpc.main.id
  traffic_type             = "ALL"  # Capture accept and reject
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.vpc_flow_logs.arn
  iam_role_arn             = aws_iam_role.vpc_flow_logs.arn
  max_aggregation_interval = 60  # 1 minute for faster detection

  tags = {
    Name       = "vpc-flow-logs"
    Compliance = "soc2-hipaa"
  }
}

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/aws/vpc/flow-logs/${aws_vpc.main.id}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.cloudwatch.arn

  tags = {
    Compliance = "soc2-hipaa"
  }
}

resource "aws_iam_role" "vpc_flow_logs" {
  name = "vpc-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "vpc-flow-logs-policy"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      }
    ]
  })
}
```

### IAM Password Policy - Compliant Configuration

```hcl
# REQUIRED: Strong password policy
resource "aws_iam_account_password_policy" "compliant" {
  minimum_password_length        = 14
  require_lowercase_characters   = true
  require_numbers                = true
  require_uppercase_characters   = true
  require_symbols                = true
  allow_users_to_change_password = true
  max_password_age               = 90
  password_reuse_prevention      = 24
  hard_expiry                    = false
}
```

### GuardDuty - Enable for Threat Detection

```hcl
# REQUIRED: Enable GuardDuty
resource "aws_guardduty_detector" "main" {
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  finding_publishing_frequency = "FIFTEEN_MINUTES"

  tags = {
    Compliance = "soc2-hipaa"
  }
}
```

### Security Hub - Enable for Centralized Findings

```hcl
# REQUIRED: Enable Security Hub
resource "aws_securityhub_account" "main" {}

# Enable AWS Foundational Security Best Practices
resource "aws_securityhub_standards_subscription" "aws_foundational" {
  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.main]
}

# Enable CIS AWS Foundations Benchmark
resource "aws_securityhub_standards_subscription" "cis" {
  standards_arn = "arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.2.0"
  depends_on    = [aws_securityhub_account.main]
}
```

---

## When to Use This Skill

- Reviewing Terraform before deployment
- Architecture design reviews
- Pre-audit compliance checks
- Incident response (checking if controls were in place)
- Vendor/third-party infrastructure assessment
