"""
AI-Driven Terraform Generator for CARL.

Per CLAUDE.md Design Principle: "Dynamic Processing Over Static Rules"
This module uses AI (BedrockService) to dynamically generate Terraform code
instead of maintaining thousands of lines of static templates.

The AI is given:
1. Context about what needs to be generated (requirements, compliance framework)
2. Architecture patterns from knowledge/ directory as GROUNDING CONTEXT
3. AWS best practices and pricing data
4. AFT (Account Factory for Terraform) framework guidelines when applicable

The architecture patterns keep AI code generation "honest" by providing:
- Specific AWS service configurations
- Cost ranges and drivers
- SOC 2 control mappings
- When to use / when not to use guidance
- Pros and cons

The AI generates Terraform code dynamically, validated before return.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import boto3

from services.bedrock_service import BedrockService
from utils.logger import get_logger

# Import architecture patterns for grounding context
try:
    from knowledge.architecture_patterns import (
        EGRESS_PATTERNS,
        INGRESS_PATTERNS,
        TRANSIT_PATTERNS,
    )
    from knowledge.account_patterns import (
        OU_STRUCTURE_PATTERNS,
        ACCOUNT_BASELINE_PATTERNS,
    )
    from knowledge.security_tooling_patterns import SECURITY_TOOLING_PATTERNS
    from knowledge.logging_patterns import LOGGING_PATTERNS
    from knowledge.vpc_patterns import VPC_PATTERNS
    from knowledge.kms_patterns import KMS_PATTERNS
    from knowledge.identity_patterns import IDENTITY_PATTERNS
    PATTERNS_AVAILABLE = True
except ImportError:
    PATTERNS_AVAILABLE = False

logger = get_logger(__name__)


# =============================================================================
# AFT FRAMEWORK CONTEXT
# =============================================================================

AFT_FRAMEWORK_CONTEXT = """
AWS Account Factory for Terraform (AFT) Framework:

AFT is the official AWS solution for vending AWS accounts with Terraform customizations.
It integrates with AWS Control Tower and provides:

1. ACCOUNT REQUESTS (aft-account-request):
   - Module source: github.com/aws-ia/terraform-aws-control_tower_account_factory
   - control_tower_parameters block: AccountEmail, AccountName, ManagedOrganizationalUnit, SSOUserEmail
   - account_tags for metadata
   - change_management_parameters for audit trail
   - custom_fields for customization triggers
   - account_customizations_name to select which customization to apply

2. ACCOUNT CUSTOMIZATIONS (aft-account-customizations):
   - One folder per customization type (e.g., security/, workloads/, infrastructure/)
   - Applied after account creation
   - Contains Terraform for account-specific configuration
   - Has access to account context via AFT variables

3. GLOBAL CUSTOMIZATIONS (aft-global-customizations):
   - Applied to ALL accounts created via AFT
   - Security baselines, password policies, encryption defaults
   - Should be minimal but consistent

4. SCPs (Service Control Policies):
   - Preventive guardrails at Organization level
   - Applied to OUs, inherited by accounts
   - Common: DenyRootUser, DenySecurityServiceDisable, RequireIMDSv2

AFT Terraform Structure:
```
aft-account-request/
  - modules/aft-account-request/main.tf  # AFT module call
aft-account-customizations/
  - security/main.tf      # Security OU customization
  - workloads/main.tf     # Workloads OU customization
  - infrastructure/main.tf # Infrastructure OU customization
aft-global-customizations/
  - main.tf               # Applied to all accounts
scps/
  - deny-root-user.tf     # SCP definitions
  - require-imdsv2.tf
```

Key AFT Variables (available in customizations):
- var.account_id - The new account ID
- var.ct_management_account_id - Control Tower management account
- var.log_archive_account_id - Log archive account
- var.audit_account_id - Audit account
"""


# =============================================================================
# PATTERN LOADER FOR GROUNDING CONTEXT
# =============================================================================

def _extract_pattern_context(pattern, max_options: int = 3) -> str:
    """
    Extract grounding context from an architecture pattern dataclass.

    This keeps AI code generation "honest" by providing:
    - Specific configuration guidance
    - Cost information
    - SOC 2 control mappings
    """
    if not pattern:
        return ""

    lines = []
    lines.append(f"PATTERN: {pattern.question}")
    lines.append("")

    for option in pattern.options[:max_options]:
        lines.append(f"Option: {option.name}")
        lines.append(f"  Description: {option.description}")
        lines.append(f"  When to use: {', '.join(option.when_to_use[:3])}")
        lines.append(f"  Pros: {', '.join(option.pros[:3])}")
        lines.append(f"  Cons: {', '.join(option.cons[:3])}")
        lines.append(f"  Cost: ${option.monthly_cost_range[0]:.0f}-${option.monthly_cost_range[1]:.0f}/month")
        lines.append(f"  SOC 2 Controls: {', '.join(option.soc2_controls)}")
        lines.append(f"  Complexity: {option.implementation_complexity}")
        lines.append("")

    if hasattr(pattern, 'recommendation_logic') and pattern.recommendation_logic:
        lines.append(f"Recommendation Logic: {pattern.recommendation_logic[:500]}")

    return "\n".join(lines)


def get_patterns_for_module(module_type: str) -> str:
    """
    Get relevant architecture patterns for a module type.

    This provides grounding context to keep AI generation accurate.
    """
    if not PATTERNS_AVAILABLE:
        return ""

    patterns_map = {
        "egress": [EGRESS_PATTERNS],
        "ingress": [INGRESS_PATTERNS],
        "transit": [TRANSIT_PATTERNS],
        "vpc": [VPC_PATTERNS],
        "security_services": [SECURITY_TOOLING_PATTERNS],
        "cloudtrail": [LOGGING_PATTERNS],
        "guardduty": [SECURITY_TOOLING_PATTERNS],
        "config": [SECURITY_TOOLING_PATTERNS],
        "security_hub": [SECURITY_TOOLING_PATTERNS],
        "kms": [KMS_PATTERNS],
        "iam": [IDENTITY_PATTERNS],
        "aft": [OU_STRUCTURE_PATTERNS, ACCOUNT_BASELINE_PATTERNS],
        "scp": [OU_STRUCTURE_PATTERNS],
        "account": [OU_STRUCTURE_PATTERNS, ACCOUNT_BASELINE_PATTERNS],
    }

    relevant_patterns = patterns_map.get(module_type, [])

    context_parts = []
    for pattern in relevant_patterns:
        try:
            context = _extract_pattern_context(pattern)
            if context:
                context_parts.append(context)
        except Exception as e:
            logger.warning(f"Error extracting pattern context: {e}")

    return "\n\n".join(context_parts)


# System prompt for Terraform generation
TERRAFORM_GENERATOR_SYSTEM_PROMPT = """You are an expert AWS infrastructure engineer and Terraform specialist.

Your job is to generate production-ready Terraform code based on requirements.

TERRAFORM CODE STANDARDS:
1. Use Terraform 1.5+ syntax
2. Use AWS provider 5.0+
3. Follow HashiCorp best practices
4. Include proper tagging with ManagedBy and Compliance tags
5. Use data sources for existing resources when appropriate
6. Include clear comments explaining purpose
7. Use variables for configurable values
8. Include outputs for important resource attributes
9. Follow security best practices (encryption, least privilege, etc.)

SOC 2 COMPLIANCE REQUIREMENTS:
When generating for SOC 2 compliance, include:
- Encryption at rest (KMS for S3, EBS, RDS)
- Encryption in transit (TLS 1.2+)
- Logging and monitoring (CloudTrail, VPC Flow Logs, CloudWatch)
- Access control (IAM roles, security groups, NACLs)
- Audit trail (7 year retention for logs)

OUTPUT FORMAT:
Return ONLY valid Terraform HCL code. No explanations, no markdown code fences.
Start directly with # comments and Terraform resources.
"""


@dataclass
class TerraformGenerationRequest:
    """Request for AI-driven Terraform generation."""

    module_type: str  # e.g., "vpc", "security_hub", "cloudtrail", "egress"
    requirements: dict[str, Any]  # Specific requirements
    compliance_framework: str = "SOC2"  # Framework driving generation
    existing_resources: list[str] | None = None  # Resources to reference
    patterns_context: str = ""  # Architecture patterns as examples
    estimated_cost_context: str = ""  # Cost information


@dataclass
class TerraformGenerationResult:
    """Result of AI-driven Terraform generation."""

    success: bool
    content: str  # The generated Terraform code
    module_type: str
    validation_errors: list[str] | None = None
    estimated_tokens: int = 0


class AITerraformGenerator:
    """
    AI-driven Terraform code generator.

    Uses BedrockService to dynamically generate Terraform code based on
    requirements and architecture patterns, instead of static templates.
    """

    def __init__(self):
        self.bedrock = BedrockService()
        self._load_patterns_cache()

    def _load_patterns_cache(self) -> None:
        """Load architecture patterns for context."""
        self._patterns_cache: dict[str, str] = {}
        # Patterns will be loaded dynamically as needed

    def generate_terraform(
        self,
        request: TerraformGenerationRequest,
        max_fix_attempts: int = 2,
    ) -> TerraformGenerationResult:
        """
        Generate Terraform code using AI with MCP validation and auto-fix.

        Args:
            request: TerraformGenerationRequest with all context
            max_fix_attempts: Maximum attempts to auto-fix validation errors (default: 2)

        Returns:
            TerraformGenerationResult with generated code
        """
        prompt = self._build_generation_prompt(request)

        try:
            # Use lower temperature for code generation (more deterministic)
            generated_code = self.bedrock.invoke_model(
                prompt=prompt,
                system_prompt=TERRAFORM_GENERATOR_SYSTEM_PROMPT,
                max_tokens=4096,
                temperature=0.2,  # Low temperature for code
            )

            # Clean up the response
            generated_code = self._clean_terraform_output(generated_code)

            # Validate using Terraform MCP (with fallback to basic validation)
            validation_result = self._validate_terraform_via_mcp(generated_code)

            # Auto-fix loop if validation fails
            fix_attempts = 0
            while not validation_result.get("valid", False) and fix_attempts < max_fix_attempts:
                fix_attempts += 1
                logger.info(
                    f"Terraform validation failed, attempting auto-fix "
                    f"({fix_attempts}/{max_fix_attempts})"
                )

                # Get errors for AI to fix
                errors = validation_result.get("errors", [])
                if not errors:
                    # No specific errors, can't auto-fix
                    break

                # Use AI to fix the code
                generated_code = self._fix_terraform_with_ai(
                    code=generated_code,
                    validation_errors=errors,
                    request=request,
                )

                # Re-validate the fixed code
                validation_result = self._validate_terraform_via_mcp(generated_code)

            # Prepare final validation errors (if any remain)
            final_errors = []
            if not validation_result.get("valid", False):
                for err in validation_result.get("errors", []):
                    final_errors.append(err.get("summary", str(err)))

            # Add validation note if auto-fix was attempted
            if fix_attempts > 0:
                if validation_result.get("valid", False):
                    logger.info(
                        f"Auto-fix successful after {fix_attempts} attempt(s)"
                    )
                else:
                    logger.warning(
                        f"Auto-fix failed after {fix_attempts} attempt(s), "
                        f"returning code with errors"
                    )

            return TerraformGenerationResult(
                success=validation_result.get("valid", False),
                content=generated_code,
                module_type=request.module_type,
                validation_errors=final_errors if final_errors else None,
                estimated_tokens=len(generated_code.split()),
            )

        except Exception as e:
            logger.exception(f"Error generating Terraform for {request.module_type}")
            return TerraformGenerationResult(
                success=False,
                content=f"# Error generating Terraform: {str(e)}\n",
                module_type=request.module_type,
                validation_errors=[str(e)],
            )

    def _build_generation_prompt(self, request: TerraformGenerationRequest) -> str:
        """Build the prompt for Terraform generation with grounding context."""
        sections = []

        # Module type and purpose
        sections.append(f"""Generate Terraform code for: {request.module_type}
Compliance Framework: {request.compliance_framework}
""")

        # Requirements
        if request.requirements:
            req_str = json.dumps(request.requirements, indent=2)
            sections.append(f"""REQUIREMENTS:
{req_str}
""")

        # Add grounding context from architecture patterns
        pattern_context = get_patterns_for_module(request.module_type)
        if pattern_context:
            sections.append(f"""ARCHITECTURE PATTERNS (GROUNDING CONTEXT - follow these guidelines):
{pattern_context}

IMPORTANT: Use the above patterns to guide your implementation. Follow the
recommended configurations, cost considerations, and SOC 2 control mappings.
""")

        # Add AFT context for account-related generation
        if request.module_type in ["aft", "aft_account_request", "aft_main", "account", "scp"]:
            sections.append(f"""AFT FRAMEWORK (REQUIRED - follow this structure):
{AFT_FRAMEWORK_CONTEXT}

IMPORTANT: Generate code that follows the AFT framework structure exactly.
Use the official AFT module from github.com/aws-ia/terraform-aws-control_tower_account_factory
""")

        # User-provided patterns context (additional to auto-loaded)
        if request.patterns_context:
            sections.append(f"""ADDITIONAL CONTEXT:
{request.patterns_context}
""")

        # Existing resources to reference
        if request.existing_resources:
            sections.append(f"""EXISTING RESOURCES (use data sources for these):
{chr(10).join('- ' + r for r in request.existing_resources)}
""")

        # Cost context
        if request.estimated_cost_context:
            sections.append(f"""COST CONSIDERATIONS:
{request.estimated_cost_context}
""")

        # Final instruction with emphasis on grounding
        sections.append("""
Generate complete, production-ready Terraform code.

CRITICAL REQUIREMENTS:
1. Follow the architecture patterns provided above
2. Use the exact AWS resource configurations from the patterns
3. Include proper terraform and provider blocks
4. Include all necessary resources with correct arguments
5. Use variables for configurable values with sensible defaults
6. Include outputs for important resource attributes
7. Add ManagedBy = "CARL" and Compliance tags
8. Follow the cost guidance from patterns
9. Map to the SOC 2 controls specified in patterns

Return ONLY valid Terraform HCL code. No markdown, no explanations.
Start with # comments describing the module, then terraform/provider blocks.""")

        return "\n".join(sections)

    def _clean_terraform_output(self, output: str) -> str:
        """Clean up AI-generated Terraform output."""
        # Remove markdown code fences if present
        output = re.sub(r'^```(?:hcl|terraform)?\s*\n?', '', output)
        output = re.sub(r'\n?```\s*$', '', output)

        # Remove any leading/trailing whitespace
        output = output.strip()

        # Ensure file starts with a comment
        if not output.startswith('#') and not output.startswith('terraform'):
            output = f"# Generated by CARL AI\n\n{output}"

        return output

    def _validate_terraform(self, code: str) -> list[str]:
        """Basic validation of generated Terraform code."""
        errors = []

        # Check for common issues
        if len(code) < 50:
            errors.append("Generated code is too short")

        # Check for balanced braces
        open_braces = code.count('{')
        close_braces = code.count('}')
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

        # Check for required blocks in certain module types
        if 'resource "aws_' not in code and 'data "aws_' not in code:
            if 'module "' not in code:
                errors.append("No AWS resources, data sources, or modules found")

        # Check for obvious syntax issues
        if '"""' in code or "'''" in code:
            errors.append("Python string literals found in Terraform code")

        return errors

    def _validate_terraform_via_mcp(self, code: str) -> dict:
        """
        Validate Terraform code using the Terraform MCP Lambda.

        Returns dict with:
        - valid: bool
        - message: str
        - errors: list[dict] (if invalid)
        """
        try:
            # Get Lambda function name from environment or use default
            function_name = os.environ.get(
                "TERRAFORM_MCP_FUNCTION",
                "carl-dev-mcp-terraform"
            )

            # Initialize Lambda client
            lambda_client = boto3.client("lambda")

            # Call the Terraform MCP's validate_terraform tool
            payload = {
                "tool": "validate_terraform",
                "args": {
                    "terraform_code": code,
                    "full_validation": False  # Quick syntax check only
                }
            }

            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload)
            )

            # Parse response
            response_payload = json.loads(response["Payload"].read().decode())

            if response_payload.get("error"):
                logger.error(f"MCP validation error: {response_payload['error']}")
                return {
                    "valid": False,
                    "message": "MCP validation failed",
                    "errors": [{"summary": response_payload["error"]}]
                }

            # Parse the result (which is a JSON string)
            result = json.loads(response_payload.get("result", "{}"))
            return result

        except Exception as e:
            logger.warning(f"MCP validation unavailable, falling back to basic: {e}")
            # Fallback to basic validation
            basic_errors = self._validate_terraform(code)
            return {
                "valid": len(basic_errors) == 0,
                "message": "Basic validation (MCP unavailable)",
                "errors": [{"summary": err} for err in basic_errors] if basic_errors else []
            }

    def _fix_terraform_with_ai(
        self,
        code: str,
        validation_errors: list[dict],
        request: TerraformGenerationRequest,
    ) -> str:
        """
        Use AI to fix Terraform code based on validation errors.

        Args:
            code: The invalid Terraform code
            validation_errors: List of error dicts with 'summary' key
            request: Original generation request for context

        Returns:
            Fixed Terraform code
        """
        error_descriptions = "\n".join(
            f"- {err.get('summary', str(err))}" for err in validation_errors
        )

        fix_prompt = f"""The following Terraform code has validation errors. Fix the errors and return the corrected code.

VALIDATION ERRORS:
{error_descriptions}

ORIGINAL CODE:
```hcl
{code}
```

REQUIREMENTS (for context):
- Module type: {request.module_type}
- Compliance framework: {request.compliance_framework}

INSTRUCTIONS:
1. Fix all the validation errors listed above
2. Keep the overall structure and purpose the same
3. Ensure proper HCL syntax (braces, quotes, commas)
4. Return ONLY the corrected Terraform code
5. No explanations, no markdown code fences, just the fixed HCL code

Return the fixed Terraform code:"""

        try:
            fixed_code = self.bedrock.invoke_model(
                prompt=fix_prompt,
                system_prompt="You are a Terraform expert. Fix the code and return ONLY valid HCL. No explanations.",
                max_tokens=4096,
                temperature=0.1,  # Very low temperature for precise fixes
            )

            return self._clean_terraform_output(fixed_code)

        except Exception as e:
            logger.error(f"Failed to fix Terraform with AI: {e}")
            return code  # Return original if fix fails

    # =========================================================================
    # Specialized Generation Methods
    # =========================================================================

    def generate_vpc_module(
        self,
        vpc_name: str,
        cidr: str,
        azs: int = 2,
        enable_nat: bool = True,
        enable_flow_logs: bool = True,
        enable_endpoints: bool = False,
        environment: str = "production",
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate VPC Terraform module."""
        requirements = {
            "vpc_name": vpc_name,
            "cidr_block": cidr,
            "availability_zones": azs,
            "enable_nat_gateway": enable_nat,
            "enable_vpc_flow_logs": enable_flow_logs,
            "enable_vpc_endpoints": enable_endpoints,
            "environment": environment,
            "private_subnets": True,
            "public_subnets": True,
            "enable_dns_hostnames": True,
            "enable_dns_support": True,
        }

        patterns_context = """
VPC Best Practices:
- Use /16 to /20 CIDR for VPCs
- Separate public and private subnets
- One NAT Gateway per AZ for HA (or single for cost savings)
- Enable VPC Flow Logs for security monitoring (SOC 2 CC7.2)
- Use VPC endpoints for AWS services to reduce NAT costs
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="vpc",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_security_services_module(
        self,
        enable_guardduty: bool = True,
        enable_security_hub: bool = True,
        enable_config: bool = True,
        enable_inspector: bool = True,
        enable_macie: bool = False,
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate security services Terraform module."""
        requirements = {
            "enable_guardduty": enable_guardduty,
            "enable_security_hub": enable_security_hub,
            "enable_config": enable_config,
            "enable_inspector": enable_inspector,
            "enable_macie": enable_macie,
            "guardduty_datasources": ["s3_logs", "kubernetes_audit_logs", "malware_protection"],
            "security_hub_standards": ["CIS AWS Foundations", "AWS Foundational Security Best Practices"],
            "config_all_supported": True,
            "inspector_resource_types": ["EC2", "ECR", "LAMBDA"],
        }

        patterns_context = """
Security Services Best Practices:
- Enable GuardDuty with all data sources (SOC 2 CC7.1 Threat Detection)
- Enable Security Hub with CIS and AWS FSBP standards (SOC 2 CC7.2)
- Enable AWS Config for configuration recording (SOC 2 CC7.2)
- Enable Inspector for vulnerability scanning (SOC 2 CC7.1)
- Macie is optional - only for S3 data classification needs
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="security_services",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_cloudtrail_module(
        self,
        multi_region: bool = True,
        is_organization_trail: bool = False,
        enable_log_validation: bool = True,
        retention_days: int = 2555,  # 7 years for SOC 2
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate CloudTrail Terraform module."""
        requirements = {
            "multi_region_trail": multi_region,
            "is_organization_trail": is_organization_trail,
            "enable_log_file_validation": enable_log_validation,
            "include_global_service_events": True,
            "retention_days": retention_days,
            "encrypt_with_kms": True,
            "enable_cloudwatch_logs": True,
            "event_selectors": {
                "read_write_type": "All",
                "include_management_events": True,
            },
        }

        patterns_context = """
CloudTrail Best Practices (SOC 2 CC7.2):
- Enable multi-region trail for complete coverage
- Enable log file validation for integrity (CC7.2)
- Encrypt logs with KMS (CC6.7)
- 7-year retention for SOC 2 audit requirements
- Send to CloudWatch Logs for real-time alerting
- Use S3 lifecycle rules for cost-effective storage (Glacier after 90 days)
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="cloudtrail",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_iam_password_policy(
        self,
        minimum_length: int = 14,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_numbers: bool = True,
        require_symbols: bool = True,
        max_age_days: int = 90,
        reuse_prevention: int = 24,
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate IAM password policy Terraform."""
        requirements = {
            "minimum_password_length": minimum_length,
            "require_uppercase_characters": require_uppercase,
            "require_lowercase_characters": require_lowercase,
            "require_numbers": require_numbers,
            "require_symbols": require_symbols,
            "max_password_age": max_age_days,
            "password_reuse_prevention": reuse_prevention,
            "allow_users_to_change_password": True,
        }

        patterns_context = """
IAM Password Policy (SOC 2 CC6.1):
- Minimum 14 characters (NIST recommendation)
- Require uppercase, lowercase, numbers, symbols
- 90-day password expiration
- Prevent reuse of last 24 passwords
- Allow users to change their own passwords
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="iam_password_policy",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_scp(
        self,
        scp_name: str,
        description: str,
        policy_statements: list[dict],
        target_ous: list[str],
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate Service Control Policy Terraform."""
        requirements = {
            "scp_name": scp_name,
            "description": description,
            "policy_statements": policy_statements,
            "target_ous": target_ous,
        }

        patterns_context = """
SCP Best Practices (SOC 2 CC6.1, CC6.6):
- Use Deny policies for preventive controls
- Never deny essential services (CloudTrail, Config)
- Apply to OUs, not individual accounts
- Test in sandbox OU before production
- Include proper conditions (e.g., ArnNotLike for break-glass)
- Common SCPs: DenyRootUser, DenySecurityServiceDisable, RequireIMDSv2
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="scp",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_config_rules(
        self,
        enable_org_rules: bool = True,
        rules: list[str] | None = None,
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate AWS Config rules Terraform."""
        default_rules = [
            "cloudtrail-enabled",
            "guardduty-enabled-centralized",
            "s3-bucket-public-read-prohibited",
            "s3-bucket-public-write-prohibited",
            "s3-bucket-ssl-requests-only",
            "s3-bucket-server-side-encryption-enabled",
            "encrypted-volumes",
            "rds-storage-encrypted",
            "vpc-flow-logs-enabled",
            "iam-password-policy",
            "iam-user-mfa-enabled",
            "root-account-mfa-enabled",
            "access-keys-rotated",
            "cmk-backing-key-rotation-enabled",
            "ec2-imdsv2-check",
        ]

        requirements = {
            "enable_organization_rules": enable_org_rules,
            "config_rules": rules or default_rules,
        }

        patterns_context = """
AWS Config Rules for SOC 2:
- CloudTrail enabled (CC7.2)
- GuardDuty enabled (CC7.1)
- S3 encryption and public access blocked (CC6.7)
- EBS and RDS encryption (CC6.7)
- VPC Flow Logs enabled (CC7.2)
- IAM password policy compliant (CC6.1)
- MFA enabled for users and root (CC6.1)
- Access keys rotated within 90 days (CC6.1)
- KMS key rotation enabled (CC6.7)
- IMDSv2 required on EC2 (CC6.1)
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="config_rules",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_cloudwatch_alarms(
        self,
        cloudtrail_log_group: str,
        sns_topic_name: str = "security-alerts",
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate CloudWatch alarms for security monitoring."""
        requirements = {
            "cloudtrail_log_group_name": cloudtrail_log_group,
            "sns_topic_name": sns_topic_name,
            "alarms": [
                {"name": "root-account-usage", "description": "Root account was used"},
                {"name": "unauthorized-api-calls", "description": "Unauthorized API calls detected"},
                {"name": "console-login-without-mfa", "description": "Console login without MFA"},
                {"name": "iam-policy-changes", "description": "IAM policy changes detected"},
                {"name": "cloudtrail-changes", "description": "CloudTrail configuration changed"},
                {"name": "security-group-changes", "description": "Security group changes"},
                {"name": "nacl-changes", "description": "Network ACL changes"},
                {"name": "kms-key-changes", "description": "KMS key disabled or deleted"},
            ],
        }

        patterns_context = """
CloudWatch Alarms for SOC 2 (CC7.1, CC7.2):
- Root account usage - immediate alert (CIS 3.3)
- Unauthorized API calls - detect attacks (CIS 3.1)
- Console login without MFA (CIS 3.2)
- IAM policy changes (CIS 3.4)
- CloudTrail configuration changes (CIS 3.5)
- Security group changes (CIS 3.10)
- Network ACL changes (CIS 3.11)
- KMS key disabling/deletion (CIS 3.7)

Use CloudWatch Log Metric Filters on CloudTrail logs.
Send alerts to SNS topic with email subscription.
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="cloudwatch_alarms",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_aft_account_request(
        self,
        account_name: str,
        account_email: str,
        ou_name: str,
        purpose: str,
        sso_user_email: str,
        compliance: str = "SOC2",
        tags: dict[str, str] | None = None,
    ) -> TerraformGenerationResult:
        """Generate AFT account request Terraform."""
        requirements = {
            "account_name": account_name,
            "account_email": account_email,
            "managed_organizational_unit": ou_name,
            "sso_user_email": sso_user_email,
            "purpose": purpose,
            "account_tags": tags or {},
            "enable_guardduty": True,
            "enable_security_hub": True,
            "enable_config": True,
        }

        patterns_context = f"""
AFT Account Request for {ou_name} OU:
- Use control_tower_parameters for account creation
- Set account_customizations_name based on OU
- Enable security services via custom_fields
- Add compliance and environment tags
- Purpose: {purpose}
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="aft_account_request",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_aft_main_module(
        self,
        primary_region: str,
        terraform_version: str = "1.6.0",
        delete_default_vpcs: bool = True,
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate main AFT module configuration."""
        requirements = {
            "aft_source": "github.com/aws-ia/terraform-aws-control_tower_account_factory",
            "primary_region": primary_region,
            "terraform_version": terraform_version,
            "delete_default_vpcs_enabled": delete_default_vpcs,
            "cloudtrail_data_events": False,
            "enterprise_support": False,
            "vcs_provider": "github",
            "maximum_concurrent_customizations": 5,
        }

        patterns_context = """
AFT Main Module Configuration:
- Use official AWS-IA AFT module from GitHub
- Enable deletion of default VPCs (security best practice)
- Configure VCS provider for GitOps workflow
- Set appropriate concurrent customization limits
- Include proper tagging for CARL management
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="aft_main",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_central_logging_bucket(
        self,
        bucket_name_suffix: str,
        retention_days: int = 2555,
        enable_access_logging: bool = True,
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate central logging S3 bucket."""
        requirements = {
            "bucket_name_suffix": bucket_name_suffix,
            "retention_days": retention_days,
            "versioning_enabled": True,
            "encryption": "aws:kms",
            "public_access_block": True,
            "lifecycle_rules": [
                {"transition_to_ia_days": 90},
                {"transition_to_glacier_days": 365},
                {"expiration_days": retention_days},
            ],
            "enable_access_logging": enable_access_logging,
            "allowed_services": ["cloudtrail.amazonaws.com", "config.amazonaws.com"],
        }

        patterns_context = """
Central Logging Bucket (SOC 2 CC7.2, A1.3):
- Enable versioning for data integrity
- KMS encryption for data at rest
- Block all public access
- Lifecycle rules: IA after 90 days, Glacier after 1 year
- 7-year retention for SOC 2 compliance
- Bucket policy allowing CloudTrail and Config
- Enable access logging to separate bucket
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="central_logging_bucket",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )

    def generate_egress_module(
        self,
        egress_type: str,  # "distributed_nat", "centralized_nat", "network_firewall"
        vpc_count: int = 1,
        availability_zones: int = 2,
        transit_gateway_id: str | None = None,
        compliance: str = "SOC2",
    ) -> TerraformGenerationResult:
        """Generate egress architecture Terraform."""
        requirements = {
            "egress_type": egress_type,
            "vpc_count": vpc_count,
            "availability_zones": availability_zones,
            "transit_gateway_id": transit_gateway_id,
        }

        if egress_type == "distributed_nat":
            patterns_context = """
Distributed NAT Gateway:
- NAT Gateway in each VPC's public subnet
- $32.40/month per NAT Gateway + $0.045/GB
- Simplest architecture, no TGW required
- Good for: Few VPCs, simple requirements
"""
        elif egress_type == "centralized_nat":
            patterns_context = """
Centralized NAT Gateway (via TGW):
- Shared egress VPC with NAT Gateways
- Transit Gateway connects spoke VPCs
- $36/month per TGW attachment + NAT costs
- Good for: Many VPCs, cost optimization
"""
        else:  # network_firewall
            patterns_context = """
AWS Network Firewall:
- Centralized inspection of all egress traffic
- $284.40/month per endpoint + $0.065/GB
- Supports domain filtering, IDS/IPS
- Good for: Compliance, threat detection
- SOC 2 CC7.1 (Network Monitoring)
"""

        return self.generate_terraform(
            TerraformGenerationRequest(
                module_type="egress",
                requirements=requirements,
                compliance_framework=compliance,
                patterns_context=patterns_context,
            )
        )
