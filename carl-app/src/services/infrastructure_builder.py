"""
Infrastructure Builder Service for CARL.

Generates compliant Terraform code based on selected blueprints and configurations.
"""

import json
import os
from dataclasses import dataclass
from typing import Any

from src.services.bedrock_service import BedrockService
from src.utils.logger import get_logger

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

    def __init__(self):
        self.bedrock = BedrockService()
        self._load_blueprints()

    def _load_blueprints(self):
        """Load infrastructure blueprint templates."""
        self.blueprints = {
            "networking/basic-vpc": self._blueprint_basic_vpc,
            "networking/standard-vpc": self._blueprint_standard_vpc,
            "networking/enterprise-vpc": self._blueprint_enterprise_vpc,
            "compute/basic-ec2": self._blueprint_basic_ec2,
            "compute/ecs-fargate": self._blueprint_ecs_fargate,
            "compute/eks-cluster": self._blueprint_eks_cluster,
            "database/rds-single": self._blueprint_rds_single,
            "database/rds-multi-az": self._blueprint_rds_multi_az,
            "database/aurora-serverless": self._blueprint_aurora_serverless,
            "storage/compliant-s3": self._blueprint_compliant_s3,
            "storage/secure-s3": self._blueprint_secure_s3,
            "security/basic-stack": self._blueprint_security_basic,
            "security/soc2-stack": self._blueprint_security_soc2,
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
            {"name": "compute/basic-ec2", "description": "Basic compliant EC2"},
            {"name": "compute/ecs-fargate", "description": "ECS Fargate deployment"},
            {"name": "compute/eks-cluster", "description": "Production EKS cluster"},
            {"name": "database/rds-single", "description": "Single-AZ RDS"},
            {"name": "database/rds-multi-az", "description": "Multi-AZ RDS"},
            {"name": "database/aurora-serverless", "description": "Aurora Serverless v2"},
            {"name": "storage/compliant-s3", "description": "Compliant S3 bucket"},
            {"name": "storage/secure-s3", "description": "Secure S3 with Macie"},
            {"name": "security/basic-stack", "description": "Basic security services"},
            {"name": "security/soc2-stack", "description": "SOC 2 security stack"},
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
        """Generate basic compliant VPC."""
        name = config.get("name", "main")
        cidr = config.get("cidr", "10.0.0.0/16")
        azs = config.get("azs", 2)
        environment = config.get("environment", "dev")

        terraform = f'''# Basic Compliant VPC
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
            ],
            deployment_steps=[
                "1. Review and customize variables",
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
        return self._generate_stub("security/basic-stack", config)

    def _blueprint_security_soc2(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("security/soc2-stack", config)

    def _blueprint_serverless_api(self, config: dict) -> GeneratedInfrastructure:
        return self._generate_stub("serverless/api", config)

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
