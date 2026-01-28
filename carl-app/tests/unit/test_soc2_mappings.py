"""
Tests for SOC 2 mappings.
"""

import pytest

from src.utils.soc2_mappings import (
    get_control_description,
    get_controls_for_service,
    get_soc2_controls,
)


class TestSOC2Mappings:
    """Tests for SOC 2 control mappings."""

    def test_get_soc2_controls_config_rule(self):
        """Test getting controls for Config rules."""
        controls = get_soc2_controls("s3-bucket-public-read-prohibited")
        assert "CC6.6" in controls

        controls = get_soc2_controls("iam-password-policy")
        assert "CC6.1" in controls

        controls = get_soc2_controls("encrypted-volumes")
        assert "CC6.5" in controls

    def test_get_soc2_controls_guardduty(self):
        """Test getting controls for GuardDuty finding types."""
        controls = get_soc2_controls("UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration")
        assert "CC6.1" in controls or "CC7.2" in controls

    def test_get_soc2_controls_unknown(self):
        """Test default controls for unknown identifiers."""
        controls = get_soc2_controls("unknown-rule-xyz")
        assert controls == ["CC6.6"]

    def test_get_control_description(self):
        """Test getting control descriptions."""
        desc = get_control_description("CC6.1")
        assert "access" in desc.lower()

        desc = get_control_description("CC7.2")
        assert "monitor" in desc.lower()

        desc = get_control_description("UNKNOWN")
        assert "SOC 2 Control" in desc

    def test_get_controls_for_service(self):
        """Test getting controls for AWS services."""
        controls = get_controls_for_service("s3")
        assert "CC6.5" in controls
        assert "CC6.6" in controls

        controls = get_controls_for_service("iam")
        assert "CC6.1" in controls

        controls = get_controls_for_service("unknown-service")
        assert controls == ["CC6.6"]

    def test_get_controls_for_service_case_insensitive(self):
        """Test service lookup is case insensitive."""
        controls_lower = get_controls_for_service("s3")
        controls_upper = get_controls_for_service("S3")
        assert controls_lower == controls_upper
