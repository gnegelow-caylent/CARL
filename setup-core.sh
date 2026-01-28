#!/bin/bash
set -e

# CARL Minimal Core Setup
# Deploys just the essentials in ~5 minutes
# Cost: ~$10-20/month

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║      ██████╗ █████╗ ██████╗ ██╗                                 ║
║     ██╔════╝██╔══██╗██╔══██╗██║                                 ║
║     ██║     ███████║██████╔╝██║                                 ║
║     ██║     ██╔══██║██╔══██╗██║                                 ║
║     ╚██████╗██║  ██║██║  ██║███████╗                            ║
║      ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝                            ║
║                                                                  ║
║   Cloud Automated Risk & Compliance Logic                       ║
║   Quick Setup - Minimal Core (~$10-20/month)                    ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}\n"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}✗ Terraform not installed${NC}"
    echo "  Install from: https://www.terraform.io/downloads"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI not installed${NC}"
    echo "  Install from: https://aws.amazon.com/cli/"
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}✗ AWS credentials not configured${NC}"
    echo "  Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region || echo "us-east-1")

echo -e "${GREEN}✓ Terraform $(terraform version -json | jq -r '.terraform_version')${NC}"
echo -e "${GREEN}✓ AWS Account $ACCOUNT_ID${NC}"
echo -e "${GREEN}✓ AWS Region $REGION${NC}\n"

# Simple questions
echo -e "${BLUE}Quick Setup (3 questions)${NC}\n"

# Question 1: Environment
echo "1. Which environment are you deploying?"
echo "   dev  - Development/testing"
echo "   qa   - QA/staging"
echo "   prod - Production"
echo ""
read -p "Environment [dev]: " ENVIRONMENT
ENVIRONMENT=${ENVIRONMENT:-dev}

# Question 2: Slack (optional)
echo ""
echo "2. Do you have Slack credentials ready?"
echo "   (You can add these later with: terraform apply)"
echo ""
read -p "Configure Slack now? [y/N]: " HAS_SLACK

if [[ $HAS_SLACK =~ ^[Yy]$ ]]; then
    echo ""
    read -p "   Slack Bot Token (xoxb-...): " SLACK_BOT_TOKEN
    read -p "   Slack Signing Secret: " SLACK_SIGNING_SECRET
else
    SLACK_BOT_TOKEN=""
    SLACK_SIGNING_SECRET=""
    echo -e "${YELLOW}   Skipping Slack config (configure later)${NC}"
fi

# Question 3: State backend
echo ""
echo "3. Terraform state backend:"
echo "   remote - S3 bucket (team collaboration, recommended)"
echo "   local  - Local file (quick start, single user)"
echo ""
read -p "Backend [remote]: " BACKEND
BACKEND=${BACKEND:-remote}

# Summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}Configuration Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo "Environment:     $ENVIRONMENT"
echo "AWS Account:     $ACCOUNT_ID"
echo "AWS Region:      $REGION"
echo "Slack Enabled:   $([ -n "$SLACK_BOT_TOKEN" ] && echo 'Yes' || echo 'No (configure later)')"
echo "State Backend:   $BACKEND"
echo ""
echo -e "${YELLOW}Estimated Cost:  ~\$10-20/month${NC}"
echo ""
read -p "Deploy CARL core? [y/N]: " CONFIRM

if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Create backend if remote
if [ "$BACKEND" == "remote" ]; then
    echo ""
    echo -e "${YELLOW}Setting up remote state backend...${NC}"

    STATE_BUCKET="carl-tfstate-$ACCOUNT_ID"
    STATE_TABLE="carl-tfstate-locks"

    # Create S3 bucket
    if aws s3 ls "s3://$STATE_BUCKET" 2>&1 | grep -q 'NoSuchBucket'; then
        aws s3api create-bucket --bucket "$STATE_BUCKET" --region us-east-1
        aws s3api put-bucket-versioning --bucket "$STATE_BUCKET" --versioning-configuration Status=Enabled
        aws s3api put-bucket-encryption --bucket "$STATE_BUCKET" --server-side-encryption-configuration '{
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        }'
        echo -e "${GREEN}✓ Created S3 bucket: $STATE_BUCKET${NC}"
    else
        echo -e "${GREEN}✓ S3 bucket exists: $STATE_BUCKET${NC}"
    fi

    # Create DynamoDB table
    if ! aws dynamodb describe-table --table-name "$STATE_TABLE" --region us-east-1 &>/dev/null; then
        aws dynamodb create-table \
            --table-name "$STATE_TABLE" \
            --attribute-definitions AttributeName=LockID,AttributeType=S \
            --key-schema AttributeName=LockID,KeyType=HASH \
            --billing-mode PAY_PER_REQUEST \
            --region us-east-1 > /dev/null
        echo -e "${GREEN}✓ Created DynamoDB table: $STATE_TABLE${NC}"
    else
        echo -e "${GREEN}✓ DynamoDB table exists: $STATE_TABLE${NC}"
    fi

    # Create backend.tf
    cat > carl-infrastructure/core/backend.tf <<EOF
terraform {
  backend "s3" {
    bucket         = "$STATE_BUCKET"
    key            = "carl-core/$ENVIRONMENT/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "$STATE_TABLE"
  }
}
EOF
    echo -e "${GREEN}✓ Created backend configuration${NC}"
fi

# Generate terraform.tfvars
echo ""
echo -e "${YELLOW}Generating configuration...${NC}"

cd carl-infrastructure/core

cat > terraform.tfvars <<EOF
# CARL Core Configuration
# Generated: $(date)

environment = "$ENVIRONMENT"
region      = "$REGION"

EOF

if [ -n "$SLACK_BOT_TOKEN" ]; then
    cat >> terraform.tfvars <<EOF
# Slack credentials
slack_bot_token      = "$SLACK_BOT_TOKEN"
slack_signing_secret = "$SLACK_SIGNING_SECRET"

EOF
fi

cat >> terraform.tfvars <<EOF
tags = {
  Project     = "CARL"
  Environment = "$ENVIRONMENT"
  ManagedBy   = "Terraform"
}
EOF

echo -e "${GREEN}✓ Created terraform.tfvars${NC}"

# Deploy!
echo ""
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}Deploying CARL Core...${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"

terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Success!
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║                  CARL Core Deployed! 🎉                          ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get outputs
API_ENDPOINT=$(terraform output -raw api_endpoint 2>/dev/null || echo "N/A")
WEBHOOK_URL=$(terraform output -raw slack_webhook_url 2>/dev/null || echo "N/A")
LAMBDA_NAME=$(terraform output -raw lambda_function_name 2>/dev/null || echo "N/A")

echo -e "${BLUE}API Endpoint:${NC}    $API_ENDPOINT"
echo -e "${BLUE}Slack Webhook:${NC}   $WEBHOOK_URL"
echo -e "${BLUE}Lambda Function:${NC} $LAMBDA_NAME"
echo ""

if [ -z "$SLACK_BOT_TOKEN" ]; then
    echo -e "${YELLOW}⚠ Slack not configured yet${NC}"
    echo ""
    echo "To configure Slack later:"
    echo "  1. Create Slack App: https://api.slack.com/apps"
    echo "  2. Get bot token and signing secret"
    echo "  3. Run: terraform apply -var=\"slack_bot_token=xoxb-...\" -var=\"slack_signing_secret=...\""
    echo ""
else
    echo -e "${GREEN}✓ Slack configured${NC}"
    echo ""
    echo "Configure Slack App:"
    echo "  1. Go to https://api.slack.com/apps"
    echo "  2. Select your app"
    echo "  3. Under 'Event Subscriptions', set URL to:"
    echo "     $WEBHOOK_URL"
    echo "  4. Under 'Slash Commands', create /carl command"
    echo "  5. Test: /carl hello"
    echo ""
fi

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "  1. Test CARL in Slack:"
echo "     ${GREEN}/carl hello${NC}"
echo ""
echo "  2. CARL will ask what you want to do:"
echo "     • Monitor existing infrastructure"
echo "     • Build compliant infrastructure"
echo "     • Architecture advice only"
echo ""
echo "  3. CARL deploys features based on your choice"
echo ""
echo "  4. View logs:"
echo "     ${GREEN}aws logs tail /aws/lambda/$LAMBDA_NAME --follow${NC}"
echo ""
echo -e "${BLUE}Monthly Cost:${NC} ~\$10-20 (core only)"
echo ""
echo "Add features later to increase capabilities (and cost)"
echo ""

# Show detailed cost estimate
terraform output -raw estimated_monthly_cost

echo ""
echo -e "${GREEN}Setup complete! 🚀${NC}"
