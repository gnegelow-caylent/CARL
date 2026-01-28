# GitHub App Authentication for CARL

## Why GitHub App Instead of Personal Access Token?

**Personal Access Tokens (PATs):**
- ❌ Never expire (security risk)
- ❌ Tied to a user account (breaks if user leaves)
- ❌ Broad permissions
- ❌ Hard to audit

**GitHub Apps:**
- ✅ Tokens expire automatically (1 hour)
- ✅ Not tied to any user
- ✅ Fine-grained repository permissions
- ✅ Better audit trail
- ✅ Industry best practice

## Quick Setup

### Prerequisites
- AWS CLI configured
- `jq` installed (`brew install jq` on macOS)
- Admin access to GitHub organization

### One-Command Setup

```bash
./scripts/setup-github-app.sh
```

This interactive script will:
1. Guide you through creating a GitHub App
2. Store credentials in AWS Secrets Manager
3. Configure Lambda environment variables

### Manual Setup (If Preferred)

#### Step 1: Create GitHub App

1. Go to: https://github.com/organizations/YOUR_ORG/settings/apps/new

2. Configure:
   - **Name**: CARL Infrastructure Bot
   - **Homepage URL**: https://github.com/YOUR_ORG/carl_infra
   - **Webhook**: Uncheck "Active"

3. **Repository permissions**:
   - Contents: **Read and write**
   - Pull requests: **Read and write**
   - Metadata: **Read-only** (auto-selected)

4. Click **Create GitHub App**

5. After creation:
   - Note the **App ID** (shown at top of page)
   - Scroll to **Private keys** section
   - Click **Generate a private key**
   - Download the `.pem` file

#### Step 2: Install the App

1. In GitHub App settings, click **Install App**
2. Select your organization
3. Choose **Only select repositories**
4. Select `carl_infra` repository
5. Click **Install**
6. Note the **Installation ID** from the URL:
   ```
   https://github.com/settings/installations/12345678
                                              ^^^^^^^^
                                         Installation ID
   ```

#### Step 3: Store Credentials in AWS

```bash
# Set variables
APP_ID="your-app-id"
INSTALLATION_ID="your-installation-id"
PRIVATE_KEY_PATH="path/to/downloaded-key.pem"
ENVIRONMENT="dev"  # or qa/prod

# Create JSON credentials
aws secretsmanager create-secret \
  --name "/carl/$ENVIRONMENT/github-app-credentials" \
  --description "GitHub App credentials for CARL" \
  --secret-string "$(jq -n \
    --arg app_id "$APP_ID" \
    --arg private_key "$(cat $PRIVATE_KEY_PATH)" \
    --arg installation_id "$INSTALLATION_ID" \
    '{app_id: $app_id, private_key: $private_key, installation_id: $installation_id}'
  )" \
  --region us-east-1
```

#### Step 4: Update Lambda Configuration

The Lambda will automatically use GitHub App if credentials are present:

```bash
# Verify configuration
aws lambda get-function-configuration \
  --function-name carl-dev-api \
  --region us-east-1 \
  --query 'Environment.Variables.GITHUB_APP_CREDENTIALS_SECRET'
```

Expected output:
```
"/carl/dev/github-app-credentials"
```

## How It Works

```
/carl build command
     ↓
Lambda invokes get_github_service()
     ↓
get_github_app_auth() reads credentials from Secrets Manager
     ↓
GitHubAppAuth generates JWT token (10 min validity)
     ↓
JWT exchanged for installation token (1 hour validity)
     ↓
Token cached and reused until expiration
     ↓
GitHub API calls use fresh token
     ↓
Token expires automatically (no cleanup needed)
```

## Architecture

```python
# In slack_router.py
def get_github_service():
    # Try GitHub App (preferred)
    github_app = get_github_app_auth()
    # Pass token provider function (not static token!)
    return GitHubService(
        github_app.get_installation_token,  # ← Callable, not string
        GITHUB_INFRA_OWNER,
        GITHUB_INFRA_REPO
    )
```

```python
# In github_service.py
class GitHubService:
    def __init__(self, token_or_provider, owner, repo):
        # Support both static token and token provider
        if callable(token_or_provider):
            self._token_provider = token_or_provider  # ← GitHub App
        else:
            self._static_token = token_or_provider    # ← Legacy PAT

    def _get_headers(self):
        # Get fresh token on every request
        token = self._static_token or self._token_provider()
        return {"Authorization": f"Bearer {token}"}
```

## Security Benefits

### Token Expiration
- **Installation tokens**: 1 hour TTL
- **JWT tokens**: 10 minutes TTL
- Tokens automatically regenerated as needed
- No manual rotation required

### Audit Trail
All actions appear in GitHub as:
```
CARL Infrastructure Bot (Bot)
    └─ Created pull request #123
    └─ Committed to branch feature/...
```

vs. Personal Access Token:
```
john.doe (User)
    └─ Created pull request #123
```

### Permission Scope
GitHub App has access to:
- ✅ `carl_infra` repository only
- ✅ Contents (read/write) - for branches and commits
- ✅ Pull requests (read/write) - for PRs
- ❌ No access to other repositories
- ❌ No access to organization settings
- ❌ No access to user data

## Troubleshooting

### "Authentication failed" Error

Check the credentials in Secrets Manager:
```bash
aws secretsmanager get-secret-value \
  --secret-id /carl/dev/github-app-credentials \
  --region us-east-1 \
  --query SecretString \
  --output text | jq .
```

Should contain:
```json
{
  "app_id": "123456",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "installation_id": "789012"
}
```

### "Installation not found" Error

Verify the app is installed on `carl_infra` repository:
1. Go to: https://github.com/apps/YOUR-APP-NAME/installations
2. Check that `carl_infra` is listed
3. Verify installation ID matches

### Token Generation Test

Test token generation manually:
```python
from services.github_app_service import GitHubAppAuth

auth = GitHubAppAuth(
    app_id="your-app-id",
    private_key=open("key.pem").read(),
    installation_id="your-installation-id"
)

token = auth.get_installation_token()
print(f"Token: {token[:20]}...")  # First 20 chars
```

## Migration from PAT to GitHub App

If you're currently using a Personal Access Token:

1. Set up GitHub App (follow steps above)
2. Deploy Lambda with updated code
3. Lambda automatically tries GitHub App first
4. If GitHub App fails, falls back to PAT
5. Once confirmed working, remove PAT secret:
   ```bash
   aws secretsmanager delete-secret \
     --secret-id /carl/dev/github-infra-token \
     --region us-east-1
   ```

## Credential Rotation

To rotate the private key:

1. Generate new key in GitHub App settings
2. Download new `.pem` file
3. Re-run setup script or manually update secret:
   ```bash
   aws secretsmanager update-secret \
     --secret-id /carl/dev/github-app-credentials \
     --secret-string "$(jq -n \
       --arg app_id "$APP_ID" \
       --arg private_key "$(cat new-key.pem)" \
       --arg installation_id "$INSTALLATION_ID" \
       '{app_id: $app_id, private_key: $private_key, installation_id: $installation_id}'
     )"
   ```
4. No Lambda restart needed - new key used on next token generation

## Additional Resources

- [GitHub Apps Documentation](https://docs.github.com/en/apps)
- [JWT Token Format](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app)
- [Installation Tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)
