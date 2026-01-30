"""
Learning Service for CARL - Continuous Learning & Environment Adaptation

This service implements Design Principle #4: Continuous Learning.

Key Functions:
1. Log every scan interaction (question → scans → results)
2. Store user feedback (thumbs up/down)
3. Analyze patterns to learn what scans are most useful
4. Build resource knowledge graph from scan results
5. Generate learned context for agent instructions

Cost: ~$0.67/month (primarily DynamoDB storage and pattern analysis)
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from collections import Counter

import boto3
from boto3.dynamodb.conditions import Key, Attr

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScanInteraction:
    """A single interaction for learning (scan, architecture, or compliance)."""
    interaction_id: str
    account_id: str
    user_id: str
    interaction_type: str  # "scan", "architecture", or "compliance"
    question: str
    question_hash: str  # MD5 hash for grouping similar questions
    scans_performed: list[str]  # Tool names called (or recommendations for architecture)
    resources_found: list[str]  # Resource IDs discovered (or components recommended)
    scan_duration_ms: int
    was_useful: Optional[bool] = None  # User feedback (None = no feedback yet)
    timestamp: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"ACCOUNT#{self.account_id}",
            "sk": f"INTERACTION#{self.timestamp}#{self.interaction_id}",
            "interaction_id": self.interaction_id,
            "account_id": self.account_id,
            "user_id": self.user_id,
            "interaction_type": self.interaction_type,
            "question": self.question,
            "question_hash": self.question_hash,
            "scans_performed": self.scans_performed,
            "resources_found": self.resources_found,
            "scan_duration_ms": self.scan_duration_ms,
            "was_useful": self.was_useful,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ResourceNode:
    """A node in the resource knowledge graph."""
    resource_id: str
    resource_type: str
    account_id: str
    region: str
    relationships: dict = field(default_factory=dict)  # {relationship_type: [resource_ids]}
    properties: dict = field(default_factory=dict)
    last_scanned: str = ""
    scan_count: int = 0
    issues_found: int = 0

    def __post_init__(self):
        if not self.last_scanned:
            self.last_scanned = datetime.utcnow().isoformat()

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "pk": f"ACCOUNT#{self.account_id}#RESOURCE#{self.resource_id}",
            "sk": f"TYPE#{self.resource_type}",
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "account_id": self.account_id,
            "region": self.region,
            "relationships": self.relationships,
            "properties": self.properties,
            "last_scanned": self.last_scanned,
            "scan_count": self.scan_count,
            "issues_found": self.issues_found,
        }


@dataclass
class LearnedPattern:
    """A learned pattern from historical interactions."""
    pattern_type: str  # "question_to_scans", "resource_frequency", "common_topics"
    pattern_data: dict
    confidence: float  # 0.0 to 1.0
    sample_size: int
    last_updated: str = ""

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.utcnow().isoformat()


class LearningService:
    """Service for continuous learning from scan interactions."""

    def __init__(
        self,
        scan_history_table: str,
        resource_graph_table: str,
        account_id: Optional[str] = None
    ):
        self.scan_history_table = scan_history_table
        self.resource_graph_table = resource_graph_table

        self.dynamodb = boto3.resource("dynamodb")
        self.history_table = self.dynamodb.Table(scan_history_table)
        self.graph_table = self.dynamodb.Table(resource_graph_table)

        # Get account ID if not provided
        if account_id:
            self.account_id = account_id
        else:
            sts = boto3.client("sts")
            self.account_id = sts.get_caller_identity()["Account"]

    def log_interaction(
        self,
        user_id: str,
        question: str,
        scans_performed: list[str],
        resources_found: list[str],
        scan_duration_ms: int,
        interaction_type: str = "scan",
        metadata: dict = None
    ) -> str:
        """
        Log an interaction for learning (scan, architecture, or compliance).

        Args:
            user_id: Slack user ID
            question: User's question or request
            scans_performed: List of tool names called (e.g., ["scan_vpc", "scan_iam"])
                           For architecture: patterns/tools used (e.g., ["get_patterns", "get_pricing"])
                           For compliance: assessment steps (e.g., ["assess_soc2", "create_epic"])
            resources_found: List of resource IDs discovered
                           For architecture: components recommended (e.g., ["vpc", "ec2:t3.medium"])
                           For compliance: findings IDs (e.g., ["FND-001", "FND-002"])
            scan_duration_ms: How long the operation took
            interaction_type: Type of interaction: "scan", "architecture", or "compliance"
            metadata: Additional context

        Returns:
            interaction_id for later feedback association
        """
        try:
            # Validate interaction type
            if interaction_type not in ["scan", "architecture", "compliance"]:
                logger.warning(f"Invalid interaction_type: {interaction_type}, defaulting to 'scan'")
                interaction_type = "scan"

            # Generate interaction ID with type prefix
            timestamp = datetime.utcnow()
            type_prefix = interaction_type[:4].upper()  # SCAN, ARCH, COMP
            interaction_id = f"{type_prefix}_{timestamp.strftime('%Y%m%d%H%M%S')}_{hashlib.md5(question.encode()).hexdigest()[:8]}"

            # Hash question for pattern matching (normalize to lowercase, remove punctuation)
            question_normalized = question.lower().strip().rstrip('?!')
            question_hash = hashlib.md5(question_normalized.encode()).hexdigest()

            interaction = ScanInteraction(
                interaction_id=interaction_id,
                account_id=self.account_id,
                user_id=user_id,
                interaction_type=interaction_type,
                question=question,
                question_hash=question_hash,
                scans_performed=scans_performed,
                resources_found=resources_found,
                scan_duration_ms=scan_duration_ms,
                metadata=metadata or {},
                timestamp=timestamp.isoformat()
            )

            # Store in DynamoDB
            self.history_table.put_item(Item=interaction.to_dynamodb_item())

            logger.info(f"Logged {interaction_type} interaction {interaction_id}: {len(scans_performed)} actions, {len(resources_found)} items")

            return interaction_id

        except Exception as e:
            logger.error(f"Failed to log interaction: {e}", exc_info=True)
            return None

    def record_feedback(self, interaction_id: str, was_useful: bool):
        """
        Record user feedback on a scan interaction.

        Args:
            interaction_id: ID from log_interaction()
            was_useful: True for thumbs up, False for thumbs down
        """
        try:
            # Query to find the interaction
            response = self.history_table.query(
                IndexName="AccountIndex",
                KeyConditionExpression=Key("account_id").eq(self.account_id),
                FilterExpression=Attr("interaction_id").eq(interaction_id),
                Limit=1
            )

            if not response.get("Items"):
                logger.warning(f"Interaction {interaction_id} not found for feedback")
                return

            item = response["Items"][0]

            # Update with feedback
            self.history_table.update_item(
                Key={"pk": item["pk"], "sk": item["sk"]},
                UpdateExpression="SET was_useful = :useful",
                ExpressionAttributeValues={":useful": was_useful}
            )

            logger.info(f"Recorded feedback for {interaction_id}: {'👍' if was_useful else '👎'}")

        except Exception as e:
            logger.error(f"Failed to record feedback: {e}", exc_info=True)

    def update_resource_graph(
        self,
        resource_id: str,
        resource_type: str,
        region: str,
        properties: dict = None,
        relationships: dict = None,
        issues_found: int = 0
    ):
        """
        Update resource knowledge graph with scan results.

        Args:
            resource_id: AWS resource ID (e.g., "vpc-abc123")
            resource_type: Resource type (e.g., "VPC", "SecurityGroup")
            region: AWS region
            properties: Resource properties (CIDR, tags, etc.)
            relationships: Related resources (e.g., {"contains": ["sg-123", "subnet-456"]})
            issues_found: Number of issues detected
        """
        try:
            pk = f"ACCOUNT#{self.account_id}#RESOURCE#{resource_id}"
            sk = f"TYPE#{resource_type}"

            # Check if resource exists
            response = self.graph_table.get_item(Key={"pk": pk, "sk": sk})

            if response.get("Item"):
                # Update existing resource
                existing = response["Item"]

                update_expr = "SET last_scanned = :now, scan_count = scan_count + :one"
                expr_values = {
                    ":now": datetime.utcnow().isoformat(),
                    ":one": 1
                }

                if properties:
                    update_expr += ", properties = :props"
                    expr_values[":props"] = properties

                if relationships:
                    update_expr += ", relationships = :rels"
                    expr_values[":rels"] = relationships

                if issues_found is not None:
                    update_expr += ", issues_found = :issues"
                    expr_values[":issues"] = issues_found

                self.graph_table.update_item(
                    Key={"pk": pk, "sk": sk},
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_values
                )

                logger.debug(f"Updated resource graph node: {resource_id}")
            else:
                # Create new resource node
                node = ResourceNode(
                    resource_id=resource_id,
                    resource_type=resource_type,
                    account_id=self.account_id,
                    region=region,
                    properties=properties or {},
                    relationships=relationships or {},
                    scan_count=1,
                    issues_found=issues_found
                )

                self.graph_table.put_item(Item=node.to_dynamodb_item())

                logger.info(f"Created resource graph node: {resource_id}")

        except Exception as e:
            logger.error(f"Failed to update resource graph: {e}", exc_info=True)

    def analyze_patterns(self, days_lookback: int = 30, interaction_type: str = None) -> dict[str, LearnedPattern]:
        """
        Analyze historical interactions to learn patterns.

        Args:
            days_lookback: How many days of history to analyze
            interaction_type: Filter by interaction type ("scan", "architecture", "compliance") or None for all

        Returns:
            Dictionary of learned patterns by type
        """
        try:
            since = (datetime.utcnow() - timedelta(days=days_lookback)).isoformat()

            # Query interactions for this account
            response = self.history_table.query(
                IndexName="AccountIndex",
                KeyConditionExpression=Key("account_id").eq(self.account_id) & Key("timestamp").gte(since)
            )

            all_interactions = response.get("Items", [])

            # Filter by interaction type if specified
            if interaction_type:
                interactions = [i for i in all_interactions if i.get("interaction_type") == interaction_type]
                logger.info(f"Filtered to {len(interactions)} {interaction_type} interactions (from {len(all_interactions)} total)")
            else:
                interactions = all_interactions

            if not interactions:
                logger.info(f"No {interaction_type or 'any'} interactions found for pattern analysis")
                return {}

            logger.info(f"Analyzing {len(interactions)} interactions from last {days_lookback} days")

            patterns = {}

            # Pattern 1: Question → Scans/Recommendations mapping
            question_scan_map = {}
            for item in interactions:
                q_hash = item.get("question_hash")
                scans = item.get("scans_performed", [])
                was_useful = item.get("was_useful")

                if q_hash and scans:
                    if q_hash not in question_scan_map:
                        question_scan_map[q_hash] = {"scans": [], "useful_count": 0, "total_count": 0}

                    question_scan_map[q_hash]["scans"].extend(scans)
                    question_scan_map[q_hash]["total_count"] += 1

                    if was_useful:
                        question_scan_map[q_hash]["useful_count"] += 1

            # Calculate confidence based on feedback
            useful_scan_patterns = {}
            for q_hash, data in question_scan_map.items():
                if data["total_count"] >= 2:  # At least 2 samples
                    # Most common scans for this question type
                    scan_counts = Counter(data["scans"])
                    top_scans = scan_counts.most_common(3)

                    confidence = data["useful_count"] / data["total_count"] if data["total_count"] > 0 else 0.5

                    useful_scan_patterns[q_hash] = {
                        "scans": [s[0] for s in top_scans],
                        "confidence": confidence,
                        "sample_size": data["total_count"]
                    }

            patterns["question_to_scans"] = LearnedPattern(
                pattern_type="question_to_scans",
                pattern_data=useful_scan_patterns,
                confidence=len(useful_scan_patterns) / len(question_scan_map) if question_scan_map else 0,
                sample_size=len(interactions)
            )

            # Pattern 2: Most frequently checked resources
            all_resources = []
            for item in interactions:
                all_resources.extend(item.get("resources_found", []))

            resource_freq = Counter(all_resources)
            top_resources = resource_freq.most_common(10)

            patterns["resource_frequency"] = LearnedPattern(
                pattern_type="resource_frequency",
                pattern_data={
                    "top_resources": [{"id": r[0], "count": r[1]} for r in top_resources],
                    "total_unique": len(set(all_resources))
                },
                confidence=1.0,  # Frequency data is always accurate
                sample_size=len(all_resources)
            )

            # Pattern 3: Common question topics (keywords)
            question_words = []
            for item in interactions:
                question = item.get("question", "").lower()
                # Extract keywords (simple: split and filter common words)
                words = [w for w in question.split() if len(w) > 3 and w not in ['what', 'where', 'when', 'does', 'have', 'this', 'that']]
                question_words.extend(words)

            topic_freq = Counter(question_words)
            top_topics = topic_freq.most_common(10)

            patterns["common_topics"] = LearnedPattern(
                pattern_type="common_topics",
                pattern_data={
                    "topics": [{"topic": t[0], "frequency": t[1]} for t in top_topics]
                },
                confidence=1.0,
                sample_size=len(question_words)
            )

            logger.info(f"Pattern analysis complete: {len(patterns)} patterns learned")

            return patterns

        except Exception as e:
            logger.error(f"Failed to analyze patterns: {e}", exc_info=True)
            return {}

    def get_learned_context(self, question: str = None, interaction_type: str = None) -> str:
        """
        Generate learned context for agent instructions.

        This context is injected into the agent's system prompt to make it
        environment-aware based on past interactions.

        Args:
            question: Current question (optional, for question-specific context)
            interaction_type: Filter by interaction type ("scan", "architecture", "compliance")

        Returns:
            String with learned context for agent
        """
        try:
            # Analyze recent patterns (filtered by type if specified)
            patterns = self.analyze_patterns(days_lookback=30, interaction_type=interaction_type)

            if not patterns:
                return ""

            context_parts = []

            # Add interaction type specific header
            if interaction_type == "architecture":
                header_prefix = "Architecture"
                action_word = "recommendations"
            elif interaction_type == "compliance":
                header_prefix = "Compliance"
                action_word = "assessments"
            else:
                header_prefix = "Scan"
                action_word = "scans"

            # Add common topics
            if "common_topics" in patterns:
                topics = patterns["common_topics"].pattern_data.get("topics", [])[:5]
                if topics:
                    topic_str = ", ".join([t["topic"] for t in topics])
                    context_parts.append(f"Users frequently ask about: {topic_str}")

            # Add frequently checked resources (for scan type)
            if interaction_type in [None, "scan"] and "resource_frequency" in patterns:
                resources = patterns["resource_frequency"].pattern_data.get("top_resources", [])[:5]
                if resources:
                    resource_str = ", ".join([r["id"] for r in resources])
                    context_parts.append(f"Frequently checked resources: {resource_str}")

            # Add question-specific recommendations
            if question and "question_to_scans" in patterns:
                q_normalized = question.lower().strip().rstrip('?!')
                q_hash = hashlib.md5(q_normalized.encode()).hexdigest()

                scan_patterns = patterns["question_to_scans"].pattern_data
                if q_hash in scan_patterns:
                    recommended_scans = scan_patterns[q_hash]["scans"]
                    confidence = scan_patterns[q_hash]["confidence"]

                    if confidence > 0.6:  # High confidence
                        scan_str = ", ".join(recommended_scans)
                        context_parts.append(f"For similar questions, these {action_word} were most useful: {scan_str}")

            if context_parts:
                header = f"\n\nLearned from past {interaction_type or 'all'} interactions:"
                return header + "\n• " + "\n• ".join(context_parts)

            return ""

        except Exception as e:
            logger.error(f"Failed to generate learned context: {e}", exc_info=True)
            return ""

    def get_resource_context(self, resource_ids: list[str] = None) -> str:
        """
        Get context about specific resources from knowledge graph.

        Args:
            resource_ids: Optional list of specific resource IDs to query

        Returns:
            String with resource context
        """
        try:
            if resource_ids:
                # Query specific resources
                nodes = []
                for res_id in resource_ids:
                    response = self.graph_table.query(
                        KeyConditionExpression=Key("pk").eq(f"ACCOUNT#{self.account_id}#RESOURCE#{res_id}")
                    )
                    nodes.extend(response.get("Items", []))
            else:
                # Get top resources by scan frequency
                response = self.graph_table.query(
                    KeyConditionExpression=Key("pk").begins_with(f"ACCOUNT#{self.account_id}#RESOURCE#"),
                    Limit=10
                )
                nodes = response.get("Items", [])

            if not nodes:
                return ""

            context_parts = []
            for node in nodes[:5]:  # Top 5
                res_id = node.get("resource_id")
                res_type = node.get("resource_type")
                issues = node.get("issues_found", 0)

                if issues > 0:
                    context_parts.append(f"{res_id} ({res_type}): {issues} known issues")
                else:
                    context_parts.append(f"{res_id} ({res_type}): no issues")

            if context_parts:
                header = "\n\nKnown resources:"
                return header + "\n• " + "\n• ".join(context_parts)

            return ""

        except Exception as e:
            logger.error(f"Failed to get resource context: {e}", exc_info=True)
            return ""
