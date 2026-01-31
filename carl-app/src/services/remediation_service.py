"""
Remediation Service for CARL.

Generates remediation commands and code for security findings.
Users can copy/paste commands to fix issues manually.

**Manual Remediation Approach:**
- CARL has NO write permissions (safe)
- CARL generates commands/code for user
- User reviews and executes manually
- Clear audit trail (user's IAM credentials)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import json

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RemediationGuidance:
    """Remediation guidance for a security finding."""
    finding_id: str
    title: str
    description: str
    aws_cli_commands: List[str]
    terraform_code: Optional[str] = None
    manual_steps: Optional[List[str]] = None
    references: Optional[List[str]] = None
    estimated_time: str = "5 minutes"
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH for risk of running this fix


class RemediationService:
    """
    Service for generating remediation guidance.

    Provides AWS CLI commands, Terraform code, and manual steps
    for fixing security findings.
    """

    def generate_remediation(self, finding: Dict) -> Optional[RemediationGuidance]:
        """
        Generate remediation guidance for a finding.

        Args:
            finding: Finding dict with resource_type, resource_id, title, description

        Returns:
            RemediationGuidance with commands and steps, or None if no remediation available
        """
        finding_id = finding.get('id', 'unknown')
        resource_type = finding.get('resource_type', '').upper()  # Normalize to uppercase for matching
        resource_id = finding.get('resource_id', '')
        title = finding.get('title', '')
        description = finding.get('description', '')

        # S3 Encryption
        if 'S3' in resource_type and 'encryption' in title.lower():
            bucket_name = self._extract_bucket_name(resource_id)
            return RemediationGuidance(
                finding_id=finding_id,
                title="Enable S3 Bucket Encryption",
                description=f"Enable default encryption on S3 bucket {bucket_name}",
                aws_cli_commands=[
                    f"# Enable AES256 encryption on {bucket_name}",
                    f"aws s3api put-bucket-encryption \\",
                    f"  --bucket {bucket_name} \\",
                    f"  --server-side-encryption-configuration '{{",
                    f"    \"Rules\": [{{",
                    f"      \"ApplyServerSideEncryptionByDefault\": {{",
                    f"        \"SSEAlgorithm\": \"AES256\"",
                    f"      }},",
                    f"      \"BucketKeyEnabled\": true",
                    f"    }}]",
                    f"  }}'",
                    "",
                    f"# Or use KMS encryption (recommended for sensitive data):",
                    f"aws s3api put-bucket-encryption \\",
                    f"  --bucket {bucket_name} \\",
                    f"  --server-side-encryption-configuration '{{",
                    f"    \"Rules\": [{{",
                    f"      \"ApplyServerSideEncryptionByDefault\": {{",
                    f"        \"SSEAlgorithm\": \"aws:kms\",",
                    f"        \"KMSMasterKeyID\": \"alias/aws/s3\"",
                    f"      }},",
                    f"      \"BucketKeyEnabled\": true",
                    f"    }}]",
                    f"  }}'",
                ],
                terraform_code=f"""
resource "aws_s3_bucket_server_side_encryption_configuration" "{bucket_name.replace('-', '_')}_encryption" {{
  bucket = "{bucket_name}"

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm     = "AES256"
      # Or use KMS:
      # sse_algorithm     = "aws:kms"
      # kms_master_key_id = aws_kms_key.my_key.arn
    }}
    bucket_key_enabled = true
  }}
}}
""",
                references=[
                    "https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-bucket-encryption.html"
                ],
                estimated_time="2 minutes",
                risk_level="LOW"
            )

        # S3 Public Access
        elif 'S3' in resource_type and 'public' in title.lower():
            bucket_name = self._extract_bucket_name(resource_id)
            return RemediationGuidance(
                finding_id=finding_id,
                title="Block S3 Bucket Public Access",
                description=f"Enable public access block on S3 bucket {bucket_name}",
                aws_cli_commands=[
                    f"# Block all public access on {bucket_name}",
                    f"aws s3api put-public-access-block \\",
                    f"  --bucket {bucket_name} \\",
                    f"  --public-access-block-configuration \\",
                    f"    BlockPublicAcls=true,\\",
                    f"    IgnorePublicAcls=true,\\",
                    f"    BlockPublicPolicy=true,\\",
                    f"    RestrictPublicBuckets=true",
                ],
                terraform_code=f"""
resource "aws_s3_bucket_public_access_block" "{bucket_name.replace('-', '_')}_public_access_block" {{
  bucket = "{bucket_name}"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}
""",
                references=[
                    "https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html"
                ],
                estimated_time="1 minute",
                risk_level="LOW"
            )

        # S3 Versioning
        elif 'S3' in resource_type and 'versioning' in title.lower():
            bucket_name = self._extract_bucket_name(resource_id)
            return RemediationGuidance(
                finding_id=finding_id,
                title="Enable S3 Bucket Versioning",
                description=f"Enable versioning on S3 bucket {bucket_name}",
                aws_cli_commands=[
                    f"# Enable versioning on {bucket_name}",
                    f"aws s3api put-bucket-versioning \\",
                    f"  --bucket {bucket_name} \\",
                    f"  --versioning-configuration Status=Enabled",
                ],
                terraform_code=f"""
resource "aws_s3_bucket_versioning" "{bucket_name.replace('-', '_')}_versioning" {{
  bucket = "{bucket_name}"

  versioning_configuration {{
    status = "Enabled"
  }}
}}
""",
                references=[
                    "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html"
                ],
                estimated_time="1 minute",
                risk_level="LOW"
            )

        # IAM Password Policy
        elif 'iam' in resource_type.lower() and 'password policy' in title.lower():
            return RemediationGuidance(
                finding_id=finding_id,
                title="Configure IAM Password Policy",
                description="Set account-level password policy with security best practices",
                aws_cli_commands=[
                    "# Set strong password policy",
                    "aws iam update-account-password-policy \\",
                    "  --minimum-password-length 14 \\",
                    "  --require-symbols \\",
                    "  --require-numbers \\",
                    "  --require-uppercase-characters \\",
                    "  --require-lowercase-characters \\",
                    "  --allow-users-to-change-password \\",
                    "  --max-password-age 90 \\",
                    "  --password-reuse-prevention 24 \\",
                    "  --hard-expiry",
                ],
                terraform_code="""
resource "aws_iam_account_password_policy" "strict" {
  minimum_password_length        = 14
  require_lowercase_characters   = true
  require_uppercase_characters   = true
  require_numbers                = true
  require_symbols                = true
  allow_users_to_change_password = true
  max_password_age               = 90
  password_reuse_prevention      = 24
  hard_expiry                    = true
}
""",
                references=[
                    "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_passwords_account-policy.html"
                ],
                estimated_time="2 minutes",
                risk_level="LOW"
            )

        # IAM MFA
        elif 'iam' in resource_type.lower() and 'mfa' in title.lower():
            user_name = self._extract_username(resource_id)
            return RemediationGuidance(
                finding_id=finding_id,
                title="Enable MFA for IAM User",
                description=f"Enable multi-factor authentication for user {user_name}",
                aws_cli_commands=[
                    f"# MFA must be enabled via AWS Console or programmatically with virtual/hardware device",
                    f"# Step 1: Create virtual MFA device",
                    f"aws iam create-virtual-mfa-device \\",
                    f"  --virtual-mfa-device-name {user_name}-mfa \\",
                    f"  --outfile /tmp/{user_name}-qr-code.png \\",
                    f"  --bootstrap-method QRCodePNG",
                    "",
                    f"# Step 2: Scan QR code with authenticator app and get two consecutive codes",
                    "",
                    f"# Step 3: Enable MFA device (replace CODE1 and CODE2 with actual codes)",
                    f"aws iam enable-mfa-device \\",
                    f"  --user-name {user_name} \\",
                    f"  --serial-number arn:aws:iam::ACCOUNT-ID:mfa/{user_name}-mfa \\",
                    f"  --authentication-code1 CODE1 \\",
                    f"  --authentication-code2 CODE2",
                ],
                manual_steps=[
                    f"1. Go to IAM Console → Users → {user_name} → Security credentials",
                    "2. Click 'Assign MFA device'",
                    "3. Choose 'Virtual MFA device'",
                    "4. Scan QR code with authenticator app (Google Authenticator, Authy, etc.)",
                    "5. Enter two consecutive codes from the app",
                    "6. Click 'Assign MFA'",
                ],
                references=[
                    "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_enable_virtual.html"
                ],
                estimated_time="5 minutes",
                risk_level="LOW"
            )

        # Security Group 0.0.0.0/0
        elif 'security' in resource_type.lower() and '0.0.0.0/0' in description:
            sg_id = resource_id
            return RemediationGuidance(
                finding_id=finding_id,
                title="Remove Overly Permissive Security Group Rule",
                description=f"Remove 0.0.0.0/0 ingress rule from security group {sg_id}",
                aws_cli_commands=[
                    f"# First, describe the security group to see all rules",
                    f"aws ec2 describe-security-groups --group-ids {sg_id}",
                    "",
                    f"# Then revoke the specific rule (example for SSH on port 22):",
                    f"aws ec2 revoke-security-group-ingress \\",
                    f"  --group-id {sg_id} \\",
                    f"  --protocol tcp \\",
                    f"  --port 22 \\",
                    f"  --cidr 0.0.0.0/0",
                    "",
                    f"# Add restricted rule (example: only from your office IP)",
                    f"aws ec2 authorize-security-group-ingress \\",
                    f"  --group-id {sg_id} \\",
                    f"  --protocol tcp \\",
                    f"  --port 22 \\",
                    f"  --cidr YOUR_OFFICE_IP/32",
                ],
                manual_steps=[
                    f"1. Go to EC2 Console → Security Groups → {sg_id}",
                    "2. Click 'Inbound rules' tab",
                    "3. Find rules with Source '0.0.0.0/0'",
                    "4. Click 'Edit inbound rules'",
                    "5. Delete the 0.0.0.0/0 rule or change to specific IP/CIDR",
                    "6. Add rule with your specific IP range if needed",
                    "7. Click 'Save rules'",
                ],
                references=[
                    "https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html"
                ],
                estimated_time="5 minutes",
                risk_level="HIGH"  # Could break connectivity
            )

        # VPC Flow Logs
        elif 'vpc' in resource_type.lower() and 'flow log' in title.lower():
            vpc_id = resource_id.split('/')[-1]
            return RemediationGuidance(
                finding_id=finding_id,
                title="Enable VPC Flow Logs",
                description=f"Enable flow logs on VPC {vpc_id}",
                aws_cli_commands=[
                    f"# Create CloudWatch log group",
                    f"aws logs create-log-group --log-group-name /aws/vpc/flowlogs/{vpc_id}",
                    "",
                    f"# Create IAM role for flow logs (if doesn't exist)",
                    f"# See: https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs-cwl.html#flow-logs-iam",
                    "",
                    f"# Enable VPC flow logs",
                    f"aws ec2 create-flow-logs \\",
                    f"  --resource-type VPC \\",
                    f"  --resource-ids {vpc_id} \\",
                    f"  --traffic-type ALL \\",
                    f"  --log-destination-type cloud-watch-logs \\",
                    f"  --log-group-name /aws/vpc/flowlogs/{vpc_id} \\",
                    f"  --deliver-logs-permission-arn arn:aws:iam::ACCOUNT-ID:role/flowlogsRole",
                ],
                terraform_code=f"""
resource "aws_flow_log" "{vpc_id.replace('-', '_')}_flow_log" {{
  iam_role_arn    = aws_iam_role.flowlogs.arn
  log_destination = aws_cloudwatch_log_group.vpc_flowlogs.arn
  traffic_type    = "ALL"
  vpc_id          = "{vpc_id}"
}}

resource "aws_cloudwatch_log_group" "vpc_flowlogs" {{
  name              = "/aws/vpc/flowlogs/{vpc_id}"
  retention_in_days = 30
}}

resource "aws_iam_role" "flowlogs" {{
  name = "vpc-flowlogs-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Principal = {{
        Service = "vpc-flow-logs.amazonaws.com"
      }}
      Action = "sts:AssumeRole"
    }}]
  }})
}}

resource "aws_iam_role_policy" "flowlogs" {{
  name = "vpc-flowlogs-policy"
  role = aws_iam_role.flowlogs.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ]
      Resource = "*"
    }}]
  }})
}}
""",
                references=[
                    "https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html"
                ],
                estimated_time="10 minutes",
                risk_level="LOW"
            )

        # CloudTrail Not Enabled
        elif 'cloudtrail' in resource_type.lower() and ('not enabled' in title.lower() or 'not configured' in title.lower()):
            return RemediationGuidance(
                finding_id=finding_id,
                title="Enable CloudTrail",
                description="Enable CloudTrail for audit logging",
                aws_cli_commands=[
                    "# Create S3 bucket for CloudTrail logs",
                    "aws s3 mb s3://my-cloudtrail-logs-ACCOUNT-ID-REGION",
                    "",
                    "# Create CloudTrail",
                    "aws cloudtrail create-trail \\",
                    "  --name my-cloudtrail \\",
                    "  --s3-bucket-name my-cloudtrail-logs-ACCOUNT-ID-REGION \\",
                    "  --is-multi-region-trail \\",
                    "  --enable-log-file-validation",
                    "",
                    "# Start logging",
                    "aws cloudtrail start-logging --name my-cloudtrail",
                ],
                terraform_code="""
resource "aws_cloudtrail" "main" {
  name                          = "main-cloudtrail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true
  }
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket = "my-cloudtrail-logs-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AWSCloudTrailAclCheck"
      Effect = "Allow"
      Principal = {
        Service = "cloudtrail.amazonaws.com"
      }
      Action   = "s3:GetBucketAcl"
      Resource = aws_s3_bucket.cloudtrail.arn
    },
    {
      Sid    = "AWSCloudTrailWrite"
      Effect = "Allow"
      Principal = {
        Service = "cloudtrail.amazonaws.com"
      }
      Action   = "s3:PutObject"
      Resource = "${aws_s3_bucket.cloudtrail.arn}/*"
      Condition = {
        StringEquals = {
          "s3:x-amz-acl" = "bucket-owner-full-control"
        }
      }
    }]
  })
}
""",
                references=[
                    "https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-create-and-update-a-trail.html"
                ],
                estimated_time="15 minutes",
                risk_level="LOW"
            )

        # RDS Publicly Accessible
        elif 'rds' in resource_type.lower() and 'publicly accessible' in title.lower():
            db_instance = resource_id.split(':')[-1]
            return RemediationGuidance(
                finding_id=finding_id,
                title="Make RDS Database Private",
                description=f"Disable public accessibility on RDS instance {db_instance}",
                aws_cli_commands=[
                    f"# Make RDS instance private",
                    f"aws rds modify-db-instance \\",
                    f"  --db-instance-identifier {db_instance} \\",
                    f"  --no-publicly-accessible \\",
                    f"  --apply-immediately",
                    "",
                    "# Note: This will cause brief downtime during modification",
                ],
                terraform_code=f"""
resource "aws_db_instance" "{db_instance.replace('-', '_')}" {{
  # ... other configuration ...

  publicly_accessible = false

  # Ensure it's in private subnets
  db_subnet_group_name = aws_db_subnet_group.private.name
}}
""",
                references=[
                    "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html"
                ],
                estimated_time="5 minutes",
                risk_level="HIGH"  # Could break connectivity if app expects public access
            )

        # Default case - generic guidance
        else:
            logger.warning(f"No specific remediation guidance for finding: {title}")
            return None

    def _extract_bucket_name(self, resource_id: str) -> str:
        """Extract bucket name from S3 ARN or ID."""
        if resource_id.startswith('arn:aws:s3:::'):
            return resource_id.replace('arn:aws:s3:::', '')
        return resource_id

    def _extract_username(self, resource_id: str) -> str:
        """Extract username from IAM ARN or ID."""
        if 'user/' in resource_id:
            return resource_id.split('user/')[-1]
        return resource_id

    def format_for_slack(self, guidance: RemediationGuidance) -> Dict:
        """
        Format remediation guidance for Slack display.

        Args:
            guidance: RemediationGuidance object

        Returns:
            Dict with Slack blocks for rich display
        """
        risk_emoji = {
            'LOW': '🟢',
            'MEDIUM': '🟡',
            'HIGH': '🔴'
        }

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🔧 {guidance.title}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": guidance.description}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Estimated Time:* {guidance.estimated_time}"},
                    {"type": "mrkdwn", "text": f"*Risk Level:* {risk_emoji.get(guidance.risk_level, '⚪')} {guidance.risk_level}"},
                ]
            }
        ]

        # AWS CLI Commands
        if guidance.aws_cli_commands:
            cli_code = "\n".join(guidance.aws_cli_commands)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*AWS CLI Commands:*\n```bash\n{cli_code}\n```"}
            })

        # Terraform Code
        if guidance.terraform_code:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Terraform Code:*\n```hcl\n{guidance.terraform_code.strip()}\n```"}
            })

        # Manual Steps
        if guidance.manual_steps:
            steps_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(guidance.manual_steps))
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Manual Steps (AWS Console):*\n{steps_text}"}
            })

        # References
        if guidance.references:
            refs_text = "\n".join(f"• {ref}" for ref in guidance.references)
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"*References:*\n{refs_text}"}]
            })

        return {"blocks": blocks}
