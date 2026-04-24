"""
CARL Remediation Agent - AWS Bedrock AgentCore Runtime

This agent handles AI-powered security remediation with human approval.
It classifies findings by risk level and applies fixes either directly
(LOW risk) or via GitHub PR (MEDIUM/HIGH risk).

Deployed to: AWS Bedrock AgentCore Runtime
Entry Point: carl_remediate_agent.py
"""

import os
import sys
import json
import logging
import traceback
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum

# Configure logging early to capture startup issues
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

logger.info("=== CARL Remediation Agent Starting ===")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")

# Import boto3
try:
    import boto3
    logger.info(f"boto3 imported successfully, version: {boto3.__version__}")
except Exception as e:
    logger.error(f"Failed to import boto3: {e}")
    traceback.print_exc()

# AgentCore Runtime imports
try:
    from bedrock_agentcore.runtime import BedrockAgentCoreApp
    logger.info("BedrockAgentCoreApp imported successfully")
except Exception as e:
    logger.error(f"Failed to import BedrockAgentCoreApp: {e}")
    traceback.print_exc()
    raise

# Initialize AgentCore app
logger.info("Initializing BedrockAgentCoreApp...")
app = BedrockAgentCoreApp(debug=True)
logger.info("BedrockAgentCoreApp initialized successfully")

# Environment variables (set by Terraform)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
FOUNDATION_MODEL = os.environ.get("FOUNDATION_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
FINDINGS_TABLE = os.environ.get("FINDINGS_TABLE", "carl-dev-findings")
GITHUB_SECRET_ARN = os.environ.get("GITHUB_SECRET_ARN", "")

logger.info(f"Configuration: AWS_REGION={AWS_REGION}, FOUNDATION_MODEL={FOUNDATION_MODEL}")


# =============================================================================
# Risk Level Classification
# =============================================================================

class RiskLevel(Enum):
    """Risk level for remediation actions."""
    LOW = "LOW"          # Safe to apply directly (e.g., enable encryption)
    MEDIUM = "MEDIUM"    # May affect availability (e.g., modify security groups)
    HIGH = "HIGH"        # Could break services (e.g., change network config)


class RemediationMethod(Enum):
    """How the fix will be applied."""
    DIRECT_API = "DIRECT_API"     # Apply via AWS API directly
    TERRAFORM_PR = "TERRAFORM_PR"  # Create PR with Terraform code


# Risk classification for finding types
FINDING_RISK_MAP = {
    # LOW RISK - Safe to apply directly
    "s3_encryption": RiskLevel.LOW,
    "s3_versioning": RiskLevel.LOW,
    "s3_public_access_block": RiskLevel.LOW,
    "iam_password_policy": RiskLevel.LOW,
    "cloudtrail_enabled": RiskLevel.LOW,

    # MEDIUM RISK - May affect logging/monitoring
    "vpc_flow_logs": RiskLevel.MEDIUM,
    "cloudwatch_logging": RiskLevel.MEDIUM,
    "config_enabled": RiskLevel.MEDIUM,

    # HIGH RISK - Could break connectivity
    "security_group_open": RiskLevel.HIGH,
    "rds_public_access": RiskLevel.HIGH,
    "ec2_public_ip": RiskLevel.HIGH,
    "iam_mfa_user": RiskLevel.HIGH,
    "asg_public_ip": RiskLevel.HIGH,
}


def classify_finding_risk(finding: dict) -> RiskLevel:
    """Classify risk level for a finding."""
    title = finding.get("title", "").lower()
    description = finding.get("description", "").lower()

    # Check explicit mappings first
    for pattern, risk in FINDING_RISK_MAP.items():
        if pattern in title or pattern in description:
            return risk

    # Keyword-based classification
    high_risk_keywords = [
        "security group", "0.0.0.0/0", "publicly accessible",
        "public ip", "mfa", "ingress", "egress", "network acl"
    ]

    medium_risk_keywords = [
        "flow log", "cloudwatch", "logging", "monitoring",
        "config", "trail", "audit"
    ]

    low_risk_keywords = [
        "encryption", "versioning", "public access block",
        "password policy", "key rotation"
    ]

    combined = f"{title} {description}"

    for keyword in high_risk_keywords:
        if keyword in combined:
            return RiskLevel.HIGH

    for keyword in medium_risk_keywords:
        if keyword in combined:
            return RiskLevel.MEDIUM

    for keyword in low_risk_keywords:
        if keyword in combined:
            return RiskLevel.LOW

    return RiskLevel.MEDIUM


def get_remediation_method(risk_level: RiskLevel) -> RemediationMethod:
    """Determine remediation method based on risk level."""
    if risk_level == RiskLevel.LOW:
        return RemediationMethod.DIRECT_API
    return RemediationMethod.TERRAFORM_PR


# =============================================================================
# Resource Detection
# =============================================================================

@dataclass
class S3BucketStatus:
    """Status of an S3 bucket."""
    bucket_name: str
    encryption_enabled: bool = False
    encryption_type: Optional[str] = None
    versioning_enabled: bool = False
    public_access_block_enabled: bool = False


@dataclass
class IAMPasswordPolicyStatus:
    """Status of IAM password policy."""
    policy_exists: bool = False
    minimum_password_length: int = 0
    require_symbols: bool = False
    require_numbers: bool = False
    require_uppercase: bool = False
    require_lowercase: bool = False
    max_password_age: Optional[int] = None
    is_compliant: bool = False


class ResourceDetector:
    """Detects existing AWS resources to prevent duplicate creation."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.s3 = boto3.client("s3", region_name=region)
        self.iam = boto3.client("iam", region_name=region)
        self.ec2 = boto3.client("ec2", region_name=region)
        self.logs = boto3.client("logs", region_name=region)

    def detect_s3_bucket_status(self, bucket_name: str) -> S3BucketStatus:
        """Detect S3 bucket security status."""
        if bucket_name.startswith("arn:aws:s3:::"):
            bucket_name = bucket_name.replace("arn:aws:s3:::", "")

        status = S3BucketStatus(bucket_name=bucket_name)

        try:
            enc_config = self.s3.get_bucket_encryption(Bucket=bucket_name)
            rules = enc_config.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
            if rules:
                status.encryption_enabled = True
                status.encryption_type = rules[0].get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm")
        except Exception:
            pass

        try:
            v = self.s3.get_bucket_versioning(Bucket=bucket_name)
            status.versioning_enabled = v.get("Status") == "Enabled"
        except Exception:
            pass

        try:
            pab = self.s3.get_public_access_block(Bucket=bucket_name)["PublicAccessBlockConfiguration"]
            status.public_access_block_enabled = all([
                pab.get("BlockPublicAcls", False),
                pab.get("IgnorePublicAcls", False),
                pab.get("BlockPublicPolicy", False),
                pab.get("RestrictPublicBuckets", False)
            ])
        except Exception:
            pass

        return status

    def detect_iam_password_policy(self) -> IAMPasswordPolicyStatus:
        """Detect IAM password policy status."""
        status = IAMPasswordPolicyStatus()

        try:
            policy = self.iam.get_account_password_policy()["PasswordPolicy"]
            status.policy_exists = True
            status.minimum_password_length = policy.get("MinimumPasswordLength", 0)
            status.require_symbols = policy.get("RequireSymbols", False)
            status.require_numbers = policy.get("RequireNumbers", False)
            status.require_uppercase = policy.get("RequireUppercaseCharacters", False)
            status.require_lowercase = policy.get("RequireLowercaseCharacters", False)
            status.max_password_age = policy.get("MaxPasswordAge")

            # Check compliance
            status.is_compliant = (
                status.minimum_password_length >= 14 and
                status.require_symbols and
                status.require_numbers and
                status.require_uppercase and
                status.require_lowercase
            )
        except self.iam.exceptions.NoSuchEntityException:
            pass
        except Exception as e:
            logger.warning(f"Error detecting IAM password policy: {e}")

        return status

    def detect_remediation_status(self, finding: dict) -> dict:
        """Check if a finding has already been remediated."""
        title_lower = finding.get("title", "").lower()
        resource_id = finding.get("resource_id", "")
        resource_type = finding.get("resource_type", "").lower()

        # S3 encryption check
        if "encryption" in title_lower and "s3" in resource_type:
            status = self.detect_s3_bucket_status(resource_id)
            if status.encryption_enabled:
                return {
                    "already_remediated": True,
                    "existing_resource": {"type": "s3_encryption", "algorithm": status.encryption_type},
                    "message": f"S3 bucket already has encryption enabled ({status.encryption_type})"
                }

        # S3 versioning check
        elif "versioning" in title_lower and "s3" in resource_type:
            status = self.detect_s3_bucket_status(resource_id)
            if status.versioning_enabled:
                return {
                    "already_remediated": True,
                    "existing_resource": {"type": "s3_versioning"},
                    "message": "S3 bucket versioning is already enabled"
                }

        # S3 public access block check
        elif "public access" in title_lower and "s3" in resource_type:
            status = self.detect_s3_bucket_status(resource_id)
            if status.public_access_block_enabled:
                return {
                    "already_remediated": True,
                    "existing_resource": {"type": "s3_public_access_block"},
                    "message": "S3 public access block is already enabled"
                }

        # IAM password policy check
        elif "password policy" in title_lower:
            status = self.detect_iam_password_policy()
            if status.is_compliant:
                return {
                    "already_remediated": True,
                    "existing_resource": {"type": "iam_password_policy", "min_length": status.minimum_password_length},
                    "message": f"IAM password policy meets compliance requirements (min length: {status.minimum_password_length})"
                }

        return {
            "already_remediated": False,
            "existing_resource": None,
            "message": "Resource needs remediation"
        }


# =============================================================================
# Remediation Actions
# =============================================================================

class RemediationExecutor:
    """Executes remediation actions."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.s3 = boto3.client("s3", region_name=region)
        self.iam = boto3.client("iam", region_name=region)

    def apply_s3_encryption(self, bucket_name: str) -> dict:
        """Enable S3 bucket encryption."""
        try:
            if bucket_name.startswith("arn:aws:s3:::"):
                bucket_name = bucket_name.replace("arn:aws:s3:::", "")

            self.s3.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    "Rules": [{
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        },
                        "BucketKeyEnabled": True
                    }]
                }
            )

            logger.info(f"Enabled encryption on S3 bucket: {bucket_name}")
            return {"success": True, "action": "S3 encryption enabled", "bucket": bucket_name}

        except Exception as e:
            logger.exception(f"Error enabling S3 encryption: {bucket_name}")
            return {"success": False, "error": str(e)}

    def apply_s3_versioning(self, bucket_name: str) -> dict:
        """Enable S3 bucket versioning."""
        try:
            if bucket_name.startswith("arn:aws:s3:::"):
                bucket_name = bucket_name.replace("arn:aws:s3:::", "")

            self.s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"}
            )

            logger.info(f"Enabled versioning on S3 bucket: {bucket_name}")
            return {"success": True, "action": "S3 versioning enabled", "bucket": bucket_name}

        except Exception as e:
            logger.exception(f"Error enabling S3 versioning: {bucket_name}")
            return {"success": False, "error": str(e)}

    def apply_s3_public_access_block(self, bucket_name: str) -> dict:
        """Enable S3 public access block."""
        try:
            if bucket_name.startswith("arn:aws:s3:::"):
                bucket_name = bucket_name.replace("arn:aws:s3:::", "")

            self.s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True
                }
            )

            logger.info(f"Enabled public access block on S3 bucket: {bucket_name}")
            return {"success": True, "action": "S3 public access blocked", "bucket": bucket_name}

        except Exception as e:
            logger.exception(f"Error enabling S3 public access block: {bucket_name}")
            return {"success": False, "error": str(e)}

    def apply_iam_password_policy(self) -> dict:
        """Set strong IAM password policy."""
        try:
            self.iam.update_account_password_policy(
                MinimumPasswordLength=14,
                RequireSymbols=True,
                RequireNumbers=True,
                RequireUppercaseCharacters=True,
                RequireLowercaseCharacters=True,
                AllowUsersToChangePassword=True,
                MaxPasswordAge=90,
                PasswordReusePrevention=24,
                HardExpiry=True
            )

            logger.info("Updated IAM password policy")
            return {"success": True, "action": "IAM password policy updated"}

        except Exception as e:
            logger.exception("Error updating IAM password policy")
            return {"success": False, "error": str(e)}


# =============================================================================
# Terraform Generation
# =============================================================================

def generate_terraform_code(finding: dict, bedrock_client) -> str:
    """Generate Terraform code using AI."""
    title = finding.get("title", "")
    resource_id = finding.get("resource_id", "")
    resource_type = finding.get("resource_type", "")

    prompt = f"""Generate Terraform code to remediate this security finding.

FINDING:
- Title: {title}
- Resource Type: {resource_type}
- Resource ID: {resource_id}

REQUIREMENTS:
1. Use proper Terraform resource naming conventions
2. Include appropriate tags (ManagedBy = "CARL", Remediation = "true")
3. Follow AWS security best practices
4. Include any required IAM roles/policies with least privilege

Generate ONLY the Terraform HCL code, no explanations. The code should be production-ready and idempotent.
"""

    try:
        response = bedrock_client.invoke_model(
            modelId=FOUNDATION_MODEL,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "system": "You are a Terraform expert. Generate only HCL code, no explanations.",
                "messages": [{"role": "user", "content": prompt}],
            })
        )

        result = json.loads(response["body"].read())
        terraform_code = result["content"][0]["text"]

        # Clean up - extract HCL code from markdown if present
        hcl_match = re.search(r'```(?:hcl|terraform)?\s*\n(.*?)\n```', terraform_code, re.DOTALL)
        if hcl_match:
            terraform_code = hcl_match.group(1).strip()

        return terraform_code

    except Exception as e:
        logger.warning(f"AI generation failed: {e}")
        return f"# Error generating Terraform code: {e}"


# =============================================================================
# Mock Findings Service (for AgentCore - reads from DynamoDB)
# =============================================================================

class FindingsService:
    """Service to interact with findings stored in DynamoDB."""

    def __init__(self, table_name: str = None):
        self.table_name = table_name or FINDINGS_TABLE
        self.dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
        self.table = self.dynamodb.Table(self.table_name)

    def get_recent_findings(self, severity: str = None, status: str = "NEW", limit: int = 10) -> list:
        """Get recent findings from DynamoDB."""
        try:
            scan_kwargs = {"Limit": limit * 2}  # Get extra in case of filtering

            response = self.table.scan(**scan_kwargs)
            findings = response.get("Items", [])

            # Filter by status and severity
            filtered = []
            for f in findings:
                if status and f.get("status") != status:
                    continue
                if severity and f.get("severity") != severity:
                    continue
                filtered.append(f)
                if len(filtered) >= limit:
                    break

            return filtered

        except Exception as e:
            logger.error(f"Error getting findings: {e}")
            return []

    def get_finding(self, finding_id: str) -> Optional[dict]:
        """Get a specific finding by ID."""
        try:
            # Try to query by finding_id
            response = self.table.scan(
                FilterExpression="id = :fid",
                ExpressionAttributeValues={":fid": finding_id},
                Limit=1
            )
            items = response.get("Items", [])
            return items[0] if items else None

        except Exception as e:
            logger.error(f"Error getting finding {finding_id}: {e}")
            return None


# =============================================================================
# AgentCore Entrypoint
# =============================================================================

# Global instances
detector = ResourceDetector(region=AWS_REGION)
executor = RemediationExecutor(region=AWS_REGION)
findings_service = FindingsService()
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# In-memory pending approvals (in production, would use DynamoDB)
pending_approvals: dict[str, dict] = {}


@app.entrypoint
def invoke(payload: dict, context: Any = None) -> dict:
    """
    AgentCore Runtime entrypoint.

    Supported actions:
    - list: List findings that can be remediated
    - preview <finding_id>: Preview fix for a finding
    - approve <approval_id>: Apply an approved fix
    - generate <finding_id>: Generate fix and request approval
    """
    logger.info("=== INVOKE CALLED ===")
    logger.info(f"Payload: {json.dumps(payload, default=str)[:500]}")

    try:
        prompt = payload.get("prompt", "")

        if not prompt:
            return {"result": help_message()}

        prompt_lower = prompt.lower().strip()

        # Parse command
        if prompt_lower.startswith("list"):
            return {"result": handle_list(prompt)}
        elif prompt_lower.startswith("preview"):
            finding_id = prompt.split(maxsplit=1)[1] if len(prompt.split()) > 1 else ""
            return {"result": handle_preview(finding_id)}
        elif prompt_lower.startswith("generate") or prompt_lower.startswith("fix"):
            finding_id = prompt.split(maxsplit=1)[1] if len(prompt.split()) > 1 else ""
            return {"result": handle_generate(finding_id)}
        elif prompt_lower.startswith("approve"):
            approval_id = prompt.split(maxsplit=1)[1] if len(prompt.split()) > 1 else ""
            return {"result": handle_approve(approval_id)}
        elif prompt_lower.startswith("help"):
            return {"result": help_message()}
        else:
            # Default: use AI to understand and respond
            return {"result": handle_natural_language(prompt)}

    except Exception as e:
        logger.error(f"Error in invoke: {e}")
        traceback.print_exc()
        return {"result": f"Error: {str(e)}"}


def help_message() -> str:
    """Return help message."""
    return """*CARL Remediation Agent*

Commands:
- `list` - List findings that can be remediated (sorted by risk)
- `preview <finding_id>` - Preview what a fix will change
- `generate <finding_id>` - Generate fix and request approval
- `approve <approval_id>` - Apply an approved fix

Risk Levels:
- *LOW* (green): Applied directly via AWS API (e.g., S3 encryption)
- *MEDIUM* (yellow): Creates GitHub PR (e.g., VPC flow logs)
- *HIGH* (red): Creates GitHub PR for careful review (e.g., security groups)

CARL *never* applies fixes without explicit approval."""


def handle_list(prompt: str) -> str:
    """List findings that can be remediated."""
    findings = findings_service.get_recent_findings(status="NEW", limit=20)

    if not findings:
        return "No findings needing remediation. All clear!"

    # Classify and sort by risk
    classified = []
    already_fixed = []

    for f in findings:
        detection = detector.detect_remediation_status(f)
        if detection["already_remediated"]:
            already_fixed.append(f)
            continue

        risk = classify_finding_risk(f)
        method = get_remediation_method(risk)
        classified.append({
            "finding": f,
            "risk": risk,
            "method": method
        })

    # Sort by risk (LOW first)
    risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
    classified.sort(key=lambda x: risk_order.get(x["risk"], 1))

    # Build response
    lines = [f"*Findings Needing Remediation* ({len(classified)} total)\n"]

    risk_emoji = {RiskLevel.LOW: ":green_circle:", RiskLevel.MEDIUM: ":yellow_circle:", RiskLevel.HIGH: ":red_circle:"}

    for item in classified[:10]:  # Limit to 10
        f = item["finding"]
        risk = item["risk"]
        method = item["method"]

        emoji = risk_emoji.get(risk, ":white_circle:")
        lines.append(f"{emoji} *{risk.value}* | `{f.get('id', 'unknown')[:12]}` | {f.get('title', 'Unknown')}")
        lines.append(f"   Resource: `{f.get('resource_id', 'unknown')[:40]}`")
        lines.append(f"   Method: {method.value}")
        lines.append("")

    if already_fixed:
        lines.append(f"\n_({len(already_fixed)} findings already remediated)_")

    return "\n".join(lines)


def handle_preview(finding_id: str) -> str:
    """Preview what a fix will change."""
    if not finding_id:
        return "Please provide a finding ID. Example: `preview finding-123`"

    finding = findings_service.get_finding(finding_id)
    if not finding:
        return f"Finding `{finding_id}` not found."

    detection = detector.detect_remediation_status(finding)
    if detection["already_remediated"]:
        return f"Finding `{finding_id}` is already remediated: {detection['message']}"

    risk = classify_finding_risk(finding)
    method = get_remediation_method(risk)

    lines = [
        f"*Preview: {finding.get('title', 'Unknown')}*\n",
        f"*Finding ID:* `{finding_id}`",
        f"*Resource:* `{finding.get('resource_id', 'unknown')}`",
        f"*Risk Level:* {risk.value}",
        f"*Method:* {method.value}",
        "",
        "*What will change:*"
    ]

    title_lower = finding.get("title", "").lower()
    if "encryption" in title_lower:
        lines.append("- Server-side encryption: Disabled -> Enabled (AES-256)")
    elif "versioning" in title_lower:
        lines.append("- Versioning: Disabled -> Enabled")
    elif "public access" in title_lower:
        lines.append("- Public access: Allowed -> Blocked")
    elif "password policy" in title_lower:
        lines.append("- Password policy: Weak/Default -> Strong (14+ chars, symbols, rotation)")
    else:
        lines.append("- Configuration: Non-compliant -> Compliant")

    lines.append(f"\nUse `generate {finding_id}` to create the fix.")

    return "\n".join(lines)


def handle_generate(finding_id: str) -> str:
    """Generate fix and request approval."""
    if not finding_id:
        return "Please provide a finding ID. Example: `generate finding-123`"

    finding = findings_service.get_finding(finding_id)
    if not finding:
        return f"Finding `{finding_id}` not found."

    detection = detector.detect_remediation_status(finding)
    if detection["already_remediated"]:
        return f"Finding `{finding_id}` is already remediated: {detection['message']}"

    risk = classify_finding_risk(finding)
    method = get_remediation_method(risk)

    # Generate Terraform code
    terraform_code = generate_terraform_code(finding, bedrock)

    # Create approval ID
    approval_id = hashlib.md5(
        f"{finding_id}:{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:12]

    # Store pending approval
    pending_approvals[approval_id] = {
        "finding_id": finding_id,
        "finding": finding,
        "risk": risk.value,
        "method": method.value,
        "terraform_code": terraform_code,
        "created_at": datetime.utcnow().isoformat(),
    }

    lines = [
        f"*Fix Generated: {finding.get('title', 'Unknown')}*\n",
        f"*Approval ID:* `{approval_id}`",
        f"*Risk Level:* {risk.value}",
        f"*Method:* {method.value}",
        "",
        "*Terraform Code:*",
        "```hcl",
        terraform_code[:1500],  # Truncate if too long
        "```",
        "",
        f"To apply this fix, use: `approve {approval_id}`"
    ]

    return "\n".join(lines)


def handle_approve(approval_id: str) -> str:
    """Apply an approved fix."""
    if not approval_id:
        return "Please provide an approval ID. Example: `approve abc123def456`"

    approval = pending_approvals.get(approval_id)
    if not approval:
        return f"Approval `{approval_id}` not found or expired."

    finding = approval["finding"]
    risk = RiskLevel(approval["risk"])
    method = RemediationMethod(approval["method"])

    if method == RemediationMethod.DIRECT_API:
        # Apply directly via AWS API
        title_lower = finding.get("title", "").lower()
        resource_id = finding.get("resource_id", "")
        resource_type = finding.get("resource_type", "").lower()

        if "encryption" in title_lower and "s3" in resource_type:
            result = executor.apply_s3_encryption(resource_id)
        elif "versioning" in title_lower and "s3" in resource_type:
            result = executor.apply_s3_versioning(resource_id)
        elif "public access" in title_lower and "s3" in resource_type:
            result = executor.apply_s3_public_access_block(resource_id)
        elif "password policy" in title_lower:
            result = executor.apply_iam_password_policy()
        else:
            result = {"success": False, "error": "Direct API fix not implemented for this finding type"}

        if result.get("success"):
            del pending_approvals[approval_id]
            return f":white_check_mark: *Fix Applied Successfully*\n\n{result.get('action', 'Fix applied')}\n\nTerraform code for audit:\n```hcl\n{approval['terraform_code'][:500]}\n```"
        else:
            return f":x: *Fix Failed*\n\nError: {result.get('error', 'Unknown error')}"

    else:
        # For MEDIUM/HIGH risk, would create GitHub PR
        # For now, return the Terraform code
        return f":warning: *MEDIUM/HIGH Risk Fix*\n\nThis fix requires review via GitHub PR.\n\nTerraform code:\n```hcl\n{approval['terraform_code'][:1000]}\n```\n\n_In production, this would create a GitHub PR automatically._"


def handle_natural_language(prompt: str) -> str:
    """Handle natural language queries using AI."""
    # Get findings context
    findings = findings_service.get_recent_findings(limit=5)
    findings_context = json.dumps(findings, default=str)[:2000]

    system_prompt = """You are CARL's Remediation Agent. Help users understand and fix security findings.

Available commands:
- list: List findings needing remediation
- preview <id>: Preview a fix
- generate <id>: Generate fix code
- approve <id>: Apply an approved fix

Be concise and direct. If the user seems to want to fix something, guide them to use the appropriate command."""

    try:
        response = bedrock.invoke_model(
            modelId=FOUNDATION_MODEL,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": f"Current findings:\n{findings_context}\n\nUser request: {prompt}"
                    }
                ],
            })
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    except Exception as e:
        logger.error(f"AI response failed: {e}")
        return f"I can help you remediate security findings. Try `list` to see available fixes or `help` for commands."


# AgentCore entry point
if __name__ == "__main__":
    logger.info("=== Starting CARL Remediation Agent Server ===")
    logger.info(f"Listening on port 8080")
    try:
        app.run(port=8080)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        traceback.print_exc()
        sys.exit(1)
