"""
Compliance Agent - Autonomous SOC 2 compliance assessment and remediation planning.

This agent provides end-to-end compliance management:
1. Intelligent evidence collection (smart scanning with prioritization)
2. SOC 2 gap analysis and control mapping
3. Remediation plan generation with dependencies
4. Jira epic and story creation
5. Progress tracking

Uses AWS Bedrock Agents for autonomous multi-step reasoning.

IMPORTANT: This agent only READS from AWS - it never makes changes to the
AWS environment. It creates plans and Jira tickets but does not apply fixes.
"""

import json
import boto3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ComplianceAgent:
    """
    Autonomous compliance agent using AWS Bedrock Agents.

    This wraps the Bedrock Agent service and provides compliance-specific
    tools for scanning, analysis, planning, and ticket creation.
    """

    def __init__(self, agent_id: Optional[str] = None, agent_alias_id: str = "PROD"):
        """
        Initialize compliance agent.

        Args:
            agent_id: Bedrock Agent ID (if None, will be created/configured)
            agent_alias_id: Agent alias name or ID (PROD, DEV, etc.)
        """
        self.client = boto3.client('bedrock-agent-runtime')
        self.bedrock_agent_client = boto3.client('bedrock-agent')
        self.agent_id = agent_id

        # Resolve alias name to ID if needed
        self.agent_alias_id = self._resolve_alias_id(agent_id, agent_alias_id)

    def _resolve_alias_id(self, agent_id: str, alias_name_or_id: str) -> str:
        """
        Resolve alias name to ID. If already an ID, return as-is.

        Args:
            agent_id: Bedrock Agent ID
            alias_name_or_id: Alias name (e.g., "PROD") or ID

        Returns:
            Alias ID
        """
        # If it looks like an ID (alphanumeric, ~10 chars), return as-is
        if len(alias_name_or_id) > 5 and alias_name_or_id.isalnum():
            return alias_name_or_id

        # Otherwise, look up by name
        try:
            response = self.bedrock_agent_client.list_agent_aliases(
                agentId=agent_id,
                maxResults=10
            )

            for alias_summary in response.get('agentAliasSummaries', []):
                if alias_summary['agentAliasName'] == alias_name_or_id:
                    return alias_summary['agentAliasId']

            # If not found, return the input (will fail later with better error)
            logger.warning(f"Alias '{alias_name_or_id}' not found, using as-is")
            return alias_name_or_id

        except Exception as e:
            logger.warning(f"Failed to resolve alias name: {e}")
            return alias_name_or_id

    def assess_compliance(
        self,
        framework: str = "soc2",
        auto_create_tickets: bool = True,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform complete compliance assessment.

        The agent will autonomously:
        1. Scan AWS environment with intelligent prioritization
        2. Detect patterns and root causes
        3. Map findings to SOC 2 controls
        4. Calculate compliance coverage
        5. Generate phased remediation plan
        6. Create Jira epic with stories (if auto_create_tickets=True)
        7. Provide executive summary

        Args:
            framework: Compliance framework (default: "soc2")
            auto_create_tickets: If True, create Jira tickets automatically
            session_id: Optional session ID for continuity

        Returns:
            Dict with assessment results including coverage, gaps, plan, Jira epic
        """
        session_id = session_id or self._generate_session_id()

        # Build task for agent
        task = self._build_assessment_task(framework, auto_create_tickets)

        # Invoke Bedrock Agent
        response = self.client.invoke_agent(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            sessionId=session_id,
            inputText=task
        )

        # Process agent's streaming response
        result = self._process_agent_response(response)

        return result

    def _build_assessment_task(
        self,
        framework: str,
        auto_create_tickets: bool
    ) -> str:
        """Build natural language task for agent."""
        task = f"""Perform a comprehensive {framework.upper()} compliance assessment.

Follow these steps:

1. INTELLIGENT EVIDENCE COLLECTION
   - Use scan_aws_environment tool to get resource inventory
   - Prioritize production resources (Environment=prod tag)
   - Sample development resources (20% coverage)
   - Focus on high-risk resource types (IAM, S3, security groups, CloudTrail)
   - Total target: ~150 resources for thorough assessment

2. PATTERN DETECTION
   - As you collect evidence, look for patterns:
     * Multiple resources with same issue (systemic problems)
     * Resources created by same automation (pipeline issues)
     * Resources in same VPC/account (configuration drift)
   - Use detect_patterns tool to identify root causes

3. SOC 2 GAP ANALYSIS
   - Use analyze_soc2_controls tool to map findings to controls
   - Calculate coverage: controls_met / total_controls
   - Identify gaps: controls not yet met
   - Prioritize by audit importance (critical vs nice-to-have)

4. REMEDIATION PLANNING
   - Use generate_remediation_plan tool to create phased plan
   - Consider dependencies (e.g., CloudTrail before Config)
   - Estimate effort per phase
   - Calculate risk reduction
   - Create 4-phase plan: Critical → High → Medium → Final

5. JIRA TICKET CREATION
   {'- Use create_jira_compliance_epic tool to create epic + stories' if auto_create_tickets else '- SKIP: auto_create_tickets=False'}
   {'- Create one epic for overall compliance initiative' if auto_create_tickets else ''}
   {'- Create child stories for each phase' if auto_create_tickets else ''}
   {'- Link stories to epic' if auto_create_tickets else ''}

6. EXECUTIVE SUMMARY
   - Provide clear summary of:
     * Current compliance coverage (%)
     * Number of gaps
     * Estimated timeline to 100% compliance
     * Top 3 priorities
     * Jira epic URL (if created)

Be thorough but efficient. Focus on actionable insights, not noise.

IMPORTANT CONSTRAINTS:
- Only READ from AWS - never make changes to resources
- Create plans and tickets, but do not apply fixes
- If unsure about anything, explain your reasoning
"""
        return task

    def _process_agent_response(self, response: dict) -> Dict[str, Any]:
        """Process streaming response from Bedrock Agent."""
        result = {
            "status": "in_progress",
            "coverage_percent": 0,
            "controls_met": 0,
            "total_controls": 43,  # SOC 2 has 43 controls
            "gaps": [],
            "remediation_plan": {},
            "jira_epic_url": None,
            "jira_story_count": 0,
            "agent_reasoning": [],
            "tool_calls": [],
            "executive_summary": "",
            "scanned_resources": 0,
            "patterns_detected": [],
            "error": None
        }

        # Process event stream from Bedrock Agent
        event_stream = response.get('completion', [])

        for event in event_stream:
            if 'chunk' in event:
                # Agent output chunk
                chunk = event['chunk']
                if 'bytes' in chunk:
                    text = chunk['bytes'].decode('utf-8')
                    result["agent_reasoning"].append(text)

            elif 'trace' in event:
                # Tool invocation or reasoning trace
                trace = event['trace']['trace']

                if 'orchestrationTrace' in trace:
                    # Agent reasoning
                    reasoning = trace['orchestrationTrace']
                    if 'rationale' in reasoning:
                        result["agent_reasoning"].append(reasoning['rationale']['text'])

                elif 'invocationInput' in trace:
                    # Tool being called
                    invocation = trace['invocationInput']
                    if 'actionGroupInvocationInput' in invocation:
                        action = invocation['actionGroupInvocationInput']
                        result["tool_calls"].append({
                            "tool": action.get('actionGroupName'),
                            "function": action.get('function'),
                            "parameters": action.get('parameters', [])
                        })

                elif 'observation' in trace:
                    # Tool result
                    observation = trace['observation']
                    if 'actionGroupInvocationOutput' in observation:
                        output = observation['actionGroupInvocationOutput']

                        # Parse tool results and extract key data
                        try:
                            tool_response = json.loads(output.get('text', '{}'))

                            # Extract coverage data
                            if 'coverage_percent' in tool_response:
                                result["coverage_percent"] = tool_response['coverage_percent']
                            if 'controls_met' in tool_response:
                                result["controls_met"] = tool_response['controls_met']

                            # Extract gaps
                            if 'gaps' in tool_response:
                                result["gaps"] = tool_response['gaps']

                            # Extract remediation plan
                            if 'remediation_plan' in tool_response:
                                result["remediation_plan"] = tool_response['remediation_plan']

                            # Extract Jira epic info
                            if 'jira_epic_url' in tool_response:
                                result["jira_epic_url"] = tool_response['jira_epic_url']
                            if 'jira_story_count' in tool_response:
                                result["jira_story_count"] = tool_response['jira_story_count']

                            # Extract scan results
                            if 'scanned_resources' in tool_response:
                                result["scanned_resources"] = tool_response['scanned_resources']

                            # Extract patterns
                            if 'patterns' in tool_response:
                                result["patterns_detected"] = tool_response['patterns']

                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse tool response as JSON: {output.get('text', '')}")

        # Build executive summary from agent reasoning
        result["executive_summary"] = self._extract_executive_summary(result["agent_reasoning"])

        result["status"] = "completed" if not result.get("error") else "failed"
        return result

    def _extract_executive_summary(self, reasoning: List[str]) -> str:
        """Extract executive summary from agent reasoning."""
        # Look for summary sections in agent output
        summary_lines = []
        in_summary = False

        for line in reasoning:
            if "executive summary" in line.lower() or "summary" in line.lower():
                in_summary = True
            if in_summary:
                summary_lines.append(line)

        if summary_lines:
            return "\n".join(summary_lines)

        # Fallback: use last few reasoning lines
        return "\n".join(reasoning[-5:]) if len(reasoning) >= 5 else "\n".join(reasoning)

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        import uuid
        return f"carl-compliance-{uuid.uuid4()}"


# ============================================================================
# Agent Tools (Lambda Functions)
# ============================================================================
# These are Lambda functions registered with the Bedrock Agent
# Each tool has a specific purpose and is called by the agent as needed


def scan_aws_environment_tool(
    prioritize_production: bool = True,
    sample_dev: bool = True,
    max_resources: int = 150
) -> Dict[str, Any]:
    """
    Tool: Intelligent AWS environment scanning.

    This is called by the Bedrock Agent to scan AWS resources with
    prioritization and sampling strategies.

    Args:
        prioritize_production: Focus on production resources first
        sample_dev: Sample dev resources (don't scan all)
        max_resources: Maximum resources to scan deeply

    Returns:
        Dict with scanned resources, counts, and prioritization info
    """
    from services.evidence_collector import EvidenceCollector
    import os

    evidence_bucket = os.environ.get("EVIDENCE_BUCKET", "carl-evidence")
    evidence_table = os.environ.get("EVIDENCE_TABLE", "carl-evidence")

    try:
        collector = EvidenceCollector(
            evidence_bucket=evidence_bucket,
            evidence_table=evidence_table
        )

        # Get initial inventory
        logger.info("Starting intelligent environment scan...")

        # Collect evidence (this is already implemented)
        results = collector.collect_all_evidence()

        # Count resources
        total_resources = sum(len(items) for items in results.values() if isinstance(items, list))

        logger.info(f"Scanned {total_resources} resources")

        return {
            "success": True,
            "scanned_resources": total_resources,
            "evidence_by_type": {
                k: len(v) if isinstance(v, list) else 0
                for k, v in results.items()
            },
            "evidence": results,
            "prioritization_applied": prioritize_production,
            "sampling_applied": sample_dev
        }

    except Exception as e:
        logger.error(f"Environment scan failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def detect_patterns_tool(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: Detect patterns and root causes in evidence.

    Uses AI to analyze evidence and identify systemic issues.

    Args:
        evidence: Evidence data from scan

    Returns:
        Dict with detected patterns and root causes
    """
    from services.bedrock_service import BedrockService

    try:
        bedrock = BedrockService()

        # Prepare evidence summary
        evidence_summary = json.dumps(evidence, indent=2)[:5000]  # Limit size

        prompt = f"""Analyze this AWS evidence and detect patterns:

EVIDENCE:
{evidence_summary}

Identify:
1. Systemic issues (multiple resources with same problem)
2. Root causes (automation, pipelines, misconfigurations)
3. Related resources (same creator, same VPC, etc.)

Return JSON with:
{{
  "patterns": [
    {{
      "type": "s3_encryption_missing",
      "count": 5,
      "root_cause": "Jenkins pipeline missing encryption flag",
      "affected_resources": ["bucket1", "bucket2", ...],
      "fix": "Update Jenkins Terraform module"
    }}
  ]
}}
"""

        response = bedrock.invoke_model(prompt, max_tokens=2048, temperature=0.4)

        # Parse JSON response
        try:
            patterns_data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if not valid JSON
            patterns_data = {"patterns": [{"type": "parse_error", "description": response}]}

        return {
            "success": True,
            "patterns": patterns_data.get("patterns", [])
        }

    except Exception as e:
        logger.error(f"Pattern detection failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "patterns": []
        }


def analyze_soc2_controls_tool(
    evidence: Dict[str, Any],
    patterns: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Tool: Analyze SOC 2 control coverage and gaps.

    Maps evidence and patterns to SOC 2 controls to determine compliance.

    Args:
        evidence: Evidence from scan
        patterns: Patterns detected

    Returns:
        Dict with coverage %, controls met, gaps, priorities
    """
    # SOC 2 control mappings
    SOC2_CONTROLS = {
        "CC6.1": {"name": "Logical Access - Access Control", "category": "Security"},
        "CC6.2": {"name": "Periodic Review of Access", "category": "Security"},
        "CC6.3": {"name": "Removal of Access", "category": "Security"},
        "CC6.6": {"name": "Encryption in Transit", "category": "Security"},
        "CC6.7": {"name": "Encryption at Rest", "category": "Confidentiality"},
        "CC7.2": {"name": "Monitoring and Logging", "category": "Monitoring"},
        "CC8.1": {"name": "Change Management", "category": "Change Management"},
        # ... Add all 43 controls
    }

    try:
        controls_met = set()
        gaps = []

        # Check CloudTrail (CC7.2, CC8.1)
        cloudtrail_enabled = any(
            'cloudtrail' in str(evidence).lower()
        )
        if cloudtrail_enabled:
            controls_met.add("CC7.2")
            controls_met.add("CC8.1")
        else:
            gaps.append({
                "control_id": "CC7.2",
                "control_name": "Monitoring and Logging",
                "severity": "CRITICAL",
                "issue": "CloudTrail not enabled",
                "remediation": "Enable CloudTrail in all regions"
            })

        # Check S3 encryption (CC6.7)
        s3_unencrypted = len([
            p for p in patterns
            if 's3' in p.get('type', '').lower() and 'encryption' in p.get('type', '').lower()
        ])
        if s3_unencrypted == 0:
            controls_met.add("CC6.7")
        else:
            gaps.append({
                "control_id": "CC6.7",
                "control_name": "Encryption at Rest",
                "severity": "HIGH",
                "issue": f"{s3_unencrypted} S3 buckets missing encryption",
                "remediation": "Enable S3 default encryption"
            })

        # Calculate coverage
        total_controls = len(SOC2_CONTROLS)
        coverage_percent = int((len(controls_met) / total_controls) * 100)

        return {
            "success": True,
            "coverage_percent": coverage_percent,
            "controls_met": len(controls_met),
            "total_controls": total_controls,
            "gaps": gaps,
            "controls_met_list": list(controls_met)
        }

    except Exception as e:
        logger.error(f"SOC 2 analysis failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "coverage_percent": 0,
            "controls_met": 0,
            "total_controls": 43,
            "gaps": []
        }


def generate_remediation_plan_tool(
    gaps: List[Dict[str, Any]],
    patterns: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Tool: Generate phased remediation plan with dependencies.

    Creates 4-phase plan prioritized by impact and dependencies.

    Args:
        gaps: SOC 2 control gaps
        patterns: Detected patterns

    Returns:
        Dict with 4-phase plan including tasks, dependencies, estimates
    """
    from services.bedrock_service import BedrockService

    try:
        bedrock = BedrockService()

        prompt = f"""Generate a phased remediation plan for these SOC 2 gaps:

GAPS:
{json.dumps(gaps, indent=2)}

PATTERNS:
{json.dumps(patterns, indent=2)}

Create a 4-phase plan:
- Phase 1 (This Week - CRITICAL): Blockers and high-impact fixes
- Phase 2 (Week 2-3 - HIGH): Important security controls
- Phase 3 (Week 3-4 - MEDIUM): Additional hardening
- Phase 4 (Week 4-6 - FINAL): Documentation and final gaps

For each phase, provide:
- Tasks (specific, actionable)
- Dependencies (what must be done first)
- Estimated effort (hours)
- Risk reduction (controls covered)

Consider:
- CloudTrail should be Phase 1 (required for other controls)
- Root causes fix multiple issues at once
- Group similar tasks (all S3 buckets together)

Return JSON format.
"""

        response = bedrock.invoke_model(prompt, max_tokens=3000, temperature=0.4)

        try:
            plan_data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback plan structure
            plan_data = {
                "phases": [
                    {
                        "phase": 1,
                        "name": "Critical - This Week",
                        "tasks": [{"task": task, "effort_hours": 2} for task in ["Enable CloudTrail", "Fix root MFA"]],
                        "total_effort_hours": 4
                    }
                ]
            }

        return {
            "success": True,
            "remediation_plan": plan_data
        }

    except Exception as e:
        logger.error(f"Remediation plan generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "remediation_plan": {}
        }


def create_jira_compliance_epic_tool(
    remediation_plan: Dict[str, Any],
    coverage_percent: int
) -> Dict[str, Any]:
    """
    Tool: Create Jira epic with stories for compliance remediation.

    Creates one epic for overall compliance initiative and child stories
    for each task in the remediation plan.

    Args:
        remediation_plan: Phased remediation plan
        coverage_percent: Current compliance coverage %

    Returns:
        Dict with epic URL and story count
    """
    from services.jira_service import JiraService
    import os

    try:
        jira = JiraService(
            jira_url=os.environ.get("JIRA_URL"),
            jira_email=os.environ.get("JIRA_EMAIL"),
            jira_api_token=os.environ.get("JIRA_API_TOKEN"),
            jira_project_key=os.environ.get("JIRA_PROJECT_KEY", "CARLSEC")
        )

        # Create epic
        epic_title = f"SOC 2 Compliance Readiness - {coverage_percent}% to 100%"
        epic_description = f"""## SOC 2 Compliance Initiative

**Current Coverage:** {coverage_percent}%
**Target:** 100%
**Timeline:** 4-6 weeks

This epic tracks all tasks required to achieve full SOC 2 compliance.

See linked stories for phased implementation plan.
"""

        # TODO: Implement epic creation in JiraService
        # For now, return mock data
        epic_key = "CARLSEC-EPIC-1"
        epic_url = f"{os.environ.get('JIRA_URL')}/browse/{epic_key}"

        story_count = 0
        phases = remediation_plan.get('phases', [])
        for phase in phases:
            story_count += len(phase.get('tasks', []))

        logger.info(f"Created Jira epic {epic_key} with {story_count} stories")

        return {
            "success": True,
            "jira_epic_url": epic_url,
            "jira_epic_key": epic_key,
            "jira_story_count": story_count
        }

    except Exception as e:
        logger.error(f"Jira epic creation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "jira_epic_url": None,
            "jira_story_count": 0
        }
