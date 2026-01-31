"""
Compliance Report Generator for CARL.

Generates audit-ready reports for SOC 2 and other compliance frameworks:
- Executive summary with compliance posture
- Control-by-control breakdown with evidence
- Findings and remediation status
- Exception/risk acceptance documentation
- Historical trend analysis

Reports are generated in Markdown format for easy conversion to PDF.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import boto3

from utils.logger import get_logger
from services.evidence_collector import (
    EvidenceCollector,
    Evidence,
    SOC2Control,
    RESOURCE_CONTROL_MAPPING,
)

logger = get_logger(__name__)


class ReportType(Enum):
    """Types of compliance reports."""
    EXECUTIVE_SUMMARY = "executive_summary"
    FULL_AUDIT = "full_audit"
    CONTROL_SPECIFIC = "control_specific"
    FINDINGS_SUMMARY = "findings_summary"
    EVIDENCE_INVENTORY = "evidence_inventory"
    EXCEPTION_REPORT = "exception_report"
    TREND_ANALYSIS = "trend_analysis"


class ComplianceStatus(Enum):
    """Overall compliance status."""
    COMPLIANT = "compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"


@dataclass
class ControlAssessment:
    """Assessment of a single SOC 2 control."""
    control_id: str
    control_name: str
    control_description: str
    status: ComplianceStatus
    evidence_count: int
    evidence_ids: list[str]
    findings_count: int
    finding_ids: list[str]
    exceptions_count: int
    exception_ids: list[str]
    notes: str = ""
    last_assessed: str = ""


@dataclass
class ReportMetadata:
    """Metadata for a generated report."""
    report_id: str
    report_type: str
    title: str
    generated_at: str
    generated_by: str
    audit_period_start: str
    audit_period_end: str
    framework: str
    version: str = "1.0"


# SOC 2 Control Descriptions
SOC2_CONTROL_DESCRIPTIONS = {
    "CC1.1": "COSO Principle 1: The entity demonstrates a commitment to integrity and ethical values.",
    "CC1.2": "COSO Principle 2: The board of directors demonstrates independence from management and exercises oversight.",
    "CC1.3": "COSO Principle 3: Management establishes structures, reporting lines, and appropriate authorities.",
    "CC1.4": "COSO Principle 4: The entity demonstrates a commitment to attract, develop, and retain competent individuals.",
    "CC1.5": "COSO Principle 5: The entity holds individuals accountable for their internal control responsibilities.",

    "CC2.1": "COSO Principle 13: The entity obtains or generates and uses relevant, quality information.",
    "CC2.2": "COSO Principle 14: The entity internally communicates information necessary to support functioning of internal control.",
    "CC2.3": "COSO Principle 15: The entity communicates with external parties regarding matters affecting internal control.",

    "CC3.1": "COSO Principle 6: The entity specifies objectives with sufficient clarity.",
    "CC3.2": "COSO Principle 7: The entity identifies risks to the achievement of objectives and analyzes them.",
    "CC3.3": "COSO Principle 8: The entity considers the potential for fraud in assessing risks.",
    "CC3.4": "COSO Principle 9: The entity identifies and assesses changes that could impact internal control.",

    "CC4.1": "COSO Principle 16: The entity selects, develops, and performs ongoing and/or separate evaluations.",
    "CC4.2": "COSO Principle 17: The entity evaluates and communicates internal control deficiencies.",

    "CC5.1": "COSO Principle 10: The entity selects and develops control activities that mitigate risks.",
    "CC5.2": "COSO Principle 11: The entity selects and develops general control activities over technology.",
    "CC5.3": "COSO Principle 12: The entity deploys control activities through policies and procedures.",

    "CC6.1": "The entity implements logical access security software and infrastructure to protect information assets.",
    "CC6.2": "Prior to issuing system credentials, the entity registers and authorizes new users.",
    "CC6.3": "The entity removes access to protected information assets when appropriate.",
    "CC6.4": "The entity restricts physical access to facilities and protected information assets.",
    "CC6.5": "The entity discontinues logical and physical protections over physical assets only after transfer.",
    "CC6.6": "The entity implements logical access security measures to protect against threats from outside boundaries.",
    "CC6.7": "The entity restricts the transmission, movement, and removal of information to authorized users.",
    "CC6.8": "The entity implements controls to prevent or detect and act upon unauthorized or malicious software.",

    "CC7.1": "To meet its objectives, the entity uses detection and monitoring procedures.",
    "CC7.2": "The entity monitors system components for anomalies that indicate malicious acts.",
    "CC7.3": "The entity evaluates security events to determine whether they could represent failures.",
    "CC7.4": "The entity responds to identified security incidents by executing defined procedures.",
    "CC7.5": "The entity identifies, develops, and implements activities to recover from identified incidents.",

    "CC8.1": "The entity authorizes, designs, develops, configures, documents, tests, approves, and implements changes.",

    "CC9.1": "The entity identifies, selects, and develops risk mitigation activities for risks from business partners.",
    "CC9.2": "The entity assesses and manages risks associated with vendors and business partners.",

    "A1.1": "The entity maintains, monitors, and evaluates current processing capacity and use of system components.",
    "A1.2": "The entity authorizes, designs, develops, and implements activities to recover from identified incidents.",
    "A1.3": "The entity tests recovery plan procedures supporting system recovery.",

    "C1.1": "The entity identifies and maintains confidential information to meet entity's objectives.",
    "C1.2": "The entity disposes of confidential information to meet entity's objectives.",

    "PI1.1": "The entity obtains or generates, uses, and communicates relevant, quality information.",
    "PI1.2": "The entity implements policies and procedures over system inputs to result in accurate processing.",
    "PI1.3": "The entity implements policies and procedures over system processing to result in timely processing.",
    "PI1.4": "The entity implements policies and procedures to make information processing activities visible.",
    "PI1.5": "The entity implements policies and procedures to store inputs, items, and outputs completely.",
}


class ReportGenerator:
    """Service for generating compliance reports."""

    def __init__(
        self,
        evidence_collector: EvidenceCollector,
        findings_table: str = None,
        exceptions_table: str = None,
        reports_bucket: str = None
    ):
        self.evidence_collector = evidence_collector
        self.findings_table = findings_table
        self.exceptions_table = exceptions_table
        self.reports_bucket = reports_bucket

        self.dynamodb = boto3.resource("dynamodb")
        self.s3 = boto3.client("s3")

        if findings_table:
            self.findings_db = self.dynamodb.Table(findings_table)
        else:
            self.findings_db = None

        if exceptions_table:
            self.exceptions_db = self.dynamodb.Table(exceptions_table)
        else:
            self.exceptions_db = None

    def generate_executive_summary(
        self,
        audit_period_start: str,
        audit_period_end: str,
        organization_name: str = "Organization"
    ) -> str:
        """Generate an executive summary report."""
        timestamp = datetime.utcnow()

        # Get coverage data
        coverage = self.evidence_collector.get_control_coverage()

        # Get findings summary
        findings_summary = self._get_findings_summary()

        # Get exceptions summary
        exceptions_summary = self._get_exceptions_summary()

        # Calculate overall status
        if coverage["coverage_percent"] >= 90 and findings_summary["critical"] == 0:
            overall_status = ComplianceStatus.COMPLIANT
        elif coverage["coverage_percent"] >= 70:
            overall_status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            overall_status = ComplianceStatus.NON_COMPLIANT

        # Generate report
        report = f"""# SOC 2 Type II Compliance Executive Summary

**Organization:** {organization_name}
**Audit Period:** {audit_period_start} to {audit_period_end}
**Report Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Generated By:** CARL (Cloud Automated Risk & Compliance Logic)

---

## Overall Compliance Status: {overall_status.value.upper().replace('_', ' ')}

### Summary Metrics

| Metric | Value |
|--------|-------|
| Control Coverage | {coverage["coverage_percent"]:.1f}% |
| Controls Assessed | {len(coverage["covered"])} of {len(coverage["covered"]) + len(coverage["missing"])} |
| Total Evidence Items | {sum(len(v) for v in coverage["control_evidence"].values())} |
| Open Findings | {findings_summary["total"]} |
| Critical Findings | {findings_summary["critical"]} |
| High Findings | {findings_summary["high"]} |
| Active Exceptions | {exceptions_summary["active"]} |

---

## Compliance Posture by Trust Service Category

### Security (Common Criteria)

| Control Area | Status | Evidence | Findings |
|--------------|--------|----------|----------|
| CC1 - Control Environment | {'✅' if self._check_control_area_status('CC1', coverage) else '⚠️'} | {self._count_evidence_for_area('CC1', coverage)} items | {self._count_findings_for_area('CC1', findings_summary)} |
| CC2 - Communication | {'✅' if self._check_control_area_status('CC2', coverage) else '⚠️'} | {self._count_evidence_for_area('CC2', coverage)} items | {self._count_findings_for_area('CC2', findings_summary)} |
| CC3 - Risk Assessment | {'✅' if self._check_control_area_status('CC3', coverage) else '⚠️'} | {self._count_evidence_for_area('CC3', coverage)} items | {self._count_findings_for_area('CC3', findings_summary)} |
| CC4 - Monitoring | {'✅' if self._check_control_area_status('CC4', coverage) else '⚠️'} | {self._count_evidence_for_area('CC4', coverage)} items | {self._count_findings_for_area('CC4', findings_summary)} |
| CC5 - Control Activities | {'✅' if self._check_control_area_status('CC5', coverage) else '⚠️'} | {self._count_evidence_for_area('CC5', coverage)} items | {self._count_findings_for_area('CC5', findings_summary)} |
| CC6 - Logical Access | {'✅' if self._check_control_area_status('CC6', coverage) else '⚠️'} | {self._count_evidence_for_area('CC6', coverage)} items | {self._count_findings_for_area('CC6', findings_summary)} |
| CC7 - System Operations | {'✅' if self._check_control_area_status('CC7', coverage) else '⚠️'} | {self._count_evidence_for_area('CC7', coverage)} items | {self._count_findings_for_area('CC7', findings_summary)} |
| CC8 - Change Management | {'✅' if self._check_control_area_status('CC8', coverage) else '⚠️'} | {self._count_evidence_for_area('CC8', coverage)} items | {self._count_findings_for_area('CC8', findings_summary)} |
| CC9 - Risk Mitigation | {'✅' if self._check_control_area_status('CC9', coverage) else '⚠️'} | {self._count_evidence_for_area('CC9', coverage)} items | {self._count_findings_for_area('CC9', findings_summary)} |

### Availability

| Control | Status | Evidence | Findings |
|---------|--------|----------|----------|
| A1 - Availability | {'✅' if self._check_control_area_status('A1', coverage) else '⚠️'} | {self._count_evidence_for_area('A1', coverage)} items | {self._count_findings_for_area('A1', findings_summary)} |

### Confidentiality

| Control | Status | Evidence | Findings |
|---------|--------|----------|----------|
| C1 - Confidentiality | {'✅' if self._check_control_area_status('C1', coverage) else '⚠️'} | {self._count_evidence_for_area('C1', coverage)} items | {self._count_findings_for_area('C1', findings_summary)} |

---

## Critical Findings Requiring Attention

{self._format_critical_findings(findings_summary)}

---

## Controls Missing Evidence

The following controls require evidence collection:

{self._format_missing_controls(coverage["missing"])}

---

## Active Risk Exceptions

{self._format_active_exceptions(exceptions_summary)}

---

## Recommendations

1. **Immediate Actions:**
{self._generate_immediate_recommendations(findings_summary, coverage)}

2. **Short-term Improvements:**
{self._generate_shortterm_recommendations(findings_summary, coverage)}

3. **Long-term Initiatives:**
{self._generate_longterm_recommendations(findings_summary, coverage)}

---

*This report was automatically generated by CARL. For the complete audit package including all evidence artifacts, please refer to the Full Audit Report.*

"""
        return report

    def generate_full_audit_report(
        self,
        audit_period_start: str,
        audit_period_end: str,
        organization_name: str = "Organization"
    ) -> str:
        """Generate a comprehensive audit report with control-by-control breakdown."""
        timestamp = datetime.utcnow()
        coverage = self.evidence_collector.get_control_coverage()
        findings_summary = self._get_findings_summary()

        report = f"""# SOC 2 Type II Full Audit Report

**Organization:** {organization_name}
**Audit Period:** {audit_period_start} to {audit_period_end}
**Report Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Framework:** SOC 2 Trust Services Criteria (2017)

---

## Table of Contents

1. Executive Summary
2. Scope and Methodology
3. Control Assessment Details
4. Evidence Inventory
5. Findings and Remediation
6. Exceptions and Risk Acceptances
7. Appendices

---

## 1. Executive Summary

{self._generate_brief_summary(coverage, findings_summary)}

---

## 2. Scope and Methodology

### In-Scope Systems
- AWS Infrastructure (All Regions)
- Identity and Access Management
- Network Security Controls
- Data Protection Mechanisms
- Logging and Monitoring Systems

### Assessment Methodology
- Automated evidence collection via AWS APIs
- Security Hub compliance checks
- AWS Config rule evaluations
- Manual attestations where applicable

### Evidence Collection
- **Automated:** Resource configurations, security findings, access logs
- **Point-in-Time:** Configuration snapshots at regular intervals
- **Continuous:** Security Hub and GuardDuty findings

---

## 3. Control Assessment Details

"""
        # Add detailed control assessments
        for control in SOC2Control:
            assessment = self._assess_control(control.value, coverage, findings_summary)
            report += self._format_control_assessment(assessment)

        report += """
---

## 4. Evidence Inventory

"""
        report += self._generate_evidence_inventory(coverage)

        report += """
---

## 5. Findings and Remediation

"""
        report += self._generate_findings_section(findings_summary)

        report += """
---

## 6. Exceptions and Risk Acceptances

"""
        report += self._generate_exceptions_section()

        report += """
---

## 7. Appendices

### A. AWS Services in Scope
- IAM (Identity and Access Management)
- S3 (Simple Storage Service)
- EC2 (Elastic Compute Cloud)
- VPC (Virtual Private Cloud)
- RDS (Relational Database Service)
- CloudTrail
- Security Hub
- GuardDuty
- AWS Config
- KMS (Key Management Service)

### B. Compliance Standards Enabled
- AWS Foundational Security Best Practices
- CIS AWS Foundations Benchmark
- PCI DSS (where applicable)

### C. Report Generation Details
- Tool: CARL (Cloud Automated Risk & Compliance Logic)
- Version: 1.0
- Collection Method: AWS SDK (boto3)
- Storage: S3 with encryption, DynamoDB for metadata

---

*End of Report*

"""
        return report

    def generate_control_report(self, control_id: str) -> str:
        """Generate a detailed report for a specific control."""
        coverage = self.evidence_collector.get_control_coverage()
        findings_summary = self._get_findings_summary()
        assessment = self._assess_control(control_id, coverage, findings_summary)

        description = SOC2_CONTROL_DESCRIPTIONS.get(control_id, "No description available")

        report = f"""# Control Assessment Report: {control_id}

**Control:** {control_id}
**Description:** {description}
**Assessment Date:** {datetime.utcnow().strftime('%Y-%m-%d')}
**Status:** {assessment.status.value.upper().replace('_', ' ')}

---

## Evidence Summary

| Metric | Count |
|--------|-------|
| Evidence Items | {assessment.evidence_count} |
| Open Findings | {assessment.findings_count} |
| Active Exceptions | {assessment.exceptions_count} |

---

## Evidence Items

"""
        # Get evidence details
        evidence_items = self.evidence_collector.get_evidence_by_control(control_id)
        for evidence in evidence_items:
            report += f"""
### {evidence.title}

- **ID:** {evidence.evidence_id}
- **Type:** {evidence.evidence_type}
- **Resource:** {evidence.resource_id}
- **Collected:** {evidence.collected_at}
- **S3 Location:** {evidence.s3_key}
- **Content Hash:** {evidence.content_hash}

"""

        report += """
---

## Related Findings

"""
        # Would fetch actual findings here
        report += "_No open findings for this control._\n" if assessment.findings_count == 0 else f"_{assessment.findings_count} findings require attention._\n"

        report += """
---

## Recommendations

"""
        report += self._generate_control_recommendations(control_id, assessment)

        return report

    def _get_findings_summary(self) -> dict:
        """Get summary of current findings."""
        if not self.findings_db:
            return {
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "by_control": {},
                "items": []
            }

        try:
            response = self.findings_db.scan()
            items = response.get("Items", [])

            summary = {
                "total": len(items),
                "critical": sum(1 for i in items if i.get("severity") == "CRITICAL"),
                "high": sum(1 for i in items if i.get("severity") == "HIGH"),
                "medium": sum(1 for i in items if i.get("severity") == "MEDIUM"),
                "low": sum(1 for i in items if i.get("severity") == "LOW"),
                "by_control": {},
                "items": items
            }

            for item in items:
                for control in item.get("controls", []):
                    if control not in summary["by_control"]:
                        summary["by_control"][control] = []
                    summary["by_control"][control].append(item)

            return summary

        except Exception as e:
            logger.exception("Error getting findings summary")
            return {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0, "by_control": {}, "items": []}

    def _get_exceptions_summary(self) -> dict:
        """Get summary of active exceptions."""
        if not self.exceptions_db:
            return {"active": 0, "expired": 0, "items": []}

        try:
            response = self.exceptions_db.scan()
            items = response.get("Items", [])
            now = datetime.utcnow().isoformat()

            return {
                "active": sum(1 for i in items if i.get("expires_at", "9999") > now and i.get("status") == "approved"),
                "expired": sum(1 for i in items if i.get("expires_at", "9999") <= now),
                "items": items
            }

        except Exception as e:
            logger.exception("Error getting exceptions summary")
            return {"active": 0, "expired": 0, "items": []}

    def _assess_control(
        self,
        control_id: str,
        coverage: dict,
        findings_summary: dict
    ) -> ControlAssessment:
        """Assess a single control's compliance status."""
        evidence_ids = coverage["control_evidence"].get(control_id, [])
        finding_ids = [f["id"] for f in findings_summary["by_control"].get(control_id, [])]

        # Determine status
        if len(evidence_ids) == 0:
            status = ComplianceStatus.NOT_ASSESSED
        elif len(finding_ids) > 0:
            critical_findings = any(
                f.get("severity") in ["CRITICAL", "HIGH"]
                for f in findings_summary["by_control"].get(control_id, [])
            )
            status = ComplianceStatus.NON_COMPLIANT if critical_findings else ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            status = ComplianceStatus.COMPLIANT

        return ControlAssessment(
            control_id=control_id,
            control_name=control_id,
            control_description=SOC2_CONTROL_DESCRIPTIONS.get(control_id, ""),
            status=status,
            evidence_count=len(evidence_ids),
            evidence_ids=evidence_ids,
            findings_count=len(finding_ids),
            finding_ids=finding_ids,
            exceptions_count=0,  # Would calculate from exceptions DB
            exception_ids=[],
            last_assessed=datetime.utcnow().isoformat()
        )

    def _check_control_area_status(self, area_prefix: str, coverage: dict) -> bool:
        """Check if a control area has adequate coverage."""
        relevant_controls = [c for c in coverage["covered"] if c.startswith(area_prefix)]
        all_controls = [c.value for c in SOC2Control if c.value.startswith(area_prefix)]
        return len(relevant_controls) >= len(all_controls) * 0.7

    def _count_evidence_for_area(self, area_prefix: str, coverage: dict) -> int:
        """Count evidence items for a control area."""
        return sum(
            len(evidence)
            for control, evidence in coverage["control_evidence"].items()
            if control.startswith(area_prefix)
        )

    def _count_findings_for_area(self, area_prefix: str, findings_summary: dict) -> int:
        """Count findings for a control area."""
        return sum(
            len(findings)
            for control, findings in findings_summary["by_control"].items()
            if control.startswith(area_prefix)
        )

    def _format_critical_findings(self, findings_summary: dict) -> str:
        """Format critical findings for the report."""
        critical = [f for f in findings_summary["items"] if f.get("severity") == "CRITICAL"]
        if not critical:
            return "_No critical findings._"

        lines = []
        for finding in critical[:10]:
            lines.append(f"- **{finding.get('title', 'Unknown')}** - {finding.get('resource_id', 'N/A')}")

        return "\n".join(lines)

    def _format_missing_controls(self, missing: list) -> str:
        """Format list of controls missing evidence."""
        if not missing:
            return "_All controls have evidence._"

        lines = []
        for control in missing:
            desc = SOC2_CONTROL_DESCRIPTIONS.get(control, "No description")
            lines.append(f"- **{control}**: {desc[:100]}...")

        return "\n".join(lines)

    def _format_active_exceptions(self, exceptions_summary: dict) -> str:
        """Format active exceptions for the report."""
        if exceptions_summary["active"] == 0:
            return "_No active risk exceptions._"

        lines = [f"**{exceptions_summary['active']} active exception(s)**\n"]
        for exc in exceptions_summary.get("items", [])[:5]:
            if exc.get("status") == "approved":
                lines.append(f"- {exc.get('title', 'Unknown')} - Expires: {exc.get('expires_at', 'N/A')}")

        return "\n".join(lines)

    def _generate_immediate_recommendations(self, findings: dict, coverage: dict) -> str:
        """Generate immediate action recommendations."""
        recs = []
        if findings["critical"] > 0:
            recs.append(f"   - Address {findings['critical']} critical finding(s) immediately")
        if findings["high"] > 0:
            recs.append(f"   - Remediate {findings['high']} high-severity finding(s) within 7 days")
        if len(coverage["missing"]) > 0:
            recs.append(f"   - Collect evidence for {len(coverage['missing'])} control(s) missing documentation")

        return "\n".join(recs) if recs else "   - No immediate actions required"

    def _generate_shortterm_recommendations(self, findings: dict, coverage: dict) -> str:
        """Generate short-term improvement recommendations."""
        recs = [
            "   - Implement automated evidence collection for remaining controls",
            "   - Review and update security policies quarterly",
            "   - Conduct access reviews for privileged accounts"
        ]
        return "\n".join(recs)

    def _generate_longterm_recommendations(self, findings: dict, coverage: dict) -> str:
        """Generate long-term initiative recommendations."""
        recs = [
            "   - Implement continuous compliance monitoring",
            "   - Expand coverage to additional compliance frameworks",
            "   - Automate remediation for common findings"
        ]
        return "\n".join(recs)

    def _generate_brief_summary(self, coverage: dict, findings: dict) -> str:
        """Generate brief summary paragraph."""
        return f"""
This report provides a comprehensive assessment of the organization's compliance posture
against SOC 2 Trust Services Criteria. The assessment covered {len(coverage["covered"])} controls
with {coverage["coverage_percent"]:.1f}% evidence coverage. There are currently {findings["total"]}
open findings, including {findings["critical"]} critical and {findings["high"]} high severity items
requiring attention.
"""

    def _format_control_assessment(self, assessment: ControlAssessment) -> str:
        """Format a control assessment for the report."""
        status_icon = {
            ComplianceStatus.COMPLIANT: "✅",
            ComplianceStatus.PARTIALLY_COMPLIANT: "⚠️",
            ComplianceStatus.NON_COMPLIANT: "❌",
            ComplianceStatus.NOT_ASSESSED: "❓"
        }

        return f"""
### {assessment.control_id} {status_icon.get(assessment.status, "❓")}

**Description:** {assessment.control_description}

**Status:** {assessment.status.value.replace('_', ' ').title()}

| Metric | Count |
|--------|-------|
| Evidence Items | {assessment.evidence_count} |
| Open Findings | {assessment.findings_count} |
| Exceptions | {assessment.exceptions_count} |

---

"""

    def _generate_evidence_inventory(self, coverage: dict) -> str:
        """Generate evidence inventory section."""
        lines = ["| Control | Evidence Count | Evidence IDs |", "|---------|---------------|--------------|"]

        for control, evidence_ids in sorted(coverage["control_evidence"].items()):
            ids_display = ", ".join(evidence_ids[:3])
            if len(evidence_ids) > 3:
                ids_display += f" (+{len(evidence_ids) - 3} more)"
            lines.append(f"| {control} | {len(evidence_ids)} | {ids_display} |")

        return "\n".join(lines)

    def _generate_findings_section(self, findings_summary: dict) -> str:
        """Generate findings section of the report."""
        if findings_summary["total"] == 0:
            return "_No open findings._\n"

        lines = [
            "### Findings by Severity\n",
            f"- **Critical:** {findings_summary['critical']}",
            f"- **High:** {findings_summary['high']}",
            f"- **Medium:** {findings_summary['medium']}",
            f"- **Low:** {findings_summary['low']}",
            "\n### Recent Findings\n",
            "| Title | Severity | Resource | Control |",
            "|-------|----------|----------|---------|"
        ]

        for finding in findings_summary["items"][:20]:
            controls = ", ".join(finding.get("controls", [])[:2])
            lines.append(
                f"| {finding.get('title', 'Unknown')[:50]} | {finding.get('severity', 'N/A')} | "
                f"{finding.get('resource_id', 'N/A')[:30]} | {controls} |"
            )

        return "\n".join(lines)

    def _generate_exceptions_section(self) -> str:
        """Generate exceptions section of the report."""
        exceptions = self._get_exceptions_summary()

        if exceptions["active"] == 0:
            return "_No active risk exceptions._\n"

        lines = [
            f"**Active Exceptions:** {exceptions['active']}\n",
            "| Exception | Control | Expires | Approved By |",
            "|-----------|---------|---------|-------------|"
        ]

        for exc in exceptions.get("items", []):
            if exc.get("status") == "approved":
                lines.append(
                    f"| {exc.get('title', 'Unknown')[:40]} | {exc.get('control', 'N/A')} | "
                    f"{exc.get('expires_at', 'N/A')[:10]} | {exc.get('approved_by', 'N/A')} |"
                )

        return "\n".join(lines)

    def _generate_control_recommendations(self, control_id: str, assessment: ControlAssessment) -> str:
        """Generate recommendations for a specific control."""
        recs = []

        if assessment.status == ComplianceStatus.NOT_ASSESSED:
            recs.append("- Collect evidence to demonstrate control implementation")
            recs.append("- Document control procedures and policies")

        if assessment.findings_count > 0:
            recs.append(f"- Address {assessment.findings_count} open finding(s)")
            recs.append("- Implement automated remediation where possible")

        if assessment.evidence_count < 3:
            recs.append("- Gather additional evidence to strengthen control documentation")

        if not recs:
            recs.append("- Continue current practices")
            recs.append("- Monitor for any changes that may affect compliance")

        return "\n".join(recs)

    def save_report(self, report_content: str, report_type: ReportType, filename: str = None) -> str:
        """Save report to S3 and return the S3 key."""
        if not self.reports_bucket:
            logger.warning("No reports bucket configured")
            return ""

        timestamp = datetime.utcnow()
        if not filename:
            filename = f"{report_type.value}_{timestamp.strftime('%Y%m%d_%H%M%S')}.md"

        s3_key = f"reports/{timestamp.strftime('%Y/%m')}/{filename}"

        self.s3.put_object(
            Bucket=self.reports_bucket,
            Key=s3_key,
            Body=report_content.encode("utf-8"),
            ContentType="text/markdown",
            Metadata={
                "report-type": report_type.value,
                "generated-at": timestamp.isoformat(),
            }
        )

        logger.info(f"Report saved to s3://{self.reports_bucket}/{s3_key}")
        return s3_key

    def save_document(
        self,
        document_buffer: Any,
        report_type: ReportType,
        format: str = "docx",
        filename: str = None
    ) -> str:
        """
        Save a document (Word/PDF) to S3 and return the S3 key.

        Args:
            document_buffer: BytesIO buffer containing the document
            report_type: Type of report
            format: Document format ('docx' or 'pdf')
            filename: Optional custom filename

        Returns:
            S3 key where document was saved
        """
        if not self.reports_bucket:
            logger.warning("No reports bucket configured")
            return ""

        timestamp = datetime.utcnow()
        if not filename:
            filename = f"{report_type.value}_{timestamp.strftime('%Y%m%d_%H%M%S')}.{format}"

        s3_key = f"reports/{timestamp.strftime('%Y/%m')}/{filename}"

        # Determine content type
        content_types = {
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'pdf': 'application/pdf'
        }
        content_type = content_types.get(format, 'application/octet-stream')

        self.s3.put_object(
            Bucket=self.reports_bucket,
            Key=s3_key,
            Body=document_buffer.getvalue(),
            ContentType=content_type,
            Metadata={
                "report-type": report_type.value,
                "generated-at": timestamp.isoformat(),
                "format": format
            }
        )

        logger.info(f"Document saved to s3://{self.reports_bucket}/{s3_key}")
        return s3_key

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for downloading a report from S3.

        Args:
            s3_key: The S3 key of the report
            expiration: URL expiration time in seconds (default 1 hour)

        Returns:
            Presigned URL for downloading the report
        """
        if not self.reports_bucket or not s3_key:
            return ""

        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.reports_bucket,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            logger.info(f"Generated presigned URL for {s3_key} (expires in {expiration}s)")
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return ""

    def generate_executive_summary_pdf(
        self,
        audit_period_start: str,
        audit_period_end: str,
        organization_name: str = "Organization"
    ) -> tuple[bytes, dict]:
        """
        Generate executive summary as professional PDF.

        Returns:
            Tuple of (PDF bytes, report data dict)
        """
        from services.pdf_generator import PDFReportGenerator

        # Get data
        coverage = self.evidence_collector.get_control_coverage()
        findings_summary = self._get_findings_summary()
        exceptions_summary = self._get_exceptions_summary()

        # Calculate compliance score
        compliance_score = coverage["coverage_percent"]
        if findings_summary["critical"] > 0:
            compliance_score *= 0.7  # Penalty for critical findings

        # Structure data for PDF
        report_data = {
            'report_type': 'SOC 2 Executive Summary',
            'organization': organization_name,
            'audit_period': f'{audit_period_start} to {audit_period_end}',
            'generated_at': datetime.utcnow().strftime('%B %d, %Y'),
            'compliance_score': compliance_score,
            'executive_summary': self._generate_executive_text(coverage, findings_summary),
            'total_controls': len(coverage["covered"]) + len(coverage["missing"]),
            'controls_passed': len(coverage["covered"]),
            'total_findings': findings_summary["total"],
            'findings_by_severity': {
                'critical': findings_summary["critical"],
                'high': findings_summary["high"],
                'medium': findings_summary["medium"],
                'low': findings_summary["low"]
            },
            'controls': self._format_controls_for_pdf(coverage, findings_summary),
            'findings': self._format_findings_for_pdf(findings_summary.get('findings', []))
        }

        # Generate PDF
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_pdf(report_data)

        return pdf_bytes, report_data

    def generate_full_audit_pdf(
        self,
        audit_period_start: str,
        audit_period_end: str,
        organization_name: str = "Organization"
    ) -> tuple[bytes, dict]:
        """
        Generate full audit report as professional PDF.

        Returns:
            Tuple of (PDF bytes, report data dict)
        """
        from services.pdf_generator import PDFReportGenerator

        # Get data
        coverage = self.evidence_collector.get_control_coverage()
        findings_summary = self._get_findings_summary()
        exceptions_summary = self._get_exceptions_summary()

        # Calculate compliance score
        compliance_score = coverage["coverage_percent"]
        if findings_summary["critical"] > 0:
            compliance_score *= 0.7

        # Structure comprehensive data for PDF
        report_data = {
            'report_type': 'SOC 2 Full Audit Report',
            'organization': organization_name,
            'audit_period': f'{audit_period_start} to {audit_period_end}',
            'generated_at': datetime.utcnow().strftime('%B %d, %Y'),
            'compliance_score': compliance_score,
            'executive_summary': self._generate_executive_text(coverage, findings_summary),
            'total_controls': len(coverage["covered"]) + len(coverage["missing"]),
            'controls_passed': len(coverage["covered"]),
            'total_findings': findings_summary["total"],
            'findings_by_severity': {
                'critical': findings_summary["critical"],
                'high': findings_summary["high"],
                'medium': findings_summary["medium"],
                'low': findings_summary["low"]
            },
            'controls': self._format_controls_for_pdf(coverage, findings_summary, detailed=True),
            'findings': self._format_findings_for_pdf(findings_summary.get('findings', []), detailed=True)
        }

        # Generate PDF
        pdf_gen = PDFReportGenerator()
        pdf_bytes = pdf_gen.generate_pdf(report_data)

        return pdf_bytes, report_data

    def _generate_executive_text(self, coverage: dict, findings_summary: dict) -> str:
        """Generate concise executive summary text."""
        total_controls = len(coverage["covered"]) + len(coverage["missing"])
        coverage_pct = coverage["coverage_percent"]

        if coverage_pct >= 90 and findings_summary["critical"] == 0:
            status = "The organization demonstrates strong compliance posture"
        elif coverage_pct >= 70:
            status = "The organization demonstrates partial compliance with areas requiring attention"
        else:
            status = "The organization requires significant remediation to achieve compliance"

        return f"""{status}. Assessment covers {len(coverage['covered'])} of {total_controls} SOC 2 controls ({coverage_pct:.0f}% coverage). {findings_summary['total']} findings identified across all severity levels, including {findings_summary['critical']} critical issues requiring immediate attention."""

    def _format_controls_for_pdf(self, coverage: dict, findings_summary: dict, detailed: bool = False) -> list[dict]:
        """Format control data for PDF table."""
        controls = []

        # Map controls to their status
        for control_id in coverage["covered"]:
            evidence_count = len(coverage["control_evidence"].get(control_id, []))
            findings_count = len([f for f in findings_summary.get("findings", [])
                                if control_id in f.get("control_ids", [])])

            controls.append({
                'control_id': control_id,
                'control_name': SOC2_CONTROL_DESCRIPTIONS.get(control_id, "").split(":")[1].strip()
                              if ":" in SOC2_CONTROL_DESCRIPTIONS.get(control_id, "") else "N/A",
                'status': 'compliant' if findings_count == 0 else 'non-compliant',
                'evidence_count': evidence_count,
                'findings_count': findings_count
            })

        # Add missing controls
        for control_id in coverage["missing"]:
            controls.append({
                'control_id': control_id,
                'control_name': SOC2_CONTROL_DESCRIPTIONS.get(control_id, "").split(":")[1].strip()
                              if ":" in SOC2_CONTROL_DESCRIPTIONS.get(control_id, "") else "N/A",
                'status': 'not_assessed',
                'evidence_count': 0,
                'findings_count': 0
            })

        # Sort by control ID
        controls.sort(key=lambda x: x['control_id'])

        return controls

    def _format_findings_for_pdf(self, findings: list, detailed: bool = False) -> list[dict]:
        """Format findings data for PDF."""
        formatted = []

        for finding in findings[:20]:  # Limit to top 20 for readability
            formatted.append({
                'title': finding.get('title', 'N/A'),
                'severity': finding.get('severity', 'MEDIUM').upper(),
                'resource_id': finding.get('resource_id', 'N/A'),
                'description': finding.get('description', 'N/A')[:200] + '...'
                             if len(finding.get('description', '')) > 200 and not detailed
                             else finding.get('description', 'N/A'),
                'remediation_steps': finding.get('remediation_steps', 'N/A')[:300] + '...'
                                   if len(finding.get('remediation_steps', '')) > 300 and not detailed
                                   else finding.get('remediation_steps', 'N/A')
            })

        return formatted

    def save_pdf_report(self, pdf_bytes: bytes, report_type: ReportType) -> str:
        """
        Save PDF report to S3 and return the S3 key.

        Args:
            pdf_bytes: PDF content as bytes
            report_type: Type of report

        Returns:
            S3 key where PDF was saved
        """
        if not self.reports_bucket:
            logger.warning("No reports bucket configured")
            return ""

        timestamp = datetime.utcnow()
        filename = f"{report_type.value}_{timestamp.strftime('%Y%m%d_%H%M%S')}.pdf"
        s3_key = f"reports/{timestamp.strftime('%Y/%m')}/{filename}"

        self.s3.put_object(
            Bucket=self.reports_bucket,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            ContentDisposition=f'attachment; filename="{filename}"',
            Metadata={
                "report-type": report_type.value,
                "generated-at": timestamp.isoformat(),
            }
        )

        logger.info(f"PDF report saved to s3://{self.reports_bucket}/{s3_key}")
        return s3_key
