"""
AWS Certificate Manager (ACM) Architecture Patterns for CARL.

Patterns for SSL/TLS certificate management, validation, renewal automation,
and CloudFront integration.

SOC 2 Relevance:
- CC6.1: Logical and physical access controls (encrypted connections)
- CC6.6: Encryption of data in transit
- CC7.2: System monitoring (certificate expiration monitoring)
"""

from dataclasses import dataclass
from typing import List
from .architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    SOC2Mapping,
)


# Pattern 1: Certificate Lifecycle Management Strategy
CERTIFICATE_LIFECYCLE_PATTERNS = ArchitectureDecision(
    category="Security - Certificate Management",
    question="What certificate lifecycle management strategy should be implemented?",
    context="""
Certificate lifecycle management ensures SSL/TLS certificates are properly provisioned,
monitored, and renewed to maintain secure encrypted connections. Poor certificate
management can lead to service outages from expired certificates or security incidents
from manual certificate handling.

Key considerations:
- ACM provides free public certificates with automatic renewal
- ACM can import third-party certificates (no auto-renewal)
- Certificate expiration can cause service outages if not monitored
- CloudFront requires certificates in us-east-1 region
- Multi-region applications need certificate replication strategy
""",
    options=[
        DecisionOption(
            name="ACM Public Certificates Only",
            description="""
Use AWS Certificate Manager to provision and manage all public SSL/TLS certificates.
ACM handles validation, automatic renewal (60 days before expiry), and deployment.
All certificates are managed by AWS with no manual intervention required.

Implementation:
- Request ACM certificates for all public domains
- Use DNS validation (recommended) or email validation
- ACM automatically renews certificates in use
- Certificates automatically deployed to ALB, CloudFront, API Gateway

Certificate scope:
- Single domain: example.com
- Wildcard: *.example.com (covers all subdomains)
- Multi-domain (SAN): example.com, www.example.com, api.example.com
""",
            pros=[
                "Completely free - no certificate costs",
                "Automatic renewal every 60 days before expiry",
                "No manual certificate management overhead",
                "Integrated with ALB, CloudFront, API Gateway, Elastic Beanstalk",
                "Private keys never leave AWS infrastructure",
                "CloudWatch metrics for certificate expiration",
            ],
            cons=[
                "Limited to AWS services only (cannot export for EC2, on-prem)",
                "Cannot use with services running on EC2 instances directly",
                "Must use DNS or email validation (may require domain access)",
                "CloudFront certificates must be in us-east-1 region",
                "No support for private CA certificates",
            ],
            cost_factors=[
                "ACM public certificates: $0 (completely free)",
                "DNS validation: $0 (uses Route 53 or external DNS)",
                "CloudWatch metrics: $0 (included)",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Provides free SSL/TLS certificates with automatic renewal",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch metrics track certificate expiration automatically",
                ),
            ],
        ),
        DecisionOption(
            name="Hybrid ACM + Imported Certificates",
            description="""
Use ACM for most public certificates, but import third-party certificates when needed
(e.g., extended validation certificates, certificates for non-AWS services, organizational
requirements for specific CAs).

Implementation:
- Use ACM for standard public certificates
- Import third-party certificates from external CAs
- Set up CloudWatch alarms for imported certificate expiration (no auto-renewal)
- Implement renewal workflows for imported certificates

Use cases for imported certificates:
- Extended Validation (EV) certificates (ACM only provides DV)
- Certificates required by compliance/policy to use specific CA
- Certificates needed on EC2 instances or on-premises servers
- Multi-cloud certificate standardization
""",
            pros=[
                "Flexibility to use any certificate authority",
                "Supports Extended Validation (EV) certificates",
                "Can export certificates for use on EC2 or on-premises",
                "ACM certificates still free with auto-renewal",
                "Single management interface for all certificates",
            ],
            cons=[
                "Imported certificates cost from third-party CA ($50-300/year)",
                "No automatic renewal for imported certificates",
                "Manual renewal process creates operational overhead",
                "Risk of service outage if imported certificate expires",
                "Need monitoring and alerting for imported certificate expiration",
            ],
            cost_factors=[
                "ACM public certificates: $0",
                "Third-party certificates: $50-300/cert/year",
                "CloudWatch alarms for expiration: approx. $0.10/alarm/month",
                "Operational overhead for renewals: staff time",
            ],
            monthly_cost_range=(5.00, 50.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Provides SSL/TLS certificates from multiple sources",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch alarms track imported certificate expiration",
                ),
            ],
        ),
        DecisionOption(
            name="ACM Private CA for Internal Services",
            description="""
Use AWS Certificate Manager Private Certificate Authority (ACM Private CA) to issue
and manage certificates for internal services, microservices, and service mesh.
Combine with ACM public certificates for external-facing services.

Implementation:
- Create ACM Private CA for internal certificate authority
- Issue private certificates for internal services (APIs, databases, service mesh)
- Use ACM public certificates for external-facing services
- Implement short-lived certificates (1-7 days) for zero-trust architecture

Use cases:
- Service-to-service encryption in microservices
- mTLS (mutual TLS) authentication
- Kubernetes service mesh (Istio, Linkerd) certificates
- Internal API encryption
- Database connection encryption
""",
            pros=[
                "Full control over private certificate authority",
                "Issue unlimited private certificates after CA cost",
                "Supports short-lived certificates (1 hour to 10 years)",
                "Integrated with AWS services (API Gateway, NLB, IoT)",
                "Supports certificate revocation",
                "Ideal for zero-trust security model",
            ],
            cons=[
                "High cost: $400/month per Private CA",
                "Private certificates cost $0.75 each (after first 1,000/month free)",
                "Additional complexity managing private CA",
                "Need backup and disaster recovery for CA",
                "Overkill for small deployments",
            ],
            cost_factors=[
                "ACM Private CA: $400/month per CA",
                "Private certificates: $0 for first 1,000/month, then $0.75 each",
                "ACM public certificates: $0",
                "For 2,000 certs/month: $400 + (1,000 × $0.75) = $1,150/month",
            ],
            monthly_cost_range=(400.00, 2000.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="mTLS certificates provide service authentication",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Encrypts all internal service communication",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Certificate Management",
            description="""
Comprehensive certificate management combining ACM public certificates, ACM Private CA,
imported certificates, and automated certificate lifecycle management. Implements
certificate monitoring, alerting, rotation automation, and compliance reporting.

Implementation:
- ACM public certificates for all external services
- ACM Private CA for internal microservices and service mesh
- Import third-party EV certificates when required
- Automated certificate inventory and compliance scanning
- Certificate expiration monitoring with 90/60/30/7-day alerts
- Integration with AWS Config for certificate compliance rules
- Certificate usage analytics and optimization

Certificate governance:
- Automated certificate inventory (AWS Config)
- Certificate compliance rules (key length, expiration, usage)
- Certificate rotation playbooks
- Certificate incident response procedures
""",
            pros=[
                "Complete certificate lifecycle management",
                "Zero unplanned certificate expirations",
                "Compliance reporting and auditing",
                "Supports all certificate use cases",
                "Automated certificate inventory",
                "Integration with security tooling",
            ],
            cons=[
                "High cost from Private CA and third-party certificates",
                "Complex architecture requiring expertise",
                "Significant operational overhead",
                "May be overkill for smaller organizations",
            ],
            cost_factors=[
                "ACM public certificates: $0",
                "ACM Private CA: $400/month × number of CAs",
                "Private certificates: $0.75 each after 1,000/month",
                "Third-party certificates: $50-300/cert/year",
                "AWS Config rules: approx. $2/rule/region/month",
                "CloudWatch alarms: approx. $0.10/alarm/month",
            ],
            monthly_cost_range=(500.00, 3000.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Comprehensive encryption for all services",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Complete certificate monitoring and compliance reporting",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Automated certificate rotation and change tracking",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose ACM Public Certificates Only when:
- All services run on AWS (ALB, CloudFront, API Gateway)
- Small to medium organization with limited security team
- Cost optimization is important
- No requirement for certificate export or private CA

Choose Hybrid ACM + Imported Certificates when:
- Need Extended Validation (EV) certificates
- Some services run on EC2 or on-premises requiring exported certificates
- Organizational policy requires specific certificate authority
- Medium-sized organization with some certificate management capability

Choose ACM Private CA when:
- Large microservices architecture requiring service-to-service encryption
- Implementing zero-trust security model with mTLS
- Need to issue thousands of short-lived certificates
- Kubernetes or service mesh deployment (Istio, Linkerd, Consul)
- Can justify $400+/month cost per Private CA

Choose Enterprise Certificate Management when:
- Large enterprise with complex certificate requirements
- Strict compliance requirements (PCI DSS, HIPAA, SOC 2 Type II)
- Multiple AWS accounts and hybrid cloud environment
- Need certificate compliance reporting and auditing
- Budget supports $500-3,000/month for certificate management
""",
    examples=[
        {
            "scenario": "Startup with web application on ALB",
            "recommendation": "ACM Public Certificates Only",
            "reasoning": "Free certificates with automatic renewal. ALB integration is seamless. No operational overhead.",
        },
        {
            "scenario": "Financial services company with EV certificate requirement",
            "recommendation": "Hybrid ACM + Imported Certificates",
            "reasoning": "Import EV certificates for compliance while using ACM for most services. Set up expiration monitoring.",
        },
        {
            "scenario": "Microservices platform with 50+ services needing mTLS",
            "recommendation": "ACM Private CA",
            "reasoning": "Issue short-lived certificates for each service. Private CA cost justified by security benefits.",
        },
        {
            "scenario": "Enterprise with 1,000+ certificates across AWS and on-premises",
            "recommendation": "Enterprise Certificate Management",
            "reasoning": "Need comprehensive management, compliance reporting, and automated lifecycle management.",
        },
    ],
)


# Pattern 2: Certificate Scope Strategy
CERTIFICATE_SCOPE_PATTERNS = ArchitectureDecision(
    category="Security - Certificate Management",
    question="What certificate scope strategy should be implemented?",
    context="""
Certificate scope determines which domains are covered by a single certificate.
The choice between single domain, wildcard, and multi-domain (SAN) certificates
affects cost, management overhead, security posture, and operational flexibility.

Certificate types:
- Single domain: example.com (covers exactly one domain)
- Wildcard: *.example.com (covers all first-level subdomains)
- Multi-domain (SAN): example.com, www.example.com, api.example.com (explicit list)
- Wildcard with SAN: *.example.com, *.api.example.com, example.com

ACM considerations:
- ACM public certificates are free regardless of type
- Can include up to 10 domain names in multi-domain certificate
- Wildcard certificates cover unlimited first-level subdomains
- Cannot mix wildcard and specific domains in same ACM certificate (use separate certs)
""",
    options=[
        DecisionOption(
            name="Single Certificate per Domain",
            description="""
Use a separate certificate for each specific domain or subdomain. Each service
gets its own dedicated certificate with no wildcards.

Implementation:
- Request separate ACM certificate for each domain:
  - www.example.com → Certificate 1
  - api.example.com → Certificate 2
  - app.example.com → Certificate 3
  - admin.example.com → Certificate 4

Certificate management:
- Each ALB, CloudFront distribution, or API Gateway gets specific certificate
- Add new certificate when adding new subdomain
- Easier to track certificate usage per service
""",
            pros=[
                "Maximum security - compromised certificate affects one service only",
                "Clear certificate-to-service mapping",
                "Can revoke individual certificates without affecting others",
                "Easier to audit certificate usage",
                "No risk of wildcard certificate compromise affecting all services",
            ],
            cons=[
                "High management overhead - many certificates to track",
                "More complex DNS validation (separate validation per cert)",
                "More CloudWatch metrics to monitor",
                "Requires new certificate for every new subdomain",
                "Can hit ACM certificate limits in large deployments",
            ],
            cost_factors=[
                "ACM certificates: $0 (all free)",
                "CloudWatch metrics: approx. $0 (included)",
                "Operational overhead: high (manual work per certificate)",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Provides SSL/TLS encryption for each service",
                ),
            ],
        ),
        DecisionOption(
            name="Wildcard Certificates",
            description="""
Use wildcard certificates to cover all first-level subdomains. Single certificate
covers unlimited subdomains at one level (*.example.com covers api.example.com,
www.example.com, app.example.com, etc.).

Implementation:
- Request ACM wildcard certificate: *.example.com
- Use same certificate across all first-level subdomains
- Add apex domain certificate separately: example.com
- Request additional wildcard if using nested subdomains: *.api.example.com

Coverage examples:
- *.example.com covers:
  ✓ www.example.com
  ✓ api.example.com
  ✓ app.example.com
  ✗ example.com (apex domain not covered)
  ✗ v1.api.example.com (nested subdomain not covered)
""",
            pros=[
                "Minimal management overhead - one certificate covers many subdomains",
                "Easy to add new subdomains (no new certificate needed)",
                "Free with ACM (same as single domain certificates)",
                "Simplified certificate deployment across services",
                "Reduces ACM certificate count",
            ],
            cons=[
                "Security risk - compromised wildcard affects all subdomains",
                "Cannot revoke access to individual subdomain without affecting all",
                "Apex domain (example.com) requires separate certificate",
                "Nested subdomains (api.v1.example.com) not covered",
                "Harder to audit which services use certificate",
                "May violate security policies requiring per-service certificates",
            ],
            cost_factors=[
                "ACM wildcard certificate: $0",
                "ACM apex domain certificate: $0",
                "Total: $0 for unlimited subdomains",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Provides SSL/TLS encryption for all subdomains",
                ),
            ],
        ),
        DecisionOption(
            name="Multi-Domain (SAN) Certificates",
            description="""
Use Subject Alternative Name (SAN) certificates that explicitly list multiple domains
in a single certificate. Good middle ground between single domain and wildcard.

Implementation:
- Request ACM certificate with multiple domains (up to 10):
  - Primary domain: example.com
  - Additional domains:
    - www.example.com
    - api.example.com
    - app.example.com
    - admin.example.com

- Group related services under single certificate
- Can create multiple SAN certificates for different service groups:
  - Certificate 1: Main website (example.com, www.example.com)
  - Certificate 2: API services (api.example.com, api-v2.example.com)
  - Certificate 3: Admin services (admin.example.com, admin-staging.example.com)
""",
            pros=[
                "Balance between security and management overhead",
                "Explicit list of covered domains (no wildcards)",
                "Can group related services logically",
                "Easier certificate tracking than wildcards",
                "Can revoke without affecting unrelated services",
                "Free with ACM (up to 10 domains per certificate)",
            ],
            cons=[
                "Limited to 10 domains per ACM certificate",
                "Must request new certificate or update when adding domains",
                "More certificates to manage than wildcard approach",
                "Cannot dynamically add subdomains without certificate update",
                "Updating certificate requires re-validation",
            ],
            cost_factors=[
                "ACM multi-domain certificates: $0",
                "Can create multiple SAN certificates (all free)",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Provides SSL/TLS encryption for multiple domains",
                ),
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Explicit domain list provides clear access boundaries",
                ),
            ],
        ),
        DecisionOption(
            name="Hybrid Certificate Strategy",
            description="""
Combine different certificate types based on service requirements and security posture.
Use wildcards for development/staging, SAN certificates for production service groups,
and single certificates for high-security services.

Implementation:
Production:
- High-security services: Single certificates (admin.example.com, payments.example.com)
- Service groups: SAN certificates (api.example.com, api-v2.example.com)
- General services: Wildcard certificate (*.app.example.com)

Non-production:
- Wildcard certificates: *.dev.example.com, *.staging.example.com
- Minimal certificate management in non-production environments

Certificate policy:
- Define when to use each certificate type
- Document security requirements per service tier
- Automated certificate selection based on service classification
""",
            pros=[
                "Optimizes security vs. management overhead per service",
                "High-security services get dedicated certificates",
                "Development environments simplified with wildcards",
                "Flexible approach adapts to different requirements",
                "Can enforce different policies per environment",
            ],
            cons=[
                "Most complex certificate architecture",
                "Requires clear policy and documentation",
                "More certificates to manage than pure wildcard",
                "Team needs to understand certificate selection criteria",
                "Mixing strategies can create confusion",
            ],
            cost_factors=[
                "All ACM certificates: $0",
                "Operational overhead: medium-high",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Comprehensive encryption with appropriate security per service",
                ),
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Certificate strategy aligns with service security classification",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Single Certificate per Domain when:
- High-security requirements (finance, healthcare, government)
- Need to isolate certificate compromise impact
- Small number of domains/subdomains (<5)
- Regulatory requirements for per-service certificates
- Want clear audit trail of certificate usage

Choose Wildcard Certificates when:
- Many subdomains with similar security requirements
- Frequently add new subdomains (SaaS platforms)
- Development/staging environments
- Small to medium organization with limited security team
- Cost and simplicity are priorities

Choose Multi-Domain (SAN) Certificates when:
- Moderate number of domains (5-10 per service group)
- Want to group related services logically
- Need explicit domain list for compliance
- Balance between security and management
- Services have similar but not identical security requirements

Choose Hybrid Certificate Strategy when:
- Large organization with diverse security requirements
- Different certificate needs per environment (prod vs. dev)
- High-security services alongside general services
- Mature security organization with clear policies
- Can manage complexity of multiple certificate types
""",
    examples=[
        {
            "scenario": "Banking application with strict security requirements",
            "recommendation": "Single Certificate per Domain",
            "reasoning": "Each service (web, API, mobile API, admin) gets dedicated certificate. Compromise isolation is critical.",
        },
        {
            "scenario": "SaaS platform with customer subdomains (customer1.app.com, customer2.app.com)",
            "recommendation": "Wildcard Certificates",
            "reasoning": "*.app.example.com covers all customer subdomains. New customers added without certificate changes.",
        },
        {
            "scenario": "E-commerce site with API and admin portal",
            "recommendation": "Multi-Domain (SAN) Certificates",
            "reasoning": "One certificate covers example.com, www.example.com, api.example.com. Simple and secure.",
        },
        {
            "scenario": "Enterprise with production + 3 non-production environments",
            "recommendation": "Hybrid Certificate Strategy",
            "reasoning": "Production uses SAN certificates per service group. Non-prod uses wildcards (*.dev, *.staging, *.test).",
        },
    ],
)


# Pattern 3: Certificate Validation and Renewal Monitoring
CERTIFICATE_VALIDATION_PATTERNS = ArchitectureDecision(
    category="Security - Certificate Management",
    question="What certificate validation and renewal monitoring strategy should be implemented?",
    context="""
Certificate validation proves domain ownership before ACM issues a certificate.
Monitoring ensures certificates are renewed before expiration. Poor validation
and monitoring can cause service outages from expired certificates or delays
in certificate issuance.

ACM validation methods:
- DNS validation: Add CNAME record to prove domain ownership (recommended)
- Email validation: Click link sent to domain admin email (not recommended)

ACM renewal:
- ACM automatically renews certificates 60 days before expiration
- Renewal requires certificate to be actively in use (attached to resource)
- ACM exports DaysToExpiry metric to CloudWatch
- Imported certificates do NOT auto-renew
""",
    options=[
        DecisionOption(
            name="Basic DNS Validation",
            description="""
Use DNS validation for all ACM certificates. Add CNAME records to DNS manually
or via Route 53 automation. Rely on ACM's automatic renewal with no additional
monitoring beyond AWS Service Health Dashboard.

Implementation:
- Request ACM certificate with DNS validation
- Add CNAME validation records to Route 53 (or external DNS)
- ACM validates domain ownership and issues certificate
- ACM automatically renews certificates in use
- No custom monitoring configured

Validation process:
1. Request ACM certificate
2. ACM provides CNAME record: _abc123.example.com → _xyz456.acm-validations.aws
3. Add CNAME record to DNS
4. ACM validates and issues certificate (usually < 30 minutes)
5. ACM auto-renews 60 days before expiration
""",
            pros=[
                "Simple setup with minimal configuration",
                "DNS validation is more reliable than email",
                "Route 53 can automatically add validation records",
                "ACM handles renewal automatically",
                "No ongoing monitoring overhead",
            ],
            cons=[
                "No proactive alerting if renewal fails",
                "Relies on ACM service health (no independent monitoring)",
                "Won't catch unused certificates that don't renew",
                "No visibility into certificate lifecycle",
                "May not detect issues until service outage",
            ],
            cost_factors=[
                "ACM certificates: $0",
                "Route 53 hosted zone: $0.50/zone/month",
                "Route 53 queries: $0.40 per million queries",
            ],
            monthly_cost_range=(0, 1.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="DNS validation proves domain ownership for certificate issuance",
                ),
            ],
        ),
        DecisionOption(
            name="DNS Validation with Basic Monitoring",
            description="""
Use DNS validation for all ACM certificates. Add CloudWatch alarms for certificate
expiration monitoring. Get alerted 30 days before certificate expiration (covers
ACM public certificates and imported certificates).

Implementation:
- Use DNS validation for certificate issuance
- Create CloudWatch alarm on ACM DaysToExpiry metric
- Alert at 30 days before expiration
- Send alerts to SNS topic → email or Slack
- Monitor both ACM and imported certificates

CloudWatch alarm configuration:
- Metric: AWS/CertificateManager DaysToExpiry
- Condition: DaysToExpiry < 30
- Period: 1 day
- Evaluation: 1 consecutive period
- Action: Send SNS notification
""",
            pros=[
                "Proactive alerting before certificate expiration",
                "Catches renewal failures early (30-day warning)",
                "Monitors imported certificates (which don't auto-renew)",
                "Low cost ($0.10/alarm/month)",
                "Simple to set up and maintain",
            ],
            cons=[
                "Only alerts at 30 days (no escalating alerts)",
                "Manual response required to fix renewal issues",
                "Doesn't validate certificate is actually in use",
                "No automated remediation",
                "Limited visibility into certificate lifecycle",
            ],
            cost_factors=[
                "ACM certificates: $0",
                "CloudWatch alarms: $0.10 per alarm × number of certificates",
                "SNS notifications: $0 (first 1,000/month), then $0.50 per million",
                "For 20 certificates: $2/month",
            ],
            monthly_cost_range=(1.00, 10.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Ensures certificates remain valid with proactive monitoring",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch alarms provide certificate expiration visibility",
                ),
            ],
        ),
        DecisionOption(
            name="Automated DNS Validation with Escalating Alerts",
            description="""
Fully automated DNS validation using Route 53. Multi-level certificate expiration
monitoring with escalating alerts (90/60/30/7 days before expiration). Automated
remediation for common renewal failures.

Implementation:
- Use Route 53 for DNS with automatic validation record creation
- CloudWatch alarms at multiple thresholds:
  - 90 days: INFO alert to ops team (low priority)
  - 60 days: WARNING alert (investigate if ACM renewal hasn't started)
  - 30 days: CRITICAL alert (escalate to senior engineers)
  - 7 days: EMERGENCY alert (page on-call, executive notification)

- Lambda function for automated remediation:
  - Check if certificate is attached to resources
  - Verify DNS validation records are correct
  - Attempt to trigger renewal if possible
  - Create incident ticket if automated fix fails

Monitoring dashboard:
- Certificate inventory (ACM + imported)
- Days to expiration per certificate
- Renewal status
- Validation record health
""",
            pros=[
                "Zero manual intervention for DNS validation",
                "Multiple alert levels prevent surprise expirations",
                "Automated remediation reduces operational burden",
                "Comprehensive visibility into certificate lifecycle",
                "Catches issues early with 90-day advance warning",
            ],
            cons=[
                "More complex setup (Lambda, multiple alarms)",
                "Alert fatigue if too many certificates triggering 90-day alerts",
                "Requires Route 53 (doesn't work with external DNS automation)",
                "Higher cost from multiple alarms per certificate",
            ],
            cost_factors=[
                "ACM certificates: $0",
                "CloudWatch alarms: $0.10 × 4 levels × number of certificates",
                "Lambda function: approx. $0.20/month for remediation checks",
                "Route 53: $0.50/zone/month",
                "For 20 certificates: $8 (alarms) + $0.20 (Lambda) + $0.50 (R53) = approx. $9/month",
            ],
            monthly_cost_range=(5.00, 50.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Automated validation and renewal prevent certificate outages",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Multi-level monitoring provides comprehensive certificate oversight",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Automated remediation prevents service outages from expired certificates",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Certificate Governance",
            description="""
Comprehensive certificate management with automated validation, continuous monitoring,
compliance enforcement, and integration with ITSM/incident management. Includes
certificate inventory management, usage analytics, and compliance reporting.

Implementation:
- Automated DNS validation via Route 53 or external DNS automation
- Continuous certificate monitoring:
  - Real-time certificate inventory (AWS Config)
  - Certificate usage tracking (which resources use which certificates)
  - Certificate compliance scanning (key strength, expiration, usage)
  - Certificate chain validation

- Advanced alerting:
  - Escalating alerts (90/60/30/14/7/1 day)
  - Integration with PagerDuty, ServiceNow, Jira
  - Alert routing based on certificate criticality
  - Executive dashboard for certificate compliance

- Automated remediation and orchestration:
  - Detect and fix common renewal failures
  - Automatic certificate rotation for imported certificates
  - Integration with certificate ordering workflow
  - Automated compliance remediation

- Compliance and reporting:
  - Monthly certificate inventory reports
  - Certificate compliance posture dashboards
  - Audit logs for all certificate operations
  - SOC 2 evidence collection (certificate management controls)
""",
            pros=[
                "Complete certificate lifecycle management",
                "Zero unplanned certificate expirations",
                "Comprehensive compliance and audit reporting",
                "Automated remediation reduces operational burden",
                "Executive visibility into certificate posture",
                "Integration with enterprise ITSM tools",
            ],
            cons=[
                "High implementation complexity",
                "Significant ongoing operational overhead",
                "Cost from Config rules, custom Lambda functions, alarms",
                "Requires dedicated team or expertise",
                "May be overkill for small organizations",
            ],
            cost_factors=[
                "ACM certificates: $0",
                "AWS Config rules: $2/rule/region × 3 rules = $6/month (us-east-1)",
                "CloudWatch alarms: $0.10 × 6 levels × 50 certificates = $30/month",
                "Lambda functions: $5/month for remediation and compliance scanning",
                "CloudWatch dashboards: $3/month per dashboard",
                "SNS/PagerDuty integration: varies",
                "Total: approx. $50-200/month depending on scale",
            ],
            monthly_cost_range=(50.00, 200.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption of data in transit",
                    how_it_helps="Enterprise-grade certificate management ensures continuous encryption",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Comprehensive monitoring and compliance reporting",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Automated remediation prevents certificate-related outages",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Certificate rotation and changes tracked with audit logs",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Risk assessment",
                    how_it_helps="Certificate compliance scanning identifies risks",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Basic DNS Validation when:
- Small organization with few certificates (<10)
- All certificates are ACM public certificates (auto-renewal)
- Low budget for monitoring
- Trust AWS service health for renewal notifications
- Can tolerate reactive response to issues

Choose DNS Validation with Basic Monitoring when:
- Any organization using imported certificates (no auto-renewal)
- Want proactive alerts before expiration
- Budget supports $1-10/month for monitoring
- Have operations team to respond to alerts
- Most common choice for small to medium organizations

Choose Automated DNS Validation with Escalating Alerts when:
- Medium to large organization with many certificates (20+)
- High availability requirements (cannot tolerate outages)
- Operations team wants proactive early warnings
- Budget supports $5-50/month for advanced monitoring
- Use Route 53 for DNS management

Choose Enterprise Certificate Governance when:
- Large enterprise with 50+ certificates
- Strict compliance requirements (SOC 2 Type II, ISO 27001)
- Need compliance reporting and audit trails
- Budget supports $50-200/month for certificate management
- Have dedicated security or compliance team
- Multi-account AWS environment
""",
    examples=[
        {
            "scenario": "Startup with 3 ACM certificates for web app",
            "recommendation": "Basic DNS Validation",
            "reasoning": "ACM auto-renewal sufficient. Small scale doesn't justify monitoring cost.",
        },
        {
            "scenario": "E-commerce site with imported EV certificate + 5 ACM certificates",
            "recommendation": "DNS Validation with Basic Monitoring",
            "reasoning": "Imported certificate requires monitoring. CloudWatch alarm ensures no surprise expiration.",
        },
        {
            "scenario": "SaaS platform with 30 certificates across prod and non-prod",
            "recommendation": "Automated DNS Validation with Escalating Alerts",
            "reasoning": "Large certificate inventory needs proactive monitoring. Escalating alerts prevent issues.",
        },
        {
            "scenario": "Financial services company with 100+ certificates and SOC 2 requirements",
            "recommendation": "Enterprise Certificate Governance",
            "reasoning": "Compliance reporting required. AWS Config tracks certificate compliance. Audit logs needed for SOC 2.",
        },
    ],
)


# Export all patterns
__all__ = [
    "CERTIFICATE_LIFECYCLE_PATTERNS",
    "CERTIFICATE_SCOPE_PATTERNS",
    "CERTIFICATE_VALIDATION_PATTERNS",
]
