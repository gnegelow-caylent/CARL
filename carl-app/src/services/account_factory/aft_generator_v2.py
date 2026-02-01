"""
AI-Driven AFT Generator for CARL.

Per CLAUDE.md Design Principle: "Dynamic Processing Over Static Rules"
This module uses AI (via AITerraformGenerator) to dynamically generate AFT
Terraform configurations instead of maintaining static templates.

The AI is grounded by:
1. AFT Framework structure (from aws-ia/terraform-aws-control_tower_account_factory)
2. Architecture patterns from knowledge/ directory
3. Compliance framework (SOC2, etc.) requirements
4. AWS best practices for multi-account

Key difference from aft_generator.py:
- OLD: 2000+ lines of static f-string templates
- NEW: AI generates code dynamically, grounded by patterns + AFT framework
"""

import json
from dataclasses import dataclass, field
from typing import Any

from services.ai_terraform_generator import (
    AITerraformGenerator,
    TerraformGenerationRequest,
    AFT_FRAMEWORK_CONTEXT,
    get_patterns_for_module,
)
from services.framework_loader import ComplianceFramework, ServiceControlPolicy
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AFTModuleConfig:
    """Configuration for the AFT module."""

    aft_management_account_email: str
    primary_region: str = "us-east-1"
    additional_regions: list[str] = field(default_factory=list)
    ct_home_region: str = "us-east-1"
    aft_feature_cloudtrail_data_events: bool = False
    aft_feature_enterprise_support: bool = False
    aft_feature_delete_default_vpcs_enabled: bool = True
    terraform_version: str = "1.6.0"
    terraform_distribution: str = "oss"


class AIAFTGenerator:
    """
    AI-Driven AFT Generator.

    Uses AITerraformGenerator to dynamically generate Terraform code
    while maintaining AFT framework structure and conventions.

    The AI is grounded by:
    - AFT Framework context (official AWS module structure)
    - Architecture patterns from knowledge/ (OU structure, account baselines)
    - Compliance framework requirements (SOC2, etc.)
    """

    def __init__(self):
        self.ai_generator = AITerraformGenerator()

    def generate_complete_aft(
        self,
        config: AFTModuleConfig,
        framework: ComplianceFramework,
        accounts: list,  # list[AccountConfig]
    ) -> dict[str, str]:
        """
        Generate complete AFT Terraform configuration using AI.

        Returns dict of filename -> content.
        Structure follows official AFT framework.
        """
        files = {}

        # Core AFT setup (AI-generated with AFT framework grounding)
        files["aft-main.tf"] = self._generate_aft_main(config, framework)
        files["providers.tf"] = self._generate_providers(config)
        files["variables.tf"] = self._generate_variables(config, framework)
        files["terraform.tfvars"] = self._generate_tfvars(config)
        files["backend.tf"] = self._generate_backend(config)

        # Account requests (AI-generated for each account)
        for account in accounts:
            filename = f"account-requests/{account.name}.tf"
            files[filename] = self._generate_account_request(account, framework)

        # Account customizations
        files["account-customizations/README.md"] = self._generate_customizations_readme()

        # Generate customization for each OU type
        customization_types = set()
        for account in accounts:
            customization_types.add(account.ou_name.lower())

        for cust_type in customization_types:
            files[f"account-customizations/{cust_type}/main.tf"] = (
                self._generate_account_customization(cust_type, framework, accounts)
            )
            files[f"account-customizations/{cust_type}/variables.tf"] = (
                self._generate_customization_variables()
            )

        # Global customizations (applied to ALL accounts)
        files["global-customizations/main.tf"] = self._generate_global_customization(framework)
        files["global-customizations/variables.tf"] = self._generate_customization_variables()

        # SCPs from framework (AI-generated)
        for scp in framework.scps:
            filename = f"scps/{scp.name}.tf"
            files[filename] = self._generate_scp_terraform(scp, framework)

        # Security baseline (AI-generated with security patterns)
        security_files = self._generate_security_baseline(framework, accounts)
        files.update(security_files)

        # Centralized logging (AI-generated with logging patterns)
        logging_files = self._generate_logging_baseline(framework)
        files.update(logging_files)

        # VPCs for workload accounts (AI-generated with VPC patterns)
        for account in accounts:
            if account.vpcs:
                for vpc in account.vpcs:
                    filename = f"vpcs/{account.name}-{vpc.name}.tf"
                    files[filename] = self._generate_vpc_terraform(account, vpc, framework)

        return files

    def _generate_aft_main(self, config: AFTModuleConfig, framework: ComplianceFramework) -> str:
        """Generate main AFT module configuration using AI."""
        requirements = {
            "module_source": "github.com/aws-ia/terraform-aws-control_tower_account_factory",
            "aft_feature_cloudtrail_data_events": config.aft_feature_cloudtrail_data_events,
            "aft_feature_enterprise_support": config.aft_feature_enterprise_support,
            "aft_feature_delete_default_vpcs_enabled": config.aft_feature_delete_default_vpcs_enabled,
            "terraform_version": config.terraform_version,
            "terraform_distribution": config.terraform_distribution,
            "ct_home_region": config.ct_home_region,
            "vcs_provider": "github",
            "maximum_concurrent_customizations": 5,
            "compliance_framework": framework.name,
        }

        patterns_context = f"""
{AFT_FRAMEWORK_CONTEXT}

This is the MAIN AFT module configuration that sets up Account Factory for Terraform.
Use the official AWS-IA module from GitHub.
Include outputs for aft_account_id and aft_codepipeline_name.
"""

        result = self.ai_generator.generate_terraform(
            TerraformGenerationRequest(
                module_type="aft_main",
                requirements=requirements,
                compliance_framework=framework.name,
                patterns_context=patterns_context,
            )
        )

        if result.success:
            return result.content
        else:
            # Fallback to minimal working template
            logger.warning(f"AI generation failed for aft-main.tf: {result.validation_errors}")
            return self._fallback_aft_main(config)

    def _generate_providers(self, config: AFTModuleConfig) -> str:
        """Generate providers configuration using AI."""
        requirements = {
            "terraform_version_constraint": ">= 1.5.0",
            "aws_provider_version": ">= 5.0",
            "primary_region": config.primary_region,
            "additional_regions": config.additional_regions,
            "default_tags": {
                "ManagedBy": "CARL-AccountFactory",
                "Environment": "management",
            },
        }

        result = self.ai_generator.generate_terraform(
            TerraformGenerationRequest(
                module_type="providers",
                requirements=requirements,
                compliance_framework="SOC2",
                patterns_context="Generate Terraform and AWS provider blocks with default tags.",
            )
        )

        if result.success:
            return result.content
        else:
            return self._fallback_providers(config)

    def _generate_variables(self, config: AFTModuleConfig, framework: ComplianceFramework) -> str:
        """Generate variables file using AI."""
        requirements = {
            "variables": [
                {"name": "ct_management_account_id", "type": "string", "description": "Control Tower Management Account ID"},
                {"name": "log_archive_account_id", "type": "string", "description": "Log Archive Account ID"},
                {"name": "audit_account_id", "type": "string", "description": "Audit Account ID"},
                {"name": "aft_management_account_id", "type": "string", "description": "AFT Management Account ID"},
                {"name": "primary_region", "type": "string", "default": config.primary_region, "description": "Primary AWS region"},
                {"name": "compliance_framework", "type": "string", "default": framework.name, "description": "Compliance framework"},
                {"name": "account_request_repo_name", "type": "string", "description": "GitHub repo for account requests"},
                {"name": "global_customizations_repo_name", "type": "string", "description": "GitHub repo for global customizations"},
                {"name": "account_customizations_repo_name", "type": "string", "description": "GitHub repo for account customizations"},
                {"name": "account_provisioning_customizations_repo_name", "type": "string", "description": "GitHub repo for provisioning customizations"},
            ],
        }

        result = self.ai_generator.generate_terraform(
            TerraformGenerationRequest(
                module_type="variables",
                requirements=requirements,
                compliance_framework=framework.name,
                patterns_context="Generate Terraform variable blocks for AFT configuration.",
            )
        )

        if result.success:
            return result.content
        else:
            return self._fallback_variables()

    def _generate_tfvars(self, config: AFTModuleConfig) -> str:
        """Generate terraform.tfvars file."""
        # This is always static since it's just placeholders
        return f'''# Terraform Variables for AFT
# Generated by CARL - Fill in with your actual values
#
# REQUIRED: Update these before running terraform apply

ct_management_account_id = "REPLACE_WITH_MANAGEMENT_ACCOUNT_ID"
log_archive_account_id   = "REPLACE_WITH_LOG_ARCHIVE_ACCOUNT_ID"
audit_account_id         = "REPLACE_WITH_AUDIT_ACCOUNT_ID"
aft_management_account_id = "REPLACE_WITH_AFT_MANAGEMENT_ACCOUNT_ID"

primary_region = "{config.primary_region}"

account_request_repo_name              = "aft-account-request"
global_customizations_repo_name        = "aft-global-customizations"
account_customizations_repo_name       = "aft-account-customizations"
account_provisioning_customizations_repo_name = "aft-account-provisioning-customizations"
'''

    def _generate_backend(self, config: AFTModuleConfig) -> str:
        """Generate backend configuration."""
        return f'''# Terraform Backend Configuration
# Generated by CARL
#
# Using S3 backend with DynamoDB locking for state management

terraform {{
  backend "s3" {{
    bucket         = "REPLACE_WITH_STATE_BUCKET"
    key            = "aft/terraform.tfstate"
    region         = "{config.primary_region}"
    encrypt        = true
    dynamodb_table = "REPLACE_WITH_LOCK_TABLE"
  }}
}}
'''

    def _generate_account_request(self, account, framework: ComplianceFramework) -> str:
        """Generate account request Terraform using AI."""
        requirements = {
            "account_name": account.name,
            "account_email": account.email or f"{account.name}@example.com",
            "managed_organizational_unit": account.ou_name,
            "sso_user_email": account.sso_user_email if hasattr(account, 'sso_user_email') else "",
            "purpose": account.purpose,
            "customizations_name": account.ou_name.lower(),
            "enable_security_services": True,
            "tags": {
                "Purpose": account.purpose,
                "OU": account.ou_name,
                "ManagedBy": "CARL-AFT",
            },
        }

        patterns_context = f"""
{AFT_FRAMEWORK_CONTEXT}

This is an AFT ACCOUNT REQUEST for the {account.name} account.
Use the control_tower_parameters block format.
Include account_tags and account_customizations_name.
"""

        result = self.ai_generator.generate_terraform(
            TerraformGenerationRequest(
                module_type="aft_account_request",
                requirements=requirements,
                compliance_framework=framework.name,
                patterns_context=patterns_context,
            )
        )

        if result.success:
            return result.content
        else:
            return self._fallback_account_request(account)

    def _generate_customizations_readme(self) -> str:
        """Generate README for account customizations."""
        return '''# AFT Account Customizations

Generated by CARL Account Factory.

## Structure

Each folder represents an account customization type:
- `security/` - Applied to Security OU accounts (audit, log-archive)
- `infrastructure/` - Applied to Infrastructure OU accounts (aft-management)
- `workloads/` - Applied to Workloads OU accounts (dev, staging, prod)

## How It Works

1. When AFT creates an account, it looks at the `account_customizations_name`
2. AFT runs the Terraform in the matching folder
3. Each customization has access to AFT variables (account_id, etc.)

## Files

- `main.tf` - Main customization resources
- `variables.tf` - Variable definitions (AFT provides values)

## Adding New Customizations

1. Create a new folder with your customization name
2. Add `main.tf` and `variables.tf`
3. Set `account_customizations_name` in the account request
'''

    def _generate_account_customization(
        self, cust_type: str, framework: ComplianceFramework, accounts: list
    ) -> str:
        """Generate account customization using AI."""
        # Determine what security services to enable based on OU type
        enable_guardduty = True
        enable_security_hub = True
        enable_config = True

        requirements = {
            "customization_type": cust_type,
            "enable_guardduty": enable_guardduty,
            "enable_security_hub": enable_security_hub,
            "enable_config": enable_config,
            "enable_inspector": cust_type == "workloads",
            "compliance_framework": framework.name,
        }

        # Get relevant patterns for this OU type
        patterns_context = get_patterns_for_module("security_services")
        patterns_context += f"""

This is an AFT ACCOUNT CUSTOMIZATION for the {cust_type.upper()} OU.
It runs after account creation to configure security services.
Use AFT variables: var.account_id, var.ct_management_account_id
"""

        result = self.ai_generator.generate_terraform(
            TerraformGenerationRequest(
                module_type="aft_account_customization",
                requirements=requirements,
                compliance_framework=framework.name,
                patterns_context=patterns_context,
            )
        )

        if result.success:
            return result.content
        else:
            return self._fallback_account_customization(cust_type)

    def _generate_customization_variables(self) -> str:
        """Generate variables for customizations."""
        return '''# AFT Customization Variables
# These are automatically provided by AFT

variable "account_id" {
  description = "The account ID being customized"
  type        = string
}

variable "ct_management_account_id" {
  description = "Control Tower management account ID"
  type        = string
}

variable "log_archive_account_id" {
  description = "Log Archive account ID"
  type        = string
}

variable "audit_account_id" {
  description = "Audit account ID"
  type        = string
}

variable "aft_management_account_id" {
  description = "AFT Management account ID"
  type        = string
}
'''

    def _generate_global_customization(self, framework: ComplianceFramework) -> str:
        """Generate global customization using AI."""
        requirements = {
            "iam_password_policy": {
                "minimum_length": 14,
                "require_uppercase": True,
                "require_lowercase": True,
                "require_numbers": True,
                "require_symbols": True,
                "max_age_days": 90,
                "reuse_prevention": 24,
            },
            "s3_block_public_access": True,
            "ebs_encryption_default": True,
            "imdsv2_required": True,
            "compliance_framework": framework.name,
        }

        patterns_context = f"""
This is an AFT GLOBAL CUSTOMIZATION applied to ALL accounts.
Include:
1. IAM password policy (SOC 2 CC6.1)
2. S3 block public access (SOC 2 CC6.7)
3. EBS encryption by default (SOC 2 CC6.7)
4. IMDSv2 requirement (SOC 2 CC6.1)

Keep it minimal but consistent across all accounts.
"""

        result = self.ai_generator.generate_terraform(
            TerraformGenerationRequest(
                module_type="aft_global_customization",
                requirements=requirements,
                compliance_framework=framework.name,
                patterns_context=patterns_context,
            )
        )

        if result.success:
            return result.content
        else:
            return self._fallback_global_customization()

    def _generate_scp_terraform(self, scp: ServiceControlPolicy, framework: ComplianceFramework) -> str:
        """Generate SCP Terraform using AI."""
        requirements = {
            "scp_name": scp.name,
            "description": scp.description,
            "policy_statements": scp.statement if hasattr(scp, 'statement') else [],
            "target_ous": scp.targets if hasattr(scp, 'targets') else [],
            "compliance_controls": scp.soc2_controls if hasattr(scp, 'soc2_controls') else [],
        }

        patterns_context = get_patterns_for_module("scp")
        patterns_context += f"""

Generate aws_organizations_policy and aws_organizations_policy_attachment resources.
SCP name: {scp.name}
Description: {scp.description}
"""

        result = self.ai_generator.generate_terraform(
            TerraformGenerationRequest(
                module_type="scp",
                requirements=requirements,
                compliance_framework=framework.name,
                patterns_context=patterns_context,
            )
        )

        if result.success:
            return result.content
        else:
            return self._fallback_scp(scp)

    def _generate_security_baseline(
        self, framework: ComplianceFramework, accounts: list
    ) -> dict[str, str]:
        """Generate security baseline files using AI."""
        files = {}

        # Security Hub delegation
        result = self.ai_generator.generate_security_services_module(
            enable_guardduty=True,
            enable_security_hub=True,
            enable_config=True,
            enable_inspector=True,
            compliance=framework.name,
        )
        files["security-baseline/security-services.tf"] = result.content

        # CloudWatch alarms for security monitoring
        result = self.ai_generator.generate_cloudwatch_alarms(
            cloudtrail_log_group="/aws/cloudtrail/organization",
            sns_topic_name="security-alerts",
            compliance=framework.name,
        )
        files["security-baseline/cloudwatch-alarms.tf"] = result.content

        # AWS Config rules
        result = self.ai_generator.generate_config_rules(
            enable_org_rules=True,
            compliance=framework.name,
        )
        files["security-baseline/config-rules.tf"] = result.content

        return files

    def _generate_logging_baseline(self, framework: ComplianceFramework) -> dict[str, str]:
        """Generate logging baseline files using AI."""
        files = {}

        # Organization CloudTrail
        result = self.ai_generator.generate_cloudtrail_module(
            multi_region=True,
            is_organization_trail=True,
            enable_log_validation=True,
            retention_days=2555,  # 7 years for SOC 2
            compliance=framework.name,
        )
        files["logging/cloudtrail-org.tf"] = result.content

        # Central logging bucket
        result = self.ai_generator.generate_central_logging_bucket(
            bucket_name_suffix="central-logs",
            retention_days=2555,
            enable_access_logging=True,
            compliance=framework.name,
        )
        files["logging/central-logging-bucket.tf"] = result.content

        return files

    def _generate_vpc_terraform(self, account, vpc, framework: ComplianceFramework) -> str:
        """Generate VPC Terraform using AI."""
        result = self.ai_generator.generate_vpc_module(
            vpc_name=f"{account.name}-{vpc.name}",
            cidr=vpc.cidr if hasattr(vpc, 'cidr') else "10.0.0.0/16",
            azs=vpc.availability_zones if hasattr(vpc, 'availability_zones') else 2,
            enable_nat=vpc.enable_nat if hasattr(vpc, 'enable_nat') else True,
            enable_flow_logs=True,  # Always enable for SOC 2
            environment=account.ou_name.lower(),
            compliance=framework.name,
        )

        if result.success:
            return result.content
        else:
            return f"# Error generating VPC: {result.validation_errors}"

    # =========================================================================
    # Fallback Templates (used when AI generation fails)
    # =========================================================================

    def _fallback_aft_main(self, config: AFTModuleConfig) -> str:
        """Fallback template for aft-main.tf."""
        return f'''# AWS Account Factory for Terraform (AFT)
# Generated by CARL - Fallback template

module "aft" {{
  source = "github.com/aws-ia/terraform-aws-control_tower_account_factory"

  aft_feature_cloudtrail_data_events      = {str(config.aft_feature_cloudtrail_data_events).lower()}
  aft_feature_enterprise_support          = {str(config.aft_feature_enterprise_support).lower()}
  aft_feature_delete_default_vpcs_enabled = {str(config.aft_feature_delete_default_vpcs_enabled).lower()}

  terraform_version      = "{config.terraform_version}"
  terraform_distribution = "{config.terraform_distribution}"
  ct_home_region         = "{config.ct_home_region}"

  ct_management_account_id  = var.ct_management_account_id
  log_archive_account_id    = var.log_archive_account_id
  audit_account_id          = var.audit_account_id
  aft_management_account_id = var.aft_management_account_id

  vcs_provider                                  = "github"
  account_request_repo_name                     = var.account_request_repo_name
  global_customizations_repo_name               = var.global_customizations_repo_name
  account_customizations_repo_name              = var.account_customizations_repo_name
  account_provisioning_customizations_repo_name = var.account_provisioning_customizations_repo_name

  maximum_concurrent_customizations = 5

  tags = {{
    ManagedBy  = "CARL-AccountFactory"
    Compliance = var.compliance_framework
  }}
}}

output "aft_account_id" {{
  value = var.aft_management_account_id
}}
'''

    def _fallback_providers(self, config: AFTModuleConfig) -> str:
        """Fallback template for providers.tf."""
        return f'''terraform {{
  required_version = ">= 1.5.0"

  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }}
  }}
}}

provider "aws" {{
  region = var.primary_region

  default_tags {{
    tags = {{
      ManagedBy   = "CARL-AccountFactory"
      Environment = "management"
    }}
  }}
}}

provider "aws" {{
  alias  = "us_east_1"
  region = "us-east-1"
}}
'''

    def _fallback_variables(self) -> str:
        """Fallback template for variables.tf."""
        return '''variable "ct_management_account_id" {
  description = "Control Tower Management Account ID"
  type        = string
}

variable "log_archive_account_id" {
  description = "Log Archive Account ID"
  type        = string
}

variable "audit_account_id" {
  description = "Audit Account ID"
  type        = string
}

variable "aft_management_account_id" {
  description = "AFT Management Account ID"
  type        = string
}

variable "primary_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-east-1"
}

variable "compliance_framework" {
  description = "Compliance framework"
  type        = string
  default     = "SOC2"
}

variable "account_request_repo_name" {
  description = "GitHub repo for account requests"
  type        = string
}

variable "global_customizations_repo_name" {
  description = "GitHub repo for global customizations"
  type        = string
}

variable "account_customizations_repo_name" {
  description = "GitHub repo for account customizations"
  type        = string
}

variable "account_provisioning_customizations_repo_name" {
  description = "GitHub repo for provisioning customizations"
  type        = string
}
'''

    def _fallback_account_request(self, account) -> str:
        """Fallback template for account request."""
        return f'''# Account Request: {account.name}
# Generated by CARL

module "{account.name.replace("-", "_")}_account_request" {{
  source = "../modules/aft-account-request"

  control_tower_parameters = {{
    AccountEmail              = "{account.email or f'{account.name}@example.com'}"
    AccountName               = "{account.name}"
    ManagedOrganizationalUnit = "{account.ou_name}"
    SSOUserEmail              = "admin@example.com"
    SSOUserFirstName          = "Admin"
    SSOUserLastName           = "User"
  }}

  account_tags = {{
    Purpose   = "{account.purpose}"
    OU        = "{account.ou_name}"
    ManagedBy = "CARL-AFT"
  }}

  account_customizations_name = "{account.ou_name.lower()}"
}}
'''

    def _fallback_account_customization(self, cust_type: str) -> str:
        """Fallback template for account customization."""
        return f'''# Account Customization: {cust_type}
# Generated by CARL

# Enable GuardDuty
resource "aws_guardduty_detector" "main" {{
  enable = true

  tags = {{
    ManagedBy = "CARL-AFT"
  }}
}}

# Enable Security Hub
resource "aws_securityhub_account" "main" {{
  enable_default_standards = true
}}
'''

    def _fallback_global_customization(self) -> str:
        """Fallback template for global customization."""
        return '''# Global Customization - Applied to ALL accounts
# Generated by CARL

# IAM Password Policy
resource "aws_iam_account_password_policy" "strict" {
  minimum_password_length        = 14
  require_uppercase_characters   = true
  require_lowercase_characters   = true
  require_numbers                = true
  require_symbols                = true
  allow_users_to_change_password = true
  max_password_age               = 90
  password_reuse_prevention      = 24
}

# S3 Block Public Access
resource "aws_s3_account_public_access_block" "main" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
'''

    def _fallback_scp(self, scp: ServiceControlPolicy) -> str:
        """Fallback template for SCP."""
        return f'''# SCP: {scp.name}
# {scp.description}
# Generated by CARL

resource "aws_organizations_policy" "{scp.name.replace("-", "_")}" {{
  name        = "{scp.name}"
  description = "{scp.description}"
  type        = "SERVICE_CONTROL_POLICY"

  content = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      # Policy statements here
    ]
  }})

  tags = {{
    ManagedBy  = "CARL-AFT"
    Compliance = "SOC2"
  }}
}}
'''
