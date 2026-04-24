"""
Remediation Agent for CARL.

An AI-powered agent that can remediate security findings with human approval.

Key Features:
- Risk-based ranking (LOW, MEDIUM, HIGH)
- Human-in-the-loop approval workflow
- Low-risk fixes: Direct AWS API calls (with approval)
- High-risk fixes: Creates GitHub PRs for Terraform changes
- Always generates Terraform code (even for direct fixes)

Design Principles:
- NEVER auto-fix without explicit user approval
- Rank findings by risk to help users prioritize
- Show full fix details before execution
- Generate audit trail for all actions
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional
from dataclasses import dataclass, asdict

import boto3
from boto3.dynamodb.conditions import Key

from services.agent_core import AgentCore, Tool
from services.findings_service import FindingsService
from services.remediation_service import RemediationService, RemediationGuidance
from services.github_service import GitHubService
from services.github_app_service import GitHubAppAuth
from services.resource_detector import ResourceDetector
from utils.aws_client import get_secret
from utils.logger import get_logger

logger = get_logger(__name__)

# DynamoDB table for persisting approvals across Lambda invocations
APPROVALS_TABLE = os.environ.get("APPROVALS_TABLE", "carl-dev-approvals")

# GitHub configuration (matches Lambda environment variables from main.tf)
GITHUB_APP_CREDENTIALS_SECRET = os.environ.get("GITHUB_APP_CREDENTIALS_SECRET", "/carl/dev/github-app-credentials")
GITHUB_INFRA_TOKEN_SECRET = os.environ.get("GITHUB_INFRA_TOKEN_SECRET", "")
GITHUB_INFRA_OWNER = os.environ.get("GITHUB_INFRA_OWNER", "")
GITHUB_INFRA_REPO = os.environ.get("GITHUB_INFRA_REPO", "carl-infrastructure")


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
# LOW: Non-disruptive, additive changes only
# MEDIUM: Could affect monitoring/logging
# HIGH: Could break connectivity/access
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
    "iam_mfa_user": RiskLevel.HIGH,  # Can lock out users
    "asg_public_ip": RiskLevel.HIGH,
}


def classify_finding_risk(finding: dict) -> RiskLevel:
    """
    Classify risk level for a finding.

    Uses title/description keywords to determine risk level.
    """
    title = finding.get("title", "").lower()
    description = finding.get("description", "").lower()
    resource_type = finding.get("resource_type", "").lower()

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

    # Default to MEDIUM for unknown patterns
    return RiskLevel.MEDIUM


def get_remediation_method(risk_level: RiskLevel) -> RemediationMethod:
    """
    Determine remediation method based on risk level.

    LOW risk -> Direct API call (faster, simpler)
    MEDIUM/HIGH risk -> Terraform PR (review required)
    """
    if risk_level == RiskLevel.LOW:
        return RemediationMethod.DIRECT_API
    return RemediationMethod.TERRAFORM_PR


# =============================================================================
# Remediation Request/Result Models
# =============================================================================

@dataclass
class RemediationRequest:
    """A request to remediate a finding."""
    finding_id: str
    account_id: str
    finding: dict
    risk_level: RiskLevel
    method: RemediationMethod
    terraform_code: str
    aws_cli_commands: list[str]
    requested_by: str
    requested_at: str
    status: str = "PENDING_APPROVAL"  # PENDING_APPROVAL, APPROVED, REJECTED, APPLIED, FAILED
    approval_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "account_id": self.account_id,
            "finding": self.finding,
            "risk_level": self.risk_level.value,
            "method": self.method.value,
            "terraform_code": self.terraform_code,
            "aws_cli_commands": self.aws_cli_commands,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at,
            "status": self.status,
            "approval_id": self.approval_id,
        }


@dataclass
class RemediationResult:
    """Result of a remediation action."""
    finding_id: str
    success: bool
    method: RemediationMethod
    pr_url: Optional[str] = None
    applied_at: Optional[str] = None
    error: Optional[str] = None
    terraform_code: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "success": self.success,
            "method": self.method.value,
            "pr_url": self.pr_url,
            "applied_at": self.applied_at,
            "error": self.error,
            "terraform_code": self.terraform_code,
        }


# =============================================================================
# Remediation Agent
# =============================================================================

class RemediationAgent:
    """
    AI-powered remediation agent with human approval workflow.

    Workflow:
    1. User requests remediation for finding(s)
    2. Agent classifies risk and generates fix code
    3. User approves/rejects each fix
    4. Agent applies approved fixes (direct API or PR)
    5. Agent reports results
    """

    def __init__(
        self,
        region: str = "us-east-1",
        github_token_or_provider: Optional[Any] = None,
        infra_repo: Optional[str] = None,
        infra_repo_owner: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.region = region
        self.findings_service = FindingsService()
        self.remediation_service = RemediationService()
        self.resource_detector = ResourceDetector(region=region)
        self.progress_callback = progress_callback

        # GitHub service for PR creation (use module-level constants as defaults)
        self.github_token_or_provider = github_token_or_provider
        self.infra_repo = infra_repo or GITHUB_INFRA_REPO
        self.infra_repo_owner = infra_repo_owner or GITHUB_INFRA_OWNER

        # DynamoDB for persistent approval storage (required for Lambda)
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.approvals_table = self.dynamodb.Table(APPROVALS_TABLE)

        # Build the agent
        self._build_agent()

    def _build_agent(self):
        """Build the AgentCore with remediation tools."""
        instructions = """You are a security remediation agent for CARL.

Your job is to help users fix security findings in their AWS environment safely.

IMPORTANT RULES:
1. NEVER apply fixes without explicit user approval
2. Always show the fix details (risk level, Terraform code) before asking for approval
3. For HIGH risk fixes, strongly recommend reviewing the Terraform PR before merging
4. Generate Terraform code for ALL fixes (even if applying directly via API)
5. Maintain audit trail of all actions

When presenting fixes to users:
- Group by risk level (show LOW risk first, then MEDIUM, then HIGH)
- Explain what each fix will do in plain language
- Show the exact changes that will be made
- Warn about potential impacts for HIGH risk fixes

You have access to these tools:
- get_pending_remediations: List findings that can be remediated
- get_finding_details: Get full details of a specific finding
- generate_fix: Generate Terraform code and CLI commands for a fix
- preview_fix: Show what a fix will change before applying
- apply_direct_fix: Apply a LOW risk fix directly via AWS API (requires approval)
- create_fix_pr: Create a GitHub PR with Terraform fix (for MEDIUM/HIGH risk)
"""

        self.agent = AgentCore(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            system_instructions=instructions,
            max_turns=10,
            region=self.region,
            progress_callback=self.progress_callback,
        )

        # Register tools
        for tool in self._create_tools():
            self.agent.add_tool(tool)

    def _create_tools(self) -> list[Tool]:
        """Create the remediation tools."""
        return [
            Tool(
                name="get_pending_remediations",
                description="Get a list of findings that can be remediated, ranked by risk level. Returns finding ID, title, risk level, and recommended remediation method.",
                function=self._get_pending_remediations,
                input_schema={
                    "type": "object",
                    "properties": {
                        "severity_filter": {
                            "type": "string",
                            "description": "Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)",
                            "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of findings to return",
                            "default": 10
                        }
                    },
                    "required": []
                }
            ),
            Tool(
                name="get_finding_details",
                description="Get full details of a specific finding including resource information and recommended fix.",
                function=self._get_finding_details,
                input_schema={
                    "type": "object",
                    "properties": {
                        "finding_id": {
                            "type": "string",
                            "description": "The ID of the finding to retrieve"
                        }
                    },
                    "required": ["finding_id"]
                }
            ),
            Tool(
                name="generate_fix",
                description="Generate Terraform code and AWS CLI commands for remediating a finding. Always call this before apply_direct_fix or create_fix_pr.",
                function=self._generate_fix,
                input_schema={
                    "type": "object",
                    "properties": {
                        "finding_id": {
                            "type": "string",
                            "description": "The ID of the finding to generate fix for"
                        }
                    },
                    "required": ["finding_id"]
                }
            ),
            Tool(
                name="preview_fix",
                description="Preview what changes a fix will make without applying. Shows before/after state.",
                function=self._preview_fix,
                input_schema={
                    "type": "object",
                    "properties": {
                        "finding_id": {
                            "type": "string",
                            "description": "The ID of the finding to preview fix for"
                        }
                    },
                    "required": ["finding_id"]
                }
            ),
            Tool(
                name="request_approval",
                description="Request user approval for a fix. Returns an approval_id that can be used with apply_direct_fix or create_fix_pr.",
                function=self._request_approval,
                input_schema={
                    "type": "object",
                    "properties": {
                        "finding_id": {
                            "type": "string",
                            "description": "The ID of the finding to request approval for"
                        },
                        "requested_by": {
                            "type": "string",
                            "description": "User ID or name requesting the fix"
                        }
                    },
                    "required": ["finding_id", "requested_by"]
                }
            ),
            Tool(
                name="apply_direct_fix",
                description="Apply a LOW risk fix directly via AWS API. Requires prior approval. Only works for LOW risk fixes.",
                function=self._apply_direct_fix,
                input_schema={
                    "type": "object",
                    "properties": {
                        "approval_id": {
                            "type": "string",
                            "description": "The approval ID from request_approval"
                        }
                    },
                    "required": ["approval_id"]
                }
            ),
            Tool(
                name="create_fix_pr",
                description="Create a GitHub PR with Terraform code to fix a finding. Used for MEDIUM/HIGH risk fixes.",
                function=self._create_fix_pr,
                input_schema={
                    "type": "object",
                    "properties": {
                        "approval_id": {
                            "type": "string",
                            "description": "The approval ID from request_approval"
                        }
                    },
                    "required": ["approval_id"]
                }
            ),
        ]

    # =========================================================================
    # DynamoDB Approval Storage
    # =========================================================================

    def _store_approval(self, request: RemediationRequest) -> bool:
        """Store a pending approval in DynamoDB."""
        try:
            # Convert to dict and handle enums
            item = {
                "approval_id": request.approval_id,
                "timestamp": request.requested_at,
                "finding_id": request.finding_id,
                "account_id": request.account_id,
                "finding": json.dumps(request.finding),  # Store as JSON string
                "risk_level": request.risk_level.value,
                "method": request.method.value,
                "terraform_code": request.terraform_code,
                "aws_cli_commands": request.aws_cli_commands,
                "requested_by": request.requested_by,
                "requested_at": request.requested_at,
                "status": request.status,
                # TTL: expire after 24 hours
                "ttl": int((datetime.utcnow() + timedelta(hours=24)).timestamp()),
            }

            self.approvals_table.put_item(Item=item)
            logger.info(f"Stored approval {request.approval_id} in DynamoDB")
            return True
        except Exception as e:
            logger.exception(f"Error storing approval {request.approval_id}: {e}")
            return False

    def _get_approval(self, approval_id: str) -> Optional[RemediationRequest]:
        """Retrieve a pending approval from DynamoDB."""
        try:
            # Query by approval_id (hash key) - may have multiple timestamps
            response = self.approvals_table.query(
                KeyConditionExpression=Key("approval_id").eq(approval_id),
                ScanIndexForward=False,  # Most recent first
                Limit=1
            )

            items = response.get("Items", [])
            if not items:
                logger.warning(f"Approval {approval_id} not found in DynamoDB")
                return None

            item = items[0]

            # Reconstruct RemediationRequest from DynamoDB item
            request = RemediationRequest(
                finding_id=item["finding_id"],
                account_id=item["account_id"],
                finding=json.loads(item["finding"]),  # Parse JSON string
                risk_level=RiskLevel(item["risk_level"]),
                method=RemediationMethod(item["method"]),
                terraform_code=item["terraform_code"],
                aws_cli_commands=item.get("aws_cli_commands", []),
                requested_by=item["requested_by"],
                requested_at=item["requested_at"],
                status=item["status"],
                approval_id=approval_id,
            )

            logger.info(f"Retrieved approval {approval_id} from DynamoDB")
            return request
        except Exception as e:
            logger.exception(f"Error retrieving approval {approval_id}: {e}")
            return None

    def _update_approval_status(self, approval_id: str, status: str) -> bool:
        """Update the status of an approval in DynamoDB."""
        try:
            # First get the item to get the timestamp (range key)
            response = self.approvals_table.query(
                KeyConditionExpression=Key("approval_id").eq(approval_id),
                Limit=1
            )

            items = response.get("Items", [])
            if not items:
                return False

            timestamp = items[0]["timestamp"]

            self.approvals_table.update_item(
                Key={
                    "approval_id": approval_id,
                    "timestamp": timestamp,
                },
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": status},
            )
            logger.info(f"Updated approval {approval_id} status to {status}")
            return True
        except Exception as e:
            logger.exception(f"Error updating approval {approval_id} status: {e}")
            return False

    def _get_pending_approvals(self) -> list[RemediationRequest]:
        """Get all pending approvals from DynamoDB."""
        try:
            # Scan for PENDING_APPROVAL status (not ideal but approvals should be few)
            response = self.approvals_table.scan(
                FilterExpression="status = :status",
                ExpressionAttributeValues={":status": "PENDING_APPROVAL"}
            )

            requests = []
            for item in response.get("Items", []):
                try:
                    request = RemediationRequest(
                        finding_id=item["finding_id"],
                        account_id=item["account_id"],
                        finding=json.loads(item["finding"]),
                        risk_level=RiskLevel(item["risk_level"]),
                        method=RemediationMethod(item["method"]),
                        terraform_code=item["terraform_code"],
                        aws_cli_commands=item.get("aws_cli_commands", []),
                        requested_by=item["requested_by"],
                        requested_at=item["requested_at"],
                        status=item["status"],
                        approval_id=item["approval_id"],
                    )
                    requests.append(request)
                except Exception as e:
                    logger.warning(f"Error parsing approval item: {e}")
                    continue

            return requests
        except Exception as e:
            logger.exception(f"Error getting pending approvals: {e}")
            return []

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    def _get_pending_remediations(
        self,
        severity_filter: Optional[str] = None,
        limit: int = 10
    ) -> dict[str, Any]:
        """Get findings that can be remediated."""
        try:
            # Get findings from service
            findings = self.findings_service.get_recent_findings(
                severity=severity_filter,
                status="NEW",  # Only NEW findings
                limit=limit * 2  # Get extra in case some are already remediated
            )

            # Filter to findings that have remediation available AND aren't already fixed
            remediable = []
            already_fixed = []

            for finding in findings:
                guidance = self.remediation_service.generate_remediation(finding)
                if guidance:
                    # Check if resource already exists/is compliant
                    detection_result = self.resource_detector.detect_remediation_status(finding)

                    if detection_result["already_remediated"]:
                        # Resource already compliant - skip but log
                        already_fixed.append({
                            "finding_id": finding.get("id"),
                            "title": finding.get("title"),
                            "status": "ALREADY_COMPLIANT",
                            "message": detection_result["message"],
                        })
                        logger.info(f"Skipping already-remediated finding: {finding.get('id')} - {detection_result['message']}")
                        continue

                    risk_level = classify_finding_risk(finding)
                    method = get_remediation_method(risk_level)
                    remediable.append({
                        "finding_id": finding.get("id"),
                        "title": finding.get("title"),
                        "severity": finding.get("severity"),
                        "resource_type": finding.get("resource_type"),
                        "resource_id": finding.get("resource_id"),
                        "risk_level": risk_level.value,
                        "remediation_method": method.value,
                        "estimated_time": guidance.estimated_time,
                    })

                    if len(remediable) >= limit:
                        break

            # Sort by risk level (LOW first, then MEDIUM, then HIGH)
            risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
            remediable.sort(key=lambda x: risk_order.get(x["risk_level"], 1))

            result = {
                "success": True,
                "count": len(remediable),
                "findings": remediable,
                "message": f"Found {len(remediable)} findings needing remediation"
            }

            # Include already-fixed info if any were skipped
            if already_fixed:
                result["already_compliant"] = already_fixed
                result["message"] += f" ({len(already_fixed)} already compliant)"

            return result

        except Exception as e:
            logger.exception("Error getting pending remediations")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_finding_details(self, finding_id: str) -> dict[str, Any]:
        """Get full details of a finding."""
        try:
            finding = self.findings_service.get_finding(finding_id)
            if not finding:
                return {
                    "success": False,
                    "error": f"Finding {finding_id} not found"
                }

            # Check if already remediated
            detection_result = self.resource_detector.detect_remediation_status(finding)

            # Get remediation guidance
            guidance = self.remediation_service.generate_remediation(finding)
            risk_level = classify_finding_risk(finding)
            method = get_remediation_method(risk_level)

            return {
                "success": True,
                "finding": {
                    "id": finding.get("id"),
                    "title": finding.get("title"),
                    "severity": finding.get("severity"),
                    "description": finding.get("description"),
                    "resource_type": finding.get("resource_type"),
                    "resource_id": finding.get("resource_id"),
                    "account_id": finding.get("account_id"),
                    "status": finding.get("status"),
                },
                "current_state": {
                    "already_remediated": detection_result["already_remediated"],
                    "existing_resource": detection_result["existing_resource"],
                    "message": detection_result["message"],
                },
                "remediation": {
                    "available": guidance is not None and not detection_result["already_remediated"],
                    "risk_level": risk_level.value,
                    "method": method.value,
                    "terraform_code": guidance.terraform_code if guidance else None,
                    "aws_cli_commands": guidance.aws_cli_commands if guidance else None,
                    "estimated_time": guidance.estimated_time if guidance else None,
                    "references": guidance.references if guidance else None,
                }
            }

        except Exception as e:
            logger.exception(f"Error getting finding details: {finding_id}")
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_fix(self, finding_id: str) -> dict[str, Any]:
        """Generate fix code for a finding."""
        try:
            finding = self.findings_service.get_finding(finding_id)
            if not finding:
                return {
                    "success": False,
                    "error": f"Finding {finding_id} not found"
                }

            # Check if already remediated
            detection_result = self.resource_detector.detect_remediation_status(finding)
            if detection_result["already_remediated"]:
                return {
                    "success": False,
                    "already_remediated": True,
                    "finding_id": finding_id,
                    "message": detection_result["message"],
                    "existing_resource": detection_result["existing_resource"],
                    "error": f"No fix needed - {detection_result['message']}"
                }

            guidance = self.remediation_service.generate_remediation(finding)
            if not guidance:
                return {
                    "success": False,
                    "error": f"No remediation available for finding {finding_id}"
                }

            risk_level = classify_finding_risk(finding)
            method = get_remediation_method(risk_level)

            # Generate smart Terraform code that uses data sources for existing resources
            terraform_code = self._generate_smart_terraform(finding, guidance, detection_result)

            return {
                "success": True,
                "finding_id": finding_id,
                "risk_level": risk_level.value,
                "method": method.value,
                "terraform_code": terraform_code,
                "aws_cli_commands": guidance.aws_cli_commands,
                "manual_steps": guidance.manual_steps,
                "estimated_time": guidance.estimated_time,
                "references": guidance.references,
                "message": f"Generated {method.value} fix for {finding.get('title')}"
            }

        except Exception as e:
            logger.exception(f"Error generating fix for {finding_id}")
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_smart_terraform(
        self,
        finding: dict,
        guidance: RemediationGuidance,
        detection_result: dict
    ) -> str:
        """
        Generate Terraform code that's aware of existing resources.

        Uses AI to generate code, providing context about existing resources
        so the AI can use data sources instead of creating duplicates.
        """
        from services.bedrock_service import BedrockService

        title = finding.get("title", "")
        resource_id = finding.get("resource_id", "")
        resource_type = finding.get("resource_type", "")

        # Build context about existing resources for the AI
        existing_resources_context = self._build_existing_resources_context(finding)

        # Generate Terraform using AI with existing resource context
        prompt = f"""Generate Terraform code to remediate this security finding.

FINDING:
- Title: {title}
- Resource Type: {resource_type}
- Resource ID: {resource_id}

EXISTING RESOURCES IN AWS (use data sources for these, don't recreate):
{existing_resources_context}

REQUIREMENTS:
1. If a resource already exists (listed above), use a Terraform data source to reference it
2. Only create resources that don't already exist
3. Use proper Terraform resource naming conventions
4. Include appropriate tags (ManagedBy = "CARL", Remediation = "true")
5. Follow AWS security best practices
6. Include any required IAM roles/policies with least privilege

REFERENCE (base guidance, adapt as needed):
{guidance.terraform_code or "No base guidance available"}

Generate ONLY the Terraform HCL code, no explanations. The code should be production-ready and idempotent.
"""

        try:
            bedrock = BedrockService()
            terraform_code = bedrock.generate_text(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.2,  # Low temperature for consistent code generation
            )

            # Clean up response - extract just the HCL code
            terraform_code = self._extract_terraform_code(terraform_code)

            return terraform_code

        except Exception as e:
            logger.warning(f"AI generation failed, falling back to base guidance: {e}")
            # Fallback to original guidance if AI generation fails
            return guidance.terraform_code or ""

    def _build_existing_resources_context(self, finding: dict) -> str:
        """
        Build context string about existing resources for AI code generation.

        Scans for related resources that might be reused.
        """
        context_lines = []
        title_lower = finding.get("title", "").lower()
        resource_id = finding.get("resource_id", "")

        try:
            # For VPC Flow Logs, check for existing log groups
            if "flow log" in title_lower:
                vpc_id = resource_id
                if not vpc_id.startswith("vpc-"):
                    import re
                    match = re.search(r'(vpc-[a-z0-9]+)', resource_id)
                    if match:
                        vpc_id = match.group(1)

                # Check common log group naming patterns
                log_group_patterns = [
                    f"/aws/vpc/flowlogs/{vpc_id}",
                    f"/aws/vpc-flow-logs/{vpc_id}",
                    f"vpc-flowlogs-{vpc_id}",
                ]

                for pattern in log_group_patterns:
                    status = self.resource_detector.detect_cloudwatch_log_group(pattern)
                    if status.exists:
                        context_lines.append(
                            f"- CloudWatch Log Group EXISTS: {pattern} "
                            f"(ARN: {status.arn}, retention: {status.retention_days} days)"
                        )
                        break
                else:
                    context_lines.append("- No existing CloudWatch Log Group found for this VPC")

                context_lines.append(f"- VPC ID: {vpc_id}")

            # For S3 findings, check bucket status
            elif "s3" in finding.get("resource_type", "").lower():
                bucket_name = resource_id
                if bucket_name.startswith("arn:aws:s3:::"):
                    bucket_name = bucket_name.replace("arn:aws:s3:::", "")

                status = self.resource_detector.detect_s3_bucket_status(bucket_name)
                context_lines.append(f"- S3 Bucket: {bucket_name}")
                context_lines.append(f"  - Encryption: {'enabled (' + status.encryption_type + ')' if status.encryption_enabled else 'NOT enabled'}")
                context_lines.append(f"  - Versioning: {'enabled' if status.versioning_enabled else 'NOT enabled'}")
                context_lines.append(f"  - Public Access Block: {'enabled' if status.public_access_block_enabled else 'NOT enabled'}")

            # For IAM password policy
            elif "password policy" in title_lower:
                status = self.resource_detector.detect_iam_password_policy()
                if status.policy_exists:
                    context_lines.append(f"- IAM Password Policy EXISTS with:")
                    context_lines.append(f"  - Min length: {status.minimum_password_length}")
                    context_lines.append(f"  - Max age: {status.max_password_age} days")
                    context_lines.append(f"  - Compliant: {status.is_compliant}")
                else:
                    context_lines.append("- No IAM Password Policy configured")

            # Default case
            if not context_lines:
                context_lines.append("- No existing related resources detected")

        except Exception as e:
            logger.warning(f"Error building existing resources context: {e}")
            context_lines.append(f"- Could not scan for existing resources: {e}")

        return "\n".join(context_lines)

    def _extract_terraform_code(self, response: str) -> str:
        """
        Extract Terraform HCL code from AI response.

        Handles markdown code blocks and other formatting.
        """
        import re

        # Try to extract from markdown code block
        hcl_match = re.search(r'```(?:hcl|terraform)?\s*\n(.*?)\n```', response, re.DOTALL)
        if hcl_match:
            return hcl_match.group(1).strip()

        # If no code block, assume the whole response is code
        # but strip any leading/trailing explanation text
        lines = response.strip().split('\n')

        # Find first line that looks like Terraform
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('resource ', 'data ', 'variable ', 'locals ', '#', 'terraform ')):
                start_idx = i
                break

        # Find last line that looks like Terraform (ending brace or comment)
        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line.endswith('}') or line.startswith('#') or '=' in line:
                end_idx = i + 1
                break

        return '\n'.join(lines[start_idx:end_idx]).strip()

    def _preview_fix(self, finding_id: str) -> dict[str, Any]:
        """Preview what a fix will change."""
        try:
            finding = self.findings_service.get_finding(finding_id)
            if not finding:
                return {
                    "success": False,
                    "error": f"Finding {finding_id} not found"
                }

            guidance = self.remediation_service.generate_remediation(finding)
            if not guidance:
                return {
                    "success": False,
                    "error": f"No remediation available for finding {finding_id}"
                }

            risk_level = classify_finding_risk(finding)

            # Build preview of changes
            preview = {
                "finding": finding.get("title"),
                "resource": f"{finding.get('resource_type')}: {finding.get('resource_id')}",
                "risk_level": risk_level.value,
                "changes": [],
            }

            # Parse what will change based on finding type
            title_lower = finding.get("title", "").lower()

            if "encryption" in title_lower:
                preview["changes"].append({
                    "attribute": "Server-side encryption",
                    "before": "Disabled",
                    "after": "Enabled (AES-256)"
                })
            elif "versioning" in title_lower:
                preview["changes"].append({
                    "attribute": "Versioning",
                    "before": "Disabled",
                    "after": "Enabled"
                })
            elif "public access" in title_lower:
                preview["changes"].append({
                    "attribute": "Public access",
                    "before": "Allowed",
                    "after": "Blocked"
                })
            elif "flow log" in title_lower:
                preview["changes"].append({
                    "attribute": "VPC Flow Logs",
                    "before": "Not configured",
                    "after": "Enabled (CloudWatch)"
                })
            elif "security group" in title_lower:
                preview["changes"].append({
                    "attribute": "Ingress rule",
                    "before": "0.0.0.0/0 (open to internet)",
                    "after": "Restricted to specific CIDRs"
                })
            elif "password policy" in title_lower:
                preview["changes"].append({
                    "attribute": "Password policy",
                    "before": "Weak/Default",
                    "after": "Strong (14+ chars, symbols, rotation)"
                })
            else:
                preview["changes"].append({
                    "attribute": "Configuration",
                    "before": "Non-compliant",
                    "after": "Compliant"
                })

            return {
                "success": True,
                "preview": preview,
                "terraform_code": guidance.terraform_code,
                "message": f"Preview for {finding.get('title')}"
            }

        except Exception as e:
            logger.exception(f"Error previewing fix for {finding_id}")
            return {
                "success": False,
                "error": str(e)
            }

    def _request_approval(
        self,
        finding_id: str,
        requested_by: str
    ) -> dict[str, Any]:
        """Request approval for a fix."""
        try:
            finding = self.findings_service.get_finding(finding_id)
            if not finding:
                return {
                    "success": False,
                    "error": f"Finding {finding_id} not found"
                }

            guidance = self.remediation_service.generate_remediation(finding)
            if not guidance:
                return {
                    "success": False,
                    "error": f"No remediation available for finding {finding_id}"
                }

            risk_level = classify_finding_risk(finding)
            method = get_remediation_method(risk_level)

            # Generate approval ID
            approval_id = hashlib.md5(
                f"{finding_id}:{requested_by}:{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:12]

            # Create remediation request
            request = RemediationRequest(
                finding_id=finding_id,
                account_id=finding.get("account_id", "unknown"),
                finding=finding,
                risk_level=risk_level,
                method=method,
                terraform_code=guidance.terraform_code or "",
                aws_cli_commands=guidance.aws_cli_commands or [],
                requested_by=requested_by,
                requested_at=datetime.utcnow().isoformat(),
                status="PENDING_APPROVAL",
                approval_id=approval_id,
            )

            # Store pending approval in DynamoDB (persists across Lambda invocations)
            self._store_approval(request)

            return {
                "success": True,
                "approval_id": approval_id,
                "finding_id": finding_id,
                "risk_level": risk_level.value,
                "method": method.value,
                "terraform_code": guidance.terraform_code,
                "status": "PENDING_APPROVAL",
                "message": f"Approval requested for {finding.get('title')}. Use approval_id '{approval_id}' to apply or create PR."
            }

        except Exception as e:
            logger.exception(f"Error requesting approval for {finding_id}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_direct_fix(self, approval_id: str) -> dict[str, Any]:
        """Apply a LOW risk fix directly via AWS API."""
        try:
            # Get pending approval from DynamoDB
            request = self._get_approval(approval_id)
            if not request:
                return {
                    "success": False,
                    "error": f"Approval {approval_id} not found or expired"
                }

            # Verify risk level allows direct API
            if request.risk_level != RiskLevel.LOW:
                return {
                    "success": False,
                    "error": f"Direct API fix only allowed for LOW risk. This is {request.risk_level.value} risk. Use create_fix_pr instead."
                }

            # Apply the fix
            finding = request.finding
            title_lower = finding.get("title", "").lower()
            resource_id = finding.get("resource_id", "")

            # Execute the appropriate fix
            if "encryption" in title_lower and "s3" in finding.get("resource_type", "").lower():
                result = self._apply_s3_encryption(resource_id)
            elif "versioning" in title_lower and "s3" in finding.get("resource_type", "").lower():
                result = self._apply_s3_versioning(resource_id)
            elif "public access" in title_lower and "s3" in finding.get("resource_type", "").lower():
                result = self._apply_s3_public_access_block(resource_id)
            elif "password policy" in title_lower:
                result = self._apply_iam_password_policy()
            else:
                return {
                    "success": False,
                    "error": f"Direct API fix not implemented for this finding type. Use create_fix_pr instead.",
                    "terraform_code": request.terraform_code,
                }

            if result["success"]:
                # Update status in DynamoDB
                self._update_approval_status(approval_id, "APPLIED")

                # Update finding status
                self.findings_service.update_finding_status(
                    request.finding_id,
                    request.account_id,
                    "REMEDIATED"
                )

                return {
                    "success": True,
                    "finding_id": request.finding_id,
                    "method": "DIRECT_API",
                    "applied_at": datetime.utcnow().isoformat(),
                    "terraform_code": request.terraform_code,
                    "message": f"Successfully applied fix for {finding.get('title')}"
                }
            else:
                # Update status in DynamoDB
                self._update_approval_status(approval_id, "FAILED")
                return result

        except Exception as e:
            logger.exception(f"Error applying direct fix for {approval_id}")
            return {
                "success": False,
                "error": str(e)
            }

    def _create_fix_pr(self, approval_id: str) -> dict[str, Any]:
        """Create a GitHub PR with Terraform fix."""
        try:
            # Get pending approval from DynamoDB
            request = self._get_approval(approval_id)
            if not request:
                return {
                    "success": False,
                    "error": f"Approval {approval_id} not found or expired"
                }

            # Validate GitHub configuration
            if not self.github_token_or_provider or not self.infra_repo_owner:
                return {
                    "success": False,
                    "error": "GitHub not configured. Set GITHUB_APP_CREDENTIALS_SECRET and GITHUB_INFRA_OWNER environment variables.",
                    "terraform_code": request.terraform_code,
                    "message": "You can copy the Terraform code above and manually create a PR."
                }

            # Create GitHub service
            github = GitHubService(
                token_or_provider=self.github_token_or_provider,
                repo_owner=self.infra_repo_owner,
                repo_name=self.infra_repo,
            )

            finding = request.finding
            finding_id = request.finding_id

            # Create branch
            branch_name = f"carl-fix-{finding_id}"
            github.create_branch(branch_name, force=True)

            # Prepare file content
            # Clean up resource name for filename
            resource_id = finding.get("resource_id", "unknown").replace("/", "-").replace(":", "-")
            filename = f"remediations/{finding_id}-{resource_id}.tf"

            # Add header comment to Terraform code
            terraform_content = f"""# Remediation for: {finding.get('title')}
# Finding ID: {finding_id}
# Resource: {finding.get('resource_type')} - {finding.get('resource_id')}
# Risk Level: {request.risk_level.value}
# Generated by CARL at {datetime.utcnow().isoformat()}
# Requested by: {request.requested_by}

{request.terraform_code}
"""

            # Commit file
            commit_message = f"fix: Remediate {finding.get('title')}\n\nFinding ID: {finding_id}\nRisk Level: {request.risk_level.value}"
            github.commit_files(
                branch=branch_name,
                files={filename: terraform_content},
                message=commit_message,
            )

            # Create PR
            pr_body = f"""## Security Remediation

**Finding:** {finding.get('title')}
**Finding ID:** `{finding_id}`
**Severity:** {finding.get('severity')}
**Risk Level:** {request.risk_level.value}
**Resource:** {finding.get('resource_type')} - `{finding.get('resource_id')}`

### Description
{finding.get('description', 'No description available.')}

### Changes
This PR adds Terraform code to remediate the security finding.

### Terraform Code
```hcl
{request.terraform_code}
```

### Checklist
- [ ] Review the Terraform code
- [ ] Run `terraform plan` to verify changes
- [ ] Apply changes with `terraform apply`

---
*Generated by CARL Security Bot*
"""

            pr = github.create_pull_request(
                title=f"[CARL] Remediate: {finding.get('title')}",
                body=pr_body,
                head=branch_name,
                base="develop",
            )

            pr_url = pr.get("html_url")

            # Update status in DynamoDB
            self._update_approval_status(approval_id, "PR_CREATED")

            return {
                "success": True,
                "finding_id": finding_id,
                "method": "TERRAFORM_PR",
                "pr_url": pr_url,
                "pr_number": pr.get("number"),
                "branch": branch_name,
                "message": f"Created PR for {finding.get('title')}: {pr_url}"
            }

        except Exception as e:
            logger.exception(f"Error creating PR for {approval_id}")
            # Update status in DynamoDB on failure
            self._update_approval_status(approval_id, "FAILED")
            return {
                "success": False,
                "error": str(e),
                "terraform_code": request.terraform_code if request else None,
                "message": "Failed to create PR. You can copy the Terraform code and manually create a PR."
            }

    # =========================================================================
    # Direct Fix Implementations (LOW risk only)
    # =========================================================================

    def _apply_s3_encryption(self, bucket_name: str) -> dict[str, Any]:
        """Enable S3 bucket encryption."""
        try:
            # Extract bucket name from ARN if needed
            if bucket_name.startswith("arn:aws:s3:::"):
                bucket_name = bucket_name.replace("arn:aws:s3:::", "")

            s3 = boto3.client("s3", region_name=self.region)

            s3.put_bucket_encryption(
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
            return {
                "success": True,
                "action": "S3 encryption enabled",
                "bucket": bucket_name
            }

        except Exception as e:
            logger.exception(f"Error enabling S3 encryption: {bucket_name}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_s3_versioning(self, bucket_name: str) -> dict[str, Any]:
        """Enable S3 bucket versioning."""
        try:
            if bucket_name.startswith("arn:aws:s3:::"):
                bucket_name = bucket_name.replace("arn:aws:s3:::", "")

            s3 = boto3.client("s3", region_name=self.region)

            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={"Status": "Enabled"}
            )

            logger.info(f"Enabled versioning on S3 bucket: {bucket_name}")
            return {
                "success": True,
                "action": "S3 versioning enabled",
                "bucket": bucket_name
            }

        except Exception as e:
            logger.exception(f"Error enabling S3 versioning: {bucket_name}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_s3_public_access_block(self, bucket_name: str) -> dict[str, Any]:
        """Enable S3 public access block."""
        try:
            if bucket_name.startswith("arn:aws:s3:::"):
                bucket_name = bucket_name.replace("arn:aws:s3:::", "")

            s3 = boto3.client("s3", region_name=self.region)

            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True
                }
            )

            logger.info(f"Enabled public access block on S3 bucket: {bucket_name}")
            return {
                "success": True,
                "action": "S3 public access blocked",
                "bucket": bucket_name
            }

        except Exception as e:
            logger.exception(f"Error enabling S3 public access block: {bucket_name}")
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_iam_password_policy(self) -> dict[str, Any]:
        """Set strong IAM password policy."""
        try:
            iam = boto3.client("iam", region_name=self.region)

            iam.update_account_password_policy(
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
            return {
                "success": True,
                "action": "IAM password policy updated"
            }

        except Exception as e:
            logger.exception("Error updating IAM password policy")
            return {
                "success": False,
                "error": str(e)
            }

    # =========================================================================
    # Public API
    # =========================================================================

    def execute(self, user_message: str) -> str:
        """Execute the agent with a user request."""
        return self.agent.execute(user_message)

    def get_pending_approvals(self) -> list[dict]:
        """Get all pending approval requests from DynamoDB."""
        return [req.to_dict() for req in self._get_pending_approvals()]

    def approve_fix(self, approval_id: str) -> dict[str, Any]:
        """
        Approve and execute a fix.

        For LOW risk: Applies directly via AWS API
        For MEDIUM/HIGH risk: Creates GitHub PR
        """
        request = self._get_approval(approval_id)
        if not request:
            return {
                "success": False,
                "error": f"Approval {approval_id} not found"
            }

        if request.method == RemediationMethod.DIRECT_API:
            return self._apply_direct_fix(approval_id)
        else:
            return self._create_fix_pr(approval_id)

    def reject_fix(self, approval_id: str, reason: str = "Rejected by user") -> dict[str, Any]:
        """Reject a fix request."""
        request = self._get_approval(approval_id)
        if not request:
            return {
                "success": False,
                "error": f"Approval {approval_id} not found"
            }

        # Update status in DynamoDB
        self._update_approval_status(approval_id, "REJECTED")

        return {
            "success": True,
            "approval_id": approval_id,
            "status": "REJECTED",
            "reason": reason,
            "message": f"Fix request rejected: {reason}"
        }

    def approve_all(self, approval_ids: list[str]) -> list[dict[str, Any]]:
        """Approve and execute multiple fixes."""
        results = []
        for approval_id in approval_ids:
            result = self.approve_fix(approval_id)
            results.append(result)
        return results


# =============================================================================
# Convenience Functions
# =============================================================================

def create_remediation_agent(
    progress_callback: Optional[Callable[[str], None]] = None
) -> RemediationAgent:
    """Create a remediation agent with default configuration.

    Uses GitHub App authentication (preferred) or falls back to static token.
    """
    github_token_or_provider = None

    # Try GitHub App first (preferred)
    if GITHUB_APP_CREDENTIALS_SECRET:
        try:
            credentials_json = get_secret(GITHUB_APP_CREDENTIALS_SECRET)
            credentials = json.loads(credentials_json)
            github_app = GitHubAppAuth(
                app_id=credentials["app_id"],
                private_key=credentials["private_key"],
                installation_id=credentials["installation_id"]
            )
            # Pass token provider function (generates short-lived tokens)
            github_token_or_provider = github_app.get_installation_token
            logger.info("Remediation agent using GitHub App authentication")
        except Exception as e:
            logger.warning(f"GitHub App not configured for remediation: {e}")

    # Fall back to static token (legacy)
    if not github_token_or_provider and GITHUB_INFRA_TOKEN_SECRET:
        try:
            github_token_or_provider = get_secret(GITHUB_INFRA_TOKEN_SECRET)
            logger.info("Remediation agent using static token authentication (legacy)")
        except Exception as e:
            logger.warning(f"Failed to get GitHub token from Secrets Manager: {e}")

    return RemediationAgent(
        region=os.environ.get("AWS_REGION", "us-east-1"),
        github_token_or_provider=github_token_or_provider,
        infra_repo=GITHUB_INFRA_REPO,
        infra_repo_owner=GITHUB_INFRA_OWNER,
        progress_callback=progress_callback,
    )


def get_remediable_findings(
    severity_filter: Optional[str] = None,
    limit: int = 10
) -> list[dict]:
    """Get findings that can be remediated, ranked by risk."""
    agent = create_remediation_agent()
    result = agent._get_pending_remediations(
        severity_filter=severity_filter,
        limit=limit
    )
    return result.get("findings", [])
