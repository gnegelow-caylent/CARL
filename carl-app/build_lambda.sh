#!/bin/bash
# Build Lambda deployment package using Docker to match Lambda runtime

set -e

echo "🐳 Building Lambda package in Docker (Amazon Linux 2)..."

# Clean previous build
rm -rf build lambda.zip

# Create build directory
mkdir -p build

# Copy source code
cp -r src build/

# Build dependencies in Docker container matching Lambda runtime
docker run --rm \
  -v "$(pwd)":/var/task \
  -w /var/task \
  public.ecr.aws/lambda/python:3.12 \
  bash -c "
    pip install -r requirements.txt -t build/ --upgrade &&
    cd build &&
    zip -r ../lambda.zip . -q
  "

echo "✅ Lambda package built: lambda.zip ($(du -h lambda.zip | cut -f1))"
echo ""
echo "To deploy:"
echo "  cp lambda.zip ../carl-infrastructure/core/"
echo "  cd ../carl-infrastructure/core"
echo "  terraform apply -var='environment=dev'"
