"""
Backup and Disaster Recovery Patterns for AWS.

Patterns for AWS Backup, cross-region replication, and disaster recovery strategies.
"""

from knowledge.architecture_patterns import ArchitectureDecision

AWS_BACKUP_CENTRALIZED = ArchitectureDecision(
    name="Centralized Backup with AWS Backup",
    context="""
    Need centralized backup management for:
    - EC2 instances
    - EBS volumes
    - RDS databases
    - DynamoDB tables
    - EFS file systems
    - Automated scheduling
    - Retention policies
    - Compliance requirements (SOC 2, HIPAA)
    """,
    options={
        "AWS Backup (Recommended)": """
        **Architecture:**
        - AWS Backup service (centralized)
        - Backup plans (schedules + retention)
        - Backup vaults (encrypted storage)
        - Cross-region copy (disaster recovery)
        - CloudWatch alarms for failures
        - SNS notifications

        **Features:**
        - Centralized backup across services
        - Policy-based backup (tag-based)
        - Cross-region copy
        - Point-in-time recovery
        - Backup compliance reporting
        - Encrypted vaults (KMS)

        **Cost:** approx. $0.05/GB/month + restore fees
        - Storage: $0.05/GB/month (warm storage)
        - Cold storage: $0.01/GB/month (for compliance archives)
        - Restore: $0.02/GB
        - Example: 100GB daily backups, 30-day retention = approx. $5/month

        **Backup Schedule Example:**
        - Daily at 2am UTC
        - Retain 7 daily, 4 weekly, 12 monthly
        - Copy to second region for DR

        **Pros:**
        - Centralized management
        - Policy-based (tag resources for backup)
        - Cross-service support
        - SOC 2 compliant
        - Automated compliance reporting

        **Cons:**
        - Additional cost beyond service snapshots
        - Not all services supported (Lambda, CloudFormation)

        **When to use:** Production workloads, compliance requirements, multi-service backup
        """,

        "Service-Native Backups (Manual)": """
        **Architecture:**
        - RDS automated backups
        - EBS snapshots (manual or Lambda)
        - DynamoDB PITR
        - S3 versioning + lifecycle

        **Features:**
        - Free or included with service
        - Service-specific features

        **Cost:** approx. $0.05/GB/month (snapshot storage)
        - Usually same as AWS Backup
        - No centralized fees

        **Pros:**
        - No additional backup service cost
        - Service-native features

        **Cons:**
        - Manual management per service
        - No centralized dashboard
        - No cross-service policies
        - No compliance reporting
        - Must script cross-region copy

        **When to use:** Single service, tight budget, simple requirements
        """
    },
    recommendation="AWS Backup for production workloads",
    tradeoffs="""
    **AWS Backup vs Service-Native:**
    - AWS Backup: Centralized, policy-based, compliant, +$0 cost (same storage rates)
    - Service-Native: Decentralized, manual, no compliance reports, same storage cost

    **Why use AWS Backup:**
    - Centralized dashboard
    - Tag-based policies
    - Cross-region copy automation
    - Compliance reporting (SOC 2 requirement)

    **Cost is the same** for storage, so AWS Backup wins for operational simplicity
    """,
    related_controls=["A1.3", "CC9.2", "CC6.7"],
    aws_services=["backup", "s3", "kms", "cloudwatch", "sns"],
    estimated_cost="$5-50/month depending on data volume"
)

DISASTER_RECOVERY = ArchitectureDecision(
    name="Disaster Recovery Strategies",
    context="""
    Need disaster recovery plan with:
    - Recovery Time Objective (RTO)
    - Recovery Point Objective (RPO)
    - Multi-region failover
    - Data replication
    - Automated or manual failover
    """,
    options={
        "Pilot Light (Low Cost)": """
        **Architecture:**
        - Primary region: Full production stack
        - DR region: Minimal resources (data replication only)
        - Data continuously replicated (RDS, S3, DynamoDB)
        - Infrastructure as code (Terraform) ready to deploy

        **How it works:**
        1. Normal: Primary region serves traffic
        2. Disaster: Deploy infrastructure in DR region (Terraform apply)
        3. Start services with replicated data
        4. Update DNS to point to DR region

        **RTO:** 1-4 hours (time to deploy infrastructure)
        **RPO:** 5-15 minutes (replication lag)

        **Cost:** approx. $20-50/month (data replication only)
        - RDS cross-region replica: $30/month (db.t3.micro)
        - S3 cross-region replication: $0.02/GB
        - DynamoDB global tables: 2x write costs

        **Pros:**
        - Very cheap (no idle compute in DR)
        - Acceptable RTO for most businesses
        - Low RPO (continuous replication)

        **Cons:**
        - Manual failover
        - 1-4 hour downtime
        - Requires testing

        **When to use:** Most production workloads, RTO < 4 hours acceptable
        """,

        "Warm Standby (Medium Cost)": """
        **Architecture:**
        - Primary region: Full production stack
        - DR region: Scaled-down production (minimal instances)
        - Continuous data replication
        - Auto Scaling configured to scale up on failover

        **How it works:**
        1. Normal: DR region runs at 20-30% capacity
        2. Disaster: Auto Scaling scales up DR region
        3. Update DNS to DR region

        **RTO:** 10-30 minutes (scale up time)
        **RPO:** 5 minutes

        **Cost:** approx. $200-500/month
        - 20-30% of production cost always running
        - Data replication costs

        **Pros:**
        - Faster failover (10-30 min)
        - Pre-warmed environment
        - Easy to test

        **Cons:**
        - Higher cost (always running)
        - Still requires scaling

        **When to use:** RTO < 30 minutes required, can justify cost
        """,

        "Hot Standby / Active-Active (High Cost)": """
        **Architecture:**
        - Both regions fully active
        - Route53 health checks + failover routing
        - Automatic failover
        - Bi-directional replication (DynamoDB global tables)

        **How it works:**
        1. Normal: Both regions serve traffic
        2. Disaster: Route53 automatically routes to healthy region

        **RTO:** < 1 minute (automatic)
        **RPO:** < 1 minute (synchronous replication)

        **Cost:** approx. 2x production cost
        - Running full stack in both regions

        **Pros:**
        - Zero downtime failover
        - Automatic
        - Highest availability

        **Cons:**
        - Very expensive (2x cost)
        - Complex to manage
        - Data consistency challenges

        **When to use:** Mission-critical apps, financial services, SLA < 99.99%
        """,

        "Backup & Restore (Lowest Cost)": """
        **Architecture:**
        - AWS Backup with cross-region copy
        - No DR region infrastructure
        - Restore from backup on disaster

        **RTO:** 4-24 hours
        **RPO:** 24 hours (daily backups)

        **Cost:** approx. $5/month (backup storage only)

        **When to use:** Non-critical apps, RTO > 24 hours acceptable
        """
    },
    recommendation="Pilot Light for most production workloads",
    tradeoffs="""
    **DR Strategy vs Cost vs RTO:**

    | Strategy | Cost | RTO | RPO | When to Use |
    |----------|------|-----|-----|-------------|
    | Backup & Restore | $5/mo | 4-24h | 24h | Non-critical |
    | Pilot Light | $20-50/mo | 1-4h | 5min | Most production |
    | Warm Standby | $200-500/mo | 10-30min | 5min | RTO < 30min |
    | Hot Standby | 2x prod | <1min | <1min | Mission-critical |

    **Default choice:** Pilot Light (RTO 1-4h, RPO 5min, $20-50/mo)

    **Upgrade to Warm Standby if:** RTO < 30 minutes required
    **Upgrade to Hot Standby if:** RTO < 1 minute required (rare)
    """,
    related_controls=["A1.3", "CC9.2", "A1.2"],
    aws_services=["backup", "rds", "s3", "dynamodb", "route53", "cloudformation"],
    estimated_cost="$20-50/month for Pilot Light"
)

BACKUP_COMPLETE = ArchitectureDecision(
    name="Complete Production Backup & DR Solution",
    context="""
    Production backup and disaster recovery with all best practices:
    - Automated backups
    - Cross-region replication
    - Disaster recovery plan (Pilot Light)
    - Monitoring and alerting
    - Compliance reporting
    - SOC 2 compliant
    """,
    options={
        "Full Stack Backup & DR (Recommended)": """
        **Complete Architecture:**

        **Primary Region:**
        - Production workloads
        - AWS Backup with daily/weekly/monthly schedules
        - Backup vaults (KMS encrypted)
        - RDS with automated backups enabled
        - DynamoDB with PITR enabled
        - S3 with versioning + lifecycle policies

        **DR Region:**
        - RDS read replica (cross-region)
        - S3 cross-region replication
        - DynamoDB global tables (if needed)
        - Terraform code ready to deploy compute
        - AMIs copied to DR region
        - EBS snapshots copied to DR region

        **Backup Policy:**
        - Daily backups at 2am UTC
        - Retain: 7 daily, 4 weekly, 12 monthly
        - Cross-region copy (same retention)
        - Tag-based: All resources tagged "Backup=true"
        - Vault lock for compliance (prevents deletion)

        **Monitoring:**
        - CloudWatch alarms:
          * Backup job failures
          * Replication lag > 15 minutes
          * Backup vault not encrypted
          * Failed cross-region copy
        - SNS notifications
        - AWS Backup compliance reports

        **DR Runbook:**
        1. Detect disaster (monitoring, health checks)
        2. Run Terraform in DR region (15 minutes)
        3. Promote RDS replica to master (5 minutes)
        4. Update Route53 to point to DR region (5 minutes)
        5. Verify application functionality
        - Total RTO: 30-60 minutes

        **Testing:**
        - Monthly DR drill (automated with Lambda)
        - Quarterly full failover test
        - Document lessons learned

        **SOC 2 Controls Addressed:**
        - A1.3: Recovery procedures (backups + DR plan)
        - CC9.2: Business continuity (DR tested quarterly)
        - CC6.7: Encryption (KMS-encrypted backups)
        - CC7.2: Monitoring (backup success/failure alarms)
        - CC4.1: Ongoing evaluations (monthly DR drills)

        **Cost Breakdown:** approx. $80-150/month
        - AWS Backup storage: $20-40/month (200GB with retention)
        - RDS read replica (DR): $30-60/month (db.t3.micro or small)
        - S3 cross-region replication: $10-20/month
        - EBS snapshot copies: $5-10/month
        - DynamoDB global tables: Variable (2x write costs)
        - CloudWatch: $5/month

        **Terraform Modules Needed:**
        - AWS Backup plans and vaults
        - Backup selection (tag-based)
        - Cross-region backup copy
        - RDS instance with read replica
        - S3 buckets with replication
        - DynamoDB tables with PITR
        - CloudWatch alarms
        - SNS topics
        - Lambda for DR testing (optional)
        - IAM roles for AWS Backup

        **Pros:**
        - Production-ready
        - SOC 2 compliant
        - Automated backups
        - DR tested regularly
        - Low RTO (30-60 min)
        - Low RPO (5 min)

        **Cons:**
        - Requires DR testing discipline
        - Slightly higher cost

        **When to use:** All production applications
        """
    },
    recommendation="Full stack with AWS Backup, cross-region DR, and monthly testing",
    tradeoffs="No tradeoffs - this is the complete, production-ready setup",
    related_controls=["A1.3", "CC9.2", "CC6.7", "CC7.2", "CC4.1"],
    aws_services=["backup", "rds", "s3", "dynamodb", "cloudwatch", "sns", "kms", "lambda"],
    estimated_cost="$80-150/month"
)

# Export patterns
PATTERNS = [
    AWS_BACKUP_CENTRALIZED,
    DISASTER_RECOVERY,
    BACKUP_COMPLETE
]
