# CARL - Future Features & Roadmap

This document tracks potential future features and enhancements for CARL.

---

## 🤖 AI-Generated Compliance Documentation

**Status:** 💡 Idea / Not Started
**Priority:** High
**Estimated Effort:** 4-6 weeks
**Value:** Increase evidence coverage from 23% to 70-80%

### Problem Statement

CARL currently automates **10 of 43 SOC 2 controls (23.3%)** through AWS API scanning. The remaining **33 controls (76.7%)** are organizational/governance controls that require manual documentation:

- Policies (security, HR, ethics, change management)
- Procedures (incident response, access review, risk assessment)
- Process documentation (vendor management, business continuity)
- Meeting artifacts (board oversight, security committee)
- Training materials
- Records (risk register, vendor assessments)

**Current state:** Users must write these documents themselves or hire consultants ($50k-$150k).

**Proposed solution:** Use Claude AI (via Bedrock) to auto-generate customized compliance documentation.

---

## What CARL Could Auto-Generate

### ✅ Tier 1: Fully Generatable (High Confidence)

These can be **completely generated** by AI with minimal user input:

#### 1. **Policy Documents** (10-15 policies)
- **Security Policy** (CC2.3, CC5.3)
  - Information security program overview
  - Security roles and responsibilities
  - Classification of information
  - Acceptable use policy
  - Password requirements
  - Encryption standards

- **Access Control Policy** (CC6.1, CC6.2, CC6.3, CC6.4, CC6.6)
  - User provisioning process
  - Access approval workflow
  - MFA requirements
  - Access review procedures (quarterly)
  - Deprovisioning process

- **Change Management Policy** (CC8.1)
  - Change request process
  - Testing and approval requirements
  - Emergency change procedures
  - Rollback procedures

- **Incident Response Policy** (CC7.3)
  - Incident classification levels
  - Response team roles
  - Escalation procedures
  - Communication protocols
  - Post-incident review process

- **Data Protection Policy** (C1.1, C1.2)
  - Data classification scheme
  - Encryption requirements
  - Data retention schedules
  - Data destruction procedures

- **Vendor Management Policy** (CC9.1)
  - Vendor assessment criteria
  - Contract requirements
  - Ongoing monitoring process
  - Vendor offboarding

- **Business Continuity Policy** (CC9.2, CC7.4, CC7.5)
  - Recovery time objectives (RTO)
  - Recovery point objectives (RPO)
  - Backup procedures
  - Disaster recovery plan outline

- **Risk Management Policy** (CC3.2, CC3.3, CC3.4)
  - Risk assessment methodology
  - Risk rating scale
  - Risk acceptance criteria
  - Risk register maintenance

- **Code of Conduct** (CC1.1)
  - Ethical standards
  - Conflicts of interest
  - Confidentiality
  - Reporting violations

- **HR Security Policy** (CC1.4)
  - Background checks
  - Security awareness training
  - Onboarding/offboarding security
  - Disciplinary procedures

**Input needed from user:**
- Company name
- Industry
- Data types handled
- Regulatory requirements (HIPAA, PCI, etc.)
- AWS account details (auto-detected)

**What CARL generates:**
- Complete policy document (Word/PDF)
- Tailored to company's AWS architecture
- References actual AWS resources (detected from account)
- Ready for review and approval

**Example prompt to Claude:**
```
Generate a comprehensive Access Control Policy for:
- Company: Acme Corp (SaaS company)
- AWS Account: 123456789012
- Detected resources: IAM Identity Center, 15 IAM users, 3 S3 buckets
- Compliance: SOC 2 Type II
- Requirements: CC6.1, CC6.2, CC6.3, CC6.4, CC6.6

Include:
1. User provisioning process
2. MFA requirements (current status: 8/15 users have MFA)
3. Access review procedures
4. Deprovisioning process
5. References to actual AWS services
```

---

#### 2. **Procedure Documents** (8-10 procedures)

Step-by-step procedures that can be auto-generated:

- **Access Review Procedure** (CC6.6)
  - Quarterly review checklist
  - Review form template
  - Approval workflow
  - Documentation requirements

- **Incident Response Runbook** (CC7.3)
  - Detection and triage steps
  - Investigation procedures
  - Containment actions
  - Recovery steps
  - Post-mortem template

- **Change Management Procedure** (CC8.1)
  - Change request form
  - Testing checklist
  - Approval matrix
  - Deployment steps
  - Rollback procedure

- **Vulnerability Management Procedure** (CC7.1)
  - Scanning schedule
  - Severity classification
  - Remediation SLAs
  - Patching process

- **Backup and Recovery Procedure** (CC7.4, CC7.5)
  - Backup schedule
  - Testing procedures
  - Recovery steps
  - Verification checklist

- **User Onboarding Procedure** (CC6.2)
  - Access request form
  - Approval workflow
  - Account provisioning steps
  - Training requirements

- **User Offboarding Procedure** (CC6.3)
  - Termination checklist
  - Access revocation steps
  - Equipment return
  - Knowledge transfer

**What CARL generates:**
- Step-by-step procedures
- Checklists and forms
- AWS-specific commands (where applicable)
- Responsible parties (customizable)

---

#### 3. **Templates and Forms** (10-15 templates)

Pre-filled templates ready to use:

- **Risk Assessment Template** (CC3.2)
  - Risk identification form
  - Impact/likelihood matrix
  - Mitigation plan template

- **Vendor Security Questionnaire** (CC9.1)
  - SOC 2-focused questions
  - Assessment scoring rubric
  - Follow-up action plan

- **Access Review Form** (CC6.6)
  - User list (auto-populated from AWS IAM)
  - Review checklist
  - Sign-off section

- **Change Request Form** (CC8.1)
  - Change details
  - Risk assessment
  - Rollback plan
  - Approval signatures

- **Incident Report Template** (CC7.3)
  - Incident details
  - Timeline
  - Impact assessment
  - Lessons learned

- **Business Continuity Test Plan** (CC9.2)
  - Test scenarios
  - Success criteria
  - Results documentation

**What CARL generates:**
- Pre-formatted Word/PDF templates
- Auto-filled with company data
- AWS resource references (where applicable)

---

#### 4. **Training Materials** (5-8 modules)

Security awareness content:

- **Security Awareness Training Outline** (CC1.4)
  - Phishing awareness
  - Password management
  - Data handling
  - Incident reporting
  - AWS security basics

- **SOC 2 Awareness for Employees**
  - What is SOC 2?
  - Employee responsibilities
  - Key policies
  - How to report issues

**What CARL generates:**
- Training slides (PDF)
- Quiz questions
- Acknowledgment forms

---

### ⚠️ Tier 2: Partially Generatable (Requires User Input)

CARL can generate **templates** but users must **fill in actual data**:

#### 5. **Process Documentation**

- **Organizational Structure** (CC1.3)
  - CARL generates: Org chart template with roles
  - User provides: Actual names and reporting structure

- **Committee Charter** (CC1.2, CC4.1)
  - CARL generates: Security committee charter template
  - User provides: Actual committee members, meeting frequency

#### 6. **Records and Registers**

- **Risk Register** (CC3.2)
  - CARL generates: Risk register spreadsheet template
  - CARL pre-fills: AWS-detected risks (Security Hub findings)
  - User provides: Business risks, mitigation owners, dates

- **Vendor List** (CC9.1)
  - CARL generates: Vendor tracking spreadsheet
  - CARL pre-fills: AWS Marketplace vendors (if detectable)
  - User provides: Other vendors, contracts, assessment dates

- **Asset Inventory** (CC6.7)
  - CARL generates: Asset tracking template
  - CARL pre-fills: AWS resources (EC2, RDS, S3, etc.)
  - User provides: On-prem assets, software licenses

---

### ❌ Tier 3: Cannot Generate (Must Be Created by User)

These require **actual company-specific activities** that AI cannot create:

#### 7. **Meeting Artifacts**
- Board meeting minutes (CC1.2)
- Security committee meeting notes
- Risk review meeting records

**Why not generatable:** These document actual meetings that happened

#### 8. **Audit Records**
- Background check confirmations (CC1.4)
- Training completion records (CC1.4)
- Access review results (CC6.6)
- Vendor assessment results (CC9.1)

**Why not generatable:** These are proof of activities performed

#### 9. **Contractual Documents**
- Vendor contracts (CC9.1)
- Customer agreements
- NDAs

**Why not generatable:** Legal documents requiring negotiation

#### 10. **Historical Records**
- Incident reports (past incidents) (CC7.3)
- Post-mortem reports
- Audit findings and remediation

**Why not generatable:** Historical events that occurred

---

## Proposed Implementation

### Phase 1: Policy Generator (2 weeks)

**Slash command:**
```
/carl generate policy <policy-type>
/carl generate policy access-control
/carl generate policy incident-response
/carl generate policy all
```

**What it does:**
1. Scans AWS account for current configuration
2. Calls Claude via Bedrock with context
3. Generates tailored policy document
4. Posts to Slack as file attachment (Word/PDF)
5. Stores in S3 evidence bucket

**Example output:**
```
✅ Generated Access Control Policy

📄 Customized for your environment:
- References your IAM Identity Center instance
- Includes your 15 IAM users
- Notes current MFA status (8/15 enabled)
- Aligned with SOC 2 CC6.1, CC6.2, CC6.3, CC6.4, CC6.6

📎 access-control-policy.pdf (12 pages)
📎 access-control-policy.docx (editable)

💡 Next steps:
1. Review and customize for your company
2. Get approval from security lead
3. Publish to your document management system
4. Upload to CARL: /carl evidence upload CC6.1 <file>
```

**Technical approach:**
```python
def generate_policy(policy_type: str, account_context: dict) -> str:
    """Generate policy document using Claude."""

    # Gather context from AWS
    aws_context = {
        "iam_users": len(iam.list_users()["Users"]),
        "mfa_enabled": count_mfa_devices(),
        "identity_center": detect_identity_center(),
        "s3_buckets": len(s3.list_buckets()["Buckets"]),
        "ec2_instances": len(ec2.describe_instances()["Reservations"]),
        # ... more context
    }

    prompt = f"""Generate a comprehensive {policy_type} for a company with the following AWS environment:

Company: {account_context['company_name']}
Industry: {account_context['industry']}
Compliance: SOC 2 Type II

AWS Environment:
- IAM Users: {aws_context['iam_users']}
- MFA Enabled: {aws_context['mfa_enabled']}
- Identity Center: {aws_context['identity_center']}
- S3 Buckets: {aws_context['s3_buckets']}
- EC2 Instances: {aws_context['ec2_instances']}

Requirements:
- SOC 2 Control coverage: {get_control_mappings(policy_type)}
- Industry best practices
- Practical and implementable
- References actual AWS services detected

Format as a professional policy document with:
1. Purpose and Scope
2. Roles and Responsibilities
3. Policy Statements
4. Procedures
5. Enforcement
6. Review and Updates
7. Approval Signatures

Make it specific to this company's AWS environment, not generic."""

    response = bedrock.invoke_model(
        modelId="anthropic.claude-sonnet-4",
        body=json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 8000
        })
    )

    policy_text = parse_response(response)

    # Convert to Word/PDF
    policy_doc = generate_docx(policy_text)

    return policy_doc
```

---

### Phase 2: Procedure Generator (2 weeks)

**Slash command:**
```
/carl generate procedure <procedure-type>
/carl generate procedure access-review
/carl generate procedure incident-response
```

**Same approach as policies** but generates step-by-step procedures with:
- Checklists
- Forms
- AWS CLI commands (where applicable)
- Screenshots guidance

---

### Phase 3: Template Generator (1 week)

**Slash command:**
```
/carl generate template <template-type>
/carl generate template risk-register
/carl generate template vendor-questionnaire
```

**Output:**
- Excel spreadsheet
- Google Sheets link
- CSV for import

Pre-populated with:
- AWS resources (for asset inventory)
- Security Hub findings (for risk register)
- Current IAM users (for access review)

---

### Phase 4: Evidence Upload & Tracking (1 week)

**Slash command:**
```
/carl evidence upload <control> <file>
/carl evidence upload CC1.1 code-of-conduct.pdf
/carl evidence upload CC6.6 access-review-q4-2025.xlsx
```

**What it does:**
1. Upload document to S3
2. Store metadata in DynamoDB
3. Link to specific SOC 2 controls
4. Update coverage percentage

**Updated coverage display:**
```
Evidence Collection Status
Coverage: 78.5% ⬆️ (from 23.3%)

Controls Covered: 34 (auto: 10, manual: 24)
Controls Missing: 9

Missing Controls: CC1.2, CC1.3, CC4.2... (board/audit records)
```

---

## Expected Coverage Improvement

| Category | Before | After AI Generation | After Manual Review |
|----------|--------|---------------------|---------------------|
| **Technical (Auto)** | 10 controls (23%) | 10 controls (23%) | 10 controls (23%) |
| **Policies (AI)** | 0 controls | 15 controls (+35%) | 15 controls (+35%) |
| **Procedures (AI)** | 0 controls | 8 controls (+19%) | 8 controls (+19%) |
| **Templates (AI)** | 0 controls | 5 controls (+12%) | 5 controls (+12%) |
| **Records (Manual)** | 0 controls | 0 controls | 5 controls (+12%) |
| **Total** | **23.3%** | **89.3%** | **100%** |

**Key insight:** AI generation can take you from **23% to 89%** coverage with minimal manual effort.

The remaining 11% requires:
- Actual meeting minutes
- Actual vendor contracts
- Actual audit records
- Historical incident reports

---

## Business Value

### Cost Savings

**Without CARL:**
- Compliance consultant: $50k-$150k
- Time to create docs: 3-6 months
- Annual updates: $20k-$40k/year

**With CARL AI Generation:**
- One-time generation: 30 minutes
- Customization time: 1-2 weeks
- Annual updates: Re-generate in 30 minutes (free)

**ROI:** $50k-$150k saved on initial documentation

### Time Savings

**Manual documentation:**
- Access Control Policy: 2-3 days
- Incident Response Procedure: 1-2 days
- Risk Register Template: 1 day
- **Total for 30 documents: 30-60 days**

**CARL AI generation:**
- Generate all 30 documents: 30 minutes
- Review and customize: 5-10 days
- **Total: 5-10 days** (83-90% time savings)

### Audit Readiness

**Before:**
- Auditor asks for Access Control Policy
- You say "we don't have one yet"
- Auditor marks as finding
- You scramble to create it
- Follow-up audit in 3 months

**After:**
- Auditor asks for Access Control Policy
- You send generated + customized policy
- Auditor reviews and approves
- No findings, move to next control

---

## Technical Requirements

### Infrastructure Additions

1. **Claude API via Bedrock** - Already available
2. **Document generation library** - python-docx, reportlab
3. **S3 bucket for generated docs** - Already have evidence bucket
4. **DynamoDB table updates** - Add manual_evidence_uploaded field

### Cost Estimates

**Bedrock API costs:**
- Claude Sonnet 4: $3/million input tokens, $15/million output tokens
- Policy generation: ~5k input + 3k output tokens = $0.06/policy
- 30 documents: ~$2 total
- **Monthly cost for all users: ~$50-100**

**Storage costs:**
- S3 for generated docs: $0.023/GB = $2/month for 1000 documents

**Total additional infrastructure cost: ~$50-150/month**

---

## Implementation Priority

### High Priority (Implement Next)
1. **Policy Generator** - Highest impact, covers 15 controls
2. **Evidence Upload** - Needed to track manual docs
3. **Coverage Dashboard Update** - Show auto vs. manual evidence

### Medium Priority
4. **Procedure Generator** - Covers 8 controls
5. **Template Generator** - Covers 5 controls

### Low Priority (Nice to Have)
6. **Training Materials Generator**
7. **Document versioning and approval workflow**
8. **Auto-refresh on AWS changes** (policy updates when resources change)

---

## User Experience Example

```
User: /carl generate policy all

CARL: 🤖 Generating compliance documentation...

      Scanning your AWS environment:
      ✓ Found 15 IAM users
      ✓ Detected IAM Identity Center
      ✓ Found 4 S3 buckets
      ✓ Found Security Hub enabled
      ✓ Found CloudTrail enabled

      Generating 10 policy documents...
      ⏳ This will take ~2 minutes

      [2 minutes later]

      ✅ Generated 10 SOC 2 compliance policies!

      📄 Documents created:
      1. access-control-policy.pdf (CC6.1, CC6.2, CC6.3, CC6.4, CC6.6)
      2. incident-response-policy.pdf (CC7.3)
      3. change-management-policy.pdf (CC8.1)
      4. data-protection-policy.pdf (C1.1, C1.2)
      5. risk-management-policy.pdf (CC3.2, CC3.3, CC3.4)
      6. vendor-management-policy.pdf (CC9.1)
      7. business-continuity-policy.pdf (CC9.2, CC7.4, CC7.5)
      8. security-policy.pdf (CC2.3, CC5.3)
      9. code-of-conduct.pdf (CC1.1)
      10. hr-security-policy.pdf (CC1.4)

      📦 Download all: compliance-policies.zip (2.4 MB)

      💡 Next steps:
      1. Review each policy for your company's needs
      2. Customize with company-specific details
      3. Get approval from leadership
      4. Upload final versions: /carl evidence upload <control> <file>

      📊 This will increase coverage from 23% to 58% (+35%)!

User: /carl evidence upload CC6.1 access-control-policy-approved.pdf

CARL: ✅ Evidence uploaded!

      Document: access-control-policy-approved.pdf
      Size: 245 KB
      Controls: CC6.1, CC6.2, CC6.3, CC6.4, CC6.6
      Uploaded by: @greg.negelow
      Timestamp: 2026-01-29 02:45 UTC

      📊 Coverage updated: 23% → 35% (+12%)

      🎯 Keep going! Upload 9 more policies to reach 90% coverage.
```

---

## Risks and Mitigations

### Risk 1: Generated Policies Are Too Generic

**Mitigation:**
- Use AWS account scanning for context
- Detect actual resources and reference them
- Use company name, industry, data types
- Provide customization guidance
- Allow re-generation with more details

### Risk 2: Legal/Compliance Concerns

**Mitigation:**
- Add disclaimer: "Review with legal/compliance team before use"
- Provide customization guidance
- Reference industry standards (NIST, ISO)
- Don't claim "compliance guarantee"
- Position as "starting point templates"

### Risk 3: Users Don't Customize Generated Docs

**Mitigation:**
- Highlight customization TODOs in docs
- Add [CUSTOMIZE THIS] markers
- Require approval workflow before upload
- Provide review checklist

### Risk 4: Outdated Policies

**Mitigation:**
- Track generation date
- Notify when AWS environment changes significantly
- Offer re-generation quarterly
- Version tracking

---

## Success Metrics

**Adoption:**
- % of users who generate at least 1 policy
- Average policies generated per user
- Time from generation to upload

**Coverage:**
- Average coverage improvement (23% → ?)
- % of users reaching >80% coverage
- Time to reach audit-ready state

**Quality:**
- User satisfaction (survey)
- Policy rejection rate by auditors
- Customization time required

**Business:**
- Cost savings vs. consultants
- Time savings vs. manual creation
- Audit pass rate improvement

---

## Next Steps

1. **Validate demand** - Survey 10 users: Would you use this?
2. **Proof of concept** - Generate 3 policies manually with Claude
3. **Build MVP** - Policy generator for 3 most valuable policies
4. **Pilot test** - 5 beta users generate and review
5. **Iterate** - Improve based on feedback
6. **Launch** - Roll out to all users
7. **Expand** - Add procedures, templates, etc.

---

## Related Features

- **Document Management Integration** - Sync to Google Drive, SharePoint
- **Approval Workflow** - Route generated docs for review/approval
- **Version Control** - Track changes over time
- **Audit Package Generation** - Zip all evidence for auditor
- **Gap Analysis** - Show exactly what's missing for 100% coverage
- **Policy Comparison** - Compare your policies vs. industry best practices

---

## Conclusion

**Potential impact:** Increase automated coverage from **23% to 89%** with AI-generated documentation.

**User value:** Save $50k-$150k and 1-2 months of manual documentation work.

**Implementation effort:** 4-6 weeks for full feature set.

**This feature would make CARL a complete SOC 2 compliance automation solution.**
