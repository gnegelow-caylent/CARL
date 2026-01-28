#!/bin/bash
set -e

# CARL Infrastructure Setup Wizard
# Interactive script to configure and deploy CARL

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║   CARL (Cloud Automated Risk & Compliance Logic)             ║"
echo "║   Infrastructure Setup Wizard                                ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed${NC}"
    echo "Install from: https://www.terraform.io/downloads"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    echo "Install from: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    echo "Run: aws configure"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓ AWS Account: $ACCOUNT_ID${NC}"
echo -e "${GREEN}✓ Terraform: $(terraform version -json | jq -r '.terraform_version')${NC}"
echo ""

# Question 1: AWS Account Structure
echo -e "${BLUE}[1/5] AWS Account Structure${NC}"
echo ""
echo "How do you want to deploy CARL?"
echo ""
echo "  1) Single AWS account (dev/qa/prod all in one)"
echo "     └─ Simplest setup. Use tags/naming to separate environments."
echo "     └─ Lowest cost but less security isolation."
echo "     └─ Good for: Startups, testing, small teams"
echo ""
echo "  2) Separate accounts per environment (RECOMMENDED)"
echo "     └─ Dev account, QA account, Prod account"
echo "     └─ Better security isolation, clear cost separation"
echo "     └─ Follows AWS best practices"
echo "     └─ Good for: Production deployments, growing teams"
echo ""
echo "  3) Already have AWS Organizations"
echo "     └─ You have existing AWS Organizations with multiple accounts"
echo "     └─ CARL will integrate with your existing structure"
echo "     └─ Good for: Enterprises, established AWS users"
echo ""
read -p "Select option [1-3]: " ACCOUNT_STRUCTURE

case $ACCOUNT_STRUCTURE in
    1)
        DEPLOYMENT_MODE="single-account"
        echo -e "${GREEN}Selected: Single account deployment${NC}"
        ;;
    2)
        DEPLOYMENT_MODE="multi-account"
        echo -e "${GREEN}Selected: Multi-account deployment${NC}"
        read -p "Enter Dev Account ID (12 digits): " DEV_ACCOUNT_ID
        read -p "Enter QA Account ID (12 digits): " QA_ACCOUNT_ID
        read -p "Enter Prod Account ID (12 digits): " PROD_ACCOUNT_ID
        ;;
    3)
        DEPLOYMENT_MODE="organizations"
        echo -e "${GREEN}Selected: AWS Organizations integration${NC}"
        read -p "Enter Organizations Management Account ID: " ORG_MGMT_ACCOUNT_ID
        ;;
    *)
        echo -e "${RED}Invalid selection${NC}"
        exit 1
        ;;
esac

echo ""

# Question 2: Terraform State Backend
echo -e "${BLUE}[2/5] Terraform State Storage${NC}"
echo ""
echo "Where should Terraform state be stored?"
echo ""
echo "  1) Create new S3 bucket + DynamoDB for state (RECOMMENDED)"
echo "     └─ Secure remote state with locking"
echo "     └─ Enables team collaboration"
echo "     └─ Cost: ~$1/month"
echo ""
echo "  2) Use existing S3 bucket"
echo "     └─ You already have a Terraform state bucket"
echo ""
echo "  3) Local state (NOT recommended for production)"
echo "     └─ Store state files locally on your machine"
echo "     └─ Quick start but risky for production"
echo ""
read -p "Select option [1-3]: " STATE_BACKEND

case $STATE_BACKEND in
    1)
        STATE_MODE="create-backend"
        STATE_BUCKET="carl-terraform-state-$ACCOUNT_ID"
        STATE_DYNAMODB_TABLE="carl-terraform-locks"
        echo -e "${GREEN}Will create: s3://$STATE_BUCKET${NC}"
        echo -e "${GREEN}Will create: DynamoDB table $STATE_DYNAMODB_TABLE${NC}"
        ;;
    2)
        STATE_MODE="existing-backend"
        read -p "Enter existing S3 bucket name: " STATE_BUCKET
        read -p "Enter DynamoDB table name (or leave empty): " STATE_DYNAMODB_TABLE
        ;;
    3)
        STATE_MODE="local"
        echo -e "${YELLOW}Warning: Local state is not recommended for production${NC}"
        read -p "Are you sure? [y/N]: " confirm
        if [[ ! $confirm =~ ^[Yy]$ ]]; then
            echo "Exiting..."
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}Invalid selection${NC}"
        exit 1
        ;;
esac

echo ""

# Question 3: Budget/Sizing
echo -e "${BLUE}[3/5] Monthly Budget${NC}"
echo ""
echo "What's your target monthly budget for CARL infrastructure?"
echo ""
echo "  1) Minimal: \$50-75/month (Maximum cost optimization)"
echo "     └─ DynamoDB: On-demand mode (pay-per-request)"
echo "     └─ Lambda: 128 MB memory, minimal concurrency"
echo "     └─ Bedrock: Claude Haiku ONLY for all queries"
echo "     └─ S3: Standard storage, no versioning"
echo "     └─ Single region (us-east-1)"
echo "     └─ Good for: Testing, proof-of-concept, startups"
echo ""
echo "  2) Moderate: \$100-200/month (Balanced - RECOMMENDED)"
echo "     └─ DynamoDB: On-demand with reserved capacity option"
echo "     └─ Lambda: 512 MB memory, moderate concurrency"
echo "     └─ Bedrock: Haiku for simple queries, Sonnet for complex"
echo "     └─ S3: Standard-IA for old data, versioning enabled"
echo "     └─ Single region with backup to secondary"
echo "     └─ Good for: Production use, growing teams"
echo ""
echo "  3) Standard: \$200-500/month (High availability)"
echo "     └─ DynamoDB: Provisioned with auto-scaling"
echo "     └─ Lambda: 1024 MB memory, reserved concurrency"
echo "     └─ Bedrock: Sonnet for most queries, caching layer"
echo "     └─ S3: Intelligent-Tiering, cross-region replication"
echo "     └─ Multi-region deployment"
echo "     └─ Good for: Enterprise, strict SLAs, high usage"
echo ""
echo "  4) Custom (I'll specify resources manually)"
echo ""
read -p "Select option [1-4]: " BUDGET_TIER

case $BUDGET_TIER in
    1)
        SIZING_PROFILE="minimal"
        BEDROCK_MODEL="claude-3-haiku-20240307"
        BEDROCK_FALLBACK="none"
        LAMBDA_MEMORY=128
        DYNAMODB_MODE="PAY_PER_REQUEST"
        REGIONS="us-east-1"
        echo -e "${GREEN}Selected: Minimal (\$50-75/month)${NC}"
        echo -e "${YELLOW}Cost optimization: Haiku-only, minimal resources${NC}"
        ;;
    2)
        SIZING_PROFILE="moderate"
        BEDROCK_MODEL="claude-3-haiku-20240307"  # Default to Haiku
        BEDROCK_FALLBACK="claude-3-5-sonnet-20241022"  # Sonnet for complex
        LAMBDA_MEMORY=512
        DYNAMODB_MODE="PAY_PER_REQUEST"
        REGIONS="us-east-1"
        echo -e "${GREEN}Selected: Moderate (\$100-200/month)${NC}"
        echo -e "${GREEN}Smart model selection: Haiku → Sonnet for complex queries${NC}"
        ;;
    3)
        SIZING_PROFILE="standard"
        BEDROCK_MODEL="claude-3-5-sonnet-20241022"
        BEDROCK_FALLBACK="claude-3-haiku-20240307"
        LAMBDA_MEMORY=1024
        DYNAMODB_MODE="PROVISIONED"
        read -p "Enable multi-region? [y/N]: " multi_region
        if [[ $multi_region =~ ^[Yy]$ ]]; then
            REGIONS="us-east-1,us-west-2"
        else
            REGIONS="us-east-1"
        fi
        echo -e "${GREEN}Selected: Standard (\$200-500/month)${NC}"
        ;;
    4)
        SIZING_PROFILE="custom"
        echo "Custom configuration - you'll edit terraform.tfvars manually"
        BEDROCK_MODEL="claude-3-haiku-20240307"
        LAMBDA_MEMORY=512
        DYNAMODB_MODE="PAY_PER_REQUEST"
        REGIONS="us-east-1"
        ;;
    *)
        echo -e "${RED}Invalid selection${NC}"
        exit 1
        ;;
esac

echo ""

# Question 4: Slack Integration
echo -e "${BLUE}[4/5] Slack Integration${NC}"
echo ""
read -p "Do you have a Slack workspace for CARL? [y/N]: " HAS_SLACK

if [[ $HAS_SLACK =~ ^[Yy]$ ]]; then
    echo ""
    echo "You'll need to create a Slack App at https://api.slack.com/apps"
    echo "Required permissions: chat:write, commands, users:read"
    echo ""
    read -p "Enter Slack Bot Token (xoxb-...): " SLACK_BOT_TOKEN
    read -p "Enter Slack Signing Secret: " SLACK_SIGNING_SECRET

    ENABLE_SLACK="true"
else
    ENABLE_SLACK="false"
    SLACK_BOT_TOKEN=""
    SLACK_SIGNING_SECRET=""
fi

echo ""

# Question 5: Environment
echo -e "${BLUE}[5/5] Environment Selection${NC}"
echo ""
echo "Which environment are you deploying?"
echo ""
echo "  1) dev   - Development environment"
echo "  2) qa    - QA/Staging environment"
echo "  3) prod  - Production environment"
echo ""
read -p "Select environment [1-3]: " ENV_SELECTION

case $ENV_SELECTION in
    1) ENVIRONMENT="dev" ;;
    2) ENVIRONMENT="qa" ;;
    3) ENVIRONMENT="prod" ;;
    *)
        echo -e "${RED}Invalid selection${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Selected: $ENVIRONMENT environment${NC}"

# Summary
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                     Configuration Summary                     ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Deployment Mode:     $DEPLOYMENT_MODE"
echo "Environment:         $ENVIRONMENT"
echo "AWS Account:         $ACCOUNT_ID"
echo "Sizing Profile:      $SIZING_PROFILE"
echo "Bedrock Model:       $BEDROCK_MODEL"
echo "Lambda Memory:       ${LAMBDA_MEMORY}MB"
echo "DynamoDB Mode:       $DYNAMODB_MODE"
echo "Regions:             $REGIONS"
echo "State Backend:       $STATE_MODE"
if [ "$STATE_MODE" != "local" ]; then
    echo "State Bucket:        $STATE_BUCKET"
fi
echo "Slack Enabled:       $ENABLE_SLACK"
echo ""

read -p "Proceed with deployment? [y/N]: " CONFIRM

if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Generate terraform.tfvars
echo ""
echo -e "${YELLOW}Generating configuration files...${NC}"

cat > terraform.tfvars <<EOF
# CARL Infrastructure Configuration
# Generated by setup.sh on $(date)

# Environment
environment = "$ENVIRONMENT"
aws_account_id = "$ACCOUNT_ID"
deployment_mode = "$DEPLOYMENT_MODE"

# Sizing Profile
sizing_profile = "$SIZING_PROFILE"

# Bedrock Configuration (Cost Optimization)
bedrock_model_id = "$BEDROCK_MODEL"
bedrock_fallback_model_id = "$BEDROCK_FALLBACK"

# Lambda Configuration
lambda_memory_size = $LAMBDA_MEMORY
lambda_timeout = 30
lambda_reserved_concurrent_executions = -1  # No reservation for cost savings

# DynamoDB Configuration
dynamodb_billing_mode = "$DYNAMODB_MODE"

# Networking
regions = [$(echo "$REGIONS" | sed 's/,/", "/g' | sed 's/^/"/' | sed 's/$/"/')]

# Slack Integration
enable_slack = $ENABLE_SLACK
slack_bot_token = "$SLACK_BOT_TOKEN"
slack_signing_secret = "$SLACK_SIGNING_SECRET"

# Cost Optimization Flags
enable_cost_optimization = true
enable_bedrock_caching = true
enable_lambda_snapstart = false  # Enable for Java if needed

# Tagging
tags = {
  Project = "CARL"
  Environment = "$ENVIRONMENT"
  ManagedBy = "Terraform"
  CostCenter = "Security-Compliance"
}
EOF

echo -e "${GREEN}✓ Created terraform.tfvars${NC}"

# Create backend configuration if needed
if [ "$STATE_MODE" == "create-backend" ]; then
    echo ""
    echo -e "${YELLOW}Creating state backend...${NC}"

    # Create S3 bucket for state
    aws s3api create-bucket \
        --bucket "$STATE_BUCKET" \
        --region us-east-1 || true

    aws s3api put-bucket-versioning \
        --bucket "$STATE_BUCKET" \
        --versioning-configuration Status=Enabled

    aws s3api put-bucket-encryption \
        --bucket "$STATE_BUCKET" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }'

    # Create DynamoDB table for locking
    aws dynamodb create-table \
        --table-name "$STATE_DYNAMODB_TABLE" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region us-east-1 || true

    echo -e "${GREEN}✓ State backend created${NC}"
fi

# Generate backend.tf
if [ "$STATE_MODE" != "local" ]; then
    cat > backend.tf <<EOF
terraform {
  backend "s3" {
    bucket         = "$STATE_BUCKET"
    key            = "carl/$ENVIRONMENT/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "$STATE_DYNAMODB_TABLE"
  }
}
EOF
    echo -e "${GREEN}✓ Created backend.tf${NC}"
fi

# Initialize and deploy
echo ""
echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init

echo ""
echo -e "${YELLOW}Creating execution plan...${NC}"
terraform plan -out=tfplan

echo ""
read -p "Review the plan above. Apply changes? [y/N]: " APPLY_CONFIRM

if [[ $APPLY_CONFIRM =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Applying Terraform configuration...${NC}"
    terraform apply tfplan

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                   Deployment Complete! 🎉                     ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Output useful information
    API_ENDPOINT=$(terraform output -raw api_endpoint 2>/dev/null || echo "N/A")
    LAMBDA_FUNCTION=$(terraform output -raw lambda_function_name 2>/dev/null || echo "N/A")

    echo "API Endpoint:        $API_ENDPOINT"
    echo "Lambda Function:     $LAMBDA_FUNCTION"
    echo ""
    echo "Next steps:"
    echo "  1. Configure Slack App webhook URL: $API_ENDPOINT/slack"
    echo "  2. Test with: /carl status"
    echo "  3. View logs: aws logs tail /aws/lambda/$LAMBDA_FUNCTION --follow"
    echo ""
    echo "Documentation: https://github.com/your-org/carl/tree/main/docs"
else
    echo "Apply cancelled. Run 'terraform apply tfplan' when ready."
fi
