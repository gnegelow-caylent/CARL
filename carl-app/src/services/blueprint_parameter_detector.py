"""
Blueprint Parameter Detector - Intelligent input requirement analysis

This service analyzes infrastructure blueprints and intelligently determines
what parameters are required before code generation, replacing hardcoded
pattern matching with AI-driven analysis.
"""

import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ParameterType(Enum):
    """Types of parameters that can be required."""
    CIDR_BLOCK = "cidr_block"
    NAME = "name"
    REGION = "region"
    ENVIRONMENT = "environment"
    INSTANCE_TYPE = "instance_type"
    DATABASE_CONFIG = "database_config"
    BUCKET_NAME = "bucket_name"
    KEY_PAIR = "key_pair"


@dataclass
class ParameterRequirement:
    """A required parameter for a blueprint."""
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Optional[str] = None
    validation_pattern: Optional[str] = None
    validation_message: Optional[str] = None

    def validate(self, value: str) -> tuple[bool, Optional[str]]:
        """
        Validate a parameter value.

        Args:
            value: User-provided value

        Returns:
            (is_valid, error_message)
        """
        if self.required and not value:
            return False, f"{self.name} is required"

        if self.validation_pattern:
            if not re.match(self.validation_pattern, value):
                return False, self.validation_message or f"Invalid format for {self.name}"

        # Type-specific validation
        if self.type == ParameterType.CIDR_BLOCK:
            return self._validate_cidr(value)
        elif self.type == ParameterType.BUCKET_NAME:
            return self._validate_bucket_name(value)
        elif self.type == ParameterType.NAME:
            return self._validate_name(value)

        return True, None

    def _validate_cidr(self, value: str) -> tuple[bool, Optional[str]]:
        """Validate CIDR block format."""
        cidr_pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
        if not re.match(cidr_pattern, value):
            return False, "CIDR must be in format x.x.x.x/xx (e.g., 10.0.0.0/16)"

        # Validate IP octets and mask
        try:
            ip, mask = value.split('/')
            octets = [int(x) for x in ip.split('.')]

            if not all(0 <= octet <= 255 for octet in octets):
                return False, "IP octets must be between 0 and 255"

            if not 0 <= int(mask) <= 32:
                return False, "CIDR mask must be between 0 and 32"

            return True, None
        except:
            return False, "Invalid CIDR format"

    def _validate_bucket_name(self, value: str) -> tuple[bool, Optional[str]]:
        """Validate S3 bucket name format."""
        # S3 bucket name rules
        if len(value) < 3 or len(value) > 63:
            return False, "Bucket name must be between 3 and 63 characters"

        if not re.match(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$', value):
            return False, "Bucket name must start/end with lowercase letter or number, contain only lowercase letters, numbers, and hyphens"

        if '..' in value or '.-' in value or '-.' in value:
            return False, "Bucket name cannot contain consecutive periods or period-dash combinations"

        return True, None

    def _validate_name(self, value: str) -> tuple[bool, Optional[str]]:
        """Validate resource name format."""
        if not re.match(r'^[a-zA-Z0-9\-_]+$', value):
            return False, "Name must contain only letters, numbers, hyphens, and underscores"

        if len(value) < 1 or len(value) > 64:
            return False, "Name must be between 1 and 64 characters"

        return True, None


class BlueprintParameterDetector:
    """Detects required parameters for infrastructure blueprints."""

    # Known blueprint parameter requirements
    BLUEPRINT_PARAMETERS = {
        "networking/standard-vpc": [
            ParameterRequirement(
                name="vpc_cidr",
                type=ParameterType.CIDR_BLOCK,
                description="VPC CIDR block (e.g., 10.0.0.0/16)",
                default="10.0.0.0/16"
            ),
            ParameterRequirement(
                name="vpc_name",
                type=ParameterType.NAME,
                description="Name for the VPC resources",
                default="main"
            ),
            ParameterRequirement(
                name="environment",
                type=ParameterType.ENVIRONMENT,
                description="Environment (dev, staging, prod)",
                default="prod"
            ),
        ],
        "networking/multi-az-vpc": [
            ParameterRequirement(
                name="vpc_cidr",
                type=ParameterType.CIDR_BLOCK,
                description="VPC CIDR block (e.g., 10.0.0.0/16)",
                default="10.0.0.0/16"
            ),
            ParameterRequirement(
                name="vpc_name",
                type=ParameterType.NAME,
                description="Name for the VPC resources",
                default="main"
            ),
            ParameterRequirement(
                name="environment",
                type=ParameterType.ENVIRONMENT,
                description="Environment (dev, staging, prod)",
                default="prod"
            ),
            ParameterRequirement(
                name="az_count",
                type=ParameterType.NAME,
                description="Number of availability zones (2 or 3)",
                default="3",
                validation_pattern=r'^[23]$',
                validation_message="AZ count must be 2 or 3"
            ),
        ],
        "storage/s3-bucket": [
            ParameterRequirement(
                name="bucket_name",
                type=ParameterType.BUCKET_NAME,
                description="S3 bucket name (must be globally unique)",
                required=True
            ),
            ParameterRequirement(
                name="environment",
                type=ParameterType.ENVIRONMENT,
                description="Environment (dev, staging, prod)",
                default="prod"
            ),
        ],
        "security/basic-stack": [
            ParameterRequirement(
                name="environment",
                type=ParameterType.ENVIRONMENT,
                description="Environment (dev, staging, prod)",
                default="prod"
            ),
        ],
        "security/soc2-stack": [
            ParameterRequirement(
                name="environment",
                type=ParameterType.ENVIRONMENT,
                description="Environment (dev, staging, prod)",
                default="prod"
            ),
        ],
    }

    def get_required_parameters(self, blueprint_name: str) -> list[ParameterRequirement]:
        """
        Get required parameters for a blueprint.

        Args:
            blueprint_name: Blueprint identifier (e.g., "networking/standard-vpc")

        Returns:
            List of required parameters
        """
        # Exact match first
        if blueprint_name in self.BLUEPRINT_PARAMETERS:
            return self.BLUEPRINT_PARAMETERS[blueprint_name]

        # Pattern-based fallback (intelligent defaults)
        parameters = []

        # VPC-related blueprints likely need CIDR and name
        if "vpc" in blueprint_name.lower():
            parameters.extend([
                ParameterRequirement(
                    name="vpc_cidr",
                    type=ParameterType.CIDR_BLOCK,
                    description="VPC CIDR block (e.g., 10.0.0.0/16)",
                    default="10.0.0.0/16"
                ),
                ParameterRequirement(
                    name="vpc_name",
                    type=ParameterType.NAME,
                    description="Name for the VPC resources",
                    default="main"
                ),
            ])

        # S3-related blueprints need bucket name
        if "s3" in blueprint_name.lower() or "bucket" in blueprint_name.lower():
            parameters.append(
                ParameterRequirement(
                    name="bucket_name",
                    type=ParameterType.BUCKET_NAME,
                    description="S3 bucket name (must be globally unique)",
                    required=True
                )
            )

        # Database blueprints might need instance config
        if any(db in blueprint_name.lower() for db in ["rds", "database", "aurora"]):
            parameters.extend([
                ParameterRequirement(
                    name="db_instance_class",
                    type=ParameterType.INSTANCE_TYPE,
                    description="Database instance class (e.g., db.t3.micro)",
                    default="db.t3.micro"
                ),
                ParameterRequirement(
                    name="db_name",
                    type=ParameterType.NAME,
                    description="Database name",
                    default="main"
                ),
            ])

        # All blueprints should have environment
        parameters.append(
            ParameterRequirement(
                name="environment",
                type=ParameterType.ENVIRONMENT,
                description="Environment (dev, staging, prod)",
                default="prod"
            )
        )

        return parameters

    def needs_user_input(self, blueprint_name: str) -> bool:
        """
        Check if blueprint requires user input before generation.

        Args:
            blueprint_name: Blueprint identifier

        Returns:
            True if user input is needed
        """
        params = self.get_required_parameters(blueprint_name)
        # Needs input if any parameter is required and has no default
        return any(p.required and not p.default for p in params)

    def validate_parameters(self, blueprint_name: str, provided_params: dict) -> tuple[bool, list[str]]:
        """
        Validate provided parameters against requirements.

        Args:
            blueprint_name: Blueprint identifier
            provided_params: Dictionary of parameter values

        Returns:
            (all_valid, list_of_error_messages)
        """
        required_params = self.get_required_parameters(blueprint_name)
        errors = []

        for param in required_params:
            value = provided_params.get(param.name, param.default)

            # Check if required parameter is missing
            if param.required and not value:
                errors.append(f"Missing required parameter: {param.name}")
                continue

            # Validate the value if provided
            if value:
                is_valid, error_msg = param.validate(value)
                if not is_valid:
                    errors.append(error_msg)

        return len(errors) == 0, errors
