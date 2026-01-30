"""
Lambda Security Patterns for CARL.

Patterns for AWS Lambda security, secrets management, and networking.

SOC 2 Relevance:
- CC6.1: Logical and physical access controls
- CC6.6: Encryption and restricted access
- CC6.7: Transmission security
- CC7.2: System monitoring
"""

from dataclasses import dataclass
from typing import List
from .architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    SOC2Mapping,
)


# Pattern 1: Lambda Security Strategy
LAMBDA_SECURITY_STRATEGY_PATTERNS = ArchitectureDecision(
    category="Compute - Lambda Security",
    question="What Lambda security strategy should be implemented?",
    context="""
Lambda security encompasses execution roles, VPC configuration, reserved concurrency,
and access control. Strong Lambda security prevents unauthorized access and resource
exhaustion.

Key security components:
- Execution role: IAM role with minimal permissions
- VPC Lambda: Deploy functions in VPC for private resource access
- Reserved concurrency: Prevent function from consuming all account concurrency
- Resource policies: Control who can invoke functions
- Environment encryption: Encrypt environment variables with KMS
- Code signing: Verify function code integrity
""",
    options=[
        DecisionOption(
            name="Basic Execution Role (Public Lambda)",
            description="""
Lambda function with basic execution role and no VPC configuration. Function
runs in AWS-managed VPC with internet access.

Configuration:
- Basic execution role:
  - logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents
  - Additional permissions for AWS services (S3, DynamoDB)
- No VPC configuration (public Lambda)
- Environment variables for configuration
- CloudWatch Logs for logging
- No reserved concurrency (shares account limit)

Access:
- Function has internet access (can call external APIs)
- Cannot access VPC resources (RDS, ElastiCache)
- Invoked via API Gateway, S3 events, or direct invocation
""",
            pros=[
                "Simple to configure",
                "Fast cold starts (no VPC ENI creation)",
                "Internet access included",
                "No VPC management required",
            ],
            cons=[
                "Cannot access VPC resources directly",
                "Environment variables not encrypted by default",
                "No concurrency limits (can exhaust account quota)",
                "Shared execution environment (less isolation)",
            ],
            cost_factors=[
                "Lambda: $0.20 per 1M requests + compute time",
                "  - 128 MB, 100ms = $0.0000002083 per invocation",
                "CloudWatch Logs: $0.50/GB",
                "For 1M requests/month: $0.20 (requests) + approx. $2 (compute) = $2.20/month",
            ],
            monthly_cost_range=(5.00, 100.00),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM execution role restricts function permissions",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch Logs capture function activity",
                ),
            ],
        ),
        DecisionOption(
            name="VPC Lambda with Private Resource Access",
            description="""
Lambda function deployed in VPC to access private resources like RDS or ElastiCache.
Uses VPC endpoints for AWS service access.

Implementation:
- Lambda in VPC private subnets
- Security group allows outbound to RDS, ElastiCache
- VPC endpoints for AWS services (S3, DynamoDB, Secrets Manager):
  - No NAT Gateway required
  - Private connectivity to AWS services
- Execution role with VPC permissions:
  - ec2:CreateNetworkInterface
  - ec2:DescribeNetworkInterfaces
  - ec2:DeleteNetworkInterface
- Environment encryption with KMS
- CloudWatch Logs via VPC endpoint

VPC Lambda workflow:
1. Cold start: Creates ENI in VPC subnets (~10 seconds)
2. Function connects to RDS via private IP
3. AWS SDK calls go through VPC endpoints
4. Logs sent to CloudWatch via VPC endpoint

VPC endpoints needed:
- s3 (gateway endpoint, free)
- dynamodb (gateway endpoint, free)
- secretsmanager ($7.20/month)
- logs ($7.20/month)
""",
            pros=[
                "Access to VPC resources (RDS, ElastiCache)",
                "Private connectivity (no internet exposure)",
                "VPC endpoints eliminate NAT Gateway costs",
                "Security groups control network access",
                "Environment encryption with KMS",
            ],
            cons=[
                "Slower cold starts (~10 seconds for ENI creation)",
                "VPC endpoint costs (approx. $15-30/month)",
                "More complex configuration",
                "Cannot access internet without NAT Gateway or proxy",
            ],
            cost_factors=[
                "Lambda: Standard pricing (no VPC surcharge)",
                "VPC endpoints: $7.20/month × 2 (secrets, logs) = $14.40/month",
                "KMS key: $1/month",
                "For 1M requests: $2.20 (Lambda) + $14.40 (endpoints) + $1 (KMS) = $17.60/month",
            ],
            monthly_cost_range=(20.00, 150.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="VPC security groups restrict network access",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="KMS encrypts environment variables",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="Private VPC connectivity, no internet exposure",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudWatch Logs via VPC endpoint",
                ),
            ],
        ),
        DecisionOption(
            name="VPC Lambda with Reserved Concurrency",
            description="""
VPC Lambda with reserved concurrency to prevent resource exhaustion and ensure
predictable performance.

Implementation:
- All features from VPC Lambda
- Reserved concurrency per function:
  - Guarantees available concurrency
  - Prevents function from consuming all account quota
  - Example: Reserve 50 concurrent executions
- Provisioned concurrency for latency-sensitive functions:
  - Pre-initialized execution environments (no cold starts)
  - Cost: $0.015/GB-hour
- Dead Letter Queue (SQS or SNS) for failed invocations
- X-Ray tracing for observability
- CloudWatch alarms for throttling, errors

Reserved vs. Provisioned concurrency:
- Reserved: Guarantees max concurrency, but cold starts still occur
- Provisioned: Pre-warmed instances, no cold starts, higher cost

Example configuration:
- Function A: Reserved 50, Provisioned 10 (99% traffic)
- Function B: Reserved 20, Provisioned 5 (high priority)
- Function C: Reserved 10, Provisioned 0 (batch processing)
""",
            pros=[
                "Prevents resource exhaustion attacks",
                "Predictable performance with provisioned concurrency",
                "Dead Letter Queue captures failed invocations",
                "X-Ray provides end-to-end tracing",
                "Alarms alert on throttling or errors",
            ],
            cons=[
                "Provisioned concurrency adds significant cost",
                "Must estimate concurrency needs (over-provision = waste)",
                "Increased complexity (concurrency management)",
            ],
            cost_factors=[
                "Lambda: Standard pricing",
                "Reserved concurrency: Free (just a limit)",
                "Provisioned concurrency: $0.015/GB-hour",
                "  - 128 MB, 10 instances = $0.01875/hour = $13.50/month",
                "X-Ray: $5 per 1M traces + $0.50/million scanned",
                "DLQ (SQS): $0.40 per 1M requests (negligible)",
                "For 1M requests + 10 provisioned: $2.20 (requests) + $13.50 (provisioned) + $15 (endpoints) + $1 (KMS) = $31.70/month",
            ],
            monthly_cost_range=(30.00, 300.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Reserved concurrency prevents resource exhaustion",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="X-Ray tracing and CloudWatch alarms",
                ),
                SOC2Mapping(
                    control_id="CC7.3",
                    control_name="System availability",
                    how_it_helps="Provisioned concurrency ensures predictable performance",
                ),
            ],
        ),
        DecisionOption(
            name="Enterprise with PrivateLink and Code Signing",
            description="""
Enterprise Lambda deployment with PrivateLink for third-party integrations,
code signing for integrity, and comprehensive monitoring.

Implementation:
- All features from VPC Lambda with Reserved Concurrency
- Code signing with AWS Signer:
  - Verify function code integrity
  - Only signed code can be deployed
  - Signing profile with approved keys
- PrivateLink for third-party SaaS access:
  - Private connectivity to partner services
  - No internet exposure
  - Example: Snowflake, Salesforce via PrivateLink
- Secrets Manager for all secrets (not environment variables)
- Lambda Extensions for observability (New Relic, Datadog)
- GuardDuty for Lambda monitoring (malware detection)
- Config rules enforce security policies:
  - lambda-function-public-access-prohibited
  - lambda-inside-vpc
  - lambda-concurrency-check

Code signing workflow:
1. Developer commits code to Git
2. CI/CD builds and tests function
3. Signer signs deployment package
4. Upload signed package to S3
5. Lambda validates signature before execution

PrivateLink benefits:
- Private connectivity to SaaS (no internet)
- Reduced latency (AWS backbone)
- No data exfiltration risk (no internet egress)
""",
            pros=[
                "Code signing ensures integrity and provenance",
                "PrivateLink provides private connectivity to SaaS",
                "GuardDuty detects malware and threats",
                "Config rules enforce security policies",
                "Comprehensive observability with extensions",
                "Meets strictest compliance requirements",
            ],
            cons=[
                "Very high complexity",
                "Signer costs ($0.50 per signing operation)",
                "PrivateLink costs ($7.20/month per endpoint)",
                "Lambda Extensions add cold start latency",
                "GuardDuty costs (approx. $0.012/GB)",
            ],
            cost_factors=[
                "Lambda: Standard pricing",
                "Provisioned concurrency: approx. $13.50/month",
                "Signer: $0.50 per signing × 50/month = $25/month",
                "PrivateLink endpoints: $7.20/month × 2 = $14.40/month",
                "Secrets Manager: $0.40/secret/month × 3 = $1.20/month",
                "GuardDuty: approx. $5/account/month",
                "Config rules: $2/rule × 3 = $6/month",
                "For 1M requests: $2.20 (requests) + $13.50 (provisioned) + $25 (Signer) + $15 (VPC endpoints) + $14.40 (PrivateLink) + $1.20 (Secrets) + $5 (GuardDuty) + $6 (Config) = approx. $82/month",
            ],
            monthly_cost_range=(80.00, 500.00),
            implementation_complexity="Very High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Code signing + Config rules enforce access controls",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="Secrets Manager + KMS encrypt all sensitive data",
                ),
                SOC2Mapping(
                    control_id="CC6.8",
                    control_name="Malicious software prevention",
                    how_it_helps="GuardDuty detects malware in Lambda functions",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="Extensions + X-Ray + GuardDuty comprehensive monitoring",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Code signing provides cryptographic proof of integrity",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Basic Execution Role when:
- Simple event-driven functions (S3 events, SNS triggers)
- No VPC resource access needed
- Development or staging environment
- Budget-conscious
- Function needs internet access

Choose VPC Lambda when:
- Need to access VPC resources (RDS, ElastiCache, internal APIs)
- Production with moderate security requirements
- Can accept slower cold starts (~10 seconds)
- Want to eliminate NAT Gateway costs with VPC endpoints
- Most common choice for production Lambda with databases

Choose Reserved Concurrency when:
- Need predictable performance
- Prevent resource exhaustion (DoS protection)
- Latency-sensitive functions (use provisioned concurrency)
- Production with high throughput
- Budget supports provisioned concurrency costs

Choose Enterprise with PrivateLink when:
- Enterprise with strict compliance (SOC 2, PCI-DSS)
- Need code integrity verification
- Private connectivity to third-party SaaS
- Runtime malware detection required
- Have expertise in Lambda security
- Budget supports $80-500/month
""",
    examples=[
        {
            "scenario": "Image resize function triggered by S3 uploads",
            "recommendation": "Basic Execution Role (Public Lambda)",
            "reasoning": "No VPC resources needed. S3 and CloudWatch via public endpoints. Simple configuration.",
        },
        {
            "scenario": "API backend that queries RDS database",
            "recommendation": "VPC Lambda with Private Resource Access",
            "reasoning": "VPC Lambda accesses RDS privately. VPC endpoints for Secrets Manager (DB password). No NAT Gateway needed.",
        },
        {
            "scenario": "High-traffic API (10K requests/minute) with strict SLA",
            "recommendation": "VPC Lambda with Reserved Concurrency",
            "reasoning": "Provisioned concurrency eliminates cold starts. Reserved concurrency prevents throttling. X-Ray for tracing.",
        },
        {
            "scenario": "Financial services with code integrity and compliance requirements",
            "recommendation": "Enterprise with PrivateLink and Code Signing",
            "reasoning": "Code signing ensures no tampering. PrivateLink for private SaaS access. GuardDuty detects threats. Config rules enforce policies.",
        },
    ],
)


# Pattern 2: Lambda Secrets and Environment Variables
LAMBDA_SECRETS_PATTERNS = ArchitectureDecision(
    category="Compute - Lambda Security",
    question="What Lambda secrets management strategy should be implemented?",
    context="""
Lambda secrets management determines how sensitive data (database passwords, API keys)
are stored and accessed. Insecure secrets management leads to breaches.

Options:
- Environment variables: Simple but visible in console
- Secrets Manager: Encrypted, automatic rotation
- Parameter Store: Cost-effective, SSM integration
- KMS encryption: Encrypt environment variables
""",
    options=[
        DecisionOption(
            name="Environment Variables (Not Recommended)",
            description="""
Store configuration in Lambda environment variables without encryption.

Configuration:
- Environment variables set in Lambda console or IaC
- Variables visible in Lambda console
- No encryption at rest (unless KMS enabled)
- Can be read by anyone with lambda:GetFunctionConfiguration permission

Risk:
- Secrets visible in console
- No rotation capability
- Hardcoded in IaC (Git history exposure)
- CloudTrail logs may expose values
""",
            pros=[
                "Zero setup required",
                "Simple to use (process.env in code)",
                "No additional costs",
            ],
            cons=[
                "Secrets visible in Lambda console",
                "No automatic rotation",
                "Visible in CloudTrail logs (GetFunctionConfiguration)",
                "Hardcoded in infrastructure-as-code",
                "Not recommended for production secrets",
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
                    how_it_helps="Weak control - secrets in plaintext (not recommended)",
                ),
            ],
        ),
        DecisionOption(
            name="AWS Secrets Manager",
            description="""
Use AWS Secrets Manager to store secrets with automatic rotation and encryption.

Implementation:
- Store secrets in Secrets Manager
- Lambda retrieves secrets at runtime
- Secrets encrypted with KMS
- Automatic rotation supported (RDS, DocumentDB, Redshift)
- Lambda function caches secrets (reduce API calls)
- IAM permission: secretsmanager:GetSecretValue

Code example:
```python
import boto3
import json

secrets_client = boto3.client('secretsmanager')

def get_secret(secret_name):
    response = secrets_client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# Cache secret for 5 minutes to reduce API calls
secret = get_secret('prod/db/password')
```

Automatic rotation:
- Secrets Manager triggers Lambda function to rotate secret
- Lambda updates database password
- Application uses new password on next retrieval
""",
            pros=[
                "Secrets encrypted with KMS at rest",
                "Automatic rotation for RDS, DocumentDB, Redshift",
                "Versioning support (rollback to previous secret)",
                "Fine-grained IAM permissions",
                "Audit trail in CloudTrail",
                "Best practice for production",
            ],
            cons=[
                "Secrets Manager costs ($0.40/secret/month + API calls)",
                "Runtime overhead to retrieve secrets (cache recommended)",
                "Must handle secret retrieval errors",
                "Cold start latency increases slightly",
            ],
            cost_factors=[
                "Secrets Manager: $0.40/secret/month",
                "API calls: $0.05 per 10,000 calls",
                "  - 1M Lambda invocations × 1 secret = 1M API calls (with caching)",
                "  - With 5-minute cache: 1M / 300 = 3,333 API calls = $0.02",
                "For 5 secrets: $2.00 (secrets) + $0.10 (API calls) = $2.10/month",
            ],
            monthly_cost_range=(2.00, 20.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM controls who can access secrets",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="KMS encrypts secrets at rest",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudTrail logs all secret access",
                ),
            ],
        ),
        DecisionOption(
            name="SSM Parameter Store with Encryption",
            description="""
Use AWS Systems Manager Parameter Store for secrets with KMS encryption.
Cost-effective alternative to Secrets Manager.

Implementation:
- Store secrets in Parameter Store (SecureString type)
- Encrypt with KMS customer-managed key
- Lambda retrieves parameters at runtime
- IAM permission: ssm:GetParameter
- Caching recommended (reduce API calls)
- Parameter Store supports up to 10,000 parameters free tier

Parameter Store tiers:
- Standard: Free, 4 KB value size, 40 requests/second
- Advanced: $0.05 per 10,000 API calls, 8 KB value size, 1000 requests/second

Code example:
```python
import boto3

ssm_client = boto3.client('ssm')

def get_parameter(parameter_name):
    response = ssm_client.get_parameter(
        Name=parameter_name,
        WithDecryption=True
    )
    return response['Parameter']['Value']

# Cache parameter to reduce API calls
db_password = get_parameter('/prod/db/password')
```

No automatic rotation:
- Parameter Store doesn't have built-in rotation
- Must implement custom rotation with Lambda if needed
""",
            pros=[
                "Cost-effective (cheaper than Secrets Manager)",
                "KMS encryption at rest",
                "Parameter hierarchy (/prod/db/*, /staging/api/*)",
                "Integration with Systems Manager",
                "Fine-grained IAM permissions",
            ],
            cons=[
                "No automatic rotation (must implement custom)",
                "Standard tier has 40 requests/second limit",
                "No versioning support (unlike Secrets Manager)",
                "Must implement caching for cost efficiency",
            ],
            cost_factors=[
                "Parameter Store Standard: Free up to 10,000 parameters",
                "Parameter Store Advanced: $0.05 per parameter/month",
                "API calls (Standard): Free",
                "API calls (Advanced): $0.05 per 10,000 calls",
                "KMS key: $1/month",
                "For 10 parameters (Standard): $1/month (KMS only)",
            ],
            monthly_cost_range=(1.00, 10.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM controls parameter access",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="KMS encrypts parameters at rest",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudTrail logs parameter access",
                ),
            ],
        ),
        DecisionOption(
            name="Secrets Manager with Rotation and VPC Endpoint",
            description="""
Enterprise secrets management with Secrets Manager, automatic rotation, and
VPC endpoint for private access.

Implementation:
- All features from Secrets Manager
- VPC endpoint for Secrets Manager:
  - Lambda accesses Secrets Manager privately (no internet)
  - VPC endpoint: $7.20/month
- Automatic rotation for all secrets:
  - RDS/Aurora (built-in rotation)
  - Custom Lambda rotation for other secrets (API keys, third-party credentials)
- Rotation Lambda notifies team on failure
- Secrets Manager replication to second region (disaster recovery)
- Resource policies restrict secret access:
  - Only specific Lambda functions can access
  - Deny access from other accounts

Custom rotation example:
1. Rotation Lambda invoked every 30 days
2. Generate new API key with third-party service
3. Update secret in Secrets Manager
4. Test new key
5. Rollback if test fails
6. Notify team via SNS

Multi-region replication:
- Primary secret in us-east-1
- Replica in us-west-2
- Automatic failover for disaster recovery
""",
            pros=[
                "Automatic rotation reduces credential lifetime",
                "VPC endpoint provides private access",
                "Multi-region replication for disaster recovery",
                "Resource policies restrict access",
                "Custom rotation for any secret type",
                "Best practice for enterprise",
            ],
            cons=[
                "Custom rotation requires Lambda development",
                "VPC endpoint costs ($7.20/month)",
                "Replication doubles secret costs",
                "Increased complexity (rotation testing, monitoring)",
            ],
            cost_factors=[
                "Secrets Manager: $0.40/secret/month × 10 secrets = $4.00",
                "Replication: +$0.40/secret/month × 10 = $4.00",
                "VPC endpoint: $7.20/month",
                "Rotation Lambda: approx. $1/month",
                "Total: $4 (secrets) + $4 (replicas) + $7.20 (endpoint) + $1 (rotation) = $16.20/month",
            ],
            monthly_cost_range=(15.00, 100.00),
            implementation_complexity="High",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Resource policies + VPC endpoint restrict access",
                ),
                SOC2Mapping(
                    control_id="CC6.6",
                    control_name="Encryption",
                    how_it_helps="KMS encryption + automatic rotation",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="VPC endpoint provides private access",
                ),
                SOC2Mapping(
                    control_id="CC7.2",
                    control_name="System monitoring",
                    how_it_helps="CloudTrail + rotation failure alerts",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Environment Variables when:
- NEVER for production secrets
- Configuration only (non-sensitive: feature flags, URLs)
- Development environment with no real data

Choose Secrets Manager when:
- Production with RDS, DocumentDB, or Redshift (automatic rotation)
- Need secret versioning and rollback
- Budget supports $0.40/secret/month
- Most common choice for production secrets

Choose Parameter Store when:
- Budget-conscious (cheaper than Secrets Manager)
- Don't need automatic rotation
- Large number of parameters (10,000+ free tier)
- Integration with Systems Manager

Choose Secrets Manager with Rotation when:
- Enterprise with strict security requirements
- Need automatic rotation for all secrets (not just RDS)
- Multi-region disaster recovery
- Budget supports $15-100/month for secrets infrastructure
""",
    examples=[
        {
            "scenario": "Lambda function with database connection",
            "recommendation": "AWS Secrets Manager",
            "reasoning": "Store RDS password in Secrets Manager. Automatic rotation every 30 days. Lambda retrieves at runtime with caching.",
        },
        {
            "scenario": "Lambda function with 20 configuration parameters (non-sensitive)",
            "recommendation": "SSM Parameter Store with Encryption",
            "reasoning": "Parameter Store free tier covers 10,000 parameters. Cost-effective for configuration. KMS encrypts sensitive values.",
        },
        {
            "scenario": "Enterprise Lambda with third-party API keys and compliance requirements",
            "recommendation": "Secrets Manager with Rotation and VPC Endpoint",
            "reasoning": "Custom rotation for API keys. VPC endpoint for private access. Multi-region replication for DR. Resource policies restrict access.",
        },
    ],
)


# Pattern 3: Lambda Networking and Layers
LAMBDA_NETWORKING_LAYERS_PATTERNS = ArchitectureDecision(
    category="Compute - Lambda Security",
    question="What Lambda networking and layers strategy should be implemented?",
    context="""
Lambda networking determines how functions access resources (internet, VPC, AWS services).
Lambda layers enable code reuse and dependency management.

Networking options:
- Public internet: Default, fast cold starts
- VPC with NAT Gateway: Access VPC resources + internet
- VPC with VPC endpoints: Access VPC resources + AWS services (no internet)

Lambda layers:
- Shared code libraries
- Runtime dependencies
- Configuration files
- Max 5 layers per function, 250 MB total unzipped
""",
    options=[
        DecisionOption(
            name="Public Internet (No VPC)",
            description="""
Lambda function with public internet access, no VPC configuration.

Configuration:
- Function runs in AWS-managed VPC
- Internet access via AWS network
- No access to VPC resources
- Fast cold starts (<1 second)
- AWS services via public endpoints

Use cases:
- API integrations (external APIs)
- S3, DynamoDB, SNS, SQS via public endpoints
- Event-driven functions (S3 events, DynamoDB streams)
- No VPC resources needed
""",
            pros=[
                "Fast cold starts (<1 second)",
                "Simple configuration",
                "No VPC management",
                "No NAT Gateway costs",
                "Internet access included",
            ],
            cons=[
                "Cannot access VPC resources (RDS, ElastiCache)",
                "Function has internet access (potential data exfiltration)",
                "No control over outbound networking",
            ],
            cost_factors=[
                "No additional networking costs",
            ],
            monthly_cost_range=(0, 0),
            implementation_complexity="Low",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="IAM execution role controls permissions",
                ),
            ],
        ),
        DecisionOption(
            name="VPC with NAT Gateway",
            description="""
Lambda in VPC with NAT Gateway for both VPC resource access and internet access.

Implementation:
- Lambda in VPC private subnets
- Security groups control outbound access
- NAT Gateway for internet access
- Access to:
  - VPC resources (RDS, ElastiCache) via private IPs
  - Internet via NAT Gateway
  - AWS services via internet
- Cold starts: ~10 seconds (ENI creation)

Architecture:
Lambda → VPC private subnet → NAT Gateway (public subnet) → Internet

NAT Gateway costs:
- $32.40/month + $0.045/GB data processing
- High-availability: 2 NAT Gateways (one per AZ) = $64.80/month
""",
            pros=[
                "Access to VPC resources",
                "Internet access for external APIs",
                "Security groups control outbound traffic",
                "High availability with multi-AZ NAT Gateways",
            ],
            cons=[
                "Slow cold starts (~10 seconds)",
                "NAT Gateway costs ($32.40-65/month)",
                "NAT Gateway data processing costs",
                "Operational overhead (NAT Gateway management)",
            ],
            cost_factors=[
                "NAT Gateway: $32.40/month × 2 AZs = $64.80/month",
                "Data processing: $0.045/GB",
                "For 100 GB/month: $64.80 + $4.50 = $69.30/month",
            ],
            monthly_cost_range=(35.00, 150.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="Security groups restrict outbound access",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="VPC isolates function, NAT Gateway controls egress",
                ),
            ],
        ),
        DecisionOption(
            name="VPC with VPC Endpoints (No NAT Gateway)",
            description="""
Lambda in VPC with VPC endpoints for AWS service access. No internet access.

Implementation:
- Lambda in VPC private subnets
- VPC endpoints for AWS services:
  - s3 (gateway, free)
  - dynamodb (gateway, free)
  - secretsmanager ($7.20/month)
  - logs ($7.20/month)
  - Other services as needed
- No NAT Gateway (cost savings)
- No internet access (security benefit)
- Cold starts: ~10 seconds

Access pattern:
- VPC resources: Via private IPs
- AWS services: Via VPC endpoints (private)
- Internet: Not possible (blocked)

VPC endpoint costs:
- Gateway endpoints (S3, DynamoDB): Free
- Interface endpoints: $7.20/month each + data
""",
            pros=[
                "Access to VPC resources",
                "Private connectivity to AWS services",
                "No internet access (prevents data exfiltration)",
                "Eliminates NAT Gateway costs",
                "Reduced attack surface",
            ],
            cons=[
                "Cannot access external APIs or internet",
                "VPC endpoint costs (approx. $7.20/month per service)",
                "Slow cold starts (~10 seconds)",
                "Must create endpoint for each AWS service needed",
            ],
            cost_factors=[
                "VPC endpoints: $7.20/month × 2-5 services = $14.40-36/month",
                "VPC endpoint data: $0.01/GB",
                "For 100 GB/month: $14.40 (2 endpoints) + $1 (data) = $15.40/month",
            ],
            monthly_cost_range=(15.00, 50.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="VPC endpoints restrict access to AWS services only",
                ),
                SOC2Mapping(
                    control_id="CC6.7",
                    control_name="Restricted access",
                    how_it_helps="No internet access prevents data exfiltration",
                ),
            ],
        ),
        DecisionOption(
            name="VPC with Shared Lambda Layers",
            description="""
VPC Lambda with shared Lambda layers for code reuse and consistent dependencies
across multiple functions.

Implementation:
- All features from VPC with VPC Endpoints
- Lambda layers for:
  - Shared libraries (boto3, requests, database drivers)
  - Common utilities (logging, error handling, auth)
  - Runtime dependencies (Pandas, NumPy)
  - Configuration (AWS SDK config)
- Layer versioning for updates
- Cross-account layer sharing (if needed)
- Container image deployment for large dependencies (>250 MB)

Lambda layer structure:
```
layer/
  python/
    lib/
      python3.9/
        site-packages/
          boto3/
          requests/
          mycompany_utils/
```

Layer benefits:
- Reduce deployment package size (faster deploys)
- Share code across functions (DRY principle)
- Update dependencies independently (layer updates)
- Smaller function packages (faster cold starts)

Container images:
- For dependencies >250 MB (ML models, large libraries)
- Up to 10 GB image size
- Familiar Docker workflow
- Stored in ECR (scanning available)
""",
            pros=[
                "Code reuse across functions (DRY)",
                "Smaller deployment packages (faster deploys)",
                "Independent dependency updates",
                "Container images for large dependencies",
                "Cross-account sharing (organizational efficiency)",
            ],
            cons=[
                "Layer management overhead (versioning, updates)",
                "Max 5 layers per function (complexity if exceeded)",
                "250 MB total unzipped size limit (use containers if exceeded)",
                "Cold starts include layer extraction time",
            ],
            cost_factors=[
                "Lambda layers: No additional cost",
                "Container images: ECR storage ($0.10/GB-month)",
                "VPC endpoints: $14.40-36/month",
                "For 5 container images (2 GB each): $1 (ECR) + $15 (endpoints) = $16/month",
            ],
            monthly_cost_range=(15.00, 100.00),
            implementation_complexity="Medium",
            soc2_controls=[
                SOC2Mapping(
                    control_id="CC6.1",
                    control_name="Logical access controls",
                    how_it_helps="VPC + endpoints restrict access",
                ),
                SOC2Mapping(
                    control_id="CC8.1",
                    control_name="Change management",
                    how_it_helps="Layer versioning provides change control",
                ),
            ],
        ),
    ],
    decision_framework="""
Choose Public Internet when:
- No VPC resource access needed
- Function calls external APIs
- Fast cold starts required
- Development or staging environment
- S3, DynamoDB, SNS, SQS only

Choose VPC with NAT Gateway when:
- Need VPC resource access (RDS, ElastiCache)
- Also need internet access (external APIs)
- Can accept NAT Gateway costs
- High availability required (multi-AZ NAT)

Choose VPC with VPC Endpoints when:
- Need VPC resource access
- No internet access required
- Want to eliminate NAT Gateway costs
- Security priority (no data exfiltration risk)
- Most common choice for production VPC Lambda

Choose VPC with Shared Layers when:
- Multiple Lambda functions with shared dependencies
- Want to reduce deployment package sizes
- Need consistent dependencies across functions
- Organizational efficiency (code reuse)
- Large dependencies (use container images)
""",
    examples=[
        {
            "scenario": "Lambda function processing S3 events",
            "recommendation": "Public Internet (No VPC)",
            "reasoning": "No VPC resources. S3 via public endpoint. Fast cold starts. Simple configuration.",
        },
        {
            "scenario": "Lambda API backend querying RDS and calling external payment API",
            "recommendation": "VPC with NAT Gateway",
            "reasoning": "RDS in VPC. NAT Gateway for payment API calls. Security groups restrict outbound traffic.",
        },
        {
            "scenario": "Lambda processing DynamoDB stream and writing to RDS",
            "recommendation": "VPC with VPC Endpoints (No NAT Gateway)",
            "reasoning": "RDS in VPC. DynamoDB via VPC endpoint (free). No internet needed. Eliminates NAT Gateway costs.",
        },
        {
            "scenario": "10 Lambda functions with shared utilities and large ML dependencies",
            "recommendation": "VPC with Shared Lambda Layers",
            "reasoning": "Lambda layers for shared utilities. Container images for ML models (>250 MB). Code reuse across functions.",
        },
    ],
)


# Export all patterns
__all__ = [
    "LAMBDA_SECURITY_STRATEGY_PATTERNS",
    "LAMBDA_SECRETS_PATTERNS",
    "LAMBDA_NETWORKING_LAYERS_PATTERNS",
]
