"""
HIPAA Eligible AWS Services for CARL.

This module defines which AWS services are covered under AWS's Business Associate
Agreement (BAA) and are eligible for processing, storing, or transmitting ePHI.

IMPORTANT: Organizations must have an AWS BAA in place before using any AWS service
for ePHI workloads. The BAA is available through AWS Artifact.

Reference: https://aws.amazon.com/compliance/hipaa-eligible-services-reference/

Last Updated: February 2026

Usage:
    from knowledge.hipaa_eligible_services import (
        is_hipaa_eligible,
        validate_resources_hipaa_eligible,
        HIPAA_ELIGIBLE_SERVICES,
    )

    # Check if a service is HIPAA eligible
    if is_hipaa_eligible("lambda"):
        print("Lambda can be used for ePHI workloads")

    # Validate a list of resources
    violations = validate_resources_hipaa_eligible(["ec2", "lightsail"])
    # Returns: [{"service": "lightsail", "message": "..."}]
"""

from dataclasses import dataclass


@dataclass
class HIPAAService:
    """AWS service with HIPAA eligibility information."""
    name: str
    service_id: str  # AWS service identifier
    category: str
    notes: str = ""


# =============================================================================
# HIPAA Eligible AWS Services
# Organized by category, based on AWS HIPAA Eligible Services Reference
# =============================================================================

HIPAA_ELIGIBLE_SERVICES: dict[str, HIPAAService] = {
    # =========================================================================
    # Compute
    # =========================================================================
    "ec2": HIPAAService(
        name="Amazon EC2",
        service_id="ec2",
        category="Compute",
        notes="Including Amazon EBS, EC2 Auto Scaling, and Elastic Load Balancing",
    ),
    "lambda": HIPAAService(
        name="AWS Lambda",
        service_id="lambda",
        category="Compute",
    ),
    "ecs": HIPAAService(
        name="Amazon ECS",
        service_id="ecs",
        category="Compute",
        notes="Both EC2 and Fargate launch types",
    ),
    "eks": HIPAAService(
        name="Amazon EKS",
        service_id="eks",
        category="Compute",
    ),
    "fargate": HIPAAService(
        name="AWS Fargate",
        service_id="fargate",
        category="Compute",
    ),
    "batch": HIPAAService(
        name="AWS Batch",
        service_id="batch",
        category="Compute",
    ),
    "elastic-beanstalk": HIPAAService(
        name="AWS Elastic Beanstalk",
        service_id="elastic-beanstalk",
        category="Compute",
    ),
    "outposts": HIPAAService(
        name="AWS Outposts",
        service_id="outposts",
        category="Compute",
    ),
    "app-runner": HIPAAService(
        name="AWS App Runner",
        service_id="app-runner",
        category="Compute",
    ),

    # =========================================================================
    # Storage
    # =========================================================================
    "s3": HIPAAService(
        name="Amazon S3",
        service_id="s3",
        category="Storage",
        notes="Including S3 Glacier, S3 Glacier Deep Archive",
    ),
    "ebs": HIPAAService(
        name="Amazon EBS",
        service_id="ebs",
        category="Storage",
    ),
    "efs": HIPAAService(
        name="Amazon EFS",
        service_id="efs",
        category="Storage",
    ),
    "fsx": HIPAAService(
        name="Amazon FSx",
        service_id="fsx",
        category="Storage",
        notes="FSx for Windows, Lustre, NetApp ONTAP, OpenZFS",
    ),
    "storage-gateway": HIPAAService(
        name="AWS Storage Gateway",
        service_id="storage-gateway",
        category="Storage",
    ),
    "backup": HIPAAService(
        name="AWS Backup",
        service_id="backup",
        category="Storage",
    ),

    # =========================================================================
    # Database
    # =========================================================================
    "rds": HIPAAService(
        name="Amazon RDS",
        service_id="rds",
        category="Database",
        notes="MySQL, PostgreSQL, MariaDB, Oracle, SQL Server, Aurora",
    ),
    "aurora": HIPAAService(
        name="Amazon Aurora",
        service_id="aurora",
        category="Database",
    ),
    "dynamodb": HIPAAService(
        name="Amazon DynamoDB",
        service_id="dynamodb",
        category="Database",
    ),
    "redshift": HIPAAService(
        name="Amazon Redshift",
        service_id="redshift",
        category="Database",
    ),
    "elasticache": HIPAAService(
        name="Amazon ElastiCache",
        service_id="elasticache",
        category="Database",
        notes="Redis and Memcached",
    ),
    "neptune": HIPAAService(
        name="Amazon Neptune",
        service_id="neptune",
        category="Database",
    ),
    "documentdb": HIPAAService(
        name="Amazon DocumentDB",
        service_id="documentdb",
        category="Database",
    ),
    "keyspaces": HIPAAService(
        name="Amazon Keyspaces",
        service_id="keyspaces",
        category="Database",
        notes="Managed Apache Cassandra-compatible",
    ),
    "timestream": HIPAAService(
        name="Amazon Timestream",
        service_id="timestream",
        category="Database",
    ),
    "memorydb": HIPAAService(
        name="Amazon MemoryDB for Redis",
        service_id="memorydb",
        category="Database",
    ),

    # =========================================================================
    # Networking & Content Delivery
    # =========================================================================
    "vpc": HIPAAService(
        name="Amazon VPC",
        service_id="vpc",
        category="Networking",
    ),
    "cloudfront": HIPAAService(
        name="Amazon CloudFront",
        service_id="cloudfront",
        category="Networking",
    ),
    "route53": HIPAAService(
        name="Amazon Route 53",
        service_id="route53",
        category="Networking",
    ),
    "api-gateway": HIPAAService(
        name="Amazon API Gateway",
        service_id="api-gateway",
        category="Networking",
    ),
    "direct-connect": HIPAAService(
        name="AWS Direct Connect",
        service_id="direct-connect",
        category="Networking",
    ),
    "global-accelerator": HIPAAService(
        name="AWS Global Accelerator",
        service_id="global-accelerator",
        category="Networking",
    ),
    "privatelink": HIPAAService(
        name="AWS PrivateLink",
        service_id="privatelink",
        category="Networking",
    ),
    "transit-gateway": HIPAAService(
        name="AWS Transit Gateway",
        service_id="transit-gateway",
        category="Networking",
    ),
    "elb": HIPAAService(
        name="Elastic Load Balancing",
        service_id="elb",
        category="Networking",
        notes="ALB, NLB, CLB, GLB",
    ),
    "vpn": HIPAAService(
        name="AWS VPN",
        service_id="vpn",
        category="Networking",
    ),
    "network-firewall": HIPAAService(
        name="AWS Network Firewall",
        service_id="network-firewall",
        category="Networking",
    ),

    # =========================================================================
    # Security, Identity & Compliance
    # =========================================================================
    "iam": HIPAAService(
        name="AWS IAM",
        service_id="iam",
        category="Security",
    ),
    "kms": HIPAAService(
        name="AWS KMS",
        service_id="kms",
        category="Security",
    ),
    "secrets-manager": HIPAAService(
        name="AWS Secrets Manager",
        service_id="secrets-manager",
        category="Security",
    ),
    "cognito": HIPAAService(
        name="Amazon Cognito",
        service_id="cognito",
        category="Security",
    ),
    "guardduty": HIPAAService(
        name="Amazon GuardDuty",
        service_id="guardduty",
        category="Security",
    ),
    "inspector": HIPAAService(
        name="Amazon Inspector",
        service_id="inspector",
        category="Security",
    ),
    "macie": HIPAAService(
        name="Amazon Macie",
        service_id="macie",
        category="Security",
        notes="Useful for PHI detection in S3",
    ),
    "security-hub": HIPAAService(
        name="AWS Security Hub",
        service_id="security-hub",
        category="Security",
    ),
    "waf": HIPAAService(
        name="AWS WAF",
        service_id="waf",
        category="Security",
    ),
    "shield": HIPAAService(
        name="AWS Shield",
        service_id="shield",
        category="Security",
    ),
    "acm": HIPAAService(
        name="AWS Certificate Manager",
        service_id="acm",
        category="Security",
    ),
    "cloudhsm": HIPAAService(
        name="AWS CloudHSM",
        service_id="cloudhsm",
        category="Security",
    ),
    "directory-service": HIPAAService(
        name="AWS Directory Service",
        service_id="directory-service",
        category="Security",
    ),
    "iam-identity-center": HIPAAService(
        name="AWS IAM Identity Center",
        service_id="iam-identity-center",
        category="Security",
        notes="Formerly AWS SSO",
    ),
    "firewall-manager": HIPAAService(
        name="AWS Firewall Manager",
        service_id="firewall-manager",
        category="Security",
    ),
    "audit-manager": HIPAAService(
        name="AWS Audit Manager",
        service_id="audit-manager",
        category="Security",
    ),
    "artifact": HIPAAService(
        name="AWS Artifact",
        service_id="artifact",
        category="Security",
        notes="Download AWS BAA here",
    ),

    # =========================================================================
    # Management & Governance
    # =========================================================================
    "cloudwatch": HIPAAService(
        name="Amazon CloudWatch",
        service_id="cloudwatch",
        category="Management",
    ),
    "cloudtrail": HIPAAService(
        name="AWS CloudTrail",
        service_id="cloudtrail",
        category="Management",
    ),
    "config": HIPAAService(
        name="AWS Config",
        service_id="config",
        category="Management",
    ),
    "systems-manager": HIPAAService(
        name="AWS Systems Manager",
        service_id="systems-manager",
        category="Management",
    ),
    "organizations": HIPAAService(
        name="AWS Organizations",
        service_id="organizations",
        category="Management",
    ),
    "control-tower": HIPAAService(
        name="AWS Control Tower",
        service_id="control-tower",
        category="Management",
    ),
    "trusted-advisor": HIPAAService(
        name="AWS Trusted Advisor",
        service_id="trusted-advisor",
        category="Management",
    ),
    "health": HIPAAService(
        name="AWS Health",
        service_id="health",
        category="Management",
    ),
    "service-catalog": HIPAAService(
        name="AWS Service Catalog",
        service_id="service-catalog",
        category="Management",
    ),
    "cloudformation": HIPAAService(
        name="AWS CloudFormation",
        service_id="cloudformation",
        category="Management",
    ),

    # =========================================================================
    # Application Integration
    # =========================================================================
    "sns": HIPAAService(
        name="Amazon SNS",
        service_id="sns",
        category="Integration",
    ),
    "sqs": HIPAAService(
        name="Amazon SQS",
        service_id="sqs",
        category="Integration",
    ),
    "eventbridge": HIPAAService(
        name="Amazon EventBridge",
        service_id="eventbridge",
        category="Integration",
    ),
    "step-functions": HIPAAService(
        name="AWS Step Functions",
        service_id="step-functions",
        category="Integration",
    ),
    "mq": HIPAAService(
        name="Amazon MQ",
        service_id="mq",
        category="Integration",
    ),
    "kinesis": HIPAAService(
        name="Amazon Kinesis",
        service_id="kinesis",
        category="Integration",
        notes="Data Streams, Data Firehose, Data Analytics",
    ),

    # =========================================================================
    # Analytics
    # =========================================================================
    "athena": HIPAAService(
        name="Amazon Athena",
        service_id="athena",
        category="Analytics",
    ),
    "emr": HIPAAService(
        name="Amazon EMR",
        service_id="emr",
        category="Analytics",
    ),
    "glue": HIPAAService(
        name="AWS Glue",
        service_id="glue",
        category="Analytics",
    ),
    "quicksight": HIPAAService(
        name="Amazon QuickSight",
        service_id="quicksight",
        category="Analytics",
    ),
    "opensearch": HIPAAService(
        name="Amazon OpenSearch Service",
        service_id="opensearch",
        category="Analytics",
    ),
    "msk": HIPAAService(
        name="Amazon MSK",
        service_id="msk",
        category="Analytics",
    ),
    "lake-formation": HIPAAService(
        name="AWS Lake Formation",
        service_id="lake-formation",
        category="Analytics",
    ),

    # =========================================================================
    # Machine Learning
    # =========================================================================
    "sagemaker": HIPAAService(
        name="Amazon SageMaker",
        service_id="sagemaker",
        category="ML",
    ),
    "comprehend": HIPAAService(
        name="Amazon Comprehend",
        service_id="comprehend",
        category="ML",
    ),
    "comprehend-medical": HIPAAService(
        name="Amazon Comprehend Medical",
        service_id="comprehend-medical",
        category="ML",
        notes="Specifically designed for healthcare",
    ),
    "transcribe": HIPAAService(
        name="Amazon Transcribe",
        service_id="transcribe",
        category="ML",
    ),
    "transcribe-medical": HIPAAService(
        name="Amazon Transcribe Medical",
        service_id="transcribe-medical",
        category="ML",
    ),
    "textract": HIPAAService(
        name="Amazon Textract",
        service_id="textract",
        category="ML",
    ),
    "rekognition": HIPAAService(
        name="Amazon Rekognition",
        service_id="rekognition",
        category="ML",
    ),
    "bedrock": HIPAAService(
        name="Amazon Bedrock",
        service_id="bedrock",
        category="ML",
    ),
    "healthlake": HIPAAService(
        name="Amazon HealthLake",
        service_id="healthlake",
        category="ML",
        notes="FHIR-compliant data lake for healthcare",
    ),

    # =========================================================================
    # Containers
    # =========================================================================
    "ecr": HIPAAService(
        name="Amazon ECR",
        service_id="ecr",
        category="Containers",
    ),

    # =========================================================================
    # Developer Tools
    # =========================================================================
    "codebuild": HIPAAService(
        name="AWS CodeBuild",
        service_id="codebuild",
        category="Developer Tools",
    ),
    "codepipeline": HIPAAService(
        name="AWS CodePipeline",
        service_id="codepipeline",
        category="Developer Tools",
    ),
    "codecommit": HIPAAService(
        name="AWS CodeCommit",
        service_id="codecommit",
        category="Developer Tools",
    ),
}


# =============================================================================
# Non-Eligible Services (Common ones to watch for)
# =============================================================================

NON_HIPAA_ELIGIBLE_SERVICES = [
    "lightsail",
    "amplify",
    "appflow",
    "braket",  # Quantum computing
    "chime",
    "connect",  # Contact center - has separate HIPAA considerations
    "gamelift",
    "honeycode",
    "ivs",  # Interactive Video Service
    "location",
    "lumberyard",
    "nimble-studio",
    "robomaker",
    "sumerian",
    "workmail",
    "workdocs",  # Check latest - may be eligible now
    "workspaces",  # Check latest - may be eligible now
]


# =============================================================================
# Helper Functions
# =============================================================================

def is_hipaa_eligible(service_id: str) -> bool:
    """
    Check if an AWS service is HIPAA eligible.

    Args:
        service_id: AWS service identifier (e.g., "s3", "lambda", "ec2")

    Returns:
        True if the service is HIPAA eligible, False otherwise
    """
    return service_id.lower() in HIPAA_ELIGIBLE_SERVICES


def get_service_info(service_id: str) -> HIPAAService | None:
    """
    Get HIPAA eligibility information for a service.

    Args:
        service_id: AWS service identifier

    Returns:
        HIPAAService if eligible, None if not
    """
    return HIPAA_ELIGIBLE_SERVICES.get(service_id.lower())


def validate_resources_hipaa_eligible(service_ids: list[str]) -> list[dict]:
    """
    Validate that a list of AWS services are HIPAA eligible.

    Args:
        service_ids: List of AWS service identifiers

    Returns:
        List of violation dicts for non-eligible services
    """
    violations = []
    for service_id in service_ids:
        if not is_hipaa_eligible(service_id):
            violations.append({
                "service": service_id,
                "eligible": False,
                "message": f"AWS {service_id} is not covered under the AWS HIPAA BAA. "
                           f"Do not use for ePHI workloads.",
                "recommendation": "Use a HIPAA-eligible alternative or ensure this "
                                  "service does not process, store, or transmit ePHI.",
            })
    return violations


def get_services_by_category(category: str) -> list[HIPAAService]:
    """
    Get all HIPAA-eligible services in a category.

    Args:
        category: Category name (e.g., "Compute", "Database", "Security")

    Returns:
        List of HIPAAService objects in that category
    """
    return [
        svc for svc in HIPAA_ELIGIBLE_SERVICES.values()
        if svc.category.lower() == category.lower()
    ]


def get_all_categories() -> list[str]:
    """
    Get all unique service categories.

    Returns:
        List of category names
    """
    return sorted(set(svc.category for svc in HIPAA_ELIGIBLE_SERVICES.values()))


def get_eligible_services_summary() -> dict[str, list[str]]:
    """
    Get a summary of eligible services grouped by category.

    Returns:
        Dict mapping category to list of service names
    """
    summary = {}
    for svc in HIPAA_ELIGIBLE_SERVICES.values():
        if svc.category not in summary:
            summary[svc.category] = []
        summary[svc.category].append(svc.name)
    return {k: sorted(v) for k, v in sorted(summary.items())}


def check_terraform_resources_hipaa(resource_types: list[str]) -> list[dict]:
    """
    Check Terraform resource types for HIPAA eligibility.

    Args:
        resource_types: List of Terraform resource types (e.g., ["aws_instance", "aws_lightsail_instance"])

    Returns:
        List of violation dicts for non-eligible resources
    """
    # Map Terraform resource prefixes to service IDs
    TF_TO_SERVICE = {
        "aws_instance": "ec2",
        "aws_launch_template": "ec2",
        "aws_autoscaling": "ec2",
        "aws_lb": "elb",
        "aws_alb": "elb",
        "aws_s3": "s3",
        "aws_lambda": "lambda",
        "aws_ecs": "ecs",
        "aws_eks": "eks",
        "aws_rds": "rds",
        "aws_db": "rds",
        "aws_dynamodb": "dynamodb",
        "aws_elasticache": "elasticache",
        "aws_vpc": "vpc",
        "aws_subnet": "vpc",
        "aws_security_group": "vpc",
        "aws_kms": "kms",
        "aws_secretsmanager": "secrets-manager",
        "aws_cloudwatch": "cloudwatch",
        "aws_cloudtrail": "cloudtrail",
        "aws_sns": "sns",
        "aws_sqs": "sqs",
        "aws_kinesis": "kinesis",
        "aws_glue": "glue",
        "aws_athena": "athena",
        "aws_sagemaker": "sagemaker",
        "aws_ecr": "ecr",
        "aws_cognito": "cognito",
        "aws_iam": "iam",
        "aws_api_gateway": "api-gateway",
        "aws_apigateway": "api-gateway",
        "aws_cloudfront": "cloudfront",
        "aws_route53": "route53",
        "aws_waf": "waf",
        "aws_guardduty": "guardduty",
        "aws_inspector": "inspector",
        "aws_macie": "macie",
        "aws_config": "config",
        "aws_ssm": "systems-manager",
        "aws_backup": "backup",
        # Non-eligible
        "aws_lightsail": "lightsail",
        "aws_amplify": "amplify",
    }

    violations = []
    for resource_type in resource_types:
        # Find matching service
        service_id = None
        for prefix, svc in TF_TO_SERVICE.items():
            if resource_type.startswith(prefix):
                service_id = svc
                break

        if service_id and not is_hipaa_eligible(service_id):
            violations.append({
                "resource_type": resource_type,
                "service": service_id,
                "eligible": False,
                "message": f"Terraform resource '{resource_type}' uses AWS {service_id}, "
                           f"which is not HIPAA eligible.",
            })

    return violations
