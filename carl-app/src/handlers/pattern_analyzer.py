"""
Pattern Analyzer Lambda Handler

This Lambda function runs periodically (daily) to analyze scan history patterns
and generate learned insights for continuous learning.

Invoked by: EventBridge rule (cron: daily at 2am UTC)
Cost: ~$0/month (within Lambda free tier, 30 invocations/month × 30 seconds)
"""

import json
import os
from datetime import datetime

import boto3

from services.learning_service import LearningService
from utils.logger import get_logger

logger = get_logger(__name__)


def handler(event, context):
    """
    Analyze patterns for all interaction types (scan, architecture, compliance).

    This function:
    1. Analyzes last 30 days of interactions by type
    2. Identifies useful patterns (question → actions)
    3. Tracks resource/component frequency
    4. Identifies common topics
    5. Publishes CloudWatch metrics
    6. Logs insights for monitoring

    Args:
        event: EventBridge event (cron trigger)
        context: Lambda context

    Returns:
        Success/failure status with pattern summary
    """
    logger.info("Starting daily pattern analysis for all interaction types")

    try:
        # Get table names from environment
        scan_history_table = os.environ.get("SCAN_HISTORY_TABLE")
        resource_graph_table = os.environ.get("RESOURCE_GRAPH_TABLE")

        if not scan_history_table or not resource_graph_table:
            logger.error("Missing required environment variables")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Missing table configuration"})
            }

        # Initialize learning service
        learning_service = LearningService(
            scan_history_table=scan_history_table,
            resource_graph_table=resource_graph_table
        )

        all_results = {}

        # Analyze patterns for each interaction type
        interaction_types = ["scan", "architecture", "compliance"]

        for interaction_type in interaction_types:
            logger.info(f"\n{'='*60}")
            logger.info(f"Analyzing {interaction_type.upper()} interactions")
            logger.info(f"{'='*60}")

            patterns = learning_service.analyze_patterns(
                days_lookback=30,
                interaction_type=interaction_type
            )

            if not patterns:
                logger.info(f"No {interaction_type} patterns found - not enough data yet")
                all_results[interaction_type] = {"status": "no_data"}
                continue

            # Log insights for this type
            for pattern_type, pattern in patterns.items():
                logger.info(f"\nPattern Type: {pattern_type}")
                logger.info(f"Confidence: {pattern.confidence:.2%}")
                logger.info(f"Sample Size: {pattern.sample_size}")

                if pattern_type == "question_to_scans":
                    useful_patterns = pattern.pattern_data
                    logger.info(f"Learned {len(useful_patterns)} question → action mappings")

                    # Log top 5 most confident patterns
                    sorted_patterns = sorted(
                        useful_patterns.items(),
                        key=lambda x: x[1]["confidence"],
                        reverse=True
                    )

                    for i, (q_hash, data) in enumerate(sorted_patterns[:5], 1):
                        actions = ", ".join(data["scans"])
                        confidence = data["confidence"]
                        sample_size = data["sample_size"]
                        logger.info(f"  {i}. Actions: [{actions}] - Confidence: {confidence:.2%} (n={sample_size})")

                elif pattern_type == "resource_frequency":
                    top_resources = pattern.pattern_data.get("top_resources", [])
                    logger.info(f"Top 5 frequently checked items:")

                    for i, res in enumerate(top_resources[:5], 1):
                        logger.info(f"  {i}. {res['id']} - checked {res['count']} times")

                elif pattern_type == "common_topics":
                    topics = pattern.pattern_data.get("topics", [])
                    logger.info(f"Top 5 common topics:")

                    for i, topic in enumerate(topics[:5], 1):
                        logger.info(f"  {i}. '{topic['topic']}' - {topic['frequency']} mentions")

            # Store results for this type
            all_results[interaction_type] = {
                "status": "success",
                "patterns_count": len(patterns),
                "insights": {pt: {"confidence": p.confidence, "sample_size": p.sample_size}
                           for pt, p in patterns.items()}
            }

        logger.info("\n" + "=" * 60)
        logger.info("ANALYSIS COMPLETE FOR ALL TYPES")
        logger.info("=" * 60)

        # Publish metrics to CloudWatch for each interaction type
        try:
            cloudwatch = boto3.client("cloudwatch")

            for interaction_type, results in all_results.items():
                if results.get("status") != "success":
                    continue

                metrics = []
                insights = results.get("insights", {})

                # Total patterns learned for this type
                if "question_to_scans" in insights:
                    metrics.append({
                        "MetricName": "PatternsLearned",
                        "Dimensions": [{"Name": "InteractionType", "Value": interaction_type}],
                        "Value": insights["question_to_scans"]["sample_size"],
                        "Unit": "Count",
                        "Timestamp": datetime.utcnow()
                    })

                    # Average confidence
                    metrics.append({
                        "MetricName": "PatternConfidence",
                        "Dimensions": [{"Name": "InteractionType", "Value": interaction_type}],
                        "Value": insights["question_to_scans"]["confidence"] * 100,
                        "Unit": "Percent",
                        "Timestamp": datetime.utcnow()
                    })

                # Put metrics
                if metrics:
                    cloudwatch.put_metric_data(
                        Namespace="CARL/Learning",
                        MetricData=metrics
                    )
                    logger.info(f"Published {len(metrics)} metrics for {interaction_type} to CloudWatch")

        except Exception as e:
            logger.warning(f"Failed to publish CloudWatch metrics: {e}")

        # Return summary
        summary = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "results_by_type": all_results
        }

        logger.info("Pattern analysis complete for all interaction types")

        return {
            "statusCode": 200,
            "body": json.dumps(summary, default=str)
        }

    except Exception as e:
        logger.exception("Failed to analyze patterns")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "error": str(e)
            })
        }
