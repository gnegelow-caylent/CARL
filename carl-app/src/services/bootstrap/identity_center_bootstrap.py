"""
IAM Identity Center Bootstrap Service for CARL.

Automates the setup of IAM Identity Center (SSO), permission sets,
and account assignments.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class PermissionSetConfiguration:
    """Permission set configuration."""
    name: str
    description: str
    session_duration: str = "PT1H"  # ISO 8601 duration (PT1H = 1 hour)
    managed_policies: list[str] = None  # ARNs of managed policies
    inline_policy: Optional[dict[str, Any]] = None
    tags: dict[str, str] = None

    def __post_init__(self):
        if self.managed_policies is None:
            self.managed_policies = []
        if self.tags is None:
            self.tags = {}


@dataclass
class GroupConfiguration:
    """Identity Center group configuration."""
    name: str
    description: str


@dataclass
class AccountAssignment:
    """Account and permission set assignment."""
    account_id: str
    permission_set_name: str
    principal_type: str  # "GROUP" or "USER"
    principal_name: str  # Group or user name


@dataclass
class IdentityCenterBootstrapResult:
    """Result of Identity Center bootstrap."""
    success: bool
    instance_arn: str
    identity_store_id: str
    permission_set_map: dict[str, str]  # Name -> ARN
    group_map: dict[str, str]  # Name -> Group ID
    assignment_results: list[dict[str, Any]]
    errors: list[str]


class IdentityCenterBootstrapService:
    """Service for bootstrapping IAM Identity Center."""

    def __init__(self):
        self.sso_admin_client = boto3.client("sso-admin")
        self.identity_store_client = boto3.client("identitystore")
        self.orgs_client = boto3.client("organizations")

    def bootstrap_identity_center(
        self,
        permission_sets: Optional[list[PermissionSetConfiguration]] = None,
        groups: Optional[list[GroupConfiguration]] = None,
        assignments: Optional[list[AccountAssignment]] = None,
    ) -> IdentityCenterBootstrapResult:
        """
        Bootstrap IAM Identity Center with permission sets and assignments.

        Args:
            permission_sets: List of permission sets to create
            groups: List of groups to create
            assignments: List of account assignments

        Returns:
            IdentityCenterBootstrapResult
        """
        errors = []
        permission_set_map = {}
        group_map = {}
        assignment_results = []

        # Get Identity Center instance
        try:
            instance_arn, identity_store_id = self._get_instance()
            logger.info(
                f"Identity Center instance: {instance_arn}, "
                f"Identity store: {identity_store_id}"
            )
        except Exception as e:
            logger.error(f"Failed to get Identity Center instance: {e}")
            return IdentityCenterBootstrapResult(
                success=False,
                instance_arn="",
                identity_store_id="",
                permission_set_map={},
                group_map={},
                assignment_results=[],
                errors=[str(e)],
            )

        # Create permission sets
        if permission_sets:
            permission_set_map, ps_errors = self._create_permission_sets(
                instance_arn, permission_sets
            )
            errors.extend(ps_errors)

        # Create groups
        if groups:
            group_map, group_errors = self._create_groups(
                identity_store_id, groups
            )
            errors.extend(group_errors)

        # Create account assignments
        if assignments:
            assignment_results, assign_errors = self._create_assignments(
                instance_arn,
                identity_store_id,
                assignments,
                permission_set_map,
                group_map,
            )
            errors.extend(assign_errors)

        return IdentityCenterBootstrapResult(
            success=len(errors) == 0,
            instance_arn=instance_arn,
            identity_store_id=identity_store_id,
            permission_set_map=permission_set_map,
            group_map=group_map,
            assignment_results=assignment_results,
            errors=errors,
        )

    def _get_instance(self) -> tuple[str, str]:
        """Get Identity Center instance ARN and identity store ID."""
        try:
            response = self.sso_admin_client.list_instances()
            if not response["Instances"]:
                raise ValueError(
                    "No Identity Center instance found. Please enable "
                    "IAM Identity Center in the AWS Console first."
                )

            instance = response["Instances"][0]
            return instance["InstanceArn"], instance["IdentityStoreId"]

        except ClientError as e:
            raise RuntimeError(
                f"Failed to get Identity Center instance: {e}"
            )

    def _create_permission_sets(
        self,
        instance_arn: str,
        ps_configs: list[PermissionSetConfiguration],
    ) -> tuple[dict[str, str], list[str]]:
        """Create permission sets."""
        ps_map = {}
        errors = []

        for ps_config in ps_configs:
            try:
                # Check if permission set exists
                existing_ps = self._find_permission_set_by_name(
                    instance_arn, ps_config.name
                )

                if existing_ps:
                    ps_arn = existing_ps["PermissionSetArn"]
                    logger.info(
                        f"Permission set '{ps_config.name}' already exists: {ps_arn}"
                    )

                    # Update if needed
                    self._update_permission_set(
                        instance_arn, ps_arn, ps_config
                    )

                else:
                    # Create permission set
                    response = self.sso_admin_client.create_permission_set(
                        InstanceArn=instance_arn,
                        Name=ps_config.name,
                        Description=ps_config.description,
                        SessionDuration=ps_config.session_duration,
                        Tags=[
                            {"Key": k, "Value": v}
                            for k, v in ps_config.tags.items()
                        ],
                    )
                    ps_arn = response["PermissionSet"]["PermissionSetArn"]
                    logger.info(
                        f"Created permission set '{ps_config.name}': {ps_arn}"
                    )

                    # Attach managed policies
                    for policy_arn in ps_config.managed_policies:
                        try:
                            self.sso_admin_client.attach_managed_policy_to_permission_set(
                                InstanceArn=instance_arn,
                                PermissionSetArn=ps_arn,
                                ManagedPolicyArn=policy_arn,
                            )
                            logger.info(
                                f"Attached policy {policy_arn} to '{ps_config.name}'"
                            )
                        except ClientError as e:
                            if (
                                e.response["Error"]["Code"]
                                != "ConflictException"
                            ):
                                raise

                    # Add inline policy
                    if ps_config.inline_policy:
                        self.sso_admin_client.put_inline_policy_to_permission_set(
                            InstanceArn=instance_arn,
                            PermissionSetArn=ps_arn,
                            InlinePolicy=json.dumps(ps_config.inline_policy),
                        )
                        logger.info(
                            f"Added inline policy to '{ps_config.name}'"
                        )

                ps_map[ps_config.name] = ps_arn

            except ClientError as e:
                error_msg = f"Failed to create permission set '{ps_config.name}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return ps_map, errors

    def _find_permission_set_by_name(
        self, instance_arn: str, name: str
    ) -> Optional[dict]:
        """Find permission set by name."""
        try:
            paginator = self.sso_admin_client.get_paginator(
                "list_permission_sets"
            )

            for page in paginator.paginate(InstanceArn=instance_arn):
                for ps_arn in page["PermissionSets"]:
                    response = self.sso_admin_client.describe_permission_set(
                        InstanceArn=instance_arn,
                        PermissionSetArn=ps_arn,
                    )
                    ps = response["PermissionSet"]
                    if ps["Name"] == name:
                        return ps

        except ClientError as e:
            logger.error(f"Failed to list permission sets: {e}")

        return None

    def _update_permission_set(
        self,
        instance_arn: str,
        ps_arn: str,
        ps_config: PermissionSetConfiguration,
    ):
        """Update existing permission set."""
        try:
            self.sso_admin_client.update_permission_set(
                InstanceArn=instance_arn,
                PermissionSetArn=ps_arn,
                Description=ps_config.description,
                SessionDuration=ps_config.session_duration,
            )
            logger.info(f"Updated permission set '{ps_config.name}'")

        except ClientError as e:
            logger.warning(f"Failed to update permission set: {e}")

    def _create_groups(
        self, identity_store_id: str, group_configs: list[GroupConfiguration]
    ) -> tuple[dict[str, str], list[str]]:
        """Create Identity Center groups."""
        group_map = {}
        errors = []

        for group_config in group_configs:
            try:
                # Check if group exists
                existing_group = self._find_group_by_name(
                    identity_store_id, group_config.name
                )

                if existing_group:
                    group_id = existing_group["GroupId"]
                    logger.info(
                        f"Group '{group_config.name}' already exists: {group_id}"
                    )
                else:
                    # Create group
                    response = self.identity_store_client.create_group(
                        IdentityStoreId=identity_store_id,
                        DisplayName=group_config.name,
                        Description=group_config.description,
                    )
                    group_id = response["GroupId"]
                    logger.info(
                        f"Created group '{group_config.name}': {group_id}"
                    )

                group_map[group_config.name] = group_id

            except ClientError as e:
                error_msg = (
                    f"Failed to create group '{group_config.name}': {e}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        return group_map, errors

    def _find_group_by_name(
        self, identity_store_id: str, name: str
    ) -> Optional[dict]:
        """Find group by name."""
        try:
            paginator = self.identity_store_client.get_paginator("list_groups")

            for page in paginator.paginate(IdentityStoreId=identity_store_id):
                for group in page["Groups"]:
                    if group["DisplayName"] == name:
                        return group

        except ClientError as e:
            logger.error(f"Failed to list groups: {e}")

        return None

    def _create_assignments(
        self,
        instance_arn: str,
        identity_store_id: str,
        assignments: list[AccountAssignment],
        permission_set_map: dict[str, str],
        group_map: dict[str, str],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Create account assignments."""
        results = []
        errors = []

        for assignment in assignments:
            try:
                # Get permission set ARN
                ps_arn = permission_set_map.get(assignment.permission_set_name)
                if not ps_arn:
                    error_msg = (
                        f"Permission set '{assignment.permission_set_name}' "
                        f"not found"
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue

                # Get principal ID
                if assignment.principal_type == "GROUP":
                    principal_id = group_map.get(assignment.principal_name)
                    if not principal_id:
                        error_msg = (
                            f"Group '{assignment.principal_name}' not found"
                        )
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue
                else:
                    # For USER, need to look up user
                    principal_id = self._find_user_by_name(
                        identity_store_id, assignment.principal_name
                    )
                    if not principal_id:
                        error_msg = (
                            f"User '{assignment.principal_name}' not found"
                        )
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue

                # Check if assignment exists
                if self._assignment_exists(
                    instance_arn,
                    assignment.account_id,
                    ps_arn,
                    assignment.principal_type,
                    principal_id,
                ):
                    logger.info(
                        f"Assignment already exists: {assignment.principal_name} "
                        f"-> {assignment.account_id} -> {assignment.permission_set_name}"
                    )
                    results.append(
                        {
                            "account_id": assignment.account_id,
                            "permission_set": assignment.permission_set_name,
                            "principal": assignment.principal_name,
                            "status": "exists",
                        }
                    )
                    continue

                # Create assignment
                response = self.sso_admin_client.create_account_assignment(
                    InstanceArn=instance_arn,
                    TargetId=assignment.account_id,
                    TargetType="AWS_ACCOUNT",
                    PermissionSetArn=ps_arn,
                    PrincipalType=assignment.principal_type,
                    PrincipalId=principal_id,
                )

                logger.info(
                    f"Created assignment: {assignment.principal_name} "
                    f"-> {assignment.account_id} -> {assignment.permission_set_name}"
                )

                results.append(
                    {
                        "account_id": assignment.account_id,
                        "permission_set": assignment.permission_set_name,
                        "principal": assignment.principal_name,
                        "status": "created",
                        "request_id": response["AccountAssignmentCreationStatus"][
                            "RequestId"
                        ],
                    }
                )

            except ClientError as e:
                error_msg = f"Failed to create assignment: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return results, errors

    def _find_user_by_name(
        self, identity_store_id: str, name: str
    ) -> Optional[str]:
        """Find user ID by username."""
        try:
            paginator = self.identity_store_client.get_paginator("list_users")

            for page in paginator.paginate(IdentityStoreId=identity_store_id):
                for user in page["Users"]:
                    if user.get("UserName") == name:
                        return user["UserId"]

        except ClientError as e:
            logger.error(f"Failed to list users: {e}")

        return None

    def _assignment_exists(
        self,
        instance_arn: str,
        account_id: str,
        ps_arn: str,
        principal_type: str,
        principal_id: str,
    ) -> bool:
        """Check if account assignment already exists."""
        try:
            paginator = self.sso_admin_client.get_paginator(
                "list_account_assignments"
            )

            for page in paginator.paginate(
                InstanceArn=instance_arn,
                AccountId=account_id,
                PermissionSetArn=ps_arn,
            ):
                for assignment in page["AccountAssignments"]:
                    if (
                        assignment["PrincipalType"] == principal_type
                        and assignment["PrincipalId"] == principal_id
                    ):
                        return True

        except ClientError as e:
            logger.error(f"Failed to check assignment: {e}")

        return False

    def get_recommended_permission_sets(
        self,
    ) -> list[PermissionSetConfiguration]:
        """Get recommended baseline permission sets."""
        return [
            PermissionSetConfiguration(
                name="AdministratorAccess",
                description="Full AWS access",
                session_duration="PT1H",
                managed_policies=[
                    "arn:aws:iam::aws:policy/AdministratorAccess"
                ],
                tags={"Purpose": "Admin", "Environment": "All"},
            ),
            PermissionSetConfiguration(
                name="PowerUserAccess",
                description="Full access except IAM and Organizations",
                session_duration="PT4H",
                managed_policies=[
                    "arn:aws:iam::aws:policy/PowerUserAccess"
                ],
                tags={"Purpose": "Development", "Environment": "NonProd"},
            ),
            PermissionSetConfiguration(
                name="ReadOnlyAccess",
                description="Read-only access to all services",
                session_duration="PT12H",
                managed_policies=[
                    "arn:aws:iam::aws:policy/ReadOnlyAccess"
                ],
                tags={"Purpose": "Audit", "Environment": "All"},
            ),
            PermissionSetConfiguration(
                name="SecurityAudit",
                description="Security audit and compliance access",
                session_duration="PT8H",
                managed_policies=[
                    "arn:aws:iam::aws:policy/SecurityAudit"
                ],
                tags={"Purpose": "Security", "Environment": "All"},
            ),
            PermissionSetConfiguration(
                name="BillingAccess",
                description="Billing and cost management access",
                session_duration="PT8H",
                managed_policies=[
                    "arn:aws:iam::aws:policy/job-function/Billing"
                ],
                tags={"Purpose": "Finance", "Environment": "All"},
            ),
        ]

    def get_recommended_groups(self) -> list[GroupConfiguration]:
        """Get recommended baseline groups."""
        return [
            GroupConfiguration(
                name="CloudPlatformAdmins",
                description="Cloud platform administrators with full access",
            ),
            GroupConfiguration(
                name="Developers",
                description="Developers with PowerUser access in non-prod",
            ),
            GroupConfiguration(
                name="SecurityTeam",
                description="Security team with audit access across all accounts",
            ),
            GroupConfiguration(
                name="ReadOnlyUsers",
                description="Users with read-only access for reporting",
            ),
            GroupConfiguration(
                name="FinanceTeam",
                description="Finance team with billing access",
            ),
        ]
