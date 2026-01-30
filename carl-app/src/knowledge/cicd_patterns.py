"""
CI/CD Pipeline Patterns for AWS.

Patterns for CodePipeline, CodeBuild, CodeDeploy, and GitHub Actions with AWS integration.
"""

from knowledge.architecture_patterns import ArchitectureDecision

CICD_GITHUB_ACTIONS = ArchitectureDecision(
    name="GitHub Actions with AWS Deployment",
    context="""
    Need CI/CD pipeline with:
    - Git-based workflow
    - Automated testing
    - AWS deployment
    - Pull request previews
    - Low cost
    """,
    options={
        "GitHub Actions + OIDC to AWS (Recommended)": """
        **Architecture:**
        - GitHub repository
        - GitHub Actions workflows
        - OpenID Connect (OIDC) to AWS (no long-lived credentials)
        - Deploy to Lambda, ECS, S3, etc.
        - CloudWatch for deployment logs

        **Features:**
        - No AWS credentials in GitHub (OIDC)
        - Parallel jobs
        - Matrix builds
        - Reusable workflows
        - GitHub-hosted runners (free)

        **Cost:** approx. $0/month (free tier)
        - Free for public repos
        - 2,000 minutes/month free for private repos
        - Self-hosted runners: free (use EC2)

        **Example Workflow:**
        1. Push to main branch
        2. GitHub Actions triggers
        3. Run tests (Jest, pytest, etc.)
        4. Build artifacts (Docker image, Lambda zip)
        5. Assume AWS role via OIDC
        6. Deploy to AWS (update Lambda, push to ECR, etc.)
        7. Run smoke tests
        8. Notify Slack on success/failure

        **Pros:**
        - Free (within limits)
        - No AWS credentials to manage
        - Fast builds
        - Great for open source
        - Huge marketplace of actions

        **Cons:**
        - Dependent on GitHub
        - 6-hour job limit
        - Less integration with AWS than CodePipeline

        **When to use:** Most projects, GitHub-hosted, want free/cheap CI/CD
        """,

        "GitHub Actions + Self-Hosted Runners": """
        **Architecture:**
        - GitHub Actions
        - EC2 self-hosted runners (or ECS tasks)
        - VPC access (can access private RDS, etc.)

        **Cost:** approx. $10-30/month (EC2 t3.micro or t3.small)

        **Pros:**
        - Unlimited minutes
        - VPC access
        - Faster (no download time)
        - Custom software/tools

        **Cons:**
        - Must manage runners
        - Security concerns (third-party code on your EC2)

        **When to use:** High build volume, need VPC access, hitting GitHub minute limits
        """
    },
    recommendation="GitHub Actions + OIDC (free, secure, simple)",
    tradeoffs="""
    **GitHub Actions vs CodePipeline:**
    - GitHub Actions: Free/cheap, GitHub ecosystem, OIDC auth
    - CodePipeline: More AWS-native, $1/pipeline/month, deeper AWS integration

    **GitHub-hosted vs Self-hosted:**
    - GitHub-hosted: Free (within limits), zero management
    - Self-hosted: Unlimited, VPC access, requires EC2 management

    **Default choice:** GitHub Actions with OIDC (free, secure)
    """,
    related_controls=["CC8.1", "PI1.4", "CC5.3"],
    aws_services=["iam", "lambda", "ecs", "s3", "cloudwatch"],
    estimated_cost="$0/month (free tier)"
)

CICD_CODEPIPELINE = ArchitectureDecision(
    name="AWS CodePipeline Full CI/CD",
    context="""
    Need AWS-native CI/CD with:
    - Multiple environments (dev, staging, prod)
    - Manual approval steps
    - Blue/green deployments
    - Integration with AWS services
    - Audit trail
    """,
    options={
        "CodePipeline + CodeBuild + CodeDeploy (AWS-Native)": """
        **Architecture:**
        - CodePipeline (orchestration)
        - CodeCommit or GitHub (source)
        - CodeBuild (build/test)
        - CodeDeploy (deployment)
        - S3 (artifact storage)
        - SNS (notifications)
        - CloudWatch (logs, metrics)

        **Features:**
        - Multi-stage pipeline (dev → staging → prod)
        - Manual approval gates
        - Blue/green deployments
        - Canary deployments
        - Rollback on CloudWatch alarm
        - IAM integration

        **Cost:** approx. $1/pipeline/month + build minutes
        - CodePipeline: $1/active pipeline/month
        - CodeBuild: $0.005/build minute (100 free/month)
        - CodeDeploy: Free
        - Example: 1 pipeline, 100 builds/month at 5 min = approx. $3.50/month

        **Pipeline Stages:**
        1. Source: CodeCommit or GitHub webhook
        2. Build: CodeBuild compiles, runs tests, builds Docker image
        3. Test: CodeBuild runs integration tests
        4. Deploy to Dev: CodeDeploy blue/green
        5. Manual Approval: Security/QA approval
        6. Deploy to Prod: CodeDeploy with canary (10% → 100%)
        7. Notify: SNS to Slack

        **Pros:**
        - Native AWS integration
        - Manual approval gates
        - Advanced deployment strategies
        - CloudWatch alarm rollback
        - Audit trail in CloudTrail

        **Cons:**
        - More expensive than GitHub Actions
        - Less community actions
        - Tied to AWS

        **When to use:** AWS-centric teams, need approval gates, compliance audit trail
        """,

        "CodePipeline + Jenkins": """
        **Architecture:**
        - CodePipeline orchestration
        - Jenkins on EC2 (build server)
        - CodeDeploy for deployment

        **Cost:** approx. $30/month (EC2 for Jenkins)

        **When to use:** Existing Jenkins pipelines, complex build requirements
        """
    },
    recommendation="GitHub Actions for most projects, CodePipeline for enterprise/compliance",
    tradeoffs="""
    **CodePipeline vs GitHub Actions:**
    - CodePipeline: $1-5/mo, approval gates, AWS-native, audit trail
    - GitHub Actions: Free, faster, community actions, less AWS integration

    **When to use CodePipeline:**
    - Need manual approval gates (QA/security sign-off)
    - Multi-environment with different permissions
    - Compliance audit trail important
    - Already all-in on AWS

    **When to use GitHub Actions:**
    - Cost-conscious
    - GitHub-hosted
    - Don't need approval gates
    """,
    related_controls=["CC8.1", "PI1.4", "CC5.3", "CC4.1"],
    aws_services=["codepipeline", "codebuild", "codedeploy", "s3", "cloudwatch", "sns"],
    estimated_cost="$1-10/month"
)

CICD_ECS_DEPLOYMENT = ArchitectureDecision(
    name="CI/CD for ECS Fargate Applications",
    context="""
    Need to deploy containerized apps to ECS with:
    - Automated Docker image builds
    - Blue/green deployments
    - Rollback on failure
    - Zero-downtime deployments
    """,
    options={
        "GitHub Actions + ECR + ECS (Recommended)": """
        **Architecture:**
        - GitHub repository with Dockerfile
        - GitHub Actions workflow
        - Amazon ECR (container registry)
        - ECS Fargate cluster
        - Application Load Balancer
        - Blue/green deployment

        **Workflow:**
        1. Push to main branch
        2. GitHub Actions builds Docker image
        3. Run tests in container
        4. Push image to ECR (with tag: commit SHA)
        5. Update ECS task definition (new image)
        6. ECS deploys new tasks (blue/green)
        7. ALB shifts traffic gradually
        8. CloudWatch monitors for errors
        9. Auto-rollback on alarm

        **Cost:** approx. $0/month (GitHub Actions) + ECR storage
        - GitHub Actions: Free (within limits)
        - ECR: $0.10/GB/month (approx. $5/month for 50GB)

        **Pros:**
        - Zero-downtime deployments
        - Fast rollback
        - Free CI/CD
        - Simple workflow

        **Cons:**
        - No built-in approval gates (can add manually)

        **When to use:** Most ECS Fargate deployments
        """,

        "CodePipeline + CodeBuild + ECR + ECS": """
        **Architecture:**
        - CodePipeline orchestration
        - CodeBuild (Docker build)
        - ECR registry
        - ECS blue/green deployment controller
        - CodeDeploy for traffic shifting

        **Features:**
        - Manual approval before prod
        - Canary deployments (10% → 50% → 100%)
        - CloudWatch alarm rollback

        **Cost:** approx. $3-5/month

        **Pros:**
        - Approval gates
        - Advanced traffic shifting
        - Alarm-based rollback

        **Cons:**
        - More expensive
        - More complex

        **When to use:** Enterprise, need approval gates, advanced deployment strategies
        """
    },
    recommendation="GitHub Actions for most teams, CodePipeline for enterprise",
    tradeoffs="""
    **GitHub Actions vs CodePipeline for ECS:**
    - GitHub Actions: Free, simple, fast
    - CodePipeline: Approval gates, canary, $3-5/mo

    Both support blue/green deployments and rollback
    """,
    related_controls=["CC8.1", "CC5.3"],
    aws_services=["ecr", "ecs", "elasticloadbalancing", "codepipeline", "codebuild"],
    estimated_cost="$0-5/month"
)

CICD_LAMBDA_DEPLOYMENT = ArchitectureDecision(
    name="CI/CD for Lambda Functions",
    context="""
    Need to deploy Lambda functions with:
    - Automated testing
    - Versioning and aliases
    - Canary deployments
    - Rollback capability
    """,
    options={
        "GitHub Actions + Lambda (Simple)": """
        **Architecture:**
        - GitHub repository
        - GitHub Actions workflow
        - AWS Lambda
        - Lambda versions + aliases

        **Workflow:**
        1. Push to main
        2. Run unit tests
        3. Package Lambda code (zip)
        4. Update Lambda function code
        5. Publish new version
        6. Update alias (prod → v123)
        7. Run smoke tests

        **Cost:** $0/month (GitHub Actions free tier)

        **Pros:**
        - Simple
        - Free
        - Fast deployments

        **Cons:**
        - No traffic shifting
        - Manual rollback

        **When to use:** Simple Lambda functions, small teams
        """,

        "SAM + CodePipeline (Advanced)": """
        **Architecture:**
        - SAM template (Infrastructure as Code)
        - CodePipeline + CodeBuild
        - CodeDeploy for Lambda (traffic shifting)
        - CloudWatch alarms (auto-rollback)

        **Features:**
        - Canary deployments (10% → 100%)
        - Linear traffic shifting (10% every 10 minutes)
        - Automatic rollback on alarms

        **Deployment Types:**
        - Canary10Percent30Minutes
        - Linear10PercentEvery10Minutes
        - AllAtOnce

        **Cost:** approx. $1-5/month

        **Pros:**
        - Advanced traffic shifting
        - Auto-rollback on errors
        - Infrastructure as Code

        **Cons:**
        - More complex
        - Slower deployments

        **When to use:** Production Lambda APIs, need gradual rollout
        """
    },
    recommendation="GitHub Actions for simple, SAM + CodePipeline for production",
    tradeoffs="""
    **Simple vs Advanced Lambda Deployment:**
    - GitHub Actions: Fast, free, all-at-once deploy
    - SAM + CodePipeline: Gradual, safe, auto-rollback, $1-5/mo

    **When to use advanced:**
    - Production APIs with traffic
    - Need canary deployments
    - Want automatic rollback
    """,
    related_controls=["CC8.1", "CC5.3"],
    aws_services=["lambda", "codepipeline", "codedeploy", "cloudwatch", "sam"],
    estimated_cost="$0-5/month"
)

CICD_COMPLETE = ArchitectureDecision(
    name="Complete Production CI/CD Pipeline",
    context="""
    Production CI/CD with all best practices:
    - Automated testing (unit, integration, security)
    - Multi-environment (dev, staging, prod)
    - Manual approval gates
    - Blue/green or canary deployments
    - Automated rollback
    - Security scanning
    - Audit trail
    - SOC 2 compliant
    """,
    options={
        "Full Stack CI/CD (Recommended)": """
        **Complete Architecture:**

        **Source Control:**
        - GitHub repository (main branch protected)
        - Branch protection rules
        - Required PR reviews
        - Status checks must pass

        **CI Pipeline (GitHub Actions):**
        1. **Linting:** ESLint, Pylint, Terraform fmt
        2. **Unit Tests:** Jest, pytest, Go test
        3. **Security Scanning:**
           - Dependency scanning (Dependabot)
           - Secret scanning (GitHub native)
           - SAST (Semgrep, SonarCloud)
           - Container scanning (Trivy)
        4. **Build:** Docker image or Lambda zip
        5. **Integration Tests:** Against test environment

        **CD Pipeline:**

        **Dev Environment (Auto-Deploy):**
        - Deploys on merge to main
        - No approval needed
        - All-at-once deployment
        - Smoke tests after deploy

        **Staging Environment (Auto-Deploy):**
        - Deploys after successful dev
        - Runs full integration test suite
        - Load testing (optional)

        **Production Environment (Manual Approval + Canary):**
        - Manual approval required (security/QA)
        - Canary deployment (10% → 50% → 100%)
        - CloudWatch alarms monitoring:
          * Error rate
          * Latency p99
          * Custom metrics
        - Automatic rollback on alarm
        - Post-deployment smoke tests

        **Deployment Strategies by Service:**
        - **ECS Fargate:** Blue/green via ECS deployment controller
        - **Lambda:** CodeDeploy canary (SAM)
        - **Static site:** S3 + CloudFront invalidation

        **Security:**
        - OIDC to AWS (no long-lived credentials)
        - IAM roles per environment
        - Secrets in GitHub Secrets + AWS Secrets Manager
        - Signed commits required
        - Audit log in GitHub + CloudTrail

        **Monitoring:**
        - CloudWatch dashboards per environment
        - Deployment success/failure metrics
        - Build duration tracking
        - SNS notifications to Slack:
          * Build failures
          * Deployment started/completed
          * Rollback triggered

        **SOC 2 Controls Addressed:**
        - CC8.1: Change management (automated pipeline, approval gates)
        - CC5.3: Policies and procedures (IaC, documented pipeline)
        - PI1.4: Authorization (manual approvals, IAM roles)
        - CC4.1: Ongoing evaluations (automated tests)
        - CC6.8: Malware protection (security scanning)

        **Cost Breakdown:** approx. $5-20/month
        - GitHub Actions: $0-10/month (free tier usually sufficient)
        - ECR: $5/month (container storage)
        - CodeDeploy: Free
        - S3: $1/month (artifacts)
        - CloudWatch: $3/month (logs, alarms)

        **Terraform Modules Needed:**
        - IAM OIDC provider for GitHub
        - IAM roles per environment (deploy-dev, deploy-prod)
        - ECR repository with lifecycle policies
        - CodeDeploy application (for Lambda canary)
        - CloudWatch alarms (for rollback)
        - SNS topics (notifications)
        - S3 bucket (artifacts, encrypted)

        **Pros:**
        - Production-ready
        - SOC 2 compliant
        - Automated security scanning
        - Safe deployments (canary)
        - Audit trail
        - Low cost

        **Cons:**
        - Requires discipline (don't skip approvals)

        **When to use:** All production applications
        """
    },
    recommendation="Full stack with automated testing, security scanning, and canary deployments",
    tradeoffs="No tradeoffs - this is the complete, production-ready setup",
    related_controls=["CC8.1", "CC5.3", "PI1.4", "CC4.1", "CC6.8"],
    aws_services=["iam", "ecr", "ecs", "lambda", "codedeploy", "cloudwatch", "sns", "s3"],
    estimated_cost="$5-20/month"
)

# Export patterns
PATTERNS = [
    CICD_GITHUB_ACTIONS,
    CICD_CODEPIPELINE,
    CICD_ECS_DEPLOYMENT,
    CICD_LAMBDA_DEPLOYMENT,
    CICD_COMPLETE
]
