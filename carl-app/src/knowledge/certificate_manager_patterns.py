"""
AWS Certificate Manager (ACM) Patterns for CARL Foundation Builder.

Comprehensive patterns for SSL/TLS certificate management, lifecycle automation,
and CloudFront/ALB certificate deployment strategies.
"""

from dataclasses import dataclass, field
from typing import Any

from .architecture_patterns import ArchitectureDecision, DecisionOption


# =============================================================================
# ACM CERTIFICATE PATTERNS
# =============================================================================

CERTIFICATE_PATTERNS = ArchitectureDecision(
    question="How should SSL/TLS certificates be managed with AWS Certificate Manager?",
    options=[
        DecisionOption(
            name="Single Domain Certificate",
            description="One certificate per domain (e.g., api.company.com)",
            when_to_use=[
                "Single subdomain application",
                "Simple deployment",
                "Separate teams managing different subdomains",
                "Security isolation between services",
            ],
            when_not_to_use=[
                "Multiple subdomains for same application",
                "Many microservices on subdomains",
                "Wildcard certificate would simplify management",
            ],
            pros=[
                "Simplest to manage",
                "Clear ownership per certificate",
                "Least privilege (cert only valid for one domain)",
                "Easy to revoke single service",
            ],
            cons=[
                "More certificates to manage",
                "Certificate limit per account (2,048)",
                "More renewals to track",
                "Repetitive configuration",
            ],
            monthly_cost_range=(0.00, 0.00),
            cost_drivers=[
                "ACM certificates: FREE",
                "No charge for public certificates",
                "Auto-renewal is free",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
            implementation_guidance="""
# Single Domain Certificate

resource "aws_acm_certificate" "api" {
  domain_name       = "api.company.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "api-cert"
    Environment = "production"
    ManagedBy   = "CARL"
  }
}

# DNS validation (automatic with Route 53)
resource "aws_route53_record" "api_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.api_cert_validation : record.fqdn]
}

# Use with ALB
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"  # TLS 1.3 only
  certificate_arn   = aws_acm_certificate.api.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Best Practices:
# - Always use DNS validation (not email)
# - Use create_before_destroy to avoid downtime
# - Choose modern SSL policy (TLS 1.3 preferred)
# - Set up CloudWatch alarm for expiration (ACM auto-renews, but monitor anyway)
""",
            validation_checklist=[
                "Certificate uses DNS validation (not email)",
                "Route 53 validation records created automatically",
                "Certificate status is ISSUED before using",
                "SSL policy is modern (TLS 1.3 or TLS 1.2 minimum)",
                "CloudWatch alarm for certificate expiration (just in case)",
                "create_before_destroy lifecycle rule set",
                "Certificate tags include ownership and environment",
            ],
        ),
        DecisionOption(
            name="Wildcard Certificate (Recommended for Most)",
            description="One certificate for all subdomains (*.company.com)",
            when_to_use=[
                "Multiple subdomains for same application",
                "Microservices architecture",
                "Want simplified certificate management",
                "Frequent new subdomain additions",
            ],
            when_not_to_use=[
                "Security requirement to isolate subdomains",
                "Different teams own different subdomains",
                "Need granular revocation",
            ],
            pros=[
                "Single certificate for all subdomains",
                "Easy to add new subdomains",
                "Simplified management",
                "One renewal to track",
                "Works with ALB and CloudFront",
            ],
            cons=[
                "If compromised, affects all subdomains",
                "Can't revoke for single subdomain",
                "Doesn't cover root domain (company.com)",
                "Less granular access control",
            ],
            monthly_cost_range=(0.00, 0.00),
            cost_drivers=[
                "ACM certificates: FREE",
                "No charge regardless of subdomains covered",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="low",
            operational_overhead="low",
            implementation_guidance="""
# Wildcard Certificate

resource "aws_acm_certificate" "wildcard" {
  domain_name       = "*.company.com"
  validation_method = "DNS"

  # Optionally add root domain as Subject Alternative Name (SAN)
  subject_alternative_names = [
    "company.com"  # Covers both root and wildcard
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name        = "wildcard-cert"
    Environment = "production"
    Scope       = "all-subdomains"
  }
}

# DNS validation
resource "aws_route53_record" "wildcard_validation" {
  for_each = {
    for dvo in aws_acm_certificate.wildcard.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "wildcard" {
  certificate_arn         = aws_acm_certificate.wildcard.arn
  validation_record_fqdns = [for record in aws_route53_record.wildcard_validation : record.fqdn]
}

# Use with ALB (multiple subdomains)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.wildcard.arn

  # All subdomains use same certificate
  # Route based on host header in listener rules
}

# Covered domains:
# *.company.com covers: api.company.com, app.company.com, admin.company.com, etc.
# Does NOT cover: company.com (add as SAN if needed)
# Does NOT cover: sub.api.company.com (multi-level wildcards not supported)
""",
            validation_checklist=[
                "Wildcard domain specified correctly (*.domain.com)",
                "Root domain added as SAN if needed (company.com)",
                "DNS validation record created",
                "Tested with multiple subdomains",
                "CloudWatch alarm for expiration monitoring",
                "Document all services using this certificate",
                "Security review approved wildcard usage",
            ],
        ),
        DecisionOption(
            name="Multi-Domain Certificate (SAN)",
            description="One certificate for multiple specific domains using Subject Alternative Names",
            when_to_use=[
                "Fixed set of specific domains",
                "Mix of root domains and subdomains",
                "Want single certificate management",
                "Domains don't follow wildcard pattern",
            ],
            when_not_to_use=[
                "Domains follow simple wildcard pattern",
                "Frequently adding new domains",
                "More than 10 domains (gets unwieldy)",
            ],
            pros=[
                "One certificate for multiple specific domains",
                "Covers root and subdomains",
                "More secure than wildcard (explicit domains)",
                "Easier than managing many single certs",
            ],
            cons=[
                "Must reissue to add new domains",
                "More complex validation",
                "Can hit SAN limit (100 domains per cert)",
                "Harder to audit what's covered",
            ],
            monthly_cost_range=(0.00, 0.00),
            cost_drivers=[
                "ACM certificates: FREE",
                "No additional cost for SANs",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="medium",
            implementation_guidance="""
# Multi-Domain Certificate

resource "aws_acm_certificate" "multi_domain" {
  domain_name       = "company.com"  # Primary domain
  validation_method = "DNS"

  subject_alternative_names = [
    "www.company.com",
    "api.company.com",
    "app.company.com",
    "admin.company.com",
    "*.staging.company.com",  # Can mix wildcards
    "otherbrand.com",         # Can even have different root domains
    "www.otherbrand.com"
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name      = "multi-domain-cert"
    Domains   = "company.com,otherbrand.com"  # Track covered domains
  }
}

# DNS validation for all domains
resource "aws_route53_record" "multi_domain_validation" {
  for_each = {
    for dvo in aws_acm_certificate.multi_domain.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id  # Must handle multiple zones if different root domains
}

# Use Cases:
# - Single certificate for main site + API + admin portal
# - Covers both company.com and www.company.com
# - Can include staging wildcard for all staging subdomains
# - Useful when rebranding (cover old and new domains during transition)
""",
            validation_checklist=[
                "All required domains listed in SANs",
                "DNS validation completed for ALL domains",
                "Multiple Route 53 zones handled if needed",
                "Tested all covered domains resolve correctly",
                "Document why multi-domain cert chosen over wildcard",
                "Plan for reissuance when adding domains",
                "SAN count under 100 limit",
            ],
        ),
    ],
    estimated_implementation_time="1 day",
    recommendation_strategy="Use Wildcard Certificate for most applications with multiple subdomains. Use Single Domain for security-isolated services. Use Multi-Domain (SAN) for specific fixed set of domains that don't follow wildcard pattern.",
)


# =============================================================================
# ACM REGIONAL VS GLOBAL PATTERNS
# =============================================================================

CERTIFICATE_LOCATION_PATTERNS = ArchitectureDecision(
    question="Where should ACM certificates be provisioned (Regional vs Global)?",
    options=[
        DecisionOption(
            name="Regional Certificates (ALB, API Gateway, NLB)",
            description="Certificates in same region as load balancer",
            when_to_use=[
                "Using Application Load Balancer",
                "Using Network Load Balancer",
                "Using Regional API Gateway",
                "Not using CloudFront",
            ],
            when_not_to_use=[
                "Using CloudFront distribution",
                "Need global edge locations",
            ],
            pros=[
                "Simple - certificate in same region as resource",
                "Works with ALB, NLB, API Gateway",
                "Can use different certs per region",
            ],
            cons=[
                "Must provision cert in each region",
                "Can't use with CloudFront",
                "No edge location termination",
            ],
            monthly_cost_range=(0.00, 0.00),
            cost_drivers=[
                "ACM certificates: FREE",
                "Regional certificates are free",
            ],
            soc2_controls=["CC6.6"],
            implementation_complexity="low",
            operational_overhead="low",
            implementation_guidance="""
# Regional Certificate for ALB

resource "aws_acm_certificate" "alb_cert" {
  domain_name       = "api.company.com"
  validation_method = "DNS"

  # Certificate is in same region as ALB (provider default region)

  tags = {
    Name   = "alb-cert"
    Region = "us-east-1"
  }
}

# Use with ALB in same region
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = "443"
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate.alb_cert.arn  # Same region

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Multi-Region Pattern:
# If deploying to multiple regions, create certificate in EACH region

provider "aws" {
  alias  = "us_west_2"
  region = "us-west-2"
}

resource "aws_acm_certificate" "alb_cert_west" {
  provider = aws.us_west_2

  domain_name       = "api.company.com"
  validation_method = "DNS"

  # Same domain, different region
}
""",
            validation_checklist=[
                "Certificate in same region as ALB/NLB/API Gateway",
                "If multi-region, certificate created in each region",
                "Route 53 health checks configured for multi-region",
                "DNS validation works across all regions",
            ],
        ),
        DecisionOption(
            name="Global Certificate (CloudFront) in us-east-1",
            description="Certificate in us-east-1 for CloudFront distributions",
            when_to_use=[
                "Using CloudFront CDN",
                "Need edge location SSL termination",
                "Global user base",
                "Static site or API with CloudFront",
            ],
            when_not_to_use=[
                "Not using CloudFront",
                "Only need regional ALB",
            ],
            pros=[
                "Works with CloudFront globally",
                "SSL termination at edge locations",
                "Lower latency for global users",
                "Only need one certificate (not per-region)",
            ],
            cons=[
                "MUST be in us-east-1 (CloudFront requirement)",
                "Can't use regional certificates with CloudFront",
                "Must remember us-east-1 requirement",
            ],
            monthly_cost_range=(0.00, 0.00),
            cost_drivers=[
                "ACM certificates: FREE",
                "CloudFront data transfer: $0.085/GB (first 10TB)",
            ],
            soc2_controls=["CC6.6", "CC6.7"],
            implementation_complexity="medium",
            operational_overhead="low",
            implementation_guidance="""
# Global Certificate for CloudFront (MUST be in us-east-1)

# Create provider for us-east-1 (CloudFront requirement)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

resource "aws_acm_certificate" "cloudfront_cert" {
  provider = aws.us_east_1  # CRITICAL: Must be us-east-1 for CloudFront

  domain_name       = "cdn.company.com"
  validation_method = "DNS"

  subject_alternative_names = [
    "www.company.com",
    "company.com"
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name    = "cloudfront-cert"
    Purpose = "CloudFront"
  }
}

# DNS validation (can use Route 53 in any region)
resource "aws_route53_record" "cloudfront_cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cloudfront_cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

resource "aws_acm_certificate_validation" "cloudfront_cert" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.cloudfront_cert.arn
  validation_record_fqdns = [for record in aws_route53_record.cloudfront_cert_validation : record.fqdn]
}

# Use with CloudFront
resource "aws_cloudfront_distribution" "cdn" {
  # ... other configuration ...

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.cloudfront_cert.arn
    ssl_support_method       = "sni-only"  # Free (vs $600/month for dedicated IP)
    minimum_protocol_version = "TLSv1.2_2021"  # Modern TLS only
  }
}

# CRITICAL REMINDERS:
# 1. CloudFront certificates MUST be in us-east-1
# 2. Use sni-only (not vip) to avoid $600/month dedicated IP cost
# 3. Use modern TLS version (TLSv1.2_2021 or TLSv1.3_2021)
# 4. CloudFront automatically uses certificate at all edge locations
""",
            validation_checklist=[
                "Certificate created in us-east-1 (CloudFront requirement)",
                "Certificate validation completed",
                "CloudFront distribution uses sni-only (not vip for cost)",
                "Minimum TLS version is modern (1.2 or 1.3)",
                "Tested HTTPS access from multiple global locations",
                "Alternative domain names (CNAMEs) configured in CloudFront",
                "Route 53 alias points to CloudFront distribution",
            ],
        ),
    ],
    estimated_implementation_time="1 day",
    recommendation_strategy="Use Regional Certificates for ALB/NLB in each region. Use Global Certificate in us-east-1 for CloudFront. If using both ALB and CloudFront, need certificates in both locations.",
)


# =============================================================================
# CERTIFICATE MONITORING PATTERNS
# =============================================================================

CERTIFICATE_MONITORING_PATTERNS = ArchitectureDecision(
    question="How should certificate expiration and renewal be monitored?",
    options=[
        DecisionOption(
            name="CloudWatch Alarms for Certificate Expiration",
            description="Set up CloudWatch alarms to alert on certificate expiration",
            when_to_use=[
                "All production certificates",
                "Want proactive expiration alerts",
                "Need compliance evidence of monitoring",
            ],
            when_not_to_use=[
                "Only using ACM certificates (auto-renew anyway)",
                "Development/staging environments",
            ],
            pros=[
                "Proactive alerts before expiration",
                "Works for ACM and imported certificates",
                "Free (CloudWatch alarms)",
                "Compliance evidence",
            ],
            cons=[
                "ACM auto-renews anyway (redundant for ACM)",
                "Must set up for each certificate",
                "Can create alert fatigue if too sensitive",
            ],
            monthly_cost_range=(0.00, 1.00),
            cost_drivers=[
                "CloudWatch alarms: $0.10/alarm/month (first 10 free)",
                "Typical: $0-1/month for 10-20 certificates",
            ],
            soc2_controls=["CC6.6", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
            implementation_guidance="""
# CloudWatch Alarm for Certificate Expiration

resource "aws_cloudwatch_metric_alarm" "certificate_expiration" {
  alarm_name          = "acm-certificate-expiring-${aws_acm_certificate.main.domain_name}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DaysToExpiry"
  namespace           = "AWS/CertificateManager"
  period              = 86400  # 1 day
  statistic           = "Minimum"
  threshold           = 30  # Alert 30 days before expiration
  alarm_description   = "Certificate expires in less than 30 days"

  dimensions = {
    CertificateArn = aws_acm_certificate.main.arn
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]

  tags = {
    Certificate = aws_acm_certificate.main.domain_name
  }
}

# Auto-Renewal Monitoring (for imported certificates)
resource "aws_cloudwatch_metric_alarm" "imported_cert_not_renewed" {
  alarm_name          = "imported-cert-renewal-failed"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DaysToExpiry"
  namespace           = "AWS/CertificateManager"
  period              = 86400
  statistic           = "Minimum"
  threshold           = 7  # Critical alert 7 days before
  alarm_description   = "CRITICAL: Imported certificate expires in 7 days"

  dimensions = {
    CertificateArn = aws_acm_certificate.imported.arn
  }

  alarm_actions = [
    aws_sns_topic.critical_alerts.arn,
    aws_sns_topic.pagerduty.arn  # Page on-call for imported certs
  ]
}

# Best Practices:
# - ACM certificates: 30-day warning (auto-renews at 60 days, but monitor anyway)
# - Imported certificates: 7-day critical alert (no auto-renewal!)
# - Set up SNS topics to notify ops team
# - Review certificate inventory quarterly
# - Document certificate ownership and renewal process
""",
            validation_checklist=[
                "CloudWatch alarm created for each production certificate",
                "Threshold set appropriately (30 days for ACM, 7 days critical for imported)",
                "SNS topic configured with correct subscribers",
                "Test alarm by adjusting threshold temporarily",
                "Alarm tags include certificate domain for easy identification",
                "Runbook documented for certificate renewal process",
            ],
        ),
        DecisionOption(
            name="AWS Config Rules for Certificate Compliance",
            description="Use AWS Config to track certificate compliance and renewal status",
            when_to_use=[
                "Need compliance auditing",
                "Want centralized certificate inventory",
                "Track certificate configuration changes",
                "SOC 2 / compliance requirements",
            ],
            when_not_to_use=[
                "Small deployments (<5 certificates)",
                "Cost-sensitive (Config has monthly cost)",
            ],
            pros=[
                "Centralized compliance dashboard",
                "Tracks configuration changes",
                "Automated compliance checks",
                "Audit trail for compliance",
            ],
            cons=[
                "AWS Config costs money ($2/month per rule)",
                "More complex setup",
                "Overkill for simple deployments",
            ],
            monthly_cost_range=(2.00, 10.00),
            cost_drivers=[
                "AWS Config: $2/month per active rule",
                "Config rules for certificates: 2-3 rules = $4-6/month",
                "Configuration item recordings: $0.003/item",
                "Typical: $2-10/month",
            ],
            soc2_controls=["CC6.6", "CC7.2", "CC8.1"],
            implementation_complexity="medium",
            operational_overhead="low",
            implementation_guidance="""
# AWS Config Rules for Certificate Compliance

resource "aws_config_config_rule" "acm_certificate_expiration" {
  name = "acm-certificate-expiration-check"

  source {
    owner             = "AWS"
    source_identifier = "ACM_CERTIFICATE_EXPIRATION_CHECK"
  }

  input_parameters = jsonencode({
    daysToExpiration = 30  # Flag certificates expiring in 30 days
  })

  depends_on = [aws_config_configuration_recorder.main]
}

resource "aws_config_config_rule" "acm_certificate_rsa_check" {
  name = "acm-certificate-rsa-check"

  source {
    owner             = "AWS"
    source_identifier = "ACM_CERTIFICATE_RSA_CHECK"
  }

  input_parameters = jsonencode({
    minimumRSAKeyLength = 2048  # Require RSA 2048+ bit keys
  })
}

# SNS topic for Config compliance notifications
resource "aws_sns_topic" "config_compliance" {
  name = "config-compliance-notifications"
}

resource "aws_config_delivery_channel" "main" {
  name           = "config-delivery-channel"
  s3_bucket_name = aws_s3_bucket.config.bucket
  sns_topic_arn  = aws_sns_topic.config_compliance.arn

  depends_on = [aws_config_configuration_recorder.main]
}

# Benefits:
# - Centralized view of all certificates in AWS Config dashboard
# - Automatic compliance checks (expiration, key length, etc.)
# - Historical tracking of certificate changes
# - Audit trail for compliance (SOC 2 CC8.1)
""",
            validation_checklist=[
                "AWS Config enabled in all regions with certificates",
                "Config rules deployed for certificate expiration",
                "Config rules deployed for certificate key length",
                "SNS topic configured for non-compliance notifications",
                "Config delivery channel set up to S3",
                "Quarterly review process for certificate compliance",
                "Cost reviewed and approved ($2-10/month)",
            ],
        ),
    ],
    estimated_implementation_time="1 day",
    recommendation_strategy="Use CloudWatch Alarms for simple certificate expiration monitoring (free for first 10). Use AWS Config Rules for compliance auditing and centralized tracking (costs $2-10/month). Combine both for production environments.",
)


# =============================================================================
# HELPER FUNCTION TO GET ALL CERTIFICATE MANAGER PATTERNS
# =============================================================================

def get_certificate_manager_patterns() -> dict[str, ArchitectureDecision]:
    """Get all AWS Certificate Manager patterns for CARL."""
    return {
        "certificate_types": CERTIFICATE_PATTERNS,
        "certificate_location": CERTIFICATE_LOCATION_PATTERNS,
        "certificate_monitoring": CERTIFICATE_MONITORING_PATTERNS,
    }
