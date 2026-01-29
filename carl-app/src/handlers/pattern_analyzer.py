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
    Analyze scan history patterns and log insights.

    This function:
    1. Analyzes last 30 days of scan interactions
    2. Identifies useful patterns (question → scans)
    3. Tracks resource frequency
    4. Identifies common topics
    5. Logs insights for monitoring

    Args:
        event: EventBridge event (cron trigger)
        context: Lambda context

    Returns:
        Success/failure status with pattern summary
    """
    logger.info("Starting daily pattern analysis")

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

        # Analyze patterns from last 30 days
        patterns = learning_service.analyze_patterns(days_lookback=30)

        if not patterns:
            logger.info("No patterns found - not enough data yet")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "status": "success",
                    "message": "No patterns found - need more interaction data"
                })
            }

        # Log insights
        logger.info("=" * 60)
        logger.info("PATTERN ANALYSIS RESULTS")
        logger.info("=" * 60)

        for pattern_type, pattern in patterns.items():
            logger.info(f"\nPattern Type: {pattern_type}")
            logger.info(f"Confidence: {pattern.confidence:.2%}")
            logger.info(f"Sample Size: {pattern.sample_size}")

            if pattern_type == "question_to_scans":
                useful_patterns = pattern.pattern_data
                logger.info(f"Learned {len(useful_patterns)} question → scan mappings")

                # Log top 5 most confident patterns
                sorted_patterns = sorted(
                    useful_patterns.items(),
                    key=lambda x: x[1]["confidence"],
                    reverse=True
                )

                for i, (q_hash, data) in enumerate(sorted_patterns[:5], 1):
                    scans = ", ".join(data["scans"])
                    confidence = data["confidence"]
                    sample_size = data["sample_size"]
                    logger.info(f"  {i}. Scans: [{scans}] - Confidence: {confidence:.2%} (n={sample_size})")

            elif pattern_type == "resource_frequency":
                top_resources = pattern.pattern_data.get("top_resources", [])
                logger.info(f"Top 5 frequently checked resources:")

                for i, res in enumerate(top_resources[:5], 1):
                    logger.info(f"  {i}. {res['id']} - checked {res['count']} times")

            elif pattern_type == "common_topics":
                topics = pattern.pattern_data.get("topics", [])
                logger.info(f"Top 5 common question topics:")

                for i, topic in enumerate(topics[:5], 1):
                    logger.info(f"  {i}. '{topic['topic']}' - {topic['frequency']} mentions")

        logger.info("=" * 60)

        # Publish metrics to CloudWatch (optional)
        try:
            cloudwatch = boto3.client("cloudwatch")

            metrics = []

            # Total patterns learned
            metrics.append({
                "MetricName": "PatternsLearned",
                "Value": len(patterns.get("question_to_scans", {}).pattern_data),
                "Unit": "Count",
                "Timestamp": datetime.utcnow()
            })

            # Average confidence
            if "question_to_scans" in patterns:
                avg_confidence = patterns["question_to_scans"].confidence
                metrics.append({
                    "MetricName": "PatternConfidence",
                    "Value": avg_confidence,
                    "Unit": "Percent",
                    "Timestamp": datetime.utcnow()
                })

            # Total interactions analyzed
            metrics.append({
                "MetricName": "InteractionsAnalyzed",
                "Value": patterns.get("common_topics", patterns.get("resource_frequency")).sample_size,
                "Unit": "Count",
                "Timestamp": datetime.utcnow()
            })

            # Put metrics
            if metrics:
                cloudwatch.put_metric_data(
                    Namespace="CARL/Learning",
                    MetricData=metrics
                )
                logger.info(f"Published {len(metrics)} metrics to CloudWatch")

        except Exception as e:
            logger.warning(f"Failed to publish CloudWatch metrics: {e}")

        # Return summary
        summary = {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "patterns_analyzed": len(patterns),
            "insights": {}
        }

        for pattern_type, pattern in patterns.items():
            summary["insights"][pattern_type] = {
                "confidence": pattern.confidence,
                "sample_size": pattern.sample_size
            }

        logger.info("Pattern analysis complete")

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
