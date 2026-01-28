"""
AWS WAF (Web Application Firewall) Patterns for CARL Foundation Builder.

Comprehensive patterns for WAF rule management, managed rule groups,
and web application protection strategies.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# WAF DEPLOYMENT PATTERNS
# =============================================================================

WAF_DEPLOYMENT_PATTERNS = ArchitectureDecision(
    question="Where and how should AWS WAF be deployed?",
    options=[
        DecisionOption(
            name="WAF on ALB (Regional)",
            description="Deploy WAF on Application Load Balancers",
            when_to_use=[
                "ALB-based architecture",
                "Regional applications",
                "Internal and external APIs",
                "Most web applications",
            ],
            when_not_to_use=[
                "Using CloudFront (use CloudFront WAF instead)",
                "No ALB in architecture",
            ],
            pros=[
                "Protects at application layer",
                "Works with internal ALBs",
                "Lower latency than CloudFront",
                "Regional deployment",
            ],
            cons=[
                "Per-region deployment needed",
                "Doesn't protect against DDoS at edge",
                "No geo-blocking at edge",
            ],
            monthly_cost_range=(5.00, 50.00),
            cost_drivers=[
                "Web ACL: $5/mo",
                "Rules: $1/rule/mo",
                "Requests: $0.60/1M requests",
                "10-20 rules typical: $15-25/mo",
            ],
            soc2_controls=["CC6.6", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="WAF on CloudFront (Edge)",
            description="Deploy WAF on CloudFront distributions",
            when_to_use=[
                "Global applications",
                "Using CloudFront CDN",
                "Need edge protection",
                "DDoS protection priority",
            ],
            when_not_to_use=[
                "Regional-only applications",
                "Not using CloudFront",
            ],
            pros=[
                "Edge-level protection",
                "Blocks at closest location",
                "Integrated with Shield",
                "Geo-blocking at edge",
            ],
            cons=[
                "Must use CloudFront",
                "Global deployment (can't be regional)",
                "Slightly different rule options",
            ],
            monthly_cost_range=(10.00, 100.00),
            cost_drivers=[
                "Web ACL: $5/mo",
                "Rules: $1/rule/mo",
                "Requests: $0.60/1M requests",
                "Higher request volume at edge",
            ],
            soc2_controls=["CC6.6", "CC6.8", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="WAF on API Gateway",
            description="Deploy WAF on API Gateway REST APIs",
            when_to_use=[
                "API Gateway REST APIs",
                "Regional APIs",
                "Need API-specific protection",
            ],
            when_not_to_use=[
                "HTTP APIs (not supported)",
                "WebSocket APIs (not supported)",
                "Using ALB for APIs (use ALB WAF)",
            ],
            pros=[
                "Protects API Gateway directly",
                "Good for REST APIs",
                "Regional deployment",
            ],
            cons=[
                "Only REST APIs supported",
                "Per-region deployment",
                "Limited compared to ALB WAF",
            ],
            monthly_cost_range=(5.00, 30.00),
            cost_drivers=[
                "Web ACL: $5/mo",
                "Rules: $1/rule/mo",
                "Requests: $0.60/1M requests",
            ],
            soc2_controls=["CC6.6", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Layered WAF Strategy",
            description="WAF at both CloudFront (edge) and ALB (origin)",
            when_to_use=[
                "High-security applications",
                "Need defense in depth",
                "Using CloudFront + ALB",
                "DDoS + application protection",
            ],
            when_not_to_use=[
                "Cost is primary concern",
                "Simple applications",
                "Single-layer protection sufficient",
            ],
            pros=[
                "Defense in depth",
                "Edge and origin protection",
                "Different rules at each layer",
                "Maximum security",
            ],
            cons=[
                "Double WAF cost",
                "More complex management",
                "Need to coordinate rules",
            ],
            monthly_cost_range=(20.00, 150.00),
            cost_drivers=[
                "2× Web ACLs: $10/mo",
                "2× Rule sets",
                "Requests charged at both layers",
            ],
            soc2_controls=["CC6.6", "CC6.8", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    WAF deployment decision tree:

    1. Are you using CloudFront?
       YES, and need edge protection → CloudFront WAF
       YES, but also need origin protection → Layered WAF
       NO → ALB or API Gateway WAF

    2. What's your architecture?
       ALB-based → WAF on ALB
       API Gateway REST → WAF on API Gateway
       CloudFront → WAF on CloudFront

    3. What's your security requirement?
       Standard → Single-layer WAF
       High (PCI-DSS, financial) → Layered WAF

    WAF deployment best practices:
    - Start with managed rule groups
    - Enable logging (S3 or Kinesis Firehose)
    - Use rate limiting for APIs
    - Test in COUNT mode first
    - Monitor blocked requests
    - Regular rule review and tuning

    WAF logging destinations:
    - S3 bucket (cheapest, batch analysis)
    - Kinesis Data Firehose (real-time)
    - CloudWatch Logs (integration with insights)

    Cost optimization:
    - Use managed rule groups (shared cost)
    - Combine rules where possible
    - Use IP sets for bulk IPs
    - Use string match sets for patterns
    - Monitor request charges
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.6: WAF provides boundary protection
    - CC6.8: Threat detection and mitigation
    - CC7.2: Security monitoring (WAF logs)

    WAF demonstrates:
    - Protection against OWASP Top 10
    - Defense against common attacks
    - Logging of blocked requests
    - Proactive security posture

    Auditors want to see:
    - WAF rules documented
    - Evidence of protection (logs)
    - Regular rule updates
    - Tuning process
    """,
    common_mistakes=[
        "Enabling BLOCK mode without testing",
        "Not enabling logging",
        "Using only custom rules (skip managed rules)",
        "Not monitoring blocked requests",
        "No rate limiting rules",
    ],
)


# =============================================================================
# WAF RULE STRATEGY PATTERNS
# =============================================================================

WAF_RULE_STRATEGY_PATTERNS = ArchitectureDecision(
    question="What WAF rule strategy should be implemented?",
    options=[
        DecisionOption(
            name="Managed Rules Only",
            description="Use AWS and marketplace managed rule groups",
            when_to_use=[
                "Getting started with WAF",
                "Standard web applications",
                "Limited security expertise",
                "Most organizations",
            ],
            when_not_to_use=[
                "Very custom applications",
                "Need specific custom rules",
            ],
            pros=[
                "AWS maintains rules",
                "Automatic updates",
                "OWASP coverage",
                "Low maintenance",
            ],
            cons=[
                "Less customization",
                "May block legitimate traffic",
                "Need tuning",
            ],
            monthly_cost_range=(5.00, 20.00),
            cost_drivers=[
                "Web ACL: $5/mo",
                "Core Rule Set: $10/mo",
                "Additional rule groups: $1-5/mo each",
            ],
            soc2_controls=["CC6.8", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="Managed + Custom Rules",
            description="Managed rules plus application-specific custom rules",
            when_to_use=[
                "Production applications",
                "Need application-specific protection",
                "Have security expertise",
                "Custom attack patterns",
            ],
            when_not_to_use=[
                "No resources for rule management",
                "Simple applications",
            ],
            pros=[
                "Best of both worlds",
                "Application-specific protection",
                "Flexible",
                "Covers custom threats",
            ],
            cons=[
                "More rules to manage",
                "Requires expertise",
                "Testing needed",
            ],
            monthly_cost_range=(10.00, 50.00),
            cost_drivers=[
                "Web ACL: $5/mo",
                "Managed rules: $10-15/mo",
                "Custom rules: $1/rule/mo",
                "10-30 custom rules typical",
            ],
            soc2_controls=["CC6.8", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Advanced Rule Strategy",
            description="Comprehensive rules with rate limiting, geo-blocking, IP reputation",
            when_to_use=[
                "High-value applications",
                "Public-facing APIs",
                "Need sophisticated protection",
                "Regulatory requirements (PCI-DSS)",
            ],
            when_not_to_use=[
                "Internal applications only",
                "Simple use cases",
            ],
            pros=[
                "Comprehensive protection",
                "Rate limiting per client",
                "Geo-blocking",
                "IP reputation filtering",
                "Bot detection",
            ],
            cons=[
                "Complex to configure",
                "Higher cost",
                "Requires ongoing tuning",
            ],
            monthly_cost_range=(20.00, 100.00),
            cost_drivers=[
                "Web ACL: $5/mo",
                "Multiple managed rule groups: $15-30/mo",
                "Custom rules: $10-30/mo",
                "Bot Control (optional): $10/mo + $1/1M requests",
            ],
            soc2_controls=["CC6.6", "CC6.8", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    Recommended managed rule groups:

    **Core Rule Set (Must have):**
    - AWS Managed Rules Core Rule Set (CRS)
    - Protects against OWASP Top 10
    - Cost: ~$10/mo
    - Coverage: SQLi, XSS, LFI, RFI, RCE

    **Additional managed rules:**
    - Known Bad Inputs ($5/mo)
    - SQL Database ($5/mo) - if using SQL
    - Linux Operating System ($5/mo) - if Linux backends
    - PHP Application ($5/mo) - if PHP
    - WordPress Application ($5/mo) - if WordPress
    - Amazon IP Reputation List ($5/mo)

    **Custom rule examples:**

    1. **Rate Limiting (API protection):**
    ```
    Rule: RateLimit-API
    Type: RateBasedRule
    Limit: 2000 requests per 5 minutes per IP
    Action: BLOCK
    Scope: Specific URI path (/api/*)
    ```

    2. **Geo-blocking:**
    ```
    Rule: BlockCountries
    Type: GeoMatchRule
    Countries: [High-risk countries]
    Action: BLOCK
    Exception: Known partner IPs
    ```

    3. **Auth endpoint protection:**
    ```
    Rule: RateLimit-Login
    Type: RateBasedRule
    Limit: 5 requests per 5 minutes per IP
    Path: /login, /api/auth/*
    Action: BLOCK
    ```

    4. **Block known bad user agents:**
    ```
    Rule: BlockBadBots
    Type: StringMatchRule
    Header: User-Agent
    Patterns: [scanner patterns]
    Action: BLOCK
    ```

    5. **Require specific headers:**
    ```
    Rule: RequireAPIKey
    Type: ByteMatchRule
    Header: X-API-Key
    Condition: NOT present
    Action: BLOCK
    Scope: /api/*
    ```

    Rule priority recommendations:
    1. Rate limiting rules (PRIORITY 1-10)
    2. Geo-blocking (PRIORITY 11-20)
    3. Known bad actors (PRIORITY 21-30)
    4. Managed rule groups (PRIORITY 100-200)
    5. Custom application rules (PRIORITY 300+)

    Testing strategy:
    1. Deploy in COUNT mode
    2. Monitor for false positives (7-14 days)
    3. Add exceptions for legitimate traffic
    4. Switch to BLOCK mode
    5. Monitor continuously
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC6.8: WAF rules mitigate threats
    - CC7.2: Rule logging provides monitoring

    Rule strategy demonstrates:
    - Layered security (defense in depth)
    - Protection against known attacks
    - Proactive threat mitigation
    - Regular rule updates

    Auditors review:
    - Rule documentation
    - Rule rationale
    - Blocked request analysis
    - False positive handling process
    """,
    common_mistakes=[
        "Enabling too many managed rules (false positives)",
        "No rate limiting rules",
        "Not testing in COUNT mode first",
        "Forgetting to update custom rules",
        "No process for reviewing blocked requests",
    ],
)


# =============================================================================
# WAF LOGGING AND MONITORING PATTERNS
# =============================================================================

WAF_LOGGING_PATTERNS = ArchitectureDecision(
    question="How should WAF logging and monitoring be configured?",
    options=[
        DecisionOption(
            name="S3 Logging Only",
            description="Log all WAF actions to S3 bucket",
            when_to_use=[
                "Compliance requires log retention",
                "Batch analysis sufficient",
                "Cost optimization priority",
            ],
            when_not_to_use=[
                "Need real-time analysis",
                "Active threat response",
            ],
            pros=[
                "Cheapest option",
                "Long-term retention",
                "Compliance-friendly",
                "Athena analysis",
            ],
            cons=[
                "Not real-time",
                "Manual analysis needed",
                "Delayed threat response",
            ],
            monthly_cost_range=(5.00, 20.00),
            cost_drivers=[
                "S3 storage: $0.023/GB",
                "Typical: 1-5GB/mo",
                "Athena queries: $5/TB",
            ],
            soc2_controls=["CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="CloudWatch Logs + Insights",
            description="Stream WAF logs to CloudWatch for analysis",
            when_to_use=[
                "Need real-time visibility",
                "CloudWatch-centric monitoring",
                "Want integrated dashboards",
            ],
            when_not_to_use=[
                "High request volume (expensive)",
                "Long-term retention needed",
            ],
            pros=[
                "Real-time analysis",
                "CloudWatch Insights queries",
                "Integrated dashboards",
                "Alarms on patterns",
            ],
            cons=[
                "Higher cost",
                "Retention limits (default 30 days)",
                "Can be expensive at scale",
            ],
            monthly_cost_range=(10.00, 100.00),
            cost_drivers=[
                "Data ingestion: $0.50/GB",
                "Storage: $0.03/GB",
                "Queries: $0.005/GB scanned",
            ],
            soc2_controls=["CC4.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="Kinesis + SIEM Integration",
            description="Stream via Kinesis Firehose to SIEM or analytics",
            when_to_use=[
                "SIEM integration (Splunk, Datadog, etc.)",
                "Real-time threat detection",
                "Security operations center (SOC)",
                "Enterprise environments",
            ],
            when_not_to_use=[
                "No SIEM",
                "Simple logging needs",
                "Budget constraints",
            ],
            pros=[
                "Real-time streaming",
                "SIEM integration",
                "Advanced analytics",
                "Automated response",
            ],
            cons=[
                "Most expensive",
                "Complex setup",
                "SIEM costs additional",
            ],
            monthly_cost_range=(20.00, 200.00),
            cost_drivers=[
                "Kinesis Firehose: $0.029/GB",
                "SIEM ingestion costs",
                "Lambda transformations",
            ],
            soc2_controls=["CC4.1", "CC7.2", "CC7.3"],
            implementation_complexity="high",
            operational_overhead="high",
        },
    ],
    recommendation_logic="""
    WAF logging strategy:

    **For most organizations:**
    - Primary: S3 for long-term storage
    - Secondary: CloudWatch for recent analysis (7-30 days)
    - Use Kinesis Firehose to deliver to both

    **Setup:**
    ```
    WAF → Kinesis Firehose → S3 (primary)
                           → CloudWatch Logs (secondary)
    ```

    **Key metrics to monitor:**
    - Blocked requests by rule
    - Blocked requests by country
    - Blocked requests by IP
    - Top blocked URIs
    - Rate limit violations
    - False positive rate

    **CloudWatch Insights queries:**

    1. Top blocked IPs:
    ```
    fields httpRequest.clientIp, @timestamp
    | filter action = "BLOCK"
    | stats count() by httpRequest.clientIp
    | sort count desc
    | limit 20
    ```

    2. Blocked requests by rule:
    ```
    fields terminatingRuleId, @timestamp
    | filter action = "BLOCK"
    | stats count() by terminatingRuleId
    ```

    3. Geographic distribution of blocks:
    ```
    fields httpRequest.country, @timestamp
    | filter action = "BLOCK"
    | stats count() by httpRequest.country
    | sort count desc
    ```

    **Alarms to create:**
    - Spike in blocked requests (unusual activity)
    - New countries appearing (geo-anomaly)
    - Rate limit rule triggering (potential attack)
    - Specific rule blocking frequently (tune or investigate)

    **Retention recommendations:**
    - S3: 1-7 years (compliance)
    - CloudWatch: 30-90 days (recent analysis)
    - Kinesis: Real-time only
    """,
    soc2_relevance="""
    SOC 2 controls:
    - CC7.2: WAF logs provide security monitoring
    - CC4.1: Logs analyzed for anomalies
    - CC7.3: Logs support incident response

    WAF logging demonstrates:
    - All blocked requests logged
    - Retention for audit purposes
    - Analysis of attack patterns
    - Evidence of protection

    Auditors expect:
    - WAF logging enabled
    - Logs retained appropriately
    - Evidence of log review
    - Response to anomalies
    """,
    common_mistakes=[
        "Not enabling logging at all",
        "Logs not accessible (wrong S3 permissions)",
        "No analysis of logs (collect but never review)",
        "No alarms on log patterns",
        "Insufficient retention",
    ],
)


def get_waf_patterns() -> dict:
    """Get all AWS WAF patterns."""
    return {
        "waf_deployment": WAF_DEPLOYMENT_PATTERNS,
        "waf_rules": WAF_RULE_STRATEGY_PATTERNS,
        "waf_logging": WAF_LOGGING_PATTERNS,
    }
