#!/bin/bash
# CARL MCP Setup Script
# Sets up MCP server to use existing AgentCore deployment

set -e

echo "🚀 CARL MCP Setup"
echo "================="
echo ""
echo "This script will configure the MCP server to use your existing CARL infrastructure."
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Check AWS credentials
echo -e "${BLUE}Step 1: AWS Credentials${NC}"
echo "Which AWS profile should CARL use?"
read -p "AWS Profile name (default: carl-dev): " AWS_PROFILE
AWS_PROFILE=${AWS_PROFILE:-carl-dev}

# Test credentials
echo "Testing AWS credentials..."
ACCOUNT_ID=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text 2>/dev/null) || {
    echo -e "${RED}❌ AWS credentials not valid for profile: $AWS_PROFILE${NC}"
    echo ""
    echo "Please configure AWS credentials first:"
    echo "  aws configure --profile $AWS_PROFILE"
    exit 1
}

AWS_REGION=$(aws configure get region --profile $AWS_PROFILE)
AWS_REGION=${AWS_REGION:-us-east-1}

echo -e "${GREEN}✓ AWS Account: $ACCOUNT_ID${NC}"
echo -e "${GREEN}✓ Region: $AWS_REGION${NC}"
echo ""

# Step 2: Get AgentCore ARNs
echo -e "${BLUE}Step 2: Getting AgentCore ARNs${NC}"
echo "Retrieving ARNs from deployed infrastructure..."

cd carl-infrastructure/core

# Try to get ARNs from terraform
ASK_ARN=$(terraform output -raw agentcore_ask_runtime_arn 2>/dev/null) || ASK_ARN=""
ARCHITECT_ARN=$(terraform output -raw agentcore_architect_runtime_arn 2>/dev/null) || ARCHITECT_ARN=""
REMEDIATE_ARN=$(terraform output -raw agentcore_remediate_runtime_arn 2>/dev/null) || REMEDIATE_ARN=""

if [ -z "$ASK_ARN" ] || [ "$ASK_ARN" == "null" ]; then
    echo -e "${YELLOW}⚠️  Could not get ARNs from terraform output${NC}"
    echo ""
    echo "Please enter the AgentCore runtime ARNs manually."
    echo "You can find these in AWS Console > Bedrock > AgentCore > Runtimes"
    echo ""

    read -p "Ask Agent ARN: " ASK_ARN
    read -p "Architect Agent ARN: " ARCHITECT_ARN
    read -p "Remediate Agent ARN: " REMEDIATE_ARN
else
    echo -e "${GREEN}✓ Ask Agent: $ASK_ARN${NC}"
    echo -e "${GREEN}✓ Architect Agent: $ARCHITECT_ARN${NC}"
    echo -e "${GREEN}✓ Remediate Agent: $REMEDIATE_ARN${NC}"
fi
echo ""

# Step 3: Get DynamoDB and S3 info
echo -e "${BLUE}Step 3: Getting storage configuration${NC}"

# DynamoDB prefix (usually carl-dev or carl-prod)
ENVIRONMENT=$(echo $ASK_ARN | grep -o 'carl_[^_]*' | sed 's/carl_//' || echo "dev")
DYNAMODB_PREFIX="carl-${ENVIRONMENT}"

# S3 bucket names
EVIDENCE_BUCKET=$(terraform output -raw foundation_evidence_bucket 2>/dev/null) || EVIDENCE_BUCKET="${DYNAMODB_PREFIX}-evidence-${ACCOUNT_ID}"
REPORTS_BUCKET=$(terraform output -raw foundation_reports_bucket 2>/dev/null) || REPORTS_BUCKET="${DYNAMODB_PREFIX}-reports-${ACCOUNT_ID}"

echo -e "${GREEN}✓ DynamoDB prefix: $DYNAMODB_PREFIX${NC}"
echo -e "${GREEN}✓ Evidence bucket: $EVIDENCE_BUCKET${NC}"
echo -e "${GREEN}✓ Reports bucket: $REPORTS_BUCKET${NC}"
echo ""

# Step 4: Install MCP server
echo -e "${BLUE}Step 4: Installing MCP server${NC}"
cd ../../carl-mcp-server

if python3 -c "import carl_mcp_server" 2>/dev/null; then
    echo -e "${GREEN}✓ MCP server already installed${NC}"
else
    echo "Installing MCP server..."
    pip3 install -e . > /dev/null 2>&1
    echo -e "${GREEN}✓ MCP server installed${NC}"
fi
echo ""

# Step 5: Generate Claude Desktop config
echo -e "${BLUE}Step 5: Generating Claude Desktop configuration${NC}"

CLAUDE_CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
CLAUDE_CONFIG_DIR=$(dirname "$CLAUDE_CONFIG_FILE")

# Create directory if it doesn't exist
mkdir -p "$CLAUDE_CONFIG_DIR"

# Generate CARL config
CARL_CONFIG=$(cat <<EOF
{
  "command": "python3",
  "args": ["-m", "carl_mcp_server"],
  "env": {
    "AWS_PROFILE": "$AWS_PROFILE",
    "AWS_REGION": "$AWS_REGION",
    "CARL_AGENTCORE_ASK_ARN": "$ASK_ARN",
    "CARL_AGENTCORE_ARCHITECT_ARN": "$ARCHITECT_ARN",
    "CARL_AGENTCORE_REMEDIATE_ARN": "$REMEDIATE_ARN",
    "CARL_DYNAMODB_PREFIX": "$DYNAMODB_PREFIX",
    "CARL_S3_EVIDENCE_BUCKET": "$EVIDENCE_BUCKET",
    "CARL_S3_REPORTS_BUCKET": "$REPORTS_BUCKET"
  }
}
EOF
)

# Read existing config or create new
if [ -f "$CLAUDE_CONFIG_FILE" ]; then
    EXISTING_CONFIG=$(cat "$CLAUDE_CONFIG_FILE")
    echo "$EXISTING_CONFIG" | jq ".mcpServers.carl = $CARL_CONFIG" > "$CLAUDE_CONFIG_FILE"
    echo -e "${GREEN}✓ Updated existing Claude Desktop config${NC}"
else
    echo "{\"mcpServers\": {\"carl\": $CARL_CONFIG}}" | jq . > "$CLAUDE_CONFIG_FILE"
    echo -e "${GREEN}✓ Created new Claude Desktop config${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ CARL MCP Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Configuration saved to:"
echo "  $CLAUDE_CONFIG_FILE"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Restart Claude Desktop (Cmd+Q, then reopen)"
echo "2. Test with: 'Use carl_ask to check my AWS security posture'"
echo ""
echo "Available tools:"
echo "  • carl_ask - Intelligent Q&A"
echo "  • carl_architect - Architecture recommendations"
echo "  • carl_scan_environment - Direct AWS scanning"
echo "  • carl_remediate_finding - Fix security issues"
echo "  • carl_collect_evidence - Compliance evidence"
echo "  • carl_generate_report - Compliance reports"
echo ""
echo -e "${YELLOW}⚠️  Remember to restart Claude Desktop!${NC}"
