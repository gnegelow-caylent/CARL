#!/bin/bash
# Deploy Lambda functions to AWS

set -e

ENVIRONMENT="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"

echo "Deploying CARL to $ENVIRONMENT environment..."

# Validate environment
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

# Check if packages exist
if [[ ! -d "$DIST_DIR" ]]; then
    echo "Error: No packages found. Run build.sh first."
    exit 1
fi

# Function names
SLACK_ROUTER="carl-slack-router-$ENVIRONMENT"
FINDINGS_PROCESSOR="carl-findings-processor-$ENVIRONMENT"

# Deploy Slack Router
if [[ -f "$DIST_DIR/slack_router.zip" ]]; then
    echo "Deploying $SLACK_ROUTER..."
    aws lambda update-function-code \
        --function-name "$SLACK_ROUTER" \
        --zip-file "fileb://$DIST_DIR/slack_router.zip" \
        --no-cli-pager

    # Wait for update to complete
    aws lambda wait function-updated --function-name "$SLACK_ROUTER"
    echo "Deployed $SLACK_ROUTER"
fi

# Deploy Findings Processor
if [[ -f "$DIST_DIR/findings_processor.zip" ]]; then
    echo "Deploying $FINDINGS_PROCESSOR..."
    aws lambda update-function-code \
        --function-name "$FINDINGS_PROCESSOR" \
        --zip-file "fileb://$DIST_DIR/findings_processor.zip" \
        --no-cli-pager

    # Wait for update to complete
    aws lambda wait function-updated --function-name "$FINDINGS_PROCESSOR"
    echo "Deployed $FINDINGS_PROCESSOR"
fi

echo ""
echo "Deployment complete!"

# Print function URLs
echo ""
echo "Lambda Functions:"
aws lambda list-functions \
    --query "Functions[?starts_with(FunctionName, 'carl-') && contains(FunctionName, '$ENVIRONMENT')].[FunctionName, LastModified]" \
    --output table \
    --no-cli-pager
