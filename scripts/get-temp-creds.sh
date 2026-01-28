#!/bin/bash
# Get temporary AWS credentials with MFA for CARL bootstrap
# This creates short-lived credentials that expire automatically

set -e

echo "🔐 AWS Temporary Credentials with MFA"
echo ""

# Get current IAM user
CURRENT_USER=$(aws sts get-caller-identity --query Arn --output text)
echo "Current user: $CURRENT_USER"

# Extract account ID and username
ACCOUNT_ID=$(echo $CURRENT_USER | cut -d: -f5)
USERNAME=$(echo $CURRENT_USER | cut -d/ -f2)

# MFA device ARN
MFA_DEVICE="arn:aws:iam::${ACCOUNT_ID}:mfa/${USERNAME}"

echo "MFA device: $MFA_DEVICE"
echo ""

# Prompt for MFA token
read -p "Enter MFA token code: " MFA_TOKEN

# Request temporary credentials (valid for 4 hours)
echo ""
echo "Requesting temporary credentials..."

CREDENTIALS=$(aws sts get-session-token \
    --serial-number "$MFA_DEVICE" \
    --token-code "$MFA_TOKEN" \
    --duration-seconds 14400)

# Extract credentials
ACCESS_KEY=$(echo $CREDENTIALS | jq -r '.Credentials.AccessKeyId')
SECRET_KEY=$(echo $CREDENTIALS | jq -r '.Credentials.SecretAccessKey')
SESSION_TOKEN=$(echo $CREDENTIALS | jq -r '.Credentials.SessionToken')
EXPIRATION=$(echo $CREDENTIALS | jq -r '.Credentials.Expiration')

# Export to environment
export AWS_ACCESS_KEY_ID="$ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$SECRET_KEY"
export AWS_SESSION_TOKEN="$SESSION_TOKEN"

echo ""
echo "✅ Temporary credentials acquired!"
echo "Expires: $EXPIRATION"
echo ""
echo "Credentials are set in your environment."
echo "Run your AWS commands now (they will use MFA credentials)."
echo ""
echo "Example:"
echo "  ./bootstrap.sh"
echo ""
echo "To use in a new terminal, run:"
echo "  export AWS_ACCESS_KEY_ID=$ACCESS_KEY"
echo "  export AWS_SECRET_ACCESS_KEY=$SECRET_KEY"
echo "  export AWS_SESSION_TOKEN=$SESSION_TOKEN"
echo ""
