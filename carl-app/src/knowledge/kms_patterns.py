"""
AWS KMS Key Management Patterns for CARL Foundation Builder.

Comprehensive patterns for encryption key management, rotation,
and encryption-at-rest strategies.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# KMS KEY STRATEGY PATTERNS
# =============================================================================

KMS_KEY_STRATEGY_PATTERNS = ArchitectureDecision(
    question="What KMS key strategy should be implemented?",
    options=[
        DecisionOption(
            name="AWS Managed Keys Only",
            description="Use AWS managed keys for all encryption",
            when_to_use=[
                "Getting started with encryption",
                "Simple requirements",
                "No custom key policies needed",
                "Development environments",
            ],
            when_not_to_use=[
                "Need key rotation control",
                "Compliance requires customer-managed keys",
                "Need custom key policies",
                "SOC 2 production environments",
            ],
            pros=[
                "Free (no KMS key costs)",
                "Automatic rotation (yearly)",
                "No key management overhead",
                "Simple to use",
            ],
            cons=[
                "Can't control rotation schedule",
                "Can't disable or delete keys",
                "No custom key policies",
                "Limited auditability",
                "Can't grant cross-account access",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=[
                "AWS managed keys: Free",
                "API calls still charged: $0.03/10K",
            ],
            soc2_controls=["CC6.5"],
            hipaa_controls=["164.312(a)(2)(iv)"],  # Encryption and Decryption
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Single CMK per Service",
            description="One customer-managed key per AWS service",
            when_to_use=[
                "SOC 2 compliance",
                "Need key rotation control",
                "Most production environments",
                "Cost-conscious but need control",
            ],
            when_not_to_use=[
                "Need fine-grained access control",
                "Multi-tenant applications",
                "Strict data isolation requirements",
            ],
            pros=[
                "Balance of simplicity and control",
                "Lower cost than many keys",
                "Full key policy control",
                "Can enable/disable",
                "CloudTrail visibility",
            ],
            cons=[
                "Coarser access control",
                "Can't isolate by workload",
                "Single key compromise affects all",
            ],
            monthly_cost_range=(5.00, 20.00),
            cost_drivers=[
                "CMK: $1/mo per key",
                "5-10 keys typical (S3, RDS, EBS, Secrets, etc.)",
                "API calls: $0.03/10K requests",
            ],
            soc2_controls=["CC6.5", "C1.1"],
            hipaa_controls=["164.312(a)(2)(iv)", "164.312(c)(1)"],  # Encryption, Integrity
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Multi-Key Strategy (Per Workload/Environment)",
            description="Separate keys per workload and environment",
            when_to_use=[
                "Multi-tenant applications",
                "Need data isolation",
                "Different access controls per workload",
                "Strict compliance (HIPAA, PCI)",
            ],
            when_not_to_use=[
                "Simple single application",
                "Cost optimization priority",
                "High operational overhead concern",
            ],
            pros=[
                "Strong data isolation",
                "Fine-grained access control",
                "Least privilege per workload",
                "Blast radius containment",
            ],
            cons=[
                "Higher key costs",
                "More keys to manage",
                "More complex policies",
                "Harder to audit",
            ],
            monthly_cost_range=(20.00, 100.00),
            cost_drivers=[
                "CMK: $1/mo per key",
                "20-50+ keys for large environments",
                "API calls scale with usage",
            ],
            soc2_controls=["CC6.1", "CC6.5", "C1.1"],
            hipaa_controls=["164.312(a)(1)", "164.312(a)(2)(iv)", "164.312(c)(1)"],  # Access Control, Encryption, Integrity
            implementation_complexity="high",
            operational_overhead="high",
        ),
        DecisionOption(
            name="Centralized Key Management (Multi-Account)",
            description="Keys in central account, shared cross-account",
            when_to_use=[
                "Multi-account organization",
                "Centralized security team",
                "Want single key for same data across accounts",
                "Simplified key lifecycle",
            ],
            when_not_to_use=[
                "Need per-account isolation",
                "Accounts are fully independent",
                "No central security team",
            ],
            pros=[
                "Centralized key management",
                "Easier to audit",
                "Consistent key policies",
                "Fewer keys overall",
            ],
            cons=[
                "Cross-account key grants needed",
                "Dependency on central account",
                "More complex policies",
                "Single point of failure",
            ],
            monthly_cost_range=(10.00, 50.00),
            cost_drivers=[
                "Fewer total keys than distributed",
                "CMK: $1/mo per key",
                "Cross-account API calls charged",
            ],
            soc2_controls=["CC6.5", "C1.1"],
            hipaa_controls=["164.312(a)(2)(iv)", "164.312(c)(1)"],  # Encryption, Integrity
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Decision tree for KMS key strategy:

    1. What are your compliance requirements?
       None/Basic → AWS managed keys OK
       SOC 2 → Customer-managed keys (single per service)
       HIPAA/PCI/FedRAMP → Multi-key strategy

    2. How many accounts?
       1 account → Single CMK per service
       Multi-account, shared data → Centralized key management
       Multi-account, isolated → Per-account keys

    3. Do you need data isolation?
       YES (multi-tenant, regulated) → Multi-key strategy
       NO → Single CMK per service

    Recommended key architecture for most organizations:

    **Production Account:**
    - kms-prod-s3: S3 bucket encryption
    - kms-prod-rds: RDS/Aurora encryption
    - kms-prod-ebs: EBS volume encryption
    - kms-prod-secrets: Secrets Manager encryption
    - kms-prod-logs: CloudWatch Logs encryption
    - kms-prod-backup: AWS Backup encryption
    - kms-prod-sns: SNS topic encryption
    - kms-prod-sqs: SQS queue encryption

    **Key naming convention:**
    kms-{environment}-{service}-{optional-workload}

    Examples:
    - kms-prod-s3
    - kms-prod-rds-orderservice
    - kms-staging-ebs
    - kms-dev-secrets

    Key policy best practices:
    1. Always include key administrators
    2. Separate key admins from key users
    3. Enable key rotation (automatic yearly)
    4. Use condition keys (aws:PrincipalOrgID)
    5. Grant least privilege
    6. Document key purpose in description

    Services requiring KMS encryption:
    - S3 buckets (especially sensitive data)
    - RDS/Aurora databases
    - EBS volumes
    - Secrets Manager secrets
    - CloudWatch Logs (optional)
    - SNS topics (optional)
    - SQS queues (optional)
    - Lambda environment variables
    - EFS file systems
    - DynamoDB tables
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.5: Encryption of confidential information
    - C1.1: Encryption protects confidentiality

    KMS demonstrates:
    - Encryption at rest for all sensitive data
    - Key rotation (evidence of ongoing security)
    - Access control (who can use keys)
    - Audit trail (CloudTrail KMS events)

    Auditors want to see:
    - Customer-managed keys for production
    - Key rotation enabled
    - Key policies restricting access
    - CloudTrail logs of key usage
    - Documentation of key purpose
    """,
    common_mistakes=[
        "Using AWS managed keys in production (no rotation control)",
        "Not enabling automatic key rotation",
        "Overly permissive key policies",
        "Single key for everything (no isolation)",
        "Not documenting key purpose",
        "Forgetting KMS permissions in IAM policies",
    ],
)


# =============================================================================
# KEY ROTATION PATTERNS
# =============================================================================

KEY_ROTATION_PATTERNS = ArchitectureDecision(
    question="How should KMS key rotation be handled?",
    options=[
        DecisionOption(
            name="Automatic Yearly Rotation",
            description="Enable AWS automatic key rotation (yearly)",
            when_to_use=[
                "Standard security requirements",
                "Most production environments",
                "Want simplicity",
                "SOC 2 compliance",
            ],
            when_not_to_use=[
                "Need custom rotation schedule",
                "Compliance requires more frequent rotation",
            ],
            pros=[
                "Fully automated",
                "No downtime",
                "Old key material retained for decryption",
                "Transparent to applications",
            ],
            cons=[
                "Fixed yearly schedule",
                "Can't rotate on-demand",
                "Not all key types support it",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Automatic rotation is free"],
            soc2_controls=["CC6.5"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Manual Rotation with Aliases",
            description="Manual key rotation using key aliases",
            when_to_use=[
                "Need custom rotation schedule",
                "Compliance requires specific frequency",
                "Want rotation control",
                "Imported key material",
            ],
            when_not_to_use=[
                "Automatic rotation is sufficient",
                "Don't want operational overhead",
            ],
            pros=[
                "Control rotation timing",
                "Works with imported keys",
                "Can rotate on security event",
                "More flexibility",
            ],
            cons=[
                "Manual process",
                "Must update key ARN in resources",
                "Higher operational overhead",
                "Risk of downtime if not careful",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=[
                "New key: $1/mo",
                "Keep old key for decryption: $1/mo",
                "During overlap: $2/mo per rotated key",
            ],
            soc2_controls=["CC6.5"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Key rotation strategy:

    **Always:**
    - Enable automatic key rotation on all CMKs (if supported)
    - Document rotation schedule
    - Test key rotation in non-prod first

    **Automatic rotation behavior:**
    - Rotates every 365 days
    - Old key material kept for decryption
    - Same key ID and ARN
    - Transparent to applications
    - Free

    **When automatic rotation is NOT supported:**
    - Asymmetric keys
    - Keys in custom key stores
    - Keys with imported key material

    **Manual rotation process:**
    1. Create new CMK
    2. Update alias to point to new key
    3. Re-encrypt data with new key (if needed)
    4. Keep old key for decryption
    5. After cutover period, disable old key
    6. After retention period, delete old key

    **Rotation schedule recommendations:**
    - Standard: Yearly (automatic)
    - High security: Quarterly (manual)
    - Incident response: Immediate (manual)

    **Testing rotation:**
    ```bash
    # Check rotation status
    aws kms get-key-rotation-status --key-id KEY_ID

    # Enable rotation
    aws kms enable-key-rotation --key-id KEY_ID

    # Check last rotation (in CloudTrail)
    aws cloudtrail lookup-events --lookup-attributes \
      AttributeKey=ResourceName,AttributeValue=KEY_ID
    ```
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.5: Key rotation reduces risk of compromise

    Key rotation demonstrates:
    - Ongoing security maintenance
    - Reduced window of vulnerability
    - Compliance with best practices

    Auditors expect:
    - Evidence of key rotation (CloudTrail)
    - Documented rotation schedule
    - Rotation enabled on all production keys
    """,
    common_mistakes=[
        "Not enabling automatic rotation",
        "Deleting old key immediately after rotation",
        "Rotating keys without testing",
        "Not documenting rotation schedule",
        "Assuming manual rotation is better (automatic is simpler)",
    ],
)


# =============================================================================
# KEY POLICY PATTERNS
# =============================================================================

KEY_POLICY_PATTERNS = ArchitectureDecision(
    question="How should KMS key policies be structured?",
    options=[
        DecisionOption(
            name="Minimal Key Policy (Root Account)",
            description="Allow root account full access",
            when_to_use=[
                "Development environments",
                "Getting started",
                "Internal testing",
            ],
            when_not_to_use=[
                "Production environments",
                "Compliance requirements",
                "Need least privilege",
            ],
            pros=[
                "Simplest policy",
                "All IAM policies work",
                "No policy management",
            ],
            cons=[
                "Overly permissive",
                "No separation of key admin vs user",
                "Not compliant with security best practices",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Key policies are free"],
            soc2_controls=[],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard Key Policy (Least Privilege)",
            description="Separate key administrators and key users",
            when_to_use=[
                "Production environments",
                "SOC 2 compliance",
                "Most use cases",
                "Need audit trail",
            ],
            when_not_to_use=[
                "Development/sandbox environments",
            ],
            pros=[
                "Least privilege",
                "Separation of duties",
                "Clear access control",
                "Audit-friendly",
            ],
            cons=[
                "More complex",
                "Must maintain policy",
                "IAM + key policy both required",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Key policies are free"],
            soc2_controls=["CC6.1", "CC6.5"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Cross-Account Key Policy",
            description="Key shared across multiple accounts",
            when_to_use=[
                "Multi-account organization",
                "Centralized key management",
                "Shared data encryption",
            ],
            when_not_to_use=[
                "Single account",
                "Account isolation required",
            ],
            pros=[
                "Single key for cross-account data",
                "Centralized management",
                "Cost-effective",
            ],
            cons=[
                "Complex policy",
                "Grant management needed",
                "Cross-account dependency",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Key policies are free"],
            soc2_controls=["CC6.1", "CC6.5"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Key policy best practices:

    **Standard Key Policy Template:**
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "Enable IAM User Permissions",
          "Effect": "Allow",
          "Principal": {
            "AWS": "arn:aws:iam::ACCOUNT_ID:root"
          },
          "Action": "kms:*",
          "Resource": "*",
          "Condition": {
            "StringEquals": {
              "kms:ViaService": [
                "s3.REGION.amazonaws.com"
              ]
            }
          }
        },
        {
          "Sid": "Allow Key Administrators",
          "Effect": "Allow",
          "Principal": {
            "AWS": [
              "arn:aws:iam::ACCOUNT_ID:role/KeyAdminRole"
            ]
          },
          "Action": [
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
          ],
          "Resource": "*"
        },
        {
          "Sid": "Allow Key Usage",
          "Effect": "Allow",
          "Principal": {
            "AWS": [
              "arn:aws:iam::ACCOUNT_ID:role/ApplicationRole"
            ]
          },
          "Action": [
            "kms:Decrypt",
            "kms:DescribeKey",
            "kms:Encrypt",
            "kms:ReEncrypt*",
            "kms:GenerateDataKey*"
          ],
          "Resource": "*"
        }
      ]
    }
    ```

    **Cross-Account Key Policy Addition:**
    ```json
    {
      "Sid": "Allow External Account",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::EXTERNAL_ACCOUNT:root"
      },
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": "s3.REGION.amazonaws.com",
          "aws:PrincipalOrgID": "o-xxxxxxxxxx"
        }
      }
    }
    ```

    **Key Policy Security:**
    - Always separate key admins from key users
    - Use kms:ViaService to restrict to specific services
    - Use aws:PrincipalOrgID for Organization boundaries
    - Grant least privilege (Decrypt vs Encrypt vs both)
    - Document policy rationale

    **Common key policy statements:**
    - Key administrators: Full control except decrypt/encrypt
    - Key users: Encrypt, decrypt, generate data keys only
    - Service roles: Specific to service needs
    - Grant users: Can create grants (for cross-account)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: Key policies enforce access control
    - CC6.5: Encryption key access is restricted

    Key policies demonstrate:
    - Least privilege access to encryption keys
    - Separation of duties (admin vs user)
    - Audit trail (CloudTrail logs policy changes)

    Auditors review:
    - Key policy for each production key
    - Separation of admin and user roles
    - Restrictive policies (not root-only)
    """,
    common_mistakes=[
        "Allowing root account without conditions (too permissive)",
        "Same principal as admin and user (no separation)",
        "Not using kms:ViaService (allows any AWS service)",
        "Cross-account without aws:PrincipalOrgID (allows any account)",
        "Granting kms:* to users (should be limited actions)",
        "Not documenting key policy rationale",
    ],
)


# =============================================================================
# ENCRYPTION AT REST PATTERNS
# =============================================================================

ENCRYPTION_AT_REST_PATTERNS = ArchitectureDecision(
    question="What encryption-at-rest strategy should be implemented?",
    options=[
        DecisionOption(
            name="Service Default Encryption",
            description="Use service default encryption (AWS managed or none)",
            when_to_use=[
                "Development environments",
                "Non-sensitive data",
                "Cost optimization priority",
            ],
            when_not_to_use=[
                "Production environments",
                "Sensitive data",
                "Compliance requirements",
            ],
            pros=[
                "Simplest approach",
                "No KMS costs",
                "No key management",
            ],
            cons=[
                "May not encrypt by default",
                "No key control",
                "Not compliant",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Default encryption is free"],
            soc2_controls=[],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Encryption Everywhere (CMK)",
            description="Customer-managed keys for all data at rest",
            when_to_use=[
                "Production environments",
                "SOC 2 compliance",
                "Sensitive data",
                "Best practice",
            ],
            when_not_to_use=[
                "Development environments (can use AWS managed)",
            ],
            pros=[
                "Full encryption coverage",
                "Key rotation control",
                "Audit trail",
                "Compliance-ready",
            ],
            cons=[
                "KMS costs",
                "Key management overhead",
                "More complex",
            ],
            monthly_cost_range=(10.00, 50.00),
            cost_drivers=[
                "CMKs: $1/mo per key",
                "API calls: $0.03/10K",
                "10-20 keys typical",
            ],
            soc2_controls=["CC6.5", "C1.1"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Encryption-at-rest checklist:

    **Always Encrypt:**
    - RDS/Aurora databases (CMK)
    - S3 buckets with sensitive data (CMK)
    - EBS volumes (enable account default)
    - Secrets Manager secrets (CMK)
    - DynamoDB tables with PII (CMK)

    **Optionally Encrypt:**
    - CloudWatch Logs (CMK for sensitive logs)
    - SNS topics (CMK for sensitive messages)
    - SQS queues (CMK for sensitive data)
    - Lambda environment variables (CMK)

    **Implementation:**

    1. **Enable EBS encryption by default:**
    ```bash
    aws ec2 enable-ebs-encryption-by-default --region us-east-1
    aws ec2 modify-ebs-default-kms-key-id --kms-key-id KEY_ARN
    ```

    2. **S3 bucket encryption:**
    ```json
    {
      "Rules": [
        {
          "ApplyServerSideEncryptionByDefault": {
            "SSEAlgorithm": "aws:kms",
            "KMSMasterKeyID": "KEY_ARN"
          },
          "BucketKeyEnabled": true
        }
      ]
    }
    ```

    3. **RDS encryption:**
    - Enable during creation (can't add later)
    - Use KMS CMK
    - Snapshots inherit encryption

    4. **Secrets Manager:**
    - Enable KMS encryption
    - Separate key per environment

    **Enforcement:**
    - SCP: Deny unencrypted resource creation
    - Config Rules: Detect unencrypted resources
    - S3 Bucket Policies: Deny unencrypted uploads
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.5: Data at rest is encrypted
    - C1.1: Confidential data is protected

    Encryption at rest demonstrates:
    - Protection of sensitive data
    - Defense in depth
    - Industry best practices

    Auditors expect:
    - All production data encrypted
    - Customer-managed keys
    - Evidence of encryption (Config, API calls)
    """,
    common_mistakes=[
        "Not enabling EBS encryption by default",
        "Creating RDS without encryption (can't add later)",
        "S3 buckets without encryption",
        "Using AWS managed keys in production",
        "Not testing key policies before production",
    ],
)


def get_kms_patterns() -> dict:
    """Get all KMS key management patterns."""
    return {
        "kms_strategy": KMS_KEY_STRATEGY_PATTERNS,
        "key_rotation": KEY_ROTATION_PATTERNS,
        "key_policies": KEY_POLICY_PATTERNS,
        "encryption_at_rest": ENCRYPTION_AT_REST_PATTERNS,
    }
