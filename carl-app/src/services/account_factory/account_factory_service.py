"""
Account Factory Service for CARL.

Orchestrates multi-account AWS environment setup using AFT (Account Factory for Terraform).
Driven by compliance frameworks - the framework defines the organizational structure,
accounts, SCPs, and security requirements.
"""

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import boto3

from services.framework_loader import (
    ComplianceFramework,
    FrameworkLoader,
    OrganizationalUnit,
    ServiceControlPolicy,
    get_framework_loader,
)
from services.architecture_tools import generate_terraform_code

logger = logging.getLogger(__name__)


# US AWS Regions
US_REGIONS = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
}


class AccountFactoryState(Enum):
    """States for Account Factory session."""
    STARTED = "started"
    FRAMEWORK_SELECTED = "framework_selected"
    COLLECTING_CONFIG = "collecting_config"
    CONFIGURING_ACCOUNTS = "configuring_accounts"
    CONFIGURING_VPCS = "configuring_vpcs"
    REVIEWING = "reviewing"
    GENERATING = "generating"
    COMPLETE = "complete"


@dataclass
class VPCConfig:
    """VPC configuration for an account."""
    name: str
    cidr: str
    environment: str  # production, staging, development
    availability_zones: int = 2
    enable_nat_gateway: bool = True
    enable_vpc_endpoints: bool = True
    attach_transit_gateway: bool = True  # SOC2 recommended for centralized egress/inspection


@dataclass
class AccountConfig:
    """Configuration for a single AWS account."""
    name: str
    email: str  # Must be unique across AWS
    ou_name: str
    purpose: str
    sso_user_email: Optional[str] = None
    vpcs: list[VPCConfig] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)

    # Compliance-driven settings (populated from framework)
    enable_guardduty: bool = True
    enable_security_hub: bool = True
    enable_config: bool = True
    enable_cloudtrail: bool = True  # Usually org-level, but can be account-level
    enable_inspector: bool = True


@dataclass
class AccountFactorySession:
    """Session state for Account Factory wizard."""
    session_id: str
    user_id: str
    channel_id: str
    state: AccountFactoryState = AccountFactoryState.STARTED

    # Framework (drives everything)
    framework: Optional[ComplianceFramework] = None

    # Configuration collected from user
    aft_account_email: str = ""  # Email for AFT management account
    primary_region: str = "us-east-1"
    additional_regions: list[str] = field(default_factory=list)

    # Accounts to create (derived from framework + customization)
    accounts: list[AccountConfig] = field(default_factory=list)

    # Current progress
    current_account_index: int = 0
    current_vpc_index: int = 0

    # Generated output
    generated_modules: list[dict] = field(default_factory=list)
    estimated_monthly_cost: float = 0.0

    @classmethod
    def create(cls, user_id: str, channel_id: str) -> "AccountFactorySession":
        """Create new session with unique ID."""
        return cls(
            session_id=str(uuid.uuid4())[:8],
            user_id=user_id,
            channel_id=channel_id,
        )


class AccountFactoryService:
    """
    Account Factory Service.

    Generates AFT (Account Factory for Terraform) configuration based on
    compliance frameworks. The framework defines:
    - Organizational structure (OUs)
    - Accounts per OU
    - SCPs (Service Control Policies)
    - Required security services per account

    This service:
    1. Loads the compliance framework
    2. Derives account structure from framework
    3. Collects minimal user input (emails, customization)
    4. Generates complete AFT Terraform
    5. Pushes to GitHub
    """

    def __init__(self):
        self.sessions: dict[str, AccountFactorySession] = {}
        self.framework_loader = get_framework_loader()
        # No longer using static AFTGenerator - using AI-driven generation via generate_terraform_code
        self.dynamodb = boto3.resource('dynamodb')

    def create_session(self, user_id: str, channel_id: str) -> AccountFactorySession:
        """Create a new Account Factory session."""
        session = AccountFactorySession.create(user_id, channel_id)
        self.sessions[session.session_id] = session
        self._save_session(session)
        logger.info(f"Created Account Factory session {session.session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[AccountFactorySession]:
        """Get session by ID (from cache or DynamoDB)."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        return self._load_session(session_id)

    def select_framework(
        self,
        session: AccountFactorySession,
        framework_id: str
    ) -> dict:
        """
        Select compliance framework for the session.

        This populates the organizational structure, accounts, and SCPs
        based on the framework definition.
        """
        try:
            framework = self.framework_loader.load(framework_id)
            session.framework = framework
            session.state = AccountFactoryState.FRAMEWORK_SELECTED

            # Derive accounts from framework's organizational structure
            session.accounts = self._derive_accounts_from_framework(framework)

            self._save_session(session)

            return {
                "success": True,
                "framework_name": framework.name,
                "org_structure": [
                    {
                        "ou_name": ou.ou_name,
                        "purpose": ou.purpose,
                        "accounts": [
                            {"name": acc["name"], "purpose": acc["purpose"]}
                            for acc in ou.accounts
                        ]
                    }
                    for ou in framework.organizational_structure
                ],
                "scps": [
                    {"name": scp.name, "description": scp.description}
                    for scp in framework.scps
                ],
                "total_accounts": len(session.accounts),
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Framework '{framework_id}' not found",
                "available": self.framework_loader.list_available_frameworks(),
            }
        except Exception as e:
            logger.error(f"Failed to load framework: {e}")
            return {"success": False, "error": str(e)}

    def _derive_accounts_from_framework(
        self,
        framework: ComplianceFramework
    ) -> list[AccountConfig]:
        """
        Derive account configurations from framework's organizational structure.

        The framework defines which accounts should exist in each OU.
        We create AccountConfig objects with compliance-driven defaults.
        """
        accounts = []

        # Add AFT management account first
        accounts.append(AccountConfig(
            name="aft-management",
            email="",  # User must provide
            ou_name="Infrastructure",
            purpose="AFT management and account vending",
            enable_guardduty=True,
            enable_security_hub=True,
            enable_config=True,
            enable_cloudtrail=False,  # Org-level trail
            enable_inspector=False,  # Not needed for management
        ))

        # Derive accounts from organizational structure
        for ou in framework.organizational_structure:
            for acc_def in ou.accounts:
                # Determine security settings based on OU
                is_security_ou = ou.ou_name.lower() == "security"
                is_workload = ou.ou_name.lower() == "workloads"

                account = AccountConfig(
                    name=acc_def["name"],
                    email="",  # User must provide
                    ou_name=ou.ou_name,
                    purpose=acc_def["purpose"],
                    # Security OU gets full security tooling
                    enable_guardduty=True,
                    enable_security_hub=is_security_ou,  # Delegated admin in security
                    enable_config=True,
                    enable_cloudtrail=is_security_ou,  # Org trail in security
                    enable_inspector=is_workload,  # Workloads need scanning
                    tags={
                        "OU": ou.ou_name,
                        "Compliance": framework.id.upper(),
                        "ManagedBy": "CARL-AccountFactory",
                    }
                )
                accounts.append(account)

        return accounts

    def set_account_email(
        self,
        session: AccountFactorySession,
        account_name: str,
        email: str
    ) -> dict:
        """Set email for an account."""
        for account in session.accounts:
            if account.name == account_name:
                account.email = email
                self._save_session(session)
                return {"success": True, "account": account_name, "email": email}

        return {"success": False, "error": f"Account '{account_name}' not found"}

    def set_aft_account_email(
        self,
        session: AccountFactorySession,
        email: str
    ) -> dict:
        """Set AFT management account email."""
        session.aft_account_email = email

        # Also set it on the AFT account config
        for account in session.accounts:
            if account.name == "aft-management":
                account.email = email
                break

        self._save_session(session)
        return {"success": True, "aft_email": email}

    def set_primary_region(
        self,
        session: AccountFactorySession,
        region: str
    ) -> dict:
        """
        Set primary region for the organization.

        Automatically enables all other US regions for multi-region resilience.
        """
        session.primary_region = region

        # Auto-enable all other US regions
        session.additional_regions = [
            r for r in US_REGIONS.keys()
            if r != region  # Exclude the primary region
        ]

        self._save_session(session)

        logger.info(f"Primary region set to {region}. Additional regions: {', '.join(session.additional_regions)}")

        return {
            "success": True,
            "primary_region": region,
            "additional_regions": session.additional_regions,
            "message": f"✅ Primary region: {region}\n✅ Additional regions enabled: {', '.join(session.additional_regions)}"
        }

    def set_account_emails(
        self,
        session: AccountFactorySession,
        emails: dict[str, str]
    ) -> dict:
        """Set emails for multiple accounts at once.

        Args:
            emails: Dict mapping account_name -> email
        """
        updated = []
        for account in session.accounts:
            if account.name in emails:
                account.email = emails[account.name]
                updated.append(account.name)

        self._save_session(session)
        return {"success": True, "updated_accounts": updated}

    def add_vpc_to_account(
        self,
        session: AccountFactorySession,
        account_name: str,
        vpc_config: VPCConfig
    ) -> dict:
        """Add a VPC configuration to an account."""
        for account in session.accounts:
            if account.name == account_name:
                account.vpcs.append(vpc_config)

                # If TGW attachment is enabled, ensure Network account exists
                network_account_added = False
                if vpc_config.attach_transit_gateway:
                    network_account_added = self._ensure_network_account(session)

                self._save_session(session)
                return {
                    "success": True,
                    "account": account_name,
                    "vpc": vpc_config.name,
                    "total_vpcs": len(account.vpcs),
                    "network_account_added": network_account_added,
                }

        return {"success": False, "error": f"Account '{account_name}' not found"}

    def _ensure_network_account(self, session: AccountFactorySession) -> bool:
        """
        Ensure a Network account exists for Transit Gateway.

        Network account hosts the Transit Gateway and provides centralized
        egress/inspection for SOC2 compliance.
        """
        # Check if network account already exists
        for account in session.accounts:
            if account.name == "network" or "network" in account.name.lower():
                return False  # Already exists

        # Add Network account to Shared Services OU
        network_account = AccountConfig(
            name="network",
            email="",  # User must provide
            ou_name="Shared Services",
            purpose="Transit Gateway, centralized egress, network inspection",
            enable_guardduty=True,
            enable_security_hub=True,
            enable_config=True,
            enable_cloudtrail=False,  # Org-level trail
            enable_inspector=False,
            tags={
                "OU": "Shared Services",
                "Purpose": "Network Hub",
                "ManagedBy": "CARL-AccountFactory",
            }
        )
        session.accounts.append(network_account)

        # Also move AFT to Shared Services if it's in Infrastructure
        for account in session.accounts:
            if account.name == "aft-management" and account.ou_name == "Infrastructure":
                account.ou_name = "Shared Services"

        return True

    def get_next_question(self, session: AccountFactorySession) -> Optional[dict]:
        """
        Get the next question to ask the user.

        Questions are driven by what's missing:
        1. Framework selection (if not selected)
        2. AFT account email
        3. Primary region
        4. Account emails (for each account)
        5. VPC configuration (for workload accounts)
        """
        if not session.framework:
            return {
                "type": "framework_select",
                "question": "Which compliance framework should drive your AWS organization?",
                "options": self._get_framework_options(),
            }

        if not session.aft_account_email:
            return {
                "type": "aft_email",
                "question": "What email should be used for the AFT management account?",
                "description": "This account manages Account Factory for Terraform. Use a unique email not already associated with an AWS account.",
                "input_type": "text",
            }

        if not session.primary_region:
            return {
                "type": "primary_region",
                "question": "Which AWS region should be the primary region?",
                "description": "CloudTrail, Config aggregator, and centralized logging will be in this region. All other US regions will be automatically enabled for multi-region resilience.",
                "options": [
                    {"value": region, "label": name}
                    for region, name in US_REGIONS.items()
                ],
            }

        # Check for accounts missing emails - return ALL at once for better UX
        accounts_needing_emails = [
            {
                "name": account.name,
                "purpose": account.purpose,
                "ou_name": account.ou_name,
            }
            for account in session.accounts
            if not account.email and account.name != "aft-management"
        ]
        if accounts_needing_emails:
            return {
                "type": "all_account_emails",
                "question": "Configure email addresses for your AWS accounts",
                "description": "Each AWS account needs a unique email address. These cannot be changed after account creation.",
                "accounts": accounts_needing_emails,
            }

        # Check for workload accounts that need VPCs
        for account in session.accounts:
            if account.ou_name.lower() == "workloads" and not account.vpcs:
                session.state = AccountFactoryState.CONFIGURING_VPCS
                return {
                    "type": "vpc_config",
                    "account_name": account.name,
                    "question": f"Configure VPC for '{account.name}' account",
                    "description": f"This is a workload account ({account.purpose}). Configure at least one VPC.",
                    "show_vpc_modal": True,
                }

        # All questions answered - ready to generate
        session.state = AccountFactoryState.REVIEWING
        self._save_session(session)
        return None

    def _get_framework_options(self) -> list[dict]:
        """Get available framework options with metadata."""
        options = []
        for framework_id in self.framework_loader.list_available_frameworks():
            metadata = self.framework_loader.get_framework_metadata(framework_id)
            if metadata:
                options.append({
                    "value": framework_id,
                    "label": metadata.get("name", framework_id),
                    "description": metadata.get("description", ""),
                })
        return options

    def generate_aft_terraform(self, session: AccountFactorySession, status_callback=None) -> dict:
        """
        Generate complete AFT Terraform configuration.

        Args:
            session: The account factory session
            status_callback: Optional callback function(message: str) for status updates

        Returns dict with:
        - terraform_files: dict[filename, content]
        - metadata: PR description, cost estimates, etc.
        """
        if not session.framework:
            return {"success": False, "error": "No framework selected"}

        session.state = AccountFactoryState.GENERATING
        self._save_session(session)

        try:
            # Generate AFT modules using AI-driven generation
            terraform_files = self._generate_aft_with_ai(session, status_callback)

            if status_callback:
                status_callback("⏳ Calculating cost estimates...")

            # Calculate cost estimate
            estimated_cost = self._estimate_monthly_cost(session)
            session.estimated_monthly_cost = estimated_cost

            session.state = AccountFactoryState.COMPLETE
            self._save_session(session)

            if status_callback:
                status_callback(f"✅ Generation complete! Estimated cost: ${estimated_cost:.2f}/month")

            return {
                "success": True,
                "terraform_files": terraform_files,
                "metadata": {
                    "framework": session.framework.name,
                    "total_accounts": len(session.accounts),
                    "total_vpcs": sum(len(acc.vpcs) for acc in session.accounts),
                    "estimated_monthly_cost": f"${estimated_cost:.2f}",
                    "primary_region": session.primary_region,
                    "scps": [scp.name for scp in session.framework.scps],
                },
            }
        except Exception as e:
            logger.exception(f"Failed to generate AFT Terraform: {e}")
            error_message = str(e)
            if "generate_terraform_code" in error_message:
                error_message = f"AI generation failed: {error_message}"
            return {"success": False, "error": error_message}

    def _generate_aft_with_ai(self, session: AccountFactorySession, status_callback=None) -> dict[str, str]:
        """
        Generate complete AFT Terraform configuration using AI-driven generation.

        Uses generate_terraform_code tool with architecture patterns as grounding.
        Per CLAUDE.md: No static Terraform templates - AI generates dynamically.
        """
        files = {}
        framework = session.framework

        # Calculate actual total steps dynamically
        vpc_count = sum(len(acc.vpcs) for acc in session.accounts)
        total_steps = (
            3 +  # AFT main, providers, variables
            1 +  # Account requests (parallel)
            1 +  # Account customizations (parallel)
            1 +  # Global customizations
            1 +  # SCPs (parallel)
            1 +  # Security services
            1 +  # CloudWatch alarms
            1 +  # Config rules
            1 +  # CloudTrail
            1 +  # Central logging bucket
            (1 if vpc_count > 0 else 0)  # VPCs (parallel, conditional)
        )  # = 13 steps total (or 12 if no VPCs)
        current_step = 0

        def update_status(message: str):
            """Helper to send status updates."""
            nonlocal current_step
            current_step += 1
            if status_callback:
                status_callback(f"⏳ Step {current_step}/{total_steps}: {message}")

        # Core AFT setup
        update_status("Generating AFT main configuration...")
        aft_main_result = generate_terraform_code(
            module_type="aft_main",
            requirements={
                "primary_region": session.primary_region,
                "terraform_version": "1.6.0",
                "delete_default_vpcs": True,
                "aft_management_account_email": session.aft_account_email,
            },
            compliance_framework=framework.name,
        )
        files["aft-main.tf"] = aft_main_result.get("content", "# Error generating aft-main.tf")

        # Providers (generic, can use AI)
        update_status("Generating provider configurations...")
        providers_result = generate_terraform_code(
            module_type="providers",
            requirements={
                "primary_region": session.primary_region,
                "additional_regions": session.additional_regions,
            },
            compliance_framework=framework.name,
        )
        files["providers.tf"] = providers_result.get("content", "# Error generating providers.tf")

        # Variables
        update_status("Generating variable definitions...")
        variables_result = generate_terraform_code(
            module_type="variables",
            requirements={
                "primary_region": session.primary_region,
                "compliance_framework": framework.name,
            },
            compliance_framework=framework.name,
        )
        files["variables.tf"] = variables_result.get("content", "# Error generating variables.tf")

        # Root-level backend configuration
        files["backend.tf"] = f"""# AFT Backend Configuration
# This should be configured with your actual backend details before running terraform init

terraform {{
  backend "s3" {{
    bucket         = "aft-backend-ORGANIZATION_ID"  # Replace with your organization ID
    key            = "aft-main/terraform.tfstate"
    region         = "{session.primary_region}"
    encrypt        = true
    kms_key_id     = "alias/aft-backend"
    dynamodb_table = "aft-backend-lock"
  }}
}}
"""

        # Root-level README
        files["README.md"] = f"""# AFT Multi-Account Terraform Configuration

Generated by CARL Account Factory for {framework.name} compliance.

## Structure

```
.
├── aft-main.tf                    # AFT core configuration
├── providers.tf                   # AWS provider configuration
├── variables.tf                   # Root-level variables
├── backend.tf                     # Terraform backend configuration
├── account-requests/              # Account vending machine requests
│   ├── account-name-1.tf
│   └── account-name-2.tf
├── account-customizations/        # Per-OU account customizations
│   ├── workloads/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── backend.tf
│   │   └── versions.tf
│   └── security/
│       ├── main.tf
│       └── ...
├── global-customizations/         # Organization-wide settings
│   ├── main.tf                    # IAM password policy, S3 block public access
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf
│   └── versions.tf
├── scps/                          # Service Control Policies (consolidated)
│   ├── main.tf                    # All SCPs in one file (AWS limit: 5 per OU)
│   ├── variables.tf
│   ├── outputs.tf
│   └── versions.tf
├── security-baseline/             # Security services
│   ├── security-services.tf       # GuardDuty, Security Hub, Config, Inspector
│   ├── cloudwatch-alarms.tf       # Security monitoring alarms
│   ├── config-rules.tf            # AWS Config compliance rules
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf
│   └── versions.tf
├── logging/                       # Centralized logging
│   ├── cloudtrail-org.tf          # Organization CloudTrail
│   ├── central-logging-bucket.tf  # S3 bucket for logs
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf
│   └── versions.tf
└── vpcs/                          # VPC configurations
    ├── account-vpc-name.tf
    └── ...
```

## Deployment Order

1. **Prerequisites**: Configure backend.tf with your actual S3 bucket and DynamoDB table
2. **Root Module**: Deploy aft-main.tf, providers, and global-customizations first
3. **SCPs**: Deploy Service Control Policies (max 5 per OU due to AWS limits)
4. **Account Requests**: Vend new accounts
5. **Logging**: Set up CloudTrail and central logging
6. **Security Baseline**: Enable security services
7. **Account Customizations**: Apply per-OU customizations
8. **VPCs**: Deploy VPC configurations

## Usage

```bash
# Initialize Terraform
terraform init

# Plan deployment
terraform plan

# Apply configuration
terraform apply

# Deploy specific module
cd security-baseline
terraform init
terraform apply
```

## Variables

See `variables.tf` in each module directory for required variables.

## Compliance Framework

- **Framework**: {framework.name}
- **Total Accounts**: {len(session.accounts)}
- **Total VPCs**: {sum(len(acc.vpcs) for acc in session.accounts)}
- **Primary Region**: {session.primary_region}
- **SCPs**: {len(framework.scps)} policies (consolidated into 1 file)

## Cost Estimate

**Estimated Monthly Cost**: ${self._estimate_monthly_cost(session):.2f}

See individual module documentation for detailed cost breakdowns.

## Support

Generated by CARL Account Factory
For questions or issues, contact your DevOps team.
"""

        # Account requests - one per account (PARALLEL)
        update_status(f"Generating {len(session.accounts)} account request modules in parallel...")

        def generate_account_request(account):
            """Generate account request Terraform (runs in parallel)."""
            result = generate_terraform_code(
                module_type="aft_account_request",
                requirements={
                    "account_name": account.name,
                    "account_email": account.email,
                    "ou_name": account.ou_name,
                    "purpose": account.purpose,
                    "sso_user_email": account.sso_user_email or "",
                    "tags": account.tags,
                },
                compliance_framework=framework.name,
            )
            logger.info(f"Generated account request for {account.name}")
            return f"account-requests/{account.name}.tf", result.get("content", f"# Error generating {account.name}")

        # Execute in parallel (max 5 concurrent to avoid rate limits)
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(generate_account_request, acc) for acc in session.accounts]
            for future in as_completed(futures):
                filename, content = future.result()
                files[filename] = content

        # Account customizations per OU type (PARALLEL)
        update_status("Generating account customizations per OU in parallel...")
        customization_types = set(acc.ou_name.lower() for acc in session.accounts)

        def generate_customization(cust_type):
            """Generate OU customization Terraform module (runs in parallel)."""
            result = generate_terraform_code(
                module_type="account_customization",
                requirements={
                    "customization_type": cust_type,
                    "enable_guardduty": True,
                    "enable_security_hub": True,
                    "enable_config": True,
                },
                compliance_framework=framework.name,
            )
            logger.info(f"Generated customization for OU: {cust_type}")

            # Proper Terraform module structure for each OU
            module_files = {
                f"account-customizations/{cust_type}/main.tf": result.get("content", "# Error"),
                f"account-customizations/{cust_type}/variables.tf": f"""# Variables for {cust_type} OU Customizations

variable "account_id" {{
  description = "AWS Account ID"
  type        = string
}}

variable "region" {{
  description = "AWS Region"
  type        = string
  default     = "{session.primary_region}"
}}
""",
                f"account-customizations/{cust_type}/outputs.tf": """# Outputs

output "customization_status" {
  description = "Account customization deployment status"
  value       = "complete"
}
""",
                f"account-customizations/{cust_type}/backend.tf": f"""# Backend configuration for {cust_type} OU customizations
terraform {{
  backend "s3" {{
    bucket         = "aft-backend-${{var.account_id}}"
    key            = "account-customizations/{cust_type}/terraform.tfstate"
    region         = "{session.primary_region}"
    encrypt        = true
    dynamodb_table = "aft-backend-lock"
  }}
}}
""",
                f"account-customizations/{cust_type}/versions.tf": """terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
""",
            }
            return module_files

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(generate_customization, ct) for ct in customization_types]
            for future in as_completed(futures):
                module_files = future.result()
                files.update(module_files)

        # Global customizations
        update_status("Generating global customizations...")
        global_result = generate_terraform_code(
            module_type="global_customization",
            requirements={
                "iam_password_policy": True,
                "s3_block_public_access": True,
                "ebs_encryption_default": True,
            },
            compliance_framework=framework.name,
        )

        # Proper Terraform module structure
        files["global-customizations/main.tf"] = global_result.get("content", "# Error")
        files["global-customizations/variables.tf"] = f"""# Global Customizations Variables

variable "organization_id" {{
  description = "AWS Organization ID"
  type        = string
}}

variable "primary_region" {{
  description = "Primary AWS Region"
  type        = string
  default     = "{session.primary_region}"
}}
"""
        files["global-customizations/outputs.tf"] = """# Global Customizations Outputs

output "iam_password_policy_applied" {
  description = "IAM password policy configuration status"
  value       = true
}

output "s3_public_access_blocked" {
  description = "S3 public access block status"
  value       = true
}
"""
        files["global-customizations/backend.tf"] = f"""# Backend configuration
terraform {{
  backend "s3" {{
    bucket         = "aft-backend-${{var.organization_id}}"
    key            = "global-customizations/terraform.tfstate"
    region         = "{session.primary_region}"
    encrypt        = true
    dynamodb_table = "aft-backend-lock"
  }}
}}
"""
        files["global-customizations/versions.tf"] = """terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
"""

        # SCPs from framework - CONSOLIDATED (AWS limit: 5 SCPs per OU)
        # Generate all SCPs in a single main.tf file to avoid hitting AWS limits
        update_status(f"Generating {len(framework.scps)} Service Control Policies (consolidated)...")

        scps_result = generate_terraform_code(
            module_type="scp_consolidated",
            requirements={
                "scps": [
                    {
                        "name": scp.name,
                        "description": scp.description,
                        "policy_statements": scp.statement if hasattr(scp, 'statement') else [],
                        "target_ous": scp.targets if hasattr(scp, 'targets') else [],
                    }
                    for scp in framework.scps
                ],
                "consolidate": True,  # Signal to generate all SCPs in one file
            },
            compliance_framework=framework.name,
        )

        # Proper Terraform module structure
        files["scps/main.tf"] = scps_result.get("content", "# Error generating SCPs")
        files["scps/variables.tf"] = """# SCP Module Variables

variable "organization_id" {
  description = "AWS Organization ID"
  type        = string
}

variable "target_ou_ids" {
  description = "Map of OU names to OU IDs for SCP attachment"
  type        = map(string)
  default     = {}
}
"""
        files["scps/outputs.tf"] = """# SCP Module Outputs

output "scp_ids" {
  description = "Map of SCP names to SCP IDs"
  value       = { for k, v in aws_organizations_policy.scp : k => v.id }
}

output "scp_arns" {
  description = "Map of SCP names to SCP ARNs"
  value       = { for k, v in aws_organizations_policy.scp : k => v.arn }
}
"""
        files["scps/versions.tf"] = """terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
"""
        logger.info(f"Generated consolidated SCPs module with {len(framework.scps)} policies")

        # Security baseline module - generate all security services together
        update_status("Generating security services baseline...")
        security_result = generate_terraform_code(
            module_type="security_services",
            requirements={
                "enable_guardduty": True,
                "enable_security_hub": True,
                "enable_config": True,
                "enable_inspector": True,
            },
            compliance_framework=framework.name,
        )
        files["security-baseline/security-services.tf"] = security_result.get("content", "# Error")

        # CloudWatch alarms
        update_status("Generating CloudWatch alarms...")
        alarms_result = generate_terraform_code(
            module_type="cloudwatch_alarms",
            requirements={
                "cloudtrail_log_group": "/aws/cloudtrail/organization",
                "sns_topic_name": "security-alerts",
            },
            compliance_framework=framework.name,
        )
        files["security-baseline/cloudwatch-alarms.tf"] = alarms_result.get("content", "# Error")

        # Config rules
        update_status("Generating AWS Config rules...")
        config_result = generate_terraform_code(
            module_type="config_rules",
            requirements={"enable_org_rules": True},
            compliance_framework=framework.name,
        )
        files["security-baseline/config-rules.tf"] = config_result.get("content", "# Error")

        # Security baseline module structure files
        files["security-baseline/variables.tf"] = f"""# Security Baseline Variables

variable "organization_id" {{
  description = "AWS Organization ID"
  type        = string
}}

variable "security_account_id" {{
  description = "Security tooling account ID"
  type        = string
}}

variable "primary_region" {{
  description = "Primary AWS Region"
  type        = string
  default     = "{session.primary_region}"
}}

variable "enabled_regions" {{
  description = "List of regions to enable security services"
  type        = list(string)
  default     = ["{session.primary_region}"]
}}
"""
        files["security-baseline/outputs.tf"] = """# Security Baseline Outputs

output "guardduty_detector_id" {
  description = "GuardDuty detector ID"
  value       = try(aws_guardduty_detector.main.id, null)
}

output "security_hub_arn" {
  description = "Security Hub ARN"
  value       = try(aws_securityhub_account.main.arn, null)
}

output "config_recorder_name" {
  description = "AWS Config recorder name"
  value       = try(aws_config_configuration_recorder.main.name, null)
}
"""
        files["security-baseline/backend.tf"] = f"""# Backend configuration
terraform {{
  backend "s3" {{
    bucket         = "aft-backend-${{var.organization_id}}"
    key            = "security-baseline/terraform.tfstate"
    region         = "{session.primary_region}"
    encrypt        = true
    dynamodb_table = "aft-backend-lock"
  }}
}}
"""
        files["security-baseline/versions.tf"] = """terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
"""

        # CloudTrail
        update_status("Generating CloudTrail organization trail...")
        cloudtrail_result = generate_terraform_code(
            module_type="cloudtrail",
            requirements={
                "multi_region": True,
                "is_organization_trail": True,
                "retention_days": 2555,
            },
            compliance_framework=framework.name,
        )
        files["logging/cloudtrail-org.tf"] = cloudtrail_result.get("content", "# Error")

        # Central logging bucket
        logging_result = generate_terraform_code(
            module_type="central_logging_bucket",
            requirements={
                "bucket_name_suffix": "central-logs",
                "retention_days": 2555,
            },
            compliance_framework=framework.name,
        )
        files["logging/central-logging-bucket.tf"] = logging_result.get("content", "# Error")

        # Logging module structure files
        files["logging/variables.tf"] = f"""# Logging Module Variables

variable "organization_id" {{
  description = "AWS Organization ID"
  type        = string
}}

variable "log_archive_account_id" {{
  description = "Log Archive account ID"
  type        = string
}}

variable "primary_region" {{
  description = "Primary AWS Region"
  type        = string
  default     = "{session.primary_region}"
}}

variable "cloudtrail_retention_days" {{
  description = "CloudTrail log retention in days"
  type        = number
  default     = 2555  # 7 years for compliance
}}
"""
        files["logging/outputs.tf"] = """# Logging Module Outputs

output "cloudtrail_arn" {
  description = "CloudTrail trail ARN"
  value       = try(aws_cloudtrail.organization.arn, null)
}

output "central_logging_bucket_name" {
  description = "Central logging S3 bucket name"
  value       = try(aws_s3_bucket.central_logs.id, null)
}

output "cloudtrail_log_group_arn" {
  description = "CloudWatch Logs group ARN for CloudTrail"
  value       = try(aws_cloudwatch_log_group.cloudtrail.arn, null)
}
"""
        files["logging/backend.tf"] = f"""# Backend configuration
terraform {{
  backend "s3" {{
    bucket         = "aft-backend-${{var.organization_id}}"
    key            = "logging/terraform.tfstate"
    region         = "{session.primary_region}"
    encrypt        = true
    dynamodb_table = "aft-backend-lock"
  }}
}}
"""
        files["logging/versions.tf"] = """terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
"""

        # VPCs for workload accounts (PARALLEL)
        vpc_count = sum(len(acc.vpcs) for acc in session.accounts)
        if vpc_count > 0:
            update_status(f"Generating {vpc_count} VPC configurations in parallel...")

            def generate_vpc(account, vpc):
                """Generate VPC Terraform (runs in parallel)."""
                result = generate_terraform_code(
                    module_type="vpc",
                    requirements={
                        "vpc_name": f"{account.name}-{vpc.name}",
                        "cidr": vpc.cidr,
                        "azs": vpc.availability_zones,
                        "enable_nat": vpc.enable_nat_gateway,
                        "enable_flow_logs": True,
                        "enable_endpoints": vpc.enable_vpc_endpoints,
                        "environment": vpc.environment,
                    },
                    compliance_framework=framework.name,
                )
                logger.info(f"Generated VPC: {account.name}-{vpc.name}")
                return f"vpcs/{account.name}-{vpc.name}.tf", result.get("content", "# Error")

            # Execute in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for account in session.accounts:
                    for vpc in account.vpcs:
                        futures.append(executor.submit(generate_vpc, account, vpc))

                for future in as_completed(futures):
                    filename, content = future.result()
                    files[filename] = content

        logger.info(f"Generated {len(files)} Terraform files for AFT configuration")
        return files

    def _estimate_monthly_cost(self, session: AccountFactorySession) -> float:
        """
        Estimate monthly cost for the multi-account setup.

        Costs include:
        - AFT infrastructure (~$50/month)
        - GuardDuty per account (~$1-2/account)
        - Security Hub per account (~$0 base, findings-based)
        - Config per account (~$2/account)
        - VPC costs (NAT Gateway, etc.)
        """
        cost = 50.0  # AFT base infrastructure

        for account in session.accounts:
            # Security services
            if account.enable_guardduty:
                cost += 1.5
            if account.enable_config:
                cost += 2.0
            if account.enable_inspector:
                cost += 0.5

            # VPC costs
            for vpc in account.vpcs:
                if vpc.enable_nat_gateway:
                    cost += 32.40 * vpc.availability_zones  # NAT per AZ
                if vpc.enable_vpc_endpoints:
                    cost += 7.50 * 3  # Assume 3 common endpoints

        return cost

    def get_summary(self, session: AccountFactorySession) -> dict:
        """Get summary of the current session state."""
        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "framework": session.framework.name if session.framework else None,
            "primary_region": session.primary_region,
            "accounts": [
                {
                    "name": acc.name,
                    "ou": acc.ou_name,
                    "email": acc.email or "(not set)",
                    "vpcs": len(acc.vpcs),
                    "purpose": acc.purpose,
                }
                for acc in session.accounts
            ],
            "estimated_cost": f"${session.estimated_monthly_cost:.2f}/month" if session.estimated_monthly_cost else None,
        }

    def _save_session(self, session: AccountFactorySession) -> None:
        """Save session to DynamoDB."""
        try:
            import os
            table_name = os.environ.get('FOUNDATION_TABLE', 'carl-dev-foundation')
            table = self.dynamodb.Table(table_name)

            # Serialize session
            session_data = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "channel_id": session.channel_id,
                "state": session.state.value,
                "aft_account_email": session.aft_account_email,
                "primary_region": session.primary_region,
                "additional_regions": session.additional_regions,
                "estimated_monthly_cost": str(session.estimated_monthly_cost),
                "accounts": [
                    {
                        "name": acc.name,
                        "email": acc.email,
                        "ou_name": acc.ou_name,
                        "purpose": acc.purpose,
                        "enable_guardduty": acc.enable_guardduty,
                        "enable_security_hub": acc.enable_security_hub,
                        "enable_config": acc.enable_config,
                        "enable_cloudtrail": acc.enable_cloudtrail,
                        "enable_inspector": acc.enable_inspector,
                        "vpcs": [
                            {
                                "name": vpc.name,
                                "cidr": vpc.cidr,
                                "environment": vpc.environment,
                                "availability_zones": vpc.availability_zones,
                                "enable_nat_gateway": vpc.enable_nat_gateway,
                                "enable_vpc_endpoints": vpc.enable_vpc_endpoints,
                            }
                            for vpc in acc.vpcs
                        ],
                        "tags": acc.tags,
                    }
                    for acc in session.accounts
                ],
            }

            if session.framework:
                session_data["framework_id"] = session.framework.id

            from datetime import datetime, timedelta
            table.put_item(
                Item={
                    'pk': f'ACCOUNT_FACTORY#{session.session_id}',
                    'sk': 'SESSION',
                    'data': json.dumps(session_data),
                    'ttl': int((datetime.now() + timedelta(hours=24)).timestamp()),
                }
            )
            logger.info(f"Saved Account Factory session {session.session_id}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")

    def _load_session(self, session_id: str) -> Optional[AccountFactorySession]:
        """Load session from DynamoDB."""
        try:
            import os
            table_name = os.environ.get('FOUNDATION_TABLE', 'carl-dev-foundation')
            table = self.dynamodb.Table(table_name)

            response = table.get_item(
                Key={
                    'pk': f'ACCOUNT_FACTORY#{session_id}',
                    'sk': 'SESSION'
                }
            )

            if 'Item' not in response:
                return None

            data = json.loads(response['Item']['data'])

            # Reconstruct session
            session = AccountFactorySession(
                session_id=data['session_id'],
                user_id=data['user_id'],
                channel_id=data['channel_id'],
                state=AccountFactoryState(data['state']),
                aft_account_email=data.get('aft_account_email', ''),
                primary_region=data.get('primary_region', ''),
                additional_regions=data.get('additional_regions', []),
                estimated_monthly_cost=float(data.get('estimated_monthly_cost', 0)),
            )

            # Reconstruct accounts
            session.accounts = []
            for acc_data in data.get('accounts', []):
                vpcs = [
                    VPCConfig(
                        name=vpc['name'],
                        cidr=vpc['cidr'],
                        environment=vpc['environment'],
                        availability_zones=vpc.get('availability_zones', 2),
                        enable_nat_gateway=vpc.get('enable_nat_gateway', True),
                        enable_vpc_endpoints=vpc.get('enable_vpc_endpoints', True),
                    )
                    for vpc in acc_data.get('vpcs', [])
                ]

                account = AccountConfig(
                    name=acc_data['name'],
                    email=acc_data.get('email', ''),
                    ou_name=acc_data['ou_name'],
                    purpose=acc_data['purpose'],
                    enable_guardduty=acc_data.get('enable_guardduty', True),
                    enable_security_hub=acc_data.get('enable_security_hub', True),
                    enable_config=acc_data.get('enable_config', True),
                    enable_cloudtrail=acc_data.get('enable_cloudtrail', False),
                    enable_inspector=acc_data.get('enable_inspector', True),
                    vpcs=vpcs,
                    tags=acc_data.get('tags', {}),
                )
                session.accounts.append(account)

            # Reload framework
            if 'framework_id' in data:
                try:
                    session.framework = self.framework_loader.load(data['framework_id'])
                except Exception as e:
                    logger.warning(f"Could not reload framework: {e}")

            self.sessions[session_id] = session
            logger.info(f"Loaded Account Factory session {session_id}")
            return session

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None


# Singleton instance
_account_factory_service: Optional[AccountFactoryService] = None


def get_account_factory_service() -> AccountFactoryService:
    """Get or create the global Account Factory service instance."""
    global _account_factory_service
    if _account_factory_service is None:
        _account_factory_service = AccountFactoryService()
    return _account_factory_service
