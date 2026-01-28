#!/bin/bash
# Setup script for configuring GitHub App authentication for CARL
# This creates short-lived tokens instead of permanent PATs

set -e

echo "================================================"
echo "CARL GitHub App Setup"
echo "================================================"
echo ""
echo "This script will help you configure GitHub App authentication"
echo "for CARL to create infrastructure deployment PRs."
echo ""
echo "Benefits of GitHub App vs Personal Access Token:"
echo "  ✓ Tokens expire automatically (1 hour)"
echo "  ✓ Not tied to a user account"
echo "  ✓ Fine-grained repository permissions"
echo "  ✓ Better audit trail"
echo ""

# Check prerequisites
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "❌ jq not found. Please install it first (brew install jq)"
    exit 1
fi

# Get environment
read -p "Environment (dev/qa/prod) [dev]: " ENVIRONMENT
ENVIRONMENT=${ENVIRONMENT:-dev}

# Get AWS region
read -p "AWS Region [us-east-1]: " AWS_REGION
AWS_REGION=${AWS_REGION:-us-east-1}

echo ""
echo "================================================"
echo "Step 1: Create GitHub App"
echo "================================================"
echo ""
echo "1. Go to: https://github.com/organizations/YOUR_ORG/settings/apps/new"
echo "   (or for personal account: https://github.com/settings/apps/new)"
echo ""
echo "2. Fill in the form:"
echo "   - Name: CARL Infrastructure Bot"
echo "   - Homepage URL: https://github.com/YOUR_ORG/carl_infra"
echo "   - Webhook: Uncheck 'Active'"
echo ""
echo "3. Repository permissions:"
echo "   - Contents: Read and write"
echo "   - Pull requests: Read and write"
echo "   - Metadata: Read-only (auto-selected)"
echo ""
echo "4. Click 'Create GitHub App'"
echo ""
echo "5. After creation:"
echo "   - Note the 'App ID' (shown at top)"
echo "   - Scroll down to 'Private keys'"
echo "   - Click 'Generate a private key'"
echo "   - Save the downloaded .pem file"
echo ""
echo "6. Install the app:"
echo "   - Click 'Install App' in left sidebar"
echo "   - Select your organization"
echo "   - Choose 'Only select repositories'"
echo "   - Select 'carl_infra' repository"
echo "   - Click 'Install'"
echo "   - Note the installation ID from the URL (last number in the path)"
echo "     Example: github.com/settings/installations/12345678"
echo "              Installation ID = 12345678"
echo ""
read -p "Press ENTER when you've completed the GitHub App setup..."

echo ""
echo "================================================"
echo "Step 2: Enter GitHub App Details"
echo "================================================"
echo ""

# Get App ID
read -p "Enter GitHub App ID: " APP_ID
if [ -z "$APP_ID" ]; then
    echo "❌ App ID is required"
    exit 1
fi

# Get Installation ID
read -p "Enter Installation ID: " INSTALLATION_ID
if [ -z "$INSTALLATION_ID" ]; then
    echo "❌ Installation ID is required"
    exit 1
fi

# Get private key file
read -p "Enter path to private key file (.pem): " PRIVATE_KEY_PATH
if [ ! -f "$PRIVATE_KEY_PATH" ]; then
    echo "❌ Private key file not found: $PRIVATE_KEY_PATH"
    exit 1
fi

echo ""
echo "Reading private key..."
PRIVATE_KEY=$(cat "$PRIVATE_KEY_PATH")

echo ""
echo "================================================"
echo "Step 3: Store Credentials in AWS Secrets Manager"
echo "================================================"
echo ""

SECRET_NAME="/carl/$ENVIRONMENT/github-app-credentials"

# Create JSON payload
CREDENTIALS_JSON=$(jq -n \
  --arg app_id "$APP_ID" \
  --arg private_key "$PRIVATE_KEY" \
  --arg installation_id "$INSTALLATION_ID" \
  '{
    app_id: $app_id,
    private_key: $private_key,
    installation_id: $installation_id
  }')

# Check if secret already exists
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$AWS_REGION" &> /dev/null; then
    echo "Secret already exists. Updating..."
    aws secretsmanager update-secret \
      --secret-id "$SECRET_NAME" \
      --secret-string "$CREDENTIALS_JSON" \
      --region "$AWS_REGION"
    echo "✅ Secret updated: $SECRET_NAME"
else
    echo "Creating new secret..."
    aws secretsmanager create-secret \
      --name "$SECRET_NAME" \
      --description "GitHub App credentials for CARL infrastructure deployments" \
      --secret-string "$CREDENTIALS_JSON" \
      --region "$AWS_REGION"
    echo "✅ Secret created: $SECRET_NAME"
fi

echo ""
echo "================================================"
echo "Step 4: Update Lambda Configuration"
echo "================================================"
echo ""

# Get Lambda function name
LAMBDA_NAME="carl-$ENVIRONMENT-api"

echo "Updating Lambda environment variables..."
aws lambda update-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --region "$AWS_REGION" \
  --environment "Variables={
    GITHUB_APP_CREDENTIALS_SECRET=$SECRET_NAME,
    GITHUB_INFRA_OWNER=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.GITHUB_INFRA_OWNER' --output text 2>/dev/null || echo 'your-org'),
    GITHUB_INFRA_REPO=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.GITHUB_INFRA_REPO' --output text 2>/dev/null || echo 'carl_infra'),
    ENVIRONMENT=$ENVIRONMENT,
    CONFIG_TABLE=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.CONFIG_TABLE' --output text 2>/dev/null),
    EVIDENCE_TABLE=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.EVIDENCE_TABLE' --output text 2>/dev/null),
    FINDINGS_TABLE=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.FINDINGS_TABLE' --output text 2>/dev/null),
    EXCEPTIONS_TABLE=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.EXCEPTIONS_TABLE' --output text 2>/dev/null),
    EVIDENCE_BUCKET=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.EVIDENCE_BUCKET' --output text 2>/dev/null),
    REPORTS_BUCKET=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.REPORTS_BUCKET' --output text 2>/dev/null),
    BEDROCK_MODEL_ID=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.BEDROCK_MODEL_ID' --output text 2>/dev/null),
    BEDROCK_REGION=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.BEDROCK_REGION' --output text 2>/dev/null),
    SLACK_BOT_TOKEN_SSM=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.SLACK_BOT_TOKEN_SSM' --output text 2>/dev/null),
    SLACK_SIGNING_SECRET_SSM=$(aws lambda get-function-configuration --function-name $LAMBDA_NAME --region $AWS_REGION --query 'Environment.Variables.SLACK_SIGNING_SECRET_SSM' --output text 2>/dev/null)
  }" \
  --output text > /dev/null 2>&1

echo "✅ Lambda configuration updated"

echo ""
echo "================================================"
echo "✅ Setup Complete!"
echo "================================================"
echo ""
echo "GitHub App Configuration:"
echo "  App ID: $APP_ID"
echo "  Installation ID: $INSTALLATION_ID"
echo "  Secret: $SECRET_NAME"
echo ""
echo "Next Steps:"
echo "  1. Deploy updated Lambda code with GitHub App support"
echo "  2. Test with: /carl build networking/basic-vpc"
echo "  3. Verify PR is created in carl_infra repository"
echo ""
echo "Security Notes:"
echo "  ✓ Tokens expire automatically after 1 hour"
echo "  ✓ Tokens regenerate on-demand"
echo "  ✓ Private key securely stored in Secrets Manager"
echo "  ✓ No permanent credentials in use"
echo ""
echo "To rotate credentials:"
echo "  1. Generate new private key in GitHub App settings"
echo "  2. Re-run this script with new key"
echo ""
