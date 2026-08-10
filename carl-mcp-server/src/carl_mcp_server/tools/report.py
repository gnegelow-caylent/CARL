"""
CARL Report Generation Tool

Generate compliance reports for audits.
"""
import os
import logging
import boto3
from datetime import datetime
from typing import Dict, Any
from mcp.types import Tool

logger = logging.getLogger(__name__)

def carl_report_tool() -> Tool:
    """Define the carl_generate_report MCP tool."""
    return Tool(
        name="carl_generate_report",
        description="""Generate compliance reports for auditors.

Creates comprehensive compliance reports based on collected evidence,
findings, and control assessments.

Report types:
- **executive**: Executive summary for leadership
- **full**: Detailed compliance report with all evidence
- **control**: Specific control assessment (e.g., CC6.1, HIPAA §164.312)

Supported frameworks:
- SOC 2 (Trust Service Criteria)
- HIPAA (Technical Safeguards)
- PCI DSS (Requirements)
- NIST CSF 2.0 (Functions)

Report includes:
- Control compliance status
- Evidence references
- Findings and gaps
- Remediation recommendations
- Audit trail

Example:
  report_type: "executive"
  framework: "soc2"

Returns formatted report with option to save to S3.""",
        inputSchema={
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "description": "Report type: 'executive', 'full', or 'control'",
                    "enum": ["executive", "full", "control"]
                },
                "framework": {
                    "type": "string",
                    "description": "Compliance framework: 'soc2', 'hipaa', 'pci', 'nist'",
                    "default": "soc2"
                },
                "control_id": {
                    "type": "string",
                    "description": "Specific control ID (required for 'control' report type)"
                },
                "save_to_s3": {
                    "type": "boolean",
                    "description": "Save report to S3 bucket",
                    "default": False
                }
            },
            "required": ["report_type"]
        }
    )

async def handle_carl_report(arguments: Dict[str, Any]) -> str:
    """Execute the carl_generate_report tool."""
    report_type = arguments.get("report_type", "executive")
    framework = arguments.get("framework", "soc2").lower()
    control_id = arguments.get("control_id")
    save_to_s3 = arguments.get("save_to_s3", False)

    logger.info(f"Generating {report_type} report for framework: {framework}")

    try:
        # Get AWS session
        profile = os.getenv("AWS_PROFILE")
        region = os.getenv("AWS_REGION", "us-east-1")

        if profile:
            session = boto3.Session(profile_name=profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)

        # Initialize report generator
        generator = ReportGenerator(session, framework)

        # Generate report
        if report_type == "executive":
            report = generator.generate_executive_report()
        elif report_type == "full":
            report = generator.generate_full_report()
        elif report_type == "control":
            if not control_id:
                return "❌ Error: control_id is required for control report type"
            report = generator.generate_control_report(control_id)
        else:
            return f"❌ Unknown report type: {report_type}"

        # Save to S3 if requested
        if save_to_s3:
            s3_location = generator.save_to_s3(report, report_type)
            report += f"\n\n---\n📄 Report saved to: {s3_location}"

        return report

    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
        return f"""❌ Report generation failed: {str(e)}

Please check:
1. AWS credentials are configured
2. Evidence has been collected (use carl_collect_evidence first)
3. DynamoDB tables deployed:
   cd carl-infrastructure/mcp-deployment
   terraform apply"""


class ReportGenerator:
    """Generates compliance reports from evidence."""

    def __init__(self, session: boto3.Session, framework: str = "soc2"):
        self.session = session
        self.framework = framework
        self.account_id = session.client('sts').get_caller_identity()['Account']
        self.region = session.region_name
        self.timestamp = datetime.utcnow().isoformat()

    def generate_executive_report(self) -> str:
        """Generate executive summary report."""
        # Query evidence and findings
        evidence_summary = self._get_evidence_summary()
        findings_summary = self._get_findings_summary()

        output = [
            f"# Executive Compliance Report",
            f"\n**Framework**: {self.framework.upper()}",
            f"**AWS Account**: {self.account_id}",
            f"**Region**: {self.region}",
            f"**Report Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"\n## Compliance Posture\n"
        ]

        # Overall score
        total_controls = evidence_summary.get("total_controls", 0)
        compliant_controls = evidence_summary.get("compliant_controls", 0)
        if evidence_summary.get("error"):
            output.append(f"**Overall Compliance**: ❌ {evidence_summary['error']}")
        elif total_controls > 0:
            score = (compliant_controls / total_controls) * 100
            output.append(f"**Overall Compliance**: {score:.1f}% ({compliant_controls}/{total_controls} controls)")
        else:
            output.append("**Overall Compliance**: No evidence collected yet. Run `carl_collect_evidence` first.")

        # Findings summary
        output.append(f"\n## Security Findings\n")
        if findings_summary.get("error"):
            output.append(f"❌ {findings_summary['error']}")
        else:
            critical = findings_summary.get("critical", 0)
            high = findings_summary.get("high", 0)
            medium = findings_summary.get("medium", 0)
            low = findings_summary.get("low", 0)

            if critical + high + medium + low > 0:
                output.append(f"- 🔴 Critical: {critical}")
                output.append(f"- 🟠 High: {high}")
                output.append(f"- 🟡 Medium: {medium}")
                output.append(f"- 🟢 Low: {low}")
            else:
                output.append("✅ No active findings")

        # Key gaps
        output.append(f"\n## Key Compliance Gaps\n")
        gaps = self._identify_compliance_gaps(evidence_summary)
        if gaps:
            for gap in gaps:
                output.append(f"- {gap}")
        else:
            output.append("✅ No critical gaps identified")

        # Recommendations
        output.append(f"\n## Recommendations\n")
        recommendations = self._generate_recommendations(evidence_summary, findings_summary)
        for i, rec in enumerate(recommendations, 1):
            output.append(f"{i}. {rec}")

        return "\n".join(output)

    def generate_full_report(self) -> str:
        """Generate full detailed report."""
        output = [
            f"# Full Compliance Report",
            f"\n**Framework**: {self.framework.upper()}",
            f"**AWS Account**: {self.account_id}",
            f"**Region**: {self.region}",
            f"**Report Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"\n## Executive Summary\n"
        ]

        # Add executive summary
        exec_summary = self.generate_executive_report()
        output.append(exec_summary.split("## Compliance Posture")[1])

        # Control-by-control analysis
        output.append(f"\n## Control Assessment\n")

        control_definitions = self._get_control_definitions()
        for control_id, control_info in control_definitions.items():
            output.append(f"\n### {control_id}: {control_info['name']}")
            output.append(f"**Description**: {control_info['description']}")

            # Get evidence for this control
            evidence = self._get_evidence_for_control(control_id)
            if evidence:
                output.append(f"**Status**: ✅ Evidence collected ({len(evidence)} items)")
                output.append(f"**Evidence**:")
                for ev in evidence[:3]:  # Show first 3
                    output.append(f"  - {ev['resource_type']}: {ev['resource_id']}")
                if len(evidence) > 3:
                    output.append(f"  - ... and {len(evidence)-3} more")
            else:
                output.append(f"**Status**: ⚠️ No evidence collected")

        return "\n".join(output)

    def generate_control_report(self, control_id: str) -> str:
        """Generate report for specific control."""
        output = [
            f"# Control Assessment Report",
            f"\n**Control ID**: {control_id}",
            f"**Framework**: {self.framework.upper()}",
            f"**AWS Account**: {self.account_id}",
            f"**Report Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"\n## Control Definition\n"
        ]

        # Get control details
        control_info = self._get_control_info(control_id)
        if not control_info:
            return f"❌ Control {control_id} not found in {self.framework} framework"

        output.append(f"**Name**: {control_info['name']}")
        output.append(f"**Description**: {control_info['description']}")
        output.append(f"**Category**: {control_info.get('category', 'N/A')}")

        # Evidence
        output.append(f"\n## Evidence\n")
        evidence = self._get_evidence_for_control(control_id)

        if evidence:
            output.append(f"**Total Evidence Items**: {len(evidence)}")
            output.append(f"\n### Evidence Details\n")

            for ev in evidence:
                output.append(f"#### {ev['resource_type']}: {ev['resource_id']}")
                output.append(f"- **Compliant**: {'✅ Yes' if ev.get('compliant') else '❌ No'}")
                output.append(f"- **Collected**: {ev.get('timestamp', 'Unknown')}")
                if ev.get('data'):
                    output.append(f"- **Configuration**: See evidence data")
                output.append("")
        else:
            output.append("⚠️ No evidence collected for this control")

        # Findings related to this control
        output.append(f"\n## Related Findings\n")
        findings = self._get_findings_for_control(control_id)
        if findings:
            for finding in findings:
                severity_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(finding.get("severity"), "⚠️")
                output.append(f"{severity_emoji} **{finding.get('severity')}**: {finding.get('title')}")
                output.append(f"  - Resource: {finding.get('resource_id')}")
                output.append("")
        else:
            output.append("✅ No findings related to this control")

        return "\n".join(output)

    def save_to_s3(self, report: str, report_type: str) -> str:
        """Save report to S3."""
        try:
            bucket = os.getenv("CARL_S3_REPORTS_BUCKET", "")
            if not bucket:
                return "S3 bucket not configured"

            s3 = self.session.client('s3')
            key = f"reports/{self.framework}/{report_type}/{self.timestamp}.md"

            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=report.encode('utf-8'),
                ContentType='text/markdown'
            )

            return f"s3://{bucket}/{key}"

        except Exception as e:
            logger.error(f"Failed to save to S3: {e}")
            return f"Failed to save: {str(e)}"

    def _get_evidence_summary(self) -> Dict[str, Any]:
        """Get summary of collected evidence."""
        try:
            table_name = os.getenv("CARL_DYNAMODB_EVIDENCE_TABLE", "carl-prod-evidence")
            dynamodb = self.session.resource('dynamodb')
            table = dynamodb.Table(table_name)

            # Query evidence
            response = table.scan(
                FilterExpression="framework = :fw",
                ExpressionAttributeValues={":fw": self.framework},
                Limit=100
            )

            items = response.get('Items', [])
            compliant = sum(1 for item in items if item.get('compliant', False))

            return {
                "total_controls": len(items),
                "compliant_controls": compliant,
                "evidence_count": len(items)
            }

        except Exception as e:
            error_name = type(e).__name__
            logger.error(f"Error getting evidence summary: {error_name}: {e}")

            # Distinguish between infrastructure errors and no evidence
            if "ResourceNotFoundException" in error_name or "not found" in str(e).lower():
                return {
                    "total_controls": 0,
                    "compliant_controls": 0,
                    "error": f"DynamoDB table '{table_name}' not found. Deploy CARL infrastructure first."
                }
            else:
                return {
                    "total_controls": 0,
                    "compliant_controls": 0,
                    "error": f"Failed to query evidence: {error_name}: {str(e)}"
                }

    def _get_findings_summary(self) -> Dict[str, int]:
        """Get summary of findings by severity."""
        try:
            table_name = os.getenv("CARL_DYNAMODB_FINDINGS_TABLE", "carl-dev-findings")
            dynamodb = self.session.resource('dynamodb')
            table = dynamodb.Table(table_name)

            response = table.scan(
                FilterExpression="account_id = :acc",
                ExpressionAttributeValues={":acc": self.account_id},
                Limit=100
            )

            items = response.get('Items', [])
            summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}

            for item in items:
                severity = item.get('severity', '').lower()
                if severity in summary:
                    summary[severity] += 1

            return summary

        except Exception as e:
            error_name = type(e).__name__
            logger.error(f"Error getting findings summary: {error_name}: {e}")

            # Distinguish between infrastructure errors and no findings
            if "ResourceNotFoundException" in error_name or "not found" in str(e).lower():
                return {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "error": f"DynamoDB table '{table_name}' not found. Deploy CARL infrastructure first."
                }
            else:
                return {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "error": f"Failed to query findings: {error_name}: {str(e)}"
                }

    def _identify_compliance_gaps(self, evidence_summary: Dict[str, Any]) -> list:
        """Identify key compliance gaps."""
        gaps = []

        if evidence_summary.get("total_controls", 0) == 0:
            gaps.append("No evidence collected - run carl_collect_evidence")
        else:
            compliance_rate = (evidence_summary.get("compliant_controls", 0) / evidence_summary.get("total_controls", 1)) * 100
            if compliance_rate < 70:
                gaps.append(f"Low compliance rate ({compliance_rate:.0f}%) - immediate attention required")

        return gaps if gaps else ["No critical gaps identified"]

    def _generate_recommendations(self, evidence_summary: Dict[str, Any], findings_summary: Dict[str, int]) -> list:
        """Generate remediation recommendations."""
        recs = []

        if findings_summary.get("critical", 0) > 0:
            recs.append("Address CRITICAL findings immediately - potential security breach risk")
        if findings_summary.get("high", 0) > 0:
            recs.append("Remediate HIGH severity findings within 7 days")
        if evidence_summary.get("total_controls", 0) == 0:
            recs.append("Run evidence collection: carl_collect_evidence")
        else:
            compliance_rate = (evidence_summary.get("compliant_controls", 0) / evidence_summary.get("total_controls", 1)) * 100
            if compliance_rate < 100:
                recs.append(f"Improve compliance from {compliance_rate:.0f}% to 100%")

        return recs if recs else ["Maintain current security posture"]

    def _get_control_definitions(self) -> Dict[str, Dict[str, str]]:
        """Get control definitions for framework."""
        # Control definitions mapped to what the scanner actually checks
        if self.framework == "soc2":
            return {
                "CC6.1": {"name": "Logical Access", "description": "Entity implements logical access controls", "category": "Security"},
                "CC6.2": {"name": "MFA & Authentication", "description": "Entity implements multi-factor authentication", "category": "Security"},
                "CC6.7": {"name": "Data Classification", "description": "Entity protects confidential information", "category": "Security"},
                "CC7.2": {"name": "Monitoring", "description": "Entity monitors system and takes action", "category": "Operations"},
                "CC7.3": {"name": "Logging & Alerting", "description": "Entity evaluates security events and anomalies", "category": "Operations"}
            }
        elif self.framework == "pci":
            return {
                "3.4": {"name": "Encryption at Rest", "description": "PAN is rendered unreadable anywhere it is stored", "category": "Data Protection"},
                "3.5": {"name": "Key Management", "description": "Document and implement procedures to protect cryptographic keys", "category": "Data Protection"},
                "8.1.6": {"name": "Password Policy", "description": "Password parameters are configured to require minimum password length", "category": "Access Control"},
                "8.2.3": {"name": "Password Strength", "description": "Passwords must meet minimum complexity requirements", "category": "Access Control"},
                "8.3": {"name": "Multi-Factor Authentication", "description": "MFA implemented for all access to CDE", "category": "Access Control"},
                "10.1": {"name": "Audit Trails", "description": "Processes and mechanisms for implementing audit trails", "category": "Monitoring"},
                "10.2": {"name": "Automated Audit Trails", "description": "Audit logs record user activities and exceptions", "category": "Monitoring"},
                "10.3": {"name": "Audit Log Protection", "description": "Audit logs are protected from destruction and unauthorized modification", "category": "Monitoring"},
                "11.5": {"name": "Change Detection", "description": "Deploy a change-detection mechanism to alert personnel", "category": "Security Monitoring"}
            }
        elif self.framework == "hipaa":
            return {
                "164.308(a)(1)(ii)(D)": {"name": "Information System Activity Review", "description": "Implement procedures to regularly review records of information system activity", "category": "Administrative Safeguards"},
                "164.308(a)(5)(ii)(D)": {"name": "Password Management", "description": "Procedures for creating, changing, and safeguarding passwords", "category": "Administrative Safeguards"},
                "164.312(a)(2)(i)": {"name": "Unique User Identification", "description": "Assign unique name/number for identifying and tracking user identity", "category": "Access Control"},
                "164.312(a)(2)(iv)": {"name": "Encryption and Decryption", "description": "Implement mechanism to encrypt and decrypt ePHI", "category": "Access Control"},
                "164.312(b)": {"name": "Audit Controls", "description": "Implement hardware, software, and/or procedural mechanisms that record and examine activity", "category": "Audit Controls"},
                "164.312(e)(2)(ii)": {"name": "Encryption", "description": "Implement mechanism to encrypt ePHI whenever deemed appropriate", "category": "Transmission Security"}
            }
        elif self.framework == "nist":
            return {
                "PR.AC-1": {"name": "Identity Management", "description": "Identities and credentials are issued, managed, verified, revoked for authorized devices/users", "category": "Protect - Access Control"},
                "PR.AC-7": {"name": "Authentication", "description": "Users and devices are authenticated commensurate with the risk", "category": "Protect - Access Control"},
                "PR.DS-1": {"name": "Data-at-Rest Protection", "description": "Data-at-rest is protected", "category": "Protect - Data Security"},
                "PR.DS-5": {"name": "Data-in-Transit Protection", "description": "Protections against data leaks are implemented", "category": "Protect - Data Security"},
                "PR.PT-1": {"name": "Audit Logs", "description": "Audit/log records are determined, documented, implemented, and reviewed", "category": "Protect - Protective Technology"},
                "DE.AE-3": {"name": "Event Analysis", "description": "Event data are collected and correlated from multiple sources and sensors", "category": "Detect - Anomalies and Events"},
                "DE.CM-1": {"name": "Network Monitoring", "description": "The network is monitored to detect potential cybersecurity events", "category": "Detect - Continuous Monitoring"},
                "DE.CM-7": {"name": "Unauthorized Activity Monitoring", "description": "Monitoring for unauthorized personnel, connections, devices, and software", "category": "Detect - Continuous Monitoring"},
                "RS.AN-1": {"name": "Incident Investigation", "description": "Notifications from detection systems are investigated", "category": "Respond - Analysis"}
            }
        return {}

    def _get_control_info(self, control_id: str) -> Dict[str, str]:
        """Get information about a specific control."""
        controls = self._get_control_definitions()
        return controls.get(control_id)

    def _get_evidence_for_control(self, control_id: str) -> list:
        """Get evidence items for a specific control."""
        try:
            table_name = os.getenv("CARL_DYNAMODB_EVIDENCE_TABLE", "carl-prod-evidence")
            dynamodb = self.session.resource('dynamodb')
            table = dynamodb.Table(table_name)

            response = table.scan(
                FilterExpression="contains(controls, :ctrl)",
                ExpressionAttributeValues={":ctrl": control_id},
                Limit=50
            )

            return response.get('Items', [])

        except Exception as e:
            logger.error(f"Error getting evidence for control: {e}")
            return []

    def _get_findings_for_control(self, control_id: str) -> list:
        """Get findings related to a specific control."""
        # Simplified - would map findings to controls in full implementation
        return []
