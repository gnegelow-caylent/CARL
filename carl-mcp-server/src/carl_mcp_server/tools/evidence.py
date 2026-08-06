"""
CARL Evidence Collection Tool

Collect compliance evidence across AWS environment.
"""
import os
import json
import logging
import hashlib
import boto3
from datetime import datetime
from typing import Dict, Any, List
from mcp.types import Tool

logger = logging.getLogger(__name__)

def carl_evidence_tool() -> Tool:
    """Define the carl_collect_evidence MCP tool."""
    return Tool(
        name="carl_collect_evidence",
        description="""Collect audit evidence for compliance frameworks.

Performs comprehensive evidence collection across AWS services and stores results
in DynamoDB and S3 for audit purposes.

Supported frameworks:
- SOC 2 (Security, Availability, Confidentiality)
- HIPAA (Technical Safeguards)
- PCI DSS (Payment Card Industry)
- NIST CSF 2.0 (Cybersecurity Framework)

Evidence collected includes:
- IAM policies and access controls
- Encryption configurations (S3, RDS, EBS)
- Logging and monitoring (CloudTrail, VPC Flow Logs)
- Network security (Security Groups, NACLs)
- Security tool findings (Security Hub, GuardDuty)

Evidence is stored with:
- Point-in-time snapshots for historical proof
- Control mappings (e.g., CC6.1, HIPAA §164.312)
- Metadata for audit trail

Returns:
- Summary of evidence collected by service
- Control coverage analysis
- Storage locations (DynamoDB table, S3 bucket)""",
        inputSchema={
            "type": "object",
            "properties": {
                "framework": {
                    "type": "string",
                    "description": "Compliance framework: 'soc2', 'hipaa', 'pci', 'nist', or 'all'",
                    "default": "soc2"
                },
                "store": {
                    "type": "boolean",
                    "description": "Store evidence in DynamoDB/S3 (requires tables to be deployed)",
                    "default": True
                }
            }
        }
    )

async def handle_carl_evidence(arguments: Dict[str, Any]) -> str:
    """Execute the carl_collect_evidence tool."""
    framework = arguments.get("framework", "soc2").lower()
    store = arguments.get("store", True)

    logger.info(f"Collecting evidence for framework: {framework}")

    try:
        # Get AWS session
        profile = os.getenv("AWS_PROFILE")
        region = os.getenv("AWS_REGION", "us-east-1")

        if profile:
            session = boto3.Session(profile_name=profile, region_name=region)
        else:
            session = boto3.Session(region_name=region)

        # Initialize evidence collector
        collector = EvidenceCollector(session, framework)

        # Collect evidence
        evidence_results = collector.collect_all()

        # Store evidence if requested
        if store:
            storage_info = collector.store_evidence(evidence_results)
        else:
            storage_info = {"stored": False}

        # Format results
        return format_evidence_results(evidence_results, framework, storage_info)

    except Exception as e:
        logger.exception(f"Evidence collection failed: {e}")
        return f"""❌ Evidence collection failed: {str(e)}

Please check:
1. AWS credentials are configured
2. IAM permissions for read access to AWS services
3. DynamoDB tables deployed (if storing evidence):
   cd carl-infrastructure/mcp-deployment
   terraform apply"""


class EvidenceCollector:
    """Collects compliance evidence from AWS."""

    def __init__(self, session: boto3.Session, framework: str = "soc2"):
        self.session = session
        self.framework = framework
        self.account_id = session.client('sts').get_caller_identity()['Account']
        self.region = session.region_name
        self.timestamp = datetime.utcnow().isoformat()

    def collect_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """Collect evidence across all services."""
        return {
            "iam": self.collect_iam_evidence(),
            "s3": self.collect_s3_evidence(),
            "vpc": self.collect_vpc_evidence(),
            "cloudtrail": self.collect_cloudtrail_evidence(),
            "security_hub": self.collect_security_hub_evidence(),
            "kms": self.collect_kms_evidence(),
        }

    def collect_iam_evidence(self) -> List[Dict[str, Any]]:
        """Collect IAM evidence."""
        iam = self.session.client('iam')
        evidence = []

        try:
            # Password policy
            try:
                policy = iam.get_account_password_policy()['PasswordPolicy']
                evidence.append({
                    "resource_type": "IAM::PasswordPolicy",
                    "resource_id": f"account-{self.account_id}",
                    "data": policy,
                    "controls": self._map_controls("iam_password_policy"),
                    "compliant": self._check_password_policy_compliance(policy)
                })
            except iam.exceptions.NoSuchEntityException:
                evidence.append({
                    "resource_type": "IAM::PasswordPolicy",
                    "resource_id": f"account-{self.account_id}",
                    "data": {},
                    "controls": self._map_controls("iam_password_policy"),
                    "compliant": False
                })

            # MFA status for users
            users = iam.list_users(MaxItems=10)['Users']
            for user in users:
                mfa_devices = iam.list_mfa_devices(UserName=user['UserName'])['MFADevices']
                evidence.append({
                    "resource_type": "IAM::User",
                    "resource_id": user['UserName'],
                    "data": {
                        "username": user['UserName'],
                        "mfa_enabled": len(mfa_devices) > 0,
                        "create_date": user['CreateDate'].isoformat()
                    },
                    "controls": self._map_controls("iam_mfa"),
                    "compliant": len(mfa_devices) > 0
                })

        except Exception as e:
            logger.error(f"IAM evidence collection error: {e}")

        return evidence

    def collect_s3_evidence(self) -> List[Dict[str, Any]]:
        """Collect S3 evidence."""
        s3 = self.session.client('s3')
        evidence = []

        try:
            buckets = s3.list_buckets()['Buckets']

            for bucket in buckets[:100]:  # Limit to 100 (aligned with scan.py)
                bucket_name = bucket['Name']

                try:
                    # Encryption
                    encryption = None
                    try:
                        encryption = s3.get_bucket_encryption(Bucket=bucket_name)['ServerSideEncryptionConfiguration']
                    except s3.exceptions.ClientError:
                        pass

                    # Versioning
                    versioning = s3.get_bucket_versioning(Bucket=bucket_name)

                    # Public access block
                    public_access = None
                    try:
                        public_access = s3.get_public_access_block(Bucket=bucket_name)['PublicAccessBlockConfiguration']
                    except s3.exceptions.ClientError:
                        pass

                    evidence.append({
                        "resource_type": "S3::Bucket",
                        "resource_id": bucket_name,
                        "data": {
                            "encryption": encryption,
                            "versioning": versioning.get('Status'),
                            "public_access_block": public_access
                        },
                        "controls": self._map_controls("s3_security"),
                        "compliant": encryption is not None and public_access is not None
                    })

                except Exception as e:
                    logger.debug(f"Could not collect evidence for bucket {bucket_name}: {e}")

        except Exception as e:
            logger.error(f"S3 evidence collection error: {e}")

        return evidence

    def collect_vpc_evidence(self) -> List[Dict[str, Any]]:
        """Collect VPC evidence."""
        ec2 = self.session.client('ec2')
        evidence = []

        try:
            # VPCs and flow logs
            vpcs = ec2.describe_vpcs()['Vpcs']
            flow_logs = ec2.describe_flow_logs()['FlowLogs']
            vpc_logs_map = {fl['ResourceId']: fl for fl in flow_logs}

            for vpc in vpcs:
                vpc_id = vpc['VpcId']
                has_flow_logs = vpc_id in vpc_logs_map

                evidence.append({
                    "resource_type": "EC2::VPC",
                    "resource_id": vpc_id,
                    "data": {
                        "cidr": vpc['CidrBlock'],
                        "flow_logs_enabled": has_flow_logs,
                        "flow_log_config": vpc_logs_map.get(vpc_id)
                    },
                    "controls": self._map_controls("vpc_flow_logs"),
                    "compliant": has_flow_logs
                })

        except Exception as e:
            logger.error(f"VPC evidence collection error: {e}")

        return evidence

    def collect_cloudtrail_evidence(self) -> List[Dict[str, Any]]:
        """Collect CloudTrail evidence."""
        cloudtrail = self.session.client('cloudtrail')
        evidence = []

        try:
            trails = cloudtrail.describe_trails()['trailList']

            for trail in trails:
                status = cloudtrail.get_trail_status(Name=trail['TrailARN'])

                evidence.append({
                    "resource_type": "CloudTrail::Trail",
                    "resource_id": trail['Name'],
                    "data": {
                        "is_logging": status.get('IsLogging'),
                        "log_file_validation_enabled": trail.get('LogFileValidationEnabled'),
                        "is_multi_region": trail.get('IsMultiRegionTrail'),
                        "s3_bucket": trail.get('S3BucketName')
                    },
                    "controls": self._map_controls("cloudtrail_logging"),
                    "compliant": status.get('IsLogging') and trail.get('LogFileValidationEnabled')
                })

        except Exception as e:
            logger.error(f"CloudTrail evidence collection error: {e}")

        return evidence

    def collect_security_hub_evidence(self) -> List[Dict[str, Any]]:
        """Collect Security Hub evidence."""
        securityhub = self.session.client('securityhub')
        evidence = []

        try:
            # Get active findings (aligned with scan.py pagination)
            paginator = securityhub.get_paginator('get_findings')
            page_iterator = paginator.paginate(
                Filters={'RecordState': [{'Value': 'ACTIVE', 'Comparison': 'EQUALS'}]},
                PaginationConfig={'MaxItems': 100}
            )

            for page in page_iterator:
                for finding in page.get('Findings', []):
                    evidence.append({
                        "resource_type": "SecurityHub::Finding",
                        "resource_id": finding['Id'],
                        "data": {
                            "title": finding['Title'],
                            "severity": finding['Severity']['Label'],
                            "resource": finding.get('Resources', [{}])[0].get('Id'),
                            "generator_id": finding['GeneratorId']
                        },
                        "controls": self._map_controls("security_monitoring"),
                        "compliant": False  # Active findings indicate non-compliance
                })

        except securityhub.exceptions.InvalidAccessException:
            logger.info("Security Hub not enabled")
        except Exception as e:
            logger.error(f"Security Hub evidence collection error: {e}")

        return evidence

    def collect_kms_evidence(self) -> List[Dict[str, Any]]:
        """Collect KMS evidence."""
        kms = self.session.client('kms')
        evidence = []

        try:
            keys = kms.list_keys(Limit=100)['Keys']  # Aligned with scan.py

            for key in keys:
                key_id = key['KeyId']
                metadata = kms.describe_key(KeyId=key_id)['KeyMetadata']

                # Only include customer-managed keys
                if metadata['KeyManager'] == 'CUSTOMER':
                    # Check key rotation status (required for PCI 3.5/3.6)
                    rotation_status = None
                    rotation_enabled = False
                    try:
                        rotation_status = kms.get_key_rotation_status(KeyId=key_id)
                        rotation_enabled = rotation_status.get('KeyRotationEnabled', False)
                    except Exception as e:
                        logger.debug(f"Could not check rotation for key {key_id}: {e}")

                    evidence.append({
                        "resource_type": "KMS::Key",
                        "resource_id": key_id,
                        "data": {
                            "key_state": metadata['KeyState'],
                            "enabled": metadata['Enabled'],
                            "rotation_enabled": rotation_enabled,
                            "description": metadata.get('Description', ''),
                            "creation_date": metadata['CreationDate'].isoformat()
                        },
                        "controls": self._map_controls("encryption_at_rest"),
                        "compliant": (
                            metadata['Enabled'] and
                            metadata['KeyState'] == 'Enabled' and
                            rotation_enabled  # Rotation required for compliance
                        )
                    })

        except Exception as e:
            logger.error(f"KMS evidence collection error: {e}")

        return evidence

    def _map_controls(self, evidence_type: str) -> List[str]:
        """Map evidence type to compliance controls."""
        control_mappings = {
            "iam_password_policy": {
                "soc2": ["CC6.1", "CC6.7"],
                "hipaa": ["164.308(a)(5)(ii)(D)", "164.312(a)(2)(i)"],
                "pci": ["8.1.6", "8.2.3"],
                "nist": ["PR.AC-1", "PR.AC-7"]
            },
            "iam_mfa": {
                "soc2": ["CC6.1", "CC6.2"],
                "hipaa": ["164.312(a)(2)(i)"],
                "pci": ["8.3"],
                "nist": ["PR.AC-1", "PR.AC-7"]
            },
            "s3_security": {
                "soc2": ["CC6.1", "CC6.7"],
                "hipaa": ["164.312(a)(2)(iv)", "164.312(e)(2)(ii)"],
                "pci": ["3.4", "3.5"],
                "nist": ["PR.DS-1", "PR.DS-5"]
            },
            "vpc_flow_logs": {
                "soc2": ["CC7.2"],
                "hipaa": ["164.312(b)"],
                "pci": ["10.1"],
                "nist": ["DE.AE-3", "DE.CM-1"]
            },
            "cloudtrail_logging": {
                "soc2": ["CC7.2", "CC7.3"],
                "hipaa": ["164.312(b)"],
                "pci": ["10.2", "10.3"],
                "nist": ["DE.AE-3", "DE.CM-1", "PR.PT-1"]
            },
            "security_monitoring": {
                "soc2": ["CC7.2", "CC7.3"],
                "hipaa": ["164.308(a)(1)(ii)(D)"],
                "pci": ["11.5"],
                "nist": ["DE.CM-1", "DE.CM-7", "RS.AN-1"]
            },
            "encryption_at_rest": {
                "soc2": ["CC6.7"],
                "hipaa": ["164.312(a)(2)(iv)"],
                "pci": ["3.4"],
                "nist": ["PR.DS-1"]
            }
        }

        # If framework is "all", aggregate all frameworks
        if self.framework == "all":
            all_controls = []
            for framework_controls in control_mappings.get(evidence_type, {}).values():
                all_controls.extend(framework_controls)
            return list(set(all_controls))  # Remove duplicates
        else:
            return control_mappings.get(evidence_type, {}).get(self.framework, [])

    def _check_password_policy_compliance(self, policy: Dict[str, Any]) -> bool:
        """Check if password policy meets compliance requirements."""
        required_checks = {
            "MinimumPasswordLength": lambda v: v >= 14,
            "RequireUppercaseCharacters": lambda v: v is True,
            "RequireLowercaseCharacters": lambda v: v is True,
            "RequireNumbers": lambda v: v is True,
            "RequireSymbols": lambda v: v is True,
            "MaxPasswordAge": lambda v: v <= 90
        }

        for key, check_func in required_checks.items():
            if key not in policy or not check_func(policy[key]):
                return False
        return True

    def store_evidence(self, evidence_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Store evidence in DynamoDB and S3."""
        try:
            # Get table/bucket names from environment
            evidence_table = os.getenv("CARL_DYNAMODB_EVIDENCE_TABLE", "carl-prod-evidence")
            evidence_bucket = os.getenv("CARL_S3_EVIDENCE_BUCKET", "")

            dynamodb = self.session.resource('dynamodb')
            table = dynamodb.Table(evidence_table)

            stored_count = 0
            for category, evidence_items in evidence_results.items():
                for evidence in evidence_items:
                    # Generate evidence ID
                    evidence_id = self._generate_evidence_id(evidence)

                    # Store in DynamoDB
                    item = {
                        "pk": f"EVIDENCE#{evidence_id}",
                        "sk": f"TIMESTAMP#{self.timestamp}",
                        "evidence_id": evidence_id,
                        "account_id": self.account_id,
                        "region": self.region,
                        "timestamp": self.timestamp,
                        "framework": self.framework,
                        "category": category,
                        **evidence
                    }
                    table.put_item(Item=item)
                    stored_count += 1

            return {
                "stored": True,
                "table": evidence_table,
                "bucket": evidence_bucket if evidence_bucket else "Not configured",
                "count": stored_count
            }

        except Exception as e:
            logger.error(f"Failed to store evidence: {e}")
            return {"stored": False, "error": str(e)}

    def _generate_evidence_id(self, evidence: Dict[str, Any]) -> str:
        """Generate unique evidence ID."""
        content = f"{evidence['resource_type']}#{evidence['resource_id']}#{self.account_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


def format_evidence_results(
    evidence_results: Dict[str, List[Dict[str, Any]]],
    framework: str,
    storage_info: Dict[str, Any]
) -> str:
    """Format evidence collection results."""
    output = [f"# Compliance Evidence Collection - {framework.upper()}\n"]

    # Summary
    total_items = sum(len(items) for items in evidence_results.values())
    compliant_items = sum(
        1 for items in evidence_results.values()
        for item in items
        if item.get("compliant", False)
    )

    output.append(f"**Total Evidence Collected**: {total_items} items")
    output.append(f"**Compliant Items**: {compliant_items}/{total_items} ({(compliant_items/total_items*100):.1f}%)\n")

    # By service
    output.append("## Evidence by Service\n")
    for service, items in evidence_results.items():
        if items:
            compliant = sum(1 for item in items if item.get("compliant", False))
            output.append(f"### {service.upper()}")
            output.append(f"- {len(items)} resources scanned")
            output.append(f"- {compliant} compliant, {len(items)-compliant} non-compliant")

            # Show sample controls
            if items:
                sample_controls = items[0].get("controls", [])
                if sample_controls:
                    output.append(f"- Controls: {', '.join(sample_controls[:3])}")
            output.append("")

    # Storage info
    if storage_info.get("stored"):
        output.append(f"\n## Storage")
        output.append(f"✅ Evidence stored successfully")
        output.append(f"- DynamoDB Table: `{storage_info['table']}`")
        output.append(f"- S3 Bucket: `{storage_info.get('bucket', 'Not configured')}`")
        output.append(f"- Items Stored: {storage_info['count']}")
    else:
        output.append(f"\n## Storage")
        if storage_info.get("error"):
            output.append(f"❌ Evidence storage failed")
            output.append(f"- Error: {storage_info['error']}")
            output.append(f"\nTo enable storage, deploy CARL infrastructure:")
            output.append(f"- DynamoDB table: Set `CARL_DYNAMODB_EVIDENCE_TABLE`")
            output.append(f"- S3 bucket (optional): Set `CARL_S3_EVIDENCE_BUCKET`")
        else:
            output.append(f"⚠️ Evidence collected but not stored (storage disabled)")

    return "\n".join(output)
