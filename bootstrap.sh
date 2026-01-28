#!/bin/bash
set -e

# CARL Bootstrap Script
# Sets up OIDC authentication and Terraform backend for CARL deployment

echo "🚀 CARL Bootstrap - Setting up OIDC and Terraform Backend"
echo ""

# ============================================================================
# Configuration
# ============================================================================

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}

# Get GitHub info
GITHUB_ORG=${GITHUB_ORG:-gnegelow-caylent}
GITHUB_REPO=${GITHUB_REPO:-CARL}

echo "Configuration:"
echo "  AWS Account: $AWS_ACCOUNT_ID"
echo "  AWS Region: $AWS_REGION"
echo "  GitHub Repo: $GITHUB_ORG/$GITHUB_REPO"
echo ""

read -p "Is this correct? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted. Set AWS_REGION, GITHUB_ORG, GITHUB_REPO environment variables and try again."
    exit 1
fi

# ============================================================================
# Step 1: Create S3 Bucket for Terraform State
# ============================================================================

echo ""
echo "📦 Step 1: Creating S3 bucket for Terraform state..."

STATE_BUCKET="carl-tfstate-${AWS_ACCOUNT_ID}"

# Check if bucket exists
if aws s3 ls "s3://${STATE_BUCKET}" 2>/dev/null; then
    echo "  ✓ Bucket already exists: ${STATE_BUCKET}"
else
    # Create bucket
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "${STATE_BUCKET}" --region "${AWS_REGION}"
    else
        aws s3api create-bucket \
            --bucket "${STATE_BUCKET}" \
            --region "${AWS_REGION}" \
            --create-bucket-configuration LocationConstraint="${AWS_REGION}"
    fi
    echo "  ✓ Created bucket: ${STATE_BUCKET}"
fi

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket "${STATE_BUCKET}" \
    --versioning-configuration Status=Enabled
echo "  ✓ Enabled versioning"

# Enable encryption
aws s3api put-bucket-encryption \
    --bucket "${STATE_BUCKET}" \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            },
            "BucketKeyEnabled": true
        }]
    }'
echo "  ✓ Enabled encryption"

# Block public access
aws s3api put-public-access-block \
    --bucket "${STATE_BUCKET}" \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
echo "  ✓ Blocked public access"

# Add lifecycle policy to clean up old versions
aws s3api put-bucket-lifecycle-configuration \
    --bucket "${STATE_BUCKET}" \
    --lifecycle-configuration '{
        "Rules": [{
            "Id": "DeleteOldVersions",
            "Status": "Enabled",
            "NoncurrentVersionExpiration": {
                "NoncurrentDays": 90
            }
        }]
    }'
echo "  ✓ Added lifecycle policy (delete old versions after 90 days)"

# ============================================================================
# Step 2: Deploy OIDC Infrastructure
# ============================================================================

echo ""
echo "🔐 Step 2: Deploying OIDC authentication..."

cd carl-infrastructure/oidc

# Create backend config
cat > backend.tf <<EOF
terraform {
  backend "s3" {
    bucket = "${STATE_BUCKET}"
    key    = "carl-oidc/terraform.tfstate"
    region = "${AWS_REGION}"
  }
}
EOF

echo "  ✓ Created backend configuration"

# Initialize Terraform
terraform init -upgrade

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
region         = "${AWS_REGION}"
github_org     = "${GITHUB_ORG}"
github_repo    = "${GITHUB_REPO}"
terraform_state_bucket     = "${STATE_BUCKET}"
terraform_state_lock_table = "carl-tfstate-locks"
EOF

echo "  ✓ Created terraform.tfvars"

# Apply OIDC infrastructure
echo ""
echo "  Deploying OIDC provider and IAM roles..."
terraform apply -auto-approve

# Get outputs
echo ""
echo "  ✓ OIDC infrastructure deployed!"

ROLE_ARN_DEV=$(terraform output -raw deployer_role_arn_dev)
ROLE_ARN_QA=$(terraform output -raw deployer_role_arn_qa)
ROLE_ARN_PROD=$(terraform output -raw deployer_role_arn_prod)

cd ../..

# ============================================================================
# Step 3: Configure Core Backend
# ============================================================================

echo ""
echo "⚙️  Step 3: Configuring CARL core backend..."

cd carl-infrastructure/core

# Create backend config
cat > backend.tf <<EOF
terraform {
  backend "s3" {
    bucket = "${STATE_BUCKET}"
    key    = "carl-core/terraform.tfstate"
    region = "${AWS_REGION}"
  }
}
EOF

echo "  ✓ Created backend configuration for core"

cd ../..

# ============================================================================
# Step 4: Output GitHub Secrets
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Bootstrap Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Next Step: Add these secrets to GitHub"
echo ""
echo "Go to: https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/settings/secrets/actions"
echo ""
echo "Click 'New repository secret' and add these 4 secrets:"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Name:  AWS_ROLE_ARN_DEV"
echo "Value: ${ROLE_ARN_DEV}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Name:  AWS_ROLE_ARN_QA"
echo "Value: ${ROLE_ARN_QA}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Name:  AWS_ROLE_ARN_PROD"
echo "Value: ${ROLE_ARN_PROD}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Name:  AWS_REGION"
echo "Value: ${AWS_REGION}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "After adding secrets, deploy CARL:"
echo ""
echo "  git checkout -b develop"
echo "  git push origin develop"
echo ""
echo "Or use GitHub UI: Actions → Deploy CARL Core → Run workflow"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 Documentation:"
echo "  - OIDC_SETUP.md - OIDC authentication details"
echo "  - DEPLOYMENT.md - Full deployment guide"
echo "  - COST_OPTIMIZATION.md - Cost saving strategies"
echo ""
echo "💡 Tip: OIDC uses temporary credentials (no access keys needed!)"
echo ""
