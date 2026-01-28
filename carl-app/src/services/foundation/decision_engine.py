"""
Decision Engine for CARL Foundation Builder.

Guides users through architecture decisions with AI-driven recommendations.

Hybrid approach:
- Static patterns provide structure and accurate pricing
- AI provides personalized recommendations and explanations
- Feedback loop enables continuous learning
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid
import json

from src.knowledge.architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    EGRESS_PATTERNS,
    INGRESS_PATTERNS,
    TRANSIT_PATTERNS,
    SITE_TO_SITE_VPN_PATTERNS,
    CLIENT_VPN_PATTERNS,
    get_all_patterns,
)
from src.knowledge.aws_pricing import (
    calculate_monthly_cost,
    Region,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SessionState(Enum):
    """Decision session states."""
    INITIALIZED = "initialized"
    GATHERING_REQUIREMENTS = "gathering_requirements"
    REVIEWING_DECISIONS = "reviewing_decisions"
    GENERATING_CODE = "generating_code"
    COMPLETED = "completed"


@dataclass
class RequirementInput:
    """User input for a requirement question."""
    question_id: str
    question: str
    answer: Any
    answered_at: str | None = None


@dataclass
class DecisionResult:
    """Result of an architecture decision."""
    category: str
    decision: ArchitectureDecision
    selected_option: DecisionOption
    user_confirmed: bool = False
    custom_configuration: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionSession:
    """
    Tracks a user's foundation building session.

    Maintains state across multiple Slack interactions.
    """
    session_id: str
    user_id: str
    channel_id: str
    state: SessionState

    # Collected requirements
    requirements: dict[str, Any] = field(default_factory=dict)
    requirement_inputs: list[RequirementInput] = field(default_factory=list)

    # Decisions made
    decisions: list[DecisionResult] = field(default_factory=list)

    # Current position in workflow
    current_phase: str = "requirements"
    current_question_index: int = 0

    # Configuration options
    region: Region = Region.US_EAST_1
    scale_tier: str = "startup"  # startup, growth, enterprise

    # Generated outputs
    estimated_monthly_cost: float = 0.0
    terraform_modules: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, user_id: str, channel_id: str) -> "DecisionSession":
        """Create a new decision session."""
        return cls(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            channel_id=channel_id,
            state=SessionState.INITIALIZED,
        )


# =============================================================================
# REQUIREMENT QUESTIONS
# =============================================================================

REQUIREMENT_QUESTIONS = [
    {
        "id": "organization_scale",
        "question": "What is the scale of your AWS deployment?",
        "description": "This helps determine the complexity of networking and management.",
        "options": [
            {
                "value": "startup",
                "label": "Startup (1-5 accounts, <10 VPCs)",
                "description": "Early stage, simplicity preferred, cost-conscious",
            },
            {
                "value": "growth",
                "label": "Growth (5-20 accounts, 10-50 VPCs)",
                "description": "Scaling team, some standardization needed",
            },
            {
                "value": "enterprise",
                "label": "Enterprise (20-100+ accounts, 50+ VPCs)",
                "description": "Large org, strict compliance, centralized management",
            },
        ],
        "default": "startup",
    },
    {
        "id": "vpc_count",
        "question": "How many VPCs do you currently have or plan to have?",
        "description": "Determines transit architecture (peering vs TGW vs Cloud WAN)",
        "input_type": "number",
        "min": 1,
        "max": 100,
        "default": 1,
    },
    {
        "id": "multi_region",
        "question": "Will you deploy across multiple AWS regions?",
        "description": "Affects transit architecture and disaster recovery planning",
        "options": [
            {
                "value": "single_region",
                "label": "Single region",
                "description": "All workloads in one region",
            },
            {
                "value": "multi_region_simple",
                "label": "Multi-region (simple)",
                "description": "2-3 regions, limited inter-region traffic",
            },
            {
                "value": "multi_region_complex",
                "label": "Multi-region (complex)",
                "description": "Global deployment, significant inter-region traffic",
            },
        ],
        "default": "single_region",
    },
    {
        "id": "compliance_requirements",
        "question": "What compliance frameworks apply to your environment?",
        "description": "Determines security controls and inspection requirements",
        "multi_select": True,
        "options": [
            {"value": "soc2", "label": "SOC 2"},
            {"value": "hipaa", "label": "HIPAA"},
            {"value": "pci_dss", "label": "PCI-DSS"},
            {"value": "cis", "label": "CIS Benchmarks"},
            {"value": "fedramp", "label": "FedRAMP"},
            {"value": "none", "label": "No specific framework (best practices)"},
        ],
        "default": ["soc2"],
    },
    {
        "id": "traffic_inspection",
        "question": "Do you need to inspect egress (outbound) traffic?",
        "description": "Some compliance frameworks require traffic inspection/logging",
        "options": [
            {
                "value": "no",
                "label": "No inspection needed",
                "description": "Basic NAT for outbound access, VPC Flow Logs only",
            },
            {
                "value": "logging_only",
                "label": "Logging only",
                "description": "Centralized logging but no active inspection",
            },
            {
                "value": "full_inspection",
                "label": "Full inspection (IDS/IPS)",
                "description": "AWS Network Firewall with domain/IP filtering",
            },
        ],
        "default": "no",
    },
    {
        "id": "on_premises",
        "question": "Do you need to connect to on-premises data centers?",
        "description": "Determines VPN or Direct Connect requirements",
        "options": [
            {
                "value": "none",
                "label": "No on-premises connectivity",
                "description": "Cloud-native, no hybrid connection",
            },
            {
                "value": "vpn_only",
                "label": "VPN (< 1 Gbps, variable latency OK)",
                "description": "Site-to-site VPN over internet",
            },
            {
                "value": "direct_connect",
                "label": "Direct Connect (high bandwidth, consistent latency)",
                "description": "Dedicated connection, typically 1-10 Gbps",
            },
            {
                "value": "both",
                "label": "Direct Connect + VPN backup",
                "description": "DX primary with VPN for redundancy",
            },
        ],
        "default": "none",
    },
    {
        "id": "remote_users",
        "question": "Do remote users need VPN access to AWS resources?",
        "description": "Determines client VPN architecture",
        "options": [
            {
                "value": "none",
                "label": "No client VPN needed",
                "description": "All access via public endpoints or SSO apps",
            },
            {
                "value": "small",
                "label": "Small team (< 20 users)",
                "description": "AWS Client VPN is cost-effective",
            },
            {
                "value": "medium",
                "label": "Medium team (20-100 users)",
                "description": "Consider cost comparison of options",
            },
            {
                "value": "large",
                "label": "Large team (100+ users)",
                "description": "Self-managed or enterprise solution may be cheaper",
            },
        ],
        "default": "none",
    },
    {
        "id": "public_applications",
        "question": "Will you host public-facing applications?",
        "description": "Determines ingress architecture and WAF requirements",
        "options": [
            {
                "value": "none",
                "label": "No public applications",
                "description": "Internal workloads only",
            },
            {
                "value": "single_region",
                "label": "Public apps (single region users)",
                "description": "ALB + WAF, no CDN needed",
            },
            {
                "value": "global",
                "label": "Public apps (global users)",
                "description": "CloudFront + WAF at edge recommended",
            },
        ],
        "default": "none",
    },
    {
        "id": "landing_zone",
        "question": "Do you need a landing zone / account factory?",
        "description": "For multi-account governance and automated account provisioning",
        "options": [
            {
                "value": "none",
                "label": "No (single account or manual management)",
                "description": "Managing accounts individually",
            },
            {
                "value": "control_tower",
                "label": "AWS Control Tower",
                "description": "AWS-managed landing zone with guardrails",
            },
            {
                "value": "control_tower_aft",
                "label": "Control Tower + AFT",
                "description": "Automated account vending with Terraform",
            },
            {
                "value": "custom",
                "label": "Custom landing zone",
                "description": "Custom Organizations + Terraform (advanced)",
            },
        ],
        "default": "none",
    },
    {
        "id": "monthly_budget",
        "question": "What's your approximate monthly budget for infrastructure?",
        "description": "Helps calibrate recommendations (not a hard limit)",
        "options": [
            {
                "value": "minimal",
                "label": "Minimal (< $500/mo)",
                "description": "Cost-optimized, simpler architecture",
            },
            {
                "value": "moderate",
                "label": "Moderate ($500 - $2000/mo)",
                "description": "Balance of cost and features",
            },
            {
                "value": "substantial",
                "label": "Substantial ($2000 - $10000/mo)",
                "description": "Can invest in enterprise features",
            },
            {
                "value": "enterprise",
                "label": "Enterprise (> $10000/mo)",
                "description": "Full featured, compliance-first",
            },
        ],
        "default": "minimal",
    },
]


class DecisionEngine:
    """
    Engine for guiding users through architecture decisions.

    Uses AI (Bedrock/Claude) for personalized recommendations while
    maintaining accurate pricing from static data.

    Hybrid approach:
    - AI generates the recommendation logic and explanations
    - Static patterns provide structure and accurate pricing
    - User feedback improves future recommendations
    """

    def __init__(self, use_ai: bool = True, feedback_table: str = None):
        self.patterns = get_all_patterns()
        self.sessions: dict[str, DecisionSession] = {}
        self.use_ai = use_ai
        self.feedback_table = feedback_table
        self._ai_architect = None

    @property
    def ai_architect(self):
        """Lazy load AI architect to avoid circular imports."""
        if self._ai_architect is None and self.use_ai:
            try:
                from src.services.ai_architect import get_ai_architect
                self._ai_architect = get_ai_architect(self.feedback_table)
            except Exception as e:
                logger.warning(f"Could not initialize AI Architect: {e}")
                self.use_ai = False
        return self._ai_architect

    def create_session(self, user_id: str, channel_id: str) -> DecisionSession:
        """Create a new decision session."""
        session = DecisionSession.create(user_id, channel_id)
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> DecisionSession | None:
        """Get an existing session."""
        return self.sessions.get(session_id)

    def get_user_session(self, user_id: str, channel_id: str) -> DecisionSession | None:
        """Get active session for a user in a channel."""
        for session in self.sessions.values():
            if (
                session.user_id == user_id
                and session.channel_id == channel_id
                and session.state != SessionState.COMPLETED
            ):
                return session
        return None

    def get_next_question(self, session: DecisionSession) -> dict | None:
        """Get the next requirement question for a session."""
        if session.current_phase != "requirements":
            return None

        if session.current_question_index >= len(REQUIREMENT_QUESTIONS):
            return None

        return REQUIREMENT_QUESTIONS[session.current_question_index]

    def process_answer(
        self,
        session: DecisionSession,
        question_id: str,
        answer: Any,
    ) -> dict:
        """
        Process a user's answer to a requirement question.

        Returns the next action (next_question, show_summary, etc.)
        """
        # Store the answer
        session.requirements[question_id] = answer
        session.requirement_inputs.append(RequirementInput(
            question_id=question_id,
            question=REQUIREMENT_QUESTIONS[session.current_question_index]["question"],
            answer=answer,
        ))

        # Move to next question
        session.current_question_index += 1

        # Check if we have all requirements
        if session.current_question_index >= len(REQUIREMENT_QUESTIONS):
            session.current_phase = "decisions"
            session.state = SessionState.REVIEWING_DECISIONS

            # Generate recommendations based on requirements
            self._generate_recommendations(session)

            return {
                "action": "show_recommendations",
                "session": session,
            }

        # Return next question
        next_q = REQUIREMENT_QUESTIONS[session.current_question_index]
        return {
            "action": "ask_question",
            "question": next_q,
            "progress": f"{session.current_question_index + 1}/{len(REQUIREMENT_QUESTIONS)}",
        }

    def _generate_recommendations(self, session: DecisionSession) -> None:
        """Generate architecture recommendations based on requirements."""
        req = session.requirements

        # Try AI-driven recommendations first
        if self.use_ai and self.ai_architect:
            try:
                self._generate_ai_recommendations(session)
                return
            except Exception as e:
                logger.warning(f"AI recommendation failed, falling back to static: {e}")

        # Fallback to static rule-based recommendations
        self._generate_static_recommendations(session)

    def _generate_ai_recommendations(self, session: DecisionSession) -> None:
        """Generate recommendations using AI with pattern context."""
        req = session.requirements

        # Get AI recommendation for the complete foundation
        ai_response = self.ai_architect.recommend_foundation(req)

        # Store AI explanation in session for later use
        session.requirements["_ai_explanation"] = ai_response

        # Still use static patterns for structured output + accurate pricing
        # But let AI influence the selections based on its analysis
        ai_selections = self._parse_ai_selections(ai_response, req)

        # Egress
        egress_option = ai_selections.get("egress") or self._recommend_egress(req)
        session.decisions.append(DecisionResult(
            category="egress",
            decision=EGRESS_PATTERNS,
            selected_option=egress_option,
        ))

        # Transit (if multiple VPCs)
        vpc_count = req.get("vpc_count", 1)
        if vpc_count > 1:
            transit_option = ai_selections.get("transit") or self._recommend_transit(req)
            session.decisions.append(DecisionResult(
                category="transit",
                decision=TRANSIT_PATTERNS,
                selected_option=transit_option,
            ))

        # Ingress (if public apps)
        if req.get("public_applications") != "none":
            ingress_option = ai_selections.get("ingress") or self._recommend_ingress(req)
            session.decisions.append(DecisionResult(
                category="ingress",
                decision=INGRESS_PATTERNS,
                selected_option=ingress_option,
            ))

        # Site-to-Site VPN (if on-premises)
        if req.get("on_premises") in ["vpn_only", "direct_connect", "both"]:
            vpn_option = ai_selections.get("site_vpn") or self._recommend_site_vpn(req)
            session.decisions.append(DecisionResult(
                category="site_to_site_vpn",
                decision=SITE_TO_SITE_VPN_PATTERNS,
                selected_option=vpn_option,
            ))

        # Client VPN (if remote users)
        if req.get("remote_users") != "none":
            client_vpn_option = ai_selections.get("client_vpn") or self._recommend_client_vpn(req)
            session.decisions.append(DecisionResult(
                category="client_vpn",
                decision=CLIENT_VPN_PATTERNS,
                selected_option=client_vpn_option,
            ))

        self._calculate_total_cost(session)

    def _parse_ai_selections(self, ai_response: str, req: dict) -> dict[str, DecisionOption]:
        """Parse AI response to extract recommended options."""
        selections = {}
        ai_lower = ai_response.lower()

        # Map AI keywords to pattern options
        egress_mappings = {
            "network firewall": EGRESS_PATTERNS.options[2],
            "centralized nat": EGRESS_PATTERNS.options[1],
            "distributed nat": EGRESS_PATTERNS.options[0],
        }

        transit_mappings = {
            "cloud wan": TRANSIT_PATTERNS.options[3],
            "transit gateway": TRANSIT_PATTERNS.options[2],
            "vpc peering": TRANSIT_PATTERNS.options[1],
        }

        ingress_mappings = {
            "cloudfront": INGRESS_PATTERNS.options[2],
            "centralized ingress": INGRESS_PATTERNS.options[1],
            "distributed alb": INGRESS_PATTERNS.options[0],
        }

        vpn_mappings = {
            "direct connect": SITE_TO_SITE_VPN_PATTERNS.options[2],
            "accelerated vpn": SITE_TO_SITE_VPN_PATTERNS.options[1],
            "site-to-site vpn": SITE_TO_SITE_VPN_PATTERNS.options[0],
        }

        client_vpn_mappings = {
            "self-managed": CLIENT_VPN_PATTERNS.options[1],
            "aws client vpn": CLIENT_VPN_PATTERNS.options[0],
        }

        # Simple keyword matching (AI response should mention these)
        for keyword, option in egress_mappings.items():
            if keyword in ai_lower:
                selections["egress"] = option
                break

        for keyword, option in transit_mappings.items():
            if keyword in ai_lower:
                selections["transit"] = option
                break

        for keyword, option in ingress_mappings.items():
            if keyword in ai_lower:
                selections["ingress"] = option
                break

        for keyword, option in vpn_mappings.items():
            if keyword in ai_lower:
                selections["site_vpn"] = option
                break

        for keyword, option in client_vpn_mappings.items():
            if keyword in ai_lower:
                selections["client_vpn"] = option
                break

        return selections

    def _generate_static_recommendations(self, session: DecisionSession) -> None:
        """Generate recommendations using static rule-based logic (fallback)."""
        req = session.requirements

        # Egress recommendation
        egress_option = self._recommend_egress(req)
        session.decisions.append(DecisionResult(
            category="egress",
            decision=EGRESS_PATTERNS,
            selected_option=egress_option,
        ))

        # Transit recommendation (if multiple VPCs)
        vpc_count = req.get("vpc_count", 1)
        if vpc_count > 1:
            transit_option = self._recommend_transit(req)
            session.decisions.append(DecisionResult(
                category="transit",
                decision=TRANSIT_PATTERNS,
                selected_option=transit_option,
            ))

        # Ingress recommendation (if public apps)
        if req.get("public_applications") != "none":
            ingress_option = self._recommend_ingress(req)
            session.decisions.append(DecisionResult(
                category="ingress",
                decision=INGRESS_PATTERNS,
                selected_option=ingress_option,
            ))

        # Site-to-Site VPN (if on-premises)
        if req.get("on_premises") in ["vpn_only", "direct_connect", "both"]:
            vpn_option = self._recommend_site_vpn(req)
            session.decisions.append(DecisionResult(
                category="site_to_site_vpn",
                decision=SITE_TO_SITE_VPN_PATTERNS,
                selected_option=vpn_option,
            ))

        # Client VPN (if remote users)
        if req.get("remote_users") != "none":
            client_vpn_option = self._recommend_client_vpn(req)
            session.decisions.append(DecisionResult(
                category="client_vpn",
                decision=CLIENT_VPN_PATTERNS,
                selected_option=client_vpn_option,
            ))

        # Calculate total estimated cost
        self._calculate_total_cost(session)

    def get_ai_explanation(self, session: DecisionSession, decision_index: int) -> str:
        """Get AI-powered detailed explanation for a specific decision."""
        if decision_index >= len(session.decisions):
            return "Invalid decision index."

        decision = session.decisions[decision_index]

        if self.use_ai and self.ai_architect:
            try:
                prompt = f"""Explain this architecture decision in detail:

Category: {decision.category}
Selected Option: {decision.selected_option.name}
Description: {decision.selected_option.description}

User's Requirements:
{json.dumps({k: v for k, v in session.requirements.items() if not k.startswith('_')}, indent=2)}

Provide:
1. Why this option was recommended for their specific situation
2. How it addresses their compliance requirements
3. Cost optimization tips
4. Implementation considerations
5. Common pitfalls to avoid"""

                return self.ai_architect.invoke_architect(prompt, category=decision.category)
            except Exception as e:
                logger.warning(f"AI explanation failed: {e}")

        # Fallback to static explanation
        return self.format_decision_detail(decision)

    def compare_alternatives(self, session: DecisionSession, decision_index: int) -> str:
        """Get AI-powered comparison of alternatives."""
        if decision_index >= len(session.decisions):
            return "Invalid decision index."

        decision = session.decisions[decision_index]

        if self.use_ai and self.ai_architect:
            try:
                options_list = "\n".join([
                    f"- {opt.name}: {opt.description}"
                    for opt in decision.decision.options
                ])

                prompt = f"""Compare these architecture options for {decision.category}:

{options_list}

User's context:
- Scale: {session.requirements.get('organization_scale', 'unknown')}
- VPCs: {session.requirements.get('vpc_count', 1)}
- Budget: {session.requirements.get('monthly_budget', 'unknown')}
- Compliance: {session.requirements.get('compliance_requirements', [])}

Currently selected: {decision.selected_option.name}

Provide a detailed comparison including:
1. Feature comparison table
2. Cost comparison at different scales
3. When each option is the best choice
4. Migration path if needs change later"""

                return self.ai_architect.invoke_architect(prompt, category=decision.category)
            except Exception as e:
                logger.warning(f"AI comparison failed: {e}")

        # Fallback to static alternatives
        return self.format_alternatives(decision)

    def record_decision_feedback(
        self,
        session: DecisionSession,
        decision_index: int,
        feedback_type: str,
        feedback_text: str
    ) -> bool:
        """Record user feedback on a decision for learning."""
        if not self.ai_architect or decision_index >= len(session.decisions):
            return False

        decision = session.decisions[decision_index]

        try:
            return self.ai_architect.record_feedback(
                recommendation_id=f"{session.session_id}_{decision_index}",
                category=decision.category,
                feedback_type=feedback_type,
                feedback_text=feedback_text,
                user_id=session.user_id
            )
        except Exception as e:
            logger.warning(f"Could not record feedback: {e}")
            return False

    def _recommend_egress(self, req: dict) -> DecisionOption:
        """Recommend egress architecture."""
        vpc_count = req.get("vpc_count", 1)
        inspection = req.get("traffic_inspection", "no")

        if inspection == "full_inspection":
            return EGRESS_PATTERNS.options[2]  # Network Firewall
        elif vpc_count <= 3:
            return EGRESS_PATTERNS.options[0]  # Distributed NAT
        else:
            return EGRESS_PATTERNS.options[1]  # Centralized NAT

    def _recommend_transit(self, req: dict) -> DecisionOption:
        """Recommend transit architecture."""
        vpc_count = req.get("vpc_count", 1)
        multi_region = req.get("multi_region", "single_region")

        if multi_region == "multi_region_complex":
            return TRANSIT_PATTERNS.options[3]  # Cloud WAN
        elif vpc_count <= 4:
            return TRANSIT_PATTERNS.options[1]  # VPC Peering
        else:
            return TRANSIT_PATTERNS.options[2]  # Transit Gateway

    def _recommend_ingress(self, req: dict) -> DecisionOption:
        """Recommend ingress architecture."""
        public_apps = req.get("public_applications", "none")
        vpc_count = req.get("vpc_count", 1)

        if public_apps == "global":
            return INGRESS_PATTERNS.options[2]  # CloudFront + WAF
        elif vpc_count > 5:
            return INGRESS_PATTERNS.options[1]  # Centralized Ingress
        else:
            return INGRESS_PATTERNS.options[0]  # Distributed ALB

    def _recommend_site_vpn(self, req: dict) -> DecisionOption:
        """Recommend site-to-site connectivity."""
        on_prem = req.get("on_premises", "none")

        if on_prem == "direct_connect" or on_prem == "both":
            return SITE_TO_SITE_VPN_PATTERNS.options[2]  # Direct Connect
        else:
            return SITE_TO_SITE_VPN_PATTERNS.options[0]  # Standard VPN

    def _recommend_client_vpn(self, req: dict) -> DecisionOption:
        """Recommend client VPN architecture."""
        remote_users = req.get("remote_users", "none")

        if remote_users == "large":
            return CLIENT_VPN_PATTERNS.options[1]  # Self-managed (cheaper at scale)
        else:
            return CLIENT_VPN_PATTERNS.options[0]  # AWS Client VPN

    def _calculate_total_cost(self, session: DecisionSession) -> None:
        """Calculate total estimated monthly cost."""
        total = 0.0

        for decision in session.decisions:
            cost_range = decision.selected_option.monthly_cost_range
            # Use midpoint of range as estimate
            total += (cost_range[0] + cost_range[1]) / 2

        session.estimated_monthly_cost = total

    def format_recommendations_message(self, session: DecisionSession) -> str:
        """Format recommendations as a Slack message."""
        lines = [
            "*Foundation Architecture Recommendations*",
            "",
            f"Based on your requirements, here are CARL's recommendations:",
            "",
        ]

        for i, decision in enumerate(session.decisions, 1):
            opt = decision.selected_option
            lines.extend([
                f"*{i}. {decision.category.replace('_', ' ').title()}*",
                f"   Recommendation: *{opt.name}*",
                f"   {opt.description}",
                "",
                f"   _Pros:_",
            ])
            for pro in opt.pros[:3]:
                lines.append(f"   • {pro}")

            lines.append(f"   _Cons:_")
            for con in opt.cons[:3]:
                lines.append(f"   • {con}")

            lines.extend([
                "",
                f"   _Est. Monthly Cost:_ ${opt.monthly_cost_range[0]:.0f} - ${opt.monthly_cost_range[1]:.0f}",
                f"   _SOC 2 Controls:_ {', '.join(opt.soc2_controls)}",
                "",
            ])

        lines.extend([
            "---",
            f"*Total Estimated Monthly Cost:* ${session.estimated_monthly_cost:.0f}",
            "",
            "_Reply with:_",
            "• `accept` - Generate Terraform code for these recommendations",
            "• `change <number>` - See alternatives for a specific decision",
            "• `explain <number>` - Get detailed explanation for a decision",
            "• `cancel` - Cancel this session",
        ])

        return "\n".join(lines)

    def format_decision_detail(self, decision: DecisionResult) -> str:
        """Format detailed decision information."""
        opt = decision.selected_option
        dec = decision.decision

        lines = [
            f"*{decision.category.replace('_', ' ').title()}*",
            "",
            f"*Selected: {opt.name}*",
            opt.description,
            "",
            "*When to use:*",
        ]
        for item in opt.when_to_use:
            lines.append(f"• {item}")

        lines.append("\n*When NOT to use:*")
        for item in opt.when_not_to_use:
            lines.append(f"• {item}")

        lines.extend([
            "",
            "*Full Pros:*",
        ])
        for pro in opt.pros:
            lines.append(f"• {pro}")

        lines.append("\n*Full Cons:*")
        for con in opt.cons:
            lines.append(f"• {con}")

        lines.extend([
            "",
            "*Cost Breakdown:*",
        ])
        for driver in opt.cost_drivers:
            lines.append(f"• {driver}")

        lines.extend([
            "",
            f"*Implementation Complexity:* {opt.implementation_complexity}",
            f"*Operational Overhead:* {opt.operational_overhead}",
            "",
            "*Decision Logic:*",
            dec.recommendation_logic.strip(),
            "",
            "*Common Mistakes to Avoid:*",
        ])
        for mistake in dec.common_mistakes:
            lines.append(f"• {mistake}")

        return "\n".join(lines)

    def format_alternatives(self, decision: DecisionResult) -> str:
        """Format alternative options for a decision."""
        lines = [
            f"*Alternative Options for {decision.category.replace('_', ' ').title()}*",
            "",
            f"_Current selection:_ *{decision.selected_option.name}*",
            "",
            "*Available alternatives:*",
            "",
        ]

        for i, opt in enumerate(decision.decision.options, 1):
            is_selected = opt.name == decision.selected_option.name
            marker = "✓" if is_selected else " "

            lines.extend([
                f"*{i}. {opt.name}* {marker}",
                f"   {opt.description}",
                f"   Cost: ${opt.monthly_cost_range[0]:.0f} - ${opt.monthly_cost_range[1]:.0f}/mo",
                f"   Complexity: {opt.implementation_complexity}",
                "",
            ])

        lines.extend([
            "---",
            "_Reply with `select <number>` to change your selection_",
        ])

        return "\n".join(lines)
