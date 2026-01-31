#!/bin/bash
#
# Build and Push CARL Lambda Container Image to ECR
#
# This script builds a Docker image with PDF generation dependencies
# and pushes it to Amazon ECR for Lambda container deployment.
#
# Requirements:
# - Docker installed and running
# - AWS CLI configured with credentials
#
# Cost: ~$0.03/month (ECR storage) + ~$0.001 per report execution
#

set -e  # Exit on error

echo "🐳 Building CARL Lambda Container Image..."
echo ""

# Configuration
AWS_REGION=$(aws configure get region || echo "us-east-1")
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPOSITORY="carl-lambda"
IMAGE_TAG="latest"
IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}"

echo "📋 Configuration:"
echo "   AWS Account: $AWS_ACCOUNT_ID"
echo "   AWS Region: $AWS_REGION"
echo "   ECR Repository: $ECR_REPOSITORY"
echo "   Image Tag: $IMAGE_TAG"
echo ""

# Create ECR repository if it doesn't exist
echo "📦 Creating ECR repository (if needed)..."
aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" 2>/dev/null || \
    aws ecr create-repository \
        --repository-name "$ECR_REPOSITORY" \
        --region "$AWS_REGION" \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256 \
        > /dev/null

echo "✅ ECR repository ready"
echo ""

# Login to ECR
echo "🔐 Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "✅ Logged in to ECR"
echo ""

# Build Docker image
echo "🏗️  Building Docker image..."
echo "   (This may take 3-5 minutes for first build)"
echo ""

cd carl-app
docker build --platform linux/amd64 -t "$ECR_REPOSITORY:$IMAGE_TAG" .
cd ..

echo ""
echo "✅ Docker image built successfully"
echo ""

# Tag image for ECR
echo "🏷️  Tagging image..."
docker tag "$ECR_REPOSITORY:$IMAGE_TAG" "$IMAGE_URI"

# Get image size
IMAGE_SIZE=$(docker images "$ECR_REPOSITORY:$IMAGE_TAG" --format "{{.Size}}")
echo "   Image size: $IMAGE_SIZE"
echo ""

# Push to ECR
echo "⬆️  Pushing to ECR..."
echo "   URI: $IMAGE_URI"
echo ""

docker push "$IMAGE_URI"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Container Image Published Successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Image URI: $IMAGE_URI"
echo ""
echo "Next steps:"
echo "1. Update Terraform to use container image:"
echo "   image_uri = \"$IMAGE_URI\""
echo ""
echo "2. Uncomment PDF dependencies in carl-app/requirements.txt"
echo ""
echo "3. Deploy: cd carl-infrastructure/environments/dev && terraform apply"
echo ""
echo "4. Test: /carl report executive"
echo ""
echo "Cost: ~\$0.03/month (ECR storage) + ~\$0.001 per report"
echo ""

# Save image URI for Terraform
mkdir -p layer-output
echo "$IMAGE_URI" > layer-output/image-uri.txt
echo "Image URI saved to: layer-output/image-uri.txt"
echo ""
