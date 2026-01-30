"""
Aurora Database Patterns for CARL
Provides decision frameworks for Amazon Aurora deployment, scaling, and security patterns.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_aurora_deployment_pattern() -> DecisionPattern:
    """
    Pattern for selecting Aurora deployment architecture.
    Covers single-region, multi-region, and global database configurations.
    """
    return DecisionPattern(
        pattern_id="aurora-deployment-architecture",
        name="Aurora Deployment Architecture Selection",
        category="database",
        subcategory="aurora",
        description="Framework for selecting the appropriate Amazon Aurora deployment architecture based on availability requirements, latency needs, and disaster recovery objectives.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Recovery Requirements",
                weight=0.25,
                considerations=[
                    "What is your Recovery Time Objective (RTO)?",
                    "What is your Recovery Point Objective (RPO)?",
                    "Do you need cross-region disaster recovery?",
                    "What are your data durability requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Availability Requirements",
                weight=0.25,
                considerations=[
                    "What is your uptime SLA requirement?",
                    "Can you tolerate regional outages?",
                    "Do you need automatic failover?",
                    "What is the acceptable downtime for maintenance?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.20,
                considerations=[
                    "What are your read/write latency requirements?",
                    "Do you have globally distributed users?",
                    "What is your expected transaction volume?",
                    "Do you need read scaling across regions?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Constraints",
                weight=0.15,
                considerations=[
                    "What is your database infrastructure budget?",
                    "Can you justify multi-region costs?",
                    "What is the cost of downtime for your business?",
                    "Do you need cost optimization for read replicas?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.15,
                considerations=[
                    "What is your team's expertise with Aurora?",
                    "Can you manage multi-region operations?",
                    "Do you need simple backup/restore procedures?",
                    "What is your monitoring and alerting maturity?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="aurora-single-region-single-az",
                name="Single Region - Single AZ",
                description="Aurora cluster with primary instance in a single Availability Zone. Suitable for development/test environments only.",
                pros_cons=ProConsList(
                    pros=[
                        "Lowest cost option for Aurora deployment",
                        "Simplest configuration and management",
                        "Fast deployment and setup time",
                        "Suitable for non-production workloads",
                        "Easy to upgrade to multi-AZ later"
                    ],
                    cons=[
                        "No high availability - single point of failure",
                        "Downtime during instance failures",
                        "No automatic failover capability",
                        "Not suitable for production workloads",
                        "Limited disaster recovery options"
                    ]
                ),
                estimated_cost="$200-500/month for db.r6g.large instance",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="System availability commitment - NOT MET for production (single point of failure)",
                        implementation_guidance="Use only for development/testing; implement multi-AZ for production systems"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Backup and recovery procedures - basic automated backups available",
                        implementation_guidance="Configure automated backups with appropriate retention period"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-single-region-multi-az",
                name="Single Region - Multi-AZ with Read Replicas",
                description="Aurora cluster with multi-AZ deployment, including read replicas for high availability and read scaling.",
                pros_cons=ProConsList(
                    pros=[
                        "High availability with automatic failover (1-2 minutes)",
                        "Read scaling with up to 15 read replicas",
                        "Storage automatically replicated across 3 AZs",
                        "Continuous backup to S3 with point-in-time recovery",
                        "Good balance of cost and availability",
                        "Supports connection pooling and read endpoint"
                    ],
                    cons=[
                        "Single region - vulnerable to regional outages",
                        "RTO of 1-2 minutes during failover",
                        "RPO of potentially several minutes with async replication",
                        "No protection against regional disasters",
                        "Read replicas add to overall cost"
                    ]
                ),
                estimated_cost="$600-2,000/month (primary + 2-3 read replicas, db.r6g.large)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="System availability - high availability with automatic failover",
                        implementation_guidance="Deploy primary and at least one read replica in different AZs; configure automatic failover"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Backup and recovery - automated continuous backups with PITR",
                        implementation_guidance="Configure backup retention period (35 days max); test restore procedures quarterly"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Data availability SLA - 99.95% uptime commitment",
                        implementation_guidance="Monitor failover metrics; maintain runbooks for manual failover procedures"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-multi-region-read-replicas",
                name="Multi-Region with Cross-Region Read Replicas",
                description="Aurora cluster with cross-region read replicas for disaster recovery and global read access.",
                pros_cons=ProConsList(
                    pros=[
                        "Disaster recovery with cross-region redundancy",
                        "Low-latency reads for global users",
                        "Physical isolation from primary region failures",
                        "Typical cross-region replication lag < 1 second",
                        "Can promote replica to standalone cluster",
                        "Supports up to 5 secondary regions"
                    ],
                    cons=[
                        "Higher costs due to cross-region data transfer",
                        "Manual failover required for DR scenarios (RTO: 10-15 minutes)",
                        "RPO of several seconds due to async replication",
                        "Increased operational complexity",
                        "Write latency not improved (single primary region)",
                        "Cross-region data transfer charges apply"
                    ]
                ),
                estimated_cost="$1,500-4,000/month (primary + cross-region replicas + data transfer approx. $500/TB)",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Disaster recovery capabilities - cross-region failover",
                        implementation_guidance="Document and test DR procedures quarterly; maintain DR runbooks with RTO/RPO targets"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Regional availability - protection against regional outages",
                        implementation_guidance="Configure CloudWatch alarms for replication lag; implement automated monitoring"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data residency - understand data replication across regions",
                        implementation_guidance="Document data residency requirements; ensure cross-region replication complies with regulations"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-global-database",
                name="Aurora Global Database",
                description="Aurora Global Database with primary region and up to 5 secondary regions, enabling fast cross-region disaster recovery and global reads with <1s latency.",
                pros_cons=ProConsList(
                    pros=[
                        "Fast cross-region disaster recovery (RTO < 1 minute)",
                        "Typical replication lag < 1 second across regions",
                        "Write forwarding from secondary regions (Aurora MySQL 3.x)",
                        "Low-latency reads globally for distributed applications",
                        "Supports up to 5 secondary regions with 16 read replicas each",
                        "Dedicated infrastructure for replication (no impact on primary)",
                        "Automated failover available with managed recovery"
                    ],
                    cons=[
                        "Higher cost compared to cross-region read replicas",
                        "Most expensive Aurora deployment option",
                        "Increased operational complexity for global operations",
                        "Write latency still tied to primary region",
                        "Requires careful planning for regional failover",
                        "Limited to compatible Aurora MySQL and PostgreSQL versions"
                    ]
                ),
                estimated_cost="$3,000-8,000/month (primary + 2 secondary regions + data transfer + replication infrastructure)",
                implementation_complexity="Very High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Business continuity - fast disaster recovery with minimal data loss",
                        implementation_guidance="Implement managed failover; test global failover procedures quarterly; document RTO/RPO metrics"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Global availability - multi-region redundancy with fast failover",
                        implementation_guidance="Configure cross-region monitoring; implement automated failover testing; maintain global runbooks"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="High availability commitment - 99.99% uptime achievable",
                        implementation_guidance="Monitor global replication lag; implement automated alerting; maintain SLA documentation"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data sovereignty and compliance - data replicated globally",
                        implementation_guidance="Document data residency requirements for each region; implement compliance controls per region"
                    )
                ]
            )
        ],
        decision_framework="""
        AURORA DEPLOYMENT ARCHITECTURE SELECTION FRAMEWORK:

        1. START WITH ENVIRONMENT TYPE:
           - Development/Testing → Single Region, Single AZ
           - Staging → Single Region, Multi-AZ (1 read replica)
           - Production → Multi-AZ or better

        2. EVALUATE AVAILABILITY REQUIREMENTS:
           - 99.9% (43 minutes downtime/month) → Multi-AZ with read replicas
           - 99.95% (22 minutes downtime/month) → Multi-AZ with multiple read replicas
           - 99.99% (4 minutes downtime/month) → Multi-region or Global Database

        3. ASSESS DISASTER RECOVERY NEEDS:
           - RTO > 15 minutes, RPO > 5 minutes → Multi-AZ only
           - RTO 5-15 minutes, RPO 1-5 minutes → Cross-region read replicas
           - RTO < 5 minutes, RPO < 1 minute → Aurora Global Database

        4. CONSIDER GLOBAL PERFORMANCE:
           - Single region users → Multi-AZ sufficient
           - Multi-region users (read-heavy) → Cross-region read replicas
           - Multi-region users (write-heavy) → Aurora Global Database with write forwarding

        5. EVALUATE COST VS. REQUIREMENTS:
           - Budget constrained, regional focus → Multi-AZ
           - Moderate budget, DR required → Cross-region read replicas
           - Mission-critical, global scale → Aurora Global Database

        6. FACTOR IN COMPLIANCE:
           - Data residency restrictions → Carefully plan region selection
           - High availability mandates → Multi-region required
           - Audit requirements → Consider Global Database for comprehensive logging

        RECOMMENDATION MATRIX:

        | Use Case | Availability | DR Needs | Best Fit |
        |----------|-------------|----------|----------|
        | Dev/Test | Low | None | Single-AZ |
        | Standard Production | High | Regional | Multi-AZ + Replicas |
        | Enterprise Production | Very High | Cross-Region | Cross-Region Replicas |
        | Global Mission-Critical | Maximum | Minimal RTO/RPO | Aurora Global Database |

        COST OPTIMIZATION TIPS:
        - Start with Multi-AZ for production; add regions as needed
        - Use Aurora Serverless v2 for variable workloads
        - Right-size instances based on actual workload patterns
        - Consider Reserved Instances for long-term production workloads
        - Monitor cross-region data transfer costs closely
        """,
        real_world_examples=[
            "E-commerce platform serving US customers deployed Multi-AZ Aurora in us-east-1 with 3 read replicas, achieving 99.97% uptime and handling Black Friday traffic spikes",
            "Global SaaS company implemented Aurora Global Database with primary in us-east-1 and secondaries in eu-west-1 and ap-southeast-1, reducing read latency for international users by 60%",
            "Financial services firm used cross-region read replicas for disaster recovery, successfully failing over to secondary region during a regional AWS outage with 12-minute RTO",
            "Media streaming service deployed Aurora Global Database to support 50M global users, achieving <100ms read latency worldwide and <1 minute failover during DR test"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Concepts.AuroraHighAvailability.html",
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html",
            "https://aws.amazon.com/rds/aurora/pricing/"
        ]
    )


def get_aurora_performance_pattern() -> DecisionPattern:
    """
    Pattern for Aurora performance optimization and scaling strategies.
    Covers instance sizing, read scaling, and auto-scaling configurations.
    """
    return DecisionPattern(
        pattern_id="aurora-performance-scaling",
        name="Aurora Performance and Scaling Strategy",
        category="database",
        subcategory="aurora",
        description="Framework for optimizing Aurora performance through appropriate instance sizing, read replica scaling, and auto-scaling configurations.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Workload Characteristics",
                weight=0.30,
                considerations=[
                    "What is your read/write ratio?",
                    "Do you have predictable or variable workload patterns?",
                    "What are your peak transaction rates?",
                    "Do you have batch processing windows?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.25,
                considerations=[
                    "What are your query latency requirements?",
                    "What throughput (IOPS) do you need?",
                    "Do you have specific connection pool requirements?",
                    "What is your tolerance for performance variability?"
                ]
            ),
            DecisionCriteria(
                criterion="Scalability Needs",
                weight=0.20,
                considerations=[
                    "How quickly must you scale to meet demand?",
                    "Do you need to scale reads independently from writes?",
                    "Can you tolerate scaling delays?",
                    "What is your growth projection?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.15,
                considerations=[
                    "What is your database performance budget?",
                    "Can you use burstable instances for variable workloads?",
                    "Is cost predictability important?",
                    "Can you use Reserved Instances?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Requirements",
                weight=0.10,
                considerations=[
                    "Do you need hands-off scaling automation?",
                    "Can you manage manual scaling operations?",
                    "What is your monitoring capability?",
                    "Do you need predictable monthly costs?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="aurora-provisioned-fixed",
                name="Provisioned Instances - Fixed Capacity",
                description="Traditional provisioned Aurora instances with fixed compute capacity. Manual scaling by adding read replicas or changing instance sizes.",
                pros_cons=ProConsList(
                    pros=[
                        "Predictable, consistent performance",
                        "No scaling delays - always ready for peak load",
                        "Most cost-effective for steady, high-utilization workloads",
                        "Supports largest instance sizes (up to 128 vCPU, 1024 GB RAM)",
                        "Compatible with Reserved Instances for cost savings",
                        "No warm-up period needed for performance"
                    ],
                    cons=[
                        "Pay for capacity even during idle periods",
                        "Manual intervention required for scaling",
                        "Over-provisioning necessary to handle peaks",
                        "Scaling requires instance restarts (5-10 minutes)",
                        "Cannot scale down during low-traffic periods automatically"
                    ]
                ),
                estimated_cost="$600-5,000/month (db.r6g.large to db.r6g.4xlarge, 1-3 instances)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Performance availability - consistent capacity for SLA commitments",
                        implementation_guidance="Right-size instances for peak load; monitor CPU and memory utilization; maintain capacity buffer"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Capacity management - planned scaling procedures",
                        implementation_guidance="Document scaling procedures; schedule maintenance windows; test instance resizing"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-provisioned-autoscaling-replicas",
                name="Provisioned with Auto-Scaling Read Replicas",
                description="Provisioned primary instance with auto-scaling read replicas that scale based on CPU or connection metrics.",
                pros_cons=ProConsList(
                    pros=[
                        "Automatic read scaling based on demand",
                        "Cost-effective for read-heavy workloads",
                        "Can scale from 1 to 15 read replicas automatically",
                        "No application changes needed",
                        "Maintains consistent write performance on primary",
                        "Scales up in minutes, scales down gradually"
                    ],
                    cons=[
                        "Write capacity still fixed (primary instance)",
                        "Read replica scaling takes 10-15 minutes",
                        "Costs can spike with aggressive scaling policies",
                        "Requires connection pooling and read endpoint usage",
                        "Auto-scaling based on metrics may lag actual demand",
                        "Minimum read replica count still incurs base cost"
                    ]
                ),
                estimated_cost="$800-4,000/month (db.r6g.large primary + 1-5 auto-scaled replicas)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Scalability for availability - automatic capacity adjustment",
                        implementation_guidance="Configure auto-scaling policies; set min/max replica limits; monitor scaling events"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance monitoring - metrics-based scaling triggers",
                        implementation_guidance="Define CloudWatch alarms for CPU/connections; test scaling policies; review scaling history"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost controls - scaling limits to prevent runaway costs",
                        implementation_guidance="Set maximum replica count; implement budget alerts; review scaling costs monthly"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-serverless-v2",
                name="Aurora Serverless v2",
                description="Automatically scales compute capacity from 0.5 to 128 ACUs (Aurora Capacity Units) based on workload demand with instant scaling.",
                pros_cons=ProConsList(
                    pros=[
                        "Instant scaling (seconds) up or down based on demand",
                        "Pay only for capacity used, billed per second",
                        "Scales to zero when idle (significant cost savings)",
                        "No manual intervention required",
                        "Supports read replicas for high availability",
                        "Handles unpredictable workload spikes automatically",
                        "Compatible with Global Database and read replicas"
                    ],
                    cons=[
                        "Higher per-ACU cost compared to equivalent provisioned capacity",
                        "May not be cost-effective for consistently high utilization",
                        "Cold start delay when scaling from minimum ACU",
                        "Limited to specific instance classes and features",
                        "Costs can be unpredictable with highly variable workloads",
                        "Requires careful min/max ACU configuration to control costs"
                    ]
                ),
                estimated_cost="$300-3,000/month (0.5-16 ACU range, varies by actual usage; approx. $0.12/ACU-hour)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Elastic availability - automatic capacity for demand spikes",
                        implementation_guidance="Configure appropriate min/max ACU limits; monitor scaling patterns; test spike scenarios"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance elasticity - maintains SLA during variable load",
                        implementation_guidance="Set min ACU to prevent cold starts; monitor scaling latency; configure CloudWatch alarms"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost optimization - pay-per-use model with controls",
                        implementation_guidance="Set max ACU to cap costs; implement budget alerts; review usage patterns monthly"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-hybrid-approach",
                name="Hybrid: Provisioned Primary + Serverless v2 Replicas",
                description="Provisioned instance for primary (predictable write performance) with Aurora Serverless v2 read replicas for elastic read scaling.",
                pros_cons=ProConsList(
                    pros=[
                        "Predictable write performance with provisioned primary",
                        "Elastic read scaling with Serverless v2 replicas",
                        "Cost-effective for read-heavy variable workloads",
                        "Best of both worlds - stability and elasticity",
                        "Can scale read capacity instantly during traffic spikes",
                        "Reduces costs during low-traffic periods"
                    ],
                    cons=[
                        "Most complex configuration to manage",
                        "Requires understanding of both provisioned and serverless models",
                        "Mixed pricing model can complicate cost forecasting",
                        "Need to carefully configure read endpoint routing",
                        "Monitoring requires tracking both instance types",
                        "Higher operational complexity for troubleshooting"
                    ]
                ),
                estimated_cost="$1,000-4,000/month (db.r6g.xlarge primary + 1-3 Serverless v2 replicas at 0.5-8 ACU)",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Hybrid availability - predictable writes with elastic reads",
                        implementation_guidance="Monitor both instance types; configure separate alarms; document hybrid architecture"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance optimization - balanced cost and performance",
                        implementation_guidance="Right-size primary for writes; configure serverless for read elasticity; test failover scenarios"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost management - optimize for workload characteristics",
                        implementation_guidance="Monitor costs by instance type; review scaling patterns; adjust ACU limits based on usage"
                    )
                ]
            )
        ],
        decision_framework="""
        AURORA PERFORMANCE AND SCALING SELECTION FRAMEWORK:

        1. ANALYZE WORKLOAD CHARACTERISTICS:
           - Steady, predictable load → Provisioned Fixed
           - Variable read load, steady writes → Provisioned + Auto-Scaling Replicas
           - Highly variable overall load → Aurora Serverless v2
           - Heavy writes, variable reads → Hybrid Approach

        2. EVALUATE UTILIZATION PATTERNS:
           - >70% utilization 24/7 → Provisioned Fixed (most cost-effective)
           - 40-70% with peaks → Provisioned + Auto-Scaling Replicas
           - <40% with unpredictable spikes → Aurora Serverless v2
           - Mixed patterns → Hybrid Approach

        3. ASSESS SCALING REQUIREMENTS:
           - Manual scaling acceptable → Provisioned Fixed
           - Read scaling needed (10-15 min ok) → Auto-Scaling Replicas
           - Instant scaling required → Aurora Serverless v2
           - Write + read scaling needed → Hybrid or Serverless v2

        4. CONSIDER COST OPTIMIZATION:
           - Budget predictability critical → Provisioned Fixed with Reserved Instances
           - Cost optimization for variable load → Aurora Serverless v2
           - Balance of both → Provisioned + Auto-Scaling Replicas
           - Maximum flexibility → Hybrid Approach (requires cost monitoring)

        5. FACTOR IN OPERATIONAL COMPLEXITY:
           - Minimal ops team → Serverless v2 (most automated)
           - Standard ops capability → Provisioned + Auto-Scaling
           - Advanced ops team → Hybrid Approach
           - Simple management preferred → Provisioned Fixed

        WORKLOAD-BASED RECOMMENDATIONS:

        | Workload Type | Read/Write Ratio | Variability | Best Fit |
        |---------------|-----------------|-------------|----------|
        | OLTP Production | 60/40 | Low | Provisioned Fixed |
        | Read-Heavy API | 90/10 | Medium | Provisioned + Auto-Scaling |
        | Dev/Test/Staging | 70/30 | High | Aurora Serverless v2 |
        | Global Application | 80/20 | Medium-High | Hybrid Approach |
        | Analytics/Reporting | 95/5 | High | Serverless v2 Replicas |

        COST OPTIMIZATION STRATEGIES:
        - Use Reserved Instances for provisioned primary instances (up to 50% savings)
        - Set appropriate min/max ACU for Serverless v2 to prevent cost overruns
        - Monitor and adjust auto-scaling policies based on actual patterns
        - Consider Aurora I/O-Optimized for high-throughput workloads
        - Use smaller instances with more replicas rather than fewer large instances

        PERFORMANCE OPTIMIZATION TIPS:
        - Use read endpoints for read replicas to enable automatic load balancing
        - Implement connection pooling (e.g., RDS Proxy) to reduce connection overhead
        - Monitor query performance with Performance Insights
        - Use Aurora parallel query for analytical queries on large tables
        - Consider Aurora Global Database for write forwarding from secondary regions
        """,
        real_world_examples=[
            "E-commerce site used Provisioned + Auto-Scaling Replicas, scaling from 2 to 8 read replicas during Black Friday, handling 5x normal traffic with <50ms query latency",
            "SaaS startup implemented Aurora Serverless v2 for multi-tenant database, reducing costs by 60% while maintaining <100ms p99 latency during business hours",
            "Media company deployed Hybrid approach with provisioned primary (db.r6g.2xlarge) and 3 Serverless v2 replicas (0.5-16 ACU), saving 40% on read capacity costs",
            "Financial analytics platform used Provisioned Fixed instances with Reserved Instances, achieving predictable $3,200/month cost while maintaining 99.99% availability"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Managing.Performance.html",
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html",
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Integrating.AutoScaling.html"
        ]
    )


def get_aurora_security_pattern() -> DecisionPattern:
    """
    Pattern for Aurora security and backup strategies.
    Covers encryption, network isolation, backup configurations, and compliance.
    """
    return DecisionPattern(
        pattern_id="aurora-security-backup",
        name="Aurora Security and Backup Strategy",
        category="database",
        subcategory="aurora",
        description="Comprehensive framework for implementing Aurora security controls, encryption, network isolation, backup strategies, and compliance requirements.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Data Sensitivity",
                weight=0.30,
                considerations=[
                    "What classification level is your data (public, internal, confidential, restricted)?",
                    "Do you store PII, PHI, or payment card data?",
                    "What are your data encryption requirements?",
                    "Are there regulatory compliance requirements (HIPAA, PCI-DSS, SOC 2)?"
                ]
            ),
            DecisionCriteria(
                criterion="Backup and Recovery",
                weight=0.25,
                considerations=[
                    "What is your Recovery Time Objective (RTO)?",
                    "What is your Recovery Point Objective (RPO)?",
                    "How long must you retain backups?",
                    "Do you need point-in-time recovery?"
                ]
            ),
            DecisionCriteria(
                criterion="Access Control",
                weight=0.20,
                considerations=[
                    "How many users/applications need database access?",
                    "Do you need fine-grained access controls?",
                    "Are there segregation of duties requirements?",
                    "Do you need database activity auditing?"
                ]
            ),
            DecisionCriteria(
                criterion="Network Security",
                weight=0.15,
                considerations=[
                    "Should database be accessible from internet?",
                    "Do you need private connectivity from on-premises?",
                    "What are your network isolation requirements?",
                    "Do you need cross-region secure connectivity?"
                ]
            ),
            DecisionCriteria(
                criterion="Compliance Requirements",
                weight=0.10,
                considerations=[
                    "What compliance frameworks apply (SOC 2, HIPAA, PCI-DSS)?",
                    "Do you need audit trails for database access?",
                    "Are there data residency requirements?",
                    "Do you need encryption key management?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="aurora-basic-security",
                name="Basic Security Configuration",
                description="Standard Aurora security with VPC isolation, default encryption, and automated backups. Suitable for internal applications with low-sensitivity data.",
                pros_cons=ProConsList(
                    pros=[
                        "Quick setup with AWS default security settings",
                        "Automated backups included at no extra cost",
                        "VPC isolation provides network-level protection",
                        "Default encryption at rest with AWS-managed keys",
                        "Suitable for most internal applications"
                    ],
                    cons=[
                        "Limited auditability and compliance features",
                        "No fine-grained access controls",
                        "AWS-managed keys don't meet some compliance requirements",
                        "Basic backup retention (1-35 days only)",
                        "No advanced threat protection or monitoring"
                    ]
                ),
                estimated_cost="Included in Aurora base cost (approx. $600/month for db.r6g.large multi-AZ)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Logical access controls - basic VPC and IAM controls",
                        implementation_guidance="Configure VPC security groups; use IAM database authentication where possible"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption at rest - AWS-managed encryption keys",
                        implementation_guidance="Enable default encryption; document encryption settings; ensure all snapshots encrypted"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Backup and recovery - automated daily backups",
                        implementation_guidance="Configure backup retention (minimum 7 days); test restore procedures quarterly"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-enhanced-security",
                name="Enhanced Security with KMS and Monitoring",
                description="Comprehensive security with customer-managed KMS keys, enhanced monitoring, IAM authentication, and extended backup retention.",
                pros_cons=ProConsList(
                    pros=[
                        "Customer-managed encryption keys for compliance",
                        "IAM database authentication for fine-grained access",
                        "Enhanced monitoring with Performance Insights",
                        "CloudWatch Logs integration for query logging",
                        "Meets SOC 2 and HIPAA requirements",
                        "Supports automatic backup to S3 with encryption"
                    ],
                    cons=[
                        "Higher operational complexity managing KMS keys",
                        "Additional costs for KMS, enhanced monitoring, and logs",
                        "Requires IAM policy management for database access",
                        "More complex troubleshooting with encrypted snapshots",
                        "Key rotation requires careful planning"
                    ]
                ),
                estimated_cost="$800-1,200/month (Aurora + KMS approx. $1/key/month + Enhanced Monitoring approx. $3/instance + logs approx. $50-100/month)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - IAM authentication and fine-grained permissions",
                        implementation_guidance="Implement IAM database authentication; use least-privilege IAM policies; rotate credentials regularly"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption - customer-managed KMS keys with key rotation",
                        implementation_guidance="Create customer-managed KMS key; enable automatic key rotation; encrypt all snapshots and backups"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Monitoring and logging - comprehensive database activity monitoring",
                        implementation_guidance="Enable Enhanced Monitoring; configure CloudWatch Logs; export query logs to S3 for analysis"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Backup retention - extended retention with encryption",
                        implementation_guidance="Configure 35-day backup retention; export snapshots to S3 for long-term retention; test restore procedures"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-compliance-security",
                name="Compliance-Grade Security (HIPAA/PCI-DSS)",
                description="Maximum security configuration for regulated data with AWS Backup, Database Activity Streams, Secrets Manager integration, and comprehensive audit logging.",
                pros_cons=ProConsList(
                    pros=[
                        "Meets HIPAA, PCI-DSS, and SOC 2 Type II requirements",
                        "Database Activity Streams for real-time monitoring",
                        "AWS Backup for centralized, policy-based backup management",
                        "Secrets Manager integration for credential rotation",
                        "Comprehensive audit trails for compliance reporting",
                        "VPC endpoints for private connectivity without internet exposure",
                        "Multi-layer encryption (at-rest, in-transit, backups)"
                    ],
                    cons=[
                        "Highest cost option with multiple additional services",
                        "Complex configuration and ongoing management",
                        "Requires security expertise for proper implementation",
                        "Database Activity Streams can impact performance slightly",
                        "More complex disaster recovery testing procedures",
                        "Extensive documentation required for compliance audits"
                    ]
                ),
                estimated_cost="$1,500-2,500/month (Aurora + KMS + Backup approx. $200 + Activity Streams approx. $150 + Secrets Manager approx. $10 + enhanced logs approx. $200)",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Comprehensive access control - IAM, Secrets Manager, least privilege",
                        implementation_guidance="Implement IAM authentication; use Secrets Manager for credential management; enable automatic rotation; enforce MFA for privileged access"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - Database Activity Streams for compliance",
                        implementation_guidance="Enable Database Activity Streams; stream to Kinesis Data Streams; integrate with SIEM; retain logs per compliance requirements"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Multi-layer encryption - at-rest, in-transit, backups",
                        implementation_guidance="Use customer-managed KMS keys; enforce SSL/TLS connections; encrypt all backups and snapshots; enable key rotation"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - real-time threat detection",
                        implementation_guidance="Configure GuardDuty for Aurora; enable CloudTrail for API monitoring; implement automated alerting for suspicious activity"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Enterprise backup and recovery - AWS Backup with compliance",
                        implementation_guidance="Configure AWS Backup vault with 7+ year retention; enable backup vault lock; test disaster recovery quarterly; document recovery procedures"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network isolation - private VPC endpoints and security groups",
                        implementation_guidance="Use VPC endpoints for private connectivity; implement security groups with least privilege; disable public accessibility"
                    )
                ]
            ),
            DecisionOption(
                option_id="aurora-zero-trust-security",
                name="Zero-Trust Security Architecture",
                description="Advanced security model with RDS Proxy, private endpoints, comprehensive monitoring, automated response, and defense-in-depth strategies.",
                pros_cons=ProConsList(
                    pros=[
                        "Defense-in-depth with multiple security layers",
                        "RDS Proxy for connection pooling and credential management",
                        "Automated threat response with Lambda and EventBridge",
                        "Private connectivity with no internet exposure",
                        "Centralized logging and SIEM integration",
                        "Supports blue/green deployments for secure updates",
                        "Exceeds most compliance framework requirements",
                        "Automated security posture management"
                    ],
                    cons=[
                        "Most expensive and complex security configuration",
                        "Requires advanced security and DevOps expertise",
                        "RDS Proxy adds latency (typically 1-5ms)",
                        "Extensive automation infrastructure required",
                        "Complex troubleshooting with multiple security layers",
                        "Highest operational overhead for maintenance and updates",
                        "May be over-engineered for some use cases"
                    ]
                ),
                estimated_cost="$2,500-4,000/month (Aurora + RDS Proxy approx. $60/proxy + all Compliance features + Security Hub approx. $50 + automation infrastructure approx. $100)",
                implementation_complexity="Very High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Zero-trust access - RDS Proxy with Secrets Manager and IAM",
                        implementation_guidance="Deploy RDS Proxy in private subnets; use Secrets Manager for all credentials; implement IAM authentication; enforce least-privilege access"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Comprehensive audit logging - multi-layer logging and analysis",
                        implementation_guidance="Enable Database Activity Streams; export to data lake; integrate with SIEM; implement automated log analysis with ML"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Multi-layer encryption - end-to-end with key management",
                        implementation_guidance="Customer-managed KMS keys with restricted access; enforce TLS 1.3; encrypt all data paths; implement key usage monitoring"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Automated security monitoring - real-time detection and response",
                        implementation_guidance="Deploy GuardDuty; configure Security Hub; implement EventBridge rules for automated response; integrate with incident management"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Threat prevention - automated response to security events",
                        implementation_guidance="Implement Lambda functions for automated remediation; configure WAF for SQL injection protection; enable anomaly detection"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Resilient backup strategy - multi-region with immutability",
                        implementation_guidance="Configure AWS Backup with Vault Lock; replicate to secondary region; implement backup verification; test DR procedures monthly"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network segmentation - micro-segmentation with PrivateLink",
                        implementation_guidance="Use VPC endpoints for all AWS services; implement network ACLs; deploy in isolated subnets; use Transit Gateway for hub-spoke architecture"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Change management - blue/green deployments for updates",
                        implementation_guidance="Use Aurora blue/green deployments; implement automated testing; maintain rollback procedures; document all changes"
                    )
                ]
            )
        ],
        decision_framework="""
        AURORA SECURITY AND BACKUP SELECTION FRAMEWORK:

        1. ASSESS DATA SENSITIVITY AND COMPLIANCE:
           - Internal tools, low sensitivity → Basic Security
           - Customer data, moderate sensitivity → Enhanced Security
           - PII, PHI, payment data → Compliance-Grade Security
           - Highly regulated, mission-critical → Zero-Trust Security

        2. EVALUATE COMPLIANCE REQUIREMENTS:
           - No specific compliance → Basic or Enhanced Security
           - SOC 2 Type II required → Enhanced Security minimum
           - HIPAA or PCI-DSS → Compliance-Grade Security minimum
           - Multiple frameworks + FedRAMP → Zero-Trust Security

        3. DETERMINE BACKUP AND RECOVERY NEEDS:
           - RPO < 5 minutes → All options support (continuous backup)
           - RTO < 15 minutes → Multi-AZ with any security tier
           - Long-term retention (>35 days) → Enhanced Security or higher (AWS Backup)
           - Cross-region DR → Compliance-Grade or higher

        4. CONSIDER OPERATIONAL MATURITY:
           - Limited security expertise → Basic or Enhanced Security
           - Dedicated security team → Compliance-Grade Security
           - Advanced DevSecOps → Zero-Trust Security
           - Managed services available → Any tier with managed support

        5. FACTOR IN BUDGET CONSTRAINTS:
           - Tight budget → Basic Security
           - Moderate budget, compliance needed → Enhanced Security
           - Compliance-mandated features → Compliance-Grade Security
           - Maximum security posture → Zero-Trust Security

        COMPLIANCE FRAMEWORK MAPPING:

        | Framework | Minimum Tier | Key Requirements |
        |-----------|-------------|------------------|
        | SOC 2 Type II | Enhanced Security | Encryption, monitoring, backup retention |
        | HIPAA | Compliance-Grade | BAA, encryption, audit logs, access controls |
        | PCI-DSS | Compliance-Grade | Encryption, activity streams, network isolation |
        | ISO 27001 | Compliance-Grade | Comprehensive controls, audit trails |
        | FedRAMP | Zero-Trust | Defense-in-depth, automated monitoring, incident response |

        SECURITY HARDENING CHECKLIST:

        1. Encryption:
           - Enable encryption at rest (customer-managed KMS keys for compliance)
           - Enforce TLS 1.2+ for connections in-transit
           - Encrypt all backups and snapshots
           - Enable automatic KMS key rotation

        2. Network Isolation:
           - Deploy in private subnets (no public accessibility)
           - Use VPC security groups with least-privilege rules
           - Implement VPC endpoints for AWS service connectivity
           - Consider AWS PrivateLink for cross-VPC access

        3. Access Control:
           - Use IAM database authentication where possible
           - Implement Secrets Manager for credential management
           - Enable automatic credential rotation
           - Enforce MFA for privileged database access
           - Use RDS Proxy for connection pooling and credential management

        4. Monitoring and Logging:
           - Enable Enhanced Monitoring (1-second granularity)
           - Configure Performance Insights for query analysis
           - Enable Database Activity Streams for compliance
           - Export logs to CloudWatch and S3 for long-term retention
           - Integrate with SIEM for security analytics

        5. Backup and Recovery:
           - Configure automated backups (minimum 7-day retention)
           - Use AWS Backup for policy-based backup management
           - Enable Vault Lock for backup immutability
           - Test restore procedures regularly (quarterly minimum)
           - Document and practice disaster recovery procedures

        6. Compliance and Audit:
           - Enable CloudTrail for API activity logging
           - Configure AWS Config for resource compliance monitoring
           - Use Security Hub for centralized security findings
           - Maintain documentation for audit evidence
           - Implement periodic security assessments and penetration testing

        COST OPTIMIZATION FOR SECURITY:
        - Start with Enhanced Security; add features as compliance requires
        - Use AWS Backup for cost-effective long-term retention vs. snapshots
        - Implement log filtering to reduce CloudWatch Logs costs
        - Consider RDS Proxy for reducing connection overhead and costs
        - Use Reserved Instances for predictable long-term workloads
        """,
        real_world_examples=[
            "Healthcare SaaS company implemented Compliance-Grade Security for HIPAA compliance, using Database Activity Streams and AWS Backup with 10-year retention, passing audit without findings",
            "Financial services firm deployed Zero-Trust Security with RDS Proxy, achieving <5ms connection latency while maintaining comprehensive audit trails for SOX compliance",
            "E-commerce platform used Enhanced Security with KMS encryption and IAM authentication, meeting PCI-DSS requirements while keeping costs under $1,200/month",
            "Startup used Basic Security for MVP, then migrated to Enhanced Security as customer base grew, achieving SOC 2 Type II certification within 6 months"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/UsingWithRDS.html",
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/DBActivityStreams.html",
            "https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Overview.Encryption.html",
            "https://aws.amazon.com/compliance/services-in-scope/"
        ]
    )


# Export all patterns
AURORA_PATTERNS = [
    get_aurora_deployment_pattern(),
    get_aurora_performance_pattern(),
    get_aurora_security_pattern()
]
