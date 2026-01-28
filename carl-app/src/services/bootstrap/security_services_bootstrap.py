"""
Security Services Delegated Admin Bootstrap Service for CARL.

Automates the setup of Security Hub, GuardDuty, Inspector, Config,
and other security services with delegated administration.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class SecurityServicesBootstrapResult:
    """Result of security services bootstrap."""
    success: bool
    security_hub_admin: Optional[str] = None
    guardduty_admin: Optional[str] = None
    inspector_admin: Optional[str] = None
    macie_admin: Optional[str] = None
    detective_admin: Optional[str] = None
    config_aggregator_created: bool = False
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SecurityServicesBootstrapService:
    """Service for bootstrapping AWS security services."""

    def __init__(self, delegated_admin_account_id: str, regions: Optional[list[str]] = None):
        """
        Initialize security services bootstrap.

        Args:
            delegated_admin_account_id: Account ID for delegated administrator
            regions: List of regions to enable services in (default: current region)
        """
        self.delegated_admin_account_id = delegated_admin_account_id
        self.regions = regions or [boto3.Session().region_name]
        self.orgs_client = boto3.client("organizations")

    def bootstrap_all_services(
        self,
        enable_security_hub: bool = True,
        enable_guardduty: bool = True,
        enable_inspector: bool = True,
        enable_macie: bool = False,
        enable_detective: bool = False,
        enable_config_aggregator: bool = True,
    ) -> SecurityServicesBootstrapResult:
        """
        Bootstrap all security services with delegated administration.

        Args:
            enable_security_hub: Enable Security Hub
            enable_guardduty: Enable GuardDuty
            enable_inspector: Enable Inspector
            enable_macie: Enable Macie
            enable_detective: Enable Detective
            enable_config_aggregator: Enable Config aggregator

        Returns:
            SecurityServicesBootstrapResult
        """
        result = SecurityServicesBootstrapResult(success=True)

        # Security Hub
        if enable_security_hub:
            try:
                self._setup_security_hub()
                result.security_hub_admin = self.delegated_admin_account_id
                logger.info("✓ Security Hub delegated admin configured")
            except Exception as e:
                error_msg = f"Security Hub setup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False

        # GuardDuty
        if enable_guardduty:
            try:
                self._setup_guardduty()
                result.guardduty_admin = self.delegated_admin_account_id
                logger.info("✓ GuardDuty delegated admin configured")
            except Exception as e:
                error_msg = f"GuardDuty setup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False

        # Inspector
        if enable_inspector:
            try:
                self._setup_inspector()
                result.inspector_admin = self.delegated_admin_account_id
                logger.info("✓ Inspector delegated admin configured")
            except Exception as e:
                error_msg = f"Inspector setup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False

        # Macie
        if enable_macie:
            try:
                self._setup_macie()
                result.macie_admin = self.delegated_admin_account_id
                logger.info("✓ Macie delegated admin configured")
            except Exception as e:
                error_msg = f"Macie setup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False

        # Detective
        if enable_detective:
            try:
                self._setup_detective()
                result.detective_admin = self.delegated_admin_account_id
                logger.info("✓ Detective delegated admin configured")
            except Exception as e:
                error_msg = f"Detective setup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False

        # Config Aggregator
        if enable_config_aggregator:
            try:
                self._setup_config_aggregator()
                result.config_aggregator_created = True
                logger.info("✓ Config aggregator created")
            except Exception as e:
                error_msg = f"Config aggregator setup failed: {e}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False

        return result

    def _setup_security_hub(self):
        """Setup Security Hub with delegated administrator."""
        for region in self.regions:
            logger.info(f"Setting up Security Hub in {region}...")

            # Enable Security Hub in delegated admin account
            securityhub_client = boto3.client("securityhub", region_name=region)

            try:
                # Enable Security Hub
                securityhub_client.enable_security_hub(
                    EnableDefaultStandards=True
                )
                logger.info(f"  Enabled Security Hub in {region}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceConflictException":
                    logger.info(f"  Security Hub already enabled in {region}")
                else:
                    raise

            # Register delegated administrator in management account
            try:
                securityhub_client.enable_organization_admin_account(
                    AdminAccountId=self.delegated_admin_account_id
                )
                logger.info(
                    f"  Registered delegated admin for Security Hub in {region}"
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceConflictException":
                    logger.info(
                        f"  Delegated admin already registered in {region}"
                    )
                else:
                    raise

            # Auto-enable for new accounts
            try:
                securityhub_client.update_organization_configuration(
                    AutoEnable=True,
                    AutoEnableStandards="DEFAULT",
                )
                logger.info(f"  Enabled auto-enable for new accounts in {region}")
            except ClientError as e:
                logger.warning(
                    f"  Failed to enable auto-enable in {region}: {e}"
                )

    def _setup_guardduty(self):
        """Setup GuardDuty with delegated administrator."""
        for region in self.regions:
            logger.info(f"Setting up GuardDuty in {region}...")

            guardduty_client = boto3.client("guardduty", region_name=region)

            # Enable GuardDuty
            try:
                response = guardduty_client.create_detector(
                    Enable=True,
                    FindingPublishingFrequency="FIFTEEN_MINUTES",
                    DataSources={
                        "S3Logs": {"Enable": True},
                        "Kubernetes": {"AuditLogs": {"Enable": True}},
                        "MalwareProtection": {
                            "ScanEc2InstanceWithFindings": {
                                "EbsVolumes": {"Enable": False}
                            }
                        },
                    },
                )
                detector_id = response["DetectorId"]
                logger.info(f"  Created GuardDuty detector: {detector_id}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "BadRequestException":
                    # Detector already exists, get it
                    response = guardduty_client.list_detectors()
                    if response["DetectorIds"]:
                        detector_id = response["DetectorIds"][0]
                        logger.info(
                            f"  Using existing detector: {detector_id}"
                        )
                    else:
                        raise
                else:
                    raise

            # Enable organization admin account
            try:
                guardduty_client.enable_organization_admin_account(
                    AdminAccountId=self.delegated_admin_account_id
                )
                logger.info(
                    f"  Registered delegated admin for GuardDuty in {region}"
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "BadRequestException":
                    logger.info(
                        f"  Delegated admin already registered in {region}"
                    )
                else:
                    raise

            # Auto-enable for organization
            try:
                guardduty_client.update_organization_configuration(
                    DetectorId=detector_id,
                    AutoEnable=True,
                    DataSources={
                        "S3Logs": {"AutoEnable": True},
                        "Kubernetes": {"AuditLogs": {"AutoEnable": True}},
                    },
                )
                logger.info(
                    f"  Enabled auto-enable for new accounts in {region}"
                )
            except ClientError as e:
                logger.warning(
                    f"  Failed to enable auto-enable in {region}: {e}"
                )

    def _setup_inspector(self):
        """Setup Inspector with delegated administrator."""
        for region in self.regions:
            logger.info(f"Setting up Inspector in {region}...")

            inspector_client = boto3.client("inspector2", region_name=region)

            # Enable Inspector
            try:
                inspector_client.enable(
                    ResourceTypes=["EC2", "ECR", "LAMBDA"]
                )
                logger.info(f"  Enabled Inspector in {region}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ValidationException":
                    logger.info(f"  Inspector already enabled in {region}")
                else:
                    raise

            # Enable delegated admin
            try:
                inspector_client.enable_delegated_admin_account(
                    DelegatedAdminAccountId=self.delegated_admin_account_id
                )
                logger.info(
                    f"  Registered delegated admin for Inspector in {region}"
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ValidationException":
                    logger.info(
                        f"  Delegated admin already registered in {region}"
                    )
                else:
                    raise

            # Enable auto-enable
            try:
                inspector_client.update_organization_configuration(
                    AutoEnable={
                        "Ec2": True,
                        "Ecr": True,
                        "Lambda": True,
                    }
                )
                logger.info(
                    f"  Enabled auto-enable for new accounts in {region}"
                )
            except ClientError as e:
                logger.warning(
                    f"  Failed to enable auto-enable in {region}: {e}"
                )

    def _setup_macie(self):
        """Setup Macie with delegated administrator."""
        for region in self.regions:
            logger.info(f"Setting up Macie in {region}...")

            macie_client = boto3.client("macie2", region_name=region)

            # Enable Macie
            try:
                macie_client.enable_macie()
                logger.info(f"  Enabled Macie in {region}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConflictException":
                    logger.info(f"  Macie already enabled in {region}")
                else:
                    raise

            # Enable delegated admin
            try:
                macie_client.enable_organization_admin_account(
                    AdminAccountId=self.delegated_admin_account_id
                )
                logger.info(
                    f"  Registered delegated admin for Macie in {region}"
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConflictException":
                    logger.info(
                        f"  Delegated admin already registered in {region}"
                    )
                else:
                    raise

    def _setup_detective(self):
        """Setup Detective with delegated administrator."""
        for region in self.regions:
            logger.info(f"Setting up Detective in {region}...")

            detective_client = boto3.client("detective", region_name=region)

            # Enable Detective
            try:
                response = detective_client.create_graph()
                graph_arn = response["GraphArn"]
                logger.info(f"  Created Detective graph: {graph_arn}")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConflictException":
                    # Graph already exists
                    response = detective_client.list_graphs()
                    if response["GraphList"]:
                        graph_arn = response["GraphList"][0]["Arn"]
                        logger.info(f"  Using existing graph: {graph_arn}")
                    else:
                        raise
                else:
                    raise

            # Enable delegated admin
            try:
                detective_client.enable_organization_admin_account(
                    AccountId=self.delegated_admin_account_id
                )
                logger.info(
                    f"  Registered delegated admin for Detective in {region}"
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConflictException":
                    logger.info(
                        f"  Delegated admin already registered in {region}"
                    )
                else:
                    raise

    def _setup_config_aggregator(self):
        """Setup Config aggregator in delegated admin account."""
        # This should run in the delegated admin account
        for region in self.regions:
            logger.info(f"Setting up Config aggregator in {region}...")

            config_client = boto3.client("config", region_name=region)

            aggregator_name = "organization-aggregator"

            try:
                # Create organization aggregator
                config_client.put_configuration_aggregator(
                    ConfigurationAggregatorName=aggregator_name,
                    OrganizationAggregationSource={
                        "RoleArn": f"arn:aws:iam::{self.delegated_admin_account_id}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig",
                        "AllAwsRegions": True,
                    },
                )
                logger.info(f"  Created Config aggregator: {aggregator_name}")

            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceInUseException":
                    logger.info(
                        f"  Config aggregator already exists in {region}"
                    )
                else:
                    raise

    def enable_service_in_member_accounts(
        self, service: str, account_ids: list[str]
    ):
        """
        Enable a security service in member accounts.

        Args:
            service: Service name (guardduty, securityhub, inspector, etc.)
            account_ids: List of account IDs to enable service in
        """
        for region in self.regions:
            logger.info(
                f"Enabling {service} in {len(account_ids)} accounts in {region}..."
            )

            if service == "guardduty":
                self._enable_guardduty_members(region, account_ids)
            elif service == "securityhub":
                self._enable_securityhub_members(region, account_ids)
            elif service == "inspector":
                self._enable_inspector_members(region, account_ids)
            elif service == "macie":
                self._enable_macie_members(region, account_ids)
            else:
                logger.warning(f"Unknown service: {service}")

    def _enable_guardduty_members(self, region: str, account_ids: list[str]):
        """Enable GuardDuty in member accounts."""
        guardduty_client = boto3.client("guardduty", region_name=region)

        # Get detector ID
        response = guardduty_client.list_detectors()
        if not response["DetectorIds"]:
            logger.error("No GuardDuty detector found")
            return

        detector_id = response["DetectorIds"][0]

        # Create members
        members = [{"AccountId": account_id} for account_id in account_ids]

        try:
            guardduty_client.create_members(
                DetectorId=detector_id, AccountDetails=members
            )
            logger.info(f"  Added {len(members)} GuardDuty members")
        except ClientError as e:
            logger.warning(f"  Failed to add members: {e}")

    def _enable_securityhub_members(self, region: str, account_ids: list[str]):
        """Enable Security Hub in member accounts."""
        securityhub_client = boto3.client("securityhub", region_name=region)

        # Create members
        members = [{"AccountId": account_id} for account_id in account_ids]

        try:
            securityhub_client.create_members(AccountDetails=members)
            logger.info(f"  Added {len(members)} Security Hub members")
        except ClientError as e:
            logger.warning(f"  Failed to add members: {e}")

    def _enable_inspector_members(self, region: str, account_ids: list[str]):
        """Enable Inspector in member accounts."""
        inspector_client = boto3.client("inspector2", region_name=region)

        try:
            inspector_client.associate_member(
                AccountId=self.delegated_admin_account_id
            )
            logger.info(f"  Associated Inspector members")
        except ClientError as e:
            logger.warning(f"  Failed to associate members: {e}")

    def _enable_macie_members(self, region: str, account_ids: list[str]):
        """Enable Macie in member accounts."""
        macie_client = boto3.client("macie2", region_name=region)

        # Create members
        members = {
            account_id: {"accountId": account_id} for account_id in account_ids
        }

        try:
            macie_client.create_member(account=members)
            logger.info(f"  Added {len(members)} Macie members")
        except ClientError as e:
            logger.warning(f"  Failed to add members: {e}")
