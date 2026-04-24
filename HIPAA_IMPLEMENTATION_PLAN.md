# HIPAA Implementation Plan for CARL

## Overview

Add HIPAA (Health Insurance Portability and Accountability Act) as a second compliance framework alongside SOC 2. This enables CARL to serve healthcare companies, health tech startups, and any organization handling Protected Health Information (PHI).

## HIPAA Security Rule Quick Reference

| Safeguard | Section | Requirement |
|-----------|---------|-------------|
| Access Control | 164.312(a)(1) | Unique user IDs, emergency access, auto-logoff, encryption |
| Audit Controls | 164.312(b) | Record and examine system activity |
| Integrity | 164.312(c)(1) | Protect ePHI from improper alteration |
| Authentication | 164.312(d) | Verify person/entity identity |
| Transmission Security | 164.312(e)(1) | Encrypt ePHI in transit |

---

## Phase 1: Framework Abstraction Layer (Week 1)

**Goal:** Make CARL framework-agnostic so adding HIPAA (and future frameworks) is clean.

### 1.1 Create Framework Configuration

```
carl-app/src/knowledge/compliance_frameworks.py
```

```python
from dataclasses import dataclass
from enum import Enum

class ComplianceFramework(Enum):
    SOC2 = "soc2"
    HIPAA = "hipaa"

@dataclass
class FrameworkConfig:
    id: str
    name: str
    description: str
    controls_prefix: str
    evidence_retention_days: int
    report_template: str
    aws_config_rules: list[str]
    security_hub_standards: list[str]

FRAMEWORKS = {
    "soc2": FrameworkConfig(
        id="soc2",
        name="SOC 2 Type II",
        description="Service Organization Control 2 - Trust Services Criteria",
        controls_prefix="CC",
        evidence_retention_days=2555,  # 7 years
        report_template="soc2_report.html",
        aws_config_rules=[
            "cloudtrail-enabled",
            "guardduty-enabled-centralized",
            "s3-bucket-server-side-encryption-enabled",
            # ... existing rules
        ],
        security_hub_standards=[
            "aws-foundational-security-best-practices/v/1.0.0",
            "cis-aws-foundations-benchmark/v/1.4.0",
        ],
    ),
    "hipaa": FrameworkConfig(
        id="hipaa",
        name="HIPAA Security Rule",
        description="Health Insurance Portability and Accountability Act",
        controls_prefix="164.312",
        evidence_retention_days=2190,  # 6 years
        report_template="hipaa_report.html",
        aws_config_rules=[
            "s3-bucket-server-side-encryption-enabled",  # 164.312(a)(2)(iv)
            "encrypted-volumes",                          # 164.312(a)(2)(iv)
            "rds-storage-encrypted",                      # 164.312(a)(2)(iv)
            "cloudtrail-enabled",                         # 164.312(b)
            "cloud-trail-log-file-validation-enabled",    # 164.312(c)(1)
            "iam-user-mfa-enabled",                       # 164.312(d)
            "alb-http-to-https-redirection-check",        # 164.312(e)(1)
            "elb-tls-https-listeners-only",               # 164.312(e)(1)
            "api-gw-ssl-enabled",                         # 164.312(e)(1)
        ],
        security_hub_standards=[
            "aws-foundational-security-best-practices/v/1.0.0",
            # HIPAA standard when available
        ],
    ),
}
```

### 1.2 Update Evidence Collector

Modify `evidence_collector.py` to accept framework parameter:

```python
def collect_evidence(self, framework: str = "soc2") -> list[Evidence]:
    config = FRAMEWORKS[framework]
    # Use framework-specific config rules
    # Map findings to framework controls
```

### 1.3 Update AI Prompts

Add framework context to `bedrock_service.py`:

```python
FRAMEWORK_PROMPTS = {
    "soc2": "Map recommendations to SOC 2 Trust Services Criteria (CC6.x, CC7.x, etc.)",
    "hipaa": """Map recommendations to HIPAA Security Rule:
    - 164.312(a)(1): Access Control
    - 164.312(b): Audit Controls
    - 164.312(c)(1): Integrity
    - 164.312(d): Authentication
    - 164.312(e)(1): Transmission Security""",
}
```

---

## Phase 2: HIPAA Control Mappings (Week 1-2)

**Goal:** Map AWS services and configurations to HIPAA controls.

### 2.1 Create HIPAA Control Definitions

```
carl-app/src/knowledge/hipaa_controls.py
```

```python
HIPAA_CONTROLS = {
    "164.312(a)(1)": {
        "name": "Access Control",
        "description": "Implement technical policies to allow access only to authorized persons",
        "implementation_specs": [
            "164.312(a)(2)(i) - Unique User Identification",
            "164.312(a)(2)(ii) - Emergency Access Procedure",
            "164.312(a)(2)(iii) - Automatic Logoff",
            "164.312(a)(2)(iv) - Encryption and Decryption",
        ],
        "aws_services": ["IAM", "Cognito", "SSO", "KMS"],
        "aws_controls": [
            "Unique IAM users (no shared credentials)",
            "MFA enabled for all users",
            "Session timeout policies",
            "KMS encryption for data at rest",
        ],
    },
    "164.312(b)": {
        "name": "Audit Controls",
        "description": "Implement mechanisms to record and examine activity",
        "aws_services": ["CloudTrail", "CloudWatch", "VPC Flow Logs", "S3 Access Logs"],
        "aws_controls": [
            "CloudTrail enabled in all regions",
            "CloudTrail log file validation",
            "VPC Flow Logs enabled",
            "S3 access logging enabled",
            "6-year log retention",
        ],
    },
    "164.312(c)(1)": {
        "name": "Integrity",
        "description": "Protect ePHI from improper alteration or destruction",
        "aws_services": ["S3 Versioning", "RDS", "Backup"],
        "aws_controls": [
            "S3 versioning enabled",
            "S3 Object Lock for immutability",
            "RDS automated backups",
            "AWS Backup for critical resources",
        ],
    },
    "164.312(d)": {
        "name": "Person or Entity Authentication",
        "description": "Verify identity of person/entity seeking access",
        "aws_services": ["IAM", "Cognito", "SSO"],
        "aws_controls": [
            "MFA required for all access",
            "Strong password policies",
            "Certificate-based authentication where applicable",
        ],
    },
    "164.312(e)(1)": {
        "name": "Transmission Security",
        "description": "Protect ePHI during electronic transmission",
        "aws_services": ["ACM", "ALB", "CloudFront", "API Gateway"],
        "aws_controls": [
            "TLS 1.2+ for all connections",
            "HTTPS enforced (no HTTP)",
            "VPN or Direct Connect for hybrid",
            "S3 bucket policies requiring SSL",
        ],
    },
}
```

### 2.2 Update Architecture Patterns

Extend existing patterns with HIPAA controls:

```python
@dataclass
class ArchitectureOption:
    name: str
    description: str
    # ... existing fields ...
    soc2_controls: list[str]
    hipaa_controls: list[str]  # NEW

# Example
ArchitectureOption(
    name="KMS Encryption",
    description="AWS KMS for encryption at rest",
    soc2_controls=["CC6.1", "CC6.7"],
    hipaa_controls=["164.312(a)(2)(iv)", "164.312(c)(1)"],
)
```

---

## Phase 3: HIPAA-Specific Features (Week 2)

**Goal:** Add features unique to HIPAA compliance.

### 3.1 PHI Detection Integration

Integrate Amazon Macie for PHI detection:

```python
# services/phi_detector.py
class PHIDetector:
    """Detect Protected Health Information in AWS resources."""

    def scan_s3_for_phi(self, bucket_name: str) -> list[PHIFinding]:
        """Use Macie to scan S3 bucket for PHI."""
        # Enable Macie classification job
        # Return findings with PHI identifiers

    def get_phi_locations(self) -> dict:
        """Get map of all PHI locations in AWS account."""
        # S3 buckets with PHI
        # RDS databases with PHI
        # DynamoDB tables with PHI
```

### 3.2 HIPAA Eligible Services Validation

```python
# knowledge/hipaa_eligible_services.py
HIPAA_ELIGIBLE_SERVICES = [
    "ec2", "rds", "s3", "lambda", "dynamodb", "ecs", "eks",
    "api-gateway", "cloudfront", "cognito", "kms", "secrets-manager",
    "cloudtrail", "cloudwatch", "sns", "sqs", "kinesis",
    # ... full list from AWS HIPAA eligible services
]

def validate_hipaa_eligible(resource_type: str) -> bool:
    """Check if AWS service is HIPAA eligible."""
    return resource_type.lower() in HIPAA_ELIGIBLE_SERVICES

def scan_for_ineligible_services(self) -> list[Finding]:
    """Find resources using non-HIPAA-eligible services."""
    # Scan account for all resources
    # Flag any using non-eligible services
```

### 3.3 BAA (Business Associate Agreement) Tracking

```python
# services/baa_tracker.py
class BAATracker:
    """Track Business Associate Agreements."""

    def check_aws_baa_status(self) -> bool:
        """Verify AWS BAA is in place via AWS Artifact."""

    def list_third_party_baas(self) -> list[BAA]:
        """List all third-party BAAs from DynamoDB."""

    def get_baa_expiration_alerts(self) -> list[Alert]:
        """Get BAAs expiring in next 90 days."""
```

---

## Phase 4: HIPAA Terraform Blueprints (Week 2-3)

**Goal:** Create HIPAA-compliant infrastructure blueprints.

### 4.1 New Blueprints

| Blueprint | Description |
|-----------|-------------|
| `hipaa/foundation` | Base HIPAA-compliant account setup |
| `hipaa/phi-storage` | S3 + KMS for PHI storage |
| `hipaa/phi-database` | RDS with encryption, backups, audit |
| `hipaa/phi-compute` | EC2/ECS with hardened AMIs |
| `hipaa/audit-logging` | CloudTrail + CloudWatch + 6yr retention |

### 4.2 HIPAA Foundation Blueprint

```hcl
# Generated by CARL for HIPAA compliance

# Encryption key for all PHI
resource "aws_kms_key" "phi" {
  description             = "KMS key for PHI encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Compliance = "HIPAA"
    DataClass  = "PHI"
  }
}

# CloudTrail for audit logging (164.312(b))
resource "aws_cloudtrail" "hipaa_audit" {
  name                          = "hipaa-audit-trail"
  s3_bucket_name                = aws_s3_bucket.audit_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true  # 164.312(c)(1)
  kms_key_id                    = aws_kms_key.phi.arn
}

# S3 for PHI storage (164.312(a)(2)(iv), 164.312(e)(1))
resource "aws_s3_bucket" "phi_storage" {
  bucket = "${var.prefix}-phi-storage"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "phi" {
  bucket = aws_s3_bucket.phi_storage.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.phi.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_versioning" "phi" {
  bucket = aws_s3_bucket.phi_storage.id
  versioning_configuration {
    status = "Enabled"  # 164.312(c)(1) - Integrity
  }
}

resource "aws_s3_bucket_policy" "require_ssl" {
  bucket = aws_s3_bucket.phi_storage.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "RequireSSL"  # 164.312(e)(1)
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = ["${aws_s3_bucket.phi_storage.arn}/*"]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}
```

---

## Phase 5: HIPAA Reports & Evidence (Week 3)

**Goal:** Generate HIPAA-specific compliance reports.

### 5.1 HIPAA Evidence Mapping

```python
HIPAA_EVIDENCE_MAP = {
    "164.312(a)(1)": {
        "name": "Access Control Evidence",
        "evidence_types": [
            "iam_password_policy",
            "iam_mfa_status",
            "iam_user_list",
            "cognito_user_pool_config",
            "kms_key_policies",
        ],
    },
    "164.312(b)": {
        "name": "Audit Control Evidence",
        "evidence_types": [
            "cloudtrail_config",
            "cloudwatch_log_groups",
            "vpc_flow_logs",
            "s3_access_logs",
        ],
    },
    # ... other controls
}
```

### 5.2 HIPAA Report Template

```
HIPAA Security Rule Compliance Report
=====================================

Organization: {org_name}
Assessment Date: {date}
Assessment Period: {start_date} - {end_date}

Executive Summary
-----------------
Overall Compliance: {percentage}%
Controls Assessed: {total_controls}
Controls Passing: {passing_controls}
Controls Failing: {failing_controls}

Control Assessment Details
--------------------------

§164.312(a)(1) - Access Control
Status: {status}
Evidence Collected:
- IAM Password Policy: {evidence}
- MFA Status: {evidence}
Findings: {findings}

§164.312(b) - Audit Controls
Status: {status}
Evidence Collected:
- CloudTrail Configuration: {evidence}
- Log Retention: {evidence}
Findings: {findings}

... (continue for all controls)
```

---

## Phase 6: Slack Command Updates (Week 3)

### 6.1 Framework Selection

```
/carl status                      # Default: SOC 2
/carl status --framework hipaa    # HIPAA status

/carl evidence collect            # Default: SOC 2
/carl evidence collect --framework hipaa

/carl build hipaa/foundation      # HIPAA blueprints
/carl build hipaa/phi-storage

/carl ask "Is my S3 HIPAA compliant?"  # AI understands context
```

### 6.2 Multi-Framework Dashboard

```
/carl compliance overview

┌─────────────────────────────────────────────────┐
│           CARL Compliance Dashboard              │
├─────────────────────────────────────────────────┤
│                                                 │
│  SOC 2 Type II          HIPAA Security Rule    │
│  ██████████░░ 85%       ████████░░░░ 72%       │
│                                                 │
│  Critical: 2            Critical: 4            │
│  High: 5                High: 8                │
│  Medium: 12             Medium: 15             │
│                                                 │
│  Last Scan: 2 hours ago                        │
└─────────────────────────────────────────────────┘
```

---

## Implementation Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Framework Abstraction | `compliance_frameworks.py`, updated prompts, parameterized evidence |
| 1-2 | Control Mappings | `hipaa_controls.py`, updated architecture patterns |
| 2 | HIPAA Features | PHI detection, eligible services validation, BAA tracking |
| 2-3 | Blueprints | `hipaa/foundation`, `hipaa/phi-storage`, `hipaa/phi-database` |
| 3 | Reports & Evidence | HIPAA report template, evidence mapping |
| 3 | Slack Updates | `--framework` flag, multi-framework dashboard |

---

## Files to Create/Modify

### New Files
- `carl-app/src/knowledge/compliance_frameworks.py`
- `carl-app/src/knowledge/hipaa_controls.py`
- `carl-app/src/knowledge/hipaa_eligible_services.py`
- `carl-app/src/services/phi_detector.py`
- `carl-app/src/services/baa_tracker.py`
- `carl-app/src/templates/hipaa_report.html`

### Modified Files
- `carl-app/src/services/evidence_collector.py` - Add framework parameter
- `carl-app/src/services/bedrock_service.py` - Add HIPAA prompts
- `carl-app/src/services/ai_terraform_generator.py` - Add HIPAA context
- `carl-app/src/services/report_generator.py` - Multi-framework support
- `carl-app/src/handlers/slack_router.py` - `--framework` flag
- `carl-app/src/knowledge/architecture_patterns.py` - Add `hipaa_controls`
- `carl-app/src/knowledge/vpc_patterns.py` - Add `hipaa_controls`
- `carl-app/src/knowledge/kms_patterns.py` - Add `hipaa_controls`
- (all pattern files)

---

## Cost Impact

| Component | Monthly Cost |
|-----------|--------------|
| Amazon Macie (PHI detection) | $1-10/month (depends on S3 size) |
| Extended log retention (6 years) | ~$5/month additional |
| No other infrastructure changes | $0 |
| **Total Additional** | **~$6-15/month** |

---

## Success Criteria

- [ ] `/carl status --framework hipaa` returns HIPAA compliance score
- [ ] `/carl evidence collect --framework hipaa` maps to HIPAA controls
- [ ] `/carl build hipaa/foundation` generates valid, HIPAA-compliant Terraform
- [ ] AI answers reference HIPAA controls when framework=hipaa
- [ ] HIPAA report template generates auditor-ready documentation
- [ ] PHI detection identifies S3 buckets with health data
- [ ] Eligible services validation flags non-HIPAA services
