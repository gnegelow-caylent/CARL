"""
RDS Deployment and Security Patterns for CARL.

Patterns for Amazon RDS deployment strategies, security, and backup/recovery.

SOC 2 Relevance:
- CC6.1: Logical and physical access controls
- CC6.6: Encryption at rest and in transit
- A1.2: System backup and recovery
- A1.3: Business continuity
"""

from dataclasses import dataclass
from typing import List
from .architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    SOC2Mapping,
)


# Pattern 1: RDS Deployment Strategy
RDS_DEPLOYMENT_STRATEGY_PATTERNS = ArchitectureDecision(
    category="Database - RDS",
    question="What RDS deployment strategy should be implemented?",
    context="""
RDS deployment strategy determines availability, performance, and cost. Single-AZ
is for development, Multi-AZ for production, read replicas for read-heavy workloads,
and multi-region for disaster recovery.

Deployment options:
- Single-AZ: One instance in one availability zone
- Multi-AZ: Standby replica in second AZ (automatic failover)
- Read replicas: Asynchronous replication for read scaling
- Multi-region: Cross-region replication for DR
""",
    options=[
        DecisionOption(
            name="Single-AZ Development",
            description="""
Single RDS instance in one availability zone for development or testing.

Configuration:
- Single db.t3.micro or db.t3.small instance
- One availability zone
- Public or private subnet (private recommended)
- Security group restricts access
- Automated backups (7 days retention)
- No standby replica (downtime during maintenance)

Use cases:
- Development environments
- Testing and staging (non-critical)
- Proof of concepts
- Cost optimization for non-production
""",
            pros=[
                "Lowest cost (approx. $15/month for db.t3.micro)",
                "Simple to set up",
                "Good for development",
                "Automated backups included",
            ],
            cons=[
                "No high availability (single point of failure)",
                "Downtime during maintenance windows",
                "AZ failure = database unavailable",
                "Not suitable for production",
            ],
            cost_factors=[
                "RDS instance: db.t3.micro = approx. $15/month",
                "Storage: $0.115/GB-month (gp3)",
                "Backups: Same-region snapshots free",
                "For db.t3.micro + 20 GB: $15 + $2.30 = $17.30/month",
            ],
            monthly_cost_range=(15.00, 100.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Security groups and IAM restrict database access",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup",
                    how_it_helps="Automated backups (7 days retention)",
                ),
            ],
        ),
        DecisionOption(
            name="Multi-AZ Production",
            description="""
Multi-AZ RDS deployment with automatic failover for production workloads.

Implementation:
- Primary instance in one AZ
- Standby replica in second AZ (synchronous replication)
- Automatic failover (~60 seconds)
- DNS endpoint (CNAME) automatically updates on failover
- Automated backups (7-35 days retention)
- Maintenance windows (minor version upgrades on standby first)

How Multi-AZ works:
1. Writes go to primary instance
2. Synchronous replication to standby
3. If primary fails, automatic failover to standby
4. DNS endpoint updates automatically
5. Application reconnects (no code changes needed)

Failover scenarios:
- AZ failure
- Instance failure
- Storage failure
- Network issues
- Planned maintenance

Cost:
- Multi-AZ doubles compute cost (2 instances)
- Storage charged once (replicated automatically)
""",
            pros=[
                "High availability (99.95% SLA)",
                "Automatic failover (~60 seconds)",
                "Zero data loss (synchronous replication)",
                "No code changes needed (DNS failover)",
                "Standby used for backups (no primary I/O impact)",
                "Best practice for production",
            ],
            cons=[
                "Double compute cost (2 instances)",
                "Standby not used for reads (idle unless failover)",
                "Slight write latency (synchronous replication)",
            ],
            cost_factors=[
                "RDS instance: db.t3.small Multi-AZ = approx. $60/month (2x Single-AZ)",
                "Storage: $0.115/GB-month (charged once, replicated)",
                "Backups: Free for retention <= DB size",
                "For db.t3.small Multi-AZ + 100 GB: $60 + $11.50 = $71.50/month",
            ],
            monthly_cost_range=(70.00, 500.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Security groups and IAM control access",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup and recovery",
                    how_it_helps="Multi-AZ + automated backups ensure recoverability",
                ),
                SOC2Mapping(
                    control_id="A1.3",
                    control_name="Business continuity",
                    how_it_helps="Automatic failover ensures minimal downtime",
                ),
            ],
        ),
        DecisionOption(
            name="Multi-AZ with Read Replicas",
            description="""
Multi-AZ primary with read replicas for read-heavy workloads and reporting.

Implementation:
- Multi-AZ primary (write instance)
- 1-5 read replicas in same or different AZs
- Read replicas asynchronously replicate from primary
- Read traffic offloaded to replicas
- Primary handles writes only
- Replicas can be promoted to primary (manual or automatic)

Read replica uses:
- Offload read traffic (reporting, analytics)
- Different instance types (e.g., r6g for memory-intensive reads)
- Cross-region for disaster recovery
- Blue/green deployments (promote replica to new primary)

Replication lag:
- Asynchronous replication (typically <1 second lag)
- Monitor ReplicaLag CloudWatch metric
- Application must handle eventual consistency

Architecture:
```
Primary (Multi-AZ) ← Writes
  ↓
  ├─ Read Replica 1 (us-east-1a) ← Reads
  ├─ Read Replica 2 (us-east-1b) ← Reads
  └─ Read Replica 3 (us-west-2)  ← DR
```
""",
            pros=[
                "Read scaling (offload reads to replicas)",
                "Different instance types per workload",
                "Cross-region replicas for disaster recovery",
                "Can promote replica to primary (failover option)",
                "Minimal impact on primary (backups from replica)",
            ],
            cons=[
                "Increased cost (pay for each replica)",
                "Replication lag (eventual consistency)",
                "Application must route reads to replicas",
                "Cross-region data transfer costs",
            ],
            cost_factors=[
                "Primary: db.m5.large Multi-AZ = approx. $280/month",
                "Read replica: db.m5.large = approx. $140/month each",
                "Storage: $0.115/GB-month per instance",
                "Cross-region replication: $0.02/GB data transfer",
                "For primary + 2 replicas (same region) + 500 GB: $280 + $280 (replicas) + $172 (storage) = $732/month",
            ],
            monthly_cost_range=(400.00, 2000.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Security groups per instance",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup and recovery",
                    how_it_helps="Backups from replica, cross-region for DR",
                ),
                SOC2Mapping(
                    control_id="A1.3",
                    control_name="Business continuity",
                    how_it_helps="Read replicas can be promoted for disaster recovery",
                ),
            ],
        ),
        DecisionOption(
            name="Multi-Region Deployment",
            description="""
Multi-region RDS deployment for disaster recovery and geographic distribution.

Implementation:
- Primary Multi-AZ in primary region (e.g., us-east-1)
- Cross-region read replica in DR region (e.g., us-west-2)
- Read replica in DR region is also Multi-AZ (for DR HA)
- Automated backups in both regions
- Disaster recovery procedure:
  1. Promote cross-region replica to primary
  2. Update application DNS to DR region
  3. Monitor and verify functionality

Multi-region architecture:
```
Primary Region (us-east-1):
  Primary Multi-AZ ← Writes
    ↓
    ├─ Read Replica 1 (local reads)
    └─ Cross-region replication
         ↓
DR Region (us-west-2):
  Read Replica Multi-AZ ← DR + local reads
    ↓
    └─ Can be promoted to primary
```

Disaster recovery testing:
- Quarterly DR drills (promote replica, test application)
- Measure RTO (Recovery Time Objective) and RPO (Recovery Point Objective)
- RTO: ~15 minutes (replica promotion + DNS update)
- RPO: Replication lag (typically <5 seconds)
""",
            pros=[
                "Geographic disaster recovery",
                "Low RPO (replication lag typically <5 seconds)",
                "RTO ~15 minutes (replica promotion)",
                "Cross-region read replicas serve local users",
                "Automated replication (no manual sync)",
            ],
            cons=[
                "Significant cost (2 Multi-AZ deployments + replicas)",
                "Cross-region data transfer costs ($0.02/GB)",
                "Increased operational complexity",
                "Must test DR procedures regularly",
            ],
            cost_factors=[
                "Primary Multi-AZ: db.m5.xlarge = approx. $560/month",
                "DR replica Multi-AZ: db.m5.xlarge = approx. $560/month",
                "Read replicas: db.m5.large × 2 = approx. $280/month",
                "Storage: $0.115/GB-month × 4 instances",
                "Cross-region replication: $0.02/GB (data transfer)",
                "For 1 TB database with 500 GB/month replication: $560 (primary) + $560 (DR) + $280 (replicas) + $460 (storage) + $10 (xfer) = approx. $1,870/month",
            ],
            monthly_cost_range=(1500.00, 5000.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup and recovery",
                    how_it_helps="Multi-region backups ensure data recoverability",
                ),
                SOC2Mapping(
                    control_id="A1.3",
                    control_name="Business continuity",
                    how_it_helps="Cross-region failover for geographic disasters",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Single-AZ when:
- Development or testing environment
- Non-critical data
- Cost is primary concern
- Acceptable to have downtime during maintenance
- No production use

Choose Multi-AZ when:
- Production workloads
- Need high availability (99.95% SLA)
- Cannot accept downtime during maintenance
- Most common choice for production databases

Choose Multi-AZ with Read Replicas when:
- Read-heavy workloads (reporting, analytics)
- Need to scale reads independently
- Want different instance types for different workloads
- Cross-region for disaster recovery consideration

Choose Multi-Region when:
- Geographic disaster recovery required
- Compliance requires multi-region data presence
- Need low-latency access in multiple regions
- Budget supports $1500-5000/month
- Have expertise in DR procedures
""",
    examples=[
        {
            "scenario": "Development environment for testing application",
            "recommendation": "Single-AZ Development",
            "reasoning": "Development data, acceptable downtime. Single-AZ keeps costs low (approx. $20/month).",
        },
        {
            "scenario": "Production SaaS application database",
            "recommendation": "Multi-AZ Production",
            "reasoning": "Production requires high availability. Multi-AZ provides automatic failover. 99.95% SLA.",
        },
        {
            "scenario": "E-commerce site with heavy read traffic for product catalog",
            "recommendation": "Multi-AZ with Read Replicas",
            "reasoning": "Multi-AZ primary for writes. Read replicas offload product catalog queries. Scale reads independently.",
        },
        {
            "scenario": "Financial services with disaster recovery requirements",
            "recommendation": "Multi-Region Deployment",
            "reasoning": "Cross-region replica in DR region. RTO ~15 minutes. RPO ~5 seconds. Quarterly DR testing.",
        },
    ],
)


# Pattern 2: RDS Security
RDS_SECURITY_PATTERNS = ArchitectureDecision(
    category="Database - RDS",
    question="What RDS security strategy should be implemented?",
    context="""
RDS security encompasses network isolation, encryption, authentication, and monitoring.
Strong database security prevents unauthorized access and data breaches.

Security layers:
- Network: VPC private subnets, security groups
- Encryption: At rest (KMS), in transit (TLS)
- Authentication: IAM database authentication, Secrets Manager
- Monitoring: Enhanced Monitoring, Performance Insights, audit logs
""",
    options=[
        DecisionOption(
            name="Default VPC with Basic Security",
            description="""
RDS in default VPC with basic security configuration.

Configuration:
- Default VPC (automatically created)
- Public or private subnet
- Security group allows 3306/5432 from application security group
- Master username/password (stored in Secrets Manager recommended)
- No encryption at rest (default)
- TLS optional for client connections
- Standard CloudWatch metrics

Not recommended for production due to:
- Default VPC shared with other resources
- No encryption at rest
- TLS not enforced
""",
            pros=[
                "Quick to set up",
                "No VPC design needed",
                "Standard security group rules",
            ],
            cons=[
                "Default VPC not isolated",
                "No encryption at rest",
                "TLS not enforced (data in transit unencrypted)",
                "Not suitable for compliance (SOC 2, HIPAA, PCI-DSS)",
            ],
            cost_factors=[
                "No additional security costs",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Security groups restrict access (basic)",
                ),
            ],
        ),
        DecisionOption(
            name="Private Subnet with Encryption",
            description="""
RDS in private subnets with encryption at rest and in transit.

Implementation:
- Custom VPC with private subnets (no internet routing)
- DB subnet group spans multiple AZs
- Security group allows 3306/5432 from application security group only
- Encryption at rest with KMS customer-managed key
- TLS enforced for client connections:
  - MySQL: REQUIRE SSL in user grants
  - PostgreSQL: rds.force_ssl=1
- Master password in Secrets Manager with automatic rotation
- Enhanced Monitoring (1-minute granularity)
- CloudWatch Logs for slow queries, audit logs

Network isolation:
- RDS in private subnets (no internet gateway route)
- Only application instances can reach database
- No public accessibility

Encryption:
- At rest: KMS CMK encrypts storage, backups, snapshots, replicas
- In transit: TLS 1.2+ enforced
- Secrets Manager rotates master password every 30 days
""",
            pros=[
                "Private subnets isolate database",
                "Encryption at rest and in transit",
                "Secrets Manager automatic rotation",
                "Enhanced Monitoring provides detailed metrics",
                "TLS enforced (data in transit encrypted)",
                "Best practice for production",
            ],
            cons=[
                "Requires VPC design",
                "KMS key costs ($1/month)",
                "Enhanced Monitoring costs (approx. $3/month per instance)",
                "Secrets Manager costs ($0.40/secret/month)",
            ],
            cost_factors=[
                "KMS key: $1/month",
                "Enhanced Monitoring: approx. $3/month per instance",
                "Secrets Manager: $0.40/secret/month + rotation Lambda (approx. $1/month)",
                "For Multi-AZ: $1 (KMS) + $3 (monitoring) + $1.40 (Secrets) = $5.40/month overhead",
            ],
            monthly_cost_range=(5.00, 20.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Private subnets + security groups restrict access",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="KMS encryption at rest, TLS enforced in transit",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Enhanced Monitoring + CloudWatch Logs",
                ),
            ],
        ),
        DecisionOption(
            name="Secrets Manager Rotation with IAM Auth",
            description="""
Enterprise RDS security with Secrets Manager rotation and IAM database authentication.

Implementation:
- All features from Private Subnet with Encryption
- IAM database authentication:
  - No password needed (uses IAM token)
  - Token valid for 15 minutes
  - Lambda and EC2 authenticate via IAM role
  - Eliminates password management
- Secrets Manager automatic rotation (30 days)
- Performance Insights (7 days free, 2 years retention optional)
- Database activity monitoring via audit logs
- Security Hub integration for findings

IAM authentication workflow:
1. Application IAM role has rds-db:connect permission
2. Application generates auth token using IAM credentials
3. Connects to RDS using token (no password)
4. Token expires after 15 minutes
5. New token generated for next connection

Benefits:
- No database passwords to manage
- IAM policies control database access
- CloudTrail logs all authentication attempts
- Token auto-expires (short-lived credentials)

Performance Insights:
- 7 days retention free
- Identify slow queries and bottlenecks
- Drill down into query performance
- 2 years retention: $0.09/vCPU/month
""",
            pros=[
                "IAM authentication eliminates password management",
                "Secrets Manager automatic rotation for master password",
                "Performance Insights identifies slow queries",
                "Comprehensive audit logging",
                "CloudTrail logs authentication attempts",
            ],
            cons=[
                "IAM auth requires application code changes",
                "Performance Insights retention costs (approx. $2/month for db.t3.small)",
                "Audit logs generate significant CloudWatch Logs volume",
            ],
            cost_factors=[
                "KMS: $1/month",
                "Enhanced Monitoring: approx. $3/month",
                "Secrets Manager: $1.40/month",
                "Performance Insights (2yr retention): approx. $2/month (db.t3.small = 2 vCPU × $0.09)",
                "Audit logs: approx. $5-20/month (depends on query volume)",
                "Total: approx. $12-27/month overhead",
            ],
            monthly_cost_range=(12.00, 50.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM authentication with short-lived tokens",
                ),
                SOC2Mapping(
                    control_id="CC6.2",
                    control_name="Authentication",
                    how_it_helps="IAM-based authentication, no passwords",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="KMS encryption + TLS enforced",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Performance Insights + audit logs + Enhanced Monitoring",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise with Encryption and Compliance Logging",
            description="""
Comprehensive RDS security for enterprise with advanced encryption and compliance.

Implementation:
- All features from Secrets Manager Rotation with IAM Auth
- Encryption best practices:
  - KMS CMK with automatic key rotation
  - Envelope encryption for data
  - Encrypted backups and snapshots
  - Encrypted read replicas
- Advanced monitoring:
  - Database Activity Streams (DAS) for real-time monitoring:
    - Kinesis Data Streams receives all database activity
    - Lambda processes and stores in S3 for audit
    - Near real-time detection of suspicious activity
  - GuardDuty RDS Protection (malicious activity detection)
  - Config rules enforce security policies:
    - rds-instance-public-access-check
    - rds-snapshot-encrypted
    - rds-snapshots-public-prohibited
- VPC Flow Logs for network traffic analysis
- Security Hub aggregates all findings
- Automated remediation for non-compliant configurations

Database Activity Streams:
- Captures all database activity (queries, connections, DDL)
- Immutable audit trail (cannot be modified by DB admin)
- Encrypted in Kinesis (no plaintext access)
- Compliance requirement for PCI-DSS, HIPAA

GuardDuty RDS Protection:
- Detects suspicious login attempts
- Identifies anomalous database queries
- Alerts on potential data exfiltration
""",
            pros=[
                "Comprehensive encryption (data, backups, replicas)",
                "Database Activity Streams provide immutable audit trail",
                "GuardDuty detects threats in real-time",
                "Config rules enforce security policies",
                "Meets strictest compliance (SOC 2, PCI-DSS, HIPAA)",
            ],
            cons=[
                "High complexity (many security services)",
                "Database Activity Streams significant cost (approx. $0.30/hour = $216/month)",
                "GuardDuty RDS costs (approx. $0.012/GB analyzed)",
                "Alert fatigue if not properly tuned",
            ],
            cost_factors=[
                "KMS: $1/month + key rotation (free)",
                "Enhanced Monitoring: approx. $3/month",
                "Performance Insights (2yr): approx. $2/month",
                "Database Activity Streams: approx. $216/month per instance",
                "GuardDuty RDS: approx. $5-15/month",
                "Config rules: $2/rule × 3 = $6/month",
                "Security Hub: approx. $1.20/account/month",
                "VPC Flow Logs: approx. $10-50/month",
                "Total: approx. $244-294/month overhead per instance",
            ],
            monthly_cost_range=(250.00, 500.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM auth + Database Activity Streams audit all access",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Comprehensive encryption (data, backups, activity streams)",
                ),
                SOC2Mapping(
                    control_id="CC6.8",
                    control_name="Malicious software prevention",
                    how_it_helps="GuardDuty detects threats and anomalies",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Database Activity Streams + GuardDuty + Enhanced Monitoring",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Immutable audit trail via Database Activity Streams",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Default VPC when:
- NEVER for production (security anti-pattern)
- Only for learning/experimentation

Choose Private Subnet with Encryption when:
- Production workloads
- Need encryption at rest and in transit
- Moderate security requirements
- Most common choice for production RDS

Choose Secrets Manager Rotation with IAM Auth when:
- Production with high security needs
- Want to eliminate database passwords
- Need performance monitoring (slow query analysis)
- Compliance requires audit logging

Choose Enterprise with Encryption when:
- Enterprise with strict compliance (SOC 2, PCI-DSS, HIPAA)
- Need immutable audit trail (Database Activity Streams)
- Real-time threat detection required
- Budget supports $250-500/month per instance
- Have expertise in AWS security services
""",
    examples=[
        {
            "scenario": "Development database for testing",
            "recommendation": "Private Subnet with Encryption",
            "reasoning": "Even for dev, use encryption best practices. Private subnets isolate database. Low overhead cost (approx. $5/month).",
        },
        {
            "scenario": "Production SaaS application database",
            "recommendation": "Secrets Manager Rotation with IAM Auth",
            "reasoning": "IAM authentication for applications. Secrets Manager rotates master password. Performance Insights identifies bottlenecks.",
        },
        {
            "scenario": "Healthcare application with HIPAA requirements",
            "recommendation": "Enterprise with Encryption and Compliance Logging",
            "reasoning": "Database Activity Streams provide audit trail for HIPAA. GuardDuty detects threats. Config rules enforce security policies.",
        },
    ],
)


# Pattern 3: RDS Backup and Recovery
RDS_BACKUP_RECOVERY_PATTERNS = ArchitectureDecision(
    category="Database - RDS",
    question="What RDS backup and recovery strategy should be implemented?",
    context="""
RDS backup and recovery strategy determines recovery point objective (RPO) and
recovery time objective (RTO). Automated backups provide point-in-time recovery,
snapshots enable long-term retention, and cross-region backups support disaster recovery.

Backup types:
- Automated backups: Daily snapshots + transaction logs (1-35 days retention)
- Manual snapshots: User-initiated, indefinite retention
- Point-in-time recovery (PITR): Restore to any second within retention period
- Cross-region backups: Replicate to DR region
""",
    options=[
        DecisionOption(
            name="Default Backups (7 Days)",
            description="""
RDS default automated backups with 7-day retention.

Configuration:
- Automated daily backups (default enabled)
- 7-day retention period (default)
- Backup window: 30-minute window (e.g., 03:00-03:30 UTC)
- Point-in-time recovery to any second within 7 days
- Backups stored in S3 (AWS-managed)
- Transaction logs backed up every 5 minutes

Restoration process:
1. Restore from automated backup or PITR
2. Creates new RDS instance (cannot restore in-place)
3. Update application connection string
4. RTO: ~30 minutes (depends on database size)
5. RPO: Up to 5 minutes (transaction log frequency)
""",
            pros=[
                "Automated (no manual intervention)",
                "Free backup storage (up to DB size)",
                "Point-in-time recovery included",
                "Covers most recovery scenarios",
            ],
            cons=[
                "Only 7-day retention (short for some use cases)",
                "Backups deleted when RDS instance deleted",
                "No cross-region backups (single region only)",
                "RTO ~30 minutes (may be too long for critical systems)",
            ],
            cost_factors=[
                "Backup storage: Free (up to 100% of DB size)",
                "Beyond DB size: $0.095/GB-month",
                "For 100 GB database with 7-day retention: $0 (within free tier)",
            ],
            monthly_cost_range=(0, 10.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup",
                    how_it_helps="Automated daily backups with 7-day retention",
                ),
            ],
        ),
        DecisionOption(
            name="Extended Retention with PITR (35 Days)",
            description="""
Extended automated backup retention with 35-day point-in-time recovery.

Implementation:
- Automated backups with 35-day retention (maximum)
- Point-in-time recovery to any second within 35 days
- Weekly manual snapshots for long-term retention:
  - Manual snapshots never expire (indefinite retention)
  - Tag with date and purpose
  - Lifecycle policy can delete old snapshots
- Backup monitoring with CloudWatch alarms:
  - Alert if backup fails
  - Alert if backup storage exceeds threshold

Backup strategy:
- Automated: 35-day PITR (operational recovery)
- Manual weekly: Long-term retention (compliance, DR testing)
- Manual pre-change: Before major schema changes (rollback capability)

Manual snapshot use cases:
- Compliance requires 1-year retention
- Pre-production deployment (rollback option)
- DR testing (restore snapshot in DR region)
""",
            pros=[
                "35-day PITR (covers month-end scenarios)",
                "Manual snapshots for indefinite retention",
                "Backup monitoring with alarms",
                "Can restore to any point in 35 days",
            ],
            cons=[
                "Backup storage costs beyond DB size",
                "Manual snapshots require management (lifecycle policies)",
                "Still single-region (no geographic DR)",
            ],
            cost_factors=[
                "Backup storage: $0.095/GB-month (beyond DB size)",
                "For 200 GB database with 35-day retention:",
                "  - ~400 GB backup storage (2x DB size with logs)",
                "  - First 200 GB free, next 200 GB = $19/month",
                "Manual snapshots: $0.095/GB-month",
                "For 5 weekly snapshots (200 GB each): $95/month",
                "Total: $19 (automated) + $95 (manual) = $114/month",
            ],
            monthly_cost_range=(20.00, 150.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup",
                    how_it_helps="35-day PITR + manual snapshots for long-term retention",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch alarms monitor backup success",
                ),
            ],
        ),
        DecisionOption(
            name="Cross-Region Backups for Disaster Recovery",
            description="""
Automated backups with cross-region replication for geographic disaster recovery.

Implementation:
- All features from Extended Retention (35 days)
- Cross-region automated backup replication:
  - Primary region: us-east-1
  - DR region: us-west-2
  - Automated backups replicated to DR region
  - Manual snapshots can also be copied
- Disaster recovery testing quarterly:
  - Restore snapshot in DR region
  - Test application connectivity
  - Measure RTO and RPO
- Backup encryption in both regions (KMS CMK)

Cross-region backup workflow:
1. Automated backup in primary region
2. AWS replicates to DR region automatically
3. Backup encrypted with DR region KMS key
4. In DR scenario:
   a. Restore backup in DR region
   b. Create read replica from DR backup (Multi-AZ)
   c. Promote to primary
   d. Update application DNS
5. RTO: ~45 minutes (restore + DNS update)
6. RPO: Backup frequency (5 minutes for transaction logs)

Cost optimization:
- Delete old cross-region backups (retain 7 days in DR region)
- Use Backup Vault for centralized backup management
""",
            pros=[
                "Geographic disaster recovery",
                "Automated cross-region replication",
                "DR region backups ready for restoration",
                "Encrypted backups in both regions",
                "Quarterly DR testing ensures readiness",
            ],
            cons=[
                "Cross-region storage costs ($0.095/GB-month per region)",
                "Cross-region data transfer costs ($0.02/GB)",
                "Increased complexity (multi-region management)",
                "Must manage KMS keys in both regions",
            ],
            cost_factors=[
                "Backup storage (primary): $20/month",
                "Backup storage (DR): $20/month (7-day retention in DR)",
                "Cross-region replication: $0.02/GB",
                "  - 200 GB database × 30 days = 6 TB/month = $120/month",
                "KMS keys: $2/month (one per region)",
                "Total: $20 (primary) + $20 (DR) + $120 (replication) + $2 (KMS) = $162/month",
            ],
            monthly_cost_range=(150.00, 500.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup",
                    how_it_helps="Cross-region backups ensure geographic redundancy",
                ),
                SOC2Mapping(
                    control_id="A1.3",
                    control_name="Business continuity",
                    how_it_helps="DR region backups support disaster recovery",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Backup Strategy with AWS Backup",
            description="""
Comprehensive enterprise backup strategy with AWS Backup, lifecycle policies,
and automated disaster recovery testing.

Implementation:
- AWS Backup centralized backup management:
  - Backup plans define retention, frequency, regions
  - Supports RDS, Aurora, EBS, EFS, DynamoDB, S3
  - Cross-account backup (copy to security account)
  - Backup Vault Lock (WORM - write once, read many)
- Backup strategy:
  - Hourly backups retained for 24 hours (RPO 1 hour)
  - Daily backups retained for 35 days
  - Weekly backups retained for 1 year
  - Monthly backups retained for 7 years (compliance)
- Cross-region replication to 2 DR regions (us-west-2, eu-west-1)
- Automated DR testing:
  - Monthly: Automated restore in DR region
  - Lambda validates connectivity and data integrity
  - Cleanup after test
  - Alert if DR test fails
- Compliance reporting:
  - AWS Backup provides compliance dashboard
  - Automated evidence for auditors (backup completion, retention)

AWS Backup Vault Lock:
- Immutable backups (cannot be deleted by anyone)
- Compliance mode: Even root cannot delete
- Supports SOC 2, HIPAA, PCI-DSS requirements
- Prevents ransomware from deleting backups

Lifecycle policies:
- Transition old backups to cold storage (AWS Backup Cold Storage)
- Cold storage: $0.025/GB-month (vs. $0.095/GB-month warm)
- 90-day retrieval window for cold storage
""",
            pros=[
                "Centralized backup management (AWS Backup)",
                "Multiple retention policies (hourly, daily, weekly, monthly)",
                "Cross-account backups (security isolation)",
                "Backup Vault Lock prevents deletion (ransomware protection)",
                "Automated DR testing with validation",
                "Lifecycle policies reduce costs (cold storage)",
                "Comprehensive compliance reporting",
            ],
            cons=[
                "Very high complexity (AWS Backup configuration)",
                "Significant costs ($500-2000/month depending on retention)",
                "Cross-account and cross-region add complexity",
                "Automated DR testing requires Lambda development",
            ],
            cost_factors=[
                "AWS Backup: $0.50/GB-month (warm storage)",
                "Cold storage: $0.025/GB-month (after 90 days)",
                "Cross-region replication: $0.02/GB",
                "For 500 GB database with retention policies:",
                "  - Daily (35 days): 500 GB × 35 × $0.50 = $8,750 (transition to cold)",
                "  - Monthly (7 years): 500 GB × 12 × 7 × $0.025 = $1,050/month",
                "  - Cross-region (2 regions): +$1,050/month",
                "Realistic with lifecycle: approx. $100-500/month",
            ],
            monthly_cost_range=(100.00, 2000.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Backup",
                    how_it_helps="AWS Backup provides centralized, automated backups",
                ),
                SOC2Mapping(
                    control_id="A1.3",
                    control_name="Business continuity",
                    how_it_helps="Automated DR testing + cross-region backups",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Encrypted backups with Backup Vault Lock",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="AWS Backup compliance dashboard and reporting",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Default Backups when:
- Development or staging environment
- 7-day recovery window sufficient
- Budget-conscious
- No compliance requirements

Choose Extended Retention with PITR when:
- Production workloads
- Need 35-day recovery window
- Manual snapshots for compliance (1-year retention)
- Most common choice for production

Choose Cross-Region Backups when:
- Geographic disaster recovery required
- Compliance requires multi-region backups
- Quarterly DR testing capability
- Budget supports $150-500/month

Choose Enterprise Backup Strategy when:
- Enterprise with multiple databases and services
- Need centralized backup management
- Strict compliance (SOC 2, HIPAA, PCI-DSS, GDPR)
- Long-term retention (7+ years)
- Backup Vault Lock for ransomware protection
- Automated DR testing required
- Budget supports $100-2000/month
""",
    examples=[
        {
            "scenario": "Development database for testing",
            "recommendation": "Default Backups (7 Days)",
            "reasoning": "Development data. 7-day retention sufficient. Free backup storage within DB size.",
        },
        {
            "scenario": "Production SaaS application database",
            "recommendation": "Extended Retention with PITR (35 Days)",
            "reasoning": "35-day PITR for operational recovery. Weekly manual snapshots for compliance. CloudWatch alarms monitor backups.",
        },
        {
            "scenario": "E-commerce platform with disaster recovery requirements",
            "recommendation": "Cross-Region Backups for Disaster Recovery",
            "reasoning": "Cross-region backups in DR region. Quarterly DR testing ensures RTO/RPO. Automated replication.",
        },
        {
            "scenario": "Financial services with 7-year retention and ransomware protection",
            "recommendation": "Enterprise Backup Strategy with AWS Backup",
            "reasoning": "AWS Backup centralized management. Backup Vault Lock prevents deletion. Lifecycle policies reduce costs. Automated DR testing.",
        },
    ],
)


# Export all patterns
__all__ = [
    "RDS_DEPLOYMENT_STRATEGY_PATTERNS",
    "RDS_SECURITY_PATTERNS",
    "RDS_BACKUP_RECOVERY_PATTERNS",
]
