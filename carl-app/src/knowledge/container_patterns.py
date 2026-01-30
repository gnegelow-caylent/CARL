"""
Container and Load Balancer Patterns for AWS.

Patterns for ALB, ECS, EKS, and Fargate containerized applications.
"""

from knowledge.architecture_patterns import ArchitectureDecision

ALB_APPLICATION = ArchitectureDecision(
    name="Application Load Balancer for Web Applications",
    context="""
    Need load balancing for web application with:
    - HTTP/HTTPS traffic
    - Path-based or host-based routing
    - SSL termination
    - Auto-scaling targets
    - Health checks
    """,
    options={
        "ALB + EC2 Auto Scaling Group": """
        **Architecture:**
        - Application Load Balancer (public subnet)
        - EC2 instances in Auto Scaling Group (private subnet)
        - Target Group with health checks
        - ACM certificate for HTTPS
        - Security groups (least privilege)

        **Features:**
        - Layer 7 (HTTP/HTTPS) load balancing
        - Path-based routing (/api → backend, /admin → admin servers)
        - Host-based routing (api.example.com → API servers)
        - Sticky sessions
        - WebSocket support
        - HTTP/2 and gRPC support

        **Cost:** approx. $16/month + $0.008/LCU-hour + EC2 costs
        - ALB: approx. $16/month base
        - LCU: approx. $0.008/hour (Load Balancer Capacity Unit)
        - EC2: Depends on instance types (t3.medium = approx. $30/month each)
        - Example: ALB + 2 t3.medium = approx. $76/month

        **Pros:**
        - Advanced routing
        - WebSocket support
        - Integrated with Auto Scaling
        - Native AWS service

        **Cons:**
        - More expensive than NLB for simple cases
        - Not for TCP/UDP (use NLB)

        **When to use:** Web applications, microservices, HTTP/HTTPS traffic
        """,

        "ALB + ECS/Fargate": """
        **Architecture:**
        - Application Load Balancer
        - ECS Fargate tasks (serverless containers)
        - Target Group (dynamic port mapping)
        - Service Auto Scaling

        **Features:**
        - Serverless containers (no EC2 management)
        - Dynamic port mapping
        - Blue/green deployments
        - Faster scaling than EC2

        **Cost:** approx. $16/month (ALB) + Fargate costs
        - ALB: approx. $16/month
        - Fargate: approx. $0.04/vCPU-hour + $0.004/GB-hour
        - Example: 0.25 vCPU, 0.5GB = approx. $10/month per task

        **Pros:**
        - No EC2 management
        - Pay per use (can scale to zero)
        - Fast deployment
        - Better for microservices

        **Cons:**
        - More expensive per compute hour than EC2
        - Cold start for scaling

        **When to use:** Microservices, containerized apps, want serverless
        """,

        "ALB + Lambda": """
        **Architecture:**
        - ALB with Lambda targets
        - Lambda functions handle requests
        - Path-based routing to different functions

        **Cost:** approx. $16/month (ALB) + Lambda costs
        - Cheaper than API Gateway REST API for high traffic

        **When to use:** Very high traffic APIs (>10M requests/month where ALB becomes cheaper than API Gateway)
        """
    },
    recommendation="ALB + ECS Fargate for containerized apps, ALB + EC2 for traditional apps",
    tradeoffs="""
    **ALB + EC2 vs ALB + Fargate:**
    - EC2: Cheaper at scale, more control, requires management
    - Fargate: Easier, serverless, more expensive per hour

    **ALB vs API Gateway:**
    - ALB: Better for containers, always-on cost, WebSockets
    - API Gateway: Better for serverless, pay-per-request, simpler

    **Break-even:** API Gateway vs ALB at approx. 5-10M requests/month
    """,
    related_controls=["CC6.1", "A1.2", "CC7.2"],
    aws_services=["elasticloadbalancing", "ec2", "autoscaling", "acm", "waf"],
    estimated_cost="$16-100/month depending on compute"
)

ECS_FARGATE = ArchitectureDecision(
    name="ECS Fargate Containerized Applications",
    context="""
    Need to run containerized applications with:
    - No server management
    - Auto-scaling
    - Service discovery
    - Load balancing
    - CI/CD integration
    """,
    options={
        "ECS Fargate (Recommended for Most Containers)": """
        **Architecture:**
        - ECS Cluster
        - Fargate tasks (serverless containers)
        - ALB for load balancing
        - ECR for container registry
        - CloudWatch Logs
        - Service Auto Scaling
        - VPC with private subnets

        **Features:**
        - Serverless (no EC2 to manage)
        - Task-level isolation
        - Service discovery
        - Blue/green deployments
        - Integration with AWS services

        **Cost:** approx. $0.04/vCPU-hour + $0.004/GB-hour
        - 0.25 vCPU, 0.5GB = approx. $10/month (24/7)
        - 1 vCPU, 2GB = approx. $50/month (24/7)
        - Can scale to zero for dev/test

        **Pros:**
        - No EC2 management
        - Task-level security
        - Fast deployment
        - Pay per task
        - Easier than EC2-based ECS

        **Cons:**
        - More expensive than ECS on EC2 at scale
        - 4GB RAM minimum per task (use EC2 for smaller)
        - No persistent storage (use EFS)

        **When to use:** Most containerized apps, microservices, want serverless
        """,

        "ECS on EC2": """
        **Architecture:**
        - ECS Cluster
        - EC2 instances (container hosts)
        - ECS agent
        - Multiple tasks per instance
        - Capacity Providers

        **Features:**
        - More control over instances
        - Can use Spot instances (savings)
        - Persistent storage
        - GPU support

        **Cost:** approx. $30/month per t3.medium (24/7)
        - Cheaper per compute hour than Fargate
        - Must pay for full instances even if not fully utilized

        **Pros:**
        - Cheaper at high utilization
        - More control
        - Spot instance support (70% savings)
        - GPU workloads

        **Cons:**
        - Must manage EC2 instances
        - More complex
        - Slower scaling

        **When to use:** High utilization (>70%), need Spot instances, GPU workloads
        """,

        "Lambda (For Simple Cases)": """
        **Architecture:**
        - Lambda with container image support
        - Up to 10GB container images
        - 15-minute timeout

        **Cost:** approx. $0.20/million invocations
        - Much cheaper for sporadic workloads

        **Pros:**
        - True serverless
        - Pay per invocation
        - No always-on costs

        **Cons:**
        - 15-min timeout
        - Cold starts
        - 10GB image limit

        **When to use:** Batch jobs, event-driven processing, short-running tasks
        """
    },
    recommendation="ECS Fargate for most containerized applications",
    tradeoffs="""
    **Fargate vs ECS on EC2:**
    - Fargate: Easier, serverless, approx. $50/mo per 1vCPU/2GB task
    - EC2: Cheaper at scale, more control, approx. $30/mo per t3.medium (can run multiple tasks)

    **Break-even:** Fargate cheaper than EC2 when utilization <50%

    **Fargate vs Lambda:**
    - Fargate: Long-running, HTTP servers, always-on
    - Lambda: Event-driven, batch jobs, sporadic

    **Start with Fargate**, optimize to EC2 if needed
    """,
    related_controls=["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
    aws_services=["ecs", "ecr", "elasticloadbalancing", "cloudwatch", "secretsmanager"],
    estimated_cost="$50-200/month for small app"
)

ECS_COMPLETE = ArchitectureDecision(
    name="Complete Production ECS Fargate Application",
    context="""
    Production containerized application with all best practices:
    - Load balancing
    - Auto-scaling
    - Service discovery
    - CI/CD
    - Monitoring and alerting
    - Security (encryption, secrets)
    - SOC 2 compliant
    """,
    options={
        "Full Stack ECS Fargate (Recommended)": """
        **Complete Architecture:**

        **Compute:**
        - ECS Cluster with Fargate
        - ECS Services (one per microservice)
        - Task definitions (container specs)
        - Service Auto Scaling (target tracking)
        - VPC with private subnets (no public IPs on tasks)

        **Load Balancing:**
        - Application Load Balancer (public subnet)
        - Target Groups (health checks)
        - ACM certificate (HTTPS)
        - WAF (rate limiting, threat protection)

        **Container Registry:**
        - ECR (private Docker registry)
        - Image scanning (vulnerabilities)
        - Lifecycle policies (cleanup old images)
        - Encryption at rest

        **Security:**
        - IAM roles for tasks (least privilege)
        - Secrets Manager (database passwords, API keys)
        - Parameter Store (configuration)
        - Security groups (task-level)
        - VPC endpoints (private AWS API access)
        - Encryption at rest (EFS, ECR)
        - Encryption in transit (TLS, HTTPS)

        **Monitoring:**
        - CloudWatch Logs (centralized)
        - CloudWatch Container Insights (resource metrics)
        - X-Ray (distributed tracing)
        - CloudWatch Alarms:
          * CPU utilization > 80%
          * Memory utilization > 80%
          * Target response time > 1s
          * 5xx errors > 1%
          * Task count < minimum
        - SNS notifications

        **CI/CD:**
        - CodePipeline or GitHub Actions
        - CodeBuild (build Docker images)
        - Push to ECR
        - Blue/green deployment (ECS deployment controller)
        - Automated rollback on alarm

        **Data:**
        - RDS or Aurora (database)
        - ElastiCache (caching)
        - S3 (file storage)
        - EFS (shared persistent storage, if needed)

        **SOC 2 Controls Addressed:**
        - CC6.1: Access controls (IAM, security groups)
        - CC6.7: Encryption (TLS, KMS, Secrets Manager)
        - CC7.1: Threat detection (WAF, vulnerability scanning)
        - CC7.2: System monitoring (CloudWatch, X-Ray)
        - CC8.1: Change management (CI/CD, blue/green)
        - A1.2: Availability (Auto Scaling, Multi-AZ ALB)

        **Cost Breakdown:** approx. $150-400/month
        - ALB: $16/month
        - Fargate tasks: $50-200/month (depends on size/count)
        - RDS: $30-100/month (db.t3.micro to db.t3.small)
        - ECR: $0.10/GB/month (approx. $5/month)
        - CloudWatch: $10-20/month
        - WAF: $10/month
        - VPC endpoints: $7.50/month per endpoint (optional)
        - X-Ray: $5/month

        **Terraform Modules Needed:**
        - VPC with public/private subnets
        - ALB with HTTPS listener and ACM certificate
        - ECS cluster
        - ECS task definitions (with secrets)
        - ECS services with auto-scaling
        - IAM roles for tasks
        - ECR repository with scanning
        - Security groups (ALB, tasks, RDS)
        - RDS instance
        - Secrets Manager secrets
        - CloudWatch log groups and alarms
        - WAF WebACL
        - X-Ray sampling rules
        - CodePipeline (optional)

        **Pros:**
        - Production-ready
        - SOC 2 compliant
        - Serverless containers
        - Auto-scaling
        - Blue/green deployments

        **Cons:**
        - More complex than Lambda
        - Higher cost than EC2-based ECS

        **When to use:** All production containerized applications
        """
    },
    recommendation="Full stack with ALB, Fargate, monitoring, and CI/CD",
    tradeoffs="No tradeoffs - this is the complete, production-ready setup",
    related_controls=["CC6.1", "CC6.7", "CC7.1", "CC7.2", "CC8.1", "A1.2"],
    aws_services=["ecs", "ecr", "elasticloadbalancing", "waf", "rds", "elasticache", "cloudwatch", "xray", "secretsmanager", "codepipeline"],
    estimated_cost="$150-400/month"
)

EKS_KUBERNETES = ArchitectureDecision(
    name="EKS Kubernetes Cluster",
    context="""
    Need Kubernetes with:
    - Container orchestration at scale
    - Multi-tenant workloads
    - Advanced networking (service mesh)
    - Existing Kubernetes workloads to migrate
    - GitOps workflows
    """,
    options={
        "EKS with Fargate (Serverless Kubernetes)": """
        **Architecture:**
        - EKS control plane (managed)
        - Fargate profiles (serverless nodes)
        - ALB Ingress Controller
        - ECR for images
        - VPC with private subnets

        **Features:**
        - Serverless nodes (no EC2)
        - Pay per pod
        - Managed control plane
        - Kubernetes 1.28+

        **Cost:** approx. $72/month + pod costs
        - EKS control plane: $0.10/hour = approx. $72/month
        - Fargate pods: approx. $0.04/vCPU-hour + $0.004/GB-hour
        - Example: 3 pods (0.25vCPU, 0.5GB each) = approx. $100/month total

        **Pros:**
        - No node management
        - Pay per pod
        - Secure (pod-level isolation)

        **Cons:**
        - More expensive than ECS Fargate
        - Longer pod startup time
        - Limited Kubernetes features (no DaemonSets on Fargate)

        **When to use:** Need Kubernetes but want serverless nodes
        """,

        "EKS with EC2 Node Groups": """
        **Architecture:**
        - EKS control plane
        - EC2 node groups (managed or self-managed)
        - Cluster Autoscaler or Karpenter
        - VPC CNI for networking

        **Features:**
        - Full Kubernetes support
        - Spot instance support
        - GPU support
        - DaemonSets, HostPath, etc.

        **Cost:** approx. $72/month + EC2 costs
        - EKS control plane: approx. $72/month
        - EC2 nodes: approx. $30/month per t3.medium
        - Example: 2 t3.medium nodes = approx. $132/month total

        **Pros:**
        - Full Kubernetes features
        - Cheaper per compute hour
        - Spot instance support (70% savings)
        - More control

        **Cons:**
        - Must manage nodes
        - More complex

        **When to use:** Standard Kubernetes workloads, need full features
        """,

        "ECS Fargate (Simpler Alternative)": """
        **Cost:** approx. $50/month (no control plane cost)

        **When to consider ECS instead:**
        - Don't need Kubernetes features
        - Want simpler operations
        - Save $72/month on control plane

        **ECS is often sufficient** unless you specifically need:
        - Kubernetes ecosystem (Helm, operators)
        - Multi-cloud portability
        - Advanced networking (service mesh)
        """
    },
    recommendation="ECS Fargate unless you specifically need Kubernetes",
    tradeoffs="""
    **EKS vs ECS:**
    - EKS: Kubernetes ecosystem, $72/mo control plane, more complex
    - ECS: AWS-native, no control plane cost, simpler

    **When to use EKS:**
    - Migrating from on-prem Kubernetes
    - Need Helm charts, operators
    - Multi-cloud strategy
    - Team has Kubernetes expertise

    **When to use ECS:**
    - New to containers
    - AWS-only
    - Want simplicity
    - Save $72/month

    **Default choice:** Start with ECS Fargate, only use EKS if you need Kubernetes features
    """,
    related_controls=["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
    aws_services=["eks", "ec2", "ecr", "elasticloadbalancing", "cloudwatch"],
    estimated_cost="$130-500/month"
)

# Export patterns
PATTERNS = [
    ALB_APPLICATION,
    ECS_FARGATE,
    ECS_COMPLETE,
    EKS_KUBERNETES
]
