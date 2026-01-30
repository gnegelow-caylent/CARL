"""
Pricing Prefetch Lambda Handler

Invoked monthly (1st of month at 3am UTC) to prefetch AWS pricing data.

This Lambda:
1. Queries AWS Price List API for common services
2. Caches pricing in DynamoDB (pricing-cache table)
3. Publishes CloudWatch metrics
4. Takes 5-10 minutes to run

Cost: ~$0.05/month (12 invocations/year × 10 min execution)
ROI: Eliminates 5-15 second delays on every architecture question
"""

import json
import os
from datetime import datetime

import boto3

from services.pricing_prefetch_service import PricingPrefetchService
from utils.logger import get_logger

logger = get_logger(__name__)


def handler(event, context):
    """
    Prefetch AWS pricing data for common services.

    This runs monthly to keep pricing cache fresh. AWS pricing
    changes infrequently (monthly/quarterly), so monthly refresh
    is more than sufficient.

    Args:
        event: EventBridge event (cron trigger)
        context: Lambda context

    Returns:
        Success/failure status with prefetch summary
    """
    logger.info("Starting monthly AWS pricing prefetch")

    try:
        # Get table name from environment
        pricing_cache_table = os.environ.get("PRICING_CACHE_TABLE")

        if not pricing_cache_table:
            logger.error("Missing PRICING_CACHE_TABLE environment variable")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Missing table configuration"})
            }

        # Initialize prefetch service
        prefetch_service = PricingPrefetchService(
            pricing_cache_table=pricing_cache_table
        )

        # Prefetch pricing for common regions
        regions = [
            "us-east-1",
            "us-west-2",
            "eu-west-1",
        ]

        logger.info(f"Prefetching pricing for regions: {', '.join(regions)}")

        results = prefetch_service.prefetch_all_pricing(regions=regions)

        # Log results
        logger.info("="*60)
        logger.info("PRICING PREFETCH COMPLETE")
        logger.info("="*60)
        logger.info(f"Timestamp: {results['timestamp']}")
        logger.info(f"Total items cached: {results['total_items']}")
        logger.info(f"Regions: {', '.join(results['regions'])}")

        for service, service_results in results['services'].items():
            if service_results['status'] == 'success':
                logger.info(f"  ✓ {service}: {service_results['items']} items")
            else:
                logger.error(f"  ✗ {service}: {service_results.get('error', 'Unknown error')}")

        if results['errors']:
            logger.warning(f"Encountered {len(results['errors'])} errors:")
            for error in results['errors']:
                logger.warning(f"  - {error}")

        # Publish CloudWatch metrics
        try:
            cloudwatch = boto3.client("cloudwatch")

            metrics = [
                {
                    "MetricName": "PricingItemsCached",
                    "Value": results['total_items'],
                    "Unit": "Count",
                    "Timestamp": datetime.utcnow()
                },
                {
                    "MetricName": "PricingServicesSuccess",
                    "Value": sum(1 for s in results['services'].values() if s['status'] == 'success'),
                    "Unit": "Count",
                    "Timestamp": datetime.utcnow()
                },
                {
                    "MetricName": "PricingServicesFailed",
                    "Value": len(results['errors']),
                    "Unit": "Count",
                    "Timestamp": datetime.utcnow()
                }
            ]

            cloudwatch.put_metric_data(
                Namespace="CARL/Pricing",
                MetricData=metrics
            )

            logger.info(f"Published {len(metrics)} metrics to CloudWatch")

        except Exception as e:
            logger.warning(f"Failed to publish CloudWatch metrics: {e}")

        # Return summary
        return {
            "statusCode": 200,
            "body": json.dumps(results, default=str)
        }

    except Exception as e:
        logger.exception("Failed to prefetch pricing")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "error": str(e)
            })
        }
