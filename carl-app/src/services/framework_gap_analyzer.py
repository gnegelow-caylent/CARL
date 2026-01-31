"""
Framework Gap Analyzer for CARL.

Analyzes compliance gaps between framework requirements and current AWS environment.
Integrates with existing resource_detector for environment scanning.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from services.framework_loader import ComplianceFramework, ServiceConfig
from services.resource_detector import ResourceDetector
from utils.logger import get_logger

logger = get_logger(__name__)


class GapStatus(Enum):
    """Status of a compliance gap."""
    COMPLIANT = "compliant"  # Service exists and meets requirements
    MISSING = "missing"  # Service doesn't exist
    MISCONFIGURED = "misconfigured"  # Service exists but config doesn't meet requirements


@dataclass
class ComplianceViolation:
    """A specific configuration violation."""
    check: str  # The validation check that failed
    failure_message: str  # Why it failed
    current_value: Any = None  # Current configuration value
    required_value: Any = None  # Required configuration value


@dataclass
class ComplianceGap:
    """A compliance gap between required and actual state."""
    service: str  # Service name (e.g., "cloudtrail", "guardduty")
    status: GapStatus
    category: str  # Category from framework (e.g., "logging_monitoring")
    controls: list[str]  # SOC 2 controls affected (e.g., ["CC7.2", "A1.3"])
    why_required: str  # Business explanation
    audit_evidence: list[str]  # What auditors will check

    # For COMPLIANT status
    current_config: dict[str, Any] = field(default_factory=dict)
    resource_arn: Optional[str] = None

    # For MISSING status
    required_config: dict[str, Any] = field(default_factory=dict)
    estimated_monthly_cost: float = 0.0

    # For MISCONFIGURED status
    violations: list[ComplianceViolation] = field(default_factory=list)

    def is_critical(self) -> bool:
        """Check if this gap affects critical security controls."""
        # Controls starting with CC6 (access) or CC7 (monitoring) are critical
        return any(c.startswith(('CC6', 'CC7')) for c in self.controls)


@dataclass
class FrameworkGapAnalysis:
    """Complete gap analysis results."""
    framework_id: str
    framework_name: str
    gaps: list[ComplianceGap]
    scan_timestamp: str
    account_id: str
    region: str

    @property
    def compliant_count(self) -> int:
        """Number of compliant services."""
        return len([g for g in self.gaps if g.status == GapStatus.COMPLIANT])

    @property
    def missing_count(self) -> int:
        """Number of missing services."""
        return len([g for g in self.gaps if g.status == GapStatus.MISSING])

    @property
    def misconfigured_count(self) -> int:
        """Number of misconfigured services."""
        return len([g for g in self.gaps if g.status == GapStatus.MISCONFIGURED])

    @property
    def total_services(self) -> int:
        """Total number of services checked."""
        return len(self.gaps)

    @property
    def compliance_percentage(self) -> float:
        """Percentage of compliant services."""
        if self.total_services == 0:
            return 0.0
        return (self.compliant_count / self.total_services) * 100

    @property
    def critical_gaps(self) -> list[ComplianceGap]:
        """Get only critical gaps (affecting CC6/CC7 controls)."""
        return [g for g in self.gaps if g.is_critical() and g.status != GapStatus.COMPLIANT]

    @property
    def estimated_cost_to_fix(self) -> float:
        """Estimated monthly cost to fix all missing services."""
        return sum(
            g.estimated_monthly_cost for g in self.gaps
            if g.status == GapStatus.MISSING
        )


class FrameworkGapAnalyzer:
    """
    Analyzes compliance gaps between framework requirements and AWS environment.

    Uses existing resource_detector for environment scanning.
    """

    def __init__(self, resource_detector: Optional[ResourceDetector] = None):
        """Initialize the gap analyzer."""
        self.detector = resource_detector or ResourceDetector()
        logger.info("FrameworkGapAnalyzer initialized")

    def analyze(
        self,
        framework: ComplianceFramework,
        account_id: str = "unknown",
        region: str = "us-east-1"
    ) -> FrameworkGapAnalysis:
        """
        Analyze compliance gaps for a framework.

        Args:
            framework: Compliance framework to check against
            account_id: AWS account ID being analyzed
            region: Primary AWS region

        Returns:
            FrameworkGapAnalysis with all gaps identified
        """
        logger.info(f"Starting gap analysis for framework: {framework.name}")

        # Scan current AWS environment
        current_resources = self.detector.scan()
        logger.info(f"Scanned AWS environment, found {len(current_resources)} resource types")

        # Analyze each required service
        gaps = []
        for category, service_configs in framework.required_services.items():
            for service_config in service_configs:
                gap = self._analyze_service(service_config, current_resources, category)
                gaps.append(gap)

        # Create analysis result
        from datetime import datetime
        analysis = FrameworkGapAnalysis(
            framework_id=framework.id,
            framework_name=framework.name,
            gaps=gaps,
            scan_timestamp=datetime.utcnow().isoformat(),
            account_id=account_id,
            region=region
        )

        logger.info(
            f"Gap analysis complete: {analysis.compliant_count} compliant, "
            f"{analysis.missing_count} missing, "
            f"{analysis.misconfigured_count} misconfigured"
        )

        return analysis

    def _analyze_service(
        self,
        service_config: ServiceConfig,
        current_resources: dict[str, Any],
        category: str
    ) -> ComplianceGap:
        """
        Analyze a single service for compliance.

        Args:
            service_config: Required service configuration from framework
            current_resources: Current AWS resources from scan
            category: Framework category (e.g., "logging_monitoring")

        Returns:
            ComplianceGap for this service
        """
        service_name = service_config.service

        # Check if service exists
        if service_name not in current_resources:
            # Service is missing
            return ComplianceGap(
                service=service_name,
                status=GapStatus.MISSING,
                category=category,
                controls=service_config.controls,
                why_required=service_config.why_required,
                audit_evidence=service_config.audit_evidence,
                required_config=service_config.config,
                estimated_monthly_cost=self._estimate_service_cost(service_name)
            )

        # Service exists - check configuration
        current_config = current_resources[service_name]

        # Run validation checks
        violations = self._validate_service_config(
            service_config,
            current_config
        )

        if violations:
            # Service is misconfigured
            return ComplianceGap(
                service=service_name,
                status=GapStatus.MISCONFIGURED,
                category=category,
                controls=service_config.controls,
                why_required=service_config.why_required,
                audit_evidence=service_config.audit_evidence,
                current_config=current_config,
                required_config=service_config.config,
                violations=violations,
                resource_arn=current_config.get('arn'),
                estimated_monthly_cost=0.0  # No additional cost, just config change
            )

        # Service is compliant
        return ComplianceGap(
            service=service_name,
            status=GapStatus.COMPLIANT,
            category=category,
            controls=service_config.controls,
            why_required=service_config.why_required,
            audit_evidence=service_config.audit_evidence,
            current_config=current_config,
            resource_arn=current_config.get('arn')
        )

    def _validate_service_config(
        self,
        service_config: ServiceConfig,
        current_config: dict[str, Any]
    ) -> list[ComplianceViolation]:
        """
        Validate service configuration against requirements.

        Args:
            service_config: Required configuration from framework
            current_config: Current configuration from AWS

        Returns:
            List of violations (empty if compliant)
        """
        violations = []

        # Run validation checks from framework YAML
        for check_def in service_config.validation_checks:
            check_expr = check_def['check']
            failure_msg = check_def['failure']

            # Parse and evaluate check
            violation = self._evaluate_check(check_expr, service_config, current_config)
            if violation:
                violations.append(ComplianceViolation(
                    check=check_expr,
                    failure_message=failure_msg,
                    current_value=violation.get('current'),
                    required_value=violation.get('required')
                ))

        return violations

    def _evaluate_check(
        self,
        check_expr: str,
        service_config: ServiceConfig,
        current_config: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """
        Evaluate a validation check expression.

        Supports expressions like:
        - "retention >= 2555 days"
        - "multi_region == true"
        - "enabled for all VPCs"
        - "all console users have MFA"

        Args:
            check_expr: Check expression from framework YAML
            service_config: Required configuration
            current_config: Current configuration

        Returns:
            Violation details if check fails, None if passes
        """
        # CloudTrail retention check
        if "retention >= " in check_expr:
            required_days = int(check_expr.split(">=")[1].strip().split()[0])
            current_days = current_config.get('retention_days', 0)

            if current_days < required_days:
                return {
                    'current': f"{current_days} days",
                    'required': f"{required_days} days"
                }

        # Boolean checks (multi_region, enabled, etc.)
        elif "==" in check_expr:
            parts = check_expr.split("==")
            field = parts[0].strip()
            expected = parts[1].strip().lower() == "true"

            current_value = current_config.get(field, False)
            if current_value != expected:
                return {
                    'current': str(current_value),
                    'required': str(expected)
                }

        # "enabled for all VPCs" check
        elif "enabled for all VPCs" in check_expr:
            if not current_config.get('enabled_for_all_vpcs', False):
                return {
                    'current': "Not enabled for all VPCs",
                    'required': "Enabled for all VPCs"
                }

        # "all console users have MFA" check
        elif "all console users have MFA" in check_expr:
            if not current_config.get('all_users_have_mfa', False):
                return {
                    'current': "Some users without MFA",
                    'required': "All users require MFA"
                }

        # "detector enabled" check (GuardDuty, Inspector)
        elif "detector enabled" in check_expr or "inspector enabled" in check_expr:
            if not current_config.get('enabled', False):
                return {
                    'current': "Disabled",
                    'required': "Enabled"
                }

        # "recorder enabled" check (Config)
        elif "recorder enabled" in check_expr:
            if not current_config.get('recorder_enabled', False):
                return {
                    'current': "Config recorder not enabled",
                    'required': "Config recorder enabled"
                }

        # "all_supported_resources" check
        elif "all_supported_resources == true" in check_expr:
            if not current_config.get('all_supported_resources', False):
                return {
                    'current': "Recording limited resources",
                    'required': "Recording all supported resources"
                }

        # "hub enabled" check (Security Hub)
        elif "hub enabled" in check_expr:
            if not current_config.get('hub_enabled', False):
                return {
                    'current': "Security Hub not enabled",
                    'required': "Security Hub enabled"
                }

        # "standards enabled" check
        elif "standards enabled" in check_expr:
            if not current_config.get('standards_enabled', False):
                return {
                    'current': "Standards not enabled",
                    'required': "CIS + AWS Foundational standards enabled"
                }

        # "rotation enabled" check (KMS)
        elif "rotation enabled" in check_expr:
            if not current_config.get('rotation_enabled', False):
                return {
                    'current': "Key rotation disabled",
                    'required': "Key rotation enabled"
                }

        # "encryption enabled on all buckets" check
        elif "encryption enabled on all buckets" in check_expr:
            if not current_config.get('all_buckets_encrypted', False):
                return {
                    'current': "Some unencrypted buckets",
                    'required': "All buckets encrypted"
                }

        # "all RDS instances encrypted" check
        elif "all RDS instances encrypted" in check_expr:
            if not current_config.get('all_rds_encrypted', False):
                return {
                    'current': "Some unencrypted RDS instances",
                    'required': "All RDS instances encrypted"
                }

        # "encryption_by_default" check (EBS)
        elif "encryption_by_default == true" in check_expr:
            if not current_config.get('encryption_by_default', False):
                return {
                    'current': "EBS encryption by default disabled",
                    'required': "EBS encryption by default enabled"
                }

        # "all data sources enabled" check (GuardDuty)
        elif "all data sources enabled" in check_expr:
            required_sources = ['s3', 'eks', 'malware', 'rds']
            current_sources = current_config.get('enabled_data_sources', [])
            missing = [s for s in required_sources if s not in current_sources]

            if missing:
                return {
                    'current': f"Missing: {', '.join(missing)}",
                    'required': "S3, EKS, Malware, RDS protection all enabled"
                }

        # No violation
        return None

    def _estimate_service_cost(self, service_name: str) -> float:
        """
        Estimate monthly cost for a service.

        These are baseline estimates for small accounts.
        """
        cost_estimates = {
            'cloudtrail': 0.0,  # Management events are free
            'vpc_flow_logs': 10.0,  # Depends on traffic
            'guardduty': 1.0,  # ~$0.50-2/month
            'config': 2.0,  # Recorder + rules
            'security_hub': 0.0,  # No charge for hub itself
            'inspector': 1.0,  # Pay per scan
            'kms': 1.0,  # $1/month per key
            'iam_password_policy': 0.0,  # Free
            'iam_mfa': 0.0,  # Free
            's3_encryption': 0.0,  # Free (KMS key cost separate)
            'ebs_encryption': 0.0,  # Free
            'rds_encryption': 0.0,  # Free (no additional cost)
        }

        return cost_estimates.get(service_name, 0.0)


# Singleton instance
_gap_analyzer: Optional[FrameworkGapAnalyzer] = None


def get_gap_analyzer() -> FrameworkGapAnalyzer:
    """Get or create the global gap analyzer instance."""
    global _gap_analyzer
    if _gap_analyzer is None:
        _gap_analyzer = FrameworkGapAnalyzer()
    return _gap_analyzer
