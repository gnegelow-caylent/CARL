#!/bin/bash
set -e

# CARL Jira Configuration Script
# Adds Jira integration to an existing CARL installation

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                                                                  ║"
echo "║              CARL Jira Integration Configuration                 ║"
echo "║                                                                  ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

# Get AWS info
AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

# Check for required Jira credentials
if [ -z "$JIRA_URL" ] || [ -z "$JIRA_API_TOKEN" ]; then
    echo -e "${RED}✗${NC} Missing Jira credentials!"
    echo ""
    echo "Please set the following environment variables:"
    echo ""
    echo "  export JIRA_URL=https://your-domain.atlassian.net"
    echo "  export JIRA_API_TOKEN=your-api-token"
    echo "  export JIRA_USER=your-email@example.com  # Optional"
    echo "  export JIRA_PROJECT=CARL  # Optional, defaults to CARL"
    echo ""
    exit 1
fi

JIRA_USER=${JIRA_USER:-}
JIRA_PROJECT=${JIRA_PROJECT:-CARL}

echo -e "${GREEN}✓${NC} Jira credentials provided"
echo "  URL:     $JIRA_URL"
echo "  User:    ${JIRA_USER:-<not set>}"
echo "  Project: $JIRA_PROJECT"
echo ""

# Test Jira connection
echo -e "${BLUE}ℹ${NC} Testing Jira connection..."
if curl -s -u "${JIRA_USER}:${JIRA_API_TOKEN}" \
    -H "Accept: application/json" \
    "${JIRA_URL}/rest/api/3/myself" | grep -q accountId; then
    echo -e "${GREEN}✓${NC} Jira connection successful"
else
    echo -e "${RED}✗${NC} Failed to connect to Jira"
    echo ""
    echo "Please verify:"
    echo "  1. JIRA_URL is correct"
    echo "  2. JIRA_API_TOKEN is valid"
    echo "  3. JIRA_USER has access to the instance"
    echo ""
    exit 1
fi

# Verify project exists
echo -e "${BLUE}ℹ${NC} Verifying Jira project..."
if curl -s -u "${JIRA_USER}:${JIRA_API_TOKEN}" \
    "${JIRA_URL}/rest/api/3/project/${JIRA_PROJECT}" | grep -q key; then
    echo -e "${GREEN}✓${NC} Jira project '$JIRA_PROJECT' exists"
else
    echo -e "${YELLOW}⚠${NC} Jira project '$JIRA_PROJECT' not found"
    echo ""
    read -p "Do you want to use a different project key? [y/N]: " USE_DIFFERENT
    if [[ $USE_DIFFERENT =~ ^[Yy]$ ]]; then
        read -p "Enter project key: " JIRA_PROJECT
        if [ -z "$JIRA_PROJECT" ]; then
            echo -e "${RED}✗${NC} Project key cannot be empty"
            exit 1
        fi
    else
        echo ""
        echo "Please create the project in Jira first, then run this script again."
        exit 1
    fi
fi

# Store credentials in Secrets Manager
echo ""
echo -e "${BLUE}ℹ${NC} Storing Jira credentials in AWS Secrets Manager..."

JIRA_SECRET_NAME="carl/jira/credentials"
SECRET_STRING="{\"url\": \"${JIRA_URL}\", \"user\": \"${JIRA_USER}\", \"api_token\": \"${JIRA_API_TOKEN}\", \"project\": \"${JIRA_PROJECT}\"}"

if aws secretsmanager describe-secret --secret-id "$JIRA_SECRET_NAME" --region "$AWS_REGION" &>/dev/null; then
    # Update existing secret
    aws secretsmanager update-secret \
        --secret-id "$JIRA_SECRET_NAME" \
        --secret-string "$SECRET_STRING" \
        --region "$AWS_REGION" > /dev/null
    echo -e "${GREEN}✓${NC} Updated Jira credentials in Secrets Manager"
else
    # Create new secret
    aws secretsmanager create-secret \
        --name "$JIRA_SECRET_NAME" \
        --description "CARL Jira integration credentials" \
        --secret-string "$SECRET_STRING" \
        --region "$AWS_REGION" > /dev/null
    echo -e "${GREEN}✓${NC} Created Jira credentials in Secrets Manager"
fi

# Update Lambda environment variables to enable Jira integration
echo -e "${BLUE}ℹ${NC} Updating Lambda configuration..."

LAMBDA_NAME="carl-slack-router-dev"
if aws lambda get-function --function-name "$LAMBDA_NAME" --region "$AWS_REGION" &>/dev/null; then
    aws lambda update-function-configuration \
        --function-name "$LAMBDA_NAME" \
        --environment "Variables={
            JIRA_ENABLED=true,
            JIRA_SECRET_NAME=${JIRA_SECRET_NAME}
        }" \
        --region "$AWS_REGION" > /dev/null

    echo -e "${GREEN}✓${NC} Lambda configuration updated"
else
    echo -e "${YELLOW}⚠${NC} Lambda function not found - may need manual configuration"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║              Jira Integration Configured! 🎉                     ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "  1. Test the integration:"
echo "     ${CYAN}/carl scan${NC}"
echo ""
echo "  2. Check your Jira project for new issues"
echo ""
echo "  3. View Jira sync status:"
echo "     ${CYAN}/carl jira status${NC}"
echo ""

echo "Configuration complete!"
echo ""
