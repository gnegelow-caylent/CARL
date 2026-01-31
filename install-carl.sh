#!/bin/bash
set -e

# CARL Automated Installer
# Deploys CARL with minimal user interaction
# Requirements: AWS CLI configured, Slack + GitHub App credentials

# ============================================================================
# Configuration & Colors
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_STATE_FILE=".carl-install-state.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# Banner
# ============================================================================

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
║   Automated Installer v2.0 (GitHub App)                         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}\n"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_step() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

save_state() {
    local key=$1
    local value=$2

    if [ ! -f "$INSTALL_STATE_FILE" ]; then
        echo "{\"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"resources_created\": {}}" > "$INSTALL_STATE_FILE"
    fi

    # Update state file with new resource
    jq ".resources_created.\"$key\" = \"$value\"" "$INSTALL_STATE_FILE" > "${INSTALL_STATE_FILE}.tmp"
    mv "${INSTALL_STATE_FILE}.tmp" "$INSTALL_STATE_FILE"
}

get_state() {
    local key=$1
    if [ -f "$INSTALL_STATE_FILE" ]; then
        jq -r ".resources_created.\"$key\" // empty" "$INSTALL_STATE_FILE"
    fi
}

# ============================================================================
# Rollback Function
# ============================================================================

rollback() {
    log_step "🔄 Rolling Back CARL Installation"

    if [ ! -f "$INSTALL_STATE_FILE" ]; then
        log_error "No installation state found. Nothing to rollback."
        exit 1
    fi

    log_warning "This will delete all CARL resources created during installation."
    read -p "Are you sure? [y/N]: " CONFIRM

    if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
        echo "Rollback cancelled."
        exit 0
    fi

    # Destroy Terraform infrastructure
    if [ "$(get_state terraform_deployed)" = "true" ]; then
        log_info "Destroying Terraform infrastructure..."
        cd "$SCRIPT_DIR/carl-infrastructure/core"
        terraform destroy -auto-approve || log_warning "Terraform destroy had errors (continuing)"
        cd "$SCRIPT_DIR"
        log_success "Terraform infrastructure destroyed"
    fi

    # Delete secrets
    SLACK_SECRET=$(get_state slack_secret_arn)
    if [ -n "$SLACK_SECRET" ]; then
        log_info "Deleting Slack credentials secret..."
        aws secretsmanager delete-secret --secret-id "$SLACK_SECRET" --force-delete-without-recovery 2>/dev/null || true
        log_success "Slack secret deleted"
    fi

    JIRA_SECRET=$(get_state jira_secret_arn)
    if [ -n "$JIRA_SECRET" ]; then
        log_info "Deleting Jira credentials secret..."
        aws secretsmanager delete-secret --secret-id "$JIRA_SECRET" --force-delete-without-recovery 2>/dev/null || true
        log_success "Jira secret deleted"
    fi

    GITHUB_SECRET=$(get_state github_secret_arn)
    if [ -n "$GITHUB_SECRET" ]; then
        log_info "Deleting GitHub App credentials secret..."
        aws secretsmanager delete-secret --secret-id "$GITHUB_SECRET" --force-delete-without-recovery 2>/dev/null || true
        log_success "GitHub App secret deleted"
    fi

    # Schedule KMS key deletion
    KMS_KEY=$(get_state kms_key_id)
    if [ -n "$KMS_KEY" ]; then
        log_info "Scheduling KMS key deletion (7 day window)..."
        aws kms schedule-key-deletion --key-id "$KMS_KEY" --pending-window-in-days 7 2>/dev/null || true
        log_success "KMS key scheduled for deletion"
    fi

    # Disable GuardDuty
    DETECTOR_ID=$(get_state guardduty_detector_id)
    if [ -n "$DETECTOR_ID" ]; then
        log_info "Disabling GuardDuty..."
        aws guardduty delete-detector --detector-id "$DETECTOR_ID" 2>/dev/null || true
        log_success "GuardDuty disabled"
    fi

    # Disable Security Hub
    if [ "$(get_state security_hub_enabled)" = "true" ]; then
        log_info "Disabling Security Hub..."
        aws securityhub disable-security-hub 2>/dev/null || true
        log_success "Security Hub disabled"
    fi

    # Delete DynamoDB lock table
    LOCK_TABLE=$(get_state dynamodb_lock_table)
    if [ -n "$LOCK_TABLE" ]; then
        log_info "Deleting DynamoDB lock table..."
        aws dynamodb delete-table --table-name "$LOCK_TABLE" 2>/dev/null || true
        log_success "DynamoDB lock table deleted"
    fi

    # Empty and delete S3 state bucket
    STATE_BUCKET=$(get_state s3_state_bucket)
    if [ -n "$STATE_BUCKET" ]; then
        log_info "Emptying and deleting S3 state bucket..."
        aws s3 rm "s3://${STATE_BUCKET}" --recursive 2>/dev/null || true
        aws s3api delete-bucket --bucket "$STATE_BUCKET" 2>/dev/null || true
        log_success "S3 state bucket deleted"
    fi

    # Remove state file
    rm -f "$INSTALL_STATE_FILE"

    log_success "Rollback complete!"
    exit 0
}

# Check for rollback flag
if [ "$1" = "--rollback" ]; then
    rollback
fi

# ============================================================================
# Step 1: Prerequisites Check
# ============================================================================

log_step "Step 1: Checking Prerequisites"

# Check required tools
MISSING_TOOLS=()

if ! command -v terraform &> /dev/null; then
    MISSING_TOOLS+=("terraform")
fi

if ! command -v aws &> /dev/null; then
    MISSING_TOOLS+=("aws")
fi

if ! command -v python3 &> /dev/null; then
    MISSING_TOOLS+=("python3")
fi

if ! command -v jq &> /dev/null; then
    MISSING_TOOLS+=("jq")
fi

if ! command -v git &> /dev/null; then
    MISSING_TOOLS+=("git")
fi

if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    log_error "Missing required tools:"
    for tool in "${MISSING_TOOLS[@]}"; do
        echo "  - $tool"
    done
    echo ""
    echo "Please install missing tools and try again."
    exit 1
fi

log_success "All required tools installed"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    log_error "AWS credentials not configured"
    echo "  Run: aws configure"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${CARL_REGION:-${AWS_REGION:-us-east-1}}
ENVIRONMENT=${CARL_ENVIRONMENT:-dev}

log_success "AWS Account: $AWS_ACCOUNT_ID"
log_success "AWS Region: $AWS_REGION"
log_success "Environment: $ENVIRONMENT"

# ============================================================================
# Step 2: Validate Required Credentials
# ============================================================================

log_step "Step 2: Validating Required Credentials"

# Check Slack credentials (REQUIRED)
if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_SIGNING_SECRET" ]; then
    log_error "Slack credentials are REQUIRED!"
    echo ""
    echo "CARL uses Slack as its primary interface."
    echo "Please set the following environment variables:"
    echo ""
    echo "  export SLACK_BOT_TOKEN=xoxb-..."
    echo "  export SLACK_SIGNING_SECRET=..."
    echo ""
    echo "Then run the installer again."
    exit 1
fi

log_success "Slack credentials provided"

# Check GitHub App credentials (REQUIRED for /carl build)
if [ -z "$GITHUB_APP_ID" ] || [ -z "$GITHUB_INSTALLATION_ID" ] || [ -z "$GITHUB_PRIVATE_KEY_PATH" ]; then
    log_error "GitHub App credentials are REQUIRED!"
    echo ""
    echo "CARL uses a GitHub App to create infrastructure deployment PRs."
    echo ""
    echo "Why GitHub App instead of Personal Access Token?"
    echo "  ✓ Tokens expire automatically (1 hour vs permanent)"
    echo "  ✓ Not tied to a user account"
    echo "  ✓ Fine-grained repository permissions"
    echo "  ✓ Better audit trail"
    echo ""
    echo "Please follow these steps:"
    echo ""
    echo "1. Run the GitHub App setup wizard:"
    echo "   ${CYAN}./scripts/setup-github-app.sh${NC}"
    echo ""
    echo "   This will guide you through:"
    echo "   - Creating a GitHub App in your org/account"
    echo "   - Generating and downloading a private key"
    echo "   - Installing the app on your repositories"
    echo ""
    echo "2. Set environment variables and re-run installer:"
    echo "   ${CYAN}export GITHUB_APP_ID=123456${NC}"
    echo "   ${CYAN}export GITHUB_INSTALLATION_ID=789012${NC}"
    echo "   ${CYAN}export GITHUB_PRIVATE_KEY_PATH=/path/to/app-private-key.pem${NC}"
    echo "   ${CYAN}export GITHUB_ORG=your-org${NC}"
    echo "   ${CYAN}export GITHUB_REPO=carl-infrastructure-deployments${NC}"
    echo ""
    echo "See GITHUB_APP_SETUP.md for detailed instructions."
    exit 1
fi

# Validate private key file exists
if [ ! -f "$GITHUB_PRIVATE_KEY_PATH" ]; then
    log_error "GitHub private key file not found: $GITHUB_PRIVATE_KEY_PATH"
    echo ""
    echo "Please check the path and ensure the .pem file exists."
    exit 1
fi

GITHUB_ORG=${GITHUB_ORG:-}
GITHUB_REPO=${GITHUB_REPO:-carl-infrastructure-deployments}

if [ -z "$GITHUB_ORG" ]; then
    log_error "GITHUB_ORG is required!"
    echo ""
    echo "  export GITHUB_ORG=your-github-org-or-username"
    exit 1
fi

log_success "GitHub App credentials provided"
log_success "  App ID: $GITHUB_APP_ID"
log_success "  Installation ID: $GITHUB_INSTALLATION_ID"
log_success "  Target: $GITHUB_ORG/$GITHUB_REPO"

# Check Jira credentials (OPTIONAL)
if [ -n "$JIRA_API_TOKEN" ] && [ -n "$JIRA_URL" ]; then
    INSTALL_JIRA=true
    JIRA_USER=${JIRA_USER:-}
    JIRA_PROJECT=${JIRA_PROJECT:-CARL}
    log_success "Jira credentials provided - will configure integration"
else
    INSTALL_JIRA=false
    log_warning "No Jira credentials - skipping Jira integration"
fi

# ============================================================================
# Step 3: Enable AWS Services
# ============================================================================

log_step "Step 3: Enabling Required AWS Services"

# Enable Security Hub
log_info "Enabling Security Hub..."
if aws securityhub describe-hub --region "$AWS_REGION" &>/dev/null; then
    log_success "Security Hub already enabled"
else
    aws securityhub enable-security-hub --region "$AWS_REGION" &>/dev/null || true
    # Enable AWS Foundational Security Best Practices
    aws securityhub batch-enable-standards \
        --standards-subscription-requests '[{"StandardsArn": "arn:aws:securityhub:'"$AWS_REGION"'::standards/aws-foundational-security-best-practices/v/1.0.0"}]' \
        --region "$AWS_REGION" &>/dev/null || true
    log_success "Security Hub enabled"
    save_state "security_hub_enabled" "true"
fi

# Enable GuardDuty
log_info "Enabling GuardDuty..."
DETECTOR_ID=$(aws guardduty list-detectors --region "$AWS_REGION" --query 'DetectorIds[0]' --output text 2>/dev/null)
if [ "$DETECTOR_ID" != "None" ] && [ -n "$DETECTOR_ID" ]; then
    log_success "GuardDuty already enabled"
else
    DETECTOR_ID=$(aws guardduty create-detector --enable --region "$AWS_REGION" --query 'DetectorId' --output text)
    log_success "GuardDuty enabled"
    save_state "guardduty_detector_id" "$DETECTOR_ID"
fi

# Enable AWS Config
log_info "Enabling AWS Config..."
if aws configservice describe-configuration-recorders --region "$AWS_REGION" 2>/dev/null | grep -q "ConfigurationRecorders"; then
    log_success "AWS Config already enabled"
else
    # Create S3 bucket for Config
    CONFIG_BUCKET="config-recordings-${AWS_ACCOUNT_ID}"
    aws s3 mb "s3://${CONFIG_BUCKET}" --region "$AWS_REGION" 2>/dev/null || true

    # Create IAM role for Config
    cat > /tmp/config-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "config.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

    aws iam create-role \
        --role-name AWSConfigRole \
        --assume-role-policy-document file:///tmp/config-trust-policy.json 2>/dev/null || true

    aws iam attach-role-policy \
        --role-name AWSConfigRole \
        --policy-arn arn:aws:iam::aws:policy/service-role/ConfigRole 2>/dev/null || true

    # Enable Config
    aws configservice put-configuration-recorder \
        --configuration-recorder name=default,roleARN=arn:aws:iam::${AWS_ACCOUNT_ID}:role/AWSConfigRole \
        --recording-group allSupported=true,includeGlobalResourceTypes=true \
        --region "$AWS_REGION" 2>/dev/null || true

    aws configservice put-delivery-channel \
        --delivery-channel name=default,s3BucketName=${CONFIG_BUCKET} \
        --region "$AWS_REGION" 2>/dev/null || true

    aws configservice start-configuration-recorder --configuration-recorder-name default --region "$AWS_REGION" 2>/dev/null || true

    log_success "AWS Config enabled"
fi

# Check Bedrock access
log_info "Checking AWS Bedrock access..."
CLAUDE_MODELS=$(aws bedrock list-foundation-models \
    --region "$AWS_REGION" \
    --query 'modelSummaries[?contains(modelId, `anthropic.claude-3-5-sonnet`)].modelId' \
    --output text 2>/dev/null)

if [ -z "$CLAUDE_MODELS" ]; then
    log_warning "Unable to verify Bedrock model access"
    echo ""
    echo "  CARL requires access to Claude models in AWS Bedrock."
    echo "  Please enable model access manually:"
    echo ""
    echo "  1. Go to: https://${AWS_REGION}.console.aws.amazon.com/bedrock/home?region=${AWS_REGION}#/modelaccess"
    echo "  2. Click 'Enable specific models'"
    echo "  3. Enable: Claude 3.5 Sonnet v2 and Claude 3 Haiku"
    echo "  4. Click 'Save changes'"
    echo ""
    read -p "  Press ENTER once you've enabled Bedrock model access..."
else
    log_success "Bedrock access verified"
fi

# ============================================================================
# Step 4: Create Terraform Backend
# ============================================================================

log_step "Step 4: Creating Terraform State Backend"

STATE_BUCKET="carl-terraform-state-${AWS_ACCOUNT_ID}"
LOCK_TABLE="carl-terraform-state-lock"

# Create S3 bucket
log_info "Creating S3 bucket for Terraform state..."
if aws s3 ls "s3://${STATE_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$STATE_BUCKET" --region "$AWS_REGION"
    else
        aws s3api create-bucket \
            --bucket "$STATE_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
    fi
    log_success "Created S3 bucket: $STATE_BUCKET"
    save_state "s3_state_bucket" "$STATE_BUCKET"
else
    log_success "S3 bucket already exists: $STATE_BUCKET"
fi

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket "$STATE_BUCKET" \
    --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
    --bucket "$STATE_BUCKET" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            },
            "BucketKeyEnabled": true
        }]
    }'

# Block public access
aws s3api put-public-access-block \
    --bucket "$STATE_BUCKET" \
    --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

log_success "S3 bucket configured with versioning and encryption"

# Create DynamoDB table
log_info "Creating DynamoDB table for state locking..."
if ! aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$AWS_REGION" &>/dev/null; then
    aws dynamodb create-table \
        --table-name "$LOCK_TABLE" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "$AWS_REGION" > /dev/null
    log_success "Created DynamoDB table: $LOCK_TABLE"
    save_state "dynamodb_lock_table" "$LOCK_TABLE"
else
    log_success "DynamoDB table already exists: $LOCK_TABLE"
fi

# ============================================================================
# Step 5: Update Configuration Files
# ============================================================================

log_step "Step 5: Updating Configuration Files"

# Update backend.tf
log_info "Updating backend configuration..."
cat > "$SCRIPT_DIR/carl-infrastructure/core/backend.tf" <<EOF
terraform {
  backend "s3" {
    bucket         = "${STATE_BUCKET}"
    key            = "core/terraform.tfstate"
    region         = "${AWS_REGION}"
    dynamodb_table = "${LOCK_TABLE}"
    encrypt        = true
  }
}
EOF
log_success "Updated backend.tf"

# Update variables.tf defaults if needed
log_info "Updating variables..."
sed -i.bak "s/default = \"us-east-1\"/default = \"${AWS_REGION}\"/" "$SCRIPT_DIR/carl-infrastructure/core/variables.tf" 2>/dev/null || true
sed -i.bak "s/Environment = \"dev\"/Environment = \"${ENVIRONMENT}\"/" "$SCRIPT_DIR/carl-infrastructure/core/variables.tf" 2>/dev/null || true
log_success "Updated variables.tf"

# Update GitHub workflow files with account ID
log_info "Updating GitHub workflows..."
find "$SCRIPT_DIR/.github/workflows" -name "*.yml" -type f -exec \
    sed -i.bak "s/123456789012/${AWS_ACCOUNT_ID}/g" {} \; 2>/dev/null || true
log_success "Updated workflow files"

# Generate terraform.tfvars
log_info "Generating terraform.tfvars..."
cat > "$SCRIPT_DIR/carl-infrastructure/core/terraform.tfvars" <<EOF
# CARL Configuration
# Generated: $(date)

aws_region  = "${AWS_REGION}"
environment = "${ENVIRONMENT}"

tags = {
  Project     = "CARL"
  ManagedBy   = "Terraform"
  Environment = "${ENVIRONMENT}"
  Owner       = "$(aws sts get-caller-identity --query Arn --output text)"
}
EOF
log_success "Created terraform.tfvars"

# ============================================================================
# Step 6: Store Secrets in AWS Secrets Manager
# ============================================================================

log_step "Step 6: Storing Integration Credentials"

# Store Slack credentials
log_info "Storing Slack credentials..."
SLACK_SECRET_NAME="carl/slack/credentials"
if aws secretsmanager describe-secret --secret-id "$SLACK_SECRET_NAME" --region "$AWS_REGION" &>/dev/null; then
    aws secretsmanager update-secret \
        --secret-id "$SLACK_SECRET_NAME" \
        --secret-string "{\"bot_token\": \"${SLACK_BOT_TOKEN}\", \"signing_secret\": \"${SLACK_SIGNING_SECRET}\"}" \
        --region "$AWS_REGION" > /dev/null
    log_success "Updated Slack credentials"
else
    SLACK_SECRET_ARN=$(aws secretsmanager create-secret \
        --name "$SLACK_SECRET_NAME" \
        --description "CARL Slack integration credentials" \
        --secret-string "{\"bot_token\": \"${SLACK_BOT_TOKEN}\", \"signing_secret\": \"${SLACK_SIGNING_SECRET}\"}" \
        --region "$AWS_REGION" \
        --query 'ARN' \
        --output text)
    log_success "Created Slack credentials secret"
    save_state "slack_secret_arn" "$SLACK_SECRET_ARN"
fi

# Store Jira credentials (if provided)
if [ "$INSTALL_JIRA" = true ]; then
    log_info "Storing Jira credentials..."
    JIRA_SECRET_NAME="carl/jira/credentials"
    if aws secretsmanager describe-secret --secret-id "$JIRA_SECRET_NAME" --region "$AWS_REGION" &>/dev/null; then
        aws secretsmanager update-secret \
            --secret-id "$JIRA_SECRET_NAME" \
            --secret-string "{\"url\": \"${JIRA_URL}\", \"user\": \"${JIRA_USER}\", \"api_token\": \"${JIRA_API_TOKEN}\", \"project\": \"${JIRA_PROJECT}\"}" \
            --region "$AWS_REGION" > /dev/null
        log_success "Updated Jira credentials"
    else
        JIRA_SECRET_ARN=$(aws secretsmanager create-secret \
            --name "$JIRA_SECRET_NAME" \
            --description "CARL Jira integration credentials" \
            --secret-string "{\"url\": \"${JIRA_URL}\", \"user\": \"${JIRA_USER}\", \"api_token\": \"${JIRA_API_TOKEN}\", \"project\": \"${JIRA_PROJECT}\"}" \
            --region "$AWS_REGION" \
            --query 'ARN' \
            --output text)
        log_success "Created Jira credentials secret"
        save_state "jira_secret_arn" "$JIRA_SECRET_ARN"
    fi
fi

# Store GitHub App credentials
log_info "Storing GitHub App credentials..."
GITHUB_SECRET_NAME="carl/github/app-credentials"
GITHUB_PRIVATE_KEY=$(cat "$GITHUB_PRIVATE_KEY_PATH")

GITHUB_CREDENTIALS=$(jq -n \
    --arg app_id "$GITHUB_APP_ID" \
    --arg installation_id "$GITHUB_INSTALLATION_ID" \
    --arg private_key "$GITHUB_PRIVATE_KEY" \
    --arg org "$GITHUB_ORG" \
    --arg repo "$GITHUB_REPO" \
    '{
        app_id: $app_id,
        installation_id: $installation_id,
        private_key: $private_key,
        org: $org,
        repo: $repo
    }')

if aws secretsmanager describe-secret --secret-id "$GITHUB_SECRET_NAME" --region "$AWS_REGION" &>/dev/null; then
    aws secretsmanager update-secret \
        --secret-id "$GITHUB_SECRET_NAME" \
        --secret-string "$GITHUB_CREDENTIALS" \
        --region "$AWS_REGION" > /dev/null
    log_success "Updated GitHub App credentials"
else
    GITHUB_SECRET_ARN=$(aws secretsmanager create-secret \
        --name "$GITHUB_SECRET_NAME" \
        --description "CARL GitHub App credentials for infrastructure deployments" \
        --secret-string "$GITHUB_CREDENTIALS" \
        --region "$AWS_REGION" \
        --query 'ARN' \
        --output text)
    log_success "Created GitHub App credentials secret"
    save_state "github_secret_arn" "$GITHUB_SECRET_ARN"
fi

# ============================================================================
# Step 7: Deploy Core Infrastructure
# ============================================================================

log_step "Step 7: Deploying Core Infrastructure"

cd "$SCRIPT_DIR/carl-infrastructure/core"

log_info "Initializing Terraform..."
terraform init -upgrade

log_info "Generating Terraform plan..."
terraform plan -out=tfplan

echo ""
log_warning "Review the plan above. This will create AWS resources."
read -p "Proceed with deployment? [y/N]: " PROCEED

if [[ ! $PROCEED =~ ^[Yy]$ ]]; then
    log_error "Deployment cancelled by user"
    exit 1
fi

log_info "Applying Terraform configuration... (this may take 5-10 minutes)"
terraform apply tfplan

log_success "Core infrastructure deployed!"
save_state "terraform_deployed" "true"

# Capture outputs
API_GATEWAY_URL=$(terraform output -raw api_gateway_url 2>/dev/null || echo "N/A")
LAMBDA_FUNCTION=$(terraform output -raw slack_router_function_arn 2>/dev/null || echo "N/A")
KMS_KEY_ID=$(terraform output -raw kms_key_id 2>/dev/null || echo "")

if [ -n "$KMS_KEY_ID" ]; then
    save_state "kms_key_id" "$KMS_KEY_ID"
fi

cd "$SCRIPT_DIR"

# ============================================================================
# Step 8: Post-Deployment Configuration
# ============================================================================

log_step "Step 8: Post-Deployment Configuration"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}║                  CARL Deployed Successfully! 🎉                  ║${NC}"
echo -e "${GREEN}║                                                                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}Deployment Summary:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AWS Account:      $AWS_ACCOUNT_ID"
echo "  Region:           $AWS_REGION"
echo "  Environment:      $ENVIRONMENT"
echo "  API Gateway URL:  $API_GATEWAY_URL"
echo "  Lambda Function:  $LAMBDA_FUNCTION"
echo ""
echo "  Integrations:"
echo "    ✅ Slack:        Configured"
echo "    ✅ GitHub:       Configured (App ID: $GITHUB_APP_ID)"
echo "    ✅ GitHub Repo:  $GITHUB_ORG/$GITHUB_REPO"
if [ "$INSTALL_JIRA" = true ]; then
    echo "    ✅ Jira:         Configured ($JIRA_URL)"
else
    echo "    ⏭  Jira:         Not configured"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# Step 9: Next Steps
# ============================================================================

log_step "Next Steps"

echo -e "${YELLOW}1. Configure Slack App${NC}"
echo ""
echo "   Update your Slack app with the API Gateway URL:"
echo ""
echo "   a. Go to: https://api.slack.com/apps"
echo "   b. Select your CARL app"
echo "   c. Update these sections with: ${CYAN}${API_GATEWAY_URL}/slack/events${NC}"
echo "      - Slash Commands → /carl → Request URL"
echo "      - Event Subscriptions → Request URL"
echo "      - Interactivity & Shortcuts → Request URL"
echo ""

echo -e "${YELLOW}2. Test CARL in Slack${NC}"
echo ""
echo "   Run these commands in your Slack workspace:"
echo ""
echo "   ${CYAN}/carl help${NC}               - View available commands"
echo "   ${CYAN}/carl ask <question>${NC}     - Ask architecture questions"
echo "   ${CYAN}/carl scan${NC}               - Run compliance scan"
echo "   ${CYAN}/carl build <pattern>${NC}    - Generate infrastructure code"
echo ""

echo -e "${YELLOW}3. Validate Deployment${NC}"
echo ""
echo "   Run the validation script:"
echo "   ${CYAN}./validate-deployment.sh${NC}"
echo ""

echo -e "${YELLOW}4. View Logs${NC}"
echo ""
echo "   Monitor Lambda logs:"
echo "   ${CYAN}aws logs tail /aws/lambda/carl-slack-router-${ENVIRONMENT} --follow${NC}"
echo ""

if [ "$INSTALL_JIRA" = false ]; then
    echo -e "${YELLOW}5. Optional: Add Jira Integration Later${NC}"
    echo ""
    echo "   To add Jira integration later:"
    echo ""
    echo "   export JIRA_URL=https://your-domain.atlassian.net"
    echo "   export JIRA_API_TOKEN=your-token"
    echo "   export JIRA_USER=your-email@example.com"
    echo "   export JIRA_PROJECT=CARL"
    echo ""
    echo "   Then run:"
    echo "   ${CYAN}./configure-jira.sh${NC}"
    echo ""
fi

echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Estimated monthly cost: \$75-200"
echo ""
echo "Security benefits of GitHub App:"
echo "  ✓ Tokens expire automatically after 1 hour"
echo "  ✓ Not tied to any user account"
echo "  ✓ Fine-grained repository permissions"
echo "  ✓ Better audit trail in GitHub"
echo ""
echo "To rollback this installation:"
echo "  ${CYAN}./install-carl.sh --rollback${NC}"
echo ""
