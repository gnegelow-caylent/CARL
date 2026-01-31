#!/bin/bash

# CARL Deployment Validation Script
# Runs comprehensive checks to verify CARL is deployed correctly

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# ============================================================================
# Helper Functions
# ============================================================================

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNING++))
}

section_header() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# ============================================================================
# Banner
# ============================================================================

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║                  CARL Deployment Validation                      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Get AWS info
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
ENVIRONMENT="dev"

# ============================================================================
# AWS Services
# ============================================================================

section_header "AWS Services"

# Bedrock
if aws bedrock list-foundation-models --region "$AWS_REGION" --query 'modelSummaries[?contains(modelId, `claude-3-5-sonnet`)].modelId' --output text 2>/dev/null | grep -q claude; then
    check_pass "Bedrock: Claude models accessible"
else
    check_fail "Bedrock: Claude models not accessible"
fi

# Security Hub
if aws securityhub describe-hub --region "$AWS_REGION" &>/dev/null; then
    check_pass "Security Hub: Enabled"
else
    check_fail "Security Hub: Not enabled"
fi

# GuardDuty
if aws guardduty list-detectors --region "$AWS_REGION" --query 'DetectorIds[0]' --output text 2>/dev/null | grep -qv None; then
    check_pass "GuardDuty: Enabled"
else
    check_fail "GuardDuty: Not enabled"
fi

# AWS Config
if aws configservice describe-configuration-recorders --region "$AWS_REGION" 2>/dev/null | grep -q ConfigurationRecorders; then
    check_pass "AWS Config: Enabled"
else
    check_warn "AWS Config: Not enabled (optional)"
fi

# ============================================================================
# Terraform Backend
# ============================================================================

section_header "Terraform Backend"

STATE_BUCKET="carl-terraform-state-${AWS_ACCOUNT_ID}"
LOCK_TABLE="carl-terraform-state-lock"

# S3 Bucket
if aws s3 ls "s3://${STATE_BUCKET}" &>/dev/null; then
    check_pass "S3 State Bucket: $STATE_BUCKET exists"

    # Check versioning
    if aws s3api get-bucket-versioning --bucket "$STATE_BUCKET" 2>/dev/null | grep -q "Enabled"; then
        check_pass "S3 Versioning: Enabled"
    else
        check_fail "S3 Versioning: Not enabled"
    fi

    # Check encryption
    if aws s3api get-bucket-encryption --bucket "$STATE_BUCKET" &>/dev/null; then
        check_pass "S3 Encryption: Enabled"
    else
        check_fail "S3 Encryption: Not enabled"
    fi
else
    check_fail "S3 State Bucket: Does not exist"
fi

# DynamoDB Lock Table
if aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$AWS_REGION" &>/dev/null; then
    check_pass "DynamoDB Lock Table: $LOCK_TABLE exists"
else
    check_fail "DynamoDB Lock Table: Does not exist"
fi

# ============================================================================
# Core Infrastructure
# ============================================================================

section_header "Core Infrastructure"

# Lambda Function
LAMBDA_NAME="carl-slack-router-${ENVIRONMENT}"
if aws lambda get-function --function-name "$LAMBDA_NAME" --region "$AWS_REGION" &>/dev/null; then
    check_pass "Lambda Function: $LAMBDA_NAME exists"

    # Test invoke
    RESPONSE=$(aws lambda invoke \
        --function-name "$LAMBDA_NAME" \
        --payload '{"body": "{\"type\": \"url_verification\", \"challenge\": \"test\"}"}' \
        --region "$AWS_REGION" \
        /tmp/lambda-test.json 2>&1)

    if grep -q '"challenge": "test"' /tmp/lambda-test.json 2>/dev/null; then
        check_pass "Lambda Test Invoke: Successful"
    else
        check_fail "Lambda Test Invoke: Failed"
    fi
    rm -f /tmp/lambda-test.json
else
    check_fail "Lambda Function: Does not exist"
fi

# API Gateway
cd "$(dirname "${BASH_SOURCE[0]}")/carl-infrastructure/core" 2>/dev/null
if [ -f "terraform.tfstate" ] || terraform state list &>/dev/null 2>&1; then
    API_URL=$(terraform output -raw api_gateway_url 2>/dev/null)
    if [ -n "$API_URL" ] && [ "$API_URL" != "null" ]; then
        check_pass "API Gateway: $API_URL"

        # Test endpoint
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/slack/events" \
            -H "Content-Type: application/json" \
            -d '{"type": "url_verification", "challenge": "test"}' 2>/dev/null)

        if [ "$HTTP_CODE" = "200" ]; then
            check_pass "API Gateway Test: HTTP 200 OK"
        else
            check_fail "API Gateway Test: HTTP $HTTP_CODE"
        fi
    else
        check_fail "API Gateway: URL not found"
    fi
else
    check_warn "API Gateway: Cannot check (no Terraform state)"
fi
cd - > /dev/null 2>&1

# ============================================================================
# DynamoDB Tables
# ============================================================================

section_header "DynamoDB Tables"

EXPECTED_TABLES=(
    "carl-findings-${ENVIRONMENT}"
    "carl-evidence-${ENVIRONMENT}"
    "carl-scan-history-${ENVIRONMENT}"
    "carl-preferences-${ENVIRONMENT}"
    "carl-approvals-${ENVIRONMENT}"
    "carl-resource-graph-${ENVIRONMENT}"
    "carl-pricing-cache-${ENVIRONMENT}"
)

for table in "${EXPECTED_TABLES[@]}"; do
    if aws dynamodb describe-table --table-name "$table" --region "$AWS_REGION" &>/dev/null; then
        STATUS=$(aws dynamodb describe-table --table-name "$table" --region "$AWS_REGION" --query 'Table.TableStatus' --output text)
        if [ "$STATUS" = "ACTIVE" ]; then
            check_pass "Table: $table (ACTIVE)"
        else
            check_warn "Table: $table ($STATUS)"
        fi
    else
        check_fail "Table: $table (NOT FOUND)"
    fi
done

# ============================================================================
# S3 Buckets
# ============================================================================

section_header "S3 Buckets"

EVIDENCE_BUCKET="carl-evidence-${AWS_ACCOUNT_ID}-${ENVIRONMENT}"
REPORTS_BUCKET="carl-reports-${AWS_ACCOUNT_ID}-${ENVIRONMENT}"

for bucket in "$EVIDENCE_BUCKET" "$REPORTS_BUCKET"; do
    if aws s3 ls "s3://${bucket}" &>/dev/null; then
        check_pass "Bucket: $bucket exists"

        # Check encryption
        if aws s3api get-bucket-encryption --bucket "$bucket" &>/dev/null; then
            check_pass "Bucket Encryption: $bucket"
        else
            check_fail "Bucket Encryption: $bucket not encrypted"
        fi

        # Check public access block
        if aws s3api get-public-access-block --bucket "$bucket" 2>/dev/null | grep -q "true"; then
            check_pass "Public Access Block: $bucket"
        else
            check_fail "Public Access Block: $bucket not configured"
        fi
    else
        check_fail "Bucket: $bucket does not exist"
    fi
done

# ============================================================================
# KMS Keys
# ============================================================================

section_header "KMS Encryption"

KMS_ALIAS="alias/carl-${ENVIRONMENT}"
if aws kms list-aliases --region "$AWS_REGION" --query "Aliases[?AliasName=='${KMS_ALIAS}'].TargetKeyId" --output text 2>/dev/null | grep -q .; then
    KEY_ID=$(aws kms list-aliases --region "$AWS_REGION" --query "Aliases[?AliasName=='${KMS_ALIAS}'].TargetKeyId" --output text)
    check_pass "KMS Key: $KMS_ALIAS exists"

    # Check key state
    KEY_STATE=$(aws kms describe-key --key-id "$KEY_ID" --region "$AWS_REGION" --query 'KeyMetadata.KeyState' --output text 2>/dev/null)
    if [ "$KEY_STATE" = "Enabled" ]; then
        check_pass "KMS Key State: Enabled"
    else
        check_fail "KMS Key State: $KEY_STATE"
    fi
else
    check_fail "KMS Key: Does not exist"
fi

# ============================================================================
# Secrets Manager
# ============================================================================

section_header "Secrets Manager"

# Slack credentials
if aws secretsmanager describe-secret --secret-id "carl/slack/credentials" --region "$AWS_REGION" &>/dev/null; then
    check_pass "Secret: Slack credentials exist"

    # Validate secret content
    SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "carl/slack/credentials" --region "$AWS_REGION" --query SecretString --output text 2>/dev/null)
    if echo "$SECRET_VALUE" | jq -e '.bot_token and .signing_secret' &>/dev/null; then
        check_pass "Secret: Slack credentials valid format"
    else
        check_fail "Secret: Slack credentials invalid format"
    fi
else
    check_fail "Secret: Slack credentials not found"
fi

# Jira credentials (optional)
if aws secretsmanager describe-secret --secret-id "carl/jira/credentials" --region "$AWS_REGION" &>/dev/null; then
    check_pass "Secret: Jira credentials exist"
else
    check_warn "Secret: Jira credentials not found (optional)"
fi

# GitHub credentials
if aws secretsmanager describe-secret --secret-id "carl/github/token" --region "$AWS_REGION" &>/dev/null; then
    check_pass "Secret: GitHub credentials exist"
else
    check_fail "Secret: GitHub credentials not found"
fi

# ============================================================================
# IAM Roles
# ============================================================================

section_header "IAM Roles"

# Lambda execution role
LAMBDA_ROLE="carl-slack-router-${ENVIRONMENT}"
if aws iam get-role --role-name "$LAMBDA_ROLE" &>/dev/null; then
    check_pass "IAM Role: $LAMBDA_ROLE exists"
else
    check_fail "IAM Role: $LAMBDA_ROLE not found"
fi

# ============================================================================
# CloudWatch Logs
# ============================================================================

section_header "CloudWatch Logs"

LOG_GROUP="/aws/lambda/carl-slack-router-${ENVIRONMENT}"
if aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --region "$AWS_REGION" 2>/dev/null | grep -q "$LOG_GROUP"; then
    check_pass "Log Group: $LOG_GROUP exists"

    # Check for recent logs
    RECENT_LOGS=$(aws logs describe-log-streams \
        --log-group-name "$LOG_GROUP" \
        --order-by LastEventTime \
        --descending \
        --max-items 1 \
        --region "$AWS_REGION" 2>/dev/null | jq -r '.logStreams[0].lastEventTimestamp // empty')

    if [ -n "$RECENT_LOGS" ]; then
        check_pass "Log Activity: Recent logs found"
    else
        check_warn "Log Activity: No logs yet (Lambda hasn't been invoked)"
    fi
else
    check_fail "Log Group: Does not exist"
fi

# ============================================================================
# Configuration Files
# ============================================================================

section_header "Configuration Files"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check backend.tf
if [ -f "$SCRIPT_DIR/carl-infrastructure/core/backend.tf" ]; then
    if grep -q "CHANGEME" "$SCRIPT_DIR/carl-infrastructure/core/backend.tf"; then
        check_fail "backend.tf: Contains placeholder values"
    else
        check_pass "backend.tf: Configured"
    fi
else
    check_fail "backend.tf: Not found"
fi

# Check for placeholder account IDs in workflows
if grep -rq "123456789012" "$SCRIPT_DIR/.github/workflows/" 2>/dev/null; then
    check_fail "GitHub Workflows: Contains placeholder account ID"
else
    check_pass "GitHub Workflows: Configured"
fi

# Check terraform.tfvars
if [ -f "$SCRIPT_DIR/carl-infrastructure/core/terraform.tfvars" ]; then
    check_pass "terraform.tfvars: Exists"
else
    check_warn "terraform.tfvars: Not found (may use defaults)"
fi

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Validation Summary${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${GREEN}Passed:${NC}   $CHECKS_PASSED"
echo -e "  ${RED}Failed:${NC}   $CHECKS_FAILED"
echo -e "  ${YELLOW}Warnings:${NC} $CHECKS_WARNING"
echo ""

# Overall status
TOTAL_CHECKS=$((CHECKS_PASSED + CHECKS_FAILED + CHECKS_WARNING))
PASS_RATE=$((CHECKS_PASSED * 100 / TOTAL_CHECKS))

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical checks passed! CARL is ready to use.${NC}"
    EXIT_CODE=0
elif [ $CHECKS_FAILED -le 2 ]; then
    echo -e "${YELLOW}⚠ Minor issues found. CARL may work but review failures above.${NC}"
    EXIT_CODE=1
else
    echo -e "${RED}✗ Multiple failures detected. Please fix issues before using CARL.${NC}"
    EXIT_CODE=2
fi

echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""

if [ $CHECKS_FAILED -gt 0 ]; then
    echo "  1. Review failed checks above"
    echo "  2. Fix configuration issues"
    echo "  3. Re-run validation: ./validate-deployment.sh"
    echo ""
fi

echo "  • Test in Slack: /carl help"
echo "  • View logs: aws logs tail /aws/lambda/carl-slack-router-${ENVIRONMENT} --follow"
echo "  • Read docs: DEPLOYMENT_SETUP_GUIDE.md"
echo ""

exit $EXIT_CODE
