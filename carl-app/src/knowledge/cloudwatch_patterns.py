"""
CloudWatch Monitoring and Alerting Patterns for CARL Foundation Builder.

Comprehensive patterns for CloudWatch metrics, alarms, dashboards,
and notification strategies.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# CLOUDWATCH ALARM STRATEGY PATTERNS
# =============================================================================

CLOUDWATCH_ALARM_PATTERNS = ArchitectureDecision(
    question="What CloudWatch alarm strategy should be implemented?",
    options=[
        DecisionOption(
            name="Basic Resource Alarms",
            description="Essential alarms for critical resources only",
            when_to_use=[
                "Getting started with monitoring",
                "Small environments (< 10 resources)",
                "Development/testing environments",
                "Cost optimization priority",
            ],
            when_not_to_use=[
                "Production environments",
                "SOC 2 compliance requirements",
                "Need comprehensive monitoring",
            ],
            pros=[
                "Low cost",
                "Simple to manage",
                "Quick to set up",
                "Focuses on critical issues",
            ],
            cons=[
                "Limited coverage",
                "May miss important issues",
                "Not compliant-ready",
                "Manual alarm creation",
            ],
            monthly_cost_range=(0, 10.00),
            cost_drivers=[
                "Standard metrics: Free",
                "Alarms: First 10 free, then $0.10/alarm/mo",
                "5-10 alarms typical",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Standard Alarm Coverage",
            description="Comprehensive alarms for all critical resources",
            when_to_use=[
                "Production environments",
                "SOC 2 compliance",
                "Most organizations",
                "Need proactive monitoring",
            ],
            when_not_to_use=[
                "Very small environments",
                "Development/sandbox only",
            ],
            pros=[
                "Good coverage",
                "Compliance-friendly",
                "Proactive issue detection",
                "Reasonable cost",
            ],
            cons=[
                "More alarms to manage",
                "Higher cost than basic",
                "Need alarm tuning",
            ],
            monthly_cost_range=(10.00, 50.00),
            cost_drivers=[
                "Alarms: $0.10/alarm/mo",
                "50-200 alarms typical",
                "SNS notifications: $0.50/100K",
            ],
            soc2_controls=["CC4.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Enterprise Monitoring",
            description="Advanced monitoring with composite alarms and anomaly detection",
            when_to_use=[
                "Large production environments",
                "Critical applications",
                "Need sophisticated alerting",
                "Reduce alert fatigue",
            ],
            when_not_to_use=[
                "Simple environments",
                "Cost is primary concern",
                "Don't need advanced features",
            ],
            pros=[
                "Composite alarms reduce noise",
                "Anomaly detection (ML-based)",
                "Metric math for custom metrics",
                "Advanced dashboards",
            ],
            cons=[
                "Higher cost",
                "More complex to configure",
                "Requires tuning",
            ],
            monthly_cost_range=(50.00, 200.00),
            cost_drivers=[
                "Standard alarms: $0.10/alarm/mo",
                "Composite alarms: $0.50/alarm/mo",
                "Anomaly detection: $0.30/metric/mo",
                "Contributor Insights: $0.50/rule/mo",
            ],
            soc2_controls=["CC4.1", "CC4.2", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    CloudWatch alarm decision tree:

    1. What type of environment?
       Development/Sandbox → Basic alarms
       Production → Standard or Enterprise

    2. Do you have SOC 2 requirements?
       YES → Minimum Standard alarms
       NO → Basic may be sufficient

    3. Do you have alert fatigue issues?
       YES → Enterprise (composite alarms)
       NO → Standard is fine

    Essential alarms for all production resources:

    **EC2 Instances:**
    - CPUUtilization > 80% for 5 minutes
    - StatusCheckFailed_System = 1
    - StatusCheckFailed_Instance = 1

    **RDS Databases:**
    - CPUUtilization > 80% for 10 minutes
    - FreeStorageSpace < 10GB
    - DatabaseConnections > 80% of max
    - ReadLatency or WriteLatency > 1 second

    **Lambda Functions:**
    - Errors > 1% of invocations
    - Throttles > 0
    - Duration > 80% of timeout
    - ConcurrentExecutions > 80% of limit

    **ALB/NLB:**
    - TargetResponseTime > 1 second (p99)
    - UnHealthyHostCount > 0
    - HTTPCode_Target_5XX_Count > 10/min
    - HTTPCode_ELB_5XX_Count > 10/min

    **DynamoDB:**
    - UserErrors > 10/min
    - SystemErrors > 0
    - ConsumedReadCapacityUnits > 80%
    - ConsumedWriteCapacityUnits > 80%

    **ECS/Fargate:**
    - CPUUtilization > 80%
    - MemoryUtilization > 80%
    - RunningTaskCount < DesiredCount

    **API Gateway:**
    - 5XXError > 1%
    - Count (requests) < expected minimum
    - Latency > 1000ms (p99)

    Alarm best practices:
    - Use multiple data points (e.g., 3 out of 5)
    - Set appropriate evaluation periods
    - Use "M out of N" for transient issues
    - Always have actions (SNS topic)
    - Tag alarms for organization
    - Document alarm rationale

    Composite alarm example (reduce noise):
    ```
    Alarm: EC2-Instance-Unhealthy
    Condition:
      (CPUUtilization > 90% AND StatusCheckFailed = 1)
      OR
      (MemoryUtilization > 90% AND StatusCheckFailed = 1)
    ```

    Anomaly detection use cases:
    - Traffic patterns (request count)
    - Error rates (when normal varies)
    - Cost anomalies (unexpected spikes)
    - Resource utilization (seasonal patterns)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC4.1: Monitoring activities (alarms detect issues)
    - CC4.2: Evaluation of monitoring results
    - CC7.2: Security monitoring (detect security events)

    CloudWatch alarms demonstrate:
    - Proactive monitoring of system health
    - Automated detection of anomalies
    - Audit trail of alerts
    - Response to monitoring events

    Auditors want to see:
    - Documented alarm strategy
    - Evidence of alarm configuration
    - Alarm history (CloudWatch logs)
    - Response to alarms (incident tickets)
    """,
    common_mistakes=[
        "Too sensitive alarms (alert fatigue)",
        "No alarms on critical resources",
        "Alarms with no actions (no SNS topic)",
        "Not using multiple data points",
        "Not documenting alarm thresholds",
        "No alarm testing",
    ],
)


# =============================================================================
# NOTIFICATION STRATEGY PATTERNS
# =============================================================================

NOTIFICATION_STRATEGY_PATTERNS = ArchitectureDecision(
    question="How should CloudWatch alarm notifications be configured?",
    options=[
        DecisionOption(
            name="SNS to Email",
            description="SNS topics with email subscriptions",
            when_to_use=[
                "Getting started",
                "Small teams",
                "Email-based workflows",
                "Simple notification needs",
            ],
            when_not_to_use=[
                "Need incident management",
                "Large teams",
                "24/7 on-call rotation",
            ],
            pros=[
                "Simple to set up",
                "No additional tools needed",
                "Free (SNS)",
                "Email audit trail",
            ],
            cons=[
                "Email can be ignored",
                "No escalation",
                "No on-call rotation",
                "Limited actionability",
            ],
            monthly_cost_range=(0, 1.00),
            cost_drivers=[
                "SNS: $0.50 per 1M notifications",
                "Email: Free",
            ],
            soc2_controls=["CC7.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="SNS to Slack",
            description="SNS topics posting to Slack channels",
            when_to_use=[
                "Slack-based team communication",
                "Need team visibility",
                "Collaborative response",
                "Most organizations",
            ],
            when_not_to_use=[
                "Don't use Slack",
                "Need formal incident management",
            ],
            pros=[
                "Team visibility",
                "Quick response",
                "Can integrate with Lambda for rich formatting",
                "Collaborative",
            ],
            cons=[
                "Slack can be noisy",
                "No formal on-call",
                "Requires Lambda for formatting",
            ],
            monthly_cost_range=(1.00, 10.00),
            cost_drivers=[
                "SNS: $0.50/1M notifications",
                "Lambda (formatting): $1-5/mo",
            ],
            soc2_controls=["CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="SNS to PagerDuty/Opsgenie",
            description="Integration with incident management platform",
            when_to_use=[
                "24/7 on-call rotation",
                "Need escalation policies",
                "Multiple teams",
                "Production critical applications",
            ],
            when_not_to_use=[
                "Small teams with no on-call",
                "Development environments",
                "Budget constraints",
            ],
            pros=[
                "On-call rotation",
                "Escalation policies",
                "Incident management",
                "Acknowledgment tracking",
                "Integration with ITSM",
            ],
            cons=[
                "Additional cost (PagerDuty license)",
                "More complex setup",
                "Requires training",
            ],
            monthly_cost_range=(20.00, 100.00),
            cost_drivers=[
                "PagerDuty: approx. $20-40/user/mo",
                "Opsgenie: approx. $9-29/user/mo",
                "SNS: Minimal",
            ],
            soc2_controls=["CC7.3", "CC4.1"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Multi-Channel Strategy",
            description="Different notification channels by severity",
            when_to_use=[
                "Large organizations",
                "Different SLAs by severity",
                "Want to reduce noise",
                "Sophisticated operations team",
            ],
            when_not_to_use=[
                "Small teams",
                "Simple notification needs",
            ],
            pros=[
                "Reduced noise",
                "Appropriate urgency",
                "Flexible",
                "Can route by team",
            ],
            cons=[
                "More complex to manage",
                "Multiple integrations",
                "Requires discipline",
            ],
            monthly_cost_range=(20.00, 150.00),
            cost_drivers=[
                "Multiple SNS topics",
                "Incident management platforms",
                "Lambda for routing",
            ],
            soc2_controls=["CC7.3", "CC4.1"],
            implementation_complexity="high",
            operational_overhead="high",
        },
    ],
    recommendation_logic="""
    Notification strategy by severity:

    **CRITICAL (P1):**
    - PagerDuty/Opsgenie page
    - Immediate phone call/SMS
    - Slack #incidents channel
    - Example: Database down, site outage

    **HIGH (P2):**
    - PagerDuty/Opsgenie alert
    - Slack #alerts channel
    - Email to on-call
    - Example: High error rate, degraded performance

    **MEDIUM (P3):**
    - Slack #monitoring channel
    - Email to team
    - Example: High CPU, approaching threshold

    **LOW (P4):**
    - Slack #monitoring channel (once/hour digest)
    - Email digest
    - Example: Informational, trends

    Multi-channel setup:
    ```
    SNS Topics:
    - alarms-critical  → PagerDuty + Slack #incidents
    - alarms-high      → PagerDuty + Slack #alerts
    - alarms-medium    → Slack #monitoring + Email
    - alarms-low       → Email digest
    ```

    SNS to Slack setup:
    1. Create SNS topic
    2. Create Lambda function for formatting
    3. Subscribe Lambda to SNS topic
    4. Lambda posts to Slack webhook
    5. Format with alarm details, runbook links

    SNS to PagerDuty setup:
    1. Create PagerDuty service
    2. Get integration email
    3. Subscribe email to SNS topic
    4. Configure urgency mapping
    5. Set escalation policies

    Best practices:
    - Always have a default SNS topic
    - Tag alarms with severity
    - Include runbook links in alarm description
    - Test notifications
    - Review and tune regularly
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.3: Incident response (notifications trigger response)
    - CC4.1: Monitoring results communicated

    Notification strategy demonstrates:
    - Timely response to security events
    - Escalation procedures
    - Audit trail of notifications
    - Acknowledgment tracking

    Auditors want to see:
    - Documented notification procedures
    - On-call rotation (if 24/7)
    - Evidence of timely response
    - Incident management integration
    """,
    common_mistakes=[
        "All alerts to one channel (noise)",
        "No severity differentiation",
        "Email-only for critical alerts",
        "Not testing notification delivery",
        "No escalation for unacknowledged alerts",
    ],
)


# =============================================================================
# DASHBOARD PATTERNS
# =============================================================================

DASHBOARD_PATTERNS = ArchitectureDecision(
    question="What CloudWatch dashboard strategy should be implemented?",
    options=[
        DecisionOption(
            name="Single Overview Dashboard",
            description="One dashboard showing key metrics",
            when_to_use=[
                "Small environments",
                "Getting started",
                "Need simple overview",
            ],
            when_not_to_use=[
                "Many applications/services",
                "Different teams",
            ],
            pros=[
                "Simple",
                "Easy to maintain",
                "Quick overview",
            ],
            cons=[
                "Limited detail",
                "Doesn't scale",
                "Hard to find specific metrics",
            ],
            monthly_cost_range=(3.00, 3.00),
            cost_drivers=[
                "Dashboard: $3/mo per dashboard",
            ],
            soc2_controls=["CC4.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Service-Based Dashboards",
            description="Separate dashboard per application/service",
            when_to_use=[
                "Microservices architecture",
                "Multiple applications",
                "Different teams own services",
                "Most organizations",
            ],
            when_not_to_use=[
                "Monolithic application",
                "Very small environment",
            ],
            pros=[
                "Focused views",
                "Team ownership",
                "Easier to find relevant metrics",
                "Scales well",
            ],
            cons=[
                "More dashboards to maintain",
                "Higher cost",
                "Need navigation",
            ],
            monthly_cost_range=(15.00, 60.00),
            cost_drivers=[
                "Dashboard: $3/mo each",
                "5-20 dashboards typical",
            ],
            soc2_controls=["CC4.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Hierarchical Dashboard Strategy",
            description="Executive → Team → Service dashboards",
            when_to_use=[
                "Large organizations",
                "Multiple teams",
                "Need different views by role",
                "Enterprise environments",
            ],
            when_not_to_use=[
                "Small teams",
                "Simple environments",
            ],
            pros=[
                "Role-appropriate views",
                "Executive visibility",
                "Team autonomy",
                "Comprehensive",
            ],
            cons=[
                "Many dashboards",
                "Higher cost",
                "Requires governance",
            ],
            monthly_cost_range=(30.00, 150.00),
            cost_drivers=[
                "Dashboard: $3/mo each",
                "10-50 dashboards",
            ],
            soc2_controls=["CC4.1", "CC4.2", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Recommended dashboard hierarchy:

    **Executive Dashboard:**
    - Overall system health (green/yellow/red)
    - Total request count and errors
    - P99 latency across all services
    - Cost trends
    - Security alerts summary
    - Availability SLA status

    **Team Dashboard (per team):**
    - Services owned by team
    - Request rates and error rates
    - Latency (p50, p95, p99)
    - Resource utilization
    - Recent alarms
    - Deployment markers

    **Service Dashboard (per service):**
    - Request metrics (count, rate, errors)
    - Latency distribution
    - Dependency health
    - Resource metrics (CPU, memory, disk)
    - Custom business metrics
    - Log insights

    **Infrastructure Dashboard:**
    - EC2 instance health
    - RDS performance
    - Lambda concurrency
    - NAT Gateway bytes
    - VPC Flow Logs summary

    Dashboard best practices:
    - Use automatic dashboards (AWS-managed)
    - Add custom metrics for business KPIs
    - Use annotations for deployments
    - Link to runbooks
    - Share via URL or embed
    - Use metric math for calculations
    - Set auto-refresh (1-5 minutes)

    Metric math examples:
    - Error rate: SUM(Errors) / SUM(Requests) * 100
    - Availability: (1 - SUM(5XX) / SUM(Requests)) * 100
    - Cost per request: TotalCost / SUM(Requests)
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC4.1: Dashboards support monitoring activities
    - CC4.2: Results evaluated and communicated
    - CC7.2: Security metrics visible

    Dashboards demonstrate:
    - Ongoing monitoring
    - Visibility into system health
    - Trend analysis
    - Executive oversight

    Auditors may review:
    - Dashboard configurations
    - Who has access to dashboards
    - How dashboards are used in operations
    """,
    common_mistakes=[
        "Too many metrics on one dashboard",
        "No dashboard governance",
        "Not using automatic dashboards",
        "No deployment markers",
        "Stale dashboards (not maintained)",
    ],
)


def get_cloudwatch_patterns() -> dict:
    """Get all CloudWatch monitoring patterns."""
    return {
        "alarm_strategy": CLOUDWATCH_ALARM_PATTERNS,
        "notification_strategy": NOTIFICATION_STRATEGY_PATTERNS,
        "dashboard_strategy": DASHBOARD_PATTERNS,
    }
