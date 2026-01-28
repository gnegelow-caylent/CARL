"""
AWS Secrets Manager Lifecycle Patterns for CARL.

Patterns for secrets management, rotation automation, access control, and
compliance monitoring.

SOC 2 Relevance:
- CC6.1: Logical access controls (secrets rotation and access management)
- CC6.7: Restricted access to system configurations and master encryption keys
- CC7.2: System monitoring (secrets access auditing)
- CC8.1: Change management (automated secrets rotation)
"""

from dataclasses import dataclass
from typing import List
from .architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    SOC2Mapping,
)


# Pattern 1: Secrets Lifecycle Management Strategy
SECRETS_LIFECYCLE_PATTERNS = ArchitectureDecision(
    category="Security - Secrets Management",
    question="What secrets lifecycle management strategy should be implemented?",
    context="""
Secrets lifecycle management determines how credentials, API keys, and sensitive
configuration are stored, rotated, and accessed. Poor secrets management is a
leading cause of security breaches and compliance violations.

AWS Secrets Manager provides:
- Encrypted storage for secrets (KMS encryption at rest)
- Automatic rotation for supported services (RDS, Redshift, DocumentDB)
- Custom rotation using Lambda functions
- Fine-grained access control via IAM policies
- Audit logging via CloudTrail
- Secret versioning with AWSCURRENT and AWSPREVIOUS staging labels

Secret types:
- Database credentials (RDS, Aurora, Redshift)
- API keys (third-party services, internal APIs)
- SSH keys and certificates
- OAuth tokens and refresh tokens
- Application configuration secrets
- Service-to-service authentication credentials
""",
    options=[
        DecisionOption(
            name="Basic Secrets Storage (No Rotation)",
            description="""
Use Secrets Manager for encrypted secrets storage with manual rotation. Secrets
are stored encrypted at rest but rotation is a manual process triggered by
security team on a defined schedule (e.g., quarterly).

Implementation:
- Create secrets in Secrets Manager with KMS encryption
- Application retrieves secrets at runtime via SDK
- Manual rotation process:
  1. Generate new credentials
  2. Update secret in Secrets Manager
  3. Restart applications to pick up new credentials
  4. Verify old credentials no longer work

Access control:
- IAM policies restrict secret access per application
- CloudTrail logs all secret access for audit

Use for:
- Secrets that change infrequently (quarterly rotation acceptable)
- Third-party API keys where rotation is manual process
- Small organizations with limited secrets
""",
            pros=[
                "Simple to implement and understand",
                "No Lambda functions or rotation logic required",
                "Lowest cost (storage only, no rotation costs)",
                "Suitable for secrets without built-in rotation support",
                "Full control over rotation timing",
            ],
            cons=[
                "Manual rotation creates operational burden",
                "Risk of forgotten rotations (human error)",
                "Rotation requires application restarts (downtime)",
                "Does not meet compliance requirements for frequent rotation",
                "No automated rollback if rotation fails",
                "Higher risk of credential compromise",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret per month",
                "API calls: $0.05 per 10,000 calls",
                "For 20 secrets with 100K API calls/month: (20 × $0.40) + (10 × $0.05) = $8.50/month",
            ],
            monthly_cost_range=(5.00, 20.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Encrypted secrets storage with IAM access control",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudTrail logs all secret access for audit",
                ),
            ],
        ),
        DecisionOption(
            name="Automatic Rotation for Databases",
            description="""
Use Secrets Manager with automatic rotation for database credentials (RDS, Aurora,
Redshift, DocumentDB). Secrets Manager automatically rotates credentials on a
defined schedule (e.g., every 30 days) with zero application downtime.

Implementation:
- Enable automatic rotation when creating secret
- Secrets Manager creates Lambda rotation function automatically
- Rotation strategy: Single user (creates new password) or Alternating users
- Applications retrieve current secret version dynamically
- No application restarts needed for rotation

Rotation process (automatic):
1. Secrets Manager creates new password/credentials
2. Updates database with new credentials
3. Tests new credentials work
4. Marks new version as AWSCURRENT
5. Old version becomes AWSPREVIOUS (still valid for 24 hours)
6. Applications automatically use new version on next call

Supported services:
- Amazon RDS (MySQL, PostgreSQL, Oracle, SQL Server)
- Amazon Aurora (MySQL, PostgreSQL)
- Amazon Redshift
- Amazon DocumentDB
""",
            pros=[
                "Zero downtime rotation (no application restarts)",
                "Completely automated - no manual intervention",
                "Built-in rollback using AWSPREVIOUS version",
                "Meets compliance requirements for frequent rotation",
                "Applications automatically use latest credentials",
                "Reduces risk of credential compromise",
            ],
            cons=[
                "Only supports specific AWS database services",
                "Lambda rotation function costs (~$1/month per secret)",
                "More complex troubleshooting if rotation fails",
                "Requires application to fetch secret on each connection (or cache with TTL)",
                "Cannot use for third-party databases or API keys",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret per month",
                "Rotation Lambda: ~$1 per secret per month (execution + VPC costs)",
                "API calls: $0.05 per 10,000 calls",
                "For 10 RDS databases: (10 × $0.40) + (10 × $1) + API calls = $14+/month",
            ],
            monthly_cost_range=(10.00, 50.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Automatic credential rotation reduces compromise risk",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Encrypted secrets with automated rotation",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Automated rotation tracked and auditable",
                ),
            ],
        ),
        DecisionOption(
            name="Custom Rotation for All Secrets",
            description="""
Implement custom rotation logic for all secret types using Lambda functions.
Supports database credentials, API keys, OAuth tokens, service account credentials,
and any other secret type. Rotation frequency and logic customized per secret type.

Implementation:
- Create custom Lambda rotation functions per secret type
- Configure rotation schedule per secret (7-90 days typical)
- Implement rotation logic:
  - Database credentials: Create new password, update DB, test connection
  - API keys: Call third-party API to regenerate key, update secret
  - OAuth tokens: Use refresh token to get new access token
  - Service accounts: Rotate service account keys via API

Lambda rotation function:
- createSecret: Generate new credentials
- setSecret: Store/activate new credentials in target system
- testSecret: Verify new credentials work
- finishSecret: Mark new version as AWSCURRENT

Rotation strategies:
- Single user rotation: Change password for existing user
- Alternating users: Rotate between two users (zero downtime)
- Multi-user rotation: Rotate through pool of credentials
""",
            pros=[
                "Supports any secret type (not limited to AWS services)",
                "Customizable rotation frequency per secret",
                "Can implement complex rotation logic",
                "Zero downtime with alternating users strategy",
                "Meets strictest compliance requirements",
                "Significantly reduces credential compromise risk",
            ],
            cons=[
                "High implementation complexity (custom Lambda per secret type)",
                "Lambda costs for rotation executions",
                "Need to test and maintain rotation functions",
                "Rotation failures require troubleshooting",
                "Higher operational burden than basic storage",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret per month",
                "Lambda rotation: $0.50-2.00 per secret per month (depends on complexity)",
                "API calls: $0.05 per 10,000 calls",
                "Development time: 4-8 hours per secret type for rotation function",
                "For 30 secrets: (30 × $0.40) + (30 × $1.50) + API calls = $57+/month",
            ],
            monthly_cost_range=(30.00, 150.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Frequent automated rotation for all credential types",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Encrypted secrets with comprehensive rotation",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudTrail logs all secret operations",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="All rotations tracked with full audit trail",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Secrets Governance",
            description="""
Comprehensive secrets management with automated rotation, continuous compliance
monitoring, secrets discovery, and integration with ITSM/incident management.
Includes secrets inventory, usage analytics, and breach detection.

Implementation:
- Automated rotation for all secrets (database + custom Lambda functions)
- Continuous secrets compliance monitoring:
  - Detect secrets in code repositories (GitHub, GitLab, Bitbucket scanning)
  - Identify unrotated secrets (AWS Config rules)
  - Alert on secrets approaching rotation deadline
  - Monitor excessive secret access (anomaly detection)

- Secrets discovery and remediation:
  - Scan EC2, Lambda, ECS for hardcoded secrets
  - Automated migration to Secrets Manager
  - Secret sprawl detection and consolidation

- Advanced access control:
  - Resource-based policies for cross-account access
  - VPC endpoint policies for Secrets Manager
  - IAM permission boundaries
  - Secrets Manager replicas across regions

- Incident response:
  - Emergency rotation workflow
  - Secret compromise detection (GuardDuty integration)
  - Automated revocation and rotation on compromise
  - Integration with PagerDuty, ServiceNow

- Compliance and reporting:
  - Secrets inventory dashboard
  - Rotation compliance reports
  - Access analytics (who accessed which secrets)
  - SOC 2 evidence collection
""",
            pros=[
                "Zero unrotated secrets (comprehensive automation)",
                "Proactive secrets discovery prevents hardcoded credentials",
                "Detects and responds to secret compromises automatically",
                "Complete compliance reporting and audit trails",
                "Reduces secret sprawl across organization",
                "Integration with enterprise security tools",
            ],
            cons=[
                "Very high implementation complexity",
                "Significant cost from scanning, monitoring, Lambda executions",
                "Requires dedicated security team or expertise",
                "Ongoing operational overhead",
                "May be overkill for small organizations",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret × number of secrets",
                "Lambda rotation: $1.50 per secret per month",
                "AWS Config rules: $2 per rule per region × 5 rules = $10/month",
                "Secrets scanning: $50-200/month (third-party tools)",
                "CloudWatch dashboards: $3/month per dashboard",
                "GuardDuty: ~$4-10/month per account",
                "For 100 secrets: (100 × $0.40) + (100 × $1.50) + $10 + $200 + $3 + $10 = $413/month",
            ],
            monthly_cost_range=(200.00, 1000.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Comprehensive secrets rotation and access management",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Enterprise-grade secrets protection with breach detection",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Continuous monitoring and anomaly detection",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Automated incident response prevents outages",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Complete rotation tracking and compliance reporting",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Risk assessment",
                    how_it_helps="Secrets discovery identifies security risks",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Basic Secrets Storage (No Rotation) when:
- Very small organization (<10 secrets)
- Secrets change infrequently (quarterly rotation acceptable)
- Limited budget for secrets management
- No strict compliance requirements for rotation frequency
- Can tolerate manual rotation process

Choose Automatic Rotation for Databases when:
- Using RDS, Aurora, Redshift, or DocumentDB
- Want zero downtime rotation
- Meet compliance requirements for database credential rotation (30-90 days)
- Have budget for $1-2/secret/month for rotation
- Most common choice for database-heavy applications

Choose Custom Rotation for All Secrets when:
- Need to rotate API keys, OAuth tokens, service account credentials
- Strict compliance requirements (rotate every 7-30 days)
- Can invest in custom Lambda rotation function development
- Budget supports $30-150/month for rotation costs
- Medium to large organization with security team

Choose Enterprise Secrets Governance when:
- Large organization with 50+ secrets
- Strict compliance requirements (SOC 2 Type II, PCI-DSS, HIPAA)
- Need to detect and remediate hardcoded secrets
- Budget supports $200-1,000/month for comprehensive management
- Multi-account AWS environment
- Have dedicated security or compliance team
""",
    examples=[
        {
            "scenario": "Startup with 5 RDS databases and a few API keys",
            "recommendation": "Automatic Rotation for Databases",
            "reasoning": "Enable automatic rotation for RDS credentials ($14/month). Manually rotate API keys quarterly.",
        },
        {
            "scenario": "SaaS platform with 10 databases + 20 third-party API keys",
            "recommendation": "Custom Rotation for All Secrets",
            "reasoning": "Automatic rotation for databases. Custom Lambda functions for API key rotation every 30 days.",
        },
        {
            "scenario": "Financial services company with 100+ secrets and compliance requirements",
            "recommendation": "Enterprise Secrets Governance",
            "reasoning": "Need comprehensive rotation, secrets scanning, and compliance reporting for auditors.",
        },
        {
            "scenario": "Small agency with WordPress site using RDS",
            "recommendation": "Basic Secrets Storage (No Rotation)",
            "reasoning": "Single database credential. Manually rotate quarterly. Automatic rotation not justified for $1/month savings.",
        },
    ],
)


# Pattern 2: Secret Organization and Naming Strategy
SECRET_ORGANIZATION_PATTERNS = ArchitectureDecision(
    category="Security - Secrets Management",
    question="What secret organization and naming strategy should be implemented?",
    context="""
Secret organization determines how secrets are structured, named, and accessed.
Good organization makes it easy to find secrets, apply IAM policies, and maintain
secrets across environments and applications.

Organization considerations:
- Naming convention (hierarchical vs. flat)
- Granularity (one secret per credential vs. bundled secrets)
- Environment separation (dev/staging/prod)
- Application grouping
- Access control boundaries

Secrets Manager supports:
- Hierarchical naming with "/" delimiter (prod/db/mysql/master)
- Tags for metadata and grouping
- IAM policies with pattern matching (Allow: prod/*)
- Secret replication across regions
""",
    options=[
        DecisionOption(
            name="Flat Naming Structure",
            description="""
Use simple flat naming without hierarchy. Each secret has a unique name without
path-like structure. Suitable for small deployments with few secrets.

Naming examples:
- mysql-master-password
- stripe-api-key
- github-oauth-token
- redis-connection-string

Organization:
- No hierarchical structure
- Tags used for grouping (Environment: prod, App: web)
- IAM policies grant access per secret name
""",
            pros=[
                "Simple and easy to understand",
                "No need to plan hierarchy in advance",
                "Works well for small number of secrets (<20)",
                "Direct secret name in IAM policies",
            ],
            cons=[
                "Difficult to scale beyond 20-30 secrets",
                "Hard to apply IAM policies to groups of secrets",
                "No logical organization visible in secret names",
                "Name collisions across environments/applications",
                "Challenging to find related secrets",
            ],
            cost_factors=["No additional cost - same pricing regardless of naming"],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Basic secrets organization with IAM access control",
                ),
            ],
        ),
        DecisionOption(
            name="Environment-Based Hierarchy",
            description="""
Organize secrets by environment first, then by application or service. Enables
easy separation of dev, staging, and production secrets with IAM policies.

Naming convention:
{environment}/{application}/{component}/{secret-type}

Examples:
- prod/webapp/database/master-password
- prod/webapp/stripe/api-key
- staging/webapp/database/master-password
- dev/api/github/oauth-token

IAM policies:
- Developers: Allow staging/*, dev/*
- Production apps: Allow prod/{app-name}/*
- DBA team: Allow */database/*

Tags:
- Environment: prod, staging, dev
- Application: webapp, api, worker
- Owner: team-name
""",
            pros=[
                "Clear environment separation",
                "Easy IAM policies per environment (Allow: prod/*)",
                "Prevents accidental prod access from non-prod",
                "Scales to 100+ secrets",
                "Logical grouping visible in secret paths",
            ],
            cons=[
                "Longer secret names (typing/copy-paste)",
                "Need to plan hierarchy structure",
                "Duplicate secrets across environments (same secret, different values)",
                "Refactoring hierarchy is difficult",
            ],
            cost_factors=["No additional cost - same pricing regardless of naming"],
            monthly_cost_range=(0, 0),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Environment-based access control prevents unauthorized access",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Clear separation of prod and non-prod secrets",
                ),
            ],
        ),
        DecisionOption(
            name="Application-Based Hierarchy",
            description="""
Organize secrets by application/service first, then by environment and component.
Enables per-application IAM policies and clear ownership.

Naming convention:
{application}/{environment}/{component}/{secret-type}

Examples:
- webapp/prod/database/master-password
- webapp/prod/stripe/api-key
- webapp/staging/database/master-password
- api/prod/github/oauth-token
- worker/prod/sqs/credentials

IAM policies:
- Web app team: Allow webapp/*/*
- API team: Allow api/*/*
- Each app has dedicated IAM role with access only to its secrets

Tags:
- Application: webapp, api, worker
- Environment: prod, staging, dev
- Component: database, payment, auth
""",
            pros=[
                "Clear application ownership",
                "Easy per-application IAM policies",
                "Scales well for microservices (each service = application)",
                "Application teams have full control of their secrets",
                "Reduces blast radius of compromised credentials",
            ],
            cons=[
                "Shared secrets duplicated across applications",
                "Harder to enforce environment-wide policies",
                "Need discipline to prevent secret sprawl",
                "Refactoring applications requires secret renames",
            ],
            cost_factors=["No additional cost - same pricing regardless of naming"],
            monthly_cost_range=(0, 0),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Per-application access control limits credential access",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Application-based secrets isolation",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Multi-Dimension Hierarchy",
            description="""
Comprehensive hierarchical structure supporting multiple access patterns.
Combines account, environment, application, and component in flexible hierarchy.
Suitable for large organizations with complex IAM requirements.

Naming convention:
{account-name}/{environment}/{application}/{component}/{secret-type}

Examples:
- platform/prod/webapp/database/master-password
- platform/prod/webapp/stripe/api-key
- analytics/prod/redshift/database/master-password
- shared/prod/auth/oauth/github-client-secret

Alternative patterns supported:
- By account: platform/*, analytics/*, shared/*
- By environment: */prod/*, */staging/*
- By application: */*/webapp/*, */*/api/*
- By component: */*/*/database/*, */*/*/payment/*

IAM policy examples:
- Production access: Allow */prod/*/*
- Application team: Allow platform/*/*/webapp/*
- DBA team: Allow */*/*/database/*
- Shared services: Allow shared/*/*

Organization features:
- Cross-account secret sharing via resource policies
- Regional replication for DR
- Secret versioning strategy (AWSCURRENT, AWSPREVIOUS, AWSPENDING)
- Automated secret lifecycle (create → active → deprecated → deleted)

Tags (metadata):
- Account: platform, analytics, shared
- Environment: prod, staging, dev
- Application: webapp, api, worker, auth
- Component: database, payment, messaging
- Owner: team-email
- CostCenter: finance, engineering, operations
- Compliance: pci-dss, hipaa, sox
""",
            pros=[
                "Supports complex multi-account organizations",
                "Flexible IAM policies for any access pattern",
                "Clear ownership and metadata",
                "Scales to 1,000+ secrets",
                "Compliance tagging for audit requirements",
                "Enables cross-account secret sharing",
            ],
            cons=[
                "Very long secret names",
                "Complex to design and implement",
                "Requires governance and standards documentation",
                "Need automation for secret creation (to enforce naming)",
                "Overkill for small to medium organizations",
            ],
            cost_factors=["No additional cost - same pricing regardless of naming"],
            monthly_cost_range=(0, 0),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Multi-dimensional access control for complex organizations",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Comprehensive secrets isolation and sharing controls",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Compliance tagging enables audit reporting",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Risk assessment",
                    how_it_helps="Clear ownership and metadata supports risk assessment",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Flat Naming Structure when:
- Very small organization (<20 secrets total)
- Single environment (production only)
- Simple application architecture
- No plans to scale secrets management

Choose Environment-Based Hierarchy when:
- Multiple environments (dev, staging, prod)
- Need strict separation between prod and non-prod
- 20-100 secrets
- Security team needs environment-wide access control
- Most common choice for small to medium organizations

Choose Application-Based Hierarchy when:
- Microservices architecture (many applications)
- Application teams own their secrets
- Need to isolate secrets per service
- 50-200 secrets
- Clear application boundaries

Choose Enterprise Multi-Dimension Hierarchy when:
- Large organization (200+ secrets)
- Multi-account AWS environment
- Complex IAM access patterns
- Need cross-account secret sharing
- Compliance requirements for secret tagging and ownership
- Have dedicated security team to maintain governance
""",
    examples=[
        {
            "scenario": "Startup with single web application and 10 secrets",
            "recommendation": "Flat Naming Structure",
            "reasoning": "Simple names like 'db-password' and 'stripe-key' sufficient. No need for complexity.",
        },
        {
            "scenario": "SaaS company with dev, staging, prod environments",
            "recommendation": "Environment-Based Hierarchy",
            "reasoning": "prod/webapp/db, staging/webapp/db clearly separates environments. IAM policies prevent prod access from staging.",
        },
        {
            "scenario": "Platform with 15 microservices, each needing 5-10 secrets",
            "recommendation": "Application-Based Hierarchy",
            "reasoning": "api-gateway/prod/*, user-service/prod/*, payment-service/prod/* isolates secrets per service.",
        },
        {
            "scenario": "Enterprise with 5 AWS accounts, 200+ secrets, compliance requirements",
            "recommendation": "Enterprise Multi-Dimension Hierarchy",
            "reasoning": "platform/prod/webapp/db/password structure supports complex IAM policies, cross-account sharing, compliance tagging.",
        },
    ],
)


# Pattern 3: Secret Access and Caching Strategy
SECRET_ACCESS_PATTERNS = ArchitectureDecision(
    category="Security - Secrets Management",
    question="What secret access and caching strategy should be implemented?",
    context="""
Secret access strategy determines how frequently applications retrieve secrets
from Secrets Manager and whether secrets are cached. The choice affects cost
(API call charges), security (cache compromise risk), and performance (latency).

Access considerations:
- Frequency: Fetch on every use vs. cache for period
- Cache duration: Seconds to hours
- Cache invalidation: How to update when secret rotates
- Cost: $0.05 per 10,000 API calls
- Security: Cached secrets in memory are vulnerable to memory dumps

Example costs:
- No caching, 1M requests/month: 1M / 10K × $0.05 = $5/month per secret
- Cache for 1 hour, 1M requests/month: ~1 fetch/hour = $0 (under free tier)
""",
    options=[
        DecisionOption(
            name="No Caching (Fetch on Every Access)",
            description="""
Fetch secret from Secrets Manager on every access. No caching in application
memory or filesystem. Maximum security at cost of higher API charges and latency.

Implementation:
- Application calls GetSecretValue on every database connection, API call, etc.
- No in-memory caching
- Secrets Manager SDK handles API calls

Example (Python):
```python
import boto3

def get_database_connection():
    client = boto3.client('secretsmanager')
    secret = client.get_secret_value(SecretId='prod/webapp/database/master')
    password = json.loads(secret['SecretString'])['password']
    return connect_to_database(password)  # Fetches secret every time
```
""",
            pros=[
                "Maximum security - no secrets in memory",
                "Immediately picks up rotated secrets (no stale credentials)",
                "No cache invalidation logic needed",
                "Simple implementation",
            ],
            cons=[
                "Highest API costs ($0.05 per 10,000 calls)",
                "Higher latency on every secret access (50-200ms per fetch)",
                "Can hit Secrets Manager API rate limits (10,000 requests/second per region)",
                "Unnecessary cost for secrets that rarely change",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret per month",
                "API calls: $0.05 per 10,000 calls",
                "For 1M calls/month: (1,000,000 / 10,000) × $0.05 = $5/month (just API calls)",
                "For 10M calls/month: $50/month in API calls alone",
            ],
            monthly_cost_range=(5.00, 100.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="No cached secrets reduces memory dump risk",
                ),
            ],
        ),
        DecisionOption(
            name="Short-Term Caching (1-5 minutes)",
            description="""
Cache secrets in application memory for 1-5 minutes. Balance between cost
savings and security. Suitable for most applications with moderate secret
access frequency.

Implementation:
- Fetch secret on first access
- Cache in memory with TTL (time-to-live) of 1-5 minutes
- Refresh after TTL expires
- Secrets Manager SDK provides built-in caching (recommended)

Example (Python with AWS Secrets Manager caching library):
```python
from aws_secretsmanager_caching import SecretCache

# Cache secrets for 300 seconds (5 minutes)
cache = SecretCache(config=SecretCacheConfig(ttl=300))

def get_database_password():
    # Fetches from cache if < 5 minutes old, otherwise calls API
    secret = cache.get_secret_value(SecretId='prod/webapp/database/master')
    return json.loads(secret)['password']
```

API call reduction:
- No caching: 1,000 requests/min = 1,000 API calls
- 5-min caching: 1,000 requests/min = 0.2 API calls/min = 12 API calls/hour
""",
            pros=[
                "Significant cost savings (99%+ reduction in API calls)",
                "Lower latency - most requests served from cache (0ms vs 50-200ms)",
                "Secrets still refresh frequently (1-5 minutes)",
                "Built-in SDK support (easy to implement)",
                "Good security posture (short cache window)",
            ],
            cons=[
                "Slight delay in picking up rotated secrets (up to 5 minutes)",
                "Secrets stored in application memory (memory dump risk)",
                "Need to tune TTL based on rotation frequency",
                "Cache per process (Lambda = cache per container)",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret per month",
                "API calls with 5-min caching: ~288 calls/day = ~$0.13/month per secret",
                "For 10 secrets: (10 × $0.40) + $1.30 = $5.30/month (vs $54/month without caching)",
            ],
            monthly_cost_range=(5.00, 20.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Short cache duration limits secret exposure window",
                ),
            ],
        ),
        DecisionOption(
            name="Application Lifetime Caching",
            description="""
Cache secrets for the entire application lifetime. Fetch secret once on
application startup, use cached value until application restarts. Suitable
for long-running applications where secrets change infrequently.

Implementation:
- Fetch all secrets during application initialization
- Store in memory for application lifetime (days to weeks)
- Restart application to pick up rotated secrets
- NOT suitable for Lambda (containers restart frequently)

Example (Python):
```python
import boto3
import json

# Global variable - loaded once at startup
DATABASE_PASSWORD = None

def initialize_app():
    global DATABASE_PASSWORD
    client = boto3.client('secretsmanager')
    secret = client.get_secret_value(SecretId='prod/webapp/database/master')
    DATABASE_PASSWORD = json.loads(secret['SecretString'])['password']
    print("Secrets loaded")

def get_database_connection():
    # Uses cached secret from startup
    return connect_to_database(DATABASE_PASSWORD)

# Call once at app startup
initialize_app()
```

Deployment process:
1. Rotate secret in Secrets Manager
2. Trigger application deployment (ECS, EKS, EC2 Auto Scaling)
3. New application instances fetch new secret on startup
4. Old instances terminate after health check passes
5. Zero downtime deployment
""",
            pros=[
                "Minimum API costs (~1 call per app startup)",
                "Zero latency for secret access (in-memory variable)",
                "Simple implementation (no cache logic needed)",
                "Suitable for EC2, ECS, EKS long-running applications",
            ],
            cons=[
                "Requires application restart to pick up rotated secrets",
                "High security risk - secrets in memory for days/weeks",
                "Vulnerable to memory dumps and core dumps",
                "Not suitable for Lambda or frequently restarted containers",
                "Manual coordination between secret rotation and deployment",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret per month",
                "API calls: ~1 call per app startup (negligible cost)",
                "For 10 secrets with 50 app restarts/month: ~$0.02/month in API calls",
            ],
            monthly_cost_range=(5.00, 10.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Secrets fetched from encrypted store, but cached long-term",
                ),
            ],
        ),
        DecisionOption(
            name="Adaptive Caching with Rotation Detection",
            description="""
Intelligent caching that adapts TTL based on secret rotation schedule and
automatically invalidates cache when rotation occurs. Optimizes for cost,
performance, and security.

Implementation:
- Use Secrets Manager caching SDK with version tracking
- Detect secret rotation via version labels (AWSCURRENT changed)
- Adaptive TTL:
  - Secrets rotating every 7 days: Cache for 1 hour
  - Secrets rotating every 30 days: Cache for 6 hours
  - Secrets rotating every 90 days: Cache for 24 hours

- Cache invalidation triggers:
  - TTL expires (time-based)
  - AWSCURRENT version changed (rotation detection)
  - Manual invalidation via API (emergency rotation)

- EventBridge integration:
  - Listen for RotationSucceeded events
  - Invalidate cache across all application instances
  - Trigger health checks to verify new credentials work

Example (Python with advanced caching):
```python
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig

# Cache for 1 hour with version tracking
config = SecretCacheConfig(
    ttl=3600,  # 1 hour
    max_cache_size=100,
    version_stage='AWSCURRENT'
)
cache = SecretCache(config=config)

def get_secret_with_rotation_detection(secret_id):
    # Automatically detects version changes and refetches
    secret = cache.get_secret_value(SecretId=secret_id)
    return json.loads(secret)

# EventBridge Lambda function - invalidates cache on rotation
def handle_rotation_event(event, context):
    secret_id = event['detail']['secretId']
    # Publish SNS message to all app instances to invalidate cache
    sns.publish(Topic='cache-invalidation', Message=json.dumps({'secret_id': secret_id}))
```

Monitoring:
- CloudWatch metrics for cache hit ratio
- Alert if cache hit ratio < 90% (too many API calls)
- Alert if secret versions differ across app instances
""",
            pros=[
                "Optimal balance of cost, performance, and security",
                "Automatically picks up rotated secrets (no manual restart)",
                "Adaptive TTL reduces API calls based on rotation frequency",
                "Cache invalidation ensures all instances use latest secret",
                "Monitoring provides visibility into cache effectiveness",
            ],
            cons=[
                "Most complex implementation (EventBridge, cache invalidation logic)",
                "Need distributed cache invalidation mechanism",
                "Requires monitoring and tuning",
                "EventBridge costs for rotation events (~$1/million events)",
                "Application must handle cache invalidation messages",
            ],
            cost_factors=[
                "Secret storage: $0.40 per secret per month",
                "API calls with adaptive caching: ~$0.05-0.50 per secret per month",
                "EventBridge: ~$1 per million events (rotation events = minimal)",
                "SNS: $0 for first 1,000 notifications, then $0.50 per million",
                "CloudWatch metrics: $0.30 per custom metric per month",
                "For 30 secrets: (30 × $0.40) + (30 × $0.25) + $10 (monitoring) = $29/month",
            ],
            monthly_cost_range=(20.00, 100.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Automated cache invalidation ensures latest credentials are used",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Intelligent caching with rotation detection balances security and performance",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Cache hit ratio and version monitoring provide visibility",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Rotation events trigger automated cache updates",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose No Caching when:
- Extremely high security requirements (defense, healthcare, finance)
- Low request volume (<10,000 requests/month per secret)
- Secrets rotate very frequently (every few hours)
- Cost is not a concern
- Cannot tolerate any risk of stale credentials

Choose Short-Term Caching (1-5 minutes) when:
- Most applications with moderate request volume
- Balance cost savings and security
- Secrets rotate every 7-90 days
- Can tolerate up to 5-minute delay in rotation
- Most common choice for production applications

Choose Application Lifetime Caching when:
- Long-running applications (EC2, ECS, EKS) that restart infrequently
- Secrets change rarely (quarterly rotation or less)
- Willing to coordinate secret rotation with application deployment
- Minimize cost is highest priority
- Not suitable for Lambda or high-churn containers

Choose Adaptive Caching with Rotation Detection when:
- High request volume (>1M requests/month per secret)
- Multiple application instances need cache invalidation
- Want to optimize cost while maintaining security
- Have engineering resources to implement EventBridge integration
- Enterprise applications with sophisticated requirements
""",
    examples=[
        {
            "scenario": "Banking application with PCI-DSS requirements",
            "recommendation": "No Caching",
            "reasoning": "High security requirements. Cannot risk cached credentials in memory. Accept higher API costs.",
        },
        {
            "scenario": "E-commerce web application with 10K requests/minute",
            "recommendation": "Short-Term Caching (1-5 minutes)",
            "reasoning": "Balance security and cost. 5-minute cache reduces API calls by 99%. Tolerable rotation delay.",
        },
        {
            "scenario": "Long-running data processing job on EC2 (runs for days)",
            "recommendation": "Application Lifetime Caching",
            "reasoning": "Fetch secret once at job startup. Job restarts infrequently. Minimal API costs.",
        },
        {
            "scenario": "Microservices platform with 50 services, each calling Secrets Manager frequently",
            "recommendation": "Adaptive Caching with Rotation Detection",
            "reasoning": "High request volume justifies EventBridge integration. Cache invalidation ensures all services use latest secrets.",
        },
    ],
)


# Export all patterns
__all__ = [
    "SECRETS_LIFECYCLE_PATTERNS",
    "SECRET_ORGANIZATION_PATTERNS",
    "SECRET_ACCESS_PATTERNS",
]
