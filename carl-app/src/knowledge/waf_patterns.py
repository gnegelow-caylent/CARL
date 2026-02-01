"""
AWS WAF (Web Application Firewall) Patterns for CARL Foundation Builder.

Comprehensive patterns for AWS WAF rule configuration, managed rule groups,
and protection strategies for web applications and APIs.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# AWS WAF DEPLOYMENT PATTERNS
# =============================================================================

WAF_DEPLOYMENT_PATTERNS = ArchitectureDecision(
    question="How should AWS WAF be deployed and configured?",
    options=[
        DecisionOption(
            name="WAF with Managed Rule Groups Only",
            description="Use AWS Managed Rules without custom rules",
            when_to_use=[
                "Getting started with WAF",
                "Standard web application security needed",
                "Limited security engineering resources",
                "Need quick OWASP protection",
            ],
            when_not_to_use=[
                "Custom application-specific threats",
                "Need fine-tuned rate limiting",
                "Require geo-blocking specific countries",
                "Advanced bot management needed",
            ],
            pros=[
                "Quick to implement (minutes)",
                "AWS maintains and updates rules",
                "Covers OWASP Top 10 automatically",
                "No rule tuning required initially",
                "Lower operational overhead",
            ],
            cons=[
                "Can cause false positives",
                "Less control over specific rules",
                "May need to add custom exceptions",
                "Not optimized for your application",
            ],
            monthly_cost_range=(5.00, 50.00),
            cost_drivers=[
                "WAF ACL: $5/month per web ACL",
                "Rules: $1/month per rule (managed rules count as 1)",
                "Requests: $0.60/million requests",
                "Typical small app: $5-15/month (1M requests)",
                "Typical medium app: $15-50/month (10M requests)",
            ],
            soc2_controls=["CC6.6", "CC7.1", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
            implementation_guidance="""
# AWS WAF with Managed Rule Groups

resource "aws_wafv2_web_acl" "main" {
  name  = "app-protection"
  scope = "REGIONAL"  # Use "CLOUDFRONT" for CloudFront distributions

  default_action {
    allow {}  # Allow by default, block on rule matches
  }

  # AWS Managed Rules: Core Rule Set (CRS)
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}  # Use default action from managed rule
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
        
        # Exclude rules that cause false positives (example)
        # excluded_rule {
        #   name = "SizeRestrictions_BODY"
        # }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules: Known Bad Inputs
  rule {
    name     = "AWS-AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesKnownBadInputsMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules: SQL Injection
  rule {
    name     = "AWS-AWSManagedRulesSQLiRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesSQLiRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesSQLiMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "AppProtectionMetric"
    sampled_requests_enabled   = true
  }

  tags = {
    Environment = "production"
    ManagedBy   = "CARL"
  }
}

# Attach to Application Load Balancer
resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = aws_lb.app.arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}

# Common AWS Managed Rule Groups:
# - AWSManagedRulesCommonRuleSet: OWASP Top 10 protection
# - AWSManagedRulesKnownBadInputsRuleSet: Known malicious inputs
# - AWSManagedRulesSQLiRuleSet: SQL injection protection
# - AWSManagedRulesLinuxRuleSet: Linux-specific vulnerabilities
# - AWSManagedRulesUnixRuleSet: Unix-specific vulnerabilities
# - AWSManagedRulesWindowsRuleSet: Windows-specific vulnerabilities
# - AWSManagedRulesPHPRuleSet: PHP-specific vulnerabilities
# - AWSManagedRulesWordPressRuleSet: WordPress protection
# - AWSManagedRulesAmazonIpReputationList: Block known malicious IPs
# - AWSManagedRulesAnonymousIpList: Block anonymizing services (VPN, proxy, Tor)
# - AWSManagedRulesBotControlRuleSet: Bot protection (additional cost)
""",
            validation_checklist=[
                "WAF web ACL created and associated with ALB or CloudFront",
                "Core Rule Set (CRS) enabled for OWASP protection",
                "Known Bad Inputs rule set enabled",
                "SQL injection rule set enabled if using database",
                "CloudWatch metrics enabled for monitoring",
                "Sampled requests enabled for debugging",
                "Test WAF in count mode first (don't block immediately)",
                "Review sampled requests for false positives",
            ],
        ),
        DecisionOption(
            name="WAF with Custom Rate Limiting & Geo-Blocking",
            description="Managed rules plus custom rate limiting and geographic restrictions",
            when_to_use=[
                "Production applications with known traffic patterns",
                "Need DDoS protection",
                "Want to block specific countries/regions",
                "Prevent brute force attacks",
            ],
            when_not_to_use=[
                "Global user base (geo-blocking would hurt legitimate users)",
                "Unpredictable traffic patterns",
                "Don't know appropriate rate limits",
            ],
            pros=[
                "Protects against DDoS/brute force",
                "Reduces malicious traffic from specific regions",
                "Lower request costs (blocked early)",
                "Application-specific protection",
            ],
            cons=[
                "Can block legitimate users if misconfigured",
                "Requires understanding of traffic patterns",
                "More complex to maintain",
                "Rate limits need periodic review",
            ],
            monthly_cost_range=(10.00, 100.00),
            cost_drivers=[
                "WAF ACL: $5/month",
                "Rules: $1/month per rule (3-5 custom rules = $3-5)",
                "Requests: $0.60/million (reduced by blocking)",
                "Rate-based rules: Track request counts (small cost)",
                "Typical: $10-100/month depending on traffic",
            ],
            soc2_controls=["CC6.6", "CC7.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
            implementation_guidance="""
# WAF with Rate Limiting and Geo-Blocking

resource "aws_wafv2_web_acl" "advanced" {
  name  = "advanced-app-protection"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  # Rate-based rule: Block IPs with >2000 requests in 5 minutes
  rule {
    name     = "RateLimitRule"
    priority = 0  # Higher priority = evaluated first

    action {
      block {
        custom_response {
          response_code = 429  # Too Many Requests
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"

        # Optional: Apply rate limit only to specific paths
        # scope_down_statement {
        #   byte_match_statement {
        #     field_to_match {
        #       uri_path {}
        #     }
        #     positional_constraint = "STARTS_WITH"
        #     search_string         = "/api/login"
        #     text_transformation {
        #       priority = 0
        #       type     = "LOWERCASE"
        #     }
        #   }
        # }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitMetric"
      sampled_requests_enabled   = true
    }
  }

  # Geo-blocking rule: Block traffic from specific countries
  rule {
    name     = "GeoBlockRule"
    priority = 1

    action {
      block {}
    }

    statement {
      geo_match_statement {
        country_codes = ["CN", "RU", "KP"]  # Example: Block China, Russia, North Korea
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "GeoBlockMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules (same as previous example)
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "AdvancedAppProtectionMetric"
    sampled_requests_enabled   = true
  }
}

# CloudWatch Alarm for Rate Limit Triggers
resource "aws_cloudwatch_metric_alarm" "rate_limit_triggered" {
  alarm_name          = "waf-rate-limit-blocking"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "WAF rate limiting is blocking traffic"

  dimensions = {
    Rule      = "RateLimitRule"
    WebACL    = aws_wafv2_web_acl.advanced.name
    Region    = "us-east-1"
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
}

# Rate Limit Guidelines:
# - API endpoints: 100-1000 requests/5min per IP
# - Login endpoints: 5-20 requests/5min per IP (prevent brute force)
# - Public pages: 2000-5000 requests/5min per IP
# - Adjust based on CloudWatch metrics and legitimate traffic patterns
""",
            validation_checklist=[
                "Rate limits configured based on baseline traffic analysis",
                "Tested rate limits don't block legitimate users",
                "Geo-blocking countries verified (check your user base first!)",
                "CloudWatch alarms created for rate limit triggers",
                "Custom response codes configured (429 for rate limits)",
                "Sampled requests reviewed for false positives",
                "Exception process documented for legitimate blocked traffic",
            ],
        ),
        DecisionOption(
            name="Advanced WAF with Bot Management & IP Reputation",
            description="Comprehensive WAF with bot protection, IP reputation lists, and custom rules",
            when_to_use=[
                "High-value applications (e-commerce, banking)",
                "Targeted by sophisticated bots",
                "Need advanced threat intelligence",
                "Scraping/credential stuffing concerns",
            ],
            when_not_to_use=[
                "Budget-constrained (<$100/month for WAF)",
                "Low-traffic applications",
                "Simple brute force protection sufficient",
            ],
            pros=[
                "Best-in-class bot protection",
                "Blocks known malicious IPs automatically",
                "Protects against credential stuffing",
                "Advanced threat intelligence",
                "Reduces scraping and fraud",
            ],
            cons=[
                "Significantly higher cost (Bot Control: $10/month + $1/million requests)",
                "Complex configuration",
                "May require tuning for specific bots",
                "Can impact performance (additional inspection)",
            ],
            monthly_cost_range=(50.00, 500.00),
            cost_drivers=[
                "WAF ACL: $5/month",
                "Rules: $1/month per rule (~10 rules = $10)",
                "Bot Control Managed Rule: $10/month + $1/million bot-checked requests",
                "IP Reputation Lists: $1/month per list",
                "Requests: $0.60/million requests",
                "Typical medium traffic: $50-150/month",
                "Typical high traffic: $150-500/month",
            ],
            soc2_controls=["CC6.6", "CC7.1", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="medium",
            implementation_guidance="""
# Advanced WAF with Bot Management

resource "aws_wafv2_web_acl" "enterprise" {
  name  = "enterprise-app-protection"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  # AWS Managed Rules: Bot Control (Advanced)
  rule {
    name     = "AWS-AWSManagedRulesBotControlRuleSet"
    priority = 0

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesBotControlRuleSet"

        # Bot Control configuration
        managed_rule_group_configs {
          aws_managed_rules_bot_control_rule_set {
            inspection_level = "TARGETED"  # Options: COMMON or TARGETED
          }
        }

        # Exclude specific bot rules if needed
        # excluded_rule {
        #   name = "CategoryHttpLibrary"  # Allow legitimate HTTP libraries
        # }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "BotControlMetric"
      sampled_requests_enabled   = true
    }
  }

  # IP Reputation List: Block known malicious IPs
  rule {
    name     = "AWS-AWSManagedRulesAmazonIpReputationList"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesAmazonIpReputationList"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "IpReputationMetric"
      sampled_requests_enabled   = true
    }
  }

  # Anonymous IP List: Block Tor, VPNs, proxies
  rule {
    name     = "AWS-AWSManagedRulesAnonymousIpList"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesAnonymousIpList"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AnonymousIpMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rate limiting on login endpoint (prevent credential stuffing)
  rule {
    name     = "LoginRateLimitRule"
    priority = 3

    action {
      block {
        custom_response {
          response_code = 429
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = 10  # Max 10 login attempts per 5 minutes
        aggregate_key_type = "IP"

        scope_down_statement {
          byte_match_statement {
            field_to_match {
              uri_path {}
            }
            positional_constraint = "EXACTLY"
            search_string         = "/api/login"
            text_transformation {
              priority = 0
              type     = "LOWERCASE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "LoginRateLimitMetric"
      sampled_requests_enabled   = true
    }
  }

  # Core rule set (OWASP protection)
  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 4

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "EnterpriseProtectionMetric"
    sampled_requests_enabled   = true
  }
}

# Bot Control Inspection Levels:
# - COMMON: Basic bot detection (lower cost, less accuracy)
# - TARGETED: Advanced bot detection (higher cost, better accuracy)

# Use Cases:
# - E-commerce: Prevent scraping, inventory hoarding, fraud
# - APIs: Prevent unauthorized automation, rate limit abuse
# - Login pages: Prevent credential stuffing, brute force
# - Content sites: Prevent scraping, hotlinking
""",
            validation_checklist=[
                "Bot Control configured with appropriate inspection level",
                "Tested with known good bots (search engines, monitoring)",
                "Search engine bots whitelisted if needed (Google, Bing)",
                "IP Reputation List enabled for threat intelligence",
                "Anonymous IP blocking evaluated (may block legitimate VPN users)",
                "Login endpoint has aggressive rate limiting",
                "Cost reviewed and approved ($50-500/month range)",
                "CloudWatch dashboard created for WAF metrics",
                "Weekly review process for blocked requests",
            ],
        ),
    ],
    estimated_implementation_time="2-3 days",
    recommendation_strategy="Start with Managed Rule Groups Only for quick OWASP protection. Add Rate Limiting & Geo-Blocking for production applications. Use Advanced Bot Management only for high-value applications targeted by bots. Always test in count mode first!",
)


# =============================================================================
# WAF DEPLOYMENT LOCATIONS PATTERNS
# =============================================================================

WAF_LOCATION_PATTERNS = ArchitectureDecision(
    question="Where should AWS WAF be deployed (ALB vs CloudFront)?",
    options=[
        DecisionOption(
            name="WAF on Application Load Balancer (Regional)",
            description="Deploy WAF directly on ALB in single region",
            when_to_use=[
                "Single-region application",
                "Don't use CloudFront CDN",
                "Direct ALB access required",
                "Regional compliance requirements",
            ],
            when_not_to_use=[
                "Global application with users worldwide",
                "Using CloudFront CDN",
                "Need edge-location protection",
            ],
            pros=[
                "Simpler architecture",
                "Lower latency (no CDN hop)",
                "Easier to debug",
                "Works with any ALB application",
            ],
            cons=[
                "No global DDoS protection",
                "Higher latency for distant users",
                "All traffic hits regional ALB",
                "Limited to regional AWS Shield Standard",
            ],
            monthly_cost_range=(5.00, 50.00),
            cost_drivers=[
                "Same WAF costs as CloudFront",
                "No CloudFront data transfer costs",
                "Typical: $5-50/month",
            ],
            soc2_controls=["CC6.6", "CC7.1"],
            implementation_complexity="low",
            operational_overhead="low",
            implementation_guidance="""
# WAF on ALB

resource "aws_wafv2_web_acl" "alb_protection" {
  name  = "alb-waf"
  scope = "REGIONAL"  # Must be REGIONAL for ALB

  # ... (rule configuration from previous examples)
}

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = aws_lb.app.arn
  web_acl_arn  = aws_wafv2_web_acl.alb_protection.arn
}

# When to Use ALB WAF:
# - Internal applications (not public internet)
# - Single-region deployments
# - No need for CDN caching
# - Direct WebSocket connections (CloudFront complicates WebSockets)
""",
            validation_checklist=[
                "WAF scope set to REGIONAL (not CLOUDFRONT)",
                "WAF associated with correct ALB",
                "Security group still restricts traffic to ALB",
                "CloudWatch metrics enabled",
                "Tested with legitimate traffic",
            ],
        ),
        DecisionOption(
            name="WAF on CloudFront (Global Edge Protection)",
            description="Deploy WAF at CloudFront edge locations worldwide",
            when_to_use=[
                "Global user base",
                "Already using CloudFront CDN",
                "Need edge-location DDoS protection",
                "Want to block attacks before they reach origin",
            ],
            when_not_to_use=[
                "Single-region application",
                "Don't use CloudFront",
                "WebSocket-heavy application (CloudFront adds complexity)",
            ],
            pros=[
                "Global DDoS protection",
                "Blocks attacks at edge (before hitting origin)",
                "Lower origin load",
                "Better global performance (CDN caching)",
                "AWS Shield Advanced available",
            ],
            cons=[
                "More complex architecture",
                "CloudFront data transfer costs",
                "Harder to debug (distributed)",
                "CDN cache considerations",
            ],
            monthly_cost_range=(10.00, 200.00),
            cost_drivers=[
                "WAF: Same costs as ALB WAF",
                "CloudFront: $0.085/GB data transfer (first 10TB)",
                "CloudFront requests: $0.0075/10,000 HTTPS requests",
                "Typical small: $10-30/month",
                "Typical medium: $30-100/month",
                "Typical large: $100-200+/month",
            ],
            soc2_controls=["CC6.6", "CC7.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
            implementation_guidance="""
# WAF on CloudFront

# 1. Create WAF in us-east-1 (required for CloudFront)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

resource "aws_wafv2_web_acl" "cloudfront_protection" {
  provider = aws.us_east_1  # CloudFront WAF must be in us-east-1

  name  = "cloudfront-waf"
  scope = "CLOUDFRONT"  # Must be CLOUDFRONT for CloudFront

  # ... (rule configuration)
}

# 2. Associate with CloudFront distribution
resource "aws_cloudfront_distribution" "app" {
  # ... (CloudFront configuration)

  web_acl_id = aws_wafv2_web_acl.cloudfront_protection.arn

  # Restrict ALB to only accept traffic from CloudFront
  # Use custom header and ALB listener rule
}

# 3. Restrict ALB to CloudFront traffic only
resource "aws_lb_listener_rule" "cloudfront_only" {
  listener_arn = aws_lb_listener.https.arn

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  condition {
    http_header {
      http_header_name = "X-Custom-Secret-Header"
      values           = [random_password.cloudfront_secret.result]
    }
  }
}

# Benefits of CloudFront + WAF:
# - Attacks blocked at 200+ edge locations (not at origin)
# - Origin protected by custom header (CloudFront only)
# - Better performance for global users
# - DDoS protection included (Shield Standard)
""",
            validation_checklist=[
                "WAF created in us-east-1 (CloudFront requirement)",
                "WAF scope set to CLOUDFRONT",
                "CloudFront distribution associated with WAF",
                "ALB restricted to CloudFront traffic only (custom header)",
                "CloudFront cache behaviors configured correctly",
                "SSL certificate in us-east-1 (ACM for CloudFront)",
                "Tested with traffic from multiple regions",
            ],
        ),
    ],
    estimated_implementation_time="1-2 days",
    recommendation_strategy="Use ALB WAF for single-region applications or when not using CloudFront. Use CloudFront WAF for global applications to block attacks at edge and improve performance. If using CloudFront, always put WAF there (not on ALB).",
)


# =============================================================================
# HELPER FUNCTION TO GET ALL WAF PATTERNS
# =============================================================================

def get_waf_patterns() -> dict[str, ArchitectureDecision]:
    """Get all AWS WAF patterns for CARL."""
    return {
        "waf_deployment": WAF_DEPLOYMENT_PATTERNS,
        "waf_location": WAF_LOCATION_PATTERNS,
    }
