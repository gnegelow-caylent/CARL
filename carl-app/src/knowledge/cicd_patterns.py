"""
CI/CD Pipeline Patterns for AWS.

Patterns for CodePipeline, CodeBuild, CodeDeploy, and GitHub Actions with AWS integration.
"""

from knowledge.architecture_patterns import ArchitectureDecision, DecisionOption

CICD_GITHUB_ACTIONS = ArchitectureDecision(
    question="What should I use for CI/CD pipelines to AWS?",
    options=[
        DecisionOption(
            name="GitHub Actions + OIDC to AWS (Recommended)",
            description="GitHub Actions with OpenID Connect authentication - no long-lived AWS credentials needed",
            when_to_use=[
                "Using GitHub for source control",
                "Want free or low-cost CI/CD",
                "Need fast build times",
                "Public repos or private repos <2000 minutes/month",
                "Security-conscious (OIDC, no stored credentials)",
            ],
            when_not_to_use=[
                "Need manual approval gates (use CodePipeline)",
                "Multi-environment with strict access controls",
                "Compliance requires audit trail in AWS (use CodePipeline)",
                "Not using GitHub",
            ],
            pros=[
                "Free for public repos",
                "2,000 free minutes/month for private repos",
                "No AWS credentials stored (OIDC authentication)",
                "Fast builds with parallel jobs",
                "Huge marketplace of actions",
                "Matrix builds for multi-platform testing",
            ],
            cons=[
                "Dependent on GitHub availability",
                "6-hour job timeout limit",
                "Less AWS integration than CodePipeline",
                "No native approval gates (can implement manually)",
            ],
            monthly_cost_range=(0.0, 10.0),
            cost_drivers=[
                "Free for public repositories",
                "Private repos: 2,000 minutes/month free",
                "Additional minutes: $0.008/minute (Linux)",
                "Example: 3,000 minutes/month = $8/month",
            ],
            soc2_controls=["CC8.1", "PI1.4", "CC5.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="GitHub Actions + Self-Hosted Runners",
            description="GitHub Actions with EC2 self-hosted runners for unlimited builds and VPC access",
            when_to_use=[
                "High build volume (>2000 minutes/month)",
                "Need VPC access (private RDS, internal APIs)",
                "Need custom software or GPU instances",
                "Want faster builds (no artifact download)",
            ],
            when_not_to_use=[
                "Low build volume (<2000 minutes/month - use GitHub-hosted)",
                "Don't want to manage EC2 instances",
                "Security concerns about running third-party code",
            ],
            pros=[
                "Unlimited build minutes",
                "VPC network access",
                "Faster builds (no artifact download)",
                "Custom software pre-installed",
                "Can use GPU instances",
            ],
            cons=[
                "Must manage EC2 instances (patching, monitoring)",
                "Security risk (third-party code runs on your infrastructure)",
                "Always-on cost even when not building",
            ],
            monthly_cost_range=(10.0, 50.0),
            cost_drivers=[
                "EC2: t3.micro ≈ $7/month, t3.small ≈ $15/month",
                "EBS storage: included in EC2",
                "Example: 1 t3.small runner = $15/month for unlimited builds",
            ],
            soc2_controls=["CC8.1", "CC5.3"],
            implementation_complexity="medium",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="CodePipeline + CodeBuild (AWS-Native)",
            description="Fully AWS-native CI/CD with manual approval gates and deep AWS integration",
            when_to_use=[
                "Need manual approval gates (security/QA sign-off)",
                "Multi-environment with strict IAM controls",
                "Compliance requires AWS audit trail (CloudTrail)",
                "All-in on AWS ecosystem",
                "Using CodeCommit for source control",
            ],
            when_not_to_use=[
                "Cost-sensitive (<$1/month budget)",
                "Using GitHub (GitHub Actions is easier)",
                "Don't need approval gates",
                "Small project with simple deployment",
            ],
            pros=[
                "Native AWS integration (IAM, CloudWatch, CloudTrail)",
                "Manual approval gates built-in",
                "Advanced deployment strategies (canary, blue/green)",
                "CloudWatch alarm-based rollback",
                "Full audit trail in AWS",
            ],
            cons=[
                "$1/pipeline/month (always-on cost)",
                "Build minutes cost $0.005/minute",
                "Less community tooling than GitHub Actions",
                "Tied to AWS (not portable)",
            ],
            monthly_cost_range=(3.0, 20.0),
            cost_drivers=[
                "CodePipeline: $1/active pipeline/month",
                "CodeBuild: $0.005/build minute (100 minutes free/month)",
                "Example: 1 pipeline, 500 build minutes/month = $3.50/month",
            ],
            soc2_controls=["CC8.1", "PI1.4", "CC5.3", "CC4.1"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF using_github AND cost_sensitive:
        → GitHub Actions + OIDC (free or cheap)

    ELIF need_approval_gates OR compliance_audit_trail:
        → CodePipeline (AWS-native approvals)

    ELIF build_volume > 2000_minutes_per_month:
        → GitHub Actions + Self-hosted runners (unlimited)

    ELSE:
        → GitHub Actions + OIDC (best for most cases)

    **Cost Comparison (500 build minutes/month):**
    - GitHub Actions: $0/month (within free tier)
    - GitHub Actions (self-hosted): $15/month (t3.small always-on)
    - CodePipeline: $3.50/month ($1 pipeline + $2.50 build minutes)

    **When to Use CodePipeline:**
    - Need manual approval gates
    - Multi-environment with different IAM permissions
    - Compliance requires AWS audit trail
    - Already all-in on AWS

    **When to Use GitHub Actions:**
    - Using GitHub for source control
    - Want free or low-cost CI/CD
    - Don't need approval gates
    - 80% of use cases
    """,
    soc2_relevance="""
    CI/CD pipelines are critical for SOC 2 change management:

    **CC8.1 (Change Management):** Automated pipelines ensure all changes go through testing
    **PI1.4 (Authorization):** Approval gates enforce proper authorization for production changes
    **CC5.3 (Policies and Procedures):** Documented pipeline enforces deployment procedures
    **CC4.1 (Ongoing Evaluations):** Automated tests continuously validate system quality

    GitHub Actions and CodePipeline both support audit logging and approval gates.
    """,
    common_mistakes=[
        "Storing AWS credentials in GitHub Secrets (use OIDC instead)",
        "Not setting up branch protection rules (allow direct commits to main)",
        "Skipping security scanning (missing vulnerabilities)",
        "Using self-hosted runners without proper security hardening",
        "Not implementing approval gates for production deployments",
    ],
)

CICD_ECS_DEPLOYMENT = ArchitectureDecision(
    question="How should I deploy containerized applications to ECS?",
    options=[
        DecisionOption(
            name="GitHub Actions + ECR + ECS (Recommended)",
            description="GitHub Actions builds Docker images, pushes to ECR, deploys to ECS with blue/green",
            when_to_use=[
                "Using GitHub for source control",
                "Want free CI/CD",
                "ECS Fargate or ECS on EC2 deployments",
                "Need zero-downtime deployments",
                "Don't need approval gates",
            ],
            when_not_to_use=[
                "Need manual approval gates (use CodePipeline)",
                "Need canary deployments (use CodePipeline + CodeDeploy)",
                "Enterprise compliance requirements",
            ],
            pros=[
                "Free CI/CD (GitHub Actions free tier)",
                "Zero-downtime blue/green deployments",
                "Fast rollback (revert task definition)",
                "Simple workflow",
                "Integrates well with ECR",
            ],
            cons=[
                "No built-in approval gates",
                "No canary deployments (all-at-once traffic shift)",
                "Manual rollback (not automatic)",
            ],
            monthly_cost_range=(0.0, 5.0),
            cost_drivers=[
                "GitHub Actions: $0/month (free tier)",
                "ECR: $0.10/GB/month (≈ $5/month for 50GB images)",
                "ECS: No deployment cost (pay for tasks)",
            ],
            soc2_controls=["CC8.1", "CC5.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="CodePipeline + CodeBuild + CodeDeploy",
            description="Full AWS-native pipeline with approval gates, canary deployments, and alarm-based rollback",
            when_to_use=[
                "Need manual approval gates",
                "Need canary deployments (10% → 50% → 100%)",
                "Want CloudWatch alarm-based automatic rollback",
                "Enterprise compliance requirements",
                "Multi-environment with strict controls",
            ],
            when_not_to_use=[
                "Cost-sensitive (adds $3-5/month)",
                "Simple deployment without approvals",
                "Using GitHub (GitHub Actions is simpler)",
            ],
            pros=[
                "Manual approval gates built-in",
                "Advanced traffic shifting (canary, linear)",
                "Automatic rollback on CloudWatch alarms",
                "Full audit trail in CloudTrail",
                "Deeper AWS integration",
            ],
            cons=[
                "More expensive ($3-5/month)",
                "More complex to set up",
                "Slower deployments (gradual traffic shift)",
            ],
            monthly_cost_range=(5.0, 15.0),
            cost_drivers=[
                "CodePipeline: $1/pipeline/month",
                "CodeBuild: $0.005/minute (≈ $2/month for 400 minutes)",
                "CodeDeploy: Free",
                "ECR: $5/month",
                "Example: $8/month total",
            ],
            soc2_controls=["CC8.1", "PI1.4", "CC5.3", "CC4.1"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF need_approval_gates OR need_canary_deployment:
        → CodePipeline + CodeDeploy ($8/month, enterprise features)

    ELSE:
        → GitHub Actions ($0/month, simple)

    **Deployment Strategies:**
    - GitHub Actions: Blue/green (instant traffic switch)
    - CodePipeline: Canary (10% → 50% → 100%) or Linear (10% every 10 minutes)

    **Cost Comparison:**
    - GitHub Actions: $0/month (free)
    - CodePipeline: $8/month (approval gates, canary, auto-rollback)

    **Recommendation:** Start with GitHub Actions. Add CodePipeline only if you need approval gates or canary deployments for production.
    """,
    soc2_relevance="""
    ECS deployments must be controlled and monitored:

    **CC8.1 (Change Management):** Automated deployments ensure tested code reaches production
    **CC5.3 (Policies):** Blue/green or canary deployments follow safe deployment procedures

    CodePipeline adds approval gates for **PI1.4 (Authorization)** controls.
    """,
    common_mistakes=[
        "Not using blue/green deployments (downtime during deploys)",
        "Not setting up CloudWatch alarms for deployment monitoring",
        "Not tagging Docker images with commit SHA (can't track what's deployed)",
        "Deploying directly to production without staging environment",
        "Not implementing rollback strategy (stuck with broken deployment)",
    ],
)

CICD_LAMBDA_DEPLOYMENT = ArchitectureDecision(
    question="How should I deploy Lambda functions?",
    options=[
        DecisionOption(
            name="GitHub Actions + Lambda (Simple)",
            description="GitHub Actions packages and deploys Lambda functions - fast and free",
            when_to_use=[
                "Simple Lambda functions",
                "Small teams",
                "Don't need traffic shifting",
                "Want fast deployments",
                "Cost-sensitive",
            ],
            when_not_to_use=[
                "Production APIs with significant traffic",
                "Need canary deployments",
                "Want automatic rollback on errors",
            ],
            pros=[
                "Simple and fast",
                "Free (GitHub Actions)",
                "Quick deployments (seconds)",
                "Easy rollback (update alias to previous version)",
            ],
            cons=[
                "All-at-once deployment (no traffic shifting)",
                "Manual rollback (not automatic)",
                "No gradual rollout",
            ],
            monthly_cost_range=(0.0, 0.0),
            cost_drivers=[
                "GitHub Actions: $0/month (free tier)",
                "Lambda: No deployment cost",
            ],
            soc2_controls=["CC8.1", "CC5.3"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="SAM + CodePipeline + CodeDeploy (Advanced)",
            description="AWS SAM with CodeDeploy for gradual traffic shifting and automatic rollback",
            when_to_use=[
                "Production Lambda APIs",
                "Need canary deployments (10% → 100%)",
                "Want automatic rollback on errors",
                "Using Infrastructure as Code (SAM/CloudFormation)",
            ],
            when_not_to_use=[
                "Simple Lambda functions (overkill)",
                "Development/staging only",
                "Don't need gradual rollout",
            ],
            pros=[
                "Gradual traffic shifting (canary, linear)",
                "Automatic rollback on CloudWatch alarms",
                "Infrastructure as Code (SAM templates)",
                "Pre and post-traffic hooks for validation",
            ],
            cons=[
                "More complex setup",
                "Slower deployments (10-30 minutes for gradual shift)",
                "Costs $1-5/month (CodePipeline)",
            ],
            monthly_cost_range=(1.0, 5.0),
            cost_drivers=[
                "CodePipeline: $1/pipeline/month",
                "CodeBuild: $0-2/month",
                "CodeDeploy: Free",
                "Example: $3/month",
            ],
            soc2_controls=["CC8.1", "CC5.3", "CC4.1"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF production_api AND traffic_volume > 10K_requests_per_day:
        → SAM + CodePipeline (canary, auto-rollback)

    ELSE:
        → GitHub Actions (simple, fast, free)

    **Deployment Strategies:**
    - GitHub Actions: All-at-once (instant switch)
    - SAM + CodeDeploy:
      * Canary10Percent30Minutes (10% for 30 min, then 100%)
      * Linear10PercentEvery10Minutes (gradual 10-minute increments)
      * AllAtOnce (instant, but with hooks)

    **Cost Comparison:**
    - GitHub Actions: $0/month
    - SAM + CodePipeline: $3/month

    **Recommendation:** Use GitHub Actions for most Lambda functions. Add SAM + CodeDeploy for production APIs that need safe, gradual rollouts.
    """,
    soc2_relevance="""
    Lambda deployments must be controlled:

    **CC8.1 (Change Management):** Automated deployments with testing
    **CC5.3 (Policies):** Canary deployments follow safe rollout procedures
    **CC4.1 (Ongoing Evaluations):** Automatic rollback validates deployments

    SAM + CodeDeploy provides stronger change management controls.
    """,
    common_mistakes=[
        "Not using Lambda versions and aliases (can't rollback)",
        "Deploying all traffic at once to production (risky)",
        "Not setting up CloudWatch alarms for error rates",
        "Not testing Lambda functions before deployment",
        "Forgetting to run smoke tests after deployment",
    ],
)

CICD_COMPLETE = ArchitectureDecision(
    question="What does a complete production CI/CD pipeline look like?",
    options=[
        DecisionOption(
            name="Full Production CI/CD Pipeline (Recommended)",
            description="Complete pipeline with automated testing, security scanning, approval gates, and safe deployments",
            when_to_use=[
                "All production applications",
                "SOC 2 compliance required",
                "Customer-facing services",
                "Want enterprise-grade deployments",
            ],
            when_not_to_use=[
                "Proof of concept",
                "Internal tools without security requirements",
                "Simple scripts or utilities",
            ],
            pros=[
                "Production-ready out of the box",
                "SOC 2 compliant",
                "Automated security scanning",
                "Safe deployments with rollback",
                "Complete audit trail",
                "Low cost ($5-20/month)",
            ],
            cons=[
                "More complex than simple deployments",
                "Requires discipline (don't skip approvals)",
                "Slower deployments (security scans + approvals)",
            ],
            monthly_cost_range=(5.0, 20.0),
            cost_drivers=[
                "GitHub Actions: $0-10/month (free tier usually sufficient)",
                "ECR: $5/month (container image storage)",
                "CodeDeploy: Free",
                "S3: $1/month (artifacts)",
                "CloudWatch: $3/month (logs and alarms)",
                "Example: $9/month for complete pipeline",
            ],
            soc2_controls=["CC8.1", "CC5.3", "PI1.4", "CC4.1", "CC6.8"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Complete Pipeline Components:**

    **1. Source Control (GitHub):**
    - Main branch protected (no direct commits)
    - Required PR reviews (1-2 approvers)
    - Status checks must pass
    - Signed commits enforced

    **2. CI Pipeline (GitHub Actions):**

    **Linting:**
    - ESLint, Pylint, Terraform fmt
    - Enforce code style

    **Unit Tests:**
    - Jest, pytest, Go test
    - Minimum 80% code coverage

    **Security Scanning:**
    - Dependency scanning (Dependabot, Snyk)
    - Secret scanning (GitHub native)
    - SAST (Semgrep, SonarCloud)
    - Container scanning (Trivy, ECR scanning)
    - Infrastructure scanning (Checkov for Terraform)

    **Build:**
    - Docker image or Lambda package
    - Tag with commit SHA
    - Push to ECR or S3

    **Integration Tests:**
    - Test against staging environment
    - API tests, end-to-end tests

    **3. CD Pipeline (Multi-Environment):**

    **Dev Environment:**
    - Auto-deploy on merge to main
    - No approval needed
    - All-at-once deployment
    - Smoke tests after deploy

    **Staging Environment:**
    - Auto-deploy after successful dev
    - Full integration test suite
    - Load testing (optional)

    **Production Environment:**
    - Manual approval required (security/QA team)
    - Canary deployment:
      * 10% traffic for 10 minutes
      * 50% traffic for 10 minutes
      * 100% traffic
    - CloudWatch alarms monitoring:
      * Error rate > 1%
      * Latency p99 > 1 second
      * Custom business metrics
    - Automatic rollback on alarm
    - Post-deployment smoke tests

    **4. Deployment Strategies:**
    - **ECS Fargate:** Blue/green via ECS deployment controller
    - **Lambda:** CodeDeploy canary (SAM)
    - **Static sites:** S3 + CloudFront invalidation

    **5. Security:**
    - OIDC to AWS (no long-lived credentials)
    - IAM roles per environment (deploy-dev, deploy-staging, deploy-prod)
    - Secrets in GitHub Secrets + AWS Secrets Manager
    - Least privilege IAM policies
    - Audit log in GitHub + CloudTrail

    **6. Monitoring & Notifications:**
    - CloudWatch dashboards per environment
    - Deployment success/failure metrics
    - Build duration tracking
    - SNS notifications to Slack:
      * Build failures
      * Deployment started/completed/failed
      * Rollback triggered
      * Security vulnerabilities found

    **Cost:** $5-20/month for complete production pipeline
    """,
    soc2_relevance="""
    This pipeline addresses all critical SOC 2 change management controls:

    **CC8.1 (Change Management):**
    - All changes go through automated pipeline
    - Testing ensures changes don't break system
    - Approval gates enforce authorization
    - Audit trail tracks all deployments

    **CC5.3 (Policies and Procedures):**
    - Pipeline enforces documented procedures
    - Infrastructure as Code (IaC)
    - Automated, repeatable deployments

    **PI1.4 (Authorization):**
    - Manual approvals for production changes
    - IAM roles enforce least privilege
    - Signed commits enforce identity

    **CC4.1 (Ongoing Evaluations):**
    - Automated tests continuously validate quality
    - Security scans detect vulnerabilities
    - Integration tests validate system health

    **CC6.8 (Malware Protection):**
    - Dependency scanning detects vulnerable libraries
    - Container scanning detects malicious images
    - SAST detects code vulnerabilities

    This is the gold standard for SOC 2 compliant CI/CD.
    """,
    common_mistakes=[
        "Skipping security scanning (missing vulnerabilities in production)",
        "No approval gates for production (unauthorized changes)",
        "All-at-once production deploys (risky, no gradual rollout)",
        "Not setting up automatic rollback (stuck with broken deployment)",
        "Storing AWS credentials in GitHub Secrets (use OIDC)",
        "No branch protection (allow direct commits to main)",
        "Skipping integration tests (unit tests don't catch everything)",
        "No monitoring/alerting (don't know when deployments fail)",
    ],
)

# Export patterns
PATTERNS = [
    CICD_GITHUB_ACTIONS,
    CICD_ECS_DEPLOYMENT,
    CICD_LAMBDA_DEPLOYMENT,
    CICD_COMPLETE
]
