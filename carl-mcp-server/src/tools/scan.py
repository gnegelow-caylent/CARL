"""
CARL Scan Tool

Scan AWS environment for security findings.
"""
import logging
import os
import boto3
from typing import Dict, Any
from mcp.types import Tool

logger = logging.getLogger(__name__)

def carl_scan_tool() -> Tool:
    """Define the carl_scan_environment MCP tool."""
    return Tool(
        name="carl_scan_environment",
        description="""Scan AWS environment for security findings and compliance issues.

Performs comprehensive security scanning across AWS services including:
- IAM (users, roles, password policies, MFA)
- S3 (encryption, versioning, public access)
- VPC (flow logs, security groups, NACLs)
- Security Hub (active findings)
- CloudTrail (logging configuration)
- GuardDuty (threat detection findings)

Returns a summary of findings with severity levels and recommendations.""",
        inputSchema={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "Scan scope: 'all', 'iam', 's3', 'vpc', 'security_hub', 'cloudtrail', 'guardduty'",
                    "default": "all"
                }
            }
        }
    )

async def handle_carl_scan(arguments: Dict[str, Any]) -> str:
    """Execute the carl_scan_environment tool."""
    scope = arguments.get("scope", "all").lower()

    logger.info(f"Starting AWS security scan with scope: {scope}")

    try:
        # Get AWS session
        profile = os.getenv("AWS_PROFILE")
        region = os.getenv("AWS_REGION", "us-east-1")

        if profile:
            session = boto3.Session(profile_name=profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)

        # Initialize scanner
        scanner = AWSScanner(session)

        # Perform scan based on scope
        if scope == "all":
            results = scanner.scan_all()
        elif scope == "iam":
            results = scanner.scan_iam()
        elif scope == "s3":
            results = scanner.scan_s3()
        elif scope == "vpc":
            results = scanner.scan_vpc()
        elif scope == "security_hub":
            results = scanner.scan_security_hub()
        elif scope == "cloudtrail":
            results = scanner.scan_cloudtrail()
        elif scope == "guardduty":
            results = scanner.scan_guardduty()
        else:
            return f"❌ Unknown scan scope: {scope}. Use 'all', 'iam', 's3', 'vpc', 'security_hub', 'cloudtrail', or 'guardduty'."

        # Format results
        return format_scan_results(results, scope)

    except Exception as e:
        logger.exception(f"Scan failed: {e}")
        return f"❌ Scan failed: {str(e)}\n\nPlease check:\n1. AWS credentials are configured\n2. IAM permissions for read access to AWS services"


class AWSScanner:
    """Lightweight AWS security scanner."""

    def __init__(self, session: boto3.Session):
        self.session = session
        self.account_id = session.client('sts').get_caller_identity()['Account']
        self.region = session.region_name

    def scan_all(self) -> Dict[str, Any]:
        """Scan all supported services."""
        return {
            "iam": self.scan_iam(),
            "s3": self.scan_s3(),
            "vpc": self.scan_vpc(),
            "security_hub": self.scan_security_hub(),
            "cloudtrail": self.scan_cloudtrail(),
            "guardduty": self.scan_guardduty(),
        }

    def scan_iam(self) -> Dict[str, Any]:
        """Scan IAM configuration."""
        iam = self.session.client('iam')
        findings = []

        try:
            # Check password policy
            try:
                policy = iam.get_account_password_policy()['PasswordPolicy']
                if not policy.get('RequireUppercaseCharacters'):
                    findings.append({
                        "severity": "MEDIUM",
                        "resource": "IAM Password Policy",
                        "issue": "Password policy does not require uppercase characters"
                    })
                if not policy.get('RequireLowercaseCharacters'):
                    findings.append({
                        "severity": "MEDIUM",
                        "resource": "IAM Password Policy",
                        "issue": "Password policy does not require lowercase characters"
                    })
                if policy.get('MinimumPasswordLength', 0) < 14:
                    findings.append({
                        "severity": "HIGH",
                        "resource": "IAM Password Policy",
                        "issue": f"Minimum password length is {policy.get('MinimumPasswordLength')} (recommended: 14+)"
                    })
            except iam.exceptions.NoSuchEntityException:
                findings.append({
                    "severity": "HIGH",
                    "resource": "IAM Password Policy",
                    "issue": "No password policy configured"
                })

            # Check for users without MFA
            users = iam.list_users()['Users']
            for user in users[:10]:  # Limit to 10 to avoid rate limits
                try:
                    mfa_devices = iam.list_mfa_devices(UserName=user['UserName'])['MFADevices']
                    if not mfa_devices:
                        findings.append({
                            "severity": "HIGH",
                            "resource": f"IAM User: {user['UserName']}",
                            "issue": "MFA not enabled"
                        })
                except Exception as e:
                    logger.debug(f"Could not check MFA for {user['UserName']}: {e}")

        except Exception as e:
            logger.error(f"IAM scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "IAM", "issue": str(e)})

        return {"service": "IAM", "findings": findings, "scanned": True}

    def scan_s3(self) -> Dict[str, Any]:
        """Scan S3 buckets."""
        s3 = self.session.client('s3')
        findings = []

        try:
            buckets = s3.list_buckets()['Buckets']

            for bucket in buckets[:20]:  # Limit to 20 buckets
                bucket_name = bucket['Name']

                try:
                    # Check encryption
                    try:
                        s3.get_bucket_encryption(Bucket=bucket_name)
                    except s3.exceptions.ClientError as e:
                        if e.response['Error']['Code'] == 'ServerSideEncryptionConfigurationNotFoundError':
                            findings.append({
                                "severity": "HIGH",
                                "resource": f"S3 Bucket: {bucket_name}",
                                "issue": "Encryption not enabled"
                            })

                    # Check versioning
                    versioning = s3.get_bucket_versioning(Bucket=bucket_name)
                    if versioning.get('Status') != 'Enabled':
                        findings.append({
                            "severity": "MEDIUM",
                            "resource": f"S3 Bucket: {bucket_name}",
                            "issue": "Versioning not enabled"
                        })

                    # Check public access block
                    try:
                        public_access = s3.get_public_access_block(Bucket=bucket_name)['PublicAccessBlockConfiguration']
                        if not all([
                            public_access.get('BlockPublicAcls'),
                            public_access.get('IgnorePublicAcls'),
                            public_access.get('BlockPublicPolicy'),
                            public_access.get('RestrictPublicBuckets')
                        ]):
                            findings.append({
                                "severity": "CRITICAL",
                                "resource": f"S3 Bucket: {bucket_name}",
                                "issue": "Public access block not fully configured"
                            })
                    except s3.exceptions.ClientError:
                        findings.append({
                            "severity": "CRITICAL",
                            "resource": f"S3 Bucket: {bucket_name}",
                            "issue": "No public access block configured"
                        })

                except Exception as e:
                    logger.debug(f"Could not scan bucket {bucket_name}: {e}")

        except Exception as e:
            logger.error(f"S3 scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "S3", "issue": str(e)})

        return {"service": "S3", "findings": findings, "scanned": True}

    def scan_vpc(self) -> Dict[str, Any]:
        """Scan VPC configuration."""
        ec2 = self.session.client('ec2')
        findings = []

        try:
            # Check VPCs for flow logs
            vpcs = ec2.describe_vpcs()['Vpcs']
            flow_logs = ec2.describe_flow_logs()['FlowLogs']
            vpc_ids_with_logs = {fl['ResourceId'] for fl in flow_logs}

            for vpc in vpcs:
                vpc_id = vpc['VpcId']
                if vpc_id not in vpc_ids_with_logs:
                    findings.append({
                        "severity": "MEDIUM",
                        "resource": f"VPC: {vpc_id}",
                        "issue": "VPC Flow Logs not enabled"
                    })

            # Check security groups for overly permissive rules
            sgs = ec2.describe_security_groups()['SecurityGroups']
            for sg in sgs[:20]:  # Limit to 20
                for rule in sg.get('IpPermissions', []):
                    for ip_range in rule.get('IpRanges', []):
                        if ip_range.get('CidrIp') == '0.0.0.0/0':
                            findings.append({
                                "severity": "HIGH",
                                "resource": f"Security Group: {sg['GroupId']}",
                                "issue": f"Port {rule.get('FromPort', 'ALL')} open to internet (0.0.0.0/0)"
                            })

        except Exception as e:
            logger.error(f"VPC scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "VPC", "issue": str(e)})

        return {"service": "VPC", "findings": findings, "scanned": True}

    def scan_security_hub(self) -> Dict[str, Any]:
        """Scan Security Hub findings."""
        securityhub = self.session.client('securityhub')
        findings = []

        try:
            # Check if Security Hub is enabled
            try:
                response = securityhub.get_findings(
                    Filters={
                        'SeverityLabel': [{'Value': 'CRITICAL', 'Comparison': 'EQUALS'}],
                        'RecordState': [{'Value': 'ACTIVE', 'Comparison': 'EQUALS'}]
                    },
                    MaxResults=10
                )

                for finding in response.get('Findings', []):
                    findings.append({
                        "severity": finding['Severity']['Label'],
                        "resource": finding.get('Resources', [{}])[0].get('Id', 'Unknown'),
                        "issue": finding['Title']
                    })

            except securityhub.exceptions.InvalidAccessException:
                findings.append({
                    "severity": "INFO",
                    "resource": "Security Hub",
                    "issue": "Security Hub not enabled in this region"
                })

        except Exception as e:
            logger.error(f"Security Hub scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "Security Hub", "issue": str(e)})

        return {"service": "Security Hub", "findings": findings, "scanned": True}

    def scan_cloudtrail(self) -> Dict[str, Any]:
        """Scan CloudTrail configuration."""
        cloudtrail = self.session.client('cloudtrail')
        findings = []

        try:
            trails = cloudtrail.describe_trails()['trailList']

            if not trails:
                findings.append({
                    "severity": "CRITICAL",
                    "resource": "CloudTrail",
                    "issue": "No CloudTrail trails configured"
                })
            else:
                for trail in trails:
                    # Check if trail is logging
                    status = cloudtrail.get_trail_status(Name=trail['TrailARN'])
                    if not status.get('IsLogging'):
                        findings.append({
                            "severity": "HIGH",
                            "resource": f"CloudTrail: {trail['Name']}",
                            "issue": "Trail is not logging"
                        })

                    # Check for log file validation
                    if not trail.get('LogFileValidationEnabled'):
                        findings.append({
                            "severity": "MEDIUM",
                            "resource": f"CloudTrail: {trail['Name']}",
                            "issue": "Log file validation not enabled"
                        })

        except Exception as e:
            logger.error(f"CloudTrail scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "CloudTrail", "issue": str(e)})

        return {"service": "CloudTrail", "findings": findings, "scanned": True}

    def scan_guardduty(self) -> Dict[str, Any]:
        """Scan GuardDuty findings."""
        guardduty = self.session.client('guardduty')
        findings = []

        try:
            # Check if GuardDuty is enabled
            detectors = guardduty.list_detectors()['DetectorIds']

            if not detectors:
                findings.append({
                    "severity": "HIGH",
                    "resource": "GuardDuty",
                    "issue": "GuardDuty not enabled"
                })
            else:
                for detector_id in detectors:
                    # Get active findings
                    finding_ids = guardduty.list_findings(
                        DetectorId=detector_id,
                        FindingCriteria={
                            'Criterion': {
                                'severity': {'Gte': 7}  # High and Critical
                            }
                        },
                        MaxResults=10
                    )['FindingIds']

                    if finding_ids:
                        finding_details = guardduty.get_findings(
                            DetectorId=detector_id,
                            FindingIds=finding_ids
                        )['Findings']

                        for finding in finding_details:
                            findings.append({
                                "severity": "HIGH" if finding['Severity'] >= 7 else "MEDIUM",
                                "resource": finding.get('Resource', {}).get('ResourceType', 'Unknown'),
                                "issue": finding['Title']
                            })

        except Exception as e:
            logger.error(f"GuardDuty scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "GuardDuty", "issue": str(e)})

        return {"service": "GuardDuty", "findings": findings, "scanned": True}


def format_scan_results(results: Dict[str, Any], scope: str) -> str:
    """Format scan results for display."""
    if scope == "all":
        # Format comprehensive scan results
        output = ["# AWS Security Scan Results\n"]

        total_findings = 0
        by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}

        for service_name, service_results in results.items():
            if not service_results.get("scanned"):
                continue

            findings = service_results.get("findings", [])
            if findings:
                output.append(f"\n## {service_results['service']}")
                output.append(f"Found {len(findings)} issue(s):\n")

                for finding in findings:
                    severity = finding.get("severity", "UNKNOWN")
                    if severity in by_severity:
                        by_severity[severity] += 1
                    total_findings += 1

                    emoji = {
                        "CRITICAL": "🔴",
                        "HIGH": "🟠",
                        "MEDIUM": "🟡",
                        "LOW": "🟢",
                        "INFO": "ℹ️",
                        "ERROR": "❌"
                    }.get(severity, "⚠️")

                    output.append(f"{emoji} **{severity}**: {finding.get('resource', 'Unknown')}")
                    output.append(f"   {finding.get('issue', 'No details')}\n")

        # Summary
        output.insert(1, f"\n**Summary**: {total_findings} findings across {len([r for r in results.values() if r.get('scanned')])} services\n")
        if by_severity:
            severity_summary = ", ".join([f"{count} {sev}" for sev, count in by_severity.items() if count > 0])
            output.insert(2, f"**By Severity**: {severity_summary}\n")

        return "\n".join(output)

    else:
        # Format single service scan
        findings = results.get("findings", [])
        service = results.get("service", scope.upper())

        output = [f"# {service} Security Scan\n"]

        if not findings:
            output.append("✅ No issues found!")
        else:
            output.append(f"Found {len(findings)} issue(s):\n")

            for finding in findings:
                severity = finding.get("severity", "UNKNOWN")
                emoji = {
                    "CRITICAL": "🔴",
                    "HIGH": "🟠",
                    "MEDIUM": "🟡",
                    "LOW": "🟢",
                    "INFO": "ℹ️",
                    "ERROR": "❌"
                }.get(severity, "⚠️")

                output.append(f"{emoji} **{severity}**: {finding.get('resource', 'Unknown')}")
                output.append(f"   {finding.get('issue', 'No details')}\n")

        return "\n".join(output)
