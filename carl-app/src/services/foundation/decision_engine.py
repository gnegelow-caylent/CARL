"""
Decision Engine for CARL Foundation Builder.

Guides users through architecture decisions with AI-driven recommendations.

Hybrid approach:
- Static patterns provide structure and accurate pricing
- AI provides personalized recommendations and explanations
- Feedback loop enables continuous learning
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timedelta
import uuid
import json
import os
import boto3

from knowledge.architecture_patterns import (
    ArchitectureDecision,
    DecisionOption,
    EGRESS_PATTERNS,
    INGRESS_PATTERNS,
    TRANSIT_PATTERNS,
    SITE_TO_SITE_VPN_PATTERNS,
    CLIENT_VPN_PATTERNS,
    get_all_patterns,
)
from knowledge.aws_pricing import (
    calculate_monthly_cost,
    Region,
)
from services.framework_loader import ComplianceFramework, get_framework_loader
from services.framework_gap_analyzer import (
    FrameworkGapAnalysis,
    ComplianceGap,
    GapStatus,
    get_gap_analyzer
)
from utils.logger import get_logger

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

    # Framework-aware additions
    compliance_controls: list[str] = field(default_factory=list)  # e.g., ["CC7.2", "A1.3"]
    why_required: str = ""  # Business explanation from framework
    audit_evidence: list[str] = field(default_factory=list)  # What auditors check
    gap_status: Optional[str] = None  # "missing", "misconfigured", or None for pattern-based


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

    # Framework-aware additions (NEW)
    framework: Optional[ComplianceFramework] = None  # Selected compliance framework
    gap_analysis: Optional[FrameworkGapAnalysis] = None  # Gap analysis results
    framework_mode: bool = False  # True if using framework-driven flow

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

    def __init__(self, use_ai: bool = True, feedback_table: str = None, foundation_table: str = None):
        self.patterns = get_all_patterns()
        self.sessions: dict[str, DecisionSession] = {}  # In-memory cache
        self.use_ai = use_ai
        self.feedback_table = feedback_table
        self.foundation_table = foundation_table or os.environ.get("FOUNDATION_TABLE", "carl-dev-foundation")
        self._ai_architect = None
        self._dynamodb = None

    @property
    def dynamodb(self):
        """Lazy load DynamoDB client."""
        if self._dynamodb is None:
            self._dynamodb = boto3.resource('dynamodb')
        return self._dynamodb

    @property
    def ai_architect(self):
        """Lazy load AI architect to avoid circular imports."""
        if self._ai_architect is None and self.use_ai:
            try:
                from services.ai_architect import get_ai_architect
                self._ai_architect = get_ai_architect(self.feedback_table)
            except Exception as e:
                logger.warning(f"Could not initialize AI Architect: {e}")
                self.use_ai = False
        return self._ai_architect

    def _save_session_to_dynamodb(self, session: DecisionSession):
        """Persist session to DynamoDB."""
        try:
            table = self.dynamodb.Table(self.foundation_table)

            # Convert session to dict (handle complex types)
            session_dict = {
                'session_id': session.session_id,
                'user_id': session.user_id,
                'channel_id': session.channel_id,
                'state': session.state.value,
                'requirements': session.requirements,
                'current_phase': session.current_phase,
                'current_question_index': session.current_question_index,
                'region': session.region.value if hasattr(session.region, 'value') else str(session.region),
                'scale_tier': session.scale_tier,
                'estimated_monthly_cost': session.estimated_monthly_cost,
                'framework_mode': session.framework_mode,
            }

            # Serialize requirement_inputs (list of RequirementInput dataclass objects)
            if session.requirement_inputs:
                session_dict['requirement_inputs'] = [
                    {
                        'question_id': ri.question_id,
                        'question': ri.question,
                        'answer': ri.answer,
                        'answered_at': ri.answered_at
                    }
                    for ri in session.requirement_inputs
                ]

            # Serialize decisions (list of DecisionResult dataclass objects)
            if session.decisions:
                session_dict['decisions'] = [
                    {
                        'category': d.category,
                        'selected_option_name': d.selected_option.name if d.selected_option else None,
                        'user_confirmed': d.user_confirmed,
                        'custom_configuration': d.custom_configuration,
                        'compliance_controls': d.compliance_controls,
                        'why_required': d.why_required,
                        'audit_evidence': d.audit_evidence,
                        'gap_status': d.gap_status,
                    }
                    for d in session.decisions
                ]

            # Store framework and gap analysis IDs (not full objects)
            if session.framework:
                session_dict['framework_id'] = session.framework.id
            if session.gap_analysis:
                session_dict['gap_analysis_compliance'] = session.gap_analysis.compliance_percentage
                session_dict['gap_analysis_missing'] = session.gap_analysis.missing_count
                session_dict['gap_analysis_misconfigured'] = session.gap_analysis.misconfigured_count

            table.put_item(
                Item={
                    'pk': f'SESSION#{session.session_id}',
                    'sk': 'METADATA',
                    'data': json.dumps(session_dict),
                    'ttl': int((datetime.now() + timedelta(hours=24)).timestamp()),  # 24 hour expiry
                }
            )
            logger.info(f"Saved session {session.session_id} to DynamoDB")
        except Exception as e:
            logger.error(f"Failed to save session to DynamoDB: {e}", exc_info=True)

    def _load_session_from_dynamodb(self, session_id: str) -> DecisionSession | None:
        """Load session from DynamoDB."""
        try:
            table = self.dynamodb.Table(self.foundation_table)
            response = table.get_item(
                Key={
                    'pk': f'SESSION#{session_id}',
                    'sk': 'METADATA'
                }
            )

            if 'Item' not in response:
                return None

            session_data = json.loads(response['Item']['data'])

            # Reconstruct session
            session = DecisionSession(
                session_id=session_data['session_id'],
                user_id=session_data['user_id'],
                channel_id=session_data['channel_id'],
                state=SessionState(session_data['state']),
                requirements=session_data.get('requirements', {}),
                current_phase=session_data.get('current_phase', 'requirements'),
                current_question_index=session_data.get('current_question_index', 0),
                scale_tier=session_data.get('scale_tier', 'startup'),
                estimated_monthly_cost=session_data.get('estimated_monthly_cost', 0.0),
                framework_mode=session_data.get('framework_mode', False),
            )

            # Deserialize requirement_inputs
            if 'requirement_inputs' in session_data:
                session.requirement_inputs = [
                    RequirementInput(
                        question_id=ri['question_id'],
                        question=ri['question'],
                        answer=ri['answer'],
                        answered_at=ri.get('answered_at')
                    )
                    for ri in session_data['requirement_inputs']
                ]

            # Deserialize decisions (simplified - won't fully reconstruct DecisionResult objects)
            # This is OK because decisions are only needed for code generation at the end
            if 'decisions' in session_data:
                session.decisions = []  # Will be regenerated if needed

            # Reload framework if needed
            if 'framework_id' in session_data:
                try:
                    loader = get_framework_loader()
                    session.framework = loader.load(session_data['framework_id'])
                except Exception as e:
                    logger.warning(f"Could not reload framework: {e}")

            logger.info(f"Loaded session {session_id} from DynamoDB")
            return session

        except Exception as e:
            logger.error(f"Failed to load session from DynamoDB: {e}", exc_info=True)
            return None

    def create_session(self, user_id: str, channel_id: str) -> DecisionSession:
        """Create a new decision session."""
        session = DecisionSession.create(user_id, channel_id)
        self.sessions[session.session_id] = session
        self._save_session_to_dynamodb(session)
        return session

    def get_session(self, session_id: str) -> DecisionSession | None:
        """Get an existing session (from memory or DynamoDB)."""
        # Check memory cache first
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Load from DynamoDB
        session = self._load_session_from_dynamodb(session_id)
        if session:
            self.sessions[session_id] = session  # Cache it
        return session

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

    def create_framework_session(
        self,
        user_id: str,
        channel_id: str,
        framework_id: str,
        account_id: str = "unknown",
        region: str = "us-east-1"
    ) -> tuple[DecisionSession, FrameworkGapAnalysis]:
        """
        Create a new framework-driven session (NEW).

        Loads framework, scans AWS environment, performs gap analysis.

        Returns:
            (session, gap_analysis) tuple
        """
        logger.info(f"Creating framework session for {framework_id}")

        # Load framework
        loader = get_framework_loader()
        framework = loader.load(framework_id)

        # Create session
        session = DecisionSession.create(user_id, channel_id)
        session.framework = framework
        session.framework_mode = True
        session.state = SessionState.GATHERING_REQUIREMENTS

        # Scan AWS environment and perform gap analysis
        analyzer = get_gap_analyzer()
        gap_analysis = analyzer.analyze(framework, account_id, region)
        session.gap_analysis = gap_analysis

        # Store session (memory + DynamoDB)
        self.sessions[session.session_id] = session
        self._save_session_to_dynamodb(session)

        logger.info(
            f"Framework session created: {framework.name}, "
            f"{gap_analysis.compliance_percentage:.1f}% compliant, "
            f"{gap_analysis.missing_count} missing, "
            f"{gap_analysis.misconfigured_count} misconfigured"
        )

        return session, gap_analysis

    def get_next_question(self, session: DecisionSession) -> tuple[dict | None, int]:
        """
        Get the next requirement question for a session.

        Returns:
            (question_dict, new_index) tuple
            - question_dict: The question to show (or None if done)
            - new_index: The index after skipping dependencies
        """
        if session.current_phase != "requirements":
            return None, session.current_question_index

        # Framework mode: Use framework-defined questions
        if session.framework_mode and session.framework:
            questions = session.framework.questions

            # Find next question that meets dependency requirements
            index = session.current_question_index
            while index < len(questions):
                fw_q = questions[index]

                # Check if question depends on a previous answer
                if fw_q.depends_on:
                    # depends_on format: {"multi_region": "multi"}
                    # Check if ALL dependencies are satisfied
                    dependencies_met = True
                    for dep_key, dep_value in fw_q.depends_on.items():
                        user_answer = session.requirements.get(dep_key)
                        if user_answer != dep_value:
                            dependencies_met = False
                            break

                    if not dependencies_met:
                        # Skip this question, move to next
                        index += 1
                        continue

                # Dependencies met (or no dependencies), return this question
                return {
                    "id": fw_q.id,
                    "question": fw_q.question,
                    "description": fw_q.description,
                    "input_type": fw_q.input_type,
                    "options": fw_q.options,
                    "default": fw_q.default,
                    "required": fw_q.required,
                    "depends_on": fw_q.depends_on,
                    "validation": fw_q.validation,
                    "min": fw_q.min,
                    "max": fw_q.max
                }, index

            # Reached end of questions
            return None, index

        # Original pattern mode: Use static REQUIREMENT_QUESTIONS
        if session.current_question_index >= len(REQUIREMENT_QUESTIONS):
            return None, session.current_question_index

        return REQUIREMENT_QUESTIONS[session.current_question_index], session.current_question_index

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
        # Determine which question list to use
        if session.framework_mode and session.framework:
            questions = session.framework.questions
            current_q_text = questions[session.current_question_index].question
            total_questions = len(questions)
        else:
            questions = REQUIREMENT_QUESTIONS
            current_q_text = REQUIREMENT_QUESTIONS[session.current_question_index]["question"]
            total_questions = len(REQUIREMENT_QUESTIONS)

        # Store the answer
        session.requirements[question_id] = answer
        session.requirement_inputs.append(RequirementInput(
            question_id=question_id,
            question=current_q_text,
            answer=answer,
        ))

        # Move to next question
        session.current_question_index += 1

        # Check if we have all requirements
        if session.current_question_index >= total_questions:
            session.current_phase = "decisions"
            session.state = SessionState.REVIEWING_DECISIONS

            # Generate recommendations based on requirements
            self._generate_recommendations(session)

            # Save session after generating recommendations
            self._save_session_to_dynamodb(session)

            return {
                "action": "show_recommendations",
                "session": session,
            }

        # Get next question (returns question and updated index after skips)
        next_q, new_index = self.get_next_question(session)

        # Update index to account for skipped questions
        session.current_question_index = new_index

        # Save updated session to DynamoDB (captures skipped questions)
        self._save_session_to_dynamodb(session)

        if not next_q:
            # All questions answered or skipped
            session.current_phase = "decisions"
            session.state = SessionState.REVIEWING_DECISIONS
            self._generate_recommendations(session)
            self._save_session_to_dynamodb(session)

            return {
                "action": "show_recommendations",
                "session": session,
            }

        return {
            "action": "ask_question",
            "question": next_q,
            "progress": f"{session.current_question_index + 1}/{total_questions}",
        }

    def _generate_recommendations(self, session: DecisionSession) -> None:
        """Generate architecture recommendations based on requirements."""
        req = session.requirements

        # NEW: Framework-driven flow (compliance-first)
        if session.framework_mode and session.framework:
            logger.info(f"Using framework-driven flow for {session.framework.name}")
            self._generate_framework_recommendations(session)
            return

        # Original pattern-based flow
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

    def _generate_framework_recommendations(self, session: DecisionSession) -> None:
        """
        Generate recommendations from framework gap analysis (NEW).

        This is the compliance-first flow where framework requirements
        dictate what services are needed.
        """
        if not session.framework or not session.gap_analysis:
            logger.error("Framework mode enabled but framework/gap_analysis missing")
            # Fallback to static recommendations
            self._generate_static_recommendations(session)
            return

        logger.info(
            f"Generating recommendations from {session.framework.name} gap analysis: "
            f"{session.gap_analysis.missing_count} missing, "
            f"{session.gap_analysis.misconfigured_count} misconfigured"
        )

        # Create decisions from gaps (not patterns)
        for gap in session.gap_analysis.gaps:
            # Only create decisions for non-compliant services
            if gap.status == GapStatus.COMPLIANT:
                continue

            # Create a mock decision for this gap
            # (We'll refine this to actual patterns if available)
            decision = self._gap_to_decision(gap, session)
            if decision:
                session.decisions.append(decision)

        # Calculate total cost
        session.estimated_monthly_cost = session.gap_analysis.estimated_cost_to_fix

        logger.info(f"Generated {len(session.decisions)} decisions from framework gaps")

    def _gap_to_decision(
        self,
        gap: ComplianceGap,
        session: DecisionSession
    ) -> Optional[DecisionResult]:
        """
        Convert a compliance gap to a decision result.

        For services that map to existing patterns (egress, transit, ingress),
        we use those patterns. For compliance services (cloudtrail, guardduty),
        we create synthetic decisions.
        """
        # Map gap service to existing patterns (if available)
        pattern_mappings = {
            # These gaps map to existing architecture patterns
            "nat_gateway": ("egress", EGRESS_PATTERNS, 0),  # Distributed NAT
            "network_firewall": ("egress", EGRESS_PATTERNS, 2),  # Network Firewall
            "vpc_peering": ("transit", TRANSIT_PATTERNS, 1),  # VPC Peering
            "transit_gateway": ("transit", TRANSIT_PATTERNS, 2),  # Transit Gateway
            "alb": ("ingress", INGRESS_PATTERNS, 0),  # Distributed ALB
            "cloudfront": ("ingress", INGRESS_PATTERNS, 2),  # CloudFront
        }

        if gap.service in pattern_mappings:
            category, pattern, option_index = pattern_mappings[gap.service]
            return DecisionResult(
                category=category,
                decision=pattern,
                selected_option=pattern.options[option_index],
                compliance_controls=gap.controls,
                why_required=gap.why_required,
                audit_evidence=gap.audit_evidence,
                gap_status=gap.status.value
            )

        # For compliance services without patterns, create synthetic decision
        # (cloudtrail, guardduty, config, security_hub, etc.)
        # These will be handled specially in foundation_builder
        synthetic_decision = ArchitectureDecision(
            category=gap.category,
            question=f"Enable {gap.service} for compliance",
            options=[
                DecisionOption(
                    name=f"Enable {gap.service}",
                    description=gap.why_required,
                    pros=[f"Satisfies controls: {', '.join(gap.controls)}"],
                    cons=[],
                    estimated_monthly_cost=gap.estimated_monthly_cost,
                    use_cases=[gap.category]
                )
            ]
        )

        return DecisionResult(
            category=gap.service,  # Use service name as category
            decision=synthetic_decision,
            selected_option=synthetic_decision.options[0],
            compliance_controls=gap.controls,
            why_required=gap.why_required,
            audit_evidence=gap.audit_evidence,
            gap_status=gap.status.value,
            custom_configuration=gap.required_config  # Pass required config
        )

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
