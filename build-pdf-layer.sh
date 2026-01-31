#!/bin/bash
#
# Build Lambda Layer for PDF Generation (WeasyPrint + dependencies)
# This script creates a Lambda Layer with system libraries and Python packages
# for professional PDF report generation in CARL.
#
# Requirements:
# - Docker installed and running
# - AWS CLI configured with credentials
# - Sufficient disk space (~500MB for build artifacts)
#
# Cost: FREE (Lambda Layers have no storage charges)
# Execution cost: ~$0.001 per report generated (~$0.05-$0.10/month total)
#

set -e  # Exit on error

echo "🏗️  Building Lambda Layer for PDF Generation..."
echo ""

# Configuration
LAYER_NAME="carl-pdf-dependencies"
PYTHON_VERSION="3.12"
BUILD_DIR="$(pwd)/layer-build"
OUTPUT_DIR="$(pwd)/layer-output"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf "$BUILD_DIR" "$OUTPUT_DIR"
mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

echo ""
echo "🐳 Building layer in Amazon Linux 2 container..."
echo "   (This ensures compatibility with Lambda runtime)"
echo ""

# Build layer using Docker (Amazon Linux 2 matches Lambda runtime)
docker run --rm \
    -v "$BUILD_DIR":/output \
    -v "$(pwd)/carl-app":/app \
    public.ecr.aws/lambda/python:${PYTHON_VERSION} \
    bash -c '
        set -e
        echo "📦 Installing system dependencies..."

        # Install system libraries required by WeasyPrint
        yum install -y \
            cairo \
            cairo-devel \
            pango \
            pango-devel \
            gdk-pixbuf2 \
            gdk-pixbuf2-devel \
            libffi \
            libffi-devel \
            libjpeg-turbo \
            libjpeg-turbo-devel \
            zlib \
            zlib-devel

        echo ""
        echo "🐍 Installing Python packages..."

        # Create python directory for layer structure
        mkdir -p /output/python

        # Install Python packages
        pip3 install \
            weasyprint==60.2 \
            matplotlib==3.8.2 \
            pillow==10.2.0 \
            cairocffi==1.6.1 \
            cffi==1.16.0 \
            -t /output/python \
            --no-cache-dir

        echo ""
        echo "📚 Copying system libraries..."

        # Copy required system libraries
        mkdir -p /output/lib

        # Copy Cairo and dependencies
        cp -P /usr/lib64/libcairo*.so* /output/lib/ || true
        cp -P /usr/lib64/libpango*.so* /output/lib/ || true
        cp -P /usr/lib64/libgdk*.so* /output/lib/ || true
        cp -P /usr/lib64/libffi*.so* /output/lib/ || true
        cp -P /usr/lib64/libpixman*.so* /output/lib/ || true
        cp -P /usr/lib64/libfontconfig*.so* /output/lib/ || true
        cp -P /usr/lib64/libfreetype*.so* /output/lib/ || true
        cp -P /usr/lib64/libpng*.so* /output/lib/ || true
        cp -P /usr/lib64/libjpeg*.so* /output/lib/ || true
        cp -P /usr/lib64/libharfbuzz*.so* /output/lib/ || true
        cp -P /usr/lib64/libthai*.so* /output/lib/ || true
        cp -P /usr/lib64/libdatrie*.so* /output/lib/ || true
        cp -P /usr/lib64/libgobject*.so* /output/lib/ || true
        cp -P /usr/lib64/libglib*.so* /output/lib/ || true
        cp -P /usr/lib64/libgraphite*.so* /output/lib/ || true

        # Remove unnecessary files to reduce size
        find /output/python -name "*.pyc" -delete
        find /output/python -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find /output/python -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
        find /output/python -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true

        echo ""
        echo "✅ Layer build complete!"
        echo ""
        du -sh /output/python
        du -sh /output/lib
    '

echo ""
echo "📦 Creating layer archive..."

# Create zip file
cd "$BUILD_DIR"
zip -r -q "$OUTPUT_DIR/${LAYER_NAME}.zip" python lib

cd - > /dev/null

LAYER_SIZE=$(du -h "$OUTPUT_DIR/${LAYER_NAME}.zip" | cut -f1)
echo "✅ Layer archive created: ${LAYER_SIZE}"
echo "   Location: $OUTPUT_DIR/${LAYER_NAME}.zip"

echo ""
echo "☁️  Uploading to AWS Lambda..."

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

echo "   Account: $AWS_ACCOUNT_ID"
echo "   Region: $AWS_REGION"

# Upload layer to S3 first (required for layers >50MB)
S3_BUCKET="carl-lambda-layers-${AWS_ACCOUNT_ID}"
S3_KEY="${LAYER_NAME}/${LAYER_NAME}-$(date +%Y%m%d-%H%M%S).zip"

echo ""
echo "📤 Uploading to S3..."

# Create bucket if it doesn't exist
aws s3 mb s3://${S3_BUCKET} 2>/dev/null || true

aws s3 cp "$OUTPUT_DIR/${LAYER_NAME}.zip" "s3://${S3_BUCKET}/${S3_KEY}"

echo "✅ Uploaded to s3://${S3_BUCKET}/${S3_KEY}"

echo ""
echo "🔧 Publishing Lambda Layer..."

# Publish layer version
LAYER_VERSION_ARN=$(aws lambda publish-layer-version \
    --layer-name "$LAYER_NAME" \
    --description "PDF generation dependencies (WeasyPrint, Matplotlib, Cairo, Pango)" \
    --content "S3Bucket=${S3_BUCKET},S3Key=${S3_KEY}" \
    --compatible-runtimes "python${PYTHON_VERSION}" \
    --query 'LayerVersionArn' \
    --output text)

echo "✅ Layer published!"
echo ""
echo "   Layer ARN: $LAYER_VERSION_ARN"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Lambda Layer Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "1. Update Terraform to use this layer:"
echo "   Layer ARN: $LAYER_VERSION_ARN"
echo ""
echo "2. Uncomment PDF dependencies in carl-app/requirements.txt"
echo ""
echo "3. Deploy with: cd carl-infrastructure/environments/dev && terraform apply"
echo ""
echo "4. Test with: /carl report executive"
echo ""
echo "Cost: ~\$0.001 per report (~\$0.05-$0.10/month total)"
echo ""

# Save layer ARN to file for Terraform
echo "$LAYER_VERSION_ARN" > "$OUTPUT_DIR/layer-arn.txt"
echo "Layer ARN saved to: $OUTPUT_DIR/layer-arn.txt"
echo ""
