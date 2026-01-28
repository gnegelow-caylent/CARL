"""
ECS/Fargate Security Patterns for CARL.

Patterns for ECS and Fargate security, container image security, and networking.

SOC 2 Relevance:
- CC6.1: Logical and physical access controls
- CC6.6: Encryption of data in transit and at rest
- CC6.7: Restricted access to system configurations
- CC7.2: System monitoring
"""

from dataclasses import dataclass
from typing import List
from .architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    SOC2Mapping,
)


# Pattern 1: ECS/Fargate Security Strategy
ECS_FARGATE_SECURITY_PATTERNS = ArchitectureDecision(
    category="Compute - ECS Security",
    question="What ECS/Fargate security strategy should be implemented?",
    context="""
ECS and Fargate security encompasses task execution roles, task IAM roles, Secrets Manager
integration, network modes, and runtime security. Strong container security prevents
unauthorized access, data breaches, and compliance violations.

Key security components:
- Task execution role: Pulls images, writes logs (ECS agent uses this)
- Task IAM role: Application permissions (your app uses this)
- Secrets Manager: Secure secrets injection into containers
- ECS Exec: Interactive shell access for debugging (security risk if enabled)
- Network mode: awsvpc provides isolation, bridge shares host networking
- Runtime security: GuardDuty for ECS/Fargate, Falco for container monitoring
""",
    options=[
        DecisionOption(
            name="EC2 Launch Type with Basic Security",
            description="""
Run ECS tasks on EC2 instances with basic security configuration. Suitable for
cost-sensitive deployments with existing EC2 expertise.

Configuration:
- EC2 instances in Auto Scaling Group
- ECS agent on instances
- Task execution role for pulling images from ECR
- Task IAM roles for application permissions
- Bridge network mode (containers share host networking)
- Secrets in environment variables (not recommended)
- CloudWatch Logs for logging

Security controls:
- EC2 instance security groups
- IAM task roles for API access
- CloudTrail logs all API calls
- Container logs to CloudWatch
""",
            pros=[
                "Lower cost than Fargate for long-running tasks",
                "Full control over EC2 instances",
                "Can use Reserved Instances or Savings Plans",
                "Suitable for high-throughput workloads",
            ],
            cons=[
                "Must manage EC2 instances (patching, scaling, security)",
                "Bridge mode shares host networking (less isolation)",
                "Secrets in environment variables (not secure)",
                "ECS agent requires management",
                "No IMDSv2 enforcement for containers by default",
            ],
            cost_factors=[
                "EC2 instances: Standard pricing (e.g., t3.medium = $30/month)",
                "EBS volumes: $0.10/GB-month",
                "Application Load Balancer: $16/month + LCU charges",
                "CloudWatch Logs: $0.50/GB ingested",
                "For 3 t3.medium instances: $90/month + storage + logs",
            ],
            monthly_cost_range=(100.00, 500.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM task roles restrict container access",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch Logs capture container logs",
                ),
            ],
        ),
        DecisionOption(
            name="Fargate with Secrets Manager Integration",
            description="""
Run containers on Fargate with Secrets Manager for secure secrets injection.
Serverless container platform with strong security defaults.

Implementation:
- Fargate launch type (no EC2 management)
- awsvpc network mode (each task gets ENI)
- Task execution role with Secrets Manager permissions
- Secrets Manager for sensitive data (database passwords, API keys)
- Task IAM roles with least privilege
- Security groups per service
- CloudWatch Logs with encryption
- ECS Exec disabled (default)

Secrets injection:
```json
{
  "containerDefinitions": [{
    "name": "app",
    "secrets": [{
      "name": "DB_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:region:account:secret:db-password"
    }]
  }]
}
```

Secrets are injected as environment variables at runtime, never stored in task definition.
""",
            pros=[
                "No EC2 instance management (serverless)",
                "Strong isolation with awsvpc network mode",
                "Secrets Manager integration (secure secrets)",
                "Automatic patching and maintenance by AWS",
                "Security groups per task/service",
                "IMDSv2 enforced by default on Fargate 1.4.0+",
            ],
            cons=[
                "Higher cost than EC2 launch type for 24/7 workloads",
                "Cold start time for scaling (up to 60 seconds)",
                "Secrets Manager costs ($0.40/secret/month + API calls)",
                "Limited to 4 vCPU, 30 GB memory per task",
            ],
            cost_factors=[
                "Fargate: $0.04048/vCPU-hour + $0.004445/GB-hour",
                "  - 1 vCPU, 2 GB, 24/7 = ~$40/month",
                "Secrets Manager: $0.40/secret/month + $0.05/10k API calls",
                "Application Load Balancer: $16/month",
                "CloudWatch Logs: $0.50/GB",
                "For 3 tasks (1 vCPU, 2 GB): $120/month + ALB + secrets",
            ],
            monthly_cost_range=(150.00, 600.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM task roles and security groups per task",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Secrets Manager encrypts secrets at rest",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Secrets not exposed in task definitions or logs",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch Logs capture all container activity",
                ),
            ],
        ),
        DecisionOption(
            name="Fargate with ECS Exec Disabled (Production)",
            description="""
Production Fargate deployment with ECS Exec disabled and read-only root filesystem.
Maximum security for production workloads.

Implementation:
- All features from Fargate with Secrets Manager
- ECS Exec explicitly disabled (prevents shell access)
- Read-only root filesystem (readonlyRootFilesystem: true)
- Non-root user in containers (USER 1000)
- Drop unnecessary Linux capabilities
- Network mode awsvpc with restrictive security groups
- No public IP addresses on tasks
- Private subnet deployment with NAT Gateway or VPC endpoints
- CloudWatch Container Insights for monitoring
- GuardDuty for ECS runtime security

Task definition security:
```json
{
  "containerDefinitions": [{
    "readonlyRootFilesystem": true,
    "user": "1000",
    "linuxParameters": {
      "capabilities": {
        "drop": ["ALL"]
      }
    }
  }],
  "enableExecuteCommand": false
}
```

Security groups:
- Only allow traffic from ALB security group
- Egress only to required services (RDS, Secrets Manager VPC endpoints)
""",
            pros=[
                "Maximum production security (no shell access)",
                "Read-only root filesystem prevents tampering",
                "Non-root containers reduce privilege escalation risk",
                "GuardDuty detects container runtime threats",
                "Private subnet deployment eliminates internet exposure",
                "Container Insights provides detailed metrics",
            ],
            cons=[
                "Debugging is harder (no ECS Exec, must use logs)",
                "Read-only filesystem requires planning for writable volumes",
                "GuardDuty ECS costs (~$0.012/GB analyzed)",
                "Container Insights costs (~$0.30/container/month)",
                "Requires VPC endpoints or NAT Gateway for AWS API calls",
            ],
            cost_factors=[
                "Fargate: $0.04048/vCPU-hour + $0.004445/GB-hour",
                "GuardDuty for ECS: ~$0.012/GB VPC Flow Logs analyzed",
                "Container Insights: ~$0.30/container/month",
                "VPC endpoints: $7.20/month per endpoint (Secrets Manager, ECR, CloudWatch)",
                "NAT Gateway: $32.40/month (if not using VPC endpoints)",
                "For 3 tasks: $120 (Fargate) + $1 (GuardDuty) + $1 (Insights) + $21.60 (3 endpoints) = ~$143/month",
            ],
            monthly_cost_range=(150.00, 800.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="No shell access, non-root containers, least privilege IAM",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="All data encrypted in transit and at rest",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Read-only filesystem, private subnets, restrictive security groups",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="GuardDuty runtime security, Container Insights monitoring",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise ECS with Service Mesh (App Mesh)",
            description="""
Enterprise ECS deployment with AWS App Mesh for service-to-service encryption,
observability, and traffic control. Suitable for complex microservices architectures.

Implementation:
- All features from Fargate with ECS Exec Disabled
- AWS App Mesh for service mesh capabilities:
  - mTLS for service-to-service encryption
  - Traffic management (retries, timeouts, circuit breakers)
  - Observability (X-Ray tracing, metrics)
- Envoy sidecar in each task
- Service discovery via Cloud Map
- X-Ray for distributed tracing
- Prometheus for custom metrics
- Automated certificate rotation with ACM Private CA
- Network segmentation via mesh virtual gateways

App Mesh provides:
- Mutual TLS (mTLS) between services
- Automatic retries and circuit breakers
- Traffic shifting for blue/green deployments
- Distributed tracing with X-Ray
- Metrics export to CloudWatch and Prometheus

Cost tradeoffs:
- Envoy sidecar adds vCPU/memory overhead (~0.25 vCPU, 512 MB per task)
- ACM Private CA for mTLS certificates ($400/month per CA)
- X-Ray tracing ($5 per 1 million traces)
""",
            pros=[
                "Service-to-service encryption with mTLS",
                "Advanced traffic management (retries, timeouts, circuit breakers)",
                "Distributed tracing with X-Ray",
                "Automated certificate rotation",
                "Supports complex microservices architectures",
                "Zero-trust networking within mesh",
            ],
            cons=[
                "High complexity (service mesh learning curve)",
                "Envoy sidecar adds resource overhead",
                "ACM Private CA cost ($400/month)",
                "Additional latency from Envoy proxy (~1-2ms)",
                "Overkill for simple architectures",
            ],
            cost_factors=[
                "Fargate with Envoy sidecar: ~$50/task/month (1.25 vCPU, 2.5 GB total)",
                "ACM Private CA: $400/month per CA (required for mTLS)",
                "X-Ray: $5 per 1 million traces",
                "App Mesh: No additional charge (underlying AWS services charged)",
                "Cloud Map: $0.50/million queries (for service discovery)",
                "For 10 services (30 tasks): $1,500 (Fargate) + $400 (ACM PCA) + $5 (X-Ray) = ~$1,905/month",
            ],
            monthly_cost_range=(500.00, 3000.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="mTLS enforces authentication between services",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="mTLS encrypts all service-to-service traffic",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Service mesh policies enforce access controls",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="X-Ray tracing provides end-to-end observability",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Circuit breakers and retries improve resilience",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose EC2 Launch Type when:
- Cost-sensitive for 24/7 workloads
- Existing EC2 expertise and tooling
- Need Reserved Instances or Savings Plans discounts
- High-throughput workloads (network performance)
- Can accept EC2 management overhead

Choose Fargate with Secrets Manager when:
- Want serverless containers (no EC2 management)
- Production workloads with moderate security requirements
- Need fast scaling and deployment
- Secrets must not be in task definitions
- Most common choice for new ECS deployments

Choose Fargate with ECS Exec Disabled when:
- Production environment with strict security requirements
- Compliance requires no shell access (SOC 2, PCI-DSS)
- Need runtime threat detection (GuardDuty)
- Can debug via logs only (no interactive access)
- Best practice for production workloads

Choose Enterprise with Service Mesh when:
- Complex microservices architecture (10+ services)
- Need service-to-service encryption (mTLS)
- Distributed tracing required for observability
- Advanced traffic management needed
- Budget supports $500+ per month
- Have expertise in service mesh concepts
""",
    examples=[
        {
            "scenario": "Single containerized web application with low traffic",
            "recommendation": "EC2 Launch Type with Basic Security",
            "reasoning": "Single application doesn't need Fargate's isolation. EC2 with Reserved Instances is more cost-effective.",
        },
        {
            "scenario": "SaaS platform with 5 microservices on ECS",
            "recommendation": "Fargate with Secrets Manager Integration",
            "reasoning": "Fargate eliminates EC2 management. Secrets Manager securely injects database passwords. Scales automatically.",
        },
        {
            "scenario": "Healthcare application with HIPAA requirements",
            "recommendation": "Fargate with ECS Exec Disabled (Production)",
            "reasoning": "HIPAA requires no production shell access. GuardDuty provides runtime threat detection. Read-only filesystem prevents tampering.",
        },
        {
            "scenario": "Financial services with 20 microservices and strict compliance",
            "recommendation": "Enterprise ECS with Service Mesh",
            "reasoning": "mTLS encrypts service-to-service traffic. X-Ray provides audit trail. Circuit breakers improve resilience.",
        },
    ],
)


# Pattern 2: Container Image Security
CONTAINER_IMAGE_SECURITY_PATTERNS = ArchitectureDecision(
    category="Compute - ECS Security",
    question="What container image security strategy should be implemented?",
    context="""
Container image security ensures images are free of vulnerabilities, come from trusted
sources, and are scanned regularly. Insecure images are a leading cause of container
security breaches.

Key considerations:
- Image source: Public (Docker Hub) vs. private (ECR)
- Image scanning: Vulnerabilities in OS packages and application dependencies
- Image signing: Verify image integrity and provenance
- Base image selection: Minimal images reduce attack surface
- Secrets in images: Never bake secrets into images

Common vulnerabilities:
- Outdated base images (e.g., Ubuntu 18.04 with known CVEs)
- Vulnerable dependencies (e.g., Log4Shell in Java applications)
- Secrets in images (API keys, passwords)
- Running as root user
- Unnecessary packages installed
""",
    options=[
        DecisionOption(
            name="Public Docker Hub Images (Development Only)",
            description="""
Pull images directly from Docker Hub or other public registries. Acceptable for
development and learning, but not recommended for production.

Configuration:
- Task definitions reference Docker Hub images:
  - "image": "nginx:latest"
  - "image": "postgres:14"
- No image scanning
- No image signing verification
- Public pull rate limits (100 pulls per 6 hours for anonymous)

Risk:
- Unknown vulnerabilities in images
- No control over image updates (latest tag can change)
- Public images could be compromised
- Rate limiting can break deployments
""",
            pros=[
                "Zero setup required",
                "Large selection of pre-built images",
                "Fast to get started",
                "No image storage costs",
            ],
            cons=[
                "Unknown security posture (no scanning)",
                "Public images may contain vulnerabilities or malware",
                "No control over image updates",
                "Docker Hub rate limiting (100 pulls per 6 hours)",
                "Not suitable for production (compliance risk)",
                "Cannot verify image provenance",
            ],
            cost_factors=[
                "No AWS costs (free Docker Hub tier)",
                "May need Docker Hub Pro ($5/month) to avoid rate limits",
            ],
            monthly_cost_range=(0, 5.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.8",
                    control_name="Malicious software prevention",
                    how_it_helps="No scanning - weak control (development only)",
                ),
            ],
        ),
        DecisionOption(
            name="Amazon ECR with Basic Scanning",
            description="""
Store images in Amazon ECR with basic image scanning enabled. Images are scanned
once on push for OS-level vulnerabilities.

Implementation:
- Create ECR repository per application
- Enable scan on push (basic scanning)
- Push images to ECR:
  ```
  docker tag myapp:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:latest
  docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:latest
  ```
- Basic scanning detects CVEs in OS packages
- Review scan results in ECR console
- Manually address high/critical vulnerabilities

Basic scanning:
- Scans image once on push
- Detects CVEs in OS packages only (not application dependencies)
- Powered by Clair (open source)
- Free (included with ECR)

Limitations:
- One-time scan only (new CVEs discovered later not detected)
- OS packages only (no language-specific dependencies)
- No blocking of vulnerable images
""",
            pros=[
                "Private image registry (no public exposure)",
                "Basic scanning included free",
                "Lifecycle policies for automatic cleanup",
                "IAM-based access control",
                "Replication to other regions",
            ],
            cons=[
                "Basic scanning is one-time only (no continuous scanning)",
                "Doesn't scan application dependencies (npm, pip, maven)",
                "No automated blocking of vulnerable images",
                "Manual remediation required",
            ],
            cost_factors=[
                "ECR storage: $0.10/GB-month",
                "Data transfer: $0.09/GB out to internet (free within region)",
                "Basic scanning: Free",
                "For 10 images × 500 MB = 5 GB = $0.50/month",
            ],
            monthly_cost_range=(5.00, 50.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM controls who can push/pull images",
                ),
                SOC2Mapping(
                    control_id="CC6.8",
                    control_name="Malicious software prevention",
                    how_it_helps="Basic scanning detects known CVEs in OS packages",
                ),
            ],
        ),
        DecisionOption(
            name="ECR Enhanced Scanning with Inspector",
            description="""
Use Amazon Inspector for continuous vulnerability scanning of container images.
Automatically detects new CVEs and scans both OS and application dependencies.

Implementation:
- Enable Amazon Inspector for ECR scanning
- Inspector continuously scans images for new CVEs
- Scans both OS packages and application dependencies:
  - OS: CVEs in Ubuntu, Amazon Linux, Alpine, etc.
  - Application: Vulnerabilities in npm, pip, maven, gem, etc.
- EventBridge rules alert on high/critical findings
- Lambda function can block deployment of vulnerable images
- Integration with Security Hub for centralized findings

Enhanced scanning benefits:
- Continuous monitoring (new CVEs detected automatically)
- Application dependency scanning (npm, pip, maven)
- CVSS scores and remediation guidance
- Integration with CI/CD (fail build if critical CVEs)

Example workflow:
1. Push image to ECR
2. Inspector scans image (OS + dependencies)
3. High/critical CVE found
4. EventBridge triggers Lambda
5. Lambda sends Slack alert and blocks ECS deployment
6. Developer fixes vulnerability
7. Repeat
""",
            pros=[
                "Continuous vulnerability scanning (not one-time)",
                "Scans application dependencies (npm, pip, maven)",
                "Automated alerting via EventBridge",
                "Can block vulnerable images from deployment",
                "CVSS scores and remediation guidance",
                "Integrated with Security Hub",
            ],
            cons=[
                "Inspector costs (~$0.09 per image scan)",
                "Requires automation for blocking/alerting",
                "Can generate alert fatigue if not tuned",
                "Must configure EventBridge rules and Lambda",
            ],
            cost_factors=[
                "ECR storage: $0.10/GB-month",
                "Inspector ECR scanning: ~$0.09 per image re-scan",
                "  - 10 images × 4 scans/month = $3.60/month",
                "EventBridge rules: Free (within limits)",
                "Lambda for automation: ~$1/month",
                "Security Hub: ~$1.20/account/month",
                "For 10 images: $0.50 (storage) + $3.60 (Inspector) + $1 (Lambda) + $1.20 (Hub) = ~$6.30/month",
            ],
            monthly_cost_range=(10.00, 100.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM controls image access, automated blocking prevents vulnerable deployments",
                ),
                SOC2Mapping(
                    control_id="CC6.8",
                    control_name="Malicious software prevention",
                    how_it_helps="Continuous scanning detects vulnerabilities in OS and dependencies",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Security Hub aggregates vulnerability findings",
                ),
            ],
        ),
        DecisionOption(
            name="Supply Chain Security with Image Signing (Signer)",
            description="""
Comprehensive container supply chain security with image signing, provenance tracking,
and automated vulnerability remediation. Enterprise-grade image security.

Implementation:
- All features from ECR Enhanced Scanning
- AWS Signer for image signing (Docker Content Trust alternative)
- Image provenance tracking (who built, when, from what source)
- Automated vulnerability remediation:
  - Lambda rebuilds images when CVEs detected
  - CI/CD pipeline runs tests on patched images
  - Auto-deploy to non-prod for validation
- Admission control (only signed images can be deployed)
- SBOM (Software Bill of Materials) generation
- Integration with CI/CD for automated scanning

Image signing workflow:
1. CI/CD builds image and pushes to ECR
2. Signer signs image with signing profile
3. Signature stored in ECR
4. ECS task definition requires signature verification
5. Only signed images can be deployed

Automated remediation:
1. Inspector detects critical CVE in base image
2. EventBridge triggers remediation Lambda
3. Lambda triggers CodeBuild to rebuild image
4. CodeBuild updates Dockerfile base image
5. Runs tests
6. Pushes patched image to ECR
7. Signer signs new image
8. Triggers deployment to dev/staging
9. Notifies team for prod approval

SBOM generation:
- Syft generates SBOM for each image
- SBOM stored in S3 for audit trail
- Compliance reports show all dependencies
""",
            pros=[
                "Image signing ensures integrity and provenance",
                "Automated vulnerability remediation reduces manual work",
                "SBOM provides complete visibility into dependencies",
                "Admission control prevents unsigned images",
                "Meets strictest compliance requirements (SOC 2, PCI-DSS)",
                "Supply chain security (provenance tracking)",
            ],
            cons=[
                "Very high complexity (requires significant automation)",
                "Signer costs ($0.50 per signing operation)",
                "Automated remediation requires robust CI/CD",
                "Can break deployments if not properly configured",
                "Overkill for small organizations",
            ],
            cost_factors=[
                "ECR storage: $0.10/GB-month",
                "Inspector: ~$0.09 per image scan",
                "Signer: $0.50 per signing operation (50 signs/month = $25)",
                "CodeBuild for remediation: ~$5/month",
                "Lambda automation: ~$5/month",
                "S3 for SBOM storage: ~$1/month",
                "Security Hub: ~$1.20/account/month",
                "For 10 images: ~$40/month (includes signing, scanning, automation)",
            ],
            monthly_cost_range=(50.00, 200.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Admission control allows only signed images",
                ),
                SOC2Mapping(
                    control_id="CC6.8",
                    control_name="Malicious software prevention",
                    how_it_helps="Continuous scanning + automated remediation",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="SBOM and provenance tracking provide audit trail",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Image signing provides cryptographic proof of image integrity",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Public Docker Hub when:
- Development or learning environment only
- No production deployment
- Fast experimentation needed
- Understand the security risks

Choose ECR with Basic Scanning when:
- Production deployment with basic security needs
- Need private image registry
- One-time scan on push is sufficient
- Manual vulnerability remediation acceptable
- Most common starting point for production

Choose ECR Enhanced Scanning when:
- Production with moderate to high security requirements
- Need continuous vulnerability monitoring
- Application dependency scanning required
- Can invest in automation (EventBridge, Lambda)
- Budget supports $10-100/month for scanning
- Best practice for most production workloads

Choose Supply Chain Security when:
- Enterprise with strict compliance (SOC 2, PCI-DSS, FedRAMP)
- Need cryptographic proof of image integrity
- Automated vulnerability remediation required
- Supply chain attacks are a concern
- Budget supports $50-200/month
- Have expertise in CI/CD automation
""",
    examples=[
        {
            "scenario": "Learning Kubernetes with sample applications",
            "recommendation": "Public Docker Hub Images",
            "reasoning": "Development only. Public images are fast to get started. No production data.",
        },
        {
            "scenario": "Production SaaS application with 3 microservices",
            "recommendation": "ECR with Basic Scanning",
            "reasoning": "Private ECR ensures control. Basic scanning detects OS vulnerabilities. Manual remediation acceptable for 3 images.",
        },
        {
            "scenario": "Healthcare application with 10 microservices and HIPAA requirements",
            "recommendation": "ECR Enhanced Scanning with Inspector",
            "reasoning": "Continuous scanning required. Application dependency scanning (npm, pip). EventBridge alerts security team on critical CVEs.",
        },
        {
            "scenario": "Financial services with supply chain security requirements",
            "recommendation": "Supply Chain Security with Image Signing",
            "reasoning": "Image signing provides non-repudiation. SBOM required for compliance. Automated remediation reduces risk window.",
        },
    ],
)


# Pattern 3: ECS Networking and IAM
ECS_NETWORKING_IAM_PATTERNS = ArchitectureDecision(
    category="Compute - ECS Security",
    question="What ECS networking and IAM strategy should be implemented?",
    context="""
ECS networking and IAM are critical for security. Network mode determines isolation,
IAM roles control AWS API access, and security groups control network traffic.

Network modes:
- bridge: Containers share host networking (less isolation)
- awsvpc: Each task gets own ENI (strong isolation)
- host: Container uses host network directly (not recommended)

IAM roles:
- Task execution role: ECS agent uses (pull images, write logs)
- Task IAM role: Application uses (S3, DynamoDB, etc.)

Security considerations:
- Principle of least privilege for IAM roles
- Security groups per service (not per host)
- Private subnets for tasks (no public IPs)
- VPC endpoints for AWS API access (avoid NAT Gateway)
""",
    options=[
        DecisionOption(
            name="Bridge Network Mode (EC2 Launch Type)",
            description="""
Use bridge network mode on EC2 launch type. Containers share host networking with
port mapping. Suitable for simple deployments.

Configuration:
- Network mode: bridge
- Containers use host's network interface
- Port mapping: host port 80 → container port 8080
- Security groups on EC2 instances (not tasks)
- Task execution role for image pulling
- Task IAM role for application permissions

Limitations:
- Security groups apply to EC2 instance, not individual tasks
- All tasks on instance share security group
- Dynamic port mapping requires ALB for service discovery
- Less isolation between containers
""",
            pros=[
                "Simple to understand and configure",
                "Works with EC2 launch type",
                "No ENI limits per instance",
                "Can use dynamic port mapping with ALB",
            ],
            cons=[
                "Weak isolation (containers share host networking)",
                "Security groups per instance, not per task",
                "Cannot use Fargate (Fargate requires awsvpc)",
                "Port conflicts if not using dynamic port mapping",
            ],
            cost_factors=[
                "No additional networking costs",
                "Standard EC2 pricing applies",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM task roles control application permissions",
                ),
            ],
        ),
        DecisionOption(
            name="awsvpc Network Mode (Basic)",
            description="""
Use awsvpc network mode for task-level networking isolation. Each task gets dedicated
ENI with security group and private IP.

Implementation:
- Network mode: awsvpc
- Each task gets elastic network interface (ENI)
- Security groups per service (not per host)
- Tasks launched in private subnets
- Task execution role:
  - ecr:GetAuthorizationToken
  - ecr:BatchGetImage
  - logs:CreateLogStream, logs:PutLogEvents
- Task IAM role with least privilege:
  - s3:GetObject for specific bucket
  - dynamodb:Query for specific table
- NAT Gateway for outbound internet access

Benefits:
- Strong network isolation
- Security groups per service
- Works with Fargate
- Simplified security group management
""",
            pros=[
                "Strong network isolation (ENI per task)",
                "Security groups per service, not per host",
                "Works with Fargate launch type",
                "Private IPs for tasks (no port conflicts)",
                "Simplified network security",
            ],
            cons=[
                "ENI limits per instance (EC2 launch type)",
                "Slightly higher latency (ENI overhead)",
                "More complex routing (VPC networking)",
                "NAT Gateway costs for internet access",
            ],
            cost_factors=[
                "No additional networking costs for awsvpc mode",
                "NAT Gateway: $32.40/month + $0.045/GB data processing",
                "For 100 GB/month: $32.40 + $4.50 = $36.90/month",
            ],
            monthly_cost_range=(35.00, 100.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Security groups per service enforce network access control",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Private subnets and security groups restrict network access",
                ),
            ],
        ),
        DecisionOption(
            name="awsvpc with Service Discovery (Cloud Map)",
            description="""
Use awsvpc with AWS Cloud Map for service discovery. Services find each other by
DNS name instead of hard-coded IPs/ports.

Implementation:
- awsvpc network mode
- Private subnets for tasks
- Cloud Map for service discovery:
  - Each ECS service registers tasks in Cloud Map namespace
  - Services discover each other via DNS (api.local, db.local)
  - Automatic registration/deregistration on task start/stop
- Route 53 private hosted zone
- VPC endpoints for AWS services (no NAT Gateway):
  - ecr.api, ecr.dkr, logs, s3, secretsmanager
- Task IAM roles with least privilege (specific resource ARNs)

Service discovery example:
- API service tasks register as api.service.local
- Web service queries api.service.local
- Cloud Map returns healthy API task IPs
- Web service connects to API (no hard-coded IPs)

VPC endpoints (no NAT Gateway):
- ECR API endpoint: $7.20/month + data
- ECR Docker endpoint: $7.20/month + data
- CloudWatch Logs endpoint: $7.20/month + data
- S3 gateway endpoint: Free
- Secrets Manager endpoint: $7.20/month + data
- Total: ~$29/month for 4 endpoints
""",
            pros=[
                "Service discovery via DNS (no hard-coded IPs)",
                "Automatic registration/deregistration",
                "VPC endpoints eliminate NAT Gateway costs",
                "Simplified microservices architecture",
                "Private communication (no internet exposure)",
            ],
            cons=[
                "VPC endpoint costs (~$29/month for 4 endpoints)",
                "Cloud Map costs ($0.50/million queries)",
                "More complex setup (VPC endpoints, Cloud Map)",
                "DNS propagation delays (seconds)",
            ],
            cost_factors=[
                "VPC endpoints: $7.20/month per endpoint × 4 = $28.80/month",
                "Cloud Map: $0.50/million queries (negligible for most workloads)",
                "VPC endpoint data: $0.01/GB",
                "No NAT Gateway costs",
                "For 100 GB/month: $28.80 (endpoints) + $1 (data) = ~$30/month",
            ],
            monthly_cost_range=(30.00, 100.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Least privilege IAM roles per service",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Private subnets, VPC endpoints, no NAT Gateway",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Service discovery enables failover to healthy tasks",
                ),
            ],
        ),
        DecisionOption(
            name="Full Zero-Trust with VPC Endpoints and Network Policies",
            description="""
Enterprise zero-trust networking for ECS with VPC endpoints, service mesh, and
network policies. Maximum security for complex microservices.

Implementation:
- All features from awsvpc with Service Discovery
- AWS App Mesh for mTLS and network policies:
  - Mutual TLS between services
  - Network policies control which services can communicate
  - Service-to-service authentication
- VPC endpoints for all AWS services (no internet egress)
- IAM Roles Anywhere for external service authentication
- Security groups with restrictive egress (no 0.0.0.0/0)
- GuardDuty for ECS runtime threat detection
- VPC Flow Logs analyze traffic patterns
- Network Firewall for deep packet inspection (optional)

Zero-trust principles:
1. Never trust, always verify
2. Least privilege access (network + IAM)
3. Service-to-service authentication (mTLS)
4. Continuous monitoring (GuardDuty, Flow Logs)

Network policies example:
- web-service can call api-service (allowed)
- web-service cannot call db-service (blocked by App Mesh policy)
- api-service can call db-service (allowed)

This enforces least privilege at network layer.
""",
            pros=[
                "Zero-trust networking (mTLS, network policies)",
                "Service-to-service authentication",
                "No internet egress (VPC endpoints only)",
                "Runtime threat detection (GuardDuty)",
                "Comprehensive audit trail (Flow Logs)",
                "Meets strictest compliance requirements",
            ],
            cons=[
                "Very high complexity (service mesh, network policies)",
                "ACM Private CA required for mTLS ($400/month)",
                "VPC Flow Logs storage costs (~$0.50/GB)",
                "Significant setup and maintenance effort",
                "Overkill for simple architectures",
            ],
            cost_factors=[
                "VPC endpoints: $7.20/month × 5 = $36/month",
                "ACM Private CA: $400/month (for mTLS certificates)",
                "GuardDuty: ~$0.012/GB VPC Flow Logs analyzed",
                "VPC Flow Logs: ~$0.50/GB + S3 storage",
                "App Mesh: No additional charge",
                "Network Firewall (optional): $284/month per endpoint",
                "For 500 GB/month flow logs: $36 (endpoints) + $400 (PCA) + $6 (GuardDuty) + $250 (flow logs) = ~$692/month",
            ],
            monthly_cost_range=(500.00, 1500.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Zero-trust networking with mTLS authentication",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="mTLS encrypts all service-to-service traffic",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Network policies enforce least privilege",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="GuardDuty + Flow Logs provide comprehensive monitoring",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Bridge Network Mode when:
- Using EC2 launch type
- Simple single-service deployment
- No strict security requirements
- Development environment
- Want minimal complexity

Choose awsvpc with Basic when:
- Using Fargate or want task-level isolation
- Need security groups per service
- Production with moderate security requirements
- Can use NAT Gateway for internet access
- Most common choice for production ECS

Choose awsvpc with Service Discovery when:
- Microservices architecture (5+ services)
- Need dynamic service discovery
- Want to eliminate NAT Gateway costs
- Services communicate internally
- Budget supports $30-100/month for VPC endpoints

Choose Full Zero-Trust when:
- Enterprise with 10+ microservices
- Strict compliance (SOC 2, PCI-DSS, FedRAMP)
- Need service-to-service authentication (mTLS)
- Zero-trust architecture required
- Budget supports $500-1500/month
- Have expertise in service mesh and network policies
""",
    examples=[
        {
            "scenario": "Single web application on ECS with EC2 launch type",
            "recommendation": "Bridge Network Mode",
            "reasoning": "Simple deployment. Security groups on EC2 instances sufficient. No need for awsvpc complexity.",
        },
        {
            "scenario": "Fargate-based API service with database backend",
            "recommendation": "awsvpc with Basic",
            "reasoning": "Fargate requires awsvpc. Security groups per service. NAT Gateway for internet access (AWS SDK calls).",
        },
        {
            "scenario": "Microservices platform with 8 services on Fargate",
            "recommendation": "awsvpc with Service Discovery",
            "reasoning": "Service discovery simplifies inter-service communication. VPC endpoints cheaper than NAT Gateway at scale.",
        },
        {
            "scenario": "Financial services with 20 microservices and zero-trust requirements",
            "recommendation": "Full Zero-Trust with VPC Endpoints",
            "reasoning": "mTLS for service authentication. Network policies enforce least privilege. GuardDuty detects threats. Meets compliance requirements.",
        },
    ],
)


# Export all patterns
__all__ = [
    "ECS_FARGATE_SECURITY_PATTERNS",
    "CONTAINER_IMAGE_SECURITY_PATTERNS",
    "ECS_NETWORKING_IAM_PATTERNS",
]
