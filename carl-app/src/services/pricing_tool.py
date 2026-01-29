"""
Real-Time AWS Pricing Tool for Agent Core

This tool allows agents to query real-time AWS pricing using the AWS Price List API.
Any agent can register this tool to get current pricing data for architecture recommendations.

Usage:
    from services.pricing_tool import pricing_tool

    agent = Agent(tools=[pricing_tool], ...)
    # Agent can now call get_aws_pricing autonomously
"""

import boto3
import json
from typing import Optional
from utils.logger import get_logger
from services.agent_core import Tool

logger = get_logger(__name__)


def get_aws_pricing(
    service_code: str,
    region: str = "us-east-1",
    filters: Optional[list] = None,
    max_results: int = 10
) -> dict:
    """
    Get real-time AWS pricing from Price List API.

    This function queries the AWS Price List API for current pricing information.
    It's designed to be called by agents autonomously when they need cost data.

    Args:
        service_code: AWS service code (e.g., "AmazonEC2", "AmazonRDS", "AmazonS3")
        region: AWS region to get pricing for (default: us-east-1)
        filters: Optional list of filters in AWS Price List API format
        max_results: Maximum number of results to return (default: 10)

    Returns:
        dict with:
        - service: Service code queried
        - region: Region queried
        - prices: List of pricing items with details
        - count: Number of results returned

    Example filters:
        [
            {
                "Type": "TERM_MATCH",
                "Field": "instanceType",
                "Value": "t3.medium"
            },
            {
                "Type": "TERM_MATCH",
                "Field": "operatingSystem",
                "Value": "Linux"
            }
        ]
    """
    try:
        # Map region to Price List API region code
        region_code_map = {
            "us-east-1": "US East (N. Virginia)",
            "us-east-2": "US East (Ohio)",
            "us-west-1": "US West (N. California)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "EU (Ireland)",
            "eu-central-1": "EU (Frankfurt)",
            "ap-southeast-1": "Asia Pacific (Singapore)",
            "ap-northeast-1": "Asia Pacific (Tokyo)",
        }

        location = region_code_map.get(region, region)

        # Initialize pricing client (always use us-east-1 for Price List API)
        pricing_client = boto3.client('pricing', region_name='us-east-1')

        # Build filters
        api_filters = filters or []

        # Always add location filter
        api_filters.append({
            "Type": "TERM_MATCH",
            "Field": "location",
            "Value": location
        })

        logger.info(f"Querying AWS Price List API: service={service_code}, region={region}")

        # Query pricing
        response = pricing_client.get_products(
            ServiceCode=service_code,
            Filters=api_filters,
            MaxResults=max_results
        )

        # Parse results
        prices = []
        for price_item in response.get('PriceList', []):
            price_data = json.loads(price_item)

            # Extract key information
            product = price_data.get('product', {})
            attributes = product.get('attributes', {})
            terms = price_data.get('terms', {})

            # Get on-demand pricing (most common)
            on_demand = terms.get('OnDemand', {})

            price_info = {
                "sku": product.get('sku'),
                "product_family": product.get('productFamily'),
                "attributes": attributes,
                "pricing": {}
            }

            # Extract pricing dimensions
            for term_key, term_value in on_demand.items():
                price_dimensions = term_value.get('priceDimensions', {})
                for dim_key, dim_value in price_dimensions.items():
                    price_info["pricing"] = {
                        "unit": dim_value.get('unit'),
                        "price_per_unit": dim_value.get('pricePerUnit', {}).get('USD'),
                        "description": dim_value.get('description')
                    }
                    break  # Take first price dimension
                break  # Take first term

            prices.append(price_info)

        logger.info(f"Found {len(prices)} pricing items for {service_code}")

        return {
            "service": service_code,
            "region": region,
            "prices": prices,
            "count": len(prices),
            "api_response": f"Successfully retrieved {len(prices)} pricing items"
        }

    except Exception as e:
        logger.error(f"Error querying AWS pricing: {e}", exc_info=True)
        return {
            "service": service_code,
            "region": region,
            "prices": [],
            "count": 0,
            "error": str(e),
            "api_response": f"Failed to retrieve pricing: {str(e)}"
        }


def get_common_service_pricing(
    service_name: str,
    region: str = "us-east-1",
    instance_type: Optional[str] = None
) -> dict:
    """
    Get pricing for common AWS services with simplified parameters.

    This is a convenience function for common pricing queries.
    Agents can call this for standard use cases without complex filters.

    Args:
        service_name: Common service name (ec2, rds, s3, glue, dms, lambda, etc.)
        region: AWS region
        instance_type: Optional instance type (for EC2, RDS)

    Returns:
        Pricing data in simplified format
    """
    service_map = {
        "ec2": "AmazonEC2",
        "rds": "AmazonRDS",
        "s3": "AmazonS3",
        "glue": "AWSGlue",
        "dms": "AWSDatabaseMigrationSvc",
        "lambda": "AWSLambda",
        "dynamodb": "AmazonDynamoDB",
        "redshift": "AmazonRedshift",
        "emr": "ElasticMapReduce",
        "kinesis": "AmazonKinesis",
        "vpc": "AmazonVPC",
        "elb": "AWSELB",
        "nat_gateway": "AmazonEC2",  # NAT Gateway is part of EC2 service
    }

    service_code = service_map.get(service_name.lower())
    if not service_code:
        return {
            "service": service_name,
            "error": f"Unknown service: {service_name}. Supported: {', '.join(service_map.keys())}"
        }

    filters = []

    # Add instance-specific filters
    if instance_type and service_name.lower() in ["ec2", "rds"]:
        filters.append({
            "Type": "TERM_MATCH",
            "Field": "instanceType",
            "Value": instance_type
        })

    # EC2-specific filters
    if service_name.lower() == "ec2":
        filters.append({
            "Type": "TERM_MATCH",
            "Field": "operatingSystem",
            "Value": "Linux"
        })
        filters.append({
            "Type": "TERM_MATCH",
            "Field": "tenancy",
            "Value": "Shared"
        })
        filters.append({
            "Type": "TERM_MATCH",
            "Field": "preInstalledSw",
            "Value": "NA"
        })

    return get_aws_pricing(
        service_code=service_code,
        region=region,
        filters=filters,
        max_results=20
    )


# Tool definition for AgentCore
pricing_tool = Tool(
    name="get_aws_pricing",
    description="""Get real-time AWS pricing from the AWS Price List API.

Use this tool when you need to provide cost estimates for AWS services.

Parameters:
- service_name: Service to price (ec2, rds, s3, glue, dms, lambda, dynamodb, redshift, emr, kinesis, vpc, elb, nat_gateway)
- region: AWS region (default: us-east-1)
- instance_type: Optional instance type for EC2/RDS (e.g., "t3.medium", "db.t3.medium")

Returns real-time pricing data including:
- Price per unit (hourly for compute, monthly for storage)
- Unit type (hours, GB-month, etc.)
- Service-specific attributes

Example usage:
- "What's the cost of t3.medium in us-east-1?" → get_aws_pricing(service_name="ec2", instance_type="t3.medium", region="us-east-1")
- "How much is AWS Glue?" → get_aws_pricing(service_name="glue", region="us-east-1")
- "RDS pricing for db.t3.large?" → get_aws_pricing(service_name="rds", instance_type="db.t3.large", region="us-east-1")

IMPORTANT: Always call this tool when answering cost-related questions to provide accurate, up-to-date pricing.
""",
    function=get_common_service_pricing,
    input_schema={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "AWS service name (ec2, rds, s3, glue, dms, lambda, etc.)"
            },
            "region": {
                "type": "string",
                "description": "AWS region code (us-east-1, us-west-2, etc.)",
                "default": "us-east-1"
            },
            "instance_type": {
                "type": "string",
                "description": "Instance type for EC2/RDS (e.g., t3.medium, db.t3.large)"
            }
        },
        "required": ["service_name"]
    }
)
