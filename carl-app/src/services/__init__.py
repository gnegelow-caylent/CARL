# CARL Services
"""
CARL Service Layer - Core business logic and AI capabilities.

Services:
- bedrock_service: Base Bedrock/Claude interaction
- ai_architect: AI-driven architecture recommendations (hybrid static + AI)
- knowledge_retrieval: RAG and continuous learning system
- slack_service: Slack integration
- findings_service: Compliance findings management
- architecture_advisor: Architecture pattern advisor
- cost_estimator: AWS cost estimation
- infrastructure_builder: Terraform code generation

Foundation subpackage:
- decision_engine: Guided decision workflow with AI
- foundation_builder: Foundation infrastructure generation
"""

from .bedrock_service import BedrockService
from .ai_architect import AIArchitect, get_ai_architect
from .knowledge_retrieval import KnowledgeRetrievalService, get_knowledge_service

__all__ = [
    "BedrockService",
    "AIArchitect",
    "get_ai_architect",
    "KnowledgeRetrievalService",
    "get_knowledge_service",
]
