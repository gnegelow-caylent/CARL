"""
EKS Security Patterns for CARL.

Patterns for Amazon EKS security, IRSA, Pod security, and networking.

SOC 2 Relevance:
- CC6.1: Logical and physical access controls
- CC6.2: Prior authorization and authentication
- CC6.6: Encryption and network security
- CC7.2: System monitoring
"""

from dataclasses import dataclass
from typing import List
from .architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    SOC2Mapping,
)


# Pattern 1: EKS Security Strategy
EKS_SECURITY_STRATEGY_PATTERNS = ArchitectureDecision(
    category="Compute - EKS Security",
    question="What EKS security strategy should be implemented?",
    context="""
EKS security encompasses cluster endpoint access, node security, IAM for Service Accounts
(IRSA), Pod Security Standards, and runtime security. Strong Kubernetes security prevents
unauthorized access and lateral movement.

Key security components:
- Cluster endpoint: Public vs. private API server access
- Node groups: Managed vs. self-managed, OS hardening
- IRSA (IAM Roles for Service Accounts): Fine-grained IAM permissions
- Pod Security Standards: Enforce pod security policies
- Network policies: Control pod-to-pod traffic
- Secrets encryption: Encrypt secrets at rest with KMS
""",
    options=[
        DecisionOption(
            name="Managed Node Groups with Basic Security",
            description="""
Use EKS managed node groups with basic security configuration. AWS manages node
lifecycle, patching, and scaling.

Configuration:
- Public cluster endpoint (simplified access)
- Managed node groups (AWS handles provisioning, scaling, patching)
- Amazon Linux 2 AMI (EKS-optimized)
- Basic RBAC (Kubernetes role-based access control)
- No IRSA (pods use node IAM role)
- No Pod Security Standards enforcement
- Basic security groups for nodes
- CloudWatch Logs for control plane logging

Access:
- kubectl access via public endpoint
- Nodes in private subnets with NAT Gateway
- AWS IAM Authenticator for cluster access

Node IAM role permissions:
- Shared by all pods on node (not least privilege)
- Includes ECR, CloudWatch Logs, Auto Scaling
""",
            pros=[
                "Simple to set up and manage",
                "AWS handles node patching and updates",
                "Managed node groups scale automatically",
                "Good for getting started with EKS",
            ],
            cons=[
                "Public endpoint exposes API server to internet",
                "No pod-level IAM (shared node role)",
                "No Pod Security Standards (pods can run privileged)",
                "Amazon Linux 2 (not minimal attack surface)",
                "Manual security hardening required",
            ],
            cost_factors=[
                "EKS cluster: $0.10/hour = $72/month",
                "EC2 nodes: Standard pricing (e.g., t3.medium = $30/month)",
                "NAT Gateway: $32.40/month + data",
                "CloudWatch Logs: $0.50/GB",
                "For 3 t3.medium nodes: $72 (cluster) + $90 (nodes) + $35 (NAT) = $197/month",
            ],
            monthly_cost_range=(200.00, 500.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="AWS IAM Authenticator restricts cluster access",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch Logs capture control plane activity",
                ),
            ],
        ),
        DecisionOption(
            name="Fargate Pods (Serverless)",
            description="""
Run pods on AWS Fargate for serverless Kubernetes. No node management required.

Implementation:
- Private cluster endpoint recommended
- Fargate profiles define which pods run on Fargate
- No EC2 nodes to manage (serverless)
- IRSA for pod-level IAM permissions
- Pod Security Standards enforced by Fargate
- Each pod runs in isolated compute environment
- VPC networking with security groups per pod

Fargate profile example:
```yaml
fargate_profiles:
  - name: app
    namespace: production
    labels:
      app: web
```

Pods matching namespace and labels run on Fargate automatically.

Limitations:
- Not all workloads supported (DaemonSets, privileged containers)
- Higher cost than EC2 for long-running pods
- Cold start time (30-60 seconds)
- Limited to 4 vCPU, 30 GB memory per pod
""",
            pros=[
                "No node management (serverless)",
                "Strong isolation (each pod in own compute)",
                "Automatic scaling (no cluster autoscaler needed)",
                "IRSA built-in (pod-level IAM)",
                "Pod Security Standards enforced",
            ],
            cons=[
                "Higher cost than EC2 for 24/7 workloads",
                "Not all Kubernetes features supported",
                "Cold start delays for scaling",
                "DaemonSets not supported (logging/monitoring requires workarounds)",
                "Requires VPC endpoints (no NAT Gateway support)",
            ],
            cost_factors=[
                "EKS cluster: $72/month",
                "Fargate: $0.04048/vCPU-hour + $0.004445/GB-hour",
                "  - 1 vCPU, 2 GB, 24/7 = approx. $40/pod/month",
                "VPC endpoints: $7.20/month × 4 = $28.80/month",
                "For 5 pods: $72 (cluster) + $200 (pods) + $29 (endpoints) = $301/month",
            ],
            monthly_cost_range=(300.00, 1000.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IRSA provides pod-level IAM permissions",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Pod isolation and encryption at rest",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Control plane and pod logs to CloudWatch",
                ),
            ],
        ),
        DecisionOption(
            name="Bottlerocket OS with Private Endpoint",
            description="""
Use Bottlerocket OS (AWS purpose-built Linux) with private cluster endpoint for
maximum security. Bottlerocket has minimal attack surface.

Implementation:
- Private cluster endpoint only (API server not internet-exposed)
- Bottlerocket OS on managed node groups:
  - Minimal OS (no SSH, no package manager)
  - Image-based updates (atomic, rollback-able)
  - SELinux enforcing mode
  - Read-only root filesystem
- IRSA for pod-level IAM permissions
- Pod Security Standards (Restricted profile)
- Secrets encryption with KMS
- Control plane logs to CloudWatch
- VPC endpoints for AWS API access

Bottlerocket benefits:
- Minimal attack surface (no SSH server, no shell by default)
- Automatic security updates (image-based)
- SELinux provides defense-in-depth
- Immutable infrastructure (can't be modified at runtime)

Access methods:
- SSM Session Manager for admin access (break glass)
- Bottlerocket admin container for troubleshooting
- No SSH keys required
""",
            pros=[
                "Private endpoint (API server not exposed to internet)",
                "Bottlerocket minimal attack surface",
                "Image-based updates (consistent, rollback-able)",
                "IRSA for pod-level IAM (least privilege)",
                "Pod Security Standards enforced",
                "Secrets encrypted with KMS",
            ],
            cons=[
                "Private endpoint requires VPN/bastion for kubectl access",
                "Bottlerocket learning curve (different from Amazon Linux)",
                "Limited troubleshooting tools (by design)",
                "VPC endpoints required for AWS API access",
                "More complex setup than standard managed node groups",
            ],
            cost_factors=[
                "EKS cluster: $72/month",
                "EC2 nodes (Bottlerocket): Standard pricing",
                "VPC endpoints: $7.20/month × 5 = $36/month",
                "KMS key: $1/month",
                "SSM Session Manager: approx. $1.50/node/month",
                "For 3 t3.medium nodes: $72 (cluster) + $90 (nodes) + $36 (endpoints) + $1 (KMS) + $5 (SSM) = $204/month",
            ],
            monthly_cost_range=(200.00, 800.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Private endpoint + IRSA + Pod Security Standards",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Secrets encrypted with KMS, TLS for API server",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Private endpoint, minimal OS, no SSH",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Control plane logs, SSM session logs",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise with Karpenter Auto-Scaling",
            description="""
Enterprise EKS deployment with Karpenter for intelligent node auto-scaling,
comprehensive security monitoring, and GitOps.

Implementation:
- All features from Bottlerocket with Private Endpoint
- Karpenter for intelligent node provisioning:
  - Just-in-time node provisioning (seconds, not minutes)
  - Consolidation to reduce costs
  - Diverse instance types (Spot, on-demand)
  - Custom provisioners per workload
- GuardDuty for EKS runtime security
- Falco for container runtime monitoring
- AWS Security Hub aggregates findings
- GitOps with Flux or ArgoCD
- Network policies (Calico or Cilium)
- Service mesh (Istio or App Mesh) for mTLS
- Admission controller (OPA Gatekeeper or Kyverno)

Karpenter benefits:
- Fast scaling (provisions nodes in 30-60 seconds)
- Cost optimization (consolidates underutilized nodes)
- Workload-specific provisioners (GPU, memory-optimized)
- Native support for Spot instances

Runtime security:
- GuardDuty detects threats (crypto mining, C2 communication)
- Falco monitors system calls (file access, network connections)
- Admission controller blocks non-compliant workloads
""",
            pros=[
                "Fast, intelligent auto-scaling with Karpenter",
                "Comprehensive runtime security (GuardDuty, Falco)",
                "GitOps for declarative infrastructure",
                "Network policies enforce pod-to-pod segmentation",
                "Service mesh provides mTLS and observability",
                "Admission controller prevents insecure deployments",
            ],
            cons=[
                "Very high complexity (many moving parts)",
                "Requires Kubernetes and GitOps expertise",
                "Karpenter learning curve",
                "Service mesh adds latency and resource overhead",
                "Alert fatigue if not properly tuned",
            ],
            cost_factors=[
                "EKS cluster: $72/month",
                "EC2 nodes (Karpenter-managed): Standard pricing + Spot discounts",
                "GuardDuty for EKS: approx. $0.012/GB analyzed",
                "Falco: Self-hosted (EC2 costs only)",
                "Security Hub: approx. $1.20/account/month",
                "VPC endpoints: $36/month",
                "Service mesh (if used): Envoy sidecar overhead (~20% more compute)",
                "For 10 nodes: $72 (cluster) + $300 (nodes) + $5 (GuardDuty) + $1.20 (Hub) + $36 (endpoints) = approx. $414/month",
            ],
            monthly_cost_range=(400.00, 2000.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Admission controller enforces security policies",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Service mesh mTLS, secrets encryption with KMS",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="GuardDuty + Falco + Security Hub comprehensive monitoring",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="GitOps provides audit trail for all changes",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Managed Node Groups when:
- Getting started with EKS
- Simple workloads with moderate security needs
- Want AWS to handle node management
- Budget-conscious (lowest cost option)
- Development or staging environment

Choose Fargate Pods when:
- Want serverless Kubernetes (no node management)
- Strong isolation between workloads required
- Intermittent workloads (batch jobs, cron jobs)
- Can accept higher cost for operational simplicity
- Supported workloads (no DaemonSets, privileged containers)

Choose Bottlerocket with Private Endpoint when:
- Production with high security requirements
- Need minimal attack surface
- Want image-based node updates
- Can use VPN/bastion for kubectl access
- Best practice for production EKS

Choose Enterprise with Karpenter when:
- Large-scale EKS (50+ nodes)
- Need fast, intelligent auto-scaling
- Strict compliance requirements (SOC 2, PCI-DSS)
- Want comprehensive runtime security
- Have Kubernetes and GitOps expertise
- Budget supports $400-2000/month
""",
    examples=[
        {
            "scenario": "Development environment for testing Kubernetes deployments",
            "recommendation": "Managed Node Groups with Basic Security",
            "reasoning": "Simple setup. AWS handles node management. Public endpoint simplifies access. Good for learning.",
        },
        {
            "scenario": "Batch processing workload that runs 2 hours per day",
            "recommendation": "Fargate Pods (Serverless)",
            "reasoning": "Intermittent workload doesn't justify 24/7 nodes. Fargate scales to zero. Pay only for compute used.",
        },
        {
            "scenario": "Production SaaS application with 10 microservices",
            "recommendation": "Bottlerocket OS with Private Endpoint",
            "reasoning": "Private endpoint prevents API server exposure. Bottlerocket minimal OS. IRSA for pod-level permissions. Pod Security Standards enforced.",
        },
        {
            "scenario": "Financial services with 50+ microservices and compliance requirements",
            "recommendation": "Enterprise with Karpenter Auto-Scaling",
            "reasoning": "Karpenter optimizes costs. GuardDuty detects threats. GitOps provides audit trail. Network policies enforce segmentation.",
        },
    ],
)


# Pattern 2: IRSA and Pod Security
IRSA_POD_SECURITY_PATTERNS = ArchitectureDecision(
    category="Compute - EKS Security",
    question="What IRSA and Pod security strategy should be implemented?",
    context="""
IAM Roles for Service Accounts (IRSA) provides fine-grained IAM permissions to pods.
Pod Security Standards enforce security controls on pod specifications.

IRSA:
- Eliminates shared node IAM role
- Each pod gets its own IAM role
- Uses OIDC provider for authentication
- Supports least privilege principle

Pod Security Standards:
- Privileged: Unrestricted (not recommended)
- Baseline: Minimally restrictive (blocks known privilege escalations)
- Restricted: Heavily restricted (defense-in-depth)
""",
    options=[
        DecisionOption(
            name="Shared Node IAM Role (Not Recommended)",
            description="""
All pods on a node share the node's IAM role. Simple but violates least privilege.

Configuration:
- Node IAM role has permissions for all workloads
- Pods inherit node role permissions
- No IRSA configuration
- No Pod Security Standards enforcement
- Pods can run privileged

Risk:
- Any compromised pod has full node permissions
- Cannot implement least privilege at pod level
- Difficult to audit which pod performed which action
- Pods can escalate privileges
""",
            pros=[
                "Zero setup required",
                "Simple to understand",
                "No OIDC provider needed",
            ],
            cons=[
                "Violates least privilege principle",
                "Compromised pod has excessive permissions",
                "Cannot restrict permissions per workload",
                "No pod-level audit trail",
                "Pods can run privileged (security risk)",
                "Not recommended for production",
            ],
            cost_factors=[
                "No additional costs",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Weak control - shared IAM role (not recommended)",
                ),
            ],
        ),
        DecisionOption(
            name="IRSA with Basic Pod Security",
            description="""
Enable IRSA for pod-level IAM permissions. Use Baseline Pod Security Standards.

Implementation:
- Enable IRSA on EKS cluster (OIDC provider)
- Create IAM roles for each service account
- Annotate service accounts with IAM role ARN
- Enforce Baseline Pod Security Standard:
  - Blocks privileged containers
  - Blocks hostPath volumes
  - Blocks hostNetwork, hostPID, hostIPC
- Pods run as non-root user (recommended but not enforced)

IRSA setup:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  namespace: production
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/my-app-role
```

IAM role policy (least privilege):
```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject"],
  "Resource": "arn:aws:s3:::my-bucket/*"
}
```

Pod Security Standard (Baseline):
- Prevents privilege escalation
- Blocks dangerous volume types
- Allows non-root containers
""",
            pros=[
                "Pod-level IAM permissions (least privilege)",
                "IRSA provides fine-grained access control",
                "Baseline Pod Security blocks most privilege escalations",
                "CloudTrail logs actions by IAM role (audit trail)",
                "Industry best practice",
            ],
            cons=[
                "Requires OIDC provider setup",
                "IAM role per service account (more to manage)",
                "Baseline allows some insecure configurations",
                "Doesn't enforce non-root containers",
            ],
            cost_factors=[
                "No additional costs (IRSA is free)",
                "OIDC provider is free",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IRSA provides pod-level IAM permissions (least privilege)",
                ),
                SOC2Mapping(
                    control_id="CC6.2",
                    control_name="Authentication",
                    how_it_helps="OIDC authenticates pods to IAM",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Baseline Pod Security prevents privilege escalation",
                ),
            ],
        ),
        DecisionOption(
            name="IRSA with Restricted Pod Security Standards",
            description="""
Enable IRSA with Restricted Pod Security Standards for maximum security.
Restricted profile enforces defense-in-depth.

Implementation:
- All features from IRSA with Basic Pod Security
- Enforce Restricted Pod Security Standard:
  - Must run as non-root user
  - Must drop all capabilities
  - No privilege escalation
  - Read-only root filesystem
  - Allowed volume types only (configMap, downwardAPI, emptyDir, persistentVolumeClaim, projected, secret)
- Automated policy enforcement at admission time
- Security context required for all pods

Restricted Pod Security example:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: my-app:latest
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop: ["ALL"]
      readOnlyRootFilesystem: true
```

Enforcement:
- Built-in admission controller enforces standards
- Non-compliant pods are rejected at creation
- No runtime enforcement needed (prevented at admission)
""",
            pros=[
                "Maximum pod security (defense-in-depth)",
                "Enforces non-root containers",
                "Read-only root filesystem prevents tampering",
                "Drops all capabilities (minimal privileges)",
                "Admission-time enforcement (no runtime overhead)",
                "Best practice for production",
            ],
            cons=[
                "Requires all workloads to be Restricted-compliant",
                "Some third-party charts may need modifications",
                "Read-only filesystem requires planning for temp data",
                "More restrictive (may break legacy workloads)",
            ],
            cost_factors=[
                "No additional costs",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IRSA + Restricted Pod Security enforce least privilege",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Restricted profile enforces defense-in-depth controls",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Admission enforcement prevents insecure deployments",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise with OPA Gatekeeper or Kyverno",
            description="""
Enterprise policy enforcement with OPA Gatekeeper or Kyverno. Custom policies
beyond Pod Security Standards.

Implementation:
- All features from IRSA with Restricted Pod Security
- OPA Gatekeeper or Kyverno for custom policies:
  - Enforce image registries (only ECR allowed)
  - Require resource limits on all containers
  - Enforce naming conventions
  - Require labels (owner, team, cost-center)
  - Block latest tags (require immutable tags)
  - Enforce network policies on all namespaces
- Admission webhooks enforce policies
- Audit mode to test policies before enforcement
- Policy violations logged and alerted

Example custom policies:
1. Required labels: All pods must have owner, team, cost-center labels
2. Image registry: Only images from ECR allowed
3. Resource limits: All containers must have CPU/memory limits
4. Network policies: All namespaces must have NetworkPolicy
5. Immutable tags: latest tag not allowed (require sha256 or semantic version)

OPA Gatekeeper vs. Kyverno:
- OPA Gatekeeper: Rego language, more powerful, steeper learning curve
- Kyverno: YAML policies, easier to learn, Kubernetes-native
""",
            pros=[
                "Custom policies beyond Pod Security Standards",
                "Enforce organizational standards",
                "Prevent configuration drift",
                "Audit mode for testing policies",
                "Policy violations logged for compliance",
                "GitOps-friendly (policies as code)",
            ],
            cons=[
                "Additional complexity (policy engine to manage)",
                "OPA Gatekeeper requires Rego knowledge",
                "Policy conflicts can break deployments",
                "Webhook latency (adds ~10-50ms per request)",
                "Alert fatigue if policies too strict",
            ],
            cost_factors=[
                "OPA Gatekeeper/Kyverno: Self-hosted (EC2 costs only)",
                "  - ~0.1 vCPU, 256 MB per replica (negligible)",
                "No additional AWS costs",
            ],
            monthly_cost_range=(0, 50.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Custom policies enforce least privilege",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Policy violations logged and audited",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Admission policies prevent non-compliant changes",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Shared Node IAM Role when:
- NEVER for production (security anti-pattern)
- Only acceptable for learning/experimentation

Choose IRSA with Basic Pod Security when:
- Production with moderate security requirements
- Need pod-level IAM permissions
- Want to prevent privilege escalation
- Most common choice for production EKS

Choose IRSA with Restricted Pod Security when:
- Production with high security requirements
- Need defense-in-depth
- Can ensure all workloads are Restricted-compliant
- Best practice for production workloads

Choose Enterprise with OPA/Kyverno when:
- Need custom policies beyond Pod Security Standards
- Large organization with many teams
- Want to enforce organizational standards
- GitOps workflow for policy management
- Have expertise in policy engines
""",
    examples=[
        {
            "scenario": "Development EKS cluster for learning Kubernetes",
            "recommendation": "IRSA with Basic Pod Security",
            "reasoning": "Even for dev, use IRSA for best practice learning. Baseline prevents most security issues.",
        },
        {
            "scenario": "Production SaaS application with 5 microservices",
            "recommendation": "IRSA with Restricted Pod Security Standards",
            "reasoning": "Restricted profile enforces non-root, read-only filesystem. IRSA provides pod-level IAM. Best practice.",
        },
        {
            "scenario": "Enterprise with 50+ microservices and multiple teams",
            "recommendation": "Enterprise with OPA Gatekeeper or Kyverno",
            "reasoning": "Custom policies enforce standards (ECR only, resource limits, labels). Prevents configuration drift across teams.",
        },
    ],
)


# Pattern 3: EKS Networking
EKS_NETWORKING_PATTERNS = ArchitectureDecision(
    category="Compute - EKS Security",
    question="What EKS networking strategy should be implemented?",
    context="""
EKS networking includes cluster endpoint access, VPC CNI configuration, and network
policies. Strong networking controls prevent unauthorized access and lateral movement.

Key components:
- Cluster endpoint: Public, private, or both
- VPC CNI: AWS native networking for pods
- Network policies: Control pod-to-pod traffic
- Security groups for pods: Fine-grained network control
- Service mesh: mTLS and advanced traffic management
""",
    options=[
        DecisionOption(
            name="Public Endpoint with Basic Networking",
            description="""
EKS cluster with public endpoint and basic VPC CNI configuration.

Configuration:
- Public cluster endpoint (API server accessible from internet)
- Authorized IP ranges can be configured (recommended)
- VPC CNI for pod networking
- Pods get IP addresses from VPC subnets
- No network policies (all pods can communicate)
- Basic security groups on nodes

Access:
- kubectl works from anywhere (if authorized)
- Nodes in private subnets with NAT Gateway
- Pods can reach internet via NAT Gateway
""",
            pros=[
                "Simple to set up",
                "kubectl works from anywhere",
                "No VPN/bastion required",
                "Good for development",
            ],
            cons=[
                "API server exposed to internet (even with IP restrictions)",
                "No pod-to-pod network segmentation",
                "All pods can communicate (no network policies)",
                "Not recommended for production",
            ],
            cost_factors=[
                "No additional networking costs",
                "NAT Gateway: $32.40/month + data",
            ],
            monthly_cost_range=(35.00, 100.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="API server access can be restricted by IP",
                ),
            ],
        ),
        DecisionOption(
            name="Private Endpoint with VPC CNI",
            description="""
EKS cluster with private endpoint only. API server not accessible from internet.

Implementation:
- Private cluster endpoint only
- API server accessible only from VPC
- VPN or bastion required for kubectl access
- VPC CNI for pod networking
- Pods in private subnets
- VPC endpoints for AWS API access (ECR, CloudWatch, S3)
- No NAT Gateway (use VPC endpoints)

VPC endpoints required:
- ecr.api, ecr.dkr (ECR access)
- logs (CloudWatch Logs)
- s3 (S3 access)
- sts (IAM assume role)
- ec2 (EC2 API)

kubectl access options:
- VPN to VPC
- Bastion host in VPC
- AWS Cloud9 in VPC
- Direct Connect from on-premises
""",
            pros=[
                "API server not exposed to internet",
                "VPC endpoints eliminate NAT Gateway costs",
                "More secure (private communication)",
                "Best practice for production",
            ],
            cons=[
                "Requires VPN/bastion for kubectl access",
                "VPC endpoint costs ($7.20/month each)",
                "More complex setup",
                "All pods can still communicate (no network policies)",
            ],
            cost_factors=[
                "VPC endpoints: $7.20/month × 5 = $36/month",
                "VPC endpoint data: $0.01/GB",
                "No NAT Gateway costs",
                "Bastion or VPN costs (if needed)",
            ],
            monthly_cost_range=(36.00, 100.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Private endpoint prevents internet access to API server",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="VPC endpoints provide private connectivity",
                ),
            ],
        ),
        DecisionOption(
            name="VPC CNI with IP Prefix Delegation",
            description="""
Enable VPC CNI prefix delegation for higher pod density per node. Supports
network policies with Calico.

Implementation:
- Private endpoint
- VPC CNI with prefix delegation:
  - Assigns /28 prefix to each ENI (instead of individual IPs)
  - Increases pods per node significantly
  - Reduces IP exhaustion in subnets
- Calico network policies for pod-to-pod segmentation
- Security groups for pods (fine-grained control)

IP prefix delegation benefits:
- Standard: t3.medium = 17 pods max (limited by IPs)
- Prefix delegation: t3.medium = 110 pods max

Network policies with Calico:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: web
    ports:
    - port: 8080
```

This allows only web pods to reach api pods on port 8080.
""",
            pros=[
                "Higher pod density (more pods per node)",
                "Network policies enable pod-to-pod segmentation",
                "Security groups for pods (fine-grained control)",
                "Reduces IP exhaustion in subnets",
                "Cost savings (fewer nodes needed)",
            ],
            cons=[
                "Requires Calico installation (additional complexity)",
                "Network policies learning curve",
                "Prefix delegation requires VPC CNI v1.9.0+",
                "Must plan network policies before deployment",
            ],
            cost_factors=[
                "VPC endpoints: $36/month",
                "Calico: Self-hosted (EC2 costs only, ~0.2 vCPU per node)",
                "No additional AWS costs",
            ],
            monthly_cost_range=(36.00, 150.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Network policies enforce pod-to-pod access control",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Security groups for pods provide fine-grained control",
                ),
            ],
        ),
        DecisionOption(
            name="Calico Enterprise with Network Policies",
            description="""
Enterprise networking with Calico for advanced network policies, observability,
and threat detection.

Implementation:
- All features from VPC CNI with Prefix Delegation
- Calico network policies for micro-segmentation:
  - Default deny all traffic
  - Explicit allow rules for required communication
  - Namespace isolation
  - Global network policies
- Calico Typha for scalability (100+ nodes)
- Flow logs for network observability
- Threat detection with Calico Deep Packet Inspection
- Integration with GuardDuty for EKS

Network policy layers:
1. Global: Organization-wide policies (e.g., deny all by default)
2. Namespace: Namespace-level policies (e.g., frontend can't reach database)
3. Pod: Pod-level policies (e.g., api can reach database on port 5432 only)

Observability:
- Flow logs show all pod-to-pod communication
- Visualize network topology
- Detect anomalous traffic patterns
- Compliance reporting (which pods communicate)
""",
            pros=[
                "Advanced network policies (global, namespace, pod levels)",
                "Network observability (flow logs, topology visualization)",
                "Threat detection with Deep Packet Inspection",
                "Micro-segmentation (zero-trust networking)",
                "Scales to large clusters (1000+ nodes)",
            ],
            cons=[
                "Calico learning curve (complex policies)",
                "Additional operational overhead",
                "Flow logs generate significant data",
                "Typha required for large clusters (extra resources)",
            ],
            cost_factors=[
                "VPC endpoints: $36/month",
                "Calico: Self-hosted (EC2 costs for Typha, ~1 vCPU)",
                "Flow logs storage: approx. $0.50/GB + S3",
                "GuardDuty for EKS: approx. $0.012/GB",
                "For 20 nodes: approx. $50/month (flow logs + GuardDuty)",
            ],
            monthly_cost_range=(50.00, 300.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Micro-segmentation with network policies",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Default deny with explicit allow rules",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Flow logs provide comprehensive network observability",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Public Endpoint when:
- Development or learning environment
- kubectl access from multiple locations
- Can accept internet exposure (with IP restrictions)
- Not for production

Choose Private Endpoint with VPC CNI when:
- Production with moderate security requirements
- Can use VPN/bastion for kubectl access
- Want to eliminate NAT Gateway costs
- Don't need network policies yet
- Most common choice for production EKS

Choose VPC CNI with Prefix Delegation when:
- Need higher pod density (more pods per node)
- IP exhaustion is a concern
- Want network policies for segmentation
- Cost optimization (fewer nodes)
- Best practice for production at scale

Choose Calico Enterprise when:
- Large-scale EKS (50+ nodes, 100+ pods)
- Need advanced network policies
- Micro-segmentation required (zero-trust)
- Compliance requires network observability
- Have networking and Kubernetes expertise
""",
    examples=[
        {
            "scenario": "Development EKS cluster for testing",
            "recommendation": "Public Endpoint with Basic Networking",
            "reasoning": "Development environment. Public endpoint simplifies access. No production data.",
        },
        {
            "scenario": "Production SaaS application with 10 microservices",
            "recommendation": "Private Endpoint with VPC CNI",
            "reasoning": "Private endpoint prevents internet exposure. VPC endpoints eliminate NAT Gateway. VPN for kubectl access.",
        },
        {
            "scenario": "Production with 50+ microservices and IP exhaustion concerns",
            "recommendation": "VPC CNI with IP Prefix Delegation",
            "reasoning": "Prefix delegation increases pod density. Network policies segment traffic. Calico provides observability.",
        },
        {
            "scenario": "Financial services with 100+ nodes and zero-trust requirements",
            "recommendation": "Calico Enterprise with Network Policies",
            "reasoning": "Micro-segmentation with default deny. Flow logs for compliance. Threat detection with DPI.",
        },
    ],
)


# Export all patterns
__all__ = [
    "EKS_SECURITY_STRATEGY_PATTERNS",
    "IRSA_POD_SECURITY_PATTERNS",
    "EKS_NETWORKING_PATTERNS",
]
