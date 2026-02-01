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

    # =========================================================================
    # TERRAFORM TEMPLATES
    # =========================================================================

    def _get_distributed_nat_template(self, session: DecisionSession) -> str:
        """Template for distributed NAT (NAT per VPC)."""
        return '''# Distributed NAT Gateway Configuration
# Each VPC has its own NAT Gateway(s) for outbound traffic
#
# Cost estimate: approx. $32.40/mo per NAT Gateway + $0.045/GB processed
# For HA: Deploy one NAT Gateway per AZ (typically 2-3x cost)

variable "vpc_id" {
  description = "VPC ID for NAT Gateway deployment"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for NAT Gateway placement"
  type        = list(string)
}

variable "private_route_table_ids" {
  description = "Private route table IDs to add NAT routes"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Create Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count  = length(var.public_subnet_ids)
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "nat-eip-${count.index + 1}"
  })
}

# Create NAT Gateways (one per AZ for HA)
resource "aws_nat_gateway" "main" {
  count         = length(var.public_subnet_ids)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = var.public_subnet_ids[count.index]

  tags = merge(var.tags, {
    Name = "nat-gateway-${count.index + 1}"
  })

  depends_on = [aws_eip.nat]
}

# Add routes to private route tables
resource "aws_route" "nat" {
  count                  = length(var.private_route_table_ids)
  route_table_id         = var.private_route_table_ids[count.index]
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[count.index % length(aws_nat_gateway.main)].id
}

output "nat_gateway_ids" {
  description = "IDs of NAT Gateways"
  value       = aws_nat_gateway.main[*].id
}

output "nat_gateway_public_ips" {
  description = "Public IPs of NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}
'''

    def _get_centralized_nat_template(self, session: DecisionSession) -> str:
        """Template for centralized NAT (shared egress VPC)."""
        return '''# Centralized NAT Gateway Configuration
# Shared egress VPC with NAT Gateways, connected via Transit Gateway
#
# Cost estimate:
# - Transit Gateway: $36/mo per VPC attachment
# - NAT Gateway: $32.40/mo per gateway (typically 3 for HA)
# - Data processing: $0.02/GB (TGW) + $0.045/GB (NAT)

variable "egress_vpc_cidr" {
  description = "CIDR block for egress VPC"
  type        = string
  default     = "10.255.0.0/24"
}

variable "availability_zones" {
  description = "Availability zones for deployment"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "transit_gateway_id" {
  description = "Transit Gateway ID for connectivity"
  type        = string
}

variable "spoke_vpc_cidrs" {
  description = "CIDR blocks of spoke VPCs to route through egress"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Egress VPC
resource "aws_vpc" "egress" {
  cidr_block           = var.egress_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "egress-vpc"
    Purpose = "Centralized egress for NAT"
  })
}

# Public subnets for NAT Gateways
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.egress.id
  cidr_block              = cidrsubnet(var.egress_vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "egress-public-${var.availability_zones[count.index]}"
    Tier = "public"
  })
}

# Private subnets for TGW attachment
resource "aws_subnet" "tgw" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.egress.id
  cidr_block        = cidrsubnet(var.egress_vpc_cidr, 4, count.index + length(var.availability_zones))
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "egress-tgw-${var.availability_zones[count.index]}"
    Tier = "transit-gateway"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "egress" {
  vpc_id = aws_vpc.egress.id

  tags = merge(var.tags, {
    Name = "egress-igw"
  })
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "egress-nat-eip-${count.index + 1}"
  })
}

# NAT Gateways
resource "aws_nat_gateway" "main" {
  count         = length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.tags, {
    Name = "egress-nat-${var.availability_zones[count.index]}"
  })

  depends_on = [aws_internet_gateway.egress]
}

# Transit Gateway Attachment
resource "aws_ec2_transit_gateway_vpc_attachment" "egress" {
  subnet_ids         = aws_subnet.tgw[*].id
  transit_gateway_id = var.transit_gateway_id
  vpc_id             = aws_vpc.egress.id

  tags = merge(var.tags, {
    Name = "egress-vpc-attachment"
  })
}

# Route tables and routes
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.egress.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.egress.id
  }

  # Routes back to spoke VPCs via TGW
  dynamic "route" {
    for_each = var.spoke_vpc_cidrs
    content {
      cidr_block         = route.value
      transit_gateway_id = var.transit_gateway_id
    }
  }

  tags = merge(var.tags, {
    Name = "egress-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# TGW subnet route table (routes to NAT)
resource "aws_route_table" "tgw" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.egress.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = merge(var.tags, {
    Name = "egress-tgw-rt-${var.availability_zones[count.index]}"
  })
}

resource "aws_route_table_association" "tgw" {
  count          = length(aws_subnet.tgw)
  subnet_id      = aws_subnet.tgw[count.index].id
  route_table_id = aws_route_table.tgw[count.index].id
}

output "egress_vpc_id" {
  value = aws_vpc.egress.id
}

output "nat_gateway_public_ips" {
  value = aws_eip.nat[*].public_ip
}

output "tgw_attachment_id" {
  value = aws_ec2_transit_gateway_vpc_attachment.egress.id
}
'''

    def _get_network_firewall_template(self, session: DecisionSession) -> str:
        """Template for AWS Network Firewall inspection."""
        return '''# AWS Network Firewall Configuration
# Centralized egress with traffic inspection
#
# Cost estimate:
# - Firewall endpoints: $284.40/mo each (need 2-3 for HA)
# - Data processing: $0.065/GB inspected
# - Plus Transit Gateway and NAT Gateway costs

variable "inspection_vpc_cidr" {
  description = "CIDR block for inspection VPC"
  type        = string
  default     = "10.254.0.0/24"
}

variable "availability_zones" {
  description = "Availability zones for deployment"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "transit_gateway_id" {
  description = "Transit Gateway ID"
  type        = string
}

variable "spoke_vpc_cidrs" {
  description = "CIDR blocks of spoke VPCs"
  type        = list(string)
}

variable "blocked_domains" {
  description = "Domains to block in egress traffic"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Inspection VPC
resource "aws_vpc" "inspection" {
  cidr_block           = var.inspection_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "inspection-vpc"
    Purpose = "Centralized traffic inspection"
  })
}

# Subnet tiers: public (NAT), firewall, TGW
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.inspection.id
  cidr_block              = cidrsubnet(var.inspection_vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "inspection-public-${var.availability_zones[count.index]}"
    Tier = "public"
  })
}

resource "aws_subnet" "firewall" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.inspection.id
  cidr_block        = cidrsubnet(var.inspection_vpc_cidr, 4, count.index + 4)
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "inspection-firewall-${var.availability_zones[count.index]}"
    Tier = "firewall"
  })
}

resource "aws_subnet" "tgw" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.inspection.id
  cidr_block        = cidrsubnet(var.inspection_vpc_cidr, 4, count.index + 8)
  availability_zone = var.availability_zones[count.index]

  tags = merge(var.tags, {
    Name = "inspection-tgw-${var.availability_zones[count.index]}"
    Tier = "transit-gateway"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "inspection" {
  vpc_id = aws_vpc.inspection.id

  tags = merge(var.tags, {
    Name = "inspection-igw"
  })
}

# NAT Gateways
resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"

  tags = merge(var.tags, {
    Name = "inspection-nat-eip-${count.index + 1}"
  })
}

resource "aws_nat_gateway" "main" {
  count         = length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.tags, {
    Name = "inspection-nat-${var.availability_zones[count.index]}"
  })

  depends_on = [aws_internet_gateway.inspection]
}

# Network Firewall
resource "aws_networkfirewall_firewall" "main" {
  name                = "central-inspection-firewall"
  firewall_policy_arn = aws_networkfirewall_firewall_policy.main.arn
  vpc_id              = aws_vpc.inspection.id

  dynamic "subnet_mapping" {
    for_each = aws_subnet.firewall
    content {
      subnet_id = subnet_mapping.value.id
    }
  }

  tags = merge(var.tags, {
    Name = "central-inspection-firewall"
  })
}

# Firewall Policy
resource "aws_networkfirewall_firewall_policy" "main" {
  name = "central-inspection-policy"

  firewall_policy {
    stateless_default_actions          = ["aws:forward_to_sfe"]
    stateless_fragment_default_actions = ["aws:forward_to_sfe"]

    stateful_rule_group_reference {
      resource_arn = aws_networkfirewall_rule_group.domain_block.arn
    }

    stateful_rule_group_reference {
      resource_arn = aws_networkfirewall_rule_group.threat_signatures.arn
    }
  }

  tags = var.tags
}

# Domain blocking rule group
resource "aws_networkfirewall_rule_group" "domain_block" {
  capacity = 100
  name     = "block-malicious-domains"
  type     = "STATEFUL"

  rule_group {
    rules_source {
      rules_source_list {
        generated_rules_type = "DENYLIST"
        target_types         = ["HTTP_HOST", "TLS_SNI"]
        targets              = length(var.blocked_domains) > 0 ? var.blocked_domains : [".malware.example.com"]
      }
    }
  }

  tags = var.tags
}

# AWS managed threat signatures
resource "aws_networkfirewall_rule_group" "threat_signatures" {
  capacity = 1000
  name     = "threat-signatures"
  type     = "STATEFUL"

  rule_group {
    rules_source {
      stateful_rule {
        action = "ALERT"
        header {
          destination      = "ANY"
          destination_port = "ANY"
          direction        = "ANY"
          protocol         = "TCP"
          source           = "ANY"
          source_port      = "ANY"
        }
        rule_option {
          keyword  = "sid"
          settings = ["1"]
        }
      }
    }
  }

  tags = var.tags
}

# Transit Gateway Attachment
resource "aws_ec2_transit_gateway_vpc_attachment" "inspection" {
  subnet_ids                                      = aws_subnet.tgw[*].id
  transit_gateway_id                              = var.transit_gateway_id
  vpc_id                                          = aws_vpc.inspection.id
  appliance_mode_support                          = "enable"

  tags = merge(var.tags, {
    Name = "inspection-vpc-attachment"
  })
}

# CloudWatch Log Group for firewall logs
resource "aws_cloudwatch_log_group" "firewall" {
  name              = "/aws/network-firewall/central-inspection"
  retention_in_days = 90

  tags = var.tags
}

# Firewall logging configuration
resource "aws_networkfirewall_logging_configuration" "main" {
  firewall_arn = aws_networkfirewall_firewall.main.arn

  logging_configuration {
    log_destination_config {
      log_destination = {
        logGroup = aws_cloudwatch_log_group.firewall.name
      }
      log_destination_type = "CloudWatchLogs"
      log_type             = "ALERT"
    }

    log_destination_config {
      log_destination = {
        logGroup = aws_cloudwatch_log_group.firewall.name
      }
      log_destination_type = "CloudWatchLogs"
      log_type             = "FLOW"
    }
  }
}

output "firewall_id" {
  value = aws_networkfirewall_firewall.main.id
}

output "firewall_endpoint_ids" {
  value = [for s in aws_networkfirewall_firewall.main.firewall_status[0].sync_states : s.attachment[0].endpoint_id]
}

output "inspection_vpc_id" {
  value = aws_vpc.inspection.id
}
'''

    def _get_distributed_alb_template(self, session: DecisionSession) -> str:
        """Template for distributed ALB (ALB per VPC)."""
        return '''# Distributed ALB Configuration
# Each VPC has its own ALB for inbound traffic
#
# Cost estimate:
# - ALB: $16.20/mo base + approx. $10-50/mo LCU charges
# - WAF: $5/mo + $1/rule + $0.60/million requests

variable "vpc_id" {
  description = "VPC ID for ALB deployment"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB placement"
  type        = list(string)
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
}

variable "enable_waf" {
  description = "Enable WAF protection"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  name        = "alb-security-group"
  description = "Security group for Application Load Balancer"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP for redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "alb-sg"
  })
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "main-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = true
  drop_invalid_header_fields = true

  tags = merge(var.tags, {
    Name = "main-alb"
  })
}

# HTTPS Listener
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Not Found"
      status_code  = "404"
    }
  }
}

# HTTP to HTTPS Redirect
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# WAF Web ACL
resource "aws_wafv2_web_acl" "main" {
  count       = var.enable_waf ? 1 : 0
  name        = "alb-waf-acl"
  description = "WAF ACL for ALB protection"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # AWS Managed Rules - Common Rule Set
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesCommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules - Known Bad Inputs
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "AWSManagedRulesKnownBadInputsRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rate limiting
  rule {
    name     = "RateLimitRule"
    priority = 3

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitRuleMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "ALBWebACLMetric"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

# Associate WAF with ALB
resource "aws_wafv2_web_acl_association" "main" {
  count        = var.enable_waf ? 1 : 0
  resource_arn = aws_lb.main.arn
  web_acl_arn  = aws_wafv2_web_acl.main[0].arn
}

output "alb_arn" {
  value = aws_lb.main.arn
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "alb_zone_id" {
  value = aws_lb.main.zone_id
}

output "https_listener_arn" {
  value = aws_lb_listener.https.arn
}
'''

    def _get_centralized_ingress_template(self, session: DecisionSession) -> str:
        """Template for centralized ingress VPC."""
        return '''# Centralized Ingress VPC Configuration
# Shared ingress VPC with ALB, WAF, and optional Network Firewall
#
# Cost estimate:
# - ALB: $16.20/mo + LCU charges
# - WAF: $5/mo + rules + requests
# - Transit Gateway: $36/mo per spoke VPC

# Full implementation similar to centralized NAT
# but with public-facing ALB and WAF at the edge

variable "ingress_vpc_cidr" {
  description = "CIDR block for ingress VPC"
  type        = string
  default     = "10.253.0.0/24"
}

# ... (Similar structure to centralized NAT with ALB added)
# This is a placeholder - full implementation would be ~200 lines

output "alb_dns_name" {
  value       = "placeholder"
  description = "DNS name of the centralized ALB"
}
'''

    def _get_cloudfront_template(self, session: DecisionSession) -> str:
        """Template for CloudFront + WAF at edge."""
        return '''# CloudFront + WAF Edge Configuration
# Global distribution with WAF protection at edge locations
#
# Cost estimate:
# - CloudFront: Based on data transfer and requests
# - WAF: $5/mo + $1/rule + $0.60/million requests
# - Often CHEAPER than direct serving for high bandwidth

variable "origin_domain" {
  description = "Domain name of the origin (ALB, S3, etc.)"
  type        = string
}

variable "origin_id" {
  description = "Unique identifier for the origin"
  type        = string
  default     = "primary-origin"
}

variable "certificate_arn" {
  description = "ACM certificate ARN (must be in us-east-1)"
  type        = string
}

variable "domain_names" {
  description = "Domain names for CloudFront distribution"
  type        = list(string)
}

variable "enable_waf" {
  description = "Enable WAF at edge"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Origin Access Control for S3 (if using S3 origin)
resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "main-oac"
  description                       = "OAC for CloudFront distribution"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# CloudFront Distribution
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Main CloudFront distribution"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"  # US, Canada, Europe
  aliases             = var.domain_names
  web_acl_id          = var.enable_waf ? aws_wafv2_web_acl.cloudfront[0].arn : null

  origin {
    domain_name = var.origin_domain
    origin_id   = var.origin_id

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    # Add custom headers to verify requests came through CloudFront
    custom_header {
      name  = "X-Origin-Verify"
      value = "REPLACE_WITH_SECRET"  # Store in Secrets Manager
    }
  }

  default_cache_behavior {
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = var.origin_id

    forwarded_values {
      query_string = true
      headers      = ["Origin", "Authorization"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  # Cache behavior for static assets
  ordered_cache_behavior {
    path_pattern     = "/static/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = var.origin_id

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 86400
    default_ttl            = 604800
    max_ttl                = 31536000
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn            = var.certificate_arn
    ssl_support_method             = "sni-only"
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  # Enable logging
  logging_config {
    include_cookies = false
    bucket          = "REPLACE_WITH_LOG_BUCKET.s3.amazonaws.com"
    prefix          = "cloudfront/"
  }

  tags = var.tags
}

# WAF Web ACL for CloudFront (must be in us-east-1)
resource "aws_wafv2_web_acl" "cloudfront" {
  count       = var.enable_waf ? 1 : 0
  provider    = aws.us_east_1  # WAF for CloudFront must be in us-east-1
  name        = "cloudfront-waf-acl"
  description = "WAF ACL for CloudFront"
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  # AWS Managed Rules - Common Rule Set
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # AWS Managed Rules - IP Reputation
  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "IpReputationMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rate limiting at edge
  rule {
    name     = "RateLimitRule"
    priority = 3

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 5000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "CloudFrontWebACL"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "cloudfront_domain_name" {
  value = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_hosted_zone_id" {
  value = aws_cloudfront_distribution.main.hosted_zone_id
}
'''

    def _get_vpc_peering_template(self, session: DecisionSession) -> str:
        """Template for VPC peering."""
        return '''# VPC Peering Configuration
# Direct peering connections between VPCs
#
# Cost: Free to create, pay only for cross-AZ/cross-region data transfer
# Best for: 2-5 VPCs with simple connectivity needs

variable "vpc_pairs" {
  description = "List of VPC pairs to peer"
  type = list(object({
    requester_vpc_id   = string
    accepter_vpc_id    = string
    requester_vpc_cidr = string
    accepter_vpc_cidr  = string
    name               = string
  }))
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Create VPC Peering connections
resource "aws_vpc_peering_connection" "main" {
  for_each = { for idx, pair in var.vpc_pairs : pair.name => pair }

  vpc_id      = each.value.requester_vpc_id
  peer_vpc_id = each.value.accepter_vpc_id
  auto_accept = true

  accepter {
    allow_remote_vpc_dns_resolution = true
  }

  requester {
    allow_remote_vpc_dns_resolution = true
  }

  tags = merge(var.tags, {
    Name = each.value.name
  })
}

output "peering_connection_ids" {
  value = { for k, v in aws_vpc_peering_connection.main : k => v.id }
}
'''

    def _get_transit_gateway_template(self, session: DecisionSession) -> str:
        """Template for Transit Gateway."""
        return '''# Transit Gateway Configuration
# Hub-and-spoke connectivity for VPCs
#
# Cost estimate:
# - $36/mo per VPC attachment
# - $0.02/GB data processing

variable "name" {
  description = "Name for the Transit Gateway"
  type        = string
  default     = "main-tgw"
}

variable "amazon_side_asn" {
  description = "ASN for the Amazon side of BGP"
  type        = number
  default     = 64512
}

variable "vpc_attachments" {
  description = "VPCs to attach to Transit Gateway"
  type = list(object({
    vpc_id     = string
    subnet_ids = list(string)
    name       = string
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Transit Gateway
resource "aws_ec2_transit_gateway" "main" {
  description                     = var.name
  amazon_side_asn                 = var.amazon_side_asn
  auto_accept_shared_attachments  = "enable"
  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  dns_support                     = "enable"
  vpn_ecmp_support                = "enable"

  tags = merge(var.tags, {
    Name = var.name
  })
}

# VPC Attachments
resource "aws_ec2_transit_gateway_vpc_attachment" "main" {
  for_each = { for idx, vpc in var.vpc_attachments : vpc.name => vpc }

  subnet_ids         = each.value.subnet_ids
  transit_gateway_id = aws_ec2_transit_gateway.main.id
  vpc_id             = each.value.vpc_id

  dns_support = "enable"

  tags = merge(var.tags, {
    Name = each.value.name
  })
}

# Route Table for spoke VPCs
resource "aws_ec2_transit_gateway_route_table" "spoke" {
  transit_gateway_id = aws_ec2_transit_gateway.main.id

  tags = merge(var.tags, {
    Name = "${var.name}-spoke-rt"
  })
}

output "transit_gateway_id" {
  value = aws_ec2_transit_gateway.main.id
}

output "transit_gateway_route_table_id" {
  value = aws_ec2_transit_gateway_route_table.spoke.id
}

output "attachment_ids" {
  value = { for k, v in aws_ec2_transit_gateway_vpc_attachment.main : k => v.id }
}
'''

    def _get_cloud_wan_template(self, session: DecisionSession) -> str:
        """Template for AWS Cloud WAN."""
        return '''# AWS Cloud WAN Configuration
# Global network with policy-driven management
#
# Cost: Similar to TGW but with global features

variable "global_network_name" {
  description = "Name for the global network"
  type        = string
  default     = "main-global-network"
}

variable "core_network_name" {
  description = "Name for the core network"
  type        = string
  default     = "main-core-network"
}

variable "segments" {
  description = "Network segments (e.g., production, development)"
  type = list(object({
    name        = string
    description = string
    require_attachment_acceptance = bool
  }))
  default = [
    {
      name        = "production"
      description = "Production workloads"
      require_attachment_acceptance = true
    },
    {
      name        = "development"
      description = "Development workloads"
      require_attachment_acceptance = false
    }
  ]
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Global Network
resource "aws_networkmanager_global_network" "main" {
  description = var.global_network_name

  tags = merge(var.tags, {
    Name = var.global_network_name
  })
}

# Core Network Policy Document
data "aws_networkmanager_core_network_policy_document" "main" {
  core_network_configuration {
    vpn_ecmp_support = true
    asn_ranges       = ["64512-64555"]

    edge_locations {
      location = "us-east-1"
      asn      = 64512
    }
  }

  dynamic "segments" {
    for_each = var.segments
    content {
      name                          = segments.value.name
      description                   = segments.value.description
      require_attachment_acceptance = segments.value.require_attachment_acceptance
    }
  }

  segment_actions {
    action     = "share"
    mode       = "attachment-route"
    segment    = "production"
    share_with = ["*"]
  }

  attachment_policies {
    rule_number     = 1
    condition_logic = "or"

    conditions {
      type     = "tag-value"
      operator = "equals"
      key      = "segment"
      value    = "production"
    }

    action {
      association_method = "constant"
      segment            = "production"
    }
  }

  attachment_policies {
    rule_number     = 2
    condition_logic = "or"

    conditions {
      type     = "tag-value"
      operator = "equals"
      key      = "segment"
      value    = "development"
    }

    action {
      association_method = "constant"
      segment            = "development"
    }
  }
}

# Core Network
resource "aws_networkmanager_core_network" "main" {
  global_network_id = aws_networkmanager_global_network.main.id
  policy_document   = data.aws_networkmanager_core_network_policy_document.main.json

  tags = merge(var.tags, {
    Name = var.core_network_name
  })
}

output "global_network_id" {
  value = aws_networkmanager_global_network.main.id
}

output "core_network_id" {
  value = aws_networkmanager_core_network.main.id
}

output "core_network_arn" {
  value = aws_networkmanager_core_network.main.arn
}
'''

    def _get_site_vpn_template(self, session: DecisionSession) -> str:
        """Template for site-to-site VPN."""
        return '''# Site-to-Site VPN Configuration
# IPsec VPN tunnels to on-premises
#
# Cost: $36/mo per connection (includes 2 tunnels)

variable "transit_gateway_id" {
  description = "Transit Gateway ID (if using TGW)"
  type        = string
  default     = null
}

variable "vpn_gateway_id" {
  description = "VPN Gateway ID (if using VGW)"
  type        = string
  default     = null
}

variable "customer_gateway_ip" {
  description = "Public IP of customer gateway device"
  type        = string
}

variable "customer_gateway_bgp_asn" {
  description = "BGP ASN of customer gateway"
  type        = number
  default     = 65000
}

variable "destination_cidr_blocks" {
  description = "On-premises CIDR blocks"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Customer Gateway
resource "aws_customer_gateway" "main" {
  bgp_asn    = var.customer_gateway_bgp_asn
  ip_address = var.customer_gateway_ip
  type       = "ipsec.1"

  tags = merge(var.tags, {
    Name = "main-customer-gateway"
  })
}

# VPN Connection (to Transit Gateway)
resource "aws_vpn_connection" "main" {
  count = var.transit_gateway_id != null ? 1 : 0

  customer_gateway_id = aws_customer_gateway.main.id
  transit_gateway_id  = var.transit_gateway_id
  type                = "ipsec.1"

  static_routes_only = false

  tags = merge(var.tags, {
    Name = "main-vpn-connection"
  })
}

# VPN Connection (to VPN Gateway - legacy)
resource "aws_vpn_connection" "vgw" {
  count = var.vpn_gateway_id != null ? 1 : 0

  customer_gateway_id = aws_customer_gateway.main.id
  vpn_gateway_id      = var.vpn_gateway_id
  type                = "ipsec.1"

  static_routes_only = false

  tags = merge(var.tags, {
    Name = "main-vpn-connection"
  })
}

output "customer_gateway_id" {
  value = aws_customer_gateway.main.id
}

output "vpn_connection_id" {
  value = var.transit_gateway_id != null ? aws_vpn_connection.main[0].id : aws_vpn_connection.vgw[0].id
}

output "tunnel1_address" {
  value = var.transit_gateway_id != null ? aws_vpn_connection.main[0].tunnel1_address : aws_vpn_connection.vgw[0].tunnel1_address
}

output "tunnel2_address" {
  value = var.transit_gateway_id != null ? aws_vpn_connection.main[0].tunnel2_address : aws_vpn_connection.vgw[0].tunnel2_address
}
'''

    def _get_accelerated_vpn_template(self, session: DecisionSession) -> str:
        """Template for accelerated site-to-site VPN."""
        return '''# Accelerated Site-to-Site VPN Configuration
# VPN with Global Accelerator for improved performance
#
# Cost: $36/mo VPN + approx. $36/mo accelerator charges

# Similar to standard VPN but with enable_acceleration = true
# and accelerator endpoint outputs

variable "transit_gateway_id" {
  type = string
}

variable "customer_gateway_ip" {
  type = string
}

variable "customer_gateway_bgp_asn" {
  type    = number
  default = 65000
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_customer_gateway" "main" {
  bgp_asn    = var.customer_gateway_bgp_asn
  ip_address = var.customer_gateway_ip
  type       = "ipsec.1"

  tags = merge(var.tags, {
    Name = "accelerated-customer-gateway"
  })
}

resource "aws_vpn_connection" "accelerated" {
  customer_gateway_id   = aws_customer_gateway.main.id
  transit_gateway_id    = var.transit_gateway_id
  type                  = "ipsec.1"
  enable_acceleration   = true

  tags = merge(var.tags, {
    Name = "accelerated-vpn-connection"
  })
}

output "vpn_connection_id" {
  value = aws_vpn_connection.accelerated.id
}

output "tunnel1_address" {
  value = aws_vpn_connection.accelerated.tunnel1_address
}
'''

    def _get_direct_connect_template(self, session: DecisionSession) -> str:
        """Template for Direct Connect setup."""
        return '''# AWS Direct Connect Configuration
# Dedicated network connection
#
# Cost: Port fee + carrier circuit (varies widely)

# Note: Direct Connect requires physical circuit provisioning
# This Terraform sets up the AWS side (Virtual Interface)

variable "connection_id" {
  description = "Direct Connect connection ID (from AWS console or partner)"
  type        = string
}

variable "vlan" {
  description = "VLAN number for the virtual interface"
  type        = number
}

variable "amazon_address" {
  description = "Amazon side IP address (CIDR notation)"
  type        = string
}

variable "customer_address" {
  description = "Customer side IP address (CIDR notation)"
  type        = string
}

variable "bgp_asn" {
  description = "Customer BGP ASN"
  type        = number
  default     = 65000
}

variable "transit_gateway_id" {
  description = "Transit Gateway ID for transit VIF"
  type        = string
  default     = null
}

variable "virtual_gateway_id" {
  description = "Virtual Private Gateway ID for private VIF"
  type        = string
  default     = null
}

variable "tags" {
  type    = map(string)
  default = {}
}

# Transit Virtual Interface (connects to TGW)
resource "aws_dx_transit_virtual_interface" "main" {
  count = var.transit_gateway_id != null ? 1 : 0

  connection_id  = var.connection_id
  dx_gateway_id  = aws_dx_gateway.main[0].id
  name           = "main-transit-vif"
  vlan           = var.vlan
  amazon_address = var.amazon_address
  bgp_asn        = var.bgp_asn
  mtu            = 8500

  tags = var.tags
}

# Direct Connect Gateway
resource "aws_dx_gateway" "main" {
  count = var.transit_gateway_id != null ? 1 : 0

  name            = "main-dx-gateway"
  amazon_side_asn = 64512
}

# Associate DX Gateway with Transit Gateway
resource "aws_dx_gateway_association" "main" {
  count = var.transit_gateway_id != null ? 1 : 0

  dx_gateway_id         = aws_dx_gateway.main[0].id
  associated_gateway_id = var.transit_gateway_id
}

output "dx_gateway_id" {
  value = var.transit_gateway_id != null ? aws_dx_gateway.main[0].id : null
}

output "virtual_interface_id" {
  value = var.transit_gateway_id != null ? aws_dx_transit_virtual_interface.main[0].id : null
}
'''

    def _get_client_vpn_template(self, session: DecisionSession) -> str:
        """Template for AWS Client VPN."""
        return '''# AWS Client VPN Configuration
# Managed OpenVPN-compatible client VPN
#
# Cost: $72/mo per subnet + $0.05/hr per active connection

variable "vpc_id" {
  description = "VPC ID for Client VPN"
  type        = string
}

variable "target_subnet_ids" {
  description = "Subnet IDs to associate with Client VPN"
  type        = list(string)
}

variable "client_cidr_block" {
  description = "CIDR block for VPN clients"
  type        = string
  default     = "10.100.0.0/16"
}

variable "server_certificate_arn" {
  description = "ACM certificate ARN for server"
  type        = string
}

variable "authentication_type" {
  description = "Authentication type"
  type        = string
  default     = "certificate-authentication"
}

variable "root_certificate_chain_arn" {
  description = "ACM certificate ARN for client authentication"
  type        = string
  default     = null
}

variable "saml_provider_arn" {
  description = "SAML provider ARN for SSO authentication"
  type        = string
  default     = null
}

variable "target_network_cidr" {
  description = "CIDR of target network to authorize"
  type        = string
}

variable "split_tunnel" {
  description = "Enable split tunnel (recommended)"
  type        = bool
  default     = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

# Security Group for Client VPN
resource "aws_security_group" "client_vpn" {
  name        = "client-vpn-sg"
  description = "Security group for Client VPN"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "client-vpn-sg"
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "client_vpn" {
  name              = "/aws/client-vpn/main"
  retention_in_days = 90

  tags = var.tags
}

resource "aws_cloudwatch_log_stream" "client_vpn" {
  name           = "connection-log"
  log_group_name = aws_cloudwatch_log_group.client_vpn.name
}

# Client VPN Endpoint
resource "aws_ec2_client_vpn_endpoint" "main" {
  description            = "Main Client VPN Endpoint"
  server_certificate_arn = var.server_certificate_arn
  client_cidr_block      = var.client_cidr_block
  split_tunnel           = var.split_tunnel
  transport_protocol     = "udp"
  security_group_ids     = [aws_security_group.client_vpn.id]
  vpc_id                 = var.vpc_id

  authentication_options {
    type                       = var.authentication_type
    root_certificate_chain_arn = var.authentication_type == "certificate-authentication" ? var.root_certificate_chain_arn : null
    saml_provider_arn          = var.authentication_type == "federated-authentication" ? var.saml_provider_arn : null
  }

  connection_log_options {
    enabled               = true
    cloudwatch_log_group  = aws_cloudwatch_log_group.client_vpn.name
    cloudwatch_log_stream = aws_cloudwatch_log_stream.client_vpn.name
  }

  tags = merge(var.tags, {
    Name = "main-client-vpn"
  })
}

# Network Associations
resource "aws_ec2_client_vpn_network_association" "main" {
  count                  = length(var.target_subnet_ids)
  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.main.id
  subnet_id              = var.target_subnet_ids[count.index]
}

# Authorization Rule
resource "aws_ec2_client_vpn_authorization_rule" "main" {
  client_vpn_endpoint_id = aws_ec2_client_vpn_endpoint.main.id
  target_network_cidr    = var.target_network_cidr
  authorize_all_groups   = true
}

output "client_vpn_endpoint_id" {
  value = aws_ec2_client_vpn_endpoint.main.id
}

output "client_vpn_dns_name" {
  value = aws_ec2_client_vpn_endpoint.main.dns_name
}
'''

    def _get_self_managed_vpn_template(self, session: DecisionSession) -> str:
        """Template for self-managed VPN on EC2."""
        return '''# Self-Managed VPN Configuration
# OpenVPN or WireGuard on EC2
#
# Cost: EC2 instance cost only (approx. $30-100/mo)
# Scales better for large user counts

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "vpn_type" {
  description = "VPN software to install"
  type        = string
  default     = "wireguard"  # or "openvpn"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# This is a placeholder - would include:
# - EC2 instance with user_data for VPN setup
# - Security group
# - Elastic IP
# - (Optional) Auto Scaling for HA

output "vpn_public_ip" {
  value       = "placeholder"
  description = "Public IP of VPN server"
}
'''

    def _get_security_services_template(self, compliance: list[str]) -> str:
        """Template for security services stack."""
        return '''# Security Services Stack
# Core security services for SOC 2 compliance
#
# Cost: approx. $50/mo for baseline, scales with resource count

variable "enable_guardduty" {
  type    = bool
  default = true
}

variable "enable_security_hub" {
  type    = bool
  default = true
}

variable "enable_config" {
  type    = bool
  default = true
}

variable "enable_inspector" {
  type    = bool
  default = true
}

variable "enable_macie" {
  type    = bool
  default = false
}

variable "tags" {
  type    = map(string)
  default = {}
}

# GuardDuty
resource "aws_guardduty_detector" "main" {
  count  = var.enable_guardduty ? 1 : 0
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  tags = var.tags
}

# Security Hub
resource "aws_securityhub_account" "main" {
  count                        = var.enable_security_hub ? 1 : 0
  enable_default_standards     = true
  control_finding_generator    = "SECURITY_CONTROL"
  auto_enable_controls         = true
}

# Enable CIS AWS Foundations Benchmark
resource "aws_securityhub_standards_subscription" "cis" {
  count         = var.enable_security_hub ? 1 : 0
  standards_arn = "arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.4.0"
  depends_on    = [aws_securityhub_account.main]
}

# Enable AWS Foundational Security Best Practices
resource "aws_securityhub_standards_subscription" "aws_foundational" {
  count         = var.enable_security_hub ? 1 : 0
  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.main]
}

# AWS Config
resource "aws_config_configuration_recorder" "main" {
  count    = var.enable_config ? 1 : 0
  name     = "main-recorder"
  role_arn = aws_iam_role.config[0].arn

  recording_group {
    all_supported = true
    include_global_resource_types = true
  }
}

resource "aws_config_configuration_recorder_status" "main" {
  count      = var.enable_config ? 1 : 0
  name       = aws_config_configuration_recorder.main[0].name
  is_enabled = true
  depends_on = [aws_config_delivery_channel.main]
}

resource "aws_config_delivery_channel" "main" {
  count          = var.enable_config ? 1 : 0
  name           = "main-delivery-channel"
  s3_bucket_name = aws_s3_bucket.config[0].id
  depends_on     = [aws_config_configuration_recorder.main]
}

# Config S3 Bucket
resource "aws_s3_bucket" "config" {
  count  = var.enable_config ? 1 : 0
  bucket = "config-bucket-${data.aws_caller_identity.current.account_id}"

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "config" {
  count  = var.enable_config ? 1 : 0
  bucket = aws_s3_bucket.config[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

# Config IAM Role
resource "aws_iam_role" "config" {
  count = var.enable_config ? 1 : 0
  name  = "aws-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "config.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "config" {
  count      = var.enable_config ? 1 : 0
  role       = aws_iam_role.config[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

# Inspector
resource "aws_inspector2_enabler" "main" {
  count         = var.enable_inspector ? 1 : 0
  account_ids   = [data.aws_caller_identity.current.account_id]
  resource_types = ["EC2", "ECR", "LAMBDA"]
}

# Macie (optional - can be expensive for large S3)
resource "aws_macie2_account" "main" {
  count                        = var.enable_macie ? 1 : 0
  finding_publishing_frequency = "FIFTEEN_MINUTES"
  status                       = "ENABLED"
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

output "guardduty_detector_id" {
  value = var.enable_guardduty ? aws_guardduty_detector.main[0].id : null
}

output "security_hub_enabled" {
  value = var.enable_security_hub
}

output "config_recorder_id" {
  value = var.enable_config ? aws_config_configuration_recorder.main[0].id : null
}
'''

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
        """Generate CloudTrail Terraform with SOC 2 configuration."""
        retention_days = config.get("retention_days", 2555)

        return f'''# CloudTrail Configuration with SOC 2 Compliance

resource "aws_cloudtrail" "main" {{
  name                          = "soc2-audit-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = {str(config.get("multi_region", True)).lower()}
  enable_log_file_validation    = {str(config.get("log_validation", True)).lower()}

  event_selector {{
    read_write_type           = "All"
    include_management_events = true
  }}

  tags = {{
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }}
}}

# S3 bucket for CloudTrail logs
resource "aws_s3_bucket" "cloudtrail" {{
  bucket = "cloudtrail-logs-${{data.aws_caller_identity.current.account_id}}"

  tags = {{
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }}
}}

# Enable versioning (required for compliance)
resource "aws_s3_bucket_versioning" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  versioning_configuration {{
    status = "Enabled"
  }}
}}

# Encryption (required for compliance)
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "aws:kms"
      kms_master_key_id = aws_kms_key.cloudtrail.arn
    }}
  }}
}}

# {retention_days}-day retention (SOC 2 requirement: 7 years)
resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail" {{
  bucket = aws_s3_bucket.cloudtrail.id

  rule {{
    id     = "soc2-retention"
    status = "Enabled"

    expiration {{
      days = {retention_days}
    }}
  }}
}}

# KMS key for encryption
resource "aws_kms_key" "cloudtrail" {{
  description             = "KMS key for CloudTrail log encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  tags = {{
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }}
}}

resource "aws_kms_alias" "cloudtrail" {{
  name          = "alias/cloudtrail"
  target_key_id = aws_kms_key.cloudtrail.key_id
}}

data "aws_caller_identity" "current" {{}}
'''

    def _generate_guardduty_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate GuardDuty Terraform."""
        return '''# GuardDuty Configuration

resource "aws_guardduty_detector" "main" {
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  finding_publishing_frequency = "FIFTEEN_MINUTES"

  tags = {
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }
}

output "guardduty_detector_id" {
  value = aws_guardduty_detector.main.id
}
'''

    def _generate_config_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate AWS Config Terraform."""
        return '''# AWS Config Configuration

resource "aws_config_configuration_recorder" "main" {
  name     = "soc2-config-recorder"
  role_arn = aws_iam_role.config.arn

  recording_group {
    all_supported = true
    include_global_resource_types = true
  }
}

resource "aws_config_configuration_recorder_status" "main" {
  name       = aws_config_configuration_recorder.main.name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.main]
}

resource "aws_config_delivery_channel" "main" {
  name           = "soc2-delivery-channel"
  s3_bucket_name = aws_s3_bucket.config.id

  snapshot_delivery_properties {
    delivery_frequency = "TwentyFour_Hours"
  }

  depends_on = [aws_config_configuration_recorder.main]
}

# S3 bucket for Config snapshots
resource "aws_s3_bucket" "config" {
  bucket = "config-snapshots-${data.aws_caller_identity.current.account_id}"

  tags = {
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }
}

# IAM role for Config
resource "aws_iam_role" "config" {
  name = "aws-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "config.amazonaws.com"
      }
    }]
  })

  tags = {
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }
}

resource "aws_iam_role_policy_attachment" "config" {
  role       = aws_iam_role.config.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

data "aws_caller_identity" "current" {}
'''

    def _generate_security_hub_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate Security Hub Terraform."""
        return '''# Security Hub Configuration

resource "aws_securityhub_account" "main" {
  enable_default_standards     = true
  control_finding_generator    = "SECURITY_CONTROL"
  auto_enable_controls         = true
}

# Enable CIS AWS Foundations Benchmark
resource "aws_securityhub_standards_subscription" "cis" {
  standards_arn = "arn:aws:securityhub:::ruleset/cis-aws-foundations-benchmark/v/1.4.0"
  depends_on    = [aws_securityhub_account.main]
}

# Enable AWS Foundational Security Best Practices
resource "aws_securityhub_standards_subscription" "aws_foundational" {
  standards_arn = "arn:aws:securityhub:${data.aws_region.current.name}::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.main]
}

data "aws_region" "current" {}
'''

    def _generate_inspector_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate Inspector Terraform."""
        return '''# Amazon Inspector Configuration

resource "aws_inspector2_enabler" "main" {
  account_ids   = [data.aws_caller_identity.current.account_id]
  resource_types = ["EC2", "ECR", "LAMBDA"]
}

data "aws_caller_identity" "current" {}
'''

    def _generate_vpc_flow_logs_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate VPC Flow Logs Terraform."""
        return '''# VPC Flow Logs Configuration

# Note: Apply this to each VPC in your account

resource "aws_flow_log" "vpc" {
  for_each = toset(var.vpc_ids)

  iam_role_arn    = aws_iam_role.flow_logs.arn
  log_destination = aws_s3_bucket.flow_logs.arn
  traffic_type    = "ALL"
  vpc_id          = each.value

  destination_options {
    file_format        = "parquet"
    per_hour_partition = true
  }

  tags = {
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }
}

# S3 bucket for flow logs
resource "aws_s3_bucket" "flow_logs" {
  bucket = "vpc-flow-logs-${data.aws_caller_identity.current.account_id}"

  tags = {
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }
}

# IAM role for flow logs
resource "aws_iam_role" "flow_logs" {
  name = "vpc-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "vpc-flow-logs.amazonaws.com"
      }
    }]
  })
}

variable "vpc_ids" {
  description = "List of VPC IDs to enable flow logs on"
  type        = list(string)
}

data "aws_caller_identity" "current" {}
'''

    def _generate_iam_password_policy_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate IAM Password Policy Terraform."""
        min_length = config.get("minimum_length", 14)
        max_age = config.get("max_age_days", 90)
        reuse_prevention = config.get("reuse_prevention", 24)

        return f'''# IAM Password Policy Configuration

resource "aws_iam_account_password_policy" "soc2" {{
  minimum_password_length        = {min_length}
  require_uppercase_characters   = true
  require_lowercase_characters   = true
  require_numbers                = true
  require_symbols                = true
  allow_users_to_change_password = true
  max_password_age               = {max_age}
  password_reuse_prevention      = {reuse_prevention}
}}
'''

    def _generate_kms_terraform(self, config: dict, session: DecisionSession) -> str:
        """Generate KMS key Terraform."""
        return '''# KMS Customer Managed Key

resource "aws_kms_key" "main" {
  description             = "KMS key for data encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30

  tags = {
    Compliance = "SOC2"
    ManagedBy  = "CARL"
  }
}

resource "aws_kms_alias" "main" {
  name          = "alias/soc2-encryption"
  target_key_id = aws_kms_key.main.key_id
}

output "kms_key_arn" {
  value = aws_kms_key.main.arn
}
'''

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
