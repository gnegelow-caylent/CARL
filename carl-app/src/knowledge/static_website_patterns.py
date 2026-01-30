"""
Static Website Hosting Patterns for AWS.

Comprehensive patterns for hosting static websites on AWS with CloudFront, WAF, and security best practices.
"""

from knowledge.architecture_patterns import ArchitectureDecision

STATIC_WEBSITE_BASIC = ArchitectureDecision(
    name="Basic Static Website with CloudFront",
    context="""
    Need to host a static website (HTML, CSS, JS, images) with:
    - Global distribution and low latency
    - HTTPS support
    - Basic security
    - Simple deployment
    """,
    options={
        "S3 + CloudFront (Recommended)": """
        **Architecture:**
        - S3 bucket (PRIVATE) for content storage
        - CloudFront distribution as public endpoint
        - Origin Access Control (OAC) for S3 access
        - ACM certificate for HTTPS

        **Security:**
        - S3 bucket NOT public (CloudFront only access)
        - HTTPS only (redirect HTTP to HTTPS)
        - CloudFront signed URLs/cookies (optional)
        - Block direct S3 access

        **Deployment:**
        - Upload to S3
        - CloudFront invalidation for updates
        - S3 versioning for rollback

        **Cost:** approx. $1-5/month for low traffic
        - S3: $0.023/GB storage
        - CloudFront: $0.085/GB first 10TB (US/Europe)
        - Data transfer out from S3 to CloudFront: free

        **Pros:**
        - Simple, serverless
        - Global CDN with edge caching
        - Automatic HTTPS via ACM (free)
        - 99.99% availability SLA
        - Low cost at scale

        **Cons:**
        - No server-side logic (static only)
        - CloudFront cache invalidation takes 5-10 minutes
        - Limited request/response manipulation

        **When to use:** Most static websites, SPAs, documentation sites
        """,

        "S3 Static Website Hosting (NOT RECOMMENDED)": """
        **Architecture:**
        - S3 bucket with static website hosting enabled
        - Bucket must be PUBLIC
        - Custom domain via Route53 CNAME

        **WARNING:** Not recommended due to:
        - No HTTPS support (HTTP only)
        - No CDN/caching (slow globally)
        - Public bucket (security risk)
        - No WAF protection
        - Limited to S3 region

        **Cost:** approx. $0.50/month

        **When to use:** Never for production. Only for quick demos/testing.
        """,

        "Amplify Hosting": """
        **Architecture:**
        - AWS Amplify managed hosting
        - Integrated CI/CD from Git
        - Built-in CloudFront distribution
        - Automatic HTTPS

        **Features:**
        - Git-based deployments (GitHub, GitLab, Bitbucket)
        - Automatic build on commit
        - Preview deployments for PRs
        - Built-in redirects and rewrites

        **Cost:** approx. $0.15/GB + $0.01/build minute

        **Pros:**
        - Zero infrastructure management
        - Built-in CI/CD
        - Easy rollbacks
        - Preview environments

        **Cons:**
        - Higher cost than DIY S3+CloudFront
        - Less control over CloudFront config
        - Vendor lock-in

        **When to use:** Teams wanting managed CI/CD, rapid iteration
        """
    },
    recommendation="S3 + CloudFront",
    tradeoffs="""
    **S3 + CloudFront vs Amplify:**
    - S3+CF: More control, lower cost, requires manual CI/CD
    - Amplify: Less control, higher cost, built-in CI/CD

    **NEVER use S3 static website hosting for production** (no HTTPS, public bucket)
    """,
    related_controls=["CC6.1", "CC6.7", "CC6.8", "C1.1"],
    aws_services=["s3", "cloudfront", "acm", "route53", "waf"],
    estimated_cost="$1-10/month depending on traffic"
)

STATIC_WEBSITE_WAF = ArchitectureDecision(
    name="Static Website with WAF Protection",
    context="""
    Static website needing protection against:
    - DDoS attacks
    - Geographic restrictions
    - Rate limiting
    - Common web attacks (SQLi, XSS)
    """,
    options={
        "CloudFront + AWS WAF (Recommended)": """
        **Architecture:**
        - S3 bucket (private) for content
        - CloudFront distribution
        - AWS WAF attached to CloudFront
        - WAF rules for protection

        **WAF Rules to Include:**
        1. **Rate limiting:** 2000 requests per 5 minutes per IP
        2. **Geo blocking:** Block countries if needed
        3. **Core Rule Set:** AWS Managed Rules CRS (OWASP Top 10)
        4. **Known bad inputs:** AWS Managed Rules Known Bad Inputs
        5. **IP reputation:** AWS Managed Rules IP Reputation

        **Cost:** approx. $10-20/month
        - WAF: $5/month + $1 per rule + $0.60 per million requests
        - CloudFront: same as without WAF

        **SOC 2 Controls:**
        - CC6.8: Malware protection / threat detection
        - CC7.1: System monitoring for threats
        - CC6.1: Logical access controls

        **Monitoring:**
        - CloudWatch metrics for blocked requests
        - Alarms for high block rates
        - WAF logs to S3 or CloudWatch Logs

        **Pros:**
        - Comprehensive protection
        - Managed rules (low maintenance)
        - Real-time threat blocking
        - SOC 2 compliant

        **Cons:**
        - Additional $10-20/month cost
        - Requires rule tuning to avoid false positives

        **When to use:** Production websites, sites handling sensitive data, compliance requirements
        """,

        "CloudFront + Shield Standard": """
        **Architecture:**
        - S3 + CloudFront (same as basic)
        - AWS Shield Standard (free, automatic)

        **Protection:**
        - DDoS protection (network/transport layer)
        - Automatic mitigation
        - No configuration needed

        **Cost:** Free (included with CloudFront)

        **Pros:**
        - Zero cost
        - Automatic DDoS protection
        - No configuration

        **Cons:**
        - No application-layer protection (no WAF)
        - No rate limiting
        - No geo blocking
        - Limited against sophisticated attacks

        **When to use:** Low-risk sites, non-production, tight budget
        """,

        "CloudFront + Shield Advanced + WAF": """
        **Architecture:**
        - Full protection: S3 + CloudFront + WAF + Shield Advanced

        **Features:**
        - All WAF features
        - Enhanced DDoS protection
        - DDoS Response Team (DRT) support
        - Cost protection (credits for scaling during attack)

        **Cost:** approx. $3000-3500/month
        - Shield Advanced: $3000/month
        - WAF: $10-20/month
        - CloudFront: variable

        **When to use:** Enterprise apps, very high-risk sites, financial services

        **Not recommended for most sites** - Shield Standard + WAF is sufficient
        """
    },
    recommendation="CloudFront + AWS WAF",
    tradeoffs="""
    **Shield Standard (free) vs WAF ($10-20/mo):**
    - Shield Standard: DDoS only, no app-layer protection
    - WAF: Full protection including rate limiting, geo blocking, OWASP Top 10

    **For production sites:** ALWAYS use WAF ($10-20/mo is worth it)
    **For dev/test sites:** Shield Standard is acceptable

    **Shield Advanced ($3000/mo):** Only for enterprise/high-value targets
    """,
    related_controls=["CC6.8", "CC7.1", "CC6.1", "A1.2"],
    aws_services=["cloudfront", "waf", "shield", "s3"],
    estimated_cost="$10-20/month with WAF (recommended)"
)

STATIC_WEBSITE_CICD = ArchitectureDecision(
    name="Static Website CI/CD Pipeline",
    context="""
    Need automated deployment pipeline for static website:
    - Git-based workflow
    - Automatic builds on commit
    - Preview environments
    - Rollback capability
    """,
    options={
        "GitHub Actions + S3 + CloudFront": """
        **Architecture:**
        - GitHub repository with Actions workflow
        - Build step (if needed - npm build, Jekyll, Hugo, etc.)
        - Deploy to S3
        - CloudFront invalidation

        **Workflow:**
        1. Commit to main → trigger GitHub Actions
        2. Build static assets (if needed)
        3. Sync to S3 (aws s3 sync)
        4. Invalidate CloudFront cache
        5. Notify Slack/email on success/failure

        **Cost:** approx. $0/month (GitHub Actions free tier)

        **Pros:**
        - Free (within limits)
        - Full control
        - Git-based workflow
        - Preview environments (separate S3 buckets)

        **Cons:**
        - Manual setup
        - Requires GitHub
        - Need to manage secrets

        **When to use:** Most projects with GitHub
        """,

        "AWS Amplify Hosting": """
        **Architecture:**
        - Amplify manages everything
        - Connect Git repo
        - Automatic builds and deploys

        **Features:**
        - Zero config CI/CD
        - Preview deployments for PRs
        - Easy rollbacks
        - Built-in monitoring

        **Cost:** approx. $0.15/GB + $0.01/build minute

        **Pros:**
        - No pipeline setup
        - Preview environments automatic
        - Integrated monitoring

        **Cons:**
        - 10x higher cost than DIY
        - Less flexibility

        **When to use:** Teams wanting managed solution, rapid development
        """,

        "CodePipeline + CodeBuild": """
        **Architecture:**
        - CodeCommit or GitHub as source
        - CodeBuild for build step
        - CodePipeline for orchestration
        - Deploy to S3 + invalidate CloudFront

        **Cost:** approx. $1-5/month
        - CodePipeline: $1/pipeline/month
        - CodeBuild: $0.005/build minute

        **Pros:**
        - All AWS native
        - Good for multi-environment
        - IAM integration

        **Cons:**
        - More complex setup
        - Higher cost than GitHub Actions
        - Requires AWS expertise

        **When to use:** AWS-centric teams, already using CodePipeline
        """
    },
    recommendation="GitHub Actions + S3 + CloudFront",
    tradeoffs="""
    **GitHub Actions vs Amplify:**
    - GH Actions: Free, more control, requires setup
    - Amplify: Paid, zero setup, less control

    **For most teams:** Start with GitHub Actions (free, flexible)
    **For rapid development:** Consider Amplify (paid, managed)
    """,
    related_controls=["CC8.1", "CC5.2", "PI1.4"],
    aws_services=["s3", "cloudfront", "amplify", "codepipeline", "codebuild"],
    estimated_cost="$0-5/month depending on solution"
)

STATIC_WEBSITE_COMPLETE = ArchitectureDecision(
    name="Complete Production Static Website",
    context="""
    Production static website with all best practices:
    - Global distribution
    - Security (WAF, HTTPS)
    - Monitoring and alerts
    - CI/CD pipeline
    - Custom domain
    - Compliance ready (SOC 2)
    """,
    options={
        "Full Stack (Recommended for Production)": """
        **Complete Architecture:**

        **Content Delivery:**
        - S3 bucket (private, versioning enabled)
        - CloudFront distribution with multiple origins
        - ACM certificate for HTTPS
        - Route53 for DNS (custom domain)

        **Security:**
        - AWS WAF with managed rules:
          * Core Rule Set (OWASP Top 10)
          * Known Bad Inputs
          * IP Reputation
          * Rate limiting (2000 req/5min/IP)
        - CloudFront Origin Access Control (OAC)
        - S3 bucket NOT public (CloudFront only)
        - HTTPS only (HTTP redirect)

        **Logging:**
        - CloudFront access logs → S3
        - S3 server access logging
        - WAF logs → CloudWatch Logs or S3
        - CloudTrail for API audit trail

        **Monitoring:**
        - CloudWatch alarms:
          * 4xx error rate > 10%
          * 5xx error rate > 1%
          * WAF blocked requests > 100/min
          * Origin response time > 1 second
        - SNS notifications for alarms
        - CloudWatch dashboard

        **Backup & Recovery:**
        - S3 versioning for rollback
        - Cross-region replication (optional)
        - Lifecycle policies for old versions

        **CI/CD:**
        - GitHub Actions workflow
        - Automatic deployment on merge
        - CloudFront invalidation
        - Slack notifications

        **SOC 2 Controls Addressed:**
        - CC6.1: Logical access controls (OAC, private S3)
        - CC6.7: Data classification (encryption)
        - CC6.8: Threat protection (WAF)
        - CC7.1: Threat detection (monitoring)
        - CC7.2: System monitoring (CloudWatch)
        - C1.1: Confidentiality (HTTPS, encryption)
        - A1.3: Recovery (versioning, backups)

        **Cost Breakdown:** approx. $20-40/month
        - S3 storage: $0.23/month (10GB)
        - CloudFront: $8-30/month (1TB transfer)
        - WAF: $10/month (5 rules)
        - Route53: $0.50/month (hosted zone)
        - ACM: Free
        - CloudWatch: $1-2/month (alarms, logs)

        **Terraform Modules Needed:**
        - S3 bucket with versioning
        - CloudFront distribution with OAC
        - ACM certificate
        - Route53 records
        - WAF WebACL with managed rules
        - CloudWatch alarms
        - IAM roles for GitHub Actions

        **Pros:**
        - Production-ready
        - SOC 2 compliant
        - Comprehensive security
        - Full observability

        **Cons:**
        - Higher initial setup time
        - $20-40/month cost

        **When to use:** All production websites, compliance requirements
        """
    },
    recommendation="Full Stack with all security and monitoring",
    tradeoffs="No tradeoffs - this is the complete, production-ready setup",
    related_controls=["CC6.1", "CC6.7", "CC6.8", "CC7.1", "CC7.2", "C1.1", "A1.3"],
    aws_services=["s3", "cloudfront", "waf", "acm", "route53", "cloudwatch", "sns", "cloudtrail"],
    estimated_cost="$20-40/month"
)

# Export patterns
PATTERNS = [
    STATIC_WEBSITE_BASIC,
    STATIC_WEBSITE_WAF,
    STATIC_WEBSITE_CICD,
    STATIC_WEBSITE_COMPLETE
]
