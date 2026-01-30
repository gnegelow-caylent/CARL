"""
Pricing Prefetch Service

Fetches AWS pricing for common services and stores in DynamoDB cache.
This runs as a background Lambda once per month to keep pricing data fresh.

Why prefetch?
- AWS Price List API is slow (5-15 seconds per query)
- Prices change infrequently (monthly/quarterly)
- Architecture agent needs instant pricing for good UX

Cost: ~$0.05/month (runs once per month, 5-10 minute execution)
"""

import boto3
from botocore.config import Config
from decimal import Decimal
import json
from datetime import datetime, timedelta
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)

# Boto3 config with timeouts
PRICING_API_CONFIG = Config(
    connect_timeout=5,
    read_timeout=15,  # Longer timeout for batch queries
    retries={'max_attempts': 3}
)


class PricingPrefetchService:
    """Service to prefetch and cache AWS pricing data."""

    def __init__(self, pricing_cache_table: str):
        """
        Initialize prefetch service.

        Args:
            pricing_cache_table: DynamoDB table name for pricing cache
        """
        self.cache_table = boto3.resource('dynamodb').Table(pricing_cache_table)
        self.pricing_client = boto3.client('pricing', region_name='us-east-1', config=PRICING_API_CONFIG)

    def prefetch_all_pricing(self, regions: list[str] = None) -> dict:
        """
        Prefetch pricing for all common AWS services.

        Args:
            regions: List of regions to fetch pricing for (defaults to common regions)

        Returns:
            Summary of prefetch results
        """
        if regions is None:
            regions = ["us-east-1", "us-west-2", "eu-west-1"]

        logger.info(f"Starting pricing prefetch for {len(regions)} regions")

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "regions": regions,
            "services": {},
            "total_items": 0,
            "errors": []
        }

        # Prefetch each service type
        services_to_fetch = [
            ("ec2", self._prefetch_ec2_pricing),
            ("rds", self._prefetch_rds_pricing),
            ("lambda", self._prefetch_lambda_pricing),
            ("s3", self._prefetch_s3_pricing),
            ("dynamodb", self._prefetch_dynamodb_pricing),
            ("ecs", self._prefetch_ecs_pricing),
        ]

        for service_name, fetch_function in services_to_fetch:
            logger.info(f"Prefetching {service_name} pricing...")
            try:
                count = fetch_function(regions)
                results["services"][service_name] = {"status": "success", "items": count}
                results["total_items"] += count
                logger.info(f"✓ {service_name}: {count} items cached")
            except Exception as e:
                logger.error(f"✗ {service_name} failed: {e}", exc_info=True)
                results["services"][service_name] = {"status": "error", "error": str(e)}
                results["errors"].append(f"{service_name}: {str(e)}")

        logger.info(f"Prefetch complete: {results['total_items']} total items cached")
        return results

    def _prefetch_ec2_pricing(self, regions: list[str]) -> int:
        """Prefetch EC2 instance pricing."""
        # Common instance types used in architecture patterns
        instance_types = [
            "t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge", "t3.2xlarge",
            "t2.micro", "t2.small", "t2.medium",
            "m5.large", "m5.xlarge", "m5.2xlarge", "m5.4xlarge",
            "c5.large", "c5.xlarge", "c5.2xlarge", "c5.4xlarge",
            "r5.large", "r5.xlarge", "r5.2xlarge",
        ]

        count = 0
        for region in regions:
            for instance_type in instance_types:
                try:
                    pricing_data = self._fetch_ec2_instance_price(instance_type, region)
                    if pricing_data:
                        self._store_pricing(pricing_data)
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to fetch {instance_type} in {region}: {e}")

        return count

    def _fetch_ec2_instance_price(self, instance_type: str, region: str) -> Optional[dict]:
        """Fetch pricing for specific EC2 instance type."""
        region_name_map = {
            "us-east-1": "US East (N. Virginia)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "EU (Ireland)",
        }

        location = region_name_map.get(region, region)

        filters = [
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
        ]

        response = self.pricing_client.get_products(
            ServiceCode="AmazonEC2",
            Filters=filters,
            MaxResults=1
        )

        price_list = response.get('PriceList', [])
        if not price_list:
            return None

        price_data = json.loads(price_list[0])
        price_per_hour = self._extract_on_demand_price(price_data)

        if not price_per_hour:
            return None

        return {
            "service_resource": f"ec2#{instance_type}",
            "service": "ec2",
            "region": region,
            "resource_type": instance_type,
            "price_per_hour": str(price_per_hour),
            "price_per_month": str(Decimal(price_per_hour) * Decimal("730")),  # 730 hours/month average
            "unit": "Hrs",
            "attributes": price_data.get("product", {}).get("attributes", {}),
            "last_updated": datetime.utcnow().isoformat(),
            "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
        }

    def _prefetch_rds_pricing(self, regions: list[str]) -> int:
        """Prefetch RDS instance pricing."""
        instance_classes = [
            "db.t3.micro", "db.t3.small", "db.t3.medium", "db.t3.large",
            "db.t2.micro", "db.t2.small",
            "db.m5.large", "db.m5.xlarge", "db.m5.2xlarge",
            "db.r5.large", "db.r5.xlarge",
        ]

        count = 0
        for region in regions:
            for instance_class in instance_classes:
                try:
                    pricing_data = self._fetch_rds_instance_price(instance_class, region)
                    if pricing_data:
                        self._store_pricing(pricing_data)
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to fetch {instance_class} in {region}: {e}")

        return count

    def _fetch_rds_instance_price(self, instance_class: str, region: str) -> Optional[dict]:
        """Fetch pricing for specific RDS instance."""
        region_name_map = {
            "us-east-1": "US East (N. Virginia)",
            "us-west-2": "US West (Oregon)",
            "eu-west-1": "EU (Ireland)",
        }

        location = region_name_map.get(region, region)

        filters = [
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_class},
            {"Type": "TERM_MATCH", "Field": "databaseEngine", "Value": "PostgreSQL"},
            {"Type": "TERM_MATCH", "Field": "deploymentOption", "Value": "Single-AZ"},
        ]

        response = self.pricing_client.get_products(
            ServiceCode="AmazonRDS",
            Filters=filters,
            MaxResults=1
        )

        price_list = response.get('PriceList', [])
        if not price_list:
            return None

        price_data = json.loads(price_list[0])
        price_per_hour = self._extract_on_demand_price(price_data)

        if not price_per_hour:
            return None

        return {
            "service_resource": f"rds#{instance_class}",
            "service": "rds",
            "region": region,
            "resource_type": instance_class,
            "price_per_hour": str(price_per_hour),
            "price_per_month": str(Decimal(price_per_hour) * Decimal("730")),
            "unit": "Hrs",
            "attributes": price_data.get("product", {}).get("attributes", {}),
            "last_updated": datetime.utcnow().isoformat(),
            "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
        }

    def _prefetch_lambda_pricing(self, regions: list[str]) -> int:
        """Prefetch Lambda pricing (execution and requests)."""
        count = 0

        for region in regions:
            # Lambda has simple pricing: execution time + requests
            try:
                # Request pricing
                request_pricing = {
                    "service_resource": "lambda#requests",
                    "service": "lambda",
                    "region": region,
                    "resource_type": "requests",
                    "price_per_million": "0.20",  # $0.20 per 1M requests
                    "unit": "Requests",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(request_pricing)
                count += 1

                # Execution pricing (GB-second)
                execution_pricing = {
                    "service_resource": "lambda#execution",
                    "service": "lambda",
                    "region": region,
                    "resource_type": "execution",
                    "price_per_gb_second": "0.0000166667",  # $0.0000166667 per GB-second
                    "unit": "GB-s",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(execution_pricing)
                count += 1

            except Exception as e:
                logger.warning(f"Failed to store Lambda pricing for {region}: {e}")

        return count

    def _prefetch_s3_pricing(self, regions: list[str]) -> int:
        """Prefetch S3 pricing (storage and requests)."""
        count = 0

        for region in regions:
            try:
                # S3 Standard storage
                storage_pricing = {
                    "service_resource": "s3#standard-storage",
                    "service": "s3",
                    "region": region,
                    "resource_type": "storage",
                    "storage_class": "Standard",
                    "price_per_gb_month": "0.023",  # First 50 TB
                    "unit": "GB-Mo",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(storage_pricing)
                count += 1

                # S3 PUT requests
                put_pricing = {
                    "service_resource": "s3#put-requests",
                    "service": "s3",
                    "region": region,
                    "resource_type": "requests",
                    "request_type": "PUT",
                    "price_per_thousand": "0.005",  # $0.005 per 1000 requests
                    "unit": "Requests",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(put_pricing)
                count += 1

                # S3 GET requests
                get_pricing = {
                    "service_resource": "s3#get-requests",
                    "service": "s3",
                    "region": region,
                    "resource_type": "requests",
                    "request_type": "GET",
                    "price_per_thousand": "0.0004",  # $0.0004 per 1000 requests
                    "unit": "Requests",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(get_pricing)
                count += 1

            except Exception as e:
                logger.warning(f"Failed to store S3 pricing for {region}: {e}")

        return count

    def _prefetch_dynamodb_pricing(self, regions: list[str]) -> int:
        """Prefetch DynamoDB pricing (on-demand and provisioned)."""
        count = 0

        for region in regions:
            try:
                # On-demand write pricing
                write_pricing = {
                    "service_resource": "dynamodb#on-demand-write",
                    "service": "dynamodb",
                    "region": region,
                    "resource_type": "write-request-units",
                    "price_per_million": "1.25",  # $1.25 per million WRUs
                    "unit": "WRU",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(write_pricing)
                count += 1

                # On-demand read pricing
                read_pricing = {
                    "service_resource": "dynamodb#on-demand-read",
                    "service": "dynamodb",
                    "region": region,
                    "resource_type": "read-request-units",
                    "price_per_million": "0.25",  # $0.25 per million RRUs
                    "unit": "RRU",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(read_pricing)
                count += 1

                # Storage pricing
                storage_pricing = {
                    "service_resource": "dynamodb#storage",
                    "service": "dynamodb",
                    "region": region,
                    "resource_type": "storage",
                    "price_per_gb_month": "0.25",  # $0.25 per GB-month
                    "unit": "GB-Mo",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(storage_pricing)
                count += 1

            except Exception as e:
                logger.warning(f"Failed to store DynamoDB pricing for {region}: {e}")

        return count

    def _prefetch_ecs_pricing(self, regions: list[str]) -> int:
        """Prefetch ECS Fargate pricing."""
        count = 0

        for region in regions:
            try:
                # Fargate vCPU pricing
                vcpu_pricing = {
                    "service_resource": "ecs#fargate-vcpu",
                    "service": "ecs",
                    "region": region,
                    "resource_type": "vcpu",
                    "price_per_vcpu_hour": "0.04048",  # us-east-1 pricing
                    "unit": "vCPU-Hr",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(vcpu_pricing)
                count += 1

                # Fargate memory pricing
                memory_pricing = {
                    "service_resource": "ecs#fargate-memory",
                    "service": "ecs",
                    "region": region,
                    "resource_type": "memory",
                    "price_per_gb_hour": "0.004445",  # us-east-1 pricing
                    "unit": "GB-Hr",
                    "last_updated": datetime.utcnow().isoformat(),
                    "ttl": int((datetime.utcnow() + timedelta(days=90)).timestamp())
                }
                self._store_pricing(memory_pricing)
                count += 1

            except Exception as e:
                logger.warning(f"Failed to store ECS pricing for {region}: {e}")

        return count

    def _extract_on_demand_price(self, price_data: dict) -> Optional[str]:
        """Extract on-demand price from AWS Price List API response."""
        try:
            terms = price_data.get("terms", {})
            on_demand = terms.get("OnDemand", {})

            for term_key, term_value in on_demand.items():
                price_dimensions = term_value.get("priceDimensions", {})
                for dim_key, dim_value in price_dimensions.items():
                    price_per_unit = dim_value.get("pricePerUnit", {})
                    usd_price = price_per_unit.get("USD")
                    if usd_price and usd_price != "0.0000000000":
                        return usd_price

            return None
        except Exception as e:
            logger.error(f"Failed to extract price: {e}")
            return None

    def _store_pricing(self, pricing_data: dict):
        """Store pricing data in DynamoDB cache."""
        try:
            self.cache_table.put_item(Item=pricing_data)
        except Exception as e:
            logger.error(f"Failed to store pricing: {e}", exc_info=True)
            raise

    def get_cached_price(self, service_resource: str, region: str = "us-east-1") -> Optional[dict]:
        """
        Get cached pricing data.

        Args:
            service_resource: Service resource key (e.g., "ec2#t3.medium")
            region: AWS region

        Returns:
            Pricing data or None if not found
        """
        try:
            response = self.cache_table.get_item(
                Key={"service_resource": service_resource, "region": region}
            )
            return response.get("Item")
        except Exception as e:
            logger.error(f"Failed to get cached price: {e}")
            return None
