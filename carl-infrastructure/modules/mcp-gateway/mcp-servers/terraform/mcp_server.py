"""
Terraform MCP Server for CARL
Provides tools for Terraform validation, provider documentation lookup,
and module discovery from the Terraform Registry.

Deployed as Lambda function, invoked via:
{
    "tool": "validate_terraform",
    "args": {"terraform_code": "resource ..."}
}

Note: validate_terraform and format_terraform require Terraform CLI.
For Lambda, use registry and documentation lookup tools only.
"""

import os
import json
import subprocess
import tempfile
from typing import Optional, List
import urllib.request
import urllib.error


# Terraform Registry API base URL
REGISTRY_API = "https://registry.terraform.io/v1"


def registry_request(endpoint: str) -> dict:
    """Make request to Terraform Registry API."""
    url = f"{REGISTRY_API}{endpoint}"

    headers = {
        "Accept": "application/json",
        "User-Agent": "CARL-MCP-Terraform"
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise Exception(f"Registry API error: {e.code} - {error_body}")
    except urllib.error.URLError as e:
        raise Exception(f"Registry connection error: {e.reason}")


def validate_terraform(terraform_code: str, full_validation: bool = False) -> str:
    """
    Validate Terraform code syntax and structure.

    Two modes:
    - Quick mode (default): Uses terraform fmt to check HCL syntax (fast, no providers)
    - Full mode: Runs terraform init + validate (slower, catches more issues)

    Args:
        terraform_code: The Terraform HCL code to validate
        full_validation: If True, run full init+validate (slower but more thorough)

    Returns:
        JSON with validation result, errors if any
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write Terraform code to temp file
        tf_file = os.path.join(tmpdir, "main.tf")
        with open(tf_file, "w") as f:
            f.write(terraform_code)

        try:
            # Step 1: Quick syntax check with terraform fmt
            fmt_result = subprocess.run(
                ["terraform", "fmt", "-check", "-diff", "-no-color", tf_file],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=10
            )

            # If fmt fails with non-zero exit (syntax error), report it
            if fmt_result.returncode != 0 and fmt_result.stderr:
                return json.dumps({
                    "valid": False,
                    "message": "HCL syntax error",
                    "errors": [{"summary": fmt_result.stderr.strip()}],
                    "validation_type": "syntax"
                }, indent=2)

            # For quick validation, syntax check is enough
            if not full_validation:
                return json.dumps({
                    "valid": True,
                    "message": "HCL syntax is valid",
                    "diagnostics": [],
                    "validation_type": "syntax",
                    "note": "Use full_validation=true for complete provider validation"
                }, indent=2)

            # Step 2: Full validation with init + validate
            # Create a minimal provider config to avoid downloading
            provider_file = os.path.join(tmpdir, "providers.tf")
            with open(provider_file, "w") as f:
                f.write('''
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}
''')

            # Run terraform init with longer timeout
            init_result = subprocess.run(
                ["terraform", "init", "-backend=false", "-input=false", "-no-color"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=90  # Increased timeout for provider downloads
            )

            if init_result.returncode != 0:
                return json.dumps({
                    "valid": False,
                    "message": "Terraform init failed",
                    "errors": [{"summary": init_result.stderr.strip() or init_result.stdout.strip()}],
                    "validation_type": "full"
                }, indent=2)

            # Run terraform validate
            validate_result = subprocess.run(
                ["terraform", "validate", "-json", "-no-color"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30
            )

            validation = json.loads(validate_result.stdout)

            if validation.get("valid", False):
                return json.dumps({
                    "valid": True,
                    "message": "Terraform code is valid",
                    "diagnostics": [],
                    "validation_type": "full"
                }, indent=2)
            else:
                diagnostics = validation.get("diagnostics", [])
                errors = [
                    {
                        "severity": d.get("severity", "error"),
                        "summary": d.get("summary", "Unknown error"),
                        "detail": d.get("detail", ""),
                        "range": d.get("range", {})
                    }
                    for d in diagnostics
                ]
                return json.dumps({
                    "valid": False,
                    "message": "Terraform validation failed",
                    "errors": errors,
                    "validation_type": "full"
                }, indent=2)

        except subprocess.TimeoutExpired:
            return json.dumps({
                "valid": False,
                "message": "Validation timed out",
                "errors": [{"summary": "Terraform command timed out - try syntax-only validation"}]
            }, indent=2)
        except FileNotFoundError:
            return json.dumps({
                "valid": False,
                "message": "Terraform CLI not found",
                "errors": [{"summary": "Terraform is not installed or not in PATH"}]
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "valid": False,
                "message": f"Validation error: {str(e)}",
                "errors": [{"summary": str(e)}]
            }, indent=2)


def format_terraform(terraform_code: str) -> str:
    """
    Format Terraform code according to canonical style.
    Note: Requires Terraform CLI installed.

    Args:
        terraform_code: The Terraform HCL code to format

    Returns:
        JSON with formatted code
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tf_file = os.path.join(tmpdir, "main.tf")
        with open(tf_file, "w") as f:
            f.write(terraform_code)

        try:
            subprocess.run(
                ["terraform", "fmt", tf_file],
                capture_output=True,
                text=True,
                timeout=10
            )

            with open(tf_file, "r") as f:
                formatted_code = f.read()

            return json.dumps({
                "success": True,
                "formatted_code": formatted_code,
                "message": "Code formatted successfully"
            }, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "formatted_code": terraform_code,
                "message": f"Format error: {str(e)}"
            }, indent=2)


def get_provider_docs(
    provider: str,
    resource_type: Optional[str] = None,
    namespace: str = "hashicorp"
) -> str:
    """
    Get documentation for a Terraform provider or resource.

    Args:
        provider: Provider name (e.g., 'aws', 'google', 'azurerm')
        resource_type: Specific resource type (e.g., 's3_bucket', 'lambda_function')
        namespace: Provider namespace (default: 'hashicorp')

    Returns:
        JSON with provider/resource documentation
    """
    try:
        # Get provider info
        provider_info = registry_request(f"/providers/{namespace}/{provider}")

        result = {
            "provider": provider,
            "namespace": namespace,
            "version": provider_info.get("version", "unknown"),
            "description": provider_info.get("description", ""),
            "source": f"{namespace}/{provider}"
        }

        if resource_type:
            # Try to get specific resource docs
            # Note: Full docs require scraping or using provider schema
            result["resource_type"] = resource_type
            result["documentation_url"] = (
                f"https://registry.terraform.io/providers/{namespace}/{provider}/latest/docs/resources/{resource_type}"
            )

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "provider": provider
        }, indent=2)


def search_modules(
    query: str,
    provider: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for Terraform modules in the registry.

    Args:
        query: Search query (e.g., 'vpc', 'security group', 'lambda')
        provider: Filter by provider (e.g., 'aws', 'google')
        limit: Maximum results to return

    Returns:
        JSON list of matching modules
    """
    try:
        endpoint = f"/modules/search?q={query}&limit={limit}"
        if provider:
            endpoint += f"&provider={provider}"

        response = registry_request(endpoint)

        modules = [
            {
                "name": m.get("name"),
                "namespace": m.get("namespace"),
                "provider": m.get("provider"),
                "version": m.get("version"),
                "description": m.get("description", "")[:200],
                "downloads": m.get("downloads", 0),
                "source": f"{m.get('namespace')}/{m.get('name')}/{m.get('provider')}",
                "registry_url": f"https://registry.terraform.io/modules/{m.get('namespace')}/{m.get('name')}/{m.get('provider')}"
            }
            for m in response.get("modules", [])
        ]

        return json.dumps({
            "query": query,
            "provider": provider,
            "results": modules,
            "total_found": len(modules)
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "query": query
        }, indent=2)


def get_module_details(namespace: str, name: str, provider: str) -> str:
    """
    Get detailed information about a specific Terraform module.

    Args:
        namespace: Module namespace (e.g., 'terraform-aws-modules')
        name: Module name (e.g., 'vpc')
        provider: Provider (e.g., 'aws')

    Returns:
        JSON with module details including inputs, outputs, and examples
    """
    try:
        response = registry_request(f"/modules/{namespace}/{name}/{provider}")

        result = {
            "name": response.get("name"),
            "namespace": response.get("namespace"),
            "provider": response.get("provider"),
            "version": response.get("version"),
            "description": response.get("description"),
            "source": response.get("source"),
            "published_at": response.get("published_at"),
            "downloads": response.get("downloads", 0),
            "verified": response.get("verified", False),
            "root": response.get("root", {}),
            "submodules": [s.get("path") for s in response.get("submodules", [])],
            "versions": response.get("versions", [])[:10],  # Last 10 versions
            "usage": f'module "{name}" {{\n  source  = "{namespace}/{name}/{provider}"\n  version = "{response.get("version")}"\n\n  # Add required inputs here\n}}'
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "module": f"{namespace}/{name}/{provider}"
        }, indent=2)


def list_aws_resources(category: Optional[str] = None) -> str:
    """
    List common AWS Terraform resources by category.

    Args:
        category: Filter by category (compute, storage, network, security, database)

    Returns:
        JSON with categorized AWS resources
    """
    resources = {
        "compute": [
            {"resource": "aws_instance", "description": "EC2 instance"},
            {"resource": "aws_launch_template", "description": "EC2 launch template"},
            {"resource": "aws_autoscaling_group", "description": "Auto Scaling group"},
            {"resource": "aws_lambda_function", "description": "Lambda function"},
            {"resource": "aws_ecs_cluster", "description": "ECS cluster"},
            {"resource": "aws_ecs_service", "description": "ECS service"},
            {"resource": "aws_ecs_task_definition", "description": "ECS task definition"},
            {"resource": "aws_eks_cluster", "description": "EKS cluster"},
            {"resource": "aws_eks_node_group", "description": "EKS node group"},
        ],
        "storage": [
            {"resource": "aws_s3_bucket", "description": "S3 bucket"},
            {"resource": "aws_s3_bucket_versioning", "description": "S3 versioning"},
            {"resource": "aws_s3_bucket_server_side_encryption_configuration", "description": "S3 encryption"},
            {"resource": "aws_ebs_volume", "description": "EBS volume"},
            {"resource": "aws_efs_file_system", "description": "EFS file system"},
            {"resource": "aws_dynamodb_table", "description": "DynamoDB table"},
        ],
        "network": [
            {"resource": "aws_vpc", "description": "VPC"},
            {"resource": "aws_subnet", "description": "Subnet"},
            {"resource": "aws_internet_gateway", "description": "Internet gateway"},
            {"resource": "aws_nat_gateway", "description": "NAT gateway"},
            {"resource": "aws_route_table", "description": "Route table"},
            {"resource": "aws_security_group", "description": "Security group"},
            {"resource": "aws_lb", "description": "Load balancer (ALB/NLB)"},
            {"resource": "aws_lb_target_group", "description": "LB target group"},
            {"resource": "aws_lb_listener", "description": "LB listener"},
            {"resource": "aws_api_gateway_rest_api", "description": "API Gateway REST API"},
            {"resource": "aws_apigatewayv2_api", "description": "API Gateway HTTP API"},
        ],
        "security": [
            {"resource": "aws_iam_role", "description": "IAM role"},
            {"resource": "aws_iam_policy", "description": "IAM policy"},
            {"resource": "aws_iam_user", "description": "IAM user"},
            {"resource": "aws_kms_key", "description": "KMS key"},
            {"resource": "aws_secretsmanager_secret", "description": "Secrets Manager secret"},
            {"resource": "aws_ssm_parameter", "description": "SSM parameter"},
            {"resource": "aws_wafv2_web_acl", "description": "WAFv2 web ACL"},
            {"resource": "aws_guardduty_detector", "description": "GuardDuty detector"},
            {"resource": "aws_securityhub_account", "description": "Security Hub"},
        ],
        "database": [
            {"resource": "aws_db_instance", "description": "RDS instance"},
            {"resource": "aws_rds_cluster", "description": "Aurora cluster"},
            {"resource": "aws_elasticache_cluster", "description": "ElastiCache cluster"},
            {"resource": "aws_elasticache_replication_group", "description": "ElastiCache replication group"},
            {"resource": "aws_redshift_cluster", "description": "Redshift cluster"},
        ],
        "monitoring": [
            {"resource": "aws_cloudwatch_log_group", "description": "CloudWatch log group"},
            {"resource": "aws_cloudwatch_metric_alarm", "description": "CloudWatch alarm"},
            {"resource": "aws_cloudwatch_dashboard", "description": "CloudWatch dashboard"},
            {"resource": "aws_sns_topic", "description": "SNS topic"},
            {"resource": "aws_sqs_queue", "description": "SQS queue"},
        ]
    }

    if category and category.lower() in resources:
        return json.dumps({
            "category": category,
            "resources": resources[category.lower()]
        }, indent=2)

    return json.dumps({
        "categories": list(resources.keys()),
        "resources": resources
    }, indent=2)


def generate_resource_skeleton(resource_type: str) -> str:
    """
    Generate a skeleton Terraform configuration for a resource.

    Args:
        resource_type: AWS resource type (e.g., 'aws_s3_bucket', 'aws_lambda_function')

    Returns:
        JSON with skeleton Terraform code
    """
    skeletons = {
        "aws_s3_bucket": '''resource "aws_s3_bucket" "example" {
  bucket = "my-bucket-name"

  tags = {
    Name        = "My bucket"
    Environment = "dev"
  }
}

resource "aws_s3_bucket_versioning" "example" {
  bucket = aws_s3_bucket.example.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "example" {
  bucket = aws_s3_bucket.example.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}''',

        "aws_lambda_function": '''resource "aws_lambda_function" "example" {
  function_name = "my-function"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  filename         = "lambda.zip"
  source_code_hash = filebase64sha256("lambda.zip")

  memory_size = 256
  timeout     = 30

  environment {
    variables = {
      ENVIRONMENT = "dev"
    }
  }

  tags = {
    Name = "My Lambda"
  }
}''',

        "aws_iam_role": '''resource "aws_iam_role" "example" {
  name = "my-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "My Role"
  }
}

resource "aws_iam_role_policy_attachment" "example" {
  role       = aws_iam_role.example.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}''',

        "aws_security_group": '''resource "aws_security_group" "example" {
  name        = "my-security-group"
  description = "Security group for my application"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "My Security Group"
  }
}''',

        "aws_dynamodb_table": '''resource "aws_dynamodb_table" "example" {
  name         = "my-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name = "My Table"
  }
}'''
    }

    if resource_type in skeletons:
        return json.dumps({
            "resource_type": resource_type,
            "skeleton": skeletons[resource_type],
            "documentation_url": f"https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/{resource_type.replace('aws_', '')}"
        }, indent=2)

    return json.dumps({
        "resource_type": resource_type,
        "error": "Skeleton not available for this resource type",
        "documentation_url": f"https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/{resource_type.replace('aws_', '')}"
    }, indent=2)


# Lambda handler for AgentCore/direct invocation
def handler(event, context):
    """
    Lambda handler that routes to tool functions.

    Event format:
    {
        "tool": "search_modules",
        "args": {"query": "vpc", "provider": "aws"}
    }

    Returns:
    {
        "result": <tool output>,
        "error": null  # or error message if failed
    }
    """
    try:
        tool_name = event.get("tool")
        args = event.get("args", {})

        # Map tool names to functions
        tools = {
            "validate_terraform": validate_terraform,
            "format_terraform": format_terraform,
            "get_provider_docs": get_provider_docs,
            "search_modules": search_modules,
            "get_module_details": get_module_details,
            "list_aws_resources": list_aws_resources,
            "generate_resource_skeleton": generate_resource_skeleton,
        }

        if not tool_name:
            return {
                "result": None,
                "error": "No tool specified. Available tools: " + ", ".join(tools.keys())
            }

        if tool_name not in tools:
            return {
                "result": None,
                "error": f"Unknown tool: {tool_name}. Available tools: " + ", ".join(tools.keys())
            }

        # Execute the tool
        result = tools[tool_name](**args)

        return {
            "result": result,
            "error": None
        }

    except Exception as e:
        return {
            "result": None,
            "error": str(e)
        }
