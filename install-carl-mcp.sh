#!/bin/bash
# CARL MCP Installation Script
#
# Automates deployment of CARL infrastructure and MCP server setup
#
# Usage: ./install-carl-mcp.sh [--profile AWS_PROFILE] [--region REGION]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
AWS_PROFILE=${AWS_PROFILE:-default}
AWS_REGION="us-east-1"
ENVIRONMENT="prod"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --profile)
      AWS_PROFILE="$2"
      shift 2
      ;;
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --help)
      echo "CARL MCP Installation"
      echo ""
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --profile PROFILE    AWS profile name (default: default)"
      echo "  --region REGION      AWS region (default: us-east-1)"
      echo "  --environment ENV    Environment (default: prod)"
      echo "  --help               Show this help"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage"
      exit 1
      ;;
  esac
done

echo -e "${BLUE}🚀 CARL MCP Installation${NC}"
echo -e "${BLUE}=========================${NC}"
echo ""
echo "Configuration:"
echo "  AWS Profile: $AWS_PROFILE"
echo "  Region: $AWS_REGION"
echo "  Environment: $ENVIRONMENT"
echo ""

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install it first.${NC}"
    exit 1
fi

# Verify AWS credentials
echo -e "${YELLOW}🔑 Verifying AWS credentials...${NC}"
if ! aws sts get-caller-identity --profile $AWS_PROFILE &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not valid for profile: $AWS_PROFILE${NC}"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
echo -e "${GREEN}✓ AWS Account: $ACCOUNT_ID${NC}"

# Deploy Terraform infrastructure
echo ""
echo -e "${YELLOW}🏗️  Deploying CARL infrastructure...${NC}"
cd carl-infrastructure/mcp-deployment

terraform init

echo ""
echo -e "${BLUE}Running terraform plan...${NC}"
terraform plan \
  -var="environment=$ENVIRONMENT" \
  -var="region=$AWS_REGION" \
  -out=tfplan

echo ""
read -p "Deploy infrastructure? (yes/no): " DEPLOY
if [ "$DEPLOY" != "yes" ]; then
    echo -e "${YELLOW}⚠️  Deployment cancelled${NC}"
    exit 0
fi

terraform apply tfplan

echo -e "${GREEN}✓ Infrastructure deployed${NC}"

# Get outputs
ECR_REPO=$(terraform output -raw ecr_repository_url)
ASK_ARN=$(terraform output -json mcp_configuration | jq -r '.ask_agent_arn')
ARCHITECT_ARN=$(terraform output -json mcp_configuration | jq -r '.architect_agent_arn')
REMEDIATE_ARN=$(terraform output -json mcp_configuration | jq -r '.remediate_agent_arn')

# Build and push containers
echo ""
echo -e "${YELLOW}🐳 Building agent containers...${NC}"
cd ../../carl-infrastructure/agentcore-code

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | \
  docker login --username AWS --password-stdin $ECR_REPO

# Build Ask Agent
echo ""
echo -e "${BLUE}Building Ask Agent...${NC}"
docker buildx build --platform linux/arm64 \
  -t $ECR_REPO:agentcore-ask-$ENVIRONMENT \
  -f ask-agent/Dockerfile \
  --push . || {
    echo -e "${RED}❌ Failed to build Ask Agent${NC}"
    exit 1
  }
echo -e "${GREEN}✓ Ask Agent built and pushed${NC}"

# Build Architect Agent
echo ""
echo -e "${BLUE}Building Architect Agent...${NC}"
docker buildx build --platform linux/arm64 \
  -t $ECR_REPO:agentcore-architect-$ENVIRONMENT \
  -f architect-agent/Dockerfile \
  --push . || {
    echo -e "${RED}❌ Failed to build Architect Agent${NC}"
    exit 1
  }
echo -e "${GREEN}✓ Architect Agent built and pushed${NC}"

# Build Remediate Agent
echo ""
echo -e "${BLUE}Building Remediate Agent...${NC}"
docker buildx build --platform linux/arm64 \
  -t $ECR_REPO:agentcore-remediate-$ENVIRONMENT \
  -f remediate-agent/Dockerfile \
  --push . || {
    echo -e "${RED}❌ Failed to build Remediate Agent${NC}"
    exit 1
  }
echo -e "${GREEN}✓ Remediate Agent built and pushed${NC}"

# Install MCP Server
echo ""
echo -e "${YELLOW}📦 Installing CARL MCP Server...${NC}"
cd ../../carl-mcp-server
pip3 install -e .
echo -e "${GREEN}✓ MCP Server installed${NC}"

# Generate Claude Desktop config
echo ""
echo -e "${YELLOW}⚙️  Generating Claude Desktop configuration...${NC}"

CLAUDE_CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CLAUDE_CONFIG_DIR=$(dirname "$CLAUDE_CONFIG_FILE")

# Create directory if it doesn't exist
mkdir -p "$CLAUDE_CONFIG_DIR"

# Read existing config or create new
if [ -f "$CLAUDE_CONFIG_FILE" ]; then
    EXISTING_CONFIG=$(cat "$CLAUDE_CONFIG_FILE")
else
    EXISTING_CONFIG='{}'
fi

# Generate new CARL config
CARL_CONFIG=$(cat <<EOF
{
  "command": "python",
  "args": ["-m", "carl_mcp_server"],
  "env": {
    "AWS_PROFILE": "$AWS_PROFILE",
    "AWS_REGION": "$AWS_REGION",
    "CARL_AGENTCORE_ASK_ARN": "$ASK_ARN",
    "CARL_AGENTCORE_ARCHITECT_ARN": "$ARCHITECT_ARN",
    "CARL_AGENTCORE_REMEDIATE_ARN": "$REMEDIATE_ARN"
  }
}
EOF
)

# Merge configs using jq
echo "$EXISTING_CONFIG" | jq ".mcpServers.carl = $CARL_CONFIG" > "$CLAUDE_CONFIG_FILE"

echo -e "${GREEN}✓ Claude Desktop configured${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ CARL MCP Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Restart Claude Desktop"
echo "2. Test with: 'Use carl_ask to check my AWS security posture'"
echo ""
echo "AgentCore ARNs:"
echo "  Ask:        $ASK_ARN"
echo "  Architect:  $ARCHITECT_ARN"
echo "  Remediate:  $REMEDIATE_ARN"
echo ""
echo -e "${YELLOW}⚠️  Remember to restart Claude Desktop for changes to take effect!${NC}"
