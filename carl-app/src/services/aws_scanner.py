"""
AWS Environment Scanner for CARL

Scans AWS account for common security misconfigurations and best practices.
"""

import boto3
from typing import Dict, List, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class AWSScanner:
    """Scanner for AWS security configuration and best practices."""

    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.iam = boto3.client('iam')
        self.cloudtrail = boto3.client('cloudtrail', region_name=region)
        self.ec2 = boto3.client('ec2', region_name=region)
        self.s3 = boto3.client('s3')
        self.rds = boto3.client('rds', region_name=region)
        self.kms = boto3.client('kms', region_name=region)
        self.sts = boto3.client('sts')

    def scan_environment(self) -> Dict[str, Any]:
        """Perform a comprehensive scan of the AWS environment."""
        logger.info("Starting AWS environment scan")

        results = {
            'account_id': self._get_account_id(),
            'iam': self._scan_iam(),
            'cloudtrail': self._scan_cloudtrail(),
            'security_groups': self._scan_security_groups(),
            's3': self._scan_s3_buckets(),
            'encryption': self._scan_encryption(),
            'network': self._scan_network(),
        }

        logger.info("AWS environment scan complete")
        return results

    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        try:
            return self.sts.get_caller_identity()['Account']
        except Exception as e:
            logger.error(f"Error getting account ID: {e}")
            return "unknown"

    def _scan_iam(self) -> Dict[str, Any]:
        """Scan IAM configuration."""
        results = {
            'issues': [],
            'best_practices': []
        }

        try:
            # Check for root account usage
            summary = self.iam.get_account_summary()['SummaryMap']

            if summary.get('AccountMFAEnabled', 0) == 0:
                results['issues'].append({
                    'severity': 'CRITICAL',
                    'finding': 'Root account MFA not enabled',
                    'recommendation': 'Enable MFA on root account immediately'
                })

            # Check password policy
            try:
                policy = self.iam.get_account_password_policy()['PasswordPolicy']
                if not policy.get('RequireUppercaseCharacters'):
                    results['issues'].append({
                        'severity': 'MEDIUM',
                        'finding': 'Password policy does not require uppercase letters',
                        'recommendation': 'Update password policy to require uppercase'
                    })
                if policy.get('MinimumPasswordLength', 0) < 14:
                    results['issues'].append({
                        'severity': 'MEDIUM',
                        'finding': f'Password minimum length is {policy.get("MinimumPasswordLength")} (should be 14+)',
                        'recommendation': 'Increase minimum password length to 14 characters'
                    })
            except self.iam.exceptions.NoSuchEntityException:
                results['issues'].append({
                    'severity': 'HIGH',
                    'finding': 'No password policy configured',
                    'recommendation': 'Create a strong password policy'
                })

            # Check IAM users
            users_response = self.iam.list_users()
            users = users_response['Users']

            if len(users) > 10:
                results['issues'].append({
                    'severity': 'MEDIUM',
                    'finding': f'{len(users)} IAM users found - consider using IAM Identity Center instead',
                    'recommendation': 'Migrate to IAM Identity Center for centralized access'
                })

            # Check for users without MFA
            users_without_mfa = []
            for user in users[:20]:  # Limit to first 20 to avoid API throttling
                try:
                    mfa_devices = self.iam.list_mfa_devices(UserName=user['UserName'])
                    if not mfa_devices['MFADevices']:
                        users_without_mfa.append(user['UserName'])
                except Exception as e:
                    logger.warning(f"Could not check MFA for {user['UserName']}: {e}")

            if users_without_mfa:
                results['issues'].append({
                    'severity': 'HIGH',
                    'finding': f'{len(users_without_mfa)} users without MFA: {", ".join(users_without_mfa[:5])}',
                    'recommendation': 'Enable MFA for all IAM users'
                })

        except Exception as e:
            logger.error(f"Error scanning IAM: {e}")
            results['error'] = str(e)

        return results

    def _scan_cloudtrail(self) -> Dict[str, Any]:
        """Scan CloudTrail configuration."""
        results = {
            'issues': [],
            'trails': []
        }

        try:
            trails = self.cloudtrail.describe_trails()['trailList']

            if not trails:
                results['issues'].append({
                    'severity': 'CRITICAL',
                    'finding': 'No CloudTrail trails configured',
                    'recommendation': 'Enable CloudTrail in all regions'
                })
                return results

            for trail in trails:
                trail_status = self.cloudtrail.get_trail_status(Name=trail['TrailARN'])

                trail_info = {
                    'name': trail['Name'],
                    'logging': trail_status['IsLogging'],
                    'multi_region': trail.get('IsMultiRegionTrail', False),
                    'log_file_validation': trail.get('LogFileValidationEnabled', False)
                }
                results['trails'].append(trail_info)

                if not trail_status['IsLogging']:
                    results['issues'].append({
                        'severity': 'CRITICAL',
                        'finding': f'CloudTrail "{trail["Name"]}" is not logging',
                        'recommendation': 'Enable logging for this trail'
                    })

                if not trail.get('IsMultiRegionTrail'):
                    results['issues'].append({
                        'severity': 'HIGH',
                        'finding': f'CloudTrail "{trail["Name"]}" is not multi-region',
                        'recommendation': 'Enable multi-region trail'
                    })

                if not trail.get('LogFileValidationEnabled'):
                    results['issues'].append({
                        'severity': 'MEDIUM',
                        'finding': f'CloudTrail "{trail["Name"]}" does not have log file validation',
                        'recommendation': 'Enable log file validation'
                    })

        except Exception as e:
            logger.error(f"Error scanning CloudTrail: {e}")
            results['error'] = str(e)

        return results

    def _scan_security_groups(self) -> Dict[str, Any]:
        """Scan security groups for overly permissive rules."""
        results = {
            'issues': [],
            'security_groups': []
        }

        try:
            response = self.ec2.describe_security_groups()
            security_groups = response['SecurityGroups']

            for sg in security_groups:
                # Check for 0.0.0.0/0 ingress rules
                for rule in sg.get('IpPermissions', []):
                    for ip_range in rule.get('IpRanges', []):
                        if ip_range.get('CidrIp') == '0.0.0.0/0':
                            protocol = rule.get('IpProtocol', 'all')
                            from_port = rule.get('FromPort', 'all')
                            to_port = rule.get('ToPort', 'all')

                            severity = 'CRITICAL' if from_port == 22 or from_port == 3389 else 'HIGH'

                            results['issues'].append({
                                'severity': severity,
                                'finding': f'Security group "{sg["GroupName"]}" allows {protocol}:{from_port}-{to_port} from 0.0.0.0/0',
                                'recommendation': f'Restrict access to specific IP ranges'
                            })

        except Exception as e:
            logger.error(f"Error scanning security groups: {e}")
            results['error'] = str(e)

        return results

    def _scan_s3_buckets(self) -> Dict[str, Any]:
        """Scan S3 buckets for security issues."""
        results = {
            'issues': [],
            'buckets': []
        }

        try:
            buckets = self.s3.list_buckets()['Buckets']

            for bucket in buckets[:20]:  # Limit to avoid throttling
                bucket_name = bucket['Name']

                try:
                    # Check public access
                    try:
                        acl = self.s3.get_bucket_acl(Bucket=bucket_name)
                        for grant in acl['Grants']:
                            grantee = grant.get('Grantee', {})
                            if grantee.get('Type') == 'Group' and 'AllUsers' in grantee.get('URI', ''):
                                results['issues'].append({
                                    'severity': 'CRITICAL',
                                    'finding': f'S3 bucket "{bucket_name}" has public access via ACL',
                                    'recommendation': 'Remove public ACL and use bucket policies instead'
                                })
                    except:
                        pass

                    # Check encryption
                    try:
                        encryption = self.s3.get_bucket_encryption(Bucket=bucket_name)
                    except self.s3.exceptions.ServerSideEncryptionConfigurationNotFoundError:
                        results['issues'].append({
                            'severity': 'HIGH',
                            'finding': f'S3 bucket "{bucket_name}" does not have default encryption enabled',
                            'recommendation': 'Enable default encryption (AES-256 or KMS)'
                        })
                    except:
                        pass

                    # Check versioning
                    try:
                        versioning = self.s3.get_bucket_versioning(Bucket=bucket_name)
                        if versioning.get('Status') != 'Enabled':
                            results['issues'].append({
                                'severity': 'MEDIUM',
                                'finding': f'S3 bucket "{bucket_name}" does not have versioning enabled',
                                'recommendation': 'Enable versioning for data protection'
                            })
                    except:
                        pass

                except Exception as e:
                    logger.warning(f"Could not scan bucket {bucket_name}: {e}")

        except Exception as e:
            logger.error(f"Error scanning S3: {e}")
            results['error'] = str(e)

        return results

    def _scan_encryption(self) -> Dict[str, Any]:
        """Scan encryption configuration."""
        results = {
            'issues': [],
            'kms_keys': 0
        }

        try:
            # Count KMS keys
            keys = self.kms.list_keys()
            results['kms_keys'] = len(keys['Keys'])

            # Check EBS encryption by default
            try:
                ebs_encryption = self.ec2.get_ebs_encryption_by_default()
                if not ebs_encryption['EbsEncryptionByDefault']:
                    results['issues'].append({
                        'severity': 'HIGH',
                        'finding': 'EBS encryption by default is not enabled',
                        'recommendation': 'Enable EBS encryption by default for the region'
                    })
            except:
                pass

        except Exception as e:
            logger.error(f"Error scanning encryption: {e}")
            results['error'] = str(e)

        return results

    def _scan_network(self) -> Dict[str, Any]:
        """Scan network configuration."""
        results = {
            'issues': [],
            'vpcs': [],
            'flow_logs_enabled': False
        }

        try:
            vpcs = self.ec2.describe_vpcs()['Vpcs']
            results['vpcs'] = [{'id': vpc['VpcId'], 'cidr': vpc['CidrBlock']} for vpc in vpcs]

            # Check VPC Flow Logs
            flow_logs = self.ec2.describe_flow_logs()['FlowLogs']

            vpcs_with_flow_logs = set(fl['ResourceId'] for fl in flow_logs if fl['ResourceType'] == 'VPC')
            vpcs_without_flow_logs = [vpc['VpcId'] for vpc in vpcs if vpc['VpcId'] not in vpcs_with_flow_logs]

            if vpcs_without_flow_logs:
                results['issues'].append({
                    'severity': 'HIGH',
                    'finding': f'{len(vpcs_without_flow_logs)} VPCs without Flow Logs: {", ".join(vpcs_without_flow_logs[:3])}',
                    'recommendation': 'Enable VPC Flow Logs for all VPCs'
                })
            else:
                results['flow_logs_enabled'] = True

        except Exception as e:
            logger.error(f"Error scanning network: {e}")
            results['error'] = str(e)

        return results

    def get_summary(self, scan_results: Dict[str, Any]) -> str:
        """Generate a human-readable summary of scan results."""
        all_issues = []

        for category, data in scan_results.items():
            if category == 'account_id':
                continue
            if isinstance(data, dict) and 'issues' in data:
                all_issues.extend(data['issues'])

        if not all_issues:
            return "✅ Great news! No critical security issues found in your AWS environment."

        critical = [i for i in all_issues if i['severity'] == 'CRITICAL']
        high = [i for i in all_issues if i['severity'] == 'HIGH']
        medium = [i for i in all_issues if i['severity'] == 'MEDIUM']

        summary = f"""# AWS Environment Scan Results

**Account ID:** {scan_results.get('account_id', 'unknown')}

## Security Issues Found
- 🚨 Critical: {len(critical)}
- ⚠️  High: {len(high)}
- ⚡ Medium: {len(medium)}

"""

        if critical:
            summary += "\n### 🚨 Critical Issues (Fix Immediately)\n"
            for issue in critical[:5]:
                summary += f"- **{issue['finding']}**\n"
                summary += f"  _Recommendation: {issue['recommendation']}_\n\n"

        if high:
            summary += "\n### ⚠️ High Priority Issues\n"
            for issue in high[:5]:
                summary += f"- **{issue['finding']}**\n"
                summary += f"  _Recommendation: {issue['recommendation']}_\n\n"

        if medium:
            summary += "\n### ⚡ Medium Priority Issues\n"
            for issue in medium[:3]:
                summary += f"- {issue['finding']}\n"

        return summary
