# CARL Deployment Validation Checklist

**Quick reference for validating your CARL deployment**

Use this checklist to verify each stage of your deployment is working correctly.

---

## Pre-Deployment Validation

### AWS Services Enabled

```bash
# ✓ Bedrock Models
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`)].modelId'
# Expected: Shows Claude 3.5 Sonnet and Haiku model IDs

# ✓ Security Hub
aws securityhub describe-hub --region us-east-1
# Expected: Returns hub details, not "not subscribed" error

# ✓ GuardDuty
aws guardduty list-detectors --region us-east-1
# Expected: Returns detector ID

# ✓ AWS Config
aws configservice describe-configuration-recorders
# Expected: Shows configuration recorder

# ✓ Terraform State Bucket
export BUCKET_NAME="carl-terraform-state-$(aws sts get-caller-identity --query Account --output text)"
aws s3 ls s3://${BUCKET_NAME}
# Expected: Bucket exists (may be empty)

# ✓ State Lock Table
aws dynamodb describe-table --table-name carl-terraform-state-lock
# Expected: Table details returned
```

**Status**: ⬜ All AWS services enabled and verified

---

## Configuration Validation

### Check for Placeholder Values

```bash
cd /Users/gnegelow/Documents/carl

# ✓ No CHANGEME placeholders
grep -r "CHANGEME" . --exclude-dir=.git
# Expected: No results

# ✓ No placeholder account IDs
grep -r "123456789012" . --exclude-dir=.git --exclude="*.md"
# Expected: No results in code files

# ✓ No placeholder GitHub usernames
grep -r "your-username" . --exclude-dir=.git --exclude="*.md"
# Expected: No results in code files

# ✓ Terraform backend configured
grep "bucket" carl-infrastructure/core/backend.tf
# Expected: Shows your actual bucket name with account ID
```

**Status**: ⬜ All placeholder values replaced

---

### Terraform Validation

```bash
cd /Users/gnegelow/Documents/carl/carl-infrastructure/core

# ✓ Terraform initialized
terraform init
# Expected: "Terraform has been successfully initialized!"

# ✓ Configuration valid
terraform validate
# Expected: "Success! The configuration is valid."

# ✓ Plan generates without errors
terraform plan
# Expected: Shows resources to be created, no errors
```

**Status**: ⬜ Terraform configuration valid

---

### Secrets Manager

```bash
# ✓ Slack credentials exist
aws secretsmanager describe-secret --secret-id carl/slack/credentials
# Expected: Secret details returned

# ✓ Slack credentials valid
aws secretsmanager get-secret-value --secret-id carl/slack/credentials \
  --query SecretString --output text | jq .
# Expected: Shows bot_token and signing_secret

# ✓ Jira credentials exist
aws secretsmanager describe-secret --secret-id carl/jira/credentials
# Expected: Secret details returned

# ✓ Jira credentials valid
aws secretsmanager get-secret-value --secret-id carl/jira/credentials \
  --query SecretString --output text | jq .
# Expected: Shows url, user, api_token, project
```

**Status**: ⬜ All secrets created and valid

---

## Post-Deployment Validation

### Core Infrastructure

```bash
# ✓ Lambda function exists
aws lambda get-function --function-name carl-slack-router-dev
# Expected: Function configuration returned

# ✓ Lambda function is healthy
aws lambda invoke \
  --function-name carl-slack-router-dev \
  --payload '{"body": "{\"type\": \"url_verification\", \"challenge\": \"test\"}"}' \
  /tmp/response.json && cat /tmp/response.json
# Expected: {"challenge": "test"}

# ✓ API Gateway deployed
cd /Users/gnegelow/Documents/carl/carl-infrastructure/core
export API_URL=$(terraform output -raw api_gateway_url)
echo "API Gateway URL: ${API_URL}"
# Expected: Shows HTTPS URL

# ✓ API Gateway is accessible
curl -X POST "${API_URL}/slack/events" \
  -H "Content-Type: application/json" \
  -d '{"type": "url_verification", "challenge": "test"}'
# Expected: {"challenge": "test"}
```

**Status**: ⬜ Core infrastructure deployed and accessible

---

### DynamoDB Tables

```bash
# ✓ All tables created
aws dynamodb list-tables --query 'TableNames[?starts_with(@, `carl-`)]' --output json
# Expected: Shows 12 tables:
#   - carl-findings-dev
#   - carl-evidence-dev
#   - carl-scan-history-dev
#   - carl-preferences-dev
#   - carl-approvals-dev
#   - carl-resource-graph-dev
#   - carl-pricing-cache-dev
#   - carl-learning-patterns-dev
#   - carl-jira-mapping-dev
#   - carl-learning-feedback-dev
#   - carl-learning-scan-patterns-dev
#   - carl-learning-generation-usage-dev

# ✓ Tables are active
for table in $(aws dynamodb list-tables --query 'TableNames[?starts_with(@, `carl-`)]' --output text); do
  status=$(aws dynamodb describe-table --table-name $table --query 'Table.TableStatus' --output text)
  echo "$table: $status"
done
# Expected: All tables show "ACTIVE"

# ✓ Pricing cache is populated (if prefetch ran)
aws dynamodb scan --table-name carl-pricing-cache-dev --select COUNT
# Expected: ScannedCount > 0 (after first prefetch)
```

**Status**: ⬜ All DynamoDB tables created and active

---

### S3 Buckets

```bash
# ✓ Evidence bucket exists
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3 ls s3://carl-evidence-${ACCOUNT_ID}-dev/
# Expected: Bucket is accessible

# ✓ Reports bucket exists
aws s3 ls s3://carl-reports-${ACCOUNT_ID}-dev/
# Expected: Bucket is accessible

# ✓ Buckets have encryption enabled
aws s3api get-bucket-encryption --bucket carl-evidence-${ACCOUNT_ID}-dev
# Expected: Shows encryption configuration

# ✓ Buckets block public access
aws s3api get-public-access-block --bucket carl-evidence-${ACCOUNT_ID}-dev
# Expected: All settings set to true
```

**Status**: ⬜ All S3 buckets created and secured

---

### KMS Keys

```bash
# ✓ CARL KMS key exists
aws kms list-aliases --query 'Aliases[?contains(AliasName, `carl`)]'
# Expected: Shows alias/carl-dev

# ✓ KMS key is enabled
export KEY_ID=$(aws kms list-aliases --query 'Aliases[?contains(AliasName, `carl`)].TargetKeyId' --output text)
aws kms describe-key --key-id $KEY_ID --query 'KeyMetadata.KeyState'
# Expected: "Enabled"
```

**Status**: ⬜ KMS encryption keys created

---

### IAM Roles

```bash
# ✓ Lambda execution role exists
aws iam get-role --role-name carl-slack-router-dev
# Expected: Role details returned

# ✓ Lambda role has required permissions
aws iam list-attached-role-policies --role-name carl-slack-router-dev
# Expected: Shows attached policies

# ✓ GitHub Actions role exists (if using CI/CD)
aws iam get-role --role-name GitHubActionsCARL
# Expected: Role details returned
```

**Status**: ⬜ IAM roles configured correctly

---

### CloudWatch Logs

```bash
# ✓ Log group exists
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/carl-slack-router
# Expected: Shows log group

# ✓ Logs are being written
aws logs tail /aws/lambda/carl-slack-router-dev --since 1h
# Expected: Shows recent logs (after first invocation)
```

**Status**: ⬜ CloudWatch logging configured

---

## Slack Integration Validation

### Slack App Configuration

```bash
# ✓ Get API Gateway URL
cd /Users/gnegelow/Documents/carl/carl-infrastructure/core
export API_URL=$(terraform output -raw api_gateway_url)
echo "Update Slack app with: ${API_URL}/slack/events"
```

**Manual Verification**:

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Select your CARL app
3. Verify these sections are configured with correct URL:

- ⬜ **Slash Commands**: `/carl` → Request URL = `${API_URL}/slack/events`
- ⬜ **Event Subscriptions**: Request URL = `${API_URL}/slack/events` (Status: Verified ✓)
- ⬜ **Interactivity**: Request URL = `${API_URL}/slack/events`

**Status**: ⬜ Slack app URLs configured and verified

---

### Slack Commands Testing

Test in your Slack workspace:

```
# ✓ Help command
/carl help
Expected: Shows command list with descriptions

# ✓ Ask command (AI recommendation)
/carl ask How do I create a secure S3 bucket?
Expected: Returns AI-generated recommendations with Terraform code

# ✓ Scan command (compliance scan)
/carl scan
Expected: "Scanning your AWS environment..." followed by findings summary

# ✓ Generate command (infrastructure code)
/carl generate secure VPC
Expected: Returns Terraform code for VPC with security best practices

# ✓ List commands
/carl list patterns
Expected: Shows available architecture patterns
```

**Test Results**:
- ⬜ `/carl help` working
- ⬜ `/carl ask` returning AI recommendations
- ⬜ `/carl scan` detecting findings
- ⬜ `/carl generate` creating Terraform code
- ⬜ `/carl list` showing patterns

**Status**: ⬜ All Slack commands functional

---

## Jira Integration Validation

### Jira API Connection

```bash
# ✓ Test Jira API connection
export JIRA_URL=$(aws secretsmanager get-secret-value --secret-id carl/jira/credentials --query SecretString --output text | jq -r .url)
export JIRA_USER=$(aws secretsmanager get-secret-value --secret-id carl/jira/credentials --query SecretString --output text | jq -r .user)
export JIRA_TOKEN=$(aws secretsmanager get-secret-value --secret-id carl/jira/credentials --query SecretString --output text | jq -r .api_token)

curl -u "${JIRA_USER}:${JIRA_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_URL}/rest/api/3/myself"
# Expected: Returns your Jira user details

# ✓ Verify Jira project exists
export JIRA_PROJECT=$(aws secretsmanager get-secret-value --secret-id carl/jira/credentials --query SecretString --output text | jq -r .project)
curl -u "${JIRA_USER}:${JIRA_TOKEN}" \
  "${JIRA_URL}/rest/api/3/project/${JIRA_PROJECT}"
# Expected: Returns project details
```

**Status**: ⬜ Jira API connection successful

---

### Jira Ticket Creation

Test in Slack:

```
# Run a scan that will create findings
/carl scan
```

**Manual Verification**:
1. Go to your Jira project
2. Check for new issues created by CARL

**Verify each ticket has**:
- ⬜ Summary with finding title
- ⬜ Description with detailed finding info
- ⬜ Labels with SOC2 control mappings
- ⬜ Priority based on severity (Critical/High/Medium/Low)
- ⬜ Issue type = "Bug" or "Task"

**Status**: ⬜ Jira tickets creating automatically

---

## GitHub CI/CD Validation

### GitHub Actions Setup

```bash
# ✓ OIDC provider exists
aws iam list-open-id-connect-providers \
  --query 'OpenIDConnectProviderList[?contains(Arn, `token.actions.githubusercontent.com`)]'
# Expected: Shows OIDC provider ARN

# ✓ GitHub Actions role exists
aws iam get-role --role-name GitHubActionsCARL
# Expected: Role details returned

# ✓ Trust policy allows your repo
aws iam get-role --role-name GitHubActionsCARL --query 'Role.AssumeRolePolicyDocument'
# Expected: Shows trust policy with your GitHub repo
```

**Status**: ⬜ GitHub OIDC configured

---

### GitHub Secrets

**Manual Verification**:
1. Go to your GitHub repository
2. Settings → Secrets and variables → Actions
3. Verify these secrets exist:

- ⬜ `AWS_REGION` (e.g., us-east-1)
- ⬜ `AWS_ACCOUNT_ID` (your account ID)
- ⬜ `AWS_ROLE_ARN` (GitHub Actions role ARN)
- ⬜ `TERRAFORM_STATE_BUCKET` (your state bucket name)

**Status**: ⬜ All GitHub secrets configured

---

### Workflow Testing

```bash
# Push to GitHub to trigger workflow
cd /Users/gnegelow/Documents/carl
git add .
git commit -m "Validate deployment"
git push origin main

# Monitor workflow
echo "View workflow: https://github.com/YOUR_USERNAME/carl/actions"
```

**Manual Verification**:
1. Go to GitHub Actions tab
2. Check latest workflow run
3. Verify:
   - ⬜ Workflow triggered on push
   - ⬜ Terraform plan executed successfully
   - ⬜ No authentication errors
   - ⬜ Deployment completed (if configured for main branch)

**Status**: ⬜ GitHub Actions workflows functional

---

## Feature Modules Validation

### Optional: Validate Deployed Features

If you've deployed feature modules, validate each one:

```bash
# ✓ Scanning module
aws lambda get-function --function-name carl-security-scanner-dev
# Expected: Function details returned

# ✓ Drift detection module
aws lambda get-function --function-name carl-drift-detector-dev
# Expected: Function details returned

# ✓ Real-time monitor module
aws lambda get-function --function-name carl-realtime-monitor-dev
# Expected: Function details returned

# ✓ Bootstrap module
aws lambda get-function --function-name carl-bootstrap-orchestrator-dev
# Expected: Function details returned
```

**Status**: ⬜ Feature modules deployed (if applicable)

---

## Performance & Cost Validation

### Lambda Performance

```bash
# ✓ Check Lambda metrics (last 7 days)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=carl-slack-router-dev \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average,Maximum \
  --query 'Datapoints[].[Timestamp,Average,Maximum]'
# Expected: Shows execution times (should be under 10 seconds average)

# ✓ Check Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=carl-slack-router-dev \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum
# Expected: Error count should be 0 or very low
```

**Status**: ⬜ Lambda performance acceptable

---

### Cost Monitoring

```bash
# ✓ Check current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -u +%Y-%m-01),End=$(date -u +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=SERVICE
# Expected: Shows service costs (Lambda, DynamoDB, Bedrock, etc.)

# ✓ Cost should be within expected range
# Expected monthly cost: $75-200
# - Bedrock: $30-100
# - Lambda: $5-20
# - DynamoDB: $10-30
# - S3: $5-15
# - Other: $25-35
```

**Status**: ⬜ Costs within expected range

---

## Security Validation

### Encryption

```bash
# ✓ S3 encryption enabled
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws s3api get-bucket-encryption --bucket carl-evidence-${ACCOUNT_ID}-dev
# Expected: Shows SSE-KMS with CARL key

# ✓ DynamoDB encryption enabled
aws dynamodb describe-table --table-name carl-findings-dev \
  --query 'Table.SSEDescription.Status'
# Expected: "ENABLED"

# ✓ Secrets encrypted
aws secretsmanager describe-secret --secret-id carl/slack/credentials \
  --query 'KmsKeyId'
# Expected: Shows KMS key ID
```

**Status**: ⬜ All data encrypted at rest

---

### Access Controls

```bash
# ✓ S3 buckets block public access
aws s3api get-public-access-block --bucket carl-evidence-${ACCOUNT_ID}-dev
# Expected: All settings true

# ✓ Lambda functions not publicly accessible
aws lambda get-policy --function-name carl-slack-router-dev 2>&1 | grep "ResourceNotFoundException"
# Expected: No public policy (ResourceNotFoundException is OK)

# ✓ API Gateway requires authentication
# Manual: Verify Slack signature verification in Lambda code
```

**Status**: ⬜ Access controls properly configured

---

## Final Validation

### End-to-End Test

**Complete workflow test**:

1. ⬜ In Slack, run: `/carl scan`
2. ⬜ Verify scan completes and shows findings
3. ⬜ Check Jira project for newly created tickets
4. ⬜ In Slack, run: `/carl ask What SOC2 controls do I need for S3?`
5. ⬜ Verify AI responds with relevant recommendations
6. ⬜ In Slack, run: `/carl generate secure S3 bucket`
7. ⬜ Verify Terraform code is generated
8. ⬜ Check CloudWatch logs show no errors
9. ⬜ Check DynamoDB tables have data:
   ```bash
   aws dynamodb scan --table-name carl-scan-history-dev --limit 5
   aws dynamodb scan --table-name carl-findings-dev --limit 5
   ```
10. ⬜ Verify all costs are tracking in Cost Explorer

**Status**: ⬜ End-to-end workflow successful

---

## Overall Deployment Status

| Component | Status |
|-----------|--------|
| AWS Services | ⬜ |
| Configuration | ⬜ |
| Core Infrastructure | ⬜ |
| Slack Integration | ⬜ |
| Jira Integration | ⬜ |
| GitHub CI/CD | ⬜ |
| Security | ⬜ |
| Performance | ⬜ |
| End-to-End Test | ⬜ |

---

## Troubleshooting Quick Links

If any validation fails, refer to:

- **Full Deployment Guide**: `DEPLOYMENT_SETUP_GUIDE.md`
- **Configuration Changes**: `CONFIGURATION_CHANGES_REQUIRED.md`
- **Troubleshooting Guide**: `TROUBLESHOOTING.md`
- **Architecture Details**: `ARCHITECTURE.md`

---

## Next Steps After Validation

Once all validations pass:

1. ⬜ Configure team access to Slack workspace
2. ⬜ Schedule regular compliance scans
3. ⬜ Set up CloudWatch alarms
4. ⬜ Configure billing alerts
5. ⬜ Document team-specific workflows
6. ⬜ Train team on CARL commands
7. ⬜ Review and customize architecture patterns
8. ⬜ Plan feature module deployments

---

**Deployment validated and ready for production use!** 🎉

**Last Updated**: 2026-01-30
