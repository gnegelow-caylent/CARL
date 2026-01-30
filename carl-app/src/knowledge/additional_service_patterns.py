"""
Additional AWS Service Patterns.

Patterns for Redshift, DocumentDB, Network Firewall, and Cognito.
"""

from knowledge.architecture_patterns import ArchitectureDecision

REDSHIFT_DATA_WAREHOUSE = ArchitectureDecision(
    name="Redshift Data Warehouse",
    context="""
    Need data warehouse for:
    - Analytics and BI
    - Large-scale aggregations
    - Historical data analysis
    - OLAP workloads
    - Complex SQL queries
    """,
    options={
        "Redshift Serverless (Recommended for Variable Workloads)": """
        **Architecture:**
        - Redshift Serverless (auto-scaling)
        - S3 data lake (external tables via Spectrum)
        - QuickSight or Tableau (visualization)
        - VPC private subnets
        - KMS encryption

        **Features:**
        - Auto-scales compute (RPUs)
        - Pay per use (per RPU-hour)
        - No cluster management
        - Pause when idle
        - Scales to petabytes

        **Cost:** approx. $0.375/RPU-hour + storage
        - Base capacity: 8-512 RPUs
        - Storage: $0.024/GB/month
        - Example: 8 RPUs × 40 hours/week = approx. $120/month + storage

        **Pros:**
        - Serverless (no capacity planning)
        - Auto-scales
        - Pay per use
        - Pauses when idle

        **Cons:**
        - More expensive per hour than provisioned
        - Cold start time

        **When to use:** Variable workloads, dev/test, periodic analytics
        """,

        "Redshift Provisioned Clusters": """
        **Architecture:**
        - Redshift cluster (always-on)
        - RA3 instances (compute + managed storage)
        - Multi-node for production

        **Cost:** approx. $0.25/hour per node (ra3.xlplus)
        - 2-node cluster = $360/month (24/7)
        - Reserved instances: 40-75% savings

        **Pros:**
        - Cheaper for 24/7 workloads
        - Reserved instance savings
        - Predictable performance

        **Cons:**
        - Always-on cost
        - Manual scaling

        **When to use:** Production analytics, 24/7 workloads, predictable usage
        """
    },
    recommendation="Serverless for variable workloads, Provisioned for 24/7",
    tradeoffs="""
    **Serverless vs Provisioned:**
    - Serverless: $120/mo for 40hrs/week, auto-scales, pauses
    - Provisioned: $360/mo 24/7, predictable, cheaper for heavy use

    **Break-even:** Serverless cheaper if <80 hours/week usage
    """,
    related_controls=["CC6.7", "PI1.1", "CC7.2"],
    aws_services=["redshift", "s3", "kms", "cloudwatch"],
    estimated_cost="$120-500/month depending on usage"
)

DOCUMENTDB_MONGODB = ArchitectureDecision(
    name="DocumentDB (MongoDB-Compatible)",
    context="""
    Need MongoDB-compatible database with:
    - Document data model
    - JSON storage
    - Flexible schema
    - MongoDB API compatibility
    - Managed service
    """,
    options={
        "Amazon DocumentDB (Recommended for AWS)": """
        **Architecture:**
        - DocumentDB cluster
        - Primary + read replicas (up to 15)
        - VPC private subnets
        - KMS encryption at rest
        - Automated backups

        **Features:**
        - MongoDB 4.0 compatible
        - Auto-scaling storage (10GB to 64TB)
        - Point-in-time recovery
        - Multi-AZ replication
        - Read replicas for scaling

        **Cost:** approx. $0.072/hour per db.t3.medium instance
        - 1 instance: approx. $52/month
        - Storage: $0.10/GB/month
        - I/O: $0.20/million requests
        - Example: 1 instance + 100GB = approx. $62/month

        **Pros:**
        - Managed service (AWS-native)
        - MongoDB API compatible
        - Auto-scaling storage
        - Multi-AZ
        - Integrated with AWS services

        **Cons:**
        - Not 100% MongoDB compatible (missing some features)
        - More expensive than self-managed
        - Tied to AWS

        **When to use:** AWS-centric, want managed MongoDB, acceptable compatibility
        """,

        "MongoDB Atlas (Fully Compatible)": """
        **Architecture:**
        - MongoDB Atlas (managed by MongoDB Inc.)
        - Runs on AWS infrastructure
        - Full MongoDB compatibility

        **Cost:** approx. $57/month for M10 instance

        **Pros:**
        - 100% MongoDB compatible
        - Latest MongoDB features
        - Cross-cloud

        **Cons:**
        - Third-party service
        - Less AWS integration

        **When to use:** Need full MongoDB compatibility, multi-cloud
        """
    },
    recommendation="DocumentDB for AWS-native, Atlas for full compatibility",
    tradeoffs="""
    **DocumentDB vs MongoDB Atlas:**
    - DocumentDB: AWS-native, $62/mo, 90% compatible
    - Atlas: Full MongoDB, $57/mo, third-party

    **Use DocumentDB when:**
    - AWS-centric architecture
    - Don't need latest MongoDB features
    - Want native AWS integration (VPC, IAM, etc.)

    **Use Atlas when:**
    - Need 100% MongoDB compatibility
    - Multi-cloud strategy
    """,
    related_controls=["CC6.7", "A1.3", "CC7.2"],
    aws_services=["documentdb", "kms", "cloudwatch"],
    estimated_cost="$60-200/month"
)

NETWORK_FIREWALL = ArchitectureDecision(
    name="AWS Network Firewall",
    context="""
    Need network-level traffic filtering for:
    - Stateful inspection
    - IDS/IPS (intrusion detection/prevention)
    - Domain filtering (block malicious domains)
    - Protocol filtering
    - Deep packet inspection
    """,
    options={
        "AWS Network Firewall (Recommended)": """
        **Architecture:**
        - Network Firewall endpoint (per AZ)
        - Firewall policy (rules)
        - VPC route tables (route through firewall)
        - CloudWatch Logs (traffic logs)

        **Features:**
        - Stateful inspection
        - IDS/IPS (Suricata rules)
        - Domain filtering (allow/block lists)
        - Protocol filtering
        - Managed rule groups (AWS + partners)

        **Cost:** approx. $0.395/hour per endpoint + $0.065/GB processed
        - Endpoint: $0.395/hour × 730 hours = approx. $288/month per AZ
        - Data processing: $0.065/GB
        - 3 AZs + 1TB/month = approx. $929/month

        **Pros:**
        - Managed IDS/IPS
        - Suricata-compatible rules
        - Deep packet inspection
        - Scales automatically
        - AWS-native

        **Cons:**
        - Expensive ($288/mo per AZ)
        - Complex routing
        - Adds latency

        **When to use:** Compliance requirements (PCI-DSS, HIPAA), need IDS/IPS, high-security environments
        """,

        "Security Groups + NACLs (Cheaper)": """
        **Cost:** Free

        **Features:**
        - Stateful (security groups) and stateless (NACLs)
        - IP/port filtering only

        **Pros:**
        - Free
        - Simple

        **Cons:**
        - No deep packet inspection
        - No IDS/IPS
        - No domain filtering

        **When to use:** Standard workloads (sufficient for most)
        """
    },
    recommendation="Security Groups for most workloads, Network Firewall for compliance",
    tradeoffs="""
    **Network Firewall vs Security Groups:**
    - Network Firewall: IDS/IPS, domain filtering, $929/mo (3 AZs), compliance
    - Security Groups: IP/port filtering, free, sufficient for most

    **Use Network Firewall when:**
    - Compliance requires IDS/IPS (PCI-DSS, HIPAA)
    - Need to block malicious domains
    - Deep packet inspection required

    **Use Security Groups when:**
    - Standard workloads
    - IP/port filtering sufficient
    - Cost-conscious

    **Most workloads:** Security Groups are sufficient
    """,
    related_controls=["CC6.8", "CC7.1", "CC6.1"],
    aws_services=["networkfirewall", "vpc", "cloudwatch"],
    estimated_cost="$900-1500/month (expensive, compliance only)"
)

COGNITO_AUTHENTICATION = ArchitectureDecision(
    name="Cognito User Authentication",
    context="""
    Need user authentication for:
    - Web applications
    - Mobile apps
    - API access
    - User registration and login
    - MFA
    - Social identity providers (Google, Facebook)
    """,
    options={
        "Cognito User Pools (Recommended)": """
        **Architecture:**
        - Cognito User Pool (user directory)
        - App clients (web, mobile)
        - Identity providers (social, SAML, OIDC)
        - Lambda triggers (pre/post authentication)
        - MFA (SMS, TOTP)

        **Features:**
        - Built-in user directory
        - Registration and login UI (hosted UI)
        - MFA (SMS, TOTP, email)
        - Password policies
        - Social identity providers
        - SAML and OIDC federation
        - JWT tokens
        - Lambda triggers (custom auth logic)

        **Cost:** Free up to 50,000 MAUs
        - 0-50K MAUs: Free
        - 50K-100K MAUs: $0.00550 per MAU
        - 100K+ MAUs: Decreasing per MAU
        - MFA SMS: $0.00645 per SMS (US)
        - Example: 10K users = Free

        **Pros:**
        - Free tier (50K MAUs)
        - Managed service
        - Hosted UI included
        - MFA built-in
        - Social providers easy

        **Cons:**
        - Less flexible than custom auth
        - UI customization limited

        **When to use:** Most web/mobile apps, want managed authentication
        """,

        "Custom Auth with Lambda Authorizer": """
        **Architecture:**
        - Lambda authorizer (API Gateway)
        - Custom user database (DynamoDB, RDS)
        - JWT generation
        - Password hashing (bcrypt)

        **Cost:** approx. $0.20/million authorizations

        **Pros:**
        - Full control
        - Custom logic

        **Cons:**
        - Must implement everything
        - Security responsibility
        - More work

        **When to use:** Very custom requirements, existing user database
        """
    },
    recommendation="Cognito User Pools for most applications",
    tradeoffs="""
    **Cognito vs Custom:**
    - Cognito: Managed, free (50K MAUs), MFA built-in, social providers
    - Custom: Full control, more work, security responsibility

    **Use Cognito when:**
    - Standard authentication needs
    - Want managed service
    - Need MFA, social providers

    **Use Custom when:**
    - Very specific requirements
    - Existing authentication system
    - Need unusual auth flows

    **Default choice:** Cognito (free, managed, secure)
    """,
    related_controls=["CC6.1", "CC6.2", "CC6.5"],
    aws_services=["cognito", "lambda", "apigateway"],
    estimated_cost="$0/month (free tier for most apps)"
)

# Export patterns
PATTERNS = [
    REDSHIFT_DATA_WAREHOUSE,
    DOCUMENTDB_MONGODB,
    NETWORK_FIREWALL,
    COGNITO_AUTHENTICATION
]
