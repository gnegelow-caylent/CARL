# CARL Jira Integration

**Status:** 📋 Design Phase | January 28, 2026

Comprehensive Jira Cloud integration for CARL with bi-directional sync across multiple projects.

---

## 🎯 Overview

CARL will integrate with Jira Cloud to track:
- **Phase 1 (Priority):** Security findings, risk exceptions, configuration drift, CARL feature requests, infrastructure PRs
- **Phase 2 (Later):** Evidence collection, deployment tracking

### Jira Projects Structure

| Project Key | Project Name | Purpose |
|-------------|--------------|---------|
| **CARLSEC** | CARL Security & Compliance | Security findings, exceptions, drift detection |
| **CARLDEV** | CARL Feature Development | Feature requests, bugs, enhancements for CARL itself |
| **CARLINFRA** | Infrastructure Changes | GitHub PRs for infrastructure deployments |

---

## 📊 Phase 1: Priority Features

### 1.1 Security Findings (CARLSEC)

**Flow:** Security Hub Finding → CARL Detection → Jira Ticket

**Issue Type:** `Security Finding`

**Fields:**
- **Summary:** `[{severity}] {finding_title}`
- **Description:** Finding details, affected resources, SOC 2 controls
- **Priority:** Critical/High/Medium/Low (mapped from severity)
- **Labels:** `security`, `soc2`, `{service}`, `{control-id}`
- **Components:** GuardDuty, Security Hub, Config, Inspector
- **Custom Fields:**
  - `AWS Account ID`
  - `AWS Region`
  - `Resource ARN`
  - `Finding ID` (Security Hub)
  - `SOC 2 Controls` (e.g., CC6.1, CC7.2)
  - `Compliance Status` (Compliant/Non-Compliant)
  - `First Detected`
  - `Last Seen`

**Workflow:**
```
Open → In Remediation → Remediation Complete → Verification → Closed
  ↓          ↓                    ↓                  ↓
Won't Fix  Reopened          Failed Verification  Reopened
```

**Automation:**
- **CARL → Jira:** Create ticket when finding first detected
- **CARL → Jira:** Update "Last Seen" field when finding still active
- **CARL → Jira:** Move to "Closed" when finding resolved in AWS
- **Jira → CARL:** "Won't Fix" triggers risk exception creation in CARL
- **Jira → CARL:** "In Remediation" updates CARL tracking

**Slack Integration:**
```
/carl findings [severity]
  → Shows findings with Jira ticket links
  → Button: "View in Jira" → Opens Jira ticket
  → Button: "Request Exception" → Creates exception in Jira

/carl finding {id} link-jira
  → Manually link finding to existing Jira ticket
```

---

### 1.2 Risk Exceptions (CARLSEC)

**Flow:** User Request → CARL → Jira Approval Workflow → CARL Exception

**Issue Type:** `Risk Exception`

**Fields:**
- **Summary:** `Exception Request: {finding_title}`
- **Description:** Business justification, compensating controls, expiration date
- **Priority:** Based on risk severity
- **Labels:** `exception`, `risk-acceptance`, `{control-id}`
- **Custom Fields:**
  - `Requested By`
  - `Business Justification`
  - `Compensating Controls`
  - `Expiration Date`
  - `Approved By`
  - `Approval Date`
  - `Related Finding` (link to Security Finding)
  - `Risk Level` (High/Medium/Low)

**Workflow:**
```
Requested → Under Review → Approved → Active → Expiring (30 days) → Expired
              ↓              ↓           ↓
            Denied       Denied      Renewed
```

**Automation:**
- **CARL → Jira:** Create exception request from Slack
- **Jira → CARL:** Approval triggers exception creation in CARL
- **Jira → CARL:** Denial notifies user in Slack
- **CARL → Jira:** 30 days before expiration, move to "Expiring"
- **CARL → Jira:** On expiration, move to "Expired" and notify

**Slack Integration:**
```
/carl exception request
  → Opens modal to collect justification
  → Creates Jira ticket
  → Notifies approvers in Slack with Jira link

/carl exception list
  → Shows exceptions with Jira links
  → Shows expiration status

Jira Approval:
  → Comment in Jira triggers Slack notification to requestor
  → Approval creates exception in CARL DynamoDB
  → Denial notifies in Slack
```

---

### 1.3 Configuration Drift (CARLSEC)

**Flow:** CARL Drift Detection → Jira Ticket → Remediation → Verification

**Issue Type:** `Configuration Drift`

**Fields:**
- **Summary:** `Drift Detected: {resource_type} - {resource_id}`
- **Description:** Expected vs actual configuration, drift details
- **Priority:** Based on compliance impact
- **Labels:** `drift`, `configuration`, `{service}`, `{environment}`
- **Custom Fields:**
  - `Resource Type`
  - `Resource ID`
  - `Expected State`
  - `Actual State`
  - `Drift Type` (Manual Change/Unauthorized/Unknown)
  - `Detected Date`
  - `Impact Level` (Critical/High/Medium/Low)
  - `Environment` (dev/staging/prod)

**Workflow:**
```
Detected → Acknowledged → Remediation Planned → Remediated → Verified → Closed
   ↓            ↓                ↓
Expected    Expected         Reopened
```

**Automation:**
- **CARL → Jira:** Create ticket when drift detected
- **CARL → Jira:** Update with latest drift state
- **Jira → CARL:** "Expected" triggers drift acknowledgment in CARL
- **JIRA → CARL:** "Remediated" triggers verification scan
- **CARL → Jira:** Move to "Closed" when verified fixed

**Slack Integration:**
```
/carl drift scan
  → Scans for drift
  → Creates Jira tickets for new drift
  → Shows summary with Jira links

/carl drift status
  → Shows all drift with Jira ticket status
  → Button: "View in Jira"
  → Button: "Acknowledge" (if expected)

/carl drift acknowledge {id}
  → Moves Jira ticket to "Expected"
  → Adds comment with acknowledgment reason
```

---

### 1.4 CARL Feature Requests (CARLDEV)

**Flow:** User Request → Jira Backlog → Prioritization → Development → Done

**Issue Type:** `Feature Request`, `Bug`, `Enhancement`

**Fields:**
- **Summary:** Feature/bug title
- **Description:** Detailed requirements
- **Priority:** Must Have/Should Have/Nice to Have
- **Labels:** `feature`, `bug`, `enhancement`, `user-request`
- **Components:** Security, Networking, AI, Slack, Infrastructure
- **Custom Fields:**
  - `Requested By`
  - `Use Case`
  - `Expected Benefit`
  - `Complexity` (Small/Medium/Large)
  - `User Votes` (count of users who want this)

**Workflow:**
```
Backlog → Prioritized → Planned → In Development → Code Review → Testing → Done
   ↓          ↓            ↓
Won't Do  Duplicate    Blocked
```

**Automation:**
- **CARL → Jira:** Create from Slack command
- **CARL → Jira:** Track user votes
- **Jira → CARL:** "Done" triggers release notes update
- **Jira → CARL:** "In Development" notifies requestor

**Slack Integration:**
```
/carl feature request
  → Opens modal to describe feature
  → Creates Jira ticket in CARLDEV
  → Returns ticket link
  → Users can vote on existing requests

/carl feature vote {ticket-id}
  → Increments vote count in Jira
  → Notifies CARL team

/carl features status
  → Shows top requested features
  → Shows what's in development
  → Links to Jira tickets
```

---

### 1.5 Infrastructure Changes / PRs (CARLINFRA)

**Flow:** GitHub PR Created → Jira Ticket → Review → Merge → Verification

**Issue Type:** `Infrastructure Change`

**Fields:**
- **Summary:** `PR #{pr_number}: {pr_title}`
- **Description:** PR description, changes, resources affected
- **Priority:** Based on environment (prod = high)
- **Labels:** `infrastructure`, `terraform`, `{environment}`, `{service}`
- **Custom Fields:**
  - `GitHub PR URL`
  - `PR Number`
  - `Author`
  - `Repository`
  - `Branch`
  - `Environment` (dev/staging/prod)
  - `Resources Changed` (count)
  - `Terraform Plan` (summary)
  - `Deployment Status`

**Workflow:**
```
Proposed → Review Requested → Approved → Merged → Deployment Planned → Deployed → Verified → Closed
   ↓            ↓               ↓           ↓
Rejected    Changes Req    Closed      Failed
```

**Automation:**
- **GitHub → Jira:** PR creation triggers Jira ticket
- **GitHub → Jira:** PR comments sync to Jira comments
- **Jira → GitHub:** Approval adds approval in GitHub PR
- **Jira → GitHub:** Rejection closes PR
- **GitHub → Jira:** Merge moves to "Merged"
- **CARL → Jira:** Deployment results update ticket

**Slack Integration:**
```
GitHub PR Created:
  → Jira ticket auto-created
  → Slack notification in #infra channel with Jira link

/carl infra pr {pr-number}
  → Shows PR status
  → Shows Jira ticket status
  → Shows terraform plan summary

Jira Approval/Rejection:
  → Syncs to GitHub PR
  → Notifies author in Slack
```

---

## 🔐 Authentication & Security

### Jira Cloud API Authentication

**Method:** API Token (most secure for Jira Cloud)

**Setup:**
1. Create Jira service account: `carl-bot@your-domain.com`
2. Generate API token for service account
3. Store in AWS Secrets Manager: `/carl/prod/jira-api-token`
4. Store Jira instance URL: `/carl/prod/jira-url`

**IAM Permissions:**
```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:*:*:secret:/carl/prod/jira-*"
}
```

**Jira API Access:**
```python
import requests
from base64 import b64encode

# Credentials from Secrets Manager
email = "carl-bot@your-domain.com"
api_token = get_secret("/carl/prod/jira-api-token")
jira_url = get_secret("/carl/prod/jira-url")

# Authentication
auth = b64encode(f"{email}:{api_token}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Content-Type": "application/json"
}

# Example API call
response = requests.post(
    f"{jira_url}/rest/api/3/issue",
    headers=headers,
    json=issue_data
)
```

**Security Best Practices:**
- ✅ API token stored in Secrets Manager (encrypted)
- ✅ Least privilege Jira permissions (service account only has needed access)
- ✅ Token rotation every 90 days (automated)
- ✅ All API calls logged in CloudWatch
- ✅ Rate limiting (max 100 requests/minute)

---

## 🔄 Bi-Directional Sync

### CARL → Jira (Push)

**When CARL updates Jira:**
- Finding detected → Create/update issue
- Finding resolved → Close issue
- Drift detected → Create issue
- Drift acknowledged → Update status
- Exception expiring → Update status
- User votes on feature → Increment votes

**Implementation:**
```python
class JiraService:
    def create_security_finding(self, finding: dict):
        # Create Jira issue from finding

    def update_finding_status(self, finding_id: str, status: str):
        # Update Jira issue status

    def create_exception_request(self, exception: dict):
        # Create exception request in Jira

    def create_drift_ticket(self, drift: dict):
        # Create drift ticket
```

### Jira → CARL (Pull via Webhooks)

**When Jira updates CARL:**
- Issue status changed → Update CARL
- Comment added → Sync to CARL/Slack
- Issue approved/denied → Trigger CARL action
- Custom field updated → Sync to CARL

**Webhook Setup:**
```
Jira Webhook Configuration:
URL: https://api.your-domain.com/carl/jira-webhook
Events:
  - Issue Created
  - Issue Updated
  - Issue Deleted
  - Comment Created
  - Comment Updated

JQL Filter: project in (CARLSEC, CARLDEV, CARLINFRA)
```

**Implementation:**
```python
@app.route('/carl/jira-webhook', methods=['POST'])
def jira_webhook():
    payload = request.json
    event_type = payload.get('webhookEvent')

    if event_type == 'jira:issue_updated':
        handle_issue_updated(payload)
    elif event_type == 'comment_created':
        handle_comment_created(payload)

    return {"status": "ok"}

def handle_issue_updated(payload):
    issue = payload['issue']
    project = issue['fields']['project']['key']

    if project == 'CARLSEC':
        sync_security_finding(issue)
    elif project == 'CARLDEV':
        sync_feature_request(issue)
```

---

## 📁 Jira Project Configuration

### CARLSEC (Security & Compliance)

**Issue Types:**
- Security Finding
- Risk Exception
- Configuration Drift

**Custom Fields:**
```
AWS Account ID (text)
AWS Region (select: us-east-1, us-west-2, etc.)
Resource ARN (text)
Finding ID (text)
SOC 2 Controls (multi-select: CC6.1, CC6.5, CC7.2, etc.)
Compliance Status (select: Compliant, Non-Compliant, Exception)
First Detected (datetime)
Last Seen (datetime)
Requested By (user picker)
Business Justification (textarea)
Compensating Controls (textarea)
Expiration Date (date)
Approved By (user picker)
Risk Level (select: High, Medium, Low)
Resource Type (text)
Expected State (textarea)
Actual State (textarea)
Drift Type (select: Manual Change, Unauthorized, Unknown)
Impact Level (select: Critical, High, Medium, Low)
Environment (select: dev, staging, prod)
```

**Workflows:**
- Security Finding: 8 states
- Risk Exception: 7 states
- Configuration Drift: 7 states

**Permissions:**
- CARL Bot: Create, update, transition issues
- Security Team: All permissions
- Developers: View, comment, transition (limited)
- Auditors: View only

---

### CARLDEV (Feature Development)

**Issue Types:**
- Feature Request
- Bug
- Enhancement

**Custom Fields:**
```
Requested By (user picker)
Use Case (textarea)
Expected Benefit (textarea)
Complexity (select: Small, Medium, Large)
User Votes (number)
Affected Users (number)
```

**Workflows:**
- Standard development workflow (10 states)

**Permissions:**
- CARL Bot: Create, update issues
- CARL Team: All permissions
- All Users: Create, view, vote

---

### CARLINFRA (Infrastructure Changes)

**Issue Types:**
- Infrastructure Change

**Custom Fields:**
```
GitHub PR URL (url)
PR Number (number)
Author (user picker)
Repository (text)
Branch (text)
Environment (select: dev, staging, prod)
Resources Changed (number)
Terraform Plan (textarea)
Deployment Status (select: Pending, In Progress, Success, Failed)
```

**Workflows:**
- Infrastructure change workflow (9 states)

**Permissions:**
- CARL Bot: Create, update, transition
- Infrastructure Team: All permissions
- Developers: View, comment

---

## 🛠️ Implementation Plan

### Phase 1A: Core Jira Service (Week 1)

**Deliverables:**
- `jira_service.py` - Core Jira API integration
- Authentication with API tokens
- Basic CRUD operations (create, read, update issues)
- Error handling and retry logic
- Rate limiting
- CloudWatch logging

**Files to Create:**
```
carl-app/src/services/jira_service.py
carl-app/src/services/jira_webhook_handler.py
carl-infrastructure/core/secrets.tf (Jira API token)
```

**Testing:**
- Unit tests for Jira API calls
- Integration tests with test Jira instance
- Error handling tests

---

### Phase 1B: Security Findings Integration (Week 2)

**Deliverables:**
- Security findings → Jira tickets
- Bi-directional sync for findings
- Slack commands with Jira links
- Finding resolution closes Jira tickets

**Updates:**
- Modify `slack_router.py` - Add Jira links to findings
- Create `jira_security_sync.py` - Sync logic
- Update DynamoDB schema - Add jira_ticket_id field

**Testing:**
- Create finding → Verify Jira ticket created
- Resolve finding in AWS → Verify Jira ticket closed
- Update Jira ticket → Verify CARL updated

---

### Phase 1C: Risk Exceptions Integration (Week 3)

**Deliverables:**
- Exception requests create Jira tickets
- Approval workflow in Jira
- Jira approval triggers CARL exception
- Expiration notifications

**Updates:**
- Modify `exception_manager.py` - Add Jira integration
- Create Jira workflows for exceptions
- Slack notifications for approvals/denials

**Testing:**
- Request exception → Verify Jira ticket
- Approve in Jira → Verify CARL exception created
- Denial in Jira → Verify Slack notification
- Expiration → Verify Jira status update

---

### Phase 1D: Configuration Drift Integration (Week 4)

**Deliverables:**
- Drift detection creates Jira tickets
- Acknowledgment workflow
- Remediation tracking
- Verification automation

**Updates:**
- Modify `drift_detector.py` - Add Jira integration
- Slack commands show Jira links
- Automated drift verification

**Testing:**
- Detect drift → Verify Jira ticket
- Acknowledge drift → Verify Jira status
- Remediate → Verify closed in Jira

---

### Phase 1E: Feature Requests Integration (Week 5)

**Deliverables:**
- Feature request Slack command
- Vote tracking
- Development status updates
- Release notes integration

**Updates:**
- New Slack command `/carl feature request`
- New Slack command `/carl feature vote`
- Vote tracking in Jira

**Testing:**
- Create feature request → Verify Jira ticket
- Vote on feature → Verify count incremented
- Move to "In Development" → Verify Slack notification

---

### Phase 1F: Infrastructure PR Integration (Week 6)

**Deliverables:**
- GitHub webhook → Jira ticket creation
- PR comments sync to Jira
- Jira approval → GitHub approval
- Deployment tracking

**Updates:**
- GitHub webhook handler
- Jira ↔ GitHub sync service
- Terraform plan embedding in Jira

**Testing:**
- Create PR → Verify Jira ticket
- Add PR comment → Verify Jira comment
- Approve in Jira → Verify GitHub approval
- Merge PR → Verify Jira status

---

## 📊 Jira Dashboard & Reports

### Security Dashboard (CARLSEC)

**Widgets:**
- Open findings by severity (pie chart)
- Findings by SOC 2 control (bar chart)
- Mean time to remediation (line chart)
- Exception requests pending approval (number)
- Expiring exceptions (next 30 days) (table)
- Drift by environment (pie chart)
- Top 10 most drifted resources (table)

### Development Dashboard (CARLDEV)

**Widgets:**
- Top requested features by votes (table)
- Features in development (list)
- Bugs by priority (pie chart)
- Average time to resolution (number)
- Recently completed features (list)

### Infrastructure Dashboard (CARLINFRA)

**Widgets:**
- Open PRs by environment (bar chart)
- Deployment success rate (percentage)
- Average PR review time (number)
- Failed deployments (list)
- PRs pending approval (table)

---

## 🎯 Success Metrics

### Tracking

**Security Findings:**
- Average time to create Jira ticket: <1 minute
- Bi-directional sync success rate: >99%
- Finding resolution accuracy: >95%

**Risk Exceptions:**
- Exception request to approval time: <48 hours
- Expiration notification success: 100%
- Exception compliance tracking: 100%

**Configuration Drift:**
- Drift to Jira ticket time: <5 minutes
- False positive rate: <5%
- Remediation tracking accuracy: >95%

**Feature Requests:**
- User adoption rate: >50% of users submit requests
- Vote tracking accuracy: 100%
- Feature delivery time: Track and trend

**Infrastructure Changes:**
- PR to Jira sync time: <1 minute
- Comment sync accuracy: 100%
- Deployment tracking: 100%

---

## 💰 Cost Estimate

### Jira Cloud Costs

**Assumptions:**
- 25 users
- 3 projects
- Standard plan

**Costs:**
- Jira Cloud Standard: $7.75/user/month = $194/month
- API calls: Included in plan
- Storage: Included in plan

**CARL Infrastructure Costs:**
- Jira webhook Lambda: ~$0.20/month (minimal invocations)
- Secrets Manager: $0.40/month (1 secret)
- CloudWatch logs: ~$1/month

**Total: ~$195-200/month**

---

## 🔮 Phase 2: Future Features

### Evidence Collection (Month 2)

- Evidence items → Jira attachments
- Evidence coverage tracking
- Audit report generation with Jira links

### Deployment Tracking (Month 2)

- Detailed deployment logs in Jira
- Rollback tracking
- Deployment analytics

---

## 📚 Documentation

**User Guides:**
- How to request exceptions in Jira
- How to vote on features
- How to link PRs to Jira tickets

**Admin Guides:**
- Jira project setup instructions
- Webhook configuration
- Custom field setup
- Workflow customization

**Developer Guides:**
- Jira API integration guide
- Webhook handler implementation
- Testing Jira integration

---

## 🚀 Getting Started

### Prerequisites

1. **Jira Cloud Instance**
   - Create instance at atlassian.com
   - Choose Standard plan ($7.75/user/month)

2. **Create Projects**
   - CARLSEC (Security & Compliance)
   - CARLDEV (Feature Development)
   - CARLINFRA (Infrastructure Changes)

3. **Service Account**
   - Email: `carl-bot@your-domain.com`
   - Generate API token
   - Store in AWS Secrets Manager

4. **Configure Webhooks**
   - URL: `https://api.your-domain.com/carl/jira-webhook`
   - Events: Issue created, updated, deleted, commented
   - JQL filter: `project in (CARLSEC, CARLDEV, CARLINFRA)`

5. **AWS Infrastructure**
   - Deploy Jira webhook Lambda
   - Configure Secrets Manager
   - Update IAM roles

### Initial Testing

```bash
# Test Jira connectivity
/carl jira test

# Create test finding
/carl jira test-finding

# Create test exception
/carl jira test-exception

# Create test drift
/carl jira test-drift
```

---

## ✅ Checklist

### Setup Checklist

- [ ] Jira Cloud instance created
- [ ] 3 projects created (CARLSEC, CARLDEV, CARLINFRA)
- [ ] Custom fields configured
- [ ] Workflows configured
- [ ] Service account created
- [ ] API token generated
- [ ] API token stored in Secrets Manager
- [ ] Webhooks configured
- [ ] Lambda deployed for webhooks
- [ ] IAM roles updated
- [ ] Initial testing completed

### Development Checklist

- [ ] jira_service.py created
- [ ] jira_webhook_handler.py created
- [ ] Security findings integration
- [ ] Risk exceptions integration
- [ ] Configuration drift integration
- [ ] Feature requests integration
- [ ] Infrastructure PR integration
- [ ] Bi-directional sync tested
- [ ] Slack commands updated
- [ ] Documentation complete

---

*Last Updated: January 28, 2026*
