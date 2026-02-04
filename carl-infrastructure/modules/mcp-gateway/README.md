# MCP Gateway Module

This module deploys MCP (Model Context Protocol) servers for CARL on AWS Bedrock AgentCore. It provides three specialized MCP servers that enhance CARL's capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Bedrock AgentCore                             │
│                   (Agent Runtime)                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Gateway                                  │
│              (Cognito JWT Authentication)                        │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │ GitHub MCP  │      │ Memory MCP  │      │Terraform MCP│
    │  (Lambda)   │      │  (Lambda)   │      │  (Lambda)   │
    └─────────────┘      └─────────────┘      └─────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │ GitHub API  │      │  DynamoDB   │      │  Terraform  │
    │             │      │ (Knowledge  │      │  Registry   │
    │             │      │   Graph)    │      │    API      │
    └─────────────┘      └─────────────┘      └─────────────┘
```

## MCP Servers

### 1. GitHub MCP

Repository and code management operations.

**Tools:**
| Tool | Description |
|------|-------------|
| `list_repositories` | List repos for org/user |
| `get_file_contents` | Read file from repo |
| `create_or_update_file` | Commit file changes |
| `create_branch` | Create new branch |
| `create_pull_request` | Open a PR |
| `list_pull_requests` | List PRs with filters |
| `create_terraform_pr` | Create branch, commit Terraform, open PR (convenience) |

**Example Usage:**
```python
# Create a PR with generated Terraform
result = create_terraform_pr(
    owner="my-org",
    repo="infrastructure",
    terraform_code=generated_code,
    file_path="modules/security/guardduty.tf",
    description="Enable GuardDuty for threat detection"
)
```

### 2. Memory MCP

Persistent knowledge graph for learning and pattern storage.

**Tools:**
| Tool | Description |
|------|-------------|
| `create_entity` | Create node with type and observations |
| `add_observation` | Add fact to existing entity |
| `create_relation` | Link entities with typed relation |
| `get_entity` | Retrieve entity with relations |
| `search_entities` | Search by name/observation content |
| `get_related_entities` | Get connected entities |
| `delete_entity` | Remove entity and relations |
| `get_full_graph` | Export entire graph |
| `store_learning_pattern` | Store learned patterns from interactions |

**Example Usage:**
```python
# Store a learned pattern
store_learning_pattern(
    pattern_name="iam-security-scan",
    question_pattern="IAM security questions",
    effective_scans=["scan_iam", "scan_security_hub"],
    resources_found=["iam_role", "iam_policy"],
    confidence=0.85
)

# Create entity relationships
create_entity("vpc-production", "aws_resource", ["Main production VPC"])
create_relation("vpc-production", "subnet-private-1", "contains")
```

### 3. Terraform MCP

Terraform validation, documentation, and module discovery.

**Tools:**
| Tool | Description |
|------|-------------|
| `validate_terraform` | Validate HCL syntax |
| `format_terraform` | Format code to canonical style |
| `get_provider_docs` | Get provider/resource documentation |
| `search_modules` | Search Terraform Registry |
| `get_module_details` | Get module info with usage example |
| `list_aws_resources` | List AWS resources by category |
| `generate_resource_skeleton` | Generate starter code for resource |

**Example Usage:**
```python
# Validate generated Terraform
result = validate_terraform(terraform_code)
if not result["valid"]:
    print("Errors:", result["errors"])

# Search for VPC modules
modules = search_modules("vpc", provider="aws")
```

## Usage

### Basic Module Usage

```hcl
module "mcp_gateway" {
  source = "./modules/mcp-gateway"

  environment = "dev"
  name_prefix = "carl-dev"
  aws_region  = "us-west-2"

  # GitHub MCP
  enable_github_mcp       = true
  github_token_secret_arn = aws_secretsmanager_secret.github_token.arn

  # Memory MCP
  enable_memory_mcp = true

  # Terraform MCP
  enable_terraform_mcp           = true
  terraform_cloud_token_secret_arn = aws_secretsmanager_secret.tf_cloud_token.arn

  tags = {
    Project     = "CARL"
    Environment = "dev"
  }
}
```

### Required Secrets

Store these in AWS Secrets Manager before deployment:

1. **GitHub Token** (for GitHub MCP)
   - Create a Personal Access Token with `repo` scope
   - Store as plain text secret

2. **Terraform Cloud Token** (optional, for Terraform MCP)
   - Only needed if using HCP Terraform workspaces
   - Store as plain text secret

## Deployment

### Build and Push Docker Images

```bash
# Set variables
ECR_REPO=$(terraform output -raw ecr_repository_url)
AWS_REGION=us-west-2

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO

# Build and push each MCP server
for mcp in github memory terraform; do
  cd mcp-servers/$mcp
  docker build --platform linux/arm64 -t $ECR_REPO:$mcp-latest .
  docker push $ECR_REPO:$mcp-latest
  cd ../..
done
```

### Deploy with Terraform

```bash
terraform init
terraform plan
terraform apply
```

## Outputs

| Output | Description |
|--------|-------------|
| `gateway_role_arn` | IAM role for gateway |
| `cognito_user_pool_id` | Cognito pool for auth |
| `cognito_discovery_url` | OIDC discovery URL |
| `github_mcp_function_arn` | GitHub Lambda ARN |
| `memory_mcp_function_arn` | Memory Lambda ARN |
| `terraform_mcp_function_arn` | Terraform Lambda ARN |
| `knowledge_graph_table_name` | DynamoDB table for memory |
| `ecr_repository_url` | ECR repository URL |

## Integration with AgentCore

To use these MCPs with a Bedrock AgentCore agent:

```python
from bedrock_agentcore import Agent

agent = Agent(
    name="carl-agent",
    mcp_servers=[
        "arn:aws:lambda:us-west-2:123456789:function:carl-dev-mcp-github",
        "arn:aws:lambda:us-west-2:123456789:function:carl-dev-mcp-memory",
        "arn:aws:lambda:us-west-2:123456789:function:carl-dev-mcp-terraform",
    ]
)
```

## Cost Estimate

| Component | Monthly Cost |
|-----------|--------------|
| Lambda (3 functions) | $0-5 (invocation based) |
| DynamoDB (knowledge graph) | $1-5 (on-demand) |
| ECR (images) | $0.10/GB |
| Cognito | Free tier (50k MAU) |
| **Total** | ~$5-15/month |

## Security

- All Lambda functions use least-privilege IAM roles
- Secrets accessed via AWS Secrets Manager
- JWT authentication via Cognito
- DynamoDB encrypted at rest
- ECR images scanned on push
