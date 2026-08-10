"""
CARL Scan Tool

Scan AWS environment for security findings.
"""
import logging
import os
import boto3
from datetime import datetime, timezone
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

            # Check root account MFA (CIS AWS Foundations critical control)
            try:
                account_summary = iam.get_account_summary()['SummaryMap']
                if account_summary.get('AccountMFAEnabled', 0) == 0:
                    findings.append({
                        "severity": "CRITICAL",
                        "resource": "Root Account",
                        "issue": "MFA not enabled for root account (CIS AWS Foundations critical)"
                    })
            except Exception as e:
                logger.debug(f"Could not check root account MFA: {e}")

            # Check for users without MFA
            users = iam.list_users()['Users']
            total_users = len(users)
            users_to_check = users[:100]  # Check up to 100 users
            users_checked = 0

            for user in users_to_check:
                try:
                    username = user['UserName']
                    mfa_devices = iam.list_mfa_devices(UserName=username)['MFADevices']
                    users_checked += 1
                    if not mfa_devices:
                        findings.append({
                            "severity": "HIGH",
                            "resource": f"IAM User: {username}",
                            "issue": "MFA not enabled"
                        })

                    # Check access key age (CIS AWS Foundations: rotate every 90 days)
                    access_keys = iam.list_access_keys(UserName=username)['AccessKeyMetadata']
                    for key in access_keys:
                        if key['Status'] == 'Active':
                            key_age_days = (datetime.now(timezone.utc) - key['CreateDate']).days
                            if key_age_days > 90:
                                findings.append({
                                    "severity": "MEDIUM",
                                    "resource": f"IAM User: {username}",
                                    "issue": f"Access key {key['AccessKeyId']} is {key_age_days} days old (rotate every 90 days)"
                                })
                except Exception as e:
                    logger.debug(f"Could not check MFA/keys for {username}: {e}")

        except Exception as e:
            logger.error(f"IAM scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "IAM", "issue": str(e)})

        return {
            "service": "IAM",
            "findings": findings,
            "scanned": True,
            "stats": {
                "users_checked": users_checked if 'users_checked' in locals() else 0,
                "total_users": total_users if 'total_users' in locals() else 0,
                "truncated": total_users > 100 if 'total_users' in locals() else False
            }
        }

    def scan_s3(self) -> Dict[str, Any]:
        """Scan S3 buckets."""
        s3 = self.session.client('s3')
        sts = self.session.client('sts')
        findings = []

        try:
            # Get account ID for account-level checks
            account_id = sts.get_caller_identity()['Account']

            # Check account-level S3 Block Public Access (overrides bucket-level)
            account_level_protected = False
            try:
                account_public_access = s3.get_public_access_block(
                    AccountId=account_id
                )['PublicAccessBlockConfiguration']

                account_level_protected = all([
                    account_public_access.get('BlockPublicAcls'),
                    account_public_access.get('IgnorePublicAcls'),
                    account_public_access.get('BlockPublicPolicy'),
                    account_public_access.get('RestrictPublicBuckets')
                ])
            except s3.exceptions.ClientError:
                # Account-level block not configured
                findings.append({
                    "severity": "HIGH",
                    "resource": "S3 Account Settings",
                    "issue": "Account-level Block Public Access not configured (recommended since 2019)"
                })

            buckets = s3.list_buckets()['Buckets']
            total_buckets = len(buckets)
            buckets_to_check = buckets[:100]  # Check up to 100 buckets
            buckets_checked = 0

            for bucket in buckets_to_check:
                bucket_name = bucket['Name']
                buckets_checked += 1

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

                    # Check versioning (skip AWS auto-created buckets)
                    if not any(prefix in bucket_name for prefix in ['cf-templates-', 'elasticbeanstalk-', 'aws-']):
                        versioning = s3.get_bucket_versioning(Bucket=bucket_name)
                        if versioning.get('Status') != 'Enabled':
                            findings.append({
                                "severity": "MEDIUM",
                                "resource": f"S3 Bucket: {bucket_name}",
                                "issue": "Versioning not enabled"
                            })

                    # Check bucket-level public access block (only if account-level not protecting)
                    if not account_level_protected:
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

        return {
            "service": "S3",
            "findings": findings,
            "scanned": True,
            "stats": {
                "buckets_checked": buckets_checked if 'buckets_checked' in locals() else 0,
                "total_buckets": total_buckets if 'total_buckets' in locals() else 0,
                "truncated": total_buckets > 100 if 'total_buckets' in locals() else False
            }
        }

    def scan_vpc(self) -> Dict[str, Any]:
        """Scan VPC configuration."""
        ec2 = self.session.client('ec2')
        findings = []

        try:
            # Check VPCs for flow logs
            vpcs = ec2.describe_vpcs()['Vpcs']
            flow_logs = ec2.describe_flow_logs()['FlowLogs']

            # Map VPC IDs to their flow logs for detailed checking
            vpc_flow_logs = {}
            for fl in flow_logs:
                resource_id = fl['ResourceId']
                if resource_id not in vpc_flow_logs:
                    vpc_flow_logs[resource_id] = []
                vpc_flow_logs[resource_id].append(fl)

            for vpc in vpcs:
                vpc_id = vpc['VpcId']
                if vpc_id not in vpc_flow_logs:
                    findings.append({
                        "severity": "MEDIUM",
                        "resource": f"VPC: {vpc_id}",
                        "issue": "VPC Flow Logs not enabled"
                    })
                else:
                    # Check if any flow log captures ALL traffic (recommended for compliance)
                    has_all_traffic = any(
                        fl.get('TrafficType') == 'ALL'
                        for fl in vpc_flow_logs[vpc_id]
                    )
                    if not has_all_traffic:
                        # Get traffic types configured
                        traffic_types = [fl.get('TrafficType', 'UNKNOWN') for fl in vpc_flow_logs[vpc_id]]
                        findings.append({
                            "severity": "LOW",
                            "resource": f"VPC: {vpc_id}",
                            "issue": f"VPC Flow Logs not capturing ALL traffic (current: {', '.join(traffic_types)})"
                        })

            # Check security groups for overly permissive rules
            sgs = ec2.describe_security_groups()['SecurityGroups']
            total_sgs = len(sgs)
            sgs_to_check = sgs[:100]  # Check up to 100 security groups
            sgs_checked = 0

            for sg in sgs_to_check:
                sgs_checked += 1
                for rule in sg.get('IpPermissions', []):
                    for ip_range in rule.get('IpRanges', []):
                        if ip_range.get('CidrIp') == '0.0.0.0/0':
                            port = rule.get('FromPort', 'ALL')
                            # Severity depends on port: SSH/RDP are HIGH, HTTP/HTTPS are INFO
                            if port in [22, 3389]:  # SSH, RDP
                                severity = "HIGH"
                            elif port in [80, 443]:  # HTTP, HTTPS - normal for web servers
                                severity = "INFO"
                            else:
                                severity = "MEDIUM"

                            findings.append({
                                "severity": severity,
                                "resource": f"Security Group: {sg['GroupId']}",
                                "issue": f"Port {port} open to internet (0.0.0.0/0)"
                            })

        except Exception as e:
            logger.error(f"VPC scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "VPC", "issue": str(e)})

        return {
            "service": "VPC",
            "findings": findings,
            "scanned": True,
            "stats": {
                "vpcs_checked": len(vpcs) if 'vpcs' in locals() else 0,
                "security_groups_checked": sgs_checked if 'sgs_checked' in locals() else 0,
                "total_security_groups": total_sgs if 'total_sgs' in locals() else 0,
                "truncated": total_sgs > 100 if 'total_sgs' in locals() else False
            }
        }

    def scan_security_hub(self) -> Dict[str, Any]:
        """Scan Security Hub findings."""
        securityhub = self.session.client('securityhub')
        findings = []

        try:
            # Check if Security Hub is enabled
            try:
                # Get all active findings (all severity levels, paginated)
                paginator = securityhub.get_paginator('get_findings')
                page_iterator = paginator.paginate(
                    Filters={
                        'RecordState': [{'Value': 'ACTIVE', 'Comparison': 'EQUALS'}]
                    },
                    PaginationConfig={'MaxItems': 100}  # Limit to 100 findings
                )

                findings_count = 0
                for page in page_iterator:
                    for finding in page.get('Findings', []):
                        findings_count += 1
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

        return {
            "service": "Security Hub",
            "findings": findings,
            "scanned": True,
            "stats": {
                "findings_retrieved": findings_count if 'findings_count' in locals() else 0,
                "max_findings": 100
            }
        }

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
                # Check if at least one multi-region trail exists (CIS AWS Foundations)
                has_multi_region_trail = any(trail.get('IsMultiRegionTrail', False) for trail in trails)
                if not has_multi_region_trail:
                    findings.append({
                        "severity": "HIGH",
                        "resource": "CloudTrail",
                        "issue": "No multi-region trail configured (CIS AWS Foundations recommendation)"
                    })

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

                    # Check if multi-region trail
                    if not trail.get('IsMultiRegionTrail', False):
                        findings.append({
                            "severity": "MEDIUM",
                            "resource": f"CloudTrail: {trail['Name']}",
                            "issue": "Trail is not multi-region (only logs events in single region)"
                        })

        except Exception as e:
            logger.error(f"CloudTrail scan error: {e}")
            findings.append({"severity": "ERROR", "resource": "CloudTrail", "issue": str(e)})

        return {
            "service": "CloudTrail",
            "findings": findings,
            "scanned": True,
            "stats": {
                "trails_checked": len(trails) if 'trails' in locals() else 0
            }
        }

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
                total_findings = 0
                for detector_id in detectors:
                    # Get all active findings (paginated)
                    paginator = guardduty.get_paginator('list_findings')
                    page_iterator = paginator.paginate(
                        DetectorId=detector_id,
                        PaginationConfig={'MaxItems': 100}  # Limit to 100 findings
                    )

                    finding_ids = []
                    for page in page_iterator:
                        finding_ids.extend(page['FindingIds'])

                    total_findings = len(finding_ids)

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

        return {
            "service": "GuardDuty",
            "findings": findings,
            "scanned": True,
            "stats": {
                "findings_retrieved": total_findings if 'total_findings' in locals() else 0,
                "max_findings": 100
            }
        }


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
            stats = service_results.get("stats", {})

            if findings or stats:
                output.append(f"\n## {service_results['service']}")

                # Display stats if available
                if stats:
                    stat_parts = []
                    if 'users_checked' in stats:
                        stat_parts.append(f"Checked {stats['users_checked']} of {stats['total_users']} users")
                        if stats.get('truncated'):
                            stat_parts.append("⚠️ **Truncated** - increase scan limit")
                    if 'buckets_checked' in stats:
                        stat_parts.append(f"Checked {stats['buckets_checked']} of {stats['total_buckets']} buckets")
                        if stats.get('truncated'):
                            stat_parts.append("⚠️ **Truncated** - increase scan limit")
                    if 'security_groups_checked' in stats:
                        stat_parts.append(f"Checked {stats['security_groups_checked']} of {stats['total_security_groups']} security groups")
                        if stats.get('truncated'):
                            stat_parts.append("⚠️ **Truncated** - increase scan limit")
                    if 'vpcs_checked' in stats:
                        stat_parts.append(f"Checked {stats['vpcs_checked']} VPCs")
                    if 'trails_checked' in stats:
                        stat_parts.append(f"Checked {stats['trails_checked']} CloudTrail trail(s)")
                    if 'findings_retrieved' in stats:
                        stat_parts.append(f"Retrieved {stats['findings_retrieved']} findings (max: {stats.get('max_findings', 100)})")
                        if stats['findings_retrieved'] >= stats.get('max_findings', 100):
                            stat_parts.append("⚠️ **Results limited** - some findings may not be shown")

                    if stat_parts:
                        output.append(f"*{', '.join(stat_parts)}*\n")

                if findings:
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
        stats = results.get("stats", {})
        service = results.get("service", scope.upper())

        output = [f"# {service} Security Scan\n"]

        # Display stats if available
        if stats:
            stat_parts = []
            if 'users_checked' in stats:
                stat_parts.append(f"Checked {stats['users_checked']} of {stats['total_users']} users")
                if stats.get('truncated'):
                    stat_parts.append("⚠️ **Truncated** - increase scan limit")
            if 'buckets_checked' in stats:
                stat_parts.append(f"Checked {stats['buckets_checked']} of {stats['total_buckets']} buckets")
                if stats.get('truncated'):
                    stat_parts.append("⚠️ **Truncated** - increase scan limit")
            if 'security_groups_checked' in stats:
                stat_parts.append(f"Checked {stats['security_groups_checked']} of {stats['total_security_groups']} security groups")
                if stats.get('truncated'):
                    stat_parts.append("⚠️ **Truncated** - increase scan limit")
            if 'vpcs_checked' in stats:
                stat_parts.append(f"Checked {stats['vpcs_checked']} VPCs")
            if 'findings_retrieved' in stats:
                stat_parts.append(f"Retrieved {stats['findings_retrieved']} findings (max: {stats.get('max_findings', 100)})")

            if stat_parts:
                output.append(f"*{', '.join(stat_parts)}*\n")

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
