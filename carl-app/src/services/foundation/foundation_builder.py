"""
Foundation Builder Service for CARL.

Orchestrates the generation of compliant AWS foundation infrastructure.

Per CLAUDE.md: No static Terraform templates - AI generates dynamically using
architecture patterns as grounding context.
"""

from dataclasses import dataclass
from typing import Any

from .decision_engine import DecisionSession, DecisionResult
from knowledge.aws_pricing import (
    calculate_monthly_cost,
    Region,
    NETWORKING_PRICING,
    VPN_PRICING,
    SECURITY_PRICING,
    LANDING_ZONE_PRICING,
)
from services.architecture_tools import generate_terraform_code


@dataclass
class TerraformModule:
    """Represents a generated Terraform module."""
    name: str
    path: str
    content: str
    variables: dict[str, Any]
    description: str
    estimated_monthly_cost: float

    # Framework-aware additions (NEW)
    compliance_controls: list[str] = None  # e.g., ["CC7.2", "A1.3"]
    why_required: str = ""  # Business explanation
    audit_evidence: list[str] = None  # What auditors check
    gap_status: str = ""  # "missing", "misconfigured", or empty for pattern-based

    def __post_init__(self):
        """Initialize default values for list fields."""
        if self.compliance_controls is None:
            self.compliance_controls = []
        if self.audit_evidence is None:
            self.audit_evidence = []


class FoundationBuilder:
    """
    Builds AWS foundation infrastructure based on decisions.

    Generates Terraform modules for:
    - VPC networking (egress, ingress, transit)
    - Security services (WAF, Network Firewall, GuardDuty, etc.)
    - Connectivity (VPN, Direct Connect)
    - Landing zone (Control Tower, AFT)
    """

    def __init__(self):
        self.templates: dict[str, str] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load Terraform templates for each component."""
        # Templates are embedded here for simplicity
        # In production, these would be loaded from files
        pass

    def generate_foundation(self, session: DecisionSession) -> list[TerraformModule]:
        """Generate Terraform modules based on session decisions."""
        modules = []

        for decision in session.decisions:
            module = self._generate_module_for_decision(decision, session)
            if module:
                modules.append(module)

        # Add base security services module
        security_module = self._generate_security_services_module(session)
        modules.append(security_module)

        return modules

    def _generate_module_for_decision(
        self,
        decision: DecisionResult,
        session: DecisionSession,
    ) -> TerraformModule | None:
        """Generate Terraform module for a specific decision."""

        # Pattern-based generators (networking, VPN)
        generators = {
            "egress": self._generate_egress_module,
            "ingress": self._generate_ingress_module,
            "transit": self._generate_transit_module,
            "site_to_site_vpn": self._generate_site_vpn_module,
            "client_vpn": self._generate_client_vpn_module,
        }

        # Check if this is a pattern-based decision
        if decision.category in generators:
            module = generators[decision.category](decision, session)
            # Add compliance metadata if available
            if module and decision.compliance_controls:
                module.compliance_controls = decision.compliance_controls
                module.why_required = decision.why_required
                module.audit_evidence = decision.audit_evidence
                module.gap_status = decision.gap_status
                # Prepend compliance header to content
                module.content = self._add_compliance_header(module.content, decision)
            return module

        # Framework mode: Handle compliance services (cloudtrail, guardduty, etc.)
        if session.framework_mode:
            return self._generate_compliance_service_module(decision, session)

        return None

    def _generate_egress_module(
        self,
        decision: DecisionResult,
        session: DecisionSession,
    ) -> TerraformModule:
        """Generate egress/NAT module using AI-driven generation."""
        option_name = decision.selected_option.name
        vpc_count = session.requirements.get("vpc_count", 1)

        # Determine egress type from decision
        if "Distributed" in option_name:
            egress_type = "distributed_nat"
            estimated_cost = 100.0 * vpc_count
        elif "Centralized NAT" in option_name:
            egress_type = "centralized_nat"
            estimated_cost = 150.0 + 36.0 * vpc_count
        else:  # Network Firewall
            egress_type = "network_firewall"
            estimated_cost = 850.0 + 36.0 * vpc_count

        # Use AI-driven generation with architecture patterns as grounding
        result = generate_terraform_code(
            module_type="egress",
            requirements={
                "egress_type": egress_type,
                "vpc_count": vpc_count,
                "availability_zones": 2,
            },
            compliance_framework="SOC2",
        )

        content = result.get("content", "# Error generating egress module")

        return TerraformModule(
            name="egress",
            path="modules/networking/egress",
            content=content,
            variables={
                "vpc_count": vpc_count,
                "az_count": 2,
            },
            description=f"Egress architecture: {option_name}",
            estimated_monthly_cost=estimated_cost,
        )

    def _generate_ingress_module(
        self,
        decision: DecisionResult,
        session: DecisionSession,
    ) -> TerraformModule:
        """Generate ingress module using AI-driven generation."""
        option_name = decision.selected_option.name

        # Determine ingress type from decision
        if "Distributed" in option_name:
            ingress_type = "distributed_alb"
            estimated_cost = 50.0
        elif "Centralized" in option_name:
            ingress_type = "centralized_alb"
            estimated_cost = 200.0
        else:  # CloudFront
            ingress_type = "cloudfront"
            estimated_cost = 100.0

        # Use AI-driven generation
        result = generate_terraform_code(
            module_type="ingress",
            requirements={
                "ingress_type": ingress_type,
                "enable_waf": True,
                "waf_rules": ["AWSManagedRulesCommonRuleSet"],
            },
            compliance_framework="SOC2",
        )

        content = result.get("content", "# Error generating ingress module")

        return TerraformModule(
            name="ingress",
            path="modules/networking/ingress",
            content=content,
            variables={
                "enable_waf": True,
                "waf_rules": ["AWSManagedRulesCommonRuleSet"],
            },
            description=f"Ingress architecture: {option_name}",
            estimated_monthly_cost=estimated_cost,
        )

    def _generate_transit_module(
        self,
        decision: DecisionResult,
        session: DecisionSession,
    ) -> TerraformModule:
        """Generate transit module using AI-driven generation."""
        option_name = decision.selected_option.name
        vpc_count = session.requirements.get("vpc_count", 1)

        # Determine transit type from decision
        if "Peering" in option_name:
            transit_type = "vpc_peering"
            estimated_cost = 10.0
        elif "Transit Gateway" in option_name:
            transit_type = "transit_gateway"
            estimated_cost = 36.0 * vpc_count
        elif "Cloud WAN" in option_name:
            transit_type = "cloud_wan"
            estimated_cost = 50.0 * vpc_count
        else:
            transit_type = "none"
            estimated_cost = 0.0

        # Use AI-driven generation
        result = generate_terraform_code(
            module_type="transit",
            requirements={
                "transit_type": transit_type,
                "vpc_count": vpc_count,
            },
            compliance_framework="SOC2",
        )

        content = result.get("content", "# No transit module needed for isolated VPCs")

        return TerraformModule(
            name="transit",
            path="modules/networking/transit",
            content=content,
            variables={
                "vpc_count": vpc_count,
            },
            description=f"Transit architecture: {option_name}",
            estimated_monthly_cost=estimated_cost,
        )

    def _generate_site_vpn_module(
        self,
        decision: DecisionResult,
        session: DecisionSession,
    ) -> TerraformModule:
        """Generate site-to-site VPN module using AI-driven generation."""
        option_name = decision.selected_option.name

        # Determine connectivity type from decision
        if "Direct Connect" in option_name:
            connectivity_type = "direct_connect"
            estimated_cost = 500.0
        elif "Accelerated" in option_name:
            connectivity_type = "accelerated_vpn"
            estimated_cost = 100.0
        else:
            connectivity_type = "site_to_site_vpn"
            estimated_cost = 72.0

        # Use AI-driven generation
        result = generate_terraform_code(
            module_type="site_vpn",
            requirements={
                "connectivity_type": connectivity_type,
                "customer_gateway_ip": "REPLACE_WITH_YOUR_IP",
                "bgp_asn": 65000,
            },
            compliance_framework="SOC2",
        )

        content = result.get("content", "# Error generating site VPN module")

        return TerraformModule(
            name="site_vpn",
            path="modules/connectivity/site-vpn",
            content=content,
            variables={
                "customer_gateway_ip": "REPLACE_WITH_YOUR_IP",
                "bgp_asn": 65000,
            },
            description=f"Site connectivity: {option_name}",
            estimated_monthly_cost=estimated_cost,
        )

    def _generate_client_vpn_module(
        self,
        decision: DecisionResult,
        session: DecisionSession,
    ) -> TerraformModule:
        """Generate client VPN module using AI-driven generation."""
        option_name = decision.selected_option.name
        remote_users = session.requirements.get("remote_users", "small")

        # Determine VPN type from decision
        if "Third-Party" in option_name or "Self" in option_name:
            vpn_type = "self_managed"
            estimated_cost = 100.0
        else:
            vpn_type = "aws_client_vpn"
            if remote_users == "small":
                estimated_cost = 200.0
            elif remote_users == "medium":
                estimated_cost = 400.0
            else:
                estimated_cost = 600.0

        # Use AI-driven generation
        result = generate_terraform_code(
            module_type="client_vpn",
            requirements={
                "vpn_type": vpn_type,
                "client_cidr": "10.100.0.0/16",
                "target_network_cidr": "10.0.0.0/8",
                "remote_users": remote_users,
            },
            compliance_framework="SOC2",
        )

        content = result.get("content", "# Error generating client VPN module")

        return TerraformModule(
            name="client_vpn",
            path="modules/connectivity/client-vpn",
            content=content,
            variables={
                "client_cidr": "10.100.0.0/16",
                "target_network_cidr": "10.0.0.0/8",
            },
            description=f"Remote access: {option_name}",
            estimated_monthly_cost=estimated_cost,
        )

    def _generate_security_services_module(
        self,
        session: DecisionSession,
    ) -> TerraformModule:
        """Generate security services module using AI-driven generation."""
        compliance = session.requirements.get("compliance_requirements", ["soc2"])

        # Estimate cost based on compliance requirements
        estimated_cost = 50.0  # Base security stack
        if "hipaa" in compliance or "pci_dss" in compliance:
            estimated_cost += 50.0  # Additional services

        # Use AI-driven generation
        result = generate_terraform_code(
            module_type="security_services",
            requirements={
                "enable_guardduty": True,
                "enable_security_hub": True,
                "enable_config": True,
                "enable_inspector": True,
                "enable_macie": "hipaa" in compliance,
                "compliance_requirements": compliance,
            },
            compliance_framework="SOC2",
        )

        content = result.get("content", "# Error generating security services module")

        return TerraformModule(
            name="security",
            path="modules/security/services",
            content=content,
            variables={
                "enable_guardduty": True,
                "enable_security_hub": True,
                "enable_config": True,
                "enable_inspector": True,
            },
            description="Security services stack for SOC 2 compliance",
            estimated_monthly_cost=estimated_cost,
        )

    def _add_compliance_header(self, content: str, decision: DecisionResult) -> str:
        """
        Add compliance metadata header to Terraform content (NEW).

        Generates comments at top of file with control mappings and audit evidence.
        """
        if not decision.compliance_controls:
            return content

        header_lines = []

        # Control mappings
        if decision.compliance_controls:
            controls_str = ", ".join(decision.compliance_controls)
            header_lines.append(f"# Compliance Controls: {controls_str}")

        # Why required
        if decision.why_required:
            # Wrap long lines
            import textwrap
            wrapped = textwrap.fill(
                decision.why_required,
                width=75,
                initial_indent="# Why Required: ",
                subsequent_indent="#               "
            )
            header_lines.append(wrapped)

        # Audit evidence
        if decision.audit_evidence:
            header_lines.append("#")
            header_lines.append("# Auditor Evidence:")
            for evidence in decision.audit_evidence:
                header_lines.append(f"#   - {evidence}")

        # Gap status
        if decision.gap_status:
            header_lines.append("#")
            header_lines.append(f"# Gap Status: {decision.gap_status.upper()}")

        header_lines.append("")

        return "\n".join(header_lines) + "\n" + content

    def _generate_compliance_service_module(
        self,
        decision: DecisionResult,
        session: DecisionSession
    ) -> TerraformModule:
        """
        Generate Terraform for compliance services (NEW).

        Handles CloudTrail, GuardDuty, Config, Security Hub, Inspector, etc.
        These services don't map to architecture patterns but are required by framework.
        """
        service_name = decision.category
        config = decision.custom_configuration

        # Map service names to Terraform generators
        service_generators = {
            "cloudtrail": self._generate_cloudtrail_terraform,
            "guardduty": self._generate_guardduty_terraform,
            "config": self._generate_config_terraform,
            "security_hub": self._generate_security_hub_terraform,
            "inspector": self._generate_inspector_terraform,
            "vpc_flow_logs": self._generate_vpc_flow_logs_terraform,
            "iam_password_policy": self._generate_iam_password_policy_terraform,
            "kms": self._generate_kms_terraform,
        }

        generator = service_generators.get(service_name)
        if not generator:
            # Fallback: Create minimal module
            return TerraformModule(
                name=service_name,
                path=f"modules/compliance/{service_name}",
                content=f"# {service_name} - TODO: Implement Terraform\n",
                variables={},
                description=f"Compliance service: {service_name}",
                estimated_monthly_cost=decision.selected_option.estimated_monthly_cost,
                compliance_controls=decision.compliance_controls,
                why_required=decision.why_required,
                audit_evidence=decision.audit_evidence,
                gap_status=decision.gap_status
            )

        # Generate Terraform content
        content = generator(config, session)

        # Add compliance header
        content = self._add_compliance_header(content, decision)

        return TerraformModule(
            name=service_name,
            path=f"modules/compliance/{service_name}",
            content=content,
            variables=config,
            description=decision.selected_option.description,
            estimated_monthly_cost=decision.selected_option.estimated_monthly_cost,
            compliance_controls=decision.compliance_controls,
            why_required=decision.why_required,
            audit_evidence=decision.audit_evidence,
            gap_status=decision.gap_status
        )

    def _generate_cloudtrail_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate CloudTrail Terraform with SOC 2 configuration using AI."""
        result = generate_terraform_code(
            module_type="cloudtrail",
            requirements={
                "multi_region": config.get("multi_region", True),
                "is_organization_trail": config.get("is_organization_trail", False),
                "enable_log_validation": config.get("log_validation", True),
                "retention_days": config.get("retention_days", 2555),
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating CloudTrail module")

    def _generate_guardduty_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate GuardDuty Terraform using AI."""
        result = generate_terraform_code(
            module_type="security_services",
            requirements={
                "enable_guardduty": True,
                "enable_security_hub": False,
                "enable_config": False,
                "enable_inspector": False,
                "guardduty_only": True,
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating GuardDuty module")

    def _generate_config_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate AWS Config Terraform using AI."""
        result = generate_terraform_code(
            module_type="config_rules",
            requirements={
                "enable_org_rules": config.get("enable_org_rules", True),
                "all_supported": True,
                "include_global_resources": True,
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating AWS Config module")

    def _generate_security_hub_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate Security Hub Terraform using AI."""
        result = generate_terraform_code(
            module_type="security_services",
            requirements={
                "enable_guardduty": False,
                "enable_security_hub": True,
                "enable_config": False,
                "enable_inspector": False,
                "security_hub_only": True,
                "enable_cis_standard": True,
                "enable_fsbp_standard": True,
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating Security Hub module")

    def _generate_inspector_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate Inspector Terraform using AI."""
        result = generate_terraform_code(
            module_type="security_services",
            requirements={
                "enable_guardduty": False,
                "enable_security_hub": False,
                "enable_config": False,
                "enable_inspector": True,
                "inspector_only": True,
                "resource_types": ["EC2", "ECR", "LAMBDA"],
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating Inspector module")

    def _generate_vpc_flow_logs_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate VPC Flow Logs Terraform using AI."""
        result = generate_terraform_code(
            module_type="vpc",
            requirements={
                "vpc_name": "main",
                "enable_flow_logs": True,
                "flow_logs_only": True,
                "traffic_type": "ALL",
                "log_destination": "s3",
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating VPC Flow Logs module")

    def _generate_iam_password_policy_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate IAM Password Policy Terraform using AI."""
        result = generate_terraform_code(
            module_type="iam_password_policy",
            requirements={
                "minimum_length": config.get("minimum_length", 14),
                "require_uppercase": True,
                "require_lowercase": True,
                "require_numbers": True,
                "require_symbols": True,
                "max_age_days": config.get("max_age_days", 90),
                "reuse_prevention": config.get("reuse_prevention", 24),
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating IAM Password Policy module")

    def _generate_kms_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate KMS key Terraform using AI."""
        result = generate_terraform_code(
            module_type="central_logging_bucket",
            requirements={
                "kms_key_only": True,
                "key_description": config.get("description", "KMS key for data encryption"),
                "enable_key_rotation": True,
                "deletion_window_days": 30,
            },
            compliance_framework="SOC2",
        )
        return result.get("content", "# Error generating KMS module")

    def format_generated_code_summary(
        self,
        modules: list[TerraformModule],
        session: DecisionSession,
    ) -> str:
        """Format summary of generated code for Slack."""
        total_cost = sum(m.estimated_monthly_cost for m in modules)

        # Framework mode: Different header
        if session.framework_mode and session.framework:
            lines = [
                f"*Generated {session.framework.name} Compliance Modules*",
                "",
                f"CARL has generated {len(modules)} Terraform modules to fix compliance gaps:",
                "",
            ]
        else:
            lines = [
                "*Generated Terraform Modules*",
                "",
                f"Based on your selections, CARL has generated {len(modules)} Terraform modules:",
                "",
            ]

        for module in modules:
            # Basic info
            lines.extend([
                f"*{module.name}*",
                f"   Path: `{module.path}/`",
                f"   {module.description}",
            ])

            # Compliance metadata (if available)
            if module.compliance_controls:
                controls_str = ", ".join(module.compliance_controls)
                lines.append(f"   Controls: {controls_str}")

            # Gap status
            if module.gap_status:
                status_emoji = "❌" if module.gap_status == "missing" else "⚠️"
                lines.append(f"   Status: {status_emoji} {module.gap_status.upper()}")

            # Cost
            if module.estimated_monthly_cost > 0:
                lines.append(f"   Est. Cost: ${module.estimated_monthly_cost:.2f}/mo")
            else:
                lines.append(f"   Est. Cost: $0 (config change only)")

            lines.append("")

        # Framework mode: Show compliance percentage
        if session.framework_mode and session.gap_analysis:
            lines.extend([
                "---",
                f"*Compliance Status:* {session.gap_analysis.compliance_percentage:.1f}% → 100%",
                f"*Modules Generated:* {len(modules)}",
                f"*Total Estimated Monthly Cost:* ${total_cost:.2f}",
            ])
        else:
            lines.extend([
                "---",
                f"*Total Estimated Monthly Cost:* ${total_cost:.0f}",
            "",
            "_The code has been generated with sensible defaults._",
            "_Review and customize variables before deploying._",
            "",
            "Next steps:",
            "1. Review the generated code in the output",
            "2. Update placeholder values (marked with `REPLACE_WITH_*`)",
            "3. Run `terraform init` and `terraform plan`",
            "4. Deploy with `terraform apply`",
        ])

        return "\n".join(lines)
