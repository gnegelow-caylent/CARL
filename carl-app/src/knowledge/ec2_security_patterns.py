"""
EC2 Security Patterns for CARL.

Patterns for EC2 instance security, security groups, and patch management.

SOC 2 Relevance:
- CC6.1: Logical and physical access controls
- CC6.6: Encryption of data in transit and at rest
- CC7.2: System monitoring
- CC8.1: Change management (patch management)
"""

from dataclasses import dataclass
from typing import List
from .architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    SOC2Mapping,
)


# Pattern 1: EC2 Instance Security Strategy
EC2_INSTANCE_SECURITY_PATTERNS = ArchitectureDecision(
    category="Compute - EC2 Security",
    question="What EC2 instance security strategy should be implemented?",
    context="""
EC2 instance security encompasses IMDSv2 enforcement, EBS encryption, Systems Manager
access, instance profiles, and security baselines. Strong instance security prevents
unauthorized access, data breaches, and compliance violations.

Key security components:
- IMDSv2 (Instance Metadata Service v2): Protects against SSRF attacks
- EBS encryption: Encrypts data at rest
- Systems Manager Session Manager: Secure shell access without SSH keys
- Instance profiles: IAM roles for EC2 instances
- AMI hardening: CIS benchmarks, minimal software
- CloudWatch agent: Logs and metrics collection
""",
    options=[
        DecisionOption(
            name="Basic Security (Manual Configuration)",
            description="""
Minimal security configuration applied manually when launching instances. Suitable
for development environments or small deployments with infrequent instance launches.

Configuration:
- Manual IMDSv2 enforcement per instance
- EBS encryption enabled per volume
- SSH key-based access
- Manual security group assignment
- Standard AWS AMIs with manual hardening
- Manual CloudWatch agent installation

Security controls:
- Security groups restrict inbound access
- IAM instance profiles for AWS API access
- CloudTrail logs all API calls
- EBS snapshots for backups
""",
            pros=[
                "Simple to implement for small scale",
                "No automation infrastructure required",
                "Full control over each instance",
                "No additional AWS costs beyond instances",
            ],
            cons=[
                "High risk of configuration drift",
                "Manual work for each instance launch",
                "SSH keys difficult to rotate and manage",
                "No enforcement of security baselines",
                "Audit compliance difficult to prove",
                "Scales poorly beyond 5-10 instances",
            ],
            cost_factors=[
                "EC2 instances: Standard pricing",
                "EBS volumes: $0.08-0.10/GB-month (gp3)",
                "CloudWatch Logs: $0.50/GB ingested",
                "No additional tooling costs",
            ],
            monthly_cost_range=(50.00, 500.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="SSH keys and security groups restrict access",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="EBS encryption protects data at rest",
                ),
            ],
        ),
        DecisionOption(
            name="Systems Manager with Golden AMIs",
            description="""
Use Systems Manager for secure access and golden AMIs for consistent hardening.
Eliminates SSH keys, enforces security baselines, and enables centralized management.

Implementation:
- Launch templates enforce IMDSv2, EBS encryption, SSM agent
- Golden AMIs with CIS hardening, CloudWatch agent pre-installed
- Systems Manager Session Manager for shell access (no SSH keys)
- IAM instance profiles with minimal permissions
- Systems Manager Parameter Store for configuration
- Automated patching with Systems Manager Patch Manager

AMI pipeline:
1. Start with base AWS AMI (Amazon Linux 2, Ubuntu, etc.)
2. Apply CIS benchmark hardening (Ansible/Packer)
3. Install CloudWatch agent, SSM agent
4. Remove unnecessary packages
5. Snapshot as golden AMI
6. Automate AMI updates monthly

Access method:
```bash
# No SSH keys needed - uses IAM authentication
aws ssm start-session --target i-1234567890abcdef0
```
""",
            pros=[
                "No SSH keys to manage or rotate",
                "Golden AMIs ensure consistent security posture",
                "Systems Manager provides centralized management",
                "Session Manager sessions logged to CloudWatch/S3",
                "Enforces IMDSv2, EBS encryption via launch templates",
                "Automated patching reduces manual work",
            ],
            cons=[
                "Requires golden AMI pipeline and maintenance",
                "Systems Manager costs for Parameter Store, Session Manager",
                "Initial setup effort to create launch templates and AMIs",
                "AMIs must be updated regularly (security patches)",
            ],
            cost_factors=[
                "EC2 instances: Standard pricing",
                "Systems Manager: $0.00208/hour per managed instance = ~$1.50/instance/month",
                "Parameter Store advanced: $0.05 per 10,000 API calls",
                "Session Manager logging to S3: Storage costs only",
                "Golden AMI storage: $0.05/GB-month per AMI",
                "For 10 instances: $15/month SSM + $5/month AMI storage",
            ],
            monthly_cost_range=(20.00, 100.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM-based access with Session Manager, no SSH keys",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Enforced EBS encryption and data in transit via TLS",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Session Manager logs all shell sessions",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Golden AMIs provide controlled, auditable changes",
                ),
            ],
        ),
        DecisionOption(
            name="Immutable Infrastructure with Auto Scaling",
            description="""
Treat EC2 instances as immutable cattle, not pets. Use Auto Scaling Groups with
launch templates, automated deployments, and automatic replacement instead of
patching running instances.

Implementation:
- Auto Scaling Groups with launch templates (IMDSv2, EBS encryption enforced)
- Golden AMIs updated weekly, automatically deployed
- No SSH/Session Manager access to production (break glass only)
- Application deployment via user data, AMI baking, or container images
- Automated instance replacement for patches (rolling update)
- Instance Scheduler to stop non-prod instances

Instance lifecycle:
1. Build golden AMI with application baked in
2. Launch template references latest AMI
3. Auto Scaling Group launches instances
4. Instances serve traffic (no manual changes)
5. New AMI triggers rolling replacement
6. Old instances terminated

For updates:
- New AMI → Auto Scaling Group rolling update → Old instances replaced
- No patching of running instances
- Configuration via user data or Parameter Store
""",
            pros=[
                "Maximum security - immutable instances can't be modified",
                "Automatic recovery from instance failures",
                "Consistent deployments (no configuration drift)",
                "Easy rollback (revert to previous AMI)",
                "No SSH access needed (reduces attack surface)",
                "Scales automatically based on demand",
            ],
            cons=[
                "Higher complexity (Auto Scaling, AMI pipeline, deployment automation)",
                "Longer deployment time (must bake new AMI for changes)",
                "Requires robust CI/CD pipeline",
                "Stateful applications need external state storage",
                "More AWS costs (Auto Scaling, ALB, AMI storage)",
            ],
            cost_factors=[
                "EC2 instances: Standard pricing",
                "Application Load Balancer: $16/month + $0.008/LCU-hour",
                "Auto Scaling: No additional cost",
                "Golden AMI storage: $0.05/GB-month per AMI × number of AMIs",
                "Systems Manager (break glass only): ~$1/instance/month",
                "For 10 instances + ALB: $16 (ALB) + $10 (AMIs) = $26/month overhead",
            ],
            monthly_cost_range=(50.00, 300.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="No direct access to production instances (immutable)",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Enforced EBS encryption, data in transit via ALB",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Auto Scaling ensures high availability",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="All changes via controlled AMI pipeline and deployments",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Security with Compliance Automation",
            description="""
Comprehensive EC2 security with automated compliance checking, remediation, and
advanced security controls. Implements defense-in-depth with multiple security layers.

Implementation:
- All features from Immutable Infrastructure option
- AWS Config rules enforce security requirements:
  - ec2-instance-managed-by-systems-manager
  - ec2-imdsv2-check
  - encrypted-volumes
  - ec2-instance-no-public-ip
  - approved-amis-by-id
- Security Hub for aggregated security findings
- Inspector for vulnerability scanning
- GuardDuty for threat detection
- AWS Systems Manager Compliance for patch compliance
- Automated remediation for non-compliant instances

Advanced security controls:
- IMDSv2 required (enforced by launch template + Config rule)
- EBS encryption enforced (launch template + Config rule + SCP)
- No public IPs allowed (VPC + Config rule)
- AMI approval process (only whitelisted AMIs can be launched)
- Runtime security monitoring (GuardDuty)
- Vulnerability scanning (Inspector)
- Session Manager with logging to S3 (auditable access)

Compliance automation:
- Config rules detect non-compliance
- Lambda functions auto-remediate or alert
- Security Hub provides dashboard
- Automated evidence collection for audits
""",
            pros=[
                "Continuous compliance monitoring and enforcement",
                "Automated detection and remediation of security issues",
                "Defense-in-depth with multiple security layers",
                "Comprehensive audit trail for compliance",
                "Vulnerability scanning and threat detection",
                "Meets strictest compliance requirements (SOC 2, PCI-DSS, HIPAA)",
            ],
            cons=[
                "High complexity requires dedicated security team",
                "Significant AWS costs for security services",
                "Alert fatigue if not properly tuned",
                "Requires automation expertise (Lambda, EventBridge, Config)",
                "Overkill for small organizations",
            ],
            cost_factors=[
                "EC2 instances: Standard pricing",
                "Systems Manager: ~$1.50/instance/month",
                "Config rules: $2/rule/region × 5 rules = $10/month",
                "Security Hub: ~$1.20/account/month",
                "GuardDuty: ~$4-10/account/month",
                "Inspector: ~$0.10-1/instance/month (depends on scan frequency)",
                "Application Load Balancer: $16/month",
                "Lambda for remediation: ~$5/month",
                "For 20 instances: $30 (SSM) + $10 (Config) + $1.20 (Security Hub) + $10 (GuardDuty) + $20 (Inspector) + $16 (ALB) + $5 (Lambda) = ~$92/month overhead",
            ],
            monthly_cost_range=(100.00, 500.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Multi-layered access controls with Session Manager logging",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Enforced encryption at rest and in transit with automated checks",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Comprehensive monitoring with Security Hub, GuardDuty, Inspector",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Auto Scaling with health checks ensures availability",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Automated compliance checks and controlled change process",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Risk assessment",
                    how_it_helps="Continuous vulnerability scanning and threat detection",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Basic Security when:
- Very small deployment (<5 instances)
- Development or test environment
- Infrequent instance launches
- Limited budget and team expertise
- Can tolerate manual security configuration

Choose Systems Manager with Golden AMIs when:
- 5-50 instances
- Need consistent security baselines
- Want to eliminate SSH key management
- Production environment with moderate security requirements
- Have resources to maintain golden AMI pipeline
- Most common choice for production workloads

Choose Immutable Infrastructure when:
- 20+ instances
- High availability requirements
- Modern DevOps practices
- Stateless or containerized applications
- Can invest in CI/CD automation
- Want zero configuration drift

Choose Enterprise Security when:
- 50+ instances
- Strict compliance requirements (SOC 2, PCI-DSS, HIPAA)
- Need automated compliance reporting
- Large organization with dedicated security team
- Budget supports $100-500/month for security tooling
- Requires continuous security monitoring and automated remediation
""",
    examples=[
        {
            "scenario": "Startup with 3 EC2 instances for web application",
            "recommendation": "Basic Security",
            "reasoning": "Small scale doesn't justify automation overhead. Use launch templates for IMDSv2/encryption, SSH keys for access.",
        },
        {
            "scenario": "Mid-size company with 20 EC2 instances",
            "recommendation": "Systems Manager with Golden AMIs",
            "reasoning": "Golden AMIs ensure consistency. Session Manager eliminates SSH key management. Systems Manager Patch Manager automates patching.",
        },
        {
            "scenario": "SaaS platform with Auto Scaling web tier",
            "recommendation": "Immutable Infrastructure with Auto Scaling",
            "reasoning": "Immutable instances prevent drift. Auto Scaling handles traffic spikes. AMI pipeline enables rapid deployments.",
        },
        {
            "scenario": "Financial services company with 100+ EC2 instances and PCI-DSS requirements",
            "recommendation": "Enterprise Security with Compliance Automation",
            "reasoning": "Compliance automation provides evidence for audits. Config rules enforce PCI-DSS requirements. Security Hub aggregates findings.",
        },
    ],
)


# Pattern 2: Security Group Design Strategy
SECURITY_GROUP_PATTERNS = ArchitectureDecision(
    category="Compute - EC2 Security",
    question="What security group design strategy should be implemented?",
    context="""
Security groups act as stateful firewalls controlling inbound and outbound traffic
to EC2 instances. Proper security group design is critical for security, compliance,
and operational efficiency.

Design considerations:
- Granularity: Application-level vs. role-based vs. micro-segmentation
- Source specification: CIDR blocks vs. security group references
- Egress rules: Restrictive vs. allow-all
- Naming convention: Consistent, descriptive names
- Rule limits: 60 rules per security group, 5 security groups per ENI

Common mistakes:
- 0.0.0.0/0 on inbound ports (open to internet)
- Security groups named "default", "test", "sg-12345"
- No documentation of rule purpose
- Egress allow-all when not needed
""",
    options=[
        DecisionOption(
            name="Simple Application-Level Security Groups",
            description="""
Create one security group per application tier (web, app, database). Simple to
understand and manage, suitable for small deployments.

Structure:
- web-sg: Allow 80/443 from 0.0.0.0/0, allow 22/3389 from bastion-sg
- app-sg: Allow 8080 from web-sg, allow 22/3389 from bastion-sg
- db-sg: Allow 5432/3306 from app-sg
- bastion-sg: Allow 22/3389 from office-ip/VPN-ip

Example web-sg rules:
- Inbound:
  - Port 80 (HTTP): 0.0.0.0/0 or ALB security group
  - Port 443 (HTTPS): 0.0.0.0/0 or ALB security group
  - Port 22 (SSH): bastion-sg
- Outbound:
  - All traffic: 0.0.0.0/0
""",
            pros=[
                "Simple to understand and implement",
                "Easy to troubleshoot connectivity issues",
                "Minimal number of security groups to manage",
                "Works well for small, simple architectures",
            ],
            cons=[
                "Too permissive for complex applications",
                "All web servers share same rules (no differentiation)",
                "Difficult to implement least privilege",
                "Scales poorly beyond basic 3-tier architecture",
                "Egress allow-all violates security best practices",
            ],
            cost_factors=["No cost for security groups"],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Security groups restrict network access to instances",
                ),
            ],
        ),
        DecisionOption(
            name="Role-Based Security Groups with Restrictive Egress",
            description="""
Create security groups based on instance roles and implement restrictive egress rules.
Enforces least privilege at network layer.

Structure:
- Load balancer tier:
  - alb-public-sg: 80/443 from 0.0.0.0/0
  - alb-internal-sg: 80/443 from VPC CIDR

- Application tier:
  - app-web-sg: 8080 from alb-public-sg
  - app-api-sg: 8000 from alb-internal-sg
  - app-worker-sg: No inbound, egress to SQS/SNS

- Data tier:
  - db-postgres-sg: 5432 from app-web-sg, app-api-sg
  - db-redis-sg: 6379 from app-web-sg, app-api-sg
  - db-s3-sg: 443 to S3 prefix list

- Management tier:
  - bastion-sg: 22/3389 from office-ip
  - monitoring-sg: 9090/3000 from VPC CIDR

Restrictive egress rules (deny by default):
- app-web-sg egress:
  - Port 5432 to db-postgres-sg (database)
  - Port 6379 to db-redis-sg (cache)
  - Port 443 to S3 prefix list (S3 VPC endpoint)
  - Port 443 to 0.0.0.0/0 (external APIs)
- app-worker-sg egress:
  - Port 443 to SQS/SNS prefix lists
  - Port 5432 to db-postgres-sg

Naming convention:
{environment}-{tier}-{purpose}-sg
Examples: prod-app-web-sg, staging-db-postgres-sg
""",
            pros=[
                "Least privilege network access",
                "Clear separation of concerns",
                "Restrictive egress prevents data exfiltration",
                "Scales to complex multi-tier architectures",
                "Easy to audit (clear role-based naming)",
            ],
            cons=[
                "More security groups to manage (10-20 per environment)",
                "Requires planning and documentation",
                "Troubleshooting connectivity requires understanding SG relationships",
                "Initial setup effort to define all rules",
            ],
            cost_factors=["No cost for security groups"],
            monthly_cost_range=(0, 0),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Role-based security groups enforce least privilege access",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Restrictive egress prevents unauthorized data access",
                ),
            ],
        ),
        DecisionOption(
            name="Micro-Segmentation with Security Group Chaining",
            description="""
Implement fine-grained network segmentation with security groups for each service
or microservice. Enforces zero-trust networking at AWS level.

Structure:
- One security group per service (microservices)
- Security group chaining for service-to-service communication
- VPC endpoint security groups for AWS services
- No 0.0.0.0/0 egress rules (deny-by-default)

Example for microservices architecture:
- user-service-sg:
  - Inbound: Port 8001 from api-gateway-sg
  - Outbound: Port 5432 to user-db-sg, Port 8003 to auth-service-sg

- auth-service-sg:
  - Inbound: Port 8003 from user-service-sg, order-service-sg
  - Outbound: Port 6379 to auth-cache-sg

- order-service-sg:
  - Inbound: Port 8002 from api-gateway-sg
  - Outbound: Port 5432 to order-db-sg, Port 8003 to auth-service-sg, Port 8004 to payment-service-sg

VPC endpoint security groups:
- vpce-s3-sg: Port 443 from app security groups
- vpce-dynamodb-sg: Port 443 from app security groups
- vpce-secrets-sg: Port 443 from app security groups

Security group management:
- Terraform/CloudFormation for infrastructure-as-code
- Automated documentation generation
- Security group usage tracking (AWS Config)
- Unused security group cleanup (Lambda)
""",
            pros=[
                "Maximum security - zero-trust networking",
                "Each service has minimal required access",
                "Easy to add/remove services without affecting others",
                "Supports complex microservices architectures",
                "Prevents lateral movement in case of compromise",
            ],
            cons=[
                "High complexity (50-100+ security groups)",
                "Requires automation (Terraform/CloudFormation essential)",
                "Difficult to manage manually",
                "Troubleshooting connectivity is challenging",
                "Requires comprehensive documentation",
            ],
            cost_factors=["No cost for security groups"],
            monthly_cost_range=(0, 0),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Micro-segmentation enforces zero-trust networking",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Each service has minimal network access (least privilege)",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Security Group Governance",
            description="""
Comprehensive security group management with automated compliance, monitoring,
and governance. Implements security group lifecycle management and automated remediation.

Implementation:
- All features from Micro-Segmentation option
- Automated security group compliance:
  - AWS Config rules:
    - vpc-sg-open-only-to-authorized-ports (detect 0.0.0.0/0 on sensitive ports)
    - vpc-sg-restricted-common-ports (no RDP/SSH from 0.0.0.0/0)
    - unused-security-groups (detect unused SGs)
  - Security Hub findings aggregation
  - Automated remediation for non-compliant rules

- Security group lifecycle:
  - Automated creation via Terraform/CloudFormation
  - Approval workflow for manual changes (Lambda + SNS)
  - Automated documentation (description required, auto-generated docs)
  - Quarterly security group review and cleanup
  - Security group usage metrics (CloudWatch custom metrics)

- Advanced monitoring:
  - VPC Flow Logs analyze accepted/rejected traffic
  - GuardDuty detects malicious traffic patterns
  - CloudWatch Insights analyze flow logs for anomalies
  - Automated alerts for suspicious traffic (Lambda)

- Security group tagging:
  - Environment: prod, staging, dev
  - Owner: team-name
  - Application: app-name
  - Compliance: pci-dss, hipaa
  - ReviewDate: 2026-Q1

Governance process:
1. Security groups created via IaC (Terraform)
2. Config rules enforce compliance
3. Manual changes trigger approval workflow
4. Quarterly review identifies unused SGs
5. Automated cleanup removes unused SGs
6. Audit reports generated monthly
""",
            pros=[
                "Continuous compliance monitoring",
                "Automated detection and remediation",
                "Comprehensive audit trail for compliance",
                "Security group lifecycle management",
                "Prevents security group sprawl",
                "Meets strictest compliance requirements",
            ],
            cons=[
                "Very high complexity",
                "Requires dedicated team to maintain",
                "Significant automation development effort",
                "Alert fatigue if not properly tuned",
                "Overkill for small organizations",
            ],
            cost_factors=[
                "Config rules: $2/rule/region × 3 rules = $6/month",
                "Security Hub: ~$1.20/account/month",
                "GuardDuty: ~$4-10/account/month",
                "VPC Flow Logs: ~$0.50/GB + S3 storage",
                "Lambda for automation: ~$5-10/month",
                "CloudWatch Logs Insights: ~$0.005/GB scanned",
                "Total: ~$20-50/month for security group governance",
            ],
            monthly_cost_range=(20.00, 50.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Automated governance ensures least privilege access",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access to configurations",
                    how_it_helps="Continuous monitoring and compliance enforcement",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="VPC Flow Logs and GuardDuty monitor all network traffic",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="All security group changes tracked and auditable",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Simple Application-Level when:
- Simple 3-tier architecture (web, app, database)
- Small deployment (<10 instances)
- Development or test environment
- Team new to AWS networking
- Want minimal complexity

Choose Role-Based with Restrictive Egress when:
- Multi-tier architecture with 10-50 instances
- Production environment with moderate security requirements
- Need least privilege network access
- Have resources to implement restrictive egress rules
- Most common choice for production workloads

Choose Micro-Segmentation when:
- Microservices architecture (10+ services)
- High security requirements (zero-trust networking)
- Using infrastructure-as-code (Terraform/CloudFormation)
- Need to prevent lateral movement
- Large deployment (50+ instances)

Choose Enterprise Security Group Governance when:
- Large organization (100+ instances)
- Strict compliance requirements (SOC 2, PCI-DSS, HIPAA)
- Need automated compliance reporting
- Security group sprawl is a problem
- Have dedicated security team
- Budget supports $20-50/month for governance tooling
""",
    examples=[
        {
            "scenario": "WordPress site with web server and RDS database",
            "recommendation": "Simple Application-Level Security Groups",
            "reasoning": "web-sg allows 80/443, db-sg allows 3306 from web-sg. Simple and sufficient.",
        },
        {
            "scenario": "E-commerce application with web, API, and database tiers",
            "recommendation": "Role-Based with Restrictive Egress",
            "reasoning": "Role-based SGs for each tier. Restrictive egress prevents unauthorized external access.",
        },
        {
            "scenario": "Microservices platform with 20 services",
            "recommendation": "Micro-Segmentation with Security Group Chaining",
            "reasoning": "Each service gets dedicated security group. Service-to-service communication explicitly allowed.",
        },
        {
            "scenario": "Financial services company with 200+ EC2 instances and PCI-DSS requirements",
            "recommendation": "Enterprise Security Group Governance",
            "reasoning": "Automated compliance checks required for PCI-DSS. Config rules detect non-compliance. Audit reports for auditors.",
        },
    ],
)


# Pattern 3: EC2 Patch Management Strategy
EC2_PATCH_MANAGEMENT_PATTERNS = ArchitectureDecision(
    category="Compute - EC2 Security",
    question="What EC2 patch management strategy should be implemented?",
    context="""
Patch management ensures EC2 instances receive security updates and bug fixes.
Unpatched systems are a leading cause of security breaches and compliance violations.

Patching approaches:
- Manual: SSH to instances and run package updates
- Systems Manager Patch Manager: Automated patching with maintenance windows
- Immutable infrastructure: Replace instances with new AMIs

Patch types:
- Security patches: Critical vulnerabilities (apply ASAP)
- Bug fixes: Non-security fixes (apply during maintenance window)
- Feature updates: New features (evaluate before applying)

Compliance requirements:
- PCI-DSS: Critical patches within 30 days
- SOC 2: Timely patching documented in controls
- HIPAA: Security patches within 30 days
""",
    options=[
        DecisionOption(
            name="Manual Patching",
            description="""
Manually SSH to instances and run package updates. Suitable only for very small
deployments with infrequent patching needs.

Process:
1. Review available patches monthly
2. SSH to each instance
3. Run package manager updates:
   - Amazon Linux: sudo yum update -y
   - Ubuntu: sudo apt update && sudo apt upgrade -y
4. Reboot if kernel updated
5. Document patching in spreadsheet

No automation, no enforcement, relies on manual processes.
""",
            pros=[
                "No automation infrastructure required",
                "Full control over when patches are applied",
                "No additional AWS costs",
            ],
            cons=[
                "High risk of missed patches",
                "Manual work for each instance",
                "No audit trail (difficult to prove compliance)",
                "Scales terribly (1 hour per 5-10 instances)",
                "Reboots cause downtime if not coordinated",
                "Human error likely (forget instances, skip steps)",
            ],
            cost_factors=["No additional costs beyond staff time"],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Manual patch process (weak control - no enforcement)",
                ),
            ],
        ),
        DecisionOption(
            name="Systems Manager Patch Manager (Basic)",
            description="""
Use AWS Systems Manager Patch Manager for automated patching during maintenance
windows. Patches are applied automatically on schedule.

Implementation:
- Create patch baseline (what patches to install)
  - Security patches: Install all
  - Bug fixes: Install all
  - Feature updates: Manual approval
- Create maintenance window (when to patch)
  - Non-prod: Saturday 2 AM UTC
  - Prod: Sunday 2 AM UTC, rolling by AZ
- Configure Patch Manager to scan and install patches
- Reboot instances after patching if needed
- Review patch compliance in Systems Manager console

Patch baseline options:
- AWS-DefaultPatchBaseline: Install all patches
- Custom baseline: Select specific patch types/severities

Maintenance window:
- Schedule: cron expression (e.g., cron(0 2 ? * SUN *))
- Duration: 4 hours
- Targets: All instances with tag Environment=prod
- Tasks: AWS-RunPatchBaseline
""",
            pros=[
                "Automated patching on schedule (no manual work)",
                "Patch compliance visible in console",
                "Supports maintenance windows (patch during off-hours)",
                "Can patch by tag, instance ID, or resource group",
                "Audit trail in CloudTrail and Systems Manager",
                "Reboot coordination (patch rolling by AZ)",
            ],
            cons=[
                "Systems Manager agent required on all instances",
                "Maintenance windows must be configured per environment",
                "No automated testing before production patching",
                "Reboots still cause downtime (if not using Auto Scaling)",
                "Requires Systems Manager costs (~$1.50/instance/month)",
            ],
            cost_factors=[
                "Systems Manager Patch Manager: No additional cost beyond Systems Manager",
                "Systems Manager: ~$1.50/instance/month",
                "For 20 instances: $30/month",
            ],
            monthly_cost_range=(10.00, 100.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Automated patching on schedule with audit trail",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Patch compliance tracking in Systems Manager",
                ),
            ],
        ),
        DecisionOption(
            name="Immutable Infrastructure with Golden AMIs",
            description="""
Eliminate runtime patching by replacing instances with new golden AMIs containing
latest patches. Combines patching with deployment process.

Process:
1. Weekly: Build new golden AMI with latest patches
   - Start with base AWS AMI
   - Run package updates (yum/apt update)
   - Apply CIS hardening
   - Install application
   - Snapshot as new golden AMI
   - Tag with version and date

2. Deploy new AMI:
   - Update launch template with new AMI ID
   - Auto Scaling Group performs rolling update
   - Old instances terminated
   - New instances launched with patched AMI

3. Rollback if issues:
   - Update launch template to previous AMI
   - Rolling update back to old AMI

Example pipeline:
- Sunday: Build golden AMI with latest patches
- Monday: Deploy to dev environment (auto)
- Wednesday: Deploy to staging environment (auto)
- Friday: Deploy to prod environment (manual approval)

No runtime patching:
- Instances never patched after launch
- All patches via new AMI deployment
- Immutable infrastructure (cattle not pets)
""",
            pros=[
                "Zero runtime patching (no maintenance windows needed)",
                "Consistent deployments (every instance identical)",
                "Easy rollback (revert to previous AMI)",
                "No reboot coordination needed (rolling replacement)",
                "Testing built in (dev → staging → prod)",
                "Patches deployed same way as application code",
            ],
            cons=[
                "Requires AMI build pipeline (Packer, Jenkins, etc.)",
                "Longer deployment time (build AMI + rolling update)",
                "More complex than Patch Manager",
                "Requires Auto Scaling Groups",
                "AMI storage costs ($0.05/GB-month per AMI)",
                "Weekly AMI builds even if no patches",
            ],
            cost_factors=[
                "Systems Manager: ~$1.50/instance/month (for Session Manager only)",
                "AMI storage: $0.05/GB-month × AMI size × number of AMIs",
                "  - 8 GB AMI × 4 versions = $1.60/month",
                "CI/CD pipeline: EC2 build instance or CodeBuild",
                "  - CodeBuild: $0.005/build-minute, ~30 min/build = $0.15/build",
                "  - Weekly builds: ~$0.60/month",
                "For 20 instances: $30 (SSM) + $2 (AMIs) + $3 (builds) = $35/month",
            ],
            monthly_cost_range=(30.00, 150.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Controlled deployment process with testing and rollback",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Rolling updates ensure zero downtime",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise Patch Management with Compliance Automation",
            description="""
Comprehensive patch management with automated compliance checking, testing,
emergency patching, and integration with vulnerability management.

Implementation:
- Immutable infrastructure with golden AMIs (weekly builds)
- Systems Manager for break-glass emergency patching
- Automated vulnerability scanning:
  - Inspector scans for software vulnerabilities
  - Alert on critical CVEs within 24 hours
  - Emergency patch process for critical CVEs (< 7 days)
- Patch compliance monitoring:
  - Config rules track patch compliance
  - Security Hub aggregates patch findings
  - Automated alerts for out-of-compliance instances
  - Non-compliant instances automatically replaced

Emergency patching workflow:
1. Inspector detects critical CVE
2. EventBridge triggers Lambda
3. Lambda creates incident ticket (ServiceNow/Jira)
4. Security team triages severity
5. If critical:
   - Build emergency AMI with patch
   - Deploy to dev/staging immediately
   - Test for 24 hours
   - Deploy to prod with rolling update
6. Document in compliance database

Regular patching:
- Weekly: Build AMI with all latest patches
- Deploy: dev (Mon) → staging (Wed) → prod (Fri)
- Config rules ensure instances < 14 days old

Compliance reporting:
- Monthly compliance dashboard (% of instances patched)
- Patch deployment timeline (critical patches < 7 days)
- Audit reports for SOC 2 / PCI-DSS compliance
- Evidence collection automated
""",
            pros=[
                "Meets strictest compliance requirements (SOC 2, PCI-DSS, HIPAA)",
                "Automated vulnerability detection and remediation",
                "Emergency patching process for critical CVEs",
                "Comprehensive audit trail for compliance",
                "Patch compliance enforced (non-compliant instances replaced)",
                "Integration with enterprise ITSM (ServiceNow, Jira)",
            ],
            cons=[
                "Very high complexity",
                "Requires dedicated team to maintain",
                "Significant tooling costs (Inspector, Config, Security Hub)",
                "Alert fatigue if not properly tuned",
                "Overkill for small organizations",
            ],
            cost_factors=[
                "Systems Manager: ~$1.50/instance/month",
                "Inspector: ~$0.10-1/instance/month (weekly scans)",
                "Config rules: $2/rule/region × 2 rules = $4/month",
                "Security Hub: ~$1.20/account/month",
                "AMI storage: ~$2/month",
                "CI/CD pipeline: ~$5/month",
                "Lambda for automation: ~$5/month",
                "For 50 instances: $75 (SSM) + $50 (Inspector) + $4 (Config) + $1.20 (Hub) + $12 (other) = ~$142/month",
            ],
            monthly_cost_range=(100.00, 500.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Automated patch deployment with comprehensive audit trail",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Continuous vulnerability scanning and patch compliance monitoring",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Rolling updates and automated recovery ensure availability",
                ),
                SOC2Mapping(
                    control_id="A1.2",
                    control_name="Risk assessment",
                    how_it_helps="Vulnerability scanning identifies risks, emergency patching remediates",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Manual Patching when:
- Very small deployment (< 5 instances)
- Non-production environment only
- Infrequent patching acceptable (quarterly)
- No compliance requirements
- Limited budget

Choose Systems Manager Patch Manager when:
- 5-50 instances
- Need automated patching on schedule
- Production environment with maintenance windows
- Moderate compliance requirements
- Can tolerate brief downtime for reboots
- Most common choice for traditional EC2 deployments

Choose Immutable Infrastructure when:
- Using Auto Scaling Groups already
- Want zero-downtime patching
- Modern DevOps practices
- Can invest in AMI pipeline
- Want consistent deployments (no configuration drift)
- 20+ instances

Choose Enterprise Patch Management when:
- 50+ instances
- Strict compliance requirements (PCI-DSS < 30 days, SOC 2)
- Need emergency patching process
- Continuous vulnerability scanning required
- Have dedicated security team
- Budget supports $100-500/month for tooling
""",
    examples=[
        {
            "scenario": "Development environment with 3 EC2 instances",
            "recommendation": "Manual Patching",
            "reasoning": "Small scale, non-prod. Monthly manual patching acceptable.",
        },
        {
            "scenario": "Production web application with 15 EC2 instances",
            "recommendation": "Systems Manager Patch Manager",
            "reasoning": "Automate patching during Sunday 2 AM maintenance window. Patch rolling by AZ to minimize downtime.",
        },
        {
            "scenario": "SaaS platform with Auto Scaling web tier",
            "recommendation": "Immutable Infrastructure with Golden AMIs",
            "reasoning": "Already using Auto Scaling. Build weekly AMI with patches. Rolling update with zero downtime.",
        },
        {
            "scenario": "Financial services with PCI-DSS requirement (critical patches < 30 days)",
            "recommendation": "Enterprise Patch Management",
            "reasoning": "Inspector scans for CVEs. Emergency patching for critical vulnerabilities. Config rules enforce compliance. Audit reports for PCI assessors.",
        },
    ],
)


# Export all patterns
__all__ = [
    "EC2_INSTANCE_SECURITY_PATTERNS",
    "SECURITY_GROUP_PATTERNS",
    "EC2_PATCH_MANAGEMENT_PATTERNS",
]
