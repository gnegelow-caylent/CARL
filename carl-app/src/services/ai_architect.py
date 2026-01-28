"""
AI-Driven Architecture Recommendation Service for CARL.

This service uses Bedrock/Claude as the intelligence layer with static patterns
as context/guardrails. The AI generates personalized recommendations while
maintaining accurate pricing data.

Hybrid approach:
- Static patterns = structured context/examples for the AI
- AI = generates personalized recommendations and explanations
- Pricing data = anchored to real AWS pricing (AI can hallucinate costs)
- Feedback loop = improves prompts over time
"""

import json
from datetime import datetime
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.logger import get_logger
from src.knowledge import (
    get_all_foundation_patterns,
    get_vpc_patterns,
    get_account_patterns,
    get_identity_patterns,
    get_security_tooling_patterns,
    get_logging_patterns,
    get_operational_patterns,
    NETWORKING_PRICING,
    VPN_PRICING,
    DIRECT_CONNECT_PRICING,
    SECURITY_PRICING,
    LANDING_ZONE_PRICING,
)
from src.knowledge.aws_pricing import (
    BACKUP_PRICING,
    LOGGING_PRICING,
    SYSTEMS_MANAGER_PRICING,
    IDENTITY_PRICING,
    FIREWALL_MANAGER_PRICING,
)

logger = get_logger(__name__)

# Use Sonnet for complex architectural reasoning
ARCHITECT_MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"

ARCHITECT_SYSTEM_PROMPT = """You are CARL's AI Architecture Advisor - an expert AWS Solutions Architect with deep knowledge of:
- AWS Well-Architected Framework (all 6 pillars)
- SOC 2 compliance requirements and control mappings
- AWS security best practices and landing zone design
- Cost optimization strategies
- Multi-account architectures and Control Tower
- Networking patterns (Transit Gateway, VPC, Direct Connect, VPN)
- Identity and access management (IAM Identity Center, permission sets)
- Centralized security tooling (Security Hub, GuardDuty, Config, Inspector)
- Centralized logging and monitoring

Your role is to provide personalized, contextual architecture recommendations based on:
1. The user's specific requirements (scale, budget, compliance needs)
2. AWS best practices and Well-Architected patterns
3. The reference patterns provided as context (use as examples, not rigid rules)
4. Real-world trade-offs and considerations

Guidelines:
- Always explain the "why" behind recommendations, not just the "what"
- Consider future scalability even for small deployments
- Prioritize security without over-engineering for the use case
- Be specific with AWS services and configurations
- Acknowledge trade-offs honestly - there's rarely a perfect solution
- When discussing costs, use ONLY the pricing data provided - never estimate
- Adapt recommendations to the user's experience level
- Reference specific SOC 2 controls when relevant

When you don't have enough information, ask clarifying questions rather than assuming.

IMPORTANT: You are continuously learning. If the user provides feedback that a recommendation didn't work well or they found a better approach, incorporate that learning.
"""

CATEGORY_PROMPTS = {
    "vpc_design": """Analyze VPC design requirements considering:
- CIDR planning for future growth and mergers
- Subnet tiers (public, private, data, management)
- AZ distribution for high availability
- VPC endpoints for AWS service access
- Network segmentation for compliance
- VPC Flow Logs for security monitoring""",

    "account_structure": """Analyze multi-account strategy considering:
- OU structure aligned with business units
- Core accounts (Security, Log Archive, Network, Shared Services)
- Account baselines and guardrails
- SCP policies for preventive controls
- Control Tower vs custom landing zone
- Account vending and lifecycle management""",

    "identity_access": """Analyze identity and access management considering:
- IAM Identity Center as the central identity provider
- Permission sets for role-based access
- Cross-account access patterns
- Break-glass/emergency access procedures
- MFA requirements and policies
- Integration with external IdP (Okta, Azure AD, etc.)""",

    "security_tooling": """Analyze centralized security tooling considering:
- Security Hub for unified security findings
- GuardDuty for threat detection
- AWS Config for compliance monitoring
- Inspector for vulnerability scanning
- Firewall Manager for network security policies
- Detective for security investigation
- Delegated administrator patterns""",

    "logging_monitoring": """Analyze centralized logging considering:
- CloudTrail organization trails
- VPC Flow Logs aggregation
- Application log aggregation
- Log retention and compliance requirements
- S3 vs CloudWatch Logs trade-offs
- SIEM integration requirements
- Cost optimization for log storage""",

    "networking": """Analyze networking architecture considering:
- Egress patterns (NAT, Network Firewall, proxies)
- Ingress patterns (ALB, NLB, CloudFront)
- Transit connectivity (Transit Gateway, peering)
- Hybrid connectivity (VPN, Direct Connect)
- DNS architecture (Route 53, hybrid DNS)
- DDoS protection (Shield, WAF)""",

    "operational": """Analyze operational foundation considering:
- Tagging strategy and enforcement
- Backup and DR requirements
- Cost management and allocation
- Patch management (Systems Manager)
- Configuration management
- Incident response procedures""",

    "foundation_complete": """Design a complete AWS foundation covering:
- Multi-account structure with proper OU hierarchy
- Network architecture with connectivity patterns
- Identity and access management
- Centralized security tooling
- Centralized logging and monitoring
- Operational best practices
- Cost optimization

Consider this as building a production-ready landing zone."""
}


class AIArchitect:
    """AI-driven architecture recommendation service."""

    def __init__(self, table_name: str = None):
        self.bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        self.model_id = ARCHITECT_MODEL_ID

        # DynamoDB for storing feedback and learning
        if table_name:
            self.dynamodb = boto3.resource("dynamodb")
            self.table = self.dynamodb.Table(table_name)
        else:
            self.table = None

        # Load all patterns as context
        self._patterns_cache = None
        self._pricing_cache = None

    def _get_patterns_context(self, category: str = None) -> str:
        """Get relevant patterns as context for the AI."""
        if self._patterns_cache is None:
            self._patterns_cache = {
                "vpc": get_vpc_patterns(),
                "account": get_account_patterns(),
                "identity": get_identity_patterns(),
                "security": get_security_tooling_patterns(),
                "logging": get_logging_patterns(),
                "operational": get_operational_patterns(),
            }

        if category and category in self._patterns_cache:
            patterns = self._patterns_cache[category]
        else:
            patterns = get_all_foundation_patterns()

        # Summarize patterns for context (don't dump everything)
        context_parts = []
        for name, pattern in patterns.items():
            if isinstance(pattern, dict):
                context_parts.append(f"**{name}**: {pattern.get('description', 'No description')}")
                if "options" in pattern:
                    for opt_name, opt in pattern["options"].items():
                        if isinstance(opt, dict):
                            context_parts.append(f"  - {opt_name}: {opt.get('description', '')}")

        return "\n".join(context_parts[:50])  # Limit context size

    def _get_pricing_context(self) -> str:
        """Get pricing data as context for accurate cost estimates."""
        if self._pricing_cache is None:
            self._pricing_cache = {
                "networking": NETWORKING_PRICING,
                "vpn": VPN_PRICING,
                "direct_connect": DIRECT_CONNECT_PRICING,
                "security": SECURITY_PRICING,
                "landing_zone": LANDING_ZONE_PRICING,
                "backup": BACKUP_PRICING,
                "logging": LOGGING_PRICING,
                "systems_manager": SYSTEMS_MANAGER_PRICING,
                "identity": IDENTITY_PRICING,
                "firewall_manager": FIREWALL_MANAGER_PRICING,
            }

        return json.dumps(self._pricing_cache, indent=2)

    def _get_learned_context(self, category: str) -> str:
        """Get learned improvements from past feedback."""
        if not self.table:
            return ""

        try:
            response = self.table.query(
                IndexName="category-index",
                KeyConditionExpression=Key("category").eq(category),
                Limit=10,
                ScanIndexForward=False  # Most recent first
            )

            if response.get("Items"):
                learnings = []
                for item in response["Items"]:
                    if item.get("feedback_type") == "improvement":
                        learnings.append(f"- {item.get('learning', '')}")

                if learnings:
                    return f"\n\nLearned improvements from past feedback:\n" + "\n".join(learnings)
        except Exception as e:
            logger.warning(f"Could not retrieve learned context: {e}")

        return ""

    def invoke_architect(
        self,
        prompt: str,
        category: str = None,
        include_pricing: bool = True,
        max_tokens: int = 4096,
        temperature: float = 0.4,
    ) -> str:
        """Invoke the AI architect with appropriate context."""
        # Build context
        context_parts = []

        # Add category-specific prompt if available
        if category and category in CATEGORY_PROMPTS:
            context_parts.append(f"Focus area:\n{CATEGORY_PROMPTS[category]}")

        # Add relevant patterns as examples
        patterns_context = self._get_patterns_context(category)
        if patterns_context:
            context_parts.append(f"Reference patterns (use as examples, not rigid rules):\n{patterns_context}")

        # Add pricing data
        if include_pricing:
            context_parts.append(f"AWS Pricing Data (use ONLY these figures for cost estimates):\n{self._get_pricing_context()}")

        # Add learned context
        learned = self._get_learned_context(category or "general")
        if learned:
            context_parts.append(learned)

        full_prompt = f"""Context:
{chr(10).join(context_parts)}

User Request:
{prompt}

Provide a comprehensive, personalized recommendation. Include:
1. Recommended approach with specific AWS services
2. Architecture rationale (why this approach)
3. Trade-offs and alternatives considered
4. SOC 2 compliance mapping where relevant
5. Estimated costs using ONLY the pricing data provided
6. Implementation considerations"""

        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": ARCHITECT_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": full_prompt}],
            }

            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except Exception as e:
            logger.exception("Error invoking AI Architect")
            return f"I encountered an error generating the recommendation: {str(e)}"

    def recommend_foundation(self, requirements: dict[str, Any]) -> str:
        """Generate a complete foundation recommendation based on requirements."""
        prompt = f"""Design a complete AWS foundation for this organization:

Requirements:
- Organization size: {requirements.get('org_size', 'Unknown')}
- Number of AWS accounts needed: {requirements.get('num_accounts', 'Unknown')}
- Primary workload types: {requirements.get('workload_types', 'Unknown')}
- Compliance requirements: {requirements.get('compliance', 'SOC 2')}
- Budget constraints: {requirements.get('budget', 'Not specified')}
- Existing infrastructure: {requirements.get('existing_infra', 'None')}
- Hybrid connectivity needs: {requirements.get('hybrid_connectivity', 'None')}
- Data residency requirements: {requirements.get('data_residency', 'No restrictions')}
- Expected data transfer: {requirements.get('data_transfer', 'Unknown')}
- Team AWS experience level: {requirements.get('experience_level', 'Intermediate')}

Provide a comprehensive foundation design with:
1. Account structure and OU hierarchy
2. Network architecture with diagrams (ASCII)
3. Identity and access management setup
4. Security tooling configuration
5. Logging and monitoring architecture
6. Estimated monthly costs (itemized)
7. Implementation roadmap (phases)
8. SOC 2 control coverage mapping"""

        return self.invoke_architect(prompt, category="foundation_complete", include_pricing=True)

    def recommend_pattern(
        self,
        category: str,
        question: str,
        current_state: dict[str, Any] = None
    ) -> str:
        """Get an AI-driven recommendation for a specific pattern category."""
        context = ""
        if current_state:
            context = f"\nCurrent environment state:\n{json.dumps(current_state, indent=2)}"

        prompt = f"""{question}
{context}

Consider the user's specific context and provide a tailored recommendation, not just a generic best practice."""

        return self.invoke_architect(prompt, category=category)

    def explain_tradeoffs(
        self,
        option_a: str,
        option_b: str,
        context: str = ""
    ) -> str:
        """AI-driven comparison of two architectural options."""
        prompt = f"""Compare these two AWS architecture approaches:

Option A: {option_a}
Option B: {option_b}

Context: {context if context else 'General AWS workload'}

Provide:
1. Detailed comparison table (features, costs, complexity)
2. When to choose Option A
3. When to choose Option B
4. Hybrid approaches if applicable
5. Migration path if starting with one and moving to other"""

        return self.invoke_architect(prompt, include_pricing=True)

    def answer_architecture_question(self, question: str) -> str:
        """Answer any AWS architecture question with AI + pattern context."""
        # Detect category from question
        category = self._detect_category(question)

        prompt = f"""AWS Architecture Question: {question}

Provide a thorough answer that:
1. Directly addresses the question
2. Includes specific AWS service recommendations
3. Considers security and compliance implications
4. Mentions relevant costs where applicable
5. Notes any caveats or "it depends" factors"""

        return self.invoke_architect(prompt, category=category)

    def _detect_category(self, text: str) -> Optional[str]:
        """Detect the relevant category from text."""
        text_lower = text.lower()

        category_keywords = {
            "vpc_design": ["vpc", "cidr", "subnet", "availability zone", "az", "endpoint"],
            "account_structure": ["account", "ou", "organization", "control tower", "scp"],
            "identity_access": ["iam", "identity", "permission", "role", "sso", "mfa"],
            "security_tooling": ["security hub", "guardduty", "config", "inspector", "detective"],
            "logging_monitoring": ["log", "cloudtrail", "monitoring", "cloudwatch", "siem"],
            "networking": ["nat", "transit gateway", "vpn", "direct connect", "egress", "ingress"],
            "operational": ["tag", "backup", "cost", "patch", "ssm", "systems manager"],
        }

        for category, keywords in category_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return category

        return None

    def record_feedback(
        self,
        recommendation_id: str,
        category: str,
        feedback_type: str,  # "helpful", "not_helpful", "improvement"
        feedback_text: str,
        user_id: str
    ) -> bool:
        """Record user feedback for continuous learning."""
        if not self.table:
            logger.warning("No DynamoDB table configured for feedback")
            return False

        try:
            self.table.put_item(
                Item={
                    "feedback_id": f"feedback_{datetime.utcnow().isoformat()}_{user_id}",
                    "recommendation_id": recommendation_id,
                    "category": category,
                    "feedback_type": feedback_type,
                    "feedback_text": feedback_text,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "learning": self._extract_learning(feedback_type, feedback_text) if feedback_type == "improvement" else None
                }
            )
            return True
        except Exception as e:
            logger.exception("Error recording feedback")
            return False

    def _extract_learning(self, feedback_type: str, feedback_text: str) -> str:
        """Extract a learning from feedback to improve future recommendations."""
        # Use AI to extract the key learning
        prompt = f"""Extract the key learning from this user feedback about an AWS architecture recommendation:

Feedback: {feedback_text}

Summarize in one sentence what should be remembered for future recommendations of this type."""

        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 200,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            }

            response = self.bedrock.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",  # Use Haiku for this
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except Exception:
            return feedback_text[:200]  # Fallback to truncated feedback

    def get_latest_best_practices(self, topic: str) -> str:
        """
        Query AI for the latest AWS best practices on a topic.

        The AI's training data includes AWS documentation, re:Invent talks,
        blog posts, and best practice guides up to its knowledge cutoff.
        """
        prompt = f"""What are the current AWS best practices for: {topic}

Focus on:
1. Official AWS recommendations (Well-Architected, documentation)
2. Common patterns from AWS Solutions Architects
3. Lessons learned from real-world implementations
4. Recent changes or new features that affect best practices

Be specific and cite AWS documentation or features where possible."""

        return self.invoke_architect(prompt, include_pricing=False)


# Singleton instance
_ai_architect: Optional[AIArchitect] = None


def get_ai_architect(table_name: str = None) -> AIArchitect:
    """Get or create the AI Architect singleton."""
    global _ai_architect
    if _ai_architect is None:
        _ai_architect = AIArchitect(table_name)
    return _ai_architect
