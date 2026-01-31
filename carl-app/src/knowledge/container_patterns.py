"""
Container and Load Balancer Patterns for AWS.

Patterns for ALB, ECS, EKS, and Fargate containerized applications.
"""

from knowledge.architecture_patterns import ArchitectureDecision, DecisionOption

ALB_APPLICATION = ArchitectureDecision(
    question="What load balancer should I use for my web application?",
    options=[
        DecisionOption(
            name="ALB + ECS Fargate (Recommended for Containers)",
            description="Application Load Balancer with serverless Fargate containers - no EC2 management",
            when_to_use=[
                "Containerized microservices",
                "Want serverless containers (no EC2 management)",
                "Need path-based or host-based routing",
                "Blue/green deployments required",
                "Dynamic port mapping needed",
            ],
            when_not_to_use=[
                "Non-containerized applications",
                "Need TCP/UDP load balancing (use NLB)",
                "Budget < $30/month (consider Lambda)",
            ],
            pros=[
                "No EC2 management (serverless)",
                "Fast scaling",
                "Dynamic port mapping",
                "Blue/green deployments built-in",
                "Pay per task",
                "Layer 7 routing (path, host, headers)",
            ],
            cons=[
                "More expensive than EC2 per compute hour",
                "ALB always-on cost ($16/month minimum)",
                "Cold start when scaling from zero",
            ],
            monthly_cost_range=(30.0, 150.0),
            cost_drivers=[
                "ALB: $16/month base cost",
                "LCU (Load Balancer Capacity Units): $0.008/hour",
                "Fargate tasks: $0.04/vCPU-hour + $0.004/GB-hour",
                "Example: ALB + 2 tasks (0.25 vCPU, 0.5GB) = $36/month",
            ],
            soc2_controls=["CC6.1", "A1.2", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
        DecisionOption(
            name="ALB + EC2 Auto Scaling Group",
            description="Application Load Balancer with EC2 instances - more control, cheaper at scale",
            when_to_use=[
                "Traditional web applications (not containerized)",
                "High utilization workloads (>70% CPU/memory)",
                "Need full control over OS and instances",
                "Existing EC2-based application",
            ],
            when_not_to_use=[
                "Want serverless (use Fargate or Lambda)",
                "Low utilization (<50%)",
                "Microservices architecture (containers are better)",
            ],
            pros=[
                "Cheaper at high utilization",
                "Full control over instances",
                "Can use Spot instances (70% savings)",
                "Persistent local storage",
            ],
            cons=[
                "Must manage EC2 instances (patching, monitoring)",
                "Slower scaling than containers",
                "More operational overhead",
                "Pay for full instances even when idle",
            ],
            monthly_cost_range=(76.0, 200.0),
            cost_drivers=[
                "ALB: $16/month",
                "EC2: t3.medium ≈ $30/month per instance",
                "Example: ALB + 2 t3.medium = $76/month",
            ],
            soc2_controls=["CC6.1", "A1.2", "CC7.2"],
            implementation_complexity="medium",
            operational_overhead="high",
        ),
        DecisionOption(
            name="ALB + Lambda",
            description="Application Load Balancer with Lambda functions - for very high traffic APIs",
            when_to_use=[
                "Very high traffic APIs (>10M requests/month)",
                "Break-even with API Gateway pricing",
                "Need WebSocket support with serverless",
            ],
            when_not_to_use=[
                "Low traffic (<5M requests/month - API Gateway is cheaper)",
                "Standard REST APIs (use API Gateway HTTP API)",
            ],
            pros=[
                "Cheaper than API Gateway at very high traffic",
                "WebSocket support",
                "Serverless (no containers to manage)",
            ],
            cons=[
                "ALB always-on cost ($16/month)",
                "15-minute Lambda timeout",
                "Not suitable for long-running processes",
            ],
            monthly_cost_range=(20.0, 80.0),
            cost_drivers=[
                "ALB: $16/month",
                "Lambda: $0.20/million invocations",
                "Break-even with API Gateway at ~5-10M requests/month",
            ],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF containerized_app:
        → ALB + Fargate (serverless containers)

    ELIF traditional_app AND high_utilization:
        → ALB + EC2 (cheaper at scale)

    ELIF api_traffic > 10M_requests_per_month:
        → ALB + Lambda (breaks even with API Gateway)

    ELSE:
        → ALB + Fargate (default for most cases)

    **Cost Comparison:**
    - ALB + Fargate: $36/month (2 small tasks)
    - ALB + EC2: $76/month (2 t3.medium instances)
    - ALB + Lambda: $20/month (5M requests)
    - API Gateway HTTP: $5/month (5M requests) - cheaper for low traffic

    **ALB vs API Gateway Break-even:**
    - ALB becomes cheaper than API Gateway REST at ~5-10M requests/month
    - For most REST APIs <5M requests: use API Gateway HTTP API
    - For containers: always use ALB (designed for it)
    """,
    soc2_relevance="""
    Load balancers are critical for availability and security:

    **CC6.1 (Access Controls):** Security groups restrict traffic to ALB
    **A1.2 (Availability):** Multi-AZ load balancing ensures high availability
    **CC7.2 (Monitoring):** CloudWatch metrics and access logs

    ALB supports WAF integration for threat protection.
    """,
    common_mistakes=[
        "Using ALB for low-traffic APIs (<5M requests - API Gateway is cheaper)",
        "Not enabling access logs (can't debug issues)",
        "Not setting up health check alarms",
        "Using EC2 when Fargate would be simpler and cheaper at low utilization",
        "Forgetting to attach WAF for public-facing applications",
    ],
)

ECS_FARGATE = ArchitectureDecision(
    question="What should I use to run containerized applications?",
    options=[
        DecisionOption(
            name="ECS Fargate (Recommended for Most Containers)",
            description="Serverless containers with no EC2 management - pay per task, auto-scaling, task-level isolation",
            when_to_use=[
                "Most containerized applications",
                "Microservices architecture",
                "Want serverless (no server management)",
                "Low to medium utilization (<70%)",
                "Development and staging environments",
            ],
            when_not_to_use=[
                "Very high utilization (>80% 24/7 - EC2 is cheaper)",
                "Need persistent local storage",
                "GPU workloads",
                "Tasks requiring <0.25 vCPU (Lambda is better)",
            ],
            pros=[
                "No EC2 management (truly serverless)",
                "Task-level security and isolation",
                "Fast deployment and scaling",
                "Pay only for tasks (can scale to zero)",
                "Simpler than ECS on EC2",
                "Automatic patching by AWS",
            ],
            cons=[
                "More expensive than EC2 at high utilization (>70%)",
                "0.25 vCPU minimum per task",
                "No persistent local storage (use EFS)",
                "Cold start when scaling from zero",
            ],
            monthly_cost_range=(10.0, 200.0),
            cost_drivers=[
                "Fargate: $0.04/vCPU-hour + $0.004/GB-hour",
                "0.25 vCPU, 0.5GB = $10/month per task (24/7)",
                "1 vCPU, 2GB = $50/month per task (24/7)",
                "Can scale to zero for dev/test (pay only when running)",
                "Example: 3 tasks (1 vCPU, 2GB) = $150/month",
            ],
            soc2_controls=["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="ECS on EC2",
            description="Containers running on EC2 instances - cheaper at high utilization, more control",
            when_to_use=[
                "High utilization workloads (>70% CPU/memory 24/7)",
                "Need Spot instances (70% cost savings)",
                "GPU workloads",
                "Need persistent local storage",
                "Very large scale (100+ containers)",
            ],
            when_not_to_use=[
                "Low utilization (<50% - Fargate is cheaper)",
                "Want serverless (no management overhead)",
                "Small team without container platform expertise",
            ],
            pros=[
                "Cheaper per compute hour at high utilization",
                "More control over instances",
                "Spot instance support (70% savings)",
                "GPU support",
                "Persistent local storage",
            ],
            cons=[
                "Must manage EC2 instances (patching, monitoring)",
                "Pay for full instances even when containers are idle",
                "More complex than Fargate",
                "Slower scaling",
                "Higher operational overhead",
            ],
            monthly_cost_range=(30.0, 150.0),
            cost_drivers=[
                "EC2: t3.medium ≈ $30/month per instance (24/7)",
                "Can run multiple containers per instance",
                "Example: t3.medium running 3 small containers = $10/month per container",
                "Spot instances: $9/month per t3.medium (70% savings)",
            ],
            soc2_controls=["CC6.1", "CC6.7", "CC7.2"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
        DecisionOption(
            name="Lambda with Container Images",
            description="Lambda functions packaged as container images - for event-driven, short-running tasks",
            when_to_use=[
                "Event-driven processing",
                "Batch jobs",
                "Short-running tasks (<15 minutes)",
                "Sporadic workloads",
                "Very low cost priority",
            ],
            when_not_to_use=[
                "Long-running processes (>15 minutes)",
                "HTTP servers or always-on services",
                "Need >10GB memory",
                "Container images >10GB",
            ],
            pros=[
                "True serverless (pay per invocation)",
                "Very cheap for sporadic workloads",
                "No always-on costs",
                "Auto-scales to millions of invocations",
            ],
            cons=[
                "15-minute timeout",
                "10GB memory limit",
                "10GB container image limit",
                "Cold starts",
                "Not suitable for HTTP servers",
            ],
            monthly_cost_range=(1.0, 20.0),
            cost_drivers=[
                "Lambda: $0.20/million invocations + compute time",
                "Example: 1M invocations (512MB, 1s) = $12/month",
                "Much cheaper than Fargate for sporadic workloads",
            ],
            soc2_controls=["CC6.1", "CC7.2"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF event_driven OR batch_job OR runtime < 15_minutes:
        → Lambda with containers (cheapest for sporadic)

    ELIF utilization > 70% AND scale > 20_containers:
        → ECS on EC2 (cheaper at high utilization)

    ELSE:
        → ECS Fargate (best for most cases)

    **Break-even Analysis:**
    - Fargate vs EC2: Fargate is cheaper when utilization <50-70%
    - Fargate vs Lambda: Fargate for always-on, Lambda for event-driven

    **Cost Example (1 vCPU, 2GB container, 24/7):**
    - Fargate: $50/month
    - EC2 (t3.medium): $10/month per container (can fit ~3 containers) = $30/month for instance
    - Lambda (24/7): $1,440/month (not suitable for always-on!)

    **Recommendation:** Start with Fargate, optimize to EC2 only if utilization >70% and scale justifies operational overhead.
    """,
    soc2_relevance="""
    Container platforms must ensure security and isolation:

    **CC6.1 (Access Controls):** IAM roles for tasks provide least privilege access
    **CC6.7 (Encryption):** Encryption at rest (ECR) and in transit (TLS)
    **CC7.2 (Monitoring):** CloudWatch Container Insights and logs
    **CC8.1 (Change Management):** CI/CD with blue/green deployments

    Fargate provides stronger task-level isolation than EC2.
    """,
    common_mistakes=[
        "Using ECS on EC2 when Fargate would be simpler and cheaper (low utilization)",
        "Not using Spot instances for ECS on EC2 (missing 70% savings)",
        "Using Lambda for always-on workloads (very expensive)",
        "Not setting up CloudWatch Container Insights (no visibility)",
        "Forgetting to implement blue/green deployments (risky deployments)",
    ],
)

ECS_COMPLETE = ArchitectureDecision(
    question="How do I build a production-ready containerized application with full security?",
    options=[
        DecisionOption(
            name="Complete ECS Fargate Production Stack (Recommended)",
            description="Full production stack with ALB, Fargate, monitoring, security, and CI/CD",
            when_to_use=[
                "Production workloads requiring SOC 2 compliance",
                "Customer-facing containerized applications",
                "Need enterprise security and monitoring",
                "Want low operational overhead",
            ],
            when_not_to_use=[
                "Proof of concept (too complex)",
                "Budget < $150/month",
                "Internal tools without security requirements",
            ],
            pros=[
                "Production-ready out of the box",
                "SOC 2 compliant architecture",
                "Serverless containers (no EC2 management)",
                "Auto-scaling with target tracking",
                "Blue/green deployments",
                "Comprehensive monitoring and alerting",
            ],
            cons=[
                "More complex than simple Fargate setup",
                "Higher cost ($150-400/month)",
                "Requires learning ECS concepts",
            ],
            monthly_cost_range=(150.0, 400.0),
            cost_drivers=[
                "ALB: $16/month",
                "Fargate tasks: $50-200/month (depends on size and count)",
                "RDS: $30-100/month (db.t3.micro to db.t3.small)",
                "ECR: $5/month (image storage)",
                "CloudWatch: $10-20/month (logs, metrics, alarms)",
                "WAF: $10/month (rate limiting, threat protection)",
                "X-Ray: $5/month (distributed tracing)",
                "VPC endpoints: $7.50/month per endpoint (optional)",
                "Example: Small app with 3 tasks = $150-250/month",
            ],
            soc2_controls=["CC6.1", "CC6.7", "CC7.1", "CC7.2", "CC8.1", "A1.2"],
            implementation_complexity="medium",
            operational_overhead="low",
        ),
    ],
    recommendation_logic="""
    **Complete Stack Includes:**

    **Compute:**
    - ECS Cluster with Fargate
    - ECS Services (one per microservice)
    - Task definitions with secrets from Secrets Manager
    - Service Auto Scaling (target tracking on CPU/memory)
    - VPC with private subnets (no public IPs on tasks)

    **Load Balancing:**
    - Application Load Balancer (public subnet)
    - Target Groups with health checks
    - ACM certificate for HTTPS
    - WAF with rate limiting and threat protection

    **Container Registry:**
    - ECR private registry
    - Image vulnerability scanning
    - Lifecycle policies (cleanup old images)
    - Encryption at rest

    **Security:**
    - IAM roles for tasks (least privilege)
    - Secrets Manager for passwords and API keys
    - Security groups (task-level, least privilege)
    - VPC endpoints (private AWS API access, no NAT Gateway)
    - Encryption at rest (ECR, EFS)
    - Encryption in transit (TLS, HTTPS)

    **Monitoring:**
    - CloudWatch Logs (centralized)
    - CloudWatch Container Insights (resource metrics)
    - X-Ray distributed tracing
    - CloudWatch Alarms:
      * CPU utilization > 80%
      * Memory utilization > 80%
      * Target response time > 1s
      * 5xx errors > 1%
      * Task count < minimum
    - SNS notifications for alerts

    **CI/CD:**
    - GitHub Actions or CodePipeline
    - Build Docker images in CodeBuild
    - Push to ECR
    - Blue/green deployment with ECS deployment controller
    - Automated rollback on CloudWatch alarm

    **Data:**
    - RDS or Aurora (database)
    - ElastiCache (caching)
    - S3 (file storage)
    - EFS (shared persistent storage, if needed)

    **Cost:** $150-400/month for complete production setup
    """,
    soc2_relevance="""
    This architecture addresses critical SOC 2 controls:

    **CC6.1 (Access Controls):** IAM roles + security groups enforce least privilege
    **CC6.7 (Encryption):** KMS encryption at rest + TLS in transit
    **CC7.1 (Threat Detection):** WAF + ECR vulnerability scanning
    **CC7.2 (System Monitoring):** CloudWatch Container Insights + X-Ray tracing
    **CC8.1 (Change Management):** CI/CD with blue/green deployments
    **A1.2 (Availability):** Auto Scaling + Multi-AZ ALB

    All components are managed services with built-in compliance features.
    """,
    common_mistakes=[
        "Skipping WAF (critical for rate limiting and DDoS protection)",
        "Not enabling ECR vulnerability scanning (miss security issues)",
        "Storing secrets in environment variables instead of Secrets Manager",
        "Not setting up CloudWatch alarms (no visibility into failures)",
        "Not implementing blue/green deployments (risky production deployments)",
        "Using NAT Gateway instead of VPC endpoints (unnecessary cost)",
    ],
)

EKS_KUBERNETES = ArchitectureDecision(
    question="Should I use EKS Kubernetes or ECS for containerized applications?",
    options=[
        DecisionOption(
            name="ECS Fargate (Recommended - Simpler)",
            description="AWS-native container service without Kubernetes complexity - saves $72/month on control plane",
            when_to_use=[
                "New to containers",
                "AWS-only deployment",
                "Don't need Kubernetes ecosystem",
                "Want simplicity and lower cost",
                "Team doesn't have Kubernetes expertise",
            ],
            when_not_to_use=[
                "Migrating existing Kubernetes workloads",
                "Need Helm charts and Kubernetes operators",
                "Multi-cloud strategy",
                "Advanced networking (service mesh)",
            ],
            pros=[
                "No control plane cost (save $72/month vs EKS)",
                "Simpler than Kubernetes",
                "AWS-native integrations",
                "Faster to learn",
                "Lower operational overhead",
            ],
            cons=[
                "No Kubernetes ecosystem (Helm, operators)",
                "AWS-specific (not portable to other clouds)",
                "Less advanced networking features",
            ],
            monthly_cost_range=(50.0, 200.0),
            cost_drivers=[
                "Fargate tasks only (no control plane cost)",
                "Example: 3 tasks (1 vCPU, 2GB) = $150/month",
                "$72/month cheaper than EKS for same workload",
            ],
            soc2_controls=["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
            implementation_complexity="low",
            operational_overhead="low",
        ),
        DecisionOption(
            name="EKS with Fargate (Serverless Kubernetes)",
            description="Managed Kubernetes with serverless nodes - no EC2 management but with Kubernetes ecosystem",
            when_to_use=[
                "Need Kubernetes but want serverless",
                "Migrating from on-prem Kubernetes",
                "Need Helm charts and operators",
                "Multi-cloud portability important",
            ],
            when_not_to_use=[
                "New to containers (ECS is simpler)",
                "Cost-sensitive (control plane costs $72/month)",
                "Don't need Kubernetes features",
            ],
            pros=[
                "No node management (serverless)",
                "Kubernetes ecosystem (Helm, operators)",
                "Multi-cloud portable",
                "Pod-level isolation",
            ],
            cons=[
                "Control plane: $72/month always-on cost",
                "More expensive than ECS",
                "Longer pod startup time",
                "Limited features (no DaemonSets on Fargate)",
                "More complex than ECS",
            ],
            monthly_cost_range=(100.0, 300.0),
            cost_drivers=[
                "EKS control plane: $72/month",
                "Fargate pods: $0.04/vCPU-hour + $0.004/GB-hour",
                "Example: 3 pods (0.25 vCPU, 0.5GB) = $100/month total",
            ],
            soc2_controls=["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
            implementation_complexity="high",
            operational_overhead="medium",
        ),
        DecisionOption(
            name="EKS with EC2 Node Groups",
            description="Managed Kubernetes with EC2 nodes - full Kubernetes features with Spot instance support",
            when_to_use=[
                "Standard Kubernetes workloads",
                "Need full Kubernetes features (DaemonSets, HostPath)",
                "High utilization (>70%)",
                "Need Spot instances for cost savings",
                "GPU workloads",
            ],
            when_not_to_use=[
                "Want serverless (use ECS or EKS Fargate)",
                "New to containers (steep learning curve)",
                "Low utilization (<50%)",
            ],
            pros=[
                "Full Kubernetes feature set",
                "Spot instance support (70% savings)",
                "GPU support",
                "More control over nodes",
                "Cheaper per compute hour than Fargate",
            ],
            cons=[
                "Control plane: $72/month",
                "Must manage EC2 nodes",
                "Most complex option",
                "Higher operational overhead",
            ],
            monthly_cost_range=(130.0, 500.0),
            cost_drivers=[
                "EKS control plane: $72/month",
                "EC2 nodes: $30/month per t3.medium",
                "Example: 2 t3.medium nodes = $132/month total",
                "Spot instances: $79/month (2 nodes) = 40% savings",
            ],
            soc2_controls=["CC6.1", "CC6.7", "CC7.2", "CC8.1"],
            implementation_complexity="high",
            operational_overhead="high",
        ),
    ],
    recommendation_logic="""
    **Decision Tree:**

    IF kubernetes_expertise AND (migrating_k8s OR need_helm_charts):
        → EKS (use Kubernetes)

    ELIF new_to_containers OR aws_only:
        → ECS Fargate (simpler, cheaper)

    ELIF need_spot_instances OR gpu_workloads:
        → EKS with EC2 (full features)

    ELSE:
        → ECS Fargate (default choice)

    **Cost Comparison (3 tasks/pods, 1 vCPU, 2GB each):**
    - ECS Fargate: $150/month (no control plane cost)
    - EKS Fargate: $222/month ($72 control plane + $150 pods)
    - EKS EC2: $132/month ($72 control plane + $60 for 2 t3.medium)

    **When to Use EKS:**
    1. Migrating existing Kubernetes workloads
    2. Need Helm charts or Kubernetes operators
    3. Multi-cloud portability required
    4. Team has Kubernetes expertise

    **When to Use ECS:**
    1. New to containers
    2. AWS-only deployment
    3. Want simplicity
    4. Save $72/month on control plane

    **Default recommendation:** Start with ECS Fargate. Only use EKS if you specifically need Kubernetes features.
    """,
    soc2_relevance="""
    Both EKS and ECS support SOC 2 compliance:

    **CC6.1 (Access Controls):** IAM roles for service accounts (EKS) or tasks (ECS)
    **CC6.7 (Encryption):** Encryption at rest and in transit supported by both
    **CC7.2 (Monitoring):** CloudWatch Container Insights for both
    **CC8.1 (Change Management):** CI/CD and GitOps workflows

    EKS adds Kubernetes RBAC for additional access controls.
    """,
    common_mistakes=[
        "Using EKS when ECS would be simpler and cheaper (no K8s requirement)",
        "Not using Spot instances with EKS EC2 (missing 70% cost savings)",
        "Paying $72/month for EKS control plane unnecessarily",
        "Starting with Kubernetes without team expertise (steep learning curve)",
        "Not considering operational overhead of managing Kubernetes",
    ],
)

# Export patterns
PATTERNS = [
    ALB_APPLICATION,
    ECS_FARGATE,
    ECS_COMPLETE,
    EKS_KUBERNETES
]
