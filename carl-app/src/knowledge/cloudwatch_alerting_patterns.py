"""
CloudWatch Alerting & Monitoring Patterns for CARL Foundation Builder.

Comprehensive patterns for CloudWatch alarms, composite alarms, dashboards,
and notification strategies for production AWS environments.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# CLOUDWATCH METRIC ALARMS PATTERNS
# =============================================================================

CLOUDWATCH_ALARMS_PATTERNS = ArchitectureDecision(
    question="How should CloudWatch metric alarms be configured?",
    options=[
        DecisionOption(
            name="Basic Metric Alarms",
            description="Simple threshold-based alarms for key metrics",
            when_to_use=[
                "Getting started with monitoring",
                "Small infrastructure (<10 resources)",
                "Development/staging environments",
                "Basic availability monitoring",
            ],
            when_not_to_use=[
                "Production with SLA requirements",
                "Complex failure scenarios",
                "Need anomaly detection",
                "Require composite alarm logic",
            ],
            pros=[
                "Simple to configure",
                "Easy to understand",
                "Low cost (first 10 alarms free)",
                "Quick to implement",
                "Standard AWS console management",
            ],
            cons=[
                "Static thresholds don't adapt",
                "Can't model complex scenarios",
                "Prone to false positives",
                "No correlation between metrics",
                "Manual threshold tuning required",
            ],
            monthly_cost_range=(0.00, 5.00),
            cost_drivers=[
                "Standard alarms: $0.10/alarm/month (first 10 free)",
                "High-resolution alarms: $0.30/alarm/month",
                "Typical small deployment: $0-5/month",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="low",
            operational_overhead="medium",
            implementation_guidance="""
# Basic CloudWatch Alarm Configuration

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "high-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300  # 5 minutes
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Alert when CPU exceeds 80% for 10 minutes"

  dimensions = {
    InstanceId = aws_instance.app.id
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = {
    Environment = "production"
    ManagedBy   = "CARL"
  }
}

# Key Metrics to Monitor:
# - EC2: CPUUtilization, StatusCheckFailed, NetworkIn/Out
# - RDS: DatabaseConnections, CPUUtilization, FreeStorageSpace
# - Lambda: Errors, Duration, Throttles, ConcurrentExecutions
# - ALB: TargetResponseTime, UnHealthyHostCount, HTTPCode_Target_5XX_Count
# - API Gateway: 5XXError, Latency, Count (requests)
# - DynamoDB: UserErrors, SystemErrors, ConsumedReadCapacityUnits
""",
            validation_checklist=[
                "Alarm configured for critical metrics (CPU, memory, errors)",
                "Evaluation periods set appropriately (2-3 for production)",
                "Threshold values based on baseline testing",
                "SNS topic configured with correct subscribers",
                "Alarm actions include notification (alarm_actions) and recovery if applicable",
                "Alarm descriptions are clear and actionable",
                "Tags applied for cost tracking",
            ],
        ),
        DecisionOption(
            name="Composite Alarms for Complex Scenarios",
            description="Multi-metric alarms using AND/OR logic for sophisticated alerting",
            when_to_use=[
                "Production environments with SLA requirements",
                "Need to reduce false positives",
                "Complex failure scenarios (e.g., high CPU AND high memory AND errors)",
                "Cascading alerts (suppress child alarms when parent fails)",
            ],
            when_not_to_use=[
                "Simple single-metric monitoring sufficient",
                "Cost-sensitive deployments (composite alarms cost more)",
                "Team unfamiliar with alarm composition",
            ],
            pros=[
                "Reduces alert fatigue by combining conditions",
                "Models real failure scenarios accurately",
                "Suppresses cascading alarms",
                "Better signal-to-noise ratio",
                "More actionable alerts",
            ],
            cons=[
                "More complex to configure",
                "Higher cost ($0.50/alarm vs $0.10)",
                "Harder to troubleshoot",
                "Requires understanding of boolean logic",
            ],
            monthly_cost_range=(5.00, 50.00),
            cost_drivers=[
                "Composite alarms: $0.50/alarm/month",
                "Underlying metric alarms: $0.10/alarm/month each",
                "Typical production setup: $5-50/month (10-100 alarms)",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
            implementation_guidance="""
# Composite Alarm Example: Application Degradation

resource "aws_cloudwatch_composite_alarm" "app_degraded" {
  alarm_name          = "application-degraded"
  alarm_description   = "Application is degraded: high errors AND high latency"

  # Trigger when BOTH conditions are true
  alarm_rule = "ALARM(\${aws_cloudwatch_metric_alarm.high_error_rate.alarm_name}) AND ALARM(\${aws_cloudwatch_metric_alarm.high_latency.alarm_name})"

  alarm_actions = [
    aws_sns_topic.critical_alerts.arn,
    aws_sns_topic.pagerduty.arn  # Page on-call engineer
  ]

  tags = {
    Severity    = "critical"
    Environment = "production"
  }
}

# Suppress Child Alarms Pattern (Avoid Alert Storms)
resource "aws_cloudwatch_composite_alarm" "database_down" {
  alarm_name = "database-down"

  alarm_rule = "ALARM(\${aws_cloudwatch_metric_alarm.rds_connection_failed.alarm_name})"

  alarm_actions = [aws_sns_topic.critical_alerts.arn]

  # Suppress child alarms that would fire when DB is down
  actions_suppressor {
    alarm            = aws_cloudwatch_metric_alarm.rds_connection_failed.alarm_name
    extension_period = 300  # Suppress for 5 minutes after DB alarm clears
    wait_period      = 60   # Wait 1 minute before suppressing
  }
}

# Use Cases for Composite Alarms:
# 1. Service Degradation: High errors AND high latency AND low throughput
# 2. Resource Exhaustion: High CPU AND high memory AND high disk I/O
# 3. Cascading Failures: Database down triggers app errors (suppress app alarms)
# 4. Multi-Region Health: Alarm if 2+ regions have issues simultaneously
""",
            validation_checklist=[
                "Composite alarm rule uses correct boolean logic (AND/OR/NOT)",
                "All child alarms exist and are properly configured",
                "Alarm suppression configured to avoid alert storms",
                "Critical alarms trigger PagerDuty or similar on-call system",
                "Non-critical alarms go to Slack or email only",
                "Alarm names are descriptive and indicate severity",
                "Test alarm triggers in staging before production",
            ],
        ),
        DecisionOption(
            name="Anomaly Detection Alarms (Advanced)",
            description="Machine learning-based alarms that adapt to traffic patterns",
            when_to_use=[
                "Highly variable traffic patterns",
                "Don't know appropriate static thresholds",
                "Want to reduce manual threshold tuning",
                "Need to detect unusual patterns (not just threshold breaches)",
            ],
            when_not_to_use=[
                "Predictable workloads with known limits",
                "Need deterministic alerting (ML can have false negatives)",
                "Cost-sensitive (anomaly detection costs more)",
                "Require immediate alerting (ML needs training period)",
            ],
            pros=[
                "Automatically adjusts to traffic patterns",
                "No manual threshold tuning",
                "Detects anomalies vs absolute thresholds",
                "Handles seasonality (weekday vs weekend)",
                "Reduces false positives over time",
            ],
            cons=[
                "Higher cost (anomaly detection fees)",
                "Requires 2-week training period",
                "Can miss sudden spikes during training",
                "Less predictable than static thresholds",
                "Harder to explain to stakeholders",
            ],
            monthly_cost_range=(5.00, 100.00),
            cost_drivers=[
                "Anomaly detection: $0.30/metric/month",
                "Standard alarms: $0.10/alarm/month",
                "High-volume metrics: Can add up quickly",
                "Typical production: $5-100/month (15-300 metrics)",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
            implementation_guidance="""
# Anomaly Detection Alarm Configuration

resource "aws_cloudwatch_metric_alarm" "anomalous_requests" {
  alarm_name          = "anomalous-request-rate"
  comparison_operator = "LessThanLowerOrGreaterThanUpperThreshold"
  evaluation_periods  = 2
  threshold_metric_id = "ad1"  # Reference anomaly detection

  # Metric to monitor
  metric_query {
    id          = "m1"
    return_data = true

    metric {
      metric_name = "RequestCount"
      namespace   = "AWS/ApplicationELB"
      period      = 300
      stat        = "Sum"

      dimensions = {
        LoadBalancer = aws_lb.app.arn_suffix
      }
    }
  }

  # Anomaly detection band
  metric_query {
    id          = "ad1"
    expression  = "ANOMALY_DETECTION_BAND(m1, 2)"  # 2 standard deviations
    label       = "RequestCount (expected)"
    return_data = true
  }

  alarm_description = "Request rate is outside expected range (ML-based)"
  alarm_actions     = [aws_sns_topic.alerts.arn]

  tags = {
    Type = "AnomalyDetection"
  }
}

# Best Practices:
# - Use 2 standard deviations for balanced sensitivity
# - Allow 2-week training period before relying on alarms
# - Combine with static alarms for critical thresholds
# - Monitor anomaly detection accuracy and adjust bands
# - Use for highly variable metrics (traffic, API calls, errors)
# - Avoid for metrics with known limits (disk space, connections)
""",
            validation_checklist=[
                "Anomaly detection configured with appropriate band (usually 2 std dev)",
                "Training period completed (minimum 2 weeks of data)",
                "Alarm tested with historical data to validate accuracy",
                "Still have static alarms for hard limits (e.g., 100% disk)",
                "Cost impact reviewed (anomaly detection per metric)",
                "Documentation explains how ML model works for on-call team",
            ],
        ),
    ],
    estimated_implementation_time="2-3 days",
    recommendation_strategy="Start with Basic Metric Alarms for critical resources, add Composite Alarms for production environments to reduce false positives, use Anomaly Detection for highly variable metrics where static thresholds fail.",
)


# =============================================================================
# NOTIFICATION STRATEGIES PATTERNS
# =============================================================================

NOTIFICATION_STRATEGIES_PATTERNS = ArchitectureDecision(
    question="How should CloudWatch alarm notifications be delivered?",
    options=[
        DecisionOption(
            name="SNS to Email",
            description="Simple email notifications via SNS topics",
            when_to_use=[
                "Small teams (<5 people)",
                "Non-critical systems",
                "Development/staging environments",
                "Budget-constrained",
            ],
            when_not_to_use=[
                "Production systems requiring on-call",
                "Need mobile push notifications",
                "Require alert acknowledgment",
                "High-volume alerts (email fatigue)",
            ],
            pros=[
                "Free (first 1,000 emails/month)",
                "Simple to set up",
                "No third-party dependencies",
                "Works with existing email infrastructure",
            ],
            cons=[
                "No mobile push",
                "No acknowledgment tracking",
                "Email can be delayed",
                "Prone to alert fatigue",
                "No escalation policies",
            ],
            monthly_cost_range=(0.00, 1.00),
            cost_drivers=[
                "SNS email: Free for first 1,000, then $2/100,000",
                "Typical: $0-1/month (< 1,000 emails)",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
            implementation_guidance="""
# SNS Email Notifications

resource "aws_sns_topic" "alerts" {
  name = "cloudwatch-alerts"

  tags = {
    Purpose = "CloudWatchAlarms"
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "ops-team@company.com"
}

# Filter Alarms by Severity
resource "aws_sns_topic" "critical_alerts" {
  name = "cloudwatch-critical-alerts"
}

resource "aws_sns_topic" "warning_alerts" {
  name = "cloudwatch-warning-alerts"
}

# Best Practices:
# - Separate SNS topics by severity (critical vs warning)
# - Use distribution lists, not individual emails
# - Include alarm details in subject line
# - Set up email filters to avoid missing critical alerts
# - Consider SNS → Lambda → formatted email for better UX
""",
            validation_checklist=[
                "SNS topic created and subscriptions confirmed",
                "Email addresses verified (AWS requires confirmation)",
                "Separate topics for critical vs non-critical alarms",
                "Email subject line includes severity and resource",
                "Distribution list used instead of individual emails",
                "Email filters configured to highlight critical alerts",
            ],
        ),
        DecisionOption(
            name="SNS to Slack",
            description="Slack channel notifications via AWS Chatbot or Lambda",
            when_to_use=[
                "Teams using Slack daily",
                "Want centralized alert visibility",
                "Need threaded discussions on alerts",
                "Don't require formal on-call rotation",
            ],
            when_not_to_use=[
                "Production systems requiring guaranteed delivery",
                "Need mobile push for off-hours",
                "Require acknowledgment tracking",
            ],
            pros=[
                "Immediate visibility to whole team",
                "Can discuss alerts in threads",
                "Better formatting than email",
                "Integrates with existing workflow",
                "Can use buttons for common actions",
            ],
            cons=[
                "Slack can be noisy",
                "Not suitable for paging on-call",
                "Requires AWS Chatbot or custom Lambda",
                "Slack outages affect alerting",
            ],
            monthly_cost_range=(0.00, 5.00),
            cost_drivers=[
                "AWS Chatbot: Free",
                "SNS notifications: Free (first 1M)",
                "Lambda (if custom): $0-5/month",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
            implementation_guidance="""
# Slack Integration via AWS Chatbot

resource "aws_chatbot_slack_channel_configuration" "ops_alerts" {
  configuration_name = "ops-alerts"
  slack_channel_id   = "C01234567"  # Your Slack channel ID
  slack_team_id      = "T01234567"  # Your Slack workspace ID

  iam_role_arn = aws_iam_role.chatbot.arn

  sns_topic_arns = [
    aws_sns_topic.alerts.arn
  ]

  guardrail_policy_arns = [
    "arn:aws:iam::aws:policy/ReadOnlyAccess"
  ]
}

# Slack Channel Strategy:
# - #ops-critical: P0/P1 alarms only
# - #ops-warnings: P2/P3 alarms
# - #ops-info: Low-priority notifications
# - Use @channel sparingly (critical only)
""",
            validation_checklist=[
                "AWS Chatbot configured with correct Slack channel",
                "Slack app installed in workspace with proper permissions",
                "Test message sent successfully",
                "Separate channels for different severity levels",
                "Team notifications configured appropriately (@channel for critical)",
                "Runbook links included in Slack messages",
            ],
        ),
        DecisionOption(
            name="PagerDuty Integration (Recommended for Production)",
            description="Full-featured incident management with on-call scheduling and escalation",
            when_to_use=[
                "Production systems with SLAs",
                "On-call rotation required",
                "Need mobile push notifications",
                "Require acknowledgment and escalation",
                "24/7 operations",
            ],
            when_not_to_use=[
                "Development/staging environments",
                "No on-call requirement",
                "Budget constraints (PagerDuty not free)",
            ],
            pros=[
                "Guaranteed delivery",
                "Mobile push notifications",
                "On-call scheduling",
                "Escalation policies",
                "Acknowledgment tracking",
                "Incident analytics",
                "Phone call escalation",
            ],
            cons=[
                "Additional cost (PagerDuty pricing)",
                "More complex setup",
                "Requires PagerDuty account",
            ],
            monthly_cost_range=(21.00, 100.00),
            cost_drivers=[
                "PagerDuty: $21-49/user/month (Professional/Business)",
                "AWS integration: Free",
                "Typical 5-person on-call: $105-245/month",
            ],
            soc2_controls=["CC7.2", "CC7.3"],
            implementation_complexity="medium",
            operational_overhead="low",
            implementation_guidance="""
# PagerDuty Integration via SNS

# 1. Create PagerDuty service and get integration URL
# 2. Create SNS topic that sends to PagerDuty

resource "aws_sns_topic" "pagerduty" {
  name = "cloudwatch-to-pagerduty"
}

resource "aws_sns_topic_subscription" "pagerduty" {
  topic_arn              = aws_sns_topic.pagerduty.arn
  protocol               = "https"
  endpoint               = "https://events.pagerduty.com/integration/\${var.pagerduty_integration_key}/enqueue"
  endpoint_auto_confirms = true
}

# Severity-Based Routing
resource "aws_sns_topic" "critical_pagerduty" {
  name = "critical-to-pagerduty"
  # Routes to PagerDuty high-urgency service
}

resource "aws_sns_topic" "warning_slack" {
  name = "warning-to-slack"
  # Routes to Slack, not PagerDuty (avoid alert fatigue)
}

# PagerDuty Best Practices:
# - Critical alarms (P0/P1) → PagerDuty high-urgency
# - Warning alarms (P2/P3) → PagerDuty low-urgency or Slack
# - Info alarms → Slack only
# - Set up escalation policies (primary → backup → manager)
# - Configure notification rules (push → SMS → phone after delays)
# - Use maintenance windows during deployments
# - Track MTTA (mean time to acknowledge) and MTTR
""",
            validation_checklist=[
                "PagerDuty service created with AWS CloudWatch integration",
                "SNS topic configured with PagerDuty integration URL",
                "Test incident created successfully",
                "On-call schedule configured in PagerDuty",
                "Escalation policies defined (primary → secondary → manager)",
                "Notification rules configured (push, SMS, phone)",
                "Critical alarms go to high-urgency, warnings to low-urgency",
                "Maintenance windows documented for planned maintenance",
            ],
        ),
    ],
    estimated_implementation_time="2-3 days",
    recommendation_strategy="Use SNS to Email for development/staging, SNS to Slack for team visibility, and PagerDuty for production on-call. Combine strategies: Critical alarms → PagerDuty, Warnings → Slack, Info → Email.",
)


# =============================================================================
# HELPER FUNCTION TO GET ALL CLOUDWATCH PATTERNS
# =============================================================================

def get_cloudwatch_patterns() -> dict[str, ArchitectureDecision]:
    """Get all CloudWatch alerting patterns for CARL."""
    return {
        "cloudwatch_alarms": CLOUDWATCH_ALARMS_PATTERNS,
        "notification_strategies": NOTIFICATION_STRATEGIES_PATTERNS,
    }
