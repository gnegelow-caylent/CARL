"""
S3 Advanced Patterns for CARL
Provides decision frameworks for S3 lifecycle management, replication, and compliance patterns.
"""

from typing import List, Dict, Any
from .models import (
    DecisionPattern,
    DecisionOption,
    DecisionCriteria,
    ProConsList,
    SOC2Control
)


def get_s3_lifecycle_pattern() -> DecisionPattern:
    """
    Pattern for S3 lifecycle management and storage class optimization.
    Covers lifecycle policies, storage classes, and cost optimization strategies.
    """
    return DecisionPattern(
        pattern_id="s3-lifecycle-management",
        name="S3 Lifecycle and Storage Class Optimization",
        category="storage",
        subcategory="s3",
        description="Framework for implementing S3 lifecycle policies to automatically transition objects between storage classes and optimize storage costs based on access patterns and retention requirements.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Access Patterns",
                weight=0.30,
                considerations=[
                    "How frequently is data accessed?",
                    "Is access pattern predictable or variable?",
                    "What is the typical age of accessed data?",
                    "Do you have distinct hot/warm/cold data tiers?"
                ]
            ),
            DecisionCriteria(
                criterion="Retention Requirements",
                weight=0.25,
                considerations=[
                    "How long must you retain data?",
                    "Are there compliance retention requirements?",
                    "Can old data be deleted automatically?",
                    "Do you need versioning with retention?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Optimization",
                weight=0.20,
                considerations=[
                    "What is your current S3 storage cost?",
                    "What percentage can be transitioned to cheaper storage?",
                    "What are your retrieval cost tolerances?",
                    "Can you tolerate retrieval delays?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.15,
                considerations=[
                    "What are your data retrieval SLAs?",
                    "Can you tolerate minutes-to-hours retrieval time?",
                    "Do you need immediate access to all data?",
                    "Are there performance-sensitive applications?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "Can you implement and monitor lifecycle policies?",
                    "Do you need simple or complex transition rules?",
                    "Can you analyze access patterns regularly?",
                    "What is your team's S3 expertise?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="s3-lifecycle-basic",
                name="Basic Lifecycle - Standard to IA/Glacier",
                description="Simple lifecycle policy transitioning objects from Standard to Infrequent Access after 30 days, then to Glacier after 90 days.",
                pros_cons=ProConsList(
                    pros=[
                        "Simple to configure and understand",
                        "Automatic cost optimization for aging data",
                        "No application changes needed",
                        "Can achieve 50-70% cost savings",
                        "Suitable for most workloads with predictable aging",
                        "Low operational overhead"
                    ],
                    cons=[
                        "Fixed transition schedule may not match actual access patterns",
                        "Retrieval costs if data accessed after transition",
                        "Cannot optimize for unpredictable access patterns",
                        "May transition frequently-accessed old data",
                        "Limited granularity in lifecycle rules",
                        "No intelligent analysis of actual usage"
                    ]
                ),
                estimated_cost="Reduces storage costs significantly; typical savings: 50-70% for aging data",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC7.2",
                        description="Cost management - automated storage optimization",
                        implementation_guidance="Configure lifecycle policy with appropriate transition periods; monitor storage class distribution; track cost savings; review policy effectiveness quarterly; adjust transitions based on actual patterns"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Data retention - automated lifecycle management",
                        implementation_guidance="Define retention periods in lifecycle policy; configure expiration for temporary data; maintain compliance with retention requirements; document lifecycle strategy; test restoration procedures"
                    )
                ]
            ),
            DecisionOption(
                option_id="s3-lifecycle-intelligent-tiering",
                name="S3 Intelligent-Tiering",
                description="Automated storage class transitions based on actual access patterns. Monitors access and automatically moves objects between frequent and infrequent access tiers.",
                pros_cons=ProConsList(
                    pros=[
                        "Automatic optimization based on actual access patterns",
                        "No retrieval fees when accessing data",
                        "Perfect for unpredictable or changing access patterns",
                        "Supports Archive and Deep Archive tiers (optional)",
                        "No minimum storage duration charges",
                        "Eliminates manual lifecycle rule management",
                        "Optimizes costs automatically without configuration"
                    ],
                    cons=[
                        "Monitoring fee ($0.0025 per 1,000 objects per month)",
                        "Not cost-effective for small objects (<128KB)",
                        "Requires 30 days minimum before archiving transitions",
                        "Slightly higher cost than manually optimized lifecycle",
                        "Cannot customize transition logic",
                        "Archive tiers must be explicitly enabled"
                    ]
                ),
                estimated_cost="Storage: Similar to Standard-IA; Monitoring: $0.0025/1k objects; typical: 40-60% savings with no retrieval fees",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC7.2",
                        description="Automated optimization - intelligent cost management",
                        implementation_guidance="Enable Intelligent-Tiering for appropriate buckets; configure archive tiers if needed; monitor cost savings; review object size distribution (avoid small objects); track tier transitions"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Performance optimization - access-based tiering",
                        implementation_guidance="Monitor access patterns; enable archive tiers for rarely accessed data; configure appropriate archive access tier (Archive vs Deep Archive); test retrieval performance; document tier strategy"
                    )
                ]
            ),
            DecisionOption(
                option_id="s3-lifecycle-advanced",
                name="Advanced Lifecycle - Multi-Tier Strategy",
                description="Sophisticated lifecycle strategy with multiple tiers, prefix-based rules, versioning management, and noncurrent version expiration.",
                pros_cons=ProConsList(
                    pros=[
                        "Maximum cost optimization with granular control",
                        "Different policies for different data types (prefix-based)",
                        "Versioning lifecycle management for compliance",
                        "Noncurrent version expiration reduces costs",
                        "Can achieve 70-90% cost reduction",
                        "Supports complex retention requirements",
                        "Customizable for specific business needs"
                    ],
                    cons=[
                        "Complex to design and implement",
                        "Requires deep understanding of access patterns",
                        "More difficult to troubleshoot issues",
                        "Higher operational overhead to maintain",
                        "Need to monitor multiple policies",
                        "Risk of misconfiguration causing data loss",
                        "Requires regular review and optimization"
                    ]
                ),
                estimated_cost="Maximum savings possible; typical: 70-90% reduction for mature data lifecycle",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="CC7.2",
                        description="Comprehensive cost optimization - multi-tier lifecycle",
                        implementation_guidance="Design lifecycle policies per data type; configure appropriate transition periods; implement noncurrent version management; monitor storage class distribution; review and optimize policies quarterly; track ROI"
                    ),
                    SOC2Control(
                        control_id="A1.2",
                        description="Compliance retention - versioning lifecycle management",
                        implementation_guidance="Configure noncurrent version transitions; set expiration for old versions; maintain compliance retention periods; document retention strategy; test restore from all tiers; implement Object Lock if needed"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Change management - lifecycle policy governance",
                        implementation_guidance="Document all lifecycle policies; implement change control for policy updates; test policies before deployment; maintain policy audit trail; review impact of changes; roll back if issues detected"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Data lifecycle audit - comprehensive tracking",
                        implementation_guidance="Enable S3 Storage Lens for visibility; monitor lifecycle transitions; track deletions and expirations; maintain audit logs; implement alerting for unexpected transitions; document all policies"
                    )
                ]
            )
        ],
        decision_framework="""
        S3 LIFECYCLE STRATEGY SELECTION FRAMEWORK:

        1. ANALYZE ACCESS PATTERNS:
           - Predictable aging (30+ days old = cold) → Basic Lifecycle
           - Unpredictable or changing patterns → Intelligent-Tiering
           - Complex with multiple data types → Advanced Lifecycle
           - Small files (<128KB) → Basic Lifecycle (avoid IT monitoring costs)

        2. EVALUATE DATA VOLUME AND COST:
           - <1TB, simple needs → Basic Lifecycle
           - >1TB, variable access → Intelligent-Tiering
           - >10TB, complex needs → Advanced Lifecycle
           - Cost-sensitive with time → Design custom Advanced strategy

        3. ASSESS RETRIEVAL PATTERNS:
           - Rarely retrieve old data → Glacier Deep Archive in lifecycle
           - Occasional retrieval acceptable → Glacier Flexible Retrieval
           - Need instant access to some old data → Intelligent-Tiering
           - Mix of patterns → Advanced Lifecycle with prefix-based rules

        4. CONSIDER COMPLIANCE REQUIREMENTS:
           - Simple retention (delete after X days) → Basic Lifecycle
           - No specific compliance → Basic or Intelligent-Tiering
           - Versioning with retention → Advanced Lifecycle
           - Need Object Lock → Advanced Lifecycle with compliance mode

        5. FACTOR IN OPERATIONAL CAPACITY:
           - Limited resources → Intelligent-Tiering (automatic)
           - Can implement simple policies → Basic Lifecycle
           - Can analyze and optimize → Advanced Lifecycle
           - Need continuous optimization → Intelligent-Tiering

        STORAGE CLASS COMPARISON:

        | Storage Class | Cost/GB/Month | Retrieval | Min Duration | Use Case |
        |---------------|---------------|-----------|--------------|----------|
        | Standard | $0.023 | Free | None | Frequent access |
        | Standard-IA | $0.0125 | $0.01/GB | 30 days | Infrequent access |
        | One Zone-IA | $0.01 | $0.01/GB | 30 days | Infrequent, non-critical |
        | Intelligent-Tiering | $0.023-0.0125 | Free* | None** | Unpredictable |
        | Glacier Instant | $0.004 | $0.03/GB | 90 days | Archive, instant |
        | Glacier Flexible | $0.0036 | $0.01/GB | 90 days | Archive, minutes-hours |
        | Glacier Deep Archive | $0.00099 | $0.02/GB | 180 days | Long-term archive |

        *Monitoring fee: $0.0025 per 1,000 objects
        **Archive tiers: 90/180 days minimum

        LIFECYCLE POLICY EXAMPLES:

        Basic Lifecycle:
        ```json
        {
          "Rules": [{
            "Status": "Enabled",
            "Transitions": [
              {"Days": 30, "StorageClass": "STANDARD_IA"},
              {"Days": 90, "StorageClass": "GLACIER"},
              {"Days": 365, "StorageClass": "DEEP_ARCHIVE"}
            ],
            "Expiration": {"Days": 2555}  // 7 years
          }]
        }
        ```

        Advanced with Versioning:
        ```json
        {
          "Rules": [
            {
              "Filter": {"Prefix": "logs/"},
              "Status": "Enabled",
              "Transitions": [{"Days": 7, "StorageClass": "STANDARD_IA"}],
              "NoncurrentVersionTransitions": [
                {"NoncurrentDays": 30, "StorageClass": "GLACIER"}
              ],
              "NoncurrentVersionExpiration": {"NoncurrentDays": 90}
            },
            {
              "Filter": {"Prefix": "backups/"},
              "Status": "Enabled",
              "Transitions": [{"Days": 1, "StorageClass": "GLACIER"}],
              "Expiration": {"Days": 365}
            }
          ]
        }
        ```

        COST OPTIMIZATION STRATEGIES:

        1. Object Size Considerations:
           - Objects >128KB → Any storage class
           - Objects <128KB → Avoid Intelligent-Tiering (monitoring cost)
           - Lots of small objects → Consider aggregating before storage

        2. Minimum Storage Duration:
           - Standard-IA/One Zone-IA: 30 days minimum
           - Glacier classes: 90-180 days minimum
           - Charged for minimum even if deleted earlier
           - Plan transitions carefully to avoid early deletion fees

        3. Retrieval Costs:
           - Frequent access to old data → Intelligent-Tiering (no retrieval fee)
           - Rare access → Glacier (accept retrieval cost)
           - Predictable access → Lifecycle to appropriate tier
           - Monitor retrieval costs vs storage savings

        4. Versioning Optimization:
           - Transition noncurrent versions quickly (they're rarely needed)
           - Expire old noncurrent versions (beyond compliance retention)
           - Use versioning lifecycle rules to manage costs
           - Consider delete markers cleanup

        MONITORING AND OPTIMIZATION:

        S3 Storage Lens:
        - Enable for free or advanced metrics
        - Analyze storage class distribution
        - Track lifecycle transitions
        - Identify optimization opportunities
        - Export metrics to S3 for analysis

        CloudWatch Metrics:
        - Monitor storage bytes per class
        - Track transition events
        - Alert on unexpected patterns
        - Analyze cost trends

        Cost Optimization Review:
        - Monthly: Review Storage Lens dashboard
        - Quarterly: Analyze access patterns and adjust policies
        - Annually: Comprehensive lifecycle strategy review
        - Continuous: Monitor CloudWatch metrics

        IMPLEMENTATION BEST PRACTICES:

        1. Start Simple:
           - Begin with basic lifecycle for non-critical data
           - Test with small subset first
           - Validate transitions work as expected
           - Gradually expand to more buckets

        2. Test Retrieval:
           - Test retrieval from all tiers before production
           - Measure retrieval times
           - Verify data integrity after restoration
           - Document restoration procedures

        3. Monitor Impact:
           - Track cost savings vs retrieval costs
           - Monitor application performance
           - Alert on unexpected retrieval costs
           - Adjust policies based on actual usage

        4. Version Management:
           - Implement noncurrent version lifecycle rules
           - Balance retention needs vs costs
           - Clean up delete markers
           - Test version restoration

        5. Documentation:
           - Document all lifecycle policies
           - Maintain access pattern analysis
           - Record retention requirements
           - Keep runbooks for restore operations
        """,
        real_world_examples=[
            "Media company implemented Advanced Lifecycle for video files, reducing storage costs from $50k to $15k/month by transitioning 90-day-old videos to Glacier Deep Archive",
            "SaaS platform used Intelligent-Tiering for customer data, automatically saving 45% on storage costs without any retrieval fees or application changes",
            "Financial services used Basic Lifecycle for log retention, transitioning logs to IA after 30 days and Glacier after 90, achieving 65% cost reduction while meeting compliance",
            "Healthcare provider implemented Advanced Lifecycle with versioning for patient records, meeting 7-year HIPAA retention while reducing costs by 80% through intelligent tiering"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-transition-general-considerations.html",
            "https://docs.aws.amazon.com/AmazonS3/latest/userguide/intelligent-tiering.html",
            "https://aws.amazon.com/s3/pricing/"
        ]
    )


def get_s3_replication_pattern() -> DecisionPattern:
    """
    Pattern for S3 replication strategies including cross-region and same-region replication.
    Covers disaster recovery, compliance, and latency optimization use cases.
    """
    return DecisionPattern(
        pattern_id="s3-replication-strategy",
        name="S3 Replication Strategy",
        category="storage",
        subcategory="s3",
        description="Framework for implementing S3 replication strategies including Cross-Region Replication (CRR) and Same-Region Replication (SRR) for disaster recovery, compliance, and performance optimization.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Disaster Recovery Needs",
                weight=0.30,
                considerations=[
                    "What is your Recovery Point Objective (RPO)?",
                    "What is your Recovery Time Objective (RTO)?",
                    "Do you need cross-region redundancy?",
                    "What is the impact of regional outages?"
                ]
            ),
            DecisionCriteria(
                criterion="Compliance Requirements",
                weight=0.25,
                considerations=[
                    "Are there data residency requirements?",
                    "Do you need data stored in multiple regions for compliance?",
                    "Do you need immutable copies for audit?",
                    "What are your regulatory requirements?"
                ]
            ),
            DecisionCriteria(
                criterion="Performance Requirements",
                weight=0.20,
                considerations=[
                    "Do you have globally distributed users?",
                    "Do you need low-latency access from multiple regions?",
                    "What are your data access patterns?",
                    "Do you need read replicas for performance?"
                ]
            ),
            DecisionCriteria(
                criterion="Cost Tolerance",
                weight=0.15,
                considerations=[
                    "What is your replication budget?",
                    "Can you tolerate cross-region data transfer costs?",
                    "What is the value of disaster recovery?",
                    "Can you optimize replication with filters?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Complexity",
                weight=0.10,
                considerations=[
                    "Can you manage replication configurations?",
                    "Do you need bi-directional replication?",
                    "Can you monitor replication status?",
                    "What is your team's S3 expertise?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="s3-replication-none",
                name="No Replication - Single Region Only",
                description="No S3 replication configured. Rely on S3's built-in durability (11 9's) within a single region.",
                pros_cons=ProConsList(
                    pros=[
                        "Lowest cost - no replication fees",
                        "Simplest configuration and management",
                        "No cross-region data transfer costs",
                        "S3 provides 99.999999999% durability within region",
                        "Suitable for non-critical data or recoverable data",
                        "Zero operational overhead for replication"
                    ],
                    cons=[
                        "No protection against regional outages",
                        "Single point of failure at regional level",
                        "Cannot meet cross-region compliance requirements",
                        "Higher latency for global users",
                        "No disaster recovery for region-wide events",
                        "May not meet enterprise SLAs"
                    ]
                ),
                estimated_cost="No additional replication costs",
                implementation_complexity="None",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Data durability - S3 single-region durability",
                        implementation_guidance="Document S3 durability guarantees (11 9's); implement versioning for protection against accidental deletion; configure lifecycle backups if needed; maintain disaster recovery documentation; assess risk of regional outage"
                    )
                ]
            ),
            DecisionOption(
                option_id="s3-replication-srr",
                name="Same-Region Replication (SRR)",
                description="Replicate objects within the same AWS region to a different bucket for data segregation, compliance, or testing purposes.",
                pros_cons=ProConsList(
                    pros=[
                        "Lower cost than Cross-Region Replication (no cross-region transfer)",
                        "Useful for data aggregation from multiple buckets",
                        "Separate production and test/dev data",
                        "Compliance with data residency requirements",
                        "Change ownership for cross-account replication",
                        "Lower latency than cross-region for same-region access",
                        "Maintains single region for compliance"
                    ],
                    cons=[
                        "No disaster recovery for regional outages",
                        "Both buckets in same region (single point of failure)",
                        "Still incurs replication charges (though lower than CRR)",
                        "Requires versioning on both source and destination",
                        "Not suitable for global disaster recovery",
                        "Limited use cases vs CRR"
                    ]
                ),
                estimated_cost="$0.005/GB replicated + storage costs in destination; typical: $50-500/month for 10-100TB",
                implementation_complexity="Low-Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Data segregation - same-region replication for isolation",
                        implementation_guidance="Configure SRR to destination bucket; enable versioning on both buckets; configure replication rules with appropriate filters; monitor replication status; test restore procedures; document use case"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - separate bucket permissions",
                        implementation_guidance="Configure separate IAM policies for source and destination; implement least-privilege access; use bucket policies for cross-account; audit access to both buckets; document ownership model"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data residency - maintain single-region compliance",
                        implementation_guidance="Verify both buckets in compliant region; document data residency compliance; audit replication configuration; prevent cross-region replication; maintain compliance documentation"
                    )
                ]
            ),
            DecisionOption(
                option_id="s3-replication-crr-basic",
                name="Cross-Region Replication (CRR) - Single Destination",
                description="Replicate objects to a bucket in a different AWS region for disaster recovery and compliance. One-way replication from source to destination region.",
                pros_cons=ProConsList(
                    pros=[
                        "Disaster recovery for regional outages",
                        "Meets cross-region compliance requirements",
                        "Low-latency access for geographically distributed users",
                        "Automatic, continuous replication",
                        "Typical replication time: seconds to minutes",
                        "Can change storage class on replication",
                        "Supports delete marker and version replication"
                    ],
                    cons=[
                        "Cross-region data transfer costs ($0.02/GB)",
                        "Requires versioning on both buckets",
                        "One-way replication only (source → destination)",
                        "Additional storage costs in destination region",
                        "Replication lag possible during high traffic",
                        "Delete operations not replicated by default"
                    ]
                ),
                estimated_cost="$0.02/GB data transfer + $0.005/GB replication + destination storage; typical: $200-2,000/month for 10-100TB",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Disaster recovery - cross-region data redundancy",
                        implementation_guidance="Configure CRR to secondary region; enable versioning on both buckets; test failover procedures; monitor replication lag; document RTO/RPO; maintain DR runbooks; test quarterly"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Regional availability - protection against outages",
                        implementation_guidance="Select geographically distant region; configure S3 event notifications for replication; monitor replication metrics; configure CloudWatch alarms; document failover procedures; test regional failover"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Replication monitoring - track status and lag",
                        implementation_guidance="Monitor S3 replication metrics; track replication lag time; configure alarms for replication failures; review replication status regularly; identify and resolve replication issues"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Data residency - cross-region compliance",
                        implementation_guidance="Document regions used for replication; ensure compliance in all regions; verify data residency requirements; audit replication configuration; maintain regional compliance documentation"
                    )
                ]
            ),
            DecisionOption(
                option_id="s3-replication-crr-advanced",
                name="Cross-Region Replication - Multi-Region with Bi-Directional",
                description="Advanced replication strategy with multiple destination regions and optional bi-directional replication for active-active scenarios.",
                pros_cons=ProConsList(
                    pros=[
                        "Multi-region disaster recovery",
                        "Active-active workloads with bi-directional sync",
                        "Lowest latency for globally distributed users",
                        "Maximum data redundancy and availability",
                        "Supports replica modification sync",
                        "Flexible replication routing",
                        "Can replicate to multiple destinations",
                        "Supports replication time control (RTC) for SLA"
                    ],
                    cons=[
                        "Highest cost with multiple destinations and bi-directional",
                        "Most complex replication configuration",
                        "Higher data transfer costs (multiple regions)",
                        "Storage costs in multiple regions",
                        "Complex conflict resolution for bi-directional",
                        "Requires careful configuration to avoid loops",
                        "Higher operational overhead to monitor and maintain"
                    ]
                ),
                estimated_cost="CRR cost × number of destinations; typical: $500-5,000+/month for multi-region with 10-100TB",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Enterprise disaster recovery - multi-region redundancy",
                        implementation_guidance="Configure replication to multiple regions; implement bi-directional replication if needed; enable Replication Time Control for SLA; test multi-region failover; document RTO/RPO for each region; maintain comprehensive DR plan"
                    ),
                    SOC2Control(
                        control_id="CC9.1",
                        description="Maximum availability - global redundancy",
                        implementation_guidance="Deploy to 3+ regions for highest availability; configure health checks; implement automated failover; monitor all regions; test multi-region failure scenarios; document failover procedures for each region"
                    ),
                    SOC2Control(
                        control_id="CC7.2",
                        description="Comprehensive monitoring - multi-region visibility",
                        implementation_guidance="Monitor replication metrics per region; track replication lag across all destinations; configure alarms for each replication rule; implement centralized dashboard; analyze replication patterns; optimize costs"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Configuration management - complex replication governance",
                        implementation_guidance="Document all replication rules and destinations; implement change control for replication config; test changes in non-production; maintain configuration audit trail; review configurations quarterly; prevent replication loops"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Availability SLA - replication time control",
                        implementation_guidance="Enable Replication Time Control for 15-minute SLA; monitor RTC compliance; configure alarms for SLA breach; track replication metrics; document SLA guarantees; report on SLA achievement"
                    )
                ]
            )
        ],
        decision_framework="""
        S3 REPLICATION STRATEGY SELECTION FRAMEWORK:

        1. ASSESS DISASTER RECOVERY NEEDS:
           - No DR needed, acceptable data loss → No Replication
           - Data segregation only → Same-Region Replication
           - Regional DR required → CRR Basic
           - Multi-region DR, global scale → CRR Advanced

        2. EVALUATE COMPLIANCE REQUIREMENTS:
           - Single region compliance → No Replication or SRR
           - Cross-region required → CRR Basic minimum
           - Multiple regions mandated → CRR Advanced
           - Data sovereignty concerns → Carefully select regions

        3. DETERMINE PERFORMANCE NEEDS:
           - Single region users → No Replication or SRR
           - Users in 2 regions → CRR Basic
           - Globally distributed users → CRR Advanced multi-region
           - Active-active workloads → CRR Advanced bi-directional

        4. CONSIDER COST TOLERANCE:
           - Cost-sensitive, low risk tolerance → No Replication
           - Moderate budget, moderate risk → CRR Basic
           - Mission-critical, justify cost → CRR Advanced
           - Optimize with replication filters → Any CRR tier

        5. ASSESS OPERATIONAL CAPACITY:
           - Limited resources → No Replication or SRR
           - Standard operations → CRR Basic
           - Advanced operations team → CRR Advanced
           - Need simplified management → Use S3 Batch Replication

        REPLICATION COMPARISON:

        | Replication Type | Regions | Direction | DR | Cost | Complexity |
        |------------------|---------|-----------|-----|------|------------|
        | None | 1 | N/A | No | Lowest | None |
        | SRR | 1 | One-way | No | Low | Low |
        | CRR Basic | 2 | One-way | Yes | Medium | Medium |
        | CRR Advanced | 3+ | Bi-directional | Maximum | High | High |

        REPLICATION CONFIGURATION:

        Basic CRR Setup:
        1. Enable versioning on source and destination buckets
        2. Create IAM role for replication (S3 service principal)
        3. Configure replication rule:
           - Source bucket
           - Destination bucket (different region)
           - IAM role
           - Optional: prefix filter, storage class change
        4. Enable replication

        Advanced Options:
        - Replication Time Control (RTC): 99.99% objects within 15 minutes
        - Replica modification sync: Sync metadata changes
        - Delete marker replication: Replicate deletions
        - Metrics and notifications: Monitor replication status
        - Multiple destinations: Replicate to several buckets
        - Bi-directional: Replicate changes both ways

        Bi-Directional Replication:
        - Configure replication rule in both directions
        - Enable replica modification sync
        - AWS prevents replication loops automatically
        - Monitor for conflicts (last-write-wins)
        - Test thoroughly before production

        COST OPTIMIZATION:

        Replication Costs:
        - PUT requests: $0.005 per 1,000 replicated
        - Cross-region data transfer: $0.02/GB (CRR only)
        - Storage in destination: Standard rates apply
        - RTC: Additional $0.015 per GB
        - Monitoring: CloudWatch metrics included

        Cost Optimization Strategies:
        1. Use prefix filters to replicate only necessary objects
        2. Replicate to cheaper storage class (e.g., Standard-IA)
        3. Use lifecycle policies on destination to transition to cheaper tiers
        4. Consider SRR if cross-region not needed
        5. Monitor and remove unused replication rules
        6. Use Batch Replication for backfill (cheaper than live replication)

        Example Cost Calculation (10TB):
        - CRR to 1 region: 10TB × $0.02 = $200 + storage (approx. $230 Standard)
        - SRR: 10TB × $0.005 = $50 + storage (approx. $230 Standard)
        - Multi-region (3 destinations): $200 × 3 = $600 + storage × 3

        REPLICATION MONITORING:

        CloudWatch Metrics:
        - ReplicationLatency: Time to replicate objects
        - BytesPendingReplication: Objects waiting to replicate
        - OperationsPendingReplication: Number of operations pending
        - ReplicationRuleCount: Number of active rules
        - OperationsFailedReplication: Failed replication operations

        S3 Replication Metrics:
        - Enable via bucket configuration
        - 15-minute granularity
        - Per-rule metrics available
        - Track replication progress
        - Identify issues quickly

        Monitoring Best Practices:
        - Configure CloudWatch alarms for BytesPendingReplication
        - Alert on OperationsFailedReplication > 0
        - Monitor ReplicationLatency for SLA compliance
        - Review replication dashboard weekly
        - Investigate and resolve failed replications

        DISASTER RECOVERY PROCEDURES:

        Failover to Replica:
        1. Verify replica is up-to-date (check replication lag)
        2. Update application configuration to use replica bucket
        3. Update DNS or application endpoints
        4. Verify data integrity in replica
        5. Monitor application performance
        6. Document failover event

        Failback to Primary:
        1. Resolve issue in primary region
        2. Configure reverse replication (replica → primary)
        3. Synchronize data back to primary
        4. Verify primary is up-to-date
        5. Fail back application to primary
        6. Resume normal replication (primary → replica)

        Testing:
        - Test failover procedures quarterly
        - Measure actual RTO and RPO
        - Document lessons learned
        - Update procedures based on findings
        - Train team on failover procedures

        ADVANCED USE CASES:

        S3 Batch Replication:
        - Replicate existing objects (not just new/changed)
        - Useful for backfilling replicas
        - Lower cost than enabling replication and copying
        - One-time operation vs continuous replication
        - Can replicate objects that failed replication

        Replication with Encryption:
        - Support for SSE-S3, SSE-KMS, SSE-C
        - Can change encryption on replication
        - KMS: Configure cross-region key or separate key
        - Ensure IAM role has KMS permissions
        - Test encryption in replica

        Change Storage Class on Replication:
        - Replicate to different storage class (e.g., Standard-IA)
        - Save costs on replica if accessed infrequently
        - Consider access patterns for replica
        - Can use lifecycle on replica for further optimization

        Multi-Region Active-Active:
        - Bi-directional replication between regions
        - Application writes to both regions
        - Eventual consistency between regions
        - Implement conflict resolution at application level
        - Monitor for replication conflicts
        """,
        real_world_examples=[
            "Media company implemented CRR Advanced to 3 regions for global content delivery, reducing latency by 60% for international users and achieving <1 minute replication",
            "Financial services used CRR Basic for disaster recovery, successfully failing over to secondary region during regional outage with <5 minute RTO",
            "Healthcare provider implemented SRR for HIPAA compliance, segregating production and analytics data in separate buckets within same region",
            "SaaS platform deployed bi-directional CRR for active-active architecture, serving 10M users globally with <100ms latency from nearest region"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html",
            "https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication-time-control.html",
            "https://aws.amazon.com/s3/pricing/"
        ]
    )


def get_s3_compliance_pattern() -> DecisionPattern:
    """
    Pattern for S3 compliance and data governance including Object Lock, versioning, and audit logging.
    Covers regulatory compliance, data retention, and immutability requirements.
    """
    return DecisionPattern(
        pattern_id="s3-compliance-governance",
        name="S3 Compliance and Data Governance",
        category="security",
        subcategory="s3",
        description="Comprehensive framework for implementing S3 compliance and data governance including Object Lock for immutability, versioning for data protection, and comprehensive audit logging for regulatory compliance.",
        decision_criteria=[
            DecisionCriteria(
                criterion="Regulatory Requirements",
                weight=0.30,
                considerations=[
                    "What compliance frameworks apply (SEC, FINRA, HIPAA)?",
                    "Do you need immutable storage (WORM)?",
                    "Are there data retention requirements?",
                    "Do you need audit trails for compliance?"
                ]
            ),
            DecisionCriteria(
                criterion="Data Protection Needs",
                weight=0.25,
                considerations=[
                    "Do you need protection against accidental deletion?",
                    "Do you need protection against malicious deletion?",
                    "Do you need versioning?",
                    "What is the impact of data loss?"
                ]
            ),
            DecisionCriteria(
                criterion="Retention Requirements",
                weight=0.20,
                considerations=[
                    "How long must data be retained?",
                    "Are there legal hold requirements?",
                    "Can retention periods be shortened?",
                    "Do different data types have different retention?"
                ]
            ),
            DecisionCriteria(
                criterion="Audit and Compliance",
                weight=0.15,
                considerations=[
                    "Do you need detailed access logs?",
                    "Do you need object integrity verification?",
                    "Are there audit frequency requirements?",
                    "Do you need to prove data immutability?"
                ]
            ),
            DecisionCriteria(
                criterion="Operational Flexibility",
                weight=0.10,
                considerations=[
                    "Do you need to delete objects before retention expires?",
                    "Can you tolerate strict immutability?",
                    "Do you need to modify retention periods?",
                    "What is your compliance team's involvement?"
                ]
            )
        ],
        options=[
            DecisionOption(
                option_id="s3-compliance-basic",
                name="Basic Compliance - Versioning and Logging",
                description="Basic data protection with versioning to prevent accidental deletion and S3 server access logging for audit trails.",
                pros_cons=ProConsList(
                    pros=[
                        "Protects against accidental deletion",
                        "Simple to enable and manage",
                        "Server access logging for basic audit trail",
                        "Can recover deleted or overwritten objects",
                        "Low cost - only pay for version storage",
                        "Suitable for most general compliance needs",
                        "Can enable MFA delete for additional protection"
                    ],
                    cons=[
                        "No protection against deliberate deletion by authorized users",
                        "Not immutable - versions can be deleted",
                        "Logging has delivery delay (hours)",
                        "Does not meet WORM requirements",
                        "No guaranteed retention period",
                        "Limited audit detail vs CloudTrail",
                        "Versions add storage costs"
                    ]
                ),
                estimated_cost="Storage for versions (~20-50% increase typical) + minimal logging; typical: $50-500/month additional",
                implementation_complexity="Low",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Data protection - versioning for recovery",
                        implementation_guidance="Enable versioning on all buckets; configure lifecycle policies for noncurrent versions; implement MFA delete for critical buckets; test version recovery; document versioning strategy; monitor version storage costs"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Basic audit logging - S3 server access logs",
                        implementation_guidance="Enable server access logging; configure log destination bucket; set lifecycle policy on logs; review logs periodically; maintain logs per compliance requirements; export logs for analysis"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Change management - version tracking",
                        implementation_guidance="Monitor object changes via versions; track who modified objects; implement change approval for critical data; audit version history; maintain change logs"
                    )
                ]
            ),
            DecisionOption(
                option_id="s3-compliance-governance",
                name="Governance Mode - Object Lock with Flexibility",
                description="Object Lock in Governance mode provides retention with flexibility for privileged users to override. Combines with CloudTrail for comprehensive audit trails.",
                pros_cons=ProConsList(
                    pros=[
                        "Prevents deletion during retention period",
                        "Privileged users can override if needed",
                        "Supports retention and legal hold",
                        "CloudTrail provides detailed audit trail",
                        "Meets many compliance requirements",
                        "Flexible retention period management",
                        "Can extend retention periods",
                        "Good balance of protection and flexibility"
                    ],
                    cons=[
                        "Not truly immutable (can be overridden)",
                        "Does not meet strict WORM requirements (SEC 17a-4)",
                        "Requires specific IAM permissions to override",
                        "Must enable on bucket creation (cannot add later)*",
                        "Higher cost than basic versioning alone",
                        "More complex than basic versioning"
                    ]
                ),
                estimated_cost="Storage for versions + Object Lock (no additional charge) + CloudTrail (approx. $2/100k events); typical: $100-1,000/month",
                implementation_complexity="Medium",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Data retention - governance mode Object Lock",
                        implementation_guidance="Configure Object Lock in governance mode; set default retention period; enable versioning (required); configure legal hold procedures; document override procedures with approvals; test retention enforcement; audit lock overrides"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Comprehensive audit - CloudTrail logging",
                        implementation_guidance="Enable CloudTrail for S3 data events; log all object operations; capture Object Lock changes; export logs to S3; configure log file integrity validation; maintain 7+ year retention; integrate with SIEM"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Access control - IAM permissions for overrides",
                        implementation_guidance="Grant s3:BypassGovernanceRetention only to authorized users; implement MFA for bypass operations; audit bypass usage; document approval procedures; maintain access control matrix; review permissions quarterly"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Change management - retention policy governance",
                        implementation_guidance="Document retention policies; implement change control for policy updates; require approvals for retention changes; audit all changes; maintain policy history; test enforcement"
                    )
                ]
            ),
            DecisionOption(
                option_id="s3-compliance-sec-compliance",
                name="Compliance Mode - Immutable WORM Storage",
                description="Object Lock in Compliance mode provides immutable Write-Once-Read-Many (WORM) storage meeting SEC 17a-4(f), FINRA, and CFTC requirements.",
                pros_cons=ProConsList(
                    pros=[
                        "True immutability - cannot be deleted by anyone (including root)",
                        "Meets SEC 17a-4(f) requirements",
                        "Meets FINRA 4511(c) requirements",
                        "Supports Cohasset Associates assessment",
                        "Legal hold independent of retention",
                        "Comprehensive audit trail with CloudTrail",
                        "Bucket versioning required (additional protection)",
                        "Can extend retention (never shorten)"
                    ],
                    cons=[
                        "Strict immutability - NO deletion before retention expires",
                        "Cannot shorten retention periods once set",
                        "Must configure on bucket creation*",
                        "Higher storage costs (cannot delete early)",
                        "Requires careful planning of retention periods",
                        "Most restrictive option",
                        "Complex recovery if misconfigured"
                    ]
                ),
                estimated_cost="Storage for full retention + CloudTrail + potential Vault Lock; typical: $200-5,000/month for regulated data",
                implementation_complexity="High",
                soc2_controls=[
                    SOC2Control(
                        control_id="A1.2",
                        description="Regulatory compliance - immutable WORM storage",
                        implementation_guidance="Enable Object Lock in Compliance mode; configure retention per regulatory requirements (e.g., 7 years for SEC); implement bucket key policies; test immutability; document compliance mappings; maintain Cohasset report; audit configurations annually"
                    ),
                    SOC2Control(
                        control_id="CC6.6",
                        description="Compliance audit trail - comprehensive logging",
                        implementation_guidance="Enable CloudTrail data events for all objects; enable CloudTrail log file integrity; configure S3 Inventory for object compliance reporting; export all logs for permanent retention; integrate with compliance reporting systems; maintain audit evidence"
                    ),
                    SOC2Control(
                        control_id="CC6.1",
                        description="Strict access control - no override permissions",
                        implementation_guidance="Do NOT grant bypass permissions (Compliance mode cannot be bypassed); implement least-privilege access; enforce MFA for all access; audit all attempts to delete/modify; maintain strict IAM policies; document access controls"
                    ),
                    SOC2Control(
                        control_id="PI1.5",
                        description="Legal hold - independent immutability",
                        implementation_guidance="Implement legal hold procedures; document hold processes; train legal team on S3 holds; track all legal holds; maintain hold audit trail; test hold enforcement; integrate with legal case management"
                    ),
                    SOC2Control(
                        control_id="CC5.2",
                        description="Retention policy management - strict governance",
                        implementation_guidance="Document retention policies per regulation; implement approval process for policy changes; maintain retention policy history; conduct annual retention reviews; validate compliance with regulations; document all policy decisions"
                    ),
                    SOC2Control(
                        control_id="A1.1",
                        description="Data integrity - object integrity verification",
                        implementation_guidance="Use S3 Inventory with object metadata; verify object integrity with ETags; implement automated integrity checks; detect unauthorized modifications; maintain integrity audit trail; document verification procedures"
                    )
                ]
            )
        ],
        decision_framework="""
        S3 COMPLIANCE STRATEGY SELECTION FRAMEWORK:

        1. ASSESS REGULATORY REQUIREMENTS:
           - General compliance, SOC 2 → Basic Compliance
           - Moderate compliance, flexible retention → Governance Mode
           - SEC 17a-4, FINRA, strict WORM → Compliance Mode

        2. EVALUATE IMMUTABILITY NEEDS:
           - Protect against accidents only → Basic Compliance
           - Need retention enforcement with flexibility → Governance Mode
           - Absolute immutability required → Compliance Mode
           - No immutability needed → Basic Compliance

        3. DETERMINE RETENTION FLEXIBILITY:
           - Need to delete before retention expires → Basic or Governance
           - Some flexibility acceptable → Governance Mode
           - No flexibility allowed → Compliance Mode
           - Variable retention periods → Governance Mode (easier adjustment)

        4. ASSESS COMPLIANCE BURDEN:
           - Low compliance requirements → Basic Compliance
           - Moderate compliance oversight → Governance Mode
           - Heavy regulatory scrutiny → Compliance Mode
           - Financial services regulations → Compliance Mode typically required

        5. CONSIDER OPERATIONAL IMPACT:
           - Simple protection needed → Basic Compliance
           - Balance protection and operations → Governance Mode
           - Maximum protection, accept constraints → Compliance Mode
           - Need to delete old data → Basic or Governance (NOT Compliance)

        COMPLIANCE COMPARISON:

        | Feature | Basic | Governance | Compliance |
        |---------|-------|------------|------------|
        | Versioning | Yes | Yes (Required) | Yes (Required) |
        | Deletion Protection | Soft | Protected | Immutable |
        | Retention Enforcement | No | Yes (Override) | Yes (Strict) |
        | WORM | No | No | Yes |
        | SEC 17a-4(f) | No | No | Yes |
        | Can Delete Early | Yes | With Permission | Never |
        | Cost | Lowest | Medium | Highest |
        | Complexity | Low | Medium | High |

        *Object Lock must be enabled during bucket creation. For existing buckets, contact AWS Support.

        OBJECT LOCK CONFIGURATION:

        Enable Object Lock (Governance Mode):
        1. Create new bucket with Object Lock enabled
        2. Configure default retention (e.g., 7 years)
        3. Set retention mode: GOVERNANCE
        4. Enable versioning (automatic with Object Lock)
        5. Configure IAM policies for bypass (if needed)
        6. Test retention enforcement

        Enable Object Lock (Compliance Mode):
        1. Create new bucket with Object Lock enabled
        2. Configure default retention per regulations
        3. Set retention mode: COMPLIANCE
        4. Enable versioning (automatic)
        5. DO NOT grant bypass permissions
        6. Validate immutability
        7. Obtain Cohasset report for SEC 17a-4(f) if needed

        Legal Hold:
        - Independent of retention period
        - Prevents deletion until removed
        - Can be applied/removed regardless of retention
        - Useful for litigation holds
        - Available in both Governance and Compliance modes

        REGULATORY COMPLIANCE MAPPINGS:

        SEC 17a-4(f) Requirements:
        - Use S3 Object Lock in Compliance mode
        - Configure retention period per rule (e.g., 7 years for brokers)
        - Enable CloudTrail for audit trail
        - Obtain Cohasset Associates assessment
        - Maintain documentation of configuration
        - Implement integrity verification

        FINRA 4511(c) Requirements:
        - Immutable storage (Compliance mode)
        - 6-year retention for most records
        - Audit trail of all access
        - Ability to produce records promptly
        - Index for search and retrieval
        - Document compliance procedures

        HIPAA Requirements:
        - Versioning for data protection
        - Encryption at rest (SSE-S3 or SSE-KMS)
        - Access logging (CloudTrail)
        - Retention per state requirements (typically 6-10 years)
        - Audit trails maintained
        - BAA with AWS

        GDPR Considerations:
        - Right to erasure conflicts with immutability
        - Use Governance mode (allows deletion with approval)
        - OR use pseudonymization (keep data, delete key)
        - Document legal basis for retention
        - Implement data retention policies
        - Balance immutability with data subject rights

        AUDIT LOGGING:

        CloudTrail S3 Data Events:
        - Enable for all Object Lock buckets
        - Log object-level operations (GetObject, PutObject, DeleteObject)
        - Log Object Lock operations (PutObjectRetention, GetObjectRetention)
        - Enable log file integrity validation
        - Export logs to separate secured bucket
        - Retain logs per compliance requirements (often longer than data)

        S3 Inventory:
        - Configure daily or weekly inventory
        - Include Object Lock metadata
        - Track retention dates for all objects
        - Export to separate bucket for analysis
        - Use for compliance reporting
        - Verify no unexpected configuration changes

        S3 Storage Lens:
        - Monitor compliance bucket metrics
        - Track versioning status
        - Analyze storage class distribution
        - Identify objects nearing retention expiration
        - Generate compliance reports

        COST OPTIMIZATION:

        Version Management:
        - Implement lifecycle policies for noncurrent versions
        - Transition old versions to cheaper storage (IA, Glacier)
        - Balance retention requirements vs cost
        - Monitor version storage costs
        - Consider Intelligent-Tiering for versions

        Storage Class Optimization:
        - Compliance mode: Cannot delete, but can transition storage class
        - Use lifecycle policies to move to Glacier after initial period
        - Example: Standard for 1 year, then Glacier for remaining 6 years
        - Significant cost savings while maintaining immutability

        Replication Considerations:
        - Replicate to cheaper destination storage class
        - Use lifecycle on replica for additional optimization
        - Consider replication for DR with compliance
        - Factor replication costs into compliance budget

        IMPLEMENTATION BEST PRACTICES:

        1. Test in Non-Production First:
           - Create test bucket with Object Lock
           - Test retention enforcement
           - Test legal hold procedures
           - Validate cannot delete (Compliance mode)
           - Test version recovery

        2. Plan Retention Periods Carefully:
           - Research regulatory requirements thoroughly
           - Consider future needs (cannot shorten in Compliance mode)
           - Document retention decisions
           - Get legal review and approval
           - Build in buffer if unsure (can extend, never shorten)

        3. Implement Comprehensive Monitoring:
           - CloudTrail for all operations
           - Alarms for unexpected deletions
           - Regular compliance audits
           - Inventory reporting
           - Cost monitoring

        4. Document Everything:
           - Retention policies and rationale
           - Compliance mapping to regulations
           - Override procedures (Governance mode)
           - Audit procedures and frequency
           - Disaster recovery procedures
           - Cost estimates and actuals

        5. Train Your Team:
           - Object Lock behavior and limitations
           - Compliance requirements
           - Proper tagging and classification
           - Incident response procedures
           - Legal hold processes
        """,
        real_world_examples=[
            "Financial services firm implemented Compliance mode Object Lock for trade records, meeting SEC 17a-4(f) requirements and passing regulatory audit with Cohasset report",
            "Healthcare provider used Governance mode for patient records with 10-year retention, allowing flexibility for early deletion with compliance approval while protecting against accidents",
            "Legal firm deployed Compliance mode for case files with legal hold capabilities, ensuring evidence preservation during litigation with immutable storage",
            "Enterprise used Basic Compliance (versioning + MFA delete) for general data protection, preventing accidental deletion and saving 60% vs Object Lock while meeting SOC 2 requirements"
        ],
        references=[
            "https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html",
            "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html",
            "https://d1.awsstatic.com/whitepapers/Cohasset_Associates_Amazon_S3_Service_Final_Assessment.pdf",
            "https://aws.amazon.com/compliance/sec-rule-17a-4/"
        ]
    )


# Export all patterns
S3_ADVANCED_PATTERNS = [
    get_s3_lifecycle_pattern(),
    get_s3_replication_pattern(),
    get_s3_compliance_pattern()
]
