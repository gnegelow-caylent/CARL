"""
Bootstrap Orchestrator for CARL.

Coordinates the complete AWS environment bootstrap including Organizations,
Identity Center, and security services setup.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .identity_center_bootstrap import (
    GroupConfiguration,
    IdentityCenterBootstrapService,
    PermissionSetConfiguration,
    AccountAssignment,
)
from .organizations_bootstrap import (
    OrganizationsBootstrapService,
    OUConfiguration,
    SCPConfiguration,
)
from .security_services_bootstrap import SecurityServicesBootstrapService

logger = logging.getLogger(__name__)


class BootstrapPhase(Enum):
    """Bootstrap phases."""
    ORGANIZATIONS = "organizations"
    IDENTITY_CENTER = "identity_center"
    SECURITY_SERVICES = "security_services"
    COMPLETE = "complete"


@dataclass
class BootstrapConfiguration:
    """Complete bootstrap configuration."""
    # Organizations config
    organization_feature_set: str = "ALL"
    ou_structure: Optional[list[OUConfiguration]] = None
    scps: Optional[list[SCPConfiguration]] = None

    # Identity Center config
    permission_sets: Optional[list[PermissionSetConfiguration]] = None
    groups: Optional[list[GroupConfiguration]] = None
    account_assignments: Optional[list[AccountAssignment]] = None

    # Security services config
    delegated_admin_account_id: Optional[str] = None
    security_regions: Optional[list[str]] = None
    enable_security_hub: bool = True
    enable_guardduty: bool = True
    enable_inspector: bool = True
    enable_macie: bool = False
    enable_detective: bool = False
    enable_config_aggregator: bool = True


@dataclass
class BootstrapResult:
    """Complete bootstrap result."""
    success: bool
    current_phase: BootstrapPhase
    organization_result: Optional[dict] = None
    identity_center_result: Optional[dict] = None
    security_services_result: Optional[dict] = None
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class BootstrapOrchestrator:
    """Orchestrates complete AWS environment bootstrap."""

    def __init__(self):
        self.orgs_service = OrganizationsBootstrapService()
        self.identity_service = IdentityCenterBootstrapService()

    def bootstrap_complete_environment(
        self, config: BootstrapConfiguration
    ) -> BootstrapResult:
        """
        Bootstrap complete AWS environment from scratch.

        Phases:
        1. Organizations + OU structure + SCPs
        2. IAM Identity Center + Permission Sets + Groups
        3. Security Services (delegated admin + auto-enable)

        Args:
            config: Complete bootstrap configuration

        Returns:
            BootstrapResult with status of each phase
        """
        result = BootstrapResult(
            success=True, current_phase=BootstrapPhase.ORGANIZATIONS
        )

        # Phase 1: Organizations
        logger.info("=" * 60)
        logger.info("PHASE 1: Organizations Bootstrap")
        logger.info("=" * 60)

        try:
            orgs_result = self.orgs_service.bootstrap_organization(
                feature_set=config.organization_feature_set,
                ou_structure=config.ou_structure,
                scps=config.scps,
            )

            result.organization_result = {
                "organization_id": orgs_result.organization_id,
                "root_id": orgs_result.root_id,
                "ou_map": orgs_result.ou_map,
                "scp_map": orgs_result.scp_map,
                "errors": orgs_result.errors,
            }

            if not orgs_result.success:
                logger.error("Organizations bootstrap failed")
                result.success = False
                result.errors.extend(orgs_result.errors)
                return result

            logger.info("✓ Organizations bootstrap complete")
            logger.info(f"  Organization ID: {orgs_result.organization_id}")
            logger.info(f"  Created OUs: {len(orgs_result.ou_map)}")
            logger.info(f"  Created SCPs: {len(orgs_result.scp_map)}")

        except Exception as e:
            logger.error(f"Organizations bootstrap failed: {e}")
            result.success = False
            result.errors.append(str(e))
            return result

        # Phase 2: Identity Center
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 2: IAM Identity Center Bootstrap")
        logger.info("=" * 60)
        result.current_phase = BootstrapPhase.IDENTITY_CENTER

        try:
            identity_result = self.identity_service.bootstrap_identity_center(
                permission_sets=config.permission_sets,
                groups=config.groups,
                assignments=config.account_assignments,
            )

            result.identity_center_result = {
                "instance_arn": identity_result.instance_arn,
                "identity_store_id": identity_result.identity_store_id,
                "permission_set_map": identity_result.permission_set_map,
                "group_map": identity_result.group_map,
                "assignments": identity_result.assignment_results,
                "errors": identity_result.errors,
            }

            if not identity_result.success:
                logger.error("Identity Center bootstrap failed")
                result.success = False
                result.errors.extend(identity_result.errors)
                return result

            logger.info("✓ Identity Center bootstrap complete")
            logger.info(
                f"  Created Permission Sets: {len(identity_result.permission_set_map)}"
            )
            logger.info(f"  Created Groups: {len(identity_result.group_map)}")
            logger.info(
                f"  Created Assignments: {len(identity_result.assignment_results)}"
            )

        except Exception as e:
            logger.error(f"Identity Center bootstrap failed: {e}")
            result.success = False
            result.errors.append(str(e))
            return result

        # Phase 3: Security Services
        logger.info("")
        logger.info("=" * 60)
        logger.info("PHASE 3: Security Services Bootstrap")
        logger.info("=" * 60)
        result.current_phase = BootstrapPhase.SECURITY_SERVICES

        if config.delegated_admin_account_id:
            try:
                security_service = SecurityServicesBootstrapService(
                    delegated_admin_account_id=config.delegated_admin_account_id,
                    regions=config.security_regions,
                )

                security_result = security_service.bootstrap_all_services(
                    enable_security_hub=config.enable_security_hub,
                    enable_guardduty=config.enable_guardduty,
                    enable_inspector=config.enable_inspector,
                    enable_macie=config.enable_macie,
                    enable_detective=config.enable_detective,
                    enable_config_aggregator=config.enable_config_aggregator,
                )

                result.security_services_result = {
                    "security_hub_admin": security_result.security_hub_admin,
                    "guardduty_admin": security_result.guardduty_admin,
                    "inspector_admin": security_result.inspector_admin,
                    "macie_admin": security_result.macie_admin,
                    "detective_admin": security_result.detective_admin,
                    "config_aggregator": security_result.config_aggregator_created,
                    "errors": security_result.errors,
                }

                if not security_result.success:
                    logger.error("Security services bootstrap failed")
                    result.success = False
                    result.errors.extend(security_result.errors)
                    return result

                logger.info("✓ Security services bootstrap complete")
                if security_result.security_hub_admin:
                    logger.info(
                        f"  Security Hub Admin: {security_result.security_hub_admin}"
                    )
                if security_result.guardduty_admin:
                    logger.info(
                        f"  GuardDuty Admin: {security_result.guardduty_admin}"
                    )
                if security_result.inspector_admin:
                    logger.info(
                        f"  Inspector Admin: {security_result.inspector_admin}"
                    )

            except Exception as e:
                logger.error(f"Security services bootstrap failed: {e}")
                result.success = False
                result.errors.append(str(e))
                return result
        else:
            logger.warning("No delegated admin account specified, skipping security services")

        # Complete
        result.current_phase = BootstrapPhase.COMPLETE
        logger.info("")
        logger.info("=" * 60)
        logger.info("BOOTSTRAP COMPLETE")
        logger.info("=" * 60)

        return result

    def get_quickstart_config(
        self, delegated_admin_account_id: str, security_regions: Optional[list[str]] = None
    ) -> BootstrapConfiguration:
        """
        Get quickstart configuration with AWS recommended defaults.

        Args:
            delegated_admin_account_id: Account ID for security services admin
            security_regions: List of regions for security services

        Returns:
            BootstrapConfiguration with recommended defaults
        """
        return BootstrapConfiguration(
            # Organizations
            organization_feature_set="ALL",
            ou_structure=self.orgs_service.get_aws_recommended_ou_structure(),
            scps=self.orgs_service.get_recommended_scps(),
            # Identity Center
            permission_sets=self.identity_service.get_recommended_permission_sets(),
            groups=self.identity_service.get_recommended_groups(),
            account_assignments=[],  # User must specify
            # Security Services
            delegated_admin_account_id=delegated_admin_account_id,
            security_regions=security_regions,
            enable_security_hub=True,
            enable_guardduty=True,
            enable_inspector=True,
            enable_macie=False,  # Optional, has additional costs
            enable_detective=False,  # Optional, requires GuardDuty data
            enable_config_aggregator=True,
        )

    def get_minimal_config(
        self, delegated_admin_account_id: Optional[str] = None
    ) -> BootstrapConfiguration:
        """
        Get minimal configuration for getting started.

        Args:
            delegated_admin_account_id: Optional account ID for security services

        Returns:
            BootstrapConfiguration with minimal setup
        """
        return BootstrapConfiguration(
            # Organizations - minimal OU structure
            organization_feature_set="ALL",
            ou_structure=[
                OUConfiguration(
                    name="Workloads", description="Application workloads"
                ),
                OUConfiguration(
                    name="Sandbox", description="Sandbox accounts"
                ),
            ],
            scps=[
                # Just prevent leaving organization
                SCPConfiguration(
                    name="DenyLeavingOrganization",
                    description="Prevent accounts from leaving",
                    policy_document={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Deny",
                                "Action": "organizations:LeaveOrganization",
                                "Resource": "*",
                            }
                        ],
                    },
                    target_ous=["Workloads", "Sandbox"],
                )
            ],
            # Identity Center - basic permission sets
            permission_sets=[
                PermissionSetConfiguration(
                    name="AdministratorAccess",
                    description="Full access",
                    managed_policies=[
                        "arn:aws:iam::aws:policy/AdministratorAccess"
                    ],
                ),
                PermissionSetConfiguration(
                    name="ReadOnlyAccess",
                    description="Read-only access",
                    managed_policies=[
                        "arn:aws:iam::aws:policy/ReadOnlyAccess"
                    ],
                ),
            ],
            groups=[
                GroupConfiguration(
                    name="Administrators", description="Administrators"
                ),
            ],
            account_assignments=[],  # User must specify
            # Security Services - basic only
            delegated_admin_account_id=delegated_admin_account_id,
            security_regions=None,  # Current region only
            enable_security_hub=True,
            enable_guardduty=True,
            enable_inspector=False,
            enable_macie=False,
            enable_detective=False,
            enable_config_aggregator=True,
        )
