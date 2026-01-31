# CARL Prerequisites Checklist

Complete checklist of everything needed to deploy CARL successfully.

---

## AWS Requirements

### 1. AWS Account Access
- [ ] AWS account with admin access (or IAM user with sufficient permissions)
- [ ] AWS CLI installed and configured
  ```bash
  aws --version  # Should be >= 2.0
  aws sts get-caller-identity  # Verify credentials
  ```

### 2. AWS Bedrock Model Access ⚠️ CRITICAL
- [ ] AWS Bedrock enabled in your deployment region (default: `us-east-1`)
- [ ] Claude 3.5 Sonnet model access enabled
- [ ] Claude 3 Haiku model access enabled

**How to enable:**
1. Go to: https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess
2. Click "Enable specific models"
3. Select:
   - ✅ Claude 3.5 Sonnet
   - ✅ Claude 3 Haiku
4. Click "Save changes"
5. Access is typically granted instantly

**Verify access:**
```bash
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `anthropic.claude-3-5-sonnet`)].modelId'
```

If you see model IDs listed, you're good to go!

**Note:** The bootstrap script will verify Bedrock access and provide instructions if needed.

### 3. AWS Security Hub ⚠️ REQUIRED

- [ ] AWS Security Hub enabled in your deployment region
- [ ] Security standards enabled (CIS AWS Foundations, AWS Foundational Security Best Practices)

**Why required:** CARL uses Security Hub as its primary source for security findings and compliance checks. Without it, CARL cannot scan your AWS environment.

**How to enable:**
1. Go to: https://console.aws.amazon.com/securityhub/home
2. Click "Go to Security Hub"
3. Click "Enable Security Hub"
4. Enable standards:
   - ✅ AWS Foundational Security Best Practices
   - ✅ CIS AWS Foundations Benchmark
   - ⚠️  Note: This will start scanning your AWS resources (first scan takes ~30 minutes)

**Verify Security Hub is enabled:**
```bash
aws securityhub describe-hub --region us-east-1
```

**Cost:** Security Hub costs ~$0.0010 per security check per month. Typical account: $5-15/month.

### 4. AWS Config ⚠️ REQUIRED

- [ ] AWS Config enabled in your deployment region
- [ ] Configuration recorder running
- [ ] S3 bucket for Config delivery channel created

**Why required:** CARL uses AWS Config to track resource configurations and detect drift over time. Config provides the historical baseline for compliance checks.

**How to enable:**
1. Go to: https://console.aws.amazon.com/config/home
2. Click "Get started" or "Settings"
3. Configuration recorder:
   - Record all resources in this region: ✅ Yes
   - Include global resources: ✅ Yes (if in primary region)
4. Delivery channel:
   - S3 bucket: Let AWS create one for you (or specify existing)
   - SNS topic: Optional (not required for CARL)
5. Click "Next" and "Confirm"

**Verify Config is running:**
```bash
aws configservice describe-configuration-recorders --region us-east-1
aws configservice describe-configuration-recorder-status --region us-east-1
```

**Cost:** AWS Config costs ~$0.003 per configuration item recorded, plus ~$0.001 per rule evaluation. Typical account: $10-30/month.

### 5. Optional Security Tools

CARL can leverage additional AWS security tools when enabled. These are **NOT required** but provide enhanced security insights when available:

**✅ Currently Supported:**
- **Amazon GuardDuty** - Threat detection
  - CARL will scan GuardDuty findings if enabled
  - Reported findings will include severity and recommendations
  - Cost: ~$4.45/month for 50GB CloudTrail + VPC Flow Log analysis

- **Amazon Inspector (v2)** - Vulnerability scanning
  - CARL will scan Inspector findings for EC2, ECR, Lambda vulnerabilities
  - Reported findings include CVE details and remediation
  - Cost: ~$0.09 per EC2 instance/month, $0.09 per re-scan

- **Amazon Macie** - Sensitive data discovery
  - CARL will scan Macie findings if enabled
  - Reported findings include data classification and location
  - Cost: ~$1.00/GB for S3 inventory + $0.10/GB for data classification

**CARL's Behavior:**
- ✅ If enabled: CARL scans findings and reports them
- ✅ If disabled: CARL notes tool is disabled (informational only, not critical)
- ❌ CARL will NOT automatically enable these tools (you must enable manually)

**Future Support (Not Yet Implemented):**
- Amazon Detective - Security investigation
- IAM Access Analyzer - IAM policy analysis

### 6. Terraform
- [ ] Terraform >= 1.0 installed
  ```bash
  terraform version  # Should be >= 1.0.0
  ```

---

## GitHub Requirements

### 1. Repository
- [ ] GitHub repository created (e.g., `your-org/CARL`)
- [ ] CARL code pushed to repository
- [ ] GitHub Actions enabled

### 2. GitHub CLI (optional but recommended)
- [ ] GitHub CLI installed
  ```bash
  gh --version  # Recommended for easy secret management
  ```

### 3. GitHub Personal Access Token
- [ ] Token with `repo` scope created
- [ ] Token stored securely (needed for adding secrets)

**Create token:**
1. Go to: https://github.com/settings/personal-access-tokens/new
2. Token name: `CARL Bootstrap`
3. Expiration: 7 days (short-lived, only for setup)
4. Repository access: "Only select repositories" → Choose CARL repo
5. Permissions:
   - Repository permissions → Secrets → Read and write
6. Generate token

---

## Slack Requirements

### 1. Slack Workspace
- [ ] Slack workspace with admin access
- [ ] Ability to create Slack apps

### 2. Slack App Created
- [ ] Slack app created at https://api.slack.com/apps
- [ ] App name: `CARL-dev` (or `CARL` for single environment)
- [ ] OAuth scope `chat:write` added
- [ ] Bot User OAuth Token obtained (starts with `xoxb-`)
- [ ] Signing Secret obtained

**Quick steps:**
1. https://api.slack.com/apps → "Create New App" → "From scratch"
2. Name: `CARL-dev`, select workspace
3. OAuth & Permissions → Bot Token Scopes → Add `chat:write`
4. Install to Workspace
5. Copy Bot User OAuth Token
6. Basic Information → Copy Signing Secret

See [SLACK_SETUP.md](./SLACK_SETUP.md) for detailed instructions.

---

## Summary Checklist

**Before running bootstrap:**
- [ ] AWS CLI configured
- [ ] **AWS Bedrock model access enabled** (most common blocker!)
- [ ] Terraform >= 1.0 installed
- [ ] GitHub repository created with CARL code
- [ ] GitHub token ready
- [ ] Slack app created with bot token and signing secret

**After bootstrap, before deployment:**
- [ ] 6 GitHub secrets added:
  - [ ] `AWS_ROLE_ARN_DEV`
  - [ ] `AWS_ROLE_ARN_QA`
  - [ ] `AWS_ROLE_ARN_PROD`
  - [ ] `AWS_REGION`
  - [ ] `SLACK_BOT_TOKEN_DEV`
  - [ ] `SLACK_SIGNING_SECRET_DEV`

---

## Cost Expectations

Before deploying, understand the costs:

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| S3 state bucket | ~$0.50 | Bootstrap creates this |
| Lambda (CARL core) | $10-30 | Based on usage |
| DynamoDB | $5-15 | Pay-per-request |
| API Gateway | $3-10 | Per million requests |
| Bedrock API calls | $20-100 | Claude Haiku/Sonnet usage |
| **Total** | **$40-155/month** | Scales with usage |

**Free Tier:** Some services have free tier coverage for first 12 months.

---

## Region Considerations

CARL supports deployment to any AWS region, but consider:

**Bedrock Availability:**
- ✅ `us-east-1` (N. Virginia) - Recommended, all Claude models available
- ✅ `us-west-2` (Oregon) - All Claude models available
- ✅ `eu-west-1` (Ireland) - All Claude models available
- ⚠️  Other regions - Check Bedrock availability first

**Recommendation:** Use `us-east-1` for simplest setup (default in bootstrap).

---

## Network Requirements

If deploying from restricted network:

**Required outbound access:**
- `*.amazonaws.com` (AWS services)
- `github.com` (Git operations)
- `api.slack.com` (Slack API)
- `registry.terraform.io` (Terraform providers)

**Ports:**
- `443` (HTTPS) for all services

---

## IAM Permissions Required

For the user running `./bootstrap.sh`:

**Minimum permissions:**
- S3: `CreateBucket`, `PutBucketVersioning`, `PutBucketEncryption`, `PutPublicAccessBlock`, `PutLifecycleConfiguration`
- IAM: `CreateOpenIDConnectProvider`, `CreateRole`, `CreatePolicy`, `AttachRolePolicy`
- Bedrock: `ListFoundationModels` (for verification)
- Terraform state access

**Recommendation:** Use an admin user for initial bootstrap, then restrict permissions later.

---

## Troubleshooting

### "Bedrock not available in my region"

**Solution:** Change deployment region in bootstrap script:
```bash
export AWS_REGION=us-west-2  # or eu-west-1
./bootstrap.sh
```

### "Don't have admin access to AWS"

**Solution:** Request these specific permissions from your AWS admin:
- S3 bucket creation and management
- IAM role/policy creation (limited to `carl-*` resources)
- OIDC provider creation
- Bedrock ListFoundationModels access

Share the `carl-infrastructure/oidc/main.tf` IAM policies with your admin as reference.

### "Can't create Slack app"

**Solution:** Request Slack workspace admin to:
1. Enable app creation for your user, OR
2. Create the Slack app for you and provide bot token + signing secret

### "GitHub Actions not available"

**Solution:** GitHub Actions is free for public repos, paid for private repos. If not available:
- Make repo public (if acceptable), OR
- Purchase GitHub Actions minutes, OR
- Deploy manually via Terraform (see manual deployment docs)

---

## Next Steps

Once all prerequisites are met:

1. **Run bootstrap:** `./bootstrap.sh`
2. **Add secrets:** Use GitHub CLI or UI
3. **Deploy:** `git push origin develop`
4. **Configure Slack:** Add slash commands and events
5. **Test:** `/carl help` in Slack

See [BOOTSTRAP.md](./BOOTSTRAP.md) for step-by-step deployment guide.

---

**Last Updated:** 2026-01-28
