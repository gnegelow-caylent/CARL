# CARL Infrastructure Deployment Workflow

## Overview

All CARL-generated infrastructure code is deployed through a GitOps workflow using the `carl-infrastructure-deployments` GitHub repository. This ensures proper code review, validation, and audit trails for all infrastructure changes.

## Quick Start

### Generate Infrastructure Code

```
/carl build networking/standard-vpc
```

CARL will:
1. Generate Terraform code
2. Create a feature branch in GitHub
3. Commit the code to `deployments/users/{user-id}/{blueprint}/{timestamp}/`
4. Create a Pull Request to the `develop` branch
5. Post a summary to Slack with links to the PR

### Review in Slack

You'll receive a Slack message containing:
- **Summary**: Blueprint name, PR link, compliance notes
- **Thread**:
  - Full Terraform code (for small code < 3000 chars)
  - OR Summary with resource counts (for large code)
- **File Attachment**: Complete .tf file

### Review in GitHub

1. Click the PR link from the Slack message
2. GitHub Actions will automatically:
   - Validate Terraform syntax and format
   - Run security scans (tfsec, checkov)
   - Generate a Terraform plan
   - Post plan results to PR comments and Slack

3. Review the plan output:
   - Check what resources will be created
   - Verify compliance with security standards
   - Confirm estimated costs

### Deploy to Development

Once the PR is approved:

1. **Merge the PR** to the `develop` branch

2. **Trigger the apply workflow** manually:
   - Go to GitHub Actions
   - Select "Terraform Apply - Dev" workflow
   - Click "Run workflow"
   - Enter:
     - Deployment directory (shown in plan output)
     - Plan artifact name (format: `tfplan-dev-{SHA}`)
     - Your username (for audit trail)
   - Click "Run workflow"

3. **Monitor deployment**:
   - Watch the workflow run in GitHub Actions
   - Results will be posted to Slack

## Deployment Flow Diagram

```
/carl build networking/vpc
    ↓
Generate Terraform code
    ↓
Create GitHub branch: feature/u{user-id}-{blueprint}-{timestamp}
    ↓
Commit code to: deployments/users/{user-id}/{blueprint}/{timestamp}/
    ↓
Create Pull Request to develop branch
    ↓
Post to Slack:
  - Channel: Summary + compliance notes + GitHub link
  - Thread: Full code (small) OR summary (large)
  - File: .tf attachment
    ↓
GitHub Actions (automatic):
  - Validate Terraform format
  - Run security scans
  - Generate plan
  - Post plan to PR and Slack
    ↓
User reviews in GitHub → Approve PR
    ↓
Merge PR to develop
    ↓
User triggers apply workflow manually
    ↓
Deployment completes → Results posted to Slack
```

## Slack Code Display

CARL uses **adaptive code display** to handle both small and large Terraform files:

### Small Code (≤ 3,000 characters)
- Complete Terraform code displayed in Slack thread
- Syntax highlighted with ```terraform
- Easy to review directly in Slack

### Large Code (> 3,000 characters)
- Intelligent summary posted in thread showing:
  - Resource counts by type (e.g., `aws_vpc` × 1, `aws_subnet` × 4)
  - Data sources, modules, variables, outputs count
  - Top 3 compliance notes
  - Link to GitHub PR and file attachment
- Full code always available:
  - Download file attachment from Slack
  - View in GitHub PR

## Approval Process

Different environments require different approval levels:

| Environment | Approvals Required | Auto-Merge | Manual Apply |
|-------------|-------------------|------------|--------------|
| **Dev**     | 0                 | Allowed    | Required     |
| **QA**      | 1                 | No         | Required     |
| **Prod**    | 2                 | No         | Required + 30min wait |

## Environment Promotion

To promote infrastructure to QA or Production:

1. Create a PR from `develop` to `qa` (or `qa` to `main` for prod)
2. Get required approvals
3. Merge the PR
4. Run the corresponding apply workflow

## Terraform State Management

- **State Backend**: S3 bucket `carl-tfstate-{account-id}`
- **State Locking**: DynamoDB table `carl-tfstate-locks`
- **State Path**: `deployments/users/{user-id}/{blueprint}/{timestamp}/terraform.tfstate`
- **Encryption**: AWS KMS
- **Versioning**: Enabled

Each deployment has its own isolated state file.

## Common Scenarios

### Scenario 1: Simple VPC Deployment

```
/carl build networking/basic-vpc
```

1. CARL creates PR with VPC code
2. Review plan (1 VPC, 2 subnets, route tables, IGW)
3. Merge PR
4. Run apply workflow
5. VPC created in ~2 minutes

### Scenario 2: Large Multi-Resource Infrastructure

```
/carl build application/full-stack
```

1. CARL creates PR with 50+ resources
2. Slack shows summary instead of full code
3. Download .tf file or view in GitHub
4. Review plan carefully (multiple resource types)
5. Merge PR
6. Run apply workflow
7. Resources created in ~10-15 minutes

### Scenario 3: VPC with Custom CIDR

```
/carl build networking/custom-vpc
```

1. CARL shows modal to enter CIDR block
2. Enter CIDR (e.g., 10.1.0.0/16)
3. CARL creates PR with custom config
4. Review and deploy as usual

## Troubleshooting

### Issue: GitHub token expired

**Symptom**: Error posting to GitHub
**Solution**: Update the token in Secrets Manager:
```bash
aws secretsmanager update-secret \
  --secret-id /carl/dev/github-infra-token \
  --secret-string "ghp_new_token"
```

### Issue: Plan workflow fails

**Symptom**: Terraform validation errors
**Solution**:
1. Check the workflow logs in GitHub Actions
2. Common issues:
   - Invalid Terraform syntax
   - Security scan failures
   - AWS permissions missing

### Issue: Apply workflow fails

**Symptom**: Deployment fails during apply
**Solution**:
1. Check AWS permissions for the apply role
2. Verify state file isn't locked
3. Review Terraform error messages
4. If needed, manually unlock state:
   ```bash
   terraform force-unlock -force {lock-id}
   ```

### Issue: Can't find plan artifact

**Symptom**: Apply workflow can't download plan
**Solution**:
1. Verify the plan workflow completed successfully
2. Check artifact name matches format: `tfplan-dev-{SHA}`
3. Artifacts expire after 30 days

### Issue: Slack notifications not working

**Symptom**: No Slack messages from GitHub Actions
**Solution**:
1. Verify `SLACK_WEBHOOK_CARL` secret is set correctly
2. Test webhook manually:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test from CARL"}' \
     YOUR_WEBHOOK_URL
   ```

## Best Practices

### Code Review

- Always review the plan before merging
- Check for unexpected resource deletions (🔴 Destroy)
- Verify compliance notes are addressed
- Confirm estimated costs are acceptable

### Deployment

- Deploy during business hours for dev
- Deploy during maintenance windows for prod
- Keep PRs small and focused
- One blueprint per PR

### Security

- Never commit secrets or credentials
- Use AWS Secrets Manager for sensitive data
- Review security scan results
- Follow compliance notes from CARL

### State Management

- Never manually edit state files
- Use `terraform state` commands if needed
- Keep state files encrypted
- Backup state files regularly

## Additional Resources

- [GitHub Repository Setup](./INFRASTRUCTURE_REPO_SETUP.md)
- [CARL Slack Commands](./SLACK_COMMANDS.md)
- [Architecture Patterns](./ARCHITECTURE.md)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review GitHub Actions logs
3. Contact the platform team in #cloud-platform
4. File an issue in the CARL repository
