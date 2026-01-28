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
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.securityhub = boto3.client('securityhub', region_name=region)
        self.guardduty = boto3.client('guardduty', region_name=region)
        self.config = boto3.client('config', region_name=region)
        self.backup = boto3.client('backup', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
        self.elb = boto3.client('elbv2', region_name=region)

    def scan_environment(self) -> Dict[str, Any]:
        """Perform a comprehensive SOC 2-ready scan of the AWS environment."""
        logger.info("Starting comprehensive AWS environment scan")

        results = {
            'account_id': self._get_account_id(),
            'iam': self._scan_iam(),
            'iam_access_keys': self._scan_iam_access_keys(),
            'cloudtrail': self._scan_cloudtrail(),
            'security_groups': self._scan_security_groups(),
            's3': self._scan_s3_buckets(),
            'encryption': self._scan_encryption(),
            'network': self._scan_network(),
            'compute': self._scan_compute(),
            'databases': self._scan_databases(),
            'security_services': self._scan_security_services(),
            'logging': self._scan_logging(),
            'backup': self._scan_backup(),
        }

        logger.info("Comprehensive AWS environment scan complete")
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

            # Scan all buckets (with error handling per bucket)
            for bucket in buckets:
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

    def _scan_iam_access_keys(self) -> Dict[str, Any]:
        """Scan IAM access keys for age and rotation."""
        results = {
            'issues': [],
            'keys_checked': 0
        }

        try:
            import datetime
            from datetime import timezone

            users = self.iam.list_users()['Users']

            for user in users[:50]:  # Check up to 50 users
                try:
                    keys = self.iam.list_access_keys(UserName=user['UserName'])
                    for key in keys['AccessKeyMetadata']:
                        results['keys_checked'] += 1

                        # Check key age
                        key_age = (datetime.datetime.now(timezone.utc) - key['CreateDate']).days

                        if key['Status'] == 'Active':
                            if key_age > 90:
                                results['issues'].append({
                                    'severity': 'HIGH',
                                    'finding': f'Access key for user {user["UserName"]} is {key_age} days old',
                                    'recommendation': 'Rotate access keys every 90 days'
                                })

                            # Check for unused keys
                            try:
                                last_used = self.iam.get_access_key_last_used(AccessKeyId=key['AccessKeyId'])
                                if 'LastUsedDate' in last_used['AccessKeyLastUsed']:
                                    days_unused = (datetime.datetime.now(timezone.utc) - last_used['AccessKeyLastUsed']['LastUsedDate']).days
                                    if days_unused > 90:
                                        results['issues'].append({
                                            'severity': 'MEDIUM',
                                            'finding': f'Access key for {user["UserName"]} unused for {days_unused} days',
                                            'recommendation': 'Remove unused access keys'
                                        })
                            except:
                                pass

                except Exception as e:
                    logger.warning(f"Could not check keys for {user['UserName']}: {e}")

        except Exception as e:
            logger.error(f"Error scanning IAM access keys: {e}")
            results['error'] = str(e)

        return results

    def _scan_compute(self) -> Dict[str, Any]:
        """Scan compute resources (EC2, Lambda)."""
        results = {
            'issues': [],
            'ec2_count': 0,
            'lambda_count': 0
        }

        try:
            # Scan EC2 instances
            instances = self.ec2.describe_instances()
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] in ['running', 'stopped']:
                        results['ec2_count'] += 1

                        # Check IMDSv2
                        metadata_options = instance.get('MetadataOptions', {})
                        if metadata_options.get('HttpTokens') != 'required':
                            results['issues'].append({
                                'severity': 'HIGH',
                                'finding': f'EC2 instance {instance["InstanceId"]} not using IMDSv2',
                                'recommendation': 'Require IMDSv2 for all EC2 instances'
                            })

                        # Check detailed monitoring
                        if not instance.get('Monitoring', {}).get('State') == 'enabled':
                            results['issues'].append({
                                'severity': 'MEDIUM',
                                'finding': f'EC2 instance {instance["InstanceId"]} without detailed monitoring',
                                'recommendation': 'Enable detailed monitoring for production instances'
                            })

                        # Check if instance is in a public subnet with public IP
                        if instance.get('PublicIpAddress'):
                            results['issues'].append({
                                'severity': 'HIGH',
                                'finding': f'EC2 instance {instance["InstanceId"]} has public IP address',
                                'recommendation': 'Use private subnets and NAT Gateway or VPC endpoints'
                            })

            # Scan Lambda functions
            try:
                paginator = self.lambda_client.get_paginator('list_functions')
                for page in paginator.paginate():
                    for function in page['Functions']:
                        results['lambda_count'] += 1

                        # Check if Lambda has VPC config
                        if not function.get('VpcConfig') or not function['VpcConfig'].get('VpcId'):
                            results['issues'].append({
                                'severity': 'MEDIUM',
                                'finding': f'Lambda function {function["FunctionName"]} not in VPC',
                                'recommendation': 'Consider VPC placement for sensitive workloads'
                            })

                        # Check runtime versions (only flag really old ones)
                        runtime = function.get('Runtime', '')
                        if runtime and any(old in runtime for old in ['python3.7', 'python3.6', 'nodejs12', 'nodejs10']):
                            results['issues'].append({
                                'severity': 'HIGH',
                                'finding': f'Lambda {function["FunctionName"]} using deprecated runtime {runtime}',
                                'recommendation': 'Update to supported runtime version'
                            })

            except Exception as e:
                logger.warning(f"Could not scan Lambda functions: {e}")

        except Exception as e:
            logger.error(f"Error scanning compute: {e}")
            results['error'] = str(e)

        return results

    def _scan_databases(self) -> Dict[str, Any]:
        """Scan RDS and Aurora databases."""
        results = {
            'issues': [],
            'db_count': 0
        }

        try:
            # Scan RDS instances
            db_instances = self.rds.describe_db_instances()

            for db in db_instances['DBInstances']:
                results['db_count'] += 1

                # Check encryption at rest
                if not db.get('StorageEncrypted'):
                    results['issues'].append({
                        'severity': 'CRITICAL',
                        'finding': f'RDS instance {db["DBInstanceIdentifier"]} not encrypted at rest',
                        'recommendation': 'Enable encryption at rest for all databases'
                    })

                # Check public accessibility
                if db.get('PubliclyAccessible'):
                    results['issues'].append({
                        'severity': 'CRITICAL',
                        'finding': f'RDS instance {db["DBInstanceIdentifier"]} is publicly accessible',
                        'recommendation': 'Disable public accessibility for databases'
                    })

                # Check backup retention
                retention = db.get('BackupRetentionPeriod', 0)
                if retention < 7:
                    results['issues'].append({
                        'severity': 'HIGH',
                        'finding': f'RDS instance {db["DBInstanceIdentifier"]} backup retention is {retention} days (should be 7+)',
                        'recommendation': 'Set backup retention to at least 7 days'
                    })

                # Check Multi-AZ
                if not db.get('MultiAZ'):
                    results['issues'].append({
                        'severity': 'MEDIUM',
                        'finding': f'RDS instance {db["DBInstanceIdentifier"]} not Multi-AZ',
                        'recommendation': 'Enable Multi-AZ for production databases'
                    })

                # Check automated backups
                if not db.get('BackupRetentionPeriod') or db['BackupRetentionPeriod'] == 0:
                    results['issues'].append({
                        'severity': 'CRITICAL',
                        'finding': f'RDS instance {db["DBInstanceIdentifier"]} has automated backups disabled',
                        'recommendation': 'Enable automated backups'
                    })

        except Exception as e:
            logger.error(f"Error scanning databases: {e}")
            results['error'] = str(e)

        return results

    def _scan_security_services(self) -> Dict[str, Any]:
        """Scan security services (Security Hub, GuardDuty, Config)."""
        results = {
            'issues': [],
            'services': {}
        }

        try:
            # Check Security Hub
            try:
                hub = self.securityhub.describe_hub()
                results['services']['security_hub'] = 'enabled'
            except self.securityhub.exceptions.InvalidAccessException:
                results['services']['security_hub'] = 'not_enabled'
                results['issues'].append({
                    'severity': 'CRITICAL',
                    'finding': 'AWS Security Hub is not enabled',
                    'recommendation': 'Enable Security Hub for centralized security posture management'
                })
            except Exception:
                results['services']['security_hub'] = 'unknown'

            # Check GuardDuty
            try:
                detectors = self.guardduty.list_detectors()
                if detectors['DetectorIds']:
                    detector = self.guardduty.get_detector(DetectorId=detectors['DetectorIds'][0])
                    if detector['Status'] == 'ENABLED':
                        results['services']['guardduty'] = 'enabled'
                    else:
                        results['services']['guardduty'] = 'disabled'
                        results['issues'].append({
                            'severity': 'CRITICAL',
                            'finding': 'GuardDuty is disabled',
                            'recommendation': 'Enable GuardDuty for threat detection'
                        })
                else:
                    results['services']['guardduty'] = 'not_configured'
                    results['issues'].append({
                        'severity': 'CRITICAL',
                        'finding': 'GuardDuty is not configured',
                        'recommendation': 'Enable GuardDuty for threat detection'
                    })
            except Exception:
                results['services']['guardduty'] = 'unknown'

            # Check AWS Config
            try:
                recorders = self.config.describe_configuration_recorders()
                if recorders['ConfigurationRecorders']:
                    status = self.config.describe_configuration_recorder_status()
                    if status['ConfigurationRecordersStatus']:
                        if status['ConfigurationRecordersStatus'][0]['recording']:
                            results['services']['config'] = 'enabled'
                        else:
                            results['services']['config'] = 'not_recording'
                            results['issues'].append({
                                'severity': 'HIGH',
                                'finding': 'AWS Config is not recording',
                                'recommendation': 'Enable AWS Config recording'
                            })
                else:
                    results['services']['config'] = 'not_configured'
                    results['issues'].append({
                        'severity': 'HIGH',
                        'finding': 'AWS Config is not configured',
                        'recommendation': 'Enable AWS Config for compliance tracking'
                    })
            except Exception:
                results['services']['config'] = 'unknown'

        except Exception as e:
            logger.error(f"Error scanning security services: {e}")
            results['error'] = str(e)

        return results

    def _scan_logging(self) -> Dict[str, Any]:
        """Scan logging configuration."""
        results = {
            'issues': [],
            'log_groups': 0
        }

        try:
            # Check CloudWatch log groups and retention
            paginator = self.logs.get_paginator('describe_log_groups')
            for page in paginator.paginate():
                for log_group in page['logGroups']:
                    results['log_groups'] += 1

                    retention = log_group.get('retentionInDays')
                    if not retention:
                        results['issues'].append({
                            'severity': 'MEDIUM',
                            'finding': f'Log group {log_group["logGroupName"]} has no retention policy',
                            'recommendation': 'Set log retention to prevent indefinite storage costs'
                        })
                    elif retention < 90:
                        results['issues'].append({
                            'severity': 'MEDIUM',
                            'finding': f'Log group {log_group["logGroupName"]} retention is {retention} days (recommend 90+)',
                            'recommendation': 'Increase retention for compliance requirements'
                        })

            # Check ELB access logs
            try:
                load_balancers = self.elb.describe_load_balancers()
                for lb in load_balancers['LoadBalancers']:
                    attrs = self.elb.describe_load_balancer_attributes(LoadBalancerArn=lb['LoadBalancerArn'])

                    access_logs_enabled = False
                    for attr in attrs['Attributes']:
                        if attr['Key'] == 'access_logs.s3.enabled' and attr['Value'] == 'true':
                            access_logs_enabled = True
                            break

                    if not access_logs_enabled:
                        results['issues'].append({
                            'severity': 'MEDIUM',
                            'finding': f'Load Balancer {lb["LoadBalancerName"]} does not have access logs enabled',
                            'recommendation': 'Enable access logs for audit trail'
                        })
            except Exception as e:
                logger.warning(f"Could not check ELB access logs: {e}")

        except Exception as e:
            logger.error(f"Error scanning logging: {e}")
            results['error'] = str(e)

        return results

    def _scan_backup(self) -> Dict[str, Any]:
        """Scan backup configuration."""
        results = {
            'issues': [],
            'backup_plans': 0
        }

        try:
            # Check AWS Backup plans
            plans = self.backup.list_backup_plans()
            results['backup_plans'] = len(plans.get('BackupPlansList', []))

            if results['backup_plans'] == 0:
                results['issues'].append({
                    'severity': 'HIGH',
                    'finding': 'No AWS Backup plans configured',
                    'recommendation': 'Create backup plans for critical resources (RDS, EBS, EFS)'
                })

            # Check backup vaults
            vaults = self.backup.list_backup_vaults()
            if not vaults.get('BackupVaultList'):
                results['issues'].append({
                    'severity': 'HIGH',
                    'finding': 'No backup vaults configured',
                    'recommendation': 'Create backup vaults for disaster recovery'
                })

        except Exception as e:
            logger.error(f"Error scanning backup: {e}")
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

        # Collect statistics
        compute = scan_results.get('compute', {})
        databases = scan_results.get('databases', {})
        security_services = scan_results.get('security_services', {})
        iam_keys = scan_results.get('iam_access_keys', {})
        logging = scan_results.get('logging', {})
        backup = scan_results.get('backup', {})

        summary = f"""# Comprehensive AWS Environment Scan

**Account ID:** {scan_results.get('account_id', 'unknown')}
**Region:** {self.region}

## Environment Overview
- **EC2 Instances:** {compute.get('ec2_count', 0)}
- **Lambda Functions:** {compute.get('lambda_count', 0)}
- **RDS Databases:** {databases.get('db_count', 0)}
- **Access Keys Checked:** {iam_keys.get('keys_checked', 0)}
- **CloudWatch Log Groups:** {logging.get('log_groups', 0)}
- **Backup Plans:** {backup.get('backup_plans', 0)}

## Security Services Status
- **Security Hub:** {security_services.get('services', {}).get('security_hub', 'unknown')}
- **GuardDuty:** {security_services.get('services', {}).get('guardduty', 'unknown')}
- **AWS Config:** {security_services.get('services', {}).get('config', 'unknown')}

## Security Issues Found
- 🚨 **Critical:** {len(critical)}
- ⚠️  **High:** {len(high)}
- ⚡ **Medium:** {len(medium)}
- ✅ **Total:** {len(all_issues)}

"""

        if critical:
            summary += "\n### 🚨 Critical Issues (Fix Immediately)\n"
            for issue in critical[:8]:
                summary += f"- **{issue['finding']}**\n"
                summary += f"  _Recommendation: {issue['recommendation']}_\n\n"

        if high:
            summary += "\n### ⚠️ High Priority Issues\n"
            for issue in high[:8]:
                summary += f"- **{issue['finding']}**\n"
                summary += f"  _Recommendation: {issue['recommendation']}_\n\n"

        if medium and len(medium) > 5:
            summary += f"\n### ⚡ Medium Priority Issues ({len(medium)} total)\n"
            for issue in medium[:5]:
                summary += f"- {issue['finding']}\n"
            summary += f"\n_...and {len(medium) - 5} more medium priority issues_\n"
        elif medium:
            summary += "\n### ⚡ Medium Priority Issues\n"
            for issue in medium:
                summary += f"- {issue['finding']}\n"

        return summary
