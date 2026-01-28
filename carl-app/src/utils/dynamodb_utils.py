"""DynamoDB utility functions."""
import boto3
import os

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def get_table(table_name: str):
    """
    Get a DynamoDB table resource.

    Args:
        table_name: Name of the DynamoDB table

    Returns:
        boto3 DynamoDB Table resource
    """
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    return dynamodb.Table(table_name)
