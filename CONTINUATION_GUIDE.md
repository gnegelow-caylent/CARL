# CARL - Session Continuation Guide

**Last Updated:** 2026-01-27
**Session Status:** Feature Management System Completed

---

## Quick Context

CARL (Cloud Automated Risk & Compliance Logic) is an AI-powered AWS compliance bot that helps teams:
- Build compliant AWS infrastructure from scratch
- Monitor existing infrastructure for security/compliance issues
- Get AI-driven architecture recommendations
- Automate AWS Organizations and security service setup

### Current Architecture

```
Minimal Core (~$10-20/month)
    ↓
User chooses features in Slack (/carl hello)
    ↓
CARL triggers GitHub Actions
    ↓
Terraform deploys selected features
    ↓
User can enable/disable features anytime
```

---

## What Just Got Built (This Session)

### 1. Feature Management System
**Files:** `handlers/feature_manager.py`, `modules/*/main.tf`, `core/main.tf`

- 6 features with dependency resolution
- GitHub Actions integration for auto-deployment
- Modular Terraform with feature flags (count=0)
- All features available but disabled by default

### 2. Architecture Conversation Handler
**Files:** `architect_conversation.py`, `architecture_questions.py`

- Multi-turn conversations with contextual questions
- 5 categories: database, VPC, compute, storage, application
- 30+ questions with weighted scoring
- Intelligent recommendations based on use case, budget, team size

### 3. GitHub Actions Workflow
**File:** `.github/workflows/deploy-features.yml`

- Triggered by CARL via GitHub API
- Deploys features to dev/qa/prod
- Notifies CARL when complete

---

## Project Status

### ✅ Complete

| Component | Status | Files | Lines |
|-----------|--------|-------|-------|
| Core Infrastructure | ✅ | core/main.tf, variables.tf | 500+ |
| Feature Modules | ✅ | modules/*/main.tf | 800+ |
| Feature Manager | ✅ | feature_manager.py | 550 |
| Architect Conversation | ✅ | architect_conversation.py | 350 |
| Architecture Questions | ✅ | architecture_questions.py | 1200 |
| GitHub Actions Workflow | ✅ | deploy-features.yml | 250 |
| 58+ Architecture Patterns | ✅ | knowledge/*.py | 15000+ |
| Bootstrap Automation | ✅ | services/bootstrap/*.py | 3100+ |
| Foundation Builder | ✅ | services/foundation/*.py | 2500+ |
| Onboarding Handler | ✅ | handlers/onboarding.py | 386 |

### 🚧 Integration Needed (Next Steps)

1. **Wire up feature_manager to slack_router.py**
   - Add `/carl enable <feature>` handler
   - Add `/carl disable <feature>` handler
   - Add `/carl features` handler

2. **Wire up architect_conversation to slack_router.py**
   - Add `/carl architect <question>` handler
   - Add button click handlers for conversation flow

3. **Update onboarding.py to use FeatureManager**
   - Replace manual CloudFormation commands
   - Use feature_manager.enable_feature()

4. **Configure GitHub integration**
   - Set GITHUB_TOKEN environment variable
   - Set GITHUB_REPO environment variable
   - Add CARL_DEPLOYMENT_TOKEN to GitHub secrets

5. **Test end-to-end flow**
   - Deploy minimal core
   - Test `/carl hello` onboarding
   - Test feature enable/disable
   - Test architecture conversations

---

## How to Continue This Work

### If Starting a New Session

1. **Read the summary documents:**
   ```
   - FEATURE_MANAGEMENT_SUMMARY.md (detailed implementation)
   - COMPLETION_SUMMARY.md (overall project status)
   - COST_OPTIMIZATION.md (cost strategies)
   - DEPLOYMENT.md (deployment guide)
   ```

2. **Understand the architecture:**
   - Minimal core deploys first (~$10-20/month)
   - User chooses features during `/carl hello`
   - CARL triggers GitHub Actions to deploy features
   - Features can be enabled/disabled anytime

3. **Check current status:**
   ```bash
   cd /Users/gnegelow/Documents/CARL
   ls -la carl-app/src/handlers/
   ls -la carl-infrastructure/modules/
   ```

### Integration Points

**slack_router.py** needs these imports:
```python
from handlers.feature_manager import FeatureManager
from handlers.architect_conversation import ArchitectConversationHandler
from handlers.onboarding import OnboardingHandler
```

**Add command handlers:**
```python
# Feature management
if command == "/carl enable":
    feature_id = args[0]
    feature_manager = FeatureManager(config_table)
    return feature_manager.enable_feature(workspace_id, feature_id, user_id)

elif command == "/carl disable":
    feature_id = args[0]
    return feature_manager.disable_feature(workspace_id, feature_id, user_id)

elif command == "/carl features":
    return feature_manager.list_features(workspace_id)

# Architecture conversations
elif command == "/carl architect":
    question = " ".join(args)
    category = determine_category(question)
    architect_handler = ArchitectConversationHandler(config_table)
    return architect_handler.start_conversation(user_id, workspace_id, category, question)

# Onboarding
elif command == "/carl hello":
    onboarding = OnboardingHandler(config_table)
    if not onboarding.is_onboarding_complete(workspace_id):
        return onboarding.get_welcome_message(user_id)
```

**Add button action handlers:**
```python
# In handle_interactive_action()
if action_id == "onboarding_select_monitoring":
    onboarding = OnboardingHandler(config_table)
    return onboarding.handle_selection("monitoring", user_id, workspace_id)

elif action_id.startswith("architect_answer_"):
    # Parse: "category|question_id|answer"
    category, question_id, answer = value.split("|")
    architect_handler = ArchitectConversationHandler(config_table)
    return architect_handler.handle_answer(user_id, workspace_id, category, question_id, answer)

elif action_id == "feature_enable_with_deps":
    # Parse: "feature_id|dep1,dep2"
    feature_id, deps_str = value.split("|")
    dependencies = deps_str.split(",")
    feature_manager = FeatureManager(config_table)
    return feature_manager.enable_feature_with_deps(workspace_id, feature_id, dependencies, user_id)
```

---

## Testing Checklist

### Manual Testing

1. **Minimal Core Deployment**
   ```bash
   cd carl-infrastructure/core
   terraform init
   terraform apply -var="environment=dev"
   ```
   Expected: ~$10-20/month, no feature modules deployed

2. **Onboarding Flow**
   ```
   Slack: /carl hello
   Expected: Welcome message with 4 buttons
   Click: [1️⃣ Monitor]
   Expected: Deployment confirmation
   Click: [Auto-Deploy]
   Expected: GitHub Actions triggered, deployment in progress
   Wait 5-10 minutes
   Expected: "✅ Infrastructure Monitoring is now enabled"
   ```

3. **Feature Enable/Disable**
   ```
   Slack: /carl enable drift_detection
   Expected: "Cannot enable - missing dependency: monitoring"
   Click: [Yes, enable all]
   Expected: Both monitoring and drift_detection enabled

   Slack: /carl disable monitoring
   Expected: "Cannot disable - drift_detection depends on it"
   ```

4. **Architecture Conversation**
   ```
   Slack: /carl architect "What database should I use?"
   Expected: Question 1 of 7 with buttons
   Answer all 7 questions
   Expected: Recommendation with pros/cons, alternatives
   ```

5. **Feature List**
   ```
   Slack: /carl features
   Expected: List of all 6 features with status (enabled/disabled)
   ```

### Automated Testing

Create tests in `carl-app/tests/`:

```python
# test_feature_manager.py
def test_enable_feature_without_deps():
    manager = FeatureManager("test-table")
    result = manager.enable_feature("workspace1", "monitoring", "user1", "dev")
    assert "Deploying features" in result["blocks"][0]["text"]["text"]

def test_enable_feature_with_missing_deps():
    manager = FeatureManager("test-table")
    result = manager.enable_feature("workspace1", "drift_detection", "user1", "dev")
    assert "Missing dependencies" in result["blocks"][0]["text"]["text"]

# test_architect_conversation.py
def test_conversation_flow():
    handler = ArchitectConversationHandler("test-table")

    # Start conversation
    result = handler.start_conversation("user1", "workspace1", "database", "What DB?")
    assert "Question 1 of" in result["blocks"][0]["text"]["text"]

    # Answer questions
    result = handler.handle_answer("user1", "workspace1", "database", "use_case", "user_profiles")
    assert "Question 2 of" in result["blocks"][0]["text"]["text"]

    # ... answer all 7 questions

    # Get recommendation
    result = handler.give_recommendation("user1", "workspace1", "database")
    assert "Recommended:" in result["blocks"][1]["text"]["text"]
```

---

## Cost Monitoring

Track costs for each deployment profile:

| Profile | Features | Estimated Monthly Cost |
|---------|----------|------------------------|
| Minimal | Core only | $10-20 |
| Advisor | Core + Foundation | $20-40 |
| Monitor | Core + Monitoring + Reporting | $40-70 |
| Builder | Core + Bootstrap | $30-50 |
| Standard | Core + Monitoring + Bootstrap + Reporting | $60-100 |
| Full | All features enabled | $95-175 |

**Cost breakdown by service:**
- Lambda: $5-25/month (depends on invocations)
- Bedrock: $3-50/month (Haiku: $3-10, Sonnet: $15-50)
- DynamoDB: $1-30/month (on-demand, depends on features)
- S3: $1-15/month (lifecycle policies save 40-60%)
- API Gateway: $1-5/month (HTTP API is 70% cheaper than REST)
- CloudWatch: $0-5/month (7-day retention)

---

## Common Issues & Solutions

### Issue: GitHub Actions not triggered

**Symptom:** Feature deployment doesn't start

**Solution:**
1. Check GITHUB_TOKEN environment variable is set
2. Check GITHUB_REPO format is "owner/repo"
3. Verify token has `workflow` scope
4. Check Lambda logs: `aws logs tail /aws/lambda/carl-dev-api --follow`

### Issue: Terraform plan fails

**Symptom:** GitHub Actions workflow fails at plan step

**Solution:**
1. Check module paths are correct in core/main.tf
2. Verify all required variables are passed to modules
3. Check AWS credentials have necessary permissions
4. Review Terraform output in GitHub Actions logs

### Issue: Feature dependencies not resolved

**Symptom:** Can enable drift_detection without monitoring

**Solution:**
1. Check FEATURES definition in feature_manager.py
2. Verify dependencies list is correct
3. Check enable_feature() logic for dependency checking

### Issue: Architecture conversation stuck

**Symptom:** Questions don't advance after answering

**Solution:**
1. Check DynamoDB conversation state is being saved
2. Verify question_index is incrementing
3. Check button action_id format matches handler
4. Review Lambda logs for errors

---

## File Structure Reference

```
CARL/
├── carl-app/
│   └── src/
│       ├── handlers/
│       │   ├── slack_router.py          # Main entry point (needs integration)
│       │   ├── onboarding.py            # First-time setup (needs update)
│       │   ├── feature_manager.py       # ✅ NEW - Feature enable/disable
│       │   ├── architect_conversation.py # ✅ NEW - Multi-turn conversations
│       │   ├── bootstrap_commands.py    # Bootstrap Slack commands
│       │   └── baseline_commands.py     # Account baseline commands
│       ├── services/
│       │   ├── ai_architect.py          # AI recommendations
│       │   ├── bedrock_service.py       # Claude/Bedrock integration
│       │   ├── bootstrap/               # Organizations automation
│       │   ├── foundation/              # Guided infra builder
│       │   └── ...
│       ├── knowledge/
│       │   ├── architecture_questions.py # ✅ NEW - Question framework
│       │   ├── vpc_patterns.py          # VPC patterns
│       │   ├── database_patterns.py     # Database patterns
│       │   └── ... (26 pattern files)
│       └── utils/
├── carl-infrastructure/
│   ├── core/
│   │   ├── main.tf                      # ✅ UPDATED - Added feature modules
│   │   ├── variables.tf                 # ✅ UPDATED - Added feature flags
│   │   └── outputs.tf
│   └── modules/                         # ✅ NEW - All feature modules
│       ├── monitoring/
│       │   ├── main.tf                  # Findings, evidence, scanning
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── bootstrap/                   # Organizations automation
│       ├── reporting/                   # Compliance reports
│       ├── foundation/                  # Infrastructure builder
│       ├── drift/                       # Drift detection
│       └── remediation/                 # Auto-remediation
├── .github/
│   └── workflows/
│       ├── deploy-core.yml              # Core deployment
│       └── deploy-features.yml          # ✅ NEW - Feature deployment
└── docs/
    ├── FEATURE_MANAGEMENT_SUMMARY.md    # ✅ NEW - This session's work
    ├── CONTINUATION_GUIDE.md            # ✅ NEW - This file
    ├── COMPLETION_SUMMARY.md            # Overall project status
    ├── COST_OPTIMIZATION.md             # Cost strategies
    └── DEPLOYMENT.md                    # Deployment guide
```

---

## Key Design Decisions

### 1. Why count=0 instead of separate directories?

**Decision:** Use `count = var.enable_feature ? 1 : 0` in single Terraform codebase

**Rationale:**
- Single codebase easier to maintain
- Feature flags in variables.tf are clear
- GitHub Actions can enable/disable with simple variable changes
- No need to manage multiple Terraform state files

### 2. Why GitHub Actions instead of Lambda deploying directly?

**Decision:** Lambda triggers GitHub Actions, which runs Terraform

**Rationale:**
- Terraform state managed by GitHub/S3, not Lambda
- CI/CD pipeline (validation, security scanning) runs on every deployment
- Audit trail in GitHub Actions logs
- Manual approval gates for prod
- Lambda has 15-minute timeout, some deployments take longer

### 3. Why multi-turn conversations instead of one big form?

**Decision:** Ask 5-7 contextual questions with buttons, one at a time

**Rationale:**
- Better UX in Slack (buttons vs text input)
- Progressive disclosure (don't overwhelm)
- Can adjust later questions based on early answers
- Saves conversation state in DynamoDB with TTL

### 4. Why weighted scoring for recommendations?

**Decision:** Each question has weight 1-10, answers scored per option

**Rationale:**
- Some questions matter more (use_case: weight=10 vs team_experience: weight=5)
- Allows nuanced scoring (DynamoDB: simple_lookups=10, complex_joins=2)
- Transparent algorithm, not black-box AI
- Can tune weights based on feedback

### 5. Why DynamoDB for conversation state instead of Bedrock cache?

**Decision:** Save answers in DynamoDB with TTL

**Rationale:**
- Explicit state management
- Can resume conversations later
- TTL automatically cleans up (1 hour)
- No Bedrock API call costs for state
- Easy to query/debug

---

## Environment Variables Needed

### Lambda Environment Variables (core/main.tf)
```hcl
environment {
  variables = {
    ENVIRONMENT         = var.environment
    CONFIG_TABLE        = aws_dynamodb_table.config.name

    # Bedrock
    BEDROCK_MODEL_HAIKU  = "anthropic.claude-3-haiku-20240307-v1:0"
    BEDROCK_MODEL_SONNET = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    BEDROCK_REGION       = local.region

    # Slack
    SLACK_BOT_TOKEN_SSM     = "/${var.environment}/carl/slack/bot-token"
    SLACK_SIGNING_SECRET_SSM = "/${var.environment}/carl/slack/signing-secret"

    # GitHub (for feature deployment)
    GITHUB_TOKEN = var.github_token      # Set via terraform variable
    GITHUB_REPO  = var.github_repo       # "owner/repo"
  }
}
```

### GitHub Secrets (for workflows)

**Per Environment:**
```
AWS_ACCESS_KEY_ID_DEV
AWS_SECRET_ACCESS_KEY_DEV
SLACK_BOT_TOKEN_DEV
SLACK_SIGNING_SECRET_DEV

AWS_ACCESS_KEY_ID_QA
AWS_SECRET_ACCESS_KEY_QA
SLACK_BOT_TOKEN_QA
SLACK_SIGNING_SECRET_QA

AWS_ACCESS_KEY_ID_PROD
AWS_SECRET_ACCESS_KEY_PROD
SLACK_BOT_TOKEN_PROD
SLACK_SIGNING_SECRET_PROD
```

**Global:**
```
CARL_DEPLOYMENT_TOKEN  # For CARL to call /deployment-complete endpoint
SLACK_WEBHOOK_URL      # For prod deployment notifications
PROD_APPROVERS         # Comma-separated GitHub usernames
```

---

## Next Session Checklist

When starting a new session, check these items:

- [ ] Read FEATURE_MANAGEMENT_SUMMARY.md for detailed context
- [ ] Read this file (CONTINUATION_GUIDE.md) for quick reference
- [ ] Check `/Users/gnegelow/Documents/CARL` directory structure
- [ ] Review slack_router.py to understand current integration points
- [ ] Check if GitHub secrets are configured
- [ ] Review GitHub Actions workflows (.github/workflows/)
- [ ] Check for any test failures or deployment issues

**Current Priority:** Integration (wire up feature_manager and architect_conversation to slack_router.py)

---

## Success Metrics

How to know if this implementation is working:

1. **Minimal Core Deployment:** ~$10-20/month, no feature modules
2. **Feature Enable Works:** `/carl enable monitoring` triggers GitHub Actions
3. **Dependencies Resolved:** Can't enable drift without monitoring
4. **Onboarding Works:** `/carl hello` shows 4 options, deploys on selection
5. **Architecture Works:** Multi-turn conversation gives relevant recommendations
6. **Cost Optimized:** Using Haiku for simple queries, Sonnet for complex

---

## Contact & Support

- **Documentation:** /Users/gnegelow/Documents/CARL/docs/
- **Issues:** Create GitHub issue in carl repo
- **Architecture Questions:** Check architecture_questions.py for framework
- **Cost Questions:** Check COST_OPTIMIZATION.md

---

## Summary

This session completed the feature management and architecture guidance system. CARL can now:

✅ Deploy minimal core first (~$10-20/month)
✅ Let users choose features during onboarding
✅ Enable/disable features anytime with dependency resolution
✅ Trigger GitHub Actions for automated deployment
✅ Provide intelligent architecture recommendations through contextual questions
✅ Score options based on use case, budget, team size, and other factors

**Next step:** Wire up feature_manager and architect_conversation to slack_router.py, then test end-to-end.

All contextual information has been saved in:
- FEATURE_MANAGEMENT_SUMMARY.md (detailed)
- CONTINUATION_GUIDE.md (this file - quick reference)
- COMPLETION_SUMMARY.md (overall project)

Good luck with the integration! 🚀
