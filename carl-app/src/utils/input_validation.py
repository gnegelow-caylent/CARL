"""Input validation utilities for user-provided configuration."""
import re
import ipaddress
from typing import Tuple, Optional


def validate_cidr(cidr: str) -> Tuple[bool, Optional[str]]:
    """
    Validate CIDR block format.

    Returns:
        (is_valid, error_message)
    """
    if not cidr or not isinstance(cidr, str):
        return False, "CIDR block is required"

    cidr = cidr.strip()

    # Check basic format
    if not re.match(r'^[\d\.]+/\d+$', cidr):
        return False, "Invalid CIDR format. Use format: 10.0.0.0/16"

    try:
        network = ipaddress.ip_network(cidr, strict=False)

        # Check if it's a private IP range (recommended for VPC)
        if not network.is_private:
            return False, "CIDR must be a private IP range (10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16)"

        # Check prefix length is reasonable for VPC
        if network.prefixlen < 16 or network.prefixlen > 28:
            return False, "CIDR prefix must be between /16 and /28 for VPC"

        return True, None

    except ValueError as e:
        return False, f"Invalid CIDR: {str(e)}"


def validate_resource_name(name: str, resource_type: str = "resource") -> Tuple[bool, Optional[str]]:
    """
    Validate AWS resource name.

    Rules:
    - Lowercase alphanumeric and hyphens only
    - Must start with letter
    - Must end with letter or number
    - 1-63 characters

    Returns:
        (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, f"{resource_type} name is required"

    name = name.strip()

    # Check length
    if len(name) < 1 or len(name) > 63:
        return False, f"{resource_type} name must be 1-63 characters"

    # Check format: lowercase letters, numbers, hyphens
    if not re.match(r'^[a-z][a-z0-9-]*[a-z0-9]$', name):
        return False, f"{resource_type} name must start with a letter, contain only lowercase letters, numbers, and hyphens, and end with a letter or number"

    # Check for consecutive hyphens
    if '--' in name:
        return False, f"{resource_type} name cannot contain consecutive hyphens"

    return True, None


def sanitize_resource_name(name: str) -> str:
    """
    Sanitize a resource name to make it valid.

    - Convert to lowercase
    - Replace spaces and underscores with hyphens
    - Remove invalid characters
    - Ensure starts with letter
    - Ensure ends with letter or number
    """
    if not name:
        return "default"

    # Convert to lowercase
    name = name.lower().strip()

    # Replace spaces and underscores with hyphens
    name = re.sub(r'[\s_]+', '-', name)

    # Remove any character that's not lowercase letter, number, or hyphen
    name = re.sub(r'[^a-z0-9-]', '', name)

    # Remove consecutive hyphens
    name = re.sub(r'-+', '-', name)

    # Ensure starts with letter
    if name and not name[0].isalpha():
        name = 'a' + name

    # Ensure ends with letter or number (remove trailing hyphens)
    name = name.rstrip('-')

    # Ensure minimum length
    if len(name) < 1:
        return "default"

    # Ensure maximum length
    if len(name) > 63:
        name = name[:63].rstrip('-')

    return name


def validate_environment(env: str) -> Tuple[bool, Optional[str]]:
    """
    Validate environment name.

    Returns:
        (is_valid, error_message)
    """
    valid_envs = ['dev', 'development', 'qa', 'staging', 'stage', 'prod', 'production']

    if not env or not isinstance(env, str):
        return False, "Environment is required"

    env = env.lower().strip()

    if env not in valid_envs:
        return False, f"Environment must be one of: {', '.join(valid_envs)}"

    return True, None


def validate_port(port: int) -> Tuple[bool, Optional[str]]:
    """
    Validate port number.

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(port, int):
        try:
            port = int(port)
        except (ValueError, TypeError):
            return False, "Port must be a number"

    if port < 1 or port > 65535:
        return False, "Port must be between 1 and 65535"

    return True, None


def validate_aws_region(region: str) -> Tuple[bool, Optional[str]]:
    """
    Validate AWS region name.

    Returns:
        (is_valid, error_message)
    """
    # Common AWS regions (not exhaustive, but covers most)
    valid_regions = [
        'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
        'ca-central-1',
        'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1', 'eu-south-1',
        'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
        'ap-southeast-1', 'ap-southeast-2', 'ap-southeast-3',
        'ap-south-1', 'ap-east-1',
        'sa-east-1',
        'me-south-1',
        'af-south-1',
    ]

    if not region or not isinstance(region, str):
        return False, "AWS region is required"

    region = region.lower().strip()

    if region not in valid_regions:
        return False, f"Invalid AWS region. Common regions: us-east-1, us-west-2, eu-west-1, etc."

    return True, None


def validate_s3_bucket_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate S3 bucket name according to AWS naming rules.

    Rules:
    - 3-63 characters
    - Lowercase letters, numbers, hyphens, and dots only
    - Must start and end with lowercase letter or number
    - No consecutive dots
    - Not formatted as an IP address

    Returns:
        (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Bucket name is required"

    name = name.strip().lower()

    # Check length
    if len(name) < 3 or len(name) > 63:
        return False, "Bucket name must be 3-63 characters"

    # Check format: lowercase letters, numbers, hyphens, dots
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', name):
        return False, "Bucket name must start and end with a letter or number, and contain only lowercase letters, numbers, hyphens, and dots"

    # Check for consecutive dots
    if '..' in name:
        return False, "Bucket name cannot contain consecutive dots"

    # Check for dot-dash patterns (AWS doesn't allow these in some contexts)
    if '.-' in name or '-.' in name:
        return False, "Bucket name cannot contain '.-' or '-.'"

    # Check if it looks like an IP address
    parts = name.split('.')
    if len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        return False, "Bucket name cannot be formatted as an IP address"

    return True, None


def sanitize_s3_bucket_name(name: str) -> str:
    """
    Sanitize an S3 bucket name to make it valid.

    - Convert to lowercase
    - Replace spaces and underscores with hyphens
    - Remove invalid characters
    - Ensure starts and ends with letter or number
    - Remove consecutive dots
    """
    if not name:
        return "default-bucket"

    # Convert to lowercase
    name = name.lower().strip()

    # Replace spaces and underscores with hyphens
    name = re.sub(r'[\s_]+', '-', name)

    # Remove any character that's not lowercase letter, number, hyphen, or dot
    name = re.sub(r'[^a-z0-9.-]', '', name)

    # Remove consecutive dots
    name = re.sub(r'\.+', '.', name)

    # Remove consecutive hyphens
    name = re.sub(r'-+', '-', name)

    # Remove dot-dash patterns
    name = re.sub(r'\.-|-\.', '-', name)

    # Ensure starts with letter or number
    if name and not name[0].isalnum():
        name = 'a' + name

    # Ensure ends with letter or number (remove trailing dots/hyphens)
    name = name.rstrip('.-')

    # Ensure minimum length
    if len(name) < 3:
        return "default-bucket"

    # Ensure maximum length
    if len(name) > 63:
        name = name[:63].rstrip('.-')

    return name
