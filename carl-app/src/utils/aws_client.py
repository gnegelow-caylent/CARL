"""
AWS client utilities for CARL.
"""

import json
import os
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from utils.logger import get_logger

logger = get_logger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


@lru_cache(maxsize=10)
def get_secret(secret_arn: str) -> str:
    """
    Retrieve a secret from AWS Secrets Manager.

    Results are cached to avoid repeated API calls.
    """
    client = boto3.client("secretsmanager", region_name=AWS_REGION)

    try:
        response = client.get_secret_value(SecretId=secret_arn)

        if "SecretString" in response:
            return response["SecretString"]
        else:
            # Binary secret
            import base64
            return base64.b64decode(response["SecretBinary"]).decode("utf-8")

    except ClientError as e:
        logger.error(f"Error retrieving secret {secret_arn}: {e}")
        raise


def get_parameter(parameter_name: str, decrypt: bool = True) -> str:
    """Retrieve a parameter from AWS Systems Manager Parameter Store."""
    client = boto3.client("ssm", region_name=AWS_REGION)

    try:
        response = client.get_parameter(
            Name=parameter_name,
            WithDecryption=decrypt,
        )
        return response["Parameter"]["Value"]

    except ClientError as e:
        logger.error(f"Error retrieving parameter {parameter_name}: {e}")
        raise


def assume_role(role_arn: str, session_name: str = "CARL") -> dict:
    """
    Assume an IAM role and return temporary credentials.

    Used for cross-account access.
    """
    client = boto3.client("sts", region_name=AWS_REGION)

    try:
        response = client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            DurationSeconds=3600,  # 1 hour
        )

        credentials = response["Credentials"]
        return {
            "aws_access_key_id": credentials["AccessKeyId"],
            "aws_secret_access_key": credentials["SecretAccessKey"],
            "aws_session_token": credentials["SessionToken"],
        }

    except ClientError as e:
        logger.error(f"Error assuming role {role_arn}: {e}")
        raise


def get_cross_account_client(
    service: str,
    role_arn: str,
    region: str | None = None,
):
    """
    Get a boto3 client for a service in another account.

    Args:
        service: AWS service name (e.g., 's3', 'ec2')
        role_arn: ARN of the role to assume
        region: AWS region (defaults to current region)
    """
    credentials = assume_role(role_arn)

    return boto3.client(
        service,
        region_name=region or AWS_REGION,
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        aws_session_token=credentials["aws_session_token"],
    )


def get_account_id() -> str:
    """Get the current AWS account ID."""
    client = boto3.client("sts", region_name=AWS_REGION)
    return client.get_caller_identity()["Account"]
