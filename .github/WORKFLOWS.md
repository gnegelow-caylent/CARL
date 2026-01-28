# CARL GitHub Actions Workflows

Complete CI/CD pipeline documentation for CARL.

---

## Workflows Overview

| Workflow | Trigger | Purpose | Runtime |
|----------|---------|---------|---------|
| **PR Validation** | Pull requests | Validate code, test, security scan | ~10 min |
| **Deploy Core** | Push to main/develop | Deploy core infrastructure | ~15 min |
| **Deploy Features** | Manual dispatch | Deploy individual features | ~10 min |
| **Integration Tests** | Manual/Scheduled | Test deployed infrastructure | ~5 min |
| **Release** | Version tags (v*) | Create releases with artifacts | ~5 min |

---

## 1. PR Validation (`pr-validation.yml`)

**Trigger:** Every pull request to main or develop

**Jobs:**
1. **Python Validation**
   - Lint with pylint and flake8
   - Type checking with mypy
   - Run unit tests with pytest
   - Upload coverage to Codecov

2. **Terraform Validation**
   - Format check (terraform fmt)
   - Initialize and validate
   - Runs for all modules in parallel

3. **Security Scan**
   - Trivy vulnerability scanning
   - tfsec for Terraform security
   - Checkov for infrastructure as code
   - Upload results to GitHub Security tab

4. **Lambda Package Test**
   - Build Lambda package
   - Verify size < 50MB limit
   - Upload as artifact for review

5. **Terraform Plan**
   - Run plan for dev/qa/prod
   - Comment plan output on PR
   - No actual deployment

6. **Documentation Validation**
   - Check for broken links
   - Validate markdown format

7. **PR Summary**
   - Aggregate all job results
   - Fail PR if critical jobs fail

**Required Secrets:**
- `AWS_ACCESS_KEY_ID_DEV`
- `AWS_SECRET_ACCESS_KEY_DEV`
- `AWS_ACCESS_KEY_ID_QA`
- `AWS_SECRET_ACCESS_KEY_QA`
- `AWS_ACCESS_KEY_ID_PROD`
- `AWS_SECRET_ACCESS_KEY_PROD`

**Pass Criteria:**
- All Python tests pass
- Terraform is valid
- No critical security issues
- Lambda package under 50MB

---

## 2. Deploy Core (`deploy-core.yml`)

**Trigger:** Push to main or develop branches

**Jobs:**
1. **Validate**
   - Terraform format check
   - Terraform validate
   - Python linting
   - Run tests

2. **Security Scan**
   - Trivy vulnerability scanning
   - Upload results to Security tab

3. **Plan** (PR only)
   - Run terraform plan
   - Comment plan on PR

4. **Deploy to Dev** (develop branch)
   - Auto-deploy on push to develop
   - Package Lambda
   - Run terraform apply
   - Output deployment info

5. **Deploy to QA** (develop branch)
   - Requires manual approval
   - Deploys after dev succeeds

6. **Deploy to Prod** (main branch)
   - Requires 2 manual approvals
   - Notifies Slack on completion

**Deployment Flow:**
```
Push to develop → Auto-deploy to dev → Approval → Deploy to QA
Push to main    → Approval → Deploy to prod → Slack notification
```

**Required Secrets:**
- AWS credentials per environment
- Slack credentials per environment
- `PROD_APPROVERS` (comma-separated GitHub usernames)
- `SLACK_WEBHOOK_URL`

---

## 3. Deploy Features (`deploy-features.yml`)

**Trigger:** Manual workflow dispatch or CARL via GitHub API

**Inputs:**
- `feature`: monitoring, bootstrap, reporting, foundation, drift_detection, auto_remediation
- `environment`: dev, qa, prod
- `action`: enable, disable

**Jobs:**
1. **Deploy Feature**
   - Configure AWS credentials
   - Initialize Terraform
   - Run plan with feature flag
   - Apply if plan succeeds
   - Notify CARL via `/deployment-complete` endpoint
   - Post to Slack (prod only)

**How CARL Triggers:**
```python
POST https://api.github.com/repos/{owner}/{repo}/actions/workflows/deploy-features.yml/dispatches
{
  "ref": "main",
  "inputs": {
    "feature": "monitoring",
    "environment": "dev",
    "action": "enable"
  }
}
```

**CARL Notification Endpoint:**
```
POST <carl-api-endpoint>/deployment-complete
{
  "feature": "monitoring",
  "environment": "dev",
  "action": "enable",
  "status": "success|failure",
  "workflow_run_id": "1234567890"
}
```

**Required Secrets:**
- AWS credentials per environment
- `CARL_DEPLOYMENT_TOKEN`
- `SLACK_WEBHOOK_URL` (prod only)

---

## 4. Integration Tests (`integration-tests.yml`)

**Trigger:** Manual dispatch or daily at 6 AM UTC

**Inputs:**
- `environment`: dev, qa, prod

**Jobs:**
1. **Integration Tests**
   - API health check
   - DynamoDB table verification
   - Lambda function test
   - SSM parameter check
   - Run integration test suite (when available)
   - Slack webhook test (dev only)

2. **Smoke Tests**
   - Check enabled features
   - Verify monitoring resources
   - Generate summary report

**Usage:**
```bash
# Manual trigger
gh workflow run integration-tests.yml -f environment=dev

# Or via GitHub UI: Actions → Integration Tests → Run workflow
```

**Required Secrets:**
- AWS credentials for target environment

---

## 5. Release (`release.yml`)

**Trigger:** Push tag matching `v*` (e.g., v1.0.0)

**Jobs:**
1. **Create Release**
   - Extract version from tag
   - Generate changelog from commits
   - Build Lambda package
   - Create GitHub release
   - Attach Lambda package as artifact
   - Notify Slack

**Creating a Release:**
```bash
# Tag the release
git tag -a v1.0.0 -m "CARL v1.0.0 - Initial release"
git push origin v1.0.0

# GitHub Actions automatically:
# - Builds Lambda package
# - Creates release with changelog
# - Notifies Slack
```

**Release Contents:**
- Lambda package (`lambda-{version}.zip`)
- Automated changelog
- Deployment instructions
- Links to documentation

**Required Secrets:**
- `SLACK_WEBHOOK_URL`

---

## Supporting Files

### `.pylintrc`
Python linting configuration:
- Max line length: 120
- Disabled rules: C0111, C0103, R0903, R0913, W0212, W0511

### `.github/markdown-link-check-config.json`
Markdown link validation:
- Ignores localhost links
- Ignores api.slack.com (requires auth)
- Retry on 429 status
- 20s timeout

### `.github/markdownlint-config.json`
Markdown format validation:
- Line length: 120
- Allows inline HTML
- Allows long code blocks

### `.github/CODEOWNERS`
Automatic code review assignments:
- Infrastructure: @gnegelow-caylent
- Python code: @gnegelow-caylent
- Workflows: @gnegelow-caylent

### `.github/dependabot.yml`
Automated dependency updates:
- Python packages (weekly on Monday)
- GitHub Actions (weekly)
- Terraform modules (weekly)
- Ignores major version updates

---

## Workflow Permissions

### GitHub Token Permissions Required

**PR Validation:**
- `contents: read`
- `pull-requests: write` (for commenting)
- `security-events: write` (for security scanning)

**Deploy Core:**
- `contents: read`
- `id-token: write` (for AWS OIDC)
- `deployments: write`

**Deploy Features:**
- `contents: read`
- `id-token: write`

**Release:**
- `contents: write` (for creating releases)

---

## Required GitHub Secrets

### AWS Credentials (Per Environment)
```
AWS_ACCESS_KEY_ID_DEV
AWS_SECRET_ACCESS_KEY_DEV

AWS_ACCESS_KEY_ID_QA
AWS_SECRET_ACCESS_KEY_QA

AWS_ACCESS_KEY_ID_PROD
AWS_SECRET_ACCESS_KEY_PROD
```

### Slack Credentials (Per Environment)
```
SLACK_BOT_TOKEN_DEV
SLACK_SIGNING_SECRET_DEV

SLACK_BOT_TOKEN_QA
SLACK_SIGNING_SECRET_QA

SLACK_BOT_TOKEN_PROD
SLACK_SIGNING_SECRET_PROD
```

### GitHub Integration
```
GITHUB_TOKEN            # Automatically provided by GitHub
CARL_DEPLOYMENT_TOKEN   # For CARL to call deployment-complete endpoint
```

### Notifications
```
SLACK_WEBHOOK_URL       # For deployment/release notifications
PROD_APPROVERS          # Comma-separated GitHub usernames for prod approvals
```

---

## Workflow Best Practices

### 1. Branch Protection

Configure branch protection for `main` and `develop`:
- Require PR before merging
- Require status checks to pass:
  - Python Validation
  - Terraform Validation
  - Security Scan
  - Lambda Package
- Require code review from CODEOWNERS
- Dismiss stale reviews on new commits

### 2. Environment Protection

Configure environment protection:

**dev:**
- No protection rules (auto-deploy)

**qa:**
- Require 1 reviewer approval
- Restrict to develop branch

**prod:**
- Require 2 reviewer approvals
- Restrict to main branch
- Require all status checks to pass
- Only allow specific reviewers (PROD_APPROVERS)

### 3. Monitoring

Set up monitoring for workflow failures:
- Enable workflow notifications in Slack
- Monitor GitHub Actions usage (minutes consumed)
- Set up billing alerts for Actions usage

### 4. Secret Rotation

Rotate secrets regularly:
- AWS credentials every 90 days
- Slack tokens when team members leave
- GitHub tokens every 6 months

### 5. Cost Optimization

Optimize GitHub Actions usage:
- Use caching for dependencies
- Run expensive jobs only when necessary
- Use `paths` filters to skip irrelevant changes
- Set appropriate timeouts

---

## Troubleshooting

### PR Validation Fails

**Terraform format check fails:**
```bash
cd carl-infrastructure
terraform fmt -recursive
git commit -am "Fix Terraform formatting"
```

**Python tests fail:**
```bash
cd carl-app
pytest tests/unit/ -v
# Fix failing tests
```

**Security scan finds issues:**
- Review Trivy/Checkov output in GitHub Security tab
- Fix critical/high severity issues
- Add exceptions for false positives

### Deploy Core Fails

**Terraform apply fails:**
- Check AWS credentials are valid
- Verify IAM permissions are sufficient
- Review Terraform logs in GitHub Actions

**Lambda package too large:**
- Remove unnecessary dependencies from requirements.txt
- Use Lambda layers for large libraries
- Exclude test files from package

### Feature Deployment Fails

**GitHub Actions not triggered:**
- Verify GITHUB_TOKEN has workflow scope
- Check GITHUB_REPO format is "owner/repo"
- Review Lambda logs for GitHub API errors

**Terraform plan fails:**
- Check feature dependencies are enabled
- Verify module paths are correct
- Review Terraform variables

### Integration Tests Fail

**API health check fails:**
- Verify Lambda is deployed
- Check API Gateway configuration
- Review Lambda logs for errors

**DynamoDB table not found:**
- Verify table name matches environment
- Check AWS region is correct
- Ensure DynamoDB is deployed

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Developer Workflow                       │
└─────────────────────────────────────────────────────────────┘

1. Create PR
   ↓
   PR Validation (10 min)
   - Lint, test, security scan
   - Terraform plan
   - Comment results on PR
   ↓
2. Review & Approve
   ↓
3. Merge to develop
   ↓
   Deploy Core → dev (auto)
   - Terraform apply
   - Deploy Lambda
   - Update infrastructure
   ↓
4. Manual approval
   ↓
   Deploy Core → qa
   ↓
5. Merge to main
   ↓
   Deploy Core → prod (2 approvals required)
   - Terraform apply
   - Slack notification
   ↓
6. Tag release (optional)
   ↓
   Release workflow
   - Build artifacts
   - Create GitHub release
   - Notify Slack

┌─────────────────────────────────────────────────────────────┐
│                   Feature Deployment Flow                    │
└─────────────────────────────────────────────────────────────┘

User in Slack: /carl enable monitoring
   ↓
CARL triggers GitHub Actions API
   ↓
Deploy Features workflow
   - terraform apply -var="enable_monitoring=true"
   ↓
Notify CARL when complete
   ↓
CARL notifies user in Slack
```

---

## Next Steps

1. **Configure GitHub Secrets**
   - Add all AWS credentials
   - Add Slack tokens
   - Add CARL_DEPLOYMENT_TOKEN

2. **Set up Branch Protection**
   - Configure rules for main and develop
   - Require status checks

3. **Configure Environments**
   - Set up dev/qa/prod environments
   - Add protection rules
   - Add approvers

4. **Test Workflows**
   - Create a test PR
   - Verify PR validation runs
   - Test feature deployment

5. **Set up Monitoring**
   - Enable Slack notifications
   - Monitor Actions usage
   - Set up billing alerts

---

## Support

- **Workflow Issues:** Check GitHub Actions logs
- **AWS Deployment Issues:** Review Terraform output
- **Integration Issues:** Run integration tests manually
- **Documentation:** See DEPLOYMENT.md, COST_OPTIMIZATION.md

---

**Last Updated:** 2026-01-27
