"""
AWS Organizations Bootstrap Service for CARL.

Automates the setup of AWS Organizations, OU structure,
SCPs, and account baselines.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class OUConfiguration:
    """Organizational Unit configuration."""
    name: str
    parent_id: Optional[str] = None  # None = root
    description: str = ""
    scps: list[str] = None  # SCP names to attach

    def __post_init__(self):
        if self.scps is None:
            self.scps = []


@dataclass
class SCPConfiguration:
    """Service Control Policy configuration."""
    name: str
    description: str
    policy_document: dict[str, Any]
    target_ous: list[str] = None  # OU names to attach to

    def __post_init__(self):
        if self.target_ous is None:
            self.target_ous = []


@dataclass
class OrganizationBootstrapResult:
    """Result of organization bootstrap."""
    success: bool
    organization_id: str
    root_id: str
    ou_map: dict[str, str]  # OU name -> OU ID
    scp_map: dict[str, str]  # SCP name -> Policy ID
    errors: list[str]


class OrganizationsBootstrapService:
    """Service for bootstrapping AWS Organizations."""

    def __init__(self):
        self.orgs_client = boto3.client("organizations")

    def bootstrap_organization(
        self,
        feature_set: str = "ALL",
        ou_structure: Optional[list[OUConfiguration]] = None,
        scps: Optional[list[SCPConfiguration]] = None,
    ) -> OrganizationBootstrapResult:
        """
        Bootstrap AWS Organizations with OU structure and SCPs.

        Args:
            feature_set: "ALL" or "CONSOLIDATED_BILLING"
            ou_structure: List of OU configurations to create
            scps: List of SCP configurations to create and attach

        Returns:
            OrganizationBootstrapResult with created resources
        """
        errors = []
        ou_map = {}
        scp_map = {}

        try:
            # Check if organization already exists
            org_id, root_id = self._get_or_create_organization(feature_set)
            logger.info(f"Organization ID: {org_id}, Root ID: {root_id}")

        except Exception as e:
            logger.error(f"Failed to create organization: {e}")
            return OrganizationBootstrapResult(
                success=False,
                organization_id="",
                root_id="",
                ou_map={},
                scp_map={},
                errors=[str(e)],
            )

        # Create OU structure
        if ou_structure:
            ou_map, ou_errors = self._create_ou_structure(root_id, ou_structure)
            errors.extend(ou_errors)

        # Create and attach SCPs
        if scps:
            scp_map, scp_errors = self._create_and_attach_scps(
                root_id, scps, ou_map
            )
            errors.extend(scp_errors)

        return OrganizationBootstrapResult(
            success=len(errors) == 0,
            organization_id=org_id,
            root_id=root_id,
            ou_map=ou_map,
            scp_map=scp_map,
            errors=errors,
        )

    def _get_or_create_organization(
        self, feature_set: str
    ) -> tuple[str, str]:
        """Get existing or create new organization."""
        try:
            # Try to describe existing organization
            response = self.orgs_client.describe_organization()
            org = response["Organization"]
            org_id = org["Id"]

            # Get root ID
            roots = self.orgs_client.list_roots()
            root_id = roots["Roots"][0]["Id"]

            logger.info(f"Using existing organization: {org_id}")
            return org_id, root_id

        except self.orgs_client.exceptions.AWSOrganizationsNotInUseException:
            # Create new organization
            logger.info("Creating new organization...")
            response = self.orgs_client.create_organization(
                FeatureSet=feature_set
            )
            org = response["Organization"]
            org_id = org["Id"]

            # Get root ID
            roots = self.orgs_client.list_roots()
            root_id = roots["Roots"][0]["Id"]

            logger.info(f"Created organization: {org_id}")
            return org_id, root_id

    def _create_ou_structure(
        self, root_id: str, ou_configs: list[OUConfiguration]
    ) -> tuple[dict[str, str], list[str]]:
        """Create OU structure."""
        ou_map = {"Root": root_id}
        errors = []

        # Sort OUs by parent dependency (parents first)
        sorted_ous = self._sort_ous_by_dependency(ou_configs)

        for ou_config in sorted_ous:
            try:
                parent_id = ou_map.get(ou_config.parent_id, root_id)

                # Check if OU already exists
                existing_ou = self._find_ou_by_name(
                    parent_id, ou_config.name
                )

                if existing_ou:
                    ou_id = existing_ou["Id"]
                    logger.info(
                        f"OU '{ou_config.name}' already exists: {ou_id}"
                    )
                else:
                    # Create OU
                    response = self.orgs_client.create_organizational_unit(
                        ParentId=parent_id,
                        Name=ou_config.name,
                    )
                    ou_id = response["OrganizationalUnit"]["Id"]
                    logger.info(f"Created OU '{ou_config.name}': {ou_id}")

                ou_map[ou_config.name] = ou_id

            except ClientError as e:
                error_msg = f"Failed to create OU '{ou_config.name}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return ou_map, errors

    def _sort_ous_by_dependency(
        self, ous: list[OUConfiguration]
    ) -> list[OUConfiguration]:
        """Sort OUs so parents are created before children."""
        sorted_ous = []
        remaining = ous.copy()

        while remaining:
            made_progress = False

            for ou in remaining[:]:
                # If no parent or parent already created
                if (
                    ou.parent_id is None
                    or ou.parent_id == "Root"
                    or any(s.name == ou.parent_id for s in sorted_ous)
                ):
                    sorted_ous.append(ou)
                    remaining.remove(ou)
                    made_progress = True

            if not made_progress and remaining:
                # Circular dependency or missing parent
                logger.warning(
                    f"Cannot resolve OU dependencies: {[ou.name for ou in remaining]}"
                )
                sorted_ous.extend(remaining)
                break

        return sorted_ous

    def _find_ou_by_name(
        self, parent_id: str, name: str
    ) -> Optional[dict]:
        """Find OU by name under parent."""
        try:
            paginator = self.orgs_client.get_paginator(
                "list_organizational_units_for_parent"
            )

            for page in paginator.paginate(ParentId=parent_id):
                for ou in page["OrganizationalUnits"]:
                    if ou["Name"] == name:
                        return ou

        except ClientError as e:
            logger.error(f"Failed to list OUs: {e}")

        return None

    def _create_and_attach_scps(
        self,
        root_id: str,
        scp_configs: list[SCPConfiguration],
        ou_map: dict[str, str],
    ) -> tuple[dict[str, str], list[str]]:
        """Create SCPs and attach to target OUs."""
        scp_map = {}
        errors = []

        for scp_config in scp_configs:
            try:
                # Check if SCP already exists
                existing_scp = self._find_scp_by_name(scp_config.name)

                if existing_scp:
                    policy_id = existing_scp["Id"]
                    logger.info(
                        f"SCP '{scp_config.name}' already exists: {policy_id}"
                    )

                    # Update policy content
                    try:
                        self.orgs_client.update_policy(
                            PolicyId=policy_id,
                            Content=json.dumps(scp_config.policy_document),
                        )
                        logger.info(f"Updated SCP '{scp_config.name}'")
                    except ClientError as e:
                        logger.warning(f"Failed to update SCP: {e}")

                else:
                    # Create SCP
                    response = self.orgs_client.create_policy(
                        Content=json.dumps(scp_config.policy_document),
                        Description=scp_config.description,
                        Name=scp_config.name,
                        Type="SERVICE_CONTROL_POLICY",
                    )
                    policy_id = response["Policy"]["PolicySummary"]["Id"]
                    logger.info(f"Created SCP '{scp_config.name}': {policy_id}")

                scp_map[scp_config.name] = policy_id

                # Attach to target OUs
                for ou_name in scp_config.target_ous:
                    ou_id = ou_map.get(ou_name)
                    if ou_id:
                        try:
                            self.orgs_client.attach_policy(
                                PolicyId=policy_id,
                                TargetId=ou_id,
                            )
                            logger.info(
                                f"Attached SCP '{scp_config.name}' to OU '{ou_name}'"
                            )
                        except ClientError as e:
                            if e.response["Error"]["Code"] == "DuplicatePolicyAttachmentException":
                                logger.info(
                                    f"SCP '{scp_config.name}' already attached to '{ou_name}'"
                                )
                            else:
                                raise
                    else:
                        error_msg = f"OU '{ou_name}' not found for SCP '{scp_config.name}'"
                        logger.error(error_msg)
                        errors.append(error_msg)

            except ClientError as e:
                error_msg = f"Failed to create/attach SCP '{scp_config.name}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return scp_map, errors

    def _find_scp_by_name(self, name: str) -> Optional[dict]:
        """Find SCP by name."""
        try:
            paginator = self.orgs_client.get_paginator("list_policies")

            for page in paginator.paginate(Filter="SERVICE_CONTROL_POLICY"):
                for policy in page["Policies"]:
                    if policy["Name"] == name:
                        return policy

        except ClientError as e:
            logger.error(f"Failed to list SCPs: {e}")

        return None

    def get_aws_recommended_ou_structure(self) -> list[OUConfiguration]:
        """Get AWS recommended OU structure."""
        return [
            # Core OUs
            OUConfiguration(
                name="Security",
                description="Security and audit accounts",
            ),
            OUConfiguration(
                name="Infrastructure",
                description="Shared infrastructure accounts",
            ),
            # Workloads with environments
            OUConfiguration(
                name="Workloads",
                description="Application workload accounts",
            ),
            OUConfiguration(
                name="Production",
                parent_id="Workloads",
                description="Production workload accounts",
            ),
            OUConfiguration(
                name="Staging",
                parent_id="Workloads",
                description="Staging workload accounts",
            ),
            OUConfiguration(
                name="Development",
                parent_id="Workloads",
                description="Development workload accounts",
            ),
            # Sandbox and testing
            OUConfiguration(
                name="Sandbox",
                description="Individual sandbox accounts",
            ),
            # Policy staging
            OUConfiguration(
                name="PolicyStaging",
                description="OU for testing SCPs before rollout",
            ),
            # Suspended accounts
            OUConfiguration(
                name="Suspended",
                description="Decommissioned accounts",
            ),
        ]

    def get_recommended_scps(self) -> list[SCPConfiguration]:
        """Get recommended baseline SCPs."""
        return [
            # Protect security services
            SCPConfiguration(
                name="DenySecurityServiceDisabling",
                description="Prevent disabling security services",
                policy_document={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Action": [
                                "cloudtrail:StopLogging",
                                "cloudtrail:DeleteTrail",
                                "guardduty:DeleteDetector",
                                "guardduty:DisassociateFromMasterAccount",
                                "guardduty:DisassociateMembers",
                                "securityhub:DisableSecurityHub",
                                "securityhub:DisassociateFromMasterAccount",
                                "config:DeleteConfigurationRecorder",
                                "config:DeleteDeliveryChannel",
                                "config:StopConfigurationRecorder",
                            ],
                            "Resource": "*",
                        }
                    ],
                },
                target_ous=["Production", "Staging", "Security"],
            ),
            # Prevent leaving organization
            SCPConfiguration(
                name="DenyLeavingOrganization",
                description="Prevent accounts from leaving organization",
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
                target_ous=["Workloads", "Security", "Infrastructure", "Sandbox"],
            ),
            # Region restriction (customize regions as needed)
            SCPConfiguration(
                name="RestrictRegions",
                description="Restrict operations to approved regions",
                policy_document={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Action": "*",
                            "Resource": "*",
                            "Condition": {
                                "StringNotEquals": {
                                    "aws:RequestedRegion": [
                                        "us-east-1",
                                        "us-west-2",
                                    ]
                                }
                            },
                        }
                    ],
                },
                target_ous=["Production"],
            ),
            # Require IMDSv2
            SCPConfiguration(
                name="RequireIMDSv2",
                description="Require IMDSv2 for EC2 instances",
                policy_document={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Action": "ec2:RunInstances",
                            "Resource": "arn:aws:ec2:*:*:instance/*",
                            "Condition": {
                                "StringNotEquals": {
                                    "ec2:MetadataHttpTokens": "required"
                                }
                            },
                        }
                    ],
                },
                target_ous=["Production", "Staging"],
            ),
            # Deny root user access (except break-glass)
            SCPConfiguration(
                name="DenyRootUserAccess",
                description="Deny root user access (emergency use only)",
                policy_document={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Action": "*",
                            "Resource": "*",
                            "Condition": {
                                "StringLike": {
                                    "aws:PrincipalArn": "arn:aws:iam::*:root"
                                }
                            },
                        }
                    ],
                },
                target_ous=["Workloads"],
            ),
        ]
