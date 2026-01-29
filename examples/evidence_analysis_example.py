"""
Example: Intelligent Evidence Analysis with AI

This shows how to add AI-powered evidence analysis to CARL.
Analyzes evidence immediately after collection to surface patterns.

Estimated Effort: 4-6 hours
Cost: ~$0.01 per analysis
Impact: HIGH - surfaces patterns humans would miss
"""

from services.bedrock_service import BedrockService


def analyze_evidence_with_ai(evidence_items: list[dict]) -> dict:
    """
    Analyze collected evidence and surface intelligent insights.

    Args:
        evidence_items: List of evidence items from evidence_collector

    Returns:
        Dict with patterns, priorities, and recommendations
    """
    bedrock = BedrockService()

    # Prepare evidence summary for AI
    evidence_summary = _prepare_evidence_summary(evidence_items)

    prompt = f"""Analyze this AWS environment evidence and provide intelligent insights.

EVIDENCE COLLECTED:
{evidence_summary}

Analyze and provide:

## Critical Patterns
Identify patterns that indicate systemic issues (not individual problems):
- Resources missing the same security control
- Configuration inconsistencies across resources
- Resources in same account/region with related issues

## Priority Recommendations
Based on the evidence, what should be fixed FIRST and WHY?
Consider:
- Risk (what's most dangerous?)
- Efficiency (what unblocks other fixes?)
- Compliance (what do auditors care most about?)

## Hidden Insights
What non-obvious observations can you make?
- Unusual configurations
- Resources that shouldn't exist
- Missing resources that should exist
- Trends over time (if applicable)

## Quick Wins
What can be fixed in <30 minutes that has high impact?

## Dependencies
What fixes depend on other fixes?
Example: "AWS Config requires CloudTrail to be enabled first"

Format each section clearly with bullet points.
Keep total response under 500 words.
Be specific - reference actual resources by ID."""

    analysis = bedrock.invoke_model(
        prompt=prompt,
        max_tokens=2048,
        temperature=0.4  # Lower temp for more focused analysis
    )

    # Parse AI response into structured format
    parsed = _parse_analysis_response(analysis)

    return {
        "raw_analysis": analysis,
        "critical_patterns": parsed.get("critical_patterns", []),
        "priority_recommendations": parsed.get("priority_recommendations", []),
        "hidden_insights": parsed.get("hidden_insights", []),
        "quick_wins": parsed.get("quick_wins", []),
        "dependencies": parsed.get("dependencies", []),
        "total_evidence_items": len(evidence_items)
    }


def _prepare_evidence_summary(evidence_items: list[dict]) -> str:
    """Prepare concise evidence summary for AI analysis."""
    # Group by evidence type
    by_type = {}
    for item in evidence_items:
        evidence_type = item.get("evidence_type", "unknown")
        if evidence_type not in by_type:
            by_type[evidence_type] = []
        by_type[evidence_type].append(item)

    summary_lines = []

    # Summarize IAM evidence
    if "iam_password_policy" in by_type:
        items = by_type["iam_password_policy"]
        summary_lines.append(f"IAM Password Policy: {len(items)} items")
        for item in items:
            content = item.get("content", {})
            summary_lines.append(
                f"  - Min length: {content.get('minimum_password_length', 'N/A')}, "
                f"MFA required: {content.get('require_mfa', False)}"
            )

    # Summarize S3 evidence
    if "s3_bucket" in by_type:
        items = by_type["s3_bucket"]
        summary_lines.append(f"\nS3 Buckets: {len(items)} items")

        no_encryption = [i for i in items if not i.get("content", {}).get("encryption")]
        no_versioning = [i for i in items if not i.get("content", {}).get("versioning")]
        public = [i for i in items if i.get("content", {}).get("public_access_block") != "all_blocked"]

        summary_lines.append(f"  - Missing encryption: {len(no_encryption)}")
        if no_encryption:
            bucket_names = [i.get("resource_id", "unknown") for i in no_encryption[:3]]
            summary_lines.append(f"    Examples: {', '.join(bucket_names)}")

        summary_lines.append(f"  - No versioning: {len(no_versioning)}")
        summary_lines.append(f"  - Public access not fully blocked: {len(public)}")

    # Summarize Security Group evidence
    if "security_group" in by_type:
        items = by_type["security_group"]
        summary_lines.append(f"\nSecurity Groups: {len(items)} items")

        open_sgs = []
        for item in items:
            rules = item.get("content", {}).get("ingress_rules", [])
            if any(r.get("cidr") == "0.0.0.0/0" for r in rules):
                open_sgs.append(item)

        summary_lines.append(f"  - With 0.0.0.0/0 rules: {len(open_sgs)}")
        if open_sgs:
            sg_ids = [i.get("resource_id", "unknown") for i in open_sgs[:3]]
            summary_lines.append(f"    Examples: {', '.join(sg_ids)}")

    # Summarize VPC evidence
    if "vpc_flow_logs" in by_type:
        items = by_type["vpc_flow_logs"]
        no_logs = [i for i in items if not i.get("content", {}).get("flow_logs_enabled")]
        summary_lines.append(f"\nVPCs: {len(items)} items")
        summary_lines.append(f"  - Missing flow logs: {len(no_logs)}")

    # Add account/region context
    accounts = set(item.get("account_id") for item in evidence_items if item.get("account_id"))
    regions = set(item.get("region") for item in evidence_items if item.get("region"))
    summary_lines.append(f"\nAccounts: {', '.join(accounts)}")
    summary_lines.append(f"Regions: {', '.join(regions)}")

    return "\n".join(summary_lines)


def _parse_analysis_response(analysis: str) -> dict:
    """Parse AI analysis response into structured format."""
    import re

    sections = {
        "critical_patterns": [],
        "priority_recommendations": [],
        "hidden_insights": [],
        "quick_wins": [],
        "dependencies": []
    }

    # Simple regex-based parsing (could be more sophisticated)
    current_section = None

    for line in analysis.split('\n'):
        line = line.strip()

        # Detect section headers
        if "Critical Patterns" in line:
            current_section = "critical_patterns"
        elif "Priority Recommendations" in line:
            current_section = "priority_recommendations"
        elif "Hidden Insights" in line:
            current_section = "hidden_insights"
        elif "Quick Wins" in line:
            current_section = "quick_wins"
        elif "Dependencies" in line:
            current_section = "dependencies"
        # Parse bullet points
        elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
            if current_section:
                bullet_text = line.lstrip('•-* ').strip()
                if bullet_text:
                    sections[current_section].append(bullet_text)

    return sections


# Example usage in evidence collection handler
def handle_evidence_collect_with_analysis(slack, channel_id, user_id):
    """Enhanced evidence collection with AI analysis."""
    from services.evidence_collector import EvidenceCollector

    # Collect evidence (existing code)
    collector = EvidenceCollector()
    results = collector.collect_all_evidence()

    evidence_count = sum(len(v) for v in results.values() if isinstance(v, list))

    slack.post_message(
        channel_id,
        text=f"✅ Collected {evidence_count} evidence items. Analyzing patterns..."
    )

    # AI ANALYSIS (NEW)
    try:
        evidence_items = []
        for category, items in results.items():
            if isinstance(items, list):
                evidence_items.extend(items)

        analysis = analyze_evidence_with_ai(evidence_items)

        # Post analysis to Slack in thread
        _post_analysis_to_slack(slack, channel_id, analysis)

    except Exception as e:
        logger.warning(f"Evidence analysis failed, continuing without it: {e}")

    # Continue with existing flow (create findings, etc.)
    findings = collector.create_findings_from_evidence(results)
    # ... rest of existing code


def _post_analysis_to_slack(slack, channel_id, analysis: dict):
    """Post AI analysis to Slack with nice formatting."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🧠 AI Analysis Complete"}
        }
    ]

    # Critical Patterns
    if analysis.get("critical_patterns"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🔴 Critical Patterns*\n" + "\n".join([
                    f"• {p}" for p in analysis["critical_patterns"][:3]
                ])
            }
        })

    # Priority Recommendations
    if analysis.get("priority_recommendations"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*⭐ Priority Recommendations*\n" + "\n".join([
                    f"{i+1}. {p}" for i, p in enumerate(analysis["priority_recommendations"][:3])
                ])
            }
        })

    # Quick Wins
    if analysis.get("quick_wins"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*⚡ Quick Wins (<30 min)*\n" + "\n".join([
                    f"• {w}" for w in analysis["quick_wins"][:3]
                ])
            }
        })

    # Hidden Insights
    if analysis.get("hidden_insights"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*💡 Hidden Insights*\n" + "\n".join([
                    f"• {i}" for i in analysis["hidden_insights"][:2]
                ])
            }
        })

    # Context
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"Analyzed {analysis['total_evidence_items']} evidence items"
        }]
    })

    slack.post_message(channel_id, blocks=blocks)


if __name__ == "__main__":
    # Example test data
    test_evidence = [
        {
            "evidence_type": "s3_bucket",
            "resource_id": "my-bucket-1",
            "account_id": "123456789012",
            "region": "us-east-1",
            "content": {
                "encryption": None,
                "versioning": False,
                "public_access_block": "partial"
            }
        },
        {
            "evidence_type": "s3_bucket",
            "resource_id": "my-bucket-2",
            "account_id": "123456789012",
            "region": "us-east-1",
            "content": {
                "encryption": None,
                "versioning": False,
                "public_access_block": "all_blocked"
            }
        },
        {
            "evidence_type": "iam_password_policy",
            "resource_id": "account-password-policy",
            "account_id": "123456789012",
            "region": "us-east-1",
            "content": {
                "minimum_password_length": 8,
                "require_mfa": False
            }
        }
    ]

    # Run analysis
    analysis = analyze_evidence_with_ai(test_evidence)

    print("AI Analysis Results:")
    print("===================")
    print(f"\nCritical Patterns ({len(analysis['critical_patterns'])}):")
    for p in analysis['critical_patterns']:
        print(f"  - {p}")

    print(f"\nPriority Recommendations ({len(analysis['priority_recommendations'])}):")
    for i, r in enumerate(analysis['priority_recommendations'], 1):
        print(f"  {i}. {r}")

    print(f"\nQuick Wins ({len(analysis['quick_wins'])}):")
    for w in analysis['quick_wins']:
        print(f"  - {w}")
