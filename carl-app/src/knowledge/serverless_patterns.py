"""
Serverless Application Patterns for AWS.

Patterns for API Gateway, Lambda, AppSync, and Amplify serverless applications.
"""

from knowledge.architecture_patterns import ArchitectureDecision, DecisionOption

SERVERLESS_API_BASIC = ArchitectureDecision(
    question="What should I use to build a serverless REST API?",
    options=[
        DecisionOption(
            name="API Gateway HTTP API + Lambda (Recommended)",
            description="Lighter-weight API Gateway with Lambda functions - cheaper and simpler than REST API for most use cases",
            when_to_use=[
                "Most new REST APIs and microservices",
                "Mobile app backends",
                "Need JWT authentication (built-in)",
                "Want lowest cost ($1/million requests)",
                "Simple CORS requirements",
                "Don't need API keys or caching",
            ],
            when_not_to_use=[
                "Need request validation at API Gateway level",
                "Need API keys and usage plans",
                "Need built-in caching",
                "Need SDK generation",
                "Complex request/response transformations",
            ],
            pros=[
                "Cheapest option ($1/million vs $3.50/million for REST)",
                "Simple configuration",
                "No VPC cold start",
                "Auto-scales from 0 to millions of requests",
                "JWT authorizer built-in",
                "CORS support built-in",
            ],
            cons=[
                "No API keys or usage plans",
                "No request validation (must validate in Lambda)",
                "No caching",
                "Fewer features than REST API",
            ],
            monthly_cost_range=(10.0, 50.0),
            cost_drivers=[
                "API Gateway HTTP: $1.00 per million requests",
                "Lambda: $0.20 per million requests (128MB, 100ms)",
                "Example: 10M requests/month = $12/month",
            ],
            soc2_controls=["CC6.1", "CC6.4", "CC7.2", "PI1.4"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="API Gateway REST API + Lambda",
            description="Full-featured API Gateway with request validation, caching, API keys, and SDK generation",
            when_to_use=[
                "Need API keys and usage plans",
                "Need built-in caching",
                "Need request/response validation at gateway",
                "Need SDK generation",
                "Complex request transformations",
                "Customer-facing APIs requiring rate limiting",
            ],
            when_not_to_use=[
                "Cost-sensitive (3.5x more expensive than HTTP API)",
                "Simple REST API without advanced features",
                "Don't need caching or API keys",
            ],
            pros=[
                "Full API Gateway feature set",
                "Built-in caching (reduce Lambda invocations)",
                "Request/response validation",
                "API keys and usage plans",
                "SDK generation (JavaScript, iOS, Android)",
            ],
            cons=[
                "3.5x more expensive than HTTP API ($3.50/million)",
                "More complex configuration",
                "Steeper learning curve",
            ],
            monthly_cost_range=(35.0, 150.0),
            cost_drivers=[
                "API Gateway REST: $3.50 per million requests",
                "Lambda: $0.20 per million requests",
                "Caching: $0.02/hour per GB (optional)",
                "Example: 10M requests/month = $37/month",
            ],
            soc2_controls=["CC6.1", "CC6.4", "CC7.2", "PI1.4"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="ALB + Lambda",
            description="Application Load Balancer with Lambda targets - for hybrid architectures mixing Lambda and EC2",
            when_to_use=[
                "Hybrid architecture (Lambda + EC2 targets)",
                "Need fixed IP address (with NLB)",
                "WebSocket support needed",
                "Migrating from EC2 to Lambda gradually",
                "Need path-based routing across services",
            ],
            when_not_to_use=[
                "Pure serverless (API Gateway is better)",
                "Cost-sensitive (ALB always-on cost)",
                "Small workloads (<1M requests/month)",
            ],
            pros=[
                "Can mix Lambda and EC2 targets",
                "Fixed IP possible (with NLB)",
                "WebSocket support",
                "Good for gradual migration to serverless",
            ],
            cons=[
                "Always-on cost ($16/month even with no traffic)",
                "More expensive than API Gateway for low traffic",
                "Not truly serverless (ALB always running)",
                "More complex configuration",
            ],
            monthly_cost_range=(20.0, 100.0),
            cost_drivers=[
                "ALB always-on: $16/month",
                "LCU (Load Balancer Capacity Units): $0.008/hour",
                "Lambda: $0.20 per million requests",
                "Example: Low traffic = $20/month (mostly ALB cost)",
            ],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF need_api_keys OR need_caching OR need_sdk_generation:
        → REST API ($3.50/million, full features)

    ELIF hybrid_architecture (Lambda + EC2) OR need_fixed_ip:
        → ALB + Lambda ($20-100/month, hybrid-friendly)

    ELSE:
        → HTTP API ($1/million, best for most cases)

    **Cost Comparison (10M requests/month):**
    - HTTP API: $12/month (cheapest)
    - REST API: $37/month (full features)
    - ALB + Lambda: $20-30/month (hybrid use case)

    **Recommendation:** Start with HTTP API (80% of use cases), upgrade to REST API only if you need caching, API keys, or SDK generation.
    """,
    soc2_relevance="""
    Serverless APIs are critical for SOC 2 access controls and monitoring:

    **CC6.1 (Access Controls):** Use Cognito or Lambda authorizers for authentication
    **CC6.4 (Access Restrictions):** API Gateway throttling and rate limiting
    **CC7.2 (Monitoring):** CloudWatch Logs for all API requests
    **PI1.4 (Authorization):** JWT tokens or Lambda authorizers enforce permissions

    All three options support encryption (HTTPS), logging, and authentication.
    """,
    common_mistakes=[
        "Using REST API when HTTP API is sufficient (wastes 3.5x money)",
        "Not setting up CloudWatch alarms for 5xx errors",
        "Forgetting to enable X-Ray tracing for debugging",
        "Not using Lambda layers for shared dependencies",
        "Using ALB for pure serverless (HTTP API is cheaper)",
    ],
)

SERVERLESS_API_COMPLETE = ArchitectureDecision(
    question="How do I build a production-ready serverless API with security and monitoring?",
    options=[
        DecisionOption(
            name="Complete Serverless API Stack (Recommended)",
            description="Production-ready serverless API with authentication, monitoring, WAF, encryption, and CI/CD",
            when_to_use=[
                "Production workloads requiring SOC 2 compliance",
                "Customer-facing APIs",
                "Need enterprise security controls",
                "Want full observability and monitoring",
                "Team wants low operational overhead",
            ],
            when_not_to_use=[
                "Proof of concept or prototype (overkill)",
                "Internal tools with no security requirements",
                "Budget < $50/month",
            ],
            pros=[
                "Production-ready out of the box",
                "Auto-scales to zero (pay only for usage)",
                "SOC 2 compliant architecture",
                "Low operational overhead",
                "Comprehensive monitoring and alerting",
                "Enterprise-grade security (WAF, encryption)",
            ],
            cons=[
                "Lambda cold starts (mitigate with provisioned concurrency)",
                "VPC latency if using RDS (use DynamoDB for best performance)",
                "More expensive than minimal setup ($50-200/month)",
            ],
            monthly_cost_range=(50.0, 200.0),
            cost_drivers=[
                "API Gateway: $1-3.50 per million requests",
                "Lambda: $20-50/month (depends on executions and memory)",
                "DynamoDB: $10-30/month (depends on reads/writes)",
                "Cognito: Free up to 50K MAUs",
                "WAF: $10/month + $1/million requests",
                "CloudWatch: $5-10/month (logs, metrics, alarms)",
                "X-Ray: $5/month (tracing)",
                "ACM: Free (SSL certificates)",
                "Example: 1M requests/month = $50-100/month",
            ],
            soc2_controls=["CC6.1", "CC6.4", "CC6.5", "CC6.7", "CC7.1", "CC7.2", "PI1.4"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Complete Stack Includes:**

    **API Layer:**
    - API Gateway HTTP or REST API
    - Custom domain (Route53 + ACM certificate)
    - WAF with rate limiting and IP blocking
    - CORS configuration
    - Lambda authorizer or Cognito

    **Compute:**
    - Lambda functions (one per route or grouped by domain)
    - VPC for database access (if using RDS)
    - Environment variables from Secrets Manager
    - Lambda layers for shared code

    **Data:**
    - DynamoDB (serverless, auto-scaling) OR Aurora Serverless v2 (if need SQL)
    - S3 for file uploads
    - ElastiCache (optional, for caching)

    **Security:**
    - Cognito User Pool (authentication)
    - IAM roles with least privilege
    - Secrets Manager for credentials and API keys
    - KMS encryption (DynamoDB, S3)
    - WAF rules (rate limiting, geo blocking)
    - HTTPS only

    **Monitoring:**
    - CloudWatch Logs (centralized)
    - CloudWatch Metrics (latency, errors, throttles)
    - X-Ray distributed tracing
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

    **Cost:** $50-200/month for 1M requests (all features included)
    """,
    soc2_relevance="""
    This architecture addresses critical SOC 2 controls:

    **CC6.1 (Access Controls):** Cognito authentication + IAM least privilege roles
    **CC6.4 (Logical Access Restrictions):** WAF rate limiting + IP filtering
    **CC6.5 (Access Accountability):** CloudWatch Logs track all API calls
    **CC6.7 (Encryption):** KMS encryption at rest + HTTPS in transit
    **CC7.1 (Threat Detection):** WAF + CloudWatch alarms for anomalies
    **CC7.2 (System Monitoring):** CloudWatch + X-Ray comprehensive monitoring
    **PI1.4 (Authorization):** Cognito + Lambda authorizers enforce permissions

    All components are managed services with built-in compliance features.
    """,
    common_mistakes=[
        "Skipping WAF (critical for rate limiting and DDoS protection)",
        "Not setting up CloudWatch alarms (no visibility into failures)",
        "Storing secrets in environment variables instead of Secrets Manager",
        "Not using X-Ray tracing (hard to debug distributed issues)",
        "Not implementing blue/green deployments (risky deployments)",
        "Using provisioned concurrency for all functions (expensive, only use for critical paths)",
    ],
)

GRAPHQL_APPSYNC = ArchitectureDecision(
    question="What should I use to build a GraphQL API with real-time subscriptions?",
    options=[
        DecisionOption(
            name="AWS AppSync (Recommended for GraphQL)",
            description="Managed GraphQL service with built-in real-time subscriptions, offline sync, and direct data source integrations",
            when_to_use=[
                "Building GraphQL APIs",
                "Need real-time subscriptions (WebSockets)",
                "Mobile apps requiring offline sync",
                "Want managed GraphQL service",
                "Direct DynamoDB integration needed",
                "Low DevOps overhead priority",
            ],
            when_not_to_use=[
                "Avoiding vendor lock-in is critical",
                "Need full control over GraphQL implementation",
                "Complex business logic better in code than resolvers",
                "Team not familiar with GraphQL",
            ],
            pros=[
                "Purpose-built for GraphQL (no custom implementation)",
                "Real-time subscriptions built-in (WebSockets)",
                "Offline sync SDK for mobile",
                "Auto-caching reduces database load",
                "Direct DynamoDB integration (no Lambda needed)",
                "JavaScript or VTL resolvers",
            ],
            cons=[
                "Vendor lock-in (AppSync-specific)",
                "VTL learning curve (use JavaScript resolvers instead)",
                "Less flexible than Lambda for complex logic",
                "More expensive than API Gateway for non-GraphQL use cases",
            ],
            monthly_cost_range=(40.0, 200.0),
            cost_drivers=[
                "Query/Mutation: $4.00 per million requests",
                "Real-time updates: $2.00 per million messages",
                "Example: 10M queries + 1M real-time = $42/month",
                "Cheaper than building real-time subscriptions with Lambda",
            ],
            soc2_controls=["CC6.1", "CC6.4", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="API Gateway + Lambda + GraphQL Library",
            description="Self-managed GraphQL using API Gateway, Lambda, and libraries like Apollo Server",
            when_to_use=[
                "Avoiding vendor lock-in",
                "Need full control over GraphQL implementation",
                "Complex business logic in code",
                "Existing GraphQL codebase to migrate",
                "Don't need real-time subscriptions",
                "Cost-sensitive (cheaper for query-only APIs)",
            ],
            when_not_to_use=[
                "Need real-time subscriptions (very complex to implement)",
                "Need offline sync for mobile apps",
                "Want low DevOps overhead",
                "Team lacks GraphQL expertise",
            ],
            pros=[
                "No vendor lock-in (portable GraphQL)",
                "Full flexibility and control",
                "Standard GraphQL libraries (Apollo, GraphQL.js)",
                "Easier local testing and debugging",
                "Cheaper for query-only APIs ($1.20/million)",
            ],
            cons=[
                "Must implement real-time subscriptions yourself (complex)",
                "No offline sync SDK",
                "More code to write and maintain",
                "Lambda cold starts affect performance",
                "Higher operational overhead",
            ],
            monthly_cost_range=(12.0, 60.0),
            cost_drivers=[
                "API Gateway HTTP: $1.00 per million requests",
                "Lambda: $0.20 per million requests",
                "Example: 10M requests = $12/month",
                "Cheaper than AppSync if no real-time subscriptions",
            ],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF need_realtime_subscriptions OR mobile_offline_sync:
        → AWS AppSync ($4/million, real-time built-in)

    ELIF avoid_vendor_lockin OR complex_business_logic:
        → Lambda + GraphQL library ($1.20/million, full control)

    ELSE:
        → AWS AppSync (best for most GraphQL use cases)

    **Cost Comparison (10M requests/month):**
    - AppSync: $40/month (includes real-time)
    - Lambda GraphQL: $12/month (query-only)

    **Real-Time Subscriptions:**
    - AppSync: Built-in, easy to implement
    - Lambda: Very complex (need WebSocket API, connection management, etc.)

    **Recommendation:** Use AppSync for GraphQL unless vendor lock-in is unacceptable. The real-time subscription features alone justify the cost.
    """,
    soc2_relevance="""
    GraphQL APIs require access controls and monitoring:

    **CC6.1 (Access Controls):** Cognito or API key authentication
    **CC6.4 (Access Restrictions):** Field-level authorization in resolvers
    **CC7.2 (Monitoring):** CloudWatch Logs for all GraphQL operations

    Both options support encryption (HTTPS/WSS) and CloudWatch integration.
    """,
    common_mistakes=[
        "Using Lambda for GraphQL when real-time is needed (reinventing AppSync)",
        "Not implementing field-level authorization",
        "Forgetting to enable CloudWatch Logs for debugging",
        "Not using DataLoader pattern (causes N+1 queries)",
        "Using VTL resolvers instead of JavaScript (harder to debug)",
    ],
)

FULLSTACK_AMPLIFY = ArchitectureDecision(
    question="What should I use to build a full-stack web application with minimal DevOps?",
    options=[
        DecisionOption(
            name="AWS Amplify Hosting + Backend (Recommended for Rapid Development)",
            description="All-in-one platform for frontend hosting, backend API, authentication, and CI/CD",
            when_to_use=[
                "Startups and MVPs (speed to market)",
                "Small teams without DevOps expertise",
                "Want zero-config hosting and CI/CD",
                "React, Vue, Angular, or Next.js apps",
                "Need preview environments for PRs",
                "Rapid prototyping",
            ],
            when_not_to_use=[
                "Cost-sensitive (2-3x more expensive than DIY)",
                "Need full control over infrastructure",
                "Complex custom requirements",
                "High traffic (>100GB served/month)",
            ],
            pros=[
                "Fastest way to production (minutes, not days)",
                "Managed CI/CD built-in (automatic deploys on git push)",
                "Preview environments for every PR",
                "Backend scaffolding via Amplify CLI",
                "Great for startups and MVPs",
                "Zero DevOps knowledge required",
            ],
            cons=[
                "Higher cost than DIY ($15-50/month vs $5-20/month)",
                "Less control over infrastructure",
                "Vendor lock-in (hard to migrate off Amplify)",
                "Limited customization options",
            ],
            monthly_cost_range=(15.0, 50.0),
            cost_drivers=[
                "Hosting: $0.15 per GB served",
                "Build minutes: $0.01 per minute",
                "AppSync: $4 per million requests",
                "Example: 5GB served, 100 builds, 1M API calls = $15-20/month",
            ],
            soc2_controls=["CC6.1", "CC8.1", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="CloudFront + S3 + API Gateway + Lambda (DIY)",
            description="Self-managed full-stack using individual AWS services for maximum control and cost efficiency",
            when_to_use=[
                "Cost-sensitive (want lowest cost)",
                "Need full control over infrastructure",
                "Complex custom requirements",
                "High traffic (>100GB served/month)",
                "Team has AWS expertise",
            ],
            when_not_to_use=[
                "Small team without DevOps skills",
                "Want fast time to market (Amplify is faster)",
                "Startup/MVP (speed > cost optimization)",
            ],
            pros=[
                "Lower cost (50% cheaper: $5-20/month vs $15-50/month)",
                "Full control over each service",
                "No vendor lock-in",
                "Better for complex requirements",
                "Cheaper at scale",
            ],
            cons=[
                "More setup time (days vs minutes)",
                "Manual CI/CD configuration (GitHub Actions, CodePipeline)",
                "More moving parts to manage",
                "Requires AWS knowledge",
                "Higher operational overhead",
            ],
            monthly_cost_range=(5.0, 20.0),
            cost_drivers=[
                "S3 + CloudFront: $1-5/month (5GB served)",
                "API Gateway + Lambda: $1-10/month",
                "DynamoDB: $1-5/month",
                "Example: Low traffic = $5-10/month",
            ],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF startup OR mvp OR small_team OR need_speed:
        → AWS Amplify (fastest to market)

    ELIF cost_sensitive OR high_traffic OR complex_requirements:
        → DIY CloudFront + S3 + API Gateway (cheaper, more control)

    ELSE:
        → AWS Amplify (default for most teams)

    **Cost Comparison:**
    - Amplify: $15-50/month (low traffic), easy setup
    - DIY: $5-20/month (low traffic), more setup work

    **Time to Production:**
    - Amplify: 1 hour (zero DevOps)
    - DIY: 1-2 days (requires CI/CD setup)

    **Sweet Spot Strategy:**
    1. Start with Amplify for speed (pre-product-market-fit)
    2. Migrate to DIY when you hit scale (post-PMF)
    3. Cost savings justify migration effort at 100GB+ served/month

    **Recommendation:** Use Amplify unless you have DevOps expertise and cost is critical.
    """,
    soc2_relevance="""
    Full-stack applications need comprehensive security:

    **CC6.1 (Access Controls):** Cognito authentication for both options
    **CC8.1 (Change Management):** CI/CD ensures tested, version-controlled changes
    **CC7.2 (Monitoring):** CloudWatch for backend, Amplify Console or CloudFront logs for frontend

    Both options support HTTPS, authentication, and logging for compliance.
    """,
    common_mistakes=[
        "Using Amplify for cost-sensitive projects (DIY is 50% cheaper)",
        "DIY without CI/CD (error-prone manual deployments)",
        "Not setting up CloudFront cache invalidation in CI/CD",
        "Forgetting to enable HTTPS redirect in CloudFront",
        "Not using environment variables for API endpoints (hard to deploy)",
    ],
)

# Export patterns
PATTERNS = [
    SERVERLESS_API_BASIC,
    SERVERLESS_API_COMPLETE,
    GRAPHQL_APPSYNC,
    FULLSTACK_AMPLIFY
]
