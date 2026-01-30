"""
Serverless Application Patterns for AWS.

Patterns for API Gateway, Lambda, AppSync, and Amplify serverless applications.
"""

from knowledge.architecture_patterns import ArchitectureDecision

SERVERLESS_API_BASIC = ArchitectureDecision(
    name="API Gateway + Lambda REST API",
    context="""
    Need to build a REST API with:
    - HTTP endpoints (GET, POST, PUT, DELETE)
    - Authentication and authorization
    - Request/response transformation
    - Low operational overhead
    - Auto-scaling
    """,
    options={
        "API Gateway HTTP API + Lambda (Recommended)": """
        **Architecture:**
        - API Gateway HTTP API (cheaper, simpler)
        - Lambda functions (business logic)
        - Cognito or Lambda authorizer (auth)
        - DynamoDB or RDS (data storage)
        - CloudWatch Logs (logging)

        **Features:**
        - Pay per request
        - Auto-scaling (0 to millions)
        - JWT authorizer built-in
        - CORS support
        - Custom domains

        **Cost:** approx. $1.00 per million requests
        - API Gateway HTTP: $1.00/million
        - Lambda: $0.20/million (assuming 128MB, 100ms)
        - Total: approx. $1.20/million requests

        **Pros:**
        - Cheapest option
        - Simple configuration
        - Fast (no VPC cold start)
        - Auto-scales instantly

        **Cons:**
        - Limited features vs REST API
        - No API keys
        - No request validation (must do in Lambda)

        **When to use:** Most new APIs, microservices, mobile backends
        """,

        "API Gateway REST API + Lambda": """
        **Architecture:**
        - API Gateway REST API (full features)
        - Lambda functions
        - API keys, usage plans
        - Request/response models
        - VPC integration (optional)

        **Features:**
        - Request validation
        - API keys and usage plans
        - Caching
        - More integration options
        - SDK generation

        **Cost:** approx. $3.50 per million requests
        - API Gateway REST: $3.50/million
        - Lambda: $0.20/million
        - Total: approx. $3.70/million requests

        **Pros:**
        - Full API Gateway features
        - Built-in caching
        - Request validation
        - Usage plans

        **Cons:**
        - 3.5x more expensive than HTTP API
        - More complex configuration

        **When to use:** Need caching, API keys, request validation, or SDK generation
        """,

        "ALB + Lambda": """
        **Architecture:**
        - Application Load Balancer
        - Lambda targets
        - Route53 for DNS

        **Features:**
        - Path-based routing
        - Fixed IP (with NLB)
        - Multi-target groups

        **Cost:** approx. $16/month + $0.008/LCU-hour
        - ALB always-on cost: approx. $16/month
        - Plus usage fees

        **Pros:**
        - Can mix Lambda + EC2 targets
        - Fixed IP possible
        - WebSocket support

        **Cons:**
        - More expensive (always-on ALB)
        - More complex than API Gateway
        - Not serverless (ALB always running)

        **When to use:** Hybrid architectures (Lambda + EC2), WebSockets, fixed IP required
        """
    },
    recommendation="API Gateway HTTP API + Lambda",
    tradeoffs="""
    **HTTP API vs REST API:**
    - HTTP API: $1/million, simpler, JWT auth, most use cases
    - REST API: $3.50/million, full features, caching, API keys

    **API Gateway vs ALB:**
    - API Gateway: Pay per request, true serverless
    - ALB: Always-on cost, better for hybrid (Lambda + EC2)

    **Decision:** Start with HTTP API, upgrade to REST if you need caching/API keys
    """,
    related_controls=["CC6.1", "CC6.4", "CC7.2", "PI1.4"],
    aws_services=["apigateway", "lambda", "cognito", "dynamodb", "cloudwatch"],
    estimated_cost="$1-5/million requests"
)

SERVERLESS_API_COMPLETE = ArchitectureDecision(
    name="Complete Production Serverless API",
    context="""
    Production REST API with all best practices:
    - Authentication and authorization
    - Rate limiting and throttling
    - Monitoring and alerting
    - Error handling
    - CORS and custom domains
    - SOC 2 compliant
    """,
    options={
        "Full Stack Serverless API (Recommended)": """
        **Complete Architecture:**

        **API Layer:**
        - API Gateway HTTP API (or REST if need caching)
        - Custom domain (Route53 + ACM certificate)
        - WAF attached (rate limiting, IP blocking)
        - CORS configuration
        - Lambda authorizer or Cognito

        **Compute:**
        - Lambda functions (one per route or grouped by domain)
        - VPC for database access (if RDS)
        - Environment variables from SSM/Secrets Manager
        - Lambda layers for shared code

        **Data:**
        - DynamoDB (serverless, auto-scaling) OR
        - Aurora Serverless (if need SQL)
        - S3 for file uploads
        - ElastiCache (optional, for caching)

        **Security:**
        - Cognito User Pool (authentication)
        - IAM roles (least privilege)
        - Secrets Manager (database credentials, API keys)
        - KMS encryption (DynamoDB, S3)
        - WAF rules (rate limiting, geo blocking)
        - HTTPS only (ACM certificate)

        **Monitoring:**
        - CloudWatch Logs (centralized)
        - CloudWatch Metrics (latency, errors, throttles)
        - X-Ray tracing (distributed tracing)
        - CloudWatch Alarms:
          * 5xx errors > 1%
          * p99 latency > 1 second
          * Throttles > 10/minute
          * Lambda errors > 5%
        - SNS notifications

        **CI/CD:**
        - GitHub Actions or CodePipeline
        - Automated testing
        - Blue/green deployment (Lambda versions + aliases)
        - Rollback capability

        **SOC 2 Controls Addressed:**
        - CC6.1: Access controls (Cognito, IAM)
        - CC6.4: Logical access restrictions (WAF)
        - CC6.5: Access accountability (CloudWatch logs)
        - CC6.7: Encryption (KMS, HTTPS)
        - CC7.1: Threat detection (WAF, CloudWatch)
        - CC7.2: System monitoring (CloudWatch, X-Ray)
        - PI1.4: Authorization (Cognito, Lambda authorizer)

        **Cost Breakdown:** approx. $50-200/month (1M requests)
        - API Gateway: $1-3.50/million requests
        - Lambda: $20-50/month (depends on executions)
        - DynamoDB: $10-30/month (depends on reads/writes)
        - Cognito: Free up to 50K MAUs
        - WAF: $10/month
        - CloudWatch: $5-10/month
        - X-Ray: $5/month
        - ACM: Free

        **Terraform Modules Needed:**
        - API Gateway HTTP/REST API
        - Lambda functions with environment variables
        - IAM roles for Lambda
        - DynamoDB tables with encryption
        - Cognito User Pool
        - WAF WebACL with rate limiting
        - Route53 records + ACM certificate
        - CloudWatch alarms
        - SNS topics
        - X-Ray sampling rules

        **Pros:**
        - Production-ready
        - Auto-scales to zero
        - Pay per use
        - SOC 2 compliant
        - Low operational overhead

        **Cons:**
        - Cold starts (mitigate with provisioned concurrency)
        - VPC latency if using RDS

        **When to use:** Most serverless APIs, microservices, mobile backends
        """
    },
    recommendation="Full stack with auth, monitoring, WAF, and CI/CD",
    tradeoffs="No tradeoffs - this is the complete, production-ready setup",
    related_controls=["CC6.1", "CC6.4", "CC6.5", "CC6.7", "CC7.1", "CC7.2", "PI1.4"],
    aws_services=["apigateway", "lambda", "cognito", "dynamodb", "waf", "cloudwatch", "xray", "secretsmanager", "kms"],
    estimated_cost="$50-200/month for 1M requests"
)

GRAPHQL_APPSYNC = ArchitectureDecision(
    name="GraphQL API with AWS AppSync",
    context="""
    Need GraphQL API with:
    - Real-time subscriptions
    - Flexible queries
    - Auto-scaling
    - Offline support (mobile)
    - Low latency
    """,
    options={
        "AWS AppSync (Recommended for GraphQL)": """
        **Architecture:**
        - AppSync GraphQL API
        - DynamoDB, Lambda, RDS, or HTTP as data sources
        - Cognito or API key authentication
        - Real-time subscriptions (WebSockets)
        - CloudWatch Logs

        **Features:**
        - Managed GraphQL service
        - Real-time subscriptions built-in
        - Offline sync for mobile apps
        - Caching (in-memory)
        - VTL or JavaScript resolvers

        **Cost:** approx. $4.00 per million requests
        - Query/Mutation: $4.00/million
        - Real-time updates: $2.00/million messages
        - Cheaper than API Gateway + Lambda for GraphQL

        **Pros:**
        - Built for GraphQL (no custom resolver logic)
        - Real-time subscriptions easy
        - Offline sync SDK
        - Auto-caching
        - Direct DynamoDB integration

        **Cons:**
        - Vendor lock-in (AppSync-specific)
        - VTL learning curve (use JS resolvers instead)
        - Less flexible than Lambda

        **When to use:** GraphQL APIs, real-time apps, mobile apps needing offline sync
        """,

        "API Gateway + Lambda + GraphQL library": """
        **Architecture:**
        - API Gateway HTTP/REST API
        - Lambda with Apollo Server or similar
        - GraphQL schema in code
        - DynamoDB/RDS for data

        **Features:**
        - Full control over GraphQL implementation
        - Any GraphQL library
        - Standard Node.js/Python code

        **Cost:** approx. $1.20 per million requests
        - Same as REST API (API Gateway + Lambda)

        **Pros:**
        - No vendor lock-in
        - Full flexibility
        - Standard GraphQL libraries
        - Easier testing

        **Cons:**
        - Must implement subscriptions yourself (complex)
        - No offline sync
        - More code to write
        - Cold starts

        **When to use:** Need full control, no real-time subscriptions, avoid vendor lock-in
        """
    },
    recommendation="AWS AppSync for GraphQL APIs",
    tradeoffs="""
    **AppSync vs Lambda GraphQL:**
    - AppSync: Easier, real-time built-in, $4/million, vendor lock-in
    - Lambda: More flexible, no lock-in, $1.20/million, more work

    **When to use AppSync:**
    - Real-time subscriptions needed
    - Mobile app with offline sync
    - Want managed GraphQL

    **When to use Lambda:**
    - Avoid vendor lock-in
    - Complex business logic
    - Existing GraphQL codebase
    """,
    related_controls=["CC6.1", "CC6.4", "CC7.2"],
    aws_services=["appsync", "dynamodb", "lambda", "cognito", "cloudwatch"],
    estimated_cost="$50-200/month for 1M requests"
)

FULLSTACK_AMPLIFY = ArchitectureDecision(
    name="Full-Stack Web App with AWS Amplify",
    context="""
    Need complete full-stack application with:
    - Frontend hosting (React, Vue, Angular)
    - Backend API
    - Authentication
    - Database
    - File storage
    - CI/CD
    - Minimal DevOps
    """,
    options={
        "AWS Amplify Hosting + Backend (Recommended for Rapid Development)": """
        **Architecture:**
        - Amplify Hosting (frontend - React, Vue, Angular, Next.js)
        - Amplify Backend:
          * AppSync GraphQL API
          * Cognito authentication
          * DynamoDB tables
          * S3 storage
          * Lambda functions
        - Git-based CI/CD (GitHub, GitLab, Bitbucket)

        **Features:**
        - Zero-config hosting
        - Automatic builds on git push
        - Preview environments for PRs
        - Custom domains
        - Backend scaffolding (CLI)
        - SDKs for auth, API, storage

        **Cost:** approx. $15-50/month (low traffic)
        - Hosting: $0.15/GB served
        - Build minutes: $0.01/minute
        - AppSync: $4/million requests
        - Storage: S3 costs
        - Example: 5GB served, 100 builds = approx. $15/month

        **Pros:**
        - Fastest way to production
        - Managed CI/CD built-in
        - Preview environments automatic
        - Backend scaffolding via CLI
        - Great for startups/MVPs

        **Cons:**
        - Higher cost than DIY
        - Less control over infrastructure
        - Vendor lock-in
        - Limited customization

        **When to use:** Startups, MVPs, rapid prototyping, small teams
        """,

        "CloudFront + S3 + API Gateway + Lambda (DIY)": """
        **Architecture:**
        - CloudFront + S3 (frontend hosting)
        - API Gateway + Lambda (backend API)
        - Cognito (authentication)
        - DynamoDB (database)
        - S3 (file storage)
        - GitHub Actions (CI/CD)

        **Features:**
        - Full control over each service
        - Cheaper at scale
        - More customization

        **Cost:** approx. $5-20/month (low traffic)
        - S3 + CloudFront: $1-5/month
        - API Gateway + Lambda: $1-10/month
        - DynamoDB: $1-5/month
        - Total: approx. $5-20/month (half of Amplify)

        **Pros:**
        - Lower cost
        - Full control
        - No vendor lock-in
        - Better for complex requirements

        **Cons:**
        - More setup time
        - Manual CI/CD configuration
        - More moving parts
        - Requires more AWS knowledge

        **When to use:** Cost-sensitive, complex requirements, want full control
        """
    },
    recommendation="Amplify for speed, DIY for cost/control",
    tradeoffs="""
    **Amplify vs DIY:**
    - Amplify: Fast setup, higher cost ($15-50/mo), less control
    - DIY: Slower setup, lower cost ($5-20/mo), full control

    **Decision:**
    - Pre-product-market-fit → Amplify (speed to market)
    - Post-PMF / scale → DIY (cost optimization)

    **Sweet spot:** Start with Amplify, migrate to DIY when you hit scale
    """,
    related_controls=["CC6.1", "CC8.1", "CC7.2"],
    aws_services=["amplify", "appsync", "cognito", "dynamodb", "s3", "lambda"],
    estimated_cost="$15-50/month (Amplify), $5-20/month (DIY)"
)

# Export patterns
PATTERNS = [
    SERVERLESS_API_BASIC,
    SERVERLESS_API_COMPLETE,
    GRAPHQL_APPSYNC,
    FULLSTACK_AMPLIFY
]
