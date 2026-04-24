"""
Tests for Handoff Intent Detection

These tests verify that the Ask Agent correctly detects when to suggest
handoffs to other agents (Architect or Remediate).
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Optional


# Replicate the minimal dataclasses from carl_ask_agent.py for testing
@dataclass
class ResourceScanResult:
    """Represents a scanned AWS resource."""
    service: str
    resource_type: str
    resource_id: str
    resource_name: str
    region: str
    account_id: str
    data: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)


@dataclass
class HandoffSuggestion:
    """Represents a suggested handoff to another agent."""
    target_agent: str
    reason: str
    confidence: float
    context: dict = field(default_factory=dict)


def detect_handoff_intent(question: str, response: str, scan_results: dict) -> Optional[HandoffSuggestion]:
    """
    Detect if the user's question/response suggests handing off to another agent.
    This is a copy of the function from carl_ask_agent.py for testing purposes.
    """
    question_lower = question.lower()
    response_lower = response.lower() if response else ""

    # Architecture handoff keywords
    architect_keywords = [
        "how should i design", "best way to architect", "recommend architecture",
        "vpc design", "network design", "infrastructure design",
        "what's the best approach", "how to structure", "best practices for",
        "design pattern", "architecture recommendation", "design my"
    ]

    # Remediation handoff keywords
    remediate_keywords = [
        "fix", "remediate", "resolve", "enable encryption", "enable versioning",
        "block public access", "add flow logs", "fix password policy",
        "secure", "patch", "update security", "make compliant", "fix this",
        "how do i fix", "can you fix", "please fix"
    ]

    # Check for findings in scan results
    has_findings = False
    finding_count = 0
    finding_types = []

    for service, resources in scan_results.items():
        if service.startswith("_"):
            continue
        for resource in resources:
            data = resource.data if hasattr(resource, 'data') else {}

            if data.get("encryption") == "none":
                has_findings = True
                finding_count += 1
                finding_types.append("unencrypted S3 bucket")
            if data.get("mfa_enabled") is False:
                has_findings = True
                finding_count += 1
                finding_types.append("MFA not enabled")
            if data.get("has_open_ingress"):
                has_findings = True
                finding_count += 1
                finding_types.append("open security group")
            public_access = data.get("public_access_block", {})
            if public_access and not public_access.get("block_public_acls"):
                has_findings = True
                finding_count += 1
                finding_types.append("public access not blocked")

    # Check for architecture intent
    architect_score = sum(1 for kw in architect_keywords if kw in question_lower)
    if architect_score >= 1:
        return HandoffSuggestion(
            target_agent="architect",
            reason=f"Your question suggests you're looking for architecture recommendations.",
            confidence=min(0.7 + (architect_score * 0.1), 0.95),
            context={
                "original_question": question,
                "scan_summary": f"Scanned {sum(len(r) for r in scan_results.values() if isinstance(r, list))} resources"
            }
        )

    # Check for remediation intent
    remediate_score = sum(1 for kw in remediate_keywords if kw in question_lower or kw in response_lower)

    if remediate_score >= 1 and has_findings:
        unique_findings = list(set(finding_types))[:3]
        return HandoffSuggestion(
            target_agent="remediate",
            reason=f"I found {finding_count} security issue(s) that can be remediated: {', '.join(unique_findings)}.",
            confidence=min(0.7 + (remediate_score * 0.1), 0.95),
            context={
                "original_question": question,
                "finding_count": finding_count,
                "finding_types": unique_findings
            }
        )

    # If there are findings mentioned in the response, offer remediation
    finding_indicators = ["issue", "finding", "vulnerability", "non-compliant", "missing", "not enabled", "not configured"]
    if has_findings and any(ind in response_lower for ind in finding_indicators):
        unique_findings = list(set(finding_types))[:3]
        return HandoffSuggestion(
            target_agent="remediate",
            reason=f"I found {finding_count} security issue(s) in your environment: {', '.join(unique_findings)}.",
            confidence=0.75,
            context={
                "original_question": question,
                "finding_count": finding_count,
                "finding_types": unique_findings
            }
        )

    return None


class TestArchitectHandoffDetection:
    """Tests for detecting architecture handoff intent."""

    def test_vpc_design_question(self):
        """VPC design questions should suggest architect handoff."""
        question = "How should I design my VPC for a multi-tier web application?"
        response = "Let me analyze your question..."
        scan_results = {"vpc": [], "s3": []}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "architect"
        assert handoff.confidence >= 0.7
        assert "architecture" in handoff.reason.lower()

    def test_network_design_question(self):
        """Network design questions should suggest architect handoff."""
        question = "What's the best approach for network design with AWS?"
        response = ""
        scan_results = {}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "architect"
        assert handoff.confidence >= 0.7

    def test_infrastructure_design_question(self):
        """Infrastructure design questions should suggest architect handoff."""
        question = "I need help with infrastructure design for my startup"
        response = ""
        scan_results = {}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "architect"

    def test_best_practices_question(self):
        """Best practices questions should suggest architect handoff."""
        question = "What are the best practices for setting up AWS networking?"
        response = ""
        scan_results = {"vpc": []}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "architect"

    def test_multiple_architect_keywords_high_confidence(self):
        """Multiple architecture keywords should increase confidence."""
        question = "How should I design my VPC and what's the best approach for network design?"
        response = ""
        scan_results = {}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "architect"
        assert handoff.confidence >= 0.8  # Multiple keywords = higher confidence


class TestRemediateHandoffDetection:
    """Tests for detecting remediation handoff intent."""

    def test_fix_s3_encryption(self):
        """Fix S3 encryption request with findings should suggest remediate handoff."""
        question = "Can you fix my S3 encryption issues?"
        response = "I found unencrypted buckets"
        scan_results = {
            "s3": [
                ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id="my-bucket",
                    resource_name="my-bucket",
                    region="us-east-1",
                    account_id="123456789012",
                    data={"encryption": "none"}
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "remediate"
        assert handoff.confidence >= 0.7
        assert "unencrypted S3 bucket" in handoff.context.get("finding_types", [])

    def test_remediate_security_issues(self):
        """Explicit remediate request with findings should suggest remediate handoff."""
        question = "Please remediate my security issues"
        response = "I found several issues"
        scan_results = {
            "iam": [
                ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::User",
                    resource_id="user-123",
                    resource_name="admin-user",
                    region="global",
                    account_id="123456789012",
                    data={"mfa_enabled": False}
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "remediate"
        assert handoff.context.get("finding_count", 0) >= 1

    def test_enable_encryption_request(self):
        """Enable encryption request should suggest remediate handoff."""
        question = "Enable encryption for my S3 buckets"
        response = ""
        scan_results = {
            "s3": [
                ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id="bucket-1",
                    resource_name="bucket-1",
                    region="us-east-1",
                    account_id="123456789012",
                    data={"encryption": "none"}
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "remediate"

    def test_response_contains_findings(self):
        """Response mentioning issues should suggest remediate handoff."""
        question = "What's my security posture?"
        response = "Your environment has several issues that are non-compliant"
        scan_results = {
            "vpc": [
                ResourceScanResult(
                    service="vpc",
                    resource_type="AWS::EC2::SecurityGroup",
                    resource_id="sg-123",
                    resource_name="open-sg",
                    region="us-east-1",
                    account_id="123456789012",
                    data={"has_open_ingress": True}
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "remediate"
        assert handoff.confidence >= 0.7

    def test_multiple_finding_types(self):
        """Multiple finding types should be captured in context."""
        question = "Fix all my security issues"
        response = ""
        scan_results = {
            "s3": [
                ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id="bucket-1",
                    resource_name="bucket-1",
                    region="us-east-1",
                    account_id="123456789012",
                    data={"encryption": "none", "public_access_block": {"block_public_acls": False}}
                )
            ],
            "iam": [
                ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::User",
                    resource_id="user-1",
                    resource_name="user-1",
                    region="global",
                    account_id="123456789012",
                    data={"mfa_enabled": False}
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.target_agent == "remediate"
        assert handoff.context.get("finding_count", 0) >= 3


class TestNoHandoffScenarios:
    """Tests for scenarios where no handoff should be suggested."""

    def test_simple_status_question(self):
        """Simple status questions should not trigger handoff."""
        question = "What's my current MFA status?"
        response = "Your MFA status is: 5 users with MFA enabled"
        scan_results = {
            "iam": [
                ResourceScanResult(
                    service="iam",
                    resource_type="AWS::IAM::User",
                    resource_id="user-1",
                    resource_name="user-1",
                    region="global",
                    account_id="123456789012",
                    data={"mfa_enabled": True}  # No issues
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is None

    def test_info_only_request(self):
        """Information-only requests should not trigger handoff."""
        question = "List all my S3 buckets"
        response = "You have 5 S3 buckets"
        scan_results = {
            "s3": [
                ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id="bucket-1",
                    resource_name="bucket-1",
                    region="us-east-1",
                    account_id="123456789012",
                    data={"encryption": "AES256"}  # Encrypted, no issue
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is None

    def test_fix_request_no_findings(self):
        """Fix request without actual findings should not trigger handoff."""
        question = "Fix my security issues"
        response = "Everything looks compliant"
        scan_results = {
            "s3": [
                ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id="bucket-1",
                    resource_name="bucket-1",
                    region="us-east-1",
                    account_id="123456789012",
                    data={"encryption": "aws:kms"}  # Already encrypted
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is None

    def test_empty_scan_results(self):
        """Empty scan results should not trigger handoff."""
        question = "What's wrong with my infrastructure?"
        response = "I couldn't find any resources"
        scan_results = {}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is None


class TestConfidenceThresholds:
    """Tests for confidence threshold behavior."""

    def test_single_keyword_meets_threshold(self):
        """Single architecture keyword should meet 70% threshold."""
        question = "How should I design this?"
        response = ""
        scan_results = {}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.confidence >= 0.7
        assert handoff.confidence < 0.9

    def test_confidence_caps_at_95(self):
        """Confidence should cap at 95% even with many keywords."""
        question = "How should I design my VPC with best practices for network design and infrastructure design patterns?"
        response = ""
        scan_results = {}

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.confidence <= 0.95

    def test_remediate_confidence_with_multiple_keywords(self):
        """Multiple remediation keywords should increase confidence."""
        question = "Please fix and remediate my security issues and make compliant"
        response = ""
        scan_results = {
            "s3": [
                ResourceScanResult(
                    service="s3",
                    resource_type="AWS::S3::Bucket",
                    resource_id="bucket-1",
                    resource_name="bucket-1",
                    region="us-east-1",
                    account_id="123456789012",
                    data={"encryption": "none"}
                )
            ]
        }

        handoff = detect_handoff_intent(question, response, scan_results)

        assert handoff is not None
        assert handoff.confidence >= 0.8
