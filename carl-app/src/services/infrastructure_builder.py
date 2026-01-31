"""
Infrastructure Builder Service for CARL.

Generates compliant Terraform code based on selected blueprints and configurations.
Smart generation: Scans AWS environment and only generates code for missing resources.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from services.bedrock_service import BedrockService
from services.resource_detector import ResourceDetector
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GeneratedInfrastructure:
    """Represents generated infrastructure code."""
    blueprint: str
    terraform_code: str
    variables: dict[str, Any]
    outputs: list[str]
    compliance_notes: list[str]
    deployment_steps: list[str]


class InfrastructureBuilder:
    """Service for generating compliant infrastructure code."""

    def __init__(self, region: str = "us-east-1"):
        self.bedrock = BedrockService()
        self.detector = ResourceDetector(region=region)
        self._load_blueprints()

    def _load_blueprints(self):
        """Load infrastructure blueprint templates."""
        self.blueprints = {
            "networking/basic-vpc": self._blueprint_basic_vpc,
            "networking/standard-vpc": self._blueprint_standard_vpc,
            "networking/enterprise-vpc": self._blueprint_enterprise_vpc,
            "networking/vpn-gateway": self._blueprint_vpn_gateway,
            "compute/basic-ec2": self._blueprint_basic_ec2,
            "compute/ecs-fargate": self._blueprint_ecs_fargate,
            "compute/eks-cluster": self._blueprint_eks_cluster,
            "compute/lambda-api": self._blueprint_lambda_api,
            "database/rds-single": self._blueprint_rds_single,
            "database/rds-multi-az": self._blueprint_rds_multi_az,
            "database/rds-postgres": self._blueprint_rds_postgres,
            "database/aurora-serverless": self._blueprint_aurora_serverless,
            "storage/compliant-s3": self._blueprint_compliant_s3,
            "storage/secure-s3": self._blueprint_secure_s3,
            "storage/s3-static-website": self._blueprint_s3_static_website,
            "security/basic-stack": self._blueprint_security_basic,
            "security/soc2-stack": self._blueprint_security_soc2,
            "security/cloudtrail-logging": self._blueprint_cloudtrail_logging,
            "serverless/api": self._blueprint_serverless_api,
        }

    def generate(
        self,
        blueprint_name: str,
        configuration: dict[str, Any],
    ) -> GeneratedInfrastructure:
        """
        Generate infrastructure code from a blueprint.

        Args:
            blueprint_name: Name of the blueprint to use
            configuration: Configuration parameters

        Returns:
            GeneratedInfrastructure with Terraform code
        """
        blueprint_func = self.blueprints.get(blueprint_name)
        if not blueprint_func:
            raise ValueError(f"Unknown blueprint: {blueprint_name}")

        return blueprint_func(configuration)

    def list_blueprints(self) -> list[dict[str, str]]:
        """List available blueprints."""
        return [
            {"name": "networking/basic-vpc", "description": "Basic compliant VPC"},
            {"name": "networking/standard-vpc", "description": "Standard HA VPC with WAF"},
            {"name": "networking/enterprise-vpc", "description": "Enterprise VPC with Network Firewall"},
            {"name": "networking/vpn-gateway", "description": "Site-to-Site VPN Gateway"},
            {"name": "compute/basic-ec2", "description": "Basic compliant EC2"},
            {"name": "compute/ecs-fargate", "description": "ECS Fargate deployment"},
            {"name": "compute/eks-cluster", "description": "Production EKS cluster"},
            {"name": "compute/lambda-api", "description": "Lambda + API Gateway REST API"},
            {"name": "database/rds-single", "description": "Single-AZ RDS"},
            {"name": "database/rds-multi-az", "description": "Multi-AZ RDS"},
            {"name": "database/rds-postgres", "description": "PostgreSQL RDS with backups"},
            {"name": "database/aurora-serverless", "description": "Aurora Serverless v2"},
            {"name": "storage/compliant-s3", "description": "Compliant S3 bucket"},
            {"name": "storage/secure-s3", "description": "Secure S3 with Macie"},
            {"name": "storage/s3-static-website", "description": "S3 static website with CloudFront"},
            {"name": "security/basic-stack", "description": "Basic security services"},
            {"name": "security/soc2-stack", "description": "SOC 2 security stack"},
            {"name": "security/cloudtrail-logging", "description": "CloudTrail + S3 + SNS alerts"},
            {"name": "serverless/api", "description": "Serverless API Gateway + Lambda"},
        ]

    def customize_with_ai(
        self,
        blueprint_name: str,
        requirements: str,
        base_config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Use AI to customize blueprint configuration based on requirements.
        """
        prompt = f"""Given this infrastructure blueprint and requirements, suggest optimal configuration values.

Blueprint: {blueprint_name}
Requirements: {requirements}
Base Configuration: {json.dumps(base_config, indent=2)}

Return a JSON object with recommended configuration values. Only include values that should differ from defaults.
Be conservative with sizing and cost-conscious.
Return ONLY valid JSON, no explanation."""

        response = self.bedrock.invoke_model(prompt, max_tokens=500, temperature=0.2)

        try:
            # Extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            logger.warning("Could not parse AI configuration response")

        return base_config

    # =========================================================================
    # NETWORKING BLUEPRINTS
    # =========================================================================

    def _blueprint_basic_vpc(self, config: dict) -> GeneratedInfrastructure:
        """Generate basic compliant VPC - SMART generation."""
        name = config.get("name", "main")
        cidr = config.get("cidr", "10.0.0.0/16")
        azs = config.get("azs", 2)
        environment = config.get("environment", "dev")

        # Check if VPC already exists with this name
        logger.info(f"Scanning for existing VPC with name: {name}-vpc...")
        vpc_name_to_check = f"{name}-vpc"
        vpc_exists, vpc_id, existing_cidr = self._check_vpc_exists(vpc_name_to_check)

        if vpc_exists:
            # VPC exists - just return data source
            logger.info(f"Found existing VPC: {vpc_id} ({existing_cidr})")

            terraform = f'''# Basic Compliant VPC
# Generated by CARL - Smart Infrastructure Generation
#
# CARL detected an existing VPC with name "{vpc_name_to_check}"
# VPC ID: {vpc_id}
# CIDR: {existing_cidr}
#
# Using existing VPC. Note: Subnets, NAT gateways, and route tables are NOT managed by this code.
# To fully manage networking resources, rename the VPC or remove it and re-run this blueprint.

terraform {{
  required_version = ">= 1.5.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

data "aws_vpc" "existing" {{
  filter {{
    name   = "tag:Name"
    values = ["{vpc_name_to_check}"]
  }}
}}

# Query existing subnets in this VPC (for reference)
data "aws_subnets" "existing" {{
  filter {{
    name   = "vpc-id"
    values = [data.aws_vpc.existing.id]
  }}
}}

# Outputs
output "vpc_id" {{
  description = "VPC ID (existing)"
  value       = data.aws_vpc.existing.id
}}

output "vpc_cidr" {{
  description = "VPC CIDR block (existing)"
  value       = data.aws_vpc.existing.cidr_block
}}

output "subnet_ids" {{
  description = "Existing subnet IDs in this VPC"
  value       = data.aws_subnets.existing.ids
}}
'''

            return GeneratedInfrastructure(
                blueprint="networking/basic-vpc",
                terraform_code=terraform,
                variables={"name": name, "environment": environment},
                outputs=["vpc_id", "vpc_cidr", "subnet_ids"],
                compliance_notes=[
                    f"Using existing VPC: {vpc_id}",
                    f"Existing CIDR: {existing_cidr}",
                    "Subnets and networking resources are NOT managed by this code",
                    "To create a new VPC, use a different name or remove the existing VPC",
                ],
                deployment_steps=[
                    "1. Review the existing VPC configuration",
                    "2. Run: terraform init",
                    "3. Run: terraform plan (should show data sources only)",
                    "4. Run: terraform apply",
                    "5. Use the existing subnet IDs for your workloads",
                ],
            )

        # VPC doesn't exist - create full stack
        logger.info(f"No existing VPC found. Will create new VPC: {vpc_name_to_check}")

        terraform = f'''# Basic Compliant VPC
# Generated by CARL - Smart Infrastructure Generation
#
# CARL scanned your AWS environment and detected:
#   ✗ No existing VPC found with name "{vpc_name_to_check}"
#
# This code will create a new compliant VPC with:
#   - Public and private subnets across {azs} AZs
#   - Single NAT Gateway (cost-optimized)
#   - VPC Flow Logs for audit compliance
#   - Hardened default security group

terraform {{
  required_version = ">= 1.5.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

locals {{
  name        = "{name}"
  environment = "{environment}"
  cidr        = "{cidr}"
  azs         = slice(data.aws_availability_zones.available.names, 0, {azs})

  tags = {{
    Name        = local.name
    Environment = local.environment
    ManagedBy   = "Terraform"
    Compliance  = "SOC2"
  }}
}}

data "aws_availability_zones" "available" {{
  state = "available"
}}

# VPC
resource "aws_vpc" "main" {{
  cidr_block           = local.cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, {{
    Name = "${{local.name}}-vpc"
  }})
}}

# Internet Gateway
resource "aws_internet_gateway" "main" {{
  vpc_id = aws_vpc.main.id

  tags = merge(local.tags, {{
    Name = "${{local.name}}-igw"
  }})
}}

# Public Subnets
resource "aws_subnet" "public" {{
  count             = length(local.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(local.cidr, 8, count.index)
  availability_zone = local.azs[count.index]

  map_public_ip_on_launch = false  # SOC 2: No auto-assign public IP

  tags = merge(local.tags, {{
    Name = "${{local.name}}-public-${{local.azs[count.index]}}"
    Tier = "public"
  }})
}}

# Private Subnets
resource "aws_subnet" "private" {{
  count             = length(local.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(local.cidr, 8, count.index + 10)
  availability_zone = local.azs[count.index]

  tags = merge(local.tags, {{
    Name = "${{local.name}}-private-${{local.azs[count.index]}}"
    Tier = "private"
  }})
}}

# NAT Gateway (single for cost savings in basic tier)
resource "aws_eip" "nat" {{
  domain = "vpc"

  tags = merge(local.tags, {{
    Name = "${{local.name}}-nat-eip"
  }})
}}

resource "aws_nat_gateway" "main" {{
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = merge(local.tags, {{
    Name = "${{local.name}}-nat"
  }})

  depends_on = [aws_internet_gateway.main]
}}

# Route Tables
resource "aws_route_table" "public" {{
  vpc_id = aws_vpc.main.id

  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }}

  tags = merge(local.tags, {{
    Name = "${{local.name}}-public-rt"
  }})
}}

resource "aws_route_table" "private" {{
  vpc_id = aws_vpc.main.id

  route {{
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }}

  tags = merge(local.tags, {{
    Name = "${{local.name}}-private-rt"
  }})
}}

resource "aws_route_table_association" "public" {{
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}}

resource "aws_route_table_association" "private" {{
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}}

# VPC Flow Logs (SOC 2 Required)
resource "aws_cloudwatch_log_group" "flow_logs" {{
  name              = "/aws/vpc/${{local.name}}/flow-logs"
  retention_in_days = 90

  tags = local.tags
}}

resource "aws_iam_role" "flow_logs" {{
  name = "${{local.name}}-flow-logs-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {{
        Service = "vpc-flow-logs.amazonaws.com"
      }}
    }}]
  }})
}}

resource "aws_iam_role_policy" "flow_logs" {{
  name = "${{local.name}}-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ]
      Effect   = "Allow"
      Resource = "*"
    }}]
  }})
}}

resource "aws_flow_log" "main" {{
  vpc_id                   = aws_vpc.main.id
  traffic_type             = "ALL"
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.flow_logs.arn
  iam_role_arn             = aws_iam_role.flow_logs.arn
  max_aggregation_interval = 60

  tags = merge(local.tags, {{
    Name = "${{local.name}}-flow-log"
  }})
}}

# Default Security Group - Deny All (SOC 2)
resource "aws_default_security_group" "default" {{
  vpc_id = aws_vpc.main.id

  # No ingress or egress rules = deny all
  tags = merge(local.tags, {{
    Name = "${{local.name}}-default-sg-deny-all"
  }})
}}

# Outputs
output "vpc_id" {{
  description = "VPC ID"
  value       = aws_vpc.main.id
}}

output "public_subnet_ids" {{
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}}

output "private_subnet_ids" {{
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}}

output "nat_gateway_ip" {{
  description = "NAT Gateway public IP"
  value       = aws_eip.nat.public_ip
}}
'''

        return GeneratedInfrastructure(
            blueprint="networking/basic-vpc",
            terraform_code=terraform,
            variables={"name": name, "cidr": cidr, "azs": azs, "environment": environment},
            outputs=["vpc_id", "public_subnet_ids", "private_subnet_ids", "nat_gateway_ip"],
            compliance_notes=[
                "VPC Flow Logs enabled (CC7.2)",
                "Default security group denies all (CC6.6)",
                "No auto-assign public IP (CC6.6)",
                "Single NAT Gateway - consider HA for production",
                "SMART GENERATION: New VPC will be created",
            ],
            deployment_steps=[
                "1. Review and customize CIDR block if needed",
                "2. Run: terraform init",
                "3. Run: terraform plan",
                "4. Run: terraform apply",
                "5. Note outputs for dependent resources",
            ],
        )

    def _blueprint_standard_vpc(self, config: dict) -> GeneratedInfrastructure:
        """Generate standard HA VPC with WAF-ready setup."""
        name = config.get("name", "main")
        cidr = config.get("cidr", "10.0.0.0/16")
        environment = config.get("environment", "prod")

        terraform = f'''# Standard Compliant VPC with HA
# Generated by CARL - SOC 2 Compliant

terraform {{
  required_version = ">= 1.5.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

locals {{
  name        = "{name}"
  environment = "{environment}"
  cidr        = "{cidr}"
  azs         = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {{
    Name        = local.name
    Environment = local.environment
    ManagedBy   = "Terraform"
    Compliance  = "SOC2"
  }}
}}

data "aws_availability_zones" "available" {{
  state = "available"
}}

# VPC
resource "aws_vpc" "main" {{
  cidr_block           = local.cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.tags, {{
    Name = "${{local.name}}-vpc"
  }})
}}

# Internet Gateway
resource "aws_internet_gateway" "main" {{
  vpc_id = aws_vpc.main.id
  tags   = merge(local.tags, {{ Name = "${{local.name}}-igw" }})
}}

# Subnets - Public, Private, Isolated (3 tiers)
resource "aws_subnet" "public" {{
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(local.cidr, 4, count.index)
  availability_zone = local.azs[count.index]
  map_public_ip_on_launch = false

  tags = merge(local.tags, {{
    Name = "${{local.name}}-public-${{local.azs[count.index]}}"
    Tier = "public"
  }})
}}

resource "aws_subnet" "private" {{
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(local.cidr, 4, count.index + 4)
  availability_zone = local.azs[count.index]

  tags = merge(local.tags, {{
    Name = "${{local.name}}-private-${{local.azs[count.index]}}"
    Tier = "private"
  }})
}}

resource "aws_subnet" "isolated" {{
  count             = 3
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(local.cidr, 4, count.index + 8)
  availability_zone = local.azs[count.index]

  tags = merge(local.tags, {{
    Name = "${{local.name}}-isolated-${{local.azs[count.index]}}"
    Tier = "isolated"
  }})
}}

# NAT Gateways - One per AZ for HA
resource "aws_eip" "nat" {{
  count  = 3
  domain = "vpc"
  tags   = merge(local.tags, {{ Name = "${{local.name}}-nat-eip-${{count.index}}" }})
}}

resource "aws_nat_gateway" "main" {{
  count         = 3
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.tags, {{
    Name = "${{local.name}}-nat-${{local.azs[count.index]}}"
  }})

  depends_on = [aws_internet_gateway.main]
}}

# Route Tables
resource "aws_route_table" "public" {{
  vpc_id = aws_vpc.main.id

  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }}

  tags = merge(local.tags, {{ Name = "${{local.name}}-public-rt" }})
}}

resource "aws_route_table" "private" {{
  count  = 3
  vpc_id = aws_vpc.main.id

  route {{
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }}

  tags = merge(local.tags, {{
    Name = "${{local.name}}-private-rt-${{local.azs[count.index]}}"
  }})
}}

resource "aws_route_table" "isolated" {{
  vpc_id = aws_vpc.main.id
  # No routes to internet - isolated

  tags = merge(local.tags, {{ Name = "${{local.name}}-isolated-rt" }})
}}

# Route Table Associations
resource "aws_route_table_association" "public" {{
  count          = 3
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}}

resource "aws_route_table_association" "private" {{
  count          = 3
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}}

resource "aws_route_table_association" "isolated" {{
  count          = 3
  subnet_id      = aws_subnet.isolated[count.index].id
  route_table_id = aws_route_table.isolated.id
}}

# VPC Endpoints for AWS Services (reduces NAT costs)
resource "aws_vpc_endpoint" "s3" {{
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${{data.aws_region.current.name}}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(
    [aws_route_table.public.id],
    aws_route_table.private[*].id,
    [aws_route_table.isolated.id]
  )

  tags = merge(local.tags, {{ Name = "${{local.name}}-s3-endpoint" }})
}}

resource "aws_vpc_endpoint" "dynamodb" {{
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${{data.aws_region.current.name}}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(
    aws_route_table.private[*].id,
    [aws_route_table.isolated.id]
  )

  tags = merge(local.tags, {{ Name = "${{local.name}}-dynamodb-endpoint" }})
}}

data "aws_region" "current" {{}}

# VPC Flow Logs to S3 for long-term retention
resource "aws_s3_bucket" "flow_logs" {{
  bucket = "${{local.name}}-flow-logs-${{data.aws_caller_identity.current.account_id}}"
  tags   = local.tags
}}

resource "aws_s3_bucket_versioning" "flow_logs" {{
  bucket = aws_s3_bucket.flow_logs.id
  versioning_configuration {{ status = "Enabled" }}
}}

resource "aws_s3_bucket_server_side_encryption_configuration" "flow_logs" {{
  bucket = aws_s3_bucket.flow_logs.id
  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "aws:kms"
    }}
    bucket_key_enabled = true
  }}
}}

resource "aws_s3_bucket_public_access_block" "flow_logs" {{
  bucket                  = aws_s3_bucket.flow_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

resource "aws_s3_bucket_lifecycle_configuration" "flow_logs" {{
  bucket = aws_s3_bucket.flow_logs.id

  rule {{
    id     = "flow-logs-lifecycle"
    status = "Enabled"

    transition {{
      days          = 90
      storage_class = "STANDARD_IA"
    }}
    transition {{
      days          = 180
      storage_class = "GLACIER"
    }}
    expiration {{
      days = 365
    }}
  }}
}}

data "aws_caller_identity" "current" {{}}

resource "aws_flow_log" "main" {{
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination_type = "s3"
  log_destination      = aws_s3_bucket.flow_logs.arn
  max_aggregation_interval = 60

  tags = merge(local.tags, {{ Name = "${{local.name}}-flow-log" }})
}}

# Network ACLs for defense in depth
resource "aws_network_acl" "public" {{
  vpc_id     = aws_vpc.main.id
  subnet_ids = aws_subnet.public[*].id

  # Allow inbound HTTPS
  ingress {{
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }}

  # Allow inbound HTTP (for redirect to HTTPS)
  ingress {{
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 80
    to_port    = 80
  }}

  # Allow ephemeral ports for responses
  ingress {{
    protocol   = "tcp"
    rule_no    = 200
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }}

  # Allow all outbound
  egress {{
    protocol   = "-1"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }}

  tags = merge(local.tags, {{ Name = "${{local.name}}-public-nacl" }})
}}

# Default Security Group - Deny All
resource "aws_default_security_group" "default" {{
  vpc_id = aws_vpc.main.id
  tags   = merge(local.tags, {{ Name = "${{local.name}}-default-sg-deny-all" }})
}}

# Outputs
output "vpc_id" {{
  value = aws_vpc.main.id
}}

output "public_subnet_ids" {{
  value = aws_subnet.public[*].id
}}

output "private_subnet_ids" {{
  value = aws_subnet.private[*].id
}}

output "isolated_subnet_ids" {{
  value = aws_subnet.isolated[*].id
}}

output "nat_gateway_ips" {{
  value = aws_eip.nat[*].public_ip
}}

output "flow_logs_bucket" {{
  value = aws_s3_bucket.flow_logs.id
}}
'''

        return GeneratedInfrastructure(
            blueprint="networking/standard-vpc",
            terraform_code=terraform,
            variables={"name": name, "cidr": cidr, "environment": environment},
            outputs=["vpc_id", "public_subnet_ids", "private_subnet_ids", "isolated_subnet_ids", "nat_gateway_ips"],
            compliance_notes=[
                "3-AZ HA deployment (A1.1)",
                "NAT Gateway per AZ for fault tolerance",
                "VPC Flow Logs to S3 with lifecycle (CC7.2)",
                "VPC Endpoints reduce data transfer costs",
                "Network ACLs for defense in depth (CC6.6)",
                "Default SG denies all traffic (CC6.6)",
            ],
            deployment_steps=[
                "1. Review and customize variables",
                "2. Run: terraform init",
                "3. Run: terraform plan",
                "4. Run: terraform apply",
                "5. Configure WAF when adding ALB",
            ],
        )

    def _blueprint_enterprise_vpc(self, config: dict) -> GeneratedInfrastructure:
        """Generate enterprise VPC with Network Firewall."""
        # For brevity, return a summary - full implementation would be extensive
        return GeneratedInfrastructure(
            blueprint="networking/enterprise-vpc",
            terraform_code="""# Enterprise VPC with Network Firewall
# Full implementation available in CARL Enterprise

# Key components:
# - AWS Network Firewall with stateful rules
# - Centralized inspection architecture
# - AWS WAF with managed rules
# - Shield Advanced integration
# - Transit Gateway ready
# - Route 53 Resolver DNS Firewall

# Contact your administrator for full enterprise blueprint""",
            variables=config,
            outputs=["vpc_id", "network_firewall_endpoint", "waf_web_acl_arn"],
            compliance_notes=[
                "Deep packet inspection (CC6.6)",
                "DDoS protection (A1.1)",
                "DNS filtering (CC6.6)",
                "Centralized logging (CC7.2)",
            ],
            deployment_steps=[
                "1. Contact administrator for enterprise blueprint",
                "2. Review Network Firewall rules",
                "3. Plan for Shield Advanced costs",
            ],
        )

    # Stub implementations for other blueprints (would be fully implemented)
    def _blueprint_basic_ec2(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("compute/basic-ec2", config)

    def _blueprint_ecs_fargate(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("compute/ecs-fargate", config)

    def _blueprint_eks_cluster(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("compute/eks-cluster", config)

    def _blueprint_rds_single(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("database/rds-single", config)

    def _blueprint_rds_multi_az(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("database/rds-multi-az", config)

    def _blueprint_aurora_serverless(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("database/aurora-serverless", config)

    def _blueprint_compliant_s3(self, config: dict) -> GeneratedInfrastructure:
        name = config.get("name", "data")

        terraform = f'''# Compliant S3 Bucket
# Generated by CARL - SOC 2 Compliant

resource "aws_s3_bucket" "main" {{
  bucket = "{name}-${{data.aws_caller_identity.current.account_id}}"

  tags = {{
    Name       = "{name}"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

data "aws_caller_identity" "current" {{}}

# Versioning (SOC 2: Data protection)
resource "aws_s3_bucket_versioning" "main" {{
  bucket = aws_s3_bucket.main.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

# Encryption (SOC 2: CC6.5)
resource "aws_s3_bucket_server_side_encryption_configuration" "main" {{
  bucket = aws_s3_bucket.main.id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "aws:kms"
    }}
    bucket_key_enabled = true
  }}
}}

# Block public access (SOC 2: CC6.6)
resource "aws_s3_bucket_public_access_block" "main" {{
  bucket = aws_s3_bucket.main.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

# Access logging
resource "aws_s3_bucket" "logs" {{
  bucket = "{name}-logs-${{data.aws_caller_identity.current.account_id}}"
}}

resource "aws_s3_bucket_logging" "main" {{
  bucket = aws_s3_bucket.main.id

  target_bucket = aws_s3_bucket.logs.id
  target_prefix = "access-logs/"
}}

# Lifecycle policy
resource "aws_s3_bucket_lifecycle_configuration" "main" {{
  bucket = aws_s3_bucket.main.id

  rule {{
    id     = "archive-old-versions"
    status = "Enabled"

    noncurrent_version_transition {{
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }}

    noncurrent_version_transition {{
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }}

    noncurrent_version_expiration {{
      noncurrent_days = 365
    }}
  }}
}}

# Require SSL (SOC 2: CC6.7)
resource "aws_s3_bucket_policy" "require_ssl" {{
  bucket = aws_s3_bucket.main.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Sid       = "RequireSSL"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.main.arn,
        "${{aws_s3_bucket.main.arn}}/*"
      ]
      Condition = {{
        Bool = {{
          "aws:SecureTransport" = "false"
        }}
      }}
    }}]
  }})
}}

output "bucket_name" {{
  value = aws_s3_bucket.main.id
}}

output "bucket_arn" {{
  value = aws_s3_bucket.main.arn
}}
'''

        return GeneratedInfrastructure(
            blueprint="storage/compliant-s3",
            terraform_code=terraform,
            variables={"name": name},
            outputs=["bucket_name", "bucket_arn"],
            compliance_notes=[
                "Versioning enabled (A1.2)",
                "KMS encryption (CC6.5)",
                "Public access blocked (CC6.6)",
                "SSL required (CC6.7)",
                "Access logging enabled (CC7.2)",
            ],
            deployment_steps=[
                "1. Customize bucket name",
                "2. terraform init && terraform apply",
                "3. Configure bucket policy for your use case",
            ],
        )

    def _blueprint_secure_s3(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("storage/secure-s3", config)

    def _blueprint_security_basic(self, config: dict) -> GeneratedInfrastructure:
        """Generate basic security stack - SMART generation (GuardDuty, Security Hub, CloudTrail)."""
        name = config.get("name", "basic")
        environment = config.get("environment", "dev")

        # Scan environment to detect existing resources
        logger.info("Scanning AWS environment for existing security resources...")
        status = self.detector.detect_security_resources()

        # Build detection summary
        detection_notes = []
        if status.guardduty_exists:
            detection_notes.append(f"✓ GuardDuty already exists (using existing: {status.guardduty_detector_id})")
        else:
            detection_notes.append("✗ GuardDuty not found (will create)")

        if status.security_hub_exists:
            detection_notes.append("✓ Security Hub already enabled (using existing)")
        else:
            detection_notes.append("✗ Security Hub not enabled (will enable with AWS Foundational standard)")

        if status.cloudtrail_exists:
            detection_notes.append(f"✓ CloudTrail already active (using existing: {status.cloudtrail_name})")
        else:
            detection_notes.append("✗ CloudTrail not found (will create with 1-year retention)")

        # Build Terraform code dynamically
        terraform_header = f'''# Basic Security Stack
# Generated by CARL - Smart Infrastructure Generation
#
# CARL scanned your AWS environment and detected:
{"".join([f"#   {note}" + chr(10) for note in detection_notes])}
#
# This code only creates the missing resources. Existing resources will be imported via data sources.

terraform {{
  required_version = ">= 1.5.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

locals {{
  name        = "{name}"
  environment = "{environment}"

  tags = {{
    Name        = local.name
    Environment = local.environment
    ManagedBy   = "Terraform"
  }}
}}

data "aws_caller_identity" "current" {{}}
data "aws_region" "current" {{}}

'''

        # Build resource sections dynamically
        terraform_resources = []

        # GuardDuty
        if status.guardduty_exists:
            terraform_resources.append(self._gen_guardduty_data_source(status.guardduty_detector_id))
        else:
            # Use simpler GuardDuty for basic stack (no advanced data sources)
            terraform_resources.append(f'''# ============================================================================
# GuardDuty - Threat Detection
# ============================================================================

resource "aws_guardduty_detector" "main" {{
  enable                       = true
  finding_publishing_frequency = "SIX_HOURS"

  tags = local.tags
}}
''')

        # Security Hub
        if status.security_hub_exists:
            terraform_resources.append(self._gen_security_hub_data_source())
        else:
            # Use simpler Security Hub for basic stack (only AWS Foundational standard)
            terraform_resources.append(f'''# ============================================================================
# Security Hub - Centralized Security
# ============================================================================

resource "aws_securityhub_account" "main" {{}}

resource "aws_securityhub_standards_subscription" "aws_foundational" {{
  standards_arn = "arn:aws:securityhub:${{data.aws_region.current.name}}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.main]
}}
''')

        # CloudTrail
        if status.cloudtrail_exists:
            terraform_resources.append(self._gen_cloudtrail_data_source(status.cloudtrail_name, status.cloudtrail_bucket))
        else:
            terraform_resources.append(self._gen_cloudtrail_tf(name, retention_days=365))  # 1 year for basic

        # Build outputs dynamically
        if status.guardduty_exists:
            guardduty_output = f'''output "guardduty_detector_id" {{
  description = "GuardDuty detector ID (existing)"
  value       = data.aws_guardduty_detector.existing.id
}}
'''
        else:
            guardduty_output = f'''output "guardduty_detector_id" {{
  description = "GuardDuty detector ID (created)"
  value       = aws_guardduty_detector.main.id
}}
'''

        if status.security_hub_exists:
            security_hub_output = f'''output "security_hub_status" {{
  description = "Security Hub status (existing)"
  value       = "enabled"
}}
'''
        else:
            security_hub_output = f'''output "security_hub_arn" {{
  description = "Security Hub ARN (created)"
  value       = aws_securityhub_account.main.id
}}
'''

        if status.cloudtrail_exists:
            cloudtrail_output = f'''output "cloudtrail_name" {{
  description = "CloudTrail trail name (existing)"
  value       = data.aws_cloudtrail.existing.name
}}

output "cloudtrail_bucket" {{
  description = "CloudTrail S3 bucket (existing)"
  value       = data.aws_cloudtrail.existing.s3_bucket_name
}}
'''
        else:
            cloudtrail_output = f'''output "cloudtrail_name" {{
  description = "CloudTrail trail name (created)"
  value       = aws_cloudtrail.main.id
}}

output "cloudtrail_bucket" {{
  description = "CloudTrail S3 bucket (created)"
  value       = aws_s3_bucket.cloudtrail.id
}}
'''

        terraform_outputs = f'''# ============================================================================
# Outputs
# ============================================================================

{guardduty_output}
{security_hub_output}
{cloudtrail_output}'''

        # Combine everything
        terraform = terraform_header + "\n".join(terraform_resources) + "\n" + terraform_outputs

        # Build compliance notes based on what was created/found
        compliance_notes = []
        if not status.guardduty_exists:
            compliance_notes.append("GuardDuty threat detection enabled")
        else:
            compliance_notes.append(f"Using existing GuardDuty: {status.guardduty_detector_id}")

        if not status.security_hub_exists:
            compliance_notes.append("Security Hub with AWS Foundational Security standard")
        else:
            compliance_notes.append("Using existing Security Hub")

        if not status.cloudtrail_exists:
            compliance_notes.append("Multi-region CloudTrail with 1-year retention")
        else:
            compliance_notes.append(f"Using existing CloudTrail: {status.cloudtrail_name}")

        compliance_notes.extend([
            "S3 encryption and versioning enabled",
            "SMART GENERATION: Only creates missing resources",
            "For full SOC 2 compliance, use security/soc2-stack instead",
        ])

        # Build deployment steps
        deployment_steps = [
            "1. Review generated code - only missing resources will be created",
            "2. terraform init",
            "3. terraform plan (verify correct resources)",
            "4. terraform apply",
        ]

        if not status.security_hub_exists:
            deployment_steps.append("5. Review Security Hub findings after 24 hours")
        else:
            deployment_steps.append("5. Check existing Security Hub findings")

        deployment_steps.append("6. Consider upgrading to security/soc2-stack for full compliance (adds AWS Config + 7-year retention)")

        return GeneratedInfrastructure(
            blueprint="security/basic-stack",
            terraform_code=terraform,
            variables={"name": name, "environment": environment},
            outputs=["guardduty_detector_id", "security_hub_arn", "cloudtrail_name"],
            compliance_notes=compliance_notes,
            deployment_steps=deployment_steps,
        )

    def _blueprint_security_soc2(self, config: dict) -> GeneratedInfrastructure:
        """Generate SOC 2 compliant security stack - SMART generation based on existing resources."""
        name = config.get("name", "main")
        environment = config.get("environment", "prod")
        alert_email = config.get("alert_email", "security@example.com")

        # Scan environment to detect existing resources
        logger.info("Scanning AWS environment for existing security resources...")
        status = self.detector.detect_security_resources()

        # Build detection summary for user
        detection_notes = []
        if status.guardduty_exists:
            detection_notes.append(f"✓ GuardDuty already exists (using existing detector: {status.guardduty_detector_id})")
        else:
            detection_notes.append("✗ GuardDuty not found (will create new detector)")

        if status.security_hub_exists:
            detection_notes.append(f"✓ Security Hub already enabled (skipping creation)")
        else:
            detection_notes.append("✗ Security Hub not enabled (will enable with CIS + AWS Foundational standards)")

        if status.config_exists:
            detection_notes.append(f"✓ AWS Config already active (using existing recorder: {status.config_recorder_name})")
        else:
            detection_notes.append("✗ AWS Config not configured (will create recorder and delivery channel)")

        if status.cloudtrail_exists:
            detection_notes.append(f"✓ CloudTrail already active (using existing trail: {status.cloudtrail_name})")
        else:
            detection_notes.append("✗ CloudTrail not found (will create multi-region trail with 7-year retention)")

        # Build Terraform code dynamically
        terraform_header = f'''# SOC 2 Compliant Security Stack
# Generated by CARL - Smart Infrastructure Generation
#
# CARL scanned your AWS environment and detected:
{"".join([f"#   {note}" + chr(10) for note in detection_notes])}
#
# This code only creates the missing resources. Existing resources will be imported via data sources.

terraform {{
  required_version = ">= 1.5.0"
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

locals {{
  name        = "{name}"
  environment = "{environment}"
  alert_email = "{alert_email}"

  tags = {{
    Name        = local.name
    Environment = local.environment
    ManagedBy   = "Terraform"
    Compliance  = "SOC2"
  }}
}}

data "aws_caller_identity" "current" {{}}
data "aws_region" "current" {{}}

'''

        # Build resource sections dynamically
        terraform_resources = []

        # CloudTrail
        if status.cloudtrail_exists:
            terraform_resources.append(self._gen_cloudtrail_data_source(status.cloudtrail_name, status.cloudtrail_bucket))
        else:
            terraform_resources.append(self._gen_cloudtrail_tf(name, retention_days=2555))

        # AWS Config
        if status.config_exists:
            terraform_resources.append(self._gen_config_data_source(status.config_recorder_name))
        else:
            terraform_resources.append(self._gen_config_tf(name))

        # GuardDuty
        if status.guardduty_exists:
            terraform_resources.append(self._gen_guardduty_data_source(status.guardduty_detector_id))
        else:
            terraform_resources.append(self._gen_guardduty_tf(name))

        # Security Hub
        if status.security_hub_exists:
            terraform_resources.append(self._gen_security_hub_data_source())
        else:
            terraform_resources.append(self._gen_security_hub_tf(name))

        # Always add SNS and KMS (alerting and encryption)
        terraform_resources.append(f'''# ============================================================================
# CloudWatch Alarms & SNS Notifications (CC7.2)
# ============================================================================

resource "aws_sns_topic" "security_alerts" {{
  name              = "${{local.name}}-security-alerts"
  kms_master_key_id = "alias/aws/sns"

  tags = local.tags
}}

resource "aws_sns_topic_subscription" "security_email" {{
  topic_arn = aws_sns_topic.security_alerts.arn
  protocol  = "email"
  endpoint  = local.alert_email
}}

# CloudWatch Log Group for Security Events
resource "aws_cloudwatch_log_group" "security" {{
  name              = "/aws/security/${{local.name}}"
  retention_in_days = 365
  kms_key_id        = aws_kms_key.logs.arn

  tags = local.tags
}}

# KMS Key for Log Encryption
resource "aws_kms_key" "logs" {{
  description             = "KMS key for ${{local.name}} log encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {{
          AWS = "arn:aws:iam::${{data.aws_caller_identity.current.account_id}}:root"
        }}
        Action   = "kms:*"
        Resource = "*"
      }},
      {{
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {{
          Service = "logs.${{data.aws_region.current.name}}.amazonaws.com"
        }}
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:CreateGrant",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {{
          ArnLike = {{
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${{data.aws_region.current.name}}:${{data.aws_caller_identity.current.account_id}}:*"
          }}
        }}
      }}
    ]
  }})

  tags = local.tags
}}

resource "aws_kms_alias" "logs" {{
  name          = "alias/${{local.name}}-logs"
  target_key_id = aws_kms_key.logs.key_id
}}
''')

        # Build outputs dynamically
        if status.cloudtrail_exists:
            cloudtrail_output = f'''output "cloudtrail_name" {{
  description = "CloudTrail trail name (existing)"
  value       = data.aws_cloudtrail.existing.name
}}

output "cloudtrail_bucket" {{
  description = "CloudTrail S3 bucket (existing)"
  value       = data.aws_cloudtrail.existing.s3_bucket_name
}}
'''
        else:
            cloudtrail_output = f'''output "cloudtrail_name" {{
  description = "CloudTrail trail name (created)"
  value       = aws_cloudtrail.main.id
}}

output "cloudtrail_bucket" {{
  description = "CloudTrail S3 bucket (created)"
  value       = aws_s3_bucket.cloudtrail.id
}}
'''

        if status.config_exists:
            config_output = f'''output "config_recorder_name" {{
  description = "Config recorder name (existing)"
  value       = data.aws_config_recorder.existing.name
}}
'''
        else:
            config_output = f'''output "config_recorder_name" {{
  description = "Config recorder name (created)"
  value       = aws_config_configuration_recorder.main.name
}}
'''

        if status.guardduty_exists:
            guardduty_output = f'''output "guardduty_detector_id" {{
  description = "GuardDuty detector ID (existing)"
  value       = data.aws_guardduty_detector.existing.id
}}
'''
        else:
            guardduty_output = f'''output "guardduty_detector_id" {{
  description = "GuardDuty detector ID (created)"
  value       = aws_guardduty_detector.main.id
}}
'''

        if status.security_hub_exists:
            security_hub_output = f'''output "security_hub_status" {{
  description = "Security Hub status (existing)"
  value       = "enabled"
}}
'''
        else:
            security_hub_output = f'''output "security_hub_arn" {{
  description = "Security Hub ARN (created)"
  value       = aws_securityhub_account.main.id
}}
'''

        terraform_outputs = f'''# ============================================================================
# Outputs
# ============================================================================

{cloudtrail_output}
{config_output}
{guardduty_output}
{security_hub_output}
output "security_alerts_topic" {{
  description = "SNS topic for security alerts"
  value       = aws_sns_topic.security_alerts.arn
}}

output "kms_key_arn" {{
  description = "KMS key for log encryption"
  value       = aws_kms_key.logs.arn
}}
'''

        # Combine everything
        terraform = terraform_header + "\n".join(terraform_resources) + "\n" + terraform_outputs

        # Build compliance notes based on what was created/found
        compliance_notes = []
        if not status.cloudtrail_exists:
            compliance_notes.append("CloudTrail with 7-year retention created (CC7.2, A1.2)")
        else:
            compliance_notes.append(f"Using existing CloudTrail: {status.cloudtrail_name} (CC7.2, A1.2)")

        if not status.config_exists:
            compliance_notes.append("AWS Config continuous monitoring created (CC7.2, CC8.1)")
        else:
            compliance_notes.append(f"Using existing AWS Config: {status.config_recorder_name} (CC7.2, CC8.1)")

        if not status.guardduty_exists:
            compliance_notes.append("GuardDuty threat detection enabled (CC6.1, CC7.2)")
        else:
            compliance_notes.append(f"Using existing GuardDuty: {status.guardduty_detector_id} (CC6.1, CC7.2)")

        if not status.security_hub_exists:
            compliance_notes.append("Security Hub with CIS + AWS Foundational standards enabled (CC6.1)")
        else:
            compliance_notes.append("Using existing Security Hub (CC6.1)")

        compliance_notes.extend([
            "KMS encryption for logs (CC6.5)",
            "SNS alerts for security events (CC7.2)",
            "SMART GENERATION: Only creates missing resources",
        ])

        # Build deployment steps
        deployment_steps = [
            "1. Review generated code - only missing resources will be created",
            "2. Update alert_email if needed",
            "3. terraform init",
            "4. terraform plan (verify correct resources)",
            "5. terraform apply",
        ]

        if not status.cloudtrail_exists:
            deployment_steps.append("6. Verify CloudTrail is logging events")
        if not status.config_exists:
            deployment_steps.append("6. Wait for Config recorder to start")
        if not status.security_hub_exists:
            deployment_steps.append("7. Review Security Hub findings after 24 hours")
        else:
            deployment_steps.append("6. Check existing Security Hub findings")

        deployment_steps.append(f"Final: Check SNS subscription confirmation email at {alert_email}")

        return GeneratedInfrastructure(
            blueprint="security/soc2-stack",
            terraform_code=terraform,
            variables={"name": name, "environment": environment, "alert_email": alert_email},
            outputs=["cloudtrail_name", "config_recorder_name", "guardduty_detector_id"],
            compliance_notes=compliance_notes,
            deployment_steps=deployment_steps,
        )

    def _blueprint_serverless_api(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("serverless/api", config)

    # ========================================================================
    # Helper Methods for Smart Terraform Generation
    # ========================================================================

    def _gen_guardduty_tf(self, name: str) -> str:
        """Generate GuardDuty Terraform code."""
        return f'''# ============================================================================
# GuardDuty - Threat Detection (CC6.1, CC7.2)
# ============================================================================

resource "aws_guardduty_detector" "main" {{
  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"

  datasources {{
    s3_logs {{
      enable = true
    }}
    kubernetes {{
      audit_logs {{
        enable = true
      }}
    }}
    malware_protection {{
      scan_ec2_instance_with_findings {{
        ebs_volumes {{
          enable = true
        }}
      }}
    }}
  }}

  tags = local.tags
}}
'''

    def _gen_guardduty_data_source(self, detector_id: str) -> str:
        """Generate GuardDuty data source for existing detector."""
        return f'''# ============================================================================
# GuardDuty - Using Existing Detector
# ============================================================================

data "aws_guardduty_detector" "existing" {{}}

# Existing detector ID: {detector_id}
'''

    def _gen_security_hub_tf(self, name: str) -> str:
        """Generate Security Hub Terraform code."""
        return f'''# ============================================================================
# Security Hub - Centralized Security (CC6.1, CC7.2)
# ============================================================================

resource "aws_securityhub_account" "main" {{}}

resource "aws_securityhub_standards_subscription" "cis" {{
  standards_arn = "arn:aws:securityhub:${{data.aws_region.current.name}}::standards/cis-aws-foundations-benchmark/v/1.4.0"

  depends_on = [aws_securityhub_account.main]
}}

resource "aws_securityhub_standards_subscription" "aws_foundational" {{
  standards_arn = "arn:aws:securityhub:${{data.aws_region.current.name}}::standards/aws-foundational-security-best-practices/v/1.0.0"

  depends_on = [aws_securityhub_account.main]
}}
'''

    def _gen_security_hub_data_source(self) -> str:
        """Generate Security Hub data source for existing hub."""
        return f'''# ============================================================================
# Security Hub - Using Existing Hub
# ============================================================================

# Security Hub already enabled - no new resources created
'''

    def _gen_cloudtrail_tf(self, name: str, retention_days: int = 2555) -> str:
        """Generate CloudTrail Terraform code."""
        return f'''# ============================================================================
# CloudTrail - Audit Logging (CC7.2, A1.2)
# ============================================================================

resource "aws_cloudtrail" "main" {{
  name                          = "${{local.name}}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  event_selector {{
    read_write_type           = "All"
    include_management_events = true

    data_resource {{
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::*/"]
    }}
  }}

  insight_selector {{
    insight_type = "ApiCallRateInsight"
  }}

  tags = local.tags

  depends_on = [aws_s3_bucket_policy.cloudtrail]
}}

# CloudTrail S3 Bucket
resource "aws_s3_bucket" "cloudtrail" {{
  bucket = "${{local.name}}-cloudtrail-${{data.aws_caller_identity.current.account_id}}"

  tags = merge(local.tags, {{
    Purpose = "cloudtrail-logs"
  }})
}}

resource "aws_s3_bucket_versioning" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
  }}
}}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  rule {{
    id     = "cloudtrail-lifecycle"
    status = "Enabled"

    transition {{
      days          = 90
      storage_class = "STANDARD_IA"
    }}

    transition {{
      days          = 365
      storage_class = "GLACIER"
    }}

    expiration {{
      days = {retention_days}  # SOC 2: 7 years
    }}
  }}
}}

resource "aws_s3_bucket_policy" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {{
          Service = "cloudtrail.amazonaws.com"
        }}
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail.arn
      }},
      {{
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {{
          Service = "cloudtrail.amazonaws.com"
        }}
        Action   = "s3:PutObject"
        Resource = "${{aws_s3_bucket.cloudtrail.arn}}/*"
        Condition = {{
          StringEquals = {{
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }}
        }}
      }}
    ]
  }})
}}
'''

    def _gen_cloudtrail_data_source(self, trail_name: str, bucket_name: str) -> str:
        """Generate CloudTrail data source for existing trail."""
        return f'''# ============================================================================
# CloudTrail - Using Existing Trail
# ============================================================================

data "aws_cloudtrail" "existing" {{
  name = "{trail_name}"
}}

# Existing trail: {trail_name}
# Existing bucket: {bucket_name}
'''

    def _gen_config_tf(self, name: str) -> str:
        """Generate AWS Config Terraform code."""
        return f'''# ============================================================================
# AWS Config - Configuration Monitoring (CC7.2, CC8.1)
# ============================================================================

resource "aws_config_configuration_recorder" "main" {{
  name     = "${{local.name}}-recorder"
  role_arn = aws_iam_role.config.arn

  recording_group {{
    all_supported                 = true
    include_global_resource_types = true
  }}
}}

resource "aws_config_delivery_channel" "main" {{
  name           = "${{local.name}}-delivery-channel"
  s3_bucket_name = aws_s3_bucket.config.id

  snapshot_delivery_properties {{
    delivery_frequency = "TwentyFour_Hours"
  }}

  depends_on = [aws_config_configuration_recorder.main]
}}

resource "aws_config_configuration_recorder_status" "main" {{
  name       = aws_config_configuration_recorder.main.name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.main]
}}

# Config S3 Bucket
resource "aws_s3_bucket" "config" {{
  bucket = "${{local.name}}-config-${{data.aws_caller_identity.current.account_id}}"
  tags   = local.tags
}}

resource "aws_s3_bucket_versioning" "config" {{
  bucket = aws_s3_bucket.config.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

resource "aws_s3_bucket_server_side_encryption_configuration" "config" {{
  bucket = aws_s3_bucket.config.id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
  }}
}}

resource "aws_s3_bucket_public_access_block" "config" {{
  bucket = aws_s3_bucket.config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

resource "aws_s3_bucket_policy" "config" {{
  bucket = aws_s3_bucket.config.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Sid    = "AWSConfigBucketPermissionsCheck"
        Effect = "Allow"
        Principal = {{
          Service = "config.amazonaws.com"
        }}
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.config.arn
      }},
      {{
        Sid    = "AWSConfigBucketExistenceCheck"
        Effect = "Allow"
        Principal = {{
          Service = "config.amazonaws.com"
        }}
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.config.arn
      }},
      {{
        Sid    = "AWSConfigBucketPutObject"
        Effect = "Allow"
        Principal = {{
          Service = "config.amazonaws.com"
        }}
        Action   = "s3:PutObject"
        Resource = "${{aws_s3_bucket.config.arn}}/*"
        Condition = {{
          StringEquals = {{
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }}
        }}
      }}
    ]
  }})
}}

# Config IAM Role
resource "aws_iam_role" "config" {{
  name = "${{local.name}}-config-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {{
        Service = "config.amazonaws.com"
      }}
    }}]
  }})

  tags = local.tags
}}

resource "aws_iam_role_policy_attachment" "config" {{
  role       = aws_iam_role.config.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/ConfigRole"
}}

resource "aws_iam_role_policy" "config_s3" {{
  name = "${{local.name}}-config-s3-policy"
  role = aws_iam_role.config.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Action = [
        "s3:GetBucketVersioning",
        "s3:PutObject",
        "s3:GetObject"
      ]
      Resource = [
        aws_s3_bucket.config.arn,
        "${{aws_s3_bucket.config.arn}}/*"
      ]
    }}]
  }})
}}
'''

    def _gen_config_data_source(self, recorder_name: str) -> str:
        """Generate Config data source for existing recorder."""
        return f'''# ============================================================================
# AWS Config - Using Existing Configuration
# ============================================================================

data "aws_config_recorder" "existing" {{
  name = "{recorder_name}"
}}

# Existing recorder: {recorder_name}
'''

    def _gen_vpc_data_source(self, vpc_id: str, vpc_cidr: str, name: str) -> str:
        """Generate VPC data source for existing VPC."""
        return f'''# ============================================================================
# VPC - Using Existing VPC
# ============================================================================

data "aws_vpc" "existing" {{
  id = "{vpc_id}"
}}

# Existing VPC: {vpc_id} ({vpc_cidr})
# Note: Using existing VPC. Subnets, route tables, and gateways are not managed by this code.
# To manage networking resources, consider creating a new VPC or importing existing resources.
'''

    def _check_vpc_exists(self, name: str) -> tuple[bool, str, str]:
        """Check if VPC with given name exists. Returns (exists, vpc_id, cidr)."""
        vpc_status = self.detector.detect_vpc_resources(vpc_name_filter=name)
        return (vpc_status.vpc_exists, vpc_status.vpc_id or "", vpc_status.vpc_cidr or "")

    def _blueprint_rds_postgres(self, config: dict) -> GeneratedInfrastructure:
        """Generate PostgreSQL RDS with automated backups and encryption."""
        db_name = config.get("name", "app")
        instance_class = config.get("instance_class", "db.t3.micro")
        storage_gb = config.get("storage_gb", 20)

        terraform = f'''# PostgreSQL RDS Database
# Generated by CARL - SOC 2 Compliant

resource "aws_db_subnet_group" "main" {{
  name       = "{db_name}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {{
    Name       = "{db_name}-db-subnet-group"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

resource "aws_security_group" "db" {{
  name        = "{db_name}-db-sg"
  description = "Security group for {db_name} RDS PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {{
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.app_security_group_ids
    description     = "PostgreSQL from application tier"
  }}

  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }}

  tags = {{
    Name       = "{db_name}-db-sg"
    Compliance = "SOC2"
  }}
}}

# KMS key for encryption at rest (SOC 2: CC6.5)
resource "aws_kms_key" "rds" {{
  description             = "KMS key for {db_name} RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {{
    Name       = "{db_name}-rds-kms"
    Compliance = "SOC2"
  }}
}}

resource "aws_kms_alias" "rds" {{
  name          = "alias/{db_name}-rds"
  target_key_id = aws_kms_key.rds.key_id
}}

resource "aws_db_instance" "main" {{
  identifier     = "{db_name}-db"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "{instance_class}"

  allocated_storage     = {storage_gb}
  max_allocated_storage = {storage_gb * 2}
  storage_type          = "gp3"
  storage_encrypted     = true  # SOC 2: CC6.5
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = "{db_name}"
  username = "admin"
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false  # SOC 2: CC6.6

  # Backups (SOC 2: A1.2)
  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:00-mon:05:00"

  # Encryption in transit (SOC 2: CC6.7)
  ca_cert_identifier = "rds-ca-rsa2048-g1"

  # Monitoring (SOC 2: CC7.2)
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  # Protection
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "{db_name}-final-snapshot-${{formatdate("YYYY-MM-DD-hhmm", timestamp())}}"

  tags = {{
    Name       = "{db_name}-db"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

resource "random_password" "db_password" {{
  length  = 32
  special = true
}}

resource "aws_secretsmanager_secret" "db_password" {{
  name = "{db_name}-db-password"
}}

resource "aws_secretsmanager_secret_version" "db_password" {{
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}}

resource "aws_iam_role" "rds_monitoring" {{
  name = "{db_name}-rds-monitoring-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "monitoring.rds.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})
}}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {{
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}}

variable "vpc_id" {{
  description = "VPC ID where RDS will be deployed"
  type        = string
}}

variable "private_subnet_ids" {{
  description = "Private subnet IDs for RDS subnet group"
  type        = list(string)
}}

variable "app_security_group_ids" {{
  description = "Security group IDs that need database access"
  type        = list(string)
}}

output "db_endpoint" {{
  value       = aws_db_instance.main.endpoint
  description = "Database endpoint"
}}

output "db_name" {{
  value       = aws_db_instance.main.db_name
  description = "Database name"
}}

output "db_username" {{
  value       = aws_db_instance.main.username
  description = "Database username"
}}

output "db_password_secret_arn" {{
  value       = aws_secretsmanager_secret.db_password.arn
  description = "ARN of Secrets Manager secret containing database password"
}}
'''

        return GeneratedInfrastructure(
            blueprint="database/rds-postgres",
            terraform_code=terraform,
            variables={"name": db_name, "instance_class": instance_class, "storage_gb": storage_gb},
            outputs=["db_endpoint", "db_name", "db_username", "db_password_secret_arn"],
            compliance_notes=[
                "Encryption at rest with KMS (CC6.5)",
                "Not publicly accessible (CC6.6)",
                "SSL/TLS enforced (CC6.7)",
                "Automated backups enabled (A1.2)",
                "Enhanced monitoring enabled (CC7.2)",
                "Deletion protection enabled",
            ],
            deployment_steps=[
                "1. Provide VPC ID and subnet IDs",
                "2. terraform init && terraform apply",
                "3. Retrieve password from Secrets Manager",
                "4. Test connectivity from application tier",
            ],
        )

    def _blueprint_lambda_api(self, config: dict) -> GeneratedInfrastructure:
        """Generate Lambda + API Gateway REST API."""
        api_name = config.get("name", "api")

        terraform = f'''# Lambda + API Gateway REST API
# Generated by CARL - SOC 2 Compliant

resource "aws_lambda_function" "api" {{
  filename      = "lambda.zip"
  function_name = "{api_name}-function"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  environment {{
    variables = {{
      ENVIRONMENT = var.environment
    }}
  }}

  # Encryption (SOC 2: CC6.5)
  kms_key_arn = aws_kms_key.lambda.arn

  # Logging (SOC 2: CC7.2)
  logging_config {{
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.lambda.name
  }}

  tags = {{
    Name       = "{api_name}-function"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

resource "aws_kms_key" "lambda" {{
  description             = "KMS key for {api_name} Lambda"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {{
    Name = "{api_name}-lambda-kms"
  }}
}}

resource "aws_cloudwatch_log_group" "lambda" {{
  name              = "/aws/lambda/{api_name}-function"
  retention_in_days = 30  # SOC 2: CC7.2
  kms_key_id        = aws_kms_key.lambda.arn
}}

resource "aws_iam_role" "lambda" {{
  name = "{api_name}-lambda-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "lambda.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})
}}

resource "aws_iam_role_policy_attachment" "lambda_basic" {{
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}}

# API Gateway
resource "aws_api_gateway_rest_api" "main" {{
  name        = "{api_name}"
  description = "API Gateway for {api_name}"

  endpoint_configuration {{
    types = ["REGIONAL"]
  }}

  tags = {{
    Name       = "{api_name}-api"
    Compliance = "SOC2"
  }}
}}

resource "aws_api_gateway_resource" "proxy" {{
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "{{proxy+}}"
}}

resource "aws_api_gateway_method" "proxy" {{
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "AWS_IAM"  # SOC 2: CC6.2
}}

resource "aws_api_gateway_integration" "lambda" {{
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_method.proxy.resource_id
  http_method = aws_api_gateway_method.proxy.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.api.invoke_arn
}}

resource "aws_api_gateway_deployment" "main" {{
  depends_on = [
    aws_api_gateway_integration.lambda,
  ]

  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = var.environment
}}

# Enable CloudWatch logs for API Gateway (SOC 2: CC7.2)
resource "aws_api_gateway_method_settings" "all" {{
  rest_api_id = aws_api_gateway_rest_api.main.id
  stage_name  = aws_api_gateway_deployment.main.stage_name
  method_path = "*/*"

  settings {{
    logging_level      = "INFO"
    data_trace_enabled = true
    metrics_enabled    = true
  }}
}}

resource "aws_lambda_permission" "api_gateway" {{
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${{aws_api_gateway_rest_api.main.execution_arn}}/*/*"
}}

variable "environment" {{
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}}

output "api_endpoint" {{
  value       = aws_api_gateway_deployment.main.invoke_url
  description = "API Gateway endpoint URL"
}}

output "lambda_function_name" {{
  value       = aws_lambda_function.api.function_name
  description = "Lambda function name"
}}
'''

        return GeneratedInfrastructure(
            blueprint="compute/lambda-api",
            terraform_code=terraform,
            variables={"name": api_name},
            outputs=["api_endpoint", "lambda_function_name"],
            compliance_notes=[
                "IAM authorization required (CC6.2)",
                "Encrypted environment variables (CC6.5)",
                "API Gateway logging enabled (CC7.2)",
                "Lambda logs retained 30 days (CC7.2)",
                "KMS encryption for logs",
            ],
            deployment_steps=[
                "1. Create lambda.zip with your function code",
                "2. terraform init && terraform apply",
                "3. Test API endpoint with IAM credentials",
                "4. Set up IAM policies for API access",
            ],
        )

    def _blueprint_vpn_gateway(self, config: dict) -> GeneratedInfrastructure:
        """Generate Site-to-Site VPN Gateway."""
        vpn_name = config.get("name", "corporate")
        customer_gateway_ip = config.get("customer_gateway_ip", "203.0.113.1")

        terraform = f'''# Site-to-Site VPN Gateway
# Generated by CARL - SOC 2 Compliant

resource "aws_vpn_gateway" "main" {{
  vpc_id = var.vpc_id

  tags = {{
    Name       = "{vpn_name}-vpn-gateway"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

resource "aws_customer_gateway" "main" {{
  bgp_asn    = 65000
  ip_address = "{customer_gateway_ip}"
  type       = "ipsec.1"

  tags = {{
    Name       = "{vpn_name}-customer-gateway"
    Compliance = "SOC2"
  }}
}}

resource "aws_vpn_connection" "main" {{
  vpn_gateway_id      = aws_vpn_gateway.main.id
  customer_gateway_id = aws_customer_gateway.main.id
  type                = "ipsec.1"
  static_routes_only  = true

  # Tunnel options for high availability
  tunnel1_inside_cidr   = "169.254.10.0/30"
  tunnel1_preshared_key = random_password.tunnel1_psk.result

  tunnel2_inside_cidr   = "169.254.10.4/30"
  tunnel2_preshared_key = random_password.tunnel2_psk.result

  tags = {{
    Name       = "{vpn_name}-vpn-connection"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

resource "random_password" "tunnel1_psk" {{
  length  = 32
  special = false
}}

resource "random_password" "tunnel2_psk" {{
  length  = 32
  special = false
}}

# Store VPN configuration in Secrets Manager (SOC 2: CC6.5)
resource "aws_secretsmanager_secret" "vpn_config" {{
  name = "{vpn_name}-vpn-configuration"
}}

resource "aws_secretsmanager_secret_version" "vpn_config" {{
  secret_id = aws_secretsmanager_secret.vpn_config.id
  secret_string = jsonencode({{
    tunnel1_address    = aws_vpn_connection.main.tunnel1_address
    tunnel1_preshared_key = random_password.tunnel1_psk.result
    tunnel2_address    = aws_vpn_connection.main.tunnel2_address
    tunnel2_preshared_key = random_password.tunnel2_psk.result
    customer_gateway_configuration = aws_vpn_connection.main.customer_gateway_configuration
  }})
}}

# Route propagation for private subnets
resource "aws_vpn_gateway_route_propagation" "private" {{
  count = length(var.private_route_table_ids)

  vpn_gateway_id = aws_vpn_gateway.main.id
  route_table_id = var.private_route_table_ids[count.index]
}}

# CloudWatch alarms for VPN monitoring (SOC 2: CC7.2)
resource "aws_cloudwatch_metric_alarm" "tunnel1_down" {{
  alarm_name          = "{vpn_name}-vpn-tunnel1-down"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TunnelState"
  namespace           = "AWS/VPN"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "VPN Tunnel 1 is down"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {{
    VpnId = aws_vpn_connection.main.id
  }}
}}

variable "vpc_id" {{
  description = "VPC ID where VPN Gateway will be attached"
  type        = string
}}

variable "private_route_table_ids" {{
  description = "Private route table IDs for VPN route propagation"
  type        = list(string)
}}

variable "sns_topic_arn" {{
  description = "SNS topic ARN for VPN alerts"
  type        = string
}}

output "vpn_connection_id" {{
  value       = aws_vpn_connection.main.id
  description = "VPN connection ID"
}}

output "tunnel1_address" {{
  value       = aws_vpn_connection.main.tunnel1_address
  description = "Public IP of tunnel 1"
}}

output "tunnel2_address" {{
  value       = aws_vpn_connection.main.tunnel2_address
  description = "Public IP of tunnel 2"
}}

output "vpn_config_secret_arn" {{
  value       = aws_secretsmanager_secret.vpn_config.arn
  description = "ARN of Secrets Manager secret containing VPN configuration"
}}
'''

        return GeneratedInfrastructure(
            blueprint="networking/vpn-gateway",
            terraform_code=terraform,
            variables={"name": vpn_name, "customer_gateway_ip": customer_gateway_ip},
            outputs=["vpn_connection_id", "tunnel1_address", "tunnel2_address", "vpn_config_secret_arn"],
            compliance_notes=[
                "IPsec encryption for data in transit (CC6.7)",
                "VPN configuration stored in Secrets Manager (CC6.5)",
                "CloudWatch monitoring for tunnel status (CC7.2)",
                "Dual tunnels for high availability (A1.1)",
            ],
            deployment_steps=[
                "1. Provide your on-premises gateway public IP",
                "2. terraform init && terraform apply",
                "3. Retrieve tunnel configuration from Secrets Manager",
                "4. Configure your on-premises VPN device",
                "5. Verify both tunnels are up",
            ],
        )

    def _blueprint_cloudtrail_logging(self, config: dict) -> GeneratedInfrastructure:
        """Generate CloudTrail with S3 logging and SNS alerts."""
        trail_name = config.get("name", "organization")

        terraform = f'''# CloudTrail with S3 Logging and SNS Alerts
# Generated by CARL - SOC 2 Compliant

# S3 bucket for CloudTrail logs
resource "aws_s3_bucket" "cloudtrail" {{
  bucket = "{trail_name}-cloudtrail-logs-${{data.aws_caller_identity.current.account_id}}"

  tags = {{
    Name       = "{trail_name}-cloudtrail-logs"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

data "aws_caller_identity" "current" {{}}

# Block public access (SOC 2: CC6.6)
resource "aws_s3_bucket_public_access_block" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

# Versioning (SOC 2: A1.2)
resource "aws_s3_bucket_versioning" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  versioning_configuration {{
    status = "Enabled"
  }}
}}

# Encryption (SOC 2: CC6.5)
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.cloudtrail.id
    }}
    bucket_key_enabled = true
  }}
}}

# Lifecycle policy
resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  rule {{
    id     = "archive-old-logs"
    status = "Enabled"

    transition {{
      days          = 90
      storage_class = "GLACIER"
    }}

    expiration {{
      days = 2555  # 7 years retention for compliance
    }}
  }}
}}

# S3 bucket policy for CloudTrail
resource "aws_s3_bucket_policy" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {{
          Service = "cloudtrail.amazonaws.com"
        }}
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail.arn
      }},
      {{
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {{
          Service = "cloudtrail.amazonaws.com"
        }}
        Action   = "s3:PutObject"
        Resource = "${{aws_s3_bucket.cloudtrail.arn}}/AWSLogs/${{data.aws_caller_identity.current.account_id}}/*"
        Condition = {{
          StringEquals = {{
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }}
        }}
      }},
      {{
        Sid       = "RequireSSL"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.cloudtrail.arn,
          "${{aws_s3_bucket.cloudtrail.arn}}/*"
        ]
        Condition = {{
          Bool = {{
            "aws:SecureTransport" = "false"
          }}
        }}
      }}
    ]
  }})
}}

# KMS key for encryption
resource "aws_kms_key" "cloudtrail" {{
  description             = "KMS key for {trail_name} CloudTrail"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {{
          AWS = "arn:aws:iam::${{data.aws_caller_identity.current.account_id}}:root"
        }}
        Action   = "kms:*"
        Resource = "*"
      }},
      {{
        Sid    = "Allow CloudTrail to encrypt logs"
        Effect = "Allow"
        Principal = {{
          Service = "cloudtrail.amazonaws.com"
        }}
        Action = [
          "kms:GenerateDataKey*",
          "kms:DecryptDataKey"
        ]
        Resource = "*"
        Condition = {{
          StringLike = {{
            "kms:EncryptionContext:aws:cloudtrail:arn" = "arn:aws:cloudtrail:*:${{data.aws_caller_identity.current.account_id}}:trail/*"
          }}
        }}
      }}
    ]
  }})

  tags = {{
    Name = "{trail_name}-cloudtrail-kms"
  }}
}}

resource "aws_kms_alias" "cloudtrail" {{
  name          = "alias/{trail_name}-cloudtrail"
  target_key_id = aws_kms_key.cloudtrail.key_id
}}

# SNS topic for CloudTrail alerts (SOC 2: CC7.4)
resource "aws_sns_topic" "cloudtrail_alerts" {{
  name = "{trail_name}-cloudtrail-alerts"

  kms_master_key_id = aws_kms_key.cloudtrail.id

  tags = {{
    Name       = "{trail_name}-cloudtrail-alerts"
    Compliance = "SOC2"
  }}
}}

resource "aws_sns_topic_policy" "cloudtrail_alerts" {{
  arn = aws_sns_topic.cloudtrail_alerts.arn

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "cloudtrail.amazonaws.com"
      }}
      Action   = "SNS:Publish"
      Resource = aws_sns_topic.cloudtrail_alerts.arn
    }}]
  }})
}}

# CloudTrail
resource "aws_cloudtrail" "main" {{
  name                          = "{trail_name}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  sns_topic_name                = aws_sns_topic.cloudtrail_alerts.name
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true  # SOC 2: CC7.2
  kms_key_id                    = aws_kms_key.cloudtrail.arn

  event_selector {{
    read_write_type           = "All"
    include_management_events = true

    data_resource {{
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::*/"]
    }}
  }}

  insight_selector {{
    insight_type = "ApiCallRateInsight"
  }}

  tags = {{
    Name       = "{trail_name}-trail"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}

  depends_on = [
    aws_s3_bucket_policy.cloudtrail,
  ]
}}

output "cloudtrail_arn" {{
  value       = aws_cloudtrail.main.arn
  description = "CloudTrail ARN"
}}

output "s3_bucket_name" {{
  value       = aws_s3_bucket.cloudtrail.id
  description = "S3 bucket name for CloudTrail logs"
}}

output "sns_topic_arn" {{
  value       = aws_sns_topic.cloudtrail_alerts.arn
  description = "SNS topic ARN for CloudTrail alerts"
}}
'''

        return GeneratedInfrastructure(
            blueprint="security/cloudtrail-logging",
            terraform_code=terraform,
            variables={"name": trail_name},
            outputs=["cloudtrail_arn", "s3_bucket_name", "sns_topic_arn"],
            compliance_notes=[
                "Multi-region trail enabled (CC7.2)",
                "Log file validation enabled (CC7.2)",
                "KMS encryption for logs (CC6.5)",
                "S3 public access blocked (CC6.6)",
                "SNS alerts for CloudTrail events (CC7.4)",
                "7-year log retention (compliance)",
            ],
            deployment_steps=[
                "1. terraform init && terraform apply",
                "2. Subscribe email addresses to SNS topic",
                "3. Verify CloudTrail is logging events",
                "4. Set up CloudWatch Logs insights for log analysis",
            ],
        )

    def _blueprint_s3_static_website(self, config: dict) -> GeneratedInfrastructure:
        """Generate S3 static website with CloudFront CDN."""
        site_name = config.get("name", "website")
        domain_name = config.get("domain", f"{site_name}.example.com")

        terraform = f'''# S3 Static Website with CloudFront
# Generated by CARL - SOC 2 Compliant

# S3 bucket for website content
resource "aws_s3_bucket" "website" {{
  bucket = "{site_name}-${{data.aws_caller_identity.current.account_id}}"

  tags = {{
    Name       = "{site_name}-website"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

data "aws_caller_identity" "current" {{}}

# Block public access (CloudFront will access via OAI)
resource "aws_s3_bucket_public_access_block" "website" {{
  bucket = aws_s3_bucket.website.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

# Versioning (SOC 2: A1.2)
resource "aws_s3_bucket_versioning" "website" {{
  bucket = aws_s3_bucket.website.id

  versioning_configuration {{
    status = "Enabled"
  }}
}}

# Encryption (SOC 2: CC6.5)
resource "aws_s3_bucket_server_side_encryption_configuration" "website" {{
  bucket = aws_s3_bucket.website.id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
  }}
}}

# Website configuration
resource "aws_s3_bucket_website_configuration" "website" {{
  bucket = aws_s3_bucket.website.id

  index_document {{
    suffix = "index.html"
  }}

  error_document {{
    key = "error.html"
  }}
}}

# CloudFront Origin Access Identity (SOC 2: CC6.6)
resource "aws_cloudfront_origin_access_identity" "website" {{
  comment = "OAI for {site_name}"
}}

# S3 bucket policy for CloudFront OAI
resource "aws_s3_bucket_policy" "website" {{
  bucket = aws_s3_bucket.website.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Principal = {{
          AWS = aws_cloudfront_origin_access_identity.website.iam_arn
        }}
        Action   = "s3:GetObject"
        Resource = "${{aws_s3_bucket.website.arn}}/*"
      }},
      {{
        Sid       = "RequireSSL"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.website.arn,
          "${{aws_s3_bucket.website.arn}}/*"
        ]
        Condition = {{
          Bool = {{
            "aws:SecureTransport" = "false"
          }}
        }}
      }}
    ]
  }})
}}

# CloudFront distribution (SOC 2: CC6.7 - HTTPS)
resource "aws_cloudfront_distribution" "website" {{
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = ["{domain_name}"]

  origin {{
    domain_name = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id   = "S3-{site_name}"

    s3_origin_config {{
      origin_access_identity = aws_cloudfront_origin_access_identity.website.cloudfront_access_identity_path
    }}
  }}

  default_cache_behavior {{
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-{site_name}"

    forwarded_values {{
      query_string = false

      cookies {{
        forward = "none"
      }}
    }}

    viewer_protocol_policy = "redirect-to-https"  # SOC 2: CC6.7
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }}

  # Custom error responses
  custom_error_response {{
    error_code         = 404
    response_code      = 404
    response_page_path = "/error.html"
  }}

  restrictions {{
    geo_restriction {{
      restriction_type = "none"
    }}
  }}

  # SSL certificate (SOC 2: CC6.7)
  viewer_certificate {{
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }}

  # Logging (SOC 2: CC7.2)
  logging_config {{
    include_cookies = false
    bucket          = aws_s3_bucket.logs.bucket_domain_name
    prefix          = "cloudfront/"
  }}

  tags = {{
    Name       = "{site_name}-distribution"
    Compliance = "SOC2"
    ManagedBy  = "Terraform"
  }}
}}

# S3 bucket for access logs
resource "aws_s3_bucket" "logs" {{
  bucket = "{site_name}-logs-${{data.aws_caller_identity.current.account_id}}"

  tags = {{
    Name = "{site_name}-logs"
  }}
}}

resource "aws_s3_bucket_ownership_controls" "logs" {{
  bucket = aws_s3_bucket.logs.id

  rule {{
    object_ownership = "BucketOwnerPreferred"
  }}
}}

resource "aws_s3_bucket_acl" "logs" {{
  depends_on = [aws_s3_bucket_ownership_controls.logs]

  bucket = aws_s3_bucket.logs.id
  acl    = "log-delivery-write"
}}

variable "acm_certificate_arn" {{
  description = "ARN of ACM certificate for CloudFront (must be in us-east-1)"
  type        = string
}}

output "cloudfront_domain_name" {{
  value       = aws_cloudfront_distribution.website.domain_name
  description = "CloudFront distribution domain name"
}}

output "s3_bucket_name" {{
  value       = aws_s3_bucket.website.id
  description = "S3 bucket name for website content"
}}

output "cloudfront_distribution_id" {{
  value       = aws_cloudfront_distribution.website.id
  description = "CloudFront distribution ID"
}}
'''

        return GeneratedInfrastructure(
            blueprint="storage/s3-static-website",
            terraform_code=terraform,
            variables={"name": site_name, "domain": domain_name},
            outputs=["cloudfront_domain_name", "s3_bucket_name", "cloudfront_distribution_id"],
            compliance_notes=[
                "HTTPS enforced via CloudFront (CC6.7)",
                "S3 bucket not publicly accessible (CC6.6)",
                "S3 encryption enabled (CC6.5)",
                "CloudFront access logging (CC7.2)",
                "Versioning enabled (A1.2)",
                "TLS 1.2+ minimum",
            ],
            deployment_steps=[
                "1. Create ACM certificate in us-east-1 for your domain",
                "2. terraform init && terraform apply",
                "3. Upload website files to S3 bucket",
                "4. Update DNS to point to CloudFront domain",
                "5. Test website via HTTPS",
            ],
        )

    def _generate_stub(self, blueprint: str, config: dict) -> GeneratedInfrastructure:
        """Generate a stub for blueprints not yet fully implemented."""
        return GeneratedInfrastructure(
            blueprint=blueprint,
            terraform_code=f"""# Blueprint: {blueprint}
# Configuration: {json.dumps(config, indent=2)}

# Full Terraform code generation coming soon.
# Use /carl recommend to see architecture options.""",
            variables=config,
            outputs=[],
            compliance_notes=["Blueprint implementation in progress"],
            deployment_steps=["Contact administrator for full blueprint"],
        )
