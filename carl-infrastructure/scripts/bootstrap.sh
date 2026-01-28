#!/bin/bash
# Bootstrap Terraform state backend

set -e

AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="carl-terraform-state-${ACCOUNT_ID}"
TABLE_NAME="carl-terraform-locks"

echo "Bootstrapping Terraform backend..."
echo "Account: $ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Bucket: $BUCKET_NAME"
echo "Table: $TABLE_NAME"

# Create S3 bucket
echo "Creating S3 bucket..."
if aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
    echo "Bucket already exists"
else
    aws s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$AWS_REGION" \
        $(if [ "$AWS_REGION" != "us-east-1" ]; then echo "--create-bucket-configuration LocationConstraint=$AWS_REGION"; fi)

    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "$BUCKET_NAME" \
        --versioning-configuration Status=Enabled

    # Enable encryption
    aws s3api put-bucket-encryption \
        --bucket "$BUCKET_NAME" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "aws:kms"
                },
                "BucketKeyEnabled": true
            }]
        }'

    # Block public access
    aws s3api put-public-access-block \
        --bucket "$BUCKET_NAME" \
        --public-access-block-configuration '{
            "BlockPublicAcls": true,
            "IgnorePublicAcls": true,
            "BlockPublicPolicy": true,
            "RestrictPublicBuckets": true
        }'

    echo "S3 bucket created"
fi

# Create DynamoDB table
echo "Creating DynamoDB table..."
if aws dynamodb describe-table --table-name "$TABLE_NAME" 2>/dev/null; then
    echo "Table already exists"
else
    aws dynamodb create-table \
        --table-name "$TABLE_NAME" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "$AWS_REGION"

    # Wait for table to be created
    aws dynamodb wait table-exists --table-name "$TABLE_NAME"

    echo "DynamoDB table created"
fi

echo ""
echo "Bootstrap complete!"
echo ""
echo "Update your Terraform backend configuration:"
echo ""
echo "terraform {"
echo "  backend \"s3\" {"
echo "    bucket         = \"$BUCKET_NAME\""
echo "    key            = \"<environment>/terraform.tfstate\""
echo "    region         = \"$AWS_REGION\""
echo "    dynamodb_table = \"$TABLE_NAME\""
echo "    encrypt        = true"
echo "  }"
echo "}"
