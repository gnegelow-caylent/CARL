"""
Knowledge Retrieval Service for CARL.

This service enables continuous learning by:
1. Fetching AWS documentation and best practices
2. Storing learned knowledge in a vector database (Bedrock Knowledge Bases)
3. Providing RAG (Retrieval Augmented Generation) for recommendations
4. Caching frequently accessed knowledge

The goal is to keep CARL's recommendations current with the latest
AWS features, services, and best practices.
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional
from dataclasses import dataclass, asdict

import boto3
from botocore.exceptions import ClientError

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class KnowledgeItem:
    """A piece of learned knowledge."""
    id: str
    category: str
    topic: str
    content: str
    source: str  # "aws_docs", "user_feedback", "best_practice", "case_study"
    confidence: float  # 0.0 to 1.0
    last_updated: str
    times_used: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeItem":
        return cls(**data)


# AWS documentation sources for different topics
AWS_DOCUMENTATION_SOURCES = {
    "well_architected": [
        "https://docs.aws.amazon.com/wellarchitected/latest/framework/",
        "https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/",
        "https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/",
        "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/",
    ],
    "landing_zone": [
        "https://docs.aws.amazon.com/controltower/latest/userguide/",
        "https://docs.aws.amazon.com/prescriptive-guidance/latest/migration-aws-environment/",
    ],
    "security": [
        "https://docs.aws.amazon.com/securityhub/latest/userguide/",
        "https://docs.aws.amazon.com/guardduty/latest/ug/",
        "https://docs.aws.amazon.com/config/latest/developerguide/",
    ],
    "networking": [
        "https://docs.aws.amazon.com/vpc/latest/userguide/",
        "https://docs.aws.amazon.com/vpc/latest/tgw/",
        "https://docs.aws.amazon.com/directconnect/latest/UserGuide/",
    ],
    "identity": [
        "https://docs.aws.amazon.com/singlesignon/latest/userguide/",
        "https://docs.aws.amazon.com/IAM/latest/UserGuide/",
    ],
}


class KnowledgeRetrievalService:
    """Service for retrieving and managing learned knowledge."""

    def __init__(
        self,
        knowledge_base_id: str = None,
        dynamodb_table: str = None,
        s3_bucket: str = None
    ):
        """
        Initialize the knowledge retrieval service.

        Args:
            knowledge_base_id: Bedrock Knowledge Base ID for RAG
            dynamodb_table: DynamoDB table for knowledge storage
            s3_bucket: S3 bucket for document storage
        """
        self.knowledge_base_id = knowledge_base_id
        self.s3_bucket = s3_bucket

        # Initialize AWS clients
        self.bedrock_agent = boto3.client("bedrock-agent-runtime", region_name="us-east-1")
        self.bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        self.s3 = boto3.client("s3")

        # DynamoDB for knowledge storage
        if dynamodb_table:
            self.dynamodb = boto3.resource("dynamodb")
            self.table = self.dynamodb.Table(dynamodb_table)
        else:
            self.table = None

        # In-memory cache for frequently accessed knowledge
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(hours=1)

    def retrieve_from_knowledge_base(
        self,
        query: str,
        num_results: int = 5
    ) -> list[dict]:
        """
        Retrieve relevant knowledge using Bedrock Knowledge Bases (RAG).

        This queries a pre-indexed knowledge base containing AWS documentation,
        best practices, and learned patterns.
        """
        if not self.knowledge_base_id:
            logger.warning("No Knowledge Base configured for RAG")
            return []

        try:
            response = self.bedrock_agent.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": num_results
                    }
                }
            )

            results = []
            for result in response.get("retrievalResults", []):
                results.append({
                    "content": result.get("content", {}).get("text", ""),
                    "source": result.get("location", {}).get("s3Location", {}).get("uri", ""),
                    "score": result.get("score", 0.0)
                })

            return results

        except ClientError as e:
            logger.exception("Error retrieving from Knowledge Base")
            return []

    def retrieve_and_generate(
        self,
        query: str,
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    ) -> str:
        """
        Retrieve knowledge and generate a response using RAG.

        This combines retrieval from the knowledge base with generation
        for a complete RAG workflow.
        """
        if not self.knowledge_base_id:
            return self._generate_without_rag(query, model_id)

        try:
            response = self.bedrock_agent.retrieve_and_generate(
                input={"text": query},
                retrieveAndGenerateConfiguration={
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": self.knowledge_base_id,
                        "modelArn": f"arn:aws:bedrock:us-east-1::foundation-model/{model_id}",
                        "retrievalConfiguration": {
                            "vectorSearchConfiguration": {
                                "numberOfResults": 5
                            }
                        }
                    }
                }
            )

            return response.get("output", {}).get("text", "")

        except ClientError as e:
            logger.exception("Error in retrieve_and_generate")
            return self._generate_without_rag(query, model_id)

    def _generate_without_rag(self, query: str, model_id: str) -> str:
        """Fallback generation without RAG when knowledge base unavailable."""
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2048,
                "temperature": 0.4,
                "messages": [{"role": "user", "content": query}],
            }

            response = self.bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except Exception as e:
            logger.exception("Error in fallback generation")
            return f"Error generating response: {str(e)}"

    def store_knowledge(self, item: KnowledgeItem) -> bool:
        """Store a piece of learned knowledge."""
        if not self.table:
            logger.warning("No DynamoDB table configured for knowledge storage")
            return False

        try:
            self.table.put_item(Item=item.to_dict())
            # Update cache
            cache_key = f"{item.category}:{item.topic}"
            self._cache[cache_key] = (item, datetime.utcnow())
            return True
        except Exception as e:
            logger.exception("Error storing knowledge")
            return False

    def get_knowledge(
        self,
        category: str,
        topic: str = None,
        min_confidence: float = 0.5
    ) -> list[KnowledgeItem]:
        """Retrieve stored knowledge by category and optionally topic."""
        # Check cache first
        cache_key = f"{category}:{topic or 'all'}"
        if cache_key in self._cache:
            cached, timestamp = self._cache[cache_key]
            if datetime.utcnow() - timestamp < self._cache_ttl:
                return cached if isinstance(cached, list) else [cached]

        if not self.table:
            return []

        try:
            # Query by category
            from boto3.dynamodb.conditions import Key, Attr

            if topic:
                response = self.table.query(
                    IndexName="category-topic-index",
                    KeyConditionExpression=Key("category").eq(category) & Key("topic").eq(topic),
                    FilterExpression=Attr("confidence").gte(min_confidence)
                )
            else:
                response = self.table.query(
                    IndexName="category-index",
                    KeyConditionExpression=Key("category").eq(category),
                    FilterExpression=Attr("confidence").gte(min_confidence)
                )

            items = [KnowledgeItem.from_dict(item) for item in response.get("Items", [])]

            # Update cache
            self._cache[cache_key] = (items, datetime.utcnow())

            return items

        except Exception as e:
            logger.exception("Error retrieving knowledge")
            return []

    def learn_from_feedback(
        self,
        category: str,
        topic: str,
        feedback: str,
        is_positive: bool
    ) -> Optional[KnowledgeItem]:
        """
        Learn from user feedback and store as knowledge.

        Positive feedback increases confidence in existing knowledge.
        Negative feedback with corrections creates new knowledge items.
        """
        # Find existing knowledge
        existing = self.get_knowledge(category, topic)

        if is_positive and existing:
            # Boost confidence in existing knowledge
            for item in existing:
                item.positive_feedback += 1
                item.confidence = min(1.0, item.confidence + 0.05)
                item.last_updated = datetime.utcnow().isoformat()
                self.store_knowledge(item)
            return existing[0] if existing else None

        else:
            # Extract learning from feedback using AI
            learning = self._extract_learning_from_feedback(category, topic, feedback)

            if learning:
                item = KnowledgeItem(
                    id=hashlib.sha256(f"{category}:{topic}:{feedback}".encode()).hexdigest()[:16],
                    category=category,
                    topic=topic,
                    content=learning,
                    source="user_feedback",
                    confidence=0.6,  # Start with moderate confidence
                    last_updated=datetime.utcnow().isoformat(),
                    times_used=0,
                    positive_feedback=0,
                    negative_feedback=0
                )
                self.store_knowledge(item)
                return item

        return None

    def _extract_learning_from_feedback(
        self,
        category: str,
        topic: str,
        feedback: str
    ) -> Optional[str]:
        """Use AI to extract actionable learning from feedback."""
        prompt = f"""Extract the key learning from this user feedback about AWS {category} ({topic}):

Feedback: {feedback}

If the feedback contains a correction or improvement to AWS best practices, summarize it as a clear, actionable recommendation. If the feedback is just a complaint without useful information, respond with "NO_LEARNING".

Format the learning as: "When [situation], [recommendation] because [reason]." """

        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.bedrock.invoke_model(
                modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            result = response_body["content"][0]["text"]

            if "NO_LEARNING" in result:
                return None
            return result

        except Exception as e:
            logger.exception("Error extracting learning")
            return None

    def get_contextual_knowledge(
        self,
        query: str,
        categories: list[str] = None
    ) -> str:
        """
        Get contextual knowledge combining RAG + stored knowledge.

        This is the main method for enriching AI recommendations with
        both indexed documentation and learned patterns.
        """
        context_parts = []

        # 1. Get RAG results from knowledge base
        rag_results = self.retrieve_from_knowledge_base(query, num_results=3)
        if rag_results:
            context_parts.append("## Relevant AWS Documentation:")
            for result in rag_results:
                if result["score"] > 0.5:  # Only include high-confidence results
                    context_parts.append(f"- {result['content'][:500]}...")

        # 2. Get stored learned knowledge
        if categories:
            for category in categories:
                items = self.get_knowledge(category, min_confidence=0.7)
                if items:
                    context_parts.append(f"\n## Learned Best Practices ({category}):")
                    for item in items[:3]:  # Top 3 per category
                        context_parts.append(f"- {item.content}")

        return "\n".join(context_parts) if context_parts else ""

    def update_knowledge_usage(self, knowledge_id: str) -> None:
        """Track when knowledge is used in recommendations."""
        if not self.table:
            return

        try:
            self.table.update_item(
                Key={"id": knowledge_id},
                UpdateExpression="SET times_used = times_used + :inc",
                ExpressionAttributeValues={":inc": 1}
            )
        except Exception as e:
            logger.warning(f"Could not update knowledge usage: {e}")

    def refresh_knowledge_from_docs(self, category: str) -> int:
        """
        Refresh knowledge base from AWS documentation.

        This would typically be run as a scheduled job to keep
        the knowledge base current with AWS documentation updates.

        Returns the number of documents processed.
        """
        if category not in AWS_DOCUMENTATION_SOURCES:
            logger.warning(f"No documentation sources configured for {category}")
            return 0

        # Note: Full implementation would:
        # 1. Fetch documents from AWS documentation URLs
        # 2. Parse and chunk the content
        # 3. Upload to S3 for Knowledge Base indexing
        # 4. Trigger Knowledge Base sync

        # For now, log the intent
        sources = AWS_DOCUMENTATION_SOURCES[category]
        logger.info(f"Would refresh {len(sources)} documentation sources for {category}")

        return len(sources)


# Singleton instance
_knowledge_service: Optional[KnowledgeRetrievalService] = None


def get_knowledge_service(
    knowledge_base_id: str = None,
    dynamodb_table: str = None,
    s3_bucket: str = None
) -> KnowledgeRetrievalService:
    """Get or create the Knowledge Retrieval Service singleton."""
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeRetrievalService(
            knowledge_base_id=knowledge_base_id,
            dynamodb_table=dynamodb_table,
            s3_bucket=s3_bucket
        )
    return _knowledge_service
