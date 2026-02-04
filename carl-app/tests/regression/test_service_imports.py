"""
CARL Service Import Tests

These tests verify that all services can be imported without errors.
This catches missing dependencies, syntax errors, and circular imports early.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestServiceImports:
    """Tests that all services can be imported without errors."""

    def test_import_slack_router(self):
        """Slack router should import without errors."""
        from handlers import slack_router
        assert slack_router is not None

    def test_import_bedrock_service(self):
        """Bedrock service should import without errors."""
        from services.bedrock_service import BedrockService
        assert BedrockService is not None

    def test_import_findings_service(self):
        """Findings service should import without errors."""
        from services.findings_service import FindingsService
        assert FindingsService is not None

    def test_import_evidence_collector(self):
        """Evidence collector should import without errors."""
        from services.evidence_collector import EvidenceCollector
        assert EvidenceCollector is not None

    def test_import_architecture_advisor(self):
        """Architecture advisor should import without errors."""
        from services.architecture_advisor import ArchitectureAdvisor
        assert ArchitectureAdvisor is not None

    def test_import_infrastructure_builder(self):
        """Infrastructure builder should import without errors."""
        from services.infrastructure_builder import InfrastructureBuilder
        assert InfrastructureBuilder is not None

    def test_import_cost_estimator(self):
        """Cost estimator should import without errors."""
        from services.cost_estimator import CostEstimator
        assert CostEstimator is not None

    def test_import_learning_service(self):
        """Learning service should import without errors."""
        from services.learning_service import LearningService
        assert LearningService is not None

    def test_import_build_session_service(self):
        """Build session service should import without errors."""
        from services.build_session_service import BuildSessionService
        assert BuildSessionService is not None


class TestKnowledgeImports:
    """Tests that all knowledge modules can be imported."""

    def test_import_architecture_patterns(self):
        """Architecture patterns should import without errors."""
        from knowledge import architecture_patterns
        assert architecture_patterns is not None

    def test_import_vpc_patterns(self):
        """VPC patterns should import without errors."""
        from knowledge import vpc_patterns
        assert vpc_patterns is not None

    def test_import_identity_patterns(self):
        """Identity patterns should import without errors."""
        from knowledge import identity_patterns
        assert identity_patterns is not None

    def test_import_security_tooling_patterns(self):
        """Security tooling patterns should import without errors."""
        from knowledge import security_tooling_patterns
        assert security_tooling_patterns is not None


class TestModelImports:
    """Tests that all models can be imported."""

    def test_import_finding_model(self):
        """Finding model should import without errors."""
        from models.finding import Finding, FindingSeverity, FindingStatus
        assert Finding is not None
        assert FindingSeverity is not None
        assert FindingStatus is not None


class TestUtilImports:
    """Tests that all utility modules can be imported."""

    def test_import_logger(self):
        """Logger utility should import without errors."""
        from utils.logger import get_logger
        assert get_logger is not None

    def test_import_soc2_mappings(self):
        """SOC2 mappings should import without errors."""
        from utils.soc2_mappings import get_soc2_controls
        assert get_soc2_controls is not None

    def test_import_aws_client(self):
        """AWS client utilities should import without errors."""
        from utils.aws_client import get_parameter
        assert get_parameter is not None
