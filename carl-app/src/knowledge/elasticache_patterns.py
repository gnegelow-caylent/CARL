"""
ElastiCache Patterns for CARL
Provides decision frameworks for Amazon ElastiCache deployment and security patterns.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_elasticache_deployment_pattern() -> DecisionPattern:
    """
    Pattern for selecting ElastiCache engine and deployment strategy.
    Covers Redis vs Memcached, cluster modes, and availability configurations.
    """
    return DecisionPattern(
        pattern_id="elasticache-deployment-strategy",
        name="ElastiCache Engine and Deployment Selection",
        category="cache",
        subcategory="elasticache",
        description="Framework for selecting the appropriate ElastiCache engine (Redis vs Memcached) and deployment architecture based on feature requirements, availability needs, and performance characteristics.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Feature Requirements",
                weight=0.30,
                considerations=[
                    "Do you need data persistence and snapshots?",
                    "Do you need complex data structures (lists, sets, sorted sets)?",
                    "Do you need pub/sub messaging capabilities?",
                    "Do you need transactions or Lua scripting?"
                ]
            ),
            DecisionCriteria(
                criterion="Availability and Durability",
                weight=0.25,
                considerations=[
                    "What is your uptime SLA requirement?",
                    "Can you tolerate cache data loss?",
                    "Do you need automatic failover?",
                    "Do you need multi-AZ deployment?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Needs",
                weight=0.20,
                considerations=[
                    "What are your latency requirements?",
                    "What throughput (operations/second) do you need?",
                    "Do you need to scale horizontally (sharding)?",
                    "Do you need multi-threaded performance?"
                ]
            ),
            DecisionCriteria(
                criterion="Scalability Requirements",
                weight=0.15,
                considerations=[
                    "What is your expected data size?",
                    "Do you need to scale beyond single-node capacity?",
                    "Do you need online cluster resizing?",
                    "What is your growth projection?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost and Complexity",
                weight=0.10,
                considerations=[
                    "What is your caching infrastructure budget?",
                    "Can you manage cluster complexity?",
                    "Do you need simple setup and management?",
                    "Can you utilize Reserved Nodes for savings?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="elasticache-memcached-simple",
                name="Memcached - Simple Multi-Node",
                description="Simple, multi-threaded in-memory caching with horizontal scaling across multiple nodes. No persistence or replication.",
                pros_cons=ProConsList(
                    pros=[
                        "Simplest caching solution with minimal configuration",
                        "Multi-threaded - excellent CPU utilization",
                        "Easy horizontal scaling by adding nodes",
                        "Lower cost than Redis for equivalent capacity",
                        "Ideal for simple key-value caching",
                        "Auto-discovery simplifies client configuration"
                    ],
                    cons=[
                        "No data persistence - cache lost on restart",
                        "No replication or automatic failover",
                        "No complex data structures (only strings)",
                        "No pub/sub or transaction support",
                        "Single point of failure per node",
                        "Not suitable for critical data or session stores"
                    ]
                ),
                estimated_cost="$50-400/month (cache.t4g.micro to cache.r6g.large, 2-5 nodes)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Availability - cache acceleration without high availability",
                        implementation_guidance="Deploy multiple nodes for capacity; implement application-level failover; monitor cache hit rates; acceptable for non-critical caching"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance - multi-threaded caching with horizontal scaling",
                        implementation_guidance="Monitor CPU and memory per node; scale horizontally by adding nodes; implement consistent hashing in application"
                    )
                ]
            ),
            DecisionOption(
                option_id="elasticache-redis-standalone",
                name="Redis - Standalone with Backup",
                description="Single-node Redis cluster with automated backups and optional read replicas for read scaling.",
                pros_cons=ProConsList(
                    pros=[
                        "Data persistence with automated snapshots",
                        "Supports complex data structures (lists, sets, hashes, sorted sets)",
                        "Pub/sub messaging capabilities",
                        "Backup and restore for data protection",
                        "Lower cost than clustered Redis",
                        "Suitable for session store and application state"
                    ],
                    cons=[
                        "Single point of failure (no automatic failover)",
                        "Limited to single-node capacity (up to 318GB)",
                        "Manual failover required for node failures",
                        "Downtime during maintenance windows",
                        "Read replicas are asynchronous (potential lag)",
                        "Not suitable for mission-critical workloads"
                    ]
                ),
                estimated_cost="$100-600/month (cache.r6g.large to cache.r6g.2xlarge + backups)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Availability - single-node with backup recovery",
                        implementation_guidance="Enable automated backups; document manual failover procedures; test backup restore quarterly"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - automated backups for cache recovery",
                        implementation_guidance="Configure daily automated backups; set retention period (1-35 days); test restore procedures; export backups to S3 for long-term retention"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance - Redis data structures and persistence",
                        implementation_guidance="Monitor memory usage and eviction; configure appropriate eviction policy; monitor replication lag for read replicas"
                    )
                ]
            ),
            DecisionOption(
                option_id="elasticache-redis-cluster-mode-disabled",
                name="Redis Cluster Mode Disabled (Multi-AZ)",
                description="Redis replication group with automatic failover, multi-AZ deployment, and up to 5 read replicas per shard.",
                pros_cons=ProConsList(
                    pros=[
                        "Automatic failover with multi-AZ deployment",
                        "High availability with 99.9%+ uptime",
                        "Up to 5 read replicas for read scaling",
                        "Synchronous replication for data durability",
                        "Automated backups and point-in-time recovery",
                        "Suitable for production session stores and caching",
                        "Lower complexity than cluster mode enabled"
                    ],
                    cons=[
                        "Limited to single shard capacity (up to 318GB)",
                        "Cannot scale write capacity (single primary)",
                        "More expensive than standalone Redis",
                        "Failover takes 1-2 minutes",
                        "Read replicas add to costs",
                        "Not suitable for datasets >300GB"
                    ]
                ),
                estimated_cost="$300-1,500/month (cache.r6g.large primary + 2-3 read replicas across AZs)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="High availability - automatic multi-AZ failover",
                        implementation_guidance="Deploy primary and replicas across 2-3 AZs; enable automatic failover; configure CloudWatch alarms for failover events"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data durability - multi-AZ replication with backups",
                        implementation_guidance="Enable automated daily backups; configure backup retention; test failover procedures quarterly; verify replication lag"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance and availability - read scaling with replicas",
                        implementation_guidance="Monitor primary and replica metrics; use replica endpoints for read traffic; track replication lag; implement connection pooling"
                    )
                ]
            ),
            DecisionOption(
                option_id="elasticache-redis-cluster-mode-enabled",
                name="Redis Cluster Mode Enabled (Sharded)",
                description="Horizontally scalable Redis cluster with data partitioning across multiple shards, supporting up to 500 nodes and 340TB of data.",
                pros_cons=ProConsList(
                    pros=[
                        "Massive horizontal scalability (up to 500 nodes)",
                        "Data partitioning across shards for write scaling",
                        "Supports datasets up to 340TB",
                        "High availability with automatic failover per shard",
                        "Online cluster resizing and resharding",
                        "Multi-AZ deployment for maximum availability",
                        "Read and write scaling capabilities"
                    ],
                    cons=[
                        "Most expensive ElastiCache configuration",
                        "Higher complexity for management and monitoring",
                        "Some Redis commands not supported (multi-key operations)",
                        "Application must be cluster-aware or use cluster endpoint",
                        "Resharding can impact performance temporarily",
                        "Requires understanding of hash slot distribution"
                    ]
                ),
                estimated_cost="$1,000-10,000+/month (3-20 shards, cache.r6g.large to r6g.4xlarge per shard)",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Maximum availability - multi-shard with per-shard failover",
                        implementation_guidance="Deploy 3+ shards with replicas across AZs; enable automatic failover per shard; monitor shard-level metrics; document cluster architecture"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Enterprise data protection - automated backups per shard",
                        implementation_guidance="Enable automated backups for all shards; test cluster restore procedures; document resharding procedures; maintain disaster recovery plan"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Scalability and performance - horizontal scaling for large datasets",
                        implementation_guidance="Monitor hash slot distribution; track memory per shard; implement online resizing; use cluster-aware clients; monitor cross-slot operations"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Operational monitoring - comprehensive cluster visibility",
                        implementation_guidance="Configure CloudWatch dashboards for all shards; implement shard-level alerting; monitor cluster health; track resharding events"
                    )
                ]
            )
        ],
        decision_framework="""
        ELASTICACHE ENGINE AND DEPLOYMENT SELECTION FRAMEWORK:

        1. CHOOSE ENGINE (Redis vs Memcached):

           Use Memcached if:
           - Simple key-value caching only
           - No need for data persistence
           - Multi-threaded performance critical
           - Horizontal scaling with simple architecture
           - Cost optimization is priority

           Use Redis if:
           - Need data persistence/snapshots
           - Complex data structures required (lists, sets, sorted sets)
           - Pub/sub messaging needed
           - Session store or application state
           - High availability required
           - Advanced features (transactions, Lua scripting)

        2. SELECT REDIS DEPLOYMENT MODE:

           Standalone Redis:
           - Development/testing environments
           - Non-critical caching (can tolerate data loss)
           - Dataset < 300GB
           - Budget constrained
           - Simple use cases

           Cluster Mode Disabled (Multi-AZ):
           - Production applications with HA requirements
           - Session stores and application state
           - Dataset < 300GB
           - Need automatic failover
           - Read-heavy workloads (scale with replicas)
           - Standard production workloads

           Cluster Mode Enabled:
           - Large datasets (>300GB, up to 340TB)
           - Write-heavy workloads needing horizontal write scaling
           - Mission-critical applications
           - Global scale applications
           - High throughput requirements (millions of ops/sec)

        3. EVALUATE AVAILABILITY REQUIREMENTS:
           - Can tolerate downtime → Standalone or Memcached
           - 99.9% uptime needed → Cluster Mode Disabled
           - 99.95%+ uptime needed → Cluster Mode Enabled

        4. ASSESS DATA SIZE:
           - <50GB → Any option based on features
           - 50-300GB → Standalone or Cluster Mode Disabled
           - >300GB → Cluster Mode Enabled required

        5. CONSIDER OPERATIONAL COMPLEXITY:
           - Limited ops team → Memcached or Standalone Redis
           - Standard ops capability → Cluster Mode Disabled
           - Advanced ops team → Cluster Mode Enabled
           - Managed services preferred → Consider all Redis modes with automation

        DEPLOYMENT COMPARISON:

        | Configuration | Max Size | Availability | Write Scale | Complexity | Cost Factor |
        |---------------|----------|--------------|-------------|------------|-------------|
        | Memcached Multi-Node | Unlimited* | Low | Excellent | Low | 1x |
        | Redis Standalone | 318GB | Low | Single | Low | 1.2x |
        | Redis Cluster Disabled | 318GB | High | Single | Medium | 2-3x |
        | Redis Cluster Enabled | 340TB | Very High | Excellent | High | 5-15x |

        *Memcached scales horizontally by adding nodes

        USE CASE RECOMMENDATIONS:

        | Use Case | Best Fit | Rationale |
        |----------|----------|-----------|
        | Database query caching | Memcached or Redis Standalone | Simple caching, data loss acceptable |
        | Session store | Redis Cluster Disabled | HA required, moderate size, persistence |
        | Shopping cart | Redis Cluster Disabled | HA critical, complex data structures |
        | Leaderboards/rankings | Redis Standalone/Disabled | Sorted sets, moderate scale |
        | Real-time analytics | Redis Cluster Enabled | Large datasets, high throughput |
        | Pub/sub messaging | Redis (any mode) | Redis native feature |
        | Rate limiting | Redis Standalone/Disabled | Counters, atomic operations |
        | Full-page caching | Memcached | Simple, ephemeral, cost-effective |

        SCALING STRATEGIES:

        Memcached:
        - Scale horizontally by adding nodes
        - Use consistent hashing in client
        - Simple and cost-effective
        - No rebalancing of existing data needed

        Redis Standalone:
        - Vertical scaling only (larger instance)
        - Add read replicas for read scaling
        - Limited to single-node capacity

        Redis Cluster Mode Disabled:
        - Add read replicas for read scaling (up to 5)
        - Vertical scaling of primary and replicas
        - Cannot exceed single-shard capacity (318GB)

        Redis Cluster Mode Enabled:
        - Online horizontal scaling (add/remove shards)
        - Online vertical scaling (change node types)
        - Online replica count changes
        - Resharding may impact performance temporarily

        COST OPTIMIZATION:

        1. Right-Size Instances:
           - Start small and scale based on actual usage
           - Monitor memory utilization (aim for 60-80%)
           - Use T3/T4g burstable instances for variable workloads

        2. Use Reserved Nodes:
           - 1-year or 3-year commitments
           - Up to 55% savings vs on-demand
           - Best for production long-term workloads

        3. Optimize Node Count:
           - Memcached: Use fewer, larger nodes vs many small nodes
           - Redis Cluster Disabled: Start with 1 replica, add as needed
           - Redis Cluster Enabled: Start with minimum shards needed

        4. Monitor and Adjust:
           - Review CloudWatch metrics weekly
           - Adjust instance types based on CPU/memory patterns
           - Remove unused clusters promptly

        PERFORMANCE OPTIMIZATION:

        1. Connection Management:
           - Use connection pooling in application
           - Reuse connections (don't create per request)
           - Monitor connection count

        2. Memory Management:
           - Configure appropriate eviction policy
           - Monitor eviction count (should be low)
           - Set maxmemory-policy based on use case

        3. Monitoring:
           - Track cache hit rate (aim for >80%)
           - Monitor CPU utilization (<70% typical)
           - Watch for memory pressure
           - Track replication lag for read replicas
        """,
        real_world_examples=[
            "E-commerce site used Memcached with 5 nodes for database query caching, reducing database load by 80% and achieving <1ms cache latency at $200/month",
            "SaaS platform deployed Redis Cluster Mode Disabled for session store, handling 50k concurrent users with automatic failover and 99.95% availability at $800/month",
            "Social media application implemented Redis Cluster Mode Enabled with 10 shards, managing 2TB of real-time data and processing 5M operations/second",
            "Gaming company used Redis Standalone for leaderboards with sorted sets, handling 100k players with sorted set operations at <5ms latency"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/WhatIs.html",
            "https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/Replication.Redis-RedisCluster.html",
            "https://aws.amazon.com/elasticache/pricing/"
        ]
    )


def get_elasticache_security_pattern() -> DecisionPattern:
    """
    Pattern for ElastiCache security, encryption, and access control.
    Covers network isolation, encryption, authentication, and compliance.
    """
    return DecisionPattern(
        pattern_id="elasticache-security-strategy",
        name="ElastiCache Security and Compliance Strategy",
        category="cache",
        subcategory="elasticache",
        description="Comprehensive framework for implementing ElastiCache security controls including encryption, network isolation, authentication, and compliance requirements.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Data Sensitivity",
                weight=0.30,
                considerations=[
                    "What data is stored in cache (session data, PII, etc.)?",
                    "What is the classification level of cached data?",
                    "Do you need encryption at rest and in transit?",
                    "Are there compliance requirements (HIPAA, PCI-DSS)?"
                ]
            ),
            DecisionCriteria(
                criterion="Access Control",
                weight=0.25,
                considerations=[
                    "How many applications need cache access?",
                    "Do you need user-based authentication?",
                    "Do you need fine-grained access control?",
                    "Are there segregation of duties requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Network Security",
                weight=0.20,
                considerations=[
                    "Should cache be accessible from internet?",
                    "Do you need VPC isolation?",
                    "Do you need cross-VPC or cross-account access?",
                    "What are your network isolation requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Compliance Requirements",
                weight=0.15,
                considerations=[
                    "What compliance frameworks apply?",
                    "Do you need audit trails?",
                    "Are there data residency requirements?",
                    "Do you need encryption key management?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "What is your team's security expertise?",
                    "Can you manage encryption keys?",
                    "Do you need simple security setup?",
                    "What is your security monitoring capability?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="elasticache-basic-security",
                name="Basic Security - VPC Isolation",
                description="Standard ElastiCache security with VPC deployment and security groups. No encryption or authentication.",
                pros_cons=ProConsList(
                    pros=[
                        "Simple setup with minimal configuration",
                        "VPC isolation prevents public internet access",
                        "Security groups control network access",
                        "No additional cost for basic security",
                        "Suitable for internal, non-sensitive caching",
                        "Works with both Redis and Memcached"
                    ],
                    cons=[
                        "No encryption at rest or in transit",
                        "No authentication required (network-only security)",
                        "Limited auditability and compliance features",
                        "Data transmitted in plain text",
                        "Not suitable for sensitive data",
                        "Does not meet most compliance requirements"
                    ]
                ),
                estimated_cost="No additional security costs (base ElastiCache pricing only)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Network access control - VPC and security groups",
                        implementation_guidance="Deploy in private VPC subnets; configure security groups with least privilege; restrict access to specific CIDR blocks or security groups"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network isolation - VPC-based isolation",
                        implementation_guidance="Deploy in isolated VPC subnets; use private IP addresses only; configure NACLs for subnet-level control; document network architecture"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Basic monitoring - CloudWatch metrics",
                        implementation_guidance="Configure CloudWatch alarms for connection count and memory usage; monitor security group changes; review access patterns"
                    )
                ]
            ),
            DecisionOption(
                option_id="elasticache-encryption-transit",
                name="Encryption In-Transit with Redis AUTH",
                description="Redis with TLS encryption for data in transit and Redis AUTH for password-based authentication. VPC isolation included.",
                pros_cons=ProConsList(
                    pros=[
                        "TLS encryption protects data in transit",
                        "Redis AUTH provides password authentication",
                        "VPC isolation plus encryption defense-in-depth",
                        "Meets many compliance requirements for data transmission",
                        "Compatible with Redis Cluster Mode Disabled/Enabled",
                        "Minimal performance impact (<5%)"
                    ],
                    cons=[
                        "No encryption at rest (data on disk unencrypted)",
                        "Only single password authentication (no user-based)",
                        "Not available for Memcached",
                        "Requires application changes for TLS and AUTH",
                        "Password rotation requires cluster update",
                        "Does not fully meet HIPAA or PCI-DSS requirements"
                    ]
                ),
                estimated_cost="No additional cost for encryption; same base ElastiCache pricing",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - Redis AUTH password protection",
                        implementation_guidance="Enable Redis AUTH; store password in Secrets Manager; rotate password quarterly; document authentication procedures"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption in transit - TLS 1.2+ for data protection",
                        implementation_guidance="Enable TLS encryption; enforce TLS 1.2 minimum; update application clients to use TLS; monitor non-TLS connection attempts"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - VPC isolation with encrypted communications",
                        implementation_guidance="Deploy in private subnets; use security groups; enable VPC flow logs; monitor network access patterns"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - authentication and connection tracking",
                        implementation_guidance="Configure CloudWatch alarms for authentication failures; monitor connection count; track security group changes; log API calls with CloudTrail"
                    )
                ]
            ),
            DecisionOption(
                option_id="elasticache-full-encryption",
                name="Full Encryption (At-Rest + In-Transit) with AUTH",
                description="Redis with encryption at rest using customer-managed KMS keys, encryption in transit with TLS, and Redis AUTH authentication.",
                pros_cons=ProConsList(
                    pros=[
                        "Complete encryption - at rest and in transit",
                        "Customer-managed KMS keys for compliance",
                        "Redis AUTH for password authentication",
                        "Meets HIPAA and PCI-DSS encryption requirements",
                        "VPC isolation plus multi-layer encryption",
                        "Automatic key rotation supported",
                        "Encrypted backups and snapshots"
                    ],
                    cons=[
                        "Higher operational complexity with key management",
                        "Only available for Redis (not Memcached)",
                        "Cannot enable encryption on existing unencrypted clusters",
                        "Must create new encrypted cluster and migrate data",
                        "Small performance overhead (<5-10%)",
                        "Still uses single password (not user-based authentication)"
                    ]
                ),
                estimated_cost="Base cost + KMS (approx. $1/key/month + $0.03/10k requests); typical: base + $10-50/month",
                implementation_complexity="Medium-High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.7",
                        description="Comprehensive encryption - at-rest and in-transit",
                        implementation_guidance="Create customer-managed CMK; enable encryption at rest; enable TLS for in-transit; rotate keys annually; encrypt all backups"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - AUTH with Secrets Manager",
                        implementation_guidance="Enable Redis AUTH; store password in Secrets Manager with rotation; implement least-privilege IAM for KMS key access; audit key usage"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - CloudTrail for API and key access",
                        implementation_guidance="Enable CloudTrail for ElastiCache API calls; monitor KMS key usage; log authentication attempts; export logs to S3 for retention"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - encrypted backups",
                        implementation_guidance="Configure automated backups; ensure backups encrypted with same or stronger key; test restore procedures; verify encryption on restored clusters"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data privacy - encryption for sensitive cache data",
                        implementation_guidance="Document data classification for cached data; ensure encryption meets regulatory requirements; implement data retention policies"
                    )
                ]
            ),
            DecisionOption(
                option_id="elasticache-rbac-security",
                name="Role-Based Access Control (RBAC) with Full Encryption",
                description="Redis 6+ with RBAC for user-based authentication, ACLs for fine-grained permissions, full encryption, and comprehensive monitoring.",
                pros_cons=ProConsList(
                    pros=[
                        "User-based authentication with multiple users",
                        "Fine-grained access control with Redis ACLs",
                        "Full encryption (at-rest and in-transit)",
                        "Supports different permission levels per user/application",
                        "Customer-managed KMS keys for compliance",
                        "Comprehensive audit capabilities",
                        "Meets strictest compliance requirements (HIPAA, PCI-DSS, SOC 2)",
                        "Integration with IAM for user management"
                    ],
                    cons=[
                        "Most complex ElastiCache security configuration",
                        "Requires Redis 6.0 or later",
                        "Higher operational overhead managing users and ACLs",
                        "Not available for Memcached or older Redis versions",
                        "Requires application changes for user authentication",
                        "More expensive with monitoring and security services",
                        "Steeper learning curve for ACL management"
                    ]
                ),
                estimated_cost="Base cost + KMS + CloudWatch Logs (approx. $50-100/month) + enhanced monitoring; typical: base + $100-200/month",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Fine-grained access control - RBAC with ACLs",
                        implementation_guidance="Create users with least-privilege ACLs; use Secrets Manager for password management; implement role separation; audit user access quarterly; disable default user"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="User authentication - individual user accounts",
                        implementation_guidance="Create separate users per application/service; enforce strong passwords; implement password rotation; monitor user activity; document access policies"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Multi-layer encryption - comprehensive data protection",
                        implementation_guidance="Enable encryption at-rest with CMK; enforce TLS 1.3; rotate keys automatically; encrypt backups; audit encryption settings regularly"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Comprehensive audit logging - user activity tracking",
                        implementation_guidance="Enable CloudWatch Logs for slow log; track authentication attempts; monitor command execution by user; export logs to S3; integrate with SIEM"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - real-time threat detection",
                        implementation_guidance="Configure CloudWatch alarms for failed authentication; monitor unusual command patterns; implement automated response; track user permission changes"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Access review - periodic permission audits",
                        implementation_guidance="Review user access quarterly; audit ACL configurations; remove unused users; document access changes; maintain access control matrix"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Secure backup - encrypted backups with access control",
                        implementation_guidance="Automate encrypted backups; restrict restore access to authorized users; test restore procedures with encryption; maintain backup audit trail"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Privacy controls - user-level data access controls",
                        implementation_guidance="Implement ACLs based on data sensitivity; audit data access by user; maintain data classification for cache; document privacy controls"
                    )
                ]
            )
        ],
        decision_framework="""
        ELASTICACHE SECURITY SELECTION FRAMEWORK:

        1. ASSESS DATA SENSITIVITY:
           - Non-sensitive, internal caching → Basic Security
           - Moderate sensitivity (session data) → Encryption In-Transit
           - Sensitive data (PII, financial) → Full Encryption
           - Highly regulated data (PHI, PCI) → RBAC with Full Encryption

        2. EVALUATE COMPLIANCE REQUIREMENTS:
           - No specific compliance → Basic or Encryption In-Transit
           - SOC 2 Type II → Full Encryption minimum
           - HIPAA or PCI-DSS → RBAC with Full Encryption required
           - Multiple frameworks → RBAC with Full Encryption

        3. DETERMINE ACCESS CONTROL NEEDS:
           - Network-only security sufficient → Basic Security
           - Single password authentication needed → Encryption In-Transit
           - User-based authentication required → RBAC with Full Encryption
           - Fine-grained permissions needed → RBAC with Full Encryption

        4. CONSIDER OPERATIONAL MATURITY:
           - Limited security expertise → Basic or Encryption In-Transit
           - Standard security team → Full Encryption
           - Advanced security operations → RBAC with Full Encryption
           - Managed security services → Any tier with automation

        5. FACTOR IN APPLICATION ARCHITECTURE:
           - Simple cache client → Basic Security
           - Can support TLS and AUTH → Encryption In-Transit or Full
           - Multiple applications with different permissions → RBAC
           - Microservices with service-specific access → RBAC

        COMPLIANCE FRAMEWORK MAPPING:

        | Framework | Minimum Tier | Key Requirements |
        |-----------|-------------|------------------|
        | SOC 2 Type II | Full Encryption | Encryption at-rest/in-transit, access control, logging |
        | HIPAA | RBAC Full Encryption | User authentication, comprehensive encryption, audit logs |
        | PCI-DSS | RBAC Full Encryption | Encryption, user-based access, detailed logging |
        | ISO 27001 | Full Encryption | Encryption, access controls, security monitoring |
        | FedRAMP | RBAC Full Encryption | User authentication, comprehensive controls, SIEM integration |

        SECURITY HARDENING CHECKLIST:

        1. Encryption:
           ✓ Enable TLS for encryption in-transit (all sensitive data tiers)
           ✓ Enable encryption at-rest with customer-managed KMS keys (compliance tiers)
           ✓ Enforce TLS 1.2+ minimum version
           ✓ Enable automatic KMS key rotation
           ✓ Encrypt all backups and snapshots
           ✓ Verify encryption settings regularly

        2. Authentication and Access Control:
           ✓ Enable Redis AUTH for password protection (minimum)
           ✓ Store passwords in AWS Secrets Manager
           ✓ Implement password rotation (quarterly minimum)
           ✓ Use RBAC with ACLs for user-based access (compliance requirements)
           ✓ Disable default user when RBAC enabled
           ✓ Implement least-privilege ACLs per user/application

        3. Network Security:
           ✓ Deploy in private VPC subnets (never public)
           ✓ Configure security groups with least-privilege rules
           ✓ Restrict source IPs to specific application security groups
           ✓ Enable VPC flow logs for network monitoring
           ✓ Use VPC endpoints for AWS service connectivity
           ✓ Implement Network ACLs for subnet-level control

        4. Monitoring and Logging:
           ✓ Configure CloudWatch alarms for security events
           ✓ Enable CloudTrail for API call logging
           ✓ Monitor authentication failures and unusual patterns
           ✓ Enable CloudWatch Logs for Redis slow log (RBAC tier)
           ✓ Export logs to S3 for long-term retention
           ✓ Integrate with SIEM for security analytics (compliance tiers)

        5. Backup and Recovery:
           ✓ Enable automated backups (Redis only)
           ✓ Configure appropriate backup retention period
           ✓ Ensure backups encrypted with same or stronger encryption
           ✓ Test restore procedures quarterly
           ✓ Document backup and recovery procedures
           ✓ Implement backup monitoring and alerting

        REDIS RBAC CONFIGURATION EXAMPLES:

        Read-Only User:
        ```
        ACL SETUSER readonly on >password ~* -@all +@read
        ```

        Read-Write User (no dangerous commands):
        ```
        ACL SETUSER readwrite on >password ~* -@all +@read +@write -@dangerous
        ```

        Admin User (full access):
        ```
        ACL SETUSER admin on >password ~* +@all
        ```

        Application-Specific User (specific key patterns):
        ```
        ACL SETUSER app1 on >password ~app1:* -@all +@read +@write +@string +@hash
        ```

        MIGRATION PATHS:

        Unencrypted → Encrypted:
        - Cannot enable encryption on existing cluster
        - Create new encrypted cluster
        - Use Redis replication or application-level migration
        - Test thoroughly before cutover
        - Update application connection strings

        No AUTH → Redis AUTH:
        - Enable AUTH on existing cluster
        - Update applications with password
        - Can do gradually with backwards compatibility
        - Store password in Secrets Manager

        Redis AUTH → RBAC:
        - Requires Redis 6.0+
        - Create users with appropriate ACLs
        - Update applications to authenticate with specific users
        - Disable default user when migration complete
        - Cannot enable on older Redis versions (must upgrade)

        COST OPTIMIZATION FOR SECURITY:

        - Start with Encryption In-Transit for production workloads (no extra cost)
        - Add encryption at-rest for compliance (minimal KMS cost)
        - Implement RBAC only when user-based access required
        - Use AWS-managed keys if customer-managed not required for compliance
        - Monitor CloudWatch Logs costs (can be significant with verbose logging)
        - Consider log filtering to reduce ingestion costs while maintaining security
        """,
        real_world_examples=[
            "E-commerce company used Full Encryption for session store, meeting PCI-DSS requirements with TLS and KMS encryption at $650/month total cost",
            "Healthcare SaaS implemented RBAC with Full Encryption for PHI caching, achieving HIPAA compliance with separate users per microservice",
            "Financial services firm deployed Encryption In-Transit for rate limiting cache, balancing security and simplicity at no additional cost beyond base pricing",
            "Enterprise used RBAC for multi-tenant cache, implementing ACLs to isolate tenant data access with 15 separate user accounts and detailed audit logging"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/encryption.html",
            "https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/auth.html",
            "https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/Clusters.RBAC.html",
            "https://aws.amazon.com/compliance/services-in-scope/"
        ]
    )


# Export all patterns
ELASTICACHE_PATTERNS = [
    get_elasticache_deployment_pattern(),
    get_elasticache_security_pattern()
]
