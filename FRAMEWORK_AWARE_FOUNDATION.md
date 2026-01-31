# Framework-Aware Foundation - Implementation Guide

## Overview

CARL Foundation is now **framework-aware** - it uses compliance framework definitions (SOC 2, HIPAA, etc.) to intelligently guide infrastructure setup.

**Key Benefits:**
- **Fewer questions**: 5-6 questions vs 10 (framework knows what services you need)
- **Compliance-ready**: Generated Terraform includes control mappings
- **Gap analysis**: Shows what you have vs what you need
- **Scalable**: Easy to add new frameworks (HIPAA, PCI-DSS, ISO 27001)

---

## Architecture

### Components Built

```
compliance-frameworks/
  └── soc2.yaml                    # Framework definition (single source of truth)

src/services/
  ├── framework_loader.py          # Parses YAML → Python objects
  ├── framework_gap_analyzer.py    # Compares required vs actual
  └── (Next: Update decision_engine.py, foundation_builder.py)
```

### How It Works

```
User: /carl foundation start
  ↓
1. Ask: "Which framework?" [SOC 2] [HIPAA] [Best Practices] [Skip]
  ↓
2. Load framework YAML (soc2.yaml)
  ↓
3. Scan AWS environment (existing resource_detector)
  ↓
4. Gap analysis: required vs current
  ↓
5. Show gaps with compliance context
  ↓
6. Ask only 5-6 configuration questions (framework knows the rest)
  ↓
7. Generate compliance-aware Terraform for gaps only
```

---

## Framework YAML Structure

The **framework YAML** is the single source of truth for both Foundation and Account Factory:

```yaml
framework:
  id: soc2
  name: "SOC 2 Type II"

  # Required AWS services with exact configurations
  required_services:
    logging_monitoring:
      - service: cloudtrail
        config:
          retention_days: 2555  # 7 years (SOC 2 requirement)
          multi_region: true
          log_validation: true
        controls: [CC7.2, A1.3]  # Maps to SOC 2 controls
        why_required: "7-year audit log retention required..."
        audit_evidence:
          - "CloudTrail configuration"
          - "S3 lifecycle policy"
        validation_checks:
          - check: "retention >= 2555 days"
            failure: "Retention too short - SOC 2 requires 7 years"

  # Questions to ask (configuration only, not "should we enable X?")
  questions:
    - id: primary_region
      question: "Which AWS region is your primary region?"
      options: [us-east-1, us-west-2, eu-west-1]
    - id: multi_region
      question: "Do you need multi-region monitoring?"
      options: [single, multi]
```

---

## Gap Analysis Output

After scanning AWS, user sees:

```
SOC 2 Gap Analysis

✓ Security Hub (CC8.1) - COMPLIANT
  Using existing: arn:aws:securityhub:us-east-1:123456789012:hub/default
  CIS + AWS Foundational standards enabled

❌ CloudTrail (CC7.2, A1.3) - MISCONFIGURED
   Current: 90-day retention
   Required: 2555-day retention (7 years)
   Fix: Add S3 lifecycle policy
   [Why 7 years?] ← AI explains on click

❌ GuardDuty (CC7.1) - MISSING
   Impact: No threat detection
   Cost: ~$0.50/month
   [Why required?] ← AI explains

Compliance: 1/3 controls (33%)
Estimated cost to fix: $2.50/month
```

---

## Gap Analysis Data Structures

```python
# Gap status
class GapStatus(Enum):
    COMPLIANT = "compliant"        # Exists and meets requirements
    MISSING = "missing"            # Doesn't exist
    MISCONFIGURED = "misconfigured" # Exists but config wrong

# A single compliance gap
@dataclass
class ComplianceGap:
    service: str  # "cloudtrail", "guardduty"
    status: GapStatus
    controls: list[str]  # ["CC7.2", "A1.3"]
    why_required: str  # Business explanation
    audit_evidence: list[str]  # What auditors check

    # For MISCONFIGURED
    violations: list[ComplianceViolation]
    current_config: dict
    required_config: dict

    # For MISSING
    estimated_monthly_cost: float

# Complete analysis
@dataclass
class FrameworkGapAnalysis:
    framework_name: str
    gaps: list[ComplianceGap]

    @property
    def compliance_percentage(self) -> float:
        """% of compliant services"""

    @property
    def estimated_cost_to_fix(self) -> float:
        """Total $ to fix all missing services"""
```

---

## Usage Example

```python
from services.framework_loader import get_framework_loader
from services.framework_gap_analyzer import get_gap_analyzer

# Load framework
loader = get_framework_loader()
framework = loader.load("soc2")

print(f"Loaded: {framework.name}")
print(f"Required services: {len(framework.get_all_required_services())}")
print(f"Questions: {len(framework.questions)}")

# Analyze gaps
analyzer = get_gap_analyzer()
analysis = analyzer.analyze(
    framework=framework,
    account_id="123456789012",
    region="us-east-1"
)

print(f"Compliance: {analysis.compliance_percentage:.1f}%")
print(f"Missing: {analysis.missing_count}")
print(f"Misconfigured: {analysis.misconfigured_count}")
print(f"Cost to fix: ${analysis.estimated_cost_to_fix:.2f}/month")

# Show gaps
for gap in analysis.gaps:
    print(f"\n{gap.service} ({gap.status.value})")
    print(f"  Controls: {', '.join(gap.controls)}")

    if gap.status == GapStatus.MISCONFIGURED:
        for v in gap.violations:
            print(f"  ❌ {v.failure_message}")
            print(f"     Current: {v.current_value}")
            print(f"     Required: {v.required_value}")
```

---

## Next Steps to Complete Implementation

### 1. Update `decision_engine.py`
Add framework-driven flow to DecisionEngine:

```python
class DecisionSession:
    # Add framework support
    framework: Optional[ComplianceFramework] = None
    gap_analysis: Optional[FrameworkGapAnalysis] = None

def _generate_framework_recommendations(self, session: DecisionSession):
    """Generate recommendations from framework gap analysis."""
    # Create decision for each gap
    for gap in session.gap_analysis.gaps:
        if gap.status != GapStatus.COMPLIANT:
            decision = DecisionResult(
                category=gap.category,
                selected_option=self._gap_to_option(gap),
                compliance_controls=gap.controls,
                why_required=gap.why_required
            )
            session.decisions.append(decision)
```

### 2. Update `foundation_builder.py`
Generate compliance-aware Terraform:

```python
def generate_foundation(self, session: DecisionSession):
    modules = []

    for decision in session.decisions:
        # Generate module with compliance metadata
        module = TerraformModule(
            name=decision.service,
            content=self._generate_terraform(decision),
            compliance_controls=decision.compliance_controls,  # NEW
            why_required=decision.why_required,  # NEW
            audit_evidence=decision.audit_evidence  # NEW
        )
        modules.append(module)

    return modules
```

Generated Terraform will include:
```hcl
# cloudtrail.tf
# SOC 2 Controls: CC7.2, A1.3
# Why Required: 7-year audit log retention required
# Auditor Evidence: CloudTrail logs, S3 lifecycle policy

resource "aws_cloudtrail" "main" {
  # ... with 7-year retention
}
```

### 3. Update Slack Commands
Add framework selection to `/carl foundation start`:

```python
def handle_foundation_command(slack, channel_id, user_id, args):
    if subcommand == "start":
        # NEW: First question is framework selection
        blocks = [
            {"type": "header", "text": "CARL Foundation Builder"},
            {"type": "section", "text": "Which compliance framework?"},
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": "SOC 2", "value": "soc2"},
                    {"type": "button", "text": "HIPAA", "value": "hipaa"},
                    {"type": "button", "text": "Best Practices", "value": "best_practices"},
                    {"type": "button", "text": "Skip - just networking", "value": "none"}
                ]
            }
        ]
```

---

## Adding New Frameworks

To add HIPAA, PCI-DSS, ISO 27001, etc.:

1. **Copy SOC 2 YAML template:**
   ```bash
   cp compliance-frameworks/soc2.yaml compliance-frameworks/hipaa.yaml
   ```

2. **Edit requirements:**
   ```yaml
   framework:
     id: hipaa
     name: "HIPAA"

     required_services:
       logging_monitoring:
         - service: cloudtrail
           config:
             retention_days: 2190  # 6 years (HIPAA requirement, not 7)
             encryption: required
           controls: [164.308, 164.312]  # HIPAA control IDs
   ```

3. **That's it!** Both Foundation and Account Factory automatically support it.

---

## Testing

```python
# Test framework loading
loader = get_framework_loader()
assert "soc2" in loader.list_available_frameworks()

framework = loader.load("soc2")
assert framework.name == "SOC 2 Type II"
assert len(framework.get_all_required_services()) == 15  # All required services

# Test gap analysis
analyzer = get_gap_analyzer()
analysis = analyzer.analyze(framework, account_id="123456789012")

# Should detect CloudTrail with wrong retention
cloudtrail_gap = next(g for g in analysis.gaps if g.service == "cloudtrail")
assert cloudtrail_gap.status == GapStatus.MISCONFIGURED
assert any("retention" in v.check for v in cloudtrail_gap.violations)
```

---

## Framework Validation Checks

The framework YAML supports rich validation checks:

```yaml
validation_checks:
  # Numeric comparisons
  - check: "retention >= 2555 days"
    failure: "Retention too short"

  # Boolean checks
  - check: "multi_region == true"
    failure: "Multi-region required"

  # Custom checks
  - check: "enabled for all VPCs"
    failure: "VPC Flow Logs must be enabled for all VPCs"

  - check: "all console users have MFA"
    failure: "All users must have MFA enabled"

  - check: "all data sources enabled"
    failure: "S3, EKS, Malware, RDS protection required"
```

The `FrameworkGapAnalyzer._evaluate_check()` method parses these and validates current config.

---

## Backward Compatibility

The old 10-question flow still works:

```python
# If user clicks "Skip - just networking"
if framework_choice == "none":
    # Use existing flow
    session.framework = None
    return self._generate_static_recommendations(session)  # OLD 10-question flow
```

---

## Cost Estimates

Framework YAML includes baseline cost estimates:

```yaml
estimated_monthly_costs:
  cloudtrail: 0  # Free for management events
  cloudtrail_s3_storage: 5  # 7 years of logs
  guardduty: 1
  config: 2
  total_baseline: 20  # Small account baseline
```

Gap analysis sums these for "Cost to fix" estimate.

---

## Evidence Collection

Framework YAML includes auditor evidence requirements:

```yaml
evidence_collection:
  monthly:
    - "CloudTrail logs (download from S3)"
    - "GuardDuty findings report"
    - "Security Hub compliance score"

  quarterly:
    - "IAM credential report"
    - "Access review documentation"

  annually:
    - "SOC 2 Type II audit"
    - "Penetration testing"
```

Foundation generates `evidence_collection_plan.md` based on this.

---

## Summary

**What's Built:**
- ✅ Framework YAML structure (soc2.yaml)
- ✅ FrameworkLoader (parses YAML)
- ✅ FrameworkGapAnalyzer (compares required vs actual)

**What's Next:**
- ⏳ Update decision_engine.py (framework-driven flow)
- ⏳ Update foundation_builder.py (compliance-aware Terraform)
- ⏳ Update Slack commands (framework selection UI)

**Timeline:** ~4-6 hours of development to complete integration

**Impact:** Foundation becomes a **compliance-first** tool that:
- Reduces questions (10 → 5-6)
- Generates audit-ready infrastructure
- Works for any framework (SOC 2, HIPAA, PCI-DSS, etc.)
- Single YAML drives both Foundation and Account Factory
