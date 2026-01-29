"""
Scanning Tools for AgentCore.

Wraps EvidenceCollector scanning functions as AgentCore Tools so that
agents can intelligently decide what AWS resources to scan based on user questions.

These tools replace static keyword matching with AI-driven intelligent scanning.
"""

from typing import Optional
import json
from dataclasses import dataclass

from services.evidence_collector import EvidenceCollector
from services.agent_core import Tool
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScanResult:
    """Result from a scan operation."""
    success: bool
    resource_type: str
    evidence_count: int
    summary: str
    details: dict


def create_scanning_tools(collector: EvidenceCollector) -> list[Tool]:
    """
    Create all scanning tools for AgentCore using the provided EvidenceCollector.

    Args:
        collector: Initialized EvidenceCollector instance

    Returns:
        List of Tool objects for AgentCore registration
    """

    def scan_iam() -> str:
        """
        Scan IAM resources for access control compliance.

        Scans:
        - IAM users with MFA status
        - IAM password policy
        - IAM roles and their permissions
        - Access keys and their age

        Returns:
            JSON string with scan results
        """
        try:
            logger.info("Scanning IAM resources")
            evidence_items = collector.collect_iam_evidence()

            # Summarize findings
            user_count = sum(1 for e in evidence_items if "iam_user" in e.resource_type)
            role_count = sum(1 for e in evidence_items if "iam_role" in e.resource_type)
            policy_count = sum(1 for e in evidence_items if "iam_policy" in e.resource_type)

            # Check for MFA issues
            users_without_mfa = []
            password_policy_missing = False

            for evidence in evidence_items:
                metadata = evidence.metadata if hasattr(evidence, 'metadata') else {}
                if "iam_user" in evidence.resource_type and not metadata.get('mfa_enabled', True):
                    users_without_mfa.append(metadata.get('user_name', 'Unknown'))
                if "Password Policy - NOT CONFIGURED" in evidence.title:
                    password_policy_missing = True

            result = ScanResult(
                success=True,
                resource_type="IAM",
                evidence_count=len(evidence_items),
                summary=f"Scanned {user_count} users, {role_count} roles, {policy_count} policies",
                details={
                    "user_count": user_count,
                    "role_count": role_count,
                    "policy_count": policy_count,
                    "users_without_mfa": users_without_mfa,
                    "password_policy_configured": not password_policy_missing,
                    "evidence_ids": [e.evidence_id for e in evidence_items[:10]]  # Sample
                }
            )

            return json.dumps(result.__dict__, indent=2)

        except Exception as e:
            logger.error(f"Error scanning IAM: {e}")
            return json.dumps({
                "success": False,
                "resource_type": "IAM",
                "error": str(e)
            })

    def scan_s3() -> str:
        """
        Scan S3 buckets for security compliance.

        Scans:
        - Bucket encryption settings
        - Public access blocks
        - Versioning status
        - Access logging configuration

        Returns:
            JSON string with scan results
        """
        try:
            logger.info("Scanning S3 buckets")
            evidence_items = collector.collect_s3_evidence()

            # Analyze bucket security
            unencrypted_buckets = []
            public_buckets = []
            no_versioning = []

            for evidence in evidence_items:
                metadata = evidence.metadata if hasattr(evidence, 'metadata') else {}
                bucket_name = metadata.get('bucket_name', 'Unknown')

                if metadata.get('encryption') is None:
                    unencrypted_buckets.append(bucket_name)

                public_block = metadata.get('public_access_block', {})
                if not public_block or not all([
                    public_block.get('BlockPublicAcls'),
                    public_block.get('BlockPublicPolicy'),
                    public_block.get('IgnorePublicAcls'),
                    public_block.get('RestrictPublicBuckets')
                ]):
                    public_buckets.append(bucket_name)

                if metadata.get('versioning') in ['Disabled', 'Suspended', None]:
                    no_versioning.append(bucket_name)

            result = ScanResult(
                success=True,
                resource_type="S3",
                evidence_count=len(evidence_items),
                summary=f"Scanned {len(evidence_items)} buckets",
                details={
                    "bucket_count": len(evidence_items),
                    "unencrypted_buckets": unencrypted_buckets,
                    "public_access_issues": public_buckets,
                    "versioning_disabled": no_versioning,
                    "evidence_ids": [e.evidence_id for e in evidence_items[:10]]
                }
            )

            return json.dumps(result.__dict__, indent=2)

        except Exception as e:
            logger.error(f"Error scanning S3: {e}")
            return json.dumps({
                "success": False,
                "resource_type": "S3",
                "error": str(e)
            })

    def scan_vpc() -> str:
        """
        Scan VPC and network security configuration.

        Scans:
        - VPCs and their CIDR blocks
        - VPC flow logs
        - Security groups (especially overly permissive ones)
        - Network ACLs

        Returns:
            JSON string with scan results
        """
        try:
            logger.info("Scanning VPC resources")
            evidence_items = collector.collect_vpc_evidence()

            # Analyze network security
            vpcs_without_flow_logs = []
            risky_security_groups = []

            for evidence in evidence_items:
                metadata = evidence.metadata if hasattr(evidence, 'metadata') else {}
                vpc_id = metadata.get('vpc_id', 'Unknown')

                if not metadata.get('flow_logs_enabled', False):
                    vpcs_without_flow_logs.append(vpc_id)

                for sg in metadata.get('risky_security_groups', []):
                    risky_security_groups.append({
                        'vpc_id': vpc_id,
                        'sg_id': sg.get('id'),
                        'sg_name': sg.get('name'),
                        'issue': sg.get('issue')
                    })

            result = ScanResult(
                success=True,
                resource_type="VPC",
                evidence_count=len(evidence_items),
                summary=f"Scanned {len(evidence_items)} VPCs",
                details={
                    "vpc_count": len(evidence_items),
                    "vpcs_without_flow_logs": vpcs_without_flow_logs,
                    "risky_security_groups": risky_security_groups,
                    "evidence_ids": [e.evidence_id for e in evidence_items[:10]]
                }
            )

            return json.dumps(result.__dict__, indent=2)

        except Exception as e:
            logger.error(f"Error scanning VPC: {e}")
            return json.dumps({
                "success": False,
                "resource_type": "VPC",
                "error": str(e)
            })

    def scan_cloudtrail() -> str:
        """
        Scan CloudTrail configuration for audit logging.

        Scans:
        - CloudTrail trails and their status
        - Multi-region trail configuration
        - Log file validation
        - CloudWatch Logs integration

        Returns:
            JSON string with scan results
        """
        try:
            logger.info("Scanning CloudTrail")
            evidence_items = collector.collect_cloudtrail_evidence()

            # Analyze trails
            multi_region_trails = []
            trails_with_validation = []
            trails_not_logging = []

            for evidence in evidence_items:
                metadata = evidence.metadata if hasattr(evidence, 'metadata') else {}
                trail_name = metadata.get('trail_name', 'Unknown')

                if metadata.get('is_multi_region', False):
                    multi_region_trails.append(trail_name)

                if metadata.get('log_file_validation', False):
                    trails_with_validation.append(trail_name)

                if not metadata.get('is_logging', False):
                    trails_not_logging.append(trail_name)

            result = ScanResult(
                success=True,
                resource_type="CloudTrail",
                evidence_count=len(evidence_items),
                summary=f"Scanned {len(evidence_items)} trails",
                details={
                    "trail_count": len(evidence_items),
                    "multi_region_trails": multi_region_trails,
                    "trails_with_validation": trails_with_validation,
                    "trails_not_logging": trails_not_logging,
                    "evidence_ids": [e.evidence_id for e in evidence_items[:10]]
                }
            )

            return json.dumps(result.__dict__, indent=2)

        except Exception as e:
            logger.error(f"Error scanning CloudTrail: {e}")
            return json.dumps({
                "success": False,
                "resource_type": "CloudTrail",
                "error": str(e)
            })

    def scan_security_hub() -> str:
        """
        Scan Security Hub for findings and enabled standards.

        Scans:
        - Enabled security standards (CIS, PCI-DSS, etc.)
        - Active findings by severity
        - Compliance status

        Returns:
            JSON string with scan results
        """
        try:
            logger.info("Scanning Security Hub")
            evidence_items = collector.collect_security_hub_evidence()

            # Analyze Security Hub data
            enabled_standards = []
            findings_by_severity = {}

            for evidence in evidence_items:
                metadata = evidence.metadata if hasattr(evidence, 'metadata') else {}

                # Extract enabled standards
                for standard in metadata.get('enabled_standards', []):
                    enabled_standards.append(standard.get('standard_arn', 'Unknown'))

                # Extract findings summary
                findings_by_severity = metadata.get('by_severity', {})

            result = ScanResult(
                success=True,
                resource_type="SecurityHub",
                evidence_count=len(evidence_items),
                summary=f"Scanned Security Hub ({len(enabled_standards)} standards enabled)",
                details={
                    "enabled_standards": enabled_standards,
                    "findings_by_severity": findings_by_severity,
                    "evidence_ids": [e.evidence_id for e in evidence_items[:10]]
                }
            )

            return json.dumps(result.__dict__, indent=2)

        except Exception as e:
            logger.error(f"Error scanning Security Hub: {e}")
            return json.dumps({
                "success": False,
                "resource_type": "SecurityHub",
                "error": str(e)
            })

    def scan_all() -> str:
        """
        Comprehensive scan of all AWS resources for compliance.

        Scans:
        - IAM (users, roles, policies, MFA)
        - S3 (encryption, public access, versioning)
        - VPC (flow logs, security groups, NACLs)
        - CloudTrail (audit logging)
        - Security Hub (findings, standards)

        Returns:
            JSON string with scan results from all categories
        """
        try:
            logger.info("Starting comprehensive scan")
            evidence_results = collector.collect_all_evidence()

            result = ScanResult(
                success=True,
                resource_type="ALL",
                evidence_count=sum(len(items) for items in evidence_results.values()),
                summary=f"Comprehensive scan completed",
                details={
                    "iam": len(evidence_results.get('iam', [])),
                    "s3": len(evidence_results.get('s3', [])),
                    "vpc": len(evidence_results.get('vpc', [])),
                    "cloudtrail": len(evidence_results.get('cloudtrail', [])),
                    "security_hub": len(evidence_results.get('security_hub', []))
                }
            )

            return json.dumps(result.__dict__, indent=2)

        except Exception as e:
            logger.error(f"Error in comprehensive scan: {e}")
            return json.dumps({
                "success": False,
                "resource_type": "ALL",
                "error": str(e)
            })

    # Create Tool definitions for AgentCore
    tools = [
        Tool(
            name="scan_iam",
            description="""Scan IAM resources for access control compliance.

Use this tool when the user asks about:
- IAM users, roles, or policies
- MFA (multi-factor authentication)
- Password policies
- Access keys
- User permissions or access control
- Authentication or authorization

Returns JSON with IAM configuration details, MFA status, and security issues.""",
            function=scan_iam,
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="scan_s3",
            description="""Scan S3 buckets for security compliance.

Use this tool when the user asks about:
- S3 buckets
- Bucket encryption
- Public access or bucket policies
- Versioning
- Data storage security
- Object storage

Returns JSON with bucket security settings, encryption status, and compliance issues.""",
            function=scan_s3,
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="scan_vpc",
            description="""Scan VPC and network security configuration.

Use this tool when the user asks about:
- VPCs or network configuration
- Security groups or firewalls
- Network ACLs
- VPC flow logs
- Network security or connectivity
- Subnets, route tables, or network infrastructure
- Web servers, EC2 instances, load balancers (infrastructure)
- Database connectivity (RDS, Aurora, Redshift)
- ETL infrastructure (Glue, DMS, data pipelines)

Returns JSON with VPC details, flow logs status, and security group issues.""",
            function=scan_vpc,
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="scan_cloudtrail",
            description="""Scan CloudTrail configuration for audit logging.

Use this tool when the user asks about:
- CloudTrail or audit logging
- API call logging or activity monitoring
- Log file validation
- Compliance audit trails
- Who did what in AWS

Returns JSON with trail configuration, logging status, and compliance details.""",
            function=scan_cloudtrail,
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="scan_security_hub",
            description="""Scan Security Hub for findings and enabled standards.

Use this tool when the user asks about:
- Security Hub findings
- Security standards (CIS, PCI-DSS)
- Overall security posture
- Compliance standards
- Security alerts or vulnerabilities

Returns JSON with enabled standards, findings by severity, and compliance status.""",
            function=scan_security_hub,
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="scan_all",
            description="""Comprehensive scan of all AWS resources for compliance.

Use this tool when the user asks about:
- Overall compliance status
- General security posture
- Multiple AWS services at once
- Comprehensive audit or assessment
- "Scan everything" type requests

Returns JSON with results from all scan categories (IAM, S3, VPC, CloudTrail, Security Hub).""",
            function=scan_all,
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

    return tools
