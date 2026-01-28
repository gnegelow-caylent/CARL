"""
DynamoDB Patterns for CARL
Provides decision frameworks for DynamoDB capacity planning, availability, and security patterns.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_dynamodb_capacity_pattern() -> DecisionPattern:
    """
    Pattern for selecting DynamoDB capacity mode and scaling strategy.
    Covers on-demand vs provisioned capacity and auto-scaling configurations.
    """
    return DecisionPattern(
        pattern_id="dynamodb-capacity-strategy",
        name="DynamoDB Capacity Mode Selection",
        category="database",
        subcategory="dynamodb",
        description="Framework for selecting the optimal DynamoDB capacity mode based on workload patterns, predictability, and cost optimization goals.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Workload Predictability",
                weight=0.30,
                considerations=[
                    "Can you forecast your read/write capacity needs?",
                    "Do you have steady or variable traffic patterns?",
                    "Are there unpredictable traffic spikes?",
                    "Do you have seasonal or event-driven workloads?"
                ]
            ),
            DecisionCriteria(
                criterion="Traffic Patterns",
                weight=0.25,
                considerations=[
                    "What is your typical requests per second (RPS)?",
                    "What is the ratio between peak and average traffic?",
                    "Do you have sudden, unpredictable spikes?",
                    "Can your application handle throttling gracefully?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.20,
                considerations=[
                    "What is your DynamoDB budget?",
                    "Is cost predictability or cost optimization more important?",
                    "What percentage of time is your table at peak capacity?",
                    "Can you tolerate capacity planning overhead?"
                ]
            ),
            DecisionCriteria(
                criterion="Application Requirements",
                weight=0.15,
                considerations=[
                    "Can your application retry on throttling?",
                    "What is your latency tolerance for scaling?",
                    "Do you need instant scaling capability?",
                    "Is this a new or existing application?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "Do you have resources for capacity planning?",
                    "Can you monitor and adjust capacity regularly?",
                    "Do you prefer hands-off management?",
                    "What is your team's DynamoDB expertise?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="dynamodb-on-demand",
                name="On-Demand Capacity Mode",
                description="Pay-per-request pricing model with instant, automatic scaling to handle any traffic level without capacity planning.",
                pros_cons=ProConsList(
                    pros=[
                        "No capacity planning required - zero operational overhead",
                        "Instant scaling to handle any traffic spike",
                        "Pay only for actual requests (no idle capacity costs)",
                        "Perfect for unpredictable or spiky workloads",
                        "Ideal for new applications without traffic history",
                        "No throttling due to capacity limits (only 2x previous peak limit)"
                    ],
                    cons=[
                        "Higher per-request cost than provisioned capacity",
                        "Can be 5-7x more expensive than provisioned at steady high utilization",
                        "Costs can spike unexpectedly with traffic surges",
                        "Less cost-effective for consistent, predictable workloads",
                        "Difficult to forecast monthly costs with variable traffic"
                    ]
                ),
                estimated_cost="$1.25/million write requests, $0.25/million read requests; typical: $100-2,000/month depending on traffic",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="System availability - automatic scaling without throttling",
                        implementation_guidance="Configure CloudWatch alarms for request metrics; monitor consumed capacity; no manual scaling required"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance management - instant capacity for demand spikes",
                        implementation_guidance="Monitor request patterns; implement client-side retry logic; track throttling events (should be minimal)"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost monitoring - implement budget alerts for variable costs",
                        implementation_guidance="Set up AWS Budgets with alerts; monitor daily costs; review traffic patterns to consider provisioned if steady"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-provisioned-manual",
                name="Provisioned Capacity - Manual Scaling",
                description="Fixed read and write capacity units (RCU/WCU) that you manually adjust based on anticipated traffic patterns.",
                pros_cons=ProConsList(
                    pros=[
                        "Most cost-effective for steady, predictable workloads",
                        "Up to 5-7x cheaper than on-demand at high utilization",
                        "Supports Reserved Capacity for additional savings (up to 50%)",
                        "Predictable monthly costs for budgeting",
                        "Full control over capacity allocation"
                    ],
                    cons=[
                        "Requires capacity planning and traffic forecasting",
                        "Manual scaling takes time and operational effort",
                        "Risk of throttling if capacity exceeded",
                        "Pay for provisioned capacity even when idle",
                        "Limited to 4 manual scaling operations per day per table",
                        "Application must handle throttling gracefully"
                    ]
                ),
                estimated_cost="$0.00065/WCU-hour, $0.00013/RCU-hour; typical: $50-500/month for 100-1,000 WCU/RCU",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Capacity management - manual provisioning with monitoring",
                        implementation_guidance="Document capacity planning procedures; set CloudWatch alarms for throttling; maintain runbooks for scaling"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance monitoring - prevent throttling through planning",
                        implementation_guidance="Monitor consumed vs provisioned capacity; analyze traffic patterns; schedule capacity adjustments before peak periods"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost optimization - right-size capacity for workload",
                        implementation_guidance="Review capacity utilization monthly; purchase Reserved Capacity for long-term tables; adjust capacity based on patterns"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-provisioned-autoscaling",
                name="Provisioned Capacity with Auto-Scaling",
                description="Provisioned capacity with automatic scaling based on CloudWatch metrics, adjusting RCU/WCU within defined min/max ranges.",
                pros_cons=ProConsList(
                    pros=[
                        "Automatic scaling based on actual demand",
                        "Cost-effective for variable but somewhat predictable workloads",
                        "Prevents over-provisioning during low-traffic periods",
                        "Supports Reserved Capacity for base capacity",
                        "Reduces operational overhead vs manual scaling",
                        "Can achieve 30-50% cost savings vs fixed provisioning"
                    ],
                    cons=[
                        "Scaling takes 1-5 minutes (not instant like on-demand)",
                        "May not react quickly enough to sudden traffic spikes",
                        "Requires tuning of target utilization and min/max values",
                        "Application still needs throttling retry logic",
                        "More complex than on-demand for configuration",
                        "Still pay for minimum provisioned capacity"
                    ]
                ),
                estimated_cost="Same per-unit cost as manual provisioned, but scales down to save costs; typical: $100-800/month with auto-scaling",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Automated capacity management - scaling policies with guardrails",
                        implementation_guidance="Configure auto-scaling policies with appropriate min/max; set target utilization to 70%; monitor scaling activities"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance elasticity - automatic response to demand changes",
                        implementation_guidance="Set CloudWatch alarms for throttling; configure aggressive scale-up policies; test scaling under load"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost optimization with elasticity - scale down during low traffic",
                        implementation_guidance="Review scaling patterns monthly; adjust min capacity based on actual baseline; use Reserved Capacity for minimum"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-hybrid-approach",
                name="Hybrid: Reserved Capacity + On-Demand",
                description="Combines Reserved Capacity for predictable baseline with on-demand billing for traffic above the reserved baseline.",
                pros_cons=ProConsList(
                    pros=[
                        "Best of both worlds - cost savings and flexibility",
                        "Reserved Capacity (up to 50% savings) for baseline traffic",
                        "On-demand automatic scaling for spikes above baseline",
                        "No throttling risk during unpredictable spikes",
                        "Optimized costs for workloads with predictable base + variable peaks",
                        "Simplified capacity management"
                    ],
                    cons=[
                        "Most complex pricing model to understand and optimize",
                        "Requires accurate baseline capacity forecasting",
                        "Reserved Capacity is a 1-year commitment",
                        "Over-provisioned reserved capacity is wasted money",
                        "Need to monitor both reserved and on-demand usage",
                        "May require periodic adjustment of reserved capacity"
                    ]
                ),
                estimated_cost="Reserved: ~$0.0004/WCU-hour (50% savings) + on-demand for spikes; typical: $200-1,200/month",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Hybrid capacity strategy - predictable base with elastic headroom",
                        implementation_guidance="Analyze traffic to determine baseline; purchase reserved capacity for 70% of typical load; rely on on-demand for peaks"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance optimization - eliminates throttling risk",
                        implementation_guidance="Monitor reserved vs on-demand usage; adjust reserved capacity annually; track cost efficiency"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost optimization - maximum efficiency for variable workloads",
                        implementation_guidance="Review capacity usage quarterly; adjust reserved capacity commitments; model cost scenarios for optimization"
                    )
                ]
            )
        ],
        decision_framework="""
        DYNAMODB CAPACITY MODE SELECTION FRAMEWORK:

        1. ASSESS WORKLOAD PREDICTABILITY:
           - Unpredictable or new application → On-Demand
           - Predictable with occasional spikes → Provisioned with Auto-Scaling
           - Highly predictable, steady load → Provisioned Manual
           - Predictable base + unpredictable spikes → Hybrid Approach

        2. EVALUATE TRAFFIC PATTERNS:
           - Peak/Average ratio > 3x → On-Demand
           - Peak/Average ratio 1.5-3x → Provisioned with Auto-Scaling
           - Peak/Average ratio < 1.5x → Provisioned Manual
           - High baseline with spikes → Hybrid Approach

        3. ANALYZE UTILIZATION:
           - <40% average utilization → On-Demand (pay for actual use)
           - 40-70% average utilization → Provisioned with Auto-Scaling
           - >70% average utilization → Provisioned Manual + Reserved Capacity
           - Mixed pattern → Hybrid Approach

        4. CONSIDER COST SENSITIVITY:
           - Cost predictability critical → Provisioned Manual
           - Cost optimization priority → Analyze utilization first
           - New/unknown workload → Start with On-Demand, migrate to provisioned later
           - Budget flexible → On-Demand for simplicity

        5. FACTOR IN OPERATIONAL CAPACITY:
           - Limited ops resources → On-Demand (zero management)
           - Can monitor and adjust → Provisioned with Auto-Scaling
           - Dedicated DBA/ops team → Provisioned Manual or Hybrid
           - Want hands-off solution → On-Demand

        WORKLOAD-BASED RECOMMENDATIONS:

        | Workload Type | Traffic Pattern | Utilization | Best Fit |
        |---------------|----------------|-------------|----------|
        | New Application | Unknown | Unknown | On-Demand |
        | Development/Test | Variable | Low | On-Demand |
        | Mobile App Backend | Spiky | Variable | On-Demand or Auto-Scaling |
        | SaaS Multi-Tenant | Predictable | Medium-High | Provisioned Auto-Scaling |
        | Enterprise OLTP | Steady | High (>70%) | Provisioned Manual + Reserved |
        | IoT Time-Series | Burst + Steady | Mixed | Hybrid Approach |
        | Gaming Leaderboard | Highly Variable | Spiky | On-Demand |
        | Session Store | Predictable | Medium | Provisioned Auto-Scaling |

        COST OPTIMIZATION STRATEGIES:

        1. Start with On-Demand for New Applications:
           - Monitor traffic patterns for 1-3 months
           - Analyze utilization and predictability
           - Switch to provisioned if steady patterns emerge

        2. Use Provisioned for Established Applications:
           - Calculate baseline capacity needs
           - Configure auto-scaling with 70% target utilization
           - Purchase Reserved Capacity for baseline (50% savings)

        3. Optimize Existing Provisioned Tables:
           - Review utilization metrics monthly
           - Adjust min/max capacity based on actual patterns
           - Consider on-demand if utilization < 40%

        4. Implement Hybrid for Complex Workloads:
           - Identify predictable baseline traffic
           - Purchase reserved capacity for baseline
           - Let on-demand handle unpredictable spikes

        CAPACITY PLANNING GUIDELINES:

        Provisioned Capacity Calculations:
        - 1 RCU = 1 strongly consistent read/sec (4KB) or 2 eventually consistent reads/sec
        - 1 WCU = 1 write/sec (1KB)
        - Example: 100 writes/sec of 2KB items = 200 WCU
        - Example: 200 reads/sec of 4KB items (eventually consistent) = 100 RCU

        On-Demand Pricing:
        - Write Request Unit (WRU): $1.25 per million writes
        - Read Request Unit (RRU): $0.25 per million reads
        - Example: 1B writes/month + 5B reads/month = $1,250 + $1,250 = $2,500/month

        Break-Even Analysis:
        - Provisioned is cheaper when utilization > 40-50% consistently
        - On-Demand is cheaper for spiky workloads with <40% average utilization
        - Use AWS Pricing Calculator for detailed comparison

        MIGRATION STRATEGIES:

        On-Demand → Provisioned:
        - Analyze 30 days of traffic with CloudWatch
        - Calculate required RCU/WCU based on peak with 20% buffer
        - Enable auto-scaling with min = 50% of peak, max = 120% of peak
        - Switch capacity mode (no downtime)

        Provisioned → On-Demand:
        - Switch capacity mode (no downtime)
        - Monitor costs for first week
        - Evaluate cost difference vs operational simplicity
        """,
        real_world_examples=[
            "Mobile gaming company used On-Demand for leaderboard table, handling 10x traffic spikes during events without throttling, accepting 2x cost premium for operational simplicity",
            "SaaS platform analyzed 3 months of traffic, switched from on-demand to provisioned auto-scaling, reducing costs by 60% ($3,000 → $1,200/month) while maintaining performance",
            "IoT company implemented Hybrid approach with 500 WCU/RCU reserved capacity + on-demand, saving 40% compared to pure on-demand while handling unpredictable sensor spikes",
            "Enterprise using Provisioned Manual with Reserved Capacity for 1,000 WCU/1,000 RCU baseline, achieving $600/month cost with predictable invoicing for budgeting"
        ],
        references=[
            "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html",
            "https://aws.amazon.com/dynamodb/pricing/",
            "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/AutoScaling.html"
        ]
    )


def get_dynamodb_availability_pattern() -> DecisionPattern:
    """
    Pattern for DynamoDB high availability and disaster recovery configurations.
    Covers single-region, multi-region, and global tables.
    """
    return DecisionPattern(
        pattern_id="dynamodb-availability-strategy",
        name="DynamoDB Availability and Disaster Recovery",
        category="database",
        subcategory="dynamodb",
        description="Framework for selecting DynamoDB availability architecture based on uptime requirements, disaster recovery needs, and multi-region access patterns.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Availability Requirements",
                weight=0.30,
                considerations=[
                    "What is your uptime SLA requirement?",
                    "Can you tolerate regional outages?",
                    "What is acceptable downtime for maintenance?",
                    "Do you need active-active multi-region setup?"
                ]
            ),
            DecisionCriteria(
                criterion="Disaster Recovery",
                weight=0.25,
                considerations=[
                    "What is your Recovery Time Objective (RTO)?",
                    "What is your Recovery Point Objective (RPO)?",
                    "Do you need cross-region failover?",
                    "How often can you test DR procedures?"
                ]
            ),
            DecisionCriteria(
                criterion="Geographic Distribution",
                weight=0.20,
                considerations=[
                    "Are your users globally distributed?",
                    "Do you need low-latency access from multiple regions?",
                    "Are there data residency requirements?",
                    "Do you need local writes from multiple regions?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Constraints",
                weight=0.15,
                considerations=[
                    "What is your availability budget?",
                    "Can you justify multi-region costs?",
                    "What is the cost of downtime?",
                    "Can you tolerate cross-region data transfer charges?"
                ]
            ),
            DecisionCriteria(
                criterion="Consistency Requirements",
                weight=0.10,
                considerations=[
                    "Do you require strong consistency?",
                    "Can you tolerate eventual consistency?",
                    "Do you need conflict resolution for multi-region writes?",
                    "What is your data conflict tolerance?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="dynamodb-single-region",
                name="Single Region Standard",
                description="DynamoDB table in a single AWS region with standard availability backed by multi-AZ replication within the region.",
                pros_cons=ProConsList(
                    pros=[
                        "Lowest cost option for DynamoDB deployment",
                        "Simplest configuration and management",
                        "Automatic multi-AZ replication within region (built-in)",
                        "99.99% availability SLA from AWS",
                        "Strong consistency available for reads",
                        "No cross-region data transfer costs"
                    ],
                    cons=[
                        "Single point of failure at regional level",
                        "No protection against regional AWS outages",
                        "Higher latency for users outside the region",
                        "Manual disaster recovery procedures required",
                        "RTO/RPO depends on backup/restore (minutes to hours)",
                        "No automatic failover to another region"
                    ]
                ),
                estimated_cost="Base cost only (on-demand or provisioned); no additional availability charges",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Regional availability - 99.99% SLA with multi-AZ",
                        implementation_guidance="Enable point-in-time recovery (PITR); configure CloudWatch alarms; document recovery procedures"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Backup and recovery - PITR for data protection",
                        implementation_guidance="Enable PITR (35-day retention); test restore procedures quarterly; maintain DR runbooks"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Availability commitment - single-region high availability",
                        implementation_guidance="Monitor table-level metrics; implement retry logic in application; maintain incident response plan"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-backup-restore",
                name="Single Region with Backup to Secondary Region",
                description="Primary table in one region with automated backups replicated to S3 in a secondary region for disaster recovery.",
                pros_cons=ProConsList(
                    pros=[
                        "Cost-effective disaster recovery solution",
                        "Protects against regional outages",
                        "Automated backups with up to 35-day PITR",
                        "Can restore to any region from S3 backups",
                        "Lower cost than Global Tables",
                        "Supports compliance requirements for geographic redundancy"
                    ],
                    cons=[
                        "Manual failover required (RTO: 15-60 minutes)",
                        "RPO of up to 5 minutes with PITR",
                        "No automatic failover to secondary region",
                        "Read traffic still served from primary region only",
                        "Requires careful planning and testing of restore procedures",
                        "Application changes needed to point to new region"
                    ]
                ),
                estimated_cost="Base table cost + PITR (~$0.20/GB-month) + S3 backup storage (~$0.023/GB-month)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Disaster recovery - cross-region backup capability",
                        implementation_guidance="Enable PITR; configure AWS Backup for cross-region replication; test restore procedures quarterly"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Regional redundancy - backup-based DR",
                        implementation_guidance="Document DR procedures; automate restore process where possible; maintain RTO/RPO documentation"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Recovery procedures - tested and documented",
                        implementation_guidance="Create DR runbooks; test failover annually; maintain backup verification procedures"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-global-tables",
                name="Global Tables - Multi-Region Active-Active",
                description="Multi-region, fully replicated DynamoDB tables with active-active configuration and automatic conflict resolution.",
                pros_cons=ProConsList(
                    pros=[
                        "Active-active multi-region with local writes and reads",
                        "Automatic replication across regions (typically <1 second)",
                        "99.999% availability SLA across regions",
                        "Low-latency local reads and writes globally",
                        "Automatic conflict resolution with last-writer-wins",
                        "Automatic failover - no manual intervention needed",
                        "Fast disaster recovery (RTO < 1 minute, RPO < 1 second)"
                    ],
                    cons=[
                        "Higher cost - replicate data and throughput across regions",
                        "Eventual consistency across regions (typically <1 second)",
                        "Increased complexity for conflict resolution",
                        "Higher write costs due to replication",
                        "Cross-region data transfer charges apply",
                        "Cannot guarantee strong consistency across regions"
                    ]
                ),
                estimated_cost="Base cost × number of regions + replication data transfer (~$0.02/GB); typical: 2-3x single region cost",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Global availability - 99.999% SLA with multi-region",
                        implementation_guidance="Deploy to at least 2 regions; monitor replication lag; configure CloudWatch alarms per region"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Disaster recovery - automatic cross-region failover",
                        implementation_guidance="Enable PITR in all regions; test multi-region failure scenarios; maintain monitoring for replication"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="High availability - automatic regional failover",
                        implementation_guidance="Configure Route 53 health checks; implement client-side region failover logic; document global architecture"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data residency - data replicated across regions",
                        implementation_guidance="Document data residency requirements; ensure compliance in all replica regions; implement data governance"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-global-tables-advanced",
                name="Global Tables with Advanced Monitoring and Automation",
                description="Global Tables with comprehensive monitoring, automated health checks, traffic routing, and incident response automation.",
                pros_cons=ProConsList(
                    pros=[
                        "All benefits of Global Tables plus advanced automation",
                        "Automated health checking and traffic routing",
                        "Real-time monitoring and alerting across regions",
                        "Automated incident response and remediation",
                        "Comprehensive observability for global operations",
                        "Supports complex multi-region architectures",
                        "Integration with AWS services for automation (Lambda, EventBridge)"
                    ],
                    cons=[
                        "Most expensive availability option",
                        "Highest operational complexity",
                        "Requires advanced AWS and automation expertise",
                        "More complex troubleshooting across multiple regions",
                        "Extensive automation infrastructure needed",
                        "Higher testing and validation requirements"
                    ]
                ),
                estimated_cost="Global Tables cost + Route 53 health checks (~$0.50/endpoint) + Lambda automation (~$50-200/month) + enhanced monitoring",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC9.1",
                        description="Maximum availability - automated multi-region operations",
                        implementation_guidance="Deploy Route 53 health checks; implement automated failover; configure cross-region monitoring"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Advanced disaster recovery - automated response",
                        implementation_guidance="Implement EventBridge rules for incidents; create Lambda functions for automated recovery; test DR automation quarterly"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Comprehensive monitoring - real-time global observability",
                        implementation_guidance="Deploy CloudWatch dashboards per region; implement centralized logging; configure SNS for critical alerts"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Automated incident response - minimize downtime",
                        implementation_guidance="Create automated runbooks; implement self-healing mechanisms; maintain incident response procedures"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="SLA management - achieve 99.999% availability",
                        implementation_guidance="Monitor SLA compliance; track incidents and resolutions; document availability metrics and trends"
                    )
                ]
            )
        ],
        decision_framework="""
        DYNAMODB AVAILABILITY SELECTION FRAMEWORK:

        1. DETERMINE AVAILABILITY REQUIREMENTS:
           - 99.9% (43 min downtime/month) → Single Region sufficient
           - 99.99% (4 min downtime/month) → Single Region with backups
           - 99.999% (26 sec downtime/month) → Global Tables required

        2. ASSESS DISASTER RECOVERY NEEDS:
           - RTO > 1 hour, RPO > 5 minutes → Single Region with PITR
           - RTO 15-60 minutes, RPO < 5 minutes → Backup to Secondary Region
           - RTO < 1 minute, RPO < 1 second → Global Tables
           - RTO near-zero, automated failover → Global Tables Advanced

        3. EVALUATE GEOGRAPHIC REQUIREMENTS:
           - Single-region users → Single Region
           - Multi-region users (read-heavy) → Consider Global Tables
           - Multi-region users (write-heavy) → Global Tables required
           - Compliance/data residency → Plan region selection carefully

        4. CONSIDER COST VS. REQUIREMENTS:
           - Budget constrained, regional focus → Single Region
           - Moderate budget, DR needed → Backup to Secondary Region
           - Mission-critical, global users → Global Tables
           - Maximum availability requirement → Global Tables Advanced

        5. FACTOR IN OPERATIONAL CAPABILITY:
           - Limited ops team → Single Region (simplest)
           - Can manage backups and DR → Backup to Secondary Region
           - Experienced ops team → Global Tables
           - Advanced automation capability → Global Tables Advanced

        AVAILABILITY SLA COMPARISON:

        | Configuration | AWS SLA | Typical RTO | Typical RPO | Cost Factor |
        |---------------|---------|-------------|-------------|-------------|
        | Single Region | 99.99% | 15-60 min | 5 min | 1x |
        | Backup to Secondary | 99.99% | 15-60 min | 5 min | 1.1x |
        | Global Tables (2 regions) | 99.999% | <1 min | <1 sec | 2-2.5x |
        | Global Tables Advanced | 99.999%+ | <30 sec | <1 sec | 2.5-3x |

        DISASTER RECOVERY STRATEGIES:

        Single Region:
        - Enable Point-in-Time Recovery (PITR)
        - Configure on-demand backups for critical milestones
        - Document restore procedures
        - Test restore process quarterly
        - Typical RTO: 15-60 minutes, RPO: 5 minutes

        Backup to Secondary Region:
        - Enable PITR in primary region
        - Use AWS Backup to replicate to secondary region
        - Automate restore procedures with scripts
        - Test cross-region restore quarterly
        - Typical RTO: 15-60 minutes, RPO: 5 minutes

        Global Tables:
        - Replicate to at least 2 regions
        - Enable PITR in all regions
        - Configure health checks and monitoring
        - Test regional failover scenarios
        - Typical RTO: <1 minute, RPO: <1 second

        GLOBAL TABLES BEST PRACTICES:

        1. Region Selection:
           - Choose regions close to your users
           - Consider data residency requirements
           - Deploy to at least 2 regions (3+ for mission-critical)
           - Verify all required AWS services available in each region

        2. Conflict Resolution:
           - Understand last-writer-wins conflict resolution
           - Design data model to minimize conflicts
           - Consider using version numbers or timestamps
           - Implement application-level conflict detection if needed

        3. Consistency Model:
           - Accept eventual consistency across regions
           - Use strongly consistent reads in local region when needed
           - Design application to handle replication lag gracefully
           - Monitor replication lag metrics in CloudWatch

        4. Cost Optimization:
           - Monitor cross-region data transfer costs
           - Consider region selection to minimize transfer distances
           - Use on-demand capacity if traffic is unpredictable across regions
           - Review capacity allocation per region monthly

        5. Monitoring and Alerting:
           - Configure CloudWatch alarms for replication lag
           - Monitor table-level metrics in each region
           - Set up cross-region dashboards
           - Implement automated alerting for anomalies

        FAILOVER TESTING:

        Single Region:
        - Test backup restoration quarterly
        - Validate PITR functionality
        - Document restore procedures and timings

        Global Tables:
        - Test regional failover semi-annually
        - Verify automatic replication recovery
        - Measure actual RTO/RPO during tests
        - Update failover procedures based on findings
        """,
        real_world_examples=[
            "E-commerce platform used Single Region with PITR for order table, achieving 99.99% availability at $800/month with acceptable 5-minute RPO for disaster recovery",
            "Global SaaS company deployed Global Tables across us-east-1, eu-west-1, and ap-southeast-1, reducing latency by 70% for international users while achieving 99.999% availability",
            "Financial services firm implemented Backup to Secondary Region strategy, successfully restoring from backups during regional outage with 45-minute RTO",
            "Gaming company used Global Tables Advanced with automated failover, serving 10M+ users worldwide with <50ms latency and zero downtime during regional failover test"
        ],
        references=[
            "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html",
            "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html",
            "https://aws.amazon.com/dynamodb/sla/"
        ]
    )


def get_dynamodb_security_pattern() -> DecisionPattern:
    """
    Pattern for DynamoDB security, encryption, and access control strategies.
    Covers encryption, VPC endpoints, IAM policies, and compliance requirements.
    """
    return DecisionPattern(
        pattern_id="dynamodb-security-strategy",
        name="DynamoDB Security and Compliance Strategy",
        category="database",
        subcategory="dynamodb",
        description="Comprehensive framework for implementing DynamoDB security controls including encryption, access management, monitoring, and compliance requirements.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Data Sensitivity",
                weight=0.30,
                considerations=[
                    "What classification level is your data?",
                    "Do you store PII, PHI, or payment card data?",
                    "What are your encryption requirements?",
                    "Are there regulatory compliance requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Access Control Requirements",
                weight=0.25,
                considerations=[
                    "How many users/applications need access?",
                    "Do you need fine-grained access control?",
                    "Are there segregation of duties requirements?",
                    "Do you need attribute-level access control?"
                ]
            ),
            DecisionCriteria(
                criterion="Compliance and Audit",
                weight=0.20,
                considerations=[
                    "What compliance frameworks apply?",
                    "Do you need audit trails for all data access?",
                    "Are there data retention requirements?",
                    "Do you need detailed access logging?"
                ]
            ),
            DecisionCriteria(
                criterion="Network Security",
                weight=0.15,
                considerations=[
                    "Should DynamoDB be accessible from internet?",
                    "Do you need private connectivity?",
                    "What are your network isolation requirements?",
                    "Do you need cross-account access?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost and Complexity",
                weight=0.10,
                considerations=[
                    "What is your security infrastructure budget?",
                    "Can you manage advanced security features?",
                    "Do you need managed security services?",
                    "What is your team's security expertise?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="dynamodb-basic-security",
                name="Basic Security Configuration",
                description="Standard DynamoDB security with default encryption, IAM-based access control, and CloudWatch monitoring.",
                pros_cons=ProConsList(
                    pros=[
                        "Quick setup with AWS default security",
                        "Encryption at rest with AWS-managed keys (included)",
                        "IAM-based access control with granular permissions",
                        "CloudWatch metrics for monitoring",
                        "Suitable for internal applications with low-sensitivity data",
                        "No additional cost for basic security features"
                    ],
                    cons=[
                        "Limited auditability for compliance",
                        "AWS-managed keys don't meet some compliance requirements",
                        "No detailed access logging by default",
                        "Basic network security only",
                        "Limited threat detection capabilities",
                        "No fine-grained access control at item level"
                    ]
                ),
                estimated_cost="Included in base DynamoDB cost (no additional charges)",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Logical access - IAM policies for table access",
                        implementation_guidance="Use IAM policies with least privilege; separate read and write permissions; implement MFA for console access"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption at rest - AWS-managed keys",
                        implementation_guidance="Verify encryption enabled (default); document encryption settings; ensure all tables encrypted"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Basic monitoring - CloudWatch metrics",
                        implementation_guidance="Configure CloudWatch alarms for throttling and errors; review metrics weekly; maintain incident response procedures"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-enhanced-security",
                name="Enhanced Security with KMS and VPC Endpoints",
                description="Improved security with customer-managed KMS keys, VPC endpoints for private access, and detailed CloudWatch Logs.",
                pros_cons=ProConsList(
                    pros=[
                        "Customer-managed KMS keys for compliance",
                        "VPC endpoints for private connectivity (no internet exposure)",
                        "CloudWatch Logs for detailed API access logging",
                        "Fine-grained IAM policies for item-level access",
                        "Meets SOC 2 Type II requirements",
                        "Point-in-Time Recovery (PITR) for data protection"
                    ],
                    cons=[
                        "Higher operational complexity managing KMS keys",
                        "Additional costs for KMS and VPC endpoints",
                        "VPC endpoint configuration required per VPC",
                        "CloudWatch Logs can generate significant costs",
                        "Key rotation requires planning and testing"
                    ]
                ),
                estimated_cost="Base cost + KMS (~$1/key/month + $0.03/10k requests) + VPC endpoint (~$7/month) + CloudWatch Logs (~$50-200/month)",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - fine-grained IAM with item-level permissions",
                        implementation_guidance="Implement IAM policies with condition keys; use DynamoDB conditions for item-level access; enable MFA for privileged operations"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Encryption - customer-managed KMS keys with rotation",
                        implementation_guidance="Create customer-managed CMK; enable automatic key rotation; encrypt PITR backups with same key; document key usage"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network security - VPC endpoints for private access",
                        implementation_guidance="Create VPC endpoints for DynamoDB; configure endpoint policies; restrict access to specific VPCs; disable public access where possible"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Access logging - CloudWatch Logs for API calls",
                        implementation_guidance="Enable CloudTrail for DynamoDB API logging; export logs to S3; implement log analysis and alerting; retain logs per compliance requirements"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - PITR with encrypted backups",
                        implementation_guidance="Enable PITR (35-day retention); verify backups encrypted with CMK; test restore procedures quarterly"
                    )
                ]
            ),
            DecisionOption(
                option_id="dynamodb-compliance-security",
                name="Compliance-Grade Security (HIPAA/PCI-DSS)",
                description="Maximum security for regulated data with comprehensive logging, DynamoDB Streams for audit trails, AWS Config for compliance monitoring, and defense-in-depth.",
                pros_cons=ProConsList(
                    pros=[
                        "Meets HIPAA, PCI-DSS, and SOC 2 Type II requirements",
                        "DynamoDB Streams for real-time change data capture",
                        "AWS Config for continuous compliance monitoring",
                        "Comprehensive audit trails for all data access",
                        "GuardDuty integration for threat detection",
                        "Supports data residency and sovereignty requirements",
                        "Detailed access logging at item and attribute level"
                    ],
                    cons=[
                        "Highest cost with multiple security services",
                        "Complex configuration and ongoing management",
                        "Requires security and compliance expertise",
                        "DynamoDB Streams add to read costs",
                        "Extensive documentation for compliance audits",
                        "More complex troubleshooting with multiple layers"
                    ]
                ),
                estimated_cost="Base + KMS + VPC endpoint + CloudWatch Logs + Streams (~$0.02/100k changes) + Config (~$2/rule/region) + GuardDuty (~$50+/month); typical: $300-800/month additional",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC6.1",
                        description="Comprehensive access control - attribute-level permissions",
                        implementation_guidance="Implement fine-grained IAM policies; use DynamoDB conditions for attribute-level access; enable MFA delete for critical tables; implement role-based access control (RBAC)"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Audit logging - comprehensive change tracking",
                        implementation_guidance="Enable DynamoDB Streams; export stream data to S3 via Kinesis Firehose; implement stream-based audit log analysis; retain audit logs per compliance requirements (7+ years)"
                    ),
                    SOC2Control(
                        control_id="CC6.7",
                        description="Advanced encryption - multi-layer with key management",
                        implementation_guidance="Use customer-managed CMK with restricted access; enable key rotation; implement separate keys for tables with different sensitivity; monitor key usage with CloudTrail"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Security monitoring - continuous compliance and threat detection",
                        implementation_guidance="Configure AWS Config rules for DynamoDB; enable GuardDuty for threat detection; implement Security Hub for centralized findings; automate remediation with Systems Manager"
                    ),
                    SOC2Control(
                        control_id="CC7.3",
                        description="Threat detection and response - automated security response",
                        implementation_guidance="Implement EventBridge rules for security events; create Lambda functions for automated remediation; configure SNS for critical alerts; maintain incident response runbooks"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection and recovery - immutable backups",
                        implementation_guidance="Enable PITR in all regions; use AWS Backup with Vault Lock for immutability; test disaster recovery procedures quarterly; document RTO/RPO compliance"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data privacy and residency - regional isolation",
                        implementation_guidance="Deploy tables in compliant regions only; use VPC endpoints to prevent data egress; implement data classification tagging; document data flows for privacy assessments"
                    ),
                    SOC2Control(
                        control_id="CC6.2",
                        description="Network isolation - defense-in-depth network security",
                        implementation_guidance="Use VPC endpoints with endpoint policies; implement security groups; configure NACLs for subnet-level control; disable public internet access; implement PrivateLink for cross-account access"
                    )
                ]
            )
        ],
        decision_framework="""
        DYNAMODB SECURITY SELECTION FRAMEWORK:

        1. ASSESS DATA SENSITIVITY AND COMPLIANCE:
           - Internal tools, low sensitivity → Basic Security
           - Customer data, moderate sensitivity → Enhanced Security
           - PII, PHI, payment card data → Compliance-Grade Security

        2. EVALUATE COMPLIANCE REQUIREMENTS:
           - No specific compliance → Basic Security
           - SOC 2 Type II → Enhanced Security minimum
           - HIPAA, PCI-DSS, FedRAMP → Compliance-Grade Security

        3. DETERMINE ACCESS CONTROL NEEDS:
           - Simple read/write permissions → Basic Security
           - Table-level permissions with conditions → Enhanced Security
           - Item/attribute-level permissions → Compliance-Grade Security

        4. ASSESS AUDIT AND MONITORING NEEDS:
           - Basic monitoring → Basic Security
           - API-level audit trails → Enhanced Security
           - Comprehensive change tracking → Compliance-Grade Security

        5. CONSIDER NETWORK SECURITY:
           - Public internet access acceptable → Basic Security
           - Private VPC access required → Enhanced Security minimum
           - Defense-in-depth network isolation → Compliance-Grade Security

        COMPLIANCE FRAMEWORK MAPPING:

        | Framework | Minimum Tier | Key Requirements |
        |-----------|-------------|------------------|
        | SOC 2 Type II | Enhanced | Encryption, access control, logging, PITR |
        | HIPAA | Compliance-Grade | BAA, CMK, comprehensive audit logs, Streams |
        | PCI-DSS | Compliance-Grade | Encryption, detailed logging, network isolation |
        | ISO 27001 | Compliance-Grade | Comprehensive controls, audit trails, monitoring |
        | FedRAMP | Compliance-Grade | Defense-in-depth, automated monitoring, Config |

        SECURITY HARDENING CHECKLIST:

        1. Encryption:
           ✓ Enable encryption at rest (all tiers - default AWS-managed or CMK)
           ✓ Use customer-managed KMS keys for compliance (Enhanced+)
           ✓ Enable automatic key rotation (Enhanced+)
           ✓ Encrypt all backups with same or stronger encryption (all tiers)
           ✓ Enforce encryption in-transit with TLS 1.2+ (all tiers)

        2. Access Control:
           ✓ Implement least-privilege IAM policies (all tiers)
           ✓ Use IAM condition keys for fine-grained access (Enhanced+)
           ✓ Implement attribute-level access control where needed (Compliance)
           ✓ Enable MFA for privileged operations (Enhanced+)
           ✓ Regularly review and audit IAM policies (all tiers)

        3. Network Security:
           ✓ Use VPC endpoints for private connectivity (Enhanced+)
           ✓ Configure endpoint policies to restrict access (Enhanced+)
           ✓ Implement security groups and NACLs (Compliance)
           ✓ Disable public internet access where possible (Enhanced+)
           ✓ Use AWS PrivateLink for cross-account access (Compliance)

        4. Monitoring and Logging:
           ✓ Enable CloudWatch metrics and alarms (all tiers)
           ✓ Configure CloudTrail for API logging (Enhanced+)
           ✓ Enable DynamoDB Streams for change tracking (Compliance)
           ✓ Export logs to S3 for long-term retention (Enhanced+)
           ✓ Implement automated log analysis and alerting (Compliance)

        5. Compliance and Audit:
           ✓ Enable Point-in-Time Recovery (all production tables)
           ✓ Configure AWS Config for compliance monitoring (Compliance)
           ✓ Enable GuardDuty for threat detection (Compliance)
           ✓ Implement Security Hub for centralized security (Compliance)
           ✓ Maintain documentation for audit evidence (Enhanced+)

        6. Data Protection:
           ✓ Enable PITR with appropriate retention (all production)
           ✓ Use AWS Backup for centralized backup management (Compliance)
           ✓ Enable Backup Vault Lock for immutability (Compliance)
           ✓ Test restore procedures regularly (all tiers)
           ✓ Document and practice disaster recovery (all tiers)

        FINE-GRAINED ACCESS CONTROL EXAMPLES:

        Item-Level Access (Lead ID-based):
        ```json
        {
          "Condition": {
            "ForAllValues:StringEquals": {
              "dynamodb:LeadingKeys": ["${aws:username}"]
            }
          }
        }
        ```

        Attribute-Level Access (Hide sensitive attributes):
        ```json
        {
          "Condition": {
            "ForAllValues:StringEquals": {
              "dynamodb:Attributes": ["UserId", "OrderId", "Status"]
            },
            "StringEqualsIfExists": {
              "dynamodb:Select": "SPECIFIC_ATTRIBUTES"
            }
          }
        }
        ```

        COST OPTIMIZATION FOR SECURITY:

        - Use AWS-managed keys for non-regulated data (no extra cost)
        - Implement VPC endpoints only in VPCs that need private access
        - Filter CloudWatch Logs to reduce ingestion costs
        - Use S3 Intelligent-Tiering for long-term log storage
        - Configure DynamoDB Streams only for tables requiring change tracking
        - Consider AWS Config rules carefully to avoid unnecessary costs
        """,
        real_world_examples=[
            "Healthcare startup implemented Compliance-Grade Security for patient data, achieving HIPAA compliance with DynamoDB Streams for audit trails and passing audit without findings",
            "E-commerce platform used Enhanced Security with VPC endpoints and customer-managed KMS keys, meeting PCI-DSS requirements for payment token storage at $250/month additional cost",
            "SaaS company deployed Basic Security for internal feature flags table, achieving SOC 2 Type II with minimal additional configuration and $0 extra cost",
            "Financial services firm used Compliance-Grade Security with attribute-level access control, enabling role-based data access for 500+ users while maintaining detailed audit logs"
        ],
        references=[
            "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/security.html",
            "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.howitworks.html",
            "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html",
            "https://aws.amazon.com/compliance/services-in-scope/"
        ]
    )


# Export all patterns
DYNAMODB_PATTERNS = [
    get_dynamodb_capacity_pattern(),
    get_dynamodb_availability_pattern(),
    get_dynamodb_security_pattern()
]
