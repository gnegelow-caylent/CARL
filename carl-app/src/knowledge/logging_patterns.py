"""
Centralized Logging Architecture Patterns for CARL Foundation Builder.

Comprehensive patterns for log aggregation, retention, and analysis
across multi-account AWS environments.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# LOG AGGREGATION PATTERNS
# =============================================================================

LOG_AGGREGATION_PATTERNS = ArchitectureDecision(
    question="How should logs be aggregated across accounts?",
    options=[
        DecisionOption(
            name="S3 Central Log Bucket",
            description="All logs delivered to central S3 bucket in Log Archive account",
            when_to_use=[
                "Multi-account environments",
                "Long-term retention requirements",
                "SIEM integration",
                "Cost-effective storage",
                "SOC 2 compliance",
            ],
            when_not_to_use=[
                "Real-time analysis only needed",
                "Single account",
            ],
            pros=[
                "Cheapest storage option",
                "Immutable with Object Lock",
                "Lifecycle to Glacier",
                "Works with Athena for queries",
                "Standard compliance pattern",
            ],
            cons=[
                "Not real-time",
                "Need additional tooling for analysis",
                "Large bucket to manage",
            ],
            monthly_cost_range=(20.00, 500.00),
            cost_drivers=[
                "S3 Standard: $0.023/GB",
                "S3 Glacier: $0.004/GB (after 90 days)",
                "PUT requests: $0.005/1000",
                "100GB/mo new logs = ~$25/mo current + archives",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="CloudWatch Logs Cross-Account",
            description="CloudWatch Logs with cross-account subscriptions",
            when_to_use=[
                "Real-time analysis needed",
                "CloudWatch-native tooling",
                "Smaller log volumes",
                "Quick queries via Insights",
            ],
            when_not_to_use=[
                "High log volume (expensive)",
                "Long-term retention (use S3)",
            ],
            pros=[
                "Real-time delivery",
                "CloudWatch Insights queries",
                "Metric filters and alarms",
                "Native AWS experience",
            ],
            cons=[
                "Expensive for high volume ($0.50/GB)",
                "Retention costs add up",
                "Cross-account setup complex",
            ],
            monthly_cost_range=(50.00, 2000.00),
            cost_drivers=[
                "Ingestion: $0.50/GB",
                "Storage: $0.03/GB/month",
                "Cross-account delivery: Same ingestion cost",
                "100GB/mo = ~$500/mo",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Hybrid (CloudWatch + S3)",
            description="Short-term CloudWatch, long-term S3 archival",
            when_to_use=[
                "Need real-time AND long-term storage",
                "Different access patterns",
                "Compliance requiring both",
                "Most enterprise deployments",
            ],
            when_not_to_use=[
                "Simple requirements",
                "Cost optimization priority",
            ],
            pros=[
                "Best of both worlds",
                "Real-time troubleshooting",
                "Cheap long-term storage",
                "Flexible retention",
            ],
            cons=[
                "More complex architecture",
                "Dual costs during overlap",
                "Multiple query locations",
            ],
            monthly_cost_range=(50.00, 1000.00),
            cost_drivers=[
                "CloudWatch: Short retention (7-30 days)",
                "S3: Long-term storage (1+ years)",
                "Subscription filters to S3/Kinesis",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="OpenSearch (Managed ELK)",
            description="Amazon OpenSearch Service for log analytics",
            when_to_use=[
                "Complex log analysis needed",
                "Kibana dashboards desired",
                "Full-text search requirements",
                "Large security operations",
            ],
            when_not_to_use=[
                "Simple log storage needs",
                "Cost sensitive",
                "Small team without ELK expertise",
            ],
            pros=[
                "Powerful search and analytics",
                "Kibana visualization",
                "Real-time dashboards",
                "Alerting capabilities",
            ],
            cons=[
                "Expensive (cluster costs)",
                "Operational overhead",
                "Requires expertise",
            ],
            monthly_cost_range=(200.00, 2000.00),
            cost_drivers=[
                "Cluster: $100-500/mo minimum",
                "Instance hours: Primary cost",
                "Storage: EBS costs",
                "Data transfer: Ingestion",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Log aggregation decision:

    1. What's your primary need?
       Storage/compliance → S3 central bucket
       Real-time analysis → CloudWatch or OpenSearch
       Both → Hybrid approach

    2. What's your log volume?
       < 50GB/month → CloudWatch is fine
       50-500GB/month → S3 primary, CloudWatch for select logs
       > 500GB/month → S3 required for cost, OpenSearch for analysis

    3. Do you have SIEM?
       YES → S3 delivery, SIEM does analysis
       NO → Need CloudWatch or OpenSearch for analysis

    Recommended architecture (multi-account):
    ```
    [Workload Account]           [Log Archive Account]
         │                              │
    CloudWatch ──subscription──> Kinesis Firehose
         │                              │
         └──────────────────────> Central S3 Bucket
                                        │
                                   Athena / SIEM
    ```

    Log types to centralize:
    - CloudTrail (required) - via Organization trail
    - VPC Flow Logs
    - Application logs
    - Load balancer access logs
    - CloudFront access logs
    - WAF logs
    - Lambda logs (for critical functions)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.2: Log aggregation enables monitoring
    - CC7.3: Centralized logs enable analysis

    Auditors want to see:
    - All logs in one place (or documented locations)
    - Retention policy documented and enforced
    - Evidence of log review process
    - Immutability (S3 Object Lock)
    """,
    common_mistakes=[
        "Logs scattered across accounts with no aggregation",
        "No retention policy (logs grow forever)",
        "CloudWatch for everything (expensive)",
        "Not using lifecycle policies on S3",
        "No log analysis process (collecting but not reviewing)",
    ],
)


# =============================================================================
# CLOUDTRAIL PATTERNS
# =============================================================================

CLOUDTRAIL_PATTERNS = ArchitectureDecision(
    question="How should CloudTrail be configured?",
    options=[
        DecisionOption(
            name="Organization Trail",
            description="Single CloudTrail trail for entire Organization",
            when_to_use=[
                "Multi-account environments",
                "Central log management",
                "All organizations (strongly recommended)",
            ],
            when_not_to_use=[
                "Single account (use account trail)",
            ],
            pros=[
                "Automatic for all accounts",
                "New accounts included automatically",
                "Single configuration point",
                "First trail per region is free",
            ],
            cons=[
                "Large volume of events",
                "Central bucket can be huge",
                "All-or-nothing per region",
            ],
            monthly_cost_range=(0, 50.00),
            cost_drivers=[
                "First trail (management events): FREE",
                "S3 storage: $0.023/GB",
                "Data events: $0.10/100K events (if enabled)",
            ],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Organization Trail + Data Events",
            description="Organization trail with S3 and Lambda data events",
            when_to_use=[
                "Need to track S3 object access",
                "Compliance requiring data-level logging",
                "Security investigations",
            ],
            when_not_to_use=[
                "High S3/Lambda activity (expensive)",
                "Data events not required",
            ],
            pros=[
                "Full audit trail",
                "S3 object-level logging",
                "Lambda invocation logging",
            ],
            cons=[
                "Can be very expensive",
                "Large log volume",
                "Select buckets/functions carefully",
            ],
            monthly_cost_range=(10.00, 1000.00),
            cost_drivers=[
                "Data events: $0.10/100K events",
                "High-traffic bucket: $100+/mo easily",
                "Select only sensitive buckets",
            ],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Organization Trail + Insights",
            description="Organization trail with CloudTrail Insights",
            when_to_use=[
                "Want anomaly detection",
                "Security monitoring use case",
                "Unusual API activity detection",
            ],
            when_not_to_use=[
                "Cost optimization priority",
                "Already have SIEM detection",
            ],
            pros=[
                "Automatic anomaly detection",
                "Unusual activity alerts",
                "No custom rules needed",
            ],
            cons=[
                "Additional cost",
                "May generate false positives",
            ],
            monthly_cost_range=(20.00, 200.00),
            cost_drivers=[
                "Insights: $0.35/100K events analyzed",
                "Only management events",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    CloudTrail configuration:

    1. ALWAYS create Organization Trail
       - Management events in all regions
       - Deliver to Log Archive S3 bucket
       - Enable log file validation
       - Enable encryption (KMS)

    2. Data events - be selective:
       - Sensitive S3 buckets only
       - Critical Lambda functions only
       - Cost can explode quickly

    3. Enable Insights if:
       - You don't have SIEM with similar capability
       - Want AWS-native anomaly detection
       - Budget allows

    Organization Trail setup:
    1. Create in management account
    2. Target S3 bucket in Log Archive account
    3. Enable for all regions
    4. Enable log file validation
    5. Encrypt with KMS key
    6. Enable insights (optional)

    S3 bucket policy for CloudTrail:
    - Allow cloudtrail.amazonaws.com
    - Allow from organization
    - Deny delete for compliance
    - Enable Object Lock (optional but recommended)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.1: CloudTrail logs access to AWS
    - CC7.2: API activity monitoring
    - CC7.3: Log analysis capability

    CloudTrail is MANDATORY for SOC 2:
    - Provides audit trail of all API calls
    - Required for demonstrating access monitoring
    - Retention: Minimum 90 days, recommended 1 year
    """,
    common_mistakes=[
        "Not enabling Organization Trail",
        "Single-region trail only",
        "No log file validation",
        "No encryption",
        "Data events on high-traffic buckets ($$)",
        "Not protecting the S3 bucket",
    ],
)


# =============================================================================
# APPLICATION LOGGING PATTERNS
# =============================================================================

APPLICATION_LOG_PATTERNS = ArchitectureDecision(
    question="How should application logs be managed?",
    options=[
        DecisionOption(
            name="CloudWatch Logs with Insights",
            description="Application logs to CloudWatch with Logs Insights queries",
            when_to_use=[
                "AWS-native approach",
                "Moderate log volume",
                "Simple query needs",
                "Lambda, ECS, EKS workloads",
            ],
            when_not_to_use=[
                "High log volume (> 100GB/mo)",
                "Complex analytics needed",
                "Long-term retention (use S3 tier)",
            ],
            pros=[
                "Native integration",
                "Real-time streaming",
                "Logs Insights queries",
                "Metric filters for alerts",
            ],
            cons=[
                "Expensive at scale",
                "Limited retention options",
                "Query syntax learning curve",
            ],
            monthly_cost_range=(10.00, 500.00),
            cost_drivers=[
                "Ingestion: $0.50/GB",
                "Storage: $0.03/GB/month",
                "Queries: Included in ingestion",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Structured Logging to S3 via Firehose",
            description="JSON logs via Kinesis Firehose to S3 for Athena queries",
            when_to_use=[
                "High log volume",
                "Long-term storage needed",
                "Athena for analysis",
                "Cost optimization",
            ],
            when_not_to_use=[
                "Real-time needs",
                "Simple logging requirements",
            ],
            pros=[
                "Cost-effective storage",
                "Parquet format for efficiency",
                "Athena SQL queries",
                "Lifecycle to Glacier",
            ],
            cons=[
                "Near-real-time (1-5 min delay)",
                "Setup complexity",
                "Athena query costs",
            ],
            monthly_cost_range=(5.00, 200.00),
            cost_drivers=[
                "Firehose: $0.029/GB",
                "S3: $0.023/GB",
                "Athena: $5/TB scanned",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Third-Party Logging (Datadog, Splunk)",
            description="External log management platform",
            when_to_use=[
                "Already using third-party platform",
                "Advanced analytics needed",
                "Multi-cloud environment",
                "Dedicated SRE/DevOps team",
            ],
            when_not_to_use=[
                "AWS-only environment preference",
                "Cost sensitivity",
            ],
            pros=[
                "Powerful analytics",
                "Pre-built dashboards",
                "Cross-platform support",
                "Advanced alerting",
            ],
            cons=[
                "Significant cost",
                "Data egress from AWS",
                "Vendor dependency",
            ],
            monthly_cost_range=(100.00, 5000.00),
            cost_drivers=[
                "Platform fees (per GB or host)",
                "Data egress: $0.09/GB",
                "Varies widely by vendor",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    Application logging strategy:

    1. Standardize log format:
       - JSON structured logging
       - Include: timestamp, level, service, requestId, message
       - Consistent field names across services

    2. Choose destination by volume:
       < 10GB/mo per app → CloudWatch Logs
       10-100GB/mo → Firehose to S3 + CloudWatch for alerts
       > 100GB/mo → S3 primary, sample to CloudWatch

    3. Set up log levels appropriately:
       - Production: INFO and above
       - Staging: DEBUG
       - Development: ALL

    4. Enable log correlation:
       - X-Ray trace ID in logs
       - Request ID propagation
       - Service name tagging

    Recommended log structure:
    ```json
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "level": "INFO",
      "service": "order-api",
      "requestId": "abc-123",
      "traceId": "1-abc-def",
      "message": "Order created",
      "orderId": "ord-456",
      "userId": "user-789"
    }
    ```
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.2: Application logging for monitoring

    Application logs support:
    - Security event detection
    - Troubleshooting and debugging
    - Audit trail for application actions
    """,
    common_mistakes=[
        "Unstructured log formats",
        "No correlation IDs",
        "Logging sensitive data (PII, credentials)",
        "No log level configuration",
        "Logging everything at DEBUG in production",
    ],
)


# =============================================================================
# LOG RETENTION PATTERNS
# =============================================================================

LOG_RETENTION_PATTERNS = ArchitectureDecision(
    question="What log retention policies should be implemented?",
    options=[
        DecisionOption(
            name="Compliance Minimum (90 Days)",
            description="90-day retention for basic compliance",
            when_to_use=[
                "Minimum compliance requirements",
                "Cost optimization priority",
                "Non-regulated environments",
            ],
            when_not_to_use=[
                "Regulated industries",
                "Legal hold requirements",
            ],
            pros=[
                "Lowest storage cost",
                "Meets basic requirements",
                "Quick to implement",
            ],
            cons=[
                "May not meet all compliance",
                "Limited investigation window",
                "May need exceptions for specific logs",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Just storage costs, varies by volume"],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard Retention (1 Year)",
            description="1-year retention for typical enterprise needs",
            when_to_use=[
                "SOC 2 compliance",
                "Most organizations",
                "Security investigation needs",
            ],
            when_not_to_use=[
                "Strict storage constraints",
                "Very cost sensitive",
            ],
            pros=[
                "Meets most compliance",
                "Good investigation window",
                "Industry standard",
            ],
            cons=[
                "More storage cost",
                "Need lifecycle policies",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=["Storage with Glacier after 90 days"],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Extended Retention (7 Years)",
            description="7-year retention for regulated industries",
            when_to_use=[
                "Financial services",
                "Healthcare (HIPAA)",
                "Legal requirements",
                "SEC/FINRA regulations",
            ],
            when_not_to_use=[
                "No regulatory requirement",
                "Cost prohibitive",
            ],
            pros=[
                "Meets strictest requirements",
                "Full audit trail",
                "Legal protection",
            ],
            cons=[
                "Significant storage costs",
                "Need efficient archival",
                "Retrieval can be slow/expensive",
            ],
            monthly_cost_range=(0, 0),
            cost_drivers=[
                "Deep Archive for years 2-7",
                "$0.00099/GB for Deep Archive",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    Retention policy by log type:

    | Log Type | Minimum | Recommended | Regulated |
    |----------|---------|-------------|-----------|
    | CloudTrail | 90 days | 1 year | 7 years |
    | VPC Flow Logs | 90 days | 1 year | 7 years |
    | Application | 30 days | 90 days | 1 year |
    | Access Logs | 90 days | 1 year | 7 years |
    | Security Logs | 1 year | 2 years | 7 years |

    S3 Lifecycle policy example:
    - 0-90 days: S3 Standard
    - 90-365 days: S3 Glacier Instant Retrieval
    - 1-7 years: S3 Glacier Deep Archive
    - 7+ years: Delete (unless legal hold)

    CloudWatch Logs retention:
    - 7 days: Real-time analysis logs
    - 30 days: Application logs
    - 90 days: Security-relevant logs
    - Export to S3 for longer retention

    Cost optimization:
    - Use S3 Intelligent-Tiering for variable access
    - Compress logs (gzip, Parquet)
    - Filter unnecessary logs at source
    - Use sampling for high-volume, low-value logs
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.2: Retention enables historical analysis

    Auditors will check:
    - Documented retention policy
    - Evidence of policy enforcement
    - Ability to retrieve historical logs
    - Immutability for compliance logs
    """,
    common_mistakes=[
        "No retention policy (logs grow forever)",
        "Same retention for all log types",
        "Not using Glacier for old logs",
        "Deleting logs too soon",
        "No Object Lock for compliance logs",
    ],
)


def get_logging_patterns() -> dict:
    """Get all logging architecture patterns."""
    return {
        "log_aggregation": LOG_AGGREGATION_PATTERNS,
        "cloudtrail": CLOUDTRAIL_PATTERNS,
        "application_logs": APPLICATION_LOG_PATTERNS,
        "log_retention": LOG_RETENTION_PATTERNS,
    }
